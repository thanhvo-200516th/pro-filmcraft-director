#!/usr/bin/env python3
"""
Stateless Multi-Style Visual Primitives, Living Motion Canvases & B-Roll Hygiene (`visual_blocks.py` `v6.0`)
============================================================================================================
Provides 13 crisp, 2x-supersampled RGBA/RGB primitives (zero system color emojis — 100% anti-aliased
vector geometric icons: padlock, arrow/spark, aperture) PLUS 4 full-screen living `.mp4` Motion-Design
Canvases (`dviet_motion_canvas_engine.py` `v6.0`), `anchor_shape_xyr` match-cut telemetry, B-roll
border/flatness hygiene, 46-token anti-slop prompt linting, and automatic metadata stripping.

Callable individually from Python OR via CLI:
  python3 scripts/tools/visual_blocks.py --list
  python3 scripts/tools/visual_blocks.py render --spec blocks.json
  python3 scripts/tools/visual_blocks.py --canvas concentric_lock_lab_stage --spec '{...}' -o stage.mp4
  python3 scripts/tools/visual_blocks.py render-canvas concentric_lock_lab_stage --spec '{...}' -o stage.mp4
  python3 scripts/tools/visual_blocks.py lint-prompt "..."

Primitives (PNG/RGB) & Living Stages (MP4):
   1. versus_split_card(...)             8. polaroid_callout(...)
   2. flowchart_pipeline(...)            9. floating_pill_badge(...)
   3. metric_kpi_hero(...)              10. clean_alpha_prop(...)
   4. code_terminal_window(...)         11. clean_broll_plate(...)
   5. checklist_audit_card(...)         12. viewfinder_raw_card(...)
   6. quote_editorial_note(...)         13. compact_glass_lock_badge(...)
   7. strike_myth_banner(...)
  +4 Animated Full-Screen Stages:
   - timeline_playhead_stage          - concentric_lock_lab_stage
   - giant_numeral_3d_ui_stage        - bento_kinetic_matrix_stage
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    try:
        import cv2 as _cv2_probe  # noqa: F401
        import numpy as _np_probe  # noqa: F401
        from PIL import Image as _pil_probe  # noqa: F401
    except ImportError:
        _venv_py = os.path.expanduser("~/.venvs/video-skills/bin/python3")
        if os.path.isfile(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
            os.execv(_venv_py, [_venv_py, *sys.argv])

import argparse
import importlib.util
import json
import math
import re
import subprocess
import unicodedata
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

SS = 2  # 2x supersampling factor for razor-sharp anti-aliased vector geometry & Vietnamese diacritics

STRIP_METADATA_SCRIPT = Path.home() / ".gemini/config/skills/strip-media-metadata/scripts/strip_metadata.py"

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
    "be_black": ["BeVietnamPro-Black.ttf", "BeVietnamPro-ExtraBold.ttf", "DejaVuSans-Bold.ttf"],
    "be_extrabold": ["BeVietnamPro-ExtraBold.ttf", "BeVietnamPro-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "be_bold": ["BeVietnamPro-Bold.ttf", "Montserrat-Bold.otf", "DejaVuSans-Bold.ttf"],
    "be_italic": ["BeVietnamPro-BoldItalic.ttf", "BeVietnamPro-Italic.ttf", "DejaVuSans.ttf"],
    "be_regular": ["Montserrat-Medium.ttf", "BeVietnamPro-Light.ttf", "DejaVuSans.ttf"],
    "mont_black": ["Montserrat-Black.otf", "Montserrat-ExtraBold.ttf", "BeVietnamPro-Black.ttf"],
    "mont_extrabold": ["Montserrat-ExtraBold.ttf", "Montserrat-ExtraBold.otf", "BeVietnamPro-ExtraBold.ttf"],
    "mont_bold": ["Montserrat-Bold.otf", "BeVietnamPro-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "mont_medium": ["Montserrat-Medium.ttf", "BeVietnamPro-Bold.ttf", "DejaVuSans.ttf"],
    "playfair_italic": [
        "PlayfairDisplay-BoldItalic.ttf",
        "PlayfairDisplay-Italic[wght].ttf",
        "BeVietnamPro-BoldItalic.ttf",
    ],
    "playfair_regular": [
        "PlayfairDisplay-Variable.ttf",
        "PlayfairDisplay[wght].ttf",
        "BeVietnamPro-Bold.ttf",
    ],
    "dancing": ["SVN-Dancing script.ttf", "TF-Whispers-xsaha0.ttf", "GreatVibes-Regular.ttf", "BeVietnamPro-BoldItalic.ttf"],
    "mono_bold": ["LigaSFMonoNerdFont-Bold.otf", "JetBrainsMono.ttf", "DejaVuSansMono-Bold.ttf"],
    "mono_medium": ["LigaSFMonoNerdFont-Medium.otf", "JetBrainsMono.ttf", "DejaVuSansMono-Bold.ttf"],
}

ACCENT_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "mint": {
        "main": (45, 212, 191),      # #2DD4BF
        "bright": (153, 246, 228),   # #99F6E4
        "deep": (13, 48, 52),
        "card_bg": (12, 24, 31),
    },
    "cyan": {
        "main": (56, 189, 248),      # #38BDF8
        "bright": (186, 230, 253),   # #BAE6FD
        "deep": (12, 38, 62),
        "card_bg": (11, 20, 34),
    },
    "coral": {
        "main": (255, 77, 94),       # #FF4D5E
        "bright": (254, 205, 211),   # #FECDD3
        "deep": (64, 16, 26),
        "card_bg": (26, 14, 19),
    },
    "violet": {
        "main": (192, 132, 252),     # #C084FC
        "bright": (233, 213, 255),   # #E9D5FF
        "deep": (46, 20, 72),
        "card_bg": (19, 14, 32),
    },
    "lime": {
        "main": (74, 222, 128),      # #4ADE80
        "bright": (187, 247, 208),   # #BBF7D0
        "deep": (14, 52, 30),
        "card_bg": (12, 24, 18),
    },
    "gold": {
        "main": (250, 204, 21),      # #FACC15
        "bright": (254, 240, 138),   # #FEF08A
        "deep": (58, 42, 10),
        "card_bg": (22, 20, 16),
    },
    "blue": {
        "main": (96, 165, 250),      # #60A5FA
        "bright": (191, 219, 254),   # #BFDBFE
        "deep": (17, 36, 68),
        "card_bg": (12, 20, 36),
    },
    "red": {
        "main": (255, 59, 59),       # #FF3B3B
        "bright": (254, 163, 163),
        "deep": (58, 16, 22),
        "card_bg": (26, 14, 18),
    },
    "emerald": {
        "main": (16, 185, 129),      # #10B981
        "bright": (167, 243, 208),
        "deep": (10, 46, 36),
        "card_bg": (11, 24, 22),
    },
}


# ---------------------------------------------------------------------------
# Core Normalization, Emoji Hygiene, Font Resolution & Metadata Stripping
# ---------------------------------------------------------------------------

# Zero Noto/Twemoji color emojis: strip raw color emoji codepoints and route to crisp vector geometry
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

_EMOJI_TO_VECTOR_ICON_MAP: tuple[tuple[str, str], ...] = (
    ("\U0001F512", "lock"),      # padlock
    ("\U0001F510", "lock"),      # closed lock with key
    ("\U0001F513", "lock"),      # unlocked padlock
    ("\U0001F680", "arrow"),     # launch arrow (replaces rocket)
    ("\u2728", "spark"),         # sparkles
    ("\U0001F31F", "spark"),     # glowing star
    ("\u2B50", "star"),          # star
    ("\u26A1", "bolt"),          # high voltage bolt
    ("\U0001F525", "spark"),     # flame -> spark
    ("\U0001F3AF", "aperture"),  # target -> aperture reticle
    ("\U0001F4F7", "aperture"),  # camera -> aperture
    ("\U0001F3A5", "aperture"),  # movie camera -> aperture
    ("\u2705", "check"),         # check mark
    ("\u2611", "check"),         # ballot check
    ("\u274C", "cross"),         # cross mark
    ("\u26D4", "cross"),         # no entry
)


def _extract_emoji_icon_hint(raw_text: Any, fallback: str | None = None) -> str | None:
    """Map any raw system emoji codepoint to a clean vector geometric icon name (`lock`, `arrow`, `spark`, `aperture`)."""
    s = str(raw_text or "")
    for em, vkind in _EMOJI_TO_VECTOR_ICON_MAP:
        if em in s:
            return vkind
    return fallback


def nfc_clean(text: Any, strip_commas: bool = False) -> str:
    """Normalize text to NFC Unicode and strip raw system color emojis. Optionally strip non-decimal commas."""
    s = unicodedata.normalize("NFC", str(text or ""))
    # Preserve semantic ASCII/vector tokens handled explicitly (`✓` -> check, `❯` -> chevron) only when standalone; strip color emojis
    s = _RAW_COLOR_EMOJI_RE.sub(" ", s).strip()
    if strip_commas:
        s = re.sub(r"(?<!\d),\s*|,\s*(?!\d)", " ", s)
    return re.sub(r"[ \t]+", " ", s).strip()


class VisualBlockResult(type(Path())):
    """`pathlib.Path` subclass returned by visual block primitives exposing `.anchor_shape_xyr` for concentric match-cuts."""

    anchor_shape_xyr: dict[str, Any] = {}


@lru_cache(maxsize=64)
def _resolve_font_path(role: str) -> str:
    candidates = FONT_CANDIDATES.get(role, FONT_CANDIDATES["be_bold"])
    for fname in candidates:
        for fdir in FONT_DIRS:
            cand = fdir / fname
            if cand.is_file():
                return str(cand)
    raise FileNotFoundError(f"Could not locate any local font for role={role!r}")


@lru_cache(maxsize=256)
def load_font(role: str, pt_size: int) -> ImageFont.FreeTypeFont:
    path = _resolve_font_path(role)
    return ImageFont.truetype(path, max(8, int(round(pt_size))))


@lru_cache(maxsize=1)
def _load_strip_module():
    if STRIP_METADATA_SCRIPT.is_file():
        spec = importlib.util.spec_from_file_location("_strip_media_metadata", STRIP_METADATA_SCRIPT)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def strip_image_metadata(path: str | Path) -> None:
    """Strip all identifying container metadata (PNG tEXt/iTXt/zTXt/eXIf/iCCP, JPEG APP1/APP13/EXIF/XMP/COM, WebP) in place."""
    p = Path(path)
    if not p.is_file():
        return
    mod = _load_strip_module()
    if mod is not None:
        raw = p.read_bytes()
        if raw.startswith(b"\x89PNG\r\n\x1a\n") and hasattr(mod, "strip_png"):
            cleaned, _removed = mod.strip_png(raw, keep_icc=False)
            if cleaned != raw:
                p.write_bytes(cleaned)
            return
        if raw.startswith(b"\xff\xd8") and hasattr(mod, "strip_jpeg"):
            cleaned, _removed = mod.strip_jpeg(raw, keep_icc=False)
            if cleaned != raw:
                p.write_bytes(cleaned)
            return
    if STRIP_METADATA_SCRIPT.is_file():
        subprocess.run(
            [sys.executable, str(STRIP_METADATA_SCRIPT), str(p)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def strip_png_metadata(path: str | Path) -> None:
    """Backward-compatible alias for `strip_image_metadata`."""
    strip_image_metadata(path)


def _save_supersampled(
    canvas_2x: Image.Image,
    out_path: str | Path,
    anchor_shape_xyr: dict[str, Any] | None = None,
) -> VisualBlockResult:
    """Downsample 2x RGBA canvas with LANCZOS, write clean PNG, strip metadata, and attach `anchor_shape_xyr`."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    w1 = max(1, canvas_2x.width // SS)
    h1 = max(1, canvas_2x.height // SS)
    final = canvas_2x.resize((w1, h1), Image.Resampling.LANCZOS)
    final.save(out, format="PNG", optimize=True)
    strip_png_metadata(out)

    res = VisualBlockResult(out)
    if anchor_shape_xyr is not None:
        res.anchor_shape_xyr = dict(anchor_shape_xyr)
    else:
        r_px = max(8, min(w1, h1) // 2 - 14)
        res.anchor_shape_xyr = {
            "cx_pct": 0.50,
            "cy_pct": 0.50,
            "r_pct_w": round(r_px / float(w1), 6),
            "cx_px": w1 // 2,
            "cy_px": h1 // 2,
            "r_px": r_px,
            "shape": "rounded_rect",
        }
    return res


def _palette(name: str | None) -> dict[str, tuple[int, int, int]]:
    """
    Resolve semantic hue (`mint`, `cyan`, `coral`, `violet`, `lime`, `gold`, `blue`, `red`, `emerald`)
    OR direct `#RRGGBB` hex string into harmonized `(main, bright, deep, card_bg)` RGB tuples.
    """
    key = str(name or "mint").strip().lower()
    if key in ACCENT_PALETTES:
        return ACCENT_PALETTES[key]
    m = re.match(r"^#?([0-9a-f]{6})$", key)
    if m:
        hx = m.group(1)
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        return {
            "main": (r, g, b),
            "bright": (min(255, int(r + (255 - r) * 0.55)), min(255, int(g + (255 - g) * 0.55)), min(255, int(b + (255 - b) * 0.55))),
            "deep": (max(8, int(r * 0.24)), max(10, int(g * 0.24)), max(14, int(b * 0.26))),
            "card_bg": (max(10, int(8 + r * 0.06)), max(12, int(11 + g * 0.06)), max(16, int(15 + b * 0.08))),
        }
    return ACCENT_PALETTES["mint"]


def _rgba(rgb: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), max(0, min(255, int(alpha))))


# ---------------------------------------------------------------------------
# Dynamic `textbbox` Measurement & Wrapping Helpers
# ---------------------------------------------------------------------------

_MEASURE_IMG = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMG)


def text_metrics(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, tuple[int, int, int, int]]:
    """Return `(width, height, bbox)` using exact PIL `textbbox`."""
    s = nfc_clean(text)
    if not s:
        return 0, 0, (0, 0, 0, 0)
    bb = _MEASURE_DRAW.textbbox((0, 0), s, font=font)
    return bb[2] - bb[0], bb[3] - bb[1], bb


def fit_font(
    text: str,
    role: str,
    max_width_px: int,
    start_px: int,
    min_px: int = 18,
    step_px: int = 2,
) -> ImageFont.FreeTypeFont:
    """Shrink font size smoothly until single-line `textbbox` fits `max_width_px`."""
    sz = int(start_px)
    while sz > min_px:
        f = load_font(role, sz)
        w, _, _ = text_metrics(text, f)
        if w <= max_width_px:
            return f
        sz -= max(1, step_px)
    return load_font(role, min_px)


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: int,
    max_lines: int = 4,
) -> list[str]:
    """Word-wrap Vietnamese text strictly inside `max_width_px` via `textbbox`."""
    clean = nfc_clean(text)
    if not clean:
        return [""]
    paragraphs = clean.split("\n")
    lines: list[str] = []
    for para in paragraphs:
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for w in words[1:]:
            cand = f"{cur} {w}"
            cw, _, _ = text_metrics(cand, font)
            if cw <= max_width_px:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)

    if len(lines) > max_lines:
        kept = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :])
        while tail and text_metrics(tail + "…", font)[0] > max_width_px and " " in tail:
            tail = tail.rsplit(" ", 1)[0]
        kept.append((tail + "…") if tail != " ".join(lines[max_lines - 1 :]) else tail)
        return kept
    return lines


def draw_text_centered_y(
    draw: ImageDraw.ImageDraw,
    x: float,
    cy: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    align_x: str = "left",
) -> tuple[int, int]:
    """Draw single-line text optically centered around `cy` using `textbbox` offsets."""
    s = nfc_clean(text)
    w, h, bb = text_metrics(s, font)
    if align_x == "center":
        dx = x - bb[0] - w / 2.0
    elif align_x == "right":
        dx = x - bb[0] - w
    else:
        dx = x - bb[0]
    dy = cy - (bb[1] + bb[3]) / 2.0
    draw.text((dx, dy), s, font=font, fill=fill)
    return w, h


# ---------------------------------------------------------------------------
# Reusable Glassmorphism Surfaces & Vector Icons (at 2x Supersampling)
# ---------------------------------------------------------------------------

