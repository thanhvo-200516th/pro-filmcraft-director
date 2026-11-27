"""Rule 4 (người dùng chốt 2026-11-11): không để chữ tĩnh — mọi lớp chữ có vào, giữ và ra chuyển động mượt.

Thông số đo từ @__dviet (video 7706183278461570356 + 4 video kênh, 2026-11-11, khung @24 fps quy ra giây):
  - Vào "soft_in": KHÔNG nảy / phóng — mờ nhoè thành nét. Chữ chính 7 khung (0,29 s): opacity 0 → 15 → 65 → 88 → 100 %
    ở khung 0/1/3/5/7, blur 22 → 9 → 3 → 0 (ease-out giữa bậc 2 và bậc 3). Dòng nối / phụ đề 4 khung (0,17 s).
  - Giữ: kênh chỉ trôi ≤ 1,4 % (gần như đứng). Người dùng muốn "không tĩnh" → phóng chậm đều 100 → 103 % (chữ chính) /
    101,5 % (phụ đề) suốt lúc giữ, anchor tại chữ, không nảy; dưới ngưỡng gây giật, vẫn thấy chữ "thở".
  - Ra "soft_out": opacity 100 → 0 + blur 0 → 12 trong 4 khung (0,13 s), kết thúc đúng cuối clip (đúng điểm cắt).
Chỉ BỔ SUNG phần còn thiếu: clip đã có kiểu vào riêng (slam, type, glow_in…) giữ nguyên kiểu vào; đã có chuyển động lúc giữ
thì không thêm; đã có transition_out / mờ ra thì không thêm ra.

    from text_motion import ensure_motion
    n = ensure_motion(items, fps)        # items = [(lane, clip)] của FX / MotionFX — sửa clip tại chỗ

Hồ sơ tuỳ chọn 'minimal-edu' (references/minimal-edu-style.json, chỉ khi profile.json bật): ensure_motion(items, fps,
profile=prof, cuts=[...]) — vào ngắn theo khung của chữ chính / chữ nhỏ, ra = mờ `exit_frames` khung (không nhoè), và
clip kết thúc `end_before_cut_frames` khung trước điểm cắt gần cuối clip (chỉ rút ngắn). profile=None → như cũ.

Hồ sơ minimal-edu 3.6.4: thư viện kiểu vào (ENTRANCES) + EntranceStyles xoay vòng 6–10 kiểu mỗi video, giữ / ra như dưới.
Hồ sơ minimal-edu 3.6.3 — typography chuyển động mượt ("lả lướt"): vào / giữ / ra là MỘT chuỗi keyframe của hiệu ứng `transform`
(vị trí Y, scale) + gaussian_blur + opacity, easing easeIn (hãm lúc đến) / easeOut (hãm lúc đi); FilmCraft không có bezier tuỳ ý
nên dùng đúng ba kiểu tích hợp. Một bộ "vật lý" cho cả video (KIN); chỉ khoảng trễ từ (stagger) đổi theo cụm.
"""
from __future__ import annotations

from style_profile import active, get

TEXT_LANES = {"text", "text_top", "text_low", "text_img"}
KEY_LANES = {"text", "text_top", "text_img"}          # chữ chính / tiêu đề; text_low = phụ đề, dòng nối
SOFT_IN_KEY = ([(0.0, 0), (0.042, 15), (0.125, 65), (0.208, 88), (0.292, 100)],
               [(0.0, 22), (0.125, 9), (0.208, 3), (0.292, 0)])
