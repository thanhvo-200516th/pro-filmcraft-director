#!/usr/bin/env python3
"""fc_build — turn a craft timeline spec (*.craft.json) into a native FilmCraft project (.fcproj).

    python3 fc_build.py SPEC.craft.json OUT.fcproj [--report REPORT.json] [--frames N] [--workdir DIR]

The spec (references/timeline-spec.md) is validated first. A private FilmCraft instance (craftctl)
then places every clip, text, effect, keyframe, transition, caption and marker through the control
API and writes OUT with file.saveAs. OUT is re-opened in a fresh instance and its tracks, clips,
keyframes, effects, text, transitions, captions and markers are counted against the spec.
Exit 0 = every count matches, 1 = build failed or counts differ, 2 = invalid spec.
Spec features FilmCraft cannot take are listed under "unsupported" — never dropped silently.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from craftctl import TICKS_PER_SECOND, Craft, CraftError  # noqa: E402

INTERP = {"linear": "linear", "bezier": "bezier", "easeIn": "easeIn", "easeOut": "easeOut", "hold": "hold"}
BLEND = {"normal": "Normal", "screen": "Screen", "multiply": "Multiply", "add": "Linear Dodge (Add)",
         "overlay": "Overlay"}
ALIGN = {"left": "Left", "center": "Center", "right": "Right"}
MOTION_PARAMS = {"scale", "position", "rotation", "anchor", "scale_width"}
STROKE_PARAMS = {"color": "stroke_color", "width": "stroke_width"}
SHADOW_PARAMS = {"color": "shadow_color", "opacity": "shadow_opacity", "blur": "shadow_blur",
                 "distance": "shadow_distance", "angle": "shadow_angle", "size": "shadow_size"}
TEXT_PARAMS = {"color": "fill_color", "size": "size", "position": "position", "tracking": "tracking",
               "leading": "leading"}
STILL_SECONDS = 5.0
USER_PRESETS = Path.home() / ".local/share/filmcraft/effect-presets.json"

TOP_KEYS = {"name", "width", "height", "fps", "sample_rate", "duration", "tracks", "captions", "markers",
            "notes", "unsupported"}                 # the last two: written by adapters, carried to the report
VISUAL_KEYS = {"at", "dur", "name", "motion", "opacity", "blend", "effects", "preset",
               "transition_in", "transition_out"}
MEDIA_KEYS = VISUAL_KEYS | {"src", "in", "speed", "gain_db", "audio", "audio_track"}
TEXT_KEYS = VISUAL_KEYS | {"text", "font", "style", "size", "color", "align", "position", "stroke",
                           "shadow", "tracking", "leading"}
AUDIO_KEYS = {"src", "at", "in", "dur", "name", "speed", "gain_db", "effects", "preset",
              "transition_in", "transition_out"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


class SpecError(ValueError):
    """The spec is malformed; the message lists every problem found."""


# ---------- units ---------------------------------------------------------------------------------

def fps_fraction(fps: float) -> Fraction:
    """25 -> 25/1; 29.97 -> 30000/1001 (NTSC rates snap to their exact fraction)."""
    for base in (24, 30, 48, 60, 120):
        if abs(fps - base * 1000 / 1001) < 0.005:
            return Fraction(base * 1000, 1001)
    return Fraction(fps).limit_denominator(1000)


def to_frames(seconds: float, rate: Fraction) -> int:
    return math.floor(seconds * float(rate) + 0.5 + 1e-9)


def frame_ticks(frame: int, rate: Fraction) -> int:
    return round(Fraction(frame * TICKS_PER_SECOND * rate.denominator, rate.numerator))


def sec_ticks(seconds: float, rate: Fraction) -> int:
    """Seconds -> FilmCraft ticks, snapped to the nearest timeline frame."""
    return frame_ticks(to_frames(seconds, rate), rate)


def is_animated(value) -> bool:
    return (isinstance(value, list) and len(value) > 0
            and all(isinstance(k, list) and len(k) in (2, 3) and _is_num(k[0]) for k in value))


def keyframes(value) -> list[tuple[float, object, str]]:
    return [(k[0], k[1], k[2] if len(k) == 3 else "linear") for k in value]


def frame_keys(value, rate: Fraction) -> list[tuple[float, object, str]]:
    """keyframes(value) with keys that snap to the same frame merged (the last one wins): FilmCraft keeps
    one key per frame, so sub-frame keys (e.g. a 10 ms audio attack) would otherwise vanish unreported."""
    merged: dict[int, tuple[float, object, str]] = {}
    for k in keyframes(value):
        merged[to_frames(k[0], rate)] = k
    return [merged[f] for f in sorted(merged)]


def first_value(value):
    return value[0][1] if is_animated(value) else value


def media_time(info: dict, timeline_ticks: int) -> int:
    """FilmCraft stores keyframes in source-media time: sourceIn + (t - clip start) * speed."""
    return info["sourceIn"] + round((timeline_ticks - info["start"]) * info["speed"])


def new_effect_indexes(before: list[str], after: list[str]) -> list[int]:
    """Positions in `after` of effects that were not in `before` (greedy, order-preserving)."""
    out, j = [], 0
    for i, eid in enumerate(after):
        if j < len(before) and eid == before[j]:
            j += 1
        else:
            out.append(i)
    return out


def match_preset(want: str, names: list[str]) -> str | None:
    """Exact preset name, else a unique case-insensitive prefix ("[DViet] Flash Out")."""
    if want in names:
        return want
    hits = [n for n in names if n.lower().startswith(want.lower())]
    return hits[0] if len(hits) == 1 else None


def srt_cues(path: str | Path) -> int:
    return sum(1 for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if "-->" in line)


# ---------- validation ----------------------------------------------------------------------------

def adapter_note(u) -> str:
    """An adapter's own "unsupported" entry ({what, why, where} or text) as one report line."""
    if isinstance(u, dict):
        return f"{u.get('where', 'spec')}: {u.get('what', '')} — {u.get('why', '')}".strip(" —")
    return str(u)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


