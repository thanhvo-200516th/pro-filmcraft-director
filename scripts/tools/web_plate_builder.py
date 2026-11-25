#!/usr/bin/env python3
"""
Universal Studio Director v7.1 — Web-Cinema Studio Plate & Kinetic Typography Builder (`web_plate_builder.py`)
==============================================================================================================
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
  - `render_kinetic_typo_batch(jobs, concurrency=4, ...)`
  - `render_web_plate(template, props, out_path, ...)`
  - `render_web_plates_batch(jobs, concurrency=4, ...)`
  - `render_studio_card_mov(template, props, out_path, ...)`
  - `render_dviet_typo_cluster_png(..., allow_static_thumbnail=False)`
  - `build_template_html(template, props, width=..., height=...)`
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
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

FONT_ROOT_TNEDIT = Path.home() / ".local/share/fonts/tnedit"
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


def strip_media_metadata_if_available(file_path: Path) -> None:
    """Runs local lossless strip_metadata.py if available so deliverables remain clean."""
    for script in STRIP_METADATA_Candidates:
        if script.is_file():
            subprocess.run(
                [sys.executable, str(script), "--keep-icc", str(file_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return


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

def _font_uri(path: Path) -> str:
    return path.as_uri() if path.is_file() else ""


def build_font_face_css() -> str:
    """
    Maps verified local `.ttf`/`.otf` font files directly via `file://` URIs so Chrome
    never falls back to wrong fontconfig aliases (such as SVN-Helvetica masquerading as Be Vietnam Pro).
    """
    rules: list[str] = []

    def add_face(family: str, file_path: Path, weight: str = "400", style: str = "normal") -> None:
        if not file_path.is_file():
            return
        ext = file_path.suffix.lower()
        fmt = "opentype" if ext == ".otf" else "truetype"
        uri = file_path.as_uri()
        rules.append(
            f"@font-face {{ font-family: '{family}'; src: url('{uri}') format('{fmt}'); "
            f"font-weight: {weight}; font-style: {style}; font-display: block; }}"
        )

    # Be Vietnam Pro (Full clean Vietnamese diacritic geometry)
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-ExtraLight.ttf", "200", "normal")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-Light.ttf", "300 400", "normal")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-Italic.ttf", "400", "italic")
    add_face("Be Vietnam Pro", FONT_ROOT_BASE / "Inter-Medium.ttf", "500", "normal")
    # Also register dedicated Be Vietnam Pro Bold/ExtraBold/Black
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-Bold.ttf", "600 700", "normal")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-BoldItalic.ttf", "600 700", "italic")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-ExtraBold.ttf", "800", "normal")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-ExtraBoldItalic.ttf", "800", "italic")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-Black.ttf", "900", "normal")
    add_face("Be Vietnam Pro", FONT_ROOT_TNEDIT / "BeVietnamPro-BlackItalic.ttf", "900", "italic")

    # Playfair Display (Editorial Luxury Serif & Swash Italic)
    add_face("Playfair Display", FONT_ROOT_TNEDIT / "PlayfairDisplay[wght].ttf", "400 900", "normal")
    add_face("Playfair Display", FONT_ROOT_TNEDIT / "PlayfairDisplay-Italic[wght].ttf", "400 900", "italic")
    add_face("Playfair Display", FONT_ROOT_BASE / "PlayfairDisplay-BoldItalic.ttf", "700", "italic")

    # SVN-Aaron Script (Signature Vietnamese Calligraphy)
    add_face("SVN-Aaron Script", FONT_ROOT_TNEDIT / "SVN-Aaron Script.otf", "400 700", "normal")
    add_face("SVN-Aaron Script", FONT_ROOT_TNEDIT / "SVN-Aaron Script.otf", "400 700", "italic")

    # DFVN West West (Condensed Editorial Display)
    add_face("DFVN West West", FONT_ROOT_TNEDIT / "DFVN West West Condensed.ttf", "400 800", "normal")

    # Inter & Montserrat
    add_face("Inter", FONT_ROOT_TNEDIT / "Inter[opsz,wght].ttf", "100 900", "normal")
    add_face("Inter", FONT_ROOT_TNEDIT / "Inter-Italic[opsz,wght].ttf", "100 900", "italic")
    add_face("Montserrat", FONT_ROOT_MONT / "Montserrat-Medium.ttf", "400 500", "normal")
    add_face("Montserrat", FONT_ROOT_MONT / "Montserrat-ExtraBold.ttf", "700 800", "normal")
    add_face("Montserrat", FONT_ROOT_MONT / "Montserrat-Black.otf", "900", "normal")

    # Studio Monospace
    add_face("Studio Mono", FONT_ROOT_MONO / "LigaSFMonoNerdFont-Bold.otf", "600 700", "normal")
    add_face("Studio Mono", FONT_ROOT_MONO / "LigaSFMonoNerdFont-LightItalic.otf", "400", "italic")

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

// Glow-2 optical halation envelope: 4f attack -> 1.45x peak, 28f decay -> 0.85x steady
function halationPulse(u) {
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

function applyOptionalPillEntrance(tSec, badgeAtSec, durSec = 0.22) {
  const pill = document.getElementById("ktOptPill");
  if (!pill) return;
  const pP = timeProgress(tSec, badgeAtSec, durSec, velvetC2);
  pill.style.opacity = String(pP.toFixed(4));
  pill.style.visibility = pP > 0.002 ? "visible" : "hidden";
  pill.style.transform = `translate3d(0, ${((1 - pP) * 14).toFixed(2)}px, 0)`;
}
"""


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
{COMMON_STUDIO_JS}
{frame_js}
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
    kicker_size = int(props.get("kicker_size") or max(21, round(main_size / 3.2)))
    acc_len = max(1, len(accent_text))
    auto_acc = min(round(main_size * 0.88), int((width * 0.86) / max(7.0, acc_len * 0.48)))
    accent_size = int(props.get("accent_size") or max(56, auto_acc))
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
      gap: 12px;
      font-family: 'Be Vietnam Pro', 'Inter', sans-serif;
      font-weight: 500;
      font-size: {kicker_size}px;
      line-height: 1.25;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: #FAFAFA;
      padding: 0.32em 0.25em;
      margin-bottom: calc(-0.32em - 0.26em + 5px); /* Tight parasitic gap = 5px (< 8px) */
      text-shadow: 0 4px 18px rgba(0, 0, 0, 0.42);
      will-change: transform, opacity;
    }}

    .kicker-bar {{
      width: 24px;
      height: 3px;
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
      margin-top: -6px;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 11px 24px;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.78);
      backdrop-filter: blur(20px) saturate(160%);
      -webkit-backdrop-filter: blur(20px) saturate(160%);
      border: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.36),
        0 16px 38px rgba(0, 0, 0, 0.50),
        0 0 24px {pal["glow_ambient"]};
    }}

    .pill-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: {pal["hex"]};
      box-shadow: 0 0 12px {pal["hex"]};
    }}

    .pill-text {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: {max(18, round(kicker_size * 0.72))}px;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      color: #F8FAFC;
      padding: 0.12em 0.08em;
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

def _build_frosted_glass_bento_steps(props: dict[str, Any], width: int, height: int) -> str:
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald")
    theme = nfc(props.get("theme", "dark")).lower()
    is_light = theme == "light"

    kicker = nfc(props.get("kicker", "LỘ TRÌNH CHUẨN STUDIO • 3 BƯỚC"))
    title = nfc(props.get("title", "Quy Trình Chuyển Đổi Thực Chiến"))
    bottom_note = nfc(props.get("bottom_note", ""))
    bottom_note_at_s = float(props.get("bottom_note_at_s", 1.25))
    raw_triggers = props.get("card_triggers_s") or [0.04, 0.30, 0.54]
    card_triggers_s = [float(raw_triggers[i]) if i < len(raw_triggers) else 0.04 + i * 0.26 for i in range(3)]
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    raw_steps = props.get("steps") or [
        {
            "num": "01",
            "title": "Chẩn Đoán & Khóa Tỷ Lệ Gốc",
            "desc": "Phân tích cấu trúc ánh sáng, sắc độ da và bố cục khung hình chuẩn điện ảnh.",
            "tag": "NỀN TẢNG",
        },
        {
            "num": "02",
            "title": "Tinh Chỉnh Đa Lớp Chuyên Sâu",
            "desc": "Xử lý tách nền RGBA, cân bằng tương phản và giữ trọn độ nét tự nhiên.",
            "tag": "CỐT LÕI",
        },
        {
            "num": "03",
            "title": "Kiểm Định & Xuất Bản 4K Master",
            "desc": "Khóa chuẩn âm lượng -14 LUFS, màu sắc đồng nhất trên mọi thiết bị di động.",
            "tag": "HOÀN THIỆN",
        },
    ]

    steps = list(raw_steps)[:3]
    while len(steps) < 3:
        idx = len(steps) + 1
        steps.append({"num": f"0{idx}", "title": f"Bước 0{idx}", "desc": "Chi tiết tiêu chuẩn", "tag": "CHUẨN"})

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
          <div class="step-left-col">
            <div class="step-num-ring" id="stepRing{idx}">
              <span class="step-num" id="stepNum{idx}">{num}</span>
            </div>
          </div>
          <div class="step-body-col">
            <div class="step-meta-row">
              <span class="step-tag-pill" id="stepTag{idx}">
                <span class="step-icon">{svg_icons[idx % 3]}</span>
                {st_tag}
              </span>
              <span class="step-status-dot" id="stepDot{idx}"></span>
            </div>
            <div class="step-title">{st_title}</div>
            <div class="step-desc">{st_desc}</div>
          </div>
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
      width: {min(width - 84, 948)}px;
      padding: 44px 42px 46px;
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
      gap: 10px;
      margin-bottom: 28px;
    }}

    .header-top-rail {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}

    .bento-kicker {{
      font-size: 20px;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: {pal["hex"]};
      padding: 0.20em 0.10em;
    }}

    .rail-steps-indicator {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 18px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid {border_col};
      font-family: 'Studio Mono', monospace;
      font-size: 18px;
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
      font-size: 48px;
      line-height: 1.18;
      letter-spacing: -0.028em;
      color: {text_main};
      padding: 0.18em 0.06em;
    }}

    .bento-grid {{
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }}

    .bento-step-card {{
      position: relative;
      display: flex;
      align-items: flex-start;
      gap: 26px;
      padding: 28px 30px;
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
      width: 78px;
      height: 78px;
      border-radius: 22px;
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
      font-size: 34px;
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
      justify-content: space-between;
    }}

    .step-tag-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 5px 14px;
      border-radius: 999px;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      color: {pal["hex"]};
    }}

    .step-icon {{
      width: 16px;
      height: 16px;
      display: inline-flex;
    }}

    .step-icon svg {{
      width: 16px;
      height: 16px;
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
      font-size: 31px;
      line-height: 1.24;
      letter-spacing: -0.02em;
      color: {text_main};
      padding: 0.10em 0.04em;
    }}

    .step-desc {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 400;
      font-size: 23px;
      line-height: 1.44;
      color: {text_sub};
      padding: 0.06em 0.04em;
    }}

    .bento-bottom-note {{
      position: relative;
      z-index: 3;
      margin-top: 24px;
      text-align: center;
      font-size: 30px;
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
            <div class="rail-steps-indicator">
              <span class="rail-node" id="rail0">01</span>
              <span class="rail-sep">•</span>
              <span class="rail-node" id="rail1">02</span>
              <span class="rail-sep">•</span>
              <span class="rail-node" id="rail2">03</span>
            </div>
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
    kicker = nfc(props.get("kicker", "ĐỐI CHIẾU LÂM SÀNG • PHÁC ĐỒ CÁ NHÂN HÓA"))
    title = nfc(props.get("title", "Kết Quả Phục Hình Thẩm Mỹ"))
    before_label = nfc(props.get("before_label", "TRƯỚC • BẢN GỐC"))
    after_label = nfc(props.get("after_label", "SAU • KẾT QUẢ CHUẨN TỶ LỆ"))
    process_label = nfc(props.get("process_label", "TIẾN TRÌNH TÁI TẠO ĐỘ BÓNG & SẮC ĐỘ TỰ NHIÊN"))
    process_metric = nfc(props.get("process_metric", "CHUẨN XÁC 99.4%"))
    phases = props.get("phases") or ["QUÉT VI ĐIỂM 3D", "CÂN CHỈNH TỶ LỆ VÀNG", "HOÀN THIỆN LÂM SÀNG"]

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
      width: 964px;
      display: flex;
      flex-direction: column;
      gap: 28px;
      padding: 24px;
    }}

    .clinical-header {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-left: 8px;
    }}

    .clinical-kicker {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: {pal["hex"]};
      text-shadow: 0 2px 14px rgba(0,0,0,0.45);
      padding: 0.16em 0.08em;
    }}

    .clinical-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: 50px;
      line-height: 1.16;
      letter-spacing: -0.03em;
      color: #FAFAFA;
      text-shadow: 0 8px 28px rgba(0,0,0,0.52);
      padding: 0.16em 0.06em;
    }}

    .asymmetric-deck {{
      position: relative;
      width: 916px;
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
      top: 24px;
      right: 24px;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 11px 22px;
      border-radius: 999px;
      background: rgba(12, 16, 24, 0.80);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border: 1px solid {pal["hex"]};
      box-shadow: 0 10px 26px rgba(0,0,0,0.45), 0 0 20px {pal["glow_outer"]};
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.10em;
      color: {pal["bright"]};
    }}

    .after-badge-dot {{
      width: 10px;
      height: 10px;
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
      bottom: 20px;
      left: 20px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 18px;
      border-radius: 999px;
      background: rgba(15, 17, 22, 0.84);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(255, 255, 255, 0.28);
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.10em;
      color: #E2E8F0;
    }}

    /* Ratio Telemetry Pill */
    .ratio-stamp {{
      position: absolute;
      left: 24px;
      bottom: 34px;
      z-index: 5;
      padding: 12px 20px;
      border-radius: 18px;
      background: rgba(18, 20, 26, 0.80);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      font-family: 'Studio Mono', monospace;
      font-size: 17px;
      color: rgba(248, 250, 252, 0.85);
      box-shadow: 0 16px 36px rgba(0,0,0,0.48);
    }}

    /* Live Process Bar Dock */
    .live-process-dock {{
      position: relative;
      width: 916px;
      padding: 26px 32px;
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
      align-items: center;
      justify-content: space-between;
    }}

    .proc-label {{
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: #F8FAFC;
      padding: 0.10em 0.04em;
    }}

    .proc-metric {{
      font-family: 'Studio Mono', monospace;
      font-size: 20px;
      font-weight: 700;
      color: {pal["hex"]};
    }}

    .proc-track {{
      position: relative;
      width: 100%;
      height: 12px;
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
      align-items: center;
      justify-content: space-between;
      font-size: 16px;
      font-weight: 600;
      letter-spacing: 0.08em;
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

        <div class="ratio-stamp" id="ratioStamp">TỶ LỆ HIỂN THỊ 1 : 2.8 • STUDIO Z-DEPTH</div>
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
    vault_title = nfc(props.get("vault_title", "BỘ TÀI NGUYÊN ĐỘC QUYỀN STUDIO"))
    vault_sub = nfc(props.get("vault_sub", "TRỌN BỘ 35+ PRESET • MỞ KHÓA TỨC THÌ"))
    show_gobo = bool(props.get("gobo_shadow", True))

    cards = props.get("cards") or [
        {
            "tag": "MODULE 01",
            "title": "Masterclass Nhịp Dựng",
            "meta": "18 VIDEO 4K • THỰC CHIẾN",
            "accent": "#7DD3FC",
        },
        {
            "tag": "FONT PACK",
            "title": "Tuyển Tập Chữ Việt Hóa",
            "meta": "42 FONT NFC • CHUẨN DẤU",
            "accent": "#F5C451",
        },
        {
            "tag": "EBOOK PRO",
            "title": "Sổ Tay Ánh Sáng & Bố Cục",
            "meta": "PDF 128 TRANG • BẢN ĐỒ MÀU",
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

    css = f"""
    .vault-scene {{
      position: relative;
      width: 980px;
      height: 1120px;
      display: flex;
      align-items: center;
      justify-content: center;
      perspective: 1100px;
    }}

    .gobo-shadow-svg {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 0;
    }}

    .vault-assembly {{
      position: relative;
      width: 900px;
      height: 880px;
      z-index: 2;
    }}

    /* Matte-Black Back Folder Wall + Hinged Open Top Tab (strictly behind cards) */
    .matte-box-back {{
      position: absolute;
      left: 110px;
      bottom: 84px;
      width: 680px;
      height: 410px;
      border-radius: 34px;
      background: linear-gradient(170deg, #20242E 0%, #101218 70%, #08090C 100%);
      border: 1.5px solid rgba(255, 255, 255, 0.14);
      box-shadow: 0 38px 80px rgba(0, 0, 0, 0.72);
      z-index: 1;
      transform: perspective(1100px) rotateX(6deg);
    }}

    .matte-box-lid {{
      position: absolute;
      left: 220px;
      bottom: 472px;
      width: 460px;
      height: 76px;
      border-radius: 26px 26px 8px 8px;
      background: linear-gradient(180deg, #2B303E 0%, #171A22 100%);
      border: 1px solid rgba(255, 255, 255, 0.18);
      transform-origin: bottom center;
      z-index: 0;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.32);
    }}

    /* 3 Fanned Rounded Asset Cards */
    .asset-fan-card {{
      position: absolute;
      width: 316px;
      height: 386px;
      left: 292px;
      bottom: 248px;
      padding: 26px 24px;
      border-radius: 28px;
      background: linear-gradient(160deg, rgba(32, 36, 48, 0.98) 0%, rgba(16, 18, 26, 0.98) 100%);
      border: 1.5px solid rgba(255, 255, 255, 0.22);
      box-shadow:
        0 24px 52px rgba(0, 0, 0, 0.65),
        inset 0 1px 0 rgba(255, 255, 255, 0.38);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      will-change: transform, opacity;
    }}
    .card-slot-0 {{ z-index: 3; }}
    .card-slot-2 {{ z-index: 4; }}
    .card-slot-1 {{ z-index: 5; }}

    .asset-card-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .asset-icon {{
      width: 52px;
      height: 52px;
      border-radius: 16px;
      border: 1px solid;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .asset-icon svg {{
      width: 26px;
      height: 26px;
    }}

    .asset-tag {{
      font-family: 'Studio Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.10em;
    }}

    .asset-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: 31px;
      line-height: 1.24;
      letter-spacing: -0.02em;
      color: #FAFAFA;
      padding: 0.12em 0.04em;
    }}

    .asset-meta {{
      font-size: 16px;
      font-weight: 600;
      letter-spacing: 0.08em;
      color: rgba(226, 232, 240, 0.68);
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.10);
    }}

    /* Matte-Black Front Pocket Lip */
    .matte-box-front {{
      position: absolute;
      left: 86px;
      bottom: 64px;
      width: 728px;
      height: 288px;
      border-radius: 26px 26px 38px 38px;
      background: linear-gradient(175deg, #272C38 0%, #141720 46%, #0B0D12 100%);
      border: 1.5px solid rgba(255, 255, 255, 0.20);
      box-shadow:
        inset 0 2px 1px rgba(255, 255, 255, 0.30),
        0 -10px 28px rgba(0, 0, 0, 0.45),
        0 32px 68px rgba(0, 0, 0, 0.72);
      z-index: 8;
      transform: perspective(1100px) rotateX(8deg);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 14px;
      padding: 28px 36px;
      text-align: center;
    }}

    .clasp-jewel-pill {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 20px;
      border-radius: 999px;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      color: {pal["hex"]};
      font-family: 'Studio Mono', monospace;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.12em;
      box-shadow: 0 0 22px {pal["glow_ambient"]};
    }}

    .vault-front-title {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: 33px;
      line-height: 1.22;
      letter-spacing: -0.02em;
      color: #FAFAFA;
      padding: 0.12em 0.06em;
    }}

    .vault-front-sub {{
      font-size: 18px;
      font-weight: 600;
      letter-spacing: 0.12em;
      color: rgba(226, 232, 240, 0.68);
    }}
    """

    body = f"""
    <div class="vault-scene">
      {gobo_html}
      <div class="vault-assembly" id="vaultAssembly">
        <div class="matte-box-lid" id="boxLid"></div>
        <div class="matte-box-back"></div>
        {"".join(fan_cards_html)}
        <div class="matte-box-front">
          <div class="clasp-jewel-pill">STUDIO VAULT • v7.0</div>
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
      const pC0  = segProgress(norm, 0.18, 0.68);
      const pC1  = segProgress(norm, 0.26, 0.78);
      const pC2  = segProgress(norm, 0.34, 0.88);

      const asm = document.getElementById("vaultAssembly");
      if (asm) {
        asm.style.opacity = String(pBox);
        asm.style.transform = `perspective(1100px) rotateX(${5 - 2 * pBox}deg) rotateY(${-4 + 1.5 * pBox}deg) scale(${0.92 + 0.08 * pBox})`;
      }
      const lid = document.getElementById("boxLid");
      if (lid) {
        lid.style.transform = `perspective(900px) rotateX(${-12 - 22 * pLid}deg)`;
      }

      const c0 = document.getElementById("assetCard0");
      if (c0) {
        c0.style.transform = `translate3d(${-242 * pC0}px, ${-175 * pC0}px, 0) rotateZ(${-12 * pC0}deg)`;
        c0.style.opacity = String(0.15 + 0.85 * pC0);
      }
      const c1 = document.getElementById("assetCard1");
      if (c1) {
        c1.style.transform = `translate3d(0px, ${-248 * pC1}px, 0) rotateZ(0deg)`;
        c1.style.opacity = String(0.15 + 0.85 * pC1);
      }
      const c2 = document.getElementById("assetCard2");
      if (c2) {
        c2.style.transform = `translate3d(${242 * pC2}px, ${-175 * pC2}px, 0) rotateZ(${12 * pC2}deg)`;
        c2.style.opacity = String(0.15 + 0.85 * pC2);
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
    category = nfc(props.get("category", "ĐÁNH GIÁ ĐỘC LẬP • TRẢI NGHIỆM THỰC TẾ"))
    product_name = nfc(props.get("product_name", "Bộ Đèn Studio & Ống Kính Chân Dung"))
    score = float(props.get("score", 9.4))
    score_max = nfc(props.get("score_max", "/10"))
    verdict = nfc(props.get("verdict", "ĐÁNG XUỐNG TIỀN • TỐI ƯU CHO CREATOR & PHÒNG KHÁM"))

    pros = props.get("pros") or [
        "Độ hoàn màu CRI 98+ giữ tông da chuẩn tự nhiên",
        " Tản sáng mịn hai lớp, không gây chói mắt",
        "Khung hợp kim gọn nhẹ, lắp đặt trong 45 giây",
    ]
    cons = props.get("cons") or [
        "Quạt tản nhiệt nghe nhẹ khi thu âm sát 30cm",
        "Túi đựng đi kèm hơi khít khi gắn ngàm sẵn",
    ]

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
      width: 952px;
      padding: 44px 44px 40px;
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
      gap: 28px;
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
      gap: 28px;
    }}

    .score-title-block {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .score-cat {{
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      color: {pal["hex"]};
    }}

    .score-prod-name {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: 40px;
      line-height: 1.20;
      letter-spacing: -0.025em;
      color: #FAFAFA;
      padding: 0.12em 0.04em;
    }}

    .hero-score-badge {{
      min-width: 214px;
      padding: 20px 26px;
      border-radius: 28px;
      background: rgba(255, 255, 255, 0.05);
      border: 1.5px solid {pal["pill_border"]};
      box-shadow: 0 0 34px {pal["glow_ambient"]};
      display: flex;
      align-items: baseline;
      justify-content: center;
      gap: 4px;
    }}

    .hero-score-num {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 900;
      font-size: 74px;
      line-height: 1;
      letter-spacing: -0.04em;
      color: {pal["hex"]};
      text-shadow: 0 0 24px {pal["glow_outer"]};
    }}

    .hero-score-max {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: 28px;
      color: rgba(226, 232, 240, 0.62);
    }}

    .meter-block {{
      position: relative;
      z-index: 2;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .meter-track {{
      width: 100%;
      height: 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.09);
      overflow: hidden;
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
      grid-template-columns: 1.08fr 0.92fr;
      gap: 22px;
    }}

    .pc-col {{
      padding: 26px 26px;
      border-radius: 26px;
      display: flex;
      flex-direction: column;
      gap: 16px;
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
      gap: 10px;
      font-size: 21px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    .pros-header {{ color: #4ADE80; }}
    .cons-header {{ color: #FF4D5E; }}

    .pc-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    .review-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}

    .review-item {{
      display: flex;
      align-items: flex-start;
      gap: 12px;
      font-size: 22px;
      line-height: 1.42;
      color: #F1F5F9;
      padding: 0.06em 0.02em;
    }}

    .item-icon {{
      width: 28px;
      height: 28px;
      border-radius: 9px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }}

    .pro-icon {{ background: rgba(74, 222, 128, 0.16); }}
    .con-icon {{ background: rgba(255, 77, 94, 0.16); }}
    .item-icon svg {{ width: 17px; height: 17px; }}

    .verdict-ribbon {{
      position: relative;
      z-index: 2;
      padding: 18px 26px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.12);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: {pal["bright"]};
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
        <div class="hero-score-badge">
          <span class="hero-score-num" id="scoreNum">{score:.1f}</span>
          <span class="hero-score-max">{esc(score_max)}</span>
        </div>
      </div>

      <div class="meter-block">
        <div class="meter-track">
          <div class="meter-fill" id="meterFill"></div>
        </div>
      </div>

      <div class="pros-cons-grid">
        <div class="pc-col pros-col" id="prosCol">
          <div class="pc-header pros-header">
            <span class="pc-dot" style="background:#4ADE80; box-shadow:0 0 10px #4ADE80;"></span>
            <span>Điểm cộng nổi bật</span>
          </div>
          <ul class="review-list">{pros_html}</ul>
        </div>

        <div class="pc-col cons-col" id="consCol">
          <div class="pc-header cons-header">
            <span class="pc-dot" style="background:#FF4D5E; box-shadow:0 0 10px #FF4D5E;"></span>
            <span>Điểm trừ lưu ý</span>
          </div>
          <ul class="review-list">{cons_html}</ul>
        </div>
      </div>

      <div class="verdict-ribbon">
        <span>KẾT LUẬN TỔNG ĐÀI STUDIO</span>
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
    window_title = nfc(props.get("window_title", "studio://prompt-architect-v7.1 • Gemini / Veo Cinema"))
    prompt_kicker = nfc(props.get("prompt_kicker", "CẤU TRÚC CÂU LỆNH KHÓA ÁNH SÁNG & ỐNG KÍNH"))
    prompt_text = nfc(
        props.get(
            "prompt_text",
            "Chân dung điện ảnh chuyên gia trong phòng studio tối giản, ánh sáng Rembrandt 45 độ dịu mịn, "
            "ống kính 85mm f/1.4 xóa phông tự nhiên, giữ nguyên chi tiết da thật sắc nét, tông màu vàng hổ phách & ngọc lục bảo --ar 9:16 --stylize 250",
        )
    )
    locks = list(
        props.get("locks")
        or [
            "TỶ LỆ 9:16 DỌC",
            "ỐNG KÍNH 85MM F/1.4",
            "ÁNH SÁNG REMBRANDT",
            "KHÓA SEED NHÂN VẬT",
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
      width: 980px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 32px;
      padding: 40px 24px;
      perspective: 1150px;
      will-change: transform, opacity;
    }}

    .iso-browser-window {{
      position: relative;
      width: 910px;
      border-radius: 30px;
      padding: 1.5px;
      background: linear-gradient(
        135deg,
        {pal["hex"]}CC 0%,
        #F5C45199 42%,
        rgba(255, 255, 255, 0.14) 100%
      );
      transform: perspective(1150px) rotateY(-10deg) rotateX(5deg);
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
      padding: 20px 26px;
      background: rgba(255, 255, 255, 0.04);
      border-bottom: 1px solid rgba(255, 255, 255, 0.10);
    }}

    .traffic-dots {{
      display: flex;
      align-items: center;
      gap: 9px;
    }}

    .tdot {{
      width: 13px;
      height: 13px;
      border-radius: 50%;
    }}

    .address-pill {{
      padding: 8px 20px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.12);
      font-family: 'Studio Mono', monospace;
      font-size: 16px;
      color: rgba(226, 232, 240, 0.85);
    }}

    .status-ready-pill {{
      padding: 7px 16px;
      border-radius: 999px;
      background: {pal["pill_bg"]};
      border: 1px solid {pal["pill_border"]};
      font-family: 'Studio Mono', monospace;
      font-size: 15px;
      font-weight: 700;
      color: {pal["hex"]};
    }}

    .prompt-editor-body {{
      padding: 36px 38px 40px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      min-height: 350px;
    }}

    .prompt-kicker-line {{
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: #F5C451;
    }}

    .prompt-text-box {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 500;
      font-size: 29px;
      line-height: 1.52;
      color: #F8FAFC;
      padding: 0.12em 0.06em;
    }}

    .typing-caret {{
      display: inline-block;
      width: 4px;
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
      gap: 16px;
      max-width: 920px;
      transform: perspective(1150px) rotateY(-6deg) rotateX(3deg);
    }}

    .lock-pill {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 13px 22px;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.82);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.24),
        0 18px 40px rgba(0, 0, 0, 0.50);
      color: rgba(226, 232, 240, 0.72);
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.08em;
      will-change: transform, opacity, border-color, box-shadow;
    }}

    .lock-pill svg {{
      width: 19px;
      height: 19px;
      color: {pal["hex"]};
    }}

    .iso-bottom-note {{
      font-size: 30px;
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
            <div class="status-ready-pill" id="isoStatusPill">PROMPT LOCKED</div>
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
        const ry = -14 + 4 * pWin + breathRy;
        const rx = 8 - 3 * pWin + breathRx;
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
        statusEl.textContent = (totalFrames > 1 && pType < 0.98) ? "TYPING PROMPT..." : "PROMPT LOCKED";
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
    kicker = nfc(props.get("kicker", "BẢN QUAY THÔ GỐC • CHƯA QUA CHỈNH MÀU"))
    raw_imgs = props.get("images") or [
        props.get("img_01"),
        props.get("img_02"),
        props.get("img_03"),
    ]
    captions = props.get("captions") or [
        "RAW 01 • Góc rộng tự nhiên",
        "RAW 02 • Chân dung tiêu cự 85mm",
        "RAW 03 • Chi tiết cận cảnh",
    ]
    stamps = props.get("stamps") or ["CAM A • 24FPS", "CAM B • LOG-C", "MACRO • F/2.0"]
    raw_triggers = props.get("card_triggers_s") or [0.04, 0.30, 0.54]
    card_triggers_s = [float(raw_triggers[i]) if i < len(raw_triggers) else 0.04 + i * 0.25 for i in range(3)]
    bottom_note = nfc(props.get("bottom_note", ""))
    bottom_note_at_s = float(props.get("bottom_note_at_s", 1.35))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    urls = [
        image_to_safe_data_url(raw_imgs[i] if i < len(raw_imgs) else None, fallback_variant=f"raw{i + 1}")
        for i in range(3)
    ]

    polaroids_html = []
    for i in range(3):
        cap = esc(captions[i] if i < len(captions) else f"RAW 0{i + 1}")
        st = esc(stamps[i] if i < len(stamps) else f"RAW 0{i + 1}")
        polaroids_html.append(f"""
        <div class="polaroid-card pol-{i}" id="polCard{i}">
          <div class="polaroid-photo-well">
            <img src="{urls[i]}" alt="Polaroid {i + 1}" />
            <div class="polaroid-gloss-sheen" id="polSheen{i}"></div>
            <span class="raw-corner-tag">{st}</span>
          </div>
          <div class="polaroid-footer">
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
      width: 1020px;
      height: 1060px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 28px;
      perspective: 1250px;
      will-change: transform, opacity;
    }}

    .polaroid-kicker-pill {{
      padding: 11px 26px;
      border-radius: 999px;
      background: rgba(18, 20, 26, 0.80);
      backdrop-filter: blur(18px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.14em;
      color: {pal["hex"]};
      box-shadow: 0 14px 34px rgba(0,0,0,0.46);
      z-index: 10;
    }}

    .polaroid-fan-deck {{
      position: relative;
      width: 1000px;
      height: 680px;
      transform-style: preserve-3d;
    }}

    /* Warm Cream Archival Stock Polaroid (#FAF6EE) + Multi-Layer Physical Shadows */
    .polaroid-card {{
      position: absolute;
      top: 56px;
      left: 330px;
      width: 340px;
      padding: 18px 18px 26px;
      border-radius: 14px;
      background: linear-gradient(165deg, #FCF9F2 0%, #F4EFE4 100%);
      border: 1px solid rgba(255, 255, 255, 0.92);
      box-shadow:
        0 4px 10px rgba(0, 0, 0, 0.24),
        0 18px 36px rgba(0, 0, 0, 0.38),
        0 38px 74px rgba(0, 0, 0, 0.56);
      display: flex;
      flex-direction: column;
      gap: 16px;
      will-change: transform, opacity;
    }}

    .polaroid-photo-well {{
      position: relative;
      width: 100%;
      height: 356px;
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
      position: absolute;
      top: 14px;
      left: 14px;
      padding: 5px 12px;
      border-radius: 6px;
      background: rgba(12, 14, 18, 0.76);
      backdrop-filter: blur(8px);
      font-family: 'Studio Mono', monospace;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: #F8FAFC;
      border: 1px solid rgba(255,255,255,0.20);
    }}

    .polaroid-footer {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2px 6px;
    }}

    .polaroid-caption {{
      font-family: 'Playfair Display', Georgia, serif;
      font-style: italic;
      font-weight: 700;
      font-size: 24px;
      line-height: 1.28;
      color: #1E293B;
      padding: 0.12em 0.08em;
      text-align: center;
    }}

    .polaroid-bottom-note {{
      z-index: 12;
      font-size: 36px;
      line-height: 1.24;
      color: {pal["hex"]};
      padding: 0.32em 0.25em;
      margin-top: -12px;
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
          `perspective(1250px) translate3d(${{(-298 * p0).toFixed(2)}}px, ${{(28 * p0 + (1 - p0) * 44 + f0).toFixed(2)}}px, 0) ` +
          `rotateZ(${{(-7 * p0).toFixed(2)}}deg) rotateY(${{(7 * p0).toFixed(2)}}deg)`;
      }}
      const c1 = document.getElementById("polCard1");
      if (c1) {{
        c1.style.zIndex = "4";
        c1.style.opacity = String(p1.toFixed(4));
        c1.style.transform =
          `perspective(1250px) translate3d(0px, ${{-22 * p1 + (1 - p1) * 44 + f1}}px, 0) ` +
          `rotateZ(0deg) scale(${{(0.95 + 0.07 * p1).toFixed(4)}})`;
      }}
      const c2 = document.getElementById("polCard2");
      if (c2) {{
        c2.style.zIndex = "3";
        c2.style.opacity = String(p2.toFixed(4));
        c2.style.transform =
          `perspective(1250px) translate3d(${{(298 * p2).toFixed(2)}}px, ${{(32 * p2 + (1 - p2) * 44 + f2).toFixed(2)}}px, 0) ` +
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
    degree_kicker = nfc(props.get("degree", "THẠC SĨ • BÁC SĨ CHUYÊN KHOA I"))
    doctor_name = nfc(props.get("name", "BS. CKI. NGUYỄN MINH KHÔI"))
    specialty = nfc(props.get("specialty", "Trưởng Khoa Phục Hình Thẩm Mỹ • Nha Khoa Quốc Tế"))
    credential = nfc(props.get("credential", "15+ NĂM LÂM SÀNG • THÀNH VIÊN HIỆP HỘI IMPLANT QUỐC TẾ ITI"))
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
      width: {min(width - 92, 936)}px;
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
      gap: 26px;
      padding: 28px 34px;
    }}

    .crest-medallion {{
      width: 86px;
      height: 86px;
      border-radius: 24px;
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
      width: 44px;
      height: 44px;
    }}

    .authority-copy {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 7px;
    }}

    .degree-row {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      color: {pal["hex"]};
    }}

    .verified-seal {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: {pal["hex"]};
      color: #0B1120;
    }}

    .verified-seal svg {{
      width: 13px;
      height: 13px;
    }}

    .doctor-name {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 800;
      font-size: 38px;
      line-height: 1.18;
      letter-spacing: -0.024em;
      color: {name_col};
      padding: 0.10em 0.04em;
    }}

    .doctor-specialty {{
      font-family: 'Playfair Display', Georgia, serif;
      font-style: italic;
      font-weight: 600;
      font-size: 24px;
      line-height: 1.32;
      color: {spec_col};
      padding: 0.08em 0.04em;
    }}

    .credential-bar {{
      margin-top: 6px;
      padding-top: 10px;
      border-top: 1px solid {border_col};
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.10em;
      color: {pal["bright"] if not is_light else pal["deep"]};
    }}
    """

    body = f"""
    <div class="authority-card" id="authCard">
      <div class="authority-jewel-spine" id="authSpine"></div>
      <div class="authority-inner">
        <div class="crest-medallion">
          <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M16 3L5 7.5v8.2C5 23 9.7 27.9 16 30c6.3-2.1 11-7 11-14.3V7.5L16 3z"/>
            <path d="M16 10.5v11M10.5 16h11"/>
          </svg>
        </div>
        <div class="authority-copy">
          <div class="degree-row">
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


