#!/usr/bin/env python3
"""
filmcraft_cli.py (v7.9.0) — thin shim over the vendored `craftctl.Craft`; replaces the `filmcraft-cli` binary that never existed
(only the GUI `filmcraft` does, see references/30_filmcraft_control_bridge.md).

    filmcraft_cli.py [--project P.fcproj] [--display :N] [--allow-offline] [--timeout S] <cmd>

      status                          start one private FilmCraft, ask `state.inspect`, print the version
      open   [P.fcproj]               `file.open`; report `missingMedia` (exit 3 when > 0 unless --allow-offline)
      render (--seconds S | --frame N) --out F.png
                                      `file.open` + `sequence.inspect` + `file.exportFrame` (program monitor)
      export [P.fcproj] OUT.mp4 [--crf N] [--lufs L]
                                      delegates to `scripts/tools/fc_export.py` (explicit request / draft mode only)

Exactly one JSON line on stdout. Exit 0 ok | 1 control error | 2 usage, no `filmcraft` binary or no X (`"skipped": true`
for the last two) | 3 offline media or empty frame | 124 timed out.

One private app per call (own random port, own random 64-hex token passed through the environment only and never printed,
own temp `--data-dir`, `--graphics software --no-recover --empty`); only that child process is ever terminated. Never uses the
user's `DISPLAY`: order is `--display` > `CRAFT_DISPLAY` > craftctl default (`:93`); `:0` is refused. The PNG is for structural
QA only (llvmpipe), not pixel-exact against a GPU export.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]
TICKS_PER_SECOND = 254_016_000_000  # FilmCraft time unit; asserted equal to craftctl.TICKS_PER_SECOND at runtime
EXIT_OK, EXIT_CONTROL, EXIT_USAGE, EXIT_OFFLINE, EXIT_TIMEOUT = 0, 1, 2, 3, 124
DEFAULT_TIMEOUT_S = 120
CRAFT_ARGS = ("--graphics", "software", "--empty")  # Craft itself adds --control, --data-dir and --no-recover
REFUSED_DISPLAYS = (":0", ":0.0")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_ACTIVE_PROC: list[subprocess.Popen] = []  # the one child we started, so a signal can terminate it and nothing else


class FcliError(Exception):
    """An error with the exit code and extra JSON fields it should report."""

    def __init__(self, code: int, message: str, **extra: Any):
        super().__init__(message)
        self.code = code
        self.extra = extra


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested with a fake Craft that only has `cmd()`)
# ---------------------------------------------------------------------------

def fps_from_inspect(inspected: dict[str, Any]) -> Fraction:
    """Exact frame rate from `settings.frame_rate{num,den}`. Never defaults: a missing rate is an error, not 25."""
    rate = (inspected.get("settings") or {}).get("frame_rate")
    if not isinstance(rate, dict):
        raise FcliError(EXIT_CONTROL, "sequence.inspect has no settings.frame_rate")
    num, den = rate.get("num"), rate.get("den")
    if not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in (num, den)):
        raise FcliError(EXIT_CONTROL, f"sequence.inspect settings.frame_rate is not a positive num/den: {rate!r}")
    return Fraction(num, den)


def ticks_per_frame(fps: Fraction) -> int:
    return int(round(Fraction(TICKS_PER_SECOND) / fps))


def seconds_to_ticks(seconds: float) -> int:
    return int(round(Fraction(str(seconds)) * TICKS_PER_SECOND))


def frame_to_ticks(frame: int, fps: Fraction) -> int:
    return int(round(Fraction(frame) * TICKS_PER_SECOND / fps))


def clamp_ticks(ticks: int, duration_ticks: int, fps: Fraction) -> tuple[int, bool]:
    """Clamp into [0, duration - 1 frame]; `file.exportFrame` accepts anything and returns a near-black PNG past the end."""
    if duration_ticks <= 0:
        raise FcliError(EXIT_CONTROL, f"sequence has no duration (duration={duration_ticks})")
    last = max(0, duration_ticks - ticks_per_frame(fps))
    clamped = min(max(ticks, 0), last)
    return clamped, clamped != ticks


def absolute_path(path: str | Path) -> Path:
    """The app resolves relative paths against ITS cwd (garbage); always hand it absolute ones."""
    return Path(path).expanduser().resolve()


def exit_code_for(payload: dict[str, Any]) -> int:
    if payload.get("ok"):
        return EXIT_OK
    if payload.get("exit") in (EXIT_CONTROL, EXIT_USAGE, EXIT_OFFLINE, EXIT_TIMEOUT):
        return int(payload["exit"])
    return EXIT_CONTROL


def missing_media_from_open(opened: Any) -> int:
    """`file.open` must report a real int `missingMedia`; anything else means we cannot prove 0 offline."""
    value = opened.get("missingMedia") if isinstance(opened, dict) else None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise FcliError(EXIT_CONTROL, f"file.open returned no usable missingMedia: {opened!r}")
    return value


def check_png(path: Path, min_std: float = 0.0) -> dict[str, Any]:
    """Structural check of the exported frame: exists, non-empty, PNG magic; gray std when PIL+numpy exist (enforced if min_std>0)."""
    if not path.is_file() or path.stat().st_size == 0:
        raise FcliError(EXIT_OFFLINE, f"exported frame missing or empty: {path}", blank=True)
    with path.open("rb") as fh:
        if fh.read(8) != PNG_MAGIC:
            raise FcliError(EXIT_OFFLINE, f"exported frame is not a PNG: {path}", blank=True)
    info: dict[str, Any] = {"bytes": path.stat().st_size}
    try:
        import numpy as np
        from PIL import Image
        with Image.open(path) as im:
            gray = np.asarray(im.convert("L"), dtype=np.float32)
        info["std"] = round(float(gray.std()), 2)
    except ImportError:
        info["std"] = None
    if min_std > 0 and info["std"] is not None and info["std"] <= min_std:
        raise FcliError(EXIT_OFFLINE, f"exported frame looks blank (gray std {info['std']} <= {min_std})", blank=True, **info)
    return info


def open_project(craft: Any, project: Path, allow_offline: bool) -> tuple[dict[str, Any], int]:
    """`file.open` with an absolute path; returns (payload, missingMedia). Offline media is `ok:false`/exit 3 unless allowed."""
    opened = craft.cmd("file.open", {"path": str(project)})
    missing = missing_media_from_open(opened)
    payload: dict[str, Any] = {"ok": True, "project": str(project), "missingMedia": missing}
    if missing > 0 and not allow_offline:
        payload.update(ok=False, exit=EXIT_OFFLINE, error=f"{missing} offline media item(s) in {project.name}")
    return payload, missing


def do_open(craft: Any, project: Path, allow_offline: bool) -> dict[str, Any]:
    payload, _ = open_project(craft, project, allow_offline)
    inspected = craft.cmd("sequence.inspect", {}) or {}
    payload["sequence"] = inspected.get("name")
    return payload


def do_render(craft: Any, project: Path, out: Path, seconds: float | None, frame: int | None,
              allow_offline: bool, min_std: float = 0.0) -> dict[str, Any]:
    payload, _ = open_project(craft, project, allow_offline)
    inspected = craft.cmd("sequence.inspect", {}) or {}
    fps = fps_from_inspect(inspected)
    duration = inspected.get("duration")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise FcliError(EXIT_CONTROL, f"sequence.inspect has no integer duration: {duration!r}")
    requested = frame_to_ticks(frame, fps) if frame is not None else seconds_to_ticks(seconds or 0.0)
    ticks, clamped = clamp_ticks(requested, duration, fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    exported = craft.cmd("file.exportFrame", {"path": str(out), "target": "program", "time": ticks, "format": "png"}) or {}
    payload.update(
        frame_png=str(out), fps=f"{fps.numerator}/{fps.denominator}", duration_s=round(float(Fraction(duration, TICKS_PER_SECOND)), 4),
        ticks=ticks, time_s=round(float(Fraction(ticks, TICKS_PER_SECOND)), 4), clamped=clamped,
        width=exported.get("width"), height=exported.get("height"),
    )
    try:
        payload.update(check_png(out, min_std))
    except FcliError as exc:  # blank frame: keep the fields gathered so far
        payload.update(ok=False, exit=exc.code, error=str(exc), **exc.extra)
    return payload


def do_status(craft: Any, display: str) -> dict[str, Any]:
    state = craft.cmd("state.inspect", {})
    return {"ok": True, "version": _binary_version(), "display": display, "state_keys": sorted(state) if isinstance(state, dict) else []}


# ---------------------------------------------------------------------------
# Environment, craftctl loading, process hygiene
# ---------------------------------------------------------------------------

def filmcraft_binary() -> str | None:
    """Same lookup order craftctl uses: CRAFT_BIN_DIR, then PATH, then ~/.local/bin."""
    env_dir = os.environ.get("CRAFT_BIN_DIR")
    cands = [Path(env_dir) / "filmcraft"] if env_dir else []
    on_path = shutil.which("filmcraft")
    cands += ([Path(on_path)] if on_path else []) + [Path.home() / ".local" / "bin" / "filmcraft"]
    return next((str(p) for p in cands if p.is_file()), None)


def _binary_version() -> str:
    binary = filmcraft_binary()
    if not binary:
        return ""
    try:
        r = subprocess.run([binary, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=False)
        return ((r.stdout or r.stderr).strip().splitlines() or [""])[0]
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _ovs_tools_dir() -> Path:
    base = Path(os.environ["PFD_OVS_DIR"]).expanduser() if os.environ.get("PFD_OVS_DIR") else SKILL_ROOT / "scripts" / "vendor" / "ovs_core"
    return base / "scripts" / "apps" / "craft-handoff" / "tools"


def load_craftctl(binary: str) -> Any:
    tools = _ovs_tools_dir()
    if not (tools / "craftctl.py").is_file():
        raise FcliError(EXIT_USAGE, f"vendored craftctl missing at {tools} (set PFD_OVS_DIR or restore scripts/vendor/ovs_core)")
    os.environ["CRAFT_BIN_DIR"] = str(Path(binary).parent)  # craftctl reads it at import; makes PATH installs work too
    sys.path.insert(0, str(tools))  # the vendored copy must win over anything else on the path
    import craftctl  # noqa: PLC0415
    if craftctl.TICKS_PER_SECOND != TICKS_PER_SECOND:
        raise FcliError(EXIT_CONTROL, f"craftctl.TICKS_PER_SECOND={craftctl.TICKS_PER_SECOND} differs from {TICKS_PER_SECOND}")
    return craftctl


def resolve_display(requested: str | None, craftctl: Any) -> str:
    """--display > CRAFT_DISPLAY > craftctl default (:93). Never the user's DISPLAY, never :0."""
    display = requested or os.environ.get("CRAFT_DISPLAY") or craftctl.DEFAULT_DISPLAY
    if display in REFUSED_DISPLAYS:
        raise FcliError(EXIT_USAGE, f"refusing display {display}: that is the user's real desktop; use a private X display")
    return display