SCALAR_OK = {"number": _is_num, "any": lambda v: True,
             "point": lambda v: isinstance(v, list) and len(v) == 2 and all(_is_num(x) for x in v),
             "color": lambda v: isinstance(v, str) and bool(COLOR_RE.match(v))}
STATIC_OK = {  # clip key -> (test, what it must be)
    **{k: (lambda v: _is_num(v) and v >= 0, "a number >= 0") for k in ("at", "in")},
    **{k: (lambda v: _is_num(v) and v > 0, "a number > 0") for k in ("dur", "speed")},
    "audio": (lambda v: isinstance(v, bool), "true or false"),
    "text": (lambda v: isinstance(v, str) and v != "", "a non-empty string"),
    **{k: (lambda v: isinstance(v, str), "a string") for k in ("name", "font", "style", "preset")},
    "align": (lambda v: isinstance(v, str) and v in ALIGN, f"one of {sorted(ALIGN)}"),
    "blend": (lambda v: isinstance(v, str) and v in BLEND, f"one of {sorted(BLEND)}"),
    **{k: (lambda v: isinstance(v, dict) and _is_num(v.get("frames")) and v["frames"] >= 1
           and v["frames"] == int(v["frames"]) and isinstance(v.get("effect", ""), str),
           '{"effect": id, "frames": n >= 1}') for k in ("transition_in", "transition_out")},
}
NESTED = {"motion": MOTION_PARAMS, "stroke": set(STROKE_PARAMS), "shadow": set(SHADOW_PARAMS)}


def _kind(key: str) -> str:
    return "color" if key == "color" else "point" if key in ("position", "anchor") else "number"


def _check_value(where: str, v, kind: str, dur: float | None, errs: list[str]) -> None:
    """A constant of `kind`, or a keyframe list [[t, value, interp?], ...] with sane times."""
    if not is_animated(v):
        if not SCALAR_OK[kind](v):
            errs.append(f"{where}: expected a {kind} or a keyframe list, got {v!r}")
        return
    last = -1.0
    for t, val, interp in keyframes(v):
        if t < 0 or t <= last:
            errs.append(f"{where}: key times must be >= 0 and increasing (got {t})")
        if dur is not None and t > dur + 1e-6:
            errs.append(f"{where}: key at {t}s is past the clip end ({dur}s)")
        if interp not in INTERP:
            errs.append(f"{where}: interpolation {interp!r} is not one of {sorted(INTERP)}")
        if not SCALAR_OK[kind](val):
            errs.append(f"{where}: key value {val!r} is not a {kind}")
        last = t


def _check_path(where: str, p, errs: list[str]) -> None:
    if not isinstance(p, str) or not Path(p).is_absolute():
        errs.append(f"{where}: needs an absolute path, got {p!r}")
    elif not Path(p).is_file():
        errs.append(f"{where}: file not found: {p}")


