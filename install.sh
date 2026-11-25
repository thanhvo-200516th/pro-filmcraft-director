#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="pro-filmcraft-director"

echo "=== Installing ${SKILL_NAME} (v7.3.0) ==="

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
for BIN in ffmpeg ffprobe node; do
  if command -v "$BIN" >/dev/null 2>&1; then
    echo "[OK] Found $BIN: $(command -v "$BIN")"
  else
    echo "[WARN] Missing $BIN in PATH — install before rendering 60fps plates."
  fi
done

# 4. Run v7.3 self-test suite
"$VENV_PY" "$SKILL_DIR/tests/test_skill_v73.py"
echo "=== ${SKILL_NAME} v7.3.0 installed & verified! ==="
