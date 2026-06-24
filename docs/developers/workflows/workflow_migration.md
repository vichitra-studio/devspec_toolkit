# Migration & Upgrade Workflow

The DevSpec Toolkit evolves rapidly. When you update the toolkit submodule (e.g., `git submodule update --remote`), schemas may become stricter, steps might be renumbered, or paradigms might shift.

> [!TIP]
> The `specdev align` CLI automates most of this process.

This guide explains how to use the automated alignment system. For the legacy manual approach, see [Manual Fallback](#manual-fallback-legacy).

## Prerequisites

Activate the virtual environment before running any `specdev` commands:

```bash
source devspec_env/bin/activate
```

> [!NOTE]
> The environment name is `devspec_env`. If you are running via `./tools/run_specdev.sh` the wrapper handles venv activation automatically.

## The Alignment Workflow (Recommended)

The **Alignment System** is the standard way to upgrade. It calculates the difference between your current specs and the new toolkit version, then helps you close the gap.

Detailed usage guide: **[Workflow: System Alignment & Migration](./workflow_align.md)**.

### Quick Summary

1.  **Check Status**: `specdev align status`
2.  **See Changes**: `specdev align diff`
3.  **Auto-Fix**: `specdev align apply --auto` (Renames files, updates schemas)
4.  **AI-Assist**: `specdev align prompts` (Generates prompts for complex changes)
5.  **Validate**: `specdev align validate`

---

## When Should You Update?

Since updates can be breaking, updating the toolkit is a strategic decision.

| Update Condition | Recommended Scenario |
| :--- | :--- |
| **Start of a Milestone** | **Ideal.** You have a clean slate to fix spec drift before implementation logic is written. |
| **Need New Capabilities** | You explicitly need new steps (e.g., `Red Teaming`) or new metadata fields supported by updated schemas. |
| **Tooling Issues** | You are hitting bugs in the CLI or unexpected validation failures that are fixed in newer versions. |
| **Prompt Decay** | Your AI agents are struggling. Newer toolkit versions often carry significantly verified Prompts that degrade less. |

> [!CAUTION]
> Avoid updating **mid-sprint** or days before a **deadline**. Migration requires time to "re-align" your specs.

---

## Manual Fallback (Legacy)

If the `specdev align` tool is unavailable or failing for your specific case, use this manual loop.

### 1. Update & Validate
First, update the toolkit and run the full validation suite to see what broke.

```bash
# Update the submodule
git submodule update --remote devspec_toolkit

# Run validation across the entire spec
# (or substitute the unified spec-check gate, which resolves project canon:
#  ./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .)
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

### 2. Triage The Breaks
Group the errors into three categories:
*   **Syntax/Minor:** Renamed fields or missing required metadata.
*   **Structural:** New arrays, nested objects, or split steps.
*   **Renumbered Steps:** e.g., Step 13 becoming Step 15.

### 3. Migrate Step-by-Step
Migrate files in dependency order (00 -> 16c).

#### Strategy A: Manual Quick-Fix
If the error is simple (e.g., `desc` -> `description`), manually edit the JSON.

#### Strategy B: AI-Assisted Re-Synthesis
For complex breaks:
1.  **Locate the New Prompt** (`devspec_toolkit/prompts/prompt_XX.md`).
2.  **Paste Old JSON** as context.
3.  **Ask AI**: "Re-emit this step as valid JSON that satisfies the new schema."

### 4. Handling Renumbered Steps
1.  **Rename the file** manually.
2.  **Update References** in all other JSON files (`links`, `trace_refs`).
3.  **Validate**.

---

## The Role of Versioning

The DevSpec Toolkit uses a **Rolling Release** model via Git Submodules.

### How to Stay Stable
If you are mid-sprint:
1.  **Pin the Submodule**: Do not run `git submodule update`.
2.  **Use Git Tags**: Checkout a specific definition.

```bash
# In devspec_toolkit directory
git checkout <stable_commit_hash>
```

We **strongly recommend** keeping up to date. "Breaking" changes usually fix logical holes in your specs.
