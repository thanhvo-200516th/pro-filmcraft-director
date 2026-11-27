#!/usr/bin/env python3
"""
sfx_shift.py — shift SFX clips in a spec by the list qa_sync wrote, into a NEW spec (the source spec is never edited).

    sfx_shift.py --spec X.craft.json --shifts sfx_shifts.json --out NEW.craft.json

This is a brain-triggered Gate 7b, never an automatic loop: it refuses to run twice on the same lineage. The new spec carries
`meta.sfx_shifted_once = true`; a spec that already has that marker is refused (exit 3). After one shift: compile the new spec,
export only if the user asks, measure again with qa_sync, and let the brain decide anything further by hand.

sfx_shifts.json = qa_sync output: [{"beat","clip","track","at","src","name","shift" | "trim"}, ...] (a {"shifts": [...]} wrapper is
accepted). shift > 0 moves the clip later (seconds); trim = drop that many seconds from the head of the file while the peak stays
in place (`at` and `in` grow together).

Clips are matched by (track, at +-2 ms, src). Clamps: never before 0 s and never past the end of the video; a clip that already
sits at the head of the video (at <= 0.05 s) and must move earlier has its file head cut instead (`in` grows, `dur` shrinks, gain
keyframes shift). Exit 1 when a shift matches no clip (the spec changed after measuring: run qa_sync again). Warning only when two
SFX on one track overlap after the shift.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

AT_TOL = 0.002
HEAD_AT = 0.05             # s: a clip with at <= this is the opening SFX
MARKER = "sfx_shifted_once"


def _trim_head(clip: dict, x: float) -> None:
    """Drop the first x seconds of the clip (`at` stays): in += x, dur -= x, gain keyframes shift by -x keeping the value at 0."""
    x = min(x, clip["dur"] - 0.05)
    g = clip.get("gain_db")
    if isinstance(g, list):
        ks = sorted((float(k[0]), float(k[1])) for k in g)
        v0 = float(np.interp(x, [k[0] for k in ks], [k[1] for k in ks]))
        clip["gain_db"] = [[0, round(v0, 3)]] + [[round(t - x, 4), v] for t, v in ks if t > x]
    clip["in"] = round(float(clip.get("in", 0)) + x, 4)
    clip["dur"] = round(clip["dur"] - x, 4)


def overlaps(spec: dict) -> list[str]:
    """SFX pairs on the same track that overlap by more than 1 ms (a shift can create them)."""
    out = []
    for t in spec["tracks"]:
        if t.get("type") == "audio" and "SFX" in t.get("name", ""):
            cs = sorted(t["clips"], key=lambda c: c["at"])
            out += [f"{t['name']} · {a['at']:.3f}+{a['dur']:.2f} overlaps {b['at']:.3f}" for a, b in zip(cs, cs[1:])
                    if a["at"] + a["dur"] > b["at"] + 0.001]
    return out


def apply_shifts(spec: dict, shifts: list[dict]) -> tuple[dict, list[str], list[str]]:
    """(new spec, applied lines, unmatched lines). The input spec is not modified."""
    out = copy.deepcopy(spec)
    end = float(out["duration"])
    done: list[str] = []
    missing: list[str] = []
    for sh in shifts:
        clip = next((c for t in out["tracks"] if t.get("name") == sh["track"] for c in t["clips"]
                     if abs(c["at"] - sh["at"]) <= AT_TOL and c.get("src") == sh["src"]), None)
        if clip is None:
            missing.append(f"{sh['track']} · {sh['at']:.3f} s · {sh.get('name', '')}")
            continue
        cut = float(sh.get("trim", 0.0))
        want = clip["at"] + float(sh.get("shift", 0.0)) + cut
        trim = cut or (-want if want < 0 and clip["at"] <= HEAD_AT else 0.0)
        new_at = want if cut else min(max(0.0, want), max(0.0, end - clip["dur"]))
        done.append(f"[{sh.get('beat', '?')}] {sh['track']} · {clip['at']:.3f} -> {new_at:.3f} s ({new_at - clip['at']:+.3f})"
                    f"{f' · head cut {trim:.3f} s' if trim else ''} · {sh.get('name', '')}")
        clip["at"] = round(new_at, 4)
        if trim:
            _trim_head(clip, trim)
    return out, done, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="the measured .craft.json (never modified)")
    ap.add_argument("--shifts", required=True, help="sfx_shifts.json from qa_sync.py")
    ap.add_argument("--out", required=True, help="NEW .craft.json to write")
    a = ap.parse_args()
    spec_path, out_path = Path(a.spec), Path(a.out)
    if out_path.resolve() == spec_path.resolve():
        print("--out is the source spec: write to a new file name.", file=sys.stderr)
        return 2
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    raw = json.loads(Path(a.shifts).read_text(encoding="utf-8"))
    shifts = raw.get("shifts", []) if isinstance(raw, dict) else raw
    if (spec.get("meta") or {}).get(MARKER):
        print(f"REFUSED: this spec already carries meta.{MARKER} (one shift per lineage). The brain decides the next step by hand; "
              "no automatic second pass.", file=sys.stderr)
        return 3
    new, done, missing = apply_shifts(spec, shifts)
    new["meta"] = {**(new.get("meta") or {}), MARKER: True}
    if not missing:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    print("\n".join(f"shift {d}" for d in done) or "no SFX needs shifting")
    for m in missing:
        print(f"ERROR no clip matches: {m}", file=sys.stderr)
    for o in overlaps(new):
        print(f"WARNING overlap: {o}")
    state = f"-> {out_path}" if not missing else "NOT written (unmatched shifts)"
    print(f"{state} ({len(done)} shifted · {len(missing)} unmatched). Compile the new spec, then run qa_sync again.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
