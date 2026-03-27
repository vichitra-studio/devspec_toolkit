# P3 Fix Report (Agent E)

## Inputs
- `WIP/tool_audit/p3-review-D1.md` (APPROVED_WITH_FIXES)
- `WIP/tool_audit/p3-review-D2.md` (APPROVED_WITH_FIXES)
- `WIP/tool_audit/p3-out-master-findings.md` (target file)

## Merged Findings

D1 and D2 overlapped on two items:
- **AUDIT-050 line ref** (both flagged governance.py:12 should be :11) -- merged, applied once
- **D6 golden file testing gap** (D1 SHOULD_FIX #1, D2 SHOULD_FIX #2) -- merged, addressed via expanded WIP cross-check note

## Fixes Applied

### MUST_FIX (from D1)
1. **AUDIT-032 LOC count**: Changed `345 LOC` to `499 LOC` at line 275. Verified via `wc -l tools/core/json_utils.py` = 499.

### SHOULD_FIX
2. **AUDIT-050 line number**: Changed `governance.py:12` to `governance.py:11`. Verified: line 11 contains `json.load(open(p, "r", encoding="utf-8"))`.
3. **AUDIT-001 step_13.py line number**: Changed `step_13.py:32,40,50` to `step_13.py:32,40,51`. Verified: E320 emitted at lines 32, 40, 51.
4. **"Contradiction Details" section renamed**: Changed heading to "Cross-Check Notes" (D1 SHOULD_FIX #5). Items are misses and addenda, not contradictions.
5. **WIP pipeline D5/D6 disposition added**: Expanded the WIP cross-check note with explicit disposition for D5 (declarative rules, MEDIUM GAP) and D6 (golden file testing, MEDIUM GAP), both classified as methodology recommendations excluded from code-level audit scope.
6. **WIP cli-package A2/A7 disposition added**: Added explicit disposition: A2 subsumed by AUDIT-064, A7 excluded as packaging concern noted for P4.
7. **AUDIT-069 added (fixture session scoping)**: New INFO finding from WIP:test-quality B4-01. All conftest fixtures use default function scope with no session scoping.
8. **B:T9 added to Dropped Findings table**: Low integration test count explicitly noted as EXCLUDED with rationale.
9. **AUDIT-035 severity label clarified**: Changed ambiguous "C:resolved to LOW but the coupling is MEDIUM for documentation" to "C:resolved to MEDIUM (A rated medium, B rated low; retained at MEDIUM due to undocumented coupling boundary)".

### Summary Count Updates
10. **Total findings**: 68 -> 69
11. **INFO count**: 8 -> 9
12. **MISSED_BY_AUDIT count**: 5 -> 6 (AUDIT-064 through AUDIT-069)
13. **WIP cross-check table**: test-quality MISSED_BY_AUDIT 0 -> 1, total MISSED_BY_AUDIT 5 -> 6
14. **Target file index**: tests/conftest.py updated to include AUDIT-069 (count 2 -> 3), tests/integration/conftest.py updated (count 1 -> 2)

### MINOR items noted but not applied
- **AUDIT-064 severity (INFO vs MEDIUM)**: D1 flagged this as potentially underrated. Left as-is; severity was set by the cross-reference resolution and changing it would require re-evaluation of the full severity framework. Noted for P4 consideration.
- **WIP cross-check unclassified count breakdown**: D1 suggested adding a count breakdown for the 47 unclassified items. The expanded note now provides category-level detail for pipeline, cli-package, and test-quality, which partially addresses this.

## Verification
All line number fixes verified against live codebase before application. Final file read confirmed internal consistency of counts, IDs, and cross-references.
