#!/usr/bin/env python3
"""
studio_recipe.py (v7.9.0): stateless Look S scene planner and pacing validator. The brain still decides; this only lays out the V21 pattern.

`plan_scenes(words_tl, duration, look="S")` scales the V21 scene grid of presets/studio_scene_recipe.json to `duration`,
snaps each cut to the nearest word gap, assigns a mode per beat (hook=H, text=A1/P, B-roll=A2, tension=N, steps=S, CTA=B),
enforces the polarity minimum (>= 2 light scenes, ~14 %), the plain A-roll cap and no adjacent same colour world,
and emits the jewel hex per act. Pure functions; the only I/O is the preset and a words json (dict doc or bare array).

v7.7.0 adds the hook-first-5s and pacing law (references/28_hook_first_5s_and_pacing.md), all pure and returning structured findings
(`{rule, severity error|warn, t0, t1, value, limit, message}`, empty list = clean):
`hook_template()` (hook recipe v3 as events with ms offsets), `check_hook(plan)` (first text <= 300 ms, hero box 12-18 % of frame height,
<= 5 text events in 0-3 s each held >= 600 ms, >= 3 resets in 0-3.4 s, vacuum dip >= 12 dB, whoosh within 12 ms of the punch cut),
`check_pacing(shots, resets, duration)` (max hold 2.4 s, >= 3 resets in the 0-5 s hook window and >= 2 in every later 5 s window, per-window `hold_s` and
`dead_hold_share`, shots < 1 s advisory) and `check_source_reuse(shots)` (the same B-roll source seconds never twice).

v7.8.0 (hook text must match the voice, product-safe zone, motion floor; same finding format): `hook_text_from_words(words)` builds the hook texts from the
transcript (lead line quoting the first clause, keyword hero 150-200 ms before its word, later clauses; the voice is never re-cut); `check_hook(hook, words=None)`
adds `text_voice_sync` (text onset 0-400 ms before the matching word, warn outside 100-250 ms, first text -50..+250 ms, numerals only when voiced),
`hero_safe_zone` (hero box vs `product_bbox` or the `stage` cap-top line; the rendered twin is `hero_product_overlap_px` of motion_gate.py), `text_min_size` (64 px, 3.3 %)
and `hook_motion_floor` (a BACKGROUND reset in every 1.0 s of 0-3.4 s; PiP pops and text are overlay resets); `check_pacing` adds `bg_static_hold` for shots flagged
`broll` with `moves`, and `plan_micro_moves(shots)` proposes the remedy. Resets are `{t, kind, layer: bg|overlay, mag}`; floats and tuples stay bg resets.
v7.9.0 (v4 review): `check_text_legibility` (every overlay text / card label at font x plate scale), `text_coverage` (no text-free gap > 150 ms in 0-3 s), `flash_luma_cap` / `flash_rate` and `word_gap_collision` (motion_gate), `first_text_late` (`strict_first_text=True`, the default: text at or before the first word).

CLI: studio_recipe.py --words W.json --duration D --out scenes.json [--look S|D]   (exit 0 ok, 2 bad input, 3 rule violated)
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

VERSION = "7.9.0"
PRESET = Path(__file__).resolve().parent.parent.parent / "presets" / "studio_scene_recipe.json"


def _load(path: Path = PRESET) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _words(doc) -> list[tuple[str, float, float]]:
    seq = (doc.get("words") or doc.get("words_tl") or []) if isinstance(doc, dict) else doc
    return [(str(w[0]), float(w[1]), float(w[2])) for w in seq]


def _kept_grid(grid: list[dict], words, duration: float, rec: dict) -> list[tuple[dict, float]]:
    """(grid entry, start) pairs: scaled to `duration`, snapped to word gaps, scenes shorter than `min_scene_s` absorbed."""
    scale, lo = duration / rec["reference_duration_s"], rec["min_scene_s"]
    gaps = [(a[2] + b[1]) / 2 for a, b in zip(words, words[1:])]
    raw = [0.0]
    for g in grid[1:]:
        t = g["start_s"] * scale
        near = min(gaps, key=lambda x: abs(x - t), default=t)
        raw.append(round(near if abs(near - t) <= rec["snap_tolerance_s"] else t, 3))
    raw[-1] = min(raw[-1], round(duration - lo, 3))
    keep, edge = [len(raw) - 1], raw[-1]
    for i in range(len(raw) - 2, 0, -1):  # walk back so the hook and the CTA survive on short timelines
        if edge - raw[i] >= lo and raw[i] >= lo:
            keep.append(i)
            edge = raw[i]
    return [(grid[i], raw[i]) for i in [0] + sorted(keep)]


def _polarity(scenes: list[dict], duration: float, rec: dict) -> list[dict]:
    pol, modes = rec["polarity"], [s["mode"] for s in scenes]
    length = lambda i: scenes[i]["end"] - scenes[i]["start"]  # noqa: E731
    done = lambda: modes.count("P") >= pol["min_light_scenes"] and sum(length(i) for i, m in enumerate(modes) if m == "P") / duration >= pol["min_light_share"]  # noqa: E731
    for i in sorted((i for i, m in enumerate(modes) if m in rec["polarity_candidates"]), key=lambda i: -length(i)):
        if done():
            break
        modes[i] = "P"
    return [{**s, "mode": m} for s, m in zip(scenes, modes)]


def _decorate(scenes: list[dict], words, rec: dict) -> list[dict]:
    chs, papers, out, prev, n_light = rec["chapters"], rec["polarity"]["papers"], [], None, 0
    jewels = [c["jewel"] for c in chs]
    for s in scenes:
        ch, fam = chs[s["chapter"]], rec["modes"][s["mode"]]["family"]
        cycle = papers[n_light % 3:] + papers[:n_light % 3] if s["mode"] == "P" else [rec["neon"]] if s["mode"] == "N" else jewels[s["chapter"]:] + jewels[:s["chapter"]]
        hue = next((h for h in cycle if (fam, h) != prev), cycle[0])
        n_light += s["mode"] == "P"
        text = " ".join(w for w, t0, _ in words if s["start"] <= t0 < s["end"]).split()[:8]
        out.append({**s, "act": ch["act"], "family": fam, "hue": hue, "jewel": ch["ink_on_light"] if s["mode"] == "P" else ch["jewel"] if s["mode"] == "N" else hue,
                    "render": rec["modes"][s["mode"]]["render"], "bg": rec["polarity"]["light_bg"] if s["mode"] == "P" else None,
                    "template": rec["templates"][s["kind"]], "text": " ".join(text)})
        prev = (fam, hue)
    return out


def check_scenes(scenes: list[dict], duration: float, preset: dict | None = None) -> list[str]:
    """Rule violations of a scene list (empty = ok): light minimum, plain A-roll cap, adjacent colour worlds."""
    rec = preset or _load()
    pol, span = rec["polarity"], lambda ss: sum(s["end"] - s["start"] for s in ss)  # noqa: E731
    light = [s for s in scenes if s["mode"] == "P"]
    plain = [s for s in scenes if s["mode"] == "A0" or s.get("family") == "plain"]
    bad = []
    if len(light) < pol["min_light_scenes"]:
        bad.append(f"light scenes {len(light)} < {pol['min_light_scenes']}")
    if span(light) / duration < pol["min_light_share"]:
        bad.append(f"light share {span(light) / duration:.2f} < {pol['min_light_share']}")
    if span(plain) / duration > rec["plain_aroll_max_share"]:
        bad.append(f"plain A-roll share {span(plain) / duration:.2f} > {rec['plain_aroll_max_share']}")
    bad += [f"adjacent same colour world {a['id']}/{b['id']}" for a, b in zip(scenes, scenes[1:]) if (a["family"], a["hue"]) == (b["family"], b["hue"])]
    return bad


def plan_scenes(words_tl, duration: float, look: str = "S", preset: dict | None = None) -> dict:
    rec = preset or _load()
    if look not in ("S", "D"):
        raise ValueError(f"look must be 'S' or 'D', got {look!r}")
    if duration < 2 * rec["min_scene_s"]:
        raise ValueError(f"duration must be >= {2 * rec['min_scene_s']} s, got {duration}")
    words, end = _words(words_tl), round(float(duration), 3)
    if look == "D":
        one = {"id": "D01", "start": 0.0, "end": end, "mode": "D", "kind": "strip", "chapter": 0, "act": 0, "family": "strip", "hue": None,
               "jewel": None, "render": rec["modes"]["D"]["render"], "bg": None, "template": "screen_strip", "text": ""}
        return {"look": "D", "duration": end, "scenes": [one], "stats": {"light_count": 0, "light_share": 0.0, "plain_share": 0.0, "ok": True, "violations": []}}
    kept, chs = _kept_grid(rec["grid"], words, duration, rec), rec["chapters"]
    ends = [t for _, t in kept[1:]] + [end]
    scenes = [{"id": g["id"], "start": t, "end": e, "mode": g["mode"], "kind": g["kind"],
               "chapter": max(i for i, c in enumerate(chs) if c["start_s"] <= g["start_s"])} for (g, t), e in zip(kept, ends)]
    scenes = _decorate(_polarity(scenes, duration, rec), words, rec)
    bad = check_scenes(scenes, duration, rec)
    share = lambda ss: round(sum(s["end"] - s["start"] for s in ss) / duration, 3)  # noqa: E731
    light = [s for s in scenes if s["mode"] == "P"]
    stats = {"light_count": len(light), "light_share": share(light), "plain_share": share([s for s in scenes if s["mode"] == "A0"]),
             "ok": not bad, "violations": bad}
    return {"look": "S", "duration": end, "audio_profile": rec["audio"]["profile"], "chapters": chs, "scenes": scenes, "stats": stats}


# --------------------------------------------------------------------------------------------- v7.7.0 hook + pacing law
def _f(rule: str, msg: str, severity: str = "error", t0: float | None = None, t1: float | None = None, value=None, limit=None, **extra) -> dict:
    return {"rule": rule, "severity": severity, "t0": t0, "t1": t1, "value": value, "limit": limit, "message": msg, **extra}


def hook_template(preset: dict | None = None) -> dict:
    """A copy of the `hook_0_5s` template (hook recipe v3): events with `t_ms` offsets for text, SFX, zoom, flash and vacuum."""
    return copy.deepcopy((preset or _load())["hook_0_5s"])


def _merged(times: list[float], gap: float) -> list[float]:
    out: list[float] = []
    for t in sorted(times):
        if not out or t - out[-1] >= gap:
            out.append(t)
    return out


_SKIP = {"vì", "mà", "và", "thì", "nhưng"}  # connectives skipped at a clause start
_STOP = _SKIP | {"là", "trên", "đây", "đó", "này", "bọn", "mình", "vừa", "làm", "cho", "các", "của", "có", "được", "một", "những"}  # not a keyword hero


def _fold(w) -> str:
    """NFC, lower-case, accent-folded, punctuation-free form of a word for matching."""
    d = unicodedata.normalize("NFD", unicodedata.normalize("NFC", str(w)).lower().replace("đ", "d"))
    return re.sub(r"[^0-9a-z]", "", "".join(c for c in d if unicodedata.category(c) != "Mn"))


def _nlow(w) -> str:
    return unicodedata.normalize("NFC", str(w)).lower().strip(".,!?;:\"'")


def _span(ws: list, i: int, n: int, stop: bool = False) -> list:
    """Up to `n` contiguous words from index `i` (gap <= 0.3 s); with `stop` the span ends at the first stop word."""
    out = [ws[i]]
    for w in ws[i + 1:i + n]:
        if w[1] - out[-1][2] > 0.3 or (stop and _nlow(w[0]) in _STOP):
            break
        out.append(w)
    return out


def hook_text_from_words(words, preset: dict | None = None, strict: bool = True) -> list[dict]:
    """Hook text events built from the transcript (the voice is never re-cut; the picture follows it).

    Lead line (<= `first_text_max_ms`) quotes the first clause; the hero is the first keyword voiced in 0.3-1.5 s, onset 150-200 ms before its word;
    one later clause follows >= 500 ms after (every text is a spoken word, a numeral only from the voice); each holds until the next (the last until `cover_ms`); `strict` (default since v7.9.0; False = the old +30 ms) puts the lead 20 ms BEFORE its word (v4 E1 landed 47 ms after it). `[]` for no words."""
    full = preset or _load()
    rec, mo, ws = full["hook_0_5s"], full["pacing"]["motion"], _words(words)
    bud, lead, hold = rec["text_budget_0_3s"], mo["text_lead_ms"][0] + 10, rec["text_budget_0_3s"]["hold_min_ms"]
    start = next((i for i, w in enumerate(ws) if _nlow(w[0]) not in _SKIP), None)
    if start is None:
        return []
    mk = lambda t, tier, sp, **kw: {"t_ms": t, "kind": "text", "id": tier, "tier": tier, "text": unicodedata.normalize("NFC", " ".join(w[0] for w in sp).upper()),  # noqa: E731
                                    "voice_words": [_nlow(w[0]) for w in sp], "dur_ms": hold, "lead_ms": round(sp[0][1] * 1000) - t, **kw}
    small = {"font_px": mo["min_font_px"] + 8, "glyph_frac": round(mo["min_text_box_frac"] * 1.2, 3)}
    sp = _span(ws, start, 3)
    out = [mk(max(0, min(rec["first_text_max_ms"], round(sp[0][1] * 1000) + (-20 if strict else 30))), "lead", sp, **small)]
    lo, hi = rec["hero_box"]["height_frac"]
    hero = next((i for i, w in enumerate(ws) if 0.3 <= w[1] <= 1.5 and _nlow(w[0]) not in _STOP and i >= start + len(sp)), None)
    last = start + len(sp) - 1
    if hero is not None:
        sp = _span(ws, hero, 3, stop=True)
        out.append(mk(max(round(sp[0][1] * 1000) - lead, out[-1]["t_ms"] + bud["spacing_ms"][0]), "hero", sp, height_frac=round((lo + hi) / 2, 3)))
        last = hero + len(sp) - 1
    nxt = next((i for i in range(last + 1, len(ws)) if _nlow(ws[i][0]) not in _SKIP), None)
    if nxt is not None:
        sp = _span(ws, nxt, 4)
        t = max(round(sp[0][1] * 1000) - lead, out[-1]["t_ms"] + bud["spacing_ms"][0])
        if t < 3000 and t <= round(sp[0][1] * 1000):
            out.append(mk(t, "support", sp, dur_ms=hold + 300, **small))
    for a, b in zip(out, out[1:] + [None]):
        a["dur_ms"] = max(a["dur_ms"], (b["t_ms"] if b else bud.get("cover_ms", 3000)) - a["t_ms"])
    return out


def _text_sync(texts: list[dict], words, mo: dict) -> list[dict]:
    """`text_voice_sync`: the first spoken word of each text begins 0-400 ms AFTER the text onset (warn outside the keyword band)."""
    if words is None:
        return [_f("text_voice_sync", "no words provided: text-voice sync not checked", "warn")]
    spoken, bad = [(_fold(w[0]), round(w[1] * 1000)) for w in _words(words)], []
    for k, e in enumerate(texts):
        toks = [x for x in (_fold(w) for w in (e.get("voice_words") or str(e.get("text") or "").split())) if x]
        if not toks:
            continue  # unbound template slot
        first, num = k == 0, toks[0].isdigit()
        lo, hi = mo["first_text_lead_ms"] if first else (-mo["numeral_window_ms"], mo["numeral_window_ms"]) if num else (0, mo["voice_lead_max_ms"])
        leads = [t - e["t_ms"] for w, t in spoken if w == toks[0]]
        t0, tag = e["t_ms"] / 1000, e.get("id")
        near = min(leads, key=lambda v: max(lo - v, v - hi, 0), default=None)
        if near is None or not lo <= near <= hi:
            why = "is not in the spoken words" if near is None else f"is voiced {near} ms after the text, allowed {lo}..{hi} ms"
            bad.append(_f("text_voice_sync", f"text '{tag}' ({toks[0]}) {why}; the text must match the words being spoken", t0=t0, value=near, limit=[lo, hi]))
            continue
        if not (first or num) and not mo["keyword_lead_ms"][0] <= near <= mo["keyword_lead_ms"][1]:
            bad.append(_f("text_voice_sync", f"text '{tag}' leads its word by {near} ms, comfort band {mo['keyword_lead_ms'][0]}-{mo['keyword_lead_ms'][1]} ms", "warn", t0, value=near, limit=mo["keyword_lead_ms"]))
        bad += [_f("text_voice_sync", f"text '{tag}': '{x}' is not in the spoken words", "warn", t0) for x in toks[1:] if x not in {w for w, _ in spoken}]
    return bad


def check_text_legibility(items: list[dict], preset: dict | None = None, H: int = 1920) -> list[dict]:
    """`text_min_size` for EVERY overlay text (hook texts, card labels, plate captions): `font_px` x plate `scale` >= 64 px, glyph box (`glyph_px` / `glyph_frac`) >= 3.3 % of H; `decorative: true` only lowers it to a warning (v4 K1: labels 10-27 px)."""
    mo, bad = (preset or _load())["pacing"]["motion"], []
    for e in items:
        sev, t0, px = "warn" if e.get("decorative") else "error", e.get("t_ms", 0) / 1000, e["font_px"] * e.get("scale", 1.0) if "font_px" in e else None
        fr = e["glyph_px"] / H if "glyph_px" in e else e.get("glyph_frac")
        if px is not None and px < mo["min_font_px"] - 1e-6:
            bad.append(_f("text_min_size", f"text '{e.get('id')}' font {px:.0f} px (font x plate scale) < {mo['min_font_px']} px", sev, t0, value=round(px, 1), limit=mo["min_font_px"], id=e.get("id")))
        if fr is not None and fr < mo["min_text_box_frac"]:
            bad.append(_f("text_min_size", f"text '{e.get('id')}' glyph box {fr:.4f} < {mo['min_text_box_frac']} of frame height", sev, t0, value=round(fr, 4), limit=mo["min_text_box_frac"], id=e.get("id")))
    return bad


def _coverage(texts: list[dict], bud: dict) -> list[dict]:
    """`text_coverage`: from the first text to `cover_ms`, no stretch longer than `max_gap_ms` without on-screen text (v4: 1.30-1.49, 2.43-2.73 s)."""
    bad, end, cov, mx = [], None, bud.get("cover_ms", 3000), bud.get("max_gap_ms", 150)
    for e in sorted(texts, key=lambda e: e["t_ms"]) + [{"t_ms": cov, "dur_ms": 0}]:
        if end is not None and min(e["t_ms"], cov) - end > mx:
            bad.append(_f("text_coverage", f"no on-screen text for {min(e['t_ms'], cov) - end} ms at {end / 1000:.2f}-{min(e['t_ms'], cov) / 1000:.2f} s, max {mx} ms: hold the previous text or start the next earlier", t0=end / 1000, t1=min(e["t_ms"], cov) / 1000, value=min(e["t_ms"], cov) - end, limit=mx))
        end = max(end if end is not None else 0, e["t_ms"] + e.get("dur_ms", bud["hold_min_ms"]))
    return bad


def _safe_zone(hook: dict, heroes: list[dict], mo: dict) -> list[dict]:
    """`hero_safe_zone` (plan level): the hero box must not overlap the product (2 % of the hero area tolerated). Rendered twin: `hero_product_overlap_px`."""
    w, h = hook.get("frame", (1080, 1920))
    stage = hook.get("stage") or hook.get("hero_box", {}).get("stage")
    prod = hook.get("product_bbox") or ((0, round(mo["stage_cap_top_frac"] * h), w, h) if stage else None)
    bad = []
    for e in heroes:
        box = e.get("box") or hook.get("hero_box", {}).get("rect")
        if not box or not prod:
            continue
        ov = max(0, min(box[2], prod[2]) - max(box[0], prod[0])) * max(0, min(box[3], prod[3]) - max(box[1], prod[1]))
        if ov > mo["overlap_tol_frac"] * (box[2] - box[0]) * (box[3] - box[1]):
            bad.append(_f("hero_safe_zone", f"hero '{e.get('id')}' box {list(box)} overlaps the product {list(prod)} by {ov} px2; keep it in the stage above the cap (rendered check: hero_product_overlap_px)", t0=e["t_ms"] / 1000, value=ov, limit=0))
    return bad


def _reset(r, mo: dict | None = None) -> dict:
    """Typed reset `{t, kind, layer, mag}` from a float, `(t, kind[, layer[, mag]])` or a dict; a missing layer is `bg` (text is `overlay`)."""
    d = r if isinstance(r, dict) else dict(zip(("t", "kind", "layer", "mag"), r if isinstance(r, (tuple, list)) else (r,)))
    kind = d.get("kind", "zoom")
    return {"t": float(d["t"]), "kind": kind, "layer": d.get("layer") or ("overlay" if kind == "text" else "bg"), "mag": d.get("mag")}


def _ev_reset(e: dict) -> dict:
    mag = abs(e["to"] - e["from"]) if isinstance(e.get("to"), (int, float)) and isinstance(e.get("from"), (int, float)) else e.get("mag")
    return _reset({"t": e["t_ms"] / 1000, "kind": e["kind"], "layer": e.get("layer") or ("overlay" if e.get("target") == "pip" else None), "mag": mag})


def _is_bg(r: dict, mo: dict) -> bool:
    return r["layer"] == "bg" and not (r["kind"] == "zoom" and r["mag"] is not None and r["mag"] < mo["bg_zoom_step_min"])


def hook_motion_floor(resets, window_ms: float = 3400, preset: dict | None = None) -> list[dict]:
    """Every 1.0 s window of the hook (0-1, 1-2, 2-3 and the tail 2.4-3.4 s) needs >= 1 BACKGROUND reset: cut, flash, glint, card landing or a zoom step >= 4 %.
    PiP pops and text are overlay resets and never count. Resets: floats, tuples or `{t, kind, layer, mag}` (plain ones are bg)."""
    mo = (preset or _load())["pacing"]["motion"]
    step, w = mo["floor_window_s"], window_ms / 1000
    ts = [r["t"] for r in (_reset(x) for x in resets) if _is_bg(r, mo)]
    starts = [k * step for k in range(int(w // step + 1e-9))] + ([w - step] if w % step > 1e-9 else [])
    return [_f("hook_motion_floor", f"no background reset in {a:.1f}-{a + step:.1f} s (cut, flash, glint, card landing or zoom step >= {mo['bg_zoom_step_min']:.0%}); PiP pops and text are overlay resets", t0=round(a, 3), t1=round(a + step, 3), value=0, limit=1)
            for a in starts if not any(a <= t < a + step or (a + step >= w - 1e-9 and t == a + step) for t in ts)]


def check_hook(hook: dict, preset: dict | None = None, words=None, strict_first_text: bool = True) -> list[dict]:
    """Findings of a hook plan shaped like `hook_template()` (no errors = clean). Times in ms; rules from the template's own limits.

    `words` (probe doc or `[[word, t0, t1], ...]`) enables `text_voice_sync`; without it only a warning is added. Text events may carry `voice_words`, `box`,
    `font_px`, `glyph_frac`, `height_frac`; the hook may carry `product_bbox` (x0, y0, x1, y1 in 1080x1920) or `stage` `{s}`.
    v7.9.0: `labels` (card / plate text, `font_px` + plate `scale`), text `gap_px` + `entrance` keys, flash events and `base_luma` are checked too."""
    full = preset or _load()
    rec, pc, ev, mo = full["hook_0_5s"], full["pacing"], hook.get("events", []), full["pacing"]["motion"]
    kind = lambda k: sorted((e for e in ev if e["kind"] == k), key=lambda e: e["t_ms"])  # noqa: E731
    bad, texts, win = [], kind("text"), hook.get("window_ms", rec["window_ms"])
    if not texts or texts[0]["t_ms"] > rec["first_text_max_ms"]:
        bad.append(_f("first_text", f"first text at {texts[0]['t_ms'] if texts else 'never'} ms, must be <= {rec['first_text_max_ms']} ms", t0=0.0, value=texts[0]["t_ms"] if texts else None, limit=rec["first_text_max_ms"]))
    lo, hi = rec["hero_box"]["height_frac"]
    hb = hook.get("hero_box", {}).get("height_frac")
    for h in (hb if isinstance(hb, (list, tuple)) else [hb]):
        if h is None or not lo <= h <= hi:
            bad.append(_f("hero_box", f"hero box {h} of frame height outside {lo}-{hi}", value=h, limit=[lo, hi]))
            break
    heroes = [e for e in texts if e.get("tier") == "hero"]
    for h in (e["height_frac"] for e in heroes if "height_frac" in e):  # per tier: the lead line is not counted
        if not lo <= h <= hi:
            bad.append(_f("hero_box", f"hero tier box {h} of frame height outside {lo}-{hi}", value=h, limit=[lo, hi]))
    bad += _text_sync(texts, words, mo) + check_text_legibility(texts + hook.get("labels", []), full) + _safe_zone(hook, heroes, mo) + _coverage(texts, rec["text_budget_0_3s"])
    if strict_first_text and words is not None and texts and (o := next((round(w[1] * 1000) for w in _words(words) if _nlow(w[0]) not in _SKIP), None)) is not None and texts[0]["t_ms"] > o:
        bad.append(_f("first_text_late", f"first text at {texts[0]['t_ms']} ms is {texts[0]['t_ms'] - o} ms after the first word ({o} ms); it must be on screen at or before it (snap plate starts down)", t0=texts[0]["t_ms"] / 1000, value=texts[0]["t_ms"] - o, limit=0))
    sys.path.insert(0, str(Path(__file__).resolve().parent)) if str(Path(__file__).resolve().parent) not in sys.path else None
    import motion_gate as mg  # numpy / cv2, only needed here
    bad += (mg.check_flash_plan(ev, hook.get("base_luma", (ps := full.get("photosensitivity", {})).get("plan_base_luma", 80.0)), ps.get("max_flash_luma", 220.0), ps.get("max_flashes_per_s", 3))
            + mg.check_word_gaps([e for e in texts if "gap_px" in e and "font_px" in e], mo.get("min_word_gap_em", 0.25)))
    bud, early = rec["text_budget_0_3s"], [e for e in texts if e["t_ms"] < 3000]
    if len(early) > bud["max"]:
        bad.append(_f("text_budget", f"{len(early)} text events in 0-3 s, max {bud['max']}", t0=0.0, t1=3.0, value=len(early), limit=bud["max"]))
    elif len(early) < bud["min"]:
        bad.append(_f("text_budget", f"{len(early)} text events in 0-3 s, recipe asks {bud['min']}-{bud['max']}", "warn", 0.0, 3.0, len(early), bud["min"]))
    bad += [_f("text_hold", f"text '{e.get('id')}' held {e['dur_ms']} ms, must be >= {bud['hold_min_ms']} ms", t0=e["t_ms"] / 1000, value=e["dur_ms"], limit=bud["hold_min_ms"]) for e in early if e.get("dur_ms", bud["hold_min_ms"]) < bud["hold_min_ms"]]
    gaps = [b["t_ms"] - a["t_ms"] for a, b in zip(early, early[1:]) if b["t_ms"] != a["t_ms"]]
    if any(not bud["spacing_ms"][0] <= g <= bud["spacing_ms"][1] for g in gaps):
        bad.append(_f("text_spacing", f"text onsets {gaps} ms apart, recipe {bud['spacing_ms'][0]}-{bud['spacing_ms'][1]} ms", "warn", value=gaps, limit=bud["spacing_ms"]))
    resets = _merged([e["t_ms"] / 1000 for e in ev if e["kind"] in pc["reset_kinds"] and 0 < e["t_ms"] <= win], pc["merge_s"])
    need = math.floor(win / 1000 * rec["resets_per_s_0_3p4"])
    if len(resets) < need:
        bad.append(_f("hook_resets", f"{len(resets)} visual resets in 0-{win / 1000:.1f} s, need >= {need} (one per second)", t0=0.0, t1=win / 1000, value=len(resets), limit=need))
    bad += hook_motion_floor([_ev_reset(e) for e in ev if e["kind"] in pc["reset_kinds"]], win, full)
    vac = kind("vacuum")
    if not vac or -vac[0].get("duck_db", 0) < rec["vacuum_min_dip_db"]:
        bad.append(_f("vacuum_dip", f"vacuum dip {-vac[0].get('duck_db', 0) if vac else 0} dB at 3.2-3.4 s, must be >= {rec['vacuum_min_dip_db']} dB (target {rec['vacuum_target_dip_db']})", t0=3.2, t1=3.4, value=-vac[0].get("duck_db", 0) if vac else 0, limit=rec["vacuum_min_dip_db"]))
    for c in (e for e in kind("cut") if e.get("needs_whoosh")):
        near = [abs(e["at_ms"] + e["peak_ms"] - c["t_ms"]) for e in kind("sfx") if e.get("role") == "whoosh" and "peak_ms" in e and "at_ms" in e]
        if not near or min(near) > 12:
            bad.append(_f("whoosh_align", f"no whoosh peak within 12 ms of the cut at {c['t_ms']} ms (closest {min(near) if near else 'none'} ms; basis ƯỚC)", "warn", c["t_ms"] / 1000, value=min(near) if near else None, limit=12))
    if hook.get("voice_onset_ms", rec["voice_onset_ms"]) > rec["voice_onset_max_ms"]:
        bad.append(_f("voice_onset", f"voice onset {hook['voice_onset_ms']} ms, recipe <= {rec['voice_onset_max_ms']} ms (15/17 measured hooks start at frame 0)", "warn", 0.0, value=hook["voice_onset_ms"], limit=rec["voice_onset_max_ms"]))
    return bad


def _static_runs(shots: list[dict], items: list[dict], full: dict, hook_s: float) -> list[tuple]:
    """`(shot, a, b, limit)` of every full-screen B-roll hold (shot with `broll`) longer than its limit with no background micro-move.
    Holds are split by background resets; `moves` are `{kind: push|pan|glint, t0, t1, rate_pct_s}` and only push >= 10 %/s, pan >= 4 %/s or a glint count."""
    mo, out = full["pacing"]["motion"], []
    cuts = [r["t"] for r in items if _is_bg(r, mo)]
    ok = lambda m: m["kind"] == "glint" or m.get("rate_pct_s", 0) >= (mo["min_push_rate_pct_s"] if m["kind"] == "push" else mo["min_pan_pct_crop_s"]) and m["kind"] in ("push", "pan")  # noqa: E731
    for s in (x for x in shots if x.get("broll")):
        pts = [s["start"]] + sorted(t for t in cuts if s["start"] < t < s["end"]) + [s["end"]]
        mv = sorted((m["t0"], m["t1"]) for m in s.get("moves", []) if ok(m))
        for a, b in zip(pts, pts[1:]):
            gap, at = 0.0, a
            for m0, m1 in mv + [(b, b)]:
                gap, at = max(gap, min(m0, b) - at), max(at, min(m1, b)) if m1 > a else at
            lim = mo["bg_static_run_s"][0 if a < hook_s else 1]
            if gap > lim + 1e-9:
                out.append((s, a, b, lim))
    return out


def plan_micro_moves(shots: list[dict], source_motion: dict | None = None, resets=(), preset: dict | None = None) -> list[dict]:
    """Remedy for every `bg_static_hold`: a push of about 14 %/s inside the +25 % full-screen B-roll cap, or a `split` (more bg resets) when the hold is too
    long for one push. A shot whose source clip already moves (`source_motion[id]` px/frame >= `source_flow_ok_px_frame`) needs none."""
    full = preset or _load()
    mo, caps, sm = full["pacing"]["motion"], full["camera_punch_caps"]["fullscreen_broll"] * 100, source_motion or {}
    pf = mo["proof_push"]
    proof = f"a 4 %/s push gives frame diff {pf['4_pct_s']}, a 14.5 %/s push {pf['14_5_pct_s']} [ĐO, engineer proof]"
    out = []
    for s, a, b, _ in _static_runs(shots, [_reset(r) for r in resets], full, full["hook_0_5s"]["window_ms"] / 1000):
        if sm.get(s["id"], 0.0) >= mo["source_flow_ok_px_frame"]:
            continue
        rate = min(14.0, caps / (b - a))
        if rate >= mo["min_push_rate_pct_s"]:
            out.append({"shot": s["id"], "kind": "push", "t0": a, "t1": b, "rate_pct_s": round(rate, 1), "proof": proof})
        else:
            n = math.ceil((b - a) * 14.0 / caps)
            out.append({"shot": s["id"], "kind": "split", "t0": a, "t1": b, "at": [round(a + (b - a) * k / n, 3) for k in range(1, n)], "then": "push 14 %/s per piece", "proof": proof})
    return out


def check_pacing(shots: list[dict], resets=(), duration: float | None = None, preset: dict | None = None) -> dict:
    """Pacing law over a shot list `[{id, start, end}]` (scenes from `plan_scenes` fit) plus explicit resets (seconds, or `{t, kind}` dicts).

    Shot boundaries are cuts. A reset is a cut, zoom step, flash or new text; resets within `merge_s` count once. Returns
    `{ok, hold_s, dead_hold_share, short_shot_share, windows: [{t0, t1, resets, min_resets, hold_s, dead_hold_share}], findings}`;
    `ok` = no error finding (warnings never fail). Rules: `max_hold` (> max_hold_s, error), `law_hold` (> law_hold_s, warn),
    `resets_per_5s`, `short_shots` (warn). `dead_hold_share` is a plan-level proxy (gaps without a reset longer than `dead_gap_s`).
    """
    full = preset or _load()
    pc, hook_s = full["pacing"], full["hook_0_5s"]["window_ms"] / 1000
    end = round(float(duration if duration is not None else max(s["end"] for s in shots)), 3)
    items = [_reset(r) for r in resets]
    cuts = [s["start"] for s in shots if 0 < s["start"] < end]
    marks = _merged([t for t in cuts + [r["t"] for r in items if r.get("kind", "zoom") in pc["reset_kinds"]] if 0 < t < end], pc["merge_s"])
    pts = [0.0] + marks + [end]
    spans = list(zip(pts, pts[1:]))
    owner = lambda t: next((s.get("id") for s in shots if s["start"] <= t < s["end"]), None)  # noqa: E731
    bad = []
    for a, b in spans:
        if b - a > pc["max_hold_s"] + 1e-9:
            bad.append(_f("max_hold", f"hold of {b - a:.2f} s at {a:.2f}-{b:.2f} s has no reset, max {pc['max_hold_s']} s", t0=a, t1=b, value=round(b - a, 3), limit=pc["max_hold_s"], shot=owner(a)))
        elif b - a > pc["law_hold_s"] + 1e-9:
            bad.append(_f("law_hold", f"hold of {b - a:.2f} s at {a:.2f}-{b:.2f} s, doctrine is <= {pc['law_hold_s']} s", "warn", a, b, round(b - a, 3), pc["law_hold_s"], shot=owner(a)))
    dead = lambda w0, w1: sum(max(0.0, min(b, w1) - max(a, w0)) for a, b in spans if b - a > pc["dead_gap_s"]) / (w1 - w0)  # noqa: E731
    wins, w0 = [], 0.0
    while w0 < end - 1e-9:
        w1 = min(w0 + pc["window_s"], end)
        if w1 - w0 >= pc["min_partial_window_s"] - 1e-9:
            n = sum(1 for t in marks if w0 <= t < w1)
            need = math.ceil((pc["min_resets_hook_window"] if w0 == 0 else pc["min_resets_other_window"]) * (w1 - w0) / pc["window_s"] - 1e-9)
            wins.append({"t0": round(w0, 3), "t1": round(w1, 3), "resets": n, "min_resets": need,
                         "hold_s": round(max(min(b, w1) - max(a, w0) for a, b in spans if a < w1 and b > w0), 3), "dead_hold_share": round(dead(w0, w1), 3)})
            if n < need:
                bad.append(_f("resets_per_5s", f"{n} visual resets in {w0:.0f}-{w1:.1f} s, need >= {need}", t0=round(w0, 3), t1=round(w1, 3), value=n, limit=need))
        w0 += pc["window_s"]
    bad += [_f("bg_static_hold", f"full-screen B-roll {s['id']} holds {b - a:.2f} s at {a:.2f}-{b:.2f} s without a background micro-move (push >= {pc['motion']['min_push_rate_pct_s']} %/s, pan >= {pc['motion']['min_pan_pct_crop_s']} % of the crop/s or a glint)", "error" if a < hook_s else "warn", a, b, round(b - a, 3), lim, shot=s["id"])
            for s, a, b, lim in _static_runs(shots, items, full, hook_s)]
    sw = pc["short_shot_window_s"]
    for k in range(int(end // sw) + (1 if end % sw >= sw / 2 else 0)):
        lo, hi = k * sw, min((k + 1) * sw, end)
        n = sum(1 for s in shots if lo <= s["start"] < hi and s["end"] - s["start"] < pc["short_shot_s"])
        need = math.ceil(pc["min_short_shots_per_10s"] * (hi - lo) / sw - 1e-9)
        if n < need:
            bad.append(_f("short_shots", f"{n} shots under {pc['short_shot_s']} s in {lo:.0f}-{hi:.1f} s, law asks >= {need}", "warn", lo, hi, n, need))
    short = [s for s in shots if s["end"] - s["start"] < pc["short_shot_s"]]
    return {"ok": not any(f["severity"] == "error" for f in bad), "hold_s": round(max(b - a for a, b in spans), 3), "dead_hold_share": round(dead(0.0, end), 3),
            "short_shot_share": round(len(short) / len(shots), 3) if shots else 0.0, "windows": wins, "findings": bad}


def check_source_reuse(shots: list[dict], preset: dict | None = None) -> list[dict]:
    """The same B-roll source seconds must never appear twice: shots `{id, source, src: [a, b]}` overlapping on one source are errors."""
    tol, bad = (preset or _load())["pacing"]["source_reuse_tol_s"], []
    for i, a in enumerate(shots):
        for b in shots[i + 1:]:
            ov = min(a["src"][1], b["src"][1]) - max(a["src"][0], b["src"][0])
            if a.get("source") == b.get("source") and ov > tol:
                bad.append(_f("source_reuse", f"{a['id']} and {b['id']} show the same {a['source']} seconds twice ({ov:.2f} s)", value=round(ov, 3), limit=tol, shot=a["id"], other=b["id"]))
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Look S scene planner (V21 pattern): words json + duration -> scenes.json")
    ap.add_argument("--words", required=True, help="words_tl json: probe dict doc ({'words': ...}) or bare [[word, t0, t1], ...]")
    ap.add_argument("--duration", required=True, type=float, help="timeline duration in seconds")
    ap.add_argument("--out", required=True, help="scenes.json to write")
    ap.add_argument("--look", default="S", choices=("S", "D"), help="S studio (default) or D plain screen-strip")
    args = ap.parse_args(argv)
    try:
        plan = plan_scenes(json.loads(Path(args.words).read_text(encoding="utf-8")), args.duration, args.look)
    except (OSError, ValueError, TypeError, IndexError) as exc:
        print(f"studio_recipe: {exc}", file=sys.stderr)
        return 2
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    st = plan["stats"]
    print(f"[STUDIO RECIPE v{VERSION}] look={plan['look']} scenes={len(plan['scenes'])} light={st['light_count']} ({st['light_share']:.0%}) ok={st['ok']} -> {args.out}")
    for v in st["violations"]:
        print(f"  violation: {v}", file=sys.stderr)
    return 0 if st["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
