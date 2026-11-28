#!/usr/bin/env python3
"""vector_shape_plates.py — Canvas-aware animated RGBA vector shape plates (.mov ProRes 4444 / PNG-in-MOV / qtrle).

Harvested & upgraded from `draw_path.py` for `pro-filmcraft-director` v8.
Supports both 9:16 (1080x1920), 16:9 (1920x1080), or any custom canvas (`--width`, `--height`).
Shapes: `arrow`, `circle`, `underline`, `spiral`, `zigzag`, `graph`, `highlight_box`, `line`.

Examples:
    python3 vector_shape_plates.py arrow --out arrow.mov --width 1080 --height 1920 --p0 220,1300 --p1 820,900
    python3 vector_shape_plates.py circle --out circle.mov --cx 540 --cy 780 --rx 260 --ry 120 --color "#38BDF8"
    python3 vector_shape_plates.py underline --out ul.mov --p0 220,920 --p1 860,920 --color "#FACC15"
    python3 vector_shape_plates.py highlight_box --out box.mov --x 180 --y 720 --w 720 --h 150 --color "#F43F5E"
    python3 vector_shape_plates.py spiral --out spiral.mov --cx 540 --cy 960 --r 360
    python3 vector_shape_plates.py zigzag --out zz.mov --p0 180,960 --p1 900,960
    python3 vector_shape_plates.py graph --out graph.mov --points "140,1400 400,1180 680,1040 940,680"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import numpy as np

DEFAULT_W, DEFAULT_H = 1080, 1920
SHIFT = 4                     # cv2 subpixel precision (1/16 px)
HAND_WIDTH_RATIO = 0.016      # default sleek stroke ~1.6% of min(W, H) (~17px on 1080)
HAND_JITTER = 0.10            # subtle organic hand-drawn wobble
DEFAULT_COLOR = "#FFFFFF"
DEFAULT_GLOW = "#38BDF8"
BALL_CORE = 1.7
BALL_AURA = 2.0
BALL_POP_FRAMES = 6
BALL_PULSE = (0.06, 24)


def _hex(h: str) -> np.ndarray:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def _default_stroke(canvas_w: int, canvas_h: int, ratio: float = HAND_WIDTH_RATIO) -> float:
    return max(4.0, round(min(canvas_w, canvas_h) * ratio, 1))


# ---------- Geometry ----------
def resample(pts, step: float = 2.0) -> np.ndarray:
    """Resample polyline uniformly by arc length (~step px) so trim progress maps linearly to arc length."""
    p = np.asarray(pts, dtype=np.float32)
    if len(p) < 2:
        return p
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total < 1e-4:
        return p[:2]
    n = max(2, int(total / step) + 1)
    t = np.linspace(0.0, total, n)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1).astype(np.float32)


def smooth(pts, per_seg: int = 24) -> np.ndarray:
    """Catmull-Rom spline through control points."""
    p = np.asarray(pts, dtype=np.float32)
    if len(p) < 2:
        return p
    q = np.vstack([p[0], p, p[-1]])
    out = []
    for i in range(len(p) - 1):
        p0, p1, p2, p3 = q[i], q[i + 1], q[i + 2], q[i + 3]
        for t in np.linspace(0.0, 1.0, per_seg, endpoint=False):
            out.append(
                0.5 * (
                    2 * p1
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3
                )
            )
    out.append(p[-1])
    return np.asarray(out, dtype=np.float32)


def _wobble(pts: np.ndarray, amp: float, seed: int) -> np.ndarray:
    """Subtle organic jitter interpolated along the path; endpoints remain anchored."""
    if amp <= 0 or len(pts) < 4:
        return pts
    rng = np.random.default_rng(seed)
    k = max(3, len(pts) // 30)
    xs = np.linspace(0, len(pts) - 1, k)
    off = np.stack([np.interp(np.arange(len(pts)), xs, rng.normal(0, amp, k)) for _ in range(2)], 1)
    off[0] = off[-1] = 0.0
    return (pts + off).astype(np.float32)


def _ease(kind: str, u: float) -> float:
    u = float(np.clip(u, 0.0, 1.0))
    if kind == "linear":
        return u
    if kind == "ease_out":
        return 1.0 - (1.0 - u) ** 3
    if kind == "ease_in_out":
        return u * u * (3.0 - 2.0 * u)
    if kind == "ease_out_quart":
        return 1.0 - (1.0 - u) ** 4
    raise ValueError(f"Unknown easing: {kind} (linear | ease_out | ease_in_out | ease_out_quart)")


def rounded_path(points, radius: float, per_corner: int = 14) -> tuple[np.ndarray, list[float]]:
    """Round corners of a polyline with quadratic Beziers. Returns (pts, normalized_arc_marks)."""
    p = np.asarray(points, dtype=np.float64)
    out, mid = [p[0]], [0]
    for i in range(1, len(p) - 1):
        a, b = p[i - 1] - p[i], p[i + 1] - p[i]
        la, lb = np.hypot(*a), np.hypot(*b)
        if la < 1e-6 or lb < 1e-6:
            out.append(p[i])
            mid.append(len(out) - 1)
            continue
        r = min(radius, la / 2.0, lb / 2.0)
        s, e = p[i] + a / la * r, p[i] + b / lb * r
        t = np.linspace(0.0, 1.0, per_corner)[:, None]
        out.extend((1.0 - t) ** 2 * s + 2.0 * (1.0 - t) * t * p[i] + t ** 2 * e)
        mid.append(len(out) - 1 - per_corner // 2)
    out.append(p[-1])
    mid.append(len(out) - 1)
    pts = np.asarray(out, dtype=np.float32)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    denom = max(float(cum[-1]), 1e-6)
    return pts, [float(cum[m] / denom) for m in mid]


def progress_curve(times, arcs, at_times, edge_slope: float = 0.3) -> np.ndarray:
    """Monotone cubic Hermite (Fritsch-Butland) progress curve through (times[i], arcs[i])."""
    t, y = np.asarray(times, np.float64), np.asarray(arcs, np.float64)
    if len(t) < 2 or np.any(np.diff(t) <= 0) or np.any(np.diff(y) < 0):
        raise ValueError("times must be strictly increasing (>=2 pts) and arcs non-decreasing")
    h, d = np.diff(t), np.diff(y) / np.diff(t)
    m = np.empty(len(t))
    m[0], m[-1] = edge_slope * d[0], edge_slope * d[-1]
    for k in range(1, len(t) - 1):
        w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
        m[k] = 0.0 if d[k - 1] * d[k] <= 0 else (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    x = np.clip(np.asarray(at_times, np.float64), t[0], t[-1])
    k = np.clip(np.searchsorted(t, x, side="right") - 1, 0, len(t) - 2)
    u = (x - t[k]) / h[k]
    out = (
        (2 * u ** 3 - 3 * u ** 2 + 1) * y[k]
        + (u ** 3 - 2 * u ** 2 + u) * h[k] * m[k]
        + (-2 * u ** 3 + 3 * u ** 2) * y[k + 1]
        + (u ** 3 - u ** 2) * h[k] * m[k + 1]
    )
    return np.clip(out, y[0], y[-1])


def path_points(points, progress) -> np.ndarray:
    """Path tip coordinates (N x 2) for each progress value."""
    pts = resample(points)
    idx = np.clip(np.round(np.asarray(progress, np.float64) * (len(pts) - 1)).astype(int), 0, len(pts) - 1)
    return pts[idx]


# ---------- Rasterization ----------
def _polyline(mask: np.ndarray, pts: np.ndarray, width: float) -> None:
    import cv2
    q = np.round(pts * (1 << SHIFT)).astype(np.int32)
    t = max(1, round(width) - 1)
    cv2.polylines(mask, [q], False, 255, thickness=t, lineType=cv2.LINE_AA, shift=SHIFT)
    for x, y in (q[0], q[-1]):
        cv2.circle(mask, (int(x), int(y)), round((t + 1) / 2 * (1 << SHIFT)), 255, -1, cv2.LINE_AA, SHIFT)


def _arrow_head(mask: np.ndarray, pts: np.ndarray, width: float, scale: float = 1.0) -> None:
    if scale <= 0.01:
        return
    tip = pts[-1]
    back = pts[max(0, len(pts) - 1 - 12)]
    ang = np.arctan2(tip[1] - back[1], tip[0] - back[0])
    ln = width * 3.2 * scale
    for da in (np.radians(148), np.radians(-148)):
        end = tip + ln * np.array([np.cos(ang + da), np.sin(ang + da)])
        _polyline(mask, np.array([tip, end], dtype=np.float32), width)


def _over(prem: np.ndarray, alpha: np.ndarray, mask: np.ndarray, color: np.ndarray, opacity: float = 1.0) -> None:
    a = (mask.astype(np.float32) / 255.0) * opacity
    a3 = a[..., None]
    prem *= (1.0 - a3)
    prem += color * a3
    alpha *= (1.0 - a)
    alpha += a


def _compose(
    stroke: np.ndarray,
    dot: np.ndarray | None,
    color: np.ndarray,
    glow: np.ndarray | None,
    width: float,
    dot_color: np.ndarray,
    canvas_w: int,
    canvas_h: int,
    aura: np.ndarray | None = None,
    fill_mask: np.ndarray | None = None,
    fill_color: np.ndarray | None = None,
    fill_opacity: float = 0.22,
    glow_strength: float = 1.25,
) -> np.ndarray:
    import cv2
    prem = np.zeros((canvas_h, canvas_w, 3), np.float32)
    alpha = np.zeros((canvas_h, canvas_w), np.float32)

    if fill_mask is not None and fill_color is not None and fill_opacity > 0:
        _over(prem, alpha, fill_mask, fill_color, opacity=fill_opacity)

    if aura is not None:
        _over(prem, alpha, cv2.GaussianBlur(aura, (0, 0), max(2.0, width * 0.95)), glow if glow is not None else color)

    if glow is not None:
        both = stroke if dot is None else np.maximum(stroke, dot)
        # Two-stage optical halation (tight inner bloom + wide subtle outer bloom)
        inner = cv2.GaussianBlur(both, (0, 0), max(2.0, width * 0.55))
        outer = cv2.GaussianBlur(both, (0, 0), max(4.0, width * 1.45))
        halo = np.clip(inner.astype(np.float32) * (0.95 * glow_strength) + outer.astype(np.float32) * (0.45 * glow_strength), 0, 255).astype(np.uint8)
        _over(prem, alpha, halo, glow)

    _over(prem, alpha, stroke, color)
    if dot is not None:
        _over(prem, alpha, dot, dot_color)

    out = np.zeros((canvas_h, canvas_w, 4), np.uint8)
    nz = alpha > 1e-4
    out[..., :3][nz] = np.clip(prem[nz] / alpha[nz][:, None], 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(np.round(alpha * 255.0), 0, 255).astype(np.uint8)
    return out


def _head_masks(tip: np.ndarray, head: str, f: int, width: float, canvas_w: int, canvas_h: int) -> tuple:
    k = 1.0
    if head == "ball":
        k = min(1.0, (f + 1) / BALL_POP_FRAMES) * (1.0 + BALL_PULSE[0] * np.sin(2.0 * np.pi * f / BALL_PULSE[1]))
    dot = np.zeros((canvas_h, canvas_w), np.uint8)
    _polyline(dot, np.stack([tip, tip]), width * (BALL_CORE if head == "ball" else 1.7) * k)
    aura = None
    if head == "ball":
        import cv2
        aura = np.zeros((canvas_h, canvas_w), np.uint8)
        cv2.circle(
            aura,
            (int(round(tip[0] * (1 << SHIFT))), int(round(tip[1] * (1 << SHIFT)))),
            int(width * BALL_AURA * k * (1 << SHIFT)),
            255,
            -1,
            cv2.LINE_AA,
            SHIFT,
        )
    return dot, aura


def _rounded_rect_fill_mask(
    canvas_w: int,
    canvas_h: int,
    box: tuple[float, float, float, float, float],
    sweep_p: float,
) -> np.ndarray:
    """Render a rounded rectangle interior mask swept horizontally by sweep_p (0..1)."""
    import cv2
    x, y, w, h, r = box
    mask = np.zeros((canvas_h, canvas_w), np.uint8)
    if sweep_p <= 0.01 or w <= 2 or h <= 2:
        return mask
    # Build smooth rounded rect polygon
    r = min(r, w / 2.0, h / 2.0)
    pts = []
    corners = [
        (x + w - r, y + r, -np.pi / 2, 0.0),
        (x + w - r, y + h - r, 0.0, np.pi / 2),
        (x + r, y + h - r, np.pi / 2, np.pi),
        (x + r, y + r, np.pi, 1.5 * np.pi),
    ]
    for cx, cy, a0, a1 in corners:
        ang = np.linspace(a0, a1, 12)
        for a in ang:
            pts.append([cx + r * np.cos(a), cy + r * np.sin(a)])
    poly = np.round(np.array(pts, dtype=np.float32) * (1 << SHIFT)).astype(np.int32)
    cv2.fillPoly(mask, [poly], 255, lineType=cv2.LINE_AA, shift=SHIFT)
    clip_x = int(round(x + w * np.clip(sweep_p, 0.0, 1.0)))
    if clip_x < canvas_w:
        mask[:, clip_x:] = 0
    return mask


def render_frames(
    points,
    frames: int,
    width: float,
    color: str = DEFAULT_COLOR,
    glow: str | None = DEFAULT_GLOW,
    head: str = "none",
    easing: str = "ease_out",
    jitter: float = 0.0,
    seed: int = 0,
    dot_color: str = "#FFFFFF",
    progress=None,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
    fill_box: tuple[float, float, float, float, float] | None = None,
    fill_opacity: float = 0.22,
    glow_strength: float = 1.25,
) -> Iterator[np.ndarray]:
    """Yield RGBA frames (canvas_h x canvas_w x 4 uint8, straight alpha)."""
    if frames < 2:
        raise ValueError("frames must be >= 2")
    if head not in ("none", "arrow", "dot", "ball"):
        raise ValueError(f"Unknown head: {head}")
    if progress is not None and len(progress) != frames:
        raise ValueError("progress length must equal frames")

    pts = _wobble(resample(points), jitter * width, seed)
    col = _hex(color)
    gcol = _hex(glow) if glow else None
    dcol = _hex(dot_color)

    last_frame = None
    for f in range(frames):
        p = float(progress[f]) if progress is not None else _ease(easing, f / (frames - 1))
        n = round(p * (len(pts) - 1))
        if (f == 0 or n < 1) and head != "ball" and fill_box is None:
            last_frame = np.zeros((canvas_h, canvas_w, 4), np.uint8)
            yield last_frame
            continue

        part = pts[: max(n, 0) + 1]
        stroke = np.zeros((canvas_h, canvas_w), np.uint8)
        dot, aura = None, None
        if n >= 1:
            _polyline(stroke, part, width)
        if head == "arrow":
            # Smoothly pop arrowhead during final 22% of draw
            if p >= 0.78:
                head_scale = _ease("ease_out", (p - 0.78) / 0.22)
                _arrow_head(stroke, part, width, scale=head_scale)
        if head in ("dot", "ball"):
            dot, aura = _head_masks(part[-1], head, f, width, canvas_w, canvas_h)

        fmask = None
        if fill_box is not None:
            fmask = _rounded_rect_fill_mask(canvas_w, canvas_h, fill_box, sweep_p=p)

        last_frame = _compose(
            stroke,
            dot,
            col,
            gcol,
            width,
            dcol,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            aura=aura,
            fill_mask=fmask,
            fill_color=col,
            fill_opacity=fill_opacity,
            glow_strength=glow_strength,
        )
        yield last_frame

    if hold_frames > 0 and last_frame is not None:
        for _ in range(hold_frames):
            yield last_frame


def _ffmpeg_codec_args(codec: str) -> list[str]:
    if codec == "prores4444":
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    if codec == "png":
        return ["-c:v", "png", "-pix_fmt", "rgba"]
    if codec == "qtrle":
        return ["-c:v", "qtrle", "-pix_fmt", "argb"]
    raise ValueError(f"Unsupported codec: {codec} (prores4444 | png | qtrle)")


def write(spec: dict, out: str | Path, fps: int = 60, codec: str = "prores4444") -> Path:
    """Encode animated RGBA vector shape to .mov with alpha channel."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w = int(spec.get("canvas_w", DEFAULT_W))
    h = int(spec.get("canvas_h", DEFAULT_H))
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
        "-framerate", str(fps), "-i", "-",
        *_ffmpeg_codec_args(codec),
        str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for fr in render_frames(**spec):
            proc.stdin.write(fr.tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {out}")
    return out


def still(spec: dict, out_png: str | Path) -> Path:
    """Save the final completed frame as a straight-alpha RGBA PNG."""
    from PIL import Image
    last = None
    for last in render_frames(**spec):
        pass
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    assert last is not None
    Image.fromarray(last, "RGBA").save(out, format="PNG", pnginfo=None)
    return out


def write_with_still(spec: dict, out_mov: str | Path, out_png: str | Path, fps: int = 60, codec: str = "prores4444") -> Path:
    """Write .mov and capture final frame PNG in a single render pass."""
    from PIL import Image
    out_mov = Path(out_mov)
    out_mov.parent.mkdir(parents=True, exist_ok=True)
    w = int(spec.get("canvas_w", DEFAULT_W))
    h = int(spec.get("canvas_h", DEFAULT_H))
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
        "-framerate", str(fps), "-i", "-",
        *_ffmpeg_codec_args(codec),
        str(out_mov),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    last = None
    try:
        for last in render_frames(**spec):
            proc.stdin.write(last.tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {out_mov}")
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    assert last is not None
    Image.fromarray(last, "RGBA").save(out_png, format="PNG", pnginfo=None)
    return out_mov


# ---------- Shape Presets ----------
def arrow_curve(
    p0=(220, 1420),
    p1=(820, 960),
    bend: float = 0.30,
    frames: int = 24,
    width: float | None = None,
    color: str = DEFAULT_COLOR,
    glow: str | None = DEFAULT_GLOW,
    seed: int = 2,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Curved quadratic Bezier arrow with cubic ease-out trim-path and optical glow."""
    a, b = np.array(p0, np.float32), np.array(p1, np.float32)
    d = b - a
    ctrl = (a + b) / 2.0 + bend * np.array([-d[1], d[0]], dtype=np.float32)
    t = np.linspace(0.0, 1.0, 240)[:, None]
    pts = (1.0 - t) ** 2 * a + 2.0 * (1.0 - t) * t * ctrl + t ** 2 * b
    return dict(
        points=pts,
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h),
        color=color,
        glow=glow,
        head="arrow",
        easing="ease_out",
        jitter=HAND_JITTER,
        seed=seed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def circle(
    cx: float = 540,
    cy: float = 820,
    rx: float = 260,
    ry: float = 120,
    overshoot_deg: float = 24.0,
    frames: int = 28,
    width: float | None = None,
    color: str = "#38BDF8",
    glow: str | None = "#38BDF8",
    seed: int = 4,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Organic hand-drawn highlight oval/circle with slight natural overshoot loop."""
    total_rad = np.radians(360.0 + overshoot_deg)
    th = np.linspace(-np.pi * 0.65, -np.pi * 0.65 + total_rad, 360)
    # Subtle radial taper at start/end so the loop looks natural
    spiral_factor = 1.0 + 0.04 * (th - th[0]) / max(total_rad, 1e-4)
    pts = np.stack([cx + rx * spiral_factor * np.cos(th), cy + ry * spiral_factor * np.sin(th)], 1).astype(np.float32)
    return dict(
        points=pts,
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.013),
        color=color,
        glow=glow,
        head="none",
        easing="ease_out",
        jitter=HAND_JITTER * 0.85,
        seed=seed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def underline(
    p0=(200, 980),
    p1=(880, 980),
    arch: float = -0.05,
    frames: int = 22,
    width: float | None = None,
    color: str = "#FACC15",
    glow: str | None = "#FACC15",
    seed: int = 5,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Sleek slightly-arched swoosh underline with cubic ease-out trim-path."""
    a, b = np.array(p0, np.float32), np.array(p1, np.float32)
    d = b - a
    ctrl = (a + b) / 2.0 + arch * np.array([-d[1], d[0]], dtype=np.float32)
    t = np.linspace(0.0, 1.0, 200)[:, None]
    pts = (1.0 - t) ** 2 * a + 2.0 * (1.0 - t) * t * ctrl + t ** 2 * b
    return dict(
        points=pts,
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.014),
        color=color,
        glow=glow,
        head="none",
        easing="ease_out",
        jitter=HAND_JITTER * 0.7,
        seed=seed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def spiral(
    cx: float = 540,
    cy: float = 960,
    r_max: float = 360,
    turns: float = 4.2,
    frames: int = 36,
    width: float | None = None,
    color: str = "#38BDF8",
    glow: str | None = "#38BDF8",
    seed: int = 1,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Archimedes spiral drawn outward from center with cubic ease-out and optical glow."""
    th = np.linspace(0.0, turns * 2.0 * np.pi, 1200)
    r = r_max * th / max(float(th[-1]), 1e-4)
    pts = np.stack([cx + r * np.cos(th), cy + r * np.sin(th)], 1).astype(np.float32)
    return dict(
        points=pts,
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.018),
        color=color,
        glow=glow,
        head="none",
        easing="ease_out",
        jitter=HAND_JITTER,
        seed=seed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def zigzag(
    p0=(160, 960),
    p1=(920, 960),
    n: int = 6,
    amp: float = 44.0,
    frames: int = 24,
    width: float | None = None,
    color: str = "#F43F5E",
    glow: str | None = "#F43F5E",
    seed: int = 3,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Multi-beat zigzag scribble underline/connector."""
    a, b = np.array(p0, np.float32), np.array(p1, np.float32)
    d = (b - a) / max(1e-6, float(np.hypot(*(b - a))))
    nrm = np.array([-d[1], d[0]], dtype=np.float32)
    pts = [a] + [a + (b - a) * (i + 0.5) / n + nrm * amp * (1.0 if i % 2 == 0 else -1.0) for i in range(n)] + [b]
    return dict(
        points=np.array(pts, dtype=np.float32),
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.015),
        color=color,
        glow=glow,
        head="none",
        easing="ease_out",
        jitter=HAND_JITTER * 0.6,
        seed=seed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def graph_curve(
    points,
    frames: int = 36,
    width: float | None = None,
    color: str = "#FFFFFF",
    glow: str | None = "#38BDF8",
    head: str = "ball",
    easing: str = "ease_out",
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Smooth Catmull-Rom graph line with glowing leading orb."""
    return dict(
        points=smooth(points),
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.014),
        color=color,
        glow=glow,
        head=head,
        easing=easing,
        jitter=0.0,
        seed=0,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def highlight_box(
    x: float = 180,
    y: float = 760,
    w: float = 720,
    h: float = 150,
    radius: float = 24.0,
    frames: int = 24,
    width: float | None = None,
    color: str = "#38BDF8",
    glow: str | None = "#38BDF8",
    fill_opacity: float = 0.22,
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Rounded highlight box with synchronized perimeter trim-path + translucent glowing fill sweep."""
    corners = np.array([
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h],
        [x, y],
    ], dtype=np.float32)
    pts, _ = rounded_path(corners, radius=radius, per_corner=12)
    return dict(
        points=pts,
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.008),
        color=color,
        glow=glow,
        head="none",
        easing="ease_out",
        jitter=0.0,
        seed=0,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
        fill_box=(float(x), float(y), float(w), float(h), float(radius)),
        fill_opacity=float(fill_opacity),
    )


def line(
    points,
    frames: int = 20,
    width: float | None = None,
    color: str = DEFAULT_COLOR,
    glow: str | None = DEFAULT_GLOW,
    easing: str = "ease_out",
    canvas_w: int = DEFAULT_W,
    canvas_h: int = DEFAULT_H,
    hold_frames: int = 0,
) -> dict:
    """Clean polyline with cubic ease-out trim-path."""
    return dict(
        points=np.asarray(points, np.float32),
        frames=frames,
        width=width or _default_stroke(canvas_w, canvas_h, 0.012),
        color=color,
        glow=glow,
        head="none",
        easing=easing,
        jitter=0.0,
        seed=0,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        hold_frames=hold_frames,
    )


def shift(spec: dict, dx: float, dy: float) -> dict:
    """Return a copy of spec shifted by (-dx, -dy)."""
    return {**spec, "points": np.asarray(spec["points"], np.float32) - np.array([dx, dy], np.float32)}


def hits_canvas(spec: dict, margin: float = 80) -> bool:
    """Check if any point falls within the spec's canvas bounds (+ margin)."""
    w = int(spec.get("canvas_w", DEFAULT_W))
    h = int(spec.get("canvas_h", DEFAULT_H))
    p = np.asarray(spec["points"])
    return bool(((p[:, 0] > -margin) & (p[:, 0] < w + margin) & (p[:, 1] > -margin) & (p[:, 1] < h + margin)).any())


# ---------- CLI ----------
def _xy(s: str) -> tuple[float, float]:
    x, y = s.split(",")
    return float(x), float(y)


def _build(a: argparse.Namespace) -> dict:
    common = dict(
        frames=a.frames,
        width=a.stroke_width,
        color=a.color,
        glow=None if (a.glow or "").lower() == "none" else a.glow,
        canvas_w=a.width,
        canvas_h=a.height,
        hold_frames=a.hold_frames,
    )
    if a.cmd == "arrow":
        return arrow_curve(a.p0, a.p1, bend=a.bend, **common)
    if a.cmd == "circle":
        return circle(a.cx, a.cy, a.rx, a.ry, **common)
    if a.cmd == "underline":
        return underline(a.p0, a.p1, arch=a.arch, **common)
    if a.cmd == "spiral":
        return spiral(a.cx, a.cy, a.r, turns=a.turns, **common)
    if a.cmd == "zigzag":
        return zigzag(a.p0, a.p1, n=a.beats, amp=a.amp, **common)
    if a.cmd == "highlight_box":
        return highlight_box(a.x, a.y, a.box_w, a.box_h, radius=a.radius, fill_opacity=a.fill_opacity, **common)
    pts = [_xy(s) for s in a.points.split()]
    if a.cmd == "graph":
        return graph_curve(pts, head=a.head, **common)
    return line(pts, **common)


def main() -> int:
    ap = argparse.ArgumentParser(description="Canvas-aware animated RGBA vector shape plates (.mov)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    shapes = ("arrow", "circle", "underline", "spiral", "zigzag", "graph", "highlight_box", "line")
    for name in shapes:
        s = sub.add_parser(name)
        s.add_argument("--out", required=True, help="Output .mov path")
        s.add_argument("--width", type=int, default=DEFAULT_W, help="Canvas width (default 1080)")
        s.add_argument("--height", type=int, default=DEFAULT_H, help="Canvas height (default 1920)")
        s.add_argument("--fps", type=int, default=60, help="Frame rate (default 60)")
        s.add_argument("--frames", type=int, default=28, help="Draw-in frames (default 28)")
        s.add_argument("--hold-frames", type=int, default=0, help="Hold frames after draw completes")
        s.add_argument("--stroke-width", type=float, default=None, help="Stroke width in px (auto-scaled if omitted)")
        s.add_argument("--color", default="#FFFFFF", help="Stroke hex color (default #FFFFFF)")
        s.add_argument("--glow", default="#38BDF8", help="Optical glow hex color or 'none'")
        s.add_argument("--codec", choices=("prores4444", "png", "qtrle"), default="prores4444")
        s.add_argument("--still", default=None, help="Optional final-frame PNG path")

        if name == "arrow":
            s.add_argument("--p0", type=_xy, default=(220, 1420))
            s.add_argument("--p1", type=_xy, default=(820, 960))
            s.add_argument("--bend", type=float, default=0.30)
        elif name == "circle":
            s.add_argument("--cx", type=float, default=540)
            s.add_argument("--cy", type=float, default=820)
            s.add_argument("--rx", type=float, default=260)
            s.add_argument("--ry", type=float, default=120)
        elif name == "underline":
            s.add_argument("--p0", type=_xy, default=(200, 980))
            s.add_argument("--p1", type=_xy, default=(880, 980))
            s.add_argument("--arch", type=float, default=-0.05)
        elif name == "spiral":
            s.add_argument("--cx", type=float, default=540)
            s.add_argument("--cy", type=float, default=960)
            s.add_argument("--r", type=float, default=360)
            s.add_argument("--turns", type=float, default=4.2)
        elif name == "zigzag":
            s.add_argument("--p0", type=_xy, default=(160, 960))
            s.add_argument("--p1", type=_xy, default=(920, 960))
            s.add_argument("--beats", type=int, default=6)
            s.add_argument("--amp", type=float, default=44.0)
        elif name == "highlight_box":
            s.add_argument("--x", type=float, default=180)
            s.add_argument("--y", type=float, default=760)
            s.add_argument("--box-w", type=float, default=720)
            s.add_argument("--box-h", type=float, default=150)
            s.add_argument("--radius", type=float, default=24.0)
            s.add_argument("--fill-opacity", type=float, default=0.22)
        elif name in ("graph", "line"):
            s.add_argument("--points", required=True, help='"x,y x,y ..."')
            if name == "graph":
                s.add_argument("--head", choices=("none", "dot", "ball"), default="ball")

    a = ap.parse_args()
    spec = _build(a)
    if a.still:
        out_mov = write_with_still(spec, a.out, a.still, fps=a.fps, codec=a.codec)
        print(f"[VECTOR OK] {out_mov} + {a.still} ({spec['frames'] + spec['hold_frames']} frames @ {a.fps}fps, {a.width}x{a.height})")
    else:
        out_mov = write(spec, a.out, fps=a.fps, codec=a.codec)
        print(f"[VECTOR OK] {out_mov} ({spec['frames'] + spec['hold_frames']} frames @ {a.fps}fps, {a.width}x{a.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
