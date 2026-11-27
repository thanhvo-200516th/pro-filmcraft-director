#!/usr/bin/env python3
"""fc_build_fast — như fc_build.py nhưng ghi tham số / keyframe thẳng vào .fcproj thay vì gửi từng lệnh qua app.

Đo trên KB02 (299 clip, 1491 keyframe): fc_build mất ~211 s, 185 s trong số đó là ~7 000 lệnh đặt tham số
(FilmCraft ~24 ms / lệnh, không có lệnh hàng loạt). Cách làm:
  1. App dựng khung như cũ (đặt clip, import, effects.apply, chuyển cảnh, đổi tên).
  2. `Build.set_value` KHÔNG gửi lệnh nữa mà ghi nhớ (clip, effect, tham số, giá trị / keyframe).
  3. Sau khi app lưu file, các giá trị được ghi thẳng vào JSON `.fcproj` (kiểu Float / Vec2 / Color / Choice / Bool / Text).
  4. `verify` của fc_build mở lại file đã vá bằng một FilmCraft mới và đếm keyframe / effect → báo cáo là số đo thật.
Giá trị không chuyển được kiểu (curve, wheel, choice lạ…) tự quay về đường lệnh cũ.

    python3 fc_build_fast.py SPEC.craft.json OUT.fcproj [--report R.json] [--frames N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fc_build as fb  # noqa: E402

INTERP_JSON = {"linear": "Linear", "bezier": "Bezier", "easeIn": "EaseIn", "easeOut": "EaseOut", "hold": "Hold"}
INFLUENCE = 1 / 3


def _hex(c: str) -> list[float]:
    c = c.lstrip("#")
    rgba = [int(c[i:i + 2], 16) / 255 for i in range(0, len(c), 2)]
    return [*rgba, 1.0] if len(rgba) == 3 else rgba


def tagged(info: dict, value):
    """Giá trị spec → kiểu lưu trong .fcproj; None nếu không chắc (rồi quay về lệnh app)."""
    t = info["type"]
    if t in ("float", "angle") and fb._is_num(value):
        return {"Float": float(value)}
    if t == "bool" and isinstance(value, bool):
        return {"Bool": value}
    if t == "point" and isinstance(value, list) and len(value) == 2 and all(fb._is_num(x) for x in value):
        return {"Vec2": {"x": float(value[0]), "y": float(value[1])}}
    if t == "color" and isinstance(value, str) and fb.COLOR_RE.match(value):
        return {"Color": _hex(value)}
    if t == "text" and isinstance(value, str):
        return {"Text": value}
    if t == "choice":
        opts = info.get("options") or []
        if isinstance(value, str) and value in opts:
            return {"Choice": opts.index(value)}
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(opts):
            return {"Choice": value}
    return None


class FastBuild(fb.Build):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.patches: list[dict] = []
        self.pinfo: dict[tuple[str, str], dict] = {}
        self.fallback = 0

    def load_catalog(self) -> None:
        super().load_catalog()
        for e in self.cmd("effects.list", {"detail": True}):
            for p in e["paramInfo"]:
                self.pinfo[(e["id"], p["id"])] = p

    def set_value(self, job, clip, effect, param, value, vref) -> None:
        info = self.pinfo.get((vref[0], param))
        animated = fb.is_animated(value)
        vals = ([v for _, v, _ in fb.keyframes(value)] if animated else [value]) if info else []
        if not info or info["type"] == "curve" or any(tagged(info, v) is None for v in vals):
            self.fallback += 1
            return super().set_value(job, clip, effect, param, value, vref)
        if not animated:
            self.patches.append({"clip": clip, "effect": effect, "param": param, "const": tagged(info, value)})
            return
        meta, keys = self.info[clip], fb.frame_keys(value, self.rate)
        if len(keys) < len(value):
            self.warnings.append(f"{job['where']}: {param} has {len(value)} keys but only {len(keys)} distinct "
                                 "frames; keys inside one frame were merged (last value kept)")
        out = []
        for t, v, interp in keys:
            at = meta["start"] + self.ticks(t)
            out.append({"time": fb.media_time(meta, at), "value": tagged(info, v), "interp": INTERP_JSON[interp],
                        "out_influence": INFLUENCE, "in_influence": INFLUENCE})
        self.patches.append({"clip": clip, "effect": effect, "param": param, "keys": out})
        self.expect["keyframes"] += len(keys)
        job["keys"].append({"clip": clip, "vref": vref, "param": param})


def patch_fcproj(path: Path, patches: list[dict]) -> int:
    """Ghi các giá trị đã ghi nhớ vào JSON dự án đã lưu. Trả về số tham số đã ghi."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    seq = next(v["kind"]["Sequence"] for v in doc["project"]["items"].values() if "Sequence" in v["kind"])
    items = {it["id"]: it for t in seq["video_tracks"] + seq["audio_tracks"] for it in t["items"]}
    for p in patches:
        effects = items[p["clip"]]["effects"]
        e = effects[p["effect"]] if isinstance(p["effect"], int) else next(x for x in effects if x["effect"] == p["effect"])
        slot = e["params"][p["param"]]
        if "const" in p:
            slot["value"] = p["const"]
        else:
            slot["keyframes"] = sorted(p["keys"], key=lambda k: k["time"])
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(patches)


_build_cls: dict = {}
_orig_verify = fb.verify


def _verify(out: Path, b, workdir: Path, n_frames: int, frame_stem: Path):
    n = patch_fcproj(out, b.patches)
    print(f"fc_build_fast: ghi thẳng {n} tham số vào .fcproj ({b.fallback} quay về lệnh app)", file=sys.stderr)
    return _orig_verify(out, b, workdir, n_frames, frame_stem)


fb.Build = FastBuild
fb.verify = _verify

if __name__ == "__main__":
    sys.exit(fb.main())
