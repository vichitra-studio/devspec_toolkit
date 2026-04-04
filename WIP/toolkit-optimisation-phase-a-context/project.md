## Project Context
project_type: Prompt engineering framework and toolkit
project_description: The AI Spec Driven Development Toolkit is a schema-first, AI-assisted workflow that turns spec → implementation into a deterministic pipeline. It enforces structured governance through waterfall phases, JSON schema validation, and canonical registries.

### Repository Structure
canon/ | Canonical registry (manifest.json, aliases.json) for shared vocabulary and enum definitions
changelog/ | Version changelog and release notes
docs/ | Documentation and agent protocol metadata
prompts/ | Deterministic prompt contracts for each step in the pipeline
schema/ | JSON Schemas for every spec step plus core atoms, collections, and error definitions
scripts/ | Bootstrap and initialization scripts (init_project.py)
seed_templates/ | Seed document templates for project setup
spec/ | Specification artifacts (NN_name.json format) organized in waterfall steps
templates/ | Template files for artifact generation
tests/ | pytest suite with per-step fixtures and integration tests
tools/ | Python CLI package (specdev_tools/) with validation, generation, and canonical tooling
WIP/ | Work-in-progress and experimental files

### Pipeline Stages
Phase 0 | Seed documentation (seed_overview.md + seed_tech_stack.md)
Phase I: Discovery | Steps 00–12: Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates
Phase II: Implementation | Steps 13–16c: Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review)

### Key Conventions
IDs use kebab-case only | Examples: fr-user-login, api-session-create
Owner enum fixed | Valid values: api, ui, system, ops, data, product, business, engineering
Artifacts include canonical $schema | Every spec file must reference its matching JSON Schema URI
Forward-only waterfall | Upstream changes require full replay of downstream steps
Two-phase AI runner protocol | Clarify phase (gap questions) → Emit phase (direct JSON to spec/)
Reuse atoms from schema/core/ | Never redefine primitive types; use shared collection definitions
Governance-compliant commits | Messages must match pattern in spec/10_governance.json with required trace codes
Submodule flag convention | Pass --repo-root ./devspec_toolkit when running from host repo; --spec-root ./spec and --git-root . for submodule deployments

## Build/Test Config
test_command: pytest tests/
venv: dev_env/bin/activate
repo_root_flag: --repo-root ./devspec_toolkit
commit_format: Governance-compliant pattern from spec/10_governance.json with feature/fix/docs tags and trace code references (e.g., feat(spec): add login [fr-initial-login])
test_runner: pytest tests/
suggestion: none
truncated: none
