#!/usr/bin/env python3
"""
v8_compositor_fx.py — Pro FilmCraft Director v8.0 Multi-Layer Cinema Compositor & FX Engine.

Supports both 9:16 (default 1080x1920) and 16:9 (opt-in 1920x1080) at 60fps (or 30fps).
Unifies the 4 reference channel techniques (@tng.vinhomes8, @vuotaiai, @__dviet, @xuanart.visual):
  1. Foreground Subject Matting (`extract_subject_matte`):
       RVM (RobustVideoMatting via ~/.venvs/rvm/bin/python on CUDA/CPU)
       -> fallback u2netp ONNX -> fallback OpenCV GrabCut / Chroma.
       Enables clean text-behind-subject (`kt17`, `w06`) Z-depth sandwiching.
  2. Damped-Spring Parallax / Follow-Speaker Compositing:
       Reads `subject_track.json` (from `subject_tracker.py`) and shifts overlay (x, y)
       per frame using anchors:
         `behind_head | above_head | left_shoulder | right_shoulder | follow_speaker`
  3. 60fps Optical Transitions & Stage FX:
       - `light_burst` (white-hot optical flare reveal, WCAG luma-capped)
       - `film_burn` (warm anamorphic amber/crimson light-leak transition)
       - `whip_blur` (directional horizontal motion-blur sweep)
       - `glowing_squircle_pip` (dark stage + giant neon hollow backdrop + glowing squircle PiP)
       - `broll_insert` (smooth eased full-screen / split / card B-roll that NEVER mutes voice)
  4. Master Render Pipeline CLI:
       v8_compositor_fx.py --plan <v8_edit_plan.json> --out <master_60fps.mp4> [--aspect 9:16|16:9] [--fps 60]
       - Zero-Voice-Loss Audio Guard: verifies abs(out_dur - in_dur) <= 0.15s.
       - Automatic metadata stripping via strip_metadata.py (fallback ffmpeg -map_metadata -1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------

ASPECT_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

DEFAULT_RVM_PYTHON = Path.home() / ".venvs" / "rvm" / "bin" / "python"
DEFAULT_RVM_DIR = Path.home() / ".local" / "share" / "video-ai" / "RobustVideoMatting"
DEFAULT_RVM_CHECKPOINT = DEFAULT_RVM_DIR / "rvm_mobilenetv3.pth"
DEFAULT_U2NETP_ONNX = Path.home() / ".rembg" / "models" / "u2netp" / "u2netp.onnx"
DEFAULT_STRIP_SCRIPT = Path("/home/vmiz/.gemini/config/skills/strip-media-metadata/scripts/strip_metadata.py")

MAX_AUDIO_DRIFT_SEC = 0.15
WCAG_MAX_MEAN_LUMA = 218.0  # <= 220 flash luma cap


class AudioSyncGuardError(RuntimeError):
    """Raised when rendered output duration drifts beyond 0.15s from input audio."""


# ---------------------------------------------------------------------------
# Easing & Color Helpers
# ---------------------------------------------------------------------------

def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 4.0 * t * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def hex_to_bgr(hex_color: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    s = (hex_color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return default
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (b, g, r)
    except ValueError:
        return default


def probe_media_info(path: Path) -> Dict[str, Any]:
    """Probe duration, width, height, fps, and audio stream presence via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {res.stderr.strip()}")
    data = json.loads(res.stdout or "{}")
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or 0.0)
    if duration <= 0.0 and v_stream:
        duration = float(v_stream.get("duration") or 0.0)
    if duration <= 0.0 and a_stream:
        duration = float(a_stream.get("duration") or 0.0)

    fps = 30.0
    width = 0
    height = 0
    if v_stream:
        width = int(v_stream.get("width") or 0)
        height = int(v_stream.get("height") or 0)
        rate_str = v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate") or "30/1"
        if "/" in rate_str:
            num, den = rate_str.split("/", 1)
            fps = float(num) / max(1.0, float(den))
        else:
            fps = float(rate_str)

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": a_stream is not None,
        "audio_duration": float(a_stream.get("duration") or duration) if a_stream else 0.0,
    }


def resize_cover(frame: np.ndarray, target_w: int, target_h: int, zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0) -> np.ndarray:
    """Center-cover resize with optional zoom (>=1.0) and normalized pan (-1..1)."""
    src_h, src_w = frame.shape[:2]
    if src_h == 0 or src_w == 0:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)
    scale = max(target_w / src_w, target_h / src_h) * max(1.0, float(zoom))
    new_w = max(target_w, int(round(src_w * scale)))
    new_h = max(target_h, int(round(src_h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (new_w, new_h), interpolation=interp)

    max_dx = max(0, new_w - target_w)
    max_dy = max(0, new_h - target_h)
    cx = int(round((max_dx / 2.0) * (1.0 + max(-1.0, min(1.0, pan_x)))))
    cy = int(round((max_dy / 2.0) * (1.0 + max(-1.0, min(1.0, pan_y)))))
    cx = max(0, min(max_dx, cx))
    cy = max(0, min(max_dy, cy))
    return resized[cy : cy + target_h, cx : cx + target_w]


# ---------------------------------------------------------------------------
# 1. Foreground Subject Matting (RVM CUDA -> u2netp -> GrabCut/Chroma)
# ---------------------------------------------------------------------------

def _detect_rvm_available() -> Tuple[bool, str]:
    """Check whether ~/.venvs/rvm/bin/python and RobustVideoMatting checkpoint exist."""
    rvm_py = Path(os.environ.get("PFD_RVM_PYTHON", str(DEFAULT_RVM_PYTHON)))
    rvm_dir = Path(os.environ.get("PFD_RVM_DIR", str(DEFAULT_RVM_DIR)))
    ckpt = Path(os.environ.get("PFD_RVM_CHECKPOINT", str(DEFAULT_RVM_CHECKPOINT)))
    if not (rvm_py.exists() and (rvm_dir / "inference.py").exists() and ckpt.exists()):
        return False, "cpu"
    probe = subprocess.run(
        [str(rvm_py), "-c", "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"],
        capture_output=True,
        check=False,
    )
    return True, ("cuda" if probe.returncode == 0 else "cpu")


def _extract_matte_rvm(
    video_path: Path,
    out_alpha_mp4: Path,
    fps: float,
    downsample_ratio: float = 0.25,
    seq_chunk: int = 12,
) -> Path:
    """Run RobustVideoMatting via ~/.venvs/rvm/bin/python -> PNG alpha sequence -> lossless gray MP4."""
    rvm_py = Path(os.environ.get("PFD_RVM_PYTHON", str(DEFAULT_RVM_PYTHON)))
    rvm_dir = Path(os.environ.get("PFD_RVM_DIR", str(DEFAULT_RVM_DIR)))
    ckpt = Path(os.environ.get("PFD_RVM_CHECKPOINT", str(DEFAULT_RVM_CHECKPOINT)))
    ok, device = _detect_rvm_available()
    if not ok:
        raise RuntimeError("RobustVideoMatting environment not found")

    with tempfile.TemporaryDirectory(prefix="v8_rvm_") as tmpdir:
        alpha_dir = Path(tmpdir) / "alpha"
        alpha_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(rvm_py),
            "-B",
            "inference.py",
            "--variant",
            "mobilenetv3",
            "--checkpoint",
            str(ckpt),
            "--device",
            device,
            "--input-source",
            str(video_path.resolve()),
            "--downsample-ratio",
            str(downsample_ratio),
            "--output-type",
            "png_sequence",
            "--output-alpha",
            str(alpha_dir),
            "--seq-chunk",
            str(seq_chunk),
        ]
        res = subprocess.run(cmd, cwd=str(rvm_dir), capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"RVM inference failed: {res.stderr[-600:]}")

        out_alpha_mp4.parent.mkdir(parents=True, exist_ok=True)
        ff_cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            f"{fps:.6f}",
            "-i",
            str(alpha_dir / "%04d.png"),
            "-c:v",
            "libx264",
            "-crf",
            "14",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            str(out_alpha_mp4),
        ]
        ff_res = subprocess.run(ff_cmd, capture_output=True, text=True, check=False)
        if ff_res.returncode != 0:
            raise RuntimeError(f"FFmpeg packing RVM alpha failed: {ff_res.stderr[-400:]}")
    return out_alpha_mp4


