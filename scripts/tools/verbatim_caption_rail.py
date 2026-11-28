#!/usr/bin/env python3
"""
verbatim_caption_rail.py — 100% spoken-word verbatim caption rail builder with hero-beat zone dodging.

CLI:
  verbatim_caption_rail.py --words <words_tl.json> --out <caption_rail.json> \
      [--max-words 4] [--max-chars 26] [--hero-beats <kinetic_plan.json>] [--pause-gap 0.45]

Features:
- Normalizes all Vietnamese / Unicode text to NFC (`unicodedata.normalize("NFC", ...)`).
- Guarantees 100.0% spoken-word coverage: every single word in `words_tl.json` appears in a phrase cue
  with exact per-word `[start, end]` timing for karaoke highlight / pop animation.
- Smart zone dodging: when `--hero-beats` (`kinetic_plan.json`) is supplied, any caption cue overlapping
  a hero beat is tagged `dock_mode: "compact_bottom"` (otherwise `"standard_lower"`) so the rail avoids
  colliding with giant hero typography without dropping a single spoken word.
- Built-in verification gate prints `word_coverage_pct` (must be `100.0%`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

HARD_PUNCT = (".", "?", "!", "…")
SOFT_PUNCT = (",", ";", ":")

SUB_MODES = (
    "sub_01", "sub_02", "sub_03", "sub_04", "sub_05",
    "sub_06", "sub_07", "sub_08", "sub_09", "sub_10",
)

FONT_PAIRS = (
    "FP1_EDITORIAL_LUXE",
    "FP2_SCRIPT_CONTRAST",
    "FP3_CONDENSED_IMPACT",
    "FP4_NEO_TECH_MONO",
    "FP5_DISPLAY_CHUNKY",
    "FP6_SERIF_MODERN",
)

PALETTES = (
    "PAL_ELECTRIC_CYAN",
    "PAL_EMERALD_MINT",
    "PAL_ROYAL_VIOLET",
    "PAL_CORAL_CRIMSON",
    "PAL_SOLAR_AMBER",
    "PAL_CHAMPAGNE_GOLD",
    "PAL_SILVER_CHROME",
    "PAL_DUOTONE_BLUE_ORANGE",
)

NEGATION_WORDS_VI = {
    "giả", "nhựa", "lỗi", "sai", "đừng", "tránh", "rủi", "ro",
    "hỏng", "mất", "tệ", "xấu", "cấm", "không", "chết", "phá", "bẫy", "lừa",
}

STEP_WORDS_VI = {
    "bước", "thứ", "một", "hai", "ba", "bốn", "năm", "đầu", "tiên",
    "top", "phần", "cách", "điểm", "số", "tỷ", "triệu", "ngàn", "nghìn",
}

STOP_WORDS_VI = {
    "và", "là", "của", "thì", "mà", "cái", "một", "các", "những", "ở",
    "từ", "cho", "với", "để", "này", "đó", "khi", "như", "đã", "sẽ",
    "đang", "rất", "quá", "lại", "cũng", "về", "trong", "ra", "vào",
    "lên", "xuống", "tôi", "bạn", "mình", "ta", "nó", "họ", "anh", "em",
    "chị", "hay", "hoặc", "nếu", "vì", "nên", "rằng", "thế", "vậy", "nhé", "nha",
}

TIKTOK_L_SAFE_BOX = {"x_min": 120, "x_max": 840, "y_min": 1020, "y_max": 1216}
_PUNCT_STRIP_RE = re.compile(r"^[.,!?;:()\[\]{}\"'“”‘’…\-–—]+|[.,!?;:()\[\]{}\"'“”‘’…\-–—]+$")
_HAS_DIGIT_RE = re.compile(r"\d")


def _clean_token(tok: str) -> str:
    return _PUNCT_STRIP_RE.sub("", nfc(tok).strip().lower())


def _pick_highlight_idx(cue_words: list[dict[str, Any]]) -> int:
    """Pick the most semantically impactful word index in a cue, skipping Vietnamese stop words."""
    if not cue_words:
        return 0
    best_idx = 0
    best_score = -1e9
    n = len(cue_words)
    for i, w in enumerate(cue_words):
        raw = nfc(str(w.get("word", "")))
        clean = _clean_token(raw)
        if not clean:
            continue
        score = float(len(clean))
        if _HAS_DIGIT_RE.search(clean):
            score += 12.0
        if clean in NEGATION_WORDS_VI:
            score += 10.0
        if clean in STEP_WORDS_VI:
            score += 4.5
        if clean in STOP_WORDS_VI:
            score -= 20.0
        # Slight preference for later content words (punchline position) on ties
        score += (i / max(1, n)) * 0.6
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx


def _enrich_cues_with_style_rotation(cues: list[dict[str, Any]]) -> dict[str, Any]:
    """Enrich every cue with sub_mode, font_pair, palette, highlight_idx, and safe_zone."""
    # General rotation ring excludes sub_09 (reserved for negation/warning) and sub_10 (breathing)
    general_ring = ["sub_01", "sub_02", "sub_04", "sub_06", "sub_07", "sub_05", "sub_08", "sub_03"]
    general_ptr = 0
    fp_ptr = 0
    pal_ptr = 0

    prev_mode: str | None = None
    prev_pal: str | None = None
    prev_fp: str | None = None

    max_consec_mode = 0
    cur_consec_mode = 0
    used_modes: set[str] = set()
    used_pals: set[str] = set()
    used_fps: set[str] = set()

    for idx, cue in enumerate(cues):
        cwords = cue.get("words") or []
        cleaned = [_clean_token(str(w.get("word", ""))) for w in cwords]
        text_lower = nfc(str(cue.get("text", ""))).lower()
        wc = len(cwords)

        # Semantic triggers
        has_negation = (
            any(tok in NEGATION_WORDS_VI for tok in cleaned)
            or "rủi ro" in text_lower
        )
        has_number_or_step = (
            any(_HAS_DIGIT_RE.search(tok) for tok in cleaned)
            or any(tok in STEP_WORDS_VI for tok in cleaned)
        )
        is_short_punch = wc <= 2
        is_breathing = (
            cue.get("dock_mode") == "compact_bottom"
            or (idx > 0 and idx % 6 == 5)
        )

        # Candidate selection with strict anti-monotony (max_consecutive_same_mode = 1)
        chosen_mode: str | None = None
        if has_negation and prev_mode != "sub_09":
            chosen_mode = "sub_09"
        elif has_number_or_step:
            cand = "sub_01" if (wc <= 3 or prev_mode == "sub_05") else "sub_05"
            if cand == prev_mode:
                cand = "sub_05" if cand == "sub_01" else "sub_01"
            chosen_mode = cand
        elif is_short_punch:
            cand = "sub_08" if (idx % 2 == 0 and prev_mode != "sub_08") else "sub_03"
            if cand == prev_mode:
                cand = "sub_08" if cand == "sub_03" else "sub_03"
            chosen_mode = cand
        elif is_breathing and prev_mode != "sub_10":
            chosen_mode = "sub_10"

        if chosen_mode is None or chosen_mode == prev_mode:
            for _ in range(len(general_ring)):
                cand = general_ring[general_ptr % len(general_ring)]
                general_ptr += 1
                if cand != prev_mode:
                    chosen_mode = cand
                    break
            if chosen_mode is None or chosen_mode == prev_mode:
                chosen_mode = next(m for m in SUB_MODES if m != prev_mode)

        # Font pair rotation across FP1..FP6 (never repeating back-to-back)
        fp_cand = FONT_PAIRS[fp_ptr % len(FONT_PAIRS)]
        fp_ptr += 1
        if fp_cand == prev_fp:
            fp_cand = FONT_PAIRS[fp_ptr % len(FONT_PAIRS)]
            fp_ptr += 1

        # Palette rotation across PAL_* (never repeating back-to-back)
        if chosen_mode == "sub_09" and prev_pal != "PAL_CORAL_CRIMSON":
            pal_cand = "PAL_CORAL_CRIMSON"
        else:
            pal_cand = PALETTES[pal_ptr % len(PALETTES)]
            pal_ptr += 1
            if pal_cand == prev_pal:
                pal_cand = PALETTES[pal_ptr % len(PALETTES)]
                pal_ptr += 1

        hl_idx = _pick_highlight_idx(cwords)

        cue["sub_mode"] = chosen_mode
        cue["font_pair"] = fp_cand
        cue["palette"] = pal_cand
        cue["highlight_idx"] = hl_idx
        cue["safe_zone"] = "tiktok_l_strict"
        cue["safe_zone_box_px"] = dict(TIKTOK_L_SAFE_BOX)

        if chosen_mode == prev_mode:
            cur_consec_mode += 1
        else:
            cur_consec_mode = 1
        if cur_consec_mode > max_consec_mode:
            max_consec_mode = cur_consec_mode

        prev_mode = chosen_mode
        prev_pal = pal_cand
        prev_fp = fp_cand
        used_modes.add(chosen_mode)
        used_pals.add(pal_cand)
        used_fps.add(fp_cand)

    return {
        "distinct_sub_modes": len(used_modes),
        "sub_modes_used": sorted(used_modes),
        "max_consecutive_sub_mode": max_consec_mode,
        "distinct_palettes": len(used_pals),
        "distinct_font_pairs": len(used_fps),
    }


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def load_words(path: Path) -> list[dict[str, Any]]:
    """Load word-level timeline from words_tl.json (supports dict.words, dict.segments, or bare list)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read --words file {path}: {exc}") from None

    raw_items: list[Any] = []
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        if isinstance(data.get("words"), list):
            raw_items = data["words"]
        elif isinstance(data.get("segments"), list):
            for seg in data["segments"]:
                if isinstance(seg, dict) and isinstance(seg.get("words"), list):
                    raw_items.extend(seg["words"])

    words: list[dict[str, Any]] = []
    for item in raw_items:
        token: str | None = None
        start: float | None = None
        end: float | None = None
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            token = str(item[0])
            start = float(item[1])
            end = float(item[2])
        elif isinstance(item, dict):
            raw_tok = item.get("word", item.get("text"))
            s_val = item.get("start", item.get("t0"))
            e_val = item.get("end", item.get("t1"))
            if raw_tok is not None and s_val is not None and e_val is not None:
                token = str(raw_tok)
                start = float(s_val)
                end = float(e_val)
        if token is None or start is None or end is None:
            continue
        clean = nfc(token).strip()
        if not clean:
            continue
        if end < start:
            start, end = end, start
        words.append(
            {
                "word_index": len(words),
                "word": clean,
                "start": round(start, 4),
                "end": round(end, 4),
            }
        )
    return words


