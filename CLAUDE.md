# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The **AI Spec Driven Development Toolkit** is a schema-first, AI-assisted workflow that turns spec → implementation into a deterministic pipeline. It is typically vendored as a git submodule at `<product-repo>/devspec_toolkit/` beside the host repo's live `spec/` directory.

Current version: **0.5.1** (see `tools/pyproject.toml`). Specs track the toolkit version they were written against in `spec/specdev_version`.

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

**Critical flag**: always pass `--repo-root ./devspec_toolkit` when running from the host repo so the schema registry in the toolkit resolves correctly. The host repo's live specs live at `./spec/` — pass that as the positional `<spec_dir>` argument.

---

## Querying Spec Artifacts

**NEVER read `spec/*.json` files directly** using the Read tool, `cat`, or ad-hoc scripts. Always use the `specdev-context` skill to load context for a pipeline step before any spec-related work (authoring, reviewing, analysing, debugging).

```
/specdev-context <NN>                     # load upstream context for step NN
/specdev-context <NN> --full              # bypass scope filtering
/specdev-context <NN> --scope <entry-id>  # scope to IDs reachable from a specific entry
```

The skill runs `context structure`, `context extract`, and `context canon` in sequence and loads all upstream data into working context. Direct file reads bypass schema-aware extraction, miss cross-step dependencies, and risk acting on stale or partial data.

### Viewing a step's own output artifact

To analyse the artifact a step *produced* (not its upstream inputs), use `context review`:

```bash
./tools/run_specdev.sh context review spec/03_glossary.json --step 03 --repo-root ./devspec_toolkit
```

This runs a two-pass structural + semantic review of the emitted artifact.

For targeted field reads without a full review, use `json read-multi`:

```bash
# Read several fields in one pass — output is a keyed JSON object
# Each filter must return a single value; streaming filters (.arr[]) are rejected
./tools/run_specdev.sh json read-multi spec/03_glossary.json '.terms | length' '.id' '.owner'

# Read by array index
./tools/run_specdev.sh json read spec/03_glossary.json '.terms[2]'

# Read with select() filter (streams all matching items) — use json read, not read-multi
./tools/run_specdev.sh json read spec/03_glossary.json '.terms[] | select(.domain == "analytics")'

# Tree overview — no field content, just structure
./tools/run_specdev.sh json structure spec/03_glossary.json
```

### Project-tier canon in context

`context canon` now merges project-scoped terms (from `spec/canon/`) alongside toolkit core terms when `--spec-root` is provided:

```bash
./tools/run_specdev.sh context canon --step 03 --repo-root ./devspec_toolkit --spec-root ./spec
```

Without `--spec-root`, only toolkit-core entries (units, owners, etc.) are returned.

---

## Core CLI Commands

```bash
# Unified check (recommended after generating any spec artifact)
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit
# For submodule deployments:
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Single-file validation (for iterative editing)
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

# Traceability & fixtures
./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit

# Seed enforcement
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh seed-index spec --repo-root ./devspec_toolkit

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

# DAG completeness lint (validates downstream_consumers consistency)
./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit

# Extraction intent validation (prompts vs step_order.json)
./tools/run_specdev.sh extraction-intent-check --repo-root ./devspec_toolkit

# Workspace snapshot and diff (no git commit required)
./tools/run_specdev.sh context snapshot spec --step 03 --repo-root ./devspec_toolkit   # save checkpoint
./tools/run_specdev.sh context diff spec --step 03 --repo-root ./devspec_toolkit       # diff vs checkpoint
# Snapshots are stored in .specdev/snapshots/; add .specdev/ to .gitignore if desired.

# Environment diagnostic (read-only — prints active SPECDEV_* config)
./tools/run_specdev.sh env-check --repo-root ./devspec_toolkit

# Prompt workflow reminder
./tools/run_specdev.sh ai-help --step 04

# Canonical autofix (apply canonical corrections to spec files)
./tools/run_specdev.sh canonical-autofix spec --repo-root ./devspec_toolkit --dry-run
./tools/run_specdev.sh canonical-autofix spec --repo-root ./devspec_toolkit --write

# Traceability closure check
./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit --json

# Prompt context (show downstream consumers for a step)
./tools/run_specdev.sh prompt-context 04 --repo-root ./devspec_toolkit

# Canon-schema alignment check
./tools/run_specdev.sh canon-schema-alignment --repo-root ./devspec_toolkit

# Prompt-schema sync validation
./tools/run_specdev.sh prompt-sync spec --repo-root ./devspec_toolkit

# Changelog
./tools/run_specdev.sh changelog --list --repo-root ./devspec_toolkit
./tools/run_specdev.sh changelog --validate 0.4.0 --repo-root ./devspec_toolkit

# Canon management
# Run after generating Step 03 glossary to promote project-specific terms to the canon registry.
./tools/run_specdev.sh canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit --namespace cn:project: --owner product
```

> **JSON output**: All CLI commands accept `--json` for structured JSON output with `status`, `error_count`, `warning_count`, and `errors` array. Example: `./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit --json`

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

