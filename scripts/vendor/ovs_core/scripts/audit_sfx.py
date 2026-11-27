#!/usr/bin/env python3
"""audit_sfx — kiểm toán SFX trong project FilmCraft (.fcproj) hoặc manifest JSON.

    python3 audit_sfx.py PROJECT.fcproj [--out DIR] | manifest.json

--out DIR (v2.6): nơi ghi sfx_manifest.json + audit_sfx.json (mặc định `qa/` cạnh project). Không ghi vào /tmp.

Thư viện: fcproj_sfx_manifest(project) → (events, video_end), dùng chung với fc_fast_qa.py.
Lõi kiểm toán: scripts/apps/talking-head-premiere/scripts/audit_sfx.py.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SKILL_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = HOME / ".venvs" / "video-skills" / "bin" / "python"
AUDIT_SCRIPT = SKILL_ROOT / "scripts" / "apps" / "talking-head-premiere" / "scripts" / "audit_sfx.py"
TICKS = 254_016_000_000


def run_cmd(cmd, check=True):
    print(f"▶ Thực thi: {' '.join(str(c) for c in cmd)}")
    return subprocess.run([str(c) for c in cmd], check=check, timeout=1800)


def fcproj_sfx_manifest(project: Path) -> tuple[list, float]:
    """Rút SFX từ .fcproj thành manifest cho audit_sfx.py (nhận list {path,start,duration,sourceIn,gain_db}).
    gain_db (v7.7.0) = độ lợi clip (dB) để kiểm toán clipping theo đỉnh SAU gain: đỉnh * 10**(gain_db/20) >= 1.0.
    Lấy track âm tên có "SFX"; không có thì lấy mọi track âm trừ track đầu (giọng) và track tên nhạc/music."""
    d = json.loads(project.read_text(encoding="utf-8"))
    items = d["project"]["items"]
    seqs = [i["kind"]["Sequence"] for i in items.values() if "Sequence" in i.get("kind", {})]
    seq = max(seqs, key=lambda q: sum(len(t["items"]) for t in q["audio_tracks"]))
    tracks = seq["audio_tracks"]
    pick = [t for t in tracks if "sfx" in (t.get("name") or "").lower()] or \
           [t for t in tracks[1:] if not any(k in (t.get("name") or "").lower() for k in ("nhạc", "music", "bgm"))]
    events = []
    for t in pick:
        for c in t["items"]:
            media = items[str(c["item"])]["kind"]["Media"]["media"]["File"]["path"]
            events.append({"path": media, "start": c["start"] / TICKS, "duration": c["duration"] / TICKS,
                           "sourceIn": c.get("source_in", 0) / TICKS, "source": media,
                           "gain_db": float(c.get("gain_db") or 0.0)})
    video_end = max((c["start"] + c["duration"]) / TICKS for t in seq["video_tracks"] for c in t["items"]) if seq["video_tracks"] else None
    return sorted(events, key=lambda e: e["start"]), video_end


def cmd_audit_sfx(args):
    audit_script = AUDIT_SCRIPT
    target = Path(args.project).resolve()
    if target.suffix == ".fcproj":          # audit_sfx.py chỉ đọc manifest JSON (list) → rút từ project trước
        events, video_end = fcproj_sfx_manifest(target)
        out = Path(args.out).resolve() if args.out else target.parent / "qa"
        out.mkdir(parents=True, exist_ok=True)
        man = out / "sfx_manifest.json"
        man.write_text(json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"🔎 {len(events)} SFX trong {target.name} (video dài {video_end:.2f}s) → {man}")
        cmd = [VENV_PY, audit_script, man, "--measure", "--output", out / "audit_sfx.json"] + (["--video-duration", f"{video_end:.3f}"] if video_end else [])
    else:
        cmd = [VENV_PY, audit_script, target]
    return run_cmd(cmd, check=False).returncode


def main():
    parser = argparse.ArgumentParser(description="Kiểm toán SFX trong project FilmCraft (.fcproj) / Premiere")
    parser.add_argument("project", help="Đường dẫn tới file project hoặc thư mục")
    parser.add_argument("--out", help="Thư mục ghi tệp trung gian + báo cáo (mặc định: qa/ cạnh project)")
    sys.exit(cmd_audit_sfx(parser.parse_args()))


if __name__ == "__main__":
    main()