def _check_clip(where: str, c: dict, ttype: str, n_audio: int, errs: list[str], unsup: list[str]) -> None:
    allowed = {"video": MEDIA_KEYS, "text": TEXT_KEYS, "audio": AUDIO_KEYS}[ttype]
    unsup += [f"{where}: key {k!r} is not supported on {ttype} tracks" for k in sorted(set(c) - allowed)]
    required = ("at", "text") if ttype == "text" else ("at", "src")
    errs += [f"{where}: '{k}' is required" for k in required if k not in c]
    dur = c.get("dur") if _is_num(c.get("dur")) else (STILL_SECONDS if ttype == "text" else None)
    for k in sorted(set(c) & allowed):
        v, w = c[k], f"{where}.{k}"
        if k in STATIC_OK and not STATIC_OK[k][0](v):
            errs.append(f"{w}: must be {STATIC_OK[k][1]}, got {v!r}")
        elif k in ("opacity", "size", "tracking", "leading", "position", "color", "gain_db"):
            _check_value(w, v, _kind(k), dur, errs)
        elif k in NESTED:
            if not isinstance(v, dict):
                errs.append(f"{w}: must be an object")
                continue
            unsup += [f"{w}: {sub!r} is not supported" for sub in sorted(set(v) - NESTED[k])]
            for sub in sorted(set(v) & NESTED[k]):
                _check_value(f"{w}.{sub}", v[sub], _kind(sub), dur, errs)
        elif k == "src":
            _check_path(w, v, errs)
        elif k == "audio_track" and not (isinstance(v, str) and re.fullmatch(r"A\d+", v)
                                         and 1 <= int(v[1:]) <= n_audio):
            errs.append(f"{w}: {v!r} does not name one of the {n_audio} audio tracks")
        elif k == "effects":
            if not isinstance(v, list) or not all(isinstance(fx, dict) and isinstance(fx.get("effect"), str)
                                                  and isinstance(fx.get("params", {}), dict) for fx in v):
                errs.append(f"{w}: must be a list of {{\"effect\": id, \"params\": {{...}}}}")
                continue
            for i, fx in enumerate(v):
                for p, pv in fx.get("params", {}).items():
                    _check_value(f"{w}[{i}].{p}", pv, "any", dur, errs)


def validate(spec) -> list[str]:
    """Raise SpecError listing every problem; return the 'unsupported' notes for a valid spec."""
    if not isinstance(spec, dict):
        raise SpecError("invalid spec: top level must be a JSON object")
    unsup = [f"top-level key {k!r} is not part of the spec" for k in sorted(set(spec) - TOP_KEYS)]
    unsup += [adapter_note(u) for u in spec.get("unsupported") or []]
    errs = [] if isinstance(spec.get("name"), str) and spec["name"] else ["'name' is required"]
    errs += [f"'{k}' must be a positive integer" for k in ("width", "height", "sample_rate")
             if (k in spec or k != "sample_rate") and not (type(spec.get(k)) is int and spec[k] > 0)]
    errs += [f"'{k}' must be a number > 0" for k in ("fps", "duration")
             if (k in spec or k == "fps") and not (_is_num(spec.get(k)) and spec[k] > 0)]
    tracks = spec.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errs.append("'tracks' must be a non-empty list")
        tracks = []
    tracks = [t if isinstance(t, dict) else {} for t in tracks]
    n_audio = sum(1 for t in tracks if t.get("type") == "audio")
    for ti, (label, t) in enumerate(zip(track_labels(tracks), tracks)):
        if t.get("type") not in ("video", "text", "audio") or not isinstance(t.get("clips", []), list):
            errs.append(f"tracks[{ti}]: needs 'type' video|text|audio and a 'clips' list")
            continue
        unsup += [f"{label}: key {k!r} is not supported" for k in sorted(set(t) - {"type", "name", "clips"})]
        for ci, c in enumerate(t.get("clips", [])):
            if isinstance(c, dict):
                _check_clip(f"{label} clip {ci + 1}", c, t["type"], n_audio, errs, unsup)
            else:
                errs.append(f"{label} clip {ci + 1}: must be an object")
        _check_overlaps(label, t.get("clips", []), errs)
    caps = spec.get("captions")
    if caps is not None:
        if not isinstance(caps, dict):
            caps = {"srt": None}
        unsup += [f"captions: key {k!r} is not supported" for k in sorted(set(caps) - {"srt"})]
        _check_path("captions.srt", caps.get("srt"), errs)
        if not errs and srt_cues(caps["srt"]) == 0:
            errs.append(f"captions.srt: no cues found in {caps['srt']}")
    for mi, m in enumerate(spec.get("markers") or []):
        if not isinstance(m, dict) or not (_is_num(m.get("at")) and m["at"] >= 0):
            errs.append(f"markers[{mi}]: needs 'at' >= 0")
            continue
        unsup += [f"markers[{mi}]: key {k!r} is not supported" for k in sorted(set(m) - {"at", "name", "comment"})]
    if errs:
        raise SpecError("invalid spec:\n  - " + "\n  - ".join(errs))
    return unsup


