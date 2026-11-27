#!/usr/bin/env python3
"""
env_status.py (v7.9.0) — preflight of everything `pro-filmcraft-director` needs on this host.

    env_status.py [--json] [--strict]

Each check prints OK or MISSING plus a one-line remedy. Optional items (fonts with a documented fallback,
the sibling ffmpeg-skill repo) are MISSING but never fatal. FilmCraft >= 0.13.0 and an X server (Xvfb / Xephyr) are
REQUIRED: compile gates 4/5 drive FilmCraft through the vendored craftctl. The Python packages of requirements.txt are
checked by importing them, the ffmpeg encoders (libx264, prores_ks, qtrle) by name, and the default whisper model
('small') in the Hugging Face cache (HF_HUB_CACHE > HF_HOME/hub > ~/.cache/huggingface/hub). A missing u2netp is
reported as BLOCKING for Look S studio cutouts. Exit code is 1 only when `--strict` is given AND a required check is MISSING.
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
# The vendored craftctl.py declares no version; it needs `--control`, `--data-dir`, `--no-recover`, `--empty` and
# FILMCRAFT_CONTROL_TOKEN, verified on FilmCraft 0.13.0 (the oldest build known to work), so 0.13.0 is the floor.
FILMCRAFT_MIN_VERSION = (0, 13, 0)
DEFAULT_WHISPER_MODEL = "small"  # probe_and_align.py --whisper-model default
REQUIRED_IMPORTS = ("numpy", "cv2", "PIL", "onnxruntime", "scipy", "faster_whisper")  # requirements.txt, by import name
REQUIRED_ENCODERS = ("libx264", "prores_ks", "qtrle")
U2NETP_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
_IMPORT_PROBE = (
    "import importlib, json, sys\n"
    "out = {}\n"
    "for m in sys.argv[1:]:\n"
    "    try:\n"
    "        mod = importlib.import_module(m)\n"
    "        out[m] = {'ok': True, 'version': str(getattr(mod, '__version__', '?'))}\n"
    "    except Exception as e:\n"
    "        out[m] = {'ok': False, 'error': f'{type(e).__name__}: {e}'[:120]}\n"
    "if out.get('cv2', {}).get('ok'):\n"
    "    out['cv2']['cascade'] = hasattr(sys.modules['cv2'], 'CascadeClassifier')\n"
    "print(json.dumps(out))\n"
)


def _check(name: str, ok: bool, detail: str, remedy: str, required: bool = True) -> dict[str, object]:
    return {"name": name, "status": "OK" if ok else "MISSING", "required": required, "detail": detail, "remedy": "" if ok else remedy}


def _first_line(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=False)
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
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _norm(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def version_tuple(text: str) -> tuple[int, int, int] | None:
    """`filmcraft 0.13.0` -> (0, 13, 0); None when no version number is printed."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def hf_hub_dir() -> Path:
    """Hugging Face hub cache the way huggingface_hub resolves it: HF_HUB_CACHE > HF_HOME/hub > ~/.cache/huggingface/hub."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]).expanduser() / "hub"
    return HOME / ".cache" / "huggingface" / "hub"


def _python_imports(py: str) -> dict[str, dict[str, object]]:
    try:
        r = subprocess.run([py, "-c", _IMPORT_PROBE, *REQUIRED_IMPORTS], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
        return {}


def _ffmpeg_encoders() -> set[str]:
    if not shutil.which("ffmpeg"):
        return set()
    out = _first_line_all(["ffmpeg", "-hide_banner", "-encoders"])
    return {ln.split()[1] for ln in out.splitlines() if len(ln.split()) > 1 and re.fullmatch(r"[VAS.][F.][S.][X.][B.][D.]", ln.split()[0])}


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

    py = str(venv_py) if venv_py.is_file() else sys.executable
    imp = _python_imports(py)
    bad_imp = [m for m in REQUIRED_IMPORTS if not (imp.get(m) or {}).get("ok")]
    imp_detail = f"{py}: " + ", ".join(
        f"{m} {imp[m]['version']}" if (imp.get(m) or {}).get("ok") else f"{m} MISSING ({(imp.get(m) or {}).get('error', 'not importable')})"
        for m in REQUIRED_IMPORTS)
    checks.append(_check("python_imports", not bad_imp, imp_detail,
                         f"{py} -m pip install -r {SKILL_ROOT / 'requirements.txt'} (failed imports: {', '.join(bad_imp)})"))
    cv_ok = bool((imp.get("cv2") or {}).get("ok")) and bool((imp.get("cv2") or {}).get("cascade"))
    checks.append(_check("opencv_cascade", cv_ok,
                         f"cv2 {(imp.get('cv2') or {}).get('version', '?')} CascadeClassifier={'yes' if cv_ok else 'NO'} (the Haar face gate silently falls back without it)",
                         f"{py} -m pip uninstall -y opencv-python && {py} -m pip install 'opencv-python-headless>=4.9,<5' (OpenCV 5 has no CascadeClassifier)"))

    encs = _ffmpeg_encoders()
    gone_enc = [e for e in REQUIRED_ENCODERS if e not in encs]
    checks.append(_check("ffmpeg_encoders", not gone_enc, ", ".join(f"{e}={'OK' if e in encs else 'MISSING'}" for e in REQUIRED_ENCODERS),
                         "install an ffmpeg build with libx264, prores_ks and qtrle (e.g. apt install ffmpeg, or a static build from johnvansickle.com)"))

    hub = hf_hub_dir()
    whisper = sorted(p.name for p in hub.glob("models--*faster-whisper-*")) if hub.is_dir() else []
    checks.append(_check("whisper_weights", bool(whisper), ", ".join(whisper) or f"none under {hub}",
                         f"download once: python -c \"from faster_whisper import WhisperModel; WhisperModel('{DEFAULT_WHISPER_MODEL}')\" (use --skip-whisper to avoid ASR)"))
    small = sorted(hub.glob(f"models--*faster-whisper-{DEFAULT_WHISPER_MODEL}/snapshots/*/model.bin")) if hub.is_dir() else []
    checks.append(_check(f"whisper_model_{DEFAULT_WHISPER_MODEL}", bool(small), str(small[0]) if small else f"no faster-whisper-{DEFAULT_WHISPER_MODEL} model.bin under {hub}",
                         f"download the default model once: python -c \"from faster_whisper import WhisperModel; WhisperModel('{DEFAULT_WHISPER_MODEL}')\" "
                         "(honours HF_HUB_CACHE / HF_HOME; probe_and_align.py --whisper-model defaults to it)"))

    u2netp = HOME / ".rembg/models/u2netp/u2netp.onnx"
    u2_curl = f"curl -L --create-dirs -o {u2netp} {U2NETP_URL}"
    matte = [u2netp, HOME / ".rembg/models/birefnet-portrait/birefnet-portrait.onnx"]
    env_m = os.environ.get("PFD_MATTE_MODEL")
    found = ([Path(env_m)] if env_m and Path(env_m).is_file() else []) + [p for p in matte if p.is_file()]
    checks.append(_check("matte_model", bool(found), str(found[0]) if found else "none of: " + ", ".join(map(str, matte)),
                         f"{u2_curl} (or set PFD_MATTE_MODEL=/path/model.onnx)"))

    u2_ok = u2netp.is_file() or bool(env_m and Path(env_m).is_file())
    u2 = _check("matte_u2netp", u2_ok, str(u2netp) if u2_ok else f"BLOCKING for Look S studio cutouts: {u2netp} is missing (birefnet-portrait fallback costs ~30 s/frame)",
                f"required for Look S studio cutouts: {u2_curl}", required=False)
    if not u2_ok:
        u2["blocking_for"] = "Look S studio cutouts"
    checks.append(u2)

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

    min_v = ".".join(map(str, FILMCRAFT_MIN_VERSION))
    craft_bin = Path(os.environ.get("CRAFT_BIN_DIR") or HOME / ".local/bin") / "filmcraft"  # the exact binary craftctl starts
    fc = str(craft_bin) if craft_bin.is_file() else None
    fc_version = _first_line([fc, "--version"]) if fc else ""
    fc_v = version_tuple(fc_version)
    fc_ok = bool(fc) and fc_v is not None and fc_v >= FILMCRAFT_MIN_VERSION
    on_path = shutil.which("filmcraft")
    fc_detail = (f"{fc} ({fc_version or 'no --version output'}; need >= {min_v})" if fc
                 else f"{craft_bin} not found (need FilmCraft >= {min_v})" + (f"; {on_path} is on PATH but craftctl only runs $CRAFT_BIN_DIR/filmcraft" if on_path else ""))
    checks.append(_check("filmcraft", fc_ok, fc_detail,
                         f"install FilmCraft >= {min_v} into ~/.local/bin (or set CRAFT_BIN_DIR): compile gates 4/5 drive it via craftctl"))
    x_server = next((p for p in (shutil.which("Xvfb"), shutil.which("Xephyr")) if p), None)
    checks.append(_check("x_server", bool(x_server), x_server or "neither Xvfb nor Xephyr on PATH",
                         "apt install xvfb (or xserver-xephyr): craftctl starts FilmCraft on its own display ($CRAFT_DISPLAY, default :93)"))
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
        print(json.dumps({"version": VERSION, "ok": not hard_missing, "hard_missing": [c["name"] for c in hard_missing],
                          "blocking": {c["name"]: c["blocking_for"] for c in checks if c.get("blocking_for")}, "checks": checks},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[ENV STATUS v{VERSION}]")
        for c in checks:
            tag = "" if c["required"] else (" (optional for compile)" if c.get("blocking_for") else " (optional)")
            line = f"  {c['status']:<8} {c['name']}{tag}: {c['detail']}"
            print(line + (f"\n           -> {c['remedy']}" if c["remedy"] else ""))
        print(f"  => {'READY' if not hard_missing else 'NOT READY: ' + ', '.join(str(c['name']) for c in hard_missing)}")
        for c in (c for c in checks if c.get("blocking_for")):
            print(f"  => BLOCKED for {c['blocking_for']}: {c['name']}")
    return 1 if (args.strict and hard_missing) else 0


if __name__ == "__main__":
    sys.exit(main())
