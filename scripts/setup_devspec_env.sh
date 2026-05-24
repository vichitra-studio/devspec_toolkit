#!/bin/bash
set -eo pipefail

# Setup script for the devspec toolkit virtual environment.
#
# Uses `uv` to provision a managed CPython 3.13 interpreter and an isolated
# virtualenv. Python 3.13 is REQUIRED on Apple Silicon: the toolkit depends on
# cel-python, whose `google-re2` dependency has no arm64-macOS wheel and fails
# to build from source — but cel-python drops google-re2 on Python 3.13/arm64
# macOS (per its dependency markers) and falls back to the stdlib `re` engine.
# The managed interpreter lives under uv's user-local cache (~/.local/share/uv),
# never the system Python, so nothing is installed system-wide.

echo "Setting up devspec toolkit environment (uv-managed)..."

# --- locate the toolkit 'tools/' dir (host submodule layout OR toolkit-internal) ---
if [ -d "./devspec_toolkit/tools" ]; then
    TOOLS_DIR="./devspec_toolkit/tools"          # host repo: toolkit vendored at ./devspec_toolkit
elif [ -d "./tools/specdev_tools" ]; then
    TOOLS_DIR="./tools"                          # running from inside the toolkit itself
else
    echo "ERROR: cannot find the toolkit 'tools/' dir (looked for ./devspec_toolkit/tools and ./tools)." >&2
    echo "Run this from your host repo root (toolkit vendored at ./devspec_toolkit) or from the toolkit root." >&2
    exit 1
fi
echo "Using toolkit tools dir: ${TOOLS_DIR}"

# --- require uv (user-local Python manager; no system Python needed) ---
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: 'uv' is not installed. Install it (user-local; does not touch system Python):" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "  (or: brew install uv)" >&2
    exit 1
fi

# --- provision managed CPython 3.13 (idempotent; lands in uv's user cache) ---
echo "Provisioning CPython 3.13 via uv..."
uv python install 3.13

# --- (re)create the virtualenv on the managed interpreter ---
# If an env already exists but is NOT Python 3.13 (e.g. left over from an older
# system-Python setup), rebuild it. Reusing a non-3.13 env would make the
# `uv pip install` step pull the unbuildable google-re2 on arm64 macOS,
# defeating the entire purpose of this script.
NEED_VENV=1
if [ -d "devspec_env" ]; then
    EXISTING_PY=$(devspec_env/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
    if [ "$EXISTING_PY" = "3.13" ]; then
        echo "Virtual environment 'devspec_env' already exists on Python 3.13 (reusing)."
        NEED_VENV=0
    else
        echo "Existing 'devspec_env' is Python ${EXISTING_PY}, not 3.13 — rebuilding."
        rm -rf devspec_env
    fi
fi
if [ "$NEED_VENV" -eq 1 ]; then
    echo "Creating virtual environment 'devspec_env' on Python 3.13..."
    uv venv devspec_env --python 3.13
fi

# shellcheck disable=SC1091
source devspec_env/bin/activate

# --- install dependencies + the toolkit (editable) into the venv ---
echo "Installing toolkit dependencies..."
uv pip install -r "${TOOLS_DIR}/requirements.txt"
echo "Installing devspec toolkit (editable)..."
uv pip install -e "${TOOLS_DIR}"

# --- verify ---
echo "Verifying installation..."
python -c "import specdev_tools, celpy; print('specdev_tools + celpy available')"
specdev --help >/dev/null && echo "specdev CLI OK"

echo ""
echo "Setup complete. Activate with:"
echo "  source devspec_env/bin/activate"
echo "Then run, e.g.:"
echo "  specdev --help"
