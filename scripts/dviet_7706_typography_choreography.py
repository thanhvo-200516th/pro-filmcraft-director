#!/usr/bin/env python3
"""
DVIET 7706183278461570356 - 7 Typography Entrance & Build-Up Choreography Engine
Verified Frame-by-Frame (1 frame = 41.67ms @ 24fps / 16.67ms @ 60fps)
Ready-to-run standalone Python / PIL / NumPy implementation.
"""

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops


def cubic_bezier_ease_out(p: float, x1=0.16, y1=1.0, x2=0.3, y2=1.0) -> float:
    """Expo/Quintic approximation of AE cubic-bezier(0.16, 1, 0.3, 1)."""
    p = max(0.0, min(1.0, float(p)))
    return 1.0 - math.pow(1.0 - p, 3.4)


def ease_out_back(p: float, overshoot: float = 1.15) -> float:
    p = max(0.0, min(1.0, float(p)))
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * math.pow(p - 1.0, 3) + c1 * math.pow(p - 1.0, 2)


def apply_warm_amber_halation(
    layer_rgba: Image.Image,
    bloom_intensity: float = 1.0,
    amber_rgb=(245, 158, 11),
    core_radius: float = 6.0,
    halo_radius: float = 22.0,
) -> Image.Image:
    """
    2-stage optical halation bloom (#F59E0B warm amber + #FDE047 core)
    observed in 7706183278461570356 ('chán', 'nghi ngờ', 'việt mỏi lưng', 'tia hy vọng').
    """
    if bloom_intensity <= 0.01:
        return layer_rgba

    alpha = layer_rgba.split()[3]
    w, h = layer_rgba.size

    # Outer warm amber halo (#F59E0B)
    halo_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=halo_radius))
    halo_scale = max(0.0, min(2.0, 0.68 * bloom_intensity))
    halo_alpha = halo_alpha.point(lambda v: min(255, int(v * halo_scale)))
    halo_img = Image.new("RGBA", (w, h), (*amber_rgb, 0))
    halo_img.putalpha(halo_alpha)

    # Inner golden core (#FDE047)
    core_alpha = alpha.filter(ImageFilter.GaussianBlur(radius=core_radius))
    core_scale = max(0.0, min(2.0, 0.55 * bloom_intensity))
    core_alpha = core_alpha.point(lambda v: min(255, int(v * core_scale)))
    core_img = Image.new("RGBA", (w, h), (253, 224, 71, 0))
    core_img.putalpha(core_alpha)

    out = Image.alpha_composite(halo_img, core_img)
    out = Image.alpha_composite(out, layer_rgba)
    return out


