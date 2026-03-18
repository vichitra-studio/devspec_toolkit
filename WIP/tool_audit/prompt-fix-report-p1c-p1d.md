# Prompt Fix Report: P1-C and P1-D

## P1-C (p1-prompt-hardcoding.md)

### Applied Fixes

| Review Item | Severity | Fix Applied |
|---|---|---|
| MF-1: Schema file breakdown misleading | MUST_FIX | Changed "19 step + 4 core + 1 seed_manifest" to "19 step + 1 seed_manifest + 4 core" (L41) |
| SF-1: Grep patterns lack priority order | SHOULD_FIX | Replaced flat list with numbered priority order: (1) version strings, (2) step numbers, (3) paths, (4) error messages, (5) magic numbers, (6) regex/enums (L29) |
| SF-2: Missing scope files | SHOULD_FIX | Added `scripts/templates/run_specdev.sh` to config/doc scope (L24) |
| SF-3: Error code families incomplete | SHOULD_FIX | Added "59x (R9 cross-step validation, sub-family within 5xx)" (L56) |

### Skipped (MINOR)

| Review Item | Reason |
|---|---|
| M-1: "Both P0 agents miscounted" parenthetical | Historical context removal -- low impact |
| M-2: Q7 partially answered by Known Context | Reframing optional |
| M-3: 200-line limit may be tight | Operational concern, not a prompt text fix |

## P1-D (p1-prompt-test-quality.md)

### Applied Fixes

| Review Item | Severity | Fix Applied |
|---|---|---|
| MF-1: json_utils.py LOC wrong (345 vs 499) | MUST_FIX | Changed "345" to "499" (L85). Verified: `wc -l` = 499. |
| MF-2: Validation module count ambiguous | MUST_FIX | Changed "18 modules" to "17 modules + __init__.py" (L80). Verified: `find` = 17 non-init .py files. |
| SF-1: "likely" assumption about load_json_file | SHOULD_FIX | Changed to definitive statement: "returns None and prints a warning" with source reference (L75) |
| SF-2: Q5 misleading framing about conftest deletion | SHOULD_FIX | Reframed from "can it be deleted?" to "could they share a common helper, or is duplication justified?" (L106) |
| SF-3: R9 overlap pairs missing LOC for comparison targets | SHOULD_FIX | Added LOC counts for all 6 comparison target files (L119-125) |
| SF-4: Source module coverage missing notable modules | SHOULD_FIX | Added notable validation modules with LOC: `_extraction_intent_parser.py` (124), `extraction_intent_check.py` (118), `dag_lint.py` (195) (L80) |

### Skipped (MINOR)

| Review Item | Reason |
|---|---|
| M-1: "zero skips/xfails" mentioned twice | Belt-and-suspenders is acceptable |
| M-2: Q22 about inline JSON blobs is open-ended | Narrowing scope is optional |
| M-3: 200-line output limit may be tight | Operational concern, not a prompt text fix |

## Verification

- `wc -l tools/core/json_utils.py` = 499 (confirms MF-1 fix for P1-D)
- `find tools/specdev_tools/validation -maxdepth 1 -name "*.py" -not -name "__init__.py" | wc -l` = 17 (confirms MF-2 fix for P1-D)
