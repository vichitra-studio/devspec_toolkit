#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT}/dev_env"

PY_BIN=""
if [[ -x "${VENV_DIR}/bin/python3" ]]; then
  PY_BIN="${VENV_DIR}/bin/python3"
elif [[ -x "${VENV_DIR}/bin/python" ]]; then
  PY_BIN="${VENV_DIR}/bin/python"
elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
  PY_BIN="${VENV_DIR}/Scripts/python.exe"
elif [[ -x "${VENV_DIR}/Scripts/python" ]]; then
  PY_BIN="${VENV_DIR}/Scripts/python"
fi

if [[ -z "${PY_BIN}" ]]; then
  echo "Error: dev_env virtual environment not found. Run 'python3 devspec_toolkit/scripts/init_project.py --target .' first." >&2
  exit 1
fi

"${PY_BIN}" "${ROOT}/tools/ensure_venv.py"
exec "${PY_BIN}" -m specdev_tools.cli "$@"
