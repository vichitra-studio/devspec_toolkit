## Project Context
project_type: Python CLI tool and schema-first workflow framework
project_description: The AI Spec Driven Development Toolkit is a schema-first, AI-assisted workflow that turns spec → implementation into a deterministic pipeline. It is typically vendored as a git submodule and provides tooling for spec validation, governance, canonical integrity, and automated code generation.

### Repository Structure
canon/ | Canonical registry (manifest.json, aliases.json) for shared vocabulary: units, stages, environments, roles, NFR categories, trace types, owners
changelog/ | Changelog management and tracking
devspec_env/ | Python virtual environment
docs/ | Documentation and agent protocol metadata
prompts/ | Deterministic prompt contracts for each spec step (consumed by AI runners)
schema/ | JSON Schemas for every step plus schema/core/ (atoms, collections, errors shared across steps)
scripts/ | Bootstrapping and initialization scripts (init_project.py)
seed_templates/ | Seed template files for project initialization
spec/ | Generated spec artifacts (JSON) organized by step number (00-16c)
templates/ | Reference templates for spec generation
tests/ | pytest suite with per-step valid/invalid JSON fixtures and integration tests
tools/ | Python CLI package (specdev_tools) with schema registry and step order definitions
WIP/ | Work-in-progress directories and experimental files

### Pipeline Stages
Phase 0 | Seed docs: seed_overview.md + seed_tech_stack.md before any formal specs
Phase I · Discovery | Steps 00–12: Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates
Phase II · Impl | Steps 13–16c: Extension Generator → Completeness Assessment → Roadmap → Scaffold → Trinity Loop (16a plan / 16b code / 16c review)

### Key Conventions
ID format | kebab-case only (fr-user-login, api-session-create)
Owner enum | api | ui | system | ops | data | product | business | engineering
Schema requirement | All artifacts must include the canonical $schema URI as emitted by the matching prompt
Atom reuse | Reuse atoms/collections/errors from schema/core/ — never redefine primitives
AI runner protocol | Two-phase Clarify → Emit: if Self-Audit Gate < 0.9 output gap questions; otherwise write artifact JSON directly to spec/NN_name.json
Validation ritual | After spec edit: (1) validate the changed artifact (2) seed-lint to verify seed refs (3) if traceability changed regenerate matrix and run fixtures-lint (4) use governance-compliant commit message
CLI wrapper | All CLI commands must go through ./tools/run_specdev.sh — never call internal modules directly
Critical flag | Always pass --repo-root ./devspec_toolkit when running from the host repo
Spec directory | The locked spec_dir for this repo is devspec_toolkit/spec (not a top-level spec/)

## Build/Test Config
test_command: pytest tests/
venv: source dev_env/bin/activate
repo_root_flag: --repo-root ./devspec_toolkit
commit_format: governance-compliant commit message per spec/10_governance.json
test_runner: pytest tests/
suggestion: none
