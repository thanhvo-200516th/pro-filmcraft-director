#!/usr/bin/env python3
"""
Tests for the v7.9.2 hook automation of look_s_render.py (synthetic media only, no Chrome).

  01 hook B-roll motion: a static full-screen B-roll in the hook gets a Ken Burns push + pan (+ glint) through the real `_draw`
     path; the masked frame diff reaches >= 2.0 (motion_gate.check_motion) while the untouched static shot stays below it; the push
     respects the +25 % full-screen B-roll cap, keeps the product centre in frame and is deterministic; a moving source, a short
     scene and an explicit `cam` get no auto motion
  02 `fast_studio_compositor.product_bbox_from_frame`: a bright bottle-shaped blob is boxed by the u2netp saliency matte and by the
     luminance / edge fallback; a blank frame has no product in the fallback
  03 `place_product_safe`: a hook overlay whose text box overlaps the product moves to the nearest clear band (no overlap with the
     product or the PiP, inside the 50..1030 x 140..1760 safe zone); other overlays are untouched, the input is not mutated, an
     impossible case is reported and left in place
  04 CLI: --no-hook-motion / --no-product-safe-text switch both off; the dry-run summary carries `product_bbox` and the moved
     overlays; a --draft render of a static hook passes the motion gate with the default and fails it with --no-hook-motion
  05 stage fallback: a full-height product leaves the hook text unresolved (--no-stage-fallback); by default the scene falls back to
     the product stage (s 0.72), the product box is re-detected on the staged frame and the text clears it; the render passes the gate
  06 a staged hook predicted under the 2.0 floor gets snap-punch zoom steps (>= 4 %, one per 0.6-1.0 s, push * punch <= +25 %):
     prediction and render reach >= 2.0, the flash gate holds, the product stays in frame and the text clear

Plain asserts with a `__main__` runner: `python3 tests/test_hook_auto_v792.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = SKILL_ROOT / "scripts" / "tools"
for _p in (str(SKILL_ROOT / "scripts"), str(TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable
LSR = TOOLS_DIR / "look_s_render.py"
W, H = 1080, 1920
BOTTLE = (380, 640, 701, 1501)            # x0, y0, x1, y1 (exclusive) of the synthetic bottle: cap + neck + body
PIP_MASK = (700 / W, 1446 / H, 1012 / W, 1836 / H)
SAFE = (50, 140, 1030, 1760)


def _bottle_frame(blank: bool = False) -> np.ndarray:
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    f = np.zeros((H, W, 3), np.float32) + (28 + 20 * yy)
    rng = np.random.default_rng(7)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 3)
    f += (grain * (10.0 / grain.std()))[:, :, None]                       # mottled studio backdrop (texture a camera move shows)
    f = np.clip(f, 0, 255).astype(np.uint8)
    if not blank:
        cv2.rectangle(f, (380, 900), (700, 1500), (60, 150, 230), -1)     # body
        cv2.rectangle(f, (470, 760), (610, 900), (60, 150, 230), -1)      # neck
        cv2.rectangle(f, (450, 640), (630, 760), (200, 200, 210), -1)     # cap
        for _ in range(120):                                              # droplets on the glass
            cv2.circle(f, (int(rng.integers(390, 690)), int(rng.integers(910, 1490))), int(rng.integers(4, 12)), (235, 245, 255), -1)
    return f


def _iou(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / float((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def _overlap(a, b) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, timeout=180, capture_output=True)


# ---------------------------------------------------------------------------------------------- (1) hook motion
def test_01_static_hook_broll_gets_motion() -> None:
    import look_s_render as lsr
    import motion_gate as mg

    frame = _bottle_frame()
    aroll = np.full((H, W, 3), 90, np.uint8)
    cv2.circle(aroll, (W // 2, 700), 260, (150, 170, 200), -1)
    sc = {"id": "H1", "mode": "H", "t0": 0.0, "t1": 3.48, "popout": False, "pip": "br"}
    hm = lsr.hook_motion_for(sc, 0.0, BOTTLE, (W, H))
    assert hm is not None, "a static hook B-roll must get auto motion"
    assert hm == lsr.hook_motion_for(sc, 0.0, BOTTLE, (W, H)), "hook motion must be deterministic"
    assert 0.0 < hm["zmax"] <= 0.25 + 1e-9, hm
    dur = sc["t1"] - sc["t0"]
    push_rate, pan_rate = 100 * hm["zmax"] / dur, 100 * abs(hm["pan_px"]) / (W * dur)
    assert push_rate >= 10 or pan_rate >= 4 or hm["glint"][0] > 0, (push_rate, pan_rate, hm)   # check_pacing bg_static_hold remedies
    m_end = __import__("fast_studio_compositor").hook_push_affine(1.0, hm)
    assert m_end[0, 0] <= 1.25 + 1e-6 and abs(m_end[0, 0] - m_end[1, 1]) < 1e-9, m_end
    box_end = __import__("fast_studio_compositor").hook_push_box(BOTTLE, 1.0, hm)
    assert 0 <= box_end[0] and box_end[2] <= W and 0 <= box_end[1] and box_end[3] <= H, ("product left the frame", box_end)

    ctx = {"jewel": (245, 196, 81), "bg": np.zeros((H, W, 3), np.uint8)}
    n = int(round(dur * 30))

    def frames(scene):
        for i in range(n):
            yield lsr._draw(scene, i / 30.0, ctx, aroll, None, frame)

    on = mg.check_motion(frames({**sc, "hook_motion": hm}), mask_rects=[PIP_MASK], t0=0.0, t1=3.4, fps=30)
    off = mg.check_motion(frames(sc), mask_rects=[PIP_MASK], t0=0.0, t1=3.4, fps=30)
    assert on["ok"] and on["mean"] >= 2.0, on
    assert off["mean"] < 2.0, off
    a = lsr._draw({**sc, "hook_motion": hm}, 1.3, ctx, aroll, None, frame)
    b = lsr._draw({**sc, "hook_motion": hm}, 1.3, ctx, aroll, None, frame)
    assert np.array_equal(a, b), "render must be deterministic"

    assert lsr.hook_motion_for(sc, 3.5, BOTTLE, (W, H)) is None, "a moving source needs no auto motion"
    assert lsr.hook_motion_for({**sc, "t1": 0.5}, 0.0, BOTTLE, (W, H)) is None, "a hold <= 0.8 s needs no micro-move"
    assert lsr.hook_motion_for({**sc, "cam": [1.0, 1.04]}, 0.0, BOTTLE, (W, H)) is None, "an explicit cam is the editor's decision"
    wide = lsr.hook_motion_for(sc, 0.0, BOTTLE, (3414, 1920))
    assert wide is not None and wide["crop_off"] == [1167, 0], wide
    print(f"[PASS] 01 static hook B-roll: masked diff {off['mean']} -> {on['mean']} (push {push_rate:.1f} %/s, pan {pan_rate:.1f} %/s, "
          f"zmax {hm['zmax']}), cap and product kept, deterministic, no auto motion when not needed")


def test_01b_measure_static_source() -> None:
    import look_s_render as lsr

    with tempfile.TemporaryDirectory(prefix="pfd_hook_") as td:
        d = Path(td)
        png = d / "bottle.png"
        cv2.imwrite(str(png), cv2.resize(_bottle_frame(), (640, 1138)))
        clip = d / "static.mp4"
        _ff("-loop", "1", "-i", str(png), "-t", "2.0", "-r", "30", "-vf", "scale=640:1138", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(clip))
        res = lsr.measure_hook_source(str(clip), 0.0, 2.0)
        assert res["mean_diff"] < 1.0, res
        bb = res["product"]["bbox"]
        assert bb is not None and _iou(bb, BOTTLE) >= 0.7, res
    print(f"[PASS] 01b measure_hook_source: static clip mean diff {res['mean_diff']}, product {res['product']['method']} {bb}")


# ---------------------------------------------------------------------------------------------- (2) product bbox
def test_02_product_bbox_from_frame() -> None:
    import fast_studio_compositor as fsc

    f = _bottle_frame()
    model = fsc.product_bbox_from_frame(f)
    assert model["bbox"] is not None and model["method"] in ("u2netp", "luma_edge"), model
    assert _iou(model["bbox"], BOTTLE) >= 0.8, model
    fb = fsc.product_bbox_from_frame(f, use_model=False)
    assert fb["method"] == "luma_edge" and _iou(fb["bbox"], BOTTLE) >= 0.8, fb
    small = fsc.product_bbox_from_frame(cv2.resize(f, (270, 480), interpolation=cv2.INTER_AREA), use_model=False)
    assert _iou([v * 4 for v in small["bbox"]], BOTTLE) >= 0.75, small
    blank = fsc.product_bbox_from_frame(_bottle_frame(blank=True), use_model=False)
    assert blank["bbox"] is None, blank
    print(f"[PASS] 02 product_bbox_from_frame: {model['method']} {model['bbox']}, fallback {fb['bbox']}, blank -> None")


# ---------------------------------------------------------------------------------------------- (3) overlay placement
def test_03_place_product_safe() -> None:
    import look_s_render as lsr

    ink = (406, 108, 673, 321)                 # kt plate glyph box (plate px)
    base = {"src": "a.mov", "at": 0.1, "dur": 0.7, "cx": 540.0, "orig_w": 1080, "orig_h": 440, "scale": 1.0}
    ov_hit, ov_clear, ov_late = {**base, "cy": 900.0}, {**base, "cy": 300.0}, {**base, "at": 5.0, "cy": 900.0}
    prod = (300, 500, 780, 1500)
    pip = lsr.PIP_RECTS["br"]
    hooks = [{"id": "H", "t0": 0.0, "t1": 3.48, "product_bbox": prod, "obstacles": [prod, pip]}]
    src = [ov_hit, ov_clear, ov_late]
    snap = json.dumps(src, sort_keys=True)
    new, moved, unresolved = lsr.place_product_safe(src, hooks, ink_boxes=[ink, ink, ink])
    assert json.dumps(src, sort_keys=True) == snap, "input overlays must not be mutated"
    assert len(moved) == 1 and moved[0]["index"] == 0 and not unresolved, (moved, unresolved)
    assert new[1] == ov_clear and new[2] == ov_late, new
    box = lsr._overlay_box(new[0], ink)
    assert _overlap(box, prod) == 0 and _overlap(box, pip) == 0, (box, prod)
    assert SAFE[0] <= box[0] and box[2] <= SAFE[2] and SAFE[1] <= box[1] and box[3] <= SAFE[3], box
    assert new[0]["cy"] < 900 and box[3] <= prod[1], ("nearest clear band is above the product", box)
    assert moved[0]["from_cy"] == 900.0 and moved[0]["to_cy"] == new[0]["cy"], moved

    full = (256, 99, 822, 1653)                # the e2e bottle: no band of 213 px above or below it inside the safe zone
    hooks2 = [{"id": "H", "t0": 0.0, "t1": 3.48, "product_bbox": full, "obstacles": [full, pip]}]
    new2, moved2, unresolved2 = lsr.place_product_safe([ov_clear], hooks2, ink_boxes=[ink])
    assert not moved2 and len(unresolved2) == 1 and unresolved2[0]["overlap_px2"] > 0, (moved2, unresolved2)
    assert new2[0] == ov_clear, "an overlay that cannot be cleared stays where it is"
    print(f"[PASS] 03 place_product_safe: cy 900 -> {new[0]['cy']} (box {box}), clear / late overlays untouched, impossible case reported")


# ---------------------------------------------------------------------------------------------- (4) CLI + render
def _fixture(d: Path) -> list[str]:
    png = d / "bottle.png"
    cv2.imwrite(str(png), _bottle_frame())
    broll = d / "broll"
    broll.mkdir()
    _ff("-loop", "1", "-i", str(png), "-t", "2.6", "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(broll / "b.mp4"))
    face = np.full((H, W, 3), 90, np.uint8)
    cv2.circle(face, (W // 2, 700), 260, (150, 170, 200), -1)
    cv2.imwrite(str(d / "face.png"), face)
    _ff("-loop", "1", "-i", str(d / "face.png"), "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=3.0",
        "-t", "3.0", "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        str(d / "aroll.mp4"))
    plate = np.zeros((440, 1080, 4), np.uint8)
    plate[108:322, 406:674] = (255, 255, 255, 255)
    cv2.imwrite(str(d / "plate.png"), plate)
    _ff("-loop", "1", "-i", str(d / "plate.png"), "-t", "0.5", "-r", "30", "-c:v", "qtrle", "-pix_fmt", "argb", str(d / "plate.mov"))
    (d / "overlays.json").write_text(json.dumps([{"src": "plate.mov", "at": 0.1, "dur": 0.5, "cx": 540.0, "cy": 1000.0,
                                                   "orig_w": 1080, "orig_h": 440, "scale": 1.0}]), encoding="utf-8")
    scs = [{"id": "H1", "start": 0.0, "end": 2.4, "mode": "H", "kind": "hook", "jewel": "#F5C451", "broll": "b.mp4", "text": ""},
           {"id": "C1", "start": 2.4, "end": 3.0, "mode": "A1", "kind": "text", "jewel": "#F5C451", "text": ""}]
    (d / "scenes.json").write_text(json.dumps({"look": "S", "duration": 3.0, "scenes": scs}), encoding="utf-8")
    words = [["một", 0.0, 0.5], ["hai", 0.6, 1.2], ["ba", 1.3, 2.0], ["bốn", 2.1, 2.9]]
    (d / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return ["--scenes", str(d / "scenes.json"), "--words", str(d / "words.json"), "--aroll", str(d / "aroll.mp4"),
            "--broll-dir", str(broll), "--draft", "--no-voice-guard", "--jobs", "1"]


def _run(*args: str) -> tuple[int, dict, str]:
    r = subprocess.run([PY, str(LSR), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError:
        doc = {}
    return r.returncode, doc, r.stderr


def test_04_cli_flags_and_render() -> None:
    import look_s_render as lsr
    import motion_gate as mg

    ns = lsr.build_parser().parse_args(["--scenes", "s", "--words", "w", "--aroll", "a", "--work", "k", "--out", "o",
                                        "--no-hook-motion", "--no-product-safe-text"])
    assert ns.no_hook_motion and ns.no_product_safe_text
    ns = lsr.build_parser().parse_args(["--scenes", "s", "--words", "w", "--aroll", "a", "--work", "k", "--out", "o"])
    assert not ns.no_hook_motion and not ns.no_product_safe_text
    r = subprocess.run([PY, str(LSR), "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "--no-hook-motion" in r.stdout and "--no-product-safe-text" in r.stdout, r.stdout[-400:]

    with tempfile.TemporaryDirectory(prefix="pfd_hook_cli_") as td:
        d = Path(td)
        base = _fixture(d)
        rc, doc, err = _run(*base, "--work", str(d / "w1"), "--out", str(d / "m1.mp4"), "--overlays", str(d / "overlays.json"),
                            "--dry-run")
        assert rc == 0 and doc.get("ok"), (rc, doc, err[-800:])
        ha = doc["hook_auto"]
        sc0 = ha["scenes"][0]
        assert sc0["id"] == "H1" and sc0["static"] and sc0["motion"] and sc0["motion"]["zmax"] <= 0.25 + 1e-9, sc0
        assert doc["product_bbox"] and _iou(doc["product_bbox"], BOTTLE) > 0.3, doc["product_bbox"]
        assert len(ha["moved_overlays"]) == 1 and ha["moved_overlays"][0]["to_cy"] < 1000, ha
        box = ha["moved_overlays"][0]["box_after"]
        assert _overlap(box, doc["product_bbox"]) == 0 and SAFE[1] <= box[1] and box[3] <= SAFE[3], (box, doc["product_bbox"])

        rc, doc2, err = _run(*base, "--work", str(d / "w2"), "--out", str(d / "m2.mp4"), "--overlays", str(d / "overlays.json"),
                             "--dry-run", "--no-hook-motion", "--no-product-safe-text")
        assert rc == 0 and doc2.get("ok"), (rc, doc2, err[-800:])
        assert doc2["hook_auto"]["scenes"] == [] and doc2["hook_auto"]["moved_overlays"] == [], doc2["hook_auto"]
        assert doc2["scenes"][0]["segment"] != doc["scenes"][0]["segment"], "the motion must be part of the segment cache key"

        mask = [PIP_MASK]
        rc, doc3, err = _run(*base, "--work", str(d / "w3"), "--out", str(d / "m3.mp4"))
        assert rc == 0 and doc3.get("ok"), (rc, json.dumps(doc3)[:1200], err[-1200:])
        on = mg.check_motion(str(d / "m3.mp4"), mask_rects=mask, t0=0.0, t1=2.3, fps=30)
        rc, doc4, err = _run(*base, "--work", str(d / "w4"), "--out", str(d / "m4.mp4"), "--no-hook-motion")
        assert rc == 0 and doc4.get("ok"), (rc, json.dumps(doc4)[:1200], err[-1200:])
        off = mg.check_motion(str(d / "m4.mp4"), mask_rects=mask, t0=0.0, t1=2.3, fps=30)
        assert on["ok"] and on["mean"] >= 2.0, on
        assert not off["ok"] and off["mean"] < 2.0, off
    print(f"[PASS] 04 CLI: flags parse and switch both off, dry-run reports product_bbox + moved overlay, draft render masked diff "
          f"{off['mean']} (--no-hook-motion) -> {on['mean']} (default)")


# ---------------------------------------------------------------------------------------------- (5) stage fallback
def _full_height_clip(d: Path, grain_std: float = 10.0, drops: int = 90) -> Path:
    """Static 16:9 product shot whose bottle spans the whole cover-cropped 9:16 frame (the e2e serum case)."""
    f = np.zeros((720, 1280, 3), np.float32) + 30
    rng = np.random.default_rng(11)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (720, 1280)).astype(np.float32), (0, 0), 2)
    f = np.clip(f + (grain * (grain_std / grain.std()))[:, :, None], 0, 255).astype(np.uint8)
    cv2.rectangle(f, (560, 260), (720, 700), (60, 150, 230), -1)          # body
    cv2.rectangle(f, (605, 120), (675, 260), (60, 150, 230), -1)          # neck
    cv2.rectangle(f, (595, 25), (685, 120), (200, 200, 210), -1)          # cap
    for _ in range(drops):
        cv2.circle(f, (int(rng.integers(565, 715)), int(rng.integers(265, 695))), int(rng.integers(2, 6)), (235, 245, 255), -1)
    png = d / "full.png"
    cv2.imwrite(str(png), f)
    clip = d / "broll_full" / "full.mp4"
    clip.parent.mkdir()
    _ff("-loop", "1", "-i", str(png), "-t", "2.6", "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(clip))
    return clip


def test_05_stage_fallback() -> None:
    import motion_gate as mg

    r = subprocess.run([PY, str(LSR), "--help"], capture_output=True, text=True, timeout=60)
    assert "--no-stage-fallback" in r.stdout, r.stdout[-400:]
    with tempfile.TemporaryDirectory(prefix="pfd_hook_stage_") as td:
        d = Path(td)
        base = _fixture(d)
        clip = _full_height_clip(d)
        base = [clip.parent.as_posix() if a.endswith("/broll") else a for a in base]
        scs = json.loads((d / "scenes.json").read_text(encoding="utf-8"))
        scs["scenes"][0]["broll"] = "full.mp4"
        (d / "scenes.json").write_text(json.dumps(scs), encoding="utf-8")
        (d / "overlays.json").write_text(json.dumps([{"src": "plate.mov", "at": 0.1, "dur": 0.5, "cx": 540.0, "cy": 354.0,
                                                       "orig_w": 1080, "orig_h": 440, "scale": 1.0}]), encoding="utf-8")
        ovs = ["--overlays", str(d / "overlays.json")]

        rc, off, err = _run(*base, *ovs, "--work", str(d / "w0"), "--out", str(d / "m0.mp4"), "--dry-run", "--no-stage-fallback")
        assert rc == 0 and off.get("ok"), (rc, off, err[-800:])
        assert len(off["hook_auto"]["unresolved_overlays"]) == 1 and off["hook_auto"]["stage_fallback_scenes"] == [], off["hook_auto"]

        rc, doc, err = _run(*base, *ovs, "--work", str(d / "w1"), "--out", str(d / "m1.mp4"))
        assert rc == 0 and doc.get("ok"), (rc, json.dumps(doc)[:1500], err[-1500:])
        ha = doc["hook_auto"]
        assert ha["stage_fallback_scenes"] == ["H1"] and ha["unresolved_overlays"] == [], ha
        row = ha["scenes"][0]
        assert row["stage"] == 0.72 and row["product_bbox"][1] >= 560, row          # cap top of the stage ~ 613 (0.32 H)
        assert row["motion"] and row["motion"]["zmax"] <= 0.25 + 1e-9, row
        assert 0 <= row["product_bbox"][0] and row["product_bbox"][2] <= W, ("product left the frame", row)
        ink_box = (406, 354 - 220 + 108, 674, 354 - 220 + 322)
        box = next((m["box_after"] for m in ha["moved_overlays"]), ink_box)
        assert _overlap(box, row["product_bbox"]) == 0, (box, row["product_bbox"])
        assert off["scenes"][0]["segment"] != doc["scenes"][0]["segment"], "the stage must be part of the segment cache key"
        gate = mg.check_motion(str(d / "m1.mp4"), mask_rects=[PIP_MASK], t0=0.0, t1=2.3, fps=30)
        assert gate["ok"] and gate["mean"] >= 2.0, gate
    print(f"[PASS] 05 stage fallback: full-height product -> unresolved without it; with it the scene is staged (product top "
          f"{row['product_bbox'][1]} px), 0 px overlap, masked diff {gate['mean']}")


# ---------------------------------------------------------------------------------------------- (6) zoom steps (snap punches)
def test_06_staged_hook_below_floor_gets_punches() -> None:
    import motion_gate as mg

    with tempfile.TemporaryDirectory(prefix="pfd_hook_punch_") as td:
        d = Path(td)
        base = _fixture(d)
        clip = _full_height_clip(d, grain_std=5.0, drops=30)        # a calmer shot: the staged push alone stays under 2.0
        base = [clip.parent.as_posix() if a.endswith("/broll") else a for a in base]
        scs = json.loads((d / "scenes.json").read_text(encoding="utf-8"))
        scs["scenes"][0]["broll"] = "full.mp4"
        (d / "scenes.json").write_text(json.dumps(scs), encoding="utf-8")
        (d / "overlays.json").write_text(json.dumps([{"src": "plate.mov", "at": 0.1, "dur": 0.5, "cx": 540.0, "cy": 354.0,
                                                       "orig_w": 1080, "orig_h": 440, "scale": 1.0}]), encoding="utf-8")
        ovs = ["--overlays", str(d / "overlays.json")]

        rc, doc, err = _run(*base, *ovs, "--work", str(d / "w1"), "--out", str(d / "m1.mp4"))
        assert rc == 0 and doc.get("ok"), (rc, json.dumps(doc)[:1500], err[-1500:])
        row = doc["hook_auto"]["scenes"][0]
        m = row["motion"]
        assert row["stage"] == 0.72 and m and m.get("punches"), row
        before, after = m["predicted_mean_diff"]
        assert before < 2.0 <= after, m["predicted_mean_diff"]
        assert m["punch_amp"] >= 0.04 - 1e-9, m                                       # each step is a bg reset (zoom step >= 4 %)
        assert (1 + m["zmax"]) * (1 + m["punch_amp"]) <= 1.25 + 1e-6, m              # +25 % full-screen B-roll cap
        ts = m["punches"]
        assert all(0.0 < t < 2.4 for t in ts) and all(0.6 - 1e-9 <= b - a <= 1.0 + 1e-9 for a, b in zip(ts, ts[1:])), ts
        assert 0 <= row["product_bbox"][0] and row["product_bbox"][2] <= W, ("product left the frame", row)
        assert doc["hook_auto"]["unresolved_overlays"] == [], doc["hook_auto"]
        ink_box = (406, 354 - 220 + 108, 674, 354 - 220 + 322)
        box = next((mv["box_after"] for mv in doc["hook_auto"]["moved_overlays"]), ink_box)
        assert _overlap(box, row["product_bbox"]) == 0, (box, row["product_bbox"])
        gate = mg.check_motion(str(d / "m1.mp4"), mask_rects=[PIP_MASK], t0=0.0, t1=2.3, fps=30)
        flash = mg.check_flashes(str(d / "m1.mp4"), fps=60, t0=0.0, t1=2.4)
        assert gate["ok"] and gate["mean"] >= 2.0, gate
        assert flash["ok"], flash

        rc, off, err = _run(*base, *ovs, "--work", str(d / "w2"), "--out", str(d / "m2.mp4"), "--dry-run", "--no-hook-motion")
        assert rc == 0 and off["hook_auto"]["scenes"][0]["motion"] is None, off["hook_auto"]
    print(f"[PASS] 06 staged hook under the floor: predicted {before} -> {after} with {len(ts)} zoom steps at {ts} "
          f"(+{m['punch_amp']:.0%} each, push {m['zmax']:.3f}, total <= 1.25), rendered masked diff {gate['mean']}, flash ok, 0 px overlap")


if __name__ == "__main__":
    test_01_static_hook_broll_gets_motion()
    test_01b_measure_static_source()
    test_02_product_bbox_from_frame()
    test_03_place_product_safe()
    test_04_cli_flags_and_render()
    test_05_stage_fallback()
    test_06_staged_hook_below_floor_gets_punches()
    print("TẤT CẢ ĐẠT (hook auto motion + product-safe text v7.9.2)")
