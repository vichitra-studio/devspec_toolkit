# tests/ (v3 full)

This directory contains **data-first** tests that are consumed by the AI Spec Driven Development CLI. It focuses on fixtures and deterministic checks rather than framework-specific unit tests.

## Layout

```
tests/
├─ README.md
├─ run.sh
├─ fixtures/
│  └─ login/
│     ├─ success.json
│     └─ fail.json
├─ samples/
│  └─ invariants/
│     └─ password_ok.json
└─ expectations/
   └─ trace_matrix.json
```

- `fixtures/` holds request/response pairs referenced by `05_interface_contracts.json` (`example_refs`) and validated during Step 14.
- `samples/invariants/` contains minimal contexts used by `invariants-check` (Step 6).
- `expectations/trace_matrix.json` captures expected FR→API→Fixture→NFR wiring for quick drift detection.

## Guardrails

- Filenames are **kebab/underscore**; IDs remain **kebab-case** inside JSON.
- No schema redefinition. All validation relies on `$schema` in spec artifacts and the registry in `tools/`.
- Keep payloads minimal but **falsifiable**. Add red-team cases under `fixtures/<feature>/...` and update `spec/15_redteam_loop.json` accordingly.

## Quick commands

From your host repo root (adjust `./devspec_toolkit` if the toolkit lives elsewhere):

```bash
# Add the toolkit to PYTHONPATH (adjust the path if needed)
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

# Validate specs first
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit

# Lint fixtures structure and targets
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit

# Build trace matrix and compare to expectations (manual diff)
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out /tmp/matrix.json && diff -u tests/expectations/trace_matrix.json /tmp/matrix.json || true

# Evaluate invariants against sample context
python -m specdev_tools.cli invariants-check spec --repo-root ./devspec_toolkit --sample tests/samples/invariants/password_ok.json

# Run bundled CLI smoke tests against example artifacts
./tests/unit
```
