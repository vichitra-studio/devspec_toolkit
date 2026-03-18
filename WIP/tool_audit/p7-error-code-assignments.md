# P7 Error Code Assignments

Maps each uncoded `errors.append()` site to its assigned error code for Phase 1-3 migration.
Sites already prefixed with `[EW]\d{3}` are excluded.

---

## validators/step_01.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 36   | `f"Capability '...' traces to unknown component '...'"` | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_02.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 13   | `f"Duplicate component_id: {comp_id}"` | E520 | UNRESOLVED_INPUT |
| 23   | `f"Connection[{idx}] from '{source}' not found in components"` | E590 | CROSS_STEP_ID_NOT_FOUND |
| 25   | `f"Connection[{idx}] to '{target}' not found in components"` | E590 | CROSS_STEP_ID_NOT_FOUND |
| 38   | `f"Connection[{idx}] rate_limit burst {burst} is less than rps {rps}"` | E520 | UNRESOLVED_INPUT |
| 59   | `f"Connection[{idx}] touches external component but trust_boundary is internal"` | E520 | UNRESOLVED_INPUT |
| 103  | `f"Capability trace must use one of {accepted}: {trace_id}"` | E530 | INVENTED_ENUM_OR_ID |
| 107  | `f"Missing capability coverage: {', '.join(missing)}"` | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_02a.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 15   | `f"Duplicate ci_gates entry '...' at index {i}"` | E520 | UNRESOLVED_INPUT |

## validators/step_03.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 30   | `"Terms array is empty"` | E520 | UNRESOLVED_INPUT |
| 42   | `f"Duplicate term_id '...' at index {i}"` | E520 | UNRESOLVED_INPUT |
| 50   | `f"Duplicate term '...' at index {i}"` | E520 | UNRESOLVED_INPUT |
| 56   | `f"Empty domain string at term index {i}"` | E520 | UNRESOLVED_INPUT |
| 60   | `f"Empty units string at term index {i}"` | E520 | UNRESOLVED_INPUT |
| 72   | `f"NFR metric '...' not found in glossary"` | E590 | CROSS_STEP_ID_NOT_FOUND |
| 78   | `f"NFR metric '...' missing units in glossary"` | E520 | UNRESOLVED_INPUT |
| 91   | `f"Unit mismatch for '...': expected '...', got '...'"` | E520 | UNRESOLVED_INPUT |
| 99   | Monitoring metric cross-ref | E590 | CROSS_STEP_ID_NOT_FOUND |
| 109  | Monitoring metric cross-ref | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_04.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 26   | `f"FR at index {i} has fr_id '...' that does not follow 'fr-<kebab>' convention"` | E530 | INVENTED_ENUM_OR_ID |
| 47   | `f"FR at index {index} ('...') is missing required 'trace' field"` | E520 | UNRESOLVED_INPUT |
| 49   | `f"FR '...' at index {index} has empty 'trace' array"` | E520 | UNRESOLVED_INPUT |
| 60   | `f"FR '...' references unknown capability '...'"` | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_05.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| (dup)| Duplicate api_id (via check_no_duplicates) | E520 | UNRESOLVED_INPUT |
| (method)| Invalid HTTP method validation | E530 | INVENTED_ENUM_OR_ID |

## validators/step_06.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 19   | `f"Invariant at index {i} has inv_id '...' that does not follow 'inv-<kebab>' convention"` | E530 | INVENTED_ENUM_OR_ID |
| 22   | `f"Invariant '...' missing trace"` | E520 | UNRESOLVED_INPUT |
| 28   | `f"Invariant '...' has trace target '...' that does not match (fr|api|nfr|inv)-* pattern"` | E530 | INVENTED_ENUM_OR_ID |
| 30   | (same as 28, non-dict variant) | E530 | INVENTED_ENUM_OR_ID |
| 65   | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 70   | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 76   | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 81   | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 86   | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 103  | Invariant expression validation | E520 | UNRESOLVED_INPUT |
| 108  | Invariant expression validation | E520 | UNRESOLVED_INPUT |

