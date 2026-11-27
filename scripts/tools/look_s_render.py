#!/usr/bin/env python3
"""
look_s_render.py (v7.9.0 tool set, audit 7.9.1) — stateless Look S CLI driver: scenes.json + words + A-roll -> compositor master MP4.

Replaces the per-project hand-written driver (scene map + per-frame renderers + segment build + compose). It reads the scene list that
`studio_recipe.py --out scenes.json` writes ({look, duration, scenes: [{id, start, end, mode, kind, hue, jewel, bg, text, ...}]}),
renders one cached plate segment per scene with the fast_studio_compositor API and composes the master with the voice:

  H / A2  full-screen B-roll (cover crop + slow push, or `render_product_stage` when the scene has `stage`) + `render_squircle_pip_window`
  A1      `render_full_head_studio_card` (dark card, jewel rim + halo) on a dark jewel world
  P       `render_full_head_studio_card` (light card) on the polarity paper; `popout: true` -> `render_popout_studio_card` on lavender paper
  B       `render_bottom_flush_cutout` on dark silk, jewel rim
  S       B cutout + a giant gradient numeral (`render_gradient_italic_headline`) behind the head
  N       `apply_fullwidth_neon_rim_blackout` (hard blackout on the cut, then settle)
  then    `pipe_encode_single_plate_fast` per scene (cache key = config hash) -> `verify_audio_voice_sync_guard` ->
          `compose_master_mp4_via_ffmpeg` (optional kt `.mov` plates / screen VFX from --overlays) -> ffprobe of the master.

Optional per-scene keys: broll (file, relative to --broll-dir), broll_ss (s), stage (product-stage s, e.g. 0.72), pip (br | bl),
popout (bool), photo_scale, cam ([from, to]), numeral (text). B / S / N / pop-out need a person matte: --alpha-npy (uint8 N x h x w at
--alpha-fps) or the matte model of `resolve_matte_model_path` (u2netp ~0.1 s / frame; birefnet-portrait ~30 s / frame).
Look S geometry is 1080x1920 portrait: a 1080x1920 A-roll is used as is, another 9:16 size is scaled (warning), anything else is refused.
Output: one JSON summary on stdout (logs on stderr). Exit 0 ok, 2 invalid input, 3 voice guard rejected, 4 render / compose failure.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fast_studio_compositor as fsc  # noqa: E402

VERSION = "7.9.0"
W, H = fsc.LOOK_S_W, fsc.LOOK_S_H
EXIT_OK, EXIT_INPUT, EXIT_VOICE, EXIT_RENDER = 0, 2, 3, 4
RENDERERS = {"H": "render_squircle_pip_window", "A2": "render_squircle_pip_window", "A1": "render_full_head_studio_card",
             "P": "render_full_head_studio_card", "B": "render_bottom_flush_cutout", "S": "render_bottom_flush_cutout",
             "N": "apply_fullwidth_neon_rim_blackout"}
ALPHA_MODES = {"B", "S", "N"}
BROLL_MODES = {"H", "A2"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
PIP_RECTS = {"br": (700, 1446, 1012, 1836), "bl": (68, 1446, 380, 1836)}
DARK_CARD, LIGHT_CARD = (96, 800, 984, 1810), (86, 790, 994, 1810)
FFMPEG_TIMEOUT_S = 900
TOL_S = 1e-3


class InputError(Exception):
    """Invalid input (exit 2)."""


class VoiceError(Exception):
    """Voice guard rejected the voice track (exit 3)."""


def _log(msg: str) -> None:
    print(f"[look_s_render] {msg}", file=sys.stderr, flush=True)


# ============================================================================================ input validation
def _load_json(path: Path, what: str) -> Any:
    if not path.is_file():
        raise InputError(f"{what} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"{what} is not valid UTF-8 JSON ({path}): {exc}") from exc


def load_scenes(path: Path) -> tuple[float, list[dict]]:
    """Scenes of a studio_recipe scenes.json (start / end; t0 / t1 accepted), checked: Look S, known modes, from 0, contiguous."""
    doc = _load_json(path, "scenes file")
    if isinstance(doc, dict) and doc.get("look", "S") != "S":
        raise InputError(f"look {doc.get('look')!r}: look_s_render renders Look S only (Look D is web_plate_builder screen_strip)")
    raw = doc.get("scenes") if isinstance(doc, dict) else doc
    if not isinstance(raw, list) or not raw:
        raise InputError(f"{path}: no 'scenes' list")
    scenes = []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            raise InputError(f"scene #{i} is not an object")
        sid = str(s.get("id", f"S{i + 1:02d}"))
        mode = s.get("mode")
        if mode not in RENDERERS:
            raise InputError(f"scene {sid}: mode {mode!r} is not one of {sorted(RENDERERS)}")
        try:
            t0, t1 = float(s.get("start", s.get("t0"))), float(s.get("end", s.get("t1")))
        except (TypeError, ValueError) as exc:
            raise InputError(f"scene {sid}: start / end must be numbers") from exc
        if not t1 > t0:
            raise InputError(f"scene {sid}: end {t1} <= start {t0}")
        scenes.append({**s, "id": sid, "mode": mode, "t0": t0, "t1": t1})
    if abs(scenes[0]["t0"]) > TOL_S:
        raise InputError(f"scenes must start at 0 s (first scene {scenes[0]['id']} starts at {scenes[0]['t0']})")
    for a, b in zip(scenes, scenes[1:]):
        if abs(b["t0"] - a["t1"]) > TOL_S:
            raise InputError(f"scenes are not contiguous: {b['id']} starts at {b['t0']} s but {a['id']} ends at {a['t1']} s")
    if len({s["id"] for s in scenes}) != len(scenes):
        raise InputError("scene ids must be unique")
    end = scenes[-1]["t1"]
    dur = float(doc.get("duration", end)) if isinstance(doc, dict) else end
    if abs(dur - end) > TOL_S:
        raise InputError(f"duration {dur} s does not match the last scene end {end} s")
    return end, scenes


def load_words(path: Path) -> list[tuple[str, float, float]]:
    """words_tl.json: a bare list or {words | words_tl: [...]}, each [word, start, end] or {word|w|text, start|t0, end|t1}."""
    doc = _load_json(path, "words file")
    seq = (doc.get("words") or doc.get("words_tl")) if isinstance(doc, dict) else doc
    if not isinstance(seq, list):
        raise InputError(f"{path}: expected a list of words or {{'words': [...]}}")
    out = []
    for i, w in enumerate(seq):
        try:
            if isinstance(w, dict):
                txt, a, b = w.get("word", w.get("w", w.get("text"))), w.get("start", w.get("t0")), w.get("end", w.get("t1"))
            else:
                txt, a, b = w[0], w[1], w[2]
            a, b = float(a), float(b)
        except (TypeError, ValueError, IndexError, KeyError) as exc:
            raise InputError(f"word #{i} is not [word, start, end]: {w!r}") from exc
        if b < a:
            raise InputError(f"word #{i} {txt!r} ends before it starts ({a} > {b})")
        out.append((str(txt), a, b))
    return out


def _probe(path: Path, what: str) -> dict:
    try:
        return fsc.probe_video(path)
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired) as exc:
        raise InputError(f"{what}: {exc}") from exc


def _hex_rgb(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(value or ""))
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else default  # type: ignore[return-value]


def _file_key(p: Path | None) -> list:
    if p is None:
        return []
    st = p.stat()
    return [str(p.resolve()), st.st_size, int(st.st_mtime)]


def _matte_plan(args: argparse.Namespace, alpha_ids: list[str], duration: float, warnings: list[str]) -> dict | None:
    if not alpha_ids:
        return None
    if args.alpha_npy:
        p = Path(args.alpha_npy)
        if not p.is_file():
            raise InputError(f"--alpha-npy not found: {p}")
        try:
            arr = np.load(p, mmap_mode="r")
        except (OSError, ValueError) as exc:
            raise InputError(f"--alpha-npy is not a .npy array ({p}): {exc}") from exc
        if arr.ndim != 3 or arr.shape[0] < 1:
            raise InputError(f"--alpha-npy must be uint8 N x h x w, got shape {arr.shape}")
        need = int(math.ceil(duration * args.alpha_fps))
        if arr.shape[0] < need - 1:
            warnings.append(f"alpha matte has {arr.shape[0]} frames < {need} for {duration:.2f} s at {args.alpha_fps} fps: last frame held")
        return {"kind": "npy", "path": str(p.resolve()), "fps": float(args.alpha_fps), "frames": int(arr.shape[0]), "key": _file_key(p)}
    try:
        model = fsc.resolve_matte_model_path()
    except FileNotFoundError as exc:
        raise InputError(f"scenes {alpha_ids} need a person matte (modes B / S / N / pop-out / --clean-wall) but there is no "
                         f"--alpha-npy and no matte model: {exc}") from exc
    if "birefnet" in model.name:
        warnings.append(f"matte model is birefnet-portrait ({model}): ~30 s per frame on CPU; pass --alpha-npy or install u2netp")
    return {"kind": "model", "path": str(model), "key": _file_key(model)}


def _assign_broll(scenes: list[dict], broll_dir: Path | None, warnings: list[str]) -> None:
    """Fill sc['broll_src'] / sc['broll_ss'] for H / A2 scenes: explicit `broll` first, else round-robin over --broll-dir; every file
    continues where its previous use ended, so source seconds are not reused (a reuse is reported)."""
    files = sorted(p for p in broll_dir.iterdir() if p.suffix.lower() in VIDEO_EXT) if broll_dir else []
    used: dict[str, list[tuple[float, float]]] = {}
    infos: dict[str, dict] = {}
    rr = 0
    for sc in scenes:
        if sc["mode"] not in BROLL_MODES:
            continue
        if sc.get("broll"):
            p = Path(sc["broll"])
            p = p if p.is_absolute() or broll_dir is None else broll_dir / p
        elif files:
            p, rr = files[rr % len(files)], rr + 1
        else:
            warnings.append(f"scene {sc['id']} ({sc['mode']}): no B-roll (no --broll-dir / 'broll'): PiP on a dark jewel world")
            continue
        key = str(p.resolve()) if p.exists() else str(p)
        info = infos.get(key) or _probe(p, f"B-roll of scene {sc['id']}")
        infos[key] = info
        dur = sc["t1"] - sc["t0"]
        prev = used.setdefault(key, [])
        ss = float(sc.get("broll_ss", prev[-1][1] if prev else 0.0))
        if ss + dur > info["duration"] + TOL_S and "broll_ss" not in sc:
            ss = 0.0                                          # file used up: wrap (the reuse is reported below)
        if ss + dur > info["duration"] + TOL_S:
            warnings.append(f"scene {sc['id']}: B-roll {p.name} has {info['duration']:.2f} s < {ss + dur:.2f} s needed: last frame held")
        if any(ss < b - TOL_S and a < ss + dur - TOL_S for a, b in prev):
            warnings.append(f"scene {sc['id']}: B-roll source seconds reused ({p.name} {ss:.2f}-{ss + dur:.2f} s); add footage or set broll_ss")
        prev.append((ss, ss + dur))
        sc["broll_src"], sc["broll_ss"], sc["broll_info"] = str(p.resolve()), round(ss, 4), info


def _load_overlays(path: Path | None) -> tuple[list[dict], list[dict]]:
    if path is None:
        return [], []
    doc = _load_json(path, "overlays file")
    ovs, vfx = (doc, []) if isinstance(doc, list) else (doc.get("overlays", []), doc.get("screen_vfx", []))
    for kind, items, keys in (("overlay", ovs, ("src", "at", "dur", "cx", "cy", "orig_w", "orig_h")), ("screen_vfx", vfx, ("src", "at", "dur"))):
        for i, it in enumerate(items):
            miss = [k for k in keys if k not in it]
            if miss:
                raise InputError(f"{kind} #{i} lacks {miss}")
            src = Path(it["src"])
            it["src"] = str(src if src.is_absolute() else (path.parent / src))
            if not Path(it["src"]).is_file():
                raise InputError(f"{kind} #{i} src not found: {it['src']}")
    return ovs, vfx


def build_plan(args: argparse.Namespace) -> dict:
    """Validate every input and lay out the per-scene plan (frames, renderer, B-roll, segment path). No rendering, no writes."""
    warnings: list[str] = []
    gear = fsc.RenderGear.master() if args.master else fsc.RenderGear.draft()
    duration, scenes = load_scenes(Path(args.scenes))
    words = load_words(Path(args.words))
    if words and words[-1][2] > duration + 0.05:
        warnings.append(f"last word ends at {words[-1][2]:.2f} s after the timeline end {duration:.2f} s")
    aroll_p = Path(args.aroll)
    aroll = _probe(aroll_p, "A-roll")
    geo = fsc.check_look_s_geometry(aroll["width"], aroll["height"])
    if geo["status"] == "refuse":
        raise InputError(f"A-roll {aroll_p.name}: {geo['message']}")
    if geo["status"] == "scale":
        warnings.append(f"A-roll {geo['message']}")
    if aroll["fps"] < 24:
        warnings.append(f"A-roll is {aroll['fps']} fps (< 24): motion will judder at {gear.fps} fps")
    elif aroll["fps"] + 0.01 < gear.fps:
        warnings.append(f"A-roll is {aroll['fps']} fps < gear {gear.fps} fps: source frames are repeated")
    if aroll["duration"] and aroll["duration"] + 0.05 < duration:
        raise InputError(f"A-roll is {aroll['duration']:.2f} s, shorter than the {duration:.2f} s timeline")
    audio_p = Path(args.audio) if args.audio else None
    if audio_p is not None and not audio_p.is_file():
        raise InputError(f"--audio not found: {audio_p}")
    if audio_p is None and not aroll["has_audio"]:
        raise InputError(f"A-roll {aroll_p.name} has no audio stream: pass --audio voice.wav")
    broll_dir = Path(args.broll_dir) if args.broll_dir else None
    if broll_dir is not None and not broll_dir.is_dir():
        raise InputError(f"--broll-dir is not a folder: {broll_dir}")
    _assign_broll(scenes, broll_dir, warnings)
    popout_default = fsc.LOOK_S_POPOUT
    for sc in scenes:
        sc["popout"] = bool(sc.get("popout", popout_default)) and sc["mode"] in ("P", "A1")
        sc["renderer"] = "render_popout_studio_card" if sc["popout"] else RENDERERS[sc["mode"]]
        sc["needs_alpha"] = bool(args.clean_wall or sc["mode"] in ALPHA_MODES or sc["popout"])
    matte = _matte_plan(args, [s["id"] for s in scenes if s["needs_alpha"]], duration, warnings)
    overlays, vfx = _load_overlays(Path(args.overlays) if args.overlays else None)
    work = Path(args.work)
    segs, n_step, plan_scenes = work / "segs", 0, []
    for sc in scenes:
        f0, f1 = round(sc["t0"] * gear.fps), round(sc["t1"] * gear.fps)
        if f1 <= f0:
            raise InputError(f"scene {sc['id']} is shorter than one frame at {gear.fps} fps")
        n_step += sc["mode"] == "S"
        sc["step"] = n_step
        payload = {"v": VERSION, "scene": {k: v for k, v in sc.items() if k != "broll_info"}, "f": [f0, f1], "gear": gear.name,
                   "aroll": _file_key(aroll_p), "matte": matte["key"] if (matte and sc["needs_alpha"]) else None,
                   "broll": _file_key(Path(sc["broll_src"])) if sc.get("broll_src") else None,
                   "clean_wall": [bool(args.clean_wall), float(args.wall_ref_t)]}
        seg = segs / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', sc['id'])}_{fsc.compute_segment_config_hash(payload)}.mp4"
        plan_scenes.append({**sc, "f0": f0, "f1": f1, "frames": f1 - f0, "segment": str(seg)})
    return {"gear": gear, "duration": duration, "scenes": plan_scenes, "aroll": {**aroll, "path": str(aroll_p.resolve()), "geometry": geo["status"]},
            "audio": str(audio_p.resolve()) if audio_p else None, "matte": matte, "overlays": overlays, "screen_vfx": vfx,
            "warnings": warnings, "words": len(words)}


# ============================================================================================ frame sources
def _ffmpeg_frames(path: str, ss: float, n: int, fps: int, vf: str, size: tuple[int, int]) -> Iterator[np.ndarray]:
    """n BGR frames (w x h = size) of `path` from `ss` at `fps` through `vf`; the last frame is held if the source runs out.
    ffmpeg is always killed and reaped (no leak on early close)."""
    w, h = size
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, ss):.6f}", "-i", path, "-vf", f"{vf},fps={fps}" if vf else f"fps={fps}",
           "-frames:v", str(n), "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last, k = None, 0
    try:
        while k < n:
            buf = proc.stdout.read(w * h * 3) if proc.stdout else b""
            if len(buf) < w * h * 3:
                break
            last = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            yield last
            k += 1
    finally:
        proc.kill()
        if proc.stdout:
            proc.stdout.close()
        proc.wait()
    if last is None:
        raise RuntimeError(f"no frames decoded from {path} at {ss:.3f} s")
    for _ in range(n - k):
        yield last


def _one_frame(path: str, t: float, fps: int, vf: str) -> np.ndarray:
    with contextlib.closing(_ffmpeg_frames(path, t, 1, fps, vf, (W, H))) as it:
        return next(it)


def _aroll_vf(geometry: str) -> str:
    return "" if geometry == "exact" else f"scale={W}:{H}:flags=lanczos"


class _Matte:
    """Person alpha (uint8 1080x1920) for an absolute time: from the .npy at its fps, or the matte model on the A-roll frame."""

    def __init__(self, spec: dict | None, src_fps: float):
        self.spec, self.src_fps, self.idx, self.cur, self.arr = spec, src_fps, None, None, None
        if spec and spec["kind"] == "npy":
            self.arr = np.load(spec["path"], mmap_mode="r")

    def get(self, t: float, frame_bgr: np.ndarray) -> np.ndarray:
        if self.spec is None:
            raise RuntimeError("a person matte is needed but none was planned")
        fps = self.spec.get("fps", self.src_fps)
        idx = int(t * fps + 1e-6)
        if idx != self.idx:
            if self.arr is not None:
                a = np.asarray(self.arr[min(idx, self.arr.shape[0] - 1)])
                a = a if a.dtype == np.uint8 else np.clip(a * (255.0 if a.max() <= 1.0 else 1.0), 0, 255).astype(np.uint8)
                self.cur = cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR) if a.shape[:2] != (H, W) else a
            else:
                self.cur = fsc.predict_u2netp_alpha_u8(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            self.idx = idx
        return self.cur


# ============================================================================================ backdrops
def _dark_world(rgb: tuple[int, int, int], cy: float = 0.30, strength: float = 0.22) -> np.ndarray:
    """Near-black world with a soft jewel glow centred at (0.5 W, cy H)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = ((xx - W * 0.5) / (W * 0.75)) ** 2 + ((yy - H * cy) / (H * 0.45)) ** 2
    g = (np.exp(-r2) * strength)[:, :, None]
    base = np.array([13.0, 10.0, 6.0], np.float32)
    col = np.array(rgb[::-1], np.float32)
    return np.clip(base * (1.0 - g) + col * g + 0.5, 0, 255).astype(np.uint8)


