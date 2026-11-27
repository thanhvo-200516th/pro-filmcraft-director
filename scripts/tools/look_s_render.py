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
v7.9.2 hook auto (on by default): an H / A2 B-roll scene starting inside 0-3.4 s whose source window is static (motion_gate frame diff
< 2.0, hold > 0.8 s) gets a product-anchored Ken Burns push (<= +25 %) + pan + glint (`--no-hook-motion`); kt overlays inside such a
scene are moved off the product box (u2netp saliency, luma / edge fallback) into the nearest clear band (`--no-product-safe-text`).
The summary carries `hook_auto` and `product_bbox` (feed it to studio_recipe.check_hook for `hero_safe_zone`).
v7.9.3 B-roll: `plan_broll` places each H / A2 scene on the file with the most remaining seconds that fits (backtracking, explicit
broll / broll_ss kept), never reusing source seconds (studio_recipe.check_source_reuse: exit 2 unless --allow-broll-reuse), and moves
windows off short-lived stray blobs found by `scan_broll_transients` (`broll_artifacts`; --no-broll-artifact-scan).
v7.9.4: rotated sources (container rotate 90) are read at their display size; --overlays-from-plan builds the overlays from a
plan_dviet_kinetic_beat_schedule plan (`overlays_from_plan`); --emit-overlays / --emit-scenes write the final placed overlays and
the resolved scenes (broll, broll_ss, stage, cam) for the .fcproj mirror; --alpha-fps is part of the segment hash; a hook still
under the motion floor after the punches is a warning (`hook_auto.below_floor_scenes`).
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
import motion_gate as mg  # noqa: E402
import studio_recipe as sr  # noqa: E402

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
HOOK_S = 3.4                                   # hook window (studio_recipe hook_0_5s window_ms)
HOOK_PROBE_FPS, HOOK_PROBE_SIZE = 30, (270, 480)   # motion_gate sampling of the source window
HOOK_GLINT = (0.22, 0.15, 0.85)                # [UOC] glint_sweep amount, sweep from / to as a fraction of the scene
SAFE_ZONE = (50, 140, 1030, 1760)              # platform safe zone x0, y0, x1, y1 for moved text
# [UOC] zoom steps (fsc.snap_punch, its documented 1.00 -> 1.10 in ~67 ms) when the predicted hook motion is under the floor: one
# per ~0.8 s, snapped to a word onset within 0.25 s, >= 0.6 s apart; each snaps +amp about the moving anchor and settles back over
# settle_s; the slow push shrinks so (1 + push) * (1 + amp) <= the +25 % cap; flash 0 = zoom only (else snap_punch luma cap 220)
HOOK_PUNCH = {"every_s": 0.8, "word_snap_s": 0.25, "min_gap_s": 0.6, "first_s": 0.3, "snap_s": 0.067, "settle_s": 0.35, "amp": 0.10,
              "flash": 0.0}
INK_ALPHA_MIN = 24                             # plate alpha above this is ink
# v7.9.3 [UOC] B-roll transient scan (`transient_spans`): 30 fps proxy, long side 480 px; spike vs the frames +-offset_f (0.17 s)
# away > spike_luma; hit when the largest spike blob >= hit_area of the frame; transient = a run (gaps <= gap_f) of <= max_s whose
# peak blob is peak_area..max_area. Tuned on e2e_v791 01_serum_orbit (dropper-glass sliver ~1e-3 of the frame) vs dust specks
# (<= 3.2e-4) and camera motion (runs > 1 s)
ARTIFACT_PROBE_FPS, ARTIFACT_PROBE_LONG = 30, 480
TRANSIENT = {"offset_f": 5, "spike_luma": 60, "hit_area": 2.5e-4, "peak_area": 5e-4, "max_area": 0.02, "gap_f": 2, "max_s": 0.5}
BROLL_SEARCH_NODES = 20000                     # backtracking budget of plan_broll (per pass) before the greedy fallback
# default camera zoom [from, to] per renderer when a scene has no `cam` (popout = photo_scale multiplier); --emit-scenes writes it
CAM_DEFAULTS = {"H": (1.0, 1.06), "A2": (1.0, 1.06), "A1": (0.96, 0.99), "P": (0.96, 0.99), "B": (1.015, 1.04), "S": (1.015, 1.04),
                "N": (1.0, 1.03), "popout": (1.0, 1.02)}
EMIT_DROP = {"broll_info", "broll_src", "needs_alpha", "segment", "f0", "f1", "frames", "step"}   # internal plan keys


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


def _matte_plan(args: argparse.Namespace, alpha_ids: list[str], duration: float, warnings: list[str],
                aroll_duration: float = 0.0) -> dict | None:
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
        covers = arr.shape[0] / float(args.alpha_fps)
        if aroll_duration > 0 and abs(covers - aroll_duration) > max(0.1, 2.0 / float(args.alpha_fps)):
            warnings.append(f"alpha matte covers {covers:.2f} s ({arr.shape[0]} frames at --alpha-fps {args.alpha_fps}) but the A-roll is "
                            f"{aroll_duration:.2f} s: wrong --alpha-fps or a matte of another cut (the matte drifts off the person)")
        return {"kind": "npy", "path": str(p.resolve()), "fps": float(args.alpha_fps), "frames": int(arr.shape[0]),
                "key": [*_file_key(p), float(args.alpha_fps)]}
    try:
        model = fsc.resolve_matte_model_path()
    except FileNotFoundError as exc:
        raise InputError(f"scenes {alpha_ids} need a person matte (modes B / S / N / pop-out / --clean-wall) but there is no "
                         f"--alpha-npy and no matte model: {exc}") from exc
    if "birefnet" in model.name:
        warnings.append(f"matte model is birefnet-portrait ({model}): ~30 s per frame on CPU; pass --alpha-npy or install u2netp")
    return {"kind": "model", "path": str(model), "key": _file_key(model)}


def transient_spans(frames, fps: float, cfg: dict | None = None) -> list[dict]:
    """Short-lived localized blobs (a stray glass sliver, a dropped speck) in a frame sequence -> [{t0, t1, peak_area}] in seconds.
    Spike test per pixel: frame i is compared with BOTH frames i +- offset_f; a blob brighter (or darker) than both by > spike_luma is
    something the neighbours do not have (steady motion changes monotonically and is no spike). A frame is a hit when its largest
    spike blob covers >= hit_area of the frame; a run of hits (gaps <= gap_f frames) is a transient when it lasts <= max_s (longer =
    motion) and its peak blob covers peak_area..max_area (bigger = a flash / cut, not localized). The span is padded by offset_f + 1
    frames (the clean references). The first / last offset_f frames cannot be tested."""
    c = {**TRANSIENT, **(cfg or {})}
    a = int(c["offset_f"])
    buf: list[np.ndarray] = []
    hits: list[tuple[int, float]] = []
    for k, f in enumerate(frames):
        g = f if f.ndim == 2 else cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        buf = [*buf[-2 * a:], cv2.GaussianBlur(g, (3, 3), 0).astype(np.int16)]
        if len(buf) < 2 * a + 1:
            continue
        prev, cur, nxt = buf[0], buf[a], buf[-1]
        spike = np.maximum(cur - np.maximum(prev, nxt), np.minimum(prev, nxt) - cur)
        mask = (spike > c["spike_luma"]).astype(np.uint8)
        n, _, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        top = float(st[1:, cv2.CC_STAT_AREA].max()) / mask.size if n > 1 else 0.0
        if top >= c["hit_area"]:
            hits.append((k - a, top))
    spans, run, pad = [], [], (a + 1) / fps
    for idx, area in [*hits, (None, 0.0)]:
        if run and (idx is None or idx - run[-1][0] > c["gap_f"] + 1):
            i0, i1, peak = run[0][0], run[-1][0], max(ar for _, ar in run)
            if (i1 - i0 + 1) / fps <= c["max_s"] and c["peak_area"] <= peak <= c["max_area"]:
                spans.append({"t0": round(max(0.0, i0 / fps - pad), 3), "t1": round(i1 / fps + pad, 3), "peak_area": round(peak, 5)})
            run = []
        if idx is not None:
            run.append((idx, area))
    return spans


