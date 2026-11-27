#!/usr/bin/env python3
"""
Stateless Color-World & Multi-Hue Typography, Wall Micro-Words, Negative-Leading Kiss & 3-Cam Toolkit (`v6.0` core, packaged as `v7.9.0`)
==============================================================================================================
v7.4.0: `import os` crash fix (`--self-test` / `--self-test-v71` run clean); no API change.
100% backward-compatible with `v5.1`/`v5.2` `opa-video-studio` & `craft-handoff` (`.craft.json` -> `fc_build.py` /
`spec_lint.py` / `edit_rules.py` / `text_motion.py`), upgraded with `v6.0` `@__dviet` (`770765` + 19-video audit):
  - `DVIET_COLOR_WORLDS` & `plan_color_world_for_video`: Cohesive 1-World-per-video color system
    (`1 Primary Hue + 0–1 Pain Hue + Light/Dark Polarity`) eliminating rainbow soup.
  - `dviet_wall_microword_pop` & `dviet_two_point_wall_hop`: Lowercase 1–3 word pops & 2-point spatial hops
    placed directly inside empty wall negative space (`x=735` on `left_third`, `x=345` on `right_third`, `y=380..620`).
  - `dviet_kiss_hero_pair` & `export_dviet_bevel_lockup_png`: Tight `-20%` negative-leading (`line_height ~ 0.80`,
    `hero_y - lead_y ~ 54px`) lowercase hero fusion + 2x-supersampled 3D extruded bevel lockup PNG exporter.
  - `s03_stepup_underline_sub`: Clean dual-tone / tracking-settle sub-line (`0` fake `'____'` ASCII underscores!).
  - `s10` / `s12` Whisper Mode (`whisper_mode=True` by default when `style_profile="dviet"`, `Regular y=1590`; v7.9.1: never below 64 px).
  - `aroll_camera(..., framing="center"|"left_third"|"right_third"|"closeup_high", eye_line_y=...)` (`0` black bars!)
    & `snap_subcut(..., mode="sync"|"vocal_jcut", j_lead_s=0.32)` bimodal J-Cut planner.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
import unicodedata
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

DEFAULT_FPS = 30
HERO_ROW_FIT = 0.95
DEFAULT_MAX_TEXT_WIDTH_PX = 860.0
R209_SAFE_BOTTOM_Y = 1360.0
R30_MIN_CHUNK_S = 0.18
R30_TIGHT_MAX_S = 0.32

HEX6_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
TEXT_VI_PATH = Path(__file__).resolve().parents[2] / "data" / "text_vi.json"

_OPEN_AFFX = "“«\"‘(["
_CLOSE_AFFX = "”»\"’)]"
_TRAIL_PUNCT = ",.!?…:;"
_SENTENCE_END_PUNCT = ".?!…"
_NUM_TOKEN_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)*(?:[%+xX]|[A-Za-zĐđ]{1,4})?$")
_CAPS_FILE_TOKEN_RE = re.compile(r"^[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ0-9_]{2,}(?:\.[A-Za-z0-9]{1,8})+$")

# v7.9.1: optional extra dirs; `$PFD_FONT_DIR` is searched first and fontconfig (fc-list) last (web_plate_builder.find_font_file)
FONT_SEARCH_DIRS = [
    Path.home() / ".local/share/fonts/tnedit",
    Path.home() / ".local/share/fonts/Montserrat_Static",
    Path.home() / ".local/share/fonts/motion-fx",
    Path.home() / ".local/share/fonts/opa_fonts",
    Path.home() / ".local/share/fonts/apple-sf-pro",
    Path.home() / ".local/share/fonts/apple-sf-mono",
    Path.home() / ".local/share/fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/noto"),
]

_FONT_FILE_MAP: dict[tuple[str, str], list[str]] = {
    ("be vietnam pro", "black"): ["BeVietnamPro-Black.ttf", "BeVietnamPro-ExtraBold.ttf"],
    ("be vietnam pro", "blackitalic"): ["BeVietnamPro-BlackItalic.ttf", "BeVietnamPro-BoldItalic.ttf"],
    ("be vietnam pro", "extrabold"): ["BeVietnamPro-ExtraBold.ttf", "BeVietnamPro-Bold.ttf"],
    ("be vietnam pro", "extrabolditalic"): ["BeVietnamPro-ExtraBoldItalic.ttf", "BeVietnamPro-BoldItalic.ttf"],
    ("be vietnam pro", "bold"): ["BeVietnamPro-Bold.ttf", "BeVietnamPro-ExtraBold.ttf"],
    ("be vietnam pro", "bolditalic"): ["BeVietnamPro-BoldItalic.ttf", "BeVietnamPro-Italic.ttf"],
    ("be vietnam pro", "italic"): ["BeVietnamPro-Italic.ttf", "BeVietnamPro-BoldItalic.ttf"],
    ("be vietnam pro", "semibold"): ["BeVietnamPro-Bold.ttf", "Montserrat-Medium.ttf"],
    ("be vietnam pro", "medium"): ["BeVietnamPro-Bold.ttf", "BeVietnamPro-Light.ttf"],
    ("be vietnam pro", "regular"): ["BeVietnamPro-Light.ttf", "BeVietnamPro-Bold.ttf"],
    ("be vietnam pro", "light"): ["BeVietnamPro-Light.ttf", "BeVietnamPro-ExtraLight.ttf"],
    ("montserrat", "black"): ["Montserrat-Black.otf", "Montserrat-ExtraBold.ttf", "BeVietnamPro-Black.ttf"],
    ("montserrat", "extrabold"): ["Montserrat-ExtraBold.ttf", "Montserrat-ExtraBold.otf", "BeVietnamPro-ExtraBold.ttf"],
    ("montserrat", "extrabolditalic"): ["Montserrat-ExtraBoldItalic.ttf", "BeVietnamPro-ExtraBoldItalic.ttf"],
    ("montserrat", "bold"): ["Montserrat-Bold.otf", "Montserrat-ExtraBold.ttf", "BeVietnamPro-Bold.ttf"],
    ("montserrat", "bolditalic"): ["Montserrat-ExtraBoldItalic.ttf", "Montserrat-SemiBoldItalic.ttf"],
    ("montserrat", "italic"): ["Montserrat-SemiBoldItalic.ttf", "BeVietnamPro-Italic.ttf"],
    ("montserrat", "semibold"): ["Montserrat-Bold.otf", "Montserrat-Medium.ttf"],
    ("montserrat", "medium"): ["Montserrat-Medium.ttf", "Montserrat-Bold.otf"],
    ("montserrat", "regular"): ["Montserrat-Medium.ttf", "BeVietnamPro-Bold.ttf"],
    ("playfair display", "italic"): ["PlayfairDisplay-BoldItalic.ttf", "PlayfairDisplay-Italic[wght].ttf", "BeVietnamPro-BoldItalic.ttf"],
    ("playfair display", "bolditalic"): ["PlayfairDisplay-BoldItalic.ttf", "PlayfairDisplay-Italic[wght].ttf"],
    ("playfair display", "bold"): ["PlayfairDisplay-Variable.ttf", "PlayfairDisplay[wght].ttf", "BeVietnamPro-Bold.ttf"],
    ("playfair display", "regular"): ["PlayfairDisplay-Variable.ttf", "PlayfairDisplay[wght].ttf", "BeVietnamPro-Bold.ttf"],
    ("svn-dancing script", "regular"): ["SVN-Dancing script.ttf", "TF-Whispers-xsaha0.ttf", "GreatVibes-Regular.ttf"],
    ("svn-dancing script", "bold"): ["SVN-Dancing script.ttf", "SVN-Mercury Script Bold.otf", "BeVietnamPro-BoldItalic.ttf"],
    ("bebas neue", "regular"): ["BebasNeue-Regular.ttf", "Bebas-Regular.otf", "Montserrat-Black.otf"],
    ("anton", "regular"): ["Anton-Regular.ttf", "Montserrat-Black.otf"],
    ("inter", "extrabold"): ["Inter-ExtraBold.ttf", "Inter[opsz,wght].ttf", "BeVietnamPro-ExtraBold.ttf"],
    ("inter", "bold"): ["Inter-ExtraBold.ttf", "Inter[opsz,wght].ttf", "BeVietnamPro-Bold.ttf"],
    ("inter", "regular"): ["Inter-Medium.ttf", "Inter[opsz,wght].ttf", "BeVietnamPro-Bold.ttf"],
    ("sf pro display", "black"): ["SF-Pro-Display-Black.otf", "Montserrat-Black.otf"],
    ("sf pro display", "bold"): ["SF-Pro-Display-Bold.otf", "BeVietnamPro-Bold.ttf"],
    ("sf mono", "bold"): ["LigaSFMonoNerdFont-Bold.otf", "DejaVuSansMono-Bold.ttf", "BeVietnamPro-Bold.ttf"],
    ("sf mono", "medium"): ["LigaSFMonoNerdFont-Medium.otf", "DejaVuSansMono.ttf", "BeVietnamPro-Bold.ttf"],
    ("jetbrains mono", "bold"): ["LigaSFMonoNerdFont-Bold.otf", "DejaVuSansMono-Bold.ttf", "BeVietnamPro-Bold.ttf"],
    ("dejavu sans mono", "bold"): ["DejaVuSansMono-Bold.ttf", "BeVietnamPro-Bold.ttf"],
}


# ---------------------------------------------------------------------------
# `v5.2` Semantic 6-Hue Palette & Inline Dual-Hue Token Markup
# ---------------------------------------------------------------------------

class SemanticHue(str):
    """
    String-compatible `#RRGGBB` semantic hue value (`c == "#FACC15"`, `isinstance(c, str) == True`)
    that ALSO exposes `.hex`, `.rgb`, `.roles`, `.desc` attributes and dict-style `c["rgb"]` / `c.get("rgb")`!
    """

    rgb: tuple[int, int, int]
    roles: tuple[str, ...]
    desc: str

    def __new__(
        cls,
        hex_code: str,
        rgb: tuple[int, int, int],
        roles: Sequence[str] = (),
        desc: str = "",
    ) -> "SemanticHue":
        obj = super().__new__(cls, hex_code.upper())
        obj.rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        obj.roles = tuple(str(r) for r in roles)
        obj.desc = str(desc)
        return obj

    @property
    def hex(self) -> str:
        return str(self)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key == "hex":
                return str(self)
            if key == "rgb":
                return self.rgb
            if key == "roles":
                return self.roles
            if key == "desc":
                return self.desc
            raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in ("hex", "rgb", "roles", "desc"):
            return self[key]
        return default


SEMANTIC_MULTI_HUE_PALETTE: dict[str, SemanticHue] = {
    "prestige_gold": SemanticHue(
        "#FACC15",
        (250, 204, 21),
        roles=("hook", "brand", "signature", "identity", "highlight", "authority"),
        desc="Brand / Hook / Signature",
    ),
    "alert_coral": SemanticHue(
        "#FF4D5E",
        (255, 77, 94),
        roles=("pain", "defect", "myth", "warning", "error", "problem", "conflict"),
        desc="Pain / Defect / Myth / Warning",
    ),
    "lock_mint": SemanticHue(
        "#2DD4BF",
        (45, 212, 191),
        roles=("precision", "solution", "lock", "verification", "step", "proof", "framework"),
        desc="Precision / Solution / Lock / Verification",
    ),
    "cinema_cyan": SemanticHue(
        "#38BDF8",
        (56, 189, 248),
        roles=("tech", "ai", "camera", "specs", "data", "metric", "system"),
        desc="Tech / AI / Camera / Specs (60fps)",
    ),
    "studio_violet": SemanticHue(
        "#C084FC",
        (192, 132, 252),
        roles=("creative", "light", "studio", "insight", "emotion", "story", "art"),
        desc="Creative / Studio Light / Insight",
    ),
    "warm_peach": SemanticHue(
        "#FB923C",
        (251, 146, 60),
        roles=("warmth", "craft", "confessional", "human", "creative_alt"),
        desc="Warm Studio Peach Alias / Creative Accent",
    ),
    "action_lime": SemanticHue(
        "#4ADE80",
        (74, 222, 128),
        roles=("cta", "gift", "conversion", "action", "growth", "result", "outro"),
        desc="CTA / Gift / Conversion",
    ),
    "ivory_white": SemanticHue(
        "#F8FAFC",
        (248, 250, 252),
        roles=("neutral", "base", "lead", "quiet", "bridge"),
        desc="Clean neutral base",
    ),
}

_PRIMARY_6_HUE_KEYS: tuple[str, ...] = (
    "prestige_gold",
    "alert_coral",
    "lock_mint",
    "cinema_cyan",
    "studio_violet",
    "action_lime",
)

_ARCHETYPE_HUE_ROTATIONS: dict[str, tuple[str, ...]] = {
    "dviet_vietanh_zdepth_master": ("prestige_gold", "lock_mint", "alert_coral", "cinema_cyan", "studio_violet", "action_lime"),
    "kinetic_tech_architect": ("cinema_cyan", "lock_mint", "prestige_gold", "alert_coral", "action_lime", "studio_violet"),
    "minimal_intellectual": ("lock_mint", "prestige_gold", "cinema_cyan", "studio_violet", "alert_coral", "action_lime"),
    "story_confessional": ("prestige_gold", "warm_peach", "studio_violet", "lock_mint", "alert_coral", "cinema_cyan"),
    "luxury_editorial": ("prestige_gold", "studio_violet", "lock_mint", "warm_peach", "cinema_cyan", "action_lime"),
    "high_velocity_punch": ("alert_coral", "prestige_gold", "action_lime", "cinema_cyan", "lock_mint", "studio_violet"),
}

_COMPLEMENT_HUE_MAP: dict[str, str] = {
    "prestige_gold": "lock_mint",
    "alert_coral": "cinema_cyan",
    "lock_mint": "prestige_gold",
    "cinema_cyan": "prestige_gold",
    "studio_violet": "lock_mint",
    "warm_peach": "cinema_cyan",
    "action_lime": "prestige_gold",
    "ivory_white": "lock_mint",
}

INLINE_COLOR_SHORT_MAP: dict[str, str] = {
    "gold": "#FACC15",
    "yellow": "#FACC15",
    "amber": "#FACC15",
    "prestige_gold": "#FACC15",
    "coral": "#FF4D5E",
    "red": "#FF4D5E",
    "crimson": "#FF4D5E",
    "rose": "#FF4D5E",
    "alert_coral": "#FF4D5E",
    "mint": "#2DD4BF",
    "emerald": "#2DD4BF",
    "teal": "#2DD4BF",
    "lock_mint": "#2DD4BF",
    "cyan": "#38BDF8",
    "blue": "#38BDF8",
    "sky": "#38BDF8",
    "cinema_cyan": "#38BDF8",
    "violet": "#C084FC",
    "purple": "#C084FC",
    "magenta": "#C084FC",
    "studio_violet": "#C084FC",
    "peach": "#FB923C",
    "orange": "#FB923C",
    "warm_peach": "#FB923C",
    "lime": "#4ADE80",
    "green": "#4ADE80",
    "action_lime": "#4ADE80",
    "emerald_7707": "#2EE86E",
    "amber_7706": "#F5B932",
    "violet_7693": "#A855F7",
    "cyan_7688": "#38BDF8",
    "act1_amber_gold": "#F5C451",
    "act2_crimson_coral": "#FF4D5E",
    "act3a_emerald_mint": "#34D399",
    "act3b_optical_ice_cyan": "#7DD3FC",
    "dental_porcelain_ice": "#7DD3FC",
    "nail_blush_champagne": "#F9A8D4",
    "skincare_pearl_rose": "#FDA4AF",
    "pain": "#FF4D5E",
    "ink_dark": "#111827",
    "whisper_cream": "#E8D98C",
    "white": "#F8FAFC",
    "fafafa": "#FAFAFA",
    "ivory": "#F8FAFC",
    "ivory_white": "#F8FAFC",
}

# ---------------------------------------------------------------------------
# `v7.0` `Player 3` Air-Cushion Bezier (`Video #08`, `f_01176..f_01195`) &
# `SEMANTIC_4ACT_JEWEL_PALETTES` (`#FAFAFA` Base + 1 Jewel Accent per Act + CRI-100 Industry Skins)
# ---------------------------------------------------------------------------

PLAYER3_AIR_CUSHION_CP: tuple[float, float, float, float] = (0.05, 0.92, 0.12, 1.00)


def _solve_cubic_bezier_1d(u: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Safeguarded Newton-Raphson + bisection solver for parametric 2D cubic Bezier (< 1e-12 precision)."""
    uc = float(u)
    if uc <= 0.0:
        return 0.0
    if uc >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    s = uc
    for _ in range(14):
        inv = 1.0 - s
        x = 3.0 * inv * inv * s * x1 + 3.0 * inv * s * s * x2 + s * s * s - uc
        if abs(x) < 1e-12:
            break
        if x < 0.0:
            lo = s
        else:
            hi = s
        dx = 3.0 * inv * inv * x1 + 6.0 * inv * s * (x2 - x1) + 3.0 * s * s * (1.0 - x2)
        if dx > 1e-9:
            s_next = s - x / dx
            s = s_next if (lo < s_next < hi) else 0.5 * (lo + hi)
        else:
            s = 0.5 * (lo + hi)
    inv = 1.0 - s
    return 3.0 * inv * inv * s * y1 + 3.0 * inv * s * s * y2 + s * s * s


def player3_air_cushion_bezier(u: float | Sequence[float] | Any) -> float | list[float] | Any:
    """
    Exact `v7.0` **`Player 3` Air-Cushion Bezier** measured from `f_01176..f_01195` of Video `#08`:
      `cubic-bezier(0.05, 0.92, 0.12, 1.00)`
      - Covers `> 50%` of total travel within the first `2 frames` (`u ≈ 0.10 -> y ≈ 0.71`),
      - Cushions across the final `10 frames` (`u = 0.50..1.00 -> y = 0.945..1.000`) at `< 1px/frame`!
      - Accepts scalar `float`/`int`, Python sequences (`list`/`tuple`), or `numpy.ndarray`.
    """
    x1, y1, x2, y2 = PLAYER3_AIR_CUSHION_CP
    if isinstance(u, (int, float)) and not isinstance(u, bool):
        return _solve_cubic_bezier_1d(float(u), x1, y1, x2, y2)
    # Support numpy ndarray transparently without forcing top-level import overhead
    if hasattr(u, "shape") and hasattr(u, "dtype"):
        import numpy as _np  # local fast reference

        arr = _np.asarray(u, dtype=_np.float64)
        flat = [_solve_cubic_bezier_1d(float(v), x1, y1, x2, y2) for v in arr.ravel()]
        return _np.asarray(flat, dtype=_np.float64).reshape(arr.shape)
    if isinstance(u, (list, tuple)):
        return [_solve_cubic_bezier_1d(float(v), x1, y1, x2, y2) for v in u]
    return _solve_cubic_bezier_1d(float(u), x1, y1, x2, y2)


def build_player3_air_cushion_keyframes(
    start_val: float | Sequence[float],
    end_val: float | Sequence[float],
    entrance_dur_s: float = 0.32,
    total_dur_s: float | None = None,
    fps: int = 60,
    sample_knots: Sequence[float] = (0.0, 2.0 / 19.0, 5.0 / 19.0, 9.0 / 19.0, 14.0 / 19.0, 1.0),
) -> list[list[Any]]:
    """Sample multi-knot FilmCraft keyframes faithfully reproducing `player3_air_cushion_bezier(u)`."""
    ent_s = max(round(3 / fps, 6), snap_time(entrance_dur_s, fps))
    tot_s = max(ent_s, snap_time(total_dur_s if total_dur_s is not None else ent_s, fps))
    is_vec = isinstance(start_val, (list, tuple)) and isinstance(end_val, (list, tuple))
    raw: list[list[Any]] = []
    for idx_k, u_k in enumerate(sample_knots):
        t_k = snap_time(float(u_k) * ent_s, fps)
        y_k = float(player3_air_cushion_bezier(float(u_k)))
        interp = "easeOut" if idx_k < len(sample_knots) - 1 else ("linear" if tot_s > ent_s else "easeIn")
        if is_vec:
            v_k: Any = [
                round(float(start_val[0]) + (float(end_val[0]) - float(start_val[0])) * y_k, 2),
                round(float(start_val[1]) + (float(end_val[1]) - float(start_val[1])) * y_k, 2),
            ]
        else:
            v_k = round(float(start_val) + (float(end_val) - float(start_val)) * y_k, 2)
        raw.append([t_k, v_k, interp])
    if tot_s > ent_s + (1.0 / fps):
        end_copy = [round(float(end_val[0]), 2), round(float(end_val[1]), 2)] if is_vec else round(float(end_val), 2)
        raw.append([tot_s, end_copy, "linear"])
    return _strict_kf(raw, tot_s, fps)


SEMANTIC_4ACT_JEWEL_PALETTES: dict[str, dict[str, Any]] = {
    "act1_amber_gold": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#F5C451",
        "primary_hex": "#F5C451",
        "primary_dark_ink": "#92400E",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#120F0A",
        "light_bg": "#FAF7F0",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#1C1917",
        "ui_secondary": "#7DD3FC",
        "act": "act1",
        "role": "hook_thesis_authority",
        "cri_target": 100,
        "desc": "Act 1 Hook / Core Thesis — Champagne Amber Gold #F5C451 on #FAFAFA",
    },
    "act2_crimson_coral": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#FF4D5E",
        "primary_hex": "#FF4D5E",
        "primary_dark_ink": "#9F1239",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#140A0D",
        "light_bg": "#FFF5F6",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#1F1216",
        "ui_secondary": "#F5C451",
        "act": "act2",
        "role": "pain_diagnostic_myth",
        "cri_target": 100,
        "desc": "Act 2 Pain / Diagnostic Friction / Myth — Jewel Crimson Coral #FF4D5E on #FAFAFA",
    },
    "act3a_emerald_mint": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#34D399",
        "primary_hex": "#34D399",
        "primary_dark_ink": "#065F46",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#081612",
        "light_bg": "#F0FDF7",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#0F172A",
        "ui_secondary": "#7DD3FC",
        "act": "act3a",
        "role": "solution_precision_proof",
        "cri_target": 100,
        "desc": "Act 3A Solution / Precision / Clinical Proof — Jewel Emerald Mint #34D399 on #FAFAFA",
    },
    "act3b_optical_ice_cyan": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#7DD3FC",
        "primary_hex": "#7DD3FC",
        "primary_dark_ink": "#0369A1",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#0A1017",
        "light_bg": "#F0F9FF",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#0F172A",
        "ui_secondary": "#34D399",
        "act": "act3b",
        "role": "system_optics_payoff_cta",
        "cri_target": 100,
        "desc": "Act 3B Optical System / Payoff / CTA — Optical Ice Cyan #7DD3FC on #FAFAFA",
    },
    "dental_porcelain_ice": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#7DD3FC",
        "primary_hex": "#7DD3FC",
        "primary_dark_ink": "#0369A1",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#0B1118",
        "light_bg": "#F8FAFC",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#0F172A",
        "ui_secondary": "#34D399",
        "industry_skin": "dental_clinic",
        "cri_target": 100,
        "forbid_warm_film_burn": True,
        "forbid_yellow_lut": True,
        "act_accents": {
            "act1": "#7DD3FC",
            "act2": "#FF4D5E",
            "act3a": "#34D399",
            "act3b": "#BAE6FD",
        },
        "desc": "CRI-100 Dental Clinic — Porcelain White #FAFAFA & Optical Ice #7DD3FC (0 yellow stain near enamel)",
    },
    "nail_blush_champagne": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#F9A8D4",
        "primary_hex": "#F9A8D4",
        "primary_dark_ink": "#9D174D",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#160F13",
        "light_bg": "#FDF8FA",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#3F1D2B",
        "ui_secondary": "#F5C451",
        "industry_skin": "nail_hair_salon",
        "cri_target": 100,
        "forbid_warm_film_burn": True,
        "forbid_yellow_lut": True,
        "act_accents": {
            "act1": "#F5C451",
            "act2": "#FF4D5E",
            "act3a": "#F9A8D4",
            "act3b": "#FDE68A",
        },
        "desc": "CRI-100 Nail & Hair Salon — Silk Blush #F9A8D4 & Champagne Gold #F5C451 on #FAFAFA",
    },
    "skincare_pearl_rose": {
        "base_hex": "#FAFAFA",
        "accent_hex": "#FDA4AF",
        "primary_hex": "#FDA4AF",
        "primary_dark_ink": "#9F1239",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#141013",
        "light_bg": "#FFF9FA",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#3B1822",
        "ui_secondary": "#34D399",
        "industry_skin": "luxury_skincare",
        "cri_target": 100,
        "forbid_warm_film_burn": True,
        "forbid_yellow_lut": True,
        "act_accents": {
            "act1": "#FDA4AF",
            "act2": "#FF4D5E",
            "act3a": "#34D399",
            "act3b": "#7DD3FC",
        },
        "desc": "CRI-100 Luxury Skincare — Pearl #FAFAFA, Rose Quartz #FDA4AF & Botanical Mint #34D399",
    },
}


def resolve_4act_jewel_palette(
    palette_or_act: str = "act1_amber_gold",
    act_key: str | None = None,
) -> dict[str, Any]:
    """Resolve a `SEMANTIC_4ACT_JEWEL_PALETTES` entry by exact key, act alias (`act1..act3b`), or `industry_skin`."""
    raw = str(palette_or_act or "act1_amber_gold").strip().lower()
    alias = {
        "act1": "act1_amber_gold",
        "act2": "act2_crimson_coral",
        "act3": "act3a_emerald_mint",
        "act3a": "act3a_emerald_mint",
        "act3b": "act3b_optical_ice_cyan",
        "act4": "act3b_optical_ice_cyan",
        "dental": "dental_porcelain_ice",
        "dental_clinic": "dental_porcelain_ice",
        "nail": "nail_blush_champagne",
        "nail_hair_salon": "nail_blush_champagne",
        "skincare": "skincare_pearl_rose",
        "luxury_skincare": "skincare_pearl_rose",
    }
    key = alias.get(raw, raw)
    if key not in SEMANTIC_4ACT_JEWEL_PALETTES:
        raise ValueError(
            f"Unknown 4-Act Jewel Palette={palette_or_act!r}. Valid: {list(SEMANTIC_4ACT_JEWEL_PALETTES)}"
        )
    pal = dict(SEMANTIC_4ACT_JEWEL_PALETTES[key])
    if act_key and isinstance(pal.get("act_accents"), dict):
        ak = alias.get(str(act_key).strip().lower(), str(act_key).strip().lower())
        short_ak = ak.split("_")[0]
        if short_ak in pal["act_accents"]:
            pal["active_act_accent_hex"] = pal["act_accents"][short_ak]
    return pal

# ---------------------------------------------------------------------------
# `v6.0` Cohesive `@__dviet` Color-World System (`1 Primary + 0–1 Pain + Light/Dark Polarity`)
# ---------------------------------------------------------------------------

DVIET_COLOR_WORLDS: dict[str, dict[str, str]] = {
    "emerald_cream_7707": {
        "primary_hex": "#2EE86E",
        "primary_dark_ink": "#166534",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#081C15",
        "light_bg": "#EEF4EA",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#111827",
        "ui_secondary": "#8B5CF6",
    },
    "amber_cinema_7706": {
        "primary_hex": "#F5B932",
        "primary_dark_ink": "#92400E",
        "pain_hex": "#FF4D5E",
        "dark_bg": "#120E0A",
        "light_bg": "#FAF6EC",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#1C1917",
        "ui_secondary": "#38BDF8",
    },
    "violet_aurora_7693": {
        "primary_hex": "#A855F7",
        "primary_dark_ink": "#4C1D95",
        "pain_hex": "#F43F5E",
        "dark_bg": "#120924",
        "light_bg": "#F5F3FF",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#1E1B4B",
        "ui_secondary": "#C4B5FD",
    },
    "obsidian_cyan_7688": {
        "primary_hex": "#38BDF8",
        "primary_dark_ink": "#0369A1",
        "pain_hex": "#F43F5E",
        "dark_bg": "#0B0D11",
        "light_bg": "#F1F5F9",
        "text_on_dark": "#FAFAFA",
        "text_on_light": "#0F172A",
        "ui_secondary": "#FACC15",
    },
}

_COLOR_WORLD_KEYS: tuple[str, ...] = tuple(DVIET_COLOR_WORLDS.keys())
_PAIN_ROLES: frozenset[str] = frozenset({
    "pain", "conflict", "defect", "myth", "warning", "error", "problem", "mistake", "bad",
})
_QUIET_ROLES: frozenset[str] = frozenset({
    "quiet", "neutral", "whisper", "caption_only", "breathing",
})
_UI_SECONDARY_ROLES: frozenset[str] = frozenset({
    "ui", "ui_secondary", "hud", "badge", "spec_pill",
})


def _resolve_color_world(world_id: str | None = None, video_seed: int = 0) -> tuple[str, dict[str, str]]:
    """Resolve `world_id` across `DVIET_COLOR_WORLDS` AND `v7.0` `SEMANTIC_4ACT_JEWEL_PALETTES`."""
    if world_id is None or not str(world_id).strip():
        chosen = _COLOR_WORLD_KEYS[int(video_seed) % len(_COLOR_WORLD_KEYS)]
        return chosen, DVIET_COLOR_WORLDS[chosen]
    raw = str(world_id).strip().lower()
    if raw in DVIET_COLOR_WORLDS:
        return raw, DVIET_COLOR_WORLDS[raw]
    if raw in SEMANTIC_4ACT_JEWEL_PALETTES:
        jp = SEMANTIC_4ACT_JEWEL_PALETTES[raw]
        return raw, {
            "primary_hex": str(jp["primary_hex"]),
            "primary_dark_ink": str(jp["primary_dark_ink"]),
            "pain_hex": str(jp["pain_hex"]),
            "dark_bg": str(jp["dark_bg"]),
            "light_bg": str(jp["light_bg"]),
            "text_on_dark": str(jp["text_on_dark"]),
            "text_on_light": str(jp["text_on_light"]),
            "ui_secondary": str(jp["ui_secondary"]),
        }
    alias_map = {
        "emerald": "emerald_cream_7707",
        "7707": "emerald_cream_7707",
        "emerald_cream": "emerald_cream_7707",
        "amber": "amber_cinema_7706",
        "7706": "amber_cinema_7706",
        "amber_cinema": "amber_cinema_7706",
        "violet": "violet_aurora_7693",
        "7693": "violet_aurora_7693",
        "violet_aurora": "violet_aurora_7693",
        "cyan": "obsidian_cyan_7688",
        "obsidian": "obsidian_cyan_7688",
        "7688": "obsidian_cyan_7688",
        "obsidian_cyan": "obsidian_cyan_7688",
        "dental": "dental_porcelain_ice",
        "dental_clinic": "dental_porcelain_ice",
        "nail": "nail_blush_champagne",
        "nail_hair_salon": "nail_blush_champagne",
        "skincare": "skincare_pearl_rose",
        "luxury_skincare": "skincare_pearl_rose",
        "act1": "act1_amber_gold",
        "act2": "act2_crimson_coral",
        "act3a": "act3a_emerald_mint",
        "act3b": "act3b_optical_ice_cyan",
    }
    if raw in alias_map:
        mapped = alias_map[raw]
        return _resolve_color_world(mapped, video_seed=video_seed)
    for k in _COLOR_WORLD_KEYS:
        if raw in k:
            return k, DVIET_COLOR_WORLDS[k]
    raise ValueError(
        f"Unknown color world={world_id!r}. Valid: {list(_COLOR_WORLD_KEYS) + list(SEMANTIC_4ACT_JEWEL_PALETTES)}"
    )


def plan_color_world_for_video(
    beats: Sequence[dict[str, Any] | str],
    world_id: str | None = None,
    video_seed: int = 0,
) -> dict[str, Any]:
    """
    `v6.0` Cohesive `@__dviet` Color-World Planner (Fixes Rainbow Soup):
      - Selects **1 Cohesive Color World** for the entire video (rotating `world_id` *between* videos
        via `video_seed` when `world_id is None`).
      - Assigns `primary_hex` (or `primary_dark_ink` on `polarity="light"` beats!) to `75–90%` (up to `100%`
        if zero pain/UI beats exist) of accented beats.
      - Restricts `pain_hex` STRICTLY to explicit conflict/defect/myth beats (`0–25%` of accented beats).
      - Keeps `>= 80%+` of supporting words in neutral `#FAFAFA` (`text_on_dark`) / `#111827` (`text_on_light`)!
    """
    chosen_id, world = _resolve_color_world(world_id=world_id, video_seed=video_seed)
    norm_beats: list[dict[str, Any]] = []
    for b in beats:
        norm_beats.append(dict(b) if isinstance(b, dict) else {"text": str(b)})

    n = len(norm_beats)
    if n == 0:
        return {
            "world_id": chosen_id,
            "world": dict(world),
            "video_seed": int(video_seed),
            **world,
            "stats": {
                "total_beats": 0,
                "accented_beats": 0,
                "primary_accent_beats": 0,
                "pain_accent_beats": 0,
                "ui_secondary_beats": 0,
                "primary_accent_ratio": 1.0,
                "pain_accent_ratio": 0.0,
                "supporting_neutral_ratio": 1.0,
            },
            "beats": [],
        }

    # Step 1: Identify accented vs quiet beats, and rank explicit conflict/pain & UI-tag candidates
    is_accent_flags: list[bool] = []
    pain_scores: list[tuple[int, int]] = []  # (priority_score, beat_idx)
    ui_candidates: list[int] = []

    for idx, bd in enumerate(norm_beats):
        role = unicodedata.normalize("NFC", str(bd.get("role") or bd.get("type") or "")).strip().lower()
        txt = unicodedata.normalize("NFC", str(bd.get("text") or bd.get("hero_text") or "")).strip().lower()
        explicit_acc = bd.get("is_accent")
        is_acc = (explicit_acc is not False) and (role not in _QUIET_ROLES)
        is_accent_flags.append(is_acc)
        if not is_acc:
            continue

        if bd.get("is_pain") is True or role in _PAIN_ROLES:
            pain_scores.append((2, idx))
        elif not role and any(kw in txt for kw in ("sai lầm", "thảm họa", "biến dạng", "lỗi nặng", "vỡ vụn", "đừng bao giờ")):
            pain_scores.append((1, idx))
        elif role in _UI_SECONDARY_ROLES:
            ui_candidates.append(idx)

    accented_count = sum(1 for f in is_accent_flags if f)
    # Hard cap: pain_hex <= 25% of accented beats so primary_hex >= 75%
    max_pain = math.floor(accented_count * 0.25) if accented_count >= 4 else (1 if (accented_count >= 2 and any(s == 2 for s, _ in pain_scores)) else 0)
    pain_scores.sort(key=lambda pair: (-pair[0], pair[1]))
    chosen_pain_indices = {idx for _sc, idx in pain_scores[:max_pain]}

    # Allow at most 10% ui_secondary beats ONLY if primary_hex still stays in 75-90%
    max_ui = max(0, min(len(ui_candidates), math.floor(accented_count * 0.10)))
    while max_ui > 0 and (accented_count - len(chosen_pain_indices) - max_ui) / max(1, accented_count) < 0.75:
        max_ui -= 1
    chosen_ui_indices = set(ui_candidates[:max_ui])

    planned_beats: list[dict[str, Any]] = []
    primary_count = 0
    pain_count = 0
    ui_count = 0
    total_sup_words = 0
    neutral_sup_words = 0

    for idx, bd in enumerate(norm_beats):
        pol_raw = str(bd.get("polarity") or bd.get("bg_polarity") or ("light" if bd.get("is_light_bg") else "dark")).strip().lower()
        polarity = "light" if pol_raw == "light" else "dark"
        bg_hex = world["light_bg"] if polarity == "light" else world["dark_bg"]
        neutral_text_hex = world["text_on_light"] if polarity == "light" else world["text_on_dark"]
        prim_for_pol = world["primary_dark_ink"] if polarity == "light" else world["primary_hex"]

        if not is_accent_flags[idx]:
            accent_role = "neutral"
            hero_hex = neutral_text_hex
        elif idx in chosen_pain_indices:
            accent_role = "pain"
            hero_hex = world["pain_hex"]
            pain_count += 1
        elif idx in chosen_ui_indices:
            accent_role = "ui_secondary"
            hero_hex = world["ui_secondary"]
            ui_count += 1
        else:
            accent_role = "primary"
            hero_hex = prim_for_pol
            primary_count += 1

        # Supporting words budget: >= 80%+ neutral (#FAFAFA on dark / #111827 on light)
        sup_str = str(bd.get("supporting_text") or bd.get("lead_text") or bd.get("text") or "")
        w_cnt = max(5, len(strip_inline_color_tags(sup_str).split()))
        acc_w = 1 if (accent_role in ("primary", "pain") and w_cnt >= 6) else 0
        total_sup_words += w_cnt
        neutral_sup_words += (w_cnt - acc_w)

        planned_beats.append({
            **bd,
            "beat_index": idx,
            "world_id": chosen_id,
            "polarity": polarity,
            "bg_hex": bg_hex,
            "accent_role": accent_role,
            "hero_hex": hero_hex,
            "lead_hex": neutral_text_hex,
            "supporting_text_hex": neutral_text_hex,
            "primary_hex_resolved": prim_for_pol,
            "pain_hex": world["pain_hex"],
            "ui_secondary_hex": world["ui_secondary"],
            "max_accent_words": acc_w,
        })

    denom = max(1, accented_count)
    primary_ratio = primary_count / float(denom) if accented_count > 0 else 1.0
    pain_ratio = pain_count / float(denom) if accented_count > 0 else 0.0
    sup_neutral_ratio = neutral_sup_words / float(max(1, total_sup_words))

    return {
        "world_id": chosen_id,
        "world": dict(world),
        "video_seed": int(video_seed),
        **world,
        "stats": {
            "total_beats": n,
            "accented_beats": accented_count,
            "primary_accent_beats": primary_count,
            "pain_accent_beats": pain_count,
            "ui_secondary_beats": ui_count,
            "primary_accent_ratio": round(primary_ratio, 4),
            "pain_accent_ratio": round(pain_ratio, 4),
            "supporting_neutral_ratio": round(sup_neutral_ratio, 4),
        },
        "beats": planned_beats,
    }

_INLINE_COLOR_TAG_RE = re.compile(r"\[([#A-Za-z0-9_-]+):([^\[\]]+)\]")


def resolve_semantic_color(color_or_alias: str | None, default_color: str = "#F8FAFC") -> str:
    """Resolve short color tag (`mint`, `gold`, `coral`, `cyan`, `violet`, `peach`, `lime`, `white`) or `#RRGGBB` to uppercase `#RRGGBB`."""
    if not color_or_alias:
        return str(default_color).upper()
    s = str(color_or_alias).strip()
    if HEX6_RE.match(s):
        return s.upper()
    low = s.lower()
    if low in INLINE_COLOR_SHORT_MAP:
        return INLINE_COLOR_SHORT_MAP[low]
    if low in SEMANTIC_MULTI_HUE_PALETTE:
        return str(SEMANTIC_MULTI_HUE_PALETTE[low])
    return str(default_color).upper()


def parse_inline_color_spans(markup_text: str, default_color: str = "#F8FAFC") -> list[tuple[str, str]]:
    """
    Parse inline color tags like:
      - `"luôn phải [mint:khóa] [gold:kết cấu]"` -> `[("luôn phải", "#F8FAFC"), ("khóa", "#2DD4BF"), ("kết cấu", "#FACC15")]`
      - `"để AI [#FF4D5E:không] biến dạng"` -> `[("để AI", "#F8FAFC"), ("không", "#FF4D5E"), ("biến dạng", "#F8FAFC")]`
    Unknown bracket syntax (e.g. `[60FPS]`) is preserved untouched as plain text.
    """
    s = unicodedata.normalize("NFC", str(markup_text or ""))
    def_hex = resolve_semantic_color(default_color, "#F8FAFC")
    if not s.strip():
        return []

    raw_pieces: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE_COLOR_TAG_RE.finditer(s):
        if m.start() > pos:
            raw_pieces.append((s[pos : m.start()], def_hex))
        tag_name = m.group(1).strip()
        inner_txt = m.group(2)
        if HEX6_RE.match(tag_name) or tag_name.lower() in INLINE_COLOR_SHORT_MAP:
            raw_pieces.append((inner_txt, resolve_semantic_color(tag_name, def_hex)))
        else:
            raw_pieces.append((m.group(0), def_hex))
        pos = m.end()
    if pos < len(s):
        raw_pieces.append((s[pos:], def_hex))

    spans: list[tuple[str, str]] = []
    for seg_txt, seg_col in raw_pieces:
        cleaned = clean_display_text(seg_txt).strip()
        if not cleaned:
            continue
        if spans and spans[-1][1] == seg_col and not cleaned[0] in _TRAIL_PUNCT:
            spans[-1] = (f"{spans[-1][0]} {cleaned}", seg_col)
        elif spans and cleaned in tuple(_TRAIL_PUNCT):
            spans[-1] = (f"{spans[-1][0]}{cleaned}", spans[-1][1])
        else:
            spans.append((cleaned, seg_col))
    return spans


def strip_inline_color_tags(text: str) -> str:
    """Strip inline `[color:word]` markup tags into clean NFC display text for plain-text fallbacks."""
    s = unicodedata.normalize("NFC", str(text or ""))
    if not s.strip():
        return ""

    def _sub(m: re.Match) -> str:
        tag_name = m.group(1).strip()
        if HEX6_RE.match(tag_name) or tag_name.lower() in INLINE_COLOR_SHORT_MAP:
            return m.group(2)
        return m.group(0)

    stripped = _INLINE_COLOR_TAG_RE.sub(_sub, s)
    return clean_display_text(stripped).strip()


def _infer_role_preferred_hues(role: str, text_hint: str, base_order: Sequence[str]) -> list[str]:
    r = unicodedata.normalize("NFC", str(role or "")).strip().lower()
    txt = unicodedata.normalize("NFC", str(text_hint or "")).strip().lower()
    prefs: list[str] = []

    role_direct = {
        "hook": "prestige_gold",
        "brand": "prestige_gold",
        "signature": "prestige_gold",
        "identity": "prestige_gold",
        "pain": "alert_coral",
        "defect": "alert_coral",
        "myth": "alert_coral",
        "warning": "alert_coral",
        "error": "alert_coral",
        "problem": "alert_coral",
        "solution": "lock_mint",
        "precision": "lock_mint",
        "lock": "lock_mint",
        "verification": "lock_mint",
        "proof": "lock_mint",
        "step": "lock_mint",
        "tech": "cinema_cyan",
        "ai": "cinema_cyan",
        "camera": "cinema_cyan",
        "specs": "cinema_cyan",
        "data": "cinema_cyan",
        "metric": "cinema_cyan",
        "light": "studio_violet",
        "creative": "studio_violet",
        "studio": "studio_violet",
        "insight": "studio_violet",
        "emotion": "studio_violet",
        "warmth": "warm_peach",
        "story": "warm_peach",
        "cta": "action_lime",
        "gift": "action_lime",
        "conversion": "action_lime",
        "action": "action_lime",
        "outro": "action_lime",
    }
    if r in role_direct:
        prefs.append(role_direct[r])
    else:
        for h_key, h_obj in SEMANTIC_MULTI_HUE_PALETTE.items():
            if h_key == "ivory_white":
                continue
            if any(tok in r for tok in h_obj.roles):
                prefs.append(h_key)

    # Secondary semantic cues from beat text if role was generic/missing
    if not prefs and txt:
        tv = load_text_vi()
        toks = [t.strip(_TRAIL_PUNCT + _OPEN_AFFX + _CLOSE_AFFX) for t in txt.split()]
        if any(t in tv["warn"] for t in toks) or any(k in txt for k in ("lỗi", "sai", "méo", "biến dạng", "đừng", "chán", "mất")):
            prefs.append("alert_coral")
        elif any(t in tv["cta_verbs"] for t in toks) or any(k in txt for k in ("ngay", "nhận", "tải", "bấm", "comment", "follow")):
            prefs.append("action_lime")
        elif any(k in txt for k in ("60fps", "ai", "camera", "gpu", "code", "z-depth", "render")):
            prefs.append("cinema_cyan")
        elif any(k in txt for k in ("ánh sáng", "cảm xúc", "nghệ thuật", "studio", "màu")):
            prefs.append("studio_violet")
        elif any(k in txt for k in ("khóa", "chuẩn", "chính xác", "bước", "cấu trúc")):
            prefs.append("lock_mint")

    for hk in base_order:
        if hk not in prefs:
            prefs.append(hk)
    for hk in _PRIMARY_6_HUE_KEYS:
        if hk not in prefs:
            prefs.append(hk)
    return prefs


def plan_semantic_hue_sequence(
    beats: Sequence[dict[str, Any]],
    archetype: str = "dviet_vietanh_zdepth_master",
    seed: int = 0,
) -> list[dict[str, Any]]:
    """
    Assign `(hero_hue_key, hero_hex, secondary_accent_hex)` across `beats` with HARD invariants:
      1. ZERO two consecutive beats share the same `hero_hex`.
      2. When `len(beats) >= 4`, NO single non-white hue exceeds `35%` of beats (`count <= floor(N * 0.35)`).
    """
    n = len(beats)
    if n == 0:
        return []

    arch_key = str(archetype or "dviet_vietanh_zdepth_master").strip().lower()
    raw_order = list(_ARCHETYPE_HUE_ROTATIONS.get(arch_key, _PRIMARY_6_HUE_KEYS))
    shift = int(seed) % len(raw_order)
    rotated_order = raw_order[shift:] + raw_order[:shift]

    max_per_hue = max(1, math.floor(n * 0.35)) if n >= 4 else n
    # Build preference list per beat
    beat_prefs: list[list[str]] = []
    for idx, b in enumerate(beats):
        b_dict = b if isinstance(b, dict) else {"text": str(b)}
        local_rot = rotated_order[(idx % len(rotated_order)) :] + rotated_order[: (idx % len(rotated_order))]
        prefs = _infer_role_preferred_hues(
            str(b_dict.get("role") or b_dict.get("type") or ""),
            str(b_dict.get("text") or b_dict.get("hero_text") or ""),
            local_rot,
        )
        beat_prefs.append(prefs)

    chosen_keys: list[str] = []
    counts: dict[str, int] = {}

    def _backtrack(i: int) -> bool:
        if i == n:
            return True
        prev_hex = str(SEMANTIC_MULTI_HUE_PALETTE[chosen_keys[-1]]) if chosen_keys else None
        # Rank candidates: respect role preference first, tie-breaking toward least-used hues for balanced variety
        cands = beat_prefs[i]
        scored = sorted(
            enumerate(cands),
            key=lambda pair: (0 if pair[0] == 0 else 1, counts.get(pair[1], 0), pair[0]),
        )
        for _rank, h_key in scored:
            h_hex = str(SEMANTIC_MULTI_HUE_PALETTE[h_key])
            if prev_hex is not None and h_hex == prev_hex:
                continue
            if counts.get(h_key, 0) >= max_per_hue:
                continue
            chosen_keys.append(h_key)
            counts[h_key] = counts.get(h_key, 0) + 1
            if _backtrack(i + 1):
                return True
            counts[h_key] -= 1
            chosen_keys.pop()
        return False

    if not _backtrack(0):
        # Guaranteed fallback rotation (6 distinct hues easily satisfy consecutive != and <= 35%)
        chosen_keys = []
        counts = {}
        pool = list(_PRIMARY_6_HUE_KEYS)
        for i in range(n):
            prev_k = chosen_keys[-1] if chosen_keys else ""
            pick = next(
                (k for k in pool if k != prev_k and counts.get(k, 0) < max_per_hue),
                next(k for k in pool if k != prev_k),
            )
            chosen_keys.append(pick)
            counts[pick] = counts.get(pick, 0) + 1

    out: list[dict[str, Any]] = []
    for idx, (b, h_key) in enumerate(zip(beats, chosen_keys)):
        b_dict = dict(b) if isinstance(b, dict) else {"text": str(b)}
        h_obj = SEMANTIC_MULTI_HUE_PALETTE[h_key]
        sec_key = _COMPLEMENT_HUE_MAP.get(h_key, "lock_mint")
        if str(SEMANTIC_MULTI_HUE_PALETTE[sec_key]) == str(h_obj):
            sec_key = "cinema_cyan" if h_key != "cinema_cyan" else "prestige_gold"
        sec_obj = SEMANTIC_MULTI_HUE_PALETTE[sec_key]
        out.append({
            **b_dict,
            "beat_index": idx,
            "role": str(b_dict.get("role") or "beat"),
            "hero_hue_key": h_key,
            "hero_hex": str(h_obj),
            "hero_rgb": h_obj.rgb,
            "secondary_hue_key": sec_key,
            "secondary_accent_hex": str(sec_obj),
            "base_hex": str(SEMANTIC_MULTI_HUE_PALETTE["ivory_white"]),
        })
    return out


# ---------------------------------------------------------------------------
# Vietnamese Compound Lexicon (`data/text_vi.json`) & True Ink-Box Measurement
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_text_vi() -> dict[str, frozenset[str]]:
    """Load and cache `/data/text_vi.json` lexicon sets (`pairs`, `leads`, `trails`, `function`, `pronouns`, etc.)."""
    p = TEXT_VI_PATH
    if not p.is_file():
        return {
            "leads": frozenset(),
            "trails": frozenset(),
            "function": frozenset(),
            "pronouns": frozenset(),
            "warn": frozenset(),
            "quantity": frozenset(),
            "units": frozenset(),
            "cta_verbs": frozenset(),
            "pairs": frozenset(),
        }
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, frozenset[str]] = {}
    for key in ("leads", "trails", "function", "pronouns", "warn", "quantity", "units", "cta_verbs", "pairs"):
        items = raw.get(key) or []
        out[key] = frozenset(unicodedata.normalize("NFC", str(x)).strip().lower() for x in items if str(x).strip())
    return out


def _split_token_affixes(token: str) -> tuple[str, str, str]:
    """Split raw token into `(pre_open, core, post_punct_or_close)` in NFC."""
    s = unicodedata.normalize("NFC", str(token or "")).strip()
    if not s:
        return "", "", ""
    pre = s[: len(s) - len(s.lstrip(_OPEN_AFFX))]
    rest = s[len(pre) :]
    core = rest.rstrip(_TRAIL_PUNCT + _CLOSE_AFFX)
    post = rest[len(core) :]
    return pre, core, post


def _is_caps_or_num_core(core: str) -> bool:
    """True for number tokens (`8`, `15`, `90%`, `1,5x`), ALL-CAPS words (`TRIỆU`, `AI`, `OPA`), or uppercase tech tokens (`SKILL.md`)."""
    if not core:
        return False
    if _NUM_TOKEN_RE.fullmatch(core):
        return True
    if _CAPS_FILE_TOKEN_RE.fullmatch(core):
        return True
    alpha_count = sum(ch.isalpha() for ch in core)
    return alpha_count >= 2 and core.isupper()


def is_glued_pair(w1: str, w2: str) -> bool:
    """
    `True` when `w1` has no trailing punctuation AND:
      - `f"{low1} {low2}"` is in `text_vi["pairs"]` (1,199 adjudicated Vietnamese compounds), OR
      - both tokens are ALL-CAPS / number / tech-acronym tokens (e.g. `"8 SKILL.md"`, `"15 TRIỆU"`).
    """
    _pre1, core1, post1 = _split_token_affixes(w1)
    _pre2, core2, _post2 = _split_token_affixes(w2)
    if not core1 or not core2:
        return False
    if post1:
        return False
    tv = load_text_vi()
    low1, low2 = core1.lower(), core2.lower()
    if f"{low1} {low2}" in tv["pairs"]:
        return True
    return _is_caps_or_num_core(core1) and _is_caps_or_num_core(core2)


def can_split_after(tokens: Sequence[str], idx: int) -> bool:
    """
    Linguistic boundary check between `tokens[idx]` and `tokens[idx + 1]`:
      - Returns `True` if `idx >= len(tokens) - 1` (end of sequence) or `tokens[idx]` ends with clause/sentence punctuation.
      - Returns `False` if `is_glued_pair(tokens[idx], tokens[idx + 1])`,
        OR `low(tokens[idx])` is in `text_vi["leads"]` (68 forward-binding words),
        OR `low(tokens[idx + 1])` is in `text_vi["trails"]` (9 backward-binding particles).
    """
    n = len(tokens)
    if idx < 0:
        return False
    if idx >= n - 1:
        return True
    w1, w2 = str(tokens[idx]), str(tokens[idx + 1])
    _pre1, core1, post1 = _split_token_affixes(w1)
    _pre2, core2, _post2 = _split_token_affixes(w2)
    if not core1 or not core2:
        return True
    # Explicit punctuation on w1 ends the local syntactic phrase
    if any(c in (_TRAIL_PUNCT + _CLOSE_AFFX) for c in post1):
        return True
    if is_glued_pair(w1, w2):
        return False
    tv = load_text_vi()
    if core1.lower() in tv["leads"]:
        return False
    if core2.lower() in tv["trails"]:
        return False
    return True


@lru_cache(maxsize=128)
def _resolve_typo_font_path(font: str, style: str) -> str:
    fam_key = re.sub(r"\s+", " ", str(font or "Be Vietnam Pro").strip().lower())
    sty_key = re.sub(r"[\s_-]+", "", str(style or "Bold").strip().lower())

    candidates: list[str] = []
    if (fam_key, sty_key) in _FONT_FILE_MAP:
        candidates.extend(_FONT_FILE_MAP[(fam_key, sty_key)])
    # Fallback within same font family
    for (fk, sk), files in _FONT_FILE_MAP.items():
        if fk == fam_key and files:
            for fn in files:
                if fn not in candidates:
                    candidates.append(fn)
    # Universal Vietnamese-safe fallbacks
    for fn in ("BeVietnamPro-Bold.ttf", "BeVietnamPro-ExtraBold.ttf", "Montserrat-Bold.otf", "DejaVuSans-Bold.ttf"):
        if fn not in candidates:
            candidates.append(fn)

    wpb = _wpb()
    for fname in candidates:
        for fdir in (*wpb.env_font_dirs(), *FONT_SEARCH_DIRS):
            cand = fdir / fname
            if cand.is_file():
                return str(cand)
    for fname in candidates:  # v7.9.1: fontconfig knows the file under another folder
        hit = wpb.find_font_file(fname)
        if hit is not None:
            return str(hit)
    raise FileNotFoundError(f"No font file found for font={font!r}, style={style!r} (tried {candidates} in $PFD_FONT_DIR, "
                            f"{[str(d) for d in FONT_SEARCH_DIRS]} and fontconfig); install it or set PFD_FONT_DIR")


def _wpb() -> Any:
    """web_plate_builder (lazy): the shared font search and metadata strip helpers."""
    try:
        import web_plate_builder as mod
    except ImportError:  # pragma: no cover
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import web_plate_builder as mod
    return mod


@lru_cache(maxsize=512)
def _load_pil_font(font: str, style: str, size_half_pt: int) -> ImageFont.FreeTypeFont:
    path = _resolve_typo_font_path(font, style)
    pt = max(8.0, size_half_pt / 2.0)
    return ImageFont.truetype(path, pt)


def measure_text_ink_width(
    text: str,
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 52.0,
    tracking: float | None = None,
) -> float:
    """
    Measure true rendered ink bounding-box width (`bbox[2] - bbox[0]`) via `PIL.ImageFont.getbbox`,
    capturing exact Vietnamese italic/horn overhangs (`Ế`, `Ứ`, `Ẳ`, `j`).
    """
    clean = clean_display_text(text)
    if not clean.strip():
        return 0.0
    sz = max(8.0, float(size))
    f_obj = _load_pil_font(font, style, int(round(sz * 2.0)))
    trk_val = float(tracking) if tracking is not None else 0.0
    max_w = 0.0
    for line in clean.split("\n"):
        ln = line.strip()
        if not ln:
            continue
        bb = f_obj.getbbox(ln)
        ink_w = float(bb[2] - bb[0])
        if trk_val > 0.0 and len(ln) > 1:
            ink_w += (len(ln) - 1) * (trk_val / 1000.0) * sz
        if ink_w > max_w:
            max_w = ink_w
    return max_w


def fit_font_size(
    text: str,
    font: str,
    style: str,
    requested_size: float,
    max_width_px: float = DEFAULT_MAX_TEXT_WIDTH_PX,
    fit_ratio: float = HERO_ROW_FIT,
    tracking: float | None = None,
) -> float:
    """
    Ruling `R209` / `HERO_ROW_FIT = 0.95` True Ink-Box Width Auto-Cap:
      - Measures true glyph ink overhang width (`getbbox`) at `requested_size`.
      - Returns `requested_size` unchanged if `ink_width <= max_width_px * fit_ratio`.
      - Smoothly scales down `size` (0.5pt precision) ONLY when rendered ink exceeds `max_width_px * fit_ratio`.
    """
    req = float(requested_size)
    budget = max(120.0, float(max_width_px) * float(fit_ratio))
    w_now = measure_text_ink_width(text, font, style, req, tracking=tracking)
    if w_now <= budget + 1e-3:
        return req

    min_sz = 16.0
    est = math.floor((req * (budget / max(w_now, 1.0))) * 2.0) / 2.0
    cand = max(min_sz, min(req - 0.5, est))
    while cand > min_sz and measure_text_ink_width(text, font, style, cand, tracking=tracking) > budget:
        cand = round(cand - 0.5, 2)
    return max(min_sz, round(cand, 2))


def _starts_with_proper_or_acronym(token: str) -> bool:
    """True when `token` intentionally begins with an acronym/proper-noun capital (`AI`, `OPA`, `SKILL.md`, `TikTok`, `Việt`)."""
    _pre, core, _post = _split_token_affixes(token)
    if not core:
        return False
    if _is_caps_or_num_core(core):
        return True
    # Mixed-case proper brand/tech names (e.g. TikTok, YouTube, HeyGen, FilmCraft, iOS)
    if any(ch.isupper() for ch in core[1:]):
        return True
    return False


def _format_line2_continuation(l1_last_raw_token: str, l2_tokens: Sequence[str]) -> str:
    """
    Capitalization Fix (`v5.1`):
      - Preserve natural lowercase on Line 2 continuations (`"chuyên nghiệp hơn"`, `"khách hàng mới"`).
      - Capitalize Line 2 ONLY if Line 1 ended with sentence punctuation (`. ? ! …`) OR Line 2 starts
        with an uppercase proper noun/acronym (`AI`, `OPA`, `SKILL.md`, `Việt`).
    """
    raw_l2 = clean_display_text(" ".join(str(t) for t in l2_tokens))
    if not raw_l2.strip():
        return raw_l2
    _pre1, _core1, post1 = _split_token_affixes(l1_last_raw_token)
    if any(c in _SENTENCE_END_PUNCT for c in post1):
        return _cap_sentence_case(raw_l2)

    first_tok = str(l2_tokens[0]) if l2_tokens else ""
    if _starts_with_proper_or_acronym(first_tok):
        return raw_l2

    # If first token was already capitalized in input, keep it ONLY if it is not a known lowercase lexicon word;
    # otherwise preserve natural lowercase continuation so mid-phrase splits never get falsely capitalized.
    _pre2, core2, _post2 = _split_token_affixes(first_tok)
    if core2 and core2[0].isupper():
        tv = load_text_vi()
        low2 = core2.lower()
        pair_firsts = {p.split(" ", 1)[0] for p in tv["pairs"]}
        if low2 in tv["leads"] or low2 in tv["trails"] or low2 in tv["function"] or low2 in tv["pronouns"] or low2 in pair_firsts:
            # Lowercase only the first character of core2 inside raw_l2
            idx_c = raw_l2.find(core2[0])
            if idx_c >= 0:
                return raw_l2[:idx_c] + raw_l2[idx_c].lower() + raw_l2[idx_c + 1 :]
    return raw_l2


def _best_2line_split_index(
    tokens: Sequence[str],
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 52.0,
) -> int:
    """Return optimal split index `k` (`1 <= k < len(tokens)`) minimizing linguistic violations & `getbbox` width imbalance."""
    toks = [str(t) for t in tokens if str(t).strip()]
    n = len(toks)
    if n <= 1:
        return n

    safe_budget = DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT
    best_k = (n + 1) // 2
    best_cost = float("inf")

    for k in range(1, n):
        pen = 0.0
        w_left, w_right = toks[k - 1], toks[k]
        if is_glued_pair(w_left, w_right):
            pen += 1.2e6
        elif not can_split_after(toks, k - 1):
            pen += 1.0e6

        l1_txt = _cap_sentence_case(" ".join(toks[:k]))
        l2_txt = _format_line2_continuation(w_left, toks[k:])
        w1 = measure_text_ink_width(l1_txt, font, style, size)
        w2 = measure_text_ink_width(l2_txt, font, style, size)

        max_line_w = max(w1, w2)
        if max_line_w > safe_budget:
            pen += 5.0e4 + (max_line_w - safe_budget) * 100.0

        # Reward natural clause/sentence punctuation right before split
        _pre, _core, post_l = _split_token_affixes(w_left)
        punct_bonus = -36.0 if any(c in (_TRAIL_PUNCT + _CLOSE_AFFX) for c in post_l) else 0.0

        cost = pen + abs(w1 - w2) + punct_bonus
        if cost < best_cost:
            best_cost = cost
            best_k = k

    return best_k


def split_phrase_2line(
    tokens: Sequence[str],
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 52.0,
) -> tuple[str, str]:
    """
    Linguistic & Pixel-Balanced 2-Line Caption Splitter (`v5.1`):
      - Evaluates candidate split indices `1 .. len(tokens) - 1`.
      - Penalizes compound (`text_vi["pairs"]`), `lead`, and `trail` splits (`>= 1e6`).
      - Minimizes pixel-width imbalance between Line 1 and Line 2 via `PIL.ImageFont.getbbox`.
      - Capitalizes Line 1 (`_cap_sentence_case`) and preserves natural lowercase on Line 2 continuations
        unless Line 1 ended with `. ? ! …` or Line 2 begins with a proper noun / acronym (`AI`, `OPA`, `SKILL.md`).
    """
    toks = [str(t) for t in tokens if str(t).strip()]
    if not toks:
        return ("", "")
    if len(toks) == 1:
        return (_cap_sentence_case(toks[0]), "")
    k = _best_2line_split_index(toks, font=font, style=style, size=size)
    txt1 = _cap_sentence_case(" ".join(toks[:k]))
    txt2 = _format_line2_continuation(toks[k - 1], toks[k:])
    return (txt1, txt2)


def _smart_chunk_end(
    seg_ws: Sequence[tuple[str, float, float]],
    start_idx: int,
    max_words_per_group: int,
    pause_split_s: float,
    lookahead_gap_s: float = 0.35,
) -> int:
    """
    Grow caption chunk from `start_idx` up to `max_words_per_group` (stopping at pauses `>= pause_split_s`),
    then apply `v5.1` Smart Chunk Lookahead (`+1` word if gap `< 0.35s`, or `-1` / `-2` word step-back)
    so chunks NEVER bisect a 2-syllable Vietnamese compound word or orphan a `lead`/`trail` particle!
    """
    n = len(seg_ws)
    seg_toks = [w[0] for w in seg_ws]
    ptr = start_idx + 1
    while (
        ptr < n
        and (ptr - start_idx) < max_words_per_group
        and (seg_ws[ptr][1] - seg_ws[ptr - 1][2]) < pause_split_s
    ):
        ptr += 1

    if ptr >= n:
        return n

    # If stopped because of a genuine speech pause >= pause_split_s, respect the acoustic pause
    gap_next = seg_ws[ptr][1] - seg_ws[ptr - 1][2]
    if gap_next >= pause_split_s:
        return ptr

    if not can_split_after(seg_toks, ptr - 1):
        # 1. Step +1 word (e.g. 6 -> 7) if spoken gap < 0.35s and the new boundary is clean
        if ptr < n and gap_next < lookahead_gap_s and (ptr + 1 == n or can_split_after(seg_toks, ptr)):
            return ptr + 1
        # 2. Step -1 word (e.g. 6 -> 5) if previous boundary is clean
        if (ptr - 1) > start_idx and can_split_after(seg_toks, ptr - 2):
            return ptr - 1
        # 3. Step -2 words (e.g. `lead + compound_1 | compound_2` at end of group -> cut before `lead`)
        if (ptr - 2) >= start_idx + 2 and can_split_after(seg_toks, ptr - 3):
            return ptr - 2
        # 4. Fallback +1 if gap < 0.35s so a 2-syllable compound at start_idx is still kept whole
        if ptr < n and gap_next < lookahead_gap_s:
            return ptr + 1

    return ptr


# ---------------------------------------------------------------------------
# Frame-Exact Timing, Keyframe Sanitization & Text Normalization (Rules B5/B13)
# ---------------------------------------------------------------------------

def snap_time(t: float, fps: int = DEFAULT_FPS) -> float:
    """Snap seconds to exact timeline frame boundary."""
    return round(round(float(t) * fps) / fps, 6)


def clean_display_text(text: str) -> str:
    """
    Rule B5 + Rule B13 text sanitizer:
      - Normalizes to Unicode NFC.
      - Strips non-decimal commas (`(?<!\\d),|,(?!\\d)`) while keeping decimal commas like `1,5`.
      - Collapses redundant horizontal whitespace.
    """
    s = unicodedata.normalize("NFC", str(text or ""))
    # Replace comma not flanked on BOTH sides by digits
    s = re.sub(r"(?<!\d),\s*|\s*,(?!\d)", " ", s)
    lines = [" ".join(part.split()) for part in s.split("\n")]
    out = "\n".join(ln for ln in lines if ln)
    return out if out else " "


def wcag_luminance(hex_color: str) -> float:
    """Compute WCAG relative luminance of `#RRGGBB` (matches `edit_rules.py: _luminance`)."""
    c = str(hex_color or "#FFFFFF").strip()
    if not HEX6_RE.match(c):
        return 1.0
    vals = []
    for i in (1, 3, 5):
        v = int(c[i : i + 2], 16) / 255.0
        vals.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def _strict_kf(raw_keys: Sequence[Sequence[Any]], dur: float, fps: int = DEFAULT_FPS) -> list[list[Any]]:
    """
    Guarantee strictly frame-increasing keyframes inside `[0.0, dur]`:
      - Prevents `spec_lint.py` HARD `keys_not_increasing` errors.
      - Prevents `fc_build.py` out-of-range keyframe rejections or silent sub-frame collisions.
    """
    end_f = max(2, int(round(float(dur) * fps)))
    dur_s = round(end_f / fps, 6)
    if not raw_keys:
        return []

    parsed: list[tuple[int, Any, str]] = []
    for _idx, k in enumerate(raw_keys):
        t_val = max(0.0, min(dur_s, float(k[0])))
        f_idx = max(0, min(end_f, int(round(t_val * fps))))
        interp = str(k[2]) if len(k) >= 3 else "linear"
        parsed.append((f_idx, k[1], interp))

    # Pin first and last frames cleanly, keep strictly monotonic interior frames
    first_f, first_v, first_i = parsed[0]
    last_f, last_v, last_i = parsed[-1]

    if len(parsed) == 1:
        return [[round(first_f / fps, 6), first_v, first_i]]

    kept: list[tuple[int, Any, str]] = [(first_f, first_v, first_i)]
    for f_idx, val, interp in parsed[1:-1]:
        # Leave at least 1 frame before `last_f`
        if kept[-1][0] < f_idx < last_f:
            kept.append((f_idx, val, interp))

    if last_f <= kept[-1][0]:
        last_f = min(end_f, kept[-1][0] + 1)
    if last_f > kept[-1][0]:
        kept.append((last_f, last_v, last_i))

    return [[round(f / fps, 6), v, interp] for f, v, interp in kept]


def _build_shadow(size: float, opacity: float | None = None, blur: float | None = None, distance: float | None = None) -> dict[str, Any]:
    """Soft black shadow (Rule B14: zero stroke, clean optical depth separation)."""
    big = float(size) >= 50.0
    return {
        "color": "#000000",
        "opacity": float(opacity if opacity is not None else (80.0 if big else 64.0)),
        "blur": float(blur if blur is not None else (12.0 if big else 9.0)),
        "distance": float(distance if distance is not None else (4.0 if big else 3.0)),
        "angle": 135.0,
        "size": 2.0,
    }


def _resolve_glow_effect(color: str, glow_mode: str | None) -> dict[str, Any] | None:
    """
    Build color-matched `wonder_glow` effect per Rule P11:
      - `glow_mode="auto"`: applies glow when `wcag_luminance(color) >= 0.30` OR vivid studio neon
        (`max(R,G,B) >= 220` and `wcag_luminance(color) >= 0.22`, e.g. `#FF4D5E` `alert_coral`).
      - `glow_mode="normal"`: full neon/studio bloom (`radius=22, intensity=130`)
      - `glow_mode="soft"`: subtle halo (`radius=14, intensity=52`)
      - `glow_mode="none"` / `None`: no glow
    """
    mode = str(glow_mode or "none").lower()
    if mode in ("none", "off", "false"):
        return None
    col_str = str(color or "#FFFFFF").strip().upper()
    if mode == "auto":
        lum = wcag_luminance(col_str)
        max_ch = max((int(col_str[i : i + 2], 16) for i in (1, 3, 5)), default=255) if HEX6_RE.match(col_str) else 255
        if lum < 0.30 and not (max_ch >= 220 and lum >= 0.22):
            return None
        mode = "soft" if col_str in ("#FFFFFF", "#F8FAFC", "#F1F5F9") else "normal"

    is_soft = mode == "soft"
    return {
        "effect": "wonder_glow",
        "params": {
            "threshold": 35.0,
            "radius": 14.0 if is_soft else 22.0,
            "intensity": 52.0 if is_soft else 130.0,
            "saturation": 110.0,
            "use_color": True,
            "color": col_str if HEX6_RE.match(col_str) else "#FFFFFF",
            "mode": "Add",
        },
    }


def _core_text_clip(
    *,
    text: str,
    at: float,
    dur: float,
    font: str,
    style: str,
    size: float,
    color: str,
    pos: Sequence[float],
    align: str = "center",
    anchor: Sequence[float] | None = None,
    pos_kf: Sequence[Sequence[Any]],
    scale_kf: Sequence[Sequence[Any]],
    opacity_kf: Sequence[Sequence[Any]],
    blur_kf: Sequence[Sequence[Any]] | None = None,
    extra_effects: Sequence[dict[str, Any]] | None = None,
    glow_mode: str | None = "auto",
    rotation: float | Sequence[Sequence[Any]] | None = None,
    tracking: float | Sequence[Sequence[Any]] | None = None,
    shadow_overrides: dict[str, float] | None = None,
    max_width_px: float | None = None,
    fit_ratio: float = HERO_ROW_FIT,
    lock_size: bool = False,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Internal builder producing a validated `.craft.json` `graphic_text` clip dictionary with auto ink-box width fit."""
    clean_txt = clean_display_text(strip_inline_color_tags(text) or text)
    color_hex = resolve_semantic_color(str(color), "#FFFFFF")
    at_s = max(0.0, snap_time(at, fps))
    dur_s = max(round(4 / fps, 6), snap_time(dur, fps))
    px, py = float(pos[0]), float(pos[1])

    if max_width_px is not None:
        eff_max_w = float(max_width_px)
    elif align == "left" and px > 180.0:
        eff_max_w = min(DEFAULT_MAX_TEXT_WIDTH_PX, max(320.0, 970.0 - px))
    elif align == "right" and px < 900.0:
        eff_max_w = min(DEFAULT_MAX_TEXT_WIDTH_PX, max(320.0, px - 110.0))
    else:
        eff_max_w = DEFAULT_MAX_TEXT_WIDTH_PX

    max_trk: float | None = None
    if isinstance(tracking, (int, float)):
        max_trk = float(tracking)
    elif isinstance(tracking, (list, tuple)) and tracking:
        max_trk = max(float(k[1]) for k in tracking)

    if lock_size:
        fitted_size = round(float(size), 2)
    else:
        fitted_size = fit_font_size(
            clean_txt,
            font=font,
            style=style,
            requested_size=float(size),
            max_width_px=eff_max_w,
            fit_ratio=fit_ratio,
            tracking=max_trk,
        )
    anc = [float(anchor[0]), float(anchor[1])] if anchor is not None else [px, round(py - fitted_size * 0.32, 2)]

    motion: dict[str, Any] = {
        "anchor": anc,
        "position": _strict_kf(pos_kf, dur_s, fps),
        "scale": _strict_kf(scale_kf, dur_s, fps),
    }
    if rotation is not None:
        if isinstance(rotation, (int, float)):
            motion["rotation"] = float(rotation)
        else:
            motion["rotation"] = _strict_kf(rotation, dur_s, fps)

    effects: list[dict[str, Any]] = []
    if extra_effects:
        for ef in extra_effects:
            ef_copy = {"effect": ef["effect"], "params": {}}
            for pk, pv in ef.get("params", {}).items():
                if isinstance(pv, list) and pv and isinstance(pv[0], (list, tuple)):
                    ef_copy["params"][pk] = _strict_kf(pv, dur_s, fps)
                else:
                    ef_copy["params"][pk] = pv
            effects.append(ef_copy)

    if blur_kf is not None:
        effects.append({"effect": "gaussian_blur", "params": {"blurriness": _strict_kf(blur_kf, dur_s, fps)}})

    glow_fx = _resolve_glow_effect(color_hex, glow_mode)
    if glow_fx is not None:
        effects.append(glow_fx)

    sh_kw = shadow_overrides or {}
    clip: dict[str, Any] = {
        "name": name or f"Chữ · {clean_txt.replace(chr(10), ' ')[:22]}",
        "text": clean_txt,
        "at": at_s,
        "dur": dur_s,
        "font": font,
        "style": style,
        "size": float(fitted_size),
        "color": str(color_hex),
        "align": align,
        "position": [px, py],
        "shadow": _build_shadow(fitted_size, **sh_kw),
        "motion": motion,
        "opacity": _strict_kf(opacity_kf, dur_s, fps),
        "effects": effects,
    }
    if tracking is not None:
        if isinstance(tracking, (int, float)):
            clip["tracking"] = float(tracking)
        else:
            clip["tracking"] = _strict_kf(tracking, dur_s, fps)
    # v7.9.0: blurred multi-word text widens its word gaps (tracking keys) while blurred. The widest key must stay inside the
    # max width (full width for this transient frame): first REFLOW a one-line text of >= 3 words into two balanced lines, then
    # shrink the size, never below TEXT_FLOOR_PX (64 px legibility floor).
    design_trk = clip.get("tracking")
    for _ in range(6):
        clip["tracking"] = copy.deepcopy(design_trk)
        if clip["tracking"] is None:
            clip.pop("tracking")
        apply_entrance_word_spacing(clip, fps)
        trk = clip.get("tracking")
        widest = max((float(k[1]) for k in trk), default=0.0) if isinstance(trk, list) else float(trk or 0.0)
        if lock_size or widest <= (max_trk or 0.0) + 1e-6:
            break
        if measure_text_ink_width(clip["text"], font, style, clip["size"], tracking=widest) <= eff_max_w + 1e-6:
            break
        toks = clip["text"].split()
        if "\n" not in clip["text"] and len(toks) >= 3:
            k = _best_2line_split_index(toks, font=font, style=style, size=clip["size"])
            clip["text"] = " ".join(toks[:k]) + "\n" + " ".join(toks[k:])
            continue
        refit = max(min(float(clip["size"]), TEXT_FLOOR_PX),
                    fit_font_size(clip["text"], font=font, style=style, requested_size=float(clip["size"]), max_width_px=eff_max_w,
                                  fit_ratio=1.0, tracking=widest))
        if abs(refit - clip["size"]) < 0.25:
            warnings.warn(f"{clip.get('name')}: the widened blur-in frame is wider than {eff_max_w:.0f}px at the {TEXT_FLOOR_PX}px floor; "
                          "shorten the text or split it into two clips", stacklevel=2)
            break
        clip["size"] = float(refit)
        clip["shadow"] = _build_shadow(refit, **sh_kw)
        if anchor is None:
            motion["anchor"] = [px, round(py - refit * 0.32, 2)]
    return clip


# ---------------------------------------------------------------------------
# v7.9.0 entrance word spacing (user decision 2026-11-26): a blurred multi-word text clip widens its word gaps while blurred
# ---------------------------------------------------------------------------
WS_NAT_MARGIN_EM = 0.02  # [ĐO] PIL ink metrics vs the renderer: assume the resting gap this much tighter (same as web_plate_builder)
TEXT_FLOOR_PX = 64       # = web_plate_builder.MIN_OVERLAY_FONT_PX: the word-spacing refit never shrinks a text below it

# v7.9.1: G2 subtitles (S10 / S11 / S12, whisper mode included) obey the 64 px floor; secondary presets below it are decorative
_TYPO_PRESETS = json.loads((Path(__file__).resolve().parents[2] / "presets" / "typography_hierarchy_presets.json").read_text(encoding="utf-8"))
G2_TEXT_FLOOR_PX = float(_TYPO_PRESETS["scale_tiers_9_16"].get("whisper_g2_px_floor_v791", TEXT_FLOOR_PX))
WHISPER_G2_PX = max(float(_TYPO_PRESETS["scale_tiers_9_16"]["whisper_g2_px"]), G2_TEXT_FLOOR_PX)
DECORATIVE_SECONDARY_V791: dict[str, str] = dict(_TYPO_PRESETS.get("secondary_text_decorative_v791", {}).get("presets", {}))


def _g2_chunk_end_at_floor(seg_ws: Sequence[Sequence[Any]], ptr: int, next_ptr: int, *, font: str, style: str, size: float,
                           two_line: bool = False, slot_gap_em: float | None = None) -> int:
    """v7.9.1: drop trailing words from a G2 chunk until it fits the safe width at the floored size (one line, or two balanced
    lines), so the floor never makes fit_font_size shrink the subtitle below G2_TEXT_FLOOR_PX. Keeps at least one word.
    `slot_gap_em` (S10 fixed slots): measure as S10 lays the row out, sum of per-word max(ink, advance) + max(space, gap em) gaps."""
    budget = DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT
    while next_ptr - ptr > 1:
        toks = [clean_display_text(str(w[0])) for w in seg_ws[ptr:next_ptr]]
        if slot_gap_em is not None:
            f_obj = _load_pil_font(font, style, int(round(size * 2.0)))
            gap = max(float(f_obj.getlength(" ")), size * slot_gap_em)
            width = sum(max(float(f_obj.getbbox(t)[2] - f_obj.getbbox(t)[0]), float(f_obj.getlength(t))) for t in toks)
            width += gap * (len(toks) - 1)
        else:
            lines = split_phrase_2line(toks, font=font, style=style, size=size) if (two_line and len(toks) > 3) else (" ".join(toks),)
            width = max(measure_text_ink_width(ln, font, style, size) for ln in lines)
        if width <= budget + 1e-3:
            break
        next_ptr -= 1
    return next_ptr


def _motion_gate() -> Any:
    try:
        import motion_gate as mod
    except ImportError:  # pragma: no cover
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import motion_gate as mod
    return mod


def _kf_value(kf: Any, t: float, default: float = 0.0) -> float:
    """Value of a constant or `[[t, v, interp], ...]` keyframe list at `t` (linear between keys, held outside)."""
    if kf is None:
        return float(default)
    if isinstance(kf, (int, float)):
        return float(kf)
    keys = [(float(k[0]), float(k[1])) for k in kf]
    if not keys:
        return float(default)
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 if t1 <= t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def _kf_times(kf: Any) -> list[float]:
    return [float(k[0]) for k in kf] if isinstance(kf, (list, tuple)) and kf and isinstance(kf[0], (list, tuple)) else []


def apply_entrance_word_spacing(clip: dict[str, Any], fps: int = DEFAULT_FPS) -> dict[str, Any]:
    """v7.9.0: FilmCraft text clips have no word-spacing property, so the extra word spacing of a blur entrance is keyed as TRACKING
    (per mille em, applied after every character: a word gap gains 2 x tracking / 1000 em). At every `gaussian_blur` key the clip gets
        tracking >= 500 x motion_gate.entrance_word_spacing_em(blurriness, min(scale, 1), size, resting gap)
    (the helper the web plates use; `min(scale, 1)` covers both effect orders: blur before or after Motion), with the blur key's
    interpolation, so the gap stays >= 0.25 em on every frame and the tracking returns to its resting value exactly as the blur
    reaches 0 (resting value = the 0.25 em floor when the font's natural gap is under it). An existing tracking is kept wherever it is
    already wider. One-word texts are untouched. Returns the same dict, modified."""
    text = str(clip.get("text") or "")
    if not any(len(ln.split()) >= 2 for ln in text.split("\n")):
        return clip
    blur = None
    for fx in clip.get("effects") or []:
        if isinstance(fx, dict) and fx.get("effect") == "gaussian_blur":
            blur = (fx.get("params") or {}).get("blurriness")
    if blur is None or (isinstance(blur, (int, float)) and float(blur) <= 0.0):
        return clip
    mg = _motion_gate()
    nat = mg.natural_word_gap_em(text, _resolve_typo_font_path(str(clip.get("font")), str(clip.get("style"))), 0.0)
    if nat is None:
        return clip
    nat -= WS_NAT_MARGIN_EM
    size = float(clip.get("size") or 52.0)
    dur = float(clip.get("dur") or 1.0)
    scale_kf = (clip.get("motion") or {}).get("scale", 100.0)
    old_trk = clip.get("tracking")
    blur_keys = blur if isinstance(blur, list) else [[0.0, float(blur), "linear"], [dur, float(blur), "linear"]]
    flags = {round(float(k[0]), 6): (str(k[2]) if len(k) >= 3 else "linear") for k in blur_keys}
    if isinstance(old_trk, list):
        for k in old_trk:
            flags.setdefault(round(float(k[0]), 6), str(k[2]) if len(k) >= 3 else "linear")
    times = sorted(flags)
    out = []
    for i, t in enumerate(times):
        lo, hi = times[max(0, i - 1)], times[min(len(times) - 1, i + 1)]
        probes = [lo, t, hi] + [x for x in _kf_times(scale_kf) if lo <= x <= hi]
        s_min = min(_kf_value(scale_kf, x, 100.0) for x in probes) / 100.0
        need = 500.0 * mg.entrance_word_spacing_em(_kf_value(blur_keys, t), min(s_min, 1.0), size, nat)
        val = max(need, _kf_value(old_trk, t, 0.0) if old_trk is not None else 0.0)
        out.append([t, round(math.ceil(val * 100) / 100, 2), flags[t]])
    clip["tracking"] = _strict_kf(out, dur, fps)
    return clip



def _r30_quick_exit_timings(dur: float, fps: int = DEFAULT_FPS) -> tuple[float, float, float, list[list[Any]], list[list[Any]]]:
    """
    Ruling `R30` tight-chunk timing (`0.18s <= dur < 0.32s`):
      - Exact 2-frame exit (`2 / fps`).
      - Guaranteed `>= 3` full frame intervals (`>= 4` discrete frames) at `100%` opacity.
    """
    end_f = max(5, int(round(float(dur) * fps)))
    dur_s = round(end_f / fps, 6)
    out_f = end_f - 2
    in_f = min(2, end_f - 3)
    t_in = round(in_f / fps, 6)
    t_out = round(out_f / fps, 6)

    if end_f <= 5:
        op_kf: list[list[Any]] = [
            [0.0, 100.0, "linear"],
            [t_out, 100.0, "easeOut"],
            [dur_s, 0.0, "easeIn"],
        ]
    else:
        op_in_f = min(2, end_f - 5)
        op_kf = [
            [0.0, 0.0, "easeOut"],
            [round(op_in_f / fps, 6), 100.0, "easeIn"],
            [t_out, 100.0, "easeOut"],
            [dur_s, 0.0, "easeIn"],
        ]

    blur_kf: list[list[Any]] = [
        [0.0, 8.0, "easeOut"],
        [t_in, 0.0, "easeIn"],
        [t_out, 0.0, "easeOut"],
        [dur_s, 4.0, "easeIn"],
    ]
    return dur_s, t_in, t_out, op_kf, blur_kf


# ---------------------------------------------------------------------------
# 1–9 & 13. Individual Single-Clip Typography Presets
# ---------------------------------------------------------------------------

def dviet_soft_up(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    font: str = "Be Vietnam Pro",
    style: str = "ExtraBold",
    size: float = 70.0,
    color: str = "#FFFFFF",
    align: str = "center",
    glow_mode: str | None = "auto",
    quick_exit: bool | None = None,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    Preset 1: Signature `@__dviet` gaussian blur + glide + continuous hold scale drift.
      - `R209`: Auto-flips entrance to gentle top-drop (`py - 18.0 -> py -> py - 3.0`, `scale 96 -> 100 -> 103%`)
        whenever `pos[1] >= 1360.0` so `gaussian_blur` stays inside bottom safe zone (`y <= 1650`).
      - `R30`: Applies crisp 2-frame (`2 / fps`) quick exit with `>= 3` frames at `100%` opacity when `dur < 0.32s`.
    """
    px, py = float(pos[0]), float(pos[1])
    safe_bottom = py >= R209_SAFE_BOTTOM_Y
    use_r30 = bool(quick_exit) if quick_exit is not None else (float(dur) < R30_TIGHT_MAX_S)

    if use_r30:
        dur_s, t_in, t_out, opacity_kf, blur_kf = _r30_quick_exit_timings(dur, fps=fps)
    else:
        dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
        t_in = snap_time(min(0.24, dur_s * 0.30), fps)
        t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.22)), fps)
        opacity_kf = [[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]]
        blur_in = 12.0 if safe_bottom else 15.0
        blur_out = 8.0 if safe_bottom else 10.0
        blur_kf = [[0.0, blur_in, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, blur_out, "easeIn"]]

    if safe_bottom:
        pos_kf = [[0.0, [px, py - 18.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.0], "linear"]]
        scale_kf = [[0.0, 96.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.3, "linear"], [dur_s, 103.0, "linear"]]
    else:
        pos_kf = [[0.0, [px, py + 24.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 5.0], "linear"]]
        scale_kf = [[0.0, 95.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.6, "linear"], [dur_s, 103.6, "linear"]]

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, name=name, fps=fps,
        pos_kf=pos_kf,
        scale_kf=scale_kf,
        opacity_kf=opacity_kf,
        blur_kf=blur_kf,
    )


def elastic_pop(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    font: str = "Montserrat",
    style: str = "Black",
    size: float = 78.0,
    color: str = "#2DD4BF",
    align: str = "center",
    glow_mode: str | None = "normal",
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 2: `82% -> 102% -> 100% -> 103.5%` crisp elastic impact + continuous hold drift."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_peak = snap_time(min(0.16, dur_s * 0.22), fps)
    t_settle = snap_time(min(0.28, max(t_peak + 2 / fps, dur_s * 0.34)), fps)
    t_out = snap_time(max(t_settle + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, name=name, fps=fps,
        pos_kf=[[0.0, [px, py + 18.0], "easeOut"], [t_peak, [px, py - 2.0], "easeOut"], [t_settle, [px, py], "easeIn"], [dur_s, [px, py - 4.0], "linear"]],
        scale_kf=[[0.0, 82.0, "easeOut"], [t_peak, 102.0, "easeOut"], [t_settle, 100.0, "easeIn"], [t_out, 102.6, "linear"], [dur_s, 103.5, "easeIn"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.13, t_peak), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 11.0, "easeOut"], [t_peak, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 8.0, "easeIn"]],
    )


def slide_down_reveal(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    font: str = "Montserrat",
    style: str = "ExtraBold",
    size: float = 70.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 3: Top-down editorial drop (`py-30 -> py -> py+4`) + gaussian blur clear + hold drift."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.22)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, name=name, fps=fps,
        pos_kf=[[0.0, [px, py - 30.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py + 4.0], "linear"]],
        scale_kf=[[0.0, 96.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.5, "linear"], [dur_s, 103.5, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 14.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 10.0, "easeIn"]],
    )


def swing_3d_y(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    font: str = "Montserrat",
    style: str = "Black",
    size: float = 80.0,
    color: str = "#2DD4BF",
    align: str = "center",
    glow_mode: str | None = "normal",
    rot_y_start: float = -38.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 4: `rotate_3d` Y-axis perspective swing (`rot_y: -38 -> 0 -> +2`) + matching `wonder_glow`."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.27, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    rot3d = {
        "effect": "rotate_3d",
        "params": {
            "rot_y": [[0.0, float(rot_y_start), "easeOut"], [t_in, 0.0, "easeIn"], [dur_s, 2.0, "linear"]],
        },
    }
    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, name=name, fps=fps,
        extra_effects=[rot3d],
        pos_kf=[[0.0, [px - 16.0, py + 14.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 4.0], "linear"]],
        scale_kf=[[0.0, 90.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.8, "linear"], [dur_s, 103.8, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 12.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 9.0, "easeIn"]],
    )


def flip_3d_x(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    font: str = "Montserrat",
    style: str = "ExtraBold",
    size: float = 76.0,
    color: str = "#FFC414",
    align: str = "center",
    glow_mode: str | None = "normal",
    rot_x_start: float = 32.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 5: `rotate_3d` X-axis card-flip title (`rot_x: 32 -> 0 -> -1.5`) + hold scale drift."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.27, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    rot3d = {
        "effect": "rotate_3d",
        "params": {
            "rot_x": [[0.0, float(rot_x_start), "easeOut"], [t_in, 0.0, "easeIn"], [dur_s, -1.5, "linear"]],
        },
    }
    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, name=name, fps=fps,
        extra_effects=[rot3d],
        pos_kf=[[0.0, [px, py + 22.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 4.0], "linear"]],
        scale_kf=[[0.0, 92.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.6, "linear"], [dur_s, 103.5, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 12.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 9.0, "easeIn"]],
    )


def editorial_serif_italic(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 382.0),
    font: str = "Playfair Display",
    style: str = "Italic",
    size: float = 74.0,
    color: str = "#FFC414",
    align: str = "center",
    glow_mode: str | None = "soft",
    tracking: float = 12.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 6: `Playfair Display Italic` warm gold/cream luxury slow reveal + gentle velvet float."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.30, dur_s * 0.34), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.16, dur_s * 0.22)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, tracking=tracking, name=name, fps=fps,
        pos_kf=[[0.0, [px, py + 18.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 5.0], "linear"]],
        scale_kf=[[0.0, 96.5, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.2, "linear"], [dur_s, 103.0, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.22, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 16.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 10.0, "easeIn"]],
    )


def script_brush_accent(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 488.0),
    font: str = "SVN-Dancing Script",
    style: str = "Regular",
    size: float = 62.0,
    color: str = "#FFFFFF",
    align: str = "center",
    glow_mode: str | None = "soft",
    tilt_deg: float = -2.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 7: `SVN-Dancing Script` handwritten calligraphy accent with horizontal brush-glide & organic tilt."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.26, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, rotation=float(tilt_deg), name=name, fps=fps,
        pos_kf=[[0.0, [px - 22.0, py + 10.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 5.0, py - 3.0], "linear"]],
        scale_kf=[[0.0, 94.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.18, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 12.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 8.0, "easeIn"]],
    )


def minimal_giant_word(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 880.0),
    font: str = "Montserrat",
    style: str = "Black",
    size: float = 104.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    tracking: float = -12.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 8: Single `96–112pt` monumental focal word for `minimal_intellectual` compositions (auto ink-capped if wide)."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.28, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.16, dur_s * 0.22)), fps)
    px, py = float(pos[0]), float(pos[1])
    sz = max(96.0, min(116.0, float(size)))

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=sz, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, tracking=tracking, name=name, fps=fps,
        shadow_overrides={"opacity": 84.0, "blur": 18.0, "distance": 6.0},
        pos_kf=[[0.0, [px, py + 16.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 4.0], "linear"]],
        scale_kf=[[0.0, 91.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 103.0, "linear"], [dur_s, 104.0, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.20, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 18.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 12.0, "easeIn"]],
    )


def side_left_callout(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (380.0, 920.0),
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 54.0,
    color: str = "#38BDF8",
    align: str = "left",
    glow_mode: str | None = "soft",
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """Preset 9: Left-aligned callout positioned at `x=360..420` beside speaker shoulder or 3D prop."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align,
        glow_mode=glow_mode, name=name, fps=fps,
        pos_kf=[[0.0, [px - 32.0, py], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 6.0, py - 2.0], "linear"]],
        scale_kf=[[0.0, 95.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 12.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 8.0, "easeIn"]],
    )


def hook_drop_handoff(
    text: str,
    at: float = 0.0,
    dur: float = 1.35,
    *,
    pos: Sequence[float] = (540.0, 720.0),
    font: str = "Montserrat",
    style: str = "Black",
    size: float = 108.0,
    color: str = "#FFC414",
    align: str = "center",
    glow_mode: str | None = "normal",
    tracking: float = -10.0,
    drop_px: float = 220.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    Preset 13 (`v5.1`, inspired by `Hook.tsx`):
      - `0 -> 0.32s`: `128% -> 100%` slam-in with blur `18 -> 0px`
      - Hold push: `100% -> 104%` continuous optical pressure (`static_hold == 0%`)
      - Last `0.28s`: downward blurred handoff (`py + 220px`, `scale 72%`, `blur 14px`) guiding the viewer's eye
        straight down to the speaker/captions!
    """
    dur_s = max(round(8 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.32, dur_s * 0.34), fps)
    out_span = min(0.28, dur_s * 0.28)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - out_span), fps)
    px, py = float(pos[0]), float(pos[1])
    y_drop = min(1620.0, py + float(drop_px))

    # Account for 104% hold push so peak rendered width stays safely within canvas safe width
    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, tracking=tracking,
        fit_ratio=round(HERO_ROW_FIT / 1.04, 4),
        shadow_overrides={"opacity": 86.0, "blur": 20.0, "distance": 6.0},
        name=name or f"Hook · {clean_display_text(text)[:18]}",
        fps=fps,
        pos_kf=[
            [0.0, [px, py + 36.0], "easeOut"],
            [t_in, [px, py], "easeIn"],
            [t_out, [px, py - 4.0], "easeOut"],
            [dur_s, [px, y_drop], "easeIn"],
        ],
        scale_kf=[
            [0.0, 128.0, "easeOut"],
            [t_in, 100.0, "easeIn"],
            [t_out, 104.0, "easeOut"],
            [dur_s, 72.0, "easeIn"],
        ],
        opacity_kf=[
            [0.0, 0.0, "easeOut"],
            [min(0.16, t_in), 100.0, "easeIn"],
            [t_out, 100.0, "easeOut"],
            [dur_s, 0.0, "easeIn"],
        ],
        blur_kf=[
            [0.0, 18.0, "easeOut"],
            [t_in, 0.0, "easeIn"],
            [t_out, 0.0, "easeOut"],
            [dur_s, 14.0, "easeIn"],
        ],
    )


# ---------------------------------------------------------------------------
# 10. `dual_hero_pair` (Smart Hair-Clearance Y-Safe-Zone Layout)
# ---------------------------------------------------------------------------

SINGLE_PRESET_MAP = {
    "dviet_soft_up": dviet_soft_up,
    "soft_up": dviet_soft_up,
    "elastic_pop": elastic_pop,
    "pop": elastic_pop,
    "slide_down_reveal": slide_down_reveal,
    "slide_down": slide_down_reveal,
    "swing_3d_y": swing_3d_y,
    "flip_3d_x": flip_3d_x,
    "editorial_serif_italic": editorial_serif_italic,
    "script_brush_accent": script_brush_accent,
    "minimal_giant_word": minimal_giant_word,
    "side_left_callout": side_left_callout,
    "hook_drop_handoff": hook_drop_handoff,
    "hook_handoff": hook_drop_handoff,
}


def _normalize_bbox_to_px(
    bbox: Sequence[float] | None,
    canvas_w: float = 1080.0,
    canvas_h: float = 1920.0,
) -> tuple[float, float, float, float] | None:
    """Normalize `[x0, y0, x1, y1]` (in normalized `[0..1]` OR pixel coordinates) to `(x0, y0, x1, y1)` px."""
    if bbox is None or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    vals = [float(v) for v in bbox[:4]]
    if all(0.0 <= abs(v) <= 1.5 for v in vals) and max(vals) <= 1.5:
        x0, y0, x1, y1 = vals[0] * canvas_w, vals[1] * canvas_h, vals[2] * canvas_w, vals[3] * canvas_h
    else:
        x0, y0, x1, y1 = vals[0], vals[1], vals[2], vals[3]
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def resolve_dual_rail_safe_y(
    hair_top_y: float | None = None,
    chin_y: float | None = None,
    *,
    preferred_rail: str = "auto",
    face_bbox: Sequence[float] | None = None,
    enamel_gum_bbox: Sequence[float] | None = None,
    macro_subject_bbox: Sequence[float] | None = None,
    extra_exclusion_bboxes: Sequence[Sequence[float]] | None = None,
    text_size: float = 72.0,
    line_count: int = 1,
    line_height: float = 1.0,
    has_lead: bool = False,
    lead_size: float = 32.0,
    canvas_w: float = 1080.0,
    canvas_h: float = 1920.0,
    is_broll: bool = False,
    z_plane: str = "foreground",
) -> dict[str, Any]:
    """
    `v7.0` **Dual-Rail Safe-Y Coordinator & Hard `Cranial Lock`** (`1080x1920` native physics):
      - Automatically selects between:
          1. **`Upper Editorial Stage`** (`y = 18%–34% * H` -> `345.6..652.8px` on `1920p`, bounded `>= 196px`)
          2. **`Chest Tactile Rail`** (`y = 72%–79% * H` -> `1382.4..1516.8px` on `1920p`, safely above TikTok UI)
      - Enforces **100% Hard `Cranial Lock`** on all foreground text (`z_plane != "behind_subject"`):
          - Zero glyph overlap with **`[hair_top_y - 48px, chin_y + 32px]`**!
          - Zero glyph overlap with **`enamel_gum_bbox`** and **`macro_subject_bbox`** (`+24px` clinical buffer)!
    """
    W = float(canvas_w)
    H = float(canvas_h)
    sz = max(14.0, float(text_size))
    n_lines = max(1, int(line_count))
    lh = max(0.70, float(line_height))
    lead_extra_up = (max(44.0, float(lead_size) * 0.88 + sz * 0.48)) if has_lead else 0.0

    # Glyph ink offsets relative to first-line baseline `y_base`:
    # top ascender/diacritic ~ -0.82 * sz - lead_extra_up; bottom descender ~ +0.24 * sz + (n_lines - 1)*sz*lh
    ink_up = 0.82 * sz + lead_extra_up
    ink_dn = 0.24 * sz + max(0, n_lines - 1) * sz * lh

    # 1. Build forbidden Y-intervals: Cranial Lock [hair_top - 48, chin + 32] + Clinical/Macro BBoxes
    forbidden_y_spans: list[tuple[float, float, str]] = []
    cran_zone: tuple[float, float] | None = None
    fb_px = _normalize_bbox_to_px(face_bbox, W, H)

    eff_hair = float(hair_top_y) if hair_top_y is not None else None
    eff_chin = float(chin_y) if chin_y is not None else None
    if fb_px is not None:
        fh = max(40.0, fb_px[3] - fb_px[1])
        if eff_hair is None:
            eff_hair = fb_px[1] - 0.28 * fh
        if eff_chin is None:
            eff_chin = fb_px[3] + 0.06 * fh
    elif eff_hair is not None and eff_chin is not None:
        pass
    elif eff_hair is not None and eff_chin is None:
        eff_chin = eff_hair + 0.23 * H
    elif eff_chin is not None and eff_hair is None:
        eff_hair = eff_chin - 0.23 * H
    elif not is_broll and str(z_plane).strip().lower() != "behind_subject":
        # Default canonical A-Roll cranial band when speaker is on-camera without explicit bbox
        eff_hair = 0.30 * H   # 576px
        eff_chin = 0.53 * H   # 1017.6px

    enforce_cranial = str(z_plane or "foreground").strip().lower() != "behind_subject"
    if enforce_cranial and eff_hair is not None and eff_chin is not None:
        cy0 = float(eff_hair) - 48.0
        cy1 = float(eff_chin) + 32.0
        cran_zone = (cy0, cy1)
        forbidden_y_spans.append((cy0, cy1, "cranial_lock"))

    macro_pad = 24.0
    for tag_name, raw_box in (
        ("enamel_gum_bbox", enamel_gum_bbox),
        ("macro_subject_bbox", macro_subject_bbox),
    ):
        b_px = _normalize_bbox_to_px(raw_box, W, H)
        if b_px is not None:
            forbidden_y_spans.append((b_px[1] - macro_pad, b_px[3] + macro_pad, tag_name))

    for idx_ex, ex_box in enumerate(extra_exclusion_bboxes or ()):
        b_px = _normalize_bbox_to_px(ex_box, W, H)
        if b_px is not None:
            forbidden_y_spans.append((b_px[1] - macro_pad, b_px[3] + macro_pad, f"extra_bbox_{idx_ex}"))

    def _min_clearance(y_base: float) -> float:
        iy0 = y_base - ink_up
        iy1 = y_base + ink_dn
        # Screen safe bounds [148 .. H - 180]
        edge_clear = min(iy0 - 148.0, (H - 180.0) - iy1)
        if edge_clear < 0.0:
            return edge_clear
        min_c = edge_clear
        for fy0, fy1, _lbl in forbidden_y_spans:
            # Signed separation (>0 means zero overlap, <0 means collision depth!)
            sep = max(fy0 - iy1, iy0 - fy1)
            if sep < min_c:
                min_c = sep
        return min_c

    # 2. Evaluate Upper Editorial Stage (18%..34% * H, allowing graceful lift down to 13% * H if needed)
    upper_stage_lo = 0.18 * H
    upper_stage_hi = 0.34 * H
    upper_abs_min = max(148.0 + ink_up + 2.0, 0.125 * H)
    upper_cands: list[float] = []
    # Ideal editorial anchor inside 18%..34% plus boundaries right above any forbidden ceiling
    for frac in (0.18, 0.21, 0.24, 0.27, 0.30, 0.33, 0.34):
        upper_cands.append(frac * H)
    for fy0, _fy1, _lbl in forbidden_y_spans:
        cand_above = fy0 - ink_dn - 8.0
        if upper_abs_min <= cand_above <= upper_stage_hi:
            upper_cands.append(cand_above)
    upper_cands.append(upper_abs_min)

    best_upper_y = max(upper_abs_min, min(upper_stage_hi, 0.23 * H))
    best_upper_clear = -1e9
    for yc in upper_cands:
        if yc < upper_abs_min - 1e-3 or yc > upper_stage_hi + 1e-3:
            continue
        cl_v = _min_clearance(yc)
        # Prefer staying strictly inside [0.18*H, 0.34*H] when collision-free
        in_canonical_upper = (upper_stage_lo - 2.0) <= yc <= (upper_stage_hi + 2.0)
        score = cl_v + (25.0 if (cl_v >= 0.0 and in_canonical_upper) else 0.0)
        if score > best_upper_clear:
            best_upper_clear = score
            best_upper_y = yc
    upper_true_clear = _min_clearance(best_upper_y)

    # 3. Evaluate Chest Tactile Rail (72%..79% * H, allowing up to 83% * H while staying <= H - 180)
    chest_rail_lo = 0.72 * H
    chest_rail_hi = 0.79 * H
    chest_abs_max = min(H - 180.0 - ink_dn - 2.0, 0.84 * H)
    chest_cands: list[float] = []
    for frac in (0.72, 0.74, 0.755, 0.77, 0.79):
        chest_cands.append(frac * H)
    for _fy0, fy1, _lbl in forbidden_y_spans:
        cand_below = fy1 + ink_up + 8.0
        if chest_rail_lo <= cand_below <= chest_abs_max:
            chest_cands.append(cand_below)
    if chest_abs_max >= chest_rail_lo:
        chest_cands.append(chest_abs_max)

    best_chest_y = 0.75 * H
    best_chest_clear = -1e9
    for yc in chest_cands:
        if yc < chest_rail_lo - 1e-3 or yc > max(chest_rail_hi, chest_abs_max) + 1e-3:
            continue
        cl_v = _min_clearance(yc)
        in_canonical_chest = (chest_rail_lo - 2.0) <= yc <= (chest_rail_hi + 2.0)
        score = cl_v + (25.0 if (cl_v >= 0.0 and in_canonical_chest) else 0.0)
        if score > best_chest_clear:
            best_chest_clear = score
            best_chest_y = yc
    chest_true_clear = _min_clearance(best_chest_y)

    # 4. Select optimal collision-free rail
    pref = str(preferred_rail or "auto").strip().lower()
    want_chest = pref in ("chest", "chest_tactile_rail", "lower", "bottom")
    want_upper = pref in ("upper", "upper_editorial_stage", "top")

    if upper_true_clear >= 0.0 and chest_true_clear < 0.0:
        chosen_rail = "upper_editorial_stage"
        chosen_y = best_upper_y
        chosen_clear = upper_true_clear
    elif chest_true_clear >= 0.0 and upper_true_clear < 0.0:
        chosen_rail = "chest_tactile_rail"
        chosen_y = best_chest_y
        chosen_clear = chest_true_clear
    elif want_chest and chest_true_clear >= 0.0:
        chosen_rail = "chest_tactile_rail"
        chosen_y = best_chest_y
        chosen_clear = chest_true_clear
    elif want_upper and upper_true_clear >= 0.0:
        chosen_rail = "upper_editorial_stage"
        chosen_y = best_upper_y
        chosen_clear = upper_true_clear
    elif upper_true_clear >= 0.0 and chest_true_clear >= 0.0:
        # In `auto` mode: prefer Upper Editorial Stage when upper stage stays inside canonical 18%..34%
        # and speaker hair crown leaves generous breathing room; otherwise route to Chest Tactile Rail!
        if best_upper_y >= (upper_stage_lo - 12.0) and (eff_hair is None or eff_hair >= 0.255 * H):
            chosen_rail = "upper_editorial_stage"
            chosen_y = best_upper_y
            chosen_clear = upper_true_clear
        else:
            chosen_rail = "chest_tactile_rail"
            chosen_y = best_chest_y
            chosen_clear = chest_true_clear
    else:
        # Extreme fullscreen macro fallback: pick whichever rail maximizes clearance
        if chest_true_clear >= upper_true_clear:
            chosen_rail = "chest_tactile_rail"
            chosen_y = best_chest_y
            chosen_clear = chest_true_clear
        else:
            chosen_rail = "upper_editorial_stage"
            chosen_y = best_upper_y
            chosen_clear = upper_true_clear

    safe_y = round(float(chosen_y), 1)
    iy0_final = round(safe_y - ink_up, 1)
    iy1_final = round(safe_y + ink_dn, 1)
    lead_gap = round(max(48.0, float(lead_size) * 0.42 + sz * 0.45), 1)

    cranial_ok = True
    if cran_zone is not None and enforce_cranial:
        cranial_ok = bool(iy1_final <= cran_zone[0] + 0.5 or iy0_final >= cran_zone[1] - 0.5)

    macro_ok = True
    for fy0, fy1, lbl in forbidden_y_spans:
        if lbl != "cranial_lock":
            if not (iy1_final <= fy0 + 0.5 or iy0_final >= fy1 - 0.5):
                macro_ok = False
                break

    rail_band = (
        [round(upper_stage_lo, 1), round(upper_stage_hi, 1)]
        if chosen_rail == "upper_editorial_stage"
        else [round(chest_rail_lo, 1), round(chest_rail_hi, 1)]
    )

    return {
        "y": safe_y,
        "safe_y": safe_y,
        "hero_y": safe_y,
        "lead_y": round(safe_y - lead_gap, 1),
        "rail": chosen_rail,
        "rail_y_band_px": rail_band,
        "y_pct": round(100.0 * safe_y / H, 2),
        "ink_y_span": [iy0_final, iy1_final],
        "cranial_lock_zone_y": [round(cran_zone[0], 1), round(cran_zone[1], 1)] if cran_zone else None,
        "cranial_lock_verified": cranial_ok,
        "macro_exclusion_verified": macro_ok,
        "clearance_px": round(float(chosen_clear), 1),
    }


def apply_persistent_text_bridge(
    text_clip: dict[str, Any] | list[dict[str, Any]],
    next_cut_s: float,
    lead_frames: int = 4,
    hold_across_frames: int = 10,
    fps: int = 60,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    `v7.0` **Persistent Text Bridge** (`Video #01, #06, #10, #16` @ 60fps):
      - Anchors typography across a hard visual cut at `next_cut_s`:
          1. Guarantees text enters at least `lead_frames` (`4f`) BEFORE `next_cut_s`
             (`at <= next_cut_s - lead_frames / fps`).
          2. Holds typography across the cut for `hold_across_frames` (`10f`) into the incoming shot
             (`at + dur == next_cut_s + hold_across_frames / fps`), keeping `100%` opacity across `next_cut_s`!
          3. Marks `"persistent_bridge": True` so `compile_and_verify.py` Gate 1 `c8_guard` preserves
             the cross-cut hold (and strips the metadata key cleanly before `fc_build_fast.py`).
      - Supports both a single `dict` clip and a `list[dict]` clip bundle!
    """
    fps_i = max(1, int(round(float(fps))))
    cut_s = snap_time(float(next_cut_s), fps_i)
    lead_s = max(1, int(lead_frames)) / float(fps_i)
    hold_s = max(1, int(hold_across_frames)) / float(fps_i)

    if isinstance(text_clip, list):
        if not text_clip:
            return []
        min_at = min(float(c.get("at", cut_s)) for c in text_clip)
        shift_earlier = max(0.0, min_at - max(0.0, cut_s - lead_s))
        out_bundle: list[dict[str, Any]] = []
        for c_item in text_clip:
            c_copy = copy.deepcopy(c_item)
            if shift_earlier > 0.0:
                c_copy["at"] = max(0.0, snap_time(float(c_copy.get("at", 0.0)) - shift_earlier, fps_i))
            bridged_c = apply_persistent_text_bridge(
                c_copy,
                next_cut_s=cut_s,
                lead_frames=lead_frames,
                hold_across_frames=hold_across_frames,
                fps=fps_i,
            )
            if isinstance(bridged_c, dict):
                out_bundle.append(bridged_c)
        return out_bundle

    cl = copy.deepcopy(text_clip)
    old_at = float(cl.get("at", 0.0))
    old_dur = max(4.0 / fps_i, float(cl.get("dur", 0.6)))
    max_allowed_at = max(0.0, snap_time(cut_s - lead_s, fps_i))
    new_at = min(snap_time(old_at, fps_i), max_allowed_at)
    new_end = snap_time(cut_s + hold_s, fps_i)
    new_dur = max(snap_time(6.0 / fps_i, fps_i), snap_time(new_end - new_at, fps_i))

    cl["at"] = new_at
    cl["dur"] = new_dur
    cl["persistent_bridge"] = True
    orig_name = str(cl.get("name") or "Chữ")
    if "bridge" not in orig_name.lower():
        cl["name"] = f"{orig_name} · Bridge"

    scale_t = new_dur / max(1e-6, old_dur)

    def _retime_kf_list(kfs: list[Any]) -> list[list[Any]]:
        remapped = [[round(float(k[0]) * scale_t, 6), k[1], *(k[2:3] or ["linear"])] for k in kfs]
        return _strict_kf(remapped, new_dur, fps_i)

    # Lock opacity at 100% across `t_cut_local = cut_s - new_at` and fade out cleanly in final 3 frames
    t_in_op = snap_time(min(0.14, max(2.0 / fps_i, (cut_s - new_at) * 0.65)), fps_i)
    fade_out_f = min(3, max(2, int(hold_across_frames) // 3))
    t_out_op = snap_time(max(t_in_op + 2.0 / fps_i, new_dur - fade_out_f / float(fps_i)), fps_i)
    cl["opacity"] = _strict_kf(
        [
            [0.0, 0.0, "easeOut"],
            [t_in_op, 100.0, "easeIn"],
            [t_out_op, 100.0, "linear"],
            [new_dur, 0.0, "easeIn"],
        ],
        new_dur,
        fps_i,
    )

    mot = cl.get("motion")
    if isinstance(mot, dict):
        for mk in ("position", "scale", "rotation"):
            mv = mot.get(mk)
            if isinstance(mv, list) and mv and isinstance(mv[0], (list, tuple)):
                mot[mk] = _retime_kf_list(mv)
    trk_in = cl.get("tracking")
    if isinstance(trk_in, list) and trk_in and isinstance(trk_in[0], (list, tuple)):
        cl["tracking"] = _retime_kf_list(trk_in)

    for fx in cl.get("effects") or []:
        if not isinstance(fx, dict):
            continue
        params = fx.get("params")
        if not isinstance(params, dict):
            continue
        if fx.get("effect") == "gaussian_blur" and isinstance(params.get("blurriness"), list):
            params["blurriness"] = _strict_kf(
                [
                    [0.0, 10.0, "easeOut"],
                    [t_in_op, 0.0, "easeIn"],
                    [t_out_op, 0.0, "linear"],
                    [new_dur, 6.0, "easeIn"],
                ],
                new_dur,
                fps_i,
            )
        else:
            for pk, pv in list(params.items()):
                if isinstance(pv, list) and pv and isinstance(pv[0], (list, tuple)):
                    params[pk] = _retime_kf_list(pv)

    return apply_entrance_word_spacing(cl, fps_i)  # v7.9.0: the new blur keys get their word-spacing (tracking) keys


def player3_air_cushion_slide(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 342.0),
    slide_dx_px: float = 0.0,
    slide_dy_px: float = 54.0,
    font: str = "Be Vietnam Pro",
    style: str = "ExtraBold",
    size: float = 76.0,
    color: str = "#FAFAFA",
    align: str = "center",
    glow_mode: str | None = "soft",
    name: str | None = None,
    fps: int = 60,
) -> dict[str, Any]:
    """
    `v7.0` Preset: `Player 3` Air-Cushion Bezier Slide (`Video #08`, `f_01176..f_01195`):
    Travels `>50%` distance in the first `2 frames` and glides on a `<1px/frame` air cushion across `10f`.
    """
    px, py = float(pos[0]), float(pos[1])
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    ent_s = snap_time(min(20.0 / max(30, fps), dur_s * 0.48), fps)
    t_out = snap_time(max(ent_s + 2.0 / fps, dur_s - min(0.12, dur_s * 0.18)), fps)

    pos_kf = build_player3_air_cushion_keyframes(
        [px + float(slide_dx_px), py + float(slide_dy_px)],
        [px, py],
        entrance_dur_s=ent_s,
        total_dur_s=dur_s,
        fps=fps,
    )
    scale_kf = build_player3_air_cushion_keyframes(94.0, 100.0, entrance_dur_s=ent_s, total_dur_s=t_out, fps=fps)
    if dur_s > t_out + 1.0 / fps:
        scale_kf = _strict_kf([*scale_kf, [dur_s, 101.8, "linear"]], dur_s, fps)

    return _core_text_clip(
        text=text,
        at=at,
        dur=dur_s,
        font=font,
        style=style,
        size=size,
        color=color,
        pos=(px, py),
        align=align,
        glow_mode=glow_mode,
        name=name or f"P3 Air · {clean_display_text(text)[:18]}",
        fps=fps,
        pos_kf=pos_kf,
        scale_kf=scale_kf,
        opacity_kf=[[0.0, 0.0, "easeOut"], [snap_time(min(3.0 / fps, ent_s * 0.4), fps), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 11.0, "easeOut"], [snap_time(min(5.0 / fps, ent_s * 0.6), fps), 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 6.0, "easeIn"]],
    )


SINGLE_PRESET_MAP["player3_air_cushion_slide"] = player3_air_cushion_slide
SINGLE_PRESET_MAP["player3_air_cushion"] = player3_air_cushion_slide


def compute_hero_safe_y(
    *,
    is_broll: bool = False,
    hair_top_y: float | None = None,
    has_lead: bool = True,
    has_script: bool = False,
    lead_size: float = 40.0,
    hero_size: float = 76.0,
) -> tuple[float, float, float]:
    """
    Calculate `(lead_y, hero_y, script_y)` with guaranteed zero forehead/hair collision:
      - On B-roll (`is_broll=True` and `hair_top_y is None`): relaxed editorial upper-third `(305, 402, 488)`.
      - On A-roll (`is_broll=False`):
        - Default (Rule B8 reframed speaker `reframe_y~1132`): `(252, 342, 426)`.
        - When `hair_top_y` is measured/provided (e.g. `430` or `520`): positions the lowest active text
          baseline at least `54px` above `hair_top_y`, clamped safely below TikTok status bar (`>= 188px`).
    """
    gap_lh = max(78.0, lead_size * 0.95 + hero_size * 0.68)
    gap_hs = max(82.0, hero_size * 0.72 + 30.0)

    if hair_top_y is None:
        if is_broll:
            return (305.0, 402.0, 488.0)
        return (252.0, 342.0, 426.0)

    safe_ceiling = float(hair_top_y) - 54.0
    if has_script:
        script_y = min(492.0, safe_ceiling)
        hero_y = script_y - gap_hs
        lead_y = hero_y - gap_lh
    else:
        hero_y = min(410.0 if is_broll else 372.0, safe_ceiling)
        lead_y = hero_y - gap_lh
        script_y = hero_y + gap_hs

    # Keep lead_y inside top TikTok safe margin (>= 186 px)
    min_top = 186.0 if has_lead else (196.0 - gap_lh)
    if lead_y < min_top:
        shift = min_top - lead_y
        lead_y += shift
        hero_y += shift
        script_y += shift

    return (round(lead_y, 1), round(hero_y, 1), round(script_y, 1))


def hero_skip_window(clips: Sequence[dict[str, Any]], max_spotlight_s: float = 1.45, fps: int = DEFAULT_FPS) -> tuple[float, float]:
    """Compute a subtitle `skip_window` `(t0, t1)` for a `dual_hero_pair` clip bundle."""
    if not clips:
        return (0.0, 0.0)
    t0 = min(float(c["at"]) for c in clips)
    t1 = max(float(c["at"]) + float(c["dur"]) for c in clips)
    return (max(0.0, snap_time(t0 - 0.05, fps)), snap_time(min(t1, t0 + max_spotlight_s), fps))


def dual_hero_pair(
    lead_text: str | None,
    hero_text: str,
    at: float,
    dur: float,
    *,
    is_broll: bool = False,
    hair_top_y: float | None = None,
    script_text: str | None = None,
    hero_preset: str = "elastic_pop",
    hero_font: str = "Montserrat",
    hero_style: str = "Black",
    hero_size: float = 76.0,
    hero_color: str = "#2DD4BF",
    lead_font: str = "Be Vietnam Pro",
    lead_style: str = "Bold",
    lead_size: float = 40.0,
    lead_color: str = "#FFFFFF",
    script_color: str = "#FFFFFF",
    glow_mode: str | None = "normal",
    x: float = 540.0,
    cut_times: Sequence[float] | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    Preset 10: Builds `[lead_clip, hero_clip]` (plus `script_clip` if `script_text` is set)
    with automatic A-roll vs B-roll Y-safe-zone calculation given `hair_top_y`, staggered
    choreography (`lead @ +0ms`, `hero @ +60ms`, `script @ +160ms`), ink-box width auto-fit,
    and Rule C8 cut-overrun protection.
    """
    at_s = snap_time(at, fps)
    end_s = snap_time(at_s + dur, fps)

    # Rule C8 protection: if ending within 0.50s after or right near a V1 cut, end 1 frame before cut
    if cut_times:
        nearest_cut = min((float(c) for c in cut_times), key=lambda ct: abs(end_s - ct))
        if -0.04 <= (end_s - nearest_cut) <= 0.48 and nearest_cut - at_s >= 0.34:
            end_s = snap_time(nearest_cut - 1.0 / fps, fps)

    dur_total = max(round(8 / fps, 6), snap_time(end_s - at_s, fps))
    plain_lead = strip_inline_color_tags(lead_text or "")
    plain_hero = strip_inline_color_tags(hero_text)
    eff_lead_sz = fit_font_size(plain_lead, lead_font, lead_style, lead_size) if plain_lead else lead_size
    eff_hero_sz = fit_font_size(plain_hero, hero_font, hero_style, hero_size)
    allow_script = bool(script_text and (is_broll or (hair_top_y is not None and hair_top_y >= 515.0)))
    lead_y, hero_y, script_y = compute_hero_safe_y(
        is_broll=is_broll,
        hair_top_y=hair_top_y,
        has_lead=bool(lead_text),
        has_script=allow_script,
        lead_size=eff_lead_sz,
        hero_size=eff_hero_sz,
    )

    out_clips: list[dict[str, Any]] = []
    if lead_text and str(lead_text).strip():
        lead_spans = parse_inline_color_spans(lead_text, default_color=lead_color)
        if len(lead_spans) > 1:
            out_clips.extend(
                inline_dual_hue_row(
                    lead_text, at_s, dur_total,
                    pos=(x, lead_y), base_preset="dviet_soft_up",
                    font=lead_font, style=lead_style, size=eff_lead_sz,
                    default_color=lead_color, fps=fps, glow_mode="soft",
                )
            )
        else:
            lead_col = lead_spans[0][1] if lead_spans else lead_color
            lead_clip = dviet_soft_up(
                plain_lead or lead_text,
                at_s,
                dur_total,
                pos=(x, lead_y),
                font=lead_font,
                style=lead_style,
                size=eff_lead_sz,
                color=lead_col,
                glow_mode="soft",
                name=f"Dẫn · {clean_display_text(plain_lead or lead_text)[:18]}",
                fps=fps,
            )
            out_clips.append(lead_clip)

    hero_fn = SINGLE_PRESET_MAP.get(hero_preset, elastic_pop)
    hero_stagger = snap_time(0.067, fps) if out_clips and dur_total > 0.45 else 0.0
    hero_dur = max(round(6 / fps, 6), snap_time(dur_total - hero_stagger, fps))
    hero_spans = parse_inline_color_spans(hero_text, default_color=hero_color)
    if len(hero_spans) > 1:
        out_clips.extend(
            inline_dual_hue_row(
                hero_text,
                snap_time(at_s + hero_stagger, fps),
                hero_dur,
                pos=(x, hero_y),
                base_preset=hero_preset,
                font=hero_font,
                style=hero_style,
                size=eff_hero_sz,
                default_color=hero_color,
                fps=fps,
                glow_mode=glow_mode,
            )
        )
    else:
        resolved_hero_col = hero_spans[0][1] if hero_spans else hero_color
        hero_clip = hero_fn(
            plain_hero or hero_text,
            snap_time(at_s + hero_stagger, fps),
            hero_dur,
            pos=(x, hero_y),
            font=hero_font,
            style=hero_style,
            size=eff_hero_sz,
            color=resolved_hero_col,
            glow_mode=glow_mode,
            name=f"Từ khoá · {clean_display_text(plain_hero or hero_text)[:18]}",
            fps=fps,
        )
        out_clips.append(hero_clip)

    if script_text and str(script_text).strip() and (is_broll or hair_top_y is None or hair_top_y >= 490.0):
        scr_stagger = snap_time(0.167, fps) if dur_total > 0.65 else snap_time(0.067, fps)
        scr_dur = max(round(6 / fps, 6), snap_time(dur_total - scr_stagger, fps))
        scr_clip = script_brush_accent(
            script_text,
            snap_time(at_s + scr_stagger, fps),
            scr_dur,
            pos=(x, script_y),
            color=script_color,
            glow_mode="soft",
            name=f"Nhấn · {clean_display_text(script_text)[:18]}",
            fps=fps,
        )
        out_clips.append(scr_clip)

    return out_clips


# ---------------------------------------------------------------------------
# `v6.0` `@__dviet` Wall Negative-Space Micro-Word Pop, 2-Point Wall Hop,
# Negative-Leading Kiss Hero Pair & 2x Bevel Lockup PNG Exporter
# ---------------------------------------------------------------------------

def _lowercase_preserving_inline_tags(text: str, preserve_case: bool = False) -> str:
    """100% Vietnamese NFC-safe lowercase conversion that preserves inline `[color:word]` tag names."""
    s = unicodedata.normalize("NFC", str(text or ""))
    if preserve_case or not s:
        return s

    def _repl(m: re.Match) -> str:
        return f"[{m.group(1)}:{m.group(2).lower()}]"

    out_parts: list[str] = []
    pos = 0
    for m in _INLINE_COLOR_TAG_RE.finditer(s):
        if m.start() > pos:
            out_parts.append(s[pos : m.start()].lower())
        out_parts.append(_repl(m))
        pos = m.end()
    if pos < len(s):
        out_parts.append(s[pos:].lower())
    return "".join(out_parts)


def dviet_wall_microword_pop(
    words_or_text: str | Sequence[Any],
    at: float,
    dur: float,
    *,
    cam_mode: str = "left_third",
    x: float | None = None,
    y: float = 460.0,
    tilt_deg: float = 0.0,
    is_accent: bool = False,
    is_pain: bool = False,
    polarity: str = "dark",
    color_world: str = "emerald_cream_7707",
    preserve_case: bool = False,
    font: str = "Be Vietnam Pro",
    style: str | None = None,
    size: float | None = None,
    color: str | None = None,
    glow_mode: str | None = None,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    `v6.0` `@__dviet` (`770765`) Wall Negative-Space Micro-Word Pop (ZERO bottom bar!):
      - Places **1–3 lowercase words** directly inside the **empty wall negative space**:
        - `x = 735` when `cam_mode="left_third"` (speaker framed on left Rule-of-Thirds `x=378`),
        - `x = 345` when `cam_mode="right_third"` (speaker framed on right Rule-of-Thirds `x=702`),
        - `y = 380..620` at eye/hand level.
      - Typography scale & weight:
        - Conversational pop (`is_accent=False`): `28–36pt` (`32pt`) `Be Vietnam Pro Medium` in `#FAFAFA` (`#111827` on light).
        - Spatial emphasis (`is_accent=True` or `is_pain=True`, e.g. `"chú ý"`): `52–64pt` (`58pt` 1-word / `54pt` 2–3 words)
          `Be Vietnam Pro ExtraBold` in `primary_hex` (`primary_dark_ink` on light, `pain_hex` if `is_pain`).
      - Supports `-35°..+12°` crown-tangent diagonal tilt (e.g. `"hay chuyển"` at `4.77s` of `770765`).
    """
    # Support timed sequence `[("góc", 5.10, 0.35), ("đổi", 5.45, 0.45)]` cleanly
    if isinstance(words_or_text, (list, tuple)) and words_or_text and isinstance(words_or_text[0], (list, tuple)):
        seq_clips: list[dict[str, Any]] = []
        n_seq = len(words_or_text)
        for idx, item in enumerate(words_or_text):
            w_txt = str(item[0])
            w_at = float(item[1]) if len(item) >= 2 else float(at)
            w_dur = float(item[2]) if len(item) >= 3 else float(dur)
            w_acc = bool(item[3]) if len(item) >= 4 else (is_accent or (idx == n_seq - 1 and n_seq >= 2))
            dy_step = (idx - (n_seq - 1) * 0.5) * 64.0
            dx_step = (idx - (n_seq - 1) * 0.5) * 42.0
            base_wall_x = float(x) if x is not None else (345.0 if str(cam_mode).strip().lower() == "right_third" else 735.0)
            c_item = dviet_wall_microword_pop(
                w_txt,
                w_at,
                w_dur,
                cam_mode=cam_mode,
                x=round(min(890.0, max(190.0, base_wall_x + dx_step)), 1),
                y=round(min(620.0, max(380.0, float(y) + dy_step)), 1),
                tilt_deg=tilt_deg,
                is_accent=w_acc,
                is_pain=is_pain,
                polarity=polarity,
                color_world=color_world,
                preserve_case=preserve_case,
                font=font,
                fps=fps,
            )
            if isinstance(c_item, dict):
                seq_clips.append(c_item)
        return seq_clips

    if isinstance(words_or_text, (list, tuple)):
        raw_str = " ".join(str(t) for t in words_or_text if str(t).strip())
    else:
        raw_str = str(words_or_text or "")

    formatted_txt = _lowercase_preserving_inline_tags(raw_str, preserve_case=preserve_case)
    plain_txt = strip_inline_color_tags(formatted_txt) or clean_display_text(formatted_txt)
    word_count = max(1, len(plain_txt.split()))

    _wid, world = _resolve_color_world(color_world)
    is_light = str(polarity or "dark").strip().lower() == "light"
    emph = bool(is_accent or is_pain)

    cm = str(cam_mode or "left_third").strip().lower()
    if x is not None:
        px = float(x)
    elif cm == "right_third":
        px = 345.0
    else:
        px = 735.0
    py = float(y)

    if style is not None:
        eff_style = style
    else:
        eff_style = "ExtraBold" if emph else "Medium"

    if size is not None:
        eff_size = float(size)
    elif emph:
        eff_size = 58.0 if word_count == 1 else 54.0
    else:
        eff_size = 34.0 if word_count <= 2 else 30.0

    if color is not None:
        eff_color = resolve_semantic_color(color, world["text_on_dark"])
    elif is_pain:
        eff_color = world["pain_hex"]
    elif emph:
        eff_color = world["primary_dark_ink"] if is_light else world["primary_hex"]
    else:
        eff_color = world["text_on_light"] if is_light else world["text_on_dark"]

    eff_glow = glow_mode if glow_mode is not None else ("soft" if (emph and not is_light) else "none")
    safe_wall_w = min(430.0, 2.0 * max(160.0, min(px - 65.0, 1015.0 - px)))

    use_r30 = float(dur) < R30_TIGHT_MAX_S
    if use_r30:
        dur_s, t_in, t_out, opacity_kf, blur_kf = _r30_quick_exit_timings(dur, fps=fps)
    else:
        dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
        t_in = snap_time(min(0.20, dur_s * 0.28), fps)
        t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.12, dur_s * 0.20)), fps)
        opacity_kf = [[0.0, 0.0, "easeOut"], [min(0.14, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]]
        blur_kf = [[0.0, 12.0 if emph else 9.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 6.0, "easeIn"]]

    # Clamp crown-tangent diagonal tilt inside expressive range when near bounds, animate subtle living drift
    t_deg = max(-45.0, min(25.0, float(tilt_deg)))
    rot_kf: float | list[list[Any]] | None = None
    if abs(t_deg) > 0.05:
        rot_kf = [
            [0.0, round(t_deg - 1.4, 2), "easeOut"],
            [t_in, round(t_deg, 2), "easeIn"],
            [dur_s, round(t_deg + (0.6 if t_deg >= 0 else -0.6), 2), "linear"],
        ]

    dy_in = 18.0 if emph else 14.0
    s_in = 90.0 if emph else 95.0
    return _core_text_clip(
        text=plain_txt,
        at=at,
        dur=dur_s,
        font=font,
        style=eff_style,
        size=eff_size,
        color=eff_color,
        pos=(px, py),
        align="center",
        glow_mode=eff_glow,
        rotation=rot_kf,
        max_width_px=safe_wall_w,
        shadow_overrides={"opacity": 68.0 if not is_light else 24.0, "blur": 11.0, "distance": 3.0},
        name=name or f"Tường · {plain_txt[:16]}",
        fps=fps,
        pos_kf=[[0.0, [px, py + dy_in], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.5], "linear"]],
        scale_kf=[[0.0, s_in, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=opacity_kf,
        blur_kf=blur_kf,
    )


def dviet_two_point_wall_hop(
    word1: str,
    word2: str,
    at: float,
    dur: float,
    *,
    hop_offset_s: float | None = None,
    cam_mode: str = "left_third",
    pos1: Sequence[float] | None = None,
    pos2: Sequence[float] | None = None,
    y1: float = 432.0,
    y2: float = 524.0,
    dx_hop: float = 64.0,
    tilt1_deg: float = -5.5,
    tilt2_deg: float = 3.5,
    color_world: str = "emerald_cream_7707",
    polarity: str = "dark",
    first_is_accent: bool = False,
    second_is_accent: bool = True,
    second_is_pain: bool = False,
    preserve_case: bool = False,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    `v6.0` `@__dviet` (`770765`) 2-Point Spatial Wall Hop (e.g. `"góc"` -> `"đổi"`):
      - Hop 1 (`word1`) pops in upper wall negative space `(x1, y1)` in crisp `#FAFAFA` `Medium`.
      - Hop 2 (`word2`) hops diagonally across the wall to `(x2, y2)` in `primary_hex` `58pt ExtraBold`!
    """
    at_s = snap_time(at, fps)
    dur_total = max(round(10 / fps, 6), snap_time(dur, fps))
    h_off = snap_time(float(hop_offset_s) if hop_offset_s is not None else min(0.34, dur_total * 0.42), fps)
    h_off = max(round(3 / fps, 6), min(snap_time(dur_total - 5 / fps, fps), h_off))

    cm = str(cam_mode or "left_third").strip().lower()
    base_wx = 345.0 if cm == "right_third" else 735.0
    p1 = (float(pos1[0]), float(pos1[1])) if pos1 is not None else (round(base_wx - dx_hop * 0.45, 1), float(y1))
    p2 = (float(pos2[0]), float(pos2[1])) if pos2 is not None else (round(base_wx + dx_hop * 0.55, 1), float(y2))

    # Word 1 stays slightly into Word 2's arrival for visual continuity, or holds softly above it
    dur_1 = max(round(5 / fps, 6), snap_time(min(dur_total, h_off + 0.28), fps))
    dur_2 = max(round(5 / fps, 6), snap_time(dur_total - h_off, fps))

    c1 = dviet_wall_microword_pop(
        word1,
        at_s,
        dur_1,
        cam_mode=cam_mode,
        x=p1[0],
        y=p1[1],
        tilt_deg=tilt1_deg,
        is_accent=first_is_accent,
        polarity=polarity,
        color_world=color_world,
        preserve_case=preserve_case,
        name=f"Nhảy 1 · {_lowercase_preserving_inline_tags(word1, preserve_case)[:14]}",
        fps=fps,
    )
    c2 = dviet_wall_microword_pop(
        word2,
        snap_time(at_s + h_off, fps),
        dur_2,
        cam_mode=cam_mode,
        x=p2[0],
        y=p2[1],
        tilt_deg=tilt2_deg,
        is_accent=second_is_accent,
        is_pain=second_is_pain,
        polarity=polarity,
        color_world=color_world,
        preserve_case=preserve_case,
        name=f"Nhảy 2 · {_lowercase_preserving_inline_tags(word2, preserve_case)[:14]}",
        fps=fps,
    )
    out: list[dict[str, Any]] = []
    if isinstance(c1, dict):
        out.append(c1)
    if isinstance(c2, dict):
        out.append(c2)
    return out


def dviet_kiss_hero_pair(
    lead_text: str | None,
    hero_text: str,
    at: float,
    dur: float,
    *,
    color_world: str = "emerald_cream_7707",
    polarity: str = "dark",
    is_pain: bool = False,
    preserve_case: bool = False,
    is_broll: bool = False,
    hair_top_y: float | None = None,
    x: float = 540.0,
    hero_y_override: float | None = None,
    line_height: float = 0.80,
    kiss_gap_px: float | None = None,
    lead_font: str = "Be Vietnam Pro",
    lead_style: str = "Regular",
    lead_size: float = 30.0,
    lead_color: str | None = None,
    hero_preset: str = "dviet_soft_up",
    hero_font: str = "Be Vietnam Pro",
    hero_style: str = "Black",
    hero_size: float = 92.0,
    hero_color: str | None = None,
    glow_mode: str | None = "normal",
    cut_times: Sequence[float] | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    `v6.0` `@__dviet` (`770765`) Negative-Leading Kiss Hero Pair for native `.fcproj`:
      - **Lowercase by default** (`preserve_case=False`), `lead_size=30pt Regular` `#FAFAFA` +
        `hero_size=92pt Black` in `color_world` `primary_hex` (`scale_ratio ≈ 3.07x`!).
      - Tightens vertical leading `hero_y - lead_y` from `+88px` down to **`~54px`** (`line_height ≈ 0.80`)
        with a crisp dark occlusion cushion shadow on `lead_clip` so lead & hero fuse into one sculptural unit!
    """
    _wid, world = _resolve_color_world(color_world)
    is_light = str(polarity or "dark").strip().lower() == "light"

    eff_lead_col = resolve_semantic_color(
        lead_color or (world["text_on_light"] if is_light else world["text_on_dark"]),
        "#FAFAFA",
    )
    eff_hero_col = resolve_semantic_color(
        hero_color or (world["pain_hex"] if is_pain else (world["primary_dark_ink"] if is_light else world["primary_hex"])),
        "#2EE86E",
    )

    at_s = snap_time(at, fps)
    end_s = snap_time(at_s + dur, fps)
    if cut_times:
        nearest_cut = min((float(c) for c in cut_times), key=lambda ct: abs(end_s - ct))
        if -0.04 <= (end_s - nearest_cut) <= 0.48 and nearest_cut - at_s >= 0.34:
            end_s = snap_time(nearest_cut - 1.0 / fps, fps)
    dur_total = max(round(8 / fps, 6), snap_time(end_s - at_s, fps))

    fmt_lead = _lowercase_preserving_inline_tags(lead_text or "", preserve_case=preserve_case)
    fmt_hero = _lowercase_preserving_inline_tags(hero_text, preserve_case=preserve_case)
    plain_lead = strip_inline_color_tags(fmt_lead)
    plain_hero = strip_inline_color_tags(fmt_hero)

    eff_lead_sz = fit_font_size(plain_lead, lead_font, lead_style, lead_size) if plain_lead else float(lead_size)
    eff_hero_sz = fit_font_size(plain_hero, hero_font, hero_style, hero_size)

    # Tight negative-leading delta: ~54.0px at (30pt Regular + 92pt Black, line_height=0.80)!
    gap_kiss = (
        float(kiss_gap_px)
        if kiss_gap_px is not None
        else round(max(42.0, (eff_lead_sz * 0.42 + eff_hero_sz * 0.45) * (float(line_height) / 0.80)), 1)
    )

    if hero_y_override is not None:
        hero_y = round(float(hero_y_override), 1)
    elif hair_top_y is not None:
        hero_y = round(max(242.0, min(410.0 if is_broll else 372.0, float(hair_top_y) - 54.0)), 1)
    else:
        hero_y = 396.0 if is_broll else 338.0
    lead_y = round(hero_y - gap_kiss, 1)
    if lead_y < 186.0:
        shift = 186.0 - lead_y
        lead_y = round(lead_y + shift, 1)
        hero_y = round(hero_y + shift, 1)

    out_clips: list[dict[str, Any]] = []
    if plain_lead.strip():
        t_in_l = snap_time(min(0.20, dur_total * 0.28), fps)
        t_out_l = snap_time(max(t_in_l + 2 / fps, dur_total - min(0.14, dur_total * 0.20)), fps)
        lead_clip = _core_text_clip(
            text=plain_lead,
            at=at_s,
            dur=dur_total,
            font=lead_font,
            style=lead_style,
            size=eff_lead_sz,
            color=eff_lead_col,
            pos=(x, lead_y),
            align="center",
            glow_mode="none",
            lock_size=True,
            # Occlusion cushion shadow so 30pt white lead reads razor-sharp kissing 92pt hero ascenders
            shadow_overrides={"opacity": 92.0 if not is_light else 28.0, "blur": 9.0, "distance": 2.0},
            name=f"Dẫn sát · {plain_lead[:18]}",
            fps=fps,
            pos_kf=[[0.0, [x, lead_y + 12.0], "easeOut"], [t_in_l, [x, lead_y], "easeIn"], [dur_total, [x, lead_y - 4.0], "linear"]],
            scale_kf=[[0.0, 96.0, "easeOut"], [t_in_l, 100.0, "easeIn"], [t_out_l, 102.4, "linear"], [dur_total, 103.2, "linear"]],
            opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_in_l), 100.0, "easeIn"], [t_out_l, 100.0, "linear"], [dur_total, 0.0, "easeIn"]],
            blur_kf=[[0.0, 9.0, "easeOut"], [t_in_l, 0.0, "easeIn"], [t_out_l, 0.0, "linear"], [dur_total, 6.0, "easeIn"]],
        )
        out_clips.append(lead_clip)

    hero_fn = SINGLE_PRESET_MAP.get(hero_preset, dviet_soft_up)
    hero_stagger = snap_time(0.067, fps) if out_clips and dur_total > 0.45 else 0.0
    hero_dur = max(round(6 / fps, 6), snap_time(dur_total - hero_stagger, fps))
    eff_hero_glow = "none" if is_light else glow_mode

    hero_spans = parse_inline_color_spans(fmt_hero, default_color=eff_hero_col)
    if len(hero_spans) > 1:
        out_clips.extend(
            inline_dual_hue_row(
                fmt_hero,
                snap_time(at_s + hero_stagger, fps),
                hero_dur,
                pos=(x, hero_y),
                base_preset=hero_preset,
                font=hero_font,
                style=hero_style,
                size=eff_hero_sz,
                default_color=eff_hero_col,
                fps=fps,
                glow_mode=eff_hero_glow,
            )
        )
    else:
        resolved_h_col = hero_spans[0][1] if hero_spans else eff_hero_col
        hero_clip = hero_fn(
            plain_hero,
            snap_time(at_s + hero_stagger, fps),
            hero_dur,
            pos=(x, hero_y),
            font=hero_font,
            style=hero_style,
            size=eff_hero_sz,
            color=resolved_h_col,
            glow_mode=eff_hero_glow,
            name=f"Đỉnh sát · {plain_hero[:18]}",
            fps=fps,
        )
        out_clips.append(hero_clip)

    return out_clips


LEGACY_PIL_BEVEL_VETO_MSG = (
    "[v7.0 VETO — PLASTIC_PIL_3D_BEVEL_BANNED] Calling `render_dviet_3d_extruded_bevel_word` "
    "(thick plastic PIL 3D extruded bevel) is blocked in Universal Studio Director v7.0! "
    "45,582-frame native audit confirmed 0% thick plastic PIL bevels. "
    "— Fix: Use `scripts/tools/web_plate_builder.py` (HTML5/CSS3/SVG crisp vector plates) "
    "or clean flat optical typography (`dviet_kiss_hero_pair`, `player3_air_cushion_slide`, `dviet_soft_up`, "
    "or `export_dviet_bevel_lockup_png(..., extrude_px=0.0)`)."
)


def render_dviet_3d_extruded_bevel_word(*args: Any, **kwargs: Any) -> Any:
    """
    `v7.0` Hard Veto Gatekeeper against legacy thick-plastic PIL `render_dviet_3d_extruded_bevel_word`.
    Always emits a `UserWarning` and raises `RuntimeError` directing callers to `web_plate_builder.py`
    (`HTML5/CSS3/SVG`) or clean flat optical typography!
    """
    warnings.warn(LEGACY_PIL_BEVEL_VETO_MSG, UserWarning, stacklevel=2)
    raise RuntimeError(LEGACY_PIL_BEVEL_VETO_MSG)


STATIC_HERO_PNG_VETO_MSG = (
    "[v7.1 VETO — STATIC_HERO_PNG_STAMP] Calling `export_dviet_bevel_lockup_png` without "
    "`allow_static_thumbnail=True` is blocked in Universal Studio Director v7.1! "
    "Static `.png` hero stamps (`c01..c15.png`) freeze multi-clause sentences onto the timeline prematurely. "
    "— Fix: Use `plan_dviet_kinetic_beat_schedule(...)` + `web_plate_builder.render_kinetic_typo_batch(...)` "
    "(animated ProRes 4444 `.mov` plates locked to syllable onsets) or native animated `dviet_kiss_hero_pair`, "
    "OR pass `allow_static_thumbnail=True` strictly for single static cover/thumbnail export."
)


def export_dviet_bevel_lockup_png(
    out_path: str | Path,
    hero_text: str,
    lead_text: str | None = None,
    *,
    at: float = 0.0,
    dur: float = 1.6,
    center_xy: Sequence[float] = (540.0, 355.0),
    canvas_size: tuple[int, int] = (1080, 1920),
    color_world: str = "emerald_cream_7707",
    polarity: str = "dark",
    is_pain: bool = False,
    hero_color: str | None = None,
    lead_color: str | None = None,
    hero_font: str = "Be Vietnam Pro",
    hero_style: str = "Black",
    hero_size: int = 98,
    lead_font: str = "Be Vietnam Pro",
    lead_style: str = "Medium",
    lead_size: int = 32,
    line_height: float = 0.78,
    extrude_px: float = 0.0,
    allow_legacy_pil_bevel: bool = False,
    allow_static_thumbnail: bool = False,
    preserve_case: bool = False,
    tilt_deg: float = 0.0,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    `v7.1` Clean Optical Thumbnail Lockup PNG Exporter (`allow_static_thumbnail=False` default veto!):
      - Vetoes static PIL `.png` hero stamps on timeline beats unless `allow_static_thumbnail=True`.
      - If `extrude_px > 0.0` and `not allow_legacy_pil_bevel`: raises `RuntimeError` + `UserWarning`
        blocking thick plastic `render_dviet_3d_extruded_bevel_word`.
      - When `allow_static_thumbnail=True` and `extrude_px <= 0.0`: renders a razor-sharp 2x-supersampled
        flat optical kiss lockup PNG for cover thumbnails and strips PNG metadata cleanly on disk.
      - v7.9.0 repair: the timeline entrance keeps its gaussian blur (12 -> 0 in, 0 -> 6 out) but a static PNG cannot widen its
        word spacing, so the timeline gets `gfx_clips`: ONE clip per word (`<stem>__w<line><i>.png`, same canvas / anchor / scale
        / opacity / blur keys) whose position keys spread the words apart with the blur by the helper's word spacing
        (`motion_gate.entrance_word_spacing_em(blur, min(scale, 1), size, resting gap)`) and bring them back to rest as the blur
        reaches 0, so every frame keeps the ink gap minus 2 x blur >= 0.25 em. `path` stays the full lockup (the thumbnail).
    """
    if not allow_static_thumbnail:
        warnings.warn(STATIC_HERO_PNG_VETO_MSG, UserWarning, stacklevel=2)
        raise RuntimeError(STATIC_HERO_PNG_VETO_MSG)
    if float(extrude_px) > 0.0 and not allow_legacy_pil_bevel:
        warnings.warn(LEGACY_PIL_BEVEL_VETO_MSG, UserWarning, stacklevel=2)
        raise RuntimeError(LEGACY_PIL_BEVEL_VETO_MSG)

    wid, world = _resolve_color_world(color_world)
    is_light = str(polarity or "dark").strip().lower() == "light"
    eff_hero_hex = resolve_semantic_color(
        hero_color or (world["pain_hex"] if is_pain else (world["primary_dark_ink"] if is_light else world["primary_hex"])),
        "#2EE86E",
    )
    eff_lead_hex = resolve_semantic_color(
        lead_color or (world["text_on_light"] if is_light else world["text_on_dark"]),
        "#FAFAFA",
    )

    h_font_path = _resolve_typo_font_path(hero_font, hero_style)
    l_font_path = _resolve_typo_font_path(lead_font, lead_style)
    w_cv, h_cv = int(canvas_size[0]), int(canvas_size[1])
    cx, cy = float(center_xy[0]), float(center_xy[1])

    # Render clean 2x-supersampled flat optical typography (zero plastic PIL bevel!)
    ss = 2
    hi_img = Image.new("RGBA", (w_cv * ss, h_cv * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(hi_img)
    fmt_hero = clean_display_text(strip_inline_color_tags(_lowercase_preserving_inline_tags(hero_text, preserve_case)))
    fmt_lead = clean_display_text(strip_inline_color_tags(_lowercase_preserving_inline_tags(lead_text or "", preserve_case))) if lead_text else ""

    f_hero = ImageFont.truetype(h_font_path, max(16, int(round(hero_size * ss))))
    f_lead = ImageFont.truetype(l_font_path, max(12, int(round(lead_size * ss))))

    def _hex_rgba(hx: str, alpha: int = 255) -> tuple[int, int, int, int]:
        s_h = hx.lstrip("#")
        return (int(s_h[0:2], 16), int(s_h[2:4], 16), int(s_h[4:6], 16), alpha)

    cx_s, cy_s = cx * ss, cy * ss
    # (text, font, size px, baseline y, shadow dy, shadow alpha, rgba) per line, drawn centred on cx (anchor "ms")
    if fmt_lead.strip():
        gap_s = (lead_size * 0.42 + hero_size * 0.45) * (float(line_height) / 0.80) * ss
        ly_s = cy_s - 0.5 * gap_s
        hy_s = cy_s + 0.5 * gap_s
        lines = [(fmt_lead, f_lead, l_font_path, float(lead_size), ly_s, 3, 128, _hex_rgba(eff_lead_hex)),
                 (fmt_hero, f_hero, h_font_path, float(hero_size), hy_s, 5, 148, _hex_rgba(eff_hero_hex))]
    else:
        lines = [(fmt_hero, f_hero, h_font_path, float(hero_size), cy_s, 5, 148, _hex_rgba(eff_hero_hex))]
    for txt_l, ft_l, _fp, _sz, y_l, sh_dy, sh_a, rgba_l in lines:
        draw.text((cx_s, y_l + sh_dy * ss), txt_l, font=ft_l, fill=(0, 0, 0, sh_a), anchor="ms")
        draw.text((cx_s, y_l), txt_l, font=ft_l, fill=rgba_l, anchor="ms")

    def _finish(img: Image.Image) -> Image.Image:
        if abs(float(tilt_deg)) > 0.05:
            img = img.rotate(-float(tilt_deg), resample=Image.Resampling.BICUBIC, center=(cx_s, cy_s))
        return img.resize((w_cv, h_cv), resample=Image.Resampling.LANCZOS)

    def _save_png(img: Image.Image, path: Path) -> None:
        img.save(path, format="PNG", optimize=True)
        # v7.9.1: shared helper (strip-media-metadata skill, else a PIL re-save; warns loudly when both fail)
        _wpb().strip_media_metadata(path, keep_icc=False)

    rgba = _finish(hi_img)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    _save_png(rgba, out_p)

    # v7.9.0 repair: one PNG per word at its resting place (with its shadow) for the spreading timeline clips
    word_layers = []  # (png path, line index, word index, words in line, font px, natural gap em)
    mg = _motion_gate()
    for li, (txt_l, ft_l, fp_l, sz_l, y_l, sh_dy, sh_a, rgba_l) in enumerate(lines):
        words_l = txt_l.split(" ")
        nat_l = mg.natural_word_gap_em(txt_l, fp_l, 0.0)
        x_left = cx_s - 0.5 * ft_l.getlength(txt_l)
        pos = 0
        for wi, word in enumerate(words_l):
            if word:
                img_w = Image.new("RGBA", (w_cv * ss, h_cv * ss), (0, 0, 0, 0))
                d_w = ImageDraw.Draw(img_w)
                x_w = x_left + (ft_l.getlength(txt_l[:pos]) if pos else 0.0)
                d_w.text((x_w, y_l + sh_dy * ss), word, font=ft_l, fill=(0, 0, 0, sh_a), anchor="ls")
                d_w.text((x_w, y_l), word, font=ft_l, fill=rgba_l, anchor="ls")
                p_w = out_p.with_name(f"{out_p.stem}__w{li}{wi:02d}.png")
                _save_png(_finish(img_w), p_w)
                word_layers.append((p_w, li, wi, len(words_l), sz_l, None if nat_l is None else nat_l - WS_NAT_MARGIN_EM))
            pos += len(word) + 1

    at_s = max(0.0, snap_time(at, fps))
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.16, dur_s * 0.22)), fps)
    mid_x, mid_y = w_cv * 0.5, h_cv * 0.5

    pos_kf = [[0.0, [mid_x, mid_y + 22.0], "easeOut"], [t_in, [mid_x, mid_y], "easeIn"], [dur_s, [mid_x, mid_y - 5.0], "linear"]]
    scale_kf = [[0.0, 94.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.2, "linear"], [dur_s, 103.0, "linear"]]
    blur_kf = [[0.0, 12.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 6.0, "easeIn"]]
    cos_t, sin_t = math.cos(math.radians(float(tilt_deg))), math.sin(math.radians(float(tilt_deg)))

    def _pos_at(t: float) -> list[float]:
        xs = [[k[0], k[1][0]] for k in pos_kf]
        ys = [[k[0], k[1][1]] for k in pos_kf]
        return [_kf_value(xs, t), _kf_value(ys, t)]

    def _word_clip(p_w: Path, li: int, wi: int, n_w: int, size: float, nat: float | None) -> dict[str, Any]:
        keys = []
        for t, _b, interp in blur_kf:  # the spread follows the blur keys and their easing
            sc = _kf_value(scale_kf, t, 100.0) / 100.0
            em = mg.entrance_word_spacing_em(_kf_value(blur_kf, t), min(sc, 1.0), size, nat) if nat is not None else 0.0
            off = (wi - (n_w - 1) / 2.0) * em * size * sc  # canvas px: each gap widens by em x size x scale
            x0, y0 = _pos_at(t)
            keys.append([t, [round(x0 + off * cos_t, 3), round(y0 + off * sin_t, 3)], interp])
        return {
            "name": f"Flat Optical · {clean_display_text(hero_text)[:18]} · w{li}{wi:02d}",
            "src": str(p_w.resolve()),
            "at": at_s,
            "dur": dur_s,
            "word_line": li,
            "word_index": wi,
            "word_count": n_w,
            "font_px": size,
            "motion": {"anchor": [cx, cy], "position": _strict_kf(keys, dur_s, fps), "scale": _strict_kf(scale_kf, dur_s, fps)},
            "opacity": _strict_kf(
                [[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
                dur_s, fps,
            ),
            "effects": [{"effect": "gaussian_blur", "params": {"blurriness": _strict_kf(blur_kf, dur_s, fps)}}],
        }

    gfx_clips = [_word_clip(*wl) for wl in word_layers]

    return {
        "path": str(out_p.resolve()),
        "width": w_cv,
        "height": h_cv,
        "world_id": wid,
        "hero_hex": eff_hero_hex,
        "lead_hex": eff_lead_hex,
        "gfx_clips": gfx_clips,
    }


SINGLE_PRESET_MAP["dviet_wall_microword_pop"] = dviet_wall_microword_pop
SINGLE_PRESET_MAP["wall_microword_pop"] = dviet_wall_microword_pop


# ---------------------------------------------------------------------------
# 11 & 12. Word-Locked Captions (`conversational_captions_2line` & `minimal_single_line_captions`)
# ---------------------------------------------------------------------------

def _normalize_words_tl(words_tl: Any) -> list[tuple[str, float, float]]:
    """
    Preserve raw punctuation on tokens for linguistic boundary analysis; display sanitizer runs on output text.
    `v7.1`: Seamlessly accepts:
      1. `[[word, start_s, end_s], ...]`
      2. `[{"word": ..., "start_ms": ..., "end_ms": ...}, ...]`
      3. `transcript_ms.json` dicts (`{"words_nfc": [...]}` or `{"segments": [{"words": [...]}]}`)
      4. `Path` or JSON file path string pointing to `words_tl.json` / `transcript_ms.json`.
    """
    if words_tl is None:
        return []
    raw_source: Any = words_tl
    if isinstance(raw_source, (str, Path)):
        p_cand = Path(str(raw_source)).expanduser()
        if p_cand.is_file():
            try:
                raw_source = json.loads(p_cand.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
        else:
            return []

    if isinstance(raw_source, dict):
        if isinstance(raw_source.get("words_nfc"), list):
            raw_items: Sequence[Any] = raw_source["words_nfc"]
        elif isinstance(raw_source.get("words"), list):
            raw_items = raw_source["words"]
        elif isinstance(raw_source.get("segments"), list):
            flat_seg_words: list[Any] = []
            for seg in raw_source["segments"]:
                if isinstance(seg, dict) and isinstance(seg.get("words"), list):
                    flat_seg_words.extend(seg["words"])
            raw_items = flat_seg_words
        else:
            return []
    elif isinstance(raw_source, (list, tuple)):
        if raw_source and isinstance(raw_source[0], dict) and "words" in raw_source[0] and "word" not in raw_source[0]:
            flat_list_words: list[Any] = []
            for seg in raw_source:
                if isinstance(seg, dict) and isinstance(seg.get("words"), list):
                    flat_list_words.extend(seg["words"])
            raw_items = flat_list_words
        else:
            raw_items = raw_source
    else:
        return []

    out: list[tuple[str, float, float]] = []
    for w in raw_items:
        if isinstance(w, dict):
            tok = unicodedata.normalize(
                "NFC",
                str(w.get("word") if w.get("word") is not None else (w.get("text") if w.get("text") is not None else w.get("w", ""))),
            ).strip()
            if not tok:
                continue
            if w.get("start_ms") is not None or w.get("tl_start_ms") is not None:
                ms0 = float(w["start_ms"] if w.get("start_ms") is not None else w["tl_start_ms"])
                ms1_raw = w.get("end_ms") if w.get("end_ms") is not None else w.get("tl_end_ms")
                t0 = ms0 / 1000.0
                t1 = (float(ms1_raw) / 1000.0) if ms1_raw is not None else (t0 + 0.18)
            else:
                s0_raw = w.get("start") if w.get("start") is not None else (w.get("s") if w.get("s") is not None else (w.get("dst_in") if w.get("dst_in") is not None else w.get("at")))
                if s0_raw is None:
                    continue
                t0 = float(s0_raw)
                s1_raw = w.get("end") if w.get("end") is not None else (w.get("e") if w.get("e") is not None else w.get("dst_out"))
                t1 = float(s1_raw) if s1_raw is not None else (t0 + 0.18)
            out.append((tok, round(t0, 6), round(max(t0 + 0.04, t1), 6)))
        elif isinstance(w, (list, tuple)) and len(w) >= 2:
            tok = unicodedata.normalize("NFC", str(w[0])).strip()
            if not tok:
                continue
            t0 = float(w[1])
            t1 = float(w[2]) if len(w) >= 3 else (t0 + 0.18)
            out.append((tok, t0, max(t0 + 0.04, t1)))
    return sorted(out, key=lambda item: item[1])


def _build_free_segments(
    total_dur: float,
    cut_times: Sequence[float] | None,
    skip_windows: Sequence[Sequence[float]] | None,
    fps: int = DEFAULT_FPS,
) -> list[tuple[float, float]]:
    """
    Partition `[0.0, total_dur]` at every V1 `cut_time` AND subtract every `skip_window`
    so captions NEVER cross a shot cut and NEVER overlap a Hero/Diagram window!
    Allows tight segments down to `R30_MIN_CHUNK_S` (`0.18s`).
    """
    min_seg = snap_time(R30_MIN_CHUNK_S, fps) - 1e-6
    cuts = sorted({0.0, *[snap_time(float(c), fps) for c in (cut_times or ()) if 0.0 < float(c) < total_dur], snap_time(total_dur, fps)})
    raw_segs = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1) if cuts[i + 1] - cuts[i] >= min_seg]

    if not skip_windows:
        return raw_segs

    skips = sorted((float(a), float(b)) for a, b in skip_windows if float(b) > float(a))
    carved: list[tuple[float, float]] = []
    for sa, sb in raw_segs:
        pieces = [(sa, sb)]
        for ka, kb in skips:
            next_pieces: list[tuple[float, float]] = []
            for pa, pb in pieces:
                if kb <= pa or ka >= pb:
                    next_pieces.append((pa, pb))
                else:
                    if ka - pa >= min_seg:
                        next_pieces.append((pa, snap_time(ka, fps)))
                    if pb - kb >= min_seg:
                        next_pieces.append((snap_time(kb, fps), pb))
            pieces = next_pieces
        carved.extend(pieces)
    return carved


def _cap_sentence_case(s: str) -> str:
    s = clean_display_text(s)
    return (s[0].upper() + s[1:]) if s else s


def conversational_captions_2line(
    words_tl: Sequence[Sequence[Any]],
    *,
    skip_windows: Sequence[Sequence[float]] | None = None,
    cut_times: Sequence[float] | None = None,
    total_dur: float | None = None,
    y_single: float = 1392.0,
    y_line1: float = 1358.0,
    y_line2: float = 1432.0,
    x: float = 540.0,
    size_single: float = 54.0,
    size_pair: float = 52.0,
    max_words_per_group: int = 6,
    pause_split_s: float = 0.52,
    accent_colors: Sequence[str] | None = None,
    font_cycle: Sequence[tuple[str, str]] | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, list[dict[str, Any]]]:
    """
    Preset 11: Word-locked 2-line conversational subtitles (`v5.1`):
      - Smart Compound/Lead/Trail Chunk Lookahead (`+1` word if gap `< 0.35s`, or `-1` step-back).
      - Linguistic & `getbbox` pixel-balanced 2-line split (`split_phrase_2line`) with natural lowercase Line 2.
      - Ruling `R209` Safe-Bottom Auto-Flip on `y >= 1360.0` (`y_single`, `y_line2`).
      - Ruling `R30` 2-frame quick exit (`>= 3` frames at `100%` opacity) on tight chunks (`0.18s <= dur < 0.32s`).
      - Returns `{"line1": [...], "line2": [...], "clips": [...]}` ready for `text_low 1` & `text_low 2`.
    """
    words = _normalize_words_tl(words_tl)
    if not words:
        return {"line1": [], "line2": [], "clips": []}

    end_tl = float(total_dur) if total_dur is not None else (max(w[2] for w in words) + 0.35)
    colors = list(accent_colors or ["#2DD4BF", "#FFC414", "#38BDF8", "#60A5FA"])
    fonts = list(font_cycle or [("Montserrat", "Bold"), ("Be Vietnam Pro", "Bold"), ("Be Vietnam Pro", "ExtraBold")])

    segments = _build_free_segments(end_tl, cut_times, skip_windows, fps=fps)
    line1_clips: list[dict[str, Any]] = []
    line2_clips: list[dict[str, Any]] = []
    chunk_idx = 0
    one_frame = 1.0 / fps
    min_chunk_s = snap_time(R30_MIN_CHUNK_S, fps) - 1e-6

    size_single = max(float(size_single), G2_TEXT_FLOOR_PX)  # v7.9.1: G2 reading text obeys the 64 px floor
    size_pair = max(float(size_pair), G2_TEXT_FLOOR_PX)
    for seg_a, seg_b in segments:
        seg_ws = [w for w in words if seg_a - 0.01 <= w[1] < seg_b - 0.04]
        ptr = 0
        while ptr < len(seg_ws):
            next_ptr = _smart_chunk_end(seg_ws, ptr, max_words_per_group, pause_split_s)
            f_fam0, f_sty0 = fonts[chunk_idx % len(fonts)]
            next_ptr = _g2_chunk_end_at_floor(seg_ws, ptr, next_ptr, font=f_fam0, style=f_sty0, size=size_pair, two_line=True)
            grp = seg_ws[ptr:next_ptr]
            ptr = next_ptr

            t_start = max(seg_a, snap_time(grp[0][1], fps))
            hard_ceil = snap_time(seg_b - one_frame, fps)
            next_t = snap_time(seg_ws[ptr][1] - one_frame, fps) if ptr < len(seg_ws) else hard_ceil
            t_end = min(hard_ceil, next_t, snap_time(grp[-1][2] + 0.35, fps))

            if t_end - t_start < R30_TIGHT_MAX_S:
                t_end = min(hard_ceil, next_t, snap_time(t_start + 0.33, fps))
            if t_end - t_start < min_chunk_s:
                continue

            dur_chunk = snap_time(t_end - t_start, fps)
            is_tight = dur_chunk < R30_TIGHT_MAX_S
            f_fam, f_sty = fonts[chunk_idx % len(fonts)]
            c_col = colors[chunk_idx % len(colors)]

            if len(grp) <= 3 or is_tight:
                txt1 = _cap_sentence_case(" ".join(w[0] for w in grp))
                line1_clips.append(
                    dviet_soft_up(
                        txt1, t_start, dur_chunk,
                        pos=(x, y_single), font=f_fam, style=f_sty, size=size_single,
                        color="#FFFFFF", glow_mode="none", quick_exit=is_tight,
                        name=f"Phụ đề · {txt1[:18]}", fps=fps,
                    )
                )
            else:
                grp_toks = [w[0] for w in grp]
                split_k = _best_2line_split_index(grp_toks, font=f_fam, style=f_sty, size=size_pair)
                txt1, txt2 = split_phrase_2line(grp_toks, font=f_fam, style=f_sty, size=size_pair)
                l2_ws = grp[split_k:]

                t_l2 = max(snap_time(t_start + 0.10, fps), snap_time(l2_ws[0][1], fps))
                if t_end - t_l2 < snap_time(0.20, fps):
                    t_l2 = max(t_start, snap_time(t_end - 0.20, fps))
                dur_l2 = snap_time(t_end - t_l2, fps)

                line1_clips.append(
                    dviet_soft_up(
                        txt1, t_start, dur_chunk,
                        pos=(x, y_line1), font=f_fam, style=f_sty, size=size_pair,
                        color="#FFFFFF", glow_mode="none", quick_exit=(dur_chunk < R30_TIGHT_MAX_S),
                        name=f"Phụ đề 1 · {txt1[:16]}", fps=fps,
                    )
                )
                line2_clips.append(
                    dviet_soft_up(
                        txt2, t_l2, dur_l2,
                        pos=(x, y_line2), font=f_fam, style=f_sty, size=size_pair,
                        color=c_col, glow_mode="soft", quick_exit=(dur_l2 < R30_TIGHT_MAX_S),
                        name=f"Phụ đề 2 · {txt2[:16]}", fps=fps,
                    )
                )
            chunk_idx += 1

    return {"line1": line1_clips, "line2": line2_clips, "clips": line1_clips + line2_clips}


def minimal_single_line_captions(
    words_tl: Sequence[Sequence[Any]],
    *,
    skip_windows: Sequence[Sequence[float]] | None = None,
    cut_times: Sequence[float] | None = None,
    total_dur: float | None = None,
    pos: Sequence[float] = (540.0, 1440.0),
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 44.0,
    color: str = "#F1F5F9",
    max_words_per_group: int = 5,
    pause_split_s: float = 0.45,
    glow_mode: str | None = "none",
    whisper_mode: bool | None = None,
    style_profile: str | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    Preset 12: Clean 1-line subtle captions (`v6.0` Whisper Mode Ready):
      - `whisper_mode` (defaults to `True` when `style_profile="dviet"`, `False` otherwise):
        switches captions to `style="Regular", y=1590.0` monochrome `#FAFAFA` / `#E8D98C` (v7.9.1: size floored to 64 px, was 26)
        (`0` loud `48px` Bold neon chest bar!).
      - Smart Compound/Lead/Trail Chunk Lookahead (`+1` word if gap `< 0.35s`, or `-1` step-back).
      - Ruling `R209` Safe-Bottom Auto-Flip when `pos[1] >= 1360.0` (`py - 18.0 -> py -> py - 3.0`).
      - Ruling `R30` 2-frame quick exit (`>= 3` frames at `100%` opacity) on tight chunks (`0.18s <= dur < 0.32s`).
    """
    words = _normalize_words_tl(words_tl)
    if not words:
        return []

    is_dviet_profile = str(style_profile or "").strip().lower() in ("dviet", "dviet_7707", "dviet_v6", "@__dviet")
    use_whisper = bool(whisper_mode) if whisper_mode is not None else is_dviet_profile

    px = float(pos[0])
    py = 1590.0 if (use_whisper and float(pos[1]) in (1440.0, 1428.0)) else float(pos[1])
    eff_style = "Regular" if (use_whisper and style == "Bold") else style
    # v7.9.1: whisper no longer downscales below the floor: max(whisper_g2_px | size, whisper_g2_px_floor_v791) = 64 px
    eff_size = max(WHISPER_G2_PX if (use_whisper and float(size) == 44.0) else float(size), G2_TEXT_FLOOR_PX)
    if use_whisper:
        eff_color = "#E8D98C" if str(color).strip().upper() == "#E8D98C" else "#FAFAFA"
        eff_glow: str | None = "none"
    else:
        eff_color = color
        eff_glow = glow_mode

    end_tl = float(total_dur) if total_dur is not None else (max(w[2] for w in words) + 0.35)
    segments = _build_free_segments(end_tl, cut_times, skip_windows, fps=fps)
    safe_bottom = py >= R209_SAFE_BOTTOM_Y
    one_frame = 1.0 / fps
    min_chunk_s = snap_time(R30_MIN_CHUNK_S, fps) - 1e-6
    out_clips: list[dict[str, Any]] = []

    for seg_a, seg_b in segments:
        seg_ws = [w for w in words if seg_a - 0.01 <= w[1] < seg_b - 0.04]
        ptr = 0
        while ptr < len(seg_ws):
            next_ptr = _smart_chunk_end(seg_ws, ptr, max_words_per_group, pause_split_s)
            next_ptr = _g2_chunk_end_at_floor(seg_ws, ptr, next_ptr, font=font, style=eff_style, size=eff_size)
            grp = seg_ws[ptr:next_ptr]
            ptr = next_ptr

            t_start = max(seg_a, snap_time(grp[0][1], fps))
            hard_ceil = snap_time(seg_b - one_frame, fps)
            next_t = snap_time(seg_ws[ptr][1] - one_frame, fps) if ptr < len(seg_ws) else hard_ceil
            t_end = min(hard_ceil, next_t, snap_time(grp[-1][2] + 0.32, fps))

            if t_end - t_start < R30_TIGHT_MAX_S:
                t_end = min(hard_ceil, next_t, snap_time(t_start + 0.30, fps))
            if t_end - t_start < min_chunk_s:
                continue

            raw_dur = snap_time(t_end - t_start, fps)
            if raw_dur < R30_TIGHT_MAX_S:
                dur_s, t_in, t_out, opacity_kf, blur_kf = _r30_quick_exit_timings(raw_dur, fps=fps)
            else:
                dur_s = raw_dur
                t_in = snap_time(min(0.18, dur_s * 0.28), fps)
                t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.12, dur_s * 0.20)), fps)
                opacity_kf = [[0.0, 0.0, "easeOut"], [min(0.14, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]]
                blur_kf = [[0.0, 8.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 6.0, "easeIn"]]

            if safe_bottom:
                pos_kf = [[0.0, [px, py - 18.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.0], "linear"]]
                scale_kf = [[0.0, 96.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.2, "linear"], [dur_s, 103.0, "linear"]]
            else:
                pos_kf = [[0.0, [px, py + 12.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 2.5], "linear"]]
                scale_kf = [[0.0, 98.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 101.4, "linear"], [dur_s, 102.0, "linear"]]

            raw_joined = " ".join(w[0] for w in grp)
            txt = clean_display_text(raw_joined).lower() if use_whisper else _cap_sentence_case(raw_joined)
            out_clips.append(
                _core_text_clip(
                    text=txt, at=t_start, dur=dur_s, font=font, style=eff_style, size=eff_size, color=eff_color,
                    pos=(px, py), align="center", glow_mode=eff_glow,
                    name=f"Phụ đề tối giản · {txt[:18]}", fps=fps,
                    shadow_overrides={"opacity": 54.0, "blur": 9.0, "distance": 2.0},
                    pos_kf=pos_kf,
                    scale_kf=scale_kf,
                    opacity_kf=opacity_kf,
                    blur_kf=blur_kf,
                )
            )
    return out_clips


# ---------------------------------------------------------------------------
# `v5.2` Inline Dual-Hue Single-Row `.fcproj` Builder
# ---------------------------------------------------------------------------

def inline_dual_hue_row(
    markup_text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 360.0),
    base_preset: str = "elastic_pop",
    font: str = "Montserrat",
    style: str = "Black",
    size: float = 74.0,
    default_color: str = "#F8FAFC",
    fps: int = DEFAULT_FPS,
    glow_mode: str | None = "auto",
) -> list[dict[str, Any]]:
    """
    Native FilmCraft `.fcproj` multi-color single-line builder (`v5.2`):
      - Parses `markup_text` (e.g. `"luôn phải [mint:khóa] [gold:kết cấu]"`) into colored spans.
      - Auto-fits `size` so total full-line ink width `<= DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT`.
      - Computes exact horizontal center `x_span` for each span via `PIL.ImageFont` advance widths (`getlength`)
        so multi-color words sit seamlessly on one horizontal row in `.fcproj`!
      - Emits synchronized adjacent `graphic_text` clips with identical `t_in`/`t_out` entrance & hold scale drift.
    """
    spans = parse_inline_color_spans(markup_text, default_color=default_color)
    if not spans:
        return []

    px, py = float(pos[0]), float(pos[1])
    preset_fn = SINGLE_PRESET_MAP.get(base_preset, elastic_pop)

    if len(spans) == 1:
        seg_txt, seg_col = spans[0]
        return [
            preset_fn(
                seg_txt,
                at,
                dur,
                pos=(px, py),
                font=font,
                style=style,
                size=size,
                color=seg_col,
                glow_mode=glow_mode,
                fps=fps,
            )
        ]

    # Build full display row string & fit shared font size across the entire multi-hue line
    full_line = " ".join(sp[0] for sp in spans if sp[0].strip())
    fitted_sz = fit_font_size(
        full_line,
        font=font,
        style=style,
        requested_size=float(size),
        max_width_px=DEFAULT_MAX_TEXT_WIDTH_PX,
        fit_ratio=HERO_ROW_FIT,
    )
    f_obj = _load_pil_font(font, style, int(round(fitted_sz * 2.0)))

    # Add tiny optical breathing pad (+2.5px per join) so 103.5% hold drift + glow never crowds adjacent spans
    join_pad = round(max(2.0, fitted_sz * 0.038), 2)
    n_spans = len(spans)
    total_adv = float(f_obj.getlength(full_line)) + join_pad * max(0, n_spans - 1)
    # Re-shrink slightly if join_pad nudged past HERO_ROW_FIT budget
    max_budget = DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT
    if total_adv > max_budget and fitted_sz > 16.0:
        fitted_sz = max(16.0, round(math.floor((fitted_sz * (max_budget / total_adv)) * 2.0) / 2.0, 2))
        f_obj = _load_pil_font(font, style, int(round(fitted_sz * 2.0)))
        join_pad = round(max(1.8, fitted_sz * 0.035), 2)
        total_adv = float(f_obj.getlength(full_line)) + join_pad * max(0, n_spans - 1)

    line_left_x = px - total_adv / 2.0
    out_clips: list[dict[str, Any]] = []
    prefix_str = ""

    for idx, (seg_txt, seg_col) in enumerate(spans):
        prefix_with_space = f"{prefix_str} " if prefix_str else ""
        prefix_adv = float(f_obj.getlength(prefix_with_space)) if prefix_with_space else 0.0
        seg_adv = float(f_obj.getlength(seg_txt))
        x_span = round(line_left_x + prefix_adv + idx * join_pad + seg_adv / 2.0, 2)

        clip = preset_fn(
            seg_txt,
            at,
            dur,
            pos=(x_span, py),
            font=font,
            style=style,
            size=fitted_sz,
            color=seg_col,
            glow_mode=glow_mode,
            name=f"Đa sắc {idx + 1} · {seg_txt[:16]}",
            fps=fps,
        )
        # Lock uniform size across all spans on the same row
        clip["size"] = float(fitted_sz)
        out_clips.append(clip)
        prefix_str = f"{prefix_str} {seg_txt}" if prefix_str else seg_txt

    return out_clips


# ---------------------------------------------------------------------------
# `v5.2` 4-Group Secondary-Text (`Text Phụ`) Engine (`S01..S18`, no `S13`)
# ---------------------------------------------------------------------------
# Group 1 (`G1_lead_sub` — Lead-in / Sub-line around Hero, 36–46pt)

def s01_accordion_rollout_sub(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 260.0),
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 40.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    slide_dx: float = 34.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S01: Horizontal left-in accordion slide + tracking telescope (`-14 -> +3`) + soft deblur."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    dy_end = -3.0 if py >= R209_SAFE_BOTTOM_Y else -4.0

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        tracking=[[0.0, -14.0, "easeOut"], [t_in, 2.0, "easeIn"], [dur_s, 4.0, "linear"]],
        name=name or f"S01 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px - float(slide_dx), py], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 5.0, py + dy_end], "linear"]],
        scale_kf=[[0.0, 96.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.3, "linear"], [dur_s, 103.0, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.15, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 11.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 7.0, "easeIn"]],
    )


def s02_boundary_pinch_sub(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 260.0),
    font: str = "Montserrat",
    style: str = "Bold",
    size: float = 40.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    tracking_start: float = -18.0,
    tracking_end: float = 8.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S02: Tracking expand (`-18 -> +8`) pinch-outward reveal + subtle hold breath."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.26, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    dy0 = -14.0 if py >= R209_SAFE_BOTTOM_Y else 10.0

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        tracking=[[0.0, float(tracking_start), "easeOut"], [t_in, float(tracking_end), "easeIn"], [dur_s, float(tracking_end) + 2.0, "linear"]],
        name=name or f"S02 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px, py + dy0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.0], "linear"]],
        scale_kf=[[0.0, 94.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.2, "linear"], [dur_s, 103.0, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 10.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 7.0, "easeIn"]],
    )


def s03_stepup_underline_sub(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 434.0),
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 42.0,
    color: str = "#F8FAFC",
    accent_color: str = "#2DD4BF",
    align: str = "center",
    glow_mode: str | None = "soft",
    include_underline: bool = False,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G1 · S03 (`v6.0` Clean Dual-Tone & Tracking-Settle Sub-Line — ZERO fake `'____'` ASCII underscores!):
      - Removes legacy `'__________________'` underscore text clip hack completely.
      - Renders a clean horizontal dual-tone or tracking-settle (`+12 -> +2 -> 0`) step-up sub-line,
        highlighting inline `[color:word]` tags or the final focal word/compound in `accent_color`.
    """
    _ = include_underline  # Preserved kwarg for backward compatibility; never emits ASCII '_' bars
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    safe_bot = py >= R209_SAFE_BOTTOM_Y
    dy0 = -16.0 if safe_bot else 18.0

    base_hex = resolve_semantic_color(color, "#F8FAFC")
    acc_hex = resolve_semantic_color(accent_color, base_hex)
    spans = parse_inline_color_spans(text, default_color=base_hex)

    # Auto-promote final compound/word to accent_color for clean dual-tone sub-line when >= 2 words
    if len(spans) == 1 and acc_hex != base_hex and align == "center":
        toks = spans[0][0].split()
        if len(toks) >= 2:
            tail_n = 2 if (len(toks) >= 3 and is_glued_pair(toks[-2], toks[-1])) else 1
            head_str = " ".join(toks[:-tail_n])
            tail_str = " ".join(toks[-tail_n:])
            if head_str and tail_str:
                markup_dual = f"{head_str} [{acc_hex}:{tail_str}]"
                return inline_dual_hue_row(
                    markup_dual,
                    at,
                    dur_s,
                    pos=(px, py),
                    base_preset="dviet_soft_up",
                    font=font,
                    style=style,
                    size=size,
                    default_color=base_hex,
                    fps=fps,
                    glow_mode=glow_mode,
                )
    elif len(spans) > 1 and align == "center":
        return inline_dual_hue_row(
            text,
            at,
            dur_s,
            pos=(px, py),
            base_preset="dviet_soft_up",
            font=font,
            style=style,
            size=size,
            default_color=base_hex,
            fps=fps,
            glow_mode=glow_mode,
        )

    sub_clip = _core_text_clip(
        text=text,
        at=at,
        dur=dur_s,
        font=font,
        style=style,
        size=size,
        color=acc_hex if acc_hex != base_hex else base_hex,
        pos=(px, py),
        align=align,
        glow_mode=glow_mode,
        tracking=[[0.0, 12.0, "easeOut"], [t_in, 2.0, "easeIn"], [dur_s, 0.0, "linear"]],
        name=name or f"S03 · {strip_inline_color_tags(text)[:18]}",
        fps=fps,
        pos_kf=[[0.0, [px, py + dy0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.5], "linear"]],
        scale_kf=[[0.0, 88.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.15, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 9.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 6.0, "easeIn"]],
    )
    return [sub_clip]


def s04_baseline_rise_lead(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 256.0),
    font: str = "Be Vietnam Pro",
    style: str = "SemiBold",
    size: float = 40.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "none",
    rise_px: float = 28.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S04: Crisp baseline-mask-style upward deblur lead (`R209`-safe)."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.20, dur_s * 0.28), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    dy0 = -18.0 if py >= R209_SAFE_BOTTOM_Y else float(rise_px)

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        name=name or f"S04 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px, py + dy0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.5], "linear"]],
        scale_kf=[[0.0, 97.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.0, "linear"], [dur_s, 102.8, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 13.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 8.0, "easeIn"]],
    )


def s05_feather_wipe_lead(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 256.0),
    font: str = "Be Vietnam Pro",
    style: str = "Medium",
    size: float = 40.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    drift_dx: float = 22.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S05: Gentle horizontal drift + long feather blur clear (`20 -> 0px`)."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.30, dur_s * 0.34), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.15, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        name=name or f"S05 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px - float(drift_dx), py], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 5.0, py - 2.5], "linear"]],
        scale_kf=[[0.0, 97.5, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 101.8, "linear"], [dur_s, 102.5, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.22, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 20.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 9.0, "easeIn"]],
    )


def s06_swivel_3d_sub(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 434.0),
    font: str = "Montserrat",
    style: str = "Bold",
    size: float = 40.0,
    color: str = "#38BDF8",
    align: str = "center",
    glow_mode: str | None = "soft",
    rot_y_start: float = -55.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S06: Fast `rot_y: -55 -> 0` 3D swivel tech sub-line."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.22, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    dy0 = -12.0 if py >= R209_SAFE_BOTTOM_Y else 12.0

    rot3d = {
        "effect": "rotate_3d",
        "params": {
            "rot_y": [[0.0, float(rot_y_start), "easeOut"], [t_in, 0.0, "easeIn"], [dur_s, 2.0, "linear"]],
        },
    }
    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, extra_effects=[rot3d],
        name=name or f"S06 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px - 14.0, py + dy0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 3.0], "linear"]],
        scale_kf=[[0.0, 92.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 10.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 7.0, "easeIn"]],
    )


def s07_ghost_recede_stack(
    lead_text: str,
    hero_text: str,
    sub_text: str | None = None,
    at: float = 0.0,
    dur: float = 2.0,
    *,
    t_hero_offset: float = 0.28,
    t_sub_offset: float = 0.52,
    is_broll: bool = False,
    hair_top_y: float | None = None,
    x: float = 540.0,
    lead_font: str = "Be Vietnam Pro",
    lead_style: str = "SemiBold",
    lead_size: float = 40.0,
    lead_color: str = "#F8FAFC",
    hero_preset: str = "elastic_pop",
    hero_font: str = "Montserrat",
    hero_style: str = "Black",
    hero_size: float = 76.0,
    hero_color: str = "#FACC15",
    sub_font: str = "Be Vietnam Pro",
    sub_style: str = "Bold",
    sub_size: float = 40.0,
    sub_color: str = "#2DD4BF",
    ghost_opacity: float = 26.0,
    ghost_blur: float = 6.0,
    cut_times: Sequence[float] | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G1 · S07 (`dviet_7706` Style 1 Ghost-to-Focus Progressive Stack for `.fcproj`):
      - Emits `[lead_clip, hero_clip, sub_clip]` (or `[lead_clip, hero_clip]` if `sub_text` is empty).
      - `lead_clip` enters at `100%` opacity (`0px` blur) and smoothly recedes to `26%` opacity + `6px`
        `gaussian_blur` right as `hero_clip` rises at `at + t_hero_offset`!
    """
    at_s = snap_time(at, fps)
    end_s = snap_time(at_s + dur, fps)
    if cut_times:
        nearest_cut = min((float(c) for c in cut_times), key=lambda ct: abs(end_s - ct))
        if -0.04 <= (end_s - nearest_cut) <= 0.48 and nearest_cut - at_s >= 0.45:
            end_s = snap_time(nearest_cut - 1.0 / fps, fps)

    dur_total = max(round(12 / fps, 6), snap_time(end_s - at_s, fps))
    has_sub = bool(sub_text and str(sub_text).strip())

    lead_y, hero_y, sub_y = compute_hero_safe_y(
        is_broll=is_broll,
        hair_top_y=hair_top_y,
        has_lead=True,
        has_script=has_sub,
        lead_size=lead_size,
        hero_size=hero_size,
    )

    h_off = snap_time(min(float(t_hero_offset), dur_total * 0.38), fps)
    h_off = max(round(3 / fps, 6), h_off)
    s_off = snap_time(min(float(t_sub_offset), dur_total * 0.62), fps)
    s_off = max(snap_time(h_off + 2 / fps, fps), s_off)

    # 1. Lead clip: 0 -> 100% crisp, then recedes to 26% opacity + 6px blur at [h_off .. h_off + 0.24s]
    t_lead_in = snap_time(min(0.18, h_off * 0.75), fps)
    t_lead_in = max(round(1 / fps, 6), t_lead_in)
    t_recede_end = snap_time(min(dur_total - 3 / fps, h_off + 0.24), fps)
    t_lead_out = snap_time(max(t_recede_end + 1 / fps, dur_total - min(0.14, dur_total * 0.18)), fps)

    lead_clip = _core_text_clip(
        text=lead_text,
        at=at_s,
        dur=dur_total,
        font=lead_font,
        style=lead_style,
        size=lead_size,
        color=lead_color,
        pos=(x, lead_y),
        align="center",
        glow_mode="none",
        name=f"S07 Dẫn mờ · {strip_inline_color_tags(lead_text)[:15]}",
        fps=fps,
        pos_kf=[
            [0.0, [x, lead_y + 16.0], "easeOut"],
            [t_lead_in, [x, lead_y], "easeIn"],
            [h_off, [x, lead_y - 1.0], "linear"],
            [t_recede_end, [x, lead_y - 6.0], "easeOut"],
            [dur_total, [x, lead_y - 9.0], "linear"],
        ],
        scale_kf=[
            [0.0, 96.0, "easeOut"],
            [t_lead_in, 100.0, "easeIn"],
            [h_off, 100.6, "linear"],
            [t_recede_end, 97.5, "easeOut"],
            [dur_total, 98.8, "linear"],
        ],
        opacity_kf=[
            [0.0, 0.0, "easeOut"],
            [t_lead_in, 100.0, "easeIn"],
            [h_off, 100.0, "linear"],
            [t_recede_end, float(ghost_opacity), "easeOut"],
            [t_lead_out, float(ghost_opacity), "linear"],
            [dur_total, 0.0, "easeIn"],
        ],
        blur_kf=[
            [0.0, 9.0, "easeOut"],
            [t_lead_in, 0.0, "easeIn"],
            [h_off, 0.0, "linear"],
            [t_recede_end, float(ghost_blur), "easeOut"],
            [t_lead_out, float(ghost_blur), "linear"],
            [dur_total, float(ghost_blur) + 4.0, "easeIn"],
        ],
    )

    # 2. Hero clip rising as lead recedes
    hero_dur = max(round(6 / fps, 6), snap_time(dur_total - h_off, fps))
    hero_spans = parse_inline_color_spans(hero_text, default_color=hero_color)
    out_clips: list[dict[str, Any]] = [lead_clip]
    if len(hero_spans) > 1:
        out_clips.extend(
            inline_dual_hue_row(
                hero_text,
                snap_time(at_s + h_off, fps),
                hero_dur,
                pos=(x, hero_y),
                base_preset=hero_preset,
                font=hero_font,
                style=hero_style,
                size=hero_size,
                default_color=hero_color,
                fps=fps,
                glow_mode="normal",
            )
        )
    else:
        hero_fn = SINGLE_PRESET_MAP.get(hero_preset, elastic_pop)
        h_col = hero_spans[0][1] if hero_spans else hero_color
        out_clips.append(
            hero_fn(
                strip_inline_color_tags(hero_text) or hero_text,
                snap_time(at_s + h_off, fps),
                hero_dur,
                pos=(x, hero_y),
                font=hero_font,
                style=hero_style,
                size=hero_size,
                color=h_col,
                glow_mode="normal",
                name=f"S07 Chính · {strip_inline_color_tags(hero_text)[:15]}",
                fps=fps,
            )
        )

    # 3. Sub clip tucked cleanly below hero
    if has_sub and sub_text is not None:
        sub_dur = max(round(6 / fps, 6), snap_time(dur_total - s_off, fps))
        sub_clip = s04_baseline_rise_lead(
            sub_text,
            snap_time(at_s + s_off, fps),
            sub_dur,
            pos=(x, sub_y),
            font=sub_font,
            style=sub_style,
            size=sub_size,
            color=sub_color,
            glow_mode="soft",
            rise_px=18.0,
            name=f"S07 Phụ · {strip_inline_color_tags(sub_text)[:15]}",
            fps=fps,
        )
        out_clips.append(sub_clip)

    return out_clips


def s08_poetic_scatter_lead(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 260.0),
    font: str = "Playfair Display",
    style: str = "Italic",
    size: float = 42.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    tracking_start: float = 28.0,
    tracking_end: float = 4.0,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S08: Soft slow deblur (`18 -> 0`) + wide tracking convergence (`28 -> 4`)."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.32, dur_s * 0.36), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.16, dur_s * 0.22)), fps)
    px, py = float(pos[0]), float(pos[1])
    dy0 = -16.0 if py >= R209_SAFE_BOTTOM_Y else 14.0

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        tracking=[[0.0, float(tracking_start), "easeOut"], [t_in, float(tracking_end), "easeIn"], [dur_s, max(0.0, float(tracking_end) - 2.0), "linear"]],
        name=name or f"S08 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px, py + dy0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px, py - 4.0], "linear"]],
        scale_kf=[[0.0, 97.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.0, "linear"], [dur_s, 102.8, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.22, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 18.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 10.0, "easeIn"]],
    )


def s09_overlap_script_sub(
    text: str,
    at: float,
    dur: float,
    *,
    hero_pos: Sequence[float] = (540.0, 352.0),
    hero_size: float = 76.0,
    pos: Sequence[float] | None = None,
    font: str = "SVN-Dancing Script",
    style: str = "Regular",
    size: float = 46.0,
    color: str = "#F8FAFC",
    align: str = "center",
    glow_mode: str | None = "soft",
    tilt_deg: float = -2.5,
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G1 · S09: `1/3` close-tucked calligraphy/italic sub-line with deep dark contrast pillow shadow (0 strokes)."""
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.26, dur_s * 0.32), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)
    if pos is not None:
        px, py = float(pos[0]), float(pos[1])
    else:
        px = float(hero_pos[0]) + 18.0
        py = round(float(hero_pos[1]) + float(hero_size) * 0.66, 1)

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode,
        rotation=[[0.0, float(tilt_deg) - 1.2, "easeOut"], [t_in, float(tilt_deg), "easeIn"], [dur_s, float(tilt_deg) + 0.6, "linear"]],
        shadow_overrides={"opacity": 92.0, "blur": 14.0, "distance": 4.0},
        name=name or f"S09 · {strip_inline_color_tags(text)[:18]}", fps=fps,
        pos_kf=[[0.0, [px - 18.0, py + 12.0], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 4.0, py - 3.0], "linear"]],
        scale_kf=[[0.0, 94.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.18, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 11.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 7.0, "easeIn"]],
    )


# ---------------------------------------------------------------------------
# Group 2 (`G2_quiet_bottom` — Quiet Word/Phrase-Synced Bottom Sub-Text, `Y >= 1360` `R209`-safe)
# ---------------------------------------------------------------------------

def _group_tokens_into_compound_slots(
    grp: Sequence[tuple[str, float, float]],
    max_slots: int = 4,
) -> list[tuple[list[str], float, float]]:
    """
    Merge glued 2-syllable Vietnamese compounds (`is_glued_pair`) and bound particles (`leads`/`trails`)
    into `1..max_slots` natural phrase slots so compounds NEVER pop half-by-half!
    """
    if not grp:
        return []
    raw_slots: list[list[tuple[str, float, float]]] = [[grp[0]]]
    toks = [w[0] for w in grp]
    for i in range(1, len(grp)):
        if is_glued_pair(toks[i - 1], toks[i]) or not can_split_after(toks, i - 1):
            raw_slots[-1].append(grp[i])
        else:
            raw_slots.append([grp[i]])

    # Merge shortest adjacent pair if slot count exceeds max_slots
    while len(raw_slots) > max_slots:
        best_idx = min(
            range(len(raw_slots) - 1),
            key=lambda idx: len(raw_slots[idx]) + len(raw_slots[idx + 1]),
        )
        raw_slots[best_idx] = raw_slots[best_idx] + raw_slots[best_idx + 1]
        del raw_slots[best_idx + 1]

    return [([x[0] for x in sl], sl[0][1], sl[-1][2]) for sl in raw_slots]


def _pick_phrase_semantic_slot(slot_texts: Sequence[str], tv: dict[str, frozenset[str]]) -> tuple[int, str | None]:
    """Select the single highest-salience semantic slot in a phrase (`(slot_idx, role_hint)`)."""
    best_i = len(slot_texts) - 1
    best_score = -999.0
    role_hint: str | None = None

    for idx, st in enumerate(slot_texts):
        words_clean = [_split_token_affixes(t)[1] for t in st.split() if _split_token_affixes(t)[1]]
        lows = [w.lower() for w in words_clean]
        if not lows:
            continue
        score = 0.2 * idx  # slight natural end-focus tie-breaker
        local_role: str | None = None

        if any(_is_caps_or_num_core(w) for w in words_clean):
            score += 5.0
            local_role = "tech"
        if any(lw in tv["warn"] for lw in lows):
            score += 4.5
            local_role = "pain"
        elif any(lw in tv["cta_verbs"] for lw in lows):
            score += 4.2
            local_role = "cta"
        elif any(lw in tv["quantity"] or lw in tv["units"] for lw in lows):
            score += 3.5
            local_role = "tech"

        if len(lows) >= 2 and f"{lows[0]} {lows[1]}" in tv["pairs"]:
            score += 3.0
        if all(lw in tv["function"] or lw in tv["pronouns"] for lw in lows):
            score -= 5.0
        else:
            score += 1.2

        if score > best_score:
            best_score = score
            best_i = idx
            role_hint = local_role

    if best_score < 0.0:
        return -1, None
    return best_i, role_hint


def s10_word_synced_fixed_slot_captions(
    words_tl: Sequence[Sequence[Any]],
    *,
    skip_windows: Sequence[Sequence[float]] | None = None,
    cut_times: Sequence[float] | None = None,
    total_dur: float | None = None,
    y: float = 1410.0,
    x: float = 540.0,
    size: float = 48.0,
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    base_color: str = "#F8FAFC",
    accent_colors: Sequence[str] | None = None,
    max_words_per_group: int = 5,
    max_slots: int = 4,
    pause_split_s: float = 0.45,
    whisper_mode: bool | None = None,
    style_profile: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """
    G2 · S10 (Signature `Subtitle.tsx` Fixed-Slot Word Pop + `v6.0` Whisper Mode for `.fcproj`):
      - `whisper_mode` (defaults to `True` when `style_profile="dviet"`, `False` otherwise):
        switches to `style="Regular", y=1590.0` monochrome `#FAFAFA`/`#E8D98C` (v7.9.1: size floored to 64 px, was 26)
        (`0` loud `48px` Bold neon chest bar!).
      - Splits speech into short 3–5 word compound-safe lines (`text_vi.json`).
      - Pre-calculates exact horizontal X-center of each word/compound slot across the centered line.
      - Returns `{"slots": slot_tracks, "clips": flat_clips, "phrase_count": n, "whisper_mode": use_whisper}`.
    """
    words = _normalize_words_tl(words_tl)
    if not words:
        return {"slots": [], "clips": [], "phrase_count": 0, "whisper_mode": False}

    is_dviet_profile = str(style_profile or "").strip().lower() in ("dviet", "dviet_7707", "dviet_v6", "@__dviet")
    use_whisper = bool(whisper_mode) if whisper_mode is not None else is_dviet_profile

    eff_y = 1590.0 if (use_whisper and float(y) == 1410.0) else float(y)
    # v7.9.1: whisper no longer downscales below the floor: max(whisper_g2_px | size, whisper_g2_px_floor_v791) = 64 px
    eff_size = max(WHISPER_G2_PX if (use_whisper and float(size) == 48.0) else float(size), G2_TEXT_FLOOR_PX)
    eff_style = "Regular" if (use_whisper and style == "Bold") else style

    end_tl = float(total_dur) if total_dur is not None else (max(w[2] for w in words) + 0.35)
    palette_ring = [
        resolve_semantic_color(c)
        for c in (
            accent_colors
            or [
                SEMANTIC_MULTI_HUE_PALETTE["lock_mint"],
                SEMANTIC_MULTI_HUE_PALETTE["prestige_gold"],
                SEMANTIC_MULTI_HUE_PALETTE["cinema_cyan"],
                SEMANTIC_MULTI_HUE_PALETTE["alert_coral"],
                SEMANTIC_MULTI_HUE_PALETTE["studio_violet"],
                SEMANTIC_MULTI_HUE_PALETTE["action_lime"],
            ]
        )
    ]
    if use_whisper:
        base_hex = "#E8D98C" if str(base_color).strip().upper() == "#E8D98C" else "#FAFAFA"
    else:
        base_hex = resolve_semantic_color(base_color, "#F8FAFC")
    tv = load_text_vi()

    segments = _build_free_segments(end_tl, cut_times, skip_windows, fps=fps)
    py = max(R209_SAFE_BOTTOM_Y, eff_y) if eff_y >= R209_SAFE_BOTTOM_Y else eff_y
    px = float(x)
    safe_bottom = py >= R209_SAFE_BOTTOM_Y
    one_frame = 1.0 / fps
    min_chunk_s = snap_time(R30_MIN_CHUNK_S, fps) - 1e-6

    slot_tracks: list[list[dict[str, Any]]] = [[] for _ in range(max(1, int(max_slots)))]
    all_clips: list[dict[str, Any]] = []
    phrase_idx = 0
    last_accent_hex = ""

    for seg_a, seg_b in segments:
        seg_ws = [w for w in words if seg_a - 0.01 <= w[1] < seg_b - 0.04]
        ptr = 0
        while ptr < len(seg_ws):
            next_ptr = _smart_chunk_end(seg_ws, ptr, max_words_per_group, pause_split_s)
            next_ptr = _g2_chunk_end_at_floor(seg_ws, ptr, next_ptr, font=font, style=eff_style, size=eff_size, slot_gap_em=0.28)
            grp = seg_ws[ptr:next_ptr]
            ptr = next_ptr

            t_phrase_start = max(seg_a, snap_time(grp[0][1], fps))
            hard_ceil = snap_time(seg_b - one_frame, fps)
            next_t = snap_time(seg_ws[ptr][1] - one_frame, fps) if ptr < len(seg_ws) else hard_ceil
            t_phrase_end = min(hard_ceil, next_t, snap_time(grp[-1][2] + 0.34, fps))

            if t_phrase_end - t_phrase_start < R30_TIGHT_MAX_S:
                t_phrase_end = min(hard_ceil, next_t, snap_time(t_phrase_start + 0.32, fps))
            if t_phrase_end - t_phrase_start < min_chunk_s:
                continue

            compound_slots = _group_tokens_into_compound_slots(grp, max_slots=max(1, int(max_slots)))
            slot_texts: list[str] = []
            prev_last_tok = ""
            for s_idx, (s_toks, _t0, _t1) in enumerate(compound_slots):
                if use_whisper:
                    stxt = clean_display_text(" ".join(s_toks)).lower()
                elif s_idx == 0:
                    stxt = _cap_sentence_case(" ".join(s_toks))
                else:
                    stxt = _format_line2_continuation(prev_last_tok, s_toks)
                slot_texts.append(stxt)
                prev_last_tok = s_toks[-1]

            full_line = " ".join(st for st in slot_texts if st.strip())
            fitted_sz = fit_font_size(
                full_line, font=font, style=eff_style, requested_size=eff_size,
                max_width_px=DEFAULT_MAX_TEXT_WIDTH_PX, fit_ratio=HERO_ROW_FIT,
            )
            f_obj = _load_pil_font(font, eff_style, int(round(fitted_sz * 2.0)))
            space_gap = max(float(f_obj.getlength(" ")), round(fitted_sz * 0.28, 2))

            slot_widths: list[float] = []
            for stxt in slot_texts:
                bb = f_obj.getbbox(stxt)
                ink_w = float(bb[2] - bb[0])
                adv_w = float(f_obj.getlength(stxt))
                slot_widths.append(max(ink_w, adv_w))

            total_row_w = sum(slot_widths) + space_gap * max(0, len(slot_widths) - 1)
            if total_row_w > DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT and fitted_sz > 18.0:
                scale_down = (DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT) / total_row_w
                fitted_sz = max(18.0, round(math.floor(fitted_sz * scale_down * 2.0) / 2.0, 2))
                f_obj = _load_pil_font(font, eff_style, int(round(fitted_sz * 2.0)))
                space_gap = max(float(f_obj.getlength(" ")), round(fitted_sz * 0.28, 2))
                slot_widths = [max(float(f_obj.getbbox(st)[2] - f_obj.getbbox(st)[0]), float(f_obj.getlength(st))) for st in slot_texts]
                total_row_w = sum(slot_widths) + space_gap * max(0, len(slot_widths) - 1)

            if use_whisper:
                # Monochrome #FAFAFA / #E8D98C whisper mode: ZERO loud multi-hue chest highlights
                accent_slot_idx = -1
                chosen_accent = base_hex
            else:
                accent_slot_idx, role_hint = _pick_phrase_semantic_slot(slot_texts, tv)
                preferred_hex: str | None = None
                if role_hint == "pain":
                    preferred_hex = str(SEMANTIC_MULTI_HUE_PALETTE["alert_coral"])
                elif role_hint == "cta":
                    preferred_hex = str(SEMANTIC_MULTI_HUE_PALETTE["action_lime"])
                elif role_hint == "tech":
                    preferred_hex = str(SEMANTIC_MULTI_HUE_PALETTE["cinema_cyan"])

                if preferred_hex and preferred_hex != last_accent_hex and (not accent_colors or preferred_hex in palette_ring):
                    chosen_accent = preferred_hex
                else:
                    cand_hex = palette_ring[phrase_idx % len(palette_ring)]
                    if cand_hex == last_accent_hex and len(palette_ring) > 1:
                        cand_hex = palette_ring[(phrase_idx + 1) % len(palette_ring)]
                    chosen_accent = cand_hex
                if accent_slot_idx >= 0:
                    last_accent_hex = chosen_accent

            cur_left = px - total_row_w / 2.0
            last_spawn_t = t_phrase_start

            for s_idx, ((_s_toks, s_t0, _s_t1), stxt, sw) in enumerate(zip(compound_slots, slot_texts, slot_widths)):
                slot_cx = round(cur_left + sw / 2.0, 2)
                cur_left += sw + space_gap

                raw_spawn = max(last_spawn_t, snap_time(s_t0, fps))
                max_latest_spawn = max(t_phrase_start, snap_time(t_phrase_end - R30_MIN_CHUNK_S, fps))
                t_slot_start = min(raw_spawn, max_latest_spawn)
                if slot_tracks[s_idx]:
                    prev_end = snap_time(slot_tracks[s_idx][-1]["at"] + slot_tracks[s_idx][-1]["dur"] + one_frame, fps)
                    t_slot_start = max(t_slot_start, prev_end)
                if t_phrase_end - t_slot_start < min_chunk_s:
                    continue
                last_spawn_t = t_slot_start

                raw_dur = snap_time(t_phrase_end - t_slot_start, fps)
                dur_s, t_in, t_out, opacity_kf, blur_kf = _r30_quick_exit_timings(raw_dur, fps=fps)
                if raw_dur >= R30_TIGHT_MAX_S:
                    dur_s = raw_dur
                    t_in = snap_time(min(0.16, dur_s * 0.28), fps)
                    t_out = snap_time(max(t_in + 2 / fps, dur_s - 2.0 / fps), fps)
                    opacity_kf = [[0.0, 0.0, "easeOut"], [min(0.12, t_in), 100.0, "easeIn"], [t_out, 100.0, "easeOut"], [dur_s, 0.0, "easeIn"]]
                    blur_kf = [[0.0, 8.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "easeOut"], [dur_s, 4.0, "easeIn"]]

                if safe_bottom:
                    pos_kf = [[0.0, [slot_cx, py - 18.0], "easeOut"], [t_in, [slot_cx, py], "easeIn"], [dur_s, [slot_cx, py - 2.5], "linear"]]
                else:
                    pos_kf = [[0.0, [slot_cx, py + 14.0], "easeOut"], [t_in, [slot_cx, py], "easeIn"], [dur_s, [slot_cx, py - 2.5], "linear"]]
                scale_kf = [[0.0, 95.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.0, "linear"], [dur_s, 102.8, "linear"]]

                is_accent = (not use_whisper) and (s_idx == accent_slot_idx)
                slot_col = chosen_accent if is_accent else base_hex
                slot_glow = "soft" if is_accent else "none"

                s_clip = _core_text_clip(
                    text=stxt,
                    at=t_slot_start,
                    dur=dur_s,
                    font=font,
                    style=eff_style,
                    size=fitted_sz,
                    color=slot_col,
                    pos=(slot_cx, py),
                    align="center",
                    glow_mode=slot_glow,
                    lock_size=True,
                    shadow_overrides={"opacity": 54.0 if use_whisper else 72.0, "blur": 9.0 if use_whisper else 11.0, "distance": 2.0 if use_whisper else 3.0},
                    name=f"S10 Ô {s_idx + 1} · {stxt[:14]}",
                    fps=fps,
                    pos_kf=pos_kf,
                    scale_kf=scale_kf,
                    opacity_kf=opacity_kf,
                    blur_kf=blur_kf,
                )
                slot_tracks[s_idx].append(s_clip)
                all_clips.append(s_clip)

            phrase_idx += 1

    non_empty_slots = [tr for tr in slot_tracks if tr]
    return {
        "slots": non_empty_slots,
        "clips": all_clips,
        "phrase_count": phrase_idx,
        "whisper_mode": use_whisper,
    }


def s11_conversational_2line(
    words_tl: Sequence[Sequence[Any]],
    *,
    skip_windows: Sequence[Sequence[float]] | None = None,
    cut_times: Sequence[float] | None = None,
    total_dur: float | None = None,
    y_single: float = 1392.0,
    y_line1: float = 1358.0,
    y_line2: float = 1432.0,
    x: float = 540.0,
    size_single: float = 54.0,
    size_pair: float = 52.0,
    max_words_per_group: int = 6,
    pause_split_s: float = 0.52,
    accent_colors: Sequence[str] | None = None,
    font_cycle: Sequence[tuple[str, str]] | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, list[dict[str, Any]]]:
    """G2 · S11: Enhanced 2-line conversational subtitles rotating across all 6 semantic studio hues."""
    six_hues = list(
        accent_colors
        or [
            str(SEMANTIC_MULTI_HUE_PALETTE["lock_mint"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["prestige_gold"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["cinema_cyan"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["alert_coral"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["studio_violet"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["action_lime"]),
        ]
    )
    return conversational_captions_2line(
        words_tl,
        skip_windows=skip_windows,
        cut_times=cut_times,
        total_dur=total_dur,
        y_single=y_single,
        y_line1=y_line1,
        y_line2=y_line2,
        x=x,
        size_single=size_single,
        size_pair=size_pair,
        max_words_per_group=max_words_per_group,
        pause_split_s=pause_split_s,
        accent_colors=six_hues,
        font_cycle=font_cycle,
        fps=fps,
    )


def s12_minimal_1line_quiet(
    words_tl: Sequence[Sequence[Any]],
    *,
    skip_windows: Sequence[Sequence[float]] | None = None,
    cut_times: Sequence[float] | None = None,
    total_dur: float | None = None,
    pos: Sequence[float] = (540.0, 1428.0),
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 44.0,
    color: str = "#F8FAFC",
    max_words_per_group: int = 5,
    pause_split_s: float = 0.45,
    glow_mode: str | None = "none",
    whisper_mode: bool | None = None,
    style_profile: str | None = None,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G2 · S12: Quiet 1-line compound-safe bottom captions (`R209` & `R30` compliant, `v6.0` Whisper Mode Ready):
      - `whisper_mode` (defaults to `True` when `style_profile="dviet"`, `False` otherwise):
        switches to `style="Regular", y=1590.0` monochrome `#FAFAFA`/`#E8D98C` (v7.9.1: size floored to 64 px, was 26)
    """
    return minimal_single_line_captions(
        words_tl,
        skip_windows=skip_windows,
        cut_times=cut_times,
        total_dur=total_dur,
        pos=pos,
        font=font,
        style=style,
        size=size,
        color=color,
        max_words_per_group=max_words_per_group,
        pause_split_s=pause_split_s,
        glow_mode=glow_mode,
        whisper_mode=whisper_mode,
        style_profile=style_profile,
        fps=fps,
    )


# ---------------------------------------------------------------------------
# Group 3 (`G3_spatial_shoulder_arc` — Spatial Side / Shoulder / Arc Sub-Text, 36–52pt)
# ---------------------------------------------------------------------------

def s14_shoulder_callout(
    text: str,
    at: float,
    dur: float,
    *,
    side: str = "left",
    y: float = 880.0,
    x: float | None = None,
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 46.0,
    color: str = "#38BDF8",
    align: str = "center",
    glow_mode: str | None = "soft",
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G3 · S14: Spatial shoulder callout (`left x=360` or `right x=720`) with lateral inward glide."""
    is_right = str(side or "left").strip().lower() == "right"
    px = float(x) if x is not None else (720.0 if is_right else 360.0)
    py = float(y)
    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_in = snap_time(min(0.24, dur_s * 0.30), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.14, dur_s * 0.20)), fps)

    dx_in = 30.0 if is_right else -30.0
    dx_hold = -5.0 if is_right else 5.0
    safe_side_w = min(440.0, 2.0 * max(160.0, min(px - 60.0, 1020.0 - px))) if align == "center" else None

    return _core_text_clip(
        text=text, at=at, dur=dur_s, font=font, style=style, size=size, color=color,
        pos=(px, py), align=align, glow_mode=glow_mode, max_width_px=safe_side_w,
        name=name or f"S14 ({'P' if is_right else 'T'}) · {strip_inline_color_tags(text)[:15]}", fps=fps,
        pos_kf=[[0.0, [px + dx_in, py], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + dx_hold, py - 2.5], "linear"]],
        scale_kf=[[0.0, 95.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.4, "linear"], [dur_s, 103.2, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.16, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [dur_s, 0.0, "easeIn"]],
        blur_kf=[[0.0, 11.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 8.0, "easeIn"]],
    )


def s15_tilted_counter_cluster(
    sub_text: str,
    hero_text: str,
    at: float,
    dur: float,
    *,
    side: str = "left",
    tilt_deg: float = 5.5,
    y: float = 680.0,
    x: float | None = None,
    sub_above: bool = False,
    sub_font: str = "Be Vietnam Pro",
    sub_style: str = "SemiBold",
    sub_size: float = 38.0,
    sub_color: str = "#F8FAFC",
    hero_font: str = "Montserrat",
    hero_style: str = "Black",
    hero_size: float = 54.0,
    hero_color: str = "#FF4D5E",
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G3 · S15 (`dviet_7706` Style 4 Tilted Counter-Cluster):
      - `sub_text` enters **6 frames BEFORE** `hero_text` (`6.0 / fps`) at a subtle editorial tilt!
      - Tight negative-leading shoulder lockup (`left x=340` or `right x=740`).
    """
    is_right = str(side or "left").strip().lower() == "right"
    px = float(x) if x is not None else (740.0 if is_right else 340.0)
    py_hero = float(y)
    py_sub = round(py_hero - 54.0 if sub_above else py_hero + 52.0, 1)
    eff_tilt = -abs(float(tilt_deg)) if (is_right and float(tilt_deg) > 0) else float(tilt_deg)
    tilt_drift = eff_tilt + (0.6 if eff_tilt >= 0 else -0.6)

    at_s = snap_time(at, fps)
    dur_total = max(round(12 / fps, 6), snap_time(dur, fps))
    six_frames = snap_time(6.0 / fps, fps)
    hero_delay = min(six_frames, snap_time(dur_total * 0.40, fps))
    hero_dur = max(round(6 / fps, 6), snap_time(dur_total - hero_delay, fps))

    safe_cluster_w = min(430.0, 2.0 * max(160.0, min(px - 65.0, 1015.0 - px)))

    t_sub_in = snap_time(min(0.20, dur_total * 0.25), fps)
    t_sub_out = snap_time(max(t_sub_in + 2 / fps, dur_total - min(0.14, dur_total * 0.18)), fps)
    sub_clip = _core_text_clip(
        text=sub_text,
        at=at_s,
        dur=dur_total,
        font=sub_font,
        style=sub_style,
        size=sub_size,
        color=sub_color,
        pos=(px, py_sub),
        align="center",
        glow_mode="none",
        max_width_px=safe_cluster_w,
        rotation=[[0.0, eff_tilt, "easeOut"], [dur_total, tilt_drift, "linear"]],
        name=f"S15 Phụ (-6f) · {strip_inline_color_tags(sub_text)[:14]}",
        fps=fps,
        pos_kf=[[0.0, [px, py_sub + 12.0], "easeOut"], [t_sub_in, [px, py_sub], "easeIn"], [dur_total, [px, py_sub - 3.5], "linear"]],
        scale_kf=[[0.0, 94.0, "easeOut"], [t_sub_in, 100.0, "easeIn"], [t_sub_out, 102.2, "linear"], [dur_total, 103.0, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_sub_in), 100.0, "easeIn"], [t_sub_out, 100.0, "linear"], [dur_total, 0.0, "easeIn"]],
        blur_kf=[[0.0, 8.0, "easeOut"], [t_sub_in, 0.0, "easeIn"], [t_sub_out, 0.0, "linear"], [dur_total, 6.0, "easeIn"]],
    )

    t_hero_in = snap_time(min(0.24, hero_dur * 0.32), fps)
    t_hero_out = snap_time(max(t_hero_in + 2 / fps, hero_dur - min(0.14, hero_dur * 0.20)), fps)
    hero_clip = _core_text_clip(
        text=hero_text,
        at=snap_time(at_s + hero_delay, fps),
        dur=hero_dur,
        font=hero_font,
        style=hero_style,
        size=hero_size,
        color=hero_color,
        pos=(px, py_hero),
        align="center",
        glow_mode="normal",
        max_width_px=safe_cluster_w,
        rotation=[[0.0, eff_tilt, "easeOut"], [hero_dur, tilt_drift, "linear"]],
        name=f"S15 Chính · {strip_inline_color_tags(hero_text)[:15]}",
        fps=fps,
        pos_kf=[[0.0, [px, py_hero + 18.0], "easeOut"], [t_hero_in, [px, py_hero], "easeIn"], [hero_dur, [px, py_hero - 4.0], "linear"]],
        scale_kf=[[0.0, 88.0, "easeOut"], [t_hero_in, 100.0, "easeIn"], [t_hero_out, 102.8, "linear"], [hero_dur, 103.6, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_hero_in), 100.0, "easeIn"], [t_hero_out, 100.0, "linear"], [hero_dur, 0.0, "easeIn"]],
        blur_kf=[[0.0, 12.0, "easeOut"], [t_hero_in, 0.0, "easeIn"], [t_hero_out, 0.0, "linear"], [hero_dur, 8.0, "easeIn"]],
    )

    return [sub_clip, hero_clip]


def s16_bridge_anchor_swap(
    anchor_prefix: str,
    swaps: Sequence[tuple[Any, ...]],
    *,
    pos: Sequence[float] = (540.0, 356.0),
    anchor_font: str = "Be Vietnam Pro",
    anchor_style: str = "Bold",
    swap_font: str = "Montserrat",
    swap_style: str = "Black",
    size: float = 48.0,
    anchor_color: str = "#F8FAFC",
    accent_colors: Sequence[str] | None = None,
    layout: str = "auto",
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G3 · S16: Keeps `anchor_prefix` anchored across the whole beat while swapping highlighted
    trailing keywords `swaps = [(keyword, at, dur[, color]), ...]` across consecutive sub-beats!
    Returns `[anchor_clip, *swap_clips]` where `swap_clips` are strictly non-overlapping in time.
    """
    if not swaps:
        return []

    parsed_swaps: list[tuple[str, float, float, str | None]] = []
    for item in swaps:
        kw = strip_inline_color_tags(str(item[0])) or str(item[0])
        s_at = float(item[1])
        s_dur = float(item[2])
        s_col = str(item[3]) if len(item) >= 4 and item[3] else None
        # Also honor inline `[color:word]` tag on item[0]
        sp_in = parse_inline_color_spans(str(item[0]), default_color="")
        if s_col is None and sp_in and HEX6_RE.match(sp_in[0][1]):
            s_col = sp_in[0][1]
        parsed_swaps.append((kw, s_at, s_dur, s_col))

    parsed_swaps.sort(key=lambda t: t[1])
    one_frame = 1.0 / fps
    at_bridge = snap_time(parsed_swaps[0][1], fps)
    end_bridge = snap_time(max(s[1] + s[2] for s in parsed_swaps), fps)
    dur_bridge = max(round(8 / fps, 6), snap_time(end_bridge - at_bridge, fps))

    px, py = float(pos[0]), float(pos[1])
    clean_anc = strip_inline_color_tags(anchor_prefix) or clean_display_text(anchor_prefix)
    longest_kw = max((s[0] for s in parsed_swaps), key=lambda k: len(k))

    comb_w = measure_text_ink_width(f"{clean_anc} {longest_kw}", swap_font, swap_style, size)
    use_stacked = (layout == "stacked") or (layout == "auto" and comb_w > DEFAULT_MAX_TEXT_WIDTH_PX * HERO_ROW_FIT * 1.18)

    hue_ring = list(
        accent_colors
        or [
            str(SEMANTIC_MULTI_HUE_PALETTE["lock_mint"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["prestige_gold"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["cinema_cyan"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["alert_coral"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["studio_violet"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["action_lime"]),
        ]
    )

    if use_stacked:
        anc_sz = fit_font_size(clean_anc, anchor_font, anchor_style, round(size * 0.84, 1))
        kw_sz = fit_font_size(longest_kw, swap_font, swap_style, size)
        anc_pos = (px, round(py - 56.0, 1))
        anc_align = "center"
        swap_x = px
        swap_y = py
        swap_align = "center"
    else:
        shared_sz = fit_font_size(f"{clean_anc} {longest_kw}", swap_font, swap_style, size)
        anc_sz = shared_sz
        kw_sz = shared_sz
        f_anc = _load_pil_font(anchor_font, anchor_style, int(round(shared_sz * 2.0)))
        f_kw = _load_pil_font(swap_font, swap_style, int(round(shared_sz * 2.0)))
        anc_adv = float(f_anc.getlength(clean_anc))
        kw_max_adv = max(float(f_kw.getlength(s[0])) for s in parsed_swaps)
        gap_px = max(float(f_anc.getlength(" ")), round(shared_sz * 0.30, 2))
        total_w = anc_adv + gap_px + kw_max_adv
        left_edge = max(65.0, px - total_w / 2.0)
        anc_pos = (round(left_edge + anc_adv / 2.0, 2), py)
        anc_align = "center"
        swap_x = round(left_edge + anc_adv + gap_px, 2)
        swap_y = py
        swap_align = "left"

    t_anc_in = snap_time(min(0.22, dur_bridge * 0.25), fps)
    t_anc_out = snap_time(max(t_anc_in + 2 / fps, dur_bridge - min(0.14, dur_bridge * 0.18)), fps)
    anchor_clip = _core_text_clip(
        text=clean_anc,
        at=at_bridge,
        dur=dur_bridge,
        font=anchor_font,
        style=anchor_style,
        size=anc_sz,
        color=anchor_color,
        pos=anc_pos,
        align=anc_align,
        glow_mode="none",
        lock_size=True,
        name=f"S16 Neo · {clean_anc[:15]}",
        fps=fps,
        pos_kf=[[0.0, [anc_pos[0] - 16.0, anc_pos[1]], "easeOut"], [t_anc_in, [anc_pos[0], anc_pos[1]], "easeIn"], [dur_bridge, [anc_pos[0], anc_pos[1] - 3.0], "linear"]],
        scale_kf=[[0.0, 96.0, "easeOut"], [t_anc_in, 100.0, "easeIn"], [t_anc_out, 101.8, "linear"], [dur_bridge, 102.4, "linear"]],
        opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.14, t_anc_in), 100.0, "easeIn"], [t_anc_out, 100.0, "linear"], [dur_bridge, 0.0, "easeIn"]],
        blur_kf=[[0.0, 9.0, "easeOut"], [t_anc_in, 0.0, "easeIn"], [t_anc_out, 0.0, "linear"], [dur_bridge, 6.0, "easeIn"]],
    )

    swap_clips: list[dict[str, Any]] = []
    for idx, (kw_txt, s_at, s_dur, s_col) in enumerate(parsed_swaps):
        c_start = snap_time(s_at, fps)
        if swap_clips:
            prev_end = snap_time(swap_clips[-1]["at"] + swap_clips[-1]["dur"] + one_frame, fps)
            c_start = max(c_start, prev_end)
        c_end = snap_time(s_at + s_dur, fps)
        if idx + 1 < len(parsed_swaps):
            c_end = min(c_end, snap_time(parsed_swaps[idx + 1][1] - one_frame, fps))
        raw_d = snap_time(c_end - c_start, fps)
        if raw_d < snap_time(R30_MIN_CHUNK_S, fps) - 1e-6:
            continue

        col_hex = resolve_semantic_color(s_col or hue_ring[idx % len(hue_ring)])
        if raw_d < R30_TIGHT_MAX_S:
            dur_k, t_in_k, t_out_k, op_kf_k, bl_kf_k = _r30_quick_exit_timings(raw_d, fps=fps)
        else:
            dur_k = raw_d
            t_in_k = snap_time(min(0.18, dur_k * 0.30), fps)
            t_out_k = snap_time(max(t_in_k + 2 / fps, dur_k - min(0.12, dur_k * 0.22)), fps)
            op_kf_k = [[0.0, 0.0, "easeOut"], [min(0.12, t_in_k), 100.0, "easeIn"], [t_out_k, 100.0, "easeOut"], [dur_k, 0.0, "easeIn"]]
            bl_kf_k = [[0.0, 10.0, "easeOut"], [t_in_k, 0.0, "easeIn"], [t_out_k, 0.0, "easeOut"], [dur_k, 6.0, "easeIn"]]

        sw_clip = _core_text_clip(
            text=kw_txt,
            at=c_start,
            dur=dur_k,
            font=swap_font,
            style=swap_style,
            size=kw_sz,
            color=col_hex,
            pos=(swap_x, swap_y),
            align=swap_align,
            glow_mode="normal",
            lock_size=True,
            name=f"S16 Đổi {idx + 1} · {kw_txt[:14]}",
            fps=fps,
            pos_kf=[[0.0, [swap_x, swap_y + 18.0], "easeOut"], [t_in_k, [swap_x, swap_y], "easeIn"], [dur_k, [swap_x, swap_y - 3.0], "linear"]],
            scale_kf=[[0.0, 88.0, "easeOut"], [t_in_k, 100.0, "easeIn"], [t_out_k, 102.5, "linear"], [dur_k, 103.4, "linear"]],
            opacity_kf=op_kf_k,
            blur_kf=bl_kf_k,
        )
        swap_clips.append(sw_clip)

    return [anchor_clip, *swap_clips]


def s17_circular_arc_sub_wrap(
    text: str,
    at: float,
    dur: float,
    *,
    head_center: Sequence[float] = (540.0, 560.0),
    radius: float = 265.0,
    theta_start_deg: float = -155.0,
    theta_end_deg: float = -25.0,
    font: str = "Montserrat",
    style: str = "Bold",
    size: float = 38.0,
    color: str = "#F8FAFC",
    accent_color: str = "#FACC15",
    word_stagger_s: float = 0.06,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G3 · S17 (`dviet_7706` Style 5 Circular Arc Head-Contour Wrap for `.fcproj`):
      - Emits word-by-word tangent-rotated `.fcproj` `graphic_text` clips along the head arc!
      - Distributes angular positions proportionally to each word's glyph advance width so spacing is optically uniform,
        honoring inline `[color:word]` tags or highlighting the final focal word in `accent_color`.
    """
    spans = parse_inline_color_spans(text, default_color=color)
    if not spans:
        return []

    word_items: list[tuple[str, str]] = []
    has_explicit_accent = len({c for _, c in spans}) > 1
    for seg_txt, seg_col in spans:
        for wd in seg_txt.split():
            if wd.strip():
                word_items.append((wd.strip(), seg_col))
    if not word_items:
        return []

    if not has_explicit_accent and len(word_items) >= 2:
        # Highlight final focal word (or glued final 2-word compound) in `accent_color`
        acc_hex = resolve_semantic_color(accent_color, "#FACC15")
        if is_glued_pair(word_items[-2][0], word_items[-1][0]):
            word_items[-2] = (word_items[-2][0], acc_hex)
        word_items[-1] = (word_items[-1][0], acc_hex)

    cx, cy = float(head_center[0]), float(head_center[1])
    rad = max(140.0, float(radius))
    th0, th1 = float(theta_start_deg), float(theta_end_deg)
    sz = max(24.0, min(52.0, float(size)))
    f_obj = _load_pil_font(font, style, int(round(sz * 2.0)))

    advs = [max(24.0, float(f_obj.getlength(w))) for w, _ in word_items]
    pad_adv = max(18.0, sz * 0.56)
    total_arc_units = sum(advs) + pad_adv * max(0, len(advs) - 1)
    arc_span_rad = max(0.35, abs(math.radians(th1 - th0)))
    min_rad_needed = (total_arc_units * 1.12) / arc_span_rad
    if rad < min_rad_needed:
        # Widen angular span first up to 146 deg, then gently expand radius so words never touch
        max_span_deg = min(146.0, math.degrees((total_arc_units * 1.12) / rad))
        mid_th = 0.5 * (th0 + th1)
        sign_th = 1.0 if th1 >= th0 else -1.0
        th0 = mid_th - 0.5 * max_span_deg * sign_th
        th1 = mid_th + 0.5 * max_span_deg * sign_th
        arc_span_rad = max(0.35, abs(math.radians(th1 - th0)))
        rad = max(rad, min(360.0, (total_arc_units * 1.08) / arc_span_rad))

    at_s = snap_time(at, fps)
    dur_total = max(round(8 / fps, 6), snap_time(dur, fps))
    out_clips: list[dict[str, Any]] = []
    cum_u = 0.0

    for idx, ((wd, w_col), w_adv) in enumerate(zip(word_items, advs)):
        if len(word_items) == 1:
            frac = 0.5
        else:
            center_u = cum_u + w_adv * 0.5
            frac = center_u / max(1.0, total_arc_units)
        cum_u += w_adv + pad_adv

        theta_deg = th0 + frac * (th1 - th0)
        theta_rad = math.radians(theta_deg)
        # Clamp strictly inside safe zone (x in 90..990, y >= 175)
        wx = round(min(990.0, max(90.0, cx + rad * math.cos(theta_rad))), 2)
        wy = round(max(175.0, cy + rad * math.sin(theta_rad)), 2)
        wx_in = round(min(995.0, max(85.0, cx + (rad + 18.0) * math.cos(theta_rad))), 2)
        wy_in = round(max(170.0, cy + (rad + 18.0) * math.sin(theta_rad)), 2)
        wx_hold = round(cx + (rad - 3.0) * math.cos(theta_rad), 2)
        wy_hold = round(max(175.0, cy + (rad - 3.0) * math.sin(theta_rad)), 2)

        tangent_deg = round(theta_deg + 90.0, 2)
        delay = snap_time(min(idx * float(word_stagger_s), dur_total * 0.45), fps)
        w_dur = max(round(6 / fps, 6), snap_time(dur_total - delay, fps))
        t_in = snap_time(min(0.24, w_dur * 0.34), fps)
        t_out = snap_time(max(t_in + 2 / fps, w_dur - min(0.14, w_dur * 0.20)), fps)

        is_col = w_col.upper() not in ("#FFFFFF", "#F8FAFC", "#F1F5F9")
        w_clip = _core_text_clip(
            text=wd,
            at=snap_time(at_s + delay, fps),
            dur=w_dur,
            font=font,
            style=style,
            size=sz,
            color=w_col,
            pos=(wx, wy),
            align="center",
            glow_mode="normal" if is_col else "soft",
            lock_size=True,
            rotation=[
                [0.0, round(tangent_deg - 6.0, 2), "easeOut"],
                [t_in, tangent_deg, "easeIn"],
                [w_dur, round(tangent_deg + 0.8, 2), "linear"],
            ],
            name=f"S17 Cung {idx + 1} · {wd[:12]}",
            fps=fps,
            pos_kf=[[0.0, [wx_in, wy_in], "easeOut"], [t_in, [wx, wy], "easeIn"], [w_dur, [wx_hold, wy_hold], "linear"]],
            scale_kf=[[0.0, 91.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.5, "linear"], [w_dur, 103.3, "linear"]],
            opacity_kf=[[0.0, 0.0, "easeOut"], [min(0.15, t_in), 100.0, "easeIn"], [t_out, 100.0, "linear"], [w_dur, 0.0, "easeIn"]],
            blur_kf=[[0.0, 10.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [w_dur, 6.0, "easeIn"]],
        )
        out_clips.append(w_clip)

    return out_clips


# ---------------------------------------------------------------------------
# Group 4 (`G4_ui_micro_labels` — Technical Tags / Corner Bracket / Active-Dim Step Pills, 26–42pt)
# ---------------------------------------------------------------------------

def s18_typewriter_tech_tag(
    text: str,
    at: float,
    dur: float,
    *,
    pos: Sequence[float] = (540.0, 212.0),
    font: str = "SF Mono",
    style: str = "Bold",
    size: float = 30.0,
    color: str = "#38BDF8",
    align: str = "center",
    bracket_wrap: bool = True,
    tracking: float = 38.0,
    glow_mode: str | None = "soft",
    name: str | None = None,
    fps: int = DEFAULT_FPS,
) -> dict[str, Any]:
    """G4 · S18a: Crisp HUD monospace/tech tag reveal (`[ 60FPS · Z-DEPTH ]`) with tracking lock & terminal flash."""
    clean_raw = strip_inline_color_tags(text) or clean_display_text(text)
    # Use Vietnamese-safe Montserrat Bold automatically if Vietnamese extended diacritics are present
    has_vn_diacritics = any(ord(ch) > 191 for ch in clean_raw)
    eff_font = "Montserrat" if (has_vn_diacritics and font.lower() in ("sf mono", "jetbrains mono")) else font
    eff_style = "Bold" if eff_font == "Montserrat" else style

    disp_txt = clean_raw
    if bracket_wrap and not (clean_raw.startswith("[") and clean_raw.endswith("]")):
        disp_txt = f"[ {clean_raw} ]"

    dur_s = max(round(6 / fps, 6), snap_time(dur, fps))
    t_flash = snap_time(min(2.0 / fps, dur_s * 0.16), fps)
    t_in = snap_time(min(0.18, max(t_flash + 1.0 / fps, dur_s * 0.28)), fps)
    t_out = snap_time(max(t_in + 2 / fps, dur_s - min(0.12, dur_s * 0.20)), fps)
    px, py = float(pos[0]), float(pos[1])
    sz = max(26.0, min(42.0, float(size)))

    return _core_text_clip(
        text=disp_txt,
        at=at,
        dur=dur_s,
        font=eff_font,
        style=eff_style,
        size=sz,
        color=color,
        pos=(px, py),
        align=align,
        glow_mode=glow_mode,
        tracking=[[0.0, 6.0, "easeOut"], [t_in, float(tracking), "easeIn"], [dur_s, float(tracking) + 4.0, "linear"]],
        name=name or f"S18 Tag · {clean_raw[:16]}",
        fps=fps,
        pos_kf=[[0.0, [px - 10.0, py], "easeOut"], [t_in, [px, py], "easeIn"], [dur_s, [px + 2.0, py - 2.0], "linear"]],
        scale_kf=[[0.0, 97.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 101.8, "linear"], [dur_s, 102.4, "linear"]],
        opacity_kf=[
            [0.0, 0.0, "easeOut"],
            [t_flash, 72.0, "linear"],
            [t_in, 100.0, "easeIn"],
            [t_out, 100.0, "linear"],
            [dur_s, 0.0, "easeIn"],
        ],
        blur_kf=[[0.0, 5.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_s, 4.0, "easeIn"]],
    )


def s18_active_dim_step_pills(
    steps: Sequence[tuple[Any, ...]],
    end_t: float,
    *,
    start_pos: Sequence[float] = (180.0, 640.0),
    row_gap: float = 64.0,
    font: str = "Be Vietnam Pro",
    style: str = "Bold",
    size: float = 36.0,
    align: str = "left",
    dim_opacity: float = 46.0,
    accent_colors: Sequence[str] | None = None,
    auto_number: bool = False,
    fps: int = DEFAULT_FPS,
) -> list[dict[str, Any]]:
    """
    G4 · S18b (`StepList.tsx` Active-to-Dim Progressive Step Pills for `.fcproj`):
      - Each step `(label, show_t[, color])` enters at `show_t` at `100%` opacity.
      - When the next step `i + 1` appears at `next_show_t`, earlier step clips smoothly dim their
        `opacity` keyframe down to `46%` (`dim_opacity`) while staying visible until `end_t`!
    """
    if not steps:
        return []

    parsed: list[tuple[str, float, str | None]] = []
    for idx, st in enumerate(steps):
        raw_lbl = strip_inline_color_tags(str(st[0])) or str(st[0])
        if auto_number and not re.match(r"^\d{1,2}\s*[·.:/-]", raw_lbl):
            raw_lbl = f"0{idx + 1} · {raw_lbl}" if idx < 9 else f"{idx + 1} · {raw_lbl}"
        sh_t = float(st[1])
        col_ov = str(st[2]) if len(st) >= 3 and st[2] else None
        sp_in = parse_inline_color_spans(str(st[0]), default_color="")
        if col_ov is None and sp_in and HEX6_RE.match(sp_in[0][1]):
            col_ov = sp_in[0][1]
        parsed.append((raw_lbl, sh_t, col_ov))

    parsed.sort(key=lambda item: item[1])
    end_s = snap_time(end_t, fps)
    px, py0 = float(start_pos[0]), float(start_pos[1])
    sz = max(26.0, min(42.0, float(size)))

    hue_ring = list(
        accent_colors
        or [
            str(SEMANTIC_MULTI_HUE_PALETTE["lock_mint"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["cinema_cyan"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["prestige_gold"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["action_lime"]),
            str(SEMANTIC_MULTI_HUE_PALETTE["studio_violet"]),
        ]
    )

    out_clips: list[dict[str, Any]] = []
    for idx, (lbl, show_t, col_ov) in enumerate(parsed):
        at_i = snap_time(show_t, fps)
        dur_i = snap_time(end_s - at_i, fps)
        if dur_i < round(5 / fps, 6):
            continue

        py_i = round(min(1620.0, py0 + idx * float(row_gap)), 1)
        t_in = snap_time(min(0.18, dur_i * 0.25), fps)
        t_out = snap_time(max(t_in + 2 / fps, dur_i - min(0.14, dur_i * 0.18)), fps)

        # Smoothly dim from 100% -> 46% right when the next step spawns!
        op_kf: list[list[Any]] = [
            [0.0, 0.0, "easeOut"],
            [min(0.14, t_in), 100.0, "easeIn"],
        ]
        if idx + 1 < len(parsed):
            next_show = snap_time(parsed[idx + 1][1], fps)
            t_dim_start = snap_time(next_show - at_i, fps)
            t_dim_done = snap_time(t_dim_start + 0.20, fps)
            if t_in + 1.0 / fps <= t_dim_start and t_dim_done <= t_out - 1.0 / fps:
                op_kf.extend([
                    [t_dim_start, 100.0, "linear"],
                    [t_dim_done, float(dim_opacity), "easeOut"],
                    [t_out, float(dim_opacity), "linear"],
                ])
            elif t_in + 1.0 / fps < t_out - 1.0 / fps:
                mid_t = snap_time((t_in + t_out) * 0.5, fps)
                op_kf.extend([
                    [mid_t, float(dim_opacity), "easeOut"],
                    [t_out, float(dim_opacity), "linear"],
                ])
            else:
                op_kf.append([t_out, float(dim_opacity), "linear"])
        else:
            op_kf.append([t_out, 100.0, "linear"])
        op_kf.append([dur_i, 0.0, "easeIn"])

        col_hex = resolve_semantic_color(col_ov or hue_ring[idx % len(hue_ring)])
        step_clip = _core_text_clip(
            text=lbl,
            at=at_i,
            dur=dur_i,
            font=font,
            style=style,
            size=sz,
            color=col_hex,
            pos=(px, py_i),
            align=align,
            glow_mode="soft",
            name=f"S18 Bước {idx + 1} · {lbl[:15]}",
            fps=fps,
            pos_kf=[[0.0, [px - 22.0, py_i], "easeOut"], [t_in, [px, py_i], "easeIn"], [dur_i, [px + 3.0, py_i - 2.0], "linear"]],
            scale_kf=[[0.0, 94.0, "easeOut"], [t_in, 100.0, "easeIn"], [t_out, 102.0, "linear"], [dur_i, 102.6, "linear"]],
            opacity_kf=op_kf,
            blur_kf=[[0.0, 8.0, "easeOut"], [t_in, 0.0, "easeIn"], [t_out, 0.0, "linear"], [dur_i, 5.0, "easeIn"]],
        )
        out_clips.append(step_clip)

    return out_clips


# ---------------------------------------------------------------------------
# Contextual 4-Group Secondary Rotation Planner (`G1`, `G2`, `G3`, `G4`)
# ---------------------------------------------------------------------------

SECONDARY_4GROUP_STYLES: dict[str, list[str]] = {
    "G1_lead_sub": [
        "s01_accordion_rollout_sub",
        "s02_boundary_pinch_sub",
        "s03_stepup_underline_sub",
        "s04_baseline_rise_lead",
        "s05_feather_wipe_lead",
        "s06_swivel_3d_sub",
        "s07_ghost_recede_stack",
        "s08_poetic_scatter_lead",
        "s09_overlap_script_sub",
    ],
    "G2_quiet_bottom": [
        "s10_word_synced_fixed_slot_captions",
        "s11_conversational_2line",
        "s12_minimal_1line_quiet",
    ],
    "G3_spatial_shoulder_arc": [
        "s14_shoulder_callout",
        "s15_tilted_counter_cluster",
        "s16_bridge_anchor_swap",
        "s17_circular_arc_sub_wrap",
    ],
    "G4_ui_micro_labels": [
        "s18_typewriter_tech_tag",
        "s18_active_dim_step_pills",
    ],
}

_ARCHETYPE_SECONDARY_PREFS: dict[str, dict[str, Any]] = {
    "dviet_vietanh_zdepth_master": {
        "caption_spine": "s10_word_synced_fixed_slot_captions",
        "G1": ["s07_ghost_recede_stack", "s01_accordion_rollout_sub", "s03_stepup_underline_sub", "s09_overlap_script_sub", "s04_baseline_rise_lead"],
        "G3": ["s15_tilted_counter_cluster", "s17_circular_arc_sub_wrap", "s14_shoulder_callout", "s16_bridge_anchor_swap"],
        "G4": ["s18_active_dim_step_pills", "s18_typewriter_tech_tag"],
    },
    "kinetic_tech_architect": {
        "caption_spine": "s10_word_synced_fixed_slot_captions",
        "G1": ["s06_swivel_3d_sub", "s02_boundary_pinch_sub", "s03_stepup_underline_sub", "s01_accordion_rollout_sub"],
        "G3": ["s16_bridge_anchor_swap", "s14_shoulder_callout", "s15_tilted_counter_cluster"],
        "G4": ["s18_typewriter_tech_tag", "s18_active_dim_step_pills"],
    },
    "minimal_intellectual": {
        "caption_spine": "s12_minimal_1line_quiet",
        "G1": ["s04_baseline_rise_lead", "s05_feather_wipe_lead", "s08_poetic_scatter_lead", "s02_boundary_pinch_sub"],
        "G3": ["s14_shoulder_callout", "s16_bridge_anchor_swap", "s15_tilted_counter_cluster"],
        "G4": ["s18_active_dim_step_pills", "s18_typewriter_tech_tag"],
    },
    "story_confessional": {
        "caption_spine": "s11_conversational_2line",
        "G1": ["s07_ghost_recede_stack", "s08_poetic_scatter_lead", "s09_overlap_script_sub", "s05_feather_wipe_lead"],
        "G3": ["s17_circular_arc_sub_wrap", "s15_tilted_counter_cluster", "s14_shoulder_callout"],
        "G4": ["s18_active_dim_step_pills", "s18_typewriter_tech_tag"],
    },
    "luxury_editorial": {
        "caption_spine": "s12_minimal_1line_quiet",
        "G1": ["s08_poetic_scatter_lead", "s09_overlap_script_sub", "s05_feather_wipe_lead", "s02_boundary_pinch_sub"],
        "G3": ["s17_circular_arc_sub_wrap", "s14_shoulder_callout", "s16_bridge_anchor_swap"],
        "G4": ["s18_typewriter_tech_tag", "s18_active_dim_step_pills"],
    },
    "high_velocity_punch": {
        "caption_spine": "s10_word_synced_fixed_slot_captions",
        "G1": ["s01_accordion_rollout_sub", "s06_swivel_3d_sub", "s03_stepup_underline_sub", "s04_baseline_rise_lead"],
        "G3": ["s15_tilted_counter_cluster", "s16_bridge_anchor_swap", "s14_shoulder_callout"],
        "G4": ["s18_typewriter_tech_tag", "s18_active_dim_step_pills"],
    },
}


def plan_4group_secondary_rotation(
    beats: Sequence[dict[str, Any]],
    *,
    archetype: str = "dviet_vietanh_zdepth_master",
    video_seed: int = 0,
) -> dict[str, Any]:
    """
    Contextual 4-Group Secondary Typography Planner (`v5.2`):
      - Combines `plan_semantic_hue_sequence` (0 consecutive duplicate hero hues, `<= 35%` per hue)
        with non-repeating secondary choreography across **all 4 groups** (`G1_lead_sub`, `G2_quiet_bottom`,
        `G3_spatial_shoulder_arc`, `G4_ui_micro_labels`; `S13` karaoke excluded).
      - When `len(beats) >= 4`, guarantees all 4 groups (`G1`, `G2`, `G3`, `G4`) are represented!
    """
    arch_key = str(archetype or "dviet_vietanh_zdepth_master").strip().lower()
    prefs = _ARCHETYPE_SECONDARY_PREFS.get(arch_key, _ARCHETYPE_SECONDARY_PREFS["dviet_vietanh_zdepth_master"])
    hue_beats = plan_semantic_hue_sequence(beats, archetype=arch_key, seed=video_seed)
    n = len(hue_beats)

    g2_list = SECONDARY_4GROUP_STYLES["G2_quiet_bottom"]
    default_spine = str(prefs["caption_spine"])
    if video_seed % 3 == 0:
        caption_spine = default_spine
    else:
        caption_spine = g2_list[(g2_list.index(default_spine) + video_seed) % len(g2_list)]

    if n == 0:
        return {
            "archetype": arch_key,
            "video_seed": int(video_seed),
            "caption_spine_preset": caption_spine,
            "groups_used": [],
            "hue_distribution": {},
            "group_distribution": {},
            "beats": [],
        }

    # Step 1: Map each beat semantically to its natural group
    target_groups: list[str] = []
    for idx, hb in enumerate(hue_beats):
        role = str(hb.get("role") or "").lower()
        ctype = str(hb.get("content_type") or "").lower()
        if hb.get("has_steps") or role in ("step", "tech", "specs", "ai", "metric", "data") or ctype in ("steps", "tech", "code", "kpi"):
            target_groups.append("G4_ui_micro_labels")
        elif hb.get("has_arc") or role in ("pain", "myth", "warning", "defect", "comparison", "shoulder") or ctype in ("arc", "shoulder", "versus"):
            target_groups.append("G3_spatial_shoulder_arc")
        elif role in ("quiet", "bridge", "breathing", "story_flow") or ctype in ("caption_only", "quiet"):
            target_groups.append("G2_quiet_bottom")
        elif idx == 0 or role in ("hook", "brand", "identity", "solution", "light", "creative", "cta"):
            target_groups.append("G1_lead_sub")
        else:
            cycle_4 = ("G1_lead_sub", "G3_spatial_shoulder_arc", "G2_quiet_bottom", "G4_ui_micro_labels")
            target_groups.append(cycle_4[(idx + video_seed) % 4])

    # Step 2: When len(beats) >= 4, ensure all 4 groups appear at least once without clobbering beat 0 hook
    all_4 = ("G1_lead_sub", "G2_quiet_bottom", "G3_spatial_shoulder_arc", "G4_ui_micro_labels")
    if n >= 4:
        present = set(target_groups)
        missing = [g for g in all_4 if g not in present]
        for mg in missing:
            # Replace an over-represented group (preferring interior beats idx >= 1)
            grp_counts = {g: target_groups.count(g) for g in all_4}
            cand_indices = [
                i for i in range(n - 1, -1, -1)
                if grp_counts.get(target_groups[i], 0) > 1
            ]
            rep_idx = cand_indices[0] if cand_indices else (n - 1)
            target_groups[rep_idx] = mg

    # Step 3: Pick specific non-repeating preset inside each group
    group_cursors = {"G1_lead_sub": video_seed, "G2_quiet_bottom": video_seed, "G3_spatial_shoulder_arc": video_seed, "G4_ui_micro_labels": video_seed}
    last_preset = ""
    planned_beats: list[dict[str, Any]] = []

    for idx, (hb, grp) in enumerate(zip(hue_beats, target_groups)):
        role = str(hb.get("role") or "").lower()
        if grp == "G1_lead_sub":
            pool = list(prefs["G1"])
        elif grp == "G3_spatial_shoulder_arc":
            pool = list(prefs["G3"])
            if hb.get("has_arc") and "s17_circular_arc_sub_wrap" in SECONDARY_4GROUP_STYLES[grp]:
                pool = ["s17_circular_arc_sub_wrap", *[p for p in pool if p != "s17_circular_arc_sub_wrap"]]
        elif grp == "G4_ui_micro_labels":
            pool = list(prefs["G4"])
            if hb.get("has_steps") or role == "step":
                pool = ["s18_active_dim_step_pills", "s18_typewriter_tech_tag"]
            elif role in ("tech", "specs", "ai"):
                pool = ["s18_typewriter_tech_tag", "s18_active_dim_step_pills"]
        else:
            pool = [caption_spine, *[p for p in g2_list if p != caption_spine]]

        cur = group_cursors[grp]
        pick = pool[cur % len(pool)]
        if pick == last_preset and len(pool) > 1:
            cur += 1
            pick = pool[cur % len(pool)]
        if pick == last_preset:
            # Cross-group anti-repeat guard when a 1-item or 2-item pool collided
            alt_pool = [p for p in prefs["G1"] if p != last_preset]
            pick = alt_pool[idx % len(alt_pool)]
            grp = "G1_lead_sub"
        group_cursors[grp] = cur + 1
        last_preset = pick

        planned_beats.append({
            **hb,
            "secondary_group": grp,
            "secondary_preset": pick,
        })

    hue_dist: dict[str, int] = {}
    grp_dist: dict[str, int] = {}
    for pb in planned_beats:
        hk = pb["hero_hue_key"]
        gk = pb["secondary_group"]
        hue_dist[hk] = hue_dist.get(hk, 0) + 1
        grp_dist[gk] = grp_dist.get(gk, 0) + 1

    return {
        "archetype": arch_key,
        "video_seed": int(video_seed),
        "caption_spine_preset": caption_spine,
        "groups_used": sorted(grp_dist.keys()),
        "hue_distribution": hue_dist,
        "group_distribution": grp_dist,
        "beats": planned_beats,
    }


SECONDARY_PRESET_MAP: dict[str, Any] = {
    "inline_dual_hue_row": inline_dual_hue_row,
    "dviet_wall_microword_pop": dviet_wall_microword_pop,
    "wall_microword_pop": dviet_wall_microword_pop,
    "dviet_two_point_wall_hop": dviet_two_point_wall_hop,
    "two_point_wall_hop": dviet_two_point_wall_hop,
    "dviet_kiss_hero_pair": dviet_kiss_hero_pair,
    "kiss_hero_pair": dviet_kiss_hero_pair,
    "s01_accordion_rollout_sub": s01_accordion_rollout_sub,
    "s01": s01_accordion_rollout_sub,
    "s02_boundary_pinch_sub": s02_boundary_pinch_sub,
    "s02": s02_boundary_pinch_sub,
    "s03_stepup_underline_sub": s03_stepup_underline_sub,
    "s03": s03_stepup_underline_sub,
    "s04_baseline_rise_lead": s04_baseline_rise_lead,
    "s04": s04_baseline_rise_lead,
    "s05_feather_wipe_lead": s05_feather_wipe_lead,
    "s05": s05_feather_wipe_lead,
    "s06_swivel_3d_sub": s06_swivel_3d_sub,
    "s06": s06_swivel_3d_sub,
    "s07_ghost_recede_stack": s07_ghost_recede_stack,
    "s07": s07_ghost_recede_stack,
    "s08_poetic_scatter_lead": s08_poetic_scatter_lead,
    "s08": s08_poetic_scatter_lead,
    "s09_overlap_script_sub": s09_overlap_script_sub,
    "s09": s09_overlap_script_sub,
    "s10_word_synced_fixed_slot_captions": s10_word_synced_fixed_slot_captions,
    "s10": s10_word_synced_fixed_slot_captions,
    "s11_conversational_2line": s11_conversational_2line,
    "s11": s11_conversational_2line,
    "s12_minimal_1line_quiet": s12_minimal_1line_quiet,
    "s12": s12_minimal_1line_quiet,
    "s14_shoulder_callout": s14_shoulder_callout,
    "s14": s14_shoulder_callout,
    "s15_tilted_counter_cluster": s15_tilted_counter_cluster,
    "s15": s15_tilted_counter_cluster,
    "s16_bridge_anchor_swap": s16_bridge_anchor_swap,
    "s16": s16_bridge_anchor_swap,
    "s17_circular_arc_sub_wrap": s17_circular_arc_sub_wrap,
    "s17": s17_circular_arc_sub_wrap,
    "s18_typewriter_tech_tag": s18_typewriter_tech_tag,
    "s18_tag": s18_typewriter_tech_tag,
    "s18_active_dim_step_pills": s18_active_dim_step_pills,
    "s18_steps": s18_active_dim_step_pills,
}


def compose_text(preset: str, *args: Any, **kwargs: Any) -> Any:
    """
    Unified dispatcher across all `v7.0` 4-Act Jewel Palettes, Player 3 Air-Cushion, Dual-Rail Safe-Y,
    Wall Micro-Word, Negative-Leading Kiss, Hero, Multi-Hue Inline, and 4-Group Secondary (`S01..S18`) presets.
    """
    registry = {
        **SINGLE_PRESET_MAP,
        "player3_air_cushion_slide": player3_air_cushion_slide,
        "player3_air_cushion": player3_air_cushion_slide,
        "dual_hero_pair": dual_hero_pair,
        "dviet_kiss_hero_pair": dviet_kiss_hero_pair,
        "kiss_hero_pair": dviet_kiss_hero_pair,
        "dviet_wall_microword_pop": dviet_wall_microword_pop,
        "dviet_two_point_wall_hop": dviet_two_point_wall_hop,
        "export_dviet_bevel_lockup_png": export_dviet_bevel_lockup_png,
        "conversational_captions_2line": conversational_captions_2line,
        "minimal_single_line_captions": minimal_single_line_captions,
        **SECONDARY_PRESET_MAP,
    }
    key = str(preset or "").strip()
    if key == "render_dviet_3d_extruded_bevel_word":
        return render_dviet_3d_extruded_bevel_word(*args, **kwargs)
    if key not in registry:
        raise ValueError(f"Unknown typography preset={key!r}. Valid: {sorted(registry)}")
    return registry[key](*args, **kwargs)


# ---------------------------------------------------------------------------
# Smooth `@__dviet` Camera Curve & Bimodal J-Cut Helpers (`v6.0`)
# ---------------------------------------------------------------------------

def _clamp_zero_black_bars(px: float, py: float, scale_pct: float) -> list[float]:
    """
    Guarantee `0` black bars on a `1080x1920` canvas (`anchor=[540, 960]`):
      - `1080 - 5.4 * S <= px <= 5.4 * S`
      - `1920 - 9.6 * S <= py <= 9.6 * S`
    """
    s = max(100.5, float(scale_pct))
    min_x = 1080.0 - 5.4 * s + 1.5
    max_x = 5.4 * s - 1.5
    min_y = 1920.0 - 9.6 * s + 1.5
    max_y = 9.6 * s - 1.5
    cx = min(max_x, max(min_x, float(px))) if min_x <= max_x else 540.0
    cy = min(max_y, max(min_y, float(py))) if min_y <= max_y else 960.0
    return [round(cx, 1), round(cy, 1)]


def _prepend_cut_kick(motion: dict[str, Any], dur_s: float, fps: int) -> dict[str, Any]:
    """
    `v5.1` Tactile 5-frame (`5 / fps`) `+1.8%` post-cut scale settle impulse (inspired by `Footage.tsx`):
    Applied when `cut_kick=True` and `dur_s >= 0.6s`.
    """
    if dur_s < 0.60:
        return motion
    sc = motion.get("scale")
    if not isinstance(sc, list) or not sc:
        return motion
    t_kick = snap_time(5.0 / fps, fps)
    s0 = float(sc[0][1])
    s_kick = round(s0 + 1.8, 2)
    tail = [k for k in sc[1:] if float(k[0]) >= t_kick + (1.5 / fps)]
    if not tail:
        tail = [sc[-1]]
    new_sc = [[0.0, s_kick, "easeOut"], [t_kick, round(s0, 2), "easeOut"], *tail]
    motion["scale"] = _strict_kf(new_sc, dur_s, fps)
    return motion


def aroll_camera(
    dur: float,
    mode: str = "in_hold",
    reframe_y: float = 1132.0,
    x: float = 540.0,
    fps: int = DEFAULT_FPS,
    cut_kick: bool = False,
    *,
    framing: str = "center",
    eye_line_y: float | None = None,
) -> dict[str, Any]:
    """
    `v6.0` Smooth `@__dviet` Optical-Flow & Asymmetric 3-Cam Rule-of-Thirds A-Roll Camera (`0` black bars!):
      Framings:
        - `"center"` (default): Classic centered framing (`x=540`, `scale ~ 118.5–128.5%`).
        - `"left_third"`: Speaker on left Rule-of-Thirds (`scale=136%..142.5%, x=378`), opening right wall (`x=735`).
        - `"right_third"`: Speaker on right Rule-of-Thirds (`scale=136%..142.5%, x=702`), opening left wall (`x=345`).
        - `"closeup_high"`: Intimate emotional/emphasis close-up (`scale=146%..153.5%, x=540`, elevated eye-line).
      `eye_line_y`: Optional target screen Y for speaker eye-line (auto-computes vertical position inside `0`-black-bar bounds).
    """
    d = max(round(4 / fps, 6), snap_time(dur, fps))
    fr = str(framing or "center").strip().lower()
    if fr not in ("center", "left_third", "right_third", "closeup_high"):
        raise ValueError(f"Unknown aroll_camera framing={framing!r}. Valid: center, left_third, right_third, closeup_high")

    # Resolve base scale floor & horizontal Rule-of-Thirds anchor for asymmetric 3-cam framing
    if fr == "left_third":
        s_boost = 17.5  # 118.5 + 17.5 = 136.0% exact!
        cx = 378.0 if float(x) == 540.0 else float(x)
        default_ry = 1146.0 if float(reframe_y) == 1132.0 else float(reframe_y)
    elif fr == "right_third":
        s_boost = 17.5  # 136.0% exact!
        cx = 702.0 if float(x) == 540.0 else float(x)
        default_ry = 1146.0 if float(reframe_y) == 1132.0 else float(reframe_y)
    elif fr == "closeup_high":
        s_boost = 27.5  # 146.0%..153.5% tight macro!
        cx = float(x)
        default_ry = 1186.0 if float(reframe_y) == 1132.0 else float(reframe_y)
    else:
        s_boost = 0.0
        cx = float(x)
        default_ry = float(reframe_y)

    if eye_line_y is not None:
        # Map raw talking-head eye-line (~640px at 100% scale -> offset -320px from 960 anchor) to target eye_line_y
        ref_scale = (118.5 + s_boost) / 100.0
        ry = float(eye_line_y) + 320.0 * ref_scale
    else:
        ry = default_ry

    dy_base = ry - 1132.0
    strict_coverage = (fr != "center") or (eye_line_y is not None)

    def _p(px: float, py_1132: float, s_at_kf: float) -> list[float]:
        raw_px = round(px, 1)
        raw_py = round(py_1132 + dy_base, 1)
        if strict_coverage:
            return _clamp_zero_black_bars(raw_px, raw_py, s_at_kf)
        return _clamp_zero_black_bars(raw_px, raw_py, s_at_kf) if (raw_px < 1080.0 - 5.4 * s_at_kf or raw_px > 5.4 * s_at_kf) else [raw_px, raw_py]

    if d < 1.05 or mode == "breath_still_drift":
        s0 = round((119.0 if mode == "breath_still_drift" else 122.0) + s_boost, 2)
        s1 = round((122.5 if mode == "breath_still_drift" else 118.5) + s_boost, 2)
        if fr in ("left_third", "right_third"):
            s0, s1 = max(136.0, s0), max(136.0, s1)
        p0 = _p(cx, 1130.0 if mode == "breath_still_drift" else 1138.0, s0)
        p1 = _p(cx + (4.0 if mode == "breath_still_drift" else 0.0), 1138.0 if mode == "breath_still_drift" else 1126.0, s1)
        mot = {
            "anchor": [540, 960],
            "scale": _strict_kf([[0.0, s0, "easeOut"], [d, s1, "linear"]], d, fps),
            "position": _strict_kf([[0.0, p0, "easeOut"], [d, p1, "linear"]], d, fps),
        }
        return _prepend_cut_kick(mot, d, fps) if cut_kick else mot

    if mode == "velvet_settle_then_in":
        t1 = snap_time(min(0.68, d * 0.25), fps)
        t2 = snap_time(max(t1 + 0.20, d * 0.62), fps)
        t3 = snap_time(min(d - 0.12, t2 + 0.60), fps)
        s_vals = [124.0 + s_boost, 118.5 + s_boost, 120.0 + s_boost, 127.5 + s_boost, 128.5 + s_boost]
        mot = {
            "anchor": [540, 960],
            "scale": _strict_kf(
                [[0.0, s_vals[0], "easeOut"], [t1, s_vals[1], "easeIn"], [t2, s_vals[2], "easeOut"], [t3, s_vals[3], "easeIn"], [d, s_vals[4], "linear"]],
                d, fps,
            ),
            "position": _strict_kf(
                [
                    [0.0, _p(cx, 1144.0, s_vals[0]), "easeOut"],
                    [t1, _p(cx, 1126.0, s_vals[1]), "easeIn"],
                    [t2, _p(cx, 1130.0, s_vals[2]), "easeOut"],
                    [t3, _p(cx - 18.0, 1152.0, s_vals[3]), "easeIn"],
                    [d, _p(cx - 20.0, 1154.0, s_vals[4]), "linear"],
                ],
                d, fps,
            ),
        }
        return _prepend_cut_kick(mot, d, fps) if cut_kick else mot

    if mode == "pain_emphasis_in":
        t1 = snap_time(min(0.60, d * 0.32), fps)
        t2 = snap_time(max(t1 + 0.20, d - 0.66), fps)
        s_vals = [119.0 + s_boost, 127.0 + s_boost, 128.2 + s_boost, 120.0 + s_boost]
        mot = {
            "anchor": [540, 960],
            "scale": _strict_kf(
                [[0.0, s_vals[0], "easeOut"], [t1, s_vals[1], "easeIn"], [t2, s_vals[2], "easeOut"], [d, s_vals[3], "easeIn"]],
                d, fps,
            ),
            "position": _strict_kf(
                [
                    [0.0, _p(cx, 1128.0, s_vals[0]), "easeOut"],
                    [t1, _p(cx + 16.0, 1150.0, s_vals[1]), "easeIn"],
                    [t2, _p(cx + 16.0, 1152.0, s_vals[2]), "easeOut"],
                    [d, _p(cx, 1130.0, s_vals[3]), "easeIn"],
                ],
                d, fps,
            ),
        }
        return _prepend_cut_kick(mot, d, fps) if cut_kick else mot

    if mode == "zoom_out_breath":
        t1 = snap_time(min(0.72, d * 0.38), fps)
        s_vals = [126.5 + s_boost, 118.5 + s_boost, 120.5 + s_boost]
        mot = {
            "anchor": [540, 960],
            "scale": _strict_kf([[0.0, s_vals[0], "easeOut"], [t1, s_vals[1], "easeIn"], [d, s_vals[2], "linear"]], d, fps),
            "position": _strict_kf(
                [[0.0, _p(cx - 16.0, 1148.0, s_vals[0]), "easeOut"], [t1, _p(cx, 1126.0, s_vals[1]), "easeIn"], [d, _p(cx, 1132.0, s_vals[2]), "linear"]],
                d, fps,
            ),
        }
        return _prepend_cut_kick(mot, d, fps) if cut_kick else mot

    # Default: "in_hold" (Signature @__dviet asymmetric velvet zoom-in + slow drift; 136% -> 144.7% on left/right_third)
    t1 = snap_time(min(0.60, d * 0.35), fps)
    s_vals = [118.5 + s_boost, 125.5 + s_boost, 127.2 + s_boost]
    dx_drift = -12.0 if fr == "right_third" else 14.0
    dx_end = -14.0 if fr == "right_third" else 16.0
    mot = {
        "anchor": [540, 960],
        "scale": _strict_kf([[0.0, s_vals[0], "easeOut"], [t1, s_vals[1], "easeIn"], [d, s_vals[2], "linear"]], d, fps),
        "position": _strict_kf(
            [
                [0.0, _p(cx, 1126.0, s_vals[0]), "easeOut"],
                [t1, _p(cx + dx_drift, 1146.0, s_vals[1]), "easeIn"],
                [d, _p(cx + dx_end, 1150.0, s_vals[2]), "linear"],
            ],
            d, fps,
        ),
    }
    return _prepend_cut_kick(mot, d, fps) if cut_kick else mot


def broll_camera(
    dur: float,
    mode: str = "push_in",
    scale_range: Sequence[float] = (106.0, 116.0),
    pos: Sequence[float] = (540.0, 960.0),
    pan_px: float = 36.0,
    fps: int = DEFAULT_FPS,
    cut_kick: bool = False,
) -> dict[str, Any]:
    """
    Smooth `@__dviet` B-roll plate camera choreography (`motion` dict):
      Modes:
        - `"push_in"`: `s_low -> s_high` optical push
        - `"pull_out"`: `s_high -> s_low` velvet settle-out
        - `"pan_left"`: lateral glide right-to-left (`px + pan_px/2 -> px - pan_px/2`) + gentle scale drift
        - `"pan_right"`: lateral glide left-to-right (`px - pan_px/2 -> px + pan_px/2`) + gentle scale drift
        - `"macro_crop"`: tight reframed macro (`>= 138%` if default scale passed) for detail isolation / face cropping
      `cut_kick`: When `True` and `dur >= 0.6s`, prepends a crisp 5-frame `+1.8%` scale settle impulse.
    """
    d = max(round(4 / fps, 6), snap_time(dur, fps))
    s_lo, s_hi = float(min(scale_range)), float(max(scale_range))
    px, py = float(pos[0]), float(pos[1])

    if mode == "pull_out":
        sc = [[0.0, s_hi, "easeOut"], [d, s_lo, "easeIn"]]
        ps: Any = [px, py]
    elif mode == "pan_left":
        s_start = max(s_lo, 110.0)
        sc = [[0.0, s_start, "easeOut"], [d, s_start + 4.0, "linear"]]
        ps = _strict_kf([[0.0, [round(px + pan_px * 0.5, 1), py], "easeOut"], [d, [round(px - pan_px * 0.5, 1), py], "easeIn"]], d, fps)
    elif mode == "pan_right":
        s_start = max(s_lo, 110.0)
        sc = [[0.0, s_start, "easeOut"], [d, s_start + 4.0, "linear"]]
        ps = _strict_kf([[0.0, [round(px - pan_px * 0.5, 1), py], "easeOut"], [d, [round(px + pan_px * 0.5, 1), py], "easeIn"]], d, fps)
    elif mode == "macro_crop":
        m_lo = s_lo if s_lo >= 125.0 else 138.0
        m_hi = s_hi if s_hi >= 132.0 else 150.0
        sc = [[0.0, m_lo, "easeOut"], [d, m_hi, "easeIn"]]
        ps = _strict_kf([[0.0, [px, py], "easeOut"], [d, [round(px - 10.0, 1), round(py - 8.0, 1)], "linear"]], d, fps)
    else:
        sc = [[0.0, s_lo, "easeOut"], [d, s_hi, "easeIn"]]
        ps = [px, py]

    mot = {
        "anchor": [540, 960],
        "scale": _strict_kf(sc, d, fps),
        "position": ps,
    }
    return _prepend_cut_kick(mot, d, fps) if cut_kick else mot


class SubcutPlan(float):
    """
    Float-compatible subcut timestamp (`isinstance(x, float) == True`, `float(x) == video_cut_t`)
    that ALSO exposes `.audio_cut_t`, `.video_cut_t`, `.j_lead_s`, `.mode`, and dict-style `x["audio_cut_t"]`!
    """

    audio_cut_t: float
    video_cut_t: float
    j_lead_s: float
    mode: str

    def __new__(
        cls,
        video_cut_t: float,
        *,
        audio_cut_t: float,
        j_lead_s: float,
        mode: str = "sync",
    ) -> "SubcutPlan":
        obj = super().__new__(cls, float(video_cut_t))
        obj.audio_cut_t = float(audio_cut_t)
        obj.video_cut_t = float(video_cut_t)
        obj.j_lead_s = round(float(j_lead_s), 6)
        obj.mode = str(mode)
        return obj

    def __getitem__(self, key: str) -> Any:
        if key in ("audio_cut_t", "video_cut_t", "j_lead_s", "mode"):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in ("audio_cut_t", "video_cut_t", "j_lead_s", "mode"):
            return getattr(self, key)
        return default

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "audio_cut_t": self.audio_cut_t,
            "video_cut_t": self.video_cut_t,
            "j_lead_s": self.j_lead_s,
        }


def _find_c7_clean_cut(
    words: Sequence[tuple[str, float, float]],
    t_target: float,
    max_search_s: float,
    fps: int,
) -> float:
    """Internal Rule-C7-safe cut timestamp finder near `t_target`."""
    if len(words) < 2:
        return snap_time(t_target, fps)

    best_cut: float | None = None
    best_dist = 999.0

    # Pass 1: Ideal C7 word-onset lead (~1 frame before a clean phrase/word onset with >= 105ms gap from previous onset)
    for wi in range(1, len(words)):
        w_on = words[wi][1]
        if abs(w_on - t_target) <= max_search_s:
            cand = snap_time(w_on - 1.0 / fps, fps)
            prev_on = words[wi - 1][1]
            lead = w_on - cand
            if prev_on < cand - 0.105 and 0.002 <= lead <= 0.085:
                dist = abs(cand - t_target)
                if dist < best_dist:
                    best_dist = dist
                    best_cut = cand

    if best_cut is not None:
        return best_cut

    # Pass 2: Pause midpoint where NO word onset lies inside `[cand - 0.105, cand + 0.155]`
    for wi in range(1, len(words)):
        prev_on = words[wi - 1][1]
        w_on = words[wi][1]
        lo_safe = prev_on + 0.108
        hi_safe = w_on - 0.158
        if lo_safe <= hi_safe:
            cand = snap_time(min(max(t_target, lo_safe), hi_safe), fps)
            if abs(cand - t_target) <= max_search_s and abs(cand - t_target) < best_dist:
                best_dist = abs(cand - t_target)
                best_cut = cand

    return best_cut if best_cut is not None else snap_time(t_target, fps)


def snap_subcut(
    words_tl: Sequence[Sequence[Any]],
    t_target: float,
    max_search_s: float = 0.85,
    fps: int = DEFAULT_FPS,
    *,
    mode: str = "sync",
    j_lead_s: float = 0.32,
) -> SubcutPlan:
    """
    `v6.0` Stateless Rule C7 `cut_lead`-safe intra-slice & bimodal `J-Cut` planner:
      - `mode="sync"` (default): `audio_cut_t == video_cut_t` at the cleanest C7 word-onset lead near `t_target`.
      - `mode="vocal_jcut"`: Bimodal `@__dviet` `770765` Vocal J-Cut!
        Locks `audio_cut_t` at the new vocal phrase onset near `t_target`, while holding the visual cut until
        `video_cut_t ≈ audio_cut_t + j_lead_s` (`~0.32s` later, snapped to a C7-clean stressed word onset),
        so the viewer hears the new thought lead in for `0.32s` BEFORE the camera angle / B-roll switches!
      - Returns `SubcutPlan(float)` (`isinstance(res, float) == True`, `float(res) == video_cut_t`, plus
        `res.audio_cut_t`, `res.video_cut_t`, `res.j_lead_s`, `res["audio_cut_t"]`, `res.as_dict()`).
    """
    m = str(mode or "sync").strip().lower()
    if m not in ("sync", "vocal_jcut"):
        raise ValueError(f"Unknown snap_subcut mode={mode!r}. Valid: 'sync', 'vocal_jcut'")

    words = _normalize_words_tl(words_tl)
    audio_cut = _find_c7_clean_cut(words, t_target, max_search_s=max_search_s, fps=fps)
    if m == "sync":
        return SubcutPlan(audio_cut, audio_cut_t=audio_cut, j_lead_s=0.0, mode="sync")

    lead_target = max(0.08, float(j_lead_s))
    raw_video_target = audio_cut + lead_target
    # Snap video_cut_t near `audio_cut + j_lead_s` while keeping video_cut_t >= audio_cut + 2 frames
    video_cut = _find_c7_clean_cut(words, raw_video_target, max_search_s=max(0.22, lead_target * 0.65), fps=fps)
    min_v_cut = snap_time(audio_cut + max(2.0 / fps, lead_target * 0.55), fps)
    if video_cut < min_v_cut:
        video_cut = snap_time(raw_video_target, fps)

    return SubcutPlan(
        video_cut,
        audio_cut_t=audio_cut,
        j_lead_s=round(video_cut - audio_cut, 6),
        mode="vocal_jcut",
    )


# ---------------------------------------------------------------------------
# `v7.1` Syllable-Locked `@__dviet` 12-Template Kinetic Beat Choreography Planner
# ---------------------------------------------------------------------------

KINETIC_12_CATALOG: dict[str, dict[str, Any]] = {
    "kt01_kiss_editorial_2line": {
        "id": "kt01_kiss_editorial_2line",
        "short_code": "kt01",
        "layout_silhouette": "SIL_KISS_2L",
        "entrance_style": "player3_air_cushion_kiss_20f",
        "tier_bucket": "hero_cluster",
        "supports_pill_badge": True,
        "default_rail": "auto",
        "width": 1080,
        "height": 440,
        "desc": "Negative-leading 0.78 lowercase editorial 2-line kiss with Player 3 Air-Cushion Bezier",
    },
    "kt02_feather_swash_overlap": {
        "id": "kt02_feather_swash_overlap",
        "short_code": "kt02",
        "layout_silhouette": "SIL_FEATHER_SWASH",
        "entrance_style": "feather29_swash_bloom_22f",
        "tier_bucket": "hero_cluster",
        "supports_pill_badge": True,
        "default_rail": "auto",
        "width": 1080,
        "height": 460,
        "desc": "Sub-layer Feather=29 ExtraBold + Playfair Italic Swash Overlap + Soft Optical Halation",
    },
    "kt03_per_word_nonlinear_bloom": {
        "id": "kt03_per_word_nonlinear_bloom",
        "short_code": "kt03",
        "layout_silhouette": "SIL_WORD_STAGGER",
        "entrance_style": "nonlinear_word_stagger_18f",
        "tier_bucket": "hero_cluster",
        "supports_pill_badge": False,
        "default_rail": "auto",
        "width": 1080,
        "height": 420,
        "desc": "Syllable-locked per-word nonlinear blur-to-sharp optical bloom",
    },
    "kt04_ghost_to_focus_stack": {
        "id": "kt04_ghost_to_focus_stack",
        "short_code": "kt04",
        "layout_silhouette": "SIL_GHOST_STACK",
        "entrance_style": "ghost_recede_focus_stack_24f",
        "tier_bucket": "hero_cluster",
        "supports_pill_badge": False,
        "default_rail": "auto",
        "width": 1080,
        "height": 460,
        "desc": "Receding translucent ghost stack pulling sharp foreground hero line into rack focus",
    },
    "kt05_wall_spatial_counterpoint": {
        "id": "kt05_wall_spatial_counterpoint",
        "short_code": "kt05",
        "layout_silhouette": "SIL_WALL_HOP",
        "entrance_style": "spatial_wall_hop_14f",
        "tier_bucket": "quiet_or_wall",
        "supports_pill_badge": False,
        "default_rail": "wall_third",
        "width": 1080,
        "height": 340,
        "desc": "Asymmetric wall negative-space 1–3 lowercase micro-word spatial counterpoint",
    },
    "kt06_bridge_anchor_live_swap": {
        "id": "kt06_bridge_anchor_live_swap",
        "short_code": "kt06",
        "layout_silhouette": "SIL_BRIDGE_SWAP",
        "entrance_style": "anchor_hold_slot_swap_16f",
        "tier_bucket": "specialty",
        "supports_pill_badge": False,
        "default_rail": "auto",
        "width": 1080,
        "height": 400,
        "desc": "Persistent anchor stem with live syllable-locked vertical slot word swap",
    },
    "kt07_telescoping_char_rollout": {
        "id": "kt07_telescoping_char_rollout",
        "short_code": "kt07",
        "layout_silhouette": "SIL_CHAR_ACCORDION",
        "entrance_style": "telescoping_tracking_rollout_18f",
        "tier_bucket": "specialty",
        "supports_pill_badge": True,
        "default_rail": "auto",
        "width": 1080,
        "height": 380,
        "desc": "Telescoping letter-spacing accordion rollout settling into tight -0.025em lock",
    },
    "kt08_mist_evaporation_reveal": {
        "id": "kt08_mist_evaporation_reveal",
        "short_code": "kt08",
        "layout_silhouette": "SIL_MIST_GRADIENT",
        "entrance_style": "mist_blur_evaporation_22f",
        "tier_bucket": "hero_cluster",
        "supports_pill_badge": False,
        "default_rail": "auto",
        "width": 1080,
        "height": 430,
        "desc": "Directional Gaussian mist & alpha-gradient mask evaporation reveal",
    },
    "kt09_strike_myth_laser_2phase": {
        "id": "kt09_strike_myth_laser_2phase",
        "short_code": "kt09",
        "layout_silhouette": "SIL_MYTH_STRIKE",
        "entrance_style": "laser_strike_2phase_flip_20f",
        "tier_bucket": "specialty",
        "supports_pill_badge": False,
        "default_rail": "auto",
        "width": 1080,
        "height": 450,
        "desc": "2-phase myth statement -> syllable-locked crimson laser strikethrough + jewel truth reveal",
    },
    "kt10_cursor_bars_pillar_gate": {
        "id": "kt10_cursor_bars_pillar_gate",
        "short_code": "kt10",
        "layout_silhouette": "SIL_CURSOR_HUD",
        "entrance_style": "cursor_pillar_gate_wipe_16f",
        "tier_bucket": "specialty",
        "supports_pill_badge": True,
        "default_rail": "auto",
        "width": 1080,
        "height": 390,
        "desc": "Dual optical cursor pillars parting outward to wipe-reveal precision tech/step phrase",
    },
    "kt11_cranial_svg_arc_or_tilt": {
        "id": "kt11_cranial_svg_arc_or_tilt",
        "short_code": "kt11",
        "layout_silhouette": "SIL_TILT_OR_ARC",
        "entrance_style": "svg_arc_tangent_glide_20f",
        "tier_bucket": "specialty",
        "supports_pill_badge": False,
        "default_rail": "upper_editorial_stage",
        "width": 1080,
        "height": 420,
        "desc": "Crown-tangent diagonal tilt (-8..+6 deg) or curved SVG textPath halo arc",
    },
    "kt12_whisper_or_directional_echo": {
        "id": "kt12_whisper_or_directional_echo",
        "short_code": "kt12",
        "layout_silhouette": "SIL_WHISPER_ECHO",
        "entrance_style": "whisper_directional_echo_12f",
        "tier_bucket": "quiet_or_wall",
        "supports_pill_badge": False,
        "default_rail": "chest_tactile_rail",
        "width": 1080,
        "height": 280,
        "desc": "Restrained 26–30pt lowercase editorial whisper or subtle directional echo breath",
    },
}

_KINETIC_ALIAS_MAP: dict[str, str] = {
    **{k: k for k in KINETIC_12_CATALOG},
    **{v["short_code"]: k for k, v in KINETIC_12_CATALOG.items()},
    **{v["layout_silhouette"].lower(): k for k, v in KINETIC_12_CATALOG.items()},
}

_FORMAT_MODE_ALIASES: dict[str, str] = {
    "f1": "F1", "expert_talking_head": "F1",
    "f2": "F2", "pas_bab_ecom_conversion": "F2",
    "f3": "F3", "tactile_review_testing": "F3",
    "f4": "F4", "clinical_aesthetic_before_after": "F4",
    "f5": "F5", "course_lead_magnet_funnel": "F5",
    "f6": "F6", "cinematic_vlog_storytelling": "F6",
    "f7": "F7", "tutorial_ui_walkthrough": "F7",
    "f8": "F8", "fast_paced_listicle_top_n": "F8",
    "f9": "F9", "spatial_vfx_clone_storefront_tour": "F9",
    "f10": "F10", "faceless_motion_explainer": "F10",
}

_INDUSTRY_SKIN_ALIASES: dict[str, str] = {
    "s1": "S1", "luxury_skincare": "S1", "skincare": "S1",
    "s2": "S2", "dental_clinic": "S2", "dental": "S2",
    "s3": "S3", "nail_hair_salon": "S3", "nail": "S3",
    "s4": "S4", "tactile_review": "S4", "review": "S4",
    "s5": "S5", "course_edtech": "S5", "course": "S5",
    "s6": "S6", "personal_brand": "S6",
    "s7": "S7", "cinematic_vlog": "S7", "vlog": "S7",
    "s8": "S8", "b2b_saas_realestate": "S8", "corporate": "S8", "b2b": "S8",
}

_MATCH_STRIP_RE = re.compile(r"^[\s,.;:!?…“”«»\"'‘’()\[\]{}<>—–•\-_/\\|]+|[\s,.;:!?…“”«»\"'‘’()\[\]{}<>—–•\-_/\\|]+$")
_EMDASH_BULLET_PREFIX_RE = re.compile(r"^[\s—–•\-:|/]+|[\s—–•\-:|/]+$")


def _norm_match_word(raw_tok: str) -> str:
    clean = _MATCH_STRIP_RE.sub("", unicodedata.normalize("NFC", str(raw_tok or "")).strip())
    return clean.lower()


def _is_fabricated_all_caps_kicker(raw_kicker: str) -> bool:
    s = unicodedata.normalize("NFC", str(raw_kicker or "")).strip()
    if not s:
        return False
    if s.startswith(("—", "–", "•", "//", "[")):
        return True
    letters = [ch for ch in s if ch.isalpha()]
    if len(letters) >= 3 and "".join(letters) == "".join(letters).upper() and "".join(letters) != "".join(letters).lower():
        return True
    return False


def _sanitize_dviet_kicker(
    raw_kicker: str,
    *,
    spoken_words_norm: set[str],
    industry_code: str,
    explicit_corporate_kicker: bool = False,
) -> str:
    """
    Law 1 (`v7.1`): Zero `— ALL CAPS KICKER` Spam!
      - Defaults to `""` or clean lowercase spoken setup words (`be vietnam pro` geometric sans).
      - Strips fabricated uppercase em-dash labels (`"— BƯỚC 1: ..."`, `"• MODULE 02"`) unless
        `industry_code == "S8"` AND `explicit_corporate_kicker=True`.
    """
    s = strip_inline_color_tags(unicodedata.normalize("NFC", str(raw_kicker or "")).strip())
    if not s:
        return ""
    if industry_code == "S8" and explicit_corporate_kicker:
        return _EMDASH_BULLET_PREFIX_RE.sub("", s).strip()

    was_fab = _is_fabricated_all_caps_kicker(s)
    stripped = _EMDASH_BULLET_PREFIX_RE.sub("", s).strip()
    if not stripped:
        return ""

    if was_fab:
        # If the kicker was a fabricated ALL-CAPS / em-dash label, drop it completely unless its words
        # are verbatim spoken setup words in this beat (in which case convert cleanly to lowercase!).
        toks = [_norm_match_word(t) for t in stripped.split() if _norm_match_word(t)]
        if not toks or not spoken_words_norm or not all(t in spoken_words_norm for t in toks):
            return ""
    return clean_display_text(stripped.lower())


def _match_phrase_in_words(
    phrase: str,
    norm_words: Sequence[tuple[str, str, float, float]],
    lo_idx: int,
    hi_idx: int,
) -> tuple[int, int] | None:
    """Find best `(start_idx, end_idx_inclusive)` match of `phrase` inside `norm_words[lo_idx:hi_idx]`."""
    p_toks = [_norm_match_word(t) for t in strip_inline_color_tags(phrase).split() if _norm_match_word(t)]
    if not p_toks or lo_idx >= hi_idx or lo_idx >= len(norm_words):
        return None
    hi_clamped = min(len(norm_words), max(lo_idx + 1, hi_idx))
    m = len(p_toks)

    best_span: tuple[int, int] | None = None
    best_score = 0.0
    for i in range(lo_idx, hi_clamped):
        if norm_words[i][0] != p_toks[0] and not (
            len(norm_words[i][0]) >= 3 and len(p_toks[0]) >= 3 and (norm_words[i][0].startswith(p_toks[0]) or p_toks[0].startswith(norm_words[i][0]))
        ):
            continue
        max_j = min(hi_clamped, i + m + 6)
        score = 0.0
        last_hit = i
        p_cur = 0
        gap_penalty = 0.0
        for j in range(i, max_j):
            if p_cur >= m:
                break
            w_n = norm_words[j][0]
            target_n = p_toks[p_cur]
            if not w_n:
                continue
            if w_n == target_n:
                score += 1.0
                last_hit = j
                p_cur += 1
            elif len(w_n) >= 3 and len(target_n) >= 3 and (w_n.startswith(target_n) or target_n.startswith(w_n)):
                score += 0.65
                last_hit = j
                p_cur += 1
            elif p_cur > 0:
                gap_penalty += 0.03
        norm_sc = (score / float(m)) - gap_penalty
        if norm_sc > best_score + 1e-6 and score >= max(1.0, m * 0.6):
            best_score = norm_sc
            best_span = (i, last_hit)
            if score >= m and gap_penalty == 0.0:
                break
    return best_span


def _split_beat_text_clauses(raw_text: str) -> tuple[str, str, str]:
    """Split a raw spoken beat phrase into `(kicker_setup, main_text, accent_text)` preserving word order."""
    clean = clean_display_text(strip_inline_color_tags(unicodedata.normalize("NFC", str(raw_text or ""))))
    toks = [t for t in clean.split() if t.strip()]
    if not toks:
        return ("", "", "")
    if len(toks) <= 2:
        return ("", " ".join(toks).lower(), "")
    if len(toks) <= 5:
        split_i = max(1, len(toks) - min(2, len(toks) // 2))
        while split_i > 1 and not can_split_after(toks, split_i - 1):
            split_i -= 1
        return ("", " ".join(toks[:split_i]).lower(), " ".join(toks[split_i:]).lower())
    # >= 6 words: setup kicker (2-3 words) + main_text + accent_text
    k_end = 2 if can_split_after(toks, 1) else min(3, len(toks) - 3)
    rem = toks[k_end:]
    m_end = max(1, len(rem) - min(3, max(2, len(rem) // 2)))
    while m_end > 1 and not can_split_after(rem, m_end - 1):
        m_end -= 1
    return (
        " ".join(toks[:k_end]).lower(),
        " ".join(rem[:m_end]).lower(),
        " ".join(rem[m_end:]).lower(),
    )


def _select_kinetic_templates_for_beats(
    norm_beats: Sequence[dict[str, Any]],
    *,
    video_seed: int = 0,
) -> list[str]:
    """
    Law 3 (`v7.1`): Dynamic Contrast Rhythm Solver:
      - Balances ~30–40% Hero Clusters (`kt01, kt02, kt03, kt04, kt08`)
        + ~30% Quiet/Wall (`kt12` Whisper / `kt05` Wall Counterpoint)
        + ~30% Specialty (`kt06, kt07, kt09, kt10, kt11`).
      - Hard guarantees:
          1. `0` consecutive duplicate `layout_silhouette`
          2. `0` consecutive duplicate `entrance_style`
          3. `<= 30%` max single-silhouette share (for `n >= 4`)
          4. `>= 5` distinct silhouettes when `n >= 8`.
    """
    n = len(norm_beats)
    if n == 0:
        return []

    hero_pool = [
        "kt01_kiss_editorial_2line",
        "kt02_feather_swash_overlap",
        "kt03_per_word_nonlinear_bloom",
        "kt08_mist_evaporation_reveal",
        "kt04_ghost_to_focus_stack",
    ]
    quiet_pool = [
        "kt12_whisper_or_directional_echo",
        "kt05_wall_spatial_counterpoint",
    ]
    spec_pool = [
        "kt06_bridge_anchor_live_swap",
        "kt09_strike_myth_laser_2phase",
        "kt10_cursor_bars_pillar_gate",
        "kt11_cranial_svg_arc_or_tilt",
        "kt07_telescoping_char_rollout",
    ]
    pools_by_bucket = {
        "hero_cluster": hero_pool,
        "quiet_or_wall": quiet_pool,
        "specialty": spec_pool,
    }

    max_per_sil = max(1, math.floor(n * 0.30)) if n >= 4 else 1

    # Step 1: Infer natural semantic bucket + preferred template for each beat
    natural_buckets: list[str] = []
    preferred_tpls: list[str | None] = []
    for idx, bd in enumerate(norm_beats):
        explicit_tpl = str(bd.get("template") or bd.get("kt_id") or "").strip().lower()
        resolved_exp = _KINETIC_ALIAS_MAP.get(explicit_tpl)
        role = unicodedata.normalize("NFC", str(bd.get("role") or bd.get("type") or "")).strip().lower()
        raw_k_sem = str(bd.get("kicker") or bd.get("lead_text") or "")
        safe_k_sem = "" if _is_fabricated_all_caps_kicker(raw_k_sem) else raw_k_sem
        txt_all = unicodedata.normalize(
            "NFC",
            f"{safe_k_sem} {bd.get('main_text', '')} {bd.get('hero_text', '')} {bd.get('accent_text', '')} {bd.get('text', '')}",
        ).lower()

        if resolved_exp and bd.get("lock_template") is True:
            natural_buckets.append(KINETIC_12_CATALOG[resolved_exp]["tier_bucket"])
            preferred_tpls.append(resolved_exp)
            continue

        if role in ("quiet", "whisper", "wall", "setup", "breathing") or bd.get("is_quiet") is True:
            natural_buckets.append("quiet_or_wall")
            preferred_tpls.append("kt05_wall_spatial_counterpoint" if role == "wall" or bd.get("cam_mode") in ("left_third", "right_third") else "kt12_whisper_or_directional_echo")
        elif bd.get("is_pain") is True or role in _PAIN_ROLES or any(k in txt_all for k in ("giả trân", "nhựa", "sai lầm", "bệnh", "biến dạng", "đừng")):
            natural_buckets.append("specialty")
            preferred_tpls.append("kt09_strike_myth_laser_2phase")
        elif bd.get("swap_words") or role in ("swap", "bridge_swap") or "chuyển hóa" in txt_all:
            natural_buckets.append("specialty")
            preferred_tpls.append("kt06_bridge_anchor_live_swap")
        elif bd.get("has_arc") or abs(float(bd.get("tilt_deg", 0.0) or 0.0)) > 1.0 or role in ("arc", "tilt"):
            natural_buckets.append("specialty")
            preferred_tpls.append("kt11_cranial_svg_arc_or_tilt")
        elif role in ("step", "tech", "specs", "ai", "cta", "hud") or any(k in txt_all for k in ("bước 1", "bước 2", "bước 3", "bước thứ", "prompt", "3 bước")):
            natural_buckets.append("specialty")
            preferred_tpls.append("kt10_cursor_bars_pillar_gate" if "bước" in txt_all or "prompt" in txt_all else "kt07_telescoping_char_rollout")
        elif idx == 0 or role in ("hook", "hero", "thesis", "solution", "authority"):
            natural_buckets.append("hero_cluster")
            preferred_tpls.append(resolved_exp if (resolved_exp and KINETIC_12_CATALOG[resolved_exp]["tier_bucket"] == "hero_cluster") else None)
        else:
            wave = ("hero_cluster", "quiet_or_wall", "specialty")[(idx + video_seed) % 3]
            natural_buckets.append(wave)
            preferred_tpls.append(resolved_exp)

    # Step 2: Enforce ~30–40% Hero + ~30% Quiet/Wall + ~30% Specialty quotas when n >= 6
    if n >= 6:
        target_quiet = min(len(quiet_pool) * max_per_sil, max(1, round(n * 0.28)))
        target_spec = min(len(spec_pool) * max_per_sil, max(2, round(n * 0.34)))
        target_hero = max(2, n - target_quiet - target_spec)
        # Keep hero strictly inside ~30-42%
        while target_hero > math.ceil(n * 0.42) and target_spec < len(spec_pool) * max_per_sil:
            target_hero -= 1
            target_spec += 1
        quotas = {
            "hero_cluster": target_hero,
            "quiet_or_wall": target_quiet,
            "specialty": target_spec,
        }
        cur_counts = {b: natural_buckets.count(b) for b in quotas}
        # Rebalance excess buckets into deficit buckets (protecting idx == 0 hook as hero_cluster when possible)
        for idx in range(n - 1, 0, -1):
            b_cur = natural_buckets[idx]
            if cur_counts[b_cur] > quotas[b_cur]:
                deficit_b = next((bk for bk in ("quiet_or_wall", "specialty", "hero_cluster") if cur_counts[bk] < quotas[bk]), None)
                if deficit_b is not None:
                    natural_buckets[idx] = deficit_b
                    cur_counts[b_cur] -= 1
                    cur_counts[deficit_b] += 1

    # Step 3: Assign exact `kt01..kt12` templates with 0 consecutive sil/entrance repeats & <= 30% cap
    chosen: list[str] = []
    sil_counts: dict[str, int] = {}

    for idx in range(n):
        bkt = natural_buckets[idx]
        pref_t = preferred_tpls[idx]
        prev_sil = KINETIC_12_CATALOG[chosen[-1]]["layout_silhouette"] if chosen else ""
        prev_ent = KINETIC_12_CATALOG[chosen[-1]]["entrance_style"] if chosen else ""

        # Candidate order: preferred (if in bucket or valid), then bucket pool sorted by lowest usage (maximizing distinctness!), then all 12
        b_pool = list(pools_by_bucket[bkt])
        rot_shift = (idx + video_seed) % len(b_pool)
        rotated_b_pool = b_pool[rot_shift:] + b_pool[:rot_shift]
        # Prefer unused silhouettes first so n >= 8 easily hits >= 6-9 distinct silhouettes!
        rotated_b_pool.sort(key=lambda k: sil_counts.get(KINETIC_12_CATALOG[k]["layout_silhouette"], 0))

        all_fallback = sorted(
            KINETIC_12_CATALOG.keys(),
            key=lambda k: (
                0 if KINETIC_12_CATALOG[k]["tier_bucket"] == bkt else 1,
                sil_counts.get(KINETIC_12_CATALOG[k]["layout_silhouette"], 0),
            ),
        )

        ordered_cands: list[str] = []
        if pref_t and pref_t in KINETIC_12_CATALOG and (KINETIC_12_CATALOG[pref_t]["tier_bucket"] == bkt or norm_beats[idx].get("lock_template") is True):
            ordered_cands.append(pref_t)
        for c_k in (*rotated_b_pool, *all_fallback):
            if c_k not in ordered_cands:
                ordered_cands.append(c_k)

        picked: str | None = None
        for cand in ordered_cands:
            c_meta = KINETIC_12_CATALOG[cand]
            c_sil = c_meta["layout_silhouette"]
            c_ent = c_meta["entrance_style"]
            if c_sil == prev_sil or c_ent == prev_ent:
                continue
            if sil_counts.get(c_sil, 0) >= max_per_sil:
                continue
            picked = cand
            break

        if picked is None:
            # Relax cap by +1 only if mathematically forced, still forbidding consecutive duplicate
            for cand in ordered_cands:
                c_meta = KINETIC_12_CATALOG[cand]
                if c_meta["layout_silhouette"] != prev_sil and c_meta["entrance_style"] != prev_ent:
                    picked = cand
                    break
        if picked is None:
            picked = ordered_cands[0]

        chosen.append(picked)
        s_key = KINETIC_12_CATALOG[picked]["layout_silhouette"]
        sil_counts[s_key] = sil_counts.get(s_key, 0) + 1

    return chosen


_SAFE_X_MIN, _SAFE_X_MAX = 48.0, 1032.0  # 1080-wide border-safe box (matches `resolve_dual_rail_safe_y` margins)


def _kt05_ink_x_in_plate(plate_w: float, left_text: str, main_text: str, accent_text: str) -> tuple[float, float]:
    """Horizontal ink span `(x0, x1)` in plate px of the `kt05` left/right counterpoint: the left clause is centred at
    28% (max 45% wide, ~48px), the right hero + sub at 72% (max 46% wide, ~64px / ~40px) of the plate."""
    spans: list[tuple[float, float]] = []
    if left_text:
        w = min(0.45 * plate_w, 0.52 * 48.0 * len(left_text))
        spans.append((0.28 * plate_w - 0.5 * w, 0.28 * plate_w + 0.5 * w))
    right_w = min(0.46 * plate_w, max(0.58 * 64.0 * len(main_text), 0.50 * 40.0 * len(accent_text)))
    if right_w > 0.0:
        spans.append((0.72 * plate_w - 0.5 * right_w, 0.72 * plate_w + 0.5 * right_w))
    if not spans:
        return 0.5 * plate_w - 195.0, 0.5 * plate_w + 195.0
    return min(a for a, _ in spans), max(b for _, b in spans)


def plan_dviet_kinetic_beat_schedule(
    beats: Sequence[dict[str, Any] | str],
    words_tl: Any = None,
    *,
    format_mode: str = "F1",
    industry_skin: str = "S6",
    color_policy: str = "semantic_4act_jewel",
    cranial_zone: dict[str, Any] | Sequence[float] | None = None,
    cut_times: Sequence[float] | None = None,
    fps: int = 60,
    out_dir: str | Path | None = None,
    world_id: str | None = None,
    video_seed: int = 0,
) -> dict[str, Any]:
    """
    `v7.1` **Syllable-Locked `@__dviet` Kinetic Beat Choreography Planner**:
      - Accepts `beats` + `words_tl` (`[[word, start_s, end_s], ...]`, `[{"word":..., "start_ms":..., "end_ms":...}]`,
        or `transcript_ms.json` `words_nfc` dicts / file path).
      - Enforces all 5 `@__dviet` 19-Video Empirical Laws:
          1. **Zero `— ALL CAPS KICKER` Spam:** Strips fabricated uppercase em-dash kickers (unless explicit `S8` corporate lower-third).
          2. **Strict Pill Badge Restraint:** `<= 20%` of beats, max `2–3` unique single-use pills, `0` duplicates, `0` on `F6`/`S7`.
          3. **Dynamic Contrast Rhythm:** `~30–40%` Hero Clusters + `~30%` Quiet/Wall (`kt12`/`kt05`) + `~30%` Specialty (`kt06..kt11`),
             `0` consecutive duplicate `layout_silhouette`, `0` consecutive duplicate `entrance_style`, `<= 30%` max silhouette share,
             `>= 5` distinct silhouettes when `len(beats) >= 8`.
          4. **Exact Syllable-Onset Trigger Alignment (`0` Premature Spoilers):** Locks `kicker_at_s`, `main_at_s`, `accent_at_s`,
             `slash_at_s`, `word_triggers`, and `swap_words` within `±2 frames` of actual spoken syllable onset (`t_word_start - clip_at_s`).
          5. **Dual-Rail `0%` Cranial Lock Coordinates:** Uses `resolve_dual_rail_safe_y` to assign collision-free
             `upper_editorial_stage` / `chest_tactile_rail` / `wall_third` coordinates and emits `batch_jobs` ready for
             `web_plate_builder.render_kinetic_typo_batch`.
    """
    fps_i = max(24, int(round(float(fps))))
    fmt_code = _FORMAT_MODE_ALIASES.get(str(format_mode or "F1").strip().lower(), str(format_mode or "F1").strip().upper())
    skin_code = _INDUSTRY_SKIN_ALIASES.get(str(industry_skin or "S6").strip().lower(), str(industry_skin or "S6").strip().upper())
    pol_mode = str(color_policy or "semantic_4act_jewel").strip().lower()
    if pol_mode not in ("semantic_4act_jewel", "color_world_polarity"):
        raise ValueError(f"Unsupported color_policy={color_policy!r}. Valid: 'semantic_4act_jewel', 'color_world_polarity'")

    norm_beats: list[dict[str, Any]] = [
        copy.deepcopy(b) if isinstance(b, dict) else {"text": str(b)}
        for b in beats
    ]
    n = len(norm_beats)
    parsed_words = _normalize_words_tl(words_tl)
    norm_words: list[tuple[str, str, float, float]] = [
        (_norm_match_word(tok), tok, t0, t1) for tok, t0, t1 in parsed_words
    ]
    plates_dir = Path(out_dir) if out_dir is not None else Path("web_plates")

    if n == 0:
        return {
            "version": "7.1",
            "format_mode": fmt_code,
            "industry_skin": skin_code,
            "color_policy": pol_mode,
            "fps": fps_i,
            "stats": {
                "total_beats": 0,
                "distinct_silhouettes": 0,
                "max_silhouette_share": 0.0,
                "pill_badge_count": 0,
                "pill_badge_ratio": 0.0,
                "fabricated_kickers_blocked": 0,
                "max_syllable_onset_drift_frames": 0.0,
                "cranial_lock_100pct": True,
            },
            "beats": [],
            "batch_jobs": [],
            "craft_clips": [],
        }

    # Parse global cranial_zone hints
    cz_hair: float | None = None
    cz_chin: float | None = None
    cz_face_bbox: Sequence[float] | None = None
    cz_enamel_bbox: Sequence[float] | None = None
    cz_macro_bbox: Sequence[float] | None = None
    if isinstance(cranial_zone, dict):
        if cranial_zone.get("hair_top_y") is not None:
            cz_hair = float(cranial_zone["hair_top_y"])
        if cranial_zone.get("chin_y") is not None:
            cz_chin = float(cranial_zone["chin_y"])
        cz_face_bbox = cranial_zone.get("face_bbox")
        cz_enamel_bbox = cranial_zone.get("enamel_gum_bbox")
        cz_macro_bbox = cranial_zone.get("macro_subject_bbox")
    elif isinstance(cranial_zone, (list, tuple)) and len(cranial_zone) >= 2:
        if len(cranial_zone) == 2:
            cz_hair, cz_chin = float(cranial_zone[0]), float(cranial_zone[1])
        elif len(cranial_zone) >= 4:
            cz_face_bbox = [float(x) for x in cranial_zone[:4]]

    # Select dynamic contrast templates (`kt01..kt12`)
    assigned_templates = _select_kinetic_templates_for_beats(norm_beats, video_seed=video_seed)

    # Plan chromatic palette per beat
    cw_plan = plan_color_world_for_video(norm_beats, world_id=world_id, video_seed=video_seed)
    skin_jewel_key = {
        "S1": "skincare_pearl_rose",
        "S2": "dental_porcelain_ice",
        "S3": "nail_blush_champagne",
    }.get(skin_code)

    # Law 2: Pill Badge Budget (`<= 20%` of beats, max `3` unique pills, `0` duplicates, `0` on `F6`/`S7`)
    forbid_pills = fmt_code == "F6" or skin_code == "S7"
    max_pills_allowed = 0 if forbid_pills else min(3, math.floor(n * 0.20))
    seen_badge_keys: set[str] = set()
    pills_allocated = 0

    word_cursor = 0
    fabricated_kickers_blocked = 0
    max_onset_drift_f = 0.0
    planned_beats: list[dict[str, Any]] = []
    batch_jobs: list[dict[str, Any]] = []
    craft_clips: list[dict[str, Any]] = []

    for idx, (bd, tpl_id) in enumerate(zip(norm_beats, assigned_templates)):
        tpl_meta = KINETIC_12_CATALOG[tpl_id]
        sil = tpl_meta["layout_silhouette"]
        ent_style = str(bd.get("entrance_style") or tpl_meta["entrance_style"])
        if planned_beats and ent_style == planned_beats[-1]["entrance_style"]:
            ent_style = tpl_meta["entrance_style"]

        # Extract or split beat text clauses cleanly
        raw_kicker_in = str(bd.get("kicker") if bd.get("kicker") is not None else (bd.get("lead_text") or "")).strip()
        raw_main_in = str(bd.get("main_text") if bd.get("main_text") is not None else (bd.get("hero_text") or "")).strip()
        raw_accent_in = str(bd.get("accent_text") if bd.get("accent_text") is not None else (bd.get("sub_text") or "")).strip()
        raw_full_text = str(bd.get("text") or "").strip()

        if not raw_main_in and raw_full_text:
            sp_k, sp_m, sp_a = _split_beat_text_clauses(raw_full_text)
            if not raw_kicker_in:
                raw_kicker_in = sp_k
            raw_main_in = sp_m
            if not raw_accent_in:
                raw_accent_in = sp_a
        if not raw_main_in and raw_accent_in:
            raw_main_in, raw_accent_in = raw_accent_in, ""

        # Locate beat's spoken word window inside `norm_words`
        hint_at = float(bd["at"]) if bd.get("at") is not None else (float(bd["start_s"]) if bd.get("start_s") is not None else None)
        hint_dur = float(bd["dur"]) if bd.get("dur") is not None else (
            (float(bd["end_s"]) - float(hint_at or 0.0)) if bd.get("end_s") is not None else None
        )

        if norm_words:
            if hint_at is not None:
                lo_w = 0
                while lo_w < len(norm_words) and norm_words[lo_w][3] < hint_at - 0.85:
                    lo_w += 1
                hi_end_t = hint_at + max(1.6, float(hint_dur or 2.8)) + 1.15
                hi_w = lo_w
                while hi_w < len(norm_words) and norm_words[hi_w][2] <= hi_end_t:
                    hi_w += 1
                hi_w = max(min(len(norm_words), lo_w + 1), hi_w)
            else:
                lo_w = min(word_cursor, len(norm_words) - 1)
                hi_w = min(len(norm_words), lo_w + 80)
        else:
            lo_w, hi_w = 0, 0

        beat_window_norm_set = {norm_words[j][0] for j in range(lo_w, min(len(norm_words), lo_w + 90)) if norm_words[j][0]}

        # Law 1: Sanitize kicker (0 `— ALL CAPS` spam!)
        explicit_corp = bool(
            bd.get("allow_corporate_kicker") is True
            or bd.get("explicit_corporate_lower_third") is True
            or str(bd.get("role") or "").strip().lower() == "corporate_lower_third"
        )
        if raw_kicker_in and _is_fabricated_all_caps_kicker(raw_kicker_in) and not (skin_code == "S8" and explicit_corp):
            fabricated_kickers_blocked += 1
        kicker_clean = _sanitize_dviet_kicker(
            raw_kicker_in,
            spoken_words_norm=beat_window_norm_set,
            industry_code=skin_code,
            explicit_corporate_kicker=explicit_corp,
        )
        preserve_case = bool(bd.get("preserve_case", False))
        main_clean = clean_display_text(strip_inline_color_tags(_lowercase_preserving_inline_tags(raw_main_in, preserve_case=preserve_case)))
        accent_clean = clean_display_text(strip_inline_color_tags(_lowercase_preserving_inline_tags(raw_accent_in, preserve_case=preserve_case)))

        # Law 2: Enforce Strict Pill Badge Restraint
        raw_badge = strip_inline_color_tags(unicodedata.normalize("NFC", str(bd.get("badge_text") or bd.get("pill_text") or "")).strip())
        raw_badge = _EMDASH_BULLET_PREFIX_RE.sub("", raw_badge).strip()
        badge_norm_key = raw_badge.casefold()
        if (
            raw_badge
            and not forbid_pills
            and tpl_meta.get("supports_pill_badge", False)
            and pills_allocated < max_pills_allowed
            and badge_norm_key not in seen_badge_keys
        ):
            badge_final = raw_badge
            has_pill_badge = True
            seen_badge_keys.add(badge_norm_key)
            pills_allocated += 1
        else:
            badge_final = ""
            has_pill_badge = False

        # Law 4: Exact Syllable-Onset Trigger Alignment (`±2 frames`, `0` premature spoilers!)
        search_cur = lo_w
        k_span = _match_phrase_in_words(kicker_clean, norm_words, search_cur, hi_w) if (kicker_clean and norm_words) else None
        if k_span is None and kicker_clean and norm_words and hi_w < len(norm_words):
            k_span = _match_phrase_in_words(kicker_clean, norm_words, search_cur, len(norm_words))
        if k_span is not None:
            search_cur = max(search_cur, k_span[0])
            hi_w = max(hi_w, min(len(norm_words), k_span[1] + 45))
        m_span = _match_phrase_in_words(main_clean, norm_words, search_cur, hi_w) if (main_clean and norm_words) else None
        if m_span is None and main_clean and norm_words and hi_w < len(norm_words):
            m_span = _match_phrase_in_words(main_clean, norm_words, search_cur, len(norm_words))
        if m_span is None and main_clean and norm_words and search_cur > lo_w:
            m_span = _match_phrase_in_words(main_clean, norm_words, lo_w, hi_w)
        if m_span is not None:
            search_cur = max(search_cur, m_span[1] + 1 if accent_clean else m_span[0])
            hi_w = max(hi_w, min(len(norm_words), m_span[1] + 45))
        a_span = _match_phrase_in_words(accent_clean, norm_words, min(search_cur, max(0, hi_w - 1)), hi_w) if (accent_clean and norm_words) else None
        if a_span is None and accent_clean and norm_words and hi_w < len(norm_words):
            a_span = _match_phrase_in_words(accent_clean, norm_words, min(search_cur, len(norm_words) - 1), len(norm_words))
        if a_span is None and accent_clean and norm_words:
            a_span = _match_phrase_in_words(accent_clean, norm_words, lo_w, hi_w)

        matched_spans = [sp for sp in (k_span, m_span, a_span) if sp is not None]
        if matched_spans:
            first_w_idx = min(sp[0] for sp in matched_spans)
            last_w_idx = max(sp[1] for sp in matched_spans)
            word_cursor = max(word_cursor, last_w_idx + 1)
            first_spoken_s = norm_words[first_w_idx][2]
            last_spoken_end_s = norm_words[last_w_idx][3]
            if hint_at is not None and bd.get("lock_at") is True:
                clip_at_s = max(0.0, snap_time(hint_at, fps_i))
            else:
                # Anchor clip_at_s 1 frame before earliest spoken word of this beat!
                clip_at_s = max(0.0, snap_time(first_spoken_s - (1.0 / fps_i), fps_i))
            natural_end_s = max(last_spoken_end_s + 0.18, (clip_at_s + float(hint_dur)) if hint_dur is not None else (last_spoken_end_s + 0.24))
            dur_s = max(snap_time(12.0 / fps_i, fps_i), snap_time(natural_end_s - clip_at_s, fps_i))
        else:
            fallback_at = hint_at if hint_at is not None else (idx * 2.4)
            clip_at_s = max(0.0, snap_time(fallback_at, fps_i))
            dur_s = max(snap_time(18.0 / fps_i, fps_i), snap_time(float(hint_dur or 1.8), fps_i))
            first_w_idx, last_w_idx = -1, -1

        # Optional C8 cut-boundary trim unless beat requests persistent_bridge
        want_bridge = bool(bd.get("persistent_bridge", False))
        if cut_times and not want_bridge:
            end_cand = clip_at_s + dur_s
            nearest_c = min((float(c) for c in cut_times), key=lambda ct: abs(end_cand - ct))
            if 0.0 < (end_cand - nearest_c) <= (12.0 / fps_i) and (nearest_c - clip_at_s) >= 0.35:
                dur_s = max(snap_time(10.0 / fps_i, fps_i), snap_time(nearest_c - (1.0 / fps_i) - clip_at_s, fps_i))

        # Compute exact relative trigger times (`t_word_start - clip_at_s`) within ±1 frame (<= ±2f)!
        def _rel_onset(span_pair: tuple[int, int] | None, default_rel: float) -> tuple[float, float | None]:
            if span_pair is not None and norm_words:
                abs_t = norm_words[span_pair[0]][2]
                rel_t = snap_time(max(0.0, abs_t - clip_at_s), fps_i)
                drift_f = abs((clip_at_s + rel_t) - abs_t) * fps_i
                nonlocal max_onset_drift_f
                if drift_f > max_onset_drift_f:
                    max_onset_drift_f = drift_f
                return rel_t, round(abs_t, 6)
            return snap_time(max(0.0, default_rel), fps_i), None

        kicker_at_s, kicker_abs_s = _rel_onset(k_span, 0.0) if kicker_clean else (0.0, None)
        default_main_rel = 0.14 if kicker_clean else 0.0
        main_at_s, main_abs_s = _rel_onset(m_span, default_main_rel)
        # Guarantee main never fires before spoken kicker if kicker precedes main
        if kicker_clean and k_span is not None and m_span is None:
            main_at_s = snap_time(min(dur_s * 0.45, kicker_at_s + 0.18), fps_i)
        default_acc_rel = min(max(0.0, dur_s - 0.25), main_at_s + 0.28)
        accent_at_s, accent_abs_s = _rel_onset(a_span, default_acc_rel) if accent_clean else (main_at_s, main_abs_s)

        # `slash_at_s` for `kt09_strike_myth_laser_2phase` (fires on refutation pivot onset!)
        if tpl_id == "kt09_strike_myth_laser_2phase" or bd.get("has_slash") is True:
            if a_span is not None and norm_words:
                piv_abs = norm_words[a_span[0]][2]
                slash_at_s = snap_time(max(0.0, piv_abs - clip_at_s), fps_i)
            elif m_span is not None and norm_words:
                piv_abs = norm_words[m_span[1]][2]
                slash_at_s = snap_time(max(0.0, piv_abs - clip_at_s), fps_i)
            else:
                slash_at_s = snap_time(min(dur_s * 0.52, main_at_s + 0.30), fps_i)
        else:
            slash_at_s = None

        # Per-word syllable triggers inside the matched beat span
        word_triggers: list[dict[str, Any]] = []
        if first_w_idx >= 0 and last_w_idx >= first_w_idx and norm_words:
            for wi in range(first_w_idx, last_w_idx + 1):
                _wn, w_raw, wt0, wt1 = norm_words[wi]
                if wt0 < clip_at_s - (2.0 / fps_i) or wt0 > clip_at_s + dur_s + 0.05:
                    continue
                w_rel = snap_time(max(0.0, wt0 - clip_at_s), fps_i)
                w_end_rel = snap_time(min(dur_s, max(w_rel + 2.0 / fps_i, wt1 - clip_at_s)), fps_i)
                drift_w = abs((clip_at_s + w_rel) - wt0) * fps_i
                if drift_w > max_onset_drift_f:
                    max_onset_drift_f = drift_w
                word_triggers.append(
                    {
                        "word": clean_display_text(w_raw),
                        "at_s": w_rel,
                        "end_s": w_end_rel,
                        "abs_onset_s": round(wt0, 6),
                    }
                )

        # `swap_words` alignment (`kt06_bridge_anchor_live_swap` or explicit `swap_words`)
        raw_swaps = bd.get("swap_words")
        swap_words_aligned: list[dict[str, Any]] = []
        if isinstance(raw_swaps, (list, tuple)) and raw_swaps:
            sw_cur = first_w_idx if first_w_idx >= 0 else lo_w
            for s_idx, sw_item in enumerate(raw_swaps):
                sw_txt = str(sw_item.get("word") or sw_item.get("text") or "") if isinstance(sw_item, dict) else str(sw_item)
                sw_clean = clean_display_text(_lowercase_preserving_inline_tags(sw_txt, preserve_case=preserve_case))
                sw_sp = _match_phrase_in_words(sw_clean, norm_words, sw_cur, hi_w) if (sw_clean and norm_words) else None
                if sw_sp is not None:
                    sw_cur = max(sw_cur, sw_sp[1] + 1)
                    sw_rel, sw_abs = _rel_onset(sw_sp, main_at_s + s_idx * 0.28)
                else:
                    sw_rel = snap_time(min(max(0.0, dur_s - 4.0 / fps_i), main_at_s + s_idx * 0.28), fps_i)
                    sw_abs = None
                swap_words_aligned.append({"word": sw_clean, "at_s": sw_rel, "abs_onset_s": sw_abs})
        elif tpl_id == "kt06_bridge_anchor_live_swap":
            for cand_txt, cand_at, cand_abs in ((main_clean, main_at_s, main_abs_s), (accent_clean, accent_at_s, accent_abs_s)):
                if cand_txt:
                    swap_words_aligned.append({"word": cand_txt, "at_s": cand_at, "abs_onset_s": cand_abs})

        # Chromatic resolution (`semantic_4act_jewel` vs `color_world_polarity`)
        polarity = str(bd.get("polarity") or cw_plan["beats"][idx]["polarity"] or "dark").strip().lower()
        is_pain_beat = bool(bd.get("is_pain") is True or tpl_id == "kt09_strike_myth_laser_2phase" or cw_plan["beats"][idx]["accent_role"] == "pain")
        if pol_mode == "semantic_4act_jewel":
            prog = idx / float(max(1, n - 1)) if n > 1 else 0.0
            if is_pain_beat:
                act_k = "act2"
            elif prog < 0.25:
                act_k = "act1"
            elif prog < 0.72:
                act_k = "act3a"
            else:
                act_k = "act3b"
            pal_4 = resolve_4act_jewel_palette(skin_jewel_key or act_k, act_key=act_k)
            accent_hex = str(pal_4.get("active_act_accent_hex") or pal_4["accent_hex"])
            base_hex = str(pal_4["text_on_light"] if polarity == "light" else pal_4["base_hex"])
            jewel_alias = {"act1": "gold", "act2": "crimson", "act3a": "emerald", "act3b": "ice_cyan"}.get(act_k, "gold")
        else:
            cw_b = cw_plan["beats"][idx]
            accent_hex = str(cw_b["hero_hex"])
            base_hex = str(cw_b["lead_hex"])
            jewel_alias = accent_hex

        # Law 5: Dual-Rail `0%` Cranial Lock Coordinate Resolution
        z_plane = str(bd.get("z_plane") or "foreground").strip().lower()
        b_hair = float(bd["hair_top_y"]) if bd.get("hair_top_y") is not None else cz_hair
        b_chin = float(bd["chin_y"]) if bd.get("chin_y") is not None else cz_chin
        b_face = bd.get("face_bbox") or cz_face_bbox
        b_enamel = bd.get("enamel_gum_bbox") or cz_enamel_bbox
        b_macro = bd.get("macro_subject_bbox") or cz_macro_bbox
        is_broll = bool(bd.get("is_broll", False))
        cam_mode = str(bd.get("cam_mode") or "center").strip().lower()

        pref_rail = str(bd.get("preferred_rail") or tpl_meta["default_rail"] or "auto").strip().lower()
        if pref_rail == "auto":
            pref_rail = "upper_editorial_stage" if (idx % 3 != 2) else "chest_tactile_rail"

        eff_text_sz = 32.0 if tpl_id == "kt12_whisper_or_directional_echo" else (52.0 if tpl_id == "kt05_wall_spatial_counterpoint" else 74.0)
        n_lines_est = 2 if (accent_clean and tpl_id != "kt06_bridge_anchor_live_swap") else 1
        rail_res = resolve_dual_rail_safe_y(
            hair_top_y=b_hair,
            chin_y=b_chin,
            preferred_rail="upper" if pref_rail == "wall_third" else pref_rail,
            face_bbox=b_face,
            enamel_gum_bbox=b_enamel,
            macro_subject_bbox=b_macro,
            text_size=eff_text_sz,
            line_count=n_lines_est,
            line_height=0.82,
            has_lead=bool(kicker_clean),
            lead_size=28.0,
            is_broll=is_broll,
            z_plane=z_plane,
        )

        plate_w = int(tpl_meta["width"])
        plate_h = int(tpl_meta["height"])
        if tpl_id == "kt05_wall_spatial_counterpoint" or pref_rail == "wall_third":
            rail_label = "wall_third"
            pos_x = {"right_third": 345.0, "left_third": 735.0}.get(cam_mode, 540.0)
            if tpl_id == "kt05_wall_spatial_counterpoint":
                ink_px0, ink_px1 = _kt05_ink_x_in_plate(plate_w, kicker_clean, main_clean, accent_clean)
            else:
                ink_px0, ink_px1 = plate_w / 2.0 - 195.0, plate_w / 2.0 + 195.0
            # The plate is centred on `pos_x`; slide it so its real ink stays inside the safe box.
            sx0 = pos_x - plate_w / 2.0
            shift = max(0.0, _SAFE_X_MIN - (sx0 + ink_px0))
            if sx0 + ink_px1 + shift > _SAFE_X_MAX:
                shift = _SAFE_X_MAX - (sx0 + ink_px1)
            pos_x = round(pos_x + shift, 1)
            ink_x0, ink_x1 = pos_x - plate_w / 2.0 + ink_px0, pos_x - plate_w / 2.0 + ink_px1
        else:
            rail_label = str(rail_res["rail"])
            pos_x = 540.0
            ink_x0, ink_x1 = max(50.0, pos_x - 360.0), min(1030.0, pos_x + 360.0)

        pos_y = float(rail_res["y"])
        iy0, iy1 = float(rail_res["ink_y_span"][0]), float(rail_res["ink_y_span"][1])
        ink_bbox_screen = [round(ink_x0, 1), round(iy0, 1), round(ink_x1, 1), round(iy1, 1)]
        # Align plate center vertically to the midpoint of `[iy0, iy1]` so plate ink matches `ink_bbox_screen`!
        plate_center_y = round(0.5 * (iy0 + iy1), 1)

        out_mov_path = (plates_dir / f"kt_{idx + 1:02d}_{tpl_meta['short_code']}.mov").as_posix()
        typo_meta_obj: dict[str, Any] = {
            "version": "7.1",
            "beat_index": idx,
            "template": tpl_id,
            "short_code": tpl_meta["short_code"],
            "layout_silhouette": sil,
            "entrance_style": ent_style,
            "tier_bucket": tpl_meta["tier_bucket"],
            "mode": "mov",
            "has_pill_badge": has_pill_badge,
            "badge_text": badge_final,
            "kicker": kicker_clean,
            "main_text": main_clean,
            "accent_text": accent_clean,
            "base_hex": base_hex,
            "accent_hex": accent_hex,
            "polarity": polarity,
            "z_plane": z_plane,
            "rail": rail_label,
            "pos_x": pos_x,
            "pos_y": plate_center_y,
            "plate_width": plate_w,
            "plate_height": plate_h,
            "ink_bbox_screen": ink_bbox_screen,
            "cranial_lock_verified": bool(rail_res["cranial_lock_verified"]),
            "kicker_at_s": kicker_at_s if kicker_clean else None,
            "main_at_s": main_at_s,
            "accent_at_s": accent_at_s if accent_clean else None,
            "slash_at_s": slash_at_s,
            "word_triggers": word_triggers,
            "swap_words": swap_words_aligned,
        }

        props_obj: dict[str, Any] = {
            "kicker": kicker_clean,
            "main_text": main_clean,
            "accent_text": accent_clean,
            "badge_text": badge_final,
            "has_pill_badge": has_pill_badge,
            "jewel_accent": jewel_alias,
            "base_hex": base_hex,
            "accent_hex": accent_hex,
            "polarity": polarity,
            "layout_silhouette": sil,
            "entrance_style": ent_style,
            "rail": rail_label,
            "cam_mode": cam_mode,
            "kicker_at_s": kicker_at_s if kicker_clean else None,
            "main_at_s": main_at_s,
            "accent_at_s": accent_at_s if accent_clean else None,
            "slash_at_s": slash_at_s,
            "word_triggers": word_triggers,
            "swap_words": swap_words_aligned,
            "fps": fps_i,
            "duration_sec": dur_s,
        }

        craft_clip_obj: dict[str, Any] = {
            "name": f"KT{idx + 1:02d} · {tpl_meta['short_code']} · {(main_clean or accent_clean)[:18]}",
            "src": out_mov_path,
            "in": 0.0,
            "at": clip_at_s,
            "dur": dur_s,
            "motion": {
                "anchor": [round(plate_w * 0.5, 1), round(plate_h * 0.5, 1)],
                "position": [pos_x, plate_center_y],
                "scale": 100.0,
            },
            "opacity": 100.0,
            "z_plane": z_plane,
            "typo_kinetic_meta": typo_meta_obj,
        }
        if want_bridge:
            craft_clip_obj["persistent_bridge"] = True

        job_obj: dict[str, Any] = {
            "beat_id": f"beat_{idx + 1:02d}",
            "beat_index": idx,
            "template": tpl_id,
            "layout_silhouette": sil,
            "entrance_style": ent_style,
            "mode": "mov",
            "out": out_mov_path,
            "meta_out": f"{out_mov_path}.typo_meta.json",
            "width": plate_w,
            "height": plate_h,
            "fps": fps_i,
            "duration_sec": dur_s,
            "total_frames": max(6, int(round(dur_s * fps_i))),
            "at": clip_at_s,
            "dur": dur_s,
            "rail": rail_label,
            "pos": [pos_x, plate_center_y],
            "ink_bbox_screen": ink_bbox_screen,
            "props": props_obj,
            "typo_kinetic_meta": typo_meta_obj,
            "craft_clip": craft_clip_obj,
        }

        planned_beats.append(
            {
                "beat_index": idx,
                "at": clip_at_s,
                "dur": dur_s,
                "template": tpl_id,
                "layout_silhouette": sil,
                "entrance_style": ent_style,
                "tier_bucket": tpl_meta["tier_bucket"],
                "kicker": kicker_clean,
                "main_text": main_clean,
                "accent_text": accent_clean,
                "has_pill_badge": has_pill_badge,
                "badge_text": badge_final,
                "base_hex": base_hex,
                "accent_hex": accent_hex,
                "polarity": polarity,
                "rail": rail_label,
                "pos": [pos_x, plate_center_y],
                "ink_bbox_screen": ink_bbox_screen,
                "cranial_lock_verified": bool(rail_res["cranial_lock_verified"]),
                "kicker_at_s": kicker_at_s if kicker_clean else None,
                "main_at_s": main_at_s,
                "accent_at_s": accent_at_s if accent_clean else None,
                "slash_at_s": slash_at_s,
                "kicker_abs_onset_s": kicker_abs_s,
                "main_abs_onset_s": main_abs_s,
                "accent_abs_onset_s": accent_abs_s,
                "word_triggers": word_triggers,
                "swap_words": swap_words_aligned,
                "out": out_mov_path,
            }
        )
        batch_jobs.append(job_obj)
        craft_clips.append(craft_clip_obj)

    sil_dist: dict[str, int] = {}
    bkt_dist: dict[str, int] = {}
    for pb in planned_beats:
        s_k = pb["layout_silhouette"]
        b_k = pb["tier_bucket"]
        sil_dist[s_k] = sil_dist.get(s_k, 0) + 1
        bkt_dist[b_k] = bkt_dist.get(b_k, 0) + 1

    max_sil_cnt = max(sil_dist.values()) if sil_dist else 0
    return {
        "version": "7.1",
        "format_mode": fmt_code,
        "industry_skin": skin_code,
        "color_policy": pol_mode,
        "fps": fps_i,
        "stats": {
            "total_beats": n,
            "distinct_silhouettes": len(sil_dist),
            "silhouette_distribution": sil_dist,
            "bucket_distribution": bkt_dist,
            "max_silhouette_share": round(max_sil_cnt / float(n), 4),
            "pill_badge_count": pills_allocated,
            "pill_badge_ratio": round(pills_allocated / float(n), 4),
            "unique_pill_badges": sorted(seen_badge_keys),
            "fabricated_kickers_blocked": fabricated_kickers_blocked,
            "max_syllable_onset_drift_frames": round(max_onset_drift_f, 3),
            "cranial_lock_100pct": all(bool(pb["cranial_lock_verified"]) for pb in planned_beats),
        },
        "beats": planned_beats,
        "batch_jobs": batch_jobs,
        "craft_clips": craft_clips,
    }


# ---------------------------------------------------------------------------
# CLI Inspection Helper (`typography_composer.py --list`)
# ---------------------------------------------------------------------------

CATALOG = {
    "version": "7.1",
    "kinetic_12_catalog": KINETIC_12_CATALOG,
    "semantic_4act_jewel_palettes": SEMANTIC_4ACT_JEWEL_PALETTES,
    "dviet_color_worlds": DVIET_COLOR_WORLDS,
    "semantic_multi_hue_palette": {
        k: {"hex": str(v), "rgb": list(v.rgb), "roles": list(v.roles), "desc": v.desc}
        for k, v in SEMANTIC_MULTI_HUE_PALETTE.items()
    },
    "text_presets": [
        "player3_air_cushion_slide",
        "dviet_soft_up",
        "elastic_pop",
        "slide_down_reveal",
        "swing_3d_y",
        "flip_3d_x",
        "editorial_serif_italic",
        "script_brush_accent",
        "minimal_giant_word",
        "side_left_callout",
        "dual_hero_pair",
        "dviet_kiss_hero_pair",
        "dviet_wall_microword_pop",
        "dviet_two_point_wall_hop",
        "conversational_captions_2line",
        "minimal_single_line_captions",
        "hook_drop_handoff",
        "inline_dual_hue_row",
        "s01_accordion_rollout_sub",
        "s02_boundary_pinch_sub",
        "s03_stepup_underline_sub",
        "s04_baseline_rise_lead",
        "s05_feather_wipe_lead",
        "s06_swivel_3d_sub",
        "s07_ghost_recede_stack",
        "s08_poetic_scatter_lead",
        "s09_overlap_script_sub",
        "s10_word_synced_fixed_slot_captions",
        "s11_conversational_2line",
        "s12_minimal_1line_quiet",
        "s14_shoulder_callout",
        "s15_tilted_counter_cluster",
        "s16_bridge_anchor_swap",
        "s17_circular_arc_sub_wrap",
        "s18_typewriter_tech_tag",
        "s18_active_dim_step_pills",
    ],
    "secondary_4group_styles": SECONDARY_4GROUP_STYLES,
    "aroll_camera_modes": [
        "in_hold",
        "velvet_settle_then_in",
        "pain_emphasis_in",
        "zoom_out_breath",
        "breath_still_drift",
    ],
    "aroll_camera_framings": [
        "center",
        "left_third",
        "right_third",
        "closeup_high",
    ],
    "broll_camera_modes": [
        "push_in",
        "pull_out",
        "pan_left",
        "pan_right",
        "macro_crop",
    ],
    "snap_subcut_modes": [
        "sync",
        "vocal_jcut",
    ],
    "utilities": [
        "plan_dviet_kinetic_beat_schedule",
        "compose_text",
        "player3_air_cushion_bezier",
        "build_player3_air_cushion_keyframes",
        "resolve_4act_jewel_palette",
        "resolve_dual_rail_safe_y",
        "apply_persistent_text_bridge",
        "plan_color_world_for_video",
        "export_dviet_bevel_lockup_png",
        "dviet_wall_microword_pop",
        "dviet_two_point_wall_hop",
        "dviet_kiss_hero_pair",
        "inline_dual_hue_row",
        "plan_semantic_hue_sequence",
        "plan_4group_secondary_rotation",
        "parse_inline_color_spans",
        "strip_inline_color_tags",
        "resolve_semantic_color",
        "compute_hero_safe_y",
        "hero_skip_window",
        "snap_subcut",
        "clean_display_text",
        "load_text_vi",
        "is_glued_pair",
        "can_split_after",
        "split_phrase_2line",
        "measure_text_ink_width",
        "fit_font_size",
    ],
}


def _run_self_tests_v71() -> int:
    """
    `v7.1` Syllable-Locked `@__dviet` Kinetic Choreography Planner Self-Test:
      - Tests `KINETIC_12_CATALOG` (`kt01..kt12` & all 12 `SIL_*` silhouettes)
      - Loads real `transcript_ms.json` `words_nfc` (with portable embedded fallback)
      - Verifies Law 1 (`0` fabricated `— ALL CAPS` kickers), Law 2 (`<=20%` single-use pill badges, `0` on `F6`/`S7`),
        Law 3 (`0` consecutive silhouette/entrance repeats, `<=30%` max silhouette share, `>=5` silhouettes),
        Law 4 (`±2f` syllable-onset lock with `0` premature spoilers), Law 5 (`100%` Cranial Lock),
        and `export_dviet_bevel_lockup_png` static hero PNG veto!
    """
    import tempfile

    # 1. Verify all 12 templates & silhouettes exist
    expected_sils = {
        "kt01_kiss_editorial_2line": "SIL_KISS_2L",
        "kt02_feather_swash_overlap": "SIL_FEATHER_SWASH",
        "kt03_per_word_nonlinear_bloom": "SIL_WORD_STAGGER",
        "kt04_ghost_to_focus_stack": "SIL_GHOST_STACK",
        "kt05_wall_spatial_counterpoint": "SIL_WALL_HOP",
        "kt06_bridge_anchor_live_swap": "SIL_BRIDGE_SWAP",
        "kt07_telescoping_char_rollout": "SIL_CHAR_ACCORDION",
        "kt08_mist_evaporation_reveal": "SIL_MIST_GRADIENT",
        "kt09_strike_myth_laser_2phase": "SIL_MYTH_STRIKE",
        "kt10_cursor_bars_pillar_gate": "SIL_CURSOR_HUD",
        "kt11_cranial_svg_arc_or_tilt": "SIL_TILT_OR_ARC",
        "kt12_whisper_or_directional_echo": "SIL_WHISPER_ECHO",
    }
    assert set(KINETIC_12_CATALOG.keys()) == set(expected_sils.keys())
    for kt_k, sil_v in expected_sils.items():
        assert KINETIC_12_CATALOG[kt_k]["layout_silhouette"] == sil_v

    # 2. Load optional `TRANSCRIPT_MS_JSON` env override if available (or exact `words_nfc` excerpt)
    real_tms_path = Path(os.environ.get("TRANSCRIPT_MS_JSON", "")) if os.environ.get("TRANSCRIPT_MS_JSON") else Path("_nonexistent_tms.json")
    if real_tms_path.is_file():
        tms_doc: Any = json.loads(real_tms_path.read_text(encoding="utf-8"))
        tms_source_label = str(real_tms_path)
    else:
        tms_source_label = "embedded_transcript_ms_words_nfc"
        tms_doc = {
            "fps": 30,
            "words_nfc": [
                {"word": "Ở", "start_ms": 0, "end_ms": 80},
                {"word": "phía", "start_ms": 80, "end_ms": 260},
                {"word": "trên", "start_ms": 260, "end_ms": 450},
                {"word": "là", "start_ms": 450, "end_ms": 600},
                {"word": "video", "start_ms": 600, "end_ms": 960},
                {"word": "sản", "start_ms": 960, "end_ms": 1220},
                {"word": "phẩm", "start_ms": 1220, "end_ms": 1580},
                {"word": "Và", "start_ms": 5813, "end_ms": 5980},
                {"word": "mình", "start_ms": 5980, "end_ms": 6210},
                {"word": "là", "start_ms": 6210, "end_ms": 6380},
                {"word": "Thành", "start_ms": 6380, "end_ms": 6820},
                {"word": "tại", "start_ms": 7400, "end_ms": 7620},
                {"word": "OverPower", "start_ms": 7620, "end_ms": 8250},
                {"word": "Agency", "start_ms": 8250, "end_ms": 8800},
                {"word": "sử", "start_ms": 9400, "end_ms": 9620},
                {"word": "dụng", "start_ms": 9620, "end_ms": 9900},
                {"word": "AI", "start_ms": 9900, "end_ms": 10300},
                {"word": "mắc", "start_ms": 11120, "end_ms": 11400},
                {"word": "bệnh", "start_ms": 11680, "end_ms": 12050},
                {"word": "giả", "start_ms": 12200, "end_ms": 12550},
                {"word": "trân", "start_ms": 12550, "end_ms": 12980},
                {"word": "bóng", "start_ms": 13400, "end_ms": 13720},
                {"word": "bẩy", "start_ms": 13720, "end_ms": 14050},
                {"word": "nhựa", "start_ms": 14120, "end_ms": 14520},
                {"word": "không", "start_ms": 14540, "end_ms": 14720},
                {"word": "thật", "start_ms": 14720, "end_ms": 14950},
                {"word": "3", "start_ms": 18200, "end_ms": 18480},
                {"word": "bước", "start_ms": 18480, "end_ms": 18850},
                {"word": "khóa", "start_ms": 19300, "end_ms": 19650},
                {"word": "ảnh", "start_ms": 19650, "end_ms": 19980},
                {"word": "Bước", "start_ms": 21820, "end_ms": 22120},
                {"word": "1", "start_ms": 22120, "end_ms": 22400},
                {"word": "kết", "start_ms": 22900, "end_ms": 23200},
                {"word": "cấu", "start_ms": 23200, "end_ms": 23580},
                {"word": "không", "start_ms": 24400, "end_ms": 24680},
                {"word": "biến", "start_ms": 24680, "end_ms": 24980},
                {"word": "dạng", "start_ms": 24980, "end_ms": 25350},
                {"word": "Bước", "start_ms": 25820, "end_ms": 26100},
                {"word": "2", "start_ms": 26100, "end_ms": 26380},
                {"word": "ánh", "start_ms": 26650, "end_ms": 26920},
                {"word": "sáng", "start_ms": 26920, "end_ms": 27280},
                {"word": "studio", "start_ms": 27280, "end_ms": 27750},
                {"word": "đổ", "start_ms": 28150, "end_ms": 28420},
                {"word": "bóng", "start_ms": 28420, "end_ms": 28820},
                {"word": "chân", "start_ms": 28820, "end_ms": 29120},
                {"word": "thật", "start_ms": 29120, "end_ms": 29500},
                {"word": "chuyển", "start_ms": 31200, "end_ms": 31560},
                {"word": "động", "start_ms": 31560, "end_ms": 31900},
                {"word": "camera", "start_ms": 31900, "end_ms": 32450},
                {"word": "điện", "start_ms": 33100, "end_ms": 33450},
                {"word": "ảnh", "start_ms": 33450, "end_ms": 33900},
                {"word": "mẫu", "start_ms": 35100, "end_ms": 35420},
                {"word": "câu", "start_ms": 35420, "end_ms": 35720},
                {"word": "prompt", "start_ms": 35720, "end_ms": 36280},
                {"word": "bình", "start_ms": 37600, "end_ms": 37900},
                {"word": "luận", "start_ms": 37900, "end_ms": 38280},
                {"word": "prompt", "start_ms": 38900, "end_ms": 39480},
            ],
        }

    # Intentionally include V17 anti-patterns in raw input beats to verify the planner sanitizes ALL of them!
    raw_test_beats = [
        {"kicker": "— HOOK MỞ ĐẦU • AI STUDIO", "main_text": "video sản phẩm", "badge_text": "AI LOCK", "role": "hook"},
        {"kicker": "— GIỚI THIỆU NHÂN HIỆU", "main_text": "mình là Thành", "accent_text": "OverPower Agency", "badge_text": "AI LOCK", "role": "quiet"},
        {"kicker": "— CẢNH BÁO SAI LẦM", "main_text": "sử dụng AI", "badge_text": "STEP 01", "role": "wall", "cam_mode": "left_third"},
        {"kicker": "mắc bệnh", "main_text": "giả trân", "accent_text": "nhựa không thật", "is_pain": True, "badge_text": "MYTH"},
        {"kicker": "— QUY TRÌNH CỐT LÕI", "main_text": "3 bước", "accent_text": "khóa ảnh", "badge_text": "3 STEPS", "role": "step"},
        {"kicker": "Bước 1", "main_text": "kết cấu", "accent_text": "không biến dạng", "badge_text": "LOCK 01", "role": "solution"},
        {"main_text": "ánh sáng studio", "badge_text": "CRI 100", "role": "quiet"},
        {"main_text": "đổ bóng", "accent_text": "chân thật", "has_arc": True, "badge_text": "SHADOW"},
        {"main_text": "chuyển động camera", "accent_text": "điện ảnh", "swap_words": ["camera", "điện ảnh"], "role": "swap"},
        {"main_text": "mẫu câu prompt", "badge_text": "PROMPT", "role": "tech"},
        {"main_text": "bình luận", "accent_text": "prompt", "role": "cta"},
    ]

    plan = plan_dviet_kinetic_beat_schedule(
        raw_test_beats,
        tms_doc,
        format_mode="F1",
        industry_skin="S6",
        color_policy="semantic_4act_jewel",
        cranial_zone={"hair_top_y": 862.0, "chin_y": 1365.0},
        fps=60,
    )
    st = plan["stats"]
    p_beats = plan["beats"]

    # Law 1: Zero `— ALL CAPS` kicker spam
    assert st["fabricated_kickers_blocked"] >= 4
    for pb in p_beats:
        assert not _is_fabricated_all_caps_kicker(pb["kicker"]), f"Fabricated kicker leaked: {pb['kicker']!r}"

    # Law 2: Pill badges <= 20% of beats, <= 3 unique, 0 duplicates
    assert st["pill_badge_ratio"] <= 0.20 + 1e-9, f"Pill ratio > 20%: {st}"
    assert st["pill_badge_count"] <= 3
    badges_used = [pb["badge_text"].casefold() for pb in p_beats if pb["has_pill_badge"]]
    assert len(badges_used) == len(set(badges_used)), f"Duplicate pill badges: {badges_used}"

    # Also verify 0 pills on F6 / S7
    plan_vlog = plan_dviet_kinetic_beat_schedule(raw_test_beats, tms_doc, format_mode="F6", industry_skin="S7", fps=60)
    assert plan_vlog["stats"]["pill_badge_count"] == 0, "F6/S7 must enforce 0 pill badges!"

    # Law 3: 0 consecutive silhouette/entrance repeats, <= 30% max single silhouette, >= 5 distinct silhouettes
    for a_b, b_b in zip(p_beats, p_beats[1:]):
        assert a_b["layout_silhouette"] != b_b["layout_silhouette"], f"Consecutive silhouette repeat: {a_b['layout_silhouette']}"
        assert a_b["entrance_style"] != b_b["entrance_style"], f"Consecutive entrance repeat: {a_b['entrance_style']}"
    assert st["max_silhouette_share"] <= 0.30 + 1e-9, f"Max silhouette share > 30%: {st['max_silhouette_share']}"
    assert st["distinct_silhouettes"] >= 5, f"Expected >= 5 distinct silhouettes, got {st['distinct_silhouettes']}"

    # Law 4: Exact syllable-onset alignment (`±2 frames`, `0` premature spoilers!)
    assert st["max_syllable_onset_drift_frames"] <= 2.0, f"Syllable drift > 2 frames: {st['max_syllable_onset_drift_frames']}"
    # Specifically verify multi-clause beat 3 ("mắc bệnh" -> "giả trân" -> "nhựa không thật") does NOT fire accent at t=0!
    b_myth = p_beats[3]
    assert b_myth["accent_at_s"] is not None and b_myth["accent_at_s"] > b_myth["main_at_s"] + 0.3, (
        f"Premature spoiler on multi-clause beat: {b_myth}"
    )

    # Law 5: 100% Cranial Lock clearance against [862 - 48 = 814, 1365 + 32 = 1397]
    assert st["cranial_lock_100pct"] is True
    for job in plan["batch_jobs"]:
        assert job["mode"] == "mov" and job["out"].endswith(".mov")
        iy0, iy1 = job["ink_bbox_screen"][1], job["ink_bbox_screen"][3]
        assert iy1 <= (862.0 - 48.0) + 0.5 or iy0 >= (1365.0 + 32.0) - 0.5, f"Cranial violation in job: {job['ink_bbox_screen']}"

    # Guard on `export_dviet_bevel_lockup_png`
    with tempfile.TemporaryDirectory(prefix="typo-v71-") as td:
        p_png = Path(td) / "hero_stamp.png"
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            try:
                export_dviet_bevel_lockup_png(p_png, "video sản phẩm")
                raise AssertionError("Expected RuntimeError veto when allow_static_thumbnail=False!")
            except RuntimeError as exc:
                assert "STATIC_HERO_PNG_STAMP" in str(exc)
        thumb_res = export_dviet_bevel_lockup_png(p_png, "video sản phẩm", allow_static_thumbnail=True)
        assert Path(thumb_res["path"]).is_file()

    print(
        f"[OK] v7.1 plan_dviet_kinetic_beat_schedule ({tms_source_label}): "
        f"beats={st['total_beats']}, distinct_sil={st['distinct_silhouettes']}, "
        f"max_sil_share={st['max_silhouette_share']*100:.1f}% (<=30%), "
        f"pills={st['pill_badge_count']} ({st['pill_badge_ratio']*100:.1f}% <=20%), "
        f"blocked_caps_kickers={st['fabricated_kickers_blocked']}, "
        f"max_onset_drift={st['max_syllable_onset_drift_frames']:.2f}f (<=2f), cranial_lock=100%"
    )
    return 0


def _run_self_tests() -> int:
    # 1. Player 3 Air-Cushion Bezier (Video #08, f_01176..f_01195)
    y_0 = player3_air_cushion_bezier(0.0)
    y_2f = player3_air_cushion_bezier(2.0 / 19.0)
    y_mid = player3_air_cushion_bezier(9.0 / 19.0)
    y_1 = player3_air_cushion_bezier(1.0)
    assert y_0 == 0.0 and y_1 == 1.0
    assert y_2f > 0.50, f"Player 3 must travel >50% in first 2 frames, got {y_2f:.3f}"
    tail_10f_px_per_f = (1.0 - y_mid) * 140.0 / 10.0
    assert tail_10f_px_per_f < 1.0, f"Final 10f air-cushion must stay <1px/f, got {tail_10f_px_per_f:.3f}"
    print(f"[OK] player3_air_cushion_bezier: 2f={y_2f*100:.1f}% (>50%), tail_10f={tail_10f_px_per_f:.3f}px/f (<1px/f)")

    # 2. SEMANTIC_4ACT_JEWEL_PALETTES
    for req_key in (
        "act1_amber_gold",
        "act2_crimson_coral",
        "act3a_emerald_mint",
        "act3b_optical_ice_cyan",
        "dental_porcelain_ice",
        "nail_blush_champagne",
        "skincare_pearl_rose",
    ):
        pal = resolve_4act_jewel_palette(req_key)
        assert pal["base_hex"] == "#FAFAFA" and HEX6_RE.match(pal["accent_hex"])
    assert SEMANTIC_4ACT_JEWEL_PALETTES["act1_amber_gold"]["accent_hex"] == "#F5C451"
    assert SEMANTIC_4ACT_JEWEL_PALETTES["act2_crimson_coral"]["accent_hex"] == "#FF4D5E"
    assert SEMANTIC_4ACT_JEWEL_PALETTES["act3a_emerald_mint"]["accent_hex"] == "#34D399"
    assert SEMANTIC_4ACT_JEWEL_PALETTES["act3b_optical_ice_cyan"]["accent_hex"] == "#7DD3FC"
    print("[OK] SEMANTIC_4ACT_JEWEL_PALETTES: all 7 4-Act & CRI-100 industry jewel palettes verified")

    # 3. Dual-Rail Safe-Y & Hard Cranial Lock + Enamel/Macro BBox Exclusion
    r_up = resolve_dual_rail_safe_y(hair_top_y=620.0, chin_y=1060.0, text_size=76.0)
    assert r_up["rail"] == "upper_editorial_stage" and r_up["cranial_lock_verified"] is True
    assert r_up["ink_y_span"][1] <= (620.0 - 48.0)

    r_chest = resolve_dual_rail_safe_y(hair_top_y=290.0, chin_y=760.0, text_size=76.0)
    assert r_chest["rail"] == "chest_tactile_rail" and r_chest["cranial_lock_verified"] is True
    assert r_chest["ink_y_span"][0] >= (760.0 + 32.0)

    r_dental = resolve_dual_rail_safe_y(
        is_broll=True,
        enamel_gum_bbox=(180.0, 1180.0, 900.0, 1620.0),
        preferred_rail="chest",
        text_size=74.0,
    )
    assert r_dental["rail"] == "upper_editorial_stage" and r_dental["macro_exclusion_verified"] is True
    print(
        f"[OK] resolve_dual_rail_safe_y: upper={r_up['y']}px, chest={r_chest['y']}px, "
        f"dental_enamel_reroute={r_dental['rail']} ({r_dental['y']}px)"
    )

    # 4. Persistent Text Bridge (Video #01, #06, #10, #16)
    base_clip = player3_air_cushion_slide("cầu chữ mượt", at=2.36, dur=0.5, fps=60)
    bridged = apply_persistent_text_bridge(base_clip, next_cut_s=2.40, lead_frames=4, hold_across_frames=10, fps=60)
    assert bridged["persistent_bridge"] is True
    assert bridged["at"] <= round(2.40 - 4 / 60, 6) + 1e-6
    assert abs((bridged["at"] + bridged["dur"]) - round(2.40 + 10 / 60, 6)) < 1e-5
    print(f"[OK] apply_persistent_text_bridge: at={bridged['at']:.4f}s -> end={bridged['at']+bridged['dur']:.4f}s across cut=2.40s")

    # 5. Hard Veto against plastic PIL 3D bevel `render_dviet_3d_extruded_bevel_word`
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            render_dviet_3d_extruded_bevel_word("nhựa cũ")
            raise AssertionError("Expected RuntimeError veto on render_dviet_3d_extruded_bevel_word!")
        except RuntimeError as exc:
            assert "web_plate_builder.py" in str(exc)
        assert len(caught) >= 1
    print("[OK] Legacy PIL 3D Bevel Veto: blocked `render_dviet_3d_extruded_bevel_word` -> web_plate_builder.py")
    return _run_self_tests_v71()


def _cli(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Universal Studio Director v7.9.0 — Syllable-Locked @__dviet Kinetic Beat Planner, Dual-Rail Cranial Lock & 4-Act Jewel Toolkit"
    )
    ap.add_argument("--list", dest="flag_list", action="store_true", help="Print JSON catalog of all v7.1 kinetic templates, palettes, presets, and camera/J-cut modes")
    ap.add_argument("--self-test", action="store_true", help="Run built-in v7.0 + v7.1 typography physics & Cranial Lock self-tests")
    ap.add_argument("--self-test-v71", action="store_true", help="Run v7.1 syllable-locked kinetic beat choreography & empirical law self-tests")
    ap.add_argument("cmd", nargs="?", choices=["list"], help="Optional subcommand (`list`) for backward compatibility")
    args = ap.parse_args(argv)
    if args.self_test_v71:
        return _run_self_tests_v71()
    if args.self_test:
        return _run_self_tests()
    if args.flag_list or args.cmd == "list":
        print(json.dumps(CATALOG, ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
