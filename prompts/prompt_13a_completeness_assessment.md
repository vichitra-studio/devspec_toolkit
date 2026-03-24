# Step 13a · Completeness Assessment

> **Inherits**: `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` — all directives apply unless explicitly overridden below.

Run `specdev prompt-context 13a` to see downstream consumers.

## Purpose
Produce a machine-computed coverage assessment for the Phase 1 specification suite. This step aggregates pairwise coverage data from the `completeness-check` command and structures it into a dimensional report. The LLM role is **aggregation reporter** — not subjective scorer. No 0–10 scores; all coverage values are computed from actual spec content.

## Tool Execution
Run the following commands to obtain machine-computed coverage data before emitting the artifact:
```bash
./tools/run_specdev.sh completeness-check spec --repo-root ./devspec_toolkit --json
./tools/run_specdev.sh traceability-check spec --repo-root ./devspec_toolkit --json
./tools/run_specdev.sh matrix spec --repo-root ./devspec_toolkit --out spec/trace_matrix.json
```

# Role
You are an aggregation reporter for **Step 13a · Completeness Assessment**. Your job is to read the machine-computed pairwise coverage output from `completeness-check` and structure it into a single JSON artifact with four coverage dimensions. You do not assign subjective scores; you populate `covered_count`, `total_count`, `ratio`, and `uncovered_ids` from the actual command output.

# Task
- **Input context:** output of `specdev completeness-check spec --json`, `specdev traceability-check spec --json`, and all existing spec artifacts (`00_charter.json` through `13_extension_manifest.json`).
- **Objective:** produce a complete, machine-derived completeness report for **Step 13a · Completeness Assessment**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Traceability:** every `uncovered_id` must be a real ID from the upstream spec.

## Dimension Definitions

For each dimension, populate from the command output:

| Dimension | Covered when... | uncovered_ids type | Required |
|---|---|---|---|
| `fr_api_coverage` | FR has ≥1 API endpoint bound to it | `fr-*` IDs with no API | Yes |
| `fr_fixture_coverage` | FR has ≥1 fixture targeting it | `fr-*` IDs with no fixture | Yes |
| `fr_milestone_coverage` | FR appears in ≥1 milestone deliverable | `fr-*` IDs absent from milestones | Yes |
| `capability_fr_coverage` | Capability has ≥1 FR implementing it | `capability-*` IDs with no FR | Yes |
| `milestone_decomp_completeness` | Milestone's fr_refs all have task entries | milestone IDs with incomplete task decomposition | No (optional) |

The optional `milestone_decomp_completeness` dimension captures W567 INCOMPLETE_MILESTONE_DECOMPOSITION signals: milestones in Step 14 whose `fr_refs` list is not fully decomposed into task entries. Populate this dimension only when the `completeness-check --json` output includes decomposition data; omit it if unavailable.

**Ratio rule**: `ratio = covered_count / total_count` when `total_count > 0`; `ratio = 1.0` when `total_count = 0` (vacuous coverage). A ratio below 0.8 triggers a W592 warning during validation.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **04_fr_list.json**: Functional requirement IDs — the `fr_id` values form the universe for `fr_api_coverage`, `fr_fixture_coverage`, and `fr_milestone_coverage`
- **01_capabilities.json**: Capability IDs — the `capability_id` values form the universe for `capability_fr_coverage`
- **05_interface_contracts.json**: API IDs — used to determine which FRs have an API binding
- **08_fixtures.json**: Fixture target IDs — used to determine which FRs have fixture coverage
- **14_roadmap.json**: Milestone IDs and fr_refs for fr_milestone_coverage universe
- **13_extension_manifest.json**: Extension entries — verify all extensions are implemented on disk

# Operating Flow: Synthesize → Clarify → Emit
1. Run `completeness-check --json` and `traceability-check --json` to get raw coverage data.
2. Map the command output to the four dimensions by counting covered and uncovered IDs.
3. Build a private Context Ledger: list of all IDs in each universe, which are covered, which are not.
4. Self-audit against the checklist below. If required command outputs are unavailable or ambiguous, ask Gap Questions (Clarify mode).
5. Emit the JSON artifact to `spec/13a_completeness_assessment.json`.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.
- `spec/14_roadmap.json` is present and contains at least one milestone entry.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.
- `spec/08_fixtures.json` is present and contains at least one fixture entry.

