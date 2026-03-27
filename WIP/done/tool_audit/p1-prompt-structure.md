# P1-A: Structure & Wiring Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

### Objective

Audit package structure, CLI wiring, module boundaries, and registry consistency. Identify any mismatches between declared and actual state.

### Exclusive Scope

Do NOT audit DRY patterns in validator internals (P1-B1 covers those), test quality, or error flow. Focus only on wiring, structure, imports, packaging, and documentation accuracy.

Read every file/directory listed below:

- `tools/specdev_tools/cli.py` (757 LOC) — all 25 subcommand registrations
- All `__init__.py` files: `tools/specdev_tools/__init__.py` (45 LOC), `tools/specdev_tools/canonical/__init__.py` (1 LOC), `tools/specdev_tools/core/__init__.py` (12 LOC), `tools/specdev_tools/generation/__init__.py` (1 LOC), `tools/specdev_tools/migration/__init__.py` (18 LOC), `tools/specdev_tools/migration/scripts/__init__.py` (0 LOC), `tools/specdev_tools/validation/__init__.py` (1 LOC), `tools/specdev_tools/validation/validators/__init__.py` (11 LOC)
- `tools/pyproject.toml` (version 0.4.0), `tools/setup.py` (stub: `from setuptools import setup; setup()`)
- `tools/schema_registry.json` (29 entries — both source agents miscounted as 30)
- `tools/step_order.json` (22 steps: 00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c)
- `tools/specdev_tools/core/` — 4 non-init files + `__init__.py` (12 LOC): `errors.py` (186 LOC), `registry.py` (85 LOC), `trace_types.py` (53 LOC), `changelog_parser.py` (394 LOC)
- `tools/core/json_utils.py` (499 LOC — standalone, not part of specdev_tools package)
- `tools/command_prefixes.json` (20 allowed prefixes), `tools/context/` (empty directory)
- `scripts/templates/run_specdev.sh`, `scripts/setup_devspec_env.sh`, `scripts/init_project.py`, `scripts/analyze_schema_usage.py`, `scripts/generate_fixtures_02a.py`, `scripts/templates/ensure_venv.py` (6 script files total)
- `canon/` directory (29 files: 1 manifest.json, 1 aliases.json, 2 schemas, 25 kind files in canon/kinds/)
- `prompts/` directory (41 files: 22 step prompts + 19 migration templates)
- `.pre-commit-config.yaml` (only 2 hooks: dag-lint and extraction-intent-check)
- `CLAUDE.md` (note: version mismatch — says 0.3.0 vs pyproject.toml 0.4.0)
- `docs/` directory (extensive subdirectory tree: README.md, agents/, architecture/, audit/, developers/, ops/, plans/, prompts/)
- `tools/README.md` (title says "v3 Full"), `tools/requirements.txt` (4 deps: jsonschema, pyyaml, jsonschema-specifications, pyjwt)
- `tools/trace_matrix.json` (read this file — last modified 2025-02-22, empty matrix with all-zero counters)
- `tools/specdev_tools.egg-info/` (6 files), `tools/UNKNOWN.egg-info/` (4 files — orphaned/stale)
- `.github/workflows/ci.yml` (118 lines, 4 jobs)

**Important**: Verify all counts in "Known Context from Ground Truth" against the live codebase. Report any discrepancies as findings.

### Known Context from Ground Truth

- **61 source files** in specdev_tools/, **13,228 total LOC**
- **21 step validator files** (no step_00.py — Step 00 has no deep validator)
- **DEEP_VALIDATORS** dict in validate.py has **21 entries**
- **25 CLI subcommands** + **7 align sub-actions** (status, diff, plan, apply, prompts, rollback, validate)
- **29 schema registry entries** (not 30 as both source agents initially miscounted)
- **22 steps** in step_order.json
- **Version mismatch**: CLAUDE.md claims 0.3.0, pyproject.toml has 0.4.0
- **2 subcommands** support `--json` flag: validate and traceability-check
- **Schema registry** maps 16a/16b/16c all to the same `schema/16_impl_context.schema.json`
- **No step_00 validator** exists; step 00 validation is schema-only
- **CI**: 4 jobs (validate, redteam, deploy-staging, deploy-prod), env vars SPECDEV_WARNINGS_AS_ERRORS=1 and SPECDEV_REPLAY_DIFF_ERROR_MODE=error
- **tools/core/json_utils.py** is outside the specdev_tools package — standalone AI agent tool using jq subprocess calls
- **No __version__ string** in `tools/specdev_tools/__init__.py`
- **tools/README.md** title says "AI Spec Driven Development CLI (v3 Full)"

