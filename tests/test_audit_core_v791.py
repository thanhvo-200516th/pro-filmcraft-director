#!/usr/bin/env python3
"""
Tests for the v7.9.1 core audit fixes (compile_and_verify, probe_and_align, studio_recipe, env_status, packaging, presets).

  01 gate 3 fails when edit_rules crashes or prints non-JSON (no silent "0 errors")
  02 gate 3 without --words / --manifest is SKIPPED, and SKIPPED / WARN gates are not counted as passed in the banner
  03 a 0-byte or corrupt video is rejected (non-zero exit, clear message)
  04 a video with no audio stream still writes an empty words_tl.json and an audit warning "no audio stream"
  05 the 16 kHz decode has a timeout and turns ffmpeg failures into a clear error
  06 studio_recipe CLI: empty / nan / dict-shaped words and duration vs last word end
  07 tiktok_loud help text reads the preset (-1.0 dBTP, 14 dB); studio_14 _doc no longer says the wiring is pending
  08 --display defaults to $CRAFT_DISPLAY or :93, never the user's :0 desktop
  09 env_status: FilmCraft version + X server required, python imports, ffmpeg encoders, HF cache + 'small' model, u2netp remedy
  10 requirements.txt / install.sh: no soundfile, opencv-python-headless 4.x, upper bounds, system deps, per-test timeout
  11 PFD_CACHE_DIR (default ~/.cache/pro-filmcraft-director) with legacy read fallback, atomic SFX cache, PID in backup names
  12 execution_tiers.json states the truth about the studio tier (_doc_v791)
  13 absolute-path detection (Windows drives, any POSIX root) and NFC path comparison
  14 --timeout kills child processes before exiting 124; a lock race gives a clear ProbeLockError

Synthetic inputs only (ffmpeg lavfi for the small media files). Plain asserts with a `__main__` runner.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True, timeout=120)


# ---------------------------------------------------------------------------------------------- (1) gate 3 crash
def test_01_gate3_edit_rules_crash_fails() -> None:
    import compile_and_verify as cv
    for code in ("import sys; sys.exit(3)", "print('Traceback: boom')", "import sys; print('[]'); sys.exit(1)"):
        try:
            cv.run_edit_rules_json([PY, "-c", code])
        except RuntimeError as exc:
            assert "edit_rules crashed" in str(exc), exc
            continue
        raise AssertionError(f"edit_rules {code!r} must fail gate 3")
    assert cv.run_edit_rules_json([PY, "-c", "print('[{\"rule\": \"x\", \"status\": \"OK\", \"detail\": \"\"}]')"]) == [
        {"rule": "x", "status": "OK", "detail": ""}]
    assert cv.run_edit_rules_json([PY, "-c", "print('[]')"]) == []
    # edit_rules exits 1 when it reports LỖI: that is a normal audit result, not a crash
    lo = cv.run_edit_rules_json([PY, "-c", "import json, sys; print(json.dumps([{'rule': 'C1', 'status': 'LỖI', 'detail': 'd'}])); sys.exit(1)"])
    assert lo and lo[0]["status"] == "LỖI", lo
    for code in ("import json, sys; print(json.dumps([{'rule': 'C1', 'status': 'LỖI', 'detail': 'd'}])); sys.exit(2)",
                 "import json; print(json.dumps({'rule': 'x'}))"):
        try:
            cv.run_edit_rules_json([PY, "-c", code])
        except RuntimeError as exc:
            assert "edit_rules crashed" in str(exc), exc
        else:
            raise AssertionError(f"edit_rules {code!r} must fail gate 3")
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    g3 = src.split("rules_items = run_edit_rules_json(")[1].split("v60_adj_res")[0]
    assert 'except RuntimeError as exc:' in g3 and 'gates["gate3_edit_rules"] = f"FAIL ({exc})"' in g3 and "raise" in g3, g3
    print("[PASS] 01 gate 3: edit_rules rc != 0 or non-JSON raises 'edit_rules crashed' (FAIL), a JSON list is returned")


# ---------------------------------------------------------------------------------------------- (2) SKIPPED gate 3
def test_02_gate3_skipped_is_honest() -> None:
    import compile_and_verify as cv
    gates = {f"g{i}": "PASS" for i in range(1, 9)}
    t = cv.gate_tally(gates)
    assert t["passed"] == 8 and t["total"] == 8 and t["skipped"] == [] and "8/8 GATES PASSED" in t["banner"], t
    gates["g3"] = "SKIPPED"
    gates["g2"] = "PASS (2 SOFT)"
    t = cv.gate_tally(gates)
    assert t["passed"] == 7 and t["skipped"] == ["g3"] and "7/8 GATES PASSED" in t["banner"] and "SKIPPED" in t["banner"], t
    gates["g4"] = "WARN (1 LỖI)"
    t = cv.gate_tally(gates)
    assert t["passed"] == 6 and "6/8" in t["banner"] and "g4" in t["banner"], t
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    skip_branch = src.split('"reason": "neither --words nor --manifest provided"')[0].rsplit("else:", 1)[1]
    assert 'gates["gate3_edit_rules"] = "SKIPPED"' in skip_branch, skip_branch
    assert '[8/8 GATES PASSED' not in src, "the final banner must be computed by gate_tally"
    print("[PASS] 02 gate 3 without words is SKIPPED; SKIPPED / WARN gates are not counted in the N/8 banner")


# ---------------------------------------------------------------------------------------------- (3) corrupt video
def test_03_empty_or_corrupt_video_rejected() -> None:
    import probe_and_align as pa
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        tdp = Path(td)
        empty = tdp / "empty.mp4"
        empty.write_bytes(b"")
        junk = tdp / "junk.mp4"
        junk.write_bytes(os.urandom(4096))
        for bad in (empty, junk):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = pa.main(["--input", str(bad), "--work", str(tdp / f"w_{bad.stem}"), "--skip-whisper", "--tier", "fast"])
            assert rc not in (0, None), f"{bad.name} accepted (rc={rc})"
            msg = err.getvalue()
            assert bad.name in msg and ("no video stream" in msg or "duration" in msg or "ffprobe" in msg), msg
    print("[PASS] 03 0-byte and corrupt .mp4 inputs exit non-zero with a clear message")


# ---------------------------------------------------------------------------------------------- (4) no audio stream
def test_04_no_audio_writes_empty_words_tl() -> None:
    import probe_and_align as pa
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        tdp = Path(td)
        vid = tdp / "silent_video.mp4"
        _ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=1.5", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid))
        work = tdp / "work"
        ctx = pa.probe_and_align(input_path=vid, work_dir=work, tier="fast", skip_whisper=True)
        wt = work / "words_tl.json"
        assert wt.is_file(), "words_tl.json must be written even without an audio stream"
        doc = json.loads(wt.read_text(encoding="utf-8"))
        assert doc["word_count"] == 0 and doc["words"] == [] and doc["words_tl"] == [] and "cadence_and_jcut_plan" in doc, doc
        assert any("no audio stream" in w for w in ctx["audit_warnings"]), ctx["audit_warnings"]
    print("[PASS] 04 video without audio: empty words_tl.json (normal schema) + 'no audio stream' warning")


# ---------------------------------------------------------------------------------------------- (5) decode timeout
def test_05_decode_timeout_and_errors() -> None:
    import probe_and_align as pa
    assert pa.DECODE_TIMEOUT_S > 0
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        tdp = Path(td)
        junk = tdp / "junk.wav"
        junk.write_bytes(os.urandom(2048))
        try:
            pa.decode_16k_f32_pcm(junk)
        except pa.ProbeMediaError as exc:
            assert "junk.wav" in str(exc) and "decode" in str(exc), exc
        else:
            raise AssertionError("a corrupt file must raise ProbeMediaError")
        wav = tdp / "tone.wav"
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=60", str(wav))
        try:
            pa.decode_16k_f32_pcm(wav, timeout_s=0.001)
        except pa.ProbeMediaError as exc:
            assert "timed out" in str(exc), exc
        else:
            raise AssertionError("a decode over its timeout must raise ProbeMediaError")
        assert len(pa.decode_16k_f32_pcm(wav, 1.0)) == 16000
    print("[PASS] 05 decode_16k_f32_pcm: timeout + ffmpeg failure -> ProbeMediaError with the file name")


# ---------------------------------------------------------------------------------------------- (6) studio_recipe input
def test_06_studio_recipe_validates_words() -> None:
    import studio_recipe as sr
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        tdp = Path(td)

        def run(words, duration: str) -> tuple[int, str]:
            wp = tdp / "w.json"
            wp.write_text(json.dumps(words) if not isinstance(words, str) else words, encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = sr.main(["--words", str(wp), "--duration", duration, "--out", str(tdp / "scenes.json")])
            return rc, err.getvalue()

        arr = [[f"w{i}", round(0.1 + i * 0.5, 3), round(0.4 + i * 0.5, 3)] for i in range(40)]
        rc, msg = run([], "20")
        assert rc == 2 and "0 words" in msg, (rc, msg)
        rc, msg = run({"words": []}, "20")
        assert rc == 2 and "0 words" in msg, (rc, msg)
        rc, msg = run('[["a", NaN, 1.0], ["b", 1.2, 1.5]]', "20")
        assert rc == 2 and "finite start / end" in msg and "2 words" in msg, (rc, msg)
        rc, msg = run(arr, "nan")
        assert rc == 2 and "got nan s" in msg, (rc, msg)
        rc, msg = run(arr, "10")
        assert rc == 2 and "got 10.0 s" in msg and "last word ends at 19.900 s" in msg, (rc, msg)
        rc, msg = run([{"word": "a", "start": 0.1}], "20")
        assert rc == 2, (rc, msg)
        dict_words = [{"word": w, "start": a, "end": b} for w, a, b in arr]
        rc_arr, _ = run(arr, "20.5")
        rc_dict, msg = run(dict_words, "20.5")
        assert rc_arr in (0, 3) and rc_dict == rc_arr, (rc_arr, rc_dict, msg)
        plan_arr = sr.plan_scenes(arr, 20.5)
        assert sr.plan_scenes(dict_words, 20.5) == plan_arr
        assert sr.plan_scenes({"words": [{"text": w, "start": a, "end": b} for w, a, b in arr]}, 20.5) == plan_arr
        try:
            sr.plan_scenes(arr, float("nan"))
        except ValueError:
            pass
        else:
            raise AssertionError("plan_scenes must reject a nan duration")
    print("[PASS] 06 studio_recipe: empty / nan / short-duration words exit 2; whisper dict words == array words")


# ---------------------------------------------------------------------------------------------- (7) help text
def test_07_help_text_reads_presets() -> None:
    r = subprocess.run([PY, str(TOOLS_DIR / "compile_and_verify.py"), "--help"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    help_txt = " ".join(r.stdout.split())
    prof = json.loads((SKILL_ROOT / "presets" / "profile_overrides.json").read_text(encoding="utf-8"))["audio_profiles"]
    tl = prof["tiktok_loud"]
    assert f"<= {tl['true_peak_dbtp']:g} dBTP" in help_txt and f"{tl['bgm_below_voice_db']:g} dB under voice" in help_txt, help_txt
    assert "-0.5 dBTP" not in help_txt and "6.6 dB" not in help_txt
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    doc = src.split('"""', 2)[1]
    assert "-0.5 dBTP" not in doc and "6.6 dB" not in doc
    s14 = prof["studio_14"]["_doc"].lower()
    assert "is owned by the scripts package" not in s14 and "wired" in s14, s14
    print("[PASS] 07 --audio-profile help reads tiktok_loud from the preset; studio_14 _doc says it is wired")


