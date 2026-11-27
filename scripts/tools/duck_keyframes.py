#!/usr/bin/env python3
"""
duck_keyframes.py — pure BGM ducking envelope generator (no sidechain, no media, no ffmpeg).

Turns word spans (seconds) into 4-point volume keyframes `(t, gain_db)` per phrase, the shape documented in
references/25_loudness_tiktok_vs_nle.md section 7 row 7:

  (start - pre_roll, high) -> (start - pre_roll + ramp_down, low) -> (end + release_delay, low) -> (end + release_delay + release, high)

* `pre_roll_sec`, `release_sec`, `hold_through_gap_under_sec` are READ from presets/sfx_micro_sync_rules.json
  (`ducking_4_point_envelope`); the optional vacuum floor / length are READ from presets/atomic_motion_library.json
  (`vacuum_32db_0p4s`). Derived, unvalidated on real speech: `ramp_down_sec` 0.25, `release_delay_sec` 0.2,
  `max_depth_db` 10, vacuum rate limit (once per 20 s).
* Gaps shorter than `hold_through_gap_under_sec` keep the bed ducked (anti-pumping); a phrase whose pre-roll would
  start before the previous release has finished is merged into it.
* Depth = `bed_high_db - bed_low_db` (reference: 8 dB). Gains never leave [bed_low_db, bed_high_db], except for the
  optional vacuum, which dips to `vacuum_db` on purpose.
* Output is clamped to [`clip_start`, `clip_end`]; edge values are interpolated, no release is invented past the end.

Library use:   duck_keyframes(word_spans, bed_high_db, bed_low_db, params=None) -> tuple[(t, gain_db), ...]
CLI:           duck_keyframes.py words.json --high -20 --low -28 [--clip-end 40]   (words.json: [[start, end], ...])
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence

SKILL_ROOT = Path(__file__).resolve().parents[2]
SYNC_RULES = SKILL_ROOT / "presets" / "sfx_micro_sync_rules.json"
ATOMICS = SKILL_ROOT / "presets" / "atomic_motion_library.json"
_ND = 6  # rounding of times and gains: keeps results deterministic and free of float dust

Keyframe = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class DuckParams:
    pre_roll_sec: float
    release_sec: float
    hold_through_gap_under_sec: float
    vacuum_db: float
    vacuum_sec: float
    ramp_down_sec: float = 0.25
    release_delay_sec: float = 0.2
    max_depth_db: float = 10.0
    clip_start: float = 0.0
    clip_end: Optional[float] = None
    vacuum_hits: tuple[float, ...] = ()
    vacuum_edge_sec: float = 0.05
    vacuum_min_interval_sec: float = 20.0


def default_params() -> DuckParams:
    env = json.loads(SYNC_RULES.read_text(encoding="utf-8"))["ducking_4_point_envelope"]
    vac = json.loads(ATOMICS.read_text(encoding="utf-8"))["atomics"]["vacuum_32db_0p4s"]
    return DuckParams(
        pre_roll_sec=float(env["pre_roll_sec"]),
        release_sec=float(env["release_sec"]),
        hold_through_gap_under_sec=float(env["hold_through_gap_under_sec"]),
        vacuum_db=float(vac["floor_dbfs"]),
        vacuum_sec=float(vac["duration_s"]),
    )


def level_at(points: Sequence[Keyframe], t: float) -> float:
    """Piecewise-linear value of `points` at `t`; held flat before the first and after the last point."""
    if not points:
        raise ValueError("level_at needs at least one keyframe")
    if t <= points[0][0]:
        return points[0][1]
    for (t0, g0), (t1, g1) in zip(points, points[1:]):
        if t <= t1:
            return g0 if g0 == g1 else g0 + (g1 - g0) * (t - t0) / (t1 - t0)
    return points[-1][1]


def _clean_spans(word_spans: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    out = []
    for sp in word_spans:
        if len(sp) != 2:
            raise ValueError(f"word span must be (start, end), got {tuple(sp)!r}")
        s, e = float(sp[0]), float(sp[1])
        if not (math.isfinite(s) and math.isfinite(e)) or e < s:
            raise ValueError(f"invalid word span ({s}, {e})")
        out.append((s, e))
    return sorted(out)


def _phrases(spans: list[tuple[float, float]], p: DuckParams) -> list[tuple[float, float]]:
    """Merge spans whose gap is under the hold threshold, or whose pre-roll would start before the previous release ends."""
    merged: list[tuple[float, float]] = []
    for s, e in spans:
        if merged:
            ps, pe = merged[-1]
            release_end = pe + p.release_delay_sec + p.release_sec
            if s - pe < p.hold_through_gap_under_sec or s - p.pre_roll_sec < release_end:
                merged[-1] = (ps, max(pe, e))
                continue
        merged.append((s, e))
    return merged


def _dedupe(points: list[Keyframe]) -> list[Keyframe]:
    out: list[Keyframe] = []
    for t, g in sorted((round(t, _ND), round(g, _ND)) for t, g in points):
        if out and out[-1][0] == t:
            out[-1] = (t, g)
        else:
            out.append((t, g))
    return out


def _apply_vacuum(points: list[Keyframe], p: DuckParams) -> list[Keyframe]:
    accepted: list[float] = []
    for hit in sorted(float(h) for h in p.vacuum_hits):
        if not accepted or hit - accepted[-1] >= p.vacuum_min_interval_sec:
            accepted.append(hit)
    for hit in accepted:
        t0, edge = hit - p.vacuum_sec, p.vacuum_edge_sec
        before, after = level_at(points, t0 - edge), level_at(points, hit + edge)
        kept = [q for q in points if q[0] < t0 - edge or q[0] > hit + edge]
        points = _dedupe([*kept, (t0 - edge, before), (t0, p.vacuum_db), (hit, p.vacuum_db), (hit + edge, after)])
    return points


def _clamp(points: list[Keyframe], lo: float, hi: Optional[float]) -> list[Keyframe]:
    out: list[Keyframe] = []
    first = points[0][0]
    if first < lo or (hi is not None and first > lo):
        out.append((lo, level_at(points, lo)))
    out.extend(q for q in points if q[0] >= lo and (hi is None or q[0] <= hi))
    if hi is not None and out[-1][0] < hi:
        out.append((hi, level_at(points, hi)))
    return _dedupe(out)


def duck_keyframes(word_spans: Iterable[Sequence[float]], bed_high_db: float, bed_low_db: float,
                   params: Optional[DuckParams] = None) -> tuple[Keyframe, ...]:
    """Word spans -> immutable tuple of (t, gain_db) keyframes ducking the bed from `bed_high_db` to `bed_low_db`."""
    p = params or default_params()
    high, low = float(bed_high_db), float(bed_low_db)
    if not (math.isfinite(high) and math.isfinite(low)) or low > high:
        raise ValueError(f"need finite bed_low_db <= bed_high_db, got low={low} high={high}")
    if high - low > p.max_depth_db:
        raise ValueError(f"duck depth {high - low:g} dB exceeds max_depth_db {p.max_depth_db:g}")
    if p.clip_end is not None and p.clip_end < p.clip_start:
        raise ValueError(f"clip_end {p.clip_end} before clip_start {p.clip_start}")
    phrases = _phrases(_clean_spans(word_spans), p)
    points: list[Keyframe] = []
    for s, e in phrases:
        down = s - p.pre_roll_sec
        points += [(down, high), (down + p.ramp_down_sec, low),
                   (e + p.release_delay_sec, low), (e + p.release_delay_sec + p.release_sec, high)]
    if not points:
        points = [(p.clip_start, high)]
    points = _apply_vacuum(_dedupe(points), p)
    return tuple(_clamp(points, p.clip_start, p.clip_end))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    ap.add_argument("words", help="JSON file: [[start_s, end_s], ...]")
    ap.add_argument("--high", type=float, required=True, help="bed gain_db when nobody speaks")
    ap.add_argument("--low", type=float, required=True, help="bed gain_db while speaking")
    ap.add_argument("--clip-start", type=float, default=0.0)
    ap.add_argument("--clip-end", type=float)
    ap.add_argument("--vacuum-hit", type=float, action="append", default=[], help="hit time (s); repeatable")
    a = ap.parse_args()
    params = dataclasses.replace(default_params(), clip_start=a.clip_start, clip_end=a.clip_end,
                                 vacuum_hits=tuple(a.vacuum_hit))
    spans = json.loads(Path(a.words).read_text(encoding="utf-8"))
    print(json.dumps([list(k) for k in duck_keyframes(spans, a.high, a.low, params)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