def load_hero_beats(path: Path) -> list[dict[str, Any]]:
    """Load hero beat time spans from kinetic_plan.json (supports beats/hero_beats/bare list)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read --hero-beats file {path}: {exc}") from None

    raw_beats: list[Any] = []
    if isinstance(data, list):
        raw_beats = data
    elif isinstance(data, dict):
        if isinstance(data.get("beats"), list):
            raw_beats = data["beats"]
        elif isinstance(data.get("hero_beats"), list):
            raw_beats = data["hero_beats"]

    beats: list[dict[str, Any]] = []
    for idx, b in enumerate(raw_beats):
        if not isinstance(b, dict):
            continue
        if "start" in b and "end" in b:
            s = float(b["start"])
            e = float(b["end"])
        elif "at" in b and "dur" in b:
            s = float(b["at"])
            e = s + max(0.0, float(b["dur"]))
        else:
            continue
        if e <= s:
            continue
        beats.append(
            {
                "beat_index": int(b.get("beat_index", idx)),
                "start": round(s, 4),
                "end": round(e, 4),
                "template": str(b.get("template", "")),
                "tier_bucket": str(b.get("tier_bucket", "")),
            }
        )
    return beats


def _overlapping_beats(start: float, end: float, hero_beats: list[dict[str, Any]], margin: float = 0.04) -> list[int]:
    hits: list[int] = []
    for b in hero_beats:
        if b["end"] + margin <= start or b["start"] - margin >= end:
            continue
        hits.append(b["beat_index"])
    return hits


def build_caption_rail(
    words: list[dict[str, Any]],
    max_words: int = 4,
    max_chars: int = 26,
    pause_gap: float = 0.45,
    hero_beats: list[dict[str, Any]] | None = None,
    style_rotate: bool = True,
) -> dict[str, Any]:
    """Group words into verbatim phrase cues with 100% word coverage and hero-beat zone dodging."""
    hero_list = hero_beats or []
    cues: list[dict[str, Any]] = []
    buf: list[dict[str, Any]] = []

    def flush() -> None:
        if not buf:
            return
        text = nfc(" ".join(w["word"] for w in buf))
        c_start = buf[0]["start"]
        c_end = max(buf[-1]["end"], c_start + 0.04)
        overlaps = _overlapping_beats(c_start, c_end, hero_list)
        cues.append(
            {
                "cue_index": len(cues),
                "start": round(c_start, 4),
                "end": round(c_end, 4),
                "dur": round(c_end - c_start, 4),
                "text": text,
                "char_count": len(text),
                "word_count": len(buf),
                "dock_mode": "compact_bottom" if overlaps else "standard_lower",
                "overlapping_hero_beats": overlaps,
                "words": [dict(w) for w in buf],
            }
        )
        buf.clear()

    for w in words:
        if buf:
            prev = buf[-1]
            gap = w["start"] - prev["end"]
            cand_text = nfc(" ".join(x["word"] for x in buf) + " " + w["word"])
            should_split = (
                len(buf) >= max_words
                or len(cand_text) > max_chars
                or gap >= pause_gap
                or prev["word"].endswith(HARD_PUNCT)
                or (len(buf) >= 2 and prev["word"].endswith(SOFT_PUNCT))
            )
            if should_split:
                flush()
        buf.append(w)

    flush()

    style_stats: dict[str, Any] = {}
    if style_rotate:
        style_stats = _enrich_cues_with_style_rotation(cues)

    # Verification: 100% spoken-word coverage + Unicode NFC check
    covered_indices: set[int] = set()
    nfc_ok = True
    for cue in cues:
        if cue["text"] != unicodedata.normalize("NFC", cue["text"]):
            nfc_ok = False
        for w in cue["words"]:
            covered_indices.add(int(w["word_index"]))
            if w["word"] != unicodedata.normalize("NFC", w["word"]):
                nfc_ok = False

    total_words = len(words)
    covered_count = len(covered_indices)
    coverage_pct = 100.0 if total_words == 0 else (covered_count / total_words) * 100.0
    missing_indices = sorted(set(range(total_words)) - covered_indices)
    compact_count = sum(1 for c in cues if c["dock_mode"] == "compact_bottom")

    return {
        "tool": "verbatim_caption_rail",
        "unicode_normalization": "NFC",
        "nfc_verified": nfc_ok,
        "params": {
            "max_words": max_words,
            "max_chars": max_chars,
            "pause_gap": pause_gap,
            "hero_beats_count": len(hero_list),
            "style_rotate": style_rotate,
        },
        "stats": {
            "total_words": total_words,
            "covered_words": covered_count,
            "missing_word_indices": missing_indices,
            "word_coverage_pct": round(coverage_pct, 4),
            "cue_count": len(cues),
            "compact_bottom_cues": compact_count,
            "standard_lower_cues": len(cues) - compact_count,
            **style_stats,
        },
        "cues": cues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", required=True, help="Path to words_tl.json")
    ap.add_argument("--out", required=True, help="Output caption_rail.json path")
    ap.add_argument("--max-words", type=int, default=4, help="Max words per caption cue (default: 4)")
    ap.add_argument("--max-chars", type=int, default=26, help="Max characters per caption cue (default: 26)")
    ap.add_argument("--pause-gap", type=float, default=0.45, help="Split cue on silence gap >= this many seconds (default: 0.45)")
    ap.add_argument("--hero-beats", default=None, help="Optional path to kinetic_plan.json for smart zone dodging")
    ap.add_argument(
        "--style-rotate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enrich every cue with rotating v8.1 sub_mode, font_pair, palette, highlight_idx, and TikTok L-safe-zone (default: True)",
    )
    args = ap.parse_args()

    words_path = Path(args.words)
    if not words_path.is_file():
        print(f"words file not found: {words_path}", file=sys.stderr)
        return 2

    hero_beats: list[dict[str, Any]] = []
    if args.hero_beats:
        hb_path = Path(args.hero_beats)
        if not hb_path.is_file():
            print(f"hero-beats file not found: {hb_path}", file=sys.stderr)
            return 2
        hero_beats = load_hero_beats(hb_path)

    words = load_words(words_path)
    rail = build_caption_rail(
        words=words,
        max_words=max(1, args.max_words),
        max_chars=max(1, args.max_chars),
        pause_gap=max(0.0, args.pause_gap),
        hero_beats=hero_beats,
        style_rotate=bool(args.style_rotate),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rail, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    stats = rail["stats"]
    summary = {
        "tool": "verbatim_caption_rail",
        "out": str(out_path),
        "total_words": stats["total_words"],
        "covered_words": stats["covered_words"],
        "word_coverage_pct": f"{stats['word_coverage_pct']:.1f}%",
        "cue_count": stats["cue_count"],
        "compact_bottom_cues": stats["compact_bottom_cues"],
        "nfc_verified": rail["nfc_verified"],
        "style_rotate": bool(args.style_rotate),
    }
    if args.style_rotate:
        summary["distinct_sub_modes"] = stats.get("distinct_sub_modes", 0)
        summary["max_consecutive_sub_mode"] = stats.get("max_consecutive_sub_mode", 0)
        summary["distinct_palettes"] = stats.get("distinct_palettes", 0)
        summary["distinct_font_pairs"] = stats.get("distinct_font_pairs", 0)
    print(json.dumps(summary, ensure_ascii=False))

    if stats["word_coverage_pct"] < 100.0 or not rail["nfc_verified"]:
        print("VERIFICATION FAILED: word_coverage_pct < 100.0% or non-NFC text detected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
