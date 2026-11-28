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
--min-keep 0.05 (s, speech fragments shorter than this are dropped as clicks / breaths),
--protect-short-words (lowers min-keep safety floor to 0.03s for ultra-short Vietnamese monosyllables),
--whisper-guard words_tl.json (expands every Whisper word timestamp by [-0.07, +0.09]s into protected
voice intervals that are NEVER dropped or trimmed).
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

DEFAULTS = {"noise_db": -35.0, "min_silence": 0.3, "pad_before": 0.07, "pad_after": 0.09, "merge_gap": 0.12, "min_keep": 0.05}
WHISPER_GUARD_BEFORE = 0.07
WHISPER_GUARD_AFTER = 0.09


def probe_streams(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout
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
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    ends += [dur] * (len(starts) - len(ends))
    return list(zip(starts, ends))


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for s, e in sorted(intervals):
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _subtract_intervals(base: list[tuple[float, float]], sub: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not sub:
        return base
    out: list[tuple[float, float]] = []
    for bs, be in base:
        cur = bs
        for ss, se in sub:
            if se <= cur:
                continue
            if ss >= be:
                break
            if ss > cur:
                out.append((cur, ss))
            cur = max(cur, se)
            if cur >= be:
                break
        if cur < be:
            out.append((cur, be))
    return out


def _overlaps_any(a: float, b: float, intervals: list[tuple[float, float]]) -> bool:
    for s, e in intervals:
        if e <= a:
            continue
        if s >= b:
            break
        return True
    return False


def load_whisper_guard_intervals(
    path: Path,
    dur: float,
    guard_before: float = WHISPER_GUARD_BEFORE,
    guard_after: float = WHISPER_GUARD_AFTER,
) -> tuple[list[tuple[float, float]], int]:
    """Parse word timestamps from words_tl.json and expand each by [-guard_before, +guard_after]s."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read --whisper-guard file {path}: {exc}") from None

    raw_items: list = []
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        if isinstance(data.get("words"), list):
            raw_items = data["words"]
        elif isinstance(data.get("segments"), list):
            for seg in data["segments"]:
                if isinstance(seg, dict) and isinstance(seg.get("words"), list) and seg["words"]:
                    raw_items.extend(seg["words"])
                elif isinstance(seg, dict) and "start" in seg and "end" in seg:
                    raw_items.append(seg)

    spans: list[tuple[float, float]] = []
    for item in raw_items:
        s = e = None
        if isinstance(item, (list, tuple)):
            if len(item) >= 3:
                s, e = float(item[1]), float(item[2])
            elif len(item) == 2:
                s, e = float(item[0]), float(item[1])
        elif isinstance(item, dict):
            s_val = item.get("start", item.get("t0"))
            e_val = item.get("end", item.get("t1"))
            if s_val is not None and e_val is not None:
                s, e = float(s_val), float(e_val)
        if s is not None and e is not None:
            if e < s:
                s, e = e, s
            ps = max(0.0, s - guard_before)
            pe = min(dur, e + guard_after)
            if pe > ps:
                spans.append((ps, pe))

    return _merge_intervals(spans), len(spans)


def keep_segments(
    silences: list[tuple[float, float]],
    dur: float,
    pad_before: float = 0.07,
    pad_after: float = 0.09,
    merge_gap: float = 0.12,
    fps: int = 30,
    min_keep: float = 0.05,
    protected: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """KEEP = complement of `silences` within [0, dur], padded, merged when closer than `merge_gap`, snapped to 1/fps.

    When `protected` voice intervals are supplied (from --whisper-guard), silence is never allowed inside
    those intervals, short speech fragments overlapping them are never dropped, and frame snapping expands
    outward so protected voice is never trimmed.
    """
    prot = _merge_intervals([(max(0.0, s), min(dur, e)) for s, e in (protected or [])])
    quiet = _merge_intervals([(max(0.0, s), min(dur, e)) for s, e in silences])
    if prot:
        quiet = _subtract_intervals(quiet, prot)

    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in quiet:
        if s > cursor:
            speech.append((cursor, s))
        cursor = e
    if cursor < dur:
        speech.append((cursor, dur))

    candidates: list[tuple[float, float]] = []
    for a, b in speech:
        if b - a < min_keep and not (prot and _overlaps_any(a, b, prot)):
            continue
        candidates.append((max(0.0, a - pad_before), min(dur, b + pad_after)))
    if prot:
        candidates.extend(prot)

    padded: list[tuple[float, float]] = []
    for a, b in sorted(candidates):
        if padded and a - padded[-1][1] < merge_gap:
            padded[-1] = (padded[-1][0], max(padded[-1][1], b))
        else:
            padded.append((a, b))

    last = math.floor(dur * fps + 1e-6) / fps            # last whole frame still inside the file
    snapped: list[tuple[float, float]] = []
    for a, b in padded:
        if prot and _overlaps_any(a, b, prot):
            a_s = math.floor(a * fps + 1e-9) / fps
            b_s = min(math.ceil(b * fps - 1e-9) / fps, last)
        else:
            a_s = round(a * fps) / fps
            b_s = min(round(b * fps) / fps, last)
        if b_s - a_s < 1 / fps - 1e-9:
            continue
        if snapped and a_s <= snapped[-1][1] + 1e-9:       # snapping made neighbours touch: one segment
            snapped[-1] = (snapped[-1][0], max(snapped[-1][1], b_s))
        else:
            snapped.append((a_s, b_s))
    return [(round(a, 6), round(b, 6)) for a, b in snapped]


def build_plan(
    path: Path,
    noise_db: float,
    min_silence: float,
    pad_before: float,
    pad_after: float,
    merge_gap: float,
    fps: int,
    min_keep: float,
    whisper_guard: Path | None = None,
    protect_short_words: bool = False,
) -> dict:
    info = probe_streams(path)
    if not info["audio"]:
        raise SystemExit(f"no audio stream to analyse: {path}")
    dur = info["duration"]
    eff_min_keep = min(min_keep, 0.03) if protect_short_words else min_keep
    protected: list[tuple[float, float]] = []
    protected_words = 0
    if whisper_guard is not None:
        protected, protected_words = load_whisper_guard_intervals(whisper_guard, dur)
    segs = keep_segments(
        detect_silences(path, noise_db, min_silence, dur),
        dur,
        pad_before,
        pad_after,
        merge_gap,
        fps,
        eff_min_keep,
        protected=protected,
    )
    kept = sum(b - a for a, b in segs)
    plan = {
        "tool": "silence_cut", "input": str(path), "fps": fps, "has_video": info["video"],
        "params": {"noise_db": noise_db, "min_silence": min_silence, "pad_before": pad_before, "pad_after": pad_after,
                   "merge_gap": merge_gap, "min_keep": eff_min_keep, "protect_short_words": protect_short_words,
                   "whisper_guard": str(whisper_guard) if whisper_guard else None},
        "duration": round(dur, 3), "segments": [[a, b] for a, b in segs], "segment_count": len(segs),
        "kept_seconds": round(kept, 3), "removed_seconds": round(dur - kept, 3), "out_duration": round(kept, 3),
    }
    if whisper_guard is not None:
        plan["whisper_guard_words"] = protected_words
        plan["whisper_guard_intervals"] = len(protected)
    return plan


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
    guard = Path(a.whisper_guard) if a.whisper_guard else None
    plan = build_plan(
        Path(a.input), a.noise, a.min_silence, a.pad_before, a.pad_after, a.merge_gap, a.fps, a.min_keep,
        whisper_guard=guard, protect_short_words=a.protect_short_words,
    )
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
    guard = Path(a.whisper_guard) if a.whisper_guard else None
    plan = build_plan(
        src, a.noise, a.min_silence, a.pad_before, a.pad_after, a.merge_gap, a.fps, a.min_keep,
        whisper_guard=guard, protect_short_words=a.protect_short_words,
    )
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
                            *maps, *codec, str(dst)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
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
    ap.add_argument("--min-keep", type=float, default=DEFAULTS["min_keep"], help="drop speech fragments shorter than this (default 0.05)")
    ap.add_argument("--whisper-guard", help="path to words_tl.json; expands each word by [-0.07, +0.09]s into protected voice intervals")
    ap.add_argument("--protect-short-words", action="store_true", help="lower min-keep floor to 0.03s so short Vietnamese monosyllables (<100ms) are never clipped")
    a = ap.parse_args()
    if not Path(a.input).is_file():
        print(f"input not found: {a.input}", file=sys.stderr)
        return 2
    if a.whisper_guard and not Path(a.whisper_guard).is_file():
        print(f"whisper-guard file not found: {a.whisper_guard}", file=sys.stderr)
        return 2
    return {"plan": cmd_plan, "apply": cmd_apply}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main())