def _check_overlaps(label: str, clips: list, errs: list[str]) -> None:
    timed = sorted((c["at"], c.get("dur"), i) for i, c in enumerate(clips)
                   if isinstance(c, dict) and _is_num(c.get("at")))
    for (a_at, a_dur, a_i), (b_at, _, b_i) in zip(timed, timed[1:]):
        if b_at == a_at or (_is_num(a_dur) and a_at + a_dur > b_at + 1e-6):
            errs.append(f"{label}: clip {a_i + 1} overlaps clip {b_i + 1}")


def track_labels(tracks: list[dict]) -> list[str]:
    """V1, V2… for video/text tracks and A1, A2… for audio tracks, in spec order."""
    counters, out = {"V": 0, "A": 0}, []
    for t in tracks:
        prefix = "A" if t.get("type") == "audio" else "V"
        counters[prefix] += 1
        out.append(f"{prefix}{counters[prefix]}")
    return out


def load_spec(path: str | Path) -> tuple[dict, list[str]]:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"cannot read spec {path}: {exc}") from exc
    return spec, validate(spec)


# ---------- build ---------------------------------------------------------------------------------

class Build:
    """Drives one FilmCraft instance from an empty project to a saved .fcproj."""

    def __init__(self, fc: Craft, spec: dict, unsupported: list[str]):
        self.fc, self.spec, self.unsupported, self.warnings = fc, spec, unsupported, []
        self.queue: list[tuple[str, dict]] = []      # lệnh đặt keyframe gửi dồn (FilmCraft ~45 ms / lệnh gửi lẻ)
        self.rate = fps_fraction(spec["fps"])
        self.labels = track_labels(spec["tracks"])
        self.n_video = sum(1 for lb in self.labels if lb[0] == "V")
        self.n_audio = len(self.labels) - self.n_video
        self.expect = {"keyframes": 0, "effects": 0, "linked_audio": 0}
        self.jobs: list[dict] = []
        for label, t in zip(self.labels, spec["tracks"]):
            starts = sorted(c["at"] for c in t.get("clips", []))
            for i, c in enumerate(t.get("clips", [])):
                later = [a for a in starts if a > c["at"]]
                self.jobs.append({"spec": c, "type": t["type"], "track": label, "where": f"{label} clip {i + 1}",
                                  "start": self.ticks(c["at"]), "next_at": later[0] if later else None,
                                  "fx": [], "keys": []})

    def cmd(self, command: str, params: dict | None = None):
        """Lệnh thường: gửi hết hàng chờ trước để giữ thứ tự, rồi gửi lệnh này và đọc kết quả."""
        self.flush()
        return self.fc.cmd(command, params)

    def qcmd(self, command: str, params: dict) -> None:
        self.queue.append((command, params))

    def flush(self) -> None:
        if self.queue:
            q, self.queue = self.queue, []
            self.fc.pipeline(q)

    def ticks(self, seconds: float) -> int:
        return sec_ticks(seconds, self.rate)

    def run(self, out: Path) -> None:
        self.load_catalog()
        self.cmd("file.newSequence", {"name": self.spec["name"], "width": self.spec["width"],
                                      "height": self.spec["height"], "fps": self.spec["fps"],
                                      "sampleRate": self.spec.get("sample_rate", 48000),
                                      "video": self.n_video, "audio": self.n_audio})
        for label, t in zip(self.labels, self.spec["tracks"]):
            if t.get("name"):
                self.qcmd("timeline.setTrack", {"track": label, "name": t["name"]})
        self.import_media()
        for job in self.jobs:
            self.place_text(job) if job["type"] == "text" else self.place_media(job)
        self.info = self.inspect_clips()
        for job in self.jobs:          # which returned id is the picture and which the sound
            job["video"] = next((i for i in job["ids"] if self.info[i]["track"][0] == "V"), None)
            job["audio"] = [i for i in job["ids"] if self.info[i]["track"][0] == "A"]
        self.apply_effects()
        for job in self.jobs:
            self.decorate(job)
        self.apply_presets()
        self.apply_transitions()
        if self.spec.get("captions"):
            self.cmd("captions.import", {"path": self.spec["captions"]["srt"]})
        for m in self.spec.get("markers") or []:
            self.qcmd("markers.add", {"target": "program", "time": self.ticks(m["at"]),
                                      "name": m.get("name", ""), "comment": m.get("comment", "")})
        if "duration" in self.spec:    # the spec's length becomes the sequence In/Out
            self.qcmd("markers.markIn", {"target": "program", "time": 0})
            self.qcmd("markers.markOut", {"target": "program", "time": self.ticks(self.spec["duration"])})
        self.final = self.inspect_clips()
        self.cmd("file.saveAs", {"path": str(out)})

    def load_catalog(self) -> None:
        """Effect ids, kinds and param types; unknown effect ids or params fail before any edit."""
        self.catalog = {e["id"]: {"kind": e["kind"], "params": {p["id"]: p["type"] for p in e["paramInfo"]}}
                        for e in self.cmd("effects.list", {"detail": True})}
        errs = []
        for job in self.jobs:
            for fx in job["spec"].get("effects", []):
                known = self.catalog.get(fx["effect"], {"kind": None, "params": {}})
                if known["kind"] not in ("Video", "Audio"):
                    errs.append(f"{job['where']}: unknown FilmCraft effect id {fx['effect']!r} (see effects.list)")
                elif set(fx.get("params", {})) - set(known["params"]):
                    errs.append(f"{job['where']}: {fx['effect']} has no param "
                                f"{sorted(set(fx['params']) - set(known['params']))}; it has {sorted(known['params'])}")
        if errs:
            raise SpecError("invalid spec:\n  - " + "\n  - ".join(errs))

    def import_media(self) -> None:
        paths = sorted({j["spec"]["src"] for j in self.jobs if j["type"] != "text"})
        self.media = {}
        if paths:
            res = self.cmd("file.import", {"paths": paths})
            if res.get("errors"):
                raise CraftError(f"file.import failed: {res['errors']}")
            for p in self.cmd("file.mediaProperties", {"items": res["items"]}):
                self.media[p["path"]] = {"item": p["item"], "type": p["type"], "audio": "audio" in p,
                                         "seconds": p["duration"]["seconds"]}

    def fit(self, job: dict, natural: float) -> float:
        """A clip without 'dur' runs its natural length, but never over the next clip on its track."""
        room = None if job["next_at"] is None else job["next_at"] - job["spec"]["at"]
        if room is None or natural <= room + 1e-6:
            return natural
        self.warnings.append(f"{job['where']}: runs {natural:.2f}s but the next clip on {job['track']} starts "
                             f"{room:.2f}s later; trimmed to {room:.2f}s (give it its own track to keep the tail)")
        return room

    def span_frames(self, at: float, dur: float) -> int:
        """Snapped start to snapped end: clips that touch in seconds still touch in frames (rounding the
        start and the length apart can push a clip one frame into the next)."""
        return max(1, to_frames(at + dur, self.rate) - to_frames(at, self.rate))

    def place_media(self, job: dict) -> None:
        c, where = job["spec"], job["where"]
        m, on_video = self.media.get(c["src"]), job["track"][0] == "V"
        if m is None:
            raise CraftError(f"{where}: FilmCraft did not import {c['src']}")
        if on_video == (m["type"] == "AudioOnly") or (not on_video and m["type"] == "Still"):
            raise SpecError(f"{where}: {c['src']} ({m['type']}) cannot go on track {job['track']}")
        speed, src_in = c.get("speed", 100) / 100, (0 if m["type"] == "Still" else c.get("in", 0))
        natural = STILL_SECONDS if m["type"] == "Still" else (m["seconds"] - src_in) / speed
        dur = c.get("dur") or self.fit(job, natural)
        if m["type"] != "Still" and (natural <= 0 or dur > natural + 1 / float(self.rate)):
            raise SpecError(f"{where}: in={src_in}s + dur={dur}s at {speed * 100:g}% needs more than the "
                            f"{m['seconds']:.2f}s of {c['src']}")
        frames = self.span_frames(c["at"], dur)
        job["dur"] = frame_ticks(frames, self.rate)
        params = {"item": m["item"], "track": job["track"], "time": job["start"], "sourceIn": self.ticks(src_in),
                  "duration": frame_ticks(math.ceil(frames * speed - 1e-6), self.rate)}
        if on_video:
            params["audio"] = bool(m["audio"] and c.get("audio", True))
            if params["audio"] and not self.n_audio:
                self.warnings.append(f"{where}: the source has sound but the spec has no audio track; video only")
                params["audio"] = False
            if params["audio"]:
                params["audioTrack"] = c.get("audio_track", "A1")
                self.expect["linked_audio"] += 1
        job["ids"] = self.cmd("timeline.place", params)["clips"]
        if speed != 1:     # whole source frames, re-timed, then trimmed back to the exact length
            self.cmd("clip.speedDuration", {"clips": job["ids"], "speed": c["speed"], "ripple": False})
            got = self.inspect_clips()[job["ids"][0]]["frames"]
            if got > frames:      # linked sound follows the trim
                self.cmd("timeline.trim", {"clip": job["ids"][0], "edge": "out", "mode": "regular",
                                           "deltaFrames": frames - got})

    def place_text(self, job: dict) -> None:
        c = job["spec"]
        frames = self.span_frames(c["at"], c.get("dur") or self.fit(job, STILL_SECONDS))
        job["dur"] = frame_ticks(frames, self.rate)
        params = {"text": c["text"], "seconds": float(frames / self.rate),
                  "track": int(job["track"][1:]) - 1, "time": job["start"]}
        params.update({k: first_value(c[k]) for k in ("size", "position") if k in c})
        params.update({api: c[k] for k, api in (("font", "font"), ("style", "fontStyle")) if k in c})
        if "font" in c:
            if not hasattr(self, "fonts"):
                self.fonts = {f["family"]: f["styles"] for f in self.cmd("fonts.list", {"system": True})}
            styles = self.fonts.get(c["font"], [])
            if not styles or c.get("style", styles[0]) not in styles:
                self.warnings.append(f"{job['where']}: font {c['font']!r} style {c.get('style')!r} is not "
                                     f"installed (styles found: {styles}); FilmCraft will substitute")
        job["ids"] = [self.cmd("graphics.newText", params)["clip"]]

    def inspect_clips(self) -> dict[int, dict]:
        seq = self.cmd("sequence.inspect")
        return {it["clip"]: {"track": f"{p}{ti + 1}", "start": it["start"], "frames": it["durationFrames"],
                             "sourceIn": it["sourceIn"], "speed": it["speed"],
                             "effects": [e["effect"] for e in it["effects"]]}
                for p, key in (("V", "video"), ("A", "audio"))
                for ti, track in enumerate(seq[key]) for it in track["items"]}

    def apply_effects(self) -> None:
        """effects.apply every spec effect, then find where FilmCraft put each one in the stack."""
        before = {cid: list(i["effects"]) for cid, i in self.info.items()}
        applied: dict[int, list[dict]] = {}
        for job in self.jobs:
            for fx in job["spec"].get("effects", []):
                kind = self.catalog[fx["effect"]]["kind"]
                target = job["video"] if kind == "Video" else (job["audio"] or [None])[0]
                if target is None:
                    self.unsupported.append(f"{job['where']}: {kind} effect {fx['effect']!r} needs a clip with "
                                            f"{'picture' if kind == 'Video' else 'sound'}")
                    continue
                entry = {"clip": target, "fx": fx, "index": fx["effect"]}
                self.expect["effects"] += 1
                job["fx"].append(entry)
                if fx["effect"] not in before[target]:      # intrinsic ones (motion, volume…) are reused
                    self.qcmd("effects.apply", {"clips": [target], "effect": fx["effect"]})
                    applied.setdefault(target, []).append(entry)
        self.info = self.inspect_clips()
        for cid, entries in applied.items():
            after = self.info[cid]["effects"]
            idx = new_effect_indexes(before[cid], after)
            if [after[i] for i in idx] != [e["fx"]["effect"] for e in entries]:
                raise CraftError(f"clip {cid}: effect stack {after} does not hold "
                                 f"{[e['fx']['effect'] for e in entries]} in order")
            for i, e in zip(idx, entries):
                e["index"] = i
        for e in (e for job in self.jobs for e in job["fx"]):
            stack = self.info[e["clip"]]["effects"]
            i = e["index"] if isinstance(e["index"], int) else stack.index(e["index"])
            e["vref"] = (stack[i], stack[:i].count(stack[i]))    # (effect id, nth of that id) survives re-open

    def set_value(self, job: dict, clip: int, effect, param: str, value, vref: tuple) -> None:
        """A constant, or one keyframe per key (timeline time) plus its interpolation (media time)."""
        if not is_animated(value) or self.catalog.get(vref[0], {}).get("params", {}).get(param) == "curve":
            self.qcmd("effects.setParam", {"clip": clip, "effect": effect, "param": param, "value": value})
            return
        info, keys = self.info[clip], frame_keys(value, self.rate)
        if len(keys) < len(value):
            self.warnings.append(f"{job['where']}: {param} has {len(value)} keys but only {len(keys)} distinct "
                                 "frames; keys inside one frame were merged (last value kept)")
        for t, v, interp in keys:
            at = info["start"] + self.ticks(t)
            self.qcmd("effects.setParam", {"clip": clip, "effect": effect, "param": param, "value": v,
                                           "time": at, "keyframe": True})
            if interp != "linear":
                self.qcmd("effects.setInterpolation", {"clip": clip, "effect": effect, "param": param,
                                                       "mediaTime": media_time(info, at),
                                                       "interpolation": INTERP[interp]})
        self.expect["keyframes"] += len(keys)
        job["keys"].append({"clip": clip, "vref": vref, "param": param})

    def decorate(self, job: dict) -> None:
        c, vid = job["spec"], job["video"]
        for cid in job["ids"] if "name" in c else []:
            self.qcmd("clip.rename", {"clip": cid, "name": c["name"]})
        if "gain_db" in c and job["audio"] and is_animated(c["gain_db"]):       # fades: Volume level keys (dB)
            self.set_value(job, job["audio"][0], "volume", "level", c["gain_db"], ("volume", 0))
        elif "gain_db" in c and job["audio"]:
            self.qcmd("clip.audioGain", {"clips": job["audio"], "mode": "set", "db": c["gain_db"]})
        elif "gain_db" in c:
            self.unsupported.append(f"{job['where']}: gain_db on a clip without sound")
        for k, v in (c.get("motion", {}).items() if vid else ()):
            if k in MOTION_PARAMS:
                self.set_value(job, vid, "motion", k, v, ("motion", 0))
        for param, value in (("opacity", c.get("opacity")), ("blend", BLEND.get(c.get("blend")))):
            if vid and value is not None:
                self.set_value(job, vid, "opacity", param, value, ("opacity", 0))
        if job["type"] == "text":
            self.style_text(job)
        for e in job["fx"]:
            for p, v in e["fx"].get("params", {}).items():
                self.set_value(job, e["clip"], e["index"], p, v, e["vref"])

    def style_text(self, job: dict) -> None:
        c, vid, ref = job["spec"], job["video"], ("graphic_text", 0)
        props = {"align": ALIGN[c["align"]]} if "align" in c else {}
        props.update({param: c[k] for k, param in TEXT_PARAMS.items()        # size/position went to newText
                      if k in c and (k not in ("size", "position") or is_animated(c[k]))})
        for key, table in (("stroke", STROKE_PARAMS), ("shadow", SHADOW_PARAMS)):
            if key in c:
                props.update({key: True, **{table[k]: v for k, v in c[key].items() if k in table}})
        for param, value in props.items():
            self.set_value(job, vid, "graphic_text", param, value, ref)

    def apply_presets(self) -> None:
        wanted = {j["spec"]["preset"] for j in self.jobs if "preset" in j["spec"]}
        names = [p["name"] for p in self.cmd("presets.list")["presets"]] if wanted else []
        if any(match_preset(w, names) is None for w in wanted) and USER_PRESETS.is_file():
            self.cmd("presets.import", {"path": str(USER_PRESETS)})     # read-only copy of the user's presets
            names = [p["name"] for p in self.cmd("presets.list")["presets"]]
        for job in (j for j in self.jobs if "preset" in j["spec"]):
            name = match_preset(job["spec"]["preset"], names)
            if name is None:
                self.unsupported.append(f"{job['where']}: preset {job['spec']['preset']!r} not found "
                                        f"(built-in or {USER_PRESETS})")
                continue
            self.cmd("presets.apply", {"preset": name, "clips": [job["ids"][0]]})
            job["preset"] = name

    def apply_transitions(self) -> None:
        for job in self.jobs:
            for edge in ("in", "out"):
                tr, video = job["spec"].get(f"transition_{edge}"), job["type"] != "audio"
                if tr:
                    self.qcmd("sequence.applyVideoTransition" if video else "sequence.applyAudioTransition",
                              {"clip": job["ids"][0], "frames": int(tr["frames"]), "edge": edge,
                               "effect": tr.get("effect", "cross_dissolve" if video else "constant_power")})

    def expected(self) -> dict:
        edges = {(j["track"], j["start"] + (j["dur"] if e == "out" else 0)) for j in self.jobs
                 for e in ("in", "out") if j["spec"].get(f"transition_{e}")}
        exp = {"video_tracks": self.n_video, "audio_tracks": self.n_audio, "track_names": len(self.labels),
               "clips": len(self.jobs), "linked_audio": self.expect["linked_audio"],
               "track_items": len(self.jobs) + self.expect["linked_audio"],
               "keyframes": self.expect["keyframes"], "effects": self.expect["effects"],
               "text": sum(1 for j in self.jobs if j["type"] == "text"), "transitions": len(edges),
               "captions": srt_cues(self.spec["captions"]["srt"]) if self.spec.get("captions") else 0,
               "markers": len(self.spec.get("markers") or [])}
        return {**exp, "in_out": 1} if "duration" in self.spec else exp


