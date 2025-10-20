
#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tests/run.sh [--repo-root <toolkit-root>] [--spec-dir <spec-dir>]

Options:
  --repo-root  Path to the devspec toolkit root (defaults to the script parent directory).
  --spec-dir   Path to the directory containing spec JSON artifacts (defaults to sibling spec/ when available).
  -h, --help   Show this help and exit.
EOF
}

to_abs() {
  python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TOOLKIT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
toolkit_root="$DEFAULT_TOOLKIT_ROOT"
spec_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --repo-root"; usage; exit 1; }
      toolkit_root="$(to_abs "$1")"
      ;;
    --spec-dir)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --spec-dir"; usage; exit 1; }
      spec_dir="$(to_abs "$1")"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

toolkit_root="$(to_abs "$toolkit_root")"

if [[ -z "$spec_dir" ]]; then
  if [[ -d "$toolkit_root/spec" ]]; then
    spec_dir="$(to_abs "$toolkit_root/spec")"
  else
    parent_dir="$(cd "$toolkit_root/.." && pwd)"
    if [[ -d "$parent_dir/spec" ]]; then
      spec_dir="$(to_abs "$parent_dir/spec")"
    else
      echo "Could not determine spec directory. Provide it explicitly with --spec-dir."
      exit 1
    fi
  fi
fi

spec_parent="$(cd "$spec_dir/.." && pwd)"
out_dir="$spec_parent/tests"
mkdir -p "$out_dir"

matrix_out="$spec_parent/tools/trace_matrix.json"
mkdir -p "$(dirname "$matrix_out")"
invariants_out="$out_dir/.invariants.out.json"
invariants_sample="$toolkit_root/tests/samples/invariants/password_ok.json"

echo "[1/4] validate-all"
python3 -m specdev_tools.cli validate-all "$spec_dir" --repo-root "$toolkit_root"
echo "[2/4] fixtures-lint"
python3 -m specdev_tools.cli fixtures-lint "$spec_dir" --repo-root "$toolkit_root"
echo "[3/4] matrix"
python3 -m specdev_tools.cli matrix "$spec_dir" --repo-root "$toolkit_root" --out "$matrix_out"
echo "[4/4] invariants-check"
python3 -m specdev_tools.cli invariants-check "$spec_dir" --repo-root "$toolkit_root" --sample "$invariants_sample" > "$invariants_out"
echo "Done. Outputs:"
ls -1 "$matrix_out" "$invariants_out"
