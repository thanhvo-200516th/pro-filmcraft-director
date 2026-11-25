#!/usr/bin/env python3
"""
probe_and_align.py (v7.0.0) — Universal Stateless Ingest, Probe, Audit, Alignment,
10x8 Multi-Industry Routing, Cranial Dual-Rail & Zero-Face Macro Safe-Zone Engine.

100% format-agnostic, stateless atomic CLI & Python library for `pro-filmcraft-director`
with Quad-Tier execution (`--tier auto | fast | studio | full`):
  - `fast`   : ~3–8s on clean pre-sliced bundles (Spoken-Number Alignment + 8-frame Haar Face/Cranial
               Envelope + Zero-Face Macro Safe-Zone + B-Roll Geometric Match-Cut Anchors + Vocal J-Cuts).
  - `studio` : Balanced Studio P0+P1 ingest (16-frame Haar Cranial & Dual-Rail + CIE-Lab Enamel-Gum &
               HSV/Edge Macro Safe-Box + 20ms RMS Onset Tightening + B-Roll Border/Flatness Audit).
  - `full`   : Deep ingest & QA for `raw_video` or defective `.fcproj` bundles (Spoken-Number Alignment +
               24-frame Haar Cranial Envelope + Zero-Face Macro Safe-Zone + 15fps Cut-on-Action Peaks +
               20ms RMS S04 Onset Tightening + B-Roll Uniform Border/Flatness Audit & Match-Cut Anchors).
  - `auto`   : Resolves to `full` on `raw_video` or when `existing_fcproj_audit` finds defects,
               and `fast` on clean pre-sliced bundles (with `studio`/`full` compile recommendations
               mapped from `--industry-skin` x `--format-mode` when supplied).

Supported Input Modes (auto-detected via `--input`):
  1. `raw_video`      (.mp4/.mov/.mkv/.webm/.wav/.m4a/.mp3/.flac)
  2. `project_bundle` (directory containing `assets/*`, flat `*.mp4`, optional `*.fcproj`,
                       optional `extras/00_storyboard_manifest.json`)
  3. `fcproj_file`    (file ending in `.fcproj`)

CLI Usage:
  ~/.venvs/video-skills/bin/python3 scripts/tools/probe_and_align.py \
    --input <PATH_TO_RAW_VIDEO_OR_PROJECT_DIR_OR_FCPROJ> \
    --work <WORK_DIR> \
    [--tier {auto,fast,studio,full}] \
    [--industry-skin <SKIN_ID>] \
    [--format-mode <FORMAT_ID_OR_F1..F10>] \
    [--refine-onsets | --no-refine-onsets] \
    [--script <OPTIONAL_TXT_MD_OR_STORYBOARD_JSON>] \
    [--backup] \
    [--whisper-model small] \
    [--self-test]
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import difflib
import functools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, NamedTuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

VERSION = "7.0.0"
SKILL_ROOT = Path(__file__).resolve().parents[2]
HAAR_CASCADE_XML = SKILL_ROOT / "data" / "haarcascade_frontalface_default.xml"
TEXT_VI_JSON = SKILL_ROOT / "data" / "text_vi.json"
INDUSTRY_PROFILES_JSON = SKILL_ROOT / "presets" / "industry_profiles.json"
FORMAT_MODES_JSON = SKILL_ROOT / "presets" / "format_modes_catalog.json"
EXECUTION_TIERS_JSON = SKILL_ROOT / "presets" / "execution_tiers.json"

TICKS_PER_SEC = 254016000000.0

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".opus"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
RAW_MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".cache",
    "node_modules",
    "asset_frames",
    "qa_frames",
    "old_frames",
    "stems",
    "sfx_qa",
}


# ---------------------------------------------------------------------------
# Unicode NFC & Token Alignment Utilities
# ---------------------------------------------------------------------------


def nfc(text: str) -> str:
    """Normalize string strictly to Unicode NFC with collapsed internal whitespace."""
    return " ".join(unicodedata.normalize("NFC", str(text)).split())


def norm_tok(word: str) -> str:
    """Accent-insensitive alphanumeric key for sequence alignment."""
    s = unicodedata.normalize("NFD", str(word).lower().replace("đ", "d"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s)


def clean_gt_token(raw_token: str) -> str:
    """Clean punctuation from ground-truth token while preserving technical tokens (e.g. SKILL.md, 90%, v3.2)."""
    t = unicodedata.normalize("NFC", raw_token).strip(" ,;:!?\"'()[]{}«»“”‘’…—–")
    while t.endswith(".") and not re.search(r"[A-Za-z0-9]\.[A-Za-z0-9]{1,5}$", t):
        t = t[:-1]
    while t.startswith(".") and not re.match(r"^\.[A-Za-z0-9]{1,6}$", t):
        t = t[1:]
    return t.strip(" ,;:!?\"'()[]{}«»“”‘’…")


def parse_rational_fps(fps_str: str | None, fallback: float = 30.0) -> float:
    """Parse ffprobe rational frame rate like '30000/1001' or '30/1' into float."""
    if not fps_str or fps_str in ("0/0", "0", "N/A"):
        return fallback
    if "/" in str(fps_str):
        num_s, den_s = str(fps_str).split("/", 1)
        try:
            num, den = float(num_s), float(den_s)
            if den > 0 and num > 0:
                return round(num / den, 6)
        except ValueError:
            return fallback
    try:
        v = float(fps_str)
        return v if v > 0 else fallback
    except ValueError:
        return fallback


def snap_fps_grid(fps_val: float) -> int:
    """Map float frame rate (e.g. 29.97, 30.0, 59.94, 60.0) to integer editing grid."""
    if fps_val >= 48.0:
        return 60
    if 23.5 <= fps_val < 24.5:
        return 24
    if 24.5 <= fps_val < 25.5:
        return 25
    return 30


def detect_input_mode(input_path: Path) -> str:
    """Auto-detect input mode: `raw_video`, `project_bundle`, or `fcproj_file`."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")
    if input_path.is_dir():
        return "project_bundle"
    ext = input_path.suffix.lower()
    if ext == ".fcproj":
        return "fcproj_file"
    if ext in RAW_MEDIA_EXTS:
        return "raw_video"
    if ext == "":
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(input_path)],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and any(t in r.stdout for t in ("video", "audio")):
            return "raw_video"
    raise ValueError(f"Unsupported input file extension '{ext}' for {input_path}")


def backup_fcproj(fcproj_path: Path) -> Path:
    """Create a timestamped backup of a `.fcproj` file in `~/.cache/opa-video-studio/backup/`."""
    bkp_dir = Path.home() / ".cache" / "opa-video-studio" / "backup"
    bkp_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    bkp_path = bkp_dir / f"{fcproj_path.stem}-{ts}.fcproj"
    if bkp_path.exists():
        bkp_path = bkp_dir / f"{fcproj_path.stem}-{ts}-{os.getpid()}.fcproj"
    shutil.copy2(fcproj_path, bkp_path)
    return bkp_path


# ---------------------------------------------------------------------------
# Script / Storyboard Loading & Sequence Alignment
# ---------------------------------------------------------------------------


def load_ground_truth_script(
    script_path: Path | None,
    bundle_dir: Path | None = None,
) -> dict[str, Any]:
    """Load ground-truth script from `--script` (.txt/.md/.json) or bundle storyboard manifest."""
    resolved: Path | None = None
    if script_path is not None:
        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path}")
        resolved = script_path
    elif bundle_dir is not None:
        candidates = [
            bundle_dir / "extras" / "00_storyboard_manifest.json",
            bundle_dir / "00_storyboard_manifest.json",
        ]
        for c in candidates:
            if c.is_file():
                resolved = c
                break

    if resolved is None:
        return {"source_path": None, "full_text": None, "fps": None, "segments": []}

    raw_text = resolved.read_text(encoding="utf-8")
    ext = resolved.suffix.lower()
    if ext == ".json":
        obj = json.loads(raw_text)
        if isinstance(obj, dict) and isinstance(obj.get("segments"), list):
            segs = obj["segments"]
            texts = [
                nfc(s.get("display_text") or s.get("tts_text") or s.get("text") or "")
                for s in segs
                if isinstance(s, dict)
            ]
            full_text = " ".join(t for t in texts if t)
            return {
                "source_path": str(resolved.resolve()),
                "full_text": nfc(full_text) if full_text else None,
                "fps": obj.get("fps"),
                "segments": segs,
            }
        if isinstance(obj, dict):
            txt = obj.get("script") or obj.get("text") or obj.get("transcript") or ""
            return {
                "source_path": str(resolved.resolve()),
                "full_text": nfc(txt) if txt else None,
                "fps": obj.get("fps"),
                "segments": [],
            }
        if isinstance(obj, list):
            parts = []
            for item in obj:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("display_text") or item.get("text") or item.get("word") or ""))
                elif isinstance(item, list) and item:
                    parts.append(str(item[0]))
            joined = nfc(" ".join(p for p in parts if p))
            return {"source_path": str(resolved.resolve()), "full_text": joined or None, "fps": None, "segments": []}

    # Plain .txt or .md
    cleaned_lines: list[str] = []
    in_frontmatter = False
    for idx, line in enumerate(raw_text.splitlines()):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if not stripped or stripped.startswith("```"):
            continue
        # Strip leading markdown header hashes or bullet markers while keeping prose intact
        stripped = re.sub(r"^#{1,6}\s+", "", stripped)
        stripped = re.sub(r"^[-*>]\s+", "", stripped)
        if stripped:
            cleaned_lines.append(stripped)
    joined_txt = nfc(" ".join(cleaned_lines))
    return {
        "source_path": str(resolved.resolve()),
        "full_text": joined_txt or None,
        "fps": None,
        "segments": [],
    }


# ---------------------------------------------------------------------------
# Spoken Vietnamese Number Normalizer & S04 20ms RMS Onset Tightening (v5.1)
# ---------------------------------------------------------------------------

_UNIT_DIGITS: dict[str, int] = {
    "không": 0,
    "một": 1,
    "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "tư": 4,
    "năm": 5,
    "lăm": 5,
    "nhăm": 5,
    "sáu": 6,
    "bảy": 7,
    "tám": 8,
    "chín": 9,
}
_THOUSAND_WORDS = {"nghìn", "ngàn"}
_HUNDRED_WORDS = {"trăm"}
_ZERO_FILLER_WORDS = {"linh", "lẻ"}

_NUMBER_VOCAB = (
    set(_UNIT_DIGITS)
    | {"mười", "mươi"}
    | _HUNDRED_WORDS
    | _THOUSAND_WORDS
    | _ZERO_FILLER_WORDS
)

# Guard ambiguous Vietnamese syllables so prose words ("đầu tư", "tư duy",
# "riêng lẻ", "linh hồn", "mai mốt") NEVER open a number run on their own.
_AMBIGUOUS_NUMBER_WORDS = {"tư", "lẻ", "linh", "mốt", "lăm", "nhăm"}
_NUMBER_VOCAB_START = _NUMBER_VOCAB - _AMBIGUOUS_NUMBER_WORDS

_NUM_STRIP_RE = re.compile(r"[^\w%]+", re.UNICODE)
_DIGITS_ONLY_RE = re.compile(r"^\d+$")


def _clean_num_word(word: str) -> str:
    """Lowercase NFC token stripped of punctuation except '%' for spoken-number parsing."""
    return _NUM_STRIP_RE.sub("", unicodedata.normalize("NFC", str(word)).lower())


