#!/usr/bin/env python3
"""
Tests for the v7.9.1 portability / legibility audit fixes (typography, plates, fonts, metadata, B-roll lint, vendored rules).

  01 G2 subtitles (S10 / S11 / S12, whisper included) obey the 64 px floor; every other S-preset under 64 px is marked decorative
  02 white_flash_0p25s carries the v7.9 photosensitivity cap, vacuum_32db_0p4s the 20 s gap (additive *_v791 keys)
  03 dviet_style_tokens tiktok_loud: -1.0 dBTP / 14 dB BGM-under-voice override keys match presets/profile_overrides.json
  04 ONE B-roll prompt lint: visual_blocks.lint_broll_prompt and broll_from_video read presets/broll_lint_contract.json
  05 web_cinema_plate_engine.mjs resolves Chrome through PATH, /opt/google/chrome and /snap/bin (--print-chrome)
  06 engine runner: outer timeout, clear error on empty output, per-job results, hard text blocks stay fatal, Chrome worker cap
  07 metadata strip: one shared helper with a built-in ffmpeg / PIL fallback, loud warning when both fail
  08 fonts: PFD_FONT_DIR first, fc-list fallback, _font_uri("") warns
  09 vendored ovs_core rules.json points only at tools that exist here (or says manual); PROVENANCE records the patch
  10 PROVENANCE source is a snapshot label (no local path); test_effect_presets has no cross-repo paths
  11 help banners carry 7.9.x, the --list help counts the registry, --self-test writes to a temp dir by default
  12 subprocess calls in the owned files: text=True has encoding="utf-8", errors="replace" and every run() has a timeout

Synthetic inputs only (ffmpeg lavfi / PIL). Plain asserts with a `__main__` runner.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
PRESETS = SKILL_ROOT / "presets"
VENDOR_DIR = SCRIPTS_DIR / "vendor" / "ovs_core"
ENGINE_MJS = SCRIPTS_DIR / "web_cinema_plate_engine.mjs"
PY = os.environ.get("FILMCRAFT_VENV_PYTHON") or str(Path.home() / ".venvs/video-skills/bin/python3")
if not Path(PY).is_file():
    PY = sys.executable
for _p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OWNED_PY = ("scripts/tools/web_plate_builder.py", "scripts/tools/typography_composer.py", "scripts/dviet_motion_canvas_engine.py",
            "scripts/tools/visual_blocks.py", "scripts/tools/broll_from_video.py")


def _json(rel: str):
    return json.loads((SKILL_ROOT / rel).read_text(encoding="utf-8"))


def _node() -> str | None:
    for c in (os.environ.get("NODE_BIN", ""), str(Path.home() / ".local/bin/node"), shutil.which("node") or ""):
        if c and os.access(c, os.X_OK):
            return c
    return None


def _words(text: str, t0: float = 0.2, step: float = 0.32) -> list[list]:
    return [[w, round(t0 + i * step, 3), round(t0 + i * step + step * 0.9, 3)] for i, w in enumerate(text.split())]


# ----------------------------------------------------------------------------- 01 text floor
def test_01_g2_floor_and_decorative_marks() -> None:
    import typography_composer as tc

    tiers = _json("presets/typography_hierarchy_presets.json")["scale_tiers_9_16"]
    assert tiers["whisper_g2_px"] == 26, "the original key stays (additive only)"
    assert tiers["whisper_g2_px_floor_v791"] == 64
    assert tc.G2_TEXT_FLOOR_PX == 64 and tc.WHISPER_G2_PX >= 64

    speech = ("nhiều bạn mất khách vì video làm quá chậm nhưng điều ít ai để ý là phần mở đầu chuyển đổi khách hàng tiềm năng "
              "nhanh hơn rất nhiều")
    words = _words(speech)
    sizes: dict[str, list[float]] = {}
    for prof in (None, "dviet"):
        sizes[f"s12/{prof}"] = [c["size"] for c in tc.s12_minimal_1line_quiet(words, style_profile=prof)]
        sizes[f"s10/{prof}"] = [c["size"] for c in tc.s10_word_synced_fixed_slot_captions(words, style_profile=prof)["clips"]]
        sizes[f"s12x/{prof}"] = [c["size"] for c in tc.s12_minimal_1line_quiet(words, style_profile=prof, size=30.0)]
    sizes["s11"] = [c["size"] for c in tc.s11_conversational_2line(words)["clips"]]
    for k, v in sizes.items():
        assert v, f"{k}: no clips"
        assert min(v) >= 64.0 - 1e-6, f"{k}: G2 subtitle below the 64 px floor: {sorted(set(v))}"
    # the floored text still fits the safe width (the chunker drops words instead of overflowing)
    for c in tc.s12_minimal_1line_quiet(words, style_profile="dviet"):
        w = tc.measure_text_ink_width(c["text"], c["font"], c["style"], c["size"])
        assert w <= tc.DEFAULT_MAX_TEXT_WIDTH_PX + 1e-3, (c["text"], w)

    deco = _json("presets/typography_hierarchy_presets.json")["secondary_text_decorative_v791"]
    assert deco["floor_px"] == 64 and tc.DECORATIVE_SECONDARY_V791 == deco["presets"]
    for name, fn in vars(tc).items():
        if not (re.match(r"^s\d\d_", name) and callable(fn)):
            continue
        small = {p.name: p.default for p in inspect.signature(fn).parameters.values()
                 if "size" in p.name and isinstance(p.default, (int, float)) and p.default < 64}
        if name in ("s10_word_synced_fixed_slot_captions", "s11_conversational_2line", "s12_minimal_1line_quiet"):
            assert name not in deco["presets"], f"{name} is G2 reading text: it is floored, never decorative"
            continue
        if small:
            reason = deco["presets"].get(name, "")
            assert isinstance(reason, str) and len(reason) >= 20, f"{name} defaults {small} < 64 px but is not marked decorative"
    print(f"[PASS] 01 G2 floor 64 px (min sizes {', '.join(f'{k}={min(v):.0f}' for k, v in sizes.items())}); "
          f"{len(deco['presets'])} S-presets marked decorative with a reason")


# ----------------------------------------------------------------------------- 02 flash / vacuum
def test_02_flash_cap_and_vacuum_gap() -> None:
    import duck_keyframes as dk
    import motion_gate as mg

    atoms = _json("presets/atomic_motion_library.json")["atomics"]
    fl = atoms["white_flash_0p25s"]
    assert fl["caps"]["per_video"] == 3 and "near pure white" in fl["description"], "existing keys stay (additive only)"
    cap = fl["caps_v791"]
    assert cap["max_mean_luma"] == mg.FLASH_LUMA_CAP == 220
    assert cap["max_flashes_per_s"] == mg.MAX_FLASHES_PER_S == 3
    assert cap["max_white_opacity_pct"] == 70
    assert mg.flash_peak_luma(cap["max_white_opacity_pct"] / 100.0) <= mg.FLASH_LUMA_CAP, "the capped peak passes check_flash_plan"
    plan = [{"kind": "flash", "t_ms": 1000 + i * 400, "opacity": cap["max_white_opacity_pct"], "id": f"f{i}"} for i in range(3)]
    assert not mg.check_flash_plan(plan), mg.check_flash_plan(plan)
    vac = atoms["vacuum_32db_0p4s"]
    assert vac["caps"]["min_gap_s"] == 15.0, "existing value stays (additive only)"
    assert vac["caps_v791"]["min_gap_s"] == 20.0 == dk.DuckParams.__dataclass_fields__["vacuum_min_interval_sec"].default
    print("[PASS] 02 white_flash caps_v791 = luma 220 / white 70 % / 3 per s; vacuum caps_v791.min_gap_s = 20 s (= duck_keyframes)")


# ----------------------------------------------------------------------------- 03 loudness tokens
def test_03_tiktok_loud_tokens() -> None:
    tl = _json("presets/dviet_style_tokens.json")["audio"]["tiktok_loud"]
    prof = _json("presets/profile_overrides.json")
    prof = prof.get("audio_profiles", prof)["tiktok_loud"]
    assert tl["tp_cap_dbtp"] == -0.5, "the stale key stays for the docs test (additive only)"
    assert tl["tp_cap_dbtp_v791"] == prof["true_peak_dbtp"] == -1.0
    assert tl["bgm_below_voice_db_v791"] == 14
    assert "-1.0 dBTP" in tl["note_v791"]
    print("[PASS] 03 tiktok_loud tp_cap_dbtp_v791 -1.0 dBTP, bgm_below_voice_db_v791 14 dB (= profile_overrides.json)")


# ----------------------------------------------------------------------------- 04 B-roll lint
def test_04_one_broll_lint() -> None:
    import broll_from_video as bv
    import visual_blocks as vb

    c = _json("presets/broll_lint_contract.json")
    assert "45-token" in c["supersedes"], "the old note stays (test_ports reads it)"
    src = c["single_source_v791"]
    assert src["used_by"] == ["scripts/tools/broll_from_video.py", "scripts/tools/visual_blocks.py"]
    want = [t for r in ("TEXT_IN_IMAGE", "BRAND") for t in c["rules"][r]["tokens"]]
    assert list(vb.BROLL_BANNED_TOKENS) == list(dict.fromkeys(want)), "BROLL_BANNED_TOKENS is derived from the contract"
    base = ("A Vietnamese shop owner seen from behind rearranges neatly folded clothes on a wooden shelf, "
            "soft morning window light, slow push-in, shallow depth of field")
    cases = {
        "ok": base,
        "long": base + " " + " ".join(["warm"] * (c["max_words"] + 1 - len(base.split()))),
        "short": "a shelf in light",
        "face": base + ", her face looking at the camera",
        "evidence": base + ", showing revenue growth",
        "brand": base + " next to an iphone",
        "vi": base + " cửa hàng",
    }
    for name, prompt in cases.items():
        r = vb.lint_broll_prompt(prompt)
        ingest = [e for e in bv.lint_prompt(prompt, "x", None, c) if not e["code"].startswith("ANCHOR")]
        assert r["ok"] is (not ingest), (name, r["errors"], ingest)
        assert r["ok"] is (name == "ok"), (name, r["errors"])
        assert r["word_count_range"] == [c["min_words"], c["max_words"]] == [8, 60]
    assert "iphone" in vb.lint_broll_prompt(cases["brand"])["banned_hits"]
    assert "face out of frame" in c["rules"]["FACE"]["allowed_phrases"]
    assert vb.lint_broll_prompt(base + ", face out of frame")["ok"]
    print(f"[PASS] 04 one lint: {c['min_words']}-{c['max_words']} words, {len(vb.BROLL_BANNED_TOKENS)} text/brand tokens "
          f"+ {len(c['rules']['FACE']['tokens'])} face + {len(c['rules']['R200']['evidence_terms'])} R200 terms, same verdicts")


# ----------------------------------------------------------------------------- 05 Chrome lookup
def test_05_chrome_lookup_uses_path() -> None:
    src = ENGINE_MJS.read_text(encoding="utf-8")
    for need in ("/opt/google/chrome/chrome", "/snap/bin/chromium", "process.env.PATH", "--print-chrome"):
        assert need in src, f"engine misses {need}"
    node = _node()
    if node is None:
        print("[SKIP] 05 node not installed: static checks only")
        return
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "bin" / "chromium"
        fake.parent.mkdir()
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        env = {"PATH": str(fake.parent), "HOME": td}
        r = subprocess.run([node, str(ENGINE_MJS), "--print-chrome"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, env=env)
        assert r.returncode == 0 and r.stdout.strip() == str(fake), (r.returncode, r.stdout, r.stderr)
        env["CHROME_BIN"] = str(fake)
        r2 = subprocess.run([node, str(ENGINE_MJS), "--print-chrome"], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=30, env=dict(env, PATH="/nonexistent"))
        assert r2.stdout.strip() == str(fake), r2.stdout
    print("[PASS] 05 Chrome resolved through PATH (fake `chromium`), CHROME_BIN first, /opt/google/chrome + /snap/bin listed")


# ----------------------------------------------------------------------------- 06 engine runner
def test_06_engine_runner() -> None:
    import web_plate_builder as wpb

    real_run, real_node = wpb.subprocess.run, wpb.resolve_node_binary
    seen: dict[str, object] = {}

    def fake_empty(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def fake_slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    try:
        wpb.resolve_node_binary = lambda: "node"
        with tempfile.TemporaryDirectory() as td:
            for fake, needle in ((fake_empty, "no output"), (fake_slow, "timed out")):
                wpb.subprocess.run = fake
                try:
                    wpb._run_engine_batch([{"html": "x", "out": "y"}], Path(td), concurrency=1, alpha_codec="prores4444", quiet=True)
                    raise AssertionError(f"{fake.__name__} must raise")
                except RuntimeError as exc:
                    assert needle in str(exc), str(exc)
            assert float(seen["timeout"]) > 0 and seen.get("encoding") == "utf-8" and seen.get("errors") == "replace", seen

            calls: list[int] = []

            def fake_partial(cmd, **kw):
                jobs = json.loads(Path(cmd[cmd.index("--batch-json") + 1]).read_text(encoding="utf-8"))["jobs"]
                calls.append(int(cmd[cmd.index("--concurrency") + 1]))
                res = [{"ok": True, "out": j["out"]} for j in jobs]
                res[-1] = {"ok": False, "out": jobs[-1]["out"], "error": "Page crashed", "index": len(jobs) - 1}
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": False, "failed": 1, "results": res}) + "\n", "")

            wpb.subprocess.run = fake_partial
            job = {"template": "kt12_whisper_or_directional_echo", "props": {"demo": True}, "mode": "still", "height": 560}
            jobs = [dict(job, out=f"{td}/a.png"), dict(job, out=f"{td}/b.png")]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                res = wpb.render_web_plates_batch(jobs, strip_meta=False, quiet=True)
            assert res[0].get("ok", True) is True and res[1]["ok"] is False and res[1]["failed"] is True, res
            assert "Page crashed" in res[1]["error"] and any("1 of 2" in str(w.message) for w in caught), [str(w.message) for w in caught]

            def fake_all_fail(cmd, **kw):
                jobs = json.loads(Path(cmd[cmd.index("--batch-json") + 1]).read_text(encoding="utf-8"))["jobs"]
                res = [{"ok": False, "out": j["out"], "error": "boom"} for j in jobs]
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": False, "results": res}) + "\n", "")

            wpb.subprocess.run = fake_all_fail
            try:
                wpb.render_web_plates_batch(jobs, strip_meta=False, quiet=True)
                raise AssertionError("a batch where every job failed must raise")
            except RuntimeError as exc:
                assert "boom" in str(exc)

            def fake_small_text(cmd, **kw):
                jobs = json.loads(Path(cmd[cmd.index("--batch-json") + 1]).read_text(encoding="utf-8"))["jobs"]
                res = [{"ok": True, "out": j["out"], "textSizes": [{"label": "x", "effPx": 20, "text": "nhỏ"}]} for j in jobs]
                res[0] = {"ok": False, "out": jobs[0]["out"], "error": "boom"}
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"ok": False, "results": res}) + "\n", "")

            wpb.subprocess.run = fake_small_text
            try:
                wpb.render_web_plates_batch(jobs, strip_meta=False, quiet=True)
                raise AssertionError("undersized rendered text stays a hard block next to a failed job")
            except wpb.UndersizedTextError:
                pass

            # Chrome worker cap: workspace_context.json (studio tier = 2), PFD_CHROME_WORKERS, default 4
            ctx = Path(td) / "workspace_context.json"
            ctx.write_text(json.dumps({"ram_governance": {"max_chrome_workers": 2}}), encoding="utf-8")
            old = os.environ.pop("PFD_CHROME_WORKERS", None)
            try:
                assert wpb.resolve_chrome_workers() == 4
                assert wpb.resolve_chrome_workers(work_dir=td) == 2
                assert wpb.resolve_chrome_workers(4, workspace_context=str(ctx)) == 2
                assert wpb.resolve_chrome_workers(1, workspace_context={"ram_governance": {"max_chrome_workers": 2}}) == 1
                os.environ["PFD_CHROME_WORKERS"] = "1"
                assert wpb.resolve_chrome_workers() == 1 and wpb.resolve_chrome_workers(work_dir=td) == 1
                os.environ["PFD_CHROME_WORKERS"] = "3"
                assert wpb.resolve_chrome_workers() == 3 and wpb.resolve_chrome_workers(work_dir=td) == 2
                del os.environ["PFD_CHROME_WORKERS"]
                wpb.subprocess.run = fake_partial
                calls.clear()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    wpb.render_web_plates_batch(jobs, strip_meta=False, quiet=True, work_dir=td)
                assert calls == [2], calls
            finally:
                os.environ.pop("PFD_CHROME_WORKERS", None)
                if old is not None:
                    os.environ["PFD_CHROME_WORKERS"] = old
    finally:
        wpb.subprocess.run, wpb.resolve_node_binary = real_run, real_node

    # real engine: one broken job does not discard the good one
    node = _node()
    try:
        chrome = subprocess.run([node, str(ENGINE_MJS), "--print-chrome"], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=30).stdout.strip() if node else ""
    except (OSError, subprocess.SubprocessError):
        chrome = ""
    if not chrome:
        print("[PASS] 06 runner (mocked); [SKIP] real engine: node / Chrome not installed")
        return
    with tempfile.TemporaryDirectory() as td:
        good = Path(td) / "good.html"
        good.write_text("<html><body style='margin:0;background:transparent'><div style='width:40px;height:40px;background:red'>"
                        "</div></body></html>", encoding="utf-8")
        ejobs = [{"html": str(good), "out": f"{td}/good.png", "mode": "still", "width": 64, "height": 64, "scale": 1.0, "fps": 30,
                  "frames": 1},
                 {"html": f"{td}/missing.html", "out": f"{td}/bad.png", "mode": "still", "width": 64, "height": 64, "scale": 1.0,
                  "fps": 30, "frames": 1}]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = wpb._run_engine_batch(ejobs, Path(td), concurrency=2, alpha_codec="prores4444", quiet=True)
        assert len(res) == 2 and res[0].get("ok", True) and Path(td, "good.png").is_file(), res
        assert res[1]["ok"] is False and res[1]["failed"] is True and res[1]["error"], res[1]
    print("[PASS] 06 runner: timeout + empty output raise clearly, per-job failures marked, text blocks fatal, workers 4 / ctx 2 / env; "
          "real engine keeps the good plate next to a broken one")


# ----------------------------------------------------------------------------- 07 metadata
def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg") or (str(Path.home() / ".local/bin/ffmpeg") if (Path.home() / ".local/bin/ffmpeg").is_file() else None)


def _ffprobe_tags(path: Path) -> dict:
    probe = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")
    r = subprocess.run([probe, "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    return (json.loads(r.stdout or "{}").get("format") or {}).get("tags") or {}


def test_07_metadata_fallback() -> None:
    import web_plate_builder as wpb
    from PIL import Image, PngImagePlugin

    real = list(wpb.STRIP_METADATA_Candidates)
    wpb.STRIP_METADATA_Candidates[:] = [Path("/nonexistent/strip_metadata.py")]
    try:
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "a.png"
            info = PngImagePlugin.PngInfo()
            info.add_text("Software", "SECRET-GENERATOR")
            info.add_text("parameters", "prompt: SECRET")
            Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(png, pnginfo=info)
            assert b"SECRET" in png.read_bytes()
            assert wpb.strip_media_metadata(png) == "pil"
            assert b"SECRET" not in png.read_bytes()
            with Image.open(png) as im:
                assert im.mode == "RGBA" and im.getpixel((3, 3)) == (255, 0, 0, 128), "pixels survive"

            ff = _ffmpeg()
            if ff:
                mp4 = Path(td) / "v.mp4"
                subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:d=0.4:r=10", "-metadata",
                                "title=SECRET", "-metadata", "comment=prompt SECRET", "-c:v", "mpeg4", str(mp4)],
                               check=True, timeout=60)
                assert "SECRET" in json.dumps(_ffprobe_tags(mp4))
                assert wpb.strip_media_metadata(mp4) == "ffmpeg"
                assert "SECRET" not in json.dumps(_ffprobe_tags(mp4)), _ffprobe_tags(mp4)
                import dviet_motion_canvas_engine as mce
                subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x64:d=0.4:r=10", "-metadata",
                                "title=SECRET", "-c:v", "mpeg4", str(mp4)], check=True, timeout=60)
                mce.strip_mp4_metadata(mp4)
                assert "SECRET" not in json.dumps(_ffprobe_tags(mp4)), "the canvas engine uses the shared helper"
            else:
                print("[SKIP] 07 ffmpeg not installed: video fallback not exercised")

            real_ff = wpb._resolve_ffmpeg_bin
            wpb._resolve_ffmpeg_bin = lambda: None
            try:
                odd = Path(td) / "x.mov"
                odd.write_bytes(b"not a video")
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    assert wpb.strip_media_metadata(odd) == ""
                assert any("METADATA NOT STRIPPED" in str(w.message) for w in caught), [str(w.message) for w in caught]
            finally:
                wpb._resolve_ffmpeg_bin = real_ff
    finally:
        wpb.STRIP_METADATA_Candidates[:] = real
    for rel in ("scripts/tools/typography_composer.py", "scripts/dviet_motion_canvas_engine.py", "scripts/tools/visual_blocks.py"):
        s = (SKILL_ROOT / rel).read_text(encoding="utf-8")
        assert "strip_media_metadata(" in s, f"{rel} does not call the shared helper"
    print("[PASS] 07 metadata: PIL fallback strips PNG text chunks, ffmpeg -map_metadata -1 strips video tags, loud warning when both fail")


# ----------------------------------------------------------------------------- 08 fonts
def test_08_font_search() -> None:
    import dviet_motion_canvas_engine as mce
    import typography_composer as tc
    import web_plate_builder as wpb

    dejavu = next((p for p in (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),) if p.is_file()), None)
    if dejavu is None:
        dejavu = Path(tc._resolve_typo_font_path("Be Vietnam Pro", "Bold"))
    old = os.environ.get("PFD_FONT_DIR")
    with tempfile.TemporaryDirectory() as td:
        shutil.copy(dejavu, Path(td) / "BeVietnamPro-Bold.ttf")
        shutil.copy(dejavu, Path(td) / "BeVietnamPro-ExtraBold.ttf")
        os.environ["PFD_FONT_DIR"] = td
        try:
            tc._resolve_typo_font_path.cache_clear()
            mce._resolve_font_path.cache_clear()
            assert tc._resolve_typo_font_path("Be Vietnam Pro", "Bold") == str(Path(td) / "BeVietnamPro-Bold.ttf")
            assert mce._resolve_font_path("be_extrabold") == str(Path(td) / "BeVietnamPro-ExtraBold.ttf")
            assert wpb.find_font_file("BeVietnamPro-Bold.ttf") == Path(td) / "BeVietnamPro-Bold.ttf"
        finally:
            if old is None:
                os.environ.pop("PFD_FONT_DIR", None)
            else:
                os.environ["PFD_FONT_DIR"] = old
            tc._resolve_typo_font_path.cache_clear()
            mce._resolve_font_path.cache_clear()
    if shutil.which("fc-list"):
        listed = subprocess.run(["fc-list", "--format", "%{file}\n"], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=30).stdout.split("\n")
        roots = [str(r) for r in (*wpb.FONT_ROOTS_TNEDIT, wpb.FONT_ROOT_BASE)]
        outside = next((Path(f) for f in listed if f.endswith((".ttf", ".otf")) and Path(f).is_file()
                        and not any(f.startswith(r + "/") for r in roots)), None)
        if outside is not None:
            wpb._fc_list_files.cache_clear()
            got = wpb.find_font_file(outside.name)
            assert got is not None and got.name == outside.name, (outside, got)
    else:
        print("[SKIP] 08 fc-list not installed: fontconfig fallback not exercised")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert wpb._font_uri(Path("/nonexistent/fonts/Missing-Font.ttf")) == ""
    assert any("Missing-Font.ttf" in str(w.message) and "PFD_FONT_DIR" in str(w.message) for w in caught), [str(w.message) for w in caught]
    print("[PASS] 08 fonts: PFD_FONT_DIR wins in all three resolvers, fc-list finds a font outside the user folders, _font_uri warns")


# ----------------------------------------------------------------------------- 09 vendored rules
def _repo_script_names() -> set[str]:
    return {p.name for p in SKILL_ROOT.rglob("*.py") if ".git" not in p.parts and "__pycache__" not in p.parts}


def test_09_vendored_rules_point_at_this_skill() -> None:
    rules = json.loads((VENDOR_DIR / "rules.json").read_text(encoding="utf-8"))
    have = _repo_script_names()
    bad = []
    for r in rules["rules"]:
        for k in ("text", "check", "label", "title"):
            v = r.get(k)
            if isinstance(v, str):
                bad += [f"{r['id']}.{k}: {m}" for m in re.findall(r"([\w-]+\.py)\b", v) if m not in have]
    assert not bad, "rules.json cites scripts that are not in this repo:\n" + "\n".join(bad)
    prov = (VENDOR_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "7.9.0" in prov.splitlines()[0]
    assert "patched in v7.9.1" in prov
    digest = dict(re.findall(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", prov))["rules.json"]
    assert hashlib.sha256((VENDOR_DIR / "rules.json").read_bytes()).hexdigest() == digest
    print(f"[PASS] 09 rules.json: {len(rules['rules'])} rules cite only scripts present here; PROVENANCE sha256 + v7.9.1 patch note")


# ----------------------------------------------------------------------------- 10 provenance / cross-repo paths
def test_10_no_personal_or_cross_repo_paths() -> None:
    prov = (VENDOR_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "opa-video-studio skill (snapshot)" in prov and "3.6.6" in prov and "2026-11-25" in prov
    assert "/home/" not in prov, "PROVENANCE records a personal path"
    stab = (SKILL_ROOT / "tests" / "test_stability.py").read_text(encoding="utf-8")
    assert "/home/vmiz" not in stab
    eff = (SKILL_ROOT / "tests" / "test_effect_presets.py").read_text(encoding="utf-8")
    assert "video-agent-server" not in eff and "SKILL_ROOT.parent" not in eff
    r = subprocess.run([PY, str(SKILL_ROOT / "tests" / "test_effect_presets.py")], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900, env={k: v for k, v in os.environ.items()
                                                          if k not in ("PFD_FILMCRAFT_COMMANDS", "PFD_EFFECTS_DUMP")})
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    if not (VENDOR_DIR / "references" / "filmcraft-commands.json").is_file():
        assert "[SKIP] filmcraft-commands.json not found" in r.stdout, r.stdout[-800:]
    print("[PASS] 10 PROVENANCE source = snapshot label + version/date; test_effect_presets skips explicitly without cross-repo paths")


# ----------------------------------------------------------------------------- 11 banners
def test_11_help_banners() -> None:
    import web_plate_builder as wpb

    assert re.search(r"v7\.9\.\d", (TOOLS_DIR / "web_plate_builder.py").read_text(encoding="utf-8").split("\n", 3)[2])
    r = subprocess.run([PY, str(TOOLS_DIR / "web_plate_builder.py"), "--help"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    h = " ".join(r.stdout.split())
    assert r.returncode == 0 and re.search(r"v7\.9\.\d", h) and "v7.1" not in h, h[:400]
    assert f"List all {len(wpb.TEMPLATE_DEFAULTS)} built-in" in h, h
    assert "/tmp/test_v71_web_plates" not in h and "temp" in h.lower()
    assert "/tmp/test_v71_web_plates" not in (TOOLS_DIR / "web_plate_builder.py").read_text(encoding="utf-8")
    for rel, args in (("scripts/tools/visual_blocks.py", ["--help"]), ("scripts/tools/visual_blocks.py", ["--list"]),
                      ("scripts/dviet_motion_canvas_engine.py", ["--help"])):
        r = subprocess.run([PY, str(SKILL_ROOT / rel), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=180)
        out = r.stdout + r.stderr
        assert r.returncode == 0, (rel, args, out[-600:])
        assert "v6.0" not in out and re.search(r"v?7\.9\.\d", out), (rel, args, out[:600])
    print(f"[PASS] 11 banners 7.9.x (web_plate_builder, visual_blocks --help/--list, canvas engine), --list counts "
          f"{len(wpb.TEMPLATE_DEFAULTS)} templates, --self-test default dir is a temp dir")


# ----------------------------------------------------------------------------- 12 subprocess hygiene
def test_12_subprocess_encoding_and_timeouts() -> None:
    bad = []
    for rel in OWNED_PY:
        tree = ast.parse((SKILL_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
                    and node.func.attr in ("run", "Popen", "check_output")):
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            text = isinstance(kw.get("text"), ast.Constant) and kw["text"].value is True
            if text and not ("encoding" in kw and "errors" in kw):
                bad.append(f"{rel}:{node.lineno} text=True without encoding/errors")
            if node.func.attr != "Popen" and "timeout" not in kw:
                bad.append(f"{rel}:{node.lineno} subprocess.{node.func.attr} without timeout")
    assert not bad, "\n".join(bad)
    print(f"[PASS] 12 every subprocess call in {len(OWNED_PY)} owned files has encoding/errors (text) and a timeout (run)")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (portability v7.9.1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