# ---------- verify (fresh instance) ---------------------------------------------------------------

def verify(out: Path, b: Build, workdir: Path, n_frames: int, frame_stem: Path) -> tuple[dict, list[str]]:
    """Re-open OUT in a new FilmCraft and count what it holds. Returns (actual counts, frame paths)."""
    with Craft("filmcraft", workdir) as fc:
        fc.cmd("file.open", {"path": str(out)})
        seq = fc.cmd("sequence.inspect")
        tracks = {f"{p}{i + 1}": t for p, key in (("V", "video"), ("A", "audio")) for i, t in enumerate(seq[key])}
        at = {(label, it["start"]): it for label, t in tracks.items() for it in t["items"]}

        def reopened(cid: int) -> dict | None:
            f = b.final.get(cid)
            return at.get((f["track"], f["start"])) if f else None

        names = [t.get("name") for t in b.spec["tracks"]]
        act = {"video_tracks": len(seq["video"]), "audio_tracks": len(seq["audio"]),
               "track_names": sum(1 for lb, n in zip(b.labels, names)
                                  if lb in tracks and tracks[lb]["name"] == (n or tracks[lb]["name"])),
               "clips": sum(1 for j in b.jobs if at.get((j["track"], j["start"]), {}).get("duration") == j["dur"]),
               "linked_audio": sum(1 for j in b.jobs if j["video"] for a in j["audio"] if reopened(a)),
               "track_items": len(at), "text": 0,
               "keyframes": sum(fx["params"].get(k["param"], {}).get("keyframes", 0) for j in b.jobs for k in j["keys"]
                                if (fx := _find_effect(reopened(k["clip"]), k["vref"]))),
               "effects": sum(1 for j in b.jobs for e in j["fx"] if _find_effect(reopened(e["clip"]), e["vref"])),
               "transitions": sum(len(t["transitions"]) for t in tracks.values()),
               "captions": sum(len(t["captions"]) for t in fc.cmd("captions.list")["tracks"]),
               "markers": sum(1 for m in b.spec.get("markers") or [] if any(
                   x["start"] == b.ticks(m["at"]) and x["name"] == m.get("name", "") for x in seq["markers"]))}
        for j in (j for j in b.jobs if j["type"] == "text" and reopened(j["video"])):
            layers = fc.cmd("graphics.list", {"clip": reopened(j["video"])["clip"]})["layers"]
            act["text"] += any(layer.get("text") == j["spec"]["text"] for layer in layers)
        if "duration" in b.spec:
            act["in_out"] = int(seq["in"] == 0 and seq["out"] == b.ticks(b.spec["duration"]))
        frames = []
        for i in range(n_frames):
            t = frame_ticks(to_frames((i + 0.5) / n_frames * seq["duration"] / TICKS_PER_SECOND, b.rate), b.rate)
            frames.append(f"{frame_stem}.frame{i + 1:02d}.png")
            fc.cmd("file.exportFrame", {"path": frames[-1], "target": "program", "time": t, "format": "png"})
    return act, frames