def _align_key(word: str) -> str:
    """Accent-insensitive alphanumeric + '%' key for SequenceMatcher alignment."""
    s = unicodedata.normalize("NFD", str(word).lower().replace("đ", "d"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9%]+", "", s)


def _parse_sub_thousand(words: list[str], allow_zero_hundred: bool = False) -> tuple[int, int]:
    """Parse Vietnamese number grammar in [0..999], returning `(value, words_consumed)`."""
    i, n = 0, len(words)
    total = 0

    if (
        i + 1 < n
        and words[i] in _UNIT_DIGITS
        and words[i + 1] in _HUNDRED_WORDS
        and (allow_zero_hundred or _UNIT_DIGITS[words[i]] > 0)
    ):
        total += _UNIT_DIGITS[words[i]] * 100
        i += 2
        if i + 1 < n and words[i] in _ZERO_FILLER_WORDS and words[i + 1] in _UNIT_DIGITS:
            return total + _UNIT_DIGITS[words[i + 1]], i + 2
        # After `<d> trăm`, only consume tens (`mười` / `<d> mươi`), not a bare unit without `linh/lẻ`
        if i < n and words[i] == "mười":
            total += 10
            i += 1
            if i < n and words[i] in _UNIT_DIGITS:
                total += _UNIT_DIGITS[words[i]]
                i += 1
        elif i + 1 < n and words[i] in _UNIT_DIGITS and words[i + 1] == "mươi":
            total += _UNIT_DIGITS[words[i]] * 10
            i += 2
            if i < n and words[i] in _UNIT_DIGITS:
                total += _UNIT_DIGITS[words[i]]
                i += 1
        return total, i

    if i < n and words[i] == "mười":
        total += 10
        i += 1
        if i < n and words[i] in _UNIT_DIGITS:
            total += _UNIT_DIGITS[words[i]]
            i += 1
    elif i + 1 < n and words[i] in _UNIT_DIGITS and words[i + 1] == "mươi":
        total += _UNIT_DIGITS[words[i]] * 10
        i += 2
        if i < n and words[i] in _UNIT_DIGITS:
            total += _UNIT_DIGITS[words[i]]
            i += 1
    elif i < n and words[i] in _UNIT_DIGITS:
        total += _UNIT_DIGITS[words[i]]
        i += 1

    return total, i


def _parse_number_words(words: list[str]) -> tuple[int, int]:
    """
    Ported & extended from `thlib/textnorm.py`:
    Parse prefix of `words` matching Vietnamese spoken number grammar (`0..999,999`)
    into `(integer_value, consumed_word_count)`.
    """
    n = len(words)
    if n == 0 or words[0] not in _NUMBER_VOCAB_START:
        return 0, 0

    sub_val, sub_len = _parse_sub_thousand(words, allow_zero_hundred=False)
    if sub_len > 0 and sub_len < n and words[sub_len] in _THOUSAND_WORDS:
        total = sub_val * 1000
        i = sub_len + 1
        if i + 1 < n and words[i] in _ZERO_FILLER_WORDS and words[i + 1] in _UNIT_DIGITS:
            return total + _UNIT_DIGITS[words[i + 1]], i + 2
        if i + 1 < n and words[i] in _UNIT_DIGITS and words[i + 1] in _HUNDRED_WORDS:
            rem_val, rem_len = _parse_sub_thousand(words[i:], allow_zero_hundred=True)
            return total + rem_val, i + rem_len
        return total, i

    return sub_val, sub_len


def _merge_percent_pair(tokens: list[tuple[str, list[int]]]) -> list[tuple[str, list[int]]]:
    """Merge adjacent `'phần' + 'trăm'` into `'%'` preserving source word indices."""
    out: list[tuple[str, list[int]]] = []
    i = 0
    while i < len(tokens):
        w, idx = tokens[i]
        if w == "phần" and i + 1 < len(tokens) and tokens[i + 1][0] == "trăm":
            out.append(("%", idx + tokens[i + 1][1]))
            i += 2
        else:
            out.append((w, idx))
            i += 1
    return out


def _merge_number_words(tokens: list[tuple[str, list[int]]]) -> list[tuple[str, list[int]]]:
    """
    Merge maximal Vietnamese number runs into canonical digit strings while guarding
    ambiguous words (`'tư'`, `'lẻ'`, `'linh'`, `'mốt'`, `'lăm'`, `'nhăm'`) at every run/sub-run start.
    """
    out: list[tuple[str, list[int]]] = []
    i = 0
    while i < len(tokens):
        if tokens[i][0] in _NUMBER_VOCAB_START:
            j = i
            while j < len(tokens) and tokens[j][0] in _NUMBER_VOCAB:
                j += 1
            run = tokens[i:j]
            p = 0
            while p < len(run):
                if run[p][0] not in _NUMBER_VOCAB_START:
                    out.append(run[p])
                    p += 1
                    continue
                value, consumed = _parse_number_words([w for w, _ in run[p:]])
                if consumed == 0:
                    out.append(run[p])
                    p += 1
                else:
                    chunk = run[p : p + consumed]
                    merged_idx = [k for _, idx in chunk for k in idx]
                    out.append((str(value), merged_idx))
                    p += consumed
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return out


def _attach_percent(tokens: list[tuple[str, list[int]]]) -> list[tuple[str, list[int]]]:
    """Attach adjacent `<digits> + '%'` (or colloquial `'trăm' + '%'`) into `<digits>%`."""
    out: list[tuple[str, list[int]]] = []
    i = 0
    while i < len(tokens):
        w, idx = tokens[i]
        if _DIGITS_ONLY_RE.match(w) and i + 1 < len(tokens) and tokens[i + 1][0] == "%":
            out.append((w + "%", idx + tokens[i + 1][1]))
            i += 2
        elif w == "trăm" and i + 1 < len(tokens) and tokens[i + 1][0] == "%":
            out.append(("100%", idx + tokens[i + 1][1]))
            i += 2
        else:
            out.append((w, idx))
            i += 1
    return out


def normalize_spoken_vi_tokens(raw_tokens: list[str]) -> list[tuple[str, list[int]]]:
    """
    Normalize a list of Vietnamese/technical whitespace tokens into `(canonical_token, [src_indices])`.
    Converts spoken numbers & percentages (`'hai mươi phần trăm'` -> `'20%'`, `'một trăm'` -> `'100'`,
    `'ba bước'` -> `['3', 'bước']`) while keeping `'đầu tư'`, `'tư duy'`, `'riêng lẻ'` untouched.
    Every input index `0..len(raw_tokens)-1` is preserved in ascending order.
    """
    initial: list[tuple[str, list[int]]] = []
    for i, w in enumerate(raw_tokens):
        cleaned = _clean_num_word(w)
        initial.append((cleaned if cleaned else str(w).strip().lower(), [i]))
    merged = _merge_percent_pair(initial)
    merged = _merge_number_words(merged)
    merged = _attach_percent(merged)
    return merged


def _sliding_rms_db(vo_mono: np.ndarray, sr: int = 16000, win_s: float = 0.02) -> np.ndarray:
    """Compute 20ms sliding-window RMS envelope in dBFS (`20*log10(max(rms, 1e-12))`)."""
    x = np.asarray(vo_mono, dtype=np.float64)
    if x.size == 0:
        return np.empty(0, dtype=np.float64)
    w = max(1, int(round(win_s * sr)))
    sq = x * x
    try:
        from scipy.ndimage import uniform_filter1d

        mean_sq = uniform_filter1d(sq, size=w, mode="constant")
    except Exception:
        pad_l = w // 2
        pad_r = w - 1 - pad_l
        padded = np.pad(sq, (pad_l, pad_r), mode="constant")
        cs = np.concatenate(([0.0], np.cumsum(padded)))
        mean_sq = (cs[w:] - cs[:-w]) / w
    rms = np.sqrt(np.maximum(mean_sq, 0.0))
    return 20.0 * np.log10(np.maximum(rms, 1e-12))


def find_pauses(
    vo_mono: np.ndarray,
    sr: int = 16000,
    rms_win_s: float = 0.02,
    pause_rms_db: float = -35.0,
    pause_min_s: float = 0.12,
    pause_deep_db: float = -45.0,
    pause_deep_min_s: float = 0.06,
) -> list[tuple[float, float]]:
    """
    Ported from `thlib/voice.py` (§5.1):
    Detect silence pauses `[t0, t1]` where 20ms RMS `< -35 dB` continuously for `>= 0.12s`
    with at least `>= 0.06s` below `-45 dB`.
    """
    if vo_mono is None or len(vo_mono) == 0 or sr <= 0:
        return []
    e20 = _sliding_rms_db(vo_mono, sr=sr, win_s=rms_win_s)
    mask = e20 < pause_rms_db
    deep = e20 < pause_deep_db
    d = np.diff(mask.astype(np.int8), prepend=0, append=0)
    starts = np.where(d == 1)[0].tolist()
    ends = np.where(d == -1)[0].tolist()
    pauses: list[tuple[float, float]] = []
    for a, b in zip(starts, ends):
        if (b - a) / sr >= pause_min_s and float(deep[a:b].sum()) / sr >= pause_deep_min_s:
            pauses.append((a / sr, b / sr))
    return pauses


def _correct_onsets_with_mask(
    words: list[Any],
    pauses: list[tuple[float, float]],
    onset_pre_s: float = 0.10,
    onset_post_s: float = 0.05,
    onset_mono_gap_s: float = 0.02,
) -> tuple[list[float], set[int]]:
    """
    Ported from `thlib/voice.py` (`correct_onsets` S04):
    When Whisper places a word's start inside or just after a preceding silence pause
    (`s - 0.10 <= pause_end <= e + 0.05`), snap `word_start` to `pause_end` (1-to-1),
    then enforce monotonic gap `>= onset_mono_gap_s`.
    Supports both `[tok, s, e]` lists and `{'s': s, 'e': e}` dicts.
    """
    if not words:
        return [], set()

    def _se(item: Any) -> tuple[float, float]:
        if isinstance(item, dict):
            return float(item["s"]), float(item["e"])
        return float(item[1]), float(item[2])

    se_list = [_se(w) for w in words]
    on = [s for s, _ in se_list]
    taken: set[int] = set()
    for _, t1 in sorted(pauses, key=lambda p: p[1]):
        for k, (ws, we) in enumerate(se_list):
            if k not in taken and (ws - onset_pre_s) <= t1 <= (we + onset_post_s):
                on[k] = float(t1)
                taken.add(k)
                break
    for k in range(1, len(on)):
        on[k] = max(on[k], on[k - 1] + onset_mono_gap_s)
    return on, taken


def correct_onsets(
    words: list[Any],
    pauses: list[tuple[float, float]],
    onset_pre_s: float = 0.10,
    onset_post_s: float = 0.05,
    onset_mono_gap_s: float = 0.02,
) -> list[float]:
    """Public S04 `correct_onsets` helper returning tightened onset timestamps `list[float]`."""
    on, _ = _correct_onsets_with_mask(
        words,
        pauses,
        onset_pre_s=onset_pre_s,
        onset_post_s=onset_post_s,
        onset_mono_gap_s=onset_mono_gap_s,
    )
    return on


def tighten_raw_words_onsets(
    raw_words: list[list[Any]],
    speech_segments: list[dict[str, Any]] | None,
    pauses: list[tuple[float, float]],
) -> tuple[list[list[Any]], int]:
    """Apply S04 20ms RMS onset tightening directly to Whisper `raw_words` (and `speech_segments`)."""
    if not raw_words or not pauses:
        return raw_words, 0
    new_starts, taken = _correct_onsets_with_mask(raw_words, pauses)
    tightened: list[list[Any]] = []
    for idx, rw in enumerate(raw_words):
        ns = round(new_starts[idx], 4)
        ne = round(max(float(rw[2]), ns + 0.045), 4)
        tightened.append([rw[0], ns, ne])

    if speech_segments:
        cursor = 0
        for seg in speech_segments:
            sw_list = seg.get("words") or []
            n_sw = len(sw_list)
            if n_sw > 0 and cursor + n_sw <= len(tightened):
                seg["words"] = tightened[cursor : cursor + n_sw]
                seg["start"] = tightened[cursor][1]
                seg["end"] = max(float(seg.get("end") or 0.0), tightened[cursor + n_sw - 1][2])
                seg["dur"] = round(max(0.0, float(seg["end"]) - float(seg["start"])), 4)
                cursor += n_sw

    return tightened, len(taken)


def align_words_to_script(
    raw_words: list[list[Any]],
    script_text: str | None,
    total_duration: float,
    slices: list[dict[str, Any]] | None = None,
    pauses: list[tuple[float, float]] | None = None,
) -> list[list[Any]]:
    """
    Align ground-truth Vietnamese/technical tokens onto Whisper word timestamps via SequenceMatcher:
      - Normalizes spoken Vietnamese numbers & percentages (`"hai mươi phần trăm"` <-> `"20%"`,
        `"một trăm"` <-> `"100"`, `"ba bước"` <-> `"3 bước"`, guarding `"tư"`, `"lẻ"`, `"linh"`)
        so multi-word ASR spans `[j1..j2]` lock cleanly onto digit tokens with zero drift.
      - Optional S04 `20ms` RMS onset tightening when `pauses` is supplied.
      - Normalizes 100% to Unicode NFC and enforces Rule C7 `+25ms` slice-seam lock & monotonicity.
    """
    total_end = float(slices[-1]["t1"]) if slices else max(0.1, float(total_duration))

    working_raw = raw_words
    if pauses and working_raw:
        working_raw, _ = tighten_raw_words_onsets(working_raw, None, pauses)

    if script_text:
        clean_sb = nfc(script_text)
        gt_tokens = [clean_gt_token(tok) for tok in clean_sb.split()]
        gt_tokens = [tok for tok in gt_tokens if tok]
    else:
        gt_tokens = []

    if gt_tokens and working_raw:
        gt_canon = normalize_spoken_vi_tokens(gt_tokens)
        asr_canon = normalize_spoken_vi_tokens([str(w[0]) for w in working_raw])
        gt_keys = [_align_key(tok) for tok, _ in gt_canon]
        asr_keys = [_align_key(tok) for tok, _ in asr_canon]

        sm = difflib.SequenceMatcher(None, gt_keys, asr_keys, autojunk=False)
        mapped: list[list[Any]] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    g_idxs = gt_canon[i1 + k][1]
                    a_idxs = asr_canon[j1 + k][1]
                    if len(g_idxs) == len(a_idxs):
                        for g_i, a_j in zip(g_idxs, a_idxs):
                            rw = working_raw[a_j]
                            mapped.append([nfc(gt_tokens[g_i]), float(rw[1]), float(rw[2])])
                    elif len(g_idxs) == 1:
                        t_s = float(working_raw[a_idxs[0]][1])
                        t_e = float(working_raw[a_idxs[-1]][2])
                        mapped.append([nfc(gt_tokens[g_idxs[0]]), t_s, max(t_s + 0.05, t_e)])
                    else:
                        t_s = float(working_raw[a_idxs[0]][1])
                        t_e = max(t_s + 0.08 * len(g_idxs), float(working_raw[a_idxs[-1]][2]))
                        step = (t_e - t_s) / len(g_idxs)
                        for m, g_i in enumerate(g_idxs):
                            mapped.append([nfc(gt_tokens[g_i]), t_s + m * step, t_s + (m + 0.9) * step])
            elif i2 > i1 and j2 > j1:
                g_idxs = [g_i for c_i in range(i1, i2) for g_i in gt_canon[c_i][1]]
                a_idxs = [a_j for c_j in range(j1, j2) for a_j in asr_canon[c_j][1]]
                t_s = float(working_raw[a_idxs[0]][1])
                t_e = max(t_s + 0.08 * len(g_idxs), float(working_raw[a_idxs[-1]][2]))
                step = (t_e - t_s) / len(g_idxs)
                for m, g_i in enumerate(g_idxs):
                    mapped.append([nfc(gt_tokens[g_i]), t_s + m * step, t_s + (m + 0.9) * step])
            elif i2 > i1:
                g_idxs = [g_i for c_i in range(i1, i2) for g_i in gt_canon[c_i][1]]
                prev_e = float(mapped[-1][2]) if mapped else 0.025
                next_a_idx = asr_canon[j1][1][0] if j1 < len(asr_canon) else len(working_raw)
                next_s = float(working_raw[next_a_idx][1]) if next_a_idx < len(working_raw) else (prev_e + 0.22 * len(g_idxs))
                t_s = prev_e + 0.02
                t_e = max(t_s + 0.08 * len(g_idxs), next_s - 0.01)
                step = (t_e - t_s) / len(g_idxs)
                for m, g_i in enumerate(g_idxs):
                    mapped.append([nfc(gt_tokens[g_i]), t_s + m * step, t_s + (m + 0.9) * step])
    elif gt_tokens and not working_raw:
        step = max(0.08, (total_end - 0.05) / max(1, len(gt_tokens)))
        mapped = [
            [nfc(tok), 0.025 + idx * step, min(total_end - 0.02, 0.025 + (idx + 0.9) * step)]
            for idx, tok in enumerate(gt_tokens)
        ]
    else:
        mapped = []
        for rw in working_raw:
            tok = clean_gt_token(str(rw[0]))
            if not tok:
                tok = nfc(str(rw[0])).strip()
            if tok:
                mapped.append([nfc(tok), float(rw[1]), float(rw[2])])

    snapped_mapped_indices: set[int] = set()
    if pauses and mapped:
        snapped_starts, snapped_mapped_indices = _correct_onsets_with_mask(mapped, pauses)
        for idx in range(len(mapped)):
            ns = snapped_starts[idx]
            mapped[idx][1] = ns
            mapped[idx][2] = max(float(mapped[idx][2]), ns + 0.045)

    slice_starts = [float(s["t0"]) for s in slices] if slices else []
    words_tl: list[list[Any]] = []
    n_tot = len(mapped)

    for idx, (tok, ws, we) in enumerate(mapped):
        min_start = 0.025 if slices else 0.02
        ws_c = max(min_start, min(float(ws), max(min_start, total_end - (n_tot - idx) * 0.062)))

        if slice_starts:
            for st0 in slice_starts:
                if st0 - 0.11 <= ws_c < st0 + 0.025:
                    # Clamp slice-seam smear to +25ms after slice start so Rule C7 cut_lead never smears backwards
                    ws_c = st0 + 0.025
                    break
                elif (
                    idx not in snapped_mapped_indices
                    and not pauses
                    and st0 + 0.025 <= ws_c <= st0 + 0.15
                    and (ws_c - st0) > 0.085
                ):
                    ws_c = st0 + 0.045
                    break

        if words_tl and ws_c < float(words_tl[-1][1]) + 0.058:
            ws_c = min(max(min_start, total_end - 0.04), float(words_tl[-1][1]) + 0.058)
            # Keep previous word end from overlapping badly across a slice boundary
            if words_tl[-1][2] > ws_c:
                words_tl[-1][2] = round(max(float(words_tl[-1][1]) + 0.04, ws_c - 0.005), 4)

        we_c = max(ws_c + 0.050, min(float(we), max(ws_c + 0.050, total_end - 0.02)))
        words_tl.append([nfc(tok), round(ws_c, 4), round(we_c, 4)])

    return words_tl


# ---------------------------------------------------------------------------
# 2-Speed Asymmetric Phrase Cadence & J/L-Cut Planner (v5.2)
# ---------------------------------------------------------------------------

_CHAPTER_PIVOT_PHRASES: frozenset[str] = frozenset(
    {
        "nhưng mà",
        "tuy nhiên",
        "ngược lại",
        "trái lại",
        "thực ra",
        "sự thật",
        "vấn đề",
        "sai lầm",
        "tóm lại",
        "nói tóm",
        "kết luận",
        "cuối cùng",
        "quan trọng",
        "bí quyết",
        "giải pháp",
        "nếu bạn",
        "thứ nhất",
        "đầu tiên",
        "bước 1",
        "bước một",
        "bước đầu",
        "phần 1",
        "phần một",
        "vậy thì",
        "vậy nên",
    }
)
_CHAPTER_PIVOT_SINGLE: frozenset[str] = frozenset({"nhưng"})

_FAST_CHAIN_PHRASES: frozenset[str] = frozenset(
    {
        "đó là",
        "chính là",
        "tức là",
        "nghĩa là",
        "thứ hai",
        "thứ ba",
        "thứ tư",
        "thứ năm",
        "thứ 2",
        "thứ 3",
        "thứ 4",
        "bước 2",
        "bước hai",
        "bước 3",
        "bước ba",
        "bước 4",
        "bước bốn",
        "bước tiếp",
        "tiếp theo",
        "kế tiếp",
        "ví dụ",
        "chẳng hạn",
        "cụ thể",
        "vì vậy",
        "cho nên",
        "do đó",
        "hơn nữa",
        "chưa hết",
        "đặc biệt",
        "không chỉ",
        "mà còn",
        "một là",
        "hai là",
        "ba là",
        "số 1",
        "số 2",
        "số 3",
    }
)
_FAST_CHAIN_SINGLE: frozenset[str] = frozenset({"bước"})

_NATURAL_CLAUSE_OPENERS: frozenset[str] = frozenset(
    {"khi", "vì", "bởi", "để", "mà", "thì", "hoặc", "hay", "nếu", "sau", "trước"}
)


@functools.lru_cache(maxsize=1)
def _load_text_vi_lexicon() -> dict[str, set[str]]:
    """Load `data/text_vi.json` Vietnamese prosody & glued-compound lexicon (cached)."""
    default_lex: dict[str, set[str]] = {
        "leads": {"và", "với", "của", "cho", "trong", "trên", "từ", "để", "khi", "nếu", "nhưng"},
        "trails": {"ạ", "nhé", "nha", "thôi", "nữa", "đâu", "lắm", "hơn", "nhất"},
        "units": {"bước", "thứ", "phần", "cách", "lỗi", "giây", "phút", "ngày", "lần"},
        "cta_verbs": {"bình luận", "comment", "gõ", "hashtag", "nhắn"},
        "pairs": set(),
    }
    if not TEXT_VI_JSON.is_file():
        return default_lex
    try:
        raw = json.loads(TEXT_VI_JSON.read_text(encoding="utf-8"))
        return {
            "leads": {nfc(x).lower() for x in raw.get("leads", [])},
            "trails": {nfc(x).lower() for x in raw.get("trails", [])},
            "units": {nfc(x).lower() for x in raw.get("units", [])},
            "cta_verbs": {nfc(x).lower() for x in raw.get("cta_verbs", [])},
            "pairs": {nfc(x).lower() for x in raw.get("pairs", [])},
        }
    except Exception:
        return default_lex


def extract_words_list(words_tl_or_doc: Any) -> list[list[Any]]:
    """
    Extract canonical `[[word, t0, t1], ...]` list from either a `v5.2` `words_tl.json` dict
    (`{"words": [...], "cadence_and_jcut_plan": ...}`) or a legacy `v5.1` list.
    """
    if isinstance(words_tl_or_doc, dict):
        seq = words_tl_or_doc.get("words")
        if seq is None:
            seq = words_tl_or_doc.get("words_tl") or []
    elif isinstance(words_tl_or_doc, (list, tuple)):
        seq = words_tl_or_doc
    else:
        return []
    out: list[list[Any]] = []
    for item in seq:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            out.append([nfc(str(item[0])), float(item[1]), float(item[2])])
        elif isinstance(item, dict) and "word" in item:
            out.append([nfc(str(item["word"])), float(item["s"]), float(item["e"])])
    return out


def _clean_marker_tok(tok: str) -> str:
    return nfc(tok).lower().strip(" ,.;:!?\"'()[]{}«»“”‘’…—–-")


def _extract_script_punct_after_word(words: list[list[Any]], script_text: str | None) -> dict[int, str]:
    """Map word index `i` -> trailing punctuation (`'.'`, `'?'`, `'!'`, `','`, `':'`, `';'`) from `script_text` or raw token."""
    punct_map: dict[int, str] = {}
    for idx, w in enumerate(words):
        raw_t = str(w[0]).strip()
        if raw_t and raw_t[-1] in ".?!,:;…":
            punct_map[idx] = raw_t[-1]

    if not script_text or not words:
        return punct_map

    raw_scr_tokens = [t for t in nfc(script_text).split() if t]
    scr_keys = [_align_key(clean_gt_token(t)) for t in raw_scr_tokens]
    w_keys = [_align_key(str(w[0])) for w in words]
    sm = difflib.SequenceMatcher(None, w_keys, scr_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                st = raw_scr_tokens[j1 + k].rstrip("\"'”’)]}")
                if st and st[-1] in ".?!,:;…—":
                    punct_map[i1 + k] = st[-1]
    return punct_map


def _normalize_pause_list(
    pauses: Sequence[Any] | None,
    words: list[list[Any]],
) -> list[dict[str, float]]:
    """Merge explicit acoustic silence pauses with observed inter-word gaps >= 95ms."""
    merged: list[tuple[float, float]] = []
    for p in pauses or ():
        if isinstance(p, dict) and "start" in p and "end" in p:
            s, e = float(p["start"]), float(p["end"])
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            s, e = float(p[0]), float(p[1])
        else:
            continue
        if e > s + 0.015:
            merged.append((s, e))

    for i in range(len(words) - 1):
        e_prev = float(words[i][2])
        s_next = float(words[i + 1][1])
        if s_next - e_prev >= 0.095:
            # Avoid duplicating an overlapping acoustic pause
            if not any(abs(s_next - pe) <= 0.055 or (ps <= e_prev + 0.03 and pe >= s_next - 0.03) for ps, pe in merged):
                merged.append((e_prev, s_next))

    merged.sort(key=lambda iv: (iv[0], iv[1]))
    return [
        {"start": round(s, 4), "end": round(e, 4), "dur": round(max(0.0, e - s), 4)}
        for s, e in merged
    ]


def build_cadence_and_jcut_plan(
    words_tl: Any,
    pauses: Sequence[Any] | None = None,
    slices: Sequence[dict[str, Any]] | None = None,
    fps: int = 30,
    script_text: str | None = None,
) -> dict[str, Any]:
    """
    2-Speed Asymmetric Phrase Cadence & J/L-Cut Planner (`v5.2`):
      - Analyzes inter-word/inter-clause pauses, slice seams, and `text_vi.json` linguistic markers
        (`"nhưng"`, `"đó là"`, `"bước"`, `"thứ nhất"`, `"thứ hai"`, `"thứ ba"`, `"nếu bạn"`, `"tóm lại"`, ...).
      - Classifies each cut/pause boundary into:
          * `"fast_chain"`     : target gap `45–70ms` (rapid enumeration or tight causal follow-up)
          * `"chapter_pivot"`  : target breath `220–300ms` (major structural turn where BGM/pre-swoosh breathes)
          * `"natural_clause"` : target gap `110–160ms` (conversational clause boundary)
      - Recommends `j_cut_visual_lead_ms` (`120–165ms` before speech onset when switching to B-roll/card)
        and `audio_crossfade_ms` (`28–40ms` equal-power speech splice).
    """
    words = extract_words_list(words_tl)
    lex = _load_text_vi_lexicon()
    punct_after = _extract_script_punct_after_word(words, script_text)
    norm_pauses = _normalize_pause_list(pauses, words)

    slice_seams = sorted(
        {round(float(s["t0"]), 4) for s in (slices or ()) if float(s.get("t0") or 0.0) > 0.03}
    )

    # Map each acoustic pause 1-to-1 onto the single closest inter-word boundary
    pause_by_boundary: dict[int, float] = {}
    if len(words) >= 2 and norm_pauses:
        for p_rec in norm_pauses:
            ps, pe, pdur = float(p_rec["start"]), float(p_rec["end"]), float(p_rec["dur"])
            best_i = -1
            best_dist = 0.085
            for bi in range(len(words) - 1):
                ep = float(words[bi][2])
                sn = float(words[bi + 1][1])
                ov = min(sn, pe) - max(ep, ps)
                dist = 0.0 if ov > 0.01 else min(abs(sn - pe), abs(ep - ps))
                if dist < best_dist:
                    best_dist = dist
                    best_i = bi
            if best_i >= 0:
                pause_by_boundary[best_i] = max(pause_by_boundary.get(best_i, 0.0), pdur)

    boundaries: list[dict[str, Any]] = []
    words_since_break = 0

    for i in range(len(words) - 1):
        words_since_break += 1
        tok_prev = str(words[i][0])
        tok_next = str(words[i + 1][0])
        tok_next2 = str(words[i + 2][0]) if (i + 2) < len(words) else ""
        e_prev = float(words[i][2])
        s_next = float(words[i + 1][1])

        w_prev_l = _clean_marker_tok(tok_prev)
        w_next_l = _clean_marker_tok(tok_next)
        w_next2_l = _clean_marker_tok(tok_next2)
        bigram_next = f"{w_next_l} {w_next2_l}".strip()
        bigram_cross = f"{w_prev_l} {w_next_l}".strip()

        # Measure acoustic pause or inter-word gap at boundary i -> i+1
        raw_gap_s = max(0.0, s_next - e_prev)
        matched_pause_dur_s = pause_by_boundary.get(i, 0.0)
        gap_ms = max(raw_gap_s, matched_pause_dur_s) * 1000.0

        is_seam = any((e_prev - 0.08) <= st0 <= (s_next + 0.06) for st0 in slice_seams)
        p_mark = punct_after.get(i, "")
        is_glued = bigram_cross in lex["pairs"]
        has_p_sentence = bool(p_mark) and (p_mark in ".?!")
        has_p_any = bool(p_mark) and (p_mark in ".?!,:;…—")
        prev_is_dangling_lead = (w_prev_l in lex["leads"]) and (gap_ms < 165.0) and not is_seam and not has_p_sentence

        # Identify explicit Vietnamese discourse markers at the incoming phrase head
        is_cta_head = (
            (bigram_next in lex["cta_verbs"] or w_next_l in lex["cta_verbs"])
            and i >= int(len(words) * 0.65)
        )
        is_chapter_marker = (
            bigram_next in _CHAPTER_PIVOT_PHRASES
            or w_next_l in _CHAPTER_PIVOT_SINGLE
            or is_cta_head
        )
        is_fast_marker = (
            bigram_next in _FAST_CHAIN_PHRASES
            or (w_next_l in _FAST_CHAIN_SINGLE and bigram_next not in _CHAPTER_PIVOT_PHRASES)
        )
        is_clause_marker = (
            w_next_l in _NATURAL_CLAUSE_OPENERS
            and not is_chapter_marker
            and not is_fast_marker
            and words_since_break >= 3
        )
        prev_prev_l = _clean_marker_tok(str(words[i - 1][0])) if i > 0 else ""
        prev_has_trail = (w_prev_l in lex["trails"]) and not (prev_prev_l == "thứ" and w_prev_l == "nhất")

        # Guard glued compound words unless there is an explicit pause / slice seam / full stop
        if (is_glued or prev_is_dangling_lead) and gap_ms < 150.0 and not is_seam and not has_p_sentence:
            continue

        has_boundary_signal = (
            is_chapter_marker
            or is_fast_marker
            or is_seam
            or has_p_any
            or gap_ms >= 68.0
            or (prev_has_trail and words_since_break >= 4 and gap_ms >= 48.0)
            or (is_clause_marker and gap_ms >= 42.0)
        )
        if not has_boundary_signal:
            continue

        # Classify strictly into {"chapter_pivot", "fast_chain", "natural_clause"}
        if is_chapter_marker:
            cadence_cls = "chapter_pivot"
            if bigram_next in _CHAPTER_PIVOT_PHRASES:
                marker = bigram_next
            elif is_cta_head:
                marker = f"cta:{bigram_next if bigram_next in lex['cta_verbs'] else w_next_l}"
            else:
                marker = w_next_l
            # Stronger structural breath for thesis conclusions ("tóm lại", "nhưng", "kết luận")
            heavy_turn = marker in {"tóm lại", "nói tóm", "kết luận", "cuối cùng", "nhưng", "nhưng mà", "tuy nhiên", "sự thật"}
            target_gap_ms = 275 if (heavy_turn or has_p_sentence) else 240
            target_range = [220, 300]
            j_lead_ms = 160 if heavy_turn else 148
            l_trail_ms = 125
            xfade_ms = 38
        elif is_fast_marker:
            cadence_cls = "fast_chain"
            marker = bigram_next if bigram_next in _FAST_CHAIN_PHRASES else w_next_l
            target_gap_ms = 55 if marker in {"đó là", "chính là", "tức là"} else 62
            target_range = [45, 70]
            j_lead_ms = 125
            l_trail_ms = 75
            xfade_ms = 30
        elif gap_ms >= 255.0 or (has_p_sentence and gap_ms >= 185.0 and words_since_break >= 5):
            cadence_cls = "chapter_pivot"
            marker = f"sentence_breath({p_mark or 'pause'})"
            target_gap_ms = int(round(min(300.0, max(220.0, min(gap_ms * 0.85, 285.0)))))
            target_range = [220, 300]
            j_lead_ms = 155
            l_trail_ms = 120
            xfade_ms = 38
        elif not is_clause_marker and gap_ms < 108.0 and (
            (p_mark == "," and words_since_break <= 4)
            or (words_since_break <= 5 and not is_seam)
            or (w_prev_l in lex["units"])
        ):
            cadence_cls = "fast_chain"
            marker = "rapid_enumeration_clause" if p_mark == "," else "tight_followup"
            target_gap_ms = int(round(min(70.0, max(45.0, 58.0))))
            target_range = [45, 70]
            j_lead_ms = 126
            l_trail_ms = 75
            xfade_ms = 30
        else:
            cadence_cls = "natural_clause"
            marker = (
                f"conjunction:{w_next_l}"
                if w_next_l in _NATURAL_CLAUSE_OPENERS
                else ("slice_seam" if is_seam else (f"punct:{p_mark}" if p_mark else "clause_pause"))
            )
            target_gap_ms = int(round(min(160.0, max(110.0, 135.0 if gap_ms < 110.0 else min(155.0, gap_ms * 0.88)))))
            target_range = [110, 160]
            j_lead_ms = 140
            l_trail_ms = 95
            xfade_ms = 34

        # Snap J-cut visual timestamp cleanly onto editing grid while keeping >= 0.0
        fps_safe = max(24, int(fps or 30))
        raw_jcut_s = max(0.0, s_next - (j_lead_ms / 1000.0))
        snapped_jcut_s = round(round(raw_jcut_s * fps_safe) / float(fps_safe), 4)

        boundaries.append(
            {
                "boundary_index": len(boundaries),
                "after_word_index": i,
                "before_word_index": i + 1,
                "prev_word": tok_prev,
                "next_word": tok_next,
                "prev_end_s": round(e_prev, 4),
                "next_start_s": round(s_next, 4),
                "observed_gap_ms": round(gap_ms, 1),
                "cadence_class": cadence_cls,
                "matched_marker": marker,
                "target_gap_ms": int(target_gap_ms),
                "target_gap_range_ms": target_range,
                "recommended_trim_delta_ms": round(float(target_gap_ms) - gap_ms, 1),
                "j_cut_visual_lead_ms": int(j_lead_ms),
                "j_cut_visual_cut_at_s": snapped_jcut_s,
                "l_cut_audio_trail_ms": int(l_trail_ms),
                "audio_crossfade_ms": int(xfade_ms),
                "is_slice_seam": bool(is_seam),
            }
        )
        words_since_break = 0

    n_fast = sum(1 for b in boundaries if b["cadence_class"] == "fast_chain")
    n_nat = sum(1 for b in boundaries if b["cadence_class"] == "natural_clause")
    n_piv = sum(1 for b in boundaries if b["cadence_class"] == "chapter_pivot")
    saved_ms = round(
        sum(max(0.0, float(b["observed_gap_ms"]) - float(b["target_gap_ms"])) for b in boundaries),
        1,
    )

    vocal_jcuts = plan_true_vocal_jcuts(
        words,
        boundaries=boundaries,
        fps=int(fps or 30),
    )

    return {
        "version": VERSION,
        "policy": "2_speed_asymmetric_cadence_and_true_vocal_jcut",
        "fps": int(fps or 30),
        "targets_ms": {
            "fast_chain": [45, 70],
            "natural_clause": [110, 160],
            "chapter_pivot": [220, 300],
            "j_cut_visual_lead_ms": [120, 165],
            "vocal_jcut_lead_ms": [240, 550],
            "audio_crossfade_ms": [28, 40],
        },
        "summary": {
            "boundary_count": len(boundaries),
            "fast_chain_count": n_fast,
            "natural_clause_count": n_nat,
            "chapter_pivot_count": n_piv,
            "vocal_jcut_candidate_count": len(vocal_jcuts),
            "recommended_default_j_cut_visual_lead_ms": 140,
            "recommended_default_vocal_jcut_lead_ms": 320,
            "recommended_default_audio_crossfade_ms": 34,
            "estimated_tightening_saved_ms": saved_ms,
        },
        "boundaries": boundaries,
        "vocal_jcut_candidates": vocal_jcuts,
    }


_VOCAL_JCUT_UNSTRESSED_PARTICLES: frozenset[str] = frozenset(
    {
        "là",
        "mà",
        "thì",
        "của",
        "và",
        "với",
        "cho",
        "trong",
        "trên",
        "từ",
        "để",
        "khi",
        "nếu",
        "nhưng",
        "vì",
        "bởi",
        "những",
        "các",
        "một",
        "cái",
        "việc",
        "sự",
        "đã",
        "đang",
        "sẽ",
        "rất",
        "cũng",
    }
)


def plan_true_vocal_jcuts(
    words_tl: Any,
    boundaries: Sequence[dict[str, Any]] | None = None,
    fps: int = 30,
    duration_sec: float | None = None,
    min_spacing_s: float = 1.15,
) -> list[dict[str, Any]]:
    """
    True Vocal `J-Cut` Candidate Planner (`v6.0.0` @__dviet Era-2 `7707653827016674580`):
      - Identifies major clause/chapter onsets where incoming speech starts **`240–550ms` BEFORE**
        the `0`-frame visual Hard Cut (`t_visual_cut ≈ t_word_onset + 0.32s`).
      - Snaps `t_visual_cut` onto the stressed content noun/verb onset inside
        `[t_word_onset + 0.240s, t_word_onset + 0.550s]` on the `fps` editing grid so the visual
        cut lands right on the semantic punch word while incoming voice leads smoothly ahead!
    """
    words = extract_words_list(words_tl)
    if len(words) < 3:
        return []

    fps_safe = max(24, int(fps or 30))
    total_end = (
        float(duration_sec)
        if (duration_sec is not None and duration_sec > 0.0)
        else float(words[-1][2]) + 0.08
    )

    if boundaries is None:
        base_plan = build_cadence_and_jcut_plan(words, fps=fps_safe)
        return list(base_plan.get("vocal_jcut_candidates") or [])

    major_fast_markers = {
        "thứ hai",
        "thứ ba",
        "thứ tư",
        "thứ 2",
        "thứ 3",
        "thứ 4",
        "bước 2",
        "bước hai",
        "bước 3",
        "bước ba",
        "ví dụ",
        "đặc biệt",
        "cụ thể",
    }

    raw_candidates: list[dict[str, Any]] = []
    for b_pos, b in enumerate(boundaries):
        idx0 = int(b.get("before_word_index", -1))
        if idx0 < 1 or idx0 >= len(words):
            continue

        cad_cls = str(b.get("cadence_class") or "")
        marker = str(b.get("matched_marker") or "")
        gap_ms = float(b.get("observed_gap_ms") or 0.0)
        is_seam = bool(b.get("is_slice_seam"))

        # Determine next boundary word index to verify incoming clause length
        next_b_word_idx = (
            int(boundaries[b_pos + 1]["before_word_index"])
            if (b_pos + 1) < len(boundaries)
            else len(words)
        )
        clause_word_len = next_b_word_idx - idx0

        is_major_onset = (
            cad_cls == "chapter_pivot"
            or (cad_cls == "natural_clause" and (gap_ms >= 105.0 or is_seam or clause_word_len >= 4))
            or (cad_cls == "fast_chain" and marker in major_fast_markers and clause_word_len >= 3)
        )
        if not is_major_onset:
            continue

        t_onset = float(words[idx0][1])
        # Require enough trailing room after onset so visual cut at +240..550ms lands cleanly inside the shot
        if total_end - t_onset < 0.58:
            continue

        win_lo = t_onset + 0.240
        win_hi = min(total_end - 0.05, t_onset + 0.550)
        if win_hi < win_lo:
            continue

        # Search lookahead words [idx0 + 1 .. idx0 + 5] for the stressed content noun/verb inside [240ms, 550ms]
        best_word_idx = min(len(words) - 1, idx0 + 1)
        best_score = -1e9
        best_ws: float | None = None

        for k in range(idx0 + 1, min(len(words), idx0 + 6)):
            wk_tok = _clean_marker_tok(str(words[k][0]))
            ws_k = float(words[k][1])
            we_k = float(words[k][2])
            lead_s = ws_k - t_onset
            if lead_s < 0.215:
                continue
            if lead_s > 0.575:
                break

            is_content = wk_tok not in _VOCAL_JCUT_UNSTRESSED_PARTICLES and len(wk_tok) >= 2
            dur_bonus = min(0.28, max(0.0, we_k - ws_k)) * 1.8
            sweet_prox = 1.0 - abs(lead_s - 0.320) / 0.320
            in_strict_window = 1.0 if (0.240 <= lead_s <= 0.550) else 0.35
            score = (1.6 if is_content else 0.4) + dur_bonus + 0.75 * sweet_prox + in_strict_window
            if score > best_score:
                best_score = score
                best_word_idx = k
                best_ws = ws_k

        raw_vis = best_ws if best_ws is not None else (t_onset + 0.320)
        # Snap to editing frame grid while enforcing strict [240ms, 550ms] vocal J-cut window
        min_frame = int(math.ceil((t_onset + 0.240 - 1e-9) * fps_safe))
        max_frame = int(math.floor((min(total_end - 0.04, t_onset + 0.550) + 1e-9) * fps_safe))
        if max_frame < min_frame:
            snapped_vis = round(min(total_end - 0.04, max(t_onset + 0.240, raw_vis)), 4)
        else:
            ideal_frame = int(round(raw_vis * fps_safe))
            clamped_frame = max(min_frame, min(max_frame, ideal_frame))
            snapped_vis = round(clamped_frame / float(fps_safe), 4)

        lead_ms = int(round((snapped_vis - t_onset) * 1000.0))
        lead_ms = max(240, min(550, lead_ms))

        priority = (
            3 if cad_cls == "chapter_pivot" else (2 if is_seam or gap_ms >= 150.0 else 1)
        )
        raw_candidates.append(
            {
                "_priority": priority,
                "boundary_index": int(b.get("boundary_index", b_pos)),
                "onset_word_index": idx0,
                "onset_word": str(words[idx0][0]),
                "stressed_word_index": int(best_word_idx),
                "stressed_word": str(words[best_word_idx][0]),
                "cadence_class": cad_cls,
                "matched_marker": marker,
                "t_word_onset": round(t_onset, 4),
                "t_audio_onset_s": round(t_onset, 4),
                "t_visual_cut": snapped_vis,
                "t_visual_cut_s": snapped_vis,
                "vocal_lead_ms": lead_ms,
                "visual_cut_transition_frames": 0,
                "audio_crossfade_ms": int(b.get("audio_crossfade_ms", 34)),
            }
        )

    # Space out candidates by `min_spacing_s`, preferring higher-priority chapter pivots
    selected: list[dict[str, Any]] = []
    for cand in raw_candidates:
        if not selected:
            selected.append(cand)
            continue
        prev = selected[-1]
        if cand["t_word_onset"] - prev["t_word_onset"] >= float(min_spacing_s):
            selected.append(cand)
        elif cand["_priority"] > prev["_priority"]:
            selected[-1] = cand

    out_list: list[dict[str, Any]] = []
    for c_i, cand in enumerate(selected):
        rec = {k: v for k, v in cand.items() if k != "_priority"}
        rec["candidate_index"] = c_i
        out_list.append(rec)
    return out_list


def build_words_tl_document(
    words_tl: list[list[Any]],
    *,
    pauses: Sequence[Any] | None = None,
    rms_pauses_20ms: Sequence[tuple[float, float]] | None = None,
    face_metrics: dict[str, Any] | None = None,
    tier: str = "full",
    fps: int = 30,
    fps_num: float | None = None,
    duration_sec: float = 0.0,
    slices: list[dict[str, Any]] | None = None,
    script_text: str | None = None,
    cadence_plan: dict[str, Any] | None = None,
    gesture_action_peaks_s: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Construct the canonical `v6.0.0` `words_tl.json` payload preserving all `v5.1`/`v5.2` fields
    (`words`, `words_tl`, `pauses`, `face_metrics`, `tier`, `fps`, `duration_sec`, `slices`,
    `cadence_and_jcut_plan`) while embedding `gesture_action_peaks_s` and `vocal_jcut_candidates`.
    """
    norm_pauses = _normalize_pause_list(pauses or rms_pauses_20ms, words_tl)
    plan = (
        cadence_plan
        if cadence_plan is not None
        else build_cadence_and_jcut_plan(
            words_tl,
            pauses=norm_pauses,
            slices=slices,
            fps=fps,
            script_text=script_text,
        )
    )
    if "vocal_jcut_candidates" not in plan:
        plan["vocal_jcut_candidates"] = plan_true_vocal_jcuts(
            words_tl,
            boundaries=plan.get("boundaries"),
            fps=fps,
            duration_sec=duration_sec if duration_sec > 0.0 else None,
        )
    return {
        "version": VERSION,
        "tier": tier,
        "fps": int(fps),
        "fps_num": round(float(fps_num if fps_num is not None else fps), 4),
        "duration_sec": round(float(duration_sec), 6),
        "word_count": len(words_tl),
        "words": words_tl,
        "words_tl": words_tl,
        "pauses": norm_pauses,
        "rms_pauses_20ms": [
            [round(float(a), 4), round(float(b), 4)] for a, b in (rms_pauses_20ms or ())
        ],
        "face_metrics": face_metrics if face_metrics is not None else {},
        "gesture_action_peaks_s": list(gesture_action_peaks_s or []),
        "slices": slices if slices is not None else [],
        "cadence_and_jcut_plan": plan,
    }


# ---------------------------------------------------------------------------
# Parallel Media Probing, Loudness & Silence Detection
# ---------------------------------------------------------------------------


def classify_media_file(path: Path, base_dir: Path | None = None) -> str:
    """Classify a media file objectively by directory structure and filename pattern."""
    ext = path.suffix.lower()
    rel_parts = [p.lower() for p in (path.relative_to(base_dir).parts if base_dir and path.is_relative_to(base_dir) else path.parts)]
    stem_l = path.stem.lower()

    if "voice" in rel_parts or stem_l.startswith("voice_") or "_voice" in stem_l or stem_l.startswith("vo_"):
        return "voice"
    if "bgm" in rel_parts or stem_l.startswith("bgm") or "music" in rel_parts:
        return "bgm"
    if "sfx" in rel_parts or stem_l.startswith("sfx"):
        return "sfx"
    if "overlays" in rel_parts or stem_l.startswith("ovl_") or "overlay" in stem_l:
        return "overlays" if ext in VIDEO_EXTS else "gfx"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "gfx"
    return "other"


def probe_single_media(path: Path, base_dir: Path | None = None) -> tuple[str, dict[str, Any]]:
    """Run ffprobe (or PIL for images) on a single file and return normalized metadata."""
    key = str(path.relative_to(base_dir)) if (base_dir and path.is_relative_to(base_dir)) else path.name
    category = classify_media_file(path, base_dir)
    ext = path.suffix.lower()
    size_bytes = path.stat().st_size if path.exists() else 0

    if ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                w, h = im.size
                mode = im.mode
                has_alpha = "A" in mode or ("transparency" in im.info)
        except Exception:
            w, h, mode, has_alpha = None, None, None, False
        return key, {
            "dur": 0.0,
            "w": w,
            "h": h,
            "fps": "0/0",
            "fps_num": 0.0,
            "category": category,
            "video_codec": ext.lstrip(".").upper(),
            "pix_fmt": mode,
            "has_alpha": has_alpha,
            "has_video": True,
            "has_audio": False,
            "size_bytes": size_bytes,
        }

    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout) if proc.stdout else {}
    fmt = data.get("format") or {}
    streams = data.get("streams") or []

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    dur_str = (
        fmt.get("duration")
        or (v_stream or {}).get("duration")
        or (a_stream or {}).get("duration")
        or "0.0"
    )
    try:
        dur = round(float(dur_str), 6)
    except ValueError:
        dur = 0.0

    fps_rat = (v_stream or {}).get("avg_frame_rate") or (v_stream or {}).get("r_frame_rate") or "0/0"
    if fps_rat in ("0/0", "0", None) and v_stream:
        fps_rat = v_stream.get("r_frame_rate") or "0/0"
    fps_num = parse_rational_fps(fps_rat, fallback=0.0) if v_stream else 0.0

    color_transfer = (v_stream or {}).get("color_transfer")
    color_primaries = (v_stream or {}).get("color_primaries")
    color_space = (v_stream or {}).get("color_space")
    color_range = (v_stream or {}).get("color_range")
    pix_fmt = (v_stream or {}).get("pix_fmt")
    is_hdr = bool(
        (color_transfer and color_transfer.lower() in {"arib-std-b67", "smpte2084"})
        or (color_primaries and "2020" in color_primaries.lower())
    )

    sample_rate = int(a_stream["sample_rate"]) if a_stream and a_stream.get("sample_rate") else None
    channels = int(a_stream["channels"]) if a_stream and a_stream.get("channels") else None

    info: dict[str, Any] = {
        "dur": dur,
        "w": (v_stream or {}).get("width"),
        "h": (v_stream or {}).get("height"),
        "fps": fps_rat if v_stream else "0/0",
        "fps_num": fps_num,
        "category": category,
        "has_video": v_stream is not None,
        "video_codec": (v_stream or {}).get("codec_name"),
        "pix_fmt": pix_fmt,
        "color_space": color_space,
        "color_transfer": color_transfer,
        "color_primaries": color_primaries,
        "color_range": color_range,
        "is_hdr": is_hdr,
        "has_audio": a_stream is not None,
        "audio_codec": (a_stream or {}).get("codec_name"),
        "sample_rate": sample_rate,
        "channels": channels,
        "size_bytes": size_bytes,
    }
    return key, info


def probe_media_files(
    files: list[Path],
    base_dir: Path | None = None,
    max_workers: int = 12,
) -> dict[str, dict[str, Any]]:
    """Run 12-thread ffprobe/PIL probe across a list of media files."""
    if not files:
        return {}
    workers = min(max_workers, max(1, len(files)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda p: probe_single_media(p, base_dir), files))
    return dict(sorted(results, key=lambda kv: kv[0]))


def measure_audio_lufs_and_silences(
    media_path: Path,
    duration_sec: float,
    silence_db: float = -36.0,
    silence_min_dur: float = 0.28,
    pad_sec: float = 0.045,
) -> dict[str, Any]:
    """
    Single-pass FFmpeg audio telemetry:
      - `silencedetect=noise=-36dB:d=0.28` -> silence intervals, natural cut candidates, keep segments
      - `ebur128=peak=true` -> integrated LUFS, LRA, true peak dBTP
    """
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(media_path),
            "-vn",
            "-af",
            f"silencedetect=noise={silence_db}dB:d={silence_min_dur},ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")

    starts = [float(x) for x in re.findall(r"silence_start:\s*([-\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([-\d.]+)", log)]
    if len(starts) > len(ends) and duration_sec > 0:
        ends.append(duration_sec)

    silences: list[dict[str, float]] = []
    cut_candidates: list[dict[str, float]] = []
    for s_raw, e_raw in zip(starts, ends):
        s = round(max(0.0, s_raw), 4)
        e = round(min(duration_sec, max(s, e_raw)), 4) if duration_sec > 0 else round(max(s, e_raw), 4)
        d = round(e - s, 4)
        if d >= silence_min_dur - 0.02:
            silences.append({"start": s, "end": e, "dur": d})
            mid = round((s + e) * 0.5, 4)
            cut_candidates.append({
                "t": mid,
                "silence_start": s,
                "silence_end": e,
                "silence_dur": d,
            })

    # Speech / non-silent keep segments padded gently so consonants are preserved
    keep_segments: list[dict[str, float]] = []
    cursor = 0.0
    for sil in silences:
        seg_end = min(duration_sec, sil["start"] + pad_sec)
        if seg_end - cursor > 0.12:
            keep_segments.append({
                "start": round(cursor, 4),
                "end": round(seg_end, 4),
                "dur": round(seg_end - cursor, 4),
            })
        cursor = max(cursor, sil["end"] - pad_sec)
    if duration_sec - cursor > 0.12:
        keep_segments.append({
            "start": round(cursor, 4),
            "end": round(duration_sec, 4),
            "dur": round(duration_sec - cursor, 4),
        })

    # Parse Summary block from ebur128
    summary_idx = log.rfind("Summary:")
    summary_txt = log[summary_idx:] if summary_idx != -1 else log
    m_i = re.search(r"I:\s*([-\d.]+)\s*LUFS", summary_txt)
    m_lra = re.search(r"LRA:\s*([-\d.]+)\s*LU", summary_txt)
    m_tp = re.search(r"Peak:\s*([-\d.]+)\s*dBFS", summary_txt)

    return {
        "integrated_lufs": round(float(m_i.group(1)), 2) if m_i else None,
        "lra_lu": round(float(m_lra.group(1)), 2) if m_lra else None,
        "true_peak_dbtp": round(float(m_tp.group(1)), 2) if m_tp else None,
        "silence_threshold_db": silence_db,
        "silence_min_dur_sec": silence_min_dur,
        "silences": silences,
        "natural_cut_candidates": cut_candidates,
        "keep_segments": keep_segments,
    }


# ---------------------------------------------------------------------------
# Haar Frontal-Face Detector + Subject Framing & B-Roll Quality Audit (v5.1)
# ---------------------------------------------------------------------------


class _HaarCascade(NamedTuple):
    """Parsed OpenCV stump-based Haar XML cascade for pure-NumPy Viola-Jones evaluation."""
    win: int
    feats: list[list[tuple[int, int, int, int, float]]]
    stages: list[tuple[float, list[tuple[int, float, float, float]]]]


@functools.lru_cache(maxsize=2)
def _load_haar_cascade_xml(path_str: str) -> _HaarCascade:
    """Ported from `thlib/face.py`: load OpenCV Haar XML cascade into stump arrays."""
    root = ET.parse(path_str).getroot().find("cascade")
    if root is None:
        raise ValueError(f"Invalid Haar cascade XML: {path_str}")
    feats = [
        [
            (int(x), int(y), int(w), int(h), float(wt))
            for x, y, w, h, wt in (r.text.split() for r in f.find("rects"))  # type: ignore[union-attr]
        ]
        for f in root.find("features")  # type: ignore[union-attr]
    ]
    stages = []
    for st in root.find("stages"):  # type: ignore[union-attr]
        weak = []
        for wc in st.find("weakClassifiers"):  # type: ignore[union-attr]
            node = wc.find("internalNodes").text.split()  # type: ignore[union-attr]
            leaf = wc.find("leafValues").text.split()  # type: ignore[union-attr]
            weak.append((int(node[2]), float(node[3]), float(leaf[0]), float(leaf[1])))
        stages.append((float(st.find("stageThreshold").text), weak))  # type: ignore[union-attr]
    return _HaarCascade(int(root.find("width").text), feats, stages)  # type: ignore[union-attr]


def _haar_rect_sum(
    ii_flat: np.ndarray,
    base: np.ndarray,
    stride: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
) -> np.ndarray:
    a = base + y * stride + x
    return ii_flat[a + h * stride + w] - ii_flat[a + w] - ii_flat[a + h * stride] + ii_flat[a]


def _haar_numpy_detect_batch(
    gray_frames: list[np.ndarray],
    casc: _HaarCascade,
    scales: list[float],
    step: int = 2,
) -> list[np.ndarray]:
    """Ported from `thlib/face.py`: pure-NumPy integral-image Viola-Jones across a batch of gray frames."""
    bufs: list[np.ndarray] = []
    sqs: list[np.ndarray] = []
    cols: list[tuple[np.ndarray, ...]] = []
    off = 0
    win = casc.win

    for fi, g in enumerate(gray_frames):
        h0, w0 = g.shape[:2]
        for s in scales:
            w, h = int(round(w0 / s)), int(round(h0 / s))
            if w <= win + 2 or h <= win + 2:
                continue
            img = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float64)
            ii = cv2.integral(img, sdepth=cv2.CV_64F)
            sq = cv2.integral(img * img, sdepth=cv2.CV_64F)
            ys, xs = np.mgrid[0 : h - win : step, 0 : w - win : step]
            ys, xs = ys.ravel(), xs.ravel()
            if len(xs) == 0:
                continue
            stride = ii.shape[1]
            cols.append((
                np.full(len(xs), fi),
                np.full(len(xs), s),
                off + ys * stride + xs,
                np.full(len(xs), stride),
                xs,
                ys,
            ))
            bufs.append(ii.ravel())
            sqs.append(sq.ravel())
            off += ii.size

    if not cols:
        return [np.empty((0, 4), dtype=float) for _ in gray_frames]

    fidx, scale, base_raw, stride_raw, xs, ys = (np.concatenate(c) for c in zip(*cols))
    ii_all = np.concatenate(bufs)
    sq_all = np.concatenate(sqs)
    base = base_raw.astype(np.int64)
    stride = stride_raw.astype(np.int64)

    inner = win - 2
    vs = _haar_rect_sum(ii_all, base, stride, 1, 1, inner, inner)
    vq = _haar_rect_sum(sq_all, base, stride, 1, 1, inner, inner)
    nf = inner * inner * vq - vs * vs
    nf = np.where(nf > 0, np.sqrt(np.maximum(nf, 0.0)), 1.0)

    idx = np.arange(len(base))
    for thr, weak in casc.stages:
        b, st, n = base[idx], stride[idx], nf[idx]
        total = np.zeros(len(idx), dtype=np.float64)
        for fi_w, t_w, lv, rv in weak:
            val = np.zeros(len(idx), dtype=np.float64)
            for rx, ry, rw, rh, wt in casc.feats[fi_w]:
                val += wt * _haar_rect_sum(ii_all, b, st, rx, ry, rw, rh)
            total += np.where(val / n < t_w, lv, rv)
        idx = idx[total >= thr]
        if len(idx) == 0:
            break

    out_hits: list[list[list[float]]] = [[] for _ in range(len(gray_frames))]
    for k in idx:
        s = float(scale[k])
        out_hits[int(fidx[k])].append([float(xs[k]) * s, float(ys[k]) * s, win * s, win * s])
    return [np.array(h, dtype=float).reshape(-1, 4) for h in out_hits]


def _haar_group_hits(hits: np.ndarray, min_hits: int = 3, cluster_frac: float = 0.20) -> list[float] | None:
    """Cluster Viola-Jones raw window hits into `[x0, y0, x1, y1]` (ported from `thlib/face.py`)."""
    if len(hits) < min_hits:
        return None
    c = np.median(hits, axis=0)
    near = hits[np.all(np.abs(hits - c) <= cluster_frac * c[2], axis=1)]
    if len(near) == 0:
        return None
    m = near.mean(axis=0)
    return [float(m[0]), float(m[1]), float(m[0] + m[2]), float(m[1] + m[3])]


def _detect_faces_haar(
    gray_frames: list[np.ndarray],
    cascade_xml: Path = HAAR_CASCADE_XML,
) -> tuple[str | None, list[list[float]]]:
    """
    Detect frontal face boxes `[x0, y0, x1, y1]` across grayscale thumbnail frames:
      1. Try `cv2.CascadeClassifier` (`"haar_cascade"`) if available in the OpenCV build.
      2. Fallback to pure-NumPy integral-image Viola-Jones (`"haar_numpy"`).
    """
    if not gray_frames or not cascade_xml.is_file():
        return None, []

    th_h, th_w = gray_frames[0].shape[:2]
    min_dim = min(th_w, th_h)

    # 1) Try native OpenCV CascadeClassifier when compiled in cv2
    if hasattr(cv2, "CascadeClassifier"):
        try:
            clf = cv2.CascadeClassifier(str(cascade_xml))
            if clf is not None and not clf.empty():
                min_sz = max(24, int(round(min_dim * 0.13)))
                boxes_cv: list[list[float]] = []
                for g in gray_frames:
                    rects = clf.detectMultiScale(
                        g,
                        scaleFactor=1.08,
                        minNeighbors=3,
                        minSize=(min_sz, min_sz),
                    )
                    if rects is not None and len(rects) > 0:
                        # Pick largest prominent frontal face
                        rects_sorted = sorted(rects, key=lambda r: int(r[2]) * int(r[3]), reverse=True)
                        rx, ry, rw, rh = (float(v) for v in rects_sorted[0])
                        boxes_cv.append([rx, ry, rx + rw, ry + rh])
                if boxes_cv:
                    return "haar_cascade", boxes_cv
        except Exception:
            pass

    # 2) Pure-NumPy integral-image Viola-Jones fallback (works on OpenCV 5.0+ where CascadeClassifier was removed)
    try:
        casc = _load_haar_cascade_xml(str(cascade_xml))
        s_min = max(1.45, (min_dim * 0.14) / casc.win)
        s_max = max(s_min * 1.25, (min_dim * 0.85) / casc.win)
        broad_scales: list[float] = []
        s_cur = s_min
        while s_cur <= s_max + 1e-6:
            broad_scales.append(round(s_cur, 5))
            s_cur *= 1.11

        # Scout 2 anchor frames across the clip to lock onto the presenter's face scale (~5x speedup on 24 frames)
        active_scales = broad_scales
        if len(gray_frames) >= 4:
            scout_idxs = [len(gray_frames) // 4, (len(gray_frames) * 3) // 4]
            scout_hits = _haar_numpy_detect_batch([gray_frames[i] for i in scout_idxs], casc, broad_scales, step=2)
            scout_widths: list[float] = []
            for h_arr in scout_hits:
                grp_s = _haar_group_hits(h_arr, min_hits=3, cluster_frac=0.20)
                if grp_s is not None:
                    scout_widths.append(grp_s[2] - grp_s[0])
            if scout_widths:
                s_center = float(np.median(scout_widths)) / casc.win
                s_lo = max(s_min, s_center * 0.76)
                s_hi = min(s_max, s_center * 1.30)
                narrow_scales: list[float] = []
                sc = s_lo
                while sc <= s_hi + 1e-6:
                    narrow_scales.append(round(sc, 5))
                    sc *= 1.07
                if len(narrow_scales) >= 4:
                    active_scales = narrow_scales

        boxes_np: list[list[float]] = []
        batch_sz = 12
        for a in range(0, len(gray_frames), batch_sz):
            batch_hits = _haar_numpy_detect_batch(gray_frames[a : a + batch_sz], casc, active_scales, step=2)
            for hits in batch_hits:
                grp = _haar_group_hits(hits, min_hits=3, cluster_frac=0.20)
                if grp is not None:
                    boxes_np.append(grp)

        if not boxes_np and active_scales is not broad_scales:
            for a in range(0, len(gray_frames), batch_sz):
                batch_hits = _haar_numpy_detect_batch(gray_frames[a : a + batch_sz], casc, broad_scales, step=2)
                for hits in batch_hits:
                    grp = _haar_group_hits(hits, min_hits=3, cluster_frac=0.20)
                    if grp is not None:
                        boxes_np.append(grp)

        if boxes_np:
            return "haar_numpy", boxes_np
    except Exception:
        pass

    return None, []


def _decode_sampled_rgb_frames(
    video_path: Path,
    duration_sec: float,
    num_samples: int,
    target_w: int = 270,
    src_w: int | None = None,
    src_h: int | None = None,
) -> list[np.ndarray]:
    """Decode `num_samples` evenly-spaced RGB thumbnails (`target_w` wide) via parallel fast `-ss` seeks."""
    if not video_path.is_file() or duration_sec <= 0.02 or num_samples <= 0:
        return []
    if src_w and src_h and src_w > 0 and src_h > 0:
        th_w = target_w
        th_h = max(2, int(round(src_h * (target_w / float(src_w)) / 2.0)) * 2)
    else:
        th_w, th_h = 270, 480

    frame_bytes = th_w * th_h * 3
    timestamps = [
        min(max(0.0, duration_sec - 0.04), duration_sec * (i + 0.5) / num_samples)
        for i in range(num_samples)
    ]

    def _seek_one(ts: float) -> np.ndarray | None:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={th_w}:{th_h}:flags=area",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and len(proc.stdout) >= frame_bytes:
            return np.frombuffer(proc.stdout[:frame_bytes], dtype=np.uint8).reshape(th_h, th_w, 3).copy()
        return None

    with ThreadPoolExecutor(max_workers=min(8, num_samples)) as ex:
        frames = [f for f in ex.map(_seek_one, timestamps) if f is not None]
    return frames


def _filter_face_box_outliers(boxes: list[list[float]], th_w: int, th_h: int) -> list[list[float]]:
    """Reject isolated background false-positive boxes while preserving genuine head motion."""
    if len(boxes) < 3:
        return boxes
    arr = np.asarray(boxes, dtype=float)
    med = np.median(arr, axis=0)
    mcx = 0.5 * (med[0] + med[2])
    mcy = 0.5 * (med[1] + med[3])
    mw = max(1.0, med[2] - med[0])
    mh = max(1.0, med[3] - med[1])
    kept: list[list[float]] = []
    for b in boxes:
        cx = 0.5 * (b[0] + b[2])
        cy = 0.5 * (b[1] + b[3])
        bw = max(1.0, b[2] - b[0])
        if (
            abs(cx - mcx) <= max(mw * 1.25, th_w * 0.30)
            and abs(cy - mcy) <= max(mh * 1.25, th_h * 0.30)
            and 0.55 * mw <= bw <= 1.85 * mw
        ):
            kept.append(b)
    return kept if kept else boxes


def compute_cranial_and_dual_rails(
    src_width: int,
    src_height: int,
    *,
    hair_top_y: int | float | None = None,
    chin_y: int | float | None = None,
    macro_exclusion_bbox: list[int] | None = None,
) -> tuple[list[int] | None, dict[str, Any] | None]:
    """
    Compute v7.0 Safe-Zone vertical bands in native pixel space `(W, H)`:
      - When a human face is present (`hair_top_y` and `chin_y` supplied):
          `cranial_exclusion_band = [max(0, hair_top_y - 48), min(H, chin_y + 32)]`
          `dual_rail_zones`: `upper_editorial_stage` above crown & `chest_tactile_rail` below chin.
      - When `faces == 0` and `macro_exclusion_bbox = [mx0, my0, mx1, my1]` is supplied:
          `cranial_exclusion_band = None`
          `dual_rail_zones`: safe upper/lower rails avoiding the dental/nail/skincare macro subject!
    """
    W, H = int(src_width), int(src_height)
    if W <= 0 or H <= 0:
        return None, None

    safe_x0 = int(round(W * (60.0 / 1080.0)))
    safe_x1 = int(round(W * (920.0 / 1080.0)))
    top_dead_y = int(round(H * (220.0 / 1920.0)))
    bot_safe_y = int(round(H * (1440.0 / 1920.0)))
    r209_sub_y = int(round(H * (1360.0 / 1920.0)))

    if hair_top_y is not None and chin_y is not None:
        c_y0 = max(0, int(round(float(hair_top_y))) - 48)
        c_y1 = min(H, int(round(float(chin_y))) + 32)
        if c_y1 < c_y0:
            c_y1 = c_y0
        cranial_band = [c_y0, c_y1]

        up_y0 = min(top_dead_y, c_y0)
        up_y1 = c_y0
        up_h = max(0, up_y1 - up_y0)

        ch_y0 = c_y1
        ch_y1 = max(ch_y0, bot_safe_y)
        ch_h = max(0, ch_y1 - ch_y0)

        dual_rails = {
            "mode": "face_cranial_dual_rail",
            "upper_editorial_stage": {
                "y_band_px": [up_y0, up_y1],
                "bbox_px": [safe_x0, up_y0, safe_x1, up_y1],
                "height_px": up_h,
                "usable": bool(up_h >= max(24, int(round(H * 0.065)))),
            },
            "chest_tactile_rail": {
                "y_band_px": [ch_y0, ch_y1],
                "bbox_px": [safe_x0, ch_y0, safe_x1, ch_y1],
                "r209_above_subtitle_y_band_px": [ch_y0, max(ch_y0, r209_sub_y)],
                "height_px": ch_h,
                "usable": bool(ch_h >= max(32, int(round(H * 0.08)))),
            },
        }
        return cranial_band, dual_rails

    if macro_exclusion_bbox is not None and len(macro_exclusion_bbox) >= 4:
        m_y0 = max(0, int(macro_exclusion_bbox[1]) - int(round(H * 0.015)))
        m_y1 = min(H, int(macro_exclusion_bbox[3]) + int(round(H * 0.015)))

        up_y0 = min(top_dead_y, m_y0)
        up_y1 = m_y0
        up_h = max(0, up_y1 - up_y0)

        ch_y0 = m_y1
        ch_y1 = max(ch_y0, bot_safe_y)
        ch_h = max(0, ch_y1 - ch_y0)

        dual_rails = {
            "mode": "zero_face_macro_avoidance",
            "upper_editorial_stage": {
                "y_band_px": [up_y0, up_y1],
                "bbox_px": [safe_x0, up_y0, safe_x1, up_y1],
                "height_px": up_h,
                "usable": bool(up_h >= max(24, int(round(H * 0.065)))),
            },
            "chest_tactile_rail": {
                "y_band_px": [ch_y0, ch_y1],
                "bbox_px": [safe_x0, ch_y0, safe_x1, ch_y1],
                "r209_above_subtitle_y_band_px": [ch_y0, max(ch_y0, r209_sub_y)],
                "height_px": ch_h,
                "usable": bool(ch_h >= max(32, int(round(H * 0.08)))),
            },
        }
        return None, dual_rails

    return None, None


def detect_cie_lab_enamel_gum_roi(
    rgb_frames_or_img: Sequence[np.ndarray] | np.ndarray,
    src_width: int,
    src_height: int,
) -> tuple[list[int] | None, dict[str, Any] | None]:
    """
    Zero-Face Dental Macro Safe-Zone Detector (`v7.0.0` CIE-Lab Enamel-Gum ROI):
      - Converts RGB frames to true CIE L*a*b* (`L* in [0..100]`, `a*, b* in [-128..127]`).
      - Finds bright tooth enamel / porcelain veneers (`L* > 72`, `a* <= 14`, `|b*| <= 28`)
        spatially coupled with adjacent pink gingiva / lip mucosa (`a* > 16`, `20 <= L* <= 88`).
      - Rejects uncoupled plain white studio walls (`a* <= 16` everywhere) and uncoupled pink props.
      - Returns `(enamel_gum_bbox_px, detail_dict)` in native `(src_width, src_height)` pixels.
    """
    if isinstance(rgb_frames_or_img, np.ndarray) and rgb_frames_or_img.ndim == 3:
        frames = [rgb_frames_or_img]
    else:
        frames = list(rgb_frames_or_img)  # type: ignore[arg-type]
    if not frames or src_width <= 0 or src_height <= 0:
        return None, None

    # Sample up to 5 evenly-spaced frames to capture sharpest intraoral / smile view
    if len(frames) > 5:
        pick_idxs = [int(round(i * (len(frames) - 1) / 4.0)) for i in range(5)]
        eval_frames = [frames[i] for i in dict.fromkeys(pick_idxs)]
    else:
        eval_frames = frames

    frame_boxes_px: list[list[float]] = []
    best_meta: dict[str, Any] | None = None
    best_score = -1.0

    for rgb in eval_frames:
        if rgb is None or rgb.size == 0 or rgb.ndim != 3:
            continue
        th_h, th_w = rgb.shape[:2]
        if th_w < 16 or th_h < 16:
            continue

        gray_chk = cv2.cvtColor(rgb[:, :, :3].astype(np.uint8), cv2.COLOR_RGB2GRAY)
        top_b, bot_b, left_b, right_b = _detect_uniform_borders(gray_chk, min_px=6)
        iy0 = top_b if (top_b + bot_b < th_h - 16) else 0
        iy1 = (th_h - bot_b) if (top_b + bot_b < th_h - 16) else th_h
        ix0 = left_b if (left_b + right_b < th_w - 16) else 0
        ix1 = (th_w - right_b) if (left_b + right_b < th_w - 16) else th_w

        sub_rgb = rgb[iy0:iy1, ix0:ix1, :3].astype(np.uint8)
        ih, iw = sub_rgb.shape[:2]
        inner_area = float(max(1, iw * ih))

        lab_u8 = cv2.cvtColor(sub_rgb, cv2.COLOR_RGB2Lab).astype(np.float32)
        L_star = lab_u8[:, :, 0] * (100.0 / 255.0)
        a_star = lab_u8[:, :, 1] - 128.0
        b_star = lab_u8[:, :, 2] - 128.0

        enamel_mask = ((L_star > 72.0) & (a_star <= 14.0) & (np.abs(b_star) <= 28.0)).astype(np.uint8)
        gum_mask = (
            (a_star > 16.0)
            & (L_star >= 20.0)
            & (L_star <= 88.0)
            & (b_star >= -14.0)
            & (b_star <= 40.0)
        ).astype(np.uint8)

        k_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        enamel_mask = cv2.morphologyEx(enamel_mask, cv2.MORPH_OPEN, k_clean)
        gum_mask = cv2.morphologyEx(gum_mask, cv2.MORPH_OPEN, k_clean)

        if int(enamel_mask.sum()) < max(12, int(inner_area * 0.003)) or int(gum_mask.sum()) < max(10, int(inner_area * 0.0025)):
            continue

        adj_r = max(5, int(round(min(iw, ih) * 0.065)))
        k_adj = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * adj_r + 1, 2 * adj_r + 1))
        enamel_adj = enamel_mask & cv2.dilate(gum_mask, k_adj)
        gum_adj = gum_mask & cv2.dilate(enamel_adj, k_adj)

        enamel_cnt = int(enamel_adj.sum())
        gum_cnt = int(gum_adj.sum())
        if enamel_cnt < max(10, int(inner_area * 0.0025)) or gum_cnt < max(8, int(inner_area * 0.0020)):
            continue

        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(5, adj_r | 1), max(5, adj_r | 1)))
        coupled = cv2.morphologyEx(((enamel_adj | gum_adj) * 255).astype(np.uint8), cv2.MORPH_CLOSE, k_close)
        n_lbl, lbl_map, stats, _ = cv2.connectedComponentsWithStats((coupled > 0).astype(np.uint8))

        sx = float(src_width) / float(th_w)
        sy = float(src_height) / float(th_h)

        for cid in range(1, n_lbl):
            bx, by, bw, bh, area = (int(stats[cid, k]) for k in range(5))
            area_ratio = area / inner_area
            if area_ratio < 0.0045 or area_ratio > 0.72:
                continue
            comp_mask = lbl_map == cid
            comp_enamel = comp_mask & (enamel_adj > 0)
            comp_gum = comp_mask & (gum_adj > 0)
            n_ce = int(comp_enamel.sum())
            n_cg = int(comp_gum.sum())
            if n_ce < max(8, int(inner_area * 0.002)) or n_cg < max(6, int(inner_area * 0.0015)):
                continue

            # Reject components glued simultaneously to all 4 outer borders
            touches = int(bx <= 1) + int(by <= 1) + int(bx + bw >= iw - 1) + int(by + bh >= ih - 1)
            if touches >= 4:
                continue

            mean_L_e = float(L_star[comp_enamel].mean())
            mean_a_g = float(a_star[comp_gum].mean())
            cx_n = ((bx + 0.5 * bw + ix0) / float(th_w)) - 0.50
            cy_n = ((by + 0.5 * bh + iy0) / float(th_h)) - 0.50
            center_w = math.exp(-(cx_n * cx_n + cy_n * cy_n) / 0.32)
            balance = min(float(n_ce), float(n_cg)) / max(1.0, float(max(n_ce, n_cg)))
            score = area_ratio * (1.0 + 0.6 * balance) * (1.0 + 0.02 * (mean_a_g - 16.0)) * center_w

            pad_x = bw * 0.06
            pad_y = bh * 0.08
            x0_px = max(0.0, (bx + ix0 - pad_x) * sx)
            y0_px = max(0.0, (by + iy0 - pad_y) * sy)
            x1_px = min(float(src_width), (bx + bw + ix0 + pad_x) * sx)
            y1_px = min(float(src_height), (by + bh + iy0 + pad_y) * sy)

            if score > best_score:
                best_score = score
                conf = float(
                    np.clip(
                        0.38 * min(1.0, (mean_L_e - 72.0) / 18.0)
                        + 0.38 * min(1.0, (mean_a_g - 16.0) / 18.0)
                        + 0.24 * min(1.0, area_ratio / 0.06),
                        0.35,
                        0.99,
                    )
                )
                best_meta = {
                    "enamel_mean_L_star": round(mean_L_e, 2),
                    "gum_mean_a_star": round(mean_a_g, 2),
                    "coupled_area_ratio": round(area_ratio, 4),
                    "confidence": round(conf, 4),
                }
            frame_boxes_px.append([x0_px, y0_px, x1_px, y1_px])

    if not frame_boxes_px or best_meta is None:
        return None, None

    arr_b = np.asarray(frame_boxes_px, dtype=float)
    bbox_px = [
        max(0, int(round(float(np.percentile(arr_b[:, 0], 20))))),
        max(0, int(round(float(np.percentile(arr_b[:, 1], 20))))),
        min(int(src_width), int(round(float(np.percentile(arr_b[:, 2], 80))))),
        min(int(src_height), int(round(float(np.percentile(arr_b[:, 3], 80))))),
    ]
    if bbox_px[2] <= bbox_px[0] or bbox_px[3] <= bbox_px[1]:
        return None, None

    detail = {
        "bbox_px": bbox_px,
        "bbox_norm": [
            round(bbox_px[0] / float(src_width), 4),
            round(bbox_px[1] / float(src_height), 4),
            round(bbox_px[2] / float(src_width), 4),
            round(bbox_px[3] / float(src_height), 4),
        ],
        **best_meta,
    }
    return bbox_px, detail


def detect_hsv_edge_macro_saliency_box(
    rgb_frames_or_img: Sequence[np.ndarray] | np.ndarray,
    src_width: int,
    src_height: int,
    *,
    t_std: np.ndarray | None = None,
    enamel_gum_bbox: list[int] | None = None,
) -> tuple[list[int] | None, dict[str, Any] | None]:
    """
    Zero-Face Macro Subject Safe-Zone Detector (`v7.0.0` HSV/Edge Hand-Nail-Product Saliency):
      - Fuses:
          1) HSV + YCrCb hand/finger skin & manicured nail/cosmetic chromatic saturation,
          2) Dense Sobel high-frequency optical focus energy (sharp foreground vs bokeh tabletop),
          3) Perceptual CIE-Lab ΔE contrast against outer perimeter background, and
          4) Multi-frame motion variance (`t_std`) when available.
      - Returns `(macro_subject_bbox_px, detail_dict)` so captions never collide with close-up
        nails, hands, serum droppers, cosmetic bottles, food/gadgets, or intraoral arches!
    """
    if isinstance(rgb_frames_or_img, np.ndarray) and rgb_frames_or_img.ndim == 3:
        frames = [rgb_frames_or_img]
    else:
        frames = list(rgb_frames_or_img)  # type: ignore[arg-type]
    if not frames or src_width <= 0 or src_height <= 0:
        return None, None

    rep_rgb = frames[len(frames) // 2][:, :, :3].astype(np.uint8)
    th_h, th_w = rep_rgb.shape[:2]
    if th_w < 16 or th_h < 16:
        return None, None

    gray = cv2.cvtColor(rep_rgb, cv2.COLOR_RGB2GRAY)
    top_b, bot_b, left_b, right_b = _detect_uniform_borders(gray, min_px=6)
    iy0 = top_b if (top_b + bot_b < th_h - 16) else 0
    iy1 = (th_h - bot_b) if (top_b + bot_b < th_h - 16) else th_h
    ix0 = left_b if (left_b + right_b < th_w - 16) else 0
    ix1 = (th_w - right_b) if (left_b + right_b < th_w - 16) else th_w

    sub_rgb = rep_rgb[iy0:iy1, ix0:ix1]
    sub_gray = gray[iy0:iy1, ix0:ix1]
    ih, iw = sub_gray.shape[:2]
    inner_area = float(max(1, iw * ih))

    # 1. CIE-Lab ΔE contrast vs outer 8% perimeter background ring
    lab = cv2.cvtColor(sub_rgb, cv2.COLOR_RGB2Lab).astype(np.float32)
    L_s = lab[:, :, 0] * (100.0 / 255.0)
    a_s = lab[:, :, 1] - 128.0
    b_s = lab[:, :, 2] - 128.0

    ring_w = max(2, int(round(min(iw, ih) * 0.08)))
    ring_mask = np.zeros((ih, iw), dtype=bool)
    ring_mask[:ring_w, :] = True
    ring_mask[-ring_w:, :] = True
    ring_mask[:, :ring_w] = True
    ring_mask[:, -ring_w:] = True
    bg_L = float(np.median(L_s[ring_mask]))
    bg_a = float(np.median(a_s[ring_mask]))
    bg_b = float(np.median(b_s[ring_mask]))
    delta_e = np.sqrt((L_s - bg_L) ** 2 + (a_s - bg_a) ** 2 + (b_s - bg_b) ** 2)

    # Reject completely blank / flat frames with zero subject contrast
    if float(sub_gray.std()) < 4.5 and float(np.percentile(delta_e, 92)) < 6.0:
        if enamel_gum_bbox is not None:
            return list(enamel_gum_bbox), {"macro_kind": "dental_enamel_gum", "bbox_px": list(enamel_gum_bbox), "confidence": 0.85}
        return None, None

    de_p96 = max(8.0, float(np.percentile(delta_e, 96)))
    de_norm = np.clip(delta_e / de_p96, 0.0, 1.0)

    # 2. High-frequency Sobel focus density (in-focus macro object vs soft bokeh background)
    g_blur = cv2.GaussianBlur(sub_gray, (3, 3), 0.8)
    gx = cv2.Sobel(g_blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g_blur, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(gx, gy)
    k_focus = max(7, int(round(min(iw, ih) * 0.055)) | 1)
    focus_energy = cv2.GaussianBlur(grad_mag, (k_focus, k_focus), 0.0)
    fe_p96 = max(6.0, float(np.percentile(focus_energy, 96)))
    focus_norm = np.clip(focus_energy / fe_p96, 0.0, 1.0)

    # 3. HSV + YCrCb Hand/Skin & Nail/Cosmetic Saturation Cue
    hsv = cv2.cvtColor(sub_rgb, cv2.COLOR_RGB2HSV)
    ycrcb_sub = cv2.cvtColor(sub_rgb, cv2.COLOR_RGB2YCrCb)
    H_ch, S_ch, V_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    skin_hand_mask = (
        ((H_ch <= 26) | (H_ch >= 165))
        & (S_ch >= 26)
        & (S_ch <= 200)
        & (V_ch >= 42)
        & (ycrcb_sub[:, :, 1] >= 131)
        & (ycrcb_sub[:, :, 1] <= 180)
        & (ycrcb_sub[:, :, 2] >= 75)
        & (ycrcb_sub[:, :, 2] <= 132)
    )
    bg_sat_med = float(np.median(S_ch[ring_mask]))
    vivid_swatch_mask = (S_ch.astype(np.float32) > max(62.0, bg_sat_med + 28.0)) & (V_ch >= 45)
    skin_hand_ratio = float(skin_hand_mask.mean())
    tactile_cue = np.where(skin_hand_mask, 1.0, np.where(vivid_swatch_mask, 0.75, 0.0)).astype(np.float32)

    # 4. Temporal motion cue when multiple frames exist
    if t_std is not None and t_std.shape[:2] == (th_h, th_w) and float(t_std.max()) > 3.0:
        sub_mot = t_std[iy0:iy1, ix0:ix1]
        mot_p95 = max(3.5, float(np.percentile(sub_mot, 95)))
        mot_norm = np.clip(sub_mot / mot_p95, 0.0, 1.0)
    else:
        mot_norm = np.zeros((ih, iw), dtype=np.float32)

    # Gentle spatial prior suppressing extreme 2% frame corners while preserving hands entering from bottom/sides
    yy, xx = np.mgrid[0:ih, 0:iw].astype(np.float32)
    dx = (xx / float(max(1, iw))) - 0.50
    dy = (yy / float(max(1, ih))) - 0.50
    spatial_prior = np.clip(1.08 - 0.55 * (dx * dx + 0.85 * dy * dy), 0.55, 1.05)

    sal = (0.38 * focus_norm + 0.34 * de_norm + 0.20 * tactile_cue + 0.18 * mot_norm) * spatial_prior
    sal_max = float(sal.max())
    if sal_max <= 0.12:
        return (list(enamel_gum_bbox), {"macro_kind": "dental_enamel_gum", "bbox_px": list(enamel_gum_bbox), "confidence": 0.85}) if enamel_gum_bbox else (None, None)

    thr = max(float(np.percentile(sal, 78)), 0.36 * sal_max)
    fg_bin = (sal >= thr).astype(np.uint8) * 255
    k_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    fg_bin = cv2.morphologyEx(fg_bin, cv2.MORPH_CLOSE, k_m)
    fg_bin = cv2.morphologyEx(fg_bin, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

    n_lbl, lbl_map, stats, _ = cv2.connectedComponentsWithStats((fg_bin > 0).astype(np.uint8))
    scored_comps: list[tuple[float, int, int, int, int]] = []
    for cid in range(1, n_lbl):
        bx, by, bw, bh, area = (int(stats[cid, k]) for k in range(5))
        if area < max(16, int(inner_area * 0.006)):
            continue
        touches_all = int(bx <= 1) + int(by <= 1) + int(bx + bw >= iw - 1) + int(by + bh >= ih - 1)
        if touches_all >= 4 and area > inner_area * 0.82:
            continue
        comp_sal = float(sal[lbl_map == cid].mean())
        scored_comps.append((area * comp_sal, bx, by, bw, bh))

    if not scored_comps:
        if enamel_gum_bbox is not None:
            return list(enamel_gum_bbox), {"macro_kind": "dental_enamel_gum", "bbox_px": list(enamel_gum_bbox), "confidence": 0.85}
        return None, None

    scored_comps.sort(key=lambda t: t[0], reverse=True)
    top_score = scored_comps[0][0]
    kept_c = [c for c in scored_comps[:3] if c[0] >= 0.28 * top_score]

    ux0 = min(c[1] for c in kept_c)
    uy0 = min(c[2] for c in kept_c)
    ux1 = max(c[1] + c[3] for c in kept_c)
    uy1 = max(c[2] + c[4] for c in kept_c)

    sx = float(src_width) / float(th_w)
    sy = float(src_height) / float(th_h)
    bbox_px = [
        max(0, int(round((ux0 + ix0) * sx))),
        max(0, int(round((uy0 + iy0) * sy))),
        min(int(src_width), int(round((ux1 + ix0) * sx))),
        min(int(src_height), int(round((uy1 + iy0) * sy))),
    ]

    if enamel_gum_bbox is not None:
        bbox_px = [
            min(bbox_px[0], int(enamel_gum_bbox[0])),
            min(bbox_px[1], int(enamel_gum_bbox[1])),
            max(bbox_px[2], int(enamel_gum_bbox[2])),
            max(bbox_px[3], int(enamel_gum_bbox[3])),
        ]
        macro_kind = "dental_enamel_gum"
    elif skin_hand_ratio >= 0.035:
        macro_kind = "hand_nail_or_cosmetic"
    else:
        macro_kind = "product_saliency_macro"

    conf = round(float(np.clip(sal_max / 0.85, 0.35, 0.98)), 4)
    detail = {
        "macro_kind": macro_kind,
        "bbox_px": bbox_px,
        "bbox_norm": [
            round(bbox_px[0] / float(src_width), 4),
            round(bbox_px[1] / float(src_height), 4),
            round(bbox_px[2] / float(src_width), 4),
            round(bbox_px[3] / float(src_height), 4),
        ],
        "skin_hand_ratio": round(skin_hand_ratio, 4),
        "confidence": conf,
    }
    return bbox_px, detail


def probe_broll_safe_zones(
    path: Path,
    pinfo: dict[str, Any],
) -> dict[str, Any]:
    """
    Lightweight Safe-Zone Probe for B-Roll video clips and still images (`v7.0.0`):
      - Checks Haar frontal face boxes first (`cranial_exclusion_band` + `dual_rail_zones` if `faces > 0`).
      - Whenever `faces == 0` (intraoral dental shots, nail/hand macro shots, skincare droppers,
        product unboxings), runs CIE-Lab Enamel-Gum ROI + HSV/Edge Macro Saliency detectors!
    """
    w_src = int(pinfo.get("w") or 0)
    h_src = int(pinfo.get("h") or 0)
    if w_src <= 0 or h_src <= 0 or not path.is_file():
        return {
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    ext = path.suffix.lower()
    rgb_samples: list[np.ndarray] = []
    if ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                rgb_full = np.asarray(im.convert("RGB"))
            th_w = min(270, w_src)
            th_h = max(16, int(round(h_src * (th_w / float(w_src)))))
            rgb_samples = [cv2.resize(rgb_full, (th_w, th_h), interpolation=cv2.INTER_AREA)]
        except Exception:
            pass
    elif ext in VIDEO_EXTS:
        dur = max(0.1, float(pinfo.get("dur") or 0.0))
        rgb_samples = _decode_sampled_rgb_frames(
            path,
            dur,
            num_samples=3 if dur >= 0.9 else 1,
            target_w=270,
            src_w=w_src,
            src_h=h_src,
        )

    if not rgb_samples:
        return {
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    th_h, th_w = rgb_samples[0].shape[:2]
    gray_samples = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in rgb_samples]
    haar_method, haar_boxes = _detect_faces_haar(gray_samples, HAAR_CASCADE_XML)
    if haar_method and haar_boxes:
        med_b = np.median(np.asarray(haar_boxes, dtype=float), axis=0)
        sy = float(h_src) / float(th_h)
        fbw = max(1.0, med_b[2] - med_b[0])
        hair_y_px = max(0.0, (med_b[1] - 0.30 * fbw) * sy)
        chin_y_px = min(float(h_src), med_b[3] * sy)
        cranial_band, dual_rails = compute_cranial_and_dual_rails(
            w_src,
            h_src,
            hair_top_y=hair_y_px,
            chin_y=chin_y_px,
        )
        return {
            "faces_detected": len(haar_boxes),
            "cranial_exclusion_band": cranial_band,
            "dual_rail_zones": dual_rails,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    t_std = (
        np.stack(rgb_samples).astype(np.float32).std(axis=0).mean(axis=2)
        if len(rgb_samples) > 1
        else None
    )
    enamel_bbox, enamel_detail = detect_cie_lab_enamel_gum_roi(rgb_samples, w_src, h_src)
    macro_bbox, macro_detail = detect_hsv_edge_macro_saliency_box(
        rgb_samples,
        w_src,
        h_src,
        t_std=t_std,
        enamel_gum_bbox=enamel_bbox,
    )
    _, dual_rails = compute_cranial_and_dual_rails(
        w_src,
        h_src,
        macro_exclusion_bbox=macro_bbox or enamel_bbox,
    )
    out: dict[str, Any] = {
        "faces_detected": 0,
        "cranial_exclusion_band": None,
        "dual_rail_zones": dual_rails,
        "enamel_gum_bbox": enamel_bbox,
        "macro_subject_bbox": macro_bbox,
    }
    if enamel_detail or macro_detail:
        out["zero_face_macro_safe_zone"] = {
            "enamel_gum": enamel_detail,
            "macro_subject": macro_detail,
        }
    return out


def estimate_subject_framing(
    frame_paths: list[Path],
    src_width: int | None,
    src_height: int | None,
    *,
    video_path: Path | None = None,
    duration_sec: float | None = None,
    num_samples: int | None = None,
) -> dict[str, Any]:
    """
    Estimate objective subject framing, Cranial Exclusion Band, Dual-Rail Safe Zones,
    and Zero-Face Macro Safe-Zones (`enamel_gum_bbox` & `macro_subject_bbox`) across sampled frames:
      1. `cv2.CascadeClassifier` on vendored `haarcascade_frontalface_default.xml` (`"haar_cascade"`)
      2. Pure-NumPy integral-image Viola-Jones fallback (`"haar_numpy"`)
      3. Strict anatomical head-plus-hair-crown YCrCb fallback (`"ycrcb_skin"` — rejects hands/intraoral close-ups)
      4. When `faces == 0`: CIE-Lab Enamel-Gum (`L* > 72` adjacent to `a* > 16`) & HSV/Edge Macro Saliency!
    Outputs 100% backward-compatible framing keys plus `cranial_exclusion_band`, `dual_rail_zones`,
    `enamel_gum_bbox`, and `macro_subject_bbox`.
    """
    if not src_width or not src_height:
        return {
            "detected": False,
            "reason": "no_video_frames",
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    valid_paths = [p for p in frame_paths if p.is_file()]
    if num_samples is not None and len(valid_paths) > num_samples > 0:
        idxs = [int(round(i * (len(valid_paths) - 1) / max(1, num_samples - 1))) for i in range(num_samples)]
        valid_paths = [valid_paths[i] for i in dict.fromkeys(idxs)]

    rgb_list: list[np.ndarray] = []
    for p in valid_paths:
        try:
            with Image.open(p) as im:
                rgb_list.append(np.asarray(im.convert("RGB")))
        except Exception:
            continue

    if (
        video_path is not None
        and duration_sec is not None
        and num_samples is not None
        and len(rgb_list) < num_samples
    ):
        needed = num_samples - len(rgb_list)
        extra_rgb = _decode_sampled_rgb_frames(
            video_path,
            duration_sec,
            num_samples=needed,
            target_w=270,
            src_w=src_width,
            src_h=src_height,
        )
        rgb_list.extend(extra_rgb)

    if not rgb_list and not valid_paths:
        return {
            "detected": False,
            "reason": "no_video_frames",
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    if not rgb_list:
        return {
            "detected": False,
            "reason": "unreadable_frames",
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    th_h, th_w = rgb_list[0].shape[:2]
    aligned_rgb = [
        arr if arr.shape[:2] == (th_h, th_w) else cv2.resize(arr, (th_w, th_h))
        for arr in rgb_list
    ]
    gray_frames = [cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) for arr in aligned_rgb]

    stack = np.stack(aligned_rgb).astype(np.float32)
    t_std = stack.std(axis=0).mean(axis=2) if len(aligned_rgb) > 1 else np.zeros((th_h, th_w), dtype=np.float32)
    mean_rgb = stack.mean(axis=0).astype(np.uint8)
    ycrcb = cv2.cvtColor(mean_rgb, cv2.COLOR_RGB2YCrCb)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    sx_scale = float(src_width) / th_w
    sy_scale = float(src_height) / th_h

    # Step 1 & 2: Haar Frontal-Face Detector (`haar_cascade` -> `haar_numpy`)
    haar_method, haar_boxes_th = _detect_faces_haar(gray_frames, HAAR_CASCADE_XML)
    if haar_method and haar_boxes_th:
        haar_boxes_th = _filter_face_box_outliers(haar_boxes_th, th_w, th_h)

    # Pre-check intraoral Enamel-Gum ROI when Viola-Jones finds 0 frontal faces so close-up mouths/hands
    # are NEVER misclassified as full heads by the YCrCb skin fallback!
    enamel_bbox_pre: list[int] | None = None
    enamel_detail_pre: dict[str, Any] | None = None
    if not haar_boxes_th:
        enamel_bbox_pre, enamel_detail_pre = detect_cie_lab_enamel_gum_roi(aligned_rgb, src_width, src_height)

    # Step 3: Strict anatomical head+hair-crown YCrCb fallback (only when no intraoral macro arch dominates)
    best_skin_face: tuple[float, int, int, int, int] | None = None
    skin_boxes_th: list[list[float]] = []
    is_intraoral_macro = bool(
        enamel_detail_pre is not None and float(enamel_detail_pre.get("coupled_area_ratio") or 0.0) >= 0.015
    )
    if not haar_boxes_th and not is_intraoral_macro:
        skin = (
            (ycrcb[:, :, 0] > 58)
            & (ycrcb[:, :, 1] >= 134)
            & (ycrcb[:, :, 1] <= 177)
            & (ycrcb[:, :, 2] >= 78)
            & (ycrcb[:, :, 2] <= 127)
        ).astype(np.uint8)
        skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, kernel)
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, kernel)

        n_lbl, _, stats, _ = cv2.connectedComponentsWithStats(skin)
        min_blob_area = max(90, int(th_w * th_h * 0.0025))
        for idx in range(1, n_lbl):
            x, y, bw, bh, area = (int(stats[idx, k]) for k in range(5))
            if area < min_blob_area:
                continue
            # Reject hands/forearms entering from bottom/side frame edges or lacking dark hair crown
            touches_bottom_or_sides = (x <= 3) or (x + bw >= th_w - 3) or (y + bh >= int(th_h * 0.84))
            w_frac = bw / float(max(1, th_w))
            aspect = bw / float(max(1, bh))
            hy0 = max(0, y - int(bw * 0.55))
            hair_dark = float((ycrcb[hy0 : max(hy0 + 1, y), x : x + bw, 0] < 78).mean()) if y > 6 else 0.0
            cx_n = (x + bw * 0.5) / th_w
            cy_n = (y + bh * 0.5) / th_h
            if (
                touches_bottom_or_sides
                or not (0.12 <= w_frac <= 0.55)
                or not (0.55 <= aspect <= 1.55)
                or not (0.08 <= cy_n <= 0.56)
                or hair_dark < 0.25
            ):
                continue
            mot_val = float(t_std[y : y + bh, x : x + bw].mean()) if len(aligned_rgb) > 1 else 4.0
            pos_weight = (1.0 - min(0.75, abs(cx_n - 0.5) * 1.2))
            score = area * (1.0 + mot_val * 0.35) * (1.0 + hair_dark * 1.4) * pos_weight
            if best_skin_face is None or score > best_skin_face[0]:
                best_skin_face = (score, x, y, bw, bh)
        if best_skin_face is not None:
            _, sx0, sy0, sbw, sbh = best_skin_face
            s_head_h = min(sbh, int(sbw * 1.38))
            skin_boxes_th.append([float(sx0), float(sy0), float(sx0 + sbw), float(sy0 + s_head_h)])

    # Motion / gradient upper-body or foreground silhouette
    if len(aligned_rgb) > 1 and float(t_std.max()) > 3.5:
        thresh = max(4.2, float(np.percentile(t_std, 80)))
        sil_mask = (t_std > thresh).astype(np.uint8)
        sil_mask = cv2.morphologyEx(sil_mask, cv2.MORPH_OPEN, kernel)
    else:
        gray = gray_frames[0] if len(gray_frames) == 1 else cv2.cvtColor(mean_rgb, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        sil_mask = (mag > float(np.percentile(mag, 82))).astype(np.uint8)

    ys, xs = np.where(sil_mask > 0)
    active_boxes_th = haar_boxes_th if haar_boxes_th else skin_boxes_th

    # Zero-Face Macro Safe-Zone branch (`faces == 0`)
    enamel_gum_bbox: list[int] | None = None
    macro_subject_bbox: list[int] | None = None
    zero_face_detail: dict[str, Any] | None = None
    if not active_boxes_th:
        enamel_gum_bbox = enamel_bbox_pre
        macro_subject_bbox, macro_detail = detect_hsv_edge_macro_saliency_box(
            aligned_rgb,
            src_width,
            src_height,
            t_std=t_std,
            enamel_gum_bbox=enamel_gum_bbox,
        )
        if enamel_detail_pre or macro_detail:
            zero_face_detail = {
                "enamel_gum": enamel_detail_pre,
                "macro_subject": macro_detail,
            }

    if active_boxes_th:
        detector_method = haar_method if haar_boxes_th else "ycrcb_skin"
    elif enamel_gum_bbox is not None:
        detector_method = "zero_face_cie_lab_enamel_gum"
    elif macro_subject_bbox is not None:
        detector_method = "zero_face_hsv_edge_macro"
    else:
        detector_method = "silhouette_only"

    if len(ys) > 25:
        ub_x1, ub_y1, ub_x2, ub_y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    elif active_boxes_th:
        med_b = np.median(np.asarray(active_boxes_th, dtype=float), axis=0)
        fbw_m = med_b[2] - med_b[0]
        ub_x1 = max(0, int(round(med_b[0] - fbw_m * 0.9)))
        ub_x2 = min(th_w, int(round(med_b[2] + fbw_m * 0.9)))
        ub_y1 = max(0, int(round(med_b[1] - fbw_m * 0.45)))
        ub_y2 = th_h
    elif macro_subject_bbox is not None:
        ub_x1 = max(0, int(round(macro_subject_bbox[0] / sx_scale)))
        ub_y1 = max(0, int(round(macro_subject_bbox[1] / sy_scale)))
        ub_x2 = min(th_w, int(round(macro_subject_bbox[2] / sx_scale)))
        ub_y2 = min(th_h, int(round(macro_subject_bbox[3] / sy_scale)))
    else:
        return {
            "detected": False,
            "reason": "no_salient_subject",
            "cranial_exclusion_band": None,
            "dual_rail_zones": None,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
        }

    result: dict[str, Any] = {
        "detected": True,
        "detector_method": detector_method,
        "frames_analyzed": len(aligned_rgb),
        "frames_with_face": len(active_boxes_th),
        "has_skin_face_region": len(active_boxes_th) > 0,
    }

    if active_boxes_th:
        arr_th = np.asarray(active_boxes_th, dtype=float)
        med_th = np.median(arr_th, axis=0)
        fx0_th, fy0_th, fx1_th, fy1_th = (float(med_th[k]) for k in range(4))
        fbw_th = max(1.0, fx1_th - fx0_th)
        fbh_th = max(1.0, fy1_th - fy0_th)

        # Estimate hairline above forehead top using dark hair crown or anatomical offset
        fy_i = max(0, int(round(fy0_th)))
        fx0_i = max(0, int(round(fx0_th)))
        fx1_i = min(th_w, max(fx0_i + 1, int(round(fx1_th))))
        crown_scan_y0 = max(0, fy_i - int(round(fbw_th * 0.55)))
        crown_strip = ycrcb[crown_scan_y0:fy_i, fx0_i:fx1_i, 0]
        dark_rows = np.where((crown_strip < 75).mean(axis=1) > 0.35)[0] if crown_strip.size > 0 else np.array([])
        hairline_th_y = (
            int(crown_scan_y0 + dark_rows[0])
            if len(dark_rows) > 0
            else max(ub_y1, int(round(fy0_th - fbw_th * 0.30)))
        )
        hairline_th_y = min(fy_i, max(0, hairline_th_y))

        # Scale representative face box & envelope to native video pixels (W x H)
        x0_px = max(0.0, min(float(src_width), fx0_th * sx_scale))
        y0_px = max(0.0, min(float(src_height), fy0_th * sy_scale))
        x1_px = max(x0_px + 1.0, min(float(src_width), fx1_th * sx_scale))
        y1_px = max(y0_px + 1.0, min(float(src_height), fy1_th * sy_scale))
        fw_px = x1_px - x0_px
        fh_px = y1_px - y0_px

        env_x0 = max(0.0, min(float(src_width), float(arr_th[:, 0].min()) * sx_scale))
        env_y0 = max(0.0, min(float(src_height), float(arr_th[:, 1].min()) * sy_scale))
        env_x1 = max(env_x0 + 1.0, min(float(src_width), float(arr_th[:, 2].max()) * sx_scale))
        env_y1 = max(env_y0 + 1.0, min(float(src_height), float(arr_th[:, 3].max()) * sy_scale))

        face_px = [int(round(x0_px)), int(round(y0_px)), int(round(x1_px)), int(round(y1_px))]
        eye_band_y_px = [int(round(y0_px + 0.30 * fh_px)), int(round(y0_px + 0.50 * fh_px))]
        mouth_band_y_px = [int(round(y0_px + 0.70 * fh_px)), int(round(y0_px + 0.90 * fh_px))]
        mouth_x_span_px = [int(round(x0_px + 0.22 * fw_px)), int(round(x0_px + 0.78 * fw_px))]
        face_envelope_px = [int(round(env_x0)), int(round(env_y0)), int(round(env_x1)), int(round(env_y1))]

        hair_top_y_px = int(round(hairline_th_y * sy_scale))
        chin_y_px = face_px[3]
        cranial_band, dual_rails = compute_cranial_and_dual_rails(
            src_width,
            src_height,
            hair_top_y=hair_top_y_px,
            chin_y=chin_y_px,
        )

        # Ensure upper_body_bbox encompasses detected face envelope horizontally & vertically
        ub_x1 = min(ub_x1, max(0, int(round(fx0_th - fbw_th * 0.35))))
        ub_x2 = max(ub_x2, min(th_w, int(round(fx1_th + fbw_th * 0.35))))
        ub_y1 = min(ub_y1, hairline_th_y)

        eye_y_px = y0_px + 0.38 * fh_px
        cx_px = 0.5 * (x0_px + x1_px)
        result.update({
            "face_bbox_px": face_px,
            "face_bbox_norm": [
                round(x0_px / src_width, 4),
                round(y0_px / src_height, 4),
                round(x1_px / src_width, 4),
                round(y1_px / src_height, 4),
            ],
            "face_envelope_px": face_envelope_px,
            "eye_band_y_px": eye_band_y_px,
            "mouth_band_y_px": mouth_band_y_px,
            "mouth_x_span_px": mouth_x_span_px,
            "hairline_y_px": hair_top_y_px,
            "hair_top_y_px": hair_top_y_px,
            "chin_y_px": chin_y_px,
            "cranial_exclusion_band": cranial_band,
            "dual_rail_zones": dual_rails,
            "enamel_gum_bbox": None,
            "macro_subject_bbox": None,
            "hairline_headroom_ratio": round(hairline_th_y / th_h, 4),
            "eye_line_y_px": int(round(eye_y_px)),
            "eye_line_ratio": round(eye_y_px / src_height, 4),
            "subject_center_x_px": int(round(cx_px)),
            "subject_center_x_ratio": round(cx_px / src_width, 4),
        })
    else:
        cx_th = (ub_x1 + ub_x2) * 0.5
        _, dual_rails = compute_cranial_and_dual_rails(
            src_width,
            src_height,
            macro_exclusion_bbox=macro_subject_bbox or enamel_gum_bbox,
        )
        result.update({
            "face_bbox_px": None,
            "face_bbox_norm": None,
            "face_envelope_px": None,
            "eye_band_y_px": None,
            "mouth_band_y_px": None,
            "mouth_x_span_px": None,
            "hairline_y_px": int(round(ub_y1 * sy_scale)),
            "hair_top_y_px": None,
            "chin_y_px": None,
            "cranial_exclusion_band": None,
            "dual_rail_zones": dual_rails,
            "enamel_gum_bbox": enamel_gum_bbox,
            "macro_subject_bbox": macro_subject_bbox,
            "zero_face_macro_safe_zone": zero_face_detail,
            "hairline_headroom_ratio": round(ub_y1 / th_h, 4),
            "eye_line_y_px": int(round((ub_y1 + (ub_y2 - ub_y1) * 0.25) * sy_scale)),
            "eye_line_ratio": round((ub_y1 + (ub_y2 - ub_y1) * 0.25) / th_h, 4),
            "subject_center_x_px": int(round(cx_th * sx_scale)),
            "subject_center_x_ratio": round(cx_th / th_w, 4),
        })

    result["upper_body_bbox_px"] = [
        int(round(ub_x1 * sx_scale)),
        int(round(ub_y1 * sy_scale)),
        int(round(ub_x2 * sx_scale)),
        int(round(ub_y2 * sy_scale)),
    ]
    result["upper_body_bbox_norm"] = [
        round(ub_x1 / th_w, 4),
        round(ub_y1 / th_h, 4),
        round(ub_x2 / th_w, 4),
        round(ub_y2 / th_h, 4),
    ]
    return result


def _detect_uniform_borders(
    gray: np.ndarray,
    min_px: int = 8,
    std_max: float = 3.0,
    jump: float = 30.0,
) -> list[int]:
    """
    Ported from `thlib/broll.py` (`_trim_uniform_borders` F3):
    Detect uniform black/white edge bands (`>= 8px` contiguous rows/cols with `row.std() < 3.0`,
    luminance `> 240` or `< 12`, and abrupt inner luminance jump `abs(inner_mean - border_mean) > 30.0`).
    Returns `[top, bottom, left, right]` in pixels.
    """
    g = np.asarray(gray, dtype=np.float32)
    if g.ndim != 2 or g.shape[0] < min_px * 2 or g.shape[1] < min_px * 2:
        return [0, 0, 0, 0]

    def _band(lines: np.ndarray) -> int:
        n = 0
        for row in lines:
            m = float(row.mean())
            if float(row.std()) < std_max and (m > 240.0 or m < 12.0):
                n += 1
            else:
                break
        if n < min_px or n + min_px > len(lines):
            return 0
        inner_mean = float(lines[n : n + min_px].mean())
        border_mean = float(lines[:n].mean())
        return int(n) if abs(inner_mean - border_mean) > jump else 0

    top = _band(g)
    bottom = _band(g[::-1])
    left = _band(g.T)
    right = _band(g.T[::-1])
    return [top, bottom, left, right]


def _is_broll_candidate(
    rel_key: str,
    path: Path,
    pinfo: dict[str, Any],
    has_explicit_aroll: bool,
) -> bool:
    """Identify B-roll video clips and photographic B-roll still images while excluding UI/GFX/overlays."""
    cat = str(pinfo.get("category") or "")
    rel_l = rel_key.lower()
    stem_l = path.stem.lower()
    ext = path.suffix.lower()

    if cat == "overlays" or "ovl_" in stem_l or "overlay" in rel_l:
        return False
    if any(k in rel_l for k in ("a-roll", "aroll", "talking_head", "avatar")):
        return False

    explicit_broll = bool(
        "b-roll" in rel_l
        or "broll" in rel_l
        or re.search(r"(?:^|[/_\-])br\d+", rel_l)
        or any(k in stem_l for k in ("cutaway", "insert", "footage"))
    )
    if ext in VIDEO_EXTS and cat == "video":
        return explicit_broll or has_explicit_aroll

    if ext in IMAGE_EXTS:
        if any(
            stem_l.startswith(pfx)
            for pfx in ("kw_", "panel_", "top_shade", "bottom_shade", "shade_", "matte_", "3d_", "ui_card_", "icon_", "logo")
        ):
            return False
        if "alpha" in stem_l or bool(pinfo.get("has_alpha")):
            return False
        return explicit_broll or ext in {".jpg", ".jpeg", ".webp"}

    return False


def audit_broll_media(path: Path, pinfo: dict[str, Any], flat_std_min: float = 30.0) -> dict[str, Any] | None:
    """
    Sample midpoint grayscale frame of a B-roll video or image at native resolution and measure:
      - `uniform_borders_px`: `[top, bottom, left, right]`
      - `grayscale_std`: luminance standard deviation (inner area if uniform borders exist)
      - `is_flat`: `grayscale_std < 30.0`
    """
    ext = path.suffix.lower()
    gray: np.ndarray | None = None

    if ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                gray = np.asarray(im.convert("L"), dtype=np.float32)
        except Exception:
            return None
    elif ext in VIDEO_EXTS:
        w = int(pinfo.get("w") or 0)
        h = int(pinfo.get("h") or 0)
        dur = float(pinfo.get("dur") or 0.0)
        if w <= 0 or h <= 0:
            return None
        mid_ts = max(0.0, dur * 0.5 - 0.02) if dur > 0.05 else 0.0
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                f"{mid_ts:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and len(proc.stdout) >= w * h:
            gray = np.frombuffer(proc.stdout[: w * h], dtype=np.uint8).reshape(h, w).astype(np.float32)

    if gray is None or gray.size == 0:
        return None

    borders = _detect_uniform_borders(gray)
    top, bottom, left, right = borders
    h_g, w_g = gray.shape[:2]
    if (top or bottom or left or right) and (top + bottom < h_g - 4) and (left + right < w_g - 4):
        inner = gray[top : h_g - bottom, left : w_g - right]
    else:
        inner = gray
    std_val = round(float(inner.std()), 2)
    return {
        "uniform_borders_px": borders,
        "grayscale_std": std_val,
        "is_flat": bool(std_val < flat_std_min),
    }


# ---------------------------------------------------------------------------
# v6.0 Cut-on-Action Velocity Peak Miner & Geometric Match-Cut Salience Engine
# ---------------------------------------------------------------------------


def _decode_downsampled_gray_stream(
    video_path: Path,
    sample_fps: float = 15.0,
    thumb_w: int = 160,
    src_w: int | None = None,
    src_h: int | None = None,
    max_dur_sec: float = 240.0,
) -> tuple[np.ndarray, float]:
    """Decode a video clip into a compact `(N, th_h, th_w)` uint8 luma array at `sample_fps`."""
    if not video_path.is_file():
        return np.empty((0, 0, 0), dtype=np.uint8), sample_fps

    if src_w and src_h and src_w > 0 and src_h > 0:
        th_w = int(thumb_w)
        th_h = max(16, int(round(src_h * (th_w / float(src_w)) / 2.0)) * 2)
    else:
        _, pinfo = probe_single_media(video_path, None)
        pw = int(pinfo.get("w") or 1080)
        ph = int(pinfo.get("h") or 1920)
        th_w = int(thumb_w)
        th_h = max(16, int(round(ph * (th_w / float(max(1, pw))) / 2.0)) * 2)

    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-t",
        f"{max(0.2, float(max_dur_sec)):.3f}",
        "-i",
        str(video_path),
        "-an",
        "-vf",
        f"fps={sample_fps:.3f},scale={th_w}:{th_h}:flags=fast_bilinear",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    frame_sz = th_w * th_h
    if proc.returncode != 0 or frame_sz <= 0 or len(proc.stdout) < frame_sz * 2:
        return np.empty((0, 0, 0), dtype=np.uint8), sample_fps

    n_frames = len(proc.stdout) // frame_sz
    arr = np.frombuffer(proc.stdout[: n_frames * frame_sz], dtype=np.uint8).reshape((n_frames, th_h, th_w)).copy()
    return arr, float(sample_fps)


def mine_gesture_action_peaks(
    video_path_or_frames: str | Path | Sequence[np.ndarray] | np.ndarray | None,
    duration_sec: float | None = None,
    *,
    subject_framing: dict[str, Any] | None = None,
    sample_fps: float = 15.0,
    thumb_w: int = 160,
    min_peak_gap_s: float = 0.38,
    min_strength: float = 0.18,
    t_offset_s: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Cut-on-Action Velocity Peak Miner (`v6.0.0` @__dviet Era-2 `7707653827016674580`):
      - Computes frame-to-frame motion energy around the speaker's head & hands on A-Roll
        (`15fps` downsampled luma diff).
      - Rejects isolated 1-frame pre-cut jump spikes while locking onto genuine mid-head-turn
        and hand-raise velocity peaks so A-Roll camera switches (`center -> left_third -> closeup_high`)
        snap invisibly onto physical action!
      - Returns `[{"t_sec": ..., "strength": ..., "dominant_zone": ..., "motion_luma_per_frame": ...}, ...]`.
    """
    if video_path_or_frames is None:
        return []

    eff_fps = max(4.0, float(sample_fps))
    if isinstance(video_path_or_frames, (str, Path)):
        vpath = Path(video_path_or_frames)
        max_d = float(duration_sec) if (duration_sec and duration_sec > 0.0) else 240.0
        gray_seq, eff_fps = _decode_downsampled_gray_stream(
            vpath, sample_fps=eff_fps, thumb_w=thumb_w, max_dur_sec=max_d
        )
    else:
        raw_arr = np.asarray(video_path_or_frames)
        if raw_arr.ndim == 4 and raw_arr.shape[-1] >= 3:
            frames_g = [cv2.cvtColor(f[:, :, :3].astype(np.uint8), cv2.COLOR_BGR2GRAY) for f in raw_arr]
            gray_seq = np.stack(frames_g, axis=0)
        elif raw_arr.ndim == 3:
            gray_seq = raw_arr.astype(np.uint8)
        else:
            return []

    n_f = int(gray_seq.shape[0])
    if n_f < 4:
        return []
    th_h, th_w = int(gray_seq.shape[1]), int(gray_seq.shape[2])

    # Build anatomical Head/Eye + Hand/Gesture ROI weights from `subject_framing` (or sunk-phone defaults)
    fb_norm = (subject_framing or {}).get("face_bbox_norm")
    if isinstance(fb_norm, (list, tuple)) and len(fb_norm) >= 4:
        fx0, fy0, fx1, fy1 = (float(v) for v in fb_norm[:4])
        fcx = 0.5 * (fx0 + fx1)
        fw_n = max(0.16, fx1 - fx0)
        head_x0 = max(0.06, fcx - 0.95 * fw_n)
        head_x1 = min(0.94, fcx + 0.95 * fw_n)
        head_y0 = max(0.06, fy0 - 0.25 * (fy1 - fy0))
        head_y1 = min(0.90, fy1 + 0.20 * (fy1 - fy0))
        hand_x0 = max(0.05, fcx - 1.85 * fw_n)
        hand_x1 = min(0.95, fcx + 1.85 * fw_n)
        hand_y0 = max(0.25, fy1 - 0.10 * (fy1 - fy0))
        hand_y1 = 0.96
    else:
        head_x0, head_x1, head_y0, head_y1 = 0.22, 0.78, 0.20, 0.52
        hand_x0, hand_x1, hand_y0, hand_y1 = 0.10, 0.90, 0.50, 0.95

    yy, xx = np.mgrid[0:th_h, 0:th_w].astype(np.float32)
    xn = xx / float(max(1, th_w))
    yn = yy / float(max(1, th_h))

    in_head = (xn >= head_x0) & (xn <= head_x1) & (yn >= head_y0) & (yn <= head_y1)
    in_hand = (xn >= hand_x0) & (xn <= hand_x1) & (yn >= hand_y0) & (yn <= hand_y1)

    roi_w = np.full((th_h, th_w), 0.12, dtype=np.float32)
    roi_w[in_hand] = 1.15
    roi_w[in_head] = 1.35

    # Light 3x3 spatial blur to suppress H.264 macroblock mosquito noise
    smoothed = np.empty((n_f, th_h, th_w), dtype=np.float32)
    for idx in range(n_f):
        smoothed[idx] = cv2.GaussianBlur(gray_seq[idx], (3, 3), 0.8).astype(np.float32)

    diffs = np.abs(smoothed[1:] - smoothed[:-1])  # (n_f - 1, th_h, th_w)
    weighted_diffs = diffs * roi_w[None, :, :]

    speaker_roi = in_head | in_hand
    roi_vals = weighted_diffs[:, speaker_roi] if np.any(speaker_roi) else weighted_diffs.reshape((n_f - 1, -1))
    mean_e = roi_vals.mean(axis=1)
    p92_e = np.percentile(roi_vals, 92, axis=1)
    p97_e = np.percentile(roi_vals, 97, axis=1)
    raw_energy = (0.25 * mean_e + 0.35 * p92_e + 0.40 * p97_e).astype(np.float64)

    head_energy = (
        np.percentile(diffs[:, in_head], 95, axis=1) if np.any(in_head) else np.zeros(n_f - 1, dtype=np.float64)
    )
    hand_only = in_hand & (~in_head)
    hand_energy = (
        np.percentile(diffs[:, hand_only], 95, axis=1) if np.any(hand_only) else np.zeros(n_f - 1, dtype=np.float64)
    )

    # Suppress isolated 1-frame scene-cut spikes in pre-edited clips so only physical gestures score
    med_e = float(np.median(raw_energy))
    clean_energy = raw_energy.copy()
    if n_f - 1 >= 5:
        for k in range(n_f - 1):
            left_e = raw_energy[k - 1] if k > 0 else raw_energy[min(n_f - 2, k + 1)]
            right_e = raw_energy[k + 1] if k + 1 < (n_f - 1) else left_e
            neighbor_max = max(left_e, right_e)
            if raw_energy[k] > max(18.0, 5.5 * max(0.5, med_e)) and neighbor_max < 0.22 * raw_energy[k]:
                clean_energy[k] = neighbor_max

    # 3-tap temporal smoothing [0.25, 0.50, 0.25] (~67ms @ 15fps) locks onto velocity midpoint
    if len(clean_energy) >= 3:
        pad_e = np.pad(clean_energy, (1, 1), mode="edge")
        smooth_e = 0.25 * pad_e[:-2] + 0.50 * pad_e[1:-1] + 0.25 * pad_e[2:]
    else:
        smooth_e = clean_energy

    base_floor = float(np.percentile(smooth_e, 45))
    peak_ceil = max(float(np.percentile(smooth_e, 98)), base_floor + 3.6)
    norm_strength = np.clip((smooth_e - base_floor) / max(1e-6, peak_ceil - base_floor), 0.0, 1.0)

    # Local maxima candidates above `min_strength`
    cand_indices: list[int] = []
    m_len = len(norm_strength)
    for k in range(m_len):
        s_val = float(norm_strength[k])
        if s_val < float(min_strength) or float(smooth_e[k]) < 1.35:
            continue
        prev_v = float(norm_strength[k - 1]) if k > 0 else -1.0
        next_v = float(norm_strength[k + 1]) if (k + 1) < m_len else -1.0
        if s_val >= prev_v and s_val >= next_v and (s_val > prev_v or s_val > next_v):
            cand_indices.append(k)

    # Greedy NMS by strength with `min_peak_gap_s`
    cand_indices.sort(key=lambda idx: float(norm_strength[idx]), reverse=True)
    kept: list[int] = []
    min_gap = max(0.12, float(min_peak_gap_s))
    for idx in cand_indices:
        t_cand = float(t_offset_s) + (idx + 0.5) / eff_fps
        if all(abs(t_cand - (float(t_offset_s) + (j + 0.5) / eff_fps)) >= min_gap for j in kept):
            kept.append(idx)

    kept.sort()
    peaks_out: list[dict[str, Any]] = []
    for idx in kept:
        t_pk = float(t_offset_s) + (idx + 0.5) / eff_fps
        dom_zone = "head_turn" if float(head_energy[idx]) >= float(hand_energy[idx]) * 0.92 else "hand_raise"
        peaks_out.append(
            {
                "t_sec": round(t_pk, 4),
                "strength": round(float(norm_strength[idx]), 4),
                "dominant_zone": dom_zone,
                "motion_luma_per_frame": round(float(smooth_e[idx]), 3),
            }
        )
    return peaks_out