def _paper(rgb: tuple[int, int, int]) -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
    lift = np.clip(1.0 - 0.07 * r * r, 0.9, 1.0)[:, :, None]
    return np.clip(np.array(rgb[::-1], np.float32) * lift + 0.5, 0, 255).astype(np.uint8)


def _crown_anchor(alpha_u8: np.ndarray, min_px: int = 14, band: int = 28) -> tuple[float, float] | None:
    m = alpha_u8 >= 128
    rows = np.where(m.sum(axis=1) >= min_px)[0]
    if rows.size == 0:
        return None
    y = int(rows[0])
    xs = np.where(m[y:y + band].any(axis=0))[0]
    return float(xs.mean()), float(y)


# ============================================================================================ per-scene rendering
def _ease(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


def _cam(sc: dict, u: float, a: float, b: float) -> float:
    lo, hi = sc.get("cam", (a, b))
    return float(lo) + (float(hi) - float(lo)) * _ease(u)


def _push(img: np.ndarray, z: float, pivot: tuple[float, float] = (W * 0.5, H * 0.5)) -> np.ndarray:
    if abs(z - 1.0) < 1e-4:
        return img
    M = cv2.getRotationMatrix2D(pivot, 0.0, float(z))
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _prepare(sc: dict, matte: _Matte, task: dict, warns: list[str]) -> dict:
    jewel = _hex_rgb(sc.get("jewel"), (245, 196, 81))
    ctx: dict[str, Any] = {"jewel": jewel}
    mode = sc["mode"]
    if sc["popout"]:
        ctx["bg"] = fsc.render_lavender_paper(W, H)
        pts = []
        for i in range(5):
            t = sc["t0"] + (sc["t1"] - sc["t0"]) * (i + 0.5) / 5
            frame = _one_frame(task["aroll"], t, task["fps"], task["aroll_vf"])
            pt = _crown_anchor(matte.get(t, frame))
            if pt:
                pts.append(pt)
        if pts:
            ctx["anchor"] = (float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts])))
        else:
            warns.append(f"scene {sc['id']}: no crown found in the matte, pop-out uses the compositor default head anchor")
            ctx["anchor"] = (340.0, 549.0)
    elif mode == "P":
        ctx["bg"] = _paper(_hex_rgb(sc.get("hue"), _hex_rgb(sc.get("bg"), (250, 250, 250))))
    elif mode in ("A1", "B", "S", "H", "A2"):
        ctx["bg"] = _dark_world(jewel, 0.30 if mode != "B" else 0.55)
    if mode == "S":
        try:
            ctx["bg"] = fsc.render_gradient_italic_headline(ctx["bg"], str(sc.get("numeral", sc["step"])), None, (540, 520), 300,
                                                            jewel, (255, 255, 255), 0.30)
        except FileNotFoundError as exc:
            warns.append(f"scene {sc['id']}: numeral skipped ({exc})")
    return ctx


