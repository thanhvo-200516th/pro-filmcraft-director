#!/usr/bin/env python3
"""
Universal Studio Director v7.9.1 — Web-Cinema Studio Plate & Kinetic Typography Builder (`web_plate_builder.py`)
================================================================================================================
Replaces legacy PIL/OpenCV raster cards and static PNG hero stamps with:
  - 8 Studio UI / 3D Card Templates (upgraded with continuous 3D parallax breathing, sweeping specular
    glass sheen, real-second syllable triggers, and full-duration live typing)
  - 12 `@__dviet` + `@vietanh` Kinetic Typography Templates (`kt01`..`kt12`, `0px` black stroke,
    `0.32em 0.25em` Vietnamese NFC diacritic safe padding, zero forced `— ALL CAPS KICKER`, zero
    forced pill badge, `player3Snap` / `velvetC2` / `halationPulse` / `splitGraphemesVi` / Swash-Hybrid)
rendered into 60fps ProRes 4444 (`yuva444p10le`) / `qtrle` `.mov` overlays and RGBA `.png` stills via
`web_cinema_plate_engine.mjs` (Node v22 Multi-Tab Parallel CDP Pool, 0 external npm dependencies).

8 Studio Templates (`v7.0` -> `v7.1` Continuous-Motion Upgraded):
  1. `dviet_overlapping_feather_cluster`  — Video #10/#08/#14 @__dviet Feather=29 + Swash + Glow 2
  2. `frosted_glass_bento_steps`          — 01•02•03 Glassmorphism Bento Steps + Continuous Sheen
  3. `clinical_before_after_1_to_28`      — Video #02 Asymmetric 1:2.8 Before/After + Live Process Bar
  4. `course_3d_matte_asset_box`          — Video #06 3D Matte-Black Vault Box + 3 Fan-Out Cards
  5. `tactile_review_glass_scorecard`     — 9.4/10 Glass Review Scorecard + Pros (#4ADE80) / Cons (#FF4D5E)
  6. `isometric_3d_prompt_browser`        — Video #12/#16/#18 3D Prompt Studio + Continuous Typing & Locks
  7. `skewed_3d_polaroid_trio`            — V14 -7deg / 0deg / +8deg 3D Polaroid Trio + Bottom Note Wipe
  8. `doctor_authority_lower_third`       — International Hospital / Specialist Executive Lower-Third

12 Kinetic Typography Templates (`v7.1` `@60fps` `.mov`):
  - `kt01_kiss_editorial_2line`           (`SIL_KISS_2L`)
  - `kt02_feather_swash_overlap`          (`SIL_FEATHER_SWASH`)
  - `kt03_per_word_nonlinear_bloom`       (`SIL_WORD_STAGGER`)
  - `kt04_ghost_to_focus_stack`           (`SIL_GHOST_STACK`)
  - `kt05_wall_spatial_counterpoint`      (`SIL_WALL_HOP`)
  - `kt06_bridge_anchor_live_swap`        (`SIL_BRIDGE_SWAP`)
  - `kt07_telescoping_char_rollout`       (`SIL_CHAR_ACCORDION`)
  - `kt08_mist_evaporation_reveal`        (`SIL_MIST_GRADIENT`)
  - `kt09_strike_myth_laser_2phase`       (`SIL_MYTH_STRIKE`)
  - `kt10_cursor_bars_pillar_gate`        (`SIL_CURSOR_HUD`)
  - `kt11_cranial_svg_arc_or_tilt`        (`SIL_TILT_OR_ARC`)
  - `kt12_whisper_or_directional_echo`    (`SIL_WHISPER_ECHO`)

Python API:
  - `KINETIC_TYPO_TEMPLATES`
  - `render_kinetic_typo_mov(template, props, out_path, ...)`
  - `render_kinetic_typo_batch(jobs, concurrency=None, workspace_context=None, work_dir=None, ...)`
  - `render_web_plate(template, props, out_path, ...)`
  - `render_web_plates_batch(jobs, concurrency=None, workspace_context=None, work_dir=None, ...)`
    (v7.9.1: Chrome tabs = `resolve_chrome_workers`: <= 4, env `PFD_CHROME_WORKERS`, workspace_context `max_chrome_workers`)
  - `strip_media_metadata(path)` (v7.9.1 shared helper: strip-media-metadata skill, else ffmpeg / PIL, loud warning)
  - `render_studio_card_mov(template, props, out_path, ...)`
  - `render_dviet_typo_cluster_png(..., allow_static_thumbnail=False)`
  - `build_template_html(template, props, width=..., height=...)`
"""
from __future__ import annotations

import argparse
import base64
import functools
import html
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import warnings
from pathlib import Path
from typing import Any, Sequence

THIS_FILE = Path(__file__).resolve()
SCRIPTS_DIR = THIS_FILE.parent.parent
ENGINE_MJS = SCRIPTS_DIR / "web_cinema_plate_engine.mjs"

NODE_CANDIDATES = [
    os.environ.get("NODE_BIN", ""),
    str(Path.home() / ".local/bin/node"),
    shutil.which("node") or "",
    "/usr/bin/node",
]

STRIP_METADATA_Candidates = [
    Path.home() / ".gemini/config/skills/strip-media-metadata/scripts/strip_metadata.py",
    Path.home() / ".claude/skills/strip-media-metadata/scripts/strip_metadata.py",
    Path.home() / ".agents/skills/strip-media-metadata/scripts/strip_metadata.py",
]

# v7.7.0: the TNEDIT font folder is a SEARCH LIST (first hit wins); env `PFD_FONT_DIR` is tried before it.
# v7.9.1: these user folders are OPTIONAL extra search dirs: `PFD_FONT_DIR` (os.pathsep list) comes first and fontconfig
# (`fc-list`, any installed file with the same name) is the last resort; a face that still resolves nowhere warns loudly.
FONT_ROOTS_TNEDIT: tuple[Path, ...] = (
    Path.home() / ".local/share/fonts/tnedit",
    Path.home() / ".local/share/fonts/TNEDIT_DViet/Lien_ket_thu_vien_co_san",
)
FONT_ROOT_TNEDIT = FONT_ROOTS_TNEDIT[0]  # back-compat alias: the primary folder
FONT_ROOT_MONT = Path.home() / ".local/share/fonts/Montserrat_Static"
FONT_ROOT_MONO = Path.home() / ".local/share/fonts/apple-sf-mono"
FONT_ROOT_BASE = Path.home() / ".local/share/fonts"

# 4-Act Jewel Palette (plus semantic studio aliases)
JEWEL_PALETTES: dict[str, dict[str, str]] = {
    "gold": {
        "name": "Act Gold",
        "hex": "#F5C451",
        "bright": "#FEF08A",
        "deep": "#92400E",
        "glow_inner": "rgba(254, 240, 138, 0.62)",
        "glow_outer": "rgba(245, 196, 81, 0.44)",
        "glow_ambient": "rgba(245, 196, 81, 0.20)",
        "pill_bg": "rgba(245, 196, 81, 0.14)",
        "pill_border": "rgba(245, 196, 81, 0.42)",
    },
    "crimson": {
        "name": "Act Crimson",
        "hex": "#FF4D5E",
        "bright": "#FECDD3",
        "deep": "#881337",
        "glow_inner": "rgba(254, 205, 211, 0.60)",
        "glow_outer": "rgba(255, 77, 94, 0.46)",
        "glow_ambient": "rgba(255, 77, 94, 0.20)",
        "pill_bg": "rgba(255, 77, 94, 0.14)",
        "pill_border": "rgba(255, 77, 94, 0.44)",
    },
    "emerald": {
        "name": "Act Emerald",
        "hex": "#34D399",
        "bright": "#A7F3D0",
        "deep": "#065F46",
        "glow_inner": "rgba(167, 243, 208, 0.58)",
        "glow_outer": "rgba(52, 211, 153, 0.44)",
        "glow_ambient": "rgba(52, 211, 153, 0.20)",
        "pill_bg": "rgba(52, 211, 153, 0.14)",
        "pill_border": "rgba(52, 211, 153, 0.42)",
    },
    "ice_cyan": {
        "name": "Act Ice-Cyan",
        "hex": "#7DD3FC",
        "bright": "#E0F2FE",
        "deep": "#075985",
        "glow_inner": "rgba(224, 242, 254, 0.62)",
        "glow_outer": "rgba(125, 211, 252, 0.46)",
        "glow_ambient": "rgba(125, 211, 252, 0.20)",
        "pill_bg": "rgba(125, 211, 252, 0.14)",
        "pill_border": "rgba(125, 211, 252, 0.44)",
    },
}

# Light-Canvas Polarity Jewel Palettes (rich deep ink on #F6F6F8 / #F3F8F5 / #FAF7F2 studio paper)
JEWEL_PALETTES_LIGHT: dict[str, dict[str, str]] = {
    "gold": {
        "name": "Act Gold Light",
        "hex": "#B45309",
        "bright": "#92400E",
        "deep": "#78350F",
        "glow_inner": "rgba(180, 83, 9, 0.22)",
        "glow_outer": "rgba(180, 83, 9, 0.12)",
        "glow_ambient": "rgba(180, 83, 9, 0.08)",
        "pill_bg": "rgba(255, 255, 255, 0.90)",
        "pill_border": "rgba(180, 83, 9, 0.38)",
    },
    "crimson": {
        "name": "Act Crimson Light",
        "hex": "#BE123C",
        "bright": "#9F1239",
        "deep": "#881337",
        "glow_inner": "rgba(190, 18, 60, 0.22)",
        "glow_outer": "rgba(190, 18, 60, 0.12)",
        "glow_ambient": "rgba(190, 18, 60, 0.08)",
        "pill_bg": "rgba(255, 255, 255, 0.90)",
        "pill_border": "rgba(190, 18, 60, 0.38)",
    },
    "emerald": {
        "name": "Act Emerald Light",
        "hex": "#047857",
        "bright": "#065F46",
        "deep": "#064E3B",
        "glow_inner": "rgba(4, 120, 87, 0.22)",
        "glow_outer": "rgba(4, 120, 87, 0.12)",
        "glow_ambient": "rgba(4, 120, 87, 0.08)",
        "pill_bg": "rgba(255, 255, 255, 0.90)",
        "pill_border": "rgba(4, 120, 87, 0.38)",
    },
    "ice_cyan": {
        "name": "Act Ice-Cyan Light",
        "hex": "#0369A1",
        "bright": "#075985",
        "deep": "#0C4A6E",
        "glow_inner": "rgba(3, 105, 161, 0.22)",
        "glow_outer": "rgba(3, 105, 161, 0.12)",
        "glow_ambient": "rgba(3, 105, 161, 0.08)",
        "pill_bg": "rgba(255, 255, 255, 0.90)",
        "pill_border": "rgba(3, 105, 161, 0.38)",
    },
}

PALETTE_ALIASES: dict[str, str] = {
    "gold": "gold",
    "amber": "gold",
    "prestige_gold": "gold",
    "amber_7706": "gold",
    "crimson": "crimson",
    "coral": "crimson",
    "red": "crimson",
    "pain_coral": "crimson",
    "alert_coral": "crimson",
    "emerald": "emerald",
    "mint": "emerald",
    "green": "emerald",
    "lock_mint": "emerald",
    "emerald_7707": "emerald",
    "ice_cyan": "ice_cyan",
    "ice-cyan": "ice_cyan",
    "cyan": "ice_cyan",
    "blue": "ice_cyan",
    "cinema_cyan": "ice_cyan",
    "cyan_7688": "ice_cyan",
}

KINETIC_TYPO_TEMPLATES: dict[str, dict[str, Any]] = {
    "kt01_kiss_editorial_2line": {
        "layout_silhouette": "SIL_KISS_2L",
        "default_entrance_style": "player3_kiss_rise",
        "width": 1080,
        "height": 460,
        "description": "@__dviet #01/#18/#19 lowercase negative-leading kiss (line-height 0.82) + player3Snap vertical blur 5px->0 + micro-float",
    },
    "kt02_feather_swash_overlap": {
        "layout_silhouette": "SIL_FEATHER_SWASH",
        "default_entrance_style": "feather29_swash_wipe",
        "width": 1080,
        "height": 560,
        "description": "@__dviet #08/#10 staggered 3-beat Feather=29 ExtraBold + Swash-Initial Hybrid feather=28 horizontal wipe + Glow-2 halation",
    },
    "kt03_per_word_nonlinear_bloom": {
        "layout_silhouette": "SIL_WORD_STAGGER",
        "default_entrance_style": "syllable_nonlinear_unblur",
        "width": 1080,
        "height": 460,
        "description": "@__dviet #03/#10/#19 word-by-word syllable bloom (sequential [0,1,2] or gap-bridge [0,2,1]) with 12px->0 unblur + halationPulse",
    },
    "kt04_ghost_to_focus_stack": {
        "layout_silhouette": "SIL_GHOST_STACK",
        "default_entrance_style": "bokeh_condense_recede",
        "width": 1080,
        "height": 520,
        "description": "@__dviet #12/#18 + dviet_7706 Style 1: setup line recedes (opacity 0.28, blur 4.5px) as Hero condenses out of 16px optical bokeh",
    },
    "kt05_wall_spatial_counterpoint": {
        "layout_silhouette": "SIL_WALL_HOP",
        "default_entrance_style": "spatial_counterpoint_hop",
        "width": 1080,
        "height": 540,
        "description": "@__dviet #18 EV#3 & #19 f_01320 Negative-Space Wall Hop or Left(28%) vs Right(72%) Spatial Counterpoint",
    },
    "kt06_bridge_anchor_live_swap": {
        "layout_silhouette": "SIL_BRIDGE_SWAP",
        "default_entrance_style": "anchor_slot_blur_reel",
        "width": 1080,
        "height": 440,
        "description": "@__dviet #01/#06/#11 (S16): persistent locked anchor phrase + crisp 8f vertical Gaussian blur-push live swap reel",
    },
    "kt07_telescoping_char_rollout": {
        "layout_silhouette": "SIL_CHAR_ACCORDION",
        "default_entrance_style": "grapheme_telescope_rollout",
        "width": 1080,
        "height": 440,
        "description": "@vietanh fam06 + #09: splitGraphemesVi per-grapheme rollout (-32px->0, 26ms/char, early opacity u=0.38) + moving specular sheen",
    },
    "kt08_mist_evaporation_reveal": {
        "layout_silhouette": "SIL_MIST_GRADIENT",
        "default_entrance_style": "gaussian_mist_evaporation",
        "width": 1080,
        "height": 480,
        "description": "@__dviet #12 'chữ mờ ảo' & EV#4 'vùng sáng': crisp anchor + horizontal feathered Gaussian-mist evaporation (18px->0 or 1.8px tail)",
    },
    "kt09_strike_myth_laser_2phase": {
        "layout_silhouette": "SIL_MYTH_STRIKE",
        "default_entrance_style": "slam_then_laser_slash",
        "width": 1080,
        "height": 500,
        "description": "V14/V15 + va_fam09 'giả trân': Phase 1 Hero slam/condense + Phase 2 glowing #FF4D5E SVG razor laser slash across 56% x-height",
    },
    "kt10_cursor_bars_pillar_gate": {
        "layout_silhouette": "SIL_CURSOR_HUD",
        "default_entrance_style": "center_pillar_gate_wipe",
        "width": 1080,
        "height": 460,
        "description": "va_fam03 '| 3 bước khóa ảnh |' + #19 hairline viewfinder: two glowing jewel pillars with micro-pin circles parting outward",
    },
    "kt11_cranial_svg_arc_or_tilt": {
        "layout_silhouette": "SIL_TILT_OR_ARC",
        "default_entrance_style": "cranial_arc_or_countertilt",
        "width": 1080,
        "height": 620,
        "description": "@__dviet #17/#18/#19: mode='svg_arc' true SVG <textPath> halo arch clockwise sweep OR mode='tilted_chest' -5.5deg counter-tilt",
    },
    "kt12_whisper_or_directional_echo": {
        "layout_silhouette": "SIL_WHISPER_ECHO",
        "default_entrance_style": "whisper_rail_or_ghost_echo",
        "width": 1080,
        "height": 440,
        "description": "Dual-mode @__dviet contrast: mode='whisper' ultra-clean 36-40px lowercase rail OR mode='directional_echo' #19 f_01362 stepped ghost echoes",
    },
}

TEMPLATE_DEFAULTS: dict[str, dict[str, Any]] = {
    "dviet_overlapping_feather_cluster": {
        "width": 1080,
        "height": 760,
        "description": "Video #10/#08/#14 @__dviet Feather=29 ExtraBold + Playfair/Aaron Swash Drop-Cap + Glow 2",
    },
    "frosted_glass_bento_steps": {
        "width": 1080,
        "height": 1920,
        "description": "Dark/Light Glassmorphism 01•02•03 Bento Steps with Continuous Sheen & 3D Breathing",
    },
    "clinical_before_after_1_to_28": {
        "width": 1080,
        "height": 1920,
        "description": "Video #02 Asymmetric 1:2.8 Before/After Z-Depth Comparison + Live Process Bar",
    },
    "course_3d_matte_asset_box": {
        "width": 1080,
        "height": 1920,
        "description": "Video #06 3D Matte-Black Folder/Vault Box + 3 Fan-Out Rounded Asset Cards",
    },
    "tactile_review_glass_scorecard": {
        "width": 1080,
        "height": 1920,
        "description": "Modern Glass Review Scorecard (9.4/10 + Pros #4ADE80 vs Cons #FF4D5E)",
    },
    "isometric_3d_prompt_browser": {
        "width": 1080,
        "height": 1920,
        "description": "Video #12/#16/#18 Isometric 3D Prompt Studio Browser + Continuous Typewriter + Lock Badges",
    },
    "skewed_3d_polaroid_trio": {
        "width": 1080,
        "height": 1920,
        "description": "V14 Upgrade: -7deg / 0deg / +8deg 3D Fanned Cream Polaroids + Bottom Note Wipe & Continuous Sheen",
    },
    "doctor_authority_lower_third": {
        "width": 1080,
        "height": 1920,
        "description": "International Hospital / Specialist Executive Lower-Third Credential Plate",
    },
    "screen_strip": {
        "width": 1080,
        "height": 1920,
        "description": "v7.4 @__dviet tutorial layout: 1080x~600 screen strip centred on a 3x-zoomed, blurred, darkened A-roll plate; caption y 67%",
    },
    "card_916": {
        "width": 1080,
        "height": 1920,
        "description": "v7.4 @__dviet 9:16 card with white border + rounded corners and a yellow label on a spotlight-grey stage",
    },
    "profile_card": {
        "width": 1080,
        "height": 1920,
        "description": "v7.4 @__dviet fake profile card: avatar, handle, three counts, bio",
    },
    **KINETIC_TYPO_TEMPLATES,
}


# ---------------------------------------------------------------------------
# NFC & Safe Escaping Utilities
# ---------------------------------------------------------------------------

def nfc(val: Any) -> str:
    """Guarantees 134/134 Vietnamese NFC precomposed Unicode normalization."""
    if val is None:
        return ""
    return unicodedata.normalize("NFC", str(val))


def esc(val: Any) -> str:
    """NFC-normalizes and HTML-escapes text safely."""
    return html.escape(nfc(val), quote=True)


def normalize_props_nfc(obj: Any) -> Any:
    """Recursively normalizes all strings inside dicts/lists to Unicode NFC."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        return {k: normalize_props_nfc(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, (list, tuple)):
        return [normalize_props_nfc(x) for x in obj]
    return obj


def _prop_or_demo(template: str, props: dict[str, Any], keys: str | tuple[str, ...], demo_value: str = "", *, required: bool = True) -> str:
    """Text prop (first non-empty of `keys`) without silent demo copy: a missing value is omitted (`required=False`)
    or raises `ValueError`. `props["demo"]` (CLI `--demo`, self-tests) is the only way to get `demo_value`."""
    key_t = (keys,) if isinstance(keys, str) else keys
    for k in key_t:
        val = nfc(props.get(k) or "").strip()
        if val:
            return val
    if props.get("demo"):
        return nfc(demo_value)
    if required:
        raise ValueError(
            f"{template}: required prop '{key_t[0]}' is missing (pass it, or demo=true / --demo for self-test text)"
        )
    return ""


def resolve_jewel_palette(accent: str | None, *, theme: str = "dark") -> dict[str, str]:
    """Resolves a named jewel palette or constructs one from a custom #RRGGBB hex (supports theme='light')."""
    is_light = nfc(theme).strip().lower() == "light"
    pal_table = JEWEL_PALETTES_LIGHT if is_light else JEWEL_PALETTES
    if not accent:
        return dict(pal_table["gold"])
    raw = nfc(accent).strip()
    key = raw.lower()
    if key in PALETTE_ALIASES:
        return dict(pal_table[PALETTE_ALIASES[key]])
    if is_light and key in ("#facc15", "#f5c451", "#fef08a", "#fde047", "#fbbf24"):
        return dict(JEWEL_PALETTES_LIGHT["gold"])
    if is_light and key in ("#34d399", "#10b981", "#a7f3d0", "#4ade80"):
        return dict(JEWEL_PALETTES_LIGHT["emerald"])
    if is_light and key in ("#ff4d5e", "#f43f5e", "#fecdd3"):
        return dict(JEWEL_PALETTES_LIGHT["crimson"])
    if is_light and key in ("#7dd3fc", "#38bdf8", "#e0f2fe"):
        return dict(JEWEL_PALETTES_LIGHT["ice_cyan"])
    if raw.startswith("#") and len(raw) == 7:
        try:
            r = int(raw[1:3], 16)
            g = int(raw[3:5], 16)
            b = int(raw[5:7], 16)
            if is_light:
                # Ensure deep editorial ink legibility on light paper
                luma = 0.299 * r + 0.587 * g + 0.114 * b
                if luma > 135:
                    r = max(0, int(r * 0.52))
                    g = max(0, int(g * 0.45))
                    b = max(0, int(b * 0.45))
                dr = max(0, r - 28)
                dg = max(0, g - 28)
                db = max(0, b - 28)
                return {
                    "name": f"Custom Light {raw}",
                    "hex": f"#{r:02X}{g:02X}{b:02X}",
                    "bright": f"#{dr:02X}{dg:02X}{db:02X}",
                    "deep": f"rgba({max(0, r - 60)}, {max(0, g - 60)}, {max(0, b - 60)}, 1)",
                    "glow_inner": f"rgba({r}, {g}, {b}, 0.22)",
                    "glow_outer": f"rgba({r}, {g}, {b}, 0.12)",
                    "glow_ambient": f"rgba({r}, {g}, {b}, 0.08)",
                    "pill_bg": "rgba(255, 255, 255, 0.90)",
                    "pill_border": f"rgba({r}, {g}, {b}, 0.38)",
                }
            br = min(255, r + 55)
            bg = min(255, g + 55)
            bb = min(255, b + 55)
            return {
                "name": f"Custom {raw}",
                "hex": raw,
                "bright": f"#{br:02X}{bg:02X}{bb:02X}",
                "deep": f"rgba({max(0, r - 90)}, {max(0, g - 90)}, {max(0, b - 90)}, 1)",
                "glow_inner": f"rgba({br}, {bg}, {bb}, 0.60)",
                "glow_outer": f"rgba({r}, {g}, {b}, 0.45)",
                "glow_ambient": f"rgba({r}, {g}, {b}, 0.20)",
                "pill_bg": f"rgba({r}, {g}, {b}, 0.14)",
                "pill_border": f"rgba({r}, {g}, {b}, 0.44)",
            }
        except ValueError:
            pass
    return dict(pal_table["gold"])


def resolve_node_binary() -> str:
    for cand in NODE_CANDIDATES:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise FileNotFoundError(
        f"Node v22+ binary not found. Checked: {NODE_CANDIDATES}"
    )


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")
METADATA_STRIP_TIMEOUT_S = 300.0


def _resolve_ffmpeg_bin() -> str | None:
    for cand in (os.environ.get("FFMPEG_BIN", ""), str(Path.home() / ".local/bin/ffmpeg"), shutil.which("ffmpeg") or ""):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _strip_image_with_pil(path: Path, keep_icc: bool) -> None:
    """Re-save the pixels without EXIF / XMP / text chunks (JPEG keeps its quantisation tables, quality="keep")."""
    from PIL import Image  # lazy: the HTML builders never need PIL

    tmp = path.with_name(f".{path.name}.strip{path.suffix}")
    with Image.open(path) as im:
        im.load()
        fmt = im.format
        keep = {k: im.info[k] for k in ("transparency",) if k in im.info}
        if keep_icc and im.info.get("icc_profile"):
            keep["icc_profile"] = im.info["icc_profile"]
        im.info = keep
        im.save(tmp, format=fmt, **({"quality": "keep"} if fmt == "JPEG" else {}), **keep)
    os.replace(tmp, path)


def _strip_video_with_ffmpeg(path: Path) -> bool:
    ff = _resolve_ffmpeg_bin()
    if not ff:
        return False
    tmp = path.with_name(f".{path.stem}.strip{path.suffix}")
    cmd = [ff, "-y", "-v", "error", "-i", str(path), "-map", "0:v?", "-map", "0:a?", "-map_metadata", "-1", "-map_chapters", "-1",
           "-c", "copy", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", str(tmp)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=METADATA_STRIP_TIMEOUT_S,
                           check=False)
    except (OSError, subprocess.SubprocessError):
        tmp.unlink(missing_ok=True)
        return False
    if r.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, path)
    return True


def strip_media_metadata(file_path: str | Path, *, keep_icc: bool = True) -> str:
    """v7.9.1 shared metadata strip for every deliverable (web_plate_builder, typography_composer, dviet_motion_canvas_engine,
    visual_blocks). Order: the sibling skill strip-media-metadata (`STRIP_METADATA_Candidates`, lossless) -> built-in fallback
    (images: PIL re-save without EXIF / text chunks; video: `ffmpeg -map_metadata -1 -c copy`). Returns the method that worked
    ("strip-media-metadata", "pil", "ffmpeg") or "" after a LOUD warning when nothing could strip the file. Missing file -> ""."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    for script in STRIP_METADATA_Candidates:
        if script.is_file():
            try:
                r = subprocess.run([sys.executable, str(script), *(["--keep-icc"] if keep_icc else []), str(p)], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=METADATA_STRIP_TIMEOUT_S, check=False)
                if r.returncode == 0:
                    return "strip-media-metadata"
            except (OSError, subprocess.SubprocessError):
                pass
            break
    if p.suffix.lower() in IMAGE_SUFFIXES:
        try:
            _strip_image_with_pil(p, keep_icc)
            return "pil"
        except Exception as exc:  # noqa: BLE001 - reported below, never silent
            err = f"PIL re-save failed: {exc}"
    else:
        err = "ffmpeg -map_metadata -1 failed" if _resolve_ffmpeg_bin() else "ffmpeg not found"
        if _strip_video_with_ffmpeg(p):
            return "ffmpeg"
    warnings.warn(f"METADATA NOT STRIPPED: {p} (strip-media-metadata skill not installed / failed; {err}). The file may still carry "
                  "EXIF / XMP / C2PA / generator tags: strip it before delivery.", stacklevel=2)
    return ""


def strip_media_metadata_if_available(file_path: Path) -> None:
    """Back-compat alias of `strip_media_metadata` (v7.9.1: never skips silently any more)."""
    strip_media_metadata(file_path)


# ---------------------------------------------------------------------------
# Safe Image -> Data-URL Loader + Studio Procedural Fallbacks
# ---------------------------------------------------------------------------

def _procedural_studio_svg_data_url(variant: str = "after", label: str = "") -> str:
    """Generates an ultra-clean studio artwork SVG data-URL when no external image is passed."""
    lbl = esc(label or variant.upper())
    if variant == "before":
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 720">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#292524"/>
              <stop offset="55%" stop-color="#1C1917"/>
              <stop offset="100%" stop-color="#0C0A09"/>
            </linearGradient>
            <radialGradient id="warm" cx="50%" cy="42%" r="55%">
              <stop offset="0%" stop-color="#78716C" stop-opacity="0.45"/>
              <stop offset="100%" stop-color="#1C1917" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <rect width="600" height="720" fill="url(#bg)"/>
          <rect width="600" height="720" fill="url(#warm)"/>
          <g stroke="rgba(255,255,255,0.10)" stroke-width="1.5" fill="none">
            <line x1="0" y1="240" x2="600" y2="240" stroke-dasharray="6 6"/>
            <line x1="0" y1="480" x2="600" y2="480" stroke-dasharray="6 6"/>
            <line x1="300" y1="0" x2="300" y2="720" stroke-dasharray="6 6"/>
            <circle cx="300" cy="340" r="142"/>
          </g>
          <path d="M168 355 Q300 412 432 350 Q300 448 168 355 Z" fill="#A8A29E" fill-opacity="0.34" stroke="#D6D3D1" stroke-width="2.5"/>
          <text x="300" y="655" text-anchor="middle" fill="rgba(255,255,255,0.52)" font-family="sans-serif" font-size="22" letter-spacing="3">{lbl}</text>
        </svg>"""
    elif variant in ("raw1", "raw2", "raw3"):
        palettes = {
            "raw1": ("#1E293B", "#0F172A", "#F5C451", "#38BDF8"),
            "raw2": ("#1F242D", "#111318", "#34D399", "#FDE68A"),
            "raw3": ("#271A24", "#130D14", "#FF4D5E", "#F5C451"),
        }
        c1, c2, acc1, acc2 = palettes.get(variant, palettes["raw1"])
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640">
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="{c1}"/>
              <stop offset="100%" stop-color="{c2}"/>
            </linearGradient>
            <radialGradient id="orb" cx="62%" cy="34%" r="54%">
              <stop offset="0%" stop-color="{acc1}" stop-opacity="0.52"/>
              <stop offset="55%" stop-color="{acc2}" stop-opacity="0.16"/>
              <stop offset="100%" stop-color="{c2}" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <rect width="640" height="640" fill="url(#g)"/>
          <rect width="640" height="640" fill="url(#orb)"/>
          <circle cx="320" cy="276" r="118" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.22)" stroke-width="2"/>
          <path d="M110 520 C210 410, 340 430, 530 340 L530 560 L110 560 Z" fill="rgba(255,255,255,0.08)"/>
          <g stroke="rgba(255,255,255,0.34)" stroke-width="2" fill="none">
            <path d="M44 84 L44 44 L84 44"/>
            <path d="M596 84 L596 44 L556 44"/>
            <path d="M44 556 L44 596 L84 596"/>
            <path d="M596 556 L596 596 L556 596"/>
          </g>
        </svg>"""
    else:
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 920">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#0F2942"/>
              <stop offset="48%" stop-color="#0B192C"/>
              <stop offset="100%" stop-color="#060D18"/>
            </linearGradient>
            <radialGradient id="glow" cx="54%" cy="38%" r="58%">
              <stop offset="0%" stop-color="#7DD3FC" stop-opacity="0.46"/>
              <stop offset="52%" stop-color="#34D399" stop-opacity="0.18"/>
              <stop offset="100%" stop-color="#060D18" stop-opacity="0"/>
            </radialGradient>
            <linearGradient id="pearl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#FFFFFF"/>
              <stop offset="100%" stop-color="#E0F2FE"/>
            </linearGradient>
          </defs>
          <rect width="800" height="920" fill="url(#bg)"/>
          <rect width="800" height="920" fill="url(#glow)"/>
          <g stroke="rgba(125,211,252,0.20)" stroke-width="1.5" fill="none">
            <circle cx="400" cy="410" r="220"/>
            <circle cx="400" cy="410" r="168" stroke-dasharray="8 8"/>
            <line x1="120" y1="410" x2="680" y2="410"/>
            <line x1="400" y1="140" x2="400" y2="680"/>
          </g>
          <path d="M210 402 Q400 508 590 402 Q400 562 210 402 Z" fill="url(#pearl)" fill-opacity="0.92"/>
          <circle cx="515" cy="340" r="8" fill="#FFFFFF"/>
          <path d="M515 316 L515 364 M491 340 L539 340" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round"/>
        </svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def image_to_safe_data_url(
    img_source: str | Path | None,
    *,
    fallback_variant: str = "after",
    fallback_label: str = "",
) -> str:
    """
    Converts a local path, `file://` URI, or `data:` URL into an inline base64 data-URL
    so Headless Chrome loads images 100% deterministically with zero path/CORS errors.
    """
    if not img_source:
        return _procedural_studio_svg_data_url(fallback_variant, fallback_label)
    raw = str(img_source).strip()
    if raw.startswith("data:image/"):
        return raw
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("file://"):
        from urllib.parse import unquote, urlparse
        parsed = urlparse(raw)
        candidate = Path(unquote(parsed.path))
    else:
        candidate = Path(raw).expanduser()

    if candidate.is_file():
        mime, _ = mimetypes.guess_type(str(candidate))
        if not mime:
            ext = candidate.suffix.lower()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
            }.get(ext, "image/png")
        b64 = base64.b64encode(candidate.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    return _procedural_studio_svg_data_url(fallback_variant, fallback_label)


# ---------------------------------------------------------------------------
# Deterministic Local @font-face CSS + Common Studio Motion Shell
# ---------------------------------------------------------------------------

def env_font_dirs() -> list[Path]:
    """v7.9.1: `$PFD_FONT_DIR` as a list of dirs (os.pathsep-separated), read at call time; [] when unset."""
    return [Path(d).expanduser() for d in os.environ.get("PFD_FONT_DIR", "").split(os.pathsep) if d.strip()]


@functools.lru_cache(maxsize=1)
def _fc_list_files() -> dict[str, str]:
    """Basename -> path of every font fontconfig knows (`fc-list`); {} without fontconfig. Cached per process."""
    try:  # Popen, not run(): callers that stub subprocess.run for the engine must not see this probe
        with subprocess.Popen(["fc-list", "--format", "%{file}\n"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                              encoding="utf-8", errors="replace") as proc:
            try:
                stdout, _ = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                return {}
    except (OSError, subprocess.SubprocessError):
        return {}
    out: dict[str, str] = {}
    for line in sorted((stdout or "").splitlines()):
        f = line.strip()
        if f:
            out.setdefault(Path(f).name, f)
    return out


def find_font_file(name: str, extra_dirs: Sequence[Path] = ()) -> Path | None:
    """First existing `name` in `$PFD_FONT_DIR`, then `FONT_ROOTS_TNEDIT`, then `extra_dirs`, then any fontconfig file with that
    name (`fc-list`); None when not installed (never a download)."""
    for root in [*env_font_dirs(), *FONT_ROOTS_TNEDIT, *extra_dirs]:
        cand = root / name
        if cand.is_file():
            return cand
    hit = _fc_list_files().get(name)
    return Path(hit) if hit and Path(hit).is_file() else None


def _tnedit_font(name: str) -> Path:
    """v7.9.0: a TNEDIT file that is not installed falls back to the same file in FONT_ROOT_BASE. Before, a missing folder left only the
    500 face (Inter-Medium) registered for 'Be Vietnam Pro', so every 600-800 line rendered as faux-bold Inter."""
    return find_font_file(name, (FONT_ROOT_BASE,)) or FONT_ROOTS_TNEDIT[0] / name


def _font_file(root: Path, name: str) -> Path:
    """v7.9.1: `name` in `$PFD_FONT_DIR`, then the optional user folder `root`, then `find_font_file` (TNEDIT dirs, fontconfig)."""
    for d in (*env_font_dirs(), root):
        if (d / name).is_file():
            return d / name
    return find_font_file(name) or root / name


_WARNED_FONTS: set[str] = set()


def _font_uri(path: Path) -> str:
    """file:// URI of an installed font; "" plus a loud (once per file) warning when it is missing."""
    if path.is_file():
        return path.as_uri()
    if str(path) not in _WARNED_FONTS:
        _WARNED_FONTS.add(str(path))
        warnings.warn(f"FONT NOT FOUND: {path.name} (looked in $PFD_FONT_DIR, {path.parent} and fontconfig): its @font-face is "
                      "skipped and Chrome falls back to another face. Install it or set PFD_FONT_DIR.", stacklevel=2)
    return ""


def build_font_face_css() -> str:
    """
    Maps verified local `.ttf`/`.otf` font files directly via `file://` URIs so Chrome
    never falls back to wrong fontconfig aliases (such as SVN-Helvetica masquerading as Be Vietnam Pro).
    """
    rules: list[str] = []

    def add_face(family: str, file_path: Path, weight: str = "400", style: str = "normal") -> None:
        uri = _font_uri(file_path)
        if not uri:
            return
        ext = file_path.suffix.lower()
        fmt = "opentype" if ext == ".otf" else "truetype"
        rules.append(
            f"@font-face {{ font-family: '{family}'; src: url('{uri}') format('{fmt}'); "
            f"font-weight: {weight}; font-style: {style}; font-display: block; }}"
        )

    # Be Vietnam Pro (Full clean Vietnamese diacritic geometry)
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-ExtraLight.ttf"), "200", "normal")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-Light.ttf"), "300 400", "normal")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-Italic.ttf"), "400", "italic")
    add_face("Be Vietnam Pro", _font_file(FONT_ROOT_BASE, "Inter-Medium.ttf"), "500", "normal")
    # Also register dedicated Be Vietnam Pro Bold/ExtraBold/Black
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-Bold.ttf"), "600 700", "normal")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-BoldItalic.ttf"), "600 700", "italic")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-ExtraBold.ttf"), "800", "normal")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-ExtraBoldItalic.ttf"), "800", "italic")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-Black.ttf"), "900", "normal")
    add_face("Be Vietnam Pro", _tnedit_font("BeVietnamPro-BlackItalic.ttf"), "900", "italic")

    # Playfair Display (Editorial Luxury Serif & Swash Italic)
    add_face("Playfair Display", _tnedit_font("PlayfairDisplay[wght].ttf"), "400 900", "normal")
    add_face("Playfair Display", _tnedit_font("PlayfairDisplay-Italic[wght].ttf"), "400 900", "italic")
    add_face("Playfair Display", _font_file(FONT_ROOT_BASE, "PlayfairDisplay-BoldItalic.ttf"), "700", "italic")

    # SVN-Aaron Script (Signature Vietnamese Calligraphy)
    add_face("SVN-Aaron Script", _tnedit_font("SVN-Aaron Script.otf"), "400 700", "normal")
    add_face("SVN-Aaron Script", _tnedit_font("SVN-Aaron Script.otf"), "400 700", "italic")

    # DFVN West West (Condensed Editorial Display)
    add_face("DFVN West West", _tnedit_font("DFVN West West Condensed.ttf"), "400 800", "normal")

    # Inter & Montserrat
    add_face("Inter", _tnedit_font("Inter[opsz,wght].ttf"), "100 900", "normal")
    add_face("Inter", _tnedit_font("Inter-Italic[opsz,wght].ttf"), "100 900", "italic")
    add_face("Montserrat", _font_file(FONT_ROOT_MONT, "Montserrat-Medium.ttf"), "400 500", "normal")
    add_face("Montserrat", _font_file(FONT_ROOT_MONT, "Montserrat-ExtraBold.ttf"), "700 800", "normal")
    add_face("Montserrat", _font_file(FONT_ROOT_MONT, "Montserrat-Black.otf"), "900", "normal")

    # Studio Monospace
    add_face("Studio Mono", _font_file(FONT_ROOT_MONO, "LigaSFMonoNerdFont-Bold.otf"), "600 700", "normal")
    add_face("Studio Mono", _font_file(FONT_ROOT_MONO, "LigaSFMonoNerdFont-LightItalic.otf"), "400", "italic")

    return "\n".join(rules)


def render_swash_hybrid_html_py(
    text: str,
    rest_font_family: str = "'Playfair Display', 'Be Vietnam Pro', Georgia, serif",
) -> str:
    """
    `@__dviet` Swash-Initial Hybrid Trick (#05/#06/#07/#08):
    If `text[0]` is an ASCII letter, wraps `text[0]` in ornate 'SVN-Aaron Script' / 'Playfair Display'
    italic 1.48em swash span and `text[1:]` in 'Playfair Display' Bold Italic / 'Be Vietnam Pro' Bold Italic
    so stacked Vietnamese NFC diacritics remain 100% legible.
    """
    clean = nfc(text)
    if not clean:
        return ""
    first = clean[0]
    rest = clean[1:]
    if first.isascii() and first.isalpha():
        return (
            f'<span class="swash-hybrid-init" style="display:inline-block;'
            f"font-family:'SVN-Aaron Script','Playfair Display',serif;font-style:italic;"
            f'font-weight:400;font-size:1.48em;line-height:0.84;margin-right:0.018em;'
            f'transform:translateY(0.03em) rotate(-1.5deg);">{esc(first)}</span>'
            f'<span class="swash-hybrid-rest" style="font-family:{rest_font_family};'
            f'font-style:italic;font-weight:700;">{esc(rest)}</span>'
        )
    return (
        f'<span class="swash-hybrid-rest" style="font-family:{rest_font_family};'
        f'font-style:italic;font-weight:700;">{esc(clean)}</span>'
    )


# v7.7.0 glow scale token: multiplies every `halationPulse` (hence every glow text-shadow blur). 1.0 = existing output.
# Override per process with env `PFD_GLOW_SCALE` or by assigning this module constant before building plates.
GLOW_SCALE: float = float(os.environ.get("PFD_GLOW_SCALE", "1.0"))
PAGE_LINE_GUARD = True  # v7.9.0 repair: the page-wide word-gap guard on every text line (False only for the tests' control renders)

COMMON_STUDIO_JS = r"""
// Cubic-Bezier solver (Newton-Raphson)
function solveCubicBezier(p1x, p1y, p2x, p2y, x) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const cx = 3 * p1x;
  const bx = 3 * (p2x - p1x) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * p1y;
  const by = 3 * (p2y - p1y) - cy;
  const ay = 1 - cy - by;
  const sampleX = (t) => ((ax * t + bx) * t + cx) * t;
  const sampleDerivX = (t) => (3 * ax * t + 2 * bx) * t + cx;
  const sampleY = (t) => ((ay * t + by) * t + cy) * t;

  let t = x;
  for (let i = 0; i < 8; i++) {
    const dx = sampleX(t) - x;
    if (Math.abs(dx) < 1e-6) break;
    const d = sampleDerivX(t);
    if (Math.abs(d) < 1e-6) break;
    t -= dx / d;
  }
  t = Math.max(0, Math.min(1, t));
  return sampleY(t);
}

// @__dviet Video #08 `Máy phát nhạc 3` exact snap curve: cubic-bezier(0.05, 0.92, 0.12, 1.00)
function player3Snap(u) {
  return solveCubicBezier(0.05, 0.92, 0.12, 1.00, Math.max(0, Math.min(1, u)));
}

// Velvet C2 Air-Cushion curve: cubic-bezier(0.16, 1.0, 0.30, 1.0)
function velvetC2(u) {
  return solveCubicBezier(0.16, 1.0, 0.30, 1.0, Math.max(0, Math.min(1, u)));
}

function airCushion(t) {
  return velvetC2(t);
}

function easeOutBack(u, s = 1.12) {
  if (u <= 0) return 0;
  if (u >= 1) return 1;
  const t = u - 1;
  return 1 + (s + 1) * t * t * t + s * t * t;
}

// Glow-2 optical halation envelope: 4f attack -> 1.45x peak, 28f decay -> 0.85x steady.
// v7.7.0: one global glow scale (default 1 = unchanged); a page can set window.__GLOW_SCALE (e.g. 0.5 = tight V21-style halo).
function halationPulse(u) {
  return (window.__GLOW_SCALE ?? __GLOW_SCALE_DEFAULT__) * halationPulse0(u);
}
function halationPulse0(u) {
  if (u <= 0) return 0;
  const attackEnd = 4 / 32;
  if (u <= attackEnd) {
    return 1.45 * (u / attackEnd);
  }
  if (u >= 1) return 0.85;
  return 1.45 + (0.85 - 1.45) * velvetC2((u - attackEnd) / (1 - attackEnd));
}

// Vietnamese NFC Grapheme Segmenter so stacked diacritics (ộ, ệ, ữ, ắ, ẳ) NEVER split
const __viSegmenter =
  typeof Intl !== "undefined" && typeof Intl.Segmenter === "function"
    ? new Intl.Segmenter("vi", { granularity: "grapheme" })
    : null;

function splitGraphemesVi(str) {
  const s = String(str ?? "").normalize("NFC");
  if (__viSegmenter) {
    return Array.from(__viSegmenter.segment(s), (item) => item.segment);
  }
  return Array.from(s);
}

function escapeHtmlJs(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// @__dviet Swash-Initial Hybrid Trick (#05/#06/#07/#08)
function renderSwashHybridHtml(
  text,
  restFontFamily = "'Playfair Display', 'Be Vietnam Pro', Georgia, serif"
) {
  const graphemes = splitGraphemesVi(text);
  if (graphemes.length === 0) return "";
  const first = graphemes[0];
  const rest = graphemes.slice(1).join("");
  if (/^[A-Za-z]$/.test(first)) {
    return (
      `<span class="swash-hybrid-init" style="display:inline-block;font-family:'SVN-Aaron Script','Playfair Display',serif;font-style:italic;font-weight:400;font-size:1.48em;line-height:0.84;margin-right:0.018em;transform:translateY(0.03em) rotate(-1.5deg);">${escapeHtmlJs(first)}</span>` +
      `<span class="swash-hybrid-rest" style="font-family:${restFontFamily};font-style:italic;font-weight:700;">${escapeHtmlJs(rest)}</span>`
    );
  }
  return `<span class="swash-hybrid-rest" style="font-family:${restFontFamily};font-style:italic;font-weight:700;">${escapeHtmlJs(graphemes.join(""))}</span>`;
}

// Universal real-second timestamp progress (`tSec = frameIdx / fps`, NOT clip-percentage)
function resolveSceneTimeSec(frameIdx, totalFrames, fps, stillHeroSec = 2.4) {
  const safeFps = Math.max(1, Number(fps) || 60);
  if (totalFrames <= 1) return stillHeroSec;
  return Number(frameIdx) / safeFps;
}

function timeProgress(tSec, startSec, durSec = 0.26, easeFn = player3Snap) {
  const dur = Number(durSec);
  if (!(dur > 1e-6)) return tSec >= Number(startSec) ? 1 : 0;
  const raw = (tSec - Number(startSec)) / dur;
  if (raw <= 0) return 0;
  if (raw >= 1) return 1;
  return typeof easeFn === "function" ? easeFn(raw) : raw;
}

// Settled text gentle micro-float + scale creep so plates NEVER freeze dead
function applyHoldMicroFloat(el, tSec, birthSec, ampY = 4.5, scaleCreep = 0.024) {
  if (!el) return { dy: 0, scale: 1 };
  const age = Math.max(0, tSec - Number(birthSec || 0));
  if (age <= 0) return { dy: 0, scale: 1 };
  const ramp = Math.min(1, age / 0.32);
  const dy = -Math.sin(age * 2.45) * ampY * ramp;
  const sc = 1 + (Math.min(1, age / 3.0) * scaleCreep + 0.0035 * Math.sin(age * 1.85)) * ramp;
  const tx = `translate3d(0, ${dy.toFixed(2)}px, 0) scale(${sc.toFixed(4)})`;
  el.style.transform = el.style.transform ? `${el.style.transform} ${tx}` : tx;
  return { dy, scale: sc };
}

// Smooth optical blur + upward/fade cushion exit at end of clip
function applyCleanExit(el, tSec, clipDurSec, exitDurSec = 0.14) {
  if (!el || !(clipDurSec > exitDurSec * 1.6) || !(exitDurSec > 0)) return 1;
  const exitStart = clipDurSec - exitDurSec;
  if (tSec <= exitStart) return 1;
  const u = Math.max(0, Math.min(1, (tSec - exitStart) / exitDurSec));
  const e = solveCubicBezier(0.38, 0.0, 1.0, 1.0, u);
  const remain = Math.max(0, 1 - e);
  const curOp = Number.parseFloat(el.style.opacity || "1");
  el.style.opacity = String(((Number.isFinite(curOp) ? curOp : 1) * remain).toFixed(4));
  const tx = `translate3d(0, ${(-16 * e).toFixed(2)}px, 0) scale(${(1 - 0.028 * e).toFixed(4)})`;
  el.style.transform = el.style.transform ? `${el.style.transform} ${tx}` : tx;
  const blurStr = `blur(${(5.5 * e).toFixed(2)}px)`;
  el.style.filter = el.style.filter && el.style.filter !== "none"
    ? `${el.style.filter} ${blurStr}`
    : blurStr;
  return remain;
}

function segProgress(normT, start, end) {
  if (end <= start) return normT >= start ? 1 : 0;
  return airCushion((normT - start) / (end - start));
}

// v7.9.0 entrance word-spacing guard. `entranceWordSpacingEm` is the JS mirror of motion_gate.entrance_word_spacing_em (the tests
// compare both): extra word spacing (em of the unscaled font) = max(0, MIN_EM + 2 blur / (s font) + shift / font - natural gap).
// Every [data-ws-nat0] line (resting ink gap at letter-spacing 0, measured in Python) gets it on every frame from its current
// screen-space blur (own + ancestor `filter: blur()`, each times that element's screen scale), screen scale and letter-spacing, so
// the gap stays >= 0.25 em while blurred and eases back to the natural spacing exactly as the blur reaches 0.
const __WORD_GAP_MIN_EM = __WORD_GAP_MIN_EM_VALUE__;
function entranceWordSpacingEm(blurPx, scale, fontPx, naturalGapEm, shiftPx = 0) {
  const s = Math.max(Number(scale) || 1, 1e-3);
  const f = Math.max(Number(fontPx) || 1, 1e-3);
  const need = __WORD_GAP_MIN_EM + 2 * Math.max(0, Number(blurPx) || 0) / (s * f) + Math.max(0, Number(shiftPx) || 0) / f;
  return Math.max(0, Math.ceil((need - Number(naturalGapEm)) * 1e4 - 1e-6) / 1e4);
}
function __screenScale(el) {
  let m = new DOMMatrix();
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const t = getComputedStyle(n).transform;
    if (t && t !== "none") m = new DOMMatrix(t).multiply(m);
  }
  let s = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  const r = el.getBoundingClientRect();
  if (el.offsetWidth > 0 && el.offsetHeight > 0) s = Math.min(s, r.width / el.offsetWidth, r.height / el.offsetHeight);
  return s;
}
function __filterBlurPx(el) {
  const f = getComputedStyle(el).filter;
  if (!f || f === "none") return 0;
  let s = 0;
  for (const m of f.matchAll(/blur\(\s*([\d.]+)px\s*\)/g)) s += Number(m[1]);
  return s;
}
function wordGapGuardLine(el) {
  const nat0 = Number(el.dataset.wsNat0);
  if (!Number.isFinite(nat0)) return 0;
  const cs = getComputedStyle(el);
  const f = parseFloat(cs.fontSize) || 1;
  const ls = cs.letterSpacing === "normal" ? 0 : (parseFloat(cs.letterSpacing) || 0) / f;
  let blur = 0;
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const b = __filterBlurPx(n);
    if (b) blur += b * __screenScale(n);
  }
  const ws = entranceWordSpacingEm(blur, __screenScale(el), f, nat0 + 2 * ls);
  el.style.wordSpacing = `${ws.toFixed(4)}em`;
  document.querySelectorAll(`[data-ws-follow="${el.id}"]`).forEach((g) => { g.style.wordSpacing = el.style.wordSpacing; });
  return ws;
}
function applyWordGapGuard() {
  document.querySelectorAll("[data-ws-nat0]").forEach((el) => wordGapGuardLine(el));
  if (__PFD_LINE_GUARD) __pfdLineRoots().forEach((el) => __pfdLineGapGuard(el));
}

// v7.9.0 repair (2026-11-26): EVERY other drawn text line of EVERY template is guarded too (entrance, hold and the applyCleanExit
// blur): a line = the nearest non-inline ancestor of a non-empty text node (SVG: its <text>), minus the [data-ws-nat0] /
// [data-pfd-line] lines (own guards above), [data-pfd-glow] bloom copies and [data-ws-follow] copies (they take their leader's
// spacing; the leader counts their blur). Each frame the line goes back to its template word-spacing, its narrowest adjacent-word
// INK gap is measured in the DOM (same metric as the engine probe: range boxes + canvas ink bounds, along the path for text on a
// path), and the spaces widen by `entranceWordSpacingEm(blur per neighbour, screen scale, font, measured gap)` - so the gap is
// >= 0.25 em at rest too and eases back to that resting value as the blur reaches 0.
const __PFD_LINE_GUARD = __PFD_LINE_GUARD_VALUE__;
let __pfdGuardCtx = null;  // created on first use (the script is also evaluated outside a page, in node)
function __pfdLineRootOf(node) {
  let n = node.parentElement;
  if (!n || !node.textContent.trim() || n.closest("script, style, title, defs, noscript, template")) return null;
  if (n instanceof SVGElement) return n.closest("text") || n;
  while (n.parentElement && n !== document.body && getComputedStyle(n).display.startsWith("inline")) n = n.parentElement;
  return n;
}
function __pfdLineRoots() {
  const set = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const r = __pfdLineRootOf(node);
    if (r && !r.closest("[data-pfd-glow], [data-ws-nat0], [data-pfd-line], [data-ws-follow]")) set.add(r);
  }
  return Array.from(set);
}
// screen scale of an element: its transform chain, capped by its drawn box / FRACTIONAL layout box (offsetWidth is rounded)
function __pfdGuardScale(el) {
  let m = new DOMMatrix();
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const t = getComputedStyle(n).transform;
    if (t && t !== "none") m = new DOMMatrix(t).multiply(m);
  }
  const ms = el instanceof SVGElement ? null : Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  let bs = null;
  if (el instanceof SVGElement) {
    let bb = null;
    try { bb = el.getBBox(); } catch (e) { bb = null; }
    const r = el.getBoundingClientRect();
    if (bb && bb.width > 0 && bb.height > 0) bs = Math.min(r.width / bb.width, r.height / bb.height);
  } else {
    for (let n = el; n && n.nodeType === 1 && !(n instanceof SVGElement); n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (!cs.width.endsWith("px") || !cs.height.endsWith("px")) continue;
      let w = parseFloat(cs.width), h = parseFloat(cs.height);
      if (cs.boxSizing !== "border-box") {
        const px = (k) => parseFloat(cs[k]) || 0;
        w += px("paddingLeft") + px("paddingRight") + px("borderLeftWidth") + px("borderRightWidth");
        h += px("paddingTop") + px("paddingBottom") + px("borderTopWidth") + px("borderBottomWidth");
      }
      if (!(w > 0) || !(h > 0) || Math.abs(w - n.offsetWidth) > 1 || Math.abs(h - n.offsetHeight) > 1) break;
      const rr = n.getBoundingClientRect();
      bs = Math.min(rr.width / w, rr.height / h);
      break;
    }
  }
  if (ms == null) return bs == null ? 1 : bs;
  return bs == null ? ms : Math.min(ms, bs);
}
function __pfdChainBlurPx(el) {
  let b = 0;
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const v = __filterBlurPx(n); if (v) b += v * __pfdGuardScale(n); }
  return b;
}
function __pfdInk(el, ch) {
  if (!__pfdGuardCtx) __pfdGuardCtx = document.createElement("canvas").getContext("2d");
  const cs = getComputedStyle(el);
  __pfdGuardCtx.font = cs.fontStyle + " " + cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
  if ("letterSpacing" in __pfdGuardCtx) __pfdGuardCtx.letterSpacing = "0px";
  const m = __pfdGuardCtx.measureText(ch);
  return { l: m.actualBoundingBoxLeft, r: m.actualBoundingBoxRight };
}
function __pfdLineDeficitPx(root, chars, copyBlur) {
  // widest extra word spacing (px of the space's own CSS box) any adjacent-word pair of `root` still needs on this frame
  const rect = (c) => { const r = document.createRange(); r.setStart(c.node, c.i); r.setEnd(c.node, c.i + c.g.length); return r.getBoundingClientRect(); };
  let addPx = 0;
  for (let k = 1; k < chars.length - 1; k++) {
    if (!chars[k].space || chars[k - 1].space) continue;
    let j = k; while (j < chars.length && chars[j].space) j++;
    if (j >= chars.length) break;
    const a = chars[k - 1], b = chars[j], sp = chars[k];
    const ra = rect(a), rb = rect(b);
    if (Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top) < 0.5 * Math.min(ra.height, rb.height)) continue;  // line break
    let sa = __pfdGuardScale(a.host), sb = __pfdGuardScale(b.host), ss = __pfdGuardScale(sp.host);
    const ia = __pfdInk(a.host, a.g), ib = __pfdInk(b.host, b.g);
    let gap = (rb.left - ib.l * sb) - (ra.left + ia.r * sa);
    if (a.host === b.host && a.node === b.node && a.host instanceof SVGTextContentElement && typeof a.host.getSubStringLength === "function") {
      const ctm = a.host.getScreenCTM();
      sa = sb = ss = ctm ? Math.sqrt(Math.abs(ctm.a * ctm.d - ctm.b * ctm.c)) : 1;
      gap = ((a.host.getSubStringLength(0, b.i) - ib.l) - (a.host.getSubStringLength(0, a.i) + ia.r)) * sa;
    }
    const blur = Math.max(__pfdChainBlurPx(a.host) + __pfdChainBlurPx(b.host), 2 * copyBlur);
    const fa = parseFloat(getComputedStyle(a.host).fontSize) || 1, fb = parseFloat(getComputedStyle(b.host).fontSize) || 1;
    const f = Math.max(fa, fb), s = Math.max(sa * fa, sb * fb) / f;
    const em = entranceWordSpacingEm(blur / 2, s, f, gap / (s * f));  // the ONE helper: extra em of the unscaled font
    if (em > 0 && ss > 0) addPx = Math.max(addPx, em * f * s / ss);
  }
  return addPx;
}
function __pfdLineGapGuard(root) {
  const follow = root.id ? Array.from(document.querySelectorAll(`[data-ws-follow="${root.id}"]`)) : [];
  if (root.dataset.wsBase === undefined) root.dataset.wsBase = root.style.wordSpacing || "";
  const set = (px) => {
    const ws = px > 0 ? `calc(${root.dataset.wsBase || "0px"} + ${px.toFixed(3)}px)` : root.dataset.wsBase;
    root.style.wordSpacing = ws;
    follow.forEach((g) => { g.style.wordSpacing = ws; });
  };
  set(0);
  const copyBlur = follow.reduce((m, g) => Math.max(m, __pfdChainBlurPx(g)), 0);  // an echo copy is blurred on its own
  const chars = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (__pfdLineRootOf(node) !== root) continue;
    const seg = typeof Intl !== "undefined" && Intl.Segmenter ? Array.from(new Intl.Segmenter("vi", { granularity: "grapheme" }).segment(node.textContent), (x) => [x.index, x.segment]) : Array.from(node.textContent).map((c, i) => [i, c]);
    for (const [i, g] of seg) chars.push({ node, i, g, host: node.parentElement, space: /^\s+$/.test(g) });
  }
  // a rotated / skewed ancestor is measured as its pure scale (as the probe does): the gap runs along the line, not the screen x
  const derot = [];
  for (let n = root; n && n.nodeType === 1; n = n.parentElement) {
    const t = getComputedStyle(n).transform;
    if (!t || t === "none") continue;
    const m = new DOMMatrix(t);
    if (Math.abs(m.b) < 1e-6 && Math.abs(m.c) < 1e-6) continue;
    const k = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
    derot.push([n, n.style.transform]);
    n.style.transform = "matrix(" + k + ",0,0," + k + "," + m.e + "," + m.f + ")";
  }
  let addPx = 0;
  try {
    for (let it = 0; it < 4; it++) {  // the gap is re-measured after each widening (sub-pixel layout, scale read from the box)
      const d = __pfdLineDeficitPx(root, chars, copyBlur);
      if (!(d > 0.004)) break;
      addPx += d + 0.01;
      set(addPx);
    }
  } finally {
    for (const [n, t] of derot.reverse()) n.style.transform = t;
  }
  return addPx;
}

function applyOptionalPillEntrance(tSec, badgeAtSec, durSec = 0.22) {
  const pill = document.getElementById("ktOptPill");
  if (!pill) return;
  const pP = timeProgress(tSec, badgeAtSec, durSec, velvetC2);
  pill.style.opacity = String(pP.toFixed(4));
  pill.style.visibility = pP > 0.002 ? "visible" : "hidden";
  pill.style.transform = `translate3d(0, ${((1 - pP) * 14).toFixed(2)}px, 0)`;
}
"""


def studio_common_js() -> str:
    """`COMMON_STUDIO_JS` with the module constant `GLOW_SCALE` substituted as the `window.__GLOW_SCALE ?? <default>` fallback."""
    return (COMMON_STUDIO_JS.replace("__GLOW_SCALE_DEFAULT__", f"{float(GLOW_SCALE):g}")
            .replace("__WORD_GAP_MIN_EM_VALUE__", f"{float(WORD_GAP_MIN_EM):g}")
            .replace("__PFD_LINE_GUARD_VALUE__", "true" if PAGE_LINE_GUARD else "false"))


def wrap_studio_document(
    *,
    width: int,
    height: int,
    extra_css: str,
    body_html: str,
    frame_js: str,
    theme: str = "dark",
) -> str:
    font_css = build_font_face_css()
    body_color = "#14171F" if nfc(theme).strip().lower() == "light" else "#FAFAFA"
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<style>
{font_css}

*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: antialiased;
  text-rendering: geometricPrecision;
}}

html, body {{
  width: {width}px;
  height: {height}px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0) !important;
  font-family: 'Be Vietnam Pro', 'Inter', sans-serif;
  color: {body_color};
}}

.stage-root {{
  position: relative;
  width: {width}px;
  height: {height}px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
}}

{extra_css}
</style>
</head>
<body>
<div class="stage-root" id="stageRoot">
{body_html}
</div>
<script>
{studio_common_js()}
{frame_js}
// v7.9.0: every frame ends with the entrance word-spacing guard (no-op without [data-ws-nat0] lines)
if (typeof window.__setFrame === "function") {{
  const __pfdSetFrame = window.__setFrame;
  window.__setFrame = function(...args) {{
    const r = __pfdSetFrame.apply(this, args);
    applyWordGapGuard();
    return r;
  }};
  applyWordGapGuard();
}}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Template 1: `dviet_overlapping_feather_cluster` (Video #10 + #08 + #14)
# ---------------------------------------------------------------------------

def _build_dviet_overlapping_feather_cluster(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold")
    kicker = nfc(props.get("kicker", "BÍ MẬT DỰNG PHIM TRIỆU VIEW"))
    main_text = nfc(props.get("main_text", "CHUYỂN ĐỘNG MƯỢT"))
    accent_text = nfc(props.get("accent_text", "Chuẩn Điện Ảnh"))
    badge_text = nfc(props.get("badge_text", ""))
    accent_font_key = nfc(props.get("accent_font", "playfair")).lower()
    swash_dropcap = bool(props.get("swash_dropcap", True))
    align = nfc(props.get("align", "center")).lower()

    main_len = max(1, len(main_text))
    auto_main = min(118, max(68, int((width * 0.84) / max(7.2, main_len * 0.58))))
    main_size = int(props.get("main_size") or auto_main)
    # Strict 1 : 3.2 scale between parasitic kicker and main ExtraBold hero block
    kicker_size = int(props.get("kicker_size") or secondary_text_px(props))  # v7.9.0: 70 px secondary (was main / 3.2, 21-37 px)
    acc_len = max(1, len(accent_text))
    auto_acc = min(round(main_size * 0.88), int((width * 0.86) / max(7.0, acc_len * 0.48)))
    accent_size = int(props.get("accent_size") or max(secondary_text_px(props), auto_acc))
    nowrap_hero = "nowrap" if main_len <= 24 and "\n" not in main_text else "normal"
    nowrap_acc = "nowrap" if acc_len <= 26 and "\n" not in accent_text else "normal"

    is_script = accent_font_key in ("aaron", "script", "svn-aaron", "svn-aaron script")
    accent_font_family = (
        "'SVN-Aaron Script', 'Playfair Display', serif"
        if is_script
        else "'Playfair Display', Georgia, serif"
    )
    accent_font_style = "normal" if is_script else "italic"
    accent_font_weight = "400" if is_script else "700"

    if accent_text and swash_dropcap:
        first_ch = esc(accent_text[0])
        rest_ch = esc(accent_text[1:])
        accent_inner_html = (
            f'<span class="swash-cap">{first_ch}</span><span class="accent-rest">{rest_ch}</span>'
        )
    else:
        accent_inner_html = f'<span class="accent-rest">{esc(accent_text)}</span>'

    flex_align = {"left": "flex-start", "right": "flex-end"}.get(align, "center")
    text_align = {"left": "left", "right": "right"}.get(align, "center")

    badge_html = ""
    if badge_text:
        badge_html = f"""
        <div class="glass-pill-badge" id="dvBadge">
          <span class="pill-dot"></span>
          <span class="pill-text">{esc(badge_text)}</span>
        </div>
        """

    kicker_html = ""
    if kicker:
        kicker_html = f"""
        <div class="kicker-row" id="dvKicker">
          <span class="kicker-bar"></span>
          <span class="kicker-label">{esc(kicker)}</span>
        </div>
        """

    css = f"""
    .dviet-cluster {{
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: {flex_align};
      justify-content: center;
      text-align: {text_align};
      max-width: {int(width * 0.94)}px;
      padding: 28px 36px;
    }}

    /* Parasitic Kicker: exact 1 : 3.2 scale, #FAFAFA, anchored < 8px from Main Hero */
    .kicker-row {{
      position: relative;
      z-index: 4;
      display: inline-flex;
      align-items: center;
      gap: 0.22em;
      font-family: 'Be Vietnam Pro', 'Inter', sans-serif;
      font-weight: 500;
      font-size: {kicker_size}px;
      line-height: 1.25;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #FAFAFA;
      padding: 0.32em 0.25em;
      margin-bottom: calc(-0.32em - 0.26em + 5px); /* Tight parasitic gap = 5px (< 8px) */
      text-shadow: 0 4px 18px rgba(0, 0, 0, 0.42);
      will-change: transform, opacity;
    }}

    .kicker-bar {{
      width: 0.42em;
      height: 0.07em;
      border-radius: 99px;
      background: {pal["hex"]};
      box-shadow: 0 0 12px {pal["glow_outer"]};
      flex-shrink: 0;
    }}

    /* Main Hero Block: Be Vietnam Pro ExtraBold, -0.038em, Feather=29 bottom mask, 0px stroke */
    .hero-feather-wrap {{
      position: relative;
      z-index: 2;
      filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.55));
    }}

    .hero-feather-line {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {main_size}px;
      line-height: 1.12;
      letter-spacing: -0.038em;
      white-space: {nowrap_hero};
      color: #FAFAFA;
      -webkit-text-stroke: 0px transparent;
      /* Generous 0.32em x 0.25em padding protects 134/134 NFC diacritics (ộ, ệ, ữ, ắ, ẳ) */
      padding: 0.32em 0.25em;
      -webkit-mask-image: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) 54%,
        rgba(0, 0, 0, 0.06) 96%
      );
      mask-image: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) 54%,
        rgba(0, 0, 0, 0.06) 96%
      );
      will-change: transform, opacity;
    }}

    /* Overlapping Script / Serif Jewel Accent with Swash Drop-Cap + Glow 2 Halation */
    .accent-overlap-line {{
      position: relative;
      z-index: 5;
      font-family: {accent_font_family};
      font-style: {accent_font_style};
      font-weight: {accent_font_weight};
      font-size: {accent_size}px;
      line-height: 1.16;
      white-space: {nowrap_acc};
      letter-spacing: {"0.01em" if is_script else "-0.015em"};
      color: {pal["hex"]};
      padding: 0.32em 0.25em;
      margin-top: calc(-0.66em - 0.22em);
      /* Glow 2 soft optical halation — zero black stroke */
      text-shadow:
        0 0 14px {pal["glow_inner"]},
        0 0 38px {pal["glow_outer"]},
        0 0 74px {pal["glow_ambient"]},
        0 10px 26px rgba(0, 0, 0, 0.56);
      will-change: transform, opacity;
    }}

    .swash-cap {{
      display: inline-block;
      font-family: {accent_font_family};
      font-style: italic;
      font-weight: 700;
      font-size: 1.26em;
      line-height: 1;
      color: {pal["bright"]};
      margin-right: 0.015em;
      transform: translateY(0.02em) rotate(-2deg);
      text-shadow:
        0 0 18px {pal["glow_inner"]},
        0 0 44px {pal["glow_outer"]};
    }}

    .glass-pill-badge {{
      position: relative;
      z-index: 6;
      margin-top: 0;
      display: inline-flex;
      align-items: center;
      gap: 0.2em;
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.78);
      backdrop-filter: blur(20px) saturate(160%);
      -webkit-backdrop-filter: blur(20px) saturate(160%);
      border: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.36),
        0 16px 38px rgba(0, 0, 0, 0.50),
        0 0 24px {pal["glow_ambient"]};
      font-size: {secondary_text_px(props)}px;
      max-width: {width - 80}px;
    }}

    .pill-dot {{
      width: 0.2em;
      height: 0.2em;
      border-radius: 50%;
      background: {pal["hex"]};
      box-shadow: 0 0 12px {pal["hex"]};
      flex-shrink: 0;
    }}

    .pill-text {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {secondary_text_px(props)}px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #F8FAFC;
      padding: 0.12em 0.08em;
      line-height: 1.15;
    }}
    """

    body = f"""
    <div class="dviet-cluster" id="dvCluster">
      {kicker_html}
      <div class="hero-feather-wrap">
        <div class="hero-feather-line" id="dvHero">{esc(main_text)}</div>
      </div>
      <div class="accent-overlap-line" id="dvAccent">{accent_inner_html}</div>
      {badge_html}
    </div>
    """

    js = r"""
    window.__setFrame = function(frameIdx, totalFrames, fps) {
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const pKick = segProgress(norm, 0.00, 0.34);
      const pHero = segProgress(norm, 0.06, 0.48);
      const pAcc  = segProgress(norm, 0.16, 0.64);
      const pBdg  = segProgress(norm, 0.28, 0.76);

      const kick = document.getElementById("dvKicker");
      if (kick) {
        kick.style.opacity = String(pKick);
        kick.style.transform = `translate3d(0, ${(1 - pKick) * 18}px, 0)`;
      }
      const hero = document.getElementById("dvHero");
      if (hero) {
        hero.style.opacity = String(pHero);
        hero.style.transform = `translate3d(0, ${(1 - pHero) * 32}px, 0) scale(${0.94 + 0.06 * pHero})`;
      }
      const acc = document.getElementById("dvAccent");
      if (acc) {
        acc.style.opacity = String(pAcc);
        acc.style.transform = `translate3d(${(1 - pAcc) * -22}px, ${(1 - pAcc) * 20}px, 0) scale(${0.92 + 0.08 * pAcc})`;
      }
      const bdg = document.getElementById("dvBadge");
      if (bdg) {
        bdg.style.opacity = String(pBdg);
        bdg.style.transform = `translate3d(0, ${(1 - pBdg) * 16}px, 0)`;
      }
    };
    window.__setFrame(1, 1, 30);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 2: `frosted_glass_bento_steps` (01 • 02 • 03 Glassmorphism Bento)
# ---------------------------------------------------------------------------

_BENTO_DEMO_STEPS: list[dict[str, str]] = [
    {
        "num": "01",
        "title": "Chẩn Đoán Gốc",
        "desc": "Khóa tỷ lệ & ánh sáng",
        "tag": "NỀN TẢNG",
    },
    {
        "num": "02",
        "title": "Tinh Chỉnh Đa Lớp",
        "desc": "Tách nền, cân sáng",
        "tag": "CỐT LÕI",
    },
    {
        "num": "03",
        "title": "Xuất Bản 4K",
        "desc": "Âm chuẩn -14 LUFS",
        "tag": "HOÀN THIỆN",
    },
]


def _build_frosted_glass_bento_steps(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald")
    theme = nfc(props.get("theme", "dark")).lower()
    is_light = theme == "light"

    kicker = _prop_or_demo("frosted_glass_bento_steps", props, "kicker", "LỘ TRÌNH 3 BƯỚC", required=False)
    title = _prop_or_demo("frosted_glass_bento_steps", props, "title", "Quy Trình Thực Chiến", required=False)
    # v7.9.0: every text >= 66 px on the canvas (secondary 70, titles 84) -> one-column cards, number + tag share the meta row
    sec = secondary_text_px(props)
    ttl = round(sec * 1.2)
    bottom_note = nfc(props.get("bottom_note", ""))
    bottom_note_at_s = float(props.get("bottom_note_at_s", 1.25))
    raw_triggers = props.get("card_triggers_s") or [0.04, 0.30, 0.54]
    card_triggers_s = [float(raw_triggers[i]) if i < len(raw_triggers) else 0.04 + i * 0.26 for i in range(3)]
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    raw_steps = props.get("steps") or (_BENTO_DEMO_STEPS if props.get("demo") else None)
    if not raw_steps:
        raise ValueError("frosted_glass_bento_steps: required prop 'steps' is missing (pass it, or demo=true / --demo for self-test text)")

    steps = list(raw_steps)[:3]
    while len(steps) < 3:
        idx = len(steps) + 1
        steps.append({"num": f"0{idx}", "title": f"Bước 0{idx}", "desc": "", "tag": "CHUẨN"})

    shell_bg = "rgba(248, 250, 252, 0.84)" if is_light else "rgba(18, 20, 26, 0.78)"
    card_bg = "rgba(255, 255, 255, 0.72)" if is_light else "rgba(24, 27, 36, 0.72)"
    border_col = "rgba(15, 23, 42, 0.12)" if is_light else "rgba(255, 255, 255, 0.14)"
    text_main = "#0F172A" if is_light else "#FAFAFA"
    text_sub = "rgba(15, 23, 42, 0.70)" if is_light else "rgba(226, 232, 240, 0.76)"
    muted_num = "rgba(15, 23, 42, 0.24)" if is_light else "rgba(255, 255, 255, 0.22)"

    svg_icons = [
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/></svg>""",
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>""",
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>""",
    ]

    cards_html_parts = []
    for idx, st in enumerate(steps):
        num = esc(st.get("num") or f"0{idx + 1}")
        st_title = esc(st.get("title", ""))
        st_desc = esc(st.get("desc", ""))
        st_tag = esc(st.get("tag", f"BƯỚC 0{idx + 1}"))
        cards_html_parts.append(f"""
        <div class="bento-step-card" id="bentoCard{idx}">
          <div class="card-specular-top"></div>
          <div class="step-meta-row">
            <div class="step-num-ring" id="stepRing{idx}">
              <span class="step-num" id="stepNum{idx}">{num}</span>
            </div>
            <span class="step-tag-pill" id="stepTag{idx}">
              <span class="step-icon">{svg_icons[idx % 3]}</span>
              {st_tag}
            </span>
            <span class="step-status-dot" id="stepDot{idx}"></span>
          </div>
          <div class="step-title">{st_title}</div>
          {f'<div class="step-desc">{st_desc}</div>' if st_desc else ""}
        </div>
        """)

    bottom_note_html = ""
    if bottom_note:
        bottom_note_html = f"""
        <div class="bento-bottom-note" id="bentoBottomNote">{render_swash_hybrid_html_py(bottom_note)}</div>
        """

    css = f"""
    .bento-perspective-stage {{
      perspective: 1300px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .bento-wrapper {{
      position: relative;
      width: {width - 56}px;
      padding: 40px 36px 42px;
      border-radius: 38px;
      background: {shell_bg};
      backdrop-filter: blur(24px) saturate(165%);
      -webkit-backdrop-filter: blur(24px) saturate(165%);
      border: 1px solid {border_col};
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
      overflow: hidden;
      transform-style: preserve-3d;
      will-change: transform, opacity;
    }}

    /* Continuous sweeping specular glass sheen */
    .shell-sheen-sweep {{
      position: absolute;
      top: -35%;
      bottom: -35%;
      width: 38%;
      background: linear-gradient(
        105deg,
        rgba(255, 255, 255, 0.0) 0%,
        rgba(255, 255, 255, 0.09) 48%,
        rgba(255, 255, 255, 0.16) 52%,
        rgba(255, 255, 255, 0.0) 100%
      );
      transform: skewX(-18deg);
      pointer-events: none;
      z-index: 6;
    }}

    /* 1px luminous top specular edge */
    .shell-specular-top {{
      position: absolute;
      top: 0;
      left: 6%;
      right: 6%;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.68), transparent);
      pointer-events: none;
    }}

    /* Contained ambient jewel orb refracting inside frosted shell */
    .ambient-orb-1 {{
      position: absolute;
      width: 360px;
      height: 360px;
      right: -90px;
      top: -90px;
      border-radius: 50%;
      background: radial-gradient(circle, {pal["glow_outer"]} 0%, transparent 70%);
      filter: blur(26px);
      pointer-events: none;
      z-index: 0;
    }}

    .bento-header {{
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin-bottom: 26px;
    }}

    .header-top-rail {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px 20px;
    }}

    .bento-kicker {{
      font-size: {sec}px;
      line-height: 1.15;
      font-weight: 600;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: {pal["hex"]};
      padding: 0.20em 0.10em;
    }}

    .rail-steps-indicator {{
      display: inline-flex;
      align-items: center;
      gap: 0.18em;
      padding: 0.04em 0.36em;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid {border_col};
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      font-weight: 700;
      color: {text_main};
    }}

    .rail-node {{
      transition: color 0.1s linear;
    }}

    .rail-sep {{
      opacity: 0.36;
    }}

    .bento-main-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {ttl}px;
      line-height: 1.12;
      letter-spacing: -0.028em;
      color: {text_main};
      padding: 0.18em 0.06em;
    }}

    .bento-grid {{
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}

    .bento-step-card {{
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 4px;
      padding: 20px 28px 22px;
      border-radius: 26px;
      background: {card_bg};
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid {border_col};
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
      overflow: hidden;
      will-change: transform, opacity, border-color, box-shadow;
    }}

    .card-specular-top {{
      position: absolute;
      top: 0;
      left: 8%;
      right: 8%;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.42), transparent);
    }}

    .step-num-ring {{
      width: {round(sec * 1.3)}px;
      height: {round(sec * 1.3)}px;
      border-radius: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.04);
      border: 1.5px solid {border_col};
      flex-shrink: 0;
    }}

    .step-num {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {sec}px;
      letter-spacing: -0.03em;
      color: {muted_num};
    }}

    .step-body-col {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .step-meta-row {{
      display: flex;
      align-items: center;
      gap: 22px;
    }}

    .step-meta-row .step-status-dot {{
      margin-left: auto;
    }}

    .step-tag-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.2em;
      padding: 0.02em 0.36em;
      border-radius: 999px;
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      color: {pal["hex"]};
    }}

    .step-icon {{
      width: 0.7em;
      height: 0.7em;
      display: inline-flex;
    }}

    .step-icon svg {{
      width: 0.7em;
      height: 0.7em;
    }}

    .step-status-dot {{
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background: rgba(255,255,255,0.18);
    }}

    .step-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {sec}px;
      line-height: 1.16;
      letter-spacing: -0.02em;
      color: {text_main};
      padding: 0.10em 0.04em;
    }}

    .step-desc {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 400;
      font-size: {sec}px;
      line-height: 1.22;
      color: {text_sub};
      padding: 0.06em 0.04em;
    }}

    .bento-bottom-note {{
      position: relative;
      z-index: 3;
      margin-top: 20px;
      text-align: center;
      font-size: {sec}px;
      line-height: 1.28;
      color: {pal["bright"] if not is_light else pal["deep"]};
      padding: 0.32em 0.25em;
      text-shadow: 0 4px 20px {pal["glow_ambient"]};
    }}
    """

    body = f"""
    <div class="bento-perspective-stage">
      <div class="bento-wrapper" id="bentoShell">
        <div class="shell-specular-top"></div>
        <div class="shell-sheen-sweep" id="bentoSheen"></div>
        <div class="ambient-orb-1" id="bentoOrb"></div>
        <div class="bento-header">
          <div class="header-top-rail">
            <div class="bento-kicker">{esc(kicker)}</div>
          </div>
          <div class="bento-main-title">{esc(title)}</div>
        </div>
        <div class="bento-grid">
          {"".join(cards_html_parts)}
        </div>
        {bottom_note_html}
      </div>
    </div>
    """

    js = f"""
    const ACCENT_HEX = {json.dumps(pal["hex"])};
    const ACCENT_GLOW = {json.dumps(pal["glow_outer"])};
    const ACCENT_BG = {json.dumps(pal["pill_bg"])};
    const ACCENT_BORDER = {json.dumps(pal["pill_border"])};
    const BASE_BORDER = {json.dumps(border_col)};
    const MUTED_NUM = {json.dumps(muted_num)};
    const CARD_TRIGGERS_S = {json.dumps(card_triggers_s)};
    const BOTTOM_NOTE_AT_S = {bottom_note_at_s};
    const EXIT_DUR_S = {exit_dur_s};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, 2.6);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;

      const shellP = timeProgress(tSec, 0.0, 0.34, velvetC2);
      const shell = document.getElementById("bentoShell");
      if (shell) {{
        shell.style.filter = "none";
        const breathRx = Math.sin(tSec * 1.65) * 1.45 * shellP;
        const breathRy = Math.cos(tSec * 1.35) * 1.85 * shellP;
        const breathDy = -Math.sin(tSec * 2.05) * 5.0 * shellP;
        shell.style.opacity = String(shellP);
        shell.style.transform =
          `perspective(1300px) rotateX(${{breathRx.toFixed(2)}}deg) rotateY(${{breathRy.toFixed(2)}}deg) ` +
          `translate3d(0, ${{((1 - shellP) * 34 + breathDy).toFixed(2)}}px, 0) scale(${{(0.96 + 0.04 * shellP).toFixed(4)}})`;
      }}

      const sheen = document.getElementById("bentoSheen");
      if (sheen) {{
        const cyc = (tSec * 0.42) % 1.0;
        const leftPct = -45 + cyc * 190;
        sheen.style.left = `${{leftPct.toFixed(1)}}%`;
      }}

      const orb = document.getElementById("bentoOrb");
      if (orb) {{
        orb.style.transform = `translate3d(${{(Math.sin(tSec * 1.4) * 28).toFixed(1)}}px, ${{(Math.cos(tSec * 1.1) * 22).toFixed(1)}}px, 0)`;
      }}

      for (let i = 0; i < 3; i++) {{
        const trig = CARD_TRIGGERS_S[i] ?? (0.04 + i * 0.26);
        const p = timeProgress(tSec, trig, 0.38, player3Snap);
        const card = document.getElementById("bentoCard" + i);
        const ring = document.getElementById("stepRing" + i);
        const num = document.getElementById("stepNum" + i);
        const dot = document.getElementById("stepDot" + i);
        const rail = document.getElementById("rail" + i);

        if (card) {{
          const floatCardY = p >= 1 ? Math.sin(tSec * 2.2 + i * 0.9) * 2.2 : 0;
          card.style.opacity = String((0.18 + 0.82 * p).toFixed(4));
          card.style.transform = `translate3d(${{((1 - p) * 28).toFixed(2)}}px, ${{((1 - p) * 16 + floatCardY).toFixed(2)}}px, 0)`;
          if (p > 0.30) {{
            card.style.borderColor = ACCENT_BORDER;
            card.style.boxShadow = `0 18px 42px rgba(0,0,0,0.40), 0 0 ${{(28 * p).toFixed(1)}}px ${{ACCENT_BG}}`;
          }} else {{
            card.style.borderColor = BASE_BORDER;
            card.style.boxShadow = "0 14px 34px rgba(0, 0, 0, 0.28)";
          }}
        }}
        if (ring) {{
          ring.style.background = p > 0.2 ? ACCENT_BG : "rgba(255, 255, 255, 0.04)";
          ring.style.borderColor = p > 0.2 ? ACCENT_HEX : BASE_BORDER;
          ring.style.boxShadow = p > 0.2 ? `0 0 ${{(22 * p).toFixed(1)}}px ${{ACCENT_GLOW}}` : "none";
        }}
        if (num) {{
          num.style.color = p > 0.2 ? ACCENT_HEX : MUTED_NUM;
        }}
        if (dot) {{
          dot.style.background = p > 0.35 ? ACCENT_HEX : "rgba(255,255,255,0.18)";
          dot.style.boxShadow = p > 0.35 ? `0 0 12px ${{ACCENT_HEX}}` : "none";
        }}
        if (rail) {{
          rail.style.color = p > 0.25 ? ACCENT_HEX : "inherit";
        }}
      }}

      const noteEl = document.getElementById("bentoBottomNote");
      if (noteEl) {{
        const pNote = timeProgress(tSec, BOTTOM_NOTE_AT_S, 0.34, velvetC2);
        const stop1 = Math.max(0, pNote * 124 - 24);
        const stop2 = Math.min(100, pNote * 124);
        const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{stop1.toFixed(1)}}%, rgba(0,0,0,0) ${{stop2.toFixed(1)}}%)`;
        noteEl.style.opacity = String(pNote.toFixed(4));
        noteEl.style.webkitMaskImage = mask;
        noteEl.style.maskImage = mask;
        noteEl.style.transform = `translate3d(0, ${{((1 - pNote) * 14).toFixed(2)}}px, 0)`;
      }}

      if (shell && totalFrames > 1) {{
        applyCleanExit(shell, tSec, clipDurSec, EXIT_DUR_S);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 3: `clinical_before_after_1_to_28` (Video #02 Asymmetric 1:2.8)
# ---------------------------------------------------------------------------

def _build_clinical_before_after_1_to_28(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "ice_cyan")
    kicker = nfc(props.get("kicker", "ĐỐI CHIẾU LÂM SÀNG"))
    title = nfc(props.get("title", "Kết Quả Phục Hình"))
    before_label = nfc(props.get("before_label", "TRƯỚC"))
    after_label = nfc(props.get("after_label", "SAU"))
    process_label = nfc(props.get("process_label", "TÁI TẠO ĐỘ BÓNG"))
    process_metric = nfc(props.get("process_metric", "99.4%"))
    phases = props.get("phases") or ["QUÉT 3D", "CĂN TỶ LỆ", "HOÀN THIỆN"]
    ratio_text = nfc(props.get("ratio_text", "TỶ LỆ 1 : 2.8"))
    # v7.9.0: every text >= 66 px (secondary 70, title 84); labels sit in the card corners, away from the centred subject
    sec = secondary_text_px(props)
    ttl = round(sec * 1.2)

    before_url = image_to_safe_data_url(
        props.get("before_img"), fallback_variant="before", fallback_label="BEFORE / RAW"
    )
    after_url = image_to_safe_data_url(
        props.get("after_img"), fallback_variant="after", fallback_label="AFTER / STUDIO"
    )

    # Exact 1 : 2.8 visual area hierarchy:
    # After Hero Card: 740 x 800 = 592,000 px^2
    # Before Compact Card: 420 x 504 = 211,680 px^2 -> 592,000 / 211,680 = 2.797 (~1 : 2.80!)
    phases_html = "".join(
        f'<span class="proc-phase">{esc(ph)}</span>' for ph in list(phases)[:3]
    )

    css = f"""
    .clinical-stage {{
      position: relative;
      width: {width - 40}px;
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 20px;
    }}

    .clinical-header {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-left: 8px;
    }}

    .clinical-kicker {{
      font-size: {sec}px;
      line-height: 1.15;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: {pal["hex"]};
      text-shadow: 0 2px 14px rgba(0,0,0,0.45);
      padding: 0.16em 0.08em;
    }}

    .clinical-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {ttl}px;
      line-height: 1.1;
      letter-spacing: -0.03em;
      color: #FAFAFA;
      text-shadow: 0 8px 28px rgba(0,0,0,0.52);
      padding: 0.16em 0.06em;
    }}

    .asymmetric-deck {{
      position: relative;
      width: {width - 80}px;
      height: 856px;
    }}

    /* AFTER / KẾT QUẢ Hero Card (2.8x area dominance) */
    .after-hero-card {{
      position: absolute;
      right: 0;
      bottom: 0;
      width: 740px;
      height: 800px;
      border-radius: 34px;
      overflow: hidden;
      background: #0D131F;
      border: 1.5px solid {pal["pill_border"]};
      box-shadow:
        0 30px 72px rgba(0, 0, 0, 0.65),
        0 0 42px {pal["glow_ambient"]};
      z-index: 2;
      will-change: transform, opacity;
    }}

    .after-hero-card img, .before-raw-card img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}

    .card-vignette {{
      position: absolute;
      inset: 0;
      background: linear-gradient(
        180deg,
        rgba(8, 12, 20, 0.34) 0%,
        rgba(8, 12, 20, 0.0) 30%,
        rgba(8, 12, 20, 0.0) 68%,
        rgba(8, 12, 20, 0.68) 100%
      );
      pointer-events: none;
    }}

    .after-badge {{
      position: absolute;
      top: 22px;
      right: 22px;
      display: inline-flex;
      align-items: center;
      gap: 0.18em;
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: rgba(12, 16, 24, 0.80);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border: 1px solid {pal["hex"]};
      box-shadow: 0 10px 26px rgba(0,0,0,0.45), 0 0 20px {pal["glow_outer"]};
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: {pal["bright"]};
    }}

    .after-badge-dot {{
      width: 0.22em;
      height: 0.22em;
      border-radius: 50%;
      background: {pal["hex"]};
      box-shadow: 0 0 12px {pal["hex"]};
    }}

    /* BEFORE / RAW Compact 1.0x Floating Z-Depth Reference Card */
    .before-raw-card {{
      position: absolute;
      left: 0;
      top: 0;
      width: 420px;
      height: 504px;
      border-radius: 28px;
      overflow: hidden;
      background: #18181B;
      border: 2px solid rgba(255, 255, 255, 0.78);
      box-shadow:
        0 26px 58px rgba(0, 0, 0, 0.72),
        0 0 0 1px rgba(0, 0, 0, 0.35);
      z-index: 4;
      will-change: transform, opacity;
    }}

    .before-badge {{
      position: absolute;
      bottom: 18px;
      left: 18px;
      display: inline-flex;
      align-items: center;
      gap: 0.18em;
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: rgba(15, 17, 22, 0.84);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(255, 255, 255, 0.28);
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #E2E8F0;
    }}

    /* Ratio Telemetry Pill */
    .ratio-stamp {{
      position: absolute;
      right: 22px;
      bottom: 22px;
      z-index: 5;
      padding: 0.06em 0.36em;
      border-radius: 18px;
      background: rgba(18, 20, 26, 0.80);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      color: rgba(248, 250, 252, 0.85);
      box-shadow: 0 16px 36px rgba(0,0,0,0.48);
    }}

    /* Live Process Bar Dock */
    .live-process-dock {{
      position: relative;
      width: {width - 80}px;
      padding: 22px 32px 26px;
      border-radius: 26px;
      background: rgba(18, 20, 26, 0.82);
      backdrop-filter: blur(24px) saturate(160%);
      -webkit-backdrop-filter: blur(24px) saturate(160%);
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.36),
        0 24px 56px rgba(0, 0, 0, 0.56);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .proc-top-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 4px 24px;
    }}

    .proc-label {{
      font-size: {sec}px;
      line-height: 1.15;
      font-weight: 700;
      letter-spacing: 0.03em;
      color: #F8FAFC;
      padding: 0.10em 0.04em;
    }}

    .proc-metric {{
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      font-weight: 700;
      color: {pal["hex"]};
    }}

    .proc-track {{
      position: relative;
      width: 100%;
      height: 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.10);
      overflow: hidden;
    }}

    .proc-fill {{
      height: 100%;
      width: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, {pal["hex"]} 0%, {pal["bright"]} 100%);
      box-shadow: 0 0 20px {pal["glow_outer"]};
      transform-origin: left center;
    }}

    .proc-phases-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0 28px;
      font-size: {sec}px;
      line-height: 1.2;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: rgba(226, 232, 240, 0.68);
    }}
    """

    body = f"""
    <div class="clinical-stage">
      <div class="clinical-header" id="clinHdr">
        <div class="clinical-kicker">{esc(kicker)}</div>
        <div class="clinical-title">{esc(title)}</div>
      </div>

      <div class="asymmetric-deck">
        <div class="after-hero-card" id="afterCard">
          <img src="{after_url}" alt="After Result" />
          <div class="card-vignette"></div>
          <div class="after-badge">
            <span class="after-badge-dot"></span>
            <span>{esc(after_label)}</span>
          </div>
        </div>

        <div class="before-raw-card" id="beforeCard">
          <img src="{before_url}" alt="Before Raw" />
          <div class="card-vignette"></div>
          <div class="before-badge">{esc(before_label)}</div>
        </div>

        <div class="ratio-stamp" id="ratioStamp">{esc(ratio_text)}</div>
      </div>

      <div class="live-process-dock" id="procDock">
        <div class="proc-top-row">
          <span class="proc-label">{esc(process_label)}</span>
          <span class="proc-metric" id="procPct">{esc(process_metric)}</span>
        </div>
        <div class="proc-track">
          <div class="proc-fill" id="procFill"></div>
        </div>
        <div class="proc-phases-row">{phases_html}</div>
      </div>
    </div>
    """

    js = f"""
    const FINAL_METRIC = {json.dumps(process_metric)};
    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const pBefore = segProgress(norm, 0.00, 0.36);
      const pAfter  = segProgress(norm, 0.14, 0.58);
      const pDock   = segProgress(norm, 0.28, 0.72);
      const pBar    = segProgress(norm, 0.22, 0.92);

      const bCard = document.getElementById("beforeCard");
      if (bCard) {{
        bCard.style.opacity = String(pBefore);
        bCard.style.transform = `translate3d(${{(1 - pBefore) * -32}}px, ${{(1 - pBefore) * 20}}px, 0) scale(${{0.94 + 0.06 * pBefore}})`;
      }}
      const aCard = document.getElementById("afterCard");
      if (aCard) {{
        aCard.style.opacity = String(pAfter);
        aCard.style.transform = `translate3d(${{(1 - pAfter) * 34}}px, ${{(1 - pAfter) * 26}}px, 0) scale(${{0.94 + 0.06 * pAfter}})`;
      }}
      const dock = document.getElementById("procDock");
      if (dock) {{
        dock.style.opacity = String(pDock);
        dock.style.transform = `translate3d(0, ${{(1 - pDock) * 24}}px, 0)`;
      }}
      const fill = document.getElementById("procFill");
      if (fill) {{
        fill.style.transform = `scaleX(${{Math.max(0.04, pBar)}})`;
      }}
      const pct = document.getElementById("procPct");
      if (pct) {{
        pct.textContent = norm >= 0.94 ? FINAL_METRIC : `${{Math.round(pBar * 99.4)}}%`;
      }}
    }};
    window.__setFrame(1, 1, 30);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 4: `course_3d_matte_asset_box` (Video #06 3D Matte-Black Vault Box)
# ---------------------------------------------------------------------------

def _build_course_3d_matte_asset_box(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold")
    vault_title = nfc(props.get("vault_title", "BỘ TÀI NGUYÊN STUDIO"))
    vault_sub = nfc(props.get("vault_sub", "35+ PRESET • MỞ KHÓA NGAY"))
    show_gobo = bool(props.get("gobo_shadow", True))

    cards = props.get("cards") or [
        {
            "tag": "MODULE 01",
            "title": "Masterclass Nhịp Dựng",
            "meta": "18 VIDEO 4K",
            "accent": "#7DD3FC",
        },
        {
            "tag": "FONT PACK",
            "title": "Chữ Việt Hóa",
            "meta": "42 FONT • CHUẨN DẤU",
            "accent": "#F5C451",
        },
        {
            "tag": "EBOOK PRO",
            "title": "Sổ Tay Ánh Sáng",
            "meta": "PDF 128 TRANG",
            "accent": "#34D399",
        },
    ]
    cards = list(cards)[:3]
    while len(cards) < 3:
        cards.append({"tag": "ASSET", "title": "Tài Nguyên Studio", "meta": "PRO PACK", "accent": pal["hex"]})

    card_icons = [
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="4"/><polygon points="10 9 15 12 10 15 10 9" fill="currentColor"/></svg>""",
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>""",
        """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>""",
    ]

    fan_cards_html = []
    for idx, item in enumerate(cards):
        c_acc = nfc(item.get("accent") or pal["hex"])
        fan_cards_html.append(f"""
        <div class="asset-fan-card card-slot-{idx}" id="assetCard{idx}">
          <div class="asset-card-rim"></div>
          <div class="asset-card-top">
            <span class="asset-icon" style="color:{c_acc}; border-color:{c_acc}44; background:{c_acc}1C;">
              {card_icons[idx % 3]}
            </span>
            <span class="asset-tag" style="color:{c_acc};">{esc(item.get("tag", ""))}</span>
          </div>
          <div class="asset-title">{esc(item.get("title", ""))}</div>
          <div class="asset-meta">{esc(item.get("meta", ""))}</div>
        </div>
        """)

    gobo_html = ""
    if show_gobo:
        gobo_html = """
        <svg class="gobo-shadow-svg" viewBox="0 0 900 900" aria-hidden="true">
          <defs>
            <filter id="goboBlur" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="24" />
            </filter>
          </defs>
          <g filter="url(#goboBlur)" fill="rgba(0, 0, 0, 0.34)">
            <ellipse cx="450" cy="690" rx="340" ry="72" />
            <path d="M180 280 C310 240, 420 330, 520 260 C430 370, 290 380, 180 280 Z" opacity="0.45"/>
            <path d="M510 220 C640 190, 740 290, 790 240 C700 340, 580 330, 510 220 Z" opacity="0.38"/>
          </g>
        </svg>
        """

    # v7.9.0: every text >= 66 px on the canvas (70 px secondary). The three asset cards no longer fan behind each other (their text
    # overlapped); they stack in one column and rise out of the vault, alternating a 2 deg tilt.
    sec = secondary_text_px(props)
    vault_badge = nfc(props.get("vault_badge", "STUDIO VAULT"))
    css = f"""
    .vault-scene {{
      position: relative;
      width: {width - 40}px;
      display: flex;
      align-items: center;
      justify-content: center;
      perspective: 1100px;
      padding: 40px 0 30px;
    }}

    .gobo-shadow-svg {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 0;
    }}

    .gobo-shadow-svg g {{
      fill: rgba(0, 0, 0, 0.34);
    }}

    .vault-assembly {{
      position: relative;
      width: {width - 80}px;
      display: flex;
      flex-direction: column;
      align-items: center;
      z-index: 2;
    }}

    .asset-stack {{
      position: relative;
      width: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 20px;
      padding-bottom: 44px;
      z-index: 3;
    }}

    .asset-fan-card {{
      position: relative;
      width: {width - 200}px;
      padding: 22px 34px 26px;
      border-radius: 30px;
      background: linear-gradient(160deg, rgba(32, 36, 48, 0.98) 0%, rgba(16, 18, 26, 0.98) 100%);
      border: 1.5px solid rgba(255, 255, 255, 0.22);
      box-shadow: 0 24px 54px rgba(0, 0, 0, 0.62), inset 0 1px 0 rgba(255, 255, 255, 0.22);
      display: flex;
      flex-direction: column;
      gap: 6px;
      will-change: transform, opacity;
    }}

    .asset-card-top {{
      display: flex;
      align-items: center;
      gap: 22px;
    }}

    .asset-icon {{
      width: {round(sec * 1.1)}px;
      height: {round(sec * 1.1)}px;
      flex-shrink: 0;
      border-radius: 20px;
      border: 1px solid;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .asset-icon svg {{
      width: {round(sec * 0.56)}px;
      height: {round(sec * 0.56)}px;
    }}

    .asset-tag {{
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}

    .asset-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {sec}px;
      line-height: 1.14;
      letter-spacing: -0.02em;
      color: #FAFAFA;
      padding: 0.06em 0.02em;
    }}

    .asset-meta {{
      font-size: {sec}px;
      line-height: 1.16;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: rgba(226, 232, 240, 0.72);
    }}

    .matte-box-lid {{
      position: absolute;
      left: 50%;
      bottom: calc(100% - 26px);
      width: 62%;
      height: 70px;
      margin-left: -31%;
      border-radius: 26px 26px 8px 8px;
      background: linear-gradient(180deg, #2B303E 0%, #171A22 100%);
      border: 1px solid rgba(255, 255, 255, 0.18);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.32);
      transform-origin: bottom center;
      z-index: -1;
    }}

    .matte-box-front {{
      position: relative;
      width: 100%;
      margin-top: -24px;
      border-radius: 26px 26px 38px 38px;
      background: linear-gradient(175deg, #272C38 0%, #141720 46%, #0B0D12 100%);
      border: 1.5px solid rgba(255, 255, 255, 0.20);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.30), 0 30px 70px rgba(0, 0, 0, 0.70);
      z-index: 8;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 30px 36px 34px;
      text-align: center;
    }}

    .clasp-jewel-pill {{
      display: inline-flex;
      align-items: center;
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      color: {pal["hex"]};
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.02em;
      box-shadow: 0 0 22px {pal["glow_ambient"]};
    }}

    .vault-front-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {round(sec * 1.2)}px;
      line-height: 1.1;
      letter-spacing: -0.02em;
      color: #FAFAFA;
      padding: 0.08em 0.04em;
    }}

    .vault-front-sub {{
      font-size: {sec}px;
      line-height: 1.16;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: rgba(226, 232, 240, 0.72);
    }}
    """

    body = f"""
    <div class="vault-scene">
      {gobo_html}
      <div class="vault-assembly" id="vaultAssembly">
        <div class="asset-stack">
          {"".join(fan_cards_html)}
        </div>
        <div class="matte-box-front">
          <div class="matte-box-lid" id="boxLid"></div>
          <div class="clasp-jewel-pill">{esc(vault_badge)}</div>
          <div class="vault-front-title">{esc(vault_title)}</div>
          <div class="vault-front-sub">{esc(vault_sub)}</div>
        </div>
      </div>
    </div>
    """

    js = r"""
    window.__setFrame = function(frameIdx, totalFrames, fps) {
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const pBox = segProgress(norm, 0.00, 0.34);
      const pLid = segProgress(norm, 0.08, 0.45);
      const pCard = [segProgress(norm, 0.34, 0.88), segProgress(norm, 0.26, 0.78), segProgress(norm, 0.18, 0.68)];
      const tilt = [-2, 2, -2];
      const asm = document.getElementById("vaultAssembly");
      if (asm) {
        asm.style.opacity = String(pBox);
        asm.style.transform = `perspective(1100px) rotateX(${3 - 3 * pBox}deg) scale(${0.92 + 0.08 * pBox})`;
      }
      const lid = document.getElementById("boxLid");
      if (lid) {
        lid.style.transform = `perspective(900px) rotateX(${-12 - 22 * pLid}deg)`;
      }
      for (let i = 0; i < 3; i++) {
        const c = document.getElementById("assetCard" + i);
        if (!c) continue;
        const p = pCard[i];
        // rises out of the vault: starts (3 - i) card slots lower, behind the front lip
        c.style.transform = `translate3d(0, ${((1 - p) * (3 - i) * 240).toFixed(1)}px, 0) rotateZ(${(tilt[i] * p).toFixed(2)}deg)`;
        c.style.opacity = String((0.15 + 0.85 * p).toFixed(4));
      }
    };
    window.__setFrame(1, 1, 30);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 5: `tactile_review_glass_scorecard` (Review Đa Ngành 9.4/10)
# ---------------------------------------------------------------------------

def _build_tactile_review_glass_scorecard(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold")
    category = nfc(props.get("category", "ĐÁNH GIÁ ĐỘC LẬP"))
    product_name = nfc(props.get("product_name", "Bộ Đèn Studio"))
    score = float(props.get("score", 9.4))
    score_max = nfc(props.get("score_max", "/10"))
    verdict = nfc(props.get("verdict", "ĐÁNG XUỐNG TIỀN"))
    verdict_label = nfc(props.get("verdict_label", "KẾT LUẬN"))
    pros_label = nfc(props.get("pros_label", "Điểm cộng"))
    cons_label = nfc(props.get("cons_label", "Điểm trừ"))
    pros = props.get("pros") or ["Hoàn màu CRI 98+", "Tản sáng mịn", "Lắp đặt 45 giây"]
    cons = props.get("cons") or ["Quạt hơi ồn", "Túi đựng hơi khít"]
    # v7.9.0: every text >= 66 px (secondary 70, product name 84): one column, pros above cons, score badge beside the meter
    sec = secondary_text_px(props)
    ttl = round(sec * 1.2)

    pros_html = "".join(
        f"""<li class="review-item pro-item">
              <span class="item-icon pro-icon">
                <svg viewBox="0 0 20 20" fill="none" stroke="#4ADE80" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 10.5 8.2 14.5 16 6"/></svg>
              </span>
              <span>{esc(item.strip())}</span>
            </li>"""
        for item in pros
    )
    cons_html = "".join(
        f"""<li class="review-item con-item">
              <span class="item-icon con-icon">
                <svg viewBox="0 0 20 20" fill="none" stroke="#FF4D5E" stroke-width="2.6" stroke-linecap="round"><line x1="5" y1="10" x2="15" y2="10"/></svg>
              </span>
              <span>{esc(item.strip())}</span>
            </li>"""
        for item in cons
    )

    score_ratio = max(0.05, min(1.0, score / 10.0))

    css = f"""
    .scorecard-shell {{
      position: relative;
      width: {width - 56}px;
      padding: 38px 40px 40px;
      border-radius: 38px;
      background: rgba(18, 20, 26, 0.80);
      backdrop-filter: blur(26px) saturate(165%);
      -webkit-backdrop-filter: blur(26px) saturate(165%);
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.44),
        0 28px 68px rgba(0, 0, 0, 0.60);
      display: flex;
      flex-direction: column;
      gap: 22px;
      overflow: hidden;
    }}

    .score-orb {{
      position: absolute;
      top: -80px;
      right: -60px;
      width: 320px;
      height: 320px;
      border-radius: 50%;
      background: radial-gradient(circle, {pal["glow_outer"]} 0%, transparent 70%);
      filter: blur(24px);
      pointer-events: none;
    }}

    .score-top-row {{
      position: relative;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 22px;
    }}

    .score-title-block {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .score-cat {{
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: {pal["hex"]};
      line-height: 1.15;
    }}

    .score-prod-name {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {ttl}px;
      line-height: 1.1;
      letter-spacing: -0.025em;
      color: #FAFAFA;
      padding: 0.12em 0.04em;
    }}

    .hero-score-badge {{
      padding: 14px 26px;
      border-radius: 28px;
      background: rgba(255, 255, 255, 0.05);
      border: 1.5px solid {pal["pill_border"]};
      box-shadow: 0 0 34px {pal["glow_ambient"]};
      display: flex;
      align-items: baseline;
      justify-content: center;
      gap: 4px;
      flex-shrink: 0;
    }}

    .hero-score-num {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 900;
      font-size: {round(sec * 1.6)}px;
      line-height: 1;
      letter-spacing: -0.04em;
      color: {pal["hex"]};
      text-shadow: 0 0 24px {pal["glow_outer"]};
    }}

    .hero-score-max {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {sec}px;
      color: rgba(226, 232, 240, 0.62);
    }}

    .meter-block {{
      position: relative;
      z-index: 2;
      display: flex;
      gap: 26px;
      align-items: center;
    }}

    .meter-track {{
      width: 100%;
      height: 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.09);
      overflow: hidden;
      flex: 1;
    }}

    .meter-fill {{
      height: 100%;
      width: {score_ratio * 100:.1f}%;
      border-radius: 999px;
      background: linear-gradient(90deg, #4ADE80 0%, {pal["hex"]} 100%);
      box-shadow: 0 0 20px {pal["glow_outer"]};
      transform-origin: left center;
    }}

    .pros-cons-grid {{
      position: relative;
      z-index: 2;
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
    }}

    .pc-col {{
      padding: 18px 30px 24px;
      border-radius: 26px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .pros-col {{
      background: rgba(74, 222, 128, 0.07);
      border: 1px solid rgba(74, 222, 128, 0.28);
    }}

    .cons-col {{
      background: rgba(255, 77, 94, 0.07);
      border: 1px solid rgba(255, 77, 94, 0.28);
    }}

    .pc-header {{
      display: flex;
      align-items: center;
      gap: 0.2em;
      font-size: {sec}px;
      font-weight: 800;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}

    .pros-header {{ color: #4ADE80; }}
    .cons-header {{ color: #FF4D5E; }}

    .pc-dot {{
      width: 0.22em;
      height: 0.22em;
      border-radius: 50%;
    }}

    .review-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .review-item {{
      display: flex;
      align-items: flex-start;
      gap: 0.3em;
      font-size: {sec}px;
      line-height: 1.2;
      color: #F1F5F9;
      padding: 0.06em 0.02em;
    }}

    .item-icon {{
      width: 0.7em;
      height: 0.7em;
      border-radius: 0.16em;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 0.26em;
    }}

    .pro-icon {{ background: rgba(74, 222, 128, 0.16); }}
    .con-icon {{ background: rgba(255, 77, 94, 0.16); }}
    .item-icon svg {{ width: 0.48em; height: 0.48em; }}

    .verdict-ribbon {{
      position: relative;
      z-index: 2;
      padding: 12px 28px 14px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.12);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: {pal["bright"]};
      flex-wrap: wrap;
      gap: 0 24px;
      line-height: 1.18;
    }}
    """

    body = f"""
    <div class="scorecard-shell" id="scoreShell">
      <div class="score-orb"></div>
      <div class="score-top-row">
        <div class="score-title-block">
          <div class="score-cat">{esc(category)}</div>
          <div class="score-prod-name">{esc(product_name)}</div>
        </div>
      </div>

      <div class="meter-block">
        <div class="hero-score-badge">
          <span class="hero-score-num" id="scoreNum">{score:.1f}</span>
          <span class="hero-score-max">{esc(score_max)}</span>
        </div>
        <div class="meter-track">
          <div class="meter-fill" id="meterFill"></div>
        </div>
      </div>

      <div class="pros-cons-grid">
        <div class="pc-col pros-col" id="prosCol">
          <div class="pc-header pros-header">
            <span class="pc-dot" style="background:#4ADE80; box-shadow:0 0 10px #4ADE80;"></span>
            <span>{esc(pros_label)}</span>
          </div>
          <ul class="review-list">{pros_html}</ul>
        </div>

        <div class="pc-col cons-col" id="consCol">
          <div class="pc-header cons-header">
            <span class="pc-dot" style="background:#FF4D5E; box-shadow:0 0 10px #FF4D5E;"></span>
            <span>{esc(cons_label)}</span>
          </div>
          <ul class="review-list">{cons_html}</ul>
        </div>
      </div>

      <div class="verdict-ribbon">
        <span>{esc(verdict_label)}</span>
        <span>{esc(verdict)}</span>
      </div>
    </div>
    """

    js = f"""
    const TARGET_SCORE = {score:.2f};
    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const pShell = segProgress(norm, 0.00, 0.34);
      const pScore = segProgress(norm, 0.10, 0.72);
      const pPros  = segProgress(norm, 0.22, 0.68);
      const pCons  = segProgress(norm, 0.34, 0.82);

      const shell = document.getElementById("scoreShell");
      if (shell) {{
        shell.style.opacity = String(pShell);
        shell.style.transform = `translate3d(0, ${{(1 - pShell) * 32}}px, 0) scale(${{0.95 + 0.05 * pShell}})`;
      }}
      const numEl = document.getElementById("scoreNum");
      if (numEl) {{
        numEl.textContent = (TARGET_SCORE * pScore).toFixed(1);
      }}
      const fillEl = document.getElementById("meterFill");
      if (fillEl) {{
        fillEl.style.transform = `scaleX(${{Math.max(0.03, pScore)}})`;
      }}
      const prosEl = document.getElementById("prosCol");
      if (prosEl) {{
        prosEl.style.opacity = String(pPros);
        prosEl.style.transform = `translate3d(${{(1 - pPros) * -20}}px, 0, 0)`;
      }}
      const consEl = document.getElementById("consCol");
      if (consEl) {{
        consEl.style.opacity = String(pCons);
        consEl.style.transform = `translate3d(${{(1 - pCons) * 20}}px, 0, 0)`;
      }}
    }};
    window.__setFrame(1, 1, 30);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 6: `isometric_3d_prompt_browser` (Video #12/#16/#18 3D Prompt Studio)
# ---------------------------------------------------------------------------

def _build_isometric_3d_prompt_browser(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald")
    window_title = nfc(props.get("window_title", "prompt.studio"))
    prompt_kicker = nfc(props.get("prompt_kicker", "CÂU LỆNH KHÓA ÁNH SÁNG"))
    status_done = nfc(props.get("status_done", "LOCKED"))
    status_typing = nfc(props.get("status_typing", "TYPING…"))
    # v7.9.0: every text >= 66 px on the canvas. The window turns at most ~6 deg in perspective (was 14 deg) so its near and far
    # sides stay inside the 66-74 px band around 70 px
    sec = secondary_text_px(props)
    prompt_text = nfc(
        props.get(
            "prompt_text",
            "Chân dung điện ảnh, ánh sáng Rembrandt 45 độ, ống kính 85mm f/1.4 --ar 9:16",
        )
    )
    locks = list(
        props.get("locks")
        or [
            "9:16",
            "85MM",
            "REMBRANDT",
            "KHÓA SEED",
        ]
    )[:4]
    type_start_s = float(props.get("type_start_s", 0.08))
    type_end_s_raw = props.get("type_end_s")
    type_end_s_js = "null" if type_end_s_raw is None else str(float(type_end_s_raw))
    raw_triggers = props.get("card_triggers_s")
    triggers_js = json.dumps([float(x) for x in raw_triggers]) if raw_triggers else "null"
    bottom_note = nfc(props.get("bottom_note", ""))
    bottom_note_at_s = float(props.get("bottom_note_at_s", 1.30))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    lock_badges_html = "".join(
        f"""<div class="lock-pill" id="lockPill{idx}">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="9" width="12" height="9" rx="2.5"/><path d="M6.5 9V6a3.5 3.5 0 0 1 7 0v3"/></svg>
              <span>{esc(lk)}</span>
            </div>"""
        for idx, lk in enumerate(locks)
    )

    bottom_note_html = ""
    if bottom_note:
        bottom_note_html = f"""
        <div class="iso-bottom-note" id="isoBottomNote">{render_swash_hybrid_html_py(bottom_note)}</div>
        """

    css = f"""
    .iso-scene {{
      position: relative;
      width: {width - 40}px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 28px;
      padding: 30px 20px;
      will-change: transform, opacity;
    }}

    .iso-browser-window {{
      position: relative;
      width: {width - 200}px;
      border-radius: 30px;
      padding: 1.5px;
      background: linear-gradient(
        135deg,
        {pal["hex"]}CC 0%,
        #F5C45199 42%,
        rgba(255, 255, 255, 0.14) 100%
      );
      transform: perspective(1150px) rotateY(-4deg) rotateX(3deg);
      transform-style: preserve-3d;
      box-shadow:
        -28px 36px 74px rgba(0, 0, 0, 0.66),
        0 0 46px {pal["glow_ambient"]};
      will-change: transform, opacity;
    }}

    .iso-browser-inner {{
      position: relative;
      border-radius: 28.5px;
      background: rgba(14, 17, 24, 0.92);
      backdrop-filter: blur(26px);
      -webkit-backdrop-filter: blur(26px);
      overflow: hidden;
    }}

    .iso-sheen-sweep {{
      position: absolute;
      top: -35%;
      bottom: -35%;
      width: 36%;
      background: linear-gradient(
        108deg,
        rgba(255, 255, 255, 0.0) 0%,
        rgba(255, 255, 255, 0.08) 48%,
        rgba(255, 255, 255, 0.16) 52%,
        rgba(255, 255, 255, 0.0) 100%
      );
      transform: skewX(-18deg);
      pointer-events: none;
      z-index: 5;
    }}

    .browser-chrome-bar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 26px;
      background: rgba(255, 255, 255, 0.04);
      border-bottom: 1px solid rgba(255, 255, 255, 0.10);
      flex-wrap: wrap;
      gap: 12px 18px;
    }}

    .traffic-dots {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .tdot {{
      width: 18px;
      height: 18px;
      border-radius: 50%;
    }}

    .address-pill {{
      padding: 0.02em 0.36em;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.12);
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      color: rgba(226, 232, 240, 0.85);
    }}

    .status-ready-pill {{
      padding: 0.02em 0.36em;
      border-radius: 999px;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      font-family: 'Studio Mono', monospace;
      font-size: {sec}px;
      font-weight: 700;
      color: {pal["hex"]};
    }}

    .prompt-editor-body {{
      padding: 26px 36px 34px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .prompt-kicker-line {{
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #F5C451;
      line-height: 1.15;
    }}

    .prompt-text-box {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 500;
      font-size: {sec}px;
      line-height: 1.28;
      color: #F8FAFC;
      padding: 0.12em 0.06em;
    }}

    .typing-caret {{
      display: inline-block;
      width: 6px;
      height: 1.05em;
      vertical-align: text-bottom;
      margin-left: 4px;
      border-radius: 2px;
      background: {pal["hex"]};
      box-shadow: 0 0 14px {pal["hex"]};
    }}

    .lock-badges-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 16px 18px;
      max-width: {width - 140}px;
      transform: perspective(1150px) rotateY(-4deg) rotateX(2deg);
    }}

    .lock-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.2em;
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.82);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.24),
        0 18px 40px rgba(0, 0, 0, 0.50);
      color: rgba(226, 232, 240, 0.72);
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.03em;
      will-change: transform, opacity, border-color, box-shadow;
    }}

    .lock-pill svg {{
      width: 0.62em;
      height: 0.62em;
      color: {pal["hex"]};
    }}

    .iso-bottom-note {{
      font-size: {sec}px;
      color: {pal["bright"]};
      padding: 0.32em 0.25em;
      text-align: center;
      text-shadow: 0 4px 22px {pal["glow_outer"]};
    }}
    """

    body = f"""
    <div class="iso-scene" id="isoScene">
      <div class="iso-browser-window" id="isoWin">
        <div class="iso-browser-inner">
          <div class="iso-sheen-sweep" id="isoSheen"></div>
          <div class="browser-chrome-bar">
            <div class="traffic-dots">
              <span class="tdot" style="background:#FF5F56;"></span>
              <span class="tdot" style="background:#FFBD2E;"></span>
              <span class="tdot" style="background:#27C93F;"></span>
            </div>
            <div class="address-pill">{esc(window_title)}</div>
            <div class="status-ready-pill" id="isoStatusPill">{esc(status_done)}</div>
          </div>

          <div class="prompt-editor-body">
            <div class="prompt-kicker-line">{esc(prompt_kicker)}</div>
            <div class="prompt-text-box">
              <span id="typedPrompt">{esc(prompt_text)}</span><span class="typing-caret" id="promptCaret"></span>
            </div>
          </div>
        </div>
      </div>

      <div class="lock-badges-row" id="isoLocksRow">
        {lock_badges_html}
      </div>
      {bottom_note_html}
    </div>
    """

    js = f"""
    const FULL_PROMPT = {json.dumps(prompt_text)};
    const GRAPHEMES = splitGraphemesVi(FULL_PROMPT);
    const LOCK_COUNT = {len(locks)};
    const STATUS_DONE = {json.dumps(status_done, ensure_ascii=False)};
    const STATUS_TYPING = {json.dumps(status_typing, ensure_ascii=False)};
    const TYPE_START_S = {type_start_s};
    const EXPLICIT_TYPE_END_S = {type_end_s_js};
    const EXPLICIT_TRIGGERS_S = {triggers_js};
    const ACCENT_BORDER = {json.dumps(pal["pill_border"])};
    const ACCENT_BRIGHT = {json.dumps(pal["bright"])};
    const ACCENT_AMBIENT = {json.dumps(pal["glow_ambient"])};
    const ACCENT_OUTER = {json.dumps(pal["glow_outer"])};
    const BOTTOM_NOTE_AT_S = {bottom_note_at_s};
    const EXIT_DUR_S = {exit_dur_s};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 2.6 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, Math.max(2.6, (EXPLICIT_TYPE_END_S || 1.8) + 0.5));
      const typeEndSec = EXPLICIT_TYPE_END_S != null
        ? EXPLICIT_TYPE_END_S
        : Math.max(TYPE_START_S + 0.55, clipDurSec * 0.80);

      const scene = document.getElementById("isoScene");
      if (scene) {{
        scene.style.opacity = "1";
        scene.style.transform = "";
        scene.style.filter = "none";
      }}

      const pWin = timeProgress(tSec, 0.0, 0.34, player3Snap);
      const win = document.getElementById("isoWin");
      if (win) {{
        const breathRy = Math.sin(tSec * 1.45) * 1.7 * pWin;
        const breathRx = Math.cos(tSec * 1.2) * 1.3 * pWin;
        const breathDy = -Math.sin(tSec * 2.0) * 5.0 * pWin;
        const ry = -8 + 4 * pWin + breathRy;
        const rx = 6 - 3 * pWin + breathRx;
        win.style.opacity = String(pWin);
        win.style.transform =
          `perspective(1150px) rotateY(${{ry.toFixed(2)}}deg) rotateX(${{rx.toFixed(2)}}deg) ` +
          `translate3d(0, ${{((1 - pWin) * 28 + breathDy).toFixed(2)}}px, 0)`;
      }}

      const sheen = document.getElementById("isoSheen");
      if (sheen) {{
        const cyc = (tSec * 0.38) % 1.0;
        sheen.style.left = `${{(-42 + cyc * 186).toFixed(1)}}%`;
      }}

      const pType = totalFrames <= 1
        ? 1
        : Math.max(0, Math.min(1, (tSec - TYPE_START_S) / Math.max(0.12, typeEndSec - TYPE_START_S)));
      const typed = document.getElementById("typedPrompt");
      if (typed) {{
        const count = pType >= 0.995
          ? GRAPHEMES.length
          : Math.max(1, Math.round(GRAPHEMES.length * pType));
        typed.textContent = GRAPHEMES.slice(0, count).join("");
      }}

      const caret = document.getElementById("promptCaret");
      if (caret) {{
        const isTyping = pType > 0 && pType < 0.995 && totalFrames > 1;
        const blink = isTyping ? 1.0 : (0.22 + 0.78 * (0.5 + 0.5 * Math.sin(tSec * Math.PI * 4.4)));
        caret.style.opacity = String(blink.toFixed(3));
      }}

      const statusEl = document.getElementById("isoStatusPill");
      if (statusEl) {{
        statusEl.textContent = (totalFrames > 1 && pType < 0.98) ? STATUS_TYPING : STATUS_DONE;
      }}

      const lockSpan = Math.max(0.4, typeEndSec - TYPE_START_S);
      for (let i = 0; i < LOCK_COUNT; i++) {{
        const pill = document.getElementById("lockPill" + i);
        if (!pill) continue;
        const trig = EXPLICIT_TRIGGERS_S && EXPLICIT_TRIGGERS_S[i] != null
          ? EXPLICIT_TRIGGERS_S[i]
          : TYPE_START_S + 0.14 + (i / Math.max(1, LOCK_COUNT)) * (lockSpan * 0.78);
        const pp = timeProgress(tSec, trig, 0.32, player3Snap);
        const lit = timeProgress(tSec, trig + 0.08, 0.28, velvetC2);
        const floatY = pp >= 1 ? Math.sin(tSec * 2.3 + i * 0.85) * 2.5 : 0;
        pill.style.opacity = String((0.15 + 0.85 * pp).toFixed(4));
        pill.style.transform = `translate3d(0, ${{((1 - pp) * 22 + floatY).toFixed(2)}}px, 0) scale(${{(0.94 + 0.06 * pp).toFixed(4)}})`;
        if (lit > 0.15) {{
          pill.style.borderColor = ACCENT_BORDER;
          pill.style.color = ACCENT_BRIGHT;
          pill.style.boxShadow = `inset 0 1px 0 rgba(255,255,255,0.36), 0 18px 40px rgba(0,0,0,0.50), 0 0 ${{(26 * lit).toFixed(1)}}px ${{ACCENT_OUTER}}`;
        }} else {{
          pill.style.borderColor = "rgba(255, 255, 255, 0.16)";
          pill.style.color = "rgba(226, 232, 240, 0.65)";
          pill.style.boxShadow = "0 14px 30px rgba(0, 0, 0, 0.40)";
        }}
      }}

      const noteEl = document.getElementById("isoBottomNote");
      if (noteEl) {{
        const pNote = timeProgress(tSec, BOTTOM_NOTE_AT_S, 0.34, velvetC2);
        const s1 = Math.max(0, pNote * 124 - 24);
        const s2 = Math.min(100, pNote * 124);
        const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        noteEl.style.opacity = String(pNote.toFixed(4));
        noteEl.style.webkitMaskImage = mask;
        noteEl.style.maskImage = mask;
        noteEl.style.transform = `translate3d(0, ${{((1 - pNote) * 14).toFixed(2)}}px, 0)`;
      }}

      if (scene && totalFrames > 1) {{
        applyCleanExit(scene, tSec, clipDurSec, EXIT_DUR_S);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 7: `skewed_3d_polaroid_trio` (V14 Upgrade: -7deg / 0deg / +8deg)
# ---------------------------------------------------------------------------

def _build_skewed_3d_polaroid_trio(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold")
    kicker = _prop_or_demo("skewed_3d_polaroid_trio", props, "kicker", "BẢN QUAY THÔ GỐC", required=False)
    raw_imgs = props.get("images") or [
        props.get("img_01"),
        props.get("img_02"),
        props.get("img_03"),
    ]
    captions = props.get("captions") or (
        ["Góc rộng", "85mm", "Cận cảnh"] if props.get("demo") else None
    )
    if not captions:
        raise ValueError("skewed_3d_polaroid_trio: required prop 'captions' is missing (pass it, or demo=true / --demo for self-test text)")
    stamps = props.get("stamps") or (["CAM A", "CAM B", "MACRO"] if props.get("demo") else [])
    raw_triggers = props.get("card_triggers_s") or [0.04, 0.30, 0.54]
    card_triggers_s = [float(raw_triggers[i]) if i < len(raw_triggers) else 0.04 + i * 0.25 for i in range(3)]
    bottom_note = nfc(props.get("bottom_note", ""))
    bottom_note_at_s = float(props.get("bottom_note_at_s", 1.35))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))
    # v7.9.0 (v4 K1 + user decision 2026-11-26): every text lands ~70 px (66-74) on the canvas after the plate is scaled by
    # `plate_scale` (v4: 24 / 13 / 36 px CSS x 0.76 = 18 / 10 / 27 px). The cards spread so the side cards no longer slide under the
    # centre one (their captions overlapped it), the stamp moves from the photo corner into the footer (it covered the photo) and the
    # deck grows with the caption lines instead of squeezing the photo.
    kick_px = stamp_px = cap_px = note_px = secondary_text_px(props)
    card_w = 300
    well_h = int(props.get("well_h", 300))
    cap_lines = 2
    deck_h = int(40 + 16 + well_h + 10 + (stamp_px * 1.15 + 6 if stamps else 0) + cap_lines * cap_px * 1.04 + 0.12 * cap_px + 20 + 70)

    urls = [
        image_to_safe_data_url(raw_imgs[i] if i < len(raw_imgs) else None, fallback_variant=f"raw{i + 1}")
        for i in range(3)
    ]

    polaroids_html = []
    for i in range(3):
        cap = esc(captions[i] if i < len(captions) else f"RAW 0{i + 1}")
        st = f'<span class="raw-corner-tag">{esc(stamps[i])}</span>' if i < len(stamps) and stamps[i] else ""   # v7.9.0: no default stamp
        polaroids_html.append(f"""
        <div class="polaroid-card pol-{i}" id="polCard{i}">
          <div class="polaroid-photo-well">
            <img src="{urls[i]}" alt="Polaroid {i + 1}" />
            <div class="polaroid-gloss-sheen" id="polSheen{i}"></div>
          </div>
          <div class="polaroid-footer">
            {st}
            <span class="polaroid-caption">{cap}</span>
          </div>
        </div>
        """)

    kicker_html = f'<div class="polaroid-kicker-pill" id="polKicker">{esc(kicker)}</div>' if kicker else ""
    bottom_note_html = ""
    if bottom_note:
        bottom_note_html = f"""
        <div class="polaroid-bottom-note" id="polBottomNote">{render_swash_hybrid_html_py(bottom_note)}</div>
        """

    css = f"""
    .polaroid-stage {{
      position: relative;
      width: {width - 60}px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 24px;
      perspective: 1250px;
      will-change: transform, opacity;
    }}

    .polaroid-kicker-pill {{
      padding: 0.04em 0.4em;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.80);
      backdrop-filter: blur(18px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      font-size: {kick_px}px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-align: center;
      max-width: {width - 80}px;
      color: {pal["hex"]};
      box-shadow: 0 14px 34px rgba(0,0,0,0.46);
      z-index: 10;
      line-height: 1.15;
    }}

    .polaroid-fan-deck {{
      position: relative;
      width: {width - 60}px;
      height: {deck_h}px;
      transform-style: preserve-3d;
    }}

    /* Warm Cream Archival Stock Polaroid (#FAF6EE) + Multi-Layer Physical Shadows */
    .polaroid-card {{
      position: absolute;
      top: 40px;
      left: calc(50% - {card_w // 2}px);
      width: {card_w}px;
      padding: 16px 16px 20px;
      border-radius: 14px;
      background: linear-gradient(165deg, #FCF9F2 0%, #F4EFE4 100%);
      border: 1px solid rgba(255, 255, 255, 0.92);
      box-shadow:
        0 4px 10px rgba(0, 0, 0, 0.24),
        0 18px 36px rgba(0, 0, 0, 0.38),
        0 38px 74px rgba(0, 0, 0, 0.56);
      display: flex;
      flex-direction: column;
      gap: 10px;
      will-change: transform, opacity;
    }}

    .polaroid-photo-well {{
      position: relative;
      width: 100%;
      height: {well_h}px;
      border-radius: 6px;
      overflow: hidden;
      background: #14171F;
      box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.38);
    }}

    .polaroid-photo-well img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}

    .polaroid-gloss-sheen {{
      position: absolute;
      top: -30%;
      bottom: -30%;
      width: 44%;
      background: linear-gradient(
        105deg,
        rgba(255, 255, 255, 0.0) 0%,
        rgba(255, 255, 255, 0.18) 50%,
        rgba(255, 255, 255, 0.0) 100%
      );
      transform: skewX(-20deg);
      pointer-events: none;
    }}

    .raw-corner-tag {{
      position: static;
      padding: 0 0.24em;
      border-radius: 6px;
      background: rgba(20, 23, 31, 0.88);
      font-family: 'Studio Mono', monospace;
      font-size: {stamp_px}px;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: #F8FAFC;
      border: 1px solid rgba(255,255,255,0.20);
      align-self: center;
      line-height: 1.15;
    }}

    .polaroid-footer {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 2px;
      flex-direction: column;
      gap: 6px;
    }}

    .polaroid-caption {{
      font-family: 'Playfair Display', Georgia, serif;
      font-style: italic;
      font-weight: 700;
      font-size: {cap_px}px;
      line-height: 1.04;
      color: #1E293B;
      padding: 0.06em 0.04em;
      text-align: center;
    }}

    .polaroid-bottom-note {{
      z-index: 12;
      font-size: {note_px}px;
      line-height: 1.12;
      color: {pal["hex"]};
      padding: 0.32em 0.25em;
      margin-top: -4px;
      text-align: center;
      text-shadow:
        0 0 18px {pal["glow_inner"]},
        0 0 40px {pal["glow_outer"]},
        0 8px 24px rgba(0, 0, 0, 0.62);
    }}
    """

    body = f"""
    <div class="polaroid-stage" id="polStage">
      {kicker_html}
      <div class="polaroid-fan-deck" id="polDeck">
        {"".join(polaroids_html)}
      </div>
      {bottom_note_html}
    </div>
    """

    # Exact -7deg / 0deg / +8deg 3D fanned choreography + continuous 3D parallax & sheen + bottom_note wipe
    js = f"""
    const CARD_TRIGGERS_S = {json.dumps(card_triggers_s)};
    const SPREAD = {card_w + 12};
    const BOTTOM_NOTE_AT_S = {bottom_note_at_s};
    const EXIT_DUR_S = {exit_dur_s};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, Math.max(2.4, BOTTOM_NOTE_AT_S + 0.6));

      const stage = document.getElementById("polStage");
      if (stage) {{
        stage.style.opacity = "1";
        stage.style.transform = "";
        stage.style.filter = "none";
      }}

      const pKick = timeProgress(tSec, 0.0, 0.26, velvetC2);
      const kick = document.getElementById("polKicker");
      if (kick) {{
        kick.style.opacity = String(pKick.toFixed(4));
        kick.style.transform = `translate3d(0, ${{((1 - pKick) * -18).toFixed(2)}}px, 0)`;
      }}

      const deck = document.getElementById("polDeck");
      if (deck) {{
        const rx = Math.sin(tSec * 1.55) * 1.8;
        const ry = Math.cos(tSec * 1.25) * 2.4;
        deck.style.transform = `rotateX(${{rx.toFixed(2)}}deg) rotateY(${{ry.toFixed(2)}}deg)`;
      }}

      const p0 = timeProgress(tSec, CARD_TRIGGERS_S[0], 0.40, player3Snap);
      const p1 = timeProgress(tSec, CARD_TRIGGERS_S[1], 0.40, player3Snap);
      const p2 = timeProgress(tSec, CARD_TRIGGERS_S[2], 0.40, player3Snap);

      const f0 = p0 >= 1 ? Math.sin(tSec * 2.1 + 0.0) * 5.0 : 0;
      const f1 = p1 >= 1 ? Math.sin(tSec * 2.1 + 1.1) * 5.5 : 0;
      const f2 = p2 >= 1 ? Math.sin(tSec * 2.1 + 2.2) * 5.0 : 0;

      const c0 = document.getElementById("polCard0");
      if (c0) {{
        c0.style.zIndex = "2";
        c0.style.opacity = String(p0.toFixed(4));
        c0.style.transform =
          `perspective(1250px) translate3d(${{(-SPREAD * p0).toFixed(2)}}px, ${{(28 * p0 + (1 - p0) * 44 + f0).toFixed(2)}}px, 0) ` +
          `rotateZ(${{(-7 * p0).toFixed(2)}}deg) rotateY(${{(7 * p0).toFixed(2)}}deg)`;
      }}
      const c1 = document.getElementById("polCard1");
      if (c1) {{
        c1.style.zIndex = "4";
        c1.style.opacity = String(p1.toFixed(4));
        c1.style.transform =
          `perspective(1250px) translate3d(0px, ${{-22 * p1 + (1 - p1) * 44 + f1}}px, 0) ` +
          `rotateZ(0deg) scale(${{(0.95 + 0.05 * p1).toFixed(4)}})`;
      }}
      const c2 = document.getElementById("polCard2");
      if (c2) {{
        c2.style.zIndex = "3";
        c2.style.opacity = String(p2.toFixed(4));
        c2.style.transform =
          `perspective(1250px) translate3d(${{(SPREAD * p2).toFixed(2)}}px, ${{(32 * p2 + (1 - p2) * 44 + f2).toFixed(2)}}px, 0) ` +
          `rotateZ(${{(8 * p2).toFixed(2)}}deg) rotateY(${{(-7 * p2).toFixed(2)}}deg)`;
      }}

      for (let i = 0; i < 3; i++) {{
        const sh = document.getElementById("polSheen" + i);
        if (sh) {{
          const cyc = ((tSec * 0.44) + i * 0.22) % 1.0;
          sh.style.left = `${{(-50 + cyc * 200).toFixed(1)}}%`;
        }}
      }}

      const noteEl = document.getElementById("polBottomNote");
      if (noteEl) {{
        const pNote = timeProgress(tSec, BOTTOM_NOTE_AT_S, 0.36, velvetC2);
        const s1 = Math.max(0, pNote * 126 - 26);
        const s2 = Math.min(100, pNote * 126);
        const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        noteEl.style.opacity = String(pNote.toFixed(4));
        noteEl.style.webkitMaskImage = mask;
        noteEl.style.maskImage = mask;
        noteEl.style.transform = `translate3d(0, ${{((1 - pNote) * 14).toFixed(2)}}px, 0)`;
      }}

      if (stage && totalFrames > 1) {{
        applyCleanExit(stage, tSec, clipDurSec, EXIT_DUR_S);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# Template 8: `doctor_authority_lower_third` (Hospital / Specialist Credential)
# ---------------------------------------------------------------------------

def _build_doctor_authority_lower_third(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "ice_cyan")
    degree_kicker = nfc(props.get("degree", "THẠC SĨ • BS CKI"))
    doctor_name = nfc(props.get("name", "BS. NGUYỄN MINH KHÔI"))
    specialty = nfc(props.get("specialty", "Trưởng Khoa Phục Hình"))
    credential = nfc(props.get("credential", "15+ NĂM LÂM SÀNG"))
    # v7.9.0: every text >= 66 px (secondary 70, name 84); the crest moves into the degree row so the copy gets the full width.
    # A 1080x1920 frame keeps the card in the lower third (bottom 330 px clear, its top stays below the face band y <= 960).
    sec = secondary_text_px(props)
    theme = nfc(props.get("theme", "dark")).lower()
    is_light = theme == "light"

    # Position in 9:16 lower-third safe zone if full tall frame, else center cleanly
    is_tall_frame = height >= 1200
    align_css = "align-items: flex-end; padding-bottom: 330px;" if is_tall_frame else "align-items: center;"

    shell_bg = "rgba(250, 252, 255, 0.88)" if is_light else "rgba(14, 18, 26, 0.84)"
    name_col = "#0F172A" if is_light else "#FAFAFA"
    spec_col = "rgba(15, 23, 42, 0.76)" if is_light else "rgba(226, 232, 240, 0.84)"
    border_col = "rgba(15, 23, 42, 0.12)" if is_light else "rgba(255, 255, 255, 0.16)"

    css = f"""
    .stage-root {{
      {align_css}
    }}

    .authority-card {{
      position: relative;
      width: {width - 56}px;
      display: flex;
      align-items: stretch;
      border-radius: 28px;
      background: {shell_bg};
      backdrop-filter: blur(26px) saturate(170%);
      -webkit-backdrop-filter: blur(26px) saturate(170%);
      border: 1px solid {border_col};
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.42),
        0 26px 62px rgba(0, 0, 0, 0.56);
      overflow: hidden;
      will-change: transform, opacity;
    }}

    .authority-jewel-spine {{
      width: 9px;
      background: linear-gradient(180deg, {pal["bright"]} 0%, {pal["hex"]} 100%);
      box-shadow: 0 0 22px {pal["glow_outer"]};
      flex-shrink: 0;
    }}

    .authority-inner {{
      flex: 1;
      display: flex;
      align-items: center;
      gap: 0;
      padding: 22px 34px 26px;
    }}

    .crest-medallion {{
      width: {round(sec * 1.1)}px;
      height: {round(sec * 1.1)}px;
      border-radius: 20px;
      background: {pal["pill_bg"]};
      border: 1.5px solid {pal["pill_border"]};
      box-shadow: 0 0 28px {pal["glow_ambient"]};
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      color: {pal["hex"]};
    }}

    .crest-medallion svg {{
      width: {round(sec * 0.6)}px;
      height: {round(sec * 0.6)}px;
    }}

    .authority-copy {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}

    .degree-row {{
      display: flex;
      align-items: center;
      gap: 0.22em;
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: {pal["hex"]};
      flex-wrap: wrap;
      line-height: 1.15;
    }}

    .verified-seal {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 0.62em;
      height: 0.62em;
      border-radius: 50%;
      background: {pal["hex"]};
      color: #0B1120;
    }}

    .verified-seal svg {{
      width: 0.4em;
      height: 0.4em;
    }}

    .doctor-name {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {round(sec * 1.2)}px;
      line-height: 1.1;
      letter-spacing: -0.024em;
      color: {name_col};
      padding: 0.10em 0.04em;
    }}

    .doctor-specialty {{
      font-family: 'Playfair Display', Georgia, serif;
      font-style: italic;
      font-weight: 600;
      font-size: {sec}px;
      line-height: 1.18;
      color: {spec_col};
      padding: 0.08em 0.04em;
    }}

    .credential-bar {{
      margin-top: 4px;
      padding-top: 8px;
      border-top: 1px solid {border_col};
      font-size: {sec}px;
      font-weight: 700;
      letter-spacing: 0.03em;
      color: {pal["bright"] if not is_light else pal["deep"]};
      line-height: 1.15;
    }}
    """

    body = f"""
    <div class="authority-card" id="authCard">
      <div class="authority-jewel-spine" id="authSpine"></div>
      <div class="authority-inner">
        <div class="authority-copy">
          <div class="degree-row">
            <span class="crest-medallion">
              <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 3L5 7.5v8.2C5 23 9.7 27.9 16 30c6.3-2.1 11-7 11-14.3V7.5L16 3z"/>
                <path d="M16 10.5v11M10.5 16h11"/>
              </svg>
            </span>
            <span>{esc(degree_kicker)}</span>
            <span class="verified-seal">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3.5 8.5 6.5 11.5 12.5 5"/></svg>
            </span>
          </div>
          <div class="doctor-name">{esc(doctor_name)}</div>
          <div class="doctor-specialty">{esc(specialty)}</div>
          <div class="credential-bar">{esc(credential)}</div>
        </div>
      </div>
    </div>
    """

    js = r"""
    window.__setFrame = function(frameIdx, totalFrames, fps) {
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const pCard = segProgress(norm, 0.00, 0.56);
      const card = document.getElementById("authCard");
      if (card) {
        card.style.opacity = String(pCard);
        card.style.transform = `translate3d(${(1 - pCard) * -42}px, ${(1 - pCard) * 18}px, 0) scale(${0.96 + 0.04 * pCard})`;
      }
    };
    window.__setFrame(1, 1, 30);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js)


# ---------------------------------------------------------------------------
# v7.1: 12 `@__dviet` + `@vietanh` Kinetic Typography Templates (`kt01`..`kt12`)
# ---------------------------------------------------------------------------

def _auto_typo_px(
    text: str,
    width: int,
    *,
    min_px: int = 62,
    max_px: int = 104,
    char_factor: float = 0.56,
    usable_ratio: float = 0.86,
) -> int:
    clean_len = max(1, max((len(line.strip()) for line in nfc(text).splitlines()), default=1))
    est = int((width * usable_ratio) / max(5.2, clean_len * char_factor))
    return max(min_px, min(max_px, est))


def _kt_optional_pill_html(props: dict[str, Any]) -> str:
    badge = nfc(props.get("badge_text") or props.get("pill_text") or "").strip()
    if not badge:
        return ""
    return f"""
    <div class="kt-opt-pill" id="ktOptPill">
      <span class="kt-opt-pill-dot"></span>
      <span class="kt-opt-pill-label">{esc(badge)}</span>
    </div>
    """


def _kt_theme_tokens(props: dict[str, Any]) -> tuple[str, bool, str, str, str]:
    """Returns `(theme_mode, is_light, primary_ink, hero_shadow, helper_shadow)`."""
    is_light = nfc(props.get("theme", "dark")).strip().lower() == "light"
    theme_mode = "light" if is_light else "dark"
    primary_ink = "#14171F" if is_light else "#FAFAFA"
    hero_shadow = "0 6px 20px rgba(15, 23, 42, 0.14)" if is_light else "0 8px 24px rgba(0, 0, 0, 0.54)"
    helper_shadow = "0 4px 14px rgba(15, 23, 42, 0.12)" if is_light else "0 4px 18px rgba(0, 0, 0, 0.50)"
    return theme_mode, is_light, primary_ink, hero_shadow, helper_shadow


KT_DIACRITIC_PAD_X_EM = 0.25  # horizontal padding of `.kt-diacritic-safe` (part of the kt03 word gap)
SECONDARY_TEXT_PX = 70        # [UOC] user decision 2026-11-26: secondary plate text (pills, helpers, labels) lands 66-74 px on the canvas


def secondary_text_px(props: Any = None, element_scale: float = 1.0) -> int:
    """v7.9.0: CSS px for a secondary text (pill label, helper, card label) so it is drawn at SECONDARY_TEXT_PX (~70, inside 66-74)
    on the 1080x1920 canvas after the plate scale (`props["plate_scale"]` or a number) and a static `element_scale` (a card scaled
    by its own transform)."""
    ps = float(props.get("plate_scale", 1.0)) if isinstance(props, dict) else float(props if props is not None else 1.0)
    return int(round(SECONDARY_TEXT_PX / max(ps * float(element_scale), 1e-3)))
KT_ENTRANCE_P = tuple(i / 40 for i in range(41))  # entrance progress samples for the word-spacing fit (`ws_fit_px`)


def _kt_shared_css(pal: dict[str, str], width: int, align: str = "center", *, theme: str = "dark", sec_px: int = SECONDARY_TEXT_PX) -> str:
    flex_align = {"left": "flex-start", "right": "flex-end"}.get(align, "center")
    text_align = {"left": "left", "right": "right"}.get(align, "center")
    is_light = nfc(theme).strip().lower() == "light"
    pill_bg = "rgba(255, 255, 255, 0.92)" if is_light else "rgba(16, 19, 26, 0.80)"
    pill_shadow = (
        f"0 8px 22px rgba(15, 23, 42, 0.12), 0 0 14px {pal['glow_ambient']}"
        if is_light
        else f"0 12px 30px rgba(0, 0, 0, 0.46), 0 0 20px {pal['glow_ambient']}"
    )
    pill_ink = "#14171F" if is_light else "#F8FAFC"
    return f"""
    .kt-rig {{
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: {flex_align};
      justify-content: center;
      text-align: {text_align};
      max-width: {int(width * 0.95)}px;
      padding: 18px 28px;
      will-change: transform, opacity, filter;
    }}

    .kt-diacritic-safe {{
      -webkit-text-stroke: 0px transparent !important;
      padding: 0.32em {KT_DIACRITIC_PAD_X_EM}em;
    }}

    .kt-opt-pill {{
      margin-top: 0.16em;
      font-size: {sec_px}px;
      display: inline-flex;
      align-items: center;
      gap: 0.2em;
      padding: 0.08em 0.4em;
      border-radius: 999px;
      background: {pill_bg};
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border: 1px solid {pal["pill_border"]};
      box-shadow: {pill_shadow};
      opacity: 0;
      visibility: hidden;
      will-change: transform, opacity;
    }}

    .kt-opt-pill-dot {{
      width: 0.22em;
      height: 0.22em;
      border-radius: 50%;
      background: {pal["hex"]};
      box-shadow: 0 0 10px {pal["hex"]};
    }}

    .kt-opt-pill-label {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {sec_px}px;
      letter-spacing: 0.06em;
      color: {pill_ink};
      padding: 0.14em 0.08em;
    }}
    """


# 1. `kt01_kiss_editorial_2line` (`SIL_KISS_2L`, default 1080x460)
def _build_kt01_kiss_editorial_2line(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker") or props.get("helper_text") or "").strip()
    raw_main = _prop_or_demo("kt01_kiss_editorial_2line", props, "main_text", "chạm đúng nhịp thở")
    line2_text = nfc(props.get("line2_text") or props.get("accent_text") or "").strip()
    if "\n" in raw_main and not line2_text:
        parts = [ln.strip() for ln in raw_main.splitlines() if ln.strip()]
        main_text = parts[0] if parts else raw_main
        line2_text = " ".join(parts[1:]) if len(parts) > 1 else ""
    else:
        main_text = raw_main

    hero_tone = nfc(props.get("hero_tone", "jewel")).lower()
    hero_color = primary_ink if hero_tone == "white" else pal["hex"]
    line2_color = pal["hex"] if hero_tone == "white" else primary_ink

    hero_size = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=86, max_px=108, char_factor=0.55))
    helper_size = int(props.get("kicker_size") or secondary_text_px(props))
    line2_size = int(props.get("accent_size") or max(76, round(hero_size * 0.92)))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.10 if kicker else 0.02))
    line2_at_s = float(props.get("accent_at_s", main_at_s + 0.12))
    badge_at_s = float(props.get("badge_at_s", (line2_at_s if line2_text else main_at_s) + 0.18))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))
    pill_html = _kt_optional_pill_html(props)

    helper_html = ""
    if kicker:
        helper_html = f"""
        <div class="kt01-helper-mask">
          <div class="kt01-helper kt-diacritic-safe" id="kt01Helper">{esc(kicker)}</div>
        </div>
        """

    # v7.7.0: the accent line gets the Swash-Initial Hybrid (SVN-Aaron Script first letter) unless `accent_swash=False`
    swash = bool(props.get("accent_swash", True))
    line2_html = ""
    if line2_text:
        line2_inner = render_swash_hybrid_html_py(line2_text) if swash else esc(line2_text)
        line2_html = f"""
        <div class="kt01-hero-line2 kt-diacritic-safe" id="kt01Line2">{line2_inner}</div>
        """

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt01-helper-mask {{
      overflow: hidden;
      margin-bottom: -0.34em;
      z-index: 3;
    }}

    .kt01-helper {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: {"600" if is_light else "500"};
      font-size: {helper_size}px;
      line-height: 1.05;
      letter-spacing: -0.015em;
      color: {primary_ink};
      text-shadow: {helper_shadow};
      will-change: transform, opacity;
    }}

    /* Negative-leading kiss (`line-height: 0.82` optical equivalence with safe diacritic box) */
    .kt01-hero, .kt01-hero-line2 {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      line-height: 0.82;
      letter-spacing: -0.04em;
      white-space: {"nowrap" if len(main_text) <= 22 else "normal"};
      will-change: transform, opacity, filter;
    }}

    .kt01-hero {{
      font-size: {hero_size}px;
      color: {hero_color};
      margin: -0.18em 0;
      filter: url(#kt01VertBlur);
    }}

    .kt01-hero-line2 {{
      font-size: {line2_size}px;
      color: {line2_color};
      margin-top: -0.44em;
      filter: url(#kt01VertBlur2);
    }}
    """

    body = f"""
    <svg width="0" height="0" style="position:absolute;pointer-events:none;" aria-hidden="true">
      <defs>
        <filter id="kt01VertBlur" x="-20%" y="-35%" width="140%" height="170%">
          <feGaussianBlur id="kt01BlurNode" in="SourceGraphic" stdDeviation="0 0" />
        </filter>
        <filter id="kt01VertBlur2" x="-20%" y="-35%" width="140%" height="170%">
          <feGaussianBlur id="kt01BlurNode2" in="SourceGraphic" stdDeviation="0 0" />
        </filter>
      </defs>
    </svg>
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt01-hero kt-diacritic-safe" id="kt01Hero">{esc(main_text)}</div>
      {line2_html}
      {pill_html}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const LINE2_AT = {line2_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_INNER = {json.dumps(pal["glow_inner"])};
    const GLOW_OUTER = {json.dumps(pal["glow_outer"])};
    const HERO_IS_JEWEL = {json.dumps(hero_tone != "white")};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, MAIN_AT + 0.9);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt01Helper");
      if (helper) {{
        const pH = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pH.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pH) * 105).toFixed(2)}}%, 0)`;
      }}

      const hero = document.getElementById("kt01Hero");
      const blur1 = document.getElementById("kt01BlurNode");
      if (hero) {{
        const pM = timeProgress(tSec, MAIN_AT, 0.26, player3Snap);
        const uGlow = Math.max(0, (tSec - MAIN_AT) / 0.54);
        const hPulse = HERO_IS_JEWEL ? halationPulse(uGlow) : 0.35;
        hero.style.opacity = String(Math.min(1, pM * 1.35).toFixed(4));
        hero.style.transform = `translate3d(0, ${{((1 - pM) * 42).toFixed(2)}}px, 0)`;
        hero.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (HERO_IS_JEWEL
              ? `0 0 ${{(14 * hPulse).toFixed(1)}}px ${{GLOW_INNER}}, 0 0 ${{(34 * hPulse).toFixed(1)}}px ${{GLOW_OUTER}}, ${{BASE_SH}}`
              : BASE_SH);
        if (blur1) {{
          blur1.setAttribute("stdDeviation", `0 ${{(5.0 * (1 - pM)).toFixed(2)}}`);
        }}
      }}

      const line2 = document.getElementById("kt01Line2");
      const blur2 = document.getElementById("kt01BlurNode2");
      if (line2) {{
        const p2 = timeProgress(tSec, LINE2_AT, 0.26, player3Snap);
        line2.style.opacity = String(Math.min(1, p2 * 1.35).toFixed(4));
        line2.style.transform = `translate3d(0, ${{((1 - p2) * 42).toFixed(2)}}px, 0)`;
        line2.style.textShadow = BASE_SH;
        if (blur2) {{
          blur2.setAttribute("stdDeviation", `0 ${{(5.0 * (1 - p2)).toFixed(2)}}`);
        }}
      }}

      applyOptionalPillEntrance(tSec, {badge_at_s}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.26, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 2. `kt02_feather_swash_overlap` (`SIL_FEATHER_SWASH`, default 1080x560)
def _build_kt02_feather_swash_overlap(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = _prop_or_demo("kt02_feather_swash_overlap", props, "main_text", "chuyển động mượt")
    accent_text = _prop_or_demo("kt02_feather_swash_overlap", props, "accent_text", "Chuẩn Điện Ảnh", required=False)

    main_size = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=74, max_px=106, char_factor=0.56))
    if len(main_text) <= 22:  # v7.9.0: the widest blur-in frame (word-spacing guard) must still fit on the nowrap line
        main_size = ws_fit_px(main_text, main_size, [((1 - p) * 7.5, 0.95 + 0.05 * p, -0.038) for p in KT_ENTRANCE_P if p >= 0.15],
                              kt_line_max_w(width, main_size))
    helper_size = int(props.get("kicker_size") or secondary_text_px(props))
    accent_size = int(props.get("accent_size") or max(secondary_text_px(props), min(round(main_size * 0.90), _auto_typo_px(accent_text, width, min_px=58, max_px=96, char_factor=0.50))))
    accent_lines = [accent_text]
    if accent_text and not props.get("accent_size"):  # v7.9.0 repair: the accent line is refitted to the plate like the hero
        accent_size, accent_lines = ws_fit_lines(accent_text, accent_size, [(0.0, 1.0, 0.0)], kt_line_max_w(width, accent_size),
                                                 family="Playfair Display", weight=700, italic=True, swash=True, guarded=False,
                                                 min_px=secondary_text_px(props),
                                                 one_line_min_px=secondary_text_px(props) if len(accent_text) <= 25 else None)
    accent_nowrap = len(accent_lines) > 1 or len(accent_text) <= 25

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.08 if kicker else 0.02))
    accent_at_s = float(props.get("accent_at_s", main_at_s + 0.20))
    badge_at_s = float(props.get("badge_at_s", accent_at_s + 0.18))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    swash_html = kt_lines_html(accent_lines, swash=True)
    pill_html = _kt_optional_pill_html(props)
    helper_html = (
        f'<div class="kt02-helper kt-diacritic-safe" id="kt02Helper">{esc(kicker)}</div>'
        if kicker
        else ""
    )
    wrap_drop = "drop-shadow(0 6px 20px rgba(15, 23, 42, 0.14))" if is_light else "drop-shadow(0 8px 24px rgba(0, 0, 0, 0.55))"
    feather_end = "0.22" if is_light else "0.05"

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt02-helper {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: {"600" if is_light else "500"};
      font-size: {helper_size}px;
      line-height: 1.15;
      letter-spacing: -0.01em;
      color: {primary_ink};
      margin-bottom: -0.44em;
      z-index: 4;
      text-shadow: {helper_shadow};
      will-change: transform, opacity;
    }}

    .kt02-hero-wrap {{
      position: relative;
      z-index: 2;
      filter: {wrap_drop};
    }}

    /* Feather=29 bottom alpha gradient mask */
    .kt02-hero {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {main_size}px;
      line-height: 1.10;
      letter-spacing: -0.038em;
      color: {primary_ink};
      white-space: {"nowrap" if len(main_text) <= 22 else "normal"};
      -webkit-mask-image: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) 52%,
        rgba(0, 0, 0, {feather_end}) 95%
      );
      mask-image: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) 52%,
        rgba(0, 0, 0, {feather_end}) 95%
      );
      will-change: transform, opacity, filter;
    }}

    .kt02-accent {{
      position: relative;
      z-index: 5;
      font-size: {accent_size}px;
      line-height: 1.14;
      color: {pal["hex"]};
      white-space: {"nowrap" if accent_nowrap else "normal"};
      margin-top: -0.76em;
      will-change: transform, opacity, -webkit-mask-image;
    }}

    .kt02-accent .swash-hybrid-init {{
      color: {pal["bright"]};
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt02-hero-wrap">
        <div class="kt02-hero kt-diacritic-safe" id="kt02Hero"{ws_nat0_attr(main_text, weight=800)}>{esc(main_text)}</div>
      </div>
      <div class="kt02-accent kt-diacritic-safe" id="kt02Accent">{swash_html}</div>
      {pill_html}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const GLOW_AMB = {json.dumps(pal["glow_ambient"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.9);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt02Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pK) * 18).toFixed(2)}}px, 0)`;
      }}

      const hero = document.getElementById("kt02Hero");
      if (hero) {{
        const pM = timeProgress(tSec, MAIN_AT, 0.28, player3Snap);
        hero.style.opacity = String(pM.toFixed(4));
        hero.style.transform = `translate3d(0, ${{((1 - pM) * 34).toFixed(2)}}px, 0) scale(${{(0.95 + 0.05 * pM).toFixed(4)}})`;
        hero.style.filter = pM < 0.99 ? `blur(${{((1 - pM) * 7.5).toFixed(2)}}px)` : "none";
      }}

      const acc = document.getElementById("kt02Accent");
      if (acc) {{
        const pA = timeProgress(tSec, ACC_AT, 0.34, velvetC2);
        const uGlow = Math.max(0, (tSec - ACC_AT) / 0.54);
        const hPulse = halationPulse(uGlow);
        // Feather=28 horizontal linear-gradient wipe
        const stopSolid = Math.max(0, pA * 128 - 28);
        const stopFade = Math.min(100, pA * 128);
        const hMask = `linear-gradient(90deg, rgba(0,0,0,1) ${{stopSolid.toFixed(1)}}%, rgba(0,0,0,0) ${{stopFade.toFixed(1)}}%)`;
        acc.style.opacity = String((pA > 0 ? Math.min(1, pA * 1.4) : 0).toFixed(4));
        acc.style.webkitMaskImage = hMask;
        acc.style.maskImage = hMask;
        acc.style.transform = `translate3d(${{((1 - pA) * -14).toFixed(2)}}px, ${{((1 - pA) * 10).toFixed(2)}}px, 0)`;
        acc.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (`0 0 ${{(16 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, ` +
             `0 0 ${{(40 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}, ` +
             `0 0 ${{(74 * hPulse).toFixed(1)}}px ${{GLOW_AMB}}, ` +
             BASE_SH);
      }}

      applyOptionalPillEntrance(tSec, {badge_at_s}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, ACC_AT + 0.28, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# v7.9.0: the kt03 word gap is column-gap + 2 x (diacritic padding - negative word margin) = 0.34 em of ink-box gap.
KT03_COLUMN_GAP_EM = 0.24
KT03_WORD_MARGIN_X_EM = 0.20
KT03_WORD_GAP_EM = round(KT03_COLUMN_GAP_EM + 2 * (KT_DIACRITIC_PAD_X_EM - KT03_WORD_MARGIN_X_EM), 4)


# 3. `kt03_per_word_nonlinear_bloom` (`SIL_WORD_STAGGER`, default 1080x460)
def _normalize_kt03_word_triggers(props: dict[str, Any], default_accent: str, *, theme: str = "dark") -> list[dict[str, Any]]:
    is_light = nfc(theme).strip().lower() == "light"
    primary_ink = "#14171F" if is_light else "#FAFAFA"
    neutral_glow = "rgba(15, 23, 42, 0.10)" if is_light else "rgba(255, 255, 255, 0.28)"
    raw_wt = props.get("word_triggers")
    if isinstance(raw_wt, list) and raw_wt:
        items: list[dict[str, Any]] = []
        for idx, entry in enumerate(raw_wt):
            if isinstance(entry, dict):
                w_txt = nfc(entry.get("word") or entry.get("text") or "").strip()
                if not w_txt:
                    continue
                hue_key = entry.get("hue")
                hue_low = nfc(hue_key or "").strip().lower()
                is_neutral = (not hue_low) or hue_low in ("white", "#fafafa", "#ffffff", "#f8fafc")
                col_pal = None if is_neutral else resolve_jewel_palette(hue_key, theme=theme)
                items.append(
                    {
                        "word": w_txt,
                        "at_s": float(entry.get("at_s", 0.03 + idx * 0.14)),
                        "color": col_pal["hex"] if col_pal else primary_ink,
                        "glow": col_pal["glow_outer"] if col_pal else neutral_glow,
                        "is_jewel": bool(col_pal),
                        "italic": bool(entry.get("italic", False)),
                        "scale": float(entry.get("scale", 1.0)),
                    }
                )
        if items:
            return items

    raw_words = props.get("words")
    if isinstance(raw_words, list) and raw_words:
        words = [nfc(w).strip() for w in raw_words if nfc(w).strip()]
    else:
        main_text = _prop_or_demo("kt03_per_word_nonlinear_bloom", props, "main_text", "cứ Camera bật")
        words = [w for w in main_text.split() if w]

    n = len(words)
    order = props.get("order")
    if not isinstance(order, list) or len(order) != n:
        if bool(props.get("gap_bridge", False)) and n == 3:
            order = [0, 2, 1]
        else:
            order = list(range(n))

    stagger_s = float(props.get("stagger_s", 0.14))
    start_s = float(props.get("main_at_s", 0.03))
    highlight_idx = props.get("highlight_idx")
    if highlight_idx is None:
        highlight_idx = order[-1] if n > 1 else 0

    pal = resolve_jewel_palette(default_accent, theme=theme)
    rank_of = {word_i: step_i for step_i, word_i in enumerate(order)}
    result: list[dict[str, Any]] = []
    for i, w_txt in enumerate(words):
        is_hi = i == int(highlight_idx)
        result.append(
            {
                "word": w_txt,
                "at_s": round(start_s + rank_of.get(i, i) * stagger_s, 4),
                "color": pal["hex"] if is_hi else primary_ink,
                "glow": pal["glow_outer"] if is_hi else neutral_glow,
                "is_jewel": is_hi,
                "italic": bool(props.get("highlight_italic", False) and is_hi),
                "scale": 1.06 if is_hi else 1.0,
            }
        )
    return result


def _build_kt03_per_word_nonlinear_bloom(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    default_accent = nfc(props.get("jewel_accent") or props.get("accent") or "gold")
    pal = resolve_jewel_palette(default_accent, theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    wt_list = _normalize_kt03_word_triggers(props, default_accent, theme=theme_mode)
    joined = " ".join(item["word"] for item in wt_list)
    word_px = int(props.get("main_size") or _auto_typo_px(joined, width, min_px=68, max_px=102, char_factor=0.58))
    wt_list = kt03_gap_safe_entrance(wt_list, word_px)  # v7.9.0: no word-gap collision during the bloom (motion_gate.check_word_gaps)
    helper_px = int(props.get("kicker_size") or secondary_text_px(props))

    words_spans = []
    for idx, item in enumerate(wt_list):
        fam = "'Playfair Display', 'Be Vietnam Pro', serif" if item["italic"] else "'Be Vietnam Pro', sans-serif"
        fst = "italic" if item["italic"] else "normal"
        fw = "700" if item["italic"] else "800"
        words_spans.append(
            f'<span class="kt03-word kt-diacritic-safe" id="kt03Word{idx}" '
            f'style="font-family:{fam};font-style:{fst};font-weight:{fw};color:{item["color"]};">'
            f'{esc(item["word"])}</span>'
        )

    helper_html = (
        f'<div class="kt03-helper kt-diacritic-safe" id="kt03Helper">{esc(kicker)}</div>'
        if kicker
        else ""
    )
    pill_html = _kt_optional_pill_html(props)

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt03-helper {{
      font-size: {helper_px}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      margin-bottom: -0.28em;
      text-shadow: {helper_shadow};
    }}

    .kt03-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: {"flex-start" if align == "left" else ("flex-end" if align == "right" else "center")};
      column-gap: {KT03_COLUMN_GAP_EM}em;
      row-gap: 0.06em;
      font-size: {word_px}px;
      line-height: 1.08;
      letter-spacing: -0.036em;
    }}

    .kt03-word {{
      display: inline-block;
      margin: -0.26em -{KT03_WORD_MARGIN_X_EM}em;
      will-change: transform, opacity, filter;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt03-row">{"".join(words_spans)}</div>
      {pill_html}
    </div>
    """

    last_trig = max((x["at_s"] for x in wt_list), default=0.3)
    js = f"""
    const WORDS_META = {json.dumps(wt_list, ensure_ascii=False)};
    const KICK_AT = {kicker_at_s};
    const LAST_TRIG = {last_trig};
    const EXIT_DUR = {exit_dur_s};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, LAST_TRIG + 0.8);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt03Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pK) * 16).toFixed(2)}}px, 0)`;
      }}

      for (let i = 0; i < WORDS_META.length; i++) {{
        const m = WORDS_META[i];
        const el = document.getElementById("kt03Word" + i);
        if (!el) continue;
        const p = timeProgress(tSec, m.at_s, 0.26, player3Snap);
        const uGlow = Math.max(0, (tSec - m.at_s) / 0.54);
        const hPulse = halationPulse(uGlow);
        const blurPx = (1 - p) * m.blur_px;
        const dx = (i - (WORDS_META.length - 1) / 2) * -10 * (1 - p);
        const dy = (1 - p) * 24;
        const sc = (0.88 + 0.12 * p) * (m.scale || 1.0);
        el.style.opacity = String((p > 0 ? Math.min(1, p * 1.35) : 0).toFixed(4));
        el.style.transform = `translate3d(${{dx.toFixed(2)}}px, ${{dy.toFixed(2)}}px, 0) scale(${{sc.toFixed(4)}})`;
        el.style.filter = blurPx > 0.08 ? `blur(${{blurPx.toFixed(2)}}px)` : "none";
        el.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (m.is_jewel
              ? `0 0 ${{(18 * hPulse).toFixed(1)}}px ${{m.glow}}, 0 0 ${{(42 * hPulse).toFixed(1)}}px ${{m.glow}}, ${{BASE_SH}}`
              : `0 0 ${{(10 * hPulse).toFixed(1)}}px rgba(255,255,255,0.22), ${{BASE_SH}}`);
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", last_trig + 0.18))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, LAST_TRIG + 0.26, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 4. `kt04_ghost_to_focus_stack` (`SIL_GHOST_STACK`, default 1080x520)
def _build_kt04_ghost_to_focus_stack(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "ice_cyan", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    setup_text = _prop_or_demo("kt04_ghost_to_focus_stack", props, ("setup_text", "kicker"), "tưởng chỉ cần nét căng", required=False)
    main_text = _prop_or_demo("kt04_ghost_to_focus_stack", props, "main_text", "chiều sâu quang học")
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_size = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=72, max_px=98, char_factor=0.57))
    if len(main_text) <= 22:  # v7.9.0: widest bokeh frame (blur 16, scale 1.08, letter-spacing 0.08 em) + word-spacing guard fits
        hero_size = ws_fit_px(main_text, hero_size, [((1 - p) * 16.0, 1.08 - 0.08 * p, 0.08 * (1 - p) - 0.038 * p)
                                                     for p in KT_ENTRANCE_P if min(1.0, 1.25 * p) >= 0.15], kt_line_max_w(width, hero_size))
    setup_size = int(props.get("setup_size") or secondary_text_px(props))
    acc_size = int(props.get("accent_size") or max(secondary_text_px(props), round(hero_size * 0.76)))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.34))
    accent_at_s = float(props.get("accent_at_s", main_at_s + 0.24))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    accent_html = ""
    if accent_text:
        accent_html = (
            f'<div class="kt04-accent kt-diacritic-safe" id="kt04Accent">'
            f'{render_swash_hybrid_html_py(accent_text)}</div>'
        )
    pill_html = _kt_optional_pill_html(props)

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt04-setup {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {setup_size}px;
      line-height: 1.16;
      letter-spacing: -0.015em;
      color: {primary_ink};
      margin-bottom: -0.34em;
      text-shadow: {helper_shadow};
      will-change: transform, opacity, filter;
    }}

    .kt04-hero {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_size}px;
      line-height: 1.08;
      color: {pal["hex"]};
      white-space: {"nowrap" if len(main_text) <= 22 else "normal"};
      will-change: transform, opacity, filter, letter-spacing;
    }}

    .kt04-accent {{
      font-size: {acc_size}px;
      line-height: 1.14;
      color: {primary_ink};
      margin-top: -0.46em;
      text-shadow: {hero_shadow};
      will-change: transform, opacity, -webkit-mask-image;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      <div class="kt04-setup kt-diacritic-safe" id="kt04Setup"{ws_nat0_attr(setup_text, weight=600)}>{esc(setup_text)}</div>
      <div class="kt04-hero kt-diacritic-safe" id="kt04Hero"{ws_nat0_attr(main_text, weight=800)}>{esc(main_text)}</div>
      {accent_html}
      {pill_html}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.8);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const pInSetup = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
      const pRecede = timeProgress(tSec, MAIN_AT, 0.30, velvetC2);

      const setup = document.getElementById("kt04Setup");
      if (setup) {{
        const op = pInSetup * (1.0 - (IS_LIGHT ? 0.48 : 0.72) * pRecede);
        const bl = (IS_LIGHT ? 2.4 : 4.5) * pRecede;
        const sc = (0.96 + 0.04 * pInSetup) * (1.0 - 0.06 * pRecede); // -> 0.94
        const dy = (1 - pInSetup) * 18 - 10 * pRecede;
        setup.style.opacity = String(op.toFixed(4));
        setup.style.transform = `translate3d(0, ${{dy.toFixed(2)}}px, 0) scale(${{sc.toFixed(4)}})`;
        setup.style.filter = bl > 0.05 ? `blur(${{bl.toFixed(2)}}px)` : "none";
      }}

      const hero = document.getElementById("kt04Hero");
      if (hero) {{
        const pH = timeProgress(tSec, MAIN_AT, 0.34, velvetC2);
        const uGlow = Math.max(0, (tSec - MAIN_AT) / 0.54);
        const hPulse = halationPulse(uGlow);
        const bokehBlur = (1 - pH) * 16.0;
        const lsEm = 0.08 * (1 - pH) + (-0.038) * pH;
        const scH = 1.08 - 0.08 * pH;
        hero.style.opacity = String((pH > 0 ? Math.min(1, pH * 1.25) : 0).toFixed(4));
        hero.style.letterSpacing = `${{lsEm.toFixed(4)}}em`;
        hero.style.transform = `scale(${{scH.toFixed(4)}})`;
        hero.style.filter = bokehBlur > 0.08 ? `blur(${{bokehBlur.toFixed(2)}}px)` : "none";
        hero.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (`0 0 ${{(16 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, ` +
             `0 0 ${{(38 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}, ` +
             BASE_SH);
      }}

      const acc = document.getElementById("kt04Accent");
      if (acc) {{
        const pA = timeProgress(tSec, ACC_AT, 0.30, velvetC2);
        const s1 = Math.max(0, pA * 126 - 26);
        const s2 = Math.min(100, pA * 126);
        const msk = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        acc.style.opacity = String(pA.toFixed(4));
        acc.style.webkitMaskImage = msk;
        acc.style.maskImage = msk;
        acc.style.transform = `translate3d(0, ${{((1 - pA) * 12).toFixed(2)}}px, 0)`;
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", (accent_at_s if accent_text else main_at_s) + 0.16))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.34, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 5. `kt05_wall_spatial_counterpoint` (`SIL_WALL_HOP`, default 1080x540)
def _normalize_kt05_left_clauses(
    props: dict[str, Any],
    left_text: str,
    kicker_at_s: float,
    turn_at_s: float,
) -> tuple[list[dict[str, Any]], float]:
    """
    Normalizes left-side setup clauses + right-sub accent timestamp so `kt05` NEVER flashes
    a long multi-word sentence as a single simultaneous lump.
    """
    raw_trigs = props.get("left_clauses") or props.get("syllable_triggers")
    clauses: list[dict[str, Any]] = []
    inferred_acc_at: float | None = None

    if isinstance(raw_trigs, list) and raw_trigs:
        for item in raw_trigs:
            if not isinstance(item, dict):
                continue
            tok = nfc(item.get("token") or item.get("text") or item.get("word") or "").strip()
            if not tok:
                continue
            t_at = float(item.get("at_s", kicker_at_s))
            if t_at < turn_at_s - 0.05:
                clauses.append({"text": tok, "at_s": round(t_at, 4)})
            elif t_at > turn_at_s + 0.08 and inferred_acc_at is None:
                inferred_acc_at = round(t_at, 4)

    if not clauses:
        words = left_text.split()
        if len(words) >= 4:
            # Auto-chunk into 2–3 natural spoken phrases staggered before `turn_at_s`
            n_chunks = 3 if len(words) >= 7 else 2
            chunk_sz = max(2, (len(words) + n_chunks - 1) // n_chunks)
            chunks = [" ".join(words[i : i + chunk_sz]) for i in range(0, len(words), chunk_sz)]
            span = max(0.24, (turn_at_s - 0.34) - kicker_at_s)
            step = span / max(1, len(chunks) - 1) if len(chunks) > 1 else 0.0
            for idx_c, ch_txt in enumerate(chunks):
                clauses.append({"text": ch_txt, "at_s": round(kicker_at_s + idx_c * step, 4)})
        elif left_text:
            clauses.append({"text": left_text, "at_s": round(kicker_at_s, 4)})

    acc_at_s = float(
        props.get(
            "accent_at_s",
            inferred_acc_at if inferred_acc_at is not None else (turn_at_s + 0.32),
        )
    )
    return clauses, acc_at_s


def _resolve_kt05_texts(props: dict[str, Any]) -> dict[str, Any]:
    """Single source of the `kt05` texts and clause timing, shared by the builder and `_extract_plain_hero_text`."""
    tpl = "kt05_wall_spatial_counterpoint"
    is_wall_hop = nfc(props.get("mode", "left_right_counter")).lower() == "wall_hop"
    left_text = _prop_or_demo(tpl, props, ("left_text", "setup_text", "kicker"), "chỉ một" if is_wall_hop else "ánh sáng phẳng", required=False)
    right_text = _prop_or_demo(tpl, props, ("right_text", "main_text"), "điểm chạm sáng" if is_wall_hop else "tách khối thật")
    accent_text = nfc(props.get("accent_text", "")).strip()
    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    turn_at_s = float(props.get("turn_at_s", props.get("main_at_s", 0.34 if not is_wall_hop else 0.24)))
    left_clauses, accent_at_s = _normalize_kt05_left_clauses(props, left_text, kicker_at_s, turn_at_s)
    return {
        "is_wall_hop": is_wall_hop, "left_text": left_text, "right_text": right_text, "accent_text": accent_text,
        "kicker_at_s": kicker_at_s, "turn_at_s": turn_at_s, "left_clauses": left_clauses, "accent_at_s": accent_at_s,
    }


def _build_kt05_wall_spatial_counterpoint(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "crimson", theme=theme_mode)
    k5 = _resolve_kt05_texts(props)
    is_wall_hop, right_text, accent_text = k5["is_wall_hop"], k5["right_text"], k5["accent_text"]
    kicker_at_s, turn_at_s, left_clauses, accent_at_s = k5["kicker_at_s"], k5["turn_at_s"], k5["left_clauses"], k5["accent_at_s"]
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    left_px = int(props.get("left_size") or secondary_text_px(props))
    right_px = int(props.get("main_size") or 84)  # v7.9.0: the counterpoint hero stays above the 70 px secondary side (was 64)

    left_w = 500 if is_wall_hop else 700
    left_clauses_html = "\n".join(
        f'<div class="kt05-left-clause kt-diacritic-safe" id="kt05LeftClause_{idx_c}"{ws_nat0_attr(c_item["text"], weight=left_w)}>'
        f'{esc(c_item["text"])}</div>'
        for idx_c, c_item in enumerate(left_clauses)
    )
    accent_sub_html = (
        f'<div class="kt05-right-sub kt-diacritic-safe" id="kt05RightSub">{render_swash_hybrid_html_py(accent_text)}</div>'
        if accent_text
        else ""
    )

    css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt05-canvas {{
      position: relative;
      width: {width}px;
      height: {height}px;
    }}

    .kt05-left-node {{
      position: absolute;
      left: {"24%" if is_wall_hop else "28%"};
      top: {"33%" if is_wall_hop else "48%"};
      transform: translate(-50%, -50%);
      max-width: {int(width * 0.45)}px;
      width: max-content;
      display: flex;
      flex-direction: column;
      align-items: {"flex-start" if is_wall_hop else "center"};
      gap: 4px;
      text-align: {"left" if is_wall_hop else "center"};
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: {"500" if is_wall_hop else "700"};
      font-size: {left_px}px;
      line-height: 1.15;
      letter-spacing: -0.02em;
      color: {primary_ink};
      text-shadow: {hero_shadow};
      will-change: transform, opacity, filter;
    }}

    .kt05-left-clause {{
      opacity: 0;
      white-space: nowrap;
      will-change: transform, opacity, filter;
    }}

    .kt05-right-node {{
      position: absolute;
      left: {"64%" if is_wall_hop else "72%"};
      top: {"62%" if is_wall_hop else "50%"};
      transform: translate(-50%, -50%);
      max-width: {int(width * 0.54 if is_wall_hop else width * 0.46)}px;
      width: max-content;
      text-align: {"left" if is_wall_hop else "center"};
      display: flex;
      flex-direction: column;
      align-items: {"flex-start" if is_wall_hop else "center"};
      will-change: transform, opacity, filter;
    }}

    .kt05-right-main {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {right_px}px;
      line-height: 1.06;
      letter-spacing: -0.038em;
      color: {pal["hex"]};
      will-change: transform, opacity, filter;
    }}

    .kt05-right-sub {{
      font-size: {secondary_text_px(props)}px;
      color: {primary_ink};
      text-shadow: {hero_shadow};
      margin-top: -0.42em;
      will-change: transform, opacity, -webkit-mask-image;
    }}
    """

    body = f"""
    <div class="kt05-canvas" id="ktRig">
      <div class="kt05-left-node" id="kt05Left">
        {left_clauses_html}
      </div>
      <div class="kt05-right-node" id="kt05Right">
        <div class="kt05-right-main kt-diacritic-safe" id="kt05RightMain"{ws_nat0_attr(right_text, weight=800)}>{esc(right_text)}</div>
        {accent_sub_html}
      </div>
    </div>
    """

    js = f"""
    const IS_WALL_HOP = {json.dumps(is_wall_hop)};
    const LEFT_CLAUSES = {json.dumps(left_clauses, ensure_ascii=False)};
    const KICK_AT = {kicker_at_s};
    const TURN_AT = {turn_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, Math.max(TURN_AT, ACC_AT) + 0.55);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const pTurn = timeProgress(tSec, TURN_AT, 0.28, player3Snap);
      const dimFactor = IS_WALL_HOP ? (1.0 - 0.22 * pTurn) : (1.0 - 0.52 * pTurn);

      const leftEl = document.getElementById("kt05Left");
      if (leftEl) {{
        const scRecede = 1.0 - 0.04 * pTurn;
        leftEl.style.opacity = String(dimFactor.toFixed(4));
        leftEl.style.transform = `translate(-50%, -50%) scale(${{scRecede.toFixed(4)}})`;
        leftEl.style.filter = (!IS_WALL_HOP && pTurn > 0.05) ? `blur(${{(1.2 * pTurn).toFixed(2)}}px)` : "none";
      }}

      for (let i = 0; i < LEFT_CLAUSES.length; i++) {{
        const cEl = document.getElementById("kt05LeftClause_" + i);
        if (!cEl) continue;
        const pC = timeProgress(tSec, LEFT_CLAUSES[i].at_s, 0.22, player3Snap);
        const blC = (1.0 - pC) * 7.5;
        const scC = 0.91 + 0.09 * pC;
        const dxC = (1.0 - pC) * -18.0;
        const dyC = (1.0 - pC) * 14.0;
        cEl.style.opacity = String((pC > 0 ? Math.min(1.0, pC * 1.25) : 0.0).toFixed(4));
        cEl.style.transform = `translate3d(${{dxC.toFixed(2)}}px, ${{dyC.toFixed(2)}}px, 0) scale(${{scC.toFixed(4)}})`;
        cEl.style.filter = blC > 0.08 ? `blur(${{blC.toFixed(2)}}px)` : "none";
      }}

      const rightEl = document.getElementById("kt05Right");
      const rightMain = document.getElementById("kt05RightMain");
      const rightSub = document.getElementById("kt05RightSub");
      if (rightEl) {{
        rightEl.style.opacity = String((pTurn > 0 ? 1.0 : 0.0).toFixed(4));
        rightEl.style.transform = "translate(-50%, -50%)";
      }}
      if (rightMain) {{
        const uGlow = Math.max(0, (tSec - TURN_AT) / 0.54);
        const hPulse = halationPulse(uGlow);
        const blurR = (1 - pTurn) * 10.0;
        rightMain.style.opacity = String((pTurn > 0 ? Math.min(1, pTurn * 1.35) : 0).toFixed(4));
        rightMain.style.transform =
          `translate3d(${{((1 - pTurn) * 24).toFixed(2)}}px, ${{((1 - pTurn) * 20).toFixed(2)}}px, 0) scale(${{(0.90 + 0.10 * pTurn).toFixed(4)}})`;
        rightMain.style.filter = blurR > 0.08 ? `blur(${{blurR.toFixed(2)}}px)` : "none";
        rightMain.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (`0 0 ${{(16 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, ` +
             `0 0 ${{(40 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}, ` +
             BASE_SH);
      }}
      if (rightSub) {{
        const pSub = timeProgress(tSec, ACC_AT, 0.26, velvetC2);
        const s1 = Math.max(0, pSub * 126 - 26);
        const s2 = Math.min(100, pSub * 126);
        const msk = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        rightSub.style.opacity = String(pSub.toFixed(4));
        rightSub.style.webkitMaskImage = msk;
        rightSub.style.maskImage = msk;
        rightSub.style.transform = `translate3d(0, ${{((1 - pSub) * 12).toFixed(2)}}px, 0)`;
      }}

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, Math.max(TURN_AT, ACC_AT) + 0.28, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 6. `kt06_bridge_anchor_live_swap` (`SIL_BRIDGE_SWAP`, default 1080x440)
def _normalize_kt06_swaps(props: dict[str, Any], default_accent: str, *, theme: str = "dark") -> list[dict[str, Any]]:
    is_light = nfc(theme).strip().lower() == "light"
    primary_ink = "#14171F" if is_light else "#FAFAFA"
    raw_swaps = props.get("swap_words")
    if not isinstance(raw_swaps, list) or not raw_swaps:
        tpl6 = "kt06_bridge_anchor_live_swap"
        w1 = _prop_or_demo(tpl6, props, "main_text", "màu da thật")
        w2 = _prop_or_demo(tpl6, props, "accent_text", "ánh mắt sống", required=False)
        raw_swaps = [{"text": w1, "at_s": float(props.get("main_at_s", 0.05)), "hue": default_accent, "italic": False}]
        if w2:
            raw_swaps.append({"text": w2, "at_s": float(props.get("swap_at_s", 0.42)), "hue": "emerald", "italic": True})

    out: list[dict[str, Any]] = []
    for idx, raw_item in enumerate(raw_swaps):
        item = {"text": raw_item} if isinstance(raw_item, str) else raw_item
        if isinstance(item, dict):
            txt = nfc(item.get("text") or item.get("word") or "").strip()
            if not txt:
                continue
            hue_raw = nfc(item.get("hue") or default_accent).strip()
            if hue_raw.lower() in ("white", "#fafafa", "#ffffff", "#f8fafc"):
                out.append(
                    {
                        "text": txt,
                        "at_s": float(item.get("at_s", 0.05 + idx * 0.38)),
                        "hex": primary_ink,
                        "glow": "rgba(15, 23, 42, 0.12)" if is_light else "rgba(255, 255, 255, 0.26)",
                        "italic": bool(item.get("italic", False)),
                    }
                )
            else:
                pal = resolve_jewel_palette(hue_raw, theme=theme)
                out.append(
                    {
                        "text": txt,
                        "at_s": float(item.get("at_s", 0.05 + idx * 0.38)),
                        "hex": pal["hex"],
                        "glow": pal["glow_outer"],
                        "italic": bool(item.get("italic", False)),
                    }
                )
    if not out:
        raise ValueError("kt06_bridge_anchor_live_swap: swap_words has no usable text")
    return out


def _build_kt06_bridge_anchor_live_swap(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    default_accent = nfc(props.get("jewel_accent") or props.get("accent") or "gold")
    pal = resolve_jewel_palette(default_accent, theme=theme_mode)
    anchor_text = _prop_or_demo("kt06_bridge_anchor_live_swap", props, ("anchor_text", "kicker"), "giữ trọn", required=False)
    swaps = _normalize_kt06_swaps(props, default_accent, theme=theme_mode)
    anchor_at_s = float(props.get("anchor_at_s", 0.02))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    longest_swap = max((s["text"] for s in swaps), key=len)
    combined = f"{anchor_text} {longest_swap}"
    font_px = int(props.get("main_size") or _auto_typo_px(combined, width, min_px=MIN_OVERLAY_FONT_PX, max_px=90, char_factor=0.58))

    swap_nodes_html = []
    svg_filters_html = []
    for idx, sw in enumerate(swaps):
        fam = "'Playfair Display', 'Be Vietnam Pro', serif" if sw["italic"] else "'Be Vietnam Pro', sans-serif"
        fst = "italic" if sw["italic"] else "normal"
        fw = "700" if sw["italic"] else "800"
        svg_filters_html.append(
            f'<filter id="kt06VBlur{idx}" x="-20%" y="-45%" width="140%" height="190%">'
            f'<feGaussianBlur id="kt06BlurNode{idx}" in="SourceGraphic" stdDeviation="0 0" /></filter>'
        )
        swap_nodes_html.append(
            f'<div class="kt06-swap-item kt-diacritic-safe" id="kt06Swap{idx}"'
            f'{ws_nat0_attr(sw["text"], family="Playfair Display" if sw["italic"] else "Be Vietnam Pro", weight=int(fw), italic=sw["italic"])} '
            f'style="font-family:{fam};font-style:{fst};font-weight:{fw};color:{sw["hex"]};filter:url(#kt06VBlur{idx});">'
            f'{esc(sw["text"])}</div>'
        )

    # Reserve exact slot width in ch/px based on longest swap word
    slot_min_w = max(180, int(len(longest_swap) * font_px * 0.56))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt06-bridge-line {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.24em;
      font-size: {font_px}px;
      line-height: 1.12;
      letter-spacing: -0.035em;
    }}

    .kt06-anchor {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      color: {primary_ink};
      margin: -0.24em -0.18em;
      text-shadow: {hero_shadow};
      will-change: transform, opacity;
    }}

    .kt06-reel-slot {{
      position: relative;
      display: inline-grid;
      align-items: center;
      justify-items: start;
      min-width: {slot_min_w}px;
    }}

    .kt06-swap-item {{
      grid-area: 1 / 1;
      white-space: nowrap;
      margin: -0.24em -0.18em;
      will-change: transform, opacity;
    }}
    """

    body = f"""
    <svg width="0" height="0" style="position:absolute;pointer-events:none;" aria-hidden="true">
      <defs>{"".join(svg_filters_html)}</defs>
    </svg>
    <div class="kt-rig" id="ktRig">
      <div class="kt06-bridge-line">
        <span class="kt06-anchor kt-diacritic-safe" id="kt06Anchor"{ws_nat0_attr(anchor_text, weight=800)}>{esc(anchor_text)}</span>
        <span class="kt06-reel-slot">{"".join(swap_nodes_html)}</span>
      </div>
      {_kt_optional_pill_html(props)}
    </div>
    """

    last_swap_s = max((s["at_s"] for s in swaps), default=0.4)
    js = f"""
    const SWAPS = {json.dumps(swaps, ensure_ascii=False)};
    const ANCHOR_AT = {anchor_at_s};
    const LAST_SWAP_AT = {last_swap_s};
    const EXIT_DUR = {exit_dur_s};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const reelDurSec = 8 / safeFps; // Exact 8f vertical Gaussian blur-push reel!
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, LAST_SWAP_AT + 0.6);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const anchor = document.getElementById("kt06Anchor");
      if (anchor) {{
        const pA = timeProgress(tSec, ANCHOR_AT, 0.22, player3Snap);
        anchor.style.opacity = String(pA.toFixed(4));
        anchor.style.transform = `translate3d(${{((1 - pA) * -18).toFixed(2)}}px, 0, 0)`;
      }}

      for (let i = 0; i < SWAPS.length; i++) {{
        const cur = SWAPS[i];
        const next = i + 1 < SWAPS.length ? SWAPS[i + 1] : null;
        const el = document.getElementById("kt06Swap" + i);
        const blurNode = document.getElementById("kt06BlurNode" + i);
        if (!el) continue;

        const pIn = timeProgress(tSec, cur.at_s, reelDurSec, player3Snap);
        const rawOut = next ? Math.max(0, Math.min(1, (tSec - next.at_s) / reelDurSec)) : 0;
        const pOut = next ? (rawOut >= 0.92 ? 1.0 : Math.min(1.0, velvetC2(rawOut / 0.92))) : 0;

        const op = pIn * (1 - pOut);
        const dy = (1 - pIn) * 46 - pOut * 46;
        const vBlur = (1 - pIn) * 9.5 + pOut * 9.5;
        const uGlow = Math.max(0, (tSec - cur.at_s) / 0.52);
        const hPulse = halationPulse(uGlow);

        if (op <= 0.004) {{
          el.style.opacity = "0";
          el.style.visibility = "hidden";
          el.style.textShadow = "none";
          if (blurNode) blurNode.setAttribute("stdDeviation", "0 0");
        }} else {{
          el.style.opacity = String(op.toFixed(4));
          el.style.visibility = "visible";
          el.style.transform = `translate3d(0, ${{dy.toFixed(2)}}px, 0)`;
          el.style.textShadow = IS_LIGHT
            ? BASE_SH
            : (`0 0 ${{(16 * hPulse).toFixed(1)}}px ${{cur.glow}}, ` +
               `0 0 ${{(36 * hPulse).toFixed(1)}}px ${{cur.glow}}, ` +
               BASE_SH);
          if (blurNode) {{
            blurNode.setAttribute("stdDeviation", `0 ${{vBlur.toFixed(2)}}`);
          }}
        }}
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", last_swap_s + 0.16))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, LAST_SWAP_AT + 0.16, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 7. `kt07_telescoping_char_rollout` (`SIL_CHAR_ACCORDION`, default 1080x440)
def _build_kt07_telescoping_char_rollout(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = _prop_or_demo("kt07_telescoping_char_rollout", props, "main_text", "độ nét điện ảnh")
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=68, max_px=98, char_factor=0.56))
    # v7.9.0 word-spacing guard: a space widens by the slide (<= KT07_SLIDE_PX) its next character still travels; the widest frame
    # (one space at its peak) must fit the plate, and the resting gap is measured with the fixed space box.
    face07 = css_face_file("Be Vietnam Pro", 800)
    kt07_nat = (_mg().natural_word_gap_em(main_text, face07, -0.034, space_em=KT07_SPACE_EM) if face07 else None)
    hero_lines = [main_text]
    if kt07_nat is not None and not props.get("main_size"):
        from PIL import ImageFont

        def _kt07_w(line: str, px: int, _first: bool) -> float:
            rest_w = ImageFont.truetype(str(face07), px).getlength(line.replace(" ", "")) + px * (
                line.count(" ") * KT07_SPACE_EM - 0.034 * len(line.replace(" ", "")) + 0.5)
            return rest_w + (_mg().entrance_word_spacing_em(0.0, 1.0, px, kt07_nat, shift_px=KT07_SLIDE_PX) * px if " " in line else 0.0)
        # one line down to the 64 px floor; v7.9.0 repair: a line that still does not fit wraps into fixed balanced lines
        hero_px, hero_lines = ws_fit_lines(main_text, hero_px, [(0.0, 1.0, 0.0)], width - 2 * KT_PLATE_MARGIN_PX,
                                           one_line_min_px=MIN_OVERLAY_FONT_PX, measure=_kt07_w)
    acc_px = int(props.get("accent_size") or max(secondary_text_px(props), round(hero_px * 0.72)))
    helper_px = int(props.get("kicker_size") or secondary_text_px(props))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.06 if kicker else 0.02))
    stagger_char_s = float(props.get("char_stagger_s", 0.026))  # Exact 26ms/char!
    est_roll_end = main_at_s + max(1, len(main_text)) * stagger_char_s
    accent_at_s = float(props.get("accent_at_s", est_roll_end + 0.10))
    badge_at_s = float(props.get("badge_at_s", (accent_at_s if accent_text else est_roll_end) + 0.12))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    helper_html = f'<div class="kt07-helper kt-diacritic-safe" id="kt07Helper">{esc(kicker)}</div>' if kicker else ""
    accent_html = (
        f'<div class="kt07-accent kt-diacritic-safe" id="kt07Accent">{render_swash_hybrid_html_py(accent_text)}</div>'
        if accent_text
        else ""
    )
    acc_sh = hero_shadow if is_light else f"0 0 18px {pal['glow_inner']}, 0 0 38px {pal['glow_outer']}, {hero_shadow}"
    kt07_nat_attr = (' data-ws-space-nat="%.3f"' % (math.floor((kt07_nat - WS_NAT_MARGIN_EM) * 1000) / 1000)) if kt07_nat is not None else ""

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt07-helper {{
      font-size: {helper_px}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      text-shadow: {helper_shadow};
      margin-bottom: -0.32em;
    }}

    .kt07-line {{
      display: inline-flex;
      flex-wrap: nowrap;
      align-items: baseline;
      justify-content: center;
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_px}px;
      line-height: 1.12;
      letter-spacing: -0.034em;
      padding: 0.32em 0.25em;
    }}

    .kt07-line + .kt07-line {{
      margin-top: -0.56em;
    }}

    .kt07-char {{
      display: inline-block;
      padding: 0.32em 0.16em;
      margin: -0.32em -0.16em;
      -webkit-text-stroke: 0px transparent;
      will-change: transform, opacity, color, text-shadow;
    }}

    .kt07-space {{
      display: inline-block;
      width: {KT07_SPACE_EM}em;
      flex-shrink: 0;
    }}

    .kt07-char {{
      flex-shrink: 0;
    }}

    .kt07-accent {{
      font-size: {acc_px}px;
      color: {pal["hex"]};
      margin-top: -0.52em;
      text-shadow: {acc_sh};
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      {"".join(f'<div class="kt07-line" id="kt07Line{i or ""}" data-pfd-line{kt07_nat_attr}></div>' for i in range(len(hero_lines)))}
      {accent_html}
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const HERO_LINES = {json.dumps(hero_lines, ensure_ascii=False)};
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const CHAR_STAGGER = {stagger_char_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const PAL_BRIGHT = {json.dumps(pal["bright"])};
    const PAL_HEX = {json.dumps(pal["hex"])};
    const PAL_GLOW = {json.dumps(pal["glow_outer"])};
    const PRIMARY_INK = {json.dumps(primary_ink)};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    // Build grapheme spans once (100% Vietnamese NFC diacritic safe via Intl.Segmenter); one `.kt07-line` per fixed hero line,
    // the per-character stagger runs on across the lines
    const lineHosts = Array.from(document.querySelectorAll(".kt07-line"));
    const charNodes = [];
    const SPACE_EM = {KT07_SPACE_EM};
    lineHosts.forEach((lineHost, li) => {{
      lineHost.__spaces = [];
      splitGraphemesVi(HERO_LINES[li] || "").forEach((g) => {{
        if (/^\\s+$/.test(g)) {{
          const sp = document.createElement("span");
          sp.className = "kt07-space";
          sp.textContent = " ";
          lineHost.appendChild(sp);
          lineHost.__spaces.push(sp);
        }} else {{
          const ch = document.createElement("span");
          ch.className = "kt07-char";
          ch.textContent = g;
          lineHost.appendChild(ch);
          charNodes.push(ch);
          lineHost.__spaces.forEach((sp) => {{ if (!sp.__next) sp.__next = ch; }});
        }}
      }});
    }});

    // v7.9.0 word-spacing guard for the telescoping slide: each line keeps its resting width (left-anchored, so settled letters never
    // move) and each space widens by entranceWordSpacingEm(blur, scale, font, resting gap, slide still to travel by the next letter).
    function guardKt07Spaces() {{
      lineHosts.forEach((lineHost) => {{
        const SPACE_NAT = Number(lineHost.dataset.wsSpaceNat);
        if (!Number.isFinite(SPACE_NAT)) return;
        const spaceNodes = lineHost.__spaces;
        if (!lineHost.dataset.restW && (!document.fonts || document.fonts.status === "loaded")) {{
          spaceNodes.forEach((sp) => {{ sp.style.width = `${{SPACE_EM}}em`; }});
          lineHost.style.width = "";
          lineHost.dataset.restW = String(lineHost.offsetWidth);
        }}
        if (lineHost.dataset.restW) {{
          lineHost.style.width = `${{lineHost.dataset.restW}}px`;
          lineHost.style.justifyContent = "flex-start";
        }}
        const f = parseFloat(getComputedStyle(lineHost).fontSize) || 1;
        let blur = 0;
        for (let n = lineHost; n && n.nodeType === 1; n = n.parentElement) {{
          const b = __filterBlurPx(n);
          if (b) blur += b * __screenScale(n);
        }}
        const sc = __screenScale(lineHost);
        spaceNodes.forEach((sp) => {{
          const shift = sp.__next ? Math.max(0, -(sp.__next.__dx || 0)) : 0;
          const extra = entranceWordSpacingEm(blur, sc, f, SPACE_NAT, shift);
          sp.style.width = `${{(SPACE_EM + extra).toFixed(4)}}em`;
        }});
      }});
    }}

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const rollDoneAt = MAIN_AT + charNodes.length * CHAR_STAGGER + 0.24;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, rollDoneAt + 0.6);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt07Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pK) * 16).toFixed(2)}}px, 0)`;
      }}

      // Moving optical specular sheen center across graphemes
      const sheenCenter = ((tSec - MAIN_AT) * 0.85) % 1.6 - 0.3;
      const nChars = Math.max(1, charNodes.length);

      for (let i = 0; i < charNodes.length; i++) {{
        const ch = charNodes[i];
        const birth = MAIN_AT + i * CHAR_STAGGER;
        const uRaw = Math.max(0, Math.min(1, (tSec - birth) / 0.24));
        const pMove = velvetC2(uRaw);
        // Hits opacity: 1 early at u=0.38 for telescoping overlap!
        const op = uRaw <= 0 ? 0 : Math.min(1, uRaw / 0.38);
        const dx = -{KT07_SLIDE_PX:g} * (1 - pMove);

        const posNorm = i / nChars;
        const sheenDist = Math.abs(posNorm - sheenCenter);
        const sheenHit = Math.max(0, 1 - sheenDist / 0.20) * pMove;

        ch.style.opacity = String(op.toFixed(4));
        ch.style.transform = `translate3d(${{dx.toFixed(2)}}px, 0, 0)`;
        ch.__dx = dx;
        ch.style.color = sheenHit > 0.35 ? PAL_BRIGHT : PRIMARY_INK;
        ch.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (sheenHit > 0.08
              ? `0 0 ${{(24 * sheenHit).toFixed(1)}}px ${{PAL_HEX}}, 0 0 ${{(42 * sheenHit).toFixed(1)}}px ${{PAL_GLOW}}, ${{BASE_SH}}`
              : BASE_SH);
      }}

      const acc = document.getElementById("kt07Accent");
      if (acc) {{
        const pA = timeProgress(tSec, ACC_AT, 0.30, velvetC2);
        const s1 = Math.max(0, pA * 126 - 26);
        const s2 = Math.min(100, pA * 126);
        const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        acc.style.opacity = String(pA.toFixed(4));
        acc.style.webkitMaskImage = mask;
        acc.style.maskImage = mask;
        acc.style.transform = `translate3d(0, ${{((1 - pA) * 12).toFixed(2)}}px, 0)`;
      }}

      applyOptionalPillEntrance(tSec, {badge_at_s}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, rollDoneAt, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
      guardKt07Spaces();
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


KT07_SPACE_EM = 0.28   # resting `.kt07-space` box
KT07_SLIDE_PX = 32.0   # per-grapheme slide-in distance (-32 px -> 0)


# 8. `kt08_mist_evaporation_reveal` (`SIL_MIST_GRADIENT`, default 1080x480)
def _build_kt08_mist_evaporation_reveal(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "ice_cyan", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = _prop_or_demo("kt08_mist_evaporation_reveal", props, "main_text", "vùng sáng dịu")
    accent_text = _prop_or_demo("kt08_mist_evaporation_reveal", props, "accent_text", "Tan Nhẹ Như Sương", required=False)
    keep_mist_tail = bool(props.get("keep_mist_tail", False))

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=68, max_px=96, char_factor=0.56))
    acc_px = int(props.get("accent_size") or max(secondary_text_px(props), min(round(hero_px * 0.88), _auto_typo_px(accent_text, width, min_px=54, max_px=88, char_factor=0.50))))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.06 if kicker else 0.03))
    accent_at_s = float(props.get("accent_at_s", main_at_s + 0.22))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    helper_html = f'<div class="kt08-helper kt-diacritic-safe" id="kt08Helper">{esc(kicker)}</div>' if kicker else ""
    mist_inner = render_swash_hybrid_html_py(accent_text)

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt08-helper {{
      font-size: {secondary_text_px(props)}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      text-shadow: {helper_shadow};
      margin-bottom: -0.34em;
    }}

    .kt08-anchor {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_px}px;
      line-height: 1.08;
      letter-spacing: -0.036em;
      color: {primary_ink};
      text-shadow: {hero_shadow};
      will-change: transform, opacity;
    }}

    .kt08-mist-stack {{
      position: relative;
      display: inline-grid;
      margin-top: -0.52em;
    }}

    .kt08-mist-core, .kt08-mist-halo {{
      grid-area: 1 / 1;
      font-size: {acc_px}px;
      line-height: 1.14;
      color: {pal["hex"]};
      white-space: {"nowrap" if len(accent_text) <= 25 else "normal"};
      will-change: transform, opacity, filter, -webkit-mask-image;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt08-anchor kt-diacritic-safe" id="kt08Anchor">{esc(main_text)}</div>
      <div class="kt08-mist-stack">
        <div class="kt08-mist-halo kt-diacritic-safe" id="kt08MistHalo" data-pfd-glow data-ws-follow="kt08MistCore" aria-hidden="true">{mist_inner}</div>
        <div class="kt08-mist-core kt-diacritic-safe" id="kt08MistCore"{ws_nat0_attr(accent_text, family="Playfair Display", weight=700, italic=True)}>{mist_inner}</div>
      </div>
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const ACC_AT = {accent_at_s};
    const KEEP_TAIL = {json.dumps(keep_mist_tail)};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.9);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt08Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
      }}

      const anchor = document.getElementById("kt08Anchor");
      if (anchor) {{
        const pM = timeProgress(tSec, MAIN_AT, 0.26, player3Snap);
        anchor.style.opacity = String(pM.toFixed(4));
        anchor.style.transform = `translate3d(0, ${{((1 - pM) * 28).toFixed(2)}}px, 0)`;
      }}

      const core = document.getElementById("kt08MistCore");
      const halo = document.getElementById("kt08MistHalo");
      if (core && halo) {{
        const pMist = timeProgress(tSec, ACC_AT, 0.44, velvetC2);
        const s1 = Math.max(0, pMist * 136 - 36);
        const s2 = Math.min(100, pMist * 136);
        const mistMask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        const endBlur = KEEP_TAIL ? 1.8 : 0.0;
        const curBlur = 18.0 * (1 - pMist) + endBlur * pMist;
        const dy = (1 - pMist) * 14;

        core.style.opacity = String((pMist > 0 ? Math.min(1, pMist * 1.25) : 0).toFixed(4));
        core.style.webkitMaskImage = mistMask;
        core.style.maskImage = mistMask;
        core.style.transform = `translate3d(0, ${{dy.toFixed(2)}}px, 0)`;
        core.style.filter = curBlur > 0.06 ? `blur(${{curBlur.toFixed(2)}}px)` : "none";
        core.style.textShadow = IS_LIGHT
          ? BASE_SH
          : `0 0 18px ${{GLOW_IN}}, 0 0 42px ${{GLOW_OUT}}, ${{BASE_SH}}`;

        halo.style.opacity = String((KEEP_TAIL ? 0.56 * pMist : 0.42 * (1 - pMist) * (pMist > 0 ? 1 : 0)).toFixed(4));
        halo.style.webkitMaskImage = mistMask;
        halo.style.maskImage = mistMask;
        halo.style.filter = `blur(${{(KEEP_TAIL ? 6.5 : 12.0).toFixed(1)}}px)`;
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", accent_at_s + 0.16))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, ACC_AT + 0.42, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 9. `kt09_strike_myth_laser_2phase` (`SIL_MYTH_STRIKE`, default 1080x500)
def _build_kt09_strike_myth_laser_2phase(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = _prop_or_demo("kt09_strike_myth_laser_2phase", props, "main_text", "nhìn giả trân")
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=74, max_px=104, char_factor=0.56))
    # v7.9.0: widest slam frame (scale 1.15, blur 10) + word-spacing guard fits every line; the line breaks are fixed (a short line
    # shrinks to stay one line, a long one wraps into balanced lines) so the widening never reflows the hero mid-entrance
    hero_px, hero_lines = ws_fit_lines(main_text, hero_px, [((1 - p) * 10.0, 1.15 - 0.15 * p, -0.038) for p in KT_ENTRANCE_P
                                                            if min(1.0, 1.2 * p) >= 0.15], kt_line_max_w(width, hero_px),
                                       one_line_min_px=MIN_OVERLAY_FONT_PX if len(main_text) <= 22 else None)
    laser_spans = _kt_line_spans(hero_lines, hero_px)
    acc_px = int(props.get("accent_size") or max(secondary_text_px(props), round(hero_px * 0.62)))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.04))
    slash_at_s = float(props.get("slash_at_s", main_at_s + 0.24))
    accent_at_s = float(props.get("accent_at_s", slash_at_s + 0.14))
    badge_at_s = float(props.get("badge_at_s", slash_at_s + 0.06))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    helper_html = f'<div class="kt09-helper kt-diacritic-safe" id="kt09Helper">{esc(kicker)}</div>' if kicker else ""
    accent_html = (
        f'<div class="kt09-truth kt-diacritic-safe" id="kt09Truth">{esc(accent_text)}</div>'
        if accent_text
        else ""
    )
    truth_sh = hero_shadow if is_light else f"0 0 18px {pal['glow_inner']}, 0 0 38px {pal['glow_outer']}, {hero_shadow}"

    css = _kt_shared_css(pal, width, align, theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt09-helper {{
      font-size: {secondary_text_px(props)}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      text-shadow: {helper_shadow};
      margin-bottom: -0.32em;
    }}

    .kt09-myth-box {{
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}

    .kt09-myth-hero {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_px}px;
      line-height: 1.08;
      letter-spacing: -0.038em;
      color: {primary_ink};
      white-space: nowrap;
      text-shadow: {hero_shadow};
      will-change: transform, opacity, filter;
    }}

    /* Glowing SVG #FF4D5E razor laser slash across 56% x-height of every hero line */
    .kt09-laser-svg {{
      position: absolute;
      height: 36px;
      transform: translateY(-50%) scaleX(0);
      transform-origin: left center;
      pointer-events: none;
      overflow: visible;
      z-index: 6;
      will-change: transform, opacity;
    }}

    .kt09-truth {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {acc_px}px;
      line-height: 1.16;
      letter-spacing: -0.025em;
      color: {pal["hex"]};
      margin-top: -0.34em;
      text-shadow: {truth_sh};
      will-change: transform, opacity, -webkit-mask-image;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt09-myth-box">
        <div class="kt09-myth-hero kt-diacritic-safe" id="kt09Hero"{ws_nat0_attr(main_text, weight=800)}>{kt_lines_html(hero_lines)}</div>
        {"".join(_kt09_laser_svg(i, n_lines=len(hero_lines), span=sp) for i, sp in enumerate(laser_spans))}
      </div>
      {accent_html}
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const SLASH_AT = {slash_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.8);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt09Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.20, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
      }}

      const pSlam = timeProgress(tSec, MAIN_AT, 0.22, player3Snap);
      const pSlash = timeProgress(tSec, SLASH_AT, 0.18, player3Snap);

      const hero = document.getElementById("kt09Hero");
      if (hero) {{
        const sc = 1.15 - 0.15 * pSlam;
        const bl = (1 - pSlam) * 10.0;
        const struckOp = pSlam * (1.0 - 0.22 * pSlash);
        hero.style.opacity = String((pSlam > 0 ? Math.min(1, struckOp * 1.2) : 0).toFixed(4));
        hero.style.transform = `scale(${{sc.toFixed(4)}})`;
        hero.style.filter = bl > 0.08 ? `blur(${{bl.toFixed(2)}}px)` : "none";
      }}

      document.querySelectorAll(".kt09-laser-svg").forEach((laser) => {{
        laser.style.opacity = String((pSlash > 0 ? 1 : 0).toFixed(4));
        laser.style.transform = `translateY(-50%) scaleX(${{pSlash.toFixed(4)}})`;
      }});

      const truth = document.getElementById("kt09Truth");
      if (truth) {{
        const pT = timeProgress(tSec, ACC_AT, 0.28, velvetC2);
        const s1 = Math.max(0, pT * 126 - 26);
        const s2 = Math.min(100, pT * 126);
        const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
        truth.style.opacity = String(pT.toFixed(4));
        truth.style.webkitMaskImage = mask;
        truth.style.maskImage = mask;
        truth.style.transform = `translate3d(0, ${{((1 - pT) * 14).toFixed(2)}}px, 0)`;
      }}

      applyOptionalPillEntrance(tSec, {badge_at_s}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, SLASH_AT + 0.24, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


def _kt_line_spans(lines: Sequence[str], font_px: int, weight: int = 800) -> list[float]:
    """Each fixed line's resting width as a fraction of the widest line (centred lines; PIL metrics of the drawn face)."""
    face = css_face_file("Be Vietnam Pro", weight)
    if face is None or len(lines) < 2:
        return [1.0] * len(lines)
    from PIL import ImageFont
    ft = ImageFont.truetype(str(face), font_px)
    ws = [ft.getlength(ln) for ln in lines]
    return [w / max(max(ws), 1e-6) for w in ws]


KT09_LINE_H = 1.08       # `.kt09-myth-hero` line-height
KT09_PAD_Y_EM = 0.32     # `.kt-diacritic-safe` vertical padding
KT09_SLASH_Y = 0.5955    # the slash crosses this fraction of a line box (56 % of the one-line myth box, x-height)


def _kt09_laser_svg(i: int, *, n_lines: int, span: float) -> str:
    """v7.9.0 repair: one laser slash per hero line (a wrapped myth line is struck on every line, not just the first)."""
    top = (KT09_PAD_Y_EM + (i + KT09_SLASH_Y) * KT09_LINE_H) / (2 * KT09_PAD_Y_EM + n_lines * KT09_LINE_H) * 100
    w = 96.0 * span
    lid = "kt09Laser" if i == 0 else f"kt09Laser{i}"
    return f"""<svg class="kt09-laser-svg" id="{lid}" viewBox="0 0 600 36" preserveAspectRatio="none"
             style="left:{(100 - w) / 2:.2f}%;width:{w:.2f}%;top:{top:.2f}%;">
          <defs>
            <filter id="laserBloom{i}" x="-15%" y="-180%" width="130%" height="460%">
              <feGaussianBlur stdDeviation="5.5" result="b1"/>
              <feMerge>
                <feMergeNode in="b1"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <line x1="0" y1="18" x2="600" y2="18" stroke="#FF4D5E" stroke-width="11" stroke-linecap="round" opacity="0.58" filter="url(#laserBloom{i})"/>
          <line x1="0" y1="18" x2="600" y2="18" stroke="#FF4D5E" stroke-width="6.5" stroke-linecap="round"/>
          <line x1="4" y1="18" x2="596" y2="18" stroke="#FFE4E6" stroke-width="2.4" stroke-linecap="round"/>
        </svg>
"""


# 10. `kt10_cursor_bars_pillar_gate` (`SIL_CURSOR_HUD`, default 1080x460)
def _build_kt10_cursor_bars_pillar_gate(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald", theme=theme_mode)
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = _prop_or_demo("kt10_cursor_bars_pillar_gate", props, "main_text", "3 bước khóa ảnh")

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=64, max_px=88, char_factor=0.58, usable_ratio=0.78))
    helper_px = int(props.get("kicker_size") or secondary_text_px(props))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.08 if kicker else 0.03))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))
    # v7.9.3: accent_text was silently dropped; it now lands under the gate as a secondary line on its spoken onset
    accent_text = nfc(props.get("accent_text", "")).strip()
    acc_raw = props.get("accent_at_s")
    accent_at_s = float(acc_raw) if acc_raw is not None else main_at_s + 0.30

    helper_html = f'<div class="kt10-helper kt-diacritic-safe" id="kt10Helper">{esc(kicker)}</div>' if kicker else ""
    accent_html = f'<div class="kt10-accent kt-diacritic-safe" id="kt10Accent">{esc(accent_text)}</div>' if accent_text else ""
    pillar_h = max(84, round(hero_px * 1.24))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt10-helper {{
      font-size: {helper_px}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      margin-bottom: -0.18em;
      text-shadow: {helper_shadow};
    }}

    .kt10-accent {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-size: {helper_px}px;
      font-weight: 600;
      color: {primary_ink};
      margin-top: -0.12em;
      text-shadow: {helper_shadow};
      opacity: 0;
    }}

    .kt10-gate-wrap {{
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 28px;
    }}

    .kt10-hero {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_px}px;
      line-height: 1.10;
      letter-spacing: -0.034em;
      color: {primary_ink};
      white-space: {"nowrap" if len(main_text) <= 24 else "normal"};
      text-shadow: {hero_shadow};
      will-change: clip-path, opacity, transform;
    }}

    .kt10-pillar {{
      position: absolute;
      top: 50%;
      width: 3.5px;
      height: {pillar_h}px;
      border-radius: 99px;
      background: {pal["hex"]};
      box-shadow: 0 0 16px {pal["glow_inner"]}, 0 0 34px {pal["glow_outer"]};
      transform: translate(-50%, -50%);
      pointer-events: none;
    }}

    .kt10-pin {{
      position: absolute;
      left: 50%;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: {"#FFFFFF" if is_light else pal["bright"]};
      border: 1.5px solid {pal["hex"]};
      box-shadow: 0 0 10px {pal["glow_inner"]};
      transform: translateX(-50%);
    }}

    .kt10-pin-top {{ top: -6px; }}
    .kt10-pin-bot {{ bottom: -6px; }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      {helper_html}
      <div class="kt10-gate-wrap">
        <div class="kt10-hero kt-diacritic-safe" id="kt10Hero">{esc(main_text)}</div>
        <div class="kt10-pillar" id="kt10PillarL">
          <span class="kt10-pin kt10-pin-top"></span>
          <span class="kt10-pin kt10-pin-bot"></span>
        </div>
        <div class="kt10-pillar" id="kt10PillarR">
          <span class="kt10-pin kt10-pin-top"></span>
          <span class="kt10-pin kt10-pin-bot"></span>
        </div>
      </div>
      {accent_html}
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, Math.max(MAIN_AT + 0.9, ACC_AT + 0.4));

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const helper = document.getElementById("kt10Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pK) * 14).toFixed(2)}}px, 0)`;
      }}

      const accEl = document.getElementById("kt10Accent");
      if (accEl) {{
        const pA = timeProgress(tSec, ACC_AT, 0.22, velvetC2);
        accEl.style.opacity = String(pA.toFixed(4));
        accEl.style.transform = `translate3d(0, ${{((1 - pA) * 12).toFixed(2)}}px, 0)`;
      }}

      const pGate = timeProgress(tSec, MAIN_AT, 0.34, velvetC2);
      const pIgnite = timeProgress(tSec, Math.max(0, MAIN_AT - 0.04), 0.12, player3Snap);
      const uGlow = Math.max(0, (tSec - MAIN_AT) / 0.54);
      const hPulse = halationPulse(uGlow);

      const hero = document.getElementById("kt10Hero");
      if (hero) {{
        const insetPct = 50 * (1 - pGate);
        // -30% vertical inset headroom protects stacked Vietnamese diacritics 100%!
        const cp = `inset(-30% ${{insetPct.toFixed(2)}}% -30% ${{insetPct.toFixed(2)}}%)`;
        hero.style.opacity = String((pGate > 0.01 ? 1 : 0).toFixed(4));
        hero.style.clipPath = cp;
        hero.style.webkitClipPath = cp;
        hero.style.transform = `scale(${{(0.97 + 0.03 * pGate).toFixed(4)}})`;
      }}

      const pL = document.getElementById("kt10PillarL");
      const pR = document.getElementById("kt10PillarR");
      const leftPct = 50 - 48.5 * pGate;
      const rightPct = 50 + 48.5 * pGate;
      const glowCss = IS_LIGHT
        ? `0 4px 14px rgba(15, 23, 42, 0.14), 0 0 ${{(10 * hPulse).toFixed(1)}}px ${{GLOW_IN}}`
        : `0 0 ${{(18 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, 0 0 ${{(38 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}`;
      if (pL) {{
        pL.style.opacity = String(pIgnite.toFixed(4));
        pL.style.left = `${{leftPct.toFixed(2)}}%`;
        pL.style.boxShadow = glowCss;
      }}
      if (pR) {{
        pR.style.opacity = String(pIgnite.toFixed(4));
        pR.style.left = `${{rightPct.toFixed(2)}}%`;
        pL && (pR.style.boxShadow = glowCss);
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", main_at_s + 0.18))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.34, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# v7.9.0 repair: kt11 svg_arc copy fit. A <textPath> silently drops every glyph whose midpoint falls off its path, so the arc copy is
# laid out in Python against the real path length (PIL advance ~= Chrome getComputedTextLength), widened / raised inside the plate
# margin, wrapped onto two concentric arcs, or handed to the tilt mode -- never dropped, never below MIN_OVERLAY_FONT_PX. The browser
# audit (`textPaths`, TextPathOverflowError) is the hard check.
KT11_ARC_DY_PX = 8              # the arc text baseline sits this far outside its path (<text dy="-8">)
KT11_ARC_LINE_GAP_EM = 1.38     # radial step between two concentric arcs (Be Vietnam Pro cell 1.27 em + air)
KT11_ARC_FIT_SAFETY = 1.02      # PIL advance vs Chrome getComputedTextLength (measured within 0.1 %)
KT11_ARC_RX0, KT11_ARC_RY0 = 390, 145
KT11_ARC_HOLD_SCALE = 1.0275   # applyHoldMicroFloat peak scale (1 + 0.024 creep + 0.0035 wobble) about the plate centre
KT_EXIT_BLUR_PX = 5.5          # applyCleanExit peak CSS blur (COMMON_STUDIO_JS): the page word-gap guard widens the spaces for it
KT_EXIT_MIN_SCALE = 0.972      # applyCleanExit end scale (1 - 0.028)
KT11_ARC_SUB_H_EM = 1.5        # accent INK height under the arc in secondary px (the 1.5x swash initial; its line box is ~0.6 em taller)


@functools.lru_cache(maxsize=4096)
def _kt11_half_ellipse(rx: float, ry: float, n: int = 360) -> tuple[tuple[float, ...], ...]:
    """Samples of the clockwise top half-ellipse from (-rx, 0) to (rx, 0) around (cx, base_y): (x, y, s, ux, uy) per sample, s =
    arc length so far, (ux, uy) = the glyph 'up' normal (outward)."""
    out, s, prev = [], 0.0, None
    for i in range(n + 1):
        t = math.pi * i / n
        x, y = -rx * math.cos(t), -ry * math.sin(t)
        if prev is not None:
            s += math.hypot(x - prev[0], y - prev[1])
        nx, ny = -ry * math.cos(t), -rx * math.sin(t)
        nn = math.hypot(nx, ny) or 1.0
        out.append((x, y, s, nx / nn, ny / nn))
        prev = (x, y)
    return tuple(out)


def kt11_arc_ink_box(rx: float, ry: float, s0: float, s1: float, asc: float, desc: float, pad: float = 0.0) -> tuple[float, float, float, float]:
    """Box (relative to the arc centre on the baseline) of the glyph cells drawn on path length [s0, s1] of the half-ellipse:
    each cell spans dy - desc .. dy + asc along the outward normal; `pad` grows it on every side."""
    pts = _kt11_half_ellipse(float(rx), float(ry))
    xs, ys = [], []
    for x, y, s, ux, uy in pts:
        if s0 - 1.0 <= s <= s1 + 1.0:
            for hh in (KT11_ARC_DY_PX - desc, KT11_ARC_DY_PX + asc):
                xs.append(x + ux * hh)
                ys.append(y + uy * hh)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def kt11_arc_path_d(cx: float, base_y: float, rx: float, ry: float, ext: float = 0.0) -> str:
    """SVG path of the kt11 arc: the clockwise top half-ellipse, run on past both ends (down the ellipse) by `ext` px of path length
    (the exit's word-gap widening; `startOffset="50%"` keeps the text centred on the top)."""
    if ext <= 0:
        return f"M {cx - rx},{base_y} A {rx},{ry} 0 0,1 {cx + rx},{base_y}"
    t, s, prev = 0.0, 0.0, (rx, 0.0)
    while s < ext and t < 0.45 * math.pi:
        t += 0.002
        cur = (rx * math.cos(t), ry * math.sin(t))
        s += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    x0, y0 = cx - rx * math.cos(t), base_y + ry * math.sin(t)
    x1 = cx + rx * math.cos(t)
    return f"M {x0:.2f},{y0:.2f} A {rx},{ry} 0 1,1 {x1:.2f},{y0:.2f}"


def _kt11_arc_candidates(width: int) -> list[tuple[int, int]]:
    """(rx, ry) in order of preference: the historical flat arc widened first (ry = 0.42 rx), then raised towards a semicircle."""
    rxs = range(KT11_ARC_RX0, int(width / 2 - KT_PLATE_MARGIN_PX) + 1, 5)
    out = [(rx, max(KT11_ARC_RY0, int(rx * 0.42))) for rx in rxs]
    for k in range(46, 101, 4):
        out += [(rx, max(KT11_ARC_RY0, int(rx * k / 100))) for rx in rxs]
    return out


def kt11_arc_plan(text: str, start_px: int, width: int, height: int, *, floor_px: int | None = None, sub_px: int = 0,
                  rx: int | None = None, ry: int | None = None) -> dict[str, Any] | None:
    """Fit the kt11 arc copy: one arc (font `start_px` down to `floor_px`), else two concentric arcs split at a word boundary. Every
    line must fit its path (x KT11_ARC_FIT_SAFETY) and every glyph cell stay KT_PLATE_MARGIN_PX inside the plate sides; plans that
    also fit the plate height (with the `sub_px` accent under the arc) win. Returns {px, lines, arcs, box} (box relative to the arc
    centre on the baseline) or None (no arc fits: use the tilt mode). Explicit `rx` / `ry` = no fit, one line, as given."""
    from PIL import ImageFont

    face = css_face_file("Be Vietnam Pro", 800)
    floor_px = MIN_OVERLAY_FONT_PX if floor_px is None else floor_px
    words = text.split()
    sub_h = (KT11_ARC_SUB_H_EM + 0.25) * sub_px if sub_px else 0.0  # + the gap above it

    def metrics(px):
        if face is None:
            return (lambda t, widest=False: 0.56 * px * len(t)), 1.0 * px, 0.27 * px
        ft = ImageFont.truetype(str(face), px)
        asc, desc = ft.getmetrics()
        mg = _mg()

        def guarded(t, widest):  # v7.9.0 repair: the page word-gap guard widens every space at rest and through the exit blur
            nat = mg.natural_word_gap_em(t, face, -0.02)  # PIL vs Chrome metrics: covered by KT11_ARC_FIT_SAFETY on the fit
            if nat is None:
                return 0.0
            em = mg.entrance_word_spacing_em(0.0, 1.0, px, nat)
            if widest:  # the fit needs the widest frame (exit blur); the ink box / centring the resting text
                em = max(em, mg.entrance_word_spacing_em(KT_EXIT_BLUR_PX * KT11_ARC_HOLD_SCALE, KT_EXIT_MIN_SCALE, px, nat))
            return t.count(" ") * em * px
        return (lambda t, widest=False: ft.getlength(t) - 0.02 * px * len(t) + guarded(t, widest)), float(asc), float(desc)

    def plan_for(px, lines, arcs, meas, asc, desc):
        pad = 0.1 * px + 4
        box = None
        for (a, b), ln in zip(arcs, lines):
            total = _kt11_half_ellipse(float(a), float(b))[-1][2]
            need = meas(ln)
            s0 = max(0.0, (total - need) / 2)
            bx = kt11_arc_ink_box(a, b, s0, min(total, s0 + need), asc, desc, pad)
            box = bx if box is None else (min(box[0], bx[0]), min(box[1], bx[1]), max(box[2], bx[2]), max(box[3], bx[3]))
        # v7.9.0 repair: the exit blur widens the spaces (page word-gap guard): each path runs on past both ends of the half-ellipse
        # by half that extra length, so the centred text never drops a glyph on the exit (the resting text keeps the half-ellipse)
        ext = [max(0.0, (meas(ln, widest=True) - meas(ln)) * KT11_ARC_FIT_SAFETY / 2) + (4.0 if " " in ln else 0.0) for ln in lines]
        return {"px": px, "lines": list(lines), "arcs": [(int(a), int(b)) for a, b in arcs], "box": box, "ext": ext,
                "content_h": box[3] - box[1] + sub_h}

    if rx is not None or ry is not None or face is None:
        meas, asc, desc = metrics(start_px)
        return plan_for(start_px, [text], [(rx or KT11_ARC_RX0, ry or KT11_ARC_RY0)], meas, asc, desc)

    lim = (width / 2 - KT_PLATE_MARGIN_PX) / KT11_ARC_HOLD_SCALE  # the hold creep scales the ink about the plate centre
    cands = _kt11_arc_candidates(width)
    loose = []  # plans that fit the arcs but not the plate height: the plate grows to the shortest one
    for n_lines in (1, 2):
        splits = [[text]] if n_lines == 1 else [[" ".join(words[:k]), " ".join(words[k:])] for k in range(1, len(words))]
        if not splits:
            continue
        for px in range(int(start_px), int(floor_px) - 1, -1):
            meas, asc, desc = metrics(px)
            needs = [[meas(t) * KT11_ARC_FIT_SAFETY for t in sp] for sp in splits]
            gap = KT11_ARC_LINE_GAP_EM * px
            for a0, b0 in cands:
                arcs = [(a0 - k * gap, b0 - k * gap) for k in range(n_lines)]
                if arcs[-1][0] < 0.5 * a0 or arcs[-1][1] < 0.3 * arcs[-1][0]:
                    continue
                lens = [_kt11_half_ellipse(float(a), float(b))[-1][2] for a, b in arcs]
                fits = [(max(n / L for n, L in zip(nd, lens)), sp) for sp, nd in zip(splits, needs) if all(n <= L for n, L in zip(nd, lens))]
                if not fits:
                    continue
                plan = plan_for(px, min(fits)[1], arcs, meas, asc, desc)
                b = plan["box"]
                if b[0] < -lim or b[2] > lim:
                    continue
                if plan["content_h"] <= height - 2 * KT_PLATE_MARGIN_PX:
                    return plan
                loose.append(plan)
                break  # larger arcs at this size are only taller
    return min(loose, key=lambda q: q["content_h"]) if loose else None


# 11. `kt11_cranial_svg_arc_or_tilt` (`SIL_TILT_OR_ARC`, default 1080x620)
def _build_kt11_cranial_svg_arc_or_tilt(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    mode = nfc(props.get("mode", "svg_arc")).lower()
    is_tilt = mode in ("tilted_chest", "tilt")
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    plan = None
    if not is_tilt:
        main_text = _prop_or_demo("kt11_cranial_svg_arc_or_tilt", props, "main_text", "vòng sáng điện ảnh tự nhiên")
        accent_text = nfc(props.get("accent_text", "")).strip()
        arc_px = int(props.get("main_size") or max(secondary_text_px(props), min(84, int(760 / max(9.0, len(main_text) * 0.54)))))
        sec_px = secondary_text_px(props)
        # v7.9.0 repair: fit the copy to the arc (widen / raise inside the plate margin, two arcs, else the tilt mode below)
        plan_h = min(height, int(TEMPLATE_DEFAULTS["kt11_cranial_svg_arc_or_tilt"]["height"]))  # stable while the plate fit grows it
        plan = kt11_arc_plan(main_text, arc_px, width, plan_h, floor_px=arc_px if props.get("main_size") else MIN_OVERLAY_FONT_PX,
                             sub_px=sec_px if accent_text else 0, rx=int(props["arc_rx"]) if "arc_rx" in props else None,
                             ry=int(props["arc_ry"]) if "arc_ry" in props else None)
        if plan is None:
            is_tilt = True
            props = dict(props, sub_text=props.get("sub_text") or accent_text)
    if not is_tilt:
        main_at_s = float(props.get("main_at_s", 0.04))
        accent_at_s = float(props.get("accent_at_s", main_at_s + 0.28))
        arc_px = plan["px"]
        cx = width // 2
        box = plan["box"]
        sub_gap = 0.25 * sec_px
        content_bottom = box[3] + (sub_gap + KT11_ARC_SUB_H_EM * sec_px if accent_text else 0.0)
        base_y = int(round(height / 2 - (box[1] + content_bottom) / 2))  # the arc (+ accent) is centred in the plate
        sub_top = base_y + box[3] + sub_gap - 0.32 * sec_px  # minus the .kt-diacritic-safe top padding
        arc_paths = "\n              ".join(
            f'<path id="kt11HaloPath{k or ""}" d="{kt11_arc_path_d(cx, base_y, a, b, ext)}" fill="none" />'
            for k, ((a, b), ext) in enumerate(zip(plan["arcs"], plan.get("ext") or [0.0] * len(plan["arcs"]))))
        arc_texts = "\n              ".join(
            f'<text class="kt11-arc-text" dy="-{KT11_ARC_DY_PX}">\n                <textPath href="#kt11HaloPath{k or ""}" startOffset="50%" '
            f'text-anchor="middle">{esc(ln)}</textPath>\n              </text>' for k, ln in enumerate(plan["lines"]))

        sub_html = (
            f'<div class="kt11-arc-sub kt-diacritic-safe" id="kt11ArcSub">{render_swash_hybrid_html_py(accent_text)}</div>'
            if accent_text
            else ""
        )
        halo_filter_xml = (
            """
              <filter id="kt11WarmHalo" x="-25%" y="-35%" width="150%" height="170%">
                <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#0F172A" flood-opacity="0.14" result="drop" />
                <feMerge>
                  <feMergeNode in="drop" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            """
            if is_light
            else """
              <filter id="kt11WarmHalo" x="-25%" y="-35%" width="150%" height="170%">
                <feGaussianBlur stdDeviation="8" result="haloBlur" />
                <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.52" result="drop" />
                <feMerge>
                  <feMergeNode in="haloBlur" />
                  <feMergeNode in="drop" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            """
        )

        css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
        .kt11-arc-stage {{
          position: relative;
          width: {width}px;
          height: {height}px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
        }}

        .kt11-arc-svg {{
          width: {width}px;
          height: {height}px;
          overflow: visible;
        }}

        .kt11-arc-text {{
          font-family: 'Be Vietnam Pro', sans-serif;
          font-weight: 800;
          font-size: {arc_px}px;
          letter-spacing: -0.02em;
          fill: {pal["hex"]};
        }}

        .kt11-arc-sub {{
          position: absolute;
          top: {sub_top:.1f}px;
          font-size: {sec_px}px;
          color: {primary_ink};
          text-shadow: {hero_shadow};
        }}
        """

        body = f"""
        <div class="kt11-arc-stage" id="ktRig">
          <svg class="kt11-arc-svg" viewBox="0 0 {width} {height}">
            <defs>
              {arc_paths}
              <linearGradient id="kt11ClockSweep" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop id="kt11StopSolid" offset="0%" stop-color="#FFFFFF" stop-opacity="1" />
                <stop id="kt11StopFade" offset="0%" stop-color="#FFFFFF" stop-opacity="0" />
              </linearGradient>
              <mask id="kt11ArcMask">
                <rect x="0" y="0" width="{width}" height="{height}" fill="url(#kt11ClockSweep)" />
              </mask>
              {halo_filter_xml}
            </defs>
            <g mask="url(#kt11ArcMask)" filter="url(#kt11WarmHalo)">
              {arc_texts}
            </g>
          </svg>
          {sub_html}
        </div>
        """

        js = f"""
        const MAIN_AT = {main_at_s};
        const ACC_AT = {accent_at_s};
        const EXIT_DUR = {exit_dur_s};

        window.__setFrame = function(frameIdx, totalFrames, fps) {{
          const safeFps = Math.max(1, Number(fps) || 60);
          const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
          const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.9);

          const rig = document.getElementById("ktRig");
          if (rig) {{
            rig.style.opacity = "1";
            rig.style.transform = "";
            rig.style.filter = "none";
          }}

          const pSweep = timeProgress(tSec, MAIN_AT, 0.42, velvetC2);
          const sSolid = Math.max(0, pSweep * 128 - 28);
          const sFade = Math.min(100, pSweep * 128);
          const st1 = document.getElementById("kt11StopSolid");
          const st2 = document.getElementById("kt11StopFade");
          if (st1) st1.setAttribute("offset", `${{sSolid.toFixed(1)}}%`);
          if (st2) st2.setAttribute("offset", `${{sFade.toFixed(1)}}%`);

          const sub = document.getElementById("kt11ArcSub");
          if (sub) {{
            const pSub = timeProgress(tSec, ACC_AT, 0.28, velvetC2);
            sub.style.opacity = String(pSub.toFixed(4));
            sub.style.transform = `translate3d(0, ${{((1 - pSub) * 16).toFixed(2)}}px, 0)`;
          }}

          if (rig) {{
            applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.42, 4.5, 0.024);
            if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
          }}
        }};
        window.__setFrame(1, 1, 60);
        """
        return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)

    # `mode == "tilted_chest"`: -5.5deg counter-tilted 2-part signature cluster (`sub` enters -0.10s before `hero`)
    sub_text = _prop_or_demo("kt11_cranial_svg_arc_or_tilt", props, ("sub_text", "kicker"), "chạm cảm xúc", required=False)
    main_text = _prop_or_demo("kt11_cranial_svg_arc_or_tilt", props, "main_text", "Đúng Nhịp Thật")
    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=72, max_px=100, char_factor=0.56))
    # v7.9.0 repair: fixed line breaks + nowrap (the blurred, widened hero no longer wraps mid-entrance and snaps back)
    hero_px, hero_lines = ws_fit_lines(main_text, hero_px, [((1 - p) * 7.0, 0.92 + 0.08 * p, 0.0) for p in KT_ENTRANCE_P
                                                            if min(1.0, 1.35 * p) >= 0.15], kt_line_max_w(width, hero_px),
                                       family="Playfair Display", weight=700, italic=True, swash=True,
                                       one_line_min_px=MIN_OVERLAY_FONT_PX if len(main_text) <= 22 else None)
    sub_px = int(props.get("sub_size") or secondary_text_px(props))

    main_at_s = max(0.12, float(props.get("main_at_s", 0.14)))
    sub_at_s = float(props.get("sub_at_s", max(0.0, main_at_s - 0.10)))  # Exact -0.10s before hero!
    tilt_deg = float(props.get("tilt_deg", -5.5))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt11-tilt-cluster {{
      display: flex;
      flex-direction: column;
      align-items: center;
      transform: rotate({tilt_deg}deg);
    }}

    .kt11-tilt-sub {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {sub_px}px;
      line-height: 1.12;
      color: {primary_ink};
      margin-bottom: -0.38em;
      text-shadow: {hero_shadow};
      will-change: transform, opacity;
    }}

    .kt11-tilt-hero {{
      font-size: {hero_px}px;
      line-height: 1.10;
      white-space: nowrap;
      color: {pal["hex"]};
      will-change: transform, opacity, filter;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      <div class="kt11-tilt-cluster">
        <div class="kt11-tilt-sub kt-diacritic-safe" id="kt11TiltSub">{esc(sub_text)}</div>
        <div class="kt11-tilt-hero kt-diacritic-safe" id="kt11TiltHero"{ws_nat0_attr(main_text, family="Playfair Display", weight=700, italic=True)}>{kt_lines_html(hero_lines, swash=True)}</div>
      </div>
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const SUB_AT = {sub_at_s};
    const MAIN_AT = {main_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, MAIN_AT + 0.9);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const sub = document.getElementById("kt11TiltSub");
      if (sub) {{
        const pS = timeProgress(tSec, SUB_AT, 0.22, player3Snap);
        sub.style.opacity = String(pS.toFixed(4));
        sub.style.transform = `translate3d(0, ${{((1 - pS) * 24).toFixed(2)}}px, 0)`;
      }}

      const hero = document.getElementById("kt11TiltHero");
      if (hero) {{
        const pH = timeProgress(tSec, MAIN_AT, 0.26, player3Snap);
        const uGlow = Math.max(0, (tSec - MAIN_AT) / 0.54);
        const hPulse = halationPulse(uGlow);
        hero.style.opacity = String((pH > 0 ? Math.min(1, pH * 1.35) : 0).toFixed(4));
        hero.style.transform = `translate3d(0, ${{((1 - pH) * 36).toFixed(2)}}px, 0) scale(${{(0.92 + 0.08 * pH).toFixed(4)}})`;
        hero.style.filter = pH < 0.99 ? `blur(${{((1 - pH) * 7.0).toFixed(2)}}px)` : "none";
        hero.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (`0 0 ${{(16 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, ` +
             `0 0 ${{(38 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}, ` +
             BASE_SH);
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", main_at_s + 0.18))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.26, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 12. `kt12_whisper_or_directional_echo` (`SIL_WHISPER_ECHO`, default 1080x440)
KT12_WHISPER_DARK_WEIGHT = 600  # v7.9.3: >= 600 over A-roll / busy dark footage (400 was illegible in e2e_v791)
KT12_WHISPER_DARK_HALO = "0 0 2px rgba(0, 0, 0, 0.85), 0 0 12px rgba(0, 0, 0, 0.72), 0 4px 18px rgba(0, 0, 0, 0.55)"


def _build_kt12_whisper_or_directional_echo(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    mode = nfc(props.get("mode", "whisper")).lower()
    is_echo = mode in ("directional_echo", "echo")
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    if not is_echo:
        # `mode="whisper"`: ultra-clean 36–40px lowercase geometric sans (#FAFAFA dark / #14171F light), 0 pill, 0 heavy glow
        main_text = _prop_or_demo("kt12_whisper_or_directional_echo", props, "main_text", "nhưng điều ít ai để ý là...")
        # v7.8.0: the whisper no longer renders at 31-40 px (illegible on a phone); floor MIN_OVERLAY_FONT_PX. An explicit `main_size`
        # below the floor raises ValueError (v7.9.0; it was honoured with a warning before).
        if props.get("main_size"):
            whisper_px = enforce_min_text_px(int(props["main_size"]), forced=True, label="kt12 whisper")
        else:
            fit_text = max(main_text, nfc(props.get("accent_text", "")).strip(), key=len)  # v7.9.3: both whisper lines fit
            whisper_px = enforce_min_text_px(_auto_typo_px(fit_text, width, min_px=MIN_OVERLAY_FONT_PX, max_px=80, char_factor=0.52))
        main_at_s = float(props.get("main_at_s", 0.02))
        reveal_style = nfc(props.get("reveal", "feather_wipe")).lower()
        # v7.9.3: the whisper drew its first clause only (accent_text dropped) at weight 400 with a 0.5-alpha shadow -- illegible over
        # A-roll. The accent is a second whisper line; the dark theme (A-roll / busy footage) gets weight 600 and a tight dark halo.
        accent_text = nfc(props.get("accent_text", "")).strip()
        acc_raw = props.get("accent_at_s")
        accent_at_s = (float(acc_raw) if acc_raw is not None else main_at_s + 0.28) if accent_text else main_at_s
        whisper_shadow = helper_shadow if is_light else KT12_WHISPER_DARK_HALO
        sub_html = f'<div class="kt12-whisper-line" id="kt12WhisperSub">{esc(accent_text)}</div>' if accent_text else ""

        css = f"""
        .kt12-whisper-rig {{
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          max-width: {int(width * 0.90)}px;
          padding: 16px 24px;
          will-change: transform, opacity, filter;
        }}

        .kt12-whisper-line {{
          font-family: 'Be Vietnam Pro', sans-serif;
          font-weight: {"500" if is_light else str(KT12_WHISPER_DARK_WEIGHT)};
          font-size: {whisper_px}px;
          line-height: 1.32;
          letter-spacing: -0.01em;
          color: {primary_ink};
          -webkit-text-stroke: 0px transparent !important;
          padding: 0.32em 0.25em;
          text-align: center;
          /* Dark halo for legibility (no glow, no pill, no stroke) */
          text-shadow: {whisper_shadow};
          will-change: opacity, transform, -webkit-mask-image;
        }}
        """

        body = f"""
        <div class="kt12-whisper-rig" id="ktRig">
          <div class="kt12-whisper-line" id="kt12Whisper">{esc(main_text)}</div>
          {sub_html}
        </div>
        """

        js = f"""
        const MAIN_AT = {main_at_s};
        const ACC_AT = {accent_at_s};
        const REVEAL_STYLE = {json.dumps(reveal_style)};
        const EXIT_DUR = {exit_dur_s};

        window.__setFrame = function(frameIdx, totalFrames, fps) {{
          const safeFps = Math.max(1, Number(fps) || 60);
          const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
          const fade4fSec = 4 / safeFps;
          const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, Math.max(MAIN_AT, ACC_AT) + 0.7);

          const rig = document.getElementById("ktRig");
          if (rig) {{
            rig.style.opacity = "1";
            rig.style.transform = "";
            rig.style.filter = "none";
          }}

          for (const [elId, AT] of [["kt12Whisper", MAIN_AT], ["kt12WhisperSub", ACC_AT]]) {{
            const el = document.getElementById(elId);
            if (!el) continue;
            if (REVEAL_STYLE === "fade") {{
              const pF = timeProgress(tSec, AT, fade4fSec, velvetC2);
              el.style.opacity = String(pF.toFixed(4));
              el.style.transform = `translate3d(0, ${{((1 - pF) * 8).toFixed(2)}}px, 0)`;
            }} else {{
              const pW = timeProgress(tSec, AT, 0.22, velvetC2);
              const s1 = Math.max(0, pW * 124 - 24);
              const s2 = Math.min(100, pW * 124);
              const mask = `linear-gradient(90deg, rgba(0,0,0,1) ${{s1.toFixed(1)}}%, rgba(0,0,0,0) ${{s2.toFixed(1)}}%)`;
              el.style.opacity = String(Math.min(1, pW * 1.6).toFixed(4));
              el.style.webkitMaskImage = mask;
              el.style.maskImage = mask;
              el.style.transform = `translate3d(0, ${{((1 - pW) * 6).toFixed(2)}}px, 0)`;
            }}
          }}

          if (rig) {{
            applyHoldMicroFloat(rig, tSec, MAIN_AT + 0.22, 2.8, 0.012);
            if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
          }}
        }};
        window.__setFrame(1, 1, 60);
        """
        return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)

    # `mode="directional_echo"` (`#19 f_01362` `"lặp lại"`):
    # Sharp front accent keyword + 2 stepped upward-right blurred ghost echoes (+10px,-12px)@0.42 & (+20px,-24px)@0.18 + tight negative-leading bottom phrase
    main_text = _prop_or_demo("kt12_whisper_or_directional_echo", props, "main_text", "lặp lại")
    bottom_text = _prop_or_demo("kt12_whisper_or_directional_echo", props, ("accent_text", "sub_text"), "đúng cấu trúc nhịp", required=False)

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=78, max_px=102, char_factor=0.56))
    bot_px = int(props.get("accent_size") or secondary_text_px(props))

    main_at_s = float(props.get("main_at_s", 0.03))
    echo_at_s = float(props.get("echo_at_s", main_at_s + 0.12))
    accent_at_s = float(props.get("accent_at_s", echo_at_s + 0.10))

    echo_op1 = float(props.get("echo_opacity", 0.42))  # front ghost; the far ghost keeps the 0.18 / 0.42 ratio
    echo_op2 = echo_op1 * (0.18 / 0.42)

    css = _kt_shared_css(pal, width, "center", theme=theme_mode, sec_px=secondary_text_px(props)) + f"""
    .kt12-echo-stack {{
      position: relative;
      display: inline-grid;
      place-items: center;
    }}

    .kt12-echo-layer {{
      grid-area: 1 / 1;
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: {hero_px}px;
      line-height: 1.04;
      letter-spacing: -0.04em;
      color: {pal["hex"]};
      white-space: nowrap;
      will-change: transform, opacity, filter;
    }}

    .kt12-echo-front {{
      z-index: 4;
    }}

    .kt12-echo-g1 {{
      z-index: 2;
      filter: blur(2.2px);
    }}

    .kt12-echo-g2 {{
      z-index: 1;
      filter: blur(4.6px);
    }}

    .kt12-echo-bottom {{
      position: relative;
      z-index: 5;
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 700;
      font-size: {bot_px}px;
      line-height: 0.92;
      letter-spacing: -0.025em;
      color: {primary_ink};
      margin-top: -0.46em;
      text-shadow: {hero_shadow};
      will-change: transform, opacity;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      <div class="kt12-echo-stack">
        <div class="kt12-echo-layer kt12-echo-g2 kt-diacritic-safe" id="kt12Echo2" data-ws-follow="kt12Front">{esc(main_text)}</div>
        <div class="kt12-echo-layer kt12-echo-g1 kt-diacritic-safe" id="kt12Echo1" data-ws-follow="kt12Front">{esc(main_text)}</div>
        <div class="kt12-echo-layer kt12-echo-front kt-diacritic-safe" id="kt12Front">{esc(main_text)}</div>
      </div>
      <div class="kt12-echo-bottom kt-diacritic-safe" id="kt12Bottom">{esc(bottom_text)}</div>
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const MAIN_AT = {main_at_s};
    const ECHO_AT = {echo_at_s};
    const ACC_AT = {accent_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};
    const BASE_SH = {json.dumps(hero_shadow)};

    window.__setFrame = function(frameIdx, totalFrames, fps) {{
      const safeFps = Math.max(1, Number(fps) || 60);
      const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
      const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, ACC_AT + 0.85);

      const rig = document.getElementById("ktRig");
      if (rig) {{
        rig.style.opacity = "1";
        rig.style.transform = "";
        rig.style.filter = "none";
      }}

      const pMain = timeProgress(tSec, MAIN_AT, 0.22, player3Snap);
      const pEcho = timeProgress(tSec, ECHO_AT, 0.24, player3Snap);
      const uGlow = Math.max(0, (tSec - MAIN_AT) / 0.54);
      const hPulse = halationPulse(uGlow);

      const front = document.getElementById("kt12Front");
      if (front) {{
        front.style.opacity = String(pMain.toFixed(4));
        front.style.transform = `translate3d(0, ${{((1 - pMain) * 32).toFixed(2)}}px, 0)`;
        front.style.textShadow = IS_LIGHT
          ? BASE_SH
          : (`0 0 ${{(14 * hPulse).toFixed(1)}}px ${{GLOW_IN}}, ` +
             `0 0 ${{(34 * hPulse).toFixed(1)}}px ${{GLOW_OUT}}, ` +
             BASE_SH);
      }}

      const e1 = document.getElementById("kt12Echo1");
      if (e1) {{
        e1.style.opacity = String(({echo_op1:g} * pEcho).toFixed(4));
        e1.style.transform = `translate3d(${{(10 * pEcho).toFixed(2)}}px, ${{-12 * pEcho}}px, 0)`;
      }}

      const e2 = document.getElementById("kt12Echo2");
      if (e2) {{
        e2.style.opacity = String(({echo_op2:.4g} * pEcho).toFixed(4));
        e2.style.transform = `translate3d(${{(20 * pEcho).toFixed(2)}}px, ${{-24 * pEcho}}px, 0)`;
      }}

      const bot = document.getElementById("kt12Bottom");
      if (bot) {{
        const pB = timeProgress(tSec, ACC_AT, 0.24, player3Snap);
        bot.style.opacity = String(pB.toFixed(4));
        bot.style.transform = `translate3d(0, ${{((1 - pB) * 24).toFixed(2)}}px, 0)`;
      }}

      applyOptionalPillEntrance(tSec, {float(props.get("badge_at_s", accent_at_s + 0.14))}, 0.22);

      if (rig) {{
        applyHoldMicroFloat(rig, tSec, ACC_AT + 0.24, 4.5, 0.024);
        if (totalFrames > 1) applyCleanExit(rig, tSec, clipDurSec, EXIT_DUR);
      }}
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# ---------------------------------------------------------------------------
# v7.4: 3 @__dviet layout templates (`screen_strip`, `card_916`, `profile_card`)
# Role-named slots (`data-slot="..."`): see LAYOUT_TEMPLATE_SLOTS. Geometry is an ESTIMATE from the 17-video
# corpus (references/dviet_19/INDEX.md): strip 1080x~600 at y 660-1260, caption y ~67 %, card border ~8 px.
# ---------------------------------------------------------------------------

LAYOUT_TEMPLATES = ("screen_strip", "card_916", "profile_card")

LAYOUT_TEMPLATE_SLOTS: dict[str, list[str]] = {
    "screen_strip": ["aroll_plate", "title", "screen_content", "caption", "caption_keyword"],
    "card_916": ["stage", "card_media", "card_label"],
    "profile_card": ["avatar", "display_name", "handle", "stat_posts", "stat_followers", "stat_following", "bio"],
}

LAYOUT_FALLBACK_SANS = "Be Vietnam Pro"
LAYOUT_FALLBACK_SERIF = "Playfair Display"
_DVIET_TOKENS_PATH = THIS_FILE.parents[2] / "presets" / "dviet_style_tokens.json"
_FONT_WARNED: set[str] = set()


# ---------------------------------------------------------------------------
# v7.8.0: minimum legible overlay text + product-safe hero lock-up
# ---------------------------------------------------------------------------
MIN_OVERLAY_FONT_PX = 64      # [UOC] no overlay text below a 64 px font on the 1080x1920 canvas (the v3 whisper rendered at 31 px)
MIN_OVERLAY_CAP_PX = 46       # [UOC] cap height floor in px
MIN_GLYPH_FRAC = 0.033        # [UOC] glyph box >= 3.3 % of the 1920 frame height
WORD_GAP_MIN_EM = 0.25        # [UOC] = motion_gate.WORD_GAP_MIN_EM: adjacent-word gap floor on every visible entrance frame
WS_NAT_MARGIN_EM = 0.02       # [ĐO] PIL vs Chrome ink metrics differ by up to ~0.011 em (Playfair italic): the guard assumes a gap this much tighter
KT03_BLUR_PX = 12.0           # kt03 bloom blur before the gap cap (the v7.1 look)
KT03_WORD_W_EM = 0.72         # [UOC] per-character width over-estimate for the per-word scale cap (Be Vietnam Pro ExtraBold ~0.6)
FRAME_H_DEFAULT = 1920
HERO_GOLD = "#F5C451"
HERO_PLATE_W, HERO_PLATE_H = 1080, 640                 # legacy v3 hero plate
HERO_LEGACY_BASELINE_Y, HERO_LEGACY_NUM_H, HERO_LEGACY_W, HERO_LEGACY_GAP = 475, 285, 780, 40
DEFAULT_HERO_LINES: list[tuple[str, str, int]] = [("3", HERO_GOLD, HERO_LEGACY_BASELINE_Y), ("BƯỚC", HERO_GOLD, HERO_LEGACY_BASELINE_Y)]


class UndersizedTextError(ValueError):
    """v7.9.0 hard block: a non-decorative plate text renders below MIN_OVERLAY_FONT_PX on the canvas. `.audits` = the failed jobs."""

    def __init__(self, message: str, audits: Sequence[dict[str, Any]] = ()) -> None:
        super().__init__(message)
        self.audits = list(audits)


class TextPathOverflowError(ValueError):
    """v7.9.0 repair hard block: an SVG <textPath> text is longer than its path, so Chrome silently drops the glyphs whose midpoint
    falls off the path (the long kt11 arc lost its first / last words while every size audit passed). Raised after rendering for
    every job, decorative included (dropped words are never decorative). `.audits` = the failed jobs (`textpath_overflow` =
    the engine's `textPaths` records: chars, rendered, textLen, pathLen, start, end)."""

    def __init__(self, message: str, audits: Sequence[dict[str, Any]] = ()) -> None:
        super().__init__(message)
        self.audits = list(audits)


def enforce_min_text_px(font_px: int | float, *, forced: bool = False, label: str = "text") -> int:
    """Raise `font_px` to MIN_OVERLAY_FONT_PX. `forced=True` (the caller named the size explicitly) raises ValueError below the floor
    (v7.9.0; it only warned before): an explicit illegible size is an error, not something to keep silently."""
    px = int(round(font_px))
    if px >= MIN_OVERLAY_FONT_PX:
        return px
    if forced:
        raise ValueError(f"{label}: font {px}px is below the {MIN_OVERLAY_FONT_PX}px legibility floor")
    return MIN_OVERLAY_FONT_PX


def gap_safe_blur_px(font_px: float, gap_px: float, blur_px: float, *, scale: float = 1.0, word_w_px: float = 0.0,
                     min_em: float = WORD_GAP_MIN_EM) -> float:
    """v7.9.0: `blur_px` capped so a per-word entrance keeps the adjacent-word gap >= `min_em` em (the motion_gate.word_gap_series
    model: a Gaussian sigma b eats 2 b of the gap, a per-word scale s eats (s - 1) x `word_w_px`, the em grows with s)."""
    room = gap_px - max(0.0, scale - 1.0) * word_w_px - min_em * font_px * scale
    return max(0.0, min(float(blur_px), math.floor(room / 2.0 * 100) / 100))


def gap_safe_word_scale(font_px: float, gap_px: float, scale: float, word_w_px: float, min_em: float = WORD_GAP_MIN_EM) -> float:
    """v7.9.0: a per-word resting scale `scale` capped so gap - (s - 1) x word_w >= `min_em` x font x s (never below 1.0)."""
    if scale <= 1.0:
        return float(scale)
    return max(1.0, min(float(scale), math.floor((gap_px + word_w_px) / (word_w_px + min_em * font_px) * 1e4) / 1e4))


def kt03_gap_safe_entrance(words: list[dict[str, Any]], word_px: float) -> list[dict[str, Any]]:
    """kt03 words with `scale` capped and a per-word `blur_px` (<= KT03_BLUR_PX) that keep the 0.25 em gap on every frame
    (v4 K3: a 12 px bloom over a tight gap read 'MÌNHVỪA'). Word width is over-estimated (KT03_WORD_W_EM per char) on purpose."""
    gap_px = KT03_WORD_GAP_EM * word_px
    out = []
    for m in words:
        w_px = KT03_WORD_W_EM * word_px * max(1, len(m["word"]))
        sc = gap_safe_word_scale(word_px, gap_px, float(m.get("scale", 1.0)), w_px)
        out.append({**m, "scale": sc, "blur_px": gap_safe_blur_px(word_px, gap_px, KT03_BLUR_PX, scale=sc, word_w_px=w_px)})
    return out


def _mg() -> Any:
    """motion_gate (same folder): the word-gap model shared by the plates, FilmCraft keys and the gate."""
    try:
        import motion_gate as mod
    except ImportError:  # pragma: no cover - imported from another working directory
        sys.path.insert(0, str(THIS_FILE.parent))
        import motion_gate as mod
    return mod


def css_face_file(family: str = "Be Vietnam Pro", weight: int = 800, italic: bool = False) -> Path | None:
    """The font file `build_font_face_css` registers for (family, weight, style): the metrics the plate is drawn with."""
    fam = nfc(family).strip().strip("'\"").lower()
    w = int(weight)
    if fam.startswith("playfair"):
        cands = ["PlayfairDisplay-Italic[wght].ttf", "PlayfairDisplay-BoldItalic.ttf"] if italic else ["PlayfairDisplay[wght].ttf", "PlayfairDisplay-Variable.ttf"]
    elif italic:
        cands = ["BeVietnamPro-ExtraBoldItalic.ttf" if w >= 800 else ("BeVietnamPro-BoldItalic.ttf" if w >= 600 else "BeVietnamPro-Italic.ttf"),
                 "BeVietnamPro-Italic.ttf"]
    elif w >= 800:
        cands = ["BeVietnamPro-ExtraBold.ttf"] if w == 800 else ["BeVietnamPro-Black.ttf", "BeVietnamPro-ExtraBold.ttf"]
    elif w >= 600:
        cands = ["BeVietnamPro-Bold.ttf"]
    elif w == 500:
        cands = ["Inter-Medium.ttf", "BeVietnamPro-Medium.ttf"]
    else:
        cands = ["BeVietnamPro-Light.ttf", "BeVietnamPro-Regular.ttf"]
    for name in cands:
        f = _tnedit_font(name)
        if f.is_file():
            return f
    return None


def ws_nat0_attr(text: str, *, family: str = "Be Vietnam Pro", weight: int = 800, italic: bool = False,
                 space_em: float | None = None, letter_spacing_em: float = 0.0) -> str:
    """v7.9.0: ` data-ws-nat0="<em>"` for a line with a blur / slide entrance: its narrowest resting ink gap at letter-spacing 0
    (`motion_gate.natural_word_gap_em`, floored to 1e-3 em); the page guard `applyWordGapGuard` widens the word spacing from it.
    Empty for a one-word line (nothing to collide)."""
    face = css_face_file(family, weight, italic)
    if face is None:
        return ' data-ws-nat0="%.3f"' % (_mg().SPACE_EM - 0.03)  # [UOC] unknown face: assume tight bearings
    nat = _mg().natural_word_gap_em(text, face, letter_spacing_em, space_em=space_em)
    return "" if nat is None else ' data-ws-nat0="%.3f"' % (math.floor((nat - WS_NAT_MARGIN_EM) * 1000) / 1000)


def ws_fit_px(text: str, font_px: int, states: Sequence[tuple[float, float, float]], max_w: float, *, family: str = "Be Vietnam Pro",
              weight: int = 800, italic: bool = False, min_px: int = MIN_OVERLAY_FONT_PX) -> int:
    """v7.9.0: largest font px <= `font_px` whose widest entrance frame still fits `max_w` px on one line. `states` = the visible
    entrance frames as (blur px, scale, letter-spacing em); each is widened by `motion_gate.entrance_word_spacing_em` in every gap."""
    if len(nfc(text).split()) < 2:
        return int(font_px)
    return ws_fit_lines(text, font_px, states, max_w, family=family, weight=weight, italic=italic, min_px=min_px,
                        one_line_min_px=min_px, max_lines=1)[0]


def ws_fit_lines(text: str, font_px: int, states: Sequence[tuple[float, float, float]], max_w: float, *,
                 family: str = "Be Vietnam Pro", weight: int = 800, italic: bool = False, swash: bool = False, guarded: bool = True,
                 min_px: int = MIN_OVERLAY_FONT_PX, one_line_min_px: int | None = None, max_lines: int = 4,
                 measure: Any = None) -> tuple[int, list[str]]:
    """v7.9.0 repair: font px and FIXED line breaks for a kt line so its widest entrance frame fits `max_w` px on every line. One
    line first, shrinking down to `one_line_min_px` (None = no shrink for one line); else 2..`max_lines` balanced lines at `font_px`;
    the size drops (to `min_px`) only when even `max_lines` lines do not fit. The caller renders the lines with `<br>` + nowrap, so the
    word-spacing guard can widen a line without it reflowing mid-entrance. `swash` = the first line starts with the 1.48 em swash
    initial (`render_swash_hybrid_html_py`); `guarded=False` = the line has no entrance word-spacing guard (no widening).
    `measure(line, px, first_line) -> px` replaces the built-in widest-frame width (a template with its own spacing model, kt07)."""
    words = nfc(text).split()
    face = css_face_file(family, weight, italic)
    if measure is None and (face is None or not states) or not words:
        return int(font_px), [" ".join(words)]
    from PIL import ImageFont
    mg = _mg()
    nat0 = (mg.natural_word_gap_em(text, face, 0.0) or mg.SPACE_EM) if measure is None else 0.0
    fonts: dict[int, Any] = {}

    def ft(px: int) -> Any:
        if px not in fonts:
            fonts[px] = ImageFont.truetype(str(face), px)
        return fonts[px]

    def widest(line: str, px: int, first: bool) -> float:
        if measure is not None:
            return float(measure(line, px, first))
        if swash and first and line[:1].isascii() and line[:1].isalpha():
            base = ft(round(px * 1.48)).getlength(line[0]) + 0.018 * px + ft(px).getlength(line[1:])
        else:
            base = ft(px).getlength(line)
        n_gaps = line.count(" ")
        return max((base + len(line) * ls * px + (n_gaps * mg.entrance_word_spacing_em(b, sc, px, nat0 + 2 * ls) * px if guarded else 0)) * sc
                   for b, sc, ls in states)

    def split(k: int, px: int) -> tuple[float, list[str]]:  # contiguous k-line split minimising the widest line
        n = len(words)
        best: dict[tuple[int, int], tuple[float, list[str]]] = {}

        def go(i: int, left: int) -> tuple[float, list[str]]:
            if (i, left) in best:
                return best[(i, left)]
            if left == 1:
                ln = " ".join(words[i:])
                r = (widest(ln, px, i == 0), [ln])
            else:
                r = (math.inf, [])
                for j in range(i + 1, n - left + 2):
                    ln = " ".join(words[i:j])
                    rest_w, rest = go(j, left - 1)
                    cand = (max(widest(ln, px, i == 0), rest_w), [ln] + rest)
                    if cand[0] < r[0]:
                        r = cand
            best[(i, left)] = r
            return r
        return go(0, k)

    px = int(font_px)
    floor1 = max(int(min_px), int(font_px if one_line_min_px is None else one_line_min_px))
    while True:
        w1, lines = split(1, px)
        if w1 <= max_w or px <= floor1:
            break
        px -= 1
    if w1 <= max_w:
        return px, lines
    k_max = max(1, min(int(max_lines), len(words)))
    for k in range(2, k_max + 1):
        wk, lines = split(k, int(font_px))
        if wk <= max_w:
            return int(font_px), lines
    px = int(font_px)
    wk, lines = split(k_max, px)
    while wk > max_w and px > min_px:
        px -= 1
        wk, lines = split(k_max, px)
    return px, lines


def kt_lines_html(lines: Sequence[str], *, swash: bool = False) -> str:
    """The fixed lines of `ws_fit_lines` as HTML (escaped, `<br>`-joined; `swash` = swash-hybrid initial on the first line)."""
    if swash:
        return render_swash_hybrid_html_py("\n".join(lines)).replace("\n", "<br>")
    return "<br>".join(esc(ln) for ln in lines)


KT_PLATE_MARGIN_PX = 40  # [UOC] a widened entrance frame keeps its ink this far inside the plate edges


def kt_line_max_w(width: int, font_px: float) -> float:
    """Room for one nowrap kt line on its widest entrance frame: the plate width minus KT_PLATE_MARGIN_PX each side (a centred nowrap
    line overflows the rig symmetrically) minus the 0.25 em diacritic-safe padding each side."""
    return width - 2 * KT_PLATE_MARGIN_PX - 2 * KT_DIACRITIC_PAD_X_EM * font_px


def plate_text_px(nominal_px: float, plate_scale: float = 1.0) -> int:
    """v7.9.0: CSS px for a plate text so it lands >= MIN_OVERLAY_FONT_PX on the 1080x1920 canvas after the plate is scaled by
    `plate_scale` (effective px = CSS px x plate scale). Never smaller than `nominal_px`."""
    return max(int(round(nominal_px)), int(math.ceil(MIN_OVERLAY_FONT_PX / max(float(plate_scale), 1e-3) - 1e-9)))


def audit_plate_text_px(html_text: str, plate_scale: float = 1.0, floor: float = MIN_OVERLAY_FONT_PX) -> list[tuple[str, float]]:
    """v7.9.0: every CSS rule `selector { font-size: Npx }` whose canvas size N x `plate_scale` is under `floor` px ->
    [(selector, effective px)]. Empty list = every styled text clears the legibility floor (v4 K1 polaroid labels: 10-27 px)."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", html_text):
        for px in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", m.group(2)):
            eff = float(px) * float(plate_scale)
            if eff < floor - 1e-6:
                out.append((m.group(1).strip().splitlines()[-1].strip(), round(eff, 1)))
    return out


def _hex_to_rgb(c: Any) -> tuple[int, int, int]:
    if isinstance(c, str):
        h = c.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return int(c[0]), int(c[1]), int(c[2])


def _hero_font(font_path: Path | None) -> Path:
    cand = [font_path] if font_path else []
    cand += [_font_file(FONT_ROOT_BASE, "BeVietnamPro-ExtraBold.ttf"), _font_file(Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans-Bold.ttf")]
    for c in cand:
        if c and Path(c).is_file():
            return Path(c)
    raise FileNotFoundError("no hero font found (BeVietnamPro-ExtraBold.ttf)")


def _hero_masks(lines: Sequence[tuple[str, Any, int]], size: tuple[int, int], target_w: float, font_path: Path, dy: int,
                gap: int, num_h: float) -> list[Any]:
    """One PIL mask per line / row -> [(mask uint8 HxW, rgb, ink bbox, (text, baseline))]. Lines sharing a baseline form one row (a leading
    digit string is sized by `num_h`, the rest fill `target_w`); every other row is width-fitted to `target_w`."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    pw, ph = size
    rows: dict[int, list[tuple[str, Any]]] = {}
    for text, col, base in lines:
        rows.setdefault(int(base), []).append((nfc(text), col))
    out = []
    for base, items in rows.items():
        def fitted(txt: str, w: float) -> Any:
            f = ImageFont.truetype(str(font_path), 200)
            return ImageFont.truetype(str(font_path), max(8, int(round(200 * w / max(f.getlength(txt), 1.0)))))
        fonts: list[Any] = []
        remaining = target_w - gap * (len(items) - 1)
        for i, (txt, _) in enumerate(items):
            if len(items) > 1 and i == 0 and txt.isdigit():
                f0 = ImageFont.truetype(str(font_path), 200)
                bb = f0.getbbox(txt, anchor="ls")
                f = ImageFont.truetype(str(font_path), int(round(200 * num_h / max(1, bb[3] - bb[1]))))
                remaining -= f.getlength(txt)
                fonts.append(f)
            else:
                fonts.append(None)
        flex = [i for i, f in enumerate(fonts) if f is None]
        for i in flex:
            fonts[i] = fitted(items[i][0], remaining / len(flex))
        widths = [f.getlength(t) for f, (t, _) in zip(fonts, items)]
        x = (pw - (sum(widths) + gap * (len(items) - 1))) / 2.0
        for (txt, col), f, w in zip(items, fonts, widths):
            im = Image.new("L", (pw, ph), 0)
            ImageDraw.Draw(im).text((x, base + dy), txt, font=f, fill=255, anchor="ls")
            m = np.asarray(im, np.uint8)
            ys, xs = np.where(m >= 128)
            if ys.size:
                out.append((m, _hex_to_rgb(col), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), (txt, base)))
            x += w + gap
    return out


def render_hero_lockup(
    lines: Sequence[tuple[str, Any, int]] | None = None,
    *,
    plate_size: tuple[int, int] = (HERO_PLATE_W, HERO_PLATE_H),
    target_w: float = HERO_LEGACY_W,
    text_band: tuple[int, int] | None = None,
    font_path: Path | None = None,
    gap: int = HERO_LEGACY_GAP,
    num_h: float = HERO_LEGACY_NUM_H,
    frame_h: int = FRAME_H_DEFAULT,
) -> dict[str, Any]:
    """Static hero tier lock-up as straight-alpha RGBA, from `lines=[(text, color, baseline_y), ...]`.
    `lines=None` -> `DEFAULT_HERO_LINES` ('3' + 'BƯỚC' on one baseline in a 1080x640 plate, 780 px wide): the pre-v7.8.0 output.
    Lines with the same baseline share a row (numeral + word); other rows are fitted to `target_w` (VIDEO / SẢN PHẨM: same width).
    `text_band=(y0, y1)` is the product-safe y range: when the ink would cross it the baselines are shifted (clamped) to fit; a block
    taller than the band raises ValueError. Returns {rgba, alpha, bbox (x0,y0,x1,y1 inclusive), lines (as drawn), hero_frac, dy}.
    The animation (pop / exit) is the caller's job; this only lays out the glyphs."""
    import numpy as np

    use = list(lines) if lines is not None else list(DEFAULT_HERO_LINES)
    if not use:
        raise ValueError("lines must not be empty")
    fp = _hero_font(font_path)
    size = (int(plate_size[0]), int(plate_size[1]))
    dy = 0
    masks = _hero_masks(use, size, target_w, fp, dy, gap, num_h)
    if not masks:
        raise ValueError("hero lines rendered no ink")

    def block(ms: list[Any]) -> tuple[int, int]:
        return min(m[2][1] for m in ms), max(m[2][3] for m in ms)

    if text_band is not None:
        top, bot = block(masks)
        b0, b1 = int(text_band[0]), int(text_band[1])
        if (bot - top + 1) > (b1 - b0 + 1):
            raise ValueError(f"hero block {bot - top + 1}px tall does not fit the product-safe band {b0}..{b1} ({b1 - b0 + 1}px)")
        if top < b0:
            dy = b0 - top
        elif bot > b1:
            dy = b1 - bot
        if dy:
            masks = _hero_masks(use, size, target_w, fp, dy, gap, num_h)
    pw, ph = size
    rgb = np.zeros((ph, pw, 3), np.float32)
    alpha = np.zeros((ph, pw), np.float32)
    for m, col, _bb, _lab in masks:
        a = m.astype(np.float32) / 255.0
        rgb = rgb * (1 - a)[:, :, None] + np.array(col, np.float32)[None, None, :] * a[:, :, None]
        alpha = np.clip(alpha + a * (1 - alpha), 0, 1)
    top, bot = block(masks)
    x0, x1 = min(m[2][0] for m in masks), max(m[2][2] for m in masks)
    rgba = np.dstack([np.clip(rgb + 0.5, 0, 255), alpha * 255.0 + 0.5]).clip(0, 255).astype(np.uint8)
    return {"rgba": rgba, "alpha": alpha, "bbox": (x0, top, x1, bot), "dy": dy,
            "lines": [(t, c, b + dy) for (t, c, b) in use] if dy else list(use),
            "hero_frac": (bot - top + 1) / float(frame_h)}



def _dviet_accent_hex(name: str = "yellow_bright", default: str = "#F1C711") -> str:
    """Accent colour from presets/dviet_style_tokens.json (single token file), constant fallback when absent."""
    try:
        return str(json.loads(_DVIET_TOKENS_PATH.read_text(encoding="utf-8"))["palette"]["accents"][name])
    except (OSError, ValueError, KeyError):
        return default


def _registered_font_families() -> set[str]:
    return {m.lower() for m in re.findall(r"font-family:\s*'([^']+)'", build_font_face_css())}


def _system_has_font(family: str) -> bool:
    try:
        r = subprocess.run(["fc-match", "-f", "%{family}", family], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return family.lower() in {p.strip().lower() for p in (r.stdout or "").replace(",", "\n").split("\n")}


def resolve_layout_font(requested: str | None, default: str = LAYOUT_FALLBACK_SANS, *, serif: bool = False) -> str:
    """
    CSS `font-family` stack for a layout template. If the requested family is neither registered by
    `build_font_face_css()` nor installed, falls back to Be Vietnam Pro (sans) / Playfair Display (serif)
    and PRINTS a warning (once per family) to stderr.
    """
    fallback = LAYOUT_FALLBACK_SERIF if serif else LAYOUT_FALLBACK_SANS
    family = nfc(requested or default).strip() or default
    if family.lower() in _registered_font_families() or _system_has_font(family):
        base = family
    else:
        base = fallback
        if family not in _FONT_WARNED:
            _FONT_WARNED.add(family)
            print(f"[WARN] web_plate_builder: font '{family}' not available; falling back to '{fallback}'", file=sys.stderr)
    tail = "Georgia, serif" if serif else "'Inter', sans-serif"
    stack = [f"'{base}'"] + ([f"'{fallback}'"] if base != fallback else []) + [tail]
    return ", ".join(stack)


def _procedural_aroll_plate_data_url() -> str:
    """Stand-in A-roll: warm wall + head-and-shoulders silhouette (used when no `aroll_image` is given)."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 960">
      <defs>
        <linearGradient id="w" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#8d7b68"/><stop offset="100%" stop-color="#4a4036"/></linearGradient>
        <radialGradient id="k" cx="30%" cy="30%" r="70%"><stop offset="0%" stop-color="#f3d9b4" stop-opacity="0.55"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></radialGradient>
      </defs>
      <rect width="540" height="960" fill="url(#w)"/><rect width="540" height="960" fill="url(#k)"/>
      <ellipse cx="270" cy="330" rx="86" ry="104" fill="#2b2420"/>
      <path d="M60 960 C70 700 170 560 270 560 C370 560 470 700 480 960 Z" fill="#1d1a18"/>
    </svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


_LAYOUT_JS_FINAL_STATE = r"""
    window.__setFrame = function(frameIdx, totalFrames, fps) {
      const norm = totalFrames <= 1 ? 1 : frameIdx / (totalFrames - 1);
      const p = segProgress(norm, 0.00, 0.5);
      const root = document.getElementById("layoutRoot");
      if (root) {
        root.style.opacity = String(p);
        root.style.transform = `translate3d(0, ${((1 - p) * 18).toFixed(2)}px, 0)`;
      }
    };
    window.__setFrame(1, 1, 30);
"""


def _build_screen_strip(props: dict[str, Any], width: int, height: int) -> str:
    """Tutorial layout: ~1080x600 screen strip centred on the A-roll plate zoomed 3x, blurred and darkened."""
    sans = resolve_layout_font(props.get("font_family"))
    accent = nfc(props.get("accent_hex") or _dviet_accent_hex())
    strip_h = int(props.get("strip_height") or 600)
    strip_cy = float(props.get("strip_center_y_pct", 50.0)) / 100.0 * height
    strip_top = int(round(strip_cy - strip_h / 2.0))
    caption_y = float(props.get("caption_y_pct", 67.0)) / 100.0 * height
    title_y = float(props.get("title_y_pct", 23.0)) / 100.0 * height
    plate = image_to_safe_data_url(props.get("aroll_image")) if props.get("aroll_image") else _procedural_aroll_plate_data_url()
    screen = image_to_safe_data_url(props.get("screen_image"), fallback_variant="after", fallback_label="screen")
    title = nfc(props.get("title", "bước một"))
    caption = nfc(props.get("caption", "tạo clip ghép bằng phím tắt"))
    keyword = nfc(props.get("caption_keyword", ""))
    zoom = float(props.get("plate_zoom", 3.0))
    blur_px = int(props.get("plate_blur_px", 48))
    dark = float(props.get("plate_brightness", 0.45))
    kw_html = f'<span class="ss-kw" data-slot="caption_keyword">{esc(keyword)}</span> ' if keyword else ""
    # v7.9.0: caption and keyword at the 70 px secondary size (were 44 / 27 px). The caption keeps its measured y (67 %) for its first
    # line but never starts above the strip bottom + 24 px, so a 2-3 line caption grows downwards instead of onto the screen content.
    sec = secondary_text_px(props)
    cap_top = max(caption_y - 0.5 * 1.2 * sec - 0.2 * sec, strip_top + strip_h + 24)
    title_html = f'<div class="ss-title" data-slot="title">{esc(title)}</div>' if title else ""
    css = """
    .stage-root { background: #0b0b0c; }
    #layoutRoot { position: absolute; inset: 0; will-change: transform, opacity; }
    .ss-plate { position: absolute; inset: 0; overflow: hidden; }
    .ss-plate-img { position: absolute; inset: 0; background-size: cover; background-position: 50% 30%;
      transform: scale(__ZOOM__); filter: blur(__BLUR__px) brightness(__DARK__) saturate(0.85); }
    .ss-strip { position: absolute; left: 0; width: __W__px; top: __STRIP_TOP__px; height: __STRIP_H__px; overflow: hidden;
      background: #101114; box-shadow: 0 18px 60px rgba(0,0,0,0.55); }
    .ss-strip img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .ss-title { position: absolute; left: 0; width: __W__px; top: __TITLE_Y__px; transform: translateY(-50%); text-align: center;
      font-family: __SANS__; font-weight: 800; font-size: 112px; letter-spacing: -0.05em; line-height: 1.08; color: #FFFFFF;
      padding: 0.30em 0.25em 0.10em; text-shadow: 0 0 18px rgba(255,255,255,0.35); }
    .ss-caption { position: absolute; left: 60px; width: __CAPW__px; top: __CAP_TOP__px; text-align: center;
      font-family: __SANS__; font-weight: 600; font-size: __SEC__px; letter-spacing: -0.02em; line-height: 1.2; color: #FFFFFF;
      padding: 0.2em 0; text-shadow: 0 2px 10px rgba(0,0,0,0.5); }
    .ss-kw { font-weight: 800; font-size: 1em; letter-spacing: 0.01em; text-transform: uppercase; color: __ACCENT__; }
    """
    css = (css.replace("__ZOOM__", f"{zoom:g}").replace("__BLUR__", str(blur_px)).replace("__DARK__", f"{dark:g}")
              .replace("__W__", str(width)).replace("__STRIP_TOP__", str(strip_top)).replace("__STRIP_H__", str(strip_h))
              .replace("__TITLE_Y__", f"{title_y:.0f}").replace("__CAP_TOP__", f"{cap_top:.0f}").replace("__CAPW__", str(width - 120))
              .replace("__SEC__", str(sec))
              .replace("__SANS__", sans).replace("__ACCENT__", accent))
    body = f"""
    <div id="layoutRoot">
      <div class="ss-plate" data-slot="aroll_plate"><div class="ss-plate-img" style="background-image:url('{plate}')"></div></div>
      {title_html}
      <div class="ss-strip" data-slot="screen_content"><img alt="" src="{screen}" /></div>
      <div class="ss-caption" data-slot="caption">{kw_html}{esc(caption)}</div>
    </div>
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=_LAYOUT_JS_FINAL_STATE)


def _build_card_916(props: dict[str, Any], width: int, height: int) -> str:
    """9:16 card with a solid white border on a spotlight-grey stage; yellow label overlapping the lower-left edge."""
    sans = resolve_layout_font(props.get("font_family"))
    accent = nfc(props.get("accent_hex") or _dviet_accent_hex("yellow_bright"))
    card_w = int(props.get("card_width") or 540)
    card_h = int(round(card_w * 16 / 9))
    border = int(props.get("border_px") or 8)
    radius = int(props.get("radius_px") or 30)
    cy = float(props.get("card_center_y_pct", 47.0)) / 100.0 * height
    label = nfc(props.get("label", "edited"))
    media = image_to_safe_data_url(props.get("card_image"), fallback_variant="raw1")
    transparent = nfc(props.get("stage", "spotlight_grey")).lower() == "transparent"
    stage_bg = "transparent" if transparent else "radial-gradient(ellipse 70% 55% at 50% 38%, #8e8e93 0%, #55555a 38%, #1d1d20 100%)"
    css = """
    #layoutRoot { position: absolute; inset: 0; will-change: transform, opacity; }
    .cd-stage { position: absolute; inset: 0; background: __STAGE__; }
    .cd-card { position: absolute; left: __CARD_X__px; top: __CARD_TOP__px; width: __CARD_W__px; height: __CARD_H__px;
      border: __BORDER__px solid #FFFFFF; border-radius: __RADIUS__px; background: #000; box-shadow: 0 24px 70px rgba(0,0,0,0.5); }
    .cd-media { position: absolute; inset: 0; border-radius: calc(__RADIUS__px - __BORDER__px); overflow: hidden; }
    .cd-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .cd-label { position: absolute; left: 22px; bottom: -34px; font-family: __SANS__; font-weight: 800; font-size: __SEC__px;
      letter-spacing: -0.04em; line-height: 1.1; padding: 0.30em 0.25em 0.10em; color: __ACCENT__;
      text-shadow: 0 6px 18px rgba(0,0,0,0.55); }
    """
    css = (css.replace("__STAGE__", stage_bg).replace("__CARD_X__", str(int(round((width - card_w) / 2))))
              .replace("__CARD_TOP__", str(int(round(cy - card_h / 2)))).replace("__CARD_W__", str(card_w))
              .replace("__CARD_H__", str(card_h)).replace("__BORDER__", str(border)).replace("__RADIUS__", str(radius))
              .replace("__SANS__", sans).replace("__ACCENT__", accent).replace("__SEC__", str(secondary_text_px(props))))
    body = f"""
    <div id="layoutRoot">
      <div class="cd-stage" data-slot="stage"></div>
      <div class="cd-card">
        <div class="cd-media" data-slot="card_media"><img alt="" src="{media}" /></div>
        <div class="cd-label" data-slot="card_label">{esc(label)}</div>
      </div>
    </div>
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=_LAYOUT_JS_FINAL_STATE)


def _build_profile_card(props: dict[str, Any], width: int, height: int) -> str:
    """Fake profile card (avatar, handle, three counts, bio): ~70 % wide, centred at y ~43 %, semi-transparent dark grey."""
    sans = resolve_layout_font(props.get("font_family"))
    card_w = int(width * float(props.get("card_width_pct", 92.0)) / 100.0)  # v7.9.0: 92 % (was 70 %) for the 70 px text
    sec = secondary_text_px(props)
    cy = float(props.get("card_center_y_pct", 43.0)) / 100.0 * height
    name = nfc(props.get("display_name", "Minh Anh | Video Editor"))
    handle = nfc(props.get("handle", "@minhanh.edit"))
    bio = nfc(props.get("bio", "đang học dựng video mỗi ngày"))
    stats = props.get("stats") or [
        {"value": "0", "label": "bài viết"},
        {"value": "0", "label": "người theo dõi"},
        {"value": "1", "label": "đang theo dõi"},
    ]
    stats = [{"value": nfc(s.get("value", "0")), "label": nfc(s.get("label", ""))} for s in list(stats)[:3]]
    while len(stats) < 3:
        stats.append({"value": "0", "label": ""})
    slot_names = ("stat_posts", "stat_followers", "stat_following")
    stat_html = "".join(
        f'<div class="pc-stat" data-slot="{slot_names[i]}"><div class="pc-num">{esc(s["value"])}</div><div class="pc-lbl">{esc(s["label"])}</div></div>'
        for i, s in enumerate(stats)
    )
    if props.get("avatar_image"):
        avatar_inner = f'<img alt="" src="{image_to_safe_data_url(props["avatar_image"])}" />'
    else:
        initial = esc((nfc(props.get("avatar_text") or name).strip()[:1] or "?").upper())
        avatar_inner = f'<span class="pc-initial">{initial}</span>'
    css = """
    #layoutRoot { position: absolute; inset: 0; will-change: transform, opacity; }
    .pc-card { position: absolute; left: __CARD_X__px; top: __CARD_CY__px; transform: translateY(-50%); width: __CARD_W__px; padding: 36px 40px 38px;
      border-radius: 28px; background: rgba(34,34,38,0.62); backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px);
      border: 1px solid rgba(255,255,255,0.14); color: #FFFFFF; font-family: __SANS__; }
    .pc-head { display: flex; align-items: center; gap: 26px; }
    .pc-avatar { width: 150px; height: 150px; border-radius: 50%; overflow: hidden; flex: 0 0 auto;
      background: linear-gradient(135deg, #f4c40c, #d79e00); display: flex; align-items: center; justify-content: center; }
    .pc-avatar img { width: 100%; height: 100%; object-fit: cover; }
    .pc-initial { font-size: __TTL__px; font-weight: 800; color: #111111; padding-top: 0.12em; }
    .pc-name { font-size: __SEC__px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.12; padding-top: 0.1em; }
    .pc-handle { font-size: __SEC__px; font-weight: 500; color: rgba(255,255,255,0.68); line-height: 1.2; }
    .pc-stats { display: flex; flex-direction: column; gap: 2px; margin-top: 26px; padding-top: 18px; border-top: 1px solid rgba(255,255,255,0.14); }
    .pc-stat { display: flex; align-items: baseline; gap: 0.3em; }
    .pc-num { font-size: __SEC__px; font-weight: 800; line-height: 1.2; min-width: 1.2em; }
    .pc-lbl { font-size: __SEC__px; font-weight: 500; color: rgba(255,255,255,0.68); line-height: 1.2; }
    .pc-bio { margin-top: 18px; font-size: __SEC__px; font-weight: 500; line-height: 1.2; color: rgba(255,255,255,0.88); padding-top: 0.1em; }
    """
    css = (css.replace("__CARD_X__", str(int(round((width - card_w) / 2)))).replace("__CARD_CY__", str(int(round(cy))))
              .replace("__CARD_W__", str(card_w)).replace("__SANS__", sans).replace("__SEC__", str(sec))
              .replace("__TTL__", str(round(sec * 1.2))))
    body = f"""
    <div id="layoutRoot">
      <div class="pc-card">
        <div class="pc-head">
          <div class="pc-avatar" data-slot="avatar">{avatar_inner}</div>
          <div>
            <div class="pc-name" data-slot="display_name">{esc(name)}</div>
            <div class="pc-handle" data-slot="handle">{esc(handle)}</div>
          </div>
        </div>
        <div class="pc-stats">{stat_html}</div>
        <div class="pc-bio" data-slot="bio">{esc(bio)}</div>
      </div>
    </div>
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=_LAYOUT_JS_FINAL_STATE)


FEATHER_CLUSTER_SELFTEST_PROPS: dict[str, Any] = {
    # No kicker: ALL-CAPS kickers contradict the SKILL.md anti-pattern (0.0 % of @__dviet frames).
    "kicker": "",
    "main_text": "độ sâu điện ảnh",
    "accent_text": "Chạm Cảm Xúc Thật",
    "badge_text": "NFC: Ộ • Ệ • Ữ • Ắ • Ẳ",
    "jewel_accent": "gold",
}

LAYOUT_SELFTEST_PROPS: dict[str, dict[str, Any]] = {
    "screen_strip": {"title": "bước một", "caption": "tạo clip ghép bằng phím tắt", "caption_keyword": "MÁY PHÁT NHẠC 3"},
    "card_916": {"label": "edited"},
    "profile_card": {},
}


# v7.9.0: one sample per template / mode WITH the optional secondary texts (kicker, pill, sub lines) so the size and word-gap
# checks (tests/test_text_legibility_v79.py) and the acceptance renders see every text a template can draw.
TEXT_ACCEPTANCE_SAMPLES: list[dict[str, Any]] = [
    {"name": "feather_cluster", "template": "dviet_overlapping_feather_cluster", "props": dict(FEATHER_CLUSTER_SELFTEST_PROPS, kicker="mẹo dựng nhanh")},
    {"name": "bento_steps", "template": "frosted_glass_bento_steps", "props": {"demo": True, "jewel_accent": "emerald", "bottom_note": "Chuẩn hóa ánh sáng & độ nét tự nhiên"}},
    {"name": "clinical", "template": "clinical_before_after_1_to_28", "props": {"jewel_accent": "ice_cyan"}},
    {"name": "course_box", "template": "course_3d_matte_asset_box", "props": {"jewel_accent": "gold", "gobo_shadow": True}},
    {"name": "scorecard", "template": "tactile_review_glass_scorecard", "props": {"jewel_accent": "gold", "score": 9.4}},
    {"name": "prompt_browser", "template": "isometric_3d_prompt_browser", "props": {"jewel_accent": "emerald", "type_start_s": 0.08, "type_end_s": 1.6}},
    {"name": "polaroid", "template": "skewed_3d_polaroid_trio", "props": {"demo": True, "jewel_accent": "gold", "bottom_note": "Giữ trọn kết cấu ánh sáng thật"}},
    {"name": "polaroid_s076", "template": "skewed_3d_polaroid_trio", "plate_scale": 0.76,
     "props": {"captions": ["Ảnh thô 01", "Ảnh thô 02", "Ảnh thô 03"], "bottom_note": "chụp vội trên bàn làm việc", "plate_scale": 0.76}},
    {"name": "doctor_lower_third", "template": "doctor_authority_lower_third", "props": {"jewel_accent": "ice_cyan"}, "width": 1080, "height": 600},
    {"name": "doctor_lower_third_916", "template": "doctor_authority_lower_third", "props": {"jewel_accent": "ice_cyan"}},
    {"name": "screen_strip", "template": "screen_strip", "props": dict(LAYOUT_SELFTEST_PROPS["screen_strip"])},
    {"name": "card_916", "template": "card_916", "props": dict(LAYOUT_SELFTEST_PROPS["card_916"])},
    {"name": "profile_card", "template": "profile_card", "props": dict(LAYOUT_SELFTEST_PROPS["profile_card"])},
    {"name": "kt01", "template": "kt01_kiss_editorial_2line", "props": {"helper_text": "nhịp dựng mượt", "main_text": "chạm đúng cảm xúc", "pill_text": "mới", "jewel_accent": "gold"}},
    {"name": "kt02", "template": "kt02_feather_swash_overlap", "props": {"kicker": "bí quyết", "main_text": "độ sâu ánh sáng", "accent_text": "Chuẩn Điện Ảnh", "pill_text": "60 fps", "jewel_accent": "gold"}},
    {"name": "kt03", "template": "kt03_per_word_nonlinear_bloom", "props": {"kicker": "nhớ nhé", "pill_text": "mẹo", "word_triggers": [
        {"word": "cứ", "at_s": 0.02, "hue": "white"}, {"word": "Camera", "at_s": 0.24, "hue": "gold", "italic": True, "scale": 1.08},
        {"word": "bật", "at_s": 0.12, "hue": "white"}]}},
    {"name": "kt04", "template": "kt04_ghost_to_focus_stack", "props": {"setup_text": "tưởng chỉ cần nét căng", "main_text": "chiều sâu quang học", "pill_text": "quang học", "jewel_accent": "ice_cyan"}},
    {"name": "kt05", "template": "kt05_wall_spatial_counterpoint", "props": {"mode": "left_right_counter", "left_text": "ánh sáng phẳng", "right_text": "tách khối thật", "accent_text": "Có Chiều Sâu", "jewel_accent": "crimson", "turn_at_s": 0.20}},
    {"name": "kt05_wall", "template": "kt05_wall_spatial_counterpoint", "props": {"mode": "wall_hop", "left_text": "chỉ một", "right_text": "điểm chạm sáng", "jewel_accent": "crimson"}},
    {"name": "kt06", "template": "kt06_bridge_anchor_live_swap", "props": {"anchor_text": "giữ trọn", "pill_text": "chân thật", "swap_words": [
        {"text": "màu da thật", "at_s": 0.04, "hue": "gold"}, {"text": "ánh mắt sống", "at_s": 0.28, "hue": "emerald", "italic": True}]}},
    {"name": "kt07", "template": "kt07_telescoping_char_rollout", "props": {"kicker": "từng ký tự", "main_text": "chữ việt ộ ệ ữ ắ ẳ", "accent_text": "Từng Ký Tự Mượt", "pill_text": "NFC", "jewel_accent": "gold"}},
    {"name": "kt08", "template": "kt08_mist_evaporation_reveal", "props": {"kicker": "nhẹ thôi", "main_text": "vùng sáng dịu", "accent_text": "Tan Nhẹ Như Sương", "keep_mist_tail": True, "pill_text": "mềm", "jewel_accent": "ice_cyan"}},
    {"name": "kt09", "template": "kt09_strike_myth_laser_2phase", "props": {"kicker": "đừng tin", "main_text": "nhìn giả trân", "accent_text": "giữ chi tiết da thật", "pill_text": "sự thật", "jewel_accent": "emerald", "slash_at_s": 0.20}},
    {"name": "kt10", "template": "kt10_cursor_bars_pillar_gate", "props": {"kicker": "chỉ cần", "main_text": "3 bước khóa ảnh", "pill_text": "3 bước", "jewel_accent": "emerald"}},
    {"name": "kt11_arc", "template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "svg_arc", "main_text": "vòng sáng điện ảnh tự nhiên", "accent_text": "Tỏa Sáng", "jewel_accent": "gold"}},
    {"name": "kt11_tilt", "template": "kt11_cranial_svg_arc_or_tilt", "props": {"mode": "tilted_chest", "sub_text": "chạm cảm xúc", "main_text": "Đúng Nhịp Thật", "pill_text": "nhịp", "jewel_accent": "gold"}},
    {"name": "kt12_whisper", "template": "kt12_whisper_or_directional_echo", "props": {"mode": "whisper", "main_text": "nói nhỏ thôi", "pill_text": "thì thầm"}},
    {"name": "kt12_echo", "template": "kt12_whisper_or_directional_echo", "props": {"mode": "directional_echo", "main_text": "lặp lại", "accent_text": "đúng cấu trúc nhịp", "jewel_accent": "crimson", "echo_at_s": 0.12}},
]


def render_layout_templates_self_test(out_dir: Path) -> dict[str, Any]:
    """Render the three v7.4 layout templates to PNGs (1080x1920) and sanity-check them."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        {"template": t, "out": str(out_dir / f"layout_{i + 1:02d}_{t}.png"), "mode": "still", "width": 1080, "height": 1920,
         "props": LAYOUT_SELFTEST_PROPS[t]}
        for i, t in enumerate(LAYOUT_TEMPLATES)
    ]
    render_web_plates_batch(jobs, concurrency=3, strip_meta=True, quiet=True)
    pngs: dict[str, Any] = {}
    for job in jobs:
        p = Path(job["out"])
        raw = p.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"{p} is not a valid PNG")
        w, h = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        if (w, h) != (1080, 1920):
            raise AssertionError(f"{p} is {w}x{h}, expected 1080x1920")
        info: dict[str, Any] = {"path": str(p), "width": w, "height": h, "bytes": len(raw)}
        try:
            from PIL import Image, ImageStat

            with Image.open(p) as im:
                rgb = im.convert("RGB")
                spread = max(ImageStat.Stat(rgb).stddev)
                alpha_max = im.getchannel("A").getextrema()[1] if im.mode == "RGBA" else 255
            if spread < 8.0 or alpha_max < 200:
                raise AssertionError(f"{p.name} looks empty (stddev={spread:.1f}, alpha_max={alpha_max})")
            info["stddev"] = round(spread, 1)
        except ImportError:
            pass
        pngs[job["template"]] = info
    return {"ok": True, "pngs": pngs, "slots": LAYOUT_TEMPLATE_SLOTS}


# ---------------------------------------------------------------------------
# Template Dispatcher & Public Python API (`v7.0` + `v7.1`)
# ---------------------------------------------------------------------------

_BUILDERS = {
    # 8 Studio Cards & Clusters (`v7.0` + Continuous-Motion `v7.1`)
    "dviet_overlapping_feather_cluster": _build_dviet_overlapping_feather_cluster,
    "frosted_glass_bento_steps": _build_frosted_glass_bento_steps,
    "clinical_before_after_1_to_28": _build_clinical_before_after_1_to_28,
    "course_3d_matte_asset_box": _build_course_3d_matte_asset_box,
    "tactile_review_glass_scorecard": _build_tactile_review_glass_scorecard,
    "isometric_3d_prompt_browser": _build_isometric_3d_prompt_browser,
    "skewed_3d_polaroid_trio": _build_skewed_3d_polaroid_trio,
    "doctor_authority_lower_third": _build_doctor_authority_lower_third,
    # 3 @__dviet layout templates (v7.4.0)
    "screen_strip": _build_screen_strip,
    "card_916": _build_card_916,
    "profile_card": _build_profile_card,
    # 12 Kinetic Typography Templates (`v7.1` `@60fps` `.mov`)
    "kt01_kiss_editorial_2line": _build_kt01_kiss_editorial_2line,
    "kt02_feather_swash_overlap": _build_kt02_feather_swash_overlap,
    "kt03_per_word_nonlinear_bloom": _build_kt03_per_word_nonlinear_bloom,
    "kt04_ghost_to_focus_stack": _build_kt04_ghost_to_focus_stack,
    "kt05_wall_spatial_counterpoint": _build_kt05_wall_spatial_counterpoint,
    "kt06_bridge_anchor_live_swap": _build_kt06_bridge_anchor_live_swap,
    "kt07_telescoping_char_rollout": _build_kt07_telescoping_char_rollout,
    "kt08_mist_evaporation_reveal": _build_kt08_mist_evaporation_reveal,
    "kt09_strike_myth_laser_2phase": _build_kt09_strike_myth_laser_2phase,
    "kt10_cursor_bars_pillar_gate": _build_kt10_cursor_bars_pillar_gate,
    "kt11_cranial_svg_arc_or_tilt": _build_kt11_cranial_svg_arc_or_tilt,
    "kt12_whisper_or_directional_echo": _build_kt12_whisper_or_directional_echo,
}


KT_PILL_EXTRA_H = 64  # [ĐO] the 70 px pill is ~64 px taller than the old 18 px one: a kt plate that carries a pill grows by this much


def default_plate_height(template: str, props: dict[str, Any] | None = None) -> int:
    """Default plate height; v7.9.0: a kinetic plate with a pill (`badge_text` / `pill_text`) is KT_PILL_EXTRA_H taller so the
    70 px pill never clips (an explicit `height` always wins)."""
    h = int(TEMPLATE_DEFAULTS[template]["height"])
    pr = props or {}
    if template in KINETIC_TYPO_TEMPLATES and nfc(pr.get("badge_text") or pr.get("pill_text") or "").strip():
        h += KT_PILL_EXTRA_H
    return h


def list_templates() -> dict[str, dict[str, Any]]:
    return dict(TEMPLATE_DEFAULTS)


def build_template_html(
    template: str,
    props: dict[str, Any] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Generates standalone NFC-clean HTML5/CSS3/SVG markup for any Studio or Kinetic Typography Template."""
    key = nfc(template).strip()
    if key not in _BUILDERS:
        raise ValueError(
            f"Unknown Studio template '{key}'. Available: {', '.join(_BUILDERS.keys())}"
        )
    clean_props = normalize_props_nfc(props or {})
    defaults = TEMPLATE_DEFAULTS[key]
    w = int(width or clean_props.get("width") or defaults["width"])
    h = int(height or clean_props.get("height") or default_plate_height(key, clean_props))
    return _BUILDERS[key](clean_props, w, h)


KT_CHECKED_TEXT_FIELDS = ("kicker", "accent_text")  # main_text is required by every builder (`_prop_or_demo` raises without it)


def kt_dropped_text(template: str, props: dict[str, Any]) -> list[dict[str, str]]:
    """v7.9.3: the kicker / accent_text of `props` the built plate never draws (a silent text drop), as `[{field, text}]`.
    A field counts as drawn when every word of it appears in the page's visible markup (tags, <style> and <script> removed,
    whitespace ignored, case-folded), so per-word / per-character spans still count."""
    doc = build_template_html(template, props)
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", doc, flags=re.S | re.I)
    drawn = re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", " ", body))).casefold()
    out: list[dict[str, str]] = []
    for field in KT_CHECKED_TEXT_FIELDS:
        txt = nfc(props.get(field) or "").strip()
        if txt and any(tok.casefold() not in drawn for tok in txt.split()):
            out.append({"field": field, "text": txt})
    return out


def _rel_luminance(rgb: Any) -> Any:
    """WCAG relative luminance of sRGB values in 0..255 (scalar triple or an ...x3 array)."""
    import numpy as np  # lazy: only the contrast check needs numpy

    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


CONTRAST_BG_PERCENTILE = 90.0  # the background patch judged: p90 luminance under light ink, p10 under dark ink (busy footage)


def text_contrast_ratio(base_frame: Any, ink_bbox: Sequence[float], text_hex: str = "#FAFAFA", *,
                        percentile: float = CONTRAST_BG_PERCENTILE) -> float | None:
    """v7.9.3: WCAG contrast ratio of `text_hex` ink against the background under `ink_bbox` ([x0, y0, x1, y1] frame px) of
    `base_frame` (image path, PIL image or HxWx3 uint8 array). A busy background is judged by its worst patch: the `percentile`
    luminance nearest the ink (light ink: the bright tail, dark ink: the dark tail). None without a frame or an empty box."""
    if base_frame is None:
        return None
    import numpy as np

    if isinstance(base_frame, (str, Path)):
        from PIL import Image

        with Image.open(base_frame) as im:
            arr = np.asarray(im.convert("RGB"))
    else:
        arr = np.asarray(base_frame.convert("RGB") if hasattr(base_frame, "convert") else base_frame)[..., :3]
    h, w = arr.shape[:2]
    x0, y0 = max(0, int(ink_bbox[0])), max(0, int(ink_bbox[1]))
    x1, y1 = min(w, int(math.ceil(ink_bbox[2]))), min(h, int(math.ceil(ink_bbox[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    hx = nfc(text_hex).lstrip("#")
    ink_l = float(_rel_luminance([int(hx[i:i + 2], 16) for i in (0, 2, 4)]))
    bg = _rel_luminance(arr[y0:y1, x0:x1].reshape(-1, 3))
    bg_l = float(np.percentile(bg, percentile if ink_l >= 0.5 else 100.0 - percentile))
    hi, lo = max(ink_l, bg_l), min(ink_l, bg_l)
    return round((hi + 0.05) / (lo + 0.05), 3)


ENGINE_TIMEOUT_BASE_S = 120.0     # Chrome launch + page loads
ENGINE_TIMEOUT_PER_FRAME_S = 0.5  # [UOC] per rendered frame and worker (a 240-frame 60 fps kt plate takes ~20-40 s on one tab)


def engine_timeout_s(engine_jobs: Sequence[dict[str, Any]], concurrency: int) -> float:
    """v7.9.1: outer timeout of one engine run (env `PFD_ENGINE_TIMEOUT_S` overrides): base + frames x per-frame / workers."""
    if os.environ.get("PFD_ENGINE_TIMEOUT_S"):
        return max(10.0, float(os.environ["PFD_ENGINE_TIMEOUT_S"]))
    frames = sum(max(1, int(j.get("frames") or 1)) for j in engine_jobs)
    return ENGINE_TIMEOUT_BASE_S + ENGINE_TIMEOUT_PER_FRAME_S * frames / max(1, int(concurrency))


def _run_engine_batch(engine_jobs: list[dict[str, Any]], tmp_root: Path, *, concurrency: int, alpha_codec: str, quiet: bool,
                      tag: str = "batch_jobs") -> list[dict[str, Any]]:
    """One headless-Chrome run of `web_cinema_plate_engine.mjs` over `engine_jobs` -> the engine's per-job results.
    v7.9.1: bounded by `engine_timeout_s` (the engine gets a deadline 15 s earlier so it tears Chrome down itself); an empty or
    non-JSON output raises a clear RuntimeError; a job the engine could not render comes back as {ok: False, failed: True,
    error} next to the good ones (a warning names it), and only a batch where EVERY job failed raises."""
    batch_json_path = tmp_root / f"{tag}.json"
    batch_json_path.write_text(json.dumps({"concurrency": concurrency, "alphaCodec": alpha_codec, "jobs": engine_jobs},
                                          ensure_ascii=False, indent=2), encoding="utf-8")
    timeout_s = engine_timeout_s(engine_jobs, concurrency)
    cmd = [resolve_node_binary(), str(ENGINE_MJS), "--batch-json", str(batch_json_path), "--concurrency", str(concurrency),
           "--alpha-codec", str(alpha_codec), "--batch-deadline-ms", str(int(max(5.0, timeout_s - 15.0) * 1000))]
    if quiet:
        cmd.append("--quiet")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"web_cinema_plate_engine.mjs timed out after {timeout_s:.0f} s on {len(engine_jobs)} job(s) "
                           f"(env PFD_ENGINE_TIMEOUT_S raises the limit)") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"web_cinema_plate_engine.mjs failed (exit {proc.returncode}):\n{proc.stderr}")
    lines = (proc.stdout or "").strip().splitlines()
    if not lines:
        raise RuntimeError(f"web_cinema_plate_engine.mjs exited 0 with no output (expected one JSON line):\n{(proc.stderr or '')[-2000:]}")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"web_cinema_plate_engine.mjs printed no JSON result: {lines[-1][:300]!r}") from exc
    results = list(payload.get("results", []))
    failed = [r for r in results if r.get("ok") is False]
    for r in failed:
        r["failed"] = True
    if failed and len(failed) == len(results):
        raise RuntimeError("web_cinema_plate_engine.mjs rendered none of the jobs: " +
                           "; ".join(f"{Path(str(r.get('out', '?'))).name}: {r.get('error')}" for r in failed))
    if failed:
        warnings.warn(f"PLATE RENDER FAILED for {len(failed)} of {len(results)} job(s), the others rendered: " +
                      "; ".join(f"{Path(str(r.get('out', '?'))).name}: {r.get('error')}" for r in failed), stacklevel=2)
    return results


CHROME_WORKERS_MAX = 4  # CDP tabs the engine accepts


def resolve_chrome_workers(requested: int | None = None, *, workspace_context: Any = None, work_dir: str | Path | None = None) -> int:
    """v7.9.1: Chrome tab count for one engine run. `requested` (None = the cap) is limited by CHROME_WORKERS_MAX, env
    `PFD_CHROME_WORKERS`, and `ram_governance.max_chrome_workers` of the workspace context (probe_and_align: studio tier = 2) when
    one is given: a dict, a path to workspace_context.json, or `work_dir` holding workspace_context.json. Never below 1."""
    cap = CHROME_WORKERS_MAX
    env = os.environ.get("PFD_CHROME_WORKERS", "").strip()
    if env:
        try:
            cap = min(cap, max(1, int(env)))
        except ValueError:
            warnings.warn(f"PFD_CHROME_WORKERS={env!r} is not an integer; ignored", stacklevel=2)
    ctx = workspace_context
    if ctx is None and work_dir is not None and (Path(work_dir).expanduser() / "workspace_context.json").is_file():
        ctx = Path(work_dir).expanduser() / "workspace_context.json"
    if isinstance(ctx, (str, Path)):
        ctx = json.loads(Path(ctx).expanduser().read_text(encoding="utf-8"))
    if isinstance(ctx, dict):
        ctx_max = (ctx.get("ram_governance") or {}).get("max_chrome_workers")
        if ctx_max is not None:
            cap = min(cap, max(1, int(ctx_max)))
    return max(1, min(cap, int(requested))) if requested is not None else cap


KT_FIT_FPS = 60
KT_FIT_CENTRE_TOL_PX = 24  # [UOC] a kt rig's content may sit this far off the plate centre; the fit never grows past content + margins + 2x this
KT_FIT_FRAMES = tuple(range(0, 181, 3)) + (None,)  # entrance + hold of a 240-frame clip, None = the settled still (no exit frames)


def fit_kt_plate_heights(specs: Sequence[tuple[str, dict[str, Any], int, int]], tmp_root: Path, *, concurrency: int = 4,
                         quiet: bool = True, max_passes: int = 3) -> list[int]:
    """v7.9.0 repair: a default-height kinetic plate grows to its content. `specs` = [(template, props, width, height)]. Chrome
    measures the union box of every visible text run and pill over the entrance + hold frames and the settled still; a plate whose
    box comes closer than KT_PLATE_MARGIN_PX to its top / bottom edge grows by the shortfall on both sides (the rig is centred), so
    the 70 px pill and wrapped long copy never clip. Re-measured until it fits (`max_passes`). Returns the heights.
    v7.9.0 repair: the box is real ink (a <textPath> counts only its drawn glyphs: an overflowing arc grew 620 -> 1350 on the bbox
    of its dropped glyphs) and the growth is capped at the content height + 2 x KT_PLATE_MARGIN_PX + 2 x KT_FIT_CENTRE_TOL_PX:
    content further off-centre than that warns (centre the rig) instead of ballooning the plate."""
    heights = [int(h) for _t, _p, _w, h in specs]
    todo = list(range(len(specs)))
    m = KT_PLATE_MARGIN_PX
    for n_pass in range(max_passes):
        if not todo:
            break
        engine_jobs = []
        for i in todo:
            tpl, props, w, _h = specs[i]
            html_file = tmp_root / f"fit_{n_pass}_{i:03d}_{tpl}.html"
            html_file.write_text(build_template_html(tpl, props, width=w, height=heights[i]), encoding="utf-8")
            engine_jobs.append({"html": str(html_file), "out": str(tmp_root / f"fit_{n_pass}_{i:03d}.json"), "mode": "probe", "width": w,
                                "height": heights[i], "scale": 1.0, "fps": KT_FIT_FPS, "frames": 240, "probeFrom": 0, "probeTo": -1,
                                "contentBoxFrames": list(KT_FIT_FRAMES)})
        results = _run_engine_batch(engine_jobs, tmp_root, concurrency=concurrency, alpha_codec="prores4444", quiet=quiet,
                                    tag=f"fit_jobs_{n_pass}")
        nxt = []
        for i, res in zip(todo, results):
            box = res.get("contentBox")
            if not box:
                continue
            short = max(0.0, m - box[1], box[3] - (heights[i] - m))
            if short > 0.5:
                want = heights[i] + 2 * int(math.ceil(short))
                cap = max(heights[i], int(math.ceil(box[3] - box[1])) + 2 * m + 2 * KT_FIT_CENTRE_TOL_PX)
                if want > cap:
                    off = (box[1] + box[3]) / 2 - heights[i] / 2
                    warnings.warn(f"{specs[i][0]}: content {box[3] - box[1]:.0f} px tall sits {off:+.0f} px off the plate centre; plate growth "
                                  f"capped at {cap} px (was {want}): centre the rig", stacklevel=2)
                    want = cap
                if want > heights[i]:
                    heights[i] = want
                    nxt.append(i)
        todo = nxt
    return heights


def render_web_plates_batch(
    jobs: Sequence[dict[str, Any]],
    *,
    concurrency: int | None = None,
    alpha_codec: str = "prores4444",
    strip_meta: bool = True,
    quiet: bool = False,
    workspace_context: Any = None,
    work_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Renders multiple Studio plates (`.png` RGBA stills and/or `.mov` ProRes 4444 / qtrle clips)
    in parallel (`concurrency` up to 4 CDP tabs) inside a SINGLE Chrome Headless process.

    v7.9.0: every job's HTML goes through `audit_plate_text_px` at the job's `plate_scale` (job key or prop, default 1.0 = the
    plate fills the canvas) BEFORE rendering, and the engine measures every drawn text at the settled frame (computed font size x
    screen scale, `textSizes`) AFTER rendering. Each result carries `text_audit` = {ok, severity, plate_scale, undersized:
    [[selector, canvas px]], rendered_undersized: [[label, canvas px, text]]}. Undersized text (< MIN_OVERLAY_FONT_PX on the canvas)
    is a HARD BLOCK: `UndersizedTextError` is raised (CSS audit: before Chrome starts; rendered audit: after, the batch fails) unless
    the job is `decorative: true`, which only warns (severity "warn").
    Probe jobs (`mode: "probe"`, `probe_from` / `probe_to` frame range, optional `probe_ids`) write nothing and return the engine's
    per-frame `wordGaps` (see `probe_word_gaps`).
    v7.9.1: `concurrency` (None = the cap) goes through `resolve_chrome_workers` (env PFD_CHROME_WORKERS, workspace context /
    work dir `max_chrome_workers`). A job the engine fails to render comes back as {ok: False, failed: True, error} (warned) and
    the others are kept; UndersizedTextError / TextPathOverflowError stay fatal for the whole batch.
    """
    if not jobs:
        return []
    resolve_node_binary()
    if not ENGINE_MJS.is_file():
        raise FileNotFoundError(f"Engine script missing: {ENGINE_MJS}")

    safe_concurrency = resolve_chrome_workers(concurrency, workspace_context=workspace_context, work_dir=work_dir)

    with tempfile.TemporaryDirectory(prefix="usd-v71-plates-") as tmpdir:
        tmp_root = Path(tmpdir)
        engine_jobs: list[dict[str, Any]] = []
        out_paths: list[Path] = []
        text_audits: list[dict[str, Any]] = []

        sized = []  # (template, props, width, height, height given explicitly)
        for job in jobs:
            tpl = nfc(job["template"]).strip()
            if tpl not in TEMPLATE_DEFAULTS:
                raise ValueError(f"Unknown template '{tpl}'. Available: {', '.join(TEMPLATE_DEFAULTS.keys())}")
            props = normalize_props_nfc(job.get("props") or {})
            w = int(job.get("width") or props.get("width") or TEMPLATE_DEFAULTS[tpl]["width"])
            explicit_h = job.get("height") or props.get("height")
            sized.append((tpl, props, w, int(explicit_h or default_plate_height(tpl, props)), bool(explicit_h)))

        for idx, job in enumerate(jobs):
            tpl, props, w, h, _explicit = sized[idx]
            out_path = Path(job["out"]).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            html_doc = build_template_html(tpl, props, width=w, height=h)
            plate_scale = float(job.get("plate_scale", props.get("plate_scale", 1.0)))
            small = audit_plate_text_px(html_doc, plate_scale)
            text_audits.append({"ok": not small, "severity": "ok" if not small else ("warn" if job.get("decorative") else "error"),
                                "plate_scale": plate_scale, "undersized": [[sel, px] for sel, px in small], "rendered_undersized": [],
                                "decorative": bool(job.get("decorative")), "name": out_path.name})
            html_file = tmp_root / f"plate_{idx:03d}_{tpl}.html"
            html_file.write_text(html_doc, encoding="utf-8")

            default_fps = 60 if tpl in KINETIC_TYPO_TEMPLATES else 30
            fps = float(job.get("fps", default_fps))
            duration = job.get("duration_sec", job.get("duration"))
            total_frames = job.get("total_frames", job.get("frames"))
            if total_frames is None:
                total_frames = max(1, round(float(duration if duration is not None else 2.0) * fps))

            engine_job: dict[str, Any] = {
                "html": str(html_file),
                "out": str(out_path),
                "mode": job.get("mode", "auto"),
                "width": w,
                "height": h,
                "scale": float(job.get("device_scale_factor", job.get("scale", 1.0))),
                "fps": fps,
                "frames": int(total_frames),
                "alphaCodec": job.get("alpha_codec", job.get("alphaCodec", alpha_codec)),
            }
            if job.get("downscale_to_logical") is not None or job.get("downscaleToLogical") is not None:
                engine_job["downscaleToLogical"] = bool(
                    job.get("downscale_to_logical", job.get("downscaleToLogical"))
                )
            if job.get("frame_idx") is not None:
                engine_job["frameIdx"] = int(job["frame_idx"])
            for src, dst in (("probe_from", "probeFrom"), ("probe_to", "probeTo"), ("probe_ids", "probeIds"),
                             ("content_box_frames", "contentBoxFrames")):
                if job.get(src) is not None:
                    engine_job[dst] = job[src]

            engine_jobs.append(engine_job)
            out_paths.append(out_path)

        blocked = [a for a in text_audits if a["severity"] == "error"]
        if blocked:  # v7.9.0 hard block: fail before Chrome starts
            raise UndersizedTextError("; ".join(f"{a['name']}: CSS text below the {MIN_OVERLAY_FONT_PX}px legibility floor at plate scale "
                                                f"{a['plate_scale']}: {a['undersized']}" for a in blocked), blocked)

        # v7.9.0 repair: a kinetic plate at its default height grows to its content (the pill and wrapped long copy never clip);
        # identical (template, props, width, height) jobs are measured once
        fit_keys: dict[str, int] = {}
        for i, sz in enumerate(sized):
            if sz[0] in KINETIC_TYPO_TEMPLATES and not sz[4]:
                fit_keys.setdefault(json.dumps([sz[0], sz[1], sz[2], sz[3]], sort_keys=True, ensure_ascii=False, default=str), i)
        if fit_keys:
            reps = list(fit_keys.values())
            fitted = dict(zip(reps, fit_kt_plate_heights([sized[i][:4] for i in reps], tmp_root, concurrency=safe_concurrency, quiet=quiet)))
            for i, sz in enumerate(sized):
                if sz[0] in KINETIC_TYPO_TEMPLATES and not sz[4]:
                    h_fit = fitted[fit_keys[json.dumps([sz[0], sz[1], sz[2], sz[3]], sort_keys=True, ensure_ascii=False, default=str)]]
                    if h_fit != sz[3]:
                        sized[i] = sz[:3] + (h_fit,) + sz[4:]
                        Path(engine_jobs[i]["html"]).write_text(build_template_html(sz[0], sz[1], width=sz[2], height=h_fit), encoding="utf-8")
                        engine_jobs[i]["height"] = h_fit

        results = _run_engine_batch(engine_jobs, tmp_root, concurrency=safe_concurrency, alpha_codec=alpha_codec, quiet=quiet)
        for res, sz in zip(results, sized):
            res["plate_width"], res["plate_height"] = sz[2], sz[3]
        for res, audit, out_path in zip(results, text_audits, out_paths):
            rendered = [[t["label"], round(float(t["effPx"]) * audit["plate_scale"], 1), t["text"]] for t in (res.get("textSizes") or [])
                        if float(t["effPx"]) * audit["plate_scale"] < MIN_OVERLAY_FONT_PX - 1e-6]
            audit["rendered_undersized"] = rendered
            if rendered or audit["undersized"]:
                audit["ok"] = False
                audit["severity"] = "warn" if audit["decorative"] else "error"
            res["text_audit"] = audit
            if audit["severity"] == "warn":
                warnings.warn(f"{out_path.name} (decorative): text below the {MIN_OVERLAY_FONT_PX}px legibility floor at plate scale "
                              f"{audit['plate_scale']}: {audit['undersized'] or rendered}", stacklevel=2)
        blocked = [a for a in text_audits if a["severity"] == "error"]
        if blocked:  # v7.9.0 hard block: a drawn text measured below the floor fails the whole batch
            raise UndersizedTextError("; ".join(f"{a['name']}: rendered text below the {MIN_OVERLAY_FONT_PX}px legibility floor at plate "
                                                f"scale {a['plate_scale']}: {a['rendered_undersized']}" for a in blocked), blocked)
        # v7.9.0 repair hard block: a <textPath> longer than its path drops glyphs silently (decorative or not)
        for res, audit in zip(results, text_audits):
            audit["textpath_overflow"] = [t for t in (res.get("textPaths") or []) if t.get("overflow")]
        overflow = [a for a in text_audits if a["textpath_overflow"]]
        if overflow:
            for a in overflow:
                a["ok"], a["severity"] = False, "error"
            raise TextPathOverflowError("; ".join(
                f"{a['name']}: textPath text overflows its path, {t['chars'] - t['rendered']} of {t['chars']} characters dropped "
                f"(text {t['textLen']} px on a {t['pathLen']} px path): '{t['text']}'" for a in overflow for t in a["textpath_overflow"]),
                overflow)

        if strip_meta:
            for p, res in zip(out_paths, results):
                if p.is_file() and res.get("ok") is not False:
                    strip_media_metadata(p)

        return results


def probe_word_gaps(
    template: str,
    props: dict[str, Any] | None = None,
    *,
    total_frames: int = 240,
    frames: tuple[int, int] = (0, 90),
    fps: int = 60,
    ids: Sequence[str] | None = None,
    width: int | None = None,
    height: int | None = None,
    plate_scale: float = 1.0,
) -> dict[str, Any]:
    """v7.9.0: steps frames `frames` (inclusive) of a `total_frames` clip in Chrome and returns the engine probe: `wordGaps` =
    [{frameIdx, lines: [{id, wordSpacing, worst: {pair, gapPx, blurPx, effPx, needPx, emPx, opacity} | None}]}] (screen px; ink gap
    minus both neighbours' blur vs 0.25 em; pairs under 15 % opacity are skipped like `motion_gate.word_gap_series`) and `textSizes`
    at the settled frame. Lines = `ids`, else every [data-ws-nat0] / [data-pfd-line] element. Nothing is written."""
    with tempfile.TemporaryDirectory(prefix="pfd-probe-") as td:
        job = {"template": template, "props": props or {}, "out": str(Path(td) / "probe.json"), "mode": "probe", "fps": fps,
               "total_frames": int(total_frames), "probe_from": int(frames[0]), "probe_to": int(frames[1]), "plate_scale": plate_scale}
        if ids:
            job["probe_ids"] = ids if isinstance(ids, str) else list(ids)  # "*" = every drawn text line
        if width:
            job["width"] = width
        if height:
            job["height"] = height
        return render_web_plates_batch([job], concurrency=1, strip_meta=False, quiet=True)[0]


def render_web_plate(
    template: str,
    props: dict[str, Any] | None = None,
    out_path: str | Path = "plate.png",
    *,
    mode: str = "auto",
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
    duration_sec: float = 2.0,
    total_frames: int | None = None,
    frame_idx: int | None = None,
    device_scale_factor: float = 1.0,
    alpha_codec: str = "prores4444",
    strip_meta: bool = True,
    quiet: bool = False,
) -> dict[str, Any]:
    """Renders a single Studio HTML5/CSS3/SVG plate to `.png` (RGBA) or `.mov` (ProRes 4444 / qtrle)."""
    resolved_fps = fps if fps is not None else (60 if nfc(template).strip() in KINETIC_TYPO_TEMPLATES else 30)
    res = render_web_plates_batch(
        [
            {
                "template": template,
                "props": props or {},
                "out": str(out_path),
                "mode": mode,
                "width": width,
                "height": height,
                "fps": resolved_fps,
                "duration_sec": duration_sec,
                "total_frames": total_frames,
                "frame_idx": frame_idx,
                "device_scale_factor": device_scale_factor,
                "alpha_codec": alpha_codec,
            }
        ],
        concurrency=1,
        alpha_codec=alpha_codec,
        strip_meta=strip_meta,
        quiet=quiet,
    )
    return res[0]


def _extract_plain_hero_text(template: str, props: dict[str, Any]) -> str:
    parts: list[str] = []
    if template == "kt03_per_word_nonlinear_bloom":
        wt = _normalize_kt03_word_triggers(props, nfc(props.get("jewel_accent") or props.get("accent") or "gold"))
        return " ".join(x["word"] for x in wt).strip()
    if template == "kt06_bridge_anchor_live_swap":
        anchor = _prop_or_demo(template, props, ("anchor_text", "kicker"), "giữ trọn", required=False)
        swaps = _normalize_kt06_swaps(props, nfc(props.get("jewel_accent") or props.get("accent") or "gold"))
        swap_str = " / ".join(s["text"] for s in swaps)
        return f"{anchor} {swap_str}".strip()
    if template == "kt05_wall_spatial_counterpoint":
        k5 = _resolve_kt05_texts(props)
        l_txt = " ".join(c["text"] for c in k5["left_clauses"])
        r_txt = " ".join(x for x in (k5["right_text"], k5["accent_text"]) if x)
        return " — ".join(x for x in (l_txt, r_txt) if x)

    for key in ("setup_text", "sub_text", "main_text", "line2_text", "accent_text"):
        val = nfc(props.get(key) or "").strip()
        if val and val not in parts:
            parts.append(val)
    if not parts:
        # Fallback to template default render text
        if not props.get("demo"):
            raise ValueError(f"{template}: no text props to render (pass main_text, or demo=true / --demo for self-test text)")
        fallback_defaults = {
            "kt01_kiss_editorial_2line": "chạm đúng nhịp thở",
            "kt02_feather_swash_overlap": "chuyển động mượt Chuẩn Điện Ảnh",
            "kt04_ghost_to_focus_stack": "chiều sâu quang học",
            "kt05_wall_spatial_counterpoint": "ánh sáng phẳng — tách khối thật",
            "kt07_telescoping_char_rollout": "độ nét điện ảnh",
            "kt08_mist_evaporation_reveal": "vùng sáng dịu Tan Nhẹ Như Sương",
            "kt09_strike_myth_laser_2phase": "nhìn giả trân",
            "kt10_cursor_bars_pillar_gate": "3 bước khóa ảnh",
            "kt11_cranial_svg_arc_or_tilt": "vòng sáng điện ảnh tự nhiên",
            "kt12_whisper_or_directional_echo": "nhưng điều ít ai để ý là...",
        }
        return fallback_defaults.get(template, template)
    return " ".join(parts)


def _extract_syllable_triggers(template: str, props: dict[str, Any]) -> list[dict[str, Any]]:
    default_acc = nfc(props.get("jewel_accent") or props.get("accent") or "gold")
    if template == "kt03_per_word_nonlinear_bloom":
        return [
            {"token": x["word"], "at_s": round(float(x["at_s"]), 4)}
            for x in _normalize_kt03_word_triggers(props, default_acc)
        ]
    if template == "kt06_bridge_anchor_live_swap":
        anchor = _prop_or_demo(template, props, ("anchor_text", "kicker"), "giữ trọn", required=False)
        triggers = [{"token": anchor, "at_s": round(float(props.get("anchor_at_s", 0.02)), 4)}] if anchor else []
        for s in _normalize_kt06_swaps(props, default_acc):
            triggers.append({"token": s["text"], "at_s": round(float(s["at_s"]), 4)})
        return triggers

    triggers: list[dict[str, Any]] = []
    if nfc(props.get("kicker") or props.get("setup_text") or props.get("left_text") or "").strip():
        lbl = nfc(props.get("kicker") or props.get("setup_text") or props.get("left_text")).strip()
        triggers.append({"token": lbl, "at_s": round(float(props.get("kicker_at_s", 0.02)), 4)})

    main_lbl = nfc(props.get("right_text") or props.get("main_text") or "hero").strip()
    main_at = float(props.get("turn_at_s", props.get("main_at_s", 0.06 if triggers else 0.03)))
    triggers.append({"token": main_lbl, "at_s": round(main_at, 4)})

    if template == "kt09_strike_myth_laser_2phase":
        triggers.append({"token": "laser_slash", "at_s": round(float(props.get("slash_at_s", main_at + 0.24)), 4)})
    if template == "kt12_whisper_or_directional_echo" and nfc(props.get("mode", "whisper")).lower() in ("directional_echo", "echo"):
        triggers.append({"token": "ghost_echo", "at_s": round(float(props.get("echo_at_s", main_at + 0.12)), 4)})
    if nfc(props.get("accent_text") or props.get("line2_text") or "").strip():
        acc_lbl = nfc(props.get("accent_text") or props.get("line2_text")).strip()
        triggers.append({"token": acc_lbl, "at_s": round(float(props.get("accent_at_s", main_at + 0.22)), 4)})
    return triggers


def render_kinetic_typo_batch(
    jobs: Sequence[dict[str, Any]],
    *,
    concurrency: int | None = None,
    fps: int = 60,
    alpha_codec: str = "prores4444",
    device_scale_factor: float = 1.0,
    strip_meta: bool = True,
    quiet: bool = False,
    workspace_context: Any = None,
    work_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    High-throughput `v7.1` parallel kinetic typography `.mov` renderer (`@60fps`).
    Renders `kt01..kt12` jobs in parallel across up to 4 Chrome Headless CDP tabs (v7.9.1: capped by `resolve_chrome_workers`),
    writes `<out_path>.typo_meta.json` sidecars, and returns full metadata/clip dicts (a job the engine failed: `ok: False`, `error`).
    """
    if not jobs:
        return []

    batch_specs: list[dict[str, Any]] = []
    meta_records: list[tuple[Path, dict[str, Any]]] = []

    for job in jobs:
        tpl = nfc(job["template"]).strip()
        if tpl not in TEMPLATE_DEFAULTS:
            raise ValueError(
                f"Unknown kinetic typography template '{tpl}'. Available: {', '.join(KINETIC_TYPO_TEMPLATES.keys())}"
            )
        props = normalize_props_nfc(job.get("props") or {})
        dropped = kt_dropped_text(tpl, props)  # v7.9.3: fail before Chrome instead of shipping a plate without its accent
        if any(d["field"] == "accent_text" for d in dropped) and not (job.get("allow_drop_accent") or props.get("allow_drop_accent")):
            raise ValueError(
                f"[v7.9.3 DROPPED_ACCENT_TEXT] '{tpl}' would not draw accent_text "
                f"{[d['text'] for d in dropped if d['field'] == 'accent_text']} ({job.get('out')}); pick a template that draws it "
                "or set allow_drop_accent: true on the job"
            )
        kt_spec = KINETIC_TYPO_TEMPLATES.get(
            tpl,
            {
                "layout_silhouette": "SIL_FEATHER_SWASH",
                "default_entrance_style": "player3_kiss_rise",
                "width": TEMPLATE_DEFAULTS[tpl]["width"],
                "height": TEMPLATE_DEFAULTS[tpl]["height"],
            },
        )
        out_path = Path(job["out"]).expanduser().resolve()
        if out_path.suffix.lower() != ".mov":
            raise ValueError(
                f"[v7.1 KINETIC_MOV_ONLY] Expected `.mov` output path for '{tpl}', got '{out_path}'."
            )

        job_fps = int(round(float(job.get("fps", fps or 60))))
        job_dur = job.get("duration_sec", job.get("duration", 1.8))
        job_frames = job.get("total_frames", job.get("frames"))
        if job_frames is None:
            job_frames = max(1, round(float(job_dur) * job_fps))

        w = int(job.get("width") or props.get("width") or kt_spec["width"])
        explicit_h = job.get("height") or props.get("height")  # None = default height, grown to the content by the batch
        h = int(explicit_h or default_plate_height(tpl, props))
        job_codec = nfc(job.get("alpha_codec") or job.get("alphaCodec") or alpha_codec)
        job_scale = float(job.get("device_scale_factor", job.get("scale", device_scale_factor)))

        batch_specs.append(
            {
                "template": tpl,
                "props": props,
                "out": str(out_path),
                "mode": "mov",
                "width": w,
                "height": int(explicit_h) if explicit_h else None,
                "fps": job_fps,
                "total_frames": int(job_frames),
                "device_scale_factor": job_scale,
                "alpha_codec": job_codec,
            }
        )

        theme_mode = "light" if nfc(props.get("theme", "dark")).strip().lower() == "light" else "dark"
        is_whisper_clean = (
            tpl == "kt12_whisper_or_directional_echo"
            and nfc(props.get("mode", "whisper")).lower() == "whisper"
            and not (props.get("jewel_accent") or props.get("accent"))
        )
        accent_hex = (
            ("#14171F" if theme_mode == "light" else "#FAFAFA")
            if is_whisper_clean
            else resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)["hex"]
        )
        is_svg_arc = (
            tpl == "kt11_cranial_svg_arc_or_tilt"
            and nfc(props.get("mode", "svg_arc")).lower() == "svg_arc"
        )
        default_rail = "cranial_halo_rail" if is_svg_arc else "lower_chest_rail"
        default_z = "midground_behind_subject" if is_svg_arc else "foreground_over_subject"

        typo_meta = {
            "engine": "web_cinema_plate_engine_v7.1",
            "mode": "mov",
            "theme": theme_mode,
            "out": str(out_path),
            "fps": job_fps,
            "frames": int(job_frames),
            "duration_sec": round(int(job_frames) / max(1, job_fps), 4),
            "width": w,
            "height": h,
            "template": tpl,
            "layout_silhouette": nfc(
                job.get("layout_silhouette") or props.get("layout_silhouette") or kt_spec["layout_silhouette"]
            ),
            "entrance_style": nfc(
                job.get("entrance_style") or props.get("entrance_style") or kt_spec["default_entrance_style"]
            ),
            "has_pill_badge": bool(nfc(props.get("badge_text") or props.get("pill_text") or "").strip()),
            "has_kicker": bool(nfc(props.get("kicker") or "").strip()),
            "plain_hero_text": _extract_plain_hero_text(tpl, props),
            "accent_hue_hex": accent_hex,
            "placement_rail": nfc(job.get("placement_rail") or props.get("placement_rail") or default_rail),
            "z_plane": nfc(job.get("z_plane") or props.get("z_plane") or default_z),
            "syllable_triggers": props.get("syllable_triggers") or _extract_syllable_triggers(tpl, props),
            "dropped_text": dropped,
        }
        if job.get("base_frame") and job.get("ink_bbox_screen"):  # v7.9.3: measured contrast for check_text_legibility
            typo_meta["contrast"] = text_contrast_ratio(job["base_frame"], job["ink_bbox_screen"],
                                                        "#14171F" if theme_mode == "light" else "#FAFAFA")
        meta_records.append((out_path, typo_meta))

    engine_results = render_web_plates_batch(
        batch_specs,
        concurrency=concurrency,
        alpha_codec=alpha_codec,
        strip_meta=strip_meta,
        quiet=quiet,
        workspace_context=workspace_context,
        work_dir=work_dir,
    )

    final_items: list[dict[str, Any]] = []
    for (out_path, typo_meta), eng_res in zip(meta_records, engine_results):
        meta_path = Path(f"{out_path}.typo_meta.json")
        combined = {
            **typo_meta,
            "height": int(eng_res.get("plate_height") or typo_meta["height"]),
            "codec": eng_res.get("codec", "prores_ks_4444_yuva444p10le"),
            "bytes": eng_res.get("bytes", 0),
            "elapsedMs": eng_res.get("elapsedMs", 0),
            "meta_path": str(meta_path),
            "ok": eng_res.get("ok", True) is not False,
        }
        if eng_res.get("ok") is False:
            combined["error"] = str(eng_res.get("error", ""))
        meta_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
        final_items.append(combined)

    return final_items


def render_kinetic_typo_mov(
    template: str,
    props: dict[str, Any] | None,
    out_path: str | Path,
    *,
    width: int | None = None,
    height: int | None = None,
    fps: int = 60,
    duration_sec: float = 1.8,
    total_frames: int | None = None,
    device_scale_factor: float = 1.0,
    alpha_codec: str = "prores4444",
    placement_rail: str | None = None,
    z_plane: str | None = None,
    entrance_style: str | None = None,
    strip_meta: bool = True,
    quiet: bool = False,
) -> dict[str, Any]:
    """Renders a single `60fps` kinetic typography `.mov` clip and writes `<out_path>.typo_meta.json`."""
    job: dict[str, Any] = {
        "template": template,
        "props": props or {},
        "out": str(out_path),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
        "total_frames": total_frames,
        "device_scale_factor": device_scale_factor,
        "alpha_codec": alpha_codec,
    }
    if placement_rail is not None:
        job["placement_rail"] = placement_rail
    if z_plane is not None:
        job["z_plane"] = z_plane
    if entrance_style is not None:
        job["entrance_style"] = entrance_style

    return render_kinetic_typo_batch(
        [job],
        concurrency=1,
        fps=fps,
        alpha_codec=alpha_codec,
        device_scale_factor=device_scale_factor,
        strip_meta=strip_meta,
        quiet=quiet,
    )[0]


def render_dviet_typo_cluster_png(
    main_text: str,
    accent_text: str,
    out_path: str | Path,
    *,
    kicker: str = "",
    jewel_accent: str = "gold",
    accent_font: str = "playfair",
    swash_dropcap: bool = True,
    badge_text: str = "",
    width: int = 1080,
    height: int = 760,
    strip_meta: bool = True,
    allow_static_thumbnail: bool = False,
    **extra_props: Any,
) -> Path:
    """
    High-level helper for Video #10/#08/#14 @__dviet Feather=29 + Swash + Glow 2 PNG plate.
    Guarded in `v7.1`: only permitted when `allow_static_thumbnail=True` (for cover thumbnails).
    Timeline hero typography MUST use `render_kinetic_typo_mov` / `render_kinetic_typo_batch` (@60fps .mov).
    """
    if not allow_static_thumbnail:
        raise ValueError(
            "[v7.1 STATIC_HERO_PNG_STAMP VETO] Use render_kinetic_typo_mov / render_kinetic_typo_batch (@60fps .mov) instead of static PNG stamps."
        )
    props = {
        "kicker": kicker,
        "main_text": main_text,
        "accent_text": accent_text,
        "jewel_accent": jewel_accent,
        "accent_font": accent_font,
        "swash_dropcap": swash_dropcap,
        "badge_text": badge_text,
        **extra_props,
    }
    out = Path(out_path).expanduser().resolve()
    render_web_plate(
        "dviet_overlapping_feather_cluster",
        props,
        out,
        mode="still",
        width=width,
        height=height,
        strip_meta=strip_meta,
    )
    return out


def render_studio_card_mov(
    template: str,
    props: dict[str, Any] | None,
    out_path: str | Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 60,
    duration_sec: float = 2.0,
    total_frames: int | None = None,
    alpha_codec: str = "prores4444",
    strip_meta: bool = True,
) -> Path:
    """High-level helper rendering an animated transparent ProRes 4444 / qtrle `.mov` studio card."""
    out = Path(out_path).expanduser().resolve()
    render_web_plate(
        template,
        props or {},
        out,
        mode="mov",
        width=width,
        height=height,
        fps=fps,
        duration_sec=duration_sec,
        total_frames=total_frames,
        alpha_codec=alpha_codec,
        strip_meta=strip_meta,
    )
    return out


# ---------------------------------------------------------------------------
# Comprehensive `v7.1` `--self-test` Suite
# ---------------------------------------------------------------------------

def _verify_png_rgba(png_path: Path) -> dict[str, Any]:
    """Verifies PNG header/mode is RGBA and contains both transparent background & crisp opaque pixels."""
    raw = png_path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{png_path} is not a valid PNG")
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    color_type = raw[25]
    if color_type != 6:
        raise AssertionError(f"{png_path} PNG color_type={color_type}, expected 6 (RGBA)")

    info: dict[str, Any] = {"width": w, "height": h, "color_type": "RGBA", "bytes": len(raw)}
    try:
        from PIL import Image
        with Image.open(png_path) as im:
            alpha = im.getchannel("A")
            amin, amax = alpha.getextrema()
            if amin > 5 or amax < 200:
                raise AssertionError(
                    f"{png_path} failed RGBA transparency check: alpha extrema=({amin}, {amax})"
                )
            info["alpha_extrema"] = [amin, amax]
    except ImportError:
        pass
    return info


def _verify_prores4444_mov(mov_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,profile,pix_fmt,width,height,nb_frames,r_frame_rate",
            "-of",
            "json",
            str(mov_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=120,
    )
    streams = json.loads(proc.stdout).get("streams", [])
    if not streams:
        raise AssertionError(f"No video stream in {mov_path}")
    st = streams[0]
    if st.get("pix_fmt") not in ("yuva444p10le", "yuva444p12le", "argb"):
        raise AssertionError(
            f"Expected alpha pix_fmt yuva444p10le/12le/argb, got {st.get('pix_fmt')}"
        )
    return st


def run_self_test(out_dir: Path, concurrency: int | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Verify v7.1 STATIC_HERO_PNG_STAMP VETO guard + thumbnail opt-in
    veto_triggered = False
    try:
        render_dviet_typo_cluster_png(
            "CHUYỂN ĐỘNG",
            "Chuẩn Điện Ảnh",
            out_dir / "should_not_exist.png",
        )
    except ValueError as exc:
        if "STATIC_HERO_PNG_STAMP VETO" in str(exc):
            veto_triggered = True
        else:
            raise
    if not veto_triggered:
        raise AssertionError("render_dviet_typo_cluster_png failed to enforce STATIC_HERO_PNG_STAMP VETO!")

    thumb_png = render_dviet_typo_cluster_png(
        "ĐỘ SÂU ĐIỆN ẢNH",
        "Chạm Cảm Xúc Thật",
        out_dir / "00_thumbnail_dviet_cluster.png",
        badge_text="134/134 NFC: Ộ Ệ Ữ Ắ Ẳ",
        jewel_accent="gold",
        allow_static_thumbnail=True,
    )
    verified_pngs: dict[str, Any] = {thumb_png.name: _verify_png_rgba(thumb_png)}
    verified_movs: dict[str, Any] = {}

    # 2. Verify all 8 Studio Templates (including upgraded Polaroid bottom_note, Bento triggers, Isometric browser)
    batch_jobs: list[dict[str, Any]] = [
        {
            "template": "dviet_overlapping_feather_cluster",
            "out": str(out_dir / "01_dviet_overlapping_feather_cluster.png"),
            "mode": "still",
            "props": dict(FEATHER_CLUSTER_SELFTEST_PROPS),
        },
        {
            "template": "frosted_glass_bento_steps",
            "out": str(out_dir / "02_frosted_glass_bento_steps.png"),
            "mode": "still",
            "props": {
                "demo": True,
                "jewel_accent": "emerald",
                "card_triggers_s": [0.04, 0.30, 0.54],
                "bottom_note": "Chuẩn hóa ánh sáng & độ nét tự nhiên",
                "bottom_note_at_s": 1.15,
            },
        },
        {
            "template": "clinical_before_after_1_to_28",
            "out": str(out_dir / "03_clinical_before_after_1_to_28.png"),
            "mode": "still",
            "props": {"jewel_accent": "ice_cyan"},
        },
        {
            "template": "course_3d_matte_asset_box",
            "out": str(out_dir / "04_course_3d_matte_asset_box.png"),
            "mode": "still",
            "props": {"jewel_accent": "gold", "gobo_shadow": True},
        },
        {
            "template": "tactile_review_glass_scorecard",
            "out": str(out_dir / "05_tactile_review_glass_scorecard.png"),
            "mode": "still",
            "props": {"jewel_accent": "gold", "score": 9.4},
        },
        {
            "template": "isometric_3d_prompt_browser",
            "out": str(out_dir / "06_isometric_3d_prompt_browser.png"),
            "mode": "still",
            "props": {"jewel_accent": "emerald", "type_start_s": 0.08, "type_end_s": 1.6},
        },
        {
            "template": "skewed_3d_polaroid_trio",
            "out": str(out_dir / "07_skewed_3d_polaroid_trio.png"),
            "mode": "still",
            "props": {
                "demo": True,
                "jewel_accent": "gold",
                "card_triggers_s": [0.04, 0.30, 0.54],
                "bottom_note": "Giữ trọn kết cấu ánh sáng thật",
                "bottom_note_at_s": 1.35,
            },
        },
        {
            "template": "doctor_authority_lower_third",
            "out": str(out_dir / "08_doctor_authority_lower_third.png"),
            "mode": "still",
            "width": 1080,
            "height": 600,
            "props": {"jewel_accent": "ice_cyan"},
        },
        {
            "template": "frosted_glass_bento_steps",
            "out": str(out_dir / "09_frosted_glass_bento_steps_alpha.mov"),
            "mode": "mov",
            "width": 1080,
            "height": 1920,
            "fps": 60,
            "total_frames": 24,
            "props": {"demo": True, "jewel_accent": "emerald"},
        },
    ]

    render_results = render_web_plates_batch(batch_jobs, concurrency=concurrency, strip_meta=True)
    for res in render_results:
        p = Path(res["out"])
        if p.suffix.lower() == ".png":
            verified_pngs[p.name] = _verify_png_rgba(p)
        elif p.suffix.lower() == ".mov":
            verified_movs[p.name] = _verify_prores4444_mov(p)

    # 3. Verify ALL 12 v7.1 Kinetic Typography Templates (`kt01..kt12`) via `render_kinetic_typo_batch` @60fps concurrency=4
    kt_samples: list[tuple[str, dict[str, Any]]] = [
        ("kt01_kiss_editorial_2line", {"helper_text": "nhịp dựng mượt", "main_text": "chạm đúng cảm xúc", "jewel_accent": "gold"}),
        ("kt02_feather_swash_overlap", {"main_text": "độ sâu ánh sáng", "accent_text": "Chuẩn Điện Ảnh", "jewel_accent": "gold"}),
        ("kt03_per_word_nonlinear_bloom", {
            "word_triggers": [
                {"word": "cứ", "at_s": 0.02, "hue": "white"},
                {"word": "Camera", "at_s": 0.24, "hue": "gold", "italic": True, "scale": 1.08},
                {"word": "bật", "at_s": 0.12, "hue": "white"},
            ]
        }),
        ("kt04_ghost_to_focus_stack", {"setup_text": "tưởng chỉ cần nét căng", "main_text": "chiều sâu quang học", "jewel_accent": "ice_cyan"}),
        ("kt05_wall_spatial_counterpoint", {"mode": "left_right_counter", "left_text": "ánh sáng phẳng", "right_text": "tách khối thật", "jewel_accent": "crimson", "turn_at_s": 0.20}),
        ("kt06_bridge_anchor_live_swap", {
            "anchor_text": "giữ trọn",
            "swap_words": [
                {"text": "màu da thật", "at_s": 0.04, "hue": "gold"},
                {"text": "ánh mắt sống", "at_s": 0.28, "hue": "emerald", "italic": True},
            ],
        }),
        ("kt07_telescoping_char_rollout", {"main_text": "chữ việt ộ ệ ữ ắ ẳ", "accent_text": "Từng Ký Tự Mượt", "jewel_accent": "gold"}),
        ("kt08_mist_evaporation_reveal", {"main_text": "vùng sáng dịu", "accent_text": "Tan Nhẹ Như Sương", "keep_mist_tail": True, "jewel_accent": "ice_cyan"}),
        ("kt09_strike_myth_laser_2phase", {"main_text": "nhìn giả trân", "accent_text": "giữ chi tiết da thật", "jewel_accent": "emerald", "slash_at_s": 0.20}),
        ("kt10_cursor_bars_pillar_gate", {"main_text": "3 bước khóa ảnh", "jewel_accent": "emerald"}),
        ("kt11_cranial_svg_arc_or_tilt", {"mode": "svg_arc", "main_text": "vòng sáng điện ảnh tự nhiên", "jewel_accent": "gold"}),
        ("kt12_whisper_or_directional_echo", {"mode": "directional_echo", "main_text": "lặp lại", "accent_text": "đúng cấu trúc nhịp", "jewel_accent": "crimson", "echo_at_s": 0.12}),
    ]

    kt_jobs = [
        {
            "template": tpl,
            "out": str(out_dir / f"kt_{idx + 1:02d}_{tpl}.mov"),
            "fps": 60,
            "total_frames": 36,
            "props": props,
        }
        for idx, (tpl, props) in enumerate(kt_samples)
    ]

    kt_results = render_kinetic_typo_batch(kt_jobs, concurrency=concurrency, fps=60, strip_meta=True)
    verified_kt_meta: dict[str, Any] = {}
    required_meta_keys = {
        "engine",
        "mode",
        "fps",
        "template",
        "layout_silhouette",
        "entrance_style",
        "has_pill_badge",
        "has_kicker",
        "plain_hero_text",
        "accent_hue_hex",
        "placement_rail",
        "z_plane",
        "syllable_triggers",
    }

    for item in kt_results:
        mov_p = Path(item["out"])
        meta_p = Path(item["meta_path"])
        if not meta_p.is_file():
            raise AssertionError(f"Missing sidecar metadata file: {meta_p}")
        loaded_meta = json.loads(meta_p.read_text(encoding="utf-8"))
        missing = required_meta_keys - set(loaded_meta.keys())
        if missing:
            raise AssertionError(f"{meta_p} missing required keys: {missing}")
        if loaded_meta["fps"] != 60 or loaded_meta["mode"] != "mov":
            raise AssertionError(f"Expected 60fps mov in {meta_p}, got {loaded_meta}")
        if loaded_meta["has_pill_badge"] is not False or loaded_meta["has_kicker"] is not False:
            raise AssertionError(f"Unexpected default pill/kicker on {meta_p}: {loaded_meta}")
        st_info = _verify_prores4444_mov(mov_p)
        verified_movs[mov_p.name] = st_info
        verified_kt_meta[mov_p.name] = {
            "layout_silhouette": loaded_meta["layout_silhouette"],
            "entrance_style": loaded_meta["entrance_style"],
            "plain_hero_text": loaded_meta["plain_hero_text"],
            "fps": loaded_meta["fps"],
        }

    # 4. v7.4.0 layout templates: screen_strip, card_916, profile_card (one PNG each)
    layout_report = render_layout_templates_self_test(out_dir)

    report = {
        "ok": True,
        "version": "7.4.0",
        "layout_templates_tested": sorted(layout_report["pngs"]),
        "layout_pngs": layout_report["pngs"],
        "static_png_veto_verified": True,
        "out_dir": str(out_dir),
        "png_count": len(verified_pngs),
        "mov_count": len(verified_movs),
        "kinetic_templates_tested": len(verified_kt_meta),
        "verified_pngs": verified_pngs,
        "verified_kinetic_typo": verified_kt_meta,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def _load_props_arg(raw_props: str | None) -> dict[str, Any]:
    if not raw_props:
        return {}
    s = raw_props.strip()
    if s.startswith("{"):
        return json.loads(s)
    cand = Path(s).expanduser()
    if cand.is_file():
        return json.loads(cand.read_text(encoding="utf-8"))
    return json.loads(s)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Universal Studio Director v7.9.1 — Web-Cinema Studio RGBA Plate & 60fps Kinetic Typography Builder"
    )
    parser.add_argument("--list", action="store_true",
                        help=f"List all {len(TEMPLATE_DEFAULTS)} built-in Studio & Kinetic Typography templates "
                             f"({len(TEMPLATE_DEFAULTS) - len(KINETIC_TYPO_TEMPLATES)} studio + {len(KINETIC_TYPO_TEMPLATES)} kinetic)")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify static PNG veto, the Studio templates, and all 12 60fps Kinetic Typography templates",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Target directory for --self-test (default: a new temp dir, printed at the end)",
    )
    parser.add_argument("--template", "-t", help="Template name (Studio card or kt01..kt12)")
    parser.add_argument("--props-json", "-p", help="JSON string or path to JSON props file")
    parser.add_argument("--out", "-o", help="Output .png or .mov file path")
    parser.add_argument("--mode", default="auto", choices=["auto", "still", "mov", "sequence"])
    parser.add_argument("--width", "-w", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None, help="FPS (defaults to 60 for kt01..kt12, 30/60 for studio plates)")
    parser.add_argument("--duration", type=float, default=1.8)
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--frame-idx", type=int, default=None)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--alpha-codec", default="prores4444", choices=["prores4444", "qtrle"])
    parser.add_argument("--concurrency", "-c", type=int, default=None,
                        help="Chrome tabs for --self-test (default: 4, capped by env PFD_CHROME_WORKERS)")
    parser.add_argument("--no-strip", action="store_true", help="Skip strip_metadata pass")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Self-test only: fill MISSING text props with built-in demo copy (otherwise a missing required prop raises ValueError)",
    )

    args = parser.parse_args(argv)

    if args.list:
        print(
            json.dumps(
                {
                    "templates": TEMPLATE_DEFAULTS,
                    "kinetic_typo_templates": KINETIC_TYPO_TEMPLATES,
                    "palettes": list(JEWEL_PALETTES.keys()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.self_test:
        out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="pfd_web_plates_selftest_"))
        run_self_test(out_dir, concurrency=args.concurrency)
        print(f"self-test output: {out_dir}")
        return 0

    if not args.template or not args.out:
        parser.error("Provide --template and --out (or use --list / --self-test).")

    props = _load_props_arg(args.props_json)
    if args.demo:
        props = {**props, "demo": True}
    tpl_key = nfc(args.template).strip()
    out_ext = Path(args.out).suffix.lower()

    if tpl_key in KINETIC_TYPO_TEMPLATES and out_ext == ".mov" and args.mode in ("auto", "mov"):
        res = render_kinetic_typo_mov(
            template=tpl_key,
            props=props,
            out_path=args.out,
            width=args.width,
            height=args.height,
            fps=args.fps or 60,
            duration_sec=args.duration,
            total_frames=args.frames,
            device_scale_factor=args.scale,
            alpha_codec=args.alpha_codec,
            strip_meta=not args.no_strip,
        )
    else:
        res = render_web_plate(
            template=tpl_key,
            props=props,
            out_path=args.out,
            mode=args.mode,
            width=args.width,
            height=args.height,
            fps=args.fps,
            duration_sec=args.duration,
            total_frames=args.frames,
            frame_idx=args.frame_idx,
            device_scale_factor=args.scale,
            alpha_codec=args.alpha_codec,
            strip_meta=not args.no_strip,
        )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
