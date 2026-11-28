#!/usr/bin/env python3
"""
flicker_schedule.py (v8.1.0) — stateless helpers for the @__dviet "silhouette flicker" opener and its siblings.

Pure functions only (no global state, inputs are never mutated, every call returns new objects):

  * `flicker_schedule(fps_num, fps_den, states)`  -> frame-exact, non-overlapping clip rows for ONE track.
    Default = the measured 8-frame opener (references/27 section 3.1): f0 plate, f1-3 cream silhouette `#FFFBF0`,
    f4-5 plate, f6 silhouette, f7 the real subject.
  * `schedule_to_clips` / `overlay_enable_expr`   -> spec clip rows / an ffmpeg `enable=` expression from the rows.
  * `silhouette_mov_cmd`                           -> ffmpeg command that paints an alpha matte `#FFFBF0` (alpha kept).
  * `matte_from_frames` + `check_subject_matte`    -> `predict_u2netp_alpha_u8` matte + loud refusal of bad mattes.
  * `clean_plate_median`                           -> temporal median over alpha == 0 frames (cv2.inpaint fallback).
  * `preset_clips`                                 -> frame-keyed preset (presets/*.json) -> spec clip fields in seconds.
  * `vanish_rows`, `clone_appear_rows`             -> macros that emit spec rows by reusing `flicker_schedule`.
  * `refuse_c_class`                               -> C-class asks (references/27 section 4) raise instead of being faked.

Everything that depends on FilmCraft behaviour is EXPERIMENTAL and `behaviour_unverified_in_app` (MCP was down; the
`effects.list` dump dated 2026-10-29 may be stale). Nothing here renders or edits a video project.
"""
from __future__ import annotations

import re
import unicodedata
import warnings
from fractions import Fraction
from typing import Any, Callable, Iterable, Sequence

import numpy as np

VERSION = "8.1.0"
SILHOUETTE_HEX = "FFFBF0"
# (state, frames): the 8 frames measured on 7664447 at 60 fps.
DEFAULT_OPENER_STATES: tuple[tuple[str, int], ...] = (
    ("plate", 1), ("silhouette", 3), ("plate", 2), ("silhouette", 1), ("subject", 1),
)
# States whose source clip is rendered on the timeline origin: `in` = `at`.
ALIGNED_STATES = frozenset({"silhouette", "subject"})
EXIT_EFFECTS = ("dip_to_white", "flash")

# references/27 section 4 "Chưa khả thi (C)": refused with a clear error, never faked.
_C_CLASS: dict[str, str] = {
    "time_displacement": "Time Displacement / slit-scan has no FilmCraft effect (only the ffmpeg/numpy B route exists)",
    "slit_scan": "Time Displacement / slit-scan has no FilmCraft effect (only the ffmpeg/numpy B route exists)",
    "ai_object_mask": "AI Object Mask / Roto Brush quality needs a segmentation model the skill does not have (u2netp is salient-object only)",
    "object_mask": "AI Object Mask / Roto Brush quality needs a segmentation model the skill does not have (u2netp is salient-object only)",
    "roto_brush": "AI Object Mask / Roto Brush quality needs a segmentation model the skill does not have (u2netp is salient-object only)",
    "planar_tracking": "occlusion-aware planar tracking (Mocha class) is not available; only a hand-placed corner_pin exists",
    "occlusion_aware_planar_tracking": "occlusion-aware planar tracking (Mocha class) is not available; only a hand-placed corner_pin exists",
    "3d_extrude": "3D extrude / real 3D lighting is not available (A-lite flat tile or the B CSS-3D plate only)",
    "extrude_3d": "3D extrude / real 3D lighting is not available (A-lite flat tile or the B CSS-3D plate only)",
}
_HEX6 = re.compile(r"^[0-9a-fA-F]{6}$")


class FlickerError(ValueError):
    """A flicker/macro/preset input is invalid; the message says what to fix. Never degraded silently."""


class MatteError(FlickerError):
    """The matte cannot carry a silhouette (empty, whole-frame, several/overlapping subjects, not person-shaped)."""


class UnsupportedEffectError(FlickerError):
    """A C-class ask (references/27 section 4) that the skill refuses instead of faking."""


# ---------------------------------------------------------------------------
# frame arithmetic
# ---------------------------------------------------------------------------

def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _rate(fps_num: Any, fps_den: Any) -> Fraction:
    for label, v in (("fps_num", fps_num), ("fps_den", fps_den)):
        if not _is_int(v) or v <= 0:
            raise FlickerError(f"{label} must be a positive integer (settings.frame_rate num/den), got {v!r}")
    return Fraction(fps_num, fps_den)


