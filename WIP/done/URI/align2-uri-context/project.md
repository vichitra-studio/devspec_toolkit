## Project Context
project_type: schema-first development toolkit for AI-assisted workflow automation
project_description: A deterministic pipeline that converts specifications into implementation through a strict waterfall workflow with JSON schemas, validation linters, and prompt-driven artifact generation.

### Repository Structure
canon | Canonical registry for shared vocabulary (units, stages, environments, roles, NFR categories, trace types, owners)
changelog | Changelog management and version tracking
docs | Project documentation and agent protocol metadata
prompts | Deterministic prompt contracts for each specification step
schema | JSON Schemas for every step plus core atoms, collections, and errors
scripts | Utility scripts including project initialization
seed_templates | Template seed documents for project bootstrap
spec | Specification artifacts numbered 00-16c across discovery and implementation phases
templates | Template files for project generation
tests | pytest suite with per-step fixtures and integration tests
tools | Python CLI package with validation, generation, canonical, and migration submodules
WIP | Work-in-progress and experimental artifacts

### Pipeline Stages
Phase 0 Seed Docs | Seed overview and tech stack documents before formal specifications
Phase I Discovery | Steps 00-12: Charter through CI Gates (requirements, design, governance)
Phase II Implementation | Steps 13-16c: Extension Generator through Trinity Loop (code and review)

### Key Conventions
ID naming | kebab-case identifiers (fr-user-login, api-session-create)
Owner enum | api; ui; system; ops; data; product; business; engineering
Schema URI | All artifacts include canonical $schema URI from matching prompt
Two-Phase AI Protocol | Clarify (if Self-Audit Gate < 0.9) then Emit to spec file
Waterfall strict ordering | Any upstream change requires full replay of all downstream steps
Schema reuse | Use atoms/collections/errors from schema/core/ never redefine primitives

## Build/Test Config
test_command: pytest tests/
venv: devspec_env
repo_root_flag: --repo-root ./devspec_toolkit
commit_format: governance-compliant per spec/10_governance.json
test_runner: pytest tests/
suggestion: none