def x_available(display: str) -> bool:
    if Path(f"/tmp/.X11-unix/X{display.lstrip(':').split('.')[0]}").exists():
        return True
    server = os.environ.get("CRAFT_X_SERVER") or ("Xephyr" if shutil.which("Xephyr") else "Xvfb")
    return bool(shutil.which(server))


def _scrub(text: str, secret: str | None) -> str:
    return text.replace(secret, "<token>") if secret else text


class _Interrupted(Exception):
    def __init__(self, signum: int):
        super().__init__(f"signal {signum}")
        self.signum = signum


def _on_signal(signum: int, _frame: Any) -> None:
    for proc in _ACTIVE_PROC:  # only the child this process started
        if proc.poll() is None:
            proc.terminate()
    raise _Interrupted(signum)


def run_with_craft(craftctl: Any, display: str, timeout_s: int, work: Any) -> dict[str, Any]:
    """One private app per call; `work(craft)` returns the payload. The temp dir (incl. --data-dir) is removed in `finally`."""
    tmp = Path(tempfile.mkdtemp(prefix="fcli-"))
    token: str | None = None
    old = {s: signal.signal(s, _on_signal) for s in (signal.SIGALRM, signal.SIGTERM)}
    try:
        with craftctl.Craft("filmcraft", tmp, display=display, args=CRAFT_ARGS) as craft:
            token = craft.token
            _ACTIVE_PROC.append(craft.proc)
            signal.alarm(timeout_s)  # armed only once the app is up: craftctl bounds startup itself
            try:
                return work(craft)
            finally:
                signal.alarm(0)
    except _Interrupted as exc:
        timed_out = exc.signum == signal.SIGALRM
        raise FcliError(EXIT_TIMEOUT if timed_out else EXIT_CONTROL,
                        f"timed out after {timeout_s}s" if timed_out else "interrupted by SIGTERM") from None
    except craftctl.CraftError as exc:
        raise FcliError(EXIT_CONTROL, _scrub(str(exc), token)) from None
    finally:
        _ACTIVE_PROC.clear()
        for s, handler in old.items():
            signal.signal(s, handler)
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # usage errors are JSON too, exit 2
        _emit({"ok": False, "exit": EXIT_USAGE, "error": f"usage: {message}"})
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    ap = _JsonParser(description="Drive one private FilmCraft through craftctl (replaces the nonexistent `filmcraft-cli`).")
    ap.add_argument("--project", help="Project .fcproj (global option: goes BEFORE the subcommand)")
    ap.add_argument("--display", help="X display, e.g. :93 (default: CRAFT_DISPLAY, then craftctl's :93; :0 is refused)")
    ap.add_argument("--allow-offline", action="store_true", help="do not fail (exit 3) when missingMedia > 0")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help=f"seconds for the command once the app is up (default {DEFAULT_TIMEOUT_S})")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=_JsonParser)
    sub.add_parser("status", help="app + control port health, version")
    p_open = sub.add_parser("open", help="file.open and report missingMedia")
    p_open.add_argument("project_pos", nargs="?", metavar="P.fcproj")
    p_ren = sub.add_parser("render", help="export ONE frame of the program monitor as PNG")
    when = p_ren.add_mutually_exclusive_group(required=True)
    when.add_argument("--seconds", type=float, help="time in seconds")
    when.add_argument("--frame", type=int, help="frame number (0-based)")
    p_ren.add_argument("--out", required=True, help="output .png")
    p_ren.add_argument("--min-std", type=float, default=0.0, help="fail (exit 3) when the gray std of the frame is <= this (default off)")
    p_exp = sub.add_parser("export", help="export MP4 via fc_export.py (explicit request / draft mode only)")
    p_exp.add_argument("export_args", nargs="+", metavar="[P.fcproj] OUT.mp4")
    p_exp.add_argument("--crf", type=int)
    p_exp.add_argument("--lufs", type=float)
    return ap


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _project_for(args: argparse.Namespace) -> Path:
    raw = getattr(args, "project_pos", None) or args.project
    if not raw:
        raise FcliError(EXIT_USAGE, f"`{args.cmd}` needs a project: --project P.fcproj before the subcommand")
    project = absolute_path(raw)
    if not project.is_file():
        raise FcliError(EXIT_USAGE, f"project not found: {project}")
    return project


