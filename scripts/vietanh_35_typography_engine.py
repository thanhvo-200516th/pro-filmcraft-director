#!/usr/bin/env python3
"""
VIETANH 7686349228712512788 - 35 Text Animation Presets (10 Mechanical Families) (`v6.0`)
Premiere Pro <-> FilmCraft (.fcproj v17 & Python/PIL/NumPy/OpenCV Render Engine)
100% Vietnamese Unicode NFC Safe + Dynamic Unclipped Box Width (`max(920, tw+140)`) + Multi-Hue & Metallic Bokeh.
"""

import math
import re
import unicodedata
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


VA_SEMANTIC_RGB: dict[str, tuple[int, int, int]] = {
    "prestige_gold": (250, 204, 21),
    "gold": (250, 204, 21),
    "yellow": (250, 204, 21),
    "amber": (245, 158, 11),
    "alert_coral": (255, 77, 94),
    "coral": (255, 77, 94),
    "red": (255, 77, 94),
    "lock_mint": (45, 212, 191),
    "mint": (45, 212, 191),
    "emerald": (45, 212, 191),
    "teal": (45, 212, 191),
    "cinema_cyan": (56, 189, 248),
    "cyan": (56, 189, 248),
    "blue": (56, 189, 248),
    "studio_violet": (192, 132, 252),
    "violet": (192, 132, 252),
    "purple": (192, 132, 252),
    "warm_peach": (251, 146, 60),
    "peach": (251, 146, 60),
    "orange": (251, 146, 60),
    "action_lime": (74, 222, 128),
    "lime": (74, 222, 128),
    "green": (74, 222, 128),
    "ivory_white": (248, 250, 252),
    "white": (248, 250, 252),
}

_VA_INLINE_TAG_RE = re.compile(r"\[([#A-Za-z0-9_-]+):([^\[\]]+)\]")
_VA_HEX6_RE = re.compile(r"^#([0-9A-Fa-f]{6})$")

VA_BOKEH_METALLIC_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "gold": {
        "top": (255, 245, 184),
        "bot": (210, 150, 39),
        "glow": (245, 185, 45),
    },
    "mint": {
        "top": (204, 251, 241),
        "bot": (20, 184, 166),
        "glow": (45, 212, 191),
    },
    "cyan": {
        "top": (224, 242, 254),
        "bot": (14, 165, 233),
        "glow": (56, 189, 248),
    },
    "violet": {
        "top": (243, 232, 255),
        "bot": (147, 51, 234),
        "glow": (192, 132, 252),
    },
    "lime": {
        "top": (220, 252, 231),
        "bot": (34, 197, 94),
        "glow": (74, 222, 128),
    },
    "coral": {
        "top": (255, 228, 230),
        "bot": (225, 29, 72),
        "glow": (255, 77, 94),
    },
    "peach": {
        "top": (255, 237, 213),
        "bot": (234, 88, 12),
        "glow": (251, 146, 60),
    },
}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def resolve_va_color_token(token: str | tuple[int, int, int] | None, fallback: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    """Resolve short hue name (`mint`, `gold`, `coral`, ...), `#RRGGBB`, or RGB tuple to `(R, G, B)`."""
    if token is None:
        return fallback
    if isinstance(token, (tuple, list)) and len(token) >= 3:
        return (int(token[0]), int(token[1]), int(token[2]))
    key = str(token).strip()
    m = _VA_HEX6_RE.match(key)
    if m:
        hx = m.group(1)
        return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
    return VA_SEMANTIC_RGB.get(key.lower(), fallback)


def strip_va_inline_tags(text: str) -> str:
    """Strip known `[color:phrase]` inline markup tags while keeping plain text intact."""
    s = nfc(str(text or ""))

    def _repl(m: re.Match) -> str:
        raw_col = m.group(1).strip()
        if _VA_HEX6_RE.match(raw_col) or raw_col.lower() in VA_SEMANTIC_RGB:
            return m.group(2)
        return m.group(0)

    return _VA_INLINE_TAG_RE.sub(_repl, s)


def resolve_va_char_colors(
    raw_text: str,
    default_rgb: tuple[int, int, int],
    word_colors: dict[int, tuple[int, int, int]] | None = None,
    second_word_color: tuple[int, int, int] | None = None,
) -> tuple[str, list[tuple[int, int, int]]]:
    """
    Parse inline `[color:phrase]` tags AND optional `word_colors: dict[int, tuple[int, int, int]]`
    (plus legacy `second_word_color`) into `(clean_nfc_text, per_character_rgb_list)`.
    """
    s = nfc(str(raw_text or ""))
    out_chars: list[str] = []
    char_rgbs: list[tuple[int, int, int]] = []

    pos = 0
    for m in _VA_INLINE_TAG_RE.finditer(s):
        if m.start() > pos:
            seg = s[pos : m.start()]
            out_chars.extend(seg)
            char_rgbs.extend([default_rgb] * len(seg))
        raw_col = m.group(1).strip()
        inner = m.group(2)
        if _VA_HEX6_RE.match(raw_col) or raw_col.lower() in VA_SEMANTIC_RGB:
            c_rgb = resolve_va_color_token(raw_col, default_rgb)
            out_chars.extend(inner)
            char_rgbs.extend([c_rgb] * len(inner))
        else:
            lit = m.group(0)
            out_chars.extend(lit)
            char_rgbs.extend([default_rgb] * len(lit))
        pos = m.end()

    if pos < len(s):
        tail = s[pos:]
        out_chars.extend(tail)
        char_rgbs.extend([default_rgb] * len(tail))

    clean = "".join(out_chars)

    if second_word_color is not None:
        first_sp = clean.find(" ")
        if first_sp != -1:
            sw_rgb = resolve_va_color_token(second_word_color, default_rgb)
            for idx in range(first_sp + 1, len(char_rgbs)):
                if char_rgbs[idx] == default_rgb:
                    char_rgbs[idx] = sw_rgb

    if word_colors:
        word_spans = list(re.finditer(r"\S+", clean))
        n_words = len(word_spans)
        for w_key, w_col in word_colors.items():
            wi = w_key if w_key >= 0 else (n_words + w_key)
            if 0 <= wi < n_words:
                rgb_val = resolve_va_color_token(w_col, default_rgb)
                sp = word_spans[wi]
                for ci in range(sp.start(), sp.end()):
                    char_rgbs[ci] = rgb_val

    return clean, char_rgbs


def draw_multicolor_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    clean_text: str,
    char_rgbs: list[tuple[int, int, int]],
    font: ImageFont.FreeTypeFont,
    alpha: int = 255,
) -> None:
    """Draw `clean_text` at `xy` preserving exact full-prefix kerning while coloring contiguous hue runs."""
    if not clean_text or alpha <= 0:
        return
    x0, y0 = float(xy[0]), float(xy[1])
    unique_rgbs = set(char_rgbs)
    if len(unique_rgbs) <= 1:
        c0 = char_rgbs[0] if char_rgbs else (255, 255, 255)
        draw.text((x0, y0), clean_text, font=font, fill=(*c0, int(alpha)))
        return

    n = len(clean_text)
    run_start = 0
    while run_start < n:
        cur_rgb = char_rgbs[run_start]
        run_end = run_start + 1
        while run_end < n and char_rgbs[run_end] == cur_rgb:
            run_end += 1
        prefix = clean_text[:run_start]
        seg = clean_text[run_start:run_end]
        dx = draw.textlength(prefix, font=font) if prefix else 0.0
        draw.text((x0 + dx, y0), seg, font=font, fill=(*cur_rgb, int(alpha)))
        run_start = run_end


