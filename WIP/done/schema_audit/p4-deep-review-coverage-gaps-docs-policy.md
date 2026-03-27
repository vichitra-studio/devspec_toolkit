# Deep Review: coverage_gaps and docs_policy

Date: 2026-03-19

---

## Q1: coverage_gaps -- is it ever populated?

### Evidence from spec files

Only one spec file exists: `spec/05_interface_contracts.json`. It contains `"coverage_gaps": []` (empty).

### Evidence from test fixtures

Every single test fixture across all steps (120+ files) contains `"coverage_gaps": []`. Not a single fixture anywhere in the repository has a non-empty `coverage_gaps` array. Confirmed via regex search for `"coverage_gaps": [` followed by anything other than `]` -- zero matches.

The sole exception is the **unit tests for cross-step validation** (`tests/unit/validation/validators/test_r9_cross_step.py` and its duplicate `test_cross_step_validation.py`), which construct inline test data with non-empty `coverage_gaps` arrays to verify that `validate_step_12` correctly validates `upstream_item_id` references against upstream FR/NFR files.

### Evidence from prompts

Every prompt (00 through 16c) includes the boilerplate:

> Any output field whose value cannot be traced to a specific upstream artifact or seed document
> MUST be recorded in `coverage_gaps[]` with:
> - `upstream_item_id`: the ID of the upstream item that should have provided the data
> - `source_step`: the step number where the data was expected
> - `reason`: why the value could not be traced

And every prompt's JSON example template shows `"coverage_gaps": []` (empty).

So prompts **instruct** LLMs to populate it when tracing fails, but the example output is always empty, and there is no worked example of a non-empty array anywhere.

### Evidence from validators

`step_12.py` (`validate_step_12`) is the **only validator** that reads `coverage_gaps`. It does two things:
1. Iterates `instance.get("coverage_gaps", [])` and checks each gap's `upstream_item_id` against upstream FR/NFR ID sets (E590 if dangling).
2. This is purely cross-reference validation -- it does not check whether coverage_gaps *should* be populated.

No other step validator reads or validates `coverage_gaps`. No linter checks whether it should be non-empty. No tool computes it.

### Schema definition

Defined in `schema/core/collections.schema.json` as `coverageGapsArray` / `coverageGap`:
- Required fields: `upstream_item_id`, `source_step` (pattern `^[0-9]{2}[a-c]?$`), `reason` (minLength 10)
- `minItems: 0` -- explicitly allows empty

Listed as `required` in every step schema (e.g., `12_ci_gates.schema.json` line 182).

### Verdict

**coverage_gaps is effectively dead.** It is:
- Required by schema but always empty in every real spec and every test fixture
- Instructed in prompts but never demonstrated with actual content
- Only consumed by one validator (step_12) which validates references *within* it but never checks whether it *should* contain entries
- Never computed or populated by any tool in the pipeline

It is in the same category as `generation_quality` and `seed_refs` -- structurally present everywhere, functionally inert. The field's original design intent (record untraceable content) is sound, but in practice:
1. LLMs following the Clarify->Emit protocol ask questions rather than emitting gaps
2. No validator warns when coverage_gaps is suspiciously empty
3. No downstream tool or report consumes it

If it were removed, step_12's cross-reference check (lines 67-72) would simply stop iterating an always-empty array. Zero functional impact.

**Recommendation**: Either (a) remove it from required arrays across all schemas and stop including it in prompts/fixtures, or (b) add a linter that actually detects when it *should* be populated (making it earn its keep). Option (a) is simpler and honest.

---

## Q2: docs_policy -- if no prompts consume it, why have tooling for it?

### What docs_lint.py actually checks

The linter (`tools/specdev_tools/validation/docs_lint.py`) does the following:
1. Loads `spec/common/seed_manifest.json` and reads its `docs_policy` object
2. If `root_readme_required` is true, checks for `README.md` at the project root
3. If `readme_required` is true, walks each directory listed in `scope`, applying `readme_depth_default` and `readme_depth_by_scope` overrides to decide how many levels deep to require README files
4. Respects `exclusions` (skips node_modules, .git, tests/fixtures, etc.)