def scan_broll_transients(src: str, info: dict) -> list[dict]:
    """`transient_spans` of a whole B-roll file on a 30 fps proxy whose long side is 480 px."""
    iw, ih = int(info["width"]), int(info["height"])
    k = ARTIFACT_PROBE_LONG / max(iw, ih)
    pw, ph = max(2, int(round(iw * k / 2)) * 2), max(2, int(round(ih * k / 2)) * 2)
    n = int(math.ceil(float(info["duration"]) * ARTIFACT_PROBE_FPS))
    if n < 1:
        return []
    with contextlib.closing(_ffmpeg_frames(src, 0.0, n, ARTIFACT_PROBE_FPS, f"scale={pw}:{ph}:flags=area", (pw, ph))) as it:
        return transient_spans(it, ARTIFACT_PROBE_FPS)


def _hits(spans, ss: float, dur: float) -> list:
    return [s for s in spans if s[0] < ss + dur - TOL_S and ss < s[1] - TOL_S]


def _gaps(used, length: float) -> list[tuple[float, float]]:
    t, out = 0.0, []
    for a, b in sorted(used):
        if a - t > TOL_S:
            out.append((t, a))
        t = max(t, b)
    return out + ([(t, length)] if length - t > TOL_S else [])


def _broll_candidates(need: dict, used: dict, lengths: dict, pool: list, spans: dict, allow_dirty: bool) -> list[tuple]:
    """Placements (file, ss, naive_ss) of one scene, most remaining seconds first: an explicit `broll_ss` is kept as is; otherwise
    the earliest window of each free gap that has no transient (the nearest clean window after the naive gap start), or the gap
    start itself when allow_dirty and the gap has no clean window (clean placements always first)."""
    d, out = need["dur"], []
    for key in ([need["file"]] if need.get("file") else pool):
        length, iv = lengths[key], used.get(key, ())
        rank = (-(length - sum(b - a for a, b in iv)), key)
        if need.get("ss") is not None:
            ss = need["ss"]
            if ss + d <= length + TOL_S and not _hits(iv, ss, d):
                out.append((False, rank, key, ss, ss))
            continue
        for g0, g1 in _gaps(iv, length):
            if g1 - g0 + TOL_S < d:
                continue
            sp = spans.get(key, [])
            clean = next((c for c in sorted({g0, *(b for a, b in sp if g0 < b < g1)}) if c + d <= g1 + TOL_S and not _hits(sp, c, d)), None)
            if clean is not None or allow_dirty:
                out.append((clean is None, rank, key, g0 if clean is None else clean, g0))
    return [c[2:] for c in sorted(out, key=lambda c: (c[0], c[1], c[3]))]


def plan_broll(needs: list[dict], lengths: dict, pool: list, spans: dict | None = None, max_nodes: int = BROLL_SEARCH_NODES) -> dict:
    """Assign B-roll windows to scenes (timeline order) without reusing source seconds. needs: [{id, dur, file | None, ss | None}]
    (file / ss = explicit per-scene overrides, kept); lengths: file -> seconds; pool: files for scenes without an explicit file;
    spans: file -> [(t0, t1)] transients to avoid. Greedy = the file with the most remaining seconds that fits, with backtracking
    when a later scene would not fit (first clean-only, then allowing a transient; each pass has its own max_nodes budget). When no
    reuse-free plan exists, the rest is placed greedily on the largest gap (the overlap is then reported by
    studio_recipe.check_source_reuse).
    Returns {placements: {id: {file, ss, naive_ss}}, reuse_free}."""
    spans = spans or {}
    fixed = [n for n in needs if n.get("file") and n.get("ss") is not None]
    todo = [n for n in needs if not (n.get("file") and n.get("ss") is not None)]
    used0: dict[str, tuple] = {}
    for n in fixed:
        used0 = {**used0, n["file"]: (*used0.get(n["file"], ()), (n["ss"], n["ss"] + n["dur"]))}
    base = {n["id"]: {"file": n["file"], "ss": n["ss"], "naive_ss": n["ss"]} for n in fixed}
    budget = [max_nodes]   # reset per pass: an exhausted clean pass must not starve the dirty pass

    def search(i: int, used: dict, allow_dirty: bool) -> dict | None:
        if i == len(todo):
            return {}
        for key, ss, naive in _broll_candidates(todo[i], used, lengths, pool, spans, allow_dirty):
            budget[0] -= 1
            if budget[0] < 0:
                return None
            rest = search(i + 1, {**used, key: (*used.get(key, ()), (ss, ss + todo[i]["dur"]))}, allow_dirty)
            if rest is not None:
                return {todo[i]["id"]: {"file": key, "ss": ss, "naive_ss": naive}, **rest}
        return None

    for allow_dirty in (False, True):
        budget[0] = max_nodes
        found = search(0, used0, allow_dirty)
        if found is not None:
            return {"placements": {**base, **found}, "reuse_free": True}
    placed, used = dict(base), dict(used0)
    for n in todo:
        keys = [n["file"]] if n.get("file") else pool
        key = min(keys, key=lambda k: (-(lengths[k] - sum(b - a for a, b in used.get(k, ()))), k))
        gaps = _gaps(used.get(key, ()), lengths[key]) or [(0.0, lengths[key])]
        g0 = max(gaps, key=lambda g: g[1] - g[0])[0]
        ss = n["ss"] if n.get("ss") is not None else max(0.0, min(g0, lengths[key] - n["dur"]))
        placed[n["id"]] = {"file": key, "ss": ss, "naive_ss": ss}
        used = {**used, key: (*used.get(key, ()), (ss, ss + n["dur"]))}
    return {"placements": placed, "reuse_free": False}


