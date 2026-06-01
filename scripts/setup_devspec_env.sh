#!/bin/bash
set -eo pipefail

# Setup script for the devspec toolkit virtual environment.
#
# Uses `uv` to provision a managed CPython 3.13 interpreter and an isolated
# virtualenv. Python 3.13 is REQUIRED: the toolkit depends on cel-python, which
# pulls in google-re2 (a native extension). google-re2 only ships prebuilt wheels
# for cp313 (including macOS arm64); on older interpreters there is no arm64 wheel,
# so the install falls back to a source build that needs abseil headers and fails.
# Running on 3.13 takes the prebuilt-wheel path and sidesteps the build entirely.
# The managed interpreter lives under uv's user-local cache (~/.local/share/uv),
# never the system Python, so nothing is installed system-wide.
#
# Usage:
#   setup_devspec_env.sh [--tools-dir DIR] [--venv-name NAME]
#     --tools-dir DIR    Path to the toolkit 'tools/' dir (default: auto-detect)
#     --venv-name NAME   Name of the virtualenv to create (default: devspec_env)

TOOLS_DIR=""
VENV_NAME="devspec_env"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --tools-dir)
            TOOLS_DIR="$2"; shift 2 ;;
        --venv-name)
            VENV_NAME="$2"; shift 2 ;;
        *)
            echo "ERROR: unknown argument '$1'" >&2
            echo "Usage: $0 [--tools-dir DIR] [--venv-name NAME]" >&2
            exit 1 ;;
    esac
done

echo "Setting up devspec toolkit environment (uv-managed)..."

# --- locate the toolkit 'tools/' dir (only when not provided explicitly) ---
if [ -z "$TOOLS_DIR" ]; then
    if [ -d "./devspec_toolkit/tools" ]; then
        TOOLS_DIR="./devspec_toolkit/tools"      # host repo: toolkit vendored at ./devspec_toolkit
    elif [ -d "./tools/specdev_tools" ]; then
        TOOLS_DIR="./tools"                      # running from inside the toolkit itself
    else
        echo "ERROR: cannot find the toolkit 'tools/' dir (looked for ./devspec_toolkit/tools and ./tools)." >&2
        echo "Run this from your host repo root (toolkit vendored at ./devspec_toolkit) or from the toolkit root," >&2
        echo "or pass --tools-dir explicitly." >&2
        exit 1
    fi
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
# system-Python setup), rebuild it. Reusing a non-3.13 env would make the install
# step pull the unbuildable google-re2 source dist on arm64 macOS, defeating the
# entire purpose of this script.
NEED_VENV=1
if [ -d "${VENV_NAME}" ]; then
    EXISTING_PY=$("${VENV_NAME}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
    if [ "$EXISTING_PY" = "3.13" ]; then
        echo "Virtual environment '${VENV_NAME}' already exists on Python 3.13 (reusing)."
        NEED_VENV=0
    else
        echo "Existing '${VENV_NAME}' is Python ${EXISTING_PY}, not 3.13 — rebuilding."
        rm -rf "${VENV_NAME}"
    fi
fi
if [ "$NEED_VENV" -eq 1 ]; then
    echo "Creating virtual environment '${VENV_NAME}' on Python 3.13..."
    uv venv "${VENV_NAME}" --python 3.13
fi

# shellcheck disable=SC1091
source "${VENV_NAME}/bin/activate"

# --- install the toolkit (editable) + its dependencies into the venv ---
# pyproject.toml is the single source of truth for dependencies; the editable
# install resolves them (no separate requirements.txt).
echo "Installing devspec toolkit (editable) + dependencies..."
uv pip install -e "${TOOLS_DIR}"

# --- verify ---
echo "Verifying installation..."
python -c "import specdev_tools, celpy; print('specdev_tools + celpy available')"
specdev --help >/dev/null && echo "specdev CLI OK"

echo ""
echo "Setup complete. Activate with:"
echo "  source ${VENV_NAME}/bin/activate"
echo "Then run, e.g.:"
echo "  specdev --help"
