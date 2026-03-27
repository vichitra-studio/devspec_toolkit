# Review: Group 4 (P1-E + P1-F + P2)

## p1-prompt-error-collection.md

### Issues Found

1. **MUST_FIX — "spot-check 5-6 validators" is not fully named.** Q6 names 5 validators (step_05, step_08, step_14, step_16, step_16a) but Q11 says "at least 3 validators and 2 linters" without naming which ones. An agent could pick overlapping or trivial targets. Q11 should name specific validators and linters (e.g., step_01, step_06, step_12 for validators; seed_lint, hallucination_lint for linters) to ensure coverage of different error formatting patterns.

2. **SHOULD_FIX — Line 14 says "don't read all 21" but ground truth section 4.2 lists exactly 21 DEEP_VALIDATORS entries; the prompt's parenthetical "(don't read all 21)" is fine but the scope instruction on line 14 says "spot-check 5-6 validators" while Q6 only names 5 and Q11 implies 3 more.** The scope header and question lists should agree on a single number. Recommend: name exactly 5 validators in the scope section and reuse those same 5 in both Q6 and Q11.

3. **SHOULD_FIX — PROMOTABLE_PAIRS list order differs from ground truth.** P1-E line 28 lists pairs in this order: W550, W560, W561, W562, W563, W571, W572, W573, W580, W581, W150, W590, W591, W592, W593, W594, W595, W597. Ground truth section 6.1 lists them in the same order. Verified: this is accurate — no issue. (Retracted.)

4. **MINOR — validate.py line reference for iter_errors.** P1-E says "validate.py line 136" (line 25). Ground truth section 6.2 confirms line 136. Clean.

5. **SHOULD_FIX — R9 W->E promotion line reference.** P1-E line 33 says "R9 added W->E promotion via PROMOTABLE_PAIRS at validate.py line 267." Ground truth section 11 shows two R9/T26 markers: validate.py:263 (extraction intent validation) and validate.py:267 (W->E promotion). The prompt conflates these — line 267 is specifically the promotion, but T26 covers both extraction intent AND promotion. The prompt should note both lines (263 and 267) or clarify it refers only to the promotion aspect.

6. **MINOR — errors.py "3 exception classes" naming.** P1-E line 32 names all three (SpecdevError, SubmoduleDetectionError, SchemaRegistryError), matching ground truth section 6.1. Clean.

7. **SHOULD_FIX — Missing canonical/ error return pattern guidance.** Line 17 includes canonical/integrity.py and canonical/lint.py in scope but no question specifically asks about their error return patterns. Q11 says "at least 3 validators and 2 linters" — canonical modules are neither validators nor linters in the strict sense. Add a question (e.g., Q6b) specifically about canonical module error return types.

8. **MINOR — "77 error codes total: 52 E-codes, 25 W-codes" matches ground truth exactly.** Clean.

9. **MINOR — "--json flag exists on validate and traceability-check only (2 of 25 commands)" matches ground truth section 3.3.** Clean.

### Clean

- DEEP_VALIDATORS name and entry count (21) — correct per ground truth section 4.2.
- cli.py LOC (757), validate.py LOC (537), canonical/integrity.py LOC (640), canonical/lint.py LOC (472) — all match ground truth section 2.1.
- 25 subcommands — correct per ground truth section 3.1.
- errors.py LOC (186) — correct per ground truth.
- 7 non-promotable W-codes list — correct per ground truth section 6.1.
- 12 warnings.warn call sites — correct per ground truth section 10.4.
- iter_errors() marked as "VERIFIED, skip this question" — good scope control.
- Scope boundary clearly excludes module structure (P1-B2) and test quality (P1-D).

---

## p1-prompt-gaps-regressions.md

### Issues Found

