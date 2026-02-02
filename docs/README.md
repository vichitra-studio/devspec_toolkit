# Documentation Index

This directory contains the authoritative guides for the AI Spec Driven Development Toolkit.

## 👩‍💻 For Developers

| Guide | Purpose |
| :--- | :--- |
| **[Getting Started](developers/getting_started.md)** | **Start here.** End-to-end setup, environment config, and workflow walkthrough. |
| **[Reference](developers/reference.md)** | **Daily use.** Cheatsheet for CLI commands, schema IDs, and naming conventions. |
| **[Extension Schemas](developers/extension_schemas.md)** | How to write domain-specific schemas (e.g., for AI models or database tables). |

### Workflows
Detailed breakdowns of the spec lifecycle phases:
- **[Discovery (Steps 00-12)](developers/workflows/discovery.md)**: From charter to locked specs.
- **[Spec → Impl Bridge](developers/workflows/spec_to_impl.md)**: Connecting the two phases.

### Tooling & Deep Dives
- **[Coverage Matrix](developers/tooling/coverage_matrix.md)**: Understanding valid links between artifacts.
- **[Gap Hunter Checklist](developers/tooling/gap_hunter_checklist.md)**: How to manually audit specs for quality.

---

## 🤖 For AI Agents

| Resource | Purpose |
| :--- | :--- |
| **[Agent Protocol](agents/agents.md)** | Operational specificaton for AI agents (Two-Phase Flow, Self-Audit). |
| **[Manifest](agents/manifest.json)** | Machine-readable capabilities and hints. |

---

## 📄 Prompt Contracts

The single source of truth for every step's requirements lives in the **[prompts/](../prompts/)** directory.
- `prompt_00_charter.md` through `prompt_16c_review.md`.
- Shared expectations: **[prompts/shared_expectations.md](prompts/shared_expectations.md)**.
