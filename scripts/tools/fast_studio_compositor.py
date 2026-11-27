#!/usr/bin/env python3
"""
Universal Studio Director v7.9.0 — Fast Studio Framing & C/AVX2 FFmpeg Compositor
=================================================================================
v7.9.0 audit fixes (7.9.1 driver): `probe_video` + `check_look_s_geometry` (ffprobe: video stream, dims, fps; Look S needs 9:16,
drawn at 1080x1920) used by the CLI and `look_s_render.py` (the Look S CLI driver); the plate encoder never leaks ffmpeg or temp files;
concat lists escape `'` and every temp name is unique (parallel safe); the full-width alpha cache is content-hashed and written atomically;
Playfair lookup falls back to fontconfig with a loud WARNING; headline text is NFC-normalised.
v7.9.0 (v4 review K2 / K4 / A1): `render_popout_studio_card` cleans dark source side bands (letterbox / dark wall edge) and small dark wall
specks before the card is cut, refines the crown matte (guided filter on the photo + edge contrast, `crown_refine`), reports
`source_bands_px`, `card_src_rect`, `crown_alpha`; `snap_punch` caps the flashed frame at mean luma 220 (photosensitivity). Gates: motion_gate.
v7.8.0 (package S1): crisp pop-out defaults (edge 19-21 px -> 4-5 px [DO]; USM on the photo only, Lanczos4), `render_product_stage` +
`stage_geometry` (cap-top-anchored zoom, product-safe text band), `glint_sweep`, `snap_punch`. Old callers keep working.
v7.7.0: Look S pop-out card (`render_popout_studio_card`, A/B flag `LOOK_S_POPOUT`, default OFF = unchanged rounded card) with
`render_lavender_paper` / `render_gradient_italic_headline`; alpha-guarded wall cleaner (`clean_aroll_preserve_hair_crown(...,
person_alpha_u8=...)`, no-alpha path unchanged) passed through by the A1 / A2 / B renderers.
v7.4.0: `import os` crash fix, matte-model resolver (`PFD_MATTE_MODEL` -> u2netp -> birefnet-portrait, loud stderr
WARNING on the ~30 s/frame birefnet fallback), minimal CLI (`--list-options`, `--draft` / `--master`, `--input`, `--out`):
the CLI is a plain re-encode; the studio look is the Python API (see the studio recipe).
Eliminates ALL 4 root causes of visual framing defects & slow CPU rendering:

1. `render_full_head_studio_card(...)`:
   - Full-Head Rounded Studio Frame (`card_rect = (86, 790, 994, 1810), rx = 48` on light paper
     or `(96, 800, 984, 1810), rx = 48` on dark silk) enclosing 100% of the speaker's hair,
     headroom, ears, face, shoulders, and hands cleanly inside the rounded studio card.
   - Outer volumetric card aura (`backlight_halo_bgr`, `sigma = 46px`) radiates around all 4
     sides of the card BEFORE drawing the crisp 2x-supersampled card & dual specular rim.
   - Zero `u2netp` matting cost, zero shaved hair, zero ear-level crop, ~200 fps in Python!

2. `render_squircle_pip_window(...)`:
   - Clean Architectural Squircle Picture-in-Picture Window (`312x390, rx = 44`, bottom-right
     `(700, 1446, 1012, 1836)` or bottom-left `(68, 1446, 380, 1836)`).
   - Frames natural warm-lit speaker portrait (`x_src = 210..870, y_src = 785..1605`) inside
     a 2x-supersampled dual-rim glass squircle + soft ambient elevation shadow.
   - Zero amputated sleeves, zero mid-air torso gap, zero muddy oval halo, ~2,000 fps!

3. `get_or_build_fullwidth_person_alpha_seq(...)` + `apply_fullwidth_neon_rim_blackout(...)`:
   - Full-width `x = 0..1080` speaker silhouette alpha cache (persistent `.npz` keyed by a SHA-256 of the sampled frames)
     with uncropped shoulders (`w = 1.0` across `0..1080` for `y_src >= 1125`) and explicit
     screen-border morphological gradient suppression so `VFX-02` Neon Rim-Contour wraps
     cleanly across the entire shoulder to `x = 1080` with ZERO vertical border laser lines!

4. `compose_master_mp4_via_ffmpeg(...)` + `RenderGear` (`draft` 540x960@30fps vs `master` 1080x1920@60fps):
   - Single-stream V1 plate encoding (`50%` fewer video streams!) + native C/AVX2 `ffmpeg -filter_complex`
     compositing of all kinetic `.mov` plates, V2 `Screen` optical transitions (`Flash-Out`, `Film-Burn`,
     `Light-Leak`), BT.709 broadcast limiter, and `-14.0 LUFS` audio master in ~10–16 seconds!
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unicodedata
import warnings
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw


@dataclasses.dataclass(frozen=True)
class RenderGear:
    name: str
    width: int
    height: int
    fps: int
    crf: int
    preset: str

    @property
    def scale_xy(self) -> float:
        return self.width / 1080.0

    @classmethod
    def draft(cls) -> "RenderGear":
        return cls(name="draft", width=540, height=960, fps=30, crf=20, preset="ultrafast")

    @classmethod
    def master(cls) -> "RenderGear":
        return cls(name="master", width=1080, height=1920, fps=60, crf=15, preset="veryfast")


LOOK_S_W, LOOK_S_H = 1080, 1920   # every Look S constant (card / PiP rects, crown anchors, alpha cone) is in this portrait space
_ASPECT_TOL = 0.01                # 9:16 within 1 % counts as portrait (e.g. 720x1280, 540x960, 2160x3840)
_PROBE_TIMEOUT_S = 60


def _parse_rate(txt: str | None) -> float:
    try:
        num, _, den = str(txt or "0/1").partition("/")
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe_video(path: Path | str) -> dict[str, Any]:
    """ffprobe facts of a media file: {width, height, fps, duration, has_audio, codec}. Raises FileNotFoundError (no file) or
    ValueError (ffprobe failed, no video stream, no width/height or no frame rate)."""
    vp = Path(path)
    if not vp.is_file():
        raise FileNotFoundError(f"input not found: {vp}")
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate:format=duration",
         "-of", "json", str(vp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_PROBE_TIMEOUT_S,
    )
    if pr.returncode != 0:
        raise ValueError(f"ffprobe cannot read {vp}: {pr.stderr.strip()[-300:]}")
    doc = json.loads(pr.stdout or "{}")
    streams = doc.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"no video stream in {vp}")
    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    fps = _parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate"))
    if w <= 0 or h <= 0:
        raise ValueError(f"video stream of {vp} has no width/height")
    if fps <= 0:
        raise ValueError(f"video stream of {vp} has no frame rate")
    try:
        dur = float((doc.get("format") or {}).get("duration") or 0.0)
    except ValueError:
        dur = 0.0
    return {"width": w, "height": h, "fps": round(fps, 4), "duration": round(dur, 4),
            "has_audio": any(s.get("codec_type") == "audio" for s in streams), "codec": video.get("codec_name")}


def check_look_s_geometry(width: int, height: int) -> dict[str, Any]:
    """Look S input geometry verdict: `exact` (1080x1920), `scale` (other 9:16 portrait: resized to 1080x1920 once, a warning)
    or `refuse` (not 9:16: card / PiP / crown geometry would be wrong; reframe to 9:16 first)."""
    if (width, height) == (LOOK_S_W, LOOK_S_H):
        return {"status": "exact", "message": f"{width}x{height} matches the Look S geometry"}
    want = LOOK_S_W / LOOK_S_H
    if height > 0 and abs(width / height - want) / want <= _ASPECT_TOL:
        return {"status": "scale", "message": f"{width}x{height} is 9:16 but not 1080x1920: frames are scaled to 1080x1920 "
                                              f"({'upscaled, softer' if width < LOOK_S_W else 'downscaled'})"}
    return {"status": "refuse", "message": f"{width}x{height} is not 9:16 portrait: Look S geometry (cards, PiP, crown anchors) "
                                           "assumes 1080x1920; reframe the A-roll to 9:16 first"}


_FULL_CARD_RIG_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_SQUIRCLE_PIP_RIG_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_ORT_U2NETP_SINGLETON: tuple[ort.InferenceSession, str] | None = None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _matte_model_candidates() -> list[tuple[str, Path]]:
    """Ordered (label, path) candidates: env override, legacy env, u2netp, then the installed birefnet-portrait."""
    cands: list[tuple[str, Path]] = []
    for env_name in ("PFD_MATTE_MODEL", "U2NETP_ONNX_PATH"):
        raw = os.environ.get(env_name)
        if raw:
            cands.append((f"${env_name}", Path(raw).expanduser()))
    home = Path.home()
    cands.append(("u2netp", home / ".rembg/models/u2netp/u2netp.onnx"))
    cands.append(("birefnet-portrait", home / ".rembg/models/birefnet-portrait/birefnet-portrait.onnx"))
    return cands


def resolve_matte_model_path() -> Path:
    """First existing matte model; raises a clear `FileNotFoundError` naming every path and `PFD_MATTE_MODEL`."""
    cands = _matte_model_candidates()
    for label, p in cands:
        if p.is_file():
            if label == "birefnet-portrait":
                u2 = next(q for lbl, q in cands if lbl == "u2netp")
                print(
                    f"WARNING: u2netp matte model not found ({u2}); falling back to birefnet-portrait ({p}). "
                    "birefnet-portrait costs ~30 s per frame on CPU (u2netp: ~0.1 s). "
                    "Fetch u2netp (curl -L --create-dirs -o ~/.rembg/models/u2netp/u2netp.onnx "
                    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx) "
                    "or set PFD_MATTE_MODEL=/path/model.onnx.",
                    file=sys.stderr,
                )
            return p
    tried = ", ".join(str(p) for _, p in cands)
    raise FileNotFoundError(
        "No portrait matte ONNX model found. Tried: "
        f"{tried}. Install one of them (e.g. `rembg` downloads u2netp/birefnet-portrait into ~/.rembg/models/) "
        "or point the env var PFD_MATTE_MODEL at a .onnx file."
    )


def _get_u2netp_session() -> tuple[ort.InferenceSession, str]:
    global _ORT_U2NETP_SINGLETON
    if _ORT_U2NETP_SINGLETON is None:
        onnx_p = resolve_matte_model_path()
        opts = ort.SessionOptions()
        opts.enable_cpu_mem_arena = False
        opts.enable_mem_pattern = False
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 1
        sess = ort.InferenceSession(str(onnx_p), sess_options=opts, providers=["CPUExecutionProvider"])
        _ORT_U2NETP_SINGLETON = (sess, sess.get_inputs()[0].name)
    return _ORT_U2NETP_SINGLETON


def predict_u2netp_alpha_u8(rgb_u8: np.ndarray) -> np.ndarray:
    sess, inp_name = _get_u2netp_session()
    ih, iw = rgb_u8.shape[:2]
    in_shape = sess.get_inputs()[0].shape  # u2netp: 320x320, birefnet-portrait: 1024x1024
    side = int(in_shape[2]) if len(in_shape) == 4 and isinstance(in_shape[2], int) and in_shape[2] > 0 else 320
    im_320 = cv2.resize(rgb_u8, (side, side), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    mx = max(float(im_320.max()), 1.0) if side == 320 else 255.0
    im_norm = (im_320 / mx - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )
    chw = np.ascontiguousarray(im_norm.transpose((2, 0, 1))[None, ...], dtype=np.float32)
    pred = sess.run(None, {inp_name: chw})[0][0, 0]
    p_min, p_max = float(pred.min()), float(pred.max())
    pred_01 = (pred - p_min) / max(p_max - p_min, 1e-6)
    alpha_full = cv2.resize(pred_01, (iw, ih), interpolation=cv2.INTER_LINEAR)
    return np.clip(alpha_full * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)


def _clean_wall_for_render(aroll_bgr: np.ndarray, person_alpha_u8: np.ndarray, cache_key: str) -> np.ndarray:
    """Runs the alpha-guarded wall cleaner on a RAW A-roll frame of any size (the cleaner works in 1080x1920 space)."""
    h, w = aroll_bgr.shape[:2]
    if (h, w) == (1920, 1080):
        return clean_aroll_preserve_hair_crown(aroll_bgr, cache_key=cache_key, person_alpha_u8=person_alpha_u8)
    up = cv2.resize(aroll_bgr, (1080, 1920), interpolation=cv2.INTER_CUBIC)
    ua = cv2.resize(person_alpha_u8, (1080, 1920), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(clean_aroll_preserve_hair_crown(up, cache_key=cache_key, person_alpha_u8=ua), (w, h), interpolation=cv2.INTER_AREA)


# ==============================================================================
# 1. FULL-HEAD ROUNDED STUDIO CARD (ZERO HEAD/HAIR CLIPPING, FULL OUTER AURA)
# ==============================================================================
def _get_full_head_card_rig(
    W: int,
    H: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rx: int,
    mode: str,
    border_rgb: tuple[int, int, int],
) -> dict[str, Any]:
    key = (W, H, x0, y0, x1, y1, rx, mode, border_rgb)
    if key in _FULL_CARD_RIG_CACHE:
        return _FULL_CARD_RIG_CACHE[key]

    cw, ch = x1 - x0, y1 - y0
    ss = 2
    # 2x supersampled anti-aliased interior mask [ch, cw, 1]
    m_hi = Image.new("L", (cw * ss, ch * ss), 0)
    ImageDraw.Draw(m_hi).rounded_rectangle([0, 0, cw * ss - 1, ch * ss - 1], radius=rx * ss, fill=255)
    mask_u8 = np.asarray(m_hi.resize((cw, ch), Image.Resampling.LANCZOS), dtype=np.uint8)
    mask_f = (mask_u8.astype(np.float32) * (1.0 / 255.0))[:, :, None]

    # Pre-baked outer shadow & outer halo field inside padded ROI [ry0:ry1, rx0:rx1]
    pad = 110
    rx0, ry0 = max(0, x0 - pad), max(0, y0 - pad)
    rx1, ry1 = min(W, x1 + pad), min(H, y1 + pad)
    rw, rh = rx1 - rx0, ry1 - ry0

    sh_pil = Image.new("L", (rw, rh), 0)
    ImageDraw.Draw(sh_pil).rounded_rectangle(
        [x0 - rx0 + 4, y0 - ry0 + 22, x1 - rx0 - 4, y1 - ry0 + 22], radius=rx, fill=255
    )
    sh_blur = cv2.GaussianBlur(np.asarray(sh_pil, dtype=np.float32) * (1.0 / 255.0), (0, 0), 30.0)
    sh_alpha = (sh_blur * (0.18 if mode == "light" else 0.56))[:, :, None]

    aura_pil = Image.new("L", (rw // 2, rh // 2), 0)
    ImageDraw.Draw(aura_pil).rounded_rectangle(
        [(x0 - rx0 - 6) // 2, (y0 - ry0 - 8) // 2, (x1 - rx0 + 6) // 2, (y1 - ry0 + 8) // 2],
        radius=max(6, rx // 2),
        fill=255,
    )
    aura_sm = cv2.GaussianBlur(np.asarray(aura_pil, dtype=np.float32) * (1.0 / 255.0), (0, 0), 22.0)
    aura_roi = cv2.resize(aura_sm, (rw, rh), interpolation=cv2.INTER_LINEAR)[:, :, None]

    # Subtle inner studio edge vignette inside [ch, cw] so dark/warm corners look optical
    yy_i, xx_i = np.mgrid[0:ch, 0:cw].astype(np.float32)
    nx_i = (xx_i - cw * 0.5) / (cw * 0.52)
    ny_i = (yy_i - ch * 0.44) / (ch * 0.56)
    r2_i = nx_i * nx_i + ny_i * ny_i
    inner_vig = np.clip(1.0 - 0.16 * np.maximum(0.0, r2_i - 0.35), 0.76, 1.0)[:, :, None]

    # Crisp 2x supersampled dual rim cropped tightly to [ch + 8, cw + 8]
    rpad = 4
    rim_w, rim_h = cw + rpad * 2, ch + rpad * 2
    rim_hi = Image.new("RGBA", (rim_w * ss, rim_h * ss), (0, 0, 0, 0))
    rdr = ImageDraw.Draw(rim_hi)
    bx0, by0, bx1, by1 = rpad * ss, rpad * ss, (rpad + cw) * ss - 1, (rpad + ch) * ss - 1
    if mode == "light":
        rdr.rounded_rectangle([bx0 - 2, by0 - 2, bx1 + 2, by1 + 2], radius=(rx + 1) * ss, outline=(15, 23, 42, 34), width=3)
        rdr.rounded_rectangle([bx0 + 2, by0 + 2, bx1 - 2, by1 - 2], radius=max(4, (rx - 1) * ss), outline=(255, 255, 255, 248), width=5)
    else:
        rdr.rounded_rectangle(
            [bx0, by0, bx1, by1],
            radius=rx * ss,
            outline=(border_rgb[0], border_rgb[1], border_rgb[2], 195),
            width=4,
        )
        rdr.rounded_rectangle(
            [bx0 + 4, by0 + 4, bx1 - 4, by1 - 4],
            radius=max(4, (rx - 2) * ss),
            outline=(255, 255, 255, 58),
            width=2,
        )
    rim_rgba = np.asarray(rim_hi.resize((rim_w, rim_h), Image.Resampling.LANCZOS), dtype=np.uint8)
    rim_bgr = rim_rgba[:, :, 2::-1].astype(np.float32)
    rim_a = (rim_rgba[:, :, 3:4].astype(np.float32)) * (1.0 / 255.0)

    rig = {
        "x0": x0, "y0": y0, "x1": x1, "y1": y1,
        "rx0": rx0, "ry0": ry0, "rx1": rx1, "ry1": ry1,
        "mask_f": mask_f,
        "sh_alpha": sh_alpha,
        "aura_roi": aura_roi,
        "inner_vig": inner_vig,
        "rpad": rpad,
        "rim_bgr": rim_bgr,
        "rim_a": rim_a,
    }
    _FULL_CARD_RIG_CACHE[key] = rig
    return rig


def render_full_head_studio_card(
    backdrop_bgr: np.ndarray,
    aroll_clean_bgr: np.ndarray,
    *,
    card_rect: tuple[int, int, int, int] = (86, 790, 994, 1810),
    rx: int = 48,
    cam_scale: float = 0.96,
    cam_dx: float = 0.0,
    cam_dy: float = 30.0,
    mode: str = "light",
    border_rgb: tuple[int, int, int] = (255, 255, 255),
    backlight_halo_bgr: tuple[float, float, float] | None = None,
    backlight_strength: float = 0.0,
    chest_scrim: bool = False,
    person_alpha_u8: np.ndarray | None = None,
    wall_cache_key: str = "v73_studio_ref",
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """
    v7.7.0: pass the RAW A-roll plus `person_alpha_u8` to run the alpha-guarded wall cleaner first (`init_hair_safe_wall_reference`
    must have run for `wall_cache_key`); `None` = `aroll_clean_bgr` is used as given (unchanged).

    Renders a clean luxury rounded studio card enclosing 100% of the speaker's head, hair,
    headroom, ears, and shoulders (~90–120px natural studio headroom inside `card_rect`),
    with full-perimeter outer volumetric aura (`backlight_halo_bgr`) and crisp dual specular rim.
    """
    H, W = backdrop_bgr.shape[:2]
    x0, y0, x1, y1 = card_rect
    rig = _get_full_head_card_rig(W, H, x0, y0, x1, y1, rx, mode, border_rgb)
    if person_alpha_u8 is not None:
        aroll_clean_bgr = _clean_wall_for_render(aroll_clean_bgr, person_alpha_u8, wall_cache_key)

    piv = (W * 0.5, 1365.0 * (H / 1920.0))
    M = cv2.getRotationMatrix2D(piv, 0.0, float(cam_scale)).astype(np.float32)
    M[0, 2] += float(cam_dx) - float(x0)
    M[1, 2] += float(cam_dy) - float(y0)
    # Warp ONLY the [ch, cw] card interior instead of full 1080x1920!
    cw, ch = x1 - x0, y1 - y0
    card_ar = cv2.warpAffine(
        aroll_clean_bgr, M, (cw, ch), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
    ).astype(np.float32)
    card_ar *= rig["inner_vig"]

    if mode == "dark" or chest_scrim:
        yy_f = np.arange(y0, y1, dtype=np.float32)
        sc_start = 1430.0 * (H / 1920.0)
        sc_span = 310.0 * (H / 1920.0)
        u_sc = np.clip((yy_f - sc_start) / max(1.0, sc_span), 0.0, 1.0)
        w_sc = (0.5 * (1.0 - np.cos(np.pi * u_sc)))[:, None, None] * (0.42 if chest_scrim else 0.28)
        card_ar = card_ar * (1.0 - w_sc) + np.array([[[12.0, 10.0, 10.0]]], dtype=np.float32) * w_sc

    out = backdrop_bgr.copy()
    rx0, ry0, rx1, ry1 = rig["rx0"], rig["ry0"], rig["rx1"], rig["ry1"]
    roi = out[ry0:ry1, rx0:rx1].astype(np.float32)

    # 1. Ambient elevation drop shadow
    sh_col = np.array([[[28.0, 20.0, 15.0]]], dtype=np.float32) if mode == "light" else np.array([[[4.0, 4.0, 6.0]]], dtype=np.float32)
    sh_a = rig["sh_alpha"]
    roi = roi * (1.0 - sh_a) + sh_col * sh_a

    # 2. Full-card outer volumetric aura (glows evenly around ALL 4 sides of the rounded card!)
    if backlight_halo_bgr is not None and backlight_strength > 0.01:
        h_col = np.array([[list(backlight_halo_bgr)]], dtype=np.float32) * (1.0 / 255.0)
        scr_base = roi * (1.0 / 255.0)
        scr_add = np.clip(rig["aura_roi"] * float(backlight_strength) * 1.35, 0.0, 0.92) * h_col
        roi = (1.0 - (1.0 - scr_base) * (1.0 - scr_add)) * 255.0

    # 3. Composite rounded card interior cleanly inside [y0:y1, x0:x1]
    cx0_r, cy0_r = x0 - rx0, y0 - ry0
    sub_card = roi[cy0_r : cy0_r + ch, cx0_r : cx0_r + cw]
    cm = rig["mask_f"]
    roi[cy0_r : cy0_r + ch, cx0_r : cx0_r + cw] = sub_card * (1.0 - cm) + card_ar * cm

    # 4. Crisp 2x supersampled dual specular glass rim
    rp = rig["rpad"]
    ry_a, ry_b = cy0_r - rp, cy0_r + ch + rp
    rx_a, rx_b = cx0_r - rp, cx0_r + cw + rp
    if ry_a >= 0 and rx_a >= 0 and ry_b <= roi.shape[0] and rx_b <= roi.shape[1]:
        rim_sub = roi[ry_a:ry_b, rx_a:rx_b]
        ra = rig["rim_a"]
        roi[ry_a:ry_b, rx_a:rx_b] = rim_sub * (1.0 - ra) + rig["rim_bgr"] * ra

    out[ry0:ry1, rx0:rx1] = np.clip(roi + 0.5, 0.0, 255.0).astype(np.uint8)

    sy = H / 1920.0
    sx = W / 1080.0
    fx0 = piv[0] + (355.0 * sx - piv[0]) * cam_scale + cam_dx
    fx1 = piv[0] + (705.0 * sx - piv[0]) * cam_scale + cam_dx
    fy0 = piv[1] + (855.0 * sy - piv[1]) * cam_scale + cam_dy
    fy1 = piv[1] + (1375.0 * sy - piv[1]) * cam_scale + cam_dy
    return out, (fx0, fy0, fx1, fy1)


# ==============================================================================
# 2. ARCHITECTURAL SQUIRCLE PiP STUDIO WINDOW (ZERO CUTOUT AMPUTATION / HALO!)
# ==============================================================================
def _get_squircle_pip_rig(
    pw: int,
    ph: int,
    rx: int,
    rim_rgb: tuple[int, int, int],
) -> dict[str, Any]:
    key = (pw, ph, rx, rim_rgb)
    if key in _SQUIRCLE_PIP_RIG_CACHE:
        return _SQUIRCLE_PIP_RIG_CACHE[key]

    ss = 2
    m_hi = Image.new("L", (pw * ss, ph * ss), 0)
    ImageDraw.Draw(m_hi).rounded_rectangle([0, 0, pw * ss - 1, ph * ss - 1], radius=rx * ss, fill=255)
    mask_f = (np.asarray(m_hi.resize((pw, ph), Image.Resampling.LANCZOS), dtype=np.float32) * (1.0 / 255.0))[:, :, None]

    spad = 38
    sw, sh = pw + spad * 2, ph + spad * 2
    sh_pil = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(sh_pil).rounded_rectangle(
        [spad + 2, spad + 12, spad + pw - 2, spad + ph + 12], radius=rx, fill=255
    )
    sh_alpha = (cv2.GaussianBlur(np.asarray(sh_pil, dtype=np.float32) * (1.0 / 255.0), (0, 0), 16.0) * 0.62)[:, :, None]

    # Subtle outer jewel rim glow inside [sh, sw]
    gl_pil = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(gl_pil).rounded_rectangle(
        [spad - 2, spad - 2, spad + pw + 2, spad + ph + 2], radius=rx + 2, outline=255, width=6
    )
    gl_alpha = (cv2.GaussianBlur(np.asarray(gl_pil, dtype=np.float32) * (1.0 / 255.0), (0, 0), 10.0) * 0.42)[:, :, None]

    # Inner portrait optical vignette so warm studio room blends softly into glass rim
    yy_p, xx_p = np.mgrid[0:ph, 0:pw].astype(np.float32)
    nx_p = (xx_p - pw * 0.5) / (pw * 0.52)
    ny_p = (yy_p - ph * 0.42) / (ph * 0.56)
    r2_p = nx_p * nx_p + ny_p * ny_p
    inner_vig = np.clip(1.0 - 0.28 * np.maximum(0.0, r2_p - 0.25), 0.62, 1.0)[:, :, None]

    rpad = 4
    rw, rh = pw + rpad * 2, ph + rpad * 2
    rim_hi = Image.new("RGBA", (rw * ss, rh * ss), (0, 0, 0, 0))
    rdr = ImageDraw.Draw(rim_hi)
    bx0, by0, bx1, by1 = rpad * ss, rpad * ss, (rpad + pw) * ss - 1, (rpad + ph) * ss - 1
    rdr.rounded_rectangle(
        [bx0, by0, bx1, by1],
        radius=rx * ss,
        outline=(rim_rgb[0], rim_rgb[1], rim_rgb[2], 228),
        width=5,
    )
    rdr.rounded_rectangle(
        [bx0 + 5, by0 + 5, bx1 - 5, by1 - 5],
        radius=max(4, (rx - 3) * ss),
        outline=(255, 255, 255, 78),
        width=2,
    )
    rim_rgba = np.asarray(rim_hi.resize((rw, rh), Image.Resampling.LANCZOS), dtype=np.uint8)
    rim_bgr = rim_rgba[:, :, 2::-1].astype(np.float32)
    rim_a = (rim_rgba[:, :, 3:4].astype(np.float32)) * (1.0 / 255.0)

    rig = {
        "pw": pw, "ph": ph, "spad": spad, "rpad": rpad,
        "mask_f": mask_f,
        "sh_alpha": sh_alpha,
        "gl_alpha": gl_alpha,
        "inner_vig": inner_vig,
        "rim_bgr": rim_bgr,
        "rim_a": rim_a,
        "rim_bgr_col": np.array([[[float(rim_rgb[2]), float(rim_rgb[1]), float(rim_rgb[0])]]], dtype=np.float32),
    }
    _SQUIRCLE_PIP_RIG_CACHE[key] = rig
    return rig


def render_squircle_pip_window(
    canvas_bgr: np.ndarray,
    aroll_clean_bgr: np.ndarray,
    *,
    pip_rect: tuple[int, int, int, int] = (700, 1446, 1012, 1836),
    rx: int = 44,
    rim_rgb: tuple[int, int, int] = (245, 196, 81),
    inner_zoom: float = 1.02,
    opacity: float = 1.0,
    cy_src_1080p: float = 1160.0,
    crop_h_1080p: float = 875.0,
    person_alpha_u8: np.ndarray | None = None,
    wall_cache_key: str = "v73_studio_ref",
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """
    v7.7.0: `person_alpha_u8` (RAW A-roll in, alpha-guarded wall cleaner first); `None` = unchanged.

    Composites a sleek Squircle Picture-in-Picture Studio Window onto `canvas_bgr` in ~0.5ms!
    Frames `x_src = 200..870, y_src = 722..1598` (generous +80px headroom above rounded hair crown
    + full face + shoulders + mic) with zero cutout amputation, zero mid-air torso, and zero muddy halo!
    """
    op = _clamp(opacity, 0.0, 1.0)
    x0, y0, x1, y1 = pip_rect
    if op <= 0.005:
        return canvas_bgr, (float(x0), float(y0), float(x1), float(y1))

    H, W = canvas_bgr.shape[:2]
    pw, ph = x1 - x0, y1 - y0
    rig = _get_squircle_pip_rig(pw, ph, rx, rim_rgb)
    if person_alpha_u8 is not None:
        aroll_clean_bgr = _clean_wall_for_render(aroll_clean_bgr, person_alpha_u8, wall_cache_key)

    ah, aw = aroll_clean_bgr.shape[:2]
    sx_src, sy_src = aw / 1080.0, ah / 1920.0
    crop_w = (680.0 * sx_src) / max(0.85, float(inner_zoom))
    crop_h = (float(crop_h_1080p) * sy_src) / max(0.85, float(inner_zoom))
    cx_s = 534.0 * sx_src
    cy_s = float(cy_src_1080p) * sy_src
    sx0 = max(0, int(round(cx_s - crop_w * 0.5)))
    sy0 = max(0, int(round(cy_s - crop_h * 0.5)))
    sx1 = min(aw, int(round(cx_s + crop_w * 0.5)))
    sy1 = min(ah, int(round(cy_s + crop_h * 0.5)))

    portrait = cv2.resize(aroll_clean_bgr[sy0:sy1, sx0:sx1], (pw, ph), interpolation=cv2.INTER_AREA).astype(np.float32)
    portrait *= rig["inner_vig"]

    spad = rig["spad"]
    rx0, ry0 = max(0, x0 - spad), max(0, y0 - spad)
    rx1, ry1 = min(W, x1 + spad), min(H, y1 + spad)
    ox0, oy0 = rx0 - (x0 - spad), ry0 - (y0 - spad)
    ox1, oy1 = ox0 + (rx1 - rx0), oy0 + (ry1 - ry0)

    out = canvas_bgr.copy()
    roi = out[ry0:ry1, rx0:rx1].astype(np.float32)

    # 1. Soft ambient drop shadow + subtle outer jewel rim glow
    sh_a = rig["sh_alpha"][oy0:oy1, ox0:ox1] * op
    roi = roi * (1.0 - sh_a) + np.array([[[4.0, 4.0, 7.0]]], dtype=np.float32) * sh_a

    gl_a = rig["gl_alpha"][oy0:oy1, ox0:ox1] * op
    scr_b = roi * (1.0 / 255.0)
    scr_g = np.clip(gl_a * (rig["rim_bgr_col"] * (1.0 / 255.0)), 0.0, 0.85)
    roi = (1.0 - (1.0 - scr_b) * (1.0 - scr_g)) * 255.0

    # 2. Rounded Squircle portrait interior
    px_rel, py_rel = x0 - rx0, y0 - ry0
    sub_p = roi[py_rel : py_rel + ph, px_rel : px_rel + pw]
    pm = rig["mask_f"] * op
    roi[py_rel : py_rel + ph, px_rel : px_rel + pw] = sub_p * (1.0 - pm) + portrait * pm

    # 3. Crisp dual glass rim
    rp = rig["rpad"]
    ry_a, ry_b = py_rel - rp, py_rel + ph + rp
    rx_a, rx_b = px_rel - rp, px_rel + pw + rp
    if ry_a >= 0 and rx_a >= 0 and ry_b <= roi.shape[0] and rx_b <= roi.shape[1]:
        r_sub = roi[ry_a:ry_b, rx_a:rx_b]
        ra = rig["rim_a"] * op
        roi[ry_a:ry_b, rx_a:rx_b] = r_sub * (1.0 - ra) + rig["rim_bgr"] * ra

    out[ry0:ry1, rx0:rx1] = np.clip(roi + 0.5, 0.0, 255.0).astype(np.uint8)
    return out, (float(x0), float(y0), float(x1), float(y1))


# ==============================================================================
# 2B. HAIR-CROWN-SAFE STUDIO WALL CLEANER + OPTION B BOTTOM-FLUSH CUTOUT + VOICE GUARD (v7.3)
# ==============================================================================
_WALL_INPAINT_ROIS_V73: list[tuple[int, int, int, int, int, int, int, int]] = [
    (250, 742, 668, 868, 268, 760, 650, 853),    # 0: Full coat-rack LLLLLL + under-bar shadow (0% hair at y>=854 on low-head ref!)
    (700, 832, 812, 922, 712, 844, 798, 910),    # 1: Right wall black outlet across all camera pan positions
    (175, 1035, 330, 1158, 190, 1052, 315, 1142), # 2: Left white switch (dark sideburn hair protected!)
]
_K_DOME_OPEN = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 13))
_K_DOME_PAD = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
_WALL_GRAIN_V73 = np.random.default_rng(1808).normal(0.0, 0.75, (1920, 1080, 3)).astype(np.float32)
_CLEAN_WALL_CACHE_V73: dict[str, list[tuple[Any, ...]]] = {}
_REL_SUFFIX = "::rel"


def _wall_reference_entries(ref_low_head_bgr: np.ndarray, relative_outlier: bool) -> list[tuple[Any, ...]]:
    """Per-ROI Telea wall patches. `relative_outlier=False` is the v7.3 fixed 108/172 test (no-alpha path, unchanged);
    `True` flags `s_sum < 0.80 * median(ROI)` instead, so a dark wall (sum ~80) is not swallowed whole."""
    entries: list[tuple[Any, ...]] = []
    for idx, (rx0, ry0, rx1, ry1, fx0, fy0, fx1, fy1) in enumerate(_WALL_INPAINT_ROIS_V73):
        sub = np.ascontiguousarray(ref_low_head_bgr[ry0:ry1, rx0:rx1])
        msk = np.zeros(sub.shape[:2], dtype=np.uint8)
        msk[fy0 - ry0 : fy1 - ry0, fx0 - rx0 : fx1 - rx0] = 255
        s_sum = sub.astype(np.int16).sum(axis=2)
        if relative_outlier:
            low = s_sum < 0.80 * float(np.median(s_sum))
        else:
            low = (s_sum < 108) | (s_sum > 172)
        outlier = (low & (msk == 0)).astype(np.uint8) * 255
        msk_inp = cv2.bitwise_or(msk, outlier)
        inp = cv2.inpaint(sub, msk_inp, 7, cv2.INPAINT_TELEA).astype(np.float32) + _WALL_GRAIN_V73[ry0:ry1, rx0:rx1]
        ring_valid = msk_inp == 0
        ref_mean = sub[ring_valid].mean(axis=0).astype(np.float32) if np.any(ring_valid) else np.array([41.0, 54.0, 58.0], np.float32)
        alpha_base = cv2.GaussianBlur(msk.astype(np.float32) * (1.0 / 255.0), (0, 0), 3.8)
        entries.append((rx0, ry0, rx1, ry1, inp, ring_valid, ref_mean, alpha_base))
    return entries


def init_hair_safe_wall_reference(ref_low_head_bgr: np.ndarray, cache_key: str = "v73_studio_ref") -> None:
    """
    Builds the pure Telea wall reference patches once from a low-head reference frame
    (e.g. t=24.02s where hair crown is at y>=870, leaving a 17px pure-wall gap below the coat-rack!).
    v7.7.0: also builds the alpha-path variant under `cache_key + _REL_SUFFIX` (relative outlier test `s_sum < 0.80 * median(ROI)`).
    """
    if cache_key in _CLEAN_WALL_CACHE_V73:
        return
    _CLEAN_WALL_CACHE_V73[cache_key + _REL_SUFFIX] = _wall_reference_entries(ref_low_head_bgr, True)
    _CLEAN_WALL_CACHE_V73[cache_key] = _wall_reference_entries(ref_low_head_bgr, False)


def _clean_with_person_alpha(src_bgr: np.ndarray, person_alpha_u8: np.ndarray, entries: list[tuple[Any, ...]]) -> np.ndarray:
    """Alpha-guarded wall cleaner (port of project v2lib.clean_aroll_alpha): the person alpha replaces the dome / sideburn
    heuristics. Fixtures are replaced by the wall patch only where the (eroded, blurred) person alpha is ~0; the exposure
    delta comes from the wall ring outside `dilate(alpha >= 20, 15x15)` with no s_sum bounds. Inputs are not mutated."""
    H, W = src_bgr.shape[:2]
    alpha = person_alpha_u8 if person_alpha_u8.shape[:2] == (H, W) else cv2.resize(person_alpha_u8, (W, H), interpolation=cv2.INTER_LINEAR)
    out = src_bgr.copy()
    k5, k15 = np.ones((5, 5), np.uint8), np.ones((15, 15), np.uint8)
    for rx0, ry0, rx1, ry1, inp, ring_valid, ref_mean, alpha_base in entries:
        py0, py1, px0, px1 = max(0, ry0 - 16), min(H, ry1 + 16), max(0, rx0 - 16), min(W, rx1 + 16)
        a_pad = alpha[py0:py1, px0:px1]
        person_pad = cv2.GaussianBlur(cv2.erode((a_pad >= 150).astype(np.uint8), k5).astype(np.float32), (0, 0), 1.4)
        guard_pad = cv2.dilate((a_pad >= 20).astype(np.uint8), k15)
        sl = (slice(ry0 - py0, ry1 - py0), slice(rx0 - px0, rx1 - px0))
        person, guard = person_pad[sl], guard_pad[sl]
        sub = out[ry0:ry1, rx0:rx1]
        cur_valid = ring_valid & (guard == 0)
        delta = (sub[cur_valid].mean(axis=0).astype(np.float32) - ref_mean) if np.count_nonzero(cur_valid) > 40 else np.zeros(3, np.float32)
        patch_f = inp + delta[None, None, :]
        a3 = (alpha_base * (1.0 - person))[:, :, None]
        out[ry0:ry1, rx0:rx1] = np.clip(sub.astype(np.float32) * (1.0 - a3) + patch_f * a3 + 0.5, 0.0, 255.0).astype(np.uint8)
    return out


def clean_aroll_preserve_hair_crown(
    src_bgr: np.ndarray,
    *,
    cache_key: str = "v73_studio_ref",
    ema_state: dict[str, np.ndarray] | None = None,
    person_alpha_u8: np.ndarray | None = None,
) -> np.ndarray:
    """
    v7.7.0 `person_alpha_u8` (uint8 H x W, e.g. the RVM matte): switches to the alpha-guarded cleaner (no dome / `idx == 2`
    heuristics; the alpha is the hair guard, so it also works on dark walls). `None` keeps the path below exactly as before.

    Scale-Space Morphological Opening (`K_open = MORPH_ELLIPSE(15, 13)` at 1/2-res = 30x26px):
      - Erases 100% of thin stationary coat-rack prongs (5–8px) & rail (10–15px), right outlet, and left switch.
      - Preserves 100.0% of the speaker's convex rounded hair dome up to `y = 742` (`0px` horizontal flattening!)
        and protects dark left sideburns (`s_sum < 88`) on the left wall switch ROI!
    """
    if cache_key not in _CLEAN_WALL_CACHE_V73:
        init_hair_safe_wall_reference(src_bgr, cache_key=cache_key)
    if person_alpha_u8 is not None:
        return _clean_with_person_alpha(src_bgr, person_alpha_u8, _CLEAN_WALL_CACHE_V73[cache_key + _REL_SUFFIX])
    entries = _CLEAN_WALL_CACHE_V73[cache_key]

    H, W = src_bgr.shape[:2]
    out = src_bgr.copy()
    for idx, (rx0, ry0, rx1, ry1, inp, ring_valid, ref_mean, alpha_base) in enumerate(entries):
        sub = out[ry0:ry1, rx0:rx1]
        s_sum = sub.astype(np.int16).sum(axis=2)
        cur_valid = ring_valid & (s_sum >= 96) & (s_sum <= 172)
        delta = (sub[cur_valid].mean(axis=0).astype(np.float32) - ref_mean) if np.count_nonzero(cur_valid) > 40 else np.zeros(3, np.float32)
        patch_f = inp + delta[None, None, :]
        alpha = alpha_base.copy()

        if idx == 0:
            dy1 = min(H, 932)
            d_sum = src_bgr[ry0:dy1, rx0:rx1].astype(np.int16).sum(axis=2)
            dark_u8 = ((d_sum < 108).astype(np.uint8)) * 255
            dh, dw = dark_u8.shape[0] // 2, dark_u8.shape[1] // 2
            dark_h = (cv2.resize(dark_u8, (dw, dh), interpolation=cv2.INTER_AREA) >= 100).astype(np.uint8) * 255
            opened_h = cv2.morphologyEx(dark_h, cv2.MORPH_OPEN, _K_DOME_OPEN)

            n_lbl, lbls = cv2.connectedComponents(opened_h, connectivity=8)
            dome_h = np.zeros_like(opened_h, dtype=np.float32)
            if n_lbl > 1:
                anchor_lbls = np.unique(lbls[max(0, (880 - ry0) // 2) :, (320 - rx0) // 2 : (640 - rx0) // 2])
                for lb in anchor_lbls:
                    if lb > 0:
                        dome_h[lbls == lb] = 1.0
            dome_h = cv2.dilate(dome_h, _K_DOME_PAD, iterations=1)

            if ema_state is not None:
                prev = ema_state.get(cache_key)
                if prev is not None and prev.shape == dome_h.shape and float(np.mean(np.abs(dome_h - prev))) < 0.16:
                    dome_h = np.maximum(dome_h, 0.65 * dome_h + 0.35 * prev)
                ema_state[cache_key] = dome_h.copy()

            dome_full = cv2.resize(dome_h, (rx1 - rx0, dy1 - ry0), interpolation=cv2.INTER_LINEAR)[: (ry1 - ry0), :]
            hz = cv2.GaussianBlur(dome_full, (0, 0), 2.0) * np.clip((118.0 - s_sum.astype(np.float32)) / 18.0, 0.0, 1.0)
            hz = np.maximum(hz, (dome_full >= 0.55).astype(np.float32))
            alpha *= np.clip(1.0 - hz, 0.0, 1.0)
        elif idx == 2:
            # Left white wall switch: protect dark left sideburn hair if speaker leans left
            alpha *= np.clip((s_sum.astype(np.float32) - 86.0) / 24.0, 0.0, 1.0)

        a3 = alpha[:, :, None]
        out[ry0:ry1, rx0:rx1] = np.clip(sub.astype(np.float32) * (1.0 - a3) + patch_f * a3 + 0.5, 0.0, 255.0).astype(np.uint8)
    return out


def render_bottom_flush_cutout(
    canvas_bgr: np.ndarray,
    aroll_clean_bgr: np.ndarray,
    person_alpha_u8: np.ndarray,
    *,
    y_src_top: int = 735,
    cam_scale: float = 1.015,
    cam_dx: float = 0.0,
    rim_rgb: tuple[int, int, int] = (245, 196, 81),
    rim_strength: float = 0.70,
    aura_strength: float = 0.32,
    chest_scrim: bool = False,
    ground_vignette_strength: float = 0.54,
    ground_bgr: tuple[float, float, float] = (8.0, 7.0, 10.0),
    opacity: float = 1.0,
    clean_wall: bool = False,
    wall_cache_key: str = "v73_studio_ref",
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """
    v7.7.0: `clean_wall=True` treats `aroll_clean_bgr` as RAW and runs the alpha-guarded wall cleaner with `person_alpha_u8`.

    Option B Perfected — Full-Shoulders (`x = 0..1080` uncropped!), Hair-Crown-Safe (`y_src_top = 735`),
    Strictly Bottom-Flush (`y_bottom == H = 1920`, `0px` floating gap!) Speaker Cutout.
    """
    op = _clamp(opacity, 0.0, 1.0)
    H, W = canvas_bgr.shape[:2]
    sy, sx = H / 1920.0, W / 1080.0
    y_tl = max(0, int(round(float(y_src_top) * sy)))
    th = H - y_tl
    if op <= 0.005 or th <= 4:
        return canvas_bgr, (0.0, float(y_tl), float(W), float(H))

    ar_c = aroll_clean_bgr if aroll_clean_bgr.shape[:2] == (H, W) else cv2.resize(aroll_clean_bgr, (W, H), interpolation=cv2.INTER_AREA)
    pa_c = person_alpha_u8 if person_alpha_u8.shape[:2] == (H, W) else cv2.resize(person_alpha_u8, (W, H), interpolation=cv2.INTER_LINEAR)
    if clean_wall:
        ar_c = _clean_wall_for_render(ar_c, pa_c, wall_cache_key)

    sc = max(1.0, float(cam_scale))
    M = np.array(
        [
            [sc, 0.0, (1.0 - sc) * (W * 0.5) + float(cam_dx) * sx],
            [0.0, sc, (1.0 - sc) * float(H) - float(y_tl)],
        ],
        dtype=np.float32,
    )
    fg_sub = cv2.warpAffine(ar_c, M, (W, th), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    pa_sub = cv2.warpAffine(pa_c, M, (W, th), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32) * (1.0 / 255.0)

    pa_f = cv2.GaussianBlur(np.clip((pa_sub - 0.07) / 0.88, 0.0, 1.0), (5, 5), 0.9)
    pa_3 = pa_f[:, :, None]
    wall_bgr = np.array([[[42.0, 54.0, 58.0]]], dtype=np.float32)
    fringe = (pa_3 > 0.03) & (pa_3 < 0.88)
    fg_decontam = np.where(
        fringe,
        np.clip((fg_sub - wall_bgr * (1.0 - pa_3)) / np.maximum(pa_3, 0.28), 0.0, 240.0),
        fg_sub,
    )

    out = canvas_bgr.copy()
    bg_sub = out[y_tl:H, 0:W].astype(np.float32)
    rim_bgr = np.array([[[float(rim_rgb[2]), float(rim_rgb[1]), float(rim_rgb[0])]]], dtype=np.float32)

    if aura_strength > 0.01:
        pa_sm = cv2.resize(pa_f, (max(8, W // 4), max(8, th // 4)), interpolation=cv2.INTER_AREA)
        aura_sm = cv2.GaussianBlur(pa_sm, (0, 0), 9.5)
        aura_full = cv2.resize(aura_sm, (W, th), interpolation=cv2.INTER_LINEAR) * (1.0 - 0.92 * pa_f) * float(aura_strength) * op
        b_n = np.clip(bg_sub * (1.0 / 255.0), 0.0, 1.0)
        a_n = np.clip(aura_full[:, :, None] * (rim_bgr * (1.0 / 255.0)) * 1.35, 0.0, 0.85)
        bg_sub = (1.0 - (1.0 - b_n) * (1.0 - a_n)) * 255.0

    a_comp = pa_3 * op
    comp = bg_sub * (1.0 - a_comp) + fg_decontam * a_comp

    if rim_strength > 0.01:
        r_px = max(1, int(round(2.0 * sx)))
        pad = r_px + 2
        pa_pad = cv2.copyMakeBorder(pa_f, pad, pad, pad, pad, borderType=cv2.BORDER_REPLICATE)
        k_rim = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_px + 1, 2 * r_px + 1))
        dil_1 = cv2.dilate(pa_pad, k_rim, iterations=1)[pad : pad + th, pad : pad + W]
        raw_rim = np.clip(dil_1 - pa_f, 0.0, 1.0)

        xx = np.arange(W, dtype=np.float32)
        yy_abs = np.arange(y_tl, H, dtype=np.float32)
        bx_guard = np.minimum(np.clip((xx - 3.0) / (14.0 * sx), 0.0, 1.0), np.clip(((W - 4.0) - xx) / (14.0 * sx), 0.0, 1.0))
        by_rim = np.clip((1800.0 * sy - yy_abs) / max(1.0, 140.0 * sy), 0.0, 1.0)
        raw_rim *= by_rim[:, None] * bx_guard[None, :]

        rim_thread = (cv2.GaussianBlur(raw_rim, (3, 3), 0.8) + 0.32 * cv2.GaussianBlur(raw_rim, (7, 7), 1.9)) * float(rim_strength) * op
        c_n = np.clip(comp * (1.0 / 255.0), 0.0, 1.0)
        r_n = np.clip((rim_thread[:, :, None]) * (rim_bgr * (1.0 / 255.0)), 0.0, 0.88)
        comp = (1.0 - (1.0 - c_n) * (1.0 - r_n)) * 255.0

    yy_abs = np.arange(y_tl, H, dtype=np.float32)
    if chest_scrim:
        u_ch = np.clip((yy_abs - 1475.0 * sy) / max(1.0, 260.0 * sy), 0.0, 1.0)
        w_ch = (0.5 * (1.0 - np.cos(np.pi * u_ch)))[:, None, None] * 0.42 * op
        comp = comp * (1.0 - w_ch) + np.array([[[10.0, 9.0, 11.0]]], dtype=np.float32) * w_ch

    u_bot = np.clip((yy_abs - 1795.0 * sy) / max(1.0, 125.0 * sy), 0.0, 1.0)
    w_bot = (0.5 * (1.0 - np.cos(np.pi * u_bot)))[:, None, None] * op
    g_col = np.array([[list(ground_bgr)]], dtype=np.float32)
    vig_w = w_bot * (0.28 + float(ground_vignette_strength) * 0.72 * pa_3)
    comp = comp * (1.0 - vig_w) + g_col * vig_w

    out[y_tl:H, 0:W] = np.clip(comp + 0.5, 0.0, 255.0).astype(np.uint8)
    return out, (340.0 * sx, 820.0 * sy, 730.0 * sx, 1410.0 * sy)


# ==============================================================================
# 2C. LOOK S "POP-OUT" STUDIO CARD (v7.7.0, A/B flag `LOOK_S_POPOUT`): the head crown rises above a rounded light card
# ==============================================================================
LOOK_S_POPOUT: bool = os.environ.get("PFD_LOOK_S_POPOUT", "").strip().lower() in ("1", "true", "yes", "on")
_POPOUT_RIG_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_PLAYFAIR_IT_NAMES = ("PlayfairDisplay-Italic-Variable.ttf", "PlayfairDisplay-Italic[wght].ttf")


def _smooth01(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / max(e1 - e0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _fontconfig_playfair_italic() -> Path | None:
    """Playfair Display Italic via fontconfig (`fc-list`), or None (no fontconfig, no match, or only upright faces)."""
    try:
        pr = subprocess.run(["fc-list", ":family=Playfair Display", "file", "style"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in sorted(pr.stdout.splitlines()):
        path, _, style = line.partition(":")
        if "italic" in style.lower() and Path(path.strip()).is_file():
            return Path(path.strip())
    return None


def _find_playfair_italic() -> Path:
    """Installed Playfair Display Italic only (env `PFD_FONT_DIR`, then the user font folders, then fontconfig with a loud
    WARNING). Never a download, never a silent substitute font."""
    home = Path.home() / ".local" / "share" / "fonts"
    roots = ([Path(os.environ["PFD_FONT_DIR"]).expanduser()] if os.environ.get("PFD_FONT_DIR") else []) + [
        home, home / "PR_Fonts", home / "tnedit", home / "TNEDIT_DViet" / "Lien_ket_thu_vien_co_san"]
    for root in roots:
        for name in _PLAYFAIR_IT_NAMES:
            if (root / name).is_file():
                return root / name
    fc = _fontconfig_playfair_italic()
    if fc is not None:
        print(f"WARNING: Playfair Display Italic not found in {[str(r) for r in roots]}; using the fontconfig match {fc} "
              "(set PFD_FONT_DIR to pin the font file).", file=sys.stderr)
        return fc
    raise FileNotFoundError(f"Playfair Display Italic not installed (looked for {_PLAYFAIR_IT_NAMES} in {[str(r) for r in roots]} "
                            "and via fontconfig `fc-list :family=\"Playfair Display\"`)")


def render_lavender_paper(
    W: int = 1080, H: int = 1920, *, tint_rgb: tuple[int, int, int] = (250, 228, 253), seed_glow_y: float = 0.40,
) -> np.ndarray:
    """Light lavender / white paper (BGR uint8): tinted core around `seed_glow_y` (fraction of H), white at the bottom."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ny, nx = yy / H, (xx - W * 0.5) / (W * 0.5)
    core = np.exp(-(((ny - seed_glow_y) / 0.32) ** 2 + (nx / 1.25) ** 2))
    top = _smooth01(0.0, 0.25, ny)  # very top slightly greyer (status-bar scrim look)
    t = np.clip(core * 0.95 + 0.12 * top, 0.0, 1.0)[:, :, None]
    rgb = np.array([255.0, 255.0, 255.0], np.float32) * (1.0 - t) + np.array(tint_rgb, np.float32) * t
    return np.ascontiguousarray(rgb[:, :, ::-1]).clip(0, 255).astype(np.uint8)