def add_chromatic_layer_glow(
    layer_rgba: Image.Image,
    fallback_rgb: tuple[int, int, int] = (245, 158, 11),
    radius: float = 20.0,
    intensity: float = 0.80,
    has_multicolor: bool = False,
) -> Image.Image:
    """Multi-hue-aware optical bloom: blurs each colored word's own RGB when multi-color is active."""
    if intensity <= 0.01:
        return layer_rgba
    if not has_multicolor:
        return add_colored_glow(layer_rgba, glow_rgb=fallback_rgb, radius=radius, intensity=intensity)
    blurred = layer_rgba.filter(ImageFilter.GaussianBlur(radius=radius))
    r, g, b, a = blurred.split()
    scale = clamp(intensity, 0.0, 2.2)
    a = a.point(lambda v: min(255, int(v * scale)))
    glow_img = Image.merge("RGBA", (r, g, b, a))
    return Image.alpha_composite(glow_img, layer_rgba)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def ease_out_cubic(u: float) -> float:
    u = clamp(u)
    return 1.0 - math.pow(1.0 - u, 3.0)


def ease_out_expo(u: float) -> float:
    u = clamp(u)
    return 1.0 if u >= 1.0 else 1.0 - math.pow(2.0, -10.0 * u)


def ease_in_out_cubic(u: float) -> float:
    u = clamp(u)
    return 4.0 * u * u * u if u < 0.5 else 1.0 - math.pow(-2.0 * u + 2.0, 3.0) / 2.0


def ease_out_back(u: float, overshoot: float = 1.18) -> float:
    u = clamp(u)
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * math.pow(u - 1.0, 3) + c1 * math.pow(u - 1.0, 2)


def add_colored_glow(
    layer_rgba: Image.Image,
    glow_rgb: tuple[int, int, int] = (245, 158, 11),
    radius: float = 22.0,
    intensity: float = 0.85,
) -> Image.Image:
    """Premiere Pro 'Screen' / 'Linear Dodge (Add)' duplicate Gaussian Blur glow."""
    if intensity <= 0.01:
        return layer_rgba
    w, h = layer_rgba.size
    alpha = layer_rgba.split()[3]
    g_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=radius))
    scale = clamp(intensity, 0.0, 2.2)
    g_alpha = g_alpha.point(lambda v: min(255, int(v * scale)))
    glow_img = Image.new("RGBA", (w, h), (*glow_rgb, 0))
    glow_img.putalpha(g_alpha)
    return Image.alpha_composite(glow_img, layer_rgba)


def measure_char_positions(text: str, font: ImageFont.FreeTypeFont, tracking: float = 0.0):
    """Pre-measures exact x offsets of every Vietnamese NFC character using full prefix advance."""
    text = nfc(text)
    dummy = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    dr = ImageDraw.Draw(dummy)
    chars = []
    for i, ch in enumerate(text):
        prefix = text[:i]
        px = dr.textlength(prefix, font=font) + i * tracking if prefix else 0.0
        cw = dr.textlength(ch, font=font)
        bb = dr.textbbox((0, 0), ch, font=font)
        ch_h = bb[3] - bb[1]
        chars.append((ch, px, cw, ch_h))
    total_w = (chars[-1][1] + chars[-1][2]) if chars else 0.0
    full_bb = dr.textbbox((0, 0), text, font=font) if text else (0, 0, 0, 0)
    total_h = full_bb[3] - full_bb[1]
    return chars, total_w, total_h


def _measure_va_text_span(text: str, font: ImageFont.FreeTypeFont) -> tuple[float, float, float]:
    """Return `(advance_w, ink_span_w, ink_h)` in NFC so dynamic `box_w` never clips overhanging glyphs."""
    clean = nfc(text)
    if not clean:
        return 0.0, 0.0, 0.0
    dummy = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    dr = ImageDraw.Draw(dummy)
    adv_w = float(dr.textlength(clean, font=font))
    bb = dr.textbbox((0, 0), clean, font=font)
    ink_w = max(adv_w, float(bb[2] - bb[0]))
    ink_h = max(0.0, float(bb[3] - bb[1]))
    return adv_w, ink_w, ink_h


