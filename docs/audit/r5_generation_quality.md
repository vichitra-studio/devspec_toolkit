<review_prompt id="R5" areas="9" runs_after="R1,R2,R3,R4" priority="P1-high">
# Review R5: Generation Quality Self-Report — Write-Only Metadata Audit

## Scope
**Area 9 only**: `generation_quality` block audit — 7 sub-fields, 5 confirmed write-only.

This review has a mandatory decision gate before any implementation:
**Choose option (a), (b), or (c)** based on investigation findings, then implement.

- **(a) Remove entirely** — eliminate `generation_quality` from schema, replace with independent scans
- **(b) Reduce** — keep only `assumptions` field (partial value), eliminate the rest
- **(c) Make consumable** — add validators that actually gate on `preflight_passed`, cross-check `unresolved_inputs`, require specific `self_check_results`

This is a **breaking schema change** regardless of option chosen — triggers v0.4.0 migration.

**Prior reviews completed**: R1, R2, R3, R4. R5 only touches `collections.schema.json`, `spec_quality_lint.py`, `pyproject.toml`, migration scripts, and prompts. It does NOT modify `validate.py` or the validation registration chain.

---

## Files Under Review

| File | Key Lines |
|------|-----------|
| `schema/core/collections.schema.json` | 385-464 (generationQuality definition) |
| `tools/specdev_tools/validation/spec_quality_lint.py` | 94-151 (only code reading generation_quality) |
| `tools/specdev_tools/validation/validators/` | all step validators — search for generation_quality reads |
| `prompts/` | all prompts — search for generation_quality instructions |
| `tools/specdev_tools/migration/planner.py` | migration tooling — understand how schema changes propagate |
| `tools/specdev_tools/migration/runner.py` | migration runner |
| `tools/pyproject.toml` | current version (0.3.0) — confirm v0.4.0 bump needed |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- Main agent ONLY: read subagent summaries, make the option decision (a/b/c), create impl tasks
- **DECISION GATE**: Main agent must make option choice before launching Phase 2
- Token budget for main agent: < 3K tokens per session (this is the most focused review)

### Subagent Assignment

#### Phase 1 — Investigation (2 Explore subagents)

**Subagent A** (`Explore`, no isolation) — Field Consumption Audit:
```
Perform a complete field-by-field consumption audit of generation_quality.

1. Read schema/core/collections.schema.json lines 380-470
   - List all generation_quality sub-fields and their schema definitions
   - Which sub-fields are required vs optional?

2. Search ALL files in tools/specdev_tools/validation/validators/ for "generation_quality",
   "preflight_passed", "evidence_records", "placeholder_scan", "unresolved_inputs",
   "assumptions", "self_check_results"
   - For each match: is it reading the field or just passing it through?

3. Read tools/specdev_tools/validation/spec_quality_lint.py lines 90-155
   - Lines 94-114: _check_placeholder_scan_agreement() — does it read placeholder_scan.tokens_found?
   - Lines 117-151: assumptions section — does it read the assumptions array or scan free text?
   - Does any code in this file read: preflight_passed, evidence_records, unresolved_inputs,
     has_placeholders, self_check_results?

4. For each of the 7 sub-fields, produce a row:
   | sub-field | schema type | required? | read by any code? | which file/line? |

5. Count: total lines of generation_quality instructions across ALL prompts
   (search prompts/ for "generation_quality", "preflight_passed", "self_check_results")
   — approximate line count, not exact.

Report: the complete field consumption table + prompt instruction line count.
```

**Subagent B** (`Explore`, no isolation) — Migration Impact Assessment:
```
Assess the cost of each option (a/b/c):

1. Read tools/specdev_tools/migration/planner.py and runner.py — understand the migration system.
   - How does a schema version bump work?
   - What does the migration runner do to existing spec artifacts?
   - Would removing generation_quality require a migration script? What would it do?

2. Count all spec artifacts in spec/ that contain generation_quality fields
   - How many .json files in spec/ have "generation_quality"?
   - Approximate migration scope.

3. Read tools/pyproject.toml — confirm current version is 0.3.0

4. For each option, estimate:
   (a) Remove entirely: migration removes generation_quality from all artifacts. N artifacts affected.
       Independent scan infrastructure already in place? What would need to change in validators?
   (b) Reduce to assumptions only: migration removes all sub-fields except assumptions.
       Which validators would lose useful data?
   (c) Make consumable: no schema removal. What code needs to be written to actually gate on
       preflight_passed? How many validators need updating?

Report: migration scope per option and implementation effort per option.
```

#### DECISION GATE (Main Agent)

After Phase 1 completes, main agent reads both summaries and selects option based on:
- If > 3 sub-fields are truly write-only → prefer option (a) or (b)
- If migration scope is small (< 20 artifacts) → option (a) preferred
- If migration scope is large (> 50 artifacts) → option (b) is practical compromise
- If the team uses generation_quality for manual review (not automated) → option (c)

Document the decision with reasoning before launching Phase 2.

#### Phase 2 — Implementation (after decision)

