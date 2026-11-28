#!/usr/bin/env python3
"""
v8_to_craft_spec.py (v8.1.0) — Convert a `v8_edit_plan.json` into a strictly compliant
FilmCraft `.craft.json` spec enforcing all 7 rules of `references/21_craft_json_minimal_spec.md`.

CLI:
    v8_to_craft_spec.py --plan <v8_edit_plan.json> --out <project.craft.json>
                        [--work <dir>] [--width 1080] [--height 1920] [--fps 60]

Track layout:
  - V1 · A-roll          (video, "audio": false whenever VOICE exists, at: 0.0, in: 0.0, dur: vdur)
  - V2 · Behind Subject  (video, overlays with layer == "behind_subject", non-overlapping lanes)
  - V3 · B-Roll          (video, broll_inserts[], "audio": false, non-overlapping lanes)
  - V4 · 3D & Widgets    (video, overlays with layer == "front" — auto-packed into V4a, V4b, ...
                          so ZERO same-track overlaps ever occur)
  - V5 · Captions        (video, overlays with layer == "caption", non-overlapping lanes)
  - A1 · Giọng (VOICE)   (audio, 48kHz stereo PCM .wav extracted if source is video/container)
  - A2 · Nhạc nền (BGM)  (audio, if `bgm` provided; extracted to .wav if container has video)
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path
from typing import Any

VERSION = "8.1.0"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MEDIA_EXT = VIDEO_EXT | AUDIO_EXT

VOICE_TRACK = unicodedata.normalize("NFC", "A1 · Giọng (VOICE)")
BGM_TRACK = unicodedata.normalize("NFC", "A2 · Nhạc nền (BGM)")

# Strict allowlists matching scripts/vendor/ovs_core/scripts/apps/craft-handoff/tools/fc_build.py
TOP_KEYS = {
    "name", "width", "height", "fps", "sample_rate", "duration",
    "tracks", "captions", "markers", "notes", "unsupported", "meta",
}
TRACK_KEYS = {"type", "name", "clips"}
VISUAL_KEYS = {
    "at", "dur", "name", "motion", "opacity", "blend", "effects",
    "preset", "transition_in", "transition_out",
}
MEDIA_KEYS = VISUAL_KEYS | {"src", "in", "speed", "gain_db", "audio", "audio_track"}
TEXT_KEYS = VISUAL_KEYS | {
    "text", "font", "style", "size", "color", "align", "position",
    "stroke", "shadow", "tracking", "leading",
}
AUDIO_KEYS = {
    "src", "at", "in", "dur", "name", "speed", "gain_db", "effects",
    "preset", "transition_in", "transition_out",
}
MOTION_KEYS = {"scale", "position", "rotation", "anchor", "scale_width"}

# Approximate normalized anchor targets for static FilmCraft placement when anchor != "none"
ANCHOR_NORM: dict[str, tuple[float, float]] = {
    "behind_head": (0.50, 0.35),
    "above_head": (0.50, 0.16),
    "left_shoulder": (0.26, 0.54),
    "right_shoulder": (0.74, 0.54),
    "follow_speaker": (0.50, 0.42),
}


class V8SpecError(ValueError):
    """Raised when a v8_edit_plan.json cannot be converted into a valid .craft.json spec."""


def _fps_fraction(fps: float) -> Fraction:
    for base in (24, 30, 48, 60, 120):
        if abs(fps - base * 1000 / 1001) < 0.005:
            return Fraction(base * 1000, 1001)
    return Fraction(fps).limit_denominator(1000)


def _to_frames(seconds: float, rate: Fraction) -> int:
    return math.floor(seconds * float(rate) + 0.5 + 1e-9)


def _snap_sec(seconds: float, rate: Fraction) -> float:
    return round(float(_to_frames(seconds, rate)) / float(rate), 6)


def _probe_media(path: Path) -> dict[str, Any]:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if r.returncode != 0:
        raise V8SpecError(f"ffprobe failed on {path}: {r.stderr.strip()[-240:]}")
    doc = json.loads(r.stdout or "{}")
    streams = doc.get("streams") or []
    types = {s.get("codec_type") for s in streams}

    cands: list[float] = []
    fmt_dur = (doc.get("format") or {}).get("duration")
    if fmt_dur is not None:
        try:
            fd = float(fmt_dur)
            if math.isfinite(fd) and fd > 0:
                cands.append(fd)
        except ValueError:
            pass
    for st in streams:
        if st.get("codec_type") in ("video", "audio") and st.get("duration") is not None:
            try:
                sd = float(st["duration"])
                if math.isfinite(sd) and sd > 0:
                    cands.append(sd)
            except ValueError:
                pass
    dur = min(cands) if cands else 0.0
    return {
        "dur": dur,
        "has_audio": "audio" in types,
        "has_video": "video" in types,
    }


def _extract_pcm_wav(src: Path, out_wav: Path) -> Path:
    """Extract audio stream to 48kHz stereo 16-bit PCM .wav (Rule #4: audio track never takes .mp4)."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=1800,
    )
    if r.returncode != 0 or not out_wav.is_file():
        raise V8SpecError(f"ffmpeg failed extracting 48kHz stereo PCM wav from {src}: {r.stderr.strip()[-240:]}")
    return out_wav.resolve()


