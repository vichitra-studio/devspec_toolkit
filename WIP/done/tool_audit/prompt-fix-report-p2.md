# P2 Prompt Fix Report

## Source
- Review: `WIP/tool_audit/prompt-review-p2.md`
- Prompt: `WIP/tool_audit/p2-prompt-research-alignment.md`

## Fixes Applied

### MUST_FIX

| ID | Issue | Fix | Line(s) |
|----|-------|-----|---------|
| M1 | Schema file count breakdown ambiguous ("19 step + 4 core + 1 seed_manifest") | Rewritten to "24 schema files: 19 step schemas + 1 seed_manifest schema + 4 core schemas" with note that core schemas are under `schema/core/` | L53 |
| M2 | Q1 references step numbers without filenames | Added exact filenames: `schema/04_fr_list.schema.json`, `schema/08_fixtures.schema.json`, `schema/12_ci_gates.schema.json` | L87 |

### SHOULD_FIX

| ID | Issue | Fix | Line(s) |
|----|-------|-----|---------|
| S1 | Missing question about 5-layer validation pipeline architecture | Added Q10: maps current 2-hook + CI pipeline against research's 5-layer architecture | L107 |
| S2 | Missing question about `if/then/else` polymorphism preservation through dereferencing | Added Q5 with verified live data: `if/then/else` used in step 02, step 15, step 16, and core schemas `canon.schema.json`, `collections.schema.json` | L95 |
| S3 | Q8 cross-prompt dependency on P1-E is implicit | Rewrote Q9 (was Q8) to be self-contained: names the two subcommands explicitly (`validate`, `traceability-check`) and adds fallback instruction if P1-E has not run | L105 |
| S4 | Description coverage framed as documentation gap, not LLM compliance | Enhanced Q7 (was Q6) to note that research identifies `description` on every field as highest-leverage LLM compliance technique | L99 |

### MINOR (applied because trivial)

| ID | Issue | Fix |
|----|-------|-----|
| N2 | "25 commands" should be "25 subcommands" | Replaced all occurrences (L66) |
| N3 | Q4 "max 3 levels" target presented as universal, but applies to LLM-facing schemas only | Added clarifying parenthetical and extra sub-question about which schemas are LLM-consumed vs Python-only (L93) |
| N4 | Q12 (now Q14) missing canon schemas in $id reference list | Added `canon/aliases.schema.json` and `canon/kind.schema.json` to the check list (L117) |

### MINOR (skipped)

| ID | Reason |
|----|--------|
| N1 | "DO NOT re-verify" vs "spot-check" tension -- the instructions are correct as-is; the spot-check questions (Q1-Q7) make the intent clear |
| N5 | CI validation step count (14 vs 15) -- verified live: 14 specdev invocations in the validate job; the prompt is correct |

## Structural Changes

- Questions renumbered from Q1-Q12 to Q1-Q14 (added Q5 for `if/then/else`, added Q10 for validation pipeline layers)
- Section header "Schema Architecture (6 questions)" updated to "(7 questions)"
- Section header "Validation Pipeline (3 questions)" updated to "(4 questions)"
- Build Pipeline remains 3 questions (Q12-Q14)

## Verification Against Live Codebase

| Claim | Verified |
|-------|----------|
| 20 step-level + 4 core = 24 schema files | Yes -- `ls schema/*.json` = 20, `ls schema/core/*.json` = 4 |
| 25 subcommands | Yes -- `grep -c add_parser cli.py` = 25 |
| `if/then/else` in step 02, 15, 16, core/canon, core/collections | Yes -- grep confirmed all locations |
| 14 validation steps in CI validate job | Yes -- 14 specdev invocations in validate job |
| canon schemas use `$id` | Yes -- `canon.schema.json` and `collections.schema.json` confirmed |
