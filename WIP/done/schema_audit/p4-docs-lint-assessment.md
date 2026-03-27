# docs_lint Assessment

**Date**: 2026-03-19
**File**: `tools/specdev_tools/validation/docs_lint.py` (122 lines)

---

## What docs_lint checks (exact behavior)

1. Loads `spec/common/seed_manifest.json` and reads its `docs_policy` section.
2. If `root_readme_required` is true, checks that `README.md` exists at project root.
3. If `readme_required` is true, walks every directory listed in `scope`, respecting `exclusions`, and verifies that a `README.md` exists in each directory up to a configurable depth (`readme_depth_default`, overridden per-scope via `readme_depth_by_scope`).
4. All violations emit error code **E520** (shared with seed-lint manifest-missing errors).

That is the entire scope. It does not check README content, formatting, staleness, or links. It is purely a file-existence check.

## What it is NOT checking

- It checks **generic repo directory READMEs**, not spec artifacts.
- It does not validate any spec JSON file.
- It does not validate any prompt, schema, or canonical registry entry.
- It has zero interaction with the spec pipeline steps (00-16c).
- It is not referenced in `step_order.json`.

## Where it is wired in

- **CLI**: registered as `docs-lint` subcommand in `cli.py`.
- **CLAUDE.md**: listed in the "Validation Ritual" as step 3 ("docs-lint for README coverage").
- **Prompt 12 (CI Gates)**: listed as one of the CI gate commands.
- **Schema**: `docs_policy` is a **required** property in `seed_manifest.schema.json`.

## Is it part of the spec pipeline?

No. The spec pipeline (steps 00-16c) produces and validates JSON artifacts in `spec/`. docs_lint validates that directories in a configurable scope list contain `README.md` files. It is a repo-hygiene tool bolted onto the seed manifest.

## Does removing it break any spec workflow step?

No spec step produces or consumes docs_policy data. Removing docs_lint would require:

1. Removing the CLI subcommand (trivial).
2. Removing it from the validation ritual in CLAUDE.md.
3. Removing the reference in prompt_12_ci_gates.md.
4. Making `docs_policy` optional (not required) in `seed_manifest.schema.json`, or removing it entirely.
5. Removing the field from `spec/common/seed_manifest.json`.

No spec validation, traceability, or generation step would break.

## Verdict: is docs_lint scope creep?

**Yes, it is scope creep.** Reasoning:

- The devspec toolkit's purpose is spec-driven development: schema validation, traceability, canonical integrity, and pipeline governance. docs_lint does none of these.
- It enforces a generic repo convention (directories must have READMEs) that has nothing to do with spec correctness.
- It is parasitically attached to the seed manifest, which otherwise serves a clear spec-pipeline purpose (declaring seed documents and step requirements). `docs_policy` is conceptually unrelated to seed management.
- It reuses error code E520 (seed/manifest errors) rather than having its own code range, suggesting it was added opportunistically rather than designed into the error taxonomy.
- The check is shallow (file existence only), making its value low even as a repo-hygiene tool.

**Recommendation**: Extract `docs_policy` from `seed_manifest.json` and `docs_lint` from the toolkit, or demote it to an optional plugin/contrib tool. If kept, it should at minimum get its own error code range and not be a required field in the seed manifest schema.