def _assign_broll(scenes: list[dict], broll_dir: Path | None, warnings: list[str], allow_reuse: bool = False,
                  artifact_scan: bool = True) -> dict:
    """Fill sc['broll_src'] / sc['broll_ss'] for H / A2 scenes with `plan_broll` over --broll-dir (explicit `broll` / `broll_ss` kept),
    avoiding transient artifacts (`scan_broll_transients`) unless artifact_scan is off. Source reuse
    (studio_recipe.check_source_reuse) is an InputError unless allow_reuse (then a warning).
    Returns {broll_artifacts: {scanned, files, shifted, unavoided}, broll_reuse: [findings]}."""
    report = {"broll_artifacts": {"scanned": bool(artifact_scan), "files": {}, "shifted": [], "unavoided": []}, "broll_reuse": []}
    files = sorted(p for p in broll_dir.iterdir() if p.suffix.lower() in VIDEO_EXT) if broll_dir else []
    bscenes = [sc for sc in scenes if sc["mode"] in BROLL_MODES]
    if not bscenes:
        return report
    infos: dict[str, dict] = {}
    names: dict[str, str] = {}
    pool: list[str] = []
    for p in files:
        try:
            infos[str(p.resolve())] = _probe(p, f"B-roll {p.name}")
        except InputError as exc:
            warnings.append(f"B-roll {p.name} skipped: {exc}")
            continue
        pool.append(str(p.resolve()))
        names[str(p.resolve())] = p.name
    needs = []
    for sc in bscenes:
        key = None
        if sc.get("broll"):
            p = Path(sc["broll"])
            p = p if p.is_absolute() or broll_dir is None else broll_dir / p
            key = str(p.resolve()) if p.exists() else str(p)
            if key not in infos:
                infos[key] = _probe(p, f"B-roll of scene {sc['id']}")
            names[key] = p.name
        elif not pool:
            warnings.append(f"scene {sc['id']} ({sc['mode']}): no B-roll (no --broll-dir / 'broll'): PiP on a dark jewel world")
            continue
        needs.append({"id": sc["id"], "dur": sc["t1"] - sc["t0"], "file": key,
                      "ss": float(sc["broll_ss"]) if sc.get("broll_ss") is not None else None})
    if not needs:
        return report
    lengths = {k: float(v["duration"] or 0.0) for k, v in infos.items()}
    spans: dict[str, list[tuple[float, float]]] = {}
    if artifact_scan:
        for k in sorted({*pool, *(n["file"] for n in needs if n["file"])}):
            found = scan_broll_transients(k, infos[k])
            if found:
                spans[k] = [(s["t0"], s["t1"]) for s in found]
                report["broll_artifacts"]["files"][names[k]] = found
    placed = plan_broll(needs, lengths, pool, spans)["placements"]
    by_id = {sc["id"]: sc for sc in bscenes}
    for n in needs:
        sc, pl = by_id[n["id"]], placed[n["id"]]
        key, ss, name = pl["file"], pl["ss"], names[pl["file"]]
        if ss + n["dur"] > lengths[key] + TOL_S:
            warnings.append(f"scene {sc['id']}: B-roll {name} has {lengths[key]:.2f} s < {ss + n['dur']:.2f} s needed: last frame held")
        if abs(ss - pl["naive_ss"]) > TOL_S:
            report["broll_artifacts"]["shifted"].append({"scene": sc["id"], "file": name, "from_ss": round(pl["naive_ss"], 4), "ss": round(ss, 4)})
        bad = _hits(spans.get(key, []), ss, n["dur"])
        if bad:
            report["broll_artifacts"]["unavoided"].append({"scene": sc["id"], "file": name, "ss": round(ss, 4), "spans": [list(s) for s in bad]})
            warnings.append(f"scene {sc['id']}: B-roll {name} {ss:.2f}-{ss + n['dur']:.2f} s contains a transient artifact at "
                            f"{', '.join(f'{a:.2f}-{b:.2f}' for a, b in bad)} s and no clean window fits: add footage or set broll_ss")
        sc["broll_src"], sc["broll_ss"], sc["broll_info"] = key, round(ss, 4), infos[key]
    shots = [{"id": sc["id"], "source": sc["broll_src"], "src": [sc["broll_ss"], sc["broll_ss"] + sc["t1"] - sc["t0"]]}
             for sc in bscenes if sc.get("broll_src")]
    reuse = sr.check_source_reuse(shots)
    report["broll_reuse"] = reuse
    if reuse:
        msg = "; ".join(f["message"] for f in reuse)
        msg = msg.replace(str(broll_dir.resolve()) + os.sep, "") if broll_dir else msg
        if not allow_reuse:
            raise InputError(f"B-roll source reuse: {msg}. Add footage, set per-scene broll / broll_ss, or pass --allow-broll-reuse")
        warnings.extend(f"B-roll source seconds reused (--allow-broll-reuse): {f['message']}" for f in reuse)
    return report


def _load_overlays(path: Path | None) -> tuple[list[dict], list[dict]]:
    if path is None:
        return [], []
    doc = _load_json(path, "overlays file")
    ovs, vfx = (doc, []) if isinstance(doc, list) else (doc.get("overlays", []), doc.get("screen_vfx", []))
    return _check_overlays(ovs, vfx, path.parent)


def _plate_size(src: Path, job: dict, kinetic_meta: dict, base: Path) -> tuple[int, int]:
    """(w, h) of a kt plate: the rendered `<plate>.typo_meta.json` (job meta_out relative to `base`, else next to the plate) first,
    then the plan's typo_kinetic_meta plate_width / plate_height, then the batch job width / height."""
    metas = [Path(f"{src}.typo_meta.json")]
    if job.get("meta_out"):
        m = Path(str(job["meta_out"]))
        metas.insert(0, m if m.is_absolute() else base / m)
    for cand in metas:
        try:
            m = json.loads(cand.read_text(encoding="utf-8"))
            if int(m.get("width") or 0) > 0 and int(m.get("height") or 0) > 0:
                return int(m["width"]), int(m["height"])
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    for w, h in ((kinetic_meta.get("plate_width"), kinetic_meta.get("plate_height")), (job.get("width"), job.get("height"))):
        try:
            if int(w) > 0 and int(h) > 0:
                return int(w), int(h)
        except (TypeError, ValueError):
            continue
    raise InputError(f"kt plate {src.name}: no size (no rendered .typo_meta.json, plate_width / plate_height or job width / height)")


def overlays_from_plan(plan: dict, base_dir: Path | str) -> list[dict]:
    """--overlays rows from a typography_composer.plan_dviet_kinetic_beat_schedule plan: one per craft_clips entry (else per
    batch_jobs entry): src (relative to base_dir = the plan's folder), at, dur, cx / cy = motion.position (or pos) moved from the
    motion anchor to the plate centre, orig_w / orig_h = the plate size (`_plate_size`), scale = motion.scale / 100. Pure: no
    file is written; render the plates first (src existence is checked by the CLI)."""
    if not isinstance(plan, dict):
        raise InputError("plan must be a JSON object (plan_dviet_kinetic_beat_schedule output)")
    base = Path(base_dir)
    jobs = [j for j in plan.get("batch_jobs") or [] if isinstance(j, dict)]
    by_out = {str(j["out"]): j for j in jobs if j.get("out")}
    rows = [c for c in plan.get("craft_clips") or [] if isinstance(c, dict)] or jobs
    if not rows:
        raise InputError("plan has no craft_clips / batch_jobs (expected plan_dviet_kinetic_beat_schedule output)")
    out = []
    for i, c in enumerate(rows):
        src = c.get("src") or c.get("out")
        job = by_out.get(str(src), c)
        motion = c.get("motion") or {}
        try:
            pos = motion.get("position") or c.get("pos") or job.get("pos")
            at, dur, px, py = float(c["at"]), float(c["dur"]), float(pos[0]), float(pos[1])
            scale = float(motion.get("scale", 100.0)) / 100.0
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise InputError(f"plan clip #{i} ({src}): needs src, at, dur and motion.position / pos") from exc
        if not src or dur <= 0 or scale <= 0:
            raise InputError(f"plan clip #{i} ({src}): empty src, dur <= 0 or scale <= 0")
        p = Path(str(src))
        if not p.is_absolute():
            # planner paths are relative to the cwd it ran in (out_dir="work/plates") or to the plan folder: resolve once,
            # to an absolute path, so _check_overlays never prefixes the base again (work/work/... bug in the v7.9.4 run)
            p = (p if p.is_file() else base / p).resolve()
        w, h = _plate_size(p, job, c.get("typo_kinetic_meta") or job.get("typo_kinetic_meta") or {}, base)
        ax, ay = (float(v) for v in (motion.get("anchor") or (w / 2.0, h / 2.0)))
        out.append({"src": str(p), "at": at, "dur": dur, "cx": round(px + (w / 2.0 - ax) * scale, 2),
                    "cy": round(py + (h / 2.0 - ay) * scale, 2), "orig_w": w, "orig_h": h, "scale": round(scale, 4)})
    # Same rule as spec_from_plan._trim_overlaps: a plate ends where the next one starts (no two texts stacked), so the
    # master and the .fcproj mirror show the same plates for the same spans.
    out.sort(key=lambda o: o["at"])
    for a, b in zip(out, out[1:]):
        if a["at"] + a["dur"] > b["at"] + 1e-6:
            a["dur"] = round(max(0.05, b["at"] - a["at"]), 6)
    return out