def frame_time(frame: int, fps_num: int, fps_den: int) -> float:
    """Seconds of integer `frame` (rounded to 1 ns; `to_frames` of fc_build maps it back to the same frame)."""
    rate = _rate(fps_num, fps_den)
    if not _is_int(frame) or frame < 0:
        raise FlickerError(f"frame must be an integer >= 0, got {frame!r}")
    return round(float(frame / rate), 9)


def seconds_to_frame(seconds: float, fps_num: int, fps_den: int) -> int:
    """Half-up snap, the same rule as fc_build.to_frames."""
    rate = _rate(fps_num, fps_den)
    return int(float(seconds) * float(rate) + 0.5 + 1e-9)


def key_time(frame: int, fps_num: int, fps_den: int) -> float:
    """Keyframe time on `frame`, rounded to 1 us exactly like compile_and_verify.sanitize_keyframe_list (so it is left alone)."""
    return round(frame_time(frame, fps_num, fps_den), 6)


def spec_fps(fps_num: int, fps_den: int) -> float:
    """Value for the spec's `fps` key (fc_build snaps 29.97 / 23.976 / 59.94 to their exact fractions)."""
    return float(_rate(fps_num, fps_den))


def _norm_states(states: Iterable[Any] | None) -> list[tuple[str, int]]:
    items = DEFAULT_OPENER_STATES if states is None else tuple(states)
    if not items:
        raise FlickerError("states must not be empty")
    out: list[tuple[str, int]] = []
    for i, item in enumerate(items):
        try:
            name, n = item
        except (TypeError, ValueError):
            raise FlickerError(f"states[{i}] must be a (name, frames) pair, got {item!r}") from None
        if not isinstance(name, str) or not name.strip():
            raise FlickerError(f"states[{i}] name must be a non-empty string, got {name!r}")
        if not _is_int(n) or n < 1:
            raise FlickerError(f"states[{i}] ({name!r}) frames must be an integer >= 1, got {n!r}")
        out.append((unicodedata.normalize("NFC", name.strip()), n))
    return out


def flicker_schedule(
    fps_num: int, fps_den: int, states: Sequence[Sequence[Any]] | None = None, start_frame: int = 0,
) -> list[dict[str, Any]]:
    """Contiguous, non-overlapping rows for ONE track, every state an integer number of frames.

    Each row: {"state", "frame", "frames", "at", "dur"} with `at`/`dur` in seconds. `at + dur` equals the next row's
    `at` to within 1 ns, so fc_build's `_check_overlaps` (1e-6 tolerance) accepts them on a single track.
    """
    _rate(fps_num, fps_den)
    if not _is_int(start_frame) or start_frame < 0:
        raise FlickerError(f"start_frame must be an integer >= 0, got {start_frame!r}")
    rows: list[dict[str, Any]] = []
    f = start_frame
    for name, n in _norm_states(states):
        rows.append({"state": name, "frame": f, "frames": n,
                     "at": frame_time(f, fps_num, fps_den), "dur": frame_time(n, fps_num, fps_den)})
        f += n
    return rows


def schedule_to_clips(
    rows: Sequence[dict[str, Any]], sources: dict[str, Any], name_prefix: str = "Flicker",
) -> list[dict[str, Any]]:
    """Spec clip rows from schedule rows. `sources[state]` is a file path, or None = "no clip, the layer below shows
    through" (the real subject on the A-roll track). A state without a `sources` entry raises."""
    clips: list[dict[str, Any]] = []
    for r in rows:
        st = r["state"]
        if st not in sources:
            raise FlickerError(f"no source for state {st!r}: map it to a file path, or to None to show the layer below")
        if sources[st] is None:
            continue
        clip: dict[str, Any] = {"name": unicodedata.normalize("NFC", f"{name_prefix} · {st} f{r['frame']}"),
                                "src": str(sources[st]), "at": r["at"], "dur": r["dur"]}
        if st in ALIGNED_STATES:
            clip["in"] = r["at"]
        clips.append(clip)
    return clips


def overlay_enable_expr(rows: Sequence[dict[str, Any]], state: str) -> str:
    """ffmpeg `enable=` expression that is true exactly on the frames of `state` (frame-exact, any fps)."""
    parts = [f"between(n,{r['frame']},{r['frame'] + r['frames'] - 1})" for r in rows if r["state"] == state]
    if not parts:
        raise FlickerError(f"state {state!r} does not occur in the schedule")
    return "+".join(parts)