def _make_card_canvas(
    card_w: int,
    card_h: int,
    pad: int,
    radius: int,
    bg_top: tuple[int, int, int],
    bg_bot: tuple[int, int, int],
    border_rgb: tuple[int, int, int],
    glow_rgb: tuple[int, int, int] | None = None,
    bg_alpha: int = 242,
    shadow_alpha: int = 148,
) -> tuple[Image.Image, int, int]:
    """Create a 2x RGBA canvas with soft drop shadow, vertical gradient glass fill, radial aura, and crisp border."""
    W = (card_w + pad * 2) * SS
    H = (card_h + pad * 2) * SS
    x0, y0 = pad * SS, pad * SS
    x1, y1 = x0 + card_w * SS, y0 + card_h * SS
    rad = radius * SS

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 1. Soft multi-radius drop shadow
    if shadow_alpha > 0:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle(
            (x0 + 2 * SS, y0 + 10 * SS, x1 + 2 * SS, y1 + 14 * SS),
            radius=rad,
            fill=(0, 0, 0, shadow_alpha),
        )
        sh = sh.filter(ImageFilter.GaussianBlur(radius=14 * SS))
        canvas = Image.alpha_composite(canvas, sh)

    # 2. Optional ambient outer glow
    if glow_rgb is not None:
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        gd.rounded_rectangle(
            (x0 - 2 * SS, y0 - 2 * SS, x1 + 2 * SS, y1 + 2 * SS),
            radius=rad + 2 * SS,
            outline=_rgba(glow_rgb, 95),
            width=4 * SS,
        )
        gl = gl.filter(ImageFilter.GaussianBlur(radius=9 * SS))
        canvas = Image.alpha_composite(canvas, gl)

    # 3. Rounded gradient body via numpy for silky vertical interpolation
    ch = y1 - y0
    cw = x1 - x0
    t = np.linspace(0.0, 1.0, ch, dtype=np.float32)[:, None]
    grad = np.zeros((ch, cw, 4), dtype=np.uint8)
    for c_idx in range(3):
        grad[:, :, c_idx] = np.clip(bg_top[c_idx] * (1.0 - t) + bg_bot[c_idx] * t, 0, 255).astype(np.uint8)
    grad[:, :, 3] = bg_alpha
    grad_img = Image.fromarray(grad, mode="RGBA")

    # Subtle top-left radial aura inside card
    if glow_rgb is not None:
        aura = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ad = ImageDraw.Draw(aura)
        ar_w = int(cw * 0.55)
        ar_h = int(ch * 0.65)
        ad.ellipse((-ar_w // 3, -ar_h // 3, ar_w, ar_h), fill=_rgba(glow_rgb, 36))
        aura = aura.filter(ImageFilter.GaussianBlur(radius=28 * SS))
        grad_img = Image.alpha_composite(grad_img, aura)

    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=rad, fill=255)

    body_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body_layer.paste(grad_img, (x0, y0), mask)
    canvas = Image.alpha_composite(canvas, body_layer)

    # 4. Crisp inner specular highlight + outer border
    bd = ImageDraw.Draw(canvas)
    bd.rounded_rectangle(
        (x0 + 1 * SS, y0 + 1 * SS, x1 - 1 * SS, y1 - 1 * SS),
        radius=max(2, rad - 1 * SS),
        outline=(255, 255, 255, 26),
        width=max(1, 1 * SS),
    )
    bd.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=rad,
        outline=_rgba(border_rgb, 195),
        width=2 * SS,
    )
    return canvas, x0, y0