def _fit_italic(font_path: Path, weight: str, text: str, target_w: int):
    from PIL import ImageFont

    def load(sz: int):
        f = ImageFont.truetype(str(font_path), sz)
        try:
            f.set_variation_by_name(weight)
        except Exception:  # static font or unknown axis name: keep the default instance
            pass
        return f

    size = 100
    for _ in range(3):  # converge on target_w
        bb = load(size).getbbox(text)
        size = max(8, int(size * target_w / max(bb[2] - bb[0], 1)))
    return load(size)


def render_gradient_italic_headline(
    backdrop_bgr: np.ndarray,
    text: str,
    sub: str | None = None,
    center_xy: tuple[float, float] = (540, 690),
    target_w: int = 860,
    top_rgb: tuple[int, int, int] = (124, 104, 238),
    bottom_rgb: tuple[int, int, int] = (252, 246, 255),
    fade_start: float = 0.30,
    *,
    sub_rgb: tuple[int, int, int] = (150, 118, 168),
    sub_size: int = 58,
    sub_dxy: tuple[int, int] = (-300, 150),
    weight: str = "Medium Italic",
    font_path: str | Path | None = None,
) -> np.ndarray:
    """Big Playfair Display Italic headline with a vertical colour gradient (`top_rgb` -> `bottom_rgb` after `fade_start`,
    fraction of the glyph height) over the backdrop, plus an optional small `sub` word. Returns a new BGR uint8 frame.
    Text is NFC-normalised first (Vietnamese diacritics from NFD sources would otherwise draw as detached combining marks)."""
    from PIL import ImageFont

    text = unicodedata.normalize("NFC", text)
    sub = unicodedata.normalize("NFC", sub) if sub else sub
    H, W = backdrop_bgr.shape[:2]
    fp = Path(font_path) if font_path else _find_playfair_italic()
    f = _fit_italic(fp, weight, text, target_w)
    l, t, r, b = f.getbbox(text)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).text((center_xy[0] - (l + r) / 2, center_xy[1] - (t + b) / 2), text, font=f, fill=255)
    a = np.asarray(m, np.float32) / 255.0
    ys = np.where(a.max(1) > 0.05)[0]
    y0, y1 = (ys.min(), ys.max()) if ys.size else (0, 1)
    u = np.clip((np.arange(H, dtype=np.float32) - y0) / max(y1 - y0, 1), 0.0, 1.0)
    g = _smooth01(fade_start, 1.0, u)[:, None, None]
    col = (np.array(top_rgb, np.float32) * (1.0 - g) + np.array(bottom_rgb, np.float32) * g)[:, :, ::-1]
    out = backdrop_bgr.astype(np.float32) * (1.0 - a[:, :, None]) + col * a[:, :, None]
    if sub:
        fs = ImageFont.truetype(str(fp), int(sub_size))
        try:
            fs.set_variation_by_name(weight)
        except Exception:
            pass
        ms = Image.new("L", (W, H), 0)
        ImageDraw.Draw(ms).text((center_xy[0] + sub_dxy[0], center_xy[1] + sub_dxy[1]), sub, font=fs, fill=255)
        s3 = (np.asarray(ms, np.float32) / 255.0)[:, :, None]
        out = out * (1.0 - s3) + np.array(sub_rgb[::-1], np.float32) * s3
    return np.clip(out + 0.5, 0.0, 255.0).astype(np.uint8)


