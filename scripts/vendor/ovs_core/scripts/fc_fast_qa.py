#!/usr/bin/env python3
"""fc_fast_qa.py — Gộp toàn bộ bước hậu xử lý & kiểm định sau fc_build vào 1 phiên FilmCraft duy nhất.

Thay vì mở/đóng FilmCraft 4 lần rời rạc (fc_matte_band + limit-master + qa_frames + qa_audio, mất ~65s),
script này mở FilmCraft đúng 1 lần trên màn hình ảo để:
  1. Thay clip PNG "Dải tối trên" bằng Color Matte + Mask Feather mềm ("Dải tối trên · Color Matte")
  2. Gắn hoặc cập nhật hard_limiter (mặc định max = -2.2 dB) trên kênh Master ("Mix") để True Peak luôn <= -1.5 dBTP
  3. Lưu lại file .fcproj
  4. Xuất toàn bộ ảnh kiểm định (QA frames) tại các mốc thời gian yêu cầu
  5. Xuất file mix.wav và đo EBU R128 (Integrated LUFS, LRA, True Peak) + chạy audit_sfx.py kiểm tra lặp/clipping SFX

Cách dùng:
    python3 fc_fast_qa.py PROJECT.fcproj --frames-dir DIR --wav MIX.wav [--fps 30] [--limiter -2.2] [--times 0.5 1.2 4.0 ... | --times-file times.txt]

--times-file: tệp các mốc cách nhau bằng khoảng trắng / xuống dòng (contact_sheet.py times … --out times.txt); chạy giống nhau trong bash và zsh.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
CRAFT_TOOLS = THIS_DIR / "apps" / "craft-handoff" / "tools"
sys.path.insert(0, str(CRAFT_TOOLS))
sys.path.insert(0, str(THIS_DIR))

from craftctl import TICKS_PER_SECOND, Craft  # noqa: E402
from audit_sfx import AUDIT_SCRIPT, VENV_PY, fcproj_sfx_manifest  # noqa: E402

MATTE_NAME = "Dải tối trên · Color Matte"
WAV_PRESET = "Waveform Audio 48 kHz 24-bit"


def measure_loudness(wav: Path) -> dict:
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(wav), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, check=False
    ).stderr
    summary = err[err.rfind("Summary:"):]
    get = lambda key: float(re.search(rf"{key}:\s+(-?[\d.]+|-inf)", summary).group(1))  # noqa: E731
    return {"I": get("I"), "LRA": get("LRA"), "TP": get("Peak")}


def read_times_file(path: Path) -> list[float]:
    """Đọc mốc giây từ tệp (khoảng trắng / xuống dòng / dấu phẩy); lỗi chữ không phải số → ValueError nêu rõ."""
    out = []
    for tok in path.read_text(encoding="utf-8").replace(",", " ").split():
        try:
            out.append(float(tok))
        except ValueError:
            raise ValueError(f"{path}: «{tok}» không phải số giây") from None
    return out


def run_fast_qa(
    project: Path,
    frames_dir: Path | None = None,
    wav_out: Path | None = None,
    fps: float = 30.0,
    times: list[float] | None = None,
    limiter_max: float = -2.2,
    replace_matte: str = "Dải tối trên",
    matte_rect: tuple[float, float, float, float] = (-60.0, -50.0, 1140.0, 115.0),
    matte_feather: float = 868.8,
    matte_opacity: float = 59.2,
    matte_expansion: float = 213.1,
) -> int:
    t0 = time.perf_counter()
    project = project.resolve()

    with tempfile.TemporaryDirectory(prefix="fc_fast_qa_") as wd, Craft("filmcraft", Path(wd)) as fc:
        fc.cmd("file.open", {"path": str(project)})
        seq = fc.cmd("sequence.inspect")
        modified = False

        # 1. Thay "Dải tối trên" -> "Dải tối trên · Color Matte" nếu chưa thay
        hit = next(
            ((f"V{ti + 1}", it) for ti, tr in enumerate(seq["video"]) for it in tr["items"]
             if it.get("name") == replace_matte),
            None,
        )
        if hit is not None:
            track, old = hit
            fc.cmd("edit.clear", {"clips": [old["clip"]]})
            res = fc.cmd("file.newColorMatte", {"color": "#000000", "seconds": old["duration"] / TICKS_PER_SECOND})
            item = res.get("item") if isinstance(res, dict) else res
            clip = fc.cmd(
                "timeline.place",
                {"item": item, "track": track, "time": old["start"], "sourceIn": 0, "duration": old["duration"]},
            )["clips"][0]
            x0, y0, x1, y1 = matte_rect
            fc.pipeline([
                ("clip.rename", {"clip": clip, "name": MATTE_NAME}),
                ("masks.add", {"clip": clip, "effect": "opacity", "shape": "rectangle",
                               "path": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}),
                ("masks.set", {"clip": clip, "effect": "opacity", "feather": matte_feather,
                               "opacity": matte_opacity, "expansion": matte_expansion}),
            ])
            modified = True
            print(f"✅ [1/4] Đã chuyển «{replace_matte}» → «{MATTE_NAME}»")
        else:
            print(f"ℹ️ [1/4] Đã có sẵn «{MATTE_NAME}» (bỏ qua bước tạo mới)")

        # 2. Gắn hoặc cập nhật hard_limiter trên Master ("Mix")
        raw = json.loads(project.read_text(encoding="utf-8"))
        master_fx = [
            e.get("effect")
            for i in raw["project"]["items"].values()
            if "Sequence" in i.get("kind", {})
            for e in i["kind"]["Sequence"].get("master_effects") or []
        ]
        if "hard_limiter" not in master_fx:
            slot = fc.cmd("mixer.addInsert", {"strip": "Mix", "effect": "hard_limiter"})
            slot = slot.get("slot", 0) if isinstance(slot, dict) else 0
        else:
            slot = master_fx.index("hard_limiter")
        fc.cmd("mixer.setInsert", {"strip": "Mix", "slot": slot,
                                   "params": {"max": limiter_max, "lookahead": 7.0, "release": 100.0}})
        modified = True
        print(f"✅ [2/4] Đã khóa Master hard_limiter (max = {limiter_max} dB)")

        if modified:
            fc.cmd("file.saveAs", {"path": str(project)})

        # 3. Xuất toàn bộ ảnh QA trong cùng phiên
        if frames_dir is not None:
            frames_dir = frames_dir.resolve()
            frames_dir.mkdir(parents=True, exist_ok=True)
            dur_s = seq["duration"] / TICKS_PER_SECOND
            if not times:
                times = [round((i + 0.5) / 10 * dur_s, 2) for i in range(10)]
            for t in times:
                frame = round(t * fps)
                out_png = frames_dir / f"t{t:07.2f}.png"
                fc.cmd("file.exportFrame", {
                    "path": str(out_png),
                    "target": "program",
                    "time": int(frame * TICKS_PER_SECOND / fps),
                    "format": "png",
                })
            print(f"✅ [3/4] Đã xuất {len(times)} ảnh QA tại {frames_dir}")

        # 4. Xuất WAV bản trộn để đo EBU R128 trong cùng phiên
        if wav_out is not None:
            wav_out = wav_out.resolve()
            wav_out.parent.mkdir(parents=True, exist_ok=True)
            fc.cmd("export.quick", {"preset": WAV_PRESET, "path": str(wav_out), "wait": True})

    # Kiểm định EBU R128 & SFX Audit bên ngoài sau khi đóng FilmCraft
    rc = 0
    if wav_out is not None and wav_out.is_file():
        m = measure_loudness(wav_out)
        ok_audio = -16.0 <= m["I"] <= -14.0 and m["TP"] <= -1.5
        status = "ĐẠT ✅" if ok_audio else "CHƯA ĐẠT ❌"
        print(f"✅ [4/4] QA Audio: I = {m['I']:.1f} LUFS · LRA = {m['LRA']:.1f} LU · True Peak = {m['TP']:.1f} dBTP → {status}")
        if not ok_audio:
            rc = 1

    # Chạy nhanh audit-sfx
    events, video_end = fcproj_sfx_manifest(project)
    audit_script = AUDIT_SCRIPT
    qa_dir = wav_out.parent if wav_out is not None else project.parent / "qa"   # tệp tạm nằm trong qa/, không phải /tmp
    qa_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="audit_sfx_", dir=qa_dir) as tmpd:
        man = Path(tmpd) / "sfx_manifest.json"
        man.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
        cmd = [str(VENV_PY), str(audit_script), str(man), "--measure"]
        if video_end:
            cmd += ["--video-duration", f"{video_end:.3f}"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            rep = json.loads(res.stdout)
            clips_clipped = [f["path"] for f in rep.get("files", []) if f.get("clipping")]
            repeats = rep.get("repeated_takes", [])
            ok_sfx = not clips_clipped and not repeats and rep.get("missing_files", 0) == 0
            print(f"🔎 QA SFX: {rep['events']} sự kiện · {rep['unique_takes']} unique takes · "
                  f"lặp={len(repeats)} · clipping={len(clips_clipped)} → {'ĐẠT ✅' if ok_sfx else 'CẦN KIỂM TRA ⚠️'}")
            if not ok_sfx:
                rc = 1

    elapsed = time.perf_counter() - t0
    print(f"⚡ Hoàn tất toàn bộ hậu xử lý & QA trong 1 phiên duy nhất ({elapsed:.1f}s)")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", help="Đường dẫn tới file .fcproj")
    ap.add_argument("--frames-dir", help="Thư mục xuất ảnh QA (t0001.20.png...)")
    ap.add_argument("--wav", help="Đường dẫn xuất file mix.wav để đo LUFS / True Peak")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--limiter", type=float, default=-2.2, help="Ngưỡng hard_limiter trên Master (mặc định -2.2 dB)")
    ap.add_argument("--times", type=float, nargs="*", help="Danh sách các mốc giây cần xuất ảnh QA")
    ap.add_argument("--times-file", help="Tệp mốc giây (contact_sheet.py times … --out); gộp với --times")
    args = ap.parse_args()
    times = list(args.times or [])
    if args.times_file:
        try:
            times += read_times_file(Path(args.times_file))
        except (OSError, ValueError) as e:
            ap.error(str(e))
    return run_fast_qa(
        Path(args.project),
        frames_dir=Path(args.frames_dir) if args.frames_dir else None,
        wav_out=Path(args.wav) if args.wav else None,
        fps=args.fps,
        times=times or None,
        limiter_max=args.limiter,
    )


if __name__ == "__main__":
    sys.exit(main())