def _draw_vector_icon(
    draw: ImageDraw.ImageDraw,
    kind: str,
    cx: float,
    cy: float,
    r: float,
    rgb: tuple[int, int, int],
    filled_badge: bool = True,
) -> None:
    """Draw crisp geometric vector icons at `(cx, cy)` with radius `r` (already scaled by SS)."""
    if filled_badge:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgba(rgb, 38), outline=_rgba(rgb, 215), width=max(2, int(r * 0.13)))

    fg = _rgba(rgb, 255) if not filled_badge else (248, 250, 252, 255)
    stroke_w = max(2, int(round(r * 0.22)))

    if kind == "check":
        pts = [
            (cx - r * 0.42, cy + r * 0.02),
            (cx - r * 0.10, cy + r * 0.34),
            (cx + r * 0.46, cy - r * 0.30),
        ]
        draw.line(pts, fill=_rgba(rgb, 255), width=stroke_w, joint="curve")
    elif kind == "cross":
        d = r * 0.34
        draw.line([(cx - d, cy - d), (cx + d, cy + d)], fill=_rgba(rgb, 255), width=stroke_w)
        draw.line([(cx - d, cy + d), (cx + d, cy - d)], fill=_rgba(rgb, 255), width=stroke_w)
    elif kind == "dot":
        draw.ellipse((cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78), fill=_rgba(rgb, 52))
        draw.ellipse((cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42), fill=_rgba(rgb, 255))
    elif kind == "bolt":
        poly = [
            (cx + r * 0.10, cy - r * 0.58),
            (cx - r * 0.42, cy + r * 0.06),
            (cx - r * 0.04, cy + r * 0.06),
            (cx - r * 0.14, cy + r * 0.58),
            (cx + r * 0.42, cy - r * 0.08),
            (cx + r * 0.04, cy - r * 0.08),
        ]
        draw.polygon(poly, fill=_rgba(rgb, 255))
    elif kind in ("star", "spark"):
        pts = []
        for i in range(8):
            ang = -math.pi / 2 + i * (math.pi / 4)
            rad_i = r * (0.62 if i % 2 == 0 else 0.20)
            pts.append((cx + math.cos(ang) * rad_i, cy + math.sin(ang) * rad_i))
        draw.polygon(pts, fill=_rgba(rgb, 255))
    elif kind in ("lock", "padlock"):
        # Crisp vector padlock (shackle arc + body + keyhole dot)
        sh_w = r * 0.34
        sh_top = cy - r * 0.56
        sh_bot = cy + r * 0.02
        draw.arc(
            (cx - sh_w, sh_top, cx + sh_w, sh_bot),
            start=180,
            end=0,
            fill=_rgba(rgb, 255),
            width=max(2, int(round(r * 0.18))),
        )
        draw.line([(cx - sh_w, (sh_top + sh_bot) * 0.5), (cx - sh_w, cy - r * 0.04)], fill=_rgba(rgb, 255), width=max(2, int(round(r * 0.18))))
        draw.line([(cx + sh_w, (sh_top + sh_bot) * 0.5), (cx + sh_w, cy - r * 0.04)], fill=_rgba(rgb, 255), width=max(2, int(round(r * 0.18))))
        bw_h = r * 0.48
        draw.rounded_rectangle(
            (cx - bw_h, cy - r * 0.06, cx + bw_h, cy + r * 0.56),
            radius=max(2, int(r * 0.16)),
            fill=_rgba(rgb, 245),
        )
        kr = max(1.5, r * 0.11)
        draw.ellipse((cx - kr, cy + r * 0.16 - kr, cx + kr, cy + r * 0.16 + kr), fill=(12, 18, 28, 255))
    elif kind in ("arrow", "rocket", "launch"):
        # Clean 45-degree vector launch/trend arrow (replaces raw 🚀 color emoji)
        d = r * 0.46
        draw.line([(cx - d * 0.78, cy + d * 0.78), (cx + d * 0.72, cy - d * 0.72)], fill=_rgba(rgb, 255), width=stroke_w)
        draw.line(
            [(cx + d * 0.04, cy - d * 0.78), (cx + d * 0.78, cy - d * 0.78), (cx + d * 0.78, cy - d * 0.04)],
            fill=_rgba(rgb, 255),
            width=stroke_w,
            joint="curve",
        )
    elif kind in ("aperture", "camera", "lens"):
        # Crisp 6-blade optical camera aperture icon
        ro = r * 0.64
        ri = r * 0.28
        draw.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), outline=_rgba(rgb, 255), width=max(2, int(round(r * 0.15))))
        for i in range(6):
            a0 = i * (math.pi / 3.0)
            a1 = a0 + 0.96
            p0 = (cx + math.cos(a0) * ri, cy + math.sin(a0) * ri)
            p1 = (cx + math.cos(a1) * ro * 0.94, cy + math.sin(a1) * ro * 0.94)
            draw.line([p0, p1], fill=_rgba(rgb, 240), width=max(1, int(round(r * 0.13))))
    elif kind == "chevron":
        d = r * 0.38
        draw.line([(cx - d * 0.55, cy - d), (cx + d * 0.45, cy), (cx - d * 0.55, cy + d)], fill=_rgba(rgb, 255), width=stroke_w, joint="curve")
    else:
        draw.ellipse((cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36), fill=fg)


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    p0: tuple[float, float],
    p1: tuple[float, float],
    color: tuple[int, int, int, int],
    width: int,
    head_len: float,
) -> None:
    """Draw a clean vector line + triangular arrowhead from `p0` to `p1`."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-3:
        return
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    shaft_end = (p1[0] - ux * head_len * 0.72, p1[1] - uy * head_len * 0.72)
    draw.line([p0, shaft_end], fill=color, width=width)
    wing = head_len * 0.56
    tri = [
        p1,
        (p1[0] - ux * head_len + px * wing, p1[1] - uy * head_len + py * wing),
        (p1[0] - ux * head_len - px * wing, p1[1] - uy * head_len - py * wing),
    ]
    draw.polygon(tri, fill=color)


def _draw_pill_auto(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    accent_rgb: tuple[int, int, int],
    icon_kind: str | None = "dot",
    pad_x: int = 18 * SS,
    height: int = 38 * SS,
    center_x: bool = False,
) -> tuple[float, float, float, float]:
    """Draw a dynamically `textbbox`-sized pill badge. Never clips text or renders raw color emojis."""
    eff_icon = _extract_emoji_icon_hint(text, icon_kind)
    label = nfc_clean(text)
    tw, _, _ = text_metrics(label, font)
    icon_space = (26 * SS) if eff_icon else 0
    pw = tw + pad_x * 2 + icon_space
    px0 = (x - pw / 2.0) if center_x else x
    px1 = px0 + pw
    py0, py1 = y, y + height
    cy = (py0 + py1) / 2.0

    draw.rounded_rectangle(
        (px0, py0, px1, py1),
        radius=height // 2,
        fill=_rgba(accent_rgb, 34),
        outline=_rgba(accent_rgb, 195),
        width=max(2, int(1.5 * SS)),
    )
    tx = px0 + pad_x
    if eff_icon:
        _draw_vector_icon(draw, eff_icon, tx + 8 * SS, cy, 10 * SS, accent_rgb, filled_badge=False)
        tx += icon_space
    draw_text_centered_y(draw, tx, cy, label, font, _rgba(accent_rgb, 255), align_x="left")
    return px0, py0, px1, py1


# ---------------------------------------------------------------------------
# 1. `versus_split_card`
# ---------------------------------------------------------------------------

def versus_split_card(
    out_path: str | Path,
    left_title: str,
    left_items: Sequence[str],
    right_title: str,
    right_items: Sequence[str],
    badge: str | None = None,
    accent: str = "mint",
    left_accent: str = "red",
    badge_accent: str = "gold",
) -> Path:
    """
    Side-by-side 2-column comparison card:
      - Left: Dimmed Crimson/Coral 'Cách cũ / Thủ công' with vector ✕ icons
      - Right: Glowing semantic `accent` (`mint`, `cyan`, `lime`, `violet`, `gold`, ...) with vector ✓ icons
      - Center: Vector 'VS' medallion divider + optional top pill `badge`.
    """
    pal_r = _palette(accent)
    pal_l = _palette(left_accent)
    pal_b = _palette(badge_accent)
    red_rgb = pal_l["main"]
    mint_rgb = pal_r["main"]

    card_w = 920
    pad = 28
    col_gap = 28
    inner_pad = 24
    col_w = (card_w - inner_pad * 2 - col_gap) // 2  # 422 px per column

    f_badge = load_font("mont_bold", 18 * SS)
    f_title_l = fit_font(nfc_clean(left_title), "be_extrabold", (col_w - 48) * SS, 25 * SS, 17 * SS)
    f_title_r = fit_font(nfc_clean(right_title), "be_extrabold", (col_w - 48) * SS, 25 * SS, 17 * SS)
    f_item = load_font("be_bold", 20 * SS)
    f_vs = load_font("mont_black", 22 * SS)

    text_max_w = (col_w - 74) * SS
    l_wrapped = [wrap_text(it, f_item, text_max_w, max_lines=3) for it in left_items]
    r_wrapped = [wrap_text(it, f_item, text_max_w, max_lines=3) for it in right_items]

    n_rows = max(len(l_wrapped), len(r_wrapped), 1)
    line_h = 28
    row_heights = []
    for i in range(n_rows):
        nl = len(l_wrapped[i]) if i < len(l_wrapped) else 1
        nr = len(r_wrapped[i]) if i < len(r_wrapped) else 1
        row_heights.append(max(nl, nr) * line_h + 22)

    top_badge_h = 54 if badge else 0
    header_h = 68
    cols_h = header_h + sum(row_heights) + 26
    card_h = inner_pad * 2 + top_badge_h + cols_h

    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=28,
        bg_top=(15, 20, 29), bg_bot=(10, 14, 21),
        border_rgb=(71, 85, 105), glow_rgb=mint_rgb,
    )
    draw = ImageDraw.Draw(canvas)

    cur_y = y0 + inner_pad * SS
    if badge:
        _draw_pill_auto(
            draw, x0 + (card_w * SS) / 2.0, cur_y,
            badge, f_badge, pal_b["main"],
            icon_kind="bolt", height=38 * SS, center_x=True,
        )
        cur_y += top_badge_h * SS

    lx0 = x0 + inner_pad * SS
    lx1 = lx0 + col_w * SS
    rx0 = lx1 + col_gap * SS
    rx1 = rx0 + col_w * SS
    cy0 = cur_y
    cy1 = cy0 + cols_h * SS

    # Left dimmed crimson/coral column
    draw.rounded_rectangle(
        (lx0, cy0, lx1, cy1),
        radius=20 * SS,
        fill=_rgba(pal_l["card_bg"], 215),
        outline=_rgba(red_rgb, 115),
        width=2 * SS,
    )
    draw.rounded_rectangle(
        (lx0 + 2 * SS, cy0 + 2 * SS, lx1 - 2 * SS, cy0 + header_h * SS),
        radius=18 * SS,
        fill=_rgba(pal_l["deep"], 155),
    )

    # Right luminous semantic accent column + subtle outer glow
    r_glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(r_glow).rounded_rectangle(
        (rx0 - 2 * SS, cy0 - 2 * SS, rx1 + 2 * SS, cy1 + 2 * SS),
        radius=22 * SS,
        outline=_rgba(mint_rgb, 110),
        width=4 * SS,
    )
    canvas = Image.alpha_composite(canvas, r_glow.filter(ImageFilter.GaussianBlur(radius=7 * SS)))
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle(
        (rx0, cy0, rx1, cy1),
        radius=20 * SS,
        fill=_rgba(pal_r["card_bg"], 236),
        outline=_rgba(mint_rgb, 225),
        width=2 * SS,
    )
    draw.rounded_rectangle(
        (rx0 + 2 * SS, cy0 + 2 * SS, rx1 - 2 * SS, cy0 + header_h * SS),
        radius=18 * SS,
        fill=_rgba(pal_r["deep"], 180),
    )

    # Column Titles
    draw_text_centered_y(
        draw, (lx0 + lx1) / 2.0, cy0 + (header_h * SS) / 2.0,
        left_title, f_title_l, _rgba(pal_l["bright"], 245), align_x="center",
    )
    draw_text_centered_y(
        draw, (rx0 + rx1) / 2.0, cy0 + (header_h * SS) / 2.0,
        right_title, f_title_r, _rgba(pal_r["bright"], 255), align_x="center",
    )

    # Items inside both columns
    ry_cursor = cy0 + (header_h + 12) * SS
    for idx in range(n_rows):
        rh = row_heights[idx] * SS
        row_mid = ry_cursor + rh / 2.0

        if idx < len(l_wrapped):
            lines_l = l_wrapped[idx]
            _draw_vector_icon(draw, "cross", lx0 + 30 * SS, row_mid, 13 * SS, red_rgb, filled_badge=True)
            block_h = len(lines_l) * line_h * SS
            ty = row_mid - block_h / 2.0 + (line_h * SS) / 2.0
            for ln in lines_l:
                draw_text_centered_y(draw, lx0 + 54 * SS, ty, ln, f_item, (226, 212, 216, 220), align_x="left")
                ty += line_h * SS

        if idx < len(r_wrapped):
            lines_r = r_wrapped[idx]
            _draw_vector_icon(draw, "check", rx0 + 30 * SS, row_mid, 13 * SS, mint_rgb, filled_badge=True)
            block_h = len(lines_r) * line_h * SS
            ty = row_mid - block_h / 2.0 + (line_h * SS) / 2.0
            for ln in lines_r:
                draw_text_centered_y(draw, rx0 + 54 * SS, ty, ln, f_item, (248, 250, 252, 255), align_x="left")
                ty += line_h * SS

        ry_cursor += rh
        if idx < n_rows - 1:
            draw.line([(lx0 + 20 * SS, ry_cursor), (lx1 - 20 * SS, ry_cursor)], fill=(255, 255, 255, 18), width=SS)
            draw.line([(rx0 + 20 * SS, ry_cursor), (rx1 - 20 * SS, ry_cursor)], fill=(45, 212, 191, 34), width=SS)

    # Center VS Medallion Divider
    vs_cx = (lx1 + rx0) / 2.0
    vs_cy = (cy0 + cy1) / 2.0
    vs_r = 28 * SS
    draw.line([(vs_cx, cy0 + 18 * SS), (vs_cx, vs_cy - vs_r - 6 * SS)], fill=(148, 163, 184, 90), width=2 * SS)
    draw.line([(vs_cx, vs_cy + vs_r + 6 * SS), (vs_cx, cy1 - 18 * SS)], fill=(148, 163, 184, 90), width=2 * SS)
    draw.ellipse((vs_cx - vs_r - 4 * SS, vs_cy - vs_r - 4 * SS, vs_cx + vs_r + 4 * SS, vs_cy + vs_r + 4 * SS), fill=(10, 14, 21, 235))
    draw.ellipse(
        (vs_cx - vs_r, vs_cy - vs_r, vs_cx + vs_r, vs_cy + vs_r),
        fill=(24, 31, 46, 255),
        outline=(255, 196, 20, 235),
        width=3 * SS,
    )
    draw_text_centered_y(draw, vs_cx, vs_cy, "VS", f_vs, (255, 196, 20, 255), align_x="center")

    return _save_supersampled(canvas, out_path)


# ---------------------------------------------------------------------------
# 2. `flowchart_pipeline`
# ---------------------------------------------------------------------------

def _parse_step_item(item: Any, idx: int) -> tuple[str, str]:
    if isinstance(item, dict):
        t = nfc_clean(item.get("title") or item.get("label") or f"Bước {idx}")
        s = nfc_clean(item.get("sub") or item.get("desc") or "")
        return t, s
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return nfc_clean(item[0]), nfc_clean(item[1])
    raw = nfc_clean(item)
    for sep in (" — ", " - ", ": ", " | "):
        if sep in raw:
            a, b = raw.split(sep, 1)
            return a.strip(), b.strip()
    return raw, ""


def _is_active_bento_item(idx_zero: int, active_one_based: int | None) -> tuple[bool, bool]:
    """Return `(has_focus_mode, is_active)` where `active_one_based` is 1..N (or 0 if caller passed 0)."""
    if active_one_based is None:
        return False, True
    act_idx = max(0, int(active_one_based) - 1) if int(active_one_based) >= 1 else 0
    return True, (idx_zero == act_idx)


def flowchart_pipeline(
    out_path: str | Path,
    header: str,
    steps: Sequence[Any],
    accent: str = "cyan",
    active_step: int | None = None,
) -> Path:
    """
    3 or 4 (up to 6) connected workflow step nodes with optional Active-Dim Bento (`active_step=1..N`):
      - 3 steps: sleek horizontal 3-node pipeline (`01 → 02 → 03`) or vertical flow if text is dense
      - 4 steps: connected 2x2 architectural grid (`01 → 02` top, `↓`, `04 ← 03` with clear directional arrows)
      - Glowing numbered badges + vector directional arrows (`→` / `↓`)!
    """
    pal = _palette(accent)
    acc = pal["main"]
    parsed = [_parse_step_item(st, i + 1) for i, st in enumerate(steps)]
    n = len(parsed)
    if n == 0:
        parsed = [("Bước 1", "Khởi tạo"), ("Bước 2", "Xử lý"), ("Bước 3", "Xuất bản")]
        n = 3

    pad = 28
    inner_pad = 28
    f_hdr = load_font("mont_bold", 19 * SS)
    f_num = load_font("mont_black", 20 * SS)
    f_title = load_font("be_extrabold", 22 * SS)
    f_sub = load_font("be_regular", 17 * SS)

    # Choose layout intelligently: 3 short/medium steps -> horizontal; 4 steps -> 2x2 grid; else vertical stack
    max_chars = max(len(t) + len(s) for t, s in parsed)
    if n == 3 and max_chars <= 52:
        mode = "horizontal_3"
    elif n == 4:
        mode = "grid_2x2"
    else:
        mode = "vertical"

    if mode == "horizontal_3":
        card_w = 940
        arrow_gap = 38
        node_w = (card_w - inner_pad * 2 - arrow_gap * 2) // 3  # 269 px
        txt_w = (node_w - 36) * SS
        wrapped = [(wrap_text(t, f_title, txt_w, 2), wrap_text(s, f_sub, txt_w, 2) if s else []) for t, s in parsed]
        max_t_lines = max(len(wt) for wt, _ in wrapped)
        max_s_lines = max((len(ws) for _, ws in wrapped), default=0)
        node_h = 74 + max_t_lines * 30 + (max_s_lines * 24 + 8 if max_s_lines else 0) + 22
        card_h = inner_pad * 2 + 62 + node_h

        canvas, x0, y0 = _make_card_canvas(
            card_w, card_h, pad, radius=28,
            bg_top=pal["card_bg"], bg_bot=(9, 13, 22),
            border_rgb=acc, glow_rgb=acc,
        )
        fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(fg_layer)
        _draw_pill_auto(draw, x0 + (card_w * SS) / 2.0, y0 + inner_pad * SS, header, f_hdr, acc, icon_kind="bolt", center_x=True)

        ny0 = y0 + (inner_pad + 62) * SS
        ny1 = ny0 + node_h * SS
        for idx, (wt, ws) in enumerate(wrapped):
            focus_mode, is_act = _is_active_bento_item(idx, active_step)
            nx0 = x0 + (inner_pad + idx * (node_w + arrow_gap)) * SS
            nx1 = nx0 + node_w * SS
            n_fill = (24, 38, 60, 228) if (focus_mode and is_act) else ((8, 12, 20, 175) if focus_mode else (18, 28, 44, 230))
            n_out = _rgba(acc, 245 if (focus_mode and is_act) else (62 if focus_mode else 165))
            draw.rounded_rectangle(
                (nx0, ny0, nx1, ny1),
                radius=20 * SS,
                fill=n_fill,
                outline=n_out,
                width=(3 if (focus_mode and is_act) else 2) * SS,
            )
            # Number badge
            bx, by = nx0 + 34 * SS, ny0 + 34 * SS
            draw.rounded_rectangle(
                (bx - 18 * SS, by - 16 * SS, bx + 22 * SS, by + 16 * SS),
                radius=10 * SS,
                fill=_rgba(acc, 58 if is_act else 18),
                outline=_rgba(acc, 240 if is_act else 85),
                width=2 * SS,
            )
            draw_text_centered_y(draw, bx + 2 * SS, by, f"{idx + 1:02d}", f_num, _rgba(acc, 255 if is_act else 120), align_x="center")

            t_fg = (248, 250, 252, 255) if is_act else (148, 163, 184, 138)
            s_fg = (186, 205, 228, 230) if is_act else (118, 134, 156, 120)
            ty = ny0 + 74 * SS
            for ln in wt:
                draw_text_centered_y(draw, nx0 + 18 * SS, ty, ln, f_title, t_fg, align_x="left")
                ty += 30 * SS
            ty += 4 * SS
            for ln in ws:
                draw_text_centered_y(draw, nx0 + 18 * SS, ty, ln, f_sub, s_fg, align_x="left")
                ty += 24 * SS

            if idx < 2:
                ay = (ny0 + ny1) / 2.0
                _draw_arrow(
                    draw,
                    (nx1 + 6 * SS, ay),
                    (nx1 + (arrow_gap - 6) * SS, ay),
                    _rgba(acc, 245 if is_act else 110),
                    width=3 * SS,
                    head_len=13 * SS,
                )
        return _save_supersampled(Image.alpha_composite(canvas, fg_layer), out_path)

    if mode == "grid_2x2":
        card_w = 900
        col_gap = 48
        row_gap = 44
        node_w = (card_w - inner_pad * 2 - col_gap) // 2  # 398 px
        txt_w = (node_w - 92) * SS
        wrapped = [(wrap_text(t, f_title, txt_w, 2), wrap_text(s, f_sub, txt_w, 2) if s else []) for t, s in parsed]
        node_h = max(
            26 + len(wt) * 30 + (len(ws) * 23 + 6 if ws else 0) + 22
            for wt, ws in wrapped
        )
        node_h = max(108, node_h)
        card_h = inner_pad * 2 + 64 + node_h * 2 + row_gap

        canvas, x0, y0 = _make_card_canvas(
            card_w, card_h, pad, radius=28,
            bg_top=pal["card_bg"], bg_bot=(9, 13, 22),
            border_rgb=acc, glow_rgb=acc,
        )
        fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(fg_layer)
        _draw_pill_auto(draw, x0 + (card_w * SS) / 2.0, y0 + inner_pad * SS, header, f_hdr, acc, icon_kind="star", center_x=True)

        # Snake order so flow arrows never cross cleanly:
        # Row 0: [0] -> [1]
        #               ↓
        # Row 1: [3] <- [2]
        coords = [
            (0, 0),  # step 1 top-left
            (1, 0),  # step 2 top-right
            (1, 1),  # step 3 bottom-right
            (0, 1),  # step 4 bottom-left
        ]
        boxes: list[tuple[float, float, float, float]] = []
        base_y = y0 + (inner_pad + 64) * SS
        for idx, (gx, gy) in enumerate(coords):
            focus_mode, is_act = _is_active_bento_item(idx, active_step)
            nx0 = x0 + (inner_pad + gx * (node_w + col_gap)) * SS
            ny0 = base_y + gy * (node_h + row_gap) * SS
            nx1 = nx0 + node_w * SS
            ny1 = ny0 + node_h * SS
            boxes.append((nx0, ny0, nx1, ny1))

            n_fill = (24, 38, 60, 228) if (focus_mode and is_act) else ((8, 12, 20, 175) if focus_mode else (18, 28, 44, 232))
            n_out = _rgba(acc, 245 if (focus_mode and is_act) else (62 if focus_mode else 180))
            draw.rounded_rectangle(
                (nx0, ny0, nx1, ny1),
                radius=20 * SS,
                fill=n_fill,
                outline=n_out,
                width=(3 if (focus_mode and is_act) else 2) * SS,
            )
            # Glowing circular step number on left of node
            bcx = nx0 + 40 * SS
            bcy = (ny0 + ny1) / 2.0
            draw.ellipse((bcx - 22 * SS, bcy - 22 * SS, bcx + 22 * SS, bcy + 22 * SS), fill=_rgba(acc, 58 if is_act else 18), outline=_rgba(acc, 240 if is_act else 85), width=2 * SS)
            draw_text_centered_y(draw, bcx, bcy, f"{idx + 1:02d}", f_num, _rgba(acc, 255 if is_act else 120), align_x="center")

            t_fg = (248, 250, 252, 255) if is_act else (148, 163, 184, 138)
            s_fg = (186, 205, 228, 228) if is_act else (118, 134, 156, 120)
            wt, ws = wrapped[idx]
            total_th = len(wt) * 30 * SS + (len(ws) * 23 * SS + 4 * SS if ws else 0)
            ty = bcy - total_th / 2.0 + 14 * SS
            for ln in wt:
                draw_text_centered_y(draw, nx0 + 76 * SS, ty, ln, f_title, t_fg, align_x="left")
                ty += 30 * SS
            ty += 4 * SS
            for ln in ws:
                draw_text_centered_y(draw, nx0 + 76 * SS, ty, ln, f_sub, s_fg, align_x="left")
                ty += 23 * SS

        # Arrow 1 -> 2 (right)
        b0, b1, b2, b3 = boxes
        _draw_arrow(draw, (b0[2] + 7 * SS, (b0[1] + b0[3]) / 2.0), (b1[0] - 7 * SS, (b1[1] + b1[3]) / 2.0), _rgba(acc, 250), 3 * SS, 14 * SS)
        # Arrow 2 -> 3 (down)
        _draw_arrow(draw, ((b1[0] + b1[2]) / 2.0, b1[3] + 6 * SS), ((b2[0] + b2[2]) / 2.0, b2[1] - 6 * SS), _rgba(acc, 250), 3 * SS, 14 * SS)
        # Arrow 3 -> 4 (left)
        _draw_arrow(draw, (b2[0] - 7 * SS, (b2[1] + b2[3]) / 2.0), (b3[2] + 7 * SS, (b3[1] + b3[3]) / 2.0), _rgba(acc, 250), 3 * SS, 14 * SS)

        return _save_supersampled(Image.alpha_composite(canvas, fg_layer), out_path)

    # Vertical connected pipeline (2, 3 long, or 5+ steps)
    card_w = 840
    node_w = card_w - inner_pad * 2
    txt_w = (node_w - 104) * SS
    wrapped = [(wrap_text(t, f_title, txt_w, 2), wrap_text(s, f_sub, txt_w, 2) if s else []) for t, s in parsed]
    arrow_gap = 32
    node_heights = [
        max(84, 24 + len(wt) * 30 + (len(ws) * 23 + 4 if ws else 0) + 18)
        for wt, ws in wrapped
    ]
    card_h = inner_pad * 2 + 64 + sum(node_heights) + arrow_gap * (n - 1)

    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=28,
        bg_top=pal["card_bg"], bg_bot=(9, 13, 22),
        border_rgb=acc, glow_rgb=acc,
    )
    fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg_layer)
    _draw_pill_auto(draw, x0 + (card_w * SS) / 2.0, y0 + inner_pad * SS, header, f_hdr, acc, icon_kind="bolt", center_x=True)

    ny = y0 + (inner_pad + 64) * SS
    nx0 = x0 + inner_pad * SS
    nx1 = nx0 + node_w * SS
    for idx, ((wt, ws), nh) in enumerate(zip(wrapped, node_heights)):
        focus_mode, is_act = _is_active_bento_item(idx, active_step)
        ny1 = ny + nh * SS
        n_fill = (24, 38, 60, 228) if (focus_mode and is_act) else ((8, 12, 20, 175) if focus_mode else (18, 28, 44, 232))
        n_out = _rgba(acc, 245 if (focus_mode and is_act) else (62 if focus_mode else 175))
        draw.rounded_rectangle(
            (nx0, ny, nx1, ny1),
            radius=18 * SS,
            fill=n_fill,
            outline=n_out,
            width=(3 if (focus_mode and is_act) else 2) * SS,
        )
        bcx = nx0 + 44 * SS
        bcy = (ny + ny1) / 2.0
        draw.ellipse((bcx - 22 * SS, bcy - 22 * SS, bcx + 22 * SS, bcy + 22 * SS), fill=_rgba(acc, 58 if is_act else 18), outline=_rgba(acc, 240 if is_act else 85), width=2 * SS)
        draw_text_centered_y(draw, bcx, bcy, f"{idx + 1:02d}", f_num, _rgba(acc, 255 if is_act else 120), align_x="center")

        t_fg = (248, 250, 252, 255) if is_act else (148, 163, 184, 138)
        s_fg = (186, 205, 228, 228) if is_act else (118, 134, 156, 120)
        total_th = len(wt) * 30 * SS + (len(ws) * 23 * SS + 4 * SS if ws else 0)
        ty = bcy - total_th / 2.0 + 14 * SS
        for ln in wt:
            draw_text_centered_y(draw, nx0 + 84 * SS, ty, ln, f_title, t_fg, align_x="left")
            ty += 30 * SS
        ty += 4 * SS
        for ln in ws:
            draw_text_centered_y(draw, nx0 + 84 * SS, ty, ln, f_sub, s_fg, align_x="left")
            ty += 23 * SS

        if idx < n - 1:
            ax = (nx0 + nx1) / 2.0
            _draw_arrow(draw, (ax, ny1 + 4 * SS), (ax, ny1 + (arrow_gap - 4) * SS), _rgba(acc, 245), 3 * SS, 12 * SS)
        ny = ny1 + arrow_gap * SS

    return _save_supersampled(Image.alpha_composite(canvas, fg_layer), out_path)


# ---------------------------------------------------------------------------
# 3. `metric_kpi_hero`
# ---------------------------------------------------------------------------

def metric_kpi_hero(
    out_path: str | Path,
    label: str,
    big_value: str,
    sub_delta: str,
    bars: Sequence[Any] | None = None,
    accent: str = "gold",
) -> Path:
    """
    High-impact KPI stat card:
      - e.g. `"-85%"` / `"15 TRIỆU → 0Đ"` / `"100+ GÓC MÁY"`
      - Upward or downward vector trend arrow + mini spark bar chart!
    """
    pal = _palette(accent)
    acc = pal["main"]
    bright = pal["bright"]

    card_w = 880
    pad = 28
    inner_pad = 30
    chart_zone_w = 230
    left_zone_w = card_w - inner_pad * 2 - chart_zone_w - 28  # 562 px

    val_str = nfc_clean(big_value).replace("->", "→")
    lbl_str = nfc_clean(label)
    delta_str = nfc_clean(sub_delta)

    f_lbl = load_font("mont_bold", 18 * SS)
    f_big = fit_font(val_str, "be_black", left_zone_w * SS, 72 * SS, 34 * SS)
    f_delta = fit_font(delta_str, "be_bold", (left_zone_w - 52) * SS, 21 * SS, 15 * SS)
    f_bar_lbl = load_font("mont_bold", 14 * SS)

    card_h = 276
    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=28,
        bg_top=pal["card_bg"], bg_bot=(10, 13, 20),
        border_rgb=acc, glow_rgb=acc,
    )
    draw = ImageDraw.Draw(canvas)

    lx = x0 + inner_pad * SS
    top_y = y0 + inner_pad * SS

    # 1. Label pill
    _draw_pill_auto(draw, lx, top_y, lbl_str, f_lbl, acc, icon_kind="dot", height=36 * SS, center_x=False)

    # 2. Giant Hero Value with soft colored glow
    big_cy = top_y + 98 * SS
    glow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    draw_text_centered_y(gd, lx, big_cy, val_str, f_big, _rgba(acc, 135), align_x="left")
    canvas = Image.alpha_composite(canvas, glow_layer.filter(ImageFilter.GaussianBlur(radius=8 * SS)))
    draw = ImageDraw.Draw(canvas)
    draw_text_centered_y(draw, lx, big_cy, val_str, f_big, (255, 255, 255, 255), align_x="left")

    # 3. Sub-delta pill + vector trend arrow (upward vs downward cost reduction)
    is_down = bool(re.match(r"^\s*-\d", val_str)) or any(
        kw in (val_str + " " + delta_str).lower() for kw in ("giảm", "tiết kiệm", "cắt giảm", "0đ")
    )
    trend_rgb = ACCENT_PALETTES["mint"]["main"]
    dw, _, _ = text_metrics(delta_str, f_delta)
    dp_w = dw + 66 * SS
    dp_y0 = y0 + (card_h - inner_pad - 44) * SS
    dp_y1 = dp_y0 + 42 * SS
    dp_cy = (dp_y0 + dp_y1) / 2.0
    draw.rounded_rectangle(
        (lx, dp_y0, lx + dp_w, dp_y1),
        radius=21 * SS,
        fill=_rgba(trend_rgb, 32),
        outline=_rgba(trend_rgb, 185),
        width=2 * SS,
    )
    # Diagonal vector trend arrow inside delta pill
    ax0 = lx + 18 * SS
    if is_down:
        _draw_arrow(draw, (ax0, dp_cy - 8 * SS), (ax0 + 20 * SS, dp_cy + 8 * SS), _rgba(trend_rgb, 255), 3 * SS, 10 * SS)
    else:
        _draw_arrow(draw, (ax0, dp_cy + 8 * SS), (ax0 + 20 * SS, dp_cy - 8 * SS), _rgba(trend_rgb, 255), 3 * SS, 10 * SS)
    draw_text_centered_y(draw, lx + 46 * SS, dp_cy, delta_str, f_delta, (204, 251, 241, 255), align_x="left")

    # 4. Right Mini Spark Bar Chart Panel
    cx0 = x0 + (card_w - inner_pad - chart_zone_w) * SS
    cx1 = x0 + (card_w - inner_pad) * SS
    cy0 = y0 + inner_pad * SS
    cy1 = y0 + (card_h - inner_pad) * SS

    draw.rounded_rectangle(
        (cx0, cy0, cx1, cy1),
        radius=20 * SS,
        fill=(15, 22, 34, 205),
        outline=(255, 255, 255, 28),
        width=max(1, int(1.5 * SS)),
    )

    if not bars:
        raw_bars = [("T1", 28), ("T2", 42), ("T3", 58), ("T4", 76), ("NAY", 100)] if not is_down else [("CŨ", 100), ("B1", 72), ("B2", 46), ("B3", 28), ("MỚI", 15)]
    else:
        raw_bars = []
        for idx, b in enumerate(bars):
            if isinstance(b, dict):
                raw_bars.append((str(b.get("label", f"#{idx+1}")), float(b.get("value", 50))))
            elif isinstance(b, (list, tuple)) and len(b) >= 2:
                raw_bars.append((str(b[0]), float(b[1])))
            else:
                raw_bars.append((f"#{idx+1}", float(b)))

    nb = max(1, len(raw_bars))
    max_v = max(max(v for _, v in raw_bars), 1.0)
    pad_chart_x = 20 * SS
    avail_w = (cx1 - cx0) - pad_chart_x * 2
    gap_b = 10 * SS
    bar_w = max(12 * SS, (avail_w - gap_b * (nb - 1)) / nb)
    base_by = cy1 - 36 * SS
    max_bh = (base_by - (cy0 + 24 * SS))

    for i, (blbl, bval) in enumerate(raw_bars):
        bx0 = cx0 + pad_chart_x + i * (bar_w + gap_b)
        bx1 = bx0 + bar_w
        ratio = max(0.10, min(1.0, bval / max_v))
        bh = ratio * max_bh
        by0 = base_by - bh
        is_highlight = (i == nb - 1)
        b_col = _rgba(acc, 250) if is_highlight else _rgba(acc, 95)
        b_out = _rgba(bright, 240) if is_highlight else _rgba(acc, 130)
        draw.rounded_rectangle((bx0, by0, bx1, base_by), radius=6 * SS, fill=b_col, outline=b_out, width=max(1, SS))
        if blbl:
            draw_text_centered_y(draw, (bx0 + bx1) / 2.0, cy1 - 18 * SS, blbl[:4], f_bar_lbl, (148, 163, 184, 225) if not is_highlight else _rgba(bright, 255), align_x="center")

    return _save_supersampled(canvas, out_path)


# ---------------------------------------------------------------------------
# 4. `code_terminal_window`
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r'(".*?"|\'.*?\'|`.*?`|--?[a-zA-Z0-9_-]+|\b[A-Za-z0-9_./-]+(?:\.md|\.py|\.json|\.fcproj|\.sh)\b|\b\d+(?:\.\d+)?%?\b|#[A-Fa-f0-9]{6}\b|\S+|\s+)'
)

_KEYWORDS_CYAN = {
    "def", "class", "import", "from", "return", "async", "await", "if", "else", "for", "in",
    "python3", "ffmpeg", "ffprobe", "git", "npm", "npx", "uv", "render", "audit", "build",
    "name:", "description:", "model:", "tools:", "flow:", "style:",
}
_TOKENS_MINT = {"$", ">", "→", "[OK]", "PASS", "TRUE", "true", "0_LOI"}


def _draw_syntax_line(
    draw: ImageDraw.ImageDraw,
    x: float,
    cy: float,
    line: str,
    font: ImageFont.FreeTypeFont,
    max_w: float,
) -> None:
    s = nfc_clean(line)
    # Trim cleanly if single code line exceeds terminal width
    while s and text_metrics(s, font)[0] > max_w and len(s) > 8:
        s = s[:-2] + "…"

    stripped = s.lstrip()
    has_vn = any(ord(ch) > 127 and ch not in "→•…“”‘’—" for ch in s)
    f_vn = load_font("be_bold", max(14, int(round(font.size * 0.94)))) if has_vn else font

    if stripped.startswith("#") and not re.match(r"^#[0-9A-Fa-f]{6}\b", stripped):
        draw_text_centered_y(draw, x, cy, s, f_vn, (124, 142, 168, 245), align_x="left")
        return

    cursor_x = x
    space_adv = max(8 * SS, int(round(text_metrics("M", font)[0] * 0.56)))
    for tok in _TOKEN_RE.findall(s):
        if not tok.strip():
            cursor_x += space_adv * len(tok)
            continue

        tok_has_vn = any(ord(ch) > 127 and ch not in "→•…“”‘’—" for ch in tok)
        tok_font = f_vn if tok_has_vn else font

        if tok in ("[OK]", "PASS", "TRUE", "true", "0_LOI") or tok in ("$", ">", "→") or tok.startswith(("--", "-")):
            if tok == ">":
                _draw_vector_icon(draw, "chevron", cursor_x + 8 * SS, cy, 9 * SS, (45, 212, 191), filled_badge=False)
                cursor_x += 20 * SS
                continue
            col = (45, 212, 191, 255)   # #2DD4BF mint
        elif tok in _KEYWORDS_CYAN or tok.endswith(":"):
            col = (56, 189, 248, 255)   # #38BDF8 cyan
        elif (
            (tok.startswith(('"', "'", "`")) and tok.endswith(('"', "'", "`")))
            or any(tok.endswith(ext) for ext in (".md", ".py", ".json", ".fcproj", ".sh"))
            or re.match(r"^\d", tok)
        ):
            col = (255, 196, 20, 255)   # #FFC414 gold
        else:
            col = (248, 250, 252, 255)  # #F8FAFC crisp white

        draw_text_centered_y(draw, cursor_x, cy, tok, tok_font, col, align_x="left")
        tw, _, _ = text_metrics(tok, tok_font)
        cursor_x += tw


def code_terminal_window(
    out_path: str | Path,
    title: str,
    lines: Sequence[str],
    status_pill: str | None = None,
    accent: str = "cyan",
    pill_accent: str = "mint",
) -> Path:
    """
    Authentic dark macOS IDE / Terminal window:
      - Red/Yellow/Green traffic lights, title bar, optional glowing `status_pill`
      - Muted line numbers + syntax-highlighted tokens (`#38BDF8`, `#2DD4BF`, `#FACC15`, `#F8FAFC`).
    """
    pal = _palette(accent)
    pal_pill = _palette(pill_accent)
    card_w = 900
    pad = 28
    titlebar_h = 56
    line_h = 34
    code_lines = list(lines) if lines else ["# SKILL.md", "name: pro-filmcraft-director", "$ python3 build_master.py --check"]
    body_pad_y = 22
    card_h = titlebar_h + body_pad_y * 2 + len(code_lines) * line_h

    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=22,
        bg_top=(13, 17, 23), bg_bot=(9, 13, 19),
        border_rgb=pal["main"], glow_rgb=pal["main"],
    )
    draw = ImageDraw.Draw(canvas)

    # Titlebar background
    x1 = x0 + card_w * SS
    tb_y1 = y0 + titlebar_h * SS
    draw.rounded_rectangle(
        (x0 + 2 * SS, y0 + 2 * SS, x1 - 2 * SS, tb_y1),
        radius=20 * SS,
        fill=(24, 30, 42, 255),
    )
    draw.rectangle((x0 + 2 * SS, tb_y1 - 16 * SS, x1 - 2 * SS, tb_y1), fill=(24, 30, 42, 255))
    draw.line([(x0 + 2 * SS, tb_y1), (x1 - 2 * SS, tb_y1)], fill=(51, 65, 85, 210), width=2 * SS)

    # Traffic lights (#FF5F56, #FFBD2E, #27C93F)
    tl_cy = y0 + (titlebar_h * SS) / 2.0
    for idx, rgb in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = x0 + (28 + idx * 24) * SS
        r = 7 * SS
        draw.ellipse((cx - r, tl_cy - r, cx + r, tl_cy + r), fill=_rgba(rgb, 255))

    f_title = load_font("mono_bold", 17 * SS)
    f_pill = load_font("mont_bold", 15 * SS)
    f_num = load_font("mono_medium", 17 * SS)
    f_code = load_font("mono_bold", 19 * SS)

    # Status pill on top-right if provided (leaving macOS traffic lights untouched!)
    pill_left = x1 - 22 * SS
    if status_pill:
        pw = text_metrics(status_pill, f_pill)[0] + 28 * SS + 26 * SS
        pill_left = x1 - 18 * SS - pw
        _draw_pill_auto(
            draw, pill_left, y0 + 12 * SS, status_pill, f_pill, pal_pill["main"],
            icon_kind="dot", pad_x=14 * SS, height=32 * SS, center_x=False,
        )

    title_role = "be_bold" if any(ord(c) > 127 for c in str(title)) else "mono_bold"
    title_avail = max(180 * SS, pill_left - (x0 + 112 * SS))
    f_title_fit = fit_font(nfc_clean(title), title_role, int(title_avail), 17 * SS, 13 * SS)
    draw_text_centered_y(draw, x0 + 108 * SS, tl_cy, title, f_title_fit, (203, 213, 225, 245), align_x="left")

    # Gutter line
    gutter_x = x0 + 68 * SS
    draw.line([(gutter_x, tb_y1 + 8 * SS), (gutter_x, y0 + card_h * SS - 10 * SS)], fill=(51, 65, 85, 120), width=SS)

    code_x = gutter_x + 20 * SS
    max_code_w = (x1 - 26 * SS) - code_x
    for idx, raw_ln in enumerate(code_lines, start=1):
        lcy = tb_y1 + (body_pad_y + (idx - 0.5) * line_h) * SS
        draw_text_centered_y(draw, gutter_x - 14 * SS, lcy, f"{idx:02d}", f_num, (100, 116, 139, 195), align_x="right")
        _draw_syntax_line(draw, code_x, lcy, raw_ln, f_code, max_code_w)

    return _save_supersampled(canvas, out_path)


# ---------------------------------------------------------------------------
# 5. `checklist_audit_card`
# ---------------------------------------------------------------------------

def checklist_audit_card(
    out_path: str | Path,
    pill: str,
    rows: Sequence[Any],
    mode: str = "cross",
    theme: str = "red",
    accent: str | None = None,
    active_row: int | None = None,
) -> Path:
    """
    Refined glassmorphism checklist card with dynamic `textbbox` pill width, multi-hue `accent`/`theme`,
    vector icons, and optional `active_row` (`1..N`) Active-Dim focus.
    `mode`: "cross" | "check" | "num"
    `accent` / `theme`: "mint" | "cyan" | "coral" | "violet" | "lime" | "gold" | "red" | "blue"
    """
    pal = _palette(accent if accent is not None else theme)
    acc = pal["main"]
    mode_norm = str(mode or "cross").lower()

    card_w = 860
    pad = 28
    inner_pad = 28
    f_pill = load_font("mont_bold", 18 * SS)
    f_title = load_font("be_extrabold", 23 * SS)
    f_sub = load_font("be_regular", 18 * SS)
    f_num = load_font("mont_black", 19 * SS)

    parsed = [_parse_step_item(r, i + 1) for i, r in enumerate(rows)]
    if not parsed:
        parsed = [("Mục kiểm tra 1", "Chi tiết đánh giá")]

    txt_max_w = (card_w - inner_pad * 2 - 86) * SS
    wrapped = [(wrap_text(t, f_title, txt_max_w, 2), wrap_text(s, f_sub, txt_max_w, 2) if s else []) for t, s in parsed]
    row_heights = [
        max(66, 18 + len(wt) * 31 + (len(ws) * 24 + 4 if ws else 0) + 16)
        for wt, ws in wrapped
    ]
    card_h = inner_pad * 2 + 58 + sum(row_heights) + 12 * max(0, len(wrapped) - 1)

    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=28,
        bg_top=pal["card_bg"], bg_bot=(10, 14, 22),
        border_rgb=acc, glow_rgb=acc,
    )
    fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg_layer)

    pill_icon = "cross" if mode_norm == "cross" else ("check" if mode_norm == "check" else "star")
    _draw_pill_auto(draw, x0 + inner_pad * SS, y0 + inner_pad * SS, pill, f_pill, acc, icon_kind=pill_icon, height=38 * SS, center_x=False)

    ry = y0 + (inner_pad + 58) * SS
    rx0 = x0 + inner_pad * SS
    rx1 = x0 + (card_w - inner_pad) * SS
    for idx, ((wt, ws), rh) in enumerate(zip(wrapped, row_heights), start=1):
        focus_mode, is_act = _is_active_bento_item(idx - 1, active_row)
        ry1 = ry + rh * SS
        r_fill = (255, 255, 255, 22) if (focus_mode and is_act) else ((8, 12, 20, 145) if focus_mode else (255, 255, 255, 13))
        r_out = _rgba(acc, 215 if (focus_mode and is_act) else (44 if focus_mode else 78))
        draw.rounded_rectangle(
            (rx0, ry, rx1, ry1),
            radius=16 * SS,
            fill=r_fill,
            outline=r_out,
            width=max(1, int((2.2 if (focus_mode and is_act) else 1.5) * SS)),
        )
        icx = rx0 + 36 * SS
        icy = (ry + ry1) / 2.0
        ic_rgb = acc if is_act else (100, 116, 139)
        if mode_norm == "num":
            draw.ellipse((icx - 18 * SS, icy - 18 * SS, icx + 18 * SS, icy + 18 * SS), fill=_rgba(ic_rgb, 44), outline=_rgba(ic_rgb, 230 if is_act else 110), width=2 * SS)
            draw_text_centered_y(draw, icx, icy, f"{idx:02d}", f_num, _rgba(ic_rgb, 255 if is_act else 145), align_x="center")
        elif mode_norm == "check":
            _draw_vector_icon(draw, "check", icx, icy, 17 * SS, ic_rgb, filled_badge=True)
        else:
            _draw_vector_icon(draw, "cross", icx, icy, 17 * SS, ic_rgb, filled_badge=True)

        t_fg = (248, 250, 252, 255) if is_act else (148, 163, 184, 140)
        s_fg = (194, 206, 224, 228) if is_act else (118, 134, 156, 120)
        total_th = len(wt) * 31 * SS + (len(ws) * 24 * SS + 4 * SS if ws else 0)
        ty = icy - total_th / 2.0 + 15 * SS
        for ln in wt:
            draw_text_centered_y(draw, rx0 + 74 * SS, ty, ln, f_title, t_fg, align_x="left")
            ty += 31 * SS
        ty += 4 * SS
        for ln in ws:
            draw_text_centered_y(draw, rx0 + 74 * SS, ty, ln, f_sub, s_fg, align_x="left")
            ty += 24 * SS

        ry = ry1 + 12 * SS

    return _save_supersampled(Image.alpha_composite(canvas, fg_layer), out_path)


# ---------------------------------------------------------------------------
# 6. `quote_editorial_note`
# ---------------------------------------------------------------------------

def quote_editorial_note(
    out_path: str | Path,
    quote: str,
    author_or_tag: str,
    dark: bool = True,
    accent: str = "gold",
) -> Path:
    """
    Editorial paper/glass quote card (`Playfair Display` / `Be Vietnam Pro` with geometric vector
    quotation marks and semantic `accent` vertical bar — tailored for `minimal_intellectual` & story videos).
    """
    card_w = 860
    pad = 28
    inner_pad = 36
    pal = _palette(accent)

    if dark:
        bg_top, bg_bot = (20, 23, 32), (13, 15, 22)
        accent_rgb = pal["main"]
        border_rgb = pal["main"]
        quote_fg = (250, 246, 238, 255)
        tag_fg = _rgba(pal["main"], 245)
        qmark_col = _rgba(pal["main"], 68)
    else:
        bg_top, bg_bot = (251, 248, 241), (242, 236, 223)
        accent_rgb = (180, 118, 28) if str(accent).lower() == "gold" else pal["main"]
        border_rgb = (206, 192, 168)
        quote_fg = (24, 26, 32, 255)
        tag_fg = (146, 92, 18, 255) if str(accent).lower() == "gold" else _rgba(accent_rgb, 245)
        qmark_col = _rgba(accent_rgb, 52)

    f_quote = load_font("playfair_italic", 30 * SS)
    f_qmark = load_font("playfair_italic", 112 * SS)
    f_tag = load_font("mont_bold", 18 * SS)

    text_x_offset = 64
    max_qw = (card_w - inner_pad * 2 - text_x_offset - 12) * SS
    q_lines = wrap_text(quote, f_quote, max_qw, max_lines=5)
    line_h = 44

    content_h = max(110, len(q_lines) * line_h + 56)
    card_h = inner_pad * 2 + content_h

    canvas, x0, y0 = _make_card_canvas(
        card_w, card_h, pad, radius=26,
        bg_top=bg_top, bg_bot=bg_bot,
        border_rgb=border_rgb, glow_rgb=accent_rgb if dark else None,
        bg_alpha=246,
    )
    draw = ImageDraw.Draw(canvas)

    # Oversized editorial opening quote glyph
    draw.text((x0 + (inner_pad + 12) * SS, y0 + (inner_pad - 24) * SS), "“", font=f_qmark, fill=qmark_col)

    # Vertical editorial accent bar
    bar_x = x0 + inner_pad * SS
    bar_y0 = y0 + (inner_pad + 8) * SS
    bar_y1 = y0 + (card_h - inner_pad - 8) * SS
    draw.rounded_rectangle(
        (bar_x, bar_y0, bar_x + 6 * SS, bar_y1),
        radius=3 * SS,
        fill=_rgba(accent_rgb, 245),
    )

    tx = x0 + (inner_pad + text_x_offset - 28) * SS
    ty = y0 + (inner_pad + 24) * SS
    for ln in q_lines:
        draw_text_centered_y(draw, tx, ty, ln, f_quote, quote_fg, align_x="left")
        ty += line_h * SS

    # Author / editorial tag line
    tag_clean = nfc_clean(author_or_tag)
    if tag_clean and not tag_clean.startswith(("—", "-")):
        tag_clean = f"— {tag_clean}"
    tag_y = y0 + (card_h - inner_pad - 14) * SS
    draw_text_centered_y(draw, tx, tag_y, tag_clean.upper(), f_tag, tag_fg, align_x="left")

    return _save_supersampled(canvas, out_path)


# ---------------------------------------------------------------------------
# 7. `strike_myth_banner`
# ---------------------------------------------------------------------------

def strike_myth_banner(
    out_path: str | Path,
    myth_text: str,
    truth_text: str,
    accent: str = "mint",
    myth_accent: str = "red",
    badge_accent: str = "gold",
) -> Path:
    """
    Dual-tier Myth vs Truth banner:
      - Top: Crimson/Coral-struck-through misconception bar with crisp angled vector strikethrough slash
      - Bottom: Glowing semantic `accent` (`mint`, `lime`, `cyan`, `violet`, ...) & `badge_accent` truth bar!
    """
    pal_truth = _palette(accent)
    pal_myth = _palette(myth_accent)
    pal_badge = _palette(badge_accent)

    card_w = 900
    pad = 28
    tier_gap = 18
    f_badge = load_font("mont_black", 16 * SS)
    f_myth = load_font("be_bold", 23 * SS)
    f_truth = load_font("be_extrabold", 25 * SS)

    txt_max_w = (card_w - 208) * SS
    m_lines = wrap_text(myth_text, f_myth, txt_max_w, max_lines=2)
    t_lines = wrap_text(truth_text, f_truth, txt_max_w, max_lines=2)

    myth_h = max(86, 30 + len(m_lines) * 32)
    truth_h = max(96, 34 + len(t_lines) * 35)
    card_h = myth_h + tier_gap + truth_h

    W = (card_w + pad * 2) * SS
    H = (card_h + pad * 2) * SS
    x0, y0 = pad * SS, pad * SS
    x1 = x0 + card_w * SS

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Drop shadow for both bars
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((x0 + 2 * SS, y0 + 8 * SS, x1 + 2 * SS, y0 + (myth_h + 10) * SS), radius=20 * SS, fill=(0, 0, 0, 130))
    ty0 = y0 + (myth_h + tier_gap) * SS
    ty1 = ty0 + truth_h * SS
    sd.rounded_rectangle((x0 + 2 * SS, ty0 + 10 * SS, x1 + 2 * SS, ty1 + 12 * SS), radius=22 * SS, fill=(0, 0, 0, 155))
    canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(radius=12 * SS)))

    red_rgb = pal_myth["main"]
    mint_rgb = pal_truth["main"]
    gold_rgb = pal_badge["main"]

    # Ambient semantic glow under Truth bar
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).rounded_rectangle(
        (x0 - 2 * SS, ty0 - 2 * SS, x1 + 2 * SS, ty1 + 2 * SS),
        radius=24 * SS,
        outline=_rgba(mint_rgb, 125),
        width=4 * SS,
    )
    canvas = Image.alpha_composite(canvas, gl.filter(ImageFilter.GaussianBlur(radius=9 * SS)))

    draw = ImageDraw.Draw(canvas)

    # --- Top Myth Bar ---
    my1 = y0 + myth_h * SS
    draw.rounded_rectangle(
        (x0, y0, x1, my1),
        radius=20 * SS,
        fill=_rgba(pal_myth["card_bg"], 232),
        outline=_rgba(red_rgb, 155),
        width=2 * SS,
    )
    m_cy = (y0 + my1) / 2.0
    # "SAI LẦM" badge with crisp vector cross icon (zero font-glyph dependency)
    draw.rounded_rectangle(
        (x0 + 20 * SS, m_cy - 19 * SS, x0 + 156 * SS, m_cy + 19 * SS),
        radius=19 * SS,
        fill=_rgba(red_rgb, 48),
        outline=_rgba(red_rgb, 215),
        width=2 * SS,
    )
    _draw_vector_icon(draw, "cross", x0 + 42 * SS, m_cy, 9 * SS, pal_myth["bright"], filled_badge=False)
    draw_text_centered_y(draw, x0 + 98 * SS, m_cy, "SAI LẦM", f_badge, _rgba(pal_myth["bright"], 255), align_x="center")

    mtx = x0 + 178 * SS
    total_mh = len(m_lines) * 32 * SS
    mty = m_cy - total_mh / 2.0 + 16 * SS
    max_mw = 0
    for ln in m_lines:
        w_ln, _ = draw_text_centered_y(draw, mtx, mty, ln, f_myth, (226, 205, 210, 225), align_x="left")
        max_mw = max(max_mw, w_ln)
        mty += 32 * SS

    # Crisp angled vector strikethrough slash across myth text
    sx0 = mtx - 6 * SS
    sx1 = min(x1 - 24 * SS, mtx + max_mw + 10 * SS)
    sy0 = m_cy + 11 * SS
    sy1 = m_cy - 11 * SS
    draw.line([(sx0, sy0), (sx1, sy1)], fill=(24, 10, 14, 175), width=6 * SS)
    draw.line([(sx0, sy0), (sx1, sy1)], fill=_rgba(red_rgb, 240), width=3 * SS)

    # --- Bottom Truth Bar ---
    draw.rounded_rectangle(
        (x0, ty0, x1, ty1),
        radius=22 * SS,
        fill=_rgba(pal_truth["card_bg"], 244),
        outline=_rgba(mint_rgb, 235),
        width=2 * SS,
    )
    t_cy = (ty0 + ty1) / 2.0
    draw.rounded_rectangle(
        (x0 + 20 * SS, t_cy - 20 * SS, x0 + 156 * SS, t_cy + 20 * SS),
        radius=20 * SS,
        fill=_rgba(gold_rgb, 42),
        outline=_rgba(gold_rgb, 235),
        width=2 * SS,
    )
    _draw_vector_icon(draw, "check", x0 + 42 * SS, t_cy, 10 * SS, gold_rgb, filled_badge=False)
    draw_text_centered_y(draw, x0 + 98 * SS, t_cy, "SỰ THẬT", f_badge, _rgba(gold_rgb, 255), align_x="center")

    ttx = x0 + 178 * SS
    total_th = len(t_lines) * 35 * SS
    tty = t_cy - total_th / 2.0 + 17 * SS
    for ln in t_lines:
        draw_text_centered_y(draw, ttx, tty, ln, f_truth, (248, 250, 252, 255), align_x="left")
        tty += 35 * SS

    return _save_supersampled(canvas, out_path)


# ---------------------------------------------------------------------------
# 8. `polaroid_callout`
# ---------------------------------------------------------------------------

def _load_or_placeholder_photo(image_path: str | Path | None, target_w: int, target_h: int) -> Image.Image:
    if image_path and Path(image_path).is_file():
        with Image.open(image_path) as src:
            return ImageOps.fit(src.convert("RGBA"), (target_w, target_h), method=Image.Resampling.LANCZOS)
    # Graceful studio placeholder if image_path is None or synthetic
    arr = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    y_lin = np.linspace(0, 1, target_h, dtype=np.float32)[:, None]
    x_lin = np.linspace(0, 1, target_w, dtype=np.float32)[None, :]
    arr[:, :, 0] = np.clip(18 + 38 * x_lin, 0, 255).astype(np.uint8)
    arr[:, :, 1] = np.clip(28 + 64 * (1 - y_lin), 0, 255).astype(np.uint8)
    arr[:, :, 2] = np.clip(52 + 88 * x_lin * (1 - y_lin), 0, 255).astype(np.uint8)
    arr[:, :, 3] = 255
    ph = Image.fromarray(arr, mode="RGBA")
    d = ImageDraw.Draw(ph)
    step = 40 * SS
    for gx in range(0, target_w, step):
        d.line([(gx, 0), (gx, target_h)], fill=(255, 255, 255, 22), width=SS)
    for gy in range(0, target_h, step):
        d.line([(0, gy), (target_w, gy)], fill=(255, 255, 255, 22), width=SS)
    return ph


def polaroid_callout(
    out_path: str | Path,
    image_path: str | Path | None,
    caption: str,
    tilt_deg: float = -2.5,
    accent: str | None = None,
) -> Path:
    """
    Crops/frames a screenshot or B-roll still inside a clean Polaroid/editorial card
    with soft drop shadow and caption strip (plus optional semantic `accent` trim), tilted cleanly at `tilt_deg`.
    """
    frame_w = 640 * SS
    border = 24 * SS
    photo_w = frame_w - border * 2
    photo_h = 440 * SS

    f_cap = load_font("be_bold", 24 * SS)
    cap_lines = wrap_text(caption, f_cap, photo_w - 20 * SS, max_lines=2)
    bottom_strip_h = (88 + (len(cap_lines) - 1) * 30) * SS
    frame_h = border + photo_h + bottom_strip_h

    polaroid = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(polaroid)
    out_rgb = _palette(accent)["main"] if accent is not None else (226, 232, 240)
    pd.rounded_rectangle(
        (0, 0, frame_w - 1, frame_h - 1),
        radius=16 * SS,
        fill=(250, 249, 246, 255),
        outline=_rgba(out_rgb, 240 if accent is not None else 255),
        width=2 * SS,
    )

    photo = _load_or_placeholder_photo(image_path, photo_w, photo_h)
    photo_mask = Image.new("L", (photo_w, photo_h), 0)
    ImageDraw.Draw(photo_mask).rounded_rectangle((0, 0, photo_w - 1, photo_h - 1), radius=8 * SS, fill=255)
    polaroid.paste(photo, (border, border), photo_mask)

    # Subtle inner hairline around photo
    pd.rounded_rectangle(
        (border, border, border + photo_w - 1, border + photo_h - 1),
        radius=8 * SS,
        outline=(15, 23, 42, 42),
        width=max(1, SS),
    )

    # Caption centered in bottom strip
    strip_cy = border + photo_h + bottom_strip_h / 2.0
    total_ch = len(cap_lines) * 32 * SS
    cy_line = strip_cy - total_ch / 2.0 + 16 * SS
    for ln in cap_lines:
        draw_text_centered_y(pd, frame_w / 2.0, cy_line, ln, f_cap, (30, 41, 59, 255), align_x="center")
        cy_line += 32 * SS

    # Shadow matching polaroid geometry before rotation
    pad_rot = 64 * SS
    stage = Image.new("RGBA", (frame_w + pad_rot * 2, frame_h + pad_rot * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", stage.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (pad_rot + 6 * SS, pad_rot + 14 * SS, pad_rot + frame_w + 6 * SS, pad_rot + frame_h + 16 * SS),
        radius=16 * SS,
        fill=(0, 0, 0, 150),
    )
    sh = sh.filter(ImageFilter.GaussianBlur(radius=16 * SS))
    stage = Image.alpha_composite(stage, sh)
    stage.alpha_composite(polaroid, (pad_rot, pad_rot))

    if abs(float(tilt_deg)) > 0.02:
        # PIL rotate is counter-clockwise; negative tilt_deg tilts counter-clockwise or clockwise intuitively
        stage = stage.rotate(-float(tilt_deg), resample=Image.Resampling.BICUBIC, expand=True)

    # Crop excess empty transparent border while preserving full soft shadow + small margin
    abbox = stage.getchannel("A").getbbox()
    if abbox:
        m = 10 * SS
        x0 = max(0, abbox[0] - m)
        y0 = max(0, abbox[1] - m)
        x1 = min(stage.width, abbox[2] + m)
        y1 = min(stage.height, abbox[3] + m)
        # Ensure even dimensions for clean 2x downsample
        if (x1 - x0) % 2:
            x1 = min(stage.width, x1 + 1)
        if (y1 - y0) % 2:
            y1 = min(stage.height, y1 + 1)
        stage = stage.crop((x0, y0, x1, y1))

    return _save_supersampled(stage, out_path)


# ---------------------------------------------------------------------------
# 9. `floating_pill_badge`
# ---------------------------------------------------------------------------

def floating_pill_badge(
    out_path: str | Path,
    text: str,
    icon_kind: str = "dot",
    accent: str = "mint",
) -> Path:
    """
    Compact glassmorphism chapter/status pill (~84px tall, dynamically `textbbox`-sized width)
    for minimalist lower-third or top-corner tags without blocking the frame.
    `icon_kind`: "dot" | "bolt" | "star" | "spark" | "check" | "lock" | "arrow" | "aperture"
    """
    pal = _palette(accent)
    acc = pal["main"]
    eff_icon = _extract_emoji_icon_hint(text, str(icon_kind or "dot").lower()) or "dot"
    clean = nfc_clean(text)

    pill_h = 84
    pad = 18
    f_txt = fit_font(clean, "be_extrabold", 680 * SS, 26 * SS, 18 * SS)
    tw, _, _ = text_metrics(clean, f_txt)

    # Auto-sized width in 1x pixels (minimum 260, comfortable padding, max 880)
    pill_w = max(260, min(880, int(math.ceil(tw / SS)) + 124))

    canvas, x0, y0 = _make_card_canvas(
        pill_w, pill_h, pad, radius=pill_h // 2,
        bg_top=(15, 23, 36), bg_bot=(10, 15, 25),
        border_rgb=acc, glow_rgb=acc,
        bg_alpha=236, shadow_alpha=125,
    )
    draw = ImageDraw.Draw(canvas)

    cy = y0 + (pill_h * SS) / 2.0
    icx = x0 + 44 * SS
    _draw_vector_icon(draw, eff_icon, icx, cy, 18 * SS, acc, filled_badge=True)
    draw_text_centered_y(draw, x0 + 78 * SS, cy, clean, f_txt, (248, 250, 252, 255), align_x="left")

    total_w = pill_w + pad * 2
    total_h = pill_h + pad * 2
    icx_1x = pad + 44
    icy_1x = total_h // 2
    return _save_supersampled(
        canvas,
        out_path,
        anchor_shape_xyr={
            "cx_pct": round(icx_1x / float(total_w), 6),
            "cy_pct": 0.50,
            "r_pct_w": round(18.0 / float(total_w), 6),
            "cx_px": icx_1x,
            "cy_px": icy_1x,
            "r_px": 18,
            "shape": "circle",
        },
    )


# ---------------------------------------------------------------------------
# 10. `clean_alpha_prop`
# ---------------------------------------------------------------------------

def clean_alpha_prop(
    src_path: str | Path,
    out_path: str | Path,
    keep_region: Sequence[float] | None = None,
) -> Path:
    """
    Inspects an RGBA 3D prop PNG for disconnected secondary rectangular swatch artifacts
    (or masks outside `keep_region`), re-centers the clean alpha symmetrically on canvas,
    and strips all PNG metadata.

    `keep_region`: optional `[x0, y0, x1, y1]` in pixels (or normalized `0.0..1.0` floats if all <= 1.0).
    """
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"clean_alpha_prop: source file not found: {src}")

    with Image.open(src) as im:
        arr = np.array(im.convert("RGBA"), dtype=np.uint8)

    H, W = arr.shape[:2]
    alpha = arr[:, :, 3].copy()

    # 1. Optional explicit `keep_region` mask
    if keep_region is not None and len(keep_region) == 4:
        kx0, ky0, kx1, ky1 = [float(v) for v in keep_region]
        if max(abs(kx0), abs(ky0), abs(kx1), abs(ky1)) <= 1.0001:
            ix0, iy0 = int(round(kx0 * W)), int(round(ky0 * H))
            ix1, iy1 = int(round(kx1 * W)), int(round(ky1 * H))
        else:
            ix0, iy0, ix1, iy1 = int(round(kx0)), int(round(ky0)), int(round(kx1)), int(round(ky1))
        ix0, iy0 = max(0, min(W, ix0)), max(0, min(H, iy0))
        ix1, iy1 = max(0, min(W, ix1)), max(0, min(H, iy1))
        reg_mask = np.zeros((H, W), dtype=np.uint8)
        reg_mask[iy0:iy1, ix0:ix1] = 1
        alpha = alpha * reg_mask

    # 2. Connected-components inspection for disconnected solid rectangular swatches & stray specks
    fg_bin = (alpha > 8).astype(np.uint8)
    n_comp, labels, stats, _centroids = cv2.connectedComponentsWithStats(fg_bin, connectivity=8)

    if n_comp > 2:
        comps = []
        for cid in range(1, n_comp):
            cx, cy, cw, ch, area = [int(v) for v in stats[cid]]
            fill_ratio = area / max(1.0, float(cw * ch))
            comps.append({
                "id": cid,
                "bbox": (cx, cy, cx + cw, cy + ch),
                "w": cw,
                "h": ch,
                "area": area,
                "fill": fill_ratio,
            })

        # Prefer largest non-solid-rectangle component as primary prop if an organic object exists
        organic = [c for c in comps if not (c["fill"] > 0.935 and c["w"] > 40 and c["h"] > 40)]
        primary = max(organic or comps, key=lambda c: c["area"])
        px0, py0, px1, py1 = primary["bbox"]

        keep_ids = {primary["id"]}
        for c in comps:
            if c["id"] == primary["id"]:
                continue
            # Drop tiny alpha dust specks (< 0.4% of primary area)
            if c["area"] < max(24, int(primary["area"] * 0.004)):
                continue
            # Drop disconnected solid rectangular color-swatch blocks (e.g. fill >= 0.92)
            if c["fill"] >= 0.92 and c["w"] >= 28 and c["h"] >= 28:
                continue
            # Keep nearby legitimate sub-parts (floating icon elements within 28px of primary bbox)
            bx0, by0, bx1, by1 = c["bbox"]
            gap_x = max(0, px0 - bx1, bx0 - px1)
            gap_y = max(0, py0 - by1, by0 - py1)
            if math.hypot(gap_x, gap_y) <= max(28.0, min(W, H) * 0.055):
                keep_ids.add(c["id"])

        keep_mask = np.isin(labels, list(keep_ids))
        # Dilate by 2px so soft anti-aliased fringes (<8 alpha) around kept components stay silky
        keep_mask_u8 = cv2.dilate(keep_mask.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=1)
        alpha = alpha * keep_mask_u8

    arr[:, :, 3] = alpha

    # 3. Re-center clean prop symmetrically inside canvas
    ys, xs = np.where(alpha > 4)
    out_arr = np.zeros_like(arr)
    if len(xs) > 0 and len(ys) > 0:
        bx0, bx1 = int(xs.min()), int(xs.max()) + 1
        by0, by1 = int(ys.min()), int(ys.max()) + 1
        crop = arr[by0:by1, bx0:bx1]
        ch, cw = crop.shape[:2]
        dst_x = max(0, (W - cw) // 2)
        dst_y = max(0, (H - ch) // 2)
        out_arr[dst_y : dst_y + ch, dst_x : dst_x + cw] = crop
    else:
        out_arr = arr

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out_arr, mode="RGBA").save(out, format="PNG", optimize=True)
    strip_png_metadata(out)
    return out


# ---------------------------------------------------------------------------
# 11. `clean_broll_plate` & Stateless `lint_broll_prompt` (`v5.1` Hygiene)
# ---------------------------------------------------------------------------

class BrollPlateResult(type(Path())):
    """
    `pathlib.Path` subclass returned by `clean_broll_plate`:
      - Behaves 100% identically to `Path` (`isinstance(p, Path)`, `Image.open(p)`, `str(p)`).
      - Also exposes `.grayscale_std`, `.trimmed_borders`, `.is_flat`, `.warning`, `.warnings`, and `p[key]` access!
    """
    grayscale_std: float = 0.0
    trimmed_borders: dict[str, int] = {}
    is_flat: bool = False
    warning: str | None = None
    warnings: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "out_path": str(self),
            "grayscale_std": self.grayscale_std,
            "trimmed_borders": dict(self.trimmed_borders),
            "is_flat": self.is_flat,
            "warning": self.warning,
            "warnings": list(self.warnings),
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


def _trim_uniform_borders(
    img: Image.Image,
    min_px: int = 8,
    std_max: float = 3.0,
    jump: float = 30.0,
) -> tuple[Image.Image, dict[str, int]]:
    """
    Port of `broll.py:_trim_uniform_borders` (`1.2.2 F3`):
      - Detects contiguous top/bottom/left/right uniform white (`mean > 240`) or black (`mean < 12`) border bands
        with `>= min_px` (`8px`), per-line `std < 3.0`, AND sharp boundary step `abs(inner_mean - border_mean) > 30.0`
        (plus local edge step `abs(inner_mean - pre_step_mean) > 30.0` so wide smooth studio gradients stay untouched).
      - Evaluates top/bottom first, then left/right on the cropped slice so mixed letterbox + pillarbox bars are caught.
    """
    def _band(lines: np.ndarray) -> int:
        n = 0
        for row in lines:
            m = float(row.mean())
            if float(row.std()) < std_max and (m > 240.0 or m < 12.0):
                n += 1
            else:
                break
        if n < min_px or n + min_px > len(lines):
            return 0
        inner_mean = float(lines[n : n + min_px].mean())
        border_mean = float(lines[:n].mean())
        edge_mean = float(lines[n - min_px : n].mean())
        if abs(inner_mean - border_mean) > jump and abs(inner_mean - edge_mean) > jump:
            return n
        return 0

    g0 = np.asarray(img.convert("L"), dtype=np.float32)
    top = _band(g0)
    bottom = _band(g0[::-1])
    if top + bottom >= img.height - min_px * 2:
        top, bottom = 0, 0
    cur = img.crop((0, top, img.width, img.height - bottom)) if (top or bottom) else img

    g1 = np.asarray(cur.convert("L"), dtype=np.float32)
    left = _band(g1.T)
    right = _band(g1.T[::-1])
    if left + right >= cur.width - min_px * 2:
        left, right = 0, 0
    if left or right:
        cur = cur.crop((left, 0, cur.width - right, cur.height))

    # Optional second vertical check in case solid side pillarboxes masked a top/bottom bar
    if (left or right) and not (top or bottom):
        g2 = np.asarray(cur.convert("L"), dtype=np.float32)
        t2, b2 = _band(g2), _band(g2[::-1])
        if 0 < (t2 + b2) < cur.height - min_px * 2:
            cur = cur.crop((0, t2, cur.width, cur.height - b2))
            top, bottom = t2, b2

    return cur, {"left": int(left), "top": int(top), "right": int(right), "bottom": int(bottom)}


def clean_broll_plate(
    src_path: str | Path,
    out_path: str | Path,
    target_size: Sequence[int] = (1080, 1920),
    flat_std_min: float = 30.0,
    strict_flat: bool = False,
    jpeg_quality: int = 92,
) -> BrollPlateResult:
    """
    Primitive #11 (`v5.1`): Post-processes an AI/stock B-roll still plate into a clean `1080x1920` frame:
      1. Trims synthetic uniform white/black borders (`_trim_uniform_borders`) while preserving smooth studio gradients.
      2. Scales & center-crops cleanly with `LANCZOS` to `target_size` (`(1080, 1920)`).
      3. Verifies luminance contrast `grayscale_std >= 30.0` (emits `UserWarning` + populates `.warning` if flat;
         raises `ValueError` when `strict_flat=True`).
      4. Saves cleanly (PNG/JPEG/WebP inferred from `out_path`) and strips all container/EXIF/XMP/C2PA metadata.
    """
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"clean_broll_plate: source file not found: {src}")
    if len(target_size) != 2:
        raise ValueError(f"target_size must be (width, height), got {target_size!r}")

    tw, th = max(16, int(target_size[0])), max(16, int(target_size[1]))
    with Image.open(src) as im_raw:
        im_oriented = ImageOps.exif_transpose(im_raw)
        img = im_oriented.convert("RGB")

    trimmed_img, borders = _trim_uniform_borders(img)
    scale_k = max(tw / trimmed_img.width, th / trimmed_img.height)
    resized_w = max(tw, int(round(trimmed_img.width * scale_k)))
    resized_h = max(th, int(round(trimmed_img.height * scale_k)))
    scaled = trimmed_img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    cx = (scaled.width - tw) // 2
    cy = (scaled.height - th) // 2
    final = scaled.crop((cx, cy, cx + tw, cy + th))

    gray_std = float(np.asarray(final.convert("L"), dtype=np.float32).std())
    is_flat = gray_std < float(flat_std_min)
    warn_msg: str | None = None
    if is_flat:
        warn_msg = (
            f"BROLL_FLAT: {Path(out_path).name} has low luminance contrast "
            f"(grayscale_std={gray_std:.1f} < {flat_std_min:g}) — rewrite prompt with clear subject, "
            f"key/rim lighting contrast, and foreground-background depth."
        )
        warnings.warn(warn_msg, UserWarning, stacklevel=2)
        if strict_flat:
            raise ValueError(warn_msg)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ext = out.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        final.save(out, format="JPEG", quality=int(jpeg_quality), optimize=True)
    elif ext == ".webp":
        final.save(out, format="WEBP", quality=int(jpeg_quality))
    else:
        final.save(out, format="PNG", optimize=True)
    strip_image_metadata(out)

    res = BrollPlateResult(out)
    res.grayscale_std = round(gray_std, 2)
    res.trimmed_borders = borders
    res.is_flat = is_flat
    res.warning = warn_msg
    res.warnings = [warn_msg] if warn_msg else []
    return res


# Ported 46-token anti-slop hallucination banlist from `opa-video-studio` `broll_plan.py` (`1.2.3 F2`)
BROLL_BANNED_TOKENS: tuple[str, ...] = (
    "logo", "watermark", "text", "subtitle",
    # 1.2.2 F2: layout splits, fake labels, hallucinated charts/metrics, branded platforms/devices, IP characters
    "side-by-side", "split screen", "comparison", "label", "labels", "caption", "captions", "annotation", "annotations",
    "notes", "graph", "chart", "metrics", "analytics", "statistics", "engagement", "youtube", "tiktok", "facebook",
    "instagram", "iphone", "macbook", "apple", "samsung", "google", "game character",
    # 1.2.3 F2: sticky notes, checklists, handwriting, chat/messaging bubbles
    "note", "checklist", "checklists", "checkbox", "checkboxes", "written", "bullet", "bullets", "handwritten",
    "handwriting", "chat", "chatting", "message", "messages", "messaging", "texting",
)

_VI_DIACRITICS_RE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)

_BANNED_HINT_GROUPS: list[tuple[frozenset[str], str]] = [
    (
        frozenset({"side-by-side", "split screen", "comparison"}),
        "Describe ONE unified physical scene instead of a split/comparison frame (use `versus_split_card` for comparisons).",
    ),
    (
        frozenset({"graph", "chart", "metrics", "analytics", "statistics", "engagement"}),
        "Depict outcomes through human emotion or physical action (e.g. 'a relieved founder smiling in a warm studio'); render real numbers with `metric_kpi_hero`.",
    ),
    (
        frozenset({"note", "notes", "checklist", "checklists", "checkbox", "checkboxes", "written", "bullet", "bullets", "handwritten", "handwriting"}),
        "Avoid paper notes, checklists, or handwriting (AI models hallucinate garbled text); show clean desk props or use `checklist_audit_card`.",
    ),
    (
        frozenset({"chat", "chatting", "message", "messages", "messaging", "texting"}),
        "Avoid chat screens or message bubbles; show a person reacting naturally while holding a generic unbranded smartphone seen from behind/side.",
    ),
    (
        frozenset({"youtube", "tiktok", "facebook", "instagram", "google"}),
        "Replace platform names with 'a generic unbranded dark interface' or focus on the human creator and studio lighting.",
    ),
    (
        frozenset({"iphone", "macbook", "apple", "samsung"}),
        "Replace brand hardware names with 'a sleek unbranded aluminum laptop' or 'a modern bezel-less smartphone without logos'.",
    ),
    (
        frozenset({"logo", "watermark", "text", "subtitle", "label", "labels", "caption", "captions", "annotation", "annotations"}),
        "Never mention text, labels, logos, or watermarks in positive prompts (mentioning them triggers text generation); describe pure visual surfaces.",
    ),
    (
        frozenset({"game character"}),
        "Describe an original real-world human subject (age, hair, wardrobe, lighting) rather than a copyrighted game character.",
    ),
]


def _hint_for_banned_token(tok: str) -> str:
    for group_set, hint in _BANNED_HINT_GROUPS:
        if tok in group_set:
            return hint
    return f"Remove '{tok}' and describe concrete physical lighting, subject action, and unbranded objects."


def lint_broll_prompt(prompt: str, min_words: int = 8, max_words: int = 95) -> dict[str, Any]:
    """
    Stateless B-Roll Prompt Hygiene Linter (`v5.1`, ported from `broll_plan.py` `1.2.3 F2`):
      - Checks word count (`8..95` words).
      - Rejects Vietnamese diacritics (prompts for image/video generators must be English).
      - Scans all 46 anti-slop hallucination tokens (`side-by-side`, `split screen`, `graph`, `chart`,
        `metrics`, `checklist`, `handwritten`, `chat`, `youtube`, `tiktok`, `iphone`, `macbook`, `logo`, `watermark`, ...)
        and returns actionable replacement hints.
    """
    norm = unicodedata.normalize("NFC", str(prompt or "")).strip()
    words = norm.split() if norm and norm != "?" else []
    word_count = len(words)

    errors: list[str] = []
    hints: list[str] = []
    replacements: dict[str, str] = {}

    if not norm or norm == "?":
        errors.append("Prompt is empty or placeholder '?'.")
        hints.append(
            f"Write an English cinematic description ({min_words}–{max_words} words) specifying subject, action, camera framing, and lighting."
        )
    elif word_count < min_words or word_count > max_words:
        errors.append(f"Word count is {word_count} (must be {min_words}–{max_words} words).")
        if word_count < min_words:
            hints.append(
                f"Expand prompt to at least {min_words} words by adding camera framing (e.g. medium close-up, shallow depth of field) and studio lighting."
            )
        else:
            hints.append(
                f"Trim prompt to at most {max_words} words; focus on one clear subject, environment, and lighting mood."
            )

    has_vi = bool(_VI_DIACRITICS_RE.search(norm))
    if has_vi:
        errors.append("Prompt contains Vietnamese diacritics (must be 100% English).")
        hints.append("Translate the visual scene description into natural English with zero Vietnamese words or accents.")

    low = norm.lower()
    banned_hits: list[str] = []
    seen_hints: set[str] = set()
    for tok in BROLL_BANNED_TOKENS:
        pat = r"[-\s]+".join(re.escape(part) for part in re.split(r"[-\s]+", tok) if part)
        if re.search(rf"\b{pat}\b", low):
            banned_hits.append(tok)
            h = _hint_for_banned_token(tok)
            replacements[tok] = h
            if h not in seen_hints:
                seen_hints.add(h)
                hints.append(h)

    if banned_hits:
        errors.append("Banned anti-slop tokens detected: " + ", ".join(banned_hits))

    ok = len(errors) == 0
    return {
        "ok": ok,
        "valid": ok,
        "word_count": word_count,
        "word_count_range": [int(min_words), int(max_words)],
        "has_vietnamese": has_vi,
        "banned_hits": banned_hits,
        "errors": errors,
        "hints": hints,
        "replacements": replacements,
    }


# ---------------------------------------------------------------------------
# 12 & 13. `@__dviet × @vietanh` Editorial Viewfinder & Compact Lock Badge (`v5.2`)
# ---------------------------------------------------------------------------

def _draw_viewfinder_brackets(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    rgb: tuple[int, int, int],
    arm_len: float,
    stroke_w: int,
) -> None:
    """Draw 4 crisp L-shaped camera AF focus brackets + subtle center reticle."""
    col = _rgba(rgb, 245)
    # Top-Left
    draw.line([(x0, y0 + arm_len), (x0, y0), (x0 + arm_len, y0)], fill=col, width=stroke_w, joint="curve")
    # Top-Right
    draw.line([(x1 - arm_len, y0), (x1, y0), (x1, y0 + arm_len)], fill=col, width=stroke_w, joint="curve")
    # Bottom-Left
    draw.line([(x0, y1 - arm_len), (x0, y1), (x0 + arm_len, y1)], fill=col, width=stroke_w, joint="curve")
    # Bottom-Right
    draw.line([(x1 - arm_len, y1), (x1, y1), (x1, y1 - arm_len)], fill=col, width=stroke_w, joint="curve")

    # Center micro-crosshair
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    cr = arm_len * 0.34
    gap = arm_len * 0.11
    c_col = _rgba(rgb, 185)
    thin = max(1, stroke_w // 2)
    draw.line([(cx - cr, cy), (cx - gap, cy)], fill=c_col, width=thin)
    draw.line([(cx + gap, cy), (cx + cr, cy)], fill=c_col, width=thin)
    draw.line([(cx, cy - cr), (cx, cy - gap)], fill=c_col, width=thin)
    draw.line([(cx, cy + gap), (cx, cy + cr)], fill=c_col, width=thin)


def viewfinder_raw_card(
    out_path: str | Path,
    image_path: str | Path | None = None,
    caption: str = "Bằng chứng thực tế",
    rec_label: str = "REC • RAW_01.CR3",
    meta_right: str = "ISO 400 · 1/120 · F1.8",
    accent: str = "coral",
    tilt_deg: float = -1.8,
    dark_frame: bool = True,
) -> Path:
    """
    Primitive #12 (`v5.2` `@__dviet × @vietanh` Editorial Camera Viewfinder Polaroid):
      - `REC • RAW_01.CR3` frosted telemetry pill + glowing recording indicator dot
      - Corner AF focus brackets + center reticle in semantic `accent` (`mint`, `cyan`, `coral`, `violet`, `lime`, `gold`)
      - Clean dynamic `textbbox` Vietnamese NFC caption strip, 2x supersampled RGBA PNG!
    """
    pal = _palette(accent)
    acc = pal["main"]
    rec_dot_rgb = ACCENT_PALETTES["coral"]["main"]

    frame_w = 620 * SS
    border = 22 * SS
    photo_w = frame_w - border * 2
    photo_h = 430 * SS

    f_rec = load_font("mono_bold", 15 * SS)
    f_meta = load_font("mono_medium", 13 * SS)
    f_cap = load_font("be_extrabold", 23 * SS)

    clean_cap = nfc_clean(caption)
    cap_lines = wrap_text(clean_cap, f_cap, photo_w - 38 * SS, max_lines=2) if clean_cap else []
    bottom_strip_h = ((84 + (len(cap_lines) - 1) * 30) if cap_lines else 26) * SS
    frame_h = border + photo_h + bottom_strip_h

    card = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    if dark_frame:
        frame_fill = (16, 20, 29, 248)
        frame_border = _rgba(acc, 165)
        cap_fg = (248, 250, 252, 255)
    else:
        frame_fill = (250, 249, 245, 255)
        frame_border = (214, 222, 232, 255)
        cap_fg = (24, 32, 46, 255)

    cd.rounded_rectangle(
        (0, 0, frame_w - 1, frame_h - 1),
        radius=18 * SS,
        fill=frame_fill,
        outline=frame_border,
        width=2 * SS,
    )

    photo = _load_or_placeholder_photo(image_path, photo_w, photo_h)
    # Subtle top HUD vignette inside photo so REC telemetry stays legible on bright highlights
    hud_grad = np.zeros((photo_h, photo_w, 4), dtype=np.uint8)
    top_band = min(photo_h, 92 * SS)
    t_lin = np.linspace(1.0, 0.0, top_band, dtype=np.float32)[:, None]
    hud_grad[:top_band, :, 3] = (135.0 * (t_lin ** 1.4)).astype(np.uint8)
    photo = Image.alpha_composite(photo, Image.fromarray(hud_grad, mode="RGBA"))

    photo_mask = Image.new("L", (photo_w, photo_h), 0)
    ImageDraw.Draw(photo_mask).rounded_rectangle((0, 0, photo_w - 1, photo_h - 1), radius=10 * SS, fill=255)
    card.paste(photo, (border, border), photo_mask)

    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle(
        (border, border, border + photo_w - 1, border + photo_h - 1),
        radius=10 * SS,
        outline=(255, 255, 255, 34) if dark_frame else (15, 23, 42, 42),
        width=max(1, SS),
    )

    # Top-left `REC • RAW_01.CR3` frosted pill
    rec_str = nfc_clean(rec_label) or "REC • RAW_01.CR3"
    rw, _, _ = text_metrics(rec_str, f_rec)
    px0 = border + 16 * SS
    py0 = border + 16 * SS
    ph_pill = 30 * SS
    pw_pill = rw + 42 * SS
    cd.rounded_rectangle(
        (px0, py0, px0 + pw_pill, py0 + ph_pill),
        radius=ph_pill // 2,
        fill=(10, 14, 22, 205),
        outline=_rgba(acc, 140),
        width=max(1, SS),
    )
    dot_cx = px0 + 16 * SS
    dot_cy = py0 + ph_pill / 2.0
    cd.ellipse((dot_cx - 7 * SS, dot_cy - 7 * SS, dot_cx + 7 * SS, dot_cy + 7 * SS), fill=_rgba(rec_dot_rgb, 68))
    cd.ellipse((dot_cx - 4 * SS, dot_cy - 4 * SS, dot_cx + 4 * SS, dot_cy + 4 * SS), fill=_rgba(rec_dot_rgb, 255))
    draw_text_centered_y(cd, px0 + 28 * SS, dot_cy, rec_str, f_rec, (248, 250, 252, 255), align_x="left")

    # Optional top-right camera exposure telemetry (`ISO 400 · 1/120 · F1.8`)
    meta_clean = nfc_clean(meta_right)
    if meta_clean:
        mw, _, _ = text_metrics(meta_clean, f_meta)
        if px0 + pw_pill + 16 * SS + mw <= border + photo_w - 16 * SS:
            draw_text_centered_y(
                cd, border + photo_w - 16 * SS, dot_cy, meta_clean, f_meta, (226, 232, 240, 220), align_x="right"
            )

    # Semantic accent AF focus brackets with subtle glow
    inset_x = border + 36 * SS
    inset_y_top = border + 60 * SS
    inset_y_bot = border + photo_h - 30 * SS
    br_glow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    _draw_viewfinder_brackets(
        ImageDraw.Draw(br_glow),
        inset_x,
        inset_y_top,
        border + photo_w - 36 * SS,
        inset_y_bot,
        acc,
        arm_len=28 * SS,
        stroke_w=4 * SS,
    )
    card = Image.alpha_composite(card, br_glow.filter(ImageFilter.GaussianBlur(radius=4 * SS)))
    cd = ImageDraw.Draw(card)
    _draw_viewfinder_brackets(
        cd,
        inset_x,
        inset_y_top,
        border + photo_w - 36 * SS,
        inset_y_bot,
        acc,
        arm_len=28 * SS,
        stroke_w=int(round(2.5 * SS)),
    )

    # Bottom editorial caption strip with crisp accent index bar
    if cap_lines:
        strip_top = border + photo_h
        strip_cy = strip_top + bottom_strip_h / 2.0
        bar_h = min(bottom_strip_h - 28 * SS, max(26 * SS, len(cap_lines) * 28 * SS))
        cd.rounded_rectangle(
            (border + 4 * SS, strip_cy - bar_h / 2.0, border + 10 * SS, strip_cy + bar_h / 2.0),
            radius=3 * SS,
            fill=_rgba(acc, 245),
        )
        total_ch = len(cap_lines) * 30 * SS
        cy_line = strip_cy - total_ch / 2.0 + 15 * SS
        for ln in cap_lines:
            draw_text_centered_y(cd, border + 24 * SS, cy_line, ln, f_cap, cap_fg, align_x="left")
            cy_line += 30 * SS

    # Soft drop shadow + smooth tilt
    pad_rot = 60 * SS
    stage = Image.new("RGBA", (frame_w + pad_rot * 2, frame_h + pad_rot * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", stage.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (pad_rot + 5 * SS, pad_rot + 14 * SS, pad_rot + frame_w + 5 * SS, pad_rot + frame_h + 16 * SS),
        radius=18 * SS,
        fill=(0, 0, 0, 160),
    )
    stage = Image.alpha_composite(stage, sh.filter(ImageFilter.GaussianBlur(radius=15 * SS)))
    stage.alpha_composite(card, (pad_rot, pad_rot))

    if abs(float(tilt_deg)) > 0.02:
        stage = stage.rotate(-float(tilt_deg), resample=Image.Resampling.BICUBIC, expand=True)

    abbox = stage.getchannel("A").getbbox()
    if abbox:
        m = 10 * SS
        cx0 = max(0, abbox[0] - m)
        cy0 = max(0, abbox[1] - m)
        cx1 = min(stage.width, abbox[2] + m)
        cy1 = min(stage.height, abbox[3] + m)
        if (cx1 - cx0) % 2:
            cx1 = min(stage.width, cx1 + 1)
        if (cy1 - cy0) % 2:
            cy1 = min(stage.height, cy1 + 1)
        stage = stage.crop((cx0, cy0, cx1, cy1))

    return _save_supersampled(stage, out_path)


def compact_glass_lock_badge(
    out_path: str | Path,
    header: str = "VISUAL LOCK",
    status_text: str = "LOCKED 100%",
    sub_label: str | None = None,
    thumbnail_path: str | Path | None = None,
    header_accent: str = "cyan",
    status_accent: str = "mint",
    accent: str | None = None,
) -> Path:
    """
    Primitive #13 (`v5.2` `@__dviet × @vietanh` Compact Frosted Dark-Glass Lock Badge):
      - Compact ~98px tall frosted dark-glass pill/badge (zero bulky screen-hogging box!)
      - Optional rounded thumbnail slot (`thumbnail_path`) OR crisp vector padlock badge
      - Multi-hue typography stack: `header` in `#38BDF8` cyan / `#FACC15` gold +
        `status_text` (`LOCKED 100%`) in `#2DD4BF` mint / `#4ADE80` lime!
    """
    pal_hdr = _palette(header_accent)
    pal_sts = _palette(accent if accent is not None else status_accent)
    hdr_rgb = pal_hdr["main"]
    sts_rgb = pal_sts["main"]

    hdr_str = (nfc_clean(header) or "VISUAL LOCK").upper()
    sts_str = nfc_clean(status_text) or "LOCKED 100%"
    sub_str = nfc_clean(sub_label) if sub_label else ""

    f_hdr = fit_font(hdr_str, "be_extrabold", 460 * SS, 15 * SS, 12 * SS)
    f_sts = fit_font(sts_str, "be_black", 460 * SS, 25 * SS, 17 * SS)
    f_sub = load_font("mont_bold", 15 * SS)

    hw_px, _, _ = text_metrics(hdr_str, f_hdr)
    sw_px, _, _ = text_metrics(sts_str, f_sts)
    subw_px = (text_metrics(sub_str, f_sub)[0] + 14 * SS) if sub_str else 0

    has_thumb = bool(thumbnail_path and (str(thumbnail_path).lower() == "placeholder" or Path(thumbnail_path).is_file()))
    left_slot_1x = 84 if has_thumb else 74
    right_content_2x = max(hw_px, sw_px + 22 * SS + subw_px)

    badge_h = 98 if has_thumb else 92
    badge_w = max(296, min(720, left_slot_1x + int(math.ceil(right_content_2x / SS)) + 34))
    pad = 18

    canvas, x0, y0 = _make_card_canvas(
        badge_w,
        badge_h,
        pad,
        radius=26,
        bg_top=(14, 20, 31),
        bg_bot=(9, 13, 21),
        border_rgb=sts_rgb,
        glow_rgb=sts_rgb,
        bg_alpha=244,
        shadow_alpha=128,
    )
    fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg_layer)
    cy = y0 + (badge_h * SS) / 2.0

    # Left slot: optional thumbnail OR frosted vector padlock medallion
    if has_thumb:
        th_sz = 64 * SS
        tx0 = x0 + 16 * SS
        ty0 = int(round(cy - th_sz / 2.0))
        thumb_src = None if str(thumbnail_path).lower() == "placeholder" else thumbnail_path
        thumb_im = _load_or_placeholder_photo(thumb_src, th_sz, th_sz)
        t_mask = Image.new("L", (th_sz, th_sz), 0)
        ImageDraw.Draw(t_mask).rounded_rectangle((0, 0, th_sz - 1, th_sz - 1), radius=15 * SS, fill=255)
        canvas.paste(thumb_im, (tx0, ty0), t_mask)
        draw.rounded_rectangle(
            (tx0, ty0, tx0 + th_sz - 1, ty0 + th_sz - 1),
            radius=15 * SS,
            outline=_rgba(hdr_rgb, 215),
            width=2 * SS,
        )
        text_x = x0 + 94 * SS
    else:
        icx = x0 + 44 * SS
        _draw_vector_icon(draw, "lock", icx, cy, 22 * SS, sts_rgb, filled_badge=True)
        text_x = x0 + 80 * SS

    # Line 1: Header overline in cyan (#38BDF8) or gold (#FACC15)
    hdr_cy = cy - 17 * SS
    draw_text_centered_y(draw, text_x, hdr_cy, hdr_str, f_hdr, _rgba(hdr_rgb, 250), align_x="left")

    # Line 2: Glowing status dot + status_text (`LOCKED 100%`) in mint (#2DD4BF) or lime (#4ADE80)
    sts_cy = cy + 15 * SS
    dot_x = text_x + 7 * SS
    draw.ellipse((dot_x - 7 * SS, sts_cy - 7 * SS, dot_x + 7 * SS, sts_cy + 7 * SS), fill=_rgba(sts_rgb, 56))
    draw.ellipse((dot_x - 4 * SS, sts_cy - 4 * SS, dot_x + 4 * SS, sts_cy + 4 * SS), fill=_rgba(sts_rgb, 255))
    w_drawn, _ = draw_text_centered_y(draw, text_x + 20 * SS, sts_cy, sts_str, f_sts, _rgba(sts_rgb, 255), align_x="left")

    if sub_str:
        draw_text_centered_y(
            draw,
            text_x + 20 * SS + w_drawn + 12 * SS,
            sts_cy,
            sub_str,
            f_sub,
            (203, 213, 225, 215),
            align_x="left",
        )

    total_w = badge_w + pad * 2
    total_h = badge_h + pad * 2
    anchor_cx_1x = (pad + 48) if has_thumb else (pad + 44)
    anchor_r_1x = 32 if has_thumb else 22
    return _save_supersampled(
        Image.alpha_composite(canvas, fg_layer),
        out_path,
        anchor_shape_xyr={
            "cx_pct": round(anchor_cx_1x / float(total_w), 6),
            "cy_pct": 0.50,
            "r_pct_w": round(anchor_r_1x / float(total_w), 6),
            "cx_px": anchor_cx_1x,
            "cy_px": total_h // 2,
            "r_px": anchor_r_1x,
            "shape": "rounded_rect" if has_thumb else "circle",
        },
    )


# ---------------------------------------------------------------------------
# v6.0 Living Motion-Canvas Integration (`dviet_motion_canvas_engine.py`)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_motion_canvas_engine():
    scripts_dir = str(Path(__file__).resolve().parent.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import dviet_motion_canvas_engine as mce  # type: ignore

    return mce


def render_canvas_stage(stage: str, out_path: str | Path, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render one of the 4 `v6.0` animated `.mp4` full-screen Motion-Design Canvases."""
    mce = _load_motion_canvas_engine()
    kwargs = dict(spec or {})
    kwargs.pop("kind", None)
    kwargs.pop("stage", None)
    kwargs.pop("out_path", None)
    return mce.render_motion_canvas(stage=stage, out_path=out_path, **kwargs)


