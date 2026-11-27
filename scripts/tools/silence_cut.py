#!/usr/bin/env python3
"""
silence_cut.py — stateless silence cutter for talking-head A-roll (runs BEFORE probe_and_align).

The brain decides, the tool measures: `silencedetect` finds the quiet spans, the KEEP segments are their
complement, padded, merged and frame-snapped. Run it on the raw A-roll first so that `words_tl.json` is
built on the already-cut media (never cut after a spec exists: every timestamp would shift).

  silence_cut.py plan  --input X [--out plan.json] [--pad-before 0.07] [--pad-after 0.09] [--merge-gap 0.12] [--fps 30|60]
        Prints the plan as JSON: {"segments": [[start, end], ...], "kept_seconds", "removed_seconds", "out_duration", ...}.
        Writes nothing else (and the same JSON to --out when given).
  silence_cut.py apply --input X --out Y.mp4 [same options]
        Re-plans with the same options and renders Y: kept segments concatenated, constant frame rate (--fps),
        audio and video cut on identical frame boundaries. Audio-only inputs give audio-only output.

Other options: --noise -35 (dB threshold), --min-silence 0.3 (s, shortest silence that is cut),
--min-keep 0.10 (s, speech fragments shorter than this are dropped as clicks / breaths).
Segment boundaries are multiples of 1/fps; the last segment is clamped to the last whole frame of the file.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
FFPROBE = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")

DEFAULTS = {"noise_db": -35.0, "min_silence": 0.3, "pad_before": 0.07, "pad_after": 0.09, "merge_gap": 0.12, "min_keep": 0.10}


def probe_streams(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
        kinds = {s["codec_type"] for s in d.get("streams", [])}
        return {"duration": float(d["format"]["duration"]), "video": "video" in kinds, "audio": "audio" in kinds}
    except (ValueError, KeyError):
        raise SystemExit(f"cannot probe media: {path}") from None


def detect_silences(path: Path, noise_db: float, min_silence: float, dur: float) -> list[tuple[float, float]]:
    """[(silence_start, silence_end)] from ffmpeg silencedetect; a silence running to EOF ends at the file duration."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-vn", "-i", str(path), "-af",
                          f"silencedetect=n={noise_db}dB:d={min_silence}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    ends += [dur] * (len(starts) - len(ends))
    return list(zip(starts, ends))


def keep_segments(silences: list[tuple[float, float]], dur: float, pad_before: float = 0.07, pad_after: float = 0.09,
                  merge_gap: float = 0.12, fps: int = 30, min_keep: float = 0.10) -> list[tuple[float, float]]:
    """KEEP = complement of `silences` within [0, dur], padded, merged when closer than `merge_gap`, snapped to 1/fps."""
    quiet: list[tuple[float, float]] = []
    for s, e in sorted((max(0.0, s), min(dur, e)) for s, e in silences):
        if e <= s:
            continue
        if quiet and s <= quiet[-1][1]:
            quiet[-1] = (quiet[-1][0], max(quiet[-1][1], e))
        else:
            quiet.append((s, e))
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in quiet:
        if s > cursor:
            speech.append((cursor, s))
        cursor = e
    if cursor < dur:
        speech.append((cursor, dur))
    padded: list[tuple[float, float]] = []
    for a, b in speech:
        if b - a < min_keep:
            continue
        a, b = max(0.0, a - pad_before), min(dur, b + pad_after)
        if padded and a - padded[-1][1] < merge_gap:
            padded[-1] = (padded[-1][0], b)
        else:
            padded.append((a, b))
    last = math.floor(dur * fps + 1e-6) / fps            # last whole frame still inside the file
    snapped: list[tuple[float, float]] = []
    for a, b in padded:
        a, b = round(a * fps) / fps, min(round(b * fps) / fps, last)
        if b - a < 1 / fps - 1e-9:
            continue
        if snapped and a <= snapped[-1][1] + 1e-9:       # snapping made neighbours touch: one segment
            snapped[-1] = (snapped[-1][0], max(snapped[-1][1], b))
        else:
            snapped.append((a, b))
    return [(round(a, 6), round(b, 6)) for a, b in snapped]