def _draw(sc: dict, t: float, ctx: dict, aroll: np.ndarray, alpha: np.ndarray | None, broll: np.ndarray | None) -> np.ndarray:
    u = (t - sc["t0"]) / max(1e-6, sc["t1"] - sc["t0"])
    mode, jewel = sc["mode"], ctx["jewel"]
    if sc["popout"]:
        out, _ = fsc.render_popout_studio_card(ctx["bg"], aroll, alpha, head_anchor=ctx["anchor"],
                                               photo_scale=float(sc.get("photo_scale", 1.36)) * _cam(sc, u, 1.0, 1.02))
        return out
    if mode in BROLL_MODES:
        if broll is None:
            base = ctx["bg"]
        elif sc.get("stage"):
            base = fsc.render_product_stage(broll, s=float(sc["stage"]), zoom=_cam(sc, u, 1.0, 1.06))
        else:
            base = _push(broll, _cam(sc, u, 1.0, 1.06))
        out, _ = fsc.render_squircle_pip_window(base, aroll, pip_rect=PIP_RECTS.get(sc.get("pip", "br"), PIP_RECTS["br"]),
                                                rx=44, rim_rgb=jewel, inner_zoom=1.02 + 0.04 * _ease(u))
        return out
    if mode == "A1":
        out, _ = fsc.render_full_head_studio_card(ctx["bg"], aroll, card_rect=DARK_CARD, cam_scale=_cam(sc, u, 0.96, 0.99), mode="dark",
                                                  border_rgb=jewel, backlight_halo_bgr=tuple(float(c) for c in jewel[::-1]),
                                                  backlight_strength=0.35)
        return out
    if mode == "P":
        out, _ = fsc.render_full_head_studio_card(ctx["bg"], aroll, card_rect=LIGHT_CARD, cam_scale=_cam(sc, u, 0.96, 0.99), mode="light")
        return out
    if mode in ("B", "S"):
        out, _ = fsc.render_bottom_flush_cutout(ctx["bg"], aroll, alpha, cam_scale=_cam(sc, u, 1.015, 1.04), rim_rgb=jewel)
        return out
    z, piv = _cam(sc, u, 1.0, 1.03), (W * 0.5, 1365.0)
    plate, pa = _push(aroll, z, piv), _push(alpha, z, piv)
    ub = 0.88 + 0.12 * _ease((t - sc["t0"]) / 0.10)
    return fsc.apply_fullwidth_neon_rim_blackout(plate, pa, ub)


