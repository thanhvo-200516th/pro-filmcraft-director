#!/usr/bin/env python3
"""
Tests for skill code v7.9.0: the v4 review defects (K1-K4, A1, V-FLASH, V-E1, V-TEXTGAPS) as skill-level gates.

  01 pop-out card: a dark source side band (letterbox / dark wall edge) and a dark wall speck never reach the card
     (`popout_inner_edge_dark_strip_px` <= 4 px, `card_dark_speck_count` == 0)
  02 crown matte: a blocky low-res matte is refined (guided filter + edge contrast): `crown_edge_metrics` jaggedness and 10-90 rise
  03 rendered flash gate (`check_flashes`): v4 hook strobe fails (luma cap), 4 pulses / s fail (rate), one soft flash and a held
     bright scene pass; `snap_punch` never exceeds the mean-luma cap
  04 plan flash gate (`check_flash_plan`, used by `check_hook`): template clean, a full white flash and 4 flashes / s fail
  05 legibility of ALL overlay text: `check_text_legibility` on effective px (font x plate scale), card labels via `check_hook`,
     polaroid template CSS passes `audit_plate_text_px` at plate scale 0.76
  06 word-gap collision during blur-in / scale-in (`check_word_gaps`, `word_gap_collision` in `check_hook`)
  07 hook text coverage (no text-free gap > 150 ms in 0-3 s) and the strict first-text rule (`first_text_late`, default on)
  08 `render_web_plates_batch` runs `audit_plate_text_px` on every job: undersized text is a hard block (warn when `decorative`)
  09 default kt03 bloom and the per-word stagger preset keep the 0.25 em word gap on every frame (`check_word_gaps`)
  10 qa_sync: a `block: true` row is never ĐẠT, is flagged in the shift list, and the gate does not pass while one remains

Synthetic inputs only (no video file, no network). Plain asserts with a `__main__` runner: `python3 tests/test_skill_v79.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

W, H = 1080, 1920
CARD = (70, 1065, 1010, 1705)


def _sev(findings: list[dict], level: str = "error") -> set[str]:
    return {f["rule"] for f in findings if f["severity"] == level}


# ---------------------------------------------------------------------------------------------- (1) pop-out inner edge
def _dirty_source() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Light paper, a 720x1280 A-roll with a dark wall band at x 0..95 (v4: luma 6-12 vs 45) plus a dark wall speck, and a person alpha."""
    backdrop = np.full((H, W, 3), (244, 238, 250), np.uint8)
    rng = np.random.default_rng(5)
    aroll = np.clip(np.full((1280, 720, 3), 46.0) + cv2.GaussianBlur(rng.normal(0, 3, (1280, 720, 3)).astype(np.float32), (0, 0), 2.0), 0, 255)
    aroll[:, :96] = 9.0                                   # dark side band baked into the source
    aroll = aroll.astype(np.uint8)
    alpha = np.zeros((1280, 720), np.uint8)
    cv2.ellipse(alpha, (380, 700), (150, 170), 0, 0, 360, 255, -1)
    cv2.rectangle(alpha, (250, 820), (510, 1279), 255, -1)
    aroll[alpha > 0] = (90, 120, 190)
    cv2.ellipse(aroll, (640, 880), (6, 5), 0, 0, 360, (12, 12, 12), -1)   # wall-fixture leftover (the v4 top-right dot)
    return backdrop, aroll, alpha


