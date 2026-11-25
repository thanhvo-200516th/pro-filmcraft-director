#!/usr/bin/env python3
"""
Automated Verification Suite for `pro-filmcraft-director` v7.3.0.
Checks syntax, portable paths, preset catalogs, references, and v7.3 compositor/audio-sync guards.
"""

from __future__ import annotations

import json
import py_compile
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"

for p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_01_python_syntax_and_zero_hardcoded_user_paths() -> None:
    py_files = sorted(SKILL_ROOT.rglob("*.py"))
    assert len(py_files) >= 10, f"Expected >=10 python files, found {len(py_files)}"
    for pf in py_files:
        if "__pycache__" in pf.parts:
            continue
        py_compile.compile(str(pf), doraise=True)
        if pf.resolve() == Path(__file__).resolve():
            continue
        src = pf.read_text(encoding="utf-8")
        assert "/home/thanh" not in src, f"Non-portable path '/home/thanh' found in {pf.relative_to(SKILL_ROOT)}"

    mjs_file = SCRIPTS_DIR / "web_cinema_plate_engine.mjs"
    assert mjs_file.is_file(), "Missing web_cinema_plate_engine.mjs"
    assert "/home/thanh" not in mjs_file.read_text(encoding="utf-8"), "Non-portable path in web_cinema_plate_engine.mjs"
    print(f"[PASS] Syntax & portability verified across {len(py_files)} Python files + web_cinema_plate_engine.mjs")


def test_02_presets_and_references() -> None:
    presets = sorted((SKILL_ROOT / "presets").glob("*.json"))
    assert len(presets) >= 9, f"Expected >=9 JSON presets, found {len(presets)}"
    for pj in presets:
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list)) and len(data) > 0, f"Empty preset {pj.name}"

    refs = sorted((SKILL_ROOT / "references").glob("*.md"))
    assert len(refs) >= 20, f"Expected >=20 markdown references (01..20), found {len(refs)}"
    assert (SKILL_ROOT / "SKILL.md").is_file(), "Missing SKILL.md"
    print(f"[PASS] Verified {len(presets)} JSON preset catalogs & {len(refs)} reference documents")


def test_03_v73_compositor_and_sync_guard() -> None:
    import fast_studio_compositor as fsc

    # 1. Hair-safe wall init + rounded hair crown preservation
    h, w = 1920, 1080
    wall = np.full((h, w, 3), (62, 78, 92), dtype=np.uint8)
    # Synthetic thin coat-rack hook (width 6px at y=780..835)
    wall[780:835, 440:446] = (18, 20, 22)
    fsc.init_hair_safe_wall_reference(wall, cache_key="unit_test_ref")

    frame = wall.copy()
    # Synthetic convex rounded hair dome rising up to y=805 (width 180px) connected to head below y=880
    import cv2

    cv2.ellipse(frame, (460, 895), (95, 90), 0, 0, 360, (20, 24, 30), -1)
    cleaned = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="unit_test_ref")
    # Hair pixel at y=815 (well above old 845 chop!) must remain dark hair, NOT wall color!
    hair_luma = float(cleaned[815, 460].mean())
    assert hair_luma < 40.0, f"Expected rounded hair preserved at y=815, got luma={hair_luma:.1f}"

    # 2. Option A1 + Option A2 + Option B renderers
    bg = np.full((h, w, 3), 242, dtype=np.uint8)
    out_a1, bbox_a1 = fsc.render_full_head_studio_card(bg, cleaned, card_rect=(86, 775, 994, 1825))
    assert out_a1.shape == (h, w, 3) and len(bbox_a1) == 4

    out_a2, bbox_a2 = fsc.render_squircle_pip_window(bg, cleaned, pip_rect=(700, 1400, 1012, 1800))
    assert out_a2.shape == (h, w, 3) and len(bbox_a2) == 4

    pa = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(pa, (540, 1450), (380, 520), 0, 0, 360, 255, -1)
    out_b, bbox_b = fsc.render_bottom_flush_cutout(bg, cleaned, pa)
    assert out_b.shape == (h, w, 3) and len(bbox_b) == 4

    # 3. Audio Voice Sync Guard
    with tempfile.TemporaryDirectory() as td:
        wav_ok = Path(td) / "ok.wav"
        sr = 16000
        dur = 4.0
        t = np.linspace(0.0, dur, int(sr * dur), endpoint=False)
        sig = (0.25 * np.sin(2.0 * np.pi * 220.0 * t) * 32767.0).astype(np.int16)
        with wave.open(str(wav_ok), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(sig.tobytes())

        stats = fsc.verify_audio_voice_sync_guard(wav_ok, 4.0)
        assert stats["speech_density"] > 0.90

        # Mismatched uncut duration (e.g. 8.5s vs 4.0s) MUST raise ValueError/RuntimeError!
        caught = False
        try:
            fsc.verify_audio_voice_sync_guard(wav_ok, 8.5)
        except (RuntimeError, ValueError):
            caught = True
        assert caught, "verify_audio_voice_sync_guard failed to reject drifted audio duration!"

    print("[PASS] Verified v7.3 Hair-Safe Opening, Hybrid Option A1/A2/B Renderers & VoiceSyncGuard")


if __name__ == "__main__":
    test_01_python_syntax_and_zero_hardcoded_user_paths()
    test_02_presets_and_references()
    test_03_v73_compositor_and_sync_guard()
    print("TẤT CẢ ĐẠT (pro-filmcraft-director v7.3.0)")