# ---------------------------------------------------------------------------------------------- (8) --display
def test_08_display_default_is_not_the_desktop() -> None:
    import compile_and_verify as cv
    old_argv, old_env = sys.argv, os.environ.pop("CRAFT_DISPLAY", None)
    try:
        sys.argv = ["x", "--spec", "a.json", "--out", "b.fcproj", "--work", "w"]
        assert cv.parse_args().display == ":93"
        os.environ["CRAFT_DISPLAY"] = ":77"
        assert cv.parse_args().display == ":77"
    finally:
        sys.argv = old_argv
        os.environ.pop("CRAFT_DISPLAY", None)
        if old_env is not None:
            os.environ["CRAFT_DISPLAY"] = old_env
    print("[PASS] 08 --display defaults to $CRAFT_DISPLAY or :93")


# ---------------------------------------------------------------------------------------------- (9) env_status
def test_09_env_status_required_checks() -> None:
    import env_status as es
    assert es.FILMCRAFT_MIN_VERSION == (0, 13, 0)
    assert es.version_tuple("filmcraft 0.13.0") == (0, 13, 0) and es.version_tuple("filmcraft 0.12.9") < es.FILMCRAFT_MIN_VERSION
    assert es.version_tuple("") is None
    saved = {k: os.environ.pop(k, None) for k in ("HF_HOME", "HF_HUB_CACHE")}
    try:
        with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
            hub = Path(td) / "hub"
            (hub / "models--Systran--faster-whisper-base").mkdir(parents=True)
            os.environ["HF_HUB_CACHE"] = str(hub)
            checks = {c["name"]: c for c in es.gather()}
            w = checks["whisper_model_small"]
            assert w["status"] == "MISSING" and w["required"] is True and str(hub) in w["detail"], w
            (hub / "models--Systran--faster-whisper-small" / "snapshots" / "abc").mkdir(parents=True)
            checks = {c["name"]: c for c in es.gather()}
            assert checks["whisper_model_small"]["status"] == "MISSING", "a snapshot without model.bin is an incomplete download"
            (hub / "models--Systran--faster-whisper-small" / "snapshots" / "abc" / "model.bin").write_bytes(b"x")
            checks = {c["name"]: c for c in es.gather()}
            assert checks["whisper_model_small"]["status"] == "OK", checks["whisper_model_small"]
            os.environ.pop("HF_HUB_CACHE")
            os.environ["HF_HOME"] = td
            assert es.hf_hub_dir() == hub
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    for name in ("filmcraft", "x_server", "python_imports", "ffmpeg_encoders", "whisper_model_small"):
        assert name in checks and checks[name]["required"] is True, (name, checks.get(name))
    assert "0.13.0" in checks["filmcraft"]["detail"] or "0.13.0" in checks["filmcraft"]["remedy"], checks["filmcraft"]
    for mod in ("numpy", "cv2", "PIL", "onnxruntime", "scipy", "faster_whisper"):
        assert mod in checks["python_imports"]["detail"], checks["python_imports"]
    for enc in ("libx264", "prores_ks", "qtrle"):
        assert enc in checks["ffmpeg_encoders"]["detail"], checks["ffmpeg_encoders"]
    assert "rembg" not in checks["matte_model"]["remedy"] or "curl" in checks["matte_model"]["remedy"]
    assert "run `rembg` once" not in (SKILL_ROOT / "scripts" / "env_status.py").read_text(encoding="utf-8")
    u2 = checks["matte_u2netp"]
    if u2["status"] == "MISSING":
        assert "BLOCKING" in u2["detail"] and "Look S" in u2["detail"] and "curl" in u2["remedy"], u2
    print("[PASS] 09 env_status: FilmCraft >= 0.13.0, X server, imports, encoders, HF cache + 'small' are required; curl remedy")


