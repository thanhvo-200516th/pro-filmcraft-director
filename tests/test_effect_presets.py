#!/usr/bin/env python3
"""
Static validation of the experimental native-effect presets and the vanish / clone-appear macros (v7.4.0, PKG-C).

Presets under test (all `status: experimental`, `behaviour_unverified_in_app: true`):
  presets/typography_hierarchy_presets.json  native_effect_presets_v74.rgb_fringe_text_native
  presets/atomic_motion_library.json         vertical_flip_stack_native, curved_warp_lens_wave_3f,
                                             radial_focus_blur_zoom_out, sparkle_sprite_pop_6f,
                                             vanish_glow_negative_white, clone_appear_flicker (macros)

Static means: no FilmCraft, no project is built or rendered. What is checked
  * every effect / transition id exists in the `effects.list` ids documented in references/27 section 1.2 and, when
    the dump behind it is reachable, its parameter names and choices exist there too;
  * the FilmCraft commands the builders rely on exist in filmcraft-commands.json (that file lists commands, not effect ids);
  * parameters sit inside the ranges the preset declares; key times are integer frames at every project fps;
  * generated rows pass fc_build.validate, compile_and_verify.sanitize_spec (unchanged frames, no key rewritten) and spec_lint.
The only media is synthetic (numpy / ffmpeg testsrc2 <= 2 s in a temp dir).

External files are resolved relative to this skill, with env overrides, and the check is SKIPPED when absent:
  PFD_FILMCRAFT_COMMANDS   path of filmcraft-commands.json
  PFD_EFFECTS_DUMP         markdown that holds the `effects.list` dump (kb-master-video-edit.md of the video skill)

Run: python3 tests/test_effect_presets.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterator

import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
OVS = SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "scripts"
FC_BUILD = OVS / "apps" / "craft-handoff" / "tools" / "fc_build.py"
SPEC_LINT = OVS / "spec_lint.py"
PRESETS = SKILL_ROOT / "presets"
REF27 = SKILL_ROOT / "references" / "27_premiere_recipes_to_filmcraft.md"
for p in (str(TOOLS_DIR), str(SKILL_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import flicker_schedule as fs  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
RATES = [(60, 1), (24, 1), (25, 1), (30, 1), (30000, 1001)]
W, H = 360, 640
# v7.9.1: only paths inside this skill (no sibling-repo fallback); absent -> the check prints [SKIP] with the reason
DEFAULT_COMMANDS = [SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "references" / "filmcraft-commands.json"]
DEFAULT_DUMP = [SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "references" / "kb-master-video-edit.md"]
BUILDER_COMMANDS = ("effects.apply", "effects.setParam", "effects.setKeyframe", "effects.setInterpolation")
NATIVE_PRESETS = {
    "typography_hierarchy_presets.json": ("native_effect_presets_v74", ["rgb_fringe_text_native"]),
    "atomic_motion_library.json": ("atomics", ["vertical_flip_stack_native", "curved_warp_lens_wave_3f",
                                               "radial_focus_blur_zoom_out", "sparkle_sprite_pop_6f"]),
}
MACRO_PRESETS = ("vanish_glow_negative_white", "clone_appear_flicker")


# ----------------------------------------------------------------------------- helpers
def _load(name: str) -> Any:
    return json.loads((PRESETS / name).read_text(encoding="utf-8"))


def _import(path: Path, name: str):
    sp = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(sp)
    assert sp.loader is not None
    sp.loader.exec_module(mod)
    return mod


def _find(env: str, defaults: list[Path]) -> Path | None:
    if os.environ.get(env):
        p = Path(os.environ[env]).expanduser()
        return p if p.is_file() else None
    return next((p for p in defaults if p.is_file()), None)


def _presets() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for fname, (key, names) in NATIVE_PRESETS.items():
        block = _load(fname)[key]
        for n in names:
            assert n in block, f"{fname} misses {n}"
            out[n] = block[n]
    return out


def _ref27_ids() -> tuple[set[str], set[str]]:
    """(video effect ids, transition ids) from the backticked ids of references/27 section 1.2."""
    text = REF27.read_text(encoding="utf-8")
    sec = text.split("### 1.2", 1)[1].split("### 1.3", 1)[0]
    effects: set[str] = set()
    transitions: set[str] = set()
    for line in sec.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        ids = set(re.findall(r"`([a-z][a-z0-9_]*)`", line))
        (transitions if line.startswith("| Chuyển cảnh") else effects).update(ids)
    assert "rgb_split" in effects and "dip_to_white" in transitions, "ref 27 section 1.2 table not parsed"
    return effects, transitions


def _dump_params(path: Path) -> dict[str, dict[str, list[str] | None]]:
    """{effect id: {param: choices | None}} from lines like  - `rgb_split` — RGB Split: mode{Linear|Radial}, amount=10.0"""
    out: dict[str, dict[str, list[str] | None]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- `([a-z][a-z0-9_]*)` — [^:]*(?::\s*(.*))?$", line)
        if not m:
            continue
        params: dict[str, list[str] | None] = {}
        for part in re.findall(r"([a-z][a-z0-9_]*)(\{[^}]*\}|=)", m.group(2) or ""):
            params[part[0]] = part[1][1:-1].split("|") if part[1].startswith("{") else None
        out.setdefault(m.group(1), params)
    return out


def _keylists(obj: Any, where: str = "") -> Iterator[tuple[str, list]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _keylists(v, f"{where}.{k}")
    elif fs._is_keylist(obj):
        yield where, obj
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _keylists(v, f"{where}[{i}]")


def _numbers(value: Any) -> Iterator[Any]:
    """Every scalar a parameter takes: a constant, or the values of its keyframes."""
    if fs._is_keylist(value):
        for k in value:
            yield from _numbers(k[1])
    elif isinstance(value, list):
        for v in value:
            yield from _numbers(v)
    else:
        yield value


def _check_effects(label: str, effects: list[dict], preset: dict, known: set[str], dump: dict | None) -> int:
    ranges, choices = preset.get("param_ranges", {}), preset.get("param_choices", {})
    n = 0
    for fx in effects:
        eid = fx["effect"]
        assert eid in known, f"{label}: effect id {eid!r} is not in the effects.list ids documented in references/27"
        for pname, pval in fx.get("params", {}).items():
            n += 1
            key = f"{eid}.{pname}"
            if dump and eid in dump:
                assert pname in dump[eid], f"{label}: {key} is not a parameter in the effects.list dump {sorted(dump[eid])}"
            for v in _numbers(pval):
                if isinstance(v, str):
                    assert v in choices.get(key, []), f"{label}: {key}={v!r} not in declared choices {choices.get(key)}"
                    if dump and eid in dump and dump[eid].get(pname):
                        assert v in dump[eid][pname], f"{label}: {key}={v!r} not in the dump choices {dump[eid][pname]}"
                else:
                    assert key in ranges, f"{label}: {key} has no declared range"
                    lo, hi = ranges[key]
                    assert lo <= v <= hi, f"{label}: {key}={v} outside declared [{lo}, {hi}]"
    return n


def _check_fields(label: str, fields: dict, num: int, den: int, dur_frames: int) -> None:
    """Key times must be integer frames at the project rate, strictly increasing, inside the clip."""
    rate = num / den
    for where, keys in _keylists(fields):
        ts = [k[0] for k in keys]
        frames = [round(t * rate) for t in ts]
        assert all(abs(t * rate - f) < 1e-3 and isinstance(f, int) for t, f in zip(ts, frames)), f"{label}{where} {ts} not on frames @{num}/{den}"
        assert all(b > a for a, b in zip(ts, ts[1:])), f"{label}{where} keys not increasing {ts}"
        assert all(0 <= f <= dur_frames for f in frames), f"{label}{where} key past the clip ({frames} > {dur_frames})"
        assert all((len(k) == 2 or k[2] in ("linear", "bezier", "easeIn", "easeOut", "hold")) for k in keys), f"{label}{where} bad interpolation"


def _ff(*args: Any) -> None:
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", *map(str, args)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def _make_media(td: Path) -> dict[str, str]:
    _ff("-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=60:d=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", td / "subject.mp4")
    _ff("-f", "lavfi", "-i", f"color=c=0x303030:s={W}x{H}:d=0.1", "-frames:v", "1", td / "plate.png")
    _ff("-f", "lavfi", "-i", "color=c=0xFFFFFF:s=64x64:d=0.1", "-frames:v", "1", td / "sprite.png")
    return {k: str(td / v) for k, v in (("video", "subject.mp4"), ("plate", "plate.png"), ("sprite", "sprite.png"))}


def _spec(num: int, den: int, dur_s: float, tracks: list[dict]) -> dict:
    return {"name": "effect_presets", "width": W, "height": H, "fps": fs.spec_fps(num, den), "duration": dur_s, "tracks": tracks}


def _preset_spec(name: str, preset: dict, media: dict[str, str], num: int, den: int, start_frame: int = 0) -> tuple[dict, int]:
    clips = fs.preset_clips(preset, num, den, start_frame)
    dur_f = fs.preset_duration_frames(preset, num, den) + start_frame
    dur = fs.frame_time(dur_f, num, den)
    tracks = []
    for role, fields in clips.items():
        if role == "text":
            clip = {"name": f"{name} {role}", "text": "Việt", "at": 0.0, "dur": dur, **fields}
            tracks.append({"type": "text", "name": f"T · {role}", "clips": [clip]})
        else:
            src = media["sprite"] if role == "sprite" else media["video"]
            clip = {"name": f"{name} {role}", "src": src, "at": 0.0, "dur": dur, **fields}
            tracks.append({"type": "video", "name": f"V · {role}", "clips": [clip]})
    return _spec(num, den, dur, tracks), dur_f


# ----------------------------------------------------------------------------- 1. ids, commands, flags
def test_01_effect_ids_commands_and_labels() -> None:
    known, transitions = _ref27_ids()
    dump_path = _find("PFD_EFFECTS_DUMP", DEFAULT_DUMP)
    dump = _dump_params(dump_path) if dump_path else None
    if dump is not None:
        assert "rgb_split" in dump and dump["rgb_split"]["mode"] == ["Linear", "Radial"], "effects.list dump not parsed"
    else:
        print(f"[SKIP] effects.list dump not found (not vendored at {DEFAULT_DUMP[0].relative_to(SKILL_ROOT)}; set PFD_EFFECTS_DUMP): "
              "parameter names are checked against references/27 only")
    cmd_path = _find("PFD_FILMCRAFT_COMMANDS", DEFAULT_COMMANDS)
    if cmd_path is None:
        print(f"[SKIP] filmcraft-commands.json not found (not vendored at {DEFAULT_COMMANDS[0].relative_to(SKILL_ROOT)}; "
              "set PFD_FILMCRAFT_COMMANDS): builder command ids are not checked")
    else:
        ids = {c["id"] for c in json.loads(cmd_path.read_text(encoding="utf-8"))}
        missing = [c for c in BUILDER_COMMANDS if c not in ids]
        assert not missing, f"filmcraft-commands.json lacks builder commands {missing}"

    seen = 0
    for name, preset in _presets().items():
        assert preset["status"] == "experimental" and preset["behaviour_unverified_in_app"] is True, name
        assert preset["native_preset"] is True and preset["ref"].startswith("references/27_"), name
        clips = preset["clips"]
        assert len({c["role"] for c in clips}) == len(clips), f"{name}: duplicate role"
        for c in clips:
            seen += _check_effects(f"{name}/{c['role']}", c["fields"].get("effects", []), preset, known, dump)
            for tkey in ("transition_in", "transition_out"):
                if tkey in c["fields"]:
                    assert c["fields"][tkey]["effect"] in transitions, f"{name}: transition {c['fields'][tkey]['effect']}"
    for name in MACRO_PRESETS:
        p = _load("atomic_motion_library.json")["atomics"][name]
        assert p["status"] == "experimental" and p["behaviour_unverified_in_app"] is True and p["macro"].startswith("scripts/tools/flicker_schedule.py"), name
    op = _load("atomic_motion_library.json")["atomics"]["flicker_silhouette_opener_8f"]
    assert op["status"] == "experimental" and op["behaviour_unverified_in_app"] is True
    assert [tuple(s) for s in op["states"]] == list(fs.DEFAULT_OPENER_STATES) and op["duration_frames"] == 8 and op["silhouette_hex"] == "#" + fs.SILHOUETTE_HEX
    assert _load("atomic_motion_library.json")["atomics"]["radial_blur_scale_grow"]["effect"] == "radial_blur"
    assert _presets()["radial_focus_blur_zoom_out"]["reference_atomic"] == "radial_blur_scale_grow"
    tp = _load("typography_hierarchy_presets.json")
    assert _presets()["rgb_fringe_text_native"]["extends"] in tp["entrance_recipes"], "rgb fringe must extend the existing glitch_rgb_split"
    assert "glitch_rgb_split" in tp["entrance_recipes"]
    print(f"[PASS] 01 effect/transition ids documented, {seen} parameters in declared ranges/choices, experimental + unverified labels")


# ----------------------------------------------------------------------------- 2. frames at every fps
def test_02_frame_counts_are_integers_at_every_fps() -> None:
    fcb = _import(FC_BUILD, "pfd_fc_build_presets")
    for name, preset in _presets().items():
        for num, den in RATES:
            rate = fcb.fps_fraction(fs.spec_fps(num, den))
            assert rate.numerator * den == num * rate.denominator
            clips = fs.preset_clips(preset, num, den)
            dur_f = fs.preset_duration_frames(preset, num, den)
            assert isinstance(dur_f, int) and dur_f >= 1
            for role, fields in clips.items():
                _check_fields(f"{name}/{role}@{num}/{den}", fields, num, den, dur_f)
                for _, keys in _keylists(fields):
                    assert all(fcb.to_frames(k[0], rate) == round(k[0] * num / den) for k in keys)
        if preset.get("returns_to_rest"):
            shifted = fs.preset_clips(preset, 60, 1, start_frame=7)
            for role, fields in shifted.items():
                for where, keys in _keylists(fields):
                    assert keys[0][0] == 0.0 and keys[0][2] == "hold" and keys[0][1] == keys[-1][1], (name, where)
                    assert keys[1][0] == fs.key_time(7, 60, 1), (name, where)
                _check_fields(f"{name}/{role}+7", fields, 60, 1, fs.preset_duration_frames(preset, 60, 1) + 7)
        else:
            _raises(fs.FlickerError, fs.preset_clips, preset, 60, 1, 3, needle="returns_to_rest")
    # non-integer frame keys are refused, colliding seconds keys are refused
    bad = copy.deepcopy(_presets()["rgb_fringe_text_native"])
    bad["clips"][0]["fields"]["effects"][0]["params"]["amount"][1][0] = 1.5
    _raises(fs.FlickerError, fs.preset_clips, bad, 60, 1, needle="integers")
    tight = {"keys_unit": "seconds", "clips": [{"role": "c", "fields": {"opacity": [[0, 0.0], [0.01, 100.0]]}}]}
    _raises(fs.FlickerError, fs.preset_clips, tight, 24, 1, needle="collide")
    before = json.dumps(_presets()["sparkle_sprite_pop_6f"], sort_keys=True)
    fs.preset_clips(_presets()["sparkle_sprite_pop_6f"], 25, 1)
    assert json.dumps(_presets()["sparkle_sprite_pop_6f"], sort_keys=True) == before
    print(f"[PASS] 02 every preset keeps integer frame keys at {RATES}; start_frame shift, non-integer and colliding keys refused")


def _raises(exc: type[BaseException], fn, *a, needle: str = "", **kw) -> None:
    try:
        fn(*a, **kw)
    except exc as e:
        assert needle.lower() in str(e).lower(), f"error {e!r} lacks {needle!r}"
        return
    raise AssertionError(f"{getattr(fn, '__name__', fn)} did not raise {exc.__name__}")


# ----------------------------------------------------------------------------- 3. fc_build / sanitize / spec_lint
def _assert_pipeline_accepts(label: str, spec: dict, td: Path, cv, lint, fcb) -> None:
    fcb.validate(spec)
    src_clips = [c for t in spec["tracks"] for c in t["clips"]]
    sanitized, stats = cv.sanitize_spec(copy.deepcopy(spec), spec_dir=td, work_dir=td, enable_c8_guard=False)
    assert stats["same_track_trimmed_clips"] == [] and stats["eof_clamped_clips"] == [], (label, stats["same_track_trimmed_clips"], stats["eof_clamped_clips"])
    assert stats["sanitized_keyframe_lists"] == 0, f"{label}: sanitize_spec had to rewrite {stats['sanitized_keyframe_lists']} keyframe list(s)"
    out_clips = [c for t in sanitized["tracks"] for c in t["clips"]]
    rate = fcb.fps_fraction(spec["fps"])
    assert len(out_clips) == len(src_clips), label
    for a, b in zip(src_clips, out_clips):
        assert fcb.to_frames(a["at"], rate) == fcb.to_frames(b["at"], rate), (label, a["name"])
        assert fcb.to_frames(a["dur"], rate) == fcb.to_frames(b["dur"], rate), (label, a["name"])
        assert a.get("effects") == b.get("effects"), (label, a["name"], "effects changed by sanitize_spec")
    fcb.validate(sanitized)
    path = td / f"{label}.craft.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    hard = [r for r in lint.lint(path) if r["status"] == "HARD"]
    assert not hard, f"{label}: spec_lint HARD {hard}"


def test_03_generated_rows_pass_fc_build_sanitize_and_spec_lint() -> None:
    import compile_and_verify as cv  # noqa: PLC0415

    fcb, lint = _import(FC_BUILD, "pfd_fc_build_presets2"), _import(SPEC_LINT, "pfd_spec_lint_presets")
    with tempfile.TemporaryDirectory(prefix="pfd_effpre_") as td:
        td_p = Path(td)
        media = _make_media(td_p)
        for name, preset in _presets().items():
            for num, den in ((60, 1), (30000, 1001)):
                spec, _ = _preset_spec(name, preset, media, num, den)
                _assert_pipeline_accepts(f"{name}_{num}_{den}", spec, td_p, cv, lint, fcb)
            if preset.get("returns_to_rest"):
                spec, _ = _preset_spec(name, preset, media, 60, 1, start_frame=7)
                _assert_pipeline_accepts(f"{name}_shift", spec, td_p, cv, lint, fcb)
        # the flicker opener rows themselves
        sil = td_p / "sil.mov"
        _ff("-f", "lavfi", "-i", f"color=c=0xFFFBF0:s={W}x{H}:r=60:d=1", "-c:v", "qtrle", sil)
        for num, den in RATES:
            rows = fs.flicker_schedule(num, den)
            clips = fs.schedule_to_clips(rows, {"plate": media["plate"], "silhouette": str(sil), "subject": None})
            spec = _spec(num, den, 1.0, [{"type": "video", "name": "V1 · A-roll", "clips": [{"name": "A-roll", "src": media["video"], "at": 0.0, "dur": 1.0, "audio": False}]},
                                       {"type": "video", "name": "V2 · Opener (flicker)", "clips": clips}])
            _assert_pipeline_accepts(f"opener_{num}_{den}", spec, td_p, cv, lint, fcb)
    print("[PASS] 03 preset rows, shifted rows and the flicker opener pass fc_build.validate, sanitize_spec (frames and keys unchanged) and spec_lint (no HARD)")


# ----------------------------------------------------------------------------- 4. macros
def _centre_luma(args: list[str], cx: int, cy: int) -> list[int]:
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-nostdin", *args, "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()[-600:]
    fr = np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W)
    return [int(f[cy, cx]) for f in fr]


def test_04_vanish_macro_frames_and_effects() -> None:
    fcb = _import(FC_BUILD, "pfd_fc_build_vanish")
    preset = _load("atomic_motion_library.json")["atomics"]["vanish_glow_negative_white"]
    known, transitions = _ref27_ids()
    d = preset["defaults"]
    with tempfile.TemporaryDirectory(prefix="pfd_vanish_") as td:
        media = _make_media(Path(td))
        for num, den in RATES:
            rate = fcb.fps_fraction(fs.spec_fps(num, den))
            out = fs.vanish_rows(media["video"], 0.25, 1.75, media["plate"], num, den, at_s=0.1)
            assert set(out) == {"plate", "subject", "frames"}
            (subj,), (plate,) = out["subject"], out["plate"]
            fr = out["frames"]
            dur_f = fcb.to_frames(subj["dur"], rate)
            assert fr["dur"] == dur_f and fcb.to_frames(subj["at"], rate) == fr["at"] == fcb.to_frames(0.1, rate)
            assert fr["glow_start"] == dur_f - d["glow_frames"] - d["negative_frames"] and fr["negative_start"] == dur_f - d["negative_frames"]
            glow, inv = subj["effects"]
            gk, ik = glow["params"]["intensity"], inv["params"]["blend"]
            assert [fcb.to_frames(k[0], rate) for k in gk] == [0, fr["glow_start"], fr["negative_start"]]
            assert [k[1] for k in gk] == [0.0, 0.0, d["glow_peak"]]
            assert [fcb.to_frames(k[0], rate) for k in ik] == [0, fr["negative_start"]] and [k[1] for k in ik] == [0.0, 100.0] and ik[0][2] == "hold"
            tout = subj["transition_out"]
            assert tout["effect"] == d["exit_effect"] and tout["effect"] in transitions
            assert tout["frames"] == max(1, int(d["exit_s"] * num / den + 0.5 + 1e-9)) == fr["exit_frames"]
            assert fcb.to_frames(plate["at"], rate) == fr["at"] and fcb.to_frames(plate["dur"], rate) == dur_f + tout["frames"], "plate must outlast the vanish by the white tail"
            _check_effects(f"vanish@{num}/{den}", subj["effects"], preset, known, None)
            _check_fields("vanish", {"effects": subj["effects"]}, num, den, dur_f)
            spec = _spec(num, den, 2.0, [{"type": "video", "name": "V1 · plate", "clips": out["plate"]}, {"type": "video", "name": "V2 · subject", "clips": out["subject"]}])
            fcb.validate(spec)
        # the negative frames land on exactly the frames the key says (60 fps synthetic clip, ffmpeg negate)
        out = fs.vanish_rows(media["video"], 0.0, 1.0, media["plate"], 60, 1)
        nf = out["frames"]["negative_start"]
        plain = _centre_luma(["-i", media["video"], "-frames:v", "60"], W // 2 + 12, H // 2)
        neg = _centre_luma(["-i", media["video"], "-vf", f"negate=enable='gte(n,{nf})'", "-frames:v", "60"], W // 2 + 12, H // 2)
        assert neg[:nf] == plain[:nf] and all(a != b for a, b in zip(neg[nf:], plain[nf:])), (nf, neg[nf - 1: nf + 2], plain[nf - 1: nf + 2])
        # errors
        _raises(fs.FlickerError, fs.vanish_rows, media["video"], 0.0, 0.1, media["plate"], 60, 1, needle="too short")
        _raises(fs.FlickerError, fs.vanish_rows, media["video"], 1.0, 0.5, media["plate"], 60, 1, needle="in < out")
        _raises(fs.FlickerError, fs.vanish_rows, media["video"], 0.0, 1.0, media["plate"], 60, 1, exit_effect="film_burn", needle="exit_effect")
        _raises(fs.FlickerError, fs.vanish_rows, media["video"], 0.0, 1.0, media["plate"], 60, 1, glow_frames=0, needle="glow_frames")
    assert preset["profile_scope"] == ["dviet"] and "caps" in preset
    print("[PASS] 04 vanish: glow/negative/white keys on the exact frames at every fps, plate outlasts the tail, errors raise")


def test_05_clone_appear_macro_frames() -> None:
    fcb = _import(FC_BUILD, "pfd_fc_build_clone")
    preset = _load("atomic_motion_library.json")["atomics"]["clone_appear_flicker"]
    assert [tuple(s) for s in preset["defaults"]["appear_states"]] == [("off", 2), ("on", 2), ("off", 2)]
    with tempfile.TemporaryDirectory(prefix="pfd_clone_") as td:
        media = _make_media(Path(td))
        for num, den in RATES:
            rate = fcb.fps_fraction(fs.spec_fps(num, den))
            fpsf = num / den
            out = fs.clone_appear_rows(media["video"], 0.5, 1.9, media["plate"], num, den, at_s=0.0, clone_at_s=0.5, offset_s=0.4)
            fr = out["frames"]
            at_f, end_f = 0, fcb.to_frames(1.4, rate)
            assert fr["end"] == end_f and fr["clone_start"] == fcb.to_frames(0.5, rate) and fr["steady_on"] == fr["clone_start"] + 6
            on = out["clone"]
            assert [fcb.to_frames(c["at"], rate) for c in on] == [fr["clone_start"] + 2, fr["steady_on"]]
            assert [fcb.to_frames(c["dur"], rate) for c in on] == [2, end_f - fr["steady_on"]]
            for c in on:  # the duplicate plays continuously, offset_s behind the original, even across the off gap
                expect_in = 0.5 + fcb.to_frames(c["at"], rate) / fpsf - 0.4
                assert abs(c["in"] - expect_in) < 1e-6, (c, expect_in)
            spec = _spec(num, den, 1.5, [{"type": t, "name": f"V{i} · {k}", "clips": out[k]} for i, (t, k) in enumerate((("video", "plate"), ("video", "subject"), ("video", "clone")), 1)])
            fcb.validate(spec)  # three tracks, no overlap inside any of them
        # frame positions on the synthetic harness (60 fps): cream overlay stands in for the clone clip
        out = fs.clone_appear_rows(media["video"], 0.0, 1.0, media["plate"], 60, 1, clone_at_s=0.2, offset_s=0.1)
        rows = fs.flicker_schedule(60, 1, [("off", 2), ("on", 2), ("off", 2), ("on", 60 - 12 - 6)], start_frame=12)
        expr = fs.overlay_enable_expr(rows, "on")
        base = ["-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=60:d=1", "-f", "lavfi", "-i", f"color=c=0xFFFBF0:s={W}x{H}:r=60:d=1"]
        got = _centre_luma([*base, "-filter_complex", f"[0:v][1:v]overlay=enable='{expr}'", "-frames:v", "60"], W // 2 + 12, H // 2)
        p = got[0]
        want = [p] * 14 + [252] * 2 + [p] * 2 + [252] * (60 - 18)
        assert got == want and out["frames"]["clone_start"] == 12, (got[10:24], want[10:24])
        assert [fcb.to_frames(c["at"], fcb.fps_fraction(60.0)) for c in out["clone"]] == [14, 18]
        _raises(fs.FlickerError, fs.clone_appear_rows, media["video"], 0.0, 1.0, media["plate"], 60, 1, clone_at_s=0.2, offset_s=0, needle="offset_s")
        _raises(fs.FlickerError, fs.clone_appear_rows, media["video"], 0.0, 1.0, media["plate"], 60, 1, clone_at_s=0.2, offset_s=0.5, needle="before 0")
        _raises(fs.FlickerError, fs.clone_appear_rows, media["video"], 0.0, 1.0, media["plate"], 60, 1, clone_at_s=0.95, offset_s=0.1, needle="room")
        _raises(fs.FlickerError, fs.clone_appear_rows, media["video"], 0.5, 1.0, media["plate"], 60, 1, at_s=0.5, clone_at_s=0.2, offset_s=0.1, needle="inside")
        states = [["off", 2], ["on", 2]]
        before = json.dumps(states)
        fs.clone_appear_rows(media["video"], 0.0, 1.0, media["plate"], 60, 1, clone_at_s=0.2, offset_s=0.1, appear_states=states)
        assert json.dumps(states) == before
    print("[PASS] 05 clone-appear: 2-frame flicker rows on the exact frames at every fps, continuous offset playback, errors raise")


# ----------------------------------------------------------------------------- 5. docs reflect what shipped
def test_06_docs_state_what_shipped() -> None:
    ref27 = REF27.read_text(encoding="utf-8")
    ref23 = (SKILL_ROOT / "references" / "23_dviet_profile_decisions_and_backlog.md").read_text(encoding="utf-8")
    assert "## 8." in ref27 and "implemented" in ref27 and "experimental" in ref27 and "backlog" in ref27
    sec = ref27.split("## 8.", 1)[1]
    for name in [*NATIVE_PRESETS["atomic_motion_library.json"][1], *NATIVE_PRESETS["typography_hierarchy_presets.json"][1],
                 *MACRO_PRESETS, "flicker_silhouette_opener_8f", "flicker_schedule.py", "spec_from_plan"]:
        assert name in sec, f"references/27 section 8 does not mention {name}"
    for c_class in ("Time Displacement", "Object Mask", "planar", "extrude"):
        assert c_class.lower() in sec.lower(), f"section 8 must keep the C-class refusal for {c_class}"
    assert "behaviour_unverified_in_app" in sec
    assert re.search(r"\|\s*1\s*\|\s*Silhouette flicker\s*\|\s*4", ref23), "ref 23 ranking prefix must stay"
    assert "Trạng thái v7.4" in ref23
    for needle in ("flicker_schedule.py", "experimental", "implemented", "backlog"):
        assert needle in ref23, f"references/23 backlog lacks {needle!r}"
    for rel in ("references/27_premiere_recipes_to_filmcraft.md", "references/23_dviet_profile_decisions_and_backlog.md",
                "presets/atomic_motion_library.json", "presets/typography_hierarchy_presets.json", "tests/test_effect_presets.py"):
        raw = (SKILL_ROOT / rel).read_text(encoding="utf-8")
        assert unicodedata.normalize("NFC", raw) == raw, f"{rel} is not NFC"
        for bad in ("/home/" + "vmiz", "/home/" + "thanh"):
            assert bad not in raw, f"{bad} in {rel}"
    print("[PASS] 06 references 27 (section 8) and 23 state implemented / experimental / backlog per effect, NFC, no host paths")


if __name__ == "__main__":
    test_01_effect_ids_commands_and_labels()
    test_02_frame_counts_are_integers_at_every_fps()
    test_03_generated_rows_pass_fc_build_sanitize_and_spec_lint()
    test_04_vanish_macro_frames_and_effects()
    test_05_clone_appear_macro_frames()
    test_06_docs_state_what_shipped()
    print("TẤT CẢ ĐẠT (effect presets PKG-C)")