# Integration tests
pytest tests/integration/ -v
```

### Environment Variables

| Variable | Effect |
|----------|--------|
| `SPECDEV_WARNINGS_AS_ERRORS=1` | Promotes all 22 warning codes with E-code counterparts to errors |
| `SPECDEV_PROMOTE_CODES=W571,W593` | Selective promotion — only the listed W-codes are promoted to their E-code counterparts |
| `SPECDEV_MATRIX_STRICT=1` | Makes matrix coverage errors fatal (exit non-zero) |
| `SPECDEV_REPLAY_BASE_REF=<ref>` | Override the base ref for forward-replay diff detection |
| `SPECDEV_REPLAY_DIFF_ERROR_MODE=error` | Make replay diff failures fatal |
| `SPECDEV_STALENESS_THRESHOLD=N` | Minimum new upstream tokens required before W595 fires (default: 3) |

Use `env-check` to inspect the active configuration: `./tools/run_specdev.sh env-check --repo-root ./devspec_toolkit`

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
- `tools/specdev_tools/` — Python CLI package; entry point at `cli.py`, organized into subpackages:
  - `core/` — errors, json_output, registry, trace_types, changelog_parser, config, constants, loaders
  - `validation/` — validate, validators/, linters (fixtures, seed, quality, hallucination, dependency, forward-replay, traceability, invariants, governance, matrix)
  - `generation/` — prompt_generator, prompt_schema_sync, schema_differ
  - `canonical/` — autofix, integrity, lint, registry
  - `migration/` — planner, runner
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
2. **Emit**: write artifact JSON directly to `spec/NN_name.json`. Do not return fenced JSON as primary output. Seed associations are derived from `seed_manifest.json` `step_requirements` — no per-artifact `seed_refs` field is needed.

Agent protocol metadata lives in `docs/agents/manifest.json`.

---

## Troubleshooting

- **Schema not found**: run from repo root; confirm `--repo-root` points to toolkit; check `tools/schema_registry.json`
- **Unknown Target in fixtures**: ensure the target ID (`fr-*`, `api-*`, `nfr-*`, `inv-*`) exists in its spec file
- **Governance rejection**: match commit pattern from Step 10; `pr_rules` must use allowed enum values
- **Step 11 failures**: `target_ids` must target an API or Component; `mitigations` must be structured objects, not strings
- **Step 15 failures**: `method` must be one of GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD; no duplicate `interface_ref`
- **Glossary failures**: `terms` needs ≥1 item; definitions >20 chars; `domain` is kebab-case; no empty strings
- **Step 09 failures**: `tech_stack` must be an object (not array); `milestones` need a `deliverables` array
- **E530 INVENTED_ENUM_OR_ID on a `command` field**: hallucination-lint restricts the leading verb of any `command` string to its allowlist. Resolve via either (a) attach a sibling `command_ref` whose `id` is a `cn:`-prefixed string (typically `cn:project:command:<verb>` registered in `<spec-root>/canon/kinds/command.json`) — hallucination-lint bypasses the prefix check on shape alone; resolution of the ref is enforced separately by `canonical-integrity` (E110/E210), so register the entry to keep that check green; or (b) extend the project-level allowlist at `<spec-root>/canon/command_prefixes.json` (`{"allowed_prefixes": ["yq", "kubectl", ...]}`) which is merged with the toolkit default. `bash -c "<inner>"` wrapping is legal but discouraged.

---

## Submodule Deployments

When the toolkit is vendored as a git submodule inside a host repo, run commands from the **host repo root**. The positional `spec_dir` should point at the host repo's live spec directory (typically `./spec`), and `--repo-root ./devspec_toolkit` tells the CLI where to find schemas and the toolkit's core canon.

```bash
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh context structure spec --step 11 --repo-root ./devspec_toolkit
```

### When `--spec-root` and `--git-root` are needed

These flags are **not accepted on every command** (e.g. `context`, `json`, `ai-help`, `env-check` do not take them). They apply to validators and linters that need to resolve project-tier canon at `<host>/spec/canon/` or run git operations against the host repo:

```bash
./tools/run_specdev.sh validate-all spec \
  --repo-root ./devspec_toolkit \
  --spec-root ./spec \
  --git-root .
```

- `--spec-root ./spec` — lets canonical-lint / canonical-integrity discover project-tier canon under `./spec/canon/` (in addition to toolkit-core canon under `./devspec_toolkit/canon/`). Also enables hallucination-lint to merge the project-level command-prefix allowlist at `./spec/canon/command_prefixes.json` with the toolkit default at `tools/command_prefixes.json`.
- `--git-root .` — points forward-replay and governance-check at the host repo's git history instead of the submodule's.

If a command rejects these flags as "unrecognized arguments", it simply doesn't need them — drop the flags and re-run.

### Base Ref Resolution Order

Forward-replay checks resolve the diff base ref in this order:
1. `SPECDEV_REPLAY_BASE_REF` env var (explicit override)
2. Upstream tracking branch (`@{upstream}`)
3. `origin/main` → `origin/master` → `main` → `master`
4. Current branch name
5. Fallback: `origin/main`

### Troubleshooting (Submodule)

- **Forward replay silently disabled**: Pass `--git-root .` to point git operations at the host repo
- **Spec files not found**: Pass `--spec-root ./spec` to point at the host repo's spec directory
- **Silent mode="ignore"**: Set `SPECDEV_REPLAY_DIFF_ERROR_MODE=error` or ensure you're in a git repo
