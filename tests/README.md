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

- Export `PYTHONPATH` as described in [`docs/developers/getting_started.md`](../docs/developers/getting_started.md#1-set-up-your-environment).
- Run the [core validation commands](../docs/developers/reference.md#core-validation-commands), then compare `tools/trace_matrix.json` against `tests/expectations/trace_matrix.json` (e.g., `diff -u ... || true`).
- Evaluate invariants when needed: `python -m specdev_tools.cli invariants-check spec --repo-root ./devspec_toolkit --sample ./devspec_toolkit/tests/samples/invariants/password_ok.json`.
- Execute the bundled smoke tests: `./devspec_toolkit/tests/unit`.
- Run the validation suite wrapper: `./devspec_toolkit/tests/run.sh --repo-root ./devspec_toolkit [--spec-dir <path-to-spec>]`.