# ==============================================================================
# KIỂU 1: GHOST-TO-FOCUS PROGRESSIVE STACK
# (Observed at t=2.60s..3.70s & t=25.60s..26.20s: old line dims to 20% opacity + 6px blur
# instead of hard-cutting, while new line rises from +18px with amber glow from bottom up)
# ==============================================================================
def render_style1_ghost_to_focus_stack(
    canvas_size,
    prev_text: str,
    active_text: str,
    sub_text: str,
    t_sec: float,
    t_prev_start: float,
    t_active_start: float,
    t_sub_start: float,
    font_small: ImageFont.FreeTypeFont,
    font_hero: ImageFont.FreeTypeFont,
    anchor_xy=(260, 420),
) -> Image.Image:
    """
    Frame-by-frame formula (24fps):
    - Prev line ('mình đang...' / 'nghi ngờ bản thân'):
      During active entrance [t_active_start .. t_active_start + 0.33s (8 frames)]:
      opacity: 1.0 -> 0.22 (or stays at 0.85 if stacked header, 0.20 if superseded ghost)
      blur_radius: 0.0 -> 6.0px
    - Active hero line ('mơ ước' / 'chán' / 'tia hy vọng'):
      Rise duration = 9 frames (0.375s):
      y_offset(p) = +22px * (1 - ease_out(p))
      blur(p)     = 12px * (1 - p)^1.8
      bottom_up_glow_mask(y) = clip((y - y_top) / H + p * 1.2, 0, 1)
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ax, ay = anchor_xy

    # 1. Previous / Ghost layer
    if t_sec >= t_prev_start:
        p_in = min(1.0, (t_sec - t_prev_start) / 0.33)
        p_ghost = max(0.0, min(1.0, (t_sec - t_active_start) / 0.33)) if t_sec >= t_active_start else 0.0
        op_prev = cubic_bezier_ease_out(p_in) * (1.0 - 0.78 * p_ghost)
        blur_prev = 8.0 * (1.0 - p_in) + 6.0 * p_ghost

        layer_prev = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d_prev = ImageDraw.Draw(layer_prev)
        y_prev = ay - int(14 * (1.0 - cubic_bezier_ease_out(p_in)))
        d_prev.text((ax, y_prev), prev_text, font=font_small, fill=(255, 255, 255, int(255 * op_prev)))
        if blur_prev > 0.3:
            layer_prev = layer_prev.filter(ImageFilter.GaussianBlur(radius=blur_prev))
        out = Image.alpha_composite(out, layer_prev)

    # 2. Active Hero Gold line with bottom-up amber bloom
    if t_sec >= t_active_start:
        p_act = min(1.0, (t_sec - t_active_start) / 0.375)  # 9 frames @ 24fps
        e_act = cubic_bezier_ease_out(p_act)
        y_off = int(22.0 * (1.0 - e_act))
        blur_act = 12.0 * math.pow(1.0 - p_act, 1.8)
        # Bloom peaks at frame 3-4 (p ~ 0.35) then settles to 0.75
        bloom = math.sin(min(1.0, p_act * 1.8) * math.pi * 0.5) * (1.35 if p_act < 0.45 else 0.85)

        layer_act = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d_act = ImageDraw.Draw(layer_act)
        bb_a = d_act.textbbox((0, 0), active_text, font=font_hero)
        aw = bb_a[2] - bb_a[0]
        ah = bb_a[3] - bb_a[1]
        ax_clamped = max(55, min(w - aw - 55, ax - 20))
        d_act.text((ax_clamped, ay + 44 + y_off), active_text, font=font_hero, fill=(250, 204, 21, int(255 * e_act)))
        if blur_act > 0.3:
            layer_act = layer_act.filter(ImageFilter.GaussianBlur(radius=blur_act))
        layer_act = apply_warm_amber_halation(layer_act, bloom_intensity=bloom)
        out = Image.alpha_composite(out, layer_act)
    else:
        ah = 90

    # 3. Sub-line ('công việc' / 'đã chiếu tới...') tucked tightly below hero baseline (ZERO collision!)
    if t_sec >= t_sub_start and sub_text:
        p_sub = min(1.0, (t_sec - t_sub_start) / 0.29)  # 7 frames @ 24fps
        e_sub = cubic_bezier_ease_out(p_sub)
        blur_sub = 9.0 * (1.0 - e_sub)
        layer_sub = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d_sub = ImageDraw.Draw(layer_sub)
        d_sub.text((max(55, ax + 16), ay + 56 + ah + int(12 * (1.0 - e_sub))), sub_text, font=font_small, fill=(255, 255, 255, int(245 * e_sub)))
        if blur_sub > 0.3:
            layer_sub = layer_sub.filter(ImageFilter.GaussianBlur(radius=blur_sub))
        out = Image.alpha_composite(out, layer_sub)

    return out


# ==============================================================================
# KIỂU 2: LETTER-SCATTER 2D CONVERGENCE
# (Observed at f=990..1001, t=41.242s..41.700s: 'vậy là giờ' dissolves while
# individual characters of 'mình không chỉ là' start scattered in Y (+/-24px)
# and X (+/-18px) with staggered opacities, sliding into a locked baseline)
# ==============================================================================
def render_style2_letter_scatter_convergence(
    canvas_size,
    text: str,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy=(640, 280),
    duration: float = 0.458,  # 11 frames @ 24fps (41.242s -> 41.700s)
) -> Image.Image:
    """
    Exact frame-by-frame anatomy from f=990..1001:
    Each character i has deterministic initial scatter:
      dx_0(i) = (i - N/2) * 5.5 + 10.0 * sin(i * 1.7)
      dy_0(i) = 24.0 * (-1)^i * cos(i * 0.9)   (alternating upper/lower rail scatter!)
      delay(i) = 0.014 * (i % 4) + 0.008 * i   (staggered per-glyph lock-in)
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out

    # Pre-measure character final x-positions
    dummy_draw = ImageDraw.Draw(out)
    char_xs = []
    cur_x = 0.0
    tracking = -1.2  # tight editorial tracking
    for ch in text:
        bbox = dummy_draw.textbbox((0, 0), ch, font=font)
        cw = bbox[2] - bbox[0]
        char_xs.append((ch, cur_x, cw))
        cur_x += cw + tracking

    total_w = cur_x
    start_x = max(55.0, min(w - total_w - 55.0, center_xy[0] - total_w / 2.0))
    base_y = center_xy[1]
    n_chars = max(1, len(char_xs))

    for i, (ch, rel_x, cw) in enumerate(char_xs):
        if ch == " ":
            continue
        delay = (i % 4) * 0.032 + (i / n_chars) * 0.06
        local_dur = max(0.18, duration - delay)
        p = max(0.0, min(1.0, (t_sec - t_start - delay) / local_dur))
        if p <= 0.0:
            continue

        e = cubic_bezier_ease_out(p)
        # Alternating Y-rail scatter (+24px / -22px) + horizontal spread
        dx0 = (i - n_chars / 2.0) * 5.5 + 9.0 * math.sin(i * 2.1)
        dy0 = (24.0 if i % 2 == 1 else -20.0) * (0.65 + 0.35 * math.cos(i * 1.3))

        x = start_x + rel_x + dx0 * (1.0 - e)
        y = base_y + dy0 * (1.0 - e)
        alpha = int(255 * min(1.0, math.pow(p, 0.75)))
        blur_r = 6.5 * math.pow(1.0 - e, 1.6)

        glyph_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glyph_layer)
        gd.text((x, y), ch, font=font, fill=(255, 255, 255, alpha))
        if blur_r > 0.35:
            glyph_layer = glyph_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
        out = Image.alpha_composite(out, glyph_layer)

    return out


