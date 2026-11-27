#!/usr/bin/env python3
"""Kiểm spec .craft.json TRƯỚC khi dựng FilmCraft (học từ ghost-editor render_report / finals: mỗi lỗi có mã + cách sửa).

    python3 spec_lint.py work/kb06.craft.json --words work/words_tl.json [--json]

Mức:
  HARD  — fc_build_fast sẽ hỏng hoặc project sai chắc chắn → dừng build (mã thoát 2).
  SOFT  — lệch luật dựng (hook, đuôi, khoảng chết…) → ghi vào báo cáo, không chặn.
Mỗi mục: {"id", "status": HARD | SOFT | OK, "value", "target", "fix"}.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".aac", ".flac"}
HOOK_TEXT_MAX = 1.5      # chữ hoặc chuyển động đầu tiên trước 1,5 s (ghost render_report hook)
FIRST_WORD_MAX = 0.5     # lời đầu tiên trước 0,5 s
DEAD_AIR_MAX = 0.8       # khoảng lặng giữa hai từ > 0,8 s = khoảng chết
OPEN_SFX_MIN = 0.3       # luật F1: SFX mở đầu ~0,3 s ở khung 0


FORBIDDEN_SPEED_DIRS = ("/x125/", "_x125.", "/x115/", "_x115.")   # D4 (2026-11-13): bỏ 1.25x / 1.15x — chỉ x110 / x105 / gốc
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


@lru_cache(maxsize=None)
def media_size(path: str) -> tuple[int, int] | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except ValueError:
        return None


@lru_cache(maxsize=None)
def media_dur(path: str) -> float | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _keyframe_lists(obj, path: str = ""):
    """Mọi danh sách dạng [[t, giá trị…], …] trong clip (motion, opacity, tham số effect)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _keyframe_lists(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        if obj and all(isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], (int, float))
                       and not isinstance(x[0], bool) for x in obj):
            yield path, obj
        else:
            for i, v in enumerate(obj):
                yield from _keyframe_lists(v, f"{path}[{i}]")


def _item(cid: str, status: str, value, target, fix: str = "") -> dict:
    return {"id": cid, "status": status, "value": value, "target": target, "fix": fix if status != "OK" else ""}


def check_media(clips: list[tuple[str, dict]], fps: float) -> list[dict]:
    missing, past, bad_dur = [], [], []
    for tname, c in clips:
        if c.get("dur", 1) <= 0:
            bad_dur.append(f"{tname}: {c.get('name', '?')[:30]} dur={c.get('dur')}")
        src = c.get("src")
        if not src:
            continue
        p = Path(src)
        if not p.is_file():
            missing.append(str(p))
            continue
        if p.suffix.lower() in MEDIA_EXT and not c.get("loop"):
            d = media_dur(str(p))
            end = c.get("in", 0.0) + c.get("dur", 0.0)
            if d is not None and end > d + 1.0 / fps:
                past.append(f"{tname}: {p.name} in+dur={end:.3f} > file {d:.3f}")
    return [
        _item("media_missing", "HARD" if missing else "OK", missing[:5] or 0, "mọi file nguồn tồn tại",
              "tạo lại / chép media còn thiếu rồi chạy lại build_spec"),
        _item("clip_past_file_end", "HARD" if past else "OK", past[:5] or 0, "in + dur ≤ độ dài file",
              "rút dur của clip (SFX quá ngắn: đổi file hoặc cắt dur = độ dài file − in)"),
        _item("clip_dur_nonpositive", "HARD" if bad_dur else "OK", bad_dur[:5] or 0, "dur > 0",
              "bỏ clip hoặc sửa mốc cắt"),
    ]


def check_speed_quality(spec: dict, clips: list[tuple[str, dict]]) -> list[dict]:
    """D4: không dùng media tăng tốc 1.25x / 1.15x. Rule 3: nguồn video trên V1 không thấp hơn khung dựng (bị phóng to = mờ)."""
    bad_speed = sorted({Path(c["src"]).name for _, c in clips if c.get("src") and any(m in c["src"] for m in FORBIDDEN_SPEED_DIRS)})
    fw, fh = int(spec.get("width", 1080)), int(spec.get("height", 1920))
    low = []
    v1 = next((t for t in spec.get("tracks", []) if t.get("type") == "video"), {"clips": []})
    for c in v1["clips"]:
        src = c.get("src", "")
        if Path(src).suffix.lower() in VIDEO_EXT and Path(src).is_file():
            wh = media_size(src)
            if wh and min(wh[0] / fw, wh[1] / fh) < 0.99:
                low.append(f"{Path(src).name} {wh[0]}x{wh[1]}")
    return [
        _item("speed_not_allowed", "HARD" if bad_speed else "OK", bad_speed[:5] or 0, "chỉ 1.10x / 1.05x / 1.0x (video < 45 s giữ 1.0x)",
              "tăng tốc lại theo build_kit.choose_speed (media/x110 hoặc x105), bỏ media x125 / x115 khỏi spec"),
        _item("low_res_source", "SOFT" if low else "OK", sorted(set(low))[:5] or 0, f"nguồn ≥ {fw}x{fh} (không phóng to)",
              "tạo lại nguồn ở 1080x1920 (HeyGen / Muse 1080p) thay vì phóng to bản nhỏ"),
    ]