## validators/step_07.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 27   | `f"NFR at index {i} has nfr_id '...' that does not follow 'nfr-<kebab>' convention"` | E530 | INVENTED_ENUM_OR_ID |
| 33   | `f"NFR '...' target string contains no digit: '...'"` | E520 | UNRESOLVED_INPUT |
| 39   | `f"NFR '...' has invalid stage '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 46   | NFR metric cross-ref | E590 | CROSS_STEP_ID_NOT_FOUND |
| 57   | NFR metric cross-ref | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_08.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 19   | `f"Fixture at index {i} has fixture_id '...' that does not follow 'fix-<kebab>' convention"` | E530 | INVENTED_ENUM_OR_ID |
| 22   | `f"Fixture '...' missing targets"` | E520 | UNRESOLVED_INPUT |
| 28   | `f"Fixture '...' has target '...' that does not match (fr|api|nfr|inv)-* pattern"` | E530 | INVENTED_ENUM_OR_ID |
| 30   | (same as 28, non-dict variant) | E530 | INVENTED_ENUM_OR_ID |
| 49   | Fixture cross-step ref | E590 | CROSS_STEP_ID_NOT_FOUND |
| 73   | Fixture cross-step ref | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_09.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 22   | `f"Invalid target_date '...' in milestone '...'"` | E520 | UNRESOLVED_INPUT |
| 24   | `"Milestone target_date values are not ordered"` | E520 | UNRESOLVED_INPUT |
| 29   | Tech stack validation | E520 | UNRESOLVED_INPUT |
| 41   | Tech stack validation | E520 | UNRESOLVED_INPUT |

## validators/step_10.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 21   | `f"Invalid owner '...'. Must be one of ..."` | E530 | INVENTED_ENUM_OR_ID |
| 30   | `f"Invalid regex pattern in commit_message_rules: {e}"` | E520 | UNRESOLVED_INPUT |
| 37   | `f"commit_message_rules.allowed_types contains invalid entry: ..."` | E530 | INVENTED_ENUM_OR_ID |
| 48   | `f"Invalid pr_rule '...' at index {i}. Must be one of ..."` | E530 | INVENTED_ENUM_OR_ID |
| 55   | `f"Invalid trace type '...' at index {i}."` | E530 | INVENTED_ENUM_OR_ID |
| 62   | Trace type validation | E530 | INVENTED_ENUM_OR_ID |

## validators/step_11.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 80   | `f"Threat '...' has no target_ids"` | E520 | UNRESOLVED_INPUT |
| 84   | `f"Threat '...' has invalid target type '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 92   | Threat target ref | E590 | CROSS_STEP_ID_NOT_FOUND |
| 98   | Threat target ref | E590 | CROSS_STEP_ID_NOT_FOUND |
| 106  | `f"Threat '...' has no mitigations"` | E520 | UNRESOLVED_INPUT |
| 109  | `f"Threat '...' has non-object mitigation: ..."` | E520 | UNRESOLVED_INPUT |
| 113  | `f"Threat '...' has invalid mitigation type '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 117  | Mitigation validation | E520 | UNRESOLVED_INPUT |

## validators/step_12.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 23   | `f"Job '...' has step missing id/command"` | E520 | UNRESOLVED_INPUT |
| 27   | `f"Job '...' requires unknown job '...'"` | E590 | CROSS_STEP_ID_NOT_FOUND |
| 35   | `f"Circular dependency detected in job requires graph: ..."` | E141 | TASK_DEPENDENCY_CYCLE |
| 50   | CI gate validation | E303 | CI_GATE_VIOLATION |
| 81   | CI gate validation | E303 | CI_GATE_VIOLATION |
| 133  | CI gate validation | E303 | CI_GATE_VIOLATION |

## validators/step_13.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 24   | `f"Extension '...' missing required_schema_sections"` | E520 | UNRESOLVED_INPUT |
| 28   | Extension validation | E320 | STEP13_EXTENSION_ERROR |
| 36   | Extension validation | E320 | STEP13_EXTENSION_ERROR |
| 47   | Extension validation | E320 | STEP13_EXTENSION_ERROR |
| 55   | Extension validation | E320 | STEP13_EXTENSION_ERROR |
| 66   | Extension validation | E320 | STEP13_EXTENSION_ERROR |

## validators/step_13a.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 15   | `f"Element has element_id '...' that does not follow kebab-case convention"` | E530 | INVENTED_ENUM_OR_ID |
| 18   | `f"Invalid impact_score for '...': ..."` | E520 | UNRESOLVED_INPUT |
| 23   | `f"Invalid summary.completeness: ..."` | E520 | UNRESOLVED_INPUT |
| 27   | `f"summary.completeness is ... but missing_elements is empty"` | E520 | UNRESOLVED_INPUT |
| 43   | Completeness validation | E590 | CROSS_STEP_ID_NOT_FOUND |
| 59   | Completeness validation | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_14.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 30   | `f"Duplicate milestone_id '...' at index {i}"` | E520 | UNRESOLVED_INPUT |
| 39   | `f"Invalid target_date '...' in milestone '...'"` | E520 | UNRESOLVED_INPUT |
| 46   | Task validation | E520 | UNRESOLVED_INPUT |
| 53   | Task dependency | E590 | CROSS_STEP_ID_NOT_FOUND |
| 60   | Task dependency | E590 | CROSS_STEP_ID_NOT_FOUND |
| 67   | `f"Milestone '...' duplicate task_id '...'"` | E520 | UNRESOLVED_INPUT |
| 73   | `"Milestone target_date values are not ordered"` | E520 | UNRESOLVED_INPUT |
| 82   | Dependency validation | E590 | CROSS_STEP_ID_NOT_FOUND |
| 87   | `f"Dependency entry must be an object: ..."` | E520 | UNRESOLVED_INPUT |
| 92   | `f"Dependency has invalid id '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 95   | `f"External dependency '...' missing owner"` | E520 | UNRESOLVED_INPUT |
| 97   | `f"External dependency '...' missing note"` | E520 | UNRESOLVED_INPUT |
| 129  | Step09 cross-ref | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_15.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 18   | `f"Missing required field: {field}"` | E520 | UNRESOLVED_INPUT |
| 21   | `"service_skeleton must be an object"` | E520 | UNRESOLVED_INPUT |
| 24   | `"route_map must be an array"` | E520 | UNRESOLVED_INPUT |
| 27   | `"validators must be an array"` | E520 | UNRESOLVED_INPUT |
| 33   | `f"Invalid build_status '...'. Must be one of ..."` | E530 | INVENTED_ENUM_OR_ID |

