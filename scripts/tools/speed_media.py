#!/usr/bin/env python3
"""
speed_media.py — manifest-free, stateless speed policy for ONE pre-ingest media file.

IMPORTANT: speed is applied only to the pre-ingest media (after silence_cut, before probe_and_align builds
words_tl.json), never after a spec exists (.craft.json): every word time, cut, SFX and overlay would drift.
It is advisory: `plan` measures and recommends, the brain decides, then runs `apply`.

Policy (highest step whose result stays >= 45 s):  1.10  ->  1.05  ->  1.0
  - total length under 45 s after speeding up stays 1.0 (nothing is written by `apply`);
  - 1.15x and 1.25x are banned;
  - pitch is preserved (ffmpeg atempo); output is constant frame rate on the --fps grid (30 or 60).

  speed_media.py plan  --input X [--fps 30|60]
        Prints JSON: {"duration", "speed", "out_duration", "reason", ...}.
  speed_media.py apply --input X --out Y [--fps 30|60] [--speed 1.10|1.05|1.0]
        Renders Y at the policy speed (or the allowed --speed override). At 1.0 nothing is written.
  speed_media.py check --input X --out Y [--fps 30|60]
        Exit 1 when Y is not exactly X sped up by an allowed step (length within 1 frame), is under 45 s when
        sped up, is faster than the policy allows, is not constant frame rate, changed size, or lost its audio.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
FFPROBE = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")

SPEED_STEPS = (1.10, 1.05)
ALLOWED_SPEEDS = (1.0, *SPEED_STEPS)
BANNED_SPEEDS = (1.15, 1.25)
MIN_RESULT_S = 45.0


def choose_speed(total_seconds: float, steps: tuple[float, ...] = SPEED_STEPS, min_result: float = MIN_RESULT_S) -> float:
    """Highest step keeping the result >= `min_result` seconds; otherwise 1.0."""
    for s in steps:
        if round(total_seconds / s, 3) >= min_result:      # millisecond rounding: 49.5 s / 1.10 = 45 s is on the line
            return s
    return 1.0


def probe(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,r_frame_rate,avg_frame_rate,duration:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout
    try:
        d = json.loads(out)
        info: dict = {"duration": float(d["format"]["duration"])}
    except (ValueError, KeyError):
        raise SystemExit(f"cannot probe media: {path}") from None
    for s in d.get("streams", []):
        info.setdefault(s["codec_type"], s)
    return info


def _out_graph(speed: float, fps: int, has_v: bool, has_a: bool) -> tuple[list[str], list[str]]:
    """(filter args, codec args)."""
    v = f"setpts=PTS/{speed:.2f},fps={fps}"
    a = f"atempo={speed:.2f},aresample=48000:async=1:first_pts=0"
    vcodec = ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", str(fps),
              "-movflags", "+faststart"]
    acodec = ["-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    if has_v and has_a:
        return ["-filter_complex", f"[0:v]{v}[v];[0:a]{a}[a]", "-map", "[v]", "-map", "[a]"], vcodec + acodec
    if has_v:
        return ["-vf", v], vcodec + ["-an"]
    return ["-af", a], ["-ar", "48000"]


def cmd_plan(a: argparse.Namespace) -> int:
    info = probe(Path(a.input))
    dur = info["duration"]
    speed = choose_speed(dur)
    if speed == 1.0:
        reason = f"{dur:.2f} s would drop under {MIN_RESULT_S:.0f} s when sped up: stay at 1.0"
    else:
        reason = f"{dur:.2f} s / {speed:.2f} = {dur / speed:.2f} s >= {MIN_RESULT_S:.0f} s"
    print(json.dumps({"tool": "speed_media", "input": a.input, "advisory": True, "fps": a.fps, "duration": round(dur, 3),
                      "speed": speed, "out_duration": round(dur / speed, 3), "reason": reason,
                      "policy": {"steps": list(SPEED_STEPS), "min_result_seconds": MIN_RESULT_S, "banned": list(BANNED_SPEEDS)},
                      "scope": "pre-ingest media only; never after a .craft.json spec exists"}, ensure_ascii=False, indent=1))
    return 0


def cmd_apply(a: argparse.Namespace) -> int:
    src = Path(a.input)
    info = probe(src)
    speed = a.speed if a.speed is not None else choose_speed(info["duration"])
    if speed == 1.0:
        print(json.dumps({"tool": "speed_media", "speed": 1.0, "written": False, "note": "1.0x: use the source media as is"}))
        return 0
    if not a.out:
        print("apply needs --out Y", file=sys.stderr)
        return 2
    dst = Path(a.out)
    if dst.resolve() == src.resolve():
        print("--out must differ from --input", file=sys.stderr)
        return 2
    graph, codec = _out_graph(speed, a.fps, "video" in info, "audio" in info)
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", "-i", str(src), *graph, *codec, str(dst)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0:
        print(f"ffmpeg failed: {r.stderr[-500:]}", file=sys.stderr)
        return 1
    print(json.dumps({"tool": "speed_media", "speed": speed, "written": True, "out": str(dst), "fps": a.fps,
                      "out_duration": round(probe(dst)["duration"], 3)}, ensure_ascii=False))
    return 0


def check_pair(src_info: dict, dst_info: dict, fps: int) -> tuple[float | None, list[str]]:
    """(inferred speed, errors)."""
    errs: list[str] = []
    s_dur, d_dur = src_info["duration"], dst_info["duration"]
    tol = 1 / fps + 0.03                                  # 1 frame + AAC / mp3 encoder padding
    inferred = next((s for s in ALLOWED_SPEEDS if abs(d_dur - s_dur / s) <= tol), None)
    if inferred is None:
        errs.append(f"output {d_dur:.3f} s is not {s_dur:.3f} s / {{1.0, 1.05, 1.10}} (ratio {s_dur / d_dur:.3f}x; 1.15 and 1.25 are banned)")
        return None, errs
    policy = choose_speed(s_dur)
    if inferred > policy + 1e-9:
        errs.append(f"speed {inferred:.2f}x is above the policy {policy:.2f}x for a {s_dur:.2f} s source")
    if inferred != 1.0 and d_dur < MIN_RESULT_S - tol:
        errs.append(f"result {d_dur:.2f} s is under {MIN_RESULT_S:.0f} s")
    if "video" in src_info:
        v = dst_info.get("video", {})
        if not v:
            errs.append("output lost its video stream")
        else:
            want = f"{fps}/1"
            if v.get("r_frame_rate") != want or v.get("avg_frame_rate") != want:
                errs.append(f"not constant {fps} fps (r={v.get('r_frame_rate')}, avg={v.get('avg_frame_rate')})")
            if (v.get("width"), v.get("height")) != (src_info["video"].get("width"), src_info["video"].get("height")):
                errs.append("frame size differs from the source")
    if "audio" in src_info:
        if "audio" not in dst_info:
            errs.append("output lost its audio stream")
        elif "video" in dst_info:
            gap = abs(float(dst_info["video"].get("duration", d_dur)) - float(dst_info["audio"].get("duration", d_dur)))
            if gap > 1 / 30 + 0.03:
                errs.append(f"video/audio length differ by {gap:.3f} s")
    return inferred, errs


def cmd_check(a: argparse.Namespace) -> int:
    src, dst = Path(a.input), Path(a.out) if a.out else None
    src_info = probe(src)
    if choose_speed(src_info["duration"]) == 1.0 and (dst is None or not dst.is_file()):
        print(json.dumps({"tool": "speed_media", "ok": True, "note": "policy speed is 1.0: nothing to check"}))
        return 0
    if dst is None or not dst.is_file():
        print(json.dumps({"tool": "speed_media", "ok": False, "errors": ["output file missing: run `apply` first"]}))
        return 1
    inferred, errs = check_pair(src_info, probe(dst), a.fps)
    print(json.dumps({"tool": "speed_media", "ok": not errs, "speed": inferred, "errors": errs}, ensure_ascii=False))
    return 1 if errs else 0


def _speed_arg(text: str) -> float:
    v = float(text)
    if any(abs(v - b) < 1e-6 for b in BANNED_SPEEDS):
        raise argparse.ArgumentTypeError(f"{v:g}x is banned (allowed: 1.10, 1.05, 1.0)")
    if not any(abs(v - s) < 1e-6 for s in ALLOWED_SPEEDS):
        raise argparse.ArgumentTypeError(f"{v:g}x is not an allowed step (allowed: 1.10, 1.05, 1.0)")
    return min(ALLOWED_SPEEDS, key=lambda s: abs(s - v))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["plan", "apply", "check"])
    ap.add_argument("--input", required=True, help="pre-ingest media (video or audio)")
    ap.add_argument("--out", help="apply / check: the sped-up media path")
    ap.add_argument("--fps", type=int, choices=[30, 60], default=30, help="output frame grid, constant frame rate (default 30)")
    ap.add_argument("--speed", type=_speed_arg, help="apply only: override the policy with 1.10, 1.05 or 1.0 (1.15 / 1.25 refused)")
    a = ap.parse_args()
    if not Path(a.input).is_file():
        print(f"input not found: {a.input}", file=sys.stderr)
        return 2
    return {"plan": cmd_plan, "apply": cmd_apply, "check": cmd_check}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main())
