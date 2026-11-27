#!/usr/bin/env python3
"""
Tests for scripts/tools/flicker_schedule.py and the `opener` plan key of spec_from_plan.py (v7.4.0, package PKG-C).

SYNTHETIC data only: numpy frames and ffmpeg `testsrc2` clips of <= 2 s built in a temp dir. No real footage, no
FilmCraft, no project is built or rendered.

Run: python3 tests/test_flicker_schedule.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
FC_BUILD = SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "scripts" / "apps" / "craft-handoff" / "tools" / "fc_build.py"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import flicker_schedule as fs  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
RATES = [(60, 1), (24, 1), (25, 1), (30, 1), (30000, 1001)]
W, H = 360, 640


def _fc_build():
    sp = importlib.util.spec_from_file_location("pfd_fc_build_flicker", FC_BUILD)
    mod = importlib.util.module_from_spec(sp)
    assert sp.loader is not None
    sp.loader.exec_module(mod)
    return mod


def _ff(*args: str) -> None:
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def _raw_frames(cmd_args: list[str], pix_fmt: str, w: int, h: int, channels: int) -> np.ndarray:
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", *cmd_args, "-f", "rawvideo", "-pix_fmt", pix_fmt, "-"],
                       capture_output=True)
    assert r.returncode == 0, r.stderr.decode()[-800:]
    arr = np.frombuffer(r.stdout, dtype=np.uint8)
    return arr.reshape(-1, h, w, channels) if channels > 1 else arr.reshape(-1, h, w)


def _raises(exc: type[BaseException], fn, *a, needle: str = "", **kw) -> BaseException:
    try:
        fn(*a, **kw)
    except exc as e:  # noqa: PERF203
        assert needle.lower() in str(e).lower(), f"error {e!r} lacks {needle!r}"
        return e
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


# ----------------------------------------------------------------------------- 1. schedule
def test_01_schedule_is_frame_exact_and_non_overlapping() -> None:
    fcb = _fc_build()
    expect = ["plate", "silhouette", "silhouette", "silhouette", "plate", "plate", "silhouette", "subject"]
    for num, den in RATES:
        rows = fs.flicker_schedule(num, den)
        rate = fcb.fps_fraction(fs.spec_fps(num, den))
        assert rate.numerator * den == num * rate.denominator, f"fc_build snaps {num}/{den} to {rate}"
        per_frame = [r["state"] for r in rows for _ in range(r["frames"])]
        assert per_frame == expect, (num, den, per_frame)
        assert sum(r["frames"] for r in rows) == 8
        pos = 0
        for r in rows:
            assert r["frame"] == pos and isinstance(r["frames"], int)
            assert fcb.to_frames(r["at"], rate) == pos, (num, den, r)
            assert fcb.to_frames(r["at"] + r["dur"], rate) == pos + r["frames"], (num, den, r)
            pos += r["frames"]
        for a, b in zip(rows, rows[1:]):
            assert abs((a["at"] + a["dur"]) - b["at"]) < 1e-8
        # one track, every state a clip: fc_build must accept it (its overlap rule is the reason for ONE track)
        src = {"plate": "/x/plate.png", "silhouette": "/x/sil.mov", "subject": "/x/subject.mov"}
        errs: list[str] = []
        fcb._check_overlaps("V2", fs.schedule_to_clips(rows, src), errs)
        assert errs == [], errs
    # 60 fps: the opener lasts 8 frames = 0.1333 s
    r60 = fs.flicker_schedule(60, 1)
    assert abs(r60[-1]["at"] + r60[-1]["dur"] - 8 / 60) < 1e-8
    print(f"[PASS] 01 default 8-frame opener is frame-exact and overlap-free at {RATES}")


def test_02_custom_states_and_errors() -> None:
    rows = fs.flicker_schedule(60, 1, [("on", 2), ("off", 2), ("on", 2)], start_frame=10)
    assert [(r["frame"], r["frames"]) for r in rows] == [(10, 2), (12, 2), (14, 2)]
    assert rows[0]["at"] == fs.frame_time(10, 60, 1)
    states_in = [["a", 2], ["b", 1]]
    before = json.dumps(states_in)
    fs.flicker_schedule(30, 1, states_in)
    assert json.dumps(states_in) == before, "input must not be mutated"
    assert fs.flicker_schedule(60, 1) is not fs.flicker_schedule(60, 1)
    _raises(fs.FlickerError, fs.flicker_schedule, 0, 1, needle="fps_num")
    _raises(fs.FlickerError, fs.flicker_schedule, 30, 0, needle="fps_den")
    _raises(fs.FlickerError, fs.flicker_schedule, 29.97, 1, needle="fps_num")
    _raises(fs.FlickerError, fs.flicker_schedule, 60, 1, [("a", 0)], needle="frames")
    _raises(fs.FlickerError, fs.flicker_schedule, 60, 1, [("a", 1.5)], needle="frames")
    _raises(fs.FlickerError, fs.flicker_schedule, 60, 1, [], needle="empty")
    _raises(fs.FlickerError, fs.flicker_schedule, 60, 1, [("", 1)], needle="name")
    _raises(fs.FlickerError, fs.flicker_schedule, 60, 1, [("a", 1)], -1, needle="start_frame")
    rows = fs.flicker_schedule(60, 1)
    _raises(fs.FlickerError, fs.schedule_to_clips, rows, {"plate": "p.png"}, needle="silhouette")
    clips = fs.schedule_to_clips(rows, {"plate": "p.png", "silhouette": "s.mov", "subject": None})
    assert [c["name"].split(" · ")[1] for c in clips] == ["plate f0", "silhouette f1", "plate f4", "silhouette f6"]
    assert all(("in" in c) == ("silhouette" in c["name"]) for c in clips)
    assert all(unicodedata.normalize("NFC", c["name"]) == c["name"] for c in clips)
    print("[PASS] 02 custom states, start_frame, input immutability and clear errors")


# ----------------------------------------------------------------------------- 2. ffmpeg harness
def test_03_ffmpeg_overlay_reproduces_centre_luma_pattern() -> None:
    """References/27 section 3.1: overlay enable='lt(mod(n,4),2)' on a 60 fps testsrc2 clip gives 2 frames of cream
    silhouette luma then 2 frames of plate luma, repeating. Cream luma is 252; the plate value depends on the
    conversion, so it is measured from a plate-only render at the same pixel (and must differ from 252)."""
    cx, cy = W // 2 + 12, H // 2  # a flat region of testsrc2 (x = W/2 sits on a colour-bar edge)
    base = ["-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=60:d=0.2", "-f", "lavfi", "-i", f"color=c=0x{fs.SILHOUETTE_HEX}:s={W}x{H}:r=60:d=0.2"]

    def centre(filter_graph: str) -> list[int]:
        y = _raw_frames([*base, "-filter_complex", filter_graph], "gray", W, H, 1)
        return [int(f[cy, cx]) for f in y]

    plate = centre("[0:v][1:v]overlay=enable=0,format=gray")
    assert len(set(plate)) == 1 and plate[0] != 252, plate
    p = plate[0]
    got = centre("[0:v][1:v]overlay=enable='lt(mod(n,4),2)',format=gray")
    assert got == [252, 252, p, p] * 3, got
    # the same pattern from a schedule: states of 2 frames, enable expression derived from the rows
    rows = fs.flicker_schedule(60, 1, [("silhouette", 2), ("plate", 2)] * 3)
    expr = fs.overlay_enable_expr(rows, "silhouette")
    got2 = centre(f"[0:v][1:v]overlay=enable='{expr}',format=gray")
    assert got2 == got, (expr, got2)
    # the 8-frame opener on the same harness: f1-3 and f6 are the silhouette
    rows8 = fs.flicker_schedule(60, 1)
    got3 = centre(f"[0:v][1:v]overlay=enable='{fs.overlay_enable_expr(rows8, 'silhouette')}',format=gray")
    assert got3 == [p, 252, 252, 252, p, p, 252, p] + [p] * (len(got3) - 8), got3
    _raises(fs.FlickerError, fs.overlay_enable_expr, rows8, "nope", needle="nope")
    print(f"[PASS] 03 ffmpeg testsrc2 360x640@60: centre luma 252,252,{p},{p} repeating; opener frames f1-3 and f6 are silhouette")


def test_04_silhouette_colour_is_exactly_fffbf0() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_sil_") as td:
        td_p = Path(td)
        # synthetic matte: a white rectangle on black, 3 frames as a PNG sequence
        import cv2
        for i in range(3):
            m = np.zeros((H, W), np.uint8)
            m[100 + 10 * i:500, 120:240] = 255
            cv2.imwrite(str(td_p / f"m_{i:04d}.png"), m)
        out = td_p / "sil.mov"
        cmd = fs.silhouette_mov_cmd(str(td_p / "m_%04d.png"), str(out), W, H, 60, 1, codec="qtrle")
        assert "0xFFFBF0" in " ".join(cmd) and cmd[0] == "ffmpeg"
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-600:]
        rgba = _raw_frames(["-i", str(out)], "rgba", W, H, 4)
        assert len(rgba) == 3, len(rgba)
        inside, outside = rgba[0][300, 180], rgba[0][20, 20]
        assert tuple(inside) == (255, 251, 240, 255), tuple(inside)
        assert outside[3] == 0, "outside the matte must stay transparent"
        sel = rgba[2][..., 3] == 255
        assert sel.sum() == (500 - 120) * 120 and set(map(tuple, rgba[2][sel][:, :3])) == {(255, 251, 240)}
        # the deliverable codec (ProRes 4444) goes through YUV: colour within 3 levels, alpha untouched
        pr = td_p / "sil_pr.mov"
        cmd2 = fs.silhouette_mov_cmd(str(td_p / "m_%04d.png"), str(pr), W, H, 60, 1)
        r2 = subprocess.run(cmd2, capture_output=True, text=True)
        assert r2.returncode == 0, r2.stderr[-600:]
        px = _raw_frames(["-i", str(pr)], "rgba", W, H, 4)[0][300, 180]
        assert max(abs(int(a) - b) for a, b in zip(px[:3], (255, 251, 240))) <= 3 and px[3] == 255, tuple(px)
    _raises(fs.FlickerError, fs.silhouette_mov_cmd, "m.png", "o.mov", W, H, 60, 1, color="nothex", needle="hex")
    _raises(fs.FlickerError, fs.silhouette_mov_cmd, "m.png", "o.mov", W, H, 60, 1, codec="gif", needle="codec")
    _raises(fs.FlickerError, fs.silhouette_mov_cmd, "m.png", "o.mov", 0, H, 60, 1, needle="width")
    print("[PASS] 04 silhouette_mov_cmd paints exactly #FFFBF0 (lossless codec) and keeps the alpha")


# ----------------------------------------------------------------------------- 3. clean plate + matte guards
def _moving_square(n: int = 8, size: int = 40) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
    h, w = 120, 200
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.stack([(xx * 255 // w), (yy * 255 // h), ((xx + yy) * 255 // (w + h))], axis=-1).astype(np.uint8)
    frames, alphas = [], []
    for i in range(n):
        x0 = i * (w - size) // (n - 1)
        f = bg.copy()
        a = np.zeros((h, w), np.uint8)
        f[40:40 + size, x0:x0 + size] = (255, 0, 255)
        a[40:40 + size, x0:x0 + size] = 255
        frames.append(f)
        alphas.append(a)
    return bg, frames, alphas


def test_05_clean_plate_median_removes_moving_square() -> None:
    bg, frames, alphas = _moving_square()
    snap_f, snap_a = [f.copy() for f in frames], [a.copy() for a in alphas]
    plate = fs.clean_plate_median(frames, alphas)
    assert plate.shape == bg.shape and plate.dtype == np.uint8
    assert np.array_equal(plate, bg), int(np.abs(plate.astype(int) - bg.astype(int)).max())
    assert all(np.array_equal(a, b) for a, b in zip(frames, snap_f)) and all(np.array_equal(a, b) for a, b in zip(alphas, snap_a)), "inputs mutated"
    assert plate is not frames[0]
    # a subject that never leaves a small area is inpainted (fallback), not left in the plate
    _, frames2, alphas2 = _moving_square()
    for f, a in zip(frames2, alphas2):
        f[10:20, 90:100] = (255, 0, 255)
        a[10:20, 90:100] = 255
    plate2 = fs.clean_plate_median(frames2, alphas2)
    assert not np.any(np.all(plate2[10:20, 90:100] == (255, 0, 255), axis=-1)), "stuck subject must be inpainted away"
    assert np.array_equal(plate2[40:80, 0:80], bg[40:80, 0:80]), "everything else still the exact background"
    # a subject that covers too much of the frame for the whole clip: refuse, do not fake a plate
    full = [np.full((120, 200, 3), 9, np.uint8)] * 3
    covered = [np.full((120, 200), 255, np.uint8)] * 3
    _raises(fs.FlickerError, fs.clean_plate_median, full, covered, needle="never clear")
    _raises(fs.FlickerError, fs.clean_plate_median, full, covered[:2], needle="same")
    print("[PASS] 05 clean_plate_median: exact background from a moving square, inpaint fallback, loud refusal")


def _person_matte(h: int = 640, w: int = 360) -> np.ndarray:
    a = np.zeros((h, w), np.uint8)
    a[160:600, 120:240] = 255  # tall blob, ~16 % coverage
    return a


def test_06_matte_guards_raise_instead_of_degrading() -> None:
    ok = _person_matte()
    fs.check_subject_matte([ok, ok])
    _raises(fs.MatteError, fs.check_subject_matte, [ok, np.zeros_like(ok)], needle="frame 1 is empty")
    _raises(fs.MatteError, fs.check_subject_matte, [], needle="no matte")
    whole = np.full_like(ok, 255)
    _raises(fs.MatteError, fs.check_subject_matte, [whole], needle="whole shot")
    two = ok.copy()
    two[300:600, 10:90] = 255  # a second large subject beside the first
    _raises(fs.MatteError, fs.check_subject_matte, [two], needle="separate blobs")
    sofa = np.zeros_like(ok)
    sofa[400:520, 20:340] = 255  # wide, low object
    _raises(fs.MatteError, fs.check_subject_matte, [sofa], needle="not person-shaped")
    # matte_from_frames: injected predictor, strict input checks
    frames = [np.zeros((H, W, 3), np.uint8)] * 2
    got = fs.matte_from_frames(frames, predict=lambda rgb: np.full(rgb.shape[:2], 7, np.uint8))
    assert len(got) == 2 and got[0].dtype == np.uint8 and int(got[0][0, 0]) == 7
    _raises(fs.FlickerError, fs.matte_from_frames, [np.zeros((4, 4), np.uint8)], predict=lambda x: x, needle="HxWx3")
    _raises(fs.FlickerError, fs.matte_from_frames, frames, predict=lambda rgb: np.zeros((2, 2), np.uint8), needle="shape")
    print("[PASS] 06 empty / whole-frame / overlapping / non-person mattes raise MatteError (no silent degrade)")


def test_07_c_class_asks_are_refused() -> None:
    for name in ("Time Displacement", "slit-scan", "AI Object Mask", "roto brush", "occlusion-aware planar tracking",
                 "planar_tracking", "3D extrude", "extrude_3d"):
        e = _raises(fs.UnsupportedEffectError, fs.refuse_c_class, name, needle="c-class")
        assert "faked" in str(e) or "not implemented" in str(e)
    fs.refuse_c_class("flicker")
    fs.refuse_c_class("rgb_split")
    assert issubclass(fs.UnsupportedEffectError, fs.FlickerError) and issubclass(fs.MatteError, ValueError)
    print("[PASS] 07 Time Displacement, AI Object Mask, occlusion-aware planar tracking, 3D extrude are refused")


# ----------------------------------------------------------------------------- 4. spec_from_plan opener
def _make_assets(td: Path) -> tuple[Path, Path, Path]:
    media = td / "media"
    media.mkdir()
    _ff("-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=60:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2:r=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", media / "a-roll-1.mp4")
    assets = td / "assets"
    assets.mkdir()
    _ff("-f", "lavfi", "-i", f"color=c=0x303030:s={W}x{H}:d=0.1", "-frames:v", "1", assets / "plate.png")
    _ff("-f", "lavfi", "-i", f"color=c=0x{fs.SILHOUETTE_HEX}:s={W}x{H}:r=60:d=2", "-c:v", "qtrle", assets / "silhouette.mov")
    (td / "words.json").write_text("[]", encoding="utf-8")
    return media, assets, td / "words.json"


def _run_spec(td: Path, media: Path, words: Path, plan: dict, name: str, fps: str = "60") -> subprocess.CompletedProcess:
    plan_p = td / f"{name}_plan.json"
    plan_p.write_text(json.dumps(plan), encoding="utf-8")
    return subprocess.run([sys.executable, str(TOOLS_DIR / "spec_from_plan.py"), "--plan", str(plan_p), "--words", str(words),
                           "--media-dir", str(media), "--out", str(td / "out" / f"{name}.craft.json"), "--fps", fps,
                           "--width", str(W), "--height", str(H)], capture_output=True, text=True)


def test_08_spec_from_plan_opener_flicker() -> None:
    fcb = _fc_build()
    with tempfile.TemporaryDirectory(prefix="pfd_open_") as td:
        td_p = Path(td)
        media, assets, words = _make_assets(td_p)
        base = _run_spec(td_p, media, words, {"craft_clips": []}, "base")
        assert base.returncode == 0, base.stderr[-600:]
        base_spec = json.loads((td_p / "out" / "base.craft.json").read_text(encoding="utf-8"))
        assert "opener" not in base_spec["meta"] and all("Opener" not in t["name"] for t in base_spec["tracks"])

        plan = {"craft_clips": [], "opener": {"preset": "flicker", "plate": str(assets / "plate.png"),
                                               "silhouette": str(assets / "silhouette.mov")}}
        r = _run_spec(td_p, media, words, plan, "op")
        assert r.returncode == 0, r.stderr[-800:]
        spec = json.loads((td_p / "out" / "op.craft.json").read_text(encoding="utf-8"))
        track = next(t for t in spec["tracks"] if "Opener" in t["name"])
        assert track["type"] == "video" and track["name"].startswith("V2"), track["name"]
        assert spec["tracks"].index(track) == 1, "the opener sits right above the A-roll"
        assert [t["name"] for t in spec["tracks"] if t is not track] == [t["name"] for t in base_spec["tracks"]], "other tracks unchanged"
        rate = fcb.fps_fraction(60.0)
        got = [(fcb.to_frames(c["at"], rate), fcb.to_frames(c["at"] + c["dur"], rate), Path(c["src"]).name) for c in track["clips"]]
        assert got == [(0, 1, "plate.png"), (1, 4, "silhouette.mov"), (4, 6, "plate.png"), (6, 7, "silhouette.mov")], got
        assert spec["meta"]["opener"] == "flicker"
        fcb.validate(spec)  # accepted by the vendored fc_build validator (overlap rule, key checks)

        # NTSC project rate: still frame-exact
        r2 = _run_spec(td_p, media, words, plan, "ntsc", fps="29.97")
        assert r2.returncode == 0, r2.stderr[-600:]
        s2 = json.loads((td_p / "out" / "ntsc.craft.json").read_text(encoding="utf-8"))
        t2 = next(t for t in s2["tracks"] if "Opener" in t["name"])
        rate2 = fcb.fps_fraction(s2["fps"])
        assert [fcb.to_frames(c["at"], rate2) for c in t2["clips"]] == [0, 1, 4, 6]

        # explicit subject file + custom states
        plan3 = {"craft_clips": [], "opener": {"preset": "flicker", "plate": str(assets / "plate.png"), "silhouette": str(assets / "silhouette.mov"),
                                                "subject": str(assets / "silhouette.mov"), "states": [["silhouette", 2], ["plate", 2], ["subject", 2]]}}
        assert _run_spec(td_p, media, words, plan3, "custom").returncode == 0

        # errors: exit 2, message on stderr, no spec written
        for name, op, needle in [
            ("nofile", {"preset": "flicker", "plate": str(assets / "nope.png"), "silhouette": str(assets / "silhouette.mov")}, "not found"),
            ("nosil", {"preset": "flicker", "plate": str(assets / "plate.png")}, "silhouette"),
            ("unknown", {"preset": "strobe_soup"}, "unknown opener preset"),
            ("cclass", {"preset": "time_displacement"}, "c-class"),
            ("toolong", {"preset": "flicker", "plate": str(assets / "plate.png"), "silhouette": str(assets / "silhouette.mov"),
                         "states": [["plate", 200]]}, "long"),
        ]:
            rr = _run_spec(td_p, media, words, {"craft_clips": [], "opener": op}, name)
            assert rr.returncode == 2 and needle in rr.stderr.lower(), (name, rr.returncode, rr.stderr[-400:])
            assert not (td_p / "out" / f"{name}.craft.json").exists(), name
        assert _run_spec(td_p, media, words, {"craft_clips": [], "opener": "flicker"}, "bare").returncode == 2
    print("[PASS] 08 spec_from_plan opener=flicker: frame-exact rows on one new track, fc_build-valid, errors exit 2")


def test_09_tool_is_stateless_portable_nfc() -> None:
    for p in (TOOLS_DIR / "flicker_schedule.py", Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert unicodedata.normalize("NFC", src) == src, p.name
        for bad in ("/home/" + "vmiz", "/home/" + "thanh"):
            assert bad not in src, f"{bad} in {p.name}"
    src = (TOOLS_DIR / "flicker_schedule.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*global\s", src, re.M), "stateless tool: no `global` statement"
    print("[PASS] 09 flicker_schedule.py: NFC, no host paths, no global state")


if __name__ == "__main__":
    test_01_schedule_is_frame_exact_and_non_overlapping()
    test_02_custom_states_and_errors()
    test_03_ffmpeg_overlay_reproduces_centre_luma_pattern()
    test_04_silhouette_colour_is_exactly_fffbf0()
    test_05_clean_plate_median_removes_moving_square()
    test_06_matte_guards_raise_instead_of_degrading()
    test_07_c_class_asks_are_refused()
    test_08_spec_from_plan_opener_flicker()
    test_09_tool_is_stateless_portable_nfc()
    print("TẤT CẢ ĐẠT (flicker_schedule PKG-C)")