def _resolve_path(raw: str | Path, plan_dir: Path | None) -> Path | None:
    p = Path(str(raw)).expanduser()
    cands = [p] if p.is_absolute() else ([plan_dir / p, p] if plan_dir else [p])
    for c in cands:
        if c.is_file():
            return c.resolve()
    return None


def _pack_non_overlapping_lanes(
    clips: list[dict[str, Any]],
    rate: Fraction,
) -> list[list[dict[str, Any]]]:
    """
    Greedy interval-graph lane packing in exact frame units.
    Guarantees ZERO same-track overlaps (Rule #6) even after FilmCraft tick rounding.
    """
    if not clips:
        return []
    ordered = sorted(clips, key=lambda c: (float(c["at"]), float(c["dur"]), str(c.get("name", ""))))
    lanes: list[list[dict[str, Any]]] = []
    lane_end_frames: list[int] = []

    for clip in ordered:
        start_f = _to_frames(float(clip["at"]), rate)
        dur_f = max(1, _to_frames(float(clip["dur"]), rate))
        end_f = start_f + dur_f

        placed = False
        for idx, prev_end_f in enumerate(lane_end_frames):
            if prev_end_f <= start_f:
                lanes[idx].append(clip)
                lane_end_frames[idx] = end_f
                placed = True
                break
        if not placed:
            lanes.append([clip])
            lane_end_frames.append(end_f)
    return lanes


def _lane_suffix(idx: int) -> str:
    """0 -> 'a', 1 -> 'b', ..., 25 -> 'z', 26 -> 'aa'."""
    out = ""
    n = idx
    while True:
        out = chr(ord("a") + (n % 26)) + out
        n = n // 26 - 1
        if n < 0:
            break
    return out


def _build_overlay_clip(
    ov: dict[str, Any],
    idx: int,
    *,
    plan_dir: Path | None,
    vdur: float,
    width: int,
    height: int,
    rate: Fraction,
    warnings: list[str],
    label_prefix: str,
) -> dict[str, Any] | None:
    raw_src = ov.get("src")
    if not raw_src:
        warnings.append(f"{label_prefix}[{idx}]: missing 'src', skipped")
        return None
    src_path = _resolve_path(raw_src, plan_dir)
    if src_path is None:
        warnings.append(f"{label_prefix}[{idx}]: file not found ({raw_src}), skipped")
        return None

    t0 = max(0.0, float(ov.get("start", ov.get("at", 0.0))))
    if t0 >= vdur - 1e-3:
        warnings.append(f"{label_prefix}[{idx}]: starts at {t0:.3f}s >= duration {vdur:.3f}s, skipped")
        return None

    if "end" in ov and ov["end"] is not None:
        raw_dur = float(ov["end"]) - t0
    else:
        raw_dur = float(ov.get("dur", 2.0))
    if raw_dur <= 0.0:
        warnings.append(f"{label_prefix}[{idx}]: non-positive duration ({raw_dur:.3f}s), skipped")
        return None

    in_sec = max(0.0, float(ov.get("in", ov.get("broll_ss", 0.0))))
    dur = min(raw_dur, vdur - t0)

    is_media = src_path.suffix.lower() in MEDIA_EXT
    has_audio = False
    if is_media:
        minfo = _probe_media(src_path)
        has_audio = bool(minfo["has_audio"])
        fdur = float(minfo["dur"])
        if fdur > 0.0:
            if in_sec >= fdur - 1.0 / float(rate):
                in_sec = 0.0
            avail = max(0.0, fdur - in_sec)
            if dur > avail:
                dur = avail
                warnings.append(
                    f"{label_prefix}[{idx}] ({src_path.name}): clamped dur to file length ({dur:.3f}s)"
                )

    at_snap = _snap_sec(t0, rate)
    dur_snap = _snap_sec(dur, rate)
    if dur_snap <= 0.0:
        dur_snap = round(1.0 / float(rate), 6)
    if at_snap + dur_snap > vdur + 1e-6:
        dur_snap = round(max(1.0 / float(rate), vdur - at_snap), 6)

    clip: dict[str, Any] = {
        "name": str(ov.get("name") or f"{label_prefix} · {src_path.stem}"),
        "src": str(src_path),
        "at": at_snap,
        "dur": dur_snap,
    }
    if is_media:
        clip["in"] = round(in_sec, 6)
        if has_audio:
            clip["audio"] = False

    # Map static/anchor position and scale cleanly to FilmCraft `motion`
    motion: dict[str, Any] = {}
    anchor = str(ov.get("anchor", "none") or "none")
    off_x = float(ov.get("offset_x", 0.0) or 0.0)
    off_y = float(ov.get("offset_y", 0.0) or 0.0)
    has_xy = ov.get("x") is not None or ov.get("y") is not None
    if has_xy:
        px = float(ov["x"]) if ov.get("x") is not None else (width * 0.5 + off_x)
        py = float(ov["y"]) if ov.get("y") is not None else (height * 0.5 + off_y)
        motion["position"] = [round(px, 2), round(py, 2)]
    elif anchor != "none" and anchor in ANCHOR_NORM:
        nx, ny = ANCHOR_NORM[anchor]
        px = max(0.0, min(float(width), nx * width + off_x))
        py = max(0.0, min(float(height), ny * height + off_y))
        motion["position"] = [round(px, 2), round(py, 2)]
    elif abs(off_x) > 1e-3 or abs(off_y) > 1e-3:
        motion["position"] = [round(width * 0.5 + off_x, 2), round(height * 0.5 + off_y, 2)]

    scale = ov.get("scale")
    if scale is not None:
        sc = float(scale)
        if abs(sc - 1.0) > 1e-3:
            motion["scale"] = round(sc * 100.0 if sc <= 10.0 else sc, 2)

    if motion:
        clip["motion"] = motion

    opacity = ov.get("opacity")
    if opacity is not None:
        op = float(opacity)
        op_pct = op * 100.0 if op <= 1.0 else op
        op_pct = max(0.0, min(100.0, op_pct))
        if op_pct < 99.9:
            clip["opacity"] = round(op_pct, 2)

    return clip