# ---------------------------------------------------------------------------
# silhouette matte
# ---------------------------------------------------------------------------

_CODECS: dict[str, list[str]] = {
    "prores4444": ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"],
    "qtrle": ["-c:v", "qtrle", "-pix_fmt", "argb"],
    "png": ["-c:v", "png", "-pix_fmt", "rgba"],
}
_SEQUENCE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def silhouette_mov_cmd(
    matte_src: str, out: str, width: int, height: int, fps_num: int, fps_den: int,
    color: str = SILHOUETTE_HEX, codec: str = "prores4444", ffmpeg: str = "ffmpeg",
) -> list[str]:
    """ffmpeg argv that paints the gray alpha matte `matte_src` (video, or an image sequence such as `m_%04d.png`)
    with a flat `color` (default `#FFFBF0`) and keeps the matte as alpha. `qtrle` / `png` are lossless in RGB;
    `prores4444` (default) is the deliverable and goes through YUV, so the colour can be off by 1-2 levels."""
    hexcol = str(color).lstrip("#")
    if not _HEX6.match(hexcol):
        raise FlickerError(f"color must be 6 hex digits like FFFBF0, got {color!r}")
    if codec not in _CODECS:
        raise FlickerError(f"codec must be one of {sorted(_CODECS)}, got {codec!r}")
    for label, v in (("width", width), ("height", height)):
        if not _is_int(v) or v <= 0:
            raise FlickerError(f"{label} must be a positive integer, got {v!r}")
    _rate(fps_num, fps_den)
    rate = f"{fps_num}/{fps_den}"
    src = str(matte_src)
    is_seq = "%" in src or any(src.lower().endswith(e) for e in _SEQUENCE_EXT)
    graph = (f"[1:v]scale={width}:{height},format=gray[m];"
             f"[0:v][m]alphamerge=shortest=1[o]")  # shortest: the endless colour source stops with the matte
    return [ffmpeg, "-y", "-v", "error", "-nostdin",
            "-f", "lavfi", "-i", f"color=c=0x{hexcol.upper()}:s={width}x{height}:r={rate},format=rgba",  # rgba in the source: no YUV round trip
            *(["-framerate", rate] if is_seq else []), "-i", src,
            "-filter_complex", graph, "-map", "[o]", "-shortest", *_CODECS[codec], str(out)]


def matte_from_frames(
    frames: Iterable[np.ndarray], predict: Callable[[np.ndarray], np.ndarray] | None = None,
) -> list[np.ndarray]:
    """Alpha (uint8 HxW) per RGB uint8 frame. Default model: `predict_u2netp_alpha_u8` of fast_studio_compositor
    (salient-object, NOT a person detector; run `check_subject_matte` on the result). RVM is not vendored."""
    if predict is None:
        try:
            from fast_studio_compositor import predict_u2netp_alpha_u8 as predict  # noqa: PLC0415
        except ImportError as exc:
            raise FlickerError(f"cannot import predict_u2netp_alpha_u8 from fast_studio_compositor: {exc}") from exc
    out: list[np.ndarray] = []
    for i, fr in enumerate(frames):
        arr = np.asarray(fr)
        if arr.ndim != 3 or arr.shape[2] != 3 or arr.dtype != np.uint8:
            raise FlickerError(f"frame {i} must be an HxWx3 uint8 RGB array, got {arr.shape} {arr.dtype}")
        alpha = np.asarray(predict(arr), dtype=np.uint8)
        if alpha.shape != arr.shape[:2]:
            raise FlickerError(f"matte for frame {i} has shape {alpha.shape}, expected {arr.shape[:2]}")
        out.append(alpha)
    return out


