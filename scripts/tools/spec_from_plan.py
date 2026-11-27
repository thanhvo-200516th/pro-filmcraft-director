#!/usr/bin/env python3
"""
spec_from_plan.py (v7.9.0) — turn a `plan_dviet_kinetic_beat_schedule` plan into a compile-ready `.craft.json`.

    spec_from_plan.py --plan plan.json --words words_tl.json --media-dir DIR --out X.craft.json
                      [--fps 30] [--width 1080] [--height 1920] [--name NAME]
                      [--auto-sfx KEYWORD] [--no-voice-track]

Applies the conventions that are otherwise undocumented (see `references/21_craft_json_minimal_spec.md`):
  * the V1 clip with embedded audio gets `"audio": false` whenever a VOICE track exists
    (otherwise `fc_build.py` dies with `KeyError` on the linked-audio clip id);
  * the voice track is named `A1 · Giọng (VOICE)` and the BGM track `A3 · Nhạc nền (BGM)`, so the
    `audio_levels.py` role heuristic ('giọng' / 'voice' / 'vo' / 'a1', 'nhạc' / 'music' / 'bgm') classifies them;
  * `--auto-sfx KEYWORD` adds one `AUTO:<keyword>` SFX clip per beat (resolve with `compile_and_verify.py --auto-sfx-dir`);
  * plate clips whose `.mov` does not exist on disk fall back to native text clips (`main_text`);
  * optional plan key `opener` (additive): `"flicker"` or {"preset": "flicker", "plate": PNG/MP4, "silhouette": MOV,
    "subject": null, "states": [[state, frames], ...], "start_frame": 0} adds a top track `Vn · Opener (flicker)` with the
    frame-exact silhouette-flicker rows of `flicker_schedule.py` (EXPERIMENTAL, behaviour_unverified_in_app).
    Missing files, unknown presets and C-class asks raise `PlanError` (exit 2); nothing is faked.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path
from typing import Any

VERSION = "7.9.0"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
AROLL_RE = re.compile(r"a[-_ ]?roll", re.I)
BROLL_RE = re.compile(r"b[-_ ]?roll", re.I)
MUSIC_RE = re.compile(r"bgm|music|nhac|nhạc|beat", re.I)
VOICE_RE = re.compile(r"voice|giong|giọng|narrat|\bvo\b", re.I)
VOICE_TRACK = unicodedata.normalize("NFC", "A1 · Giọng (VOICE)")
BGM_TRACK = unicodedata.normalize("NFC", "A3 · Nhạc nền (BGM)")
SFX_TRACK = "A2 · SFX"
PLATE_KEYS = ("name", "src", "in", "at", "dur", "motion", "opacity", "blend", "effects", "preset")


class PlanError(ValueError):
    pass


def _probe(path: Path) -> dict[str, Any]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=120,
    )
    if r.returncode != 0:
        raise PlanError(f"ffprobe failed on {path}: {r.stderr.strip()[-200:]}")
    doc = json.loads(r.stdout or "{}")
    types = {s.get("codec_type") for s in doc.get("streams", [])}
    return {"dur": float(doc.get("format", {}).get("duration") or 0.0), "has_audio": "audio" in types, "has_video": "video" in types}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"cannot read {path}: {exc}") from exc


def last_word_end(words_doc: Any) -> float:
    words = words_doc.get("words_tl") if isinstance(words_doc, dict) else words_doc
    if isinstance(words, dict):
        words = words.get("words_tl") or words.get("words")
    ends = [float(w[2]) for w in (words or []) if isinstance(w, (list, tuple)) and len(w) >= 3]
    return max(ends, default=0.0)


def discover_media(media_dir: Path) -> dict[str, list[Path]]:
    files = sorted(p for p in media_dir.rglob("*") if p.is_file() and not p.name.startswith("."))
    return {
        "video": [p for p in files if p.suffix.lower() in VIDEO_EXT],
        "audio": [p for p in files if p.suffix.lower() in AUDIO_EXT],
    }


def pick_aroll(videos: list[Path]) -> Path:
    cands = [p for p in videos if AROLL_RE.search(p.stem)] or [p for p in videos if not BROLL_RE.search(p.stem)] or videos
    if not cands:
        raise PlanError("no video file found in --media-dir (expected an A-roll .mp4/.mov)")
    return cands[0]


def _extract_voice(src: Path, out_wav: Path) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(out_wav)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=1800,
    )
    if r.returncode != 0 or not out_wav.is_file():
        raise PlanError(f"could not extract voice from {src}: {r.stderr.strip()[-200:]}")
    return out_wav


def _resolve_plate(src: str, plan_dir: Path, media_dir: Path) -> Path | None:
    p = Path(src)
    # relative plate paths may be relative to the planner's cwd (out_dir="work/plates"), the plan folder or the media folder;
    # missing the cwd case silently swapped every kt plate for a native text proxy (v7.9.4 e2e run)
    for cand in ([p] if p.is_absolute() else [p, plan_dir / p, media_dir / p, plan_dir / p.name, media_dir / p.name]):
        if cand.is_file():
            return cand.resolve()
    return None


def _trim_overlaps(clips: list[dict[str, Any]], warnings: list[str], label: str) -> list[dict[str, Any]]:
    out = sorted(clips, key=lambda c: c["at"])
    for a, b in zip(out, out[1:]):
        if a["at"] + a["dur"] > b["at"] + 1e-6:
            new_dur = round(max(0.05, b["at"] - a["at"]), 6)
            warnings.append(f"{label}: '{a['name']}' trimmed {a['dur']:.2f}s -> {new_dur:.2f}s to avoid overlapping '{b['name']}'")
            a["dur"] = new_dur
    return out


def _fps_fraction(fps: float) -> tuple[int, int]:
    """30 -> (30, 1); 29.97 -> (30000, 1001): the same NTSC snap as fc_build.fps_fraction."""
    for base in (24, 30, 48, 60, 120):
        if abs(fps - base * 1000 / 1001) < 0.005:
            return base * 1000, 1001
    fr = Fraction(fps).limit_denominator(1000)
    return fr.numerator, fr.denominator


def _opener_clips(
    opener: Any, plan_dir: Path, media_dir: Path, fps: float, vdur: float,
) -> list[dict[str, Any]]:
    """Clip rows for the optional plan key `opener` (preset `flicker`); raises PlanError on anything unsupported."""
    import flicker_schedule as fs  # noqa: PLC0415  (sibling module; only needed when the plan asks for an opener)

    cfg = {"preset": opener} if isinstance(opener, str) else opener
    if not isinstance(cfg, dict) or not isinstance(cfg.get("preset"), str):
        raise PlanError('plan `opener` must be "flicker" or an object with a `preset` key')
    try:
        fs.refuse_c_class(cfg["preset"])
    except fs.UnsupportedEffectError as exc:
        raise PlanError(str(exc)) from exc
    if cfg["preset"] != "flicker":
        raise PlanError(f"unknown opener preset {cfg['preset']!r} (supported: 'flicker')")
    sources: dict[str, Any] = {"subject": None}  # the real subject is the A-roll on V1 showing through
    for state, key in (("plate", "plate"), ("silhouette", "silhouette")):
        if not cfg.get(key):
            raise PlanError(f"opener flicker needs `{key}` (a file: the clean plate / the #FFFBF0 silhouette .mov)")
        found = _resolve_plate(str(cfg[key]), plan_dir, media_dir)
        if found is None:
            raise PlanError(f"opener flicker: `{key}` file not found: {cfg[key]}")
        sources[state] = str(found)
    if cfg.get("subject"):
        found = _resolve_plate(str(cfg["subject"]), plan_dir, media_dir)
        if found is None:
            raise PlanError(f"opener flicker: `subject` file not found: {cfg['subject']}")
        sources["subject"] = str(found)
    num, den = _fps_fraction(fps)
    try:
        rows = fs.flicker_schedule(num, den, cfg.get("states"), int(cfg.get("start_frame", 0)))
        clips = fs.schedule_to_clips(rows, sources)
    except fs.FlickerError as exc:
        raise PlanError(f"opener flicker: {exc}") from exc
    end = rows[-1]["at"] + rows[-1]["dur"]
    if end > vdur + 1e-6:
        raise PlanError(f"opener flicker lasts {end:.3f}s but the A-roll is {vdur:.3f}s long")
    return clips


def build_spec(
    plan: Any, words_doc: Any, media_dir: Path, out_path: Path, *, plan_dir: Path, fps: float = 30.0,
    width: int = 1080, height: int = 1920, name: str | None = None, auto_sfx: str | None = None,
    voice_track: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    craft_clips = plan.get("craft_clips") if isinstance(plan, dict) else plan
    if not isinstance(craft_clips, list):
        raise PlanError("plan has no `craft_clips` list (expected plan_dviet_kinetic_beat_schedule output)")
    media = discover_media(media_dir)
    aroll = pick_aroll(media["video"]).resolve()
    ainfo = _probe(aroll)
    vdur = round(ainfo["dur"], 3)
    if vdur <= 0:
        raise PlanError(f"{aroll} has zero duration")

    voice_src: Path | None = None
    if voice_track:
        voices = [p for p in media["audio"] if VOICE_RE.search(p.stem)]
        if voices:
            voice_src = voices[0].resolve()
        elif ainfo["has_audio"]:
            voice_src = _extract_voice(aroll, out_path.parent / f"{out_path.name.replace('.craft.json', '')}_voice.wav").resolve()
        else:
            warnings.append("A-roll has no audio and no voice file in --media-dir: no VOICE track written")

    v1_clip: dict[str, Any] = {"name": f"A-roll · {aroll.stem}", "src": str(aroll), "in": 0.0, "at": 0.0, "dur": vdur}
    if voice_src is not None:
        v1_clip["audio"] = False  # else fc_build.py KeyErrors on the linked audio clip when a VOICE track exists
    tracks: list[dict[str, Any]] = [{"type": "video", "name": "V1 · A-roll", "clips": [v1_clip]}]

    plates: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    for i, cc in enumerate(craft_clips, 1):
        if not isinstance(cc, dict) or "at" not in cc:
            raise PlanError(f"craft_clips[{i - 1}] needs at least `at` (got {cc!r})")
        at = round(float(cc["at"]), 6)
        if at >= vdur:
            warnings.append(f"craft_clips[{i - 1}] starts at {at:.2f}s >= video length {vdur:.2f}s: dropped")
            continue
        dur = round(min(float(cc.get("dur") or 1.0), vdur - at), 6)
        plate = _resolve_plate(str(cc.get("src") or ""), plan_dir, media_dir) if cc.get("src") else None
        if plate is not None:
            clip = {k: cc[k] for k in PLATE_KEYS if k in cc}
            clip.update({"src": str(plate), "at": at, "dur": dur, "name": str(cc.get("name") or f"Kinetic {i}")})
            plates.append(clip)
        else:
            meta = cc.get("typo_kinetic_meta") or {}
            txt = unicodedata.normalize("NFC", " ".join(str(meta.get(k) or "").strip() for k in ("main_text", "accent_text")).strip())
            if not txt:
                warnings.append(f"craft_clips[{i - 1}]: plate missing and no main_text; dropped")
                continue
            pos = (cc.get("motion") or {}).get("position") or [meta.get("pos_x", width / 2), meta.get("pos_y", height * 0.2)]
            texts.append({
                "name": str(cc.get("name") or f"Text {i}"), "text": txt, "font": "Be Vietnam Pro", "size": 78,
                "color": str(meta.get("base_hex") or "#FAFAFA"), "position": [float(pos[0]), float(pos[1])],
                "at": at, "dur": dur,
            })
            warnings.append(f"craft_clips[{i - 1}]: plate {cc.get('src')!r} not found, native text clip used")
    if plates:
        tracks.append({"type": "video", "name": "V2 · Kinetic", "clips": _trim_overlaps(plates, warnings, "V2")})
    if texts:
        tracks.append({"type": "text", "name": "V3 · Text", "clips": _trim_overlaps(texts, warnings, "V3")})

    if plan.get("opener") if isinstance(plan, dict) else None:
        opener_clips = _opener_clips(plan["opener"], plan_dir, media_dir, fps, vdur)
        if opener_clips:
            tracks.append({"type": "video", "name": f"V{len(tracks) + 1} · Opener (flicker)", "clips": opener_clips})

    if voice_src is not None:
        tracks.append({"type": "audio", "name": VOICE_TRACK,
                       "clips": [{"name": "VO · giọng", "src": str(voice_src), "at": 0.0, "in": 0.0, "dur": vdur}]})
    sfx_clips = [
        {"name": f"SFX · {auto_sfx} {i}", "src": f"AUTO:{auto_sfx}", "at": c["at"], "dur": 0.6}
        for i, c in enumerate(plates + texts, 1)
    ] if auto_sfx else []
    if sfx_clips:
        tracks.append({"type": "audio", "name": SFX_TRACK, "clips": sorted(sfx_clips, key=lambda c: c["at"])})
    music = [p for p in media["audio"] if MUSIC_RE.search(p.stem) and p.resolve() != voice_src]
    if music:
        m = music[0].resolve()
        mdur = _probe(m)["dur"]
        tracks.append({"type": "audio", "name": BGM_TRACK,
                       "clips": [{"name": "BGM · nhạc nền", "src": str(m), "at": 0.0, "in": 0.0, "dur": round(min(mdur, vdur), 3)}]})

    spec = {
        "name": name or out_path.name.replace(".craft.json", ""),
        "width": width, "height": height, "fps": fps, "duration": vdur,
        "tracks": tracks,
        "meta": {"generator": f"spec_from_plan {VERSION}", "last_word_end_s": round(last_word_end(words_doc), 3)},
    }
    if isinstance(plan, dict) and plan.get("opener"):
        spec["meta"]["opener"] = "flicker"
    return spec, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", required=True, help="plan_dviet_kinetic_beat_schedule output (JSON with `craft_clips`)")
    ap.add_argument("--words", required=True, help="words_tl.json (array or probe_and_align document)")
    ap.add_argument("--media-dir", required=True, help="folder with the A-roll video and optional voice/BGM/plates")
    ap.add_argument("--out", required=True, help="output .craft.json")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--name")
    ap.add_argument("--auto-sfx", metavar="KEYWORD", help="add one `AUTO:<KEYWORD>` SFX clip per beat")
    ap.add_argument("--no-voice-track", action="store_true", help="keep the A-roll's embedded audio on V1 (no VOICE track)")
    args = ap.parse_args(argv)

    plan_path, out = Path(args.plan), Path(args.out)
    try:
        spec, warns = build_spec(
            _load_json(plan_path), _load_json(Path(args.words)), Path(args.media_dir).resolve(), out.resolve(),
            plan_dir=plan_path.resolve().parent, fps=args.fps, width=args.width, height=args.height,
            name=args.name, auto_sfx=args.auto_sfx, voice_track=not args.no_voice_track,
        )
    except PlanError as exc:
        print(f"spec_from_plan: {exc}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for w in warns:
        print(f"[warn] {w}", file=sys.stderr)
    print(f"[SPEC FROM PLAN v{VERSION} OK] tracks={len(spec['tracks'])} duration={spec['duration']}s -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