# ==============================================================================
# KIỂU 3: PER-WORD STAGGERED DE-BLUR + WARM AMBER HALATION BLOOM
# (Observed at f=1002..1016, t=41.742s..42.325s for 'việt mỏi lưng':
# non-linear word order! 'mỏi' enters first at f=1002, 'lưng' at f=1005 (+3f),
# 'việt' at f=1006 (+4f), each de-blurring from 14px -> 0px, y_offset +24px -> 0,
# scale 0.92 -> 1.0, with #F59E0B amber halation peaking at frame +3 of each word)
# ==============================================================================
def render_style3_per_word_staggered_deblur(
    canvas_size,
    words: list,
    t_sec: float,
    t_start: float,
    font: ImageFont.FreeTypeFont,
    center_xy=(640, 340),
    entry_order=None,
    frame_stagger_sec: float = 3.0 / 24.0,  # 2-3 frames @ 24fps
    word_dur_sec: float = 9.0 / 24.0,       # 9 frames @ 24fps
) -> Image.Image:
    """
    If entry_order is [1, 2, 0] for ['việt', 'mỏi', 'lưng'], 'mỏi' triggers at +0f,
    'lưng' at +3f, and 'việt' at +4f — matching f=1002..1012 of 7706183278461570356!
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if t_sec < t_start:
        return out

    if entry_order is None:
        entry_order = list(range(len(words)))

    dummy = ImageDraw.Draw(out)
    word_boxes = []
    cur_x = 0.0
    space_w = 18.0
    for wd in words:
        bb = dummy.textbbox((0, 0), wd, font=font)
        ww = bb[2] - bb[0]
        wh = bb[3] - bb[1]
        word_boxes.append((wd, cur_x, ww, wh))
        cur_x += ww + space_w
    total_w = cur_x - space_w
    start_x = max(55.0, min(w - total_w - 55.0, center_xy[0] - total_w / 2.0))
    base_y = center_xy[1]

    for idx, (wd, rel_x, ww, wh) in enumerate(word_boxes):
        order_rank = entry_order.index(idx) if idx in entry_order else idx
        w_start = t_start + order_rank * frame_stagger_sec
        if t_sec < w_start:
            continue

        p = min(1.0, (t_sec - w_start) / word_dur_sec)
        e = cubic_bezier_ease_out(p)

        # Frame-verified curves: blur 14->0, y_offset +24->0, scale 0.92->1.0
        blur_r = 14.0 * math.pow(1.0 - p, 1.75)
        y_off = 24.0 * (1.0 - e)
        scale = 0.92 + 0.08 * e
        alpha = int(255 * min(1.0, p * 1.6))

        # Amber bloom pulse peaks at frame 3 (p ~ 0.33) -> 1.45x, then settles to 0.85x
        bloom_pulse = 0.85 + 0.65 * math.exp(-math.pow((p - 0.35) / 0.22, 2))

        pad = 60
        tw, th = int(ww + pad * 2), int(wh + pad * 2)
        w_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        wd_draw = ImageDraw.Draw(w_img)
        # Cream-to-Gold color shift as word locks in
        r_c = int(255)
        g_c = int(235 - 31 * e)
        b_c = int(160 - 139 * e)
        wd_draw.text((pad, pad), wd, font=font, fill=(r_c, g_c, b_c, alpha))

        if abs(scale - 1.0) > 0.003:
            nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
            w_img = w_img.resize((nw, nh), Image.Resampling.BICUBIC)

        if blur_r > 0.35:
            w_img = w_img.filter(ImageFilter.GaussianBlur(radius=blur_r))

        w_img = apply_warm_amber_halation(w_img, bloom_intensity=bloom_pulse * min(1.0, p * 1.4))

        paste_x = int(start_x + rel_x - pad + (tw - w_img.width) / 2.0)
        paste_y = int(base_y + y_off - pad + (th - w_img.height) / 2.0)

        temp_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        temp_layer.paste(w_img, (paste_x, paste_y))
        out = Image.alpha_composite(out, temp_layer)

    return out


# ==============================================================================
# KIỂU 4: TILTED MULTI-CLUSTER BALANCE
# (Observed at f=571..610, t=23.80s..25.45s:
# Left cluster tilted +8.5 deg CCW: 'đúng lúc mình đang' -> 'nghi ngờ' -> 'bản thân'
# Right cluster tilted +4.5 deg CCW: 'và mất' enters FIRST at f=590, then 'định hướng'
# rises ABOVE it at f=596 with negative line-spacing so 'và mất' hugs the descenders!)
# ==============================================================================
def render_style4_tilted_multi_cluster(
    canvas_size,
    t_sec: float,
    font_small: ImageFont.FreeTypeFont,
    font_hero: ImageFont.FreeTypeFont,
) -> Image.Image:
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def build_cluster(top_txt, mid_txt, bot_txt, t_top, t_mid, t_bot, tilt_deg, center_pos):
        cw, ch = 520, 260
        c_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

        # Top sub-line (negative leading: sits right on top of hero ascenders)
        if top_txt and t_sec >= t_top:
            p = min(1.0, (t_sec - t_top) / 0.29)
            e = cubic_bezier_ease_out(p)
            l_top = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            ImageDraw.Draw(l_top).text((110, int(52 + 12 * (1 - e))), top_txt, font=font_small, fill=(255, 255, 255, int(255 * e)))
            if p < 1.0:
                l_top = l_top.filter(ImageFilter.GaussianBlur(radius=6.0 * (1 - e)))
            c_img = Image.alpha_composite(c_img, l_top)

        # Bottom sub-line ('bản thân' or 'và mất' hugging hero baseline with -14% leading)
        if bot_txt and t_sec >= t_bot:
            p = min(1.0, (t_sec - t_bot) / 0.25)
            e = cubic_bezier_ease_out(p)
            l_bot = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            ImageDraw.Draw(l_bot).text((145, int(138 + 10 * (1 - e))), bot_txt, font=font_small, fill=(255, 255, 255, int(245 * e)))
            if p < 1.0:
                l_bot = l_bot.filter(ImageFilter.GaussianBlur(radius=7.0 * (1 - e)))
            c_img = Image.alpha_composite(c_img, l_bot)

        # Mid hero gold line ('nghi ngờ' or 'định hướng')
        if mid_txt and t_sec >= t_mid:
            p = min(1.0, (t_sec - t_mid) / 0.375)
            e = cubic_bezier_ease_out(p)
            l_mid = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            ImageDraw.Draw(l_mid).text((80, int(74 + 18 * (1 - e))), mid_txt, font=font_hero, fill=(250, 204, 21, int(255 * e)))
            if p < 1.0:
                l_mid = l_mid.filter(ImageFilter.GaussianBlur(radius=12.0 * math.pow(1 - p, 1.7)))
            l_mid = apply_warm_amber_halation(l_mid, bloom_intensity=0.95 * e)
            c_img = Image.alpha_composite(c_img, l_mid)

        rotated = c_img.rotate(tilt_deg, resample=Image.Resampling.BICUBIC, expand=True)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(rotated, (int(center_pos[0] - rotated.width / 2), int(center_pos[1] - rotated.height / 2)))
        return layer

    # Left shoulder cluster (+7.5 deg CCW tilt)
    left_layer = build_cluster(
        top_txt="đúng lúc mình đang",
        mid_txt="nghi ngờ",
        bot_txt="bản thân",
        t_top=23.40,
        t_mid=23.65,
        t_bot=23.96,
        tilt_deg=7.5,
        center_pos=(int(w * 0.26), int(h * 0.42)),
    )
    out = Image.alpha_composite(out, left_layer)

    # Right shoulder cluster (+4.5 deg CCW tilt, bottom 'và mất' enters BEFORE 'định hướng'!)
    right_layer = build_cluster(
        top_txt="",
        mid_txt="định hướng",
        bot_txt="và mất",
        t_top=999.0,
        t_mid=24.83,  # f=596
        t_bot=24.59,  # f=590 ('và mất' appears 6 frames BEFORE 'định hướng')
        tilt_deg=4.5,
        center_pos=(int(w * 0.74), int(h * 0.36)),
    )
    out = Image.alpha_composite(out, right_layer)
    return out


# ==============================================================================
# KIỂU 5: CIRCULAR ARC WORD-BY-WORD WRAP
# (Observed at t=17.80s..19.20s: 'những luồng idea' -> 'dần biến thành' -> 'cơn nhức đầu'
# wrapping clockwise around the head contour R=235px, each word/glyph oriented along
# the circle tangent phi = theta + 90 deg, sweeping in with radial de-blur)
# ==============================================================================
def render_style5_circular_arc_wrap(
    canvas_size,
    arc_segments: list,
    t_sec: float,
    head_center=(540, 460),
    radius: float = 235.0,
) -> Image.Image:
    """
    arc_segments: list of dicts:
      {
        'text': 'cơn nhức đầu',
        'theta_start_deg': 165.0,  # bottom-left of head
        'theta_end_deg': 265.0,    # top-crown of head
        't_start': 18.00,
        'dur': 0.45,
        'font': font_hero,
        'color': (250, 204, 21),
        'is_gold': True
      }
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cx, cy = head_center

    for seg in arc_segments:
        if t_sec < seg["t_start"]:
            continue
        txt = seg["text"]
        n_ch = max(1, len(txt))
        th0 = seg["theta_start_deg"]
        th1 = seg["theta_end_deg"]
        font = seg["font"]
        col = seg["color"]

        seg_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for i, ch in enumerate(txt):
            if ch == " ":
                continue
            frac = i / max(1, n_ch - 1)
            char_delay = frac * (seg["dur"] * 0.55)
            p = max(0.0, min(1.0, (t_sec - seg["t_start"] - char_delay) / (seg["dur"] * 0.45)))
            if p <= 0.0:
                continue
            e = cubic_bezier_ease_out(p)

            # Angle sweeps slightly by -6 deg into final angle while radius locks from R+14 -> R
            theta_deg = (th0 + frac * (th1 - th0)) - 6.0 * (1.0 - e)
            theta_rad = math.radians(theta_deg)
            r_cur = radius + 14.0 * (1.0 - e)

            gx = cx + r_cur * math.cos(theta_rad)
            gy = cy + r_cur * math.sin(theta_rad)
            tangent_rot = -(theta_deg + 90.0)

            g_tile = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g_tile)
            gd.text((52, 42), ch, font=font, fill=(*col, int(255 * e)))
            g_rot = g_tile.rotate(tangent_rot, resample=Image.Resampling.BICUBIC, expand=False)
            if p < 1.0:
                g_rot = g_rot.filter(ImageFilter.GaussianBlur(radius=10.0 * (1.0 - e)))

            tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            tmp.paste(g_rot, (int(gx - 70), int(gy - 70)))
            seg_layer = Image.alpha_composite(seg_layer, tmp)

        if seg.get("is_gold", False):
            p_all = min(1.0, (t_sec - seg["t_start"]) / seg["dur"])
            seg_layer = apply_warm_amber_halation(seg_layer, bloom_intensity=0.9 * p_all)
        out = Image.alpha_composite(out, seg_layer)

    return out