## validators/step_16.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 71   | Behavior validation pairing | E307 | BEHAVIOR_VALIDATION_PAIRING |
| 111  | `f"Checklist item '...' has invalid type '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 114  | `f"Checklist item '...' has invalid layer '...'"` | E530 | INVENTED_ENUM_OR_ID |
| 122  | `f"Checklist item '...' is not deferred but has no nfr_refs"` | E520 | UNRESOLVED_INPUT |
| 126  | `f"Checklist item '...' is not deferred but has no fixture_ref"` | E520 | UNRESOLVED_INPUT |
| 133  | `f"Checklist item '...' is 'verified' but has no actions."` | E301 | MISSING_PROOF_CLOSURE |
| 143  | `f"Checklist item '...' is 'verified' but contains no evidence"` | E301 | MISSING_PROOF_CLOSURE |
| 175  | `f"File '...' is touched by implementation but not covered by target_file_patterns."` | E520 | UNRESOLVED_INPUT |
| 187  | `"seed_manifest.json missing docs_policy.doc_paths..."` | W570 | GRACEFUL_SKIP |
| 189  | `"Failed to read seed_manifest.json..."` | W570 | GRACEFUL_SKIP |
| 191  | `"seed_manifest.json not found..."` | W570 | GRACEFUL_SKIP |
| 215  | `"plan.docs_impact is required when code changes are present."` | E520 | UNRESOLVED_INPUT |
| 219  | `"plan.docs_impact.status must be 'required'..."` | E520 | UNRESOLVED_INPUT |
| 222  | `"plan.docs_impact.docs_touched must be provided..."` | E520 | UNRESOLVED_INPUT |
| 226  | `f"plan.docs_impact.docs_touched contains non-doc path: ..."` | E520 | UNRESOLVED_INPUT |

Note: Lines 249-426 already have E3xx/W5xx codes.

## validators/step_16a.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 19   | `"Step 16a requires a 'plan' object"` | E520 | UNRESOLVED_INPUT |
| 24   | `"Step 16a plan.status is required"` | E520 | UNRESOLVED_INPUT |
| 35   | `f"Step 16a: duplicate checklist id '...' at index {i}"` | E520 | UNRESOLVED_INPUT |
| 42   | Checklist-roadmap binding | E590 | CROSS_STEP_ID_NOT_FOUND |

## validators/step_16b.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 20   | `"Step 16b expects an 'execution' object"` | E520 | UNRESOLVED_INPUT |
| 26   | `"Step 16b execution.execution_results must be an array"` | E520 | UNRESOLVED_INPUT |
| 36   | `f"Step 16b: duplicate execution_result command '...' at index {i}"` | E520 | UNRESOLVED_INPUT |
| 41   | Execution validation | E520 | UNRESOLVED_INPUT |

## validators/step_16c.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 21   | `"Step 16c expects a 'review' object"` | E520 | UNRESOLVED_INPUT |
| 27   | Review validation | E520 | UNRESOLVED_INPUT |
| 44   | `f"Step 16c: duplicate fr_id '...' in semantic_review.fr_coverage"` | E520 | UNRESOLVED_INPUT |

---

## Linters

### fixtures_lint.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 64   | `f"{fid}: missing targets"` | E520 | UNRESOLVED_INPUT |
| 87   | `f"{fid}: targets unknown {label} '{tid}'"` | E590 | CROSS_STEP_ID_NOT_FOUND |
| 90   | `f"{fid}: missing input/expected"` | E520 | UNRESOLVED_INPUT |
| 97   | `f"{fid}: expected.status must be an HTTP status..."` | E520 | UNRESOLVED_INPUT |
| 100  | `f"{fid}: expected.body must be JSON serializable"` | E520 | UNRESOLVED_INPUT |
| 103  | `f"{fid}: expected.headers must be an object"` | E520 | UNRESOLVED_INPUT |
| 108  | `f"{fid}: expected should be a dictionary..."` | E520 | UNRESOLVED_INPUT |

### seed_lint.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 23   | `f"Missing seed manifest: ..."` | E520 | UNRESOLVED_INPUT |
| 34   | `f"Failed to read seed manifest: ..."` | E520 | UNRESOLVED_INPUT |
| 76   | `f"Missing prompts directory: ..."` | E520 | UNRESOLVED_INPUT |
| 107  | `f"Failed to read prompt: ..."` | E520 | UNRESOLVED_INPUT |
| 110  | `f"{path}: missing 'Seed Order & Mandatory Sources' section"` | E520 | UNRESOLVED_INPUT |
| 112  | `f"{path}: missing reference to spec/common/seed_manifest.json"` | E520 | UNRESOLVED_INPUT |
| 208  | `"Seed manifest has duplicate seed_id values."` | E410 | CANONICAL_ALIAS_COLLISION |
| 217  | `f"Seed '...' is missing 'path' field."` | E520 | UNRESOLVED_INPUT |
| 221  | Seed path validation | E520 | UNRESOLVED_INPUT |
| 230  | Seed path escapes root | E520 | UNRESOLVED_INPUT |
| 234  | Seed path validation | E520 | UNRESOLVED_INPUT |
| 259  | `f"global_seed_order references unknown seed_id: ..."` | E520 | UNRESOLVED_INPUT |
| 264  | `f"nested_order references unknown seed_id: ..."` | E520 | UNRESOLVED_INPUT |
| 269  | `f"step_requirements[...] references unknown seed_id: ..."` | E520 | UNRESOLVED_INPUT |
| 295  | `f"{file_path}: seed_refs must be an array"` | E520 | UNRESOLVED_INPUT |
| 301  | `f"{file_path}: seed_refs includes unknown seed_id '...'"` | E520 | UNRESOLVED_INPUT |
| 306  | Seed ref validation | E520 | UNRESOLVED_INPUT |

Note: Lines 84 (W150), 167 (W551), 199 (E520) already have codes.

### docs_lint.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 15   | `f"Missing seed manifest: ..."` | E520 | UNRESOLVED_INPUT |
| 21   | `f"Failed to read seed manifest: ..."` | E520 | UNRESOLVED_INPUT |
| 59   | `f"Missing root README.md at ..."` | E520 | UNRESOLVED_INPUT |
| 91   | `f"Docs scope not found: ..."` | E520 | UNRESOLVED_INPUT |
| 109  | `f"Missing README.md in ..."` | E520 | UNRESOLVED_INPUT |

---

## Governance

### governance.py

| Line | Current Message Pattern | Assigned Code | Mnemonic |
|------|------------------------|---------------|----------|
| 35   | `f"Commit message mismatch. {custom_msg}"` | E303 | CI_GATE_VIOLATION |
| 37   | `f"Commit message mismatch. Must match regex: ..."` | E303 | CI_GATE_VIOLATION |

---

## Summary

| Category | Files | Uncoded Sites | Primary Codes |
|----------|-------|---------------|---------------|
| Validators | 21 | ~80 | E520, E530, E590, E301, E303, E307, E320, E141, W570 |
| Linters (fixtures, seed, docs) | 3 | ~24 | E520, E590, E410 |
| Governance | 1 | 2 | E303 |
| **TOTAL** | **25** | **~106** | |

All other linter files (hallucination_lint, spec_quality_lint, dag_lint, dependency_order_lint, forward_replay_check, traceability_closure, extraction_intent_check, canon_schema_alignment) already emit fully coded errors.
