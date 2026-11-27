#!/usr/bin/env python3
"""
DVIET Full-Screen Living Motion-Design Canvases & Polarity Flip Stage Engine (v6.0 design, packaged as v7.9.1)
=============================================================================================================
Replaces static flat PNG boxes and system emojis with 100% full-screen tactile, living
Motion-Design Canvases inspired by `@__dviet` (`7707653827016674580`, `7688934517783989524`,
`7693026626333871381`):

  - Dual Polarity Modes (`"dark"` luma ~8-12% Aurora/Obsidian Silk <-> `"light"` `#EEF4EA`/`#F7F5EE`
    luma ~88-94% Warm Mint-Cream / Archival Paper with CAD hairlines & organic grain).
  - 4 Color-World Themes:
      * `"emerald_cream_7707"` (`#071D15` + `#1B4D35` <-> `#EEF4EA` + `#14532D`)
      * `"amber_cinema_7706"`  (`#0C0B09` + `#3B230E` <-> `#F7F5EE` + `#1C1917`)
      * `"violet_aurora_7693"` (`#0B0914` + `#2B194D` <-> `#F4F3F8` + `#1E1B4B`)
      * `"obsidian_cyan_7688"` (`#0C0D12` + `#13293D` <-> `#EEF4EA` + `#111827`)
  - Giant `6%–9%` Opacity Blurred Kinetic Watermark (`180–280px` lowercase geometric sans,
    `GaussianBlur 10px`, drifting `-18px` horizontally across the shot).
  - 4 Bespoke Animated Full-Screen Stage Generators (`<150MB` RAM streaming float32/uint8):
      1. `render_timeline_playhead_stage(...)`   (3D glass timeline + waveform + live playhead + optional `1x->24x` X/iris polarity flip)
      2. `render_concentric_lock_lab_stage(...)` (Cream Match-Cut Lab: gliding specimen plates locking concentrically at `(540, 920)` + `anchor_shape_xyr`)
      3. `render_giant_numeral_3d_ui_stage(...)` (Wavy 3D obsidian silk + giant `210px` numeral + `rotY=-11°, rotX=+5°` typing prompt window + edge DoF)
      4. `render_bento_kinetic_matrix_stage(...)`(Curved/perspective 3D frosted tile matrix with sequential `100%` active vs `32%` depth glow)
"""
from __future__ import annotations

import os
import sys

# Seamless virtualenv bootstrap when invoked via bare `python3` on hosts where CV/NumPy live in `~/.venvs/video-skills`
if __name__ == "__main__":
    try:
        import cv2 as _cv2_probe  # noqa: F401
        import numpy as _np_probe  # noqa: F401
        from PIL import Image as _pil_probe  # noqa: F401
    except ImportError:
        _venv_py = os.path.expanduser(os.environ.get("PFD_VENV_PYTHON") or "~/.venvs/video-skills/bin/python3")  # env override first
        if os.path.isfile(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
            os.execv(_venv_py, [_venv_py, *sys.argv])

import argparse
from functools import lru_cache
import gc
import importlib.util
import json
import math
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tracemalloc
from typing import Any, Iterator, Sequence
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

cv2.setNumThreads(2)

DEFAULT_W = 1080
DEFAULT_H = 1920
DEFAULT_FPS = 60

TOOLS_DIR = Path(__file__).resolve().parent / "tools"
FFMPEG_TIMEOUT_S = 300.0  # one-frame extraction / short encodes; never hangs forever

# v7.9.1: optional extra dirs; `$PFD_FONT_DIR` is searched first and fontconfig (fc-list) last (web_plate_builder.find_font_file)
FONT_DIRS = [
    Path.home() / ".local/share/fonts/tnedit",
    Path.home() / ".local/share/fonts/Montserrat_Static",
    Path.home() / ".local/share/fonts/motion-fx",
    Path.home() / ".local/share/fonts/opa_fonts",
    Path.home() / ".local/share/fonts/apple-sf-mono",
    Path.home() / ".local/share/fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/noto"),
]

