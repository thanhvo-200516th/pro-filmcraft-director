#!/usr/bin/env python3
"""
env_status.py (v7.9.0) — preflight of everything `pro-filmcraft-director` needs on this host.

    env_status.py [--json] [--strict]

Each check prints OK or MISSING plus a one-line remedy. Optional items (fonts with a documented fallback,
the FilmCraft control bridge, the sibling ffmpeg-skill repo) are MISSING but never fatal. Exit code is 1 only when
`--strict` is given AND a required check is MISSING.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "7.9.0"
SKILL_ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
VENDOR = SKILL_ROOT / "scripts" / "vendor" / "ovs_core"
VENV = HOME / ".venvs" / "video-skills"

FONT_FALLBACKS = {
    "SVN-Aaron": "Playfair Display Italic (references/16_v52...)",
    "DFVN West West Condensed": "Barlow Condensed ExtraBold/Black, Vietnamese-complete (references/26_dviet_fonts.md; Anton/Bebas banned by references/04: no Vietnamese)",
    "LigaSFMono": "JetBrains Mono (Vietnamese-complete); DejaVu Sans Mono is ASCII-only (dviet_motion_canvas_engine.py mono fallback list)",
    "Whisper": "SVN-Aaron Script, then Playfair Display Italic (script hero, references/26_dviet_fonts.md)",
    "Arimo": "Helvetica stand-in for the De Fonte specimen label; falls back to Inter / Be Vietnam Pro (references/26_dviet_fonts.md)",
    "Instrument Serif": "2/90 Vietnamese glyphs, so Vietnamese text goes to Playfair Display Italic (references/26_dviet_fonts.md)",
}
ENGLISH_LABELS_ONLY = {"Instrument Serif"}  # present is fine, but never route Vietnamese text to it
FILMCRAFT_CLI_SHIM = SKILL_ROOT / "scripts" / "tools" / "filmcraft_cli.py"


def _check(name: str, ok: bool, detail: str, remedy: str, required: bool = True) -> dict[str, object]:
    return {"name": name, "status": "OK" if ok else "MISSING", "required": required, "detail": detail, "remedy": "" if ok else remedy}


def _first_line(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        return ((r.stdout or r.stderr).strip().splitlines() or [""])[0]
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _font_names() -> str:
    """Lower-cased haystack of fontconfig families + font file names under the usual font dirs."""
    parts: list[str] = []
    if shutil.which("fc-list"):
        parts.append(_first_line_all(["fc-list", ":", "family", "file"]))
    for d in (HOME / ".local/share/fonts", HOME / ".fonts", Path("/usr/share/fonts"), Path("/usr/local/share/fonts")):
        if d.is_dir():
            parts.extend(p.name for p in d.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
    return "\n".join(parts).lower().replace(" ", "").replace("-", "").replace("_", "")


def _first_line_all(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _norm(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def gather() -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        checks.append(_check(tool, bool(path), path or "not on PATH", f"install ffmpeg (apt install ffmpeg) so `{tool}` is on PATH"))

    node = shutil.which("node")
    major = 0
    if node:
        m = re.match(r"v(\d+)", _first_line([node, "--version"]))
        major = int(m.group(1)) if m else 0
    checks.append(_check("node", major >= 22, f"{node or 'not found'} (major={major})", "install Node.js >= 22 (e.g. via nvm: `nvm install 22`)"))

    chrome = next((p for p in (shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")) if p), None)
    checks.append(_check("chrome", bool(chrome), chrome or "no chrome/chromium on PATH", "install Google Chrome or Chromium (needed by web_cinema_plate_engine.mjs)"))

    venv_py = VENV / "bin" / "python3"
    checks.append(_check("venv", venv_py.is_file(), str(venv_py), f"create it: python3 -m venv {VENV} && {VENV}/bin/pip install -r requirements.txt"))

    hub = HOME / ".cache" / "huggingface" / "hub"
    whisper = sorted(p.name for p in hub.glob("models--*faster-whisper-*")) if hub.is_dir() else []
    checks.append(_check("whisper_weights", bool(whisper), ", ".join(whisper) or f"none under {hub}",
                         "download once: python -c \"from faster_whisper import WhisperModel; WhisperModel('base')\" (use --skip-whisper to avoid ASR)"))

    matte = [HOME / ".rembg/models/u2netp/u2netp.onnx", HOME / ".rembg/models/birefnet-portrait/birefnet-portrait.onnx"]
    env_m = os.environ.get("PFD_MATTE_MODEL")
    found = ([Path(env_m)] if env_m and Path(env_m).is_file() else []) + [p for p in matte if p.is_file()]
    checks.append(_check("matte_model", bool(found), str(found[0]) if found else "none of: " + ", ".join(map(str, matte)),
                         "run `rembg` once (downloads u2netp / birefnet-portrait) or set PFD_MATTE_MODEL=/path/model.onnx"))

    u2netp = HOME / ".rembg/models/u2netp/u2netp.onnx"
    u2_ok = u2netp.is_file() or bool(env_m and Path(env_m).is_file())
    checks.append(_check("matte_u2netp", u2_ok, str(u2netp) if u2_ok else f"MISSING-for-studio-cutout: {u2netp} (birefnet-portrait fallback costs ~30 s/frame)",
                         f"optional: curl -L --create-dirs -o {u2netp} https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx", required=False))

    hay = _font_names()
    for fam, req in (("Be Vietnam Pro", True), ("Playfair Display", True)):
        checks.append(_check(f"font:{fam}", _norm(fam) in hay, fam, f"install {fam} into ~/.local/share/fonts and run fc-cache -f", required=req))
    for fam, fallback in FONT_FALLBACKS.items():
        ok = _norm(fam) in hay
        detail = f"{fam} (English labels only: {fallback})" if ok and fam in ENGLISH_LABELS_ONLY else fam if ok else f"{fam} (fallback: {fallback})"
        c = _check(f"font:{fam}", ok, detail, f"optional; install {fam} or rely on the documented fallback: {fallback}", required=False)
        checks.append(c)
    checks.append({"name": "fonts", "status": "OK" if all(c["status"] == "OK" for c in checks if str(c["name"]).startswith("font:") and c["required"]) else "MISSING",
                   "required": True, "detail": "Be Vietnam Pro + Playfair Display", "remedy": "install the required fonts listed above"
                   if not all(c["status"] == "OK" for c in checks if str(c["name"]).startswith("font:") and c["required"]) else ""})

    ovs = Path(os.environ["PFD_OVS_DIR"]).expanduser() if os.environ.get("PFD_OVS_DIR") else VENDOR
    needed = [ovs / "rules.json", ovs / "scripts" / "spec_lint.py", ovs / "scripts" / "audio_levels.py", ovs / "scripts" / "edit_rules.py",
              ovs / "scripts" / "fc_fast_qa.py", ovs / "scripts" / "apps" / "craft-handoff" / "tools" / "fc_build_fast.py"]
    gone = [str(p.relative_to(ovs)) for p in needed if not p.is_file()]
    checks.append(_check("ovs_core", not gone, str(ovs) if not gone else f"{ovs}: missing {', '.join(gone)}",
                         "restore scripts/vendor/ovs_core from git (see its PROVENANCE.md) or fix PFD_OVS_DIR"))

    fc = shutil.which("filmcraft") or (str(HOME / ".local/bin/filmcraft") if (HOME / ".local/bin/filmcraft").is_file() else None)
    fc_version = _first_line([fc, "--version"]) if fc else ""
    checks.append(_check("filmcraft", bool(fc), f"{fc} ({fc_version or 'no --version output'})" if fc else "`filmcraft` not found",
                         "install FilmCraft into ~/.local/bin (needed for fc_build / fc_export)"))
    x_server = next((p for p in (shutil.which("Xvfb"), shutil.which("Xephyr")) if p), None)
    parts = {"filmcraft --version": bool(fc_version), "Xvfb/Xephyr": bool(x_server), "filmcraft_cli.py": FILMCRAFT_CLI_SHIM.is_file()}
    absent = [k for k, v in parts.items() if not v]
    checks.append(_check("filmcraft_bridge", not absent,
                         f"{fc_version} + {x_server} + {FILMCRAFT_CLI_SHIM.name}" if not absent else "missing: " + ", ".join(absent) + " (1-frame render smoke is SKIPPED: no X/filmcraft)",
                         "optional: apt install xvfb (or xserver-xephyr), install FilmCraft, restore scripts/tools/filmcraft_cli.py", required=False))

    sibling = SKILL_ROOT.parent / "ffmpeg-skill"
    checks.append(_check("ffskill_bridge", (sibling / "scripts").is_dir(), str(sibling),
                         f"optional: git clone kajisho5/ffmpeg-skill to {sibling} to enable scripts/ffskill_bridge.py", required=False))
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=f"pro-filmcraft-director environment preflight (v{VERSION})")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a REQUIRED check is MISSING")
    args = ap.parse_args(argv)

    checks = gather()
    hard_missing = [c for c in checks if c["status"] == "MISSING" and c["required"]]
    if args.json:
        print(json.dumps({"version": VERSION, "ok": not hard_missing, "hard_missing": [c["name"] for c in hard_missing], "checks": checks},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[ENV STATUS v{VERSION}]")
        for c in checks:
            tag = "" if c["required"] else " (optional)"
            line = f"  {c['status']:<8} {c['name']}{tag}: {c['detail']}"
            print(line + (f"\n           -> {c['remedy']}" if c["remedy"] else ""))
        print(f"  => {'READY' if not hard_missing else 'NOT READY: ' + ', '.join(str(c['name']) for c in hard_missing)}")
    return 1 if (args.strict and hard_missing) else 0


if __name__ == "__main__":
    sys.exit(main())
