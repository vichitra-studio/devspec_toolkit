# Changelog Guide & Manifest

This document serves as the entry point for the DevSpec Toolkit's version tracking system. Unlike traditional single-file changelogs, this project uses a structured, multi-file approach to support both human readability and automated migration tooling.

## 📂 Architecture

All detailed version records are stored in the [`changelog/`](./changelog/) directory.

| Format | Path Pattern | Purpose | Audience |
| :--- | :--- | :--- | :--- |
| **Human** | `changelog/vX.Y.Z.md` | Provides a clear, readable summary of what changed, why it matters, and how to upgrade manually. Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). | Developers, Managers |
| **Machine** | `changelog/vX.Y.Z.yaml` | Strictly typed data source defining exact schema changes, field renames, and migration actions. Consumed by `specdev align`. | AI Agents, CLI Tools |

## 🚀 Version Index

| Version | Release Date | Documentation | Migration Spec | Status |
| :--- | :--- | :--- | :--- | :--- |
| **[0.2.3]** | 2026-02-12 | [v0.2.3.md](changelog/v0.2.3.md) | [v0.2.3.yaml](changelog/v0.2.3.yaml) | ⚠️ **Breaking** |
| **[0.2.2]** | 2026-02-12 | [v0.2.2.md](changelog/v0.2.2.md) | [v0.2.2.yaml](changelog/v0.2.2.yaml) | ✅ Patch |
| **[0.2.1]** | 2026-02-07 | [v0.2.1.md](changelog/v0.2.1.md) | [v0.2.1.yaml](changelog/v0.2.1.yaml) | ⚠️ **Breaking** |
| **[0.2.0]** | 2026-01-17 | [v0.2.0.md](changelog/v0.2.0.md) | [v0.2.0.yaml](changelog/v0.2.0.yaml) | ⚠️ **Breaking** (Schema Hardening) |
| **[0.1.1]** | 2026-01-13 | [v0.1.1.md](changelog/v0.1.1.md) | [v0.1.1.yaml](changelog/v0.1.1.yaml) | ✅ Patch (Fixes) |
| **[0.1.0]** | 2026-01-01 | [v0.1.0.md](changelog/v0.1.0.md) | [v0.1.0.yaml](changelog/v0.1.0.yaml) | 🏁 Baseline |

---

## ✍️ Contribution Guide

When making changes to the toolkit, you must determine if the change affects the **specification** (schemas, formats) or just the **implementation** (internal code, docs).

### 1. Does my change require a changelog entry?
- **YES**: You renamed a field in a JSON schema.
- **YES**: You added a new validation rule (e.g., `minItems: 1`).
- **YES**: You added a new Step to the framework.
- **YES**: You fixed a critical bug that alters CLI behavior.
- **NO**: You refactored internal code without changing behavior.
- **NO**: You fixed a typo in a prompt description.

### 2. How to create an entry?

#### Step A: Draft the Human Note
Edit (or create) the `Unreleased` section in `changelog/unreleased.md`. Use the standard groupings: `Required`, `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

```markdown
## [Unreleased]

### Changed
- **Schema**: Renamed `plan.tasks` to `checklist[].implementation` to better support iteration.
```

#### Step B: Define the Machine Spec (Crucial for AI)
Edit `changelog/unreleased.yaml`. This is critical because it tells the AI Agent *how* to migrate existing projects. Refer to [`changelog/format.yaml`](changelog/format.yaml) for the full schema.

**Example: Renaming a field**
```yaml
changes:
  - type: rename_field
    step_id: "09_impl_plan"
    path: "plan.tasks"
    to_path: "checklist"
    migration:
      action: auto  # Can be applied mechanically without AI reasoning
```

**Example: Adding a constraint (Requires AI)**
```yaml
changes:
  - type: add_constraint
    step_id: "02_system_sketch"
    path: "components"
    description: "minItems: 1"
    migration:
      action: ai_assisted
      prompt: template_infer_missing.md # Points to migration_prompts/
```

### 3. Release Process
When cutting a new release (e.g., `vX.Y.Z`):
1. Rename `changelog/unreleased.md` to `changelog/vX.Y.Z.md`.
2. Rename `changelog/unreleased.yaml` to `changelog/vX.Y.Z.yaml`.
3. Update the `version` and `release_date` fields in the YAML.
4. Add the new version to the [Version Index](#-version-index) table in this file.
5. Commit and tag.

---

## 🧠 Why this complexity?

Standard changelogs are insufficient for **AI-First capabilities**.
- **Human Changelogs** are ambiguous ("We improved validation").
- **Machine Specs** need precision ("Field X moved to Y").

By maintaining both, we enable:
1. **Self-Healing Projects**: The `specdev align` tool reads the YAML to automatically patch older `spec/*.json` files.
2. **Context-Aware Agents**: The AI knows exactly which features are available in the specific version a project is using.
