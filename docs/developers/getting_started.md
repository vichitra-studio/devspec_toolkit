# Getting Started With The AI Spec Driven Development Toolkit

This guide onboards developers to the end-to-end spec workflow and shows how to work with the repository, prompts, and validation tooling. It consolidates the information that previously lived in the quick start and tutorial documents so there is a single source of truth for human readers. Other docs reference this file for environment setup so keep it authoritative.

## Prerequisites
- Python 3.10+ for running the CLI and validation commands
- (Optional) Node.js for exercising generated scaffolds
- Access to an AI assistant that can emit valid JSON
- Familiarity with Git and basic JSON editing

## 1. Set Up Your Environment
All instructions assume you are at the root of your host repository and the toolkit is checked out at [./devspec_toolkit/](../../). Adjust the paths if you keep the toolkit elsewhere.

The standard setup uses the automated script to configure the environment and dependencies:

```bash
# Run the setup script (creates 'devspec_env' and installs dependencies)
./devspec_toolkit/setup_devspec_env.sh

# Activate the virtual environment
source devspec_env/bin/activate

# Configure PYTHONPATH
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

# Verify CLI availability
python -m specdev_tools.cli --help
```

> **Note:** If you prefer manual setup, ensure you create a virtual environment, install `tools/requirements.txt`, and install the package with `pip install -e ./devspec_toolkit/tools`.

When you run CLI commands against artifacts in your host repo, include `--repo-root ./devspec_toolkit` so the schema registry in the toolkit resolves correctly.

## 2. Understand The Repository Layout
Consult the [Toolkit Layout](../../README.md#toolkit-layout) diagram for the canonical directory map, then keep these working pointers in mind:
- `spec/` (in your host repo) — machine artifacts (`NN_step.json`) and human guides (`NN_step.guide.md`) you actively maintain.
- [./devspec_toolkit/](../../) — the toolkit submodule providing schemas, prompts, docs, templates, and CLI code (substitute your path if different).
  - [schema/](../../schema/) — JSON Schemas for every spec step plus shared atoms/collections/errors
  - [schema/](../../schema/) — JSON Schemas for every spec step plus shared atoms/collections/errors
  - [prompts/](../../prompts/) — deterministic prompts for AI assistants (contains the guide and requirements)
  - [tools/](../../tools/) — CLI package and schema registry used during validation
- [example/devspec_kit/](../../example/devspec_kit/) — fully specced reference artifacts for the toolkit itself (read-only)

The [developer index](index.md) links to deeper explanations when you need them.

## 3. Run The Mandala Workflow

### Phase 0 · Seed The Project (Input Zero)
Before writing formal specs, you must define the "Seed" of your project using the Smart Prompts. This ensures you have a coherent vision before structured discovery.

1. **Seed Overview** (`seed_templates/seed_overview.md`):
   - **Purpose**: acts as your "Product Coach" to define the *What*, *Who*, and *Why* (Vision, Personas, MVP Scope).
   - **Expectation**: plain English, accessible language. Completeness is mandatory (no TBDs). Defines the functional North Star.
2. **Seed Tech Stack** (`seed_templates/seed_tech_stack.md`):
   - **Purpose**: acts as your "Senior Architect" to define the *How* and *Where* (Architecture, Constraints, Dependencies).
   - **Expectation**: high technical rigor. Pinned versions (e.g. `Python 3.12`), justified choices, and explicit constraints.

**Why?** These documents eliminate ambiguity before you start the AI workflow. Step 00-12 will hallucinate if these foundations are missing.

### Phase I · Spec Discovery (Steps 00–12)
1. Locate the matching prompt in [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/).
2. Read the prompt to internalise the Definition of Ready and dependencies.
3. Run the matching prompt from [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/) using the two‑phase flow:
   - Phase A — Clarify: the assistant reads the prompt’s “Context To Ingest” and “Operating Flow”, applies the “Self‑Audit Gate”, and outputs only a short bulleted list of targeted questions if critical info is missing.
   - Phase B — Emit: after answering questions, rerun to emit exactly one fenced `json` block.
4. Paste the single fenced `json` block into `spec/NN_name.json` in your host repo.
5. Validate the artifact using the [core validation commands](reference.md#core-validation-commands).
6. Keep traceability up to date; run the same command set after each change with the `--repo-root` flag.

### Phase II · Spec → Implementation (Steps 13–17)
1. Generate scaffolds manually or using your framework's CLI (e.g., `npm init`, `fastapi new`) based on `15_scaffold.json`.
2. Implement against fixtures until `14_fixture_impl.json` reports green.
3. Expand coverage via the red-team loop, monitoring, and drift audits.

The workflow overviews in [workflows/discovery.md](workflows/discovery.md) and [workflows/spec_to_impl.md](workflows/spec_to_impl.md) provide the rationale for each phase.

## 4. Essential CLI Commands

Keep [reference.md](reference.md) handy for the complete command catalogue, flags, and troubleshooting tips. Every command in that file assumes the pattern `--repo-root ./devspec_toolkit` when you operate from your host repository.

## 5. Working With AI Assistants
- Read the prompt file before invoking an assistant so you know the Definition of Ready (DoR) and guardrails.
- Copy the prompt exactly as stored under [./devspec_toolkit/prompts/](../../prompts/).
- Use the two‑phase flow:
  - Phase A — Clarify: if the prompt’s “Self‑Audit Gate” is not satisfied, the assistant should output only a concise, grouped list of Gap Questions. Answer them.
  - Phase B — Emit: the assistant then emits **exactly one** fenced `json` block that validates against the embedded schema.
- Clarify responses: short, bulleted questions grouped by topic; no JSON, no code fences, no speculative answers; prioritize gating items (trace/owners/units/methods/security) and stop after asking until you respond.
- If validation fails, consult the guide, address errors, and re-run the emission.
- Need a quick reminder of the workflow for a given step? Run `python -m specdev_tools.cli ai-help --step NN`.

Automation protocol and runner tips live in [../agents/manifest.json](../agents/manifest.json) and [../agents/agents.md](../agents/agents.md).

## 6. Validation Rituals
Run the [core validation commands](reference.md#core-validation-commands) whenever you change specs. They enforce schema compliance, traceability coverage, and fixture health, keeping the workflow repeatable and predictable.

Prefer a single command that chains those checks? Consult [`reference.md#bundled-scripts`](reference.md#bundled-scripts) for the [tests/run.sh](../../tests/run.sh) wrapper and the example smoke test so the command details stay canonical.

## 7. Where To Go Next
- Need a conceptual model? See [workflows/discovery.md](workflows/discovery.md) and [workflows/spec_to_impl.md](workflows/spec_to_impl.md).
- Looking for troubleshooting tactics? Review [tooling/gap_hunter_checklist.md](tooling/gap_hunter_checklist.md) and [tooling/coverage_matrix.md](tooling/coverage_matrix.md).

By following this single guide, developers share the same source of truth and can collaborate with AI agents without duplicating knowledge across multiple documents.
