# Project Context: devspec_toolkit

## What This Is
AI Spec Driven Development Toolkit — schema-first, AI-assisted workflow turning spec → implementation into a deterministic pipeline. Vendored as git submodule at `<product-repo>/devspec_toolkit/`.

## Environment
- Virtualenv: `devspec_env` — activate with `source devspec_env/bin/activate`
- All CLI commands through `./tools/run_specdev.sh` — never call internal modules directly
- Pass `--repo-root ./devspec_toolkit` when running from host repo

## Test Command
```bash
pytest tests/
```
Run from toolkit root with venv active.

## Key Directories
- `schema/` — JSON Schemas for every step + `schema/core/` (atoms, collections, errors)
- `canon/` — Canonical registry (manifest.json, aliases.json)
- `tools/specdev_tools/` — Python CLI package
  - `core/` — errors, registry, trace_types, etc.
  - `validation/` — validate, validators/, linters
  - `generation/` — prompt_generator, prompt_schema_sync
  - `canonical/` — autofix, integrity, lint, registry
- `tools/schema_registry.json` — Maps step names to JSON Schema paths
- `tools/step_order.json` — Strict waterfall dependency DAG
- `prompts/` — Deterministic prompt contracts for each step
- `tests/` — pytest suite; `tests/fixtures/` has per-step valid/invalid JSON fixtures
- `docs/` — Architecture docs, audit findings, plans

## Architecture Principles
- Strict forward-only waterfall: steps 00–16c in order
- derive_allowed_upstream() derives upstream deps from positional ordering (replaced hardcoded field)
- E599 DAG_CONSUMER_INCONSISTENCY was removed (tautologically true post-derivation)
- Three-way consistency: schema enums = validator constants = prompt documentation
- Mirror test files (test_r9_*.py) must stay identical to canonical counterparts

## Commit Format
Conventional commits: feat/fix/chore/docs/test(scope): description
