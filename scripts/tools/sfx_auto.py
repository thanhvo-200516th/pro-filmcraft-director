#!/usr/bin/env python3
"""
sfx_auto.py — stateless SFX cue planner: events (hero-word entrance, transition, punch) -> catalog group -> clips.

  sfx_auto.py plan --events events.json --catalog presets/sfx_catalog.json --sfx-root DIR [--opening-seed N] --out cues.json
                   [--rules presets/sfx_micro_sync_rules.json]

`--sfx-root` (alias `--portable-root`) is the sound-library root: every catalog path is RELATIVE to it, and the
emitted clips carry the same relative `src` (the brain joins it with its own root or bundle).

events.json:
  {"duration": 40.0, "fps": 30, "name": "optional video name",
   "words": [["word", start, end], ...],                      # optional, only decides speaking / quiet gain
   "cues": [{"cue": "hero_word" | "transition" | "punch", "t": seconds, "text": "optional word",
             "group": "optional catalog group override", "offset_ms": optional (clamped to the rule range), "dur": optional}]}

Rules (presets/sfx_micro_sync_rules.json):
  - hero_word: the aligned sound lands +100..+300 ms after the cue time (default +150 ms).
  - transition: peak on the cut (offset 0); punch: peak on the punch.
  - opening: two files at frame 0-1; the pair is chosen by --opening-seed (different seed -> different pair).
  - heavy whooshes/impacts are capped at <= 5 per minute (rate over the whole video and in any 60 s window); once the
    budget is spent a transition falls back to the next of the 7 Organic Foley groups (listed under "downgraded").
  - levels by tier (big / mid / soft) and by voice (speaking = about 5 dB lower); no file is reused inside 6 s, and no
    file is reused at all while an unused one is left in the group.

The tool measures (peak position, lead, tail, peak dB of each file) and writes `at / in / dur / gain_db` per clip;
the brain places them on audio tracks. Exit 1 when a cue had no usable file under --sfx-root (see "skipped").
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import unicodedata
import zlib
from pathlib import Path

import numpy as np

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
TIER_RANK = {"big": 3, "mid": 2, "soft": 1}
REUSE_GAP = 6.0
# Mirrors compile_and_verify._HEAVY_WHOOSH_IMPACT_HINTS / _SOFT_FOLEY_EXCLUSION_HINTS so the cap counts what Gate 7 counts.
HEAVY_HINTS = ("whoosh", "swoosh", "swish", "whip", "impact", "boom", "slam", "thud", "braam", "riser_hit", "punch", "sub_drop", "chuyển cảnh")
SOFT_HINTS = ("click", "tick", "keystroke", "typewriter", "paper", "cloth_soft", "breath", "camera_shutter_soft")
HARD_HEAVY = ("whoosh", "swoosh", "impact", "boom", "slam")

FALLBACK_RULES = {
    "heavy_whoosh_cap_per_min": 5,
    "heavy_groups": ["whoosh", "boom_pre", "flash_hit", "suck_in", "leak"],
    "organic_foley_7": {"catalog_groups": ["foley_paper_slide", "foley_key_tick", "foley_shutter_click", "foley_felt_muted",
                                           "foley_glass_ping", "foley_cloth_brush", "foley_air_puff"]},
    "cue_to_group_offsets": {
        "hero_word": {"group": "key_hit", "offset_ms": 150, "offset_ms_range": [100, 300], "name_tag": "Từ khoá"},
        "transition": {"group": "whoosh", "offset_ms": 0, "offset_ms_range": [-134, 0]},
        "punch": {"group": "key_hit", "offset_ms": 0, "offset_ms_range": [-50, 100], "name_tag": "nhấn nỗi đau"},
    },
}


# ----------------------------------------------------------------------------- audio measuring
_INFO_CACHE: dict[str, dict] = {}


def sfx_info(path: Path) -> dict:
    """lead (first sound), peak_t (loudest moment, 10 ms RMS smoothed), peak_db, dur, tail (last sound) of one file."""
    key = str(path)
    if key in _INFO_CACHE:
        return _INFO_CACHE[key]
    pcm = subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-i", key, "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                         capture_output=True, timeout=1800).stdout
    x = np.abs(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768)
    if len(x) == 0:
        raise ValueError(f"cannot decode {path}")
    peak = float(x.max()) or 1e-9
    win = 480
    env = np.array([x[i:i + win].max() for i in range(0, len(x), win)])
    above = np.nonzero(env > peak * 10 ** (-30 / 20))[0]
    lead = above[0] * 0.01 if len(above) else 0.0
    tail = (above[-1] + 1) * 0.01 if len(above) else len(x) / 48000
    rms = np.array([np.sqrt(np.mean(x[i:i + win] ** 2)) for i in range(0, len(x), win)])
    if len(rms) >= 5:
        rms = np.convolve(np.pad(rms, 2, mode="edge"), np.ones(5) / 5, mode="valid")
    info = {"lead": round(float(lead), 3), "peak_t": round(int(np.argmax(rms)) * 0.01, 3),
            "peak_db": round(20 * float(np.log10(peak)), 1), "dur": round(len(x) / 48000, 3), "tail": round(float(tail), 3)}
    _INFO_CACHE[key] = info
    return info


def make_clip(path: Path, cue_t: float, align: str, peak_target_db: float, max_dur: float | None, end: float,
              max_pre: float | None = None) -> dict:
    """at / in / dur / gain_db so that the file's peak (align=peak) or onset (align=onset) lands on `cue_t`.
    `max_pre`: for peak-aligned files the sound may not start more than this many seconds before its peak (the head is cut
    and the gain ramps in over 2 frames)."""
    info = sfx_info(path)
    s_in = info["lead"]
    cut_head = align == "peak" and max_pre is not None and info["peak_t"] - s_in > max_pre
    if cut_head:
        s_in = round(info["peak_t"] - max_pre, 3)
    at = cue_t - max(0.0, info["peak_t"] - s_in) if align == "peak" else cue_t
    if at < 0:
        s_in, at = s_in - at, 0.0
    natural = min(info["dur"], info["tail"] + 0.3) - s_in
    dur = natural if max_dur is None else min(natural, max_dur)
    dur = round(min(dur, end - at), 3)
    gain = round(peak_target_db - float(info["peak_db"]), 1)
    gain_db: float | list = gain
    if at + dur >= end - 1e-3 and dur < natural - 0.01:      # clipped by the end of the video: fade out 0.25 s
        gain_db = [[0, gain], [round(max(0.0, dur - 0.25), 3), gain], [dur, -40]]
    if cut_head:                                             # entering mid-sound: fast ramp instead of a click
        ramp = round(min(0.066, dur / 3), 3)
        rest = gain_db[1:] if isinstance(gain_db, list) else [[dur, gain]]
        gain_db = [[0, -30], [ramp, gain]] + rest
    return {"at": round(at, 4), "in": round(s_in, 3), "dur": dur, "gain_db": gain_db,
            "peak_at": round(at + max(0.0, info["peak_t"] - s_in), 4)}


# ----------------------------------------------------------------------------- planning
def load_rules(catalog_path: Path, rules_arg: str | None) -> dict:
    cand = Path(rules_arg) if rules_arg else catalog_path.with_name("sfx_micro_sync_rules.json")
    rules = json.loads(cand.read_text(encoding="utf-8")) if cand.is_file() else {}
    merged = dict(FALLBACK_RULES)
    merged.update({k: v for k, v in rules.items() if k in FALLBACK_RULES})
    return merged


def is_heavy(group: str, src: str, name: str, heavy_groups: set[str]) -> bool:
    if group in heavy_groups:
        return True
    stem = unicodedata.normalize("NFC", Path(src).stem).lower()
    hay = f"{unicodedata.normalize('NFC', name).lower()} {stem}"
    if any(s in hay for s in SOFT_HINTS) and not any(h in hay for h in HARD_HEAVY):
        return False
    return any(h in hay for h in HEAVY_HINTS)


def voice_active(t: float, words: list, pad: float = 0.08) -> bool:
    return any(float(w[1]) - pad <= t <= float(w[2]) + pad for w in words)


class Picker:
    """Round-robin file chooser per group: unused files first, then files not heard in the last REUSE_GAP seconds."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.last_used: dict[str, float] = {}
        self.cursor: dict[str, int] = {}

    def pick(self, group: str, files: list[str], t: float) -> str | None:
        avail = [f for f in files if (self.root / f).is_file()]
        if not avail:
            return None
        n = len(avail)
        start = self.cursor.get(group, 0)
        for k in range(n):
            f = avail[(start + k) % n]
            if f not in self.last_used:
                self.cursor[group] = (start + k + 1) % n
                return self._take(f, t)
        for k in range(n):
            f = avail[(start + k) % n]
            if t - self.last_used[f] >= REUSE_GAP:
                self.cursor[group] = (start + k + 1) % n
                return self._take(f, t)
        return self._take(min(avail, key=lambda x: self.last_used[x]), t)

    def _take(self, f: str, t: float) -> str:
        self.last_used[f] = t
        return f