# ---------------------------------------------------------------------------------------------- (10) packaging
def test_10_requirements_and_install() -> None:
    req = (SKILL_ROOT / "requirements.txt").read_text(encoding="utf-8")
    pkgs = {ln.split("#")[0].strip().split(">")[0].split("<")[0].split("=")[0].strip().lower(): ln.split("#")[0].strip()
            for ln in req.splitlines() if ln.strip() and not ln.lstrip().startswith("#")}
    assert "soundfile" not in pkgs, pkgs
    assert "opencv-python" not in pkgs and "<5" in pkgs["opencv-python-headless"].replace(" ", ""), pkgs
    assert "<" in pkgs["numpy"] and "<" in pkgs["pillow"], pkgs
    low = req.lower()
    for dep in ("filmcraft", "xvfb", "chrome", "node", "ffmpeg"):
        assert dep in low, dep
    inst = (SKILL_ROOT / "install.sh").read_text(encoding="utf-8")
    assert "timeout" in inst and "900" in inst, "install.sh needs a per-test timeout"
    for dep in ("filmcraft", "xvfb", "chrome", "node", "ffmpeg"):
        assert dep in inst.lower(), dep
    print("[PASS] 10 requirements: no soundfile, opencv-python-headless<5, numpy/Pillow capped, system deps listed; install.sh timeout")


