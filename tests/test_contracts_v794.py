#!/usr/bin/env python3
"""
Contract tests for v7.9.4 (workspace_context shape + scene key contract), on the REAL e2e_v791 probe output.

  01 the real raw_video workspace_context (flat `subject_framing`) scales the A-roll face to the sequence (hair 768, chin 1392)
  02 the bundle-mode workspace_context (`subject_framing = {<media path>: {...}}`, probe_and_align bundle writer) picks the
     A-roll entry -- not a B-roll that also shows a face -- and scales it by THAT media's own size (media_probe w/h, else the
     face bbox px / norm), not by `ctx.resolution` (the sequence size)
  03 planner on the real beats / words / scenes with the flat AND the bundle context: cranial `verified`, 0 chest-rail beats
     while the face is visible, 0 PiP intersections
  04 scene rows keyed `t0` / `t1` (look_s_render accepts both) work in typography_composer._scene_spans, the planner and
     compile_and_verify.face_visibility_at
  05 compile_and_verify._extract_context_face_norm (Gate 3B / 5) picks the same A-roll entry as the planner in bundle mode,
     even when a B-roll with a face is listed first

Plain asserts with a `__main__` runner: `python3 tests/test_contracts_v794.py`.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import warnings
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import compile_and_verify as cv  # noqa: E402
import typography_composer as tc  # noqa: E402

warnings.filterwarnings("ignore", message="FONT NOT FOUND")

E2E = Path("/home/vmiz/Thanh/THCN/THÀNH/t/pfd_work/e2e_v791")
REAL_CTX = E2E / "work" / "workspace_context.json"
REAL_SCENES = E2E / "work" / "scenes.json"
REAL_WORDS = E2E / "work" / "words_tl.json"
REAL_BEATS = E2E / "beats.json"  # written by e2e_v791/plan_text.py
HAVE_REAL = all(p.is_file() for p in (REAL_CTX, REAL_SCENES, REAL_WORDS, REAL_BEATS))

AROLL_REL = "a-roll/aroll.mp4"
BROLL_REL = "b-roll/office_broll.mp4"
# a landscape B-roll with a detected face high in frame: if it were used, the band would land far from the speaker's head
BROLL_SF = {"detected": True, "face_bbox_px": [800, 100, 1100, 420], "face_bbox_norm": [0.4167, 0.0926, 0.5729, 0.3889],
            "hair_top_y_px": 60, "chin_y_px": 420,
            "dual_rail_zones": {"chest_tactile_rail": {"y_band_px": [480, 900], "usable": True}}}


def _real_ctx() -> dict:
    return json.loads(REAL_CTX.read_text(encoding="utf-8"))


def _bundle_ctx(tmp: Path, with_probe: bool = True) -> dict:
    """The real A-roll framing re-wrapped the way probe_and_align's bundle writer emits it (B-roll iterated first, sequence
    resolution 1080x1920 from an .fcproj), plus a media_probe.json with each media's own w/h."""
    real = _real_ctx()
    ctx = copy.deepcopy(real)
    ctx["mode"] = "project_dir"
    ctx["resolution"] = {"width": 1080, "height": 1920}
    ctx["subject_framing"] = {BROLL_REL: BROLL_SF, AROLL_REL: real["subject_framing"]}
    probe = tmp / "media_probe.json"
    probe.write_text(json.dumps({BROLL_REL: {"w": 1920, "h": 1080, "category": "video"},
                                 AROLL_REL: {"w": 720, "h": 1280, "category": "video"}}), encoding="utf-8")
    ctx["artifacts"] = {"media_probe": str(probe) if with_probe else str(tmp / "missing_probe.json")}
    return ctx


def _real_plan(ctx, scenes) -> dict:
    words = json.loads(REAL_WORDS.read_text(encoding="utf-8"))
    words = words["words"] if isinstance(words, dict) else words
    beats = json.loads(REAL_BEATS.read_text(encoding="utf-8"))
    return tc.plan_dviet_kinetic_beat_schedule(beats, words, format_mode="F1", industry_skin="S8", fps=60,
                                               workspace_context=ctx, scenes=scenes)


def _assert_face_ok(plan: dict, label: str) -> None:
    st = plan["stats"]
    assert st["cranial_lock_status"] == "verified", (label, st["cranial_lock_status"], st.get("cranial_sources"))
    assert st["chest_rail_face_beats"] == 0, (label, st)
    assert st["pip_intersections"] == 0, (label, st)
    for b in plan["beats"]:
        if b.get("face_visible"):
            assert b["rail"] != "chest_tactile_rail", (label, b)


def test_01_real_flat_context() -> None:
    if not HAVE_REAL:
        print("[SKIP] 01 e2e_v791 real context not on this machine")
        return
    fz = tc.face_zone_from_workspace_context(str(REAL_CTX))
    assert fz is not None
    assert abs(fz["hair_top_y"] - 768.0) < 0.6 and abs(fz["chin_y"] - 1392.0) < 0.6, fz
    assert fz["chest_rail_usable"] is False, fz
    print("[PASS] 01 real raw_video context: hair 768, chin 1392, chest rail unusable")


