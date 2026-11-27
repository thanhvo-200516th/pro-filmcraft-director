#!/usr/bin/env python3
"""
Tests for package S1 (skill code v7.8.0): crisp pop-out card, product stage + glint + snap punch, motion gate,
minimum legible text guard + hero lock-up, `--hook-gates` wiring and the stale-version cleanup.

All inputs are synthetic (no real video, no network, no FilmCraft). Plain assert functions with a `__main__` runner
(pytest is not installed): `python3 tests/test_skill_v78.py`.
Labels: [DO] = measured on the real S09 / v3 frames by the research phase, [UOC] = estimate / design budget.
"""

from __future__ import annotations

import inspect
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
for _p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

W, H = 1080, 1920


# ---------------------------------------------------------------------------------------------- synthetic inputs
def _popout_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(light paper backdrop, dark textured A-roll 720x1280 portrait, person alpha) for the pop-out card."""
    backdrop = np.full((H, W, 3), (244, 238, 250), np.uint8)
    rng = np.random.default_rng(7)
    aroll = np.full((1280, 720, 3), (58, 66, 74), np.uint8)
    tex = cv2.GaussianBlur(rng.normal(0, 14, (1280, 720, 3)).astype(np.float32), (0, 0), 1.2)
    aroll = np.clip(aroll.astype(np.float32) + tex, 0, 255).astype(np.uint8)
    cv2.ellipse(aroll, (340, 700), (200, 260), 0, 0, 360, (150, 170, 200), -1)       # "face" with a hard-ish edge
    alpha = np.zeros((1280, 720), np.uint8)
    cv2.ellipse(alpha, (340, 760), (230, 300), 0, 0, 360, 255, -1)
    return backdrop, aroll, alpha


def _textured(h: int, w: int, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    g = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.5)
    g = (g / (np.abs(g).max() + 1e-6)) * 90 + 120
    return cv2.cvtColor(np.clip(g, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def _zoom_frames(base: np.ndarray, n: int, fps: int, rate_per_s: float, grain: float = 0.0) -> list[np.ndarray]:
    h, w = base.shape[:2]
    rng = np.random.default_rng(11)
    out = []
    for i in range(n):
        z = 1.0 + rate_per_s * (i / fps)
        m = np.array([[z, 0, (1 - z) * w / 2], [0, z, (1 - z) * h / 2]], np.float32)
        f = cv2.warpAffine(base, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)
        if grain:
            f = f + rng.normal(0, grain, f.shape)
        out.append(np.clip(f, 0, 255).astype(np.uint8))
    return out


# ---------------------------------------------------------------------------------------------- (1) pop-out
def test_01_popout_new_defaults_and_backward_compat() -> None:
    import fast_studio_compositor as fsc
    d = {k: v.default for k, v in inspect.signature(fsc.render_popout_studio_card).parameters.items()}
    assert d["card_rect"] == (70, 1065, 1010, 1705) and d["rx"] == 64
    assert d["edge_feather"] == 1.6 and d["edge_blur"] == 0.0
    assert d["bulge"] == 0.03 and d["sag"] == 0.015
    assert d["shadow_alpha"] == 0.16 and d["shadow_dy"] == 22 and d["shadow_sigma"] == 26
    assert d["head_out_xy"] == (540.0, 900.0) and d["photo_scale"] == 1.36
    assert d["pop_alpha_feather"] == 0.6 and d["pop_alpha_choke"] == 1
    assert d["sharpen"] == 0.7 and d["sharp_sigma"] == 1.3 and d["sharpen2_amount"] == 0.0 and d["alpha_curve"] is None
    # the positional signature (backdrop, aroll, person_alpha) is unchanged and the OLD explicit kwargs still render
    backdrop, aroll, alpha = _popout_inputs()
    out, meta = fsc.render_popout_studio_card(
        backdrop, aroll, alpha, card_rect=(90, 1030, 990, 1700), rx=84, edge_feather=7.0, edge_blur=7.0, bulge=0.075,
        sag=0.045, shadow_alpha=0.20, shadow_dy=30, shadow_sigma=34.0, pop_alpha_feather=1.3, pop_alpha_choke=2,
        head_out_xy=(540.0, 900.0), photo_scale=1.36)
    assert out.shape == (H, W, 3) and meta["card_rect"] == (90, 1030, 990, 1700)
    print("[PASS] 01: pop-out defaults are the v7.8.0 values; old kwargs still accepted")


def _edge_row_x(out: np.ndarray, y: int, x_lo: int, x_hi: int) -> float:
    import motion_gate as mg
    return mg.popout_edge_width_px(out, y, (x_lo, x_hi))


def test_02_popout_edge_is_crisp() -> None:
    """[DO] real S09: card edge 19-21 px -> 4-5 px with the new recipe; gate 10-90 % rise <= 6 px at 1080 width."""
    import fast_studio_compositor as fsc
    backdrop, aroll, alpha = _popout_inputs()
    out, meta = fsc.render_popout_studio_card(backdrop, aroll, alpha)
    x0, y0, x1, y1 = meta["card_rect"]
    wl = _edge_row_x(out, (y0 + y1) // 2, x0 - 22, x0 + 22)
    wr = _edge_row_x(out, (y0 + y1) // 2, x1 - 22, x1 + 22)
    assert 0.5 <= wl <= 6.0 and 0.5 <= wr <= 6.0, (wl, wr)
    old, _ = fsc.render_popout_studio_card(backdrop, aroll, alpha, edge_feather=7.0, edge_blur=7.0, bulge=0.075, sag=0.045)
    wo = _edge_row_x(old, (y0 + y1) // 2, x0 - 40, x0 + 40)
    assert wo > 6.0, f"the metric must flag the old soft edge (got {wo:.1f} px)"
    print(f"[PASS] 02: pop-out edge 10-90 % rise L={wl:.1f}px R={wr:.1f}px (old soft edge {wo:.1f}px)")


def test_03_sharpen_is_photo_only_and_raises_face_detail() -> None:
    import fast_studio_compositor as fsc
    import motion_gate as mg
    backdrop, aroll, alpha = _popout_inputs()
    soft, _ = fsc.render_popout_studio_card(backdrop, aroll, alpha, sharpen=0.0)
    sharp, meta = fsc.render_popout_studio_card(backdrop, aroll, alpha)
    # the paper (backdrop far from the card / shadow / head) is bit-identical: the USM never touches it
    assert np.array_equal(soft[:200], sharp[:200]) and np.array_equal(soft[1900:], sharp[1900:])
    roi = (250, 1200, 830, 1600)
    ratio = mg.face_laplacian_ratio(sharp, soft, roi)
    assert ratio >= 1.8, f"sharpen 0.7/1.3 must lift the face ROI Laplacian >= 1.8x of the unsharpened render (got {ratio:.2f})"
    second, _ = fsc.render_popout_studio_card(backdrop, aroll, alpha, sharpen2_amount=0.35)
    assert not np.array_equal(second, sharp)
    print(f"[PASS] 03: USM on the photo only; face ROI Laplacian ratio {ratio:.2f}x (>= 1.8x gate)")


def test_04_alpha_curve_shrinks_the_halo() -> None:
    import fast_studio_compositor as fsc
    backdrop, aroll, alpha = _popout_inputs()
    soft = cv2.GaussianBlur(alpha, (0, 0), 6.0)
    a, _ = fsc.render_popout_studio_card(backdrop, aroll, soft)
    b, _ = fsc.render_popout_studio_card(backdrop, aroll, soft, alpha_curve=(0.25, 0.75))
    assert not np.array_equal(a, b)
    # the crown above the card: a steeper alpha ramp leaves fewer semi-transparent (blended) pixels
    def blended(img: np.ndarray) -> int:
        d = np.abs(img[780:1060].astype(np.int16) - backdrop[780:1060].astype(np.int16)).max(axis=2)
        return int(((d > 4) & (d < 120)).sum())
    assert blended(b) <= blended(a)
    print("[PASS] 04: alpha_curve=(0.25,0.75) renders and does not widen the crown halo")


# ---------------------------------------------------------------------------------------------- (2) product stage
def _stage_source(cap_row: int, h: int = 720, w: int = 1280) -> np.ndarray:
    src = np.full((h, w, 3), (30, 28, 26), np.uint8)
    src[cap_row:cap_row + 160, 560:720] = (235, 235, 235)       # bright "cap"
    return src


def _first_bright_row(img: np.ndarray, x_lo: int, x_hi: int, thr: float = 128.0) -> int:
    col = img[:, x_lo:x_hi].mean(axis=(1, 2))
    return int(np.argmax(col > thr))


def test_05_stage_geometry_and_cap_top_is_anchored() -> None:
    """[DO] cap top ~ y=613 (0.32 H) at s=0.72; the product grows downward when zooming (cap top |dy| <= 2 px)."""
    import fast_studio_compositor as fsc
    geo = fsc.stage_geometry(0.72)
    assert abs(geo["cap_top_y"] - 613) <= 2 and 0.31 <= geo["cap_top_y"] / H <= 0.33
    y0, y1 = geo["text_band"]
    assert 0 <= y0 < y1 < geo["cap_top_y"], geo
    bx0, by0, bx1, by1 = geo["product_bbox"]
    assert by0 >= geo["cap_top_y"] - 1 and by1 == H
    cap_row = int(round(fsc.CAP_TOP_SRC_FRAC * 720))
    src = _stage_source(cap_row)
    ys = []
    for z in (1.0, 1.05, 1.1, 1.18, 1.25):
        out = fsc.render_product_stage(src, s=0.72, zoom=z)
        assert out.shape == (H, W, 3) and out.dtype == np.uint8
        ys.append(_first_bright_row(out, 500, 580))
    assert max(ys) - min(ys) <= 2, f"cap top moved: {ys}"
    assert abs(ys[0] - geo["cap_top_y"]) <= 3, (ys, geo)
    # explicit anchor: the output row `cap_anchor_y` is the fixed point of the zoom (a bright stripe on source row 84.6 sits there)
    stripe = np.full((720, 1280, 3), 30, np.uint8)
    stripe[84:86, :] = 240
    rows = []
    for z in (1.0, 1.2):
        out = fsc.render_product_stage(stripe, s=0.72, zoom=z, cap_anchor_y=700)
        rows.append(_first_bright_row(out[:, 500:580], 0, 80))
    assert abs(rows[0] - 700) <= 3 and abs(rows[1] - 700) <= 3, rows
    # the product grows downward: the cap bottom edge moves down with zoom
    def cap_bottom(img: np.ndarray) -> int:
        col = img[:, 500:580].mean(axis=(1, 2))
        return int(np.where(col > 128)[0].max())
    assert cap_bottom(fsc.render_product_stage(src, zoom=1.25)) > cap_bottom(fsc.render_product_stage(src, zoom=1.0)) + 20
    # the stage above the product is blurred replicate fill (no bright cap smear above the cap top)
    out = fsc.render_product_stage(src, zoom=1.0)
    assert out[: geo["cap_top_y"] - 20, 500:580].mean() < 80
    # 9:16 sources are accepted too
    port = fsc.render_product_stage(np.full((1920, 1080, 3), 90, np.uint8), s=0.72)
    assert port.shape == (H, W, 3)
    print(f"[PASS] 05: cap top fixed across zoom 1.0-1.25 (rows {ys}); geometry cap_top={geo['cap_top_y']} band={geo['text_band']}")


def test_06_glint_and_snap_punch() -> None:
    import fast_studio_compositor as fsc
    img = np.full((H, W, 3), 15, np.uint8)
    img[900:1700, 300:800] = (90, 100, 110)                      # lit glass area
    assert np.array_equal(fsc.glint_sweep(img, 0.0), img) and np.array_equal(fsc.glint_sweep(img, 1.0), img)
    mid = fsc.glint_sweep(img, 0.5)
    d = mid.astype(np.int16) - img.astype(np.int16)
    assert d.min() >= 0 and d.max() > 0, "screen blend is additive"
    assert d[:800, :].max() == 0 or d[:800].mean() < d[900:1700, 300:800].mean(), "luminance weighting keeps the dark stage calm"
    assert d.max() <= 0.25 * 255 + 2, f"peak stays within amount 0.25 (got {d.max()})"
    seen = [int((fsc.glint_sweep(img, t) != img).any(axis=2).sum()) for t in (0.35, 0.5, 0.65)]
    assert all(s > 0 for s in seen), seen
    src = _stage_source(int(round(fsc.CAP_TOP_SRC_FRAC * 720)))
    stage = fsc.render_product_stage(src)
    ay = fsc.stage_geometry(0.72)["cap_top_y"]
    pun = fsc.snap_punch(stage, 1.10, anchor_xy=(W / 2, ay), flash=0.0)
    assert abs(_first_bright_row(pun, 500, 580) - _first_bright_row(stage, 500, 580)) <= 2, "snap punch keeps the cap top fixed"
    fl = fsc.snap_punch(stage, 1.0, anchor_xy=(W / 2, ay), flash=0.28)
    assert fl.mean() > stage.mean()
    print("[PASS] 06: glint_sweep (screen blend, luminance weighted) and anchored snap_punch")


# ---------------------------------------------------------------------------------------------- (3) motion gate
def test_07_motion_gate_static_fails_push_passes() -> None:
    """[UOC] bars: no run < 1.0 diff longer than 0.6 s; masked mean >= 2.0 (@__dviet B-roll-first 1.9-2.4)."""
    import motion_gate as mg
    base = _textured(480, 270)
    n, fps = 102, 30                                               # 3.4 s
    static = _zoom_frames(base, n, fps, 0.0, grain=0.6)
    r = mg.check_motion(static, (), 0.0, 3.4, fps=fps)
    assert not r["ok"] and r["max_static_run_s"] > 0.6 and r["share_below_1"] > 0.9 and r["mean"] < 2.0, r
    push = _zoom_frames(base, n, fps, 0.14, grain=0.0)             # 14 %/s push on a 270x480 proxy with real-looking detail
    p = mg.check_motion(push, (), 0.0, 3.4, fps=fps)
    assert p["ok"] and p["mean"] >= 2.0 and p["max_static_run_s"] <= 0.6, p
    print(f"[PASS] 07: static grain clip FAILS (mean {r['mean']:.2f}, run {r['max_static_run_s']:.2f}s); push PASSES (mean {p['mean']:.2f})")


def test_08_motion_gate_flashes_masks_and_series() -> None:
    import motion_gate as mg
    base = _textured(480, 270)
    fps = 30
    frames = _zoom_frames(base, 90, fps, 0.0, grain=0.6)
    for i in (40, 41):                                              # a white flash in the middle of a static stretch
        frames[i] = np.full_like(frames[i], 255)
    series = mg.bg_diff_series(frames, fps=fps)
    assert all(len(x) == 2 for x in series)
    runs = mg.static_runs(series, thr=1.0, min_len_s=0.6)
    assert runs and max(r[1] - r[0] for r in runs) > 2.0, "flash frames are excluded, they do not break the static run"
    raw = mg.bg_diff_series(frames, fps=fps, exclude_cut_frames=False)
    assert max(d for _, d in raw) > 20 and max(d for _, d in series) < 20
    # motion only inside the masked rectangle does not count
    moving = [f.copy() for f in _zoom_frames(base, 60, fps, 0.0, grain=0.6)]
    for i, f in enumerate(moving):
        f[360:470, 150:260] = (i * 37) % 255
    unmasked = mg.check_motion(moving, (), 0.0, 2.0, fps=fps)
    masked = mg.check_motion(moving, [(0.5, 0.7, 1.0, 1.0)], 0.0, 2.0, fps=fps)
    assert unmasked["mean"] > masked["mean"] + 0.5 and not masked["ok"]
    # t0 / t1 window selects the frames
    win = mg.bg_diff_series(frames, fps=fps, t0=1.0, t1=2.0)
    assert 28 <= len(win) <= 31
    print("[PASS] 08: flashes excluded from runs, mask rects ignored, window honoured")


def test_09_motion_gate_video_file_and_cli() -> None:
    import motion_gate as mg
    base = _textured(480, 270)
    with tempfile.TemporaryDirectory(prefix="pfd_mg_") as td:
        p = Path(td) / "clip.mp4"
        wr = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 30, (270, 480))
        assert wr.isOpened()
        for f in _zoom_frames(base, 60, 30, 0.0, grain=0.0):
            wr.write(f)
        wr.release()
        ser = mg.bg_diff_series(str(p), fps=30)
        assert len(ser) >= 50 and max(d for _, d in ser) < 2.0
        r = subprocess.run([sys.executable, str(TOOLS_DIR / "motion_gate.py"), str(p), "--t1", "2.0"], capture_output=True, text=True)
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        doc = json.loads(r.stdout)
        assert doc["ok"] is False and "max_static_run_s" in doc and "share_below_1" in doc
    print("[PASS] 09: video file path and the CLI (exit 1 on a static clip, JSON on stdout)")


def test_10_edge_laplacian_overlap_and_glyph_metrics() -> None:
    import motion_gate as mg
    img = np.zeros((H, W, 3), np.uint8)
    img[:, 540:] = 255
    assert mg.popout_edge_width_px(img, 900, (500, 580)) <= 1.5          # a hard step is ~1 px
    soft = cv2.GaussianBlur(img, (0, 0), 6.0)
    assert 10 < mg.popout_edge_width_px(soft, 900, (440, 640)) < 20       # 10-90 % of sigma 6 is ~15 px
    half = cv2.resize(img, (W // 2, H // 2))
    assert abs(mg.popout_edge_width_px(half, 450, (250, 290)) - mg.popout_edge_width_px(img, 900, (500, 580))) <= 2.5  # normalised to 1080 wide
    src = _textured(H, W)
    assert abs(mg.face_laplacian_ratio(src, src, (100, 100, 900, 900)) - 1.0) < 1e-6
    assert mg.face_laplacian_ratio(cv2.GaussianBlur(src, (0, 0), 2), src, (100, 100, 900, 900)) < 0.5
    mask = np.zeros((H, W), np.uint8)
    mask[1000:1900, 200:880] = 255
    assert mg.hero_product_overlap_px(None, (100, 300, 900, 590), mask) == 0
    assert mg.hero_product_overlap_px(None, (100, 900, 900, 1100), mask) == 101 * 680
    assert abs(mg.text_glyph_height_frac((0, 300, 800, 590), 1920) - 290 / 1920) < 1e-9
    print("[PASS] 10: edge width, Laplacian ratio, hero/product overlap and glyph-height metrics")


# ---------------------------------------------------------------------------------------------- (4) text guard + hero
def test_11_min_text_size_guard() -> None:
    import web_plate_builder as wpb
    assert wpb.MIN_OVERLAY_FONT_PX == 64 and wpb.MIN_OVERLAY_CAP_PX == 46 and abs(wpb.MIN_GLYPH_FRAC - 0.033) < 1e-9
    assert wpb.enforce_min_text_px(31) == 64 and wpb.enforce_min_text_px(80) == 80
    try:  # v7.9.0: forcing a size below the floor is an error (it only warned in v7.8.0)
        wpb.enforce_min_text_px(40, forced=True, label="x")
        raise AssertionError("forcing a size below the floor must raise")
    except ValueError as e:
        assert "64" in str(e), e
    assert wpb.enforce_min_text_px(64, forced=True) == 64 and wpb.enforce_min_text_px(90, forced=True) == 90
    # kt12 whisper default is no longer 31-40 px
    html = wpb._build_kt12_whisper_or_directional_echo({"mode": "whisper", "main_text": "nhưng điều ít ai để ý là..."}, 1080, 560)
    px = [int(m) for m in re.findall(r"font-size:\s*(\d+)px", html)]
    assert px and min(px) >= 64, px
    try:
        wpb._build_kt12_whisper_or_directional_echo({"mode": "whisper", "main_text": "abc", "main_size": 36}, 1080, 560)
        raise AssertionError("an explicit 36 px whisper must raise")
    except ValueError as e:
        assert "kt12 whisper" in str(e), e
    print(f"[PASS] 11: min text size guard (floor 64 px / cap 46 px / 3.3 %); kt12 whisper font-size {min(px)} px")


def _hero_font_ok() -> bool:
    import web_plate_builder as wpb
    return (wpb.FONT_ROOT_BASE / "BeVietnamPro-ExtraBold.ttf").is_file()


def test_12_hero_lockup_lines_band_and_legacy_default() -> None:
    import fast_studio_compositor as fsc
    import motion_gate as mg
    import web_plate_builder as wpb
    if not _hero_font_ok():
        print("[SKIP] 12: BeVietnamPro-ExtraBold.ttf not installed")
        return
    # legacy default: '3' + 'BƯỚC' on one baseline, 1080x640 plate, baseline 475, 780 px lock-up, gold
    leg = wpb.render_hero_lockup()
    assert leg["rgba"].shape == (640, 1080, 4) and leg["lines"] == [("3", "#F5C451", 475), ("BƯỚC", "#F5C451", 475)]
    assert leg["bbox"] == (171, 190, 924, 478), leg["bbox"]       # [DO] identical to the v3 `_hero_layers()` ink box
    # band-clamped two-line hero on the product stage: 0 px overlap with the product
    geo = fsc.stage_geometry(0.72)
    band = geo["text_band"]
    lines = [("VIDEO", "#FFFFFF", 420), ("SẢN PHẨM", "#F5C451", 560)]
    hero = wpb.render_hero_lockup(lines, plate_size=(W, H), target_w=800, text_band=band)
    bx0, by0, bx1, by1 = hero["bbox"]
    assert band[0] <= by0 and by1 <= band[1], (hero["bbox"], band)
    frac = (by1 - by0 + 1) / H
    assert hero["hero_frac"] == frac or abs(hero["hero_frac"] - frac) < 1e-6
    prod = np.zeros((H, W), np.uint8)
    px0, py0, px1, py1 = geo["product_bbox"]
    prod[py0:py1, px0:px1] = 255
    assert mg.hero_product_overlap_px(None, hero["bbox"], prod) == 0
    # a baseline that would push the block below the band is clamped back inside it
    low = wpb.render_hero_lockup([("VIDEO", "#FFFFFF", 900), ("SẢN PHẨM", "#F5C451", 1040)], plate_size=(W, H), target_w=800, text_band=band)
    assert low["bbox"][3] <= band[1]
    # a block taller than the band cannot be clamped: raise
    try:
        wpb.render_hero_lockup(lines, plate_size=(W, H), target_w=800, text_band=(100, 200))
    except ValueError:
        pass
    else:
        raise AssertionError("an impossible band must raise ValueError")
    # glyph height floor
    assert mg.text_glyph_height_frac(hero["bbox"], H) >= wpb.MIN_GLYPH_FRAC
    print(f"[PASS] 12: hero lock-up lines/baselines, band clamp, 0 px product overlap (hero {frac * 100:.1f} % of H)")


# ---------------------------------------------------------------------------------------------- (5) wiring + versions
def test_13_hook_gates_flag_is_optional_and_wired() -> None:
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    assert '"--hook-gates"' in src and '"--preview"' in src and "motion_gate" in src
    import compile_and_verify as cv
    old = sys.argv
    try:
        sys.argv = ["x", "--spec", "a.json", "--out", "b.fcproj", "--work", "w"]
        a = cv.parse_args()
        assert a.hook_gates is False and a.preview is None
        sys.argv = ["x", "--spec", "a.json", "--out", "b.fcproj", "--work", "w", "--hook-gates", "--preview", "p.mp4"]
        a = cv.parse_args()
        assert a.hook_gates is True and a.preview == "p.mp4"
    finally:
        sys.argv = old
    assert hasattr(cv, "run_hook_gates")
    print("[PASS] 13: --hook-gates is off by default and wired to motion_gate.check_motion")


def test_14_stale_versions_are_gone() -> None:
    for rel in ("install.sh", "requirements.txt", "scripts/dviet_smooth_camera_engine.py", "scripts/tools/probe_and_align.py",
                "scripts/vendor/ovs_core/PROVENANCE.md"):
        txt = (SKILL_ROOT / rel).read_text(encoding="utf-8")
        assert "7.6.0" not in txt and "7.4.0" not in txt, rel
    assert "7.9.0" in (SKILL_ROOT / "install.sh").read_text(encoding="utf-8")
    assert "7.9.0" in (SKILL_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()[0]
    assert "7.9.0" in (SKILL_ROOT / "scripts" / "vendor" / "ovs_core" / "PROVENANCE.md").read_text(encoding="utf-8").splitlines()[0]
    import dviet_smooth_camera_engine as eng
    front = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    assert eng.ENGINE_VERSION == re.search(r"\bv(\d+\.\d+\.\d+)", front).group(1), eng.ENGINE_VERSION  # shared source: SKILL.md
    inst = (SKILL_ROOT / "install.sh").read_text(encoding="utf-8")
    assert "tests/test_*.py" in inst and "test_studio_recipe.py" not in inst
    print("[PASS] 14: stale 7.6.0 / 7.4.0 strings replaced; install.sh runs every tests/test_*.py")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (skill v7.8.0 S1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
