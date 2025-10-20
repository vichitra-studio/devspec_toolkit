# Developer Reference

This reference collects recurring facts that developers need while authoring or reviewing specs. It replaces ad-hoc snippets scattered across multiple documents; other guides intentionally link here for the canonical commands and troubleshooting flow.

## Terminology
| Term       | Definition                                              |
|------------|----------------------------------------------------------|
| Step       | Numbered phase of the spec lifecycle (00–17, 02a)        |
| Artifact   | Machine-checked JSON file for a step (`spec/NN_name.json`) |
| Guide      | Human playbook describing a step (`spec/NN_name.guide.md`) |
| Prompt     | AI instruction file (`prompts/prompt_NN_name.md`)         |
| DoR        | Definition of Ready requirements for completing a step    |
| traceRef   | Identifier linking FRs ↔ APIs ↔ fixtures ↔ NFRs           |

## Naming & Schema Conventions
- **IDs**: kebab-case only (`fr-user-login`, `api-session-create`).
- **Owner enum**: one of `{api, ui, system, ops, data}`.
- **Artifacts**: include the canonical `$schema` URI exactly as emitted in the prompt.
- **File naming**: `spec/NN_name.json`, `spec/NN_name.guide.md`, [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/) (adjust the toolkit path as needed).
- **No redefining primitives**: reuse atoms/collections/errors from [schema/core/](../schema/core/).

## Command Cheatsheet
Set up your environment per [`getting_started.md`](getting_started.md#1-set-up-your-environment) before running these commands. Every other document links back here so this serves as the canonical command reference.

### Core validation commands
```bash
# Validation
python -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit

# Traceability & fixtures
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit

# Invariants, governance, CI
python -m specdev_tools.cli invariants-check spec --repo-root ./devspec_toolkit --sample ./devspec_toolkit/tests/samples/invariants/password_ok.json
python -m specdev_tools.cli governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): add login [fr-initial-login]"
python -m specdev_tools.cli gen-ci spec --repo-root ./devspec_toolkit --toolkit-path ./devspec_toolkit --out .github/workflows/ci.yml

# Scaffold generation
python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out

# Prompt workflow reminders
python -m specdev_tools.cli ai-help --step 04
```

Invoke commands from the root of your host repository so relative paths to `spec/` and [./devspec_toolkit/](../../) resolve cleanly.

## Two-Phase AI Runner Mode
- Prompts support a two-phase flow: Clarify (questions only) → Emit (single fenced `json`).
- Agents read each prompt’s “Context To Ingest”, follow the “Operating Flow”, apply the “Self‑Audit Gate”, and ask targeted questions if gating items are missing.
- Runners should honor the manifest interaction hints: see `docs/agents/manifest.json` (`interaction_mode: two_phase`).
- Operational guidance for agents and runner tips: `docs/agents/agents.md`.

## Validation Workflow
1. Edit the JSON artifact.
2. Run `validate`.
3. If any traceability changed, regenerate the matrix and lint fixtures.
4. Update governance-compliant commit messages per `spec/10_governance.json`.

## Bundled Scripts
- [tests/run.sh](../tests/run.sh) — chains the validation workflow for any spec set. Run it from your host repository root, pointing `--repo-root` at the toolkit path (defaults to the script parent) and optionally `--spec-dir` at an alternate spec directory:
  ```bash
  ./devspec_toolkit/tests/run.sh --repo-root ./devspec_toolkit [--spec-dir ./path/to/spec]
  ```
  The script writes the trace matrix to `tools/trace_matrix.json` beside your spec directory (see [example/tools/trace_matrix.json](../../example/tools/trace_matrix.json)) and the invariants log to `tests/.invariants.out.json` (generated on demand).
- [tests/unit](../tests/unit) — smoke-tests the bundled example artifacts. Execute it from the toolkit root to confirm the reference set remains healthy:
  ```bash
  ./devspec_toolkit/tests/unit
  ```

## Troubleshooting Checklist
- **Schema not found**: run from repo root or configure `--repo-root`; confirm [tools/schema_registry.json](../../tools/schema_registry.json).
- **Unknown API in fixtures**: ensure the target exists in `05_interface_contracts.json`.
- **Invariant evaluation null**: check referenced keys in fixtures or adjust the invariant expression.
- **Governance rejection**: match the commit pattern defined in Step 10.

## Related Resources
- [index.md](index.md) — Navigational overview of every document set.
- [getting_started.md](getting_started.md) — Single-path onboarding for new team members.
- [workflows/discovery.md](workflows/discovery.md) & [workflows/spec_to_impl.md](workflows/spec_to_impl.md) — Conceptual phase breakdowns.
- [tooling/coverage_matrix.md](tooling/coverage_matrix.md) — How traceability is enforced.
- [../agents/agents.md](../agents/agents.md) — Automation contract used by AI assistants.
