#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="pro-filmcraft-director"

echo "=== Installing ${SKILL_NAME} (v7.9.0) ==="

# Requirements (checked below and by scripts/env_status.py):
#   System (required): FilmCraft >= 0.13.0 in ~/.local/bin (or $CRAFT_BIN_DIR; compile gates 4/5 drive it via craftctl),
#   Xvfb or Xephyr (apt install xvfb), node >= 22, Chrome/Chromium (headless), ffmpeg + ffprobe with libx264 / prores_ks / qtrle,
#   a matte model (u2netp for Look S studio cutouts, or birefnet-portrait under ~/.rembg/models, or PFD_MATTE_MODEL=/path/model.onnx).
#   Python 3.10+ with requirements.txt (opencv-python-headless 4.x).

# 1. Symlink into Antigravity (~/.gemini/config/skills) & Claude (~/.claude/skills)
for TARGET_ROOT in "$HOME/.gemini/config/skills" "$HOME/.claude/skills"; do
  mkdir -p "$TARGET_ROOT"
  LINK_PATH="$TARGET_ROOT/$SKILL_NAME"
  if [ -L "$LINK_PATH" ] || [ ! -e "$LINK_PATH" ]; then
    ln -sfn "$SKILL_DIR" "$LINK_PATH"
    echo "[OK] Linked $LINK_PATH -> $SKILL_DIR"
  else
    echo "[SKIP] $LINK_PATH exists as a real directory; keeping existing directory."
  fi
done

# 2. Verify Python venv or current Python
VENV_PY="${FILMCRAFT_VENV_PYTHON:-$HOME/.venvs/video-skills/bin/python3}"
if [ ! -x "$VENV_PY" ]; then
  VENV_PY="$(command -v python3)"
fi
echo "[INFO] Using Python: $VENV_PY"

# 3. Verify core binaries
for BIN in ffmpeg ffprobe node Xvfb; do
  if command -v "$BIN" >/dev/null 2>&1; then
    echo "[OK] Found $BIN: $(command -v "$BIN")"
  else
    echo "[WARN] Missing $BIN in PATH — install before rendering 60fps plates."
  fi
done

# 3b. Node must be >= 22 (web_cinema_plate_engine.mjs)
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  if [ "${NODE_MAJOR:-0}" -ge 22 ]; then
    echo "[OK] node v${NODE_MAJOR} (>= 22)"
  else
    echo "[WARN] node v${NODE_MAJOR} is older than 22 — web plates will not render."
  fi
fi

# 3c. Chrome / Chromium (headless) for web plates
CHROME_BIN=""
for CAND in google-chrome google-chrome-stable chromium chromium-browser chrome; do
  if command -v "$CAND" >/dev/null 2>&1; then CHROME_BIN="$(command -v "$CAND")"; break; fi
done
if [ -n "$CHROME_BIN" ]; then
  echo "[OK] Found Chrome/Chromium: $CHROME_BIN"
else
  echo "[WARN] No Chrome/Chromium in PATH — web_cinema_plate_engine.mjs needs one."
fi

# 3d. FilmCraft (craftctl runs $CRAFT_BIN_DIR/filmcraft, default ~/.local/bin/filmcraft)
FC_BIN="${CRAFT_BIN_DIR:-$HOME/.local/bin}/filmcraft"
if [ -x "$FC_BIN" ]; then
  echo "[OK] Found FilmCraft: $FC_BIN ($("$FC_BIN" --version 2>/dev/null | head -n 1))"
else
  echo "[WARN] Missing $FC_BIN — install FilmCraft >= 0.13.0 (compile gates 4/5 need it)."
fi

# 4. Preflight: env_status (node >= 22, Chrome, ffmpeg, matte model, fonts). Informational here; use --strict in CI.
"$VENV_PY" "$SKILL_DIR/scripts/env_status.py" || echo "[WARN] env_status reported problems — see the remedies above."

# 5. Run v7.9.0 self-test suites (per-test wall-clock limit: PFD_TEST_TIMEOUT seconds, default 900)
TEST_TIMEOUT="${PFD_TEST_TIMEOUT:-900}"
for t in "$SKILL_DIR"/tests/test_*.py; do
  echo "== $(basename "$t")"
  if command -v timeout >/dev/null 2>&1; then
    timeout "$TEST_TIMEOUT" "$VENV_PY" "$t"
  else
    "$VENV_PY" "$t"
  fi
done
echo "=== ${SKILL_NAME} v7.9.0 installed & verified! ==="
