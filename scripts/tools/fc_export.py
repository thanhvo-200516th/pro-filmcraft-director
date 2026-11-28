#!/usr/bin/env python3
"""
fc_export.py (v8.1.0) — thin glue: export a FilmCraft `.fcproj` to MP4 through the vendored `ovs_core` exporter.

    fc_export.py IN.fcproj OUT.mp4 [--crf N] [--lufs L] [--timeout S]

v7.7.0: the export runs with `wait:False` and polls `jobs.list` every 5 s until the job reports `finished:true`
(default `--timeout 1800` s; a job error or the timeout exits 1). Measured: 2447 frames at 1080x1920@60 took 339.5 s.

Run it ONLY when the user asks for an .mp4 or in draft mode: `compile_and_verify.py` never calls it.
Needs FilmCraft + a virtual display (see `scripts/vendor/ovs_core/scripts/apps/craft-handoff/tools/craftctl.py`);
reference timing: ~49 s for a 6 s clip. `PFD_OVS_DIR` overrides the vendored directory.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]


def _ovs_tools_dir() -> Path:
    base = Path(os.environ["PFD_OVS_DIR"]).expanduser() if os.environ.get("PFD_OVS_DIR") else SKILL_ROOT / "scripts" / "vendor" / "ovs_core"
    return base / "scripts" / "apps" / "craft-handoff" / "tools"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export a FilmCraft .fcproj to MP4 (explicit request / draft mode only).")
    ap.add_argument("project", help="Input .fcproj")
    ap.add_argument("out", help="Output .mp4")
    ap.add_argument("--crf", type=int, help="x264 CRF (lower = better quality)")
    ap.add_argument("--lufs", type=float, help="Loudness normalisation on export, e.g. -14")
    ap.add_argument("--timeout", type=float, default=1800.0, help="Seconds to wait for the export job (default 1800)")
    args = ap.parse_args(argv)

    project, out = Path(args.project), Path(args.out)
    if not project.is_file():
        print(f"fc_export: project not found: {project}", file=sys.stderr)
        return 2
    tools = _ovs_tools_dir()
    if not (tools / "fc_export.py").is_file():
        print(f"fc_export: vendored exporter missing at {tools} (set PFD_OVS_DIR or restore scripts/vendor/ovs_core)", file=sys.stderr)
        return 2
    sys.path.insert(0, str(tools))  # vendored `craftctl` must win over anything else on the path
    try:
        spec = importlib.util.spec_from_file_location("pfd_ovs_fc_export", tools / "fc_export.py")
        ovs_export = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ovs_export)  # type: ignore[union-attr]
        from craftctl import CraftError
    except (ImportError, AttributeError) as exc:
        print(f"fc_export: cannot import vendored exporter: {exc}", file=sys.stderr)
        return 2
    try:
        result = ovs_export.export(project, out, "h264", args.lufs, args.crf, timeout=args.timeout)
    except CraftError as exc:
        print(f"fc_export: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