SOFT_IN_CAP = ([(0.0, 0), (0.042, 40), (0.083, 75), (0.167, 100)], [(0.0, 14), (0.167, 0)])
SOFT_OUT_S, OUT_BLUR = 0.13, 12
HOLD_SCALE = {"key": 103.0, "cap": 101.5}
ENTRANCE_WINDOW = 0.35      # có key trong 0,35 s đầu = đã có kiểu vào
MIN_HOLD_S = 0.6            # clip ngắn hơn: chỉ vào / ra, không thêm phóng giữ
MIN_CLIP_S = 0.3            # clip ngắn hơn (khung đổi font, chữ chớp…) giữ nguyên: hiệu ứng cố ý tức thời, thêm key sẽ trùng mốc
CUT_SNAP_S = 0.25           # hồ sơ: điểm cắt cách cuối clip ≤ 0,25 s (về phía trước) thì clip kết thúc theo điểm cắt đó
# ---- typography chuyển động của hồ sơ minimal-edu (mỗi số có thể ghi đè bằng hồ sơ: profile key text.kinetic.<tên>) ----
KIN = {
    "in_frames": 10,          # profile key: text.kinetic.in_frames — vào 10 khung (≈ 330 ms)
    "dy": 48,                 # profile key: text.kinetic.dy — Y +48 px → 0
    "scale_from": 90,         # profile key: text.kinetic.scale_from — scale 90 % → 100 %
    "blur_from": 12,          # profile key: text.kinetic.blur_from — blur 12 → 0 …
    "blur_frames": 6,         # profile key: text.kinetic.blur_frames — … trong 6 khung đầu
    "opacity_frames": 4,      # profile key: text.kinetic.opacity_frames — opacity 0 → 100 trong 4 khung đầu
    "stagger_frames": 2,      # profile key: text.kinetic.stagger_frames — mỗi từ trễ ≥ 2 khung so với từ trước
    "stagger_cap_frames": 8,  # profile key: text.kinetic.stagger_cap_frames — trễ tối đa 8 khung so với lúc nói
    "overshoot": 106,         # profile key: text.kinetic.overshoot — từ lớn vọt 106 % rồi lắng …
    "overshoot_frames": 12,   # profile key: text.kinetic.overshoot_frames — … xong sau 12 khung (không áp cho số / tiền)
    "hold_scale": 103,        # profile key: text.kinetic.hold_scale — lúc giữ phóng chậm 100 → 103 %
    "min_hold_frames": 12,    # profile key: text.kinetic.min_hold_frames — giữ ngắn hơn thì không phóng
    "exit_frames": 5,         # profile key: text.kinetic.exit_frames — ra 5 khung (≈ nửa lúc vào)
    "exit_dy": -24,           # profile key: text.kinetic.exit_dy — Y 0 → −24 px
    "exit_blur": 6,           # profile key: text.kinetic.exit_blur — blur 0 → 6
}
MIN_HOLD_WINDOW_FRAMES = 1  # profile key: text.kinetic.min_hold_window_frames — cửa sổ giữ ngắn nhất còn thêm phóng chậm (clip 0,6–0,95 s)
SHORT_HOLD_FLOOR = 0.1      # profile key: text.kinetic.short_hold_floor — cửa sổ ngắn: biên độ phóng ≥ 10 % của (hold_scale − 100)
MIN_ENTRY_FRAMES = 3        # clip rất ngắn: vào co lại, tối thiểu 3 khung
SKIP_KEYS = ("src", "text", "name", "font", "style", "color", "shadow", "position", "align", "tracking", "size")


def _key_times(obj) -> list[float]:
    out: list[float] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += _key_times(v)
    elif isinstance(obj, list):
        if obj and all(isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float)) and not isinstance(x[0], bool)
                       for x in obj) and len(obj) >= 2:
            out += [float(x[0]) for x in obj]
        else:
            for v in obj:
                out += _key_times(v)
    return out


def _key_spans(obj) -> list[list[float]]:
    """Mốc thời gian của từng chuỗi keyframe riêng (mỗi thuộc tính / tham số một chuỗi)."""
    out: list[list[float]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP_KEYS and k != "transition_out":
                out += _key_spans(v)
    elif isinstance(obj, list):
        if len(obj) >= 2 and all(isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float))
                                 and not isinstance(x[0], bool) for x in obj):
            out.append([float(x[0]) for x in obj])
        else:
            for v in obj:
                out += _key_spans(v)
    return out


def has_hold_motion(c: dict, t0: float, t1: float) -> bool:
    """Có chuỗi key chuyển động (motion / effect hình học, không tính mờ / nhoè vào-ra) trải ≥ 60 % đoạn giữ t0..t1."""
    src = {"motion": c.get("motion"), "effects": [e for e in c.get("effects", []) if e.get("effect") != "gaussian_blur"]}
    need = 0.6 * max(1e-3, t1 - t0)
    return any(min(k) <= t0 + 0.35 and max(k) >= t1 - 0.35 and max(k) - min(k) >= need for k in _key_spans(src))


def _static_hold(c: dict) -> bool:
    """Tiêu chí của static_report: không có chuỗi key chuyển động trải suốt lúc giữ (từ min(0,6 s, dur/3) tới trước đoạn ra)."""
    return not has_hold_motion(c, min(0.6, c["dur"] / 3), c["dur"] - SOFT_OUT_S)


def _anim_times(c: dict) -> list[float]:
    return _key_times({k: v for k, v in c.items() if k not in SKIP_KEYS and k != "transition_out"})


def _effect(c: dict, name: str) -> dict | None:
    return next((e for e in c.get("effects", []) if e.get("effect") == name), None)


