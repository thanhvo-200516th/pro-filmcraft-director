#!/usr/bin/env python3
"""
Tests for `scripts/tools/studio_recipe.py` (current version from the SKILL.md frontmatter): the stateless Look S scene planner and, since v7.7.0, the hook 0-5 s template,
the max-hold rule, the visual-change-per-5-s rule and the same-source rule, since v7.8.0 the text-voice sync, product-safe hero,
minimum text size, background motion floor and static-hold rules, plus the `studio_14` audio profile and the
`presets/studio_scene_recipe.json` preset. No media, no ffmpeg.

Run: python3 tests/test_studio_recipe.py
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
SCRIPT = TOOLS_DIR / "studio_recipe.py"
PRESET = SKILL_ROOT / "presets" / "studio_scene_recipe.json"
sys.path.insert(0, str(TOOLS_DIR))

import studio_recipe as sr  # noqa: E402

DURATION = 40.63


def _skill_version() -> str:
    """The one shared version source: the `vX.Y.Z` in the SKILL.md frontmatter."""
    m = re.search(r"\bv(\d+\.\d+\.\d+)", (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
    assert m, "SKILL.md frontmatter must carry a vX.Y.Z version"
    return m.group(1)


VERSION = _skill_version()


def v21_words(duration: float = DURATION) -> list[list]:
    """193 words in the `[[word, t0, t1], ...]` shape of the V21 transcript (small gaps, a few pauses)."""
    n, step = 193, (duration - 0.2) / 193
    words, t = [], 0.02
    for i in range(n):
        gap = 0.18 if i % 17 == 16 else 0.0
        words.append([f"w{i}", round(t + gap, 3), round(t + gap + step * 0.7, 3)])
        t += gap + step * 0.9
    return words


def _worlds(plan: dict) -> list[tuple[str, str]]:
    return [(s["family"], s["hue"]) for s in plan["scenes"]]


def test_01_plan_covers_timeline_and_follows_the_v21_pattern() -> None:
    plan = sr.plan_scenes(v21_words(), DURATION)
    sc = plan["scenes"]
    assert sc[0]["start"] == 0.0 and abs(sc[-1]["end"] - DURATION) < 1e-6
    for a, b in zip(sc, sc[1:]):
        assert a["end"] == b["start"] and a["end"] > a["start"], (a, b)
    modes = [s["mode"] for s in sc]
    assert modes[0] == "H" and modes[-1] == "B", modes
    assert "N" in modes and modes.count("S") >= 2 and "A1" in modes and "A2" in modes, modes
    assert set(modes) <= {"H", "A1", "A2", "B", "P", "N", "S"}, modes
    print("[PASS] 01 scenes tile 0..duration and follow hook=H, tension=N, steps=S, CTA=B")


def test_02_polarity_plain_cap_and_world_rules() -> None:
    plan = sr.plan_scenes(v21_words(), DURATION)
    st = plan["stats"]
    assert st["light_count"] >= 2 and st["light_share"] >= 0.14, st
    assert st["plain_share"] <= 0.25 and st["ok"] is True and st["violations"] == [], st
    w = _worlds(plan)
    assert all(a != b for a, b in zip(w, w[1:])), f"adjacent beats share a colour world: {w}"
    rec = json.loads(PRESET.read_text(encoding="utf-8"))
    ok_hex = {c["jewel"] for c in rec["chapters"]} | {c["ink_on_light"] for c in rec["chapters"]}
    assert all(s["jewel"] in ok_hex for s in plan["scenes"])
    assert all(s["jewel"] in {c["ink_on_light"] for c in rec["chapters"]} for s in plan["scenes"] if s["mode"] == "P")
    assert sorted({s["act"] for s in plan["scenes"]}) == [1, 2, 3, 4]
    light = [s for s in plan["scenes"] if s["mode"] == "P"]
    assert all(s["bg"] == "#FAFAFA" or s["bg"] in {"#F6F6F8", "#F3F8F5", "#FAF7F2"} for s in light)
    print("[PASS] 02 >=2 light scenes (>=14%), plain A-roll <= 25%, no adjacent same colour world, jewel per act")


def test_03_dict_doc_equals_bare_array_and_inputs_untouched() -> None:
    arr = v21_words()
    before = copy.deepcopy(arr)
    from_arr = sr.plan_scenes(arr, DURATION)
    from_doc = sr.plan_scenes({"words": arr, "cadence_and_jcut_plan": {}}, DURATION)
    from_alt = sr.plan_scenes({"words_tl": arr}, DURATION)
    assert from_arr == from_doc == from_alt
    assert arr == before, "plan_scenes must not mutate its input"
    assert sr.plan_scenes(arr, DURATION) == from_arr, "deterministic"
    print("[PASS] 03 probe dict doc == bare array, deterministic, input untouched")


def test_04_short_and_wordless_inputs() -> None:
    short = sr.plan_scenes(v21_words(8.0), 8.0)
    assert short["stats"]["light_count"] >= 2 and short["stats"]["ok"], short["stats"]
    assert all(s["end"] - s["start"] >= 0.99 for s in short["scenes"]), short["scenes"]
    empty = sr.plan_scenes([], 20.0)
    assert empty["scenes"][0]["start"] == 0.0 and abs(empty["scenes"][-1]["end"] - 20.0) < 1e-6
    d = sr.plan_scenes(v21_words(), DURATION, look="D")
    assert [s["mode"] for s in d["scenes"]] == ["D"] and d["look"] == "D"
    for bad in (dict(duration=0.0), dict(duration=DURATION, look="X")):
        try:
            sr.plan_scenes(v21_words(), **bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")
    print("[PASS] 04 8 s plan keeps >=2 light scenes, empty words ok, look D is one strip scene, bad args raise")


def test_05_check_scenes_flags_violations() -> None:
    plan = sr.plan_scenes(v21_words(), DURATION)
    bad = copy.deepcopy(plan["scenes"])
    for s in bad:
        s["mode"], s["family"], s["hue"] = "A0", "plain", "#111111"
    v = sr.check_scenes(bad, DURATION)
    assert any("plain" in x for x in v) and any("adjacent" in x for x in v) and any("light" in x for x in v), v
    assert sr.check_scenes(plan["scenes"], DURATION) == []
    print("[PASS] 05 check_scenes reports plain cap, adjacent world and light minimum")


def test_06_cli() -> None:
    with tempfile.TemporaryDirectory() as td:
        words = Path(td) / "w.json"
        out = Path(td) / "scenes.json"
        words.write_text(json.dumps({"words": v21_words()}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), "--words", str(words), "--duration", str(DURATION), "--out", str(out)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["stats"]["light_count"] >= 2 and doc["look"] == "S"
        r2 = subprocess.run([sys.executable, str(SCRIPT), "--words", str(Path(td) / "none.json"), "--duration", "10", "--out", str(out)],
                            capture_output=True, text=True)
        assert r2.returncode == 2, r2.returncode
    print("[PASS] 06 CLI writes scenes.json (exit 0) and exits 2 on a missing words file")


def test_07_script_is_small_and_preset_is_clean() -> None:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 480, f"studio_recipe.py must stay small (<= 480 lines since v7.8.0 added the text-voice and motion validators), has {len(lines)}"
    text = PRESET.read_text(encoding="utf-8")
    assert unicodedata.normalize("NFC", text) == text
    data = json.loads(text)
    assert data["version"] == VERSION and len({c["act"] for c in data["chapters"]}) == 4 and len(data["grid"]) >= 12
    assert set(data["v21_map"].values()) == {"A1", "A2", "B"}
    banned = "/home/" + "thanh"
    assert banned not in text and banned not in "\n".join(lines)
    print("[PASS] 07 helper <= 480 lines, preset NFC, 4 acts (5 chapters), V21 map uses A1/A2/B only")


def test_08_studio_14_audio_profile() -> None:
    prof = json.loads((SKILL_ROOT / "presets" / "profile_overrides.json").read_text(encoding="utf-8"))
    ap = prof["audio_profiles"]
    s14 = ap["studio_14"]
    assert s14["target_lufs"] == -14.0 and s14["true_peak_dbtp"] == -1.2 and s14["limiter_db"] == -2.2
    assert s14.get("no_ducking") is False and s14["bgm_stops_allowed"] is True and s14["sfx_max_cues"] == 72
    assert s14["rules_override"]["master_lufs"]["final"] == -14.0
    assert ap["platform"]["target_lufs"] == -16.0 and ap["platform"]["true_peak_dbtp"] == -1.5
    assert ap["tiktok_loud"]["target_lufs"] == -12.0 and ap["tiktok_loud"]["true_peak_dbtp"] == -1.0
    assert ap["tiktok_loud"]["limiter_db"] == -1.2 and ap["tiktok_loud"]["no_ducking"] is True
    doc = ap["tiktok_loud"]["_doc"]
    assert "Look D" in doc and "UNVALIDATED" in doc, "tiktok_loud _doc must say Look D and UNVALIDATED"
    assert prof["version"] == "7.6.0"
    print("[PASS] 08 studio_14 profile present, platform / tiktok_loud values unchanged, tiktok_loud marked Look D")


# --------------------------------------------------------------------------------------------- v7.7.0: hook / pacing
def _sev(findings: list[dict], level: str = "error") -> set[str]:
    return {f["rule"] for f in findings if f["severity"] == level}


def test_09_hook_template_and_validator() -> None:
    rec = json.loads(PRESET.read_text(encoding="utf-8"))
    assert rec["version"] == VERSION and "hook_0_5s" in rec and "pacing" in rec, sorted(rec)
    hook = sr.hook_template()
    assert hook == sr.hook_template(rec) and hook is not rec["hook_0_5s"], "hook_template returns a copy"
    ev = hook["events"]
    texts = [e for e in ev if e["kind"] == "text"]
    assert min(e["t_ms"] for e in texts) <= 200 and sum(1 for e in texts if e["t_ms"] < 3000) <= 5
    assert hook["hero_box"]["height_frac"] == [0.12, 0.18] and hook["first_text_max_ms"] == 200
    assert all(e["t_ms"] - e["peak_ms"] == e["at_ms"] for e in ev if e["kind"] == "sfx" and "peak_ms" in e), "sfx at_ms = target - peak"
    vac = next(e for e in ev if e["kind"] == "vacuum")
    assert vac["duck_db"] <= -12 and 3200 <= vac["t_ms"] <= 3380
    assert all(e.get("basis") == "ƯỚC" for e in ev if e["kind"] in ("sfx", "riser", "vacuum")), "SFX times are estimates"
    clean = sr.check_hook(hook)  # no words given: only the 'no words provided' warning, never an error
    assert not _sev(clean) and _sev(clean, "warn") == {"text_voice_sync"}, clean
    # negative cases: each one trips its own rule
    def mutate(fn):
        h = sr.hook_template()
        fn(h)
        return sr.check_hook(h)
    late = mutate(lambda h: [e.update(t_ms=e["t_ms"] + 400) for e in h["events"] if e["kind"] == "text"])
    assert "first_text" in _sev(late), late
    small = mutate(lambda h: h["hero_box"].update(height_frac=0.07))
    assert "hero_box" in _sev(small), small
    big = mutate(lambda h: h["hero_box"].update(height_frac=0.30))
    assert "hero_box" in _sev(big), big
    crowd = mutate(lambda h: h["events"].extend({"t_ms": 200 + 60 * i, "kind": "text", "dur_ms": 700} for i in range(4)))
    assert "text_budget" in _sev(crowd), crowd
    short = mutate(lambda h: next(e for e in h["events"] if e["kind"] == "text").update(dur_ms=300))
    assert "text_hold" in _sev(short), short
    soft = mutate(lambda h: next(e for e in h["events"] if e["kind"] == "vacuum").update(duck_db=-6))
    assert "vacuum_dip" in _sev(soft), soft
    novac = mutate(lambda h: h["events"].__setitem__(slice(None), [e for e in h["events"] if e["kind"] != "vacuum"]))
    assert "vacuum_dip" in _sev(novac), novac
    flat = mutate(lambda h: h["events"].__setitem__(slice(None), [e for e in h["events"] if e["kind"] in ("vacuum", "sfx", "voice", "riser")] + [e for e in h["events"] if e["kind"] == "text"][:1]))
    assert "hook_resets" in _sev(flat), flat
    offcut = mutate(lambda h: next(e for e in h["events"] if e["kind"] == "sfx" and e["id"] == "whoosh_punch").update(peak_ms=60))
    assert "whoosh_align" in _sev(offcut, "warn"), offcut
    loud = mutate(lambda h: h.update(voice_onset_ms=400))
    assert "voice_onset" in _sev(loud, "warn"), loud
    print("[PASS] 09 hook_0_5s template validates clean; first text, hero box, text budget / hold, vacuum dip, resets, whoosh align and voice onset each trip their rule")


def _shots(*cuts: float) -> list[dict]:
    edges = [0.0, *cuts]
    return [{"id": f"s{i}", "start": a, "end": b} for i, (a, b) in enumerate(zip(edges, edges[1:]))]


def test_10_max_hold_rule_and_dead_hold_share() -> None:
    assert sr._load()["pacing"]["max_hold_s"] == 2.4 and sr._load()["pacing"]["law_hold_s"] == 2.0
    # positive: a 3.9 s scene with a zoom reset at 1.9 s holds only 2.0 s; error-free
    ok = sr.check_pacing(_shots(3.9), resets=[0.7, 1.9, 2.9], duration=3.9)
    assert not _sev(ok["findings"]) and ok["hold_s"] <= 2.0 and "hold_s" in ok["windows"][0] and "dead_hold_share" in ok["windows"][0], ok
    # negative: the same 3.9 s scene with nothing inside is a 3.9 s hold -> error on the shot id
    bad = sr.check_pacing(_shots(3.9), duration=3.9)
    hold = [f for f in bad["findings"] if f["rule"] == "max_hold"]
    assert hold and hold[0]["severity"] == "error" and hold[0]["shot"] == "s0" and abs(hold[0]["value"] - 3.9) < 1e-6, bad
    assert abs(bad["hold_s"] - 3.9) < 1e-6 and bad["ok"] is False
    # 2.2 s: above the 2.0 s law, below the 2.4 s recipe cap -> warn only
    mid = sr.check_pacing(_shots(2.2, 4.4), resets=[1.0, 3.3], duration=4.4)
    assert not _sev(mid["findings"]) and not _sev(mid["findings"], "warn") - {"short_shots"}, mid
    warn = sr.check_pacing(_shots(2.2), resets=[], duration=2.2)
    assert _sev(warn["findings"], "warn") == {"law_hold"} and not _sev(warn["findings"]) and warn["ok"], warn
    # resets given as dicts (kind + t) work; kinds outside the reset set do not count
    d = sr.check_pacing(_shots(3.0), resets=[{"t": 1.5, "kind": "zoom"}], duration=3.0)
    assert "max_hold" not in _sev(d["findings"]), d
    nr = sr.check_pacing(_shots(3.0), resets=[{"t": 1.5, "kind": "sfx"}], duration=3.0)
    assert "max_hold" in _sev(nr["findings"]), nr
    # dead_hold_share: nothing for 10 s = 1.0; a cut every 0.8 s = 0.0; v2-like mix in between
    dead = sr.check_pacing(_shots(10.0), duration=10.0)
    live = sr.check_pacing(_shots(*[round(0.8 * i, 3) for i in range(1, 13)]), duration=9.6)
    mix = sr.check_pacing(_shots(4.0, 6.0, 8.0, 10.0), resets=[5.0, 6.5, 7.0, 8.5, 9.0, 9.5], duration=10.0)
    assert dead["dead_hold_share"] == 1.0 and live["dead_hold_share"] == 0.0, (dead["dead_hold_share"], live["dead_hold_share"])
    assert 0.0 < mix["dead_hold_share"] < 1.0 and abs(mix["dead_hold_share"] - 0.4) < 1e-6, mix["dead_hold_share"]
    assert live["ok"] and not dead["ok"]
    print("[PASS] 10 max-hold: >2.4 s error with shot id, 2.0-2.4 s warn, hold_s and dead_hold_share per window, dict resets, shots left untouched")


def test_11_visual_change_per_5s() -> None:
    def rule(rep: dict, name: str, t0: float) -> list[dict]:
        return [f for f in rep["findings"] if f["rule"] == name and f["t0"] == t0]

    # hook window needs >= 3 resets, every later 5 s window >= 2 (a shot boundary and an explicit reset both count)
    good = sr.check_pacing(_shots(2.0, 4.0, 6.0, 8.0, 10.0), resets=[1.0, 3.0, 5.5, 7.0, 9.0], duration=10.0)
    assert not [f for f in good["findings"] if f["rule"] == "resets_per_5s"], good
    assert [w["resets"] for w in good["windows"]] == [4, 5], good["windows"]
    hook_poor = sr.check_pacing(_shots(2.4, 5.0, 7.0, 9.0, 10.0), resets=[1.2, 6.0, 8.0], duration=10.0)
    w0 = rule(hook_poor, "resets_per_5s", 0.0)
    assert w0 and w0[0]["limit"] == 3 and w0[0]["value"] == 2 and w0[0]["severity"] == "error" and hook_poor["ok"] is False, hook_poor
    assert not rule(hook_poor, "resets_per_5s", 5.0), "window 5-10 has 3 resets, enough"
    only1 = sr.check_pacing(_shots(1.0, 2.0, 3.0, 4.0, 8.0, 10.0), resets=[], duration=10.0)
    w1 = rule(only1, "resets_per_5s", 5.0)  # the cut at 8.0 is the only change; 10.0 is the end, not a change
    assert w1 and w1[0]["value"] == 1 and w1[0]["limit"] == 2 and not rule(only1, "resets_per_5s", 0.0), only1
    # resets within 0.1 s of each other are one change (a cut with its text)
    twin = sr.check_pacing(_shots(5.0, 10.0), resets=[1.0, 1.04, 2.0, 2.05, 7.0, 8.0], duration=10.0)
    assert [w["resets"] for w in twin["windows"]] == [2, 3], twin["windows"]
    # a partial last window (2.5 s) scales the minimum to 1: one change is enough, none is not
    part_ok = sr.check_pacing(_shots(1.0, 2.0, 3.0, 4.0, 5.0, 6.5, 7.5), resets=[], duration=7.5)
    assert not rule(part_ok, "resets_per_5s", 5.0), part_ok
    part_bad = sr.check_pacing(_shots(1.0, 2.0, 3.0, 4.9, 7.5), resets=[], duration=7.5)
    pb = rule(part_bad, "resets_per_5s", 5.0)
    assert pb and pb[0]["value"] == 0 and pb[0]["limit"] == 1, part_bad
    # thresholds come from the preset argument; the default preset is not mutated
    strict = copy.deepcopy(sr._load())
    strict["pacing"]["min_resets_other_window"] = 6
    s = sr.check_pacing(_shots(2.0, 4.0, 6.0, 8.0, 10.0), resets=[1.0, 3.0, 5.0, 7.0, 9.0], duration=10.0, preset=strict)
    assert rule(s, "resets_per_5s", 5.0), s
    assert sr._load()["pacing"]["min_resets_other_window"] == 2
    # shots under 1 s: advisory (warn) per 10 s, never an error
    few = sr.check_pacing(_shots(2.0, 4.0, 6.0, 8.0, 10.0), resets=[1.0, 3.0, 5.0, 7.0, 9.0], duration=10.0)
    assert "short_shots" in _sev(few["findings"], "warn") and few["ok"], few
    many = sr.check_pacing(_shots(0.6, 1.2, 3.0, 4.5, 6.0, 7.5, 9.0, 10.0), resets=[], duration=10.0)
    assert "short_shots" not in {f["rule"] for f in many["findings"]}, many
    assert many["short_shot_share"] == 0.25 and few["short_shot_share"] == 0.0
    # planner output is a valid input and the planner itself is unchanged
    plan = sr.plan_scenes(v21_words(), DURATION)
    rep = sr.check_pacing(plan["scenes"], duration=DURATION)
    assert plan["stats"]["ok"] is True and rep["windows"][0]["t0"] == 0.0 and rep["windows"][-1]["t1"] == 40.0  # the 0.63 s tail is under the 2.5 s partial-window minimum
    print("[PASS] 11 resets per 5 s: hook window >= 3, later windows >= 2, twins merged, partial window scaled, preset thresholds, short shots advisory")


def test_12_same_source_seconds_and_punch_caps() -> None:
    clean = [{"id": "S13", "source": "flow/09", "src": [1.0, 3.35]}, {"id": "S14", "source": "02_serum_orbit", "src": [0.0, 2.0]},
             {"id": "S15", "source": "flow/09", "src": [3.35, 5.0]}]
    assert sr.check_source_reuse(clean) == []
    dup = clean[:1] + [{"id": "S14", "source": "flow/09", "src": [1.0, 3.35]}]
    f = sr.check_source_reuse(dup)
    assert len(f) == 1 and f[0]["rule"] == "source_reuse" and f[0]["severity"] == "error" and abs(f[0]["value"] - 2.35) < 1e-6, f
    assert sr.check_source_reuse(clean[:1] + [{"id": "x", "source": "flow/09", "src": [3.3, 4.0]}])[0]["value"] > 0.0
    caps = sr._load()["camera_punch_caps"]
    assert caps["b_cutout"] == 0.06 and caps["a1_card"] == 0.12 and caps["pip_inner"] == 0.08 and caps["fullscreen_broll"] == 0.25
    assert caps["velvet_settle"] == {"from": 1.20, "to": 1.02, "dur_s": 0.7}
    print("[PASS] 12 same B-roll source seconds flagged (2.35 s overlap), disjoint ranges pass, camera punch caps in the preset")


# --------------------------------------------------------------------------------------------- v7.8.0: text-voice, safe zone, motion floor
# subset of the v3 voice (words_tl_array.json), copied here so the test never reads the user's file
VO = [("Vì", 0.02, 0.12), ("trên", 0.12, 0.34), ("đây", 0.34, 0.52), ("là", 0.52, 0.86), ("video", 0.86, 1.06), ("sản", 1.06, 1.24),
      ("phẩm", 1.24, 1.48), ("mà", 1.48, 1.66), ("bọn", 1.66, 1.8), ("mình", 1.8, 1.92), ("vừa", 1.92, 2.06), ("làm", 2.06, 2.16),
      ("cho", 2.16, 2.26), ("các", 2.26, 2.36), ("hàng", 2.36, 2.58), ("và", 2.58, 2.76), ("phía", 2.76, 2.94), ("dưới", 2.94, 3.2),
      ("là", 3.2, 3.48), ("3", 3.48, 3.66), ("sản", 3.66, 3.86), ("phẩm", 3.86, 4.24)]


def _hook_with(texts: list[dict]) -> dict:
    h = sr.hook_template()
    h["events"] = [e for e in h["events"] if e["kind"] != "text"] + texts
    return h


def _txt(t_ms: int, text: str, tier: str = "support", **kw) -> dict:
    return {"t_ms": t_ms, "kind": "text", "id": f"t{t_ms}", "tier": tier, "text": text, "dur_ms": 700, "voice_words": text.lower().split(), **kw}


def test_13_hook_text_from_words_and_voice_sync() -> None:
    ev = sr.hook_text_from_words(VO)
    assert [e["tier"] for e in ev] == ["lead", "hero", "support"], ev
    # v7.9.0 strict default: the lead line lands 20 ms BEFORE its first word ("trên" at 120 ms -> 100 ms); strict=False keeps the old +30 ms
    assert [e["t_ms"] for e in ev] == [100, 700, 1500], [e["t_ms"] for e in ev]
    assert ev[0]["lead_ms"] == 20 and [e["t_ms"] for e in sr.hook_text_from_words(VO, strict=False)] == [150, 700, 1500]
    assert ev[0]["text"] == "TRÊN ĐÂY LÀ" and ev[1]["text"].startswith("VIDEO") and ev[2]["text"] == "BỌN MÌNH VỪA LÀM", [e["text"] for e in ev]
    assert all(unicodedata.normalize("NFC", e["text"]) == e["text"] for e in ev)
    assert VO is not None and all(e["kind"] == "text" and e["voice_words"] for e in ev)
    assert not _sev(sr.check_hook(_hook_with(ev), words=VO)) and not _sev(sr.check_hook(_hook_with(ev), words=VO), "warn"), sr.check_hook(_hook_with(ev), words=VO)
    # v3 defect: hero '3 BƯỚC' at 0.17 s while '3' is voiced at 3.48 s
    bad = sr.check_hook(_hook_with([_txt(170, "3 BƯỚC", "hero", voice_words=["3", "bước"]), _txt(750, "VIDEO", "support", voice_words=["video"]), _txt(1490, "BỌN MÌNH", voice_words=["bọn", "mình"])]), words=VO)
    f = [x for x in bad if x["rule"] == "text_voice_sync" and x["severity"] == "error"]
    assert f and f[0]["value"] > 3000, bad
    # a correctly led VIDEO (text 700 ms, word 860 ms, lead 160 ms) passes; 0 ms and 360 ms leads warn, 460 ms and a negative lead fail
    lead = _txt(150, "TRÊN ĐÂY LÀ", "lead")
    ok = lambda t: [x for x in sr.check_hook(_hook_with([lead, _txt(t, "VIDEO", "hero", voice_words=["video"]), _txt(1490, "BỌN MÌNH", voice_words=["bọn", "mình"])]), words=VO) if x["rule"] == "text_voice_sync"]  # noqa: E731
    assert ok(700) == [] and ok(650) == [], (ok(700), ok(650))
    assert {x["severity"] for x in ok(860)} == {"warn"}, "lead 0 ms is allowed but outside the 100-250 ms comfort band"
    assert {x["severity"] for x in ok(500)} == {"warn"}, ok(500)  # lead 360 ms
    assert {x["severity"] for x in ok(400)} == {"error"} and {x["severity"] for x in ok(900)} == {"error"}  # lead 460 ms / -40 ms
    # accent-folded, lower-cased comparison; the first text may lead by -50..+250 ms
    assert [x for x in sr.check_hook(_hook_with([_txt(150, "TREN DAY LA", "lead", voice_words=["TREN", "DAY"]), _txt(700, "VIDEO", "hero", voice_words=["VIDEO"]), _txt(1490, "BON", voice_words=["bon"])]), words=VO) if x["rule"] == "text_voice_sync"] == []
    late_first = sr.check_hook(_hook_with([_txt(150, "TRÊN", "lead", voice_words=["trên"]), _txt(700, "VIDEO", "hero", voice_words=["video"]), _txt(1490, "BỌN", voice_words=["bọn"])]), words=[("trên", 0.45, 0.6), *VO[4:]])
    assert "text_voice_sync" in _sev(late_first), "first text leading by 300 ms is above the +250 ms limit"
    # a numeral hero is only allowed when the voice says it within +-400 ms
    num_ok = sr.check_hook(_hook_with([lead, _txt(3300, "3", "hero", voice_words=["3"])]), words=VO)
    assert not [x for x in num_ok if x["rule"] == "text_voice_sync" and x["severity"] == "error"], num_ok
    # no words: only a warning; an unspoken hero word is an error
    nw = [x for x in sr.check_hook(_hook_with(ev)) if x["rule"] == "text_voice_sync"]
    assert [x["severity"] for x in nw] == ["warn"] and "no words provided" in nw[0]["message"], nw
    ghost = sr.check_hook(_hook_with([lead, _txt(700, "KHUYẾN MÃI", "hero", voice_words=["khuyến", "mãi"])]), words=VO)
    assert "text_voice_sync" in _sev(ghost), ghost
    print("[PASS] 13 hook_text_from_words (lead 100 / hero 700 / clause 1500), text_voice_sync: '3 BƯỚC' at 0.17 s errors, VIDEO lead 160 ms passes, folding, numeral window, words=None warns")


def test_14_hero_safe_zone_and_min_size() -> None:
    lead = _txt(150, "TRÊN ĐÂY LÀ", "lead")
    mk = lambda box, **hb: {**_hook_with([lead, _txt(700, "VIDEO", "hero", voice_words=["video"], box=box)]), **hb}  # noqa: E731
    over = sr.check_hook(mk((140, 700, 940, 1000), product_bbox=(270, 96, 830, 1670)), words=VO)
    f = [x for x in over if x["rule"] == "hero_safe_zone"]
    assert f and f[0]["severity"] == "error" and f[0]["value"] > 0, over
    inside = sr.check_hook(mk((140, 297, 940, 590), product_bbox=(270, 640, 830, 1670)), words=VO)
    assert "hero_safe_zone" not in {x["rule"] for x in inside}, inside
    # stage only: the cap top is 0.32 H = 614 px; the hero must end above it
    assert "hero_safe_zone" not in {x["rule"] for x in sr.check_hook(mk((140, 297, 940, 590), stage={"s": 0.72}), words=VO)}
    assert "hero_safe_zone" in _sev(sr.check_hook(mk((140, 400, 940, 700), stage={"s": 0.72}), words=VO)), "hero crosses the cap-top line"
    assert 0.32 * 1920 == 614.4 and sr._load()["hook_0_5s"]["hero_box"]["stage"]["s"] == 0.72
    # minimum size: 64 px font, 3.3 % glyph box; the lead line is not counted into the 12-18 % hero tier
    small = sr.check_hook(_hook_with([_txt(150, "từ 3 ảnh thô", "lead", font_px=31, voice_words=["trên"]), _txt(700, "VIDEO", "hero", voice_words=["video"])]), words=VO)
    assert "text_min_size" in _sev(small), small
    thin = sr.check_hook(_hook_with([_txt(150, "TRÊN", "lead", glyph_frac=0.02, voice_words=["trên"]), _txt(700, "VIDEO", "hero", voice_words=["video"])]), words=VO)
    assert "text_min_size" in _sev(thin), thin
    fine = sr.check_hook(_hook_with([_txt(150, "TRÊN", "lead", font_px=72, glyph_frac=0.04, voice_words=["trên"]), _txt(700, "VIDEO", "hero", voice_words=["video"], height_frac=0.153)]), words=VO)
    assert "text_min_size" not in {x["rule"] for x in fine} and "hero_box" not in {x["rule"] for x in fine}, fine
    tiny_hero = sr.check_hook(_hook_with([_txt(150, "TRÊN", "lead", height_frac=0.04, voice_words=["trên"]), _txt(700, "VIDEO", "hero", voice_words=["video"], height_frac=0.08)]), words=VO)
    assert "hero_box" in _sev(tiny_hero), "hero tier box 8 % of H is outside 12-18 %; the lead's 4 % is not counted"
    print("[PASS] 14 hero_safe_zone (bbox overlap error, band pass, cap-top 0.32 H), text_min_size (64 px / 3.3 %), hero tier box per tier")


def _rs(*pairs) -> list[dict]:
    return [{"t": t, "kind": k, "layer": ly, "mag": m} for t, k, ly, m in pairs]


def test_15_hook_motion_floor() -> None:
    # PiP pops and text are overlay resets: they never satisfy the floor
    pip_only = _rs((0.1, "zoom", "overlay", 0.08), (1.2, "text", "overlay", None), (2.58, "zoom", "overlay", 0.12), (3.0, "text", "overlay", None))
    f = sr.hook_motion_floor(pip_only)
    assert f and all(x["rule"] == "hook_motion_floor" and x["severity"] == "error" for x in f) and len(f) >= 3, f
    bg = _rs((0.0, "zoom", "bg", 0.22), (1.33, "cut", "bg", None), (2.03, "glint", "bg", None), (2.72, "card", "bg", None))
    assert sr.hook_motion_floor(bg) == [], sr.hook_motion_floor(bg)
    assert sr.hook_motion_floor(bg + pip_only) == []
    # a bg zoom step under 4 % is not a reset; plain tuples and floats are bg resets (back-compat)
    weak = _rs((0.0, "zoom", "bg", 0.22), (1.33, "cut", "bg", None), (2.2, "zoom", "bg", 0.02))
    assert {round(x["t0"]) for x in sr.hook_motion_floor(weak)} >= {2}, sr.hook_motion_floor(weak)
    assert sr.hook_motion_floor([(0.2, "zoom"), 1.4, (2.3, "cut"), (3.0, "flash")]) == []
    # inside check_hook: template passes, a template with only the PiP pop in 2-3 s fails
    hook = sr.hook_template()
    assert "hook_motion_floor" not in {x["rule"] for x in sr.check_hook(hook)}, sr.check_hook(hook)
    cut = sr.hook_template()
    cut["events"] = [e for e in cut["events"] if not (e["kind"] in ("glint", "card", "zoom", "cut", "flash") and 2000 <= e["t_ms"] < 3000 and e["id"] != "pip_pop")]
    assert "hook_motion_floor" in _sev(sr.check_hook(cut)), sr.check_hook(cut)
    print("[PASS] 15 hook_motion_floor: PiP pops and text do not count, bg cut / glint / card / zoom >= 4 % do, tuples back-compat, template clean")


def test_16_bg_static_hold_and_micro_moves() -> None:
    def shot(rate: float | None, t1: float = 1.2) -> list[dict]:
        mv = [{"kind": "push", "t0": 0.0, "t1": t1, "rate_pct_s": rate}] if rate else []
        return [{"id": "b0", "start": 0.0, "end": t1, "broll": True, "moves": mv}, {"id": "b1", "start": t1, "end": t1 + 0.6, "broll": True, "moves": []}]
    slow = sr.check_pacing(shot(4.0), duration=1.8)
    f = [x for x in slow["findings"] if x["rule"] == "bg_static_hold"]
    assert f and f[0]["severity"] == "error" and f[0]["shot"] == "b0" and abs(f[0]["value"] - 1.2) < 1e-6 and slow["ok"] is False, slow
    fast = sr.check_pacing(shot(14.0), duration=1.8)
    assert "bg_static_hold" not in {x["rule"] for x in fast["findings"]}, fast
    # outside the 3.4 s hook window the limit is 1.2 s and a breach is only a warning
    late = [{"id": "b2", "start": 5.0, "end": 6.5, "broll": True, "moves": []}]
    lf = [x for x in sr.check_pacing(late, duration=6.5)["findings"] if x["rule"] == "bg_static_hold"]
    assert lf and lf[0]["severity"] == "warn", lf
    # a bg reset (cut or zoom step) splits the hold; an overlay reset does not
    split = sr.check_pacing(shot(None), resets=[{"t": 0.6, "kind": "zoom", "layer": "bg", "mag": 0.08}], duration=1.8)
    assert "bg_static_hold" not in {x["rule"] for x in split["findings"]}
    ovl = sr.check_pacing(shot(None), resets=[{"t": 0.6, "kind": "zoom", "layer": "overlay", "mag": 0.12}], duration=1.8)
    assert "bg_static_hold" in {x["rule"] for x in ovl["findings"]}
    # pan >= 4 % of the crop per second and a glint sweep are micro-moves; a 2 % pan is not
    pan = [{"id": "p", "start": 0.0, "end": 1.2, "broll": True, "moves": [{"kind": "pan", "t0": 0.0, "t1": 1.2, "rate_pct_s": 4.0}]}]
    assert "bg_static_hold" not in {x["rule"] for x in sr.check_pacing(pan, duration=1.2)["findings"]}
    weakpan = [{**pan[0], "moves": [{"kind": "pan", "t0": 0.0, "t1": 1.2, "rate_pct_s": 2.0}]}]
    assert "bg_static_hold" in {x["rule"] for x in sr.check_pacing(weakpan, duration=1.2)["findings"]}
    glint = [{**pan[0], "moves": [{"kind": "glint", "t0": 0.0, "t1": 1.2}]}]
    assert "bg_static_hold" not in {x["rule"] for x in sr.check_pacing(glint, duration=1.2)["findings"]}
    # shots without a broll flag keep the old behaviour
    assert "bg_static_hold" not in {x["rule"] for x in sr.check_pacing(_shots(3.9), resets=[0.7, 1.9, 2.9], duration=3.9)["findings"]}
    # remedy: proposes a push inside the +25 % cap and cites the proof numbers; a moving source needs none
    plan = sr.plan_micro_moves(shot(4.0))
    p = [x for x in plan if x["shot"] == "b0"]
    assert p and p[0]["kind"] == "push" and p[0]["rate_pct_s"] >= 10 and p[0]["rate_pct_s"] * 1.2 <= 25 + 1e-9 and "1.23" in p[0]["proof"] and "2.09" in p[0]["proof"], plan
    assert [x for x in sr.plan_micro_moves(shot(None), source_motion={"b0": 2.0}) if x["shot"] == "b0"] == []
    long_hold = sr.plan_micro_moves([{"id": "L", "start": 0.0, "end": 4.0, "broll": True, "moves": []}])
    assert long_hold and long_hold[0]["kind"] == "split", long_hold
    print("[PASS] 16 bg_static_hold: 4 %/s x 1.2 s errors, 14 %/s passes, warn after 3.4 s, overlay resets do not split, pan / glint, plan_micro_moves cites 1.23 / 2.09")


def test_17_preset_v78_and_back_compat() -> None:
    text = PRESET.read_text(encoding="utf-8")
    rec = json.loads(text)
    h = rec["hook_0_5s"]
    assert h["first_text_max_ms"] == 200 and "3 BƯỚC" not in text and "centre_y_frac" not in text and "center_y_frac" not in text
    hero = next(e for e in h["events"] if e.get("id") == "hero")
    assert hero.get("text") is None and hero["binding"] == {"anchor_word": "auto", "lead_ms": [150, 200]}, hero
    assert "compromise" not in text and "3.48" not in text
    assert h["hero_box"]["product_safe"] is True and h["hero_box"]["stage"] == {"s": 0.72, "text_band_y": [0.07, 0.31]}
    m = rec["pacing"]["motion"]
    assert m["bg_static_run_s"] == [0.8, 1.2] and m["min_push_rate_pct_s"] == 10 and m["min_text_box_frac"] == 0.033 and m["d1_static"] == 1.0
    assert m["first_text_lead_ms"] == [-50, 250] and m["keyword_lead_ms"] == [100, 250]
    # old callers: plain tuples / floats / dicts without a layer are bg resets, check_pacing result keys are unchanged
    old = sr.check_pacing(_shots(3.9), resets=[0.7, (1.9, "zoom"), {"t": 2.9, "kind": "zoom"}], duration=3.9)
    assert old["ok"] and set(old) == {"ok", "hold_s", "dead_hold_share", "short_shot_share", "windows", "findings"}, old
    assert sr.VERSION == VERSION
    print("[PASS] 17 preset v7.8.0: first text 200 ms, hero binding (no '3 BƯỚC'), product-safe stage, pacing.motion, old callers unchanged")


if __name__ == "__main__":
    test_01_plan_covers_timeline_and_follows_the_v21_pattern()
    test_02_polarity_plain_cap_and_world_rules()
    test_03_dict_doc_equals_bare_array_and_inputs_untouched()
    test_04_short_and_wordless_inputs()
    test_05_check_scenes_flags_violations()
    test_06_cli()
    test_07_script_is_small_and_preset_is_clean()
    test_08_studio_14_audio_profile()
    test_09_hook_template_and_validator()
    test_10_max_hold_rule_and_dead_hold_share()
    test_11_visual_change_per_5s()
    test_12_same_source_seconds_and_punch_caps()
    test_13_hook_text_from_words_and_voice_sync()
    test_14_hero_safe_zone_and_min_size()
    test_15_hook_motion_floor()
    test_16_bg_static_hold_and_micro_moves()
    test_17_preset_v78_and_back_compat()
    print(f"TẤT CẢ ĐẠT (studio_recipe v{VERSION})")
