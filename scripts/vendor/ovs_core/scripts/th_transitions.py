"""Chuyển cảnh talking-head (3.6.2): các kiểu mới cho hồ sơ minimal-edu, thay cho "cắt cứng 80 %".

    fx.join(clip_after, "soft_wipe")                    # clip_after = clip ngay sau điểm cắt; clip_after["at"] = điểm cắt
    fx.th_join(clip_after, "paper_rip", cue_sfx=True)   # như join, nhận thêm tham số riêng (vd text= cho chapter_card_slam)

Bảng TH_JOINS dùng `transition_in` có sẵn của FilmCraft (spec chỉ nhận {effect, frames}: tham số của chuyển cảnh nằm ở mặc
định của FilmCraft — blur 40, feather 300, tâm iris / clock = giữa khung, góc page_peel = dưới phải, hướng push cố định).
Các kiểu còn lại dựng bằng keyframe / PNG (dip_to_paper: dip_to_color mặc định ĐỎ nên không dùng được cho giấy trắng).
Mỗi hàm sửa `clip` tại chỗ, đẩy lớp phủ vào `fx.items` và SFX vào `fx.cues` (kind "paper" mới trong sfx_catalog.json).
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

# kiểu → (id chuyển cảnh FilmCraft, số khung, SFX). Số khung ≤ 18 (hoà tan ≤ 20, 3.6.3: dài + easing để "lả lướt", user 2026-11-17);
# SFX nhẹ ("paper" = swish tầng soft). Chuyển cảnh dựng sẵn của FilmCraft căn GIỮA điểm cắt và chỉ thấy rõ ~2/3 số khung.
TH_JOINS = {
    "morph_smooth": ("morph_cut", 8, []),
    "blur_dissolve_cut": ("blur_dissolve", 16, ["paper"]),
    "soft_wipe": ("soft_wipe", 14, ["paper"]),
    "luma_fade_soft": ("luma_fade", 16, []),
    "clock_wipe_step": ("clock_wipe", 14, ["pop"]),
    "iris_round_focus": ("iris_round", 14, ["pop"]),
    "page_peel_in": ("page_peel", 16, ["pop"]),               # 3D: tính vào hạn mức 3D (remix_rules.THREE_D_TR)
    # nhóm hợp phong cách năng động (E-fit, catalog mục A/C)
    "pop_in": ("pop_motion", 8, ["pop"]),
    "neon_wipe": ("neon_wipe", 8, ["whoosh"]),
    "mosaic_pixel": ("mosaic_transition", 8, ["data_beep"]),
}
KEYED_TH = {"camera_continue": 12, "punch_settle": 14, "drift_reset": 0, "j_cut_return": 0, "dip_to_paper": 18, "paper_rip": 18, "card_swipe": 14,
            "smoke_veil": 20, "impact_shake": 8, "chapter_card_slam": 12, "vhs_rewind": 9,
            # 3.6.4 năng động: nháy sáng (số khung overlay), nhóm máy quay (khung đầu cảnh sau), rò sáng / cháy phim (cross_dissolve 2 khung)
            "flash_cut": 9, "double_flash": 12, "flicker_cut": 11, "zoom_punch_in": 10, "zoom_punch_out": 10, "whip_pan": 8, "spin_roll": 10,
            "lens_warp": 10, "rgb_split_cut": 8, "light_leak": 2, "film_burn": 2}
TH_KINDS = set(TH_JOINS) | set(KEYED_TH)
TH_FRAMES = {**{k: v[1] for k, v in TH_JOINS.items()}, **KEYED_TH}   # số khung chuyển cảnh (chapter_card_slam: 6 vào + 6 ra)
DISSOLVE_OK = {"smoke_veil", "blur_dissolve_cut", "luma_fade_soft", "dip_to_paper"}   # hoà tan: ≤ 20 khung; còn lại ≤ 18
MAX_FRAMES, MAX_FRAMES_DISSOLVE = 18, 20
# chuyển cảnh nặng (phủ khung / quét / thẻ): KHÔNG dùng khi cắt giữa câu (cut_plan.plan_cuts_min)
HEAVY_TH = {"page_peel_in", "card_swipe", "dip_to_paper", "paper_rip", "smoke_veil", "chapter_card_slam", "clock_wipe_step", "light_leak", "film_burn"}
HARD_KINDS = {"hard_cut", "j_cut_return"}          # j_cut_return = cắt cứng có dẫn hình trước lời 10 khung
FLASHY_TH = {"vhs_rewind", "flash_cut", "double_flash", "flicker_cut"}   # nháy sáng / bán phần: chịu hạn mức nháy sáng (cut_plan.FLASHY)
ONE_PER_VIDEO = {"paper_rip", "smoke_veil", "page_peel_in", "ink_matte_reveal"}   # giấy rách / khói / mực / 3D: ≤ 1 lần mỗi video
J_LEAD_FRAMES = 10
PRO_DIR = Path.home() / "Thanh/Media/TNEDIT/05_Hieu_Ung_Chuyen_Canh/Overlay_Video/PR_Overlays"
SMOKE_SRC = PRO_DIR / "OVL_Smoke_Matte_white_smoke_with_black_background_1960.mp4"


def _keyed(v) -> bool:
    return isinstance(v, list) and bool(v) and isinstance(v[0], list)


def _last(fx, c: dict) -> float:
    """Giây của khung cuối clip: keyframe cuối phải nằm trong clip (fx._frame_keys gộp khoá vượt khung cuối vào khoá trước)."""
    return (round(c["dur"] * fx.fps) - 1) / fx.fps


def _tin(clip: dict, effect: str, frames: int) -> dict:
    clip["transition_in"] = {"effect": effect, "frames": frames}
    return clip


def _cue(fx, on: bool, t: float, kind: str, max_pre: float, why: str) -> None:
    if on:
        fx.cues.append({"t": t, "kind": kind, "max_pre": round(max_pre, 3), "why": why})


# ---- chuyển động chồng hai phía điểm cắt (3.6.3) ----
# kiểu → (khung đuôi cảnh TRƯỚC, scale đuôi, nhoè đuôi, khung đầu cảnh SAU, scale đầu, nhoè đầu). Đuôi: phóng tăng dần (u²) tới scale đuôi
# ở khung cuối; đầu: về 100 % giảm tốc (cubic). Nhoè = gaussian_blur cùng cửa sổ. Chưa có trong minimal-edu-style.json:
# profile key: transitions.overlap.<kind> = [tail_frames, tail_scale, tail_blur, head_frames, head_scale, head_blur]
SMOOTH = {
    "punch_settle": (6, 1.05, 8, 14, 1.10, 8), "morph_smooth": (6, 1.03, 4, 10, 1.03, 4),
    "soft_wipe": (8, 1.04, 0, 12, 1.04, 0), "blur_dissolve_cut": (8, 1.05, 0, 12, 1.05, 0),
    "luma_fade_soft": (6, 1.03, 0, 12, 1.03, 0), "clock_wipe_step": (6, 1.03, 0, 12, 1.03, 0),
    "iris_round_focus": (6, 1.03, 0, 12, 1.03, 0), "page_peel_in": (6, 1.02, 0, 12, 1.02, 0),
    "dip_to_paper": (8, 1.03, 0, 12, 1.03, 0), "smoke_veil": (8, 1.03, 0, 12, 1.03, 0),
}


# Kiểu năng động (3.6.4): cùng khuôn với SMOOTH nhưng mạnh hơn (punch 14–28 %, nhoè nặng) nên KHÔNG qua bộ kiểm "mỗi khung đổi ≤ 3 %" của
# SMOOTH. Đuôi tăng tốc (u²), đầu giảm tốc (cubic): hai phía cùng một chuyển động. Chưa có trong minimal-edu-style.json:
# profile key: transitions.overlap.<kind> = [tail_frames, tail_scale, tail_blur, head_frames, head_scale, head_blur]
ENERGY = {
    "zoom_punch_in": (8, 1.14, 10, 10, 1.14, 10), "zoom_punch_out": (4, 1.03, 4, 10, 1.28, 14),
    "flash_cut": (4, 1.05, 0, 8, 1.08, 0), "double_flash": (4, 1.05, 0, 10, 1.08, 0), "flicker_cut": (3, 1.04, 0, 6, 1.06, 0),
    "impact_shake": (4, 1.05, 0, 8, 1.06, 0), "rgb_split_cut": (5, 1.04, 0, 8, 1.06, 0),
    "whip_pan": (4, 1.16, 0, 8, 1.16, 0), "spin_roll": (5, 1.22, 8, 10, 1.22, 8), "lens_warp": (6, 1.10, 0, 10, 1.10, 0),
    "light_leak": (6, 1.03, 0, 12, 1.04, 0), "film_burn": (6, 1.03, 0, 12, 1.04, 0),
}


def _scale_fn(clip: dict):
    """Hàm giây-trong-clip → scale hiện có của clip (hằng hoặc nội suy tuyến tính giữa các key; render lấy mẫu theo khung nên đủ chính xác)."""
    sc = clip.get("motion", {}).get("scale", 100)
    if not _keyed(sc):
        return lambda t: sc
    pts = [(float(k[0]), float(k[1])) for k in sc]

    def f(t: float) -> float:
        if t <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t <= t1:
                return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return pts[-1][1]
    return f


def _scale_env(fx, clip: dict, f0: int, f1: int, env) -> None:
    """Nhân scale clip với env(u), u 0→1 trên khung f0..f1, mỗi khung một key: giữ nguyên zoom keyframe sẵn có (A-roll zoom, drift)."""
    n = round(clip["dur"] * fx.fps)
    f0, f1 = max(0, f0), min(n - 1, f1)
    if f1 <= f0:
        return
    old, f, fps = clip.get("motion", {}).get("scale", 100), _scale_fn(clip), fx.fps
    if _keyed(old):                                 # so theo khung (key gốc có thể lệch khung vài phần nghìn giây)
        pre, post = [k for k in old if round(k[0] * fps) < f0], [k for k in old if round(k[0] * fps) > f1]
    else:
        pre, post = ([[0, old]] if f0 > 0 else []), ([[(n - 1) / fps, old]] if f1 < n - 1 else [])
    mid = [[fr / fps, round(f(fr / fps) * env((fr - f0) / (f1 - f0)), 2)] for fr in range(f0, f1 + 1)]
    clip.setdefault("motion", {})["scale"] = fx._frame_keys(pre + mid + post, clip["dur"])


def _ramp_fx(fx, clip: dict, effect: str, param: str, f0: int, f1: int, peak: float, rising: bool, extra: dict | None = None) -> None:
    """Tham số `param` của `effect`: 0 → peak (tăng tốc dần, đỉnh ở khung f1) hoặc peak → 0 (giảm tốc, hết ở f1)."""
    n = round(clip["dur"] * fx.fps)
    f0, f1, fps = max(0, f0), min(n - 1, f1), fx.fps
    if f1 <= f0:
        return
    keys = ([[0, 0]] if f0 > 0 else []) + (
        [[f0 / fps, 0, "easeOut"], [f1 / fps, peak]] if rising else [[f0 / fps, peak], [f1 / fps, 0, "easeIn"]])
    fx._fx(clip, effect, {**(extra or {}), param: fx._frame_keys(keys, clip["dur"])})


def _blur_ramp(fx, clip: dict, f0: int, f1: int, peak: float, rising: bool) -> None:
    """gaussian_blur 0 → peak (tăng tốc dần, đỉnh ở khung f1) hoặc peak → 0 (giảm tốc, hết ở f1)."""
    _ramp_fx(fx, clip, "gaussian_blur", "blurriness", f0, f1, peak, rising)


def _overlap(fx, clip: dict, before: dict | None, kind: str) -> dict:
    """Đầu cảnh sau về 100 % giảm tốc (+ nhoè); nếu có `before` (clip ngay trước điểm cắt) thì đuôi nó cũng phóng tăng tốc (+ nhoè):
    hai phía cùng chuyển động nên chuyển cảnh dựng sẵn của FilmCraft (chỉ nhận {effect, frames}) không còn "cứng"."""
    n_o, s_o, b_o, n_i, s_i, b_i = SMOOTH.get(kind) or ENERGY[kind]
    _scale_env(fx, clip, 0, n_i - 1, lambda u: 1 + (s_i - 1) * (1 - u) ** 3)
    if b_i:
        _blur_ramp(fx, clip, 0, n_i - 1, b_i, False)
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _scale_env(fx, before, nb - n_o, nb - 1, lambda u: 1 + (s_o - 1) * u * u)
        if b_o:
            _blur_ramp(fx, before, nb - n_o, nb - 1, b_o, True)
    return clip


# camera_continue: máy tiếp tục lia trái qua điểm cắt (push dựng sẵn của FilmCraft bị bóng ma lặp hình nên thay bằng keyframe)
PAN_PX, PAN_BLUR, PAN_SCALE = 48, 40, 1.10      # profile key: transitions.camera_continue.{pan_px, blur, scale}; PAN_PX ≤ (PAN_SCALE-1)·540 (không hở viền)


def _pan_env(fx, clip: dict, f0: int, f1: int, dx) -> None:
    """Dịch ngang position theo dx(u) px trên khung f0..f1 (bỏ qua nếu clip đã có keyframe position riêng)."""
    n = round(clip["dur"] * fx.fps)
    f0, f1 = max(0, f0), min(n - 1, f1)
    pos = clip.get("motion", {}).get("position")
    if f1 <= f0 or _keyed(pos):
        return
    x, y = pos or [540, 960]
    keys = ([[0, [x, y]]] if f0 > 0 else []) + [[fr / fx.fps, [round(x + dx((fr - f0) / (f1 - f0)), 1), y]] for fr in range(f0, f1 + 1)]
    keys += [[(n - 1) / fx.fps, [x, y]]] if f1 < n - 1 else []
    clip.setdefault("motion", {})["position"] = fx._frame_keys(keys, clip["dur"])


def _pan_blur(fx, clip: dict, f0: int, f1: int, rising: bool, peak: float = PAN_BLUR) -> None:
    n = round(clip["dur"] * fx.fps)
    f0, f1 = max(0, f0), min(n - 1, f1)
    keys = ([[0, 0]] if f0 > 0 else []) + ([[f0 / fx.fps, 0, "easeOut"], [f1 / fx.fps, peak]] if rising else
                                           [[f0 / fx.fps, peak], [f1 / fx.fps, 0, "easeIn"]])
    fx._fx(clip, "directional_blur", {"direction": 90, "length": fx._frame_keys(keys, clip["dur"])})


def camera_continue(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Máy lia trái liền mạch qua điểm cắt: đuôi cảnh trước (6 khung, nếu có `before`) phóng 100 → 110 % + dịch trái 48 px tăng tốc + nhoè
    ngang; đầu cảnh sau (12 khung) vào 110 % lệch phải, về 100 % giảm tốc cùng hướng trái; hoà tan 4 khung che chỗ nhảy."""
    n_o, n_i, s = 6, 12, PAN_SCALE
    _scale_env(fx, clip, 0, n_i - 1, lambda u: 1 + (s - 1) * (1 - u) ** 3)
    _pan_env(fx, clip, 0, n_i - 1, lambda u: PAN_PX * (1 - u) ** 3)
    _pan_blur(fx, clip, 0, n_i - 1, False)
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _scale_env(fx, before, nb - n_o, nb - 1, lambda u: 1 + (s - 1) * u * u)
        _pan_env(fx, before, nb - n_o, nb - 1, lambda u: -PAN_PX * u * u)
        _pan_blur(fx, before, nb - n_o, nb - 1, True)
    _cue(fx, cue_sfx, clip["at"], "whoosh", n_o / fx.fps + 0.02, "camera_continue")
    return _tin(clip, "cross_dissolve", 4)


