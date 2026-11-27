#!/usr/bin/env python3
"""
Stability-core verification for `pro-filmcraft-director` (package P1; version-agnostic: banners are compared with the module constants).

Covers: undefined-name scan, typography self-tests, matte-model resolver, ingest (`probe_and_align`),
`spec_from_plan`, `env_status`, vendored `ovs_core` integrity, audio/style profiles and version banners.
Never runs whisper (host load is high): every ASR path is skipped or unit-tested on synthetic data.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
VENDOR_DIR = SCRIPTS_DIR / "vendor" / "ovs_core"
FIXTURES = Path(__file__).resolve().parent / "fixtures_stability"
NON_PORTABLE = "/home/" + "thanh"  # split so test_skill_v73 / the gate grep do not flag this file
PY = os.environ.get("FILMCRAFT_VENV_PYTHON") or str(Path.home() / ".venvs/video-skills/bin/python3")
if not Path(PY).is_file():
    PY = sys.executable

for _p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _run(cmd: list[str], timeout: int = 600, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PFD_MATTE_MODEL", "U2NETP_ONNX_PATH", "PFD_OVS_DIR")}
    env.update(extra)
    return env


# ---------------------------------------------------------------------------
# (a) undefined-name scan
# ---------------------------------------------------------------------------

_MODULE_DUNDERS = {"__file__", "__name__", "__doc__", "__spec__", "__package__", "__builtins__", "__loader__", "__path__"}


def _undefined_names(src: str, filename: str) -> list[str]:
    """Flow-insensitive pyflakes-style scan: names that are loaded but never bound anywhere in the module."""
    try:
        from pyflakes.api import check  # type: ignore[import-not-found]  # noqa: F401
        from pyflakes import checker as _chk  # type: ignore[import-not-found]

        tree = ast.parse(src, filename)
        chk = _chk.Checker(tree, filename=filename)
        return [m.message % m.message_args for m in chk.messages if type(m).__name__ == "UndefinedName"]
    except ImportError:
        pass

    tree = ast.parse(src, filename)
    bound: set[str] = set(dir(builtins)) | _MODULE_DUNDERS
    loads: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    return []  # cannot reason about star imports
                bound.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                bound.add(node.id)
            else:
                loads.append((node.id, node.lineno))
        elif hasattr(ast, "MatchAs") and isinstance(node, (ast.MatchAs, ast.MatchStar)) and getattr(node, "name", None):
            bound.add(node.name)  # type: ignore[arg-type]
        elif hasattr(ast, "MatchMapping") and isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
    return [f"{name} (line {ln})" for name, ln in loads if name not in bound]


def test_a_no_undefined_names_in_scripts() -> None:
    problems: list[str] = []
    files = sorted(p for p in SCRIPTS_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    assert len(files) >= 10
    for pf in files:
        for msg in _undefined_names(pf.read_text(encoding="utf-8"), str(pf)):
            problems.append(f"{pf.relative_to(SKILL_ROOT)}: undefined name {msg}")
    assert not problems, "Undefined names found:\n  " + "\n  ".join(problems[:20])
    # the scanner itself must catch the historical bug class
    assert _undefined_names("def f():\n    return os.environ\n", "<synthetic>"), "scanner missed a missing `import os`"
    print(f"[PASS] a: undefined-name scan clean over {len(files)} files")


# ---------------------------------------------------------------------------
# (b) typography self-tests
# ---------------------------------------------------------------------------

def test_b_typography_self_tests() -> None:
    for flag in ("--self-test", "--self-test-v71"):
        r = _run([PY, str(TOOLS_DIR / "typography_composer.py"), flag], timeout=600)
        assert r.returncode == 0, f"typography_composer {flag} exit={r.returncode}\n{(r.stderr or r.stdout)[-800:]}"
    print("[PASS] b: typography_composer --self-test / --self-test-v71 exit 0")


# ---------------------------------------------------------------------------
# (c) matte resolver + compositor CLI
# ---------------------------------------------------------------------------

def test_c_matte_resolver_message_and_override() -> None:
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import fast_studio_compositor as fsc\n"
        "try:\n"
        "    fsc.resolve_matte_model_path()\n"
        "except FileNotFoundError as e:\n"
        "    print('ERR::' + str(e))\n"
        "else:\n"
        "    print('NOERR')\n"
    ) % str(TOOLS_DIR)
    with tempfile.TemporaryDirectory(prefix="pfd_home_") as home:
        r = _run([PY, "-c", code], env=_clean_env(HOME=home))
        assert r.returncode == 0, r.stderr[-600:]
        msg = r.stdout.split("ERR::", 1)[-1]
        assert "ERR::" in r.stdout, f"expected FileNotFoundError, got: {r.stdout!r}"
        for needle in ("PFD_MATTE_MODEL", "u2netp.onnx", "birefnet-portrait.onnx"):
            assert needle in msg, f"error message lacks {needle!r}: {msg}"

        fake = Path(home) / "custom.onnx"
        fake.write_bytes(b"x")
        code2 = code.replace("fsc.resolve_matte_model_path()", "print('OK::' + str(fsc.resolve_matte_model_path()))")
        r2 = _run([PY, "-c", code2], env=_clean_env(HOME=home, PFD_MATTE_MODEL=str(fake)))
        assert f"OK::{fake}" in r2.stdout, f"PFD_MATTE_MODEL override ignored: {r2.stdout!r} {r2.stderr[-300:]}"

        # birefnet fallback when only that model is installed
        bdir = Path(home) / ".rembg/models/birefnet-portrait"
        bdir.mkdir(parents=True)
        (bdir / "birefnet-portrait.onnx").write_bytes(b"x")
        r3 = _run([PY, "-c", code2], env=_clean_env(HOME=home))
        assert "birefnet-portrait.onnx" in r3.stdout and "OK::" in r3.stdout, r3.stdout + r3.stderr[-300:]
    print("[PASS] c: matte resolver error message, env override and birefnet fallback")


def test_c2_compositor_cli() -> None:
    r = _run([PY, str(TOOLS_DIR / "fast_studio_compositor.py"), "--help"])
    assert r.returncode == 0, r.stderr[-500:]
    assert "--draft" in r.stdout and "--master" in r.stdout and "--list-options" in r.stdout
    r2 = _run([PY, str(TOOLS_DIR / "fast_studio_compositor.py"), "--list-options"])
    assert r2.returncode == 0 and "draft" in r2.stdout and "master" in r2.stdout, r2.stdout + r2.stderr[-300:]
    print("[PASS] c2: fast_studio_compositor CLI --help / --list-options")


# ---------------------------------------------------------------------------
# (d) probe_and_align
# ---------------------------------------------------------------------------

def _make_tone_clip(path: Path, with_video: bool = True, dur: float = 3.0) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if with_video:
        cmd += ["-f", "lavfi", "-i", f"testsrc=size=320x240:rate=30:duration={dur}"]
    cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}"]
    if with_video:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast"]
    cmd += ["-c:a", "aac", "-shortest", str(path)]
    r = _run(cmd, timeout=120)
    assert r.returncode == 0 and path.is_file(), f"ffmpeg fixture failed: {r.stderr[-400:]}"


def test_d_probe_skip_whisper_writes_media_probe() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_probe_") as td:
        clip = Path(td) / "tone.mp4"
        work = Path(td) / "work"
        _make_tone_clip(clip)
        r = _run([PY, str(TOOLS_DIR / "probe_and_align.py"), "--input", str(clip), "--work", str(work),
                  "--skip-whisper", "--tier", "fast"], timeout=300)
        assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
        mp = json.loads((work / "media_probe.json").read_text(encoding="utf-8"))
        assert mp, "media_probe.json empty"
        import probe_and_align as _pa
        assert f"[PROBE & ALIGN v{_pa.VERSION} OK]" in r.stdout, r.stdout[-400:]
        assert "speech_cadence_points=" in r.stdout and " cuts=" not in r.stdout, r.stdout[-400:]
        vc = json.loads((work / "visual_cuts.json").read_text(encoding="utf-8"))
        assert isinstance(vc.get("cuts"), list) and "scene_threshold" in vc
        ctx = json.loads((work / "workspace_context.json").read_text(encoding="utf-8"))
        cad = ctx["speech_summary"]["cadence_summary"]
        assert "speech_cadence_points" in cad and cad["speech_cadence_points"] == cad["boundary_count"]
    print("[PASS] d1: probe_and_align --skip-whisper writes media_probe.json, visual_cuts.json, new label")


def test_d_probe_music_only_has_no_speech() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_music_") as td:
        clip = Path(td) / "music.mp4"
        work = Path(td) / "work"
        _make_tone_clip(clip)
        r = _run([PY, str(TOOLS_DIR / "probe_and_align.py"), "--input", str(clip), "--work", str(work),
                  "--music-only", "--tier", "fast"], timeout=300)
        assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
        ctx = json.loads((work / "workspace_context.json").read_text(encoding="utf-8"))
        assert ctx["speech_summary"]["has_speech"] is False
        assert ctx["speech_summary"]["word_count"] == 0
        assert (work / "media_probe.json").is_file()
    print("[PASS] d2: --music-only yields has_speech=false")


def test_d_probe_units() -> None:
    import numpy as np
    import probe_and_align as pa

    # repetition filter: a phrase repeated >=3 times in a row is dropped entirely
    phrase = ["Nói", "chạy", "ra", "nhanh", "đi"]
    words: list[list] = []
    t = 0.0
    for w in ["Xin", "chào"] + phrase * 3 + ["cảm", "ơn", "các", "bạn"] + phrase * 2:
        words.append([w, round(t, 2), round(t + 0.2, 2)])
        t += 0.25
    kept = [w[0] for w in pa.drop_repeated_phrases(words, min_repeats=3)]
    assert kept == ["Xin", "chào", "cảm", "ơn", "các", "bạn"] + phrase * 2, kept
    same = [["ừ", 0.0, 0.1], ["ừ", 0.1, 0.2], ["ừ", 0.2, 0.3], ["rồi", 0.4, 0.5]]
    assert [w[0] for w in pa.drop_repeated_phrases(same, min_repeats=3)] == ["rồi"]

    # visual cut clustering within 0.3 s
    assert pa.cluster_cut_times([0.5, 0.6, 0.75, 2.0, 2.1, 5.0], gap_s=0.3) == [0.5, 2.0, 5.0]
    assert pa.cluster_cut_times([], gap_s=0.3) == []

    # loudness audit warnings
    assert pa.loudness_audit_warnings(-8.0, -3.0) and pa.loudness_audit_warnings(-14.0, -0.2)
    assert pa.loudness_audit_warnings(-14.0, -3.0) == []
    assert pa.loudness_audit_warnings(None, None) == []

    # whisper thread policy
    assert pa.resolve_whisper_threads(None, load=100.0, cpus=8) == 1
    assert pa.resolve_whisper_threads(3, load=100.0, cpus=8) == 3
    assert pa.resolve_whisper_threads(None, load=0.5, cpus=16) == min(6, max(4, 16 // 2))

    # RMS/VAD no-speech gate on pure tone and silence
    sr = 16000
    tt = np.arange(sr * 3) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * tt)).astype(np.float32)
    assert pa.speech_gate(tone, sr)["has_speech"] is False
    assert pa.speech_gate(np.zeros(sr * 3, dtype=np.float32), sr)["has_speech"] is False
    print("[PASS] d3: repetition filter, cut clustering, loudness warnings, thread policy, no-speech gate")


def test_d_probe_lock_file_refuses_duplicate() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_lock_") as td:
        clip = Path(td) / "tone.mp4"
        work = Path(td) / "work"
        work.mkdir()
        _make_tone_clip(clip, dur=2.0)
        lock = work / ".probe_and_align.lock"
        lock.write_text(json.dumps({"pid": os.getpid(), "started": 0}), encoding="utf-8")  # live pid = this test
        base = [PY, str(TOOLS_DIR / "probe_and_align.py"), "--input", str(clip), "--work", str(work),
                "--skip-whisper", "--tier", "fast"]
        r = _run(base, timeout=120)
        assert r.returncode != 0 and "lock" in (r.stderr + r.stdout).lower(), (r.stderr or r.stdout)[-500:]
        assert lock.is_file(), "refused run must not delete the live lock"
        r2 = _run(base + ["--force"], timeout=300)
        assert r2.returncode == 0, (r2.stderr or r2.stdout)[-500:]
        assert not lock.exists(), "lock must be released after a successful run"
        # stale lock (dead pid) is taken over silently
        lock.write_text(json.dumps({"pid": 2 ** 22 + 12345, "started": 0}), encoding="utf-8")
        r3 = _run(base, timeout=300)
        assert r3.returncode == 0, (r3.stderr or r3.stdout)[-500:]
    print("[PASS] d4: lock file refuses duplicate run, --force overrides, stale lock reclaimed")


# ---------------------------------------------------------------------------
# (e) spec_from_plan
# ---------------------------------------------------------------------------

def test_e_spec_from_plan_sets_audio_false() -> None:
    sys.path.insert(0, str(VENDOR_DIR / "scripts" / "apps" / "craft-handoff" / "tools"))
    with tempfile.TemporaryDirectory(prefix="pfd_spec_") as td:
        media = Path(td) / "media"
        media.mkdir()
        _make_tone_clip(media / "a-roll-1.mp4", dur=3.0)
        out = Path(td) / "out" / "x.craft.json"
        r = _run([PY, str(TOOLS_DIR / "spec_from_plan.py"), "--plan", str(FIXTURES / "plan.json"),
                  "--words", str(FIXTURES / "words_tl.json"), "--media-dir", str(media), "--out", str(out)], timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
        spec = json.loads(out.read_text(encoding="utf-8"))
        tracks = {t["name"]: t for t in spec["tracks"]}
        v1 = next(t for t in spec["tracks"] if t["type"] == "video")
        assert v1["name"].startswith("V1"), v1["name"]
        assert v1["clips"][0]["audio"] is False, "V1 clip must have audio:false when a VOICE track exists"
        voice = next(t for t in spec["tracks"] if t["type"] == "audio" and "giọng" in t["name"].lower())
        assert voice["clips"] and Path(voice["clips"][0]["src"]).is_file()
        assert any(t["type"] == "text" for t in spec["tracks"]), tracks.keys()
        # the heuristic audio_levels uses must classify the voice track
        import compile_and_verify as cv
        assert cv.classify_audio_role(voice["name"], voice["clips"][0]) == "voice"
        # spec must pass the vendored fc_build validator (no FilmCraft needed)
        import importlib.util
        mod_path = VENDOR_DIR / "scripts" / "apps" / "craft-handoff" / "tools" / "fc_build.py"
        sp = importlib.util.spec_from_file_location("pfd_fc_build", mod_path)
        fcb = importlib.util.module_from_spec(sp)
        assert sp.loader is not None
        sp.loader.exec_module(fcb)
        fcb.validate(spec)

        # without any voice source: --no-voice-track keeps embedded audio on V1
        out2 = Path(td) / "out" / "y.craft.json"
        r2 = _run([PY, str(TOOLS_DIR / "spec_from_plan.py"), "--plan", str(FIXTURES / "plan.json"),
                   "--words", str(FIXTURES / "words_tl.json"), "--media-dir", str(media), "--out", str(out2),
                   "--no-voice-track"], timeout=120)
        assert r2.returncode == 0, (r2.stderr or r2.stdout)[-500:]
        v1b = next(t for t in json.loads(out2.read_text(encoding="utf-8"))["tracks"] if t["type"] == "video")
        assert v1b["clips"][0].get("audio", True) is True
    print("[PASS] e: spec_from_plan sets audio:false + valid voice track + passes fc_build.validate")


# ---------------------------------------------------------------------------
# (f) env_status
# ---------------------------------------------------------------------------

def test_f_env_status_json() -> None:
    r = _run([PY, str(SCRIPTS_DIR / "env_status.py"), "--json"], timeout=120)
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    doc = json.loads(r.stdout)
    checks = doc["checks"]
    names = {c["name"] for c in checks}
    for need in ("ffmpeg", "ffprobe", "node", "chrome", "venv", "whisper_weights", "matte_model", "fonts",
                 "ovs_core", "filmcraft", "ffskill_bridge"):
        assert need in names, f"env_status missing check {need}: {sorted(names)}"
    for c in checks:
        assert c["status"] in ("OK", "MISSING", "WARN") and "remedy" in c, c
    r2 = _run([PY, str(SCRIPTS_DIR / "env_status.py")], timeout=120)
    assert r2.returncode == 0 and ("OK" in r2.stdout or "MISSING" in r2.stdout)
    print("[PASS] f: env_status --json parses; plain mode exit 0")


# ---------------------------------------------------------------------------
# (g) banners
# ---------------------------------------------------------------------------

def _skill_version() -> str:
    """The one shared version source: the `vX.Y.Z` in the SKILL.md frontmatter."""
    m = re.search(r"\bv(\d+\.\d+\.\d+)", (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    assert m, "SKILL.md frontmatter must carry a vX.Y.Z version"
    return m.group(1)


def test_g_banners_match_module_versions() -> None:
    import compile_and_verify as cv
    import probe_and_align as pa
    import dviet_smooth_camera_engine as eng
    import env_status
    import flicker_schedule
    import motion_gate
    import spec_from_plan
    import studio_recipe
    current = _skill_version()
    assert cv.COMPILER_VERSION == pa.VERSION == current, (cv.COMPILER_VERSION, pa.VERSION, current)
    for name, ver in (("dviet_smooth_camera_engine.ENGINE_VERSION", eng.ENGINE_VERSION), ("env_status.VERSION", env_status.VERSION),
                      ("flicker_schedule.VERSION", flicker_schedule.VERSION), ("motion_gate.VERSION", motion_gate.VERSION),
                      ("spec_from_plan.VERSION", spec_from_plan.VERSION), ("studio_recipe.VERSION", studio_recipe.VERSION),
                      ("presets/studio_scene_recipe.json version",
                       json.loads((SKILL_ROOT / "presets" / "studio_scene_recipe.json").read_text(encoding="utf-8"))["version"])):
        assert ver == current, f"{name} is {ver}, SKILL.md says {current}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", cv.COMPILER_VERSION), cv.COMPILER_VERSION
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    assert "[Compiler v{COMPILER_VERSION}]" in src
    for rel in ("scripts/tools/compile_and_verify.py", "scripts/tools/probe_and_align.py",
                "scripts/tools/fast_studio_compositor.py", "scripts/tools/typography_composer.py",
                "scripts/tools/fc_export.py", "scripts/tools/filmcraft_cli.py", "scripts/tools/spec_from_plan.py", "scripts/env_status.py",
                "scripts/ffskill_bridge.py", "scripts/tools/flicker_schedule.py", "scripts/tools/studio_recipe.py"):
        head = (SKILL_ROOT / rel).read_text(encoding="utf-8")[:2500]
        assert cv.COMPILER_VERSION in head, f"{rel}: module docstring lacks {cv.COMPILER_VERSION}"
    print("[PASS] g: version constants and banners match the SKILL.md version")


# ---------------------------------------------------------------------------
# (h) vendored ovs_core, profiles, optional bridge
# ---------------------------------------------------------------------------

def test_h_vendor_integrity_and_paths() -> None:
    prov = (VENDOR_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    # v7.9.1: the source is a snapshot label + version / date, never a personal path; rules.json carries the documented v7.9.1 patch
    assert "opa-video-studio skill (snapshot)" in prov and re.search(r"\b\d+\.\d+\.\d+\b", prov) and "Copy date:" in prov
    assert "/home/" not in prov, "PROVENANCE must not record a local path"
    assert "patched in v7.9.1" in prov
    listed = re.findall(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", prov)
    assert len(listed) >= 14, f"PROVENANCE lists {len(listed)} files"
    for rel, digest in listed:
        fp = VENDOR_DIR / rel
        assert fp.is_file(), f"PROVENANCE lists missing file {rel}"
        assert hashlib.sha256(fp.read_bytes()).hexdigest() == digest, f"sha256 drift in {rel}"
    for need in ("spec_lint.py", "audio_levels.py", "edit_rules.py", "audit_sfx.py", "fc_fast_qa.py"):
        assert (VENDOR_DIR / "scripts" / need).is_file(), need
    for need in ("fc_build_fast.py", "fc_build.py", "craftctl.py", "fc_export.py"):
        assert (VENDOR_DIR / "scripts" / "apps" / "craft-handoff" / "tools" / need).is_file(), need
    assert (VENDOR_DIR / "rules.json").is_file()
    for pf in VENDOR_DIR.rglob("*.py"):
        s = pf.read_text(encoding="utf-8")
        assert NON_PORTABLE not in s, pf
        for bad in ("~/.claude", ".claude/skills", ".gemini", "opa-video-studio/scripts"):
            assert bad not in s, f"{pf.relative_to(SKILL_ROOT)} references {bad}"
    import compile_and_verify as cv
    for const in (cv.AUDIO_LEVELS_PY, cv.SPEC_LINT_PY, cv.EDIT_RULES_PY, cv.FC_BUILD_FAST_PY, cv.FC_FAST_QA_PY,
                  cv.AUDIT_SFX_PY, cv.DEFAULT_RULES_JSON):
        assert VENDOR_DIR in Path(const).parents, f"{const} is not vendored"
        assert Path(const).is_file(), const
    print("[PASS] h1: vendored ovs_core complete, hashed, scrubbed and wired")


def test_h_vendored_gates_run_standalone() -> None:
    spec = {
        "name": "t", "fps": 30, "width": 1080, "height": 1920, "duration": 3.0,
        "tracks": [{"type": "video", "name": "V1", "clips": [{"src": "/nonexistent/a.mp4", "at": 0, "dur": 3.0}]}],
    }
    with tempfile.TemporaryDirectory(prefix="pfd_vend_") as td:
        sp = Path(td) / "t.craft.json"
        sp.write_text(json.dumps(spec), encoding="utf-8")
        r = _run([PY, str(VENDOR_DIR / "scripts" / "spec_lint.py"), str(sp), "--json"], timeout=60)
        assert r.stdout.strip().startswith("["), (r.stdout + r.stderr)[-400:]
        r2 = _run([PY, str(VENDOR_DIR / "scripts" / "edit_rules.py"), "audit", str(sp), "--json"], timeout=60)
        assert r2.stdout.strip().startswith("[") or r2.stdout.strip() == "", (r2.stdout + r2.stderr)[-400:]
        r3 = _run([PY, str(VENDOR_DIR / "scripts" / "apps" / "craft-handoff" / "tools" / "fc_export.py"), "--help"])
        assert r3.returncode == 0
    print("[PASS] h2: vendored spec_lint / edit_rules / fc_export run standalone")


def test_h_ovs_dir_override_never_falls_back_silently() -> None:
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import compile_and_verify as cv\n"
        "print(cv.OPA_SKILL)\n"
    ) % str(TOOLS_DIR)
    r = _run([PY, "-c", code], env=_clean_env())
    assert Path(r.stdout.strip()) == VENDOR_DIR, r.stdout + r.stderr[-300:]
    r2 = _run([PY, "-c", code], env=_clean_env(PFD_OVS_DIR="/nonexistent/ovs"))
    assert r2.returncode != 0 or "/nonexistent/ovs" in r2.stdout, "bad PFD_OVS_DIR must fail loudly or be honoured, not fall back"
    assert ".gemini" not in r.stdout
    print("[PASS] h3: PFD_OVS_DIR honoured, default is vendored, no silent ~/.gemini fallback")


def test_h_audio_profile_and_dviet_profile() -> None:
    import compile_and_verify as cv
    with tempfile.TemporaryDirectory(prefix="pfd_prof_") as td:
        wd = Path(td)
        p_default = cv.build_effective_rules(wd, -16.0)
        assert Path(p_default) == cv.DEFAULT_RULES_JSON
        p = cv.build_effective_rules(wd, -12.0, audio_profile="tiktok_loud")
        a = json.loads(Path(p).read_text(encoding="utf-8"))["params"]["audio"]
        assert a["master_lufs"]["final"] == -12.0
        assert a["master_true_peak_dbtp"] == -1.0
        bed = a["bgm_below_voice_lu"]
        assert bed["target"] == 14.0 and bed["min"] == 12.0 and bed["max"] == 17.0, bed
        assert a["bgm_speech_floor_lu"] < 10.0
        assert a["no_ducking"] is True
    prof = cv.resolve_audio_profile("tiktok_loud")
    assert prof["target_lufs"] == -12.0 and prof["true_peak_dbtp"] == -1.0 and prof["limiter_db"] == -1.2
    assert cv.resolve_audio_profile("platform")["target_lufs"] == -16.0

    def spec_with(events: list[tuple[str, float, float]], n_cuts: int = 20) -> dict:
        v1 = [{"name": f"S{i}", "src": f"/x/s{i}.mp4", "at": i * 1.0, "dur": 1.0} for i in range(n_cuts)]
        fx = [{"name": nm, "src": "", "at": at, "dur": dur, "preset": nm} for nm, at, dur in events]
        return {"width": 1080, "height": 1920, "duration": float(n_cuts), "meta": {},
                "tracks": [{"type": "video", "name": "V1", "clips": v1}, {"type": "video", "name": "V2 · FX", "clips": fx}]}

    base_meta = {"industry_skin": "dental_clinic"}
    # default profile: warm film burn is vetoed
    s = spec_with([("film_burn", 3.0, 0.5)])
    s["meta"] = base_meta
    res_def = cv.audit_industry_cri100_veto(s, raw_spec=s, spec_meta=base_meta, strict_cri100=True)
    assert "CRI100_FORBIDDEN_WARM_FILM_BURN" in res_def["warning_codes"]
    # dviet profile: lifted for a capped (<=0.6 s) event
    res_dv = cv.audit_industry_cri100_veto(s, raw_spec=s, spec_meta=base_meta, strict_cri100=True, profile="dviet")
    assert "CRI100_FORBIDDEN_WARM_FILM_BURN" not in res_dv["warning_codes"], res_dv["warning_codes"]
    # ... but not for an event longer than 0.6 s
    s2 = spec_with([("film_burn", 3.0, 0.9)])
    s2["meta"] = base_meta
    res_long = cv.audit_industry_cri100_veto(s2, raw_spec=s2, spec_meta=base_meta, strict_cri100=True, profile="dviet")
    assert "CRI100_FORBIDDEN_WARM_FILM_BURN" in res_long["warning_codes"]
    # flash family above 20% of cuts: lift revoked
    many = [("flash_cut", 1.0 + i, 0.2) for i in range(6)]
    cap = cv.audit_dviet_wash_flash_caps(spec_with(many, n_cuts=20))
    assert cap["flash_family_share"] > 0.20 and cap["lift_allowed"] is False
    ok = cv.audit_dviet_wash_flash_caps(spec_with([("flash_cut", 3.0, 0.2), ("film_burn", 9.0, 0.5)], n_cuts=20))
    assert ok["lift_allowed"] is True and ok["soft_repeat_warnings"] == []
    rep = cv.audit_dviet_wash_flash_caps(spec_with([("flash_cut", 3.0, 0.2), ("flash_cut", 5.0, 0.2)], n_cuts=20))
    assert rep["soft_repeat_warnings"], "same kind within 4 cuts must produce a SOFT warning"
    # 4-cut grammar stays hard: the over-transition limit is untouched by profiles
    ov = json.loads((SKILL_ROOT / "presets" / "profile_overrides.json").read_text(encoding="utf-8"))
    assert ov["profiles"]["dviet"]["keeps_hard"] == ["OVER_TRANSITIONED_SPAM", "FOUR_CUT_GRAMMAR"]
    assert ov["profiles"]["default"] == {}
    print("[PASS] h4: tiktok_loud rules + dviet scoped veto lift (capped), 4-cut grammar stays HARD")


def test_h_ffskill_bridge_is_optional() -> None:
    import ffskill_bridge as fb
    assert hasattr(fb, "ffskill_available")
    if not fb.ffskill_available():
        r = _run([PY, str(SCRIPTS_DIR / "ffskill_bridge.py")])
        assert "Traceback" not in r.stderr, r.stderr[-500:]
        assert "ffmpeg-skill" in (r.stdout + r.stderr)
        try:
            fb.ffskill_doctor()
        except fb.FfskillUnavailable as e:
            assert "ffmpeg-skill" in str(e)
        else:
            raise AssertionError("ffskill_doctor must raise FfskillUnavailable when sibling repo is missing")
    print("[PASS] h5: ffskill_bridge optional (clean message when sibling repo missing)")


def test_h_filmcraft_cli_resolver_returns_the_shim() -> None:
    """`filmcraft-cli` never existed: the resolver hands out the control-bridge shim, or None when the `filmcraft` binary is absent."""
    import compile_and_verify as cv
    shim = TOOLS_DIR / "filmcraft_cli.py"
    assert shim.is_file() and Path(cv.FILMCRAFT_CLI_PY) == shim.resolve()
    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "import json, compile_and_verify as cv\n"
        "print(json.dumps(cv._filmcraft_cli_cmd(warn=False)))\n"
    ) % str(TOOLS_DIR)
    # 1) filmcraft binary present (fake executable on PATH) -> [python, shim]
    with tempfile.TemporaryDirectory(prefix="pfd_fakebin_") as home, tempfile.TemporaryDirectory(prefix="pfd_fakebin_dir_") as bindir:
        fake = Path(bindir) / "filmcraft"
        fake.write_text("#!/bin/sh\necho 'filmcraft 0.0.0'\n", encoding="utf-8")
        fake.chmod(0o755)
        r = _run([PY, "-c", probe], env=_clean_env(HOME=home, PATH=f"{bindir}:/usr/bin:/bin"))
        cmd = json.loads(r.stdout.strip().splitlines()[-1])
        assert len(cmd) == 2 and Path(cmd[0]).is_file() and Path(cmd[1]) == shim.resolve(), (cmd, r.stderr[-300:])
    # 2) no filmcraft binary -> None, and the warning names `filmcraft`, not `filmcraft-cli`
    with tempfile.TemporaryDirectory(prefix="pfd_nobin_") as home:
        env = _clean_env(HOME=home, PATH="/usr/bin:/bin")
        env.pop("CRAFT_BIN_DIR", None)
        r = _run([PY, "-c", probe.replace("warn=False", "warn=True")], env=env)
        assert r.stdout.strip().splitlines()[-1] == "null", r.stdout + r.stderr[-300:]
        assert "`filmcraft` not found" in r.stderr and "filmcraft-cli" not in r.stderr, r.stderr[-300:]
        # the shim itself answers with a clean exit-2 JSON message (no traceback) when the binary is missing
        r2 = _run([PY, str(shim), "--project", "x.fcproj", "render", "--seconds", "0.5", "--out", "x.png"], env=env)
        assert r2.returncode == 2 and "Traceback" not in r2.stderr, (r2.returncode, r2.stderr[-300:])
        msg = json.loads(r2.stdout.strip().splitlines()[-1])
        assert msg["ok"] is False and msg["skipped"] is True and "no `filmcraft` binary" in msg["error"], msg
    print("[PASS] h6: resolver returns [python, filmcraft_cli.py] or None; missing binary -> clean exit-2 JSON (skipped, not 'filmcraft-cli')")


def test_h_portable_smoke_gate_is_loud_and_not_weakened() -> None:
    """relativize_and_verify_bundle: offline media (shim exit 3 / missingMedia > 0) RAISES; skips say 'no X/filmcraft'; ok -> real int 0."""
    import contextlib
    import io
    import compile_and_verify as cv

    def run_bundle(fake_cmd, fake_smoke):
        with tempfile.TemporaryDirectory(prefix="pfd_portable_") as td:
            root = Path(td) / "bundle"
            (root / "assets" / "plates").mkdir(parents=True)
            (root / "assets" / "plates" / "a.mp4").write_bytes(b"x")
            work = Path(td) / "work"
            work.mkdir()
            src = work / "compiled.fcproj"
            src.write_text(json.dumps({"clips": [{"path": f"{root.resolve()}/assets/plates/a.mp4"}]}), encoding="utf-8")
            keep = (cv._filmcraft_cli_cmd, cv._filmcraft_render_smoke)
            cv._filmcraft_cli_cmd, cv._filmcraft_render_smoke = fake_cmd, fake_smoke
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    info = cv.relativize_and_verify_bundle(src, root / "out.fcproj", root, work, 1.0)
            finally:
                cv._filmcraft_cli_cmd, cv._filmcraft_render_smoke = keep
            return info, err.getvalue()

    ok_cmd = lambda warn=True: ["python3", "shim.py"]  # noqa: E731
    def png_smoke(payload, rc=0):
        def fake(cmd, project, seconds, out_png, timeout_s=300):
            if rc == 0:
                out_png.write_bytes(b"\x89PNG")
            return rc, payload
        return fake

    info, _ = run_bundle(ok_cmd, png_smoke({"ok": True, "missingMedia": 0}))
    assert info["offline_media"] == 0 and isinstance(info["offline_media"], int) and info["smoke_frame_png"], info
    for rc, payload in ((3, {"ok": False, "missingMedia": 2, "error": "2 offline media item(s)"}), (0, {"ok": True, "missingMedia": 1})):
        try:
            run_bundle(ok_cmd, png_smoke(payload, rc))
        except RuntimeError as exc:
            assert "offline media" in str(exc), exc
        else:
            raise AssertionError(f"offline media must FAIL the portable gate (rc={rc}, {payload})")
    try:
        run_bundle(ok_cmd, png_smoke({"ok": True}, 0))  # a shim that does not report missingMedia proves nothing
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing missingMedia must not pass as 0 offline")
    skipped, err = run_bundle(ok_cmd, png_smoke({"ok": False, "skipped": True, "error": "skipped: no X server on :93"}, 2))
    assert skipped["offline_media"] is None and skipped["smoke_frame_png"] is None and "no X server" in skipped["smoke_skipped"], skipped
    assert "SMOKE SKIPPED" in err and "check did NOT run" in err, err
    none_info, err = run_bundle(lambda warn=True: None, png_smoke({}))
    assert "no X/filmcraft" in none_info["smoke_skipped"] and "filmcraft-cli" not in none_info["smoke_skipped"] and "SMOKE SKIPPED" in err
    print("[PASS] h7: portable gate FAILS on offline media, skips are loud ('no X/filmcraft'), offline_media is a real int")


def test_i_reference_21_example_is_valid() -> None:
    doc = (SKILL_ROOT / "references" / "21_craft_json_minimal_spec.md").read_text(encoding="utf-8")
    block = re.search(r"```json\n(.*?)\n```", doc, re.S)
    assert block, "references/21 lacks the minimal JSON example"
    import importlib.util
    mod_path = VENDOR_DIR / "scripts" / "apps" / "craft-handoff" / "tools" / "fc_build.py"
    sys.path.insert(0, str(mod_path.parent))
    sp = importlib.util.spec_from_file_location("pfd_fc_build_doc", mod_path)
    fcb = importlib.util.module_from_spec(sp)
    assert sp.loader is not None
    sp.loader.exec_module(fcb)
    with tempfile.TemporaryDirectory(prefix="pfd_doc_") as td:
        d = Path(td)
        (d / "sfx").mkdir()
        _make_tone_clip(d / "a-roll-1.mp4", dur=6.0)
        for rel, hz in (("voice.wav", 200), ("bgm_music.wav", 330), ("sfx/pop_hit.wav", 1200)):
            r = _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=6", str(d / rel)])
            assert r.returncode == 0, r.stderr[-200:]
        spec = json.loads(block.group(1).replace("{DIR}", str(d)))
        notes = fcb.validate(spec)
        assert notes == [], f"reference example has unsupported keys: {notes}"
        v1 = spec["tracks"][0]["clips"][0]
        assert v1["audio"] is False
    assert "AUTO:" in doc and "--auto-sfx-dir" in doc
    print("[PASS] i: references/21 example validates against fc_build")


def test_j_v78_modules_are_deterministic_and_clean() -> None:
    """v7.8.0: motion_gate is importable stand-alone (numpy / cv2 only), deterministic on seeded synthetic frames, and the
    hook-gates wiring in compile_and_verify stays opt-in."""
    import motion_gate as mg
    import numpy as np
    rng = np.random.default_rng(5)
    base = np.clip(rng.normal(120, 40, (480, 270, 1)), 0, 255).astype(np.uint8).repeat(3, axis=2)
    still = [base.copy() for _ in range(60)]
    a = mg.check_motion(still, (), 0.0, 2.0, fps=30)
    b = mg.check_motion(still, (), 0.0, 2.0, fps=30)
    assert a == b and a["ok"] is False and a["share_below_1"] == 1.0 and a["max_static_run_s"] > 0.6, a
    assert mg.static_runs([(i / 30, 0.2) for i in range(10)], 1.0, 0.6) == []
    import compile_and_verify as cv
    assert callable(cv.run_hook_gates)
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    assert "if args.hook_gates:" in src and 'action="store_true"' in src.split('"--hook-gates"')[1][:200]
    print("[PASS] j: motion_gate deterministic on seeded frames; --hook-gates opt-in wiring present")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (stability core)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
