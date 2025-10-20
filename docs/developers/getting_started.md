# Getting Started With The AI Spec Driven Development Toolkit

This guide onboards developers to the end-to-end spec workflow and shows how to work with the repository, prompts, and validation tooling. It consolidates the information that previously lived in the quick start and tutorial documents so there is a single source of truth for human readers.

## Prerequisites
- Python 3.10+ for running the CLI and validation commands
- (Optional) Node.js for exercising generated scaffolds
- Access to an AI assistant that can emit valid JSON
- Familiarity with Git and basic JSON editing

## 1. Set Up Your Environment
All instructions assume you are at the root of your host repository and the toolkit is checked out at `./devspec_toolkit/`. Adjust the paths if you keep the toolkit elsewhere.
```bash
# adjust ./devspec_toolkit if the toolkit lives elsewhere
python -m venv .venv
. .venv/bin/activate
pip install -r ./devspec_toolkit/tools/requirements.txt

# Make the toolkit modules importable
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

# Verify the CLI is available
python -m specdev_tools.cli --help
```

When you run CLI commands against artifacts in your host repo, include `--repo-root ./devspec_toolkit` so the schema registry in the toolkit resolves correctly.

## 2. Understand The Repository Layout
- `spec/` (in your host repo) — machine artifacts (`NN_step.json`) and human guides (`NN_step.guide.md`) you actively maintain.
- `./devspec_toolkit/` — the toolkit submodule providing schemas, prompts, docs, templates, and CLI code (substitute your path if different).
  - `schema/` — JSON Schemas for every spec step plus shared atoms/collections/errors
  - `prompts/` — deterministic prompts for AI assistants (one per step)
  - `template/` — guide blueprints you copy into your host repo before editing
  - `tools/` — CLI package and schema registry used during validation
- `example/devspec_kit/` — fully specced reference artifacts for the toolkit itself (read-only)

The [developer index](index.md) links to deeper explanations when you need them.

## 3. Run The Mandala Workflow

### Phase I · Spec Discovery (Steps 00–12)
1. Copy the matching guide blueprint from `./devspec_toolkit/template/` into `spec/NN_name.guide.md` if it does not exist yet, then tailor it for your product.
2. Read the guide to internalise the Definition of Ready and dependencies.
3. Run the matching prompt from `./devspec_toolkit/prompts/prompt_NN_name.md`.
4. Paste the single fenced `json` block into `spec/NN_name.json` in your host repo.
5. Validate the artifact:
   ```bash
   python -m specdev_tools.cli validate spec/NN_name.json \
     --repo-root ./devspec_toolkit
   ```
6. Keep traceability up to date; use `matrix`, `fixtures-lint`, and `validate-all` with the same `--repo-root` flag as guardrails.

### Phase II · Spec → Implementation (Steps 13–17)
1. Generate scaffolds and validate contracts:
   ```bash
   python -m specdev_tools.cli scaffold spec \
     --repo-root ./devspec_toolkit \
     --out scaffold_out
   ```
2. Implement against fixtures until `14_fixture_impl.json` reports green.
3. Expand coverage via the red-team loop, monitoring, and drift audits.

The workflow overviews in `workflows/discovery.md` and `workflows/spec_to_impl.md` provide the rationale for each phase.

## 4. Essential CLI Commands

Keep `reference.md` handy for the complete command catalogue, flags, and troubleshooting tips. Every command in that file assumes the pattern `--repo-root ./devspec_toolkit` when you operate from your host repository.

## 5. Working With AI Assistants
- Read the human guide before invoking an assistant so you know the Definition of Ready (DoR) and guardrails.
- Copy the prompt exactly as stored under `./devspec_toolkit/prompts/`.
- Instruct the assistant to output **exactly one** fenced `json` block that validates against the embedded schema.
- If validation fails, consult the guide, adjust the prompt, and re-run the command.

Automation-specific rules and escalation paths reside in `../agents/agents.md`; developers rarely need to reference them.

## 6. Validation Rituals
Run the following whenever you change specs:
```bash
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit
```

These commands enforce schema compliance, traceability coverage, and fixture health, keeping the workflow repeatable and predictable.

## 7. Where To Go Next
- Need a conceptual model? See `workflows/discovery.md` and `workflows/spec_to_impl.md`.
- Looking for troubleshooting tactics? Review `tooling/gap_hunter_checklist.md` and `tooling/coverage_matrix.md`.

By following this single guide, developers share the same source of truth and can collaborate with AI agents without duplicating knowledge across multiple documents.