# ---------------------------------------------------------------------------------------------- (11) cache dirs
def test_11_cache_dir_env_atomic_and_pid() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        code = "import sys; sys.path.insert(0, %r); import compile_and_verify as cv; print(cv.CACHE_ROOT); print(cv.LEGACY_CACHE_ROOT)" % str(TOOLS_DIR)
        env = {k: v for k, v in os.environ.items() if k != "PFD_CACHE_DIR"}
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=120, env=env)
        lines = r.stdout.strip().splitlines()
        assert Path(lines[-2]) == Path.home() / ".cache" / "pro-filmcraft-director", r.stdout + r.stderr[-300:]
        assert Path(lines[-1]) == Path.home() / ".cache" / "opa-video-studio"
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=120, env={**env, "PFD_CACHE_DIR": td})
        assert Path(r.stdout.strip().splitlines()[-2]) == Path(td), r.stdout

        import compile_and_verify as cv
        tdp = Path(td)
        saved = (cv.SFX_ACOUSTIC_CACHE_PATH, cv.LEGACY_SFX_ACOUSTIC_CACHE_PATH, cv.BACKUP_DIR, cv._DISK_SFX_CACHE, cv._DISK_SFX_CACHE_DIRTY)
        real_replace, calls = os.replace, []
        try:
            cv.SFX_ACOUSTIC_CACHE_PATH = tdp / "new" / "sfx.json"
            cv.LEGACY_SFX_ACOUSTIC_CACHE_PATH = tdp / "old" / "sfx.json"
            cv.LEGACY_SFX_ACOUSTIC_CACHE_PATH.parent.mkdir()
            cv.LEGACY_SFX_ACOUSTIC_CACHE_PATH.write_text(json.dumps({"k": {"md5": "m"}}), encoding="utf-8")
            cv._DISK_SFX_CACHE = None
            assert cv._load_disk_sfx_cache() == {"k": {"md5": "m"}}, "legacy cache must be read as a fallback"
            cv._DISK_SFX_CACHE = {"k2": {"md5": "n"}}
            cv._DISK_SFX_CACHE_DIRTY = True

            def _rec(a, b):
                calls.append((str(a), str(b)))
                return real_replace(a, b)

            os.replace = _rec
            cv._flush_disk_sfx_cache()
            os.replace = real_replace
            assert calls and calls[-1][1] == str(cv.SFX_ACOUSTIC_CACHE_PATH), calls
            assert json.loads(cv.SFX_ACOUSTIC_CACHE_PATH.read_text(encoding="utf-8")) == {"k2": {"md5": "n"}}
            assert sorted(p.name for p in cv.SFX_ACOUSTIC_CACHE_PATH.parent.iterdir()) == ["sfx.json"], "temp file left behind"

            cv.BACKUP_DIR = tdp / "bk"
            proj = tdp / "p.fcproj"
            proj.write_text("{}", encoding="utf-8")
            bk = cv.backup_existing_fcproj(proj)
            assert bk is not None and str(os.getpid()) in bk.name and bk.parent == cv.BACKUP_DIR, bk
        finally:
            os.replace = real_replace
            (cv.SFX_ACOUSTIC_CACHE_PATH, cv.LEGACY_SFX_ACOUSTIC_CACHE_PATH, cv.BACKUP_DIR, cv._DISK_SFX_CACHE, cv._DISK_SFX_CACHE_DIRTY) = saved

        import probe_and_align as pa
        old = os.environ.get("PFD_CACHE_DIR")
        os.environ["PFD_CACHE_DIR"] = str(tdp / "pa")
        try:
            b = pa.backup_fcproj(proj)
            assert b.parent == tdp / "pa" / "backup", b
        finally:
            os.environ.pop("PFD_CACHE_DIR", None)
            if old is not None:
                os.environ["PFD_CACHE_DIR"] = old
    for rel in ("scripts/tools/compile_and_verify.py", "scripts/tools/probe_and_align.py"):
        src = (SKILL_ROOT / rel).read_text(encoding="utf-8")
        assert "PFD_CACHE_DIR" in src, rel
    print("[PASS] 11 PFD_CACHE_DIR (default ~/.cache/pro-filmcraft-director), legacy read fallback, os.replace flush, PID backup name")


