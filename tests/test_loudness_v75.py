#!/usr/bin/env python3
"""
v7.5.0 loudness table (references/25 sections 7 and 9) wired into presets/profile_overrides.json (`tiktok_loud`)
and scripts/vendor/ovs_core/scripts/audio_levels.py.

* table-driven: every value of the table, loaded through compile_and_verify.build_effective_rules;
* `platform` stays the historical profile (regression);
* audio_levels accepts the merged rules (key shape) and gives pass / warn / fail verdicts on synthetic <= 3 s
  ffmpeg sine / anoisesrc clips written to a tempdir. No project media is read, nothing is rendered.

Run: python3 tests/test_loudness_v75.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
AL_PATH = SCRIPTS_DIR / "vendor" / "ovs_core" / "scripts" / "audio_levels.py"
for p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import compile_and_verify as cv  # noqa: E402

_spec = importlib.util.spec_from_file_location("audio_levels_v75", AL_PATH)
al = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(al)

TIKTOK_AUDIO = {
    "master_lufs.final": -12.0,
    "master_lufs.tol_lu": 0.5,
    "master_true_peak_dbtp": -1.0,
    "voice_peak_dbfs.min": -3.5,
    "voice_peak_dbfs.max": -1.5,
    "voice_peak_dbfs.target": -2.0,
    "bgm_below_voice_lu.min": 12.0,
    "bgm_below_voice_lu.max": 17.0,
    "bgm_below_voice_lu.target": 14.0,
    "bgm_speech_floor_lu": 8.0,
    "sfx_peak_dbfs.tier.A": -4.0,
    "sfx_peak_dbfs.tier.B": -7.0,
    "sfx_peak_dbfs.tier.C": -10.0,
    "bgm_no_voice_lu.min": 4.0,
    "bgm_no_voice_lu.max": 8.0,
    "bgm_no_voice_lu.target": 6.0,
    "bgm_no_voice_lu.min_gap_s": 1.5,
    "lra_warn_lu": 6.0,
    "short_term_max_lufs": -7.0,
    "no_ducking": True,
}


def _dig(d: dict, dotted: str):
    for k in dotted.split("."):
        d = d[k]
    return d


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def make_tone(path: Path, *, peak_dbfs: float | None = None, lufs: float | None = None, dur: float = 3.0, noise: bool = False) -> Path:
    """Synthetic clip (sine 997 Hz, or pink-ish anoisesrc) at a known level. Exactly one of peak_dbfs / lufs."""
    src = ("anoisesrc=d={d}:c=pink:r=48000:a=0.5:seed=7" if noise else "sine=f=997:r=48000:d={d}").format(d=dur)
    _ffmpeg("-f", "lavfi", "-i", src, "-ac", "1", "-c:a", "pcm_s16le", str(path))
    m = al.measure(path)
    want = (peak_dbfs - m["peak"]) if peak_dbfs is not None else (lufs - m["lufs"])
    _ffmpeg("-i", str(path), "-af", f"volume={want:.4f}dB", "-c:a", "pcm_s16le", str(path.with_suffix(".o.wav")))
    path.with_suffix(".o.wav").replace(path)
    return path


def tiktok_rules(wd: Path) -> dict:
    eff = cv.build_effective_rules(wd, -12.0, audio_profile="tiktok_loud")
    return al.load_rules(eff)


def status(res: list[dict], rid: str) -> str:
    return next(r["status"] for r in res if r["id"] == rid)


def test_table_values_via_build_effective_rules() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        eff = cv.build_effective_rules(Path(td), -12.0, audio_profile="tiktok_loud")
        a = json.loads(Path(eff).read_text(encoding="utf-8"))["params"]["audio"]
        for dotted, want in TIKTOK_AUDIO.items():
            assert _dig(a, dotted) == want, f"{dotted}: {_dig(a, dotted)!r} != {want!r}"
        assert a["sfx_peak_dbfs"]["min"] <= min(a["sfx_peak_dbfs"]["tier"].values())
        assert a["sfx_peak_dbfs"]["max"] >= max(a["sfx_peak_dbfs"]["tier"].values())
    prof = cv.resolve_audio_profile("tiktok_loud")
    assert prof["target_lufs"] == -12.0 and prof["true_peak_dbtp"] == -1.0 and prof["limiter_db"] == -1.2
    assert prof["bgm_below_voice_db"] == 14.0 and prof["no_ducking"] is True
    assert "-12" in prof["_doc"] and "derived" in prof["_doc"].lower()
    print(f"[PASS] {len(TIKTOK_AUDIO)} table values + profile top level verified through build_effective_rules")


def test_no_official_tiktok_figure_claimed() -> None:
    text = (SKILL_ROOT / "presets" / "profile_overrides.json").read_text(encoding="utf-8").lower()
    assert not re.search(r"tiktok[^.\n]{0,40}normali[sz]\w*[^.\n]{0,15}-?\d+\s*lufs", text), "no TikTok normalization figure may be claimed"
    assert "does not publish" in text or "không công bố" in text, "preset _doc must say TikTok publishes no figure"
    print("[PASS] preset makes no official TikTok normalization claim")


def test_platform_profile_unchanged() -> None:
    plat = cv.resolve_audio_profile("platform")
    assert plat == {
        "_doc": plat["_doc"], "target_lufs": -16.0, "true_peak_dbtp": -1.5, "limiter_db": -2.2, "rules_override": {},
    }, plat
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        assert Path(cv.build_effective_rules(Path(td), -16.0)) == cv.DEFAULT_RULES_JSON
        assert Path(cv.build_effective_rules(Path(td), -16.0, audio_profile="platform")) == cv.DEFAULT_RULES_JSON
        rules = al.load_rules(cv.DEFAULT_RULES_JSON)
        assert rules["master_true_peak_dbtp"] == -1.5 and rules["voice_peak_dbfs"]["max"] == -3.0
        assert rules["bgm_below_voice_lu"]["target"] == 17.0 and rules["bgm_speech_floor_lu"] == 10.0
        assert rules["master_lufs"]["final"] == -16.0
        for k in ("bgm_no_voice_lu", "lra_warn_lu", "short_term_max_lufs"):
            assert k not in rules, f"platform rules must not gain {k}"
        wd = Path(td)
        mix = make_tone(wd / "mix.wav", lufs=-16.0)
        voice = make_tone(wd / "voice.wav", peak_dbfs=-4.0)
        bgm = make_tone(wd / "bgm.wav", peak_dbfs=-4.0, noise=True)
        res = al.check(mix, rules, voice, bgm, None)
        assert [r["id"] for r in res] == ["master_lufs", "true_peak", "voice_peak", "sfx_peak", "bgm_below_voice", "speech_floor"], \
            "platform verdict list must be exactly the historical six"
        assert status(res, "master_lufs") == "PASS" and status(res, "true_peak") == "PASS" and status(res, "voice_peak") == "PASS"
        assert {r["status"] for r in res} <= {"PASS", "FAIL", "SKIP"}, "platform must never emit WARN"
        loud = make_tone(wd / "loud.wav", peak_dbfs=-1.0)
        assert status(al.check(loud, rules, None, None, None), "true_peak") == "FAIL", "-1.0 dBTP fails the platform -1.5 ceiling"
    print("[PASS] platform profile / rules / verdict list unchanged")


def test_audio_levels_accepts_profile_and_tiktok_verdicts() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        wd = Path(td)
        rules = tiktok_rules(wd)  # load_rules raises RuleError (SystemExit) if a required key is missing
        # --- master LUFS (mix.wav window +/-0.5) ---
        for lufs, want in ((-12.0, "PASS"), (-12.4, "PASS"), (-11.6, "PASS"), (-12.7, "FAIL"), (-14.0, "FAIL"), (-10.0, "FAIL")):
            mix = make_tone(wd / "m.wav", lufs=lufs)
            assert status(al.check(mix, rules, None, None, None), "master_lufs") == want, (lufs, want)
        # --- true peak: -1.0 dBTP ceiling (platform allowed -1.5; the old tiktok_loud allowed -0.5) ---
        for peak, want in ((-8.0, "PASS"), (-1.5, "PASS"), (-0.8, "FAIL"), (-0.3, "FAIL")):
            mix = make_tone(wd / "m.wav", peak_dbfs=peak)
            assert status(al.check(mix, rules, None, None, None), "true_peak") == want, (peak, want)
        # --- voice peak window -3.5 .. -1.5 ---
        mix = make_tone(wd / "m.wav", lufs=-12.0)
        for peak, want in ((-2.0, "PASS"), (-3.4, "PASS"), (-1.6, "PASS"), (-1.0, "FAIL"), (-0.6, "FAIL"), (-4.0, "FAIL")):
            voice = make_tone(wd / "v.wav", peak_dbfs=peak)
            assert status(al.check(mix, rules, voice, None, None), "voice_peak") == want, (peak, want)
        # --- SFX stem peak: hit tier -4 sits inside -12..-3 ---
        for peak, want in ((-4.0, "PASS"), (-10.0, "PASS"), (-2.0, "FAIL"), (-14.0, "FAIL")):
            sfx = make_tone(wd / "s.wav", peak_dbfs=peak)
            assert status(al.check(mix, rules, None, None, sfx), "sfx_peak") == want, (peak, want)
        # --- BGM bed with voice: 14 LU target, window 12..17 ---
        voice = make_tone(wd / "v.wav", peak_dbfs=-2.0)
        vl = al.measure(voice)["lufs"]
        for gap, want in ((14.0, "PASS"), (12.5, "PASS"), (6.6, "FAIL"), (20.0, "FAIL")):
            bgm = make_tone(wd / "b.wav", lufs=vl - gap, noise=True)
            assert status(al.check(mix, rules, voice, bgm, None), "bgm_below_voice") == want, (gap, want)
    print("[PASS] LUFS / true peak / voice / SFX / BGM-bed verdicts on synthetic clips")


def test_sfx_tiers_plan_accepts_new_tiers() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        wd = Path(td)
        rules = tiktok_rules(wd)
        voice = make_tone(wd / "voice.wav", peak_dbfs=-6.0, dur=2.0)
        hit = make_tone(wd / "hit.wav", peak_dbfs=-1.0, dur=1.0)
        soft = make_tone(wd / "soft.wav", peak_dbfs=-1.0, dur=1.0)
        spec = {"duration": 5.0, "tracks": [
            {"type": "audio", "name": "Giọng", "clips": [{"name": "voice", "src": str(voice), "at": 0.0, "dur": 2.0}]},
            {"type": "audio", "name": "SFX", "clips": [
                {"name": "hit", "src": str(hit), "at": 0.5, "dur": 1.0, "tier": "A"},
                {"name": "soft whoosh", "src": str(soft), "at": 3.0, "dur": 1.0, "tier": "C"}]},
        ]}
        sp = wd / "x.craft.json"
        sp.write_text(json.dumps(spec), encoding="utf-8")
        rep = al.plan(sp, wd / "x.levels.craft.json", rules)
        tgt = {r["name"]: r["target"] for r in rep["clips"]}
        assert tgt["hit"] == -4.0 and tgt["soft whoosh"] == -10.0 and tgt["voice"] == -2.0, tgt
        spec["tracks"][1]["clips"][0]["tier"] = "B"
        sp.write_text(json.dumps(spec), encoding="utf-8")
        assert {r["name"]: r["target"] for r in al.plan(sp, wd / "y.craft.json", rules)["clips"]}["hit"] == -7.0
    print("[PASS] plan() resolves tiers A/B/C to -4 / -7 / -10 dBFS and voice to -2")


def _patch_short_term(mapping: dict[str, list[tuple[float, float]]]):
    orig = al.short_term
    al.short_term = lambda p: mapping[Path(p).name]
    return orig


def test_no_voice_bed_is_warn_not_fail() -> None:
    ts = [round(3.0 + 0.1 * i, 2) for i in range(70)]  # 3.0 .. 9.9 s
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        wd = Path(td)
        rules = tiktok_rules(wd)
        mix = make_tone(wd / "mix.wav", lufs=-12.0)
        voice = make_tone(wd / "voice.wav", peak_dbfs=-2.0)
        vl = al.measure(voice)["lufs"]
        bgm = make_tone(wd / "bgm.wav", lufs=vl - 14.0, noise=True)
        sv = [(t, vl if t < 4.0 or t > 9.0 else -70.0) for t in ts]  # voice speaks, then a gap (windows fully inside it), then speaks

        def run(gap_lu_in_speech: float, gap_lu_in_gap: float) -> list[dict]:
            sb = [(t, vl - (gap_lu_in_speech if v > -60 else gap_lu_in_gap)) for t, v in sv]
            orig = _patch_short_term({"voice.wav": sv, "bgm.wav": sb, "mix.wav": []})
            try:
                return al.check(mix, rules, voice, bgm, None)
            finally:
                al.short_term = orig

        ok = run(14.0, 6.0)
        assert status(ok, "bgm_no_voice") == "PASS" and status(ok, "speech_floor") == "PASS"
        for gap in (2.0, 11.0):  # too loud / too quiet for the open bed: WARN, never FAIL
            res = run(14.0, gap)
            assert status(res, "bgm_no_voice") == "WARN", gap
            assert not any(r["status"] == "FAIL" for r in res), "no-voice bed must not FAIL"
        assert status(run(5.0, 6.0), "speech_floor") == "FAIL", "speech floor 8 LU is still a hard gate"
        # fewer than min_gap_s of gap windows -> verdict omitted (nothing measured), not a failure
        sv_short = [(t, -70.0 if 5.0 <= t < 5.1 else vl) for t in ts]
        sb_short = [(t, vl - 14.0) for t, _ in sv_short]
        orig = _patch_short_term({"voice.wav": sv_short, "bgm.wav": sb_short, "mix.wav": []})
        try:
            assert all(r["id"] != "bgm_no_voice" for r in al.check(mix, rules, voice, bgm, None))
        finally:
            al.short_term = orig
        # a PARTIAL key is completed with defaults by load_rules
        partial_file = wd / "partial.json"
        doc = json.loads(cv.DEFAULT_RULES_JSON.read_text(encoding="utf-8"))
        doc["params"]["audio"]["bgm_no_voice_lu"] = {"target": 6.0}
        partial_file.write_text(json.dumps(doc), encoding="utf-8")
        loaded = al.load_rules(partial_file)["bgm_no_voice_lu"]
        assert (loaded["min"], loaded["max"], loaded["min_gap_s"]) == (4.0, 8.0, 1.5), loaded
    print("[PASS] no-voice bed 4..8 LU: PASS / WARN, never FAIL; speech floor 8 LU still FAIL")


def test_lra_and_short_term_max_are_informational() -> None:
    with tempfile.TemporaryDirectory(prefix="pfd_loud_") as td:
        wd = Path(td)
        rules = tiktok_rules(wd)
        mix = make_tone(wd / "mix.wav", lufs=-12.0)
        assert al.measure(mix).get("lra") is not None
        real_measure = al.measure
        try:
            for lra, st_max, want_lra, want_st in ((2.0, -9.0, "PASS", "PASS"), (8.0, -5.0, "WARN", "WARN"), (6.0, -7.0, "PASS", "PASS")):
                al.measure = lambda p, *a, _l=lra, **k: {**real_measure(p, *a, **k), "lra": _l}
                orig = _patch_short_term({"mix.wav": [(3.0, st_max - 2.0), (3.1, st_max), (3.2, st_max - 1.0)]})
                try:
                    res = al.check(mix, rules, None, None, None)
                finally:
                    al.short_term = orig
                assert status(res, "lra") == want_lra and status(res, "short_term_max") == want_st, (lra, st_max)
                assert not any(r["status"] == "FAIL" for r in res if r["id"] in ("lra", "short_term_max"))
        finally:
            al.measure = real_measure
        # real ffmpeg on a 3 s clip: ebur128 reports an LRA artefact (~20 LU, the 3 s window is not full yet; R128 s1: LRA is
        # meaningless for short clips). It must stay a WARN, never a FAIL.
        res = al.check(mix, rules, None, None, None)
        assert status(res, "lra") in ("PASS", "WARN") and not any(r["status"] == "FAIL" for r in res if r["id"] in ("master_lufs", "lra"))
    print("[PASS] LRA (> 6 warns) and short-term max (> -7 LUFS warns) are WARN-only")


if __name__ == "__main__":
    test_table_values_via_build_effective_rules()
    test_no_official_tiktok_figure_claimed()
    test_platform_profile_unchanged()
    test_audio_levels_accepts_profile_and_tiktok_verdicts()
    test_sfx_tiers_plan_accepts_new_tiers()
    test_no_voice_bed_is_warn_not_fail()
    test_lra_and_short_term_max_are_informational()
    print("TẤT CẢ ĐẠT (loudness table v7.5.0)")