def _kt_shared_css(pal: dict[str, str], width: int, align: str = "center", *, theme: str = "dark") -> str:
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
      padding: 0.32em 0.25em;
    }}

    .kt-opt-pill {{
      margin-top: 6px;
      display: inline-flex;
      align-items: center;
      gap: 9px;
      padding: 9px 20px;
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
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: {pal["hex"]};
      box-shadow: 0 0 10px {pal["hex"]};
    }}

    .kt-opt-pill-label {{
      font-family: 'Be Vietnam Pro', sans-serif;
      font-weight: 600;
      font-size: 18px;
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
    raw_main = nfc(props.get("main_text", "chạm đúng nhịp thở")).strip()
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
    helper_size = int(props.get("kicker_size") or max(32, min(38, round(hero_size * 0.36))))
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

    line2_html = ""
    if line2_text:
        line2_html = f"""
        <div class="kt01-hero-line2 kt-diacritic-safe" id="kt01Line2">{esc(line2_text)}</div>
        """

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
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
    main_text = nfc(props.get("main_text", "chuyển động mượt")).strip()
    accent_text = nfc(props.get("accent_text", "Chuẩn Điện Ảnh")).strip()

    main_size = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=74, max_px=106, char_factor=0.56))
    helper_size = int(props.get("kicker_size") or max(30, min(36, round(main_size * 0.35))))
    accent_size = int(props.get("accent_size") or max(60, min(round(main_size * 0.90), _auto_typo_px(accent_text, width, min_px=58, max_px=96, char_factor=0.50))))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.08 if kicker else 0.02))
    accent_at_s = float(props.get("accent_at_s", main_at_s + 0.20))
    badge_at_s = float(props.get("badge_at_s", accent_at_s + 0.18))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    swash_html = render_swash_hybrid_html_py(accent_text)
    pill_html = _kt_optional_pill_html(props)
    helper_html = (
        f'<div class="kt02-helper kt-diacritic-safe" id="kt02Helper">{esc(kicker)}</div>'
        if kicker
        else ""
    )
    wrap_drop = "drop-shadow(0 6px 20px rgba(15, 23, 42, 0.14))" if is_light else "drop-shadow(0 8px 24px rgba(0, 0, 0, 0.55))"
    feather_end = "0.22" if is_light else "0.05"

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
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
      white-space: {"nowrap" if len(accent_text) <= 25 else "normal"};
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
        <div class="kt02-hero kt-diacritic-safe" id="kt02Hero">{esc(main_text)}</div>
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
        main_text = nfc(props.get("main_text", "cứ Camera bật")).strip()
        words = [w for w in main_text.split() if w] or ["cứ", "Camera", "bật"]

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
    helper_px = int(props.get("kicker_size") or max(30, round(word_px * 0.36)))

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

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
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
      column-gap: 0.24em;
      row-gap: 0.06em;
      font-size: {word_px}px;
      line-height: 1.08;
      letter-spacing: -0.036em;
    }}

    .kt03-word {{
      display: inline-block;
      margin: -0.26em -0.20em;
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
        const blurPx = (1 - p) * 12.0;
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
    setup_text = nfc(props.get("setup_text") or props.get("kicker") or "tưởng chỉ cần nét căng").strip()
    main_text = nfc(props.get("main_text", "chiều sâu quang học")).strip()
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_size = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=72, max_px=98, char_factor=0.57))
    setup_size = int(props.get("setup_size") or max(36, min(46, round(hero_size * 0.48))))
    acc_size = int(props.get("accent_size") or max(52, round(hero_size * 0.76)))

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

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
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
      <div class="kt04-setup kt-diacritic-safe" id="kt04Setup">{esc(setup_text)}</div>
      <div class="kt04-hero kt-diacritic-safe" id="kt04Hero">{esc(main_text)}</div>
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
        else:
            clauses.append({"text": left_text, "at_s": round(kicker_at_s, 4)})

    acc_at_s = float(
        props.get(
            "accent_at_s",
            inferred_acc_at if inferred_acc_at is not None else (turn_at_s + 0.32),
        )
    )
    return clauses, acc_at_s