FONT_CANDIDATES: dict[str, list[str]] = {
    "be_black": ["BeVietnamPro-Black.ttf", "BeVietnamPro-ExtraBold.ttf", "Montserrat-Black.otf", "DejaVuSans-Bold.ttf"],
    "be_extrabold": ["BeVietnamPro-ExtraBold.ttf", "BeVietnamPro-Bold.ttf", "Montserrat-ExtraBold.ttf", "DejaVuSans-Bold.ttf"],
    "be_bold": ["BeVietnamPro-Bold.ttf", "Montserrat-Bold.otf", "DejaVuSans-Bold.ttf"],
    "be_italic": ["BeVietnamPro-BoldItalic.ttf", "Montserrat-ExtraBoldItalic.ttf", "BeVietnamPro-Italic.ttf", "DejaVuSans.ttf"],
    "be_regular": ["Montserrat-Medium.ttf", "BeVietnamPro-Light.ttf", "DejaVuSans.ttf"],
    "mont_black": ["Montserrat-Black.otf", "BeVietnamPro-Black.ttf", "DejaVuSans-Bold.ttf"],
    "mont_bold": ["Montserrat-ExtraBold.ttf", "BeVietnamPro-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "playfair_italic": ["PlayfairDisplay-BoldItalic.ttf", "PlayfairDisplay-Italic[wght].ttf", "BeVietnamPro-BoldItalic.ttf"],
    "mono_bold": ["LigaSFMonoNerdFont-Bold.otf", "JetBrainsMono.ttf", "DejaVuSansMono-Bold.ttf"],
    "mono_medium": ["LigaSFMonoNerdFont-Medium.otf", "JetBrainsMono.ttf", "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"],
}

# Strip raw Unicode color system emojis so Noto/Twemoji color bitmaps never leak into motion design
_RAW_COLOR_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE0E-\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def nfc_clean(text: Any) -> str:
    """Normalize Vietnamese Unicode to NFC and strip raw color system emojis."""
    s = unicodedata.normalize("NFC", str(text or ""))
    s = _RAW_COLOR_EMOJI_RE.sub("", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def _hex_rgb(hx: str) -> tuple[int, int, int]:
    h = hx.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# =============================================================================
# Color-World Themes & Polarity Palettes (`dark` luma 8-12% <-> `light` 88-94%)
# =============================================================================

COLOR_WORLD_THEMES: dict[str, dict[str, dict[str, Any]]] = {
    "emerald_cream_7707": {
        "dark": {
            "bg_base": _hex_rgb("#071D15"),
            "node_a": _hex_rgb("#16422E"),
            "node_b": _hex_rgb("#0D3326"),
            "silk_ridge": _hex_rgb("#1B4D35"),
            "fg_hero": _hex_rgb("#F4F8F5"),
            "fg_lead": _hex_rgb("#9CC3B0"),
            "fg_muted": _hex_rgb("#6A9280"),
            "accent": _hex_rgb("#34D399"),
            "accent_2": _hex_rgb("#FACC15"),
            "accent_3": _hex_rgb("#38BDF8"),
            "card_bg": _hex_rgb("#0B241B"),
            "card_bg_2": _hex_rgb("#071912"),
            "card_border": _hex_rgb("#2DD4BF"),
            "hairline": _hex_rgb("#5EEAD4"),
            "watermark": _hex_rgb("#A7F3D0"),
        },
        "light": {
            "bg_base": _hex_rgb("#EEF4EA"),
            "bg_edge": _hex_rgb("#DFEBDD"),
            "node_a": _hex_rgb("#F6FAF3"),
            "node_b": _hex_rgb("#E3EFE0"),
            "fg_hero": _hex_rgb("#14532D"),
            "fg_lead": _hex_rgb("#264E36"),
            "fg_muted": _hex_rgb("#4B6B58"),
            "accent": _hex_rgb("#0F766E"),
            "accent_2": _hex_rgb("#15803D"),
            "accent_3": _hex_rgb("#B45309"),
            "card_bg": _hex_rgb("#FAFDF8"),
            "card_bg_2": _hex_rgb("#F1F7EE"),
            "card_border": _hex_rgb("#14532D"),
            "hairline": _hex_rgb("#14532D"),
            "watermark": _hex_rgb("#14532D"),
        },
    },
    "amber_cinema_7706": {
        "dark": {
            "bg_base": _hex_rgb("#0C0A08"),
            "node_a": _hex_rgb("#38210D"),
            "node_b": _hex_rgb("#241509"),
            "silk_ridge": _hex_rgb("#422810"),
            "fg_hero": _hex_rgb("#FAF7F0"),
            "fg_lead": _hex_rgb("#D6C3A8"),
            "fg_muted": _hex_rgb("#96826A"),
            "accent": _hex_rgb("#F59E0B"),
            "accent_2": _hex_rgb("#FDE047"),
            "accent_3": _hex_rgb("#FB923C"),
            "card_bg": _hex_rgb("#1A140F"),
            "card_bg_2": _hex_rgb("#110D0A"),
            "card_border": _hex_rgb("#F59E0B"),
            "hairline": _hex_rgb("#FBBF24"),
            "watermark": _hex_rgb("#FDE68A"),
        },
        "light": {
            "bg_base": _hex_rgb("#F7F5EE"),
            "bg_edge": _hex_rgb("#EAE4D5"),
            "node_a": _hex_rgb("#FCFBF7"),
            "node_b": _hex_rgb("#EDE7D8"),
            "fg_hero": _hex_rgb("#1C1917"),
            "fg_lead": _hex_rgb("#443C34"),
            "fg_muted": _hex_rgb("#6B5E51"),
            "accent": _hex_rgb("#B45309"),
            "accent_2": _hex_rgb("#92400E"),
            "accent_3": _hex_rgb("#0F766E"),
            "card_bg": _hex_rgb("#FFFEFA"),
            "card_bg_2": _hex_rgb("#F5F1E6"),
            "card_border": _hex_rgb("#292524"),
            "hairline": _hex_rgb("#292524"),
            "watermark": _hex_rgb("#292524"),
        },
    },
    "violet_aurora_7693": {
        "dark": {
            "bg_base": _hex_rgb("#0B0914"),
            "node_a": _hex_rgb("#2C1A4D"),
            "node_b": _hex_rgb("#171E3F"),
            "silk_ridge": _hex_rgb("#35205C"),
            "fg_hero": _hex_rgb("#F6F4FF"),
            "fg_lead": _hex_rgb("#C4B5FD"),
            "fg_muted": _hex_rgb("#8B7EB8"),
            "accent": _hex_rgb("#C084FC"),
            "accent_2": _hex_rgb("#38BDF8"),
            "accent_3": _hex_rgb("#F472B6"),
            "card_bg": _hex_rgb("#161229"),
            "card_bg_2": _hex_rgb("#0E0B1C"),
            "card_border": _hex_rgb("#C084FC"),
            "hairline": _hex_rgb("#DDD6FE"),
            "watermark": _hex_rgb("#E9D5FF"),
        },
        "light": {
            "bg_base": _hex_rgb("#F5F4F8"),
            "bg_edge": _hex_rgb("#E7E4F0"),
            "node_a": _hex_rgb("#FAF9FC"),
            "node_b": _hex_rgb("#EAE7F3"),
            "fg_hero": _hex_rgb("#1E1B4B"),
            "fg_lead": _hex_rgb("#37306B"),
            "fg_muted": _hex_rgb("#5B548A"),
            "accent": _hex_rgb("#6D28D9"),
            "accent_2": _hex_rgb("#0284C7"),
            "accent_3": _hex_rgb("#14532D"),
            "card_bg": _hex_rgb("#FDFCFF"),
            "card_bg_2": _hex_rgb("#F2EFFA"),
            "card_border": _hex_rgb("#1E1B4B"),
            "hairline": _hex_rgb("#1E1B4B"),
            "watermark": _hex_rgb("#1E1B4B"),
        },
    },
    "obsidian_cyan_7688": {
        "dark": {
            "bg_base": _hex_rgb("#0C0D12"),
            "node_a": _hex_rgb("#132A3E"),
            "node_b": _hex_rgb("#182132"),
            "silk_ridge": _hex_rgb("#1E3852"),
            "fg_hero": _hex_rgb("#F8FAFC"),
            "fg_lead": _hex_rgb("#A5B8CC"),
            "fg_muted": _hex_rgb("#64788F"),
            "accent": _hex_rgb("#38BDF8"),
            "accent_2": _hex_rgb("#2DD4BF"),
            "accent_3": _hex_rgb("#FACC15"),
            "card_bg": _hex_rgb("#111722"),
            "card_bg_2": _hex_rgb("#0B0F17"),
            "card_border": _hex_rgb("#38BDF8"),
            "hairline": _hex_rgb("#7DD3FC"),
            "watermark": _hex_rgb("#BAE6FD"),
        },
        "light": {
            "bg_base": _hex_rgb("#EEF4EA"),
            "bg_edge": _hex_rgb("#DFE8DD"),
            "node_a": _hex_rgb("#F7FAF5"),
            "node_b": _hex_rgb("#E3ECE1"),
            "fg_hero": _hex_rgb("#111827"),
            "fg_lead": _hex_rgb("#273449"),
            "fg_muted": _hex_rgb("#52627A"),
            "accent": _hex_rgb("#0369A1"),
            "accent_2": _hex_rgb("#0F766E"),
            "accent_3": _hex_rgb("#14532D"),
            "card_bg": _hex_rgb("#FAFDF9"),
            "card_bg_2": _hex_rgb("#EFF5ED"),
            "card_border": _hex_rgb("#111827"),
            "hairline": _hex_rgb("#111827"),
            "watermark": _hex_rgb("#111827"),
        },
    },
}


def resolve_theme_palette(theme: str = "emerald_cream_7707", polarity: str = "dark") -> dict[str, Any]:
    t_key = str(theme or "emerald_cream_7707").strip().lower()
    if t_key not in COLOR_WORLD_THEMES:
        t_key = "emerald_cream_7707"
    p_key = "light" if str(polarity or "dark").strip().lower() == "light" else "dark"
    pal = dict(COLOR_WORLD_THEMES[t_key][p_key])
    pal["theme"] = t_key
    pal["polarity"] = p_key
    return pal


# =============================================================================
# Font & Easing Utilities
# =============================================================================

def _wpb() -> Any:
    """scripts/tools/web_plate_builder.py (lazy): the shared font search and metadata strip helpers."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    import web_plate_builder as mod

    return mod


@lru_cache(maxsize=64)
def _resolve_font_path(role: str) -> str:
    candidates = FONT_CANDIDATES.get(role, FONT_CANDIDATES["be_bold"])
    wpb = _wpb()
    for fname in candidates:
        for fdir in (*wpb.env_font_dirs(), *FONT_DIRS):
            cand = fdir / fname
            if cand.is_file():
                return str(cand)
    for fname in candidates:  # v7.9.1: fontconfig knows the file under another folder
        hit = wpb.find_font_file(fname)
        if hit is not None:
            return str(hit)
    raise FileNotFoundError(f"Could not locate font for role={role!r} (tried {candidates} in $PFD_FONT_DIR, "
                            f"{[str(d) for d in FONT_DIRS]} and fontconfig); install it or set PFD_FONT_DIR")


@lru_cache(maxsize=256)
def load_font(role: str, pt_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_resolve_font_path(role), max(8, int(round(pt_size))))


_MEASURE_IMG = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMG)


def text_metrics(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, tuple[int, int, int, int]]:
    s = nfc_clean(text)
    if not s:
        return 0, 0, (0, 0, 0, 0)
    bb = _MEASURE_DRAW.textbbox((0, 0), s, font=font)
    return bb[2] - bb[0], bb[3] - bb[1], bb


def fit_font(text: str, role: str, max_w: int, start_px: int, min_px: int = 18) -> ImageFont.FreeTypeFont:
    sz = int(start_px)
    while sz > min_px:
        f = load_font(role, sz)
        if text_metrics(text, f)[0] <= max_w:
            return f
        sz -= 2
    return load_font(role, min_px)


def cubic_bezier(u: float, x1: float = 0.14, y1: float = 0.90, x2: float = 0.20, y2: float = 1.00) -> float:
    """Safeguarded Newton-Raphson cubic Bezier solver matching `@__dviet` 60fps easing."""
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    s = float(u)
    for _ in range(10):
        inv = 1.0 - s
        x = 3.0 * inv * inv * s * x1 + 3.0 * inv * s * s * x2 + s * s * s - u
        if abs(x) < 1e-9:
            break
        if x < 0.0:
            lo = s
        else:
            hi = s
        dx = 3.0 * inv * inv * x1 + 6.0 * inv * s * (x2 - x1) + 3.0 * s * s * (1.0 - x2)
        s = (s - x / dx) if (dx > 1e-8 and lo < (s - x / dx) < hi) else 0.5 * (lo + hi)
    inv = 1.0 - s
    return 3.0 * inv * inv * s * y1 + 3.0 * inv * s * s * y2 + s * s * s


def smooth_window(t: float, t0: float, t1: float) -> float:
    if t1 <= t0:
        return 1.0 if t >= t0 else 0.0
    return cubic_bezier(max(0.0, min(1.0, (t - t0) / (t1 - t0))))


def _rgba(rgb: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), max(0, min(255, int(alpha))))


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    x: float,
    cy: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    align_x: str = "left",
) -> tuple[int, int]:
    s = nfc_clean(text)
    if not s:
        return 0, 0
    w, h, bb = text_metrics(s, font)
    if align_x == "center":
        dx = x - bb[0] - w * 0.5
    elif align_x == "right":
        dx = x - bb[0] - w
    else:
        dx = x - bb[0]
    dy = cy - (bb[1] + bb[3]) * 0.5
    draw.text((dx, dy), s, font=font, fill=fill)
    return w, h


# =============================================================================
# Clean Vector Geometric Icons (Zero System Emojis!)
# =============================================================================

def draw_vector_glyph(
    draw: ImageDraw.ImageDraw,
    kind: str,
    cx: float,
    cy: float,
    r: float,
    rgb: tuple[int, int, int],
    alpha: int = 255,
    badge_bg_alpha: int = 0,
) -> None:
    """Anti-aliased geometric vector glyphs: `padlock`, `spark`, `aperture`, `arrow`, `check`, `reticle`."""
    col = _rgba(rgb, alpha)
    sw = max(2, int(round(r * 0.18)))
    if badge_bg_alpha > 0:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgba(rgb, badge_bg_alpha), outline=_rgba(rgb, min(255, alpha)), width=max(1, sw // 2))

    k = str(kind or "spark").lower()
    if k in ("lock", "padlock"):
        sh_w = r * 0.34
        draw.arc((cx - sh_w, cy - r * 0.58, cx + sh_w, cy + r * 0.04), start=180, end=0, fill=col, width=sw)
        draw.line([(cx - sh_w, cy - r * 0.27), (cx - sh_w, cy - r * 0.02)], fill=col, width=sw)
        draw.line([(cx + sh_w, cy - r * 0.27), (cx + sh_w, cy - r * 0.02)], fill=col, width=sw)
        draw.rounded_rectangle(
            (cx - r * 0.48, cy - r * 0.06, cx + r * 0.48, cy + r * 0.56),
            radius=max(2, int(r * 0.14)),
            outline=col,
            fill=_rgba(rgb, max(45, alpha // 3)),
            width=sw,
        )
        kr = max(1.5, r * 0.10)
        draw.ellipse((cx - kr, cy + r * 0.22 - kr, cx + kr, cy + r * 0.22 + kr), fill=col)
    elif k in ("aperture", "camera", "lens"):
        ro = r * 0.68
        ri = r * 0.30
        draw.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), outline=col, width=sw)
        for i in range(6):
            a0 = i * (math.pi / 3.0)
            a1 = a0 + 0.95
            p0 = (cx + math.cos(a0) * ri, cy + math.sin(a0) * ri)
            p1 = (cx + math.cos(a1) * ro * 0.94, cy + math.sin(a1) * ro * 0.94)
            draw.line([p0, p1], fill=col, width=max(1, int(sw * 0.8)))
    elif k in ("arrow", "rocket", "launch"):
        d = r * 0.52
        draw.line([(cx - d * 0.75, cy + d * 0.75), (cx + d * 0.72, cy - d * 0.72)], fill=col, width=sw)
        draw.line([(cx + d * 0.05, cy - d * 0.75), (cx + d * 0.75, cy - d * 0.75), (cx + d * 0.75, cy - d * 0.05)], fill=col, width=sw)
    elif k == "check":
        pts = [(cx - r * 0.44, cy + r * 0.02), (cx - r * 0.10, cy + r * 0.36), (cx + r * 0.48, cy - r * 0.32)]
        draw.line(pts, fill=col, width=sw)
    else:  # "spark" / 4-point geometric star
        pts = []
        for i in range(8):
            ang = -math.pi * 0.5 + i * (math.pi * 0.25)
            rr = r * (0.68 if i % 2 == 0 else 0.20)
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        draw.polygon(pts, fill=col)


# =============================================================================
# Premultiplied Sub-Pixel Compositing & 3D Perspective Helpers (`<150MB` RAM)
# =============================================================================

def _rgba_to_premul(pil_rgba: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """Convert PIL RGBA image into `(premul_rgb_f32 [H,W,3], alpha_f32 [H,W,1])` in `[0..255]` and `[0..1]`."""
    arr = np.asarray(pil_rgba, dtype=np.float32)
    a = arr[:, :, 3:4] * (1.0 / 255.0)
    premul = arr[:, :, :3] * a
    return premul, a


def _blend_premul_roi(
    dst_rgb_f32: np.ndarray,
    premul_rgb: np.ndarray,
    alpha_01: np.ndarray,
    dx: float,
    dy: float,
    opacity: float = 1.0,
    scale: float = 1.0,
) -> None:
    """Sub-pixel `cv2.warpAffine` premultiplied alpha composite onto `dst_rgb_f32` in place."""
    if opacity <= 0.002:
        return
    H, W = dst_rgb_f32.shape[:2]
    sh, sw = premul_rgb.shape[:2]

    # Compute tight destination bounding box around translated/scaled sprite
    cx_s, cy_s = sw * 0.5, sh * 0.5
    dst_cx = cx_s + dx
    dst_cy = cy_s + dy
    half_w = sw * 0.5 * scale + 3.0
    half_h = sh * 0.5 * scale + 3.0

    x0 = max(0, int(math.floor(dst_cx - half_w)))
    y0 = max(0, int(math.floor(dst_cy - half_h)))
    x1 = min(W, int(math.ceil(dst_cx + half_w)))
    y1 = min(H, int(math.ceil(dst_cy + half_h)))
    if x1 <= x0 or y1 <= y0:
        return

    rw, rh = x1 - x0, y1 - y0
    tx = (dst_cx - scale * cx_s) - x0
    ty = (dst_cy - scale * cy_s) - y0
    M = np.array([[scale, 0.0, tx], [0.0, scale, ty]], dtype=np.float32)

    pack = np.concatenate([premul_rgb, alpha_01], axis=2)
    warped = cv2.warpAffine(
        pack,
        M,
        (rw, rh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    roi = dst_rgb_f32[y0:y1, x0:x1]
    if dst_rgb_f32.shape[2] == 4:
        w_rgba = warped * float(opacity)
        w_a = w_rgba[:, :, 3:4]
        np.multiply(roi, 1.0 - w_a, out=roi)
        np.add(roi, w_rgba, out=roi)
    else:
        w_rgb = warped[:, :, :3] * float(opacity)
        w_a = warped[:, :, 3:4] * float(opacity)
        np.multiply(roi, 1.0 - w_a, out=roi)
        np.add(roi, w_rgb, out=roi)


def compute_3d_perspective_homography(
    card_w: int,
    card_h: int,
    dst_cx: float,
    dst_cy: float,
    rot_y_deg: float = -11.0,
    rot_x_deg: float = 5.0,
    rot_z_deg: float = 0.0,
    focal_px: float = 1380.0,
    zoom: float = 1.0,
) -> np.ndarray:
    """Exact pinhole camera 3x3 homography mapping a `(card_w, card_h)` sprite into 3D space at `(dst_cx, dst_cy)`."""
    rx = math.radians(rot_x_deg)
    ry = math.radians(rot_y_deg)
    rz = math.radians(rot_z_deg)

    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]], dtype=np.float64)
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]], dtype=np.float64)
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]], dtype=np.float64)
    R = Rz @ Ry @ Rx

    sc = float(zoom)
    src_to_centered = np.array(
        [[sc, 0.0, -card_w * 0.5 * sc], [0.0, sc, -card_h * 0.5 * sc], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    plane_to_cam = np.column_stack([R[:, 0], R[:, 1], np.array([0.0, 0.0, focal_px], dtype=np.float64)])
    K = np.array([[focal_px, 0.0, dst_cx], [0.0, focal_px, dst_cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    H_mat = K @ plane_to_cam @ src_to_centered
    return (H_mat / H_mat[2, 2]).astype(np.float32)


# =============================================================================
# Tactile Living Backdrop + Giant 6-9% Blurred Kinetic Watermark
# =============================================================================

class LivingBackdropRig:
    """
    Precomputes low-memory coordinate grids & blurred kinetic watermark once per stage,
    then synthesizes tactile `dark` (8-12% luma aurora / 3D obsidian silk + orbital arcs + bokeh)
    or `light` (88-94% luma `#EEF4EA`/`#F7F5EE` paper grain + vignette + CAD grid/arcs) per frame.
    """

    def __init__(
        self,
        width: int,
        height: int,
        theme: str = "emerald_cream_7707",
        polarity: str = "dark",
        backdrop_mode: str = "aurora",
        watermark_text: str = "khóa ảnh",
        watermark_opacity: float = 0.078,
        seed: int = 7707,
    ) -> None:
        self.W = int(width)
        self.H = int(height)
        self.scale = self.W / 1080.0
        self.pal = resolve_theme_palette(theme, polarity)
        self.polarity = self.pal["polarity"]
        self.backdrop_mode = backdrop_mode  # "aurora" | "silk"
        self.watermark_opacity = float(max(0.06, min(0.09, watermark_opacity)))

        # Quarter-res grid for silky fast float32 aurora / 3D wavy silk synthesis (< 1.6 MB)
        self.gw = max(64, self.W // 4)
        self.gh = max(64, self.H // 4)
        ys = np.linspace(-1.0, 1.0, self.gh, dtype=np.float32)[:, None]
        xs = np.linspace(-1.0, 1.0, self.gw, dtype=np.float32)[None, :]
        self.gx = np.broadcast_to(xs, (self.gh, self.gw)).copy()
        self.gy = np.broadcast_to(ys, (self.gh, self.gw)).copy()
        self.r2 = self.gx * self.gx + (self.gy * 1.35) ** 2

        rng = np.random.default_rng(seed)
        if self.polarity == "light":
            # Quarter-res vignette + compact 256x256 tileable paper grain (< 1.6 MB instead of 25 MB!)
            vig_lo = np.clip((self.gx * self.gx * 0.55 + self.gy * self.gy * 0.45), 0.0, 1.0)
            c0 = np.array(self.pal["bg_base"], dtype=np.float32)[None, None, :]
            c1 = np.array(self.pal["bg_edge"], dtype=np.float32)[None, None, :]
            fiber_lo = rng.normal(0.0, 1.3, size=(self.gh, self.gw, 1)).astype(np.float32)
            self.lo_paper_base = np.clip(c0 * (1.0 - vig_lo[:, :, None]) + c1 * vig_lo[:, :, None] + fiber_lo, 0.0, 255.0)
            g_tile = rng.normal(0.0, 2.0, size=(256, 256)).astype(np.float32)
            reps_y = (self.H + 255) // 256
            reps_x = (self.W + 255) // 256
            self.grain_row = np.tile(g_tile, (1, reps_x))[:, : self.W]
            self.reps_y = reps_y
        else:
            self.lo_paper_base = None
            d_tile = rng.normal(0.0, 0.65, size=(256, 256)).astype(np.float32)
            reps_x = (self.W + 255) // 256
            self.grain_row = np.tile(d_tile, (1, reps_x))[:, : self.W]
            self.reps_y = (self.H + 255) // 256
        self._u8_mask = np.zeros((self.H, self.W), dtype=np.uint8)

        # Subtle drifting bokeh / dust motes
        n_motes = 18
        self.motes = [
            (
                float(rng.uniform(0.06, 0.94)),
                float(rng.uniform(0.06, 0.94)),
                float(rng.uniform(-0.022, 0.022)),
                float(rng.uniform(-0.032, -0.008)),
                float(rng.uniform(2.2, 6.8) * self.scale),
                float(rng.uniform(0.10, 0.28)),
            )
            for _ in range(n_motes)
        ]

        # Pre-render Giant 6-9% Blurred Kinetic Watermark (`180-280px` lowercase geometric sans, GaussianBlur 10px)
        wm_clean = nfc_clean(watermark_text).lower() or "khóa ảnh"
        wm_font_px = int(round(228 * self.scale))
        f_wm = fit_font(wm_clean, "be_black", int(self.W * 1.18), wm_font_px, int(180 * self.scale))
        tw, th, bb = text_metrics(wm_clean, f_wm)
        pad = int(round(36 * self.scale))
        wm_img = Image.new("RGBA", (max(64, tw + pad * 2), max(64, th + pad * 2)), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wm_img)
        wd.text((pad - bb[0], pad - bb[1]), wm_clean, font=f_wm, fill=_rgba(self.pal["watermark"], 255))
        wm_img = wm_img.filter(ImageFilter.GaussianBlur(radius=max(2.0, 10.0 * self.scale)))
        self.wm_premul, self.wm_alpha = _rgba_to_premul(wm_img)

    def render_into(self, dst_f32: np.ndarray, t: float, progress_01: float, watermark_cy_pct: float = 0.50) -> None:
        """Synthesize full-screen animated backdrop + orbital CAD arcs + drifting `-18px` blurred watermark."""
        W, H = self.W, self.H
        sc = self.scale

        if self.polarity == "light" and self.lo_paper_base is not None:
            lx = 0.28 * math.cos(t * 0.9)
            ly = -0.22 + 0.18 * math.sin(t * 0.7)
            glow_lo = np.exp(-((self.gx - lx) ** 2 + (self.gy - ly) ** 2) * 2.2).astype(np.float32)[:, :, None] * 4.5
            lo_lit = self.lo_paper_base + glow_lo
            cv2.resize(lo_lit, (W, H), dst=dst_f32, interpolation=cv2.INTER_LINEAR)
            for by in range(0, H, 256):
                bh = min(256, H - by)
                dst_f32[by : by + bh] += self.grain_row[:bh, :, None]
            np.clip(dst_f32, 0.0, 255.0, out=dst_f32)
        else:
            base = np.array(self.pal["bg_base"], dtype=np.float32)[None, None, :]
            na = np.array(self.pal["node_a"], dtype=np.float32)[None, None, :]
            nb = np.array(self.pal["node_b"], dtype=np.float32)[None, None, :]

            if self.backdrop_mode == "silk":
                # Slow-drifting 3D wavy obsidian silk folds (tactile anisotropic sheen within 8-12% luma)
                phase = t * 1.15
                u_wave = self.gx * 2.6 + self.gy * 1.55 + 0.35 * np.sin(self.gy * 2.8 + phase * 0.7)
                fold_1 = 0.5 + 0.5 * np.sin(u_wave * 2.4 - phase)
                fold_2 = 0.5 + 0.5 * np.cos((self.gx * 1.4 - self.gy * 2.7) * 2.1 + phase * 0.65)
                ridge = (fold_1 ** 3.2) * 0.62 + (fold_2 ** 4.0) * 0.38
                vig = np.clip(1.0 - 0.35 * self.r2, 0.25, 1.0)
                ridge_col = np.array(self.pal["silk_ridge"], dtype=np.float32)[None, None, :]
                lo_rgb = base + (ridge_col - base) * (ridge * vig)[:, :, None] * 0.92
            else:
                # Breathing 2-node aurora gradient mesh (#071D15 + #1B4D35 etc., luma 8-12%)
                ax1 = -0.34 + 0.24 * math.sin(t * 0.95)
                ay1 = -0.32 + 0.18 * math.cos(t * 0.75)
                ax2 = 0.36 + 0.22 * math.cos(t * 0.82 + 1.1)
                ay2 = 0.30 + 0.20 * math.sin(t * 0.68 + 0.6)
                w1 = np.exp(-((self.gx - ax1) ** 2 + ((self.gy - ay1) * 1.35) ** 2) * 2.35)
                w2 = np.exp(-((self.gx - ax2) ** 2 + ((self.gy - ay2) * 1.35) ** 2) * 2.65)
                lo_rgb = base + (na - base) * (w1[:, :, None] * 0.82) + (nb - base) * (w2[:, :, None] * 0.72)

            cv2.resize(lo_rgb.astype(np.float32), (W, H), dst=dst_f32, interpolation=cv2.INTER_LINEAR)
            for by in range(0, H, 256):
                bh = min(256, H - by)
                dst_f32[by : by + bh] += self.grain_row[:bh, :, None]
            np.clip(dst_f32, 0.0, 255.0, out=dst_f32)

        # Draw 1px anti-aliased architectural CAD grid / orbital hairline arcs & bokeh dust using single reusable 1-ch mask
        u8_mask = self._u8_mask
        u8_mask.fill(0)
        hl_col = np.array(self.pal["hairline"], dtype=np.float32)[None, None, :]
        acc_col = np.array(self.pal["accent"], dtype=np.float32)[None, None, :]

        if self.polarity == "light":
            step = int(round(120 * sc))
            drift_px = int(round(progress_01 * 14 * sc))
            for gx in range((step // 2) - drift_px % step, W, step):
                cv2.line(u8_mask, (gx, 0), (gx, H), 22, 1, cv2.LINE_AA)
            for gy in range(step // 2, H, step):
                cv2.line(u8_mask, (0, gy), (W, gy), 22, 1, cv2.LINE_AA)
            ocx, ocy = W // 2, int(round(H * 0.48))
            ang_off = t * 6.5
            cv2.ellipse(u8_mask, (ocx, ocy), (int(430 * sc), int(430 * sc)), ang_off, 195, 345, 48, 1, cv2.LINE_AA)
            cv2.ellipse(u8_mask, (ocx, ocy), (int(430 * sc), int(430 * sc)), ang_off, 15, 165, 44, 1, cv2.LINE_AA)
            cv2.ellipse(u8_mask, (ocx, ocy), (int(310 * sc), int(310 * sc)), -ang_off * 0.8, 0, 360, 28, 1, cv2.LINE_AA)
            for rx_p in (0.09, 0.91):
                for ry_p in (0.08, 0.92):
                    px, py = int(W * rx_p), int(H * ry_p)
                    arm = int(9 * sc)
                    cv2.line(u8_mask, (px - arm, py), (px + arm, py), 68, 1, cv2.LINE_AA)
                    cv2.line(u8_mask, (px, py - arm), (px, py + arm), 68, 1, cv2.LINE_AA)
            tint_col = hl_col
        else:
            ocx, ocy = W // 2, int(round(H * 0.48))
            ang_off = t * 8.0
            cv2.ellipse(u8_mask, (ocx, ocy), (int(465 * sc), int(465 * sc)), ang_off, 200, 340, 42, 1, cv2.LINE_AA)
            cv2.ellipse(u8_mask, (ocx, ocy), (int(355 * sc), int(355 * sc)), -ang_off * 0.7, 25, 155, 38, 1, cv2.LINE_AA)
            S = 16
            for bx0, by0, vx, vy, rad, ma in self.motes:
                mx = ((bx0 + vx * t) % 1.0) * W
                my = ((by0 + vy * t) % 1.0) * H
                ix, iy = int(round(mx * S)), int(round(my * S))
                ir = max(8, int(round(rad * S)))
                cv2.circle(u8_mask, (ix, iy), ir, int(round(ma * 255)), -1, cv2.LINE_AA, shift=4)
            tint_col = acc_col

        m_f32 = u8_mask.astype(np.float32) * (1.0 / 255.0)
        inv_m = 1.0 - m_f32
        tc = tint_col[0, 0]
        for c_i in range(3):
            ch_v = dst_f32[:, :, c_i]
            ch_v *= inv_m
            ch_v += m_f32 * float(tc[c_i])

        # Giant 6-9% Opacity Blurred Kinetic Watermark drifting `-18px` horizontally across shot
        wm_dx = (0.5 - progress_01) * (-18.0 * sc) * -1.0  # starts +9px -> drifts -18px to -9px
        wm_x = (W - self.wm_premul.shape[1]) * 0.5 + wm_dx
        wm_y = H * watermark_cy_pct - self.wm_premul.shape[0] * 0.5
        _blend_premul_roi(dst_f32, self.wm_premul, self.wm_alpha, wm_x, wm_y, opacity=self.watermark_opacity)


# =============================================================================
# Editorial Header & Frosted Glass Builders
# =============================================================================

def _make_editorial_header_sprite(
    width: int,
    pal: dict[str, Any],
    tag_text: str,
    lead_text: str,
    hero_text: str,
    icon_kind: str = "spark",
    scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """2x-supersampled lowercase editorial lead + crisp extruded/accent focal hero title."""
    SS = 2
    W2 = int(width * SS)
    H2 = int(round(340 * scale * SS))
    img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    is_light = pal["polarity"] == "light"
    acc = pal["accent"]
    hero_rgb = pal["fg_hero"]
    lead_rgb = pal["fg_lead"]

    f_tag = load_font("mono_bold", int(round(16 * scale * SS)))
    f_lead = fit_font(nfc_clean(lead_text).lower(), "be_regular", int(W2 * 0.84), int(round(36 * scale * SS)), int(round(22 * scale * SS)))
    f_hero = fit_font(nfc_clean(hero_text).lower(), "be_italic", int(W2 * 0.86), int(round(82 * scale * SS)), int(round(44 * scale * SS)))

    # 1. Top CAD pill
    tag_clean = nfc_clean(tag_text).upper()
    tw, _, _ = text_metrics(tag_clean, f_tag)
    pw = tw + int(round(68 * scale * SS))
    ph = int(round(38 * scale * SS))
    px0 = (W2 - pw) * 0.5
    py0 = int(round(20 * scale * SS))
    draw.rounded_rectangle(
        (px0, py0, px0 + pw, py0 + ph),
        radius=ph // 2,
        fill=_rgba(acc, 24 if is_light else 36),
        outline=_rgba(acc, 165 if is_light else 210),
        width=max(2, int(round(1.5 * scale * SS))),
    )
    draw_vector_glyph(draw, icon_kind, px0 + int(24 * scale * SS), py0 + ph * 0.5, 9 * scale * SS, acc, alpha=255)
    _draw_centered(draw, px0 + int(42 * scale * SS), py0 + ph * 0.5, tag_clean, f_tag, _rgba(acc, 245), align_x="left")

    # 2. Lowercase sans lead
    lead_cy = int(round(112 * scale * SS))
    _draw_centered(draw, W2 * 0.5, lead_cy, nfc_clean(lead_text).lower(), f_lead, _rgba(lead_rgb, 245), align_x="center")

    # 3. Extruded / crisp focal hero title
    hero_cy = int(round(206 * scale * SS))
    hero_str = nfc_clean(hero_text).lower()
    if not is_light:
        glow = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        _draw_centered(gd, W2 * 0.5, hero_cy, hero_str, f_hero, _rgba(acc, 110), align_x="center")
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(radius=10 * scale * SS)))
        draw = ImageDraw.Draw(img)
        # Subtle 3D extrusion offset
        for step_i in (4, 2):
            off = int(round(step_i * scale * SS))
            _draw_centered(draw, W2 * 0.5 + off * 0.6, hero_cy + off, hero_str, f_hero, _rgba(pal["bg_base"], 220), align_x="center")
    else:
        # Tactile letterpress subtle offset on cream paper
        off = int(round(3 * scale * SS))
        _draw_centered(draw, W2 * 0.5 + off * 0.5, hero_cy + off, hero_str, f_hero, _rgba(acc, 38), align_x="center")

    _draw_centered(draw, W2 * 0.5, hero_cy, hero_str, f_hero, _rgba(hero_rgb, 255), align_x="center")

    down = img.resize((width, int(round(340 * scale))), Image.Resampling.LANCZOS)
    return _rgba_to_premul(down)


def _render_polarity_flip_matte(
    width: int,
    height: int,
    progress_flip_01: float,
    shape: str = "x",
    rim_rgb: tuple[int, int, int] = (52, 211, 153),
) -> tuple[np.ndarray, np.ndarray]:
    """
    `770765` `09.0s` mechanic: Giant vector `X` or circle `iris` zooms `1x -> 24x` over 10 frames
    to invert `dark` <-> `light` mid-scene!
    Returns `(alpha_01 [H,W,1], rim_rgb_f32 [H,W,3])`.
    """
    eased = cubic_bezier(progress_flip_01, 0.18, 0.86, 0.24, 1.00)
    zoom = 1.0 + 23.0 * (eased ** 1.35)  # 1x -> 24x
    mask_u8 = np.zeros((height, width), dtype=np.uint8)
    rim_u8 = np.zeros((height, width), dtype=np.uint8)
    cx, cy = width // 2, int(round(height * 0.50))
    sc = width / 1080.0

    if str(shape or "x").lower() == "iris":
        rad = int(round(52.0 * sc * zoom))
        cv2.circle(mask_u8, (cx, cy), rad, 255, -1, cv2.LINE_AA)
        if progress_flip_01 < 0.96:
            cv2.circle(rim_u8, (cx, cy), rad, 220, max(2, int(round(5 * sc))), cv2.LINE_AA)
    else:
        # Giant architectural vector X zooming 1x -> 24x (reaches full-screen 100% fill at 24x)
        arm_len = 116.0 * sc * zoom
        thickness = max(6, int(round(58.0 * sc * zoom)))
        d = arm_len * 0.7071
        p1 = (int(round(cx - d)), int(round(cy - d)))
        p2 = (int(round(cx + d)), int(round(cy + d)))
        p3 = (int(round(cx - d)), int(round(cy + d)))
        p4 = (int(round(cx + d)), int(round(cy - d)))
        cv2.line(mask_u8, p1, p2, 255, thickness, cv2.LINE_AA)
        cv2.line(mask_u8, p3, p4, 255, thickness, cv2.LINE_AA)
        if progress_flip_01 < 0.94:
            rim_k = cv2.dilate(mask_u8, np.ones((7, 7), np.uint8), iterations=1) - mask_u8
            rim_u8 = rim_k

    a01 = mask_u8.astype(np.float32)[:, :, None] * (1.0 / 255.0)
    rim_a01 = rim_u8.astype(np.float32) * (1.0 / 255.0)
    return a01, rim_a01


# =============================================================================
# FFmpeg Streaming Encoder & Metadata Hygiene
# =============================================================================

@lru_cache(maxsize=1)
def _resolve_ffmpeg() -> str:
    for cand in (str(Path.home() / ".local/bin/ffmpeg"), shutil.which("ffmpeg") or ""):
        if cand and os.path.isfile(cand):
            return cand
    raise FileNotFoundError("ffmpeg binary not found")


def strip_mp4_metadata(path: str | Path) -> None:
    """v7.9.1: shared helper (strip-media-metadata skill, else `ffmpeg -map_metadata -1 -c copy`; warns loudly when both fail)."""
    _wpb().strip_media_metadata(path, keep_icc=False)


def encode_frames_to_mp4(
    frame_iter: Iterator[np.ndarray],
    out_path: str | Path,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    fps: int = DEFAULT_FPS,
    crf: int = 17,
    input_color: str = "rgb",
) -> dict[str, Any]:
    """Stream frames directly into H.264 `.mp4` via FFmpeg stdin pipe (`<150MB` RAM, zero temp PNGs)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pix_in = "bgr24" if input_color.lower() == "bgr" else "rgb24"
    cmd = [
        _resolve_ffmpeg(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        pix_in,
        "-s",
        f"{int(width)}x{int(height)}",
        "-r",
        str(int(fps)),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(int(crf)),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    n_frames = 0
    mid_luma_pct = 0.0
    try:
        for idx, frame in enumerate(frame_iter):
            arr = np.ascontiguousarray(frame, dtype=np.uint8)
            if idx == 0 or idx % 15 == 0:
                # Track representative frame luminance (%)
                if input_color.lower() == "bgr":
                    luma = 0.114 * arr[:, :, 0].mean() + 0.587 * arr[:, :, 1].mean() + 0.299 * arr[:, :, 2].mean()
                else:
                    luma = 0.299 * arr[:, :, 0].mean() + 0.587 * arr[:, :, 1].mean() + 0.114 * arr[:, :, 2].mean()
                mid_luma_pct = round(float(luma / 255.0 * 100.0), 2)
            proc.stdin.write(arr.tobytes())
            n_frames += 1
    finally:
        proc.stdin.close()
    stderr_bytes = proc.stderr.read() if proc.stderr else b""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg encode failed (rc={rc}): {stderr_bytes.decode('utf-8', errors='replace')}")
    strip_mp4_metadata(out)
    return {"out_path": str(out), "num_frames": n_frames, "mean_luma_pct": mid_luma_pct}


# =============================================================================
# STAGE 1: `render_timeline_playhead_stage` (`770765` 09.5s & 19.1s + Polarity Flip)
# =============================================================================

def _build_timeline_console_shell(
    card_w: int,
    card_h: int,
    pal: dict[str, Any],
    blocks: Sequence[dict[str, Any]],
    scale: float,
) -> tuple[np.ndarray, np.ndarray, list[tuple[float, float, float, float, tuple[int, int, int], str]]]:
    """Pre-render 2x-supersampled frosted glass timeline console shell + ruler ticks."""
    SS = 2
    W2, H2 = card_w * SS, card_h * SS
    is_light = pal["polarity"] == "light"
    img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(round(20 * scale * SS))
    x0, y0 = pad, pad
    x1, y1 = W2 - pad, H2 - pad
    rad = int(round(28 * scale * SS))

    # Drop shadow
    sh = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (x0, y0 + int(10 * scale * SS), x1, y1 + int(12 * scale * SS)),
        radius=rad,
        fill=(14, 34, 24, 38) if is_light else (0, 0, 0, 145),
    )
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(radius=12 * scale * SS)))
    draw = ImageDraw.Draw(img)

    # Frosted glass body
    bg_fill = _rgba(pal["card_bg"], 226 if is_light else 234)
    border_col = _rgba(pal["card_border"], 85 if is_light else 175)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=rad, fill=bg_fill, outline=border_col, width=max(2, int(2 * scale * SS)))

    # Top timecode ruler strip (`00:01 .. 00:05`)
    ruler_y1 = y0 + int(round(68 * scale * SS))
    draw.line([(x0 + int(24 * scale * SS), ruler_y1), (x1 - int(24 * scale * SS), ruler_y1)], fill=_rgba(pal["fg_muted"], 75), width=max(1, SS))

    f_tc = load_font("mono_bold", int(round(15 * scale * SS)))
    f_lane = load_font("mono_bold", int(round(14 * scale * SS)))
    track_x0 = x0 + int(round(88 * scale * SS))
    track_x1 = x1 - int(round(36 * scale * SS))
    track_span = track_x1 - track_x0

    for sec_i in range(6):
        tx = track_x0 + (sec_i / 5.0) * track_span
        draw.line([(tx, ruler_y1 - int(14 * scale * SS)), (tx, ruler_y1)], fill=_rgba(pal["fg_lead"], 155), width=max(1, int(1.5 * SS)))
        _draw_centered(draw, tx, y0 + int(32 * scale * SS), f"00:0{sec_i}", f_tc, _rgba(pal["fg_muted"], 215), align_x="center")
        if sec_i < 5:
            for sub_i in range(1, 4):
                stx = tx + (sub_i / 20.0) * track_span
                draw.line([(stx, ruler_y1 - int(7 * scale * SS)), (stx, ruler_y1)], fill=_rgba(pal["fg_muted"], 75), width=max(1, SS))

    # Track lane labels (`V2`, `V1`, `A1`)
    lane_ys = [
        ruler_y1 + int(round(62 * scale * SS)),
        ruler_y1 + int(round(156 * scale * SS)),
        ruler_y1 + int(round(256 * scale * SS)),
    ]
    for lbl, lcy in zip(("V2", "V1", "A1"), lane_ys):
        _draw_centered(draw, x0 + int(44 * scale * SS), lcy, lbl, f_lane, _rgba(pal["fg_muted"], 210), align_x="center")
        lh = int(round(36 * scale * SS))
        draw.rounded_rectangle(
            (track_x0, lcy - lh, track_x1, lcy + lh),
            radius=int(round(12 * scale * SS)),
            fill=_rgba(pal["fg_muted"], 16 if is_light else 22),
            outline=_rgba(pal["fg_muted"], 34),
            width=max(1, SS),
        )

    # V1 continuous anchor structure bar
    v1_cy = lane_ys[1]
    v1_h = int(round(30 * scale * SS))
    draw.rounded_rectangle(
        (track_x0 + int(6 * scale * SS), v1_cy - v1_h, track_x1 - int(6 * scale * SS), v1_cy + v1_h),
        radius=int(round(10 * scale * SS)),
        fill=_rgba(pal["accent_2"], 34 if is_light else 46),
        outline=_rgba(pal["accent_2"], 135),
        width=max(1, int(1.5 * SS)),
    )
    draw_vector_glyph(draw, "padlock", track_x0 + int(34 * scale * SS), v1_cy, 11 * scale * SS, pal["accent_2"], alpha=235)
    f_v1 = load_font("be_bold", int(round(17 * scale * SS)))
    _draw_centered(
        draw,
        track_x0 + int(58 * scale * SS),
        v1_cy,
        "TRACK GỐC · KHÓA KẾT CẤU & ÁNH SÁNG 100%",
        f_v1,
        _rgba(pal["fg_hero"], 225),
        align_x="left",
    )

    # Return normalized 1x coordinates for V2 blocks & A1 waveform zone so per-frame playhead interaction is dynamic
    block_specs_1x: list[tuple[float, float, float, float, tuple[int, int, int], str]] = []
    v2_cy_1x = lane_ys[0] / SS
    v2_h_1x = 31.0 * scale
    palette_cycle = [pal["accent"], pal["accent_3"], pal["accent_2"]]
    for idx, blk in enumerate(blocks):
        u0 = float(blk.get("u0", idx / max(1, len(blocks))))
        u1 = float(blk.get("u1", (idx + 1) / max(1, len(blocks)) - 0.02))
        bx0 = (track_x0 / SS) + u0 * (track_span / SS)
        bx1 = (track_x0 / SS) + u1 * (track_span / SS)
        col = palette_cycle[idx % len(palette_cycle)]
        block_specs_1x.append((bx0, v2_cy_1x - v2_h_1x, bx1, v2_cy_1x + v2_h_1x, col, nfc_clean(blk.get("label", f"STEP 0{idx+1}"))))

    down = img.resize((card_w, card_h), Image.Resampling.LANCZOS)
    premul, a = _rgba_to_premul(down)
    return premul, a, block_specs_1x


