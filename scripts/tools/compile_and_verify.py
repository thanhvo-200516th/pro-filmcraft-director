#!/usr/bin/env python3
"""
compile_and_verify.py (v7.9.0) — Dual-Tier Stateless FilmCraft (.craft.json -> .fcproj) Compiler,
4-Cut Grammar & Bimodal C7 Adjudicator, Color-World Polarity, Spatial Density & 8-Gate Verifier.

v7.4.0: gate dependencies are vendored in `scripts/vendor/ovs_core/` (override: env `PFD_OVS_DIR`); `--profile {default,dviet}`
and `--audio-profile {platform,studio_14,tiktok_loud}` (the choices are read from `presets/profile_overrides.json`; `studio_14` = Look S, -14 LUFS / -1.2 dBTP, v7.7.0); a missing `filmcraft` binary or X server skips the
1-frame render smoke (`scripts/tools/filmcraft_cli.py`) with a loud warning instead of crashing; offline media FAILS it. Never exports `.mp4` (use `fc_export.py` on request).

100% aesthetic-agnostic, stateless mechanical compiler for ANY creative `.craft.json` spec
designed by the Director Agent (standalone project OR portable `bs/` bundle), with configurable
execution tiers (`--tier auto | fast | full`).

Execution Tiers:
  - `fast` (P0 Express Core Physics + v6.0 Era-2 Director Telemetry):
      Gate 1: Mechanical Pre-Flight Sanitizer + `meta.bgm_stops` Silence Vacuum Carver (`>=0.50s` `-inf dB`
              vacuum + `35ms` pre-stop fade-out & beat-aligned re-entry) + Optional `+2.2 dB @ 185Hz` Vocal
              Chest Warmth + Acoustic `lag_ms` (`5ms env5`) Peak-on-Cut Aligner + MD5 SFX Deduplication
              + Speech Micro-Fade Auto-Polisher (`fade_in >= 0.018s`, `fade_out >= 0.022s` when unbridged)
      Gate 2: Pre-Build Spec Lint (`spec_lint.py` -> 0 HARD errors) + `— Fix:` diagnostics
      Gate 3: Editorial Rules Audit (`edit_rules.py` + `v6.0` 4-Cut Grammar & Bimodal `C7` Adjudicator) + `v6.0` Audits:
              1) `audit_chromatic_diversity` (`color_world_polarity` 1–2 Hue World + Polarity Flips vs `RAINBOW_HUE_SOUP`;
                 opt-in `multi_hue_6` legacy mode),
              2) `audit_transition_and_rhythm_continuity` (`clean_hard_cut_pct` 40–75%, `true_vocal_jcut_count`
                 `[-850ms..-140ms]`, `OVER_TRANSITIONED_SPAM` `>45%`, `WHOOSH_OVERLOAD` `>6/min`, `bgm_silence_stops_count`),
              3) `audit_secondary_text_groups` (`100ms` spatial sampler: `MAX_ZONES <= 2` / `3` w/ `<=30pt` whisper G2,
                 `CARD_TEXT_COLLISION`, `FRAME_CLUTTER_OVERLOAD`, `clean_breathing_frame_pct`, `lowercase_hero_pct`)
      Gate 4: Fast FilmCraft Compilation & Structural Parity (`fc_build_fast.py` -> `mismatches == {}`)
      Gate 5: Single-Session Post-FX & Visual QA (`fc_fast_qa.py` -> Color Matte feather upgrade,
              Master `hard_limiter`, 16 hero-peak QA frames, `4x4` `1440x2560` contact sheet)
      Gate 6: Closed-Loop EBU R128 Audio Mastering (`audio_levels.py` plan + pre-trim + stems + check;
              fast audio-only re-trim if `|measured_lufs - target_lufs| > 0.45 LU`).
              NOTE: the loop only converges on REAL SPEECH (tone / music-only / silent fixtures cannot be gain-matched
              to the LUFS target and will report Gate 6 FAIL or non-converged by design). `--audio-profile studio_14`
              (-14 LUFS, <= -1.2 dBTP, ducking ON, Look S) or `tiktok_loud` (-12 LUFS, <= -1.0 dBTP, no ducking, BGM 14 dB under voice;
              the numbers live in presets/profile_overrides.json and `--help` prints them from there)
              overrides the ovs -16 LUFS rule.
      Gate 7: SFX Integrity (`audit_sfx.py`) + Ruling `R217` Normalized Cross-Correlation (`match_at`)
              SFX Sync Audit + Optional Portable Relative Bundle Mode (`--portable-root`)
      Gate 8: Epistemic `claim_gate` (`R200`) + Tri-State Verdict + `compile_report.json` + Vietnamese `EDITOR-REPORT.md`

  - `full` (P0 + P1 + P2 Studio Proof):
      Everything in `fast`, PLUS:
      - Gate 1/6: Automatic `16kHz` BGM Steady-State Offset Selector (`LRA <= 5.5 LU`)
      - Gate 3:   Strict `v6.0` Color-World, Clutter & Cut-Grammar Concern Elevation
      - Gate 5:   Blank Render Guard (`grayscale_std >= 10.0` across all 16 QA frames),
                  Parallel `270x480` Frozen Video B-Roll Detector (`mean(|f2 - f1|) >= 0.8`),
                  Projected `facesafe` Eye/Mouth & Safe-Zone (`50..1030 x 140..1760`) True Glyph Ink
                  Audit (`PIL.ImageFont.getbbox`, Ruling `R26` no-glow, Ruling `R208` `<1.5s` hook exempt)
      - Gate 6:   Ruling `R35` In-Memory Post-AAC (`192k`) `4x` True-Peak Guard (`<= -1.5 dBTP`,
                  auto-stepping Master `hard_limiter` ceiling down on overshoot)
"""
from __future__ import annotations

import argparse
import colorsys
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

def _venv_root_from_env() -> Path | None:
    """Venv root named by `FILMCRAFT_VENV_PYTHON` (a python binary) or `PFD_VENV` (a venv dir or python binary)."""
    for key in ("FILMCRAFT_VENV_PYTHON", "PFD_VENV"):
        raw = os.environ.get(key)
        if raw:
            p = Path(raw).expanduser()
            return p.parent.parent if p.is_file() else p
    return None


# Env first; an already-active venv needs nothing; the legacy ~/.venvs path is only the last fallback.
_VENV_ROOT = _venv_root_from_env() or (None if sys.prefix != sys.base_prefix else Path.home() / ".venvs/video-skills")
_VENV_SITE = _VENV_ROOT / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages" if _VENV_ROOT else None
if _VENV_SITE is not None and _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import correlate

COMPILER_VERSION = "7.9.0"
TICKS_PER_SECOND = 254_016_000_000
SR = 48000
ENV5_WIN = 240  # 5.0 ms boxcar window at 48 kHz (matches thlib/sfxlib.py::_ENV5_WIN)

V71_KINETIC_TEMPLATE_SILHOUETTES: dict[str, str] = {
    "kt01_kiss_editorial_2line": "SIL_KISS_2L",
    "kt01": "SIL_KISS_2L",
    "kt02_feather_swash_overlap": "SIL_FEATHER_SWASH",
    "kt02": "SIL_FEATHER_SWASH",
    "dviet_overlapping_feather_cluster": "SIL_FEATHER_SWASH",
    "kt03_per_word_nonlinear_bloom": "SIL_WORD_STAGGER",
    "kt03": "SIL_WORD_STAGGER",
    "kt04_ghost_to_focus_stack": "SIL_GHOST_STACK",
    "kt04": "SIL_GHOST_STACK",
    "kt05_wall_spatial_counterpoint": "SIL_WALL_HOP",
    "kt05": "SIL_WALL_HOP",
    "kt06_bridge_anchor_live_swap": "SIL_BRIDGE_SWAP",
    "kt06": "SIL_BRIDGE_SWAP",
    "kt07_telescoping_char_rollout": "SIL_CHAR_ACCORDION",
    "kt07": "SIL_CHAR_ACCORDION",
    "kt08_mist_evaporation_reveal": "SIL_MIST_GRADIENT",
    "kt08": "SIL_MIST_GRADIENT",
    "kt09_strike_myth_laser_2phase": "SIL_MYTH_STRIKE",
    "kt09": "SIL_MYTH_STRIKE",
    "kt10_cursor_bars_pillar_gate": "SIL_CURSOR_HUD",
    "kt10": "SIL_CURSOR_HUD",
    "kt11_cranial_svg_arc_or_tilt": "SIL_TILT_OR_ARC",
    "kt11": "SIL_TILT_OR_ARC",
    "kt12_whisper_or_directional_echo": "SIL_WHISPER_ECHO",
    "kt12": "SIL_WHISPER_ECHO",
}

V71_KINETIC_TEMPLATE_ENTRANCES: dict[str, str] = {
    "kt01_kiss_editorial_2line": "player3_air_cushion_kiss_20f",
    "kt01": "player3_air_cushion_kiss_20f",
    "kt02_feather_swash_overlap": "feather29_swash_bloom_22f",
    "kt02": "feather29_swash_bloom_22f",
    "kt03_per_word_nonlinear_bloom": "nonlinear_word_stagger_18f",
    "kt03": "nonlinear_word_stagger_18f",
    "kt04_ghost_to_focus_stack": "ghost_recede_focus_stack_24f",
    "kt04": "ghost_recede_focus_stack_24f",
    "kt05_wall_spatial_counterpoint": "spatial_wall_hop_14f",
    "kt05": "spatial_wall_hop_14f",
    "kt06_bridge_anchor_live_swap": "anchor_hold_slot_swap_16f",
    "kt06": "anchor_hold_slot_swap_16f",
    "kt07_telescoping_char_rollout": "telescoping_tracking_rollout_18f",
    "kt07": "telescoping_tracking_rollout_18f",
    "kt08_mist_evaporation_reveal": "mist_blur_evaporation_22f",
    "kt08": "mist_blur_evaporation_22f",
    "kt09_strike_myth_laser_2phase": "laser_strike_2phase_flip_20f",
    "kt09": "laser_strike_2phase_flip_20f",
    "kt10_cursor_bars_pillar_gate": "cursor_pillar_gate_wipe_16f",
    "kt10": "cursor_pillar_gate_wipe_16f",
    "kt11_cranial_svg_arc_or_tilt": "svg_arc_tangent_glide_20f",
    "kt11": "svg_arc_tangent_glide_20f",
    "kt12_whisper_or_directional_echo": "whisper_directional_echo_12f",
    "kt12": "whisper_directional_echo_12f",
}

_HERO_PNG_STAMP_RE = re.compile(r"(?:^|/|\\)c\d{2}(?:_[a-z0-9_\-]+)?\.png$", re.IGNORECASE)


def _load_sidecar_typo_meta(src_str: str | None, spec_dir: Path | None = None) -> dict[str, Any] | None:
    """Auto-load `<src>.typo_meta.json` or `Path(src).with_suffix('.mov.typo_meta.json')` if present on disk."""
    if not src_str:
        return None
    raw_p = Path(str(src_str))
    base_paths = [raw_p]
    if spec_dir is not None and not raw_p.is_absolute():
        base_paths.append((spec_dir / raw_p).resolve())
    for bp in base_paths:
        candidates = [
            Path(str(bp) + ".typo_meta.json"),
            bp.with_suffix(".mov.typo_meta.json"),
            bp.with_suffix(".typo_meta.json"),
        ]
        for cand in candidates:
            if cand.is_file():
                try:
                    doc = json.loads(cand.read_text(encoding="utf-8"))
                    if isinstance(doc, dict):
                        return doc
                except (OSError, json.JSONDecodeError):
                    pass
    return None

V70_MICRO_BRIDGE_ALIASES: dict[str, str] = {
    "exposure_bloom_landing_3f": "exposure_bloom_landing_3f",
    "exposure_bloom_3f": "exposure_bloom_landing_3f",
    "exposure_bloom": "exposure_bloom_landing_3f",
    "bloom_landing_3f": "exposure_bloom_landing_3f",
    "rack_focus_bridge_13f": "rack_focus_bridge_13f",
    "camera_rack_focus_bridge_13f": "rack_focus_bridge_13f",
    "rack_focus_13f": "rack_focus_bridge_13f",
    "rack_focus": "rack_focus_bridge_13f",
}


def _resolve_venv_python() -> Path:
    """`FILMCRAFT_VENV_PYTHON` / `PFD_VENV`, else the running interpreter, else the legacy ~/.venvs path if it exists."""
    env_py = os.environ.get("FILMCRAFT_VENV_PYTHON")
    if env_py:
        return Path(env_py).expanduser()
    pfd = os.environ.get("PFD_VENV")
    if pfd:
        p = Path(pfd).expanduser()
        return p if p.is_file() else p / "bin" / "python3"
    if sys.executable:
        return Path(sys.executable)
    return Path.home() / ".venvs/video-skills/bin/python3"


VENV_PY = _resolve_venv_python()
_PROBE_TIMEOUT_S = 120.0  # ffprobe / fc-match style probes
_RUN_TIMEOUT_S = 1800.0  # ffmpeg passes and the FilmCraft / fc_build / edit_rules / spec_lint / audit_sfx helper CLIs
SKILL_ROOT = Path(__file__).resolve().parents[2]
HAAR_CASCADE_XML = SKILL_ROOT / "data" / "haarcascade_frontalface_default.xml"

VENDORED_OVS_DIR = SKILL_ROOT / "scripts" / "vendor" / "ovs_core"


def _resolve_ovs_dir() -> Path:
    """Gate dependencies live in the vendored `scripts/vendor/ovs_core/`; `PFD_OVS_DIR` (or legacy
    `OPA_VIDEO_STUDIO_DIR`) overrides it explicitly. Never falls back silently to ~/.gemini or ~/.claude."""
    for env_name in ("PFD_OVS_DIR", "OPA_VIDEO_STUDIO_DIR"):
        raw = os.environ.get(env_name)
        if raw:
            p = Path(raw).expanduser()
            if not p.is_dir():
                print(f"⚠️  [PFD] {env_name}={p} is not a directory; gates that need it will fail loudly.", file=sys.stderr)
            return p
    return VENDORED_OVS_DIR


OPA_SKILL = _resolve_ovs_dir()
OPA_SCRIPTS = OPA_SKILL / "scripts"
AUDIO_LEVELS_PY = OPA_SCRIPTS / "audio_levels.py"
SPEC_LINT_PY = OPA_SCRIPTS / "spec_lint.py"
EDIT_RULES_PY = OPA_SCRIPTS / "edit_rules.py"
FC_BUILD_FAST_PY = OPA_SCRIPTS / "apps" / "craft-handoff" / "tools" / "fc_build_fast.py"
FC_FAST_QA_PY = OPA_SCRIPTS / "fc_fast_qa.py"
AUDIT_SFX_PY = OPA_SCRIPTS / "audit_sfx.py"
DEFAULT_RULES_JSON = OPA_SKILL / "rules.json"

# v7.9.1: one cache root for this skill (env PFD_CACHE_DIR); the pre-7.9.1 opa-video-studio cache is still READ as a fallback.
LEGACY_CACHE_ROOT = Path.home() / ".cache" / "opa-video-studio"
CACHE_ROOT = Path(os.environ["PFD_CACHE_DIR"]).expanduser() if os.environ.get("PFD_CACHE_DIR") else Path.home() / ".cache" / "pro-filmcraft-director"
BACKUP_DIR = CACHE_ROOT / "backup"
SFX_ACOUSTIC_CACHE_PATH = CACHE_ROOT / "sfx_acoustic_cache_v51.json"
LEGACY_SFX_ACOUSTIC_CACHE_PATH = LEGACY_CACHE_ROOT / "sfx_acoustic_cache_v51.json"

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
VALID_INTERP = {"linear", "bezier", "easeIn", "easeOut", "hold"}
MAIN_TEXT_LANES = {"text", "text_top", "text_sub", "text_img"}
ABS_FS_PREFIXES = ("/home/", "/tmp/", "/mnt/", "/var/", "/opt/", "/usr/", "/root/", "/media/", "/etc/")
_WIN_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/])")  # C:\x, D:/x, \\server\share


def _is_abs_media_path(s: str) -> bool:
    """Absolute filesystem path on any host: a POSIX root path, a Windows drive path or a UNC share."""
    return bool(s) and (os.path.isabs(s) or s.startswith("/") or bool(_WIN_ABS_PATH_RE.match(s)))


def _same_media_path(a: str, b: str) -> bool:
    """Compare two media paths after Unicode NFC (macOS / some exports write NFD Vietnamese names)."""
    na, nb = unicodedata.normalize("NFC", str(a)), unicodedata.normalize("NFC", str(b))
    return na == nb or Path(na).resolve() == Path(nb).resolve()

SAFE_ZONE_BOX = {"x_min": 50.0, "x_max": 1030.0, "y_min": 140.0, "y_max": 1760.0}
EYE_REL_BOX = (0.10, 0.30, 0.90, 0.50)    # matches thlib/facesafe.py face.eye_box
MOUTH_REL_BOX = (0.25, 0.70, 0.75, 0.90)  # matches thlib/facesafe.py face.mouth_box
FACE_MARGIN_PX = 10.0

STILL_PLATE_HINTS = (
    "still",
    "plate",
    "static",
    "anh_tinh",
    "ảnh tĩnh",
    "freeze",
    "ken_burns",
    "photo",
    "polaroid",
    "screenshot",
)

FONT_CANDIDATES = [
    str(Path.home() / ".local/share/fonts/tnedit/BeVietnamPro-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

_DISK_SFX_CACHE: dict[str, dict[str, Any]] | None = None
_DISK_SFX_CACHE_DIRTY = False


def _py_bin() -> str:
    return str(VENV_PY) if VENV_PY.is_file() else sys.executable


FILMCRAFT_CLI_PY = Path(__file__).resolve().parent / "filmcraft_cli.py"


def _filmcraft_bin_or_none(warn: bool = True) -> str | None:
    """Locate the FilmCraft GUI binary `filmcraft` (CRAFT_BIN_DIR, PATH, ~/.local/bin); `None` (plus a loud warning) when absent.
    A `filmcraft-cli` binary never existed (only the GUI does): 1-frame renders go through `filmcraft_cli.py`."""
    on_path = shutil.which("filmcraft")
    cands = [Path(os.environ["CRAFT_BIN_DIR"]) / "filmcraft"] if os.environ.get("CRAFT_BIN_DIR") else []
    cands += ([Path(on_path)] if on_path else []) + [Path.home() / ".local" / "bin" / "filmcraft"]
    found = next((str(c) for c in cands if c.is_file()), None)
    if found:
        return found
    if warn:
        print(
            "⚠️  [WARNING] FilmCraft binary `filmcraft` not found (checked CRAFT_BIN_DIR, PATH and ~/.local/bin/filmcraft); "
            "the step that needs it is SKIPPED, not passed. Install FilmCraft or run `scripts/env_status.py`.",
            file=sys.stderr,
        )
    return None


def _filmcraft_bin() -> str:
    found = _filmcraft_bin_or_none(warn=False)
    if found:
        return found
    raise FileNotFoundError("Binary not found: filmcraft (checked CRAFT_BIN_DIR, PATH and ~/.local/bin/filmcraft)")


def _filmcraft_cli_cmd(warn: bool = True) -> list[str] | None:
    """Command prefix of the control-bridge shim (`scripts/tools/filmcraft_cli.py`), or `None` when the `filmcraft` binary is absent."""
    if _filmcraft_bin_or_none(warn=warn) is None:
        return None
    return [sys.executable, str(FILMCRAFT_CLI_PY)]


def _filmcraft_render_smoke(cli_cmd: list[str], project: Path, seconds: float, out_png: Path, timeout_s: int = 300) -> tuple[int, dict[str, Any]]:
    """Run `filmcraft_cli.py --project P render --seconds S --out F` (no `--allow-offline`); returns (exit code, the shim's JSON line)."""
    try:
        r = subprocess.run(
            [*cli_cmd, "--project", str(project), "render", "--seconds", f"{seconds:.2f}", "--out", str(out_png)],
            capture_output=True, text=True, check=False, timeout=timeout_s,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 124, {"ok": False, "error": f"filmcraft_cli.py timed out after {timeout_s}s"}
    last = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        payload = json.loads(last)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": (r.stderr or r.stdout).strip()[-500:]}
    return r.returncode, payload if isinstance(payload, dict) else {"ok": False, "error": last[:500]}


def _loud_smoke_skip(reason: str) -> None:
    print(f"⚠️  [SMOKE SKIPPED] 1-frame render smoke ({reason}); the '0 offline media' check did NOT run.", file=sys.stderr)


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _snap(t: float, fps: float) -> float:
    return round(round(float(t) * fps) / fps, 6)


def _lane(track_name: str) -> str:
    cleaned = track_name.replace("FX ·", "").strip()
    parts = cleaned.split()
    return parts[0] if parts else ""


def _is_animated_kf_list(val: Any) -> bool:
    return (
        isinstance(val, list)
        and len(val) > 0
        and all(
            isinstance(k, (list, tuple))
            and len(k) in (2, 3)
            and _is_num(k[0])
            for k in val
        )
    )


# ==============================================================================
# [P0] Acoustic SFX Profiling (`5ms env5` `lag_ms` + MD5 Cache) & R217 `match_at`
# ==============================================================================

def _load_disk_sfx_cache() -> dict[str, dict[str, Any]]:
    global _DISK_SFX_CACHE
    if _DISK_SFX_CACHE is not None:
        return _DISK_SFX_CACHE
    for cache_path in (SFX_ACOUSTIC_CACHE_PATH, LEGACY_SFX_ACOUSTIC_CACHE_PATH):
        if not cache_path.is_file():
            continue
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _DISK_SFX_CACHE = data
                return _DISK_SFX_CACHE
        except (OSError, json.JSONDecodeError):
            pass
    _DISK_SFX_CACHE = {}
    return _DISK_SFX_CACHE


def _flush_disk_sfx_cache() -> None:
    global _DISK_SFX_CACHE_DIRTY
    if not _DISK_SFX_CACHE_DIRTY or _DISK_SFX_CACHE is None:
        return
    try:
        SFX_ACOUSTIC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SFX_ACOUSTIC_CACHE_PATH.with_name(f"{SFX_ACOUSTIC_CACHE_PATH.name}.{os.getpid()}.tmp")
        tmp_path.write_text(
            json.dumps(_DISK_SFX_CACHE, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(tmp_path, SFX_ACOUSTIC_CACHE_PATH)  # atomic: parallel compiles never read a half-written cache
        _DISK_SFX_CACHE_DIRTY = False
    except OSError:
        pass


@lru_cache(maxsize=None)
def probe_media_duration(path_str: str) -> float | None:
    """Probe exact playable duration (min of format duration and primary media stream duration if finite)."""
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration",
            "-of",
            "json",
            path_str,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=_PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

    candidates: list[float] = []
    fmt_dur = (data.get("format") or {}).get("duration")
    if fmt_dur is not None:
        try:
            fd = float(fmt_dur)
            if math.isfinite(fd) and fd > 0:
                candidates.append(fd)
        except ValueError:
            pass

    for st in data.get("streams") or []:
        if st.get("codec_type") in ("video", "audio") and st.get("duration") is not None:
            try:
                sd = float(st["duration"])
                if math.isfinite(sd) and sd > 0:
                    candidates.append(sd)
            except ValueError:
                pass

    return min(candidates) if candidates else None


@lru_cache(maxsize=None)
def decode_mono_48k(path_str: str) -> np.ndarray:
    """Decode audio file to 48kHz mono float64 (averaging channels cleanly)."""
    r_ch = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=channels",
            "-of",
            "default=nw=1:nk=1",
            path_str,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=_PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    try:
        ch = max(1, int((r_ch.stdout or "2").split()[0]))
    except (ValueError, IndexError):
        ch = 2

    r = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            path_str,
            "-vn",
            "-ac",
            str(ch),
            "-ar",
            str(SR),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=False,
        timeout=_RUN_TIMEOUT_S,
    )
    if r.returncode != 0 or not r.stdout:
        return np.zeros(0, dtype=np.float64)
    arr = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    n_frames = len(arr) // ch
    if n_frames <= 0:
        return np.zeros(0, dtype=np.float64)
    arr = arr[: n_frames * ch].reshape(n_frames, ch)
    return arr[:, 0] if ch == 1 else arr.mean(axis=1)


@lru_cache(maxsize=None)
def measure_sfx_acoustic_profile(path_str: str) -> dict[str, Any] | None:
    """
    Ported from `thlib/sfxlib.py::_shape`:
      - Decodes mono 48kHz PCM
      - Computes `5ms` (`240`-sample) boxcar envelope `env5`
      - Finds exact acoustic climax `lag_ms = argmax(env5) / 48.0`, `dur_s`, and file `md5`
      - Cached in memory and `$PFD_CACHE_DIR/sfx_acoustic_cache_v51.json` (default `~/.cache/pro-filmcraft-director`)
    """
    global _DISK_SFX_CACHE_DIRTY
    p = Path(path_str)
    if not p.is_file():
        return None
    resolved = p.resolve()
    try:
        st = resolved.stat()
    except OSError:
        return None

    cache_key = f"{resolved}|{st.st_mtime_ns}|{st.st_size}"
    disk_cache = _load_disk_sfx_cache()
    cached = disk_cache.get(cache_key)
    if isinstance(cached, dict) and "md5" in cached and "lag_ms" in cached and "dur_s" in cached:
        return cached

    try:
        file_md5 = hashlib.md5(resolved.read_bytes()).hexdigest()
    except OSError:
        return None

    y = decode_mono_48k(str(resolved))
    probed_dur = probe_media_duration(str(resolved))
    pcm_dur = len(y) / float(SR) if len(y) > 0 else 0.0
    if probed_dur is not None and pcm_dur > 0:
        dur_s = min(probed_dur, pcm_dur)
    else:
        dur_s = probed_dur or pcm_dur

    if len(y) == 0 or dur_s <= 0:
        prof = {
            "path": str(resolved),
            "md5": file_md5,
            "dur_s": round(float(dur_s or 0.0), 6),
            "lag_ms": 0.0,
            "lag_s": 0.0,
            "peak_dbfs": -240.0,
            "has_signal": False,
        }
        disk_cache[cache_key] = prof
        _DISK_SFX_CACHE_DIRTY = True
        return prof

    peak_amp = float(np.max(np.abs(y)))
    peak_dbfs = 20.0 * math.log10(max(peak_amp, 1e-12))
    env5 = np.convolve(np.abs(y), np.ones(ENV5_WIN, dtype=np.float64) / ENV5_WIN, mode="same")
    ip = int(np.argmax(env5))
    lag_ms = round(ip / 48.0, 2)
    lag_s = round(ip / float(SR), 6)

    prof = {
        "path": str(resolved),
        "md5": file_md5,
        "dur_s": round(float(dur_s), 6),
        "lag_ms": lag_ms,
        "lag_s": lag_s,
        "peak_dbfs": round(peak_dbfs, 2),
        "has_signal": bool(peak_dbfs > -65.0),
    }
    disk_cache[cache_key] = prof
    _DISK_SFX_CACHE_DIRTY = True
    return prof


def match_at(window: np.ndarray, seg: np.ndarray) -> int:
    """
    Ruling R217 (`thlib/audio.py:226-233`):
    FFT sliding-L2 cosine-similarity normalized cross-correlation so louder speech near an SFX cue
    never pulls correlation away from the true SFX transient.
    """
    num = correlate(window, seg, mode="valid", method="fft")
    cs = np.concatenate(([0.0], np.cumsum(np.asarray(window, dtype=np.float64) ** 2)))
    energy = np.sqrt(np.maximum(cs[len(seg) :] - cs[: -len(seg)], 0.0))
    best_idx = int(np.argmax(num / np.maximum(energy, 1e-12)))
    return best_idx


def audit_sfx_sync_r217(
    sfx_stem_wav: Path,
    mix_wav: Path,
    levels_spec: dict[str, Any],
    fps: float,
) -> dict[str, Any]:
    """
    Gate 7 Ruling `R217` SFX Sync Audit:
      - Compares `stems/sfx.wav` against FilmCraft's exported `mix.wav`
      - Checks isolated/active SFX cues inside a `±10 frame` window around each cue's peak
      - Reports `ncc_verified_cues`, `median_abs_offset_frames`, and flags warnings if any cue
        appears muted (`energy == 0` in mix) or shifted `> 3 frames`.
    """
    if not sfx_stem_wav.is_file() or not mix_wav.is_file():
        return {
            "executed": False,
            "reason": "missing sfx.wav or mix.wav",
            "ncc_verified_cues": 0,
            "median_abs_offset_frames": 0.0,
            "muted_cues": [],
            "shifted_cues": [],
            "warnings": [],
            "cues": [],
        }

    sfx_mono = decode_mono_48k(str(sfx_stem_wav))
    mix_mono = decode_mono_48k(str(mix_wav))
    n_min = min(len(sfx_mono), len(mix_mono))
    if n_min < ENV5_WIN * 2:
        return {
            "executed": False,
            "reason": "decoded audio too short",
            "ncc_verified_cues": 0,
            "median_abs_offset_frames": 0.0,
            "muted_cues": [],
            "shifted_cues": [],
            "warnings": [],
            "cues": [],
        }

    sfx_mono = sfx_mono[:n_min]
    mix_mono = mix_mono[:n_min]

    # Collect SFX clips from spec to label cues accurately
    spec_sfx_clips: list[dict[str, Any]] = []
    for tr in levels_spec.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            if cl.get("src") and classify_audio_role(tname, cl) == "sfx":
                spec_sfx_clips.append(
                    {
                        "track": tname,
                        "name": str(cl.get("name", "SFX")),
                        "at": float(cl.get("at", 0.0)),
                        "end": float(cl.get("at", 0.0)) + float(cl.get("dur", 0.0)),
                    }
                )

    env5 = np.convolve(np.abs(sfx_mono), np.ones(ENV5_WIN, dtype=np.float64) / ENV5_WIN, mode="same")
    active = env5 > 5e-4
    diff = np.diff(active.astype(np.int8), prepend=0, append=0)
    raw_runs = list(zip(np.where(diff == 1)[0].tolist(), np.where(diff == -1)[0].tolist()))

    # Merge micro-gaps (< 60ms) inside multi-transient SFX bodies
    bodies: list[list[int]] = []
    merge_gap = int(0.06 * SR)
    for a, b in raw_runs:
        if bodies and (a - bodies[-1][1]) < merge_gap:
            bodies[-1][1] = b
        else:
            bodies.append([a, b])

    search_samples = int(round(10.0 * SR / fps))  # ±10 frames
    cue_reports: list[dict[str, Any]] = []
    muted_cues: list[dict[str, Any]] = []
    shifted_cues: list[dict[str, Any]] = []
    warnings: list[str] = []

    for idx_b, (a, b) in enumerate(bodies):
        b = min(b, n_min)
        if (b - a) < int(0.08 * SR):
            continue
        seg = sfx_mono[a:b]
        seg_norm = float(np.linalg.norm(seg))
        if seg_norm <= 1e-6:
            continue

        pk_idx = a + int(np.argmax(env5[a:b]))
        pk_s = round(pk_idx / float(SR), 4)

        # Match cue label from spec
        matched_names = [
            c["name"]
            for c in spec_sfx_clips
            if (c["at"] - 0.05) <= pk_s <= (c["end"] + 0.05)
        ]
        cue_label = matched_names[0] if matched_names else f"sfx_cue_{idx_b + 1:02d}"

        lo = max(0, a - search_samples)
        hi = min(n_min, b + search_samples)
        window = mix_mono[lo:hi]
        if len(window) < len(seg):
            continue

        cs = np.concatenate(([0.0], np.cumsum(np.asarray(window, dtype=np.float64) ** 2)))
        win_energies = np.sqrt(np.maximum(cs[len(seg) :] - cs[: -len(seg)], 0.0))
        max_mix_energy = float(np.max(win_energies)) if len(win_energies) else 0.0

        if max_mix_energy <= 1e-7:
            rec = {
                "cue": cue_label,
                "peak_s": pk_s,
                "offset_frames": None,
                "mix_energy": 0.0,
                "status": "MUTED",
            }
            cue_reports.append(rec)
            muted_cues.append(rec)
            warnings.append(
                f"R217 MUTED_SFX: Cue '{cue_label}' (peak={pk_s:.2f}s) has zero energy in mix.wav "
                f"— Fix: unmute track or raise clip '{cue_label}' gain_db at {pk_s:.2f}s"
            )
            continue

        # Skip low-SNR SFX cues buried > 16.5 dB underneath loud concurrent speech/BGM
        local_mix_norm = float(np.linalg.norm(mix_mono[a:b]))
        snr_ratio = seg_norm / max(local_mix_norm, 1e-12)
        if snr_ratio < 0.15:
            continue

        best_idx = match_at(window, seg)
        offset_f = round((lo + best_idx - a) * fps / float(SR), 2)
        status = "SHIFTED" if abs(offset_f) > 3.0 else "OK"
        rec = {
            "cue": cue_label,
            "peak_s": pk_s,
            "offset_frames": offset_f,
            "snr_ratio": round(snr_ratio, 3),
            "mix_energy": round(max_mix_energy, 4),
            "status": status,
        }
        cue_reports.append(rec)
        if abs(offset_f) > 3.0:
            shifted_cues.append(rec)
            warnings.append(
                f"R217 SFX_SHIFT: Cue '{cue_label}' (peak={pk_s:.2f}s) shifted by {offset_f:+.2f} frames (> 3f) in mix.wav "
                f"— Fix: shift clip '{cue_label}' at by {-offset_f / fps:+.3f}s ({-offset_f:+.1f} frames)"
            )

    valid_offsets = [abs(float(c["offset_frames"])) for c in cue_reports if c.get("offset_frames") is not None]
    median_abs = round(float(np.median(valid_offsets)), 3) if valid_offsets else 0.0

    return {
        "executed": True,
        "ncc_verified_cues": len(valid_offsets),
        "median_abs_offset_frames": median_abs,
        "max_abs_offset_frames": round(max(valid_offsets), 3) if valid_offsets else 0.0,
        "muted_cues": muted_cues,
        "shifted_cues": shifted_cues,
        "warnings": warnings,
        "cues": cue_reports,
    }


# ==============================================================================
# [P2] BGM Steady-State Offset Selector (`16kHz` LRA) & R35 Post-AAC True Peak
# ==============================================================================

def select_steady_state_bgm_offset(
    bgm_path: Path,
    clip_dur_s: float,
    file_dur_s: float,
    fps: float,
) -> dict[str, Any]:
    """
    Scan candidate `in` offsets (`0.0, 2.0 .. min(24.0, file_dur - clip_dur)`) on a fast `16kHz`
    downsampled mono envelope and pick the window with the lowest EBU Tech 3342 LRA / dynamic variance
    (target `LRA <= 5.5 LU`, avoiding quiet-intro -> loud-drop swells drowning speech).
    """
    sr_16k = 16000
    max_offset = min(24.0, max(0.0, file_dur_s - clip_dur_s - 0.10))
    if max_offset < 1.95:
        return {"selected_in_s": 0.0, "lra_lu": 0.0, "lra_at_0_lu": 0.0, "candidates_tested": 1, "changed": False}

    max_decode_s = min(file_dur_s, clip_dur_s + max_offset + 1.0)
    r = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-t",
            f"{max_decode_s:.2f}",
            "-i",
            str(bgm_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sr_16k),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
        check=False,
        timeout=_RUN_TIMEOUT_S,
    )
    if r.returncode != 0 or not r.stdout:
        return {"selected_in_s": 0.0, "lra_lu": 0.0, "lra_at_0_lu": 0.0, "candidates_tested": 0, "changed": False}

    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    win = int(3.0 * sr_16k)
    hop = int(0.1 * sr_16k)
    if len(x) < win + hop:
        return {"selected_in_s": 0.0, "lra_lu": 0.0, "lra_at_0_lu": 0.0, "candidates_tested": 1, "changed": False}

    cs = np.concatenate(([0.0], np.cumsum(x * x)))
    starts = np.arange(0, len(x) - win + 1, hop)
    st_db = -0.691 + 10.0 * np.log10(np.maximum((cs[starts + win] - cs[starts]) / win, 1e-20))

    def _window_lra_and_std(st_slice: np.ndarray) -> tuple[float, float]:
        if len(st_slice) == 0:
            return 99.0, 99.0
        keep = st_slice >= -70.0
        if not np.any(keep):
            return 99.0, 99.0
        rel = -0.691 + 10.0 * np.log10(np.mean(10.0 ** ((st_slice[keep] + 0.691) / 10.0))) - 20.0
        kept = st_slice[keep & (st_slice >= rel)]
        if len(kept) == 0:
            return 99.0, 99.0
        return float(np.percentile(kept, 95) - np.percentile(kept, 10)), float(np.std(kept))

    candidates: list[tuple[float, float, float]] = []
    off = 0.0
    while off <= max_offset + 1e-6:
        snapped_off = _snap(off, fps)
        if snapped_off + clip_dur_s <= file_dur_s - 0.02:
            lo = max(0, int(round((snapped_off + 1.0) / 0.1)))
            hi = min(len(st_db), max(lo + 1, int(round((snapped_off + clip_dur_s - 1.5 - 3.0) / 0.1)) + 1))
            lra_val, std_val = _window_lra_and_std(st_db[lo:hi])
            candidates.append((snapped_off, lra_val, std_val))
        off += 2.0

    if not candidates:
        return {"selected_in_s": 0.0, "lra_lu": 0.0, "lra_at_0_lu": 0.0, "candidates_tested": 0, "changed": False}

    lra_0 = candidates[0][1]
    best_off, best_lra, best_std = min(candidates, key=lambda c: (round(c[1], 3), round(c[2], 3), c[0]))
    return {
        "selected_in_s": best_off,
        "lra_lu": round(best_lra, 2),
        "std_lu": round(best_std, 2),
        "lra_at_0_lu": round(lra_0, 2),
        "steady_state_ok": bool(best_lra <= 5.5),
        "candidates_tested": len(candidates),
        "changed": bool(best_off > 1e-4),
    }


def measure_ebur128(wav_path: Path) -> dict[str, float]:
    r = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(wav_path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    err = r.stderr
    if r.returncode != 0 or "Summary:" not in err:
        raise RuntimeError(f"Failed to measure EBU R128 on {wav_path}")
    summary = err[err.rfind("Summary:") :]

    def _extract(key: str) -> float:
        m = re.search(rf"{key}:\s+(-?[\d.]+|-?inf)", summary)
        if not m:
            return -math.inf
        s = m.group(1)
        return -math.inf if "inf" in s else float(s)

    return {
        "lufs": round(_extract("I"), 2),
        "lra": round(_extract("LRA"), 2),
        "true_peak_dbtp": round(_extract("Peak"), 2),
    }


def measure_post_aac_true_peak_dbtp(wav_path: Path) -> float:
    """
    Ruling `R35` Post-AAC True-Peak Guard:
    Encode `mix.wav` to in-memory AAC (`-c:a aac -b:a 192k -f adts -`) -> decode & measure
    `4x` oversampled True Peak via `ebur128=peak=true`.
    """
    enc = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(wav_path),
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SR),
            "-f",
            "adts",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    dec = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-f",
            "aac",
            "-i",
            "-",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        stdin=enc.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if enc.stdout is not None:
        enc.stdout.close()
    _, dec_err_bytes = dec.communicate()
    enc.wait()
    dec_err = dec_err_bytes.decode("utf-8", "replace")
    if dec.returncode != 0 or "Summary:" not in dec_err:
        raise RuntimeError(f"Failed to measure post-AAC R35 True Peak on {wav_path}")
    summary = dec_err[dec_err.rfind("Summary:") :]
    m = re.search(r"Peak:\s+(-?[\d.]+|-?inf)", summary)
    if not m or "inf" in m.group(1):
        return -math.inf
    return round(float(m.group(1)), 2)


# ==============================================================================
# Audio Classification, Sanitizer & Fast In-Place `.fcproj` Gain Re-Trim
# ==============================================================================

def classify_audio_role(track_name: str, clip: dict[str, Any]) -> str | None:
    for text in (clip.get("name", ""), track_name):
        s = str(text).lower()
        if "sfx" in s:
            return "sfx"
        if any(k in s for k in ("nhạc", "music", "bgm", "drone", "sub_drone", "undertone")):
            return "bgm"
        if "giọng" in s or "voice" in s or re.match(r"\s*(vo|a1)\b", s):
            return "voice"
    return None


def _is_bgm_or_drone_clip(track_name: str, clip: dict[str, Any]) -> bool:
    if classify_audio_role(track_name, clip) == "bgm":
        return True
    combined = f"{clip.get('name', '')} {track_name}".lower()
    return any(k in combined for k in ("nhạc", "music", "bgm", "drone", "ambient", "bed", "pad", "undertone"))


def ensure_audio_role_tag(track: dict[str, Any], clip: dict[str, Any]) -> None:
    """Only if an audio clip lacks Vietnamese/standard keywords needed by audio_levels.py, append a non-destructive role tag."""
    tname = str(track.get("name", ""))
    cname = str(clip.get("name", ""))
    has_audio_levels_kw = any(
        k in f"{cname} {tname}".lower()
        for k in ("sfx", "nhạc", "music", "bgm", "giọng", "voice")
    ) or bool(re.match(r"\s*vo\b", cname.lower())) or bool(re.match(r"\s*vo\b", tname.lower()))
    if has_audio_levels_kw:
        return
    combined = f"{cname} {tname}".lower()
    if any(k in combined for k in ("narration", "dialogue", "speech", "vocal", "talk", "aroll", "a-roll")) or re.match(r"\s*a1\b", tname.lower()):
        clip["name"] = f"{clip.get('name') or 'Audio'} (Voice)".strip()
    elif any(k in combined for k in ("ambient", "bed", "score", "soundtrack", "song", "drone", "pad", "undertone")):
        clip["name"] = f"{clip.get('name') or 'Audio'} (BGM)".strip()
    else:
        clip["name"] = f"{clip.get('name') or 'Audio'} (SFX)".strip()


VOCAL_CHEST_WARMTH_DEFAULT = {
    "freq_hz": 185.0,
    "gain_db": 2.2,
    "q": 1.15,
    "hpf_hz": 75.0,
}


def apply_vocal_chest_warmth_185hz(
    src_path: Path,
    work_dir: Path,
    gain_db: float = 2.2,
    freq_hz: float = 185.0,
    q_val: float = 1.15,
    hpf_hz: float = 75.0,
) -> Path | None:
    """
    `v6.0` Vocal Chest Warmth (`+2.2 dB @ 185Hz`, `Q=1.15` + `75Hz` HPF):
    Renders a deterministic cached 48kHz PCM WAV in `<work_dir>/_vocal_warmth_cache/` when requested.
    """
    if not src_path.is_file():
        return None
    cache_dir = work_dir / "_vocal_warmth_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    st = src_path.stat()
    sig = hashlib.md5(
        f"{src_path.resolve()}|{st.st_mtime_ns}|{st.st_size}|{freq_hz:.1f}|{gain_db:.2f}|{q_val:.2f}|{hpf_hz:.1f}".encode()
    ).hexdigest()[:12]
    out_wav = cache_dir / f"{src_path.stem}_warm185_{sig}.wav"
    if out_wav.is_file() and out_wav.stat().st_size > 256:
        return out_wav
    af_chain = f"highpass=f={hpf_hz:g},equalizer=f={freq_hz:g}:t=q:w={q_val:g}:g={gain_db:g}"
    r = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(src_path),
            "-vn",
            "-af",
            af_chain,
            "-ar",
            str(SR),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        capture_output=True,
        check=False,
        timeout=_RUN_TIMEOUT_S,
    )
    if r.returncode == 0 and out_wav.is_file() and out_wav.stat().st_size > 256:
        return out_wav
    return None


def _normalize_bgm_stop_windows(
    raw_stops: Any,
    seq_dur: float,
    fps: float,
    bgm_beats: list[float] | None = None,
) -> list[tuple[float, float]]:
    """
    Normalize `meta.bgm_stops: [[start_s, end_s], ...]` into merged, frame-snapped
    `>= 0.50s` silence vacuum windows within `[0.0, seq_dur]`, optionally beat-aligning re-entry.
    """
    if not isinstance(raw_stops, list):
        return []
    parsed: list[tuple[float, float]] = []
    beats_sorted = sorted(float(b) for b in (bgm_beats or []) if _is_num(b))
    for item in raw_stops:
        s_raw: float | None = None
        e_raw: float | None = None
        if isinstance(item, (list, tuple)) and len(item) >= 2 and _is_num(item[0]) and _is_num(item[1]):
            s_raw, e_raw = float(item[0]), float(item[1])
        elif isinstance(item, dict) and _is_num(item.get("start")) and _is_num(item.get("end")):
            s_raw, e_raw = float(item["start"]), float(item["end"])
        if s_raw is None or e_raw is None or e_raw <= s_raw + 1e-4:
            continue
        st_s = max(0.0, min(seq_dur, _snap(s_raw, fps)))
        en_s = max(st_s, min(seq_dur, _snap(e_raw, fps)))
        min_vacuum = _snap(0.50, fps)
        if (en_s - st_s) < min_vacuum - 1e-6:
            en_s = min(seq_dur, _snap(st_s + 0.50, fps))
        if beats_sorted and en_s < seq_dur - 1.0 / fps:
            cand_beats = [b for b in beats_sorted if (en_s - 0.020) <= b <= min(seq_dur, en_s + 0.085)]
            if cand_beats:
                snapped_beat = _snap(min(cand_beats, key=lambda b: abs(b - en_s)), fps)
                if (snapped_beat - st_s) >= min_vacuum - 1e-6:
                    en_s = snapped_beat
        if (en_s - st_s) >= min(min_vacuum, seq_dur) - 1e-6 and en_s > st_s + (1.0 / fps):
            parsed.append((st_s, en_s))

    parsed.sort(key=lambda w: (w[0], w[1]))
    merged: list[tuple[float, float]] = []
    for st_s, en_s in parsed:
        if merged and st_s <= merged[-1][1] + (1.0 / fps) + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], en_s))
        else:
            merged.append((st_s, en_s))
    return merged


def _slice_clip_gain_for_subsegment(
    orig_gain: Any,
    sub_offset_s: float,
    sub_dur_s: float,
    fps: float,
    pre_stop_fade_out_s: float | None = None,
    reentry_fade_in_s: float | None = None,
) -> Any:
    """Slice scalar or keyframed `gain_db` onto `[sub_offset_s, sub_offset_s + sub_dur_s]` with crisp stop/reentry ramps."""
    one_f = 1.0 / fps
    if _is_animated_kf_list(orig_gain):
        v_start = round(float(_eval_kf_param(orig_gain, sub_offset_s, 0.0)), 2)
        v_end = round(float(_eval_kf_param(orig_gain, sub_offset_s + sub_dur_s, 0.0)), 2)
        inner = [
            [round(float(k[0]) - sub_offset_s, 6), round(float(k[1]), 2), *(list(k[2:3]))]
            for k in sorted(orig_gain, key=lambda x: float(x[0]))
            if (sub_offset_s + 0.5 * one_f) < float(k[0]) < (sub_offset_s + sub_dur_s - 0.5 * one_f)
        ]
        kfs: list[list[Any]] = [[0.0, v_start, "linear"], *inner, [round(sub_dur_s, 6), v_end]]
    else:
        base_db = round(float(orig_gain if _is_num(orig_gain) else 0.0), 2)
        if pre_stop_fade_out_s is None and reentry_fade_in_s is None:
            return base_db
        kfs = [[0.0, base_db, "linear"], [round(sub_dur_s, 6), base_db]]

    if reentry_fade_in_s is not None and sub_dur_s >= reentry_fade_in_s + 2.0 * one_f:
        fi = _snap(max(one_f, reentry_fade_in_s), fps)
        v_fi = round(float(_eval_kf_param(kfs, fi, 0.0)), 2)
        kfs = [[0.0, round(v_fi - 30.0, 2), "easeOut"], [fi, v_fi, "linear"]] + [
            k for k in kfs if float(k[0]) > fi + 0.5 * one_f
        ]

    if pre_stop_fade_out_s is not None and sub_dur_s >= pre_stop_fade_out_s + 2.0 * one_f:
        fo = _snap(max(one_f, pre_stop_fade_out_s), fps)
        t_fo_start = round(sub_dur_s - fo, 6)
        v_fo = round(float(_eval_kf_param(kfs, t_fo_start, 0.0)), 2)
        kfs = [k for k in kfs if float(k[0]) < t_fo_start - 0.5 * one_f] + [
            [t_fo_start, v_fo, "easeIn"],
            [round(sub_dur_s, 6), round(v_fo - 48.0, 2)],
        ]

    return kfs


def carve_bgm_silence_stops(
    tracks: list[dict[str, Any]],
    stop_windows: list[tuple[float, float]],
    fps: float,
) -> list[dict[str, Any]]:
    """
    `v6.0` Music Stop Vacuum Carver:
    Splits/carves `bgm` & `drone` clips around every `[start_s, end_s]` window (`>= 0.50s` true `-inf dB`
    silence vacuum with crisp `35ms` pre-stop fade-out and beat-aligned click-free re-entry).
    """
    if not stop_windows:
        return []
    min_seg_dur = _snap(2.0 / fps, fps)
    pre_fade_s = max(1.0 / fps, _snap(0.035, fps))  # crisp ~35ms pre-stop fade-out (1f@30fps / 2f@60fps)
    reentry_fade_s = 1.0 / fps                      # crisp 1-frame beat-aligned re-entry
    carved_records: list[dict[str, Any]] = []

    for tr in tracks:
        if tr.get("type") != "audio":
            continue
        tname = str(tr.get("name", ""))
        orig_clips = tr.get("clips", [])
        if not orig_clips:
            continue
        new_clips: list[dict[str, Any]] = []
        for cl in orig_clips:
            if not _is_bgm_or_drone_clip(tname, cl):
                new_clips.append(cl)
                continue
            c_at0 = float(cl.get("at", 0.0))
            c_dur0 = float(cl.get("dur", 0.0))
            c_end0 = c_at0 + c_dur0
            c_in0 = max(0.0, float(cl.get("in", 0.0)))
            raw_spd = float(cl.get("speed", 1.0))
            spd_factor = raw_spd / 100.0 if raw_spd > 10.0 else max(0.01, raw_spd)
            orig_gain = cl.get("gain_db", 0.0)
            base_name = str(cl.get("name") or "BGM")

            overlapping = [(st, en) for (st, en) in stop_windows if en > c_at0 + 1e-5 and st < c_end0 - 1e-5]
            if not overlapping:
                new_clips.append(cl)
                continue

            # Carve `[c_at0, c_end0]` around all overlapping `[st, en]` stop windows
            cursor = c_at0
            seg_idx = 0
            entered_after_stop = False
            for st_s, en_s in overlapping:
                eff_st = max(cursor, st_s)
                eff_en = min(c_end0, en_s)
                left_dur = _snap(eff_st - cursor, fps)
                if left_dur >= min_seg_dur:
                    seg_idx += 1
                    sub_off = cursor - c_at0
                    left_cl = copy.deepcopy(cl)
                    left_cl["at"] = _snap(cursor, fps)
                    left_cl["dur"] = left_dur
                    left_cl["in"] = round(c_in0 + sub_off * spd_factor, 4)
                    if len(overlapping) >= 1:
                        left_cl["name"] = f"{base_name} #{seg_idx}" if seg_idx > 1 else base_name
                    left_cl["gain_db"] = _slice_clip_gain_for_subsegment(
                        orig_gain,
                        sub_offset_s=sub_off,
                        sub_dur_s=left_dur,
                        fps=fps,
                        pre_stop_fade_out_s=pre_fade_s,
                        reentry_fade_in_s=reentry_fade_s if entered_after_stop else None,
                    )
                    left_cl.pop("transition_out", None)
                    new_clips.append(left_cl)

                carved_records.append(
                    {
                        "track": tname,
                        "source_clip": base_name,
                        "stop_start_s": round(eff_st, 4),
                        "stop_end_s": round(eff_en, 4),
                        "vacuum_dur_s": round(eff_en - eff_st, 4),
                        "pre_stop_fade_ms": round(pre_fade_s * 1000.0, 1),
                        "reentry_at_s": round(eff_en, 4) if eff_en < c_end0 - min_seg_dur else None,
                    }
                )
                cursor = eff_en
                entered_after_stop = True

            tail_dur = _snap(c_end0 - cursor, fps)
            if tail_dur >= min_seg_dur:
                seg_idx += 1
                sub_off = cursor - c_at0
                right_cl = copy.deepcopy(cl)
                right_cl["at"] = _snap(cursor, fps)
                right_cl["dur"] = tail_dur
                right_cl["in"] = round(c_in0 + sub_off * spd_factor, 4)
                right_cl["name"] = f"{base_name} #{seg_idx}" if seg_idx > 1 else base_name
                right_cl["gain_db"] = _slice_clip_gain_for_subsegment(
                    orig_gain,
                    sub_offset_s=sub_off,
                    sub_dur_s=tail_dur,
                    fps=fps,
                    pre_stop_fade_out_s=None,
                    reentry_fade_in_s=reentry_fade_s if entered_after_stop else None,
                )
                right_cl.pop("transition_in", None)
                new_clips.append(right_cl)

        new_clips.sort(key=lambda c: float(c.get("at", 0.0)))
        tr["clips"] = new_clips

    return carved_records


def resolve_clip_src(
    raw_src: str,
    spec_dir: Path,
    portable_root: Path | None,
    work_dir: Path,
) -> str:
    p = Path(raw_src)
    if p.is_absolute():
        return str(p)
    for base in [spec_dir, portable_root, work_dir, Path.cwd()]:
        if base is not None:
            cand = (base / p).resolve()
            if cand.is_file():
                return str(cand)
    fallback_base = portable_root if portable_root is not None else spec_dir
    return str((fallback_base / p).resolve())


def sanitize_keyframe_list(kf_list: list[Any], dur: float, fps: float) -> tuple[Any, bool]:
    """
    Ensure `[t, val, ease]` keyframe list has strictly increasing frame-aligned `t` within `[0.0, dur]`.
    Returns `(sanitized_list_or_scalar, was_modified)`.
    """
    max_frame = max(1, round(dur * fps))
    raw_items: list[tuple[float, Any, str | None]] = []
    for k in kf_list:
        t_raw = float(k[0])
        val = k[1]
        has_interp = len(k) >= 3 and k[2] is not None
        interp = str(k[2]) if has_interp else None
        if interp is not None and interp not in VALID_INTERP:
            interp = "linear"
        raw_items.append((t_raw, val, interp))

    indexed = sorted(enumerate(raw_items), key=lambda x: (x[1][0], x[0]))
    frames_assigned: list[tuple[int, Any, str | None]] = []
    for _, (t_raw, val, interp) in indexed:
        t_clamped = max(0.0, min(dur, t_raw))
        f_idx = max(0, min(max_frame, round(t_clamped * fps)))
        frames_assigned.append((f_idx, val, interp))

    if len(frames_assigned) >= 3:
        f_last = frames_assigned[-1][0]
        f_prev = frames_assigned[-2][0]
        f_prev2 = frames_assigned[-3][0]
        if f_last == max_frame and f_prev == max_frame and (max_frame - 1) > f_prev2:
            frames_assigned[-2] = (max_frame - 1, frames_assigned[-2][1], frames_assigned[-2][2])

    by_frame: dict[int, tuple[Any, str | None]] = {}
    for idx_k, (f_idx, val, interp) in enumerate(frames_assigned):
        if f_idx == 0 and 0 in by_frame and idx_k > 0 and len(frames_assigned) == 2:
            if max_frame >= 1:
                by_frame[max_frame] = (val, interp)
                continue
        by_frame[f_idx] = (val, interp)

    out_kfs: list[list[Any]] = []
    for f_idx in sorted(by_frame):
        t_s = round(f_idx / fps, 6)
        val, interp = by_frame[f_idx]
        if interp is not None:
            out_kfs.append([t_s, val, interp])
        else:
            out_kfs.append([t_s, val])

    if len(out_kfs) == 1:
        return out_kfs[0][1], True

    changed = out_kfs != [list(k) for k in kf_list]
    return out_kfs, changed


def walk_and_sanitize_keyframes(node: Any, dur: float, fps: float) -> int:
    """Recursively sanitize all keyframe lists inside a clip dict; returns count of modified lists."""
    modified_count = 0
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k in ("src", "text", "name"):
                continue
            v = node[k]
            if _is_animated_kf_list(v):
                new_v, mod = sanitize_keyframe_list(v, dur, fps)
                node[k] = new_v
                if mod:
                    modified_count += 1
            else:
                modified_count += walk_and_sanitize_keyframes(v, dur, fps)
    elif isinstance(node, list):
        for item in node:
            modified_count += walk_and_sanitize_keyframes(item, dur, fps)
    return modified_count


def _infer_sfx_sync_frame_offset(track_name: str, clip_name: str) -> int | None:
    """
    For `AUTO:<keyword>` SFX clips:
      - V1 cut / opener SFX (`mở đầu`, `chuyển cảnh`, `cut`, `trans`): `sync_frame_offset = 0`
      - Hero text / UI card entrance SFX (`nhấn`, `accent`, `hero`, `ui`, `đồ hoạ`, `card`, `pop`): `+5` frames
        (lands at ~90% visual settle!)
    """
    cn = clip_name.lower()
    tn = track_name.lower()
    if any(k in cn for k in ("mở đầu", "open", "chuyển cảnh", "cut", "trans")):
        return 0
    if any(k in tn for k in ("chuyển cảnh", "cut", "trans")):
        return 0
    if any(k in cn or k in tn for k in ("nhấn", "accent", "hero", "ui", "đồ hoạ", "đồ họa", "card", "pop", "text")):
        return 5
    return 0


def sanitize_spec(
    raw_spec: dict[str, Any],
    spec_dir: Path,
    work_dir: Path,
    portable_root: Path | None = None,
    auto_sfx_dir: Path | None = None,
    enable_c8_guard: bool = True,
    optimize_bgm_offset: bool = False,
    vocal_chest_warmth: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Gate 1: Mechanical Pre-Flight Sanitizer + `meta.bgm_stops` Silence Vacuum Carver
            + Optional `+2.2 dB @ 185Hz` Vocal Chest Warmth + Acoustic `lag_ms` Peak-on-Cut Aligner
            + MD5 Dedup + Optional `optimize_bgm_offset` Steady-State Selector.
    100% aesthetic-agnostic physics only: never alters typography, colors, visual coordinates, or camera.
    """
    spec = copy.deepcopy(raw_spec)
    # Extract & strip optional compiler metadata block so `fc_build_fast.py` never flags unsupported top-level key
    popped_meta = spec.pop("meta", None)
    raw_meta: dict[str, Any] = popped_meta if isinstance(popped_meta, dict) else {}
    top_bgm_stops = spec.pop("bgm_stops", None)
    top_micro_bridges = spec.pop("micro_bridges", None)
    top_transition_style = spec.pop("transition_style", None)
    spec.pop("industry_skin", None)
    spec.pop("format_mode", None)
    spec.pop("enamel_gum_bbox", None)
    spec.pop("macro_subject_bbox", None)
    spec.pop("cranial_zone", None)

    fps = float(spec.get("fps", 30.0))
    tracks = spec.get("tracks", [])

    stats: dict[str, Any] = {
        "fps": fps,
        "snapped_clips": 0,
        "eof_clamped_clips": [],
        "c8_trimmed_clips": [],
        "persistent_text_bridges_preserved": [],
        "same_track_trimmed_clips": [],
        "sanitized_keyframe_lists": 0,
        "auto_allocated_sfx": [],
        "raw_sfx_tokens": [],
        "v70_clip_annotations": [],
        "typo_kinetic_annotations": [],
        "micro_bridges_planned": [],
        "md5_dedup_skipped": 0,
        "sfx_acoustic_profiles_measured": 0,
        "lag_ms_aligned_count": 0,
        "lag_ms_aligned_clips": [],
        "bgm_offset_optimizations": [],
        "bgm_stops_requested": [],
        "bgm_stops_carved_count": 0,
        "bgm_stops_carved_details": [],
        "vocal_chest_warmth": {
            **VOCAL_CHEST_WARMTH_DEFAULT,
            "enabled": False,
            "applied_clips": 0,
        },
        "speech_micro_fades_count": 0,
        "speech_micro_fades_polished": [],
    }

    # Sequence duration snap (infer early so BGM & SFX clamping know exact timeline end)
    v1_track = next(
        (t for t in tracks if t.get("type") == "video" and str(t.get("name", "")).startswith("V1")),
        None,
    ) or next((t for t in tracks if t.get("type") == "video"), None)

    if _is_num(spec.get("duration")) and float(spec["duration"]) > 0:
        spec["duration"] = _snap(float(spec["duration"]), fps)
    else:
        max_end = max(
            (float(c.get("at", 0.0)) + float(c.get("dur", 0.0)) for t in tracks for c in t.get("clips", [])),
            default=1.0,
        )
        spec["duration"] = _snap(max_end, fps)
    seq_dur = float(spec["duration"])

    # Collect already-used explicit SFX files (paths, basenames, AND MD5 hashes!)
    used_sfx_keys: set[str] = set()
    used_sfx_md5s: set[str] = set()
    has_auto_sfx = False

    for tr in tracks:
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            s = str(cl.get("src") or "")
            if s.upper().startswith("AUTO:"):
                has_auto_sfx = True
            elif s:
                resolved = resolve_clip_src(s, spec_dir, portable_root, work_dir)
                cl["src"] = resolved
                rp = Path(resolved)
                if rp.suffix.lower() in AUDIO_EXT:
                    used_sfx_keys.add(str(rp.resolve()).casefold())
                    used_sfx_keys.add(rp.name.casefold())
                    if classify_audio_role(tname, cl) == "sfx" and rp.is_file():
                        prof = measure_sfx_acoustic_profile(str(rp))
                        if prof:
                            stats["sfx_acoustic_profiles_measured"] += 1
                            used_sfx_md5s.add(prof["md5"])

    sfx_candidates: list[Path] = []
    if has_auto_sfx:
        search_sfx_dir = auto_sfx_dir
        if search_sfx_dir is None:
            for cand_dir in [
                portable_root / "assets" / "sfx" if portable_root else None,
                spec_dir / "assets" / "sfx",
                work_dir / "assets" / "sfx",
            ]:
                if cand_dir is not None and cand_dir.is_dir():
                    search_sfx_dir = cand_dir
                    break
        if search_sfx_dir is None or not search_sfx_dir.is_dir():
            raise RuntimeError(
                "Spec contains `src: 'AUTO:<keyword>'` SFX clips, but `--auto-sfx-dir` was not provided "
                "and no `assets/sfx/` folder was found."
            )
        sfx_candidates = sorted(
            p.resolve()
            for p in search_sfx_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXT
        )

    def allocate_auto_sfx(spec_token: str, clip_name: str) -> tuple[Path, dict[str, Any]]:
        kw_raw = spec_token.split(":", 1)[1].strip()
        kws = [k.strip().lower() for k in re.split(r"[,|/;+\s]+", kw_raw) if k.strip() and k.strip().lower() != "any"]

        def _is_valid_unused(cand: Path) -> tuple[bool, dict[str, Any] | None]:
            if str(cand).casefold() in used_sfx_keys or cand.name.casefold() in used_sfx_keys:
                return False, None
            prof = measure_sfx_acoustic_profile(str(cand))
            if prof is None or prof["dur_s"] < 0.10 or not prof["has_signal"]:
                return False, None
            if prof["md5"] in used_sfx_md5s:
                stats["md5_dedup_skipped"] += 1
                return False, None
            return True, prof

        for kw in kws:
            for cand in sfx_candidates:
                haystack = f"{cand.parent.name}/{cand.name}".lower()
                if kw in haystack:
                    ok, prof = _is_valid_unused(cand)
                    if ok and prof is not None:
                        used_sfx_keys.add(str(cand).casefold())
                        used_sfx_keys.add(cand.name.casefold())
                        used_sfx_md5s.add(prof["md5"])
                        stats["sfx_acoustic_profiles_measured"] += 1
                        return cand, prof

        for cand in sfx_candidates:
            ok, prof = _is_valid_unused(cand)
            if ok and prof is not None:
                used_sfx_keys.add(str(cand).casefold())
                used_sfx_keys.add(cand.name.casefold())
                used_sfx_md5s.add(prof["md5"])
                stats["sfx_acoustic_profiles_measured"] += 1
                return cand, prof

        raise RuntimeError(
            f"Auto-SFX allocator exhausted unique MD5-deduplicated SFX files (>=0.10s) in {auto_sfx_dir} "
            f"for clip '{clip_name}' ({spec_token})"
        )

    # 1a + 1b + 1c: Auto-SFX resolution, Peak-on-Cut `lag_ms` alignment, BGM steady-state offset, & EOF clamping
    for tr_idx_san, tr in enumerate(tracks):
        ttype = tr.get("type", "")
        tname = str(tr.get("name", ""))
        clips = tr.get("clips", [])
        if ttype == "audio" and len(clips) >= 2:
            clips.sort(key=lambda c: float(c.get("at", 0.0)))

        prev_track_end_s = 0.0
        persistent_bridge_ids: set[int] = set()
        for idx_c, cl in enumerate(clips):
            raw_src = str(cl.get("src") or "")
            if raw_src:
                stats["raw_sfx_tokens"].append(
                    {
                        "track": tname,
                        "clip": str(cl.get("name") or ""),
                        "raw_src": raw_src,
                        "at": float(cl.get("at", 0.0)),
                    }
                )
            # Extract & strip v7.0 / v7.1 clip annotations (`typo_kinetic_meta` + sidecar `.typo_meta.json`)
            # so `fc_build_fast.py` never flags unsupported keys while Gate 3B/3C & Cranial Audit retain full metadata!
            v70_ann: dict[str, Any] = {}
            for ann_k in (
                "persistent_bridge",
                "z_plane",
                "transition_style",
                "enamel_gum_bbox",
                "macro_subject_bbox",
                "hair_top_y",
                "chin_y",
                "face_bbox",
            ):
                if ann_k in cl:
                    v70_ann[ann_k] = cl.pop(ann_k)

            inline_tkm = cl.pop("typo_kinetic_meta", None)
            extra_tkm_keys: dict[str, Any] = {}
            for tk_field in (
                "layout_silhouette",
                "entrance_style",
                "has_pill_badge",
                "badge_text",
                "ink_bbox_screen",
                "plate_width",
                "plate_height",
                "allow_static_thumbnail",
            ):
                if tk_field in cl:
                    extra_tkm_keys[tk_field] = cl.pop(tk_field)

            sidecar_tkm = _load_sidecar_typo_meta(raw_src, spec_dir=spec_dir) if raw_src else None
            merged_tkm: dict[str, Any] | None = None
            if isinstance(inline_tkm, dict) or isinstance(sidecar_tkm, dict) or extra_tkm_keys:
                merged_tkm = {
                    **(sidecar_tkm if isinstance(sidecar_tkm, dict) else {}),
                    **(inline_tkm if isinstance(inline_tkm, dict) else {}),
                    **extra_tkm_keys,
                }
                if "z_plane" in v70_ann and "z_plane" not in merged_tkm:
                    merged_tkm["z_plane"] = v70_ann["z_plane"]
                elif "z_plane" in merged_tkm and "z_plane" not in v70_ann:
                    v70_ann["z_plane"] = merged_tkm["z_plane"]
                v70_ann["typo_kinetic_meta"] = merged_tkm
                stats["typo_kinetic_annotations"].append(
                    {
                        "track_index": tr_idx_san,
                        "track": tname,
                        "track_type": ttype,
                        "clip": str(cl.get("name") or cl.get("text") or ""),
                        "src": raw_src,
                        "at": round(float(cl.get("at", 0.0)), 4),
                        "dur": round(float(cl.get("dur", 0.5)), 4),
                        "z_plane": str(merged_tkm.get("z_plane") or v70_ann.get("z_plane") or "foreground"),
                        "typo_kinetic_meta": merged_tkm,
                    }
                )

            if v70_ann.get("persistent_bridge") is True or "· bridge" in str(cl.get("name") or "").lower():
                persistent_bridge_ids.add(id(cl))
                v70_ann["persistent_bridge"] = True

            # Intercept v7.0 virtual micro-bridges placed in `transition_in` / `transition_out`
            for tr_edge in ("transition_in", "transition_out"):
                tr_obj = cl.get(tr_edge)
                if isinstance(tr_obj, dict):
                    fx_raw = str(tr_obj.get("effect") or tr_obj.get("style") or "").strip().lower()
                    if fx_raw in V70_MICRO_BRIDGE_ALIASES:
                        popped_tr = cl.pop(tr_edge)
                        c_at_e = float(cl.get("at", 0.0))
                        c_dur_e = float(cl.get("dur", 0.0))
                        cut_e = c_at_e if tr_edge == "transition_in" else (c_at_e + c_dur_e)
                        stats["micro_bridges_planned"].append(
                            {
                                "type": V70_MICRO_BRIDGE_ALIASES[fx_raw],
                                "at": round(cut_e, 4),
                                "frames": popped_tr.get("frames"),
                                "peak_ev": popped_tr.get("peak_ev", 1.55),
                                "max_sigma": popped_tr.get("max_sigma", 14.0),
                                "source": f"{tname}:{tr_edge}",
                            }
                        )

            if v70_ann.get("transition_style"):
                ts_raw = str(v70_ann["transition_style"]).strip().lower()
                if ts_raw in V70_MICRO_BRIDGE_ALIASES:
                    stats["micro_bridges_planned"].append(
                        {
                            "type": V70_MICRO_BRIDGE_ALIASES[ts_raw],
                            "at": round(float(cl.get("at", 0.0)), 4),
                            "peak_ev": 1.55,
                            "max_sigma": 14.0,
                            "source": f"{tname}:clip.transition_style",
                        }
                    )

            if v70_ann:
                stats["v70_clip_annotations"].append(
                    {
                        "track": tname,
                        "clip": str(cl.get("name") or cl.get("text") or ""),
                        "at": round(float(cl.get("at", 0.0)), 4),
                        "dur": round(float(cl.get("dur", 0.5)), 4),
                        **v70_ann,
                    }
                )

            was_auto_sfx = raw_src.upper().startswith("AUTO:")
            sfx_prof: dict[str, Any] | None = None

            if was_auto_sfx:
                chosen, sfx_prof = allocate_auto_sfx(raw_src, cl.get("name", "SFX"))
                cl["src"] = str(chosen)
                stats["auto_allocated_sfx"].append(
                    {
                        "clip": cl.get("name", "SFX"),
                        "token": raw_src,
                        "resolved": str(chosen),
                        "md5": sfx_prof["md5"],
                        "lag_ms": sfx_prof["lag_ms"],
                    }
                )

            if ttype == "audio" and cl.get("src"):
                ensure_audio_role_tag(tr, cl)

            role = classify_audio_role(tname, cl) if ttype == "audio" else None
            has_explicit_sync = _is_num(cl.get("sync_peak_at"))
            explicit_sync_peak = float(cl.pop("sync_peak_at")) if has_explicit_sync else None
            explicit_sync_frame_off = int(round(float(cl.pop("sync_frame_offset", 0)))) if "sync_frame_offset" in cl else None

            if "at" in cl:
                old_at = float(cl["at"])
                new_at = max(0.0, _snap(old_at, fps))
                if abs(new_at - old_at) > 1e-7:
                    stats["snapped_clips"] += 1
                cl["at"] = new_at

            if "dur" in cl:
                old_dur = float(cl["dur"])
                new_dur = max(_snap(1.0 / fps, fps), _snap(old_dur, fps))
                if abs(new_dur - old_dur) > 1e-7:
                    stats["snapped_clips"] += 1
                cl["dur"] = new_dur

            # Peak-on-Cut `lag_ms` SFX Alignment
            if ttype == "audio" and role == "sfx" and (has_explicit_sync or was_auto_sfx) and cl.get("src"):
                if sfx_prof is None:
                    sfx_prof = measure_sfx_acoustic_profile(str(cl["src"]))
                    if sfx_prof is not None:
                        stats["sfx_acoustic_profiles_measured"] += 1

                if sfx_prof is not None and sfx_prof["dur_s"] > 0:
                    orig_at = float(cl.get("at", 0.0))
                    orig_in = max(0.0, float(cl.get("in", 0.0)))
                    cname = str(cl.get("name", "SFX"))
                    is_frame0_opener = ("mở đầu" in cname.lower()) and orig_at <= 0.04

                    if explicit_sync_peak is not None:
                        f_off = explicit_sync_frame_off if explicit_sync_frame_off is not None else 0
                        target_peak_s = max(0.0, explicit_sync_peak + f_off / fps)
                    else:
                        f_off = explicit_sync_frame_off if explicit_sync_frame_off is not None else (_infer_sfx_sync_frame_offset(tname, cname) or 0)
                        target_peak_s = 0.0 if is_frame0_opener else max(0.0, orig_at + f_off / fps)

                    target_peak_s = min(target_peak_s, max(0.0, seq_dur - 2.0 / fps))
                    lag_s = float(sfx_prof["lag_s"])
                    fdur_sfx = float(sfx_prof["dur_s"])
                    desired_at = target_peak_s - lag_s

                    # Maximum lead before target_peak_s without going < 0, overlapping prev clip on track, or > 220ms
                    avail_lead = max(0.0, target_peak_s - prev_track_end_s)
                    max_lead_s = 0.0 if is_frame0_opener else min(0.220, avail_lead)

                    if desired_at < 0.0 or lag_s > 0.220 or desired_at < prev_track_end_s - 1e-6:
                        new_in = max(orig_in, lag_s - max_lead_s)
                    else:
                        new_in = orig_in

                    min_req_dur = min(fdur_sfx, 0.30 if is_frame0_opener else (2.0 / fps))
                    max_safe_in = max(0.0, fdur_sfx - min_req_dur - 1e-4)
                    new_in = round(min(new_in, max_safe_in), 4)
                    eff_lead_s = max(0.0, lag_s - new_in)

                    aligned_at = 0.0 if is_frame0_opener else max(prev_track_end_s, _snap(target_peak_s - eff_lead_s, fps))
                    cl["in"] = new_in
                    cl["at"] = aligned_at
                    stats["lag_ms_aligned_count"] += 1
                    stats["lag_ms_aligned_clips"].append(
                        {
                            "track": tname,
                            "clip": cname,
                            "lag_ms": sfx_prof["lag_ms"],
                            "sync_frame_offset": f_off,
                            "target_peak_s": round(target_peak_s, 4),
                            "old_at": round(orig_at, 4),
                            "new_at": aligned_at,
                            "new_in": new_in,
                        }
                    )

            # BGM Steady-State Offset Selector (`optimize_bgm_offset`)
            if (
                optimize_bgm_offset
                and ttype == "audio"
                and role == "bgm"
                and cl.get("src")
                and abs(float(cl.get("in", 0.0))) <= 1e-4
            ):
                bgm_p = Path(str(cl["src"]))
                if bgm_p.is_file():
                    bgm_fdur = probe_media_duration(str(bgm_p))
                    bgm_cdur = float(cl.get("dur", seq_dur))
                    if bgm_fdur is not None and bgm_fdur > bgm_cdur + 10.0:
                        opt_res = select_steady_state_bgm_offset(bgm_p, bgm_cdur, bgm_fdur, fps)
                        if opt_res["changed"]:
                            cl["in"] = opt_res["selected_in_s"]
                        stats["bgm_offset_optimizations"].append(
                            {
                                "clip": cl.get("name", bgm_p.name),
                                "src": bgm_p.name,
                                **opt_res,
                            }
                        )

            # Strict EOF clamping on finite media files
            src_str = cl.get("src")
            if src_str and not cl.get("loop"):
                src_p = Path(src_str)
                if src_p.is_file() and src_p.suffix.lower() in MEDIA_EXT:
                    fdur = sfx_prof["dur_s"] if sfx_prof is not None else probe_media_duration(str(src_p))
                    if fdur is not None and fdur > 0:
                        raw_spd = float(cl.get("speed", 1.0))
                        spd_factor = raw_spd / 100.0 if raw_spd > 10.0 else raw_spd
                        spd_factor = max(0.01, spd_factor)
                        src_in = max(0.0, float(cl.get("in", 0.0)))
                        min_clip_dur = _snap(1.0 / fps, fps)

                        if src_in >= fdur - (min_clip_dur * spd_factor):
                            src_in = max(0.0, round(fdur - min(cl.get("dur", min_clip_dur) * spd_factor, fdur), 4))
                            cl["in"] = src_in

                        cur_dur = float(cl.get("dur", min_clip_dur))
                        # Also clamp against timeline end for SFX so cues never hang past sequence markOut
                        if role == "sfx" and float(cl.get("at", 0.0)) + cur_dur > seq_dur:
                            cur_dur = max(min_clip_dur, _snap(seq_dur - float(cl.get("at", 0.0)), fps))
                            cl["dur"] = cur_dur

                        if src_in + cur_dur * spd_factor > fdur + 1e-4:
                            avail_timeline_s = max(0.0, (fdur - src_in) / spd_factor)
                            safe_frames = max(1, math.floor(avail_timeline_s * fps + 1e-5))
                            clamped_dur = round(safe_frames / fps, 6)
                            while safe_frames > 1 and (src_in + clamped_dur * spd_factor > fdur + 1e-4):
                                safe_frames -= 1
                                clamped_dur = round(safe_frames / fps, 6)
                            cl["dur"] = clamped_dur
                            stats["eof_clamped_clips"].append(
                                {
                                    "track": tname,
                                    "clip": cl.get("name", src_p.name),
                                    "old_dur": round(cur_dur, 4),
                                    "new_dur": clamped_dur,
                                    "in": round(src_in, 4),
                                    "file_dur": round(fdur, 4),
                                }
                            )

            # Prevent intra-track collision (including 1e-6 6-decimal rounding residue!) with next clip
            c_at_now = float(cl.get("at", 0.0))
            c_dur_now = float(cl.get("dur", 0.0))
            if idx_c + 1 < len(clips):
                nxt_orig_at = _snap(float(clips[idx_c + 1].get("at", seq_dur)), fps)
                if nxt_orig_at > c_at_now + (1.0 / fps) and c_at_now + c_dur_now > nxt_orig_at:
                    c_dur_now = max(_snap(1.0 / fps, fps), _snap(nxt_orig_at - c_at_now, fps))
                    if c_at_now + c_dur_now > nxt_orig_at:
                        c_dur_now = round(nxt_orig_at - c_at_now, 6)
                    cl["dur"] = c_dur_now
            if ttype == "audio":
                prev_track_end_s = max(prev_track_end_s, c_at_now + c_dur_now)

    # Flush disk acoustic cache if new SFX files were profiled
    _flush_disk_sfx_cache()

    # Snap markers into [0.0, seq_dur]
    for mk in spec.get("markers") or []:
        if isinstance(mk, dict) and _is_num(mk.get("at")):
            mk["at"] = max(0.0, min(seq_dur, _snap(float(mk["at"]), fps)))

    # 1d: C8 Cut-Boundary Guard (trims main text clips ending 1..12 frames past a V1 cut back to cut_t - 1/fps;
    #     v7.0 EXEMPT: intentional `persistent_bridge` clips (`apply_persistent_text_bridge`) hold across cuts!)
    cut_ts: list[float] = []
    if v1_track and v1_track.get("clips"):
        v1_sorted = sorted(v1_track["clips"], key=lambda c: float(c.get("at", 0.0)))
        cut_ts = [float(b["at"]) for a, b in zip(v1_sorted, v1_sorted[1:]) if float(b["at"]) > 0.05]

    persistent_ann_keys = {
        (a["track"], round(float(a["at"]), 3), a["clip"])
        for a in stats["v70_clip_annotations"]
        if a.get("persistent_bridge") is True
    }

    if enable_c8_guard and cut_ts:
        one_frame = 1.0 / fps
        for tr in tracks:
            tname = str(tr.get("name", ""))
            if _lane(tname).lower() not in MAIN_TEXT_LANES:
                continue
            for cl in tr.get("clips", []):
                if not (_is_num(cl.get("at")) and _is_num(cl.get("dur"))):
                    continue
                c_at = float(cl["at"])
                c_dur = float(cl["dur"])
                c_end = c_at + c_dur
                cname_c = str(cl.get("name") or cl.get("text") or "")
                is_pbridge = (
                    (id(cl) in persistent_bridge_ids)
                    or ("· bridge" in cname_c.lower())
                    or ((tname, round(c_at, 3), cname_c) in persistent_ann_keys)
                )
                nearest_cut = min(cut_ts, key=lambda ct: abs(c_end - ct))
                overrun_frames = (c_end - nearest_cut) * fps
                if is_pbridge and 1e-3 < overrun_frames <= 18.0:
                    stats["persistent_text_bridges_preserved"].append(
                        {
                            "track": tname,
                            "clip": cname_c[:28],
                            "cut_at": nearest_cut,
                            "hold_across_frames": round(overrun_frames, 2),
                        }
                    )
                    continue
                if 1e-3 < overrun_frames <= 12.0 + 1e-3 and c_at < nearest_cut - max(0.15, 3.0 * one_frame):
                    new_end = _snap(nearest_cut - one_frame, fps)
                    new_dur = _snap(new_end - c_at, fps)
                    if new_dur >= _snap(3.0 * one_frame, fps):
                        cl["dur"] = new_dur
                        stats["c8_trimmed_clips"].append(
                            {
                                "track": tname,
                                "clip": cl.get("name", cl.get("text", "?"))[:28],
                                "cut_at": nearest_cut,
                                "old_end": round(c_end, 4),
                                "new_end": new_end,
                                "overrun_frames": round(overrun_frames, 2),
                            }
                        )

    # 1d_bis (v7.0): Collect & normalize `meta.micro_bridges` / `transition_style` AdjustmentLayer requests
    raw_mb_sources = [
        raw_meta.get("micro_bridges"),
        top_micro_bridges,
    ]
    for mb_src in raw_mb_sources:
        if isinstance(mb_src, list):
            for item in mb_src:
                if isinstance(item, dict):
                    b_raw = str(
                        item.get("type") or item.get("style") or item.get("bridge") or item.get("effect") or ""
                    ).strip().lower()
                    t_raw = item.get("at") if _is_num(item.get("at")) else (
                        item.get("cut_at") if _is_num(item.get("cut_at")) else item.get("time")
                    )
                    if b_raw in V70_MICRO_BRIDGE_ALIASES and _is_num(t_raw):
                        stats["micro_bridges_planned"].append(
                            {
                                "type": V70_MICRO_BRIDGE_ALIASES[b_raw],
                                "at": _snap(float(t_raw), fps),
                                "frames": item.get("frames"),
                                "peak_ev": float(item.get("peak_ev", 1.55)),
                                "max_sigma": float(item.get("max_sigma", 14.0)),
                                "source": "meta.micro_bridges",
                            }
                        )
        elif isinstance(mb_src, str) and mb_src.strip().lower() in V70_MICRO_BRIDGE_ALIASES:
            b_canon = V70_MICRO_BRIDGE_ALIASES[mb_src.strip().lower()]
            for ct in cut_ts:
                stats["micro_bridges_planned"].append(
                    {
                        "type": b_canon,
                        "at": _snap(ct, fps),
                        "frames": None,
                        "peak_ev": 1.55,
                        "max_sigma": 14.0,
                        "source": "meta.micro_bridges(string)",
                    }
                )

    seq_trans_style = raw_meta.get("transition_style") or top_transition_style
    if isinstance(seq_trans_style, str) and seq_trans_style.strip().lower() in V70_MICRO_BRIDGE_ALIASES:
        b_canon = V70_MICRO_BRIDGE_ALIASES[seq_trans_style.strip().lower()]
        covered_ts = {float(m["at"]) for m in stats["micro_bridges_planned"]}
        for ct in cut_ts:
            if not any(abs(ct - ex_t) <= (2.0 / fps) for ex_t in covered_ts):
                stats["micro_bridges_planned"].append(
                    {
                        "type": b_canon,
                        "at": _snap(ct, fps),
                        "frames": None,
                        "peak_ev": 1.55,
                        "max_sigma": 14.0,
                        "source": "meta.transition_style",
                    }
                )
    elif isinstance(seq_trans_style, list):
        valid_styles = [
            V70_MICRO_BRIDGE_ALIASES[str(s).strip().lower()]
            for s in seq_trans_style
            if str(s).strip().lower() in V70_MICRO_BRIDGE_ALIASES
        ]
        if valid_styles:
            covered_ts = {float(m["at"]) for m in stats["micro_bridges_planned"]}
            for idx_ct, ct in enumerate(cut_ts):
                if not any(abs(ct - ex_t) <= (2.0 / fps) for ex_t in covered_ts):
                    stats["micro_bridges_planned"].append(
                        {
                            "type": valid_styles[idx_ct % len(valid_styles)],
                            "at": _snap(ct, fps),
                            "frames": None,
                            "peak_ev": 1.55,
                            "max_sigma": 14.0,
                            "source": "meta.transition_style(list)",
                        }
                    )

    # Deduplicate micro_bridges_planned by timestamp (within 1.5 frames)
    dedup_mb: list[dict[str, Any]] = []
    for mb in sorted(stats["micro_bridges_planned"], key=lambda x: float(x["at"])):
        mb_t = float(mb["at"])
        if mb_t <= 0.02 or mb_t >= seq_dur - (1.0 / fps):
            continue
        if dedup_mb and abs(mb_t - float(dedup_mb[-1]["at"])) <= (1.5 / fps):
            dedup_mb[-1] = mb
        else:
            dedup_mb.append(mb)
    stats["micro_bridges_planned"] = dedup_mb

    # 1e: Same-track micro-overlap guard (zero intra-track overlap across ALL tracks)
    for tr in tracks:
        tname = str(tr.get("name", ""))
        clips = tr.get("clips", [])
        if len(clips) < 2:
            continue
        clips.sort(key=lambda c: float(c.get("at", 0.0)))
        for idx_pair in range(len(clips) - 1):
            a = clips[idx_pair]
            b = clips[idx_pair + 1]
            a_at, a_dur = float(a.get("at", 0.0)), float(a.get("dur", 0.0))
            b_at = float(b.get("at", 0.0))
            if b_at < a_at + (1.0 / fps) - 1e-6:
                b_at = _snap(a_at + (1.0 / fps), fps)
                b["at"] = b_at
            if (a_at + a_dur) > b_at + 1e-6:
                new_dur = max(_snap(1.0 / fps, fps), _snap(b_at - a_at, fps))
                stats["same_track_trimmed_clips"].append(
                    {
                        "track": tname,
                        "clip": a.get("name", "?")[:28],
                        "old_dur": round(a_dur, 4),
                        "new_dur": new_dur,
                        "next_at": b_at,
                    }
                )
                a["dur"] = new_dur

    # 1e_bis (v5.2): Auto-polish speech clip micro-fades (`fade_in >= 0.018s`, `fade_out >= 0.022s` when unbridged)
    # Converts raw `fade_in` / `fade_out` hints (and unbridged speech cuts) into frame-aligned `volume.level`
    # `gain_db` micro-ramps so speech cuts never click or pop and `fc_build_fast.py` sees 0 unsupported keys.
    raw_fade_hints: dict[int, tuple[float, float]] = {}
    voice_spans: list[tuple[str, float, float, dict[str, Any]]] = []
    for tr in tracks:
        ttype = tr.get("type", "")
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            fi_hint = float(cl.pop("fade_in", 0.0) or 0.0) if "fade_in" in cl else 0.0
            fo_hint = float(cl.pop("fade_out", 0.0) or 0.0) if "fade_out" in cl else 0.0
            if fi_hint > 0.0 or fo_hint > 0.0:
                raw_fade_hints[id(cl)] = (fi_hint, fo_hint)
            if ttype == "audio" and cl.get("src") and classify_audio_role(tname, cl) == "voice":
                c_at_v = float(cl.get("at", 0.0))
                c_dur_v = float(cl.get("dur", 0.0))
                voice_spans.append((tname, c_at_v, c_at_v + c_dur_v, cl))

    for tname, c_at_v, c_end_v, cl in voice_spans:
        c_dur_v = round(c_end_v - c_at_v, 6)
        fi_hint, fo_hint = raw_fade_hints.get(id(cl), (0.0, 0.0))
        req_fi = max(fi_hint, 0.018)
        req_fo = max(fo_hint, 0.022)
        fi_frames = max(1, math.ceil((req_fi - 1e-6) * fps))
        fo_frames = max(1, math.ceil((req_fo - 1e-6) * fps))
        if round(c_dur_v * fps) < (fi_frames + fo_frames + 2):
            continue
        fi_s = round(fi_frames / fps, 6)
        fo_s = round(fo_frames / fps, 6)

        start_bridged = bool(cl.get("transition_in")) or any(
            (o_cl is not cl) and (o_at < c_at_v - 1e-4) and (o_end > c_at_v + 0.008)
            for _, o_at, o_end, o_cl in voice_spans
        )
        end_bridged = bool(cl.get("transition_out")) or any(
            (o_cl is not cl) and (o_at < c_end_v - 0.008) and (o_end > c_end_v + 1e-4)
            for _, o_at, o_end, o_cl in voice_spans
        )

        g_cur = cl.get("gain_db", 0.0)
        polished_fi_s = 0.0
        polished_fo_s = 0.0

        if _is_animated_kf_list(g_cur):
            g_sorted = sorted(g_cur, key=lambda k: float(k[0]))
            peak_db = max(float(k[1]) for k in g_sorted)
            has_fi = (float(g_sorted[0][1]) <= peak_db - 12.0) and (
                len(g_sorted) >= 2 and float(g_sorted[1][0]) >= 0.018 - 1e-4
            )
            has_fo = (float(g_sorted[-1][1]) <= peak_db - 12.0) and (
                len(g_sorted) >= 2 and (c_dur_v - float(g_sorted[-2][0])) >= 0.022 - 1e-4
            )
            need_fi = (not start_bridged) and (not has_fi)
            need_fo = (not end_bridged) and (not has_fo)
            if need_fi or need_fo:
                lo_bound = (fi_s + 0.5 / fps) if need_fi else -1.0
                hi_bound = (c_dur_v - fo_s - 0.5 / fps) if need_fo else (c_dur_v + 1.0)
                mid_keys = [list(k) for k in g_sorted if lo_bound < float(k[0]) < hi_bound]
                first_plat = round(float(mid_keys[0][1] if mid_keys else peak_db), 2)
                last_plat = round(float(mid_keys[-1][1] if mid_keys else peak_db), 2)
                rebuilt: list[list[Any]] = []
                if need_fi:
                    rebuilt.append([0.0, round(first_plat - 36.0, 2), "easeOut"])
                    rebuilt.append([fi_s, first_plat, "linear"])
                    polished_fi_s = fi_s
                elif g_sorted:
                    rebuilt.extend([list(k) for k in g_sorted if float(k[0]) <= lo_bound or not need_fi][:2 if has_fi else 1])
                for mk in mid_keys:
                    if not rebuilt or float(mk[0]) > float(rebuilt[-1][0]) + 0.5 / fps:
                        rebuilt.append(mk)
                if need_fo:
                    rebuilt.append([round(c_dur_v - fo_s, 6), last_plat, "easeIn"])
                    rebuilt.append([round(c_dur_v, 6), round(last_plat - 36.0, 2)])
                    polished_fo_s = fo_s
                elif not rebuilt or float(g_sorted[-1][0]) > float(rebuilt[-1][0]) + 0.5 / fps:
                    rebuilt.append(list(g_sorted[-1]))
                cl["gain_db"] = rebuilt
        elif _is_num(g_cur) or g_cur is None:
            if (not start_bridged) or (not end_bridged):
                base_db = round(float(0.0 if g_cur is None else g_cur), 2)
                floor_db = round(base_db - 36.0, 2)
                rebuilt_s: list[list[Any]] = []
                if not start_bridged:
                    rebuilt_s.append([0.0, floor_db, "easeOut"])
                    rebuilt_s.append([fi_s, base_db, "linear"])
                    polished_fi_s = fi_s
                else:
                    rebuilt_s.append([0.0, base_db, "linear"])
                if not end_bridged:
                    rebuilt_s.append([round(c_dur_v - fo_s, 6), base_db, "easeIn"])
                    rebuilt_s.append([round(c_dur_v, 6), floor_db])
                    polished_fo_s = fo_s
                else:
                    rebuilt_s.append([round(c_dur_v, 6), base_db])
                cl["gain_db"] = rebuilt_s

        if polished_fi_s > 0.0 or polished_fo_s > 0.0:
            stats["speech_micro_fades_count"] += 1
            stats["speech_micro_fades_polished"].append(
                {
                    "track": tname,
                    "clip": str(cl.get("name", "Voice"))[:36],
                    "at": round(c_at_v, 4),
                    "dur": c_dur_v,
                    "fade_in_s": round(polished_fi_s, 4),
                    "fade_out_s": round(polished_fo_s, 4),
                    "start_bridged": start_bridged,
                    "end_bridged": end_bridged,
                }
            )

    # 1e_ter (v6.0): Carve `meta.bgm_stops` (`[[start_s, end_s], ...]`) `>= 0.50s` `-inf dB` silence vacuums
    bgm_stops_raw = raw_meta.get("bgm_stops") if raw_meta.get("bgm_stops") is not None else top_bgm_stops
    bgm_beats_raw = raw_meta.get("bgm_beats") if isinstance(raw_meta.get("bgm_beats"), list) else None
    stop_windows = _normalize_bgm_stop_windows(bgm_stops_raw, seq_dur=seq_dur, fps=fps, bgm_beats=bgm_beats_raw)
    if stop_windows:
        stats["bgm_stops_requested"] = [[round(a, 4), round(b, 4)] for a, b in stop_windows]
        carved = carve_bgm_silence_stops(tracks, stop_windows=stop_windows, fps=fps)
        stats["bgm_stops_carved_details"] = carved
        stats["bgm_stops_carved_count"] = len({(r["stop_start_s"], r["stop_end_s"]) for r in carved})

    # 1e_quater (v6.0): Optional `+2.2 dB @ 185Hz` Vocal Chest Warmth (`meta.vocal_chest_warmth` / CLI flag)
    warmth_cfg = raw_meta.get("vocal_chest_warmth")
    enable_warmth = (
        bool(vocal_chest_warmth)
        if vocal_chest_warmth is not None
        else bool(warmth_cfg)
    )
    if enable_warmth and portable_root is None:
        w_freq = float(warmth_cfg.get("freq_hz", 185.0)) if isinstance(warmth_cfg, dict) else 185.0
        w_gain = float(warmth_cfg.get("gain_db", 2.2)) if isinstance(warmth_cfg, dict) else 2.2
        w_q = float(warmth_cfg.get("q", 1.15)) if isinstance(warmth_cfg, dict) else 1.15
        w_hpf = float(warmth_cfg.get("hpf_hz", 75.0)) if isinstance(warmth_cfg, dict) else 75.0
        warmed_map: dict[str, str] = {}
        applied_warm = 0
        for tr in tracks:
            if tr.get("type") != "audio":
                continue
            tname = str(tr.get("name", ""))
            for cl in tr.get("clips", []):
                if classify_audio_role(tname, cl) != "voice" or not cl.get("src"):
                    continue
                s_orig = str(cl["src"])
                if s_orig not in warmed_map:
                    w_out = apply_vocal_chest_warmth_185hz(
                        Path(s_orig),
                        work_dir=work_dir,
                        gain_db=w_gain,
                        freq_hz=w_freq,
                        q_val=w_q,
                        hpf_hz=w_hpf,
                    )
                    if w_out is not None:
                        warmed_map[s_orig] = str(w_out)
                if s_orig in warmed_map:
                    cl["src"] = warmed_map[s_orig]
                    applied_warm += 1
        stats["vocal_chest_warmth"] = {
            "freq_hz": w_freq,
            "gain_db": w_gain,
            "q": w_q,
            "hpf_hz": w_hpf,
            "enabled": True,
            "applied_clips": applied_warm,
        }

    # 1f: Keyframe Monotonicity & [0.0, dur] Bounds Guard (runs after all duration adjustments!)
    for tr in tracks:
        for cl in tr.get("clips", []):
            c_dur = float(cl.get("dur", 5.0))
            stats["sanitized_keyframe_lists"] += walk_and_sanitize_keyframes(cl, c_dur, fps)

    return spec, stats


def adjust_spec_audio_gains(
    spec_path: Path,
    delta_voice_db: float,
    delta_sfx_db: float,
    delta_bgm_db: float | None = None,
) -> None:
    """Shift scalar OR keyframe-list `gain_db` on audio tracks cleanly."""
    bgm_d = delta_voice_db if delta_bgm_db is None else delta_bgm_db
    doc = json.loads(spec_path.read_text(encoding="utf-8"))
    for tr in doc.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            if "src" not in cl:
                continue
            role = classify_audio_role(tname, cl) or "sfx"
            delta = delta_sfx_db if role == "sfx" else (bgm_d if role == "bgm" else delta_voice_db)
            g = cl.get("gain_db", 0.0)
            if _is_animated_kf_list(g):
                cl["gain_db"] = [[k[0], round(float(k[1]) + delta, 2), *k[2:]] for k in g]
            elif _is_num(g):
                cl["gain_db"] = round(float(g) + delta, 2)
    spec_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_fcproj_audio_gains(
    fcproj_path: Path,
    delta_voice_db: float,
    delta_sfx_db: float,
    delta_bgm_db: float | None = None,
) -> None:
    """
    Fast in-place `.fcproj` audio gain shifter for closed-loop pass 2:
    Shifts `gain_db` (or animated `volume.level` keyframes) directly on audio track items
    without re-building unchanged video/text tracks from scratch.
    """
    bgm_d = delta_voice_db if delta_bgm_db is None else delta_bgm_db
    if abs(delta_voice_db) <= 1e-6 and abs(delta_sfx_db) <= 1e-6 and abs(bgm_d) <= 1e-6:
        return
    doc = json.loads(fcproj_path.read_text(encoding="utf-8"))
    seq = next(
        (v["kind"]["Sequence"] for v in doc.get("project", {}).get("items", {}).values() if "Sequence" in v.get("kind", {})),
        None,
    )
    if seq is None:
        return
    for tr in seq.get("audio_tracks", []):
        tname = str(tr.get("name", ""))
        for item in tr.get("items", []):
            role = classify_audio_role(tname, {"name": item.get("name", "")}) or "sfx"
            delta = delta_sfx_db if role == "sfx" else (bgm_d if role == "bgm" else delta_voice_db)
            vol_fx = next((ef for ef in (item.get("effects") or []) if ef.get("effect") == "volume"), None)
            lvl_slot = (vol_fx.get("params") or {}).get("level") if vol_fx else None
            kfs = lvl_slot.get("keyframes") if isinstance(lvl_slot, dict) else None
            if isinstance(kfs, list) and len(kfs) > 0:
                for kf in kfs:
                    if isinstance(kf.get("value"), dict) and "Float" in kf["value"]:
                        kf["value"]["Float"] = round(float(kf["value"]["Float"]) + delta, 2)
            else:
                item["gain_db"] = round(float(item.get("gain_db") or 0.0) + delta, 2)
    fcproj_path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def present_audio_roles(spec_path: Path) -> set[str]:
    doc = json.loads(spec_path.read_text(encoding="utf-8"))
    roles: set[str] = set()
    for tr in doc.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        for cl in tr.get("clips", []):
            if cl.get("src"):
                r = classify_audio_role(str(tr.get("name", "")), cl)
                if r:
                    roles.add(r)
    return roles


def spec_bgm_has_eq_chain(spec_path: Path) -> bool:
    """Check whether any BGM clip in `spec_path` explicitly carries a notch/peaking EQ effect."""
    doc = json.loads(spec_path.read_text(encoding="utf-8"))
    for tr in doc.get("tracks", []):
        if tr.get("type") != "audio":
            continue
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            if classify_audio_role(tname, cl) == "bgm":
                for fx in cl.get("effects") or []:
                    if any(k in str(fx.get("effect", "")).lower() for k in ("eq", "equalizer", "notch")):
                        return True
    return False


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def build_effective_rules(work_dir: Path, target_lufs: float, audio_profile: str | None = None) -> Path:
    """Rules file handed to `audio_levels.py`. `audio_profile` (`studio_14`, `tiktok_loud`) overrides the ovs -16 LUFS rule
    so Gate 6 measures against the loudness the profile actually targets."""
    overrides = resolve_audio_profile(audio_profile).get("rules_override") or {}
    if not overrides and abs(target_lufs - (-16.0)) <= 1e-6:
        return DEFAULT_RULES_JSON
    rules_doc = json.loads(DEFAULT_RULES_JSON.read_text(encoding="utf-8"))
    rules_doc["params"]["audio"]["master_lufs"]["final"] = round(float(target_lufs), 2)
    if overrides:
        rules_doc["params"]["audio"] = _deep_merge(rules_doc["params"]["audio"], overrides)
        rules_doc["params"]["audio"]["master_lufs"]["final"] = round(float(target_lufs), 2)
    eff_path = work_dir / "audio_rules_effective.json"
    eff_path.write_text(json.dumps(rules_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return eff_path


def voice_delta_window(rules_path: Path, init_vb_trim: float) -> tuple[float, float]:
    """Closed-loop voice gain window keeping voice peak inside the rules' `voice_peak_dbfs` (0.08 dB inner margin).
    With the default rules (-5..-3, target -4) this is exactly `(-0.92 - init, +0.92 - init)`."""
    vp = json.loads(Path(rules_path).read_text(encoding="utf-8"))["params"]["audio"]["voice_peak_dbfs"]
    base = float(vp["target"]) + float(init_vb_trim)
    return float(vp["min"]) + 0.08 - base, float(vp["max"]) - 0.08 - base


def voice_pretrim_db(rules_path: Path, init_vb_trim: float) -> float:
    """v7.9.3: voice share of the initial pre-trim, clamped so the planned voice peak (`voice_peak_dbfs.target` + trim) stays
    inside the rules' window (0.08 dB inner margin). studio_14 asked +1.28 dB on top of the -4 dBFS plan (-2.72 > -3.0 max)."""
    lo, hi = voice_delta_window(rules_path, 0.0)
    return round(max(lo, min(hi, float(init_vb_trim))), 2)


def voice_peak_retrim_delta(
    stems_check: list[dict[str, Any]] | None,
    rules_path: Path,
    lufs: float,
    target_lufs: float,
    tol_lu: float = 0.45,
) -> float:
    """v7.9.3 post-pass-1 retrim: dB that brings a FAIL `voice_peak` stem back inside `voice_peak_dbfs` (0.08 dB inner margin),
    clamped so `lufs + delta` stays within `target_lufs +/- tol_lu` (the mix follows the voice; BGM moves with it). 0.0 = no retrim."""
    item = next((s for s in stems_check or [] if s.get("id") == "voice_peak"), None)
    if not item or item.get("status") != "FAIL" or not _is_num(item.get("value")) or not math.isfinite(float(lufs)):
        return 0.0
    vp = json.loads(Path(rules_path).read_text(encoding="utf-8"))["params"]["audio"]["voice_peak_dbfs"]
    peak = float(item["value"])
    if peak > float(vp["max"]):
        want = float(vp["max"]) - 0.08 - peak
    elif peak < float(vp["min"]):
        want = float(vp["min"]) + 0.08 - peak
    else:
        return 0.0
    lo = float(target_lufs) - tol_lu - float(lufs)
    hi = float(target_lufs) + tol_lu - float(lufs)
    return round(max(min(lo, 0.0), min(max(hi, 0.0), want)), 2)


# ==============================================================================
# [P1] Gate 5 Deep Visual Rigor (`full` mode):
#      1. Blank Render (`grayscale_std >= 10.0`) & Frozen B-Roll (`mean(|f2-f1|) >= 0.8`)
#      2. Projected `facesafe` Eye/Mouth & Safe-Zone True Glyph Ink Audit
# ==============================================================================

class HaarCascadeModel(NamedTuple):
    win: int
    feats: list[list[tuple[int, int, int, int, float]]]
    stages: list[tuple[float, list[tuple[int, float, float, float]]]]


@lru_cache(maxsize=2)
def _load_vendored_haar(xml_path_str: str) -> HaarCascadeModel:
    """Parse OpenCV Haar cascade XML for vectorized `cv2.integral` Viola-Jones (works on OpenCV 5.0!)."""
    root = ET.parse(xml_path_str).getroot().find("cascade")
    if root is None:
        raise ValueError(f"Invalid Haar XML: {xml_path_str}")
    win = int(root.findtext("width") or "24")
    features_el = root.find("features")
    feats = [
        [
            (int(x), int(y), int(w), int(h), float(wt))
            for x, y, w, h, wt in (r.text.split() for r in (f.find("rects") if f.find("rects") is not None else []))
        ]
        for f in (features_el if features_el is not None else [])
    ]
    stages: list[tuple[float, list[tuple[int, float, float, float]]]] = []
    stages_el = root.find("stages")
    for st in (stages_el if stages_el is not None else []):
        weak: list[tuple[int, float, float, float]] = []
        weak_el = st.find("weakClassifiers")
        for wc in (weak_el if weak_el is not None else []):
            node = (wc.findtext("internalNodes") or "").split()
            leaf = (wc.findtext("leafValues") or "").split()
            weak.append((int(node[2]), float(node[3]), float(leaf[0]), float(leaf[1])))
        stages.append((float(st.findtext("stageThreshold") or "0.0"), weak))
    return HaarCascadeModel(win=win, feats=feats, stages=stages)


def detect_frontal_faces_1080p(png_paths: list[Path]) -> list[tuple[float, float, float, float] | None]:
    """
    Detect primary frontal face bounding box `(x0, y0, x1, y1)` in `1080x1920` coordinates
    across a batch of PNGs using `cv2.CascadeClassifier` if available, else vectorized
    `thlib/face.py` Viola-Jones on vendored `data/haarcascade_frontalface_default.xml`.
    """
    if not png_paths or not HAAR_CASCADE_XML.is_file():
        return [None] * len(png_paths)

    if hasattr(cv2, "CascadeClassifier"):
        clf = cv2.CascadeClassifier(str(HAAR_CASCADE_XML))  # type: ignore[attr-defined]
        out_boxes: list[tuple[float, float, float, float] | None] = []
        for p in png_paths:
            gray = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                out_boxes.append(None)
                continue
            h0, w0 = gray.shape[:2]
            small = cv2.resize(gray, (540, 960), interpolation=cv2.INTER_AREA)
            faces = clf.detectMultiScale(small, scaleFactor=1.1, minNeighbors=5, minSize=(65, 65))
            if len(faces) == 0:
                out_boxes.append(None)
            else:
                x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
                sx, sy = w0 / 540.0, h0 / 960.0
                out_boxes.append((float(x * sx), float(y * sy), float((x + w) * sx), float((y + h) * sy)))
        return out_boxes

    # Vectorized numpy + cv2.integral Viola-Jones (OpenCV 5.0 native)
    casc = _load_vendored_haar(str(HAAR_CASCADE_XML))
    work_w, work_h = 270, 480
    scale_out = 1080.0 / work_w
    scales = [3.0 * (1.08 ** k) for k in range(12)]
    step = 2

    gray_frames: list[np.ndarray] = []
    valid_map: list[int] = []
    for idx_p, p in enumerate(png_paths):
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if g is not None:
            gray_frames.append(cv2.resize(g, (work_w, work_h), interpolation=cv2.INTER_AREA))
            valid_map.append(idx_p)

    results: list[tuple[float, float, float, float] | None] = [None] * len(png_paths)
    if not gray_frames:
        return results

    bufs, sqs, cols, off = [], [], [], 0
    for fi, g in enumerate(gray_frames):
        h0, w0 = g.shape
        for s in scales:
            w, h = int(round(w0 / s)), int(round(h0 / s))
            if w <= casc.win or h <= casc.win:
                continue
            img = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float64)
            ii = cv2.integral(img, sdepth=cv2.CV_64F)
            sq = cv2.integral(img * img, sdepth=cv2.CV_64F)
            ys, xs = np.mgrid[0 : h - casc.win : step, 0 : w - casc.win : step]
            ys, xs = ys.ravel(), xs.ravel()
            stride = ii.shape[1]
            cols.append(
                (
                    np.full(len(xs), fi),
                    np.full(len(xs), s),
                    off + ys * stride + xs,
                    np.full(len(xs), stride),
                    xs,
                    ys,
                )
            )
            bufs.append(ii.ravel())
            sqs.append(sq.ravel())
            off += ii.size

    if not cols:
        return results

    I = np.concatenate(bufs)
    Q = np.concatenate(sqs)
    fidx, scale_arr, base, stride_arr, xs_arr, ys_arr = (np.concatenate(c) for c in zip(*cols))
    base = base.astype(np.int64)
    stride_arr = stride_arr.astype(np.int64)

    def _rect(arr: np.ndarray, b_idx: np.ndarray, st_v: np.ndarray, rx: int, ry: int, rw: int, rh: int) -> np.ndarray:
        a = b_idx + ry * st_v + rx
        return arr[a + rh * st_v + rw] - arr[a + rw] - arr[a + rh * st_v] + arr[a]

    inner = casc.win - 2
    vs = _rect(I, base, stride_arr, 1, 1, inner, inner)
    vq = _rect(Q, base, stride_arr, 1, 1, inner, inner)
    nf = inner * inner * vq - vs * vs
    nf = np.where(nf > 0, np.sqrt(np.maximum(nf, 0.0)), 1.0)

    alive = np.arange(len(base))
    for thr, weak in casc.stages:
        b_cur, st_cur, n_cur = base[alive], stride_arr[alive], nf[alive]
        total = np.zeros(len(alive), dtype=np.float64)
        for feat_i, node_t, lv, rv in weak:
            val = np.zeros(len(alive), dtype=np.float64)
            for rx, ry, rw, rh, wt in casc.feats[feat_i]:
                val += wt * _rect(I, b_cur, st_cur, rx, ry, rw, rh)
            total += np.where(val / n_cur < node_t, lv, rv)
        alive = alive[total >= thr]
        if len(alive) == 0:
            break

    hits_per_frame: list[list[list[float]]] = [[] for _ in range(len(gray_frames))]
    for k in alive:
        s = float(scale_arr[k])
        hits_per_frame[int(fidx[k])].append(
            [
                float(xs_arr[k] * s * scale_out),
                float(ys_arr[k] * s * scale_out),
                float(casc.win * s * scale_out),
                float(casc.win * s * scale_out),
            ]
        )

    for fi, hits in enumerate(hits_per_frame):
        if len(hits) < 3:
            continue
        arr = np.asarray(hits, dtype=np.float64)
        med = np.median(arr, axis=0)
        near = arr[np.all(np.abs(arr - med) <= 0.25 * med[2], axis=1)]
        if len(near) == 0:
            continue
        bx = near.mean(axis=0)
        results[valid_map[fi]] = (
            round(float(bx[0]), 1),
            round(float(bx[1]), 1),
            round(float(bx[0] + bx[2]), 1),
            round(float(bx[1] + bx[3]), 1),
        )
    return results


def _eval_kf_param(val: Any, tau: float, default: Any) -> Any:
    """Evaluate a scalar or `[t, v, interp]` keyframe parameter at clip-local time `tau`."""
    if val is None:
        return default
    if not _is_animated_kf_list(val):
        return val
    keys = sorted(val, key=lambda k: float(k[0]))
    if tau <= float(keys[0][0]):
        return keys[0][1]
    if tau >= float(keys[-1][0]):
        return keys[-1][1]
    for k0, k1 in zip(keys, keys[1:]):
        t0, v0 = float(k0[0]), k0[1]
        t1, v1 = float(k1[0]), k1[1]
        if t0 <= tau <= t1:
            p = 0.0 if t1 <= t0 + 1e-9 else (tau - t0) / (t1 - t0)
            if isinstance(v0, list) and isinstance(v1, list) and len(v0) == 2 and len(v1) == 2:
                return [float(v0[0]) + p * (float(v1[0]) - float(v0[0])), float(v0[1]) + p * (float(v1[1]) - float(v0[1]))]
            if _is_num(v0) and _is_num(v1):
                return float(v0) + p * (float(v1) - float(v0))
            return v0
    return keys[-1][1]


def _motion_transform_point(clip: dict[str, Any], tau: float, x: float, y: float, seq_w: float = 1080.0, seq_h: float = 1920.0) -> tuple[float, float]:
    """Project source/layer point `(x, y)` through FilmCraft `motion` (`anchor`, `scale`, `position`) at `tau`."""
    mot = clip.get("motion") or {}
    anc = _eval_kf_param(mot.get("anchor"), tau, [seq_w / 2.0, seq_h / 2.0])
    mpos = _eval_kf_param(mot.get("position"), tau, [seq_w / 2.0, seq_h / 2.0])
    mscale = float(_eval_kf_param(mot.get("scale"), tau, 100.0)) / 100.0
    ax, ay = float(anc[0]), float(anc[1])
    px, py = float(mpos[0]), float(mpos[1])
    return px + mscale * (x - ax), py + mscale * (y - ay)


def _motion_unproject_box(
    clip: dict[str, Any],
    tau: float,
    box_screen: tuple[float, float, float, float],
    seq_w: float = 1080.0,
    seq_h: float = 1920.0,
) -> tuple[float, float, float, float]:
    """Invert FilmCraft `motion` at `tau` to recover unscaled `1080x1920` source face box."""
    mot = clip.get("motion") or {}
    anc = _eval_kf_param(mot.get("anchor"), tau, [seq_w / 2.0, seq_h / 2.0])
    mpos = _eval_kf_param(mot.get("position"), tau, [seq_w / 2.0, seq_h / 2.0])
    mscale = max(0.05, float(_eval_kf_param(mot.get("scale"), tau, 100.0)) / 100.0)
    ax, ay = float(anc[0]), float(anc[1])
    px, py = float(mpos[0]), float(mpos[1])
    x0, y0, x1, y1 = box_screen
    return (
        (x0 - px) / mscale + ax,
        (y0 - py) / mscale + ay,
        (x1 - px) / mscale + ax,
        (y1 - py) / mscale + ay,
    )


def _is_v1_broll_clip(clip: dict[str, Any], primary_aroll_src: str | None = None) -> bool:
    cname = str(clip.get("name", "")).lower()
    src = str(clip.get("src", ""))
    fn = Path(src).name.lower() if src else ""
    if cname.startswith(("b-roll", "broll", "footage")) or clip.get("broll_source"):
        return True
    if any(k in fn for k in ("b-roll", "broll", "footage", "ftg_", "stock_")) or "06_b-roll" in src.lower():
        return True
    if cname.startswith(("a-roll", "aroll")) or "a-roll" in fn or "aroll" in fn:
        return False
    if primary_aroll_src and src and not _same_media_path(src, primary_aroll_src):
        return True
    return False


def _is_explicit_still_plate(clip: dict[str, Any]) -> bool:
    if clip.get("still_plate") is True or clip.get("is_still") is True:
        return True
    src = str(clip.get("src") or "")
    if Path(src).suffix.lower() not in VIDEO_EXT:
        return True
    haystack = f"{clip.get('name', '')} {Path(src).stem}".lower()
    return any(tok in haystack for tok in STILL_PLATE_HINTS)


def _extract_gray_270x480(video_path: str, time_s: float) -> np.ndarray | None:
    r = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-ss",
            f"{max(0.0, time_s):.3f}",
            "-i",
            video_path,
            "-vf",
            "scale=270:480,format=gray",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=False,
        timeout=_RUN_TIMEOUT_S,
    )
    if r.returncode != 0 or len(r.stdout) < 270 * 480:
        return None
    return np.frombuffer(r.stdout[: 270 * 480], dtype=np.uint8).reshape(480, 270)


@lru_cache(maxsize=128)
def resolve_installed_font_path(family: str, style: str) -> str | None:
    """Resolve `(family, style)` via `fc-match` for accurate `PIL.ImageFont.getbbox` glyph ink metrics."""
    r = subprocess.run(
        ["fc-match", "-f", "%{file}", f"{family}:style={style}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=_PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    cand = (r.stdout or "").strip()
    if cand and Path(cand).is_file():
        return cand
    for fp in FONT_CANDIDATES:
        if Path(fp).is_file():
            return fp
    return None


@lru_cache(maxsize=256)
def _load_pil_font(font_path: str | None, size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, max(8, size_px))
        except OSError:
            pass
    return ImageFont.load_default()


def measure_text_clip_ink_bbox(
    clip: dict[str, Any],
    tau: float,
    seq_w: float = 1080.0,
    seq_h: float = 1920.0,
) -> tuple[float, float, float, float] | None:
    """
    Compute true glyph ink bounding box `(x0, y0, x1, y1)` in `1080x1920` screen pixels at clip-local time `tau`:
      - Uses `PIL.ImageFont.getbbox` WITHOUT `wonder_glow` bloom per Ruling `R26`.
      - Projects exact baseline anchor (`ms` / `ls` / `rs`) through FilmCraft `motion` (`anchor`, `scale`, `position`).
    """
    txt = str(clip.get("text") or "").strip()
    if not txt:
        return None
    op = float(_eval_kf_param(clip.get("opacity"), tau, 100.0))
    if op < 25.0:
        return None

    size_val = float(_eval_kf_param(clip.get("size"), tau, 52.0))
    pos_val = _eval_kf_param(clip.get("position"), tau, [seq_w / 2.0, seq_h / 2.0])
    px, py = float(pos_val[0]), float(pos_val[1])

    fam = str(clip.get("font") or "Montserrat")
    sty = str(clip.get("style") or "Bold")
    fpath = resolve_installed_font_path(fam, sty)
    pil_font = _load_pil_font(fpath, int(round(size_val)))

    align = str(clip.get("align") or "center").lower()
    pil_anchor = {"left": "ls", "center": "ms", "right": "rs"}.get(align, "ms")
    lead_raw = float(_eval_kf_param(clip.get("leading"), tau, 0.0))
    line_step = lead_raw if lead_raw > 2.0 else size_val * 1.22

    lines = [ln for ln in txt.split("\n") if ln.strip()] or [txt]
    boxes: list[tuple[float, float, float, float]] = []
    for idx_ln, ln in enumerate(lines):
        dy = idx_ln * line_step
        try:
            bx0, by0, bx1, by1 = pil_font.getbbox(ln, anchor=pil_anchor)
        except TypeError:
            bx0, by0, bx1, by1 = pil_font.getbbox(ln)
        lx0, ly0 = px + float(bx0), py + dy + float(by0)
        lx1, ly1 = px + float(bx1), py + dy + float(by1)
        sx0, sy0 = _motion_transform_point(clip, tau, lx0, ly0, seq_w, seq_h)
        sx1, sy1 = _motion_transform_point(clip, tau, lx1, ly1, seq_w, seq_h)
        boxes.append((min(sx0, sx1), min(sy0, sy1), max(sx0, sx1), max(sy0, sy1)))

    return (
        round(min(b[0] for b in boxes), 1),
        round(min(b[1] for b in boxes), 1),
        round(max(b[2] for b in boxes), 1),
        round(max(b[3] for b in boxes), 1),
    )


def _extract_context_face_norm(context_doc: dict[str, Any] | None) -> list[float] | None:
    if not isinstance(context_doc, dict):
        return None
    sf = context_doc.get("subject_framing")
    if isinstance(sf, dict):
        if isinstance(sf.get("face_bbox_norm"), list) and len(sf["face_bbox_norm"]) == 4:
            return [float(x) for x in sf["face_bbox_norm"]]
        # v7.9.4 bundle map {<media path>: framing}: the A-roll entry (path names `a-roll` / `aroll`), else the first face, as
        # typography_composer._aroll_framing does; the norm bbox is already relative to that clip's own size
        faces = [(str(rel), sub) for rel, sub in sf.items()
                 if isinstance(sub, dict) and isinstance(sub.get("face_bbox_norm"), list) and len(sub["face_bbox_norm"]) == 4]
        if faces:
            _rel, sub = next(((r, f) for r, f in faces if "a-roll" in r.lower() or "aroll" in r.lower()), faces[0])
            return [float(x) for x in sub["face_bbox_norm"]]
    return None


# v7.9.3 Gate 5: real V2 plate ink + face visibility windows
LOOK_S_PIP_RECTS = {"br": (700.0, 1446.0, 1012.0, 1836.0), "bl": (68.0, 1446.0, 380.0, 1836.0)}  # mirrors look_s_render.PIP_RECTS
FACE_FULL_MODES = frozenset({"P", "B", "S", "A1", "N"})  # Look S modes with the speaker visible full-frame
FACE_PIP_MODES = frozenset({"H", "A2"})  # full-screen B-roll: the face is only inside the PiP rect
PLATE_INK_ALPHA_MIN = 24  # mirrors look_s_render.INK_ALPHA_MIN
_KT_PROXY_NAME_RE = re.compile(r"^\s*KT(\d+)\s*·\s*(kt\d+)\b", re.I)
_KT_PLATE_FILE_RE = re.compile(r"(?:^|[_\-])kt_?\d{2}", re.I)


@lru_cache(maxsize=256)
def _plate_alpha_ink_px(src: str, t0: float, t1: float) -> tuple[tuple[int, int, int, int], int, int] | None:
    """Union of the opaque pixels (alpha > PLATE_INK_ALPHA_MIN) of an alpha plate over [t0, t1] at 10 fps, in plate px, with the
    plate (w, h). None when unreadable or fully transparent in that window."""
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", src],
        capture_output=True, text=True, check=False, timeout=_PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    try:
        st = json.loads(pr.stdout or "{}")["streams"][0]
        w, h = int(st["width"]), int(st["height"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return None
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t0):.3f}", "-t", f"{max(0.1, t1 - t0):.3f}", "-i", src,
           "-vf", "fps=10", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, check=False, timeout=_RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None
    n = len(r.stdout) // (w * h * 4)
    if r.returncode != 0 or n == 0:
        return None
    m = (np.frombuffer(r.stdout[: n * w * h * 4], np.uint8).reshape(n, h, w, 4)[..., 3] > PLATE_INK_ALPHA_MIN).any(axis=0)
    ys, xs = np.nonzero(m)
    if not xs.size:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), w, h


def measure_plate_ink_bbox(
    clip: dict[str, Any],
    tau: float,
    seq_w: float = 1080.0,
    seq_h: float = 1920.0,
    position: Any = None,
) -> tuple[float, float, float, float] | None:
    """v7.9.3: screen ink box of an alpha plate clip (V2 kinetic `.mov`): union of the plate's opaque pixels from clip-local `tau`
    (settled) to the clip end, projected through FilmCraft `motion` (anchor defaults to the plate centre, `position` overrides
    the motion position, e.g. a text proxy's position). None when invisible (opacity < 25), missing or unreadable."""
    src = str(clip.get("src") or "")
    if not src or not Path(src).is_file():
        return None
    if float(_eval_kf_param(clip.get("opacity"), tau, 100.0)) < 25.0:
        return None
    c_in, c_dur = float(clip.get("in", 0.0) or 0.0), float(clip.get("dur", 0.0) or 0.0)
    got = _plate_alpha_ink_px(src, round(c_in + max(0.0, tau), 3), round(c_in + max(c_dur, tau + 0.1), 3))
    if got is None:
        return None
    (x0, y0, x1, y1), w, h = got
    mot = dict(clip.get("motion") or {})
    mot.setdefault("anchor", [w / 2.0, h / 2.0])
    if position is not None:
        mot["position"] = position
    mot.setdefault("position", clip.get("position") or [seq_w / 2.0, seq_h / 2.0])
    proj = {"motion": mot}
    sx0, sy0 = _motion_transform_point(proj, tau, float(x0), float(y0), seq_w, seq_h)
    sx1, sy1 = _motion_transform_point(proj, tau, float(x1), float(y1), seq_w, seq_h)
    return round(min(sx0, sx1), 1), round(min(sy0, sy1), 1), round(max(sx0, sx1), 1), round(max(sy0, sy1), 1)


def load_scenes(path: str | Path | None) -> list[dict[str, Any]] | None:
    """`--scenes scenes.json` (studio_recipe output `{scenes: [...]}` or a bare list) -> scene list; None when not given."""
    if not path:
        return None
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    scenes = doc.get("scenes") if isinstance(doc, dict) else doc
    if not isinstance(scenes, list):
        raise ValueError(f"--scenes {path}: expected a list or {{'scenes': [...]}}")
    return [s for s in scenes if isinstance(s, dict)]


def face_visibility_at(
    ts: float,
    scenes: list[dict[str, Any]] | None,
    face_windows: Any = None,
) -> tuple[str | None, tuple[float, float, float, float] | None]:
    """v7.9.3: where the speaker's face is visible at `ts`. ("full", None) in Look S modes P/B/S/A1/N (or an unknown mode),
    ("pip", rect) in H/A2 full-screen B-roll (face only inside the PiP rect), ("none", None) outside every `meta.face_windows`
    window, (None, None) when neither scenes nor windows say anything (legacy: the A-roll face bands apply)."""
    for sc in scenes or []:
        try:
            s0, s1 = float(sc.get("start", sc.get("t0"))), float(sc.get("end", sc.get("t1")))  # look_s_render accepts both
        except (TypeError, ValueError):
            continue
        if s0 <= ts < s1:
            mode = str(sc.get("mode") or "").upper()
            if mode in FACE_PIP_MODES:
                return "pip", LOOK_S_PIP_RECTS.get(str(sc.get("pip") or "br"), LOOK_S_PIP_RECTS["br"])
            return "full", None
    if isinstance(face_windows, list):
        for w in face_windows:
            if isinstance(w, (list, tuple)) and len(w) >= 2 and _is_num(w[0]) and _is_num(w[1]):
                w0, w1 = float(w[0]), float(w[1])
            elif isinstance(w, dict) and _is_num(w.get("start", w.get("at"))):
                w0 = float(w.get("start", w.get("at")))
                w1 = float(w["end"]) if _is_num(w.get("end")) else w0 + (float(w["dur"]) if _is_num(w.get("dur")) else 0.0)
            else:
                continue
            if w0 <= ts < w1:
                return "full", None
        return "none", None
    return None, None


def run_full_visual_rigor_gate5(
    spec: dict[str, Any],
    qa_frames_dir: Path,
    planned_16: list[tuple[float, str]],
    context_doc: dict[str, Any] | None = None,
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Package 2 (`full` mode) Gate 5 Visual Proof:
      1. Blank Render Guard: all 16 `qa_frames/*.png` have `grayscale_std >= 10.0`
      2. Frozen Video B-Roll Detector: every V1 video B-roll (`dur >= 0.8s`) has `mean(|f2 - f1|) >= 0.8`
      3. Projected `facesafe` Eye/Mouth & Safe-Zone (`50..1030 x 140..1760`) True Glyph Ink Audit
         (Ruling `R26` no-glow ink, Ruling `R208` `<1.5s` opening hook exemption).
    """
    seq_w = float(spec.get("width", 1080))
    seq_h = float(spec.get("height", 1920))
    tracks = spec.get("tracks", [])

    # 1. Blank Render Guard across all 16 QA PNGs
    png_files: list[tuple[float, str, Path]] = []
    fallbacks = sorted(qa_frames_dir.glob("*.png"))
    for idx, (t_sec, tag) in enumerate(planned_16):
        cand = qa_frames_dir / f"t{t_sec:07.2f}.png"
        if not cand.is_file() and idx < len(fallbacks):
            cand = fallbacks[idx]
        if cand.is_file():
            png_files.append((t_sec, tag, cand))

    frame_stds: list[dict[str, Any]] = []
    blank_frames: list[dict[str, Any]] = []
    for t_sec, tag, p in png_files:
        with Image.open(p) as im:
            g_arr = np.asarray(im.convert("L"), dtype=np.float32)
            std_v = round(float(np.std(g_arr)), 2)
        rec = {"time_s": t_sec, "tag": tag, "png": p.name, "grayscale_std": std_v}
        frame_stds.append(rec)
        if std_v < 10.0:
            blank_frames.append(rec)

    # Identify V1 track & primary A-roll source
    v1_track = next(
        (t for t in tracks if t.get("type") == "video" and str(t.get("name", "")).startswith("V1")),
        None,
    ) or next((t for t in tracks if t.get("type") == "video"), None)
    v1_clips = sorted((v1_track or {}).get("clips", []), key=lambda c: float(c.get("at", 0.0)))

    aroll_src_counts: dict[str, float] = {}
    for cl in v1_clips:
        s = str(cl.get("src") or "")
        nm = str(cl.get("name", "")).lower()
        if s and (nm.startswith(("a-roll", "aroll")) or "aroll" in Path(s).name.lower() or "a-roll" in Path(s).name.lower()):
            aroll_src_counts[s] = aroll_src_counts.get(s, 0.0) + float(cl.get("dur", 0.0))
    primary_aroll_src = max(aroll_src_counts, key=aroll_src_counts.get) if aroll_src_counts else None

    # 2. Parallel Frozen Video B-Roll Detector on V1 (`dur >= 0.8s`)
    broll_jobs: list[dict[str, Any]] = []
    for cl in v1_clips:
        cdur = float(cl.get("dur", 0.0))
        csrc = str(cl.get("src") or "")
        if cdur < 0.8 or not csrc or not Path(csrc).is_file():
            continue
        if not _is_v1_broll_clip(cl, primary_aroll_src):
            continue
        if _is_explicit_still_plate(cl):
            continue
        raw_spd = float(cl.get("speed", 1.0))
        spd = raw_spd / 100.0 if raw_spd > 10.0 else max(0.01, raw_spd)
        c_in = max(0.0, float(cl.get("in", 0.0)))
        fdur = probe_media_duration(csrc) or (c_in + cdur * spd)
        t1 = c_in + 0.12
        t2 = min(max(t1 + 0.15, fdur - 0.05), c_in + cdur * spd - 0.12)
        if t2 <= t1 + 0.08:
            continue
        broll_jobs.append(
            {
                "name": str(cl.get("name", Path(csrc).name)),
                "src": csrc,
                "at": float(cl.get("at", 0.0)),
                "dur": cdur,
                "t1": round(t1, 3),
                "t2": round(t2, 3),
            }
        )

    def _probe_broll_motion(job: dict[str, Any]) -> dict[str, Any]:
        f1 = _extract_gray_270x480(job["src"], job["t1"])
        f2 = _extract_gray_270x480(job["src"], job["t2"])
        if f1 is None or f2 is None:
            return {**job, "mean_abs_diff": None, "frozen": False}
        diff_v = round(float(np.mean(np.abs(f2.astype(np.float32) - f1.astype(np.float32)))), 3)
        return {**job, "mean_abs_diff": diff_v, "frozen": bool(diff_v < 0.8)}

    broll_motion_results: list[dict[str, Any]] = []
    if broll_jobs:
        with ThreadPoolExecutor(max_workers=min(8, len(broll_jobs))) as ex:
            broll_motion_results = list(ex.map(_probe_broll_motion, broll_jobs))
    frozen_broll = [r for r in broll_motion_results if r.get("frozen")]

    # 3. Projected `facesafe` Eye/Mouth & Safe-Zone Ink Audit
    def _active_v1_at(ts: float) -> tuple[dict[str, Any] | None, bool]:
        for cl in v1_clips:
            c0 = float(cl.get("at", 0.0))
            c1 = c0 + float(cl.get("dur", 0.0))
            if c0 <= ts < c1 - 1e-6:
                return cl, _is_v1_broll_clip(cl, primary_aroll_src)
        return None, False

    aroll_qa_indices = [i for i, (ts, _, _) in enumerate(png_files) if not _active_v1_at(ts)[1] and _active_v1_at(ts)[0] is not None]
    aroll_pngs = [png_files[i][2] for i in aroll_qa_indices]
    haar_boxes = detect_frontal_faces_1080p(aroll_pngs) if aroll_pngs else []

    qa_face_by_time: dict[float, tuple[float, float, float, float]] = {}
    unprojected_source_boxes: list[tuple[float, float, float, float]] = []
    for idx_local, box in enumerate(haar_boxes):
        if box is None:
            continue
        ts, _, _ = png_files[aroll_qa_indices[idx_local]]
        qa_face_by_time[ts] = box
        v1_cl, _ = _active_v1_at(ts)
        if v1_cl is not None:
            unprojected_source_boxes.append(_motion_unproject_box(v1_cl, ts - float(v1_cl["at"]), box, seq_w, seq_h))

    # Build canonical unscaled `1080x1920` source face box from `--context` AND/OR median unprojected Haar box
    ctx_norm = _extract_context_face_norm(context_doc)
    canonical_src_face: tuple[float, float, float, float] | None = None
    if unprojected_source_boxes:
        arr_u = np.asarray(unprojected_source_boxes, dtype=np.float64)
        med_u = np.median(arr_u, axis=0)
        canonical_src_face = (float(med_u[0]), float(med_u[1]), float(med_u[2]), float(med_u[3]))
    elif ctx_norm is not None:
        canonical_src_face = (
            ctx_norm[0] * seq_w,
            ctx_norm[1] * seq_h,
            ctx_norm[2] * seq_w,
            ctx_norm[3] * seq_h,
        )

    def _face_bands_at(ts: float) -> dict[str, tuple[float, float, float, float]] | None:
        v1_cl, is_br = _active_v1_at(ts)
        if v1_cl is None or is_br:
            return None
        # Prefer direct Haar hit on matching QA timestamp if within ±0.08s
        near_qa = next((bx for qt, bx in qa_face_by_time.items() if abs(qt - ts) <= 0.08), None)
        if near_qa is not None:
            fx0, fy0, fx1, fy1 = near_qa
        elif canonical_src_face is not None:
            tau = ts - float(v1_cl.get("at", 0.0))
            sx0, sy0 = _motion_transform_point(v1_cl, tau, canonical_src_face[0], canonical_src_face[1], seq_w, seq_h)
            sx1, sy1 = _motion_transform_point(v1_cl, tau, canonical_src_face[2], canonical_src_face[3], seq_w, seq_h)
            fx0, fy0, fx1, fy1 = min(sx0, sx1), min(sy0, sy1), max(sx0, sx1), max(sy0, sy1)
        else:
            return None

        fw, fh = max(1.0, fx1 - fx0), max(1.0, fy1 - fy0)
        eye_band = (
            fx0 + EYE_REL_BOX[0] * fw,
            fy0 + EYE_REL_BOX[1] * fh,
            fx0 + EYE_REL_BOX[2] * fw,
            fy0 + EYE_REL_BOX[3] * fh,
        )
        mouth_band = (
            fx0 + MOUTH_REL_BOX[0] * fw,
            fy0 + MOUTH_REL_BOX[1] * fh,
            fx0 + MOUTH_REL_BOX[2] * fw,
            fy0 + MOUTH_REL_BOX[3] * fh,
        )
        return {"face": (fx0, fy0, fx1, fy1), "eye_band": eye_band, "mouth_band": mouth_band}

    safe_zone_warnings: list[dict[str, Any]] = []
    face_room_warnings: list[dict[str, Any]] = []
    text_clips_audited = 0
    plate_clips_audited = 0
    plate_text_proxies: list[dict[str, Any]] = []
    r208_exempt_count = 0
    # v7.9.3: face visibility windows (--scenes, else context scenes, else meta.face_windows; none = legacy everywhere)
    if scenes is None and isinstance(context_doc, dict) and isinstance(context_doc.get("scenes"), list):
        scenes = [s for s in context_doc["scenes"] if isinstance(s, dict)]
    face_windows = (spec.get("meta") or {}).get("face_windows") if isinstance(spec.get("meta"), dict) else None

    # V2+ alpha plates (kinetic `.mov`), and the folders they live in (to recognise text proxies of a plate)
    plate_clips: list[tuple[str, dict[str, Any]]] = []
    for tr in tracks:
        if tr.get("type") != "video" or tr is v1_track:
            continue
        for cl in tr.get("clips", []):
            src = str(cl.get("src") or "")
            if (src and Path(src).suffix.lower() in (".mov", ".webm", ".mkv") and Path(src).is_file()
                    and (_load_sidecar_typo_meta(src) is not None or _KT_PLATE_FILE_RE.search(Path(src).name))):
                plate_clips.append((str(tr.get("name", "")), cl))
    plate_dirs = sorted({str(Path(str(cl["src"])).parent) for _, cl in plate_clips})

    def _proxy_plate_of(cname: str) -> Path | None:
        m = _KT_PROXY_NAME_RE.match(cname)
        if not m:
            return None
        fname = f"kt_{int(m.group(1)):02d}_{m.group(2).lower()}.mov"
        return next((Path(d) / fname for d in plate_dirs if (Path(d) / fname).is_file()), None)

    def _audit_ink_box(tname: str, ln: str, cname: str, c_at: float, c_dur: float, t_probe: float,
                       ink: tuple[float, float, float, float], cur_px: float, cur_py: float,
                       size_fix: tuple[str, float, str], source: str) -> None:
        nonlocal r208_exempt_count
        ix0, iy0, ix1, iy1 = ink
        # (a) Safe-Zone Check (`x: 50..1030, y: 140..1760`)
        out_sides: list[str] = []
        fix_parts: list[str] = []
        if ix0 < SAFE_ZONE_BOX["x_min"] or ix1 > SAFE_ZONE_BOX["x_max"]:
            ink_w = max(1.0, ix1 - ix0)
            max_safe_w = SAFE_ZONE_BOX["x_max"] - SAFE_ZONE_BOX["x_min"]
            if ink_w > max_safe_w:
                fix_parts.append(f"reduce {size_fix[0]} to {math.floor(size_fix[1] * (max_safe_w / ink_w))}{size_fix[2]}")
            else:
                dx = (SAFE_ZONE_BOX["x_min"] - ix0) if ix0 < SAFE_ZONE_BOX["x_min"] else (SAFE_ZONE_BOX["x_max"] - ix1)
                fix_parts.append(f"move pos_x to {round(cur_px + dx, 1)}")
            out_sides.append(f"x={ix0:.0f}..{ix1:.0f}")
        if iy0 < SAFE_ZONE_BOX["y_min"] or iy1 > SAFE_ZONE_BOX["y_max"]:
            dy = (SAFE_ZONE_BOX["y_min"] - iy0) if iy0 < SAFE_ZONE_BOX["y_min"] else (SAFE_ZONE_BOX["y_max"] - iy1)
            fix_parts.append(f"move pos_y to {round(cur_py + dy, 1)}")
            out_sides.append(f"y={iy0:.0f}..{iy1:.0f}")
        if out_sides:
            safe_zone_warnings.append(
                {
                    "track": tname,
                    "clip": cname,
                    "at": round(c_at, 3),
                    "ink_bbox": [ix0, iy0, ix1, iy1],
                    "violation": ", ".join(out_sides),
                    "source": source,
                    "fix": f"move/resize clip '{cname}' (at={c_at:.2f}s): " + ", ".join(fix_parts),
                }
            )

        # (b) Ruling `R208`: exempt `< 1.5s` opening hook titles from Face-Room check
        if (ln != "text_low") and (
            (c_at < 1.5 and (c_at + c_dur) <= 1.60) or ("hook" in cname.lower() and c_at < 1.5 and c_dur <= 1.55)
        ):
            r208_exempt_count += 1
            return

        # Face-Room only where the face is visible (v7.9.3): A-roll eye/mouth bands, or the PiP rect on H/A2 B-roll scenes
        vis, pip_rect = face_visibility_at(t_probe, scenes, face_windows)
        if vis == "none":
            return
        if vis == "pip" and pip_rect is not None:
            bands: dict[str, tuple[float, float, float, float]] | None = {"face": pip_rect, "pip_rect": pip_rect}
            band_names: tuple[str, ...] = ("pip_rect",)
        else:
            bands = _face_bands_at(t_probe)
            band_names = ("eye_band", "mouth_band")
        if bands is None:
            return

        for band_name in band_names:
            bx0, by0, bx1, by1 = bands[band_name]
            exp_x0, exp_y0 = bx0 - FACE_MARGIN_PX, by0 - FACE_MARGIN_PX
            exp_x1, exp_y1 = bx1 + FACE_MARGIN_PX, by1 + FACE_MARGIN_PX
            ov_x = min(ix1, exp_x1) - max(ix0, exp_x0)
            ov_y = min(iy1, exp_y1) - max(iy0, exp_y0)
            if ov_x > 2.0 and ov_y > 2.0:
                face_mid_y = 0.5 * (bands["face"][1] + bands["face"][3])
                if band_name == "pip_rect":
                    # Move above the PiP window
                    safe_y = max(SAFE_ZONE_BOX["y_min"] + 44.0, round(cur_py - (iy1 - (by0 - 18.0)), 1))
                elif ln != "text_low" and cur_py <= face_mid_y:
                    # Move above eye_band
                    target_bottom = bands["eye_band"][1] - 18.0
                    safe_y = max(SAFE_ZONE_BOX["y_min"] + 44.0, round(cur_py - (iy1 - target_bottom), 1))
                else:
                    # Move below mouth_band
                    target_top = bands["mouth_band"][3] + 18.0
                    safe_y = min(SAFE_ZONE_BOX["y_max"] - 20.0, round(cur_py + (target_top - iy0), 1))

                face_room_warnings.append(
                    {
                        "track": tname,
                        "clip": cname,
                        "at": round(c_at, 3),
                        "probe_t": t_probe,
                        "band": band_name,
                        "overlap_px": round(ov_y, 1),
                        "ink_bbox": [ix0, iy0, ix1, iy1],
                        "band_bbox": [round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)],
                        "safe_y": safe_y,
                        "source": source,
                        "fix": f"move clip '{cname}' (at={c_at:.2f}s) pos_y to {safe_y}",
                    }
                )
                break

    for tr in tracks:
        if tr.get("type") != "text":
            continue
        tname = str(tr.get("name", ""))
        ln = _lane(tname)
        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.05:
                continue
            cname = str(cl.get("name") or cl.get("text") or "Text")
            tau_settle = min(0.30, max(0.12, c_dur * 0.40))
            t_probe = round(c_at + tau_settle, 3)
            pos_val = _eval_kf_param(cl.get("position"), tau_settle, [seq_w / 2.0, seq_h / 2.0])
            cur_px, cur_py = float(pos_val[0]), float(pos_val[1])
            # v7.9.3: a text proxy standing in for a V2 plate (`KTnn · ktXX` with `kt_nn_ktXX.mov` on disk) is audited with the
            # plate's real alpha ink at the proxy's position, and flagged
            proxy_plate = _proxy_plate_of(cname)
            ink = None
            if proxy_plate is not None:
                ink = measure_plate_ink_bbox({"src": str(proxy_plate), "in": 0.0, "dur": c_dur, "opacity": cl.get("opacity")},
                                             tau_settle, seq_w, seq_h, position=[cur_px, cur_py])
                plate_text_proxies.append({"track": tname, "clip": cname, "at": round(c_at, 3), "plate": str(proxy_plate),
                                           "ink_bbox": list(ink) if ink else None})
            source = "plate_alpha" if ink is not None else "pil_glyph"
            if ink is None:
                ink = measure_text_clip_ink_bbox(cl, tau_settle, seq_w, seq_h)
            if ink is None:
                continue
            text_clips_audited += 1
            size_now = float(_eval_kf_param(cl.get("size"), tau_settle, 52.0))
            _audit_ink_box(tname, ln, cname, c_at, c_dur, t_probe, ink, cur_px, cur_py, ("size", size_now, "px"), source)

    # v7.9.3: V2 kinetic plates measured from their real alpha (projected through motion anchor / position / scale)
    for tname, cl in plate_clips:
        c_at = float(cl.get("at", 0.0))
        c_dur = float(cl.get("dur", 0.5))
        if c_dur <= 0.05:
            continue
        cname = str(cl.get("name") or Path(str(cl.get("src"))).name)
        tau_settle = min(0.30, max(0.12, c_dur * 0.40))
        t_probe = round(c_at + tau_settle, 3)
        ink = measure_plate_ink_bbox(cl, tau_settle, seq_w, seq_h)
        if ink is None:
            continue
        plate_clips_audited += 1
        mot = cl.get("motion") if isinstance(cl.get("motion"), dict) else {}
        mpos = _eval_kf_param(mot.get("position"), tau_settle, cl.get("position") or [seq_w / 2.0, seq_h / 2.0])
        scale_now = float(_eval_kf_param(mot.get("scale"), tau_settle, 100.0))
        _audit_ink_box(tname, _lane(tname), cname, c_at, c_dur, t_probe, ink, float(mpos[0]), float(mpos[1]),
                       ("motion.scale", scale_now, "%"), "plate_alpha")

    return {
        "executed": True,
        "qa_frames_checked": len(frame_stds),
        "min_grayscale_std": min((r["grayscale_std"] for r in frame_stds), default=0.0),
        "blank_frames": blank_frames,
        "broll_clips_checked": len(broll_motion_results),
        "frozen_broll": frozen_broll,
        "broll_motion": broll_motion_results,
        "aroll_qa_faces_detected": len(qa_face_by_time),
        "aroll_qa_frames_total": len(aroll_qa_indices),
        "text_clips_audited": text_clips_audited,
        "plate_clips_audited": plate_clips_audited,
        "plate_text_proxies": plate_text_proxies,
        "face_scope": "scenes" if scenes else ("meta.face_windows" if isinstance(face_windows, list) else "all_frames"),
        "r208_hook_exempt_clips": r208_exempt_count,
        "safe_zone_warnings": safe_zone_warnings,
        "face_room_warnings": face_room_warnings,
    }


# ==============================================================================
# [v6.0] Director Physics & Era-2 Manifesto Audits:
#   1. `audit_chromatic_diversity` (`color_world_polarity` 1–2 Hue World + Polarity Flips vs `RAINBOW_HUE_SOUP`;
#      opt-in `multi_hue_6` legacy mode)
#   2. `adjudicate_v60_cut_grammar_and_c7` & `audit_transition_and_rhythm_continuity`
#      (`4-Cut Grammar` 40–75% Clean Hard Cuts, Bimodal `C7` `True Vocal J-Cut` `[-850ms..-140ms]`,
#       `OVER_TRANSITIONED_SPAM` `>45%`, `WHOOSH_OVERLOAD` `>6/min`, `bgm_silence_stops_count`)
#   3. `audit_secondary_text_groups` (`100ms` Spatial Density Cap `MAX_ZONES <= 2` / `3` w/ `<=30pt` G2,
#      `CARD_TEXT_COLLISION`, `FRAME_CLUTTER_OVERLOAD`, `clean_breathing_frame_pct`, `lowercase_hero_pct`)
# ==============================================================================

CANONICAL_HUE_BUCKETS = (
    "gold_amber",
    "coral_red",
    "mint_emerald",
    "cyan_blue",
    "violet_purple",
    "lime_green",
    "orange_peach",
    "neutral_white",
)

RESTRAINED_PALETTE_ARCHETYPES = {
    "minimal_intellectual",
    "story_confessional_breath",
}

COLOR_WORLD_DEFAULT_PREFIXES = (
    "dviet_",
    "minimal_",
    "story_",
)

SECONDARY_TEXT_GROUPS = (
    "G1_lead_sub",
    "G2_quiet_bottom",
    "G3_spatial_shoulder_arc",
    "G4_ui_micro_labels",
)

_HERO_TRACK_RE = re.compile(r"\b(text_hi|text_mid|text_top|hero|title)\b", re.IGNORECASE)
_SECONDARY_TRACK_RE = re.compile(r"\b(text_sub|text_low|callout|caption|sub_text|micro|shoulder)\b", re.IGNORECASE)
_GHOST_ECHO_RE = re.compile(r"\b(ghost|echo_bg|backdrop_dup|shadow_dup)\b", re.IGNORECASE)
_HERO_NAME_KEYWORDS = ("hero", "từ khoá", "từ khóa", "hook")
_INLINE_HUE_TAG_RE = re.compile(r"\[(#?[a-zA-Z0-9_]+):([^\]]+)\]")
_INLINE_TOKEN_TO_BUCKET = {
    "gold": "gold_amber",
    "amber": "gold_amber",
    "yellow": "gold_amber",
    "coral": "coral_red",
    "red": "coral_red",
    "crimson": "coral_red",
    "mint": "mint_emerald",
    "emerald": "mint_emerald",
    "teal": "mint_emerald",
    "cyan": "cyan_blue",
    "blue": "cyan_blue",
    "cobalt": "cyan_blue",
    "violet": "violet_purple",
    "purple": "violet_purple",
    "peach": "orange_peach",
    "orange": "orange_peach",
    "lime": "lime_green",
    "acid_lime": "lime_green",
    "green": "lime_green",
    "white": "neutral_white",
    "ink": "neutral_white",
    "black": "neutral_white",
}
_CARD_GFX_TRACK_RE = re.compile(r"\b(card|gfx|prop|visual_block|ui_card|text_img)\b", re.IGNORECASE)
_CARD_GFX_NAME_HINTS = (
    "checklist_audit_card",
    "code_terminal_window",
    "flowchart_pipeline",
    "versus_split_card",
    "metric_kpi_hero",
    "strike_myth_banner",
    "quote_editorial_note",
    "polaroid_callout",
    "floating_pill_badge",
    "clean_alpha_prop",
    "card_",
    "gfx_",
    "prop_",
)
_BG_PLATE_EXCLUSION_HINTS = (
    "dải tối",
    "color matte",
    "vignette",
    "top_shade",
    "bokeh",
    "plane_1",
    "plane1",
    "clean_broll_plate",
    "b-roll",
    "broll",
    "a-roll",
    "aroll",
    "rvm",
    "cutout",
    "speaker",
    "foreground",
    "motion_canvas_bg",
    "polarity_canvas",
    "light_canvas",
    "paper_canvas",
    "sage_canvas",
    "white_canvas",
    "chuyển cảnh",
)
_POLARITY_LIGHT_HINTS = (
    "polarity_light",
    "polarity_flip",
    "light_canvas",
    "paper_canvas",
    "sage_canvas",
    "white_canvas",
    "eef4ea",
    "fafafa",
    "f7f4eb",
    "high_key",
    "motion_canvas_light",
    "wall_of_words",
    "canvas_light",
)
_HEAVY_WGPU_TRANS_EFFECTS = (
    "whip",
    "zoom_blur",
    "directional_blur",
    "flash",
    "flicker",
    "glitch",
    "luma_fade",
    "rgb_split",
    "film_dissolve",
    "cross_dissolve",
    "optical_depth",
)
_HEAVY_WHOOSH_IMPACT_HINTS = (
    "whoosh",
    "swoosh",
    "swish",
    "whip",
    "impact",
    "boom",
    "slam",
    "thud",
    "braam",
    "riser_hit",
    "punch",
    "sub_drop",
    "chuyển cảnh",
)
_SOFT_FOLEY_EXCLUSION_HINTS = (
    "click",
    "tick",
    "keystroke",
    "typewriter",
    "paper",
    "cloth_soft",
    "breath",
    "camera_shutter_soft",
)


def _strip_inline_hue_markup(text: str) -> str:
    return _INLINE_HUE_TAG_RE.sub(r"\2", text)


def _extract_inline_hue_buckets(text: str) -> list[str]:
    buckets: list[str] = []
    for m in _INLINE_HUE_TAG_RE.finditer(text):
        tok = m.group(1).strip().lower()
        if tok.startswith("#"):
            b = classify_hex_hue_bucket(tok)
        else:
            b = _INLINE_TOKEN_TO_BUCKET.get(tok, "neutral_white")
        if b != "neutral_white" and b not in buckets:
            buckets.append(b)
    return buckets


def _parse_hex_hsv(color_val: Any) -> tuple[float, float, float] | None:
    if isinstance(color_val, str):
        s = color_val.strip().lstrip("#")
        if len(s) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in s):
            s = "".join(ch * 2 for ch in s)
        if len(s) in (6, 8) and all(ch in "0123456789abcdefABCDEF" for ch in s):
            if len(s) == 8 and int(s[6:8], 16) == 0:
                return None
            r_f = int(s[0:2], 16) / 255.0
            g_f = int(s[2:4], 16) / 255.0
            b_f = int(s[4:6], 16) / 255.0
            return colorsys.rgb_to_hsv(r_f, g_f, b_f)
    elif isinstance(color_val, (list, tuple)) and len(color_val) >= 3 and all(_is_num(x) for x in color_val[:3]):
        mx = max(float(color_val[0]), float(color_val[1]), float(color_val[2]))
        div = 255.0 if mx > 1.001 else 1.0
        r_f = max(0.0, min(1.0, float(color_val[0]) / div))
        g_f = max(0.0, min(1.0, float(color_val[1]) / div))
        b_f = max(0.0, min(1.0, float(color_val[2]) / div))
        return colorsys.rgb_to_hsv(r_f, g_f, b_f)
    return None


def classify_hex_hue_bucket(color_val: Any) -> str:
    """
    Normalize a hex string (`#RGB`, `#RRGGBB`, `#RRGGBBAA`) or RGB triplet into one of the 8
    canonical perceptual hue buckets:
      `gold_amber`, `coral_red`, `mint_emerald`, `cyan_blue`, `violet_purple`,
      `lime_green`, `orange_peach`, `neutral_white`.
    """
    hsv = _parse_hex_hsv(color_val)
    if hsv is None:
        return "neutral_white"
    hue_01, sat, val = hsv
    if sat <= 0.16 or val <= 0.18 or (sat <= 0.22 and val <= 0.78):
        return "neutral_white"

    deg = (hue_01 * 360.0) % 360.0
    if deg >= 325.0 or deg < 14.0:
        return "coral_red"
    if deg < 35.0:
        return "orange_peach"
    if deg < 66.0:
        return "gold_amber"
    if deg < 150.0:
        return "lime_green"
    if deg < 178.0:
        return "mint_emerald"
    if deg < 242.0:
        return "cyan_blue"
    return "violet_purple"


def _resolve_clip_color_and_bucket(clip: dict[str, Any], tau_settle: float) -> tuple[str, str]:
    raw_c = clip.get("color")
    if raw_c is None and isinstance(clip.get("fill"), str):
        raw_c = clip.get("fill")
    if _is_animated_kf_list(raw_c):
        settled = _eval_kf_param(raw_c, tau_settle, "#FFFFFF")
        b_settled = classify_hex_hue_bucket(settled)
        if b_settled != "neutral_white":
            return str(settled), b_settled
        for k in reversed(raw_c):
            if len(k) >= 2:
                b_cand = classify_hex_hue_bucket(k[1])
                if b_cand != "neutral_white":
                    return str(k[1]), b_cand
        hex_out, b_out = str(settled), b_settled
    else:
        hex_out = str(raw_c) if isinstance(raw_c, str) and raw_c.strip() else "#FFFFFF"
        b_out = classify_hex_hue_bucket(hex_out)

    if b_out == "neutral_white":
        inline_bs = _extract_inline_hue_buckets(str(clip.get("text") or ""))
        if inline_bs:
            return hex_out, inline_bs[0]
    return hex_out, b_out


def _clip_max_opacity(clip: dict[str, Any]) -> float:
    op = clip.get("opacity")
    if op is None:
        return 100.0
    if _is_animated_kf_list(op):
        vals = [float(k[1]) for k in op if len(k) >= 2 and _is_num(k[1])]
        return max(vals) if vals else 100.0
    return float(op) if _is_num(op) else 100.0


def _clip_settled_size(clip: dict[str, Any], tau_settle: float, default: float = 52.0) -> float:
    sz = clip.get("size")
    if sz is None:
        return default
    if _is_animated_kf_list(sz):
        s_val = float(_eval_kf_param(sz, tau_settle, default))
        vals = [float(k[1]) for k in sz if len(k) >= 2 and _is_num(k[1])]
        return max(s_val, max(vals) if vals else s_val)
    return float(sz) if _is_num(sz) else default


def _is_ghost_echo_text_clip(clip: dict[str, Any], cname_low: str) -> bool:
    if _GHOST_ECHO_RE.search(cname_low):
        return True
    return _clip_max_opacity(clip) < 35.0


def _is_hero_text_clip(track_name: str, clip: dict[str, Any], size_px: float) -> bool:
    cname_low = unicodedata.normalize("NFC", str(clip.get("name") or "")).lower()
    if _is_ghost_echo_text_clip(clip, cname_low):
        return False
    tname_low = unicodedata.normalize("NFC", track_name).lower()
    ln = _lane(track_name).lower()
    if _HERO_TRACK_RE.search(tname_low) or ln in ("text_hi", "text_mid", "text_top", "hero", "title"):
        return True
    if any(kw in cname_low for kw in _HERO_NAME_KEYWORDS):
        return True
    if size_px >= 60.0:
        return True
    return False


def _merged_spec_meta(spec: dict[str, Any], spec_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    base = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    if isinstance(spec_meta, dict) and spec_meta:
        return {**base, **spec_meta}
    return dict(base)


def _resolve_archetype(
    spec: dict[str, Any],
    archetype: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> str:
    if isinstance(archetype, str) and archetype.strip():
        return archetype.strip().lower()
    meta = _merged_spec_meta(spec, spec_meta)
    cand = meta.get("archetype") or spec.get("archetype") or ""
    return str(cand).strip().lower()


def _is_dviet_era2_archetype(eff_arch: str) -> bool:
    return ("dviet_era2" in eff_arch) or ("7707" in eff_arch)


def _uses_v60_dviet_4cut_grammar(
    spec: dict[str, Any],
    archetype: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> bool:
    meta = _merged_spec_meta(spec, spec_meta)
    cg = str(meta.get("cut_grammar") or spec.get("cut_grammar") or "").strip().lower()
    if cg == "dviet_4cut":
        return True
    if cg in ("legacy_100pct_wgpu", "strict_wgpu"):
        return False
    eff_arch = _resolve_archetype(spec, archetype, spec_meta)
    return any(eff_arch.startswith(p) or (p in eff_arch) for p in ("dviet_", "minimal_", "story_"))


def _resolve_color_policy(
    spec: dict[str, Any],
    archetype: str | None = None,
    color_policy: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> str:
    meta = _merged_spec_meta(spec, spec_meta)
    explicit = str(color_policy or meta.get("color_policy") or spec.get("color_policy") or "").strip().lower()
    if explicit in ("multi_hue_6", "rainbow_6", "legacy_6hue"):
        return "multi_hue_6"
    if explicit in ("semantic_4act_jewel", "4act_jewel", "jewel_4act"):
        return "semantic_4act_jewel"
    if explicit in ("color_world_polarity", "color_world", "2_hue_polarity"):
        return "color_world_polarity"
    return "color_world_polarity"


def _detect_polarity_light_clips(
    spec: dict[str, Any],
    spec_meta: dict[str, Any] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """
    Detect full-screen high-key light canvases (`#EEF4EA`, `#FAFAFA`, `#F7F4EB`), Motion Canvas
    polarity flips, or dark-ink text spans indicating high-key polarity shifts.
    """
    meta = _merged_spec_meta(spec, spec_meta)
    details: list[dict[str, Any]] = []
    covered_intervals: list[tuple[float, float]] = []

    raw_flips = meta.get("polarity_flips")
    if isinstance(raw_flips, list):
        for idx_pf, pf in enumerate(raw_flips):
            if isinstance(pf, (list, tuple)) and len(pf) >= 2 and _is_num(pf[0]) and _is_num(pf[1]):
                s0, s1 = float(pf[0]), float(pf[1])
                details.append({"track": "meta.polarity_flips", "name": f"polarity_flip_{idx_pf+1}", "at": round(s0, 3), "dur": round(max(0.0, s1 - s0), 3), "reason": "meta.polarity_flips"})
                covered_intervals.append((s0, s1))
            elif isinstance(pf, dict) and _is_num(pf.get("at")):
                s0 = float(pf["at"])
                dur_pf = float(pf.get("dur", 1.0))
                details.append({"track": "meta.polarity_flips", "name": str(pf.get("name", f"polarity_flip_{idx_pf+1}")), "at": round(s0, 3), "dur": round(dur_pf, 3), "reason": str(pf.get("bg", "meta.polarity_flips"))})
                covered_intervals.append((s0, s0 + dur_pf))

    for tr in spec.get("tracks", []):
        tname = str(tr.get("name", ""))
        ttype = str(tr.get("type", ""))
        if ttype == "audio":
            continue
        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.04:
                continue
            cname = str(cl.get("name") or "")
            csrc = str(cl.get("src") or "")
            hay = unicodedata.normalize("NFC", f"{cname} {Path(csrc).name if csrc else ''} {tname}").lower()

            if ttype != "text" and "text" not in cl:
                s0 = float(_eval_kf_param((cl.get("motion") or {}).get("scale"), 0.0, 100.0))
                is_light_color = False
                for ck in ("bg_color", "canvas_color", "fill", "color"):
                    if cl.get(ck) is not None:
                        hsv = _parse_hex_hsv(cl.get(ck))
                        if hsv is not None and hsv[2] >= 0.82 and hsv[1] <= 0.22:
                            is_light_color = True
                            break
                has_hint = any(h in hay for h in _POLARITY_LIGHT_HINTS)
                if (is_light_color or has_hint) and s0 >= 70.0:
                    details.append(
                        {
                            "track": tname,
                            "name": cname or Path(csrc).name or "light_canvas",
                            "at": round(c_at, 3),
                            "dur": round(c_dur, 3),
                            "reason": "light_canvas_plate",
                        }
                    )
                    covered_intervals.append((c_at, c_at + c_dur))

    # Also detect dark-ink text spans (`#0D0D0D` / `#111111` / `#1C1B18`) over uncovered light frames
    for tr in spec.get("tracks", []):
        tname = str(tr.get("name", ""))
        ttype = str(tr.get("type", ""))
        for cl in tr.get("clips", []):
            if ttype != "text" and "text" not in cl:
                continue
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            raw_c = cl.get("color")
            c_val = _eval_kf_param(raw_c, min(0.25, c_dur * 0.4), "#FFFFFF") if _is_animated_kf_list(raw_c) else raw_c
            hsv = _parse_hex_hsv(c_val)
            if hsv is not None and hsv[2] <= 0.24:
                t_mid = c_at + 0.5 * c_dur
                if not any(a - 0.05 <= t_mid <= b + 0.05 for a, b in covered_intervals):
                    details.append(
                        {
                            "track": tname,
                            "name": str(cl.get("name") or cl.get("text", "dark_ink"))[:28],
                            "at": round(c_at, 3),
                            "dur": round(c_dur, 3),
                            "reason": f"dark_ink_text({c_val})",
                        }
                    )
                    covered_intervals.append((c_at, c_at + c_dur))

    return len(details), details


def audit_chromatic_diversity(
    spec: dict[str, Any],
    archetype: str | None = None,
    tier_used: str = "fast",
    color_policy: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `v6.0` Chromatic Policy & Polarity Flip Audit:
      - Supports two policies (`meta.color_policy` / `color_policy`):
          1. `"color_world_polarity"` (DEFAULT in `v6.0` for `dviet_*`, `minimal_*`, `story_*` & general):
             Validates `@__dviet`'s 19-video law: **1 Primary Signature Hue (`55%–100%` of accented heroes)
             + `0–1` Secondary Pain/Contrast Hue (`0%–45%`)** (`1–2` text accent buckets; up to `3` in
             `tech_saas_modular` / `high_retention_proof` / `hybrid_adaptive`).
             Flags `RAINBOW_HUE_SOUP` if `>= 5` distinct neon/accent hue buckets appear in a single video!
             Records `polarity_light_clips_or_frames` (`#EEF4EA` / `#FAFAFA` full-screen light canvases).
          2. `"multi_hue_6"` (opt-in legacy mode when `meta.color_policy == "multi_hue_6"`):
             Preserves `v5.2` `<= 42%` `MONO_HUE_OVERUSE` & `>= 3` `CONSECUTIVE_HERO_HUE_REPEAT` checks.
    """
    eff_arch = _resolve_archetype(spec, archetype, spec_meta)
    eff_policy = _resolve_color_policy(spec, archetype=eff_arch, color_policy=color_policy, spec_meta=spec_meta)
    is_restrained_arch = any(r_arch in eff_arch for r_arch in RESTRAINED_PALETTE_ARCHETYPES)
    is_strict_2hue_world = (not eff_arch) or any(
        eff_arch.startswith(p) or (p in eff_arch) for p in COLOR_WORLD_DEFAULT_PREFIXES
    )
    tracks = spec.get("tracks", [])

    hero_clips: list[dict[str, Any]] = []
    secondary_clips: list[dict[str, Any]] = []
    extra_inline_buckets: set[str] = set()

    for tr_idx, tr in enumerate(tracks):
        tname = str(tr.get("name", ""))
        ttype = str(tr.get("type", ""))
        for cl_idx, cl in enumerate(tr.get("clips", [])):
            if ttype != "text" and "text" not in cl:
                continue
            txt = str(cl.get("text") or "").strip()
            if not txt:
                continue
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.04:
                continue
            tau_settle = min(0.30, max(0.12, c_dur * 0.40))
            sz = _clip_settled_size(cl, tau_settle, 52.0)
            hex_c, bucket = _resolve_clip_color_and_bucket(cl, tau_settle)
            for ib in _extract_inline_hue_buckets(txt):
                extra_inline_buckets.add(ib)
            rec = {
                "track": tname,
                "track_idx": tr_idx,
                "clip_idx": cl_idx,
                "name": str(cl.get("name") or _strip_inline_hue_markup(txt)[:28]),
                "text": txt[:40],
                "at": round(c_at, 3),
                "dur": round(c_dur, 3),
                "size": round(sz, 1),
                "color": hex_c,
                "hue_bucket": bucket,
            }
            if _is_hero_text_clip(tname, cl, sz):
                hero_clips.append(rec)
            else:
                secondary_clips.append(rec)

    hero_clips.sort(key=lambda r: (r["at"], r["track_idx"], r["clip_idx"]))
    secondary_clips.sort(key=lambda r: (r["at"], r["track_idx"], r["clip_idx"]))

    accented_heroes = [r for r in hero_clips if r["hue_bucket"] != "neutral_white"]
    neutral_heroes = [r for r in hero_clips if r["hue_bucket"] == "neutral_white"]

    hero_accent_counts: dict[str, int] = {}
    for r in accented_heroes:
        b = r["hue_bucket"]
        hero_accent_counts[b] = hero_accent_counts.get(b, 0) + 1

    secondary_hue_counts: dict[str, int] = {}
    for r in secondary_clips:
        b = r["hue_bucket"]
        secondary_hue_counts[b] = secondary_hue_counts.get(b, 0) + 1

    n_acc = len(accented_heroes)
    ranked_hero_hues = sorted(hero_accent_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    hue_distribution: dict[str, float] = {
        b: round(100.0 * cnt / n_acc, 1)
        for b, cnt in ranked_hero_hues
    } if n_acc > 0 else {}

    distinct_accent_hues = sorted(hero_accent_counts.keys())
    all_distinct_accent_hues = sorted(
        {
            b
            for b in (*hero_accent_counts.keys(), *secondary_hue_counts.keys(), *extra_inline_buckets)
            if b != "neutral_white"
        }
    )

    dominant_hue: str | None = None
    max_share_pct = 0.0
    max_share_ratio = 0.0
    secondary_contrast_hue: str | None = None
    secondary_share_pct = 0.0
    if n_acc > 0 and ranked_hero_hues:
        dominant_hue, dom_cnt = ranked_hero_hues[0]
        max_share_ratio = dom_cnt / float(n_acc)
        max_share_pct = round(100.0 * max_share_ratio, 1)
        if len(ranked_hero_hues) >= 2:
            secondary_contrast_hue = ranked_hero_hues[1][0]
            secondary_share_pct = round(100.0 * ranked_hero_hues[1][1] / float(n_acc), 1)

    polarity_light_count, polarity_light_details = _detect_polarity_light_clips(spec, spec_meta)

    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []
    mono_hue_overuse = False
    rainbow_hue_soup = False
    restrained_palette_exempt = False
    consecutive_repeats: list[dict[str, Any]] = []

    if eff_policy == "color_world_polarity":
        # `v6.0` Default Policy — 1 Primary Signature Hue (`55%–100%`) + `0–1` Secondary Pain/Contrast Hue (`0%–45%`)
        if len(all_distinct_accent_hues) >= 5 or len(distinct_accent_hues) >= 5:
            rainbow_hue_soup = True
            keep_pair = [h for h, _ in ranked_hero_hues[:2]] or all_distinct_accent_hues[:2]
            msg_soup = (
                f"RAINBOW_HUE_SOUP: {len(all_distinct_accent_hues)} distinct neon/accent hue buckets "
                f"({', '.join(all_distinct_accent_hues)}) appear in one video "
                f"(v6.0 Color-World law allows 1 Primary Signature Hue + 0–1 Secondary Contrast Hue)"
            )
            fix_soup = (
                f"consolidate all accented typography into 1 Color World (keep primary '{keep_pair[0]}' at 55%–100%"
                + (f" + secondary contrast '{keep_pair[1]}' <= 45%" if len(keep_pair) > 1 else "")
                + ", use #FAFAFA/#111111 neutrals & #EEF4EA/#FAFAFA polarity flips; or set meta.color_policy='multi_hue_6')"
            )
            warning_codes.append("RAINBOW_HUE_SOUP")
            warnings.append(
                {
                    "code": "RAINBOW_HUE_SOUP",
                    "distinct_accent_hues": all_distinct_accent_hues,
                    "distinct_count": len(all_distinct_accent_hues),
                    "elevate_concern_in_full": True,
                    "message": msg_soup,
                    "fix": fix_soup,
                }
            )
        elif is_strict_2hue_world and len(distinct_accent_hues) > 2 and (n_acc >= 4 and max_share_ratio < 0.55 - 1e-9):
            keep_pair = [h for h, _ in ranked_hero_hues[:2]]
            msg_frag = (
                f"COLOR_WORLD_FRAGMENTED: {len(distinct_accent_hues)} Hero accent buckets ({', '.join(distinct_accent_hues)}) "
                f"dilute primary hue '{dominant_hue}' to {max_share_pct:.1f}% (target 1–2 buckets with primary 55%–100%)"
            )
            fix_frag = (
                f"re-tint extra Hero accents into primary '{keep_pair[0]}' (55%–100%) and at most 1 secondary contrast hue "
                f"'{keep_pair[1]}' (<= 45%)"
            )
            warning_codes.append("COLOR_WORLD_FRAGMENTED")
            warnings.append(
                {
                    "code": "COLOR_WORLD_FRAGMENTED",
                    "distinct_accent_hues": distinct_accent_hues,
                    "primary_share_pct": max_share_pct,
                    "elevate_concern_in_full": True,
                    "message": msg_frag,
                    "fix": fix_frag,
                }
            )
    elif eff_policy == "semantic_4act_jewel":
        # `v7.0/v7.1` Chapter-Scoped 4-Act Jewel Policy (1–4 jewel accents on #FAFAFA, <= 1 jewel hue per beat)
        if len(all_distinct_accent_hues) >= 5 or len(distinct_accent_hues) >= 5:
            rainbow_hue_soup = True
            msg_soup = (
                f"RAINBOW_HUE_SOUP: {len(all_distinct_accent_hues)} distinct neon/accent hue buckets "
                f"({', '.join(all_distinct_accent_hues)}) exceed the 4-Act Jewel budget (<= 4 chapter jewel hues)"
            )
            fix_soup = "consolidate accents into SEMANTIC_4ACT_JEWEL_PALETTES (#F5C451, #FF4D5E, #34D399, #7DD3FC on #FAFAFA)"
            warning_codes.append("RAINBOW_HUE_SOUP")
            warnings.append(
                {
                    "code": "RAINBOW_HUE_SOUP",
                    "distinct_accent_hues": all_distinct_accent_hues,
                    "distinct_count": len(all_distinct_accent_hues),
                    "elevate_concern_in_full": True,
                    "message": msg_soup,
                    "fix": fix_soup,
                }
            )
    else:
        # Opt-in Legacy `multi_hue_6` Policy (`meta.color_policy == "multi_hue_6"`)
        if n_acc >= 4 and dominant_hue is not None and max_share_ratio > 0.42 + 1e-9:
            if is_restrained_arch and len(distinct_accent_hues) >= 2:
                restrained_palette_exempt = True
            else:
                mono_hue_overuse = True
                if is_restrained_arch:
                    restrained_palette_exempt = True
                alt_buckets = [
                    b for b in ("cyan_blue", "mint_emerald", "coral_red", "gold_amber", "violet_purple", "orange_peach")
                    if b != dominant_hue and b not in hero_accent_counts
                ] or [b for b in ("cyan_blue", "mint_emerald", "coral_red", "gold_amber") if b != dominant_hue]
                msg = (
                    f"MONO_HUE_OVERUSE: '{dominant_hue}' accounts for {max_share_pct:.1f}% "
                    f"({hero_accent_counts[dominant_hue]}/{n_acc}) of accented Hero beats (limit <= 42.0%, target <= 35.0%)"
                )
                fix = (
                    f"diversify Hero accent colors across >= 3 semantic hue buckets (e.g. re-tint 2 '{dominant_hue}' "
                    f"Hero clips to {', '.join(alt_buckets[:2])} so each hue stays <= 35%)"
                )
                warning_codes.append("MONO_HUE_OVERUSE")
                warnings.append(
                    {
                        "code": "MONO_HUE_OVERUSE",
                        "dominant_hue": dominant_hue,
                        "share_pct": max_share_pct,
                        "accented_hero_count": n_acc,
                        "elevate_concern_in_full": not is_restrained_arch,
                        "message": msg,
                        "fix": fix,
                    }
                )

        run_start = 0
        while run_start < n_acc:
            run_end = run_start + 1
            cur_b = accented_heroes[run_start]["hue_bucket"]
            while run_end < n_acc and accented_heroes[run_end]["hue_bucket"] == cur_b:
                run_end += 1
            run_len = run_end - run_start
            if run_len >= 3:
                run_slice = accented_heroes[run_start:run_end]
                mid_clip = run_slice[len(run_slice) // 2]
                alt_b = next(
                    (b for b in ("cyan_blue", "mint_emerald", "coral_red", "gold_amber", "violet_purple") if b != cur_b),
                    "cyan_blue",
                )
                rep_rec = {
                    "hue_bucket": cur_b,
                    "run_length": run_len,
                    "start_at": run_slice[0]["at"],
                    "end_at": run_slice[-1]["at"],
                    "clips": [f"{c['name']}@{c['at']:.2f}s" for c in run_slice],
                }
                consecutive_repeats.append(rep_rec)
                msg_r = (
                    f"CONSECUTIVE_HERO_HUE_REPEAT: {run_len} consecutive accented Hero clips "
                    f"({rep_rec['start_at']:.2f}s..{rep_rec['end_at']:.2f}s) repeat '{cur_b}' ({', '.join(rep_rec['clips'][:4])})"
                )
                fix_r = (
                    f"break the {run_len}-clip '{cur_b}' streak by switching Hero clip '{mid_clip['name']}' "
                    f"(at={mid_clip['at']:.2f}s) to a contrasting hue bucket such as '{alt_b}'"
                )
                if "CONSECUTIVE_HERO_HUE_REPEAT" not in warning_codes:
                    warning_codes.append("CONSECUTIVE_HERO_HUE_REPEAT")
                warnings.append(
                    {
                        "code": "CONSECUTIVE_HERO_HUE_REPEAT",
                        "hue_bucket": cur_b,
                        "run_length": run_len,
                        "elevate_concern_in_full": not is_restrained_arch,
                        "message": msg_r,
                        "fix": fix_r,
                    }
                )
            run_start = run_end

    if warnings:
        status = "WARN"
    elif restrained_palette_exempt:
        status = "PASS_RESTRAINED"
    else:
        status = "PASS"

    return {
        "executed": True,
        "status": status,
        "color_policy": eff_policy,
        "archetype": eff_arch or None,
        "tier_used": tier_used,
        "restrained_palette_exempt": restrained_palette_exempt,
        "hero_clips_total": len(hero_clips),
        "accented_hero_count": n_acc,
        "neutral_hero_count": len(neutral_heroes),
        "secondary_clips_total": len(secondary_clips),
        "hue_distribution": hue_distribution,
        "hero_hue_counts": {
            **({"neutral_white": len(neutral_heroes)} if neutral_heroes else {}),
            **hero_accent_counts,
        },
        "secondary_hue_counts": secondary_hue_counts,
        "distinct_accent_hues": distinct_accent_hues,
        "distinct_accent_hue_count": len(distinct_accent_hues),
        "all_distinct_accent_hues": all_distinct_accent_hues,
        "dominant_accent_hue": dominant_hue,
        "primary_signature_hue": dominant_hue,
        "max_accent_share_pct": max_share_pct,
        "primary_signature_share_pct": max_share_pct,
        "secondary_contrast_hue": secondary_contrast_hue,
        "secondary_contrast_share_pct": secondary_share_pct,
        "polarity_light_clips_or_frames": polarity_light_count,
        "polarity_light_details": polarity_light_details,
        "rainbow_hue_soup": rainbow_hue_soup,
        "mono_hue_overuse": mono_hue_overuse,
        "consecutive_repeats": consecutive_repeats,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


def _is_primary_visual_shot_clip(track_name: str, clip: dict[str, Any]) -> bool:
    """Identify full-frame camera/B-roll shots on V1/V2/V3 (excluding vignettes, mattes, transition wipes & small PiPs)."""
    tname_low = track_name.lower()
    if any(tname_low.startswith(pref) for pref in ("trans", "text", "gfx", "band", "ảnh bìa")):
        return False
    cname_low = str(clip.get("name") or "").lower()
    src_low = str(clip.get("src") or "").lower()
    if any(k in cname_low for k in ("dải tối", "color matte", "vignette", "tấm màu", "mũi tên")):
        return False
    if any(k in src_low for k in ("top_shade", "vignette", "panel_")):
        return False
    s0 = float(_eval_kf_param((clip.get("motion") or {}).get("scale"), 0.0, 100.0))
    if s0 < 75.0:
        return False
    return True


def _cut_has_heavy_wgpu_transition(
    cut_t: float,
    prev_cl: dict[str, Any],
    curr_cl: dict[str, Any],
    trans_overlays: list[dict[str, Any]],
) -> bool:
    if curr_cl.get("transition_in") or prev_cl.get("transition_out"):
        return True
    if any(
        (float(ov.get("at", 0.0)) - 0.45) <= cut_t <= (float(ov.get("at", 0.0)) + float(ov.get("dur", 0.0)) + 0.45)
        for ov in trans_overlays
    ):
        return True
    for cl_chk in (prev_cl, curr_cl):
        for fx in cl_chk.get("effects") or []:
            fx_id = str(fx.get("effect") or "").lower()
            if any(tok in fx_id for tok in _HEAVY_WGPU_TRANS_EFFECTS):
                return True
    return False


def _evaluate_cut_bimodal_c7(
    cut_t: float,
    voice_clips: list[tuple[int, str, float, float, dict[str, Any]]],
    words: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluate Bimodal `C7` (`t_voice_in - t_visual_cut`) at visual cut `cut_t`:
      - Verified `true_vocal_jcut`: `t_voice_in - cut_t` in `[-0.850s, -0.140s]` (`[-850ms, -140ms]`),
        where incoming speech on `A1/A2` (or new spoken clause onset after pause) genuinely pre-leads
        the visual cut and continues across `cut_t`.
      - `sloppy_mid_syllable`: accidental voice clip or unbridged word chop in `[-0.130s, -0.010s]`.
      - `clean_post_cut_lead`: post-cut onset in `[-0.009s, +0.120s]`.
      - `continuous_or_silent`: continuous mid-thought breath or pause gap across `cut_t`.
    """
    # 1. Inspect `A1/A2/A3` voice clip onsets near `cut_t`
    jcut_clip_leads: list[float] = []
    sloppy_clip_leads: list[float] = []
    post_clip_leads: list[float] = []
    for _, _, v_at, v_end, v_cl in voice_clips:
        lead_s = v_at - cut_t
        if -0.850 - 1e-4 <= lead_s <= -0.140 + 1e-4 and v_end >= cut_t + 0.04:
            jcut_clip_leads.append(lead_s)
        elif -0.130 - 1e-4 <= lead_s <= -0.010 + 1e-4 and v_end >= cut_t + 0.02:
            # Check if bridged seamlessly by an earlier overlapping voice clip starting in J-cut window
            bridged_by_jcut = any(
                (o_cl is not v_cl)
                and (-0.850 - 1e-4 <= (o_at - cut_t) <= -0.140 + 1e-4)
                and (o_end >= v_at + 0.01)
                for _, _, o_at, o_end, o_cl in voice_clips
            )
            if not bridged_by_jcut:
                sloppy_clip_leads.append(lead_s)
        elif -0.010 < lead_s <= 0.120 + 1e-4:
            post_clip_leads.append(lead_s)

    # 2. Inspect `words` timeline (`[[word, t_start, (optional t_end)], ...]`) if provided
    jcut_word_leads: list[float] = []
    sloppy_word_leads: list[float] = []
    post_word_leads: list[float] = []
    if isinstance(words, list) and words:
        parsed_words: list[tuple[str, float, float]] = []
        for w in words:
            if isinstance(w, (list, tuple)) and len(w) >= 2 and _is_num(w[1]):
                t0 = float(w[1])
                t1 = float(w[2]) if len(w) >= 3 and _is_num(w[2]) else (t0 + 0.20)
                parsed_words.append((str(w[0]), t0, max(t0, t1)))
            elif isinstance(w, dict) and _is_num(w.get("start")):
                t0 = float(w["start"])
                t1 = float(w.get("end", t0 + 0.20))
                parsed_words.append((str(w.get("word", "")), t0, max(t0, t1)))
        parsed_words.sort(key=lambda x: x[1])

        for idx_w, (_, w_t0, _) in enumerate(parsed_words):
            lead_w = w_t0 - cut_t
            if -0.850 - 1e-4 <= lead_w <= -0.140 + 1e-4:
                prev_end = parsed_words[idx_w - 1][2] if idx_w > 0 else -999.0
                prev_start = parsed_words[idx_w - 1][1] if idx_w > 0 else -999.0
                matches_clip_onset = any(abs(v_at - w_t0) <= 0.09 for _, _, v_at, _, _ in voice_clips)
                is_clause_onset = (idx_w == 0) or ((w_t0 - prev_end) >= 0.10) or ((w_t0 - prev_start) >= 0.36) or matches_clip_onset
                # Verify speech continues across or right up to `cut_t`
                clause_reaches_cut = any(
                    (w_t0 <= wt0 <= cut_t + 0.35) and (wt1 >= cut_t - 0.05 or wt0 >= cut_t - 0.12)
                    for _, wt0, wt1 in parsed_words[idx_w:]
                )
                if is_clause_onset and clause_reaches_cut:
                    jcut_word_leads.append(lead_w)
            elif -0.130 - 1e-4 <= lead_w <= -0.010 + 1e-4:
                sloppy_word_leads.append(lead_w)
            elif -0.010 < lead_w <= 0.120 + 1e-4:
                post_word_leads.append(lead_w)

    if sloppy_clip_leads:
        sl = min(sloppy_clip_leads, key=abs)
        return {"cut_at": round(cut_t, 3), "classification": "sloppy_mid_syllable", "lead_ms": round(sl * 1000.0, 1)}

    if jcut_clip_leads or jcut_word_leads:
        cand_j = jcut_clip_leads[0] if jcut_clip_leads else jcut_word_leads[0]
        return {"cut_at": round(cut_t, 3), "classification": "true_vocal_jcut", "lead_ms": round(cand_j * 1000.0, 1)}

    if sloppy_word_leads:
        sw = min(sloppy_word_leads, key=abs)
        return {"cut_at": round(cut_t, 3), "classification": "sloppy_mid_syllable", "lead_ms": round(sw * 1000.0, 1)}

    if post_clip_leads or post_word_leads:
        pl = post_clip_leads[0] if post_clip_leads else post_word_leads[0]
        return {"cut_at": round(cut_t, 3), "classification": "clean_post_cut_lead", "lead_ms": round(pl * 1000.0, 1)}

    return {"cut_at": round(cut_t, 3), "classification": "continuous_or_silent", "lead_ms": None}


def adjudicate_v60_cut_grammar_and_c7(
    spec: dict[str, Any],
    words: list[Any] | None = None,
    rules_items: list[dict[str, Any]] | None = None,
    archetype: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `v6.0` Cut-Grammar & Bimodal `C7` Adjudicator:
    Active when `archetype` is `dviet_*` / `minimal_*` / `story_*` or `meta.cut_grammar == "dviet_4cut"`.
      - Classifies V1 cuts into Clean Hard Cuts (`0`-frame) vs Heavy `wgpu` Transitions, plus True Vocal
        `J-Cuts` (`t_voice_in - t_visual_cut` in `[-850ms, -140ms]`) vs Sloppy Mid-Syllable Cuts (`[-130ms, -10ms]`).
      - Re-adjudicates `edit_rules.py` false-positive errors on `"Mọi điểm cắt có chuyển cảnh"` (and `"Chuyển cảnh đa dạng"`)
        and `"C7 cut_lead"` **ONLY WHEN** uncovered/negative-lead cuts are verified Clean Intentional Hard Cuts
        (`40%–75%` of V1 cuts) or verified True Vocal `J-Cuts` (`[-850ms, -140ms]`), NEVER forgiving sloppy
        mid-syllable cuts in `[-130ms, -10ms]`.
    """
    active = _uses_v60_dviet_4cut_grammar(spec, archetype=archetype, spec_meta=spec_meta)
    eff_arch = _resolve_archetype(spec, archetype=archetype, spec_meta=spec_meta)
    tracks = spec.get("tracks", [])

    v1_track = next(
        (t for t in tracks if t.get("type") == "video" and str(t.get("name", "")).startswith("V1")),
        None,
    ) or next((t for t in tracks if t.get("type") == "video"), None)
    v1_clips = sorted(
        [c for c in (v1_track or {}).get("clips", []) if _is_primary_visual_shot_clip(str((v1_track or {}).get("name", "V1")), c)],
        key=lambda c: float(c.get("at", 0.0)),
    )
    trans_overlays = [
        c
        for tr in tracks
        if str(tr.get("name", "")).lower().startswith(("fx · trans", "trans "))
        for c in tr.get("clips", [])
    ]

    voice_clips: list[tuple[int, str, float, float, dict[str, Any]]] = []
    a_idx = 0
    for tr in tracks:
        if tr.get("type") != "audio":
            continue
        a_idx += 1
        tname = str(tr.get("name", f"A{a_idx}"))
        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.0))
            if c_dur <= 0.0:
                continue
            role = classify_audio_role(tname, cl)
            if role == "voice" or (role is None and a_idx == 1):
                voice_clips.append((a_idx, tname, c_at, c_at + c_dur, cl))

    v1_cuts = [(float(b.get("at", 0.0)), a, b) for a, b in zip(v1_clips, v1_clips[1:]) if float(b.get("at", 0.0)) > 0.05]
    total_v1_cuts = len(v1_cuts)
    clean_hard_cuts: list[float] = []
    wgpu_trans_cuts: list[float] = []
    cut_evaluations: list[dict[str, Any]] = []
    true_jcuts: list[dict[str, Any]] = []
    sloppy_cuts: list[dict[str, Any]] = []

    for cut_t, prev_cl, curr_cl in v1_cuts:
        has_wgpu = _cut_has_heavy_wgpu_transition(cut_t, prev_cl, curr_cl, trans_overlays)
        if has_wgpu:
            wgpu_trans_cuts.append(round(cut_t, 3))
        else:
            clean_hard_cuts.append(round(cut_t, 3))

        ev = _evaluate_cut_bimodal_c7(cut_t, voice_clips=voice_clips, words=words)
        ev["has_wgpu_transition"] = has_wgpu
        cut_evaluations.append(ev)
        if ev["classification"] == "true_vocal_jcut":
            true_jcuts.append(ev)
        elif ev["classification"] == "sloppy_mid_syllable":
            sloppy_cuts.append(ev)

    clean_hard_cut_pct = round(100.0 * len(clean_hard_cuts) / total_v1_cuts, 1) if total_v1_cuts > 0 else 0.0
    wgpu_transition_pct = round(100.0 * len(wgpu_trans_cuts) / total_v1_cuts, 1) if total_v1_cuts > 0 else 0.0
    in_4cut_hard_quota = (39.9 <= clean_hard_cut_pct <= 75.1) if total_v1_cuts > 0 else True
    all_hard_cuts_are_jcuts = bool(clean_hard_cuts) and all(
        any(abs(jc["cut_at"] - hc) <= 0.03 for jc in true_jcuts) for hc in clean_hard_cuts
    )

    adjudicated_rules: list[str] = []
    if active and isinstance(rules_items, list):
        for r_it in rules_items:
            rule_name = str(r_it.get("rule", ""))
            st_cur = str(r_it.get("status", "OK"))
            detail_cur = str(r_it.get("detail", ""))
            if st_cur not in ("LỖI", "CẢNH BÁO"):
                continue

            # (A) Re-adjudicate `"Mọi điểm cắt có chuyển cảnh"` & `"Chuyển cảnh đa dạng"`
            if "Mọi điểm cắt có chuyển cảnh" in rule_name:
                if len(sloppy_cuts) == 0 and (in_4cut_hard_quota or all_hard_cuts_are_jcuts):
                    r_it["original_status"] = st_cur
                    r_it["status"] = "OK"
                    r_it["adjudicated_by"] = "v6.0_dviet_4cut_grammar"
                    r_it["detail"] = (
                        f"{detail_cur} [v6.0 Adjudicated PASS: clean_hard_cut_pct={clean_hard_cut_pct:.1f}% "
                        f"in 40–75% 4-Cut Grammar / {len(true_jcuts)} True Vocal J-Cut(s)]"
                    )
                    adjudicated_rules.append(rule_name)

            elif "Chuyển cảnh đa dạng" in rule_name and st_cur == "CẢNH BÁO":
                # Only forgive when flashy <= 25% and warning was triggered by intentional hard cuts (`?`)
                m_fl = re.search(r"=\s*(\d+)%", detail_cur)
                flash_pct = int(m_fl.group(1)) if m_fl else 0
                if flash_pct <= 25 and len(sloppy_cuts) == 0 and (in_4cut_hard_quota or all_hard_cuts_are_jcuts):
                    r_it["original_status"] = st_cur
                    r_it["status"] = "OK"
                    r_it["adjudicated_by"] = "v6.0_dviet_4cut_grammar"
                    r_it["detail"] = (
                        f"{detail_cur} [v6.0 Adjudicated PASS: 4-Cut Grammar intentional hard cuts ({clean_hard_cut_pct:.1f}%)]"
                    )
                    adjudicated_rules.append(rule_name)

            # (B) Re-adjudicate `"C7 cut_lead"` via Bimodal `C7` (`[0..90ms]` OR `[-850..-140ms]` True Vocal J-Cut)
            elif "C7 cut_lead" in rule_name:
                # Parse timestamps flagged by edit_rules (`3.40s (-65 ms)`) to verify every flagged cut
                flagged_ts = [float(m.group(1)) for m in re.finditer(r"(\d+\.\d+)s\s*\(([+-]?\d+)\s*ms\)", detail_cur)]
                if len(sloppy_cuts) == 0 and flagged_ts and all(
                    any(abs(jc["cut_at"] - ft) <= 0.04 for jc in true_jcuts) for ft in flagged_ts
                ):
                    r_it["original_status"] = st_cur
                    r_it["status"] = "OK"
                    r_it["adjudicated_by"] = "v6.0_bimodal_c7_jcut"
                    jcut_summary = ", ".join(f"{jc['cut_at']:.2f}s ({jc['lead_ms']:+.0f}ms)" for jc in true_jcuts[:6])
                    r_it["detail"] = (
                        f"{detail_cur} [v6.0 Bimodal C7 PASS: verified True Vocal J-Cut(s) in [-850ms..-140ms]: {jcut_summary}]"
                    )
                    adjudicated_rules.append(rule_name)

    return {
        "active": active,
        "archetype": eff_arch or None,
        "v1_cuts_total": total_v1_cuts,
        "clean_hard_cut_count": len(clean_hard_cuts),
        "clean_hard_cut_pct": clean_hard_cut_pct,
        "wgpu_transition_count": len(wgpu_trans_cuts),
        "wgpu_transition_pct": wgpu_transition_pct,
        "in_4cut_hard_quota_40_75": in_4cut_hard_quota,
        "true_vocal_jcut_count": len(true_jcuts),
        "true_vocal_jcuts": true_jcuts,
        "sloppy_mid_syllable_cut_count": len(sloppy_cuts),
        "sloppy_mid_syllable_cuts": sloppy_cuts,
        "cut_evaluations": cut_evaluations,
        "adjudicated_rules": adjudicated_rules,
    }


def _count_bgm_silence_stops(
    tracks: list[dict[str, Any]],
    seq_dur: float,
    san_stats: dict[str, Any] | None = None,
) -> int:
    """Count carved `meta.bgm_stops` plus any explicit `>= 0.48s` silence gaps between BGM/drone clips."""
    carved_cnt = int((san_stats or {}).get("bgm_stops_carved_count", 0))
    gap_windows: list[tuple[float, float]] = []
    for tr in tracks:
        if tr.get("type") != "audio":
            continue
        tname = str(tr.get("name", ""))
        bgm_cls = sorted(
            [c for c in tr.get("clips", []) if _is_bgm_or_drone_clip(tname, c) and float(c.get("dur", 0.0)) > 0],
            key=lambda c: float(c.get("at", 0.0)),
        )
        for a, b in zip(bgm_cls, bgm_cls[1:]):
            gap_s0 = float(a.get("at", 0.0)) + float(a.get("dur", 0.0))
            gap_s1 = float(b.get("at", 0.0))
            if (gap_s1 - gap_s0) >= 0.48 - 1e-4:
                if not any(abs(gap_s0 - x0) <= 0.06 and abs(gap_s1 - x1) <= 0.06 for x0, x1 in gap_windows):
                    gap_windows.append((gap_s0, gap_s1))
        if bgm_cls and seq_dur > 1.0:
            last_end = float(bgm_cls[-1].get("at", 0.0)) + float(bgm_cls[-1].get("dur", 0.0))
            if 0.50 <= (seq_dur - last_end) <= 4.0:
                if not any(abs(last_end - x0) <= 0.06 for x0, _ in gap_windows):
                    gap_windows.append((last_end, seq_dur))
    return max(carved_cnt, len(gap_windows))


def _is_heavy_whoosh_or_impact_sfx(track_name: str, clip: dict[str, Any]) -> bool:
    cname = unicodedata.normalize("NFC", str(clip.get("name") or "")).lower()
    src_stem = unicodedata.normalize("NFC", Path(str(clip.get("src") or "")).stem).lower()
    tname = unicodedata.normalize("NFC", track_name).lower()
    hay = f"{cname} {src_stem} {tname}"
    if any(sf in f"{cname} {src_stem}" for sf in _SOFT_FOLEY_EXCLUSION_HINTS):
        if not any(hw in f"{cname} {src_stem}" for hw in ("whoosh", "swoosh", "impact", "boom", "slam")):
            return False
    return any(hw in hay for hw in _HEAVY_WHOOSH_IMPACT_HINTS)


def _speech_clip_has_micro_fade(clip: dict[str, Any], edge: str) -> bool:
    """Verify whether a speech clip's `in` (`>=0.018s`) or `out` (`>=0.022s`) edge is faded or transition-bridged."""
    if clip.get(f"transition_{edge}"):
        return True
    raw_f = clip.get(f"fade_{edge}")
    min_req = 0.018 if edge == "in" else 0.022
    if _is_num(raw_f) and float(raw_f) >= min_req - 1e-4:
        return True
    g = clip.get("gain_db")
    if _is_animated_kf_list(g):
        g_sorted = sorted(g, key=lambda k: float(k[0]))
        if len(g_sorted) >= 2:
            peak_db = max(float(k[1]) for k in g_sorted)
            c_dur = float(clip.get("dur", 0.0))
            if edge == "in":
                return (float(g_sorted[0][1]) <= peak_db - 12.0) and (float(g_sorted[1][0]) >= 0.018 - 1e-4)
            return (float(g_sorted[-1][1]) <= peak_db - 12.0) and ((c_dur - float(g_sorted[-2][0])) >= 0.022 - 1e-4)
    return False


def audit_transition_and_rhythm_continuity(
    spec: dict[str, Any],
    archetype: str | None = None,
    san_stats: dict[str, Any] | None = None,
    tier_used: str = "fast",
    words: list[Any] | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `v6.0` Cross-Cut Motion Continuity, 4-Cut Grammar, Bimodal `C7` J-Cut & Whoosh Restraint Audit:
      - Inspects `V1`/`V2`/`V3` visual clips and `A1`/`A2`/`A3` (+ SFX & BGM) audio clips.
      - Records `clean_hard_cut_pct`, `true_vocal_jcut_count`, and `bgm_silence_stops_count`.
      - Flags `OVER_TRANSITIONED_SPAM` if `> 45%` of V1 cuts have heavy `wgpu` transitions in
        `dviet_era2_7707_manifesto` / `dviet_vietanh_zdepth_master` mode.
      - Flags `SLOPPY_MID_SYLLABLE_CUT` if any cut has an accidental chop in `[-130ms, -10ms]`
        when `4-Cut Grammar` / Bimodal `C7` is active.
      - Flags `WHOOSH_OVERLOAD` if heavy whoosh/impact SFX exceed `6/min` in `dviet_era2` mode.
      - Detects `DEAD_POSTCUT_CAMERA_HOLD`, verifies speech micro-fades, and counts J/L-cut & SFX bridges.
    """
    eff_arch = _resolve_archetype(spec, archetype, spec_meta)
    is_minimal_tripod_arch = "minimal_intellectual" in eff_arch
    is_dviet_era2 = _is_dviet_era2_archetype(eff_arch)
    is_over_trans_guarded_arch = is_dviet_era2 or ("dviet_vietanh_zdepth_master" in eff_arch)
    tracks = spec.get("tracks", [])
    max_clip_end = max(
        (float(c.get("at", 0.0)) + float(c.get("dur", 0.0)) for tr in tracks for c in tr.get("clips", [])),
        default=0.0,
    )
    seq_dur = float(spec.get("duration") or max_clip_end or 0.0)

    # 1. Collect V1/V2/V3 visual shot tracks
    visual_shot_tracks: list[tuple[str, str, list[dict[str, Any]]]] = []
    v_counter = 0
    for tr in tracks:
        if tr.get("type") != "video":
            continue
        v_counter += 1
        tname = str(tr.get("name", f"V{v_counter}"))
        v_label = f"V{v_counter}"
        is_v123 = (v_counter <= 3) or bool(re.match(r"^\s*v[123]\b", tname, re.IGNORECASE))
        if not is_v123:
            continue
        shots = [cl for cl in tr.get("clips", []) if _is_primary_visual_shot_clip(tname, cl)]
        if shots:
            shots_sorted = sorted(shots, key=lambda c: float(c.get("at", 0.0)))
            visual_shot_tracks.append((v_label, tname, shots_sorted))

    dead_holds: list[dict[str, Any]] = []
    minimal_tripod_exempt: list[dict[str, Any]] = []
    flagged_keys: set[tuple[str, float]] = set()
    visual_cut_times: list[float] = []

    # Intra-track consecutive shot scale-jump -> post-cut hold check
    for v_label, tname, shots in visual_shot_tracks:
        for prev_cl, curr_cl in zip(shots, shots[1:]):
            prev_at = float(prev_cl.get("at", 0.0))
            prev_dur = float(prev_cl.get("dur", 0.0))
            prev_end = prev_at + prev_dur
            curr_at = float(curr_cl.get("at", 0.0))
            curr_dur = float(curr_cl.get("dur", 0.0))
            if curr_at > 0.05 and (seq_dur <= 0.0 or curr_at < seq_dur - 0.05):
                visual_cut_times.append(round(curr_at, 4))
            if (curr_at - prev_end) > 0.15 or curr_dur < 1.2:
                continue

            prev_scale_end = float(_eval_kf_param((prev_cl.get("motion") or {}).get("scale"), prev_dur, 100.0))
            curr_scale_0 = float(_eval_kf_param((curr_cl.get("motion") or {}).get("scale"), 0.0, 100.0))
            curr_scale_045 = float(_eval_kf_param((curr_cl.get("motion") or {}).get("scale"), 0.45, 100.0))
            scale_jump = round(abs(curr_scale_0 - prev_scale_end), 3)
            hold_delta = round(abs(curr_scale_045 - curr_scale_0), 4)

            if scale_jump > 8.0 and hold_delta < 0.15:
                rec_h = {
                    "track": tname,
                    "clip": str(curr_cl.get("name") or f"{v_label}_shot"),
                    "at": round(curr_at, 3),
                    "dur": round(curr_dur, 3),
                    "prev_end_scale": round(prev_scale_end, 2),
                    "scale_0s": round(curr_scale_0, 2),
                    "scale_045s": round(curr_scale_045, 2),
                    "scale_jump_pct": scale_jump,
                    "postcut_delta_pct": hold_delta,
                }
                if is_minimal_tripod_arch or curr_cl.get("static_tripod") is True:
                    minimal_tripod_exempt.append(rec_h)
                else:
                    flagged_keys.add((tname, round(curr_at, 3)))
                    dead_holds.append(rec_h)

    # Cross-track V2/V3 cutaway cutting over V1 check
    if len(visual_shot_tracks) >= 2:
        _, _, v1_shots = visual_shot_tracks[0]
        for v_label, tname, overlay_shots in visual_shot_tracks[1:]:
            for ov_cl in overlay_shots:
                ov_at = float(ov_cl.get("at", 0.0))
                ov_dur = float(ov_cl.get("dur", 0.0))
                ov_end = ov_at + ov_dur
                if ov_at > 0.05 and (seq_dur <= 0.0 or ov_at < seq_dur - 0.05):
                    visual_cut_times.append(round(ov_at, 4))
                if ov_end > 0.05 and (seq_dur <= 0.0 or ov_end < seq_dur - 0.05):
                    visual_cut_times.append(round(ov_end, 4))
                if ov_dur < 1.2 or (tname, round(ov_at, 3)) in flagged_keys:
                    continue
                under_v1 = next(
                    (
                        c for c in v1_shots
                        if float(c.get("at", 0.0)) <= ov_at - 0.02
                        and (float(c.get("at", 0.0)) + float(c.get("dur", 0.0))) > ov_at + 0.02
                    ),
                    None,
                )
                if under_v1 is None:
                    continue
                tau_v1 = ov_at - float(under_v1.get("at", 0.0))
                v1_scale_at_cut = float(_eval_kf_param((under_v1.get("motion") or {}).get("scale"), tau_v1, 100.0))
                ov_s0 = float(_eval_kf_param((ov_cl.get("motion") or {}).get("scale"), 0.0, 100.0))
                ov_s045 = float(_eval_kf_param((ov_cl.get("motion") or {}).get("scale"), 0.45, 100.0))
                scale_jump = round(abs(ov_s0 - v1_scale_at_cut), 3)
                hold_delta = round(abs(ov_s045 - ov_s0), 4)
                if scale_jump > 8.0 and hold_delta < 0.15:
                    rec_ov = {
                        "track": tname,
                        "clip": str(ov_cl.get("name") or f"{v_label}_cutaway"),
                        "at": round(ov_at, 3),
                        "dur": round(ov_dur, 3),
                        "prev_end_scale": round(v1_scale_at_cut, 2),
                        "scale_0s": round(ov_s0, 2),
                        "scale_045s": round(ov_s045, 2),
                        "scale_jump_pct": scale_jump,
                        "postcut_delta_pct": hold_delta,
                    }
                    if is_minimal_tripod_arch or ov_cl.get("static_tripod") is True:
                        minimal_tripod_exempt.append(rec_ov)
                    else:
                        flagged_keys.add((tname, round(ov_at, 3)))
                        dead_holds.append(rec_ov)

    # Deduplicate & merge nearby visual cut timestamps (within 40ms)
    dedup_cuts: list[float] = []
    for ct in sorted(visual_cut_times):
        if not dedup_cuts or (ct - dedup_cuts[-1]) > 0.04:
            dedup_cuts.append(ct)

    # 2. Audio tracks inspection (`A1`/`A2`/`A3` + SFX tracks): speech micro-fades, J/L-cuts & SFX bridges
    voice_clips: list[tuple[int, str, float, float, dict[str, Any]]] = []
    sfx_clips: list[tuple[int, str, float, float, dict[str, Any]]] = []
    a_counter = 0
    for tr in tracks:
        if tr.get("type") != "audio":
            continue
        a_counter += 1
        tname = str(tr.get("name", f"A{a_counter}"))
        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.0))
            if c_dur <= 0.0:
                continue
            role = classify_audio_role(tname, cl)
            if role == "voice" or (role is None and a_counter == 1):
                voice_clips.append((a_counter, tname, c_at, c_at + c_dur, cl))
            elif role == "sfx":
                sfx_clips.append((a_counter, tname, c_at, c_at + c_dur, cl))

    # 2b (`v6.0`): 4-Cut Grammar, Bimodal C7 True Vocal J-Cut, BGM Silence Stops & Whoosh Restraint
    cut_adj = adjudicate_v60_cut_grammar_and_c7(
        spec,
        words=words,
        rules_items=None,
        archetype=eff_arch,
        spec_meta=spec_meta,
    )
    clean_hard_cut_pct = float(cut_adj["clean_hard_cut_pct"])
    wgpu_transition_pct = float(cut_adj["wgpu_transition_pct"])
    v1_cuts_total = int(cut_adj["v1_cuts_total"])
    true_vocal_jcut_count = int(cut_adj["true_vocal_jcut_count"])
    bgm_silence_stops_count = _count_bgm_silence_stops(tracks, seq_dur=seq_dur, san_stats=san_stats)

    heavy_whoosh_clips = [
        {"track": tname, "clip": str(scl.get("name") or "SFX")[:32], "at": round(s_at, 3)}
        for _, tname, s_at, _, scl in sfx_clips
        if _is_heavy_whoosh_or_impact_sfx(tname, scl)
    ]
    heavy_whoosh_count = len(heavy_whoosh_clips)
    eff_dur_min = max(seq_dur, 5.0) / 60.0
    heavy_whoosh_per_min = round(heavy_whoosh_count / eff_dur_min, 2) if seq_dur > 0 else 0.0

    # Speech micro-fade verification
    unpolished_speech_edges: list[dict[str, Any]] = []
    speech_faded_count = 0
    for a_idx, tname, c_at, c_end, cl in voice_clips:
        if (c_end - c_at) < 0.14:
            speech_faded_count += 1
            continue
        in_bridged = any(
            (o_cl is not cl) and (o_at < c_at - 1e-4) and (o_end > c_at + 0.008)
            for _, _, o_at, o_end, o_cl in voice_clips
        )
        out_bridged = any(
            (o_cl is not cl) and (o_at < c_end - 0.008) and (o_end > c_end + 1e-4)
            for _, _, o_at, o_end, o_cl in voice_clips
        )
        ok_in = in_bridged or _speech_clip_has_micro_fade(cl, "in")
        ok_out = out_bridged or _speech_clip_has_micro_fade(cl, "out")
        if ok_in and ok_out:
            speech_faded_count += 1
        else:
            unpolished_speech_edges.append(
                {
                    "track": tname,
                    "clip": str(cl.get("name") or "Voice")[:32],
                    "at": round(c_at, 3),
                    "missing_fade_in": not ok_in,
                    "missing_fade_out": not ok_out,
                }
            )

    # J-cut / cross-track overlap bridges (`cross_track_overlaps`)
    checkerboard_voice_overlaps = 0
    for i in range(len(voice_clips)):
        ai, _, at_i, end_i, _ = voice_clips[i]
        for j in range(i + 1, len(voice_clips)):
            aj, _, at_j, end_j, _ = voice_clips[j]
            if ai == aj:
                continue
            ov = min(end_i, end_j) - max(at_i, at_j)
            if 0.015 <= ov <= 1.50:
                checkerboard_voice_overlaps += 1

    jl_speech_cut_bridges = 0
    for ct in dedup_cuts:
        spans_across = any((v_at + 0.04) <= ct <= (v_end - 0.04) for _, _, v_at, v_end, _ in voice_clips)
        if spans_across:
            jl_speech_cut_bridges += 1

    visual_layer_bridges = 0
    if len(visual_shot_tracks) >= 2:
        v1_cuts_only = [
            float(b.get("at", 0.0))
            for a, b in zip(visual_shot_tracks[0][2], visual_shot_tracks[0][2][1:])
            if float(b.get("at", 0.0)) > 0.05
        ]
        for v1_ct in v1_cuts_only:
            if any(
                (float(ov.get("at", 0.0)) + 0.04) <= v1_ct <= (float(ov.get("at", 0.0)) + float(ov.get("dur", 0.0)) - 0.04)
                for _, _, ov_shots in visual_shot_tracks[1:]
                for ov in ov_shots
            ):
                visual_layer_bridges += 1

    cross_track_overlaps = checkerboard_voice_overlaps + jl_speech_cut_bridges + visual_layer_bridges

    # Transition SFX bridges (`sfx_transition_bridges`: starts >= 60ms before visual cut & spans across cut)
    sfx_bridge_details: list[dict[str, Any]] = []
    for ct in dedup_cuts:
        matching_sfx = [
            (tname, s_at, s_end, scl)
            for _, tname, s_at, s_end, scl in sfx_clips
            if 0.060 - 1e-4 <= (ct - s_at) <= 0.750 and s_end >= ct - 1e-4
        ]
        if matching_sfx:
            tname_m, s_at_m, s_end_m, scl_m = min(matching_sfx, key=lambda m: abs((ct - m[1]) - 0.12))
            sfx_bridge_details.append(
                {
                    "cut_at": round(ct, 3),
                    "sfx_clip": str(scl_m.get("name") or Path(str(scl_m.get("src", "SFX"))).stem)[:36],
                    "track": tname_m,
                    "sfx_at": round(s_at_m, 3),
                    "pre_cut_lead_ms": round((ct - s_at_m) * 1000.0, 1),
                    "sfx_end": round(s_end_m, 3),
                }
            )

    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []
    for dh in dead_holds:
        target_drift = round(dh["scale_0s"] + (3.5 if dh["scale_0s"] <= dh["prev_end_scale"] else -3.0), 1)
        msg_dh = (
            f"DEAD_POSTCUT_CAMERA_HOLD: '{dh['clip']}' on {dh['track']} (at={dh['at']:.2f}s, dur={dh['dur']:.2f}s) "
            f"holds flat scale ({dh['scale_0s']:.2f}% -> {dh['scale_045s']:.2f}%, delta={dh['postcut_delta_pct']:.3f}% < 0.15%) "
            f"right after {dh['scale_jump_pct']:.1f}% jump from {dh['prev_end_scale']:.1f}%"
        )
        fix_dh = (
            f"add frame-0 `cut_kick` or C² `motion.scale` drift on '{dh['clip']}' (at={dh['at']:.2f}s), "
            f"e.g. `[[0.0, {dh['scale_0s']:.1f}, 'easeOut'], [{dh['dur']:.2f}, {target_drift:.1f}, 'linear']]`"
        )
        if "DEAD_POSTCUT_CAMERA_HOLD" not in warning_codes:
            warning_codes.append("DEAD_POSTCUT_CAMERA_HOLD")
        warnings.append(
            {
                "code": "DEAD_POSTCUT_CAMERA_HOLD",
                "clip": dh["clip"],
                "at": dh["at"],
                "elevate_concern_in_full": True,
                "message": msg_dh,
                "fix": fix_dh,
            }
        )

    # `v6.0` OVER_TRANSITIONED_SPAM (`> 45%` heavy wgpu transitions on V1 cuts in Era-2 / Z-Depth master modes)
    wgpu_cnt = int(cut_adj["wgpu_transition_count"])
    if is_over_trans_guarded_arch and (
        (v1_cuts_total >= 3 and wgpu_transition_pct > 45.0 + 1e-6)
        or (v1_cuts_total == 2 and wgpu_cnt == 2)
    ):
        msg_ot = (
            f"OVER_TRANSITIONED_SPAM: {wgpu_cnt}/{v1_cuts_total} ({wgpu_transition_pct:.1f}% > 45.0%) V1 cuts use heavy "
            f"wgpu transitions in '{eff_arch}' (target 40%–75% clean 0-frame hard cuts + True Vocal J-Cuts)"
        )
        fix_ot = (
            "strip redundant `transition_in`/`transition_out` wipes on intra-thought cuts so <= 45% of V1 cuts "
            "carry wgpu transitions and 55%–75% breathe as clean 0-frame hard cuts or vocal J-cuts"
        )
        warning_codes.append("OVER_TRANSITIONED_SPAM")
        warnings.append(
            {
                "code": "OVER_TRANSITIONED_SPAM",
                "wgpu_transition_pct": wgpu_transition_pct,
                "clean_hard_cut_pct": clean_hard_cut_pct,
                "elevate_concern_in_full": True,
                "message": msg_ot,
                "fix": fix_ot,
            }
        )

    # `v6.0` SLOPPY_MID_SYLLABLE_CUT (`[-130ms, -10ms]` accidental chop)
    if cut_adj["active"] and cut_adj["sloppy_mid_syllable_cuts"]:
        sc0 = cut_adj["sloppy_mid_syllable_cuts"][0]
        msg_sc = (
            f"SLOPPY_MID_SYLLABLE_CUT: {len(cut_adj['sloppy_mid_syllable_cuts'])} cut(s) land inside accidental chop "
            f"zone [-130ms, -10ms] (first at {sc0['cut_at']:.2f}s, lead={sc0['lead_ms']:+.1f}ms)"
        )
        fix_sc = (
            f"either shift V1 cut at {sc0['cut_at']:.2f}s earlier so speech starts 0..+90ms after the cut, "
            f"or pre-lead incoming voice to [-650ms..-140ms] for a True Vocal J-Cut"
        )
        warning_codes.append("SLOPPY_MID_SYLLABLE_CUT")
        warnings.append(
            {
                "code": "SLOPPY_MID_SYLLABLE_CUT",
                "cut_at": sc0["cut_at"],
                "lead_ms": sc0["lead_ms"],
                "elevate_concern_in_full": True,
                "message": msg_sc,
                "fix": fix_sc,
            }
        )

    # `v6.0` WHOOSH_OVERLOAD (`> 6/min` heavy whoosh/impact SFX in `dviet_era2` mode)
    if is_dviet_era2 and heavy_whoosh_count >= 2 and heavy_whoosh_per_min > 6.0 + 1e-6:
        msg_wh = (
            f"WHOOSH_OVERLOAD: {heavy_whoosh_count} heavy whoosh/impact SFX in {seq_dur:.1f}s "
            f"({heavy_whoosh_per_min:.1f}/min > 6.0/min limit; target <= 5.0/min in '{eff_arch}')"
        )
        fix_wh = (
            "remove redundant whoosh/impact cues on standard hard cuts and reserve heavy acoustic hits "
            "(<= 5/min) strictly for major act/polarity turns or Music Stop drops"
        )
        warning_codes.append("WHOOSH_OVERLOAD")
        warnings.append(
            {
                "code": "WHOOSH_OVERLOAD",
                "heavy_whoosh_count": heavy_whoosh_count,
                "heavy_whoosh_per_min": heavy_whoosh_per_min,
                "elevate_concern_in_full": True,
                "message": msg_wh,
                "fix": fix_wh,
            }
        )

    polished_cnt = int((san_stats or {}).get("speech_micro_fades_count", 0))
    status = "WARN" if warnings else "PASS"

    return {
        "executed": True,
        "status": status,
        "archetype": eff_arch or None,
        "tier_used": tier_used,
        "visual_cuts_total": len(dedup_cuts),
        "v1_cuts_total": v1_cuts_total,
        "clean_hard_cut_count": int(cut_adj["clean_hard_cut_count"]),
        "clean_hard_cut_pct": clean_hard_cut_pct,
        "wgpu_transition_count": wgpu_cnt,
        "wgpu_transition_pct": wgpu_transition_pct,
        "true_vocal_jcut_count": true_vocal_jcut_count,
        "true_vocal_jcuts": cut_adj["true_vocal_jcuts"],
        "sloppy_mid_syllable_cuts": cut_adj["sloppy_mid_syllable_cuts"],
        "bgm_silence_stops_count": bgm_silence_stops_count,
        "heavy_whoosh_impact_count": heavy_whoosh_count,
        "heavy_whoosh_per_min": heavy_whoosh_per_min,
        "dead_postcut_camera_holds": dead_holds,
        "dead_postcut_camera_hold_count": len(dead_holds),
        "minimal_tripod_exempt_shots": minimal_tripod_exempt,
        "speech_clips_total": len(voice_clips),
        "speech_micro_fades_verified": speech_faded_count,
        "speech_micro_fades_auto_polished": polished_cnt,
        "unpolished_speech_edges": unpolished_speech_edges,
        "cross_track_overlaps": cross_track_overlaps,
        "overlap_breakdown": {
            "checkerboard_voice_overlaps": checkerboard_voice_overlaps,
            "jl_speech_cut_bridges": jl_speech_cut_bridges,
            "visual_layer_bridges": visual_layer_bridges,
        },
        "sfx_transition_bridges": len(sfx_bridge_details),
        "sfx_transition_bridge_details": sfx_bridge_details,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


def _classify_secondary_text_group(
    track_name: str,
    clip: dict[str, Any],
    size_px: float,
    screen_x: float,
    screen_y: float,
    rotation_deg: float,
    seq_w: float = 1080.0,
) -> str:
    """
    Classify a secondary text clip into one of the 4 canonical groups:
      - `G1_lead_sub`: upper/mid lead-ins, ghost stacks, script sub-lines around Hero
      - `G2_quiet_bottom`: `Y >= 1340` word-synced fixed-slot or 1/2-line quiet whisper/conversational sub-text
      - `G3_spatial_shoulder_arc`: off-center `|x - 540| >= 95` shoulder callouts, tilted clusters, or rotated arc segments
      - `G4_ui_micro_labels`: `size <= 42` tags, typewriter labels, active-dim step pills
    """
    tname_low = unicodedata.normalize("NFC", track_name).lower()
    cname_low = unicodedata.normalize("NFC", str(clip.get("name") or "")).lower()
    combined = f"{cname_low} {tname_low}"

    for grp_id in SECONDARY_TEXT_GROUPS:
        if grp_id.lower() in combined:
            return grp_id

    if _is_ghost_echo_text_clip(clip, cname_low):
        return "G1_lead_sub"

    has_g1_hint = any(
        k in combined
        for k in ("s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "dẫn ·", "nhấn ·", "lead", "ghost")
    )
    has_g2_hint = any(k in combined for k in ("s10", "s11", "s12", "phụ đề", "quiet_bottom", "fixed_slot", "whisper"))
    has_g3_hint = any(
        k in combined
        for k in ("s14", "s15", "s16", "s17", "shoulder", "callout", "arc", "tilt", "cluster", "anchor", "side_left", "side_right")
    )
    has_g4_hint = any(
        k in combined
        for k in ("s18", "micro", "typewriter", "pill", "step", "tag", "hud", "badge", "ui_label", "bracket")
    )
    is_tilted = abs(rotation_deg) >= 2.5
    is_off_center = abs(screen_x - (seq_w / 2.0)) >= 95.0

    if has_g4_hint and size_px < 52.0:
        return "G4_ui_micro_labels"
    if has_g3_hint or (is_tilted and not has_g1_hint and not has_g2_hint):
        return "G3_spatial_shoulder_arc"
    if has_g2_hint:
        return "G2_quiet_bottom"
    if has_g1_hint:
        return "G1_lead_sub"

    # G2 quiet bottom conversational/whisper captions (`Y >= 1340` checked BEFORE `size_px <= 35` so 26pt whisper G2 stays G2!)
    if screen_y >= 1340.0:
        return "G2_quiet_bottom"

    if _lane(track_name).lower() == "text_low" and screen_y >= 1200.0:
        return "G2_quiet_bottom"

    if size_px <= 35.0:
        return "G4_ui_micro_labels"

    if is_off_center:
        return "G3_spatial_shoulder_arc"

    return "G1_lead_sub"


def _clip_rotation_deg(clip: dict[str, Any], tau: float) -> float:
    mot = clip.get("motion") or {}
    rot = float(_eval_kf_param(mot.get("rotation"), tau, clip.get("rotation", 0.0) or 0.0))
    if abs(rot) >= 0.1:
        return rot
    for fx in clip.get("effects") or []:
        if fx.get("effect") in ("transform", "rotate_3d"):
            params = fx.get("params") or {}
            for rk in ("rotation", "rot_z"):
                if rk in params:
                    rv = float(_eval_kf_param(params[rk], tau, 0.0))
                    if abs(rv) >= 0.1:
                        return rv
    return 0.0


def _is_graphic_card_overlay_clip(track_idx: int, track_name: str, track_type: str, clip: dict[str, Any]) -> bool:
    """Identify structured graphic cards / props / visual_blocks on `card*`, `gfx*`, `prop*`, `text_img` tracks."""
    if track_type == "audio" or track_type == "text" or "text" in clip:
        return False
    tname_low = unicodedata.normalize("NFC", track_name).lower()
    cname_low = unicodedata.normalize("NFC", str(clip.get("name") or "")).lower()
    src_str = str(clip.get("src") or "")
    src_low = unicodedata.normalize("NFC", src_str).lower()
    if tname_low.startswith(("v1 ", "v1·", "fx · trans", "trans ", "band", "ảnh bìa")) or tname_low == "v1":
        return False
    if track_idx == 0 and not _CARD_GFX_TRACK_RE.search(tname_low):
        return False
    hay = f"{cname_low} {Path(src_low).name if src_low else ''} {tname_low}"
    if any(ex in hay for ex in _BG_PLATE_EXCLUSION_HINTS):
        return False
    if tname_low.startswith("gfx_under") and not any(h in hay for h in _CARD_GFX_NAME_HINTS):
        return False
    if _CARD_GFX_TRACK_RE.search(tname_low):
        return True
    if "/gfx/" in src_low.replace("\\", "/") or any(h in hay for h in _CARD_GFX_NAME_HINTS):
        return True
    return False


@lru_cache(maxsize=256)
def _probe_image_opaque_bbox(path_str: str) -> tuple[int, int, tuple[int, int, int, int]] | None:
    """Return `(img_w, img_h, (ax0, ay0, ax1, ay1))` non-transparent ink bounds for a PNG/WebP/JPEG card."""
    p = Path(path_str)
    if not p.is_file() or p.suffix.lower() not in (".png", ".webp", ".jpg", ".jpeg"):
        return None
    try:
        with Image.open(p) as im:
            w, h = im.size
            if "A" in im.getbands():
                alpha = np.asarray(im.getchannel("A"), dtype=np.uint8)
                ys, xs = np.where(alpha > 24)
                if len(xs) > 0 and len(ys) > 0:
                    return w, h, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            return w, h, (0, 0, w, h)
    except OSError:
        return None


def measure_card_clip_bbox(
    clip: dict[str, Any],
    tau: float,
    seq_w: float = 1080.0,
    seq_h: float = 1920.0,
) -> tuple[float, float, float, float] | None:
    """Compute screen bounding box `(x0, y0, x1, y1)` of a `card*` / `gfx*` / `prop*` overlay clip at `tau`."""
    op = float(_eval_kf_param(clip.get("opacity"), tau, 100.0))
    if op < 25.0:
        return None
    for bk in ("bbox", "ink_bbox", "rect"):
        bv = clip.get(bk)
        if isinstance(bv, (list, tuple)) and len(bv) == 4 and all(_is_num(x) for x in bv):
            return (float(bv[0]), float(bv[1]), float(bv[2]), float(bv[3]))

    mot = clip.get("motion") or {}
    mscale = max(0.05, float(_eval_kf_param(mot.get("scale"), tau, clip.get("scale", 100.0) or 100.0)) / 100.0)
    default_pos = clip.get("position") if isinstance(clip.get("position"), (list, tuple)) else [seq_w / 2.0, seq_h / 2.0]
    mpos = _eval_kf_param(mot.get("position"), tau, default_pos)
    px, py = float(mpos[0]), float(mpos[1])

    src_str = str(clip.get("src") or "")
    img_info = _probe_image_opaque_bbox(src_str) if src_str else None
    if img_info is not None:
        iw, ih, (ax0, ay0, ax1, ay1) = img_info
        anc = _eval_kf_param(mot.get("anchor"), tau, [iw / 2.0, ih / 2.0])
        anc_x, anc_y = float(anc[0]), float(anc[1])
        x0 = px + mscale * (ax0 - anc_x)
        y0 = py + mscale * (ay0 - anc_y)
        x1 = px + mscale * (ax1 - anc_x)
        y1 = py + mscale * (ay1 - anc_y)
        return (round(min(x0, x1), 1), round(min(y0, y1), 1), round(max(x0, x1), 1), round(max(y0, y1), 1))

    # Fallback geometry for synthetic/unrendered card specs
    cw = float(clip.get("width", 820.0)) * mscale
    ch = float(clip.get("height", 420.0)) * mscale
    return (round(px - cw / 2.0, 1), round(py - ch / 2.0, 1), round(px + cw / 2.0, 1), round(py + ch / 2.0, 1))


def _is_all_caps_hero_text(raw_text: str) -> bool | None:
    """Return `True` if ALL-CAPS, `False` if lowercase/mixed-case, or `None` if text has `< 2` alphabetic chars."""
    clean = _strip_inline_hue_markup(unicodedata.normalize("NFC", raw_text))
    letters = [ch for ch in clean if ch.isalpha()]
    if len(letters) < 2:
        return None
    joined = "".join(letters)
    return bool(joined == joined.upper() and joined != joined.lower())


def audit_secondary_text_groups(
    spec: dict[str, Any],
    single_hero_strict: bool | None = None,
    tier_used: str = "fast",
    archetype: str | None = None,
    spec_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `v6.0` Spatial Density (`MAX_ZONES = 2`), `Card <-> Text Mutex`, Lowercase & Breathing Audit:
      - Classifies secondary text clips into `G1_lead_sub`, `G2_quiet_bottom`, `G3_spatial_shoulder_arc`,
        and `G4_ui_micro_labels` (`1–3` curated groups per video is `PASS` — never requires `4/4`).
      - Includes `card*` / `gfx*` / `prop*` bounding boxes in collision checks against `Hero`, `G1`, `G2`,
        `G3`, and `G4`; flags `CARD_TEXT_COLLISION` if any text clip collides with an active graphic card!
      - Samples timeline every `100ms` across ALL overlay tracks (`card*`, `gfx*`, `prop*`, `text*`, `callout*`):
        flags `FRAME_CLUTTER_OVERLOAD` if active distinct overlay zones exceed **`2`** (`3` allowed only
        with whisper `<= 30pt` `G2`) for `> 15%` of video duration!
      - Measures `clean_breathing_frame_pct` (target `>= 12%` zero-overlay frames) + `lowercase_hero_pct`
        (target `>= 70%` lowercase/mixed-case heroes in `dviet_era2` mode; warns `ALL_CAPS_HERO_OVERUSE` if `100%` ALL-CAPS).
    """
    seq_w = float(spec.get("width", 1080))
    seq_h = float(spec.get("height", 1920))
    fps = float(spec.get("fps", 30.0))
    meta = _merged_spec_meta(spec, spec_meta)
    eff_arch = _resolve_archetype(spec, archetype, spec_meta)
    is_dviet_era2 = _is_dviet_era2_archetype(eff_arch)
    strict_flag = (
        bool(single_hero_strict)
        if single_hero_strict is not None
        else bool(meta.get("single_hero_strict") or spec.get("single_hero_strict"))
    )

    group_buckets: dict[str, list[dict[str, Any]]] = {g: [] for g in SECONDARY_TEXT_GROUPS}
    hero_spans: list[dict[str, Any]] = []
    bottom_spans: list[dict[str, Any]] = []
    all_text_spans: list[dict[str, Any]] = []
    card_spans: list[dict[str, Any]] = []

    tracks = spec.get("tracks", [])
    max_clip_end = max(
        (float(c.get("at", 0.0)) + float(c.get("dur", 0.0)) for tr in tracks for c in tr.get("clips", [])),
        default=1.0,
    )
    seq_dur = max(0.20, float(spec.get("duration") or max_clip_end or 1.0))

    for tr_idx, tr in enumerate(tracks):
        tname = str(tr.get("name", ""))
        ttype = str(tr.get("type", ""))
        tname_low = unicodedata.normalize("NFC", tname).lower()
        ln = _lane(tname).lower()
        is_sec_track = (
            ln in ("text_sub", "text_low", "callout")
            or bool(_SECONDARY_TRACK_RE.search(tname_low))
        )
        is_explicit_hero_track = (
            ln in ("text_hi", "text_mid", "text_top", "hero", "title")
            or bool(_HERO_TRACK_RE.search(tname_low))
        )

        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.04:
                continue
            tau_settle = min(0.30, max(0.12, c_dur * 0.40))

            if _is_graphic_card_overlay_clip(tr_idx, tname, ttype, cl):
                c_bbox = measure_card_clip_bbox(cl, tau_settle, seq_w, seq_h)
                if c_bbox is not None:
                    card_spans.append(
                        {
                            "track": tname,
                            "name": str(cl.get("name") or Path(str(cl.get("src") or "card")).stem)[:36],
                            "at": c_at,
                            "end": c_at + c_dur,
                            "dur": round(c_dur, 3),
                            "screen_y": round(0.5 * (c_bbox[1] + c_bbox[3]), 1),
                            "ink_bbox": c_bbox,
                            "clip_ref": cl,
                        }
                    )
                continue

            if ttype != "text" and "text" not in cl:
                continue
            txt = str(cl.get("text") or "").strip()
            if not txt:
                continue
            sz = _clip_settled_size(cl, tau_settle, 52.0)
            pos = _eval_kf_param(cl.get("position"), tau_settle, [seq_w / 2.0, seq_h / 2.0])
            px, py = float(pos[0]), float(pos[1])
            sx, sy = _motion_transform_point(cl, tau_settle, px, py, seq_w, seq_h)
            rot = _clip_rotation_deg(cl, tau_settle)
            cname = str(cl.get("name") or _strip_inline_hue_markup(txt)[:28])
            cname_low = unicodedata.normalize("NFC", cname).lower()
            is_ghost = _is_ghost_echo_text_clip(cl, cname_low)
            has_hero_kw = any(kw in cname_low for kw in _HERO_NAME_KEYWORDS)

            is_primary_hero = (
                (not is_ghost)
                and (
                    (sz >= 64.0 and not (is_sec_track and sz < 76.0 and not has_hero_kw))
                    or (is_explicit_hero_track and sz >= 56.0)
                    or (has_hero_kw and sz >= 56.0)
                )
            )
            is_secondary = is_ghost or ((not is_primary_hero) and (sz < 64.0 or is_sec_track))
            ink_box = measure_text_clip_ink_bbox(cl, tau_settle, seq_w, seq_h)

            if is_primary_hero:
                h_rec = {
                    "role": "Hero",
                    "group": "Hero",
                    "track": tname,
                    "name": cname,
                    "text": txt[:48],
                    "raw_text": txt,
                    "at": c_at,
                    "end": c_at + c_dur,
                    "size": round(sz, 1),
                    "screen_x": round(sx, 1),
                    "screen_y": round(sy, 1),
                    "ink_bbox": ink_box,
                    "is_ghost": False,
                    "clip_ref": cl,
                }
                hero_spans.append(h_rec)
                all_text_spans.append(h_rec)

            if is_secondary:
                grp = _classify_secondary_text_group(tname, cl, sz, sx, sy, rot, seq_w)
                rec_s = {
                    "track": tname,
                    "name": cname,
                    "text": txt[:36],
                    "at": round(c_at, 3),
                    "end": round(c_at + c_dur, 3),
                    "dur": round(c_dur, 3),
                    "size": round(sz, 1),
                    "screen_x": round(sx, 1),
                    "screen_y": round(sy, 1),
                    "rotation": round(rot, 2),
                }
                group_buckets[grp].append(rec_s)
                s_full = {
                    **rec_s,
                    "role": "Secondary",
                    "group": grp,
                    "ink_bbox": ink_box,
                    "is_ghost": is_ghost,
                    "clip_ref": cl,
                }
                if not is_ghost:
                    all_text_spans.append(s_full)
                if grp == "G2_quiet_bottom":
                    bottom_spans.append(s_full)

    total_sec = sum(len(v) for v in group_buckets.values())
    group_counts = {g: len(group_buckets[g]) for g in SECONDARY_TEXT_GROUPS}
    active_group_names = [g for g in SECONDARY_TEXT_GROUPS if group_counts[g] > 0]

    groups_summary: dict[str, dict[str, Any]] = {}
    for g in SECONDARY_TEXT_GROUPS:
        cnt = group_counts[g]
        groups_summary[g] = {
            "count": cnt,
            "share_pct": round(100.0 * cnt / total_sec, 1) if total_sec > 0 else 0.0,
            "sample_clips": [f"{r['name']}@{r['at']:.2f}s" for r in group_buckets[g][:4]],
        }

    # 1. Check Hero-vs-Bottom-Caption collisions
    min_ov_s = max(0.08, 2.5 / fps)
    collisions: list[dict[str, Any]] = []
    for h in hero_spans:
        for b in bottom_spans:
            ov_t0 = max(float(h["at"]), float(b["at"]))
            ov_t1 = min(float(h["end"]), float(b["end"]))
            ov_dur = ov_t1 - ov_t0
            if ov_dur < min_ov_s:
                continue
            t_mid = 0.5 * (ov_t0 + ov_t1)
            op_h = float(_eval_kf_param(h["clip_ref"].get("opacity"), t_mid - float(h["at"]), 100.0))
            op_b = float(_eval_kf_param(b["clip_ref"].get("opacity"), t_mid - float(b["at"]), 100.0))
            if op_h < 35.0 or op_b < 35.0:
                continue

            spatial_overlap = False
            hb, bb = h.get("ink_bbox"), b.get("ink_bbox")
            if hb is not None and bb is not None:
                ov_x = min(hb[2], bb[2]) - max(hb[0], bb[0])
                ov_y = min(hb[3] + 12.0, bb[3]) - max(hb[1] - 12.0, bb[1])
                spatial_overlap = bool(ov_x > 4.0 and ov_y > 2.0)

            if strict_flag or spatial_overlap:
                collisions.append(
                    {
                        "hero_clip": h["name"],
                        "hero_track": h["track"],
                        "bottom_clip": b["name"],
                        "bottom_track": b["track"],
                        "overlap_start_s": round(ov_t0, 3),
                        "overlap_end_s": round(ov_t1, 3),
                        "overlap_dur_s": round(ov_dur, 3),
                        "spatial_ink_overlap": spatial_overlap,
                    }
                )

    # 2 (`v6.0`): Check `Card <-> Text` Bounding-Box Collisions across `Hero`, `G1`, `G2`, `G3`, and `G4`
    card_text_collisions: list[dict[str, Any]] = []
    for cd in card_spans:
        cb = cd.get("ink_bbox")
        if cb is None:
            continue
        for tx in all_text_spans:
            tb = tx.get("ink_bbox")
            if tb is None:
                continue
            ov_t0 = max(float(cd["at"]), float(tx["at"]))
            ov_t1 = min(float(cd["end"]), float(tx["end"]))
            ov_dur = ov_t1 - ov_t0
            if ov_dur < min_ov_s:
                continue
            t_mid = 0.5 * (ov_t0 + ov_t1)
            op_cd = float(_eval_kf_param(cd["clip_ref"].get("opacity"), t_mid - float(cd["at"]), 100.0))
            op_tx = float(_eval_kf_param(tx["clip_ref"].get("opacity"), t_mid - float(tx["at"]), 100.0))
            if op_cd < 35.0 or op_tx < 35.0:
                continue
            ov_x = min(cb[2], tb[2]) - max(cb[0], tb[0])
            ov_y = min(cb[3], tb[3]) - max(cb[1], tb[1])
            if ov_x > 4.0 and ov_y > 4.0:
                card_text_collisions.append(
                    {
                        "card_clip": cd["name"],
                        "card_track": cd["track"],
                        "text_clip": tx["name"],
                        "text_track": tx["track"],
                        "text_group": tx["group"],
                        "overlap_start_s": round(ov_t0, 3),
                        "overlap_end_s": round(ov_t1, 3),
                        "overlap_dur_s": round(ov_dur, 3),
                        "overlap_px": [round(ov_x, 1), round(ov_y, 1)],
                    }
                )

    # 3 (`v6.0`): `100ms` Timeline Spatial Density Sampler (`MAX_ZONES = 2`; `3` allowed w/ whisper `<=30pt` G2)
    n_steps = max(1, int(math.ceil(seq_dur / 0.10)))
    sample_times = [round(min(seq_dur - 1e-4, (i + 0.5) * 0.10), 4) for i in range(n_steps)]
    clean_breathing_samples = 0
    clutter_overload_samples = 0
    max_active_zones = 0

    for ts in sample_times:
        zones_at_t: set[str] = set()
        hero_ys: list[float] = []
        card_ys: list[float] = []
        g2_max_sz = 0.0

        for cd in card_spans:
            if float(cd["at"]) <= ts < float(cd["end"]):
                op_cd = float(_eval_kf_param(cd["clip_ref"].get("opacity"), ts - float(cd["at"]), 100.0))
                if op_cd >= 35.0:
                    cy = float(cd["screen_y"])
                    if not card_ys or all(abs(cy - ey) > 280.0 for ey in card_ys):
                        card_ys.append(cy)
                        zones_at_t.add(f"card_{len(card_ys)}")

        for tx in all_text_spans:
            if float(tx["at"]) <= ts < float(tx["end"]):
                op_tx = float(_eval_kf_param(tx["clip_ref"].get("opacity"), ts - float(tx["at"]), 100.0))
                if op_tx < 35.0:
                    continue
                grp = str(tx["group"])
                if grp == "Hero":
                    hy = float(tx["screen_y"])
                    if not hero_ys or all(abs(hy - ey) > 260.0 for ey in hero_ys):
                        hero_ys.append(hy)
                        zones_at_t.add(f"hero_{len(hero_ys)}")
                else:
                    zones_at_t.add(grp)
                    if grp == "G2_quiet_bottom":
                        g2_max_sz = max(g2_max_sz, float(tx["size"]))

        z_cnt = len(zones_at_t)
        max_active_zones = max(max_active_zones, z_cnt)
        if z_cnt == 0:
            clean_breathing_samples += 1
        else:
            has_whisper_g2 = ("G2_quiet_bottom" in zones_at_t) and (g2_max_sz <= 30.0 + 1e-6)
            allowed_zones = 3 if has_whisper_g2 else 2
            if z_cnt > allowed_zones:
                clutter_overload_samples += 1

    clean_breathing_frame_pct = round(100.0 * clean_breathing_samples / len(sample_times), 1)
    clutter_overload_pct = round(100.0 * clutter_overload_samples / len(sample_times), 1)

    # 4 (`v6.0`): Lowercase / Mixed-Case Hero Ratio (`target >= 70%` in `dviet_era2` mode; warn if `100%` ALL-CAPS)
    hero_case_flags = [
        f for f in (_is_all_caps_hero_text(h.get("raw_text", h["text"])) for h in hero_spans) if f is not None
    ]
    all_caps_hero_count = sum(1 for f in hero_case_flags if f is True)
    lowercase_or_mixed_count = sum(1 for f in hero_case_flags if f is False)
    lowercase_hero_pct = (
        round(100.0 * lowercase_or_mixed_count / len(hero_case_flags), 1)
        if hero_case_flags
        else 100.0
    )

    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []
    if collisions:
        c0 = collisions[0]
        reason_tag = "single_hero_strict=true dual-focal collision" if strict_flag and not c0["spatial_ink_overlap"] else "spatial ink overlap"
        msg_c = (
            f"HERO_BOTTOM_CAPTION_COLLISION: {len(collisions)} Hero vs G2_quiet_bottom collision(s) detected "
            f"({reason_tag}; first: '{c0['hero_clip']}' vs '{c0['bottom_clip']}' at {c0['overlap_start_s']:.2f}s..{c0['overlap_end_s']:.2f}s)"
        )
        fix_c = (
            f"duck/mute G2_quiet_bottom caption '{c0['bottom_clip']}' during Hero window "
            f"[{c0['overlap_start_s']:.2f}s..{c0['overlap_end_s']:.2f}s] so strictly 1 focal point is active"
        )
        warning_codes.append("HERO_BOTTOM_CAPTION_COLLISION")
        warnings.append(
            {
                "code": "HERO_BOTTOM_CAPTION_COLLISION",
                "collision_count": len(collisions),
                "elevate_concern_in_full": True,
                "message": msg_c,
                "fix": fix_c,
            }
        )

    if card_text_collisions:
        ct0 = card_text_collisions[0]
        msg_ct = (
            f"CARD_TEXT_COLLISION: {len(card_text_collisions)} graphic card vs text collision(s) detected "
            f"(first: '{ct0['card_clip']}' on {ct0['card_track']} collides with {ct0['text_group']} '{ct0['text_clip']}' "
            f"at {ct0['overlap_start_s']:.2f}s..{ct0['overlap_end_s']:.2f}s)"
        )
        fix_ct = (
            f"suppress/trim '{ct0['text_clip']}' ({ct0['text_group']}) or reposition '{ct0['card_clip']}' during "
            f"[{ct0['overlap_start_s']:.2f}s..{ct0['overlap_end_s']:.2f}s] to enforce Card <-> Text mutex"
        )
        warning_codes.append("CARD_TEXT_COLLISION")
        warnings.append(
            {
                "code": "CARD_TEXT_COLLISION",
                "collision_count": len(card_text_collisions),
                "elevate_concern_in_full": True,
                "message": msg_ct,
                "fix": fix_ct,
            }
        )

    if clutter_overload_pct > 15.0 + 1e-9:
        msg_cl = (
            f"FRAME_CLUTTER_OVERLOAD: active overlay zones exceed MAX_ZONES=2 (3 w/ <=30pt whisper G2) for "
            f"{clutter_overload_pct:.1f}% (> 15.0% limit; max_zones={max_active_zones}) of video duration"
        )
        fix_cl = (
            "strip concurrent overlays so each 100ms slice holds <= 2 distinct zones (e.g. 1 Hero + 1 G1 sub-line, "
            "or shrink G2 bottom caption to <= 26–30pt whisper size and suppress G1/G3 during graphic cards)"
        )
        warning_codes.append("FRAME_CLUTTER_OVERLOAD")
        warnings.append(
            {
                "code": "FRAME_CLUTTER_OVERLOAD",
                "clutter_overload_pct": clutter_overload_pct,
                "max_active_zones": max_active_zones,
                "elevate_concern_in_full": True,
                "message": msg_cl,
                "fix": fix_cl,
            }
        )

    if is_dviet_era2 and len(hero_case_flags) >= 2 and lowercase_or_mixed_count == 0:
        msg_ac = (
            f"ALL_CAPS_HERO_OVERUSE: 100% ({all_caps_hero_count}/{len(hero_case_flags)}) of Hero clips are ALL-CAPS "
            f"in '{eff_arch}' (v6.0 Era-2 law targets >= 70% lowercase/mixed-case negative-leading Hero typography)"
        )
        fix_ac = (
            "convert >= 70% of Hero display phrases to editorial lowercase or mixed case with tight kiss line-height "
            "(0.78–0.92), reserving ALL-CAPS strictly for <= 30% shock punch words"
        )
        warning_codes.append("ALL_CAPS_HERO_OVERUSE")
        warnings.append(
            {
                "code": "ALL_CAPS_HERO_OVERUSE",
                "all_caps_hero_count": all_caps_hero_count,
                "lowercase_hero_pct": lowercase_hero_pct,
                "elevate_concern_in_full": True,
                "message": msg_ac,
                "fix": fix_ac,
            }
        )

    return {
        "executed": True,
        "status": "WARN" if warnings else "PASS",
        "archetype": eff_arch or None,
        "tier_used": tier_used,
        "single_hero_strict": strict_flag,
        "total_secondary_clips": total_sec,
        "active_secondary_groups": len(active_group_names),
        "active_secondary_group_names": active_group_names,
        "curated_1_to_3_groups_pass": 1 <= len(active_group_names) <= 3 or len(active_group_names) == 0,
        "group_counts": group_counts,
        "groups": groups_summary,
        "card_overlay_clips_total": len(card_spans),
        "card_text_collisions": card_text_collisions,
        "zero_card_text_collision": len(card_text_collisions) == 0,
        "hero_bottom_collisions": collisions,
        "zero_hero_bottom_collision": len(collisions) == 0,
        "max_concurrent_overlay_zones": max_active_zones,
        "clutter_overload_pct": clutter_overload_pct,
        "clean_breathing_frame_pct": clean_breathing_frame_pct,
        "lowercase_hero_pct": lowercase_hero_pct,
        "all_caps_hero_count": all_caps_hero_count,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


# ==============================================================================
# [v7.0] Universal Studio Director Stateless Gatekeeper:
#   1. `CRANIAL_EXCLUSION_AUDIT` (`[hair_top - 48px, chin + 32px]` Foreground Text Lock)
#   2. `INDUSTRY_CRI100_VETO_AUDIT` (`dental_clinic`, `luxury_skincare`, `nail_hair_salon`)
#   3. `inject_micro_bridge_adjustment_layers_fcproj` (`exposure_bloom_landing_3f` & `rack_focus_bridge_13f`)
# ==============================================================================

CRI100_INDUSTRY_SKINS: dict[str, str] = {
    "dental_clinic": "dental_clinic",
    "dental": "dental_clinic",
    "nha_khoa": "dental_clinic",
    "luxury_skincare": "luxury_skincare",
    "skincare": "luxury_skincare",
    "my_pham": "luxury_skincare",
    "nail_hair_salon": "nail_hair_salon",
    "nail_salon": "nail_hair_salon",
    "nail": "nail_hair_salon",
    "hair_salon": "nail_hair_salon",
}

_WARM_FILM_BURN_TOKENS = (
    "film_burn",
    "filmburn",
    "warm_burn",
    "warm film burn",
    "light_leak_warm",
    "amber_burn",
    "fire_burn",
    "orange_flash",
    "vintage_burn",
    "sun_burn",
    "burn_transition",
)

_YELLOW_WARM_LUT_TOKENS = (
    "warm_lut",
    "warmlut",
    "sepia",
    "vintage_yellow",
    "amber_grade",
    "kodak_warm",
    "golden_hour_lut",
    "yellow_tint",
    "warm_film_lut",
    "tungsten_yellow",
    "teal_orange_heavy",
)

_DENTAL_BANNED_SFX_TOKENS = (
    "bone_crack",
    "bone_snap",
    "bone_break",
    "neck_crack",
    "tooth_crack",
    "crunch_bone",
    "dental_drill",
    "drill",
    "bone_crunch",
    "grind_metal",
    "bonesaw",
)

_RVM_CUTOUT_TRACK_HINTS = (
    "rvm",
    "cutout",
    "plane1",
    "plane_1",
    "speaker_fg",
    "subject_matte",
    "person_cutout",
    "tach_nen",
    "tách nền",
)


def _normalize_bbox_screen_px(
    raw_bbox: Any,
    seq_w: float = 1080.0,
    seq_h: float = 1920.0,
) -> tuple[float, float, float, float] | None:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4 or not all(_is_num(v) for v in raw_bbox[:4]):
        return None
    vals = [float(v) for v in raw_bbox[:4]]
    if all(0.0 <= abs(v) <= 1.5 for v in vals) and max(vals) <= 1.5:
        x0, y0, x1, y1 = vals[0] * seq_w, vals[1] * seq_h, vals[2] * seq_w, vals[3] * seq_h
    else:
        x0, y0, x1, y1 = vals[0], vals[1], vals[2], vals[3]
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _parse_timed_bboxes(
    raw_entry: Any,
    seq_w: float,
    seq_h: float,
    seq_dur: float,
) -> list[tuple[float, float, tuple[float, float, float, float]]]:
    """Parse single `[x0, y0, x1, y1]` or list of `{"at": t0, "end"|"dur": ..., "bbox": [...]}` windows."""
    if raw_entry is None:
        return []
    direct = _normalize_bbox_screen_px(raw_entry, seq_w, seq_h)
    if direct is not None:
        return [(0.0, seq_dur, direct)]
    out: list[tuple[float, float, tuple[float, float, float, float]]] = []
    if isinstance(raw_entry, list):
        for item in raw_entry:
            if isinstance(item, dict):
                b = _normalize_bbox_screen_px(item.get("bbox") or item.get("rect"), seq_w, seq_h)
                if b is None:
                    continue
                t0 = float(item.get("at", item.get("start", 0.0)))
                if _is_num(item.get("end")):
                    t1 = float(item["end"])
                elif _is_num(item.get("dur")):
                    t1 = t0 + float(item["dur"])
                else:
                    t1 = seq_dur
                if t1 > t0:
                    out.append((t0, t1, b))
            else:
                b2 = _normalize_bbox_screen_px(item, seq_w, seq_h)
                if b2 is not None:
                    out.append((0.0, seq_dur, b2))
    elif isinstance(raw_entry, dict):
        b = _normalize_bbox_screen_px(raw_entry.get("bbox") or raw_entry.get("rect"), seq_w, seq_h)
        if b is not None:
            t0 = float(raw_entry.get("at", raw_entry.get("start", 0.0)))
            t1 = float(raw_entry["end"]) if _is_num(raw_entry.get("end")) else (t0 + float(raw_entry.get("dur", seq_dur)))
            out.append((t0, t1, b))
    return out


def _is_rvm_cutout_track(track_name: str, clip: dict[str, Any]) -> bool:
    t_low = unicodedata.normalize("NFC", track_name).lower()
    c_low = unicodedata.normalize("NFC", str(clip.get("name") or "")).lower()
    s_low = unicodedata.normalize("NFC", Path(str(clip.get("src") or "")).name).lower()
    hay = f"{t_low} {c_low} {s_low}"
    return any(h in hay for h in _RVM_CUTOUT_TRACK_HINTS)


def _face_metrics_of(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    """`face_metrics` (probe doc / `words_tl.json`) or `subject_framing` (`workspace_context.json`) holding source-px face data."""
    if not isinstance(ctx, dict):
        return None
    for key in ("face_metrics", "subject_framing"):
        fm = ctx.get(key)
        if isinstance(fm, dict) and any(fm.get(k) for k in ("hair_top_y_px", "chin_y_px", "face_bbox_px", "face_bbox_norm")):
            return fm
    return None


def auto_load_face_context(context_path: Path | None, work_dir: Path, words_path: Path | None) -> dict[str, Any] | None:
    """Without `--context`: `workspace_context.json` in the work dir or next to `--words`, else the `face_metrics` of the words doc."""
    if context_path is not None:
        return None
    cands = [work_dir / "workspace_context.json"] + ([words_path.parent / "workspace_context.json"] if words_path else [])
    for cand in cands:
        if cand.is_file():
            try:
                doc = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if _face_metrics_of(doc):
                return doc
    if words_path and words_path.is_file():
        try:
            doc = json.loads(words_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if _face_metrics_of(doc):
            return {"face_metrics": _face_metrics_of(doc)}
    return None


def _source_dims_of_face_metrics(ctx: dict[str, Any], fm: dict[str, Any], probe_src: str | None) -> tuple[float, float] | None:
    """Source frame size of the face data: `resolution`, else `face_bbox_px / face_bbox_norm`, else a cv2 probe of the A-roll."""
    res = ctx.get("resolution")
    if isinstance(res, dict) and _is_num(res.get("width")) and _is_num(res.get("height")):
        return float(res["width"]), float(res["height"])
    px, nm = fm.get("face_bbox_px"), fm.get("face_bbox_norm")
    if isinstance(px, list) and isinstance(nm, list) and len(px) == 4 and len(nm) == 4 and nm[2] > 0.05 and nm[3] > 0.05:
        return round(float(px[2]) / float(nm[2])), round(float(px[3]) / float(nm[3]))
    if probe_src and Path(probe_src).is_file():
        cap = cv2.VideoCapture(probe_src)
        try:
            w, h = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        finally:
            cap.release()
        if w > 0 and h > 0:
            return float(w), float(h)
    return None


def normalize_words_file(words_path: Path, work_dir: Path) -> Path:
    """Write `[[word, t0, t1], ...]` (from a bare list or the probe doc `{words | words_tl}`) under `work_dir`; return that path."""
    doc = json.loads(words_path.read_text(encoding="utf-8"))
    try:
        from probe_and_align import extract_words_list
        words = extract_words_list(doc)
    except ImportError:
        seq = (doc.get("words") if doc.get("words") is not None else doc.get("words_tl")) if isinstance(doc, dict) else doc
        words = [[str(w[0]), float(w[1]), float(w[2])] for w in (seq or []) if isinstance(w, (list, tuple)) and len(w) >= 3]
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / f"{words_path.stem}.words_list.json"
    out.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return out


_PLATE_SRC_RE = re.compile(r"(^|[/_\\ ])kt_?\d{1,2}(?!\d)", re.IGNORECASE)


def spec_has_rendered_plates(spec: dict[str, Any]) -> bool:
    """True when any clip is a V6+ rendered Lane-B typography plate (`typo_kinetic_meta`, `kt_NN_*.mov`, or the cluster template)."""
    for tr in spec.get("tracks", []):
        for cl in tr.get("clips", []):
            src = str(cl.get("src") or "")
            if isinstance(cl.get("typo_kinetic_meta"), dict) or _PLATE_SRC_RE.search(Path(src).name) or "dviet_overlapping_feather_cluster" in src:
                return True
    return False


def audit_cranial_exclusion(
    spec: dict[str, Any],
    *,
    raw_spec: dict[str, Any] | None = None,
    context_doc: dict[str, Any] | None = None,
    spec_meta: dict[str, Any] | None = None,
    san_stats: dict[str, Any] | None = None,
    qa_face_by_time: dict[float, tuple[float, float, float, float]] | None = None,
    tier_used: str = "fast",
) -> dict[str, Any]:
    """
    `v7.0` Gate **`CRANIAL_EXCLUSION_AUDIT`**:
      - Verifies that `100%` of **foreground text clips** (`z_plane != "behind_subject"` and no RVM
        speaker cutout track rendered above them) maintain strict clearance outside the speaker's
        cranial zone **`[hair_top - 48px, chin + 32px]`** (forehead, hair crown, eyebrows, eyes, chin).
      - Resolves cranial bounds from `meta` / `raw_spec` / `context_doc` / V1 clip annotations / QA Haar
        detections (projected through V1 `motion`), or canonical A-Roll speaker framing when V1 is A-Roll.
    """
    seq_w = float(spec.get("width", 1080))
    seq_h = float(spec.get("height", 1920))
    meta = _merged_spec_meta(raw_spec or spec, spec_meta)
    ctx = context_doc if isinstance(context_doc, dict) else {}
    tracks = spec.get("tracks", [])
    anns = (san_stats or {}).get("v70_clip_annotations") or []

    # Map clip annotations by (track, round(at, 3), clip_name)
    ann_by_key: dict[tuple[str, float, str], dict[str, Any]] = {}
    v1_clip_anns: list[dict[str, Any]] = []
    for a in anns:
        k = (str(a.get("track", "")), round(float(a.get("at", 0.0)), 3), str(a.get("clip", "")))
        ann_by_key[k] = a
        if str(a.get("track", "")).lower().startswith("v1") or ("hair_top_y" in a or "chin_y" in a or "face_bbox" in a):
            v1_clip_anns.append(a)

    # Identify V1 track & primary A-Roll source
    v1_track = next(
        (t for t in tracks if t.get("type") == "video" and str(t.get("name", "")).startswith("V1")),
        None,
    ) or next((t for t in tracks if t.get("type") == "video"), None)
    v1_clips = sorted((v1_track or {}).get("clips", []), key=lambda c: float(c.get("at", 0.0)))

    aroll_src_counts: dict[str, float] = {}
    for cl in v1_clips:
        s = str(cl.get("src") or "")
        nm = str(cl.get("name", "")).lower()
        if s and (nm.startswith(("a-roll", "aroll")) or "aroll" in Path(s).name.lower() or "a-roll" in Path(s).name.lower()):
            aroll_src_counts[s] = aroll_src_counts.get(s, 0.0) + float(cl.get("dur", 0.0))
    primary_aroll_src = max(aroll_src_counts, key=aroll_src_counts.get) if aroll_src_counts else None

    _, light_canvas_details = _detect_polarity_light_clips(spec, meta)
    light_intervals = [(float(d["at"]), float(d["at"]) + float(d["dur"])) for d in light_canvas_details]

    # Collect RVM cutout spans by track index so behind-subject text tracks are recognized accurately
    cutout_spans: list[tuple[int, float, float]] = []
    for tr_idx, tr in enumerate(tracks):
        if tr.get("type") != "video":
            continue
        tname = str(tr.get("name", ""))
        for cl in tr.get("clips", []):
            if _is_rvm_cutout_track(tname, cl):
                c0 = float(cl.get("at", 0.0))
                c1 = c0 + float(cl.get("dur", 0.0))
                cutout_spans.append((tr_idx, c0, c1))

    # Extract explicit global cranial hints (`meta` / `raw_spec` / `context_doc`)
    cz_raw = meta.get("cranial_zone") or (raw_spec or {}).get("cranial_zone") or ctx.get("cranial_zone") or {}
    sf_raw = meta.get("subject_framing") or ctx.get("subject_framing") or {}
    explicit_hair_top = (
        cz_raw.get("hair_top_y") if isinstance(cz_raw, dict) and _is_num(cz_raw.get("hair_top_y"))
        else (meta.get("hair_top_y") if _is_num(meta.get("hair_top_y")) else (sf_raw.get("hair_top_y") if isinstance(sf_raw, dict) and _is_num(sf_raw.get("hair_top_y")) else None))
    )
    explicit_chin = (
        cz_raw.get("chin_y") if isinstance(cz_raw, dict) and _is_num(cz_raw.get("chin_y"))
        else (meta.get("chin_y") if _is_num(meta.get("chin_y")) else (sf_raw.get("chin_y") if isinstance(sf_raw, dict) and _is_num(sf_raw.get("chin_y")) else None))
    )
    explicit_face_bbox = _normalize_bbox_screen_px(
        (cz_raw.get("face_bbox") if isinstance(cz_raw, dict) else None)
        or meta.get("face_bbox")
        or _extract_context_face_norm(ctx),
        seq_w,
        seq_h,
    )
    # Source-px face data (`face_metrics` / `subject_framing`) -> projected through the real V1 motion at each probe
    face_src: dict[str, float] | None = None
    fm_ctx = _face_metrics_of(ctx)
    if fm_ctx is not None:
        dims = _source_dims_of_face_metrics(ctx, fm_ctx, primary_aroll_src) or (seq_w, seq_h)
        sw_, sh_ = dims
        fb_px = fm_ctx.get("face_envelope_px") or fm_ctx.get("face_bbox_px")
        fb_norm = fm_ctx.get("face_bbox_norm")
        if not (isinstance(fb_px, list) and len(fb_px) == 4) and isinstance(fb_norm, list) and len(fb_norm) == 4:
            fb_px = [fb_norm[0] * sw_, fb_norm[1] * sh_, fb_norm[2] * sw_, fb_norm[3] * sh_]
        hair_px = fm_ctx.get("hair_top_y_px")
        chin_px = fm_ctx.get("chin_y_px")
        if _is_num(hair_px) or _is_num(chin_px) or fb_px:
            fh_px = max(40.0, float(fb_px[3]) - float(fb_px[1])) if fb_px else 0.23 * sh_
            hair_src = float(hair_px) if _is_num(hair_px) else (float(fb_px[1]) - 0.28 * fh_px if fb_px else float(chin_px) - 0.23 * sh_)
            chin_src = float(chin_px) if _is_num(chin_px) else (float(fb_px[3]) + 0.06 * fh_px if fb_px else hair_src + 0.23 * sh_)
            face_src = {
                "hair": hair_src, "chin": chin_src,
                "x0": float(fb_px[0]) if fb_px else 0.28 * sw_, "x1": float(fb_px[2]) if fb_px else 0.72 * sw_,
                "w": float(sw_), "h": float(sh_),
            }
    no_cranial_data_hits: list[float] = []
    has_explicit_cranial_meta = bool(
        explicit_hair_top is not None or explicit_chin is not None or explicit_face_bbox is not None or v1_clip_anns
        or face_src is not None
    )
    strict_cranial = bool(meta.get("strict_cranial_lock") or meta.get("cranial_lock_strict"))

    def _active_cranial_box_at(ts: float) -> tuple[float, float, float, float] | None:
        """Return `(cran_x0, hair_top - 48, cran_x1, chin + 32)` on A-Roll frames at `ts`, or `None` on B-Roll/Canvas."""
        if any(a - 0.02 <= ts <= b + 0.02 for a, b in light_intervals):
            return None

        v1_cl: dict[str, Any] | None = None
        for cl in v1_clips:
            c0 = float(cl.get("at", 0.0))
            c1 = c0 + float(cl.get("dur", 0.0))
            if c0 <= ts < c1 - 1e-6:
                v1_cl = cl
                break

        if v1_cl is not None and _is_v1_broll_clip(v1_cl, primary_aroll_src):
            # Check if this specific clip explicitly declared a face/cranial zone anyway
            c_ann = next(
                (a for a in v1_clip_anns if float(a["at"]) - 0.02 <= ts <= float(a["at"]) + float(a["dur"]) + 0.02),
                None,
            )
            if not c_ann:
                return None

        # 1. Per-shot annotation on V1 clip
        shot_ann = next(
            (a for a in v1_clip_anns if float(a["at"]) - 0.02 <= ts <= float(a["at"]) + float(a["dur"]) + 0.02),
            None,
        )
        if shot_ann:
            fb_s = _normalize_bbox_screen_px(shot_ann.get("face_bbox"), seq_w, seq_h)
            ht_s = float(shot_ann["hair_top_y"]) if _is_num(shot_ann.get("hair_top_y")) else None
            ch_s = float(shot_ann["chin_y"]) if _is_num(shot_ann.get("chin_y")) else None
            if fb_s is not None:
                fh_s = max(40.0, fb_s[3] - fb_s[1])
                ht = ht_s if ht_s is not None else (fb_s[1] - 0.28 * fh_s)
                ch = ch_s if ch_s is not None else (fb_s[3] + 0.06 * fh_s)
                return (fb_s[0] - 48.0, ht - 48.0, fb_s[2] + 48.0, ch + 32.0)
            if ht_s is not None or ch_s is not None:
                ht = ht_s if ht_s is not None else (float(ch_s) - 0.23 * seq_h)  # type: ignore[arg-type]
                ch = ch_s if ch_s is not None else (ht + 0.23 * seq_h)
                return (0.26 * seq_w - 48.0, ht - 48.0, 0.74 * seq_w + 48.0, ch + 32.0)

        # 2. Direct QA Haar detection near `ts`
        if qa_face_by_time:
            near_qa = next((bx for qt, bx in qa_face_by_time.items() if abs(qt - ts) <= 0.12), None)
            if near_qa is not None:
                fx0, fy0, fx1, fy1 = near_qa
                fh_q = max(40.0, fy1 - fy0)
                return (fx0 - 48.0, (fy0 - 0.28 * fh_q) - 48.0, fx1 + 48.0, (fy1 + 0.06 * fh_q) + 32.0)

        # 3a. Source-px `face_metrics` projected through the real V1 `motion` (anchor defaults to the source centre)
        if face_src is not None and explicit_hair_top is None and explicit_chin is None and v1_cl is not None:
            tau = ts - float(v1_cl.get("at", 0.0))
            clip_src = {**v1_cl, "motion": {**(v1_cl.get("motion") or {}), "anchor": (v1_cl.get("motion") or {}).get("anchor") or [face_src["w"] / 2.0, face_src["h"] / 2.0]}}
            px0, py_hair = _motion_transform_point(clip_src, tau, face_src["x0"], face_src["hair"], seq_w, seq_h)
            px1, py_chin = _motion_transform_point(clip_src, tau, face_src["x1"], face_src["chin"], seq_w, seq_h)
            return (min(px0, px1) - 48.0, min(py_hair, py_chin) - 48.0, max(px0, px1) + 48.0, max(py_hair, py_chin) + 32.0)

        # 3. Explicit meta / context cranial coordinates (projected through V1 `motion` if `face_bbox` is source-space)
        if explicit_hair_top is not None or explicit_chin is not None:
            ht_e = float(explicit_hair_top) if explicit_hair_top is not None else (float(explicit_chin) - 0.23 * seq_h)  # type: ignore[arg-type]
            ch_e = float(explicit_chin) if explicit_chin is not None else (ht_e + 0.23 * seq_h)
            cx0 = explicit_face_bbox[0] if explicit_face_bbox is not None else 0.28 * seq_w
            cx1 = explicit_face_bbox[2] if explicit_face_bbox is not None else 0.72 * seq_w
            return (cx0 - 48.0, ht_e - 48.0, cx1 + 48.0, ch_e + 32.0)

        if explicit_face_bbox is not None:
            if v1_cl is not None:
                tau = ts - float(v1_cl.get("at", 0.0))
                sx0, sy0 = _motion_transform_point(v1_cl, tau, explicit_face_bbox[0], explicit_face_bbox[1], seq_w, seq_h)
                sx1, sy1 = _motion_transform_point(v1_cl, tau, explicit_face_bbox[2], explicit_face_bbox[3], seq_w, seq_h)
                fx0, fy0, fx1, fy1 = min(sx0, sx1), min(sy0, sy1), max(sx0, sx1), max(sy0, sy1)
            else:
                fx0, fy0, fx1, fy1 = explicit_face_bbox
            fh_e = max(40.0, fy1 - fy0)
            return (fx0 - 48.0, (fy0 - 0.28 * fh_e) - 48.0, fx1 + 48.0, (fy1 + 0.06 * fh_e) + 32.0)

        # 4. No cranial data for a verified A-Roll frame -> explicit `CRANIAL_NO_DATA` warning (no guessed box)
        if v1_cl is not None:
            cname_v1 = str(v1_cl.get("name") or "").lower()
            src_v1 = str(v1_cl.get("src") or "").lower()
            is_aroll = (
                cname_v1.startswith(("a-roll", "aroll"))
                or "aroll" in Path(src_v1).name
                or "a-roll" in Path(src_v1).name
                or (primary_aroll_src is not None and _same_media_path(str(v1_cl.get("src") or ""), primary_aroll_src))
            )
            if is_aroll:
                no_cranial_data_hits.append(ts)  # no face data anywhere: report it, never invent a box

        return None

    # Map typo_kinetic_annotations by (track, round(at, 3), clip_name) as well
    tkm_anns = (san_stats or {}).get("typo_kinetic_annotations") or []
    tkm_by_key: dict[tuple[str, float, str], dict[str, Any]] = {}
    for ta in tkm_anns:
        tk_k = (str(ta.get("track", "")), round(float(ta.get("at", 0.0)), 3), str(ta.get("clip", "")))
        if isinstance(ta.get("typo_kinetic_meta"), dict):
            tkm_by_key[tk_k] = ta["typo_kinetic_meta"]

    # Also build a lookup of raw_spec clips so direct (unsanitized) calls can inspect inline `typo_kinetic_meta`
    raw_tkm_by_key: dict[tuple[str, float, str], dict[str, Any]] = {}
    if isinstance(raw_spec, dict):
        for r_tr in raw_spec.get("tracks") or []:
            r_tname = str(r_tr.get("name", ""))
            for r_cl in r_tr.get("clips") or []:
                if isinstance(r_cl.get("typo_kinetic_meta"), dict):
                    r_cname = str(r_cl.get("name") or r_cl.get("text") or "")
                    raw_tkm_by_key[(r_tname, round(float(r_cl.get("at", 0.0)), 3), r_cname)] = r_cl["typo_kinetic_meta"]

    def _resolve_lane_b_typo_meta(tname_s: str, cl_obj: dict[str, Any], c_at_s: float, c_ann_obj: dict[str, Any]) -> dict[str, Any] | None:
        if isinstance(cl_obj.get("typo_kinetic_meta"), dict):
            return cl_obj["typo_kinetic_meta"]
        if isinstance(c_ann_obj.get("typo_kinetic_meta"), dict):
            return c_ann_obj["typo_kinetic_meta"]
        cname_s = str(cl_obj.get("name") or cl_obj.get("text") or "")
        k_lookup = (tname_s, round(c_at_s, 3), cname_s)
        if k_lookup in tkm_by_key:
            return tkm_by_key[k_lookup]
        if k_lookup in raw_tkm_by_key:
            return raw_tkm_by_key[k_lookup]
        src_s = str(cl_obj.get("src") or "")
        sidecar = _load_sidecar_typo_meta(src_s) if src_s else None
        if sidecar is not None:
            return sidecar
        # Detect unlabeled Lane-B hero typography plates (`c01..c15.png`, `kt_01_kt01.mov`, `dviet_overlapping_feather_cluster`)
        hay_s = unicodedata.normalize("NFC", f"{tname_s} {cname_s} {Path(src_s).name if src_s else ''}").lower()
        if _HERO_PNG_STAMP_RE.search(src_s) or any(
            tok in hay_s
            for tok in ("dviet_overlapping_feather_cluster", "kinetic typo", "hero typo", "kt_0", "kt_1", "kt01", "kt02", "kt03", "kt04", "kt05", "kt06", "kt07", "kt08", "kt09", "kt10", "kt11", "kt12")
        ):
            return {"inferred_lane_b_typo_plate": True}
        return None

    def _measure_lane_b_plate_ink_bbox(
        cl_obj: dict[str, Any],
        tkm: dict[str, Any],
        tau_s: float,
    ) -> tuple[float, float, float, float] | None:
        op_v = float(_eval_kf_param(cl_obj.get("opacity"), tau_s, 100.0))
        if op_v < 25.0:
            return None
        mot = cl_obj.get("motion") if isinstance(cl_obj.get("motion"), dict) else {}
        def_pos = cl_obj.get("position") if isinstance(cl_obj.get("position"), (list, tuple)) else [
            float(tkm.get("pos_x", seq_w * 0.5)),
            float(tkm.get("pos_y", seq_h * 0.5)),
        ]
        mpos = _eval_kf_param(mot.get("position"), tau_s, def_pos)
        cur_px, cur_py = float(mpos[0]), float(mpos[1])
        mscale = max(0.05, float(_eval_kf_param(mot.get("scale"), tau_s, cl_obj.get("scale", 100.0) or 100.0)) / 100.0)

        ib_scr = _normalize_bbox_screen_px(tkm.get("ink_bbox_screen") or cl_obj.get("ink_bbox_screen"), seq_w, seq_h)
        if ib_scr is not None:
            # v7.9.3: ink_bbox_screen is the placement at scale 100 around (pos_x, pos_y); motion.scale grows it around the position
            ref_x = float(tkm["pos_x"]) if _is_num(tkm.get("pos_x")) else cur_px
            ref_y = float(tkm["pos_y"]) if _is_num(tkm.get("pos_y")) else cur_py
            return (round(cur_px + mscale * (ib_scr[0] - ref_x), 1), round(cur_py + mscale * (ib_scr[1] - ref_y), 1),
                    round(cur_px + mscale * (ib_scr[2] - ref_x), 1), round(cur_py + mscale * (ib_scr[3] - ref_y), 1))

        src_s = str(cl_obj.get("src") or "")
        if src_s and _probe_image_opaque_bbox(src_s) is not None:
            return measure_card_clip_bbox(cl_obj, tau_s, seq_w, seq_h)

        raw_pw = float(tkm.get("ink_width_px") or tkm.get("plate_width") or tkm.get("width") or cl_obj.get("width") or 760.0)
        raw_ph = float(tkm.get("ink_height_px") or tkm.get("plate_height") or tkm.get("height") or cl_obj.get("height") or 320.0)
        eff_w = min(840.0, raw_pw * 0.78 if raw_pw >= 960.0 else raw_pw) * mscale
        if raw_ph >= 1400.0:
            if _is_num(tkm.get("safe_y")) or _is_num(tkm.get("render_y")):
                center_y = float(tkm.get("safe_y") if _is_num(tkm.get("safe_y")) else tkm["render_y"])
            elif str(tkm.get("rail") or "").lower() == "upper_editorial_stage":
                center_y = 380.0
            elif str(tkm.get("rail") or "").lower() == "chest_tactile_rail":
                center_y = 1420.0
            else:
                center_y = cur_py
            eff_h = 240.0 * mscale
        else:
            center_y = cur_py
            eff_h = (float(tkm["ink_height_px"]) if _is_num(tkm.get("ink_height_px")) else (raw_ph * 0.70)) * mscale
        return (
            round(cur_px - 0.5 * eff_w, 1),
            round(center_y - 0.5 * eff_h, 1),
            round(cur_px + 0.5 * eff_w, 1),
            round(center_y + 0.5 * eff_h, 1),
        )

    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []
    foreground_clips_audited = 0
    foreground_lane_b_plates_audited = 0
    behind_subject_exempt = 0
    unaudited_no_data = 0

    for tr_idx, tr in enumerate(tracks):
        ttype = str(tr.get("type", ""))
        tname = str(tr.get("name", ""))
        if ttype == "audio":
            continue
        ln = _lane(tname)
        for cl in tr.get("clips", []):
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.04:
                continue
            is_text_clip = (ttype == "text") or ("text" in cl)
            txt = str(cl.get("text") or "").strip() if is_text_clip else ""
            cname_lookup = str(cl.get("name") or (txt[:28] if is_text_clip else ""))
            c_ann = ann_by_key.get((tname, round(c_at, 3), cname_lookup), {})

            lane_b_tkm: dict[str, Any] | None = None
            if is_text_clip:
                if not txt:
                    continue
                cname = cname_lookup
            else:
                if tr_idx == 0 and tname.lower().startswith("v1"):
                    continue
                lane_b_tkm = _resolve_lane_b_typo_meta(tname, cl, c_at, c_ann)
                if lane_b_tkm is None:
                    continue
                cname = str(cl.get("name") or Path(str(cl.get("src") or "plate")).name)[:36]
                txt = str(lane_b_tkm.get("main_text") or lane_b_tkm.get("accent_text") or cname)

            tau_settle = min(0.30, max(0.12, c_dur * 0.40))
            t_probe = round(c_at + tau_settle, 3)

            z_plane_val = str(
                (lane_b_tkm or {}).get("z_plane")
                or c_ann.get("z_plane")
                or cl.get("z_plane")
                or ""
            ).strip().lower()
            is_behind = (
                z_plane_val == "behind_subject"
                or "behind" in tname.lower()
                or any(ct_idx > tr_idx and ct_0 <= t_probe <= ct_1 for ct_idx, ct_0, ct_1 in cutout_spans)
            )
            if is_behind:
                behind_subject_exempt += 1
                continue

            # Ruling R208 `<1.5s` opening hook exemption ONLY when explicit cranial lock/meta was not forced
            if (not has_explicit_cranial_meta) and (not strict_cranial) and (ln != "text_low"):
                if (c_at < 1.5 and (c_at + c_dur) <= 1.60) or ("hook" in cname.lower() and c_at < 1.5 and c_dur <= 1.55):
                    continue

            n_no_data = len(no_cranial_data_hits)
            cran_box = _active_cranial_box_at(t_probe)
            if cran_box is None:
                if len(no_cranial_data_hits) > n_no_data:
                    unaudited_no_data += 1
                continue

            if is_text_clip:
                ink = measure_text_clip_ink_bbox(cl, tau_settle, seq_w, seq_h)
            else:
                ink = _measure_lane_b_plate_ink_bbox(cl, lane_b_tkm or {}, tau_settle)
            if ink is None:
                continue

            foreground_clips_audited += 1
            if not is_text_clip:
                foreground_lane_b_plates_audited += 1

            ix0, iy0, ix1, iy1 = ink
            cx0, cy0, cx1, cy1 = cran_box
            ov_x = min(ix1, cx1) - max(ix0, cx0)
            ov_y = min(iy1, cy1) - max(iy0, cy0)

            if ov_x > 4.0 and ov_y > 4.0:
                if is_text_clip:
                    pos_val = _eval_kf_param(cl.get("position"), tau_settle, [seq_w / 2.0, seq_h / 2.0])
                else:
                    mot_c = cl.get("motion") if isinstance(cl.get("motion"), dict) else {}
                    pos_val = _eval_kf_param(mot_c.get("position"), tau_settle, cl.get("position") or [seq_w / 2.0, 0.5 * (iy0 + iy1)])
                cur_py = float(pos_val[1])
                cran_mid_y = 0.5 * (cy0 + cy1)
                rec_upper_y = max(196.0, round(cur_py - (iy1 - (cy0 - 8.0)), 1))
                rec_chest_y = min(1516.0, max(1382.4, round(cur_py + ((cy1 + 8.0) - iy0), 1)))
                best_fix_y = rec_upper_y if (cur_py <= cran_mid_y and cy0 >= 320.0) else rec_chest_y
                best_rail_lbl = "Upper Editorial Stage" if best_fix_y == rec_upper_y else "Chest Tactile Rail"
                kind_lbl = "foreground text" if is_text_clip else "foreground Lane-B typography plate"

                msg_v = (
                    f"CRANIAL_EXCLUSION_VIOLATION: {kind_lbl} '{cname}' on '{tname}' (at={c_at:.2f}s) "
                    f"ink y=[{iy0:.1f}..{iy1:.1f}] invades Cranial Lock [hair_top-48={cy0:.1f}px .. chin+32={cy1:.1f}px] "
                    f"by {ov_y:.1f}px"
                )
                fix_v = (
                    f"use `resolve_dual_rail_safe_y(...)` -> move '{cname}' (at={c_at:.2f}s) `position[1]` to "
                    f"{best_rail_lbl} (`y={best_fix_y:.1f}`)"
                )
                rec_v = {
                    "track": tname,
                    "clip": cname,
                    "clip_kind": "text" if is_text_clip else "lane_b_typo_plate",
                    "text": txt[:36],
                    "at": round(c_at, 3),
                    "probe_t": t_probe,
                    "ink_bbox": [round(ix0, 1), round(iy0, 1), round(ix1, 1), round(iy1, 1)],
                    "cranial_lock_bbox": [round(cx0, 1), round(cy0, 1), round(cx1, 1), round(cy1, 1)],
                    "overlap_y_px": round(ov_y, 1),
                    "recommended_y": best_fix_y,
                    "recommended_rail": best_rail_lbl,
                    "fix": fix_v,
                }
                violations.append(rec_v)
                if "CRANIAL_EXCLUSION_VIOLATION" not in warning_codes:
                    warning_codes.append("CRANIAL_EXCLUSION_VIOLATION")
                warnings.append(
                    {
                        "code": "CRANIAL_EXCLUSION_VIOLATION",
                        "severity": "ERROR" if strict_cranial else "WARN",
                        "elevate_concern_in_full": True,
                        "message": msg_v,
                        "fix": fix_v,
                        **rec_v,
                    }
                )

    if unaudited_no_data:
        warning_codes.append("CRANIAL_NO_DATA")
        warnings.append(
            {
                "code": "CRANIAL_NO_DATA",
                "severity": "WARN",
                "message": (
                    f"no cranial data: {unaudited_no_data} foreground clip(s) over A-roll were not audited "
                    "(no cranial_zone / face_metrics / --context)"
                ),
                "fix": "pass --context workspace_context.json (or keep it in the work dir / next to --words) so face_metrics are projected through the V1 motion",
            }
        )
    return {
        "executed": True,
        "gate": "CRANIAL_EXCLUSION_AUDIT",
        "status": "FAIL" if (violations and strict_cranial) else ("WARN" if (violations or unaudited_no_data) else "PASS"),
        "unaudited_no_cranial_data": unaudited_no_data,
        "strict_cranial_lock": strict_cranial,
        "foreground_text_clips_audited": foreground_clips_audited,
        "foreground_lane_b_plates_audited": foreground_lane_b_plates_audited,
        "behind_subject_zdepth_exempt": behind_subject_exempt,
        "violation_count": len(violations),
        "violations": violations,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


# ==============================================================================
# v7.4.0 Profiles: `--profile {default,dviet}` + `--audio-profile {platform,studio_14,tiktok_loud}` (choices come from the preset file)
# ==============================================================================
PROFILE_OVERRIDES_PATH = SKILL_ROOT / "presets" / "profile_overrides.json"
_FLASH_FAMILY_TOKENS = ("flash", "flicker", "strobe", "shutter")
_WASH_FAMILY_TOKENS = _WARM_FILM_BURN_TOKENS + ("light_leak", "lightleak", "wash")
_DVIET_DEFAULT_CAPS = {"max_event_s": 0.6, "max_flash_family_share": 0.20, "min_gap_cuts": 4}


@lru_cache(maxsize=1)
def _load_profile_overrides() -> dict[str, Any]:
    try:
        return json.loads(PROFILE_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read {PROFILE_OVERRIDES_PATH}: {exc}") from exc


def resolve_audio_profile(name: str | None) -> dict[str, Any]:
    """Return the `audio_profiles[name]` block (default `platform` = historical -16 LUFS / -1.5 dBTP behaviour)."""
    key = name or "platform"
    profiles = _load_profile_overrides().get("audio_profiles", {})
    if key not in profiles:
        raise ValueError(f"unknown --audio-profile {key!r}; expected one of {sorted(profiles)}")
    return profiles[key]


def profile_limiter_db(prof: dict[str, Any]) -> float:
    """Default master limiter ceiling of an audio profile: `limiter_db_v793` when present (v7.9.3, studio_14 -1.3 dB: the old
    `limiter_db` -2.2 was copied from `platform` and kept Look S below -14 LUFS), else `limiter_db`."""
    return float(prof.get("limiter_db_v793", prof["limiter_db"]))


def _lufs_target_shift(audio_profile: str | None, target_lufs: float) -> float:
    """LU the pre-trims move from the -16 LUFS baseline: every profile except `tiktok_loud` (its own tuned trims) follows its target."""
    return 0.0 if audio_profile == "tiktok_loud" else round(float(target_lufs) - (-16.0), 2)


def _event_kind(hay: str) -> tuple[str, str] | None:
    """(family, kind) of a flash/wash token inside `hay`, else None."""
    low = hay.lower()
    for tok in _FLASH_FAMILY_TOKENS:
        if tok in low:
            m = re.search(rf"[a-z0-9_]*{tok}[a-z0-9_]*", low)
            return "flash", (m.group(0) if m else tok)
    for tok in _WASH_FAMILY_TOKENS:
        if tok in low:
            return "wash", tok
    return None


def audit_dviet_wash_flash_caps(spec: dict[str, Any], caps: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Profile `dviet`: scopes the warm-film-burn veto and white-flash ban. A wash/flash event may be lifted only when
      - it lasts <= `max_event_s` (0.6 s),
      - the flash family stays <= `max_flash_family_share` (20%) of V1 cuts (`lift_allowed`),
      - (SOFT lint) no kind repeats within `min_gap_cuts` (4) cuts.
    Does NOT touch the 4-Cut Grammar / `OVER_TRANSITIONED_SPAM` (still HARD in `audit_transition_and_rhythm_continuity`).
    """
    cfg = {**_DVIET_DEFAULT_CAPS, **(caps or _load_profile_overrides().get("profiles", {}).get("dviet", {}).get("wash_flash", {}))}
    tracks = [t for t in spec.get("tracks", []) if str(t.get("type", "")) != "audio"]
    v1 = next((t for t in tracks if str(t.get("name", "")).strip().upper().startswith("V1")), tracks[0] if tracks else {"clips": []})
    v1_starts = sorted(float(c.get("at", 0.0)) for c in v1.get("clips", []))
    n_cuts = max(1, len(v1_starts) - 1)

    def cut_index(t: float) -> int:
        return sum(1 for a in v1_starts[1:] if a <= t + 1e-6)

    events: list[dict[str, Any]] = []
    for tr in tracks:
        is_v1 = tr is v1
        for cl in tr.get("clips", []):
            at = float(cl.get("at", 0.0))
            fields = [str(cl.get("name") or ""), str(cl.get("preset") or ""), Path(str(cl.get("src") or "")).name,
                      json.dumps(cl.get("transition_in") or {}, ensure_ascii=False), json.dumps(cl.get("transition_out") or {}, ensure_ascii=False)]
            hit = _event_kind(" ".join(fields if not is_v1 else fields[3:]))
            if hit is None:
                continue
            fam, kind = hit
            dur = float(cl.get("dur", 0.0)) if not is_v1 else float((cl.get("transition_in") or {}).get("dur", 0.3) or 0.3)
            events.append({"family": fam, "kind": kind, "at": round(at, 3), "dur": round(dur, 3),
                           "track": str(tr.get("name", "")), "cut_index": cut_index(at)})

    flash_events = [e for e in events if e["family"] == "flash"]
    share = round(len(flash_events) / float(n_cuts), 4)
    over_cap = [e for e in events if e["dur"] > float(cfg["max_event_s"]) + 1e-6]
    repeats: list[str] = []
    last_idx: dict[str, int] = {}
    for e in sorted(events, key=lambda x: x["at"]):
        prev = last_idx.get(e["kind"])
        if prev is not None and e["cut_index"] - prev < int(cfg["min_gap_cuts"]):
            repeats.append(f"{e['kind']} repeats within {int(cfg['min_gap_cuts'])} cuts (at {e['at']:.2f}s, cut #{e['cut_index']}, previous cut #{prev})")
        last_idx[e["kind"]] = e["cut_index"]
    return {
        "executed": True,
        "profile": "dviet",
        "n_cuts": n_cuts,
        "events": events,
        "flash_family_share": share,
        "max_flash_family_share": float(cfg["max_flash_family_share"]),
        "lift_allowed": share <= float(cfg["max_flash_family_share"]) + 1e-9,
        "over_cap_events": over_cap,
        "max_event_s": float(cfg["max_event_s"]),
        "soft_repeat_warnings": repeats,
        "warnings": [
            {"code": "DVIET_WASH_FLASH_REPEAT", "severity": "WARN", "message": r,
             "fix": f"vary the wash/flash kind or move it >= {int(cfg['min_gap_cuts'])} cuts away"}
            for r in repeats
        ] + (
            [{"code": "DVIET_FLASH_FAMILY_OVER_CAP", "severity": "ERROR", "elevate_concern_in_full": True,
              "message": f"flash family {share:.0%} of cuts > {float(cfg['max_flash_family_share']):.0%}: dviet veto lift revoked",
              "fix": "cut flash/flicker events until they are <= 20% of V1 cuts"}]
            if share > float(cfg["max_flash_family_share"]) + 1e-9 else []
        ),
    }


def audit_industry_cri100_veto(
    spec: dict[str, Any],
    *,
    raw_spec: dict[str, Any] | None = None,
    context_doc: dict[str, Any] | None = None,
    spec_meta: dict[str, Any] | None = None,
    san_stats: dict[str, Any] | None = None,
    industry_skin_override: str | None = None,
    strict_cri100: bool = False,
    profile: str = "default",
) -> dict[str, Any]:
    """
    `v7.0` Gate **`INDUSTRY_CRI100_VETO_AUDIT`** (`v7.4.0`: `profile="dviet"` lifts the Warm Film Burn veto for capped events only):
      - Active when `meta.industry_skin` (or `--industry-skin`) is `dental_clinic`, `luxury_skincare`,
        or `nail_hair_salon` (also audits `enamel_gum_bbox` / `macro_subject_bbox` whenever provided):
          1. **`CRI100_FORBIDDEN_WARM_FILM_BURN`**: Bans `Warm Film Burn` / orange light-leak transitions.
          2. **`CRI100_FORBIDDEN_YELLOW_WARM_LUT`**: Bans yellow/warm LUTs & `lumetri.temperature > +6.0`
             that stain porcelain enamel yellow or distort true CRI-100 skin/nail color.
          3. **`DENTAL_FORBIDDEN_HARSH_SFX`**: Bans visceral `bone_crack` / `drill` SFX in `dental_clinic`.
          4. **`ENAMEL_GUM_TEXT_OCCLUSION` / `MACRO_SUBJECT_TEXT_OCCLUSION`**: Bans text/cards overlapping
             `enamel_gum_bbox` or `macro_subject_bbox` (`+16px` clinical margin).
    """
    seq_w = float(spec.get("width", 1080))
    seq_h = float(spec.get("height", 1920))
    tracks = spec.get("tracks", [])
    max_end = max(
        (float(c.get("at", 0.0)) + float(c.get("dur", 0.0)) for tr in tracks for c in tr.get("clips", [])),
        default=1.0,
    )
    seq_dur = max(0.20, float(spec.get("duration") or max_end or 1.0))

    meta = _merged_spec_meta(raw_spec or spec, spec_meta)
    ctx = context_doc if isinstance(context_doc, dict) else {}
    raw_skin = str(
        industry_skin_override
        or meta.get("industry_skin")
        or (raw_spec or {}).get("industry_skin")
        or ctx.get("industry_skin")
        or ""
    ).strip().lower()
    canon_skin = CRI100_INDUSTRY_SKINS.get(raw_skin)
    is_cri100_skin = canon_skin in ("dental_clinic", "luxury_skincare", "nail_hair_salon")
    strict_veto = bool(strict_cri100 or meta.get("strict_cri100_veto"))

    # Collect `enamel_gum_bbox` and `macro_subject_bbox` windows from meta, raw_spec, context, and V1 clip annotations
    enamel_windows = _parse_timed_bboxes(
        meta.get("enamel_gum_bbox") or (raw_spec or {}).get("enamel_gum_bbox") or ctx.get("enamel_gum_bbox"),
        seq_w, seq_h, seq_dur,
    )
    macro_windows = _parse_timed_bboxes(
        meta.get("macro_subject_bbox") or (raw_spec or {}).get("macro_subject_bbox") or ctx.get("macro_subject_bbox"),
        seq_w, seq_h, seq_dur,
    )
    for ann in (san_stats or {}).get("v70_clip_annotations") or []:
        t0_a = float(ann.get("at", 0.0))
        t1_a = t0_a + float(ann.get("dur", 0.5))
        if ann.get("enamel_gum_bbox") is not None:
            for _, _, bx in _parse_timed_bboxes(ann["enamel_gum_bbox"], seq_w, seq_h, seq_dur):
                enamel_windows.append((t0_a, t1_a, bx))
        if ann.get("macro_subject_bbox") is not None:
            for _, _, bx in _parse_timed_bboxes(ann["macro_subject_bbox"], seq_w, seq_h, seq_dur):
                macro_windows.append((t0_a, t1_a, bx))

    if not is_cri100_skin and not enamel_windows and not macro_windows:
        return {
            "executed": False,
            "active": False,
            "gate": "INDUSTRY_CRI100_VETO_AUDIT",
            "industry_skin": raw_skin or None,
            "status": "SKIPPED_GENERAL",
            "veto_count": 0,
            "violations": [],
            "warning_codes": [],
            "warnings": [],
        }

    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []

    dviet_caps = audit_dviet_wash_flash_caps(spec) if profile == "dviet" else None

    def _burn_lifted(c_dur: float) -> bool:
        """`dviet`: a Warm Film Burn *event* (<= 0.6 s) is allowed while the flash family stays <= 20% of cuts."""
        return bool(dviet_caps and dviet_caps["lift_allowed"] and c_dur <= float(dviet_caps["max_event_s"]) + 1e-6)

    def _record_veto(code: str, msg: str, fix: str, extra: dict[str, Any]) -> None:
        rec = {"code": code, "message": msg, "fix": fix, **extra}
        violations.append(rec)
        if code not in warning_codes:
            warning_codes.append(code)
        warnings.append(
            {
                "code": code,
                "severity": "ERROR",
                "elevate_concern_in_full": True,
                "message": msg,
                "fix": fix,
                **extra,
            }
        )

    # Check 1 & 2: Warm Film Burn & Yellow/Warm LUT Vetoes across all visual tracks & raw_spec
    if is_cri100_skin:
        # Also inspect sequence-level transition_style / raw_spec hints + v70_clip_annotations
        seq_style_str = json.dumps(
            {
                "ts": meta.get("transition_style") or (raw_spec or {}).get("transition_style"),
                "lut": meta.get("lut") or meta.get("color_lut") or (raw_spec or {}).get("lut"),
            },
            ensure_ascii=False,
        ).lower()
        if any(tok in seq_style_str for tok in _WARM_FILM_BURN_TOKENS):
            _record_veto(
                "CRI100_FORBIDDEN_WARM_FILM_BURN",
                f"CRI100_FORBIDDEN_WARM_FILM_BURN: `meta` declares Warm Film Burn in `{canon_skin}` (destroys CRI-100 color accuracy)",
                "replace `Warm Film Burn` with `meta.transition_style = 'rack_focus_bridge_13f'` or `'exposure_bloom_landing_3f'`",
                {"track": "meta", "clip": "meta.transition_style", "at": 0.0},
            )
        if any(tok in seq_style_str for tok in _YELLOW_WARM_LUT_TOKENS):
            _record_veto(
                "CRI100_FORBIDDEN_YELLOW_WARM_LUT",
                f"CRI100_FORBIDDEN_YELLOW_WARM_LUT: `meta` declares warm/yellow LUT in `{canon_skin}` (stains enamel/skin yellow)",
                f"remove warm LUT and use CRI-100 neutral D65 palette (`{canon_skin}` jewel palette on `#FAFAFA`)",
                {"track": "meta", "clip": "meta.lut", "at": 0.0},
            )
        for ann in (san_stats or {}).get("v70_clip_annotations") or []:
            ann_ts = str(ann.get("transition_style") or "").lower()
            if ann_ts and any(tok in ann_ts for tok in _WARM_FILM_BURN_TOKENS) and not _burn_lifted(float(ann.get("dur", 0.5))):
                _record_veto(
                    "CRI100_FORBIDDEN_WARM_FILM_BURN",
                    f"CRI100_FORBIDDEN_WARM_FILM_BURN: clip '{ann.get('clip', '?')}' on '{ann.get('track', 'V1')}' (at={float(ann.get('at', 0.0)):.2f}s) declares `transition_style='{ann_ts}'` in `{canon_skin}`",
                    "replace clip `transition_style` with `'rack_focus_bridge_13f'` or `'exposure_bloom_landing_3f'`",
                    {"track": str(ann.get("track", "V1")), "clip": str(ann.get("clip", "?")), "at": round(float(ann.get("at", 0.0)), 3)},
                )

        for tr in tracks:
            ttype = str(tr.get("type", ""))
            tname = str(tr.get("name", ""))
            if ttype == "audio":
                continue
            for cl in tr.get("clips", []):
                c_at = float(cl.get("at", 0.0))
                cname = str(cl.get("name") or "")
                csrc = str(cl.get("src") or "")
                cpreset = str(cl.get("preset") or "")
                tr_in = json.dumps(cl.get("transition_in") or {}, ensure_ascii=False)
                tr_out = json.dumps(cl.get("transition_out") or {}, ensure_ascii=False)
                hay_vis = unicodedata.normalize("NFC", f"{cname} {Path(csrc).name if csrc else ''} {cpreset} {tr_in} {tr_out}").lower()

                if any(tok in hay_vis for tok in _WARM_FILM_BURN_TOKENS) and not _burn_lifted(float(cl.get("dur", 0.0))):
                    _record_veto(
                        "CRI100_FORBIDDEN_WARM_FILM_BURN",
                        f"CRI100_FORBIDDEN_WARM_FILM_BURN: clip '{cname or Path(csrc).name}' on '{tname}' (at={c_at:.2f}s) uses Warm Film Burn in `{canon_skin}`",
                        f"delete Warm Film Burn at {c_at:.2f}s and use `rack_focus_bridge_13f` or `exposure_bloom_landing_3f` (`meta.micro_bridges`)",
                        {"track": tname, "clip": cname or Path(csrc).name, "at": round(c_at, 3)},
                    )

                if any(tok in hay_vis for tok in _YELLOW_WARM_LUT_TOKENS):
                    _record_veto(
                        "CRI100_FORBIDDEN_YELLOW_WARM_LUT",
                        f"CRI100_FORBIDDEN_YELLOW_WARM_LUT: clip '{cname or Path(csrc).name}' on '{tname}' (at={c_at:.2f}s) applies warm/yellow LUT in `{canon_skin}`",
                        "remove warm/sepia LUT to preserve CRI-100 porcelain enamel & true skin/nail pigment",
                        {"track": tname, "clip": cname or Path(csrc).name, "at": round(c_at, 3)},
                    )

                for fx in cl.get("effects") or []:
                    fx_id = str(fx.get("effect") or "").lower()
                    params = fx.get("params") or {}
                    fx_str = json.dumps(fx, ensure_ascii=False).lower()
                    if any(tok in fx_str for tok in _WARM_FILM_BURN_TOKENS) and not _burn_lifted(float(cl.get("dur", 0.0))):
                        _record_veto(
                            "CRI100_FORBIDDEN_WARM_FILM_BURN",
                            f"CRI100_FORBIDDEN_WARM_FILM_BURN: effect '{fx_id}' on '{cname}' (at={c_at:.2f}s) triggers Warm Film Burn in `{canon_skin}`",
                            "replace with `rack_focus_bridge_13f` AdjustmentLayer",
                            {"track": tname, "clip": cname, "at": round(c_at, 3)},
                        )
                    if fx_id == "lumetri" or "lut" in fx_id or "color" in fx_id:
                        lut_str = f"{params.get('look_lut', '')} {params.get('input_lut', '')} {params.get('look', '')}".lower()
                        temp_raw = params.get("temperature", 0.0)
                        temp_val = float(_eval_kf_param(temp_raw, 0.0, 0.0)) if (temp_raw is not None) else 0.0
                        if any(tok in lut_str for tok in _YELLOW_WARM_LUT_TOKENS) or ("warm" in lut_str or "amber" in lut_str or "sepia" in lut_str) or temp_val > 6.0:
                            _record_veto(
                                "CRI100_FORBIDDEN_YELLOW_WARM_LUT",
                                f"CRI100_FORBIDDEN_YELLOW_WARM_LUT: `{fx_id}` on '{cname}' (at={c_at:.2f}s, temperature={temp_val:+.1f}, lut='{lut_str.strip()}') casts yellow tint in `{canon_skin}`",
                                f"reset `{fx_id}.temperature = 0.0` and clear warm `look_lut` on '{cname}' (at={c_at:.2f}s)",
                                {"track": tname, "clip": cname, "at": round(c_at, 3), "temperature": temp_val},
                            )

    # Check 3: Dental Clinic Forbidden Harsh/Visceral SFX (`bone_crack`, `drill`)
    if canon_skin == "dental_clinic":
        checked_sfx_at: set[tuple[str, float]] = set()
        for tok_rec in (san_stats or {}).get("raw_sfx_tokens") or []:
            hay_raw = unicodedata.normalize("NFC", f"{tok_rec.get('clip', '')} {tok_rec.get('raw_src', '')}").lower()
            hit_kw = next((kw for kw in _DENTAL_BANNED_SFX_TOKENS if kw in hay_raw), None)
            if hit_kw is not None:
                key_s = (str(tok_rec.get("track", "")), round(float(tok_rec.get("at", 0.0)), 3))
                checked_sfx_at.add(key_s)
                _record_veto(
                    "DENTAL_FORBIDDEN_HARSH_SFX",
                    f"DENTAL_FORBIDDEN_HARSH_SFX: SFX '{tok_rec.get('clip') or tok_rec.get('raw_src')}' at {key_s[1]:.2f}s uses banned dental anxiety token `{hit_kw}` in `dental_clinic`",
                    f"replace `{hit_kw}` SFX at {key_s[1]:.2f}s with gentle clinical sound (`AUTO:soft_tick` / `glass_shimmer` / `velvet_air`)",
                    {"track": key_s[0], "clip": str(tok_rec.get("clip") or tok_rec.get("raw_src")), "at": key_s[1], "banned_token": hit_kw},
                )
        for tr in tracks:
            if tr.get("type") != "audio":
                continue
            tname = str(tr.get("name", ""))
            for cl in tr.get("clips", []):
                c_at = round(float(cl.get("at", 0.0)), 3)
                if (tname, c_at) in checked_sfx_at:
                    continue
                cname = str(cl.get("name") or "")
                csrc = str(cl.get("src") or "")
                hay_a = unicodedata.normalize("NFC", f"{cname} {Path(csrc).name if csrc else ''}").lower()
                hit_kw = next((kw for kw in _DENTAL_BANNED_SFX_TOKENS if kw in hay_a), None)
                if hit_kw is not None:
                    _record_veto(
                        "DENTAL_FORBIDDEN_HARSH_SFX",
                        f"DENTAL_FORBIDDEN_HARSH_SFX: audio clip '{cname or Path(csrc).name}' on '{tname}' (at={c_at:.2f}s) contains banned `{hit_kw}` in `dental_clinic`",
                        f"replace `{hit_kw}` SFX at {c_at:.2f}s with clean clinical foley (`soft_tick` / `ui_shimmer`)",
                        {"track": tname, "clip": cname or Path(csrc).name, "at": c_at, "banned_token": hit_kw},
                    )

    # Check 4: Zero Foreground Text / Graphic Card Occlusion over `enamel_gum_bbox` & `macro_subject_bbox`
    margin_px = 16.0
    if enamel_windows or macro_windows:
        for tr_idx, tr in enumerate(tracks):
            tname = str(tr.get("name", ""))
            ttype = str(tr.get("type", ""))
            if ttype == "audio":
                continue
            for cl in tr.get("clips", []):
                c_at = float(cl.get("at", 0.0))
                c_dur = float(cl.get("dur", 0.5))
                if c_dur <= 0.04:
                    continue
                c_end = c_at + c_dur
                tau_settle = min(0.30, max(0.12, c_dur * 0.40))
                cname = str(cl.get("name") or cl.get("text") or "Overlay")[:32]

                box_ov: tuple[float, float, float, float] | None = None
                if ttype == "text" or "text" in cl:
                    box_ov = measure_text_clip_ink_bbox(cl, tau_settle, seq_w, seq_h)
                elif _is_graphic_card_overlay_clip(tr_idx, tname, ttype, cl):
                    box_ov = measure_card_clip_bbox(cl, tau_settle, seq_w, seq_h)
                if box_ov is None:
                    continue

                ix0, iy0, ix1, iy1 = box_ov
                for code_b, label_b, win_list in (
                    ("ENAMEL_GUM_TEXT_OCCLUSION", "enamel_gum_bbox", enamel_windows),
                    ("MACRO_SUBJECT_TEXT_OCCLUSION", "macro_subject_bbox", macro_windows),
                ):
                    for w0, w1, (bx0, by0, bx1, by1) in win_list:
                        if min(c_end, w1) - max(c_at, w0) < 0.04:
                            continue
                        ov_x = min(ix1, bx1 + margin_px) - max(ix0, bx0 - margin_px)
                        ov_y = min(iy1, by1 + margin_px) - max(iy0, by0 - margin_px)
                        if ov_x > 2.0 and ov_y > 2.0:
                            # Suggest Upper Editorial Stage if macro is lower, else Chest Tactile Rail
                            mid_by = 0.5 * (by0 + by1)
                            sug_rail = "Upper Editorial Stage (`y=380`)" if mid_by >= 0.48 * seq_h else "Chest Tactile Rail (`y=1440`)"
                            _record_veto(
                                code_b,
                                f"{code_b}: '{cname}' on '{tname}' (at={c_at:.2f}s) overlaps `{label_b}` [{bx0:.0f},{by0:.0f}..{bx1:.0f},{by1:.0f}] by {ov_y:.1f}px",
                                f"call `resolve_dual_rail_safe_y(..., {label_b}=[{bx0:.0f}, {by0:.0f}, {bx1:.0f}, {by1:.0f}])` -> move '{cname}' to {sug_rail}",
                                {
                                    "track": tname,
                                    "clip": cname,
                                    "at": round(c_at, 3),
                                    "target_bbox": [round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)],
                                    "overlay_bbox": [round(ix0, 1), round(iy0, 1), round(ix1, 1), round(iy1, 1)],
                                    "overlap_y_px": round(ov_y, 1),
                                },
                            )
                            break

    return {
        "executed": True,
        "active": True,
        "gate": "INDUSTRY_CRI100_VETO_AUDIT",
        "industry_skin": canon_skin or raw_skin or "macro_bbox_guard",
        "strict_cri100_veto": strict_veto,
        "enamel_gum_windows_checked": len(enamel_windows),
        "macro_subject_windows_checked": len(macro_windows),
        "veto_count": len(violations),
        "status": "FAIL" if (violations and strict_veto) else ("VETO_WARN" if violations else "PASS"),
        "violations": violations,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


def _is_hero_typography_plate_track_or_clip(track_name: str, clip_name: str, src_str: str, tkm: dict[str, Any] | None) -> bool:
    """Identify Hero / Kinetic Typography plate tracks or `c01..c15.png` / `dviet_overlapping_feather_cluster` stamps."""
    t_low = unicodedata.normalize("NFC", track_name).lower()
    c_low = unicodedata.normalize("NFC", clip_name).lower()
    s_name = unicodedata.normalize("NFC", Path(src_str).name if src_str else "").lower()
    if any(k in t_low for k in ("ảnh bìa", "thumbnail", "cover")):
        return False
    if isinstance(tkm, dict) and tkm.get("allow_static_thumbnail") is True:
        return False
    if src_str and _HERO_PNG_STAMP_RE.search(src_str):
        return True
    hay = f"{t_low} {c_low} {s_name}"
    if "dviet_overlapping_feather_cluster" in hay:
        return True
    if ("hero" in t_low and any(w in t_low for w in ("typo", "text", "chữ", "plate", "cluster", "lockup", "kinetic"))) or (
        "kinetic" in t_low and ("typo" in t_low or "text" in t_low or "chữ" in t_low)
    ):
        return True
    if isinstance(tkm, dict) and str(tkm.get("template") or "").strip().lower() in V71_KINETIC_TEMPLATE_SILHOUETTES:
        return True
    return False


def audit_kinetic_typography_choreography(
    spec: dict[str, Any],
    *,
    raw_spec: dict[str, Any] | None = None,
    spec_meta: dict[str, Any] | None = None,
    san_stats: dict[str, Any] | None = None,
    tier_used: str = "fast",
    strict_rules: bool = False,
    spec_dir: Path | None = None,
) -> dict[str, Any]:
    """
    `v7.1` Gate 3C: **`KINETIC_TYPOGRAPHY_CHOREOGRAPHY_AUDIT`** (Anti-Cookie-Cutter Vetoes):
      1. **`STATIC_HERO_PNG_STAMP`** (`FAIL` in BOTH `fast` and `full`!):
         Vetoes static `.png` stamps (`c01..c15.png`) or `mode == "still"` on Hero kinetic typography tracks
         or `dviet_overlapping_feather_cluster` `.png` plates.
      2. **`LAYOUT_SILHOUETTE_MONOTONY`** (`FAIL` in `full` / `--strict-rules`, `CONCERN` in `fast`):
         Vetoes repeating the exact same `layout_silhouette` `> 2` consecutive typography beats, or single
         silhouette share `> 35%` when `n_typo_beats >= 6`.
      3. **`PILL_BADGE_OVERUSE`** (`FAIL` in `full` / `--strict-rules`, `CONCERN` in `fast`):
         Vetoes `has_pill_badge` on `> 30%` of typography beats (`n_typo_beats >= 4`) OR duplicate `badge_text`
         used `>= 2` times in one video.
      4. **`ENTRANCE_STYLE_MONOTONY`** (`FAIL` in `full` / `--strict-rules`, `CONCERN` in `fast`):
         Vetoes repeating the exact same `entrance_style` `> 2` consecutive typography beats, or `< 4` distinct
         entrance styles when `n_typo_beats >= 8`.
    """
    tracks_src = (raw_spec if isinstance(raw_spec, dict) and raw_spec.get("tracks") else spec).get("tracks") or []
    san_tkm_list = (san_stats or {}).get("typo_kinetic_annotations") or []
    san_tkm_map: dict[tuple[str, float, str], dict[str, Any]] = {}
    for ta in san_tkm_list:
        if isinstance(ta.get("typo_kinetic_meta"), dict):
            san_tkm_map[(str(ta.get("track", "")), round(float(ta.get("at", 0.0)), 3), str(ta.get("clip", "")))] = ta["typo_kinetic_meta"]

    beat_records: list[dict[str, Any]] = []
    static_stamp_hits: list[dict[str, Any]] = []

    for tr_idx, tr in enumerate(tracks_src):
        ttype = str(tr.get("type", ""))
        tname = str(tr.get("name", ""))
        if ttype == "audio" or (tr_idx == 0 and tname.lower().startswith("v1")):
            continue
        for cl in tr.get("clips") or []:
            if _clip_max_opacity(cl) < 5.0:
                continue
            c_at = float(cl.get("at", 0.0))
            c_dur = float(cl.get("dur", 0.5))
            if c_dur <= 0.04:
                continue
            cname = str(cl.get("name") or cl.get("text") or "")
            src_str = str(cl.get("src") or "")

            inline_tkm = cl.get("typo_kinetic_meta") if isinstance(cl.get("typo_kinetic_meta"), dict) else None
            san_tkm = san_tkm_map.get((tname, round(c_at, 3), cname))
            sidecar_tkm = _load_sidecar_typo_meta(src_str, spec_dir=spec_dir) if src_str else None

            direct_tkm_fields: dict[str, Any] = {}
            for df in ("layout_silhouette", "entrance_style", "has_pill_badge", "badge_text", "mode", "template", "allow_static_thumbnail"):
                if df in cl and cl.get(df) is not None:
                    direct_tkm_fields[df] = cl[df]

            has_explicit_tkm = bool(inline_tkm or san_tkm or sidecar_tkm or direct_tkm_fields)
            merged_tkm: dict[str, Any] = {
                **(sidecar_tkm or {}),
                **(san_tkm or {}),
                **(inline_tkm or {}),
                **direct_tkm_fields,
            }
            is_hero_plate = _is_hero_typography_plate_track_or_clip(tname, cname, src_str, merged_tkm if has_explicit_tkm else None)
            if not has_explicit_tkm and not is_hero_plate:
                continue

            if merged_tkm.get("allow_static_thumbnail") is True or any(k in tname.lower() for k in ("ảnh bìa", "thumbnail")):
                continue

            tpl_key = str(merged_tkm.get("template") or "").strip().lower()
            if not tpl_key and "dviet_overlapping_feather_cluster" in f"{tname} {cname} {src_str}".lower():
                tpl_key = "dviet_overlapping_feather_cluster"

            mode_val = str(merged_tkm.get("mode") or "").strip().lower()
            is_png_src = bool(src_str and Path(src_str).suffix.lower() == ".png")

            # Check 1: `STATIC_HERO_PNG_STAMP`
            if mode_val == "still" or (is_png_src and (has_explicit_tkm or is_hero_plate)):
                static_stamp_hits.append(
                    {
                        "track": tname,
                        "clip": cname or (Path(src_str).name if src_str else "hero_stamp"),
                        "src": src_str,
                        "at": round(c_at, 3),
                        "mode": mode_val or ("still_png" if is_png_src else "still"),
                    }
                )

            sil_val = str(
                merged_tkm.get("layout_silhouette")
                or V71_KINETIC_TEMPLATE_SILHOUETTES.get(tpl_key)
                or ("SIL_FEATHER_SWASH" if (is_png_src and is_hero_plate) else "")
            ).strip()
            ent_val = str(
                merged_tkm.get("entrance_style")
                or ("static_png_stamp" if (mode_val == "still" or (is_png_src and is_hero_plate)) else V71_KINETIC_TEMPLATE_ENTRANCES.get(tpl_key, ""))
            ).strip()
            badge_txt = unicodedata.normalize("NFC", str(merged_tkm.get("badge_text") or "")).strip()
            has_pill = bool(merged_tkm.get("has_pill_badge") is True or bool(badge_txt))

            beat_records.append(
                {
                    "track_index": tr_idx,
                    "track": tname,
                    "clip": cname or (Path(src_str).name if src_str else f"beat@{c_at:.2f}s"),
                    "at": round(c_at, 4),
                    "dur": round(c_dur, 4),
                    "template": tpl_key,
                    "layout_silhouette": sil_val,
                    "entrance_style": ent_val,
                    "has_pill_badge": has_pill,
                    "badge_text": badge_txt,
                }
            )

    beat_records.sort(key=lambda r: (float(r["at"]), int(r["track_index"])))
    n_beats = len(beat_records)

    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    warning_codes: list[str] = []
    elevate_to_fail = bool(str(tier_used).lower() == "full" or strict_rules)

    def _emit_v71(code: str, msg: str, fix: str, *, always_fail: bool = False, extra: dict[str, Any] | None = None) -> None:
        is_hard = bool(always_fail or elevate_to_fail)
        sev = "ERROR" if is_hard else "WARN"
        rec = {"code": code, "severity": sev, "always_fail": always_fail, "message": msg, "fix": fix, **(extra or {})}
        violations.append(rec)
        if code not in warning_codes:
            warning_codes.append(code)
        warnings.append(
            {
                "code": code,
                "severity": sev,
                "elevate_concern_in_full": True,
                "message": msg,
                "fix": fix,
                **(extra or {}),
            }
        )

    # 1. `STATIC_HERO_PNG_STAMP` (Hard FAIL in BOTH `fast` and `full`!)
    if static_stamp_hits:
        sample_names = ", ".join(f"{h['clip']}@{h['at']:.2f}s" for h in static_stamp_hits[:4])
        _emit_v71(
            "STATIC_HERO_PNG_STAMP",
            f"STATIC_HERO_PNG_STAMP: {len(static_stamp_hits)} static `.png` / `mode='still'` Hero typography stamp(s) detected ({sample_names})",
            "replace static `.png` hero stamps with `typography_composer.plan_dviet_kinetic_beat_schedule(...)` + `web_plate_builder.render_kinetic_typo_batch(...)` animated ProRes 4444 `.mov` plates (`kt01..kt12`)",
            always_fail=True,
            extra={"static_stamp_count": len(static_stamp_hits), "samples": static_stamp_hits[:6]},
        )

    # 2. `LAYOUT_SILHOUETTE_MONOTONY` (>2 consecutive same silhouette OR >35% share when n >= 6)
    sil_seq = [r["layout_silhouette"] for r in beat_records if r["layout_silhouette"]]
    max_sil_run = 0
    max_sil_run_name = ""
    cur_run = 0
    prev_s = ""
    for s_v in sil_seq:
        if s_v == prev_s:
            cur_run += 1
        else:
            cur_run = 1
            prev_s = s_v
        if cur_run > max_sil_run:
            max_sil_run = cur_run
            max_sil_run_name = s_v

    sil_counts: dict[str, int] = {}
    for s_v in sil_seq:
        sil_counts[s_v] = sil_counts.get(s_v, 0) + 1
    top_sil, top_sil_cnt = max(sil_counts.items(), key=lambda kv: kv[1]) if sil_counts else ("", 0)
    top_sil_share = (top_sil_cnt / float(n_beats)) if n_beats > 0 else 0.0

    if max_sil_run > 2 or (n_beats >= 6 and top_sil_share > 0.35 + 1e-9):
        reasons_sil: list[str] = []
        if max_sil_run > 2:
            reasons_sil.append(f"`{max_sil_run_name}` repeated {max_sil_run} consecutive beats (limit <= 2)")
        if n_beats >= 6 and top_sil_share > 0.35 + 1e-9:
            reasons_sil.append(f"`{top_sil}` share is {top_sil_share*100:.1f}% ({top_sil_cnt}/{n_beats}, limit <= 35.0%)")
        _emit_v71(
            "LAYOUT_SILHOUETTE_MONOTONY",
            f"LAYOUT_SILHOUETTE_MONOTONY: {'; '.join(reasons_sil)}",
            "use `plan_dviet_kinetic_beat_schedule(...)` to alternate Hero Clusters (`kt01..kt04/kt08`) with Quiet/Wall (`kt12/kt05`) & Specialty (`kt06/kt09/kt10/kt11`) so each silhouette stays <= 30% with 0 consecutive repeats",
            extra={
                "max_consecutive_silhouette": max_sil_run,
                "dominant_silhouette": top_sil,
                "dominant_silhouette_share_pct": round(top_sil_share * 100.0, 1),
            },
        )

    # 3. `PILL_BADGE_OVERUSE` (>30% of beats when n >= 4 OR duplicate badge_text >= 2)
    pill_beats = [r for r in beat_records if r["has_pill_badge"]]
    pill_ratio = (len(pill_beats) / float(n_beats)) if n_beats > 0 else 0.0
    badge_freq: dict[str, list[str]] = {}
    for r in pill_beats:
        bt = r["badge_text"].strip()
        if bt:
            bk = bt.casefold()
            badge_freq.setdefault(bk, []).append(bt)
    dup_badges = {vals[0]: len(vals) for _bk, vals in badge_freq.items() if len(vals) >= 2}

    if (n_beats >= 4 and pill_ratio > 0.30 + 1e-9) or dup_badges:
        reasons_pill: list[str] = []
        if n_beats >= 4 and pill_ratio > 0.30 + 1e-9:
            reasons_pill.append(f"pill badges appear on {pill_ratio*100:.1f}% ({len(pill_beats)}/{n_beats}) of typography beats (limit <= 30%, target <= 20%)")
        if dup_badges:
            dup_str = ", ".join(f"'{k}'×{v}" for k, v in dup_badges.items())
            reasons_pill.append(f"duplicate `badge_text` reused >= 2 times ({dup_str})")
        _emit_v71(
            "PILL_BADGE_OVERUSE",
            f"PILL_BADGE_OVERUSE: {'; '.join(reasons_pill)}",
            "restrict `badge_text` pills to <= 20% of beats (max 2–3 unique single-use pills per video, 0 duplicates, 0 on F6/S7)",
            extra={
                "pill_beat_count": len(pill_beats),
                "pill_ratio_pct": round(pill_ratio * 100.0, 1),
                "duplicate_badges": dup_badges,
            },
        )

    # 4. `ENTRANCE_STYLE_MONOTONY` (>2 consecutive same entrance_style OR <4 distinct when n >= 8)
    ent_seq = [r["entrance_style"] for r in beat_records if r["entrance_style"]]
    max_ent_run = 0
    max_ent_run_name = ""
    cur_e_run = 0
    prev_e = ""
    for e_v in ent_seq:
        if e_v == prev_e:
            cur_e_run += 1
        else:
            cur_e_run = 1
            prev_e = e_v
        if cur_e_run > max_ent_run:
            max_ent_run = cur_e_run
            max_ent_run_name = e_v
    distinct_ents = sorted(set(ent_seq))

    if max_ent_run > 2 or (n_beats >= 8 and len(distinct_ents) < 4):
        reasons_ent: list[str] = []
        if max_ent_run > 2:
            reasons_ent.append(f"`{max_ent_run_name}` repeated {max_ent_run} consecutive beats (limit <= 2)")
        if n_beats >= 8 and len(distinct_ents) < 4:
            reasons_ent.append(f"only {len(distinct_ents)} distinct `entrance_style`(s) across {n_beats} beats (require >= 4)")
        _emit_v71(
            "ENTRANCE_STYLE_MONOTONY",
            f"ENTRANCE_STYLE_MONOTONY: {'; '.join(reasons_ent)}",
            "rotate across >= 4 distinct `@__dviet` entrance physics (`player3_air_cushion_kiss_20f`, `feather29_swash_bloom_22f`, `nonlinear_word_stagger_18f`, `laser_strike_2phase_flip_20f`, `whisper_directional_echo_12f`)",
            extra={
                "max_consecutive_entrance": max_ent_run,
                "distinct_entrance_count": len(distinct_ents),
                "distinct_entrances": distinct_ents,
            },
        )

    has_always_fail = any(v.get("always_fail") for v in violations)
    if has_always_fail or (violations and elevate_to_fail):
        gate_status = "FAIL"
    elif violations:
        gate_status = "CONCERN"
    else:
        gate_status = "PASS"

    return {
        "executed": True,
        "gate": "KINETIC_TYPOGRAPHY_CHOREOGRAPHY_AUDIT",
        "status": gate_status,
        "tier_used": tier_used,
        "typo_beats_audited": n_beats,
        "static_hero_png_stamps": len(static_stamp_hits),
        "distinct_silhouettes": len(sil_counts),
        "silhouette_distribution": sil_counts,
        "max_silhouette_share_pct": round(top_sil_share * 100.0, 1),
        "max_consecutive_silhouette": max_sil_run,
        "pill_badge_count": len(pill_beats),
        "pill_badge_ratio_pct": round(pill_ratio * 100.0, 1),
        "duplicate_badges": dup_badges,
        "distinct_entrance_styles": len(distinct_ents),
        "max_consecutive_entrance": max_ent_run,
        "violation_count": len(violations),
        "violations": violations,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }


def _build_fcproj_default_lumetri_params() -> dict[str, Any]:
    """Exact FilmCraft native `lumetri` parameter dictionary (`temperature=0.0` CRI-100 neutral)."""
    ident_curve = {"value": {"Curve": [[0.0, 0.0], [1.0, 1.0]]}}
    empty_curve = {"value": {"Curve": []}}
    neutral_tint = {"value": {"Color": [0.5, 0.5, 0.5, 1.0]}}
    zero_vec = {"value": {"Vec2": {"x": 0.0, "y": 0.0}}}
    return {
        "basic_on": {"value": {"Bool": True}},
        "blacks": {"value": {"Float": 0.0}},
        "contrast": {"value": {"Float": 0.0}},
        "creative_on": {"value": {"Bool": True}},
        "creative_sat": {"value": {"Float": 100.0}},
        "curve_blue": copy.deepcopy(ident_curve),
        "curve_green": copy.deepcopy(ident_curve),
        "curve_luma": copy.deepcopy(ident_curve),
        "curve_red": copy.deepcopy(ident_curve),
        "curves_hdr_range": {"value": {"Float": 1000.0}},
        "curves_on": {"value": {"Bool": True}},
        "exposure": {"value": {"Float": 0.0}},
        "faded_film": {"value": {"Float": 0.0}},
        "hdr_specular": {"value": {"Float": 0.0}},
        "hdr_white": {"value": {"Float": 1000.0}},
        "highlight_tint": copy.deepcopy(neutral_tint),
        "highlights": {"value": {"Float": 0.0}},
        "hsl_blur": {"value": {"Float": 0.0}},
        "hsl_denoise": {"value": {"Float": 0.0}},
        "hsl_hue": {"value": {"Float": 0.0}},
        "hsl_hue_range": {"value": {"Float": 30.0}},
        "hsl_hue_shift": {"value": {"Float": 0.0}},
        "hsl_luma_max": {"value": {"Float": 95.0}},
        "hsl_luma_min": {"value": {"Float": 5.0}},
        "hsl_on": {"value": {"Bool": False}},
        "hsl_sat": {"value": {"Float": 100.0}},
        "hsl_sat_min": {"value": {"Float": 10.0}},
        "hsl_show_mask": {"value": {"Choice": 0}},
        "hsl_soft": {"value": {"Float": 20.0}},
        "hsl_temp": {"value": {"Float": 0.0}},
        "hsl_tint": {"value": {"Float": 0.0}},
        "hue_vs_hue": copy.deepcopy(empty_curve),
        "hue_vs_luma": copy.deepcopy(empty_curve),
        "hue_vs_sat": copy.deepcopy(empty_curve),
        "input_lut": {"value": {"Text": ""}},
        "look": {"value": {"Choice": 0}},
        "look_intensity": {"value": {"Float": 100.0}},
        "look_lut": {"value": {"Text": ""}},
        "luma_vs_sat": copy.deepcopy(empty_curve),
        "sat_vs_sat": copy.deepcopy(empty_curve),
        "saturation": {"value": {"Float": 100.0}},
        "shadow_tint": copy.deepcopy(neutral_tint),
        "shadows": {"value": {"Float": 0.0}},
        "sharpen": {"value": {"Float": 0.0}},
        "temperature": {"value": {"Float": 0.0}},
        "tint": {"value": {"Float": 0.0}},
        "vibrance": {"value": {"Float": 0.0}},
        "vignette_amount": {"value": {"Float": 0.0}},
        "vignette_feather": {"value": {"Float": 50.0}},
        "vignette_midpoint": {"value": {"Float": 50.0}},
        "vignette_on": {"value": {"Bool": True}},
        "vignette_roundness": {"value": {"Float": 0.0}},
        "wheel_highlights": copy.deepcopy(zero_vec),
        "wheel_highlights_l": {"value": {"Float": 0.0}},
        "wheel_midtones": copy.deepcopy(zero_vec),
        "wheel_midtones_l": {"value": {"Float": 0.0}},
        "wheel_shadows": copy.deepcopy(zero_vec),
        "wheel_shadows_l": {"value": {"Float": 0.0}},
        "wheels_on": {"value": {"Bool": True}},
        "whites": {"value": {"Float": 0.0}},
    }


def _build_fcproj_intrinsic_video_effects(seq_w: int, seq_h: int) -> list[dict[str, Any]]:
    cx, cy = float(seq_w) * 0.5, float(seq_h) * 0.5
    return [
        {
            "effect": "motion",
            "enabled": True,
            "params": {
                "anchor": {"value": {"Vec2": {"x": cx, "y": cy}}},
                "anti_flicker": {"value": {"Float": 0.0}},
                "position": {"value": {"Vec2": {"x": cx, "y": cy}}},
                "rotation": {"value": {"Float": 0.0}},
                "scale": {"value": {"Float": 100.0}},
                "scale_width": {"value": {"Float": 100.0}},
                "uniform_scale": {"value": {"Bool": True}},
            },
        },
        {
            "effect": "opacity",
            "enabled": True,
            "params": {
                "blend": {"value": {"Choice": 0}},
                "opacity": {"value": {"Float": 100.0}},
            },
        },
        {
            "effect": "time_remap",
            "enabled": True,
            "params": {
                "speed": {"value": {"Float": 100.0}},
            },
        },
    ]


def inject_micro_bridge_adjustment_layers_fcproj(
    fcproj_path: Path,
    micro_bridges: list[dict[str, Any]],
    fps: float | None = None,
) -> dict[str, Any]:
    """
    `v7.0` Native `.fcproj` **`AdjustmentLayer` Micro-Bridge Synthesizer**:
      - Automatically injects a dedicated `FX · v7.0 Micro-Bridges` video track right above the
        camera/B-roll plate tracks (below foreground `text` & `card` tracks so `Persistent Text Bridges`
        stay 100% razor-sharp!) populated with native FilmCraft `AdjustmentLayer` clips for:
          * **`exposure_bloom_landing_3f`** (`Video #19`, `3f` CRI-100 `lumetri` exposure bloom landing)
          * **`rack_focus_bridge_13f`** (`Video #18`, `13f` = `5f Blur-Out -> 3f Bokeh Hold -> 5f Pull-Focus In`
            CRI-100 neutral `gaussian_blur` + subtle bokeh lift, `repeat_edge=True`)
    """
    if not micro_bridges:
        return {"injected": False, "count": 0, "items": []}

    doc = json.loads(fcproj_path.read_text(encoding="utf-8"))
    proj = doc.get("project") or {}
    items_map = proj.get("items") or {}
    seq = next((v["kind"]["Sequence"] for v in items_map.values() if "Sequence" in v.get("kind", {})), None)
    if seq is None:
        return {"injected": False, "count": 0, "items": [], "reason": "no Sequence found in .fcproj"}

    settings = seq.get("settings") or {}
    seq_w = int(settings.get("width", 1080))
    seq_h = int(settings.get("height", 1920))
    fr = settings.get("frame_rate") or {"num": int(round(fps or 60.0)), "den": 1}
    fr_num = max(1, int(fr.get("num", 60)))
    fr_den = max(1, int(fr.get("den", 1)))
    eff_fps = float(fps) if fps else (float(fr_num) / float(fr_den))
    one_frame_ticks = round(TICKS_PER_SECOND * fr_den / fr_num)

    seq_out_ticks = seq.get("mark_out")
    if not isinstance(seq_out_ticks, int) or seq_out_ticks <= 0:
        seq_out_ticks = max(
            (int(it.get("start", 0)) + int(it.get("duration", 0)) for tr in seq.get("video_tracks", []) for it in tr.get("items", [])),
            default=10 * TICKS_PER_SECOND,
        )

    next_id = int(proj.get("next_id", max((int(k) for k in items_map.keys() if str(k).isdigit()), default=10) + 1))
    adj_item_id = next_id
    next_id += 1

    # Synthetic AdjustmentLayer project bin item (0 external file paths -> 100% portable bundle safe!)
    adj_bin_dur = max(5 * TICKS_PER_SECOND, 30 * one_frame_ticks)
    items_map[str(adj_item_id)] = {
        "id": adj_item_id,
        "name": "Adjustment Layer · v7.0 Micro-Bridges",
        "label": "Lavender",
        "kind": {
            "AdjustmentLayer": {
                "width": seq_w,
                "height": seq_h,
                "rate": {"num": fr_num, "den": fr_den},
                "duration": adj_bin_dur,
            }
        },
        "metadata": {},
        "created": adj_item_id,
    }
    root_children = (proj.get("root") or {}).setdefault("children", [])
    root_children.append({"Item": adj_item_id})

    def _kf(t_ticks: int, val: float, interp: str = "Linear") -> dict[str, Any]:
        return {
            "time": int(t_ticks),
            "value": {"Float": round(float(val), 4)},
            "interp": interp,
            "out_influence": 1.0 / 3.0,
            "in_influence": 1.0 / 3.0,
        }

    built_track_items: list[dict[str, Any]] = []
    injected_records: list[dict[str, Any]] = []
    last_end_ticks = 0

    for mb in sorted(micro_bridges, key=lambda m: float(m.get("at", 0.0))):
        b_raw = str(mb.get("type") or "").strip().lower()
        b_type = V70_MICRO_BRIDGE_ALIASES.get(b_raw)
        if not b_type:
            continue
        cut_s = float(mb.get("at", 0.0))
        cut_f = max(0, int(round(cut_s * eff_fps)))

        if b_type == "exposure_bloom_landing_3f":
            n_frames = max(2, int(mb.get("frames") or 3))
            start_f = cut_f
            start_ticks = max(last_end_ticks, start_f * one_frame_ticks)
            dur_ticks = min(n_frames * one_frame_ticks, max(0, seq_out_ticks - start_ticks))
            if dur_ticks < 2 * one_frame_ticks:
                continue
            peak_ev = float(mb.get("peak_ev", 1.55))
            lum_params = _build_fcproj_default_lumetri_params()
            if n_frames == 3:
                lum_params["exposure"]["keyframes"] = [
                    _kf(0, peak_ev, "EaseOut"),
                    _kf(one_frame_ticks, peak_ev * 0.52, "Linear"),
                    _kf(2 * one_frame_ticks, peak_ev * 0.18, "Linear"),
                    _kf(3 * one_frame_ticks, 0.0, "EaseIn"),
                ]
                lum_params["highlights"]["keyframes"] = [
                    _kf(0, 32.0, "EaseOut"),
                    _kf(one_frame_ticks, 16.0, "Linear"),
                    _kf(3 * one_frame_ticks, 0.0, "EaseIn"),
                ]
            else:
                lum_params["exposure"]["keyframes"] = [
                    _kf(0, peak_ev, "EaseOut"),
                    _kf(dur_ticks, 0.0, "EaseIn"),
                ]
            fx_stack = [
                *_build_fcproj_intrinsic_video_effects(seq_w, seq_h),
                {"effect": "lumetri", "enabled": True, "params": lum_params},
            ]
            clip_label = f"Adj · Exposure Bloom 3f @{cut_s:.2f}s"
        else:
            # `rack_focus_bridge_13f`: 5f Blur-Out -> [Cut] -> 3f Bokeh Hold -> 5f Pull-Focus In (CRI-100 neutral!)
            n_frames = max(5, int(mb.get("frames") or 13))
            n_pre = max(1, int(round(n_frames * (5.0 / 13.0))))
            n_hold = max(1, int(round(n_frames * (3.0 / 13.0))))
            start_f = max(0, cut_f - n_pre)
            start_ticks = max(last_end_ticks, start_f * one_frame_ticks)
            dur_ticks = min(n_frames * one_frame_ticks, max(0, seq_out_ticks - start_ticks))
            if dur_ticks < 4 * one_frame_ticks:
                continue
            max_sigma = float(mb.get("max_sigma", 14.0))
            peak_blur = round(max_sigma * 2.2, 2)
            t_apex = min(dur_ticks - 2 * one_frame_ticks, n_pre * one_frame_ticks)
            t_hold_end = min(dur_ticks - one_frame_ticks, (n_pre + n_hold) * one_frame_ticks)

            blur_fx = {
                "effect": "gaussian_blur",
                "enabled": True,
                "params": {
                    "blurriness": {
                        "value": {"Float": 0.0},
                        "keyframes": [
                            _kf(0, 0.0, "EaseOut"),
                            _kf(t_apex, peak_blur, "Bezier"),
                            _kf(t_hold_end, round(peak_blur * 0.94, 2), "EaseOut"),
                            _kf(dur_ticks, 0.0, "EaseIn"),
                        ],
                    },
                    "dimensions": {"value": {"Choice": 0}},
                    "repeat_edge": {"value": {"Bool": True}},
                },
            }
            lum_params = _build_fcproj_default_lumetri_params()
            lum_params["exposure"]["keyframes"] = [
                _kf(0, 0.0, "EaseOut"),
                _kf(t_apex, 0.10, "Bezier"),
                _kf(t_hold_end, 0.08, "EaseOut"),
                _kf(dur_ticks, 0.0, "EaseIn"),
            ]
            fx_stack = [
                *_build_fcproj_intrinsic_video_effects(seq_w, seq_h),
                blur_fx,
                {"effect": "lumetri", "enabled": True, "params": lum_params},
            ]
            clip_label = f"Adj · Rack Focus {n_frames}f @{cut_s:.2f}s"

        clip_id = next_id
        next_id += 1
        built_track_items.append(
            {
                "id": clip_id,
                "item": adj_item_id,
                "name": clip_label,
                "label": "Lavender",
                "start": int(start_ticks),
                "duration": int(dur_ticks),
                "source_in": 0,
                "speed": 1.0,
                "reverse": False,
                "enabled": True,
                "link": None,
                "group": None,
                "effects": fx_stack,
                "markers": [],
                "gain_db": 0.0,
                "frame_hold": None,
                "scale_to_frame": False,
            }
        )
        last_end_ticks = int(start_ticks + dur_ticks)
        injected_records.append(
            {
                "clip_id": clip_id,
                "type": b_type,
                "name": clip_label,
                "cut_at_s": round(cut_s, 4),
                "start_s": round(start_ticks / float(TICKS_PER_SECOND), 4),
                "dur_s": round(dur_ticks / float(TICKS_PER_SECOND), 4),
                "frames": int(round(dur_ticks / float(one_frame_ticks))),
            }
        )

    if not built_track_items:
        return {"injected": False, "count": 0, "items": []}

    track_id = next_id
    next_id += 1
    adj_track = {
        "id": track_id,
        "kind": "Video",
        "name": "FX · v7.0 Micro-Bridges",
        "items": built_track_items,
        "transitions": [],
        "locked": False,
        "sync_lock": True,
        "enabled": True,
        "muted": False,
        "solo": False,
        "channels": "Stereo",
        "volume_db": 0.0,
        "pan": 0.0,
        "effects": [],
        "mixer": {
            "mode": "Read",
            "output": None,
            "record_arm": False,
            "solo_safe": False,
            "input_map": "Stereo",
        },
    }

    # Insert right below foreground `text` / `card` / `gfx` / `band` tracks so typography stays 100% sharp!
    v_tracks = seq.setdefault("video_tracks", [])
    insert_idx = len(v_tracks)
    for idx_vt, vt in enumerate(v_tracks):
        vt_name = str(vt.get("name") or "").lower()
        has_graphic_text = any(
            any(ef.get("effect") == "graphic_text" for ef in (it.get("effects") or []))
            for it in (vt.get("items") or [])
        )
        if has_graphic_text or any(vt_name.startswith(p) for p in ("text", "card", "gfx", "callout", "band", "dải tối")):
            insert_idx = idx_vt
            break
    v_tracks.insert(insert_idx, adj_track)
    proj["next_id"] = next_id

    fcproj_path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {
        "injected": True,
        "track_name": "FX · v7.0 Micro-Bridges",
        "track_index": insert_idx,
        "adjustment_item_id": adj_item_id,
        "count": len(injected_records),
        "items": injected_records,
    }


# ==============================================================================
# [P0] Actionable `— Fix:` Self-Repair Diagnostics Formatter
# ==============================================================================

def build_lint_fix_diagnostic(item: dict[str, Any], spec: dict[str, Any]) -> str:
    cid = str(item.get("id", ""))
    val = item.get("value")
    raw_fix = str(item.get("fix") or "")
    v1_clips = next((t.get("clips", []) for t in spec.get("tracks", []) if t.get("type") == "video"), [])

    if cid == "low_res_source" and v1_clips:
        for c in v1_clips:
            if isinstance(val, list) and any(Path(str(c.get("src", ""))).name in str(v) for v in val):
                return f"upscale/regenerate V1 clip '{c.get('name', '?')}' (at={c.get('at', 0):.2f}s, src={Path(c['src']).name}) to {spec.get('width', 1080)}x{spec.get('height', 1920)}"
    if cid == "opening_sfx":
        return "place SFX clip 'SFX MỞ ĐẦU' on track A2 with at=0.00s, dur>=0.35s"
    if cid == "hook_text_late":
        return f"shift first hero/caption text clip `at` earlier to <= 1.20s (currently {val}s)"
    if cid == "dead_air" and isinstance(val, list) and val:
        return f"trim V1/A1 silence gap or insert B-roll/SFX accent at {val[0]}"
    if cid == "clip_past_file_end" and isinstance(val, list) and val:
        return f"clamp `dur = file_dur - in` on {val[0]}"
    return raw_fix or f"adjust `{cid}` ({val}) to satisfy `{item.get('target')}`"


def build_edit_rule_fix_diagnostic(item: dict[str, Any], spec: dict[str, Any]) -> str:
    rule = str(item.get("rule", ""))
    detail = str(item.get("detail", ""))
    tracks = spec.get("tracks", [])

    if "Font" in rule:
        return f"consolidate/expand typography `font` families across text tracks to 4–6 families ({detail[:80]})"
    if "Chữ chính có phát sáng" in rule:
        for tr in tracks:
            if _lane(str(tr.get("name", ""))) in ("text", "text_top", "text_img"):
                for cl in tr.get("clips", []):
                    if not any(e.get("effect") in ("wonder_glow", "glow", "outer_glow") for e in (cl.get("effects") or [])):
                        return f"append `wonder_glow` (radius=18, intensity=95, mode='Add') to clip '{cl.get('name', cl.get('text', '?'))}' (at={cl.get('at', 0):.2f}s)"
    if "Mọi điểm cắt có chuyển cảnh" in rule:
        return f"add `transition_in` (`whip`/`film_dissolve`/`luma_fade`, frames=6) on V1 clips at uncovered cuts ({detail})"
    if "Zoom in / out ở đoạn nói dài" in rule:
        return f"add animated `motion.scale` keyframes (e.g. `118 -> 125`) on long V1 A-roll clips ({detail})"
    if "Nhiều B-roll" in rule:
        return f"insert visual B-roll clip on V1 inside longest A-roll span ({detail[:95]})"
    if "C7 cut_lead" in rule:
        return f"shift V1/A1 cut boundary 1–2 frames earlier so first spoken word starts +20..+80ms after cut ({detail})"
    if "C8 text_cut_overrun" in rule:
        return f"trim main text clip `dur` so `at + dur <= cut_t - 1/fps` ({detail})"
    if "dấu phẩy" in rule:
        return f"strip non-decimal commas `,` from on-screen `text` clips ({detail[:80]})"
    return f"adjust timeline spec for rule '{rule}' ({detail[:90]})"


# ==============================================================================
# QA Frame Planner, Contact Sheet, Portable Bundle & Vietnamese `EDITOR-REPORT.md`
# ==============================================================================

def plan_16_qa_frames(spec: dict[str, Any]) -> list[tuple[float, str]]:
    """
    Stratified 16-bucket QA frame planner: combines 16 evenly-spaced timeline buckets
    with exact hero-peak / UI-card settlement timestamps so every tile shows crisp settled visuals.
    """
    dur = max(1.0, float(spec.get("duration", 10.0)))
    fps = float(spec.get("fps", 30.0))
    tracks = spec.get("tracks", [])

    hero_peaks: list[tuple[float, str, int]] = []
    for tr in tracks:
        tname = str(tr.get("name", ""))
        ln = _lane(tname)
        is_hero_text = tr.get("type") == "text" and ln != "text_low"
        is_card = tr.get("type") == "video" and any(k in tname.lower() for k in ("card", "text_img"))
        if not (is_hero_text or is_card):
            continue
        prio = 0 if ln in ("text", "text_img") or is_card else 1
        for cl in tr.get("clips", []):
            at = float(cl.get("at", 0.0))
            cdur = float(cl.get("dur", 0.5))
            if cdur < 0.25:
                continue
            settle = min(0.42, max(0.20, cdur * 0.36))
            peak_t = round(min(at + settle, at + cdur - 2.0 / fps), 2)
            if 0.05 <= peak_t <= dur - 0.08:
                raw_label = str(cl.get("text") or cl.get("name") or "HERO").strip()
                short_lbl = re.sub(r"\s+", " ", raw_label)[:16]
                hero_peaks.append((peak_t, f"HERO:{short_lbl}", prio))

    v1_clips = []
    for tr in tracks:
        if tr.get("type") == "video":
            v1_clips = sorted(tr.get("clips", []), key=lambda c: float(c.get("at", 0.0)))
            break
    cut_points = [float(c.get("at", 0.0)) for c in v1_clips[1:] if float(c.get("at", 0.0)) > 0.05]

    def _near_cut(ts: float, margin: float = 0.22) -> bool:
        return any(abs(ts - ct) < margin for ct in cut_points)

    def _shot_tag(ts: float) -> str:
        for c in v1_clips:
            if float(c.get("at", 0.0)) <= ts < float(c.get("at", 0.0)) + float(c.get("dur", 0.0)):
                nm = str(c.get("name", "")).lower()
                return "B-Roll" if ("b-roll" in nm or "footage" in nm) else "A-Roll"
        return "Shot"

    selected: list[tuple[float, str]] = []
    for i in range(16):
        b0 = i * dur / 16.0
        b1 = (i + 1) * dur / 16.0
        mid = round((i + 0.5) * dur / 16.0, 2)
        min_allowed = max(0.05, b0 + 0.06, (selected[-1][0] + 0.25) if selected else 0.05)
        max_allowed = min(dur - 0.08, b1 - 0.06)

        in_bucket = [
            (pt, plab, prio)
            for pt, plab, prio in hero_peaks
            if min_allowed <= pt <= max_allowed and not _near_cut(pt, 0.14)
        ]
        if in_bucket:
            chosen_t, chosen_lab, _ = min(in_bucket, key=lambda x: (x[2], abs(x[0] - mid)))
            selected.append((chosen_t, chosen_lab))
        else:
            t_use = max(min_allowed, min(max(min_allowed, dur - 0.08), mid))
            if _near_cut(t_use, 0.22):
                nearest_ct = min(cut_points, key=lambda ct: abs(t_use - ct))
                cand_after = round(nearest_ct + 0.28, 2)
                cand_before = round(nearest_ct - 0.26, 2)
                if min_allowed <= cand_after <= max(max_allowed, min_allowed):
                    t_use = cand_after
                elif min_allowed <= cand_before <= max(max_allowed, min_allowed):
                    t_use = cand_before
            t_use = round(t_use, 2)
            selected.append((t_use, _shot_tag(t_use)))

    return selected


def build_4x4_contact_sheet(
    qa_frames_dir: Path,
    planned_frames: list[tuple[float, str]],
    out_jpg: Path,
) -> Path:
    """Build labeled 4x4 `qa_contact_sheet.jpg` at exact 1440x2560 resolution (4*360 x 4*640)."""
    tile_w, tile_h = 360, 640
    cols, rows = 4, 4
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (14, 16, 20))
    draw = ImageDraw.Draw(sheet)

    font = ImageFont.load_default()
    for fp in FONT_CANDIDATES:
        if Path(fp).is_file():
            try:
                font = ImageFont.truetype(fp, 15)
                break
            except OSError:
                pass

    png_fallbacks = sorted(qa_frames_dir.glob("*.png"))
    for idx in range(min(16, len(planned_frames))):
        t_sec, tag = planned_frames[idx]
        fx = (idx % cols) * tile_w
        fy = (idx // cols) * tile_h
        cand_png = qa_frames_dir / f"t{t_sec:07.2f}.png"
        if not cand_png.is_file() and idx < len(png_fallbacks):
            cand_png = png_fallbacks[idx]

        if cand_png.is_file():
            im = Image.open(cand_png).convert("RGB").resize((tile_w, tile_h), Image.Resampling.LANCZOS)
            sheet.paste(im, (fx, fy))

        label = f"#{idx+1:02d} {t_sec:05.2f}s · {tag}"
        bbox = draw.textbbox((0, 0), label, font=font)
        bw = min(tile_w - 12, (bbox[2] - bbox[0]) + 16)
        bh = (bbox[3] - bbox[1]) + 10
        draw.rounded_rectangle([fx + 6, fy + 6, fx + 6 + bw, fy + 6 + bh], radius=6, fill=(10, 12, 16))
        draw.text((fx + 14, fy + 10 - bbox[1]), label, font=font, fill=(94, 234, 212))

    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_jpg, format="JPEG", quality=90)
    return out_jpg


def backup_existing_fcproj(out_path: Path) -> Path | None:
    """Rule A3: Backup existing .fcproj into `$PFD_CACHE_DIR/backup/` (default ~/.cache/pro-filmcraft-director) before overwriting."""
    if not out_path.is_file():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bk_path = BACKUP_DIR / f"{out_path.stem}-{stamp}-{os.getpid()}{out_path.suffix}"
    shutil.copy2(out_path, bk_path)
    return bk_path


def relativize_and_verify_bundle(
    compiled_fcproj: Path,
    out_fcproj: Path,
    portable_root: Path,
    work_dir: Path,
    smoke_time_s: float,
) -> dict[str, Any]:
    """
    Portable Relative Bundle Mode:
      - Rewrites `<portable_root>/assets/...` -> `assets/...`
      - Verifies `leftover_abs_paths == []` and `broken_rel_paths == []`
      - Updates `<portable_root>/bundle_manifest.json` with SHA256 & byte counts
      - Runs the 1-frame `filmcraft_cli.py render` smoke (without `--allow-offline`) to prove 0 offline media (`missingMedia` from `file.open`; > 0 raises)
    """
    root_resolved = portable_root.resolve()
    prefixes_to_strip = []
    for assets_cand in {
        str(root_resolved).rstrip("/") + "/assets/",
        str(portable_root.absolute()).rstrip("/") + "/assets/",
        str((portable_root / "assets").resolve()).rstrip("/") + "/",
    }:
        prefixes_to_strip.append(unicodedata.normalize("NFC", assets_cand))

    doc = json.loads(compiled_fcproj.read_text(encoding="utf-8"))

    def _rewrite_node(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _rewrite_node(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_rewrite_node(x) for x in node]
        if isinstance(node, str):
            node_nfc = unicodedata.normalize("NFC", node)
            for pref in prefixes_to_strip:
                if node_nfc.startswith(pref):
                    return "assets/" + node_nfc[len(pref) :]
            return node
        return node

    rel_doc = _rewrite_node(doc)

    leftover_abs: list[str] = []
    referenced_rels: list[str] = []

    def _audit_paths(node: Any, key_name: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                _audit_paths(v, k)
        elif isinstance(node, list):
            for x in node:
                _audit_paths(x, key_name)
        elif isinstance(node, str):
            is_path_key = key_name in ("path", "file", "src")
            if node.startswith("assets/"):
                referenced_rels.append(node)
            elif (is_path_key and _is_abs_media_path(node)) or node.startswith(ABS_FS_PREFIXES) or _WIN_ABS_PATH_RE.match(node):
                leftover_abs.append(node)

    _audit_paths(rel_doc)
    unique_rels = sorted(set(referenced_rels))
    broken_rels = [r for r in unique_rels if not (root_resolved / r).is_file()]

    if leftover_abs or broken_rels:
        raise RuntimeError(
            f"Portable bundle path verification failed! "
            f"leftover_abs_paths={leftover_abs[:5]}, broken_rel_paths={broken_rels[:5]}"
        )

    out_fcproj.parent.mkdir(parents=True, exist_ok=True)
    out_fcproj.write_text(json.dumps(rel_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for rel in unique_rels:
        ap = root_resolved / rel
        raw_bytes = ap.read_bytes()
        b_len = len(raw_bytes)
        total_bytes += b_len
        parts = rel.split("/")
        category = parts[1] if len(parts) >= 3 else "misc"
        entries.append(
            {
                "source": str(ap),
                "bundled_rel": rel,
                "category": category,
                "bytes": b_len,
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }
        )

    bm_path = root_resolved / "bundle_manifest.json"
    bm_payload = {
        "project": out_fcproj.stem,
        "source_fcproj": str(out_fcproj),
        "bundle_dir": str(root_resolved),
        "bundled_fcproj": str(out_fcproj),
        "unique_assets": len(entries),
        "total_path_refs": len(referenced_rels),
        "assets_bytes": total_bytes,
        "assets_mb": round(total_bytes / (1024 * 1024), 2),
        "missing_sources": [],
        "leftover_abs_paths": [],
        "broken_rel_paths": [],
        "ok": True,
        "assets": entries,
    }
    bm_path.write_text(json.dumps(bm_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_base: dict[str, Any] = {
        "enabled": True,
        "portable_root": str(root_resolved),
        "bundle_manifest": str(bm_path),
        "unique_assets": len(entries),
        "total_path_refs": len(referenced_rels),
        "assets_mb": bm_payload["assets_mb"],
        "leftover_abs_paths": leftover_abs,
        "broken_rel_paths": broken_rels,
        "smoke_frame_seconds": round(smoke_time_s, 2),
    }
    fc_cli = _filmcraft_cli_cmd()
    if fc_cli is None:
        _loud_smoke_skip("no filmcraft binary")
        return {**summary_base, "smoke_frame_png": None, "smoke_skipped": "skipped: no X/filmcraft (filmcraft binary not found)", "offline_media": None}
    smoke_png = work_dir / "portable_smoke_frame.png"
    if smoke_png.exists():
        smoke_png.unlink()

    smoke_proj = out_fcproj
    temp_assets_link: Path | None = None
    if out_fcproj.parent.resolve() != root_resolved:
        smoke_proj = work_dir / f"_smoke_{out_fcproj.name}"
        shutil.copy2(out_fcproj, smoke_proj)
        link_cand = work_dir / "assets"
        if not link_cand.exists():
            link_cand.symlink_to(root_resolved / "assets")
            temp_assets_link = link_cand

    try:
        rc, res = _filmcraft_render_smoke(fc_cli, smoke_proj, smoke_time_s, smoke_png)
    finally:
        if temp_assets_link is not None and temp_assets_link.is_symlink():
            temp_assets_link.unlink()
        if smoke_proj != out_fcproj and smoke_proj.exists():
            smoke_proj.unlink()

    if rc == 2 and res.get("skipped"):
        _loud_smoke_skip(str(res.get("error")))
        return {**summary_base, "smoke_frame_png": None, "smoke_skipped": str(res.get("error")), "offline_media": None}
    missing = res.get("missingMedia")
    if rc == 3 or (isinstance(missing, int) and missing > 0):
        raise RuntimeError(
            f"Portable bundle has {missing} offline media item(s) (0 required): {res.get('error')}. "
            "A relative path in the .fcproj does not resolve next to the project; fix the bundle, do not use --allow-offline."
        )
    if rc != 0 or not smoke_png.is_file() or not isinstance(missing, int):
        raise RuntimeError(f"Portable 1-frame smoke test failed (exit={rc}): {str(res.get('error') or res)[:500]}")

    return {**summary_base, "smoke_frame_png": str(smoke_png), "offline_media": missing}


def write_editor_report_md(report_path: Path, summary: dict[str, Any]) -> Path:
    """
    Generate `<work>/EDITOR-REPORT.md` (Vietnamese Markdown 8-Gate Scorecard):
      - Tier used (`fast` vs `full`), Verdict (`VERIFIED` | `DONE_WITH_CONCERNS` | `REJECTED`), `owner_stage`
      - Gate 1–8 status table & benchmark timings
      - EBU R128 + Ruling `R35` post-AAC dBTP + BGM steady-state LRA summary
      - Acoustic `lag_ms` Peak-on-Cut + Ruling `R217` Normalized Cross-Correlation (`match_at`) SFX sync
      - Face-Room (`facesafe`) & B-Roll motion / Blank-frame audit
      - Ruling `R200` `claim_gate` notice (when active)
      - Concrete `— Fix:` recommendations
    """
    verdict = summary.get("verdict", "REJECTED")
    tier_used = summary.get("tier_used", "fast")
    owner_stage = summary.get("owner_stage")
    gates = summary.get("gates", {})
    timings = summary.get("timings_sec", {})
    san = summary.get("sanitizer") or {}
    aud = summary.get("audio_mastering") or {}
    sfx_aud = summary.get("sfx_audit") or {}
    r217 = summary.get("sfx_sync_r217") or {}
    vis = summary.get("visual_rigor") or {}
    chrom = summary.get("chromatic_diversity") or {}
    trans_cont = summary.get("transition_continuity") or {}
    sec_grps = summary.get("secondary_text_groups") or {}
    cran_aud = summary.get("cranial_exclusion_audit") or {}
    cri100_aud = summary.get("industry_cri100_veto") or {}
    kt_aud = summary.get("kinetic_typography_audit") or {}
    mb_info = summary.get("micro_bridges") or {}
    claim = summary.get("claim_gate") or {}
    diags = summary.get("diagnostics") or []
    concerns = summary.get("concerns") or []
    inputs = summary.get("inputs") or {}
    outputs = summary.get("outputs") or {}

    gate_labels = [
        ("gate1_mechanical_sanitizer", "Gate 1 · Mechanical Sanitizer + `bgm_stops`, `lag_ms`, Micro-Fades & MD5 Dedup"),
        ("gate2_spec_lint", "Gate 2 · Pre-Build Spec Lint (`spec_lint.py`)"),
        ("gate3_edit_rules", "Gate 3 · Editorial Rules + `v7.0` Cranial Lock, CRI-100 Veto & Color/Density Audits"),
        ("gate4_fc_build_parity", "Gate 4 · FilmCraft Compile, Keyframe Parity & `v7.0` `AdjustmentLayer` Micro-Bridges"),
        ("gate5_postfx_and_contact_sheet", "Gate 5 · Post-FX, Contact Sheet & Pixel/Face-Room Audit"),
        ("gate6_closed_loop_loudness", "Gate 6 · Closed-Loop EBU R128 + R35 Post-AAC True-Peak"),
        ("gate7_sfx_and_portable_bundle", "Gate 7 · SFX Integrity + R217 `match_at` NCC Sync"),
        ("gate8_epistemic_verdict_and_report", "Gate 8 · Epistemic `claim_gate` (R200) & Tri-State Verdict"),
    ]

    lines: list[str] = [
        f"# EDITOR-REPORT — `{Path(str(inputs.get('out') or 'project.fcproj')).name}` (Compiler v{COMPILER_VERSION})",
        "",
        f"- **Phán quyết (Verdict):** `{verdict}`" + (f" · **Owner Stage:** `{owner_stage}`" if owner_stage else ""),
        f"- **Chế độ kiểm định (Tier):** `{tier_used}` (yêu cầu: `{inputs.get('tier_requested', 'auto')}`)",
        f"- **Tổng thời gian thực thi:** `{summary.get('total_elapsed_sec', 0.0):.2f}s`",
        f"- **File `.fcproj` xuất ra:** `{outputs.get('fcproj') or inputs.get('out')}`",
        f"- **Contact Sheet (`1440x2560`):** `{outputs.get('qa_contact_sheet') or '—'}`",
        "",
        "## 1. Bảng Điểm 8 Cổng Kiểm Định (Gates 1–8)",
        "",
        "| Cổng | Trạng thái |",
        "|---|---|",
    ]
    for g_key, g_title in gate_labels:
        lines.append(f"| {g_title} | `{gates.get(g_key, 'PENDING')}` |")

    if claim.get("active"):
        lines += [
            "",
            "## 2. Cổng Thực Chứng Epistemic — Ruling `R200` (`claim_gate`)",
            "",
            "> **LƯU Ý BẮT BUỘC (Ruling R200 — `claim_gate: active`):** Bản dựng kỹ thuật đã hoàn tất, "
            "**NHƯNG KHÔNG ĐĂNG TẢI CÔNG KHAI** trước khi người dùng trực tiếp xác nhận tính xác thực của mọi con số/tuyên bố "
            "trong lời thoại và bật nhãn minh hoạ AI (TikTok / YouTube / Reels) đối với các cảnh B-roll do AI tạo.",
        ]
    else:
        lines += [
            "",
            "## 2. Cổng Thực Chứng Epistemic — Ruling `R200` (`claim_gate`)",
            "",
            "- `claim_gate`: **không bật** (`false`).",
        ]

    post_aac_tp = aud.get("post_aac_true_peak_dbtp")
    post_aac_str = f"`{post_aac_tp:.2f} dBTP` (R35 <= `{inputs.get('tp_ceiling_dbtp', -1.5)} dBTP`)" if isinstance(post_aac_tp, (int, float)) and math.isfinite(post_aac_tp) else "`—` (chỉ đo ở `--tier full`)"
    lines += [
        "",
        "## 3. Âm Thanh Chủ Động — EBU R128, BGM Steady-State & Ruling `R35`",
        "",
        f"- **Integrated Loudness (`mix.wav`):** `{aud.get('measured_lufs', '—')} LUFS` (mục tiêu `{inputs.get('target_lufs', -16.0)} LUFS`, sai lệch `{aud.get('lufs_deviation_lu', '—')} LU`)",
        f"- **Loudness Range (`LRA`):** `{aud.get('measured_lra_lu', '—')} LU`",
        f"- **Lossless PCM True Peak:** `{aud.get('measured_true_peak_dbtp', '—')} dBTP` (giới hạn `<= {inputs.get('tp_ceiling_dbtp', -1.5)} dBTP`)",
        f"- **Post-AAC 192k True Peak (Ruling `R35`):** {post_aac_str}",
        f"- **Master `hard_limiter` trần cuối:** `{aud.get('limiter_max_db', inputs.get('limiter_db', -2.2))} dB` · Số lượt Closed-Loop: `{aud.get('closed_loop_attempts', 0)}`",
    ]
    bgm_opts = san.get("bgm_offset_optimizations") or []
    if bgm_opts:
        for b in bgm_opts:
            lines.append(
                f"- **BGM Steady-State Offset (`{b.get('src')}`):** chọn `in = {b.get('selected_in_s')}s` "
                f"(`LRA = {b.get('lra_lu')} LU`, so với `in=0.0s` `LRA = {b.get('lra_at_0_lu')} LU`)"
            )

    lines += [
        "",
        "## 4. Đồng Bộ Vi Mô SFX — Acoustic `lag_ms` (`5ms env5`) & Ruling `R217` (`match_at`)",
        "",
        f"- **Tổng sự kiện SFX:** `{sfx_aud.get('events', 0)}` · Unique takes: `{sfx_aud.get('unique_takes', 0)}` · Lặp file/MD5: `{len(sfx_aud.get('repeated_takes') or [])}` (MD5 dedup loại `{san.get('md5_dedup_skipped', 0)}` bản trùng)",
        f"- **Căn đỉnh `lag_ms` Peak-on-Cut (Gate 1):** đã căn `{san.get('lag_ms_aligned_count', 0)}` clip (`0f` tại điểm cắt V1, `+5f` tại điểm dừng chữ/UI)",
        f"- **Kiểm chứng tương quan chéo chuẩn hoá `R217` (`stems/sfx.wav` vs `mix.wav`):** "
        f"`{r217.get('ncc_verified_cues', 0)}` cue đã đo · Trung vị độ lệch tuyệt đối: `{r217.get('median_abs_offset_frames', 0.0):.2f} frames` "
        f"· Cue câm (`energy == 0`): `{len(r217.get('muted_cues') or [])}` · Cue lệch `> 3 frames`: `{len(r217.get('shifted_cues') or [])}`",
    ]

    lines += [
        "",
        "## 5. Kiểm Định Hình Ảnh, Chuyển Động B-Roll & Vùng Mặt (`facesafe`)",
        "",
    ]
    if vis.get("executed"):
        lines += [
            f"- **Blank Render Check (16 QA frames):** `min(grayscale_std) = {vis.get('min_grayscale_std', 0.0):.2f}` (ngưỡng `>= 10.0`) · Khung đen/hỏng: `{len(vis.get('blank_frames') or [])}`",
            f"- **Frozen Video B-Roll Check (`270x480`):** đã đo `{vis.get('broll_clips_checked', 0)}` clip video B-roll trên V1 · B-roll đứng hình (`FROZEN_BROLL`): `{len(vis.get('frozen_broll') or [])}`",
            f"- **Face-Room & Safe-Zone Ink Audit (`50..1030 x 140..1760`, Ruling `R26` & `R208`):** "
            f"phát hiện mặt trên `{vis.get('aroll_qa_faces_detected', 0)}/{vis.get('aroll_qa_frames_total', 0)}` khung QA A-roll · "
            f"đã đo `{vis.get('text_clips_audited', 0)}` lớp chữ (miễn trừ hook `<1.5s` theo R208: `{vis.get('r208_hook_exempt_clips', 0)}`) · "
            f"Cảnh báo đè mặt: `{len(vis.get('face_room_warnings') or [])}` · Cảnh báo tràn Safe-Zone: `{len(vis.get('safe_zone_warnings') or [])}`",
        ]
    else:
        lines.append("- Đã chạy chế độ `--tier fast` (xuất đủ 16 khung QA + `qa_contact_sheet.jpg`; bật `--tier full` để kích hoạt kiểm tra `facesafe` & `FROZEN_BROLL` sâu).")

    gc = sec_grps.get("group_counts") or {}
    hue_dist_str = json.dumps(chrom.get("hue_distribution") or {}, ensure_ascii=False)
    lines += [
        "",
        "## 6. Kiểm Định Thẩm Mỹ & Nhịp Điệu `v6.0` (`Color-World Polarity` · `4-Cut & J-Cut` · `Spatial Density <= 2`)",
        "",
        f"- **Chính sách sắc độ & Polarity (`audit_chromatic_diversity`):** policy `{chrom.get('color_policy', 'color_world_polarity')}` · "
        f"trạng thái `{chrom.get('status', '—')}` · `primary_signature_hue`: `{chrom.get('primary_signature_hue')}` "
        f"(`{chrom.get('primary_signature_share_pct', 0.0)}%`) · `secondary_contrast_hue`: `{chrom.get('secondary_contrast_hue')}` "
        f"(`{chrom.get('secondary_contrast_share_pct', 0.0)}%`) · `hue_distribution`: `{hue_dist_str}` · "
        f"`RAINBOW_HUE_SOUP`: `{chrom.get('rainbow_hue_soup', False)}` · `polarity_light_clips_or_frames`: `{chrom.get('polarity_light_clips_or_frames', 0)}`",
        f"- **Ngữ pháp 4 kiểu cắt, Bimodal `C7` J-Cut & Âm thanh (`audit_transition_and_rhythm_continuity`):** trạng thái `{trans_cont.get('status', '—')}` · "
        f"`clean_hard_cut_pct`: `{trans_cont.get('clean_hard_cut_pct', 0.0)}%` (`wgpu={trans_cont.get('wgpu_transition_pct', 0.0)}%`) · "
        f"`true_vocal_jcut_count`: `{trans_cont.get('true_vocal_jcut_count', 0)}` · `bgm_silence_stops_count`: `{trans_cont.get('bgm_silence_stops_count', 0)}` · "
        f"`heavy_whoosh_per_min`: `{trans_cont.get('heavy_whoosh_per_min', 0.0)}/min` · `DEAD_POSTCUT_CAMERA_HOLD`: `{trans_cont.get('dead_postcut_camera_hold_count', 0)}`",
        f"- **Mật độ không gian `MAX_ZONES <= 2`, Card-Text Mutex & Nhịp thở (`audit_secondary_text_groups`):** trạng thái `{sec_grps.get('status', '—')}` · "
        f"`active_secondary_groups`: `{sec_grps.get('active_secondary_groups', 0)}` (`{sec_grps.get('active_secondary_group_names', [])}`) · "
        f"`max_concurrent_overlay_zones`: `{sec_grps.get('max_concurrent_overlay_zones', 0)}` (`clutter_overload_pct={sec_grps.get('clutter_overload_pct', 0.0)}%`) · "
        f"`zero_card_text_collision`: `{sec_grps.get('zero_card_text_collision', True)}` · "
        f"`clean_breathing_frame_pct`: `{sec_grps.get('clean_breathing_frame_pct', 0.0)}%` · `lowercase_hero_pct`: `{sec_grps.get('lowercase_hero_pct', 100.0)}%`",
        "",
        "## 6B. Cổng Vật Lý Quang Học & Y Khoa `v7.0/v7.1` (`CRANIAL_EXCLUSION_AUDIT` + Lane-B · `INDUSTRY_CRI100_VETO_AUDIT` · `AdjustmentLayer` Micro-Bridges)",
        "",
        f"- **Khóa vùng sọ mặt `[hair_top - 48px, chin + 32px]` (`CRANIAL_EXCLUSION_AUDIT`):** trạng thái `{cran_aud.get('status', '—')}` · "
        f"đã đo `{cran_aud.get('foreground_text_clips_audited', 0)}` lớp tiền cảnh (`Lane-B plates`: `{cran_aud.get('foreground_lane_b_plates_audited', 0)}`, miễn trừ Z-depth sau lưng chủ thể: `{cran_aud.get('behind_subject_zdepth_exempt', 0)}`) · "
        f"Vi phạm chạm trán/tóc/cằm: `{cran_aud.get('violation_count', 0)}`",
        f"- **Kiểm định trung tính màu `CRI-100` & Vùng Cấm Chuyên Ngành (`INDUSTRY_CRI100_VETO_AUDIT`):** "
        f"`industry_skin={cri100_aud.get('industry_skin') or 'general'}` · trạng thái `{cri100_aud.get('status', 'SKIPPED_GENERAL')}` · "
        f"Số lỗi Veto (`Warm Film Burn` / `Yellow LUT` / `bone_crack` / `enamel_gum_bbox` / `macro_subject_bbox`): `{cri100_aud.get('veto_count', 0)}`",
        f"- **Cầu nối quang học `AdjustmentLayer` trên `.fcproj` (`inject_micro_bridge_adjustment_layers_fcproj`):** "
        f"`injected={mb_info.get('injected', False)}` · số cầu nối `{mb_info.get('count', 0)}` trên rãnh `{mb_info.get('track_name', '—')}` "
        f"(dưới rãnh chữ tiền cảnh để giữ chữ sắc nét 100%)",
        "",
        "## 6C. Cổng Chống Rập Khuôn Kinetic Typography `v7.1` (`Gate 3C · KINETIC_TYPOGRAPHY_CHOREOGRAPHY_AUDIT`)",
        "",
        f"- **Trạng thái Gate 3C:** `{kt_aud.get('status', '—')}` · Số nhịp chữ kinetic đã đo: `{kt_aud.get('typo_beats_audited', 0)}` · "
        f"`STATIC_HERO_PNG_STAMP`: `{kt_aud.get('static_hero_png_stamps', 0)}`",
        f"- **Đa dạng bố cục & chuyển động (`kt01..kt12`):** `distinct_silhouettes={kt_aud.get('distinct_silhouettes', 0)}` "
        f"(`max_share={kt_aud.get('max_silhouette_share_pct', 0.0)}%`, `max_run={kt_aud.get('max_consecutive_silhouette', 0)}`) · "
        f"`distinct_entrance_styles={kt_aud.get('distinct_entrance_styles', 0)}` (`max_run={kt_aud.get('max_consecutive_entrance', 0)})`",
        f"- **Kiềm chế Pill Badge (`<= 20%` mục tiêu, `0` trùng lặp):** `pill_badges={kt_aud.get('pill_badge_count', 0)}` "
        f"(`{kt_aud.get('pill_badge_ratio_pct', 0.0)}%`) · Trùng nhãn `badge_text`: `{kt_aud.get('duplicate_badges', {})}`",
    ]

    lines += [
        "",
        "## 7. Cảnh Báo & Đề Xuất Tự Sửa (`— Fix:` Self-Repair Diagnostics)",
        "",
    ]
    if not diags and not concerns and not summary.get("error"):
        lines.append("- **Không có lỗi hay cảnh báo nào (`0 issues`).** Bản dựng đạt chuẩn xuất xưởng.")
    else:
        if summary.get("error"):
            lines.append(f"- **LỖI DỪNG BUILD:** {summary['error']}")
        for d in diags:
            lines.append(
                f"- **[{d.get('severity', 'WARN')} · {d.get('gate', 'gate')} · `{d.get('code', '')}`]** "
                f"{d.get('message', '')} — Fix: {d.get('fix', '')}"
            )
        diag_fixes = {d.get("fix", "") for d in diags}
        for c_msg in concerns:
            if not any(fx and fx in c_msg for fx in diag_fixes):
                lines.append(f"- **[CONCERN]** {c_msg}")

    lines += [
        "",
        "## 8. Thời Gian Từng Bước (Timings)",
        "",
        "| Giai đoạn | Thời gian (s) |",
        "|---|---|",
    ]
    for k_t, v_t in timings.items():
        lines.append(f"| `{k_t}` | `{v_t:.3f}s` |")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def open_in_filmcraft_gui(fcproj_path: Path, display: str) -> int:
    fc_bin = _filmcraft_bin()
    env = {**os.environ, "DISPLAY": display}
    proc = subprocess.Popen(
        [fc_bin, "--no-recover", str(fcproj_path.resolve())],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"🖥️  Opened {fcproj_path.name} in FilmCraft GUI (PID={proc.pid}, DISPLAY={display})")
    return proc.pid


def sync_sidecar_metadata(spec_in: Path, work_dir: Path, portable_root: Path | None) -> None:
    """Copy sidecar hints (`_broll_sources.json`, `pain.json`, `profile.json`) into work_dir if present beside input spec."""
    if spec_in.parent.resolve() == work_dir.resolve():
        return
    for fname in ("_broll_sources.json", "pain.json", "profile.json"):
        dst = work_dir / fname
        if dst.is_file():
            continue
        for cand_dir in [spec_in.parent, portable_root / "extras" if portable_root else None]:
            if cand_dir is not None and (cand_dir / fname).is_file():
                shutil.copy2(cand_dir / fname, dst)
                break


def run_edit_rules_json(cmd: list[str]) -> list[dict[str, Any]]:
    """Run `edit_rules.py audit ... --json`; a crash or non-JSON output raises instead of reading as "0 errors".

    edit_rules exits 0 when clean and 1 when it reports LỖI items; any other exit code, a non-list output,
    or exit 1 without a LỖI item (a traceback after partial output) is a crash.
    """
    r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace")
    tail = (r.stderr or r.stdout or "").strip()[-300:]
    try:
        items = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"edit_rules crashed: exit {r.returncode}, non-JSON output ({exc}): {tail}") from exc
    if not isinstance(items, list):
        raise RuntimeError(f"edit_rules crashed: exit {r.returncode}, expected a JSON list, got {type(items).__name__}")
    has_err = any(isinstance(it, dict) and it.get("status") == "LỖI" for it in items)
    if r.returncode not in (0, 1) or (r.returncode == 1) != has_err:
        raise RuntimeError(f"edit_rules crashed: exit {r.returncode} with {'' if has_err else 'no '}LỖI items: {tail}")
    return items


def gate_tally(gates: dict[str, str]) -> dict[str, Any]:
    """Honest gate count for the final banner: only `PASS...` counts as passed; SKIPPED / WARN / other states are named."""
    passed = [k for k, v in gates.items() if str(v).startswith("PASS")]
    skipped = [k for k, v in gates.items() if str(v).startswith("SKIPPED")]
    other = [k for k, v in gates.items() if k not in passed and k not in skipped]
    banner = f"{len(passed)}/{len(gates)} GATES PASSED"
    if skipped:
        banner += f" · SKIPPED: {', '.join(skipped)}"
    if other:
        banner += " · NOT PASSED: " + ", ".join(f"{k}={gates[k]}" for k in other)
    return {"passed": len(passed), "total": len(gates), "skipped": skipped, "not_passed": other, "banner": banner}


def resolve_execution_tier(
    requested_tier: str,
    context_doc: dict[str, Any] | None,
    raw_spec: dict[str, Any],
    strict_rules: bool,
    claim_gate_flag: bool | None,
) -> tuple[str, bool]:
    """Resolve `(tier_used, claim_gate_active)` according to v5.1 Dual-Tier rules."""
    spec_meta = raw_spec.get("meta") if isinstance(raw_spec.get("meta"), dict) else {}
    ctx_claim = bool((context_doc or {}).get("claim_gate")) if isinstance(context_doc, dict) else False
    claim_gate_active = bool(claim_gate_flag) if claim_gate_flag is not None else bool(spec_meta.get("claim_gate") or ctx_claim)

    if requested_tier in ("fast", "full"):
        return requested_tier, claim_gate_active

    # `auto` mode
    if strict_rules or claim_gate_active:
        return "full", claim_gate_active
    if isinstance(context_doc, dict):
        rec = str(context_doc.get("recommended_compile_tier") or "").strip().lower()
        if rec in ("fast", "full"):
            return rec, claim_gate_active
    return "fast", claim_gate_active


def _run_self_tests() -> int:
    """
    `v7.0` Stateless Gatekeeper Smoke & Unit Test Suite:
      1. `CRANIAL_EXCLUSION_AUDIT` (`[hair_top - 48px, chin + 32px]` Foreground Text Lock + Z-depth RVM exemption)
      2. `INDUSTRY_CRI100_VETO_AUDIT` (`dental_clinic`, `luxury_skincare`, `nail_hair_salon` vetoes + bbox guards)
      3. `sanitize_spec` (`persistent_bridge` C8 guard exemption + `micro_bridges_planned`) +
         `inject_micro_bridge_adjustment_layers_fcproj` (`exposure_bloom_landing_3f` & `rack_focus_bridge_13f`)
         verified against live `fc_build_fast.py` & `filmcraft_cli.py render`!
    """
    import tempfile

    # 1. Test `CRANIAL_EXCLUSION_AUDIT`
    bad_cranial_spec: dict[str, Any] = {
        "name": "test_cranial_bad",
        "fps": 60,
        "width": 1080,
        "height": 1920,
        "duration": 4.0,
        "meta": {
            "cranial_zone": {"hair_top_y": 360.0, "chin_y": 820.0},
            "strict_cranial_lock": True,
        },
        "tracks": [
            {
                "type": "video",
                "name": "V1 · A-Roll",
                "clips": [{"name": "A-Roll #1", "src": "/tmp/fake_aroll.mp4", "at": 0.0, "dur": 4.0}],
            },
            {
                "type": "text",
                "name": "TEXT · Hero",
                "clips": [
                    {
                        "name": "Bad Forehead Text",
                        "text": "Đè Lên Trán",
                        "font": "Be Vietnam Pro",
                        "size": 84,
                        "position": [540.0, 560.0],
                        "at": 1.80,
                        "dur": 1.20,
                    }
                ],
            },
        ],
    }
    res_cran_bad = audit_cranial_exclusion(bad_cranial_spec, raw_spec=bad_cranial_spec, spec_meta=bad_cranial_spec["meta"])
    assert res_cran_bad["status"] == "FAIL" and res_cran_bad["violation_count"] == 1, f"Expected cranial FAIL, got {res_cran_bad}"
    assert "resolve_dual_rail_safe_y" in res_cran_bad["violations"][0]["fix"]

    good_cranial_spec: dict[str, Any] = {
        "name": "test_cranial_good",
        "fps": 60,
        "width": 1080,
        "height": 1920,
        "duration": 4.0,
        "meta": {
            "cranial_zone": {"hair_top_y": 420.0, "chin_y": 860.0},
            "strict_cranial_lock": True,
        },
        "tracks": [
            {
                "type": "video",
                "name": "V1 · A-Roll",
                "clips": [{"name": "A-Roll #1", "src": "/tmp/fake_aroll.mp4", "at": 0.0, "dur": 4.0}],
            },
            {
                "type": "text",
                "name": "TEXT · Behind Subject",
                "clips": [
                    {
                        "name": "Z-Depth Hero",
                        "text": "HỆ THỐNG",
                        "size": 180,
                        "position": [540.0, 620.0],
                        "z_plane": "behind_subject",
                        "at": 0.50,
                        "dur": 2.00,
                    }
                ],
            },
            {
                "type": "video",
                "name": "V2 · RVM Speaker Cutout",
                "clips": [{"name": "Speaker RVM", "src": "/tmp/speaker_rvm.mov", "at": 0.0, "dur": 4.0}],
            },
            {
                "type": "text",
                "name": "TEXT · Dual Rail Safe",
                "clips": [
                    {
                        "name": "Upper Editorial",
                        "text": "Chuẩn Điện Ảnh",
                        "size": 72,
                        "position": [540.0, 260.0],
                        "at": 1.80,
                        "dur": 1.00,
                    },
                    {
                        "name": "Chest Tactile",
                        "text": "Sắc nét tuyệt đối",
                        "size": 68,
                        "position": [540.0, 1420.0],
                        "at": 2.90,
                        "dur": 0.90,
                    },
                ],
            },
        ],
    }
    res_cran_good = audit_cranial_exclusion(good_cranial_spec, raw_spec=good_cranial_spec, spec_meta=good_cranial_spec["meta"])
    assert res_cran_good["status"] == "PASS" and res_cran_good["violation_count"] == 0, f"Expected cranial PASS, got {res_cran_good}"
    assert res_cran_good["behind_subject_zdepth_exempt"] == 1

    # 2. Test `INDUSTRY_CRI100_VETO_AUDIT`
    bad_dental_spec: dict[str, Any] = {
        "name": "test_dental_veto",
        "fps": 60,
        "width": 1080,
        "height": 1920,
        "duration": 4.0,
        "meta": {
            "industry_skin": "dental_clinic",
            "transition_style": "warm_film_burn",
            "enamel_gum_bbox": [340.0, 680.0, 740.0, 860.0],
            "macro_subject_bbox": [{"at": 2.0, "dur": 1.5, "bbox": [260.0, 520.0, 820.0, 1180.0]}],
        },
        "tracks": [
            {
                "type": "video",
                "name": "V1 · Dental Macro",
                "clips": [
                    {
                        "name": "Smile Shot",
                        "src": "/tmp/smile.mp4",
                        "at": 0.0,
                        "dur": 4.0,
                        "effects": [{"effect": "lumetri", "params": {"temperature": 15.0, "look_lut": "kodak_warm.cube"}}],
                    }
                ],
            },
            {
                "type": "text",
                "name": "TEXT · Caption",
                "clips": [
                    {
                        "name": "Over Teeth",
                        "text": "Sứ Veneer",
                        "size": 84,
                        "position": [540.0, 760.0],
                        "at": 0.50,
                        "dur": 1.20,
                    },
                    {
                        "name": "Over Macro",
                        "text": "Chi tiết",
                        "size": 80,
                        "position": [540.0, 880.0],
                        "at": 2.20,
                        "dur": 1.00,
                    },
                ],
            },
            {
                "type": "audio",
                "name": "A2 · SFX",
                "clips": [{"name": "SFX bone_crack harsh", "src": "/tmp/bone_crack_01.wav", "at": 0.50, "dur": 0.40}],
            },
        ],
    }
    res_cri_bad = audit_industry_cri100_veto(
        bad_dental_spec,
        raw_spec=bad_dental_spec,
        spec_meta=bad_dental_spec["meta"],
        strict_cri100=True,
    )
    assert res_cri_bad["status"] == "FAIL", f"Expected CRI100 FAIL, got {res_cri_bad}"
    for expected_code in (
        "CRI100_FORBIDDEN_WARM_FILM_BURN",
        "CRI100_FORBIDDEN_YELLOW_WARM_LUT",
        "DENTAL_FORBIDDEN_HARSH_SFX",
        "ENAMEL_GUM_TEXT_OCCLUSION",
        "MACRO_SUBJECT_TEXT_OCCLUSION",
    ):
        assert expected_code in res_cri_bad["warning_codes"], f"Missing {expected_code} in {res_cri_bad['warning_codes']}"

    good_dental_spec: dict[str, Any] = {
        "name": "test_dental_clean",
        "fps": 60,
        "width": 1080,
        "height": 1920,
        "duration": 4.0,
        "meta": {
            "industry_skin": "dental_clinic",
            "transition_style": "rack_focus_bridge_13f",
            "enamel_gum_bbox": [340.0, 680.0, 740.0, 860.0],
        },
        "tracks": [
            {
                "type": "video",
                "name": "V1 · Dental CRI100",
                "clips": [
                    {
                        "name": "Smile Shot Clean",
                        "src": "/tmp/smile.mp4",
                        "at": 0.0,
                        "dur": 4.0,
                        "effects": [{"effect": "lumetri", "params": {"temperature": 0.0}}],
                    }
                ],
            },
            {
                "type": "text",
                "name": "TEXT · Dual Rail",
                "clips": [
                    {
                        "name": "Porcelain Title",
                        "text": "Sứ Lạnh CRI-100",
                        "size": 76,
                        "position": [540.0, 1420.0],
                        "at": 0.50,
                        "dur": 1.20,
                    }
                ],
            },
            {
                "type": "audio",
                "name": "A2 · SFX",
                "clips": [{"name": "SFX soft_tick", "src": "/tmp/soft_tick_01.wav", "at": 0.50, "dur": 0.30}],
            },
        ],
    }
    res_cri_good = audit_industry_cri100_veto(
        good_dental_spec,
        raw_spec=good_dental_spec,
        spec_meta=good_dental_spec["meta"],
        strict_cri100=True,
    )
    assert res_cri_good["status"] == "PASS" and res_cri_good["veto_count"] == 0, f"Expected CRI100 PASS, got {res_cri_good}"

    # 3. End-to-End `sanitize_spec` + `fc_build_fast.py` + `inject_micro_bridge_adjustment_layers_fcproj` + `filmcraft_cli.py render`
    with tempfile.TemporaryDirectory(prefix="v70_compiler_selftest_") as td:
        tdir = Path(td)
        clip_mp4 = tdir / "plate.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=540x960:rate=60:duration=1.5",
                "-pix_fmt",
                "yuv420p",
                str(clip_mp4),
            ],
            check=True,
            timeout=_RUN_TIMEOUT_S,
        )
        bridge_spec: dict[str, Any] = {
            "name": "v70_micro_bridge_smoke",
            "fps": 60,
            "width": 1080,
            "height": 1920,
            "duration": 1.40,
            "meta": {
                "industry_skin": "luxury_skincare",
                "micro_bridges": [
                    {"type": "exposure_bloom_landing_3f", "at": 0.45, "peak_ev": 1.55},
                    {"type": "rack_focus_bridge_13f", "at": 0.95, "max_sigma": 14.0},
                ],
            },
            "tracks": [
                {
                    "type": "video",
                    "name": "V1 · Plate",
                    "clips": [
                        {"name": "Shot 1", "src": str(clip_mp4), "in": 0.0, "at": 0.0, "dur": 0.45},
                        {"name": "Shot 2", "src": str(clip_mp4), "in": 0.2, "at": 0.45, "dur": 0.50},
                        {"name": "Shot 3", "src": str(clip_mp4), "in": 0.4, "at": 0.95, "dur": 0.45},
                    ],
                },
                {
                    "type": "text",
                    "name": "TEXT · Persistent Bridge",
                    "clips": [
                        {
                            "name": "Keyword · Bridge",
                            "text": "TINH KHIẾT",
                            "font": "Be Vietnam Pro",
                            "size": 78,
                            "color": "#FAFAFA",
                            "position": [540.0, 1420.0],
                            "at": 0.3833,
                            "dur": 0.2333,
                            "persistent_bridge": True,
                        }
                    ],
                },
            ],
        }
        san_doc, san_st = sanitize_spec(bridge_spec, spec_dir=tdir, work_dir=tdir, enable_c8_guard=True)
        assert len(san_st["persistent_text_bridges_preserved"]) == 1, f"Persistent bridge not preserved: {san_st}"
        assert len(san_st["c8_trimmed_clips"]) == 0, f"Persistent bridge should bypass C8 trim: {san_st}"
        assert len(san_st["micro_bridges_planned"]) == 2, f"Expected 2 planned micro-bridges: {san_st}"

        san_json = tdir / "smoke.sanitized.craft.json"
        out_fcproj = tdir / "smoke.fcproj"
        rep_json = tdir / "build_rep.json"
        san_json.write_text(json.dumps(san_doc, ensure_ascii=False, indent=2), encoding="utf-8")

        py = _py_bin()
        r_b = subprocess.run(
            [py, str(FC_BUILD_FAST_PY), str(san_json), str(out_fcproj), "--report", str(rep_json)],
            capture_output=True,
            text=True,
            check=False,
            timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace",
        )
        assert r_b.returncode == 0, f"fc_build_fast failed: {r_b.stderr or r_b.stdout}"
        mb_res = inject_micro_bridge_adjustment_layers_fcproj(out_fcproj, san_st["micro_bridges_planned"], fps=60.0)
        assert mb_res["injected"] is True and mb_res["count"] == 2, f"Micro-bridge injection failed: {mb_res}"
        assert mb_res["track_index"] == 1, f"AdjustmentLayer track must sit between V1(0) and TEXT(2), got {mb_res}"

        fc_cli = _filmcraft_cli_cmd()
        arr_png = None
        out_png = tdir / "bloom_frame.png"
        rc_ren, res_ren = (
            _filmcraft_render_smoke(fc_cli, out_fcproj, 0.45, out_png)
            if fc_cli is not None else (2, {"skipped": True, "error": "skipped: no X/filmcraft (filmcraft binary not found)"})
        )
        if rc_ren == 2 and res_ren.get("skipped"):
            print(f"⚠️  [SELF-TEST SKIPPED] 1-frame `filmcraft_cli.py render` smoke ({res_ren.get('error')}); fc_build_fast + micro-bridge injection above DID run.")
        else:
            assert rc_ren == 0 and out_png.is_file(), f"filmcraft_cli.py render failed (exit={rc_ren}): {res_ren}"
            assert res_ren.get("missingMedia") == 0, f"self-test project has offline media: {res_ren}"
            arr_png = np.asarray(Image.open(out_png).convert("L"), dtype=np.float32)
            assert float(arr_png.std()) > 5.0, f"Rendered frame looks blank: std={arr_png.std():.2f}"

        # 4. v7.1 Lane-B Cranial Exclusion Blind-Spot Closure + Sidecar `.typo_meta.json` Harvesting
        sidecar_plate_mov = tdir / "kt_bad_forehead.mov"
        sidecar_plate_mov.write_bytes(b"")
        Path(f"{sidecar_plate_mov}.typo_meta.json").write_text(
            json.dumps(
                {
                    "version": "7.1",
                    "template": "kt01_kiss_editorial_2line",
                    "layout_silhouette": "SIL_KISS_2L",
                    "entrance_style": "player3_air_cushion_kiss_20f",
                    "mode": "mov",
                    "z_plane": "foreground",
                    "pos_x": 540.0,
                    "pos_y": 580.0,
                    "ink_bbox_screen": [220.0, 490.0, 860.0, 670.0],
                }
            ),
            encoding="utf-8",
        )
        bad_laneb_cranial_spec: dict[str, Any] = {
            "name": "test_laneb_cranial_bad",
            "fps": 60,
            "width": 1080,
            "height": 1920,
            "duration": 4.0,
            "meta": {
                "cranial_zone": {"hair_top_y": 380.0, "chin_y": 820.0},
                "strict_cranial_lock": True,
            },
            "tracks": [
                {
                    "type": "video",
                    "name": "V1 · A-Roll",
                    "clips": [{"name": "A-Roll #1", "src": str(clip_mp4), "at": 0.0, "dur": 1.4}],
                },
                {
                    "type": "video",
                    "name": "V2 · Kinetic Typo Plates",
                    "clips": [
                        {
                            "name": "Bad Forehead Plate",
                            "src": str(sidecar_plate_mov),
                            "at": 0.20,
                            "dur": 1.00,
                            "motion": {"anchor": [540.0, 220.0], "position": [540.0, 580.0], "scale": 100.0},
                        }
                    ],
                },
            ],
        }
        san_lb_doc, san_lb_st = sanitize_spec(bad_laneb_cranial_spec, spec_dir=tdir, work_dir=tdir)
        assert len(san_lb_st["typo_kinetic_annotations"]) == 1, f"Sidecar typo_meta not harvested: {san_lb_st}"
        res_lb_cran_bad = audit_cranial_exclusion(
            san_lb_doc,
            raw_spec=bad_laneb_cranial_spec,
            spec_meta=bad_laneb_cranial_spec["meta"],
            san_stats=san_lb_st,
        )
        assert res_lb_cran_bad["status"] == "FAIL" and res_lb_cran_bad["foreground_lane_b_plates_audited"] == 1, (
            f"Expected Lane-B cranial FAIL, got {res_lb_cran_bad}"
        )

        # 5. v7.1 Gate 3C: Bad V17-style static/repetitive spec -> catches ALL 4 veto codes!
        bad_v17_clips: list[dict[str, Any]] = []
        for idx_v17 in range(10):
            bad_v17_clips.append(
                {
                    "name": f"Hero Stamp {idx_v17 + 1:02d}",
                    "src": f"/tmp/web_plates/c{idx_v17 + 1:02d}_stamp.png",
                    "at": round(idx_v17 * 1.2, 3),
                    "dur": 1.0,
                    "typo_kinetic_meta": {
                        "template": "dviet_overlapping_feather_cluster",
                        "layout_silhouette": "SIL_FEATHER_SWASH",
                        "entrance_style": "feather29_swash_bloom_22f",
                        "mode": "still",
                        "has_pill_badge": idx_v17 < 6,
                        "badge_text": "AI LOCK" if idx_v17 < 3 else (f"STEP {idx_v17}" if idx_v17 < 6 else ""),
                    },
                }
            )
        bad_v17_spec: dict[str, Any] = {
            "name": "test_bad_v17_stamps",
            "fps": 60,
            "width": 1080,
            "height": 1920,
            "duration": 14.0,
            "tracks": [
                {"type": "video", "name": "V1 · Spine", "clips": [{"name": "S1", "src": str(clip_mp4), "at": 0.0, "dur": 1.4}]},
                {"type": "video", "name": "V2 · Hero Typo Plates", "clips": bad_v17_clips},
            ],
        }
        res_v17_fast = audit_kinetic_typography_choreography(bad_v17_spec, raw_spec=bad_v17_spec, tier_used="fast")
        res_v17_full = audit_kinetic_typography_choreography(bad_v17_spec, raw_spec=bad_v17_spec, tier_used="full")
        assert res_v17_fast["status"] == "FAIL", f"STATIC_HERO_PNG_STAMP must FAIL even in fast tier: {res_v17_fast}"
        assert res_v17_full["status"] == "FAIL"
        for req_v71_code in (
            "STATIC_HERO_PNG_STAMP",
            "LAYOUT_SILHOUETTE_MONOTONY",
            "PILL_BADGE_OVERUSE",
            "ENTRANCE_STYLE_MONOTONY",
        ):
            assert req_v71_code in res_v17_full["warning_codes"], f"Missing {req_v71_code} in {res_v17_full['warning_codes']}"

        # 6. v7.1 Clean kinetic spec planned via `typography_composer.plan_dviet_kinetic_beat_schedule` -> 0 errors!
        if str(SKILL_ROOT / "scripts" / "tools") not in sys.path:
            sys.path.insert(0, str(SKILL_ROOT / "scripts" / "tools"))
        import typography_composer as _tc

        clean_plan = _tc.plan_dviet_kinetic_beat_schedule(
            [
                {"main_text": "video sản phẩm", "badge_text": "AI STUDIO", "role": "hook"},
                {"main_text": "mình là thành", "role": "quiet"},
                {"main_text": "sử dụng ai", "role": "wall", "cam_mode": "left_third"},
                {"main_text": "giả trân", "accent_text": "nhựa không thật", "is_pain": True},
                {"main_text": "3 bước", "accent_text": "khóa ảnh", "badge_text": "3 STEPS", "role": "step"},
                {"main_text": "kết cấu", "accent_text": "không biến dạng", "role": "solution"},
                {"main_text": "ánh sáng studio", "role": "quiet"},
                {"main_text": "đổ bóng", "accent_text": "chân thật", "has_arc": True},
                {"main_text": "camera", "accent_text": "điện ảnh", "swap_words": ["camera", "điện ảnh"], "role": "swap"},
            ],
            [
                ["video", 0.40, 0.72], ["sản", 0.72, 0.96], ["phẩm", 0.96, 1.28],
                ["mình", 2.10, 2.34], ["là", 2.34, 2.52], ["thành", 2.52, 2.90],
                ["sử", 3.60, 3.82], ["dụng", 3.82, 4.08], ["ai", 4.08, 4.42],
                ["giả", 5.20, 5.52], ["trân", 5.52, 5.90], ["nhựa", 6.20, 6.52], ["không", 6.52, 6.76], ["thật", 6.76, 7.10],
                ["3", 8.00, 8.24], ["bước", 8.24, 8.58], ["khóa", 8.80, 9.12], ["ảnh", 9.12, 9.48],
                ["kết", 10.20, 10.48], ["cấu", 10.48, 10.82], ["không", 11.10, 11.35], ["biến", 11.35, 11.65], ["dạng", 11.65, 12.00],
                ["ánh", 12.80, 13.08], ["sáng", 13.08, 13.42], ["studio", 13.42, 13.88],
                ["đổ", 14.60, 14.88], ["bóng", 14.88, 15.22], ["chân", 15.22, 15.52], ["thật", 15.52, 15.88],
                ["camera", 16.60, 17.08], ["điện", 17.35, 17.68], ["ảnh", 17.68, 18.08],
            ],
            cranial_zone={"hair_top_y": 862.0, "chin_y": 1365.0},
            out_dir=tdir / "clean_plates",
            fps=60,
        )
        clean_v71_spec: dict[str, Any] = {
            "name": "test_clean_v71_kinetic",
            "fps": 60,
            "width": 1080,
            "height": 1920,
            "duration": 19.0,
            "meta": {
                "cranial_zone": {"hair_top_y": 862.0, "chin_y": 1365.0},
                "strict_cranial_lock": True,
                "color_policy": "semantic_4act_jewel",
            },
            "tracks": [
                {"type": "video", "name": "V1 · A-Roll", "clips": [{"name": "A-Roll #1", "src": str(clip_mp4), "loop": True, "at": 0.0, "dur": 19.0}]},
                {"type": "video", "name": "V2 · Kinetic Typo Plates", "clips": clean_plan["craft_clips"]},
            ],
        }
        san_clean_doc, san_clean_st = sanitize_spec(clean_v71_spec, spec_dir=tdir, work_dir=tdir)
        # Ensure `typo_kinetic_meta` was cleanly stripped before `fc_build_fast.py`
        for tr_c in san_clean_doc["tracks"]:
            for cl_c in tr_c["clips"]:
                assert "typo_kinetic_meta" not in cl_c
        res_clean_kt = audit_kinetic_typography_choreography(
            san_clean_doc,
            raw_spec=clean_v71_spec,
            san_stats=san_clean_st,
            tier_used="full",
            strict_rules=True,
        )
        res_clean_cran = audit_cranial_exclusion(
            san_clean_doc,
            raw_spec=clean_v71_spec,
            spec_meta=clean_v71_spec["meta"],
            san_stats=san_clean_st,
            tier_used="full",
        )
        assert res_clean_kt["status"] == "PASS" and res_clean_kt["violation_count"] == 0, f"Expected clean v7.1 PASS, got {res_clean_kt}"
        assert res_clean_cran["status"] == "PASS" and res_clean_cran["violation_count"] == 0, f"Expected clean cranial PASS, got {res_clean_cran}"

    print(
        json.dumps(
            {
                "ok": True,
                "compiler_version": COMPILER_VERSION,
                "cranial_audit_bad": res_cran_bad["status"],
                "cranial_audit_good": res_cran_good["status"],
                "laneb_cranial_audit_bad": res_lb_cran_bad["status"],
                "cri100_veto_caught": res_cri_bad["warning_codes"],
                "cri100_clean": res_cri_good["status"],
                "v71_gate3c_bad_caught": res_v17_full["warning_codes"],
                "v71_gate3c_clean": res_clean_kt["status"],
                "micro_bridges_injected": mb_res["count"],
                "adjustment_track_index": mb_res["track_index"],
                "rendered_frame_std": round(float(arr_png.std()), 2) if arr_png is not None else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="compile_and_verify.py",
        description=(
            f"v{COMPILER_VERSION} Universal Studio Stateless FilmCraft (.craft.json -> .fcproj) Gatekeeper: "
            "Gate 3C Kinetic Typography Anti-Cookie-Cutter Vetoes, Lane-B CRANIAL_EXCLUSION_AUDIT, "
            "INDUSTRY_CRI100_VETO_AUDIT, Native AdjustmentLayer Micro-Bridges & Closed-Loop EBU R128 Verifier."
        ),
    )
    ap.add_argument("--spec", help="Path to input .craft.json spec")
    ap.add_argument("--out", help="Path to output .fcproj file")
    ap.add_argument("--work", help="Working directory for intermediate specs, stems, and QA reports")
    ap.add_argument(
        "--words",
        help="Optional timeline word timestamps JSON: a bare [[word, t0, t1], ...] list OR the probe doc "
        "words_tl.json ({\"words\": [[w, t0, t1]], \"words_tl\": [...], \"face_metrics\": {...}}); "
        "a normalised list copy is written under --work and forwarded to spec_lint / edit_rules",
    )
    ap.add_argument("--manifest", help="Optional 00_storyboard_manifest.json for editorial audit")
    ap.add_argument(
        "--tier",
        choices=("auto", "fast", "full"),
        default="auto",
        help="Execution rigor tier: `fast` (P0 Express Physics + v7.1 Audits), `full` (P0+P1+P2 Studio Proof), or `auto` (default)",
    )
    ap.add_argument(
        "--scenes",
        help="v7.9.3 optional `scenes.json` (studio_recipe): Gate 5 FACE_ROOM applies the A-roll eye/mouth bands only in modes "
        "P/B/S/A1/N and only the PiP rect in H/A2 full-screen B-roll scenes (default: context `scenes`, then spec "
        "`meta.face_windows`, else every frame)",
    )
    ap.add_argument(
        "--context",
        help="Optional `workspace_context.json` from `probe_and_align.py` (provides `subject_framing` / `face_metrics` in source px, "
        "`cranial_zone` & `recommended_compile_tier`). Without it, `workspace_context.json` in --work or next to --words (or the "
        "`face_metrics` of the --words probe doc) is auto-loaded for the cranial audit, projected through the real V1 motion; "
        "with no face data the audit emits a `no cranial data` WARN",
    )
    ap.add_argument(
        "--archetype",
        help="Optional director archetype override (e.g. `dviet_era2_7707_manifesto`, `dviet_vietanh_zdepth_master`, `minimal_intellectual`; also read from `spec.meta.archetype`)",
    )
    ap.add_argument(
        "--industry-skin",
        default=None,
        help="Optional v7.0 industry skin override (`dental_clinic`, `luxury_skincare`, `nail_hair_salon`; also read from `spec.meta.industry_skin`)",
    )
    ap.add_argument(
        "--strict-cri100",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail build if INDUSTRY_CRI100_VETO_AUDIT detects any forbidden Warm Film Burn, yellow LUT, harsh dental SFX, or enamel/macro occlusion",
    )
    ap.add_argument(
        "--color-policy",
        choices=("color_world_polarity", "semantic_4act_jewel", "multi_hue_6"),
        default=None,
        help="Chromatic policy override (`color_world_polarity` default, `semantic_4act_jewel`, or opt-in `multi_hue_6`; also read from `spec.meta.color_policy`)",
    )
    ap.add_argument(
        "--vocal-chest-warmth",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Apply +2.2 dB @ 185Hz (Q=1.15) + 75Hz HPF vocal chest warmth to voice clips (also read from `spec.meta.vocal_chest_warmth`)",
    )
    ap.add_argument(
        "--single-hero-strict",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enforce zero Hero-vs-Bottom-Caption dual-focal collision (also read from `spec.meta.single_hero_strict`)",
    )
    ap.add_argument(
        "--claim-gate",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable Epistemic Ruling R200 `claim_gate` hold notice in EDITOR-REPORT.md (also read from `spec.meta.claim_gate`)",
    )
    ap.add_argument(
        "--optimize-bgm-offset",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Scan 16kHz BGM envelope to pick lowest-LRA steady-state `in` offset (default: ON in `full`, OFF in `fast`)",
    )
    ap.add_argument(
        "--target-lufs", type=float, default=None,
        help="Target integrated loudness in LUFS (default: -16.0, or the --audio-profile target)",
    )
    ap.add_argument(
        "--profile", choices=("default", "dviet"), default="default",
        help="Style profile: `default` = historical behaviour; `dviet` scopes the Warm Film Burn / white-flash vetoes to capped wash/flash events (4-Cut Grammar stays HARD)",
    )
    audio_profiles = _load_profile_overrides()["audio_profiles"]
    pl, s14, tl = (audio_profiles[k] for k in ("platform", "studio_14", "tiktok_loud"))
    ap.add_argument(
        "--audio-profile", choices=tuple(audio_profiles), default="platform",
        help=(
            "Loudness profile (presets/profile_overrides.json): "
            f"`platform` ({pl['target_lufs']:g} LUFS, <= {pl['true_peak_dbtp']:g} dBTP, default), "
            f"`studio_14` (Look S: {s14['target_lufs']:g} LUFS, <= {s14['true_peak_dbtp']:g} dBTP, ducking ON) or "
            f"`tiktok_loud` ({tl['target_lufs']:g} LUFS, <= {tl['true_peak_dbtp']:g} dBTP, "
            f"{'no ducking' if tl.get('no_ducking') else 'ducking ON'}, BGM {tl['bgm_below_voice_db']:g} dB under voice)"
        ),
    )
    ap.add_argument("--portable-root", help="Optional bundle root dir to relativize `assets/...` & update bundle_manifest.json")
    ap.add_argument("--auto-sfx-dir", help="Optional directory to auto-resolve `src: 'AUTO:<keyword>'` SFX clips")
    ap.add_argument(
        "--c8-guard",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Trim main text clips ending 1..12 frames past a V1 cut back to cut_t - 1/fps (default: enabled; exempts `persistent_bridge` clips)",
    )
    ap.add_argument("--limiter", type=float, default=None, help="Master hard_limiter ceiling in dB (default: the --audio-profile ceiling, limiter_db_v793 when present: platform -2.2, studio_14 -1.3, tiktok_loud -1.2)")
    ap.add_argument("--strict-rules", action="store_true", help="Fail build if edit_rules.py or v7.0 Cranial/CRI-100 audits report errors")
    ap.add_argument(
        "--hook-gates", action="store_true",
        help="v7.8.0 (default OFF): run motion_gate.check_motion on --preview (frame diff over 0..3.4 s; failures become concerns)",
    )
    ap.add_argument("--preview", help="Rendered preview MP4 that --hook-gates measures")
    ap.add_argument("--hook-mask", action="append", default=[], metavar="X0,Y0,X1,Y1",
                    help="Normalised rect (0..1) ignored by --hook-gates (PiP / text box); repeatable")
    ap.add_argument("--open-app", action="store_true", help="Launch FilmCraft desktop GUI (--no-recover) on completion")
    ap.add_argument(
        "--display", default=os.environ.get("CRAFT_DISPLAY") or ":93",
        help="X11 DISPLAY for --open-app (default: $CRAFT_DISPLAY or :93, the isolated craftctl display; pass :0 to open on your desktop)",
    )
    ap.add_argument("--self-test", action="store_true", help="Run v7.0 Stateless Gatekeeper unit & FilmCraft AdjustmentLayer smoke tests")
    args = ap.parse_args()
    if args.hook_gates and not args.preview:
        ap.error("--hook-gates needs --preview <rendered preview .mp4>")
    if not args.self_test and (not args.spec or not args.out or not args.work):
        ap.error("the following arguments are required unless --self-test is passed: --spec, --out, --work")
    audio_prof = resolve_audio_profile(args.audio_profile)
    if args.target_lufs is None:
        args.target_lufs = float(audio_prof["target_lufs"])
    if args.limiter is None:
        args.limiter = profile_limiter_db(audio_prof)
    args.tp_ceiling = float(audio_prof["true_peak_dbtp"])
    args.audio_no_ducking = bool(audio_prof.get("no_ducking"))
    return args


def run_hook_gates(preview: str, mask_args: list[str] | None = None, t0: float = 0.0, t1: float = 3.4) -> dict[str, Any]:
    """v7.8.0 opt-in (`--hook-gates`): `motion_gate.check_motion` on a rendered preview. Pure measurement, never raises on a bad
    clip (the verdict is in the returned dict); a missing / unreadable preview is reported as ok=False with the reason."""
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import motion_gate  # noqa: PLC0415 (lazy: the default path never imports it)
    masks = [tuple(float(x) for x in m.split(",")) for m in (mask_args or [])]
    try:
        return motion_gate.check_motion(preview, masks, t0, t1)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "errors": [str(exc)], "mean": 0.0, "max_static_run_s": 0.0, "share_below_1": 0.0}


def main() -> int:
    args = parse_args()
    if args.self_test:
        return _run_self_tests()
    t_start_all = time.perf_counter()
    py = _py_bin()

    spec_in = Path(args.spec).resolve()
    out_fcproj = Path(args.out).resolve()
    work_dir = Path(args.work).resolve()
    words_path = Path(args.words).resolve() if args.words else None
    manifest_path = Path(args.manifest).resolve() if args.manifest else None
    context_path = Path(args.context).resolve() if args.context else None
    portable_root = Path(args.portable_root).resolve() if args.portable_root else None
    auto_sfx_dir = Path(args.auto_sfx_dir).resolve() if args.auto_sfx_dir else None

    work_dir.mkdir(parents=True, exist_ok=True)
    summary_path = work_dir / "compile_summary.json"
    compile_report_path = work_dir / "compile_report.json"
    editor_report_path = work_dir / "EDITOR-REPORT.md"

    stem = spec_in.name
    for suf in (".levels.craft.json", ".sanitized.craft.json", ".craft.json", ".json"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
            break

    timings: dict[str, float] = {}
    gates: dict[str, str] = {
        "gate1_mechanical_sanitizer": "PENDING",
        "gate2_spec_lint": "PENDING",
        "gate3_edit_rules": "PENDING",
        "gate4_fc_build_parity": "PENDING",
        "gate5_postfx_and_contact_sheet": "PENDING",
        "gate6_closed_loop_loudness": "PENDING",
        "gate7_sfx_and_portable_bundle": "PENDING",
        "gate8_epistemic_verdict_and_report": "PENDING",
    }

    diagnostics: list[dict[str, str]] = []
    concerns: list[str] = []
    failure_owner_stage: str | None = None

    def _add_diag(gate: str, severity: str, code: str, message: str, fix: str) -> None:
        diagnostics.append(
            {
                "gate": gate,
                "severity": severity,
                "code": code,
                "message": message,
                "fix": fix,
            }
        )

    summary: dict[str, Any] = {
        "ok": False,
        "compiler": "pro-filmcraft-director/scripts/tools/compile_and_verify.py",
        "version": COMPILER_VERSION,
        "tier_used": args.tier if args.tier != "auto" else "fast",
        "verdict": "REJECTED",
        "owner_stage": None,
        "editor_report": str(editor_report_path),
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_elapsed_sec": 0.0,
        "timings_sec": timings,
        "gates": gates,
        "inputs": {
            "spec": str(spec_in),
            "out": str(out_fcproj),
            "work": str(work_dir),
            "words": str(words_path) if words_path else None,
            "manifest": str(manifest_path) if manifest_path else None,
            "context": str(context_path) if context_path else None,
            "tier_requested": args.tier,
            "archetype_flag": args.archetype,
            "industry_skin_flag": args.industry_skin,
            "strict_cri100_flag": args.strict_cri100,
            "single_hero_strict_flag": args.single_hero_strict,
            "claim_gate_flag": args.claim_gate,
            "optimize_bgm_offset_flag": args.optimize_bgm_offset,
            "target_lufs": args.target_lufs,
            "tp_ceiling_dbtp": args.tp_ceiling,
            "profile": args.profile,
            "audio_profile": args.audio_profile,
            "portable_root": str(portable_root) if portable_root else None,
            "auto_sfx_dir": str(auto_sfx_dir) if auto_sfx_dir else None,
            "c8_guard": args.c8_guard,
            "limiter_db": args.limiter,
            "strict_rules": args.strict_rules,
            "open_app": args.open_app,
        },
        "outputs": {
            "editor_report": str(editor_report_path),
            "compile_report": str(compile_report_path),
            "compile_summary": str(summary_path),
        },
        "diagnostics": diagnostics,
        "concerns": concerns,
    }

    try:
        failure_owner_stage = "INTAKE"
        if not spec_in.is_file():
            raise FileNotFoundError(f"Input spec not found: {spec_in}")
        if words_path and not words_path.is_file():
            raise FileNotFoundError(f"Words file not found: {words_path}")
        if manifest_path and not manifest_path.is_file():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        if context_path and not context_path.is_file():
            raise FileNotFoundError(f"Workspace context file not found: {context_path}")
        if portable_root and not portable_root.is_dir():
            raise FileNotFoundError(f"Portable root directory not found: {portable_root}")

        context_doc = json.loads(context_path.read_text(encoding="utf-8")) if context_path else None
        if args.scenes and not Path(args.scenes).is_file():
            raise FileNotFoundError(f"Scenes file not found: {args.scenes}")
        scenes_list = load_scenes(args.scenes)
        words_src_path = words_path
        if words_path:
            words_path = normalize_words_file(words_path, work_dir)
        words_doc = json.loads(words_path.read_text(encoding="utf-8")) if words_path else None
        cranial_ctx = context_doc if context_doc is not None else auto_load_face_context(context_path, work_dir, words_src_path)
        raw_spec = json.loads(spec_in.read_text(encoding="utf-8"))
        spec_meta = raw_spec.get("meta") if isinstance(raw_spec.get("meta"), dict) else {}
        ctx_dict = context_doc if isinstance(context_doc, dict) else {}
        effective_archetype = (
            args.archetype
            or spec_meta.get("archetype")
            or raw_spec.get("archetype")
            or ctx_dict.get("archetype")
            or ctx_dict.get("selected_archetype")
        )

        tier_used, claim_gate_active = resolve_execution_tier(
            requested_tier=args.tier,
            context_doc=context_doc,
            raw_spec=raw_spec,
            strict_rules=args.strict_rules,
            claim_gate_flag=args.claim_gate,
        )
        optimize_bgm = args.optimize_bgm_offset if args.optimize_bgm_offset is not None else (tier_used == "full")

        summary["tier_used"] = tier_used
        summary["inputs"]["optimize_bgm_offset_effective"] = optimize_bgm
        summary["claim_gate"] = {
            "active": claim_gate_active,
            "ruling": "R200",
            "hold_publish_until_user_confirms": claim_gate_active,
        }
        if spec_meta:
            summary["spec_meta"] = spec_meta

        # Ruling R200: check if `meta.broll_class == 'heavy'` has unprovided `owner == 'user'` real footage
        if spec_meta.get("broll_class") == "heavy":
            missing_user_assets = [
                str(a.get("desc") or a.get("anchor_quote") or "user_asset")
                for a in (spec_meta.get("broll_assets") or [])
                if isinstance(a, dict) and a.get("owner") == "user" and not a.get("provided")
            ]
            if missing_user_assets:
                concerns.append(
                    f"R200 (broll_class=heavy): cảnh thật từ user còn thiếu ({', '.join(missing_user_assets)}) — AI chỉ minh hoạ"
                )

        sync_sidecar_metadata(spec_in, work_dir, portable_root)
        print(
            f"🎬 [Compiler v{COMPILER_VERSION}] Tier=`{tier_used}` · optimize_bgm={optimize_bgm} · "
            f"claim_gate={claim_gate_active}"
        )

        # ======================================================================
        # GATE 1: Mechanical Sanitizer + Acoustic `lag_ms` Peak-on-Cut & MD5 Dedup
        # ======================================================================
        failure_owner_stage = "PLAN"
        t0 = time.perf_counter()
        sanitized_spec, san_stats = sanitize_spec(
            raw_spec,
            spec_dir=spec_in.parent,
            work_dir=work_dir,
            portable_root=portable_root,
            auto_sfx_dir=auto_sfx_dir,
            enable_c8_guard=args.c8_guard,
            optimize_bgm_offset=optimize_bgm,
            vocal_chest_warmth=args.vocal_chest_warmth,
        )
        sanitized_path = work_dir / f"{stem}.sanitized.craft.json"
        levels_path = work_dir / f"{stem}.levels.craft.json"
        sanitized_path.write_text(json.dumps(sanitized_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        timings["gate1_preflight_sanitize"] = round(time.perf_counter() - t0, 3)
        gates["gate1_mechanical_sanitizer"] = "PASS"
        summary["sanitizer"] = san_stats
        summary["outputs"]["sanitized_spec"] = str(sanitized_path)
        print(
            f"✅ [Gate 1/8] Mechanical & Acoustic Sanitizer ({timings['gate1_preflight_sanitize']:.2f}s): "
            f"snapped={san_stats['snapped_clips']}, eof_clamped={len(san_stats['eof_clamped_clips'])}, "
            f"bgm_stops={san_stats['bgm_stops_carved_count']}, lag_ms_aligned={san_stats['lag_ms_aligned_count']}, "
            f"micro_fades={san_stats['speech_micro_fades_count']}, md5_dedup={san_stats['md5_dedup_skipped']}, "
            f"auto_sfx={len(san_stats['auto_allocated_sfx'])}, bgm_opt={len(san_stats['bgm_offset_optimizations'])}"
        )

        # ======================================================================
        # STEP 2A: Audio Plan + Intelligent Initial Pre-Trim
        # ======================================================================
        failure_owner_stage = "BUILD"
        t0 = time.perf_counter()
        effective_rules = build_effective_rules(work_dir, args.target_lufs, args.audio_profile)
        audio_roles = present_audio_roles(sanitized_path)
        if audio_roles:
            r_plan = subprocess.run(
                [
                    py,
                    str(AUDIO_LEVELS_PY),
                    "plan",
                    str(sanitized_path),
                    "-o",
                    str(levels_path),
                    "--rules",
                    str(effective_rules),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace",
            )
            if r_plan.returncode != 0:
                raise RuntimeError(f"audio_levels.py plan failed:\n{r_plan.stderr or r_plan.stdout}")
            lufs_target_shift = _lufs_target_shift(args.audio_profile, args.target_lufs)
            init_vb_trim = round(-0.72 + lufs_target_shift, 2)
            init_sfx_trim = round(-0.50 + min(0.50, lufs_target_shift * 0.5), 2)
            # v7.9.3: the voice share is clamped to the voice_peak window (BGM keeps the full LUFS shift)
            init_voice_trim = voice_pretrim_db(effective_rules, init_vb_trim)
            adjust_spec_audio_gains(levels_path, init_voice_trim, init_sfx_trim, delta_bgm_db=init_vb_trim)
        else:
            # Strip any leftover `tier` keys on audio clips if no audio_levels plan ran
            clean_doc = json.loads(sanitized_path.read_text(encoding="utf-8"))
            for tr in clean_doc.get("tracks", []):
                if tr.get("type") == "audio":
                    for cl in tr.get("clips", []):
                        cl.pop("tier", None)
            levels_path.write_text(json.dumps(clean_doc, ensure_ascii=False, indent=2), encoding="utf-8")
            init_vb_trim, init_sfx_trim = 0.0, 0.0
            init_voice_trim = 0.0

        timings["audio_plan_and_pretrim"] = round(time.perf_counter() - t0, 3)
        summary["outputs"]["levels_spec"] = str(levels_path)
        levels_spec_doc = json.loads(levels_path.read_text(encoding="utf-8"))

        # ======================================================================
        # GATE 2: Pre-Build Spec Lint (`spec_lint.py` -> 0 HARD errors)
        # ======================================================================
        failure_owner_stage = "PLAN"
        t0 = time.perf_counter()
        lint_cmd = [py, str(SPEC_LINT_PY), str(levels_path), "--json"]
        if words_path:
            lint_cmd += ["--words", str(words_path)]
        r_lint = subprocess.run(lint_cmd, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace")
        if not r_lint.stdout.strip():
            raise RuntimeError(f"spec_lint.py failed to produce output:\n{r_lint.stderr}")
        lint_items = json.loads(r_lint.stdout)
        for item in lint_items:
            if item["status"] in ("HARD", "SOFT"):
                fix_action = build_lint_fix_diagnostic(item, levels_spec_doc)
                item["actionable_fix"] = fix_action
                _add_diag(
                    "gate2_spec_lint",
                    "ERROR" if item["status"] == "HARD" else "WARN",
                    item["id"],
                    f"{item['id']}={item['value']} (target: {item.get('target')})",
                    fix_action,
                )
                print(f"   [LINT {item['status']:<4}] {item['id']:<26} {item['value']} — Fix: {fix_action}")
            else:
                print(f"   [LINT {item['status']:<4}] {item['id']:<26} {item['value']}")

        hard_items = [x for x in lint_items if x["status"] == "HARD"]
        soft_items = [x for x in lint_items if x["status"] == "SOFT"]
        ok_items = [x for x in lint_items if x["status"] == "OK"]
        for s_it in soft_items:
            concerns.append(f"Spec Lint SOFT `{s_it['id']}`: {s_it['value']} — Fix: {s_it.get('actionable_fix', s_it.get('fix', ''))}")

        timings["gate2_spec_lint"] = round(time.perf_counter() - t0, 3)
        summary["lint"] = {
            "hard_count": len(hard_items),
            "soft_count": len(soft_items),
            "ok_count": len(ok_items),
            "hard_items": hard_items,
            "soft_items": soft_items,
        }
        if hard_items:
            gates["gate2_spec_lint"] = "FAIL"
            if any(h["id"] in ("media_missing", "text_voice_burst") for h in hard_items):
                failure_owner_stage = "INTAKE"
            first_h = hard_items[0]
            raise RuntimeError(
                f"Gate 2 (spec_lint) failed with {len(hard_items)} HARD error(s): "
                f"{first_h['id']}={first_h['value']} — Fix: {first_h.get('actionable_fix', first_h.get('fix', ''))}"
            )
        gates["gate2_spec_lint"] = "PASS" if not soft_items else f"PASS ({len(soft_items)} SOFT)"
        print(
            f"✅ [Gate 2/8] Spec Lint ({timings['gate2_spec_lint']:.2f}s): "
            f"0 HARD · {len(soft_items)} SOFT · {len(ok_items)} OK"
        )

        # ======================================================================
        # GATE 3: Editorial Rules Audit (`edit_rules.py` + `v6.0` 4-Cut & Bimodal C7 Adjudicator)
        # ======================================================================
        failure_owner_stage = "PLAN"
        t0 = time.perf_counter()
        if words_path or manifest_path or args.strict_rules:
            rules_base = [py, str(EDIT_RULES_PY), "audit", str(levels_path)]
            if args.profile == "dviet":
                rules_base += ["--profile", "dviet"]
            if args.profile == "dviet" or spec_has_rendered_plates(levels_spec_doc):
                rules_base += ["--lane-b-plates"]
            if words_path:
                rules_base += ["--words", str(words_path)]
            if manifest_path:
                rules_base += ["--manifest", str(manifest_path)]

            try:
                rules_items = run_edit_rules_json([*rules_base, "--json"])
            except RuntimeError as exc:
                gates["gate3_edit_rules"] = f"FAIL ({exc})"
                raise RuntimeError(f"Gate 3 failed: {exc}") from exc
            v60_adj_res = adjudicate_v60_cut_grammar_and_c7(
                levels_spec_doc,
                words=words_doc,
                rules_items=rules_items,
                archetype=str(effective_archetype) if effective_archetype else None,
                spec_meta=spec_meta,
            )
            for r_it in rules_items:
                st_r = r_it.get("status", "OK")
                if st_r in ("LỖI", "CẢNH BÁO"):
                    fix_r = build_edit_rule_fix_diagnostic(r_it, levels_spec_doc)
                    r_it["actionable_fix"] = fix_r
                    _add_diag(
                        "gate3_edit_rules",
                        "ERROR" if st_r == "LỖI" else "WARN",
                        r_it.get("rule", "edit_rule"),
                        str(r_it.get("detail", "")),
                        fix_r,
                    )
                    concerns.append(f"Edit Rules {st_r} `{r_it.get('rule')}`: {r_it.get('detail')} — Fix: {fix_r}")
                    print(f"   [{st_r:<9}] {r_it['rule']:<56} {r_it['detail']} — Fix: {fix_r}")
                else:
                    print(f"   [{st_r:<9}] {r_it['rule']:<56} {r_it['detail']}")

            err_cnt = sum(1 for r in rules_items if r.get("status") == "LỖI")
            warn_cnt = sum(1 for r in rules_items if r.get("status") == "CẢNH BÁO")
            unchk_cnt = sum(1 for r in rules_items if r.get("status") == "CHƯA KIỂM")
            timings["gate3_edit_rules"] = round(time.perf_counter() - t0, 3)
            summary["edit_rules"] = {
                "executed": True,
                "errors": err_cnt,
                "warnings": warn_cnt,
                "unchecked": unchk_cnt,
                "v60_adjudicator": v60_adj_res,
                "items": rules_items,
            }
            if args.strict_rules and err_cnt > 0:
                gates["gate3_edit_rules"] = "FAIL"
                first_err = next(r for r in rules_items if r.get("status") == "LỖI")
                raise RuntimeError(
                    f"Gate 3 (edit_rules --strict-rules) failed with {err_cnt} LỖI: "
                    f"{first_err.get('rule')} — Fix: {first_err.get('actionable_fix', '')}"
                )
            gates["gate3_edit_rules"] = "PASS" if err_cnt == 0 else f"WARN ({err_cnt} LỖI)"
            print(
                f"✅ [Gate 3/8] Edit Rules + v6.0 Adjudicator ({timings['gate3_edit_rules']:.2f}s): "
                f"{err_cnt} LỖI · {warn_cnt} CẢNH BÁO · {unchk_cnt} CHƯA KIỂM "
                f"(adjudicated={len(v60_adj_res['adjudicated_rules'])})"
            )
        else:
            timings["gate3_edit_rules"] = 0.0
            gates["gate3_edit_rules"] = "SKIPPED"
            summary["edit_rules"] = {"executed": False, "reason": "neither --words nor --manifest provided"}
            print("ℹ️  [Gate 3/8] Edit Rules Audit skipped (no --words or --manifest provided)")

        # Gate 3B (`v6.0`): Color-World Polarity, 4-Cut/J-Cut Continuity & Spatial Density (`MAX_ZONES=2`)
        t_v60 = time.perf_counter()
        if args.single_hero_strict is not None:
            effective_single_hero_strict = bool(args.single_hero_strict)
        elif "single_hero_strict" in spec_meta:
            effective_single_hero_strict = bool(spec_meta.get("single_hero_strict"))
        elif "single_hero_strict" in raw_spec:
            effective_single_hero_strict = bool(raw_spec.get("single_hero_strict"))
        elif "single_hero_strict" in ctx_dict:
            effective_single_hero_strict = bool(ctx_dict.get("single_hero_strict"))
        else:
            effective_single_hero_strict = False

        chrom_res = audit_chromatic_diversity(
            levels_spec_doc,
            archetype=str(effective_archetype) if effective_archetype else None,
            tier_used=tier_used,
            color_policy=args.color_policy,
            spec_meta=spec_meta,
        )
        trans_res = audit_transition_and_rhythm_continuity(
            levels_spec_doc,
            archetype=str(effective_archetype) if effective_archetype else None,
            san_stats=san_stats,
            tier_used=tier_used,
            words=words_doc,
            spec_meta=spec_meta,
        )
        sec_grp_res = audit_secondary_text_groups(
            levels_spec_doc,
            single_hero_strict=effective_single_hero_strict,
            tier_used=tier_used,
            archetype=str(effective_archetype) if effective_archetype else None,
            spec_meta=spec_meta,
        )
        cran_res = audit_cranial_exclusion(
            levels_spec_doc,
            raw_spec=raw_spec,
            context_doc=cranial_ctx,
            spec_meta=spec_meta,
            san_stats=san_stats,
            tier_used=tier_used,
        )
        cri100_res = audit_industry_cri100_veto(
            levels_spec_doc,
            raw_spec=raw_spec,
            context_doc=context_doc,
            spec_meta=spec_meta,
            san_stats=san_stats,
            industry_skin_override=args.industry_skin,
            strict_cri100=bool(args.strict_cri100),
            profile=args.profile,
        )
        dviet_caps_res = (
            audit_dviet_wash_flash_caps(levels_spec_doc) if args.profile == "dviet"
            else {"executed": False, "profile": args.profile, "warnings": []}
        )
        kinetic_typo_res = audit_kinetic_typography_choreography(
            levels_spec_doc,
            raw_spec=raw_spec,
            spec_meta=spec_meta,
            san_stats=san_stats,
            tier_used=tier_used,
            strict_rules=bool(args.strict_rules),
            spec_dir=spec_in.parent,
        )

        timings["gate3_v70_aesthetic_and_cri100_audits"] = round(time.perf_counter() - t_v60, 3)
        timings["gate3_v60_aesthetic_audits"] = timings["gate3_v70_aesthetic_and_cri100_audits"]
        timings["gate3_v52_aesthetic_audits"] = timings["gate3_v70_aesthetic_and_cri100_audits"]
        summary["chromatic_diversity"] = chrom_res
        summary["transition_continuity"] = trans_res
        summary["secondary_text_groups"] = sec_grp_res
        summary["cranial_exclusion_audit"] = cran_res
        summary["industry_cri100_veto"] = cri100_res
        summary["dviet_wash_flash_caps"] = dviet_caps_res
        summary["kinetic_typography_audit"] = kinetic_typo_res

        v60_warn_count = 0
        for audit_name, audit_res in (
            ("gate3_chromatic_diversity", chrom_res),
            ("gate3_transition_continuity", trans_res),
            ("gate3_secondary_text_groups", sec_grp_res),
            ("gate3_cranial_exclusion", cran_res),
            ("gate3_industry_cri100_veto", cri100_res),
            ("gate3_dviet_wash_flash", dviet_caps_res),
            ("gate3c_kinetic_typography", kinetic_typo_res),
        ):
            for w_item in audit_res.get("warnings") or []:
                v60_warn_count += 1
                w_code = str(w_item.get("code", "V70_WARN"))
                w_sev = str(w_item.get("severity", "WARN"))
                w_msg = str(w_item.get("message", ""))
                w_fix = str(w_item.get("fix", ""))
                _add_diag(audit_name, w_sev, w_code, w_msg, w_fix)
                if (tier_used == "full" and w_item.get("elevate_concern_in_full")) or w_code in (
                    "HERO_BOTTOM_CAPTION_COLLISION",
                    "CARD_TEXT_COLLISION",
                    "FRAME_CLUTTER_OVERLOAD",
                    "RAINBOW_HUE_SOUP",
                    "CRANIAL_EXCLUSION_VIOLATION",
                    "CRI100_FORBIDDEN_WARM_FILM_BURN",
                    "CRI100_FORBIDDEN_YELLOW_WARM_LUT",
                    "DENTAL_FORBIDDEN_HARSH_SFX",
                    "ENAMEL_GUM_TEXT_OCCLUSION",
                    "MACRO_SUBJECT_TEXT_OCCLUSION",
                    "STATIC_HERO_PNG_STAMP",
                    "LAYOUT_SILHOUETTE_MONOTONY",
                    "PILL_BADGE_OVERUSE",
                    "ENTRANCE_STYLE_MONOTONY",
                ):
                    concerns.append(f"{w_msg} — Fix: {w_fix}")
                print(f"   ⚠️  [v7.1 {w_code}] {w_msg} — Fix: {w_fix}")

        if kinetic_typo_res.get("status") == "FAIL":
            gates["gate3_edit_rules"] = "FAIL"
            first_kv = (kinetic_typo_res.get("violations") or [{}])[0]
            raise RuntimeError(
                f"Gate 3C KINETIC_TYPOGRAPHY_CHOREOGRAPHY_AUDIT failed ({kinetic_typo_res.get('violation_count')} veto(es)): "
                f"{first_kv.get('code', 'V71_KINETIC_VETO')} — {first_kv.get('message', '')} — Fix: {first_kv.get('fix', '')}"
            )
        if cran_res.get("status") == "FAIL" or (args.strict_rules and int(cran_res.get("violation_count", 0)) > 0):
            gates["gate3_edit_rules"] = "FAIL"
            first_cv = (cran_res.get("violations") or [{}])[0]
            raise RuntimeError(
                f"Gate 3B CRANIAL_EXCLUSION_AUDIT failed ({cran_res.get('violation_count')} violation(s)): "
                f"'{first_cv.get('clip', '?')}' at {first_cv.get('at', 0.0)}s — Fix: {first_cv.get('fix', '')}"
            )
        if cri100_res.get("status") == "FAIL" or (args.strict_rules and int(cri100_res.get("veto_count", 0)) > 0):
            gates["gate3_edit_rules"] = "FAIL"
            first_iv = (cri100_res.get("violations") or [{}])[0]
            raise RuntimeError(
                f"Gate 3B INDUSTRY_CRI100_VETO_AUDIT failed ({cri100_res.get('veto_count')} veto(es)): "
                f"{first_iv.get('code', 'CRI100_VETO')} — Fix: {first_iv.get('fix', '')}"
            )

        if v60_warn_count > 0 and gates["gate3_edit_rules"] == "PASS":
            gates["gate3_edit_rules"] = f"PASS ({v60_warn_count} v7.1 WARN)"

        print(
            f"🎨 [Gate 3B/3C v7.1 Audits] ({timings['gate3_v70_aesthetic_and_cri100_audits']:.3f}s): "
            f"kinetic_typo={kinetic_typo_res['status']} (beats={kinetic_typo_res['typo_beats_audited']}, sil={kinetic_typo_res['distinct_silhouettes']}, pills={kinetic_typo_res['pill_badge_count']}), "
            f"cranial={cran_res['status']} (violations={cran_res['violation_count']}, lane_b={cran_res.get('foreground_lane_b_plates_audited', 0)}), "
            f"cri100={cri100_res['status']} (skin={cri100_res.get('industry_skin') or 'general'}, vetoes={cri100_res['veto_count']}), "
            f"policy={chrom_res['color_policy']} hues={chrom_res['distinct_accent_hues']} "
            f"polarity={chrom_res['polarity_light_clips_or_frames']} ({chrom_res['status']}), "
            f"hard_cuts={trans_res['clean_hard_cut_pct']:.1f}% jcuts={trans_res['true_vocal_jcut_count']} "
            f"bgm_stops={trans_res['bgm_silence_stops_count']}, "
            f"max_zones={sec_grp_res['max_concurrent_overlay_zones']} "
            f"breathing={sec_grp_res['clean_breathing_frame_pct']:.1f}% ({sec_grp_res['status']})"
        )

        # ======================================================================
        # GATES 4, 5 & 6: FilmCraft Build + Post-FX/Visual Rigor + Closed-Loop Loudness/R35
        # ======================================================================
        failure_owner_stage = "BUILD"
        build_fcproj = work_dir / f"{stem}.compiled.fcproj"
        build_report_path = work_dir / "fc_build_report.json"
        qa_frames_dir = work_dir / "qa_frames"
        mix_wav_path = work_dir / "mix.wav"
        stems_dir = work_dir / "stems"

        planned_16 = plan_16_qa_frames(sanitized_spec)
        qa_time_strs = [f"{t:.2f}" for t, _ in planned_16]
        fps_str = f"{float(sanitized_spec.get('fps', 30.0)):g}"
        use_bgm_chain = spec_bgm_has_eq_chain(levels_path)

        timings["gate4_fc_build_fast"] = 0.0
        timings["gate5_fc_fast_qa_and_frames"] = 0.0
        timings["gate6_closed_loop_loudness"] = 0.0

        effective_limiter_db = float(args.limiter)
        closed_loop_delta = 0.0
        attempts_used = 0
        ebur_metrics = {"lufs": -math.inf, "lra": 0.0, "true_peak_dbtp": -math.inf}
        post_aac_tp_dbtp: float | None = None
        stems_check_res: list[dict[str, Any]] = []
        build_report: dict[str, Any] = {}

        if qa_frames_dir.exists():
            shutil.rmtree(qa_frames_dir)
        qa_frames_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(2):
            attempts_used = attempt + 1
            if mix_wav_path.exists():
                mix_wav_path.unlink()

            if attempt == 0:
                # Gate 4: Full FilmCraft build & parity check on pass 1
                t_b = time.perf_counter()
                r_build = subprocess.run(
                    [
                        py,
                        str(FC_BUILD_FAST_PY),
                        str(levels_path),
                        str(build_fcproj),
                        "--report",
                        str(build_report_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace",
                )
                timings["gate4_fc_build_fast"] = round(timings["gate4_fc_build_fast"] + (time.perf_counter() - t_b), 3)
                if r_build.returncode != 0 or not build_report_path.is_file():
                    gates["gate4_fc_build_parity"] = "FAIL"
                    raise RuntimeError(
                        f"Gate 4 (fc_build_fast) failed (exit={r_build.returncode}):\n"
                        f"{(r_build.stderr or r_build.stdout).strip()}"
                    )
                build_report = json.loads(build_report_path.read_text(encoding="utf-8"))
                if not build_report.get("ok") or build_report.get("mismatches"):
                    gates["gate4_fc_build_parity"] = "FAIL"
                    raise RuntimeError(f"Gate 4 parity mismatch: {build_report.get('mismatches')}")

                # v7.0 Native AdjustmentLayer Synthesis (`exposure_bloom_landing_3f` & `rack_focus_bridge_13f`)
                t_mb = time.perf_counter()
                mb_inject_res = inject_micro_bridge_adjustment_layers_fcproj(
                    build_fcproj,
                    san_stats.get("micro_bridges_planned") or [],
                    fps=float(sanitized_spec.get("fps", 30.0)),
                )
                timings["gate4_v70_micro_bridges"] = round(time.perf_counter() - t_mb, 3)
                summary["micro_bridges"] = mb_inject_res

                gates["gate4_fc_build_parity"] = "PASS"
                mb_note = (
                    f", adj_micro_bridges={mb_inject_res['count']} on '{mb_inject_res.get('track_name')}'"
                    if mb_inject_res.get("injected")
                    else ""
                )
                print(
                    f"✅ [Gate 4/8] FilmCraft Compile Parity: "
                    f"clips={build_report['actual'].get('clips')}, keyframes={build_report['actual'].get('keyframes')}, "
                    f"mismatches={{}}{mb_note}"
                )

            # Gate 5: Single-Session Post-FX + QA Frames (pass 1) + mix.wav export
            t_q = time.perf_counter()
            qa_cmd = [
                py,
                str(FC_FAST_QA_PY),
                str(build_fcproj),
                "--wav",
                str(mix_wav_path),
                "--fps",
                fps_str,
                "--limiter",
                f"{effective_limiter_db:g}",
            ]
            if attempt == 0:
                qa_cmd += ["--frames-dir", str(qa_frames_dir), "--times", *qa_time_strs]

            r_qa = subprocess.run(qa_cmd, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace")
            timings["gate5_fc_fast_qa_and_frames"] = round(
                timings["gate5_fc_fast_qa_and_frames"] + (time.perf_counter() - t_q), 3
            )
            if r_qa.stdout.strip():
                print(r_qa.stdout.rstrip())

            exported_pngs = sorted(qa_frames_dir.glob("*.png"))
            if len(exported_pngs) < len(qa_time_strs) or not mix_wav_path.is_file():
                gates["gate5_postfx_and_contact_sheet"] = "FAIL"
                raise RuntimeError(
                    f"Gate 5 (fc_fast_qa) failed to export frames/WAV "
                    f"(frames={len(exported_pngs)}/{len(qa_time_strs)}, wav={mix_wav_path.is_file()}):\n"
                    f"{(r_qa.stderr or r_qa.stdout).strip()}"
                )

            # Gate 6: Closed-Loop Loudness + Optional Ruling R35 Post-AAC True Peak Check
            t_l = time.perf_counter()
            ebur_metrics = measure_ebur128(mix_wav_path)
            if tier_used == "full" and audio_roles:
                post_aac_tp_dbtp = measure_post_aac_true_peak_dbtp(mix_wav_path)

            if audio_roles:
                stems_dir.mkdir(parents=True, exist_ok=True)
                stems_cmd = [
                    py,
                    str(AUDIO_LEVELS_PY),
                    "stems",
                    str(levels_path),
                    str(stems_dir),
                    "--rules",
                    str(effective_rules),
                ]
                if use_bgm_chain:
                    stems_cmd.append("--bgm-chain")
                r_stems = subprocess.run(stems_cmd, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace")
                if r_stems.returncode != 0:
                    raise RuntimeError(f"audio_levels.py stems failed:\n{r_stems.stderr or r_stems.stdout}")

                chk_cmd = [
                    py,
                    str(AUDIO_LEVELS_PY),
                    "check",
                    str(mix_wav_path),
                    "--allow-skip",
                    "--rules",
                    str(effective_rules),
                ]
                for role_name in ("voice", "bgm", "sfx"):
                    if role_name in audio_roles and (stems_dir / f"{role_name}.wav").is_file():
                        chk_cmd += [f"--{role_name}", str(stems_dir / f"{role_name}.wav")]

                r_chk = subprocess.run(chk_cmd, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace")
                m_json = re.search(r"(\[\s*\{.*\}\s*\])\s*$", r_chk.stdout, re.S)
                if m_json:
                    stems_check_res = json.loads(m_json.group(1))
                for line in r_chk.stdout.splitlines():
                    if line.startswith("[") and len(line.strip()) > 2:
                        print(f"   {line}")

            timings["gate6_closed_loop_loudness"] = round(
                timings["gate6_closed_loop_loudness"] + (time.perf_counter() - t_l), 3
            )

            lufs_dev = abs(ebur_metrics["lufs"] - float(args.target_lufs)) if math.isfinite(ebur_metrics["lufs"]) else 0.0
            need_lufs_retrim = bool(audio_roles and math.isfinite(ebur_metrics["lufs"]) and lufs_dev > 0.45)
            need_r35_limiter_step = bool(
                tier_used == "full"
                and post_aac_tp_dbtp is not None
                and math.isfinite(post_aac_tp_dbtp)
                and post_aac_tp_dbtp > args.tp_ceiling + 1e-6
            )
            need_pcm_tp_step = bool(audio_roles and ebur_metrics["true_peak_dbtp"] > args.tp_ceiling + 1e-6)
            # v7.9.3: LUFS on target but the voice stem peak FAILs -> retrim the voice (+ BGM, gap kept) inside +/- 0.45 LU
            voice_peak_delta = (
                voice_peak_retrim_delta(stems_check_res, effective_rules, ebur_metrics["lufs"], float(args.target_lufs))
                if audio_roles and not need_lufs_retrim else 0.0
            )
            need_voice_peak_retrim = abs(voice_peak_delta) >= 0.01

            if attempt == 0 and (need_lufs_retrim or need_r35_limiter_step or need_pcm_tp_step or need_voice_peak_retrim):
                vb_delta = 0.0
                voice_delta = 0.0
                bgm_delta = 0.0
                sfx_delta = 0.0
                if need_lufs_retrim:
                    vb_delta = round(float(args.target_lufs) - ebur_metrics["lufs"], 2)
                    # Keep voice_peak strictly inside the rules' window (default [-4.92, -3.08] dBFS) after initial_pretrim
                    vd_lo, vd_hi = voice_delta_window(effective_rules, init_voice_trim)
                    voice_delta = round(max(vd_lo, min(vd_hi, vb_delta)), 2)
                    bgm_delta = round(vb_delta + (vb_delta - voice_delta) * 1.25, 2)
                    sfx_delta = round(max(-3.0, min(0.45, vb_delta * 0.65)), 2)
                    closed_loop_delta = vb_delta
                    adjust_spec_audio_gains(levels_path, voice_delta, sfx_delta, delta_bgm_db=bgm_delta)
                    patch_fcproj_audio_gains(build_fcproj, voice_delta, sfx_delta, delta_bgm_db=bgm_delta)
                elif need_voice_peak_retrim:
                    voice_delta = bgm_delta = voice_peak_delta
                    adjust_spec_audio_gains(levels_path, voice_delta, 0.0, delta_bgm_db=bgm_delta)
                    patch_fcproj_audio_gains(build_fcproj, voice_delta, 0.0, delta_bgm_db=bgm_delta)
                    print(f"🔁 [Voice-Peak Re-Trim] voice_peak FAIL with I={ebur_metrics['lufs']:.2f} LUFS on target -> voice/BGM {voice_delta:+.2f} dB")
                if need_r35_limiter_step and post_aac_tp_dbtp is not None:
                    step_down = max(0.15, round(post_aac_tp_dbtp - (args.tp_ceiling - 0.1), 2))
                    effective_limiter_db = round(effective_limiter_db - step_down, 2)
                elif need_pcm_tp_step:
                    step_down = max(0.20, round(ebur_metrics["true_peak_dbtp"] - (args.tp_ceiling - 0.15), 2))
                    effective_limiter_db = round(effective_limiter_db - step_down, 2)

                print(
                    f"🔁 [Closed-Loop Fast Audio Re-Trim] I={ebur_metrics['lufs']:.2f} LUFS, "
                    f"PCM_TP={ebur_metrics['true_peak_dbtp']:.2f} dBTP, AAC_TP={post_aac_tp_dbtp} dBTP -> "
                    f"gain_delta={vb_delta:+.2f} dB (sfx {sfx_delta:+.2f} dB), limiter={effective_limiter_db:.2f} dB!"
                )
                continue
            break

        # Build 4x4 labeled contact sheet (1440x2560)
        t_cs = time.perf_counter()
        contact_sheet_path = build_4x4_contact_sheet(
            qa_frames_dir=qa_frames_dir,
            planned_frames=planned_16,
            out_jpg=work_dir / "qa_contact_sheet.jpg",
        )
        timings["contact_sheet_render"] = round(time.perf_counter() - t_cs, 3)

        # Package 2 (`full` mode): Deep Visual Rigor (Blank Render, Frozen B-Roll, `facesafe` Ink Audit)
        levels_spec_doc = json.loads(levels_path.read_text(encoding="utf-8"))
        if tier_used == "full":
            t_vr = time.perf_counter()
            vis_rigor = run_full_visual_rigor_gate5(
                spec=levels_spec_doc,
                qa_frames_dir=qa_frames_dir,
                planned_16=planned_16,
                context_doc=context_doc,
                scenes=scenes_list,
            )
            timings["gate5_full_visual_rigor"] = round(time.perf_counter() - t_vr, 3)
            summary["visual_rigor"] = vis_rigor

            if vis_rigor["blank_frames"]:
                gates["gate5_postfx_and_contact_sheet"] = "FAIL"
                bf = vis_rigor["blank_frames"][0]
                fix_bf = f"inspect corrupt/black V1 source or GPU effect at {bf['time_s']:.2f}s ({bf['png']}, std={bf['grayscale_std']})"
                _add_diag("gate5_visual_rigor", "ERROR", "BLANK_RENDER", f"Blank QA frame {bf['png']} (std={bf['grayscale_std']} < 10.0)", fix_bf)
                raise RuntimeError(f"Gate 5 BLANK_RENDER at {bf['time_s']:.2f}s ({bf['png']}, grayscale_std={bf['grayscale_std']}) — Fix: {fix_bf}")

            for fb_item in vis_rigor["frozen_broll"]:
                fix_fb = (
                    f"replace static video clip '{fb_item['name']}' (at={fb_item['at']:.2f}s, src={Path(fb_item['src']).name}) "
                    f"with moving B-roll video or add `\"still_plate\": true` + Ken Burns `motion.scale`"
                )
                msg_fb = f"FROZEN_BROLL: '{fb_item['name']}' at {fb_item['at']:.2f}s has mean(|f2-f1|)={fb_item['mean_abs_diff']} < 0.8"
                _add_diag("gate5_visual_rigor", "WARN", "FROZEN_BROLL", msg_fb, fix_fb)
                concerns.append(f"{msg_fb} — Fix: {fix_fb}")
                print(f"   ⚠️  [Gate 5 FROZEN_BROLL] {msg_fb} — Fix: {fix_fb}")

            for sz_item in vis_rigor["safe_zone_warnings"]:
                msg_sz = f"SAFE_ZONE: '{sz_item['clip']}' (at={sz_item['at']:.2f}s) ink [{sz_item['violation']}] outside [50..1030, 140..1760]"
                _add_diag("gate5_visual_rigor", "WARN", "SAFE_ZONE", msg_sz, sz_item["fix"])
                concerns.append(f"{msg_sz} — Fix: {sz_item['fix']}")
                print(f"   ⚠️  [Gate 5 SAFE_ZONE] {msg_sz} — Fix: {sz_item['fix']}")

            for fr_item in vis_rigor["face_room_warnings"]:
                msg_fr = f"FACE_ROOM: '{fr_item['clip']}' (at={fr_item['at']:.2f}s) overlaps {fr_item['band']} by {fr_item['overlap_px']}px"
                _add_diag("gate5_visual_rigor", "WARN", "FACE_ROOM", msg_fr, fr_item["fix"])
                concerns.append(f"{msg_fr} — Fix: {fr_item['fix']}")
                print(f"   ⚠️  [Gate 5 FACE_ROOM] {msg_fr} — Fix: {fr_item['fix']}")

            for px_item in vis_rigor["plate_text_proxies"]:
                msg_px = (f"PLATE_TEXT_PROXY: '{px_item['clip']}' (at={px_item['at']:.2f}s) is a text proxy of V2 plate "
                          f"{Path(px_item['plate']).name} (audited with the plate's alpha ink)")
                fix_px = f"put {Path(px_item['plate']).name} back on V2 so the .fcproj shows the same plate as the master"
                _add_diag("gate5_visual_rigor", "WARN", "PLATE_TEXT_PROXY", msg_px, fix_px)
                concerns.append(f"{msg_px} — Fix: {fix_px}")
                print(f"   ⚠️  [Gate 5 PLATE_TEXT_PROXY] {msg_px} — Fix: {fix_px}")

            print(
                f"👁️  [Gate 5 Deep Pixel Rigor] ({timings['gate5_full_visual_rigor']:.2f}s): "
                f"min_std={vis_rigor['min_grayscale_std']:.1f}, broll_checked={vis_rigor['broll_clips_checked']} "
                f"(frozen={len(vis_rigor['frozen_broll'])}), faces={vis_rigor['aroll_qa_faces_detected']}/{vis_rigor['aroll_qa_frames_total']}, "
                f"text_ink={vis_rigor['text_clips_audited']}, plate_ink={vis_rigor['plate_clips_audited']}, "
                f"face_scope={vis_rigor['face_scope']} (face_warns={len(vis_rigor['face_room_warnings'])}, safe_warns={len(vis_rigor['safe_zone_warnings'])})"
            )
        else:
            summary["visual_rigor"] = {"executed": False, "reason": "tier=fast"}

        gates["gate5_postfx_and_contact_sheet"] = "PASS"

        # Validate final loudness, stems_check diagnostics & True Peak
        for sc_item in stems_check_res:
            if sc_item.get("status") == "FAIL":
                sid = str(sc_item.get("id", "audio_check"))
                sval = sc_item.get("value")
                srule = sc_item.get("rule")
                if sid == "bgm_below_voice":
                    fix_sc = f"shift BGM clip `gain_db` to keep BGM within {srule} (measured {sval} LU)"
                elif sid == "speech_floor" and args.audio_no_ducking:
                    fix_sc = f"lower the static BGM `gain_db` (profile `{args.audio_profile}` forbids ducking; measured floor {sval} LU < {srule})"
                elif sid == "speech_floor":
                    fix_sc = f"duck BGM `gain_db` by -3.0 dB during speech windows (measured floor {sval} LU < {srule})"
                else:
                    fix_sc = f"adjust `{sid}` gain_db/limiter so {sval} satisfies {srule}"
                _add_diag("gate6_audio_mastering", "WARN", sid, f"{sid}={sval} ({srule})", fix_sc)
                concerns.append(f"Audio stem check `{sid}`: {sval} vs {srule} — Fix: {fix_sc}")
                print(f"   ⚠️  [Gate 6 Audio Stem] {sid}={sval} ({srule}) — Fix: {fix_sc}")

        tp_ok = ebur_metrics["true_peak_dbtp"] <= args.tp_ceiling + 1e-6
        aac_tp_ok = (post_aac_tp_dbtp is None) or (post_aac_tp_dbtp <= args.tp_ceiling + 1e-6)
        lufs_final_dev = abs(ebur_metrics["lufs"] - float(args.target_lufs)) if math.isfinite(ebur_metrics["lufs"]) else 0.0
        lufs_ok = (not audio_roles) or (lufs_final_dev <= 0.55 and tp_ok)
        if not lufs_ok:
            gates["gate6_closed_loop_loudness"] = "FAIL"
            fix_loud = (
                f"shift audio track `gain_db` by {float(args.target_lufs) - ebur_metrics['lufs']:+.2f} dB "
                f"and set `--limiter {min(effective_limiter_db, args.tp_ceiling - 1.0):.2f}`"
            )
            _add_diag("gate6_audio_mastering", "ERROR", "master_loudness", f"I={ebur_metrics['lufs']} LUFS, TP={ebur_metrics['true_peak_dbtp']} dBTP", fix_loud)
            raise RuntimeError(
                f"Gate 6 loudness check failed after {attempts_used} pass(es): "
                f"measured={ebur_metrics['lufs']} LUFS (target={args.target_lufs}), "
                f"TP={ebur_metrics['true_peak_dbtp']} dBTP (limit <= {args.tp_ceiling:g} dBTP) — Fix: {fix_loud}"
            )
        if not aac_tp_ok and post_aac_tp_dbtp is not None:
            fix_aac = f"lower `--limiter` ceiling to {round(effective_limiter_db - (post_aac_tp_dbtp - (args.tp_ceiling - 0.1)), 2):.2f} dB (R35 post-AAC TP={post_aac_tp_dbtp:.2f} dBTP)"
            _add_diag("gate6_audio_mastering", "WARN", "r35_post_aac_tp", f"Post-AAC TP={post_aac_tp_dbtp:.2f} dBTP > {args.tp_ceiling:g} dBTP", fix_aac)
            concerns.append(f"R35 Post-AAC True Peak {post_aac_tp_dbtp:.2f} dBTP > {args.tp_ceiling:g} dBTP — Fix: {fix_aac}")

        gates["gate6_closed_loop_loudness"] = "PASS"
        aac_log = f", AAC_TP={post_aac_tp_dbtp:.2f} dBTP" if post_aac_tp_dbtp is not None else ""
        print(
            f"✅ [Gate 5 & 6/8] Contact Sheet (1440x2560) + Closed-Loop Audio: "
            f"I={ebur_metrics['lufs']:.2f} LUFS (target {args.target_lufs:.1f}), "
            f"PCM_TP={ebur_metrics['true_peak_dbtp']:.2f} dBTP{aac_log}, passes={attempts_used}"
        )

        summary["fc_build"] = {
            "ok": build_report.get("ok", False),
            "mismatches": build_report.get("mismatches", {}),
            "unsupported": build_report.get("unsupported", []),
            "warnings": build_report.get("warnings", []),
            "counts": build_report.get("actual", {}),
        }
        summary["audio_mastering"] = {
            "target_lufs": args.target_lufs,
            "initial_pretrim_db": {"voice_bgm": init_vb_trim, "voice": init_voice_trim, "sfx": init_sfx_trim},
            "measured_lufs": ebur_metrics["lufs"],
            "measured_lra_lu": ebur_metrics["lra"],
            "measured_true_peak_dbtp": ebur_metrics["true_peak_dbtp"],
            "post_aac_true_peak_dbtp": post_aac_tp_dbtp,
            "lufs_deviation_lu": round(lufs_final_dev, 2),
            "closed_loop_attempts": attempts_used,
            "closed_loop_delta_db": closed_loop_delta,
            "limiter_max_db": effective_limiter_db,
            "stems_bgm_chain": use_bgm_chain,
            "stems_check": stems_check_res,
        }
        summary["outputs"].update(
            {
                "fc_build_report": str(build_report_path),
                "mix_wav": str(mix_wav_path),
                "stems_dir": str(stems_dir) if audio_roles else None,
                "qa_frames_dir": str(qa_frames_dir),
                "qa_contact_sheet": str(contact_sheet_path),
            }
        )

        # ======================================================================
        # GATE 7: SFX Integrity + Ruling `R217` `match_at` NCC Audit + Portable Bundle
        # ======================================================================
        t0 = time.perf_counter()
        sfx_qa_dir = work_dir / "sfx_qa"
        sfx_qa_dir.mkdir(parents=True, exist_ok=True)
        r_sfx = subprocess.run(
            [py, str(AUDIT_SFX_PY), str(build_fcproj), "--out", str(sfx_qa_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=_RUN_TIMEOUT_S, encoding="utf-8", errors="replace",
        )
        sfx_json_path = sfx_qa_dir / "audit_sfx.json"
        if r_sfx.returncode != 0 or not sfx_json_path.is_file():
            gates["gate7_sfx_and_portable_bundle"] = "FAIL"
            raise RuntimeError(f"Gate 7 (audit_sfx.py) failed:\n{r_sfx.stderr or r_sfx.stdout}")

        sfx_rep = json.loads(sfx_json_path.read_text(encoding="utf-8"))
        repeated_takes = sfx_rep.get("repeated_takes", [])
        missing_sfx = int(sfx_rep.get("missing_files", 0))
        clipping_rows = [f for f in sfx_rep.get("files", []) if f.get("clipping")]  # judged on the post-gain peak (audit_sfx.py, v7.7.0)
        clipping_sfx = [f["path"] for f in clipping_rows]

        # Ruling `R217` Normalized Cross-Correlation (`match_at`) SFX Sync Audit
        r217_res = audit_sfx_sync_r217(
            sfx_stem_wav=stems_dir / "sfx.wav",
            mix_wav=mix_wav_path,
            levels_spec=levels_spec_doc,
            fps=float(sanitized_spec.get("fps", 30.0)),
        )
        summary["sfx_sync_r217"] = r217_res
        for w_r217 in r217_res.get("warnings") or []:
            msg_part, _, fix_part = w_r217.partition(" — Fix: ")
            _add_diag("gate7_sfx_sync_r217", "WARN", "R217_SFX_SYNC", msg_part, fix_part or "align SFX clip `at`")
            concerns.append(w_r217)
            print(f"   ⚠️  [Gate 7 {w_r217}]")

        if clipping_sfx:
            worst_after = max((float(f.get("peak_dbfs_after_gain") or 0.0) for f in clipping_rows), default=0.0)
            fix_clip = (f"lower the clip `gain_db` until the post-gain peak is <= -1.0 dBFS (worst now {worst_after:+.1f} dBFS after gain) "
                        f"on {[Path(p).name for p in clipping_sfx[:3]]}")
            _add_diag("gate7_sfx_audit", "WARN", "SFX_SOURCE_CLIPPING", f"{len(clipping_sfx)} SFX clip(s) reach 0 dBFS after their clip gain", fix_clip)
            concerns.append(f"SFX source clipping ({len(clipping_sfx)} file(s)) — Fix: {fix_clip}")

        summary["sfx_audit"] = {
            "events": sfx_rep.get("events", 0),
            "unique_takes": sfx_rep.get("unique_takes", 0),
            "repeated_takes": repeated_takes,
            "missing_files": missing_sfx,
            "clipping_files": clipping_sfx,
            "ncc_verified_cues": r217_res.get("ncc_verified_cues", 0),
            "median_abs_offset_frames": r217_res.get("median_abs_offset_frames", 0.0),
        }
        summary["outputs"]["sfx_audit_json"] = str(sfx_json_path)

        if repeated_takes or missing_sfx > 0:
            gates["gate7_sfx_and_portable_bundle"] = "FAIL"
            fix_rep = f"replace duplicate SFX takes {repeated_takes[:4]} with `AUTO:<keyword>` + `--auto-sfx-dir`"
            _add_diag("gate7_sfx_audit", "ERROR", "SFX_INTEGRITY", f"repeated_takes={repeated_takes}, missing_files={missing_sfx}", fix_rep)
            raise RuntimeError(
                f"Gate 7 SFX audit failed: repeated_takes={repeated_takes}, missing_files={missing_sfx} — Fix: {fix_rep}"
            )

        backup_path = backup_existing_fcproj(out_fcproj)
        if backup_path:
            summary["outputs"]["backup_fcproj"] = str(backup_path)
            print(f"📦 [Rule A3 Backup] Saved previous {out_fcproj.name} -> {backup_path}")

        if portable_root is not None:
            smoke_t = planned_16[len(planned_16) // 3][0] if planned_16 else 1.0
            bundle_info = relativize_and_verify_bundle(
                compiled_fcproj=build_fcproj,
                out_fcproj=out_fcproj,
                portable_root=portable_root,
                work_dir=work_dir,
                smoke_time_s=smoke_t,
            )
            summary["portable_bundle"] = bundle_info
            summary["outputs"]["bundle_manifest"] = bundle_info["bundle_manifest"]
            summary["outputs"]["portable_smoke_png"] = bundle_info["smoke_frame_png"]
        else:
            out_fcproj.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build_fcproj, out_fcproj)
            summary["portable_bundle"] = {"enabled": False}

        summary["outputs"]["fcproj"] = str(out_fcproj)
        timings["gate7_sfx_and_portable_bundle"] = round(time.perf_counter() - t0, 3)
        gates["gate7_sfx_and_portable_bundle"] = "PASS"
        print(
            f"✅ [Gate 7/8] SFX Audit ({sfx_rep.get('events', 0)} events, 0 repeats, "
            f"R217 verified={r217_res.get('ncc_verified_cues', 0)}, median_offset={r217_res.get('median_abs_offset_frames', 0.0):.2f}f) "
            f"& Export ({timings['gate7_sfx_and_portable_bundle']:.2f}s) -> {out_fcproj}"
        )

        # ======================================================================
        # GATE 8: Epistemic `claim_gate` (R200) + Tri-State Verdict + `EDITOR-REPORT.md`
        # ======================================================================
        t_g8 = time.perf_counter()
        if args.hook_gates:
            hook_res = run_hook_gates(args.preview, args.hook_mask)
            summary["hook_gates"] = hook_res
            if hook_res.get("ok"):
                print(f"✅ [Hook gates] motion mean={hook_res['mean']:.2f}, max static run={hook_res['max_static_run_s']:.2f}s")
            else:
                concerns.append("hook_gates: " + "; ".join(hook_res.get("errors") or ["motion gate failed"]))
                print(f"⚠️ [Hook gates] {concerns[-1]}")
        verdict = "DONE_WITH_CONCERNS" if concerns else "VERIFIED"
        summary["ok"] = True
        summary["verdict"] = verdict
        summary["owner_stage"] = None
        gates["gate8_epistemic_verdict_and_report"] = f"PASS ({verdict})"

        if args.open_app:
            gui_pid = open_in_filmcraft_gui(out_fcproj, args.display)
            summary["opened_gui_pid"] = gui_pid

        timings["gate8_report_and_verdict"] = round(time.perf_counter() - t_g8, 3)
        summary["total_elapsed_sec"] = round(time.perf_counter() - t_start_all, 3)
        summary["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        tally = gate_tally(gates)
        summary["gates_passed"] = tally["passed"]
        summary["gates_skipped"] = tally["skipped"]

        write_editor_report_md(editor_report_path, summary)
        serialized_summary = json.dumps(summary, ensure_ascii=False, indent=2)
        summary_path.write_text(serialized_summary, encoding="utf-8")
        compile_report_path.write_text(serialized_summary, encoding="utf-8")

        claim_banner = " · [R200 CLAIM_GATE: HOLD PUBLISH UNTIL USER CONFIRMS]" if claim_gate_active else ""
        print(
            f"🚀 [{tally['banner']} · {verdict}] Tier=`{tier_used}` · Compiled `{out_fcproj.name}` "
            f"in {summary['total_elapsed_sec']:.2f}s!{claim_banner}\n"
            f"   📄 Report  -> {editor_report_path}\n"
            f"   📊 Summary -> {compile_report_path} (& {summary_path.name})"
        )
        return 0

    except Exception as exc:
        summary["ok"] = False
        summary["verdict"] = "REJECTED"
        summary["owner_stage"] = failure_owner_stage or "BUILD"
        summary["error"] = str(exc)
        gates["gate8_epistemic_verdict_and_report"] = "REJECTED"
        summary["total_elapsed_sec"] = round(time.perf_counter() - t_start_all, 3)
        summary["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            write_editor_report_md(editor_report_path, summary)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as rep_exc:
            print(f"WARNING: could not write editor report {editor_report_path}: {type(rep_exc).__name__}: {rep_exc}", file=sys.stderr)
        serialized_err = json.dumps(summary, ensure_ascii=False, indent=2)
        summary_path.write_text(serialized_err, encoding="utf-8")
        compile_report_path.write_text(serialized_err, encoding="utf-8")
        print(
            f"❌ [COMPILER REJECTED · owner_stage={summary['owner_stage']} after {summary['total_elapsed_sec']:.2f}s] {exc}",
            file=sys.stderr,
        )
        print(f"   📄 Report  -> {editor_report_path}", file=sys.stderr)
        print(f"   📊 Summary -> {compile_report_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