def build_plan(path: Path, noise_db: float, min_silence: float, pad_before: float, pad_after: float, merge_gap: float,
               fps: int, min_keep: float) -> dict:
    info = probe_streams(path)
    if not info["audio"]:
        raise SystemExit(f"no audio stream to analyse: {path}")
    dur = info["duration"]
    segs = keep_segments(detect_silences(path, noise_db, min_silence, dur), dur, pad_before, pad_after, merge_gap, fps, min_keep)
    kept = sum(b - a for a, b in segs)
    return {
        "tool": "silence_cut", "input": str(path), "fps": fps, "has_video": info["video"],
        "params": {"noise_db": noise_db, "min_silence": min_silence, "pad_before": pad_before, "pad_after": pad_after,
                   "merge_gap": merge_gap, "min_keep": min_keep},
        "duration": round(dur, 3), "segments": [[a, b] for a, b in segs], "segment_count": len(segs),
        "kept_seconds": round(kept, 3), "removed_seconds": round(dur - kept, 3), "out_duration": round(kept, 3),
    }


def filter_script(segs: list[list[float]], fps: int, has_video: bool) -> tuple[str, list[str]]:
    parts: list[str] = []
    for i, (a, b) in enumerate(segs):
        if has_video:
            parts.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS,fps={fps}[v{i}]")
        parts.append(f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS[a{i}]")
    n = len(segs)
    if has_video:
        pairs = "".join(f"[v{i}][a{i}]" for i in range(n))
        parts.append(f"{pairs}concat=n={n}:v=1:a=1[vc][ac];[vc]fps={fps}[v]")
        return ";".join(parts), ["-map", "[v]", "-map", "[ac]"]
    parts.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ac]")
    return ";".join(parts), ["-map", "[ac]"]


def cmd_plan(a: argparse.Namespace) -> int:
    plan = build_plan(Path(a.input), a.noise, a.min_silence, a.pad_before, a.pad_after, a.merge_gap, a.fps, a.min_keep)
    text = json.dumps(plan, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def cmd_apply(a: argparse.Namespace) -> int:
    if not a.out:
        print("apply needs --out Y (media file)", file=sys.stderr)
        return 2
    src, dst = Path(a.input), Path(a.out)
    if src.resolve() == dst.resolve():
        print("--out must differ from --input (the source is never overwritten)", file=sys.stderr)
        return 2
    plan = build_plan(src, a.noise, a.min_silence, a.pad_before, a.pad_after, a.merge_gap, a.fps, a.min_keep)
    if not plan["segments"]:
        print("nothing to keep: the whole input is silence", file=sys.stderr)
        return 1
    graph, maps = filter_script(plan["segments"], a.fps, plan["has_video"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    codec = (["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", str(a.fps),
              "-movflags", "+faststart", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"] if plan["has_video"]
             else ["-ar", "48000"])
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "graph.txt"
        script.write_text(graph, encoding="utf-8")
        r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", "-i", str(src), "-filter_complex_script", str(script),
                            *maps, *codec, str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ffmpeg failed: {r.stderr[-500:]}", file=sys.stderr)
        return 1
    print(json.dumps({"tool": "silence_cut", "out": str(dst), "segments": plan["segment_count"], "fps": a.fps,
                      "planned_duration": plan["out_duration"], "removed_seconds": plan["removed_seconds"]}, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["plan", "apply"])
    ap.add_argument("--input", required=True, help="A-roll video (or audio) to cut")
    ap.add_argument("--out", help="plan: optional JSON path; apply: output media path (required)")
    ap.add_argument("--pad-before", type=float, default=DEFAULTS["pad_before"], help="seconds kept before speech (default 0.07)")
    ap.add_argument("--pad-after", type=float, default=DEFAULTS["pad_after"], help="seconds kept after speech (default 0.09)")
    ap.add_argument("--merge-gap", type=float, default=DEFAULTS["merge_gap"], help="merge kept segments closer than this (default 0.12)")
    ap.add_argument("--fps", type=int, choices=[30, 60], default=30, help="frame grid and output frame rate (default 30)")
    ap.add_argument("--noise", type=float, default=DEFAULTS["noise_db"], help="silence threshold in dB (default -35)")
    ap.add_argument("--min-silence", type=float, default=DEFAULTS["min_silence"], help="shortest silence to cut, seconds (default 0.3)")
    ap.add_argument("--min-keep", type=float, default=DEFAULTS["min_keep"], help="drop speech fragments shorter than this (default 0.10)")
    a = ap.parse_args()
    if not Path(a.input).is_file():
        print(f"input not found: {a.input}", file=sys.stderr)
        return 2
    return {"plan": cmd_plan, "apply": cmd_apply}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main())
