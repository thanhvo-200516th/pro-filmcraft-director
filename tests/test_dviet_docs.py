#!/usr/bin/env python3
"""
P3 verification suite for `pro-filmcraft-director` (version-agnostic, >= 7.6.0):
17-video @__dviet index, version-labelled docs, style tokens, zoom / transition / canvas presets,
text lock-ups and layout templates.

Run: python3 tests/test_dviet_docs.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
PRESETS = SKILL_ROOT / "presets"

for p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

MIN_VERSION = (7, 6, 0)


def _skill_version() -> str:
    """The current version, parsed from the SKILL.md frontmatter (`vX.Y.Z`); must be >= 7.6.0 so the tests do not break on every release."""
    front = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    m = re.search(r"\bv(\d+\.\d+\.\d+)", front)
    assert m, "SKILL.md frontmatter must carry a vX.Y.Z version"
    assert tuple(int(x) for x in m.group(1).split(".")) >= MIN_VERSION, f"SKILL.md version {m.group(1)} is older than 7.6.0"
    return m.group(1)


VERSION = _skill_version()
# Old current-version labels that must not survive in the docs (kept split so this file is not self-flagged).
STALE_LABELS = [r"v7\.1", r"v7\.2", r"v7\.3\.0"]

DVIET_IDS = [
    "7664447064352509204", "7664633717771488532", "7664835388476755220", "7664969137445276949",
    "7666801391284964628", "7667598741888634132", "7668334908615560469", "7669054598971133204",
    "7669758857471741204", "7670574911680777492", "7672413018575146261", "7677448217667063061",
    "7683763922234641684", "7688934517783989524", "7693026626333871381", "7706183278461570356",
    "7707653827016674580",
]

# Files owned by the P1 / P2 work packages: links to them are checked only when they exist.
OTHER_PACKAGE_LINK_PATTERNS = [
    r"^references/21_.*\.md$",
    r"^references/22_.*\.md$",
    r"^scripts/env_status\.py$",
    r"^scripts/tools/(fc_export|spec_from_plan|silence_cut|speed_media|sfx_auto|qa_sync|sfx_shift|broll_from_video)\.py$",
    r"^presets/(profile_overrides|sfx_catalog|pain_keywords|studio_scene_recipe)\.json$",
    r"^references/24_studio_look_recipe\.md$",
    r"^scripts/tools/studio_recipe\.py$",
]

NEW_ATOMICS = [
    "punch_220_q25", "push_130_long", "step_zoom_13_8_9", "jc_reset_push_4_10", "dolly_out_12_16",
    "radial_blur_scale_grow",
    "color_wash_multi_0p6s", "film_burn_perf_5f", "light_leak_overlay", "white_flash_0p25s",
    "vertical_roll_slide", "orange_ghost_pre_cut_5f", "vacuum_32db_0p4s",
]
TRANSITION_ATOMICS = NEW_ATOMICS[6:]


def _read(rel: str) -> str:
    return (SKILL_ROOT / rel).read_text(encoding="utf-8")


def _assert_nfc(obj, where: str) -> None:
    if isinstance(obj, str):
        assert obj == unicodedata.normalize("NFC", obj), f"non-NFC string in {where}: {obj[:40]!r}"
    elif isinstance(obj, list):
        for x in obj:
            _assert_nfc(x, where)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_nfc(k, where)
            _assert_nfc(v, where)


def _git_head_json(rel: str):
    r = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=str(SKILL_ROOT), capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------

def test_01_index_has_all_17_ids() -> None:
    idx = SKILL_ROOT / "references" / "dviet_19" / "INDEX.md"
    assert idx.is_file() and idx.stat().st_size > 0, "Missing references/dviet_19/INDEX.md"
    text = idx.read_text(encoding="utf-8")
    on_disk = sorted(p.stem for p in (idx.parent).glob("[0-9]*.md"))
    assert len(on_disk) == 17, f"Expected 17 per-video files, found {len(on_disk)}"
    assert on_disk == sorted(DVIET_IDS), "Per-video files differ from the expected 17 ids"
    for vid in DVIET_IDS:
        assert vid in text, f"INDEX.md misses video id {vid}"
        # table row: one line per id with a link to the per-video file
        assert re.search(rf"^\|\s*\[{vid}\]", text, re.M), f"INDEX.md has no table row for {vid}"
    for needle in ("ƯỚC", "estimate".lower()):
        assert needle.lower() in text.lower(), f"INDEX.md must flag estimates ({needle})"
    assert "backlog" in text and "done v7.4" in text, "INDEX.md gap table needs 'done v7.4' / 'backlog' statuses"
    for sig in ("silhouette flicker", "F1C711", "E5B70C", "F8C818", "-10.7", "+3.0", "1332x720", "1440x1080"):
        assert sig.lower() in text.lower(), f"INDEX.md synthesis misses signature {sig!r}"
    print("[PASS] INDEX.md covers 17 ids, estimates flagged, gap table present")


def test_02_version_labels() -> None:
    docs = ["SKILL.md", "README.md", "tests/test_skill_v73.py"]  # install.sh belongs to the compositor package and is not asserted here
    for rel in docs:
        text = _read(rel)
        assert VERSION in text or rel.startswith("tests/"), f"{rel} does not contain {VERSION}"  # the test file derives its version from SKILL.md
        for pat in STALE_LABELS:
            m = re.search(pat, text)
            assert not m, f"{rel} still carries stale label {m.group(0)!r}"
    skill = _read("SKILL.md")
    assert re.search(rf"^name: pro-filmcraft-director", skill, re.M), "SKILL.md frontmatter name missing"
    assert VERSION in skill.split("---", 2)[1], f"SKILL.md frontmatter must carry {VERSION}"
    h1 = [ln for ln in skill.splitlines() if ln.startswith("# ")][0]
    assert VERSION in h1, f"SKILL.md H1 must carry the frontmatter version {VERSION}: {h1}"
    assert VERSION in _read("README.md").splitlines()[0], f"README.md H1 must carry {VERSION}"
    assert VERSION in "\n".join(_read("docs/TIEN_DO_SKILL.md").splitlines()[:5]) or f"v{VERSION}" in _read("docs/TIEN_DO_SKILL.md"), f"docs/TIEN_DO_SKILL.md must mention {VERSION}"
    assert "pro-filmcraft-director v" in _read("tests/test_skill_v73.py").strip().splitlines()[-1], "final line of test_skill_v73.py must print the version"
    # The previous release label may survive only as history ("introduced in"), never in the places that name the current version.
    prev = "7.5.0"
    current_label_places = {
        "SKILL.md frontmatter": skill.split("---", 2)[1],
        "SKILL.md H1": h1,
        "README.md H1": _read("README.md").splitlines()[0],
    }
    for where, text in current_label_places.items():
        assert prev not in text, f"{where} still carries the previous release label {prev}"
    print(f"[PASS] {VERSION} present, no stale v7.1/v7.2/v7.3.0 labels and no {prev} current-version label in SKILL.md, README.md, test_skill_v73.py")


def test_03_skill_md_links_and_pointers() -> None:
    text = _read("SKILL.md")
    broken: list[str] = []
    skipped = 0
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        link = m.group(1)
        if link.startswith(("http://", "https://", "#", "mailto:")):
            continue
        rel = link.split("#", 1)[0]
        norm = (SKILL_ROOT / rel).resolve()
        if norm.exists():
            continue
        rel_clean = str(Path(rel)) if not rel.startswith("./") else str(Path(rel[2:]))
        if any(re.match(pat, rel_clean) for pat in OTHER_PACKAGE_LINK_PATTERNS):
            skipped += 1  # owned by P1/P2; allowed to be missing when P3 runs alone
            continue
        broken.append(link)
    assert not broken, f"Broken relative links in SKILL.md: {broken}"
    assert "references/dviet_19/INDEX.md" in text, "SKILL.md must point to references/dviet_19/INDEX.md"
    assert "23_dviet_profile_decisions_and_backlog.md" in text, "SKILL.md must point to reference 23"
    assert "web_cinema_plate_engine.mjs" in text, "SKILL.md must index web_cinema_plate_engine.mjs"
    assert "--tier studio" in text, "SKILL.md must document --tier studio"
    assert "AUTO:" in text and "--auto-sfx-dir" in text, "SKILL.md must document AUTO: / --auto-sfx-dir"
    assert "04_qa_4pass_inspector" not in text and "build_v14_dviet_smooth_master" not in text, \
        "SKILL.md must not link the broken targets of references 12/13"
    for cli in ("env_status.py", "--profile", "--audio-profile", "tiktok_loud", "--whisper-threads", "--music-only",
                "fc_export.py", "spec_from_plan.py", "silence_cut.py", "speed_media.py", "sfx_auto.py",
                "qa_sync.py", "sfx_shift.py", "broll_from_video.py"):
        assert cli in text, f"SKILL.md does not document {cli}"
    assert not re.search(r"5 (stateless )?(atomic )?tools", text, re.I), "SKILL.md still says '5 tools'"
    readme = _read("README.md")
    for ref in ("30_filmcraft_control_bridge.md", "25_loudness_tiktok_vs_nle.md", "26_dviet_fonts.md", "27_premiere_recipes_to_filmcraft.md"):
        assert f"references/{ref}" in text, f"SKILL.md must link reference {ref}"
        assert f"references/{ref}" in readme, f"README.md must link reference {ref}"
    for tool in ("filmcraft_cli.py", "flicker_schedule.py", "duck_keyframes.py"):
        assert tool in text and tool in readme, f"{tool} must be documented in SKILL.md and README.md"
    assert "`filmcraft-cli`" not in text.split("### Step 0")[1].split("### Step 1")[0], "Step 0 must describe the control-bridge shim, not filmcraft-cli"
    assert "What the director may promise" in text and "Object Mask" in text and "Time Displacement" in text, "SKILL.md needs the A/B/C honesty table"
    print(f"[PASS] SKILL.md links resolve ({skipped} links to P1/P2 files skipped when missing) and CLIs are documented")


def test_04_rule_a1_and_install() -> None:
    skill = _read("SKILL.md")
    assert "fc_export.py" in skill and "Rule A1" in skill
    a1 = [ln for ln in skill.splitlines() if "Rule A1" in ln]
    assert any("only when the user asks" in ln or "draft" in ln for ln in a1), "Rule A1 must say .mp4 only on request or in draft mode"
    inst = _read("install.sh")
    assert "env_status" in inst, "install.sh must run env_status"
    for needle in ("node", "chrome", "ffmpeg"):
        assert needle in inst.lower(), f"install.sh/README must declare {needle}"
    req = _read("requirements.txt")
    for needle in ("node", "chrome", "ffmpeg", "matte"):
        assert needle in req.lower(), f"requirements.txt comments must declare {needle}"
    print("[PASS] Rule A1 and install/requirements declarations")


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

def test_05_presets_load_nfc_and_keys() -> None:
    names = [
        "dviet_style_tokens", "canvas_presets", "atomic_motion_library", "format_modes_catalog",
        "typography_hierarchy_presets", "dviet_pattern_catalog",
    ]
    data = {}
    for n in names:
        data[n] = json.loads((PRESETS / f"{n}.json").read_text(encoding="utf-8"))
        _assert_nfc(data[n], n)

    tok = data["dviet_style_tokens"]
    for k in ("palette", "font_roles", "tiers", "caption_y_pct", "lockup", "constellation", "canvases", "audio", "provenance"):
        assert k in tok, f"dviet_style_tokens.json misses {k}"
    roles = {"caption", "keyword_sans", "script_accent", "number", "header", "cta", "bilingual_sub", "lockup_sub", "lockup_hero", "constellation"}
    assert roles <= set(tok["font_roles"]) and roles <= set(tok["tiers"]), "tokens must define all 10 roles"
    cy = tok["caption_y_pct"]
    assert cy["talking"]["range"] == [52, 58] and cy["panel"]["value"] == 67 and cy["hero"]["value"] == 27
    assert 80 <= cy["bilingual_en"]["value"] <= 85
    assert "tiktok_loud" in tok["audio"] and tok["audio"]["tiktok_loud"]["tp_cap_dbtp"] == -0.5
    assert all(g.get("flag") in ("measured", "estimate") for g in tok["provenance"]["groups"].values())
    assert "Instrument Serif" in tok["font_roles"]["font_specimen"]["allow_banned_fonts"]
    assert tok["font_roles"]["script_accent"]["swash_hybrid"] is True
    assert all(not v["swash_hybrid"] for k, v in tok["font_roles"].items() if k != "script_accent")

    cv = data["canvas_presets"]["canvases"]
    got = {(c["width"], c["height"], c["fps"]) for c in cv.values()}
    assert {(1080, 1920, 60), (1080, 1920, 30), (1440, 1080, 24), (1440, 1080, 30), (1332, 720, 30)} <= got
    assert all("safe_zone" in c for c in cv.values())
    assert "safe_zone_scaling_rule" in data["canvas_presets"]

    atoms = data["atomic_motion_library"]["atomics"]
    for a in NEW_ATOMICS:
        assert a in atoms, f"atomic_motion_library.json misses {a}"
    for a in TRANSITION_ATOMICS:
        assert atoms[a]["profile_scope"] == ["dviet"], f"{a} must be scoped to dviet"
        assert "max_duration" in atoms[a] and "caps" in atoms[a], f"{a} needs max_duration and caps"
    assert atoms["light_leak_overlay"]["rotate_deg"] == 90 and atoms["light_leak_overlay"]["scale_pct"] == 177.8
    assert atoms["light_leak_overlay"]["blend_mode"] == "Add"
    assert atoms["push_130_long"]["duration_s"] == 16

    pv = data["format_modes_catalog"]["profile_vetoes"]
    assert "dviet" in json.dumps(pv) and "profile_scope" in json.dumps(pv)

    th = data["typography_hierarchy_presets"]
    for k in ("caption_y_by_layout_v74", "script_accent_whole_word_v74", "keyword_caps_small_yellow_v74"):
        assert k in th, f"typography_hierarchy_presets.json misses additive key {k}"

    pats = {p["id"] for p in data["dviet_pattern_catalog"]["patterns"]}
    for pid in ("dviet_screen_strip_tutorial", "dviet_card_916_labeled", "dviet_profile_card"):
        assert pid in pats, f"dviet_pattern_catalog.json misses {pid}"
    print(f"[PASS] presets load, NFC, new keys present ({len(NEW_ATOMICS)} atomics)")


def test_06_existing_presets_unchanged() -> None:
    for rel in ("presets/atomic_motion_library.json", "presets/format_modes_catalog.json",
                "presets/typography_hierarchy_presets.json", "presets/dviet_pattern_catalog.json"):
        old = _git_head_json(rel)
        if old is None:
            print(f"[SKIP] no git baseline for {rel}")
            continue
        new = json.loads(_read(rel))

        def check(o, n, path):
            if isinstance(o, dict):
                assert isinstance(n, dict), f"{rel}:{path} changed type"
                for k, v in o.items():
                    assert k in n, f"{rel}:{path}/{k} was removed"
                    check(v, n[k], f"{path}/{k}")
            elif isinstance(o, list) and path.endswith("/patterns"):
                ids_old = [x["id"] for x in o]
                ids_new = [x["id"] for x in n]
                assert ids_old == ids_new[: len(ids_old)], f"{rel}: existing patterns reordered or removed"
                for a, b in zip(o, n):
                    assert a == b, f"{rel}: pattern {a['id']} changed"
            else:
                assert o == n, f"{rel}:{path} value changed ({o!r} -> {n!r})"

        check(old, new, "")
    safe_old = _git_head_json("presets/platform_safe_zones.json")
    if safe_old is not None:
        assert safe_old == json.loads(_read("presets/platform_safe_zones.json")), "platform_safe_zones.json must stay unchanged"
    print("[PASS] existing preset keys and values are unchanged (additive only)")


def test_07_reference_23_content() -> None:
    text = _read("references/23_dviet_profile_decisions_and_backlog.md")
    for needle in ("script_accent", "Instrument Serif", "De Fonte", "visual_archetypes_catalog.json:190", "font_specimen",
                   "sandwiched", "tiktok_loud", "-0.5 dBTP", "--profile dviet",
                   "silhouette flicker", "clean-plate", "planar tracking", "clone", "waveform", "constellation",
                   "pixel stretch", "RGB fringe", "sparkle", "keycap", "slit-scan"):
        assert needle.lower() in text.lower(), f"reference 23 misses {needle!r}"
    assert "04_qa_4pass_inspector" in text and "build_v14_dviet_smooth_master" in text, "reference 23 must list the broken links of refs 12/13"
    assert re.search(r"\|\s*1\s*\|\s*Silhouette flicker\s*\|\s*4", text), "backlog must be ranked with video counts"
    print("[PASS] reference 23 records decisions (a)-(f) and a ranked backlog")


# ---------------------------------------------------------------------------
# Code
# ---------------------------------------------------------------------------

def test_08_dviet_text_uses_token_y() -> None:
    import dviet_text as dt

    tokens = json.loads((PRESETS / "dviet_style_tokens.json").read_text(encoding="utf-8"))
    events = {
        "events": [
            {"role": "caption", "text": "với hiệu ứng này", "at": 1.0, "dur": 1.0, "layout": "talking"},
            {"role": "caption", "text": "bước thứ hai", "at": 2.5, "dur": 1.0, "layout": "panel"},
            {"role": "caption", "text": "hero trên panel", "at": 4.0, "dur": 1.0, "layout": "hero"},
            {"role": "bilingual_sub", "text": "video editing is tiring.", "at": 5.0, "dur": 1.5},
            {"role": "lockup_sub", "text": "mình không", "at": 7.0, "dur": 2.0},
            {"role": "lockup_hero", "text": "nổi tiếng", "at": 7.0, "dur": 0.9},
            {"role": "keyword_sans", "text": "tạo ra", "at": 9.2, "dur": 0.8},
            {"role": "script_accent", "text": "chuyên nghiệp", "at": 10.3, "dur": 1.0},
            {"role": "number", "text": "3", "at": 11.5, "dur": 1.2},
            {"role": "header", "text": "bước một", "at": 13.0, "dur": 2.0},
            {"role": "cta", "text": "Lưu lại", "at": 15.5, "dur": 1.5},
            {"role": "constellation", "text": "Sợ", "satellites": ["chẳng", "mãi thì", "bao"], "at": 18.0, "dur": 2.0},
            {"role": "caption", "text": unicodedata.normalize("NFD", "Nguyễn Đức Việt"), "at": 21.0, "dur": 1.0},
        ]
    }
    out = dt.build_tracks(events, tokens)
    clips = [c for t in out["tracks"] for c in t["clips"]]
    by_text = {c["text"]: c for c in clips}
    cy = tokens["caption_y_pct"]
    assert by_text["với hiệu ứng này"]["y_pct"] == cy["talking"]["value"]
    assert by_text["bước thứ hai"]["y_pct"] == cy["panel"]["value"]
    assert by_text["hero trên panel"]["y_pct"] == cy["hero"]["value"]
    assert by_text["video editing is tiring."]["y_pct"] == cy["bilingual_en"]["value"]
    assert by_text["video editing is tiring."]["italic"] is True
    for c in clips:
        assert c["text"] == unicodedata.normalize("NFC", c["text"]), "clip text must be NFC"
        assert c["size_px"] > 0 and c["entrance"]["name"] in tokens["animations"]
        assert 0 < c["position"][1] < tokens["canvas"]["h"]
    assert any(c["text"] == "Nguyễn Đức Việt" for c in clips), "decomposed input must be NFC-normalized"
    assert by_text["nổi tiếng"]["size_px"] > by_text["mình không"]["size_px"], "lock-up hero must be bigger than the sub line"
    assert by_text["Sợ"]["role"] == "constellation" and sum(1 for c in clips if c["role"] == "constellation_satellite") == 3
    # y overrides and sizes come from tokens
    ev2 = {"events": [{"role": "caption", "text": "x", "at": 0, "dur": 1, "y_pct": 40}]}
    assert dt.build_tracks(ev2, tokens)["tracks"][0]["clips"][0]["y_pct"] == 40
    # unknown role is an error, missing font is only a warning
    try:
        dt.build_tracks({"events": [{"role": "nope", "text": "x", "at": 0, "dur": 1}]}, tokens)
        raise AssertionError("unknown role must raise")
    except ValueError:
        pass
    assert isinstance(out["warnings"], list)
    # banned fonts: rejected for ordinary roles, allowed (ASCII only) for font_specimen under the token
    spec_ok = dt.build_tracks({"events": [{"role": "font_specimen", "text": "Instrument Serif", "font": "Instrument Serif", "at": 0, "dur": 1}]}, tokens)
    assert spec_ok["tracks"][0]["clips"][0]["font"]["family"] == "Instrument Serif"
    for bad in ({"role": "font_specimen", "text": "Cắt cứng", "font": "Instrument Serif", "at": 0, "dur": 1},
                {"role": "font_specimen", "text": "x", "font": "Great Vibes", "at": 0, "dur": 1}):
        try:
            dt.build_tracks({"events": [bad]}, tokens)
            raise AssertionError(f"banned font must be rejected: {bad}")
        except ValueError:
            pass
    # CLI contract
    with tempfile.TemporaryDirectory() as td:
        ev_p, out_p = Path(td) / "events.json", Path(td) / "tracks.json"
        ev_p.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "dviet_text.py"), "--events", str(ev_p),
             "--tokens", str(PRESETS / "dviet_style_tokens.json"), "--out", str(out_p)],
            capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, r.stderr
        written = json.loads(out_p.read_text(encoding="utf-8"))
        assert written["tracks"] and written["profile"] == "dviet"
    print("[PASS] dviet_text: y%, size and entrance come from tokens; NFC; roles; CLI")


def test_09_web_plate_layout_templates_and_no_caps_kicker() -> None:
    import web_plate_builder as wpb

    props = wpb.FEATHER_CLUSTER_SELFTEST_PROPS
    kicker = props.get("kicker", "")
    assert not kicker or not (kicker.upper() == kicker and any(ch.isalpha() for ch in kicker)), \
        f"ALL-CAPS kicker in the feather-cluster self-test sample: {kicker!r}"
    for key in ("main_text", "accent_text"):
        assert props.get(key), key
    assert set(wpb.LAYOUT_TEMPLATES) == {"screen_strip", "card_916", "profile_card"}
    for t in wpb.LAYOUT_TEMPLATES:
        assert t in wpb.TEMPLATE_DEFAULTS and wpb.LAYOUT_TEMPLATE_SLOTS[t], t
    with tempfile.TemporaryDirectory() as td:
        rep = wpb.render_layout_templates_self_test(Path(td))
        assert rep["ok"] is True
        for t in wpb.LAYOUT_TEMPLATES:
            p = Path(rep["pngs"][t]["path"])
            assert p.is_file() and p.stat().st_size > 2000, f"{t} PNG missing"
        # missing font falls back and warns
        html = wpb.build_template_html("profile_card", {"font_family": "Definitely Missing Font 123"})
        assert "Be Vietnam Pro" in html
    print("[PASS] web_plate_builder: 3 layout templates render PNGs, no ALL-CAPS kicker in sample, font fallback")


def test_10_camera_engine_zoom() -> None:
    import dviet_smooth_camera_engine as cam

    # Presets are present and default tracks are untouched
    for name in ("punch_220_q25", "push_130_long", "step_zoom_13_8_9", "jc_reset_push_4_10", "dolly_out_12_16"):
        assert name in cam.ZOOM_PRESETS, name
    assert cam.ZOOM_PRESETS["push_130_long"]["duration_s"] == 16.0
    assert cam.ZOOM_PRESETS["punch_220_q25"]["scale_to"] == 2.2 and cam.ZOOM_PRESETS["punch_220_q25"]["duration_s"] == 0.25
    atoms = json.loads((PRESETS / "atomic_motion_library.json").read_text(encoding="utf-8"))["atomics"]
    for name, spec in cam.ZOOM_PRESETS.items():  # data and engine must agree
        a = atoms[name]
        assert name in a["engine_preset"], name
        if "steps_pct" in spec:
            assert a["steps_pct"] == spec["steps_pct"]
        else:
            assert abs(a["duration_s"] - spec["duration_s"]) < 1e-9, name
            assert abs(a["keyframes"][-1]["scale"] - 100.0 * spec["scale_to"]) < 1e-6, name
    assert set(cam.build_dviet_aroll_rhythm_presets()) == {"seg_02", "seg_03", "seg_05", "seg_07", "seg_08", "seg_11"}

    # Safe-box clamp: head top at y=300 with pivot y=806 limits scale to 806/(806-300)
    s = cam.clamp_scale_to_safe_box(2.2, head_top_y=300.0, pivot_y=806.4, margin_px=0.0)
    assert abs(s - 806.4 / (806.4 - 300.0)) < 1e-6, s
    assert cam.clamp_scale_to_safe_box(1.1, head_top_y=300.0, pivot_y=806.4) == 1.1
    assert cam.clamp_scale_to_safe_box(2.2, head_top_y=None, pivot_y=806.4) == 2.2
    low = cam.clamp_scale_to_safe_box(2.2, head_top_y=None, pivot_y=806.4, source_size=(720, 1280))
    assert abs(low - 720 / 1080) < 1e-6 or low == 1.0, f"source below 1080p must not be upscaled: {low}"
    tr = cam.build_zoom_track("punch_220_q25", t0=0.0, head_top_y=300.0, pivot_y=806.4)
    assert max(k.scale for k in tr.keyframes) <= 806.4 / (806.4 - 300.0) + 1e-6

    # C4 rule: a spoken run >= 4 s gets zoom keys, shorter ones do not
    words = [{"word": "a", "start": 0.0 + 0.3 * i, "end": 0.0 + 0.3 * i + 0.25} for i in range(16)]  # 0..4.75 s continuous
    words += [{"word": "b", "start": 8.0 + 0.3 * i, "end": 8.0 + 0.3 * i + 0.25} for i in range(8)]  # 2.4 s run
    keys = cam.c4_zoom_keys(words)
    assert len(keys) == 1 and keys[0]["preset"] in cam.ZOOM_PRESETS and keys[0]["t0"] < 4.0
    assert cam.c4_zoom_keys(words[16:]) == []

    # Radial blur grows with scale deviation and never touches the centre
    import numpy as np
    p_a = cam.radial_blur_params_for_scale(1.0)
    p_b = cam.radial_blur_params_for_scale(0.85)
    p_c = cam.radial_blur_params_for_scale(1.3)
    assert p_a["max_blur_ksize"] < p_c["max_blur_ksize"] and p_a["max_blur_ksize"] < p_b["max_blur_ksize"]
    assert p_b["inner_r"] < p_a["inner_r"] and p_c["inner_r"] < p_a["inner_r"]
    rng = np.random.default_rng(3)
    img = (rng.random((320, 180, 3)) * 255).astype(np.uint8)
    out = cam.apply_scale_radial_blur(img, 0.85)
    assert np.array_equal(out[150:170, 80:100], img[150:170, 80:100]), "centre must stay razor sharp"
    assert float(np.abs(out[:20].astype(int) - img[:20].astype(int)).mean()) > 5.0, "edges must be blurred at 0.85x"

    # End-to-end measured scale curve on a 5 s synthetic clip (cv2.estimateAffinePartial2D, no face detection)
    rep = cam.run_zoom_self_test()
    assert rep["ok"] is True and rep["clips"], rep
    for clip in rep["clips"]:
        assert clip["max_log_err"] < 0.03, clip
    print("[PASS] camera engine: presets, safe-box clamp, C4 rule, radial blur and measured 5 s scale curve")


def test_11_no_forbidden_strings_in_owned_files() -> None:
    owned = [
        "SKILL.md", "README.md", "install.sh", "requirements.txt",
        "references/dviet_19/INDEX.md", "references/23_dviet_profile_decisions_and_backlog.md",
        "references/24_studio_look_recipe.md", "references/20_v73_hybrid_ab_voicesync_and_hairsafe_compositor.md",
        "presets/studio_scene_recipe.json", "presets/profile_overrides.json", "scripts/tools/studio_recipe.py",
        "presets/dviet_style_tokens.json", "presets/canvas_presets.json", "presets/atomic_motion_library.json",
        "presets/format_modes_catalog.json", "presets/typography_hierarchy_presets.json", "presets/dviet_pattern_catalog.json",
        "scripts/dviet_smooth_camera_engine.py", "scripts/tools/web_plate_builder.py", "scripts/tools/dviet_text.py",
        "tests/test_dviet_docs.py",  # tests/test_skill_v73.py is excluded: it holds the checker literal itself
    ]
    banned = "/home/" + "thanh"
    for rel in owned:
        assert banned not in _read(rel), f"{banned} found in {rel}"
    print("[PASS] no personal absolute paths in owned files")


def test_12_look_s_docs_and_policy() -> None:
    skill, readme, ref24 = _read("SKILL.md"), _read("README.md"), _read("references/24_studio_look_recipe.md")
    assert skill.count("Look S") >= 3 and "Look D" in skill, "SKILL.md must define Look S and Look D"
    front = skill.split("---", 2)[1]
    assert "Full-Head Studio Rounded Cards" in front and "Squircle PiP" in front, "frontmatter must keep the Full-Head Card / Squircle PiP emphasis"
    for needle in ("Step 3b", "studio_recipe.py", "24_studio_look_recipe.md", "--master", "mp4-first", "md5", "--context",
                   "init_hair_safe_wall_reference", "clean_aroll_preserve_hair_crown", "pipe_encode_single_plate_fast",
                   "compose_master_mp4_via_ffmpeg", "skewed_3d_polaroid_trio", "frosted_glass_bento_steps", "isometric_3d_prompt_browser",
                   "kt11", "150-168%", "136%", "1.18x", "studio_14", "only a plain re-encode"):
        assert needle in skill, f"SKILL.md must mention {needle!r}"
    for needle in ("Option A1", "squircle", "MP4 master", ".fcproj", "studio_14", "24_studio_look_recipe.md"):
        assert needle in readme, f"README.md must mention {needle!r}"
    assert readme.index("Option A1") < readme.index("1a. Phiên Bản"), "README must lead with the Option A1/A2/B highlights"
    for needle in ["S01A", "S02", "S12C", "VFX-01", "VFX-08", "11.80", "14.95", "15.08", "A3..A8", "72", "-14.0", "-1.2", "#F5C451",
                   "dviet_19videos_complete_forensics_and_roundtable.md", "v21_hybrid_ab_voicesync_and_github_skill_package.md",
                   "v19_dviet_redirection_vfx_sfx_beatdrop_walkthrough.md"] + [f"{c}" for c in ("1.33", "13.47", "35.78")]:
        assert needle in ref24, f"reference 24 must mention {needle!r}"
    assert "24_studio_look_recipe.md" in _read("references/23_dviet_profile_decisions_and_backlog.md")
    assert "24_studio_look_recipe.md" in _read("references/20_v73_hybrid_ab_voicesync_and_hairsafe_compositor.md")
    assert "Look S" in _read("references/23_dviet_profile_decisions_and_backlog.md")
    pal = json.loads(_read("presets/dviet_style_tokens.json"))["palette"]
    assert pal["accent_policy"] == "tokens" and set(pal["accent_policy_options"]) == {"tokens", "color_world"}
    assert pal["rule"].startswith("Look D only"), "palette.rule must be scoped to Look D"
    assert pal["default_accent"] == "yellow_bright" and pal["accents"]["yellow_bright"] == "#F1C711"
    print("[PASS] Look S / Look D policy, Step 3b, reference 24, README highlights and the scoped accent rule")


if __name__ == "__main__":
    test_01_index_has_all_17_ids()
    test_02_version_labels()
    test_03_skill_md_links_and_pointers()
    test_04_rule_a1_and_install()
    test_05_presets_load_nfc_and_keys()
    test_06_existing_presets_unchanged()
    test_07_reference_23_content()
    test_08_dviet_text_uses_token_y()
    test_09_web_plate_layout_templates_and_no_caps_kicker()
    test_10_camera_engine_zoom()
    test_11_no_forbidden_strings_in_owned_files()
    test_12_look_s_docs_and_policy()
    print(f"TẤT CẢ ĐẠT (dviet docs & presets v{VERSION})")