# ---------------------------------------------------------------------------------------------- (12) execution tiers
def test_12_execution_tiers_doc_truth() -> None:
    doc = json.loads((SKILL_ROOT / "presets" / "execution_tiers.json").read_text(encoding="utf-8"))
    note = doc.get("_doc_v791", "")
    assert "--tier full" in note and "bgm_lra_offset_optimizer" in note and "R35" in note, note
    assert doc["tiers"]["studio"]["skipped_heavy_gates"] == ["bgm_lra_offset_optimizer", "post_aac_true_peak_guard_r35"]
    print("[PASS] 12 execution_tiers.json _doc_v791: studio compiles with --tier full, so bgm_lra and R35 run")


# ---------------------------------------------------------------------------------------------- (13) abs paths / NFC
def test_13_abs_paths_and_nfc() -> None:
    import compile_and_verify as cv
    for p in ("C:\\Users\\a\\clip.mp4", "D:/media/a.mov", "/Users/a/clip.mp4", "/srv/x.wav", "/home/a.mp4", "\\\\nas\\share\\a.mp4"):
        assert cv._is_abs_media_path(p), p
    for p in ("assets/a.mp4", "a.mp4", "./a.mp4", "", "C:", "https://x/y.mp4"):
        assert not cv._is_abs_media_path(p), p
    nfd = unicodedata.normalize("NFD", "/tmp/Tiếng Việt/a-roll.mp4")
    nfc = unicodedata.normalize("NFC", nfd)
    assert nfd != nfc and cv._same_media_path(nfd, nfc) and not cv._same_media_path(nfc, "/tmp/other.mp4")
    assert cv._is_v1_broll_clip({"src": nfd, "name": "x"}, nfc) == cv._is_v1_broll_clip({"src": nfc, "name": "x"}, nfc)
    print("[PASS] 13 absolute paths (POSIX root, Windows drive, UNC) detected; NFC/NFD media paths compare equal")