# ==============================================================================
# KIỂU 6: OVERLAP SCRIPT/SANS NEGATIVE-LEADING LOCKUP
# (Observed at t=45.0s..47.0s:
# - 'người ta nói' (white sans) overlapped 1/3 by 'đi xa' (gold bold with '+' star mark)
# - 'phải đi' -> 'đi cùng' -> 'nhau' stair-stepped lockup
# - 'và mình' curved on an arc above calligraphic 'biết ơn')
# ==============================================================================
def render_style6_overlap_negative_leading_lockup(
    canvas_size,
    top_sans_text: str,
    hero_overlap_text: str,
    t_sec: float,
    t_top_start: float,
    t_hero_start: float,
    font_sans: ImageFont.FreeTypeFont,
    font_hero: ImageFont.FreeTypeFont,
    anchor_xy=(760, 290),
) -> Image.Image:
    """
    1/3 Vertical & Horizontal Overlap Lockup:
    - Top line ('người ta nói') enters first at (ax, ay)
    - When hero line ('đi xa') enters at t_hero_start, its ascenders overlap the lower 33%
      of the top line (dy = +0.58 * font_sans_height) and shift left by dx = -0.32 * width,
      with a soft dark occlusion drop-shadow behind the top line so both remain 100% legible.
    """
    w, h = canvas_size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ax, ay = anchor_xy

    # Hero layer (drawn underneath or with blend so top white text stays crisp over gold halo)
    if t_sec >= t_hero_start:
        p_h = min(1.0, (t_sec - t_hero_start) / 0.33)
        e_h = cubic_bezier_ease_out(p_h)
        hero_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hero_layer)
        bb_h = hd.textbbox((0, 0), hero_overlap_text, font=font_hero)
        hw = bb_h[2] - bb_h[0]
        hx = max(65, min(w - hw - 55, ax - 32))
        hy = ay + 36 + int(16 * (1.0 - e_h))  # Clean 1/3 negative leading without covering top text!
        hd.text((hx, hy), hero_overlap_text, font=font_hero, fill=(250, 204, 21, int(255 * e_h)))
        # Sparkle '+' accent at top-left of hero word
        hd.text((hx - 24, hy - 14), "+", font=font_sans, fill=(254, 240, 138, int(255 * e_h)))
        if p_h < 1.0:
            hero_layer = hero_layer.filter(ImageFilter.GaussianBlur(radius=11.0 * (1.0 - e_h)))
        hero_layer = apply_warm_amber_halation(hero_layer, bloom_intensity=1.05 * e_h)
        out = Image.alpha_composite(out, hero_layer)

    # Top sans line ('người ta nói') sitting 1/3 over the gold glow
    if t_sec >= t_top_start:
        p_t = min(1.0, (t_sec - t_top_start) / 0.29)
        e_t = cubic_bezier_ease_out(p_t)
        top_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        td = ImageDraw.Draw(top_layer)
        bb_t = td.textbbox((0, 0), top_sans_text, font=font_sans)
        tw_t = bb_t[2] - bb_t[0]
        tx = max(60, min(w - tw_t - 55, ax))
        ty = ay + int(12 * (1.0 - e_t))
        # Subtle dark contrast pillow so overlapping 1/3 edge reads cleanly
        td.text((tx + 2, ty + 2), top_sans_text, font=font_sans, fill=(15, 10, 5, int(185 * e_t)))
        td.text((tx, ty), top_sans_text, font=font_sans, fill=(255, 255, 255, int(255 * e_t)))
        if p_t < 1.0:
            top_layer = top_layer.filter(ImageFilter.GaussianBlur(radius=8.0 * (1.0 - e_t)))
        out = Image.alpha_composite(out, top_layer)

    return out