def test_01_popout_inner_edge_strip_and_speck() -> None:
    import fast_studio_compositor as fsc
    import motion_gate as mg
    backdrop, aroll, alpha = _dirty_source()
    kw = dict(head_anchor=(380.0, 530.0), photo_scale=1.36)
    # the metric itself: a raw paste of the dirty source shows the strip and the speck
    M = np.array([[1.36, 0, 540 - 1.36 * 380], [0, 1.36, 900 - 1.36 * 530]], np.float32)
    raw = cv2.warpAffine(aroll, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    pal = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR)
    pasted = backdrop.copy()
    x0, y0, x1, y1 = CARD
    pasted[y0:y1, x0:x1] = raw[y0:y1, x0:x1]
    assert mg.popout_inner_edge_dark_strip_px(pasted, CARD) > 20, mg.popout_inner_edge_dark_strip_px(pasted, CARD)
    assert mg.card_dark_speck_count(pasted, CARD, exclude_mask=pal) >= 1
    out, meta = fsc.render_popout_studio_card(backdrop, aroll, alpha, **kw)
    strip = mg.popout_inner_edge_dark_strip_px(out, meta["card_rect"])
    specks = mg.card_dark_speck_count(out, meta["card_rect"], exclude_mask=pal)
    assert strip <= mg.INNER_STRIP_GATE_PX, f"dark inner-edge strip {strip:.1f} px > {mg.INNER_STRIP_GATE_PX} px"
    assert specks == 0, f"{specks} dark wall speck(s) inside the card"
    assert meta["source_bands_px"]["left"] >= 90, meta["source_bands_px"]
    # clean source: the guard is a no-op on the card interior (no band, no speck)
    clean = aroll.copy()
    clean[:, :96] = 46
    clean[alpha > 0] = (90, 120, 190)
    _, m2 = fsc.render_popout_studio_card(backdrop, clean, alpha, **kw)
    assert m2["source_bands_px"] == {"left": 0, "right": 0, "top": 0, "bottom": 0}, m2["source_bands_px"]
    print(f"[PASS] 01 pop-out: source band {meta['source_bands_px']['left']} px cleaned, inner strip {strip:.1f} px, specks {specks}")


# ---------------------------------------------------------------------------------------------- (2) crown matte
def test_02_crown_matte_refine() -> None:
    import fast_studio_compositor as fsc
    import motion_gate as mg
    backdrop = np.full((H, W, 3), (244, 238, 250), np.uint8)
    aroll = np.full((1280, 720, 3), (60, 64, 70), np.uint8)
    full = np.zeros((1280, 720), np.uint8)
    cv2.ellipse(full, (340, 700), (160, 160), 0, 0, 360, 255, -1, lineType=cv2.LINE_AA)
    cv2.rectangle(full, (200, 800), (480, 1279), 255, -1)
    aroll[full > 127] = (70, 110, 200)
    # a blocky 1/8-res matte (the RVM matte is computed small and at 30 fps), upscaled nearest -> stair-step crown edge
    small = cv2.resize(full, (90, 160), interpolation=cv2.INTER_AREA)
    blocky = cv2.resize((small > 127).astype(np.uint8) * 255, (720, 1280), interpolation=cv2.INTER_NEAREST)
    _, off = fsc.render_popout_studio_card(backdrop, aroll, blocky, crown_refine=False)
    _, on = fsc.render_popout_studio_card(backdrop, aroll, blocky)
    a_off, a_on = mg.crown_edge_metrics(off["crown_alpha"]), mg.crown_edge_metrics(on["crown_alpha"])
    assert a_on["columns"] > 100, a_on
    assert a_on["jaggedness_px"] < a_off["jaggedness_px"] * 0.7, (a_on, a_off)
    assert a_on["jaggedness_px"] <= mg.CROWN_JAG_GATE_PX and a_on["rise_px"] <= mg.CROWN_RISE_GATE_PX, a_on
    print(f"[PASS] 02 crown matte: jaggedness {a_off['jaggedness_px']:.2f} -> {a_on['jaggedness_px']:.2f} px, rise {a_on['rise_px']:.2f} px")


# ---------------------------------------------------------------------------------------------- (3) rendered flash gate
def _frames(lumas: list[float]) -> list[np.ndarray]:
    return [np.full((240, 135, 3), int(round(v)), np.uint8) for v in lumas]


def _pulse(peak: float, base: float = 70.0, decay: int = 8) -> list[float]:
    return [peak] + [base + (peak - base) * (1 - (k + 1) / decay) for k in range(decay)]


