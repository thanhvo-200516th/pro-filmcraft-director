#!/usr/bin/env python3
"""
Root-cause fixes v7.9.3 for compile_and_verify (studio_14 loudness / voice peak, Gate 5 plate ink + face windows, Gate 3B scale,
SFX clipping window).

  01 studio_14 default limiter = `limiter_db_v793` (-1.3 dB, inside the -1.2 dBTP ceiling); `limiter_db` kept; --limiter wins
  02 the initial voice pre-trim is clamped so the planned voice peak stays inside the rules' voice_peak_dbfs window
  03 post-pass-1 voice-peak retrim: brings a FAIL voice peak back inside the window without leaving target +/- 0.45 LU
  04 V2 plate ink is measured from the plate alpha and projected through motion (anchor / position / scale)
  05 Gate 5 audits V2 plates with their real ink and honours motion.scale (SAFE_ZONE)
  06 Gate 5 FACE_ROOM only where the face is visible: --scenes modes (P/B/S/A1/N full, H/A2 only the PiP rect), meta.face_windows
  07 Gate 5 flags a V2 plate replaced by a text proxy and audits the plate's real ink instead of the PIL proxy
  08 Gate 3B (cranial) honours motion.scale when the plate carries ink_bbox_screen
  09 audit_sfx measures only the used window [sourceIn, sourceIn + duration] (whole-file peak gave false clipping)
  10 --help lists --scenes; main() wires the voice pre-trim clamp and the voice-peak retrim

Synthetic inputs only (ffmpeg lavfi). Plain asserts with a `__main__` runner.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import compile_and_verify as cv  # noqa: E402

PY = sys.executable
VENDOR_DIR = SKILL_ROOT / "scripts" / "vendor" / "ovs_core"
AUDIT_SFX_TH = VENDOR_DIR / "scripts" / "apps" / "talking-head-premiere" / "scripts" / "audit_sfx.py"


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True, timeout=120)


def _alpha_plate(path: Path, w: int, h: int, box: tuple[int, int, int, int], dur: float = 1.0) -> Path:
    """qtrle ARGB plate: opaque white inside box (x0, y0, x1, y1 exclusive), transparent elsewhere."""
    x0, y0, x1, y1 = box
    a_expr = f"if(between(X\\,{x0}\\,{x1 - 1})*between(Y\\,{y0}\\,{y1 - 1})\\,255\\,0)"
    _ffmpeg("-f", "lavfi", "-i", f"color=c=white:s={w}x{h}:d={dur}:r=10,format=rgba,geq=r=255:g=255:b=255:a='{a_expr}'",
            "-c:v", "qtrle", "-pix_fmt", "argb", str(path))
    return path


def _near(a, b, tol: float = 1.5) -> bool:
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _parse(argv: list[str]):
    old = sys.argv
    sys.argv = ["compile_and_verify.py", *argv]
    try:
        return cv.parse_args()
    finally:
        sys.argv = old


# ---------------------------------------------------------------------------------------------- (1) limiter
def test_01_studio_14_default_limiter() -> None:
    s14 = cv.resolve_audio_profile("studio_14")
    assert s14["limiter_db"] == -2.2, "presets are additive: limiter_db stays"
    assert s14["limiter_db_v793"] == -1.3 and s14["limiter_db_v793"] < s14["true_peak_dbtp"]
    assert cv.profile_limiter_db(s14) == -1.3
    assert cv.profile_limiter_db(cv.resolve_audio_profile("platform")) == -2.2
    assert cv.profile_limiter_db(cv.resolve_audio_profile("tiktok_loud")) == -1.2
    base = ["--spec", "x.json", "--out", "x.fcproj", "--work", "w"]
    assert _parse([*base, "--audio-profile", "studio_14"]).limiter == -1.3
    assert _parse([*base, "--audio-profile", "studio_14", "--limiter", "-2.0"]).limiter == -2.0
    assert _parse(base).limiter == -2.2
    print("[PASS] 01 studio_14 default limiter -1.3 dB (limiter_db_v793); --limiter still wins")


# ---------------------------------------------------------------------------------------------- (2) voice pre-trim
def test_02_voice_pretrim_clamped() -> None:
    with tempfile.TemporaryDirectory() as td:
        rules = cv.build_effective_rules(Path(td), -14.0, "studio_14")
        vp = json.loads(Path(rules).read_text(encoding="utf-8"))["params"]["audio"]["voice_peak_dbfs"]
        shift = cv._lufs_target_shift("studio_14", -14.0)
        init_vb = round(-0.72 + shift, 2)
        assert init_vb == 1.28
        trim = cv.voice_pretrim_db(rules, init_vb)
        assert float(vp["target"]) + trim <= float(vp["max"]) - 0.08 + 1e-9, (trim, vp)
        assert trim == round(float(vp["max"]) - 0.08 - float(vp["target"]), 2)
        tl = cv.build_effective_rules(Path(td), -12.0, "tiktok_loud")
        assert cv.voice_pretrim_db(tl, -0.72) == -0.72
    assert cv.voice_pretrim_db(cv.DEFAULT_RULES_JSON, -0.72) == -0.72
    print("[PASS] 02 voice pre-trim clamped to the voice_peak window (+1.28 -> +0.92 on studio_14)")


# ---------------------------------------------------------------------------------------------- (3) voice-peak retrim
def test_03_voice_peak_retrim() -> None:
    with tempfile.TemporaryDirectory() as td:
        rules = cv.build_effective_rules(Path(td), -14.0, "studio_14")
        hot = [{"id": "voice_peak", "status": "FAIL", "value": -2.72, "rule": "-5.0 … -3.0 dBFS"}]
        assert cv.voice_peak_retrim_delta(hot, rules, -14.0, -14.0) == -0.36
        assert cv.voice_peak_retrim_delta(hot, rules, -14.3, -14.0) == -0.15  # stays inside -14 +/- 0.45 LU
        quiet = [{"id": "voice_peak", "status": "FAIL", "value": -5.3}]
        assert cv.voice_peak_retrim_delta(quiet, rules, -14.0, -14.0) == 0.38
        ok = [{"id": "voice_peak", "status": "PASS", "value": -3.4}]
        assert cv.voice_peak_retrim_delta(ok, rules, -14.0, -14.0) == 0.0
        assert cv.voice_peak_retrim_delta([], rules, -14.0, -14.0) == 0.0
        assert cv.voice_peak_retrim_delta(hot, rules, float("-inf"), -14.0) == 0.0
    print("[PASS] 03 voice-peak retrim inside the loudness tolerance")


# ---------------------------------------------------------------------------------------------- (4) plate ink
def test_04_plate_ink_from_alpha() -> None:
    with tempfile.TemporaryDirectory() as td:
        plate = _alpha_plate(Path(td) / "kt_01_kt01.mov", 400, 200, (100, 50, 300, 150))
        clip = {"src": str(plate), "at": 0.0, "dur": 1.0,
                "motion": {"anchor": [200.0, 100.0], "position": [540.0, 960.0], "scale": 50.0}}
        box = cv.measure_plate_ink_bbox(clip, 0.2)
        assert box is not None and _near(box, (490, 935, 590, 985)), box
        bare = {"src": str(plate), "at": 0.0, "dur": 1.0}
        assert _near(cv.measure_plate_ink_bbox(bare, 0.2), (440, 910, 640, 1010)), cv.measure_plate_ink_bbox(bare, 0.2)
        assert cv.measure_plate_ink_bbox({**clip, "opacity": 10.0}, 0.2) is None
        assert cv.measure_plate_ink_bbox({"src": str(Path(td) / "missing.mov"), "dur": 1.0}, 0.2) is None
    print("[PASS] 04 plate ink from alpha, projected through motion")


def _aroll_spec(extra_tracks: list[dict], dur: float = 10.0, meta: dict | None = None) -> dict:
    return {"width": 1080, "height": 1920, "fps": 30.0, "duration": dur, "meta": meta or {},
            "tracks": [{"name": "V1 · A-roll", "type": "video",
                        "clips": [{"name": "A-roll", "src": "/nonexistent/aroll.mp4", "at": 0.0, "dur": dur}]},
                       *extra_tracks]}


_CTX = {"subject_framing": {"face_bbox_norm": [0.3, 0.2, 0.7, 0.45]}}  # face 324..756 x 384..864, mouth band y 720..816


def _gate5(spec: dict, td: str, **kw) -> dict:
    qd = Path(td) / "qa"
    qd.mkdir(exist_ok=True)
    return cv.run_full_visual_rigor_gate5(spec=spec, qa_frames_dir=qd, planned_16=[], context_doc=_CTX, **kw)


# ---------------------------------------------------------------------------------------------- (5) gate 5 plates
def test_05_gate5_plate_real_ink_and_scale() -> None:
    with tempfile.TemporaryDirectory() as td:
        plate = _alpha_plate(Path(td) / "kt_01_kt01.mov", 1080, 200, (340, 40, 740, 160), dur=2.0)
        cl = {"name": "KT01 · kt01 · x", "src": str(plate), "at": 2.0, "dur": 2.0,
              "motion": {"anchor": [540.0, 100.0], "position": [540.0, 354.4], "scale": 100.0}}
        spec = _aroll_spec([{"name": "V2 · Kinetic", "type": "video", "clips": [cl]}])
        res = _gate5(spec, td)
        assert res["plate_clips_audited"] == 1, res
        assert not res["safe_zone_warnings"], res["safe_zone_warnings"]  # 1080-wide plate, 400 px of real ink
        big = _aroll_spec([{"name": "V2 · Kinetic", "type": "video",
                            "clips": [{**cl, "motion": {**cl["motion"], "scale": 300.0}}]}])
        res2 = _gate5(big, td)
        assert len(res2["safe_zone_warnings"]) == 1 and res2["safe_zone_warnings"][0]["source"] == "plate_alpha", res2
    print("[PASS] 05 Gate 5 measures V2 plates from alpha and honours motion.scale")


# ---------------------------------------------------------------------------------------------- (6) face windows
def test_06_face_room_only_where_face_visible() -> None:
    def txt(at: float, y: float, x: float = 450.0, text: str = "chạm miệng") -> dict:
        return {"name": f"T{at:g}", "text": text, "font": "Be Vietnam Pro", "size": 60, "position": [x, y], "at": at, "dur": 1.0}

    texts = {"name": "V3 · Text", "type": "text", "clips": [txt(2.0, 790.0), txt(6.0, 790.0)]}
    scenes = [{"id": "S1", "start": 0.0, "end": 5.0, "mode": "A2"}, {"id": "S2", "start": 5.0, "end": 10.0, "mode": "P"}]
    with tempfile.TemporaryDirectory() as td:
        legacy = _gate5(_aroll_spec([texts]), td)
        assert sorted(w["at"] for w in legacy["face_room_warnings"]) == [2.0, 6.0], legacy["face_room_warnings"]
        scoped = _gate5(_aroll_spec([texts]), td, scenes=scenes)
        assert [w["at"] for w in scoped["face_room_warnings"]] == [6.0], scoped["face_room_warnings"]
        win = _gate5(_aroll_spec([texts], meta={"face_windows": [[5.0, 10.0]]}), td)
        assert [w["at"] for w in win["face_room_warnings"]] == [6.0], win["face_room_warnings"]
        win2 = _gate5(_aroll_spec([texts], meta={"face_windows": [{"start": 5.0, "end": 10.0}]}), td)
        assert [w["at"] for w in win2["face_room_warnings"]] == [6.0], win2["face_room_warnings"]
        # H / A2: only the PiP rect (Look S br = 700..1012 x 1446..1836) protects the face
        pip = {"name": "V3 · Text", "type": "text", "clips": [txt(2.0, 1620.0, x=856.0, text="PiP")]}
        rp = _gate5(_aroll_spec([pip]), td, scenes=scenes)
        assert [w["band"] for w in rp["face_room_warnings"]] == ["pip_rect"], rp["face_room_warnings"]
        ctx_scenes = cv.run_full_visual_rigor_gate5(spec=_aroll_spec([texts]), qa_frames_dir=Path(td) / "qa", planned_16=[],
                                                    context_doc={**_CTX, "scenes": scenes})
        assert [w["at"] for w in ctx_scenes["face_room_warnings"]] == [6.0], ctx_scenes["face_room_warnings"]
    print("[PASS] 06 FACE_ROOM only where the face is visible (scenes / meta.face_windows / PiP rect)")


# ---------------------------------------------------------------------------------------------- (7) text proxy
def test_07_text_proxy_flagged_and_plate_ink_used() -> None:
    with tempfile.TemporaryDirectory() as td:
        p1 = _alpha_plate(Path(td) / "kt_01_kt01.mov", 1080, 200, (340, 40, 740, 160))
        _alpha_plate(Path(td) / "kt_11_kt10.mov", 1080, 200, (240, 40, 840, 160))
        v2 = {"name": "V2 · Kinetic", "type": "video",
              "clips": [{"name": "KT01 · kt01 · x", "src": str(p1), "at": 2.0, "dur": 1.0,
                         "motion": {"anchor": [540.0, 100.0], "position": [540.0, 354.4], "scale": 100.0}}]}
        v3 = {"name": "V3 · Text", "type": "text",
              "clips": [{"name": "KT11 · kt10 · 3 bước", "text": "3 bước khoá ảnh sản phẩm", "font": "Be Vietnam Pro",
                         "size": 78, "color": "#FAFAFA", "position": [540.0, 354.4], "at": 5.0, "dur": 2.5}]}
        proxy_ink = cv.measure_text_clip_ink_bbox(v3["clips"][0], 0.3)
        res = _gate5(_aroll_spec([v2, v3]), td)
        prox = res["plate_text_proxies"]
        assert len(prox) == 1 and Path(prox[0]["plate"]).name == "kt_11_kt10.mov", prox
        assert not any(w["clip"].startswith("KT11") for w in res["safe_zone_warnings"]), (proxy_ink, res["safe_zone_warnings"])
        assert _near(prox[0]["ink_bbox"], (240, 294.4, 840, 414.4), 2.0), prox
    print("[PASS] 07 text proxy of a V2 plate flagged; the plate's real ink is audited")


# ---------------------------------------------------------------------------------------------- (8) gate 3B scale
def test_08_gate3b_ink_bbox_screen_honours_scale() -> None:
    def spec_with(scale: float) -> dict:
        plate = {"name": "KT01 · kt01 · plate", "src": "/nonexistent/kt_01_kt01.mov", "at": 3.0, "dur": 2.0,
                 "motion": {"position": [540.0, 1050.0], "scale": scale},
                 "typo_kinetic_meta": {"ink_bbox_screen": [340.0, 1000.0, 740.0, 1100.0], "pos_x": 540.0, "pos_y": 1050.0,
                                       "z_plane": "foreground_over_subject"}}
        return _aroll_spec([{"name": "V2 · Kinetic", "type": "video", "clips": [plate]}],
                           meta={"cranial_zone": {"hair_top_y": 600.0, "chin_y": 900.0, "face_bbox": [300.0, 620.0, 780.0, 900.0]}})
    r100 = cv.audit_cranial_exclusion(spec_with(100.0), tier_used="full")
    r300 = cv.audit_cranial_exclusion(spec_with(300.0), tier_used="full")
    assert r100["foreground_lane_b_plates_audited"] == 1 and not r100["violations"], r100
    assert r300["violations"], r300
    print("[PASS] 08 Gate 3B ink_bbox_screen scaled by motion.scale")


# ---------------------------------------------------------------------------------------------- (9) audit_sfx window
def test_09_audit_sfx_measures_used_window() -> None:
    spec = importlib.util.spec_from_file_location("audit_sfx_th", AUDIT_SFX_TH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "paper.wav"
        _ffmpeg("-f", "lavfi", "-i", "aevalsrc='if(lt(t\\,0.5)\\,1.0\\,0.2)':s=48000:d=1.5", "-c:a", "pcm_f32le", str(wav))
        used = mod.audit([{"path": str(wav), "start": 1.0, "duration": 0.4, "sourceIn": 1.0}], Path(td), 10.0, True)["files"][0]
        assert used["clipping"] is False and abs(used["peak_dbfs"] - (-13.98)) < 0.1, used
        assert used["measured_window"] == [1.0, 1.4], used
        head = mod.audit([{"path": str(wav), "start": 1.0, "duration": 0.4, "sourceIn": 0.0}], Path(td), 10.0, True)["files"][0]
        assert head["clipping"] is True, head
    prov = (VENDOR_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "patched v7.9.3" in prov
    digest = hashlib.sha256(AUDIT_SFX_TH.read_bytes()).hexdigest()
    assert re.search(rf"`scripts/apps/talking-head-premiere/scripts/audit_sfx.py`\s*\|\s*{digest}", prov), "PROVENANCE sha256 drift"
    print("[PASS] 09 audit_sfx measures [sourceIn, sourceIn + duration]; PROVENANCE records the v7.9.3 patch")


# ---------------------------------------------------------------------------------------------- (10) CLI wiring
def test_10_cli_and_main_wiring() -> None:
    r = subprocess.run([PY, str(TOOLS_DIR / "compile_and_verify.py"), "--help"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "--scenes" in r.stdout, r.stdout[-400:]
    src = inspect.getsource(cv.main)
    for needle in ("voice_pretrim_db(", "voice_peak_retrim_delta(", "scenes="):
        assert needle in src, needle
    print("[PASS] 10 --scenes flag; main wires the voice pre-trim clamp, voice-peak retrim and scenes")


if __name__ == "__main__":
    test_01_studio_14_default_limiter()
    test_02_voice_pretrim_clamped()
    test_03_voice_peak_retrim()
    test_04_plate_ink_from_alpha()
    test_05_gate5_plate_real_ink_and_scale()
    test_06_face_room_only_where_face_visible()
    test_07_text_proxy_flagged_and_plate_ink_used()
    test_08_gate3b_ink_bbox_screen_honours_scale()
    test_09_audit_sfx_measures_used_window()
    test_10_cli_and_main_wiring()
    print("TẤT CẢ ĐẠT (root-cause compile v7.9.3)")