def check_subject_matte(
    alphas: Iterable[np.ndarray], *, threshold: int = 128, min_coverage: float = 0.005, max_coverage: float = 0.75,
    min_aspect: float = 0.6, second_blob_ratio: float = 0.15,
) -> None:
    """Raise `MatteError` when a matte cannot be one single standing/sitting person (heuristics, not a detector):
    empty, covering most of the frame, a second blob >= `second_blob_ratio` of the biggest one (several or
    overlapping subjects: occlusion-aware matting is C-class), or a blob wider than tall (`min_aspect` = h/w)."""
    import cv2  # noqa: PLC0415

    seen = 0
    for i, a in enumerate(alphas):
        seen += 1
        mask = (np.asarray(a) >= threshold).astype(np.uint8)
        cov = float(mask.mean())
        if cov < min_coverage:
            raise MatteError(f"matte frame {i} is empty ({cov:.2%} < {min_coverage:.2%} coverage): no subject found, "
                             "refusing to build a silhouette from nothing")
        if cov > max_coverage:
            raise MatteError(f"matte frame {i} covers {cov:.0%} of the frame: the salient-object model grabbed the whole "
                             "shot, not a single person")
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        blobs = sorted(((int(stats[j, cv2.CC_STAT_AREA]), j) for j in range(1, n)), reverse=True)
        if len(blobs) > 1 and blobs[1][0] >= second_blob_ratio * blobs[0][0]:
            raise MatteError(f"matte frame {i} has {len(blobs)} separate blobs: several or overlapping subjects "
                             "(occlusion-aware matting is C-class, not supported)")
        j = blobs[0][1]
        w, h = int(stats[j, cv2.CC_STAT_WIDTH]), int(stats[j, cv2.CC_STAT_HEIGHT])
        if h < min_aspect * w:
            raise MatteError(f"matte frame {i}: main blob is {w}x{h} px (h/w {h / max(w, 1):.2f} < {min_aspect}), "
                             "not person-shaped (u2netp is salient-object, it also grabs furniture)")
    if seen == 0:
        raise MatteError("no matte frames given")