def test_03_rendered_flash_gate() -> None:
    import fast_studio_compositor as fsc
    import motion_gate as mg
    fps = 60
    # v4 hook: 1-frame jump 52 -> 248 then two 208 shutter pulses, 0.25 s apart
    v4 = [52.0] * 10 + _pulse(248) + [70.0] * 6 + _pulse(208, decay=3) + [70.0] * 11 + _pulse(208, decay=3) + [70.0] * 30
    r = mg.check_flashes(_frames(v4), fps=fps)
    assert not r["ok"] and r["peak_luma"] >= 240 and any("luma" in e for e in r["errors"]), r
    # 4 pulses within one second (peaks under the cap) break the 3 / s rule
    four = [60.0] * 6
    for _ in range(4):
        four += _pulse(190, base=60, decay=4) + [60.0] * 9
    r4 = mg.check_flashes(_frames(four + [60.0] * 20), fps=fps)
    assert not r4["ok"] and r4["max_flashes_per_s"] >= 4 and any("per" in e for e in r4["errors"]), r4
    # one soft flash ramped over 3 frames to 200 passes; a cut to a held bright paper scene is not a flash
    soft = [70.0] * 10 + [130.0, 175.0, 200.0, 170.0, 140.0, 110.0, 90.0, 70.0] + [70.0] * 20
    assert mg.check_flashes(_frames(soft), fps=fps)["ok"], mg.check_flashes(_frames(soft), fps=fps)
    held = [70.0] * 10 + [242.0] * 90 + [70.0] * 10
    rh = mg.check_flashes(_frames(held), fps=fps)
    assert rh["ok"], rh
    # snap_punch caps the mean luma of the flashed frame
    img = np.full((H // 4, W // 4, 3), 170, np.uint8)
    fl = fsc.snap_punch(img, 1.0, anchor_xy=(W / 8, 150), flash=1.0, flash_bgr=(255, 255, 255))
    assert cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY).mean() <= mg.FLASH_LUMA_CAP + 0.5
    print(f"[PASS] 03 flash gate: v4 hook peak {r['peak_luma']:.0f} fails, 4 / s fails, soft flash and held paper pass, snap_punch capped")


# ---------------------------------------------------------------------------------------------- (4) plan flash gate
def test_04_plan_flash_gate_in_check_hook() -> None:
    import motion_gate as mg
    import studio_recipe as sr
    hook = sr.hook_template()
    assert not ({"flash_luma_cap", "flash_rate"} & {f["rule"] for f in sr.check_hook(hook)}), sr.check_hook(hook)
    white = sr.hook_template()
    next(e for e in white["events"] if e.get("id") == "white_cut").pop("opacity", None)   # full-frame white, the v4 V8 white_flash
    assert "flash_luma_cap" in _sev(sr.check_hook(white)), sr.check_hook(white)
    strobe = sr.hook_template()
    strobe["events"] += [{"t_ms": t, "kind": "flash", "id": f"f{t}", "opacity": [0, 40, 0]} for t in (3500, 3550, 3600)]
    assert "flash_rate" in _sev(sr.check_hook(strobe)), sr.check_hook(strobe)
    assert abs(mg.flash_peak_luma(1.0, 80.0) - 255.0) < 1e-6 and mg.flash_peak_luma(0.6, 80.0) < 220
    print("[PASS] 04 check_hook: template flashes pass, full white flash and 4 flashes / s fail")


# ---------------------------------------------------------------------------------------------- (5) legibility
def test_05_all_overlay_text_legible() -> None:
    import studio_recipe as sr
    import web_plate_builder as wpb
    items = [{"id": "pol_caption", "font_px": 24, "scale": 0.76}, {"id": "pol_note", "font_px": 36, "scale": 0.76},
             {"id": "p05", "font_px": 54}, {"id": "ok", "font_px": 88, "scale": 0.76}, {"id": "glyph", "glyph_px": 40}]
    f = sr.check_text_legibility(items)
    bad = {x["id"] for x in f if x["severity"] == "error"}
    assert bad == {"pol_caption", "pol_note", "p05", "glyph"}, f
    assert all(x["rule"] == "text_min_size" for x in f)
    hook = sr.hook_template()
    hook["labels"] = [{"id": "SẢN PHẨM 01", "t_ms": 2720, "font_px": 13, "scale": 0.76}]
    assert "text_min_size" in _sev(sr.check_hook(hook)), sr.check_hook(hook)
    # polaroid template: every CSS font size times the plate scale clears 64 px
    html = wpb.build_template_html("skewed_3d_polaroid_trio", {"captions": ["Ảnh thô 01", "Ảnh thô 02", "Ảnh thô 03"],
                                                               "bottom_note": "chụp vội trên bàn làm việc", "plate_scale": 0.76})
    assert wpb.audit_plate_text_px(html, 0.76) == [], wpb.audit_plate_text_px(html, 0.76)
    assert wpb.audit_plate_text_px(".x { font-size: 24px; }", 0.76), "the audit must flag a 24 px CSS size"
    assert "RAW 01" not in html, "no default stamp text"
    print("[PASS] 05 legibility: plate-scaled labels fail, card labels fail in check_hook, polaroid CSS clears 64 px at 0.76")


# ---------------------------------------------------------------------------------------------- (6) word gaps
def test_06_word_gap_collision() -> None:
    import motion_gate as mg
    import studio_recipe as sr
    blur_in = [{"t_ms": 0, "opacity": 0.1, "blur_px": 10, "scale": 1.12}, {"t_ms": 67, "opacity": 1.0, "blur_px": 0, "scale": 1.0}]
    k3 = mg.check_word_gaps([{"id": "E3", "font_px": 84, "gap_px": 21, "entrance": blur_in}])
    assert k3 and k3[0]["rule"] == "word_gap_collision" and k3[0]["severity"] == "error" and k3[0]["value"] < 21, k3
    calm = [{"t_ms": 0, "opacity": 0.1, "blur_px": 4, "scale": 1.04}, {"t_ms": 67, "opacity": 1.0, "blur_px": 0, "scale": 1.0}]
    assert mg.check_word_gaps([{"id": "E3", "font_px": 84, "gap_px": 30, "entrance": calm}]) == []
    per_word = [{"t_ms": 0, "opacity": 0.5, "blur_px": 0, "scale": 1.3}, {"t_ms": 100, "opacity": 1.0, "blur_px": 0, "scale": 1.0}]
    assert mg.check_word_gaps([{"id": "pw", "font_px": 84, "gap_px": 30, "word_w_px": 200, "per_word_scale": True, "entrance": per_word}])
    assert mg.check_word_gaps([{"id": "rest", "font_px": 84, "gap_px": 12}]), "a resting gap under 0.25 em fails too"
    hook = sr.hook_template()
    next(e for e in hook["events"] if e.get("id") == "clause").update(font_px=84, gap_px=21, entrance=blur_in)
    assert "word_gap_collision" in _sev(sr.check_hook(hook)), sr.check_hook(hook)
    print(f"[PASS] 06 word gaps: v4 K3 blur-in collides (min {k3[0]['value']:.1f} px), wider gap + sigma 4 passes, per-word scale-in caught")


# ---------------------------------------------------------------------------------------------- (7) coverage + first text
VO = [("Vì", 0.02, 0.12), ("trên", 0.12, 0.34), ("đây", 0.34, 0.52), ("là", 0.52, 0.86), ("video", 0.86, 1.06), ("sản", 1.06, 1.24),
      ("phẩm", 1.24, 1.48), ("mà", 1.48, 1.66), ("bọn", 1.66, 1.8), ("mình", 1.8, 1.92), ("vừa", 1.92, 2.06), ("làm", 2.06, 2.16),
      ("cho", 2.16, 2.26), ("các", 2.26, 2.36), ("hàng", 2.36, 2.58), ("và", 2.58, 2.76), ("phía", 2.76, 2.94), ("dưới", 2.94, 3.2)]


def _txt(t_ms: int, dur: int, words: list[str], tier: str = "support") -> dict:
    return {"t_ms": t_ms, "kind": "text", "id": f"t{t_ms}", "tier": tier, "text": " ".join(words).upper(), "dur_ms": dur, "voice_words": words}


def test_07_text_coverage_and_first_text() -> None:
    import studio_recipe as sr
    h = sr.hook_template()
    assert "text_coverage" not in {f["rule"] for f in sr.check_hook(h)}, sr.check_hook(h)
    # v4: E2 ends at 1.30 s, E3 starts at 1.49 s (190 ms gap); E3 ends 2.43 s, cards at 2.73 s
    v4 = sr.hook_template()
    v4["events"] = [e for e in v4["events"] if e["kind"] != "text"] + [
        _txt(150, 600, ["trên", "đây", "là"], "lead"), _txt(700, 600, ["video"], "hero"), _txt(1490, 940, ["bọn", "mình"])]
    cov = [f for f in sr.check_hook(v4, words=VO) if f["rule"] == "text_coverage"]
    assert cov and cov[0]["severity"] == "error" and abs(cov[0]["t0"] - 1.3) < 1e-6 and cov[0]["value"] == 190, cov
    ev = sr.hook_text_from_words(VO)
    assert "text_coverage" not in {f["rule"] for f in sr.check_hook({**h, "events": [e for e in h["events"] if e["kind"] != "text"] + ev}, words=VO)}
    # strict first text: E1 at 150 ms quotes 'trên' voiced at 120 ms -> late; at 100 ms it passes
    late = sr.check_hook(v4, words=VO, strict_first_text=True)
    f = [x for x in late if x["rule"] == "first_text_late"]
    assert f and f[0]["severity"] == "error" and f[0]["value"] == 30, late
    v4["events"] = [dict(e, t_ms=100) if e.get("id") == "t150" else e for e in v4["events"]]
    assert "first_text_late" not in {x["rule"] for x in sr.check_hook(v4, words=VO, strict_first_text=True)}
    strict = sr.hook_text_from_words(VO, strict=True)
    assert strict[0]["t_ms"] <= 120 - 17 and strict[0]["lead_ms"] >= 17, strict[0]
    print("[PASS] 07 text coverage: v4 190 ms gap at 1.30 s fails, template and hook_text_from_words pass; first_text_late +30 ms caught")


# ---------------------------------------------------------------------------------------------- (8) plate text audit in the batch
def test_08_batch_render_audits_plate_text() -> None:
    """v7.9.0 + user decision 2026-11-26: undersized plate text is a HARD BLOCK (UndersizedTextError, raised before Chrome for CSS);
    `decorative: true` only warns. The 18 px kt pill of v4 is 70 px now, so the default kt01 pill passes."""
    import json
    import subprocess
    import tempfile
    import warnings
    import web_plate_builder as wpb
    calls = []

    def fake_run(cmd, **kw):
        jobs = json.loads(Path(cmd[cmd.index("--batch-json") + 1]).read_text(encoding="utf-8"))["jobs"]
        calls.append(jobs)
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": True, "results": [{"out": j["out"]} for j in jobs]}) + "\n", "")

    real_run, real_node = wpb.subprocess.run, wpb.resolve_node_binary
    wpb.subprocess.run, wpb.resolve_node_binary = fake_run, (lambda: "node")
    try:
        with tempfile.TemporaryDirectory() as td, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            jobs = [{"template": "kt12_whisper_or_directional_echo", "props": {"demo": True}, "out": f"{td}/a.png", "mode": "still"},
                    {"template": "skewed_3d_polaroid_trio", "props": {"captions": ["Ảnh 01", "Ảnh 02", "Ảnh 03"], "plate_scale": 0.76},
                     "out": f"{td}/b.png", "mode": "still"},
                    {"template": "kt01_kiss_editorial_2line", "props": {"demo": True, "pill_text": "mới"}, "out": f"{td}/c.png", "mode": "still"},
                    {"template": "kt01_kiss_editorial_2line", "props": {"demo": True, "kicker": "nhỏ", "kicker_size": 30}, "out": f"{td}/d.png",
                     "mode": "still", "decorative": True}]
            res = wpb.render_web_plates_batch(jobs, strip_meta=False, quiet=True)
            small = dict(jobs[3], decorative=False, out=f"{td}/e.png")
            n_calls = len(calls)
            try:
                wpb.render_web_plates_batch([jobs[0], small], strip_meta=False, quiet=True)
                raise AssertionError("an undersized non-decorative plate must fail the batch")
            except wpb.UndersizedTextError as exc:
                assert "e.png" in str(exc) and "64px" in str(exc) and len(calls) == n_calls, (str(exc), "raised before the engine ran")
    finally:
        wpb.subprocess.run, wpb.resolve_node_binary = real_run, real_node
    assert calls and [r["text_audit"]["severity"] for r in res] == ["ok", "ok", "ok", "warn"], [r["text_audit"] for r in res]
    assert res[1]["text_audit"]["plate_scale"] == 0.76 and res[3]["text_audit"]["undersized"], res[3]
    assert all(r["text_audit"]["ok"] is (r["text_audit"]["severity"] == "ok") for r in res)
    msgs = [str(w.message) for w in caught]
    assert any("d.png" in m and "64px" in m for m in msgs) and not any("c.png" in m for m in msgs), msgs
    print("[PASS] 08 batch render: every plate audited at its plate scale; undersized text = hard block (raised), decorative = warn")


# ---------------------------------------------------------------------------------------------- (9) default kt03 word gap
def _kt03_lines(props: dict) -> list[dict]:
    """The kt03 bloom as `check_word_gaps` lines: gap and font from the generated CSS, the per-word entrance from WORDS_META using the
    template's own formulas (opacity min(1, 1.35 p), blur (1 - p) x blur_px, scale (0.88 + 0.12 p) x scale), p sampled densely."""
    import json
    import re
    import web_plate_builder as wpb
    html = wpb.build_template_html("kt03_per_word_nonlinear_bloom", props, width=1080, height=420)
    meta = json.loads(re.search(r"const WORDS_META = (\[.*?\]);", html).group(1))
    row = re.search(r"\.kt03-row \{([^}]*)\}", html).group(1)
    f = float(re.search(r"font-size: (\d+)px", row).group(1))
    cg = float(re.search(r"column-gap: ([\d.]+)em", row).group(1))
    mx = float(re.search(r"\.kt03-word \{[^}]*margin: -[\d.]+em -([\d.]+)em", html).group(1))
    pad = float(re.search(r"\.kt-diacritic-safe \{[^}]*padding: [\d.]+em ([\d.]+)em", html).group(1))
    gap_px = (cg + 2 * (pad - mx)) * f
    font = wpb.FONT_ROOT_BASE / "BeVietnamPro-ExtraBold.ttf"
    if font.is_file():
        from PIL import ImageFont
        ft = ImageFont.truetype(str(font), int(f))
    lines = []
    for m in meta:
        w = ft.getlength(m["word"]) if font.is_file() else wpb.KT03_WORD_W_EM * f * len(m["word"])
        ent = [{"t_ms": i * 13, "opacity": min(1.0, 1.35 * (i / 20)), "blur_px": (1 - i / 20) * m["blur_px"],
                "scale": (0.88 + 0.12 * i / 20) * m["scale"]} for i in range(21)]
        lines.append({"id": m["word"], "font_px": f, "gap_px": gap_px, "per_word_scale": True, "word_w_px": w, "entrance": ent})
    return lines


def test_09_default_kt_entrances_keep_word_gap() -> None:
    import copy
    import json
    import motion_gate as mg
    for props in ({"demo": True}, {"main_text": "mình vừa làm", "main_size": 102}, {"words": ["tách", "nền", "siêu", "nhanh"], "highlight_idx": 1},
                  {"main_text": "cứ Camera bật", "main_size": 68}):
        lines = _kt03_lines(props)
        assert lines and mg.check_word_gaps(lines) == [], (props, mg.check_word_gaps(lines))
        assert any(ln["entrance"][0]["blur_px"] > 0 for ln in lines), "the bloom keeps a blur where the gap allows it"
    # negative control: the pre-v7.9.0 bloom (blur 12 px, highlight 1.06x) collides on the same gap
    old = copy.deepcopy(_kt03_lines({"demo": True}))
    for ln, sc in zip(old, (1.0, 1.0, 1.06)):
        ln["entrance"] = [{**k, "blur_px": (1 - i / 20) * 12.0, "scale": (0.88 + 0.12 * i / 20) * sc} for i, k in enumerate(ln["entrance"])]
    assert mg.check_word_gaps(old), "a 12 px bloom over the 0.34 em gap must fail"
    # per-word stagger preset (values are additive-only): the guardrail caps the per-word scale at 100 % on its 0.25 em gap
    pws = json.loads((SKILL_ROOT / "presets" / "typography_hierarchy_presets.json").read_text(encoding="utf-8"))
    pws = next(v for k, v in _walk(pws) if k == "per_word_stagger")
    cap, f = pws["nfc_guardrails"]["max_word_scale_pct"], 84.0
    gap = pws["nfc_guardrails"]["word_spacing_em"] * f
    keys = lambda sc: [{"t_ms": i * 100, "opacity": 1.0, "scale": v / 100.0} for i, v in enumerate(sc)]  # noqa: E731
    line = lambda sc: [{"id": "pws", "font_px": f, "gap_px": gap, "per_word_scale": True, "word_w_px": 200, "entrance": keys(sc)}]  # noqa: E731
    assert cap == 100.0 and mg.check_word_gaps(line([min(v, cap) for v in pws["scale"]])) == []
    assert max(pws["scale"]) <= cap or mg.check_word_gaps(line(pws["scale"])), "an unclamped overshoot must be caught"
    print("[PASS] 09 kt03 default bloom (4 prop sets) keeps >= 0.25 em, the old 12 px / 1.06x fails; per_word_stagger clamped to max_word_scale_pct passes, 101 % fails")


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


# ---------------------------------------------------------------------------------------------- (10) SFX block rows
def test_10_sfx_block_rows_never_pass() -> None:
    import qa_sync as qs
    ev = {"track": "SFX 1", "at": 0.8, "name": "SFX whoosh · cut", "src": "w.wav"}
    # fps 10: the peak tolerance (0.05 + 1 frame = 0.15 s) is wider than the 0.1 s block threshold
    cut = {"beat": "cut", "clip": "V1 @ 1.00", "event": ev, **qs.judge(1.0, 1.0, {"a_peak": 0.88, "a_start": 0.95}, 10.0)}
    assert cut["block"] and not cut["ok"] and cut["status"] != "ĐẠT", cut
    txt = qs.judge_text(1.0, {"a_peak": 0.89, "a_start": 0.89}, False, 8.0)
    assert txt["block"] and not txt["ok"] and txt["status"] != "ĐẠT", txt
    sh = qs.shifts_of([cut])
    assert len(sh) == 1 and sh[0]["block"] is True and sh[0]["shift"] > 0, sh
    fine = {"beat": "cut", "clip": "V1 @ 2.00", "event": ev, **qs.judge(2.0, 2.0, {"a_peak": 2.03, "a_start": 1.98}, 30.0)}
    assert fine["ok"] and not fine["block"] and "block" not in str(qs.shifts_of([fine]))
    assert qs.gate_pass([fine]) and not qs.gate_pass([fine, cut])
    print("[PASS] 10 qa_sync: a block row is never ĐẠT (fps 10 / 8 edge), carries block:true in sfx_shifts, gate_pass is False while it remains")


if __name__ == "__main__":
    test_01_popout_inner_edge_strip_and_speck()
    test_02_crown_matte_refine()
    test_03_rendered_flash_gate()
    test_04_plan_flash_gate_in_check_hook()
    test_05_all_overlay_text_legible()
    test_06_word_gap_collision()
    test_07_text_coverage_and_first_text()
    test_08_batch_render_audits_plate_text()
    test_09_default_kt_entrances_keep_word_gap()
    test_10_sfx_block_rows_never_pass()
    print("TẤT CẢ ĐẠT (skill v7.9.0)")