# ---------------------------------------------------------------------------------------------- (14) timeout + lock
def test_14_timeout_kills_children_and_lock_race() -> None:
    import probe_and_align as pa
    with tempfile.TemporaryDirectory(prefix="pfd791_") as td:
        pid_file = Path(td) / "child.pid"
        code = (
            "import subprocess, sys, time; sys.path.insert(0, %r); import probe_and_align as pa\n"
            "c = subprocess.Popen(['sleep', '60']); open(%r, 'w').write(str(c.pid)); time.sleep(0.2)\n"
            "pa._abort_run(124)\n"
        ) % (str(TOOLS_DIR), str(pid_file))
        for new_session in (False, True):
            r = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=120, start_new_session=new_session)
            assert r.returncode == 124, (r.returncode, r.stderr[-400:])
            child = int(pid_file.read_text())
            for _ in range(50):
                try:
                    state = Path(f"/proc/{child}/stat").read_text().rsplit(")", 1)[1].split()[0]
                except (FileNotFoundError, ProcessLookupError):
                    break  # gone (killed and reaped)
                if state == "Z":
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(f"child sleep {child} survived _abort_run (new_session={new_session})")
        src = (TOOLS_DIR / "probe_and_align.py").read_text(encoding="utf-8")
        on_timeout = src.split("def _on_timeout")[1].split("watchdog = ")[0]
        assert "_abort_run(124)" in on_timeout and "os._exit(124)" not in on_timeout, on_timeout

        work = Path(td) / "work"
        work.mkdir()
        real_open = os.open

        def _race(path, flags, *a):
            if str(path).endswith(pa.LOCK_NAME):
                raise FileExistsError(path)
            return real_open(path, flags, *a)

        os.open = _race
        try:
            pa.acquire_lock(work)
        except pa.ProbeLockError as exc:
            assert "lock" in str(exc) and pa.LOCK_NAME in str(exc), exc
        else:
            raise AssertionError("a lock race must raise ProbeLockError")
        finally:
            os.open = real_open
    print("[PASS] 14 _abort_run kills child processes (inherited and own process group) and exits 124; lock race -> ProbeLockError")


if __name__ == "__main__":
    test_01_gate3_edit_rules_crash_fails()
    test_02_gate3_skipped_is_honest()
    test_03_empty_or_corrupt_video_rejected()
    test_04_no_audio_writes_empty_words_tl()
    test_05_decode_timeout_and_errors()
    test_06_studio_recipe_validates_words()
    test_07_help_text_reads_presets()
    test_08_display_default_is_not_the_desktop()
    test_09_env_status_required_checks()
    test_10_requirements_and_install()
    test_11_cache_dir_env_atomic_and_pid()
    test_12_execution_tiers_doc_truth()
    test_13_abs_paths_and_nfc()
    test_14_timeout_kills_children_and_lock_race()
    print("TẤT CẢ ĐẠT (audit core v7.9.1)")