def _do_export(args: argparse.Namespace, display: str) -> dict[str, Any]:
    *head, out = args.export_args
    if len(head) > 1 or (not head and not args.project):
        raise FcliError(EXIT_USAGE, "export takes [P.fcproj] OUT.mp4 (project may also come from --project)")
    project = absolute_path(head[0] if head else args.project)
    cmd = [sys.executable, str(Path(__file__).resolve().parent / "fc_export.py"), str(project), str(absolute_path(out))]
    cmd += (["--crf", str(args.crf)] if args.crf is not None else []) + (["--lufs", str(args.lufs)] if args.lufs is not None else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=1800,
                       env={**os.environ, "CRAFT_DISPLAY": display})
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        raise FcliError(r.returncode if r.returncode in (EXIT_CONTROL, EXIT_USAGE) else EXIT_CONTROL, (r.stderr or r.stdout).strip()[-500:])
    try:
        return {"ok": True, "export": json.loads(last)}
    except json.JSONDecodeError:
        return {"ok": True, "export_stdout": last}


def _run(args: argparse.Namespace) -> dict[str, Any]:
    binary = filmcraft_binary()
    if not binary:
        raise FcliError(EXIT_USAGE, "skipped: no `filmcraft` binary (checked CRAFT_BIN_DIR, PATH, ~/.local/bin)", skipped=True)
    craftctl = load_craftctl(binary)
    display = resolve_display(args.display, craftctl)
    if not x_available(display):
        raise FcliError(EXIT_USAGE, f"skipped: no X server on {display} and no Xvfb/Xephyr installed", skipped=True)
    if args.cmd == "export":
        return _do_export(args, display)
    if args.cmd == "status":
        return run_with_craft(craftctl, display, args.timeout, lambda c: do_status(c, display))
    project = _project_for(args)
    if args.cmd == "open":
        return run_with_craft(craftctl, display, args.timeout, lambda c: do_open(c, project, args.allow_offline))
    out = absolute_path(args.out)
    return run_with_craft(craftctl, display, args.timeout, lambda c: do_render(
        c, project, out, args.seconds, args.frame, args.allow_offline, args.min_std))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = time.perf_counter()
    try:
        payload = _run(args)
    except FcliError as exc:
        payload = {"ok": False, "exit": exc.code, "error": str(exc), **exc.extra}
    payload["elapsed_s"] = round(time.perf_counter() - started, 2)
    _emit(payload)
    return exit_code_for(payload)


if __name__ == "__main__":
    sys.exit(main())
