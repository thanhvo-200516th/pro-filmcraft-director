#!/usr/bin/env python3
"""
Tests for the skill code of package S1 (v7.7.0): pop-out studio card, alpha-guarded wall cleaner,
`studio_14` audio profile wiring, `fc_export` job polling, swash / glow / echo in `web_plate_builder`,
SFX source clipping after gain.

Plain assert functions with a `__main__` runner (pytest is not installed). Run: `python3 tests/test_skill_v77.py`.
The "unchanged" golden hashes below were taken from the pre-change compositor (v7.6.0 working tree) on the synthetic
inputs built here; they only hold for the same OpenCV / NumPy build (`--print-golden` prints the current ones).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
TOOLS_DIR = SCRIPTS_DIR / "tools"
OVS_TOOLS = SCRIPTS_DIR / "vendor" / "ovs_core" / "scripts" / "apps" / "craft-handoff" / "tools"
OVS_AUDIT = SCRIPTS_DIR / "vendor" / "ovs_core" / "scripts" / "apps" / "talking-head-premiere" / "scripts" / "audit_sfx.py"
OVS_MANIFEST = SCRIPTS_DIR / "vendor" / "ovs_core" / "scripts" / "audit_sfx.py"

for p in (str(SCRIPTS_DIR), str(TOOLS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

W, H = 1080, 1920

# sha256 of the pre-change renders on `_legacy_inputs()` (see module docstring)
GOLDEN_CV5 = {
    "cleaner_no_alpha": "18e9c68b8e309f73191660c366cd877200d9ebe41b5d010fba0a023e248d963a",
    "full_head_card": "31a9a44412b18b63ecbab8ec13be26dee384af137705a61963f1c23d0648a27f",
    "squircle_pip": "1cbe6afafd60d673d943a63195c7d0e8b6d4481bfda4039b38a062ef2d477a55",
    "bottom_flush": "f5bb3a73616d5f84a2defd2d69c274ba979f3cc20438c66dff2f08e5d7b5bd01",
}
# OpenCV 4.x (pinned by requirements.txt since v7.9.1) resamples a few bits differently; these were taken from the
# committed v7.9.1 compositor (7f7b482, bit-identical to the pre-change render under OpenCV 5) on opencv-python-headless 4.14.
GOLDEN_CV4 = {
    "cleaner_no_alpha": "18e9c68b8e309f73191660c366cd877200d9ebe41b5d010fba0a023e248d963a",
    "full_head_card": "9f2a90c9ae30cbd7fbb6b916b9a81396d8565ecc085e8728898dde3f4ba0d58d",
    "squircle_pip": "1cbe6afafd60d673d943a63195c7d0e8b6d4481bfda4039b38a062ef2d477a55",
    "bottom_flush": "3221dae349dc3cb2c1dba3917d48917a35e77bd2cd465ff430fa50ca4c3cedb7",
}
GOLDEN = GOLDEN_CV5 if int(cv2.__version__.split(".")[0]) >= 5 else GOLDEN_CV4


# ---------------------------------------------------------------------------------------------- synthetic inputs
def _legacy_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(wall, frame, person_alpha) copied from tests/test_skill_v73.py::test_03: thin rack hook + hair dome."""
    wall = np.full((H, W, 3), (62, 78, 92), dtype=np.uint8)
    wall[780:835, 440:446] = (18, 20, 22)
    frame = wall.copy()
    cv2.ellipse(frame, (460, 895), (95, 90), 0, 0, 360, (20, 24, 30), -1)
    pa = np.zeros((H, W), dtype=np.uint8)
    cv2.ellipse(pa, (540, 1450), (380, 520), 0, 0, 360, 255, -1)
    return wall, frame, pa


def _sha(*arrays: np.ndarray) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def _legacy_hashes() -> dict[str, str]:
    import fast_studio_compositor as fsc

    wall, frame, pa = _legacy_inputs()
    fsc.init_hair_safe_wall_reference(wall, cache_key="v77_golden")
    cleaned = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_golden")
    bg = np.full((H, W, 3), 242, dtype=np.uint8)
    a1, _ = fsc.render_full_head_studio_card(bg, cleaned, card_rect=(86, 775, 994, 1825))
    a2, _ = fsc.render_squircle_pip_window(bg, cleaned, pip_rect=(700, 1400, 1012, 1800))
    b, _ = fsc.render_bottom_flush_cutout(bg, cleaned, pa)
    return {
        "cleaner_no_alpha": _sha(cleaned),
        "full_head_card": _sha(a1),
        "squircle_pip": _sha(a2),
        "bottom_flush": _sha(b),
    }