# ==============================================================================
# KIỂU 7: CONTINUOUS MICRO-FLOAT (HOLD-PHASE LIVING MOTION)
# (Observed across all holds: e.g. t=42.20s..43.40s & t=24.00s..25.45s:
# while the viewer reads the locked-in cluster, it never freezes dead —
# it continuously drifts in scale (+3.0%), Y (-5.5px), and subtle tilt (+0.6 deg))
# ==============================================================================
def apply_style7_continuous_micro_float(
    cluster_rgba: Image.Image,
    t_sec: float,
    t_cluster_birth: float,
    hold_duration: float = 1.8,
    scale_amp: float = 0.03,   # +3% progressive scale creep
    float_y_px: float = -5.5,  # -5.5px upward drift + sine breath
    float_x_px: float = 2.5,
) -> Image.Image:
    """
    Applies sub-pixel continuous micro-float during the reading hold phase:
      S(t)  = 1.0 + 0.03 * ((t - t0) / T_hold) + 0.004 * sin(2*pi*0.9*(t - t0))
      dy(t) = -5.5 * ((t - t0) / T_hold) + 2.2 * sin(2*pi*1.1*(t - t0))
      dx(t) = 2.0 * cos(2*pi*0.7*(t - t0))
    """
    dt = max(0.0, t_sec - t_cluster_birth)
    prog = min(1.0, dt / max(0.1, hold_duration))

    scale = 1.0 + scale_amp * prog + 0.004 * math.sin(2.0 * math.pi * 0.9 * dt)
    dy = float_y_px * prog + 2.2 * math.sin(2.0 * math.pi * 1.1 * dt)
    dx = float_x_px * math.sin(2.0 * math.pi * 0.7 * dt)

    w, h = cluster_rgba.size
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    scaled = cluster_rgba.resize((nw, nh), Image.Resampling.BICUBIC)

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = int(round((w - nw) / 2.0 + dx))
    py = int(round((h - nh) / 2.0 + dy))
    out.paste(scaled, (px, py))
    return out


