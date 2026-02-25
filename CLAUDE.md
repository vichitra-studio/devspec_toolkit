# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The **AI Spec Driven Development Toolkit** is a schema-first, AI-assisted workflow that turns spec → implementation into a deterministic pipeline. It is typically vendored as a git submodule at `<product-repo>/devspec_toolkit/` beside the host repo's live `spec/` directory.

Current version: **0.2.2** (see `tools/pyproject.toml`). Specs track the toolkit version they were written against in `spec/specdev_version`.

---

## Environment Setup

```bash
# After init_project.py has run, activate the virtualenv:
source dev_env/bin/activate

# Or install manually:
pip install -r devspec_toolkit/tools/requirements.txt
pip install -e ./devspec_toolkit/tools
```

All CLI commands must go through `./tools/run_specdev.sh` — never call internal modules directly. The wrapper enforces virtualenv usage and applies schema registry resolution. It works without activating the venv first.

**Critical flag**: always pass `--repo-root ./devspec_toolkit` when running from the host repo so the schema registry in the toolkit resolves correctly. The locked `spec_dir` for this repo is `devspec_toolkit/spec` (not a top-level `spec/`).

---

## Core CLI Commands

```bash
# Validation
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

# Traceability & fixtures
./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit

# Seed and docs enforcement
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh docs-lint spec --repo-root ./devspec_toolkit

# Invariants & Governance
./tools/run_specdev.sh invariants-check spec --repo-root ./devspec_toolkit --sample ./path/to/sample.json
./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): add login [fr-initial-login]"

# Quality, hallucination, and canonical integrity
./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit

# Step-order integrity
./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit
./tools/run_specdev.sh forward-replay-check --repo-root ./devspec_toolkit --base-ref origin/main

# Prompt workflow reminder
./tools/run_specdev.sh ai-help --step 04

# Changelog
./tools/run_specdev.sh changelog --list --repo-root ./devspec_toolkit
./tools/run_specdev.sh changelog --validate 0.1.0 --repo-root ./devspec_toolkit
```

### Alignment & Migration

```bash
specdev align status --spec-dir spec
specdev align diff --spec-dir spec
specdev align plan --spec-dir spec
specdev align apply --spec-dir spec --auto
specdev align prompts --spec-dir spec --output prompts/migration/ --mode upgrade
```

### Running Tests

```bash
# Full test suite (from toolkit root with venv active)
pytest tests/

# Single test file
pytest tests/test_canonical_integrity.py

# Step-specific integration tests
python devspec_toolkit/tests/integration/test_step_02.py spec/02_system_sketch.json
python devspec_toolkit/tests/integration/test_step_12.py tests/fixtures/step_12/valid_dag.json
python devspec_toolkit/tests/integration/test_step_15.py tests/fixtures/step_15/valid_full.json
```

Set `SPECDEV_WARNINGS_AS_ERRORS=1` to promote warning-level messages to errors.

---

## Architecture

### Spec Pipeline (Steps 00–16c)

The workflow is a **strict forward-only waterfall**. Any upstream change requires full replay of all downstream steps. Steps are numbered: `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 13a 14 15 16 16a 16b 16c`.

| Phase | Steps | Purpose |
|---|---|---|
| Phase 0 | Seed docs | `seed_overview.md` + `seed_tech_stack.md` before any formal specs |
| Phase I · Discovery | 00–12 | Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates |
| Phase II · Impl | 13–16c | Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review) |

Artifacts live in `spec/NN_name.json`; human guides in `spec/NN_name.guide.md`. Prompts for AI assistants live in `prompts/prompt_NN_name.md`.

### Key Directories

- `schema/` — JSON Schemas for every step plus `schema/core/` (atoms, collections, errors shared across steps)
- `canon/` — Canonical registry (`manifest.json`, `aliases.json`) for shared vocabulary: units, stages, environments, roles, NFR categories, trace types, owners, etc. Referenced by canonical-lint and canonical-integrity checks.
- `tools/specdev_tools/` — Python CLI package; entry point at `cli.py`, one module per linting/validation command
- `tools/schema_registry.json` — Maps step names to their JSON Schema paths
- `tools/step_order.json` — Defines the strict waterfall dependency DAG
- `tools/trace_matrix.json` — Generated cross-artifact traceability matrix (FR ↔ API ↔ fixture ↔ NFR)
- `prompts/` — Deterministic prompt contracts for each step (consumed by AI runners)
- `tests/` — pytest suite; `tests/fixtures/` has per-step valid/invalid JSON fixtures; `tests/integration/` has step-level scripts
- `scripts/init_project.py` — Bootstraps a new host repo (venv, submodule, dirs, CI, hooks)

### Naming Conventions

- IDs: kebab-case only (`fr-user-login`, `api-session-create`)
- Owner enum: `api | ui | system | ops | data | product | business | engineering`
- All artifacts must include the canonical `$schema` URI as emitted by the matching prompt
- Reuse atoms/collections/errors from `schema/core/` — never redefine primitives

### Two-Phase AI Runner Protocol

Prompts support **Clarify → Emit**:
1. **Clarify**: if `Self-Audit Gate` score < 0.9, output only short bulleted gap questions (no JSON, no code fences). Group by field/topic. Stop and wait.
2. **Emit**: write artifact JSON directly to `spec/NN_name.json`. Do not return fenced JSON as primary output. Populate `seed_refs` from actually-used seeds.

Agent protocol metadata lives in `docs/agents/manifest.json`.

### Validation Ritual (after any spec edit)

1. `validate` the changed artifact
2. `seed-lint` to verify seed refs are current
3. `docs-lint` for README coverage
4. If traceability changed: regenerate `matrix` and run `fixtures-lint`
5. Governance-compliant commit message per `spec/10_governance.json`

---

## Troubleshooting

- **Schema not found**: run from repo root; confirm `--repo-root` points to toolkit; check `tools/schema_registry.json`
- **Unknown Target in fixtures**: ensure the target ID (`fr-*`, `api-*`, `nfr-*`, `inv-*`) exists in its spec file
- **Governance rejection**: match commit pattern from Step 10; `pr_rules` must use allowed enum values
- **Step 11 failures**: `target_ids` must target an API or Component; `mitigations` must be structured objects, not strings
- **Step 15 failures**: `method` must be one of GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD; no duplicate `api_ref`
- **Glossary failures**: `terms` needs ≥1 item; definitions >20 chars; `domain` is kebab-case; no empty strings
- **Step 09 failures**: `tech_stack` must be an object (not array); `milestones` need a `deliverables` array