1. **MUST_FIX — R9 markers: prompt says "12 markers" (line 32) but ground truth section 11 lists 12 source locations.** The prompt line 32 says "R9 markers in 12 source locations" — this matches. However, ground truth verification summary row says "R9 markers in source: 13 (12 listed) vs 12 → verified 12." P1-F is correct at 12. Clean on count.

2. **MUST_FIX — R9 test files: prompt says "10 files, 4,740 LOC total" (line 35).** Ground truth section 2.2 lists the 10 test_r9_* files. Let me verify LOC sum: 286+1047+461+84+459+648+584+263+433+475 = 4,740. Correct. Clean.

3. **SHOULD_FIX — P1-F line 24 says "Step 16 schema: 1868 lines, max nesting depth 19, has 4 $defs."** Ground truth section 7.3 confirms 1868 lines, nesting depth 19, 4 $defs. But P1-F also says "17 top-level properties" on line 48 — ground truth confirms 17. Clean on these facts. However, P1-F line 24 claims nesting depth 19 while the actual question Q4 on line 48 says "1868 lines, 17 top-level properties" — the nesting depth is not repeated in Q4 context. This is fine — it is in Known Context.

4. **SHOULD_FIX — Step 00 schema: P1-F line 25 says "202 lines, max nesting depth 8, 21 top-level properties."** Ground truth section 7.1 confirms 202 lines, nesting depth 8, 21 properties. Clean.

5. **MUST_FIX — P1-F line 48 says the 16a/16b/16c validators are "46/45/47 LOC."** Ground truth section 2.1: step_16a.py=46 LOC, step_16b.py=45 LOC, step_16c.py=47 LOC. Correct.

6. **SHOULD_FIX — Q5 says "Cross-reference the 23 _load_* functions (ground truth section 4.3) against step_order.json dependencies."** The question names specific checks: "at least step_08 (loads from 04, 05, 06, 07) and step_14 (loads from 01, 04, 09)." Ground truth section 4.3 shows step_08 loads: _load_fr_ids (from step 04), _load_api_ids (from step 05), _load_inv_ids (from step 06), _load_nfr_ids (from step 07). Step_14 loads: _load_step09_milestone_ids, _load_step09_tech_stack_names (from 09), _load_step04_fr_ids (from 04), _load_step01_cap_ids (from 01). The prompt's parenthetical claims match. Clean.

7. **SHOULD_FIX — Q16 references "cli.py (lines 166-175 per ground truth)."** Ground truth section 3.1 shows: env-check (line 167), dag-lint (line 170), extraction-intent-check (line 173). Line 166 is the R9 comment marker (section 11: cli.py:166 "# R9: New commands"). So lines 166-175 covers the R9 new commands block. The range 166-175 is reasonable but imprecise — the last command at line 173 plus its args could extend to ~175. This is a minor approximation. Acceptable but could be tightened.

8. **SHOULD_FIX — Scope overlap risk with P1-A (registry consistency).** P1-F line 8 explicitly excludes "registry-to-filesystem consistency (P1-A covers that)." However, Q9 asks "What happens when schema_registry.json references a schema file that doesn't exist on disk?" — this is borderline registry-filesystem consistency. The question is framed as an edge case (what happens at runtime) rather than a static consistency check, so it is defensible, but the boundary should be noted more explicitly to prevent the agent from doing a full registry audit.

9. **MINOR — Version mismatch noted (line 36): "CLAUDE.md says 0.3.0, pyproject.toml has 0.4.0."** Matches ground truth section 9.3. Clean.

10. **MINOR — "one noqa in validators/__init__.py line 7" (line 28).** Ground truth section 10.2 confirms: `validators/__init__.py:7`. Clean.

### Clean