def _check_overlays(ovs: list[dict], vfx: list[dict], base: Path) -> tuple[list[dict], list[dict]]:
    """Required keys present, src resolved against `base` and existing."""
    for kind, items, keys in (("overlay", ovs, ("src", "at", "dur", "cx", "cy", "orig_w", "orig_h")), ("screen_vfx", vfx, ("src", "at", "dur"))):
        for i, it in enumerate(items):
            miss = [k for k in keys if k not in it]
            if miss:
                raise InputError(f"{kind} #{i} lacks {miss}")
            src = Path(it["src"])
            it["src"] = str(src if src.is_absolute() else (base / src))
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
    broll_report = _assign_broll(scenes, broll_dir, warnings, allow_reuse=bool(getattr(args, "allow_broll_reuse", False)),
                                 artifact_scan=not getattr(args, "no_broll_artifact_scan", False))
    popout_default = fsc.LOOK_S_POPOUT
    for sc in scenes:
        sc["popout"] = bool(sc.get("popout", popout_default)) and sc["mode"] in ("P", "A1")
        sc["renderer"] = "render_popout_studio_card" if sc["popout"] else RENDERERS[sc["mode"]]
        sc["needs_alpha"] = bool(args.clean_wall or sc["mode"] in ALPHA_MODES or sc["popout"])
    matte = _matte_plan(args, [s["id"] for s in scenes if s["needs_alpha"]], duration, warnings, float(aroll["duration"] or 0.0))
    if getattr(args, "overlays_from_plan", None):
        plan_p = Path(args.overlays_from_plan)
        overlays, vfx = _check_overlays(overlays_from_plan(_load_json(plan_p, "plan file"), plan_p.parent), [], plan_p.parent)
    else:
        overlays, vfx = _load_overlays(Path(args.overlays) if args.overlays else None)
    hook_auto, overlays = _hook_auto(scenes, overlays, args, warnings, words)
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
            "warnings": warnings, "words": len(words), "hook_auto": hook_auto, **broll_report}


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


# ============================================================================================ v7.9.2 hook auto (motion + product-safe text)
def _motion_rules() -> dict:
    full = sr._load()
    return {"hold_s": float(full["pacing"]["motion"]["bg_static_run_s"][0]), "cap": float(full["camera_punch_caps"]["fullscreen_broll"])}


def _cover_size(iw: int, ih: int) -> tuple[int, int]:
    """Cover-scaled, uncropped size of an iw x ih source for the W x H frame (its centred crop is the default framing)."""
    s = max(W / iw, H / ih)
    return max(W, int(round(iw * s))), max(H, int(round(ih * s)))