# ---------------------------------------------------------------------------
# Registry & CLI Batch Interface (`--list` / `render` / `--canvas` / `render-canvas` / `lint-prompt`)
# ---------------------------------------------------------------------------

PRIMITIVE_FUNCTIONS = {
    "versus_split_card": versus_split_card,
    "flowchart_pipeline": flowchart_pipeline,
    "metric_kpi_hero": metric_kpi_hero,
    "code_terminal_window": code_terminal_window,
    "checklist_audit_card": checklist_audit_card,
    "quote_editorial_note": quote_editorial_note,
    "strike_myth_banner": strike_myth_banner,
    "polaroid_callout": polaroid_callout,
    "floating_pill_badge": floating_pill_badge,
    "clean_alpha_prop": clean_alpha_prop,
    "clean_broll_plate": clean_broll_plate,
    "viewfinder_raw_card": viewfinder_raw_card,
    "compact_glass_lock_badge": compact_glass_lock_badge,
}

PRIMITIVE_SCHEMAS: list[dict[str, Any]] = [
    {
        "kind": "versus_split_card",
        "description": "Side-by-side 2-column comparison card (Dimmed Crimson/Coral left vs Glowing semantic accent right + vector VS divider).",
        "required": ["out_path", "left_title", "left_items", "right_title", "right_items"],
        "optional": {"badge": None, "accent": "mint", "left_accent": "red", "badge_accent": "gold"},
    },
    {
        "kind": "flowchart_pipeline",
        "description": "Connected 3-node horizontal, 4-node 2x2 snake grid, or vertical workflow pipeline with Active-Dim Bento focus (`active_step`).",
        "required": ["out_path", "header", "steps"],
        "optional": {"accent": "cyan", "active_step": None},
    },
    {
        "kind": "metric_kpi_hero",
        "description": "High-impact KPI stat card with giant auto-fitted metric, vector trend arrow delta pill, and mini bar chart.",
        "required": ["out_path", "label", "big_value", "sub_delta"],
        "optional": {"bars": None, "accent": "gold"},
    },
    {
        "kind": "code_terminal_window",
        "description": "Authentic dark macOS IDE/Terminal window with traffic lights, line numbers, and syntax-highlighted tokens.",
        "required": ["out_path", "title", "lines"],
        "optional": {"status_pill": None, "accent": "cyan", "pill_accent": "mint"},
    },
    {
        "kind": "checklist_audit_card",
        "description": "Refined glassmorphism checklist card with multi-hue accent/theme, vector icons, and optional `active_row` Active-Dim focus.",
        "required": ["out_path", "pill", "rows"],
        "optional": {"mode": "cross", "theme": "red", "accent": None, "active_row": None},
    },
    {
        "kind": "quote_editorial_note",
        "description": "Editorial paper or dark glass quote card with Playfair Display Italic, vector quote glyph, and semantic accent bar.",
        "required": ["out_path", "quote", "author_or_tag"],
        "optional": {"dark": True, "accent": "gold"},
    },
    {
        "kind": "strike_myth_banner",
        "description": "Top red-struck-through misconception bar + bottom glowing semantic accent truth bar.",
        "required": ["out_path", "myth_text", "truth_text"],
        "optional": {"accent": "mint", "myth_accent": "red", "badge_accent": "gold"},
    },
    {
        "kind": "polaroid_callout",
        "description": "Frames a screenshot or B-roll still inside a tilted Polaroid/editorial card with soft drop shadow and caption strip.",
        "required": ["out_path", "image_path", "caption"],
        "optional": {"tilt_deg": -2.5, "accent": None},
    },
    {
        "kind": "floating_pill_badge",
        "description": "Compact ~84px tall glassmorphism status/chapter pill with vector dot/bolt/star/spark/check/lock/arrow/aperture icon.",
        "required": ["out_path", "text"],
        "optional": {"icon_kind": "dot", "accent": "mint"},
    },
    {
        "kind": "clean_alpha_prop",
        "description": "Removes disconnected rectangular color-swatch artifacts from RGBA 3D props, re-centers alpha, and strips metadata.",
        "required": ["src_path", "out_path"],
        "optional": {"keep_region": None},
    },
    {
        "kind": "clean_broll_plate",
        "description": "Trims uniform synthetic white/black borders, scales/crops with Lanczos to 1080x1920, checks grayscale_std >= 30.0, and strips metadata.",
        "required": ["src_path", "out_path"],
        "optional": {"target_size": [1080, 1920], "flat_std_min": 30.0, "strict_flat": False},
    },
    {
        "kind": "viewfinder_raw_card",
        "description": "@__dviet × @vietanh camera viewfinder Polaroid (`REC • RAW_01.CR3`, corner AF focus brackets in semantic accent color, clean caption strip).",
        "required": ["out_path"],
        "optional": {
            "image_path": None,
            "caption": "Bằng chứng thực tế",
            "rec_label": "REC • RAW_01.CR3",
            "meta_right": "ISO 400 · 1/120 · F1.8",
            "accent": "coral",
            "tilt_deg": -1.8,
            "dark_frame": True,
        },
    },
    {
        "kind": "compact_glass_lock_badge",
        "description": "@__dviet × @vietanh compact frosted dark-glass pill/badge with optional thumbnail slot, vector padlock, and multi-hue status line (`LOCKED 100%`).",
        "required": ["out_path"],
        "optional": {
            "header": "VISUAL LOCK",
            "status_text": "LOCKED 100%",
            "sub_label": None,
            "thumbnail_path": None,
            "header_accent": "cyan",
            "status_accent": "mint",
            "accent": None,
        },
    },
]