def clean_plate_median(
    frames: Sequence[np.ndarray], alphas: Sequence[np.ndarray], *, alpha_max: int = 0, min_clear_frames: int = 1,
    max_inpaint_fraction: float = 0.25,
) -> np.ndarray:
    """Clean plate from frames of a subject that moves: per pixel, the temporal median over the frames where
    alpha <= `alpha_max` (default: alpha == 0; pass dilated mattes to keep the edge halo out). Pixels clear in fewer than
    `min_clear_frames` frames are filled with cv2.inpaint; if they exceed `max_inpaint_fraction` of the frame the
    subject never left that area and the call raises instead of faking a plate. Returns a new HxWx3 uint8 array."""
    import cv2  # noqa: PLC0415

    if len(frames) == 0 or len(frames) != len(alphas):
        raise FlickerError(f"need the same non-zero number of frames and alphas, got {len(frames)} / {len(alphas)}")
    stack = np.stack([np.asarray(f) for f in frames])
    al = np.stack([np.asarray(a) for a in alphas])
    if stack.dtype != np.uint8 or stack.ndim != 4 or stack.shape[3] != 3:
        raise FlickerError(f"frames must be HxWx3 uint8 arrays, got stack {stack.shape} {stack.dtype}")
    if al.shape != stack.shape[:3]:
        raise FlickerError(f"alphas {al.shape} do not match frames {stack.shape[:3]}")
    clear = al <= alpha_max
    count = clear.sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN slice = never-clear pixel, handled below
        med = np.nanmedian(np.where(clear[..., None], stack.astype(np.float32), np.nan), axis=0)
    plate = np.clip(np.floor(np.nan_to_num(med, nan=0.0) + 0.5), 0, 255).astype(np.uint8)
    hole = count < max(1, min_clear_frames)
    frac = float(hole.mean())
    if frac > max_inpaint_fraction:
        raise FlickerError(f"{frac:.0%} of the frame is never clear of the subject (limit {max_inpaint_fraction:.0%}): "
                           "no clean plate can be recovered, shoot a plate without the subject")
    if hole.any():
        plate = cv2.inpaint(plate, hole.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
    return plate


# ---------------------------------------------------------------------------
# C-class refusal and frame-keyed presets
# ---------------------------------------------------------------------------

def refuse_c_class(name: str) -> None:
    """Raise `UnsupportedEffectError` when `name` is a C-class ask; return None otherwise."""
    key = re.sub(r"[\s\-./]+", "_", str(name).strip().lower())
    if key in _C_CLASS:
        raise UnsupportedEffectError(f"{name!r} is C-class and is not implemented: {_C_CLASS[key]} "
                                     "(references/27 section 4). Nothing was faked.")


def _is_keylist(v: Any) -> bool:
    return (isinstance(v, list) and len(v) > 0
            and all(isinstance(k, (list, tuple)) and len(k) in (2, 3) and isinstance(k[0], (int, float))
                    and not isinstance(k[0], bool) for k in v))


def preset_clips(
    preset: dict[str, Any], fps_num: int, fps_den: int, start_frame: int = 0,
) -> dict[str, dict[str, Any]]:
    """{role: spec clip fields} from a preset of presets/*.json, keyframes converted to seconds on integer frames.

    `keys_unit` "frames": key times are integer frames of the PROJECT rate (the look is a frame count, 2-3 frames).
    `keys_unit` "seconds": key times are snapped to the nearest frame. `start_frame` shifts the keys; it is only allowed
    for presets with `returns_to_rest` (the last key equals the resting value), and a hold key at 0 is prepended."""
    rate = _rate(fps_num, fps_den)
    unit = preset.get("keys_unit")
    if unit not in ("frames", "seconds"):
        raise FlickerError(f"preset keys_unit must be 'frames' or 'seconds', got {unit!r}")
    if not _is_int(start_frame) or start_frame < 0:
        raise FlickerError(f"start_frame must be an integer >= 0, got {start_frame!r}")
    if start_frame and not preset.get("returns_to_rest"):
        raise FlickerError("start_frame needs a preset with returns_to_rest = true")

    def to_frame(t: float) -> int:
        if unit == "frames":
            if t != int(t):
                raise FlickerError(f"frame counts must be integers, got {t!r}")
            return int(t)
        return seconds_to_frame(t, fps_num, fps_den)

    def conv(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if _is_keylist(v):
            frames = [to_frame(k[0]) for k in v]
            if any(b <= a for a, b in zip(frames, frames[1:])):
                raise FlickerError(f"keys {[k[0] for k in v]} collide on the {float(rate):g} fps frame grid")
            keys = [[key_time(f + start_frame, fps_num, fps_den), conv(k[1]), *k[2:]] for f, k in zip(frames, v)]
            if start_frame:
                keys.insert(0, [0.0, conv(v[-1][1]), "hold"])
            return keys
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    out: dict[str, dict[str, Any]] = {}
    for c in preset.get("clips", []):
        out[c["role"]] = conv(c.get("fields", {}))
    if not out:
        raise FlickerError("preset has no clips")
    return out


def preset_duration_frames(preset: dict[str, Any], fps_num: int, fps_den: int) -> int:
    rate = _rate(fps_num, fps_den)
    if "duration_frames" in preset:
        d = preset["duration_frames"]
        if not _is_int(d) or d < 1:
            raise FlickerError(f"duration_frames must be an integer >= 1, got {d!r}")
        return d
    return max(1, int(float(preset["duration_s"]) * float(rate) + 0.5 + 1e-9))


# ---------------------------------------------------------------------------
# macros (stretch goal): vanish and clone-appear
# ---------------------------------------------------------------------------

def _span(in_s: float, out_s: float, at_s: float, fps_num: int, fps_den: int) -> tuple[int, int]:
    if not (0 <= in_s < out_s):
        raise FlickerError(f"need 0 <= in < out, got in={in_s} out={out_s}")
    if at_s < 0:
        raise FlickerError(f"at must be >= 0, got {at_s}")
    return seconds_to_frame(at_s, fps_num, fps_den), seconds_to_frame(out_s - in_s, fps_num, fps_den)


def vanish_rows(
    subject_src: str, in_s: float, out_s: float, plate_src: str, fps_num: int, fps_den: int, *, at_s: float = 0.0,
    glow_frames: int = 5, negative_frames: int = 4, glow_peak: float = 120.0, exit_effect: str = "dip_to_white",
    exit_frames: int | None = None,
) -> dict[str, Any]:
    """Person vanishes onto a clean plate (references/27 section 3.3): the last `glow_frames` frames of the subject
    clip glow (`wonder_glow` 0 -> `glow_peak`), the last `negative_frames` are negative (`invert` blend 0 -> 100, hold),
    then `transition_out` `exit_effect` (default `dip_to_white`, 0.5 s) over the plate.
    `profile_scope: ["dviet"]` applies (white flash is scoped and capped, see references/23 1e).
    Returns {"plate": [clip], "subject": [clip], "frames": {...}}: put `plate` on the lower track, `subject` above it."""
    at_f, dur_f = _span(in_s, out_s, at_s, fps_num, fps_den)
    for label, n in (("glow_frames", glow_frames), ("negative_frames", negative_frames)):
        if not _is_int(n) or n < 1:
            raise FlickerError(f"{label} must be an integer >= 1, got {n!r}")
    if exit_effect not in EXIT_EFFECTS:
        raise FlickerError(f"exit_effect must be one of {EXIT_EFFECTS}, got {exit_effect!r}")
    if exit_frames is None:
        exit_frames = max(1, seconds_to_frame(0.5, fps_num, fps_den)) if exit_effect == "dip_to_white" else 4
    if not _is_int(exit_frames) or exit_frames < 1:
        raise FlickerError(f"exit_frames must be an integer >= 1, got {exit_frames!r}")
    glow_f = dur_f - glow_frames - negative_frames
    neg_f = dur_f - negative_frames
    if glow_f < 1:
        raise FlickerError(f"subject clip of {dur_f} frames is too short for {glow_frames}+{negative_frames} frames of effect")
    t = lambda f: frame_time(f, fps_num, fps_den)  # noqa: E731
    k = lambda f: key_time(f, fps_num, fps_den)  # noqa: E731
    subject = {
        "name": "Vanish · subject", "src": str(subject_src), "in": round(float(in_s), 9), "at": t(at_f), "dur": t(dur_f),
        "effects": [
            {"effect": "wonder_glow", "params": {"intensity": [[0.0, 0.0, "hold"], [k(glow_f), 0.0, "linear"],
                                                                [k(neg_f), float(glow_peak), "hold"]]}},
            {"effect": "invert", "params": {"channel": "RGB", "blend": [[0.0, 0.0, "hold"], [k(neg_f), 100.0, "hold"]]}},
        ],
        "transition_out": {"effect": exit_effect, "frames": exit_frames},
    }
    plate = {"name": "Vanish · clean plate", "src": str(plate_src), "at": t(at_f), "dur": t(dur_f + exit_frames)}
    return {"plate": [plate], "subject": [subject],
            "frames": {"at": at_f, "dur": dur_f, "glow_start": glow_f, "negative_start": neg_f, "exit_frames": exit_frames}}


def clone_appear_rows(
    subject_src: str, in_s: float, out_s: float, plate_src: str, fps_num: int, fps_den: int, *, at_s: float = 0.0,
    clone_at_s: float, offset_s: float, appear_states: Sequence[Sequence[Any]] = (("off", 2), ("on", 2), ("off", 2)),
) -> dict[str, Any]:
    """Clone / phan than from ONE take (references/27 section 3.2): the same matte plays again, `offset_s` seconds
    behind itself, and the duplicate flickers in with `appear_states` (2-frame on/off, built by `flicker_schedule`),
    then stays on to the end of the original. Returns {"plate", "subject", "clone": [clips]}: three tracks,
    each free of overlaps. The clone never occludes correctly when the two copies cross: that is C-class."""
    at_f, dur_f = _span(in_s, out_s, at_s, fps_num, fps_den)
    if not offset_s > 0:
        raise FlickerError(f"offset_s must be > 0 (the duplicate lags the original), got {offset_s}")
    clone_f = seconds_to_frame(clone_at_s, fps_num, fps_den)
    lead = sum(n for _, n in _norm_states(appear_states))
    on_f = clone_f + lead
    end_f = at_f + dur_f
    if clone_f < at_f or on_f >= end_f:
        raise FlickerError(f"the clone must start inside the subject clip with room to stay on "
                           f"(clone frame {clone_f}, steady on from {on_f}, original ends at frame {end_f})")
    rows = flicker_schedule(fps_num, fps_den, [*_norm_states(appear_states), ("on", end_f - on_f)], start_frame=clone_f)
    t = lambda f: frame_time(f, fps_num, fps_den)  # noqa: E731
    clone: list[dict[str, Any]] = []
    for r in rows:
        if r["state"] != "on":
            continue
        src_in = in_s + (r["frame"] - at_f) / float(_rate(fps_num, fps_den)) - offset_s
        if src_in < -1e-9:
            raise FlickerError(f"clone would read the matte before 0 s (in={src_in:.3f}); lower offset_s or start later")
        clone.append({"name": f"Clone · on f{r['frame']}", "src": str(subject_src), "in": round(max(src_in, 0.0), 9),
                      "at": r["at"], "dur": r["dur"]})
    subject = {"name": "Clone · original", "src": str(subject_src), "in": round(float(in_s), 9), "at": t(at_f), "dur": t(dur_f)}
    plate = {"name": "Clone · plate", "src": str(plate_src), "at": t(at_f), "dur": t(dur_f)}
    return {"plate": [plate], "subject": [subject], "clone": clone,
            "frames": {"clone_start": clone_f, "steady_on": on_f, "end": end_f}}


if __name__ == "__main__":
    import argparse

    argparse.ArgumentParser(description="flicker_schedule (v%s): import-only library of silhouette-flicker planning helpers; it has no command line interface." % VERSION).parse_args()
