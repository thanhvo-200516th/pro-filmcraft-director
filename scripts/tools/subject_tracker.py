#!/usr/bin/env python3
"""
subject_tracker.py — YuNet face tracking + zero-lag bidirectional EMA smoothing for pro-filmcraft-director.

CLI:
  subject_tracker.py --input <video.mp4> --out <subject_track.json> [--sample-fps 15] [--tau 0.18] [--out-fps 60]

Detects the primary speaking subject using OpenCV YuNet (with Haar Cascade fallback), fills gaps via
linear interpolation, applies zero-lag forward+backward EMA smoothing (tau=0.18 for face box,
tau=0.12 for head_top), resamples to target fps, and emits `subject_track.json` with per-frame
normalized coordinates, pixel deltas from the median face, and scale ratio.

Also exports `compute_anchor_xy(frame_data, anchor, W, H, parallax=0.35)` and `sample_track_at(track, t)`
for downstream motion/overlay compositing.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
FFPROBE = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YUNET_MODEL = REPO_ROOT / "data" / "face_detection_yunet_2023mar.onnx"

SUPPORTED_ANCHORS = (
    "behind_head",
    "above_head",
    "left_temple",
    "right_temple",
    "left_shoulder",
    "right_shoulder",
    "lower_chest",
    "follow_speaker",
)


def probe_video(path: Path) -> dict[str, Any]:
    """Probe video dimensions (accounting for rotation), fps, and duration."""
    cmd = [
        FFPROBE,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate:stream_side_data=rotation:format=duration",
        "-of", "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"ffprobe failed on {path}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise SystemExit(f"no video stream found in {path}")
    s = streams[0]
    num_s, den_s = (s.get("r_frame_rate") or "30/1").split("/")
    fps = float(num_s) / float(den_s or 1)
    rot = 0
    for sd in s.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(s["width"]), int(s["height"])
    if abs(rot) in (90, 270):
        w, h = h, w
    dur = float(data["format"]["duration"])
    return {"width": w, "height": h, "fps": fps, "duration": dur}


def read_bgr_frames(path: Path, aw: int, ah: int, sample_fps: float):
    """Stream downscaled BGR24 frames from ffmpeg at `sample_fps`."""
    cmd = [
        FFMPEG,
        "-v", "error",
        "-nostdin",
        "-i", str(path),
        "-vf", f"fps={sample_fps},scale={aw}:{ah}:flags=area,format=bgr24",
        "-f", "rawvideo",
        "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10**7)
    frame_bytes = aw * ah * 3
    try:
        assert proc.stdout is not None
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            yield np.frombuffer(buf, np.uint8).reshape(ah, aw, 3)
    finally:
        if proc.poll() is None:
            proc.kill()
        if proc.stdout is not None:
            proc.stdout.close()
        proc.wait()


def smooth_bidirectional(vals: list[tuple[float, ...] | None], fps: float, tau: float = 0.18) -> np.ndarray | None:
    """Linearly interpolate missing gaps, then run zero-lag forward + backward EMA smoothing."""
    idx = [i for i, v in enumerate(vals) if v is not None]
    if not idx:
        return None
    k = len(vals[idx[0]])  # type: ignore[arg-type]
    arr = np.array(
        [vals[i] if vals[i] is not None else (np.nan,) * k for i in range(len(vals))],
        dtype=np.float64,
    )
    for c in range(k):
        col = arr[:, c]
        good = ~np.isnan(col)
        if not good.all():
            col[~good] = np.interp(np.where(~good)[0], np.where(good)[0], col[good])
            arr[:, c] = col
    if tau > 0.0 and len(arr) > 1:
        a = 1.0 - math.exp(-1.0 / max(1e-6, fps * tau))
        for i in range(1, len(arr)):
            arr[i] = arr[i - 1] + a * (arr[i] - arr[i - 1])
        for i in range(len(arr) - 2, -1, -1):
            arr[i] = arr[i + 1] + a * (arr[i] - arr[i + 1])
    return arr


class FaceDetectorWrapper:
    """YuNet primary face detector with automatic OpenCV Haar Cascade fallback."""

    def __init__(self, aw: int, ah: int, model_path: Path = DEFAULT_YUNET_MODEL, score_thresh: float = 0.55):
        self.aw = aw
        self.ah = ah
        self.backend = "haar"
        self.yunet = None
        self.haar = None

        if model_path.is_file() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(str(model_path), "", (aw, ah), score_thresh, 0.3, 20)
                self.backend = "yunet"
            except Exception:
                self.yunet = None

        if self.yunet is None:
            cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if not cascade_path.is_file():
                raise SystemExit(f"Neither YuNet ({model_path}) nor Haar Cascade ({cascade_path}) is available")
            self.haar = cv2.CascadeClassifier(str(cascade_path))
            self.backend = "haar"

    def detect_primary(self, bgr: np.ndarray) -> tuple[float, float, float, float, float] | None:
        """Return normalized (cx, cy, w, h, head_top) or None if no face detected."""
        if self.yunet is not None:
            _, faces = self.yunet.detect(bgr)
            if faces is not None and len(faces) > 0:
                best = max(faces, key=lambda r: float(r[2]) * float(r[3]) * float(r[-1]))
                x, y, bw, bh = float(best[0]), float(best[1]), float(best[2]), float(best[3])
                cx = (x + bw * 0.5) / self.aw
                cy = (y + bh * 0.5) / self.ah
                nw = bw / self.aw
                nh = bh / self.ah
                head_top = max(0.0, (y - 0.32 * bh) / self.ah)
                return (cx, cy, nw, nh, head_top)
            return None

        assert self.haar is not None
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        rects = self.haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(36, 36))
        if len(rects) == 0:
            return None
        x, y, bw, bh = max(rects, key=lambda r: int(r[2]) * int(r[3]))
        cx = (float(x) + bw * 0.5) / self.aw
        cy = (float(y) + bh * 0.5) / self.ah
        nw = float(bw) / self.aw
        nh = float(bh) / self.ah
        head_top = max(0.0, (float(y) - 0.30 * bh) / self.ah)
        return (cx, cy, nw, nh, head_top)


def compute_anchor_xy(
    frame_data: dict[str, float],
    anchor: str,
    W: int | float,
    H: int | float,
    parallax: float = 0.35,
) -> tuple[float, float]:
    """Compute pixel (x, y) for an editorial/graphic anchor relative to tracked speaker face.

    Supported anchors:
      behind_head, above_head, left_temple, right_temple,
      left_shoulder, right_shoulder, lower_chest, follow_speaker
    """
    if anchor not in SUPPORTED_ANCHORS:
        raise ValueError(f"Unsupported anchor '{anchor}'. Expected one of: {', '.join(SUPPORTED_ANCHORS)}")

    cx = float(frame_data.get("cx", 0.5))
    cy = float(frame_data.get("cy", 0.35))
    w = float(frame_data.get("w", 0.25))
    h = float(frame_data.get("h", 0.25))
    head_top = float(frame_data.get("head_top", max(0.0, cy - 0.82 * h)))
    dx_px = float(frame_data.get("dx_px", 0.0))
    dy_px = float(frame_data.get("dy_px", 0.0))

    Wf, Hf = float(W), float(H)
    fw = w * Wf
    fh = h * Hf

    # Reconstruct median reference position from current frame + delta, then apply parallax factor
    med_x = cx * Wf - dx_px
    med_y = cy * Hf - dy_px
    med_head_top = head_top * Hf - dy_px

    ax = med_x + dx_px * parallax
    ay = med_y + dy_px * parallax
    atop = med_head_top + dy_px * parallax

    if anchor == "behind_head":
        x, y = ax, ay - 0.10 * fh
    elif anchor == "above_head":
        x, y = ax, max(0.06 * Hf, atop - 0.35 * fh)
    elif anchor == "left_temple":
        x, y = ax - 0.85 * fw, ay - 0.25 * fh
    elif anchor == "right_temple":
        x, y = ax + 0.85 * fw, ay - 0.25 * fh
    elif anchor == "left_shoulder":
        x, y = ax - 1.15 * fw, ay + 0.95 * fh
    elif anchor == "right_shoulder":
        x, y = ax + 1.15 * fw, ay + 0.95 * fh
    elif anchor == "lower_chest":
        x, y = ax, ay + 1.45 * fh
    else:  # follow_speaker
        x, y = ax, ay

    x = min(Wf, max(0.0, x))
    y = min(Hf, max(0.0, y))
    return (round(x, 2), round(y, 2))


def sample_track_at(track: dict[str, Any], t: float) -> dict[str, float]:
    """Lookup nearest/interpolated frame_data from a loaded subject_track.json at time `t`."""
    frames = track.get("frames") or []
    if not frames:
        med = track.get("median_face") or {}
        return {
            "t": t,
            "cx": float(med.get("cx", 0.5)),
            "cy": float(med.get("cy", 0.35)),
            "w": float(med.get("w", 0.25)),
            "h": float(med.get("h", 0.25)),
            "head_top": float(med.get("head_top", 0.15)),
            "dx_px": 0.0,
            "dy_px": 0.0,
            "scale_ratio": 1.0,
        }
    fps = float(track.get("fps") or 30.0)
    idx = int(round(t * fps))
    idx = max(0, min(len(frames) - 1, idx))
    return frames[idx]


def track_subject(
    video_path: Path,
    sample_fps: float = 15.0,
    tau: float = 0.18,
    head_top_tau: float = 0.12,
    out_fps: float | None = None,
    model_path: Path = DEFAULT_YUNET_MODEL,
) -> dict[str, Any]:
    """Run full face tracking, gap interpolation, zero-lag smoothing, and resampling."""
    info = probe_video(video_path)
    W, H = info["width"], info["height"]
    src_fps = info["fps"]
    dur = info["duration"]
    target_fps = float(out_fps) if out_fps and out_fps > 0 else src_fps

    # Downscale analysis frame to short side ~540px for fast, accurate YuNet inference
    if W <= H:
        aw = min(W, 540)
        ah = max(2, int(round(aw * H / W / 2)) * 2)
    else:
        ah = min(H, 540)
        aw = max(2, int(round(ah * W / H / 2)) * 2)

    detector = FaceDetectorWrapper(aw, ah, model_path=model_path)

    raw_boxes: list[tuple[float, float, float, float] | None] = []
    raw_tops: list[tuple[float] | None] = []
    detected_count = 0

    for bgr in read_bgr_frames(video_path, aw, ah, sample_fps):
        det = detector.detect_primary(bgr)
        if det is not None:
            cx, cy, nw, nh, htop = det
            raw_boxes.append((cx, cy, nw, nh))
            raw_tops.append((htop,))
            detected_count += 1
        else:
            raw_boxes.append(None)
            raw_tops.append(None)

    n_sample = len(raw_boxes)
    if n_sample == 0:
        raise SystemExit(f"decoded 0 frames from {video_path}")

    sm_box = smooth_bidirectional(raw_boxes, sample_fps, tau=tau)
    if sm_box is None:
        sm_box = np.tile([0.5, 0.35, 0.28, 0.28], (n_sample, 1))

    sm_top = smooth_bidirectional(raw_tops, sample_fps, tau=head_top_tau)
    if sm_top is None:
        sm_top = np.clip(sm_box[:, 1:2] - 0.82 * sm_box[:, 3:4], 0.0, 1.0)

    # Resample smoothed tracks from sample_fps to target_fps
    t_sample = np.arange(n_sample, dtype=np.float64) / sample_fps
    n_out = max(1, int(round(dur * target_fps)))
    t_out = np.arange(n_out, dtype=np.float64) / target_fps

    cx_out = np.interp(t_out, t_sample, sm_box[:, 0])
    cy_out = np.interp(t_out, t_sample, sm_box[:, 1])
    w_out = np.interp(t_out, t_sample, sm_box[:, 2])
    h_out = np.interp(t_out, t_sample, sm_box[:, 3])
    top_out = np.interp(t_out, t_sample, sm_top[:, 0])

    med_cx = float(np.median(cx_out))
    med_cy = float(np.median(cy_out))
    med_w = float(np.median(w_out))
    med_h = float(np.median(h_out))
    med_top = float(np.median(top_out))
    safe_med_w = med_w if med_w > 1e-6 else 1.0

    frames: list[dict[str, float]] = []
    for i in range(n_out):
        cx = float(cx_out[i])
        cy = float(cy_out[i])
        fw = float(w_out[i])
        fh = float(h_out[i])
        ht = float(top_out[i])
        dx_px = (cx - med_cx) * W
        dy_px = (cy - med_cy) * H
        scale_ratio = fw / safe_med_w
        frames.append(
            {
                "t": round(float(t_out[i]), 4),
                "cx": round(cx, 5),
                "cy": round(cy, 5),
                "w": round(fw, 5),
                "h": round(fh, 5),
                "head_top": round(ht, 5),
                "dx_px": round(dx_px, 2),
                "dy_px": round(dy_px, 2),
                "scale_ratio": round(scale_ratio, 4),
            }
        )

    return {
        "tool": "subject_tracker",
        "detector": detector.backend,
        "source": str(video_path.resolve()),
        "width": W,
        "height": H,
        "source_fps": round(src_fps, 4),
        "sample_fps": sample_fps,
        "fps": round(target_fps, 4),
        "duration": round(dur, 4),
        "frame_count": len(frames),
        "detected_ratio": round(detected_count / max(1, n_sample), 4),
        "tau": tau,
        "head_top_tau": head_top_tau,
        "median_face": {
            "cx": round(med_cx, 5),
            "cy": round(med_cy, 5),
            "w": round(med_w, 5),
            "h": round(med_h, 5),
            "head_top": round(med_top, 5),
        },
        "frames": frames,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="Input talking-head video path")
    ap.add_argument("--out", required=True, help="Output JSON path (subject_track.json)")
    ap.add_argument("--sample-fps", type=float, default=15.0, help="Face detection sampling FPS (default: 15)")
    ap.add_argument("--tau", type=float, default=0.18, help="Bidirectional EMA smoothing tau for face box (default: 0.18)")
    ap.add_argument("--head-top-tau", type=float, default=0.12, help="Bidirectional EMA smoothing tau for head_top (default: 0.12)")
    ap.add_argument("--out-fps", type=float, default=None, help="Target output FPS (default: source video FPS; e.g. 60)")
    ap.add_argument("--model", type=Path, default=DEFAULT_YUNET_MODEL, help="Path to YuNet ONNX model")
    args = ap.parse_args()

    video_path = Path(args.input)
    if not video_path.is_file():
        print(f"input not found: {video_path}", file=sys.stderr)
        return 2

    result = track_subject(
        video_path=video_path,
        sample_fps=args.sample_fps,
        tau=args.tau,
        head_top_tau=args.head_top_tau,
        out_fps=args.out_fps,
        model_path=args.model,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "tool": "subject_tracker",
                "out": str(out_path),
                "detector": result["detector"],
                "width": result["width"],
                "height": result["height"],
                "fps": result["fps"],
                "duration": result["duration"],
                "frame_count": result["frame_count"],
                "detected_ratio": result["detected_ratio"],
                "median_face": result["median_face"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