def iter_timeline_playhead_stage(
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "dark",
    lead_text: str = "quy trình 3 bước",
    hero_text: str = "khóa kết cấu,",
    watermark_text: str = "khóa ảnh",
    tag_text: str = "TIMELINE // WORKFLOW LOCK",
    blocks: Sequence[dict[str, Any]] | None = None,
    polarity_flip_at_t: float | None = None,
    flip_shape: str = "x",
    output_color: str = "rgb",
) -> Iterator[np.ndarray]:
    """
    Stage 1 Generator (`770765` 09.5s & 19.1s):
      - 3D glassmorphic timeline console (`00:00..00:05`, color-coded rounded V2 blocks, pulsing A1 waveform bars,
        live glowing playhead needle scrubbing left-to-right in sync with `t`).
      - Optional `polarity_flip_at_t`: giant vector `X` or `iris` zooms `1x -> 24x` over 10 frames to invert
        `dark` <-> `light` mid-scene!
    """
    sc = width / 1080.0
    n_frames = max(1, int(round(duration_sec * fps)))
    if not blocks:
        blocks = [
            {"u0": 0.01, "u1": 0.32, "label": "01 · KHÓA GỐC"},
            {"u0": 0.35, "u1": 0.67, "label": "02 · ÁNH SÁNG"},
            {"u0": 0.70, "u1": 0.99, "label": "03 · XUẤT 4K"},
        ]

    card_w = int(round(956 * sc))
    card_h = int(round(418 * sc))
    card_x = (width - card_w) * 0.5
    card_y = height * 0.44

    def _build_polarity_bundle(pol: str) -> dict[str, Any]:
        pal_p = resolve_theme_palette(theme, pol)
        rig_p = LivingBackdropRig(width, height, theme=theme, polarity=pol, backdrop_mode="aurora", watermark_text=watermark_text, seed=7707)
        hdr_premul, hdr_a = _make_editorial_header_sprite(width, pal_p, tag_text, lead_text, hero_text, icon_kind="aperture", scale=sc)
        con_premul, con_a, blk_specs = _build_timeline_console_shell(card_w, card_h, pal_p, blocks, sc)
        return {
            "pal": pal_p,
            "rig": rig_p,
            "hdr_premul": hdr_premul,
            "hdr_a": hdr_a,
            "con_premul": con_premul,
            "con_a": con_a,
            "blk_specs": blk_specs,
        }

    bundle_a = _build_polarity_bundle(polarity)
    inv_polarity = "light" if bundle_a["pal"]["polarity"] == "dark" else "dark"
    bundle_b = _build_polarity_bundle(inv_polarity) if polarity_flip_at_t is not None else None

    f_blk = load_font("be_extrabold", int(round(16 * sc)))
    f_tc_live = load_font("mono_bold", int(round(16 * sc)))

    buf_a = np.zeros((height, width, 3), dtype=np.float32)
    buf_b = np.zeros((height, width, 3), dtype=np.float32) if bundle_b is not None else None

    def _render_single_polarity(dst: np.ndarray, bnd: dict[str, Any], t_sec: float, u_prog: float, scrub_u: float) -> None:
        pal_c = bnd["pal"]
        is_light = pal_c["polarity"] == "light"
        bnd["rig"].render_into(dst, t_sec, u_prog, watermark_cy_pct=0.49)

        # Gentle floating entrance & breathing on header and timeline console
        enter = smooth_window(t_sec, 0.0, min(0.38, duration_sec * 0.35))
        hdr_y = height * 0.14 + (1.0 - enter) * (-18.0 * sc) + math.sin(t_sec * 1.4) * (2.0 * sc)
        _blend_premul_roi(dst, bnd["hdr_premul"], bnd["hdr_a"], 0.0, hdr_y, opacity=0.35 + 0.65 * enter)

        cy_float = card_y + (1.0 - enter) * (22.0 * sc) + math.cos(t_sec * 1.2) * (2.5 * sc)
        _blend_premul_roi(dst, bnd["con_premul"], bnd["con_a"], card_x, cy_float, opacity=0.40 + 0.60 * enter)

        # Dynamic overlay layer inside console: active V2 blocks + pulsing A1 waveform + glowing playhead needle
        ov = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        pad_1x = 20.0 * sc
        track_x0 = pad_1x + 88.0 * sc
        track_x1 = card_w - pad_1x - 36.0 * sc
        track_span = track_x1 - track_x0
        play_x = track_x0 + scrub_u * track_span

        # 1. Color-coded V2 blocks lighting up when playhead enters/passes them
        for bx0, by0, bx1, by1, col, lbl in bnd["blk_specs"]:
            is_hit = play_x >= (bx0 - 6.0 * sc)
            is_inside = (bx0 - 4.0 * sc) <= play_x <= (bx1 + 4.0 * sc)
            fill_a = 205 if is_inside else (135 if is_hit else (48 if is_light else 56))
            out_a = 255 if is_inside else (180 if is_hit else 95)
            od.rounded_rectangle(
                (bx0, by0, bx1, by1),
                radius=int(round(11 * sc)),
                fill=_rgba(col, fill_a if not is_light else min(185, fill_a)),
                outline=_rgba(col, out_a),
                width=max(2, int(round((2.6 if is_inside else 1.5) * sc))),
            )
            txt_col = (255, 255, 255, 255) if (is_inside and is_light) else (_rgba(pal_c["fg_hero"], 250 if is_hit else 155))
            if not is_light and is_inside:
                txt_col = (10, 22, 18, 255)
            _draw_centered(od, (bx0 + bx1) * 0.5, (by0 + by1) * 0.5, lbl, f_blk, txt_col, align_x="center")

        # 2. Animated A1 audio/signal waveform bars (46 vertical rounded bars)
        a1_cy = pad_1x + (68.0 + 256.0) * sc
        n_bars = 46
        bar_step = (track_span - 16.0 * sc) / n_bars
        bar_w = max(3.0 * sc, bar_step * 0.52)
        for bi in range(n_bars):
            bu = (bi + 0.5) / n_bars
            bx = track_x0 + 8.0 * sc + bi * bar_step
            dist_ph = abs(bu - scrub_u)
            prox = math.exp(-(dist_ph * 8.5) ** 2)
            amp = (0.24 + 0.52 * abs(math.sin(bi * 0.72 + t_sec * 5.8)) * (0.45 + 0.55 * abs(math.cos(bi * 0.31 - t_sec * 3.1))) + 0.24 * prox)
            bh = max(4.0 * sc, min(28.0 * sc, amp * 28.0 * sc))
            passed = bu <= scrub_u
            b_rgb = pal_c["accent"] if passed else pal_c["fg_muted"]
            b_alpha = int(round(235 if prox > 0.45 else (175 if passed else (75 if is_light else 68))))
            od.rounded_rectangle((bx, a1_cy - bh, bx + bar_w, a1_cy + bh), radius=max(1, int(bar_w * 0.5)), fill=_rgba(b_rgb, b_alpha))

        # 3. Live Glowing Playhead Needle + Pentagon Cap + Floating Timecode Readout
        needle_top = pad_1x + 48.0 * sc
        needle_bot = card_h - pad_1x - 24.0 * sc
        ph_rgb = pal_c["accent_2"] if not is_light else pal_c["accent"]

        glow_im = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_im)
        gd.line([(play_x, needle_top), (play_x, needle_bot)], fill=_rgba(ph_rgb, 165), width=max(3, int(round(6 * sc))))
        ov = Image.alpha_composite(ov, glow_im.filter(ImageFilter.GaussianBlur(radius=6 * sc)))
        od = ImageDraw.Draw(ov)

        od.line([(play_x, needle_top), (play_x, needle_bot)], fill=_rgba(ph_rgb, 255), width=max(2, int(round(2.6 * sc))))
        cap_w, cap_h = 10.0 * sc, 13.0 * sc
        od.polygon(
            [
                (play_x - cap_w, needle_top - cap_h),
                (play_x + cap_w, needle_top - cap_h),
                (play_x + cap_w, needle_top - cap_h * 0.3),
                (play_x, needle_top + 2.0 * sc),
                (play_x - cap_w, needle_top - cap_h * 0.3),
            ],
            fill=_rgba(ph_rgb, 255),
        )

        # Live scrubbing timecode badge below console track
        tc_sec = int(scrub_u * 5.0)
        tc_frm = int(round((scrub_u * 5.0 - tc_sec) * fps)) % max(1, fps)
        tc_str = f"TC 00:0{tc_sec}:{tc_frm:02d} · LOCK ACTIVE"
        tw_tc, _, _ = text_metrics(tc_str, f_tc_live)
        pill_w = tw_tc + 36 * sc
        pill_x = max(pad_1x + 16 * sc, min(card_w - pad_1x - pill_w - 16 * sc, play_x - pill_w * 0.5))
        pill_y = card_h - pad_1x - 46 * sc
        od.rounded_rectangle(
            (pill_x, pill_y, pill_x + pill_w, pill_y + 30 * sc),
            radius=int(round(15 * sc)),
            fill=_rgba(pal_c["card_bg_2"], 235),
            outline=_rgba(ph_rgb, 210),
            width=max(1, int(round(1.5 * sc))),
        )
        _draw_centered(od, pill_x + pill_w * 0.5, pill_y + 15 * sc, tc_str, f_tc_live, _rgba(ph_rgb, 255), align_x="center")

        ov_premul, ov_a = _rgba_to_premul(ov)
        _blend_premul_roi(dst, ov_premul, ov_a, card_x, cy_float, opacity=1.0)

    flip_dur = 10.0 / max(1.0, float(fps))  # Exact 10-frame polarity flip (`770765` 09.0s mechanic)

    for idx in range(n_frames):
        t = idx / max(1.0, float(fps))
        u = idx / max(1, n_frames - 1) if n_frames > 1 else 0.5
        scrub_u = 0.08 + 0.84 * cubic_bezier(u, 0.22, 0.68, 0.28, 1.00)

        if polarity_flip_at_t is None or bundle_b is None or t < polarity_flip_at_t:
            _render_single_polarity(buf_a, bundle_a, t, u, scrub_u)
            out_f32 = buf_a
        elif t >= polarity_flip_at_t + flip_dur:
            _render_single_polarity(buf_b, bundle_b, t, u, scrub_u)
            out_f32 = buf_b
        else:
            assert buf_b is not None
            _render_single_polarity(buf_a, bundle_a, t, u, scrub_u)
            _render_single_polarity(buf_b, bundle_b, t, u, scrub_u)
            u_flip = (t - polarity_flip_at_t) / max(1e-6, flip_dur)
            rim_rgb = bundle_a["pal"]["accent"]
            matte_a, rim_a01 = _render_polarity_flip_matte(
                width, height, u_flip, shape=flip_shape, rim_rgb=rim_rgb
            )
            buf_a *= 1.0 - matte_a
            buf_b *= matte_a
            buf_a += buf_b
            for c_i in range(3):
                buf_a[:, :, c_i] += rim_a01 * float(rim_rgb[c_i])
            np.clip(buf_a, 0.0, 255.0, out=buf_a)
            out_f32 = buf_a

        u8 = out_f32.astype(np.uint8)
        yield u8[:, :, ::-1] if output_color.lower() == "bgr" else u8


