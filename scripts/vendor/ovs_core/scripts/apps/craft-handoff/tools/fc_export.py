#!/usr/bin/env python3
"""fc_export — mở một project FilmCraft (.fcproj) trên màn hình ảo và xuất ra file video (mặc định MP4 H.264).

Dùng cho chế độ server / job API: không có người duyệt nên bản dựng được xuất tự động.
Làm tay trên máy vẫn giữ luật "không tự xuất MP4" — chỉ chạy công cụ này khi được yêu cầu hoặc khi chạy theo job.

    python fc_export.py PROJECT.fcproj OUT.mp4 [--format h264] [--lufs -14] [--crf 20] [--timeout 1800]

Env: CRAFT_DISPLAY, CRAFT_BIN_DIR, CRAFT_X_SERVER (Xephyr | Xvfb) — xem craftctl.py.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from craftctl import Craft, CraftError  # noqa: E402


DEFAULT_TIMEOUT_S = 1800.0
POLL_S = 5.0


def _wait_for_job(fc, job_id, timeout: float, poll_s: float) -> dict:
    """Poll `jobs.list` until OUR job reports `finished: true`, then return its entry.

    A finished entry stays in the list and an empty list only means "not registered yet", so neither is a completion
    signal. A job error (or a finished job without a result) raises CraftError."""
    deadline = time.monotonic() + timeout
    while True:
        jobs = fc.cmd("jobs.list") or []
        mine = [j for j in jobs if job_id is None or j.get("id") == job_id]
        if not mine and job_id is None:
            mine = list(jobs)[-1:]
        job = mine[-1] if mine else None
        if job is not None and job.get("finished"):
            status = str(job.get("status") or "").lower()
            if job.get("error") or status.startswith(("error", "failed", "cancel")):
                raise CraftError(f"export job {job_id} failed: {job.get('error') or job.get('status')}")
            if not isinstance(job.get("result"), dict):
                raise CraftError(f"export job {job_id} finished without a result: {job}")
            return job
        if time.monotonic() >= deadline:
            raise CraftError(f"export job {job_id} timeout after {timeout:g} s (last state: {job})")
        time.sleep(poll_s)


def export(project: Path, out: Path, fmt: str = "h264", lufs: float | None = None, crf: int | None = None,
           workdir: Path | None = None, *, timeout: float = DEFAULT_TIMEOUT_S, poll_s: float = POLL_S) -> dict:
    """Export through `export.quick` with wait:False and poll `jobs.list` every `poll_s` (5 s) up to `timeout` s (1800 s).
    A single blocking `wait:True` call dies on the control socket for long projects (measured: 339.5 s, 15 058 423 B for 2447 frames)."""
    project, out = project.resolve(), out.resolve()
    if not project.exists():
        raise CraftError(f"không có project {project}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = workdir or Path(tempfile.mkdtemp(prefix="fc_export-"))
    params: dict = {"path": str(out), "format": fmt, "wait": False}
    if lufs is not None:
        params["loudnessLufs"] = lufs
    if crf is not None:
        params["bitrateMode"], params["crf"] = "crf", crf
    try:
        with Craft("filmcraft", tmp) as fc:
            fc.cmd("file.open", {"path": str(project)})
            started = fc.cmd("export.quick", params) or {}
            job = _wait_for_job(fc, started.get("job"), timeout, poll_s)   # leave the `with Craft` block only after finished:true
    finally:
        if workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)
    result = job["result"]
    done = Path(result.get("path") or out)
    if not done.exists() or done.stat().st_size == 0:
        raise CraftError(f"FilmCraft báo xong nhưng không có file {done}: {result}")
    return {"out": str(done), "bytes": int(result.get("bytes") or done.stat().st_size), "result": result}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Xuất video từ project FilmCraft (.fcproj).")
    ap.add_argument("project")
    ap.add_argument("out")
    ap.add_argument("--format", default="h264")
    ap.add_argument("--lufs", type=float, help="chuẩn hoá loudness khi xuất, vd -14")
    ap.add_argument("--crf", type=int)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="giây chờ job xuất (mặc định 1800)")
    a = ap.parse_args(argv)
    try:
        print(json.dumps(export(Path(a.project), Path(a.out), a.format, a.lufs, a.crf, timeout=a.timeout), ensure_ascii=False))
    except CraftError as exc:
        print(f"fc_export: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