def _find_effect(clip: dict | None, vref: tuple) -> dict | None:
    same = [e for e in clip["effects"] if e["effect"] == vref[0]] if clip else []
    return same[vref[1]] if vref[1] < len(same) else None


# ---------- CLI -----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a FilmCraft .fcproj from a craft timeline spec.")
    ap.add_argument("spec", help="timeline spec (*.craft.json)")
    ap.add_argument("out", help="project to write (*.fcproj)")
    ap.add_argument("--report", help="write the verification report (JSON) here")
    ap.add_argument("--frames", type=int, default=0, help="export N QA frames of the program monitor")
    ap.add_argument("--workdir", help="app data/logs folder (default: a temp folder, removed on success)")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    report_path = Path(a.report).resolve() if a.report else None
    workdir = Path(a.workdir).resolve() if a.workdir else Path(tempfile.mkdtemp(prefix="fc_build-"))
    try:
        if out.suffix != ".fcproj":
            raise SpecError(f"OUT must end in .fcproj: {out}")
        spec, unsupported = load_spec(a.spec)
        out.parent.mkdir(parents=True, exist_ok=True)
        with Craft("filmcraft", workdir / "build") as fc:
            b = Build(fc, spec, unsupported)
            b.run(out)
        expected = b.expected()
        actual, frames = verify(out, b, workdir / "verify", max(a.frames, 0), (report_path or out).with_suffix(""))
    except SpecError as exc:
        print(f"fc_build: {exc}", file=sys.stderr)
        return 2
    except CraftError as exc:
        print(f"fc_build: {exc}\n  app data and logs kept in {workdir}", file=sys.stderr)
        return 1
    mismatches = {k: {"expected": v, "actual": actual.get(k)} for k, v in expected.items() if actual.get(k) != v}
    report = {"spec": str(Path(a.spec).resolve()), "out": str(out), "ok": not mismatches,
              "expected": expected, "actual": actual, "mismatches": mismatches,
              "unsupported": b.unsupported, "warnings": b.warnings, "frames": frames,
              "presets_applied": {j["where"]: j["preset"] for j in b.jobs if j.get("preset")}}
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    notes = [f"unsupported: {n}" for n in b.unsupported] + [f"warning: {n}" for n in b.warnings]
    notes += [f"mismatch {k}: expected {v['expected']}, found {v['actual']}" for k, v in mismatches.items()]
    for note in notes:
        print(f"fc_build: {note}", file=sys.stderr)
    print(f"fc_build: {'MISMATCH' if mismatches else 'OK'} {out}" + (f"  report: {report_path}" if report_path else ""))
    if not mismatches and not a.workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
