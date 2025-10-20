# Developer Reference

This reference collects recurring facts that developers need while authoring or reviewing specs. It replaces ad-hoc snippets scattered across multiple documents.

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
- **File naming**: `spec/NN_name.json`, `spec/NN_name.guide.md`, `./devspec_toolkit/prompts/prompt_NN_name.md` (adjust the toolkit path as needed).
- **No redefining primitives**: reuse atoms/collections/errors from `schema/core/`.

## Command Cheatsheet
```bash
# One-time per shell: expose the toolkit modules (adjust the path if needed)
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

# Validation
python -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit

# Traceability & fixtures
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit

# Invariants, governance, CI
python -m specdev_tools.cli invariants-check spec --repo-root ./devspec_toolkit --sample tests/samples/invariants/password_ok.json
python -m specdev_tools.cli governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): add login [fr-initial-login]"
python -m specdev_tools.cli gen-ci spec --repo-root ./devspec_toolkit --toolkit-path ./devspec_toolkit --out .github/workflows/ci.yml

# Scaffold generation
python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out
```

Invoke commands from the root of your host repository so relative paths to `spec/` and `./devspec_toolkit/` resolve cleanly.

## Validation Workflow
1. Edit the JSON artifact.
2. Run `validate`.
3. If any traceability changed, regenerate the matrix and lint fixtures.
4. Update governance-compliant commit messages per `spec/10_governance.json`.

## Troubleshooting Checklist
- **Schema not found**: run from repo root or configure `--repo-root`; confirm `tools/schema_registry.json`.
- **Unknown API in fixtures**: ensure the target exists in `05_interface_contracts.json`.
- **Invariant evaluation null**: check referenced keys in fixtures or adjust the invariant expression.
- **Governance rejection**: match the commit pattern defined in Step 10.

## Related Resources
- `index.md` — Navigational overview of every document set.
- `getting_started.md` — Single-path onboarding for new team members.
- `workflows/discovery.md` & `workflows/spec_to_impl.md` — Conceptual phase breakdowns.
- `tooling/coverage_matrix.md` — How traceability is enforced.
- `../agents/agents.md` — Automation contract used by AI assistants.