def measure_hook_source(src: str, ss: float, dur: float, detect: bool = True) -> dict:
    """Source window of a hook B-roll on the default cover crop: motion_gate mean frame diff (30 fps, 270x480 proxy) and the product
    box (`fsc.product_bbox_from_frame` on the first, middle and last frame, union, in 1080x1920 pixels)."""
    pw, ph = HOOK_PROBE_SIZE
    n = max(2, int(round(dur * HOOK_PROBE_FPS)))
    vf = f"scale={pw}:{ph}:force_original_aspect_ratio=increase:flags=area,crop={pw}:{ph}"
    with contextlib.closing(_ffmpeg_frames(src, ss, n, HOOK_PROBE_FPS, vf, (pw, ph))) as it:
        frames = [f.copy() for f in it]
    d = [v for _, v in mg.bg_diff_series(frames, fps=HOOK_PROBE_FPS, size=(pw, ph))]
    mean = round(float(np.mean(d)) if d else 0.0, 3)
    product: dict[str, Any] = {"bbox": None, "method": "none"}
    if detect:
        found = [fsc.product_bbox_from_frame(frames[k]) for k in sorted({0, len(frames) // 2, len(frames) - 1})]
        boxes = [r["bbox"] for r in found if r["bbox"] is not None]
        if boxes:
            k = W / pw
            product = {"bbox": [int(round(min(b[0] for b in boxes) * k)), int(round(min(b[1] for b in boxes) * k)),
                                int(round(max(b[2] for b in boxes) * k)), int(round(max(b[3] for b in boxes) * k))],
                       "method": next(r["method"] for r in found if r["bbox"] is not None)}
    return {"mean_diff": mean, "static": mean < mg.MIN_MEAN_DIFF, "product": product}


def hook_motion_for(sc: dict, source_mean_diff: float, product_bbox, src_size: tuple[int, int] = (W, H),
                    anchor: tuple[float, float] | None = None) -> dict | None:
    """Auto micro-move of a hook B-roll scene (`fsc.hook_push_params` + glint) or None when it needs none: not H / A2, starts after
    the hook, explicit `cam` (the editor's decision), the source already moves (diff >= motion_gate MIN_MEAN_DIFF) or the hook part
    of the hold is <= bg_static_run_s[0] (0.8 s)."""
    rules = _motion_rules()
    if (sc["mode"] not in BROLL_MODES or sc["t0"] >= HOOK_S - TOL_S or "cam" in sc or source_mean_diff >= mg.MIN_MEAN_DIFF
            or min(sc["t1"], HOOK_S) - sc["t0"] <= rules["hold_s"] + 1e-9):
        return None
    hm = fsc.hook_push_params(sc["t1"] - sc["t0"], product_bbox, src_size, W=W, H=H, cap=rules["cap"], anchor=anchor)
    return {**hm, "glint": list(HOOK_GLINT)}


def _punch_zoom(hm: dict, t_rel: float) -> float:
    """Extra zoom factor of the punches at `t_rel`: snap up to 1 + amp over snap_s, settle back to 1 over settle_s."""
    hp, amp = HOOK_PUNCH, float(hm.get("punch_amp", 0.0))
    for tk in hm.get("punches", ()):
        dt = t_rel - tk
        if 0.0 <= dt < hp["snap_s"] + hp["settle_s"]:
            return 1.0 + amp * (_ease(dt / hp["snap_s"]) if dt < hp["snap_s"] else 1.0 - _ease((dt - hp["snap_s"]) / hp["settle_s"]))
    return 1.0


def _punch_flash(hm: dict, t_rel: float) -> float:
    fl = float(hm.get("punch_flash", 0.0))
    for tk in hm.get("punches", ()):
        if fl > 0 and 0.0 <= t_rel - tk < 3 * HOOK_PUNCH["snap_s"]:
            return fl * (1.0 - (t_rel - tk) / (3 * HOOK_PUNCH["snap_s"]))
    return 0.0


def _move_at(hm: dict, t_rel: float) -> tuple[float, float]:
    """(total zoom, pan px) of the hook move at `t_rel` (push * punch, pan follows the push)."""
    e = _ease(t_rel / max(1e-6, hm["dur_s"]))
    return (1.0 + hm["zmax"] * e) * _punch_zoom(hm, t_rel), hm["pan_px"] * e


def _box_at(box, hm: dict, z: float, pan: float) -> tuple[float, float, float, float]:
    ax, ay = hm["anchor"]
    return (z * (box[0] - ax) + ax + pan, z * (box[1] - ay) + ay, z * (box[2] - ax) + ax + pan, z * (box[3] - ay) + ay)


def _hook_base(sc: dict, hm: dict, broll: np.ndarray, t_rel: float, size: tuple[int, int] = (W, H)) -> np.ndarray:
    """Hook B-roll background with the auto move at `t_rel`: product-anchored push + pan (cover: `broll` is the uncropped cover-scaled
    source; stage: `render_product_stage` anchored on the cap top, the pan moves cx so the output shift is pan_px * e at every zoom),
    glint and the punch flash (`fsc.snap_punch`, luma cap 220). `size` < W x H renders the same picture smaller (motion prediction)."""
    k = size[0] / W
    u = t_rel / max(1e-6, hm["dur_s"])
    e = _ease(u)
    if sc.get("stage"):
        z = 1.0 + hm["zmax"] * e
        base = fsc.render_product_stage(broll, s=float(sc["stage"]), cx=0.5 - hm["pan_px"] * e / (hm["stage_w"] * z), zoom=z,
                                        out_size=size)
    else:
        M = fsc.hook_push_affine(e, hm)
        M[:, 2] *= k
        base = cv2.warpAffine(broll, M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if hm.get("glint"):
        amount, g0, g1 = hm["glint"]
        base = fsc.glint_sweep(base, (u - g0) / max(1e-6, g1 - g0), amount, width_px=150.0 * k)
    zp, fl = _punch_zoom(hm, t_rel), _punch_flash(hm, t_rel)
    if zp > 1.0 or fl > 0:   # punch about the moving anchor = one zoom of (push * punch) about it, cap-safe by construction
        base = fsc.snap_punch(base, zp, anchor_xy=((hm["anchor"][0] + hm["pan_px"] * e) * k, hm["anchor"][1] * k), flash=fl)
    return base


def punch_times(sc: dict, words) -> list[float]:
    """Scene-relative zoom-step times: a target every HOOK_PUNCH every_s inside the hook part of the scene, snapped to the nearest word
    onset within word_snap_s, kept >= min_gap_s apart, after first_s and a full step before the hook / scene end. Deterministic."""
    hp, end = HOOK_PUNCH, min(sc["t1"], HOOK_S) - sc["t0"] - HOOK_PUNCH["snap_s"]
    onsets = sorted(float(w[1]) - sc["t0"] for w in (words or ()) if sc["t0"] <= float(w[1]) < sc["t0"] + end)
    out: list[float] = []
    k = 1
    while k * hp["every_s"] <= end + 1e-9:
        tgt, prev = k * hp["every_s"], out[-1] if out else -1e9
        near = [o for o in onsets if abs(o - tgt) <= hp["word_snap_s"] and o - prev >= hp["min_gap_s"] and hp["first_s"] <= o <= end]
        t = min(near, key=lambda o: (abs(o - tgt), o)) if near else tgt
        if t - prev >= hp["min_gap_s"] - 1e-9 and hp["first_s"] <= t <= end:
            out.append(round(t, 4))
        k += 1
    return out


def _overflow(box) -> float:
    return max(0.0, -box[0]) + max(0.0, box[2] - W) + max(0.0, -box[1]) + max(0.0, box[3] - H)


def with_punches(hm: dict, times: list[float], step_min: float, product_bbox=None, cap: float | None = None) -> dict:
    """`hm` plus zoom steps (snap + settle) at `times`. The slow push shrinks to (1 + cap) / (1 + amp) - 1 so the total zoom never
    passes the cap; the pan is re-planned for the new push. amp starts at HOOK_PUNCH amp and shrinks (x 0.8) until the product box
    never overflows the frame more than the plain full-cap move did (sampled every 1/60 s); below `step_min` (4 %) no punches."""
    if not times:
        return hm
    cap = float(cap if cap is not None else _motion_rules()["cap"])
    ref = max((_overflow(fsc.hook_push_box(product_bbox, e, hm)) for e in (0.0, 1.0)), default=0.0) if product_bbox else 0.0
    amp = HOOK_PUNCH["amp"]
    while amp >= step_min - 1e-9:
        zb = math.floor(((1.0 + cap) / (1.0 + amp) - 1.0) * 1e4) / 1e4      # floor: push * punch never passes the cap
        base = fsc.hook_push_params(hm["dur_s"], product_bbox, tuple(hm["src_size"]), W=W, H=H, cap=zb,
                                    anchor=tuple(hm["anchor"]) if hm.get("stage_w") else None)
        cand = {**hm, **{k: base[k] for k in ("zmax", "anchor", "pan_px")}, "punches": list(times), "punch_amp": round(amp, 4),
                "punch_flash": HOOK_PUNCH["flash"]}
        grid = [i / 60.0 for i in range(int(hm["dur_s"] * 60) + 1)]
        if not product_bbox or all(_overflow(_box_at(product_bbox, cand, *_move_at(cand, t))) <= ref + 0.5 for t in grid):
            return cand
        amp *= 0.8
    return hm


def predict_hook_motion(sc: dict, hm: dict, dur: float) -> float:
    """motion_gate mean frame diff of the planned hook background (no PiP, no text) rendered at the 270x480 probe size."""
    pw, ph = HOOK_PROBE_SIZE
    k = pw / W
    n = max(2, int(round(dur * HOOK_PROBE_FPS)))
    if sc.get("stage"):
        iw, ih = sc["broll_info"]["width"], sc["broll_info"]["height"]
        size = (max(2, int(round(iw * ph / ih))), ph)
    else:
        size = (max(pw, int(round(hm["src_size"][0] * k))), max(ph, int(round(hm["src_size"][1] * k))))

    def frames():   # hm stays in 1080x1920 px: _hook_base scales the cover affine; the stage cx does not depend on the size
        with contextlib.closing(_ffmpeg_frames(sc["broll_src"], sc["broll_ss"], n, HOOK_PROBE_FPS, f"scale={size[0]}:{size[1]}", size)) as it:
            for i, f in enumerate(it):
                yield _hook_base(sc, hm, f, i / HOOK_PROBE_FPS, (pw, ph))
    d = [v for _, v in mg.bg_diff_series(frames(), fps=HOOK_PROBE_FPS, size=(pw, ph))]
    return round(float(np.mean(d)) if d else 0.0, 3)


def _stage_layout(sc: dict) -> tuple[float, int]:
    """(stage layer width in output px at zoom 1, cap-top row) of `render_product_stage` for this scene's B-roll."""
    s, iw, ih = float(sc["stage"]), sc["broll_info"]["width"], sc["broll_info"]["height"]
    return iw * max(H * s / ih, W / iw), int(fsc.stage_geometry(s, W, H)["cap_top_y"])


def _stage_product_bbox(sc: dict, dur: float) -> dict:
    """Product box re-detected on the staged frame (`render_product_stage` of the first, middle and last source frame at the
    270x480 probe size, union, in 1080x1920 px)."""
    pw, ph = HOOK_PROBE_SIZE
    iw, ih = sc["broll_info"]["width"], sc["broll_info"]["height"]
    sw = max(2, int(round(iw * ph / ih)))
    boxes, method = [], "none"
    for t in (0.0, dur / 2.0, max(0.0, dur - 1.0 / HOOK_PROBE_FPS)):
        with contextlib.closing(_ffmpeg_frames(sc["broll_src"], sc["broll_ss"] + t, 1, HOOK_PROBE_FPS, f"scale={sw}:{ph}", (sw, ph))) as it:
            staged = fsc.render_product_stage(next(it), s=float(sc["stage"]), out_size=(pw, ph))
        r = fsc.product_bbox_from_frame(staged)
        if r["bbox"] is not None:
            boxes.append(r["bbox"])
            method = r["method"]
    k = W / pw
    bb = [int(round(v * k)) for v in _box_union(boxes)] if boxes else None
    return {"bbox": bb, "method": f"stage_{method}" if bb else "stage_geometry"}


def _box_union(boxes) -> list[int] | None:
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return [int(math.floor(min(b[0] for b in boxes))), int(math.floor(min(b[1] for b in boxes))),
            int(math.ceil(max(b[2] for b in boxes))), int(math.ceil(max(b[3] for b in boxes)))]


def _clip_box(b) -> list[int] | None:
    if b is None:
        return None
    x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(W, b[2]), min(H, b[3])
    return [x0, y0, x1, y1] if x1 > x0 and y1 > y0 else None


def _swept_product_box(sc: dict, bbox, hm: dict | None) -> list[int] | None:
    """Product box in the output over the whole scene (camera move included; both ends bound it)."""
    if sc.get("stage") and bbox is None:
        x0, y0, x1, y1 = fsc.stage_geometry(float(sc["stage"]), W, H)["product_bbox"]
        z = 1.0 + hm["zmax"] if hm else max(float(v) for v in sc.get("cam", (1.0, 1.06)))
        return _clip_box(_box_union([(W / 2 - z * (W / 2 - x0), y0, W / 2 + z * (x1 - W / 2), H)]))
    if bbox is None:
        return None
    if hm and hm.get("punches"):   # punch zoom is not linear in the push: sweep the move every 1/60 s
        return _clip_box(_box_union([_box_at(bbox, hm, *_move_at(hm, i / 60.0)) for i in range(int(hm["dur_s"] * 60) + 1)]))
    if hm:   # the stage zoom about (W / 2, cap top) + cx pan is the same affine as hook_push_box with that anchor
        return _clip_box(_box_union([fsc.hook_push_box(bbox, e, hm) for e in (0.0, 1.0)]))
    ax, ay = (W / 2, _stage_layout(sc)[1]) if sc.get("stage") else (W / 2, H / 2)
    zs = [float(v) for v in sc.get("cam", (1.0, 1.06))]
    return _clip_box(_box_union([[z * (bbox[0] - ax) + ax, z * (bbox[1] - ay) + ay, z * (bbox[2] - ax) + ax,
                                  z * (bbox[3] - ay) + ay] for z in zs]))


def _overlap(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _overlay_box(ov: dict, ink) -> tuple[float, float, float, float]:
    """Frame box (1080x1920) of the ink box `ink` (plate px, x1 / y1 exclusive) of a kt overlay placed at cx / cy / scale."""
    s = float(ov.get("scale", 1.0))
    left, top = float(ov["cx"]) - int(ov["orig_w"]) * s / 2.0, float(ov["cy"]) - int(ov["orig_h"]) * s / 2.0
    return (round(left + ink[0] * s, 2), round(top + ink[1] * s, 2), round(left + ink[2] * s, 2), round(top + ink[3] * s, 2))


def _overlay_ink_box(ov: dict) -> tuple[int, int, int, int]:
    """Union of the opaque pixels of a kt `.mov` plate over its frames (10 fps), in plate px; the whole plate when unreadable."""
    w, h = int(ov["orig_w"]), int(ov["orig_h"])
    cmd = ["ffmpeg", "-v", "error", "-i", str(ov["src"]), "-vf", f"fps=10,scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    try:
        pr = subprocess.run(cmd, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 0, 0, w, h
    n = len(pr.stdout) // (w * h * 4)
    if pr.returncode != 0 or n == 0:
        return 0, 0, w, h
    m = (np.frombuffer(pr.stdout[:n * w * h * 4], np.uint8).reshape(n, h, w, 4)[..., 3] > INK_ALPHA_MIN).any(axis=0)
    ys, xs = np.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if xs.size else (0, 0, w, h)


def _clear_shift(box, obstacles) -> tuple[float, float] | None:
    """(dx, dy) moving `box` to the nearest y with no obstacle overlap inside SAFE_ZONE (x only clamped into it); None if none."""
    sx0, sy0, sx1, sy1 = SAFE_ZONE
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw > sx1 - sx0 or bh > sy1 - sy0:
        return None
    dx = max(sx0 - box[0], 0.0) + min(sx1 - box[2], 0.0)
    lo, hi = sy0, sy1 - bh
    cands = {box[1], lo, hi} | {o[3] for o in obstacles} | {o[1] - bh for o in obstacles}
    ok = [y for y in cands if lo <= y <= hi
          and not any(_overlap((box[0] + dx, y, box[2] + dx, y + bh), o) for o in obstacles)]
    if not ok:
        return None
    y = min(ok, key=lambda v: (abs(v - box[1]), v))
    return dx, y - box[1]


def place_product_safe(overlays: list[dict], hooks: list[dict], ink_boxes: list | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Move every overlay whose window intersects a hook scene and whose ink box overlaps that scene's `product_bbox` to the nearest
    clear band (no overlap with any of the scene's `obstacles`: product + PiP), inside SAFE_ZONE; the size is never changed (text
    stays >= 64 px). `hooks`: [{id, t0, t1, product_bbox, obstacles}]. Returns (new overlay list, moved, unresolved); the input is not
    mutated and an overlay that cannot be cleared stays where it is (reported)."""
    new, moved, unresolved = [], [], []
    for i, ov in enumerate(overlays):
        a, b = float(ov["at"]), float(ov["at"]) + float(ov["dur"])
        hit = [hk for hk in hooks if hk.get("product_bbox") and min(b, hk["t1"]) - max(a, hk["t0"]) > TOL_S]
        ink = (ink_boxes[i] if ink_boxes is not None else None) or (_overlay_ink_box(ov) if hit else None)
        box = _overlay_box(ov, ink) if hit else None
        if not hit or not any(_overlap(box, hk["product_bbox"]) for hk in hit):
            new.append(ov)
            continue
        ids, name = [hk["id"] for hk in hit], Path(str(ov["src"])).name
        shift = _clear_shift(box, [o for hk in hit for o in hk["obstacles"] if o])
        if shift is None:
            unresolved.append({"index": i, "src": name, "at": a, "scenes": ids, "box": list(box),
                               "overlap_px2": int(sum(_overlap(box, hk["product_bbox"]) for hk in hit))})
            new.append(ov)
            continue
        nov = {**ov, "cx": round(float(ov["cx"]) + shift[0], 2), "cy": round(float(ov["cy"]) + shift[1], 2)}
        moved.append({"index": i, "src": name, "at": a, "scenes": ids, "from_cy": float(ov["cy"]), "to_cy": nov["cy"],
                      "from_cx": float(ov["cx"]), "to_cx": nov["cx"], "box_before": list(box), "box_after": list(_overlay_box(nov, ink))})
        new.append(nov)
    return new, moved, unresolved


def _hook_auto(scenes: list[dict], overlays: list[dict], args: argparse.Namespace, warnings: list[str],
               words=None) -> tuple[dict, list[dict]]:
    """Measure every hook B-roll scene, set its `hook_motion` (part of the segment cache key) and move hook overlays off the product."""
    no_motion, no_text = bool(getattr(args, "no_hook_motion", False)), bool(getattr(args, "no_product_safe_text", False))
    no_stage = bool(getattr(args, "no_stage_fallback", False))
    info: dict[str, Any] = {"motion": not no_motion, "product_safe_text": not no_text, "stage_fallback": not no_stage, "scenes": [],
                            "product_bbox": None, "moved_overlays": [], "unresolved_overlays": [], "stage_fallback_scenes": [],
                            "below_floor_scenes": []}
    if no_motion and no_text:
        return info, overlays

    def analyse(sc: dict) -> tuple[dict, dict]:
        dur = sc["t1"] - sc["t0"]
        probe = measure_hook_source(sc["broll_src"], sc["broll_ss"], min(dur, HOOK_S - sc["t0"]), detect=not sc.get("stage"))
        if sc.get("stage"):
            probe["product"] = _stage_product_bbox(sc, min(dur, HOOK_S - sc["t0"]))
            stage_w, cap_y = _stage_layout(sc)
            size, anchor = (int(round(stage_w)), H), (W / 2.0, float(cap_y))
        else:
            size, anchor = _cover_size(sc["broll_info"]["width"], sc["broll_info"]["height"]), None
        bbox = probe["product"]["bbox"]
        sc.pop("hook_motion", None)
        hm = None if no_motion else hook_motion_for(sc, probe["mean_diff"], bbox, size, anchor=anchor)
        pred, below = None, False
        if hm:
            hm = {**hm, "stage_w": round(size[0], 2)} if sc.get("stage") else hm
            hook_dur = min(dur, HOOK_S - sc["t0"])
            pred = [predict_hook_motion(sc, hm, hook_dur)]
            if pred[0] < mg.MIN_MEAN_DIFF:   # under the floor: zoom steps (bg resets) on word onsets
                hm = with_punches(hm, punch_times(sc, words), float(sr._load()["pacing"]["motion"]["bg_zoom_step_min"]), bbox)
                if hm.get("punches"):
                    pred.append(predict_hook_motion(sc, hm, hook_dur))
            below = pred[-1] < mg.MIN_MEAN_DIFF
            sc["hook_motion"] = hm
        prod = _swept_product_box(sc, bbox, hm)
        hook = {"id": sc["id"], "t0": sc["t0"], "t1": sc["t1"], "product_bbox": prod,
                "obstacles": [prod, PIP_RECTS.get(sc.get("pip", "br"), PIP_RECTS["br"])]}
        row = {"id": sc["id"], "t0": sc["t0"], "t1": sc["t1"], "source_mean_diff": probe["mean_diff"], "static": probe["static"],
               "stage": sc.get("stage"), "product_method": probe["product"]["method"], "product_bbox_source": bbox, "product_bbox": prod,
               "motion": hm and {**hm, "push_pct_s": round(100 * hm["zmax"] / dur, 2), "pan_pct_s": round(100 * abs(hm["pan_px"]) / (W * dur), 2),
                                 "predicted_mean_diff": pred},
               "motion_below_floor": below,
               "motion_skipped": None if hm else ("--no-hook-motion" if no_motion else "explicit cam" if "cam" in sc else
                                                  "source moves" if not probe["static"] else "hold <= bg_static_run_s")}
        return hook, row

    hook_scenes = [sc for sc in scenes if sc["mode"] in BROLL_MODES and sc["t0"] < HOOK_S - TOL_S and sc.get("broll_src")]
    hooks, rows = (list(x) for x in zip(*(analyse(sc) for sc in hook_scenes))) if hook_scenes else ([], [])
    if not no_text and overlays:
        src_overlays = overlays
        overlays, moved, unresolved = place_product_safe(src_overlays, hooks)
        stuck = {sid for u in unresolved for sid in u["scenes"]}
        if stuck and not no_stage:   # v7.9.2: no clear band -> the product stage (v4 D1 fix) frees the band above the cap
            for k, sc in enumerate(hook_scenes):
                if sc["id"] in stuck and not sc.get("stage"):
                    sc["stage"] = fsc.STAGE_S_DEFAULT
                    hooks[k], rows[k] = analyse(sc)
                    info["stage_fallback_scenes"].append(sc["id"])
            overlays, moved, unresolved = place_product_safe(src_overlays, hooks)
        info["moved_overlays"], info["unresolved_overlays"] = moved, unresolved
        for u in unresolved:
            staged = all(next(sc for sc in hook_scenes if sc["id"] == sid).get("stage") for sid in u["scenes"])
            warnings.append(f"overlay {u['src']} at {u['at']:.2f} s overlaps the product of {u['scenes']} and no clear band fits it in the "
                            "safe zone" + (" even on the product stage: use another B-roll" if staged else
                                           ": set `stage: 0.72` on the scene (render_product_stage frees the band above the cap), drop "
                                           "--no-stage-fallback, or use another B-roll"))
    info["scenes"] = rows
    info["below_floor_scenes"] = [r["id"] for r in rows if r["motion_below_floor"]]
    for r in rows:   # after the stage fallback re-analysis: one warning per scene, on its final move
        if r["motion_below_floor"]:
            warnings.append(f"scene {r['id']}: hook B-roll motion is still {r['motion']['predicted_mean_diff'][-1]:.2f} < "
                            f"{mg.MIN_MEAN_DIFF} (motion_gate floor) after the auto push"
                            f"{' + zoom steps' if r['motion'].get('punches') else ''}: use a moving B-roll or set `stage` / `cam`")
    info["product_bbox"] = _box_union([hk["product_bbox"] for hk in hooks])
    return info, overlays


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
                                               photo_scale=float(sc.get("photo_scale", 1.36)) * _cam(sc, u, *CAM_DEFAULTS["popout"]))
        return out
    if mode in BROLL_MODES:
        hm = sc.get("hook_motion")
        if broll is None:
            base = ctx["bg"]
        elif hm:
            base = _hook_base(sc, hm, broll, t - sc["t0"])
        elif sc.get("stage"):
            base = fsc.render_product_stage(broll, s=float(sc["stage"]), zoom=_cam(sc, u, *CAM_DEFAULTS[mode]))
        else:
            base = _push(broll, _cam(sc, u, *CAM_DEFAULTS[mode]))
        out, _ = fsc.render_squircle_pip_window(base, aroll, pip_rect=PIP_RECTS.get(sc.get("pip", "br"), PIP_RECTS["br"]),
                                                rx=44, rim_rgb=jewel, inner_zoom=1.02 + 0.04 * _ease(u))
        return out
    if mode == "A1":
        out, _ = fsc.render_full_head_studio_card(ctx["bg"], aroll, card_rect=DARK_CARD, cam_scale=_cam(sc, u, *CAM_DEFAULTS["A1"]),
                                                  mode="dark",
                                                  border_rgb=jewel, backlight_halo_bgr=tuple(float(c) for c in jewel[::-1]),
                                                  backlight_strength=0.35)
        return out
    if mode == "P":
        out, _ = fsc.render_full_head_studio_card(ctx["bg"], aroll, card_rect=LIGHT_CARD, cam_scale=_cam(sc, u, *CAM_DEFAULTS["P"]),
                                                  mode="light")
        return out
    if mode in ("B", "S"):
        out, _ = fsc.render_bottom_flush_cutout(ctx["bg"], aroll, alpha, cam_scale=_cam(sc, u, *CAM_DEFAULTS[mode]), rim_rgb=jewel)
        return out
    z, piv = _cam(sc, u, *CAM_DEFAULTS["N"]), (W * 0.5, 1365.0)
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
            elif sc.get("hook_motion"):
                sw, sh = sc["hook_motion"]["src_size"]
                br_it = _ffmpeg_frames(sc["broll_src"], sc["broll_ss"], n, gear.fps, f"scale={sw}:{sh}:flags=lanczos", (sw, sh))
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
            "overlays": len(plan["overlays"]), "screen_vfx": len(plan["screen_vfx"]), "words": plan["words"], "warnings": plan["warnings"],
            "hook_auto": plan["hook_auto"], "product_bbox": plan["hook_auto"]["product_bbox"],
            "broll_artifacts": plan["broll_artifacts"], "broll_reuse": plan["broll_reuse"]}


def emitted_scene(s: dict) -> dict:
    """One resolved scene for --emit-scenes (the .fcproj mirror): the input keys + start / end, the chosen broll (absolute) /
    broll_ss, the final stage, the effective cam [from, to] (hook auto: [1, 1 + zmax], the move itself in hook_motion)."""
    row = {k: v for k, v in s.items() if k not in EMIT_DROP}
    row.update(start=s["t0"], end=s["t1"])
    if s.get("broll_src"):
        row.update(broll=s["broll_src"], broll_ss=s["broll_ss"])
    hm = s.get("hook_motion")
    cam = s.get("cam") or ((1.0, round(1.0 + float(hm["zmax"]), 4)) if hm else CAM_DEFAULTS["popout" if s.get("popout") else s["mode"]])
    row["cam"] = [float(v) for v in cam]
    return row


def _emit(plan: dict, args: argparse.Namespace) -> dict:
    """--emit-overlays (final placed overlays, --overlays format) / --emit-scenes (resolved scenes, scenes.json format)."""
    done = {}
    for flag, doc in (("emit_overlays", lambda: {"overlays": plan["overlays"], "screen_vfx": plan["screen_vfx"]}),
                      ("emit_scenes", lambda: {"look": "S", "duration": plan["duration"],
                                               "scenes": [emitted_scene(s) for s in plan["scenes"]]})):
        dst = getattr(args, flag, None)
        if dst:
            p = Path(dst)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            done[flag.split("_", 1)[1]] = str(p)
    return done


def run(args: argparse.Namespace) -> dict:
    plan = build_plan(args)
    out = _summary(plan)
    emitted = _emit(plan, args)
    if emitted:
        out["emitted"] = emitted
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
    ap.add_argument("--broll-dir", help="B-roll clips for H / A2 scenes (v7.9.3: the file with the most remaining seconds that fits, "
                                        "source seconds never reused: a reuse is exit 2 unless --allow-broll-reuse)")
    ap.add_argument("--alpha-npy", help="person matte, uint8 N x h x w (e.g. the RVM cache); else the matte model is used")
    ap.add_argument("--alpha-fps", type=float, default=30.0, help="frame rate of --alpha-npy (default 30)")
    ap.add_argument("--audio", help="voice / mix track for the master (default: the A-roll audio)")
    ov = ap.add_mutually_exclusive_group()
    ov.add_argument("--overlays", help="JSON list of kt .mov plates {src, at, dur, cx, cy, orig_w, orig_h, scale?} or "
                                       "{'overlays': [...], 'screen_vfx': [{src, at, dur, opacity?}]}")
    ov.add_argument("--overlays-from-plan", help="v7.9.4: plan.json of typography_composer.plan_dviet_kinetic_beat_schedule (plates "
                                                 "rendered): craft_clips / batch_jobs -> overlays (overlays_from_plan); instead of "
                                                 "--overlays")
    ap.add_argument("--emit-overlays", help="v7.9.4: write the final placed overlays (after the product-safe moves) to this JSON "
                                            "(--overlays format) for the .fcproj mirror")
    ap.add_argument("--emit-scenes", help="v7.9.4: write the resolved scenes (broll absolute, broll_ss, stage, cam, hook_motion) to "
                                          "this JSON (scenes.json format) for spec_from_plan / the .fcproj mirror; re-render from the "
                                          "original scenes.json (an explicit cam switches hook auto off)")
    ap.add_argument("--clean-wall", action="store_true", help="run the alpha-guarded wall cleaner (its ROIs are measured on the "
                                                              "reference studio wall; off by default)")
    ap.add_argument("--wall-ref-t", type=float, default=0.0, help="low-head reference frame time for --clean-wall (s)")
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1), help="parallel segment renders (default min(4, CPUs))")
    ap.add_argument("--no-voice-guard", action="store_true", help="report a voice guard rejection as a warning instead of exit 3")
    ap.add_argument("--dry-run", action="store_true", help="validate every input and print the per-scene plan; render nothing")
    ap.add_argument("--no-hook-motion", action="store_true", help="v7.9.2: no automatic push + pan + glint on a static H / A2 B-roll "
                                                                  "inside 0-3.4 s (on by default: masked frame diff floor 2.0, +25 %% cap)")
    ap.add_argument("--no-product-safe-text", action="store_true", help="v7.9.2: keep hook overlays where they are even when they "
                                                                        "overlap the detected product box (on by default)")
    ap.add_argument("--no-stage-fallback", action="store_true", help="v7.9.2: when no clear band fits a hook overlay, do not switch "
                                                                     "that hook scene to the product stage (s 0.72, cap at y 613)")
    ap.add_argument("--allow-broll-reuse", action="store_true", help="v7.9.3: report B-roll source seconds shown twice as a warning "
                                                                       "instead of exit 2")
    ap.add_argument("--no-broll-artifact-scan", action="store_true", help="v7.9.3: do not scan B-roll for short-lived bright / dark "
                                                                           "blobs (stray slivers) and do not shift broll_ss past them")
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
