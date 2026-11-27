#!/usr/bin/env python3
"""
Tests for the v7.9.4 pipeline fixes (synthetic media only, fast, no Chrome).

  01 rotation: a stream with a 90 deg display matrix is probed at its display size (fast_studio_compositor.probe_video and
     probe_and_align.probe_single_media, `rotation` reported); a portrait phone A-roll stored landscape + rotate 90 passes the Look S
     geometry check (dry-run exit 0, not 2); a rotated B-roll decoded at the probed size is the autorotated picture, not scrambled
  02 overlays writer: `overlays_from_plan` maps plan_dviet_kinetic_beat_schedule craft_clips / batch_jobs to --overlays rows (src,
     at, dur, cx / cy from motion.position + anchor, orig_w / orig_h from the rendered .typo_meta.json first, scale = motion.scale / 100)
  03 --overlays-from-plan + --emit-overlays + --emit-scenes (dry-run): the emitted overlays are the placed ones and reload through
     --overlays; the emitted scenes carry broll (absolute), broll_ss, cam and reload through load_scenes
  04 segment cache: --alpha-fps is part of the segment hash; a matte whose frames / fps does not cover the A-roll is a warning
  05 plan_broll: the clean pass and the dirty pass each get the full node budget (a dirty-only plan is still found reuse-free)
  06 hook auto: a predicted hook motion still under motion_gate MIN_MEAN_DIFF after the punches is a warning + `motion_below_floor`

Plain asserts with a `__main__` runner: `python3 tests/test_pipeline_v794.py`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable
LSR = TOOLS_DIR / "look_s_render.py"


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, timeout=120, capture_output=True)


def _clip(path: Path, size: str, dur: float = 1.0, audio: bool = True, rotate: int | None = None) -> Path:
    raw = path.with_name(path.stem + "_raw.mp4") if rotate is not None else path
    args = ["-f", "lavfi", "-i", f"testsrc=size={size}:rate=30:duration={dur}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={dur}", "-c:a", "aac", "-shortest"]
    _ff(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(raw))
    if rotate is not None:
        _ff("-display_rotation", str(rotate), "-i", str(raw), "-c", "copy", str(path))
    return path


def _lsr(*args: str) -> tuple[int, dict]:
    r = subprocess.run([PY, str(LSR), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.returncode, {"stdout": r.stdout[-800:], "stderr": r.stderr[-800:]}


def _case(d: Path, scenes: list[dict], aroll: Path, extra_words: int = 0) -> list[str]:
    dur = scenes[-1]["end"]
    (d / "scenes.json").write_text(json.dumps({"look": "S", "duration": dur, "scenes": scenes}), encoding="utf-8")
    (d / "words.json").write_text(json.dumps([[f"w{i}", i * 0.4 + 0.05, i * 0.4 + 0.3] for i in range(int(dur / 0.4) + extra_words)]),
                                  encoding="utf-8")
    return ["--scenes", str(d / "scenes.json"), "--words", str(d / "words.json"), "--aroll", str(aroll), "--work", str(d / "work"),
            "--out", str(d / "master.mp4"), "--dry-run", "--no-hook-motion", "--no-product-safe-text", "--no-broll-artifact-scan"]


def _sc(i: int, t0: float, t1: float, mode: str, **kw) -> dict:
    return {"id": f"T{i}", "start": t0, "end": t1, "mode": mode, "kind": "text", "jewel": "#F5C451", "text": "", **kw}


# ---------------------------------------------------------------------------------------------- (1) rotation
def test_01_rotation_probe_and_decode() -> None:
    import fast_studio_compositor as fsc
    import look_s_render as lsr
    import probe_and_align as pa
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td)
        rot = _clip(d / "rot.mp4", "320x180", rotate=90)
        info = fsc.probe_video(rot)
        assert (info["width"], info["height"]) == (180, 320) and info["rotation"] in (90, 270), info
        assert fsc.probe_video(d / "rot_raw.mp4")["rotation"] == 0
        _, pinfo = pa.probe_single_media(rot)
        assert (pinfo["w"], pinfo["h"]) == (180, 320) and pinfo["rotation"] in (90, 270), pinfo
        # decoded at the probed size = the autorotated picture (not the stored frame bytes reshaped)
        with __import__("contextlib").closing(lsr._ffmpeg_frames(str(rot), 0.0, 1, 30, "", (info["width"], info["height"]))) as it:
            got = next(it).astype(np.int16)
        with __import__("contextlib").closing(lsr._ffmpeg_frames(str(d / "rot_raw.mp4"), 0.0, 1, 30, "", (320, 180))) as it:
            raw = next(it).astype(np.int16)
        err = min(float(np.abs(got - np.rot90(raw, k).astype(np.int16)).mean()) for k in (1, -1))
        assert err < 2.0, err
        # portrait phone A-roll stored landscape (1280x720) + rotate 90 = 720x1280 9:16 -> scaled, not refused
        aroll = _clip(d / "phone.mp4", "1280x720", dur=1.2, rotate=90)
        rc, doc = _lsr(*_case(d, [_sc(0, 0.0, 1.0, "A1")], aroll))
        assert rc == 0 and doc["aroll"]["width"] == 720 and doc["aroll"]["height"] == 1280 and doc["aroll"]["geometry"] == "scale", (rc, doc)
    print("[PASS] 01 rotation: display size probed (compositor + probe_and_align), rotated phone A-roll accepted, decode consistent")


# ---------------------------------------------------------------------------------------------- (2) overlays writer
def _fake_plan(d: Path) -> Path:
    plates = d / "plates"
    plates.mkdir()
    for n in ("kt_01_kt01.mov", "kt_02_kt05.mov"):
        (plates / n).write_bytes(b"\0")
    (plates / "kt_01_kt01.mov.typo_meta.json").write_text(json.dumps({"width": 1080, "height": 400}), encoding="utf-8")
    clip = lambda src, at, dur, pos, anchor, scale, ph: {  # noqa: E731
        "name": src, "src": src, "in": 0.0, "at": at, "dur": dur, "motion": {"anchor": anchor, "position": pos, "scale": scale},
        "typo_kinetic_meta": {"plate_width": 1080, "plate_height": ph}}
    plan = {"version": "7.1", "fps": 60,
            "craft_clips": [clip("plates/kt_01_kt01.mov", 0.1, 0.9, [540.0, 354.4], [540.0, 220.0], 100.0, 440),
                            clip("plates/kt_02_kt05.mov", 1.2, 0.8, [500.0, 1391.2], [540.0, 170.0], 80.0, 340)],
            "batch_jobs": [{"out": "plates/kt_01_kt01.mov", "meta_out": "plates/kt_01_kt01.mov.typo_meta.json", "width": 1080, "height": 440},
                           {"out": "plates/kt_02_kt05.mov", "meta_out": "plates/kt_02_kt05.mov.typo_meta.json", "width": 1080, "height": 340}]}
    p = d / "plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    return p


def test_02_overlays_from_plan() -> None:
    import look_s_render as lsr
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td)
        p = _fake_plan(d)
        ovs = lsr.overlays_from_plan(json.loads(p.read_text(encoding="utf-8")), d)
        assert len(ovs) == 2, ovs
        a, b = ovs
        assert a["src"] == str(d / "plates/kt_01_kt01.mov") and (a["at"], a["dur"]) == (0.1, 0.9), a
        assert (a["orig_w"], a["orig_h"]) == (1080, 400), a                 # rendered meta wins over plate_height 440
        assert (a["cx"], a["cy"], a["scale"]) == (540.0, 334.4, 1.0), a   # anchor y 220 vs the 400 px plate centre 200: -20
        assert (b["orig_w"], b["orig_h"]) == (1080, 340) and b["scale"] == 0.8, b       # no meta -> plate_height
        assert (b["cx"], b["cy"]) == (500.0, 1391.2), b
        # batch_jobs only (no craft_clips): pos + width / height
        jobs = {"batch_jobs": [{"out": "plates/kt_02_kt05.mov", "at": 2.0, "dur": 1.0, "pos": [540.0, 900.0], "width": 1080, "height": 340}]}
        (o,) = lsr.overlays_from_plan(jobs, d)
        assert (o["cx"], o["cy"], o["orig_h"], o["scale"], o["at"]) == (540.0, 900.0, 340, 1.0, 2.0), o
        try:
            lsr.overlays_from_plan({"craft_clips": []}, d)
            raise AssertionError("an empty plan must be an InputError")
        except lsr.InputError:
            pass
    print("[PASS] 02 overlays_from_plan: craft_clips / batch_jobs -> overlays (meta height, anchor, scale)")


# ---------------------------------------------------------------------------------------------- (3) CLI writer + mirror emit
def test_03_cli_overlays_from_plan_and_emit() -> None:
    import look_s_render as lsr
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td)
        r = subprocess.run([PY, str(LSR), "--help"], capture_output=True, text=True, timeout=60)
        for flag in ("--overlays-from-plan", "--emit-overlays", "--emit-scenes"):
            assert flag in r.stdout, flag
        plan = _fake_plan(d)
        aroll = _clip(d / "aroll.mp4", "540x960", dur=3.2)
        broll = d / "broll"
        broll.mkdir()
        _clip(broll / "b1.mp4", "320x180", dur=3.0, audio=False)
        base = _case(d, [_sc(0, 0.0, 1.5, "H"), _sc(1, 1.5, 3.0, "A1")], aroll) + ["--broll-dir", str(broll)]
        rc, doc = _lsr(*base, "--overlays-from-plan", str(plan), "--overlays", str(plan))
        assert rc == 2, (rc, doc)                                            # mutually exclusive
        eo, es = d / "out_overlays.json", d / "out_scenes.json"
        rc, doc = _lsr(*base, "--overlays-from-plan", str(plan), "--emit-overlays", str(eo), "--emit-scenes", str(es))
        assert rc == 0 and doc["overlays"] == 2 and doc["emitted"] == {"overlays": str(eo), "scenes": str(es)}, (rc, doc)
        em = json.loads(eo.read_text(encoding="utf-8"))
        assert [o["src"] for o in em["overlays"]] == [str(d / "plates/kt_01_kt01.mov"), str(d / "plates/kt_02_kt05.mov")], em
        rc2, doc2 = _lsr(*base, "--overlays", str(eo))
        assert rc2 == 0 and doc2["overlays"] == 2, (rc2, doc2)
        sd = json.loads(es.read_text(encoding="utf-8"))
        h, a1 = sd["scenes"]
        assert sd["look"] == "S" and sd["duration"] == 3.0, sd
        assert h["broll"] == str((broll / "b1.mp4").resolve()) and h["broll_ss"] == 0.0 and h["cam"] == [1.0, 1.06], h
        assert a1["cam"] == [0.96, 0.99] and "broll" not in a1 and "broll_info" not in h and "segment" not in h, a1
        dur, loaded = lsr.load_scenes(es)
        assert dur == 3.0 and [s["id"] for s in loaded] == ["T0", "T1"], loaded
    print("[PASS] 03 CLI: --overlays-from-plan (exclusive with --overlays), --emit-overlays reloads, --emit-scenes carries broll / ss / cam")


# ---------------------------------------------------------------------------------------------- (4) segment cache
def test_04_alpha_fps_in_hash_and_mismatch_warning() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td)
        aroll = _clip(d / "aroll.mp4", "540x960", dur=2.0)
        npy = d / "alpha.npy"
        np.save(npy, np.zeros((60, 32, 18), np.uint8))                      # 60 frames = 2.0 s at 30 fps
        base = _case(d, [_sc(0, 0.0, 1.0, "B"), _sc(1, 1.0, 2.0, "A1")], aroll) + ["--alpha-npy", str(npy)]
        rc, a = _lsr(*base, "--alpha-fps", "30")
        assert rc == 0 and not any("alpha matte" in w for w in a["warnings"]), (rc, a)
        rc, b = _lsr(*base, "--alpha-fps", "25")
        assert rc == 0, (rc, b)
        assert a["scenes"][0]["segment"] != b["scenes"][0]["segment"], "alpha fps must change the B segment hash"
        assert a["scenes"][1]["segment"] == b["scenes"][1]["segment"], "A1 needs no matte: its hash must not change"
        assert any("alpha matte" in w and "A-roll" in w for w in b["warnings"]), b["warnings"]
    print("[PASS] 04 --alpha-fps hashed into matte segments; frames / fps vs A-roll mismatch warned")


# ---------------------------------------------------------------------------------------------- (5) plan_broll budget
def test_05_plan_broll_budget_per_pass() -> None:
    import look_s_render as lsr
    needs = [{"id": f"s{i}", "dur": 1.0, "file": None, "ss": None} for i in range(5)] + [{"id": "s5", "dur": 1.0, "file": "X", "ss": None}]
    lengths = {"A": 10.0, "B": 10.0, "C": 10.0, "X": 10.0}
    spans = {"X": [(0.0, 10.0)]}                                             # X has no clean window: only the dirty pass can place s5
    res = lsr.plan_broll(needs, lengths, ["A", "B", "C"], spans, max_nodes=60)   # clean pass alone visits > 60 nodes
    assert res["reuse_free"] is True and res["placements"]["s5"]["file"] == "X", res
    print("[PASS] 05 plan_broll: the dirty pass gets its own node budget (reuse-free plan found)")


# ---------------------------------------------------------------------------------------------- (6) hook floor warning
def test_06_hook_motion_below_floor_warning() -> None:
    import look_s_render as lsr
    import motion_gate as mg
    orig = (lsr.measure_hook_source, lsr.predict_hook_motion)
    args = argparse.Namespace(no_hook_motion=False, no_product_safe_text=True, no_stage_fallback=False)
    words = [[f"w{i}", i * 0.4 + 0.05, i * 0.4 + 0.3] for i in range(8)]
    try:
        lsr.measure_hook_source = lambda *a, **k: {"mean_diff": 0.3, "static": True, "product": {"bbox": [380, 640, 700, 1500], "method": "x"}}
        for pred, below in ((0.9, True), (mg.MIN_MEAN_DIFF + 0.5, False)):
            lsr.predict_hook_motion = lambda *a, _p=pred, **k: _p
            sc = {"id": "H0", "mode": "H", "t0": 0.0, "t1": 2.4, "broll_src": "x.mp4", "broll_ss": 0.0,
                  "broll_info": {"width": 1080, "height": 1920}}
            warnings: list[str] = []
            info, _ = lsr._hook_auto([sc], [], args, warnings, words)
            row = info["scenes"][0]
            assert row["motion"] and row["motion_below_floor"] is below, row
            assert any("H0" in w and "floor" in w for w in warnings) is below, warnings
            assert (info["below_floor_scenes"] == ["H0"]) is below, info
    finally:
        lsr.measure_hook_source, lsr.predict_hook_motion = orig
    print("[PASS] 06 hook auto: predicted motion still under the floor after punches -> warning + motion_below_floor")


def test_07_overlays_from_plan_trims_overlap() -> None:
    import look_s_render as lsr
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td)
        plan = {"batch_jobs": [{"out": "plates/a.mov", "at": 0.10, "dur": 0.93, "pos": [540.0, 354.4], "width": 1080, "height": 440},
                               {"out": "plates/b.mov", "at": 0.85, "dur": 0.82, "pos": [540.0, 354.4], "width": 1080, "height": 460}]}
        a, b = lsr.overlays_from_plan(plan, d)
        assert abs(a["at"] + a["dur"] - b["at"]) < 1e-6 and b["dur"] == 0.82, (a, b)   # kt_01 / kt_02 case from the e2e plan
    print("[PASS] 07 overlays_from_plan trims overlapping plates like spec_from_plan (no two texts stacked)")


def test_08_overlays_from_plan_cwd_relative_src() -> None:
    import os
    import look_s_render as lsr
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td); (d / "work/plates").mkdir(parents=True); (d / "work/plates/a.mov").write_bytes(b"x")
        plan = {"batch_jobs": [{"out": "work/plates/a.mov", "at": 0.1, "dur": 0.5, "pos": [540.0, 354.4], "width": 1080, "height": 440}]}
        old = os.getcwd(); os.chdir(d)
        try:
            (o,) = lsr.overlays_from_plan(plan, d / "work")       # plan saved in work/, src relative to the cwd
            assert Path(o["src"]).is_absolute() and Path(o["src"]).is_file(), o
            ovs, _ = lsr._check_overlays([dict(o)], [], d / "work")  # no second prefix
            assert Path(ovs[0]["src"]).is_file(), ovs
        finally:
            os.chdir(old)
    print("[PASS] 08 overlays_from_plan resolves cwd-relative plate paths once (no work/work/... prefix)")


def test_09_spec_from_plan_resolves_cwd_relative_plates() -> None:
    import os
    import spec_from_plan as sfp
    with tempfile.TemporaryDirectory(prefix="pfd794_") as td:
        d = Path(td); (d / "work/plates").mkdir(parents=True); (d / "work/plates/a.mov").write_bytes(b"x")
        old = os.getcwd(); os.chdir(d)
        try:   # plan in work/, plate path relative to the cwd -> must resolve (was: native text proxy fallback)
            got = sfp._resolve_plate("work/plates/a.mov", d / "work", d / "work")
            assert got is not None and got.is_file(), got
        finally:
            os.chdir(old)
    print("[PASS] 09 spec_from_plan resolves cwd-relative kt plates (no silent text-proxy fallback)")


if __name__ == "__main__":
    test_01_rotation_probe_and_decode()
    test_02_overlays_from_plan()
    test_03_cli_overlays_from_plan_and_emit()
    test_04_alpha_fps_in_hash_and_mismatch_warning()
    test_05_plan_broll_budget_per_pass()
    test_06_hook_motion_below_floor_warning()
    test_07_overlays_from_plan_trims_overlap()
    test_08_overlays_from_plan_cwd_relative_src()
    test_09_spec_from_plan_resolves_cwd_relative_plates()
    print("TẤT CẢ ĐẠT (pipeline v7.9.4)")
