#!/usr/bin/env python3
"""
Root-cause tests v7.9.3 (synthetic media only, fast): B-roll reuse, transient B-roll artifacts, early low-res / low-fps warning.

  01 `look_s_render.transient_spans`: a short-lived bright sliver on a static textured shot is found (span padded around it);
     steady motion of a bright object, tiny dust specks and a full-frame flash are not transients
  02 `look_s_render.scan_broll_transients` on an encoded clip: the sliver is found at its source time, a clean clip has none
  03 `look_s_render.plan_broll`: the e2e_v791 layout (3 files x 8 s, H / A2 scenes 3.48 / 2.78 / 5.08 / 1.82 / 3.16 / 3.18 s and
     the two dropper-glass transients of 01_serum_orbit) is placed without any source reuse (studio_recipe.check_source_reuse
     is empty) and the hook window is clean; the old round-robin layout reused seconds; greedy = file with most remaining seconds
  04 explicit per-scene `broll` / `broll_ss` overrides are kept
  05 CLI dry-run: unavoidable reuse exits 2 naming --allow-broll-reuse, the flag turns it into a warning; a hook window with a
     transient is shifted to the nearest clean window (`broll_artifacts`), --no-broll-artifact-scan keeps ss 0
  06 probe_and_align: a 320x568 @ 30 fps raw video gets an early Look S source warning (1080p re-export / upscale) in
     audit_warnings and workspace_context.look_s_source; exit 0

Plain asserts with a `__main__` runner: `python3 tests/test_rootcause_broll_v793.py`.
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
FPS = 30


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, timeout=120, capture_output=True)


def _backdrop(w: int, h: int, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    g = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 4)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    return np.clip(40 + 30 * yy + g * (12.0 / g.std()), 0, 255).astype(np.uint8)


def _sliver_frames(w: int, h: int, n: int, hit: range, seed: int = 3) -> list[np.ndarray]:
    """Static textured shot with light sensor noise; frames in `hit` carry a bright thin sliver (a stray glass shard)."""
    base, rng, out = _backdrop(w, h, seed), np.random.default_rng(seed + 1), []
    for i in range(n):
        f = np.clip(base.astype(np.int16) + rng.integers(-3, 4, base.shape), 0, 255).astype(np.uint8)
        if i in hit:
            x, y = int(w * 0.30), int(h * 0.20) + 3 * (i - hit.start)
            cv2.rectangle(f, (x, y), (x + max(3, w // 110), y + h // 6), 235, -1)
        out.append(cv2.cvtColor(f, cv2.COLOR_GRAY2BGR))
    return out


def _write_clip(path: Path, frames: list[np.ndarray]) -> Path:
    h, w = frames[0].shape[:2]
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    assert p.stdin is not None
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close()
    assert p.wait(timeout=120) == 0
    return path


# ---------------------------------------------------------------------------------------------- (1) transient detector
def test_01_transient_spans_synthetic() -> None:
    import look_s_render as lsr
    w, h, n = 480, 270, 90
    spans = lsr.transient_spans(_sliver_frames(w, h, n, range(45, 50)), FPS)
    assert len(spans) == 1, spans
    sp = spans[0]
    assert sp["t0"] <= 45 / FPS and sp["t1"] >= 50 / FPS and sp["t1"] - sp["t0"] < 0.8, sp

    base = _backdrop(w, h)
    moving = []
    for i in range(n):                                          # a bright ball crossing the shot for 3 s: motion, not a transient
        f = base.copy()
        cv2.circle(f, (20 + i * 5, h // 2), 18, 240, -1)
        moving.append(f)
    assert lsr.transient_spans(moving, FPS) == [], lsr.transient_spans(moving, FPS)

    rng, dust = np.random.default_rng(9), []
    for _ in range(n):                                          # 1-2 px dust specks twinkling everywhere
        f = base.copy()
        for _ in range(25):
            x, y = int(rng.integers(0, w - 2)), int(rng.integers(0, h - 2))
            f[y:y + 2, x:x + 2] = 230
        dust.append(f)
    assert lsr.transient_spans(dust, FPS) == [], lsr.transient_spans(dust, FPS)

    flash = [base.copy() if not 40 <= i < 43 else np.full_like(base, 250) for i in range(n)]
    assert lsr.transient_spans(flash, FPS) == [], "a full-frame flash is not a localized transient"
    print("[PASS] 01 transient_spans: sliver found (padded span); moving ball, dust specks and a full-frame flash are not transients")


def test_02_scan_encoded_clip() -> None:
    import look_s_render as lsr
    with tempfile.TemporaryDirectory(prefix="pfd793_") as td:
        d = Path(td)
        dirty = _write_clip(d / "dirty.mp4", _sliver_frames(640, 360, 90, range(30, 35)))
        clean = _write_clip(d / "clean.mp4", _sliver_frames(640, 360, 90, range(0)))
        sp = lsr.scan_broll_transients(str(dirty), lsr.fsc.probe_video(dirty))
        assert len(sp) == 1 and sp[0]["t0"] <= 1.0 and sp[0]["t1"] >= 35 / FPS, sp
        assert lsr.scan_broll_transients(str(clean), lsr.fsc.probe_video(clean)) == []
    print("[PASS] 02 scan_broll_transients: the encoded sliver is found at its source time; a clean clip has none")


# ---------------------------------------------------------------------------------------------- (3) assignment
E2E = [("S01A", 0.0, 3.48), ("S05A", 12.4, 15.18), ("S07", 19.0, 24.08), ("S10", 29.12, 30.94), ("S11", 30.94, 34.1), ("S12B", 36.02, 39.2)]
FILES = ["01_serum_orbit_16x9.mp4", "02_perfume_camera_9x16.mp4", "02_perfume_camera_dark.mp4"]


def _shots(placed: dict, durs: dict) -> list[dict]:
    return [{"id": k, "source": v["file"], "src": [v["ss"], v["ss"] + durs[k]]} for k, v in placed.items()]


def test_03_plan_broll_no_reuse() -> None:
    import look_s_render as lsr
    import studio_recipe as sr
    durs = {sid: round(t1 - t0, 4) for sid, t0, t1 in E2E}
    needs = [{"id": sid, "dur": durs[sid], "file": None, "ss": None} for sid, _, _ in E2E]
    lengths = {f: 8.0 for f in FILES}
    spans = {FILES[0]: [(1.267, 1.70), (4.50, 5.20)]}

    # the old round-robin layout (v792_6_final.json): the dark file got S07 then S12B -> wrapped to 0 -> overlapped S07
    old = [("S01A", 0, 0.0), ("S05A", 1, 0.0), ("S07", 2, 0.0), ("S10", 0, 3.48), ("S11", 1, 2.78), ("S12B", 2, 0.0)]
    rr = {sid: {"file": FILES[k], "ss": ss} for sid, k, ss in old}
    assert [f["shot"] for f in sr.check_source_reuse(_shots(rr, durs))] == ["S07"], "the round-robin layout must reproduce the reuse"

    res = lsr.plan_broll(needs, lengths, FILES, spans)
    placed = res["placements"]
    assert res["reuse_free"] and set(placed) == set(durs), res
    assert sr.check_source_reuse(_shots(placed, durs)) == [], sr.check_source_reuse(_shots(placed, durs))
    for sid, v in placed.items():
        assert 0.0 <= v["ss"] and v["ss"] + durs[sid] <= 8.0 + 1e-6, (sid, v)
    hook = placed["S01A"]
    assert not any(a < hook["ss"] + durs["S01A"] and hook["ss"] < b for a, b in spans.get(hook["file"], [])), hook

    two = lsr.plan_broll([{"id": f"X{i}", "dur": 3.0, "file": None, "ss": None} for i in range(3)], {"A": 8.0, "B": 4.0}, ["A", "B"], {})
    got = {k: (v["file"], v["ss"]) for k, v in two["placements"].items()}
    assert got == {"X0": ("A", 0.0), "X1": ("A", 3.0), "X2": ("B", 0.0)}, got          # most remaining seconds that fits

    tight = lsr.plan_broll([{"id": f"Y{i}", "dur": 3.0, "file": None, "ss": None} for i in range(3)], {"A": 4.0, "B": 4.0}, ["A", "B"], {})
    assert not tight["reuse_free"] and set(tight["placements"]) == {"Y0", "Y1", "Y2"}, tight
    print("[PASS] 03 plan_broll: e2e_v791 layout placed with 0 reused seconds and a clean hook (round-robin reused); most-remaining greedy")


def test_04_explicit_overrides_kept() -> None:
    import look_s_render as lsr
    needs = [{"id": "A", "dur": 2.0, "file": "f2", "ss": 1.5}, {"id": "B", "dur": 2.0, "file": "f2", "ss": None},
             {"id": "C", "dur": 2.0, "file": None, "ss": 4.0}, {"id": "D", "dur": 2.0, "file": None, "ss": None}]
    res = lsr.plan_broll(needs, {"f1": 8.0, "f2": 8.0}, ["f1", "f2"], {"f2": [(4.0, 4.5)]})
    p = res["placements"]
    assert (p["A"]["file"], p["A"]["ss"]) == ("f2", 1.5), p
    assert p["B"]["file"] == "f2" and (p["B"]["ss"] >= 4.5 or p["B"]["ss"] + 2.0 <= 1.5), p
    assert p["C"]["ss"] == 4.0, p
    assert res["reuse_free"], res
    print("[PASS] 04 explicit broll / broll_ss overrides are kept; a file-only override is placed clean inside that file")


# ---------------------------------------------------------------------------------------------- (5) CLI
def _cli_case(d: Path, scenes: list[dict], clips: dict[str, list[np.ndarray]]) -> list[str]:
    dur = scenes[-1]["end"]
    _ff("-f", "lavfi", "-i", f"color=c=0x303040:size=540x960:rate=30:duration={dur}", "-f", "lavfi", "-i",
        f"sine=frequency=220:sample_rate=48000:duration={dur}", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(d / "aroll.mp4"))
    broll = d / "broll"
    broll.mkdir(exist_ok=True)
    for name, frames in clips.items():
        _write_clip(broll / name, frames)
    (d / "scenes.json").write_text(json.dumps({"look": "S", "duration": dur, "scenes": scenes}), encoding="utf-8")
    (d / "words.json").write_text(json.dumps([[f"w{i}", i * 0.4 + 0.05, i * 0.4 + 0.3] for i in range(int(dur / 0.4))]), encoding="utf-8")
    return ["--scenes", str(d / "scenes.json"), "--words", str(d / "words.json"), "--aroll", str(d / "aroll.mp4"), "--work", str(d / "work"),
            "--out", str(d / "master.mp4"), "--broll-dir", str(broll), "--dry-run", "--no-hook-motion", "--no-product-safe-text"]


def _lsr(*args: str) -> tuple[int, dict]:
    r = subprocess.run([PY, str(LSR), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.returncode, {"stdout": r.stdout[-800:], "stderr": r.stderr[-800:]}


def test_05_cli_reuse_and_artifacts() -> None:
    r = subprocess.run([PY, str(LSR), "--help"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "--allow-broll-reuse" in r.stdout and "--no-broll-artifact-scan" in r.stdout, r.stdout[-400:]
    sc = lambda i, t0, t1, m: {"id": f"T{i}", "start": t0, "end": t1, "mode": m, "kind": "text", "jewel": "#F5C451", "text": ""}  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="pfd793_") as td:
        d = Path(td)
        base = _cli_case(d, [sc(0, 0.0, 1.5, "H"), sc(1, 1.5, 3.0, "A2")], {"only.mp4": _sliver_frames(320, 180, 60, range(0))})
        rc, doc = _lsr(*base)
        assert rc == 2 and doc.get("ok") is False and "--allow-broll-reuse" in doc.get("error", "") and "T0" in doc["error"], (rc, doc)
        rc, doc = _lsr(*base, "--allow-broll-reuse")
        assert rc == 0 and doc["broll_reuse"] and any("reuse" in w for w in doc["warnings"]), (rc, doc)

    with tempfile.TemporaryDirectory(prefix="pfd793_") as td:
        d = Path(td)
        base = _cli_case(d, [sc(0, 0.0, 1.5, "H"), sc(1, 1.5, 2.0, "A1")], {"hook.mp4": _sliver_frames(640, 360, 120, range(15, 20))})
        rc, doc = _lsr(*base)
        assert rc == 0, (rc, doc)
        hook = doc["scenes"][0]["broll"]
        art = doc["broll_artifacts"]
        assert art["scanned"] and art["files"]["hook.mp4"], art
        t1 = art["files"]["hook.mp4"][0]["t1"]
        assert hook["ss"] >= t1 - 1e-6 and hook["ss"] >= 0.633, (hook, art)
        assert art["shifted"] and art["shifted"][0]["scene"] == "T0" and art["shifted"][0]["from_ss"] == 0.0, art
        assert doc["broll_reuse"] == [], doc["broll_reuse"]
        rc, doc = _lsr(*base, "--no-broll-artifact-scan")
        assert rc == 0 and doc["scenes"][0]["broll"]["ss"] == 0.0 and doc["broll_artifacts"]["scanned"] is False, doc
    print("[PASS] 05 CLI: reuse -> exit 2 (--allow-broll-reuse -> warning); hook shifted past the transient; scan can be switched off")


# ---------------------------------------------------------------------------------------------- (6) probe early warning
def test_06_probe_low_res_low_fps_warning() -> None:
    import probe_and_align as pa
    chk = pa.look_s_source_check(1080, 1920, 59.94)
    assert chk["ok"] and chk["warnings"] == [], chk
    chk = pa.look_s_source_check(720, 1280, 30.0)
    assert chk["low_res"] and chk["low_fps"] and not chk["ok"] and len(chk["warnings"]) == 2, chk
    with tempfile.TemporaryDirectory(prefix="pfd793_") as td:
        tdp = Path(td)
        vid = tdp / "small.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x568:rate=30:duration=1.5", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid))
        rc = pa.main(["--input", str(vid), "--work", str(tdp / "work"), "--skip-whisper", "--tier", "fast"])
        assert rc == 0, rc
        ctx = json.loads((tdp / "work" / "workspace_context.json").read_text(encoding="utf-8"))
        ls = ctx["look_s_source"]
        assert ls["low_res"] and ls["low_fps"] and not ls["ok"], ls
        hits = [w for w in ctx["audit_warnings"] if "Look S" in w]
        assert len(hits) == 2 and any("1080p" in w for w in hits) and any("60" in w for w in hits), ctx["audit_warnings"]
    print("[PASS] 06 probe_and_align: early Look S low-res / low-fps warning in audit_warnings + workspace_context, exit 0")


if __name__ == "__main__":
    test_01_transient_spans_synthetic()
    test_02_scan_encoded_clip()
    test_03_plan_broll_no_reuse()
    test_04_explicit_overrides_kept()
    test_05_cli_reuse_and_artifacts()
    test_06_probe_low_res_low_fps_warning()
    print("TẤT CẢ ĐẠT (root cause B-roll v7.9.3)")