def test_02_bundle_context_picks_aroll_and_its_size() -> None:
    if not HAVE_REAL:
        print("[SKIP] 02 e2e_v791 real context not on this machine")
        return
    with tempfile.TemporaryDirectory() as td:
        fz = tc.face_zone_from_workspace_context(_bundle_ctx(Path(td)))
        assert fz is not None, "bundle-shaped subject_framing must be unwrapped"
        assert abs(fz["hair_top_y"] - 768.0) < 0.6 and abs(fz["chin_y"] - 1392.0) < 0.6, fz  # 720x1280 A-roll, not 1080x1920
        assert fz["chest_rail_usable"] is False, fz
        fz2 = tc.face_zone_from_workspace_context(_bundle_ctx(Path(td), with_probe=False))
        assert fz2 is not None, "no media_probe -> size from face bbox px / norm"
        assert abs(fz2["hair_top_y"] - 768.0) < 3.0 and abs(fz2["chin_y"] - 1392.0) < 3.0, fz2
    only_broll = {"resolution": {"width": 1080, "height": 1920}, "subject_framing": {BROLL_REL: {"detected": False}}}
    assert tc.face_zone_from_workspace_context(only_broll) is None
    print("[PASS] 02 bundle context: A-roll entry chosen over a face B-roll, scaled by its own 720x1280 (probe or bbox norm)")


def test_03_planner_on_real_inputs() -> None:
    if not HAVE_REAL:
        print("[SKIP] 03 e2e_v791 real inputs not on this machine")
        return
    _assert_face_ok(_real_plan(str(REAL_CTX), str(REAL_SCENES)), "flat")
    with tempfile.TemporaryDirectory() as td:
        _assert_face_ok(_real_plan(_bundle_ctx(Path(td)), str(REAL_SCENES)), "bundle")
    print("[PASS] 03 planner on real beats/words/scenes (flat + bundle ctx): verified, 0 chest-face beats, 0 PiP hits")


def test_04_scene_rows_with_t0_t1() -> None:
    rows = [{"t0": 0.0, "t1": 3.0, "mode": "H", "pip": "bl"}, {"t0": 3.0, "t1": 6.0, "mode": "P"},
            {"start": 6.0, "end": 9.0, "mode": "A2"}]
    assert tc._scene_spans({"scenes": rows}) == [(0.0, 3.0, "H", "bl"), (3.0, 6.0, "P", "br"), (6.0, 9.0, "A2", "br")]
    vis, rect = cv.face_visibility_at(1.0, rows)
    assert vis == "pip" and rect == cv.LOOK_S_PIP_RECTS["bl"], (vis, rect)
    assert cv.face_visibility_at(4.0, rows) == ("full", None)
    assert cv.face_visibility_at(7.0, rows)[0] == "pip"
    if HAVE_REAL:
        real = json.loads(REAL_SCENES.read_text(encoding="utf-8"))
        real["scenes"] = [{**{k: v for k, v in s.items() if k not in ("start", "end")}, "t0": s["start"], "t1": s["end"]}
                          for s in real["scenes"]]
        _assert_face_ok(_real_plan(str(REAL_CTX), real), "t0/t1 scenes")
    print("[PASS] 04 t0/t1 scene rows: _scene_spans, planner and face_visibility_at agree with start/end rows")


def test_05_gate_face_norm_matches_planner_in_bundle_mode() -> None:
    if not HAVE_REAL:
        print("[SKIP] 05 e2e_v791 real context not on this machine")
        return
    aroll_norm = [float(x) for x in _real_ctx()["subject_framing"]["face_bbox_norm"]]
    assert cv._extract_context_face_norm(_real_ctx()) == aroll_norm, "flat context"
    with tempfile.TemporaryDirectory() as td:
        ctx = _bundle_ctx(Path(td))
        assert list(ctx["subject_framing"])[0] == BROLL_REL, "B-roll with a face must be listed first"
        assert cv._extract_context_face_norm(ctx) == aroll_norm, cv._extract_context_face_norm(ctx)
    no_aroll_name = {"subject_framing": {"clip_b.mp4": BROLL_SF, "clip_c.mp4": {"detected": True, "face_bbox_norm": [0, 0, 1, 1]}}}
    assert cv._extract_context_face_norm(no_aroll_name) == BROLL_SF["face_bbox_norm"], "no A-roll name -> first face"
    print("[PASS] 05 Gate 3B/5 face norm = planner's A-roll entry in bundle mode (B-roll face listed first)")


if __name__ == "__main__":
    test_01_real_flat_context()
    test_02_bundle_context_picks_aroll_and_its_size()
    test_03_planner_on_real_inputs()
    test_04_scene_rows_with_t0_t1()
    test_05_gate_face_norm_matches_planner_in_bundle_mode()
    print("TẤT CẢ ĐẠT (contracts v7.9.4)")