def check_keyframes(clips: list[tuple[str, dict]]) -> list[dict]:
    bad = []
    for tname, c in clips:
        for path, keys in _keyframe_lists({k: v for k, v in c.items() if k not in ("src", "text", "name")}):
            ts = [k[0] for k in keys]
            if any(b <= a + 1e-6 for a, b in zip(ts, ts[1:])):
                bad.append(f"{tname}: {c.get('name', '?')[:24]} {path} {ts[:6]}")
    return [_item("keys_not_increasing", "HARD" if bad else "OK", bad[:5] or 0, "mốc key tăng ngặt",
                  "gộp / bỏ key trùng mốc (clip quá ngắn → clamp_keys)")]


def words_list(doc) -> list | None:
    """`words_tl.json` as a bare [[chữ, t0, t1], …]; also takes the probe doc {"words": …} / {"words_tl": …}."""
    if isinstance(doc, dict):
        doc = doc.get("words") if doc.get("words") is not None else doc.get("words_tl")
    if not isinstance(doc, (list, tuple)):
        return None
    out = [[w["word"], w["s"], w["e"]] if isinstance(w, dict) else w for w in doc if isinstance(w, (dict, list, tuple))]
    return out or None


def check_hook(spec: dict, clips: list[tuple[str, dict]], words: list | None) -> list[dict]:
    words = words_list(words)
    text_at = [c["at"] for t, c in clips if c.get("text") or t.startswith("text")]
    first_text = min(text_at) if text_at else None
    out = [_item("hook_text_late", "SOFT" if first_text is None or first_text > HOOK_TEXT_MAX else "OK",
                 first_text, f"≤ {HOOK_TEXT_MAX} s", "đưa chữ hook / chữ chính đầu tiên vào trước 1,5 s")]
    if words:
        fw = float(words[0][1])
        out.append(_item("hook_first_word_late", "SOFT" if fw > FIRST_WORD_MAX else "OK", round(fw, 2),
                         f"≤ {FIRST_WORD_MAX} s", "cắt bớt khoảng lặng đầu A-roll 1"))
    opening = [c for t, c in clips if t.startswith("A") and "mở đầu" in c.get("name", "").lower() and c["at"] <= 0.04]
    ok = any(c.get("dur", 0) >= OPEN_SFX_MIN - 0.02 for c in opening)
    out.append(_item("opening_sfx", "OK" if ok else "SOFT", len(opening), f"SFX MỞ ĐẦU ở khung 0, ≥ {OPEN_SFX_MIN} s",
                     "luật F1: đặt SFX mở đầu ~0,3 s tại 00:00:00:00"))
    v1 = next((t for t in spec["tracks"] if t.get("type") == "video"), {"clips": []})
    starts0 = any(c["at"] <= 1e-3 for c in v1["clips"])
    out.append(_item("frame0_black", "OK" if starts0 else "SOFT", starts0, "V1 có hình ở khung 0",
                     "kéo clip đầu V1 về 0"))
    return out


BURST_N, BURST_S = 6, 0.3   # ≥ 6 từ bắt đầu trong 0,3 s = chữ bật ra cùng lúc, lệch giọng (B16)


def check_text_voice(words: list | None) -> list[dict]:
    words = words_list(words)
    if not words:
        return [_item("text_voice_burst", "OK", "không có words", "-", "")]
    st = [float(w[1]) for w in words]
    bursts = sorted({round(st[i], 2) for i in range(len(st) - BURST_N + 1) if st[i + BURST_N - 1] - st[i] <= BURST_S})
    return [_item("text_voice_burst", "HARD" if bursts else "OK", bursts[:6] or 0,
                  f"< {BURST_N} từ trong {BURST_S} s (chữ khớp giọng)",
                  "chạy retime_voice.py <thư mục video> (mốc từ giọng HeyGen bị dồn) rồi sinh lại spec")]