- 21 step validators, NO step_00 validator — correct per ground truth sections 4.1-4.2.
- 22 steps in step_order.json — correct per ground truth section 2.5.
- Schema registry 29 entries — correct per ground truth section 2.4.
- 24 schema files (19 step + 4 core + 1 seed_manifest) — correct per ground truth section 2.3.
- 23 _load_* functions — correct per ground truth section 4.3.
- Zero TODOs in specdev_tools/, one in tools/core/json_utils.py — correct per ground truth section 10.1.
- Zero skip/xfail — correct per ground truth section 10.3.
- R9 task IDs (T18, T20, T22, T24, T26, T28) — correct per ground truth section 11.
- R9 new CLI commands (dag-lint, extraction-intent-check, env-check) — correct per ground truth section 11.
- Scope exclusions clearly stated for P1-B, P1-D, P1-A.

---

## p2-prompt-research-alignment.md

### Issues Found

1. **MUST_FIX — "Known Current State" section claims to be "ALL from verified ground truth" but introduces claims not in ground truth.** Specifically:
   - Line 46: "All step schemas use `$ref` to core schemas (atoms, collections, errors, canon)" — ground truth section 7 only verified $ref usage for steps 00, 05, and 16. The claim "all step schemas" is an extrapolation. The agent should spot-check rather than assume this is verified.
   - Line 50: "`additionalProperties: false` confirmed at root and nested objects (checked on step 00 and step 05)" — this correctly scopes to the two checked schemas and is fine.
   - Line 52: "`description` on properties: minimal (step 00 has description only on `_migration_notes`; step 05 has on `enum_provenance` and `resolver`)" — matches ground truth sections 7.1 and 7.2. Clean.

2. **MUST_FIX — P2 line 56 says "validate.py line 136 uses iter_errors() — collect-all IS implemented at JSON Schema level."** This is the same fact verified in P1-E. Q7 then says "(iter_errors already verified — note this.)" — this is good, but the instruction "note this" is weak. An over-thorough agent may still re-read validate.py to "note" it. Recommend: change to "DO NOT re-verify. State as given fact in output." to match the stronger language used elsewhere.

3. **SHOULD_FIX — Duplicate iter_errors() reference across prompts.** P1-E line 25 says "validate.py line 136 uses iter_errors() — VERIFIED, skip this question." P2 line 56 repeats the same fact. P2 Q7 explicitly notes "(iter_errors already verified)." This is not a duplicate question (P1-E asks about pipeline behavior, P2 asks about migration scope), but the redundant known-context entry could confuse an agent into thinking it should verify. Recommend: P2 should reference "per P1-E Known Context" rather than restating the full fact.

4. **SHOULD_FIX — Research summary claims "6 research documents" but the prompt does not list them by name.** The research summary (lines 15-40) covers 5 topic areas (Schema DRY, Validation & Error Handling, LLM Constraints, Migration Pattern, Tooling Stack). The user's review criteria says "Does P2's research summary cover all 6 research documents' key recommendations?" — without the 6 document names listed anywhere in P2, it is impossible for a reviewer or agent to verify completeness. The prompt should list the 6 document filenames from the research directory.

5. **SHOULD_FIX — P2 line 47 says "Only step 16 has local $defs (4 defs: specRef, severityLevel, executionStatus, evidenceObject)."** Ground truth section 7.3 confirms: "Has $defs: Yes (4 defs: specRef, severityLevel, executionStatus, evidenceObject)." Clean on facts. But P2 also says "No other step schema uses $defs" — ground truth only checked steps 00, 05, and 16. This is an extrapolation presented as verified fact.

6. **SHOULD_FIX — P2 line 63 says ".pre-commit-config.yaml: 2 hooks only (dag-lint, extraction-intent-check)."** Ground truth section 2.13 confirms 2 hooks: dag-lint and extraction-intent-check. Clean.

7. **SHOULD_FIX — P2 line 53 says "Schema registry: 29 entries."** Ground truth section 2.4 confirms 29. Clean.

8. **SHOULD_FIX — P2 line 51 says "Nesting depth: step 00 = 8, step 05 = 10, step 16 = 19 (exceeds 3-level target)."** Ground truth: step 00 nesting=8 (section 7.1), step 05 nesting=10 (section 7.2), step 16 nesting=19 (section 7.3). Clean. But step 05 nesting depth is NOT explicitly stated as "10" in ground truth — ground truth section 7.2 says "Max nesting depth: 10." Confirmed. Clean.