It emits E520 errors for missing READMEs.

### What values does docs_policy actually have?

From `spec/common/seed_manifest.json`:
```json
"docs_policy": {
    "readme_required": true,
    "root_readme_required": true,
    "readme_depth_default": 0,
    "readme_depth_by_scope": {},
    "scope": ["devspec_toolkit/"],
    "exclusions": [
        "devspec_toolkit/node_modules/",
        "devspec_toolkit/.git/",
        "devspec_toolkit/.venv/",
        "devspec_toolkit/__pycache__/",
        "devspec_toolkit/dist/",
        "devspec_toolkit/build/",
        "devspec_toolkit/coverage/",
        "devspec_toolkit/tests/fixtures/",
        "devspec_toolkit/tools/specdev_tools.egg-info/"
    ],
    "doc_paths": ["docs/**", "README.md", "CHANGELOG.md"]
}
```

With `readme_depth_default: 0` and empty `readme_depth_by_scope`, this policy effectively says: "require a README at the project root and at each scope root directory, but nowhere deeper." That is functionally equivalent to "require a root README."

### Is docs_policy configurable in a meaningful way?

**Yes, but only in theory.** The schema supports:
- `readme_depth_by_scope`: e.g., `{"docs/": 2, "src/": 1}` would require READMEs at docs/, docs/*/*, and src/*
- `scope`: can target specific directories
- `exclusions`: can skip directories

A monorepo with multiple packages could configure `scope: ["packages/"]` with `readme_depth_by_scope: {"packages/": 1}` to enforce READMEs in each package. That is a legitimate use case.

### Is it consumed by prompts?

Only one prompt references `docs_policy`: `prompt_16a_impl_planner.md` (line 246), which instructs the LLM to update `docs_policy.readme_depth_by_scope` when introducing new directories. This is a governance instruction, not a consumption of the policy for generation.

No prompt reads docs_policy to decide what to generate.

### Could docs_lint hardcode "require a root README"?

Yes, trivially. The current actual configuration with `readme_depth_default: 0` does almost exactly that. But hardcoding would lose the ability to enforce deeper README requirements per-scope, which is the only non-trivial feature of docs_lint.

### Would a project ever configure docs_policy differently?

Plausible scenarios:
1. **Monorepo**: `scope: ["packages/", "services/"]`, `readme_depth_by_scope: {"packages/": 1, "services/": 2}` -- require READMEs in each package and two levels deep in services
2. **Docs-heavy project**: `readme_depth_default: 2` -- require READMEs in every top-level and second-level directory
3. **Minimal project**: `readme_required: false` -- skip the check entirely

These are valid but speculative. No evidence any consumer project has ever used anything other than the defaults.

### Verdict

**docs_policy is over-engineered for its current usage, but not entirely without value.**

Current state:
- The schema defines 7 required fields for docs_policy
- The actual configuration uses trivial defaults (depth 0, empty depth overrides)
- Only one prompt mentions it (and only as a governance note)
- docs_lint is 120 lines of code to enforce what is currently "check for root README"

Three options, in order of simplicity:

1. **Simplify to convention**: Hardcode "require root README" in docs_lint. Remove docs_policy from seed_manifest schema. Delete ~80 lines of depth/scope walking code. This matches actual usage.

2. **Keep but make optional**: Remove docs_policy from `required` in seed_manifest schema. If absent, fall back to "require root README." Projects that need depth enforcement can opt in. This preserves the feature without forcing empty boilerplate.

3. **Keep as-is**: Defensible if the team expects multi-scope/depth usage in future consumer projects. But currently, the complexity is not justified by any real usage.

**Recommendation**: Option 2. Make docs_policy optional with sensible defaults. If a project omits it, docs_lint checks for a root README only. If a project provides it, the full depth/scope engine activates. This eliminates boilerplate for simple projects while preserving the feature for complex ones.