### Questions

**Wiring (7 questions)**

1. Enumerate all 25 subcommand registrations in cli.py. For each, verify the handler function exists and is correctly wired. Are there any dead or unreachable subcommands?
2. Do all 29 schema_registry.json entries resolve to existing schema files on disk? Are there any schema files on disk NOT in the registry?
3. Does step_order.json's 22-step list match the set of steps referenced in schema_registry.json, DEEP_VALIDATORS, and prompt files? Identify any gaps or extras.
4. Does `scripts/templates/run_specdev.sh` cover all 25 CLI subcommands, or does it only wrap a subset?
5. Does CLAUDE.md accurately describe the current CLI subcommands? Are any missing or renamed?
6. Is the `align` subcommand's 7-action set (status, diff, plan, apply, prompts, rollback, validate) correctly wired to handler functions?
7. Are the 2 `--json` flag subcommands (validate, traceability-check) the only ones that should support structured output? Should others (e.g., matrix, canonical-lint) also support it?

**Structure (9 questions)**

8. Assess `__init__.py` cleanliness across all 8 init files. Is the lazy-import shim in the top-level `__init__.py` (45 LOC) still necessary? Are there stale entries in the `_MOVED` dict?
9. Is the subpackage split (core/, canonical/, generation/, validation/, migration/) well-justified? Are there modules that belong in a different subpackage?
10. `tools/core/json_utils.py` (499 LOC) exists outside `specdev_tools/`. Does it overlap with any functionality inside the package? Should it be integrated or removed?
11. What is the purpose of `tools/command_prefixes.json` and the empty `tools/context/` directory? Are they referenced anywhere in the codebase?
12. Are there orphan files — files that exist but are never imported, referenced, or tested?
13. Is `tools/pyproject.toml` consistent with `tools/setup.py` and `tools/requirements.txt`? Does pyproject.toml declare all deps that requirements.txt lists?
14. Is version 0.4.0 declared consistently? Check pyproject.toml, `__init__.py` (no `__version__`), CLAUDE.md (says 0.3.0), tools/README.md (says "v3 Full").
15. Do the 22 prompt file names follow a consistent naming convention that maps to step numbers? Are there any naming anomalies?
16. Are all 25 canon kinds referenced by at least one schema or validator? Are there unused kinds?

**Import Topology (3 questions)**

17. Draw the inter-package dependency graph. The ground truth shows: core/ is a leaf dependency; canonical/ depends on core/; generation/ depends on core/; validation/ depends on core/, canonical/, and generation/; migration/ depends on core/ and generation/. Are there any violations of this layering?
18. validate.py imports from `generation.prompt_schema_sync` — is this a layer violation (validation depending on generation)?
19. Does cli.py use lazy imports for all subpackages, or does it eagerly import everything at module load time?

**Packaging (2 questions)**

20. `tools/UNKNOWN.egg-info/` exists alongside `tools/specdev_tools.egg-info/`. What created the UNKNOWN egg-info? Should both be gitignored?
21. `tools/trace_matrix.json` has all-zero counters and was last modified 2025-02-22. Is this a generated artifact that should be gitignored, or a checked-in seed?

**Documentation (1 question)**

22. Compile all documentation accuracy issues: CLAUDE.md version (0.3.0 vs 0.4.0), tools/README.md version ("v3 Full"), any CLI subcommands documented in CLAUDE.md that don't exist (or vice versa).

### Output Format

Write to: `WIP/tool_audit/p1-out-structure.md`

Use finding format:

```
### FINDING-S{N}: {Title}
- **Severity**: critical | high | medium | low | info
- **Category**: WIRING | STRUCTURE | IMPORTS | PACKAGING | DOCUMENTATION
- **Location**: {file path(s)}
- **Description**: {what is wrong}
- **Evidence**: {specific lines, counts, or diffs}
- **Recommendation**: {what to do}
```

End with a `## PASS` section listing things that are correct and well-structured.

Limit: 200 lines.
