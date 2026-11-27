#!/usr/bin/env python3
"""
Regression tests for the v7.6 code fixes (package P-A): kt05/kt06 demo-text leak, kt05 overflow, `--words` probe doc,
edit_rules scoping under the `dviet` profile, cranial audit through the real V1 motion, matte-model warning.

Plain runnable script: exits non-zero on the first failure. No Chrome / ffmpeg render is started.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
OVS_SCRIPTS = SCRIPTS_DIR / "vendor" / "ovs_core" / "scripts"

for p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import web_plate_builder as wpb  # noqa: E402
import typography_composer as tc  # noqa: E402
import compile_and_verify as cav  # noqa: E402

KT_TEMPLATES = (
    "kt01_kiss_editorial_2line",
    "kt02_feather_swash_overlap",
    "kt03_per_word_nonlinear_bloom",
    "kt04_ghost_to_focus_stack",
    "kt05_wall_spatial_counterpoint",
    "kt06_bridge_anchor_live_swap",
    "kt07_telescoping_char_rollout",
    "kt08_mist_evaporation_reveal",
    "kt09_strike_myth_laser_2phase",
    "kt10_cursor_bars_pillar_gate",
    "kt11_cranial_svg_arc_or_tilt",
    "kt12_whisper_or_directional_echo",
)
LEAKED = ("chỉ một", "ánh sáng phẳng", "điểm chạm sáng", "tách khối thật", "màu da thật", "ánh mắt sống", "chiều sâu thật", "giữ trọn")


def _load_script(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.append(str(path.parent))  # vendored scripts import their siblings (style_profile, th_transitions)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_01_kt05_only_main_text_has_no_demo_copy() -> None:
    props = {"main_text": "bình luận"}
    html = wpb.build_template_html("kt05_wall_spatial_counterpoint", props)
    for leak in LEAKED:
        assert leak not in html, f"kt05 leaked demo text {leak!r}"
    assert "bình luận" in html
    assert wpb._extract_plain_hero_text("kt05_wall_spatial_counterpoint", props) == "bình luận"
    wall = wpb.build_template_html("kt05_wall_spatial_counterpoint", {"mode": "wall_hop", "main_text": "prompt"})
    assert "chỉ một" not in wall and "điểm chạm sáng" not in wall
    # plain_hero_text reports every rendered clause (left + right + accent) so Gate 3C / R200 see it
    full = wpb._extract_plain_hero_text(
        "kt05_wall_spatial_counterpoint", {"kicker": "mắc bệnh", "main_text": "sử dụng AI", "accent_text": "không thật"}
    )
    for tok in ("mắc bệnh", "sử dụng AI", "không thật"):
        assert tok in full, f"plain_hero_text {full!r} misses rendered clause {tok!r}"
    print("[PASS] 01 kt05: only main_text renders no demo clause; plain_hero_text reports left + right + accent")


def test_02_kt06_plain_string_swaps() -> None:
    props = {"swap_words": ["bình luận", "Prompt"]}
    html = wpb.build_template_html("kt06_bridge_anchor_live_swap", props)
    assert "bình luận" in html and "Prompt" in html
    for leak in LEAKED:
        assert leak not in html, f"kt06 leaked demo text {leak!r}"
    swaps = wpb._normalize_kt06_swaps(props, "gold")
    assert [s["text"] for s in swaps] == ["bình luận", "Prompt"]
    assert wpb._extract_plain_hero_text("kt06_bridge_anchor_live_swap", props) == "bình luận / Prompt"
    only_main = wpb.build_template_html("kt06_bridge_anchor_live_swap", {"main_text": "bình luận"})
    assert "màu da thật" not in only_main and "ánh mắt sống" not in only_main and "giữ trọn" not in only_main
    print("[PASS] 02 kt06: plain-string swap_words render, no demo anchor / swaps")


def test_03_missing_required_prop_raises_with_demo_escape() -> None:
    for tpl in KT_TEMPLATES:
        try:
            wpb.build_template_html(tpl, {})
        except ValueError as exc:
            assert tpl in str(exc), f"error for {tpl} must name the template: {exc}"
        else:
            raise AssertionError(f"{tpl} rendered with no text props (silent demo default)")
        html = wpb.build_template_html(tpl, {"demo": True})
        assert "<html" in html.lower()
    for tpl in ("frosted_glass_bento_steps", "skewed_3d_polaroid_trio"):
        try:
            wpb.build_template_html(tpl, {"jewel_accent": "gold"})
        except ValueError as exc:
            assert tpl in str(exc)
        else:
            raise AssertionError(f"{tpl} rendered without steps / captions")
        assert "<html" in wpb.build_template_html(tpl, {"demo": True}).lower()
    steps = [{"num": "01", "title": "A", "desc": "b", "tag": "c"}] * 3
    html = wpb.build_template_html("frosted_glass_bento_steps", {"steps": steps})
    assert "Quy Trình Chuyển Đổi Thực Chiến" not in html and "LỘ TRÌNH CHUẨN STUDIO" not in html
    pol = wpb.build_template_html("skewed_3d_polaroid_trio", {"captions": ["x", "y", "z"]})
    assert "CAM A" not in pol and "BẢN QUAY THÔ GỐC" not in pol
    print("[PASS] 03 every kt01..kt12 + bento + polaroid raise without text, --demo / demo=true escape works")


def test_04_kt05_wall_hop_pos_x_and_clamp() -> None:
    beats = [{"kicker": "mắc bệnh", "main_text": "sử dụng AI khá dài dòng", "accent_text": "không thật", "role": "wall"}]
    for cam in ("center", "left_third", "right_third"):
        plan = tc.plan_dviet_kinetic_beat_schedule(
            [{**beats[0], "cam_mode": cam}], None, cranial_zone={"hair_top_y": 862.0, "chin_y": 1365.0}
        )
        job = plan["batch_jobs"][0]
        assert job["template"] == "kt05_wall_spatial_counterpoint"
        x0, _, x1, _ = job["ink_bbox_screen"]
        assert 48.0 - 0.1 <= x0 and x1 <= 1032.0 + 0.1, f"{cam}: ink bbox {job['ink_bbox_screen']} leaves the [48,1032] safe box"
        assert x1 > x0
        if cam == "center":
            assert abs(job["pos"][0] - 540.0) <= 60.0, f"center framing must keep the plate near x=540, got {job['pos']}"
            assert abs(0.5 * (x0 + x1) - 540.0) <= 140.0
    plan_l = tc.plan_dviet_kinetic_beat_schedule(
        [{**beats[0], "cam_mode": "left_third"}], None, cranial_zone={"hair_top_y": 862.0, "chin_y": 1365.0}
    )
    plan_r = tc.plan_dviet_kinetic_beat_schedule(
        [{**beats[0], "cam_mode": "right_third"}], None, cranial_zone={"hair_top_y": 862.0, "chin_y": 1365.0}
    )
    assert plan_l["batch_jobs"][0]["pos"][0] > plan_r["batch_jobs"][0]["pos"][0]
    print("[PASS] 04 kt05 pos_x follows cam_mode (center=540) and the ink bbox stays inside [48,1032]")


def _small_spec(tmp: Path) -> Path:
    media = tmp / "a.mp4"
    media.write_bytes(b"x")
    spec = {
        "name": "t.craft", "fps": 30, "width": 1080, "height": 1920, "duration": 4.0,
        "tracks": [{"type": "video", "name": "V1 · A-roll", "clips": [
            {"name": "A-roll 1", "src": str(media), "at": 0.0, "dur": 2.0},
            {"name": "A-roll 2", "src": str(media), "at": 2.0, "dur": 2.0},
        ]}],
    }
    sp = tmp / "t.craft.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    return sp


def test_05_words_probe_doc_is_accepted() -> None:
    spec_lint = _load_script(OVS_SCRIPTS / "spec_lint.py", "pfd_spec_lint_v76")
    words = [["xin", 0.1, 0.3], ["chào", 0.3, 0.6], ["các", 0.6, 0.8], ["bạn", 0.8, 1.0]]
    doc = {"version": "7.4.0", "words": words, "words_tl": words, "face_metrics": {}}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sp = _small_spec(tmp)
        wp = tmp / "words_tl.json"
        wp.write_text(json.dumps(doc), encoding="utf-8")
        res = spec_lint.lint(sp, doc)  # must not raise KeyError / TypeError
        assert any(r["id"] == "hook_first_word_late" for r in res)
        only_tl = spec_lint.lint(sp, {"words_tl": words})
        assert any(r["id"] == "hook_first_word_late" for r in only_tl)
        r = subprocess.run([sys.executable, str(OVS_SCRIPTS / "spec_lint.py"), str(sp), "--words", str(wp), "--json"], capture_output=True, text=True)
        assert r.returncode in (0, 2) and r.stdout.strip().startswith("["), f"spec_lint CLI crashed on the dict doc: {r.stderr[-400:]}"
        # compile_and_verify forwards a normalised bare list to spec_lint and edit_rules
        norm = cav.normalize_words_file(wp, tmp / "work")
        assert json.loads(norm.read_text(encoding="utf-8")) == words and norm.parent == tmp / "work"
        bare = tmp / "bare.json"
        bare.write_text(json.dumps(words), encoding="utf-8")
        assert json.loads(cav.normalize_words_file(bare, tmp / "work2").read_text(encoding="utf-8")) == words
        er = subprocess.run([sys.executable, str(OVS_SCRIPTS / "edit_rules.py"), "audit", str(sp), "--words", str(wp), "--json"], capture_output=True, text=True)
        assert er.stdout.strip().startswith("["), f"edit_rules CLI crashed on the dict doc: {er.stderr[-400:]}"
    print("[PASS] 05 --words probe doc (dict with words / words_tl) accepted by spec_lint, edit_rules and compile_and_verify")


def _rules_spec() -> dict:
    return {
        "fps": 30, "width": 1080, "height": 1920, "duration": 6.0,
        "tracks": [{"type": "video", "name": "V1 · A-roll", "clips": [
            {"name": "A-roll 1", "src": "/x/a.mp4", "at": 0.0, "dur": 3.0},
            {"name": "A-roll 2", "src": "/x/a.mp4", "at": 3.0, "dur": 3.0},
        ]}],
    }


def _rule(res: list, startswith: str) -> dict:
    return next(r for r in res if r["rule"].startswith(startswith))


def test_06_edit_rules_scoping_for_dviet() -> None:
    er = _load_script(OVS_SCRIPTS / "edit_rules.py", "pfd_edit_rules_v76")
    spec = _rules_spec()
    base = er.audit_spec(spec)
    c1_default = _rule(base, "Mọi điểm cắt có chuyển cảnh")
    assert c1_default["status"] == "LỖI", "default profile: a bare cut stays LỖI"
    font_default = _rule(base, "Font")
    assert font_default["status"] == "CẢNH BÁO", f"0 countable fonts must be WARN, not LỖI: {font_default}"
    for kwargs in ({"scope": "dviet"}, {"lane_b_plates": True}):
        res = er.audit_spec(spec, **kwargs)
        c1 = _rule(res, "Mọi điểm cắt có chuyển cảnh")
        assert c1["status"] == "CẢNH BÁO" and "ovs C1 not adopted (references/23 decision f)" in c1["detail"], c1
        fo = _rule(res, "Font")
        assert fo["status"] == "CẢNH BÁO" and "ovs C1 not adopted (references/23 decision f)" in fo["detail"], fo
    # 3 countable fonts under dviet are out of the 4-6 band: still a WARN there, LỖI by default
    spec3 = _rules_spec()
    spec3["tracks"].append({"type": "text", "name": "TEXT · a", "clips": [
        {"name": "t", "text": "a", "font": f, "at": 0.0, "dur": 1.0} for f in ("F1", "F2", "F3")]})
    assert _rule(er.audit_spec(spec3), "Font")["status"] == "LỖI"
    assert _rule(er.audit_spec(spec3, scope="dviet"), "Font")["status"] == "CẢNH BÁO"
    r = subprocess.run([sys.executable, str(OVS_SCRIPTS / "edit_rules.py"), "audit", "--help"], capture_output=True, text=True)
    assert "--profile" in r.stdout and "--lane-b-plates" in r.stdout
    # compile_and_verify detects rendered Lane-B plate clips
    plate_spec = _rules_spec()
    plate_spec["tracks"].append({"type": "video", "name": "V6 · Kinetic", "clips": [
        {"name": "KT01 · kt01", "src": "/x/plates/kt_01_kt01.mov", "at": 0.5, "dur": 1.0}]})
    assert cav.spec_has_rendered_plates(plate_spec) and not cav.spec_has_rendered_plates(_rules_spec())
    print("[PASS] 06 edit_rules: dviet / lane-b plates downgrade C1 + Font 4-6 to WARN with note; default unchanged except 0 fonts")


def _cranial_spec() -> dict:
    return {
        "name": "cranial", "fps": 30, "width": 1080, "height": 1920, "duration": 4.0, "meta": {},
        "tracks": [
            {"type": "video", "name": "V1 · A-Roll", "clips": [{
                "name": "A-roll 1", "src": "/nonexistent/rough_cut.mp4", "at": 0.0, "dur": 4.0,
                "motion": {"position": [540.0, 960.0], "scale": 150.0}}]},
            {"type": "text", "name": "TEXT · Hero", "clips": [
                {"name": "Above head", "text": "AI", "font": "Be Vietnam Pro", "size": 60, "position": [540.0, 520.0], "at": 1.8, "dur": 1.2},
                {"name": "On forehead", "text": "AI", "font": "Be Vietnam Pro", "size": 60, "position": [540.0, 900.0], "at": 1.8, "dur": 1.2},
            ]},
        ],
    }


def test_07_cranial_box_uses_face_metrics_through_v1_motion() -> None:
    ctx = {
        "resolution": {"width": 720, "height": 1280},
        "face_metrics": {"hair_top_y_px": 528, "chin_y_px": 917, "face_bbox_px": [237, 665, 483, 917],
                         "face_bbox_norm": [0.3287, 0.5198, 0.671, 0.7163]},
    }
    spec = _cranial_spec()
    res = cav.audit_cranial_exclusion(spec, raw_spec=spec, context_doc=ctx, spec_meta={})
    names = [v["clip"] for v in res["violations"]]
    assert names == ["On forehead"], f"text above the real hair line must pass, text on the forehead must fail: {names}"
    cy0 = res["violations"][0]["cranial_lock_bbox"][1]
    assert 700.0 <= cy0 + 48.0 <= 900.0, f"canvas hair_top should be ~792-880, got {cy0 + 48.0}"
    assert not any(w["code"] == "CRANIAL_NO_DATA" for w in res["warnings"])
    # same numbers without `resolution`: source size is recovered from face_bbox_px / face_bbox_norm
    ctx2 = {"face_metrics": ctx["face_metrics"]}
    res2 = cav.audit_cranial_exclusion(spec, raw_spec=spec, context_doc=ctx2, spec_meta={})
    assert [v["clip"] for v in res2["violations"]] == ["On forehead"]
    # no data at all: an explicit WARN instead of a made-up box
    res3 = cav.audit_cranial_exclusion(spec, raw_spec=spec, context_doc=None, spec_meta={})
    assert res3["status"] == "WARN" and res3["violation_count"] == 0
    assert any(w["code"] == "CRANIAL_NO_DATA" and "no cranial data" in w["message"] for w in res3["warnings"])
    # auto-load: next to --words (probe doc carries face_metrics) or workspace_context.json in the work dir
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        wp = tmp / "words_tl.json"
        wp.write_text(json.dumps({"words": [], "face_metrics": ctx["face_metrics"]}), encoding="utf-8")
        auto = cav.auto_load_face_context(None, tmp / "work", wp)
        assert auto and auto["face_metrics"]["hair_top_y_px"] == 528
        (tmp / "work").mkdir()
        (tmp / "work" / "workspace_context.json").write_text(json.dumps({"subject_framing": ctx["face_metrics"]}), encoding="utf-8")
        wp2 = tmp / "elsewhere" / "w.json"
        auto2 = cav.auto_load_face_context(None, tmp / "work", wp2)
        assert auto2 and cav._face_metrics_of(auto2)["hair_top_y_px"] == 528
        assert cav.auto_load_face_context(tmp / "work" / "workspace_context.json", tmp / "work", wp) is None  # explicit --context wins
    print("[PASS] 07 cranial box: face_metrics projected through the V1 motion (hair ~792), no-data WARN, auto-load")


def test_08_matte_fallback_warns_and_env_status_reports_u2netp() -> None:
    import fast_studio_compositor as fsc
    import env_status

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        bf = home / ".rembg/models/birefnet-portrait/birefnet-portrait.onnx"
        bf.parent.mkdir(parents=True)
        bf.write_bytes(b"x")
        saved = {k: os.environ.pop(k, None) for k in ("PFD_MATTE_MODEL", "U2NETP_ONNX_PATH")}
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                chosen = fsc.resolve_matte_model_path()
            assert chosen == bf
            msg = err.getvalue()
            assert "WARNING" in msg and "u2netp" in msg and "birefnet-portrait" in msg and "30 s" in msg, msg
            u2 = home / ".rembg/models/u2netp/u2netp.onnx"
            u2.parent.mkdir(parents=True)
            u2.write_bytes(b"x")
            err2 = io.StringIO()
            with contextlib.redirect_stderr(err2):
                assert fsc.resolve_matte_model_path() == u2
            assert err2.getvalue() == "", "no warning when u2netp is present"
            u2.unlink()
            env_status.HOME = home
            checks = {c["name"]: c for c in env_status.gather()}
            c = checks["matte_u2netp"]
            assert c["status"] == "MISSING" and c["required"] is False
            assert "studio" in c["detail"] and "u2netp" in c["remedy"]
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
            if old_home is not None:
                os.environ["HOME"] = old_home
    help_txt = fsc._build_arg_parser().format_help()
    assert "plain re-encode" in help_txt and "studio recipe" in help_txt
    print("[PASS] 08 compositor warns loudly on the birefnet fallback; env_status reports u2netp as optional-missing; CLI help is honest")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print("TẤT CẢ ĐẠT (skill v7.6 fixes, P-A)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