def _parse_json_spec_arg(spec_arg: str | None) -> Any:
    if not spec_arg:
        return {}
    s = str(spec_arg).strip()
    if s.startswith(("{", "[")):
        return json.loads(s)
    p = Path(s)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(s)


def render_batch(spec_items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render a batch list of static block or animated motion-canvas specifications and return metadata (`anchor_shape_xyr`)."""
    mce = _load_motion_canvas_engine()
    results: list[dict[str, Any]] = []
    for idx, item in enumerate(spec_items):
        if not isinstance(item, dict) or "kind" not in item:
            raise ValueError(f"Block #{idx} missing 'kind': {item!r}")
        kind = str(item["kind"])
        if kind in mce.CANVAS_STAGE_FUNCTIONS:
            out_path = item.get("out_path") or item.get("output")
            if not out_path:
                raise ValueError(f"Motion canvas #{idx} ({kind}) requires 'out_path'")
            c_meta = render_canvas_stage(kind, out_path, item)
            results.append({"index": idx, "kind": kind, **c_meta})
            continue
        if kind not in PRIMITIVE_FUNCTIONS:
            valid = sorted(set(PRIMITIVE_FUNCTIONS) | set(s["kind"] for s in mce.CANVAS_STAGE_SCHEMAS))
            raise ValueError(f"Unknown visual block/canvas kind={kind!r}. Valid: {valid}")
        kwargs = {k: v for k, v in item.items() if k != "kind"}
        out_p = PRIMITIVE_FUNCTIONS[kind](**kwargs)
        with Image.open(out_p) as im:
            w, h = im.size
        entry: dict[str, Any] = {"index": idx, "kind": kind, "out_path": str(out_p), "width": w, "height": h}
        if hasattr(out_p, "anchor_shape_xyr") and out_p.anchor_shape_xyr:
            entry["anchor_shape_xyr"] = out_p.anchor_shape_xyr
        if isinstance(out_p, BrollPlateResult):
            entry["grayscale_std"] = out_p.grayscale_std
            entry["trimmed_borders"] = out_p.trimmed_borders
            if out_p.warning:
                entry["warning"] = out_p.warning
        results.append(entry)
    return results


def _print_list_catalog() -> int:
    mce = _load_motion_canvas_engine()
    accent_hex_map = {
        k: f"#{v['main'][0]:02X}{v['main'][1]:02X}{v['main'][2]:02X}"
        for k, v in sorted(ACCENT_PALETTES.items())
    }
    print(
        json.dumps(
            {
                "version": "6.0",
                "primitives": PRIMITIVE_SCHEMAS,
                "motion_canvases": mce.CANVAS_STAGE_SCHEMAS,
                "canvas_themes": list(mce.COLOR_WORLD_THEMES.keys()),
                "canvas_polarities": ["dark", "light"],
                "accents": sorted(ACCENT_PALETTES),
                "accent_hex": accent_hex_map,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cli(argv: Sequence[str] | None = None) -> int:
    eff_argv = list(sys.argv[1:] if argv is None else argv)
    if eff_argv == ["--list"] or (
        "--list" in eff_argv and not any(c in eff_argv for c in ("render", "render-canvas", "--canvas", "lint-prompt"))
    ):
        return _print_list_catalog()

    # Direct top-level `--canvas <stage> [--spec '{...}'] -o stage.mp4` shortcut
    if "--canvas" in eff_argv and (not eff_argv or eff_argv[0] not in ("render", "render-canvas", "lint-prompt", "list")):
        c_parser = argparse.ArgumentParser(description="Render a v6.0 Living Motion-Design Canvas (.mp4)")
        c_parser.add_argument("--canvas", required=True, help="Stage name (`timeline_playhead_stage`, `concentric_lock_lab_stage`, `giant_numeral_3d_ui_stage`, `bento_kinetic_matrix_stage`)")
        c_parser.add_argument("--spec", default="{}", help="Inline JSON spec string or path to `.json` spec file")
        c_parser.add_argument("-o", "--output", required=True, help="Output `.mp4` path")
        c_args = c_parser.parse_args(eff_argv)
        spec_obj = _parse_json_spec_arg(c_args.spec)
        if not isinstance(spec_obj, dict):
            raise ValueError("--spec for --canvas must be a JSON object")
        res = render_canvas_stage(c_args.canvas, c_args.output, spec_obj)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Stateless 13-Primitive Visual Blocks, 4 Living Motion Canvases & B-Roll Hygiene Toolkit (v6.0)")
    parser.add_argument("--list", action="store_true", help="Print JSON schema of all 13 visual primitives and 4 animated motion canvases")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("list", help="Print JSON schema of all 13 visual primitives and 4 animated motion canvases")

    p_render = sub.add_parser("render", help="Batch-render blocks/canvases from a JSON spec file or inline JSON")
    p_render.add_argument("--spec", required=True, help="Path to JSON list of block specs (or inline JSON)")

    p_canvas = sub.add_parser("render-canvas", help="Render an animated full-screen v6.0 Motion-Design Canvas (.mp4)")
    p_canvas.add_argument("stage_pos", nargs="?", help="Stage name positional")
    p_canvas.add_argument("--canvas", dest="canvas_flag", help="Stage name flag")
    p_canvas.add_argument("--spec", default="{}", help="Inline JSON spec string or path to `.json` file")
    p_canvas.add_argument("-o", "--output", required=True, help="Output `.mp4` path")

    p_lint = sub.add_parser("lint-prompt", help="Audit an AI B-roll prompt against the 46-token anti-slop banlist")
    p_lint.add_argument("prompt", help="English B-roll prompt string to validate")

    args = parser.parse_args(eff_argv)
    if args.list or args.cmd == "list":
        return _print_list_catalog()

    if args.cmd == "lint-prompt":
        report = lint_broll_prompt(args.prompt)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "render-canvas":
        stage_name = args.canvas_flag or args.stage_pos
        if not stage_name:
            p_canvas.error("Specify stage name via positional argument or --canvas")
        spec_obj = _parse_json_spec_arg(args.spec)
        if not isinstance(spec_obj, dict):
            raise ValueError("--spec for render-canvas must be a JSON object")
        res = render_canvas_stage(stage_name, args.output, spec_obj)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "render":
        payload = _parse_json_spec_arg(args.spec)
        items = payload["blocks"] if isinstance(payload, dict) and "blocks" in payload else payload
        if not isinstance(items, list):
            raise ValueError("--spec JSON must be a list of block objects or {'blocks': [...]}")
        rendered = render_batch(items)
        print(json.dumps({"rendered": len(rendered), "items": rendered}, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
