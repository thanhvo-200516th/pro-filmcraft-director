#!/usr/bin/env python3
"""
Root-cause tests for v7.9.3 kinetic typography placement and legibility (e2e_v791 findings).

  01 workspace_context subject_framing (SOURCE px 720x1280) is scaled to the 1080x1920 sequence (hair 768, chin 1392)
  02 planner + workspace_context: real cranial band [720, 1424] cleared, 0 chest-rail beats while the face is visible,
     cranial status "verified"; without context the old default band is kept and flagged "assumed_default"
  03 planner + scenes (path inputs): face modes P/B/S/A1/N forbid the chest rail, H/A2 (full-screen B-roll) do not
  04 resolve_dual_rail_safe_y(allow_chest_rail=False) never returns the chest rail
  05 kt12 whisper over A-roll: weight >= 600, a dark halo, accent_text drawn; kt10 draws accent_text
  06 kt_dropped_text finds a real drop (kt11 tilt with kicker + accent); the batch refuses it without allow_drop_accent
  07 the planner reports dropped_text and fails on a dropped accent unless the beat sets allow_drop_accent
  08 text_contrast_ratio samples the background under the ink box (None without a frame)
  09 check_text_legibility: optional `contrast` < 3:1 error, < 4.5:1 warn
  10 H/A2 scenes: the squircle PiP window (look_s_render.PIP_RECTS, br / bl) is an exclusion box -- no planned ink intersects it;
     the x-shift fallback ends the ink >= 24 px before the PiP and keeps the 50 px safe zone

Synthetic inputs only, no Chrome. Plain asserts with a `__main__` runner: `python3 tests/test_rootcause_typo_v793.py`.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import studio_recipe as sr  # noqa: E402
import typography_composer as tc  # noqa: E402
import web_plate_builder as wpb  # noqa: E402

FACE_BAND = (768.0 - 48.0, 1392.0 + 32.0)  # [hair - 48, chin + 32] in sequence px

CTX = {
    "resolution": {"width": 720, "height": 1280},
    "subject_framing": {
        "detected": True,
        "face_bbox_px": [229, 657, 489, 928],
        "hair_top_y_px": 512,
        "chin_y_px": 928,
        "dual_rail_zones": {
            "upper_editorial_stage": {"y_band_px": [147, 464], "usable": True},
            "chest_tactile_rail": {"y_band_px": [960, 960], "usable": False},
        },
    },
}

BEATS = [
    {"main_text": f"ý chính {i}", "accent_text": f"phần phụ {i}", "at": i * 2.4, "dur": 1.8} for i in range(9)
]


def _overlaps_band(bbox) -> bool:
    return not (bbox[3] <= FACE_BAND[0] + 0.5 or bbox[1] >= FACE_BAND[1] - 0.5)


def test_01_face_zone_scaled_to_sequence() -> None:
    fz = tc.face_zone_from_workspace_context(CTX)
    assert fz is not None
    assert abs(fz["hair_top_y"] - 768.0) < 0.6 and abs(fz["chin_y"] - 1392.0) < 0.6, fz
    assert fz["chest_rail_usable"] is False
    assert tc.face_zone_from_workspace_context({"subject_framing": {"detected": False}}) is None
    print("[PASS] 01 subject_framing source px -> sequence px (hair 768, chin 1392), chest rail unusable")


def test_02_planner_uses_real_face() -> None:
    plan = tc.plan_dviet_kinetic_beat_schedule(BEATS, None, workspace_context=CTX)
    st = plan["stats"]
    assert st["cranial_lock_status"] == "verified", st
    assert st["chest_rail_face_beats"] == 0, st
    for b in plan["beats"]:
        assert b["face_visible"] is True and b["rail"] != "chest_tactile_rail", b
        assert not _overlaps_band(b["ink_bbox_screen"]), (b["template"], b["ink_bbox_screen"])
    old = tc.plan_dviet_kinetic_beat_schedule(BEATS, None)
    assert old["stats"]["cranial_lock_status"] == "assumed_default", old["stats"]
    assert any(b["rail"] == "chest_tactile_rail" for b in old["beats"]), "no context = old alternation kept"
    print("[PASS] 02 workspace_context: 0 chest beats with face, real band cleared; no context = assumed_default")


def test_03_scenes_decide_face_visibility() -> None:
    scenes = {"scenes": [{"start": 0.0, "end": 7.0, "mode": "P"}, {"start": 7.0, "end": 14.5, "mode": "A2"},
                         {"start": 14.5, "end": 30.0, "mode": "S"}]}
    with tempfile.TemporaryDirectory() as td:
        cp, sp = Path(td, "ctx.json"), Path(td, "scenes.json")
        cp.write_text(json.dumps(CTX), encoding="utf-8")
        sp.write_text(json.dumps(scenes), encoding="utf-8")
        plan = tc.plan_dviet_kinetic_beat_schedule(BEATS, None, workspace_context=str(cp), scenes=sp)
    for b in plan["beats"]:
        mid = b["at"] + 0.5 * b["dur"]
        if b["at"] >= 7.0 and b["at"] + b["dur"] <= 14.5:
            assert b["face_visible"] is False, b
        elif mid < 7.0 or mid > 14.5:
            assert b["face_visible"] is True and b["rail"] != "chest_tactile_rail", b
        assert not _overlaps_band(b["ink_bbox_screen"]), b
    assert plan["stats"]["chest_rail_face_beats"] == 0
    print("[PASS] 03 scenes: chest rail forbidden in P/S scenes, allowed in A2 B-roll, band always cleared")


def test_04_resolver_can_forbid_chest() -> None:
    r = tc.resolve_dual_rail_safe_y(hair_top_y=500.0, chin_y=1300.0, preferred_rail="chest", allow_chest_rail=False)
    assert r["rail"] != "chest_tactile_rail", r
    r2 = tc.resolve_dual_rail_safe_y(hair_top_y=768.0, chin_y=1392.0, preferred_rail="chest")
    assert r2["rail"] == "chest_tactile_rail", "default unchanged"
    print("[PASS] 04 resolve_dual_rail_safe_y(allow_chest_rail=False) never picks the chest rail")


def _css_block(html_doc: str, cls: str) -> str:
    m = re.search(r"\." + re.escape(cls) + r"\s*\{([^}]*)\}", html_doc)
    assert m, cls
    return m.group(1)


def test_05_whisper_and_kt10_legible_and_complete() -> None:
    props = {"mode": "whisper", "main_text": "chụp vội", "accent_text": "trên bàn làm việc"}
    doc = wpb.build_template_html("kt12_whisper_or_directional_echo", props)
    blk = _css_block(doc, "kt12-whisper-line")
    weight = int(re.search(r"font-weight:\s*(\d+)", blk).group(1))
    assert weight >= 600, blk
    shadow = re.search(r"text-shadow:\s*([^;]+);", blk).group(1)
    alphas = [float(a) for a in re.findall(r"rgba\(0,\s*0,\s*0,\s*([0-9.]+)\)", shadow)]
    assert alphas and max(alphas) >= 0.8, f"dark halo expected over A-roll: {shadow}"
    assert wpb.kt_dropped_text("kt12_whisper_or_directional_echo", props) == []
    p10 = {"main_text": "3 bước", "accent_text": "khoá ảnh sản phẩm", "jewel_accent": "emerald"}
    assert wpb.kt_dropped_text("kt10_cursor_bars_pillar_gate", p10) == []
    print(f"[PASS] 05 kt12 whisper weight {weight}, halo alpha {max(alphas)}, accent drawn; kt10 accent drawn")


def test_06_dropped_text_detected_and_batch_refuses() -> None:
    props = {"mode": "tilt", "kicker": "chạm", "main_text": "đúng nhịp", "accent_text": "cảm xúc thật"}
    dropped = wpb.kt_dropped_text("kt11_cranial_svg_arc_or_tilt", props)
    assert [d["field"] for d in dropped] == ["accent_text"], dropped
    with tempfile.TemporaryDirectory() as td:
        job = {"template": "kt11_cranial_svg_arc_or_tilt", "props": props, "out": f"{td}/a.mov", "duration_sec": 1.0}
        try:
            wpb.render_kinetic_typo_batch([job], quiet=True)
        except ValueError as exc:
            assert "allow_drop_accent" in str(exc) and "cảm xúc thật" in str(exc), exc
        else:
            raise AssertionError("a dropped accent_text must fail the batch")
    print("[PASS] 06 kt_dropped_text finds the kt11 tilt accent drop; the batch refuses it")


def test_07_planner_reports_and_fails_on_drop() -> None:
    plan = tc.plan_dviet_kinetic_beat_schedule(BEATS, None, workspace_context=CTX)
    assert plan["stats"]["dropped_text"] == [], plan["stats"]["dropped_text"]
    real = wpb.kt_dropped_text
    wpb.kt_dropped_text = lambda tpl, props: [{"field": "accent_text", "text": props.get("accent_text", "")}] if props.get("accent_text") else []
    try:
        try:
            tc.plan_dviet_kinetic_beat_schedule(BEATS[:2], None)
        except ValueError as exc:
            assert "allow_drop_accent" in str(exc), exc
        else:
            raise AssertionError("planner must fail on a dropped accent_text")
        ok = tc.plan_dviet_kinetic_beat_schedule([dict(b, allow_drop_accent=True) for b in BEATS[:2]], None)
        assert len(ok["stats"]["dropped_text"]) == 2 and ok["batch_jobs"][0]["dropped_text"], ok["stats"]["dropped_text"]
    finally:
        wpb.kt_dropped_text = real
    print("[PASS] 07 planner: dropped_text in stats / job, ValueError unless allow_drop_accent")


def test_08_contrast_helper() -> None:
    white = np.full((1920, 1080, 3), 255, np.uint8)
    black = np.zeros((1920, 1080, 3), np.uint8)
    busy = black.copy()
    busy[:, ::2] = 250
    box = [180, 300, 900, 420]
    assert wpb.text_contrast_ratio(None, box) is None
    assert wpb.text_contrast_ratio(white, box, "#FAFAFA") < 1.2
    assert wpb.text_contrast_ratio(black, box, "#FAFAFA") > 15.0
    assert wpb.text_contrast_ratio(busy, box, "#FAFAFA") < 1.5, "busy background judged by its brightest patch"
    assert wpb.text_contrast_ratio(white, box, "#14171F") > 15.0
    print("[PASS] 08 text_contrast_ratio: white/black/busy backgrounds, None without a frame")


def test_09_legibility_contrast_rule() -> None:
    base = {"id": "kt12", "font_px": 72, "t_ms": 0}
    f_err = sr.check_text_legibility([dict(base, contrast=2.5)])
    f_warn = sr.check_text_legibility([dict(base, contrast=4.0)])
    assert [(f["rule"], f["severity"]) for f in f_err] == [("text_contrast", "error")], f_err
    assert [(f["rule"], f["severity"]) for f in f_warn] == [("text_contrast", "warn")], f_warn
    assert sr.check_text_legibility([dict(base, contrast=5.0)]) == [] and sr.check_text_legibility([base]) == []
    print("[PASS] 09 check_text_legibility contrast: < 3:1 error, < 4.5:1 warn, absent = no finding")


def test_10_pip_window_is_an_exclusion_box() -> None:
    import look_s_render as lsr

    assert {k: tuple(v) for k, v in tc.LOOK_S_PIP_RECTS.items()} == lsr.PIP_RECTS, "planner PiP rects mirror the compositor's"
    for pip in ("br", "bl"):
        scenes = [{"start": 0.0, "end": 30.0, "mode": "A2", "pip": pip}]
        plan = tc.plan_dviet_kinetic_beat_schedule(BEATS, None, workspace_context=CTX, scenes=scenes)
        rx0, ry0, rx1, ry1 = lsr.PIP_RECTS[pip]
        for b in plan["beats"]:
            x0, y0, x1, y1 = b["ink_bbox_screen"]
            assert not (x0 < rx1 and x1 > rx0 and y0 < ry1 and y1 > ry0), (pip, b["template"], b["ink_bbox_screen"])
            assert b["face_visible"] is False and not _overlaps_band(b["ink_bbox_screen"]), b
        assert plan["stats"]["pip_intersections"] == 0, plan["stats"]
    dx = tc._shift_clear_of_pip(300.0, 690.0, [lsr.PIP_RECTS["br"]])
    assert dx is not None and abs((690.0 + dx) - (700 - 24)) < 1e-6 and 300.0 + dx >= 50.0, dx
    assert tc._shift_clear_of_pip(50.0, 770.0, [lsr.PIP_RECTS["br"]]) is None, "cannot shift past the 50 px safe zone"
    print("[PASS] 10 H/A2 PiP window (br / bl) never intersected by planned ink; x-shift fallback keeps 24 px gap + 50 px zone")


if __name__ == "__main__":
    test_01_face_zone_scaled_to_sequence()
    test_02_planner_uses_real_face()
    test_03_scenes_decide_face_visibility()
    test_04_resolver_can_forbid_chest()
    test_05_whisper_and_kt10_legible_and_complete()
    test_06_dropped_text_detected_and_batch_refuses()
    test_07_planner_reports_and_fails_on_drop()
    test_08_contrast_helper()
    test_09_legibility_contrast_rule()
    test_10_pip_window_is_an_exclusion_box()
    print("TẤT CẢ ĐẠT (root cause typo v7.9.3)")