def render_segment(task: dict) -> dict:
    """Render one scene to its plate segment (process-pool worker; only plain data in / out)."""
    t_start = time.time()
    sc, warns = task["scene"], []
    gear = fsc.RenderGear.master() if task["gear"] == "master" else fsc.RenderGear.draft()
    matte = _Matte(task["matte"], task["src_fps"]) if sc["needs_alpha"] else None
    if task["clean_wall"]:
        ref = _one_frame(task["aroll"], task["wall_ref_t"], gear.fps, task["aroll_vf"])
        fsc.init_hair_safe_wall_reference(ref)
    ctx = _prepare(sc, matte, task, warns)
    n = sc["f1"] - sc["f0"]
    t0 = sc["f0"] / gear.fps
    with contextlib.ExitStack() as stack:
        ar_it = stack.enter_context(contextlib.closing(_ffmpeg_frames(task["aroll"], t0, n, gear.fps, task["aroll_vf"], (W, H))))
        br_it = None
        if sc.get("broll_src"):
            if sc.get("stage"):
                bi = sc["broll_info"]
                br_it = _ffmpeg_frames(sc["broll_src"], sc["broll_ss"], n, gear.fps, "", (bi["width"], bi["height"]))
            else:
                cover = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
                br_it = _ffmpeg_frames(sc["broll_src"], sc["broll_ss"], n, gear.fps, cover, (W, H))
            stack.enter_context(contextlib.closing(br_it))

        def frames() -> Iterator[np.ndarray]:
            for i, aroll in enumerate(ar_it):
                t = (sc["f0"] + i) / gear.fps
                alpha = matte.get(t, aroll) if matte else None
                if task["clean_wall"]:
                    aroll = fsc.clean_aroll_preserve_hair_crown(aroll, person_alpha_u8=alpha)
                yield _draw(sc, t, ctx, aroll, alpha, next(br_it) if br_it else None)

        fsc.pipe_encode_single_plate_fast(frames(), Path(sc["segment"]), gear=gear, threads=2)
    return {"id": sc["id"], "elapsed_s": round(time.time() - t_start, 2), "warnings": warns}