The Phase 2 subagents below are written for option (b) as the default.
If option (a) or (c) is chosen, adapt the instructions and use the corresponding task IDs (Ta*/Tc*).

**Subagent C** (`general-purpose`, isolation: `worktree`) — Schema Update [Option B]:
```
Implement the schema reduction for option (b): keep only `assumptions`, remove all other
generation_quality sub-fields.

1. schema/core/collections.schema.json:
   - In the generationQuality definition, remove all sub-fields EXCEPT "assumptions"
   - Keep "assumptions" as the single retained field
   - Update the "required" array to reflect the new schema
   - Add a comment: "# v0.4.0: reduced from 7 sub-fields to assumptions-only"

2. tools/specdev_tools/validation/spec_quality_lint.py:
   - Remove _check_placeholder_scan_agreement() (lines 94-114) — independent E510 scan replaces it
   - Remove E511 error code emission (the circularity is eliminated)
   - Keep the assumptions content scanning logic (lines 117-151) — this has genuine value
   - Update any references to removed sub-fields

3. tools/pyproject.toml:
   - Bump version from "0.3.0" to "0.4.0"

4. tools/specdev_tools/core/errors.py:
   - If E511 exists, mark it as deprecated/removed with a comment

Run: pytest tests/ -k quality -v and confirm pass.
```

**Subagent D** (`general-purpose`, isolation: `worktree`) — Migration Script:
```
Create a migration script for v0.3.0 → v0.4.0 that removes write-only generation_quality fields.

1. Create tools/specdev_tools/migration/scripts/v0_3_to_v0_4.py:
   - Read each spec artifact in spec/
   - If generation_quality exists, keep ONLY the "assumptions" sub-field
   - Remove: preflight_passed, evidence_records, placeholder_scan, unresolved_inputs, self_check_results
   - Write back the modified artifact
   - Print summary: N artifacts updated, M fields removed

2. Register the migration script in tools/step_order.json or migration config (follow existing pattern)

3. Test the migration script against a fixture:
   - Create tests/fixtures/migration/v0_3_generation_quality_full.json with all 7 sub-fields
   - Run migration, verify only "assumptions" remains

Run: pytest tests/ -k migration -v
```

**Subagent E** (`general-purpose`, isolation: `worktree`) — Prompt Cleanup:
```
Remove generation_quality instructions for deleted fields from all prompts.

For each prompt in prompts/ that contains generation_quality instructions:
1. Remove instructions for: preflight_passed, evidence_records, placeholder_scan,
   unresolved_inputs, has_placeholders, self_check_results
2. Keep instructions for: assumptions (the one retained field)
3. If the generation_quality section becomes trivial after removal, replace with:
   "Populate generation_quality.assumptions with any assumptions made during generation.
   Be specific: list each assumption as a testable claim."

Do not touch any other parts of the prompts.
Count: how many prompts were updated and how many lines were removed total.
```

#### Phase 3 — Integration (after Phase 2)

**Subagent F** (`general-purpose`, no isolation):
```
Run full validation suite after v0.4.0 changes:
1. pytest tests/ --tb=short -q
2. ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
3. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
Report: pass/fail counts. Flag any E511 references that weren't cleaned up.
Note any spec artifacts that failed validation after the generation_quality schema change.
```

---

## Investigation Checklist

- [ ] Which generation_quality sub-fields are read by any validator or tool?
- [ ] Is placeholder_scan.tokens_found the only consumed sub-field (via E511)?
- [ ] Does E511 add detection value beyond E510 independent scan?
- [ ] How many spec artifacts in spec/ contain generation_quality?
- [ ] How many prompt lines reference generation_quality sub-fields that would be removed?
- [ ] Does the migration runner support schema field removal?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Decision Record (required before Part B — main agent writes this after Phase 1)
```
Option: (a) remove | (b) reduce | (c) make consumable
Reason: [one sentence]
Migration scope: N spec artifacts, M prompt lines
Version bump: 0.3.0 → 0.4.0
```

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R5-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code, one block per finding.

### Part B: Implementation Plan

**VERIFIED STRUCTURE NOTES (from codebase audit):**
- `tools/specdev_tools/migration/scripts/` directory does NOT exist — any migration script task must first create this directory (`mkdir -p tools/specdev_tools/migration/scripts/`)
- `tools/specdev_tools/core/errors.py` was already modified by R3 (E211) and R4 (E561/562/563). R5 only marks E511 deprecated. Read current state first, add deprecation comment only.

Main agent selects the correct option branch after the decision gate.

---
#### Option (a): Remove entirely

Task IDs use `Ta` prefix to distinguish from other options.