def _sanitize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Rule #7: Strip every unknown key outside `meta` using fc_build.py's strict allowlist."""
    clean: dict[str, Any] = {k: v for k, v in spec.items() if k in TOP_KEYS}
    clean_tracks: list[dict[str, Any]] = []
    for tr in clean.get("tracks", []):
        if not isinstance(tr, dict):
            continue
        ttype = tr.get("type")
        allowed = {"video": MEDIA_KEYS, "text": TEXT_KEYS, "audio": AUDIO_KEYS}.get(ttype)
        if allowed is None:
            continue
        ctr = {k: tr[k] for k in TRACK_KEYS if k in tr}
        clean_clips: list[dict[str, Any]] = []
        for cl in ctr.get("clips", []):
            if not isinstance(cl, dict):
                continue
            ccl = {k: v for k, v in cl.items() if k in allowed}
            if "motion" in ccl and isinstance(ccl["motion"], dict):
                ccl["motion"] = {mk: mv for mk, mv in ccl["motion"].items() if mk in MOTION_KEYS}
                if not ccl["motion"]:
                    del ccl["motion"]
            clean_clips.append(ccl)
        ctr["clips"] = clean_clips
        clean_tracks.append(ctr)
    clean["tracks"] = clean_tracks
    return clean


def build_spec_from_v8_plan(
    plan: dict[str, Any],
    out_path: Path,
    *,
    work_dir: Path | None = None,
    plan_dir: Path | None = None,
    width: int = 1080,
    height: int = 1920,
    fps: float = 60.0,
    name: str | None = None,
    write: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """
    Build (and optionally write) a strictly compliant FilmCraft `.craft.json` from a `v8_edit_plan.json`.
    Returns `(spec, warnings)`.
    """
    if not isinstance(plan, dict):
        raise V8SpecError("v8_edit_plan must be a JSON object")

    warnings: list[str] = []
    out_path = Path(out_path).resolve()
    work = Path(work_dir).resolve() if work_dir else (out_path.parent / ".v8_craft_work").resolve()
    rate = _fps_fraction(fps)

    raw_aroll = plan.get("aroll")
    if not raw_aroll:
        raise V8SpecError("plan is missing required 'aroll' path")
    aroll_path = _resolve_path(raw_aroll, plan_dir)
    if aroll_path is None:
        raise V8SpecError(f"A-roll file not found: {raw_aroll}")

    ainfo = _probe_media(aroll_path)
    aroll_dur = float(ainfo["dur"])
    if aroll_dur <= 0.0:
        raise V8SpecError(f"A-roll has zero duration: {aroll_path}")

    req_dur = float(plan.get("duration") or aroll_dur)
    vdur = round(min(req_dur, aroll_dur), 3)

    # Rule #4: Audio track NEVER takes .mp4 — resolve or extract 48kHz stereo PCM .wav
    voice_wav: Path | None = None
    raw_audio_src = plan.get("audio_mix") or plan.get("audio") or str(aroll_path)
    audio_src_path = _resolve_path(raw_audio_src, plan_dir)
    if audio_src_path is None:
        warnings.append(f"audio source not found ({raw_audio_src}); falling back to A-roll audio")
        audio_src_path = aroll_path

    audio_info = _probe_media(audio_src_path)
    if audio_info["has_audio"]:
        is_pure_audio = (audio_src_path.suffix.lower() in AUDIO_EXT) and (not audio_info["has_video"])
        if is_pure_audio:
            voice_wav = audio_src_path.resolve()
        else:
            stem = out_path.name.replace(".craft.json", "")
            voice_wav = _extract_pcm_wav(audio_src_path, work / f"{stem}_voice.wav")
    else:
        warnings.append(f"no audio stream found in {audio_src_path}; A1 VOICE track omitted")

    voice_dur = vdur
    if voice_wav is not None:
        vinfo = _probe_media(voice_wav)
        if vinfo["dur"] > 0.0:
            voice_dur = round(min(vdur, float(vinfo["dur"])), 3)

    tracks: list[dict[str, Any]] = []

    # V1 · A-roll (Rule #1: "audio": false whenever VOICE track exists)
    v1_clip: dict[str, Any] = {
        "name": f"A-roll · {aroll_path.stem}",
        "src": str(aroll_path),
        "in": 0.0,
        "at": 0.0,
        "dur": vdur,
        "audio": False,
    }
    tracks.append({"type": "video", "name": "V1 · A-roll", "clips": [v1_clip]})

    # Partition overlays by layer
    overlays = list(plan.get("overlays") or [])
    behind_clips: list[dict[str, Any]] = []
    front_clips: list[dict[str, Any]] = []
    caption_clips: list[dict[str, Any]] = []

    for i, ov in enumerate(overlays):
        if not isinstance(ov, dict):
            continue
        layer = str(ov.get("layer", "front") or "front").strip().lower()
        if layer == "behind_subject":
            c = _build_overlay_clip(
                ov, i, plan_dir=plan_dir, vdur=vdur, width=width, height=height,
                rate=rate, warnings=warnings, label_prefix="Behind",
            )
            if c is not None:
                behind_clips.append(c)
        elif layer == "caption":
            c = _build_overlay_clip(
                ov, i, plan_dir=plan_dir, vdur=vdur, width=width, height=height,
                rate=rate, warnings=warnings, label_prefix="Caption",
            )
            if c is not None:
                caption_clips.append(c)
        else:
            c = _build_overlay_clip(
                ov, i, plan_dir=plan_dir, vdur=vdur, width=width, height=height,
                rate=rate, warnings=warnings, label_prefix="Widget",
            )
            if c is not None:
                front_clips.append(c)

    # V2 · Behind Subject (packed into non-overlapping lanes if needed)
    behind_lanes = _pack_non_overlapping_lanes(behind_clips, rate)
    for li, lane in enumerate(behind_lanes):
        tname = "V2 · Behind Subject" if len(behind_lanes) == 1 else f"V2{_lane_suffix(li)} · Behind Subject"
        tracks.append({"type": "video", "name": tname, "clips": lane})

    # V3 · B-Roll (broll_inserts[], "audio": false, packed into non-overlapping lanes)
    broll_clips: list[dict[str, Any]] = []
    for i, br in enumerate(plan.get("broll_inserts") or []):
        if not isinstance(br, dict):
            continue
        c = _build_overlay_clip(
            br, i, plan_dir=plan_dir, vdur=vdur, width=width, height=height,
            rate=rate, warnings=warnings, label_prefix="B-Roll",
        )
        if c is not None:
            c["audio"] = False
            broll_clips.append(c)
    broll_lanes = _pack_non_overlapping_lanes(broll_clips, rate)
    for li, lane in enumerate(broll_lanes):
        tname = "V3 · B-Roll" if len(broll_lanes) == 1 else f"V3{_lane_suffix(li)} · B-Roll"
        tracks.append({"type": "video", "name": tname, "clips": lane})

    # V4 · 3D & Widgets (auto-packed into V4a, V4b, ... when overlapping)
    front_lanes = _pack_non_overlapping_lanes(front_clips, rate)
    for li, lane in enumerate(front_lanes):
        tname = "V4 · 3D & Widgets" if len(front_lanes) == 1 else f"V4{_lane_suffix(li)} · 3D & Widgets"
        tracks.append({"type": "video", "name": tname, "clips": lane})

    # V5 · Captions (packed into non-overlapping lanes if needed)
    caption_lanes = _pack_non_overlapping_lanes(caption_clips, rate)
    for li, lane in enumerate(caption_lanes):
        tname = "V5 · Captions" if len(caption_lanes) == 1 else f"V5{_lane_suffix(li)} · Captions"
        tracks.append({"type": "video", "name": tname, "clips": lane})

    # A1 · Giọng (VOICE)
    if voice_wav is not None:
        tracks.append(
            {
                "type": "audio",
                "name": VOICE_TRACK,
                "clips": [
                    {
                        "name": "VO · giọng",
                        "src": str(voice_wav),
                        "in": 0.0,
                        "at": 0.0,
                        "dur": voice_dur,
                    }
                ],
            }
        )

    # A2 · Nhạc nền (BGM) (optional)
    if plan.get("bgm"):
        bgm_path = _resolve_path(plan["bgm"], plan_dir)
        if bgm_path is None:
            warnings.append(f"BGM file not found ({plan['bgm']}), omitted")
        else:
            binfo = _probe_media(bgm_path)
            if not binfo["has_audio"]:
                warnings.append(f"BGM file has no audio stream ({bgm_path}), omitted")
            else:
                if (bgm_path.suffix.lower() not in AUDIO_EXT) or binfo["has_video"]:
                    stem = out_path.name.replace(".craft.json", "")
                    bgm_path = _extract_pcm_wav(bgm_path, work / f"{stem}_bgm.wav")
                    binfo = _probe_media(bgm_path)
                bdur = round(min(float(binfo["dur"]) or vdur, vdur), 3)
                bgm_clip: dict[str, Any] = {
                    "name": "BGM · nhạc nền",
                    "src": str(bgm_path.resolve()),
                    "in": 0.0,
                    "at": 0.0,
                    "dur": bdur,
                }
                if plan.get("bgm_db") is not None:
                    bgm_clip["gain_db"] = float(plan["bgm_db"])
                tracks.append({"type": "audio", "name": BGM_TRACK, "clips": [bgm_clip]})

    spec_name = name or out_path.name.replace(".craft.json", "")
    raw_spec: dict[str, Any] = {
        "name": spec_name,
        "width": int(width),
        "height": int(height),
        "fps": float(fps) if float(fps) != int(fps) else int(fps),
        "duration": vdur,
        "tracks": tracks,
        "meta": {
            "generator": f"v8_to_craft_spec {VERSION}",
            "source_aroll": str(aroll_path),
            "front_lanes": len(front_lanes),
            "stages_count": len(plan.get("stages") or []),
            "transitions_count": len(plan.get("transitions") or []),
        },
    }

    spec = _sanitize_spec(raw_spec)
    if write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return spec, warnings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Convert v8_edit_plan.json into a strictly compliant FilmCraft .craft.json spec."
    )
    ap.add_argument("--plan", required=True, type=Path, help="Input v8_edit_plan.json")
    ap.add_argument("--out", required=True, type=Path, help="Output .craft.json path")
    ap.add_argument("--work", type=Path, default=None, help="Working directory for extracted .wav audio")
    ap.add_argument("--width", type=int, default=1080, help="Canvas width (default: 1080)")
    ap.add_argument("--height", type=int, default=1920, help="Canvas height (default: 1920)")
    ap.add_argument("--fps", type=float, default=60.0, help="Timeline FPS (default: 60)")
    ap.add_argument("--name", default=None, help="Optional project name")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan_path = args.plan.resolve()
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"v8_to_craft_spec: cannot read {plan_path}: {exc}", file=sys.stderr)
        return 2

    try:
        spec, warnings = build_spec_from_v8_plan(
            plan,
            args.out,
            work_dir=args.work,
            plan_dir=plan_path.parent,
            width=args.width,
            height=args.height,
            fps=args.fps,
            name=args.name,
            write=True,
        )
    except V8SpecError as exc:
        print(f"v8_to_craft_spec: {exc}", file=sys.stderr)
        return 2

    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)
    total_clips = sum(len(t.get("clips", [])) for t in spec.get("tracks", []))
    print(
        f"[V8 TO CRAFT SPEC v{VERSION} OK] tracks={len(spec['tracks'])} clips={total_clips} "
        f"duration={spec['duration']}s -> {args.out.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