9. **MINOR — P2 line 66 says "CI: 4 jobs" and lists the 4 jobs.** Matches ground truth section 2.14. Clean.

10. **MINOR — P2 line 59 says "77 error codes (52 E, 25 W), 18 PROMOTABLE_PAIRS."** Matches ground truth section 6.1. Clean.

11. **MINOR — P2 line 67 says "CI runs 14 validation steps."** Ground truth section 2.14 says "14 validation steps." Clean.

12. **MUST_FIX — Scope overlap with P1-E.** P2 Q8 asks "The --json flag exists on 2 of 25 commands. To extend JSON output to all commands: is there a common output pattern that could be abstracted, or does each command format output differently?" P1-E Q9-Q10 ask about the JSON output schema and machine-parsable output for non-JSON commands. While P1-E focuses on current state and P2 focuses on migration path, an agent answering P2 Q8 will necessarily investigate the same code paths as P1-E Q9-Q10. Recommend: P2 Q8 should say "Building on P1-E findings about current --json output format, assess..." to avoid redundant exploration.

### Clean

- Schema file count (24), breakdown (19+4+1) — correct per ground truth section 2.3.
- Core atoms provides 6 shared $defs — correct per ground truth section 7.4.
- $id format URL-based — correct per ground truth sections 7.1-7.3.
- No WriteValidatedJSON MCP tool — correct (not in ground truth, implied by absence).
- No Makefile — confirmed by ground truth section 2.14.
- Python dependencies list — matches ground truth section 13 (tools/requirements.txt).
- 25 commands total — correct per ground truth section 3.1.
- 2 commands with --json — correct per ground truth section 3.3.

---

## Summary

- Total issues: 13 (MUST_FIX: 4, SHOULD_FIX: 7, MINOR: 2)

| # | File | Severity | Issue |
|---|------|----------|-------|
| 1 | p1-prompt-error-collection.md | MUST_FIX | Q11 does not name specific validators/linters for spot-check |
| 2 | p1-prompt-error-collection.md | SHOULD_FIX | Scope header says "5-6 validators" but questions name inconsistent counts |
| 3 | p1-prompt-error-collection.md | SHOULD_FIX | R9 T26 line refs should note both 263 and 267 |
| 4 | p1-prompt-error-collection.md | SHOULD_FIX | No question targets canonical/ module error return patterns despite scope inclusion |
| 5 | p1-prompt-gaps-regressions.md | SHOULD_FIX | Q9 (missing schema file) risks overlapping P1-A registry-filesystem scope |
| 6 | p1-prompt-gaps-regressions.md | MINOR | Q16 line range "166-175" is an approximation |
| 7 | p2-prompt-research-alignment.md | MUST_FIX | "All step schemas use $ref" and "No other step schema uses $defs" are extrapolations presented as verified ground truth |
| 8 | p2-prompt-research-alignment.md | MUST_FIX | Research documents not listed by name — completeness unverifiable |
| 9 | p2-prompt-research-alignment.md | MUST_FIX | Scope overlap: P2 Q8 duplicates P1-E Q9/Q10 investigation scope |
| 10 | p2-prompt-research-alignment.md | SHOULD_FIX | iter_errors() "note this" instruction too weak — should say "DO NOT re-verify" |
| 11 | p2-prompt-research-alignment.md | SHOULD_FIX | Duplicate iter_errors() known-context entry across P1-E and P2 |
| 12 | p2-prompt-research-alignment.md | SHOULD_FIX | "$defs" extrapolation: only 3 schemas checked, claimed for all |
| 13 | p2-prompt-research-alignment.md | MINOR | P2 restates P1-E known context verbatim instead of referencing it |
