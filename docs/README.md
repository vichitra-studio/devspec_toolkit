# Documentation Index

This directory contains the authoritative guides for the AI Spec Driven Development Toolkit.

## 👩‍💻 For Developers

| Guide | Purpose |
| :--- | :--- |
| **[Getting Started](developers/getting_started.md)** | **Start here.** End-to-end setup, environment config, and workflow walkthrough. |
| **[Reference](developers/reference.md)** | **Daily use.** Cheatsheet for CLI commands, schema IDs, and naming conventions. |
| **[Extension Schemas](developers/extension_schemas.md)** | How to write domain-specific schemas (e.g., for AI models or database tables). |
| **Seed Manifest** (`spec/common/seed_manifest.json`) | Mandatory seed order, step requirements, and docs policy. |

### Workflows
Detailed breakdowns of the spec lifecycle phases:
- **[Discovery (Steps 00-12)](developers/workflows/discovery.md)**: From charter to locked specs.
- **[Spec → Impl Bridge](developers/workflows/spec_to_impl.md)**: Connecting the two phases.

### Workflows (additional)
- **[Alignment & Migration](developers/workflows/workflow_align.md)**: Upgrading specs to a new toolkit version.
- **[Migration Guide](developers/workflows/workflow_migration.md)**: Detailed migration options including manual fallback.
- **[Feature Extension](developers/workflows/workflow_feature_extension.md)**: Adding new spec extensions.

### Tooling & Deep Dives
- **[Coverage Matrix](developers/tooling/coverage_matrix.md)**: Understanding valid links between artifacts.
- **[Gap Hunter Checklist](developers/tooling/gap_hunter_checklist.md)**: How to manually audit specs for quality.
- **[Error Codes](developers/error-codes.md)**: Full reference for all E/W validation error codes.
- **[Path Conventions](developers/path_conventions.md)**: File and directory naming rules.
- **Strict mode checks**: quality and hallucination gates (`spec-quality-lint`, `hallucination-lint`) plus replay/dependency checks are documented in [Reference](developers/reference.md).
- **[Align Tool](developers/tools/align.md)**: How the `align` subcommand works for spec migration.
- **[Changelog Parser](developers/tools/changelog_parser.md)**: How the changelog is parsed and validated.
- **[Prompt Context Tool](developers/tools/prompt_context.md)**: How `prompt-context` resolves downstream consumers per step.
- **[Schema Differ](developers/tools/schema_differ.md)**: How schema diffs are computed for migration planning.

### Architecture & Operations
- **[Governance Architecture](architecture/governance_architecture.md)**: Design of the governance and validation system.
- **[ADR: Template Engine](ops/adr_template_engine.md)**: Decision record for the migration prompt template renderer.
- **[Toolkit Update Checklist](ops/toolkit_update_checklist.md)**: Steps for releasing a new toolkit version.

---

## 🤖 For AI Agents

| Resource | Purpose |
| :--- | :--- |
| **[Agent Protocol](agents/agents.md)** | Operational specificaton for AI agents (Two-Phase Flow, Self-Audit). |
| **[Manifest](agents/manifest.json)** | Machine-readable capabilities and hints. |

---

## 📄 Prompt Contracts

The single source of truth for every step's requirements lives in the **[prompts/](../prompts/)** directory (top-level, beside this `docs/` directory).
- `prompt_00_charter.md` through `prompt_16c_impl_reviewer.md`.
- `prompt_16_impl_context.md` for the Step 16 Trinity Anchor.
- Shared expectations (inherited by all step prompts): **[docs/prompts/shared_expectations.md](prompts/shared_expectations.md)**.
