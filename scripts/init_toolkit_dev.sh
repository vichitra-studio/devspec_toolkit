#!/bin/bash
set -eo pipefail

# Initialize the devspec toolkit repository itself for development.
#
# This is the toolkit-internal counterpart to init_project.py (which bootstraps a
# *host* repo). It reuses setup_devspec_env.sh as the env primitive (uv-managed
# CPython 3.13 + editable install) and layers on the toolkit-dev extras: the dev
# tooling (pytest + pre-commit) and the git pre-commit hooks.
#
# Run from the toolkit repo root:
#   bash scripts/init_toolkit_dev.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Anchor to the toolkit repo root (parent of scripts/) so the venv and all relative
# paths below resolve correctly no matter where this script is invoked from.
cd "${SCRIPT_DIR}/.."

# 1. uv-managed Python 3.13 venv + editable toolkit install (deps from pyproject)
bash "${SCRIPT_DIR}/setup_devspec_env.sh"

# 2. Install dev tooling (pytest + pre-commit) from the [dev] extra and wire up
#    the git hooks. pyproject.toml is the single source of truth for dev deps.
# shellcheck disable=SC1091
source devspec_env/bin/activate
echo "Installing dev tooling (pytest, pre-commit) from the [dev] extra..."
uv pip install -e "./tools[dev]"
echo "Installing git pre-commit hooks..."
pre-commit install

# 3. Smoke test — prove the CLI works and the fast unit tests pass.
echo "Running smoke test..."
specdev --help >/dev/null && echo "specdev CLI OK"
python -m pytest tests/unit/ -q --tb=short

echo ""
echo "Toolkit dev environment ready. Activate with:"
echo "  source devspec_env/bin/activate"