def _popout_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(backdrop, aroll, alpha, person_colour): smooth grey-blue A-roll with a saturated red head, crown at (340, 549)."""
    import fast_studio_compositor as fsc

    backdrop = fsc.render_lavender_paper(W, H)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    aroll = np.stack([150 + 20 * xx / W, 120 + 25 * yy / H, 110 + 10 * xx / W], axis=2).astype(np.uint8)
    alpha = np.zeros((H, W), np.uint8)
    cv2.ellipse(alpha, (340, 549 + 130), (110, 130), 0, 0, 360, 255, -1)
    cv2.rectangle(alpha, (150, 800), (530, 1900), 255, -1)  # shoulders / torso
    aroll[alpha > 0] = (40, 60, 200)
    return backdrop, aroll, alpha, np.array([40, 60, 200], np.uint8)


# ---------------------------------------------------------------------------------------------- (1) pop-out card
def test_01_popout_head_is_outside_the_card_and_seam_is_continuous() -> None:
    import fast_studio_compositor as fsc

    backdrop, aroll, alpha, person = _popout_inputs()
    out, meta = fsc.render_popout_studio_card(backdrop, aroll, alpha)
    x0, y0, x1, y1 = meta["card_rect"]
    assert (x0, y0, x1, y1) == (70, 1065, 1010, 1705)   # v7.8.0 defaults (v7.7.0: 90, 1030, 990, 1700)
    assert out.shape == backdrop.shape and out.dtype == np.uint8
    assert abs(meta["pop_height_px"] - 165.0) < 1e-6, meta   # v7.8.0 (v7.7.0: 130)
    hx = 540
    # (1) the head is drawn ABOVE the card top edge, on the backdrop
    px = out[y0 - 5, hx].astype(int)
    assert np.abs(px - backdrop[y0 - 5, hx].astype(int)).max() > 60, "no head pixel above the card"
    assert np.abs(px - person.astype(int)).max() <= 6, f"head pixel above the card is not the person: {px}"
    # the crown lands on head_out_xy: first person row near y=900
    col = np.abs(out[:, hx].astype(int) - backdrop[:, hx].astype(int)).sum(1)
    top = int(np.argmax(col[800:1030] > 90)) + 800
    assert 893 <= top <= 912, f"crown row {top}"
    # (2) below the top edge the card shows the SAME photo (one affine for card and cut-out)
    M = np.array([[1.36, 0, 540 - 1.36 * 340], [0, 1.36, 900 - 1.36 * 549]], np.float32)
    photo = cv2.warpAffine(aroll, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
    for x in (480, 540, 600):
        d = np.abs(out[y0 + 80, x].astype(int) - photo[y0 + 80, x].astype(int)).max()
        assert d <= 2, f"card photo differs at x={x}: {d}"
    # seam: rows just above and just below the edge agree
    for dy in (2, 6, 20):
        d = np.abs(out[y0 - dy, hx].astype(int) - out[y0 + dy, hx].astype(int)).max()
        assert d <= 12, f"seam break at dy={dy}: {d}"
    print("[PASS] 01 pop-out: head above the card, crown at head_out_xy, card = same photo, seam continuous")


def test_02_popout_no_person_gives_no_head_and_inputs_are_not_mutated() -> None:
    import fast_studio_compositor as fsc

    backdrop, aroll, alpha, _ = _popout_inputs()
    b0, a0, al0 = backdrop.copy(), aroll.copy(), alpha.copy()
    out_none, meta = fsc.render_popout_studio_card(backdrop, aroll, np.zeros_like(alpha))
    y0 = meta["card_rect"][1]
    band = np.abs(out_none[y0 - 100 : y0 - 8, 440:640].astype(int) - backdrop[y0 - 100 : y0 - 8, 440:640].astype(int))
    assert band.max() <= 40, f"only the soft shadow may reach above the card, got {band.max()}"
    out_head, _ = fsc.render_popout_studio_card(backdrop, aroll, alpha)
    band_h = np.abs(out_head[y0 - 100 : y0 - 8, 440:640].astype(int) - backdrop[y0 - 100 : y0 - 8, 440:640].astype(int))
    assert band_h.max() > 100
    assert np.array_equal(backdrop, b0) and np.array_equal(aroll, a0) and np.array_equal(alpha, al0), "inputs mutated"
    print("[PASS] 02 pop-out: empty alpha -> no head pixels above the card; inputs untouched")


def test_03_popout_fringe_is_decontaminated() -> None:
    """A dark wall halo inside the soft alpha edge must not show up on the crown edge of the output."""
    import fast_studio_compositor as fsc

    backdrop, aroll, alpha, person = _popout_inputs()
    wall = np.array([60, 52, 48], np.uint8)  # dark wall (BGR)
    ar = aroll.copy()
    soft = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), 3.0)  # 0..255 soft edge
    edge = (soft > 20) & (alpha == 0)
    ar[edge] = wall
    ar[(alpha == 255)] = person
    # edge pixels carry a mix wall*(1-a)+person*a, as a real RVM fringe does
    a = (soft / 255.0)[:, :, None]
    mix = (wall.astype(np.float32) * (1 - a) + person.astype(np.float32) * a).astype(np.uint8)
    ar[(soft > 5) & (soft < 250)] = mix[(soft > 5) & (soft < 250)]
    out_dirty, _ = fsc.render_popout_studio_card(backdrop, ar, soft.astype(np.uint8))
    out_clean, _ = fsc.render_popout_studio_card(backdrop, aroll, soft.astype(np.uint8))
    y0 = 1065
    # compare the left crown edge band (x ~ 420..470 at y ~ 940..1000) against the clean-photo render
    ys, xs = slice(940, 1000), slice(400, 480)
    diff = np.abs(out_dirty[ys, xs].astype(int) - out_clean[ys, xs].astype(int)).mean()
    assert diff < 14.0, f"fringe contamination reaches the output: mean diff {diff:.1f}"
    assert y0 > 0
    print(f"[PASS] 03 pop-out: dark-wall fringe decontaminated (mean edge diff {diff:.1f})")


def test_04_popout_ab_flag_off_is_bit_identical_and_caches_rig() -> None:
    import fast_studio_compositor as fsc

    wall, frame, pa = _legacy_inputs()
    bg = np.full((H, W, 3), 242, dtype=np.uint8)
    fsc.init_hair_safe_wall_reference(wall, cache_key="v77_flag")
    cleaned = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_flag")
    direct, bb = fsc.render_full_head_studio_card(bg, cleaned, card_rect=(86, 775, 994, 1825))
    assert fsc.LOOK_S_POPOUT is False, "the 'Look S pop-out' flag must default to OFF"
    via, bb2 = fsc.render_studio_card_ab(bg, cleaned, pa, card_rect=(86, 775, 994, 1825))
    assert np.array_equal(direct, via) and bb == bb2, "flag off must be bit-identical to render_full_head_studio_card"
    via_off, _ = fsc.render_studio_card_ab(bg, cleaned, pa, popout=False, card_rect=(86, 775, 994, 1825))
    assert np.array_equal(direct, via_off)
    on, meta = fsc.render_studio_card_ab(bg, cleaned, pa, popout=True)
    assert "pop_height_px" in meta and on.shape == direct.shape
    n_before = len(fsc._POPOUT_RIG_CACHE)
    backdrop, aroll, alpha, _ = _popout_inputs()
    fsc.render_popout_studio_card(backdrop, aroll, alpha)
    fsc.render_popout_studio_card(backdrop, aroll, alpha)
    assert len(fsc._POPOUT_RIG_CACHE) <= n_before + 1, "mask / remap maps must be cached by (card_rect, rx, bulge, sag)"
    print("[PASS] 04 'Look S pop-out' A/B flag: off = bit-identical rounded card, rig cache by geometry")


def test_05_popout_helpers_paper_and_headline() -> None:
    import fast_studio_compositor as fsc

    paper = fsc.render_lavender_paper(W, H, tint_rgb=(250, 228, 253), seed_glow_y=0.40)
    assert paper.shape == (H, W, 3) and paper.dtype == np.uint8
    assert paper[H - 4, W // 2].min() > 240, "bottom of the paper is near white"
    assert paper[int(0.4 * H), W // 2, 1] < paper[H - 4, W // 2, 1], "tinted core around seed_glow_y"
    p0 = paper.copy()
    head = fsc.render_gradient_italic_headline(paper, "1 lỗi phổ biến", "mà", (540, 690), 860, (124, 104, 238), (252, 246, 255), 0.30)
    assert head.shape == paper.shape and np.array_equal(paper, p0), "backdrop must not be mutated"
    changed = np.abs(head.astype(int) - paper.astype(int)).sum(2) > 30
    ys, xs = np.where(changed)
    assert ys.size > 2000, "headline drew nothing"
    assert 580 <= ys.min() and ys.max() <= 935 and 80 <= xs.min() and xs.max() <= 1000, (ys.min(), ys.max(), xs.min(), xs.max())
    print("[PASS] 05 lavender paper + gradient italic headline")


# ---------------------------------------------------------------------------------------------- (2) wall cleaner
def _dark_wall_case() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame = np.full((H, W, 3), (26, 27, 27), np.uint8)  # sum 80: below the old fixed 108 floor
    # coat rack: rail + prongs, sum ~20, well inside the compositor ROI 0 mask (268..650 x 760..853)
    cv2.rectangle(frame, (300, 790), (620, 800), (6, 7, 7), -1)
    for x in (320, 380, 440, 500, 560):
        cv2.rectangle(frame, (x, 800), (x + 6, 840), (6, 7, 7), -1)
    ref = frame.copy()  # low-head reference: the rack is there, the speaker is not
    # speaker hair crown in front of the lower right of the ROI (dark, sum ~30) with an alpha
    alpha = np.zeros((H, W), np.uint8)
    cv2.ellipse(alpha, (560, 905), (90, 80), 0, 0, 360, 255, -1)
    frame[alpha > 0] = (10, 10, 10)
    return ref, frame, alpha


def _rack_residual(img: np.ndarray, alpha: np.ndarray) -> int:
    x0, y0, x1, y1 = 262, 752, 664, 858
    s = img[y0:y1, x0:x1].astype(int).sum(2)
    return int(((s < 64) & (alpha[y0:y1, x0:x1] < 20)).sum())


def test_06_alpha_wall_cleaner_dark_wall_removes_rack_and_keeps_hair() -> None:
    import fast_studio_compositor as fsc

    ref, frame, alpha = _dark_wall_case()
    f0, a0 = frame.copy(), alpha.copy()
    fsc.init_hair_safe_wall_reference(ref, cache_key="v77_dark")
    assert _rack_residual(frame, alpha) > 1500, "fixture must contain rack pixels"
    out = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_dark", person_alpha_u8=alpha)
    assert _rack_residual(out, alpha) == 0, f"{_rack_residual(out, alpha)} residual rack pixels"
    # hair is untouched deep inside the alpha
    assert np.array_equal(out[905, 560], frame[905, 560]) and np.array_equal(out[880:930, 540:580][20:30, 15:25], frame[880:930, 540:580][20:30, 15:25])
    # the wall around is still the wall colour (delta estimated from the ring, not dragged by hair)
    assert np.abs(out[775, 470].astype(int) - np.array([26, 27, 27])).max() <= 3, out[775, 470]
    assert np.array_equal(frame, f0) and np.array_equal(alpha, a0), "inputs mutated"
    print("[PASS] 06 alpha-guarded wall cleaner: dark wall (sum 80), 0 residual rack pixels, hair kept")


def test_07_alpha_wall_cleaner_skips_dome_blocks() -> None:
    """With an alpha the dome / idx==2 heuristics are skipped: a dark blob that is NOT person is cleaned in ROI 2."""
    import fast_studio_compositor as fsc

    ref = np.full((H, W, 3), (62, 78, 92), np.uint8)
    frame = ref.copy()
    frame[1090:1110, 220:290] = (14, 16, 18)  # dark switch plate inside ROI 2, not a person
    fsc.init_hair_safe_wall_reference(ref, cache_key="v77_roi2")
    no_alpha = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_roi2")
    with_alpha = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_roi2", person_alpha_u8=np.zeros((H, W), np.uint8))
    wallc = np.array([62, 78, 92])
    d_no = int(np.abs(no_alpha[1095:1105, 230:280].astype(int) - wallc).max())
    d_al = int(np.abs(with_alpha[1095:1105, 230:280].astype(int) - wallc).max())
    assert d_al < d_no and d_al <= 10, (d_no, d_al)
    print("[PASS] 07 alpha path skips the dome / left-switch hair heuristics")


def test_08_no_alpha_path_is_unchanged() -> None:
    import fast_studio_compositor as fsc

    cur = _legacy_hashes()
    if "--print-golden" in sys.argv:
        print(json.dumps(cur, indent=1))
    for k, v in GOLDEN.items():
        assert cur[k] == v, f"{k}: pre-change render drifted ({cur[k][:12]} != {v[:12]})"
    wall, frame, pa = _legacy_inputs()
    fsc.init_hair_safe_wall_reference(wall, cache_key="v77_same")
    a = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_same")
    b = fsc.clean_aroll_preserve_hair_crown(frame, cache_key="v77_same", person_alpha_u8=None)
    assert np.array_equal(a, b), "person_alpha_u8=None must equal the legacy call"
    bg = np.full((H, W, 3), 242, dtype=np.uint8)
    c1, _ = fsc.render_full_head_studio_card(bg, a, card_rect=(86, 775, 994, 1825))
    c2, _ = fsc.render_full_head_studio_card(bg, a, card_rect=(86, 775, 994, 1825), person_alpha_u8=None)
    assert np.array_equal(c1, c2)
    print("[PASS] 08 no-alpha path bit-identical to the pre-change render (cleaner, A1, A2, B)")


def test_09_renderers_pass_the_alpha_to_the_cleaner() -> None:
    import fast_studio_compositor as fsc

    ref, frame, alpha = _dark_wall_case()
    fsc.init_hair_safe_wall_reference(ref, cache_key="v77_pass")
    bg = np.full((H, W, 3), 242, dtype=np.uint8)
    real = fsc.clean_aroll_preserve_hair_crown
    seen: list[tuple[str, bool, str]] = []

    def spy(src, *, cache_key="v73_studio_ref", ema_state=None, person_alpha_u8=None):
        seen.append((cache_key, person_alpha_u8 is not None and person_alpha_u8.shape == alpha.shape and bool(np.array_equal(person_alpha_u8, alpha)), ""))
        return real(src, cache_key=cache_key, ema_state=ema_state, person_alpha_u8=person_alpha_u8)

    fsc.clean_aroll_preserve_hair_crown = spy
    try:
        # A1 really removes the rack inside the card
        card = dict(card_rect=(86, 600, 994, 1700), cam_scale=1.0, cam_dy=0.0)
        raw, _ = fsc.render_full_head_studio_card(bg, frame, **card)
        assert not seen, "no alpha -> the cleaner must not run"
        cl, _ = fsc.render_full_head_studio_card(bg, frame, person_alpha_u8=alpha, wall_cache_key="v77_pass", **card)
        assert not np.array_equal(raw, cl), "render_full_head_studio_card ignored person_alpha_u8"
        # A2 and B hand the same alpha to the cleaner
        fsc.render_squircle_pip_window(bg, frame, pip_rect=(100, 700, 700, 1300), person_alpha_u8=alpha, wall_cache_key="v77_pass")
        fsc.render_bottom_flush_cutout(bg, frame, alpha, clean_wall=True, wall_cache_key="v77_pass")
        n = len(seen)
        fsc.render_bottom_flush_cutout(bg, frame, alpha)
        assert len(seen) == n, "clean_wall defaults to False"
    finally:
        fsc.clean_aroll_preserve_hair_crown = real
    assert len(seen) == 3 and all(k == "v77_pass" and ok for k, ok, _ in seen), seen
    print("[PASS] 09 A1 / A2 / B pass the alpha through to the wall cleaner")


# ---------------------------------------------------------------------------------------------- (3) compile_and_verify
def test_10_audio_profile_studio_14_accepted_and_lufs_shift() -> None:
    r = subprocess.run([sys.executable, str(TOOLS_DIR / "compile_and_verify.py"), "--help"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    assert "studio_14" in r.stdout, "--audio-profile help must list studio_14"
    # argparse really accepts it: parse only (no spec needed with --self-test is too heavy), use the parser helper
    import compile_and_verify as cv

    profiles = tuple(cv._load_profile_overrides()["audio_profiles"])
    assert "studio_14" in profiles and "platform" in profiles
    old_argv = sys.argv
    try:
        sys.argv = ["compile_and_verify.py", "--self-test", "--audio-profile", "studio_14"]
        args = cv.parse_args() if hasattr(cv, "parse_args") else None
    finally:
        sys.argv = old_argv
    if args is not None:
        assert args.audio_profile == "studio_14" and abs(args.target_lufs - (-14.0)) < 1e-9
    assert cv._lufs_target_shift("studio_14", -14.0) == 2.0
    assert cv._lufs_target_shift("platform", -16.0) == 0.0
    assert cv._lufs_target_shift("platform", -14.5) == 1.5
    assert cv._lufs_target_shift("tiktok_loud", -12.0) == 0.0
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    assert "{platform,tiktok_loud}" not in src, "stale audio-profile mention left in compile_and_verify.py"
    print("[PASS] 10 --audio-profile studio_14 accepted; lufs_target_shift for every non-tiktok profile")


def _manifest_events(gain_db: float) -> list[dict]:
    """fcproj_sfx_manifest on a tiny project with one SFX clip carrying `gain_db`."""
    spec = importlib.util.spec_from_file_location("pfd_ovs_manifest", OVS_MANIFEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ticks = mod.TICKS
    items = {"1": {"kind": {"Media": {"media": {"File": {"path": "/x/a.wav"}}}}}}
    clip = {"item": 1, "start": ticks, "duration": ticks, "source_in": 0, "gain_db": gain_db}
    seq = {"audio_tracks": [{"name": "A1 voice", "items": []}, {"name": "A2 SFX", "items": [clip]}],
           "video_tracks": [{"items": [{"start": 0, "duration": 2 * ticks}]}]}
    items["9"] = {"kind": {"Sequence": seq}}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "p.fcproj"
        p.write_text(json.dumps({"project": {"items": items}}), encoding="utf-8")
        events, _ = mod.fcproj_sfx_manifest(p)
    return events


def test_11_sfx_source_clipping_uses_post_gain_peak() -> None:
    ev = _manifest_events(-9.5)
    assert ev and ev[0]["gain_db"] == -9.5, ev
    assert _manifest_events(0.0)[0]["gain_db"] == 0.0
    spec = importlib.util.spec_from_file_location("pfd_audit_core", OVS_AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as td:
        import wave

        wav = Path(td) / "hot.wav"
        sig = (np.clip(np.sin(np.linspace(0, 60, 24000)) * 1.0, -1, 1) * 32767).astype(np.int16)
        sig[100] = -32768  # full-scale sample: peak exactly 1.0 (0 dBFS)
        with wave.open(str(wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(sig.tobytes())
        base = [{"path": str(wav), "start": 0.0, "duration": 0.5}]
        rep0 = mod.audit(base, Path(td), 2.0, do_measure=True)
        assert rep0["files"][0]["clipping"] is True, "an unattenuated 0 dBFS file clips"
        rep_g = mod.audit([{**base[0], "gain_db": -9.5}], Path(td), 2.0, do_measure=True)
        assert rep_g["files"][0]["clipping"] is False, "-9.5 dB of clip gain removes the clipping"
        assert rep_g["files"][0]["peak_dbfs_after_gain"] < -9.0
        rep_p = mod.audit([{**base[0], "gain_db": 3.0}], Path(td), 2.0, do_measure=True)
        assert rep_p["files"][0]["clipping"] is True
    src = (TOOLS_DIR / "compile_and_verify.py").read_text(encoding="utf-8")
    assert "post-gain" in src, "Fix text must mention the post-gain peak"
    print("[PASS] 11 SFX_SOURCE_CLIPPING: gain_db in the manifest, clipping = peak * 10**(gain_db/20) >= 1")


# ---------------------------------------------------------------------------------------------- (4) fc_export / craftctl
class _FakeCraft:
    """Stands in for craftctl.Craft: export.quick returns at once, jobs.list reports a running job, then finished."""

    scripts: list = []
    seen: list = []

    def __init__(self, app, workdir, *a, **k):
        self.calls = []
        type(self).seen = self.calls
        self.polls = 0
        self.out: Path | None = None

    def __enter__(self):
        return self

    def __exit__(self, *e):
        self.calls.append(("close", None))

    def cmd(self, command, params=None):
        self.calls.append((command, params))
        if command == "file.open":
            return {"path": params["path"]}
        if command == "export.quick":
            assert params["wait"] is False, "export must use wait:False"
            self.out = Path(params["path"])
            return {"job": 7, "path": params["path"]}
        if command == "jobs.list":
            step = type(self).scripts[min(self.polls, len(type(self).scripts) - 1)]
            self.polls += 1
            jobs = step(self) if callable(step) else step
            return jobs
        raise AssertionError(command)


def _load_fc_export():
    sys.path.insert(0, str(OVS_TOOLS))
    spec = importlib.util.spec_from_file_location("pfd_ovs_fc_export_v77", OVS_TOOLS / "fc_export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_12_fc_export_polls_until_finished_true() -> None:
    mod = _load_fc_export()
    mod.Craft = _FakeCraft
    stale = {"id": 0, "finished": True, "result": {"bytes": 1, "path": "/old.mp4"}}

    def finish(fc):
        fc.out.write_bytes(b"x" * 321)
        return [stale, {"id": 7, "finished": True, "result": {"bytes": 321, "frames": 9, "path": str(fc.out)}}]

    running = [stale, {"id": 7, "finished": False, "progress": 0.4, "result": None}]
    _FakeCraft.scripts = [[], [stale], running, running, finish]  # empty list first: NOT a sign of completion
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "p.fcproj"
        proj.write_text("{}", encoding="utf-8")
        out = Path(td) / "o.mp4"
        res = mod.export(proj, out, poll_s=0.01, timeout=5.0)
        assert res["bytes"] == 321 and Path(res["out"]).resolve() == out.resolve(), res
        assert res["result"]["frames"] == 9
        jl = [c for c in _FakeCraft.seen if c[0] == "jobs.list"]
        assert len(jl) == 5, f"must keep polling through empty / stale / running lists: {len(jl)}"
        order = [c[0] for c in _FakeCraft.seen]
        assert order.index("close") > max(i for i, c in enumerate(order) if c == "jobs.list"), "left the Craft block before the job finished"
    print("[PASS] 12 fc_export: wait:False + jobs.list polling by job id, empty list is not 'done'")


def test_13_fc_export_maps_job_error_and_timeout_to_crafterror() -> None:
    mod = _load_fc_export()
    mod.Craft = _FakeCraft
    CraftError = mod.CraftError
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "p.fcproj"
        proj.write_text("{}", encoding="utf-8")
        _FakeCraft.scripts = [[{"id": 7, "finished": True, "error": "encoder crashed", "result": None}]]
        try:
            mod.export(proj, Path(td) / "e.mp4", poll_s=0.01, timeout=2.0)
        except CraftError as exc:
            assert "encoder crashed" in str(exc)
        else:
            raise AssertionError("job error must raise CraftError")
        _FakeCraft.scripts = [[{"id": 7, "finished": False, "result": None}]]
        try:
            mod.export(proj, Path(td) / "t.mp4", poll_s=0.01, timeout=0.1)
        except CraftError as exc:
            assert "timeout" in str(exc).lower()
        else:
            raise AssertionError("a job that never finishes must time out")
    spec = importlib.util.spec_from_file_location("pfd_fc_export_wrap", TOOLS_DIR / "fc_export.py")
    wrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrap)
    r = subprocess.run([sys.executable, str(TOOLS_DIR / "fc_export.py"), "--help"], capture_output=True, text=True, timeout=60)
    assert "--timeout" in r.stdout, r.stdout
    print("[PASS] 13 fc_export: job error and timeout -> CraftError; --timeout exposed")


def test_14_ensure_display_probes_instead_of_trusting_the_socket_file() -> None:
    sys.path.insert(0, str(OVS_TOOLS))
    spec = importlib.util.spec_from_file_location("pfd_craftctl_v77", OVS_TOOLS / "craftctl.py")
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        cc.X11_SOCKET_DIR = Path(td)
        stale = Path(td) / "X93"
        s = socket.socket(socket.AF_UNIX)
        s.bind(str(stale))
        s.close()  # leaves a socket file nobody listens on
        assert stale.exists() and cc.display_alive(":93") is False, "stale socket file must not count as a live display"
        live = Path(td) / "X94"
        srv = socket.socket(socket.AF_UNIX)
        srv.bind(str(live))
        srv.listen(1)
        try:
            assert cc.display_alive(":94") is True
        finally:
            srv.close()
        assert cc.display_alive(":95") is False
    print("[PASS] 14 craftctl.display_alive: stale /tmp/.X11-unix/X93 is not trusted")


# ---------------------------------------------------------------------------------------------- (5) web_plate_builder
def test_15_kt01_swash_span_and_aaron_font_face() -> None:
    import web_plate_builder as wpb

    base = dict(main_text="và mình là", theme="light", jewel_accent="#F5C451", hero_tone="white")
    for accent in ("Thành", "Sản phẩm & Logo gốc"):
        html = wpb._build_kt01_kiss_editorial_2line({**base, "accent_text": accent}, 1080, 560)
        assert "swash-hybrid-init" in html, f"default must swash the accent line: {accent}"
        m = re.search(r'id="kt01Line2">(.*?)</div>', html, re.S)
        assert m and 'class="swash-hybrid-rest"' in m.group(1), m.group(1)[:200] if m else "no line2"
        assert "SVN-Aaron Script" in html
        off = wpb._build_kt01_kiss_editorial_2line({**base, "accent_text": accent, "accent_swash": False}, 1080, 560)
        m2 = re.search(r'id="kt01Line2">(.*?)</div>', off, re.S)
        assert m2 and "swash-hybrid-init" not in m2.group(1), "accent_swash=False keeps the plain line"
    if wpb.find_font_file("SVN-Aaron Script.otf") is not None:
        assert re.search(r"@font-face \{ font-family: 'SVN-Aaron Script'; src: url\('file://[^']*SVN-Aaron", html), "Aaron @font-face missing"
        assert "svn-aaron script" in wpb._registered_font_families()
    else:
        print("[SKIP] SVN-Aaron Script.otf not installed on this machine")
    print("[PASS] 15 kt01 accent swash span + SVN-Aaron Script @font-face")


def test_16_font_root_is_a_search_list() -> None:
    import os
    import web_plate_builder as wpb

    assert isinstance(wpb.FONT_ROOTS_TNEDIT, tuple) and len(wpb.FONT_ROOTS_TNEDIT) >= 2
    names = [str(p) for p in wpb.FONT_ROOTS_TNEDIT]
    assert any(n.endswith(".local/share/fonts/tnedit") for n in names)
    assert any(n.endswith("TNEDIT_DViet/Lien_ket_thu_vien_co_san") for n in names)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "Fake-Font.otf").write_bytes(b"x")
        os.environ["PFD_FONT_DIR"] = td
        try:
            assert wpb.find_font_file("Fake-Font.otf") == Path(td) / "Fake-Font.otf"
        finally:
            del os.environ["PFD_FONT_DIR"]
    assert wpb.find_font_file("definitely-not-a-font.ttf") is None
    print("[PASS] 16 FONT_ROOT_TNEDIT is a search list (+ PFD_FONT_DIR)")


def _node_pulse(js: str, scale: float | None, u: float) -> float:
    prelude = "const window = " + ("{}" if scale is None else json.dumps({"__GLOW_SCALE": scale})) + ";"
    code = f"{prelude}\n{js}\nconsole.log(halationPulse({u}));"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-400:]
    return float(r.stdout.strip())


def test_17_glow_scale_lowers_text_shadow_blur_and_default_is_unchanged() -> None:
    import web_plate_builder as wpb

    assert wpb.GLOW_SCALE == 1.0
    assert "window.__GLOW_SCALE ?? 1" in wpb.studio_common_js(), "default must read window.__GLOW_SCALE ?? 1"
    html1 = wpb._build_kt01_kiss_editorial_2line(dict(main_text="AI", theme="dark", jewel_accent="#F5C451"), 1080, 560)
    doc = wpb.wrap_studio_document(width=100, height=100, extra_css="", body_html="", frame_js="")
    assert "window.__GLOW_SCALE ?? 1" in doc and "halationPulse" in doc and "__GLOW_SCALE_DEFAULT__" not in doc
    assert "0 0 ${(14 * hPulse).toFixed(1)}px" in html1, "text-shadow blur formula must stay"
    if shutil.which("node"):
        js = wpb.studio_common_js()
        full = _node_pulse(js, None, 0.1)
        half = _node_pulse(js, 0.5, 0.1)
        assert abs(full - 1.45 * (0.1 / (4 / 32)) * 1.0) < 1e-6, full
        assert abs(half - 0.5 * full) < 1e-9, (full, half)
        assert 14 * half < 14 * full and 34 * half < 34 * full
    old = wpb.GLOW_SCALE
    try:
        wpb.GLOW_SCALE = 0.5
        assert "window.__GLOW_SCALE ?? 0.5" in wpb.studio_common_js()
    finally:
        wpb.GLOW_SCALE = old
    print("[PASS] 17 glow scale token: default 1.0 unchanged, 0.5 halves halationPulse (text-shadow blur)")


def test_18_kt12_echo_opacity_prop() -> None:
    import web_plate_builder as wpb

    props = dict(mode="directional_echo", main_text="PROMPT", jewel_accent="#FACC15")
    d = wpb._build_kt12_whisper_or_directional_echo(props, 1080, 560)
    assert "(0.42 * pEcho)" in d and "(0.18 * pEcho)" in d, "default echo opacities must stay 0.42 / 0.18"
    t = wpb._build_kt12_whisper_or_directional_echo({**props, "echo_opacity": 0.2}, 1080, 560)
    assert "(0.2 * pEcho)" in t and "(0.42 * pEcho)" not in t
    assert re.search(r"\(0\.0857\d* \* pEcho\)", t), "second ghost scales with the first (0.18 / 0.42)"
    print("[PASS] 18 kt12 echo_opacity prop (default unchanged)")


def main() -> int:
    if "--print-golden" in sys.argv:
        print(json.dumps(_legacy_hashes(), indent=1))
        return 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print("TẤT CẢ ĐẠT (skill code S1 v7.7.0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
