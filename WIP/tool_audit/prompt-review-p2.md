# Prompt Review: P2 Research Alignment

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| 24 schema files (19 step + 4 core + 1 seed_manifest) | L53 | `find schema -name '*.json' -type f` = 24 (20 step + 4 core; 19 step count wrong -- there are 20 step-level schemas including seed_manifest) | PARTIAL -- see MUST_FIX #1 |
| Schema registry: 29 entries | L61 | `python3 -c "len(json.load(...))"` = 29 | YES |
| `$id` format: URL-based `https://specdev.local/schema/...` | L57 | `schema/00_charter.schema.json` has `$id: "https://specdev.local/schema/00_charter.schema.json"` | YES |
| `iter_errors()` at line 136 | L64 | `grep -n iter_errors validate.py` shows line 136 | YES |
| `--json` on 2 of 25 commands | L66 | `grep --json cli.py` shows validate + traceability-check; `grep add_parser` shows 25 subcommands | YES |
| 77 error codes (52 E, 25 W), 18 PROMOTABLE_PAIRS | L67 | Regex count in errors.py: 52 E, 25 W, 18 pairs | YES |
| 2 pre-commit hooks (dag-lint, extraction-intent-check) | L71 | `.pre-commit-config.yaml` has exactly 2 hooks | YES |
| Core atoms: 6 shared `$defs` with `$anchor` | L56 | `atoms.schema.json` has 6 defs: metadata, kebabId, timestamp, owner, tag, screamingSnakeId -- all with `$anchor` | YES |
| CI: 4 jobs | L74 | `.github/workflows/ci.yml` has jobs: validate, redteam, deploy-staging, deploy-prod | YES |
| Dependencies: jsonschema>=4.21.1, pyyaml>=6.0.1, jsonschema-specifications>=2023.12.1, pyjwt>=2.8.0 | L80 | `pyproject.toml` lists exactly these 4 | YES |
| `additionalProperties: false` at root and nested (step 00, step 05) | L58 | step 00 has 4 occurrences of `additionalProperties`; confirmed at nested levels | YES |
| Nesting depth: step 00=8, step 05=10, step 16=19 | L59 | Ground truth Section 7 confirms these exact values | YES (from ground truth) |
| Checked schemas use `$ref` to core schemas | L54 | `grep '"$ref"' schema/00_charter.schema.json` shows 23 `$ref` occurrences referencing atoms/collections | YES |
| Only step 16 uses local `$defs` | L55 | Ground truth Section 7 confirms steps 00 and 05 have no `$defs`, step 16 has 4 | YES (from ground truth) |
| Canon kinds: 25 kind files | L95 | `ls canon/kinds/ | wc -l` = 25 | YES |
| No Makefile, no build step | L72-73 | No Makefile in repo, no schemas/src/ or schemas/dist/ directory | YES |

## Research Coverage Check

| Research Document | Key Recommendations | Covered in Prompt? |
|------------------|-------------------|-------------------|
| agent-migration-patterns.md | Strangler fig migration; dual-write/shadow-read; anti-corruption layer; Claude structured output constraints; LLM failure modes; WriteValidatedJSON MCP tool | YES -- migration pattern (L40-42), WriteValidatedJSON (L30-31) |
| json-schema-dry-patterns.md | Bundle vs. dereference distinction; `schemas/src/` -> `schemas/dist/`; URN-based `$id`; build-time resolution pipeline; LLM provider `$ref` support differences | YES -- DRY pattern (L23-25), build pipeline (Q10-Q11) |
| json-schema-migration-summary.md | Three-layer schema system; naming conventions (kebab filenames, PascalCase `$defs`, snake_case properties); record schemas with `if/then/else` polymorphism | PARTIAL -- naming conventions mentioned at L48 but Q area doesn't probe `if/then/else` polymorphism patterns |
| json-schema-research-report.md | Two-audience schema problem; validation pipeline architecture (5 layers); agent self-correction flow; WriteValidatedJSON MCP spec; pre-commit staleness check; multi-agent protocol standards (A2A, ACP, LACP); ~25K-50K token elimination estimate | PARTIAL -- see SHOULD_FIX #1, #2 |
| json-schema-standards.md | JSON Schema 2020-12 vocabulary system; `$defs` replaces `definitions`; `$ref` alongside sibling keywords; `prefixItems` replaces tuple `items`; custom meta-schemas | YES -- covered implicitly by DRY pattern section |
| json-validation-tooling.md | AJV (standalone compile, custom keywords); check-jsonschema (pre-commit native); sourcemeta/jsonschema (C++ binary); YAML frontmatter validation approaches | PARTIAL -- AJV/check-jsonschema/ajv-cli mentioned at L45-47 but frontmatter validation not asked about |

## Issues Found

### MUST_FIX

**M1. Schema file count breakdown is wrong (L53)**
The prompt says "19 step + 4 core + 1 seed_manifest = 24." There are 20 files in `schema/` (not counting core) including seed_manifest.schema.json. The breakdown should be "20 step-level (including seed_manifest) + 4 core = 24" or "19 step + 1 seed_manifest + 4 core = 24." The current phrasing is confusing because it says "19 step" then separately adds "1 seed_manifest" which implies 19+4+1=24, which is technically correct if parsed that way, but the sentence reads as "24 schema files (19 step + 4 core + 1 seed_manifest)" which could be read as 19+4+1=24 (fine) or 24=(19+4) with 1 extra. Clarify as: "24 schema files: 19 step schemas + 1 seed_manifest schema + 4 core schemas."