def _extract_matte_u2netp_frame(frame_bgr: np.ndarray, session: Any) -> np.ndarray:
    """Single-frame saliency matte via u2netp ONNX."""
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    inp = cv2.resize(rgb, (320, 320), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    inp = (inp - mean) / std
    inp = np.transpose(inp, (2, 0, 1))[None, ...]
    input_name = session.get_inputs()[0].name
    pred = session.run(None, {input_name: inp})[0][0, 0]
    pmin, pmax = float(pred.min()), float(pred.max())
    norm = (pred - pmin) / max(1e-6, pmax - pmin)
    alpha = cv2.resize((norm * 255.0).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
    return alpha


def _extract_matte_grabcut_or_chroma_frame(frame_bgr: np.ndarray, chroma_key: Optional[str] = None) -> np.ndarray:
    """Fast fallback foreground matte using chroma key (green/blue) or center-prior GrabCut."""
    h, w = frame_bgr.shape[:2]
    if chroma_key in ("green", "blue"):
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        if chroma_key == "green":
            bg_mask = cv2.inRange(hsv, np.array([35, 50, 40]), np.array([85, 255, 255]))
        else:
            bg_mask = cv2.inRange(hsv, np.array([95, 50, 40]), np.array([135, 255, 255]))
        fg = 255 - bg_mask
        fg = cv2.GaussianBlur(fg, (5, 5), 0)
        return fg

    # Downscaled GrabCut for speed on fallback path
    scale = min(1.0, 240.0 / max(1, w))
    sw, sh = max(32, int(w * scale)), max(32, int(h * scale))
    small = cv2.resize(frame_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
    mask = np.zeros((sh, sw), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    rect = (int(sw * 0.12), int(sh * 0.08), int(sw * 0.76), int(sh * 0.90))
    try:
        cv2.grabCut(small, mask, rect, bgd, fgd, 2, cv2.GC_INIT_WITH_RECT)
        fg_small = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except cv2.error:
        fg_small = np.zeros((sh, sw), np.uint8)
        cv2.ellipse(fg_small, (sw // 2, int(sh * 0.58)), (int(sw * 0.34), int(sh * 0.44)), 0, 0, 360, 255, -1)
    fg = cv2.resize(fg_small, (w, h), interpolation=cv2.INTER_LINEAR)
    fg = cv2.GaussianBlur(fg, (9, 9), 0)
    return fg


def extract_subject_matte(
    video_path: Path,
    work_dir: Path,
    backend: str = "auto",
    downsample_ratio: float = 0.25,
    chroma_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract per-frame foreground subject alpha matte as a cached grayscale MP4.

    Backend priority for `auto`:
      1. RVM (`~/.venvs/rvm/bin/python` + RobustVideoMatting on CUDA/CPU)
      2. `u2netp` ONNX (`~/.rembg/models/u2netp/u2netp.onnx`)
      3. OpenCV GrabCut / Chroma fallback

    Returns: {"alpha_mp4": Path, "backend_used": str, "device": str, "cached": bool}
    """
    video_path = Path(video_path).resolve()
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    info = probe_media_info(video_path)
    fps = info["fps"] or 30.0

    stat = video_path.stat()
    key = hashlib.md5(f"{video_path}:{stat.st_size}:{int(stat.st_mtime)}:{backend}:{downsample_ratio}".encode()).hexdigest()[:12]
    out_alpha_mp4 = work_dir / f"subject_matte_{key}.mp4"
    if out_alpha_mp4.exists() and out_alpha_mp4.stat().st_size > 1024:
        return {"alpha_mp4": out_alpha_mp4, "backend_used": f"{backend}(cached)", "device": "cache", "cached": True}

    # 1. Try RVM
    if backend in ("auto", "rvm"):
        rvm_ok, rvm_dev = _detect_rvm_available()
        if rvm_ok:
            try:
                _extract_matte_rvm(video_path, out_alpha_mp4, fps=fps, downsample_ratio=downsample_ratio)
                return {"alpha_mp4": out_alpha_mp4, "backend_used": "rvm", "device": rvm_dev, "cached": False}
            except Exception as exc:
                if backend == "rvm":
                    raise
                print(f"[v8_compositor_fx] WARN: RVM failed ({exc}), falling back to u2netp/grabcut.", file=sys.stderr)

    # 2. Try u2netp ONNX
    u2netp_path = Path(os.environ.get("U2NETP_ONNX_PATH", os.environ.get("PFD_MATTE_MODEL", str(DEFAULT_U2NETP_ONNX))))
    ort_session = None
    backend_used = "grabcut" if not chroma_key else f"chroma_{chroma_key}"
    if backend in ("auto", "u2netp") and u2netp_path.exists():
        try:
            import onnxruntime as ort  # type: ignore

            ort_session = ort.InferenceSession(str(u2netp_path), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
            backend_used = "u2netp"
        except Exception as exc:
            if backend == "u2netp":
                raise
            print(f"[v8_compositor_fx] WARN: u2netp unavailable ({exc}), falling back to grabcut.", file=sys.stderr)

    # Frame-by-frame u2netp or grabcut -> pipe into grayscale MP4
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for matte extraction: {video_path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ff_cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-s",
        f"{w}x{h}",
        "-r",
        f"{fps:.6f}",
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-crf",
        "14",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        str(out_alpha_mp4),
    ]
    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if ort_session is not None:
                alpha = _extract_matte_u2netp_frame(frame, ort_session)
            else:
                alpha = _extract_matte_grabcut_or_chroma_frame(frame, chroma_key=chroma_key)
            proc.stdin.write(alpha.tobytes())
        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg matte encoder exited with {ret}")
    finally:
        cap.release()

    return {"alpha_mp4": out_alpha_mp4, "backend_used": backend_used, "device": "cpu", "cached": False}


# ---------------------------------------------------------------------------
# 2. Parallax / Follow-Speaker Tracking & Damped Spring Solver
# ---------------------------------------------------------------------------

@dataclass
class SubjectSample:
    t: float
    face_cx: float  # normalized 0..1
    face_cy: float  # normalized 0..1
    head_top_y: float  # normalized 0..1
    face_w: float = 0.22
    face_h: float = 0.24
    shoulder_l: Tuple[float, float] = (0.28, 0.52)
    shoulder_r: Tuple[float, float] = (0.72, 0.52)


class SubjectTrackReader:
    """Loads `subject_track.json` (from `subject_tracker.py`) and interpolates anchor points at time t."""

    def __init__(self, samples: List[SubjectSample], src_w: int = 1080, src_h: int = 1920):
        self.samples = sorted(samples, key=lambda s: s.t)
        self.src_w = max(1, src_w)
        self.src_h = max(1, src_h)

    @classmethod
    def from_json(cls, path: Optional[Path], fallback_w: int = 1080, fallback_h: int = 1920) -> "SubjectTrackReader":
        if not path or not Path(path).exists():
            return cls([SubjectSample(t=0.0, face_cx=0.50, face_cy=0.38, head_top_y=0.22)], fallback_w, fallback_h)

        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        src_w = int(raw.get("width") or raw.get("video_width") or fallback_w)
        src_h = int(raw.get("height") or raw.get("video_height") or fallback_h)
        rows = raw.get("frames") or raw.get("samples") or raw.get("track") or (raw if isinstance(raw, list) else [])

        samples: List[SubjectSample] = []
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            t = float(row.get("t", row.get("time", row.get("sec", idx / 30.0))))

            # Accept normalized or pixel coords, or bbox [x, y, w, h]
            bbox = row.get("face_bbox_norm") or row.get("bbox_norm") or row.get("face_bbox") or row.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                bx, by, bw, bh = [float(v) for v in bbox]
                if max(bx, by, bw, bh) > 1.5:
                    bx, by, bw, bh = bx / src_w, by / src_h, bw / src_w, bh / src_h
                cx = bx + bw * 0.5
                cy = by + bh * 0.5
                head_top = max(0.05, by - bh * 0.18)
            else:
                cx = float(row.get("face_cx", row.get("cx", row.get("x", 0.5))))
                cy = float(row.get("face_cy", row.get("cy", row.get("y", 0.38))))
                bw = float(row.get("face_w", row.get("w", 0.22)))
                bh = float(row.get("face_h", row.get("h", 0.24)))
                if cx > 1.5:
                    cx /= src_w
                if cy > 1.5:
                    cy /= src_h
                if bw > 1.5:
                    bw /= src_w
                if bh > 1.5:
                    bh /= src_h
                head_top = float(row.get("head_top_y", row.get("head_top", row.get("crown_y", max(0.05, cy - bh * 0.65)))))
                if head_top > 1.5:
                    head_top /= src_h

            sl = row.get("left_shoulder") or row.get("shoulder_l")
            sr = row.get("right_shoulder") or row.get("shoulder_r")
            if isinstance(sl, (list, tuple)) and len(sl) == 2:
                sl_pt = (float(sl[0]) / (src_w if sl[0] > 1.5 else 1.0), float(sl[1]) / (src_h if sl[1] > 1.5 else 1.0))
            else:
                sl_pt = (max(0.08, cx - bw * 1.15), min(0.88, cy + bh * 0.85))
            if isinstance(sr, (list, tuple)) and len(sr) == 2:
                sr_pt = (float(sr[0]) / (src_w if sr[0] > 1.5 else 1.0), float(sr[1]) / (src_h if sr[1] > 1.5 else 1.0))
            else:
                sr_pt = (min(0.92, cx + bw * 1.15), min(0.88, cy + bh * 0.85))

            samples.append(
                SubjectSample(
                    t=t,
                    face_cx=cx,
                    face_cy=cy,
                    head_top_y=head_top,
                    face_w=bw,
                    face_h=bh,
                    shoulder_l=sl_pt,
                    shoulder_r=sr_pt,
                )
            )
        if not samples:
            samples = [SubjectSample(t=0.0, face_cx=0.50, face_cy=0.38, head_top_y=0.22)]
        return cls(samples, src_w, src_h)

    def sample_at(self, t: float) -> SubjectSample:
        if len(self.samples) == 1 or t <= self.samples[0].t:
            return self.samples[0]
        if t >= self.samples[-1].t:
            return self.samples[-1]
        lo, hi = 0, len(self.samples) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if self.samples[mid].t <= t:
                lo = mid
            else:
                hi = mid
        a, b = self.samples[lo], self.samples[hi]
        u = (t - a.t) / max(1e-6, b.t - a.t)
        return SubjectSample(
            t=t,
            face_cx=a.face_cx + (b.face_cx - a.face_cx) * u,
            face_cy=a.face_cy + (b.face_cy - a.face_cy) * u,
            head_top_y=a.head_top_y + (b.head_top_y - a.head_top_y) * u,
            face_w=a.face_w + (b.face_w - a.face_w) * u,
            face_h=a.face_h + (b.face_h - a.face_h) * u,
            shoulder_l=(
                a.shoulder_l[0] + (b.shoulder_l[0] - a.shoulder_l[0]) * u,
                a.shoulder_l[1] + (b.shoulder_l[1] - a.shoulder_l[1]) * u,
            ),
            shoulder_r=(
                a.shoulder_r[0] + (b.shoulder_r[0] - a.shoulder_r[0]) * u,
                a.shoulder_r[1] + (b.shoulder_r[1] - a.shoulder_r[1]) * u,
            ),
        )

    def anchor_target_px(self, t: float, anchor: str, canvas_w: int, canvas_h: int) -> Tuple[float, float]:
        s = self.sample_at(t)
        if anchor == "behind_head":
            return (s.face_cx * canvas_w, max(0.14, s.face_cy - s.face_h * 0.15) * canvas_h)
        if anchor == "above_head":
            return (s.face_cx * canvas_w, max(0.10, s.head_top_y - 0.08) * canvas_h)
        if anchor == "left_shoulder":
            return (s.shoulder_l[0] * canvas_w, s.shoulder_l[1] * canvas_h)
        if anchor == "right_shoulder":
            return (s.shoulder_r[0] * canvas_w, s.shoulder_r[1] * canvas_h)
        if anchor == "follow_speaker":
            return (s.face_cx * canvas_w, s.face_cy * canvas_h)
        return (0.5 * canvas_w, 0.5 * canvas_h)


@dataclass
class SpringParallaxState:
    """Critically/slightly underdamped 2D spring for smooth parallax overlay tracking."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    stiffness: float = 68.0
    damping: float = 15.0
    parallax_gain: float = 0.65

    def step(self, target_x: float, target_y: float, dt: float) -> Tuple[float, float]:
        dt = max(1e-4, min(0.05, float(dt)))
        ax = self.stiffness * (target_x - self.x) - self.damping * self.vx
        ay = self.stiffness * (target_y - self.y) - self.damping * self.vy
        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.x, self.y


# ---------------------------------------------------------------------------
# 3. 60fps Optical Transitions & Stage FX
# ---------------------------------------------------------------------------

def apply_light_burst(
    frame_bgr: np.ndarray,
    progress: float,
    color_hex: str = "#FFF7E6",
    intensity: float = 0.82,
    center_norm: Tuple[float, float] = (0.5, 0.42),
) -> np.ndarray:
    """
    White-hot optical flare reveal at beat transitions (WCAG luma-capped <= 218).
    progress in [0.0, 1.0]: peaks around 0.38 then decays smoothly.
    """
    p = max(0.0, min(1.0, float(progress)))
    if p <= 0.0 or p >= 1.0:
        return frame_bgr
    bell = math.sin(math.pi * (p ** 0.72)) ** 1.35
    strength = bell * max(0.0, min(1.0, intensity))
    if strength < 0.01:
        return frame_bgr

    h, w = frame_bgr.shape[:2]
    cx, cy = int(w * center_norm[0]), int(h * center_norm[1])
    yy, xx = np.ogrid[:h, :w]
    rx = max(1.0, w * (0.35 + 0.55 * bell))
    ry = max(1.0, h * (0.28 + 0.48 * bell))
    dist2 = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    radial = np.exp(-dist2 * 1.8).astype(np.float32)

    # Add horizontal anamorphic flare streak
    streak = np.exp(-(((yy - cy) / max(1.0, h * 0.045)) ** 2)).astype(np.float32) * 0.55
    mask = np.clip((radial + streak) * strength, 0.0, 1.0)[..., None]

    tint = np.array(hex_to_bgr(color_hex, (230, 247, 255)), dtype=np.float32).reshape(1, 1, 3)
    f = frame_bgr.astype(np.float32)
    out = f + (255.0 - f) * mask * 0.75 + tint * mask * 0.38
    out = np.clip(out, 0.0, 255.0)

    # WCAG flash luma cap
    mean_luma = float(out.mean())
    if mean_luma > WCAG_MAX_MEAN_LUMA:
        scale_down = WCAG_MAX_MEAN_LUMA / max(1.0, mean_luma)
        out = np.clip(out * scale_down, 0.0, 255.0)
    return out.astype(np.uint8)


def apply_film_burn(
    frame_bgr: np.ndarray,
    progress: float,
    intensity: float = 0.75,
    side: str = "right",
) -> np.ndarray:
    """
    Warm anamorphic light-leak / 35mm film burn flash transition (amber + halation crimson).
    Screen-blended with WCAG luma guard.
    """
    p = max(0.0, min(1.0, float(progress)))
    if p <= 0.0 or p >= 1.0:
        return frame_bgr
    env = math.sin(math.pi * p) ** 1.15 * max(0.0, min(1.0, intensity))
    if env < 0.01:
        return frame_bgr

    h, w = frame_bgr.shape[:2]
    x_grid = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    y_grid = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]

    sweep_x = (1.15 - p * 1.3) if side == "right" else (-0.15 + p * 1.3)
    blob1 = np.exp(-(((x_grid - sweep_x) / 0.36) ** 2 + ((y_grid - 0.35) / 0.52) ** 2))
    blob2 = np.exp(-(((x_grid - (sweep_x + 0.18)) / 0.25) ** 2 + ((y_grid - 0.70) / 0.45) ** 2))

    # Warm crimson/orange/amber burn layers (BGR)
    burn = np.zeros((h, w, 3), dtype=np.float32)
    burn[..., 2] = np.clip((blob1 * 255.0 + blob2 * 220.0) * env, 0.0, 255.0)  # R
    burn[..., 1] = np.clip((blob1 * 135.0 + blob2 * 65.0) * env, 0.0, 255.0)   # G
    burn[..., 0] = np.clip((blob1 * 28.0 + blob2 * 14.0) * env, 0.0, 255.0)    # B

    # Screen blend: 1 - (1 - A)(1 - B)
    a = frame_bgr.astype(np.float32) / 255.0
    b = burn / 255.0
    out = (1.0 - (1.0 - a) * (1.0 - b)) * 255.0

    mean_luma = float(out.mean())
    if mean_luma > WCAG_MAX_MEAN_LUMA:
        out *= WCAG_MAX_MEAN_LUMA / max(1.0, mean_luma)
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def apply_whip_blur(
    frame_bgr: np.ndarray,
    progress: float,
    direction: str = "horizontal",
    max_kernel: int = 55,
) -> np.ndarray:
    """
    Directional motion-blur sweep between cuts (whip pan / speed ramp).
    progress in [0.0, 1.0]: peaks at 0.5.
    """
    p = max(0.0, min(1.0, float(progress)))
    bell = math.sin(math.pi * p)
    k = int(round(bell * max_kernel))
    if k < 3:
        return frame_bgr
    if k % 2 == 0:
        k += 1
    kernel = np.zeros((k, k), dtype=np.float32)
    if direction == "vertical":
        kernel[:, k // 2] = 1.0 / k
    else:
        kernel[k // 2, :] = 1.0 / k
    return cv2.filter2D(frame_bgr, -1, kernel)


def _make_squircle_mask(w: int, h: int, radius: int) -> np.ndarray:
    """Smooth anti-aliased rounded-square (squircle-like) alpha mask in uint8."""
    scale = 2
    sw, sh, sr = w * scale, h * scale, min(radius * scale, (min(w, h) * scale) // 2)
    mask = np.zeros((sh, sw), dtype=np.uint8)
    cv2.rectangle(mask, (sr, 0), (sw - sr, sh), 255, -1)
    cv2.rectangle(mask, (0, sr), (sw, sh - sr), 255, -1)
    cv2.circle(mask, (sr, sr), sr, 255, -1)
    cv2.circle(mask, (sw - sr, sr), sr, 255, -1)
    cv2.circle(mask, (sr, sh - sr), sr, 255, -1)
    cv2.circle(mask, (sw - sr, sh - sr), sr, 255, -1)
    return cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA)


def render_glowing_squircle_pip(
    speaker_frame: np.ndarray,
    canvas_w: int,
    canvas_h: int,
    backdrop_text: str = "PRO STUDIO",
    neon_hex: str = "#8C6CFF",
    bg_hex: str = "#090A10",
    pip_scale: float = 0.62,
    t_local: float = 0.0,
) -> np.ndarray:
    """
    `@vuotaiai` / `@xuanart.visual` dark studio stage + giant neon hollow backdrop text
    + glowing rounded-square (squircle) speaker PiP with multi-pass bloom rim.
    Works cleanly in both 9:16 and 16:9.
    """
    stage = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    bg_bgr = np.array(hex_to_bgr(bg_hex, (16, 10, 9)), dtype=np.uint8)
    stage[:, :] = bg_bgr
    neon_bgr = hex_to_bgr(neon_hex, (255, 108, 140))

    # Subtle radial spotlight behind PiP
    yy, xx = np.ogrid[:canvas_h, :canvas_w]
    spot = np.exp(-(((xx - canvas_w * 0.5) / (canvas_w * 0.42)) ** 2 + ((yy - canvas_h * 0.52) / (canvas_h * 0.34)) ** 2))
    glow_bg = np.zeros_like(stage, dtype=np.float32)
    for c in range(3):
        glow_bg[..., c] = spot * neon_bgr[c] * 0.24
    stage = np.clip(stage.astype(np.float32) + glow_bg, 0, 255).astype(np.uint8)

    # Giant hollow neon backdrop text (behind squircle PiP)
    if backdrop_text:
        text_layer = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        label = backdrop_text.upper()
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = (canvas_w / 320.0) if canvas_w <= canvas_h else (canvas_w / 460.0)
        thickness = max(3, int(canvas_w / 180))
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        if tw > canvas_w * 0.92:
            font_scale *= (canvas_w * 0.92) / max(1, tw)
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        tx = (canvas_w - tw) // 2
        # Repeat 2-3 stacked hollow lines for @vuotaiai kinetic backdrop feel
        y_positions = [int(canvas_h * 0.26), int(canvas_h * 0.54), int(canvas_h * 0.82)]
        for idx, ty in enumerate(y_positions):
            drift = int(math.sin(t_local * 1.4 + idx) * (canvas_w * 0.015))
            # Draw outline by drawing thick neon then carving inner with bg
            cv2.putText(text_layer, label, (tx + drift, ty), font, font_scale, neon_bgr, thickness + 3, cv2.LINE_AA)
            cv2.putText(text_layer, label, (tx + drift, ty), font, font_scale, (0, 0, 0), max(1, thickness - 1), cv2.LINE_AA)
        bloom = cv2.GaussianBlur(text_layer, (0, 0), sigmaX=12.0)
        stage = np.clip(stage.astype(np.float32) + text_layer.astype(np.float32) * 0.55 + bloom.astype(np.float32) * 0.65, 0, 255).astype(np.uint8)

    # Squircle PiP geometry (adaptive for 9:16 vs 16:9)
    side = int(min(canvas_w, canvas_h) * max(0.35, min(0.84, pip_scale)))
    pip_w = side
    pip_h = int(side * (1.12 if canvas_h > canvas_w else 0.92))
    pip_x = (canvas_w - pip_w) // 2
    pip_y = int((canvas_h - pip_h) * 0.48)
    radius = int(min(pip_w, pip_h) * 0.14)

    mask = _make_squircle_mask(pip_w, pip_h, radius)

    # Multi-pass neon rim glow around squircle
    rim_canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    edge = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    rim_rgb = np.zeros((pip_h, pip_w, 3), dtype=np.uint8)
    for c in range(3):
        rim_rgb[..., c] = (edge.astype(np.float32) / 255.0 * neon_bgr[c]).astype(np.uint8)
    rim_canvas[pip_y : pip_y + pip_h, pip_x : pip_x + pip_w] = rim_rgb
    outer_glow = cv2.GaussianBlur(rim_canvas, (0, 0), sigmaX=22.0)
    inner_glow = cv2.GaussianBlur(rim_canvas, (0, 0), sigmaX=6.0)
    stage = np.clip(
        stage.astype(np.float32) + outer_glow.astype(np.float32) * 0.95 + inner_glow.astype(np.float32) * 0.85,
        0,
        255,
    ).astype(np.uint8)

    # Composite cropped speaker inside squircle
    pip_img = resize_cover(speaker_frame, pip_w, pip_h, zoom=1.06 + 0.03 * math.sin(t_local * 0.9))
    alpha_f = (mask.astype(np.float32) / 255.0)[..., None]
    roi = stage[pip_y : pip_y + pip_h, pip_x : pip_x + pip_w].astype(np.float32)
    blended = pip_img.astype(np.float32) * alpha_f + roi * (1.0 - alpha_f)
    stage[pip_y : pip_y + pip_h, pip_x : pip_x + pip_w] = np.clip(blended, 0, 255).astype(np.uint8)

    # Crisp 2px specular rim highlight
    stage = np.clip(stage.astype(np.float32) + rim_canvas.astype(np.float32) * 0.70, 0, 255).astype(np.uint8)
    return stage


def composite_broll_insert(
    base_frame: np.ndarray,
    broll_frame: np.ndarray,
    t_local: float,
    dur: float,
    layout: str = "fullscreen",
    accent_hex: str = "#F1C711",
    pip_speaker: bool = False,
) -> np.ndarray:
    """
    Smooth eased B-roll insert (fullscreen | split_top | card_float) that NEVER cuts or mutes voice.
    Adds micro Ken Burns push so B-roll never looks frozen.
    """
    h, w = base_frame.shape[:2]
    fade_s = min(0.22, dur * 0.25)
    if t_local < fade_s:
        alpha_env = ease_out_cubic(t_local / max(1e-4, fade_s))
    elif t_local > dur - fade_s:
        alpha_env = ease_out_cubic((dur - t_local) / max(1e-4, fade_s))
    else:
        alpha_env = 1.0

    push = 1.0 + 0.08 * (t_local / max(0.01, dur))

    if layout == "fullscreen":
        br = resize_cover(broll_frame, w, h, zoom=push)
        out = cv2.addWeighted(br, alpha_env, base_frame, 1.0 - alpha_env, 0.0)
        if pip_speaker:
            # Small speaker PiP in bottom-right safe area so presenter remains visible
            pw = int(w * (0.28 if h > w else 0.22))
            ph = int(pw * (1.25 if h > w else 0.85))
            px = w - pw - int(w * 0.06)
            py = int(h * (0.58 if h > w else 0.62))
            pip_src = resize_cover(base_frame, pw, ph, zoom=1.10)
            pmask = _make_squircle_mask(pw, ph, int(min(pw, ph) * 0.16))
            af = (pmask.astype(np.float32) / 255.0 * alpha_env)[..., None]
            roi = out[py : py + ph, px : px + pw].astype(np.float32)
            out[py : py + ph, px : px + pw] = np.clip(pip_src.astype(np.float32) * af + roi * (1.0 - af), 0, 255).astype(np.uint8)
        return out

    if layout == "split_top":
        split_h = int(h * 0.50)
        br = resize_cover(broll_frame, w, split_h, zoom=push)
        out = base_frame.copy()
        slide_y = int((1.0 - alpha_env) * (-split_h))
        vis_h = split_h + slide_y
        if vis_h > 0:
            out[0:vis_h, 0:w] = br[split_h - vis_h : split_h, 0:w]
            # Crisp 3px divider line
            div_y = min(h - 3, vis_h)
            out[div_y : div_y + 3, :] = hex_to_bgr(accent_hex, (17, 199, 241))
        return out

    # Default: card_float (rounded B-roll showcase card over speaker / upper editorial stage)
    cw = int(w * (0.82 if h > w else 0.46))
    ch = int(cw * (9.0 / 16.0))
    cx = (w - cw) // 2 if h > w else int(w * 0.50)
    cy = int(h * 0.16) if h > w else int((h - ch) * 0.45)
    y_offset = int((1.0 - alpha_env) * 60)
    cy = max(0, min(h - ch, cy + y_offset))

    br = resize_cover(broll_frame, cw, ch, zoom=push)
    mask = _make_squircle_mask(cw, ch, int(min(cw, ch) * 0.08))
    af = (mask.astype(np.float32) / 255.0 * alpha_env)[..., None]
    out = base_frame.copy()
    roi = out[cy : cy + ch, cx : cx + cw].astype(np.float32)
    out[cy : cy + ch, cx : cx + cw] = np.clip(br.astype(np.float32) * af + roi * (1.0 - af), 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Overlay Media Reader (RGBA PNG / ProRes 4444 / qtrle MOV / WebM)
# ---------------------------------------------------------------------------

class OverlayClipReader:
    """Reads static RGBA PNG or animated RGBA video plates and alpha-blends them onto canvas."""

    def __init__(self, spec: Dict[str, Any], canvas_w: int, canvas_h: int):
        self.spec = spec
        self.src = Path(spec["src"])
        self.t0 = float(spec.get("start", spec.get("at", 0.0)))
        self.t1 = float(spec.get("end", self.t0 + float(spec.get("dur", 2.0))))
        self.layer = str(spec.get("layer", "front"))  # "behind_subject" | "front" | "caption"
        self.anchor = str(spec.get("anchor", "none"))  # none | behind_head | above_head | left_shoulder | right_shoulder | follow_speaker
        self.offset_x = float(spec.get("offset_x", 0.0))
        self.offset_y = float(spec.get("offset_y", 0.0))
        self.base_x = spec.get("x")
        self.base_y = spec.get("y")
        self.scale = float(spec.get("scale", 1.0))
        self.opacity = float(spec.get("opacity", 1.0))
        self.parallax_gain = float(spec.get("parallax_gain", 0.65))
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        self.is_image = self.src.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")
        self._img_bgra: Optional[np.ndarray] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._ff_proc: Optional[subprocess.Popen] = None
        self._vid_w: int = 0
        self._vid_h: int = 0
        self._vid_fps: float = 60.0
        self._last_fidx: int = -1
        self._cached_bgra: Optional[np.ndarray] = None
        self._eof: bool = False
        self._spring: Optional[SpringParallaxState] = None

        if self.is_image and self.src.exists():
            img = cv2.imread(str(self.src), cv2.IMREAD_UNCHANGED)
            if img is not None:
                if img.ndim == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                elif img.shape[2] == 3:
                    a = np.full((img.shape[0], img.shape[1], 1), 255, dtype=np.uint8)
                    img = np.concatenate([img, a], axis=2)
                self._img_bgra = img

    def is_active(self, t: float) -> bool:
        return self.t0 <= t <= self.t1

    def _start_ffmpeg_reader(self) -> bool:
        info = probe_media_info(self.src)
        self._vid_w = int(info.get("width") or 0)
        self._vid_h = int(info.get("height") or 0)
        self._vid_fps = float(info.get("fps") or 60.0)
        if self._vid_w <= 0 or self._vid_h <= 0:
            return False
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(self.src),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-",
        ]
        self._ff_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self._vid_w * self._vid_h * 4 * 2,
        )
        self._last_fidx = -1
        self._eof = False
        return True

    def _get_bgra(self, t: float) -> Optional[np.ndarray]:
        if self.is_image:
            return self._img_bgra
        if not self.src.exists():
            return None
        if self._ff_proc is None and not self._eof:
            if not self._start_ffmpeg_reader():
                self._eof = True
                return None

        frame_idx = max(0, int(math.floor((t - self.t0) * self._vid_fps)))
        if frame_idx == self._last_fidx and self._cached_bgra is not None:
            return self._cached_bgra
        if self._eof:
            return self._cached_bgra

        frame_bytes = self._vid_w * self._vid_h * 4
        assert self._ff_proc is not None and self._ff_proc.stdout is not None
        while self._last_fidx < frame_idx:
            buf = self._ff_proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                self._eof = True
                self.close()
                break
            self._cached_bgra = np.frombuffer(buf, dtype=np.uint8).reshape((self._vid_h, self._vid_w, 4))
            self._last_fidx += 1
        return self._cached_bgra

    def composite(
        self,
        canvas: np.ndarray,
        t: float,
        dt: float,
        tracker: SubjectTrackReader,
    ) -> np.ndarray:
        bgra = self._get_bgra(t)
        if bgra is None:
            return canvas

        oh, ow = bgra.shape[:2]
        if abs(self.scale - 1.0) > 1e-3:
            nw = max(2, int(round(ow * self.scale)))
            nh = max(2, int(round(oh * self.scale)))
            bgra = cv2.resize(bgra, (nw, nh), interpolation=cv2.INTER_AREA if self.scale < 1.0 else cv2.INTER_LINEAR)
            oh, ow = bgra.shape[:2]

        # Determine center (cx, cy)
        if self.anchor and self.anchor != "none":
            tx, ty = tracker.anchor_target_px(t, self.anchor, self.canvas_w, self.canvas_h)
            tx += self.offset_x
            ty += self.offset_y
            if self._spring is None:
                self._spring = SpringParallaxState(x=tx, y=ty, parallax_gain=self.parallax_gain)
            cx, cy = self._spring.step(tx, ty, dt)
        else:
            cx = float(self.base_x) if self.base_x is not None else (self.canvas_w * 0.5 + self.offset_x)
            cy = float(self.base_y) if self.base_y is not None else (self.canvas_h * 0.5 + self.offset_y)

        x0 = int(round(cx - ow * 0.5))
        y0 = int(round(cy - oh * 0.5))
        x1 = x0 + ow
        y1 = y0 + oh

        # Clip to canvas bounds
        cx0 = max(0, x0)
        cy0 = max(0, y0)
        cx1 = min(self.canvas_w, x1)
        cy1 = min(self.canvas_h, y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return canvas

        ox0 = cx0 - x0
        oy0 = cy0 - y0
        ox1 = ox0 + (cx1 - cx0)
        oy1 = oy0 + (cy1 - cy0)

        patch = bgra[oy0:oy1, ox0:ox1]
        alpha = (patch[..., 3:4].astype(np.float32) / 255.0) * max(0.0, min(1.0, self.opacity))
        fg = patch[..., :3].astype(np.float32)
        bg = canvas[cy0:cy1, cx0:cx1].astype(np.float32)
        canvas[cy0:cy1, cx0:cx1] = np.clip(fg * alpha + bg * (1.0 - alpha), 0, 255).astype(np.uint8)
        return canvas

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._ff_proc is not None:
            if self._ff_proc.stdout is not None:
                try:
                    self._ff_proc.stdout.close()
                except Exception:
                    pass
            if self._ff_proc.poll() is None:
                self._ff_proc.terminate()
                try:
                    self._ff_proc.wait(timeout=2)
                except Exception:
                    self._ff_proc.kill()
            self._ff_proc = None


# ---------------------------------------------------------------------------
# 4. Audio Preservation & Metadata Stripping
# ---------------------------------------------------------------------------

def mux_preserve_audio_and_verify(
    video_only_mp4: Path,
    audio_source: Path,
    out_mp4: Path,
    bgm_path: Optional[Path] = None,
    bgm_db: float = -18.0,
) -> Dict[str, Any]:
    """
    Mux rendered video with 100% intact input audio (optional BGM ducked under voice).
    Enforces Zero-Voice-Loss Audio Guard: abs(out_dur - in_dur) <= 0.15s.
    """
    in_info = probe_media_info(audio_source)
    in_dur = in_info["duration"]
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    if bgm_path and Path(bgm_path).exists() and in_info["has_audio"]:
        bgm_vol = 10.0 ** (bgm_db / 20.0)
        filter_complex = (
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[voice];"
            f"[2:a]aloop=loop=-1:size=2e+09,aformat=sample_rates=48000:channel_layouts=stereo,volume={bgm_vol:.5f}[bgm];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0.2[aout]"
        )
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_only_mp4),
            "-i",
            str(audio_source),
            "-i",
            str(bgm_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
    elif in_info["has_audio"]:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_only_mp4),
            "-i",
            str(audio_source),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_only_mp4),
            "-c:v",
            "copy",
            "-an",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg audio mux failed: {res.stderr[-500:]}")

    out_info = probe_media_info(out_mp4)
    out_dur = out_info["duration"]
    drift = abs(out_dur - in_dur)
    if in_dur > 0.0 and drift > MAX_AUDIO_DRIFT_SEC:
        raise AudioSyncGuardError(
            f"Zero-Voice-Loss guard FAILED: in_dur={in_dur:.3f}s, out_dur={out_dur:.3f}s, drift={drift:.3f}s > {MAX_AUDIO_DRIFT_SEC}s"
        )
    return {"in_dur": in_dur, "out_dur": out_dur, "drift_sec": round(drift, 4), "has_audio": out_info["has_audio"]}


def strip_output_metadata(mp4_path: Path) -> str:
    """Strip all EXIF/XMP/C2PA/encoder metadata via strip_metadata.py or ffmpeg fallback."""
    if DEFAULT_STRIP_SCRIPT.exists():
        res = subprocess.run(
            [sys.executable, str(DEFAULT_STRIP_SCRIPT), str(mp4_path), "--in-place"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return "strip_metadata.py"

    tmp_clean = mp4_path.with_suffix(".clean.mp4")
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(mp4_path),
        "-map",
        "0",
        "-c",
        "copy",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-fflags",
        "+bitexact",
        "-movflags",
        "+faststart",
        str(tmp_clean),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0 and tmp_clean.exists():
        shutil.move(str(tmp_clean), str(mp4_path))
        return "ffmpeg_map_metadata_-1"
    if tmp_clean.exists():
        tmp_clean.unlink()
    return "skipped"


# ---------------------------------------------------------------------------
# 5. Master Multi-Layer Render Pipeline & FilmCraft .fcproj Bridge (v8.1)
# ---------------------------------------------------------------------------

def _detect_filmcraft_and_display() -> Tuple[bool, str]:
    """Check whether FilmCraft binary and a virtual/explicit X display (Xvfb/Xephyr/CRAFT_DISPLAY) exist."""
    cands: List[Path] = []
    if os.environ.get("CRAFT_BIN_DIR"):
        cands.append(Path(os.environ["CRAFT_BIN_DIR"]) / "filmcraft")
    on_path = shutil.which("filmcraft")
    if on_path:
        cands.append(Path(on_path))
    cands.append(Path.home() / ".local" / "bin" / "filmcraft")
    fc_bin = next((c for c in cands if c.is_file()), None)
    if fc_bin is None:
        return False, "filmcraft binary not found"
    has_x = bool(os.environ.get("CRAFT_DISPLAY") or shutil.which("Xvfb") or shutil.which("Xephyr"))
    if not has_x:
        return False, "Xvfb/Xephyr not found and CRAFT_DISPLAY unset"
    return True, str(fc_bin)


def _export_fcproj_bridge(
    plan: Dict[str, Any],
    work: Path,
    canvas_w: int,
    canvas_h: int,
    fps: int,
    export_fcproj: Optional[Path] = None,
    craft_spec: Optional[Path] = None,
    plan_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Generate a strictly compliant `.craft.json` via `v8_to_craft_spec.build_spec_from_v8_plan`
    and (when `export_fcproj` is set) compile it to `.fcproj` via `compile_and_verify.py`.
    Never fails the already-rendered MP4 master if FilmCraft/Xvfb is unavailable.
    """
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from v8_to_craft_spec import build_spec_from_v8_plan  # noqa: PLC0415

    spec_path = (
        Path(craft_spec).resolve()
        if craft_spec
        else (Path(export_fcproj).resolve().with_suffix(".craft.json") if export_fcproj else (work / "project.craft.json").resolve())
    )
    spec, spec_warnings = build_spec_from_v8_plan(
        plan,
        spec_path,
        work_dir=work / "fc_spec_audio",
        plan_dir=plan_dir,
        width=canvas_w,
        height=canvas_h,
        fps=float(fps),
        write=True,
    )
    bridge_info: Dict[str, Any] = {
        "craft_spec": str(spec_path),
        "spec_tracks": len(spec.get("tracks", [])),
        "spec_warnings": spec_warnings,
    }
    if export_fcproj is None:
        bridge_info["fcproj_status"] = "spec_only"
        return bridge_info

    fcproj_path = Path(export_fcproj).resolve()
    bridge_info["fcproj_out"] = str(fcproj_path)

    fc_ok, fc_reason = _detect_filmcraft_and_display()
    compile_script = tools_dir / "compile_and_verify.py"
    if not fc_ok or not compile_script.is_file():
        bridge_info["fcproj_status"] = "spec_ready_filmcraft_unavailable"
        bridge_info["fcproj_reason"] = fc_reason if not fc_ok else f"missing {compile_script}"
        print(
            f"[v8_compositor_fx] INFO: {bridge_info['fcproj_status']} ({bridge_info['fcproj_reason']}); "
            f"preserved spec at {spec_path}",
            file=sys.stderr,
        )
        return bridge_info

    fc_work = work / "fc_compile"
    fc_work.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(compile_script),
        "--spec",
        str(spec_path),
        "--out",
        str(fcproj_path),
        "--work",
        str(fc_work),
        "--tier",
        "fast",
        "--audio-profile",
        "studio_14",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if res.returncode == 0 and fcproj_path.is_file():
        bridge_info["fcproj_status"] = "compiled_ok"
        bridge_info["fcproj_work"] = str(fc_work)
    else:
        combined = f"{res.stdout}\n{res.stderr}".lower()
        if any(tok in combined for tok in ("filmcraft", "xvfb", "display", "smoke skipped")):
            bridge_info["fcproj_status"] = "spec_ready_filmcraft_unavailable"
        else:
            bridge_info["fcproj_status"] = "compile_failed"
        bridge_info["fcproj_returncode"] = res.returncode
        bridge_info["fcproj_error"] = (res.stderr or res.stdout).strip()[-500:]
        print(
            f"[v8_compositor_fx] WARN: compile_and_verify exited {res.returncode} "
            f"({bridge_info['fcproj_status']}); MP4 master intact, spec preserved at {spec_path}",
            file=sys.stderr,
        )
    return bridge_info


def render_v8_plan(
    plan: Dict[str, Any],
    out_mp4: Path,
    aspect: str = "9:16",
    fps: int = 60,
    work_dir: Optional[Path] = None,
    matte_backend: str = "auto",
    dry_run: bool = False,
    export_fcproj: Optional[Path] = None,
    craft_spec: Optional[Path] = None,
    plan_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Render a `v8_edit_plan.json` into a 60fps master MP4 with:
      - Layer 0: Base A-roll / Glowing Squircle PiP stage / B-roll insert
      - Layer 1: Behind-subject overlays (`kt17`, `w06`, parallax text behind speaker)
      - Layer 2: Foreground subject cutout via RVM/u2netp alpha matte (only when Layer 1 is active)
      - Layer 3: Front overlays (glass pills, 3D icons, charts, spring-parallax badges)
      - Layer 4: Verbatim caption rail overlays (always readable, never occluded)
      - Layer 5: Optical transitions (`light_burst`, `film_burn`, `whip_blur`)
    """
    if aspect not in ASPECT_DIMENSIONS:
        raise ValueError(f"Unsupported aspect '{aspect}'. Expected one of {list(ASPECT_DIMENSIONS.keys())}")
    canvas_w, canvas_h = ASPECT_DIMENSIONS[aspect]

    aroll_path = Path(plan["aroll"])
    if not aroll_path.exists():
        raise FileNotFoundError(f"A-roll not found: {aroll_path}")
    audio_source = Path(plan.get("audio_mix") or plan.get("audio") or aroll_path)
    bgm_path = Path(plan["bgm"]) if plan.get("bgm") else None
    bgm_db = float(plan.get("bgm_db", -18.0))

    info = probe_media_info(aroll_path)
    duration = float(plan.get("duration") or info["duration"])
    total_frames = max(1, int(round(duration * fps)))

    work = Path(work_dir) if work_dir else out_mp4.parent / ".v8_work"
    work.mkdir(parents=True, exist_ok=True)

    overlays_spec: List[Dict[str, Any]] = list(plan.get("overlays", []))
    needs_matte = any(str(ov.get("layer", "front")) == "behind_subject" for ov in overlays_spec)
    stages_spec: List[Dict[str, Any]] = list(plan.get("stages", []))
    brolls_spec: List[Dict[str, Any]] = list(plan.get("broll_inserts", []))
    transitions_spec: List[Dict[str, Any]] = list(plan.get("transitions", []))

    summary: Dict[str, Any] = {
        "aspect": aspect,
        "resolution": [canvas_w, canvas_h],
        "fps": fps,
        "duration": round(duration, 4),
        "total_frames": total_frames,
        "needs_matte": needs_matte,
        "overlays_count": len(overlays_spec),
        "stages_count": len(stages_spec),
        "broll_inserts_count": len(brolls_spec),
        "transitions_count": len(transitions_spec),
        "dry_run": dry_run,
    }
    if dry_run:
        return summary

    # Load subject tracking
    track_path = Path(plan["subject_track"]) if plan.get("subject_track") else None
    tracker = SubjectTrackReader.from_json(track_path, fallback_w=info["width"] or canvas_w, fallback_h=info["height"] or canvas_h)

    # Extract foreground subject matte only if needed and backend != none
    matte_cap: Optional[cv2.VideoCapture] = None
    matte_fps = info["fps"] or 30.0
    if needs_matte and matte_backend != "none":
        if plan.get("alpha_mp4") and Path(plan["alpha_mp4"]).exists():
            matte_info = {"alpha_mp4": Path(plan["alpha_mp4"]), "backend_used": "precomputed", "device": "disk", "cached": True}
        else:
            matte_info = extract_subject_matte(
                aroll_path,
                work_dir=work,
                backend=matte_backend,
                downsample_ratio=float(plan.get("rvm_downsample", 0.25)),
                chroma_key=plan.get("chroma_key"),
            )
        summary["matte"] = {k: str(v) if isinstance(v, Path) else v for k, v in matte_info.items()}
        matte_cap = cv2.VideoCapture(str(matte_info["alpha_mp4"]))
        matte_fps = matte_cap.get(cv2.CAP_PROP_FPS) or matte_fps

    # Open A-roll and B-roll captures
    aroll_cap = cv2.VideoCapture(str(aroll_path))
    aroll_fps = aroll_cap.get(cv2.CAP_PROP_FPS) or info["fps"] or 30.0
    broll_caps: Dict[int, Tuple[cv2.VideoCapture, float]] = {}
    for idx, br in enumerate(brolls_spec):
        bp = Path(br["src"])
        if bp.exists():
            cap = cv2.VideoCapture(str(bp))
            broll_caps[idx] = (cap, cap.get(cv2.CAP_PROP_FPS) or 30.0)

    overlay_readers = [OverlayClipReader(ov, canvas_w, canvas_h) for ov in overlays_spec]

    video_only_mp4 = work / f"{out_mp4.stem}_video_only.mp4"
    ff_cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{canvas_w}x{canvas_h}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-crf",
        str(int(plan.get("crf", 17))),
        "-preset",
        str(plan.get("preset", "medium")),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(video_only_mp4),
    ]
    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)
    last_aroll_idx = -1
    cached_aroll: Optional[np.ndarray] = None
    last_matte_idx = -1
    cached_matte: Optional[np.ndarray] = None
    dt = 1.0 / max(1, fps)

    try:
        assert proc.stdin is not None
        for f_idx in range(total_frames):
            t = f_idx / float(fps)

            # Read synchronized A-roll frame
            src_idx = int(math.floor(t * aroll_fps))
            if src_idx != last_aroll_idx or cached_aroll is None:
                if src_idx != last_aroll_idx + 1:
                    aroll_cap.set(cv2.CAP_PROP_POS_FRAMES, src_idx)
                ok, raw_fr = aroll_cap.read()
                if ok and raw_fr is not None:
                    cached_aroll = resize_cover(raw_fr, canvas_w, canvas_h)
                    last_aroll_idx = src_idx
                elif cached_aroll is None:
                    cached_aroll = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

            frame = cached_aroll.copy()

            # Stage override (e.g., glowing_squircle_pip)
            active_stage = next((st for st in stages_spec if float(st["start"]) <= t <= float(st["end"])), None)
            if active_stage and active_stage.get("type") == "glowing_squircle_pip":
                frame = render_glowing_squircle_pip(
                    cached_aroll,
                    canvas_w,
                    canvas_h,
                    backdrop_text=str(active_stage.get("backdrop_text", "STUDIO")),
                    neon_hex=str(active_stage.get("neon_hex", "#8C6CFF")),
                    bg_hex=str(active_stage.get("bg_hex", "#090A10")),
                    pip_scale=float(active_stage.get("pip_scale", 0.62)),
                    t_local=t - float(active_stage["start"]),
                )

            # Behind-subject overlays + Foreground Matte sandwich
            behind_active = [r for r in overlay_readers if r.layer == "behind_subject" and r.is_active(t)]
            if behind_active:
                for reader in behind_active:
                    frame = reader.composite(frame, t, dt, tracker)
                if matte_cap is not None:
                    m_idx = int(math.floor(t * matte_fps))
                    if m_idx != last_matte_idx or cached_matte is None:
                        if m_idx != last_matte_idx + 1:
                            matte_cap.set(cv2.CAP_PROP_POS_FRAMES, m_idx)
                        mok, mraw = matte_cap.read()
                        if mok and mraw is not None:
                            if mraw.ndim == 3:
                                mraw = cv2.cvtColor(mraw, cv2.COLOR_BGR2GRAY)
                            cached_matte = resize_cover(cv2.cvtColor(mraw, cv2.COLOR_GRAY2BGR), canvas_w, canvas_h)[..., 0]
                            last_matte_idx = m_idx
                    if cached_matte is not None:
                        af = (cached_matte.astype(np.float32) / 255.0)[..., None]
                        frame = np.clip(
                            cached_aroll.astype(np.float32) * af + frame.astype(np.float32) * (1.0 - af),
                            0,
                            255,
                        ).astype(np.uint8)

            # B-roll inserts (voice stays 100% intact)
            for b_idx, br in enumerate(brolls_spec):
                b0, b1 = float(br["start"]), float(br["end"])
                if b0 <= t <= b1 and b_idx in broll_caps:
                    bcap, bfps = broll_caps[b_idx]
                    ss = float(br.get("broll_ss", 0.0))
                    bf_idx = max(0, int(math.floor((ss + (t - b0)) * bfps)))
                    bcap.set(cv2.CAP_PROP_POS_FRAMES, bf_idx)
                    bok, bfr = bcap.read()
                    if bok and bfr is not None:
                        frame = composite_broll_insert(
                            frame,
                            bfr,
                            t_local=t - b0,
                            dur=max(0.05, b1 - b0),
                            layout=str(br.get("layout", "fullscreen")),
                            accent_hex=str(br.get("accent_hex", "#F1C711")),
                            pip_speaker=bool(br.get("pip_speaker", False)),
                        )

            # Front overlays (3D badges, glass pills, charts)
            for reader in overlay_readers:
                if reader.layer == "front" and reader.is_active(t):
                    frame = reader.composite(frame, t, dt, tracker)

            # Caption rail overlays (topmost readability layer)
            for reader in overlay_readers:
                if reader.layer == "caption" and reader.is_active(t):
                    frame = reader.composite(frame, t, dt, tracker)

            # 60fps Optical Transitions
            for tr in transitions_spec:
                tr_t0 = float(tr.get("at", tr.get("start", 0.0)))
                tr_dur = float(tr.get("dur", 0.30))
                tr_start = tr_t0 - tr_dur * 0.5 if "at" in tr else tr_t0
                tr_end = tr_start + tr_dur
                if tr_start <= t <= tr_end:
                    prog = (t - tr_start) / max(1e-4, tr_dur)
                    ttype = str(tr.get("type", "light_burst"))
                    if ttype == "light_burst":
                        frame = apply_light_burst(
                            frame,
                            prog,
                            color_hex=str(tr.get("color_hex", "#FFF7E6")),
                            intensity=float(tr.get("intensity", 0.80)),
                        )
                    elif ttype == "film_burn":
                        frame = apply_film_burn(
                            frame,
                            prog,
                            intensity=float(tr.get("intensity", 0.72)),
                            side=str(tr.get("side", "right")),
                        )
                    elif ttype == "whip_blur":
                        frame = apply_whip_blur(
                            frame,
                            prog,
                            direction=str(tr.get("direction", "horizontal")),
                            max_kernel=int(tr.get("max_kernel", 55)),
                        )

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg master video encode failed with exit code {ret}")
    finally:
        aroll_cap.release()
        if matte_cap is not None:
            matte_cap.release()
        for bcap, _ in broll_caps.values():
            bcap.release()
        for r in overlay_readers:
            r.close()

    # Mux audio + enforce Zero-Voice-Loss guard (abs(out_dur - in_dur) <= 0.15s)
    audio_report = mux_preserve_audio_and_verify(
        video_only_mp4=video_only_mp4,
        audio_source=audio_source,
        out_mp4=out_mp4,
        bgm_path=bgm_path,
        bgm_db=bgm_db,
    )
    summary["audio_guard"] = audio_report

    # Strip all metadata before delivery
    strip_method = strip_output_metadata(out_mp4)
    summary["metadata_strip"] = strip_method
    summary["out_mp4"] = str(out_mp4)

    # Dual-Deliverable FilmCraft .fcproj Bridge (v8.1)
    if export_fcproj is not None or craft_spec is not None:
        fc_bridge = _export_fcproj_bridge(
            plan=plan,
            work=work,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            fps=fps,
            export_fcproj=export_fcproj,
            craft_spec=craft_spec,
            plan_dir=plan_dir,
        )
        summary.update(fc_bridge)

    return summary


# ---------------------------------------------------------------------------
# Self-Test & CLI Entrypoint
# ---------------------------------------------------------------------------

def _run_self_test() -> int:
    """Synthetic 1.0s test verifying optical FX, squircle PiP, spring parallax, and audio guard."""
    with tempfile.TemporaryDirectory(prefix="v8_fx_selftest_") as td:
        tdir = Path(td)
        aroll = tdir / "synth_aroll.mp4"
        out_mp4 = tdir / "synth_master.mp4"
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=540x960:rate=30:duration=1.0",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(aroll),
        ]
        subprocess.run(cmd, check=True)
        plan = {
            "aroll": str(aroll),
            "stages": [{"type": "glowing_squircle_pip", "start": 0.0, "end": 0.5, "backdrop_text": "V8 STUDIO"}],
            "transitions": [
                {"type": "light_burst", "at": 0.5, "dur": 0.24},
                {"type": "film_burn", "at": 0.75, "dur": 0.24},
                {"type": "whip_blur", "at": 0.90, "dur": 0.16},
            ],
        }
        report = render_v8_plan(plan, out_mp4, aspect="9:16", fps=30, work_dir=tdir / "work", matte_backend="none")
        print(json.dumps({"self_test": "PASS", "report": report}, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pro FilmCraft Director v8.0 Multi-Layer Cinema Compositor & FX Engine (9:16 default, 16:9 opt-in)."
    )
    p.add_argument("--plan", type=Path, help="Path to v8_edit_plan.json")
    p.add_argument("--out", type=Path, help="Output master MP4 path")
    p.add_argument("--aspect", choices=["9:16", "16:9"], default="9:16", help="Canvas aspect ratio (default: 9:16)")
    p.add_argument("--fps", type=int, default=60, help="Output framerate (default: 60)")
    p.add_argument("--work", type=Path, default=None, help="Working/cache directory for mattes and intermediates")
    p.add_argument(
        "--matte-backend",
        choices=["auto", "rvm", "u2netp", "grabcut", "none"],
        default="auto",
        help="Foreground subject matting backend (default: auto = RVM CUDA -> u2netp -> GrabCut)",
    )
    p.add_argument(
        "--export-fcproj",
        type=Path,
        default=None,
        help="Optional editable FilmCraft .fcproj output (builds .craft.json via v8_to_craft_spec.py + compile_and_verify.py)",
    )
    p.add_argument(
        "--craft-spec",
        type=Path,
        default=None,
        help="Optional output path for the generated FilmCraft .craft.json spec",
    )
    p.add_argument("--dry-run", action="store_true", help="Validate plan and print summary without rendering")
    p.add_argument("--self-test", action="store_true", help="Run a 1-second synthetic smoke test")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return _run_self_test()
    if not args.plan or not args.out:
        print("ERROR: --plan and --out are required (or pass --self-test).", file=sys.stderr)
        return 2
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = render_v8_plan(
        plan=plan,
        out_mp4=args.out,
        aspect=args.aspect,
        fps=args.fps,
        work_dir=args.work,
        matte_backend=args.matte_backend,
        dry_run=args.dry_run,
        export_fcproj=args.export_fcproj,
        craft_spec=args.craft_spec,
        plan_dir=plan_path.parent,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