def render_timeline_playhead_stage(
    out_path: str | Path | None = None,
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "dark",
    lead_text: str = "quy trình 3 bước",
    hero_text: str = "khóa kết cấu,",
    watermark_text: str = "khóa ảnh",
    tag_text: str = "TIMELINE // WORKFLOW LOCK",
    blocks: Sequence[dict[str, Any]] | None = None,
    polarity_flip_at_t: float | None = None,
    flip_shape: str = "x",
    crf: int = 17,
) -> dict[str, Any] | Iterator[np.ndarray]:
    frame_gen = iter_timeline_playhead_stage(
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        theme=theme,
        polarity=polarity,
        lead_text=lead_text,
        hero_text=hero_text,
        watermark_text=watermark_text,
        tag_text=tag_text,
        blocks=blocks,
        polarity_flip_at_t=polarity_flip_at_t,
        flip_shape=flip_shape,
        output_color="rgb",
    )
    if out_path is None:
        return frame_gen
    enc = encode_frames_to_mp4(frame_gen, out_path, width=width, height=height, fps=fps, crf=crf, input_color="rgb")
    return {
        **enc,
        "stage": "timeline_playhead_stage",
        "theme": theme,
        "polarity": polarity,
        "polarity_flip_at_t": polarity_flip_at_t,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
        "anchor_shape_xyr": {
            "cx_pct": 0.50,
            "cy_pct": 0.55,
            "r_pct_w": 0.44,
            "cx_px": width // 2,
            "cy_px": int(round(height * 0.55)),
            "r_px": int(round(width * 0.44)),
            "shape": flip_shape if polarity_flip_at_t is not None else "rounded_rect",
        },
    }


