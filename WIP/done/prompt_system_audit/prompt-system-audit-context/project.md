## Project Context
project_type: Python specification-driven development toolkit
project_description: A schema-first, AI-assisted workflow that turns spec → implementation into a deterministic pipeline. The toolkit is typically vendored as a git submodule and provides validation, testing, and governance tools for managing multi-phase specification artifacts.

### Repository Structure
canon/ | Canonical registry for shared vocabulary (units, stages, environments, roles, NFR categories)
changelog/ | Version control and changelog management
docs/ | Documentation including agent protocol metadata
prompts/ | Deterministic prompt contracts for each specification step
schema/ | JSON Schemas for every specification step plus shared core schemas
scripts/ | Initialization and deployment scripts including run_specdev.sh template
seed_templates/ | Template files for seed documentation
spec/ | Locked specification directory for toolkit artifacts
templates/ | Template files for project generation
tests/ | pytest test suite with fixtures and integration tests
tools/ | Python CLI package (specdev_tools) with entry point at cli.py
WIP/ | Work-in-progress and experimental files

### Pipeline Stages
Phase 0 | Seed documentation (seed_overview.md + seed_tech_stack.md before formal specs)
Phase I · Discovery | Steps 00–12: Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates
Phase II · Impl | Steps 13–16c: Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review)

### Key Conventions
ID naming | IDs must be kebab-case only (e.g., fr-user-login, api-session-create)
Owner enum | api | ui | system | ops | data | product | business | engineering
Schema URI requirement | All artifacts must include the canonical $schema URI as emitted by the matching prompt
Primitive reuse | Reuse atoms/collections/errors from schema/core/ — never redefine primitives
CLI wrapper requirement | All CLI commands must go through ./tools/run_specdev.sh wrapper, never call internal modules directly
Repo root flag | Always pass --repo-root ./devspec_toolkit when running from host repo
Waterfall workflow | Strict forward-only waterfall; any upstream change requires full replay of all downstream steps
Step numbering | Steps numbered: 00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 13a 14 15 16 16a 16b 16c
Two-phase AI protocol | Clarify (if Self-Audit Gate < 0.9, output questions only) → Emit (write artifact JSON directly to spec/)
Validation ritual | After spec edit: validate, seed-lint, regenerate matrix if traceability changed, fixtures-lint, governance-compliant commit

## Build/Test Config
test_command: pytest tests/
venv: devspec_env
repo_root_flag: --repo-root ./devspec_toolkit
commit_format: Governance-compliant per spec/10_governance.json
test_runner: pytest tests/
suggestion: none