def _composite_va_box(
    out: Image.Image,
    lay: Image.Image,
    cx: float,
    top_y: float,
    dx: float = 0.0,
) -> None:
    """
    Safely composite a dynamic `(box_w, box_h)` RGBA layer (`box_w >= max(920, tw + 140)`) onto `out`:
      - Preserves 1:1 pixel sharpness whenever rendered ink fits inside `out.width - 32`.
      - Proportionally downscales `lay` ONLY when wide phrases exceed `out.width - 32`, preventing right-edge clipping (`'xưởngm'`).
      - Center-trims empty transparent margin if `lay.width > out.width` on compact preview canvases.
    """
    w, h = out.size
    bbox = lay.getbbox()
    if bbox is None:
        return

    ink_w = bbox[2] - bbox[0]
    safe_canvas_w = max(64, w - 32)
    cur_lay = lay
    cur_top_y = float(top_y)

    if ink_w > safe_canvas_w:
        scale_fit = safe_canvas_w / float(ink_w)
        nw = max(1, int(round(cur_lay.width * scale_fit)))
        nh = max(1, int(round(cur_lay.height * scale_fit)))
        cur_top_y += (cur_lay.height - nh) * 0.5
        cur_lay = cur_lay.resize((nw, nh), Image.Resampling.LANCZOS)
        bbox = cur_lay.getbbox()
        if bbox is None:
            return

    if cur_lay.width > w:
        ink_cx = 0.5 * (bbox[0] + bbox[2])
        crop_l = int(round(ink_cx - w * 0.5))
        crop_l = max(0, min(cur_lay.width - w, crop_l))
        cur_lay = cur_lay.crop((crop_l, 0, crop_l + w, cur_lay.height))

    if cur_lay.height > h:
        ink_cy = 0.5 * (bbox[1] + bbox[3])
        crop_t = int(round(ink_cy - h * 0.5))
        crop_t = max(0, min(cur_lay.height - h, crop_t))
        cur_lay = cur_lay.crop((0, crop_t, cur_lay.width, crop_t + h))
        cur_top_y = 0.0

    margin_x = min(20, max(0, (w - cur_lay.width) // 2))
    px = max(margin_x, min(w - cur_lay.width - margin_x, int(round(cx - cur_lay.width * 0.5 + dx))))
    py = max(0, min(h - cur_lay.height, int(round(cur_top_y))))
    out.alpha_composite(cur_lay, (px, py))


# ==============================================================================
# FAM_01: STAGGERED SLIDE + DE-BLUR & INVISIBLE BASELINE MASK
# Presets: #1 Minimal Style, #3 Clear Green, #9 Fresh Simple, #10 Wave
# ==============================================================================
def render_va_fam01_baseline_mask_slide(
    canvas_size: tuple[int, int],
    top_text: str,
    hero_text: str,
    t_sec: float,
    t_start: float,
    font_top: ImageFont.FreeTypeFont,
    font_hero: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 460),
    top_color: tuple[int, int, int] = (255, 255, 255),
    hero_color: tuple[int, int, int] = (30, 232, 108),
    stagger_sec: float = 0.14,
    wave_warp: bool = False,
    word_colors: dict[int, tuple[int, int, int]] | None = None,
    top_word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Premiere Pro: Transform (Position Y: +52px -> 0, Shutter 180) placed ABOVE Crop (Bottom)
    + Gaussian Blur (24 -> 0), optionally with Wave Warp (Sine, Height 16 -> 0).
    Supports `word_colors` AND inline `[color:word]` multi-hue tags!
    `v6.0`: Dynamic `box_w = max(920, int(tw + 140))` so long Vietnamese lines are NEVER right-clipped!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    cx, cy = center_xy
    top_base_rgb = resolve_va_color_token(top_color, (255, 255, 255))
    hero_base_rgb = resolve_va_color_token(hero_color, (30, 232, 108))

    # 1. Top line (#1 Minimal / #3 CLEAR / #9 Fresh)
    if top_text:
        clean_top, top_rgbs = resolve_va_char_colors(top_text, top_base_rgb, word_colors=top_word_colors)
        u1 = clamp((t_sec - t_start) / 0.30)
        e1 = ease_out_cubic(u1)
        adv_t, tw, th_t = _measure_va_text_span(clean_top, font_top)
        box_w = max(920, int(math.ceil(tw + 140)))
        box_h = max(140, int(math.ceil(th_t + 88)))
        lay1 = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        d1 = ImageDraw.Draw(lay1)
        tx = max(32, min(box_w - int(math.ceil(tw)) - 32, int((box_w - adv_t) / 2 - 45)))
        dy1 = int(36 * (1.0 - e1))
        draw_multicolor_line(d1, (tx, 28 + dy1), clean_top, top_rgbs, font_top, alpha=int(255 * e1))
        blur1 = 14.0 * (1.0 - e1)
        if blur1 > 0.35:
            lay1 = lay1.filter(ImageFilter.GaussianBlur(radius=blur1))
        # Crop bottom baseline mask proportionally below top baseline
        crop_y1 = max(108, box_h - 32)
        arr1 = np.array(lay1)
        arr1[crop_y1:, :, 3] = 0
        lay1 = Image.fromarray(arr1)
        _composite_va_box(out, lay1, cx, max(40, cy - 82))

    # 2. Hero line (#3 Green / #9 Simple / #10 Wave) rising through invisible floor mask
    if t_sec >= t_start + stagger_sec and hero_text:
        clean_hero, hero_rgbs = resolve_va_char_colors(hero_text, hero_base_rgb, word_colors=word_colors)
        has_multi_hero = len(set(hero_rgbs)) > 1
        u2 = clamp((t_sec - (t_start + stagger_sec)) / 0.36)
        e2 = ease_out_cubic(u2)
        adv_h, tw_h, th_h = _measure_va_text_span(clean_hero, font_hero)
        box_w = max(920, int(math.ceil(tw_h + 140)))
        box_h = max(220, int(math.ceil(th_h + 116)))
        lay2 = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(lay2)
        hx = max(32, min(box_w - int(math.ceil(tw_h)) - 32, int((box_w - adv_h) / 2 + (30 if top_text else 0))))
        dy2 = int(58 * (1.0 - e2))
        draw_multicolor_line(d2, (hx, 34 + dy2), clean_hero, hero_rgbs, font_hero, alpha=int(255 * min(1.0, u2 * 1.6)))

        if wave_warp and u2 < 0.98:
            arr = np.array(lay2)
            bh, bw = arr.shape[:2]
            xs, ys = np.meshgrid(np.arange(bw, dtype=np.float32), np.arange(bh, dtype=np.float32))
            amp = 15.0 * (1.0 - e2)
            ys_warp = ys + amp * np.sin(2.0 * math.pi * xs / 145.0 - 7.0 * u2)
            arr = cv2.remap(arr, xs, ys_warp, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            lay2 = Image.fromarray(arr)

        blur2 = 16.0 * math.pow(1.0 - u2, 1.6)
        if blur2 > 0.35:
            lay2 = lay2.filter(ImageFilter.GaussianBlur(radius=blur2))
        glow_fallback = hero_rgbs[0] if hero_rgbs else hero_base_rgb
        lay2 = add_chromatic_layer_glow(
            lay2, fallback_rgb=glow_fallback, radius=20.0, intensity=0.75 * e2, has_multicolor=has_multi_hero
        )
        # Invisible Baseline Crop
        crop_y2 = max(162, box_h - 58)
        arr2 = np.array(lay2)
        arr2[crop_y2:, :, 3] = 0
        lay2 = Image.fromarray(arr2)
        _composite_va_box(out, lay2, cx, cy - 12)

    return out


# ==============================================================================
# FAM_02: DIAGONAL ROTATION WHIP + HDR GLOW DECAY
# Presets: #2 Orange, #26 Speed Up
# ==============================================================================
def render_va_fam02_diagonal_rotation_whip(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    color_rgb: tuple[int, int, int] = (255, 94, 26),
    mode: str = "orange_whip",  # "orange_whip" (#2) or "speed_up" (#26)
) -> Image.Image:
    """
    Premiere Pro #2 Orange: Scale 150% -> 96% -> 100%, Rotation -20 deg -> 0 deg,
    Gaussian Blur 32 -> 0 + Screen HDR Glow.
    Premiere Pro #26 Speed Up: Position X -140px -> +6px -> 0px, Skew -12 deg -> 0 deg,
    Directional Blur 90 deg (40 -> 0).
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    u = clamp((t_sec - t_start) / 0.38)
    e_back = ease_out_back(u, overshoot=1.22)
    e_cub = ease_out_cubic(u)

    dummy_d = ImageDraw.Draw(out)
    tw = dummy_d.textlength(nfc(text), font=font)
    box_w = min(w - 40, max(360, int(tw + 160)))
    box_h = 260
    lay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    dr.text(((box_w - tw) / 2, 65), nfc(text), font=font, fill=(*color_rgb, int(255 * min(1.0, u * 2.2))))

    arr = np.array(lay)
    bh, bw = arr.shape[:2]
    if mode == "orange_whip":
        scale = 1.48 - 0.48 * e_back
        angle = -20.0 * (1.0 - e_back)
        M = cv2.getRotationMatrix2D((bw * 0.5, bh * 0.5), angle, max(0.5, scale))
        arr = cv2.warpAffine(arr, M, (bw, bh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        lay = Image.fromarray(arr)
        blur_r = 18.0 * math.pow(1.0 - u, 1.7)
        if blur_r > 0.35:
            lay = lay.filter(ImageFilter.GaussianBlur(radius=blur_r))
    else:
        dx = -145.0 * (1.0 - e_back)
        shear = -0.22 * (1.0 - e_cub)
        M = np.array([[1.0, shear, dx - shear * bh * 0.5], [0.0, 1.0, 0.0]], dtype=np.float32)
        arr = cv2.warpAffine(arr, M, (bw, bh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        k_x = max(1, int(38 * math.pow(1.0 - u, 1.6)))
        if k_x > 1:
            arr = cv2.blur(arr, (k_x, 1))
        lay = Image.fromarray(arr)

    glow_str = 1.35 * (1.0 - 0.45 * e_cub)
    lay = add_colored_glow(lay, glow_rgb=color_rgb, radius=26.0, intensity=glow_str)
    px = max(40, min(w - box_w - 40, int(center_xy[0] - box_w // 2)))
    py = max(40, min(h - box_h - 40, int(center_xy[1] - box_h // 2)))
    out.alpha_composite(lay, (px, py))
    return out


# ==============================================================================
# FAM_03: CENTER-OUT DUAL CURSOR BARS + MASK EXPAND
# Preset: #4 Text Focused (| text focused |)
# ==============================================================================
def render_va_fam03_center_cursor_bars_expand(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    bar_color: tuple[int, int, int] = (41, 121, 255),
    text_color: tuple[int, int, int] = (255, 255, 255),
    word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Premiere Pro #4 Text Focused:
    - 2 vertical cursor bars (#2979FF, left bar has top circle pin, right bar has bottom circle pin)
      expand outward from Center_X to Center_X +- (TextWidth/2 + 24px).
    - Text layer & horizontal glow band reveal via matching Crop Left/Right (50% -> 0%).
    - Supports `word_colors` AND inline `[color:word]` multi-hue tags!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    u = clamp((t_sec - t_start) / 0.40)
    e = ease_out_expo(u)

    bar_rgb = resolve_va_color_token(bar_color, (41, 121, 255))
    base_txt_rgb = resolve_va_color_token(text_color, (255, 255, 255))
    clean_txt, char_rgbs = resolve_va_char_colors(text, base_txt_rgb, word_colors=word_colors)
    if not clean_txt:
        return out

    dummy = ImageDraw.Draw(out)
    tw = dummy.textlength(clean_txt, font=font)
    bb = dummy.textbbox((0, 0), clean_txt, font=font)
    th = bb[3] - bb[1]
    cx, cy = center_xy
    max_half = int(tw / 2 + 26)
    cur_half = max(3, int(max_half * e))

    # 1. Horizontal glow band behind text
    band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bdr = ImageDraw.Draw(band)
    bdr.rectangle([cx - cur_half, cy - th // 2 - 8, cx + cur_half, cy + th // 2 + 12], fill=(*bar_rgb, int(115 * e)))
    band = band.filter(ImageFilter.GaussianBlur(radius=28))
    out = Image.alpha_composite(out, band)

    # 2. Text layer cropped strictly between [cx - cur_half, cx + cur_half]
    txt_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tdr = ImageDraw.Draw(txt_lay)
    tx0 = int(cx - tw / 2)
    ty0 = int(cy - th / 2 - 6)
    draw_multicolor_line(tdr, (tx0, ty0), clean_txt, char_rgbs, font, alpha=255)
    arr_t = np.array(txt_lay)
    left_cut = max(0, cx - cur_half)
    right_cut = min(w, cx + cur_half)
    arr_t[:, :left_cut, 3] = 0
    arr_t[:, right_cut:, 3] = 0
    txt_lay = Image.fromarray(arr_t)
    out = Image.alpha_composite(out, txt_lay)

    # 3. Left & Right Neon Cursor Bars with Top/Bottom Pin Circles
    bars_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr_b = ImageDraw.Draw(bars_lay)
    bar_top = cy - th // 2 - 14
    bar_bot = cy + th // 2 + 18
    lx = cx - cur_half
    rx = cx + cur_half
    # Left bar + top pin circle
    dr_b.rectangle([lx - 3, bar_top, lx + 3, bar_bot], fill=(*bar_rgb, 255))
    dr_b.ellipse([lx - 8, bar_top - 10, lx + 8, bar_top + 6], fill=(*bar_rgb, 255))
    # Right bar + bottom pin circle
    dr_b.rectangle([rx - 3, bar_top, rx + 3, bar_bot], fill=(*bar_rgb, 255))
    dr_b.ellipse([rx - 8, bar_bot - 6, rx + 8, bar_bot + 10], fill=(*bar_rgb, 255))
    bars_lay = add_colored_glow(bars_lay, glow_rgb=bar_rgb, radius=14.0, intensity=1.1)
    out = Image.alpha_composite(out, bars_lay)
    return out


# ==============================================================================
# FAM_04: VERTICAL PASS-THROUGH CROSSOVER
# Preset: #5 Modern Vibrant
# ==============================================================================
def render_va_fam04_vertical_passthrough_crossover(
    canvas_size: tuple[int, int],
    top_text: str,
    bottom_text: str,
    t_sec: float,
    t_start: float,
    font_top: ImageFont.FreeTypeFont,
    font_bottom: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 470),
    top_color: tuple[int, int, int] = (255, 255, 255),
    bottom_color: tuple[int, int, int] = (30, 107, 255),
) -> Image.Image:
    """
    Premiere Pro #5 Modern Vibrant:
    - Top line ('Modern', white) starts at BOTTOM position (Y_bot) and flies UP to Y_top.
    - Bottom line ('Vibrant', electric blue) starts at TOP position (Y_top) and flies DOWN to Y_bot.
    - Both pass right through each other at u=0.5 with Gaussian Blur (28 -> 0) and Screen Glow!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    u = clamp((t_sec - t_start) / 0.42)
    e = ease_in_out_cubic(u)
    cx, cy = center_xy

    y_top_target = cy - 46
    y_bot_target = cy + 28
    # Crossover interpolation!
    y_top_cur = int(y_bot_target + (y_top_target - y_bot_target) * e)
    y_bot_cur = int(y_top_target + (y_bot_target - y_top_target) * e)
    blur_r = 22.0 * math.pow(1.0 - u, 1.55)
    alpha = int(255 * min(1.0, u * 2.0))

    # Bottom layer (flies from top -> bottom)
    lay_bot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    db = ImageDraw.Draw(lay_bot)
    bw = db.textlength(nfc(bottom_text), font=font_bottom)
    db.text((max(50, cx - bw / 2), y_bot_cur), nfc(bottom_text), font=font_bottom, fill=(*bottom_color, alpha))
    if blur_r > 0.35:
        lay_bot = lay_bot.filter(ImageFilter.GaussianBlur(radius=blur_r))
    lay_bot = add_colored_glow(lay_bot, glow_rgb=bottom_color, radius=24.0, intensity=1.15)

    # Top layer (flies from bottom -> top)
    lay_top = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dt = ImageDraw.Draw(lay_top)
    tw = dt.textlength(nfc(top_text), font=font_top)
    dt.text((max(50, cx - tw / 2), y_top_cur), nfc(top_text), font=font_top, fill=(*top_color, alpha))
    if blur_r > 0.35:
        lay_top = lay_top.filter(ImageFilter.GaussianBlur(radius=blur_r))

    out = Image.alpha_composite(out, lay_bot)
    out = Image.alpha_composite(out, lay_top)
    return out


# ==============================================================================
# FAM_05: SOFT GRADIENT WIPE + GLOWING LEADING EDGE (& GIANT WATERMARK)
# Presets: #6 Soft Motion, #19 Simple Type, #20 Bright Silver, #32 MONEY $100
# ==============================================================================
def render_va_fam05_soft_wipe_glow_watermark(
    canvas_size: tuple[int, int],
    top_text: str,
    bottom_text: str,
    t_sec: float,
    t_start: float,
    font_top: ImageFont.FreeTypeFont,
    font_bottom: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    top_color: tuple[int, int, int] = (255, 255, 255),
    bottom_color: tuple[int, int, int] = (255, 215, 0),
    watermark_text: str = "$$$$",
    font_watermark: ImageFont.FreeTypeFont | None = None,
) -> Image.Image:
    """
    Premiere Pro #6 / #19 / #20 / #32 MONEY $100:
    - Optional giant 14% opacity watermark ('$$$$') behind main 2-tier text.
    - Soft Linear Wipe (-90 deg, Feather 45) with a glowing blurred leading edge.
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    u = clamp((t_sec - t_start) / 0.44)
    e = ease_out_cubic(u)
    cx, cy = center_xy

    fw = font_watermark or font_bottom
    _, tw_top, _ = _measure_va_text_span(top_text, font_top) if top_text else (0.0, 0.0, 0.0)
    _, tw_bot, th_bot = _measure_va_text_span(bottom_text, font_bottom) if bottom_text else (0.0, 0.0, 0.0)
    _, tw_wm, _ = _measure_va_text_span(watermark_text, fw) if watermark_text else (0.0, 0.0, 0.0)
    tw = max(tw_top, tw_bot, tw_wm * 0.85)
    box_w = max(920, int(math.ceil(tw + 140)))
    box_h = max(280, int(math.ceil(th_bot + 160)))
    sharp = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(sharp)

    # 1. Background giant watermark (#32 '$$$$' at 14% opacity)
    if watermark_text:
        ww = dr.textlength(nfc(watermark_text), font=fw)
        dr.text(((box_w - ww) / 2, 48), nfc(watermark_text), font=fw, fill=(*bottom_color, 38))

    # 2. Foreground 2-tier text
    if top_text:
        tw_t = dr.textlength(nfc(top_text), font=font_top)
        dr.text(((box_w - tw_t) / 2, 32), nfc(top_text), font=font_top, fill=(*top_color, 255))
    if bottom_text:
        bw = dr.textlength(nfc(bottom_text), font=font_bottom)
        dr.text(((box_w - bw) / 2, 92), nfc(bottom_text), font=font_bottom, fill=(*bottom_color, 255))

    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=18.0))
    blurred = add_colored_glow(blurred, glow_rgb=bottom_color, radius=24.0, intensity=1.1)

    arr_s = np.array(sharp, dtype=np.float32)
    arr_b = np.array(blurred, dtype=np.float32)
    xs = np.arange(box_w, dtype=np.float32)[None, :, None]
    feather = 135.0
    wipe_x = -feather + (box_w + feather * 2.2) * e
    mask_s = np.clip((wipe_x - xs) / feather, 0.0, 1.0)
    mask_b = np.clip((wipe_x + 45.0 - xs) / (feather * 1.2), 0.0, 1.0) * (1.0 - 0.65 * mask_s)

    comp = np.clip(arr_s * mask_s + arr_b * mask_b, 0, 255).astype(np.uint8)
    lay = Image.fromarray(comp)
    dx = int(-16 * (1.0 - e))
    _composite_va_box(out, lay, cx, cy - box_h * 0.5, dx=dx)
    return out


# ==============================================================================
# FAM_06: OVERLAPPING CHARACTER ROLL-OUT (TELESCOPING ACCORDION)
# Presets: #15 Subtitles, #16 Movement Fluid, #22 Create Freely, #23 Stay stunning,
#          #24 Made Simple, #27 Edit Customize Presets, #28 Text Spotlight,
#          #34 THE ESSENTIAL, #35 Instant upgrades
# ==============================================================================
def render_va_fam06_overlapping_character_rollout(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    color_rgb: tuple[int, int, int] = (255, 255, 255),
    second_word_color: tuple[int, int, int] | None = None,
    slide_px: float = 34.0,
    char_stagger_sec: float = 0.032,
    char_dur_sec: float = 0.16,
    moving_spotlight: bool = False,
    word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Signature @vietanh.videoeditor mechanism (#15, #16, #22, #23, #24, #27, #28, #34, #35):
    Each character i starts at (x_i - slide_px), overlapping character i-1, while its opacity
    reaches 100% by u_i = 0.38 so adjacent letters visibly telescope/overlap ('l+e', 'E+M', 't+o', 'g+h')
    at the right leading edge before sliding into place!
    Supports `word_colors`, `second_word_color`, AND inline `[color:word]` multi-hue tags!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start or not text:
        return out

    base_rgb = resolve_va_color_token(color_rgb, (255, 255, 255))
    clean_txt, char_rgbs = resolve_va_char_colors(
        text, base_rgb, word_colors=word_colors, second_word_color=second_word_color
    )
    if not clean_txt:
        return out
    has_multi = len(set(char_rgbs)) > 1

    chars, total_w, total_h = measure_char_positions(clean_txt, font, tracking=0.0)
    _, ink_w, ink_h = _measure_va_text_span(clean_txt, font)
    tw = max(total_w, ink_w)
    box_w = max(920, int(math.ceil(tw + 140 + max(0.0, slide_px))))
    box_h = max(220, int(math.ceil(max(total_h, ink_h) + 128)))

    cx, cy = center_xy
    local_cx = box_w * 0.5
    local_cy = box_h * 0.5
    start_x = max(50.0, local_cx - total_w / 2.0)
    base_y = local_cy - total_h / 2.0

    head_x = start_x
    head_rgb = base_rgb
    box_lay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    lay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)

    for i, (ch, rel_x, cw, ch_h) in enumerate(chars):
        if ch == " ":
            continue
        u_i = clamp((t_sec - t_start - i * char_stagger_sec) / char_dur_sec)
        if u_i <= 0.0:
            continue
        e_i = ease_out_cubic(u_i)
        # Reaches 100% opacity at u_i = 0.38 -> produces exact overlapping letters at the front wave!
        alpha_i = int(255 * clamp(u_i * 2.65, 0.0, 1.0))
        x_draw = start_x + rel_x - slide_px * (1.0 - e_i)
        c_rgb = char_rgbs[i] if i < len(char_rgbs) else base_rgb
        if x_draw + cw * 0.5 >= head_x:
            head_x = x_draw + cw * 0.5
            head_rgb = c_rgb
        dr.text((x_draw, base_y), ch, font=font, fill=(*c_rgb, alpha_i))

    if moving_spotlight:
        spot = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        sdr = ImageDraw.Draw(spot)
        r = 95
        sdr.ellipse([int(head_x - r), int(local_cy - r * 0.65), int(head_x + r), int(local_cy + r * 0.65)], fill=(*head_rgb, 90))
        spot = spot.filter(ImageFilter.GaussianBlur(radius=32))
        box_lay = Image.alpha_composite(box_lay, spot)

    fallback_glow = resolve_va_color_token(second_word_color, base_rgb) if second_word_color else base_rgb
    lay = add_chromatic_layer_glow(
        lay, fallback_rgb=fallback_glow, radius=18.0, intensity=0.55, has_multicolor=has_multi
    )
    box_lay = Image.alpha_composite(box_lay, lay)
    _composite_va_box(out, box_lay, cx, cy - box_h * 0.5)
    return out


# ==============================================================================
# FAM_07: BOUNDARY-FIRST / NON-LINEAR INTERLEAVED UNFOLD
# Presets: #17 Next Chapter (N_t -> Nxt -> Next), #25 Clean style (Cle_yle -> Clean style),
#          #33 fresh / MINT (f_h -> frsh -> fresh)
# ==============================================================================
def render_va_fam07_boundary_first_interleaved_unfold(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    color_rgb: tuple[int, int, int] = (255, 255, 255),
    inward_pinch_px: float = 24.0,
    word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Premiere Pro #17 Next / #25 Clean style / #33 fresh:
    Outer boundary characters (leftmost & rightmost) appear FIRST pinched slightly inward (+-inward_pinch_px),
    leaving a gap in the middle ('N  t', 'Cle  yle', 'f  h'). Then middle characters pop in at the center
    and push the outer boundaries outward to their final kerning!
    Supports `word_colors` AND inline `[color:word]` multi-hue tags!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start or not text:
        return out

    base_rgb = resolve_va_color_token(color_rgb, (255, 255, 255))
    clean_txt, char_rgbs = resolve_va_char_colors(text, base_rgb, word_colors=word_colors)
    if not clean_txt:
        return out
    has_multi = len(set(char_rgbs)) > 1

    chars, total_w, total_h = measure_char_positions(clean_txt, font, tracking=0.0)
    n = max(1, len(chars))
    mid = (n - 1) / 2.0
    max_rank = max(1.0, math.ceil(mid))

    cx, cy = center_xy
    start_x = max(55.0, min(w - total_w - 55.0, cx - total_w / 2.0))
    base_y = cy - total_h / 2.0

    u_global = clamp((t_sec - t_start) / 0.38)
    e_global = ease_out_cubic(u_global)
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)

    for i, (ch, rel_x, cw, ch_h) in enumerate(chars):
        if ch == " ":
            continue
        # Rank 0 = outer boundary letters (appear at t_start), highest rank = center letters!
        rank = min(i, n - 1 - i)
        delay = (rank / max_rank) * 0.16
        u_i = clamp((t_sec - t_start - delay) / 0.16)
        if u_i <= 0.0:
            continue
        e_i = ease_out_back(u_i, overshoot=1.12)
        # Outer letters start pinched toward the center and expand outward as center letters pop in
        dir_from_mid = -1.0 if i < mid else (1.0 if i > mid else 0.0)
        pinch_dx = -dir_from_mid * inward_pinch_px * (1.0 - e_global)
        x_draw = start_x + rel_x + pinch_dx
        y_draw = base_y + 8.0 * (1.0 - e_i)
        alpha_i = int(255 * clamp(u_i * 2.2, 0.0, 1.0))
        c_rgb = char_rgbs[i] if i < len(char_rgbs) else base_rgb
        dr.text((x_draw, y_draw), ch, font=font, fill=(*c_rgb, alpha_i))

    lay = add_chromatic_layer_glow(
        lay, fallback_rgb=base_rgb, radius=16.0, intensity=0.5, has_multicolor=has_multi
    )
    out = Image.alpha_composite(out, lay)
    return out


# ==============================================================================
# FAM_08: PER-CHARACTER BOTTOM-ANCHORED STEP-UP & COLOR TINT LERP
# Presets: #7 Central Focus, #11 Fully Customizable, #18 New Creative Today, #21 New Creative
# ==============================================================================
def render_va_fam08_bottom_anchored_stepup_color_lerp(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    start_rgb: tuple[int, int, int] = (158, 56, 20),
    end_rgb: tuple[int, int, int] = (255, 255, 255),
    char_stagger_sec: float = 0.032,
    underline_color: tuple[int, int, int] | None = None,
) -> Image.Image:
    """
    Premiere Pro #11 Fully Customizable & #18 New Creative Today & #21 Underline:
    Each character scales from 35% -> 100% anchored at its bottom baseline while stepping up
    from +16px -> 0px (creating the visible staircase on trailing characters 'i-v-e'),
    and interpolating color from start_rgb (#9E3814 dark amber) to end_rgb (#FFFFFF).
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start or not text:
        return out

    text = nfc(text)
    chars, total_w, total_h = measure_char_positions(text, font, tracking=0.0)
    cx, cy = center_xy
    start_x = max(55.0, min(w - total_w - 55.0, cx - total_w / 2.0))
    base_y = cy - total_h / 2.0

    for i, (ch, rel_x, cw, ch_h) in enumerate(chars):
        if ch == " ":
            continue
        u_i = clamp((t_sec - t_start - i * char_stagger_sec) / 0.18)
        if u_i <= 0.0:
            continue
        e_i = ease_out_back(u_i, overshoot=1.10)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * clamp(u_i * 1.25))
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * clamp(u_i * 1.25))
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * clamp(u_i * 1.25))
        alpha_i = int(255 * clamp(u_i * 1.8, 0.0, 1.0))

        # Bottom-anchored scale + staircase step-up (+16px -> 0px)
        scale_i = clamp(0.38 + 0.62 * e_i, 0.25, 1.08)
        dy_i = 16.0 * (1.0 - clamp(u_i * 1.15))

        gw, gh = max(8, int(cw + 36)), max(8, int(total_h + 44))
        g_img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        ImageDraw.Draw(g_img).text((18, 14), ch, font=font, fill=(r, g, b, alpha_i))
        nw, nh = max(1, int(gw * scale_i)), max(1, int(gh * scale_i))
        g_rs = g_img.resize((nw, nh), Image.Resampling.BICUBIC)
        px = int(start_x + rel_x - 18 * scale_i)
        py = int(base_y - 14 + (gh - nh) + dy_i)
        out.alpha_composite(g_rs, (max(10, min(w - nw - 10, px)), max(10, min(h - nh - 10, py))))

    if underline_color is not None:
        u_line = ease_out_cubic(clamp((t_sec - t_start) / 0.34))
        lw = int(total_w * 0.45 * u_line)
        if lw > 2:
            ul = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(ul).rounded_rectangle(
                [int(start_x), int(base_y + total_h + 10), int(start_x + lw), int(base_y + total_h + 17)],
                radius=3, fill=(*underline_color, 255)
            )
            ul = add_colored_glow(ul, glow_rgb=underline_color, radius=14.0, intensity=0.9)
            out = Image.alpha_composite(out, ul)

    return out


# ==============================================================================
# FAM_09: DELAYED NEON STRIKETHROUGH (#8 Error) & GOLDEN BOKEH COLLAPSE (#14 Premium Text)
# Presets: #8 Error, #12 Colorful Text, #13 VHS, #14 Premium Text
# ==============================================================================
def render_va_fam09_error_neon_strikethrough(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    bar_delay_sec: float = 0.28,
    bar_rgb: tuple[int, int, int] = (255, 45, 65),
    text_rgb: tuple[int, int, int] = (255, 255, 255),
    word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Premiere Pro #8 Error (2-Phase Choreography):
    - Phase 1 (t_start .. t_start + 0.28s): Text de-blurs cleanly (Gaussian Blur 26 -> 0, Scale 92% -> 100%).
      NO strike bar yet!
    - Phase 2 (t_start + 0.28s .. +0.58s): A horizontal neon laser bar (`bar_rgb`) shoots from left to right
      (Scale X: 0% -> 100%) across the middle of the word, casting a colored Linear Dodge (Add) glow!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start or not text:
        return out

    resolved_bar = resolve_va_color_token(bar_rgb, (255, 45, 65))
    resolved_txt = resolve_va_color_token(text_rgb, (255, 255, 255))
    clean_txt, char_rgbs = resolve_va_char_colors(text, resolved_txt, word_colors=word_colors)
    if not clean_txt:
        return out

    u_txt = clamp((t_sec - t_start) / 0.28)
    e_txt = ease_out_cubic(u_txt)
    cx, cy = center_xy

    dummy = ImageDraw.Draw(out)
    tw = dummy.textlength(clean_txt, font=font)
    bb = dummy.textbbox((0, 0), clean_txt, font=font)
    th = bb[3] - bb[1]
    tx0 = int(cx - tw / 2)
    ty0 = int(cy - th / 2)

    # Phase 1: Text De-Blur
    txt_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_multicolor_line(
        ImageDraw.Draw(txt_lay),
        (tx0, ty0 + int(10 * (1.0 - e_txt))),
        clean_txt,
        char_rgbs,
        font,
        alpha=int(255 * e_txt),
    )
    blur_r = 20.0 * math.pow(1.0 - u_txt, 1.6)
    if blur_r > 0.35:
        txt_lay = txt_lay.filter(ImageFilter.GaussianBlur(radius=blur_r))
    out = Image.alpha_composite(out, txt_lay)

    # Phase 2: Delayed Neon Strikethrough Bar shooting Left -> Right
    if t_sec >= t_start + bar_delay_sec:
        u_bar = clamp((t_sec - (t_start + bar_delay_sec)) / 0.28)
        e_bar = ease_out_cubic(u_bar)
        bar_full_w = int(tw + 28)
        bar_cur_w = max(4, int(bar_full_w * e_bar))
        bx0 = tx0 - 14
        by_mid = int(ty0 + th * 0.56)

        bar_lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(bar_lay).rounded_rectangle(
            [bx0, by_mid - 5, bx0 + bar_cur_w, by_mid + 5], radius=4, fill=(*resolved_bar, 255)
        )
        bar_glow = add_colored_glow(bar_lay, glow_rgb=resolved_bar, radius=26.0, intensity=1.65)
        out = Image.alpha_composite(out, bar_glow)

    return out


def render_va_fam09_golden_bokeh_collapse(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    palette_mode: str = "gold",
) -> Image.Image:
    """
    Premiere Pro #14 Premium Text (`v5.2` Multi-Hue Metallic Bokeh):
    Gaussian Blur (55 -> 0) placed BEFORE Alpha Levels / Morphological Dilation so the text starts
    as glowing round bokeh orbs that collapse into sharp metallic letters!
    `palette_mode`: `"gold"`, `"mint"`, `"cyan"`, `"violet"`, `"lime"`, `"coral"` (or `"peach"`).
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    clean_txt = strip_va_inline_tags(text)
    if t_sec < t_start or not clean_txt:
        return out

    u = clamp((t_sec - t_start) / 0.42)
    e = ease_out_cubic(u)
    cx, cy = center_xy

    adv_bk, tw_bk, th_bk = _measure_va_text_span(clean_txt, font)
    box_w = max(920, int(math.ceil(tw_bk + 140)))
    box_h = max(220, int(math.ceil(th_bk + 120)))
    mask_pil = Image.new("L", (box_w, box_h), 0)
    dr = ImageDraw.Draw(mask_pil)
    dr.text(((box_w - adv_bk) / 2, 48), clean_txt, font=font, fill=255)
    mask_np = np.array(mask_pil)

    if u < 0.96:
        # Morphological circular bokeh dilation + blur + alpha threshold choke
        rad = max(1, int(22 * (1.0 - e)))
        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rad * 2 + 1, rad * 2 + 1))
        dil = cv2.dilate(mask_np, kern, iterations=1)
        sigma = max(0.8, 18.0 * (1.0 - e))
        blurred = cv2.GaussianBlur(dil, (0, 0), sigmaX=sigma, sigmaY=sigma)
        # Boost & round bokeh lobes
        gain = 1.0 + 1.85 * (1.0 - e)
        mask_np = np.clip(blurred.astype(np.float32) * gain, 0, 255).astype(np.uint8)

    pal = VA_BOKEH_METALLIC_PALETTES.get(str(palette_mode or "gold").strip().lower(), VA_BOKEH_METALLIC_PALETTES["gold"])
    top_c, bot_c, glow_c = pal["top"], pal["bot"], pal["glow"]

    ys = np.linspace(0.0, 1.0, box_h, dtype=np.float32)[:, None]
    r_ch = np.clip(top_c[0] + (bot_c[0] - top_c[0]) * ys, 0, 255).astype(np.uint8)
    g_ch = np.clip(top_c[1] + (bot_c[1] - top_c[1]) * ys, 0, 255).astype(np.uint8)
    b_ch = np.clip(top_c[2] + (bot_c[2] - top_c[2]) * ys, 0, 255).astype(np.uint8)
    rgb = np.zeros((box_h, box_w, 4), dtype=np.uint8)
    rgb[:, :, 0] = r_ch
    rgb[:, :, 1] = g_ch
    rgb[:, :, 2] = b_ch
    rgb[:, :, 3] = (mask_np.astype(np.float32) * min(1.0, u * 2.2)).astype(np.uint8)

    lay = Image.fromarray(rgb)
    lay = add_colored_glow(lay, glow_rgb=glow_c, radius=24.0, intensity=1.15 * (1.2 - 0.4 * e))
    _composite_va_box(out, lay, cx, cy - box_h * 0.5)
    return out


# ==============================================================================
# FAM_10: 3D Y-AXIS CHARACTER SWIVEL (#30) & VERTICAL HORIZON GRADIENT RISE (#29, #31)
# Presets: #29 Energy Rising, #30 Dynamic Rotating, #31 Future Digital
# ==============================================================================
def render_va_fam10_3d_y_swivel_characters(
    canvas_size: tuple[int, int],
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    color_rgb: tuple[int, int, int] = (255, 255, 255),
    char_stagger_sec: float = 0.032,
    word_colors: dict[int, tuple[int, int, int]] | None = None,
) -> Image.Image:
    """
    Premiere Pro #30 Dynamic Rotating:
    Each character flips 90 deg -> 0 deg around its vertical Y axis (Basic 3D > Swivel: -90 -> 0),
    projected as horizontal scale_x = cos(theta_i) and dx = -18 * sin(theta_i).
    Supports `word_colors` AND inline `[color:word]` multi-hue tags!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start or not text:
        return out

    base_rgb = resolve_va_color_token(color_rgb, (255, 255, 255))
    clean_txt, char_rgbs = resolve_va_char_colors(text, base_rgb, word_colors=word_colors)
    if not clean_txt:
        return out
    has_multi = len(set(char_rgbs)) > 1

    chars, total_w, total_h = measure_char_positions(clean_txt, font, tracking=0.0)
    cx, cy = center_xy
    start_x = max(55.0, min(w - total_w - 55.0, cx - total_w / 2.0))
    base_y = cy - total_h / 2.0

    for i, (ch, rel_x, cw, ch_h) in enumerate(chars):
        if ch == " ":
            continue
        u_i = clamp((t_sec - t_start - i * char_stagger_sec) / 0.20)
        if u_i <= 0.0:
            continue
        e_i = ease_out_cubic(u_i)
        theta = (1.0 - e_i) * (math.pi / 2.0)
        scale_x = max(0.06, math.cos(theta))
        dx = -18.0 * math.sin(theta)
        alpha_i = int(255 * clamp(u_i * 2.2, 0.0, 1.0))
        c_rgb = char_rgbs[i] if i < len(char_rgbs) else base_rgb

        gw, gh = max(8, int(cw + 32)), max(8, int(total_h + 40))
        g_img = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        ImageDraw.Draw(g_img).text((16, 12), ch, font=font, fill=(*c_rgb, alpha_i))
        nw = max(1, int(gw * scale_x))
        g_rs = g_img.resize((nw, gh), Image.Resampling.BICUBIC)
        px = int(start_x + rel_x + (gw - nw) * 0.5 - 16 + dx)
        py = int(base_y - 12)
        out.alpha_composite(g_rs, (max(10, min(w - nw - 10, px)), max(10, min(h - gh - 10, py))))

    out = add_chromatic_layer_glow(
        out, fallback_rgb=base_rgb, radius=16.0, intensity=0.5, has_multicolor=has_multi
    )
    return out


def render_va_fam10_vertical_horizon_gradient_rise(
    canvas_size: tuple[int, int],
    top_label: str,
    hero_text: str,
    t_sec: float,
    t_start: float,
    font_top: ImageFont.FreeTypeFont,
    font_hero: ImageFont.FreeTypeFont,
    center_xy: tuple[int, int] = (540, 480),
    top_rgb: tuple[int, int, int] = (255, 165, 0),
    mid_rgb: tuple[int, int, int] = (220, 55, 0),
    bot_rgb: tuple[int, int, int] = (24, 6, 0),
) -> Image.Image:
    """
    Premiere Pro #29 Energy Rising & #31 Future Digital:
    - Top uppercase label ('ENERGY' / 'FUTURE') reveals with wide tracking.
    - Hero word ('rising' / 'Digital') rises character-by-character from dark bottom (+20px -> 0px)
      through a fixed screen-space vertical horizon gradient (Bright Gold/Blue at top -> Dark shadow at bottom).
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out
    cx, cy = center_xy

    # 1. Top tracked label
    if top_label:
        u_top = clamp((t_sec - t_start) / 0.25)
        e_top = ease_out_cubic(u_top)
        dr_o = ImageDraw.Draw(out)
        tw = dr_o.textlength(nfc(top_label), font=font_top)
        dr_o.text((max(50, cx - tw / 2), cy - 78 + int(10 * (1.0 - e_top))), nfc(top_label), font=font_top, fill=(255, 255, 255, int(245 * e_top)))

    # 2. Hero text with fixed screen-space vertical horizon gradient
    chars, total_w, total_h = measure_char_positions(hero_text, font_hero, tracking=0.0)
    _, ink_w_h, ink_h_h = _measure_va_text_span(hero_text, font_hero)
    box_w = max(920, int(math.ceil(max(total_w, ink_w_h) + 140)))
    box_h = max(210, int(math.ceil(max(total_h, ink_h_h) + 116)))
    mask_pil = Image.new("L", (box_w, box_h), 0)
    dr_m = ImageDraw.Draw(mask_pil)
    sx = (box_w - total_w) / 2.0
    for i, (ch, rel_x, cw, ch_h) in enumerate(chars):
        if ch == " ":
            continue
        u_i = clamp((t_sec - t_start - 0.06 - i * 0.032) / 0.20)
        if u_i <= 0.0:
            continue
        e_i = ease_out_cubic(u_i)
        dy_i = 22.0 * (1.0 - e_i)
        dx_i = -18.0 * (1.0 - e_i)
        dr_m.text((sx + rel_x + dx_i, 32 + dy_i), ch, font=font_hero, fill=int(255 * clamp(u_i * 2.2)))

    mask_np = np.array(mask_pil)
    ys = np.linspace(0.0, 1.0, box_h, dtype=np.float32)[:, None]
    # 2-stop vertical gradient: top_rgb -> mid_rgb -> bot_rgb
    t1 = np.clip(ys * 1.8, 0.0, 1.0)
    t2 = np.clip((ys - 0.45) * 1.8, 0.0, 1.0)
    r_col = (top_rgb[0] * (1 - t1) + mid_rgb[0] * t1) * (1 - t2) + bot_rgb[0] * t2
    g_col = (top_rgb[1] * (1 - t1) + mid_rgb[1] * t1) * (1 - t2) + bot_rgb[1] * t2
    b_col = (top_rgb[2] * (1 - t1) + mid_rgb[2] * t1) * (1 - t2) + bot_rgb[2] * t2

    rgba = np.zeros((box_h, box_w, 4), dtype=np.uint8)
    rgba[:, :, 0] = np.clip(r_col, 0, 255).astype(np.uint8)
    rgba[:, :, 1] = np.clip(g_col, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = np.clip(b_col, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = mask_np

    lay = Image.fromarray(rgba)
    lay = add_colored_glow(lay, glow_rgb=top_rgb, radius=22.0, intensity=0.85)
    _composite_va_box(out, lay, cx, cy - 28)
    return out


if __name__ == "__main__":
    W, H = 1080, 640
    try:
        f_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        f_hero = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    except Exception:
        f_sub = ImageFont.load_default()
        f_hero = ImageFont.load_default()

    # Verify backward-compatible legacy signatures + v6.0 unclipped dynamic box_w (`hệ thống xưởng media`)
    im01 = render_va_fam01_baseline_mask_slide((W, H), "Luôn phải [mint:khóa]", "[gold:KẾT CẤU] [cyan:60FPS]", 0.45, 0.0, f_sub, f_hero)
    im01_wide = render_va_fam01_baseline_mask_slide((W, H), "vận hành đồng bộ", "hệ thống xưởng media", 0.55, 0.0, f_sub, f_hero)
    im05_wide = render_va_fam05_soft_wipe_glow_watermark((W, H), "tự động hóa quy trình", "hệ thống xưởng media", 0.55, 0.0, f_sub, f_hero)
    im03 = render_va_fam03_center_cursor_bars_expand((W, H), "CHUẨN [mint:Z-DEPTH] [gold:PRO]", 0.35, 0.0, f_hero, bar_color=(56, 189, 248))
    im06 = render_va_fam06_overlapping_character_rollout(
        (W, H), "hệ thống xưởng media", 0.85, 0.0, f_hero, word_colors={0: (45, 212, 191), 2: (250, 204, 21)}, moving_spotlight=True
    )
    im07 = render_va_fam07_boundary_first_interleaved_unfold((W, H), "[violet:ÁNH SÁNG] [mint:THẬT]", 0.40, 0.0, f_hero)
    im09_err = render_va_fam09_error_neon_strikethrough((W, H), "KHÔNG BIẾN DẠNG", 0.55, 0.0, f_hero, bar_rgb=(255, 77, 94), text_rgb=(248, 250, 252))
    for mode in ("gold", "mint", "cyan", "violet", "lime", "coral"):
        im09_bk = render_va_fam09_golden_bokeh_collapse((W, H), f"STUDIO {mode.upper()}", 0.36, 0.0, f_hero, palette_mode=mode)
        assert im09_bk.size == (W, H)
    im10 = render_va_fam10_3d_y_swivel_characters((W, H), "[cyan:AI] [lime:CHUYỂN ĐỘNG]", 0.45, 0.0, f_hero)
    assert im01_wide.getbbox() is not None and im05_wide.getbbox() is not None and im06.getbbox() is not None
    print(
        "vietanh_35_typography_engine v6.0 self-test OK! Rendered sizes:",
        im01.size, im01_wide.size, im05_wide.size, im06.size, im07.size, im10.size,
    )

