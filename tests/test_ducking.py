#!/usr/bin/env python3
"""
Unit tests for `scripts/tools/duck_keyframes.py` (v7.5.0): pure 4-point BGM ducking keyframes. No media, no ffmpeg.

Run: python3 tests/test_ducking.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import duck_keyframes as dk  # noqa: E402

HIGH, LOW = -20.0, -28.0  # 8 dB depth
RULES = json.loads((SKILL_ROOT / "presets" / "sfx_micro_sync_rules.json").read_text(encoding="utf-8"))["ducking_4_point_envelope"]
PRE, REL, HOLD = RULES["pre_roll_sec"], RULES["release_sec"], RULES["hold_through_gap_under_sec"]
RAMP, DELAY = 0.25, 0.2


def approx(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(a - b) <= tol


def test_constants_are_read_from_preset() -> None:
    p = dk.default_params()
    assert (p.pre_roll_sec, p.release_sec, p.hold_through_gap_under_sec) == (PRE, REL, HOLD)
    assert (p.ramp_down_sec, p.release_delay_sec) == (RAMP, DELAY)
    assert (PRE, REL, HOLD) == (0.35, 0.7, 1.5), "preset constants moved: docs (ref 25 row 7) must follow"
    print("[PASS] pre-roll / release / hold constants come from sfx_micro_sync_rules.json")


def test_single_phrase_is_four_points() -> None:
    kf = dk.duck_keyframes([(2.0, 2.4), (2.5, 3.0)], HIGH, LOW)
    t0, t1, t2, t3 = (k[0] for k in kf[:4])
    assert approx(t0, 2.0 - PRE) and kf[0][1] == HIGH
    assert approx(t1, 2.0 - PRE + RAMP) and kf[1][1] == LOW  # low reached 0.1 s before the first word
    assert approx(t2, 3.0 + DELAY) and kf[2][1] == LOW
    assert approx(t3, 3.0 + DELAY + REL) and kf[3][1] == HIGH
    assert len(kf) == 4
    print("[PASS] one phrase = exactly 4 keyframes with the documented timings")


def test_gap_under_1p5_is_held_and_over_is_released() -> None:
    held = dk.duck_keyframes([(1.0, 2.0), (3.4, 4.0)], HIGH, LOW)  # gap 1.4 < 1.5
    assert len(held) == 4, held
    assert approx(held[2][0], 4.0 + DELAY)
    split = dk.duck_keyframes([(1.0, 2.0), (3.5, 4.0)], HIGH, LOW)  # gap 1.5: not under -> two phrases
    assert len(split) == 8, split
    assert split[3][1] == HIGH and split[4][1] == HIGH and split[5][1] == LOW
    print("[PASS] gaps < 1.5 s merge into one hold, >= 1.5 s release and re-duck")


def test_properties_on_synthetic_spans() -> None:
    spans = [(0.4, 0.9), (1.0, 1.6), (4.0, 4.5), (4.6, 5.2), (9.0, 9.3), (12.0, 15.0), (15.4, 16.0), (30.0, 30.2)]
    kf = dk.duck_keyframes(spans, HIGH, LOW, dataclasses.replace(dk.default_params(), clip_end=40.0))
    times = [t for t, _ in kf]
    assert all(b > a for a, b in zip(times, times[1:])), f"times must be strictly increasing: {times}"
    assert all(LOW - 1e-9 <= g <= HIGH + 1e-9 for _, g in kf), "depth must never exceed bed_high - bed_low"
    assert times[0] == 0.0 and times[-1] == 40.0
    # every word is covered by a point of the LOW plateau
    for s, e in spans:
        lvl = dk.level_at(kf, (s + e) / 2)
        assert lvl == LOW, (s, e, lvl)
    assert dk.duck_keyframes(spans, HIGH, LOW) == dk.duck_keyframes(list(reversed(spans)), HIGH, LOW), "input order must not matter"
    assert dk.duck_keyframes(spans, HIGH, LOW) == dk.duck_keyframes(spans, HIGH, LOW), "deterministic"
    print("[PASS] monotonic, depth bounded, words covered, deterministic, order independent")


def test_clip_bounds_clamp() -> None:
    p = dataclasses.replace(dk.default_params(), clip_start=0.0, clip_end=5.0)
    kf = dk.duck_keyframes([(0.1, 1.0), (4.9, 7.0)], HIGH, LOW, p)
    assert kf[0][0] == 0.0 and kf[-1][0] == 5.0
    assert all(0.0 <= t <= 5.0 for t, _ in kf)
    assert kf[0][1] < HIGH, "first word 0.1 s in: the 0.35 s pre-roll is already partly ducked at t=0"
    assert kf[-1][1] == LOW, "words run past the clip end: stays ducked, no release is invented"
    print("[PASS] keyframes are clamped to clip bounds with interpolated edge values")


def test_no_words_and_bad_input() -> None:
    assert dk.duck_keyframes([], HIGH, LOW) == ((0.0, HIGH),)
    p = dataclasses.replace(dk.default_params(), clip_end=3.0)
    assert dk.duck_keyframes([], HIGH, LOW, p) == ((0.0, HIGH), (3.0, HIGH))
    for bad in ([(2.0, 1.0)], [(float("nan"), 1.0)], [(-1.0, 1.0, 2.0)]):
        try:
            dk.duck_keyframes(bad, HIGH, LOW)
        except ValueError:
            continue
        raise AssertionError(f"bad span {bad} must raise ValueError")
    try:
        dk.duck_keyframes([(1.0, 2.0)], -20.0, -45.0)  # 25 dB deep: far beyond the window
    except ValueError:
        pass
    else:
        raise AssertionError("depth above max_depth_db must raise")
    try:
        dk.duck_keyframes([(1.0, 2.0)], -28.0, -20.0)  # inverted
    except ValueError:
        pass
    else:
        raise AssertionError("bed_low_db above bed_high_db must raise")
    print("[PASS] empty / invalid spans and depth are handled loudly")


def test_inputs_not_mutated() -> None:
    spans = [[3.0, 4.0], [1.0, 2.0]]
    snapshot = json.dumps(spans)
    out = dk.duck_keyframes(spans, HIGH, LOW)
    assert json.dumps(spans) == snapshot
    assert isinstance(out, tuple) and all(isinstance(k, tuple) for k in out)
    print("[PASS] inputs untouched, result is an immutable tuple of tuples")


def test_vacuum_optional_and_rate_limited() -> None:
    base = dk.duck_keyframes([(1.0, 2.0), (30.0, 31.0)], HIGH, LOW, dataclasses.replace(dk.default_params(), clip_end=40.0))
    floor = dk.default_params().vacuum_db
    assert floor == -32.0 and dk.default_params().vacuum_sec == 0.4
    assert min(g for _, g in base) == LOW, "no vacuum unless requested"
    p = dataclasses.replace(dk.default_params(), clip_end=40.0, vacuum_hits=(10.0, 20.0, 31.5, 35.0))
    kf = dk.duck_keyframes([(1.0, 2.0), (30.0, 31.0)], HIGH, LOW, p)
    times = [t for t, _ in kf]
    assert all(b > a for a, b in zip(times, times[1:])), times
    assert dk.level_at(kf, 9.8) == floor and dk.level_at(kf, 9.61) == floor
    assert dk.level_at(kf, 20.0 - 0.2) == HIGH, "second hit is < 20 s after the first: dropped"
    assert dk.level_at(kf, 31.5 - 0.2) == floor, "hit > 20 s after the first vacuum is kept"
    assert dk.level_at(kf, 35.0 - 0.2) == HIGH, "hit 3.5 s after the last vacuum: dropped"
    assert dk.level_at(kf, 10.0 + 0.5) == HIGH, "bed is back at its open level after the hit"
    print("[PASS] vacuum is optional, -32 dB for 0.4 s, at most once per 20 s")


if __name__ == "__main__":
    test_constants_are_read_from_preset()
    test_single_phrase_is_four_points()
    test_gap_under_1p5_is_held_and_over_is_released()
    test_properties_on_synthetic_spans()
    test_clip_bounds_clamp()
    test_no_words_and_bad_input()
    test_inputs_not_mutated()
    test_vacuum_optional_and_rate_limited()
    print("TẤT CẢ ĐẠT (duck_keyframes v7.5.0)")
