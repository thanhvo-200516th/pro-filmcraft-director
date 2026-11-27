#!/usr/bin/env python3
"""
Tests for `scripts/tools/filmcraft_cli.py` (v7.4.0): the shim that replaces the nonexistent `filmcraft-cli`.

  - pure-function unit tests with a FAKE Craft (only `cmd()`): frame<->ticks, clamp, absolute path, exit codes, offline, token hygiene;
  - integration tests that SKIP cleanly without `~/.local/bin/filmcraft` or an X server: ffmpeg `testsrc` clip (<= 3 s) in a tempdir
    -> `fc_build_fast.py` -> `render` -> PNG with gray std > 5; offline variant -> exit 3 and `missingMedia: 1`;
  - a contract test (skipped without the app) on `engine.commands`.
Never touches a real project; the real app is only started as a private child with its own port, token and temp data dir.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
VENDOR_TOOLS = SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "scripts" / "apps" / "craft-handoff" / "tools"
SHIM = TOOLS_DIR / "filmcraft_cli.py"
PY = os.environ.get("FILMCRAFT_VENV_PYTHON") or str(Path.home() / ".venvs/video-skills/bin/python3")
if not Path(PY).is_file():
    PY = sys.executable
sys.path.insert(0, str(TOOLS_DIR))

import filmcraft_cli as fc  # noqa: E402

TICKS = 254_016_000_000
TOKEN = "ab" * 32


class FakeCraft:
    """Only `cmd()`, like the real Craft; records calls and writes a PNG when asked to export a frame."""

    def __init__(self, missing: int = 0, fps: dict | None = None, duration_frames: int = 50, write_png: bool = True):
        self.missing = missing
        self.fps = fps or {"num": 25, "den": 1}
        self.duration_frames = duration_frames
        self.write_png = write_png
        self.calls: list[tuple[str, dict]] = []
        self.token = TOKEN

    def cmd(self, command: str, params: dict | None = None):
        params = params or {}
        self.calls.append((command, params))
        if command == "file.open":
            return {"migrated": False, "missingMedia": self.missing, "path": params["path"], "schemaVersion": 15}
        if command == "sequence.inspect":
            fps = Fraction(self.fps["num"], self.fps["den"])
            out = {"name": "fake seq", "duration": int(self.duration_frames * TICKS / fps), "durationFrames": self.duration_frames,
                   "settings": {"frame_rate": self.fps}}
            return out
        if command == "file.exportFrame":
            if self.write_png:
                _write_png(Path(params["path"]), noisy=True)
            return {"depth": 8, "width": 64, "height": 36, "path": params["path"], "time": params["time"]}
        raise AssertionError(f"unexpected command {command}")


def _write_png(path: Path, noisy: bool) -> None:
    from PIL import Image
    import numpy as np
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 255, (36, 64, 3), dtype=np.uint8) if noisy else np.zeros((36, 64, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)


def _export_call(craft: FakeCraft) -> dict:
    return next(p for c, p in craft.calls if c == "file.exportFrame")


# ---------------------------------------------------------------------------
# Unit tests (no FilmCraft, no X)
# ---------------------------------------------------------------------------

def test_ticks_frame_and_seconds_conversion() -> None:
    for num, den in ((25, 1), (24, 1), (30000, 1001), (60, 1)):
        fps = Fraction(num, den)
        assert fc.fps_from_inspect({"settings": {"frame_rate": {"num": num, "den": den}}}) == fps
        assert fc.ticks_per_frame(fps) == TICKS * den // num, (num, den)
        assert fc.frame_to_ticks(0, fps) == 0
        assert fc.frame_to_ticks(10, fps) == 10 * TICKS * den // num
        assert fc.frame_to_ticks(num, fps) == fc.frame_to_ticks(1, fps) * num  # exact, no float drift
    assert fc.frame_to_ticks(30000, Fraction(30000, 1001)) == 1001 * TICKS  # 30000 frames @ 29.97 = 1001 s
    assert fc.seconds_to_ticks(0.45) == 9 * TICKS // 20
    assert fc.seconds_to_ticks(0) == 0
    print("[PASS] ticks: frame<->ticks exact for 25/1, 24/1, 30000/1001, 60/1")


def test_fps_is_never_defaulted() -> None:
    for bad in ({}, {"settings": {}}, {"settings": {"frame_rate": None}}, {"settings": {"frame_rate": {"num": 25}}},
                {"settings": {"frame_rate": {"num": 0, "den": 1}}}, {"fps": 25}):
        try:
            fc.fps_from_inspect(bad)
        except fc.FcliError as exc:
            assert exc.code == fc.EXIT_CONTROL
        else:
            raise AssertionError(f"fps must not default to 25 for {bad}")
    print("[PASS] fps: only settings.frame_rate{num,den} counts; no .get('fps', 25) fallback")


def test_clamp_to_last_frame() -> None:
    fps, dur = Fraction(25), 50 * TICKS // 25
    last = dur - fc.ticks_per_frame(fps)
    assert fc.clamp_ticks(0, dur, fps) == (0, False)
    assert fc.clamp_ticks(last, dur, fps) == (last, False)
    assert fc.clamp_ticks(last + 1, dur, fps) == (last, True)
    assert fc.clamp_ticks(99 * TICKS, dur, fps) == (last, True)
    assert fc.clamp_ticks(-5, dur, fps) == (0, True)
    try:
        fc.clamp_ticks(0, 0, fps)
    except fc.FcliError as exc:
        assert exc.code == fc.EXIT_CONTROL
    else:
        raise AssertionError("empty sequence must be an error")
    print("[PASS] clamp: [0, duration - 1 frame], clamped flag, empty sequence rejected")


def test_render_flow_with_fake_craft() -> None:
    with tempfile.TemporaryDirectory(prefix="fcli_t_") as td:
        out = Path(td) / "sub" / "f.png"
        craft = FakeCraft()
        res = fc.do_render(craft, Path(td) / "p.fcproj", out, seconds=0.45, frame=None, allow_offline=False)
        assert res["ok"] and fc.exit_code_for(res) == 0 and res["missingMedia"] == 0
        assert [c for c, _ in craft.calls] == ["file.open", "sequence.inspect", "file.exportFrame"]
        exp = _export_call(craft)
        assert exp["target"] == "program" and exp["format"] == "png" and exp["time"] == fc.seconds_to_ticks(0.45)
        assert Path(exp["path"]).is_absolute() and out.is_file()
        assert res["clamped"] is False and res["fps"] == "25/1" and res["std"] > 5
        # --frame on 30000/1001 uses the exact rate, and a frame past the end is clamped
        c2 = FakeCraft(fps={"num": 30000, "den": 1001}, duration_frames=90)
        r2 = fc.do_render(c2, Path(td) / "p.fcproj", out, seconds=None, frame=10, allow_offline=False)
        assert _export_call(c2)["time"] == 10 * TICKS * 1001 // 30000 and r2["clamped"] is False
        c3 = FakeCraft(fps={"num": 30000, "den": 1001}, duration_frames=90)
        r3 = fc.do_render(c3, Path(td) / "p.fcproj", out, seconds=None, frame=5000, allow_offline=False)
        assert r3["clamped"] is True and _export_call(c3)["time"] == 89 * TICKS * 1001 // 30000
    print("[PASS] render flow: open -> inspect -> exportFrame(program, ticks), clamp reported, exact 30000/1001")


def test_relative_paths_become_absolute() -> None:
    cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory(prefix="fcli_t_") as td:
            os.chdir(td)
            abs_out = fc.absolute_path("rel/f.png")
            assert abs_out.is_absolute() and abs_out == (Path(td).resolve() / "rel" / "f.png")
            craft = FakeCraft()
            fc.do_render(craft, fc.absolute_path("p.fcproj"), abs_out, seconds=0.0, frame=None, allow_offline=False)
            assert Path(craft.calls[0][1]["path"]).is_absolute() and Path(_export_call(craft)["path"]).is_absolute()
    finally:
        os.chdir(cwd)
    print("[PASS] paths: relative project/out are resolved to absolute before reaching the app")


def test_offline_media_maps_to_exit_3() -> None:
    with tempfile.TemporaryDirectory(prefix="fcli_t_") as td:
        out = Path(td) / "f.png"
        res = fc.do_render(FakeCraft(missing=2), Path(td) / "p.fcproj", out, seconds=0.2, frame=None, allow_offline=False)
        assert res["ok"] is False and res["missingMedia"] == 2 and fc.exit_code_for(res) == fc.EXIT_OFFLINE
        assert isinstance(res["missingMedia"], int) and out.is_file(), "frame is still exported for the human"
        ok = fc.do_render(FakeCraft(missing=2), Path(td) / "p.fcproj", out, seconds=0.2, frame=None, allow_offline=True)
        assert ok["ok"] is True and ok["missingMedia"] == 2 and fc.exit_code_for(ok) == 0
        op = fc.do_open(FakeCraft(missing=1), Path(td) / "p.fcproj", allow_offline=False)
        assert fc.exit_code_for(op) == fc.EXIT_OFFLINE and op["sequence"] == "fake seq"
    for bad in (None, {}, {"missingMedia": None}, {"missingMedia": True}, {"missingMedia": "0"}):
        try:
            fc.missing_media_from_open(bad)
        except fc.FcliError as exc:
            assert exc.code == fc.EXIT_CONTROL
        else:
            raise AssertionError(f"missingMedia {bad!r} must not be accepted as proof of 0 offline")
    print("[PASS] offline: missingMedia>0 -> exit 3 unless --allow-offline; non-int missingMedia is an error, never 0")


def test_blank_or_missing_frame_maps_to_exit_3() -> None:
    with tempfile.TemporaryDirectory(prefix="fcli_t_") as td:
        out = Path(td) / "f.png"
        res = fc.do_render(FakeCraft(write_png=False), Path(td) / "p.fcproj", out, seconds=0.0, frame=None, allow_offline=False)
        assert res["ok"] is False and fc.exit_code_for(res) == fc.EXIT_OFFLINE and res.get("blank") is True
        _write_png(out, noisy=False)
        assert fc.check_png(out)["std"] == 0.0, "default does not fail a legitimately dark frame"
        try:
            fc.check_png(out, min_std=5.0)
        except fc.FcliError as exc:
            assert exc.code == fc.EXIT_OFFLINE
        else:
            raise AssertionError("--min-std must fail a flat frame")
        out.write_bytes(b"not a png")
        try:
            fc.check_png(out)
        except fc.FcliError as exc:
            assert exc.code == fc.EXIT_OFFLINE
        else:
            raise AssertionError("garbage file is not a frame")
    print("[PASS] frame check: absent/empty/non-PNG -> exit 3; --min-std rejects a flat frame")


def test_exit_code_mapping() -> None:
    assert fc.exit_code_for({"ok": True}) == 0
    assert fc.exit_code_for({"ok": False}) == fc.EXIT_CONTROL
    assert fc.exit_code_for({"ok": False, "exit": 2}) == 2
    assert fc.exit_code_for({"ok": False, "exit": 3}) == 3
    assert fc.exit_code_for({"ok": False, "exit": 124}) == 124
    assert (fc.EXIT_OK, fc.EXIT_CONTROL, fc.EXIT_USAGE, fc.EXIT_OFFLINE) == (0, 1, 2, 3)
    print("[PASS] exit codes: 0 ok, 1 control, 2 usage/skip, 3 offline/blank, 124 timeout")


def test_token_is_never_printed() -> None:
    assert fc._scrub(f"app said {TOKEN} bye", TOKEN) == "app said <token> bye"
    assert fc._scrub("nothing", None) == "nothing"
    with tempfile.TemporaryDirectory(prefix="fcli_t_") as td:
        craft = FakeCraft()
        res = fc.do_render(craft, Path(td) / "p.fcproj", Path(td) / "f.png", seconds=0.0, frame=None, allow_offline=False)
        assert TOKEN not in json.dumps(res)
        assert TOKEN not in json.dumps(fc.do_open(craft, Path(td) / "p.fcproj", False))
    src = SHIM.read_text(encoding="utf-8")
    assert "craft.token" in src and "_scrub(" in src and "print(craft.token" not in src
    print("[PASS] token: not in any payload, scrubbed from errors")


def test_cli_without_binary_is_a_clean_exit_2() -> None:
    with tempfile.TemporaryDirectory(prefix="fcli_nobin_") as home:
        env = {k: v for k, v in os.environ.items() if k not in ("CRAFT_BIN_DIR", "CRAFT_DISPLAY", "DISPLAY")}
        env.update(HOME=home, PATH="/usr/bin:/bin")
        r = subprocess.run([PY, str(SHIM), "--project", "x.fcproj", "render", "--seconds", "0.5", "--out", "x.png"],
                           capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr[-300:])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 1 and "Traceback" not in r.stderr
        msg = json.loads(lines[0])
        assert msg["ok"] is False and msg["skipped"] is True and "filmcraft" in msg["error"] and "filmcraft-cli" not in msg["error"]
        bad = subprocess.run([PY, str(SHIM), "render", "--out", "x.png"], capture_output=True, text=True, env=env, timeout=60)
        assert bad.returncode == 2 and json.loads(bad.stdout.strip().splitlines()[0])["ok"] is False
        helped = subprocess.run([PY, str(SHIM), "--help"], capture_output=True, text=True, env=env, timeout=60)
        assert helped.returncode == 0 and "render" in helped.stdout
    print("[PASS] cli: no filmcraft binary / bad usage -> exit 2, one JSON line, no traceback")


def test_cli_refuses_the_users_desktop_display() -> None:
    if not fc.filmcraft_binary():
        print("[SKIP] display guard: no filmcraft binary on this host")
        return
    r = subprocess.run([PY, str(SHIM), "--display", ":0", "status"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "refusing display :0" in json.loads(r.stdout.strip().splitlines()[0])["error"]
    print("[PASS] cli: --display :0 refused (never the user's real desktop)")


# ---------------------------------------------------------------------------
# Integration + contract (real app on a private X display; skipped when unavailable)
# ---------------------------------------------------------------------------

def _app_unavailable() -> str | None:
    if not fc.filmcraft_binary():
        return "no filmcraft binary"
    display = os.environ.get("CRAFT_DISPLAY") or ":93"
    if display in fc.REFUSED_DISPLAYS:
        return f"CRAFT_DISPLAY={display} is the real desktop"
    if not fc.x_available(display):
        return f"no X server on {display} and no Xvfb/Xephyr"
    if not (VENDOR_TOOLS / "fc_build_fast.py").is_file():
        return "vendored fc_build_fast.py missing"
    if not shutil.which("ffmpeg"):
        return "no ffmpeg"
    return None


def _build_tiny_project(work: Path) -> Path:
    clip = work / "clip.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(clip)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and clip.is_file(), r.stderr[-300:]
    spec = {"name": "fcli_test", "width": 640, "height": 360, "fps": 25, "duration": 2.0,
            "tracks": [{"type": "video", "name": "V1", "clips": [{"name": "A", "src": str(clip), "in": 0.0, "at": 0.0, "dur": 2.0}]}]}
    (work / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    proj = work / "tiny.fcproj"
    r = subprocess.run([PY, str(VENDOR_TOOLS / "fc_build_fast.py"), str(work / "spec.json"), str(proj)],
                       capture_output=True, text=True, timeout=300, cwd=str(work))
    assert r.returncode == 0 and proj.is_file(), (r.stderr or r.stdout)[-600:]
    return proj


def _shim(*args: str) -> tuple[int, dict]:
    r = subprocess.run([PY, str(SHIM), *args], capture_output=True, text=True, timeout=300)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1, f"shim must print exactly one JSON line, got: {r.stdout!r} / {r.stderr[-300:]}"
    return r.returncode, json.loads(lines[0])


def test_integration_render_and_offline() -> None:
    why = _app_unavailable()
    if why:
        print(f"[SKIP] integration render/offline: {why}")
        return
    from PIL import Image
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="fcli_it_") as td:
        work = Path(td)
        proj = _build_tiny_project(work)
        png = work / "frame.png"
        rc, res = _shim("--project", str(proj), "render", "--seconds", "0.5", "--out", str(png), "--min-std", "5")
        assert rc == 0 and res["ok"] is True and res["missingMedia"] == 0 and res["clamped"] is False, (rc, res)
        assert (res["width"], res["height"]) == (640, 360) and res["fps"] == "25/1"
        gray = np.asarray(Image.open(png).convert("L"), dtype=np.float32)
        assert gray.std() > 5, f"frame looks blank: std={gray.std():.2f}"
        rc, res = _shim("--project", str(proj), "render", "--frame", "10", "--out", str(work / "f10.png"))
        assert rc == 0 and abs(res["time_s"] - 0.4) < 1e-6
        rc, res = _shim("--project", str(proj), "render", "--seconds", "99", "--out", str(work / "late.png"))
        assert rc == 0 and res["clamped"] is True and res["time_s"] < res["duration_s"]
        # offline: point the clip at a file that does not exist -> exit 3 and missingMedia:1
        off = work / "off.fcproj"
        off.write_text(proj.read_text(encoding="utf-8").replace(str(work / "clip.mp4"), str(work / "gone.mp4")), encoding="utf-8")
        rc, res = _shim("--project", str(off), "render", "--seconds", "0.5", "--out", str(work / "off.png"))
        assert rc == 3 and res["ok"] is False and res["missingMedia"] == 1, (rc, res)
        rc, res = _shim("--project", str(off), "--allow-offline", "render", "--seconds", "0.5", "--out", str(work / "off2.png"))
        assert rc == 0 and res["missingMedia"] == 1
        rc, res = _shim("--project", str(off), "open")
        assert rc == 3 and res["missingMedia"] == 1
        rc, res = _shim("status")
        assert rc == 0 and res["version"].startswith("filmcraft")
    print("[PASS] integration: render PNG std>5, --frame, clamp, offline -> exit 3 + missingMedia:1, status")


def test_contract_engine_commands() -> None:
    why = _app_unavailable()
    if why:
        print(f"[SKIP] contract engine.commands: {why}")
        return
    craftctl = fc.load_craftctl(fc.filmcraft_binary())
    with tempfile.TemporaryDirectory(prefix="fcli_ct_") as td:
        with craftctl.Craft("filmcraft", td, display=fc.resolve_display(None, craftctl), args=fc.CRAFT_ARGS) as app:
            ids = {c.get("id") for c in app.rpc("engine.commands")}
    missing = {"file.open", "file.exportFrame", "export.quick", "sequence.inspect"} - ids
    assert not missing, f"FilmCraft no longer lists {sorted(missing)}: re-check references/24 before upgrading"
    # `app.quit` is NOT in the 0.13.0 list yet is executable; Craft.close() relies on it, so prove it by the exit code
    assert app.proc.returncode == 0, f"app.quit did not end the app cleanly (returncode={app.proc.returncode})"
    print(f"[PASS] contract: engine.commands lists file.open, file.exportFrame, export.quick, sequence.inspect ({len(ids)} commands); app.quit exits 0")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (filmcraft_cli shim v7.4.0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