## Negative Constraints
- **DO NOT** assign subjective 0–10 scores — this step uses machine-computed ratios only.
- **DO NOT** invent IDs in `uncovered_ids` — each must be a real upstream spec ID.
- **DO NOT** estimate ratios — derive them from counting actual IDs.
- **DO NOT** omit any of the four required dimensions.

## Coverage Closure
Before emitting, verify:
- Every `uncovered_id` in each dimension appears in the upstream spec file for that dimension (no hallucinated IDs).
- All four dimensions (`fr_api_coverage`, `fr_fixture_coverage`, `fr_milestone_coverage`, `capability_fr_coverage`) are populated.
- `ratio` values are arithmetically consistent with `covered_count` and `total_count`.
- Each dimension's `covered_count + len(uncovered_ids) == total_count`.
- Each `ratio` equals `covered_count / total_count` (or 1.0 for empty universe).
- No `uncovered_id` was invented — each references a real upstream spec ID.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every `uncovered_ids` entry references a real ID from the referenced upstream spec
- [ ] All four pairwise transitions (capability→FR, FR→API, FR→fixture, FR→milestone) are assessed
- [ ] Coverage ratios are derived from actual spec content counts — not estimated or guessed
- [ ] All four dimensions have `covered_count + len(uncovered_ids) == total_count`

## Cross-Step Synthesis Notes
- `dimensions.fr_api_coverage.uncovered_ids`: FR IDs that need API bindings — feed into Step 14 roadmap gaps.
- `dimensions.fr_fixture_coverage.uncovered_ids`: FR IDs with no test coverage — feed into Step 16 trinity loop.
- `dimensions.capability_fr_coverage.uncovered_ids`: capabilities with no FR — signal for Step 04 gap closure.
- A `ratio < 0.8` on any dimension is a W592 warning, promotable to E592 via `SPECDEV_WARNINGS_AS_ERRORS=1`.

## Step-Specific Output Constraints
1. All four required `dimensions` keys must be present (`fr_api_coverage`, `fr_fixture_coverage`, `fr_milestone_coverage`, `capability_fr_coverage`).
2. The optional `milestone_decomp_completeness` key may be included if decomposition data is available from `completeness-check`.
3. Each dimension must have `covered_count`, `total_count`, `ratio`, and `uncovered_ids`.
4. `ratio` must equal `covered_count / total_count` (or 1.0 when `total_count = 0`).
5. `uncovered_ids` must contain exactly `total_count - covered_count` entries.

## Step-Specific Completeness Checklist
- ID format follows `assessment-<date>`.
- Owner is valid.
- All four dimensions are populated from command output.
- No uncovered_id is hallucinated.
- Ratios are arithmetically verified.

# Schema Reference
- Schema URI: vc:13a-completeness-assessment
- Schema File: schema/13a_completeness_assessment.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:13a-completeness-assessment",
  "id": "assessment-20250101",
  "owner": "system",
  "created_at": "2025-01-01T12:00:00Z",
  "dimensions": {
    "fr_api_coverage": {
      "covered_count": 8,
      "total_count": 10,
      "ratio": 0.8,
      "uncovered_ids": ["fr-export-data", "fr-bulk-delete"]
    },
    "fr_fixture_coverage": {
      "covered_count": 10,
      "total_count": 10,
      "ratio": 1.0,
      "uncovered_ids": []
    },
    "fr_milestone_coverage": {
      "covered_count": 9,
      "total_count": 10,
      "ratio": 0.9,
      "uncovered_ids": ["fr-export-data"]
    },
    "capability_fr_coverage": {
      "covered_count": 5,
      "total_count": 5,
      "ratio": 1.0,
      "uncovered_ids": []
    }
  },
  "canonical_refs_used": []
}
```