# =============================================================================
# STAGE 2: `render_concentric_lock_lab_stage` (`770765` 33.3s-37.5s Cream Match-Cut Lab)
# =============================================================================

def _make_shaded_3d_sphere_rgba(
    diameter_px: int,
    base_rgb: tuple[int, int, int],
    rim_rgb: tuple[int, int, int],
    light_dir: tuple[float, float, float] = (-0.42, -0.52, 0.74),
) -> Image.Image:
    """Analytic float32 ray-shaded 3D sphere (Lambertian + Phong specular + Fresnel rim + anti-aliased edge)."""
    D = max(32, int(diameter_px))
    yy, xx = np.mgrid[0:D, 0:D].astype(np.float32)
    r = (D - 2.0) * 0.5
    nx = (xx - (D - 1) * 0.5) / r
    ny = (yy - (D - 1) * 0.5) / r
    r2 = nx * nx + ny * ny
    inside = r2 < 1.0
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

    lx, ly, lz = light_dir
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln

    ndotl = np.clip(nx * lx + ny * ly + nz * lz, 0.0, 1.0)
    # Half-vector for crisp studio specular highlight (view = [0, 0, 1])
    hx, hy, hz = lx, ly, lz + 1.0
    hn = math.sqrt(hx * hx + hy * hy + hz * hz)
    spec = np.clip(nx * (hx / hn) + ny * (hy / hn) + nz * (hz / hn), 0.0, 1.0) ** 34.0
    fresnel = ((1.0 - nz) ** 2.6) * inside

    b_col = np.array(base_rgb, dtype=np.float32)[None, None, :]
    r_col = np.array(rim_rgb, dtype=np.float32)[None, None, :]
    rgb = b_col * (0.22 + 0.82 * ndotl[:, :, None]) + r_col * (0.48 * fresnel[:, :, None]) + 255.0 * (0.58 * spec[:, :, None])
    rgb = np.clip(rgb, 0.0, 255.0)

    # Smooth 1.5px anti-aliased silhouette
    dist = np.sqrt(r2) * r
    alpha = np.clip((r - dist) * 1.35 + 0.5, 0.0, 1.0) * 255.0
    rgba = np.dstack([rgb, alpha]).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def _build_specimen_plate_sprite(
    plate_size: int,
    sphere_diam: int,
    label_top: str,
    callout_code: str,
    pal: dict[str, Any],
    accent_rgb: tuple[int, int, int],
    image_path: str | Path | None = None,
    scale: float = 1.0,
    label_align: str = "left",
) -> tuple[np.ndarray, np.ndarray]:
    """Frosted glass specimen plate (`input a` or `studio b`) housing a 3D sphere OR rounded thumbnail."""
    SS = 2
    S2 = plate_size * SS
    pad = int(round(24 * scale * SS))
    img = Image.new("RGBA", (S2 + pad * 2, S2 + pad * 2), (0, 0, 0, 0))
    is_light = pal["polarity"] == "light"

    x0, y0 = pad, pad
    x1, y1 = pad + S2, pad + S2
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    rad = int(round(36 * scale * SS))

    # Soft specimen shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (x0, y0 + int(10 * scale * SS), x1, y1 + int(12 * scale * SS)),
        radius=rad,
        fill=(16, 42, 28, 34) if is_light else (0, 0, 0, 125),
    )
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(radius=11 * scale * SS)))
    draw = ImageDraw.Draw(img)

    # Translucent frosted glass plate so concentric overlap reveals layered depth!
    fill_a = 176 if is_light else 168
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=rad,
        fill=_rgba(pal["card_bg"], fill_a),
        outline=_rgba(accent_rgb, 155 if is_light else 205),
        width=max(2, int(round(2.0 * scale * SS))),
    )

    # Concentric CAD specimen ring (`ø 140`)
    sph_r2 = int(round((sphere_diam * 0.5) * SS))
    draw.ellipse(
        (cx - sph_r2 - int(10 * scale * SS), cy - sph_r2 - int(10 * scale * SS), cx + sph_r2 + int(10 * scale * SS), cy + sph_r2 + int(10 * scale * SS)),
        outline=_rgba(accent_rgb, 90),
        width=max(1, int(round(1.2 * scale * SS))),
    )

    # Center specimen: rounded thumbnail OR shaded 3D sphere
    if image_path and Path(image_path).is_file():
        with Image.open(image_path) as im_src:
            thumb = ImageOps.fit(im_src.convert("RGBA"), (sph_r2 * 2, sph_r2 * 2), method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (sph_r2 * 2, sph_r2 * 2), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, sph_r2 * 2 - 1, sph_r2 * 2 - 1), fill=255)
        img.paste(thumb, (int(cx - sph_r2), int(cy - sph_r2)), mask)
        draw = ImageDraw.Draw(img)
    else:
        sph = _make_shaded_3d_sphere_rgba(sph_r2 * 2, accent_rgb, pal["accent_2"])
        img.alpha_composite(sph, (int(cx - sph_r2), int(cy - sph_r2)))
        draw = ImageDraw.Draw(img)

    f_lbl = load_font("mono_bold", int(round(14 * scale * SS)))
    if label_align == "right":
        _draw_centered(draw, x1 - int(22 * scale * SS), y0 + int(26 * scale * SS), label_top.upper(), f_lbl, _rgba(pal["fg_lead"], 230), align_x="right")
        _draw_centered(draw, x1 - int(22 * scale * SS), y1 - int(26 * scale * SS), callout_code, f_lbl, _rgba(accent_rgb, 235), align_x="right")
    else:
        _draw_centered(draw, x0 + int(22 * scale * SS), y0 + int(26 * scale * SS), label_top.upper(), f_lbl, _rgba(pal["fg_lead"], 230), align_x="left")
        _draw_centered(draw, x0 + int(22 * scale * SS), y1 - int(26 * scale * SS), callout_code, f_lbl, _rgba(accent_rgb, 235), align_x="left")

    down = img.resize(((S2 + pad * 2) // SS, (S2 + pad * 2) // SS), Image.Resampling.LANCZOS)
    return _rgba_to_premul(down)


def iter_concentric_lock_lab_stage(
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "light",
    lead_text: str = "đối chiếu trực tiếp",
    hero_text: str = "khớp chuẩn 100%",
    watermark_text: str = "khớp chuẩn",
    tag_text: str = "SPECIMEN LAB // MATCH-CUT",
    plate_a_label: str = "input a",
    plate_b_label: str = "studio b",
    plate_a_image: str | Path | None = None,
    plate_b_image: str | Path | None = None,
    lock_cx: int | None = None,
    lock_cy: int | None = None,
    specimen_diameter: int = 280,
    output_color: str = "rgb",
) -> Iterator[np.ndarray]:
    """
    Stage 2 Generator (`770765` 33.3s-37.5s Cream Match-Cut Lab):
      - Default `polarity="light"` (`#EEF4EA` cream canvas + giant `"khớp chuẩn"` watermark).
      - Two frosted glass specimen plates (`input a` & `studio b`) annotated with monospace CAD callouts
        (`ø 140`, `LOCK 100%`, `Δ 0.0%`).
      - Physically glide horizontally along `cy=920` until they lock concentrically at `(cx=540, cy=920)`
        as a crisp focus reticle `[ + ]` pulses around the locked center!
    """
    sc = width / 1080.0
    cx_target = float(lock_cx if lock_cx is not None else round(540 * sc))
    cy_target = float(lock_cy if lock_cy is not None else round(920 * (height / 1920.0)))
    sph_diam = int(round(specimen_diameter * sc))
    plate_sz = int(round(368 * sc))

    pal = resolve_theme_palette(theme, polarity)
    is_light = pal["polarity"] == "light"
    rig = LivingBackdropRig(width, height, theme=theme, polarity=polarity, backdrop_mode="aurora", watermark_text=watermark_text, seed=3337)
    hdr_premul, hdr_a = _make_editorial_header_sprite(width, pal, tag_text, lead_text, hero_text, icon_kind="padlock", scale=sc)

    plate_a_premul, plate_a_alpha = _build_specimen_plate_sprite(
        plate_sz, sph_diam, plate_a_label, f"ø {int(round(specimen_diameter * 0.5))}", pal, pal["accent"], image_path=plate_a_image, scale=sc, label_align="left"
    )
    plate_b_premul, plate_b_alpha = _build_specimen_plate_sprite(
        plate_sz, sph_diam, plate_b_label, "REF · LOCK", pal, pal["accent_2"], image_path=plate_b_image, scale=sc, label_align="right"
    )
    pw, ph = plate_a_alpha.shape[1], plate_a_alpha.shape[0]

    f_cad = load_font("mono_bold", int(round(17 * sc)))
    f_status = load_font("be_extrabold", int(round(22 * sc)))

    n_frames = max(1, int(round(duration_sec * fps)))
    frame_f32 = np.zeros((height, width, 3), dtype=np.float32)
    max_sep = 224.0 * sc

    for idx in range(n_frames):
        t = idx / max(1.0, float(fps))
        u = idx / max(1, n_frames - 1) if n_frames > 1 else 0.55

        rig.render_into(frame_f32, t, u, watermark_cy_pct=cy_target / height)

        enter = smooth_window(t, 0.0, min(0.35, duration_sec * 0.28))
        _blend_premul_roi(frame_f32, hdr_premul, hdr_a, 0.0, height * 0.11 + (1.0 - enter) * (-14.0 * sc), opacity=0.35 + 0.65 * enter)

        # Horizontal convergence glide along exact same `cy_target = 920` -> locks concentrically by u = 0.46!
        lock_u = cubic_bezier(max(0.0, min(1.0, (u - 0.10) / 0.36)), 0.14, 0.90, 0.20, 1.00)
        sep = max_sep * (1.0 - lock_u)
        cx_a = cx_target - sep
        cx_b = cx_target + sep

        _blend_premul_roi(frame_f32, plate_a_premul, plate_a_alpha, cx_a - pw * 0.5, cy_target - ph * 0.5, opacity=1.0)
        _blend_premul_roi(frame_f32, plate_b_premul, plate_b_alpha, cx_b - pw * 0.5, cy_target - ph * 0.5, opacity=0.92 if lock_u < 0.98 else 0.84)

        # CAD callouts + pulsing `[ + ]` concentric focus reticle inside compact vertical HUD band
        hud_y0 = max(0, int(round(cy_target - plate_sz * 0.65)))
        hud_y1 = min(height, int(round(cy_target + plate_sz * 0.5 + 195.0 * sc)))
        hud_h = max(32, hud_y1 - hud_y0)
        cy_loc = cy_target - hud_y0

        hud = Image.new("RGBA", (width, hud_h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hud)
        acc = pal["accent"]
        fg_ink = pal["fg_hero"]

        # Horizontal axis datum line along y = cy_target
        hd.line([(int(72 * sc), int(cy_loc)), (int(width - 72 * sc), int(cy_loc))], fill=_rgba(acc, 48), width=max(1, int(sc)))

        is_locked = lock_u >= 0.96
        pulse = 1.0 + (0.045 * math.sin((t - 0.40 * duration_sec) * 9.0) if is_locked else 0.0)
        ret_r = (sph_diam * 0.5 + 24.0 * sc) * pulse
        arm = 24.0 * sc
        ret_alpha = int(round(90 + 165 * lock_u))

        # Focus brackets `[ + ]` around `(cx_target, cy_loc)`
        rx0, ry0 = cx_target - ret_r, cy_loc - ret_r
        rx1, ry1 = cx_target + ret_r, cy_loc + ret_r
        sw = max(2, int(round(2.5 * sc)))
        hd.line([(rx0, ry0 + arm), (rx0, ry0), (rx0 + arm, ry0)], fill=_rgba(acc, ret_alpha), width=sw)
        hd.line([(rx1 - arm, ry0), (rx1, ry0), (rx1, ry0 + arm)], fill=_rgba(acc, ret_alpha), width=sw)
        hd.line([(rx0, ry1 - arm), (rx0, ry1), (rx0 + arm, ry1)], fill=_rgba(acc, ret_alpha), width=sw)
        hd.line([(rx1 - arm, ry1), (rx1, ry1), (rx1, ry1 - arm)], fill=_rgba(acc, ret_alpha), width=sw)

        # Center `+` crosshair
        ch = 11.0 * sc
        hd.line([(cx_target - ch, cy_loc), (cx_target + ch, cy_loc)], fill=_rgba(fg_ink if is_light else (255, 255, 255), ret_alpha), width=max(2, int(round(2 * sc))))
        hd.line([(cx_target, cy_loc - ch), (cx_target, cy_loc + ch)], fill=_rgba(fg_ink if is_light else (255, 255, 255), ret_alpha), width=max(2, int(round(2 * sc))))

        if is_locked:
            ring_r = (sph_diam * 0.5) * pulse
            hd.ellipse((cx_target - ring_r, cy_loc - ring_r, cx_target + ring_r, cy_loc + ring_r), outline=_rgba(acc, 235), width=max(2, int(round(2.4 * sc))))

        # Monospace CAD Telemetry Readout Pill below specimen stage (`ø 140 · LOCK 100% · Δ 0.0%`)
        delta_pct = round((1.0 - lock_u) * 42.0, 1)
        lock_pct = int(round(58 + 42 * lock_u))
        cad_line = f"ø {int(round(specimen_diameter * 0.5))}   ·   LOCK {lock_pct}%   ·   Δ {delta_pct:.1f}%"
        pill_cy = cy_loc + plate_sz * 0.5 + 88.0 * sc
        tw_c, _, _ = text_metrics(cad_line, f_cad)
        pw_c = tw_c + 86.0 * sc
        px0_c = cx_target - pw_c * 0.5
        hd.rounded_rectangle(
            (px0_c, pill_cy - 28 * sc, px0_c + pw_c, pill_cy + 28 * sc),
            radius=int(round(28 * sc)),
            fill=_rgba(pal["card_bg"], 232 if is_light else 225),
            outline=_rgba(acc, 185 if is_locked else 110),
            width=max(2, int(round(1.8 * sc))),
        )
        draw_vector_glyph(hd, "padlock" if is_locked else "aperture", px0_c + 30 * sc, pill_cy, 12 * sc, acc, alpha=245)
        _draw_centered(hd, px0_c + 52 * sc, pill_cy, cad_line, f_cad, _rgba(fg_ink, 245), align_x="left")

        sub_caption = "ĐỒNG TÂM TUYỆT ĐỐI (540, 920) — SẴN SÀNG MATCH-CUT" if is_locked else "ĐANG CĂN CHỈNH TRỤC ĐỒNG TÂM..."
        _draw_centered(hd, cx_target, pill_cy + 62 * sc, sub_caption, f_status, _rgba(pal["fg_muted"], 220), align_x="center")

        hud_premul, hud_a = _rgba_to_premul(hud)
        _blend_premul_roi(frame_f32, hud_premul, hud_a, 0.0, float(hud_y0), opacity=1.0)

        u8 = np.clip(frame_f32, 0.0, 255.0).astype(np.uint8)
        yield u8[:, :, ::-1] if output_color.lower() == "bgr" else u8


def render_concentric_lock_lab_stage(
    out_path: str | Path | None = None,
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "light",
    lead_text: str = "đối chiếu trực tiếp",
    hero_text: str = "khớp chuẩn 100%",
    watermark_text: str = "khớp chuẩn",
    tag_text: str = "SPECIMEN LAB // MATCH-CUT",
    plate_a_label: str = "input a",
    plate_b_label: str = "studio b",
    plate_a_image: str | Path | None = None,
    plate_b_image: str | Path | None = None,
    lock_cx: int | None = None,
    lock_cy: int | None = None,
    specimen_diameter: int = 280,
    crf: int = 17,
) -> dict[str, Any] | Iterator[np.ndarray]:
    sc = width / 1080.0
    eff_cx = int(lock_cx if lock_cx is not None else round(540 * sc))
    eff_cy = int(lock_cy if lock_cy is not None else round(920 * (height / 1920.0)))
    eff_r = int(round(specimen_diameter * 0.5 * sc))

    frame_gen = iter_concentric_lock_lab_stage(
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        theme=theme,
        polarity=polarity,
        lead_text=lead_text,
        hero_text=hero_text,
        watermark_text=watermark_text,
        tag_text=tag_text,
        plate_a_label=plate_a_label,
        plate_b_label=plate_b_label,
        plate_a_image=plate_a_image,
        plate_b_image=plate_b_image,
        lock_cx=eff_cx,
        lock_cy=eff_cy,
        specimen_diameter=specimen_diameter,
        output_color="rgb",
    )
    if out_path is None:
        return frame_gen
    enc = encode_frames_to_mp4(frame_gen, out_path, width=width, height=height, fps=fps, crf=crf, input_color="rgb")
    return {
        **enc,
        "stage": "concentric_lock_lab_stage",
        "theme": theme,
        "polarity": polarity,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
        "anchor_shape_xyr": {
            "cx_pct": round(eff_cx / float(width), 6),
            "cy_pct": round(eff_cy / float(height), 6),
            "r_pct_w": round(eff_r / float(width), 6),
            "cx_px": eff_cx,
            "cy_px": eff_cy,
            "r_px": eff_r,
            "shape": "circle",
        },
    }


# =============================================================================
# STAGE 3: `render_giant_numeral_3d_ui_stage` (`768893` Step 1/2/3 + 3D Tilted Prompt Window)
# =============================================================================

def _make_giant_numeral_hero_sprites(
    width: int,
    pal: dict[str, Any],
    numeral: str,
    lead_text: str,
    hero_text: str,
    scale: float = 1.0,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """
    Build separate z-layers for `768893` depth choreography:
      - Layer A (Back): Giant `210px` sculptural numeral (`1` / `2` / `3`) with metallic gradient & rim bevel.
      - Layer B (Front): Lowercase Sans lead + Bold/Italic hero overlapping across the numeral!
    """
    SS = 2
    W2 = int(width * SS)
    H2 = int(round(430 * scale * SS))
    is_light = pal["polarity"] == "light"
    acc = pal["accent"]

    # Layer A: Sculptural 210px Numeral
    num_im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    f_num = load_font("mont_black", int(round(215 * scale * SS)))
    num_str = nfc_clean(numeral) or "1"
    nw, nh, nbb = text_metrics(num_str, f_num)
    nx = W2 * 0.5 - nw * 0.5 - nbb[0] - int(round(135 * scale * SS))
    ny = int(round(165 * scale * SS)) - (nbb[1] + nbb[3]) * 0.5

    mask = Image.new("L", (W2, H2), 0)
    ImageDraw.Draw(mask).text((nx, ny), num_str, font=f_num, fill=255)

    # Vertical sculptural gradient inside numeral mask
    y_grad = np.linspace(0.0, 1.0, H2, dtype=np.float32)[:, None]
    grad_rgba = np.zeros((H2, W2, 4), dtype=np.uint8)
    top_c = acc if not is_light else pal["fg_hero"]
    bot_c = pal["card_bg"] if not is_light else pal["bg_edge"]
    for c_i in range(3):
        grad_rgba[:, :, c_i] = np.clip(top_c[c_i] * (1.0 - y_grad * 0.82) + bot_c[c_i] * (y_grad * 0.82), 0, 255).astype(np.uint8)
    m_np = np.asarray(mask, dtype=np.float32) * ((0.38 if is_light else 0.55))
    grad_rgba[:, :, 3] = np.clip(m_np, 0, 255).astype(np.uint8)
    num_im = Image.alpha_composite(num_im, Image.fromarray(grad_rgba, mode="RGBA"))

    # Crisp sculptural rim stroke on numeral
    rim_mask = mask.filter(ImageFilter.MaxFilter(5))
    rim_edge = Image.fromarray(np.clip(np.asarray(rim_mask, np.int16) - np.asarray(mask, np.int16), 0, 255).astype(np.uint8), mode="L")
    rim_layer = Image.new("RGBA", (W2, H2), _rgba(acc, 165 if is_light else 225))
    num_im.paste(rim_layer, (0, 0), rim_edge)

    # Layer B: Foreground Editorial Lead + Hero tucked over the giant numeral
    fg_im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg_im)
    f_lead = fit_font(nfc_clean(lead_text).lower(), "be_regular", int(W2 * 0.78), int(round(38 * scale * SS)), int(round(22 * scale * SS)))
    f_hero = fit_font(nfc_clean(hero_text).lower(), "be_italic", int(W2 * 0.84), int(round(84 * scale * SS)), int(round(44 * scale * SS)))

    text_cx = W2 * 0.5 + int(round(36 * scale * SS))
    lead_cy = int(round(142 * scale * SS))
    hero_cy = int(round(240 * scale * SS))

    # Soft occlusion backdrop behind text where it crosses the giant numeral
    occ = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    od = ImageDraw.Draw(occ)
    _draw_centered(od, text_cx, hero_cy, nfc_clean(hero_text).lower(), f_hero, _rgba(pal["bg_base"], 185), align_x="center")
    fg_im = Image.alpha_composite(fg_im, occ.filter(ImageFilter.GaussianBlur(radius=9 * scale * SS)))
    fd = ImageDraw.Draw(fg_im)

    _draw_centered(fd, text_cx, lead_cy, nfc_clean(lead_text).lower(), f_lead, _rgba(pal["fg_lead"], 248), align_x="center")
    _draw_centered(fd, text_cx, hero_cy, nfc_clean(hero_text).lower(), f_hero, _rgba(pal["fg_hero"], 255), align_x="center")

    num_1x = num_im.resize((width, H2 // SS), Image.Resampling.LANCZOS)
    fg_1x = fg_im.resize((width, H2 // SS), Image.Resampling.LANCZOS)
    return _rgba_to_premul(num_1x), _rgba_to_premul(fg_1x)


def iter_giant_numeral_3d_ui_stage(
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "obsidian_cyan_7688",
    polarity: str = "dark",
    numeral: str = "1",
    lead_text: str = "bước thứ nhất",
    hero_text: str = "khóa kết cấu",
    watermark_text: str = "mẫu prompt",
    window_title: str = "PROMPT STUDIO // V6.0",
    prompt_text: str = "Giữ nguyên kết cấu sản phẩm gốc, ánh sáng ven ấm 3200K, ống kính 85mm f/1.8, độ sâu trường ảnh điện ảnh --cref 1.0 --lock",
    rot_y_deg: float = -11.0,
    rot_x_deg: float = 5.0,
    output_color: str = "rgb",
) -> Iterator[np.ndarray]:
    """
    Stage 3 Generator (`768893` 24.2s-40.4s Step `1/2/3` + 3D Tilted Prompt Window):
      - Wavy 3D obsidian silk backdrop + giant `210px` sculptural numeral tucked behind lowercase lead + hero.
      - Below it, a 3D perspective-tilted (`cv2.warpPerspective`, `rotY=-11°, rotX=+5°`) dark glass prompt/UI
        window actively typing Vietnamese prompt tokens character-by-character with a glowing cursor + edge DoF!
    """
    sc = width / 1080.0
    pal = resolve_theme_palette(theme, polarity)
    is_light = pal["polarity"] == "light"
    rig = LivingBackdropRig(width, height, theme=theme, polarity=polarity, backdrop_mode="silk", watermark_text=watermark_text, seed=7688)

    (num_premul, num_a), (fg_premul, fg_a) = _make_giant_numeral_hero_sprites(width, pal, numeral, lead_text, hero_text, scale=sc)

    # Pre-wrap prompt text lines for clean 3D UI window typing
    ui_w = int(round(884 * sc))
    ui_h = int(round(520 * sc))
    f_win_hdr = load_font("mono_bold", int(round(16 * sc)))
    f_prompt = load_font("be_bold", int(round(26 * sc)))
    f_tag = load_font("mono_bold", int(round(15 * sc)))

    clean_prompt = nfc_clean(prompt_text)
    words = clean_prompt.split()
    wrapped_lines: list[str] = []
    max_txt_w = ui_w - int(round(96 * sc))
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if text_metrics(cand, f_prompt)[0] <= max_txt_w:
            cur = cand
        else:
            if cur:
                wrapped_lines.append(cur)
            cur = w
    if cur:
        wrapped_lines.append(cur)
    wrapped_lines = wrapped_lines[:5]
    full_joined = "\n".join(wrapped_lines)
    total_chars = max(1, len(full_joined))

    # Pre-render static dark-glass prompt window shell (even in light cream polarity, a dark smoked studio UI glass card has huge editorial contrast!)
    win_bg_top = (14, 20, 30) if not is_light else (18, 28, 24)
    win_bg_bot = (9, 13, 21) if not is_light else (12, 20, 17)
    acc = pal["accent"] if not is_light else _hex_rgb("#34D399")

    shell = Image.new("RGBA", (ui_w, ui_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shell)
    rad = int(round(26 * sc))
    sd.rounded_rectangle((2, 2, ui_w - 3, ui_h - 3), radius=rad, fill=_rgba(win_bg_top, 242), outline=_rgba(acc, 205), width=max(2, int(round(2.2 * sc))))
    tb_h = int(round(62 * sc))
    sd.rounded_rectangle((4, 4, ui_w - 5, tb_h), radius=rad - 2, fill=(22, 31, 44, 255))
    sd.line([(4, tb_h), (ui_w - 5, tb_h)], fill=_rgba(acc, 95), width=max(1, int(sc)))
    for d_i, d_col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        dcx = int(round((32 + d_i * 22) * sc))
        dcy = tb_h // 2
        dr = int(round(6.5 * sc))
        sd.ellipse((dcx - dr, dcy - dr, dcx + dr, dcy + dr), fill=_rgba(d_col, 240))
    _draw_centered(sd, 108 * sc, tb_h * 0.5, nfc_clean(window_title), f_win_hdr, (212, 224, 238, 240), align_x="left")
    draw_vector_glyph(sd, "spark", ui_w - 38 * sc, tb_h * 0.5, 12 * sc, acc, alpha=245)

    # Bottom parameter pills inside prompt window
    pill_y = ui_h - int(round(64 * sc))
    px_cur = int(round(38 * sc))
    for p_txt, p_icon in (("LOCK STRUCTURE", "padlock"), ("85MM F/1.8", "aperture"), ("RAW 4K", "spark")):
        tw_p, _, _ = text_metrics(p_txt, f_tag)
        pw_p = tw_p + int(round(54 * sc))
        sd.rounded_rectangle((px_cur, pill_y, px_cur + pw_p, pill_y + int(36 * sc)), radius=int(round(18 * sc)), fill=_rgba(acc, 34), outline=_rgba(acc, 155), width=max(1, int(sc)))
        draw_vector_glyph(sd, p_icon, px_cur + 20 * sc, pill_y + 18 * sc, 9 * sc, acc, alpha=245)
        _draw_centered(sd, px_cur + 36 * sc, pill_y + 18 * sc, p_txt, f_tag, _rgba(acc, 245), align_x="left")
        px_cur += pw_p + int(round(14 * sc))

    # Horizontal edge Depth-of-Field ramp (receding right/bottom edge gets subtle cinema prime lens blur)
    dof_ramp = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    dof_weight = np.clip((dof_ramp - 0.68) / 0.30, 0.0, 1.0)[:, :, None] * 0.72

    n_frames = max(1, int(round(duration_sec * fps)))
    frame_f32 = np.zeros((height, width, 3), dtype=np.float32)

    for idx in range(n_frames):
        t = idx / max(1.0, float(fps))
        u = idx / max(1, n_frames - 1) if n_frames > 1 else 0.6

        rig.render_into(frame_f32, t, u, watermark_cy_pct=0.28)

        # Parallax z-layered giant numeral (back) + editorial headline (front)
        enter = smooth_window(t, 0.0, min(0.36, duration_sec * 0.30))
        num_dx = -10.0 * sc * (u - 0.5)
        fg_dx = +6.0 * sc * (u - 0.5)
        hdr_base_y = height * 0.13 + (1.0 - enter) * (-16.0 * sc)
        _blend_premul_roi(frame_f32, num_premul, num_a, num_dx, hdr_base_y, opacity=0.45 + 0.55 * enter)
        _blend_premul_roi(frame_f32, fg_premul, fg_a, fg_dx, hdr_base_y, opacity=0.40 + 0.60 * enter)

        # Active character-by-character Vietnamese typing inside UI card
        n_vis = max(6, min(total_chars, int(round((0.18 + 0.82 * cubic_bezier(min(1.0, u * 1.12), 0.20, 0.65, 0.35, 1.00)) * total_chars))))
        vis_sub = full_joined[:n_vis]
        vis_lines = vis_sub.split("\n")

        card_im = shell.copy()
        cd = ImageDraw.Draw(card_im)
        tx0 = int(round(42 * sc))
        ty = tb_h + int(round(56 * sc))
        line_step = int(round(52 * sc))
        cursor_x, cursor_cy = float(tx0), float(ty)

        for li, ln_str in enumerate(vis_lines):
            # Highlight `--` flags in accent color
            if "--" in ln_str:
                main_part, flag_part = ln_str.split("--", 1)
                w_m, _ = _draw_centered(cd, tx0, ty, main_part, f_prompt, (244, 248, 252, 255), align_x="left")
                sp = int(round(8 * sc)) if main_part else 0
                w_f, _ = _draw_centered(cd, tx0 + w_m + sp, ty, "--" + flag_part, f_prompt, _rgba(acc, 255), align_x="left")
                cursor_x = tx0 + w_m + sp + w_f + 6 * sc
            else:
                w_ln, _ = _draw_centered(cd, tx0, ty, ln_str, f_prompt, (244, 248, 252, 255), align_x="left")
                cursor_x = tx0 + w_ln + 6 * sc
            cursor_cy = float(ty)
            ty += line_step

        # Glowing animated typing cursor bar
        cur_pulse = int(round(165 + 90 * (0.5 + 0.5 * math.sin(t * 14.0))))
        cur_w = max(3, int(round(4 * sc)))
        cur_h = int(round(30 * sc))
        cd.rounded_rectangle(
            (cursor_x, cursor_cy - cur_h * 0.5, cursor_x + cur_w, cursor_cy + cur_h * 0.5),
            radius=max(1, cur_w // 2),
            fill=_rgba(acc, cur_pulse),
        )

        # 3D Perspective Tilt (`cv2.warpPerspective`, `rotY=-11°, rotX=+5°` + gentle breathing) into tight vertical ROI
        eff_ry = rot_y_deg + 1.4 * math.sin(t * 1.1)
        eff_rx = rot_x_deg + 0.9 * math.cos(t * 0.9)
        dst_cx = width * 0.50
        dst_cy = height * 0.59 + (1.0 - enter) * (26.0 * sc)
        band_y0 = max(0, int(round(dst_cy - ui_h * 0.68)))
        band_y1 = min(height, int(round(dst_cy + ui_h * 0.72)))
        band_h = max(16, band_y1 - band_y0)

        H_mat = compute_3d_perspective_homography(
            ui_w, ui_h, dst_cx, dst_cy - band_y0, rot_y_deg=eff_ry, rot_x_deg=eff_rx, focal_px=1380.0 * sc, zoom=0.96 + 0.04 * enter
        )

        c_premul, c_a = _rgba_to_premul(card_im)
        pack = np.concatenate([c_premul, c_a], axis=2)
        warped = cv2.warpPerspective(
            pack,
            H_mat,
            (width, band_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )

        # Subtle optical Edge Depth-of-Field on receding right perspective edge (in-place on ROI)
        blurred_warped = cv2.GaussianBlur(warped, (0, 0), sigmaX=max(1.2, 3.2 * sc))
        warped *= 1.0 - dof_weight
        warped += blurred_warped * dof_weight

        # Soft 3D ground shadow beneath tilted window
        sh_a = cv2.GaussianBlur(warped[:, :, 3], (0, 0), sigmaX=max(4.0, 16.0 * sc))
        dy_sh = int(round(20 * sc))
        roi_dst = frame_f32[band_y0:band_y1]
        if dy_sh < band_h:
            sh_scale = 0.22 if is_light else 0.55
            roi_dst[dy_sh:] *= 1.0 - (sh_a[: band_h - dy_sh, :, None] * sh_scale)

        w_a = warped[:, :, 3:4]
        roi_dst *= 1.0 - w_a
        roi_dst += warped[:, :, :3]

        u8 = np.clip(frame_f32, 0.0, 255.0).astype(np.uint8)
        yield u8[:, :, ::-1] if output_color.lower() == "bgr" else u8


def render_giant_numeral_3d_ui_stage(
    out_path: str | Path | None = None,
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "obsidian_cyan_7688",
    polarity: str = "dark",
    numeral: str = "1",
    lead_text: str = "bước thứ nhất",
    hero_text: str = "khóa kết cấu",
    watermark_text: str = "mẫu prompt",
    window_title: str = "PROMPT STUDIO // V6.0",
    prompt_text: str = "Giữ nguyên kết cấu sản phẩm gốc, ánh sáng ven ấm 3200K, ống kính 85mm f/1.8, độ sâu trường ảnh điện ảnh --cref 1.0 --lock",
    rot_y_deg: float = -11.0,
    rot_x_deg: float = 5.0,
    crf: int = 17,
) -> dict[str, Any] | Iterator[np.ndarray]:
    frame_gen = iter_giant_numeral_3d_ui_stage(
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        theme=theme,
        polarity=polarity,
        numeral=numeral,
        lead_text=lead_text,
        hero_text=hero_text,
        watermark_text=watermark_text,
        window_title=window_title,
        prompt_text=prompt_text,
        rot_y_deg=rot_y_deg,
        rot_x_deg=rot_x_deg,
        output_color="rgb",
    )
    if out_path is None:
        return frame_gen
    enc = encode_frames_to_mp4(frame_gen, out_path, width=width, height=height, fps=fps, crf=crf, input_color="rgb")
    return {
        **enc,
        "stage": "giant_numeral_3d_ui_stage",
        "theme": theme,
        "polarity": polarity,
        "numeral": numeral,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
        "anchor_shape_xyr": {
            "cx_pct": 0.50,
            "cy_pct": 0.59,
            "r_pct_w": 0.41,
            "cx_px": width // 2,
            "cy_px": int(round(height * 0.59)),
            "r_px": int(round(width * 0.41)),
            "shape": "tilted_3d_window",
        },
    }


# =============================================================================
# STAGE 4: `render_bento_kinetic_matrix_stage` (`770765` 20.4s 3D Tile Matrix)
# =============================================================================

def _make_matrix_tile_pair(
    tile_w: int,
    tile_h: int,
    num_code: str,
    title: str,
    sub: str,
    icon_kind: str,
    pal: dict[str, Any],
    accent_rgb: tuple[int, int, int],
    is_pillar: bool,
    scale: float,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
    """Pre-render `(inactive_32pct_tile, active_100pct_glow_tile)` for the 3D Bento Kinetic Matrix."""
    SS = 2
    pad = int(round(16 * scale * SS))
    W2 = tile_w * SS + pad * 2
    H2 = tile_h * SS + pad * 2
    is_light = pal["polarity"] == "light"
    rad = int(round(22 * scale * SS))

    f_num = load_font("mono_bold", int(round(16 * scale * SS)))
    f_title = fit_font(nfc_clean(title), "be_extrabold", tile_w * SS - int(36 * scale * SS), int(round(24 * scale * SS)), int(round(16 * scale * SS)))
    f_sub = fit_font(nfc_clean(sub), "be_regular", tile_w * SS - int(36 * scale * SS), int(round(16 * scale * SS)), int(round(12 * scale * SS)))

    def _build(active: bool) -> tuple[np.ndarray, np.ndarray]:
        im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        x0, y0 = pad, pad
        x1, y1 = pad + tile_w * SS, pad + tile_h * SS

        if active:
            gl = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
            ImageDraw.Draw(gl).rounded_rectangle(
                (x0 - 2 * SS, y0 - 2 * SS, x1 + 2 * SS, y1 + 2 * SS),
                radius=rad + 2 * SS,
                outline=_rgba(accent_rgb, 130 if is_light else 185),
                width=int(round(5 * scale * SS)),
            )
            im = Image.alpha_composite(im, gl.filter(ImageFilter.GaussianBlur(radius=8 * scale * SS)))

        d = ImageDraw.Draw(im)
        bg_a = (242 if is_light else 238) if active else (112 if is_light else 88)
        out_a = 245 if active else (58 if is_light else 64)
        d.rounded_rectangle(
            (x0, y0, x1, y1),
            radius=rad,
            fill=_rgba(pal["card_bg"], bg_a),
            outline=_rgba(accent_rgb if (active or is_pillar) else pal["fg_muted"], out_a),
            width=max(2, int(round((2.6 if active else 1.3) * scale * SS))),
        )

        fg_alpha = 255 if active else 92
        ic_alpha = 255 if active else 82
        _draw_centered(d, x0 + int(22 * scale * SS), y0 + int(28 * scale * SS), num_code, f_num, _rgba(accent_rgb if active else pal["fg_muted"], fg_alpha), align_x="left")
        draw_vector_glyph(
            d,
            icon_kind,
            x1 - int(30 * scale * SS),
            y0 + int(28 * scale * SS),
            12 * scale * SS,
            accent_rgb if active else pal["fg_muted"],
            alpha=ic_alpha,
            badge_bg_alpha=36 if active else 0,
        )

        _draw_centered(d, x0 + int(22 * scale * SS), y1 - int(56 * scale * SS), nfc_clean(title), f_title, _rgba(pal["fg_hero"], fg_alpha), align_x="left")
        _draw_centered(d, x0 + int(22 * scale * SS), y1 - int(25 * scale * SS), nfc_clean(sub), f_sub, _rgba(pal["fg_lead"], int(fg_alpha * 0.88)), align_x="left")

        down = im.resize((W2 // SS, H2 // SS), Image.Resampling.LANCZOS)
        return _rgba_to_premul(down)

    inact_pair = _build(False)
    return inact_pair, (_build(True) if is_pillar else inact_pair)


def iter_bento_kinetic_matrix_stage(
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "dark",
    lead_text: str = "hệ thống 3 trụ cột",
    hero_text: str = "chuẩn điện ảnh",
    watermark_text: str = "ánh sáng",
    tag_text: str = "KINETIC MATRIX // 01 · 02 · 03",
    pillars: Sequence[dict[str, Any]] | None = None,
    output_color: str = "rgb",
) -> Iterator[np.ndarray]:
    """
    Stage 4 Generator (`770765` 20.4s 3D Tile Matrix & Swiss `01/02/03` Specimen Stage):
      - Full-screen curved/perspective 3D grid of frosted tiles (`3x3` architectural matrix)
        where the 3 workflow pillars light up sequentially (`active tile 100%` crisp glow + z-lift
        while inactive tiles sit at `32%` depth), zero static PowerPoint rectangle look!
    """
    sc = width / 1080.0
    pal = resolve_theme_palette(theme, polarity)
    rig = LivingBackdropRig(width, height, theme=theme, polarity=polarity, backdrop_mode="aurora", watermark_text=watermark_text, seed=2040)
    hdr_premul, hdr_a = _make_editorial_header_sprite(width, pal, tag_text, lead_text, hero_text, icon_kind="spark", scale=sc)

    if not pillars:
        pillars = [
            {"code": "01", "title": "KHÓA KẾT CẤU", "sub": "Giữ chuẩn form gốc", "icon": "padlock"},
            {"code": "02", "title": "ÁNH SÁNG VEN", "sub": "Tách lớp chiều sâu", "icon": "spark"},
            {"code": "03", "title": "TIÊU CỰ 85MM", "sub": "Quang học điện ảnh", "icon": "aperture"},
        ]

    # 3x3 curved/perspective matrix: middle diagonal / staggered cells host the 3 hero pillars, surrounded by 6 context specimen tiles!
    context_specs = [
        ("A0", "RAW INPUT", "24-bit color", "aperture"),
        ("A2", "LUMA CURVE", "Contrast S-log", "arrow"),
        ("B0", "EDGE MATTE", "Sub-pixel alpha", "spark"),
        ("B2", "COLOR LOCK", "Delta < 0.2%", "padlock"),
        ("C0", "MOTION BLUR", "180° shutter", "arrow"),
        ("C1", "MASTER 4K", "60fps H.264", "check"),
    ]
    pillar_slots = [(0, 1), (1, 1), (2, 2)]  # Staggered diagonal eye-trace across the 3x3 matrix!
    acc_cycle = [pal["accent"], pal["accent_2"], pal["accent_3"]]

    tile_w = int(round(304 * sc))
    tile_h = int(round(196 * sc))
    gap_x = int(round(22 * sc))
    gap_y = int(round(22 * sc))

    plane_w = int(round(992 * sc))
    plane_h = int(round(672 * sc))
    grid_w = tile_w * 3 + gap_x * 2
    grid_h = tile_h * 3 + gap_y * 2
    gx0 = (plane_w - grid_w) * 0.5
    gy0 = (plane_h - grid_h) * 0.5

    cells: list[dict[str, Any]] = []
    ctx_idx = 0
    for r_i in range(3):
        for c_i in range(3):
            if (r_i, c_i) in pillar_slots:
                p_idx = pillar_slots.index((r_i, c_i))
                p_item = pillars[min(p_idx, len(pillars) - 1)]
                inact, act = _make_matrix_tile_pair(
                    tile_w,
                    tile_h,
                    str(p_item.get("code", f"0{p_idx+1}")),
                    str(p_item.get("title", f"TRỤ CỘT {p_idx+1}")),
                    str(p_item.get("sub", "Chuẩn studio")),
                    str(p_item.get("icon", "spark")),
                    pal,
                    acc_cycle[p_idx % 3],
                    is_pillar=True,
                    scale=sc,
                )
                cells.append({"r": r_i, "c": c_i, "pillar_idx": p_idx, "inact": inact, "act": act})
            else:
                cc, ct, cs, ci = context_specs[ctx_idx % len(context_specs)]
                ctx_idx += 1
                inact, act = _make_matrix_tile_pair(
                    tile_w, tile_h, cc, ct, cs, ci, pal, pal["fg_muted"], is_pillar=False, scale=sc
                )
                cells.append({"r": r_i, "c": c_i, "pillar_idx": -1, "inact": inact, "act": act})

    # Precompute subtle cylindrical barrel lens curve LUT using compact 1D broadcasting (< 6.8 MB)
    nx = np.linspace(-1.0, 1.0, plane_w, dtype=np.float32)[None, :]
    ny = np.linspace(-1.0, 1.0, plane_h, dtype=np.float32)[:, None]
    r2_curve = nx * nx * 0.055 + ny * ny * 0.032
    map_x = (plane_w * 0.5 + nx * (1.0 + r2_curve) * (plane_w * 0.5)).astype(np.float32)
    map_y = (plane_h * 0.5 + ny * (1.0 + r2_curve) * (plane_h * 0.5)).astype(np.float32)
    del r2_curve, nx, ny

    f_prog = load_font("mono_bold", int(round(16 * sc)))
    n_frames = max(1, int(round(duration_sec * fps)))
    frame_f32 = np.zeros((height, width, 3), dtype=np.float32)
    plane_rgba = np.zeros((plane_h, plane_w, 4), dtype=np.float32)
    curved_buf = np.zeros((plane_h, plane_w, 4), dtype=np.float32)
    mat_cy = height * 0.57
    band_y0 = max(0, int(round(mat_cy - plane_h * 0.62)))
    band_y1 = min(height, int(round(mat_cy + plane_h * 0.62)))
    band_h = max(32, band_y1 - band_y0)
    warped_buf = np.zeros((band_h, width, 4), dtype=np.float32)

    for idx in range(n_frames):
        t = idx / max(1.0, float(fps))
        u = idx / max(1, n_frames - 1) if n_frames > 1 else 0.5

        rig.render_into(frame_f32, t, u, watermark_cy_pct=0.56)

        enter = smooth_window(t, 0.0, min(0.35, duration_sec * 0.28))
        _blend_premul_roi(frame_f32, hdr_premul, hdr_a, 0.0, height * 0.11 + (1.0 - enter) * (-15.0 * sc), opacity=0.35 + 0.65 * enter)

        # Smooth sequential pillar activation (`0 -> 1 -> 2` across `u` in `[0..1]`)
        stage_pos = u * 2.999
        active_p = min(2, int(stage_pos))

        plane_rgba.fill(0.0)
        pad_px = int(round(16 * sc))

        # Draw inactive/context tiles first, then active glowing tile on top with 1.05x z-lift!
        ordered_cells = sorted(cells, key=lambda item: 1 if item["pillar_idx"] == active_p else 0)
        for cell in ordered_cells:
            tx = gx0 + cell["c"] * (tile_w + gap_x) - pad_px
            ty = gy0 + cell["r"] * (tile_h + gap_y) - pad_px
            p_i = cell["pillar_idx"]
            if p_i < 0:
                # Context matrix tiles sit at crisp 32% depth!
                _blend_premul_roi(plane_rgba, cell["inact"][0], cell["inact"][1], tx, ty, opacity=0.32)
            else:
                dist_act = abs((u * 2.4 - 0.2) - p_i * 0.95)
                act_w = 1.0 if p_i == active_p else max(0.0, 1.0 - dist_act * 2.2)
                if act_w < 0.5:
                    _blend_premul_roi(plane_rgba, cell["inact"][0], cell["inact"][1], tx, ty, opacity=0.36)
                else:
                    lift_scale = 1.045
                    _blend_premul_roi(plane_rgba, cell["act"][0], cell["act"][1], tx, ty, opacity=1.0, scale=lift_scale)

        cv2.remap(plane_rgba, map_x, map_y, interpolation=cv2.INTER_LINEAR, dst=curved_buf, borderMode=cv2.BORDER_CONSTANT)

        # Perspective 3D camera drift across the curved tile matrix (tight vertical band ROI)
        ry = -7.5 + 15.0 * (u - 0.5)
        rx = 8.5 - 3.0 * math.sin(u * math.pi)
        rz = -1.6 + 3.2 * u

        H_mat = compute_3d_perspective_homography(
            plane_w, plane_h, width * 0.50, mat_cy - band_y0, rot_y_deg=ry, rot_x_deg=rx, rot_z_deg=rz, focal_px=1320.0 * sc, zoom=0.98 + 0.04 * enter
        )
        warped_buf.fill(0.0)
        cv2.warpPerspective(
            curved_buf,
            H_mat,
            (width, band_h),
            dst=warped_buf,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
        w_a = np.clip(warped_buf[:, :, 3:4], 0.0, 1.0)
        roi_dst = frame_f32[band_y0:band_y1]
        roi_dst *= 1.0 - w_a
        np.add(roi_dst, warped_buf[:, :, :3], out=roi_dst)

        # Bottom Swiss `01 ──●── 02 ───── 03` CAD indicator
        hud = Image.new("RGBA", (width, int(round(120 * sc))), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hud)
        cy_bar = 60.0 * sc
        xs_nodes = [width * 0.28, width * 0.50, width * 0.72]
        hd.line([(xs_nodes[0], cy_bar), (xs_nodes[-1], cy_bar)], fill=_rgba(pal["fg_muted"], 90), width=max(2, int(round(2 * sc))))
        for ni, nx_p in enumerate(xs_nodes):
            is_on = ni == active_p
            c_node = acc_cycle[ni % 3] if is_on else pal["fg_muted"]
            nr = (18.0 if is_on else 13.0) * sc
            hd.ellipse((nx_p - nr, cy_bar - nr, nx_p + nr, cy_bar + nr), fill=_rgba(pal["card_bg"], 235), outline=_rgba(c_node, 245 if is_on else 110), width=max(2, int(round(2 * sc))))
            _draw_centered(hd, nx_p, cy_bar, f"0{ni+1}", f_prog, _rgba(c_node, 255 if is_on else 130), align_x="center")

        h_premul, h_a = _rgba_to_premul(hud)
        _blend_premul_roi(frame_f32, h_premul, h_a, 0.0, height * 0.85, opacity=1.0)

        u8 = np.clip(frame_f32, 0.0, 255.0).astype(np.uint8)
        yield u8[:, :, ::-1] if output_color.lower() == "bgr" else u8


def render_bento_kinetic_matrix_stage(
    out_path: str | Path | None = None,
    duration_sec: float = 2.4,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    theme: str = "emerald_cream_7707",
    polarity: str = "dark",
    lead_text: str = "hệ thống 3 trụ cột",
    hero_text: str = "chuẩn điện ảnh",
    watermark_text: str = "ánh sáng",
    tag_text: str = "KINETIC MATRIX // 01 · 02 · 03",
    pillars: Sequence[dict[str, Any]] | None = None,
    crf: int = 17,
) -> dict[str, Any] | Iterator[np.ndarray]:
    frame_gen = iter_bento_kinetic_matrix_stage(
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        theme=theme,
        polarity=polarity,
        lead_text=lead_text,
        hero_text=hero_text,
        watermark_text=watermark_text,
        tag_text=tag_text,
        pillars=pillars,
        output_color="rgb",
    )
    if out_path is None:
        return frame_gen
    enc = encode_frames_to_mp4(frame_gen, out_path, width=width, height=height, fps=fps, crf=crf, input_color="rgb")
    return {
        **enc,
        "stage": "bento_kinetic_matrix_stage",
        "theme": theme,
        "polarity": polarity,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": duration_sec,
        "anchor_shape_xyr": {
            "cx_pct": 0.50,
            "cy_pct": 0.57,
            "r_pct_w": 0.43,
            "cx_px": width // 2,
            "cy_px": int(round(height * 0.57)),
            "r_px": int(round(width * 0.43)),
            "shape": "curved_3d_matrix",
        },
    }


# =============================================================================
# Registry, Unified Dispatcher & Self-Test Suite
# =============================================================================

CANVAS_STAGE_FUNCTIONS = {
    "timeline_playhead_stage": render_timeline_playhead_stage,
    "render_timeline_playhead_stage": render_timeline_playhead_stage,
    "concentric_lock_lab_stage": render_concentric_lock_lab_stage,
    "render_concentric_lock_lab_stage": render_concentric_lock_lab_stage,
    "giant_numeral_3d_ui_stage": render_giant_numeral_3d_ui_stage,
    "render_giant_numeral_3d_ui_stage": render_giant_numeral_3d_ui_stage,
    "bento_kinetic_matrix_stage": render_bento_kinetic_matrix_stage,
    "render_bento_kinetic_matrix_stage": render_bento_kinetic_matrix_stage,
}

CANVAS_STAGE_SCHEMAS: list[dict[str, Any]] = [
    {
        "kind": "timeline_playhead_stage",
        "function": "render_timeline_playhead_stage",
        "default_polarity": "dark",
        "description": "3D glassmorphic timeline/workflow console (`00:00..00:05`, color-coded track blocks, pulsing waveform bars, live scrubbing playhead needle, and optional `polarity_flip_at_t` 1x->24x X/iris inversion).",
        "optional": {
            "duration_sec": 2.4,
            "fps": 60,
            "theme": "emerald_cream_7707",
            "polarity": "dark",
            "lead_text": "quy trình 3 bước",
            "hero_text": "khóa kết cấu,",
            "watermark_text": "khóa ảnh",
            "polarity_flip_at_t": None,
            "flip_shape": "x",
        },
    },
    {
        "kind": "concentric_lock_lab_stage",
        "function": "render_concentric_lock_lab_stage",
        "default_polarity": "light",
        "description": "Warm Mint-Cream `#EEF4EA` Match-Cut Lab: two frosted specimen plates (`input a` & `studio b`) gliding horizontally along `cy=920` to lock concentrically at `(540, 920)` with pulsing `[ + ]` reticle and exact `anchor_shape_xyr`.",
        "optional": {
            "duration_sec": 2.4,
            "fps": 60,
            "theme": "emerald_cream_7707",
            "polarity": "light",
            "lead_text": "đối chiếu trực tiếp",
            "hero_text": "khớp chuẩn 100%",
            "watermark_text": "khớp chuẩn",
            "plate_a_label": "input a",
            "plate_b_label": "studio b",
            "specimen_diameter": 280,
        },
    },
    {
        "kind": "giant_numeral_3d_ui_stage",
        "function": "render_giant_numeral_3d_ui_stage",
        "default_polarity": "dark",
        "description": "Wavy 3D obsidian silk backdrop + giant `210px` sculptural numeral (`1`/`2`/`3`) tucked behind editorial lead/hero + `rotY=-11°, rotX=+5°` 3D glass prompt window typing Vietnamese tokens with glowing cursor & edge DoF.",
        "optional": {
            "duration_sec": 2.4,
            "fps": 60,
            "theme": "obsidian_cyan_7688",
            "polarity": "dark",
            "numeral": "1",
            "lead_text": "bước thứ nhất",
            "hero_text": "khóa kết cấu",
            "watermark_text": "mẫu prompt",
            "rot_y_deg": -11.0,
            "rot_x_deg": 5.0,
        },
    },
    {
        "kind": "bento_kinetic_matrix_stage",
        "function": "render_bento_kinetic_matrix_stage",
        "default_polarity": "dark",
        "description": "Full-screen curved/perspective 3D grid of frosted tiles where the 3 workflow pillars light up sequentially (`100%` active glow + z-lift vs `32%` inactive depth).",
        "optional": {
            "duration_sec": 2.4,
            "fps": 60,
            "theme": "emerald_cream_7707",
            "polarity": "dark",
            "lead_text": "hệ thống 3 trụ cột",
            "hero_text": "chuẩn điện ảnh",
            "watermark_text": "ánh sáng",
        },
    },
]


def render_motion_canvas(stage: str, out_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Unified dispatcher called by Python or `visual_blocks.py --canvas`."""
    key = str(stage or "").strip()
    if key not in CANVAS_STAGE_FUNCTIONS:
        raise ValueError(f"Unknown motion canvas stage={key!r}. Valid: {sorted(s['kind'] for s in CANVAS_STAGE_SCHEMAS)}")
    res = CANVAS_STAGE_FUNCTIONS[key](out_path=out_path, **kwargs)
    assert isinstance(res, dict)
    return res


def _extract_middle_frame_png(mp4_path: Path, png_path: Path, t_sec: float = 0.75) -> None:
    cmd = [
        _resolve_ffmpeg(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{t_sec:.3f}",
        "-i",
        str(mp4_path),
        "-frames:v",
        "1",
        str(png_path),
    ]
    subprocess.run(cmd, check=True, timeout=FFMPEG_TIMEOUT_S)


def run_self_test(out_dir: str | Path = "/tmp/test_v60_canvases", duration_sec: float = 1.5, fps: int = 30) -> dict[str, Any]:
    """Render 1.5s `.mp4` clips + extract middle PNG frames for all 4 stages in BOTH `dark` and `light` `#EEF4EA` polarity."""
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    matrix = [
        ("timeline_playhead_stage", "emerald_cream_7707", "dark", {"polarity_flip_at_t": 0.68, "flip_shape": "x", "watermark_text": "khóa ảnh"}),
        ("timeline_playhead_stage", "emerald_cream_7707", "light", {"watermark_text": "giả trân", "lead_text": "loại bỏ lỗi", "hero_text": "3 bước chuẩn,"}),
        ("concentric_lock_lab_stage", "emerald_cream_7707", "dark", {"watermark_text": "khớp hình"}),
        ("concentric_lock_lab_stage", "emerald_cream_7707", "light", {"watermark_text": "khớp chuẩn"}),
        ("giant_numeral_3d_ui_stage", "obsidian_cyan_7688", "dark", {"numeral": "1", "watermark_text": "khóa ảnh"}),
        ("giant_numeral_3d_ui_stage", "emerald_cream_7707", "light", {"numeral": "2", "lead_text": "lấy ngay bộ", "hero_text": "mẫu prompt", "watermark_text": "ánh sáng"}),
        ("bento_kinetic_matrix_stage", "violet_aurora_7693", "dark", {"watermark_text": "ánh sáng"}),
        ("bento_kinetic_matrix_stage", "emerald_cream_7707", "light", {"watermark_text": "khớp hình"}),
    ]

    tracemalloc.start()
    max_stage_alloc_mb = 0.0
    outputs: list[dict[str, Any]] = []
    for stage_name, thm, pol, extra in matrix:
        load_font.cache_clear()
        gc.collect()
        tracemalloc.reset_peak()
        stem = f"{stage_name}__{pol}"
        mp4_p = base / f"{stem}.mp4"
        png_p = base / f"{stem}_mid.png"
        meta = render_motion_canvas(stage_name, mp4_p, duration_sec=duration_sec, fps=fps, theme=thm, polarity=pol, **extra)
        _cur_b, peak_b = tracemalloc.get_traced_memory()
        stage_alloc_mb = round(peak_b / (1024.0 * 1024.0), 2)
        max_stage_alloc_mb = max(max_stage_alloc_mb, stage_alloc_mb)
        meta["peak_streaming_ram_mb"] = stage_alloc_mb
        # For timeline dark with flip at 0.68s, also extract pre-flip (0.45s) and mid-flip (0.80s)
        _extract_middle_frame_png(mp4_p, png_p, t_sec=duration_sec * 0.52)
        if extra.get("polarity_flip_at_t"):
            pre_png = base / f"{stem}_preflip.png"
            flip_png = base / f"{stem}_midflip.png"
            _extract_middle_frame_png(mp4_p, pre_png, t_sec=0.42)
            _extract_middle_frame_png(mp4_p, flip_png, t_sec=float(extra["polarity_flip_at_t"]) + 0.14)
            meta["preflip_png"] = str(pre_png)
            meta["midflip_png"] = str(flip_png)
        meta["mid_png"] = str(png_p)
        outputs.append(meta)
    tracemalloc.stop()

    peak_rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
    summary = {
        "ok": True,
        "version": "6.0",
        "out_dir": str(base),
        "rendered_count": len(outputs),
        "peak_streaming_ram_mb": max_stage_alloc_mb,
        "peak_rss_mb": peak_rss_mb,
        "ram_budget_pass": max_stage_alloc_mb < 150.0,
        "outputs": outputs,
    }
    (base / "self_test_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _cli(argv: Sequence[str] | None = None) -> int:
    eff = list(sys.argv[1:] if argv is None else argv)
    if not eff or "--self-test" in eff:
        rep = run_self_test()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="DVIET Full-Screen Living Motion-Design Canvas Engine (v7.9.1)")
    parser.add_argument("--list", action="store_true", help="Print JSON catalog of all 4 animated stage generators and themes")
    parser.add_argument("--stage", help="Stage name (`timeline_playhead_stage`, `concentric_lock_lab_stage`, `giant_numeral_3d_ui_stage`, `bento_kinetic_matrix_stage`)")
    parser.add_argument("--spec", default="{}", help="Inline JSON object or path to JSON spec file")
    parser.add_argument("-o", "--output", help="Output `.mp4` path")
    args = parser.parse_args(eff)

    if args.list:
        print(
            json.dumps(
                {
                    "version": "6.0",
                    "themes": list(COLOR_WORLD_THEMES.keys()),
                    "polarities": ["dark", "light"],
                    "motion_canvases": CANVAS_STAGE_SCHEMAS,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not args.stage or not args.output:
        parser.error("Provide --stage and -o/--output (or run without args / --self-test).")

    raw_spec = str(args.spec or "{}").strip()
    if raw_spec.endswith(".json") and Path(raw_spec).is_file():
        spec_dict = json.loads(Path(raw_spec).read_text(encoding="utf-8"))
    else:
        spec_dict = json.loads(raw_spec)
    res = render_motion_canvas(args.stage, args.output, **spec_dict)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
