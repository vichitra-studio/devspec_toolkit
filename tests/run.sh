
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
echo "[1/4] validate-all"
python3 -m specdev_tools.cli validate-all "$ROOT/spec" --repo-root "$ROOT"
echo "[2/4] fixtures-lint"
python3 -m specdev_tools.cli fixtures-lint "$ROOT/spec" --repo-root "$ROOT"
echo "[3/4] matrix"
python3 -m specdev_tools.cli matrix "$ROOT/spec" --repo-root "$ROOT" --out "$ROOT/tests/.matrix.out.json"
echo "[4/4] invariants-check"
python3 -m specdev_tools.cli invariants-check "$ROOT/spec" --repo-root "$ROOT" --sample "$ROOT/tests/samples/invariants/password_ok.json" > "$ROOT/tests/.invariants.out.json"
echo "Done. Outputs:"
ls -1 "$ROOT/tests"/.matrix.out.json "$ROOT/tests"/.invariants.out.json
