#!/usr/bin/env python3
"""
ffskill_bridge.py (v7.9.0) — OPTIONAL bridge between pro-filmcraft-director ('The Creative Brain')
and kajisho5/ffmpeg-skill v4.5.3 ('The 42-Tool Deterministic FFmpeg Execution & Verification Engine').

The sibling repo `../ffmpeg-skill` is optional: when it is absent every entry point raises
`FfskillUnavailable` with a one-line remedy (and the CLI prints it) instead of a traceback.
Use `ffskill_available()` to branch, or `scripts/env_status.py` for the host report.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
FFSKILL_ROOT = SKILL_ROOT.parent / "ffmpeg-skill"
FFSKILL_SCRIPTS = FFSKILL_ROOT / "scripts"
FFSKILL_MCP = FFSKILL_ROOT / "mcp" / "server.py"


class FfskillUnavailable(RuntimeError):
    """The optional sibling repo `ffmpeg-skill` is not installed next to pro-filmcraft-director."""


def ffskill_available() -> bool:
    return FFSKILL_SCRIPTS.is_dir()


def _require_ffskill() -> None:
    if not ffskill_available():
        raise FfskillUnavailable(
            f"optional dependency ffmpeg-skill not found at {FFSKILL_ROOT} "
            "(git clone kajisho5/ffmpeg-skill there to enable ffskill_bridge; the rest of PFD works without it)"
        )


def run_ffskill_tool(tool_name: str, args: list[str], parse_json: bool = True) -> dict[str, Any] | str:
    """Invokes any of the 42 tools in kajisho5/ffmpeg-skill with --json output."""
    _require_ffskill()
    script_path = FFSKILL_SCRIPTS / f"{tool_name}.py"
    if not script_path.exists():
        raise FileNotFoundError(f"ffmpeg-skill tool not found: {script_path}")
    cmd = [sys.executable, str(script_path), *args]
    if parse_json and "--json" not in args and "--json-brief" not in args:
        cmd.append("--json")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(f"ffmpeg-skill {tool_name} failed ({proc.returncode}): {proc.stderr.strip()}")
    if parse_json:
        return json.loads(proc.stdout)
    return proc.stdout


def ffskill_doctor() -> dict[str, Any]:
    """Returns full hardware/codec/filter/font capability introspection from _contract.py doctor."""
    _require_ffskill()
    proc = subprocess.run(
        [sys.executable, str(FFSKILL_SCRIPTS / "_contract.py"), "doctor", "--json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
    )
    return json.loads(proc.stdout)


def ffskill_probe(video_path: str | Path, analyze: bool = True) -> dict[str, Any]:
    args = [str(video_path)]
    if analyze:
        args.append("--analyze")
    return run_ffskill_tool("probe", args)  # type: ignore[return-value]


def ffskill_check_comprehensive(
    video_path: str | Path,
    platform: str = "tiktok",
    content: bool = True,
    levels: str = "bt709",
) -> dict[str, Any]:
    """
    Runs check.py with platform compliance + --content (black/frozen/silence/dropouts/1-frame flashes/first-frame)
    + --levels bt709 (broadcast signal range verification).
    """
    args = [str(video_path), "--platform", platform]
    if content:
        args.append("--content")
    if levels:
        args += ["--levels", levels]
    return run_ffskill_tool("check", args)  # type: ignore[return-value]


def ffskill_smart_cut(
    video_path: str | Path,
    start: str | float,
    end: str | float,
    out_path: str | Path,
) -> dict[str, Any]:
    """GOP-boundary smart cut (--smart): re-encodes only partial GOPs at cut points, stream-copies the middle."""
    args = [
        str(video_path),
        "--start", str(start),
        "--end", str(end),
        "--smart",
        "--out", str(out_path),
        "--overwrite",
    ]
    return run_ffskill_tool("cut", args)  # type: ignore[return-value]


def ffskill_speech_aware_silence(
    video_path: str | Path,
    out_path: str | Path,
    timemap_path: str | Path | None = None,
) -> dict[str, Any]:
    """Runs speech-aware silence cutting preserving mid-clause breath pauses and auditing cut_points RMS."""
    args = [
        str(video_path),
        "--speech-aware",
        "--out", str(out_path),
        "--overwrite",
    ]
    if timemap_path:
        args += ["--timemap", str(timemap_path)]
    return run_ffskill_tool("silence", args)  # type: ignore[return-value]


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description="Optional bridge to the sibling ffmpeg-skill repo: prints its doctor summary (exit 2 when it is not installed). Import this module to call the ffskill_* helpers.").parse_args()
    try:
        doc = ffskill_doctor()
    except FfskillUnavailable as exc:
        print(f"ffskill_bridge: {exc}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps({
        "ffmpeg_skill_version": doc.get("version"),
        "ffmpeg_version": doc.get("ffmpeg"),
        "usable_tools_count": sum(1 for v in doc.get("tools", {}).values() if v.get("usable") == "yes"),
        "mcp_server_path": str(FFSKILL_MCP),
    }, indent=2))