| ID | Pri | Deps | File | Change summary | Acceptance command |
|----|-----|------|------|----------------|--------------------|
| Ta01 | P0 | — | `schema/core/collections.schema.json` | Remove entire generationQuality definition | `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` |
| Ta02 | P0 | Ta01 | `tools/specdev_tools/validation/spec_quality_lint.py` | Remove entire generation_quality block incl. _check_placeholder_scan_agreement, E511 | `pytest tests/test_spec_quality_lint.py -v` |
| Ta03 | P1 | Ta02 | `tools/specdev_tools/core/errors.py` | Mark E511 as REMOVED in v0.4.0 (read current state first) | `python -c "from specdev_tools.core.errors import *"` |
| Ta04 | P0 | Ta01 | `tools/pyproject.toml` | Bump version to 0.4.0 | check version string |
| Ta05 | P0 | Ta01 | `tools/specdev_tools/migration/scripts/v0_3_to_v0_4.py` | `mkdir -p` + create script that strips entire generation_quality key | `pytest tests/test_migration_runner.py -v` |
| Ta06 | P0 | Ta01,Ta02 | `tests/test_spec_quality_lint.py` | Update tests for removed block | `pytest tests/test_spec_quality_lint.py -v` |
| Ta07 | P2 | Ta01 | Each prompt file with generation_quality sections | One task per prompt (identified in Phase 1) | manual review |
| Da01 | P3 | Ta04 | `CHANGELOG.md` | v0.4.0 entry | — |

---
#### Option (b): Reduce to assumptions only (DEFAULT)

Task IDs use `Tb` prefix. This is the default option.

| ID | Pri | Deps | File | Change summary | Acceptance command |
|----|-----|------|------|----------------|--------------------|
| Tb01 | P0 | — | `schema/core/collections.schema.json` | Remove all generationQuality sub-fields except `assumptions` | `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` |
| Tb02 | P1 | Tb01 | `tools/specdev_tools/core/errors.py` | Mark E511 as deprecated (read current state first — R3+R4 already modified) | `python -c "from specdev_tools.core.errors import *"` |
| Tb03 | P0 | Tb01 | `tools/specdev_tools/validation/spec_quality_lint.py` | Remove E511 / _check_placeholder_scan_agreement() | `pytest tests/test_spec_quality_lint.py -v` |
| Tb04 | P0 | Tb01,Tb03 | `tests/test_spec_quality_lint.py` | Update tests for removed fields and removed E511 check | `pytest tests/test_spec_quality_lint.py -v` |
| Tb05 | P0 | Tb01 | `tools/pyproject.toml` | Bump version to 0.4.0 | `python -c "import tomllib; import pathlib; d=tomllib.loads(pathlib.Path('tools/pyproject.toml').read_text()); assert d['project']['version']=='0.4.0'"` |
| Tb06 | P0 | Tb01 | `tools/specdev_tools/migration/scripts/v0_3_to_v0_4.py` | `mkdir -p` + create script that strips all sub-fields except assumptions | `pytest tests/test_migration_runner.py -v` |
| Tb07 | P2 | Tb01 | Each prompt file with generation_quality multi-field instructions | One task per prompt (Phase 1 identifies exact list) | manual review |
| Db01 | P3 | Tb05 | `CHANGELOG.md` | v0.4.0 entry | — |
| Db02 | P3 | Tb06 | `docs/developers/` | Migration guide — update or create | — |

---
#### Option (c): Make consumable

Task IDs use `Tc` prefix.

| ID | Pri | Deps | File | Change summary | Acceptance command |
|----|-----|------|------|----------------|--------------------|
| Tc01 | P0 | — | `tools/specdev_tools/validation/spec_quality_lint.py` | Add preflight_passed gate + unresolved_inputs cross-check | `pytest tests/test_spec_quality_lint.py -v` |
| Tc02 | P0 | Tc01 | `tests/test_spec_quality_lint.py` | Tests for new gates | `pytest tests/test_spec_quality_lint.py -v` |
| Tc03 | P1 | — | `schema/core/collections.schema.json` | Add required check_ids enum to self_check_results | `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit` |
| Tc04 | P1 | Tc01 | Each prompt | Add "verify upstream preflight_passed is true" rule (one task per prompt) | manual review |
| Dc01 | P3 | — | `CHANGELOG.md` | v0.4.0 minor entry | — |

---

## Anti-Patterns
- Do not remove `assumptions` — it has genuine downstream value via content scanning
- Do not remove E510 independent placeholder scan — it is the source of truth
- Do not implement option (c) without concrete gating logic (adding validators that ACTUALLY gate)
- If choosing option (a), verify E510 scan is sufficient replacement BEFORE removing schema fields
- Version bump to 0.4.0 must happen alongside schema change — not separately

---

## Phase 4: Self-Verification Loop

After drafting Decision Record + Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md` (Phase 4).

Extra check for this review:
- CHECK 8 — Decision backed by evidence: the chosen option must cite the migration scope count from Phase 1 Subagent B findings. "Token waste" must be quantified (lines × steps × artifacts).
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r5_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md` (Phase 5). Include the Decision Record before Part A.

---

## Phase 6: Post-Implementation Verification

Run in a separate session after all Part B tasks are executed.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md` (Phase 6).
Key commands for this review:
```
pytest tests/ -k "quality or migration" -v
pytest tests/ --tb=short -q
./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
```
Also verify: no spec artifact in spec/ fails validation due to the schema change (collections.schema.json removal of fields must not break existing artifacts via `additionalProperties`).

</review_prompt>