# ============================================================================================ voice + compose + verify
def _voice_wav(plan: dict, work: Path) -> Path:
    if plan["audio"]:
        return Path(plan["audio"])
    key = fsc.compute_segment_config_hash({"aroll": _file_key(Path(plan["aroll"]["path"]))})
    wav = work / f"voice_{key}.wav"
    if not wav.is_file():
        tmp = work / f".tmp_voice_{key}_{os.getpid()}.wav"
        pr = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", plan["aroll"]["path"], "-vn", "-ac", "2", "-ar", "48000",
                             "-c:a", "pcm_s16le", str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=FFMPEG_TIMEOUT_S)
        if pr.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"voice extraction failed: {pr.stderr.strip()[-400:]}")
        os.replace(tmp, wav)
    return wav


def _scene_row(s: dict, cached: bool | None = None) -> dict:
    row = {"id": s["id"], "mode": s["mode"], "t0": s["t0"], "t1": s["t1"], "frames": s["frames"], "renderer": s["renderer"],
           "needs_alpha": s["needs_alpha"], "broll": ({"src": s["broll_src"], "ss": s["broll_ss"]} if s.get("broll_src") else None),
           "segment": s["segment"]}
    if cached is not None:
        row["cached"] = cached
    return row


def _summary(plan: dict) -> dict:
    g = plan["gear"]
    return {"ok": True, "version": VERSION, "gear": {"name": g.name, "width": g.width, "height": g.height, "fps": g.fps},
            "duration": plan["duration"], "aroll": plan["aroll"], "matte": plan["matte"] and {k: v for k, v in plan["matte"].items() if k != "key"},
            "overlays": len(plan["overlays"]), "screen_vfx": len(plan["screen_vfx"]), "words": plan["words"], "warnings": plan["warnings"]}