def clamp_offset_ms(cue: dict, rule: dict) -> int:
    lo, hi = rule.get("offset_ms_range", [rule.get("offset_ms", 0)] * 2)
    want = cue.get("offset_ms", rule.get("offset_ms", 0))
    return int(min(max(float(want), lo), hi))


def level_for(kind: dict, levels: dict, speaking: bool) -> float:
    lv = levels["transition"] if kind.get("transition") else levels[kind["tier"]]
    return float(lv[0 if speaking else 1])


def plan(events: dict, catalog: dict, rules: dict, root: Path, opening_seed: int | None) -> dict:
    fps = int(events.get("fps", 30))
    end = float(events["duration"])
    words = events.get("words") or []
    kinds, levels = catalog["kinds"], catalog["levels"]
    offsets = rules["cue_to_group_offsets"]
    heavy_groups = set(rules["heavy_groups"])
    cap = float(rules["heavy_whoosh_cap_per_min"])
    foley = [g for g in rules["organic_foley_7"]["catalog_groups"] if g in kinds]
    picker = Picker(root)
    clips: list[dict] = []
    skipped: list[dict] = []
    downgraded: list[dict] = []
    heavy_times: list[float] = []
    foley_cursor = 0

    def budget_ok(t: float) -> bool:
        in_window = sum(1 for h in heavy_times if t - 60.0 < h <= t)
        return in_window < cap and (len(heavy_times) + 1) / max(end / 60.0, 1e-9) <= cap + 1e-9

    def emit(cue: str, group: str, t_cue: float, t_sfx: float, cue_in: dict, tag_name: str) -> bool:
        """Place one clip; a heavy file only while the budget allows, otherwise a non-heavy file or an Organic Foley group."""
        nonlocal foley_cursor
        k = kinds[group]
        allow_heavy = budget_ok(t_sfx)
        files = k["files"] if allow_heavy else [f for f in k["files"] if not is_heavy(group, f, "", heavy_groups)]
        src = picker.pick(group, files, t_sfx)
        if src is None and not allow_heavy and foley and group not in foley:
            alt = foley[foley_cursor % len(foley)]
            foley_cursor += 1
            downgraded.append({"t": round(t_cue, 3), "from": group, "to": alt, "reason": f"heavy cap {cap:g}/min spent"})
            group, k = alt, kinds[alt]
            src = picker.pick(group, k["files"], t_sfx)
        if src is None:
            skipped.append({"cue": cue, "t": round(t_cue, 3), "group": group, "reason": "no usable file of this group under --sfx-root"})
            return False
        max_dur = k.get("max_dur")
        if k.get("trim") and cue_in.get("dur"):
            max_dur = max(0.12, float(cue_in["dur"]) + 0.1)
        speaking = voice_active(t_sfx, words)
        m = make_clip(root / src, t_sfx, k["align"], level_for(k, levels, speaking), max_dur, end, k.get("max_pre"))
        name = f"SFX {group} · {tag_name}"
        heavy = is_heavy(group, src, name, heavy_groups)
        if heavy:
            heavy_times.append(t_sfx)
        clips.append({"cue": cue, "group": group, "t_cue": round(t_cue, 4), "t_sfx": round(t_sfx, 4),
                      "offset_ms": int(round((t_sfx - t_cue) * 1000)), "src": src, "align": k["align"], "name": name,
                      "heavy": heavy, **m})
        return True

    # opening: frame 0-1 (two files of one pair)
    pairs = catalog["opening"]["pairs"]
    if pairs and events.get("opening", True):
        seed = zlib.crc32(str(events.get("name", "")).encode()) if opening_seed is None else opening_seed
        pair = pairs[seed % len(pairs)]
        for i, rel in enumerate(pair):
            if not (root / rel).is_file():
                skipped.append({"cue": "opening", "t": 0.0, "group": "opening", "reason": f"missing file {rel}"})
                continue
            peak_db = float(levels.get("opening", [-9, -9])[0])
            m = make_clip(root / rel, 0.0, "onset", peak_db, 0.35 if i == 0 else 0.6, end)
            name = f"SFX MỞ ĐẦU · {Path(rel).stem[:24]}"
            clips.append({"cue": "opening", "group": "opening", "t_cue": 0.0, "t_sfx": 0.0, "offset_ms": 0, "src": rel,
                          "align": "onset", "name": name, "heavy": is_heavy("opening", rel, name, heavy_groups), **m})
            picker.last_used[rel] = 0.0
            if clips[-1]["heavy"]:
                heavy_times.append(0.0)

    cues = sorted(events.get("cues", []), key=lambda c: float(c["t"]))
    for c in cues:
        kind = c.get("cue")
        rule = offsets.get(kind)
        if rule is None:
            skipped.append({"cue": kind, "t": c.get("t"), "reason": f"unknown cue (known: {', '.join(offsets)})"})
            continue
        group = c.get("group") or rule["group"]
        if group not in kinds:
            skipped.append({"cue": kind, "t": c.get("t"), "group": group, "reason": "group not in catalog"})
            continue
        t_cue = float(c["t"])
        t_sfx = max(0.0, t_cue + clamp_offset_ms(c, rule) / 1000.0)
        if t_sfx > end:
            skipped.append({"cue": kind, "t": t_cue, "group": group, "reason": "after the end of the video"})
            continue
        if kind in ("hero_word", "punch") and t_sfx < 0.3 and pairs:
            continue                                         # the opening SFX already owns frames 0-0.3 s
        tag = c.get("text") or c.get("why") or f"@{t_cue:.2f}"
        tag_name = f"«{tag}»" if kind in ("hero_word", "punch") else str(tag)
        if rule.get("name_tag"):
            tag_name = f"{rule['name_tag']} · {tag_name}" if kind == "hero_word" else f"{rule['name_tag']} {tag_name}"
        before = len(clips)
        if emit(kind, group, t_cue, t_sfx, c, tag_name) and clips[-1]["group"] == group:
            partner = kinds[group].get("with")
            if partner and partner in kinds and before < len(clips):
                if emit(kind, partner, t_cue, t_sfx, c, f"{tag_name} · layer"):
                    clips[-1]["layer_of"] = group

    clips.sort(key=lambda c: (c["at"], c["name"]))
    n_heavy = sum(1 for c in clips if c["heavy"])
    return {
        "schema": "sfx_auto/1", "fps": fps, "duration": end, "name": events.get("name"), "opening_seed": opening_seed,
        "clips": clips, "skipped": skipped, "downgraded": downgraded,
        "stats": {"clips": len(clips), "heavy": n_heavy, "heavy_per_min": round(n_heavy / max(end / 60.0, 1e-9), 2),
                  "cap_per_min": cap},
    }


