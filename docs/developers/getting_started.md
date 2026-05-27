# Getting Started With The AI Spec Driven Development Toolkit

This guide onboards developers to the end-to-end spec workflow and shows how to work with the repository, prompts, and validation tooling. It consolidates the information that previously lived in the quick start and tutorial documents so there is a single source of truth for human readers. Other docs reference this file for environment setup so keep it authoritative.

## Prerequisites
- Python 3.10+ for running the CLI and validation commands
- (Optional) Node.js for exercising generated scaffolds
- Access to an AI assistant that can emit valid JSON
- Familiarity with Git and basic JSON editing

## 0. Initialize the Project
Before setting up your environment, initialize your project using the toolkit's automated utility. This sets up the directory structure, adds the toolkit as a submodule, seeds context documents, and generates a CI workflow.

```bash
# From within the toolkit checkout (or if you curl the script):
python3 devspec_toolkit/scripts/init_project.py --target /path/to/my/project --strict
```

The script performs the following actions:
1.  **Git Initialization**: Runs `git init` and adds `devspec_toolkit` submodule.
2.  **Directory Structure**: Creates `spec/`, `spec/common/`, `spec/canon/`, `spec/impl_context/`, `.github/workflows/`, and seed-doc directories (default layout: `docs/seed/`; actual paths are declared in `spec/common/seed_manifest.json` `seeds[].path`).
3.  **Seed Templates**: Copies the seed files declared in `spec/common/seed_manifest.json` (`seeds[].path`) and the manifest itself.
4.  **Environment**: Creates `devspec_env` and installs dependencies + hooks.
5.  **Strict Mode** (Optional): Passing `--strict` enforces governance rules on commit messages.

## 1. Set Up Your Environment
The initialization utility has already created and configured your virtual environment.

Simply activate it to start working:
```bash
source devspec_env/bin/activate

# Verify everything is working
./tools/run_specdev.sh --help
```

> [!NOTE]
> If you prefer manual setup, ensure you create a virtual environment, install `tools/requirements.txt`, and install the package with `pip install -e ./devspec_toolkit/tools`.

All validation and linting commands must run through `./tools/run_specdev.sh ...`; do not call internal modules directly. This is the only supported entrypoint and ensures the virtualenv guard and schema registry behavior are applied consistently.
The wrapper invokes the `devspec_env` Python directly, so it works even if you have not activated the environment in your current shell.

When you run CLI commands against artifacts in your host repo, include `--repo-root ./devspec_toolkit` so the schema registry in the toolkit resolves correctly.

## 2. Check Toolkit Version and Alignment

The toolkit uses semantic versioning. Check the current version in [tools/pyproject.toml](../../tools/pyproject.toml):

```bash
grep 'version' devspec_toolkit/tools/pyproject.toml
```

The toolkit tracks which version your specs were written for in a `spec/specdev_version` file. This file is created at project initialization (by `init_project.py`) and updated by `specdev align` on each migration. Every project must have this file; `spec-check` reports E608 if it is absent.

**Check if you are up to date:**
```bash
specdev align status
```

*   **Aligned**: You are good to go.
*   **Mismatch**: You need to run the [Migration Workflow](workflows/workflow_align.md).

```yaml
# Example spec/specdev_version
toolkit_version: "<current toolkit version>"
created_at: "2026-01-14T00:00:00Z"
last_migration: null
```