**M2. Q1 references wrong schema filenames (L87)**
Q1 says "Spot-check 3 step schemas (e.g., step_04, step_08, step_12)." The actual filenames are `04_fr_list.schema.json`, `08_fixtures.schema.json`, `12_ci_gates.schema.json`. An agent would need to figure this out. While not technically wrong (the agent should be able to find them), providing exact filenames reduces ambiguity and wasted tokens. This applies to all questions that reference step numbers without filenames.

### SHOULD_FIX

**S1. Missing research recommendation: validation pipeline architecture layers (research-report Section 6)**
The research report describes a 5-layer validation architecture (pre-commit source schema check, pre-commit dist staleness check, WriteValidatedJSON at write time, agent self-correction, skill orchestrator trust). The prompt asks about WriteValidatedJSON (Q9) and build pipeline (Q10-Q11) separately but doesn't ask about the full validation pipeline architecture as an integrated system. Adding a question like "How does the current 2-hook pre-commit + CI validation pipeline compare to the research's 5-layer validation architecture?" would close this gap.

**S2. Missing research recommendation: `if/then/else` polymorphism preservation through dereferencing**
The research (migration-summary Section 2.3, research-report Section 5.3) emphasizes that `if/then/else` survives dereferencing and is critical for polymorphic record schemas. The devspec toolkit already uses complex schemas (step 16 has 19 levels of nesting) that may use conditional keywords. No question asks whether current schemas use `if/then/else` or whether the dereferencing path would preserve them.

**S3. Q8 references "P1-E's analysis" which creates a cross-prompt dependency (L103)**
Q8 says "Building on P1-E's analysis of current --json output format (Q9-Q10)." If P2 runs before or independently of P1-E, this reference is meaningless. The question should be self-contained or the dependency should be noted in the prompt header.

**S4. Research recommendation on `description` coverage is stronger than prompt conveys**
The research report (Section 5.5, point 5) says "`description` on every field" is one of the highest-leverage LLM compliance techniques. The prompt asks about description coverage in Q6 but doesn't frame it as an LLM compliance issue -- it frames it as a documentation gap. The research context makes this a functional requirement, not just nice-to-have.

**S5. Missing research recommendation: multi-agent protocol standards**
The research report (Section 10) covers A2A, ACP, LACP protocols. While these are more relevant to vc_agent than devspec_toolkit, the Agent Card pattern (machine-readable agent interface description) could inform the toolkit's `docs/agents/manifest.json` design. A minor question could assess alignment.

### MINOR

**N1. Prompt says "DO NOT re-read the research files" but doesn't prevent re-verification of ground truth (L8, L50)**
The ground truth section says "ALL from verified ground truth -- DO NOT re-verify" but multiple claims are worth spot-checking against live code (which is what Q1-Q6 are for). The instruction is correct but the emphasis could confuse the agent into not reading live schema files, which is the whole point of the questions.

**N2. "25 commands" claim should be "25 subcommands" (L66)**
Minor terminology: the CLI has 25 subcommands (parsers), not 25 independent commands. This is cosmetic but precision matters in a ground-truth document.

**N3. Q4 target of "max 3 levels" is research-specific, not universal (L93)**
The "max 3 levels" target comes from the LLM constraint research for *agent consumption schemas*. The devspec toolkit's schemas are validated by Python `jsonschema`, not consumed by LLMs for structured output. The question should acknowledge that the 3-level target applies specifically to LLM-facing schemas, not necessarily to all toolkit schemas.

**N4. Q12 migration scope question could be more specific (L113)**
Q12 asks "what files reference the current `$id` values" but doesn't mention that `canon/aliases.schema.json` and `canon/kind.schema.json` (which appear in the schema registry) also use `$id` and would need updating. The question lists "schema_registry.json, all schema files, validate.py, registry.py" but should also mention canon schemas.

**N5. Line 74: "CI: 4 jobs" -- should note validate job has 14-15 validation steps**
The prompt does note "14 validation steps" but the actual count of non-infrastructure steps is 15 (Prompt-schema sync, Canonical lint, Canonical integrity, Validate all specs, Spec quality lint, Hallucination lint, Seed lint, Docs lint, Dependency order lint, DAG lint, Forward replay check, Governance check, Fixtures lint, Build trace matrix, Upload matrix). The ground truth counts "matrix build + artifact upload" as one logical step to get 14. This should be explicit to avoid agent confusion.

## Verdict: APPROVED_WITH_FIXES

The prompt is well-structured with clear questions, accurate embedded state, and good coverage of the 6 research documents. The 12 questions map well to the research recommendations. Two issues need fixing before execution:

- **M1**: Clarify the schema file count breakdown (cosmetic but could confuse the agent).
- **M2**: Provide exact schema filenames in question examples to reduce agent token waste.

The SHOULD_FIX items (S1-S5) would improve coverage but the prompt is functional without them. The most impactful improvement would be S1 (adding a question about the full validation pipeline architecture) and S3 (removing the P1-E cross-dependency in Q8).