def cmd_plan(a: argparse.Namespace) -> int:
    try:
        events = json.loads(Path(a.events).read_text(encoding="utf-8"))
        catalog_path = Path(a.catalog)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        events["duration"]
    except (OSError, ValueError, KeyError) as e:
        print(f"bad input: {e!r} (events need a numeric 'duration')", file=sys.stderr)
        return 2
    root = Path(a.sfx_root)
    if not root.is_dir():
        print(f"--sfx-root is not a directory: {root}", file=sys.stderr)
        return 2
    rules = load_rules(catalog_path, a.rules)
    result = plan(events, catalog, rules, root, a.opening_seed)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    s = result["stats"]
    print(f"{s['clips']} clips · heavy {s['heavy']} ({s['heavy_per_min']}/min, cap {s['cap_per_min']:g}) · "
          f"{len(result['downgraded'])} downgraded to foley · {len(result['skipped'])} skipped -> {out}")
    for sk in result["skipped"]:
        print(f"SKIPPED {sk}", file=sys.stderr)
    return 1 if result["skipped"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="events.json -> cues.json")
    p.add_argument("--events", required=True)
    p.add_argument("--catalog", required=True, help="presets/sfx_catalog.json (relative paths only)")
    p.add_argument("--sfx-root", "--portable-root", dest="sfx_root", required=True, help="library root every catalog path is relative to")
    p.add_argument("--opening-seed", type=int, default=None, help="picks the opening pair (pair index = seed mod pair count)")
    p.add_argument("--rules", default=None, help="sfx_micro_sync_rules.json (default: next to the catalog)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_plan)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
