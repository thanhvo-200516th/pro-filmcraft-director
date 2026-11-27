#!/usr/bin/env python3
"""
Tests for the v7.9.1 audit fixes of the Look S compositor path (synthetic media only: ffmpeg testsrc2 + sine in a temp dir).

  01 `pipe_encode_single_plate_fast`: a raising frame iterator or a dead ffmpeg (BrokenPipe) leaves no ffmpeg child and no temp file
  02 `compose_master_mp4_via_ffmpeg`: a plate path with a `'` concatenates, two composes into one folder at once do not collide
  03 `probe_video` / `check_look_s_geometry`: ffprobe facts, exact / scale / refuse verdicts, the compositor CLI refuses a file with
     no video stream and its --help says what is checked
  04 `get_or_build_fullwidth_person_alpha_seq`: the cache key follows the frame content (no stale hit for the same tag + count),
     no temp file is left in the cache folder
  05 `_find_playfair_italic`: fontconfig fallback with a loud stderr WARNING when the font folders miss it
  06 `render_gradient_italic_headline`: NFD input renders exactly like NFC
  07 `motion_gate.py --help` states the default window (0-3.4 s) and the late-hook sub-window
  08 `look_s_render.py`: --help, --dry-run plan of a `studio_recipe.plan_scenes` timeline, clear refusals (missing file, no video
     stream, landscape A-roll, matte needed but none), 9:16 non-1080 A-roll is warned and scaled
  09 `look_s_render.py --draft`: every Look S mode (H, A2, A1, P, P pop-out, N, S, B) renders to a 540x960@30 master with audio,
     a second run reuses every cached segment

Plain asserts with a `__main__` runner: `python3 tests/test_look_s_driver_v791.py`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unicodedata
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
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, timeout=180, capture_output=True)


def _make_video(path: Path, w: int, h: int, dur: float, fps: int = 30, audio: bool = True) -> Path:
    a_in = ["-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={dur}"] if audio else []
    a_out = ["-c:a", "aac", "-b:a", "96k"] if audio else []
    _ff("-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}:duration={dur}", *a_in,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", *a_out, "-shortest", str(path))
    return path


def _make_wav(path: Path, dur: float) -> Path:
    _ff("-f", "lavfi", "-i", f"sine=frequency=330:sample_rate=48000:duration={dur}", "-ac", "2", str(path))
    return path


def _ffmpeg_children() -> list[int]:
    """PIDs of ffmpeg processes (running or zombie) whose parent is this test process (Linux /proc)."""
    me, kids = os.getpid(), []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text()
        except OSError:
            continue
        comm = stat[stat.index("(") + 1:stat.rindex(")")]
        ppid = int(stat[stat.rindex(")") + 2:].split()[1])
        if ppid == me and comm.startswith("ffmpeg"):
            kids.append(int(d.name))
    return kids


def _leftovers(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.name.startswith(".tmp") or p.name.startswith(".concat") or ".tmp" in p.name)


def _probe(path: Path) -> dict:
    import fast_studio_compositor as fsc
    return fsc.probe_video(path)


# ---------------------------------------------------------------------------------------------- (1) encoder leak
def test_01_pipe_encode_no_leak() -> None:
    import fast_studio_compositor as fsc

    with tempfile.TemporaryDirectory(prefix="pfd_enc_") as td:
        folder = Path(td)
        gear = fsc.RenderGear("t", 64, 64, 10, 30, "ultrafast")

        def boom():
            for i in range(3):
                yield np.full((64, 64, 3), 40 * i, np.uint8)
            raise ValueError("frame source died")

        try:
            fsc.pipe_encode_single_plate_fast(boom(), folder / "seg.mp4", gear=gear, threads=1)
        except ValueError as exc:
            assert "frame source died" in str(exc)
        else:
            raise AssertionError("the frame iterator error must propagate")
        assert not (folder / "seg.mp4").exists(), "no output on failure"
        assert _leftovers(folder) == [], _leftovers(folder)
        assert _ffmpeg_children() == [], f"ffmpeg child left behind: {_ffmpeg_children()}"

        bad = fsc.RenderGear("t", 64, 64, 10, 30, "no-such-preset")      # ffmpeg exits at encoder open -> BrokenPipe / rc != 0
        frames = (np.full((64, 64, 3), i % 255, np.uint8) for i in range(400))
        try:
            fsc.pipe_encode_single_plate_fast(frames, folder / "seg2.mp4", gear=bad, threads=1)
        except RuntimeError as exc:
            assert "seg2.mp4" in str(exc), exc
        else:
            raise AssertionError("a dead ffmpeg must raise RuntimeError")
        assert not (folder / "seg2.mp4").exists() and _leftovers(folder) == [], _leftovers(folder)
        assert _ffmpeg_children() == [], f"ffmpeg child left behind: {_ffmpeg_children()}"

        fsc.pipe_encode_single_plate_fast((np.full((64, 64, 3), 90, np.uint8) for _ in range(10)), folder / "ok.mp4", gear=gear, threads=1)
        assert (folder / "ok.mp4").is_file() and _leftovers(folder) == []
    print("[PASS] 01 pipe encoder: raising iterator / dead ffmpeg leave no child process and no temp file; the good path still works")


# ---------------------------------------------------------------------------------------------- (2) concat escaping + parallel temps
def test_02_concat_quote_and_parallel_compose() -> None:
    import fast_studio_compositor as fsc

    with tempfile.TemporaryDirectory(prefix="pfd_cat_") as td:
        quoted = Path(td) / "it's a dir"
        quoted.mkdir()
        gear = fsc.RenderGear("t", 64, 64, 10, 30, "ultrafast")
        segs = []
        for k in range(2):
            p = quoted / f"seg'{k}.mp4"
            fsc.pipe_encode_single_plate_fast((np.full((64, 64, 3), 60 + 80 * k, np.uint8) for _ in range(10)), p, gear=gear, threads=1)
            segs.append(p)
        wav = _make_wav(quoted / "voice.wav", 2.0)
        errs: list[BaseException] = []

        def run(name: str) -> None:
            try:
                fsc.compose_master_mp4_via_ffmpeg(segs, wav, [], [], quoted / name, gear=gear, threads=1)
            except BaseException as exc:  # noqa: BLE001 - collected for the assert below
                errs.append(exc)

        ths = [threading.Thread(target=run, args=(n,)) for n in ("a.mp4", "b.mp4", "c.mp4")]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        assert not errs, errs
        for n in ("a.mp4", "b.mp4", "c.mp4"):
            info = _probe(quoted / n)
            assert abs(info["duration"] - 2.0) < 0.25, (n, info)
        assert _leftovers(quoted) == [], _leftovers(quoted)
    print("[PASS] 02 compose: quoted plate paths concatenate; 3 parallel composes into one folder succeed with no temp collisions")


# ---------------------------------------------------------------------------------------------- (3) probe + geometry
def test_03_probe_and_geometry_check() -> None:
    import fast_studio_compositor as fsc

    g = fsc.check_look_s_geometry
    assert g(1080, 1920)["status"] == "exact"
    for w, h in ((540, 960), (720, 1280), (2160, 3840)):
        r = g(w, h)
        assert r["status"] == "scale" and "1080x1920" in r["message"], r
    for w, h in ((1920, 1080), (1080, 1350), (1080, 1080)):
        r = g(w, h)
        assert r["status"] == "refuse" and "9:16" in r["message"], r

    with tempfile.TemporaryDirectory(prefix="pfd_probe_") as td:
        v = _make_video(Path(td) / "a.mp4", 1080, 1920, 1.0, fps=30)
        info = fsc.probe_video(v)
        assert (info["width"], info["height"]) == (1080, 1920) and abs(info["fps"] - 30.0) < 1e-3, info
        assert info["has_audio"] and abs(info["duration"] - 1.0) < 0.1, info
        wav = _make_wav(Path(td) / "v.wav", 1.0)
        try:
            fsc.probe_video(wav)
        except ValueError as exc:
            assert "video stream" in str(exc), exc
        else:
            raise AssertionError("a wav has no video stream")

        cli = TOOLS_DIR / "fast_studio_compositor.py"
        r = subprocess.run([PY, str(cli), "--input", str(wav), "--out", str(Path(td) / "o.mp4")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert r.returncode == 2 and "video stream" in r.stderr, (r.returncode, r.stderr[-400:])
        land = _make_video(Path(td) / "land.mp4", 320, 180, 0.5, fps=30)
        r2 = subprocess.run([PY, str(cli), "--input", str(land), "--out", str(Path(td) / "o2.mp4")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        assert r2.returncode == 0 and "WARNING" in r2.stderr and "9:16" in r2.stderr, (r2.returncode, r2.stderr[-400:])
        h = subprocess.run([PY, str(cli), "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        assert h.returncode == 0 and "ffprobe" in h.stdout and "validated against it" not in h.stdout, h.stdout
    print("[PASS] 03 probe_video / check_look_s_geometry; compositor CLI refuses a stream-less input, warns on non-9:16, --help says what is checked")


# ---------------------------------------------------------------------------------------------- (4) alpha cache key
def test_04_alpha_cache_keyed_by_content() -> None:
    import fast_studio_compositor as fsc

    calls = {"n": 0}

    def fake_predict(rgb: np.ndarray) -> np.ndarray:
        calls["n"] += 1
        return np.full(rgb.shape[:2], int(rgb.mean()) % 256, np.uint8)

    real = fsc.predict_u2netp_alpha_u8
    fsc.predict_u2netp_alpha_u8 = fake_predict
    try:
        with tempfile.TemporaryDirectory(prefix="pfd_alpha_") as td:
            cache = Path(td)
            fa = [np.full((192, 108, 3), 200, np.uint8) for _ in range(4)]
            fb = [np.full((192, 108, 3), 60, np.uint8) for _ in range(4)]
            a1 = fsc.get_or_build_fullwidth_person_alpha_seq(cache, "S01", fa, stride=3)
            n1 = calls["n"]
            b1 = fsc.get_or_build_fullwidth_person_alpha_seq(cache, "S01", fb, stride=3)
            assert calls["n"] > n1, "different frames with the same tag + count must not hit the cache"
            assert not np.array_equal(a1, b1), "stale alpha returned for new frames"
            n2 = calls["n"]
            a2 = fsc.get_or_build_fullwidth_person_alpha_seq(cache, "S01", fa, stride=3)
            assert calls["n"] == n2 and np.array_equal(a1, a2), "same content must hit the cache"
            names = sorted(p.name for p in cache.iterdir())
            assert len(names) == 2 and all(n.endswith(".npz") and n.startswith("fullwidth_alpha_S01_") for n in names), names
    finally:
        fsc.predict_u2netp_alpha_u8 = real
    print("[PASS] 04 full-width alpha cache: content-hashed key (no stale hit), same content hits, atomic write leaves no temp")


# ---------------------------------------------------------------------------------------------- (5) font fallback
def test_05_font_fontconfig_fallback_is_loud() -> None:
    import fast_studio_compositor as fsc

    has_fc = subprocess.run(["fc-list", ":family=Playfair Display", "file", "style"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30).stdout
    with tempfile.TemporaryDirectory(prefix="pfd_font_") as td:
        old_env, old_home = os.environ.get("PFD_FONT_DIR"), Path.home
        os.environ["PFD_FONT_DIR"] = td
        Path.home = classmethod(lambda cls: Path(td))  # type: ignore[assignment]
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                try:
                    p = fsc._find_playfair_italic()
                except FileNotFoundError as exc:
                    p = None
                    assert "fc-match" in str(exc) or "fontconfig" in str(exc), exc
        finally:
            Path.home = old_home  # type: ignore[assignment]
            if old_env is None:
                os.environ.pop("PFD_FONT_DIR", None)
            else:
                os.environ["PFD_FONT_DIR"] = old_env
        if "Italic" in has_fc:
            assert p is not None and p.is_file() and "Playfair" in p.name, p
            assert "WARNING" in err.getvalue() and "fontconfig" in err.getvalue(), err.getvalue()
        else:
            assert p is None
    print("[PASS] 05 Playfair Italic: fontconfig fallback when the font folders miss it, with a loud stderr WARNING")


# ---------------------------------------------------------------------------------------------- (6) NFC text
def test_06_headline_nfc() -> None:
    import fast_studio_compositor as fsc

    try:
        fsc._find_playfair_italic()
    except FileNotFoundError:
        print("[SKIP] 06 Playfair Display Italic not installed")
        return
    paper = fsc.render_lavender_paper(1080, 1920)
    txt, sub = "Phấn nền mỏng nhẹ", "mà"
    nfc = fsc.render_gradient_italic_headline(paper, unicodedata.normalize("NFC", txt), unicodedata.normalize("NFC", sub))
    nfd = fsc.render_gradient_italic_headline(paper, unicodedata.normalize("NFD", txt), unicodedata.normalize("NFD", sub))
    assert unicodedata.normalize("NFD", txt) != txt
    assert np.array_equal(nfc, nfd), "NFD text must be NFC-normalised before drawing"
    print("[PASS] 06 render_gradient_italic_headline: NFD input renders identically to NFC")


# ---------------------------------------------------------------------------------------------- (7) motion_gate window
def test_07_motion_gate_help_window() -> None:
    r = subprocess.run([PY, str(TOOLS_DIR / "motion_gate.py"), "--help"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    assert r.returncode == 0, r.stderr
    flat = " ".join(r.stdout.split())
    assert "3.4" in flat and "2.03" in flat and "3.38" in flat, flat
    import motion_gate as mg
    import inspect
    sig = inspect.signature(mg.check_motion)
    assert sig.parameters["t0"].default == 0.0 and sig.parameters["t1"].default == 3.4
    print("[PASS] 07 motion_gate: default window 0-3.4 s kept, --help names the 2.03-3.38 s late-hook sub-window")


# ---------------------------------------------------------------------------------------------- look_s_render helpers
def _run_lsr(*args: str, env: dict | None = None, timeout: int = 900) -> tuple[int, dict, str]:
    r = subprocess.run([PY, str(LSR), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env)
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError:
        doc = {}
    return r.returncode, doc, r.stderr


def _words(dur: float) -> list[list]:
    n = int(dur / 0.4)
    return [[f"từ{i}", round(i * 0.4 + 0.05, 3), round(i * 0.4 + 0.33, 3)] for i in range(n)]


def _alpha_npy(path: Path, n: int, w: int = 270, h: int = 480) -> Path:
    """Synthetic person matte (head ellipse + torso) at 30 fps, uint8 (N, h, w), with a slow sway so the crown moves."""
    import cv2
    arr = np.zeros((n, h, w), np.uint8)
    for i in range(n):
        dx = int(6 * np.sin(i / 7.0))
        cv2.ellipse(arr[i], (w // 2 + dx, int(h * 0.42)), (int(w * 0.16), int(h * 0.11)), 0, 0, 360, 255, -1)
        cv2.rectangle(arr[i], (int(w * 0.22) + dx, int(h * 0.55)), (int(w * 0.78) + dx, h - 1), 255, -1)
    np.save(path, arr)
    return path


def test_08_look_s_render_validation_and_dry_run() -> None:
    import studio_recipe as sr

    r = subprocess.run([PY, str(LSR), "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stderr
    for needle in ("--scenes", "--words", "--aroll", "--work", "--out", "--draft", "--master", "--broll-dir", "--dry-run", "1080x1920"):
        assert needle in r.stdout, needle

    with tempfile.TemporaryDirectory(prefix="pfd_lsr_") as td:
        d = Path(td)
        dur = 6.0
        words = d / "words_tl.json"
        words.write_text(json.dumps(_words(dur), ensure_ascii=False), encoding="utf-8")
        plan = sr.plan_scenes(_words(dur), dur)
        scenes = d / "scenes.json"
        scenes.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        aroll = _make_video(d / "aroll.mp4", 1080, 1920, dur)
        alpha = _alpha_npy(d / "alpha.npy", int(dur * 30))
        broll = d / "broll"
        broll.mkdir()
        _make_video(broll / "b1.mp4", 640, 360, 4.0, audio=False)
        base = ["--scenes", str(scenes), "--words", str(words), "--aroll", str(aroll), "--work", str(d / "work"),
                "--out", str(d / "master.mp4")]

        rc, doc, err = _run_lsr(*base, "--draft", "--broll-dir", str(broll), "--alpha-npy", str(alpha), "--dry-run")
        assert rc == 0 and doc.get("ok") is True and doc.get("dry_run") is True, (rc, doc, err[-600:])
        assert [s["mode"] for s in doc["scenes"]] == [s["mode"] for s in plan["scenes"]], doc["scenes"]
        assert sum(s["frames"] for s in doc["scenes"]) == round(dur * 30), doc["scenes"]
        assert doc["gear"]["name"] == "draft" and doc["aroll"]["geometry"] == "exact"
        hook = doc["scenes"][0]
        assert hook["mode"] == "H" and hook["broll"] and hook["broll"]["src"].endswith("b1.mp4"), hook
        assert not (d / "master.mp4").exists() and not (d / "work" / "segs").exists(), "dry-run must not render"

        rc, doc, _ = _run_lsr(*[a if a != str(aroll) else str(d / "missing.mp4") for a in base], "--dry-run")
        assert rc == 2 and doc.get("ok") is False and "missing.mp4" in doc.get("error", ""), doc

        wav = _make_wav(d / "voice.wav", dur)
        rc, doc, _ = _run_lsr(*[a if a != str(aroll) else str(wav) for a in base], "--dry-run")
        assert rc == 2 and "video stream" in doc.get("error", ""), doc

        land = _make_video(d / "land.mp4", 640, 360, dur)
        rc, doc, _ = _run_lsr(*[a if a != str(aroll) else str(land) for a in base], "--dry-run", "--alpha-npy", str(alpha))
        assert rc == 2 and "9:16" in doc.get("error", ""), doc

        small = _make_video(d / "small.mp4", 540, 960, dur)
        rc, doc, _ = _run_lsr(*[a if a != str(aroll) else str(small) for a in base], "--dry-run", "--alpha-npy", str(alpha))
        assert rc == 0 and doc["aroll"]["geometry"] == "scale" and any("1080x1920" in w for w in doc["warnings"]), doc

        home = d / "emptyhome"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("PFD_MATTE_MODEL", "U2NETP_ONNX_PATH")}
        env["HOME"] = str(home)
        rc, doc, _ = _run_lsr(*base, "--dry-run", env=env)
        assert rc == 2 and "matte" in doc.get("error", "").lower(), doc

        bad = json.loads(scenes.read_text(encoding="utf-8"))
        bad["scenes"][1]["start"] += 0.5
        (d / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        rc, doc, _ = _run_lsr(*[a if a != str(scenes) else str(d / "bad.json") for a in base], "--dry-run", "--alpha-npy", str(alpha))
        assert rc == 2 and "contiguous" in doc.get("error", ""), doc
    print("[PASS] 08 look_s_render: --help, dry-run plan of a studio_recipe timeline, refusals (missing, no video, 16:9, no matte, gap), 9:16 scale warning")


def test_09_look_s_render_draft_all_modes() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_lsr2_") as td:
        d = Path(td)
        modes = [("H", {}), ("A2", {"pip": "bl"}), ("A1", {}), ("P", {}), ("P", {"popout": True}), ("N", {}), ("S", {}), ("B", {})]
        step, scs, t = 0.5, [], 0.0
        jewels = ["#F5C451", "#FF4D5E", "#34D399", "#7DD3FC", "#FACC15"]
        for i, (m, extra) in enumerate(modes):
            scs.append({"id": f"T{i:02d}", "start": round(t, 3), "end": round(t + step, 3), "mode": m, "kind": "text",
                        "jewel": jewels[i % 5], "hue": "#F6F6F8" if m == "P" else jewels[i % 5],
                        "bg": "#FAFAFA" if m == "P" else None, "text": "", **extra})
            t += step
        dur = round(t, 3)
        scenes = d / "scenes.json"
        scenes.write_text(json.dumps({"look": "S", "duration": dur, "scenes": scs}), encoding="utf-8")
        words = d / "words.json"
        words.write_text(json.dumps({"words": _words(dur)}, ensure_ascii=False), encoding="utf-8")
        aroll = _make_video(d / "aroll.mp4", 1080, 1920, dur)
        alpha = _alpha_npy(d / "alpha.npy", int(dur * 30))
        broll = d / "broll"
        broll.mkdir()
        _make_video(broll / "b1.mp4", 640, 360, 3.0, audio=False)
        out = d / "out" / "master.mp4"
        args = ["--scenes", str(scenes), "--words", str(words), "--aroll", str(aroll), "--work", str(d / "work"), "--out", str(out),
                "--draft", "--broll-dir", str(broll), "--alpha-npy", str(alpha), "--jobs", "4"]
        rc, doc, err = _run_lsr(*args)
        assert rc == 0 and doc.get("ok") is True, (rc, json.dumps(doc)[:1500], err[-1500:])
        info = _probe(out)
        assert (info["width"], info["height"]) == (540, 960) and abs(info["fps"] - 30) < 1e-3, info
        assert info["has_audio"] and abs(info["duration"] - dur) < 0.2, info
        assert doc["segments_rendered"] == len(modes) and doc["segments_cached"] == 0, doc
        assert doc["voice_guard"]["speech_density"] > 0.4, doc["voice_guard"]
        assert [s["renderer"] for s in doc["scenes"]][4] == "render_popout_studio_card", doc["scenes"]
        assert _ffmpeg_children() == []
        rc2, doc2, err2 = _run_lsr(*args)
        assert rc2 == 0 and doc2["segments_cached"] == len(modes) and doc2["segments_rendered"] == 0, (doc2, err2[-600:])
        assert _leftovers(out.parent) == [], _leftovers(out.parent)
    print("[PASS] 09 look_s_render --draft: H/A2/A1/P/pop-out/N/S/B render to 540x960@30 with audio; the second run reuses every segment")


if __name__ == "__main__":
    test_01_pipe_encode_no_leak()
    test_02_concat_quote_and_parallel_compose()
    test_03_probe_and_geometry_check()
    test_04_alpha_cache_keyed_by_content()
    test_05_font_fontconfig_fallback_is_loud()
    test_06_headline_nfc()
    test_07_motion_gate_help_window()
    test_08_look_s_render_validation_and_dry_run()
    test_09_look_s_render_draft_all_modes()
    print("TẤT CẢ ĐẠT (look_s_render + compositor audit fixes v7.9.1)")