def check_dead_air(words: list | None) -> list[dict]:
    words = words_list(words)
    if not words:
        return [_item("dead_air", "OK", "không có words", "-", "")]
    gaps = [(round(float(a[2]), 2), round(float(b[1]) - float(a[2]), 2)) for a, b in zip(words, words[1:])
            if float(b[1]) - float(a[2]) > DEAD_AIR_MAX]
    return [_item("dead_air", "SOFT" if gaps else "OK", [f"{t}s (+{g}s)" for t, g in gaps[:5]] or 0,
                  f"khoảng lặng giữa lời ≤ {DEAD_AIR_MAX} s", "cắt bớt khoảng lặng hoặc phủ B-roll / SFX")]


def check_ending(spec: dict, fps: float) -> list[dict]:
    tracks = spec["tracks"]
    v1 = next((t for t in tracks if t.get("type") == "video"), {"clips": []})
    a1 = next((t for t in tracks if t.get("type") == "audio"), {"clips": []})
    v_end = max((c["at"] + c["dur"] for c in v1["clips"]), default=0.0)
    a_end = max((c["at"] + c["dur"] for c in a1["clips"]), default=0.0)
    tail = 1.0 / fps + 1e-3
    return [
        _item("picture_ends_before_voice", "SOFT" if v_end + tail < a_end else "OK", round(a_end - v_end, 3),
              "V1 không hết trước giọng A1", "kéo dài clip cuối V1 hoặc giữ khung cuối"),
        _item("black_tail", "SOFT" if v_end + tail < spec.get("duration", v_end) else "OK",
              round(spec.get("duration", v_end) - v_end, 3), "V1 chạy tới hết video (đuôi đen chớp ở điểm lặp lại)",
              "đặt duration = cuối V1 hoặc kéo dài clip cuối"),
    ]


def check_caption_overlap(spec: dict, clips: list[tuple[str, dict]]) -> list[dict]:
    """C2 (v2.5): cụm phụ đề ra bằng mờ dần (cross_dissolve tâm ở cuối clip) kéo thêm frames/2 khung sau cuối clip; cụm sau không
    được vào trước lúc đó. Hai dòng của cùng một cụm (kết thúc cùng lúc, dòng dưới vào muộn hơn) không tính."""
    fps = float(spec.get("fps", 30))
    cap = [c for t, c in clips if "text_low" in t and c.get("transition_out")]
    allc = [c for t, c in clips if "text_low" in t]
    bad = []
    for c in cap:
        end = c["at"] + c["dur"]
        tail = end + c["transition_out"].get("frames", 0) / 2 / fps
        hit = [o for o in allc if o is not c and end - 0.05 <= o["at"] < tail - 1e-3]
        if hit:
            bad.append(f"{end:.2f}s (cụm sau vào {min(o['at'] for o in hit):.2f}s < hết mờ {tail:.2f}s)")
    return [_item("caption_overlap", "SOFT" if bad else "OK", bad[:5] or 0, "cụm phụ đề không chồng cụm sau (kể cả đuôi mờ dần)",
                  "chạy lại build_spec.py (mẫu v2.6: captions2 chừa đuôi mờ của cụm cuối mỗi hàng); spec tự viết: gọi captions2 MỘT lần cho cả lời, hoặc từng hàng nhưng end ≤ giờ vào hàng sau − 0,05 s")]


def check_name(spec_path: Path) -> list[dict]:
    stale = spec_path.name.startswith("xm02_") and "KB02" not in str(spec_path.resolve().parent.parent.name).upper()
    return [_item("craft_name", "SOFT" if stale else "OK", spec_path.name, "tên craft.json theo video",
                  "sinh lại build_spec bằng gen_build_spec.py mới (đặt tên theo mã video)")]


def lint(spec_path: Path, words: list | None = None) -> list[dict]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    fps = float(spec.get("fps", 30))
    clips = [(t.get("name", ""), c) for t in spec.get("tracks", []) for c in t.get("clips", [])]
    return (check_media(clips, fps) + check_speed_quality(spec, clips) + check_keyframes(clips) + check_hook(spec, clips, words)
            + check_dead_air(words) + check_text_voice(words) + check_ending(spec, fps) + check_caption_overlap(spec, clips)
            + check_name(spec_path))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--words", help="words_tl.json theo giờ timeline: [[chữ, t0, t1], …] hoặc bản probe {\"words\": […]}")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    words = words_list(json.loads(Path(a.words).read_text(encoding="utf-8"))) if a.words else None
    res = lint(Path(a.spec), words)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for r in res:
            line = f"[LINT {r['status']:<4}] {r['id']:<26} {r['value']}"
            print(line + (f"  → {r['fix']}" if r["fix"] else ""))
    return 2 if any(r["status"] == "HARD" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
