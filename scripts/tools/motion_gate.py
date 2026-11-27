#!/usr/bin/env python3
"""
motion_gate.py (v7.9.0) — pixel-level hook gates on a rendered preview. Pure numpy / cv2, importable and CLI.

Why: the v3 hook sat static for 2.2-3.4 s (frame diff < 1.0), had a soft pop-out edge and text over the product. These gates measure
the RENDERED pixels instead of trusting the plan.

  bg_diff_series(video, ...)      -> [(t_s, mean_abs_gray_diff)] at `fps`, 270x480 gray, mask rects ignored, flash/cut frames dropped
  static_runs(series, thr, min_len_s) -> [(t_start, t_end)] runs below `thr` (flash frames never break a run)
  check_motion(video, mask_rects, t0, t1) -> {ok, mean, max_static_run_s, share_below_1, errors}
        errors: a run with diff < 1.0 longer than 0.6 s [UOC] in the window; masked mean < 2.0 [UOC from the @__dviet B-roll-first hooks, 1.9-2.4]
  popout_edge_width_px(frame, row_y, x_range)  10-90 % rise of a card edge at 1080 px width (gate <= 6 px)
  face_laplacian_ratio(frame_v, source_frame, roi)  Laplacian variance of the ROI vs the plain-Lanczos source (gate >= 1.8)
  hero_product_overlap_px(frame, text_bbox, product_mask)  hero text pixels over the product silhouette (gate == 0)
  text_glyph_height_frac(bbox, H=1920)  glyph box height as a fraction of the frame (floor 3.3 %)

v7.9.0 (v4 review K1-K4, A1, V-FLASH):
  popout_inner_edge_dark_strip_px(frame, card_rect)  dark band along the card's inner left / right edge (gate <= 4 px; v4 24-30 px)
  card_dark_speck_count(frame, card_rect, exclude_mask)  small dark blobs on the card wall (gate == 0; v4 a 17x14 px dot)
  crown_edge_metrics(alpha_crop)  pop-out crown top edge: jaggedness (gate <= 1.2 px) and 10-90 % rise (gate <= 4 px)
  luma_series / check_flashes(video)  photosensitivity on the render: flash peak mean luma <= 220, <= 3 flashes in any 1 s
  flash_peak_luma / check_flash_plan(events)  the same limits on plan events (used by studio_recipe.check_hook)
  word_gap_series / check_word_gaps(lines)  adjacent-word gap >= 0.25 em on every visible frame of a blur-in / scale-in
  entrance_word_spacing_em(blur_px, scale, font_px, natural_gap_em)  the extra word spacing that keeps that gap on one frame: the ONE
        helper behind the web-plate word-spacing guard (web_plate_builder) and the FilmCraft tracking keys (typography_composer)
  natural_word_gap_em(text, font_path, letter_spacing_em)  narrowest resting ink gap between adjacent words (PIL), in em

`video` is a file path or an in-memory sequence of BGR frames sampled at `fps` (used by the synthetic tests).
`mask_rects` are NORMALISED (x0, y0, x1, y1) rectangles in 0..1 (PiP, text boxes) that are excluded from the diff.
CLI: python3 motion_gate.py VIDEO [--mask x0,y0,x1,y1 ...] [--t0 0] [--t1 3.4]  -> JSON on stdout, exit 1 when not ok.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Sequence

import cv2
import numpy as np

VERSION = "7.9.0"
FLASH_DIFF = 18.0          # [UOC] mean gray diff (0..255) above which a frame pair is a cut / white flash, not camera motion
STATIC_DIFF = 1.0          # [UOC] frame diff below this is "static" (the v3 window measured 1.20 mean, many frames < 1.0)
STATIC_MAX_S = 0.6         # [UOC] longest tolerated static run
MIN_MEAN_DIFF = 2.0        # [UOC] masked mean; @__dviet B-roll-first hooks measure 1.9-2.4
EDGE_GATE_PX = 6.0         # [DO] pop-out edge 10-90 % rise <= 6 px at 1080 wide (reference 3-5 px, v3 19-21 px)
LAPLACIAN_RATIO_GATE = 1.8  # [DO] face ROI Laplacian vs plain Lanczos (real S09: 2.2x)
INNER_STRIP_GATE_PX = 4.0  # [UOC] dark band along the card's inner edge (v4 17.0 s: 24-30 px at luma 13-21 vs 43-50 [DO])
INNER_STRIP_DARK = 0.75    # [UOC] a column is dark when < 75 % of the row's card-interior median in > half of the rows
SPECK_DARK = 28.0          # [UOC] a wall pixel this many levels under its local median is a speck candidate
SPECK_AREA = (12, 2500)    # [UOC] speck blob area in px at 1080 wide (v4 dot 17x14 px)
CROWN_JAG_GATE_PX = 1.2    # [UOC] std of the crown top edge around its own smooth curve
CROWN_RISE_GATE_PX = 4.0   # [UOC] 10-90 % alpha rise across the crown edge (v4 10-14 px [DO])
FLASH_LUMA_CAP = 220.0     # [UOC] photosensitivity: a flash may not lift the frame mean luma (0..255) above this (v4 248-250 [DO])
FLASH_SWING = 20.0         # [UOC] mean-luma change counted as one transition (~ WCAG 2.3.1 10 % relative luminance)
FLASH_PULSE_S = 0.5        # [UOC] a rise that falls back by FLASH_SWING within this is a flash (a held bright scene is not)
MAX_FLASHES_PER_S = 3      # WCAG 2.3.1: no more than three general flashes in any one second (a flash = a pair of opposing transitions)
FLASH_PLAN_BASE_LUMA = 80.0  # [UOC] frame mean luma assumed under a planned flash (v4 hook troughs 52-78 [DO])
WORD_GAP_MIN_EM = 0.25     # [UOC] adjacent-word gap floor on every visible entrance frame (nfc_guardrails word_spacing_em)
SPACE_EM = 0.23            # [DO] Be Vietnam Pro U+0020 advance, every weight (hmtx 0.23 em): the natural spacing a blur-in eases back to


def _gray_small(frame: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if (g.shape[1], g.shape[0]) != tuple(size):
        g = cv2.resize(g, size, interpolation=cv2.INTER_AREA)
    return g.astype(np.float32)


def _keep_mask(size: tuple[int, int], mask_rects: Sequence[Sequence[float]]) -> np.ndarray:
    w, h = size
    keep = np.ones((h, w), bool)
    for x0, y0, x1, y1 in mask_rects:
        keep[int(round(y0 * h)):int(round(y1 * h)), int(round(x0 * w)):int(round(x1 * w))] = False
    return keep


def _iter_frames(video: Any, fps: float, t0: float, t1: float | None):
    """Yield (t_s, BGR frame) at `fps` for path or sequence input."""
    if isinstance(video, (str, bytes)) or hasattr(video, "__fspath__"):
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise FileNotFoundError(f"cannot open video: {video}")
        src_fps = cap.get(cv2.CAP_PROP_FPS) or fps
        step = max(1, int(round(src_fps / fps)))
        i0 = int(round(t0 * src_fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i0)
        i = i0
        try:
            while True:
                if t1 is not None and i / src_fps > t1 + 1e-9:
                    break
                ok, f = cap.read()
                if not ok:
                    break
                if (i - i0) % step == 0:
                    yield i / src_fps, f
                i += 1
        finally:
            cap.release()
        return
    for i, f in enumerate(video):
        t = i / fps
        if t < t0 - 1e-9:
            continue
        if t1 is not None and t > t1 + 1e-9:
            break
        yield t, f


def bg_diff_series(
    video: Any,
    fps: float = 30,
    size: tuple[int, int] = (270, 480),
    mask_rects: Sequence[Sequence[float]] = (),
    t0: float = 0.0,
    t1: float | None = None,
    exclude_cut_frames: bool = True,
) -> list[tuple[float, float]]:
    """[(t_s, mean abs gray diff to the previous sampled frame)] over the unmasked pixels of a `size` gray proxy.
    `exclude_cut_frames` drops pairs whose diff >= FLASH_DIFF (hard cuts, white flashes and their exit frame): they are events, not camera motion."""
    keep = _keep_mask(size, mask_rects)
    if not keep.any():
        raise ValueError("mask_rects cover the whole frame")
    out: list[tuple[float, float]] = []
    prev = None
    for t, f in _iter_frames(video, float(fps), float(t0), t1):
        g = _gray_small(f, size)
        if prev is not None:
            d = float(np.abs(g - prev)[keep].mean())
            if not (exclude_cut_frames and d >= FLASH_DIFF):
                out.append((round(float(t), 4), d))
        prev = g
    return out


def static_runs(series: Sequence[tuple[float, float]], thr: float = STATIC_DIFF, min_len_s: float = STATIC_MAX_S,
                fps: float = 30.0) -> list[tuple[float, float]]:
    """Runs of consecutive samples with diff < thr whose length (last - first + one frame) exceeds `min_len_s`.
    Excluded flash frames are simply absent from the series, so they do not break a static run."""
    runs: list[tuple[float, float]] = []
    start = last = None
    for t, d in series:
        if d < thr:
            if start is None:
                start = t
            last = t
        elif start is not None:
            if last - start + 1.0 / fps > min_len_s:
                runs.append((start, last + 1.0 / fps))
            start = last = None
    if start is not None and last - start + 1.0 / fps > min_len_s:
        runs.append((start, last + 1.0 / fps))
    return runs


def check_motion(video: Any, mask_rects: Sequence[Sequence[float]] = (), t0: float = 0.0, t1: float = 3.4, *,
                 fps: float = 30, size: tuple[int, int] = (270, 480)) -> dict[str, Any]:
    """Hook motion gate over [t0, t1]: ok = no static run > 0.6 s AND masked mean frame diff >= 2.0 (flashes excluded)."""
    series = bg_diff_series(video, fps=fps, size=size, mask_rects=mask_rects, t0=t0, t1=t1)
    if not series:
        return {"ok": False, "mean": 0.0, "max_static_run_s": 0.0, "share_below_1": 1.0, "samples": 0,
                "errors": ["no frames in the window"]}
    d = np.array([x[1] for x in series], np.float64)
    runs = static_runs(series, STATIC_DIFF, 0.0, fps=fps)           # every run, then the longest
    longest = max((b - a for a, b in runs), default=0.0)
    errors: list[str] = []
    if longest > STATIC_MAX_S:
        errors.append(f"static run {longest:.2f}s > {STATIC_MAX_S}s with frame diff < {STATIC_DIFF}")
    if float(d.mean()) < MIN_MEAN_DIFF:
        errors.append(f"masked mean frame diff {d.mean():.2f} < {MIN_MEAN_DIFF}")
    return {"ok": not errors, "mean": round(float(d.mean()), 3), "max_static_run_s": round(float(longest), 3),
            "share_below_1": round(float((d < STATIC_DIFF).mean()), 3), "samples": int(d.size), "errors": errors,
            "window": [float(t0), float(t1)]}


# ------------------------------------------------------------------------------------------------ single-frame metrics
def _rise_width(profile: np.ndarray) -> float:
    """10-90 % rise width (px, sub-pixel) of a 1-D step profile; levels = medians of the 3 end samples on each side."""
    p = np.asarray(profile, np.float64)
    lo, hi = float(np.median(p[:3])), float(np.median(p[-3:]))
    if abs(hi - lo) < 1e-6:
        return float("nan")
    u = (p - lo) / (hi - lo)
    def cross(level: float) -> float:
        idx = np.where((u[:-1] - level) * (u[1:] - level) <= 0)[0]
        if idx.size == 0:
            return float("nan")
        i = int(idx[len(idx) // 2])
        den = u[i + 1] - u[i]
        return i + (0.0 if abs(den) < 1e-12 else (level - u[i]) / den)
    return abs(cross(0.9) - cross(0.1))


def popout_edge_width_px(frame: np.ndarray, row_y: int, x_range: tuple[int, int]) -> float:
    """10-90 % rise width of a vertical card edge along row `row_y` over x in `x_range`, normalised to 1080 px frame width.
    Gate: <= EDGE_GATE_PX (6 px). [DO] reference still 3-5 px, v3 19-21 px."""
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    x0, x1 = int(x_range[0]), int(x_range[1])
    return float(_rise_width(g[int(row_y), x0:x1]) * (1080.0 / g.shape[1]))


def popout_edge_width_v_px(frame: np.ndarray, col_x: int, y_range: tuple[int, int]) -> float:
    """Same as `popout_edge_width_px` for a horizontal card edge (e.g. the card top) along column `col_x`."""
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    y0, y1 = int(y_range[0]), int(y_range[1])
    return float(_rise_width(g[y0:y1, int(col_x)]) * (1080.0 / g.shape[1]))


def _lap_var(frame: np.ndarray, roi: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = roi
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g[y0:y1, x0:x1], cv2.CV_64F).var())


def face_laplacian_ratio(frame_v: np.ndarray, source_frame: np.ndarray, roi: tuple[int, int, int, int]) -> float:
    """Laplacian variance of `roi` (x0, y0, x1, y1) in the rendered frame over the SAME crop of the plain-Lanczos source.
    Gate: >= LAPLACIAN_RATIO_GATE (1.8). Replaces the whole-frame Laplacian bar of 430, which text and graphics dominate."""
    return _lap_var(frame_v, roi) / max(_lap_var(source_frame, roi), 1e-9)


def hero_product_overlap_px(frame: np.ndarray | None, text_bbox: tuple[int, int, int, int], product_mask: np.ndarray | None) -> int:
    """Pixels of the hero text box (x0, y0, x1, y1; x1/y1 inclusive or exclusive does not matter for the gate) that lie on the product.
    `product_mask`: bool / uint8 H x W (non-zero = product). When None it is estimated from `frame` (luminance deviation from the
    side columns, the `bbox_product` recipe of the stage proof). Gate: == 0."""
    if product_mask is None:
        if frame is None:
            raise ValueError("need a product_mask or a frame")
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        side = np.concatenate([g[:, :90], g[:, -90:]], 1)
        m = np.abs(g - np.median(side, 1)[:, None]) > 22
        m[:, :150] = False
        m[:, -150:] = False
        product_mask = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    x0, y0, x1, y1 = (int(v) for v in text_bbox)
    h, w = product_mask.shape[:2]
    sub = product_mask[max(0, y0):min(h, y1 + 1), max(0, x0):min(w, x1 + 1)]
    return int(np.count_nonzero(sub))


def text_glyph_height_frac(bbox: tuple[int, int, int, int], H: int = 1920) -> float:
    """Glyph box height (y1 - y0) as a fraction of the frame height. Floors: overlay text >= 3.3 %, hero tier 12-18 %."""
    return float(bbox[3] - bbox[1]) / float(H)


# ------------------------------------------------------------------------------------------- v7.9.0 pop-out card checks
def popout_inner_edge_dark_strip_px(frame: np.ndarray, card_rect: Sequence[int], inset: int = 4, probe: int = 90) -> float:
    """Width (px at 1080 wide) of a dark band along the card's inner LEFT or RIGHT edge, whichever is wider. Rows between the rounded
    corners; a column counts as dark when it is < INNER_STRIP_DARK of the row's interior median (x0+probe..x0+2*probe) in > 50 % of the
    rows; the band is the run of dark columns starting `inset` px inside the edge (the anti-aliased edge itself is skipped). Gate: <= 4 px."""
    g = (frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)).astype(np.float32)
    x0, y0, x1, y1 = (int(v) for v in card_rect)
    ch = y1 - y0
    rows = g[y0 + ch // 5:y1 - ch // 5]
    widths = []
    for side in (rows[:, x0 + inset:x0 + inset + 2 * probe], rows[:, x1 - inset - 2 * probe:x1 - inset][:, ::-1]):
        ref = np.median(side[:, probe:], axis=1, keepdims=True)
        dark = ((side[:, :probe] < INNER_STRIP_DARK * ref).mean(axis=0) > 0.5)
        widths.append(int(np.argmin(dark)) if not dark.all() else probe)
    return float(max(widths)) * 1080.0 / g.shape[1]


def card_dark_speck_count(frame: np.ndarray, card_rect: Sequence[int], exclude_mask: np.ndarray | None = None, inset: int = 12) -> int:
    """Small dark blobs (area SPECK_AREA) on the card wall: pixels > SPECK_DARK under the local median (31 px), inside the card inset by
    `inset` px, outside `exclude_mask` (the person alpha, dilated 25 px). Gate: == 0 (v4 17.0 s: a 17x14 px dot at the top right)."""
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    x0, y0, x1, y1 = (int(v) + d for v, d in zip(card_rect, (inset, inset, -inset, -inset)))
    roi = g[y0:y1, x0:x1]
    cand = (cv2.medianBlur(roi, 31).astype(np.int16) - roi.astype(np.int16)) > SPECK_DARK
    if exclude_mask is not None:
        ex = cv2.dilate((np.asarray(exclude_mask)[y0:y1, x0:x1] > 0).astype(np.uint8), np.ones((51, 51), np.uint8))
        cand &= ex == 0
    n, _, st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    return int(sum(1 for i in range(1, n) if SPECK_AREA[0] <= st[i, cv2.CC_STAT_AREA] <= SPECK_AREA[1]))


def crown_edge_metrics(alpha: np.ndarray, level: float = 0.5, smooth_px: int = 15) -> dict[str, float]:
    """Top edge of a pop-out alpha crop (uint8 or float 0..1, rows above the card): per column the sub-pixel row where alpha first
    crosses `level`. `jaggedness_px` = std of that curve around its own `smooth_px` moving average (stair steps, ragged tufts);
    `rise_px` = median 10-90 % rise down the column. Gates: CROWN_JAG_GATE_PX, CROWN_RISE_GATE_PX."""
    a = np.asarray(alpha, np.float32)
    a = a / 255.0 if a.max() > 1.0 + 1e-6 else a
    ys, rises, cols = [], [], []
    for x in range(a.shape[1]):
        c = a[:, x]
        idx = np.where(c >= level)[0]
        if idx.size == 0 or idx[0] == 0 or c.max() < 0.9:
            continue
        i = int(idx[0])
        ys.append(i - 1 + (level - c[i - 1]) / max(c[i] - c[i - 1], 1e-6))
        cols.append(x)
        lo, hi = np.where(c >= 0.1)[0], np.where(c >= 0.9)[0]
        rises.append(float(hi[0] - lo[0]) if lo.size and hi.size else float("nan"))
    if len(ys) < smooth_px:
        return {"jaggedness_px": float("nan"), "rise_px": float("nan"), "columns": len(ys)}
    y = np.array(ys, np.float64)
    k = np.ones(smooth_px) / smooth_px
    sm = np.convolve(np.pad(y, smooth_px // 2, mode="edge"), k, mode="valid")[:y.size]
    inner = slice(smooth_px, max(smooth_px + 1, y.size - smooth_px))   # the crown sides are steep: keep the top arc
    return {"jaggedness_px": float(np.std((y - sm)[inner])), "rise_px": float(np.nanmedian(rises)), "columns": len(ys)}


# -------------------------------------------------------------------------------------------- v7.9.0 photosensitivity
def luma_series(video: Any, fps: float = 60, size: tuple[int, int] = (135, 240), t0: float = 0.0, t1: float | None = None) -> list[tuple[float, float]]:
    """[(t_s, whole-frame mean luma 0..255)] on a `size` gray proxy (every frame at `fps`)."""
    return [(round(float(t), 4), float(_gray_small(f, size).mean())) for t, f in _iter_frames(video, float(fps), float(t0), t1)]


def _transitions(series: Sequence[tuple[float, float]], swing: float) -> list[tuple[float, int, float]]:
    """Zig-zag with hysteresis `swing`: [(t_confirm, +1 rise / -1 fall, extreme value before the turn)]."""
    out: list[tuple[float, int, float]] = []
    if not series:
        return out
    hi = lo = series[0]
    trend = 0
    for t, v in series[1:]:
        if trend >= 0 and v > hi[1]:
            hi = (t, v)
        if trend <= 0 and v < lo[1]:
            lo = (t, v)
        if trend >= 0 and hi[1] - v >= swing:
            out.append((t, -1, hi[1]))
            trend, lo = -1, (t, v)
        elif trend <= 0 and v - lo[1] >= swing:
            out.append((t, +1, lo[1]))
            trend, hi = 1, (t, v)
    return out


def find_flashes(series: Sequence[tuple[float, float]], swing: float = FLASH_SWING, pulse_s: float = FLASH_PULSE_S) -> list[dict[str, float]]:
    """Bright pulses: the mean luma rises by >= `swing` and falls back by >= `swing` within `pulse_s` of its peak -> [{t, peak, base}]."""
    t_arr = np.array([s[0] for s in series], np.float64)
    v_arr = np.array([s[1] for s in series], np.float64)
    out = []
    for i in range(1, len(series) - 1):
        if not (v_arr[i] >= v_arr[i - 1] and v_arr[i] > v_arr[i + 1]):
            continue
        before = np.where((t_arr < t_arr[i]) & (t_arr >= t_arr[i] - pulse_s) & (v_arr <= v_arr[i] - swing))[0]
        after = np.where((t_arr > t_arr[i]) & (t_arr <= t_arr[i] + pulse_s) & (v_arr <= v_arr[i] - swing))[0]
        if before.size and after.size:
            out.append({"t": float(t_arr[i]), "peak": float(v_arr[i]), "base": float(v_arr[before[-1]])})
    return out


def _max_per_window(times: Sequence[float], win: float = 1.0) -> int:
    ts = sorted(times)
    return max((sum(1 for u in ts if t <= u < t + win - 1e-9) for t in ts), default=0)


def check_flashes(video: Any, fps: float = 60, t0: float = 0.0, t1: float | None = None, *, cap: float = FLASH_LUMA_CAP,
                  max_per_s: int = MAX_FLASHES_PER_S, swing: float = FLASH_SWING) -> dict[str, Any]:
    """Photosensitivity gate on rendered frames (path or BGR frame sequence at `fps`).
    Errors: a bright pulse whose mean luma peaks above `cap` (220); more than `max_per_s` flashes (pairs of opposing >= `swing`
    transitions, WCAG 2.3.1) in any 1 s window. A cut to a held bright scene (paper) is not a pulse and is never capped."""
    series = luma_series(video, fps, t0=t0, t1=t1)
    pulses = find_flashes(series, swing)
    tr = _transitions(series, swing)
    per_s = max((sum(1 for u, _, _ in tr if t <= u < t + 1.0 - 1e-9) // 2 for t, _, _ in tr), default=0)
    errors = [f"flash at {p['t']:.3f}s peaks at mean luma {p['peak']:.1f} > {cap:.0f}" for p in pulses if p["peak"] > cap]
    if per_s > max_per_s:
        errors.append(f"{per_s} flashes per second > {max_per_s} (WCAG 2.3.1 general flash threshold)")
    return {"ok": not errors, "peak_luma": round(max((p["peak"] for p in pulses), default=0.0), 1), "flashes": pulses,
            "max_flashes_per_s": int(per_s), "errors": errors, "frames": len(series)}


def flash_peak_luma(opacity: float, base_luma: float = FLASH_PLAN_BASE_LUMA, colour_bgr: Sequence[int] = (255, 255, 255)) -> float:
    """Mean luma of a frame at `base_luma` under a SCREEN flash of `colour_bgr` at `opacity` (0..1)."""
    b, g, r = (float(c) for c in colour_bgr)
    lc = 0.114 * b + 0.587 * g + 0.299 * r
    return float(base_luma + float(opacity) * lc * (255.0 - base_luma) / 255.0)


def _hex_bgr(c: Any) -> tuple[int, int, int]:
    if isinstance(c, str) and len(c.lstrip("#")) == 6:
        h = c.lstrip("#")
        return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)
    return tuple(int(v) for v in c) if c else (255, 255, 255)  # type: ignore[return-value]


def check_flash_plan(events: Sequence[dict], base_luma: float = FLASH_PLAN_BASE_LUMA, cap: float = FLASH_LUMA_CAP,
                     max_per_s: int = MAX_FLASHES_PER_S) -> list[dict[str, Any]]:
    """Plan twin of `check_flashes` in the studio_recipe finding format. A flash is an event of kind `flash` (`opacity` 0..1 or 0..100,
    a list takes its max; missing = a full flash) or any event with `flash_peak` (snap punch). Rules: `flash_luma_cap`, `flash_rate`."""
    fl = []
    for e in events:
        if e.get("kind") != "flash" and "flash_peak" not in e:
            continue
        o = e.get("opacity", e.get("flash_peak", 1.0))
        o = max(o) if isinstance(o, (list, tuple)) else o
        o = float(o) / 100.0 if float(o) > 1.0 else float(o)
        col = e.get("colour") or (e.get("flash_bgr") or ((200, 235, 255) if "flash_peak" in e else (255, 255, 255)))
        fl.append((e["t_ms"] / 1000.0, flash_peak_luma(o, base_luma, _hex_bgr(col)), e.get("id")))
    bad = [{"rule": "flash_luma_cap", "severity": "error", "t0": t, "t1": None, "value": round(p, 1), "limit": cap,
            "message": f"flash '{i}' lifts the frame to mean luma {p:.0f} > {cap:.0f} (photosensitivity); lower its opacity, ramp over >= 3 frames"}
           for t, p, i in fl if p > cap]
    n = _max_per_window([t for t, _, _ in fl])
    if n > max_per_s:
        bad.append({"rule": "flash_rate", "severity": "error", "t0": None, "t1": None, "value": n, "limit": max_per_s,
                    "message": f"{n} flashes inside one second > {max_per_s} (WCAG 2.3.1); merge or drop the re-triggers"})
    return bad


# ---------------------------------------------------------------------------------------------- v7.9.0 word-gap collision
def word_gap_series(font_px: float, gap_px: float, entrance: Sequence[dict] = (), *, word_w_px: float = 0.0,
                    per_word_scale: bool = False, fps: float = 60, min_opacity: float = 0.15) -> list[tuple[float, float, float]]:
    """[(t_ms, effective gap px, em px)] for each visible frame of an entrance (keys `{t_ms, opacity, blur_px, scale}`, linear in between).
    A line-level scale scales the gap; a per-word scale grows each word about its centre and eats (s - 1) * `word_w_px` of the gap; a
    Gaussian blur of sigma b spreads both neighbours' ink by b, so the gap loses 2 b. No entrance = the resting gap only.
    Optional keys (unscaled px, before the line scale): `extra_gap_px` = word spacing added on that frame (the entrance word-spacing
    guard), `shift_px` = how far a neighbour is still offset into the gap (a sliding character)."""
    ks = sorted(entrance, key=lambda k: k["t_ms"]) or [{"t_ms": 0.0, "opacity": 1.0, "blur_px": 0.0, "scale": 1.0}]
    tk = np.array([k["t_ms"] for k in ks], np.float64)
    get = lambda name, d: np.array([float(k.get(name, d)) for k in ks])  # noqa: E731
    op, bl, sc, ex, sh = get("opacity", 1.0), get("blur_px", 0.0), get("scale", 1.0), get("extra_gap_px", 0.0), get("shift_px", 0.0)
    n = int(math.floor((tk[-1] - tk[0]) * fps / 1000.0 + 1e-9)) + 1
    out = []
    for t in tk[0] + np.arange(n) * 1000.0 / fps:
        o, b, s, e, d = (float(np.interp(t, tk, v)) for v in (op, bl, sc, ex, sh))
        if o < min_opacity:
            continue
        base = gap_px + e - d
        gap = base - (s - 1.0) * word_w_px if per_word_scale else base * s
        out.append((round(float(t), 2), gap - 2.0 * b, font_px * s))
    return out


def entrance_word_spacing_em(blur_px: float, scale: float, font_px: float, natural_gap_em: float = SPACE_EM, *,
                             shift_px: float = 0.0, min_em: float = WORD_GAP_MIN_EM) -> float:
    """Extra word spacing (em of the UNSCALED font) that keeps `check_word_gaps` true on one frame of a line-level entrance.
    Frame model (`word_gap_series`): (natural + extra - shift) x font x s - 2 x blur >= min_em x font x s, so
        extra = max(0, min_em + 2 blur / (s x font) + shift / font - natural_gap_em)   (rounded UP to 1e-4 em).
    `blur_px` and `scale` are in the space the gate measures (screen px / the line scale); `natural_gap_em` is the resting ink gap
    (`natural_word_gap_em`, ~SPACE_EM + side bearings). It returns 0 exactly when the blur and shift are 0 and the resting gap already
    clears `min_em`: the line eases back to its natural spacing as the blur reaches 0. Shared by the web plates (JS mirror
    `entranceWordSpacingEm`) and the FilmCraft tracking keys (`typography_composer`)."""
    s = max(float(scale), 1e-3)
    f = max(float(font_px), 1e-3)
    need = float(min_em) + 2.0 * max(0.0, float(blur_px)) / (s * f) + max(0.0, float(shift_px)) / f
    return max(0.0, math.ceil((need - float(natural_gap_em)) * 1e4 - 1e-6) / 1e4)


def natural_word_gap_em(text: str, font_path: Any, letter_spacing_em: float = 0.0, *, space_em: float | None = None,
                        size: int = 200) -> float | None:
    """Narrowest resting INK gap between adjacent words of `text` (every line), in em, set in `font_path` with CSS `letter_spacing_em`
    (applied after every character, so twice inside a word gap: after the last letter and after the space). `space_em` replaces the
    space advance with a fixed box (kt07 `.kt07-space`; then only the trailing letter spacing of the last letter counts).
    None when no line has two words (nothing to collide)."""
    from PIL import ImageFont
    ft = ImageFont.truetype(str(font_path), int(size))
    best = None
    for line in str(text).splitlines():
        words = line.split()
        for w1, w2 in zip(words, words[1:]):
            right = ft.getbbox(w1)[2]
            left = ft.getbbox(w2)[0]
            if space_em is None:
                gap = ft.getlength(w1 + " ") - right + left + 2.0 * letter_spacing_em * size
            else:
                gap = ft.getlength(w1) - right + float(space_em) * size + left + letter_spacing_em * size
            best = gap / size if best is None else min(best, gap / size)
    return None if best is None else round(float(best), 4)


def check_word_gaps(lines: Sequence[dict], min_em: float = WORD_GAP_MIN_EM, fps: float = 60) -> list[dict[str, Any]]:
    """`word_gap_collision`: lines `{id, font_px, gap_px, entrance?, word_w_px?, per_word_scale?, t_ms?}`; every visible frame keeps the
    narrowest adjacent-word gap >= `min_em` em (v4 K3: 21 px gap, blur sigma 10 at 1.12x -> 'MÌNHVỪA')."""
    bad = []
    for ln in lines:
        ser = word_gap_series(ln["font_px"], ln["gap_px"], ln.get("entrance") or (), word_w_px=ln.get("word_w_px", 0.0),
                              per_word_scale=bool(ln.get("per_word_scale")), fps=fps)
        worst = min(ser, key=lambda r: r[1] - min_em * r[2], default=None)
        if worst and worst[1] < min_em * worst[2] - 1e-6:
            t = (ln.get("t_ms", 0) + worst[0]) / 1000.0
            bad.append({"rule": "word_gap_collision", "severity": "error", "t0": round(t, 3), "t1": None, "value": round(worst[1], 1),
                        "limit": round(min_em * worst[2], 1), "message": f"text '{ln.get('id')}' word gap {worst[1]:.1f} px < {min_em} em "
                        f"({min_em * worst[2]:.1f} px) during its entrance: widen the space, lower the blur (sigma <= 0.35 x gap) or stagger the words"})
    return bad


# ------------------------------------------------------------------------------------------------------------------ CLI
def _parse_mask(txt: str) -> tuple[float, float, float, float]:
    v = tuple(float(x) for x in txt.split(","))
    if len(v) != 4 or not all(0.0 <= x <= 1.0 for x in v):
        raise argparse.ArgumentTypeError("mask must be x0,y0,x1,y1 as fractions 0..1")
    return v  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v7.9.0 hook motion gate on a rendered preview (JSON on stdout, exit 1 when not ok)")
    ap.add_argument("video")
    ap.add_argument("--mask", action="append", type=_parse_mask, default=[], help="normalised x0,y0,x1,y1 to ignore (PiP / text box); repeatable")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=3.4)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--flash", action="store_true", help="v7.9.0 photosensitivity gate over --t0..--t1 (whole video when --t1 < 0) at 60 fps")
    a = ap.parse_args(argv)
    res = check_flashes(a.video, 60, a.t0, None if a.t1 < 0 else a.t1) if a.flash else check_motion(a.video, a.mask, a.t0, a.t1, fps=a.fps)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