def run(args: argparse.Namespace) -> dict:
    plan = build_plan(args)
    out = _summary(plan)
    if args.dry_run:
        out.update(dry_run=True, voice_guard="skipped (dry-run)",
                   scenes=[_scene_row(s, Path(s["segment"]).is_file()) for s in plan["scenes"]])
        return out
    t_start = time.time()
    work = Path(args.work)
    (work / "segs").mkdir(parents=True, exist_ok=True)
    wav = _voice_wav(plan, work)
    try:
        out["voice_guard"] = fsc.verify_audio_voice_sync_guard(wav, plan["duration"])
    except ValueError as exc:
        if not args.no_voice_guard:
            raise VoiceError(str(exc)) from exc
        out["voice_guard"] = {"skipped": True, "error": str(exc)}
        plan["warnings"].append(f"voice guard rejected the voice but --no-voice-guard is set: {exc}")
    todo = [s for s in plan["scenes"] if not Path(s["segment"]).is_file()]
    common = {"gear": plan["gear"].name, "aroll": plan["aroll"]["path"], "aroll_vf": _aroll_vf(plan["aroll"]["geometry"]),
              "src_fps": plan["aroll"]["fps"], "fps": plan["gear"].fps, "matte": plan["matte"], "clean_wall": bool(args.clean_wall),
              "wall_ref_t": float(args.wall_ref_t)}
    tasks = [{**common, "scene": s} for s in sorted(todo, key=lambda s: -s["frames"])]
    _log(f"{len(todo)} segment(s) to render, {len(plan['scenes']) - len(todo)} cached, gear {plan['gear'].name}, jobs {args.jobs}")
    results = []
    if args.jobs > 1 and len(tasks) > 1:
        with cf.ProcessPoolExecutor(max_workers=min(args.jobs, len(tasks))) as pool:
            for res in pool.map(render_segment, tasks):
                _log(f"segment {res['id']} {res['elapsed_s']} s")
                results.append(res)
    else:
        for task in tasks:
            res = render_segment(task)
            _log(f"segment {res['id']} {res['elapsed_s']} s")
            results.append(res)
    for res in results:
        plan["warnings"].extend(res["warnings"])
    out_p = Path(args.out)
    fsc.compose_master_mp4_via_ffmpeg([Path(s["segment"]) for s in plan["scenes"]], wav, plan["overlays"], plan["screen_vfx"], out_p,
                                      gear=plan["gear"], threads=max(2, min(8, os.cpu_count() or 2)))
    probe = fsc.probe_video(out_p)
    g = plan["gear"]
    bad = []
    if (probe["width"], probe["height"]) != (g.width, g.height) or abs(probe["fps"] - g.fps) > 0.01:
        bad.append(f"master is {probe['width']}x{probe['height']}@{probe['fps']}, expected {g.width}x{g.height}@{g.fps}")
    if not probe["has_audio"]:
        bad.append("master has no audio stream")
    if bad:
        raise RuntimeError("; ".join(bad))
    if abs(probe["duration"] - plan["duration"]) > 0.1:
        plan["warnings"].append(f"master is {probe['duration']:.2f} s vs the {plan['duration']:.2f} s timeline (-shortest on the voice)")
    out.update(dry_run=False, out=str(out_p.resolve()), output_probe=probe, segments_rendered=len(todo),
               segments_cached=len(plan["scenes"]) - len(todo), elapsed_s=round(time.time() - t_start, 2),
               scenes=[_scene_row(s) for s in plan["scenes"]], warnings=plan["warnings"])
    return out