def _png_center(src: str) -> list[float] | None:
    """Tâm phần có nét của ảnh chữ PNG khung đầy (text_img) — để phóng quanh chữ, không quanh tâm khung."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            box = im.getchannel("A").getbbox() if "A" in im.getbands() else None
        return [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2] if box else None
    except Exception:  # noqa: BLE001 — không đọc được ảnh thì dùng tâm khung
        return None


def _anchor(c: dict) -> list[float]:
    pos = c.get("position")
    if isinstance(pos, (list, tuple)) and len(pos) == 2 and all(isinstance(v, (int, float)) for v in pos):
        return [float(pos[0]), float(pos[1])]
    if str(c.get("src", "")).lower().endswith(".png"):
        return _png_center(c["src"]) or [540.0, 960.0]
    return [540.0, 960.0]


def soft_in(c: dict, lane: str) -> None:
    op, bl = SOFT_IN_KEY if lane in KEY_LANES else SOFT_IN_CAP
    end = max(1e-3, c["dur"] - 1e-3)
    c["opacity"] = [[min(t, end), v] for t, v in op]
    c.setdefault("effects", []).append({"effect": "gaussian_blur",
                                        "params": {"blurriness": [[min(t, end), v] + (["easeIn"] if i else []) for i, (t, v) in enumerate(bl)]}})


def kinetic_params(prof: dict | None) -> dict:
    """Bộ thông số typography chuyển động: KIN, ghi đè bằng `text.kinetic` của hồ sơ nếu có."""
    return {**KIN, **((prof or {}).get("text", {}).get("kinetic") or {})}


def profile_in_frames(prof: dict) -> tuple[int, int]:
    """(khung vào chữ nhỏ, khung vào chữ chính) của hồ sơ: một bộ vật lý cho cả hai (kinetic.in_frames, 10 khung)."""
    n = kinetic_params(prof)["in_frames"]
    return n, n


def hold_drift(c: dict, lane: str, t0: float, t1: float) -> None:
    peak = HOLD_SCALE["key" if lane in KEY_LANES else "cap"]
    ax = _anchor(c)
    t1 = min(round(t1, 3), c["dur"])                 # làm tròn không được vượt cuối clip (fc_build chặn key quá cuối)
    t0 = min(round(t0, 3), t1 - 1e-3)
    fx = {"effect": "transform", "params": {"anchor": ax, "position": ax, "uniform_scale": True,
                                            "scale_height": [[t0, 100.0], [t1, peak, "linear"]]}}
    effects = c.setdefault("effects", [])
    mi = next((i for i, e in enumerate(effects) if e.get("effect") == "track_matte"), None)
    effects.insert(len(effects) if mi is None else mi, fx)   # phóng TRƯỚC track matte: chữ sau người vẫn khớp viền người


def soft_out(c: dict, out_s: float = SOFT_OUT_S, blur: float | None = OUT_BLUR) -> None:
    """Ra: opacity 100 → 0 trong out_s; blur=None → chỉ mờ, không nhoè (hồ sơ minimal-edu)."""
    d = c["dur"]
    t0 = max(0.0, d - out_s)
    op = c.get("opacity")
    if isinstance(op, list) and op and isinstance(op[0], (list, tuple)):
        keep = [k for k in op if k[0] < t0 - 1e-3]
        last = keep[-1][1] if keep else 100
        c["opacity"] = keep + [[t0, last], [d, 0]]
    else:
        c["opacity"] = [[0, op if isinstance(op, (int, float)) else 100], [t0, op if isinstance(op, (int, float)) else 100], [d, 0]]
    if blur is None:
        return
    fx = _effect(c, "gaussian_blur")
    if fx and isinstance(fx["params"].get("blurriness"), list):
        ks = [k for k in fx["params"]["blurriness"] if k[0] < t0 - 1e-3]
        fx["params"]["blurriness"] = ks + [[t0, 0], [d, blur]]
    else:
        c.setdefault("effects", []).append({"effect": "gaussian_blur", "params": {"blurriness": [[0, 0], [t0, 0], [d, blur]]}})


def _has_out(c: dict) -> bool:
    """Clip đã có kiểu ra riêng: transition_out, hoặc key opacity cuối là mờ về ~0 ở cuối clip."""
    d, op = c["dur"], c.get("opacity")
    fades_out = (isinstance(op, list) and len(op) >= 2 and isinstance(op[-1], (list, tuple))
                 and op[-1][0] >= d - 0.3 and op[-1][1] <= 5)        # key cuối là mờ về ~0 ở cuối clip
    return bool(c.get("transition_out")) or fades_out


def _trim_to_cut(c: dict, cuts: list[float], fps: float, frames: int) -> bool:
    """Hồ sơ: clip kết thúc `frames` khung trước điểm cắt gần cuối clip (cắt trong [cuối − CUT_SNAP_S, cuối]). Chỉ rút ngắn,
    và bỏ qua nếu clip còn key chuyển động nằm sau điểm kết thúc mới (không để key vượt cuối clip)."""
    end = c["at"] + c["dur"]
    cut = next((t for t in sorted(cuts) if end - CUT_SNAP_S <= t <= end + 1e-6), None)
    new_end = None if cut is None else round((cut - frames / fps) * fps) / fps
    if new_end is None or new_end >= end - 1e-6 or new_end - c["at"] < MIN_CLIP_S:
        return False
    if any(t > new_end - c["at"] + 1e-6 for t in _anim_times(c)):
        return False
    c["dur"] = round(new_end - c["at"], 6)
    return True


def _t(frame: float, fps: float) -> float:
    return round(frame / fps, 6)


def _keys(v, t: float = 0.0) -> list:
    """Giá trị tĩnh hoặc chuỗi key → chuỗi key mới (bản sao)."""
    if isinstance(v, list) and v and isinstance(v[0], list) and v[0] and isinstance(v[0][0], (int, float)):
        return [list(k) for k in v]
    return [[t, v]]


def _kin_fx(c: dict, anchor: list[float] | None = None) -> dict:
    """Hiệu ứng `transform` chung của chữ (anchor = position lúc đứng yên): lấy cái đã có hoặc tạo mới, đặt TRƯỚC track matte."""
    fx = next((e for e in c.get("effects", []) if e.get("effect") == "transform" and e["params"].get("uniform_scale")), None)
    if fx is None:
        ax = list(anchor) if anchor else _anchor(c)
        fx = {"effect": "transform", "params": {"anchor": ax, "position": list(ax), "uniform_scale": True, "scale_height": 100.0}}
        effects = c.setdefault("effects", [])
        mi = next((i for i, e in enumerate(effects) if e.get("effect") == "track_matte"), None)
        effects.insert(len(effects) if mi is None else mi, fx)
    return fx


def stagger_times(times: list[float], fps: float, kin: dict | None = None) -> list[float]:
    """Mốc vào của từng từ theo thứ tự đọc: cách từ trước ≥ stagger_frames khung, lệch so với lúc nói ≤ stagger_cap_frames khung."""
    k = kin or KIN
    out: list[float] = []
    for t in times:
        floor = out[-1] + k["stagger_frames"] / fps if out else t
        out.append(min(max(t, floor), t + k["stagger_cap_frames"] / fps))
    return out


def kinetic_in(c: dict, fps: float, kin: dict | None = None, overshoot: bool = False, anchor: list[float] | None = None) -> None:
    """Vào mượt: Y +dy → 0, scale scale_from → 100 (decelerate: easeIn ở key đến), blur blur_from → 0 trong blur_frames khung đầu,
    opacity 0 → 100 trong opacity_frames khung đầu. overshoot: scale vọt `overshoot` % rồi lắng xong sau overshoot_frames khung
    (chỉ từ lớn, không áp cho số / tiền). Clip ngắn: co lại, tối thiểu MIN_ENTRY_FRAMES khung."""
    k = kin or KIN
    n = max(MIN_ENTRY_FRAMES, min(k["in_frames"], round(c["dur"] * fps) - 1))
    nb, no = min(k["blur_frames"], n), min(k["opacity_frames"], n)
    fx = _kin_fx(c, anchor)
    ax, ay = fx["params"]["anchor"]
    c["opacity"] = [[0, 0], [_t(no, fps), 100]]
    c.setdefault("effects", []).insert(0, {"effect": "gaussian_blur", "params": {
        "blurriness": [[0, k["blur_from"]], [_t(nb, fps), 0, "easeIn"]]}})
    pos = [[0, [ax, ay + k["dy"]]], [_t(n, fps), [ax, ay], "easeIn"]]
    if overshoot:
        peak, end = max(1, round(n * 0.6)), max(n, min(k["overshoot_frames"], round(c["dur"] * fps) - 1))
        scale = [[0, k["scale_from"]], [_t(peak, fps), k["overshoot"], "bezier"], [_t(end, fps), 100, "easeIn"]]
    else:
        scale = [[0, k["scale_from"]], [_t(n, fps), 100, "easeIn"]]
    fx["params"]["position"], fx["params"]["scale_height"] = pos, scale


# ---- thư viện kiểu vào của chữ minimal-edu (3.6.4): nhiều kiểu xoay vòng, cùng giữ / ra của kinetic_hold / kinetic_exit ----
# Mỗi kiểu là một bảng keyframe (khung, giá trị[, nội suy]); mọi key đến đều easeIn (hãm lúc đến) — không bao giờ linear.
ENTRANCE_MIN_STYLES, ENTRANCE_MAX_STYLES = 6, 10    # profile key: text.kinetic.entrance_styles — mỗi video dùng 6–10 kiểu (chọn theo tên video)
MASK_DY_RATIO = 1.1                                 # profile key: text.kinetic.mask_dy_ratio — mask_reveal_up: chữ trồi từ dưới đường cắt (× cỡ chữ)
MASK_CUT_RATIO = 0.32                               # profile key: text.kinetic.mask_cut_ratio — đường cắt = baseline + 0,32 × cỡ (chừa dấu / chân chữ)
WIPE_MARGIN_PX = 40                                 # profile key: text.kinetic.wipe_margin_px — wipe_left: mép quét vượt mép chữ 40 px
TRACKING_FROM = -90                                 # profile key: text.kinetic.tracking_from — tracking_expand: tracking −90 → giá trị gốc
FRAME_PX = (1080, 1920)


def _entrance_specs() -> dict:
    """tên → hàm (cỡ chữ, hình học, chỉ số từ) → bảng key. Hình học g = {x0, x1, base, size} (px khung 1080×1920) hoặc None."""
    return {
        "drop_bounce": lambda g, i: {"op": [(0, 0), (3, 100)], "blur": [(0, 8), (5, 0)],
                                     "pos": [(0, 0, -60), (6, 0, 8), (12, 0, 0)]},
        "scale_pop": lambda g, i: {"op": [(0, 0), (3, 100)], "blur": [(0, 10), (5, 0)],
                                   "scale": [(0, 60), (6, 108, "bezier"), (12, 100)]},
        "mask_reveal_up": lambda g, i: {"op": [(0, 0), (1, 100)], "pos": [(0, 0, round(MASK_DY_RATIO * g["size"])), (10, 0, 0)],
                                        "crop": {"bottom": [(0, _cut_pct(g), "hold"), (10, _cut_pct(g), "hold"), (11, 0)]}},
        "wipe_left": lambda g, i: {"op": [(0, 0), (2, 100)], "pos": [(0, -36, 0), (10, 0, 0)], "dblur": [(0, 40), (8, 0)],
                                   "crop": {"right": [(0, _right_pct(g["x0"] - 20)), (10, _right_pct(g["x1"] + WIPE_MARGIN_PX)), (11, 0)],
                                            "feather": 24}},
        "tracking_expand": lambda g, i: {"op": [(0, 0), (5, 100)], "blur": [(0, 10), (6, 0)], "scale": [(0, 96), (12, 100)],
                                         "trk": [(0, TRACKING_FROM), (12, 0)]},
        "rotate_in": lambda g, i: {"op": [(0, 0), (4, 100)], "blur": [(0, 8), (6, 0)], "scale": [(0, 94), (11, 100)],
                                   "rot": [(0, -8), (11, 0)], "pos": [(0, 0, 30), (11, 0, 0)]},
        "blur_zoom": lambda g, i: {"op": [(0, 0), (5, 100)], "blur": [(0, 20), (8, 0)], "scale": [(0, 130), (11, 100)]},
        "split_rise": lambda g, i: {"op": [(0, 0), (3, 100)], "blur": [(0, 8), (5, 0)], "dblur": [(0, 30), (7, 0)],
                                    "pos": [(0, -50 if i % 2 == 0 else 50, 16), (10, 0, 0)]},
        "typewriter_soft": lambda g, i: {"op": [(0, 0), (3, 100)], "blur": [(0, 6), (6, 0)], "pos": [(0, 0, 10), (8, 0, 0)]},
        "flip_x": lambda g, i: {"op": [(0, 0), (3, 100)], "blur": [(0, 6), (6, 0)], "flip": [(0, 4), (11, 100)]},
    }


def _cut_pct(g: dict) -> float:
    """Crop `bottom` (% khung) cắt ngay dưới chân chữ."""
    return round((FRAME_PX[1] - (g["base"] + MASK_CUT_RATIO * g["size"])) / FRAME_PX[1] * 100, 2)


def _right_pct(edge_x: float) -> float:
    """Crop `right` (% khung) để mép phải của vùng hiện nằm ở x = edge_x."""
    return round(min(100.0, max(0.0, 100 - edge_x / FRAME_PX[0] * 100)), 2)


ENTRANCES = ("slide_up_blur", *_entrance_specs())
NEEDS_GEO = {"mask_reveal_up", "wipe_left"}
NO_PNG = {"tracking_expand"}                                      # ảnh chữ PNG (gradient) không có tracking
NUMBER_SAFE = tuple(s for s in ENTRANCES if s not in {"drop_bounce", "scale_pop"})      # drop_bounce / scale_pop vọt quá đích


def _frames(pts: list, scale: float) -> list[tuple]:
    """Mốc khung của chuỗi key co theo `scale` (clip ngắn), tăng ngặt, khung đầu = 0."""
    out, last = [], -1
    for j, p in enumerate(pts):
        f = 0 if j == 0 else max(last + 1, round(p[0] * scale))
        out.append((f, *p[1:]))
        last = f
    return out


def _seq(pts: list, fps: float, scale: float, conv=lambda v: v) -> list:
    """[(khung, giá trị[, nội suy])] → keys [t, giá trị, nội suy]; key đến mặc định easeIn, key đầu chỉ có nội suy nếu ghi rõ."""
    keys = []
    for j, p in enumerate(_frames(pts, scale)):
        interp = p[2] if len(p) > 2 else ("easeIn" if j else None)
        keys.append([_t(p[0], fps), conv(p[1])] + ([interp] if interp else []))
    return keys


def _apply_spec(c: dict, fps: float, spec: dict, anchor: list[float] | None, scale: float) -> None:
    """Ghi bảng key của một kiểu vào clip chữ: opacity, blur (đầu danh sách effects), transform (anchor = tâm chữ), crop / rotate_3d (sau transform)."""
    fx = _kin_fx(c, anchor)
    prm, (ax, ay) = fx["params"], fx["params"]["anchor"]
    effs = c.setdefault("effects", [])
    c["opacity"] = _seq(spec["op"], fps, scale)
    if "blur" in spec:
        effs.insert(0, {"effect": "gaussian_blur", "params": {"blurriness": _seq(spec["blur"], fps, scale)}})
    if "dblur" in spec:
        effs.insert(0, {"effect": "directional_blur", "params": {"direction": 0, "length": _seq(spec["dblur"], fps, scale)}})
    if "pos" in spec:
        prm["position"] = _seq([(p[0], [ax + p[1], ay + p[2]], *p[3:]) for p in spec["pos"]], fps, scale)
    if "scale" in spec:
        prm["scale_height"] = _seq(spec["scale"], fps, scale)
    if "rot" in spec:
        prm["rotation"] = _seq(spec["rot"], fps, scale)
    if "trk" in spec:
        base = c.get("tracking", 0)
        c["tracking"] = _seq(spec["trk"], fps, scale, lambda v: base + v)
    if "flip" in spec:       # lật quanh trục ngang của chữ: ép chiều cao 4 → 100 % (rotate_3d xoay quanh tâm KHUNG nên không dùng)
        effs.append({"effect": "transform", "params": {"anchor": [ax, ay], "position": [ax, ay], "uniform_scale": False,
                                                      "scale_height": _seq(spec["flip"], fps, scale), "scale_width": 100.0}})
    if "crop" in spec:
        params = {k: _seq(v, fps, scale) for k, v in spec["crop"].items() if k != "feather"}
        params.update({"feather": spec["crop"]["feather"]} if "feather" in spec["crop"] else {})
        effs.append({"effect": "crop", "params": params})


def entrance_in(c: dict, fps: float, style: str, kin: dict | None = None, overshoot: bool = False,
                anchor: list[float] | None = None, geo: dict | None = None, idx: int = 0) -> str:
    """Vào theo kiểu `style` (ENTRANCES). slide_up_blur = kinetic_in. Thiếu hình học cho kiểu cần nó, hoặc ảnh PNG với kiểu cần tracking →
    quay về blur_zoom. Clip ngắn: mọi mốc khung co lại cho vừa. Trả tên kiểu thật sự dùng."""
    if style not in ENTRANCES:
        raise ValueError(f"kiểu vào phải là một trong {ENTRANCES}, nhận {style!r}")
    if (style in NEEDS_GEO and not geo) or (style in NO_PNG and "src" in c):
        style = "blur_zoom"
    if style == "slide_up_blur":
        kinetic_in(c, fps, kin, overshoot, anchor)
        return style
    spec = _entrance_specs()[style](geo, idx)
    last = max(p[0] for v in spec.values() for k in (v.values() if isinstance(v, dict) else [v]) if isinstance(k, list) for p in k)
    scale = min(1.0, max(MIN_ENTRY_FRAMES, round(c["dur"] * fps) - 1) / last)
    _apply_spec(c, fps, spec, anchor, scale)
    return style


class EntranceStyles:
    """Bộ xoay kiểu vào của MỘT video: chọn 6–10 kiểu trong ENTRANCES theo tên video (seed; luôn ≥ 4 kiểu không vọt vì chỉ 2 kiểu vọt), rồi lần lượt qua chúng cho chữ lớn / chữ nhỏ.
    `.pick(kind, number, png)` → tên kiểu; kind 'hero' | 'small'. Không trùng kiểu cụm trước (cùng kind); chữ nhỏ cố tránh trùng kiểu chữ lớn
    của cùng cụm; số / tiền chỉ lấy kiểu không vọt (NUMBER_SAFE); ảnh PNG tránh NO_PNG; typewriter_soft chỉ cho chữ nhỏ."""

    def __init__(self, prof: dict | None, seed):
        import random
        import zlib
        rnd = random.Random(zlib.crc32(str(seed).encode()))
        cfg = (prof or {}).get("text", {}).get("kinetic", {}).get("entrance_styles") or [ENTRANCE_MIN_STYLES, ENTRANCE_MAX_STYLES]
        pool = rnd.sample(ENTRANCES, rnd.randint(cfg[0], cfg[1]))
        self.styles = tuple(pool)
        self._pos = {"hero": rnd.randrange(len(pool)), "small": rnd.randrange(len(pool))}
        self._last: dict[str, str | None] = {"hero": None, "small": None}
        self._hero_now: str | None = None

    def pick(self, kind: str = "hero", number: bool = False, png: bool = False) -> str:
        if kind not in self._pos:
            raise ValueError("kind phải là 'hero' hoặc 'small'")
        n = len(self.styles)
        ok = [s for s in self.styles if (kind == "small" or s != "typewriter_soft") and (not number or s in NUMBER_SAFE)
              and not (png and s in NO_PNG)] or ["blur_zoom"]
        for avoid in ({self._last[kind], self._hero_now if kind == "small" else None}, {self._last[kind]}, set()):
            for step in range(n):
                s = self.styles[(self._pos[kind] + step) % n]
                if s in ok and s not in avoid:
                    self._pos[kind] = (self._pos[kind] + step + 1) % n
                    self._last[kind] = s
                    self._hero_now = s if kind == "hero" else self._hero_now
                    return s
        self._last[kind] = ok[0]
        return ok[0]


def kinetic_hold(c: dict, t0: float, t1: float, kin: dict | None = None, fps: float = 30.0) -> None:
    """Giữ: scale phóng chậm đều từ lúc đáp (t0) tới t1 → hold_scale %, key đáp mềm cả hai phía (bezier).
    Cửa sổ giữ ngắn hơn min_hold_frames: biên độ thu theo tỉ lệ (tối thiểu SHORT_HOLD_FLOOR) — vẫn một chuỗi key liên tục nên chữ không đứng yên."""
    k = kin or KIN
    full = max(1e-3, k["min_hold_frames"] / fps)
    k = {**k, "hold_scale": 100 + (k["hold_scale"] - 100) * min(1.0, max(SHORT_HOLD_FLOOR, (t1 - t0) / full))}
    fx = _kin_fx(c)
    sk = _keys(fx["params"]["scale_height"])
    if sk[-1][0] < t0 - 1e-6:
        sk.append([_t(t0, 1.0), sk[-1][1]])
    sk[-1] = [sk[-1][0], sk[-1][1], "bezier"]
    fx["params"]["scale_height"] = sk + [[round(t1, 6), float(k["hold_scale"])]]


def _upto(keys: list, t: float) -> list:
    return [k for k in keys if k[0] < t - 1e-3]


def kinetic_exit(c: dict, fps: float, kin: dict | None = None) -> None:
    """Ra: opacity → 0, Y → exit_dy, blur 0 → exit_blur trong exit_frames khung (accelerate: easeOut ở key đi), kết thúc đúng cuối clip."""
    k = kin or KIN
    d = c["dur"]
    t0 = max(round(d - min(k["exit_frames"] / fps, d / 2), 6), 1 / fps)
    op = _upto(_keys(c.get("opacity", 100)), t0)
    c["opacity"] = op + [[t0, op[-1][1] if op else 100, "easeOut"], [d, 0]]
    fx = next((e for e in c.get("effects", []) if e.get("effect") == "gaussian_blur" and isinstance(e["params"].get("blurriness"), list)), None)
    if fx is None:
        fx = {"effect": "gaussian_blur", "params": {"blurriness": [[0, 0]]}}
        c.setdefault("effects", []).insert(0, fx)
    fx["params"]["blurriness"] = _upto(fx["params"]["blurriness"], t0) + [[t0, 0, "easeOut"], [d, k["exit_blur"]]]
    tf = _kin_fx(c)["params"]
    ax, ay = tf["anchor"]
    pos = _upto(_keys(tf["position"]), t0)
    tf["position"] = pos + [[t0, [ax, ay], "easeOut"], [d, [ax, ay + k["exit_dy"]]]]


def _profile_motion(c: dict, lane: str, fps: float, kin: dict, n: dict) -> None:
    """Hồ sơ minimal-edu: bổ sung vào (nếu chưa có kiểu vào) / giữ phóng chậm / ra cho một clip chữ."""
    ts = _anim_times(c)
    if not any(t <= ENTRANCE_WINDOW for t in ts):
        kinetic_in(c, fps, kin)
        n["in"] += 1
        ts = _anim_times(c)
    d, has_out = c["dur"], _has_out(c)
    out_s = 0.0 if has_out else min(kin["exit_frames"] / fps, d / 2)
    in_end = max([t for t in ts if t <= ENTRANCE_WINDOW + 0.25] or [0.0])
    still = not has_hold_motion(c, in_end, d - out_s) or (d >= MIN_HOLD_S and _static_hold(c))   # cùng tiêu chí với static_report
    if d - out_s - in_end >= MIN_HOLD_WINDOW_FRAMES / fps - 1e-6 and still:
        kinetic_hold(c, in_end, d - out_s, kin, fps)
        n["hold"] += 1
    if not has_out:
        kinetic_exit(c, fps, kin)
        n["out"] += 1


def ensure_motion(items: list[tuple[str, dict]], fps: float = 30.0, profile: dict | None = None,
                  cuts: list[float] | None = None) -> dict:
    """Bổ sung vào / giữ / ra cho mọi clip chữ còn thiếu. Trả số clip được thêm từng phần.
    profile = hồ sơ 'minimal-edu' đã nạp (style_profile.load) → typography chuyển động (kinetic_in / hold / exit, KIN), cắt clip
    theo `cuts` (mốc điểm cắt trên timeline, giây) để ra kết thúc `end_before_cut_frames` khung trước cắt; hồ sơ khác / None → hành vi cũ."""
    prof = profile if active(profile, "minimal-edu") else None
    n = {"in": 0, "hold": 0, "out": 0, "text": 0}
    if prof:
        n["trim"] = 0
        kin = kinetic_params(prof)
        end_f = get(prof, "text.end_before_cut_frames", [0, 2])[1]
    for lane, c in items:
        if lane not in TEXT_LANES or c.get("dur", 0) < MIN_CLIP_S:
            continue
        n["text"] += 1
        if prof and cuts and not _has_out(c) and _trim_to_cut(c, cuts, fps, end_f):
            n["trim"] += 1
        if prof:
            _profile_motion(c, lane, fps, kin, n)
            continue
        d = c["dur"]
        ts = _anim_times(c)
        if not any(t <= ENTRANCE_WINDOW for t in ts):
            soft_in(c, lane)
            n["in"] += 1
            ts = _anim_times(c)
        in_end = max([t for t in ts if t <= ENTRANCE_WINDOW + 0.25] or [0.0])
        has_out = _has_out(c)
        out_start = d if has_out else d - SOFT_OUT_S
        if d >= MIN_HOLD_S and out_start - in_end > 0.2 and not has_hold_motion(c, in_end, out_start):
            hold_drift(c, lane, in_end, out_start)
            n["hold"] += 1
        if not has_out:
            soft_out(c)
            n["out"] += 1
    return n


def static_report(tracks: list[dict], fps: float = 30.0) -> dict:
    """Đếm clip chữ tĩnh trên spec đã dựng (cho bộ kiểm): không có kiểu vào, hoặc đứng yên suốt lúc giữ."""
    total = no_in = flat = 0
    for t in tracks:
        lane = t.get("name", "").rsplit(" ", 1)[0]
        if lane not in TEXT_LANES:
            continue
        for c in t.get("clips", []):
            if c.get("dur", 0) < MIN_HOLD_S:
                continue
            total += 1
            ts = _anim_times(c)
            if not any(t_ <= ENTRANCE_WINDOW for t_ in ts):
                no_in += 1
            if _static_hold(c):
                flat += 1                  # không có chuyển động trải suốt lúc giữ = chữ đứng yên
    return {"total": total, "no_entrance": no_in, "static_hold": flat}
