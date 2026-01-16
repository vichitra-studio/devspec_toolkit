# Changelog

All notable changes to this toolkit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-01-16

### Added
- **Schema Extensions**:
    - Added generic `metadata` store to `atoms.schema.json`.
    - Integrated `metadata` into `16_impl_context.schema.json` (Plan, Tasks, Execution, Review) to capture "lost" context like Ambiguity Source and Definition of Done.
    - Added structured `coding_examples` array to replace legacy `coding_patterns`.
- **Prompts**: Updated Steps 16a, 16b, 16c to utilize new schema fields.

## [0.1.0] - 2026-01-14

### Added

**Core Spec Suite (Steps 00-16)**
- **Discovery Phase (00-12)**: Charter, Capabilities, System Sketch, Glossary, FR List, Interface Contracts, Invariants, NFRs, Fixtures, Implementation Plan, Governance, Redteam, CI Gates
- **Extension & Planning (13-14)**: Extension Generator for domain-specific specs, Roadmap with atomic user stories
- **Implementation (15-16)**: Scaffold generation, Trinity Loop (Planner/Coder/Reviewer)

**Tooling**
- `specdev-tools` CLI with validate, matrix, fixtures-lint, invariants-check, governance-check commands
- JSON Schema validation against toolkit schemas
- Trace matrix generation for FR ↔ Interface ↔ Fixture traceability
- Governance rules enforcement for commit messages

**Infrastructure**
- Project initialization script (`init_project.py`) with submodule setup
- Pre-commit hooks for spec validation
- GitHub Actions CI workflow generation
- Seed templates for project bootstrapping

**Documentation**
- Developer getting started guide and reference
- Workflow guides: Discovery, Spec-to-Implementation, Bootstrap Legacy, Feature Extension
- Prompt library with two-phase (Clarify → Emit) AI interaction pattern

### Notes
This is the baseline version establishing migration tracking. All existing functionality is considered part of v0.1.0 for future migration purposes.