def _detect_geometric_anchors_on_gray(
    gray_raw: np.ndarray,
    max_anchors: int = 3,
) -> list[dict[str, Any]]:
    """Detect dominant circular & rectangular focal shapes on a single 2D grayscale image."""
    if gray_raw is None or gray_raw.size == 0:
        return []
    g_orig = np.asarray(gray_raw, dtype=np.uint8)
    if g_orig.ndim == 3:
        g_orig = cv2.cvtColor(g_orig[:, :, :3], cv2.COLOR_BGR2GRAY)
    orig_h, orig_w = g_orig.shape[:2]
    if orig_w < 24 or orig_h < 24:
        return []

    aw = min(360, orig_w)
    ah = max(24, int(round(orig_h * (aw / float(orig_w)))))
    g = cv2.resize(g_orig, (aw, ah), interpolation=cv2.INTER_AREA)

    # Exclude uniform letterbox bars from generating false edge contours while keeping full-frame % coords!
    top_b, bot_b, left_b, right_b = _detect_uniform_borders(g, min_px=6)
    iy0 = top_b if (top_b + bot_b < ah - 24) else 0
    iy1 = (ah - bot_b) if (top_b + bot_b < ah - 24) else ah
    ix0 = left_b if (left_b + right_b < aw - 24) else 0
    ix1 = (aw - right_b) if (left_b + right_b < aw - 24) else aw
    iw = max(16, ix1 - ix0)
    ih = max(16, iy1 - iy0)
    g_inner = g[iy0:iy1, ix0:ix1]

    g_blur = cv2.GaussianBlur(g_inner, (5, 5), 1.35)
    gx = cv2.Sobel(g_blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g_blur, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(gx, gy)
    grad_p90 = max(12.0, float(np.percentile(grad_mag, 90)))

    candidates: list[dict[str, Any]] = []

    def _central_salience(cx_f: float, cy_f: float) -> float:
        dx_n = (cx_f / float(aw)) - 0.50
        dy_n = (cy_f / float(ah)) - 0.48
        return float(math.exp(-(dx_n * dx_n + dy_n * dy_n) / 0.24))

    # 1. Dominant Circular Focal Detector (`cv2.HoughCircles` + radial perimeter gradient check)
    min_r = max(10, int(round(min(iw, ih) * 0.06)))
    max_r = max(min_r + 6, int(round(min(iw, ih) * 0.47)))
    circles = cv2.HoughCircles(
        g_blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(24.0, min(iw, ih) * 0.22),
        param1=105.0,
        param2=26.0,
        minRadius=min_r,
        maxRadius=max_r,
    )
    thetas = np.linspace(0.0, 2.0 * math.pi, 36, endpoint=False, dtype=np.float32)
    cos_t = np.cos(thetas)
    sin_t = np.sin(thetas)

    if circles is not None and circles.size >= 3:
        for c_entry in circles[0][:8]:
            cx_i, cy_i, r_i = float(c_entry[0]), float(c_entry[1]), float(c_entry[2])
            px = np.clip(np.round(cx_i + r_i * cos_t).astype(np.int32), 0, iw - 1)
            py = np.clip(np.round(cy_i + r_i * sin_t).astype(np.int32), 0, ih - 1)
            samples_g = grad_mag[py, px]
            perim_grad = float(samples_g.mean()) / grad_p90
            # True circles have uniform edge support around >=68% of all 36 angles (including 45/135/225/315 deg),
            # whereas squares/rectangles only touch an inscribed circle at 4 tangent midpoints (~25-35% of angles)!
            edge_hit_frac = float((samples_g >= 0.25 * grad_p90).mean())
            if edge_hit_frac < 0.68:
                continue

            # Measure interior vs outer annulus contrast
            yy_c, xx_c = np.ogrid[0:ih, 0:iw]
            dist2 = (xx_c - cx_i) ** 2 + (yy_c - cy_i) ** 2
            in_m = dist2 <= (r_i * 0.82) ** 2
            out_m = (dist2 >= (r_i * 1.12) ** 2) & (dist2 <= (r_i * 1.48) ** 2)
            contrast = (
                abs(float(g_blur[in_m].mean()) - float(g_blur[out_m].mean())) / 65.0
                if (np.any(in_m) and np.any(out_m))
                else 0.25
            )

            cx_full = cx_i + ix0
            cy_full = cy_i + iy0
            sal = _central_salience(cx_full, cy_full)
            conf = float(
                np.clip(
                    0.34 * min(1.25, perim_grad) + 0.24 * edge_hit_frac + 0.22 * min(1.2, contrast) + 0.24 * sal,
                    0.0,
                    0.99,
                )
            )
            if conf >= 0.32 and perim_grad >= 0.28:
                candidates.append(
                    {
                        "shape": "circle",
                        "cx_pct": round((cx_full / float(aw)) * 100.0, 3),
                        "cy_pct": round((cy_full / float(ah)) * 100.0, 3),
                        "r_pct_w": round((r_i / float(aw)) * 100.0, 3),
                        "w_pct": round((2.0 * r_i / float(aw)) * 100.0, 3),
                        "h_pct": round((2.0 * r_i / float(ah)) * 100.0, 3),
                        "confidence": round(conf, 4),
                    }
                )

    # 2. Central Canny + Luma Salience Contour Detector (Rectangles & Clean Filled Circles)
    med_val = float(np.median(g_blur))
    std_val = float(g_blur.std())
    sal_dev = np.abs(g_blur.astype(np.float32) - med_val)
    sal_thr = max(14.0, 0.85 * std_val)
    sal_bin = (sal_dev >= sal_thr).astype(np.uint8) * 255
    k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    sal_bin = cv2.morphologyEx(sal_bin, cv2.MORPH_CLOSE, k5)
    sal_bin = cv2.morphologyEx(sal_bin, cv2.MORPH_OPEN, k5)

    edges = cv2.Canny(g_blur, 45, 130)
    edges_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k5)

    inner_area = float(iw * ih)
    for mask_src in (sal_bin, edges_closed):
        cnts, _ = cv2.findContours(mask_src, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in cnts:
            area = float(cv2.contourArea(cnt))
            if area < inner_area * 0.012 or area > inner_area * 0.78:
                continue
            perim = float(cv2.arcLength(cnt, True))
            if perim < 24.0:
                continue
            bx, by, bw, bh = cv2.boundingRect(cnt)
            # Ignore contours glued simultaneously to 3+ outer edges (background wall)
            touches = int(bx <= 2) + int(by <= 2) + int(bx + bw >= iw - 2) + int(by + bh >= ih - 2)
            if touches >= 3:
                continue

            circularity = (4.0 * math.pi * area) / max(1.0, perim * perim)
            rect_fill = area / max(1.0, float(bw * bh))
            hull = cv2.convexHull(cnt)
            solidity = area / max(1.0, float(cv2.contourArea(hull)))
            approx = cv2.approxPolyDP(cnt, 0.032 * perim, True)

            M_cnt = cv2.moments(cnt)
            if M_cnt["m00"] > 1e-3:
                cx_i = float(M_cnt["m10"] / M_cnt["m00"])
                cy_i = float(M_cnt["m01"] / M_cnt["m00"])
            else:
                cx_i = bx + 0.5 * bw
                cy_i = by + 0.5 * bh

            cx_full = cx_i + ix0
            cy_full = cy_i + iy0
            sal = _central_salience(cx_full, cy_full)

            # Note: for a square, circularity == pi/4 == 0.7854 and rect_fill == 1.0 (len(approx)==4);
            # for a true circle, circularity >= 0.83, len(approx) >= 7, and rect_fill ~ pi/4 < 0.85!
            is_true_circle = (
                circularity >= 0.83
                and len(approx) >= 7
                and rect_fill < 0.86
                and solidity >= 0.90
                and 0.75 <= (bw / float(max(1, bh))) <= 1.33
            )
            if is_true_circle:
                r_eq = math.sqrt(area / math.pi)
                conf = float(np.clip(0.50 * circularity + 0.24 * solidity + 0.26 * sal, 0.0, 0.98))
                candidates.append(
                    {
                        "shape": "circle",
                        "cx_pct": round((cx_full / float(aw)) * 100.0, 3),
                        "cy_pct": round((cy_full / float(ah)) * 100.0, 3),
                        "r_pct_w": round((r_eq / float(aw)) * 100.0, 3),
                        "w_pct": round((bw / float(aw)) * 100.0, 3),
                        "h_pct": round((bh / float(ah)) * 100.0, 3),
                        "confidence": round(conf, 4),
                    }
                )
            elif rect_fill >= 0.68 and (4 <= len(approx) <= 8 or solidity >= 0.86):
                r_eq = 0.5 * math.sqrt(float(bw) * float(bh))
                poly_bonus = 0.14 if len(approx) == 4 else 0.04
                conf = float(np.clip(0.45 * rect_fill + 0.22 * solidity + 0.24 * sal + poly_bonus, 0.0, 0.98))
                candidates.append(
                    {
                        "shape": "rect",
                        "cx_pct": round((cx_full / float(aw)) * 100.0, 3),
                        "cy_pct": round((cy_full / float(ah)) * 100.0, 3),
                        "r_pct_w": round((r_eq / float(aw)) * 100.0, 3),
                        "w_pct": round((bw / float(aw)) * 100.0, 3),
                        "h_pct": round((bh / float(ah)) * 100.0, 3),
                        "confidence": round(conf, 4),
                    }
                )

    if not candidates:
        return []

    # Sort highest-confidence first and deduplicate concentric overlaps (within 8% center distance)
    candidates.sort(key=lambda c: float(c["confidence"]), reverse=True)
    deduped: list[dict[str, Any]] = []
    for cand in candidates:
        is_dup = False
        for kept_c in deduped:
            dist_pct = math.hypot(cand["cx_pct"] - kept_c["cx_pct"], cand["cy_pct"] - kept_c["cy_pct"])
            r_ratio = abs(cand["r_pct_w"] - kept_c["r_pct_w"]) / max(1.0, kept_c["r_pct_w"])
            if dist_pct <= 8.5 and r_ratio <= 0.35:
                is_dup = True
                break
        if not is_dup:
            deduped.append(cand)
            if len(deduped) >= max_anchors:
                break
    return deduped


def detect_geometric_anchors(
    media_or_frame: str | Path | np.ndarray,
    pinfo: dict[str, Any] | None = None,
    *,
    max_anchors: int = 3,
) -> list[dict[str, Any]]:
    """
    Geometric Match-Cut Salience Detector (`v6.0.0`):
      - Detects dominant circular & rectangular focal shapes (`HoughCircles` + central Canny/luma
        salience contour) on B-Roll clips, still images, or in-memory NumPy frames.
      - Returns `[{"shape": "circle"|"rect", "cx_pct": ..., "cy_pct": ..., "r_pct_w": ..., "confidence": ...}, ...]`.
    """
    if isinstance(media_or_frame, np.ndarray):
        return _detect_geometric_anchors_on_gray(media_or_frame, max_anchors=max_anchors)

    path = Path(media_or_frame)
    if not path.is_file():
        return []
    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        try:
            with Image.open(path) as im:
                gray = np.asarray(im.convert("L"), dtype=np.uint8)
            return _detect_geometric_anchors_on_gray(gray, max_anchors=max_anchors)
        except Exception:
            return []

    if ext in VIDEO_EXTS:
        info = pinfo if pinfo is not None else probe_single_media(path, None)[1]
        dur = float(info.get("dur") or 0.0)
        w_src = int(info.get("w") or 1080)
        h_src = int(info.get("h") or 1920)
        rgb_samples = _decode_sampled_rgb_frames(
            path,
            max(0.1, dur),
            num_samples=3 if dur >= 0.9 else 1,
            target_w=360,
            src_w=w_src,
            src_h=h_src,
        )
        if not rgb_samples:
            return []
        role_names = ["head", "mid", "tail"] if len(rgb_samples) == 3 else ["mid"]
        pooled: list[dict[str, Any]] = []
        for s_idx, rgb in enumerate(rgb_samples):
            g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            ancs = _detect_geometric_anchors_on_gray(g, max_anchors=2)
            role = role_names[min(s_idx, len(role_names) - 1)]
            for a in ancs:
                a_copy = dict(a)
                a_copy["sample_role"] = role
                # Slightly prioritize midpoint representative frame when confidences tie
                if role == "mid":
                    a_copy["confidence"] = round(min(0.99, float(a_copy["confidence"]) + 0.015), 4)
                pooled.append(a_copy)

        pooled.sort(key=lambda c: float(c["confidence"]), reverse=True)
        deduped: list[dict[str, Any]] = []
        for cand in pooled:
            if not any(
                math.hypot(cand["cx_pct"] - k["cx_pct"], cand["cy_pct"] - k["cy_pct"]) <= 7.5
                and abs(cand["r_pct_w"] - k["r_pct_w"]) / max(1.0, k["r_pct_w"]) <= 0.30
                for k in deduped
            ):
                deduped.append(cand)
                if len(deduped) >= max_anchors:
                    break
        return deduped

    return []


def _extract_anchor_pct(anchor_or_list: dict[str, Any] | Sequence[dict[str, Any]]) -> tuple[str, float, float, float]:
    """Normalize an anchor dict (either `0..100` pct or `0..1` fraction) into `(shape, cx_pct, cy_pct, r_pct_w)`."""
    if isinstance(anchor_or_list, Sequence) and not isinstance(anchor_or_list, dict):
        if not anchor_or_list:
            raise ValueError("Empty geometric anchor list passed to solve_geometric_match_cut.")
        anchor = dict(anchor_or_list[0])
    elif isinstance(anchor_or_list, dict):
        anchor = anchor_or_list
    else:
        raise TypeError(f"Expected anchor dict or list[dict], got {type(anchor_or_list)!r}")

    shape = str(anchor.get("shape") or "circle")
    cx = float(anchor.get("cx_pct", 50.0))
    cy = float(anchor.get("cy_pct", 50.0))
    rw = float(anchor.get("r_pct_w", 18.0))

    # Auto-promote [0..1] normalized fractions if caller passed 0.50 instead of 50.0
    if 0.0 < cx <= 1.0 and 0.0 < cy <= 1.0 and 0.0 < rw <= 1.0:
        cx *= 100.0
        cy *= 100.0
        rw *= 100.0
    return shape, cx, cy, max(0.5, rw)


def solve_geometric_match_cut(
    anchor_out: dict[str, Any] | Sequence[dict[str, Any]],
    anchor_in: dict[str, Any] | Sequence[dict[str, Any]],
    canvas_size: tuple[int, int] = (1080, 1920),
) -> dict[str, Any]:
    """
    Geometric Match-Cut Affine Solver (`v6.0.0` @__dviet Era-2 `7707653827016674580`):
      - Computes exact `(scale_in, pos_x_in, pos_y_in)` (plus OpenCV 2x3 `affine_2x3` `(tx_px, ty_px)`)
        so incoming shot `B` locks concentrically onto outgoing shot `A`'s focal object
        (`Δcenter <= 2.0%`, `Δr <= 6.0%`) across a crisp `0`-frame Hard Cut!
      - Uses the `<5.8%` scale and `<1.85%` center tolerance envelope to eliminate border gaps
        whenever physically coverable, and also emits `cover_safe_pair` when `r_in > r_out` so
        dual-clip NLE compilers can push `A` in slightly and guarantee `scale >= 1.02` (`0` borders) on both!
    """
    W, H = int(canvas_size[0]), int(canvas_size[1])
    if W <= 0 or H <= 0:
        raise ValueError(f"Invalid canvas_size={canvas_size!r}")

    shape_out, cx_out_pct, cy_out_pct, r_out_pct = _extract_anchor_pct(anchor_out)
    shape_in, cx_in_pct, cy_in_pct, r_in_pct = _extract_anchor_pct(anchor_in)

    x_target = (cx_out_pct / 100.0) * W
    y_target = (cy_out_pct / 100.0) * H
    r_target_px = (r_out_pct / 100.0) * W

    u_in = (cx_in_pct / 100.0) * W
    v_in = (cy_in_pct / 100.0) * H
    r_in_px = (r_in_pct / 100.0) * W

    # 1. Exact concentric solution (0.00% center error, 0.00% radius error)
    s_exact = r_target_px / max(1e-4, r_in_px)

    # Minimum scale required for incoming B (at exact target center) to cover [0, W] x [0, H] with 0 black borders
    s_cover_exact = max(
        1.0,
        x_target / max(1.0, u_in),
        (W - x_target) / max(1.0, W - u_in),
        y_target / max(1.0, v_in),
        (H - y_target) / max(1.0, H - v_in),
    )

    # Use up to +5.6% scale slack (< 6.0% Δr limit) and <= 1.80% center slack (< 2.0% Δcenter limit)
    # to maximize zero-border coverage automatically!
    s_in = s_exact
    if s_exact < s_cover_exact and s_cover_exact <= s_exact * 1.056:
        s_in = s_cover_exact
    elif s_exact < s_cover_exact and s_exact * 1.056 >= 1.0:
        s_in = s_exact * 1.056

    pos_x_exact = x_target - s_in * (u_in - 0.5 * W)
    pos_y_exact = y_target - s_in * (v_in - 0.5 * H)

    pos_x_in = pos_x_exact
    pos_y_in = pos_y_exact
    if s_in >= 1.0:
        min_px = W * (1.0 - 0.5 * s_in)
        max_px = 0.5 * s_in * W
        min_py = H * (1.0 - 0.5 * s_in)
        max_py = 0.5 * s_in * H
        want_dx = float(np.clip(pos_x_exact, min_px, max_px)) - pos_x_exact
        want_dy = float(np.clip(pos_y_exact, min_py, max_py)) - pos_y_exact
        err_pct = math.hypot(want_dx / float(W), want_dy / float(H)) * 100.0
        if err_pct <= 1.80:
            pos_x_in += want_dx
            pos_y_in += want_dy
        elif err_pct > 1e-6:
            scale_clamp = 1.80 / err_pct
            pos_x_in += want_dx * scale_clamp
            pos_y_in += want_dy * scale_clamp

    tx_in = pos_x_in - s_in * 0.5 * W
    ty_in = pos_y_in - s_in * 0.5 * H

    x_ach = pos_x_in + s_in * (u_in - 0.5 * W)
    y_ach = pos_y_in + s_in * (v_in - 0.5 * H)
    r_ach_px = s_in * r_in_px

    delta_center_pct = math.hypot((x_ach - x_target) / float(W), (y_ach - y_target) / float(H)) * 100.0
    delta_r_pct = (abs(r_ach_px - r_target_px) / max(1e-4, r_target_px)) * 100.0

    covers_canvas = bool(
        s_in >= 1.0 - 1e-5
        and (pos_x_in - 0.5 * s_in * W) <= 0.5
        and (pos_x_in + 0.5 * s_in * W) >= W - 0.5
        and (pos_y_in - 0.5 * s_in * H) <= 0.5
        and (pos_y_in + 0.5 * s_in * H) >= H - 0.5
    )

    # Also solve zero-border reciprocal pair (`scale_out >= 1.02`, `scale_in >= 1.02`) for NLE V1 tracks
    s_out_pair = max(1.02, (1.02 / max(1e-4, s_exact)))
    # Ensure outgoing A at s_out_pair keeping center at canvas center stays in bounds, then lock B at 0.0% error
    x_tgt_pair = 0.5 * W + s_out_pair * (x_target - 0.5 * W)
    y_tgt_pair = 0.5 * H + s_out_pair * (y_target - 0.5 * H)
    x_tgt_pair = float(np.clip(x_tgt_pair, 0.18 * W, 0.82 * W))
    y_tgt_pair = float(np.clip(y_tgt_pair, 0.18 * H, 0.82 * H))
    px_out_pair = x_tgt_pair - s_out_pair * (x_target - 0.5 * W)
    py_out_pair = y_tgt_pair - s_out_pair * (y_target - 0.5 * H)
    s_in_pair = max(
        s_out_pair * s_exact,
        1.02,
        x_tgt_pair / max(1.0, u_in),
        (W - x_tgt_pair) / max(1.0, W - u_in),
        y_tgt_pair / max(1.0, v_in),
        (H - y_tgt_pair) / max(1.0, H - v_in),
    )
    s_out_pair = s_in_pair / max(1e-4, s_exact)
    px_out_pair = float(np.clip(x_tgt_pair - s_out_pair * (x_target - 0.5 * W), W * (1.0 - 0.5 * s_out_pair), 0.5 * s_out_pair * W))
    py_out_pair = float(np.clip(y_tgt_pair - s_out_pair * (y_target - 0.5 * H), H * (1.0 - 0.5 * s_out_pair), 0.5 * s_out_pair * H))
    x_tgt_final = px_out_pair + s_out_pair * (x_target - 0.5 * W)
    y_tgt_final = py_out_pair + s_out_pair * (y_target - 0.5 * H)
    px_in_pair = x_tgt_final - s_in_pair * (u_in - 0.5 * W)
    py_in_pair = y_tgt_final - s_in_pair * (v_in - 0.5 * H)

    return {
        "shape_out": shape_out,
        "shape_in": shape_in,
        "scale_in": round(float(s_in), 5),
        "scale_in_pct": round(float(s_in) * 100.0, 3),
        "pos_x_in": round(float(pos_x_in), 3),
        "pos_y_in": round(float(pos_y_in), 3),
        "dx_in_px": round(float(pos_x_in - 0.5 * W), 3),
        "dy_in_px": round(float(pos_y_in - 0.5 * H), 3),
        "tx_px": round(float(tx_in), 3),
        "ty_px": round(float(ty_in), 3),
        "affine_2x3": [
            [round(float(s_in), 6), 0.0, round(float(tx_in), 4)],
            [0.0, round(float(s_in), 6), round(float(ty_in), 4)],
        ],
        "target_center_px": [round(float(x_target), 2), round(float(y_target), 2)],
        "achieved_center_px": [round(float(x_ach), 2), round(float(y_ach), 2)],
        "delta_center_pct": round(float(delta_center_pct), 4),
        "delta_r_pct": round(float(delta_r_pct), 4),
        "concentric_locked": bool(delta_center_pct <= 2.0 and delta_r_pct <= 6.0),
        "covers_full_canvas": covers_canvas,
        "transition_frames": 0,
        "cut_type": "hard_cut_0f",
        "cover_safe_pair": {
            "scale_out": round(float(s_out_pair), 5),
            "pos_x_out": round(float(px_out_pair), 3),
            "pos_y_out": round(float(py_out_pair), 3),
            "scale_in": round(float(s_in_pair), 5),
            "pos_x_in": round(float(px_in_pair), 3),
            "pos_y_in": round(float(py_in_pair), 3),
        },
    }


def inspect_alpha_prop(png_path: Path, base_dir: Path | None = None) -> dict[str, Any]:
    """
    Inspect an RGBA PNG prop (`3d_*.png` / `*alpha*.png`):
      - Measures tight non-transparent bounding box (`alpha > 10`)
      - Checks 64x64 corners and disconnected connected-components for un-keyed corner/border blocks.
    """
    rel = str(png_path.relative_to(base_dir)) if (base_dir and png_path.is_relative_to(base_dir)) else png_path.name
    with Image.open(png_path) as im:
        rgba = np.asarray(im.convert("RGBA"))
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    mask = (alpha > 15).astype(np.uint8)
    ys, xs = np.where(mask > 0)

    if len(ys) == 0:
        return {
            "file": rel,
            "size": [w, h],
            "alpha_bbox": None,
            "opaque_ratio": 0.0,
            "corner_opaque_pixels": {"tl": 0, "tr": 0, "bl": 0, "br": 0},
            "disconnected_components": 0,
            "suspicious_unkeyed_blocks": True,
            "warnings": ["Completely transparent PNG (0 opaque pixels)"],
        }

    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    cp = min(64, w // 4, h // 4)
    corners = {
        "tl": int(mask[:cp, :cp].sum()),
        "tr": int(mask[:cp, w - cp :].sum()),
        "bl": int(mask[h - cp :, :cp].sum()),
        "br": int(mask[h - cp :, w - cp :].sum()),
    }

    n_lbl, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    comps = []
    edge_margin = max(8, int(min(w, h) * 0.035))
    for idx in range(1, n_lbl):
        cx, cy, cw, ch, area = (int(stats[idx, k]) for k in range(5))
        if area >= 60:
            touches_edge = (
                cx <= edge_margin
                or cy <= edge_margin
                or (cx + cw) >= (w - edge_margin)
                or (cy + ch) >= (h - edge_margin)
            )
            comps.append({"bbox": [cx, cy, cx + cw, cy + ch], "area": area, "touches_edge": touches_edge})
    comps.sort(key=lambda c: c["area"], reverse=True)

    warnings: list[str] = []
    bad_corners = [k for k, v in corners.items() if v >= 120]
    if bad_corners:
        warnings.append(
            f"Opaque corner region detected in {', '.join(bad_corners)} "
            f"({', '.join(f'{k}={corners[k]}' for k in bad_corners)})"
        )
    if len(comps) > 1:
        sec_large = [c for c in comps[1:] if c["area"] >= 400 or (c["touches_edge"] and c["area"] >= 100)]
        if sec_large:
            warnings.append(
                f"{len(sec_large)} disconnected secondary alpha block(s) "
                f"(largest={sec_large[0]['area']}px at {sec_large[0]['bbox']})"
            )

    return {
        "file": rel,
        "size": [w, h],
        "alpha_bbox": bbox,
        "opaque_ratio": round(float(mask.mean()), 4),
        "corner_opaque_pixels": corners,
        "significant_component_count": len(comps),
        "secondary_components": comps[1:5],
        "suspicious_unkeyed_blocks": len(warnings) > 0,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# FilmCraft `.fcproj` (v15 / v17+) Structural Parser & Defect Auditor
# ---------------------------------------------------------------------------


def _contains_none(obj: Any, prefix: str = "") -> list[str]:
    """Recursively find any None/null values inside a transition/effect parameter dict."""
    hits: list[str] = []
    if obj is None:
        hits.append(prefix or "root")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(_contains_none(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            hits.extend(_contains_none(v, f"{prefix}[{idx}]"))
    return hits


def resolve_fcproj_media_path(raw_path: str, fcproj_dir: Path) -> Path:
    """Resolve a path stored inside `.fcproj` against the project directory."""
    p = Path(raw_path)
    if p.is_absolute() and p.exists():
        return p
    cand = fcproj_dir / raw_path
    if cand.exists():
        return cand
    # Try stripping leading absolute prefix up to `assets/`
    if "assets/" in raw_path:
        rel_part = "assets/" + raw_path.split("assets/", 1)[1]
        cand2 = fcproj_dir / rel_part
        if cand2.exists():
            return cand2
    return p if p.is_absolute() else cand


def audit_fcproj(
    fcproj_path: Path,
    base_dir: Path,
    probed_media: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Parse FilmCraft `.fcproj` (schema v15/v17+) and output objective structural & defect telemetry:
      - Track counts & clip counts
      - Static PNG keyword count (`kw_*.png` or image keywords on text tracks)
      - Text-track transition defects
      - `null` transition params & single-sided transitions
      - Non-uniform scale defects (`uniform_scale=False` or asymmetric `scale_height` vs `scale_width`)
      - Voice & media EOF overruns (`source_in + duration > actual_dur`)
      - V1 & A1 timeline extraction (preserving lip-sync `source_in` ticks!)
    """
    fc_data = json.loads(fcproj_path.read_text(encoding="utf-8"))
    proj = fc_data.get("project") or {}
    raw_items = proj.get("items") or {}

    items_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw_items, dict):
        for k, v in raw_items.items():
            if isinstance(v, dict):
                items_by_id[str(k)] = v
    elif isinstance(raw_items, list):
        for v in raw_items:
            if isinstance(v, dict) and "id" in v:
                items_by_id[str(v["id"])] = v

    # Locate primary Sequence object
    seq_obj: dict[str, Any] | None = None
    seq_name: str = proj.get("name") or fcproj_path.stem

    for it in items_by_id.values():
        knd = it.get("kind")
        if isinstance(knd, dict) and isinstance(knd.get("Sequence"), dict):
            seq_obj = knd["Sequence"]
            seq_name = it.get("name") or seq_name
            break

    if seq_obj is None:
        def _scan_seq(node: Any) -> None:
            nonlocal seq_obj
            if seq_obj is not None:
                return
            if isinstance(node, dict):
                if "video_tracks" in node and "audio_tracks" in node:
                    seq_obj = node
                    return
                for val in node.values():
                    _scan_seq(val)
            elif isinstance(node, list):
                for val in node:
                    _scan_seq(val)

        _scan_seq(proj)

    # Map item_id -> media info
    media_ref_map: dict[str, dict[str, Any]] = {}
    referenced_files: list[Path] = []
    missing_media_files: list[str] = []

    for iid, it in items_by_id.items():
        knd = it.get("kind") or {}
        if "Media" in knd and isinstance(knd["Media"], dict):
            m_inner = knd["Media"].get("media") or {}
            info_inner = knd["Media"].get("info") or {}
            if "File" in m_inner and isinstance(m_inner["File"], dict):
                raw_p = str(m_inner["File"].get("path") or "")
                resolved_p = resolve_fcproj_media_path(raw_p, base_dir)
                if raw_p:
                    if resolved_p.is_file():
                        referenced_files.append(resolved_p)
                    else:
                        missing_media_files.append(raw_p)
                media_ref_map[iid] = {
                    "item_kind": "File",
                    "name": it.get("name") or Path(raw_p).name,
                    "raw_path": raw_p,
                    "resolved_path": str(resolved_p),
                    "fc_duration_s": round(float(info_inner.get("duration") or 0) / TICKS_PER_SEC, 6)
                    if info_inner.get("duration")
                    else None,
                }
            elif "Generator" in m_inner:
                gen_type = next(iter(m_inner["Generator"].keys()), "Generator") if isinstance(m_inner["Generator"], dict) else "Generator"
                media_ref_map[iid] = {"item_kind": f"Generator:{gen_type}", "name": it.get("name") or gen_type, "raw_path": None}
        elif "Graphic" in knd:
            media_ref_map[iid] = {"item_kind": "Graphic", "name": it.get("name") or "Graphic", "raw_path": None}

    if seq_obj is None:
        return {
            "fcproj_path": str(fcproj_path.resolve()),
            "schema_version": fc_data.get("schema_version"),
            "generator": fc_data.get("generator"),
            "error": "No Sequence found in .fcproj",
        }

    seq_settings = seq_obj.get("settings") or {}
    fr_obj = seq_settings.get("frame_rate") or {}
    seq_fps = (
        round(float(fr_obj.get("num", 30)) / float(fr_obj.get("den", 1)), 4)
        if isinstance(fr_obj, dict) and fr_obj.get("den")
        else 30.0
    )
    seq_w = int(seq_settings.get("width") or 1080)
    seq_h = int(seq_settings.get("height") or 1920)
    mark_out_ticks = seq_obj.get("mark_out") or 0

    v_tracks = seq_obj.get("video_tracks") or []
    a_tracks = seq_obj.get("audio_tracks") or []

    # Lookup actual probed duration by resolved path or relative path
    dur_by_resolved: dict[str, float] = {}
    if probed_media:
        for rel_k, pinfo in probed_media.items():
            cand_p = (base_dir / rel_k).resolve() if not Path(rel_k).is_absolute() else Path(rel_k).resolve()
            dur_by_resolved[str(cand_p)] = float(pinfo.get("dur") or 0.0)
            dur_by_resolved[rel_k] = float(pinfo.get("dur") or 0.0)

    def lookup_actual_dur(mref: dict[str, Any]) -> float | None:
        rp = mref.get("resolved_path")
        if rp:
            rp_abs = str(Path(rp).resolve())
            if rp_abs in dur_by_resolved:
                return dur_by_resolved[rp_abs]
        raw_p = mref.get("raw_path")
        if raw_p and raw_p in dur_by_resolved:
            return dur_by_resolved[raw_p]
        return None

    static_png_kw_clips: list[dict[str, Any]] = []
    text_track_transitions: list[dict[str, Any]] = []
    null_transition_params: list[dict[str, Any]] = []
    single_sided_transitions: list[dict[str, Any]] = []
    non_uniform_scale_defects: list[dict[str, Any]] = []
    voice_eof_overruns: list[dict[str, Any]] = []
    other_media_eof_overruns: list[dict[str, Any]] = []

    video_track_summaries: list[dict[str, Any]] = []
    audio_track_summaries: list[dict[str, Any]] = []
    max_tl_end_s = round(float(mark_out_ticks) / TICKS_PER_SEC, 6) if mark_out_ticks else 0.0

    for ti, vt in enumerate(v_tracks):
        tname = str(vt.get("name") or f"V{ti + 1}")
        tname_l = tname.lower()
        t_items = vt.get("items") or vt.get("clips") or []
        t_trans = vt.get("transitions") or []

        has_graphic_items = False
        for cl in t_items:
            iid = str(cl.get("item"))
            mref = media_ref_map.get(iid, {})
            raw_p = str(mref.get("raw_path") or "")
            fname = Path(raw_p).name.lower() if raw_p else ""
            cl_start_s = round(float(cl.get("start") or 0) / TICKS_PER_SEC, 4)
            cl_dur_s = round(float(cl.get("duration") or 0) / TICKS_PER_SEC, 4)
            cl_src_in_s = round(float(cl.get("source_in") or 0) / TICKS_PER_SEC, 4)
            max_tl_end_s = max(max_tl_end_s, round(cl_start_s + cl_dur_s, 6))

            if mref.get("item_kind") == "Graphic" or any(ef.get("effect") == "graphic_text" for ef in (cl.get("effects") or [])):
                has_graphic_items = True

            # 1) Static PNG keyword detection
            is_kw_png = fname.startswith("kw_") and fname.endswith(".png")
            is_png_on_text_track = fname.endswith(".png") and any(
                tag in tname_l for tag in ("text", "chữ", "phụ đề", "kw", "sub")
            )
            if is_kw_png or is_png_on_text_track:
                static_png_kw_clips.append({
                    "track_index": ti,
                    "track_name": tname,
                    "clip_name": cl.get("name"),
                    "file": raw_p,
                    "at_s": cl_start_s,
                    "dur_s": cl_dur_s,
                })

            # 2) Non-uniform scale defect detection
            for ef in cl.get("effects") or []:
                ef_name = ef.get("effect")
                if ef_name not in ("motion", "transform", "graphic_text"):
                    continue
                pm = ef.get("params") or {}
                uni_val = pm.get("uniform_scale", {}).get("value", {})
                uni_bool = uni_val.get("Bool", True) if isinstance(uni_val, dict) else True

                if uni_bool is False:
                    non_uniform_scale_defects.append({
                        "track_index": ti,
                        "track_name": tname,
                        "clip_name": cl.get("name"),
                        "effect": ef_name,
                        "reason": "uniform_scale=False",
                    })
                elif ef_name == "transform":
                    sh_obj = pm.get("scale_height") or {}
                    sw_obj = pm.get("scale_width") or {}
                    sh_v = (sh_obj.get("value") or {}).get("Float", 100.0)
                    sw_v = (sw_obj.get("value") or {}).get("Float", 100.0)
                    sh_kf = sh_obj.get("keyframes") or []
                    sw_kf = sw_obj.get("keyframes") or []
                    sh_kf_vals = [(k.get("time"), (k.get("value") or {}).get("Float")) for k in sh_kf]
                    sw_kf_vals = [(k.get("time"), (k.get("value") or {}).get("Float")) for k in sw_kf]
                    if abs(float(sh_v) - float(sw_v)) > 0.05 or sh_kf_vals != sw_kf_vals:
                        non_uniform_scale_defects.append({
                            "track_index": ti,
                            "track_name": tname,
                            "clip_name": cl.get("name"),
                            "effect": "transform",
                            "reason": f"asymmetric_transform_scale(sh={sh_v}/kf={len(sh_kf)}, sw={sw_v}/kf={len(sw_kf)})",
                        })

            # 3) Video clip EOF overrun check (for Movie files, not Still images)
            if mref.get("item_kind") == "File" and raw_p and Path(raw_p).suffix.lower() in VIDEO_EXTS:
                act_dur = lookup_actual_dur(mref)
                speed = float(cl.get("speed") or 1.0)
                needed_end = cl_src_in_s + cl_dur_s * speed
                if act_dur and act_dur > 0 and needed_end > act_dur + 1e-4:
                    other_media_eof_overruns.append({
                        "track_type": "video",
                        "track_index": ti,
                        "track_name": tname,
                        "clip_name": cl.get("name"),
                        "file": raw_p,
                        "src_in_s": cl_src_in_s,
                        "clip_dur_s": cl_dur_s,
                        "clip_end_s": round(needed_end, 6),
                        "actual_dur_s": round(act_dur, 6),
                        "overrun_ms": round((needed_end - act_dur) * 1000.0, 3),
                    })

        is_shade_or_matte = any(tag in tname_l for tag in ("dải tối", "shade", "matte", "vignette"))
        is_text_track = (not is_shade_or_matte) and (
            has_graphic_items
            or any(tag in tname_l for tag in ("text", "chữ", "phụ đề", "caption", "sub", "kw"))
        )

        # Inspect transitions on video track
        for tr_obj in t_trans:
            ef_obj = tr_obj.get("effect") or {}
            ef_name = ef_obj.get("effect") if isinstance(ef_obj, dict) else str(ef_obj)
            params_obj = ef_obj.get("params") if isinstance(ef_obj, dict) else {}
            tr_start_s = round(float(tr_obj.get("start") or 0) / TICKS_PER_SEC, 4)
            tr_dur_s = round(float(tr_obj.get("duration") or 0) / TICKS_PER_SEC, 4)

            if is_text_track:
                text_track_transitions.append({
                    "track_index": ti,
                    "track_name": tname,
                    "transition_id": tr_obj.get("id"),
                    "effect": ef_name,
                    "start_s": tr_start_s,
                    "dur_s": tr_dur_s,
                })

            null_paths = _contains_none(params_obj)
            if null_paths:
                null_transition_params.append({
                    "track_type": "video",
                    "track_index": ti,
                    "track_name": tname,
                    "transition_id": tr_obj.get("id"),
                    "effect": ef_name,
                    "start_s": tr_start_s,
                    "null_fields": null_paths,
                })

            if tr_obj.get("from") is None or tr_obj.get("to") is None:
                single_sided_transitions.append({
                    "track_type": "video",
                    "track_index": ti,
                    "track_name": tname,
                    "transition_id": tr_obj.get("id"),
                    "effect": ef_name,
                    "from": tr_obj.get("from"),
                    "to": tr_obj.get("to"),
                    "align": tr_obj.get("align"),
                })

        video_track_summaries.append({
            "index": ti,
            "name": tname,
            "is_text_track": is_text_track,
            "item_count": len(t_items),
            "transition_count": len(t_trans),
        })

    # Inspect audio tracks
    for ti, at in enumerate(a_tracks):
        tname = str(at.get("name") or f"A{ti + 1}")
        tname_l = tname.lower()
        t_items = at.get("items") or at.get("clips") or []
        t_trans = at.get("transitions") or []
        is_voice_track = (ti == 0 and any(k in tname_l for k in ("giọng", "voice", "a1", "thoại"))) or ("voice" in tname_l or "giọng" in tname_l)

        for cl in t_items:
            iid = str(cl.get("item"))
            mref = media_ref_map.get(iid, {})
            raw_p = str(mref.get("raw_path") or "")
            cl_start_s = round(float(cl.get("start") or 0) / TICKS_PER_SEC, 6)
            cl_dur_s = round(float(cl.get("duration") or 0) / TICKS_PER_SEC, 6)
            cl_src_in_s = round(float(cl.get("source_in") or 0) / TICKS_PER_SEC, 6)
            max_tl_end_s = max(max_tl_end_s, round(cl_start_s + cl_dur_s, 6))

            act_dur = lookup_actual_dur(mref)
            speed = float(cl.get("speed") or 1.0)
            needed_end = cl_src_in_s + cl_dur_s * speed
            file_is_voice = is_voice_track or ("voice" in raw_p.lower())

            if act_dur and act_dur > 0 and needed_end > act_dur + 1e-5:
                rec = {
                    "track_index": ti,
                    "track_name": tname,
                    "clip_name": cl.get("name"),
                    "file": raw_p,
                    "tl_start_s": round(cl_start_s, 4),
                    "src_in_s": round(cl_src_in_s, 6),
                    "clip_dur_s": round(cl_dur_s, 6),
                    "clip_end_s": round(needed_end, 6),
                    "actual_dur_s": round(act_dur, 6),
                    "overrun_ms": round((needed_end - act_dur) * 1000.0, 3),
                }
                if file_is_voice:
                    voice_eof_overruns.append(rec)
                else:
                    other_media_eof_overruns.append({"track_type": "audio", **rec})

        for tr_obj in t_trans:
            ef_obj = tr_obj.get("effect") or {}
            params_obj = ef_obj.get("params") if isinstance(ef_obj, dict) else {}
            null_paths = _contains_none(params_obj)
            if null_paths:
                null_transition_params.append({
                    "track_type": "audio",
                    "track_index": ti,
                    "track_name": tname,
                    "transition_id": tr_obj.get("id"),
                    "effect": ef_obj.get("effect") if isinstance(ef_obj, dict) else str(ef_obj),
                    "null_fields": null_paths,
                })

        audio_track_summaries.append({
            "index": ti,
            "name": tname,
            "is_voice_track": is_voice_track,
            "item_count": len(t_items),
            "transition_count": len(t_trans),
        })

    # Extract V1 & A1 timelines for lip-sync reference (compatible with turbo_bs_pipeline `old_v1`)
    v1_timeline = []
    if v_tracks:
        for cl in v_tracks[0].get("items") or []:
            mref = media_ref_map.get(str(cl.get("item")), {})
            v1_timeline.append({
                "name": cl.get("name"),
                "file": mref.get("raw_path"),
                "tl_s": round(float(cl.get("start") or 0) / TICKS_PER_SEC, 4),
                "dur_s": round(float(cl.get("duration") or 0) / TICKS_PER_SEC, 4),
                "src_in_s": round(float(cl.get("source_in") or 0) / TICKS_PER_SEC, 4),
            })

    a1_timeline = []
    if a_tracks:
        for cl in a_tracks[0].get("items") or []:
            mref = media_ref_map.get(str(cl.get("item")), {})
            a1_timeline.append({
                "name": cl.get("name"),
                "file": mref.get("raw_path"),
                "resolved_path": mref.get("resolved_path"),
                "tl_s": round(float(cl.get("start") or 0) / TICKS_PER_SEC, 4),
                "dur_s": round(float(cl.get("duration") or 0) / TICKS_PER_SEC, 4),
                "src_in_s": round(float(cl.get("source_in") or 0) / TICKS_PER_SEC, 4),
                "gain_db": cl.get("gain_db", 0.0),
            })

    severe_voice_overruns = [x for x in voice_eof_overruns if x["overrun_ms"] >= 1.0]
    warnings: list[str] = []
    if static_png_kw_clips:
        warnings.append(f"{len(static_png_kw_clips)} static PNG keyword clip(s) found on timeline")
    if text_track_transitions:
        warnings.append(f"{len(text_track_transitions)} text-track transition defect(s) found")
    if null_transition_params:
        warnings.append(f"{len(null_transition_params)} transition(s) contain null effect parameter(s)")
    if non_uniform_scale_defects:
        warnings.append(f"{len(non_uniform_scale_defects)} clip(s) have non-uniform/asymmetric scale parameters")
    if voice_eof_overruns:
        max_ov = max(x["overrun_ms"] for x in voice_eof_overruns)
        warnings.append(
            f"{len(voice_eof_overruns)} voice clip EOF overrun(s) "
            f"({len(severe_voice_overruns)} >= 1.0ms, max={max_ov:.2f}ms)"
        )
    if other_media_eof_overruns:
        warnings.append(f"{len(other_media_eof_overruns)} non-voice media clip EOF overrun(s)")
    if missing_media_files:
        warnings.append(f"{len(missing_media_files)} missing referenced media file(s)")

    return {
        "fcproj_path": str(fcproj_path.resolve()),
        "sequence_name": seq_name,
        "schema_version": fc_data.get("schema_version"),
        "generator": fc_data.get("generator"),
        "sequence_settings": {
            "width": seq_w,
            "height": seq_h,
            "fps": seq_fps,
            "sample_rate": seq_settings.get("sample_rate", 48000),
            "duration_sec": round(max_tl_end_s, 4),
        },
        "track_counts": {
            "video_tracks": len(v_tracks),
            "audio_tracks": len(a_tracks),
            "total_video_clips": sum(t["item_count"] for t in video_track_summaries),
            "total_audio_clips": sum(t["item_count"] for t in audio_track_summaries),
        },
        "video_tracks": video_track_summaries,
        "audio_tracks": audio_track_summaries,
        "static_png_keyword_count": len(static_png_kw_clips),
        "static_png_keyword_clips": static_png_kw_clips,
        "text_track_transition_defect_count": len(text_track_transitions),
        "text_track_transitions": text_track_transitions,
        "null_transition_param_count": len(null_transition_params),
        "null_transition_params": null_transition_params,
        "single_sided_transition_count": len(single_sided_transitions),
        "non_uniform_scale_defect_count": len(non_uniform_scale_defects),
        "non_uniform_scale_defects": non_uniform_scale_defects[:40],
        "voice_eof_overrun_count": len(voice_eof_overruns),
        "severe_voice_eof_overrun_count": len(severe_voice_overruns),
        "voice_eof_overruns": voice_eof_overruns,
        "other_media_eof_overrun_count": len(other_media_eof_overruns),
        "other_media_eof_overruns": other_media_eof_overruns,
        "missing_media_files": sorted(set(missing_media_files)),
        "referenced_files": [str(p.resolve()) for p in sorted(set(referenced_files))],
        "v1_timeline": v1_timeline,
        "a1_timeline": a1_timeline,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Multi-Thread Contact Sheet Builder
# ---------------------------------------------------------------------------


def _grab_video_frame(job: tuple[str, Path, float, Path, int]) -> tuple[str, Path, Path]:
    label, video_path, ts, out_path, tile_w = job
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{max(0.0, ts):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={tile_w}:-2",
            "-q:v",
            "4",
            str(out_path),
        ],
        capture_output=True,
    )
    return label, out_path, video_path


def render_raw_video_contact_sheet(
    media_path: Path,
    duration_sec: float,
    has_video: bool,
    work_dir: Path,
    audio_pcm_16k: np.ndarray | None = None,
    num_samples: int = 24,
) -> tuple[Path, list[Path]]:
    """Sample 24 evenly-spaced frames via 12-thread ffmpeg into `assets_contact_sheet.jpg`."""
    frames_dir = work_dir / "asset_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = work_dir / "assets_contact_sheet.jpg"

    if not has_video or duration_sec <= 0.0:
        # Audio-only contact sheet: clean waveform plot
        w_img, h_img = 1620, 420
        sheet = Image.new("RGB", (w_img, h_img), (18, 20, 26))
        dr = ImageDraw.Draw(sheet)
        dr.text((20, 16), f"AUDIO WAVEFORM · {media_path.name} ({duration_sec:.2f}s)", fill=(94, 234, 212))
        if audio_pcm_16k is not None and len(audio_pcm_16k) > 100:
            bins = w_img - 40
            chunk = max(1, len(audio_pcm_16k) // bins)
            trimmed = audio_pcm_16k[: bins * chunk].reshape((bins, chunk))
            peaks = np.abs(trimmed).max(axis=1)
            mid_y = h_img // 2 + 12
            amp = (h_img - 90) * 0.46
            for ix, pk in enumerate(peaks):
                dy = int(min(1.0, float(pk)) * amp)
                dr.line([(20 + ix, mid_y - dy), (20 + ix, mid_y + dy)], fill=(56, 189, 248))
        sheet.save(sheet_path, quality=88)
        return sheet_path, []

    n = max(1, num_samples)
    jobs: list[tuple[str, Path, float, Path, int]] = []
    for i in range(n):
        ts = min(max(0.0, duration_sec - 0.04), duration_sec * (i + 0.5) / n)
        lbl = f"#{i + 1:02d} {ts:05.2f}s"
        out_f = frames_dir / f"raw_{i:02d}_{ts:06.2f}.jpg"
        jobs.append((lbl, media_path, ts, out_f, 270))

    with ThreadPoolExecutor(max_workers=12) as ex:
        grabbed = list(ex.map(_grab_video_frame, jobs))

    valid_tiles = [(lbl, p) for lbl, p, _ in grabbed if p.is_file()]
    if not valid_tiles:
        sheet = Image.new("RGB", (1080, 360), (18, 20, 26))
        sheet.save(sheet_path, quality=88)
        return sheet_path, []

    with Image.open(valid_tiles[0][1]) as first_im:
        tw, th = first_im.size
    cols = 6
    rows = max(1, (len(valid_tiles) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th), (18, 20, 26))
    dr = ImageDraw.Draw(sheet)

    for idx, (lbl, p) in enumerate(valid_tiles):
        with Image.open(p) as im:
            rgb = im.convert("RGB")
            if rgb.size != (tw, th):
                rgb = rgb.resize((tw, th), Image.Resampling.BILINEAR)
            x, y = (idx % cols) * tw, (idx // cols) * th
            sheet.paste(rgb, (x, y))
            dr.rectangle([x + 4, y + 4, x + min(tw - 6, 140), y + 24], fill=(0, 0, 0))
            dr.text((x + 8, y + 7), lbl, fill=(94, 234, 212))

    sheet.save(sheet_path, quality=88)
    return sheet_path, [p for _, p in valid_tiles]


def render_bundle_contact_sheet(
    video_files: list[Path],
    prop_pngs: list[Path],
    probed: dict[str, dict[str, Any]],
    base_dir: Path,
    work_dir: Path,
    aroll_samples: int = 8,
) -> tuple[Path, dict[str, list[Path]], list[dict[str, Any]]]:
    """
    Render multi-thread `assets_contact_sheet.jpg` across all bundle video clips and `3d_*.png`
    alpha props, returning `(sheet_path, sampled_frames_by_video_rel, alpha_prop_checks)`.
    """
    frames_dir = work_dir / "asset_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = work_dir / "assets_contact_sheet.jpg"

    jobs: list[tuple[str, Path, float, Path, int]] = []
    sheet_keep_indices: set[int] = set()
    for vp in video_files:
        rel_k = str(vp.relative_to(base_dir)) if vp.is_relative_to(base_dir) else vp.name
        vdur = float(probed.get(rel_k, {}).get("dur") or 0.0)
        if vdur <= 0.05:
            continue
        is_ovl = "ovl_" in vp.name.lower() or "overlay" in vp.name.lower() or "overlays" in [pt.lower() for pt in vp.parts]
        is_aroll = "a-roll" in rel_k.lower() or "aroll" in rel_k.lower() or len(video_files) <= 4
        if is_ovl:
            ratios = [0.45]
            sheet_idxs = {0}
        elif is_aroll and aroll_samples > 4:
            ratios = [(i + 0.5) / aroll_samples for i in range(aroll_samples)]
            sheet_idxs = {int(round(k * (aroll_samples - 1) / 3.0)) for k in range(4)}
        else:
            ratios = [0.12, 0.38, 0.65, 0.88]
            sheet_idxs = {0, 1, 2, 3}
        for r_idx, r in enumerate(ratios):
            pt = round(min(max(0.0, vdur - 0.05), vdur * r), 3)
            tag = f"{vp.stem[:12]}@{pt:04.1f}s"
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{vp.stem}_{r_idx:02d}_{pt:05.2f}.jpg")
            if r_idx in sheet_idxs:
                sheet_keep_indices.add(len(jobs))
            jobs.append((tag, vp, pt, frames_dir / safe_name, 270))

    grabbed: list[tuple[str, Path, Path]] = []
    if jobs:
        with ThreadPoolExecutor(max_workers=min(12, len(jobs))) as ex:
            grabbed = list(ex.map(_grab_video_frame, jobs))

    frames_by_video: dict[str, list[Path]] = {}
    tiles: list[tuple[str, Path, bool]] = []
    for j_idx, (lbl, out_p, src_vp) in enumerate(grabbed):
        if out_p.is_file():
            rel_v = str(src_vp.relative_to(base_dir)) if src_vp.is_relative_to(base_dir) else src_vp.name
            frames_by_video.setdefault(rel_v, []).append(out_p)
            if j_idx in sheet_keep_indices:
                tiles.append((lbl, out_p, False))

    alpha_checks: list[dict[str, Any]] = []
    for p3 in prop_pngs:
        chk = inspect_alpha_prop(p3, base_dir)
        alpha_checks.append(chk)
        try:
            with Image.open(p3) as im_raw:
                im_rgba = im_raw.convert("RGBA")
                # Subtle two-tone dark checkerboard so un-keyed corner blocks stand out clearly
                bg = Image.new("RGBA", im_rgba.size, (28, 32, 42, 255))
                bg_dr = ImageDraw.Draw(bg)
                step = max(24, min(im_rgba.size) // 12)
                for cy in range(0, im_rgba.size[1], step):
                    for cx in range(0, im_rgba.size[0], step):
                        if ((cx // step) + (cy // step)) % 2 == 1:
                            bg_dr.rectangle([cx, cy, cx + step, cy + step], fill=(38, 44, 58, 255))
                bg.alpha_composite(im_rgba)
                if chk["alpha_bbox"]:
                    bx1, by1, bx2, by2 = chk["alpha_bbox"]
                    box_col = (255, 70, 70, 255) if chk["suspicious_unkeyed_blocks"] else (45, 212, 191, 220)
                    ImageDraw.Draw(bg).rectangle([bx1, by1, bx2, by2], outline=box_col, width=3)
                # Fit inside 270x480 tile preserving aspect
                canvas = Image.new("RGB", (270, 480), (18, 20, 26))
                scale = min(254.0 / max(1, bg.width), 410.0 / max(1, bg.height))
                nw, nh = max(1, int(round(bg.width * scale))), max(1, int(round(bg.height * scale)))
                thumb = bg.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
                canvas.paste(thumb, ((270 - nw) // 2, 42 + (420 - nh) // 2))
                out_prop = frames_dir / f"prop_{p3.stem}.jpg"
                canvas.save(out_prop, quality=88)
                lbl_p = f"{'WARN!' if chk['suspicious_unkeyed_blocks'] else 'PROP'} {p3.stem[:14]}"
                tiles.append((lbl_p, out_prop, chk["suspicious_unkeyed_blocks"]))
        except Exception as exc:
            chk["warnings"].append(f"Thumbnail render error: {exc}")

    tile_w, tile_h = 270, 480
    cols = 6
    rows = max(1, (len(tiles) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (18, 20, 26))
    dr = ImageDraw.Draw(sheet)

    for idx, (lbl, p, is_warn) in enumerate(tiles):
        if not p.is_file():
            continue
        with Image.open(p) as im:
            rgb = im.convert("RGB")
            if rgb.size != (tile_w, tile_h):
                canvas = Image.new("RGB", (tile_w, tile_h), (18, 20, 26))
                sc = min(tile_w / max(1, rgb.width), tile_h / max(1, rgb.height))
                nw, nh = max(1, int(round(rgb.width * sc))), max(1, int(round(rgb.height * sc)))
                canvas.paste(rgb.resize((nw, nh), Image.Resampling.BILINEAR), ((tile_w - nw) // 2, (tile_h - nh) // 2))
                rgb = canvas
            x, y = (idx % cols) * tile_w, (idx // cols) * tile_h
            sheet.paste(rgb, (x, y))
            badge_bg = (145, 24, 24) if is_warn else (0, 0, 0)
            badge_fg = (255, 228, 228) if is_warn else (94, 234, 212)
            dr.rectangle([x + 4, y + 4, x + min(tile_w - 6, 210), y + 26], fill=badge_bg)
            dr.text((x + 8, y + 7), lbl, fill=badge_fg)

    sheet.save(sheet_path, quality=88)
    return sheet_path, frames_by_video, alpha_checks


# ---------------------------------------------------------------------------
# Fast 16kHz PCM Decoding & Single-Pass `faster-whisper` Transcription
# ---------------------------------------------------------------------------


def decode_16k_f32_pcm(audio_path: Path, max_dur_sec: float | None = None) -> np.ndarray:
    """Decode any media file's audio stream into a 16kHz mono float32 numpy array in RAM."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(audio_path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    raw = subprocess.check_output(cmd)
    arr = np.frombuffer(raw, dtype=np.float32).copy()
    if max_dur_sec is not None:
        max_samples = int(round(max_dur_sec * 16000))
        arr = arr[:max_samples]
    return arr


def _resolve_whisper_model_name(
    requested_model: str,
    execution_tier: str,
    has_ground_truth_script: bool,
) -> str:
    """Use locally-cached `base` in `fast` tier when ground-truth script guarantees zero-typo alignment."""
    if requested_model == "auto":
        if execution_tier == "fast" and has_ground_truth_script:
            return "base"
        return "small"
    if requested_model == "small" and execution_tier == "fast" and has_ground_truth_script:
        hf_base = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-base"
        if hf_base.is_dir():
            return "base"
    return requested_model


def run_single_pass_whisper(
    pcm_16k: np.ndarray,
    whisper_model_name: str = "small",
    language: str = "vi",
    has_ground_truth_script: bool = False,
    script_hint: str | None = None,
    use_vad: bool = False,
) -> tuple[list[list[Any]], list[dict[str, Any]]]:
    """
    Run single-pass `faster-whisper` (`int8`, `word_timestamps=True`) on a 16kHz mono float32 RAM buffer.
    Uses `vad_filter=True` on long raw recordings (`use_vad=True`) to skip dead air for ~2.5x speedup.
    """
    from faster_whisper import WhisperModel

    if len(pcm_16k) < 400:
        return [], []

    # Physical core count + deterministic temperature=0.0 avoids SMT spin-locks & 6x fallback retries
    cpu_threads = min(6, max(4, (os.cpu_count() or 8) // 2))
    beam_size = 1 if (has_ground_truth_script or use_vad) else 2

    try:
        model = WhisperModel(whisper_model_name, device="cpu", compute_type="int8", cpu_threads=cpu_threads)
    except Exception:
        if whisper_model_name != "small":
            model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=cpu_threads)
        else:
            raise
    lang_arg = None if language == "auto" else language
    transcribe_kwargs: dict[str, Any] = {
        "language": lang_arg,
        "word_timestamps": True,
        "vad_filter": bool(use_vad),
        "beam_size": beam_size,
        "temperature": 0.0,
        "condition_on_previous_text": False,
    }
    if use_vad:
        transcribe_kwargs["vad_parameters"] = {"min_silence_duration_ms": 500, "speech_pad_ms": 250}

    segs_gen, _ = model.transcribe(pcm_16k, **transcribe_kwargs)

    raw_words: list[list[Any]] = []
    speech_segments: list[dict[str, Any]] = []
    for idx, sg in enumerate(segs_gen):
        seg_words: list[list[Any]] = []
        for w in sg.words or []:
            wt = nfc(w.word).strip()
            if wt:
                rec = [wt, round(float(w.start), 4), round(float(w.end), 4)]
                raw_words.append(rec)
                seg_words.append(rec)
        seg_txt = nfc(sg.text).strip()
        if seg_txt or seg_words:
            s_t = round(float(sg.start), 4)
            e_t = round(float(sg.end), 4)
            speech_segments.append({
                "id": idx,
                "start": s_t,
                "end": e_t,
                "dur": round(max(0.0, e_t - s_t), 4),
                "text": seg_txt,
                "words": seg_words,
            })

    return raw_words, speech_segments


# ---------------------------------------------------------------------------
# Voice Slice Discovery & Strict EOF-Clamped Concatenation
# ---------------------------------------------------------------------------


def _slice_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(?:voice_s|^s|^)(\d+)", path.stem.lower())
    if m:
        return (int(m.group(1)), path.name.lower())
    nums = re.findall(r"\d+", path.stem)
    return (int(nums[0]) if nums else 999999, path.name.lower())


def discover_voice_slices(
    base_dir: Path,
    all_media_files: list[Path],
    fcproj_audit: dict[str, Any] | None = None,
) -> list[Path]:
    """
    Discover ordered voice slice files in a bundle or `.fcproj`:
      1. `assets/voice/voice_s*.wav` / `.mp3`
      2. `*_voice*.wav` / `*_voice*.mp3` / `voice_*.wav`
      3. Referenced `A1` voice files from `.fcproj` if present and distinct
    """
    voice_dir = base_dir / "assets" / "voice"
    if voice_dir.is_dir():
        v_s = [p for p in voice_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS and re.match(r"^voice_s\d+", p.stem.lower())]
        if v_s:
            return sorted(v_s, key=_slice_sort_key)
        v_any = [p for p in voice_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
        if v_any:
            return sorted(v_any, key=_slice_sort_key)

    tagged_voice = [
        p for p in all_media_files
        if p.suffix.lower() in AUDIO_EXTS
        and (p.stem.lower().startswith("voice_s") or "_voice" in p.stem.lower() or p.stem.lower().startswith("voice_"))
    ]
    if tagged_voice:
        return sorted(tagged_voice, key=_slice_sort_key)

    if fcproj_audit and fcproj_audit.get("a1_timeline"):
        from_a1: list[Path] = []
        for item in fcproj_audit["a1_timeline"]:
            rp = item.get("resolved_path")
            if rp and Path(rp).is_file():
                from_a1.append(Path(rp))
        if from_a1:
            return from_a1

    return []


def build_clamped_voice_slices_and_buffer(
    voice_files: list[Path],
    probed: dict[str, dict[str, Any]],
    base_dir: Path,
    fps_grid: int,
    old_v1: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """
    Compute strict EOF-clamped `fps_grid` (30fps/60fps) slice boundaries (`nf / fps_grid <= actual_dur`)
    and decode all slices in parallel into a single 16kHz float32 RAM buffer.
    """
    slices: list[dict[str, Any]] = []
    t_cur = 0.0

    for idx, vf in enumerate(voice_files):
        rel_w = str(vf.relative_to(base_dir)) if vf.is_relative_to(base_dir) else vf.name
        act_dur = float(probed.get(rel_w, {}).get("dur") or 0.0)
        if act_dur <= 0.0:
            _, pinfo = probe_single_media(vf, base_dir)
            act_dur = float(pinfo.get("dur") or 0.0)

        nf = int(math.floor((act_dur + 1e-5) * fps_grid))
        while nf > 1 and (nf / fps_grid) > act_dur:
            nf -= 1
        nf = max(1, nf)
        dur = round(nf / fps_grid, 6)
        ov = old_v1[idx] if (old_v1 and idx < len(old_v1)) else {"name": "", "src_in_s": 0.0}
        slices.append({
            "id": f"s{idx:02d}",
            "idx": idx,
            "wav": rel_w,
            "abs_path": str(vf.resolve()),
            "actual_dur": round(act_dur, 6),
            "frames": nf,
            "fps": fps_grid,
            "t0": round(t_cur, 6),
            "dur": dur,
            "t1": round(t_cur + dur, 6),
            "old_v1_name": ov.get("name") or "",
            "old_src_in": ov.get("src_in_s") or 0.0,
        })
        t_cur += nf / fps_grid

    sr = 16000
    total_samples = int(math.ceil(t_cur * sr)) + sr // 4
    buf = np.zeros(max(1, total_samples), dtype=np.float32)

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(slices)))) as ex:
        decoded_list = list(ex.map(lambda s: decode_16k_f32_pcm(Path(s["abs_path"]), s["dur"]), slices))

    for s, arr in zip(slices, decoded_list):
        i0 = int(round(float(s["t0"]) * sr))
        n_copy = min(len(arr), len(buf) - i0)
        if n_copy > 0:
            buf[i0 : i0 + n_copy] = arr[:n_copy]

    trim_end = min(len(buf), int(math.ceil(t_cur * sr)) + int(0.15 * sr))
    return slices, buf[:trim_end]


# ---------------------------------------------------------------------------
# v7.0 10x8 Industry & Format Routing Context Resolver
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=8)
def _load_preset_json_cached(path_str: str) -> dict[str, Any]:
    p = Path(path_str)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_v7_routing_context(
    industry_skin: str | None,
    format_mode: str | None,
    execution_tier_used: str,
) -> dict[str, Any]:
    """
    Resolve `--industry-skin` (8 v7.0 skins + 5 v1.0 legacy aliases) and `--format-mode`
    (`F1..F10` or canonical format slug) against `industry_profiles.json`,
    `format_modes_catalog.json`, and `execution_tiers.json`.
    """
    ind_doc = _load_preset_json_cached(str(INDUSTRY_PROFILES_JSON))
    fmt_doc = _load_preset_json_cached(str(FORMAT_MODES_JSON))
    tier_doc = _load_preset_json_cached(str(EXECUTION_TIERS_JSON))

    profiles = ind_doc.get("profiles") or {}
    legacy_aliases = ind_doc.get("legacy_aliases") or {}
    format_modes = fmt_doc.get("format_modes") or {}
    code_lookup = fmt_doc.get("format_code_lookup") or {}
    matrix_10x8 = (tier_doc.get("routing_matrix_10x8") or {}).get("matrix") or {}
    hw_gov = tier_doc.get("hardware_budget_governor") or {}

    skin_req = str(industry_skin).strip() if industry_skin else None
    skin_resolved: str | None = None
    skin_profile: dict[str, Any] = {}
    if skin_req:
        sk_l = skin_req.lower()
        if sk_l in legacy_aliases and legacy_aliases[sk_l] in profiles:
            skin_resolved = str(legacy_aliases[sk_l])
            skin_profile = dict(profiles[skin_resolved])
        elif sk_l in profiles:
            skin_resolved = str(profiles[sk_l].get("maps_to_v7_skin") or sk_l)
            skin_profile = dict(profiles.get(sk_l) or {})
        else:
            skin_resolved = sk_l

    fmt_req = str(format_mode).strip() if format_mode else None
    fmt_resolved: str | None = None
    fmt_entry: dict[str, Any] = {}
    if fmt_req:
        fm_u = fmt_req.upper()
        fm_l = fmt_req.lower()
        if fm_u in code_lookup and code_lookup[fm_u] in format_modes:
            fmt_resolved = str(code_lookup[fm_u])
            fmt_entry = dict(format_modes[fmt_resolved])
        elif fm_l in format_modes:
            fmt_resolved = fm_l
            fmt_entry = dict(format_modes[fm_l])
        else:
            fmt_resolved = fm_l

    cell = (
        (matrix_10x8.get(fmt_resolved) or {}).get(skin_resolved)
        if (fmt_resolved and skin_resolved)
        else None
    ) or {}

    default_lane = str(cell.get("lane") or fmt_entry.get("default_lane") or "lane_a_native")
    rec_tier_matrix = cell.get("tier")
    tier_cfg = (tier_doc.get("tiers") or {}).get(execution_tier_used) or {}

    return {
        "industry_skin_requested": skin_req,
        "industry_skin_resolved": skin_resolved,
        "format_mode_requested": fmt_req,
        "format_mode_resolved": fmt_resolved,
        "format_code": fmt_entry.get("code"),
        "default_lane": default_lane,
        "recommended_tier_from_matrix": rec_tier_matrix,
        "target_lufs_from_matrix": cell.get("lufs"),
        "claim_gate_required": bool(
            cell.get("claim_gate")
            or (skin_profile.get("hard_veto_guards") or {}).get("claim_gate_r200")
        ),
        "recommended_micro_bridges": list(fmt_entry.get("recommended_micro_bridges") or []),
        "hard_veto_guards": dict(skin_profile.get("hard_veto_guards") or {}),
        "allowed_sfx": list(skin_profile.get("allowed_sfx") or []),
        "banned_sfx": list(skin_profile.get("banned_sfx") or []),
        "ram_governance": {
            "schedule_policy": str(hw_gov.get("schedule_policy") or "sequential_rvm_then_chrome_max2"),
            "max_ram_gb": float(hw_gov.get("max_ram_gb") or 4.5),
            "max_chrome_workers": int(tier_cfg.get("max_chrome_workers", 2 if execution_tier_used != "fast" else 0)),
        },
    }


# ---------------------------------------------------------------------------
# Top-Level Mode Runners & Public Python API
# ---------------------------------------------------------------------------


def probe_and_align(
    input_path: str | Path,
    work_dir: str | Path,
    script_path: str | Path | None = None,
    backup: bool = False,
    whisper_model: str = "small",
    language: str = "vi",
    skip_whisper: bool = False,
    tier: str = "auto",
    refine_onsets: bool | None = None,
    industry_skin: str | None = None,
    format_mode: str | None = None,
) -> dict[str, Any]:
    """
    Universal Stateless Ingest, Probe, Audit & Alignment entrypoint (`v7.0.0`).
    Auto-detects `raw_video` | `project_bundle` | `fcproj_file`, resolves `--tier {auto,fast,studio,full}`,
    computes Cranial Exclusion Bands, Dual-Rail Safe Zones, and Zero-Face Macro Safe-Zones
    (`enamel_gum_bbox` & `macro_subject_bbox`), writes unified artifacts into `work_dir`,
    and returns the `workspace_context` dictionary.
    """
    t_start = time.perf_counter()
    tier_req = str(tier or "auto").strip().lower()
    if tier_req not in {"auto", "fast", "studio", "full"}:
        raise ValueError(f"Unsupported tier '{tier}'; expected one of: auto, fast, studio, full")

    in_path = Path(input_path).resolve()
    out_dir = Path(work_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scr_path = Path(script_path).resolve() if script_path else None

    mode = detect_input_mode(in_path)
    artifacts: dict[str, str] = {}
    audit_warnings: list[str] = []
    backup_file: Path | None = None

    # =========================================================================
    # MODE 1: `raw_video` (.mp4/.mov/.mkv/.wav/.m4a/...)
    # =========================================================================
    if mode == "raw_video":
        execution_tier_used = "full" if tier_req == "auto" else tier_req
        use_refine_onsets = (execution_tier_used in {"studio", "full"}) if refine_onsets is None else bool(refine_onsets)
        face_sample_count = 8 if execution_tier_used == "fast" else (16 if execution_tier_used == "studio" else 24)
        routing_v7 = resolve_v7_routing_context(industry_skin, format_mode, execution_tier_used)

        script_info = load_ground_truth_script(scr_path, None)
        key, pinfo = probe_single_media(in_path, None)
        duration_sec = float(pinfo.get("dur") or 0.0)
        has_video = bool(pinfo.get("has_video"))
        has_audio = bool(pinfo.get("has_audio")) and duration_sec > 0.0
        fps_num = float(pinfo.get("fps_num") or 30.0) if has_video else 30.0
        fps_grid = snap_fps_grid(fps_num)

        audio_telemetry: dict[str, Any] = {
            "integrated_lufs": None,
            "lra_lu": None,
            "true_peak_dbtp": None,
            "silences": [],
            "natural_cut_candidates": [],
            "keep_segments": [],
        }
        pcm_16k = np.zeros(0, dtype=np.float32)
        words_tl: list[list[Any]] = []
        speech_segments: list[dict[str, Any]] = []
        rms_pauses: list[tuple[float, float]] = []
        tightened_onset_count = 0

        def _visual_pipeline_raw() -> tuple[
            Path,
            dict[str, Any],
            dict[str, Any] | None,
            list[dict[str, Any]],
            list[dict[str, Any]],
        ]:
            sh_p, s_frames = render_raw_video_contact_sheet(
                in_path,
                duration_sec,
                has_video,
                out_dir,
                audio_pcm_16k=None,
                num_samples=face_sample_count,
            )
            sf = estimate_subject_framing(
                s_frames,
                pinfo.get("w"),
                pinfo.get("h"),
                num_samples=face_sample_count,
            )
            is_br = _is_broll_candidate(key, in_path, pinfo, has_explicit_aroll=False)
            bq: dict[str, Any] | None = None
            geo_anchors: list[dict[str, Any]] = []
            act_peaks: list[dict[str, Any]] = []
            if is_br:
                if execution_tier_used in {"studio", "full"}:
                    bq = audit_broll_media(in_path, pinfo)
                geo_anchors = detect_geometric_anchors(in_path, pinfo)
            else:
                act_peaks = mine_gesture_action_peaks(
                    in_path,
                    duration_sec=duration_sec,
                    subject_framing=sf,
                )
            return sh_p, sf, bq, geo_anchors, act_peaks

        if has_audio:
            with ThreadPoolExecutor(max_workers=2) as ex:
                fut_lufs = ex.submit(measure_audio_lufs_and_silences, in_path, duration_sec)
                fut_pcm = ex.submit(decode_16k_f32_pcm, in_path, None)
                audio_telemetry = fut_lufs.result()
                pcm_16k = fut_pcm.result()

        # Run CTranslate2 Whisper BEFORE OpenCV (`cv2.resize`/`cv2.integral`) so OpenCV does not alter OpenMP thread affinity
        if has_audio and len(pcm_16k) > 0:
            rms_pauses = find_pauses(pcm_16k, sr=16000)
            if len(pcm_16k) > 400 and not skip_whisper:
                eff_model = _resolve_whisper_model_name(whisper_model, execution_tier_used, bool(script_info["full_text"]))
                r_words, speech_segments = run_single_pass_whisper(
                    pcm_16k,
                    whisper_model_name=eff_model,
                    language=language,
                    has_ground_truth_script=bool(script_info["full_text"]),
                    script_hint=script_info["full_text"],
                    use_vad=(len(pcm_16k) > 20 * 16000),
                )
                if use_refine_onsets and rms_pauses and r_words:
                    r_words, tightened_onset_count = tighten_raw_words_onsets(r_words, speech_segments, rms_pauses)
                words_tl = align_words_to_script(
                    r_words,
                    script_info["full_text"],
                    duration_sec,
                    slices=None,
                    pauses=rms_pauses if use_refine_onsets else None,
                )

        if has_video:
            sheet_path, subject_framing, broll_qual, raw_geo_anchors, gesture_peaks = _visual_pipeline_raw()
        else:
            sheet_path, _ = render_raw_video_contact_sheet(
                in_path,
                duration_sec,
                False,
                out_dir,
                audio_pcm_16k=pcm_16k,
                num_samples=face_sample_count,
            )
            subject_framing = {
                "detected": False,
                "reason": "no_video_frames",
                "cranial_exclusion_band": None,
                "dual_rail_zones": None,
                "enamel_gum_bbox": None,
                "macro_subject_bbox": None,
            }
            broll_qual = None
            raw_geo_anchors = []
            gesture_peaks = []

        artifacts["assets_contact_sheet"] = str(sheet_path)
        pinfo["integrated_lufs"] = audio_telemetry["integrated_lufs"]
        pinfo["true_peak_dbtp"] = audio_telemetry["true_peak_dbtp"]
        pinfo["lra_lu"] = audio_telemetry["lra_lu"]
        pinfo["subject_framing"] = subject_framing
        pinfo["cranial_exclusion_band"] = subject_framing.get("cranial_exclusion_band")
        pinfo["dual_rail_zones"] = subject_framing.get("dual_rail_zones")
        pinfo["enamel_gum_bbox"] = subject_framing.get("enamel_gum_bbox")
        pinfo["macro_subject_bbox"] = subject_framing.get("macro_subject_bbox")
        if subject_framing.get("zero_face_macro_safe_zone"):
            pinfo["zero_face_macro_safe_zone"] = subject_framing["zero_face_macro_safe_zone"]
        if raw_geo_anchors or _is_broll_candidate(key, in_path, pinfo, has_explicit_aroll=False):
            pinfo["geometric_anchors"] = raw_geo_anchors
        if gesture_peaks:
            pinfo["gesture_action_peaks_s"] = gesture_peaks
        if broll_qual is not None:
            pinfo["broll_quality"] = broll_qual
            b_top, b_bot, b_left, b_right = broll_qual["uniform_borders_px"]
            if any(v > 0 for v in broll_qual["uniform_borders_px"]):
                audit_warnings.append(
                    f"B-roll {key}: uniform edge border detected "
                    f"(top={b_top}px, bottom={b_bot}px, left={b_left}px, right={b_right}px)"
                )
            if broll_qual["is_flat"]:
                audit_warnings.append(
                    f"B-roll {key}: low-contrast/flat frame detected (grayscale_std={broll_qual['grayscale_std']:.2f} < 30.0)"
                )

        if pinfo.get("is_hdr"):
            audit_warnings.append(
                f"HDR color transfer detected ({pinfo.get('color_transfer')}/{pinfo.get('color_primaries')}); tonemap to Rec.709 if compositing SDR"
            )

        probed_map = {key: pinfo}
        media_probe_path = out_dir / "media_probe.json"
        media_probe_path.write_text(json.dumps(probed_map, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts["media_probe"] = str(media_probe_path)

        raw_pause_inputs: list[Any] = list(audio_telemetry["silences"]) + list(rms_pauses)
        cadence_plan = build_cadence_and_jcut_plan(
            words_tl,
            pauses=raw_pause_inputs,
            slices=None,
            fps=fps_grid,
            script_text=script_info["full_text"],
        )

        if words_tl:
            words_tl_doc = build_words_tl_document(
                words_tl,
                pauses=raw_pause_inputs,
                rms_pauses_20ms=rms_pauses,
                face_metrics=subject_framing,
                tier=execution_tier_used,
                fps=fps_grid,
                fps_num=fps_num,
                duration_sec=duration_sec,
                slices=[],
                script_text=script_info["full_text"],
                cadence_plan=cadence_plan,
                gesture_action_peaks_s=gesture_peaks,
            )
            words_tl_path = out_dir / "words_tl.json"
            words_tl_path.write_text(json.dumps(words_tl_doc, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts["words_tl"] = str(words_tl_path)

            words_tl_arr_path = out_dir / "words_tl_array.json"
            words_tl_arr_path.write_text(json.dumps(words_tl, ensure_ascii=False, indent=1), encoding="utf-8")
            artifacts["words_tl_array"] = str(words_tl_arr_path)

        speech_seg_payload = {
            "source_file": str(in_path),
            "duration_sec": duration_sec,
            "fps": fps_num,
            "integrated_lufs": audio_telemetry["integrated_lufs"],
            "true_peak_dbtp": audio_telemetry["true_peak_dbtp"],
            "lra_lu": audio_telemetry["lra_lu"],
            "silences": audio_telemetry["silences"],
            "rms_20ms_pause_count": len(rms_pauses),
            "tightened_onset_count": tightened_onset_count,
            "natural_cut_candidates": audio_telemetry["natural_cut_candidates"],
            "keep_segments": audio_telemetry["keep_segments"],
            "gesture_action_peaks_s": gesture_peaks,
            "cadence_and_jcut_plan": cadence_plan,
            "segments": speech_segments,
        }
        speech_seg_path = out_dir / "speech_segments.json"
        speech_seg_path.write_text(json.dumps(speech_seg_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts["speech_segments"] = str(speech_seg_path)

        recommended_compile_tier = "full"
        elapsed = round(time.perf_counter() - t_start, 3)
        ctx = {
            "version": VERSION,
            "mode": mode,
            "tier_requested": tier_req,
            "execution_tier_used": execution_tier_used,
            "recommended_compile_tier": recommended_compile_tier,
            "industry_skin": routing_v7["industry_skin_resolved"],
            "format_mode": routing_v7["format_mode_resolved"],
            "routing_v7": routing_v7,
            "input_path": str(in_path),
            "work_dir": str(out_dir),
            "elapsed_sec": elapsed,
            "fps": fps_num,
            "fps_grid": fps_grid,
            "resolution": {"width": pinfo.get("w"), "height": pinfo.get("h")},
            "duration_sec": duration_sec,
            "backup_path": None,
            "script_source": script_info["source_path"],
            "media_inventory": {
                "total_files": 1,
                "by_category": {pinfo["category"]: 1},
            },
            "speech_summary": {
                "has_speech": len(words_tl) > 0,
                "word_count": len(words_tl),
                "segment_count": len(speech_segments),
                "slice_count": 0,
                "aligned_to_script": bool(script_info["full_text"] and words_tl),
                "refine_onsets_used": use_refine_onsets,
                "rms_20ms_pause_count": len(rms_pauses),
                "tightened_onset_count": tightened_onset_count,
                "integrated_lufs": audio_telemetry["integrated_lufs"],
                "true_peak_dbtp": audio_telemetry["true_peak_dbtp"],
                "silence_count": len(audio_telemetry["silences"]),
                "natural_cut_candidate_count": len(audio_telemetry["natural_cut_candidates"]),
                "gesture_action_peak_count": len(gesture_peaks),
                "vocal_jcut_candidate_count": len(cadence_plan.get("vocal_jcut_candidates") or []),
                "cadence_summary": cadence_plan["summary"],
            },
            "gesture_action_peaks_s": gesture_peaks,
            "cadence_and_jcut_plan": cadence_plan,
            "subject_framing": subject_framing,
            "alpha_prop_checks": [],
            "audit_warnings": audit_warnings,
            "artifacts": artifacts,
        }
        ctx_path = out_dir / "workspace_context.json"
        artifacts["workspace_context"] = str(ctx_path)
        ctx_path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
        return ctx

    # =========================================================================
    # MODE 2 (`project_bundle`) & MODE 3 (`fcproj_file`)
    # =========================================================================
    if mode == "project_bundle":
        bundle_dir = in_path
        fc_candidates = sorted(bundle_dir.glob("*.fcproj"))
        fcproj_path: Path | None = fc_candidates[0] if fc_candidates else None
    else:
        fcproj_path = in_path
        bundle_dir = in_path.parent

    if backup and fcproj_path is not None and fcproj_path.is_file():
        backup_file = backup_fcproj(fcproj_path)

    script_info = load_ground_truth_script(scr_path, bundle_dir)

    # Discover media files
    discovered_files: list[Path] = []
    if mode == "project_bundle":
        for root, dirs, files in os.walk(bundle_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith("."))
            root_p = Path(root)
            for fn in sorted(files):
                fp = root_p / fn
                if fp.suffix.lower() in (RAW_MEDIA_EXTS | IMAGE_EXTS):
                    discovered_files.append(fp)
    else:
        # Mode 3 (`fcproj_file`): inspect `.fcproj` first to collect referenced media + sibling assets
        prelim_audit = audit_fcproj(fcproj_path, bundle_dir, probed_media=None)  # type: ignore[arg-type]
        ref_paths = [Path(p) for p in prelim_audit.get("referenced_files", []) if Path(p).is_file()]
        sib_assets = bundle_dir / "assets"
        if sib_assets.is_dir():
            for root, dirs, files in os.walk(sib_assets):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith("."))
                for fn in sorted(files):
                    fp = Path(root) / fn
                    if fp.suffix.lower() in (RAW_MEDIA_EXTS | IMAGE_EXTS):
                        ref_paths.append(fp)
        seen_abs: set[str] = set()
        for p in ref_paths:
            ap = str(p.resolve())
            if ap not in seen_abs:
                seen_abs.add(ap)
                discovered_files.append(p)

    # 12-thread ffprobe across all discovered media files
    probed = probe_media_files(discovered_files, base_dir=bundle_dir, max_workers=12)

    # Audit `.fcproj` if present (now with exact ffprobe durations for EOF overrun detection!)
    fcproj_audit: dict[str, Any] | None = None
    if fcproj_path is not None and fcproj_path.is_file():
        fcproj_audit = audit_fcproj(fcproj_path, bundle_dir, probed_media=probed)
        audit_path = out_dir / "existing_fcproj_audit.json"
        audit_path.write_text(json.dumps(fcproj_audit, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts["existing_fcproj_audit"] = str(audit_path)
        audit_warnings.extend(fcproj_audit.get("warnings") or [])

    voice_slices_files = discover_voice_slices(bundle_dir, discovered_files, fcproj_audit)
    fcproj_has_defects = bool(
        fcproj_audit
        and (
            fcproj_audit.get("warnings")
            or fcproj_audit.get("single_sided_transition_count", 0) > 0
            or fcproj_audit.get("error")
        )
    )
    is_clean_presliced_bundle = bool(voice_slices_files) and not fcproj_has_defects

    if tier_req == "auto":
        execution_tier_used = "fast" if is_clean_presliced_bundle else "full"
    else:
        execution_tier_used = tier_req

    use_refine_onsets = (execution_tier_used in {"studio", "full"}) if refine_onsets is None else bool(refine_onsets)
    face_sample_count = 8 if execution_tier_used == "fast" else (16 if execution_tier_used == "studio" else 24)
    routing_v7 = resolve_v7_routing_context(industry_skin, format_mode, execution_tier_used)

    # Determine canonical FPS & resolution objectively
    fps_num = 30.0
    res_w, res_h = 1080, 1920
    if fcproj_audit and fcproj_audit.get("sequence_settings"):
        ss = fcproj_audit["sequence_settings"]
        fps_num = float(ss.get("fps") or 30.0)
        res_w = int(ss.get("width") or 1080)
        res_h = int(ss.get("height") or 1920)
    elif script_info.get("fps"):
        fps_num = float(script_info["fps"])
    else:
        for pinfo in probed.values():
            if pinfo.get("category") == "video" and pinfo.get("fps_num"):
                fps_num = float(pinfo["fps_num"])
                res_w = int(pinfo.get("w") or 1080)
                res_h = int(pinfo.get("h") or 1920)
                break
    fps_grid = snap_fps_grid(fps_num)

    video_clips_for_sheet = [
        p for p in discovered_files
        if p.suffix.lower() in VIDEO_EXTS
        and "ovl_" not in p.name.lower()
        and "overlay" not in p.name.lower()
        and "overlays" not in [pt.lower() for pt in p.parts]
    ]
    prop_pngs = [
        p for p in discovered_files
        if p.suffix.lower() == ".png"
        and (
            p.stem.lower().startswith("3d_")
            or "alpha" in p.stem.lower()
            or p.stem.lower().startswith("ui_card_")
        )
    ]
    path_by_rel: dict[str, Path] = {
        (str(p.relative_to(bundle_dir)) if p.is_relative_to(bundle_dir) else p.name): p
        for p in discovered_files
    }
    has_explicit_aroll = any(
        ("a-roll" in rel_k.lower() or "aroll" in rel_k.lower())
        for rel_k, pinfo in probed.items()
        if pinfo.get("category") == "video"
    )

    def _visual_and_broll_bundle_pipeline() -> tuple[
        Path,
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, list[dict[str, Any]]],
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, Any]],
    ]:
        sh_p, f_by_vid, a_checks = render_bundle_contact_sheet(
            video_clips_for_sheet,
            prop_pngs,
            probed,
            bundle_dir,
            out_dir,
            aroll_samples=face_sample_count,
        )
        # Estimate Haar subject_framing + Cranial/Macro safe-zones cleanly without GIL contention
        aroll_targets: list[tuple[str, list[Path]]] = [
            (rel_v, fpaths)
            for rel_v, fpaths in f_by_vid.items()
            if "a-roll" in rel_v.lower() or "aroll" in rel_v.lower() or len(f_by_vid) <= 4
        ]
        sf_map: dict[str, dict[str, Any]] = {}
        aroll_peaks_by_rel: dict[str, list[dict[str, Any]]] = {}
        for rv, fps_list in aroll_targets:
            vm = probed.get(rv, {})
            vp_abs = path_by_rel.get(rv)
            sf_cur = estimate_subject_framing(
                fps_list,
                vm.get("w"),
                vm.get("h"),
                video_path=vp_abs,
                duration_sec=float(vm.get("dur") or 0.0),
                num_samples=face_sample_count,
            )
            sf_map[rv] = sf_cur
            if vp_abs is not None and not _is_broll_candidate(rv, vp_abs, vm, has_explicit_aroll):
                aroll_peaks_by_rel[rv] = mine_gesture_action_peaks(
                    vp_abs,
                    duration_sec=float(vm.get("dur") or 0.0),
                    subject_framing=sf_cur,
                )

        bq_map: dict[str, dict[str, Any]] = {}
        geo_map: dict[str, list[dict[str, Any]]] = {}
        broll_sz_map: dict[str, dict[str, Any]] = {}
        broll_targets = [
            (rel_k, path_by_rel[rel_k], pinfo)
            for rel_k, pinfo in probed.items()
            if rel_k in path_by_rel and _is_broll_candidate(rel_k, path_by_rel[rel_k], pinfo, has_explicit_aroll)
        ]
        if broll_targets:
            def _eval_broll(
                item: tuple[str, Path, dict[str, Any]],
            ) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
                rk, bp, pi = item
                bq_r = audit_broll_media(bp, pi) if execution_tier_used in {"studio", "full"} else None
                geo_r = detect_geometric_anchors(bp, pi)
                sz_r = probe_broll_safe_zones(bp, pi)
                return rk, bq_r, geo_r, sz_r

            with ThreadPoolExecutor(max_workers=min(8, len(broll_targets))) as ex_br:
                for rk, bq_res, geo_res, sz_res in ex_br.map(_eval_broll, broll_targets):
                    if bq_res is not None:
                        bq_map[rk] = bq_res
                    geo_map[rk] = geo_res
                    broll_sz_map[rk] = sz_res

        return sh_p, a_checks, sf_map, bq_map, geo_map, aroll_peaks_by_rel, broll_sz_map

    def _speech_bundle_pipeline() -> tuple[
        list[list[Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        float,
        list[tuple[float, float]],
        int,
    ]:
        dur_s = float((fcproj_audit or {}).get("sequence_settings", {}).get("duration_sec") or 0.0)
        if skip_whisper:
            return [], [], [], dur_s, [], 0

        if voice_slices_files:
            old_v1 = (fcproj_audit or {}).get("v1_timeline") or []
            s_meta, pcm_b = build_clamped_voice_slices_and_buffer(
                voice_slices_files,
                probed,
                bundle_dir,
                fps_grid=fps_grid,
                old_v1=old_v1,
            )
            dur_s = float(s_meta[-1]["t1"]) if s_meta else dur_s
            pauses_20ms = find_pauses(pcm_b, sr=16000)
            eff_model = _resolve_whisper_model_name(whisper_model, execution_tier_used, bool(script_info["full_text"]))
            r_words, _ = run_single_pass_whisper(
                pcm_b,
                whisper_model_name=eff_model,
                language=language,
                has_ground_truth_script=bool(script_info["full_text"]),
                script_hint=script_info["full_text"],
                use_vad=False,
            )
            snapped_n = 0
            if use_refine_onsets and pauses_20ms and r_words:
                r_words, snapped_n = tighten_raw_words_onsets(r_words, None, pauses_20ms)
            w_tl = align_words_to_script(
                r_words,
                script_info["full_text"],
                total_duration=dur_s,
                slices=s_meta,
                pauses=pauses_20ms if use_refine_onsets else None,
            )
            return w_tl, s_meta, [], dur_s, pauses_20ms, snapped_n

        if mode == "project_bundle":
            speech_videos = [
                p for p in video_clips_for_sheet
                if probed.get(str(p.relative_to(bundle_dir)) if p.is_relative_to(bundle_dir) else p.name, {}).get("has_audio")
            ]
            if speech_videos:
                s_meta, pcm_b = build_clamped_voice_slices_and_buffer(
                    speech_videos,
                    probed,
                    bundle_dir,
                    fps_grid=fps_grid,
                    old_v1=None,
                )
                dur_s = float(s_meta[-1]["t1"]) if s_meta else dur_s
                pauses_20ms = find_pauses(pcm_b, sr=16000)
                eff_model = _resolve_whisper_model_name(whisper_model, execution_tier_used, bool(script_info["full_text"]))
                r_words, s_segs = run_single_pass_whisper(
                    pcm_b,
                    whisper_model_name=eff_model,
                    language=language,
                    has_ground_truth_script=bool(script_info["full_text"]),
                    script_hint=script_info["full_text"],
                    use_vad=(len(pcm_b) > 25 * 16000),
                )
                if r_words:
                    snapped_n = 0
                    if use_refine_onsets and pauses_20ms:
                        r_words, snapped_n = tighten_raw_words_onsets(r_words, s_segs, pauses_20ms)
                    w_tl = align_words_to_script(
                        r_words,
                        script_info["full_text"],
                        total_duration=dur_s,
                        slices=s_meta if len(s_meta) > 1 else None,
                        pauses=pauses_20ms if use_refine_onsets else None,
                    )
                    return w_tl, s_meta, s_segs, dur_s, pauses_20ms, snapped_n

        return [], [], [], dur_s, [], 0

    # Run CTranslate2 Whisper BEFORE OpenCV (`cv2.resize`/`cv2.integral`) so OpenCV does not alter OpenMP thread affinity
    words_tl, slices_meta, bundle_speech_segs, duration_sec, bundle_pauses_20ms, tightened_cnt = _speech_bundle_pipeline()
    rms_pause_cnt = len(bundle_pauses_20ms)
    (
        sheet_path,
        alpha_checks,
        sf_by_rel,
        broll_qual_by_rel,
        geo_by_rel,
        aroll_peaks_by_rel,
        broll_sz_by_rel,
    ) = _visual_and_broll_bundle_pipeline()

    artifacts["assets_contact_sheet"] = str(sheet_path)

    for chk in alpha_checks:
        if chk["file"] in probed:
            probed[chk["file"]]["alpha_check"] = chk
        if chk["suspicious_unkeyed_blocks"]:
            for w_msg in chk["warnings"]:
                audit_warnings.append(f"Alpha prop {chk['file']}: {w_msg}")

    for rel_b, sz_info in sorted(broll_sz_by_rel.items()):
        if rel_b in probed:
            probed[rel_b]["cranial_exclusion_band"] = sz_info.get("cranial_exclusion_band")
            probed[rel_b]["dual_rail_zones"] = sz_info.get("dual_rail_zones")
            probed[rel_b]["enamel_gum_bbox"] = sz_info.get("enamel_gum_bbox")
            probed[rel_b]["macro_subject_bbox"] = sz_info.get("macro_subject_bbox")
            if sz_info.get("zero_face_macro_safe_zone"):
                probed[rel_b]["zero_face_macro_safe_zone"] = sz_info["zero_face_macro_safe_zone"]

    subject_framing_summary: dict[str, Any] = {}
    for rel_v, sf in sf_by_rel.items():
        if rel_v in probed:
            probed[rel_v]["subject_framing"] = sf
            probed[rel_v]["cranial_exclusion_band"] = sf.get("cranial_exclusion_band")
            probed[rel_v]["dual_rail_zones"] = sf.get("dual_rail_zones")
            probed[rel_v]["enamel_gum_bbox"] = sf.get("enamel_gum_bbox")
            probed[rel_v]["macro_subject_bbox"] = sf.get("macro_subject_bbox")
            if sf.get("zero_face_macro_safe_zone"):
                probed[rel_v]["zero_face_macro_safe_zone"] = sf["zero_face_macro_safe_zone"]
        if sf.get("detected") and ("a-roll" in rel_v.lower() or "aroll" in rel_v.lower() or not subject_framing_summary):
            subject_framing_summary[rel_v] = sf

    for rel_v, pks in aroll_peaks_by_rel.items():
        if rel_v in probed and pks:
            probed[rel_v]["gesture_action_peaks_s"] = pks

    for rel_b, geo_list in sorted(geo_by_rel.items()):
        if rel_b in probed:
            probed[rel_b]["geometric_anchors"] = geo_list

    for rel_b, bq in sorted(broll_qual_by_rel.items()):
        if rel_b in probed:
            probed[rel_b]["broll_quality"] = bq
        b_top, b_bot, b_left, b_right = bq["uniform_borders_px"]
        if any(v > 0 for v in bq["uniform_borders_px"]):
            audit_warnings.append(
                f"B-roll {rel_b}: uniform edge border detected "
                f"(top={b_top}px, bottom={b_bot}px, left={b_left}px, right={b_right}px)"
            )
        if bq["is_flat"]:
            audit_warnings.append(
                f"B-roll {rel_b}: low-contrast/flat frame detected (grayscale_std={bq['grayscale_std']:.2f} < 30.0)"
            )

    # Map A-Roll clip action peaks onto unified timeline timestamps `gesture_action_peaks_s`
    timeline_gesture_peaks: list[dict[str, Any]] = []
    v1_tl = (fcproj_audit or {}).get("v1_timeline") or []
    if v1_tl and aroll_peaks_by_rel:
        peaks_by_abs: dict[str, list[dict[str, Any]]] = {}
        for rv, pks in aroll_peaks_by_rel.items():
            vp = path_by_rel.get(rv)
            if vp is not None:
                peaks_by_abs[str(vp.resolve())] = pks
        for cl in v1_tl:
            raw_f = str(cl.get("file") or "")
            if not raw_f:
                continue
            rp = str(resolve_fcproj_media_path(raw_f, bundle_dir).resolve())
            src_pks = peaks_by_abs.get(rp)
            if not src_pks:
                continue
            src_in = float(cl.get("src_in_s") or 0.0)
            cl_dur = float(cl.get("dur_s") or 0.0)
            tl_s0 = float(cl.get("tl_s") or 0.0)
            for pk in src_pks:
                ts_src = float(pk["t_sec"])
                if (src_in + 0.05) <= ts_src <= (src_in + cl_dur - 0.05):
                    pk_tl = dict(pk)
                    pk_tl["t_sec"] = round(tl_s0 + (ts_src - src_in), 4)
                    timeline_gesture_peaks.append(pk_tl)
    elif slices_meta and aroll_peaks_by_rel:
        for sl in slices_meta:
            rel_w = str(sl.get("wav") or "")
            if rel_w in aroll_peaks_by_rel:
                sl_t0 = float(sl.get("t0") or 0.0)
                sl_dur = float(sl.get("dur") or 0.0)
                for pk in aroll_peaks_by_rel[rel_w]:
                    if float(pk["t_sec"]) <= sl_dur:
                        pk_tl = dict(pk)
                        pk_tl["t_sec"] = round(sl_t0 + float(pk["t_sec"]), 4)
                        timeline_gesture_peaks.append(pk_tl)
    if not timeline_gesture_peaks and aroll_peaks_by_rel:
        # Fallback to primary A-roll clip peaks
        primary_rel = next(
            (rv for rv in aroll_peaks_by_rel if "a-roll" in rv.lower() or "aroll" in rv.lower()),
            next(iter(aroll_peaks_by_rel.keys())),
        )
        timeline_gesture_peaks = list(aroll_peaks_by_rel[primary_rel])
    timeline_gesture_peaks.sort(key=lambda p: float(p["t_sec"]))

    # Write `media_probe.json` (enriched with `cranial_exclusion_band`, `dual_rail_zones`, `enamel_gum_bbox`, `macro_subject_bbox`)
    media_probe_path = out_dir / "media_probe.json"
    media_probe_path.write_text(json.dumps(probed, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["media_probe"] = str(media_probe_path)

    cadence_plan = build_cadence_and_jcut_plan(
        words_tl,
        pauses=bundle_pauses_20ms,
        slices=slices_meta,
        fps=fps_grid,
        script_text=script_info["full_text"],
    )

    if words_tl:
        if slices_meta:
            old_v1 = ((fcproj_audit or {}).get("v1_timeline") or []) if voice_slices_files else []
            tl_words_payload = {
                "fps": fps_grid,
                "duration_sec": duration_sec,
                "slices": slices_meta,
                "words_tl": words_tl,
                "old_v1": old_v1,
                "gesture_action_peaks_s": timeline_gesture_peaks,
                "cadence_and_jcut_plan": cadence_plan,
            }
            tl_words_path = out_dir / "timeline_words.json"
            tl_words_path.write_text(json.dumps(tl_words_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts["timeline_words"] = str(tl_words_path)

        words_tl_doc = build_words_tl_document(
            words_tl,
            pauses=bundle_pauses_20ms,
            rms_pauses_20ms=bundle_pauses_20ms,
            face_metrics=subject_framing_summary,
            tier=execution_tier_used,
            fps=fps_grid,
            fps_num=fps_num,
            duration_sec=duration_sec,
            slices=slices_meta,
            script_text=script_info["full_text"],
            cadence_plan=cadence_plan,
            gesture_action_peaks_s=timeline_gesture_peaks,
        )
        words_tl_path = out_dir / "words_tl.json"
        words_tl_path.write_text(json.dumps(words_tl_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts["words_tl"] = str(words_tl_path)

        words_tl_arr_path = out_dir / "words_tl_array.json"
        words_tl_arr_path.write_text(json.dumps(words_tl, ensure_ascii=False, indent=1), encoding="utf-8")
        artifacts["words_tl_array"] = str(words_tl_arr_path)

        if bundle_speech_segs:
            speech_seg_path = out_dir / "speech_segments.json"
            speech_seg_path.write_text(
                json.dumps(
                    {
                        "duration_sec": duration_sec,
                        "gesture_action_peaks_s": timeline_gesture_peaks,
                        "cadence_and_jcut_plan": cadence_plan,
                        "segments": bundle_speech_segs,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            artifacts["speech_segments"] = str(speech_seg_path)

    # Summarize media inventory by category
    by_cat: dict[str, int] = {}
    for pinfo in probed.values():
        cat = str(pinfo.get("category") or "other")
        by_cat[cat] = by_cat.get(cat, 0) + 1

    if duration_sec <= 0.0:
        duration_sec = round(sum(float(v.get("dur") or 0.0) for v in probed.values() if v.get("category") == "video"), 4)

    has_any_quality_defects = bool(fcproj_has_defects or audit_warnings)
    if execution_tier_used in {"studio", "full"} or has_any_quality_defects or not is_clean_presliced_bundle:
        recommended_compile_tier = "full"
    elif routing_v7.get("recommended_tier_from_matrix") in {"studio", "full"}:
        recommended_compile_tier = str(routing_v7["recommended_tier_from_matrix"])
    else:
        recommended_compile_tier = "fast"

    elapsed = round(time.perf_counter() - t_start, 3)
    ctx = {
        "version": VERSION,
        "mode": mode,
        "tier_requested": tier_req,
        "execution_tier_used": execution_tier_used,
        "recommended_compile_tier": recommended_compile_tier,
        "industry_skin": routing_v7["industry_skin_resolved"],
        "format_mode": routing_v7["format_mode_resolved"],
        "routing_v7": routing_v7,
        "input_path": str(in_path),
        "bundle_dir": str(bundle_dir),
        "work_dir": str(out_dir),
        "elapsed_sec": elapsed,
        "fps": fps_num,
        "fps_grid": fps_grid,
        "resolution": {"width": res_w, "height": res_h},
        "duration_sec": round(duration_sec, 6),
        "backup_path": str(backup_file) if backup_file else None,
        "script_source": script_info["source_path"],
        "media_inventory": {
            "total_files": len(probed),
            "by_category": dict(sorted(by_cat.items())),
        },
        "speech_summary": {
            "has_speech": len(words_tl) > 0,
            "word_count": len(words_tl),
            "slice_count": len(slices_meta),
            "aligned_to_script": bool(script_info["full_text"] and words_tl),
            "refine_onsets_used": use_refine_onsets,
            "rms_20ms_pause_count": rms_pause_cnt,
            "tightened_onset_count": tightened_cnt,
            "gesture_action_peak_count": len(timeline_gesture_peaks),
            "vocal_jcut_candidate_count": len(cadence_plan.get("vocal_jcut_candidates") or []),
            "cadence_summary": cadence_plan["summary"],
        },
        "gesture_action_peaks_s": timeline_gesture_peaks,
        "cadence_and_jcut_plan": cadence_plan,
        "subject_framing": subject_framing_summary,
        "alpha_prop_checks": alpha_checks,
        "audit_warnings": audit_warnings,
        "artifacts": artifacts,
    }
    ctx_path = out_dir / "workspace_context.json"
    artifacts["workspace_context"] = str(ctx_path)
    ctx_path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    return ctx


# ---------------------------------------------------------------------------
# v6.0 + v7.0 Built-in Self-Test Suite & CLI Interface
# ---------------------------------------------------------------------------


def run_v6_self_tests() -> int:
    """Verify all v6.0.0 + v7.0.0 upgrades (`mine_gesture_action_peaks`, `detect_geometric_anchors`, `solve_geometric_match_cut`, `plan_true_vocal_jcuts`, `cranial_exclusion_band`, `dual_rail_zones`, `enamel_gum_bbox`, `macro_subject_bbox`, `10x8` routing) + end-to-end `probe_and_align`."""
    # 1. Cut-on-Action Velocity Peak Miner (`mine_gesture_action_peaks`) at 15fps
    frames_15fps = np.full((60, 284, 160), 118, dtype=np.uint8)
    for fi in range(60):
        # Head turn around t = 1.20s (frames 16..21) and hand raise around t = 2.80s (frames 40..45)
        hx = int(round(80 + (18.0 * math.sin((fi - 16) / 5.0 * math.pi) if 16 <= fi <= 21 else (18.0 if fi > 21 else 0.0))))
        cv2.circle(frames_15fps[fi], (hx, 110), 22, 205, -1)
        if 40 <= fi <= 46:
            gy = int(round(240 - (fi - 40) * 14))
            cv2.rectangle(frames_15fps[fi], (35, gy), (62, gy + 32), 225, -1)
        elif fi > 46:
            cv2.rectangle(frames_15fps[fi], (35, 156), (62, 188), 225, -1)

    peaks = mine_gesture_action_peaks(frames_15fps, sample_fps=15.0)
    assert len(peaks) >= 2, f"Expected >=2 gesture action peaks, got {peaks}"
    assert any(0.95 <= p["t_sec"] <= 1.50 for p in peaks), f"Missed head-turn peak near 1.2s: {peaks}"
    assert any(2.55 <= p["t_sec"] <= 3.15 for p in peaks), f"Missed hand-raise peak near 2.8s: {peaks}"
    print(f"[OK] v6.0 mine_gesture_action_peaks: {len(peaks)} peaks -> {[(p['t_sec'], p['strength'], p['dominant_zone']) for p in peaks]}")

    # 2. Geometric Match-Cut Salience Detector & Concentric Solver (`detect_geometric_anchors` & `solve_geometric_match_cut`)
    shot_a = np.full((1920, 1080, 3), (32, 36, 42), dtype=np.uint8)
    cv2.circle(shot_a, (540, 880), 210, (232, 224, 210), -1)  # cx=50.0%, cy=45.83%, r=19.44%W
    shot_b = np.full((1920, 1080, 3), (26, 30, 36), dtype=np.uint8)
    cv2.circle(shot_b, (612, 1020), 156, (215, 232, 224), -1)  # cx=56.67%, cy=53.12%, r=14.44%W
    shot_rect = np.full((1920, 1080, 3), (28, 32, 38), dtype=np.uint8)
    cv2.rectangle(shot_rect, (300, 680), (780, 1180), (235, 235, 240), -1)

    anc_a = detect_geometric_anchors(shot_a)
    anc_b = detect_geometric_anchors(shot_b)
    anc_r = detect_geometric_anchors(shot_rect)
    assert anc_a and anc_a[0]["shape"] == "circle", f"Expected circle on shot_a, got {anc_a}"
    assert anc_b and anc_b[0]["shape"] == "circle", f"Expected circle on shot_b, got {anc_b}"
    assert anc_r and anc_r[0]["shape"] == "rect", f"Expected rect on shot_rect, got {anc_r}"

    mc = solve_geometric_match_cut(anc_a[0], anc_b[0], canvas_size=(1080, 1920))
    assert mc["concentric_locked"], f"Match-cut failed concentric lock: {mc}"
    assert mc["delta_center_pct"] <= 2.0 and mc["delta_r_pct"] <= 6.0
    assert mc["covers_full_canvas"], f"Expected 0 black borders on match-cut incoming B: {mc}"
    print(
        f"[OK] v6.0 Geometric Match-Cut: A={anc_a[0]['shape']}({anc_a[0]['cx_pct']:.1f}%,{anc_a[0]['cy_pct']:.1f}%,r={anc_a[0]['r_pct_w']:.1f}%) "
        f"<- B scale_in={mc['scale_in']:.3f} pos=({mc['pos_x_in']:.1f},{mc['pos_y_in']:.1f}) | "
        f"Δcenter={mc['delta_center_pct']:.3f}% <= 2.0% | Δr={mc['delta_r_pct']:.3f}% <= 6.0%"
    )

    # 3. True Vocal `J-Cut` Candidate Planner (`plan_true_vocal_jcuts`)
    synth_words = [
        ["Nhiều", 0.10, 0.34],
        ["người", 0.35, 0.62],
        ["quay", 0.64, 0.90],
        ["video", 0.92, 1.24],
        ["bị", 1.26, 1.44],
        ["chìm.", 1.46, 1.82],
        ["Nhưng", 2.10, 2.38],
        ["sai", 2.42, 2.68],
        ["lầm", 2.70, 2.98],
        ["lớn", 3.00, 3.26],
        ["nhất", 3.28, 3.55],
        ["nằm", 3.57, 3.82],
        ["ở", 3.84, 3.98],
        ["góc", 4.00, 4.30],
        ["máy.", 4.32, 4.68],
        ["Giải", 4.96, 5.26],
        ["pháp", 5.30, 5.62],
        ["rất", 5.64, 5.88],
        ["đơn", 5.90, 6.15],
        ["giản.", 6.17, 6.55],
    ]
    cad_doc = build_cadence_and_jcut_plan(synth_words, fps=60)
    vj_list = cad_doc["vocal_jcut_candidates"]
    assert len(vj_list) >= 2, f"Expected >=2 vocal J-cut candidates, got {vj_list}"
    for vj in vj_list:
        assert 240 <= vj["vocal_lead_ms"] <= 550, f"Vocal J-cut outside 240-550ms: {vj}"
        assert vj["t_visual_cut"] > vj["t_word_onset"]
    w_doc = build_words_tl_document(
        synth_words,
        fps=60,
        duration_sec=6.80,
        cadence_plan=cad_doc,
        gesture_action_peaks_s=peaks,
    )
    assert "gesture_action_peaks_s" in w_doc and len(w_doc["gesture_action_peaks_s"]) == len(peaks)
    assert "vocal_jcut_candidates" in w_doc["cadence_and_jcut_plan"]
    print(
        f"[OK] v6.0 True Vocal J-Cut Planner: {len(vj_list)} candidates | "
        f"first=({vj_list[0]['onset_word']}@{vj_list[0]['t_word_onset']:.2f}s -> cut@{vj_list[0]['t_visual_cut']:.3f}s on '{vj_list[0]['stressed_word']}', lead={vj_list[0]['vocal_lead_ms']}ms)"
    )

    # 4. v7.0 Cranial Exclusion Band, Dual-Rail Safe Zones & Zero-Face Macro Safe-Zones
    c_band, d_rails = compute_cranial_and_dual_rails(1080, 1920, hair_top_y=420, chin_y=860)
    assert c_band == [372, 892], f"Expected cranial_exclusion_band=[372, 892], got {c_band}"
    assert d_rails is not None
    assert d_rails["upper_editorial_stage"]["y_band_px"] == [220, 372]
    assert d_rails["chest_tactile_rail"]["y_band_px"] == [892, 1440]

    # Synthetic Zero-Face Dental close-up: Porcelain enamel (RGB 242,240,234 -> L*>94) next to pink gingiva (RGB 220,115,124 -> a*>38)
    dental_rgb = np.full((480, 270, 3), (28, 36, 48), dtype=np.uint8)
    cv2.rectangle(dental_rgb, (55, 175), (215, 222), (220, 115, 124), -1)  # Upper pink gingiva
    cv2.rectangle(dental_rgb, (62, 220), (208, 268), (242, 240, 234), -1)  # Bright porcelain enamel arch
    cv2.rectangle(dental_rgb, (58, 266), (212, 305), (216, 112, 122), -1)  # Lower pink gingiva/lip
    eg_bbox, eg_detail = detect_cie_lab_enamel_gum_roi(dental_rgb, 1080, 1920)
    assert eg_bbox is not None and eg_detail is not None, "Expected enamel_gum_bbox on dental close-up"
    assert eg_detail["enamel_mean_L_star"] > 72.0 and eg_detail["gum_mean_a_star"] > 16.0

    # Plain white wall must NOT trigger false-positive enamel_gum_bbox
    white_wall = np.full((480, 270, 3), (245, 245, 245), dtype=np.uint8)
    eg_none, _ = detect_cie_lab_enamel_gum_roi(white_wall, 1080, 1920)
    assert eg_none is None, f"Plain white wall falsely triggered enamel_gum_bbox: {eg_none}"

    # Synthetic Zero-Face Nail/Skincare Hand Macro shot
    nail_rgb = np.full((480, 270, 3), (38, 30, 28), dtype=np.uint8)
    cv2.rectangle(nail_rgb, (82, 180), (192, 380), (216, 168, 145), -1)  # Hand/fingers
    cv2.circle(nail_rgb, (110, 185), 14, (244, 166, 184), -1)  # Blush Rose gel nail
    cv2.circle(nail_rgb, (158, 180), 14, (245, 196, 81), -1)   # Champagne Gold accent nail
    mac_bbox, mac_detail = detect_hsv_edge_macro_saliency_box(nail_rgb, 1080, 1920)
    assert mac_bbox is not None and mac_detail is not None, "Expected macro_subject_bbox on nail/hand close-up"
    print(
        f"[OK] v7.0 Safe-Zone Detectors: cranial={c_band} | enamel_gum_bbox={eg_bbox} "
        f"(L*={eg_detail['enamel_mean_L_star']}, a*={eg_detail['gum_mean_a_star']}) | nail_macro_bbox={mac_bbox}"
    )

    # 5. End-to-end `probe_and_align` bundle smoke test (`media_probe.json` + `workspace_context.json` v7.0 routing)
    with tempfile.TemporaryDirectory(prefix="probe_v7_test_") as tmp_d:
        td = Path(tmp_d)
        bdir = td / "bundle"
        wdir = td / "work"
        (bdir / "assets" / "broll").mkdir(parents=True, exist_ok=True)
        Image.fromarray(cv2.cvtColor(shot_a, cv2.COLOR_BGR2RGB)).save(bdir / "assets" / "broll" / "br01_lens.jpg", quality=92)
        Image.fromarray(cv2.cvtColor(shot_rect, cv2.COLOR_BGR2RGB)).save(bdir / "assets" / "broll" / "br02_card.jpg", quality=92)
        Image.fromarray(cv2.resize(dental_rgb, (1080, 1920))).save(bdir / "assets" / "broll" / "br03_dental_macro.jpg", quality=95)
        ctx = probe_and_align(
            input_path=bdir,
            work_dir=wdir,
            skip_whisper=True,
            tier="studio",
            industry_skin="dental_clinic",
            format_mode="F4",
        )
        assert ctx["industry_skin"] == "dental_clinic"
        assert ctx["format_mode"] == "clinical_aesthetic_before_after"
        assert ctx["routing_v7"]["ram_governance"]["schedule_policy"] == "sequential_rvm_then_chrome_max2"
        mp = json.loads((wdir / "media_probe.json").read_text(encoding="utf-8"))
        assert mp["assets/broll/br01_lens.jpg"]["geometric_anchors"][0]["shape"] == "circle"
        assert mp["assets/broll/br02_card.jpg"]["geometric_anchors"][0]["shape"] == "rect"
        assert mp["assets/broll/br03_dental_macro.jpg"]["enamel_gum_bbox"] is not None
        assert mp["assets/broll/br03_dental_macro.jpg"]["macro_subject_bbox"] is not None
        print(
            f"[OK] v7.0 End-to-End Bundle Probe: version={ctx['version']} | "
            f"skin={ctx['industry_skin']} x format={ctx['format_mode']} | enamel_gum_bbox & geometric_anchors verified"
        )

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="probe_and_align.py",
        description="Universal Stateless Ingest, Probe, Audit, Alignment, 10x8 Industry Routing & Safe-Zone Engine v7.0.0.",
    )
    parser.add_argument(
        "--input",
        required=False,
        default=None,
        help="Path to raw video/audio file, project bundle directory, or .fcproj file.",
    )
    parser.add_argument(
        "--work",
        required=False,
        default=None,
        help="Working directory where unified JSON telemetry and contact sheet artifacts are written.",
    )
    parser.add_argument(
        "--tier",
        choices=["auto", "fast", "studio", "full"],
        default="auto",
        help="Execution tier: 'auto' (default), 'fast', 'studio' (P0+P1 Multi-Industry & Lane-B), or 'full' (P0+P1+P2 Forensic).",
    )
    parser.add_argument(
        "--industry-skin",
        default=None,
        help="Optional v7.0 Industry Skin ID (luxury_skincare, dental_clinic, nail_hair_salon, tactile_review, course_edtech, personal_brand, cinematic_vlog, b2b_saas_realestate, or legacy ecom/beauty_spa/real_estate/tech_saas/education).",
    )
    parser.add_argument(
        "--format-mode",
        default=None,
        help="Optional v7.0 Video Format Mode ID or code F1..F10 (e.g. expert_talking_head, pas_bab_ecom_conversion, clinical_aesthetic_before_after, faceless_motion_explainer).",
    )
    parser.add_argument(
        "--refine-onsets",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable 20ms RMS S04 acoustic onset tightening (default: active in 'studio'/'full' tiers, off in 'fast' tier).",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Optional ground-truth script (.txt, .md) or storyboard manifest (.json) for zero-typo NFC word alignment.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup existing *.fcproj to ~/.cache/opa-video-studio/backup/<stem>-<timestamp>.fcproj.",
    )
    parser.add_argument(
        "--whisper-model",
        default="small",
        help="faster-whisper model size/path (default: small).",
    )
    parser.add_argument(
        "--language",
        default="vi",
        help="ASR language code for faster-whisper (default: vi, or 'auto').",
    )
    parser.add_argument(
        "--skip-whisper",
        action="store_true",
        help="Skip faster-whisper transcription (audit & media probe only).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in v6.0 + v7.0 verification self-tests and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_v6_self_tests()

    if not args.input or not args.work:
        parser.error("the following arguments are required: --input, --work")

    ctx = probe_and_align(
        input_path=args.input,
        work_dir=args.work,
        script_path=args.script,
        backup=args.backup,
        whisper_model=args.whisper_model,
        language=args.language,
        skip_whisper=args.skip_whisper,
        tier=args.tier,
        refine_onsets=args.refine_onsets,
        industry_skin=args.industry_skin,
        format_mode=args.format_mode,
    )

    sp = ctx["speech_summary"]
    cad = sp.get("cadence_summary") or {}
    warns = len(ctx["audit_warnings"])
    route_tag = ""
    if ctx.get("industry_skin") or ctx.get("format_mode"):
        route_tag = f"route={ctx.get('industry_skin') or '-'}x{ctx.get('format_mode') or '-'} | "
    print(
        f"[PROBE & ALIGN v{VERSION} OK] mode={ctx['mode']} | tier={ctx['execution_tier_used']}(rec={ctx['recommended_compile_tier']}) | "
        f"{route_tag}elapsed={ctx['elapsed_sec']:.2f}s | dur={ctx['duration_sec']:.2f}s @ {ctx['fps_grid']}fps | "
        f"media={ctx['media_inventory']['total_files']} | slices={sp.get('slice_count', 0)} | "
        f"words={sp.get('word_count', 0)} | cuts={cad.get('boundary_count', 0)}"
        f"(fast={cad.get('fast_chain_count', 0)}/pivot={cad.get('chapter_pivot_count', 0)}/vjcut={sp.get('vocal_jcut_candidate_count', 0)}) | "
        f"peaks={sp.get('gesture_action_peak_count', 0)} | warnings={warns} -> {ctx['work_dir']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