def _build_kt05_wall_spatial_counterpoint(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "crimson", theme=theme_mode)
    mode = nfc(props.get("mode", "left_right_counter")).lower()
    is_wall_hop = mode == "wall_hop"

    left_text = nfc(props.get("left_text") or props.get("setup_text") or props.get("kicker") or ("chỉ một" if is_wall_hop else "ánh sáng phẳng")).strip()
    right_text = nfc(props.get("right_text") or props.get("main_text") or ("điểm chạm sáng" if is_wall_hop else "tách khối thật")).strip()
    accent_text = nfc(props.get("accent_text", "")).strip()

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    turn_at_s = float(props.get("turn_at_s", props.get("main_at_s", 0.34 if not is_wall_hop else 0.24)))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))
    left_clauses, accent_at_s = _normalize_kt05_left_clauses(props, left_text, kicker_at_s, turn_at_s)

    left_px = int(props.get("left_size") or (38 if is_wall_hop else 48))
    right_px = int(props.get("main_size") or (84 if is_wall_hop else 64))

    left_clauses_html = "\n".join(
        f'<div class="kt05-left-clause kt-diacritic-safe" id="kt05LeftClause_{idx_c}">{esc(c_item["text"])}</div>'
        for idx_c, c_item in enumerate(left_clauses)
    )
    accent_sub_html = (
        f'<div class="kt05-right-sub kt-diacritic-safe" id="kt05RightSub">{render_swash_hybrid_html_py(accent_text)}</div>'
        if accent_text
        else ""
    )

    css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
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
      font-size: {max(34, round(right_px * 0.62))}px;
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
        <div class="kt05-right-main kt-diacritic-safe" id="kt05RightMain">{esc(right_text)}</div>
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
        w1 = nfc(props.get("main_text", "màu da thật")).strip()
        w2 = nfc(props.get("accent_text", "ánh mắt sống")).strip()
        raw_swaps = [
            {"text": w1, "at_s": float(props.get("main_at_s", 0.05)), "hue": default_accent, "italic": False},
            {"text": w2 or "chiều sâu thật", "at_s": float(props.get("swap_at_s", 0.42)), "hue": "emerald", "italic": True},
        ]

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_swaps):
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
    fallback_pal = resolve_jewel_palette(default_accent, theme=theme)
    return out or [{"text": "màu da thật", "at_s": 0.05, "hex": fallback_pal["hex"], "glow": fallback_pal["glow_outer"], "italic": False}]


