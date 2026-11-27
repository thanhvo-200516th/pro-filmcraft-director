#!/usr/bin/env python3
"""
Tests for the 2026-11-26 user decisions on plate / FilmCraft text (skill 7.9.0):

  01 `motion_gate.entrance_word_spacing_em` (the ONE helper) and its JS mirror `entranceWordSpacingEm` agree on a grid (node)
  02 the gate model takes the guard: a blur-in that collides passes `check_word_gaps` on every frame once each frame carries the
     helper's extra spacing (`extra_gap_px`); a sliding neighbour (`shift_px`) is covered the same way
  03 web plates (Chrome probe, every frame 0..90 at 60 fps): every line-level blur / slide entrance (kt02, kt04, kt05, kt07, kt08,
     kt09, kt11 tilt) keeps the INK gap minus both neighbours' blur >= 0.25 em; the spacing is wider while blurred and back to one
     resting value once the blur is 0. Control: the same plates with the guard switched off collide
  04 FilmCraft: a blurred multi-word text clip carries tracking keys from the helper (gap >= 0.25 em on every frame, linear model),
     rests back as the blur reaches 0, one-word clips are untouched; control without the keys collides
  05 every blur-in preset of every presets/*.json file (enumerated: a `gaussian_blur` / `gaussian_blur_from` / keyframe `blur` /
     `nfc_guardrails.max_blur_px` entry, so a new unguarded blur preset fails) carries `entrance_word_spacing` equal to the helper
     and passes `check_word_gaps` at its reference size
  06 every template sample renders every text >= 64 px on the canvas (after plate_scale), every secondary text (CSS = the 70 px
     secondary size) at 66-74 px, and every text box inside the plate
  08 repair: long kt02 accent / long kt07 hero render (no hard-block raise); no kt plate (samples + long copy) has ink on its edge
     rows / columns at any entrance or hold frame (the plate grows to its content); a wrapped kt09 hero gets one laser per line
  07 `render_web_plates_batch` hard block: undersized CSS raises before Chrome starts; a text that only RENDERS small (a receding
     scale) raises after rendering; `decorative: true` only warns
  09 kt11 svg_arc long copy (31 / 44 / 60 chars): every glyph is drawn (no textPath overflows its path), >= 64 px, ink >= 40 px
     from every plate edge (glyph extents and rendered alpha), content centred, the plate does not balloon
  10 textPath overflow audit: a forced too-short arc (explicit arc_rx) raises TextPathOverflowError (hard block, decorative too)
  11 fit_kt_plate_heights measures real ink (an overflowing textPath no longer grows the plate 620 -> 1350) and caps the growth at
     the content height + margins + the centring tolerance
  12 PIL vietanh engine (fam01 baseline slide, fam04 crossover): every blurred multi-word line keeps ink gap - 2 sigma >= 0.25 em on
     every entrance frame (spied draw / blur calls) and rests at its natural spacing; control with the guard off collides
  13 EVERY `render_va_fam*` function (enumerated by inspect, every mode / colour variant, multi-word copy, frames 0..45 at 60 fps):
     each blurred multi-word line (spied PIL GaussianBlur / BoxBlur / MaxFilter and cv2 GaussianBlur / blur / boxFilter / stackBlur /
     dilate, followed through numpy; effective spread per side: Gaussian sigma, box k / 2, dilate r + 2 sigma) passes
     `check_word_gaps`; each blurring family has `word_gap_guard`, collides with it off, passes at rest and rests at one gap
  14 every va_fam preset maps 1:1 to an engine family; a family whose engine blurs text must carry `entrance_word_spacing` and
     declare a blur (or `engine_spread_px`) >= the engine's (so test 05 checks its values)
  15 Chrome probe of EVERY drawn text line ("*": not the guard's own list) of every template sample + the extra / long-copy prop sets,
     frames 0..239 (entrance, hold AND the applyCleanExit blur): ink gap - blur >= 0.25 em (rest too), no reflow, no textPath glyph
     dropped; page guard off -> the reported lines collide
  16 EVERY `render_*` of dviet_7706 (inspect): line-level blurs (style 1 ghost / hero / sub, style 4, style 6) keep the word gap,
     the ghost line resting at sigma 6 included; guard off collides
  17 export_dviet_bevel_lockup_png(allow_static_thumbnail=True): one gfx clip per word keeps the blur; the position spread keeps
     every adjacent pair >= 0.25 em on every frame and eases back to rest; no spread collides

Plain asserts with a `__main__` runner: `python3 tests/test_text_legibility_v79.py`. Tests 03, 06, 07 drive headless Chrome.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import motion_gate as mg  # noqa: E402
import web_plate_builder as wpb  # noqa: E402

KT09_LONG_COPY = {"kicker": "đừng tin lời đồn", "main_text": "đẹp tự nhiên không cần lọc", "accent_text": "giữ nguyên chi tiết làn da thật",
                  "pill_text": "sự thật", "jewel_accent": "emerald", "slash_at_s": 0.20}
GUARDED = {  # sample name -> the line ids that enter with a horizontal blur or a slide
    "kt02": ["kt02Hero"], "kt04": ["kt04Setup", "kt04Hero"], "kt05": ["kt05LeftClause_0", "kt05RightMain"],
    "kt05_wall": ["kt05LeftClause_0", "kt05RightMain"], "kt07": ["kt07Line"], "kt08": ["kt08MistCore"], "kt09": ["kt09Hero"],
    "kt11_tilt": ["kt11TiltHero"], "kt06": ["kt06Anchor", "kt06Swap0", "kt06Swap1"],
}
EXTRA = [  # more prop sets: light theme, longer lines, a two-line hero
    {"name": "kt02_light", "template": "kt02_feather_swash_overlap", "props": {"theme": "light", "main_text": "mình vừa làm xong", "accent_text": "Thật Nhanh"}, "ids": ["kt02Hero"]},
    {"name": "kt09_long", "template": "kt09_strike_myth_laser_2phase", "props": {"main_text": "đẹp tự nhiên không cần lọc"}, "ids": ["kt09Hero"]},
    {"name": "kt04_short", "template": "kt04_ghost_to_focus_stack", "props": {"setup_text": "ai cũng nghĩ", "main_text": "ánh sáng là đủ"}, "ids": ["kt04Setup", "kt04Hero"]},
    {"name": "kt07_long", "template": "kt07_telescoping_char_rollout", "props": {"main_text": "từng chữ một hiện ra"}, "ids": ["kt07Line"]},
    {"name": "kt11_tilt_b", "template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "tilted_chest", "main_text": "Giữ Trọn Cảm Xúc"}, "ids": ["kt11TiltHero"]},
    {"name": "kt09_long_copy", "template": "kt09_strike_myth_laser_2phase", "props": KT09_LONG_COPY, "ids": ["kt09Hero"]},
    {"name": "kt07_2line", "template": "kt07_telescoping_char_rollout", "props": {"main_text": "chạm đúng nhịp thở của làn da mỗi sáng"}, "ids": ["kt07Line", "kt07Line1"]},
]
TOL_PX = 0.02  # the probe rounds every px value to 0.01


def _samples() -> list[dict]:
    by = {s["name"]: s for s in wpb.TEXT_ACCEPTANCE_SAMPLES}
    return [dict(by[n], ids=ids) for n, ids in GUARDED.items()] + EXTRA


def _probe_jobs(samples: list[dict], td: str, frames: tuple[int, int] = (0, 90)) -> list[dict]:
    jobs = []
    for i, smp in enumerate(samples):
        j = {"template": smp["template"], "props": smp["props"], "out": f"{td}/p{i}.json", "mode": "probe", "fps": 60, "total_frames": 240,
             "probe_from": frames[0], "probe_to": frames[1], "plate_scale": smp.get("plate_scale", 1.0)}
        if smp.get("ids"):
            j["probe_ids"] = smp["ids"]
        for k in ("width", "height"):
            if k in smp:
                j[k] = smp[k]
        jobs.append(j)
    return jobs


def _violations(res: dict) -> list[tuple]:
    out = []
    for fr in res["wordGaps"]:
        for ln in fr["lines"]:
            w = ln["worst"]
            if w and w["effPx"] < w["needPx"] - TOL_PX:
                out.append((fr["frameIdx"], ln["id"], w["pair"], w["effPx"], w["needPx"]))
    return out


# ------------------------------------------------------------------------------------------------- (1) helper + JS mirror
def test_01_helper_and_js_mirror() -> None:
    f = 84.0
    assert mg.entrance_word_spacing_em(0, 1, f, 0.30) == 0.0, "no blur + a resting gap above the floor -> natural spacing"
    assert abs(mg.entrance_word_spacing_em(0, 1, f, mg.SPACE_EM) - 0.02) < 1e-9, "0.23 em space -> +0.02 em to reach 0.25 em"
    e = mg.entrance_word_spacing_em(10, 1.12, f, 0.25)
    assert abs(e - math.ceil((20 / (1.12 * f)) * 1e4) / 1e4) < 1e-9, e
    assert mg.entrance_word_spacing_em(0, 1, f, 0.25, shift_px=21) == 0.25
    assert mg.entrance_word_spacing_em(12, 1, f, 0.2) > mg.entrance_word_spacing_em(6, 1, f, 0.2) > mg.entrance_word_spacing_em(0, 1, f, 0.2)
    js_fn = re.search(r"(const __WORD_GAP_MIN_EM = __WORD_GAP_MIN_EM_VALUE__;\nfunction entranceWordSpacingEm\(.*?\n\})", wpb.COMMON_STUDIO_JS, re.S)
    assert js_fn, "entranceWordSpacingEm missing from COMMON_STUDIO_JS"
    grid = [(b, s, fp, nat, sh) for b in (0, 3.5, 7.5, 12, 16, 20) for s in (0.88, 1.0, 1.15) for fp in (64, 70, 103)
            for nat in (0.118, 0.228, 0.31) for sh in (0, 9.5)]
    src = js_fn.group(1).replace("__WORD_GAP_MIN_EM_VALUE__", str(mg.WORD_GAP_MIN_EM)) + \
        f"\nconsole.log(JSON.stringify({json.dumps(grid)}.map(a => entranceWordSpacingEm(...a))));"
    out = subprocess.run([wpb.resolve_node_binary(), "-e", src], capture_output=True, text=True, check=True).stdout
    js_vals = json.loads(out)
    py_vals = [mg.entrance_word_spacing_em(b, s, fp, nat, shift_px=sh) for b, s, fp, nat, sh in grid]
    assert all(abs(a - b) < 1e-9 for a, b in zip(js_vals, py_vals)), [(g, a, b) for g, a, b in zip(grid, js_vals, py_vals) if abs(a - b) >= 1e-9][:5]
    print(f"[PASS] 01 entrance_word_spacing_em: formula, rest = natural, JS mirror equal on {len(grid)} points")


# ------------------------------------------------------------------------------------------------- (2) gate model
def test_02_gate_model_takes_the_guard() -> None:
    f, nat = 84.0, 0.228
    keys = [{"t_ms": i * 1000 / 60, "opacity": min(1.0, 0.1 + i / 6), "blur_px": max(0.0, 10 * (1 - i / 8)), "scale": 1.12 - 0.12 * min(1, i / 8)}
            for i in range(13)]
    line = {"id": "E3", "font_px": f, "gap_px": nat * f, "entrance": keys}
    assert mg.check_word_gaps([line]), "the v4 K3 blur-in (sigma 10, 1.12x) must collide on the natural gap"
    guarded = [dict(k, extra_gap_px=mg.entrance_word_spacing_em(k["blur_px"], k["scale"], f, nat) * f) for k in keys]
    assert mg.check_word_gaps([dict(line, entrance=guarded)]) == [], mg.check_word_gaps([dict(line, entrance=guarded)])
    assert guarded[-1]["extra_gap_px"] == mg.entrance_word_spacing_em(0, 1.0, f, nat) * f, "rest = the 0.25 em floor only"
    slide = [{"t_ms": i * 1000 / 60, "opacity": min(1.0, i / 4), "shift_px": 32 * (1 - i / 10)} for i in range(11)]
    sl = {"id": "kt07", "font_px": 90.0, "gap_px": 0.26 * 90, "entrance": slide}
    assert mg.check_word_gaps([sl]), "a 32 px slide into the gap must collide"
    fixed = [dict(k, extra_gap_px=mg.entrance_word_spacing_em(0, 1, 90.0, 0.26, shift_px=k["shift_px"]) * 90) for k in slide]
    assert mg.check_word_gaps([dict(sl, entrance=fixed)]) == []
    print("[PASS] 02 check_word_gaps: K3 blur-in and a 32 px slide collide; per-frame helper spacing (extra_gap_px) passes")


# ------------------------------------------------------------------------------------------------- (3) web plates in Chrome
def test_03_web_plate_entrances_keep_word_gap() -> None:
    samples = _samples()
    with tempfile.TemporaryDirectory() as td:
        res = wpb.render_web_plates_batch(_probe_jobs(samples, td), concurrency=4, strip_meta=False, quiet=True)
    bad, seen = [], 0
    for smp, r in zip(samples, res):
        bad += [(smp["name"],) + v for v in _violations(r)]
        for lid in smp["ids"]:
            rows = [(fr["frameIdx"], ln) for fr in r["wordGaps"] for ln in fr["lines"] if ln["id"] == lid and ln["worst"]]
            assert rows, (smp["name"], lid, "line never visible / never measured")
            seen += len(rows)
            n_rows = {ln["rows"] for _, ln in rows}
            assert len(n_rows) == 1, (smp["name"], lid, "the widened entrance must not reflow the line", sorted(n_rows))
            if lid.startswith(("kt07Line", "kt06")):  # kt07 slides (no blur); the kt06 reel blur is vertical only (SVG "0 y")
                continue
            rest = [float(ln["wordSpacing"].rstrip("px")) for _, ln in rows if ln["worst"]["blurPx"] == 0]
            blurred = [float(ln["wordSpacing"].rstrip("px")) for _, ln in rows if ln["worst"]["blurPx"] > 0.5]
            assert blurred, (smp["name"], lid, "no blurred frame was probed")
            if rest:
                # one resting value; kt04 still settles its letter-spacing (0.08 -> -0.038 em) for a frame after the blur cut-off
                assert max(rest) - min(rest) < 0.25, (smp["name"], lid, "resting spacing must be one value", sorted(set(rest)))
                assert min(blurred) > max(rest) + 1e-6, (smp["name"], lid, "blurred frames must be wider than rest", min(blurred), max(rest))
    assert not bad, bad[:12]
    # control: the guard switched off (no resting gap measured -> no data-ws-nat0 / kt07 width keys) collides on every template
    real = wpb._mg

    class _Off:
        SPACE_EM = mg.SPACE_EM
        entrance_word_spacing_em = staticmethod(mg.entrance_word_spacing_em)

        @staticmethod
        def natural_word_gap_em(*_a, **_k):
            return None
    wpb._mg, wpb.PAGE_LINE_GUARD = (lambda: _Off), False
    try:
        with tempfile.TemporaryDirectory() as td:
            ctl = wpb.render_web_plates_batch(_probe_jobs(samples, td), concurrency=4, strip_meta=False, quiet=True)
    finally:
        wpb._mg, wpb.PAGE_LINE_GUARD = real, True
    unguarded = {smp["name"] for smp, r in zip(samples, ctl) if _violations(r)}
    assert unguarded == {s["name"] for s in samples}, ("without the guard every sample must collide", {s["name"] for s in samples} - unguarded)
    print(f"[PASS] 03 Chrome probe: {len(samples)} plates, {seen} visible line-frames keep ink gap - blur >= 0.25 em; "
          "rest spacing restored at blur 0; guard off -> all collide")


# ------------------------------------------------------------------------------------------------- (4) FilmCraft keys
def _clip_lines(clip: dict, fps: int = 60, with_tracking: bool = True) -> list[dict]:
    import typography_composer as tc
    nat = mg.natural_word_gap_em(clip["text"], tc._resolve_typo_font_path(clip["font"], clip["style"]), 0.0)
    blur = next(fx["params"]["blurriness"] for fx in clip["effects"] if fx["effect"] == "gaussian_blur")
    n = int(round(clip["dur"] * fps))
    keys = []
    for i in range(n + 1):
        t = i / fps
        trk = tc._kf_value(clip.get("tracking"), t, 0.0) if with_tracking else 0.0
        keys.append({"t_ms": t * 1000, "opacity": tc._kf_value(clip["opacity"], t, 100.0) / 100.0, "blur_px": tc._kf_value(blur, t),
                     "scale": min(1.0, tc._kf_value(clip["motion"]["scale"], t, 100.0) / 100.0),
                     "extra_gap_px": 2 * trk / 1000 * clip["size"]})
    return [{"id": clip["name"], "font_px": clip["size"], "gap_px": nat * clip["size"], "entrance": keys}]


def test_04_filmcraft_blur_entrance_tracking() -> None:
    import typography_composer as tc
    clips = [tc.dviet_soft_up("chạm đúng nhịp thở", 1.0, 1.2), tc.dviet_soft_up("hai từ", 1.0, 0.25),
             tc.dviet_soft_up("giữ trọn ánh sáng", 2.0, 1.0, pos=(540, 1400))]
    for c in clips:
        assert isinstance(c.get("tracking"), list) and c["tracking"], c.get("tracking")
        assert mg.check_word_gaps(_clip_lines(c)) == [], (c["text"], mg.check_word_gaps(_clip_lines(c))[:1])
        assert mg.check_word_gaps(_clip_lines(c, with_tracking=False)), (c["text"], "control without the keys must collide")
        blur = next(fx["params"]["blurriness"] for fx in c["effects"] if fx["effect"] == "gaussian_blur")
        zero_t = [k[0] for k in blur if float(k[1]) == 0.0]
        rest = {round(tc._kf_value(c["tracking"], t), 2) for t in zero_t}
        assert len(rest) == 1 and all(tc._kf_value(c["tracking"], k[0]) > min(rest) for k in blur if float(k[1]) > 0), (rest, c["tracking"])
        assert c["size"] >= tc.TEXT_FLOOR_PX
    one = tc.dviet_soft_up("chạm", 1.0, 1.2)
    assert "tracking" not in one, "a one-word clip has no gap to protect"
    bridged = tc.apply_persistent_text_bridge(clips[0], next_cut_s=1.5, fps=60)
    assert mg.check_word_gaps(_clip_lines(bridged)) == [], "the persistent bridge re-keys the blur and the tracking with it"
    print("[PASS] 04 FilmCraft: blurred multi-word clips get helper tracking keys (gap >= 0.25 em every frame, rest at blur 0), "
          "one word untouched, bridge re-keyed")


# ------------------------------------------------------------------------------------------------- (5) presets
def _blur_spec(p: dict) -> tuple[float, float, int, int, float] | None:
    """(start blur sigma, start scale, entrance frames, fps, resting sigma) of a text blur-in preset, None when `p` blurs no text.
    The resting sigma is the last `gaussian_blur` key (> 0 for a halo that stays, va_fam05), else 0."""
    fps = int(p.get("base_fps", 30))
    sc = p.get("scale")
    s0 = sc[0] / 100 if isinstance(sc, list) and sc and isinstance(sc[0], (int, float)) else 1.0
    kf = p.get("keyframes")
    if isinstance(p.get("gaussian_blur"), list) and p["gaussian_blur"] and float(p["gaussian_blur"][0]) > 0:
        return float(p["gaussian_blur"][0]), s0, int(p["frames"]), fps, float(p["gaussian_blur"][-1])
    if float(p.get("gaussian_blur_from") or 0) > 0:
        return float(p["gaussian_blur_from"]), s0, int(round(float(p["dur_s"]) * fps)), fps, 0.0
    if isinstance(kf, list) and kf and isinstance(kf[0], dict) and float(kf[0].get("blur") or 0) > 0:
        return float(kf[0]["blur"]), s0, int(kf[-1]["frame"]), fps, float(kf[-1].get("blur") or 0)
    mb = (p.get("nfc_guardrails") or {}).get("max_blur_px") if isinstance(p.get("nfc_guardrails"), dict) else None
    if mb and float(mb) > 0:  # a blur entrance documented only by its ceiling: guard the worst case
        return float(mb), s0, int(p["frames"]), fps, 0.0
    return None


def _blur_presets() -> list[tuple[str, str, dict]]:
    """Every text blur-in preset of every presets/*.json file: [(file, key, preset)]."""
    out = []

    def walk(rel, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict) and _blur_spec(v) is not None:
                    out.append((rel, k, v))
                walk(rel, v)
        elif isinstance(obj, list):
            for v in obj:
                walk(rel, v)
    for path in sorted((SKILL_ROOT / "presets").glob("*.json")):
        walk(path.name, json.loads(path.read_text(encoding="utf-8")))
    return out


def test_05_blur_in_presets_carry_word_spacing() -> None:
    found = _blur_presets()
    names = {k for _f, k, _p in found}
    must = {"gaussian_deblur_in", "editorial_blur_in", "blur_in", "slide_up_blur", "slow_opacity_bloom", "va_fam01_baseline_mask_slide",
            "va_fam04_vertical_passthrough_crossover", "xuanart_blur_amber_glow", "va_fam02_diagonal_rotation_whip",
            "va_fam09_error_strikethrough_and_golden_bokeh"}
    assert must <= names, ("the enumeration must find every known blur preset", must - names)
    bad = []
    for rel, key, p in found:
        ews = p.get("entrance_word_spacing")
        if not isinstance(ews, dict):
            bad.append((rel, key, "no entrance_word_spacing"))
            continue
        b0, s0, frames, fps, b1 = _blur_spec(p)
        f, nat = ews["reference_font_px"], ews["natural_gap_em"]
        want = [mg.entrance_word_spacing_em(b0, min(s0, 1.0), f, nat), mg.entrance_word_spacing_em(b1, 1, f, nat)]
        if ews["word_spacing_em"] != want or ews.get("filmcraft_tracking_per_mille") != [round(500 * v, 4) for v in want]:
            bad.append((rel, key, "word_spacing_em / tracking differ from the helper", ews["word_spacing_em"], want))
            continue
        if "engine_spread_px" in ews:  # a PIL twin whose text spread is not one Gaussian (va_fam09 bokeh: dilate + 2 sigma)
            ew = [mg.entrance_word_spacing_em(float(ews["engine_spread_px"]), 1, f, nat), mg.entrance_word_spacing_em(0, 1, f, nat)]
            if ews.get("engine_word_spacing_em") != ew:
                bad.append((rel, key, "engine_word_spacing_em differs from the helper", ews.get("engine_word_spacing_em"), ew))
                continue
        keys = [{"t_ms": i * 1000 / fps, "opacity": 1.0, "blur_px": b0 + (b1 - b0) * i / frames, "scale": min(1.0, s0 + (1 - s0) * i / frames),
                 "extra_gap_px": f * (want[0] + (want[1] - want[0]) * i / frames)} for i in range(frames + 1)]
        line = {"id": key, "font_px": f, "gap_px": nat * f, "entrance": keys}
        if mg.check_word_gaps([line]):
            bad.append((rel, key, mg.check_word_gaps([line])))
        assert mg.check_word_gaps([dict(line, entrance=[dict(k, extra_gap_px=0) for k in keys])]), f"{key}: control must collide"
    assert not bad, bad
    print(f"[PASS] 05 {len(found)} blur-in presets enumerated from presets/*.json ({', '.join(sorted(names))}) carry helper word spacing")


# ------------------------------------------------------------------------------------------------- (6) sizes + bounds
def test_06_every_template_text_band_and_bounds() -> None:
    samples = list(wpb.TEXT_ACCEPTANCE_SAMPLES)
    assert {s["template"] for s in samples} == set(wpb.TEMPLATE_DEFAULTS), set(wpb.TEMPLATE_DEFAULTS) - {s["template"] for s in samples}
    with tempfile.TemporaryDirectory() as td:
        res = wpb.render_web_plates_batch(_probe_jobs([dict(s, ids=None) for s in samples], td, (0, 0)), concurrency=4,
                                          strip_meta=False, quiet=True)
    small, band, out, n_sec = [], [], [], 0
    for smp, r in zip(samples, res):
        ps = smp.get("plate_scale", 1.0)
        sec_css = wpb.secondary_text_px(ps)
        texts = r["textSizes"]
        assert texts, smp["name"]
        for t in texts:
            eff = t["effPx"] * ps
            if eff < wpb.MIN_OVERLAY_FONT_PX:
                small.append((smp["name"], t["label"], eff, t["text"]))
            if abs(t["fontPx"] - sec_css) < 0.01:
                n_sec += 1
                if not 66.0 <= eff <= 74.0:
                    band.append((smp["name"], t["label"], eff, t["text"]))
            b, v = t["box"], t["view"]
            if b and (b[0] < 0 or b[1] < 0 or b[2] > v[0] or b[3] > v[1]):
                out.append((smp["name"], t["label"], b, v))
    assert not small, small
    assert not band, band
    assert not out, out
    assert n_sec >= 60, n_sec
    print(f"[PASS] 06 {len(samples)} samples / {len(wpb.TEMPLATE_DEFAULTS)} templates: every text >= 64 px, {n_sec} secondary texts "
          "at 66-74 px, every text box inside its plate")


# ------------------------------------------------------------------------------------------------- (7) hard block
def test_07_render_batch_hard_block() -> None:
    calls = []
    real_run = wpb.subprocess.run

    def spy(cmd, **kw):
        calls.append(cmd)
        return real_run(cmd, **kw)
    wpb.subprocess.run = spy
    try:
        with tempfile.TemporaryDirectory() as td:
            small_css = {"template": "kt01_kiss_editorial_2line", "props": {"demo": True, "kicker": "nhỏ", "kicker_size": 30},
                         "out": f"{td}/a.png", "mode": "still"}
            try:
                wpb.render_web_plates_batch([small_css], quiet=True, strip_meta=False)
                raise AssertionError("30 px CSS text must raise")
            except wpb.UndersizedTextError as exc:
                assert "a.png" in str(exc) and exc.audits and exc.audits[0]["undersized"], exc
            assert not calls, "the CSS hard block fires before Chrome starts"
            receded = {"template": "kt04_ghost_to_focus_stack", "props": {"setup_text": "tưởng chỉ cần", "main_text": "chiều sâu", "setup_size": 66},
                       "out": f"{td}/b.png", "mode": "still"}
            try:
                wpb.render_web_plates_batch([receded], quiet=True, strip_meta=False)
                raise AssertionError("a 66 px setup line receding to 0.94x renders at ~62 px and must raise")
            except wpb.UndersizedTextError as exc:
                ru = exc.audits[0]["rendered_undersized"]
                assert ru and ru[0][0] == "#kt04Setup" and ru[0][1] < 64 and not exc.audits[0]["undersized"], exc.audits
            assert calls, "the rendered audit needs Chrome"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                res = wpb.render_web_plates_batch([dict(small_css, decorative=True, out=f"{td}/c.png")], quiet=True, strip_meta=False)
            assert res[0]["text_audit"]["severity"] == "warn" and Path(f"{td}/c.png").is_file(), res[0]["text_audit"]
            assert any("c.png" in str(w.message) for w in caught)
            ok = wpb.render_web_plates_batch([{"template": "kt02_feather_swash_overlap", "props": {"demo": True, "kicker": "bí quyết", "pill_text": "mới"},
                                               "out": f"{td}/d.png", "mode": "still"}], quiet=True, strip_meta=False)
            assert ok[0]["text_audit"]["severity"] == "ok" and ok[0]["text_audit"]["rendered_undersized"] == [], ok[0]["text_audit"]
    finally:
        wpb.subprocess.run = real_run
    print("[PASS] 07 hard block: CSS 30 px raises before Chrome, a 62 px rendered setup line raises after, decorative warns, defaults pass")


# ------------------------------------------------------------------------------------------------- (8) repair regressions
EDGE_EXTRA = [  # long copy that used to clip / overflow / raise
    {"name": "kt09_long_copy", "template": "kt09_strike_myth_laser_2phase", "props": KT09_LONG_COPY},
    {"name": "kt02_light_4w", "template": "kt02_feather_swash_overlap", "props": {"theme": "light", "main_text": "mình vừa làm xong", "accent_text": "Thật Nhanh Nhưng Chuẩn"}},
    {"name": "kt02_long_accent", "template": "kt02_feather_swash_overlap", "props": {"main_text": "độ sâu ánh sáng", "accent_text": "một câu phụ khá dài để kiểm tra kích thước chữ tự co lại"}},
    {"name": "kt07_long", "template": "kt07_telescoping_char_rollout", "props": {"main_text": "chạm đúng nhịp thở của làn da mỗi sáng"}},
    {"name": "kt11_tilt_long", "template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "tilted_chest", "main_text": "Giữ Trọn Cảm Xúc", "pill_text": "nhịp"}},
]
EDGE_FRAMES = (9, 14, 30, 70, None)  # of a 240-frame clip; None = the settled still
EDGE_ALPHA = 60


def test_08_repair_long_copy_and_plate_edges() -> None:
    from PIL import Image
    import numpy as np
    for tf in (120, 300):  # a kt07 hero AT the 64 px floor measures >= 64 px (was 63.9: the probe divided by rounded offsetWidth)
        for props in ({"main_text": "chạm đúng nhịp thở", "main_size": 64}, {"main_text": "chạm đúng nhịp thở của làn da mỗi sáng"}):
            r = wpb.probe_word_gaps("kt07_telescoping_char_rollout", props, total_frames=tf, frames=(0, -1))
            sc = {t["scale"] for t in r["textSizes"] if t["label"] == ".kt07-char"}
            assert min(t["effPx"] for t in r["textSizes"]) >= wpb.MIN_OVERLAY_FONT_PX and len(sc) == 1, (props, sorted(sc))
    r = wpb.probe_word_gaps("kt02_feather_swash_overlap", EDGE_EXTRA[2]["props"], frames=(0, -1))
    acc = [t["effPx"] for t in r["textSizes"] if t["label"].startswith(".swash-hybrid")]
    assert acc and min(acc) >= 66.0, ("kt02 accent follows the secondary size rule", acc)
    html = wpb.build_template_html("kt09_strike_myth_laser_2phase", KT09_LONG_COPY)
    hero = re.search(r'id="kt09Hero"[^>]*>(.*?)</div>', html, re.S).group(1)
    n_lines = hero.count("<br>") + 1
    assert n_lines >= 2 and html.count('class="kt09-laser-svg"') == n_lines, ("one laser per hero line", n_lines, html.count('class="kt09-laser-svg"'))
    samples = [s for s in wpb.TEXT_ACCEPTANCE_SAMPLES if s["template"] in wpb.KINETIC_TYPO_TEMPLATES] + EDGE_EXTRA
    with tempfile.TemporaryDirectory() as td:
        jobs = []
        for smp in samples:
            for f in EDGE_FRAMES:
                j = {"template": smp["template"], "props": smp["props"], "out": f"{td}/{smp['name']}__{f}.png", "mode": "still", "fps": 60}
                if f is not None:
                    j.update(total_frames=240, frame_idx=f)
                jobs.append(dict(j, name=smp["name"], frame=f))
        res = wpb.render_web_plates_batch(jobs, concurrency=4, strip_meta=False, quiet=True)
        bad = []
        for j in jobs:
            a = np.asarray(Image.open(j["out"]).convert("RGBA"))[:, :, 3] > EDGE_ALPHA
            edge = {"top": int(a[0].sum()), "bottom": int(a[-1].sum()), "left": int(a[:, 0].sum()), "right": int(a[:, -1].sum())}
            if any(edge.values()):
                bad.append((j["name"], j["frame"], edge))
        assert not bad, bad
        rows = {j["name"]: r.get("plate_height") for j, r in zip(jobs, res)}
        assert rows["kt09_long_copy"] > wpb.default_plate_height("kt09_strike_myth_laser_2phase", KT09_LONG_COPY), rows["kt09_long_copy"]
    print(f"[PASS] 08 long kt02 accent / kt07 hero render; {len(samples)} kt plates x {len(EDGE_FRAMES)} frames: no ink on any plate edge; "
          f"kt09 wrapped hero -> {n_lines} lines, {n_lines} lasers, plate grown to its content")



# ------------------------------------------------------------------------------------------------- (9) kt11 arc long copy
KT11_ARC_COPY = {  # chars -> copy (the 44-char line used to lose its first / last words off the arc while every audit passed)
    31: "ánh sáng điện ảnh cho làn da ấm",
    44: "vòng sáng điện ảnh tự nhiên cho mọi khuôn mặt",
    60: "vòng sáng điện ảnh tự nhiên cho mọi khuôn mặt và mọi vùng da",
}
ARC_EDGE_ALPHA = 60


def _arc_jobs(td: str, mode: str = "still", **extra) -> list[dict]:
    jobs = []
    for n, txt in KT11_ARC_COPY.items():
        j = {"template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "svg_arc", "main_text": txt, "jewel_accent": "gold", **extra},
             "out": f"{td}/arc{n}.png", "mode": mode, "fps": 60}
        jobs.append(j)
    return jobs


def test_09_kt11_arc_long_copy_fits() -> None:
    from PIL import Image
    import numpy as np
    m = wpb.KT_PLATE_MARGIN_PX
    for n, txt in KT11_ARC_COPY.items():
        assert abs(len(txt) - n) <= 1, (n, len(txt))  # the 44 label is the reported repro line verbatim (45 code points)
    for extra in ({}, {"accent_text": "Tỏa Sáng"}):
        with tempfile.TemporaryDirectory() as td:
            jobs = _arc_jobs(td, **extra)
            res = wpb.render_web_plates_batch(jobs, concurrency=3, strip_meta=False, quiet=True)
            probes = wpb.render_web_plates_batch([dict(j, out=j["out"] + ".json", mode="probe", total_frames=240, probe_from=0, probe_to=0,
                                                       content_box_frames=list(wpb.KT_FIT_FRAMES)) for j in jobs],
                                                 concurrency=3, strip_meta=False, quiet=True)
            for (n, txt), j, r, pr in zip(KT11_ARC_COPY.items(), jobs, res, probes):
                w, h = r["plate_width"], r["plate_height"]
                tps = r["textPaths"]
                assert tps, (n, "the arc mode keeps a textPath arc for this length")
                assert all(not t["overflow"] and t["rendered"] == t["chars"] for t in tps), (n, tps)
                assert " ".join(t["text"] for t in tps) == txt, (n, "every word on an arc, in order", [t["text"] for t in tps])
                assert min(t["effPx"] for t in r["textSizes"]) >= wpb.MIN_OVERLAY_FONT_PX, (n, r["textSizes"])
                for t in tps:
                    b = t["inkBox"]
                    assert b[0] >= m and b[1] >= m and b[2] <= w - m and b[3] <= h - m, (n, "glyph ink >= 40 px from the plate edges", b, w, h)
                a = np.asarray(Image.open(j["out"]).convert("RGBA"))[:, :, 3] > ARC_EDGE_ALPHA
                band = {"top": int(a[:m].sum()), "bottom": int(a[-m:].sum()), "left": int(a[:, :m].sum()), "right": int(a[:, -m:].sum())}
                assert not any(band.values()), (n, extra, "rendered ink inside the 40 px plate margin", band)
                ys, xs = np.nonzero(a)
                cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
                assert abs(cy - h / 2) <= 12 and abs(cx - w / 2) <= 12, (n, extra, "content centred", cx, cy, w, h)
                # the plate may grow to its planned content (v7.9.0 repair: the resting word gap >= 0.25 em lengthens the arc copy, the
                # 60-char line + accent plans 574 px of content), never past it (it used to balloon 620 -> 1350)
                plan = wpb.kt11_arc_plan(txt, max(wpb.secondary_text_px(j["props"]), min(84, int(760 / max(9.0, len(txt) * 0.54)))), w,
                                         620, sub_px=wpb.secondary_text_px(j["props"]) if extra else 0)
                cap = max(wpb.default_plate_height("kt11_cranial_svg_arc_or_tilt", j["props"]) + 80,
                          math.ceil(plan["content_h"] * wpb.KT11_ARC_HOLD_SCALE) + 2 * m + 2 * wpb.KT_FIT_CENTRE_TOL_PX)  # hold creep
                assert h <= cap, (n, "plate must not balloon past its content", h, cap)
                box = pr["contentBox"]  # every entrance + hold frame to 3 s (the hold creep scales the ink about the centre)
                tol = 24 if extra else 12  # the accent's line box runs ~0.6 em below its glyphs: the visible ink (alpha, above) is centred
                assert abs((box[1] + box[3]) / 2 - h / 2) <= tol, (n, "probe content box centred", box, h)
                assert box[0] >= m and box[2] <= w - m and box[1] >= m - 0.5 and box[3] <= h - m + 0.5, (n, extra, "hold frames inside the margin", box)
    print(f"[PASS] 09 kt11 svg_arc {sorted(KT11_ARC_COPY)} chars (with / without accent): every glyph on its arc, >= 64 px, ink >= 40 px "
          "from the edges, content centred, plate not ballooned")


# ------------------------------------------------------------------------------------------------- (10) textPath overflow audit
def test_10_textpath_overflow_hard_block() -> None:
    forced = {"mode": "svg_arc", "main_text": KT11_ARC_COPY[44], "arc_rx": 300, "arc_ry": 120, "jewel_accent": "gold"}
    with tempfile.TemporaryDirectory() as td:
        for extra in ({}, {"decorative": True}):
            try:
                wpb.render_web_plates_batch([{"template": "kt11_cranial_svg_arc_or_tilt", "props": forced, "out": f"{td}/f.png",
                                              "mode": "still", **extra}], quiet=True, strip_meta=False)
                raise AssertionError(f"a 44-char line on a 300 px arc drops glyphs and must raise {extra}")
            except wpb.TextPathOverflowError as exc:
                ov = exc.audits[0]["textpath_overflow"]
                assert ov and ov[0]["rendered"] < ov[0]["chars"] and ov[0]["textLen"] > ov[0]["pathLen"], exc.audits
                assert "f.png" in str(exc)
        r = wpb.probe_word_gaps("kt11_cranial_svg_arc_or_tilt", {"mode": "svg_arc", "main_text": KT11_ARC_COPY[44]}, frames=(0, 0))
        assert r["textPaths"] and not any(t["overflow"] for t in r["textPaths"]), r["textPaths"]
    print("[PASS] 10 textPath audit: a forced 300 px arc under 44 chars raises TextPathOverflowError (decorative too); the fitted arc passes")


# ------------------------------------------------------------------------------------------------- (11) plate fit
def test_11_fit_kt_plate_heights_real_ink_and_cap() -> None:
    forced = {"mode": "svg_arc", "main_text": KT11_ARC_COPY[44], "arc_rx": 300, "arc_ry": 120, "jewel_accent": "gold"}
    with tempfile.TemporaryDirectory() as td:
        h = wpb.fit_kt_plate_heights([("kt11_cranial_svg_arc_or_tilt", forced, 1080, 620)], Path(td))[0]
    assert h <= 700, ("an overflowing textPath must not grow the plate (was 620 -> 1350)", h)
    real = wpb._run_engine_batch
    calls = []

    def fake(engine_jobs, tmp_root, **kw):  # content 400 px tall but 120 px below centre on every pass
        calls.append([j["height"] for j in engine_jobs])
        return [{"contentBox": [100.0, j["height"] / 2 - 80, 980.0, j["height"] / 2 + 320]} for j in engine_jobs]
    wpb._run_engine_batch = fake
    try:
        with tempfile.TemporaryDirectory() as td, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            h2 = wpb.fit_kt_plate_heights([("kt09_strike_myth_laser_2phase", {"main_text": "đẹp tự nhiên"}, 1080, 564)], Path(td), max_passes=3)[0]
    finally:
        wpb._run_engine_batch = real
    cap = 400 + 2 * wpb.KT_PLATE_MARGIN_PX + 2 * wpb.KT_FIT_CENTRE_TOL_PX
    assert h2 <= max(564, cap), ("growth is capped at content + margins + centring tolerance", h2, cap, calls)
    assert any("centre" in str(w.message) for w in caught), [str(w.message) for w in caught]
    print(f"[PASS] 11 fit_kt_plate_heights: overflowing arc measured by drawn glyphs ({h} px, was 1350); off-centre content capped at "
          f"{h2} px with a centring warning")


# ------------------------------------------------------------------------------------------------- (12) PIL vietanh engine
def _cv2_spread(name: str, a: tuple, k: dict) -> tuple[str, float]:
    """(kind, px) of one spied cv2 call on a text array: ("g", sigma) for GaussianBlur, ("box", horizontal reach per side) for blur /
    boxFilter / stackBlur, ("dil", horizontal radius x iterations) for dilate."""
    def ksize(v):
        return (int(v), int(v)) if isinstance(v, (int, float)) else (int(v[0]), int(v[1]))
    if name == "GaussianBlur":
        kx = ksize(k.get("ksize", a[1] if len(a) > 1 else 0))[0]
        sig = float(k.get("sigmaX", a[2] if len(a) > 2 else 0.0))
        return "g", sig if sig > 0 else 0.3 * ((kx - 1) * 0.5 - 1) + 0.8  # OpenCV's sigma for a 0 sigma
    if name in ("blur", "stackBlur"):
        return "box", ksize(k.get("ksize", a[1] if len(a) > 1 else 1))[0] / 2.0
    if name == "boxFilter":
        return "box", ksize(k.get("ksize", a[2] if len(a) > 2 else 1))[0] / 2.0
    kern = k.get("kernel", a[1] if len(a) > 1 else None)
    r = (kern.shape[1] - 1) / 2.0 if kern is not None and hasattr(kern, "shape") else 1.0
    return "dil", r * int(k.get("iterations", a[3] if len(a) > 3 else 1) or 1)


def _spy_pil_lines(render, guard: bool) -> list[dict]:
    """Run `render(guard)` with ImageDraw.text, Image.filter (GaussianBlur / BoxBlur / MaxFilter) and cv2 GaussianBlur / blur /
    boxFilter / stackBlur / dilate spied: every multi-word line drawn on a layer -> {font_px, gap_px (narrowest adjacent-word INK gap as
    drawn), blur_px (the EFFECTIVE spread per side of every blur on that same layer, 0 if none)}.
    The layer is followed through numpy (`np.array(layer)` -> cv2 ops / warps -> `Image.fromarray`) and through `filter` results, so a
    blur on a warped copy (fam02) or on the drawn mask (fam09 bokeh) counts as that layer's. Spread per side: Gaussians add in
    quadrature (sigma, the gate model), box blurs add k / 2, a dilate adds its radius - and once a lineage is dilated its Gaussians
    count 2 sigma (dilate + blur + gain = a bokeh whose visible edge sits ~2 sigma out). Only calls made BY a render function
    (its own body or a nested helper, `co_qualname`) count: a glow helper blurs a bloom copy, not the text ink. Every spied image is
    kept alive for the run so no id is reused."""
    import cv2
    from PIL import Image, ImageDraw, ImageFilter
    draws, spread, root, keep, last = [], {}, {}, [], [None]
    real_text, real_filter = ImageDraw.ImageDraw.text, Image.Image.filter
    real_ai, real_fromarray = Image.Image.__array_interface__, Image.fromarray
    cv2_names = ("GaussianBlur", "blur", "boxFilter", "stackBlur", "dilate")
    real_cv2 = {n: getattr(cv2, n) for n in cv2_names if hasattr(cv2, n)}

    def rid(core):
        return root.get(id(core), id(core))

    def by_render(depth: int = 2) -> bool:
        code = sys._getframe(depth).f_code
        return getattr(code, "co_qualname", code.co_name).split(".")[0].startswith("render_")

    def add(r, kind, px):
        d = spread.setdefault(r, {"g": 0.0, "box": 0.0, "dil": 0.0})
        d[kind] = math.hypot(d[kind], px) if kind == "g" else d[kind] + px

    def text(self, xy, txt, *a, **k):
        font = k.get("font") or (a[1] if len(a) > 1 else None)
        keep.append(self.im)
        draws.append((rid(self.im), float(xy[0]), float(xy[1]), str(txt), font))
        return real_text(self, xy, txt, *a, **k)

    def filt(self, f):
        res = real_filter(self, f)
        r = rid(self.im)
        keep.extend((self.im, res.im))
        root[id(res.im)] = r
        if by_render():
            if isinstance(f, ImageFilter.GaussianBlur):
                rad = f.radius
                add(r, "g", float(max(rad) if isinstance(rad, (tuple, list)) else rad))
            elif isinstance(f, ImageFilter.BoxBlur):
                rad = f.radius
                add(r, "box", float(max(rad) if isinstance(rad, (tuple, list)) else rad))
            elif isinstance(f, ImageFilter.MaxFilter):
                add(r, "dil", (f.size - 1) / 2.0)
        return res

    def cv2_spy(name):
        fn = real_cv2[name]

        def wrapped(*a, **k):
            if last[0] is not None and by_render():
                add(last[0], *_cv2_spread(name, a, k))
            return fn(*a, **k)
        return wrapped

    def array_iface(self):
        keep.append(self.im)
        last[0] = rid(self.im)
        return real_ai.fget(self)

    def fromarray(*a, **k):
        res = real_fromarray(*a, **k)
        if last[0] is not None:
            keep.append(res.im)
            root[id(res.im)] = last[0]
        return res
    ImageDraw.ImageDraw.text, Image.Image.filter = text, filt
    Image.Image.__array_interface__, Image.fromarray = property(array_iface), fromarray
    for n in real_cv2:
        setattr(cv2, n, cv2_spy(n))
    try:
        render(guard)
    finally:
        ImageDraw.ImageDraw.text, Image.Image.filter = real_text, real_filter
        Image.Image.__array_interface__, Image.fromarray = real_ai, real_fromarray
        for n, fn in real_cv2.items():
            setattr(cv2, n, fn)

    def eff(r):
        d = spread.get(r)
        return 0.0 if not d else d["dil"] + d["box"] + (2.0 if d["dil"] > 0 else 1.0) * d["g"]
    hi: dict = {}

    def ink(font, wd):  # sub-pixel ink extents: the outline at 8x / 8 (getbbox at the drawn size rounds to whole px)
        if not getattr(font, "path", None):
            return font.getbbox(wd)[0], font.getbbox(wd)[2]
        k = (font.path, font.size)
        if k not in hi:
            hi[k] = font.font_variant(size=int(font.size) * 8)
        b = hi[k].getbbox(wd)
        return b[0] / 8.0, b[2] / 8.0
    by_layer: dict = {}
    for lid, x, y, txt, font in draws:
        by_layer.setdefault((lid, round(y, 1)), []).append((x, txt, font))
    out = []
    for (lid, _y), runs in by_layer.items():
        words = []  # (left ink, right ink) of each drawn word
        for x, txt, font in runs:
            pos = 0
            for wd in txt.split(" "):
                if wd:
                    l, r = ink(font, wd)
                    off = font.getlength(txt[:pos]) if pos else 0.0
                    words.append((x + off + l, x + off + r, font.size))
                pos += len(wd) + 1
        words.sort()
        if len(words) < 2:
            continue
        gap = min(b[0] - a[1] for a, b in zip(words, words[1:]))
        out.append({"font_px": float(words[0][2]), "gap_px": gap, "blur_px": eff(lid)})
    return out


def test_12_pil_blur_entrances_keep_word_gap() -> None:
    import vietanh_35_typography_engine as va
    from PIL import ImageFont
    face = str(wpb.css_face_file("Be Vietnam Pro", 800))
    f_sub, f_hero = ImageFont.truetype(face, 64), ImageFont.truetype(face, 96)
    cases = {
        "fam01": lambda t, g: va.render_va_fam01_baseline_mask_slide((1080, 1080), "vận hành đồng bộ", "hệ thống xưởng media", t, 0.0,
                                                                     f_sub, f_hero, word_gap_guard=g),
        "fam01_multicolor": lambda t, g: va.render_va_fam01_baseline_mask_slide((1080, 1080), "Luôn phải [mint:khóa]", "[gold:KẾT CẤU] [cyan:60FPS]",
                                                                                t, 0.0, f_sub, f_hero, word_gap_guard=g),
        "fam04": lambda t, g: va.render_va_fam04_vertical_passthrough_crossover((1080, 1080), "chạm đúng nhịp", "làn da thật", t, 0.0,
                                                                                f_sub, f_hero, word_gap_guard=g),
    }
    ts = [i / 60 for i in range(0, 46)]
    seen = 0
    for name, fn in cases.items():
        bad, ctl, blurred, rest = [], 0, 0, set()
        for t in ts:
            for ln in _spy_pil_lines(lambda g, t=t: fn(t, g), True):
                seen += 1
                need = mg.WORD_GAP_MIN_EM * ln["font_px"]
                if ln["gap_px"] - 2 * ln["blur_px"] < need - 0.5:
                    bad.append((name, round(t, 3), ln))
                if ln["blur_px"] > 0.35:
                    blurred += 1
                else:
                    rest.add((ln["font_px"], round(ln["gap_px"], 1)))
            ctl += sum(1 for ln in _spy_pil_lines(lambda g, t=t: fn(t, g), False)
                       if ln["gap_px"] - 2 * ln["blur_px"] < mg.WORD_GAP_MIN_EM * ln["font_px"] - 0.5)
        assert blurred and not bad, (name, bad[:6])
        assert ctl, (name, "control with the guard off must collide")
        assert len({fp for fp, _g in rest}) == len(rest), (name, "one resting gap per line once the blur is 0", sorted(rest))
    print(f"[PASS] 12 PIL vietanh fam01 / fam04: {seen} blurred-or-resting multi-word line frames keep ink gap - 2 sigma >= 0.25 em; "
          "guard off -> collide")


# ------------------------------------------------------------------------------------------------- (13) / (14) every PIL family
VA_COPY = {"text": "hệ thống xưởng media", "top_text": "vận hành đồng bộ", "hero_text": "làn da thật mỗi sáng", "bottom_text": "chạm đúng nhịp",
           "top_label": "năng lượng mới"}  # required str parameter -> multi-word copy
VA_VARIANTS = {  # extra calls on top of the defaults: every mode / colour path that draws text differently
    "render_va_fam02_diagonal_rotation_whip": [{"mode": "speed_up"}],
    "render_va_fam09_error_neon_strikethrough": [{"word_colors": {1: (250, 204, 21)}}],
}
VA_TS = [i / 60 for i in range(0, 46)]  # every 60 fps frame of the first 0.75 s (all entrances are <= 0.58 s)
VA_GETBBOX_TOL_PX = 0.5  # the spy measures ink with integer getbbox at the drawn size, the helper at 200 px (same tolerance as test 12)
VA_REST_T = 0.70  # every entrance of every family has landed by then (<= 0.58 s): the frames at / after it are the resting state


def _va_render_fns() -> list[tuple[str, object]]:
    """EVERY `render_va_fam*` function of the PIL engine (inspect), so a new family is scanned without editing this file."""
    import inspect
    import vietanh_35_typography_engine as va
    return sorted((n, f) for n, f in inspect.getmembers(va, inspect.isfunction) if n.startswith("render_va_fam") and f.__module__ == va.__name__)


def _va_call(fn, t: float, guard: bool, extra: dict):
    """Call `fn` from its signature: 1080 canvas, `t_sec = t`, `t_start = 0`, Be Vietnam Pro 800 (64 px top / sub, 96 px otherwise),
    multi-word `VA_COPY` for every required text, `word_gap_guard = guard` where the family has it, defaults elsewhere."""
    import inspect
    from PIL import ImageFont
    face = str(wpb.css_face_file("Be Vietnam Pro", 800))
    kw = {}
    for name, p in inspect.signature(fn).parameters.items():
        required = p.default is inspect.Parameter.empty
        if name == "canvas_size":
            kw[name] = (1080, 1080)
        elif name in ("t_sec", "t_start"):
            kw[name] = t if name == "t_sec" else 0.0
        elif name == "word_gap_guard":
            kw[name] = guard
        elif name.startswith("font") and required:
            kw[name] = ImageFont.truetype(face, 64 if name == "font_top" else 96)
        elif name in VA_COPY and required:
            kw[name] = VA_COPY[name]
        elif required:
            raise AssertionError(f"{fn.__name__}: no test value for required parameter {name!r}: extend VA_COPY / _va_call")
    kw.update(extra)
    return fn(**kw)


_VA_SCAN: dict = {}


def _va_scan(guard: bool) -> dict[str, list[tuple]]:
    """{function name: [(variant, t, line)]} of every multi-word line every `render_va_fam*` draws on the early frames (spied)."""
    if guard not in _VA_SCAN:
        res = {}
        for name, fn in _va_render_fns():
            res[name] = [(vi, t, ln) for vi, extra in enumerate([{}] + VA_VARIANTS.get(name, [])) for t in VA_TS
                         for ln in _spy_pil_lines(lambda g, t=t, extra=extra, fn=fn: _va_call(fn, t, g, extra), guard)]
        _VA_SCAN[guard] = res
    return _VA_SCAN[guard]


def _va_gap_errors(ln: dict) -> list:
    """`check_word_gaps` on one spied frame: the drawn ink gap with the layer's blur (sigma) as a one-key entrance."""
    return mg.check_word_gaps([{"id": "pil", "font_px": ln["font_px"], "gap_px": ln["gap_px"] + VA_GETBBOX_TOL_PX,
                                "entrance": [{"t_ms": 0.0, "opacity": 1.0, "blur_px": ln["blur_px"], "scale": 1.0}]}])


def test_13_every_pil_family_blurred_line_keeps_word_gap() -> None:
    import inspect
    scan, ctl_scan = _va_scan(True), _va_scan(False)
    blurring = {n for n, rows in scan.items() if any(ln["blur_px"] > 0.35 for _v, _t, ln in rows)}
    known = {"render_va_fam01_baseline_mask_slide", "render_va_fam02_diagonal_rotation_whip", "render_va_fam04_vertical_passthrough_crossover",
             "render_va_fam09_error_neon_strikethrough", "render_va_fam05_soft_wipe_glow_watermark", "render_va_fam09_golden_bokeh_collapse"}
    assert known <= blurring, ("the spy must see every known PIL text blur (cv2 blur / GaussianBlur / dilate on the drawn layer included)",
                               known - blurring)
    bad, n_blur = [], 0
    for name, rows in scan.items():
        for vi, t, ln in rows:
            if ln["blur_px"] > 0.35:
                n_blur += 1
            if (ln["blur_px"] > 0.35 or name in blurring) and _va_gap_errors(ln):  # a blurring family is checked at rest too
                bad.append((name, vi, round(t, 3), {k: round(v, 1) for k, v in ln.items()}))
    assert not bad, bad[:8]
    fns = dict(_va_render_fns())
    for name in sorted(blurring):
        assert "word_gap_guard" in inspect.signature(fns[name]).parameters, (name, "a text blur needs the word_gap_guard switch")
        assert any(ln["blur_px"] > 0.35 and _va_gap_errors(ln) for _v, _t, ln in ctl_scan[name]), (name, "control (guard off) must collide")
        rest = {(vi, ln["font_px"], round(ln["gap_px"], 1), round(ln["blur_px"], 2)) for vi, t, ln in scan[name] if t >= VA_REST_T}
        assert rest and len({(vi, fp) for vi, fp, _g, _b in rest}) == len(rest), (name, "one resting gap per line once landed", sorted(rest))
    print(f"[PASS] 13 every PIL family ({len(scan)} render_va_fam* functions by inspect): {n_blur} blurred multi-word line frames pass "
          f"check_word_gaps (effective spread: Gaussian / box / dilate, cv2 + PIL); blurring = {sorted(blurring)}: guard switch, guard off "
          "collides, every frame incl. rest >= 0.25 em, one resting gap")


def test_14_va_presets_map_to_engine_and_guard_blur() -> None:
    recipes = json.loads((SKILL_ROOT / "presets" / "typography_hierarchy_presets.json").read_text(encoding="utf-8"))["entrance_recipes"]
    fam = lambda s: re.match(r"(?:render_)?va_fam(\d+)_", s).group(1)  # noqa: E731
    fns, keys = {}, {}
    for name, _f in _va_render_fns():
        fns.setdefault(fam(name), []).append(name)
    for key in recipes:
        if key.startswith("va_fam"):
            keys.setdefault(fam(key), []).append(key)
    assert set(fns) == set(keys) and all(len(v) == 1 for v in keys.values()), ("one va_fam preset per engine family", fns, keys)
    scan = _va_scan(True)
    bad, guarded = [], []
    for f, names in sorted(fns.items()):
        key = keys[f][0]
        seen = max((ln["blur_px"] for n in names for _v, _t, ln in scan[n]), default=0.0)
        if seen <= 0.35:
            continue
        p = recipes[key]
        if not isinstance(p.get("entrance_word_spacing"), dict):
            bad.append((key, names, f"engine blurs text (sigma {seen:.1f}) but the preset has no entrance_word_spacing"))
            continue
        spec = _blur_spec(p)
        declared = max(spec[0] if spec else 0.0, float(p["entrance_word_spacing"].get("engine_spread_px", 0.0)))
        if spec is None or declared + 1e-6 < seen:
            bad.append((key, "the preset must declare its blur (test 05 checks the spacing against it) >= the engine's", spec, round(seen, 2)))
            continue
        guarded.append(key)
    assert not bad, bad
    print(f"[PASS] 14 {len(keys)} va_fam presets map 1:1 to engine families; every text-blurring one carries entrance_word_spacing "
          f"with a declared blur >= the engine's ({', '.join(guarded)})")


# ------------------------------------------------------------------------------------------------- (15) every web line, every frame
REPORTED_WEB_LINES = {  # (sample, line) the 2026-11-26 review measured colliding without the page guard (exit blur / echo / rest gap)
    ("kt01", "kt01Hero"), ("kt01", "kt01Helper"), ("kt03", "kt03Helper"), ("kt10", "kt10Hero"), ("kt11_arc", "kt11ArcSub"),
    ("kt11_tilt", "kt11TiltSub"), ("kt12_whisper", "kt12Whisper"), ("kt12_echo", "kt12Bottom"), ("kt12_echo", "kt12Echo1"),
    ("kt12_echo", "kt12Echo2"),
}


def _all_line_samples() -> list[dict]:
    """EVERY template sample + the extra / long-copy prop sets of tests 03 / 08 / 09 (kt11 arc 31 / 44 / 60 chars)."""
    out = [dict(s) for s in wpb.TEXT_ACCEPTANCE_SAMPLES] + [dict(e) for e in EXTRA + EDGE_EXTRA]
    out += [{"name": f"kt11_arc_{n}", "template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "svg_arc", "main_text": t, "jewel_accent": "gold"}}
            for n, t in KT11_ARC_COPY.items()]
    return out


def _probe_all_lines(samples: list[dict]) -> list[dict]:
    with tempfile.TemporaryDirectory() as td:
        jobs = _probe_jobs([dict(s, ids=None) for s in samples], td, (0, 239))
        for j in jobs:
            j["probe_ids"] = "*"  # every drawn text line of the page (glow bloom copies aside), not the guard's own list
        return wpb.render_web_plates_batch(jobs, concurrency=4, strip_meta=False, quiet=True)


def test_15_every_web_line_every_frame() -> None:
    samples = _all_line_samples()
    assert {s["template"] for s in samples} == set(wpb.TEMPLATE_DEFAULTS), "every template is probed"
    res = _probe_all_lines(samples)
    wpb.PAGE_LINE_GUARD = False
    try:
        ctl = _probe_all_lines(samples)
    finally:
        wpb.PAGE_LINE_GUARD = True
    bad, reflow, overflow, n_lines, n_frames = [], [], [], 0, 0
    ctl_bad, ctl_rows = set(), {}
    for smp, r in zip(samples, ctl):
        for fr in r["wordGaps"]:
            for ln in fr["lines"]:
                w = ln["worst"]
                if w and w["opacity"] >= 0.15:
                    ctl_rows.setdefault((smp["name"], ln["id"]), set()).add(ln["rows"])
                if w and w["effPx"] < w["needPx"] - TOL_PX:
                    ctl_bad.add((smp["name"], ln["id"]))
    for smp, r in zip(samples, res):
        assert len(r["wordGaps"]) == 240, (smp["name"], "frames 0..239 (entrance, hold and the exit) are probed")
        rows, seen = {}, set()
        for fr in r["wordGaps"]:
            for ln in fr["lines"]:
                w = ln["worst"]
                if not w:
                    continue
                seen.add(ln["id"])
                n_frames += 1
                if w["effPx"] < w["needPx"] - TOL_PX:
                    bad.append((smp["name"], fr["frameIdx"], ln["id"], w))
                if w["opacity"] >= 0.15:
                    rows.setdefault(ln["id"], set()).add(ln["rows"])
                if any(t["overflow"] for t in ln.get("onPath") or []):
                    overflow.append((smp["name"], fr["frameIdx"], ln["id"], ln["onPath"]))
        n_lines += len(seen)
        for lid, rr in rows.items():  # the widening never reflows a line (a typewriter line that grows rows does so with the guard off too)
            if len(rr) > 1 and rr != ctl_rows.get((smp["name"], lid)):
                reflow.append((smp["name"], lid, sorted(rr), sorted(ctl_rows.get((smp["name"], lid), ()))))
    assert not bad, bad[:10]
    assert not reflow, reflow
    assert not overflow, overflow[:5]
    missing = REPORTED_WEB_LINES - ctl_bad
    assert not missing, ("control (page guard off) must reproduce every reported collision", sorted(missing))
    print(f"[PASS] 15 Chrome probe of EVERY text line: {len(samples)} samples / {len(wpb.TEMPLATE_DEFAULTS)} templates, frames 0..239 "
          f"(entrance, hold, exit), {n_lines} lines / {n_frames} line-frames keep ink gap - blur >= 0.25 em (rest too); no reflow, no "
          f"textPath overflow; guard off -> {len(ctl_bad)} lines collide incl. the {len(REPORTED_WEB_LINES)} reported")


# ------------------------------------------------------------------------------------------------- (16) dviet_7706 PIL engine
def _dv_calls() -> dict:
    """render_* function name -> (call(t, guard), frame times). Multi-word copy on every line; 64 px small / 96 px hero fonts."""
    import dviet_7706_typography_choreography as dv
    from PIL import ImageFont
    face = str(wpb.css_face_file("Be Vietnam Pro", 800))
    fs, fh = ImageFont.truetype(face, 64), ImageFont.truetype(face, 96)
    c = (1080, 1080)
    ts = lambda a, b: [a + i / 60 for i in range(int(round((b - a) * 60)) + 1)]  # noqa: E731
    return {
        "render_style1_ghost_to_focus_stack": (lambda t, g: dv.render_style1_ghost_to_focus_stack(
            c, "mình đang nghi ngờ", "chán việc rồi", "công việc mỗi ngày", t, 0.0, 0.4, 0.8, fs, fh, (180, 300), word_gap_guard=g), ts(0, 1.5)),
        "render_style2_letter_scatter_convergence": (lambda t, g: dv.render_style2_letter_scatter_convergence(
            c, "mình không chỉ là", t, 0.0, fh, (540, 400)), ts(0, 0.75)),
        "render_style3_per_word_staggered_deblur": (lambda t, g: dv.render_style3_per_word_staggered_deblur(
            c, ["việt", "mỏi", "lưng"], t, 0.0, fh, (540, 400), entry_order=[1, 2, 0]), ts(0, 0.9)),
        "render_style4_tilted_multi_cluster": (lambda t, g: dv.render_style4_tilted_multi_cluster(c, t, fs, fh, word_gap_guard=g), ts(23.3, 25.5)),
        "render_style5_circular_arc_wrap": (lambda t, g: dv.render_style5_circular_arc_wrap(
            c, [{"text": "cơn nhức đầu", "theta_start_deg": 170, "theta_end_deg": 265, "t_start": 0.0, "dur": 0.45, "font": fh,
                 "color": (250, 204, 21), "is_gold": True}], t, (540, 540), 300), ts(0, 0.75)),
        "render_style6_overlap_negative_leading_lockup": (lambda t, g: dv.render_style6_overlap_negative_leading_lockup(
            c, "người ta nói", "đi thật xa", t, 0.0, 0.3, fs, fh, (300, 300), word_gap_guard=g), ts(0, 1.0)),
    }


def test_16_dviet_7706_line_blurs_keep_word_gap() -> None:
    import inspect
    import dviet_7706_typography_choreography as dv
    fns = {n for n, f in inspect.getmembers(dv, inspect.isfunction) if n.startswith("render_") and f.__module__ == dv.__name__}
    calls = _dv_calls()
    assert fns == set(calls), ("every render_* function of dviet_7706 is driven (inspect): extend _dv_calls", fns ^ set(calls))
    bad, blurring, n_blur = [], set(), 0
    for name, (fn, ts) in sorted(calls.items()):
        rows = [(t, ln) for t in ts for ln in _spy_pil_lines(lambda g, t=t: fn(t, g), True)]
        if any(ln["blur_px"] > 0.35 for _t, ln in rows):
            blurring.add(name)
        for t, ln in rows:
            n_blur += ln["blur_px"] > 0.35
            if (ln["blur_px"] > 0.35 or name in blurring) and _va_gap_errors(ln):
                bad.append((name, round(t, 3), {k: round(v, 1) for k, v in ln.items()}))
        if name in blurring:
            assert "word_gap_guard" in inspect.signature(getattr(dv, name)).parameters, (name, "a line blur needs the word_gap_guard switch")
            ctl = [ln for t in ts for ln in _spy_pil_lines(lambda g, t=t: fn(t, g), False)]
            assert any(ln["blur_px"] > 0.35 and _va_gap_errors(ln) for ln in ctl), (name, "control (guard off) must collide")
    assert not bad, bad[:8]
    want = {"render_style1_ghost_to_focus_stack", "render_style4_tilted_multi_cluster", "render_style6_overlap_negative_leading_lockup"}
    assert want <= blurring, ("the spy sees every line-level blur", want - blurring)
    print(f"[PASS] 16 dviet_7706 ({len(fns)} render_* functions by inspect): {n_blur} blurred multi-word line frames (ghost line resting "
          f"at sigma 6 included) keep ink gap - 2 sigma >= 0.25 em, rest too; line blurs {sorted(blurring)}: guard off collides")


# ------------------------------------------------------------------------------------------------- (17) bevel lockup gfx clips
def _kf_xy(kf: list, t: float) -> tuple[float, float]:
    import typography_composer as tc
    return tc._kf_value([[k[0], k[1][0]] for k in kf], t), tc._kf_value([[k[0], k[1][1]] for k in kf], t)


def _gfx_lines(clips: list[dict], fps: int = 60, spread: bool = True) -> list[dict]:
    """check_word_gaps lines of every adjacent word pair of the lockup's per-word clips: resting ink gap x scale + the position spread,
    the clip blur (linear keys, as test 04)."""
    import typography_composer as tc
    from PIL import ImageFont
    out = []
    for a, b in zip(clips, clips[1:]):
        if a["word_line"] != b["word_line"]:
            continue
        f = a["font_px"]
        font = ImageFont.truetype(tc._resolve_typo_font_path("Be Vietnam Pro", "Black" if f >= 90 else "Medium"), int(f))
        wa, wb = Path(a["src"]).stem, Path(b["src"]).stem
        assert wa != wb
        dur = a["dur"]
        keys = []
        for i in range(int(round(dur * fps)) + 1):
            t = i / fps
            sc = tc._kf_value(a["motion"]["scale"], t, 100.0) / 100.0
            dx = (_kf_xy(b["motion"]["position"], t)[0] - _kf_xy(a["motion"]["position"], t)[0]) if spread else 0.0
            blur = tc._kf_value(a["effects"][0]["params"]["blurriness"], t)
            keys.append({"t_ms": t * 1000, "opacity": tc._kf_value(a["opacity"], t, 100.0) / 100.0, "blur_px": blur, "scale": sc,
                         "extra_gap_px": dx / sc})
        out.append({"font": font, "pair": (a["word_index"], b["word_index"]), "font_px": f, "entrance": keys})
    return out


def test_17_bevel_lockup_clips_spread_with_blur() -> None:
    import typography_composer as tc
    from PIL import ImageFont
    n_pairs = 0
    with tempfile.TemporaryDirectory() as td:
        for kw in ({}, {"lead_text": "bí quyết làm đẹp", "lead_size": 70}, {"tilt_deg": 3.0}):
            r = tc.export_dviet_bevel_lockup_png(Path(td) / "lockup.png", "video sản phẩm thật", allow_static_thumbnail=True, **kw)
            assert "gfx_clip" not in r and r["gfx_clips"], "the timeline gets one clip per word"
            clips = r["gfx_clips"]
            assert all(Path(c["src"]).is_file() for c in clips) and Path(r["path"]).is_file()
            assert all(any(fx["effect"] == "gaussian_blur" for fx in c["effects"]) for c in clips), "the blur effect is kept"
            for c in clips:
                blur = c["effects"][0]["params"]["blurriness"]
                assert max(float(k[1]) for k in blur) >= 6.0, blur
            for line_id in {c["word_line"] for c in clips}:
                ln = [c for c in clips if c["word_line"] == line_id]
                text = " ".join(["video", "sản", "phẩm", "thật"] if ln[0]["font_px"] == 98 else ["bí", "quyết", "làm", "đẹp"])
                face = tc._resolve_typo_font_path("Be Vietnam Pro", "Black" if ln[0]["font_px"] == 98 else "Medium")
                ft = ImageFont.truetype(face, 200)
                words = text.split()
                for (w1, w2), pair in zip(zip(words, words[1:]), _gfx_lines(ln)):
                    nat_px = (ft.getlength(w1 + " ") - ft.getbbox(w1)[2] + ft.getbbox(w2)[0]) / 200 * pair["font_px"]
                    line = {"id": f"{line_id}{pair['pair']}", "font_px": pair["font_px"], "gap_px": nat_px, "entrance": pair["entrance"]}
                    assert mg.check_word_gaps([line]) == [], (kw, pair["pair"], mg.check_word_gaps([line]))
                    n_pairs += 1
                ctl = _gfx_lines(ln, spread=False)
                nat0 = (ft.getlength(words[0] + " ") - ft.getbbox(words[0])[2] + ft.getbbox(words[1])[0]) / 200 * ctl[0]["font_px"]
                assert mg.check_word_gaps([{"id": "ctl", "font_px": ctl[0]["font_px"], "gap_px": nat0, "entrance": ctl[0]["entrance"]}]), \
                    "control (no spread) must collide"
            rest = [round(_kf_xy(c["motion"]["position"], c["dur"] * 0.6)[0] - _kf_xy(clips[0]["motion"]["position"], c["dur"] * 0.6)[0], 2)
                    for c in clips if c["word_line"] == clips[0]["word_line"]]
            first = [round(_kf_xy(c["motion"]["position"], 0)[0] - _kf_xy(clips[0]["motion"]["position"], 0)[0], 2)
                     for c in clips if c["word_line"] == clips[0]["word_line"]]
            assert first[-1] > rest[-1] > 0, ("spread while blurred, back to rest at blur 0", first, rest)
    print(f"[PASS] 17 export_dviet_bevel_lockup_png(allow_static_thumbnail=True): one clip per word keeps the blur 12 -> 0 / 0 -> 6; "
          f"{n_pairs} word pairs keep ink gap - 2 blur >= 0.25 em on every frame (spread eases back to rest); no spread -> collide")


if __name__ == "__main__":
    test_01_helper_and_js_mirror()
    test_02_gate_model_takes_the_guard()
    test_03_web_plate_entrances_keep_word_gap()
    test_04_filmcraft_blur_entrance_tracking()
    test_05_blur_in_presets_carry_word_spacing()
    test_06_every_template_text_band_and_bounds()
    test_07_render_batch_hard_block()
    test_08_repair_long_copy_and_plate_edges()
    test_09_kt11_arc_long_copy_fits()
    test_10_textpath_overflow_hard_block()
    test_11_fit_kt_plate_heights_real_ink_and_cap()
    test_12_pil_blur_entrances_keep_word_gap()
    test_13_every_pil_family_blurred_line_keeps_word_gap()
    test_14_va_presets_map_to_engine_and_guard_blur()
    test_15_every_web_line_every_frame()
    test_16_dviet_7706_line_blurs_keep_word_gap()
    test_17_bevel_lockup_clips_spread_with_blur()
    print("TẤT CẢ ĐẠT (text legibility + entrance word spacing, skill v7.9.0)")