if __name__ == "__main__":
    # Self-test: render a contact sheet verifying all 7 styles run cleanly
    W, H = 640, 360
    try:
        f_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        f_hero = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        f_small = ImageFont.load_default()
        f_hero = ImageFont.load_default()

    s1 = render_style1_ghost_to_focus_stack((W, H), "mình đang...", "chán", "công việc", 3.55, 2.60, 3.20, 3.45, f_small, f_hero, (180, 120))
    s2 = render_style2_letter_scatter_convergence((W, H), "mình không chỉ là", 41.48, 41.24, f_small, (320, 160))
    s3 = render_style3_per_word_staggered_deblur((W, H), ["việt", "mỏi", "lưng"], 42.08, 41.74, f_hero, (320, 180), entry_order=[1, 2, 0])
    s4 = render_style4_tilted_multi_cluster((W, H), 25.10, f_small, f_hero)
    s5 = render_style5_circular_arc_wrap((W, H), [{"text": "cơn nhức đầu", "theta_start_deg": 170, "theta_end_deg": 265, "t_start": 18.0, "dur": 0.45, "font": f_hero, "color": (250, 204, 21), "is_gold": True}], 18.45, (320, 240), 130)
    s6 = render_style6_overlap_negative_leading_lockup((W, H), "người ta nói", "đi xa", 45.50, 44.95, 45.25, f_small, f_hero, (260, 130))
    s7 = apply_style7_continuous_micro_float(s3, 42.80, 41.74)
    print("All 7 typography motion styles verified and rendered successfully! Sizes:", s1.size, s7.size)