def _build_kt06_bridge_anchor_live_swap(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    default_accent = nfc(props.get("jewel_accent") or props.get("accent") or "gold")
    pal = resolve_jewel_palette(default_accent, theme=theme_mode)
    anchor_text = nfc(props.get("anchor_text") or props.get("kicker") or "giữ trọn").strip()
    swaps = _normalize_kt06_swaps(props, default_accent, theme=theme_mode)
    anchor_at_s = float(props.get("anchor_at_s", 0.02))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    longest_swap = max((s["text"] for s in swaps), key=len)
    combined = f"{anchor_text} {longest_swap}"
    font_px = int(props.get("main_size") or _auto_typo_px(combined, width, min_px=60, max_px=90, char_factor=0.58))

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
            f'<div class="kt06-swap-item kt-diacritic-safe" id="kt06Swap{idx}" '
            f'style="font-family:{fam};font-style:{fst};font-weight:{fw};color:{sw["hex"]};filter:url(#kt06VBlur{idx});">'
            f'{esc(sw["text"])}</div>'
        )

    # Reserve exact slot width in ch/px based on longest swap word
    slot_min_w = max(180, int(len(longest_swap) * font_px * 0.56))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
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
        <span class="kt06-anchor kt-diacritic-safe" id="kt06Anchor">{esc(anchor_text)}</span>
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
    main_text = nfc(props.get("main_text", "độ nét điện ảnh")).strip()
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=68, max_px=98, char_factor=0.56))
    acc_px = int(props.get("accent_size") or max(48, round(hero_px * 0.72)))
    helper_px = int(props.get("kicker_size") or max(28, round(hero_px * 0.36)))

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

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
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

    .kt07-char {{
      display: inline-block;
      padding: 0.32em 0.16em;
      margin: -0.32em -0.16em;
      -webkit-text-stroke: 0px transparent;
      will-change: transform, opacity, color, text-shadow;
    }}

    .kt07-space {{
      display: inline-block;
      width: 0.28em;
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
      <div class="kt07-line" id="kt07Line"></div>
      {accent_html}
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const HERO_TEXT = {json.dumps(main_text, ensure_ascii=False)};
    const GRAPHEMES = splitGraphemesVi(HERO_TEXT);
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

    // Build grapheme spans once (100% Vietnamese NFC diacritic safe via Intl.Segmenter)
    const lineHost = document.getElementById("kt07Line");
    const charNodes = [];
    if (lineHost) {{
      GRAPHEMES.forEach((g) => {{
        if (/^\\s+$/.test(g)) {{
          const sp = document.createElement("span");
          sp.className = "kt07-space";
          sp.textContent = " ";
          lineHost.appendChild(sp);
        }} else {{
          const ch = document.createElement("span");
          ch.className = "kt07-char";
          ch.textContent = g;
          lineHost.appendChild(ch);
          charNodes.push(ch);
        }}
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
        const dx = -32 * (1 - pMove);

        const posNorm = i / nChars;
        const sheenDist = Math.abs(posNorm - sheenCenter);
        const sheenHit = Math.max(0, 1 - sheenDist / 0.20) * pMove;

        ch.style.opacity = String(op.toFixed(4));
        ch.style.transform = `translate3d(${{dx.toFixed(2)}}px, 0, 0)`;
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
    }};
    window.__setFrame(1, 1, 60);
    """
    return wrap_studio_document(width=width, height=height, extra_css=css, body_html=body, frame_js=js, theme=theme_mode)


# 8. `kt08_mist_evaporation_reveal` (`SIL_MIST_GRADIENT`, default 1080x480)
def _build_kt08_mist_evaporation_reveal(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "ice_cyan", theme=theme_mode)
    align = nfc(props.get("align", "center")).lower()
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = nfc(props.get("main_text", "vùng sáng dịu")).strip()
    accent_text = nfc(props.get("accent_text", "Tan Nhẹ Như Sương")).strip()
    keep_mist_tail = bool(props.get("keep_mist_tail", False))

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=68, max_px=96, char_factor=0.56))
    acc_px = int(props.get("accent_size") or max(56, min(round(hero_px * 0.88), _auto_typo_px(accent_text, width, min_px=54, max_px=88, char_factor=0.50))))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.06 if kicker else 0.03))
    accent_at_s = float(props.get("accent_at_s", main_at_s + 0.22))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    helper_html = f'<div class="kt08-helper kt-diacritic-safe" id="kt08Helper">{esc(kicker)}</div>' if kicker else ""
    mist_inner = render_swash_hybrid_html_py(accent_text)

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
    .kt08-helper {{
      font-size: 32px;
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
        <div class="kt08-mist-halo kt-diacritic-safe" id="kt08MistHalo">{mist_inner}</div>
        <div class="kt08-mist-core kt-diacritic-safe" id="kt08MistCore">{mist_inner}</div>
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
    main_text = nfc(props.get("main_text", "nhìn giả trân")).strip()
    accent_text = nfc(props.get("accent_text", "")).strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=74, max_px=104, char_factor=0.56))
    acc_px = int(props.get("accent_size") or max(44, round(hero_px * 0.62)))

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

    css = _kt_shared_css(pal, width, align, theme=theme_mode) + f"""
    .kt09-helper {{
      font-size: 32px;
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
      white-space: {"nowrap" if len(main_text) <= 22 else "normal"};
      text-shadow: {hero_shadow};
      will-change: transform, opacity, filter;
    }}

    /* Glowing SVG #FF4D5E razor laser slash across 56% x-height */
    .kt09-laser-svg {{
      position: absolute;
      left: 2%;
      right: 2%;
      width: 96%;
      height: 36px;
      top: 56%;
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
        <div class="kt09-myth-hero kt-diacritic-safe" id="kt09Hero">{esc(main_text)}</div>
        <svg class="kt09-laser-svg" id="kt09Laser" viewBox="0 0 600 36" preserveAspectRatio="none">
          <defs>
            <filter id="laserBloom" x="-15%" y="-180%" width="130%" height="460%">
              <feGaussianBlur stdDeviation="5.5" result="b1"/>
              <feMerge>
                <feMergeNode in="b1"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <line x1="0" y1="18" x2="600" y2="18" stroke="#FF4D5E" stroke-width="11" stroke-linecap="round" opacity="0.58" filter="url(#laserBloom)"/>
          <line x1="0" y1="18" x2="600" y2="18" stroke="#FF4D5E" stroke-width="6.5" stroke-linecap="round"/>
          <line x1="4" y1="18" x2="596" y2="18" stroke="#FFE4E6" stroke-width="2.4" stroke-linecap="round"/>
        </svg>
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

      const laser = document.getElementById("kt09Laser");
      if (laser) {{
        laser.style.opacity = String((pSlash > 0 ? 1 : 0).toFixed(4));
        laser.style.transform = `translateY(-50%) scaleX(${{pSlash.toFixed(4)}})`;
      }}

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


# 10. `kt10_cursor_bars_pillar_gate` (`SIL_CURSOR_HUD`, default 1080x460)
def _build_kt10_cursor_bars_pillar_gate(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "emerald", theme=theme_mode)
    kicker = nfc(props.get("kicker", "")).strip()
    main_text = nfc(props.get("main_text", "3 bước khóa ảnh")).strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=64, max_px=88, char_factor=0.58, usable_ratio=0.78))
    helper_px = int(props.get("kicker_size") or max(28, min(34, round(hero_px * 0.42))))

    kicker_at_s = float(props.get("kicker_at_s", 0.02))
    main_at_s = float(props.get("main_at_s", 0.08 if kicker else 0.03))
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    helper_html = f'<div class="kt10-helper kt-diacritic-safe" id="kt10Helper">{esc(kicker)}</div>' if kicker else ""
    pillar_h = max(84, round(hero_px * 1.24))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
    .kt10-helper {{
      font-size: {helper_px}px;
      font-weight: {"600" if is_light else "500"};
      color: {primary_ink};
      margin-bottom: -0.18em;
      text-shadow: {helper_shadow};
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
      {_kt_optional_pill_html(props)}
    </div>
    """

    js = f"""
    const KICK_AT = {kicker_at_s};
    const MAIN_AT = {main_at_s};
    const EXIT_DUR = {exit_dur_s};
    const GLOW_IN = {json.dumps(pal["glow_inner"])};
    const GLOW_OUT = {json.dumps(pal["glow_outer"])};
    const IS_LIGHT = {json.dumps(is_light)};

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

      const helper = document.getElementById("kt10Helper");
      if (helper) {{
        const pK = timeProgress(tSec, KICK_AT, 0.22, velvetC2);
        helper.style.opacity = String(pK.toFixed(4));
        helper.style.transform = `translate3d(0, ${{((1 - pK) * 14).toFixed(2)}}px, 0)`;
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


# 11. `kt11_cranial_svg_arc_or_tilt` (`SIL_TILT_OR_ARC`, default 1080x620)
def _build_kt11_cranial_svg_arc_or_tilt(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, _helper_shadow = _kt_theme_tokens(props)
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    mode = nfc(props.get("mode", "svg_arc")).lower()
    is_tilt = mode in ("tilted_chest", "tilt")
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    if not is_tilt:
        main_text = nfc(props.get("main_text", "vòng sáng điện ảnh tự nhiên")).strip()
        accent_text = nfc(props.get("accent_text", "")).strip()
        arc_px = int(props.get("main_size") or max(44, min(66, int(760 / max(9.0, len(main_text) * 0.54)))))
        main_at_s = float(props.get("main_at_s", 0.04))
        accent_at_s = float(props.get("accent_at_s", main_at_s + 0.28))

        cx = width // 2
        rx = int(props.get("arc_rx", 390))
        ry = int(props.get("arc_ry", 145))
        base_y = int(height * 0.72)
        x0 = cx - rx
        x1 = cx + rx

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

        css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
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
          bottom: {max(36, int(height * 0.14))}px;
          font-size: 46px;
          color: {primary_ink};
          text-shadow: {hero_shadow};
        }}
        """

        body = f"""
        <div class="kt11-arc-stage" id="ktRig">
          <svg class="kt11-arc-svg" viewBox="0 0 {width} {height}">
            <defs>
              <path id="kt11HaloPath" d="M {x0},{base_y} A {rx},{ry} 0 0,1 {x1},{base_y}" fill="none" />
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
              <text class="kt11-arc-text" dy="-8">
                <textPath href="#kt11HaloPath" startOffset="50%" text-anchor="middle">{esc(main_text)}</textPath>
              </text>
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
    sub_text = nfc(props.get("sub_text") or props.get("kicker") or "chạm cảm xúc").strip()
    main_text = nfc(props.get("main_text", "Đúng Nhịp Thật")).strip()
    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=72, max_px=100, char_factor=0.56))
    sub_px = int(props.get("sub_size") or max(36, round(hero_px * 0.44)))

    main_at_s = max(0.12, float(props.get("main_at_s", 0.14)))
    sub_at_s = float(props.get("sub_at_s", max(0.0, main_at_s - 0.10)))  # Exact -0.10s before hero!
    tilt_deg = float(props.get("tilt_deg", -5.5))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
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
      color: {pal["hex"]};
      will-change: transform, opacity, filter;
    }}
    """

    body = f"""
    <div class="kt-rig" id="ktRig">
      <div class="kt11-tilt-cluster">
        <div class="kt11-tilt-sub kt-diacritic-safe" id="kt11TiltSub">{esc(sub_text)}</div>
        <div class="kt11-tilt-hero kt-diacritic-safe" id="kt11TiltHero">{render_swash_hybrid_html_py(main_text)}</div>
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
def _build_kt12_whisper_or_directional_echo(props: dict[str, Any], width: int, height: int) -> str:
    theme_mode, is_light, primary_ink, hero_shadow, helper_shadow = _kt_theme_tokens(props)
    mode = nfc(props.get("mode", "whisper")).lower()
    is_echo = mode in ("directional_echo", "echo")
    pal = resolve_jewel_palette(props.get("jewel_accent") or props.get("accent") or "gold", theme=theme_mode)
    exit_dur_s = float(props.get("exit_dur_s", 0.14))

    if not is_echo:
        # `mode="whisper"`: ultra-clean 36–40px lowercase geometric sans (#FAFAFA dark / #14171F light), 0 pill, 0 heavy glow
        main_text = nfc(props.get("main_text", "nhưng điều ít ai để ý là...")).strip()
        whisper_px = int(props.get("main_size") or max(36, min(40, _auto_typo_px(main_text, width, min_px=36, max_px=40, char_factor=0.52))))
        main_at_s = float(props.get("main_at_s", 0.02))
        reveal_style = nfc(props.get("reveal", "feather_wipe")).lower()

        css = f"""
        .kt12-whisper-rig {{
          display: flex;
          align-items: center;
          justify-content: center;
          max-width: {int(width * 0.90)}px;
          padding: 16px 24px;
          will-change: transform, opacity, filter;
        }}

        .kt12-whisper-line {{
          font-family: 'Be Vietnam Pro', sans-serif;
          font-weight: {"500" if is_light else "400"};
          font-size: {whisper_px}px;
          line-height: 1.32;
          letter-spacing: -0.01em;
          color: {primary_ink};
          -webkit-text-stroke: 0px transparent !important;
          padding: 0.32em 0.25em;
          text-align: center;
          /* Subtle natural ambient legibility shadow ONLY — 0 heavy glow, 0 pill */
          text-shadow: {helper_shadow};
          will-change: opacity, transform, -webkit-mask-image;
        }}
        """

        body = f"""
        <div class="kt12-whisper-rig" id="ktRig">
          <div class="kt12-whisper-line" id="kt12Whisper">{esc(main_text)}</div>
        </div>
        """

        js = f"""
        const MAIN_AT = {main_at_s};
        const REVEAL_STYLE = {json.dumps(reveal_style)};
        const EXIT_DUR = {exit_dur_s};

        window.__setFrame = function(frameIdx, totalFrames, fps) {{
          const safeFps = Math.max(1, Number(fps) || 60);
          const clipDurSec = totalFrames <= 1 ? 0 : totalFrames / safeFps;
          const fade4fSec = 4 / safeFps;
          const tSec = resolveSceneTimeSec(frameIdx, totalFrames, safeFps, MAIN_AT + 0.7);

          const rig = document.getElementById("ktRig");
          if (rig) {{
            rig.style.opacity = "1";
            rig.style.transform = "";
            rig.style.filter = "none";
          }}

          const el = document.getElementById("kt12Whisper");
          if (el) {{
            if (REVEAL_STYLE === "fade") {{
              const pF = timeProgress(tSec, MAIN_AT, fade4fSec, velvetC2);
              el.style.opacity = String(pF.toFixed(4));
              el.style.transform = `translate3d(0, ${{((1 - pF) * 8).toFixed(2)}}px, 0)`;
            }} else {{
              const pW = timeProgress(tSec, MAIN_AT, 0.22, velvetC2);
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
    main_text = nfc(props.get("main_text", "lặp lại")).strip()
    bottom_text = nfc(props.get("accent_text") or props.get("sub_text") or "đúng cấu trúc nhịp").strip()

    hero_px = int(props.get("main_size") or _auto_typo_px(main_text, width, min_px=78, max_px=102, char_factor=0.56))
    bot_px = int(props.get("accent_size") or max(40, min(52, round(hero_px * 0.50))))

    main_at_s = float(props.get("main_at_s", 0.03))
    echo_at_s = float(props.get("echo_at_s", main_at_s + 0.12))
    accent_at_s = float(props.get("accent_at_s", echo_at_s + 0.10))

    css = _kt_shared_css(pal, width, "center", theme=theme_mode) + f"""
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
        <div class="kt12-echo-layer kt12-echo-g2 kt-diacritic-safe" id="kt12Echo2">{esc(main_text)}</div>
        <div class="kt12-echo-layer kt12-echo-g1 kt-diacritic-safe" id="kt12Echo1">{esc(main_text)}</div>
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
        e1.style.opacity = String((0.42 * pEcho).toFixed(4));
        e1.style.transform = `translate3d(${{(10 * pEcho).toFixed(2)}}px, ${{-12 * pEcho}}px, 0)`;
      }}

      const e2 = document.getElementById("kt12Echo2");
      if (e2) {{
        e2.style.opacity = String((0.18 * pEcho).toFixed(4));
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
    h = int(height or clean_props.get("height") or defaults["height"])
    return _BUILDERS[key](clean_props, w, h)


def render_web_plates_batch(
    jobs: Sequence[dict[str, Any]],
    *,
    concurrency: int = 4,
    alpha_codec: str = "prores4444",
    strip_meta: bool = True,
    quiet: bool = False,
) -> list[dict[str, Any]]:
    """
    Renders multiple Studio plates (`.png` RGBA stills and/or `.mov` ProRes 4444 / qtrle clips)
    in parallel (`concurrency` up to 4 CDP tabs) inside a SINGLE Chrome Headless process.
    """
    if not jobs:
        return []
    node_bin = resolve_node_binary()
    if not ENGINE_MJS.is_file():
        raise FileNotFoundError(f"Engine script missing: {ENGINE_MJS}")

    safe_concurrency = max(1, min(4, int(concurrency)))

    with tempfile.TemporaryDirectory(prefix="usd-v71-plates-") as tmpdir:
        tmp_root = Path(tmpdir)
        engine_jobs: list[dict[str, Any]] = []
        out_paths: list[Path] = []

        for idx, job in enumerate(jobs):
            tpl = nfc(job["template"]).strip()
            if tpl not in TEMPLATE_DEFAULTS:
                raise ValueError(f"Unknown template '{tpl}'. Available: {', '.join(TEMPLATE_DEFAULTS.keys())}")
            props = normalize_props_nfc(job.get("props") or {})
            defaults = TEMPLATE_DEFAULTS[tpl]
            w = int(job.get("width") or props.get("width") or defaults["width"])
            h = int(job.get("height") or props.get("height") or defaults["height"])
            out_path = Path(job["out"]).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            html_doc = build_template_html(tpl, props, width=w, height=h)
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

            engine_jobs.append(engine_job)
            out_paths.append(out_path)

        batch_json_path = tmp_root / "batch_jobs.json"
        batch_payload = {
            "concurrency": safe_concurrency,
            "alphaCodec": alpha_codec,
            "jobs": engine_jobs,
        }
        batch_json_path.write_text(json.dumps(batch_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        cmd = [
            node_bin,
            str(ENGINE_MJS),
            "--batch-json",
            str(batch_json_path),
            "--concurrency",
            str(safe_concurrency),
            "--alpha-codec",
            str(alpha_codec),
        ]
        if quiet:
            cmd.append("--quiet")

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"web_cinema_plate_engine.mjs failed (exit {proc.returncode}):\n{proc.stderr}"
            )

        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        results: list[dict[str, Any]] = payload.get("results", [])

        if strip_meta:
            for p in out_paths:
                if p.is_file():
                    strip_media_metadata_if_available(p)

        return results


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
        anchor = nfc(props.get("anchor_text") or props.get("kicker") or "giữ trọn").strip()
        swaps = _normalize_kt06_swaps(props, nfc(props.get("jewel_accent") or props.get("accent") or "gold"))
        swap_str = " / ".join(s["text"] for s in swaps)
        return f"{anchor} {swap_str}".strip()
    if template == "kt05_wall_spatial_counterpoint":
        l_txt = nfc(props.get("left_text") or props.get("setup_text") or props.get("kicker") or "").strip()
        r_txt = nfc(props.get("right_text") or props.get("main_text") or "").strip()
        if l_txt:
            parts.append(l_txt)
        if r_txt:
            parts.append(r_txt)
        if parts:
            return " — ".join(parts)

    for key in ("setup_text", "sub_text", "main_text", "line2_text", "accent_text"):
        val = nfc(props.get(key) or "").strip()
        if val and val not in parts:
            parts.append(val)
    if not parts:
        # Fallback to template default render text
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
        anchor = nfc(props.get("anchor_text") or "giữ trọn").strip()
        triggers = [{"token": anchor, "at_s": round(float(props.get("anchor_at_s", 0.02)), 4)}]
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
    concurrency: int = 4,
    fps: int = 60,
    alpha_codec: str = "prores4444",
    device_scale_factor: float = 1.0,
    strip_meta: bool = True,
    quiet: bool = False,
) -> list[dict[str, Any]]:
    """
    High-throughput `v7.1` parallel kinetic typography `.mov` renderer (`@60fps`).
    Renders `kt01..kt12` jobs in parallel across up to 4 Chrome Headless CDP tabs, writes
    `<out_path>.typo_meta.json` sidecars, and returns full metadata/clip dicts.
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
        h = int(job.get("height") or props.get("height") or kt_spec["height"])
        job_codec = nfc(job.get("alpha_codec") or job.get("alphaCodec") or alpha_codec)
        job_scale = float(job.get("device_scale_factor", job.get("scale", device_scale_factor)))

        batch_specs.append(
            {
                "template": tpl,
                "props": props,
                "out": str(out_path),
                "mode": "mov",
                "width": w,
                "height": h,
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
        }
        meta_records.append((out_path, typo_meta))

    engine_results = render_web_plates_batch(
        batch_specs,
        concurrency=concurrency,
        alpha_codec=alpha_codec,
        strip_meta=strip_meta,
        quiet=quiet,
    )

    final_items: list[dict[str, Any]] = []
    for (out_path, typo_meta), eng_res in zip(meta_records, engine_results):
        meta_path = Path(f"{out_path}.typo_meta.json")
        combined = {
            **typo_meta,
            "codec": eng_res.get("codec", "prores_ks_4444_yuva444p10le"),
            "bytes": eng_res.get("bytes", 0),
            "elapsedMs": eng_res.get("elapsedMs", 0),
            "meta_path": str(meta_path),
        }
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
        check=True,
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


def run_self_test(out_dir: Path) -> dict[str, Any]:
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
        kicker="THUMBNAIL COVER • 134/134 NFC: Ộ Ệ Ữ Ắ Ẳ",
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
            "props": {
                "kicker": "NGHỆ THUẬT DỰNG PHIM • CHUẨN STUDIO",
                "main_text": "ĐỘ SÂU ĐIỆN ẢNH",
                "accent_text": "Chạm Cảm Xúc Thật",
                "badge_text": "134/134 NFC: Ộ • Ệ • Ữ • Ắ • Ẳ",
                "jewel_accent": "gold",
            },
        },
        {
            "template": "frosted_glass_bento_steps",
            "out": str(out_dir / "02_frosted_glass_bento_steps.png"),
            "mode": "still",
            "props": {
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
            "height": 420,
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
            "props": {"jewel_accent": "emerald"},
        },
    ]

    render_results = render_web_plates_batch(batch_jobs, concurrency=4, strip_meta=True)
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

    kt_results = render_kinetic_typo_batch(kt_jobs, concurrency=4, fps=60, strip_meta=True)
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

    report = {
        "ok": True,
        "version": "7.1",
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
        description="Universal Studio Director v7.1 — Web-Cinema Studio RGBA Plate & 60fps Kinetic Typography Builder"
    )
    parser.add_argument("--list", action="store_true", help="List all 20 built-in Studio & Kinetic Typography templates")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify static PNG veto, all 8 Studio templates, and all 12 60fps Kinetic Typography templates",
    )
    parser.add_argument(
        "--out-dir",
        default="/tmp/test_v71_web_plates",
        help="Target directory for --self-test (default: /tmp/test_v71_web_plates)",
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
    parser.add_argument("--concurrency", "-c", type=int, default=4)
    parser.add_argument("--no-strip", action="store_true", help="Skip strip_metadata pass")

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
        run_self_test(Path(args.out_dir))
        return 0

    if not args.template or not args.out:
        parser.error("Provide --template and --out (or use --list / --self-test).")

    props = _load_props_arg(args.props_json)
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