# ============================================================================================ CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="look_s_render.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Look S driver (v7.9.0): render a studio_recipe scenes.json over a 9:16 A-roll (drawn at 1080x1920) into the "
                    "compositor master MP4. Stateless: every segment is cached in --work by a config hash.",
        epilog="usage: look_s_render.py --scenes scenes.json --words words_tl.json --aroll aroll.mp4 --work WORK --out master.mp4 "
               "[--draft | --master] [--broll-dir DIR] [--alpha-npy alpha.npy] [--dry-run]\n"
               "modes: H/A2 B-roll + squircle PiP, A1 dark card, P paper card (popout: true = pop-out card), B cutout, S numeral + cutout, "
               "N neon blackout.\nexit: 0 ok, 2 invalid input, 3 voice guard rejected, 4 render / compose failure. JSON summary on stdout.")
    ap.add_argument("--scenes", required=True, help="scenes.json from studio_recipe.py (contiguous scenes from 0 s, Look S modes)")
    ap.add_argument("--words", required=True, help="words_tl.json: [[word, start, end], ...] or {'words': [...]}")
    ap.add_argument("--aroll", required=True, help="A-roll video: 9:16 portrait (1080x1920 as is, other 9:16 sizes scaled); needs audio "
                                                   "unless --audio")
    ap.add_argument("--work", required=True, help="work folder (segment cache, extracted voice)")
    ap.add_argument("--out", required=True, help="master .mp4 path")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--draft", action="store_true", help="draft gear 540x960 @ 30 fps (default)")
    g.add_argument("--master", action="store_true", help="master gear 1080x1920 @ 60 fps")
    ap.add_argument("--broll-dir", help="B-roll clips for H / A2 scenes (round-robin, source seconds never reused unless reported)")
    ap.add_argument("--alpha-npy", help="person matte, uint8 N x h x w (e.g. the RVM cache); else the matte model is used")
    ap.add_argument("--alpha-fps", type=float, default=30.0, help="frame rate of --alpha-npy (default 30)")
    ap.add_argument("--audio", help="voice / mix track for the master (default: the A-roll audio)")
    ap.add_argument("--overlays", help="JSON list of kt .mov plates {src, at, dur, cx, cy, orig_w, orig_h, scale?} or "
                                       "{'overlays': [...], 'screen_vfx': [{src, at, dur, opacity?}]}")
    ap.add_argument("--clean-wall", action="store_true", help="run the alpha-guarded wall cleaner (its ROIs are measured on the "
                                                              "reference studio wall; off by default)")
    ap.add_argument("--wall-ref-t", type=float, default=0.0, help="low-head reference frame time for --clean-wall (s)")
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1), help="parallel segment renders (default min(4, CPUs))")
    ap.add_argument("--no-voice-guard", action="store_true", help="report a voice guard rejection as a warning instead of exit 3")
    ap.add_argument("--dry-run", action="store_true", help="validate every input and print the per-scene plan; render nothing")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.jobs < 1:
        args.jobs = 1
    try:
        doc, code = run(args), EXIT_OK
    except InputError as exc:
        doc, code = {"ok": False, "error": str(exc)}, EXIT_INPUT
    except VoiceError as exc:
        doc, code = {"ok": False, "error": str(exc)}, EXIT_VOICE
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:   # BrokenProcessPool is a RuntimeError
        doc, code = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, EXIT_RENDER
    doc["exit"] = code
    print(json.dumps(doc, ensure_ascii=False, indent=1, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