def _get_popout_rig(
    W: int, H: int, card_rect: tuple[int, int, int, int], rx: int, bulge: float, sag: float,
    edge_feather: float, edge_blur: float, shadow_dy: int, shadow_sigma: float, pad: int,
) -> dict[str, Any]:
    """Card mask, bulge/sag remap maps, soft alpha, edge-blur band and shadow field: all independent of the frame, cached."""
    key = (W, H, tuple(card_rect), rx, bulge, sag, edge_feather, edge_blur, shadow_dy, shadow_sigma, pad)
    hit = _POPOUT_RIG_CACHE.get(key)
    if hit is not None:
        return hit
    x0, y0, x1, y1 = card_rect
    cw, ch = x1 - x0, y1 - y0
    rx0, ry0, rx1, ry1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    rw, rh = rx1 - rx0, ry1 - ry0
    ss = 2
    m_hi = Image.new("L", (rw * ss, rh * ss), 0)
    ImageDraw.Draw(m_hi).rounded_rectangle(
        [(x0 - rx0) * ss, (y0 - ry0) * ss, (x1 - rx0) * ss - 1, (y1 - ry0) * ss - 1], radius=rx * ss, fill=255)
    mask = np.asarray(m_hi.resize((rw, rh), Image.Resampling.LANCZOS), np.float32) / 255.0
    yy, xx = np.mgrid[0:rh, 0:rw].astype(np.float32)
    cx, cy = (x0 + x1) * 0.5 - rx0, (y0 + y1) * 0.5 - ry0
    hw, hh = cw * 0.5, ch * 0.5
    u, v = (xx - cx) / hw, (yy - cy) / hh
    wb = _smooth01(-0.15, 1.0, v)                          # weight grows toward the bottom edge
    src_u = u / (1.0 + bulge * wb)                         # outward pillow (sample from nearer the centre)
    src_v = v - sag * wb * np.clip(1.0 - u * u, 0.0, 1.0)  # centre of the bottom edge sags
    mx, my = (src_u * hw + cx).astype(np.float32), (src_v * hh + cy).astype(np.float32)
    mask_w = cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    k = max(1, int(edge_feather))
    er = cv2.erode(mask_w, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    card_a = cv2.GaussianBlur(er, (0, 0), edge_feather) if edge_feather > 0.1 else mask_w
    band = None
    if edge_blur > 0.1:
        band = np.clip(1.0 - cv2.GaussianBlur(er, (0, 0), edge_feather * 1.8), 0.0, 1.0)
        band = (band * (card_a > 0.01))[:, :, None]
    shadow = cv2.GaussianBlur(np.roll(mask_w, shadow_dy, axis=0), (0, 0), shadow_sigma)[:, :, None]
    rig = {"roi": (rx0, ry0, rx1, ry1), "mx": mx, "my": my, "mask_w": mask_w, "card_a": card_a[:, :, None],
           "band": band, "shadow": shadow}
    _POPOUT_RIG_CACHE[key] = rig
    return rig


def _decontaminate_crown(photo: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Alpha-weighted despill of the cut-out edge: where the matte is partial (< ~0.98) the colour is pulled from the opaque
    interior (normalised blur of the alpha >= 0.95 core, sigma 7), so the grey wall mixed into the RVM fringe never shows."""
    core = (a >= 0.95).astype(np.float32)
    den = cv2.GaussianBlur(core, (0, 0), 7.0)
    num = cv2.GaussianBlur(photo * core[:, :, None], (0, 0), 7.0)
    fill = num / np.maximum(den, 1e-3)[:, :, None]
    k = ((1.0 - _smooth01(0.60, 0.98, a)) * (den > 0.02))[:, :, None]
    return photo * (1.0 - k) + fill * k


def _unsharp(img_f32: np.ndarray, amount: float, sigma: float) -> np.ndarray:
    """Classic unsharp mask on a float32 BGR array (clipped to 0..255). No detail is invented: it only restores the edge contrast
    that the Lanczos upscale of a 720p source flattens."""
    if amount <= 0.0:
        return img_f32
    return np.clip(img_f32 + amount * (img_f32 - cv2.GaussianBlur(img_f32, (0, 0), sigma)), 0.0, 255.0)


SHARPEN2_SIGMA = 2.0   # [UOC] optional second USM pass (sharpen2_amount > 0): wider radius, gentler, for the face-Laplacian gate
SOURCE_BAND_DARK = 0.6       # [UOC] a source edge column / row under 60 % of the wall level is a dark band (v4: luma 6-12 vs 45 [DO])
SOURCE_BAND_MAX_FRAC = 0.15  # [UOC] bands are searched in the outer 15 % of each side only
SPECK_DARK = 28.0            # [UOC] a wall pixel this far under its local median is a speck candidate (same as motion_gate)
SPECK_MAX_AREA = 2500        # [UOC] px at output scale; larger dark shapes are real wall content and stay


def _orient(a: np.ndarray, side: str) -> np.ndarray:
    """View of `a` with the `side` edge at column 0 (writable when `a` is)."""
    v = a if side in ("left", "right") else a.swapaxes(0, 1)
    return v[:, ::-1] if side in ("right", "bottom") else v


def _clean_source_bands(src_bgr: np.ndarray, person_alpha_u8: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
    """Paint dark source edge bands (letterbox, dark wall edge) with the adjacent clean wall, person pixels untouched.
    A band = the outer columns (rows) of a side, inside SOURCE_BAND_MAX_FRAC, whose wall-only median luma is < SOURCE_BAND_DARK of the
    wall just inside it. Returns (new array or the input when clean, {side: band px}). v4 K2: source x 24-72 of 720 at luma 6-12."""
    g = cv2.cvtColor(src_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    wall = person_alpha_u8 < 128
    out, bands = None, {}
    for side in ("left", "right", "top", "bottom"):
        go, wo = _orient(g, side), _orient(wall, side)
        n = max(4, int(go.shape[1] * SOURCE_BAND_MAX_FRAC))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.where(wo[::4, :2 * n], go[::4, :2 * n], np.nan), axis=0)
            ref = float(np.nanmedian(med[n:]))
        dark = np.nan_to_num(med[:n], nan=1e9) < SOURCE_BAND_DARK * ref if np.isfinite(ref) and ref >= 20.0 else np.zeros(n, bool)
        idx = np.where(dark)[0]
        w = int(idx[-1]) + 1 if idx.size and dark[:idx[-1] + 1].mean() >= 0.6 else 0
        bands[side] = w
        if w:
            out = src_bgr.copy() if out is None else out
            oo = _orient(out, side)
            fill = np.median(oo[:, w + 2:w + 26].astype(np.float32), axis=1)                     # per-row clean wall colour
            fill = cv2.GaussianBlur(fill[:, None, :], (0, 0), sigmaX=0.1, sigmaY=9.0)[:, 0, :]
            m = _orient(wall, side)[:, :w + 2]
            oo[:, :w + 2][m] = np.broadcast_to(np.clip(fill + 0.5, 0, 255).astype(np.uint8)[:, None, :], oo[:, :w + 2].shape)[m]
    return (src_bgr if out is None else out), bands


def _despeckle_wall(photo_f32: np.ndarray, person_a: np.ndarray) -> np.ndarray:
    """Fill small dark blobs on the wall (outside the person alpha dilated 25 px) with the local median (half-res, 31 px window).
    v4 K2: a 17x14 px dark dot (wall-fixture cleaner leftover) at the card's top right. Returns the input when nothing is found."""
    u8 = np.clip(photo_f32 + 0.5, 0, 255).astype(np.uint8)
    g = cv2.cvtColor(u8, cv2.COLOR_BGR2GRAY)
    hw = (g.shape[1], g.shape[0])
    small = cv2.resize(u8, (max(1, hw[0] // 2), max(1, hw[1] // 2)), interpolation=cv2.INTER_AREA)
    med_g = cv2.resize(cv2.medianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 31), hw, interpolation=cv2.INTER_LINEAR)
    cand = (med_g.astype(np.int16) - g.astype(np.int16)) > SPECK_DARK
    cand &= cv2.dilate((person_a > 0.05).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))) == 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    ids = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] <= SPECK_MAX_AREA]
    if not ids:
        return photo_f32
    m = cv2.dilate(np.isin(lab, ids).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    fill = cv2.resize(cv2.medianBlur(small, 31), hw, interpolation=cv2.INTER_LINEAR).astype(np.float32)
    out = photo_f32.copy()
    out[m] = fill[m]
    return out


def _guided_filter(I: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """He et al. grey guided filter (box filters only, no opencv-contrib)."""
    k = (2 * r + 1, 2 * r + 1)
    box = lambda x: cv2.boxFilter(x, -1, k, borderType=cv2.BORDER_REFLECT)  # noqa: E731
    mI, mp = box(I), box(p)
    a = (box(I * p) - mI * mp) / (box(I * I) - mI * mI + eps)
    b = mp - a * mI
    return box(a) * I + box(b)


def _refine_crown(a: np.ndarray, photo: np.ndarray, r: int, eps: float, contrast: tuple[float, float]) -> np.ndarray:
    """Crown matte refine: guided filter with the sharpened photo as guide (the low-res / 30 fps RVM stair steps follow the real hair
    edge), then an edge-contrast smoothstep (`contrast`) so no grey halo band is left. v4 K4: crown edge soft over 10-14 px."""
    I = cv2.cvtColor(np.clip(photo, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    q = np.clip(_guided_filter(I, a.astype(np.float32), int(r), float(eps)), 0.0, 1.0)
    return _smooth01(float(contrast[0]), float(contrast[1]), q)


def render_popout_studio_card(
    backdrop_bgr: np.ndarray,
    aroll_bgr: np.ndarray,
    person_alpha_u8: np.ndarray,
    *,
    card_rect: tuple[int, int, int, int] = (70, 1065, 1010, 1705),
    rx: int = 64,
    head_anchor: tuple[float, float] = (340.0, 549.0),   # crown top in SOURCE px
    head_out_xy: tuple[float, float] = (540.0, 900.0),   # crown top in OUTPUT px (pop_height = card_y0 - head_out_y = 165, 8.6 % of H)
    photo_scale: float = 1.36,
    pop_feather: float = 46.0,       # px below the card top where the cut-out fades back into the card (seam hide)
    pop_alpha_feather: float = 0.6,  # px gaussian on the person alpha (hair edge softness; 1.3 before v7.8.0)
    pop_alpha_choke: int = 1,        # px erode on the person alpha (RVM fringe; the colour is also decontaminated; 2 before v7.8.0)
    edge_feather: float = 1.6,       # px gaussian on the card alpha: [DO] 10-90 % edge rise 4-5 px (was 19-21 px at 7.0)
    edge_blur: float = 0.0,          # px blur of the photo inside the edge band; <= 0.1 skips the band entirely
    bulge: float = 0.03,             # outward pillow of the bottom half (fraction of half-width): [DO] side bow +28 px -> +11 px
    sag: float = 0.015,              # bottom edge drop at the centre (fraction of half-height)
    rim_px: int = 0,
    rim_alpha: float = 0.0,
    shadow_rgb: tuple[int, int, int] = (110, 80, 150),
    shadow_alpha: float = 0.16,
    shadow_dy: int = 22,
    shadow_sigma: float = 26.0,
    pad: int = 150,
    sharpen: float = 0.7,            # USM amount on the shared PHOTO array only (never the paper or the matte)
    sharp_sigma: float = 1.3,
    sharpen2_amount: float = 0.0,    # optional second USM pass (sigma SHARPEN2_SIGMA); 0.35 is the tested value
    alpha_curve: tuple[float, float] | None = None,   # optional smoothstep (lo, hi) on the RVM alpha, e.g. (0.25, 0.75), to shrink a crown halo
    clean_source_bands: bool = True,  # v7.9.0: paint dark source side bands (letterbox / dark wall edge) with the clean wall
    despeckle_wall: bool = True,      # v7.9.0: fill small dark wall specks inside the card
    crown_refine: bool = True,        # v7.9.0: guided-filter + edge-contrast crown matte (False = the v7.8.0 matte)
    crown_guided_r: int = 8,
    crown_guided_eps: float = 1e-3,
    crown_contrast: tuple[float, float] = (0.25, 0.75),
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Look S pop-out card (A/B flag `LOOK_S_POPOUT`, see `render_studio_card_ab`): a rounded light card (crisp edge, bottom-weighted
    pillow bulge + sag, lavender shadow) holds the A-roll; the speaker's head crown rises ABOVE the card top by
    `card_y0 - head_out_y` px. Card photo and cut-out share ONE affine AND ONE sharpened photo array, so the head seam is invisible.
    `person_alpha_u8` is the RVM matte in SOURCE geometry (uint8 H x W). Inputs are not mutated. Returns (BGR uint8, meta) with
    meta = {card_rect, pop_height_px, pop_bbox_y, photo_scale}.

    v7.8.0 (crisp pop-out): defaults retuned on the real S09 frames [DO] (card edge 19-21 px -> 4-5 px, face Laplacian 4.2-5.7 ->
    9.9-13.5 vs 6.0 for the plain Lanczos source); photo warp and bulge remap use INTER_LANCZOS4; one unsharp pass (`sharpen`,
    `sharp_sigma`) on the photo BEFORE both the card remap and the crown cut-out; the blur band is skipped when `edge_blur <= 0.1`.
    No neural super-resolution is used or claimed: this is Lanczos + a controlled unsharp. All old keyword arguments still work.

    v7.9.0 (v4 K2 / K4): dark source edge bands are painted with the adjacent wall before the warp (meta `source_bands_px`), small dark
    wall specks inside the card are filled, `card_src_rect` / `card_outside_source` report where the card samples the source (outside =
    reflected border), and the crown matte is refined (`crown_refine`). Gates: motion_gate.popout_inner_edge_dark_strip_px <= 4 px,
    card_dark_speck_count == 0, crown_edge_metrics(meta['crown_alpha']) jaggedness <= 1.2 px and rise <= 4 px.
    """
    H, W = backdrop_bgr.shape[:2]
    x0, y0, x1, y1 = card_rect
    sx, sy = head_anchor
    ox, oy = head_out_xy
    M = np.array([[photo_scale, 0.0, ox - photo_scale * sx], [0.0, photo_scale, oy - photo_scale * sy]], np.float32)
    src, bands = (_clean_source_bands(aroll_bgr, person_alpha_u8) if clean_source_bands
                  else (aroll_bgr, {"left": 0, "right": 0, "top": 0, "bottom": 0}))
    photo = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)
    photo = _unsharp(photo, sharpen, sharp_sigma)
    if sharpen2_amount > 0.0:
        photo = _unsharp(photo, sharpen2_amount, SHARPEN2_SIGMA)
    al = cv2.warpAffine(person_alpha_u8, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(np.float32) / 255.0
    if alpha_curve is not None:
        al = _smooth01(float(alpha_curve[0]), float(alpha_curve[1]), al)

    rig = _get_popout_rig(W, H, card_rect, rx, bulge, sag, edge_feather, edge_blur, shadow_dy, shadow_sigma, pad)
    rx0, ry0, rx1, ry1 = rig["roi"]
    if despeckle_wall:
        photo[ry0:ry1, rx0:rx1] = _despeckle_wall(photo[ry0:ry1, rx0:rx1], al[ry0:ry1, rx0:rx1])
    photo_roi = cv2.remap(photo[ry0:ry1, rx0:rx1], rig["mx"], rig["my"], cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)
    if edge_blur > 0.1 and rig["band"] is not None:
        photo_roi = photo_roi * (1.0 - rig["band"]) + cv2.GaussianBlur(photo_roi, (0, 0), edge_blur) * rig["band"]

    out = backdrop_bgr.astype(np.float32)
    roi = out[ry0:ry1, rx0:rx1]
    sh = rig["shadow"] * shadow_alpha
    roi = roi * (1.0 - sh) + np.array(shadow_rgb[::-1], np.float32) * sh
    roi = roi * (1.0 - rig["card_a"]) + photo_roi * rig["card_a"]
    if rim_px > 0 and rim_alpha > 0:
        inner = cv2.erode(rig["mask_w"], cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rim_px + 1, 2 * rim_px + 1)))
        rim = np.clip(rig["mask_w"] - inner, 0.0, 1.0)[:, :, None] * rim_alpha
        roi = roi * (1.0 - rim) + 255.0 * rim
    out[ry0:ry1, rx0:rx1] = roi

    # HEAD-OUT: person cut-out above the card top edge, fading into the card below it (only the rows that can show it)
    y_hi = int(min(H, math.ceil(y0 + pop_feather) + 4))
    rows = np.where(al[:y_hi].max(axis=1) > 0.0)[0]
    if rows.size:
        r0 = max(0, int(rows.min()) - 24)
        a_c, ph_c = al[r0:y_hi], photo[r0:y_hi]
        if crown_refine:
            a_c = _refine_crown(a_c, ph_c, crown_guided_r, crown_guided_eps, crown_contrast)
        a = a_c
        if pop_alpha_choke > 0:
            a = cv2.erode(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * pop_alpha_choke + 1, 2 * pop_alpha_choke + 1)))
        if pop_alpha_feather > 0.05:
            a = cv2.GaussianBlur(a, (0, 0), pop_alpha_feather)
        ramp = 1.0 - _smooth01(y0 - 2.0, y0 + pop_feather, np.arange(r0, y_hi, dtype=np.float32))
        pop_a = (a * ramp[:, None])[:, :, None]
        out[r0:y_hi] = out[r0:y_hi] * (1.0 - pop_a) + _decontaminate_crown(ph_c, a_c) * pop_a
        crown = np.clip(pop_a[:max(0, y0 - r0), :, 0] * 255.0 + 0.5, 0, 255).astype(np.uint8)
    else:
        crown = np.zeros((0, W), np.uint8)

    sh_, sw_ = aroll_bgr.shape[:2]
    src_rect = tuple(round(float(v), 1) for v in ((x0 - M[0, 2]) / photo_scale, (y0 - M[1, 2]) / photo_scale,
                                                    (x1 - M[0, 2]) / photo_scale, (y1 - M[1, 2]) / photo_scale))
    meta = {"card_rect": tuple(card_rect), "pop_height_px": float(y0 - oy), "photo_scale": float(photo_scale),
            "pop_bbox_y": (float(oy), float(y0 + pop_feather)), "source_bands_px": bands, "card_src_rect": src_rect,
            "card_outside_source": bool(src_rect[0] < 0 or src_rect[1] < 0 or src_rect[2] > sw_ or src_rect[3] > sh_),
            "crown_alpha": crown}
    return np.clip(out + 0.5, 0.0, 255.0).astype(np.uint8), meta


# ---------------------------------------------------------------------------------------------------------------------
# 2D. v7.8.0 PRODUCT STAGE: bottom-anchored B-roll reframe with a cap-top-anchored zoom, glint sweep and snap punch.
#     The stage keeps the TOP of the frame free for text / the 'phía dưới' card trio; the product only ever grows DOWNWARD.
# ---------------------------------------------------------------------------------------------------------------------
STAGE_S_DEFAULT = 0.72
CAP_TOP_SRC_FRAC = 0.0545        # [DO] cap top as a fraction of the SOURCE frame height (v3 macro): 613 px of 1920 at s=0.72
STAGE_FILL_SIGMA = 30.0          # [DO] blur of the replicate-filled extension above the product
STAGE_FEATHER_PX = 160           # feather length of the blur -> product transition
STAGE_TEXT_TOP_FRAC = 0.05       # [UOC] text band starts 5 % below the frame top
STAGE_TEXT_GAP_PX = 20           # [UOC] clear gap between the text band and the cap top
STAGE_SIDE_MARGIN_FRAC = 0.14    # [UOC] product silhouette lies inside x = 14 %..86 % of the width (bottle + shoulder)


def stage_geometry(s: float = STAGE_S_DEFAULT, W: int = 1080, H: int = 1920) -> dict[str, Any]:
    """Layout numbers of `render_product_stage(..., s)` at zoom 1.0 so a planner can place text without rendering.
    `cap_top_y` [DO 613 at s=0.72, 0.32 H]; `text_band` = (y0, y1) is product-safe (cap top minus `STAGE_TEXT_GAP_PX`);
    `product_bbox` = (x0, y0, x1, y1) conservative silhouette box [UOC]. Zooms are anchored at `cap_top_y`, so the band never changes."""
    cap = H * (1.0 - s * (1.0 - CAP_TOP_SRC_FRAC))
    cap_i = int(round(cap))
    m = int(round(W * STAGE_SIDE_MARGIN_FRAC))
    return {"s": float(s), "cap_top_y": cap_i,
            "text_band": (int(round(H * STAGE_TEXT_TOP_FRAC)), cap_i - STAGE_TEXT_GAP_PX),
            "product_bbox": (m, cap_i, W - m, H)}


def render_product_stage(
    frame_bgr: np.ndarray,
    s: float = STAGE_S_DEFAULT,
    cx: float = 0.5,
    zoom: float = 1.0,
    cap_anchor_y: float | None = None,
    *,
    out_size: tuple[int, int] = (1080, 1920),
) -> np.ndarray:
    """Bottom-anchored reframe of a 16:9 or 9:16 B-roll frame -> 1080x1920 BGR uint8.

    The product layer is `s` of the full output height (16:9: source height -> s*H, width cropped around `cx`; a portrait source is
    never scaled below full width). The space above it is `cv2.BORDER_REPLICATE` + Gaussian blur (sigma `STAGE_FILL_SIGMA`)
    feathered over ~`STAGE_FEATHER_PX` px. `zoom` (>= 1) is anchored at the cap top: the row `cap_anchor_y` (default
    `stage_geometry(s)['cap_top_y']`, [DO] ~0.32 H at s=0.72) maps to the same output row for every zoom, so the product grows
    downward and never enters the text band. Pure OpenCV; the input is not mutated."""
    Wo, Ho = out_size
    h, w = frame_bgr.shape[:2]
    S0 = max(Ho * s / h, Wo / w)
    geo = stage_geometry(s, Wo, Ho)
    cap_y = float(geo["cap_top_y"] if cap_anchor_y is None else cap_anchor_y)
    ty0 = Ho - h * S0                                    # top edge of the source layer at zoom 1 (bottom anchored)
    y_c = (cap_y - ty0) / S0                             # source row that sits on the anchor row
    S = S0 * max(float(zoom), 1e-3)
    ty = cap_y - y_c * S
    tx = Wo / 2.0 - cx * w * S
    M = np.array([[S, 0.0, tx], [0.0, S, ty]], np.float32)
    img = cv2.warpAffine(frame_bgr, M, (Wo, Ho), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    top = int(max(0.0, ty))
    if top > 0:
        end = ty + min(STAGE_FEATHER_PX - 90.0, 0.9 * max(cap_y - ty, 1.0))     # fully clean again before the cap top
        a = np.clip((end - np.arange(Ho, dtype=np.float32)) / float(STAGE_FEATHER_PX), 0.0, 1.0)[:, None, None]
        img = (img.astype(np.float32) * (1.0 - a) + cv2.GaussianBlur(img, (0, 0), STAGE_FILL_SIGMA).astype(np.float32) * a)
        img = np.clip(img + 0.5, 0, 255).astype(np.uint8)
    return img


_GLINT_GRID_CACHE: dict[tuple[int, int, float], np.ndarray] = {}


def glint_sweep(
    frame_bgr: np.ndarray,
    t01: float,
    amount: float = 0.25,
    angle_deg: float = 22.0,
    width_px: float = 150.0,
    mask_luma: tuple[float, float] = (0.10, 0.45),
) -> np.ndarray:
    """Soft warm light band sweeping left -> right at `angle_deg`, additive SCREEN blend weighted by the source luminance
    (smoothstep `mask_luma`) so only the glass lights up and the dark stage stays calm. `t01` in (0, 1) is the sweep progress
    (smoothstep eased); outside it the frame is returned untouched. [UOC] amount 0.22-0.30; 0.32 was already flickery
    (mean frame diff 4.25, p90 9.9) and 0.55 is flicker-prone. Returns a new array."""
    if t01 <= 0.0 or t01 >= 1.0 or amount <= 0.0:
        return frame_bgr
    Hh, Ww = frame_bgr.shape[:2]
    key = (Hh, Ww, float(angle_deg))
    p = _GLINT_GRID_CACHE.get(key)
    if p is None:
        yy, xx = np.mgrid[0:Hh, 0:Ww].astype(np.float32)
        a = math.radians(angle_deg)
        p = xx * math.cos(a) + yy * math.sin(a)
        _GLINT_GRID_CACHE[key] = p
    pmin, pmax = -2.0 * width_px, Ww * math.cos(math.radians(angle_deg)) + Hh * math.sin(math.radians(angle_deg)) + 2.0 * width_px
    e = t01 * t01 * (3.0 - 2.0 * t01)
    band = np.exp(-(((p - (pmin + (pmax - pmin) * e)) / width_px) ** 2))
    f = frame_bgr.astype(np.float32) / 255.0
    wgt = _smooth01(mask_luma[0], mask_luma[1], f.mean(axis=2))
    add = (amount * band * wgt)[:, :, None] * np.array([0.80, 0.93, 1.0], np.float32)[None, None, :]    # warm (BGR)
    return np.clip((1.0 - (1.0 - f) * (1.0 - add)) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def snap_punch(
    frame_bgr: np.ndarray,
    zoom: float,
    anchor_xy: tuple[float, float] = (540.0, 613.0),
    flash: float = 0.0,
    flash_bgr: tuple[int, int, int] = (200, 235, 255),
    max_mean_luma: float | None = 220.0,
) -> np.ndarray:
    """Anchored snap punch: scale by `zoom` about `anchor_xy` (so the anchor row, e.g. the cap top, stays put) and add a gold-white
    flash of strength `flash` (peak 0.28 [UOC]). Drive `zoom` 1.00 -> 1.10 over ~67 ms (2 frames) and `flash` over 3 frames.
    v7.9.0: the flash is scaled down so the frame mean luma never exceeds `max_mean_luma` (photosensitivity cap 220; None = off)."""
    h, w = frame_bgr.shape[:2]
    ax, ay = anchor_xy
    M = np.array([[zoom, 0.0, ax - zoom * ax], [0.0, zoom, ay - zoom * ay]], np.float32)
    out = cv2.warpAffine(frame_bgr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE) if zoom != 1.0 else frame_bgr
    if flash > 0.0:
        f = out.astype(np.float32) / 255.0
        lit = lambda k: np.clip((1.0 - (1.0 - f) * (1.0 - k * np.array(flash_bgr, np.float32) / 255.0)) * 255.0 + 0.5, 0, 255).astype(np.uint8)  # noqa: E731
        res = lit(flash)
        if max_mean_luma is not None:
            luma = lambda im: float(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).mean())  # noqa: E731
            m0, m1 = luma(out), luma(res)
            if m1 > max_mean_luma:   # screen blend is linear in k: scale the flash onto the cap
                res = lit(flash * max(0.0, max_mean_luma - 0.5 - m0) / max(m1 - m0, 1e-6)) if m0 < max_mean_luma else out
        out = res
    return out


def render_studio_card_ab(
    backdrop_bgr: np.ndarray,
    aroll_bgr: np.ndarray,
    person_alpha_u8: np.ndarray | None = None,
    *,
    popout: bool | None = None,
    **kwargs: Any,
) -> tuple[np.ndarray, Any]:
    """A/B switch 'Look S pop-out'. `popout=None` follows `LOOK_S_POPOUT` (default OFF, env `PFD_LOOK_S_POPOUT=1`).
    OFF -> `render_full_head_studio_card(backdrop, aroll, **kwargs)` untouched (bit-identical rounded card, returns its bbox);
    ON -> `render_popout_studio_card(backdrop, aroll, person_alpha_u8, **kwargs)` (returns its meta dict)."""
    on = LOOK_S_POPOUT if popout is None else bool(popout)
    if not on:
        return render_full_head_studio_card(backdrop_bgr, aroll_bgr, **kwargs)
    if person_alpha_u8 is None:
        raise ValueError("pop-out card needs person_alpha_u8 (RVM matte in source geometry)")
    return render_popout_studio_card(backdrop_bgr, aroll_bgr, person_alpha_u8, **kwargs)


def verify_audio_voice_sync_guard(
    voice_path: Path | str,
    target_duration_sec: float,
    *,
    max_drift_sec: float = 1.5,
    min_speech_density: float = 0.40,
    max_internal_silence_sec: float = 2.8,
) -> dict[str, float]:
    vp = Path(voice_path)
    if not vp.is_file():
        raise FileNotFoundError(f"[VoiceSyncGuard] Missing voice track: {vp}")

    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(vp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, timeout=_PROBE_TIMEOUT_S,
    )
    voice_dur = float(pr.stdout.strip())
    drift = abs(voice_dur - float(target_duration_sec))
    if drift > max_drift_sec:
        raise ValueError(
            f"[VoiceSyncGuard] REJECTED voice stem '{vp.name}': duration={voice_dur:.2f}s vs "
            f"target={target_duration_sec:.2f}s (drift={drift:.2f}s > {max_drift_sec:.2f}s — uncut raw take!)."
        )

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(vp), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True, timeout=_ENCODE_WAIT_S,
    ).stdout
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) * (1.0 / 32768.0)
    win = 400
    n_win = len(pcm) // win
    if n_win < 10:
        raise ValueError(f"[VoiceSyncGuard] Voice stem '{vp.name}' too short ({n_win} windows).")

    frames = pcm[: n_win * win].reshape(n_win, win)
    rms_db = 20.0 * np.log10(np.sqrt(np.mean(frames * frames, axis=1)) + 1e-7)
    peak_db = float(rms_db.max())
    if peak_db < -35.0:
        raise ValueError(f"[VoiceSyncGuard] Voice stem '{vp.name}' is silent/muted (peak={peak_db:.1f} dBFS).")

    thr_db = max(-42.0, float(np.percentile(rms_db, 90)) - 22.0)
    active = rms_db >= thr_db
    speech_density = float(np.mean(active))

    i0, i1 = min(n_win, 20), max(20, n_win - 48)
    interior_sil = (~active[i0:i1]).astype(np.int32)
    max_sil_s = 0.0
    if interior_sil.size > 0:
        padded = np.concatenate(([0], interior_sil, [0]))
        edges = np.flatnonzero(np.diff(padded))
        runs = edges[1::2] - edges[0::2]
        max_sil_s = float(runs.max() * 0.025) if runs.size > 0 else 0.0

    if speech_density < min_speech_density or max_sil_s > max_internal_silence_sec:
        raise ValueError(
            f"[VoiceSyncGuard] REJECTED voice stem '{vp.name}': speech_density={speech_density:.2f} "
            f"(min={min_speech_density:.2f}), max_interior_silence={max_sil_s:.2f}s (max={max_internal_silence_sec:.2f}s)."
        )

    return {
        "voice_dur_sec": round(voice_dur, 4),
        "drift_sec": round(drift, 4),
        "speech_density": round(speech_density, 4),
        "max_interior_silence_sec": round(max_sil_s, 4),
        "peak_dbfs": round(peak_db, 2),
    }


# ==============================================================================
# 3. FULL-WIDTH (0..1080) NEON CONTOUR ALPHA & BORDER-SAFE NEON BLACKOUT
# ==============================================================================
def _alpha_seq_digest(frames: list[np.ndarray], pms: list[np.ndarray | None] | None, stride: int) -> str:
    """SHA-256 (16 hex) of everything the full-width alpha depends on: count, stride, shape and the stride key frames' bytes."""
    h = hashlib.sha256(f"v791|{len(frames)}|{stride}|{frames[0].shape if frames else ()}".encode("utf-8"))
    keys = sorted(set(range(0, len(frames), max(1, stride))) | ({len(frames) - 1} if frames else set()))
    for i in keys:
        h.update(np.ascontiguousarray(frames[i]).tobytes())
        pm = pms[i] if (pms is not None and i < len(pms)) else None
        h.update(b"-" if pm is None else np.ascontiguousarray(pm).tobytes())
    return h.hexdigest()[:16]


def get_or_build_fullwidth_person_alpha_seq(
    cache_dir: Path,
    seg_tag: str,
    frames_clean_bgr: list[np.ndarray],
    cached_pms_u8: list[np.ndarray | None] | None = None,
    *,
    stride: int = 3,
) -> np.ndarray:
    """Full-width person alpha (half-res uint8, nf x H/2 x W/2) for a segment, cached as `.npz` in `cache_dir`.
    The cache key is a SHA-256 of the frame count, stride, shape and the content of the stride key frames (+ the RVM mattes when
    given), so new frames under the same `seg_tag` never hit a stale cache. Written to a temp file then `os.replace`d (atomic)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    nf = len(frames_clean_bgr)
    npz_p = cache_dir / f"fullwidth_alpha_{seg_tag}_{nf}f_{_alpha_seq_digest(frames_clean_bgr, cached_pms_u8, stride)}.npz"
    if npz_p.is_file():
        return np.load(npz_p)["alpha_h"]

    H, W = frames_clean_bgr[0].shape[:2]
    hw, hh = W // 2, H // 2
    cy0 = int(round(660.0 * (H / 1920.0)))
    hy0 = cy0 // 2
    tw, th = hw, hh - hy0

    yy_c, xx_c = np.mgrid[0:th, 0:tw].astype(np.float32)
    y_src = (float(cy0) + yy_c * 2.0) * (1920.0 / H)
    x_src = (xx_c * 2.0) * (1080.0 / W)

    u_top = np.clip((y_src - 740.0) / 22.0, 0.0, 1.0)
    w_top = 0.5 * (1.0 - np.cos(np.pi * u_top))
    u_left = np.clip((x_src - 205.0) / 36.0, 0.0, 1.0)
    u_right = np.clip((875.0 - x_src) / 36.0, 0.0, 1.0)
    w_head_x = (0.5 * (1.0 - np.cos(np.pi * u_left))) * (0.5 * (1.0 - np.cos(np.pi * u_right)))
    u_shld = np.clip((y_src - 1125.0) / 48.0, 0.0, 1.0)
    w_shld = 0.5 * (1.0 - np.cos(np.pi * u_shld))
    spatial_cone = w_top * (w_head_x * (1.0 - w_shld) + 1.0 * w_shld)

    key_indices = list(range(0, nf, stride))
    if key_indices[-1] != nf - 1:
        key_indices.append(nf - 1)

    kern_cc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    key_alphas: dict[int, np.ndarray] = {}

    for ki in key_indices:
        sub_rgb = cv2.cvtColor(
            cv2.resize(frames_clean_bgr[ki][cy0:H, 0:W], (tw, th), interpolation=cv2.INTER_AREA),
            cv2.COLOR_BGR2RGB,
        )
        a_rem = predict_u2netp_alpha_u8(sub_rgb).astype(np.float32)
        pm_k = cached_pms_u8[ki] if (cached_pms_u8 is not None and ki < len(cached_pms_u8)) else None
        if pm_k is not None:
            pm_sub = cv2.resize(pm_k[cy0:H, 0:W], (tw, th), interpolation=cv2.INTER_AREA).astype(np.float32)
            # Only blend RVM inside central 140..940 where RVM was valid; use 100% full-width u2netp on outer shoulders!
            w_outer = np.clip((x_src - 900.0) / 45.0, 0.0, 1.0) + np.clip((180.0 - x_src) / 45.0, 0.0, 1.0)
            w_outer = np.clip(w_outer, 0.0, 1.0)
            fused = (0.62 * a_rem + 0.38 * pm_sub) * (1.0 - w_outer) + a_rem * w_outer
            a_f = fused * spatial_cone
        else:
            a_f = a_rem * spatial_cone

        a_f = cv2.GaussianBlur(a_f, (5, 5), 0) * spatial_cone
        fg_bin = (a_f >= 22.0).astype(np.uint8)
        num_lbl, labels, stats_cc, _ = cv2.connectedComponentsWithStats(fg_bin, connectivity=8)
        if num_lbl > 1:
            areas = stats_cc[1:, cv2.CC_STAT_AREA]
            best_lbl = 1 + int(np.argmax(areas))
            if int(areas[best_lbl - 1]) >= 1600:
                keep_u8 = ((labels == best_lbl).astype(np.uint8)) * 255
                keep_soft = cv2.GaussianBlur(
                    cv2.dilate(keep_u8, kern_cc, iterations=1).astype(np.float32) * (1.0 / 255.0),
                    (7, 7),
                    1.6,
                )
                a_f *= keep_soft
            else:
                a_f.fill(0.0)
        key_alphas[ki] = a_f

    out_half = np.zeros((nf, hh, hw), dtype=np.uint8)
    k_ptr = 0
    for i in range(nf):
        while k_ptr + 1 < len(key_indices) and key_indices[k_ptr + 1] < i:
            k_ptr += 1
        k0 = key_indices[k_ptr]
        k1 = key_indices[min(len(key_indices) - 1, k_ptr + 1)]
        if k0 == k1:
            af = key_alphas[k0]
        else:
            w1 = (i - k0) / float(k1 - k0)
            af = key_alphas[k0] * (1.0 - w1) + key_alphas[k1] * w1
        out_half[i, hy0:hh, 0:hw] = np.clip(af + 0.5, 0.0, 255.0).astype(np.uint8)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{npz_p.stem}.", suffix=".tmp.npz", dir=cache_dir)
    try:
        with os.fdopen(fd, "wb") as fh:
            np.savez_compressed(fh, alpha_h=out_half)
        os.replace(tmp_name, npz_p)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return out_half


def apply_fullwidth_neon_rim_blackout(
    plate_bgr: np.ndarray,
    warped_person_alpha_u8: np.ndarray,
    u_blackout: float,
    pulse_boost: float = 0.0,
) -> np.ndarray:
    """
    Border-Safe VFX-02 Electric Neon Rim-Contour Blackout:
    Uses `BORDER_REPLICATE` when warping `person_alpha` AND suppresses artificial frame-border
    edges within 14px of `x=0`, `x=W`, and `y=H` so shoulders reaching the screen border NEVER
    trigger a vertical or horizontal neon laser line!
    """
    u = _clamp(u_blackout, 0.0, 1.0)
    if u <= 0.002:
        return plate_bgr

    H, W = plate_bgr.shape[:2]
    pa_f = cv2.GaussianBlur(warped_person_alpha_u8.astype(np.float32) * (1.0 / 255.0), (5, 5), 1.0)
    pa_3 = pa_f[:, :, None]

    src_f = plate_bgr.astype(np.float32)
    obsidian_bg = np.array([[[7.0, 5.0, 5.0]]], dtype=np.float32)
    bg_crushed = src_f * (1.0 - u) + obsidian_bg * u
    fg_dimmed = src_f * (1.0 - 0.32 * u)
    base = bg_crushed * (1.0 - pa_3) + fg_dimmed * pa_3

    # Pad with BORDER_REPLICATE before dilate/erode so silhouettes touching x=0, x=W, y=H have 0 border gradient!
    pad = 8
    pa_pad = cv2.copyMakeBorder(pa_f, pad, pad, pad, pad, borderType=cv2.BORDER_REPLICATE)
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    k_ero = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dil = cv2.dilate(pa_pad, k_dil, iterations=1)[pad : pad + H, pad : pad + W]
    ero = cv2.erode(pa_pad, k_ero, iterations=1)[pad : pad + H, pad : pad + W]
    raw_edge = np.clip(dil - ero, 0.0, 1.0)

    # Extra 14px smooth cosine border guard at left/right/bottom frame edges
    xx = np.arange(W, dtype=np.float32)
    yy = np.arange(H, dtype=np.float32)
    bx_guard = np.minimum(np.clip((xx - 3.0) / 14.0, 0.0, 1.0), np.clip(((W - 4.0) - xx) / 14.0, 0.0, 1.0))
    by_guard = np.clip(((H - 4.0) - yy) / 14.0, 0.0, 1.0)
    raw_edge *= by_guard[:, None] * bx_guard[None, :]

    core_rim = cv2.GaussianBlur(raw_edge, (0, 0), 1.6)
    edge_half = cv2.resize(raw_edge, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    bloom_half = cv2.GaussianBlur(edge_half, (0, 0), 7.5)
    outer_bloom = cv2.resize(bloom_half, (W, H), interpolation=cv2.INTER_LINEAR) * (1.0 - 0.58 * pa_f)

    gain = u * (1.0 + float(pulse_boost))
    c_core = np.array([[[40.0, 69.0, 255.0]]], dtype=np.float32)
    c_hot = np.array([[[165.0, 215.0, 255.0]]], dtype=np.float32)
    c_bloom = np.array([[[26.0, 107.0, 255.0]]], dtype=np.float32)

    neon_add = (
        c_bloom * (outer_bloom[:, :, None] * 1.65 * gain)
        + c_core * (core_rim[:, :, None] * 1.35 * gain)
        + c_hot * ((np.clip(core_rim - 0.35, 0.0, 1.0) * 1.45)[:, :, None] * gain)
    )
    b_norm = np.clip(base * (1.0 / 255.0), 0.0, 1.0)
    n_norm = np.clip(neon_add * (1.0 / 255.0), 0.0, 1.0)
    out = (1.0 - (1.0 - b_norm) * (1.0 - n_norm)) * 255.0
    return np.clip(out + 0.5, 0.0, 255.0).astype(np.uint8)


# ==============================================================================
# 4. SINGLE-STREAM ENCODER + INCREMENTAL HASH CACHE + C/AVX2 FFMPEG COMPOSITOR
# ==============================================================================
def compute_segment_config_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


_ENCODE_WAIT_S = 600       # ffmpeg drain after the last frame
_COMPOSE_TIMEOUT_S = 3600  # one master compose (a 60 s 60 fps master takes ~90 s)


def _unique_tmp(dst: Path, suffix: str | None = None) -> Path:
    """A fresh hidden temp path next to `dst` (same folder, so `replace` is atomic); parallel runs never share a name."""
    fd, name = tempfile.mkstemp(prefix=f".tmp_{dst.stem}.", suffix=suffix if suffix is not None else dst.suffix, dir=dst.parent)
    os.close(fd)
    return Path(name)


def _concat_line(p: Path) -> str:
    """One ffconcat `file` line; a `'` in the path is written as `'\\''` (close quote, escaped quote, reopen)."""
    return "file '" + str(p.resolve()).replace("'", "'\\''") + "'"


def pipe_encode_single_plate_fast(
    frame_iter,
    dst_mp4: Path,
    *,
    gear: RenderGear,
    threads: int = 3,
) -> None:
    """
    Encodes ONE clean plate stream (`_plate_seg_XX.mp4`) directly to H.264 — 50% less encoding
    work than dual-stream `pipe_encode_dual_bgr_fast`!
    The output appears only on success (unique temp file + replace). If `frame_iter` raises, ffmpeg dies (BrokenPipe) or exits
    non-zero, ffmpeg is killed and reaped and the temp file removed; iterator errors propagate, ffmpeg failures raise RuntimeError.
    """
    dst_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_mp4 = _unique_tmp(dst_mp4)
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-threads", str(threads),
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{gear.width}x{gear.height}", "-r", str(gear.fps), "-i", "-",
        "-c:v", "libx264", "-preset", gear.preset, "-crf", str(gear.crf),
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
        "-pix_fmt", "yuv420p", str(tmp_mp4),
    ]
    err_log = tempfile.TemporaryFile()   # a file, not a pipe: a chatty ffmpeg can never block on stderr while we feed stdin
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err_log)
    if proc.stdin is None:
        raise RuntimeError("ffmpeg stdin pipe was not opened")

    def _err_tail() -> str:
        err_log.seek(0)
        return err_log.read().decode("utf-8", "replace").strip()[-400:]

    ok = False
    try:
        try:
            for bgr in frame_iter:
                if bgr.shape[1] != gear.width or bgr.shape[0] != gear.height:
                    bgr = cv2.resize(bgr, (gear.width, gear.height), interpolation=cv2.INTER_AREA)
                proc.stdin.write(bgr.tobytes())
            proc.stdin.close()
        except BrokenPipeError as exc:   # frame_iter errors (incl. OSError) propagate unchanged
            proc.kill()
            proc.wait()
            raise RuntimeError(f"FFmpeg plate encode failed for {dst_mp4} (pipe closed: {exc}; rc={proc.returncode}): {_err_tail()}") from exc
        rc = proc.wait(timeout=_ENCODE_WAIT_S)
        if rc != 0:
            raise RuntimeError(f"FFmpeg plate encode failed for {dst_mp4} (rc={rc}): {_err_tail()}")
        tmp_mp4.replace(dst_mp4)
        ok = True
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if not proc.stdin.closed:
            try:
                proc.stdin.close()
            except OSError:
                pass
        err_log.close()
        if not ok:
            tmp_mp4.unlink(missing_ok=True)


def compose_master_mp4_via_ffmpeg(
    plate_segs: list[Path],
    audio_master_wav: Path,
    overlay_clips: list[dict[str, Any]],
    screen_vfx_clips: list[dict[str, Any]],
    out_mp4: Path,
    *,
    gear: RenderGear,
    threads: int = 6,
) -> None:
    """
    High-Speed Native C/AVX2 FFmpeg Filtergraph Compositor (~180–260 fps on CPU!):
    Concatenates `plate_segs` (lossless demux), overlays all `kt01..kt12` `.mov` RGBA clips
    at exact `[cx, cy, scale, opacity_expr]` windows, blends `V2` `Screen` optical transitions
    (`Flash-Out`, `Film-Burn`, `Light-Leak`), clamps broadcast BT.709 TV range, and muxes AAC!
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = _unique_tmp(out_mp4, ".concat.txt")
    concat_txt.write_text("\n".join(_concat_line(Path(p)) for p in plate_segs) + "\n", encoding="utf-8")

    cmd: list[str] = [
        "ffmpeg", "-y", "-v", "error", "-threads", str(threads),
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-i", str(audio_master_wav.resolve()),
    ]

    s_xy = gear.scale_xy
    filter_parts: list[str] = []
    cur_v = "0:v"
    inp_idx = 2

    # 1. Kinetic Typography `.mov` RGBA Overlays (`setpts` exact timeline offset + `eof_action=pass`)
    for k_i, ov in enumerate(overlay_clips):
        mov_p = Path(ov["src"]).resolve()
        at_s = float(ov["at"])
        dur_s = float(ov["dur"])
        end_s = at_s + dur_s
        sc = float(ov.get("scale", 1.0)) * s_xy
        mw = max(2, int(round(int(ov["orig_w"]) * sc)) & ~1)
        mh = max(2, int(round(int(ov["orig_h"]) * sc)) & ~1)
        ox = int(round(float(ov["cx"]) * s_xy - mw * 0.5))
        oy = int(round(float(ov["cy"]) * s_xy - mh * 0.5))

        cmd.extend(["-i", str(mov_p)])
        lbl_ov = f"kt{k_i}"
        lbl_next = f"vkt{k_i}"

        op_expr = ov.get("alpha_mul")
        chain_ov = f"[{inp_idx}:v]fps={gear.fps},scale={mw}:{mh}:flags=bicubic,format=rgba"
        if op_expr is not None:
            chain_ov += f",colorchannelmixer=aa={float(op_expr):.4f}"
        chain_ov += f",setpts=PTS-STARTPTS+({at_s:.6f}/TB)[{lbl_ov}]"
        filter_parts.append(chain_ov)

        filter_parts.append(
            f"[{cur_v}][{lbl_ov}]overlay=x={ox}:y={oy}:format=auto:eof_action=pass:"
            f"enable='between(t,{at_s:.4f},{end_s:.4f})'[{lbl_next}]"
        )
        cur_v = lbl_next
        inp_idx += 1

    # 2. Optional V2 Optical Transitions (`Flash-Out`, `Film-Burn`, `Light-Leak`) via RGB Screen Blend
    if screen_vfx_clips:
        lbl_rgb = "v_rgb_base"
        filter_parts.append(f"[{cur_v}]format=gbrp[{lbl_rgb}]")
        cur_v = lbl_rgb
        for s_i, sc_clip in enumerate(screen_vfx_clips):
            src_p = Path(sc_clip["src"]).resolve()
            at_s = float(sc_clip["at"])
            dur_s = float(sc_clip["dur"])
            end_s = at_s + dur_s
            op_s = _clamp(float(sc_clip.get("opacity", 0.85)), 0.05, 1.0)
            fi_s = max(0.02, float(sc_clip.get("fade_in_s", min(0.05, dur_s * 0.28))))
            fo_s = max(0.04, float(sc_clip.get("fade_out_s", dur_s * 0.55)))
            fo_st = max(0.0, dur_s - fo_s)

            cmd.extend(["-i", str(src_p)])
            lbl_sc = f"sc{s_i}"
            lbl_next = f"vsc{s_i}"
            filter_parts.append(
                f"[{inp_idx}:v]trim=0:{dur_s:.4f},setpts=PTS-STARTPTS,fps={gear.fps},"
                f"scale={gear.width}:{gear.height}:flags=bilinear,format=gbrp,"
                f"fade=t=in:st=0:d={fi_s:.4f}:color=black,"
                f"fade=t=out:st={fo_st:.4f}:d={fo_s:.4f}:color=black,"
                f"setpts=PTS-STARTPTS+({at_s:.6f}/TB)[{lbl_sc}]"
            )
            filter_parts.append(
                f"[{cur_v}][{lbl_sc}]blend=all_mode=screen:all_opacity={op_s:.3f}:eof_action=pass:"
                f"enable='between(t,{at_s:.4f},{end_s:.4f})'[{lbl_next}]"
            )
            cur_v = lbl_next
            inp_idx += 1

    # 3. Broadcast BT.709 TV Range Limiter
    filter_parts.append(
        f"[{cur_v}]format=yuv420p,"
        f"lutyuv=y='clip(val,16,236)':u='clip(val,16,240)':v='clip(val,16,240)',"
        f"setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[vout]"
    )

    tmp_out = _unique_tmp(out_mp4)
    cmd.extend(
        [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[vout]", "-map", "1:a:0",
            "-sn", "-map_metadata", "-1",
            "-c:v", "libx264", "-preset", gear.preset, "-crf", str(gear.crf),
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", str(tmp_out),
        ]
    )
    try:
        pr = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_COMPOSE_TIMEOUT_S)
        if pr.returncode != 0:
            raise RuntimeError(f"FFmpeg master compose failed for {out_mp4} (rc={pr.returncode}): {pr.stderr.strip()[-600:]}")
        tmp_out.replace(out_mp4)
    finally:
        tmp_out.unlink(missing_ok=True)
        concat_txt.unlink(missing_ok=True)


# ==============================================================================
# 5. MINIMAL CLI (`--list-options`, `--draft` / `--master`, `--input`, `--out`)
# ==============================================================================
def _build_arg_parser() -> "argparse.ArgumentParser":
    import argparse

    ap = argparse.ArgumentParser(
        prog="fast_studio_compositor.py",
        description=(
            "Universal Studio Director v7.9.0 — Fast Studio Framing & FFmpeg Compositor. This CLI is a plain re-encode "
            "at the chosen gear; the studio look is the Python API or the Look S driver look_s_render.py (scenes.json -> master MP4)."
        ),
    )
    ap.add_argument("--list-options", action="store_true", help="Print render gears and matte-model resolution, then exit")
    gear = ap.add_mutually_exclusive_group()
    gear.add_argument("--draft", action="store_true", help="Draft gear: 540x960 @ 30 fps, CRF 20, ultrafast")
    gear.add_argument("--master", action="store_true", help="Master gear: 1080x1920 @ 60 fps, CRF 15, veryfast")
    ap.add_argument("--input", help="Input video. Checked with ffprobe: it must exist and carry a video stream with width, height and a "
                                    "frame rate (else exit 2); a non-9:16 or non-1080x1920 input is reported as a WARNING on stderr "
                                    "and cover-scaled / centre-cropped to the gear")
    ap.add_argument("--out", help="Output .mp4 path (plain re-encode at the chosen gear: no cards, PiP, plates or matte; the studio look is the Python API, see studio recipe)")
    return ap


def main(argv: list[str] | None = None) -> int:
    import sys

    args = _build_arg_parser().parse_args(argv)
    gears = {"draft": RenderGear.draft(), "master": RenderGear.master()}
    if args.list_options:
        for name, g in gears.items():
            print(f"{name}: {g.width}x{g.height} @ {g.fps} fps, crf={g.crf}, preset={g.preset}")
        try:
            print(f"matte model: {resolve_matte_model_path()}")
        except FileNotFoundError as exc:
            print(f"matte model: MISSING ({exc})")
        return 0
    if not (args.input and args.out):
        print("fast_studio_compositor: --input and --out are required (or use --list-options)", file=sys.stderr)
        return 2
    gear = gears["master" if args.master else "draft"]
    src, dst = Path(args.input), Path(args.out)
    try:
        info = probe_video(src)
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"fast_studio_compositor: {exc}", file=sys.stderr)
        return 2
    geo = check_look_s_geometry(info["width"], info["height"])
    if geo["status"] != "exact":
        print(f"fast_studio_compositor: WARNING: {geo['message']} (this re-encode cover-scales and centre-crops to "
              f"{gear.width}x{gear.height})", file=sys.stderr)
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={gear.width}:{gear.height}:force_original_aspect_ratio=increase,crop={gear.width}:{gear.height},fps={gear.fps}"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", gear.preset,
        "-crf", str(gear.crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst),
    ]
    try:
        return subprocess.run(cmd, check=False, timeout=_COMPOSE_TIMEOUT_S).returncode
    except subprocess.TimeoutExpired:
        print(f"fast_studio_compositor: ffmpeg timed out after {_COMPOSE_TIMEOUT_S} s", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