@lru_cache(maxsize=64)
def _src_len(src: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def j_cut_time(speech_t: float, fps: int = 30) -> float:
    """Điểm cắt của j_cut_return: hình người nói vào TRƯỚC chữ đầu câu `speech_t` 10 khung (tiếng không đổi)."""
    return round(speech_t - J_LEAD_FRAMES / fps, 4)


def _simple(fx, clip: dict, kind: str, cue_sfx: bool, before: dict | None = None) -> dict:
    eff, frames, sfx = TH_JOINS[kind]
    _tin(clip, eff, frames)
    if kind in SMOOTH:
        _overlap(fx, clip, before, kind)
    for s in sfx:                                   # chuyển cảnh căn giữa điểm cắt: tiếng chỉ vào từ nửa đầu của nó
        _cue(fx, cue_sfx, clip["at"], s, frames / 2 / fx.fps + 0.02, f"chuyển cảnh {kind}")
    return clip


def punch_settle(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Ngược với zoom + punch: cảnh sau vào 110 → 100 % trong 14 khung giảm tốc (nhân với zoom sẵn có), nhoè 8 → 0, hoà tan 4 khung;
    có `before`: đuôi cảnh trước phóng 100 → 105 % + nhoè 0 → 8 trong 6 khung cuối (cùng hướng zoom hai phía điểm cắt)."""
    _overlap(fx, clip, before, "punch_settle")
    _cue(fx, cue_sfx, clip["at"], "paper", 0.12, "punch_settle")
    return _tin(clip, "cross_dissolve", 4)


def drift_reset(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Mỗi đoạn trôi chậm 100 → 105 % kèm dịch ngang 14 px, về lại ở điểm cắt kế (hoà tan 4 khung che chỗ nhảy); hướng dịch đảo chiều mỗi lần gọi."""
    mo = clip.get("motion", {})
    if _keyed(mo.get("scale")):
        raise ValueError(f"clip «{clip.get('name')}» đã có keyframe motion.scale riêng — xung đột với drift_reset")
    x, y = fx._pos_of(clip)
    sign = 1 if fx.th_state["drift"] % 2 == 0 else -1
    fx.th_state["drift"] += 1
    base = mo.get("scale", 100)
    clip.setdefault("motion", {}).update({
        "scale": fx._frame_keys([[0, base], [_last(fx, clip), round(base * 1.05, 2)]], clip["dur"]),
        "position": fx._frame_keys([[0, [x, y]], [_last(fx, clip), [x + sign * 14, y]]], clip["dur"])})
    return _tin(clip, "cross_dissolve", 4)


def j_cut_return(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Cắt cứng, không thêm gì lên clip: phần "J" nằm ở điểm cắt (xem j_cut_time) và tiếng giữ nguyên."""
    return clip


def dip_to_paper(fx, clip: dict, cue_sfx: bool = True, black: bool = False, before: dict | None = None) -> dict:
    """Chìm vào giấy trắng (PNG paper_bg, opacity 0 → 100 → 0 bezier trong 18 khung, đỉnh trắng đúng điểm cắt) hoặc `black`: dip_to_black."""
    if black:
        return _tin(clip, "dip_to_black", 12)
    import fx_gfx as G
    f = fx.fps
    p = fx.image(G.paper_bg(fx.gfx_dir, "dip_paper", "white", 0), clip["at"] - 9 / f, 18 / f, lane="trans", name="Dip giấy")
    p["opacity"] = fx._frame_keys([[0, 0, "bezier"], [9 / f, 100, "bezier"], [_last(fx, p), 0, "bezier"]], p["dur"])
    _overlap(fx, clip, before, "dip_to_paper")
    return _tin(clip, "cross_dissolve", 1)


def paper_rip(fx, clip: dict, cue_sfx: bool = True, seed: int = 0, before: dict | None = None) -> dict:
    """Hai nửa giấy rách mép phủ dần khung (5 khung bezier, kín đúng điểm cắt), giữ 1 khung rồi trượt tách ra bezier 11 khung: nửa trên
    +9° lên, nửa dưới −6° xuống."""
    import fx_gfx as G
    f = fx.fps
    n, at = 18 / f, clip["at"] - 5 / f
    for half, rot, dy in (("top", 9, -1250), ("bottom", -6, 1250)):
        c = fx.image(G.torn_paper(fx.gfx_dir, f"torn_{half}_{seed}", half, seed), at, n, lane="trans", name=f"Giấy rách {half}")
        c["opacity"] = fx._frame_keys([[0, 0, "bezier"], [5 / f, 100, "bezier"]], c["dur"])
        c["motion"] = {"position": fx._frame_keys([[0, [540, 960]], [6 / f, [540, 960], "bezier"], [_last(fx, c), [540, 960 + dy], "bezier"]], c["dur"]),
                       "rotation": fx._frame_keys([[0, 0], [6 / f, 0, "bezier"], [_last(fx, c), rot, "bezier"]], c["dur"])}
    _cue(fx, cue_sfx, clip["at"], "paper", 5 / f, "paper_rip")
    return _tin(clip, "cross_dissolve", 1)


def _card_push_out(fx, before: dict, clip: dict, n: int, dx: float) -> None:
    """Đuôi cảnh trước (nguồn kéo dài qua điểm cắt) trượt trái cùng nhịp thẻ trượt vào → không còn khoảng đen; bỏ qua nếu nguồn hết."""
    at, src = clip["at"], before["src"]
    t_in = round(before["in"] + before["dur"], 4)
    if t_in + n / fx.fps + 0.05 > _src_len(src):
        return
    c = fx.image(src, at, n / fx.fps, lane="trans", name="Đuôi cảnh trước")
    c.update({"in": t_in, "audio": False})
    sc = _scale_fn(before)(before["dur"])
    c["motion"] = {"scale": sc, "position": fx._frame_keys([[0, [540, 960], "bezier"], [(n - 1) / fx.fps, [540 - dx, 960], "bezier"]], c["dur"])}
    fx._fx(c, "directional_blur", {"direction": 90, "length": fx._frame_keys([[0, 0], [(n // 2) / fx.fps, 50], [(n - 1) / fx.fps, 0]], c["dur"])})


def card_swipe(fx, clip: dict, cue_sfx: bool = True, scale: float = 92, before: dict | None = None) -> dict:
    """B-roll thành thẻ bo góc có bóng, trượt từ phải vào 14 khung (bezier, nhoè ngang đỉnh giữa chừng, thu 98 → `scale` %) rồi nằm yên.
    Có `before`: đuôi cảnh trước trượt trái cùng nhịp (kiểu push) thay vì để lộ nền đen."""
    n, dx = 14, 1100
    x, y = fx._pos_of(clip)
    clip.setdefault("motion", {}).update({
        "scale": fx._frame_keys([[0, round(scale * 1.065, 2), "bezier"], [(n - 1) / fx.fps, scale, "bezier"]], clip["dur"]),
        "position": fx._frame_keys([[0, [x + dx, y], "bezier"], [(n - 1) / fx.fps, [x, y], "bezier"]], clip["dur"])})
    fx._fx(clip, "directional_blur", {"direction": 90, "length": fx._frame_keys([[0, 0], [(n // 2) / fx.fps, 50], [(n - 1) / fx.fps, 0]], clip["dur"])})
    fx._fx(clip, "rounded_crop", {"radius": 36, "border": 6, "border_color": "#FAFAFA"})
    fx._fx(clip, "drop_shadow", {"opacity": 55, "distance": 14, "softness": 40})
    if before is not None:
        _card_push_out(fx, before, clip, n, dx)
    _cue(fx, cue_sfx, clip["at"], "whoosh", n / 2 / fx.fps + 0.02, "card_swipe")
    return clip


def smoke_veil(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Khói trắng (OVL_Smoke_Matte, blend screen) mờ 0 → 70 → 0 bezier trong 20 khung phủ điểm cắt, cross_dissolve 8 khung bên dưới."""
    n = 20 / fx.fps
    c = fx.image(str(SMOKE_SRC), clip["at"] - n / 2, n, lane="trans", name="Màn khói")
    c.update({"in": 1.0, "audio": False, "blend": "screen", "motion": {"rotation": 90, "scale": 177.8}})
    c["opacity"] = fx._frame_keys([[0, 0, "bezier"], [n / 2, 70, "bezier"], [_last(fx, c), 0, "bezier"]], c["dur"])
    _overlap(fx, clip, before, "smoke_veil")
    _cue(fx, cue_sfx, clip["at"], "leak", n / 2, "smoke_veil")
    return _tin(clip, "cross_dissolve", 8)


SHAKE_AMOUNT = 55    # profile key: transitions.impact_shake.amount (28 cũ: rung hầu như không thấy trên bản dựng thử 2026-11-17)


def impact_shake(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Rung máy 55 → 0 (không loé trắng như flash_shake): camera_shake zoom 5, nhoè 50; cho câu chốt / từ khoá. Có `before`: đuôi cảnh
    trước phóng 100 → 105 % (4 khung) vào cú rung; đầu cảnh sau vào 106 → 100 %; hoà tan 2 khung che chỗ nhảy."""
    _overlap(fx, clip, before, "impact_shake")
    fx._fx(clip, "camera_shake", {"amount": [[0, SHAKE_AMOUNT], [fx._k(clip, 0.35), 0]], "rotation": 2.0, "zoom": 5, "frequency": 9,
                                  "complexity": 3, "motion_blur": 50})
    _cue(fx, cue_sfx, clip["at"], "boom_pre", 0.1, "impact_shake")
    _cue(fx, cue_sfx, clip["at"], "key_hit", 0.05, "impact_shake")
    return _tin(clip, "cross_dissolve", 2)


def vhs_rewind(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """vhs_damage 9 khung + rgb_split 30 → 0 (cho "lỗi" / nhớ lại)."""
    _tin(clip, "vhs_damage", 9)
    fx._fx(clip, "rgb_split", {"mode": "Linear", "amount": [[0, 30], [fx._k(clip, 0.22), 0]], "angle": 0})
    _cue(fx, cue_sfx, clip["at"], "glitch", 9 / 2 / fx.fps + 0.02, "vhs_rewind")
    return clip


def chapter_card_slam(fx, clip: dict, cue_sfx: bool = True, text: str | None = None, before: dict | None = None) -> dict:
    """Thẻ giấy phủ khung 24 khung (vào 6 · giữ 12 · ra 6, scale 108 → 100 % easeIn), điểm cắt nằm dưới thẻ; `text` ("2.", "Bước 3")
    đặt giữa thẻ."""
    import fx_gfx as G
    from style_profile import get as sp_get, load as sp_load
    f, at = fx.fps, clip["at"] - 9 / fx.fps
    card = fx.image(G.paper_bg(fx.gfx_dir, "chapter_paper", "white", 0), at, 24 / f, lane="trans", name="Thẻ chương")
    opa = [[0, 0, "bezier"], [6 / f, 100, "bezier"], [16 / f, 100, "bezier"], [23 / f, 0, "bezier"]]
    card["opacity"] = fx._frame_keys(opa, card["dur"])
    card["motion"] = {"scale": fx._frame_keys([[0, 108], [9 / f, 100, "easeIn"]], card["dur"])}
    if text:
        ink = sp_get(sp_load(name="minimal-edu"), "text.colors.on_paper", "#111111")
        t = fx.text(text, at, 24 / f, role="mx_heavy", size=260, y=1010, color=ink, shadow=None, name=f"Chữ chương {text}")
        t["opacity"] = fx._frame_keys(opa, t["dur"])
    _cue(fx, cue_sfx, at + 3 / f, "key_hit", 0.05, "chapter_card_slam")
    return _tin(clip, "cross_dissolve", 1)


# ---- 3.6.4 năng động: nháy sáng · nhóm máy quay · rò sáng (user 2026-11-17: "flicker, flash, shake, zoom punch, whip, spin") ----
def _flip(fx) -> int:
    """+1 / −1 luân phiên mỗi lần gọi (hướng whip_pan / spin_roll đảo chiều, không lặp một phía)."""
    fx.th_state["flip"] = fx.th_state.get("flip", 0) + 1
    return 1 if fx.th_state["flip"] % 2 else -1


def _flash_overlay(fx, clip: dict, pts: list, name: str, ease: str | None = "bezier") -> dict:
    """Tấm trắng phủ khung (lane trans: dưới chữ). pts = [(khung so với điểm cắt, độ mờ 0–100)]; điểm đầu / cuối phải 0."""
    f, at = fx.fps, clip["at"]
    f0 = pts[0][0]
    c = fx.image(_white_panel(fx), at + f0 / f, (pts[-1][0] - f0 + 1) / f, lane="trans", name=name)
    c["opacity"] = fx._frame_keys([[(fr - f0) / f, op, *([ease] if ease else [])] for fr, op in pts], c["dur"])
    return c


def _white_panel(fx) -> str:
    import fx_gfx as G
    return G.solid_panel(fx.gfx_dir, "flash_white", "#FFFFFF")


def flash_cut(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Loé trắng: lên 3 khung bezier, đỉnh 95 % phủ đúng khung cắt (giữ 1 khung), tắt 4 khung; punch hai phía (đuôi 105 %, đầu 108 → 100 %)."""
    _flash_overlay(fx, clip, [(-3, 0), (0, 95), (1, 95), (5, 0)], "Loé trắng")
    _overlap(fx, clip, before, "flash_cut")
    _cue(fx, cue_sfx, clip["at"], "flash_hit", 0.1, "flash_cut")
    return _tin(clip, "cross_dissolve", 1)


def double_flash(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Hai nhịp loé: 95 % đúng khung cắt, tắt hẳn ở +3, loé lại 70 % ở +5…+6 khung (tiếng màn trập)."""
    pts = [(-3, 0), (0, 95), (1, 95), (3, 0), (5, 70), (6, 70), (8, 0)]
    _flash_overlay(fx, clip, pts, "Loé đôi")
    _overlap(fx, clip, before, "double_flash")
    _cue(fx, cue_sfx, clip["at"], "flash_hit", 0.1, "double_flash")
    _cue(fx, cue_sfx, clip["at"] + 5 / fx.fps, "shutter", 0.04, "double_flash")
    return _tin(clip, "cross_dissolve", 1)


def flicker_cut(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Nhấp nháy: 5 xung trắng 1 khung (60 · 80 · 100 đúng khung cắt · 60 · 30 %) cách 1 khung tối — không easing (xung phải gắt)."""
    pts = [(-5, 0), (-4, 60), (-3, 0), (-2, 80), (-1, 0), (0, 100), (1, 0), (2, 60), (3, 0), (4, 30), (5, 0)]
    _flash_overlay(fx, clip, pts, "Nhấp nháy", ease=None)
    _overlap(fx, clip, before, "flicker_cut")
    _cue(fx, cue_sfx, clip["at"] - 5 / fx.fps, "glitch", 0.04, "flicker_cut")
    return _tin(clip, "cross_dissolve", 1)


def zoom_punch_in(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Phóng vút vào: đuôi cảnh trước 100 → 114 % (8 khung, tăng tốc, nhoè 10), cảnh sau vào 114 → 100 % (10 khung, giảm tốc)."""
    _overlap(fx, clip, before, "zoom_punch_in")
    _cue(fx, cue_sfx, clip["at"], "whoosh", 0.2, "zoom_punch_in")
    return _tin(clip, "cross_dissolve", 3)


def zoom_punch_out(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Kéo lùi: cảnh sau vào 128 → 100 % trong 10 khung giảm tốc (nhoè 14 → 0), đuôi cảnh trước chỉ nén nhẹ 103 %."""
    _overlap(fx, clip, before, "zoom_punch_out")
    _cue(fx, cue_sfx, clip["at"], "pop", 0.05, "zoom_punch_out")
    return _tin(clip, "cross_dissolve", 1)             # 128 % ≠ 103 % ở điểm cắt: hoà tan dài thành bóng ma, để nhoè 14 che chỗ nhảy


WHIP_PX, WHIP_BLUR = 80, 140       # profile key: transitions.whip_pan.{pan_px, blur}; WHIP_PX ≤ (scale-1)·540 = 86 (không hở viền)


def whip_pan(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Lia nhanh: đuôi cảnh trước (4 khung) phóng 116 % + dịch 80 px tăng tốc + nhoè ngang 140; đầu cảnh sau (8 khung) vào từ phía đối
    diện, giảm tốc về 100 %. Hướng đảo chiều mỗi lần gọi; clip đã có position riêng thì chỉ còn phóng + nhoè."""
    sg = _flip(fx)
    n_o, _, _, n_i, _, _ = ENERGY["whip_pan"]
    _overlap(fx, clip, before, "whip_pan")
    _pan_env(fx, clip, 0, n_i - 1, lambda u: sg * WHIP_PX * (1 - u) ** 3)
    _pan_blur(fx, clip, 0, n_i - 1, False, WHIP_BLUR)
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _pan_env(fx, before, nb - n_o, nb - 1, lambda u: -sg * WHIP_PX * u * u)
        _pan_blur(fx, before, nb - n_o, nb - 1, True, WHIP_BLUR)
    _cue(fx, cue_sfx, clip["at"], "whoosh", n_o / fx.fps + 0.02, "whip_pan")
    return _tin(clip, "cross_dissolve", 3)


SPIN_DEG = 6        # profile key: transitions.spin_roll.degrees; scale 1.22 ≥ cosθ + (H/W)·sinθ = 1.18 che hết góc


def _rot_env(fx, clip: dict, f0: int, f1: int, deg) -> None:
    """Xoay motion.rotation theo deg(u) độ trên khung f0..f1 (bỏ qua nếu clip đã có keyframe rotation riêng)."""
    n = round(clip["dur"] * fx.fps)
    f0, f1 = max(0, f0), min(n - 1, f1)
    base = clip.get("motion", {}).get("rotation", 0)
    if f1 <= f0 or _keyed(base):
        return
    keys = ([[0, base]] if f0 > 0 else []) + [[fr / fx.fps, round(base + deg((fr - f0) / (f1 - f0)), 2)] for fr in range(f0, f1 + 1)]
    keys += [[(n - 1) / fx.fps, base]] if f1 < n - 1 else []
    clip.setdefault("motion", {})["rotation"] = fx._frame_keys(keys, clip["dur"])


def spin_roll(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Xoay máy: đuôi cảnh trước (5 khung) xoay 6° + phóng 122 % tăng tốc, cảnh sau (10 khung) vào lệch −6° rồi giảm tốc về 0° / 100 %
    (cùng đường cong nên scale luôn che hết góc); nhoè 8; hướng đảo chiều mỗi lần gọi."""
    sg = _flip(fx)
    n_o, _, _, n_i, _, _ = ENERGY["spin_roll"]
    _overlap(fx, clip, before, "spin_roll")
    _rot_env(fx, clip, 0, n_i - 1, lambda u: sg * SPIN_DEG * (1 - u) ** 3)
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _rot_env(fx, before, nb - n_o, nb - 1, lambda u: -sg * SPIN_DEG * u * u)
    _cue(fx, cue_sfx, clip["at"], "whoosh", n_o / fx.fps + 0.02, "spin_roll")
    return _tin(clip, "cross_dissolve", 2)


LENS_CURVE = 45     # profile key: transitions.lens_warp.curvature; dương = ảnh phình ra (mép kéo ra ngoài, không hở viền; âm thì hở góc đen)


def lens_warp(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Méo ống kính: lens_distortion curvature 0 → +45 (6 khung đuôi, tăng tốc) rồi +45 → 0 (10 khung đầu, giảm tốc) + phóng 110 %."""
    n_o, _, _, n_i, _, _ = ENERGY["lens_warp"]
    _overlap(fx, clip, before, "lens_warp")
    _ramp_fx(fx, clip, "lens_distortion", "curvature", 0, n_i - 1, LENS_CURVE, False)
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _ramp_fx(fx, before, "lens_distortion", "curvature", nb - n_o, nb - 1, LENS_CURVE, True)
    _cue(fx, cue_sfx, clip["at"], "whoosh", n_o / fx.fps + 0.02, "lens_warp")
    return _tin(clip, "cross_dissolve", 3)


RGB_SPLIT = 45      # profile key: transitions.rgb_split_cut.amount


def rgb_split_cut(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Tách màu RGB hai phía: đuôi 0 → 45 (5 khung tăng tốc), đầu 45 → 0 (8 khung giảm tốc); không nháy sáng."""
    n_o, _, _, n_i, _, _ = ENERGY["rgb_split_cut"]
    _overlap(fx, clip, before, "rgb_split_cut")
    _ramp_fx(fx, clip, "rgb_split", "amount", 0, n_i - 1, RGB_SPLIT, False, {"mode": "Linear", "angle": 0})
    if before is not None:
        nb = round(before["dur"] * fx.fps)
        _ramp_fx(fx, before, "rgb_split", "amount", nb - n_o, nb - 1, RGB_SPLIT, True, {"mode": "Linear", "angle": 0})
    _cue(fx, cue_sfx, clip["at"], "glitch", 0.04, "rgb_split_cut")
    return _tin(clip, "cross_dissolve", 2)


def trans_ready(kind: str) -> bool:
    """Overlay TNEDIT của `kind` (motion_fx.TRANS) có trên máy không."""
    import motion_fx as M
    return Path(M.TRANS[kind]["src"]).exists()


def _tnedit(fx, clip: dict, kind: str, cue_sfx: bool, before: dict | None) -> dict:
    """Overlay TNEDIT (motion_fx.TRANS) có khung sáng nhất đúng điểm cắt; mỗi lần gọi một biến thể (xoay vòng). Thiếu thư viện → nháy
    trắng đơn (flash_cut) thay thế."""
    if not trans_ready(kind):
        return flash_cut(fx, clip, cue_sfx, before)
    n0, v = len(fx.cues), fx.th_state.setdefault("variant", {})
    fx.transition(clip["at"], kind, clip_after=clip, variant=v.get(kind, 0))
    v[kind] = v.get(kind, 0) + 1
    if not cue_sfx:
        del fx.cues[n0:]
    _overlap(fx, clip, before, kind)
    return clip


def light_leak(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Rò sáng (đổi chủ đề): overlay light_leak TNEDIT, khung sáng nhất đúng điểm cắt, SFX suck_in + leak; đuôi / đầu phóng nhẹ hai phía."""
    return _tnedit(fx, clip, "light_leak", cue_sfx, before)


def film_burn(fx, clip: dict, cue_sfx: bool = True, before: dict | None = None) -> dict:
    """Cháy phim Casey Neistat (đổi chủ đề): overlay film_burn TNEDIT kèm tiếng có sẵn trong file, đỉnh sáng đúng điểm cắt."""
    return _tnedit(fx, clip, "film_burn", cue_sfx, before)


_KEYED_FN = {"camera_continue": camera_continue, "punch_settle": punch_settle, "drift_reset": drift_reset, "j_cut_return": j_cut_return, "dip_to_paper": dip_to_paper,
             "paper_rip": paper_rip, "card_swipe": card_swipe, "smoke_veil": smoke_veil, "impact_shake": impact_shake,
             "vhs_rewind": vhs_rewind, "chapter_card_slam": chapter_card_slam,
             "flash_cut": flash_cut, "double_flash": double_flash, "flicker_cut": flicker_cut, "zoom_punch_in": zoom_punch_in,
             "zoom_punch_out": zoom_punch_out, "whip_pan": whip_pan, "spin_roll": spin_roll, "lens_warp": lens_warp,
             "rgb_split_cut": rgb_split_cut, "light_leak": light_leak, "film_burn": film_burn}


JOIN_MARK = " ⇢ "                                   # tên clip "… ⇢ <kiểu>": dấu cho edit_rules (FilmCraft không nhận khoá lạ)


def mark(clip: dict, kind: str) -> dict:
    """Ghi kiểu chuyển cảnh vào tên clip sau điểm cắt (thay dấu cũ nếu có); "hard_cut" cũng ghi được."""
    clip["name"] = clip.get("name", "").split(JOIN_MARK)[0] + JOIN_MARK + kind
    return clip


def join_kind(clip: dict) -> str | None:
    name = clip.get("name", "")
    return name.rsplit(JOIN_MARK, 1)[1] if JOIN_MARK in name else None


def th_join(fx, clip: dict, kind: str, cue_sfx: bool = True, before: dict | None = None, **opts) -> dict:
    """Gắn chuyển cảnh `kind` (TH_KINDS) vào đầu `clip` (clip sau điểm cắt); `before` = clip ngay trước điểm cắt (tuỳ chọn, nên truyền:
    đuôi nó cũng chuyển động / nhoè để chuyển cảnh mượt hai phía); `opts` = tham số riêng của kiểu."""
    if kind not in TH_KINDS:
        raise ValueError(f"kiểu chuyển cảnh lạ: {kind} (có: {', '.join(sorted(TH_KINDS))})")
    mark(clip, kind)
    if kind in TH_JOINS:
        return _simple(fx, clip, kind, cue_sfx, before)
    return _KEYED_FN[kind](fx, clip, cue_sfx, before=before, **opts)