## 3. Understand The Repository Layout
Consult the [Toolkit Layout](../../README.md#toolkit-layout) diagram for the canonical directory map, then keep these working pointers in mind:
- `spec/` (in your host repo) — machine artifacts (`NN_step.json`) and human guides (`NN_step.guide.md`) you actively maintain.
- [./devspec_toolkit/](../../) — the toolkit submodule providing schemas, prompts, docs, templates, and CLI code (substitute your path if different).
  - [schema/](../../schema/) — JSON Schemas for every spec step plus shared atoms/collections/errors

  - [prompts/](../../prompts/) — deterministic prompts for AI assistants (contains the guide and requirements)
  - [tools/](../../tools/) — CLI package and schema registry used during validation


The [developer index](index.md) links to deeper explanations when you need them.

## 4. Run The Mandala Workflow

### Phase 0 · Seed The Project (Input Zero)
Before writing formal specs, you must define the "Seed" of your project using the Smart Prompts. This ensures you have a coherent vision before structured discovery.

0. **Seed Manifest** (`spec/common/seed_manifest.json`):
   - **Purpose**: defines the mandatory seed order and step-specific requirements.
   - **Expectation**: treat it as the authoritative source for seed ingestion order and per-step seed requirements.
1. **Seed documents** (paths declared in `spec/common/seed_manifest.json` `seeds[].path`):
   - The manifest lists every seed file, its path relative to the repo root, and its description. Consult it as the authoritative source of seed locations and purpose.
   - Typical seeds include a product overview (Vision, Personas, MVP Scope) and a tech-stack document (Architecture, Constraints, Dependencies). Your project may declare additional seeds for any step.

**Why?** These documents eliminate ambiguity before you start the AI workflow. Step 00-12 will hallucinate if these foundations are missing.

### Phase I · Spec Discovery (Steps 00–12)
1. Locate the matching prompt in [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/).
2. Read the prompt to internalise the Definition of Ready and dependencies.
3. Run the matching prompt from [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/) using the two‑phase flow:
   - Phase A — Clarify: the assistant reads the prompt’s “Operating Flow”, applies the “Self‑Audit Gate” (and “Context To Ingest” where applicable, or “Coverage Closure” for steps that use it), and outputs only a short bulleted list of targeted questions if critical info is missing.
   - Phase B — Emit: after answering questions, rerun and write the artifact JSON directly to disk (`spec/NN_name.json`).
4. Confirm the artifact JSON is written directly to `spec/NN_name.json` in your host repo.
5. Validate the artifact using the [core validation commands](reference.md#core-validation-commands).
6. Keep traceability up to date; run the same command set after each change with the `--repo-root` flag.

### Phase II · Spec → Implementation (Steps 13–16c)
1. Generate scaffolds manually or using your framework's CLI (e.g., `npm init`, `fastapi new`) based on `15_scaffold.json`.
2. Execute the Trinity Loop (16a-c) to plan, code, and review features milestone-by-milestone.
3. Validate implementation against `08_fixtures.json` and strict NFR gates.

The workflow overviews in [workflows/discovery.md](workflows/discovery.md) and [workflows/spec_to_impl.md](workflows/spec_to_impl.md) provide the rationale for each phase.

## 5. Essential CLI Commands

Keep [reference.md](reference.md) handy for the complete command catalogue, flags, and troubleshooting tips. Every command in that file assumes the pattern `--repo-root ./devspec_toolkit` when you operate from your host repository.

## 6. Working With AI Assistants
- Read the prompt file before invoking an assistant so you know the Definition of Ready (DoR) and guardrails.
- Copy the prompt exactly as stored under [./devspec_toolkit/prompts/](../../prompts/).
- Use the two‑phase flow:
  - Phase A — Clarify: if the prompt’s “Self‑Audit Gate” is not satisfied, the assistant should output only a concise, grouped list of Gap Questions. Answer them.
  - Phase B — Emit: the assistant writes the artifact JSON directly to disk and validates against the referenced step schema.
- Clarify responses: short, bulleted questions grouped by topic; no JSON, no code fences, no speculative answers; prioritize gating items (trace/owners/units/methods/security) and stop after asking until you respond.
- If validation fails, consult the guide, address errors, and re-run the emission.
- Need a quick reminder of the workflow for a given step? Run `./tools/run_specdev.sh ai-help --step NN`.

Automation protocol and runner tips live in [../agents/manifest.json](../agents/manifest.json) and [../agents/agents.md](../agents/agents.md).

## 7. Validation Rituals
Run the [core validation commands](reference.md#core-validation-commands) whenever you change specs. They enforce schema compliance, traceability coverage, and fixture health, keeping the workflow repeatable and predictable.

## 8. Where To Go Next
- Need a conceptual model? See [workflows/discovery.md](workflows/discovery.md) and [workflows/spec_to_impl.md](workflows/spec_to_impl.md).
- Looking for troubleshooting tactics? Review [tooling/gap_hunter_checklist.md](tooling/gap_hunter_checklist.md) and [tooling/coverage_matrix.md](tooling/coverage_matrix.md).

By following this single guide, developers share the same source of truth and can collaborate with AI agents without duplicating knowledge across multiple documents.
