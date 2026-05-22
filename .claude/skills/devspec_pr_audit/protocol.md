# devspec_pr_audit — Operational Protocol

**Version:** 1.0  
**Scope:** Toolkit-internal PR audits only (see §10).  
**Catalog references:** `catalogs.md` (D1–D14, I1–I13). Slice routing: `slices.yaml`.  
**Schema references:** `schema/infra/findings.schema.json` (`vc:infra:findings`), `schema/infra/pr_audit_fix_plan.schema.json` (`vc:infra:pr-audit-fix-plan`).

Agents cite this document by section number (§1, §2, …). Do not paraphrase; quote the section tag.

---

## §1. Six-phase flow

| Phase | ID | Mode | Agent(s) | Description |
|-------|----|------|----------|-------------|
| P0 | `bash-setup` | Bash | — | Branch detection, diff enumeration, Tier-0 checks, slice-routing of changed files |
| P1 | `context` | Loop L1 (cap=4, halt) | `context-author` (sonnet), `context-verifier` (sonnet) | Produce and verify shared context bundle |
| P2 | `discovery` | Fan-out | `discovery-mechanical` (haiku) + `discovery-semantic` (sonnet, N instances) | Run mechanical checks on `semantic_work=false` slices; semantic analysis on `semantic_work=true` slices (digests produced in P0) |
| P3 | `cross-boundary` | Single-pass | `cross-boundary` (sonnet) | Apply drift catalog across slice boundaries |
| P4 | `consolidation` | Loop L2 (cap=4, degrade) | `consolidator` (sonnet) in compose-mode then verify-mode | Merge/dedup findings; build Part B fix plan; verify |
| P5 | `bash-output` | Bash | — | Write Part A + Part B artifacts; emit `SUMMARY.md` |

### Phase detail

**P0 — Bash setup.**  Run Tier-0 checks (§4). Enumerate changed files via `git diff --name-only <base>...<head>`. Route each file via `scripts/route_files.py`, which reads `slices.yaml`'s top-level `{exclusions, slices}`: files matched by any `exclusions[]` glob are dropped silently; remaining files are matched against every slice's `globs[]` (multi-slice membership allowed, `**` matches zero or more path components). Files matching no slice glob are recorded in `out_of_scope_files[]` (see §10). Run extraction scripts (`extract_digest_<type>.sh`) for all changed files; validate via `validate_digests.py` (§5). Invalid digest = P0 halt. Write `docs/audit/runs/<run-id>/.phase_0.done` on success.

**P1 — Context (loop L1).**  `context-author` reads the diff, slice routing, and changed file digests to produce `context_bundle.json` — a shared projection of facts all downstream agents will use. `context-verifier` reviews it for completeness and accuracy. See §2 for loop semantics. On convergence, write `.phase_1.done`.

**P2 — Discovery.**  
- *Tier-1 (mechanical):* `discovery-mechanical` (haiku) handles only slices where `semantic_work: false` (`generated_artifacts`, `host_integration`). Runs deterministic diff-and-compare checks. Emits findings to its designated output path.  
- *Tier-2 (semantic):* `discovery-semantic` (sonnet) instances are dispatched via greedy bin-packing (see §3). Each instance receives: its slice's changed files in full, digests of cross-slice neighbor files, and the applicable D/I subset from `slices.yaml`. Emits findings with `catalog_tag` populated for every item.  

Tier-1 is only dispatched if `generated_artifacts` or `host_integration` slices have changed files. If neither is in scope, skip Tier-1.

**P3 — Cross-boundary.**  `cross-boundary` (sonnet) receives digests for all in-scope slices and applies the cross-boundary-eligible drift types: D1, D2, D3, D6, D7, D8, D9, D12, D14.

> **Note on D11:** D11 (changelog drift) is owned exclusively by the `migration_versioning` slice and is handled entirely by that slice's Tier-2 agent. P3 does **not** apply D11 across boundaries. This is a deliberate scope decision: D11 is a single-authoring-slice concern by construction (`slices.yaml` lines 29–32). The task spec listed D11 in P3's list; this protocol supersedes that listing.
>
> **Note on D13:** D13 is owned by the `canon` and `migration_versioning` slices; their Tier-2 agents handle within-slice D13. P3 does not apply D13 across boundaries.

**P4 — Consolidation.**  `consolidator` in compose-mode merges all Tier-1, Tier-2, and P3 findings, deduplicates by `(kind, location, signature)`, and builds Part B (`fix_plan.json`). Then `consolidator` switches to verify-mode (L2 loop). See §2. On convergence or cap-degrade, write `.phase_4.done`.

**P5 — Bash output.**  Write all output artifacts to `docs/audit/runs/<run-id>/` (§11). Run audit-of-audit hook (§9). Write `.phase_5.done`. Print `SUMMARY.md` path to stdout.

---

## §2. Loop semantics

### L1 — Context loop (P1)

| Property | Value |
|----------|-------|
| Participants | `context-author` (compose), `context-verifier` (review) |
| Cap | 4 rounds |
| On cap | **HALT** — write error to run dir, stop execution, require user intervention (§7) |
| Rationale for halt | Corrupted context propagates silently through all downstream phases; degrade is not safe here |
| Convergence predicate | Verifier emits zero findings |

### L2 — Consolidation loop (P4)

| Property | Value |
|----------|-------|
| Participants | `consolidator` in compose-mode, then `consolidator` in verify-mode |
| Cap | 4 rounds |
| On cap | **DEGRADE** — write `status: PARTIAL` to `manifest.json` + list unresolved verifier deltas in `manifest.json` `meta_findings[]`; continue to P5 |
| Rationale for degrade | Partial output is more useful than no output; user can inspect and re-run from P4 (§7) |
| Convergence predicate | Verifier emits zero findings |

### Verify-only vs full-review rule

**On every loop iteration — including the final round before cap — the review pass is a full review, not a spot-check.**  
Spot-checks must not substitute for full review at any iteration. Empirical basis: spot-checks missed 29 real defects across 3 rounds during schema bring-up.

### Iteration file naming

Both L1 and L2 write per-iteration artifacts to the run dir. Files are named with a loop prefix to disambiguate:

- L1 (P1): `iter_p1_<N>_review.json` only (N = 1…cap) — no fix artifact; the next round's rewritten `context_bundle.json` constitutes the fix
- L2 (P4): `iter_p4_<N>_review.json`, `iter_p4_<N>_fix.json` (N = 1…cap)

L1 review files conform to `vc:infra:findings`. L2 review files conform to `vc:infra:findings`; L2 fix files conform to `vc:infra:pr-audit-fix-plan`. These are the audit trail; they are written but not used as primary outputs — Part A and Part B are the canonical outputs.

---

## §3. Agent contract

All agents operate within the `devspec_pr_audit` skill. **Nested subagents are forbidden** (no Agent tool calls from any agent).

### Agent roster

| Agent name | Model | Tools permitted | Write restriction | Modes |
|------------|-------|-----------------|-------------------|-------|
| `pr-audit-context-author` | sonnet | Read, Glob, Grep, Bash, Write | Own output path only (`context_bundle.json`) | compose |
| `pr-audit-context-verifier` | sonnet | Read, Glob, Grep, Bash, Write | Own output path only (`iter_p1_*_review.json`) | review |
| `pr-audit-discovery-mechanical` | haiku | Read, Glob, Grep, Bash, Write | Own output path only (finding fragments per slice) | mechanical |
| `pr-audit-discovery-semantic` | sonnet | Read, Glob, Grep, Bash, Write | Own output path only (finding fragments per bin) | semantic |
| `pr-audit-cross-boundary` | sonnet | Read, Glob, Grep, Bash, Write | Own output path only (cross-boundary findings) + meta-findings in §9 | cross-boundary, meta-review |
| `pr-audit-consolidator` | sonnet | Read, Glob, Grep, Bash, Write | Own output path only (`findings.json`, `fix_plan.json`, `iter_p4_*`) | compose, verify |

Agent names in §1/§2 narrative use shortened forms (e.g. `context-author`); §3 is the canonical roster with the `pr-audit-` invocation prefix.

**Write restriction:** Every agent may call Write only to its designated output path under `docs/audit/runs/<run-id>/`. No agent may edit source files.  
**Edit tool:** Forbidden for all agents without exception. Agents use Write (never Edit) to their designated output paths.  
**Agent tool:** Forbidden for all agents (no nested subagent dispatch).

### Bin-packing (Tier-2 dispatch)

Impact score per changed file:

```
impact = type_weight(file) × max(1, |expansion_set(file)|) × |applies.drift_types ∪ applies.invariants|
```

where `type_weight` and `applies` come from `slices.yaml` for the file's owning slice.

Greedy bin-packing: assign files to bins in decreasing impact order; open a new bin when the current bin would exceed ~200 units. Each non-empty bin = one `discovery-semantic` invocation. Concurrency cap: 6 agents dispatched in parallel waves. Wave size ≤ 6; start the next wave only after the previous wave completes.

**Worked example.** Three changed files in scope:

```
schema/example_a.schema.json   type_weight=12, expansion_set=4, |applies|=10  → impact = 480
schema/example_b.schema.json   type_weight=8,  expansion_set=3, |applies|=10  → impact = 240
prompts/example_step.md        type_weight=6,  expansion_set=2, |applies|=9   → impact = 108
```

Bin 1: `example_a.schema.json` (480 > 200 alone — single-file bins are permitted when impact > budget).
Bin 2: `example_b.schema.json` (240 > 200 alone — same rule).
Bin 3: `example_step.md` (108 fits).

Result: 3 `discovery-semantic` agents dispatched in one wave. The ~200 unit budget is a starting heuristic; tune after a dry-run measurement pass.

### `cross-boundary` dual mode

`pr-audit-cross-boundary` is used in two contexts:
- **P3 (cross-slice drift):** applies D1, D2, D3, D6, D7, D8, D9, D12, D14 across slice boundaries using digests as the agreement surface. (D11 is intra-slice-only; D13 is handled within its owning slices — see §1 notes.)
- **P5 (audit-of-audit, §9):** single-pass meta-review over consolidated findings for contradictory deltas, duplicate signatures, and missing `upstream_refs` on P0 findings.

The agent receives a `mode` field in its invocation context (`cross_boundary` or `meta_review`) to distinguish the two roles. The P5 invocation is single-pass with no loop.

---

## §4. Tier-0 deterministic check list

Tier-0 checks run in P0 Bash before any agent is dispatched. Each check emits a finding (conforming to `vc:infra:findings`) if it fails, or causes an operational halt (no finding emitted). Findings use the three-severity vocabulary of the findings schema: `P0 | P1 | P2`.

| # | Check name | Command / check | On fail: catalog_tag | Severity | Notes |
|---|-----------|-----------------|----------------------|----------|-------|
| T0-01 | `branch-not-detached` | `git symbolic-ref HEAD` exits 0 | — | **HALT** | Not a finding; user must checkout a branch (§7). No artifact written. |
| T0-02 | `commits-ahead-of-main` | `git rev-list --count main..HEAD` > 0 | — | **EXIT-CLEAN** | Zero commits → print "no changes to audit" and exit 0. No artifact written. |
| T0-03 | `first-commit-edge-case` | If `git merge-base main HEAD` fails (no common ancestor), fall back to `git rev-list --max-parents=0 HEAD` as base | — | Operational fall-back | Not a failure; log chosen base to run manifest. |
| T0-04 | `schema-metaschema-valid` | For each changed `*.schema.json`: validate against JSON Schema Draft 2020-12 metaschema | D5 | P0 | Evidence: file path + validation error message. Implementation: `scripts/tier0_checks.py:T0-04` |
| T0-05 | `json-parse-clean` | For each changed `*.json`: `python3 -c "import json,sys; json.load(open(sys.argv[1]))"` exits 0 | I3 | P0 | Evidence: file path + parse error. Skips intentionally-malformed test fixtures (stems containing "invalid" or "malformed" under `tests/fixtures/`). Implementation: `scripts/tier0_checks.py:T0-05` |
| T0-06 | `schema-registry-targets-exist` | For each entry in `tools/schema_registry.json`: target file path must exist on disk | I4 | P0 | Evidence: registry key + missing path. Implementation: `scripts/tier0_checks.py:T0-06` |
| T0-07 | `no-addl-props-true-regression` | For each changed schema: `additionalProperties: true` must not replace a prior `additionalProperties: false` (diff-check) | D14 | P1 | Evidence: file path + diff hunk. Walks nested schemas (properties, $defs, allOf, anyOf, oneOf, then, else, items, patternProperties). Implementation: `scripts/tier0_checks.py:T0-07` |
| T0-08 | `unrouted-files` | Files in diff not matched by any `slices.yaml` glob | I2 | P2 | Warning. Listed in `out_of_scope_files[]` (§10). Evidence: file list. Implementation: `scripts/tier0_checks.py:T0-08` |
| T0-09 | `changelog-entry-present` | If `migration_versioning` slice changed (non-changelog files), any schema changed, or `cli.py` changed: confirm unreleased changelog entry exists | D11 | P1 | Evidence: slice name + list of changed files with no matching entry. Implementation: `scripts/tier0_checks.py:T0-09` |
| T0-10 | `generated-artifacts-clean` | Run `specdev registry-generate --repo-root . --out <tmp> --extraction-paths-out <tmp>` and diff against committed files; any delta = failure | D9 | P0 | Evidence: diff output. Emits P2 informational finding (not P0 halt) if specdev unavailable. User can override with `--allow-tier0-failure=generated-artifacts-clean` (§7). Implementation: `scripts/tier0_checks.py:T0-10` |
| T0-11 | `new-module-has-test` | For each new `tools/specdev_tools/**/*.py` not previously in `main`: a matching test file must exist under `tests/` (pattern: `test_<module>*.py`) | I8 | P1 | Evidence: new module path + absent test path. Implementation: `scripts/tier0_checks.py:T0-11` |

**Deletion findings (removal audit):** After tier0_checks.py runs, Step 0e.5 invokes
`scripts/removal_audit.py` to detect deleted files and append catalog-tagged findings
to `p0/tier0_findings.json`. Deletions in `canon/**` and generator-owned JSON files
are P0; schema/prompt/validator deletions are P1; others are P2 (D14 fallback).
Implementation: `scripts/removal_audit.py`.

**Operational halts (T0-01, T0-02) do not write findings.json.** They exit with a human-readable message to stdout and return a non-zero exit code (T0-01) or zero exit code (T0-02).

**Override protocol:** Any single Tier-0 check can be bypassed with `--allow-tier0-failure=<check-name>` (one flag per check; no wildcards). Override is logged in the run manifest and logged in `manifest.json`'s `tier0_overrides[]`.

### Evidence templates per check

Agents and Bash scripts constructing findings from Tier-0 failures must use the following evidence field templates. The `location` field uses `file#/path` notation per the findings schema.

**T0-04 (`schema-metaschema-valid`):**
```
location: "schema/<path>/<file>.schema.json"
evidence: ["Metaschema validation error: <error message from jsonschema>", "Line: <N> (if available)"]
```

**T0-05 (`json-parse-clean`):**
```
location: "<file-path>"
evidence: ["JSON parse error: <exception message>"]
```

**T0-06 (`schema-registry-targets-exist`):**
```
location: "tools/schema_registry.json#/<key>"
evidence: ["Registry entry '<key>' points to '<target-path>' which does not exist on disk"]
```

**T0-07 (`no-addl-props-true-regression`):**
```
location: "schema/<path>/<file>.schema.json#/additionalProperties"
evidence: ["Before: additionalProperties: false", "After: additionalProperties: true", "<diff hunk>"]
```

**T0-08 (`unrouted-files`):**
```
location: "<file-path>"
evidence: ["File does not match any glob in slices.yaml; excluded from audit scope"]
```
(One finding per unrouted file. Severity P2 — informational.)

**T0-09 (`changelog-entry-present`):**
```
location: "CHANGELOG.md"
evidence: ["Slice '<slice-name>' has changed files but no matching unreleased changelog entry found",
           "Changed files in slice: <file1>, <file2>, ..."]
```

**T0-10 (`generated-artifacts-clean`):**
```
location: "<generated-file-path>"
evidence: ["Generator drift detected. Run `specdev registry-generate --repo-root .` to regenerate.",
           "Diff excerpt: <first 20 lines of diff>"]
```

**T0-11 (`new-module-has-test`):**
```
location: "tools/specdev_tools/<subpath>/<module>.py"
evidence: ["New module introduced in this PR; no matching test file found under tests/",
           "Expected pattern: tests/**/test_<module>*.py"]
```

---

## §5. Digest layer contract

Digests are skill-local JSON projections of audit-relevant facts extracted per file. They are the primary agreement surface for cross-slice analysis (P3) and reduce raw-file transfer to Tier-2 agents.

### Placement

- Schemas: `.claude/skills/devspec_pr_audit/schemas/digest_<type>.schema.json` (NOT under `schema/infra/` — internal optimization, not host-visible)
- Extractors: `.claude/skills/devspec_pr_audit/scripts/extract_digest_<type>.sh` (Bash + jq for structured files; prose nuance handled inline by Tier-2 reviewer against raw file)
- Validator: `.claude/skills/devspec_pr_audit/scripts/validate_digests.py` — runs `jsonschema` against every digest before P2 fan-out; invalid digest = P0 halt

### Cache key and storage

```
cache key: <file-sha>+<extractor-version>
path:       docs/audit/runs/<run-id>/digests/<digest-type>/<file-slug>.json
```

Cache is per-run, not shared across runs. File SHA uniqueness already holds within a run; per-run isolation simplifies cleanup (see §8).

### Extractor versioning

Each extractor script (`extract_digest_<type>.sh`) carries a version constant in its header comment:

```bash
# EXTRACTOR_VERSION=1.0.0
```

The cache key `<file-sha>+<extractor-version>` means: when an extractor is updated, bump the semver in `EXTRACTOR_VERSION` (patch for backwards-compatible extractor improvements; minor or major if the digest shape changes). On the next run, the old cached digest is silently invalidated (new cache key) and the extractor runs fresh. The version field is also written into each digest JSON as the top-level `extractor_version` field so verifiers can detect stale digests.

### Digest validation before P2

`validate_digests.py` runs `jsonschema` against every digest produced in P0 (or loaded from cache) before any P2 agent is dispatched. If any digest fails schema validation:
- Print the failing digest path and validation error
- Halt with exit code 1 (P0 halt)
- No P2 agents are dispatched

This gate prevents malformed digests from corrupting all downstream analysis silently.

### Reviewer agent access

Every Tier-2 and P3 agent receives: `digest.json` (structured projection) + raw file path. The raw file is an escape hatch for cases where the digest is insufficient; agents should prefer the digest to control token budget.

### Digest types

| Digest type | Source files | Extractor strategy | Key facts captured |
|-------------|-------------|--------------------|--------------------|
| `digest_schema` | `schema/**/*.schema.json` | Bash + jq | `schema_id`, `title`, `required[]` (root-level required names), `optional[]` (root-level optional names), `enums` map (path→values), `patterns` map (path→regex), `refs[]` ($ref targets), `additional_properties_at_root` (bool), `has_definitions`, `def_names[]` |
| `digest_prompt` | `prompts/prompt_NN_*.md` | Bash (section extract); prose nuance handled inline by Tier-2 reviewer against raw file | `step_id`, `schema_uri`, `inputs[]`, `outputs[]`, `gates[]`, `emergent_ambiguities_exit`, `anchors[]`, `section_headers[]`, `negative_constraints_count`, `downstream_consumer_count`, `shared_expectations_required` |
| `digest_validator` | `tools/specdev_tools/validation/**/*.py`, `tools/specdev_tools/generation/**/*.py` | AST (Python `ast` module) | `module_path`, exported check functions, error codes (E-codes) and warning codes (W-codes) emitted, schema paths referenced, guide refs. |
| `digest_cli` | `tools/specdev_tools/cli.py`, subcommand modules | AST + Bash (`--help` capture) | Subcommand names, per-command required and accepted flags, silently-stripped flags, positional args, env-var references. |
| `digest_canon` | `canon/**/*.json` | jq | Canonical IDs declared, namespace prefixes, alias mappings, owner fields, lifecycle/status fields, `kinds[]` |
| `digest_changelog` | `CHANGELOG.md`, `changelog/*.md` | Bash (unreleased section extract) | `version_label` (primary version section, e.g. Unreleased or 0.3.0), `breaking[]`, `added[]`, `changed[]`, `removed[]`, `deprecated[]`, `fixed[]`, `has_breaking_changes`, `section_headers[]` |

---

## §6. Idempotency and recovery

### Run-id format

```
<YYYYMMDD>-<HHMMSS>-<head-short-sha>
```

`head-short-sha` is the 7-character short SHA of the PR head commit. The diff base SHA is recorded inside `docs/audit/runs/<run-id>/manifest.json`, not in the directory name.

### Phase-marker resumption

Each phase writes a marker file on successful completion:

```
docs/audit/runs/<run-id>/.phase_0.done
docs/audit/runs/<run-id>/.phase_1.done
...
docs/audit/runs/<run-id>/.phase_5.done
```

Re-running with the same run-id checks for each marker and skips completed phases. Pass `--from pN` to force replay from phase N regardless of markers.

### Failure modes

| Failure | Behavior |
|---------|----------|
| P0/P5 Bash error | Emit human-readable error to stdout; do not write any partial artifact; exit non-zero |
| P1-P4 agent timeout or crash | Retry once with identical input; second failure → degrade to PARTIAL with failure reason logged in `manifest.json` `meta_findings[]` |
| L1 cap hit | HALT (§2, §7) — no `.phase_1.done` written |
| L2 cap hit | DEGRADE — write `status: PARTIAL` to `manifest.json`; write `.phase_4.done` with `degraded=true` marker |

### Phase immutability

Phase outputs are write-once per run-id. A completed phase's artifacts are not overwritten by subsequent phases or re-runs (unless the user passes `--from pN` to replay from that phase).

---

## §7. User intervention points

| Trigger | Required action | Resume flag |
|---------|----------------|-------------|
| T0-01 `branch-not-detached` halt | Check out a named branch | — (re-run from scratch) |
| T0-02 `commits-ahead-of-main` = 0 | No action needed; exit is clean | — |
| Any Tier-0 P0 failure | Fix the underlying issue, OR pass `--allow-tier0-failure=<check-name>` per failing check | `--from p0` |
| L1 cap halt (P1) | Review `iter_p1_4_review.json` deltas; edit `context_bundle.json` manually if needed | `--from p1` |
| L2 cap degrade (P4) | Add missing findings manually to `findings.json`; resolve noted `meta_findings[]` in `manifest.json` | `--from p4` |

`--allow-tier0-failure` accepts one check name per flag instance (e.g., `--allow-tier0-failure=generated-artifacts-clean --allow-tier0-failure=changelog-entry-present`). Wildcards are not supported.

---

## §8. Caching and WIP usage

**Digest cache:** Per-run, stored under `docs/audit/runs/<run-id>/digests/`. Not shared across runs. Cache invalidation is implicit: a new run-id generates fresh digests. Cleanup: the entire `docs/audit/runs/` tree is gitignored (per existing `.gitignore`).

**WIP/ directory:** NOT used by this skill. `WIP/` is reserved for human-curated working notes. The skill never reads from or writes to `WIP/`.

**Run artifacts:** `docs/audit/runs/<run-id>/` is the canonical output location. All intermediate artifacts (digests, iter files, phase markers) live here and are cleaned up by removing the run directory.

---

## §9. Audit-of-audit (Mode B)

### §9.1 Purpose

Catch framework-side defects that intra-loop verifiers miss:
- Agent output non-conformance (emitted artifacts that fail their declared `$schema`)
- Vacuous fix-plan acceptance commands (acceptance commands that are structurally unchecked: `|| true`, `assert ... or True`, unchecked `subprocess.run`, hardcoded `True`/`pass`)
- Cross-phase consistency drift (findings referenced in `fix_plan.json` that do not exist in `findings.json`; catalog tags not in the canonical D1–D14 / I1–I13 catalog; invented `kind` or `severity` enum values)
- Hallucinated citations (line ranges, file paths, or identifiers in a finding that cannot be verified against the source artifacts)

This operationalizes the principle "auditors must be audited." Every audit run produces a `manifest.json` `meta_findings[]` array that records any framework defects observed during the run.

### §9.2 Trigger

Invoked exactly once per run, after P4 consolidation loop converges (or P4 degrade-on-cap fires) and before P5 finalize writes `SUMMARY.md`.

Dispatch is by SKILL.md §9 (orchestrator). The agent is `pr-audit-cross-boundary` in **Mode B** (`meta_review`). Mode A is the P3 cross-boundary pass (`cross_boundary`); Mode B is the audit-of-audit pass. The invocation is single-pass with no loop.

See `.claude/agents/pr-audit-cross-boundary.md` for the full agent contract and the `§Procedure — Mode B` section.

### §9.3 Inputs

The agent receives four inputs. Three are skip-if-absent (handled gracefully when the path does not exist):

| Input | Path | Skip-if-absent |
|-------|------|----------------|
| Consolidated findings | `docs/audit/runs/<run-id>/findings.json` | No — required |
| Consolidated fix plan | `docs/audit/runs/<run-id>/fix_plan.json` | Yes — absent on no-findings path |
| P2 fragment files | `docs/audit/runs/<run-id>/p2/tier1_*` and `p2/tier2_*` | Yes |
| P3 cross-boundary output | `docs/audit/runs/<run-id>/p3/cross_boundary_findings.json` | Yes |

The agent reads these paths via the Read/Glob tools; it never writes to any of them.

### §9.4 Checks performed

**Schema conformance.** Every artifact listed in §9.3 must validate against its declared `$schema` URI. Schema validation uses the same `jsonschema` library invocation as `scripts/validate_agent_outputs.py` (the CI-side equivalent gate).

**Vacuous acceptance lint.** For each task in `fix_plan.json`, the `acceptance_command` field must not be tautological. See `scripts/assert_meaningful_acceptance.py` for the canonical implementation. Disqualifying patterns (matched by rule ID):
- `pipe_or_true` — `|| true` anywhere in the command string
- `grep_v_bare` — bare `grep -v` not used inside a pipeline
- `or_true_in_py` — `' or True'` in the body of a `python3 -c` argument
- `assert_true` — `assert True` in the body of a `python3 -c` argument
- `subprocess_no_check` — `subprocess.run` without `check=True` or `sys.exit(r.returncode)`
- `empty_command` — empty or whitespace-only command string
- `bash_noop_colon` — `:` Bash no-op as the entire command
- `literal_true` — `true` as the entire command
- `hardcoded_pass` — `printf`/`echo` without any side-effect check

**Cross-phase consistency.** Every `finding_id` referenced in a `fix_plan.json` task's `finding_ids[]` must exist as an `id` in `findings.json`. Every `catalog_tag` in any finding must be one of the canonical D1–D14 / I1–I13 values declared in `catalogs.md`. No invented `kind` enum values (permitted values per `vc:infra:findings`); no invented `severity` enum values.

**Hallucination check.** Every cited `location` (file path + optional `#/json-pointer` or `#Lstart-Lend` line range) in a finding must be verifiable: the file path must exist in the audit's changed-file set or the run artifacts; cited line ranges must fall within the file's actual line count (checked against the digest `line_count` field if available, or by stat).

### §9.5 Outputs

`meta_findings[]` in `manifest.json` — append-only array of framework-defect records. Each entry has the shape:

```json
{
  "phase_observed": "P4",
  "defect_class": "vacuous_acceptance | schema_nonconformance | cross_phase_inconsistency | hallucinated_citation",
  "description": "<human-readable summary>",
  "evidence": ["<artifact path>", "<specific field or line>"]
}
```

No separate `audit_of_audit.json` file is written. The agent appends only to `manifest.json` `meta_findings[]`. It does **not** modify `findings.json` or `fix_plan.json` — meta-findings are framework defects, not PR defects, and `findings.json` must remain strictly conformant to `vc:infra:findings`.

### §9.6 Failure modes

**Non-blocking (default path).** If audit-of-audit detects framework defects, P5 still proceeds. `SUMMARY.md` includes a dedicated `## Meta-findings (audit-of-audit)` section that surfaces the `meta_findings[]` count and full contents. The operator decides whether to act before shipping the audit. Audit-of-audit is an observability mechanism, not a blocking gate.

**Hard gate (schema-invalid consolidated outputs).** If audit-of-audit finds that `findings.json` or `fix_plan.json` themselves are schema-invalid (i.e., the consolidated P4 outputs do not validate against their declared `$schema`), the agent MUST set `status: "blocked"` in `manifest.json` and P5 MUST refuse to write `SUMMARY.md`. The run remains in blocked state until the consolidator reruns and produces valid outputs. Schema validity of the primary output artifacts is a hard gate.

**Implementation status:** This hard-gate is a design specification not yet implemented in code. `validate_agent_outputs.py` exits non-zero on schema violations (CI-side), but the `status: "blocked"` manifest write and SUMMARY.md write-suppression are tracked as hardening backlog items.

### §9.7 Historical motivation

This mechanism was added because the dry-run on commit `5dc3aa1` revealed all 7 P2 agents emitted schema-non-conformant outputs that the orchestrator's normalizer silently recovered — the recovery masked structural schema non-conformance (extra top-level and finding-level fields; `evidence` as object-arrays instead of string-arrays) that would otherwise have shipped invisibly to every subsequent run. See `docs/audit/runs/20260520-183652-5dc3aa1-scoped/SUMMARY.md` for the original observations. (Note: that SUMMARY.md uses the legacy key name `audit_of_audit[]`; the canonical key is now `meta_findings[]` per §9.5.)

---

## §10. Toolkit-vs-host scope guard

This skill audits **only the toolkit submodule** — never host-repo files.

| Rule | Detail |
|------|--------|
| Slice globs are toolkit-scoped | All paths in `slices.yaml` globs are relative to the toolkit root (e.g., `schema/**/*.json`, not `host-repo/devspec_toolkit/schema/**/*.json`) |
| Host-repo files excluded | If the PR diff touches files outside the toolkit submodule path, those files are excluded from all phases and listed in `out_of_scope_files[]` in Part A |
| Output schemas are host-visible | Host repos that consume the toolkit as a submodule may use `findings.schema.json` and `pr_audit_fix_plan.schema.json` — they consume outputs, not the skill itself |
| `spec/` dir | A host repo's `spec/canon/**` is out of scope unconditionally; it lives outside the toolkit submodule path and is never included in the PR diff for a toolkit-only audit. The `canon/` slice covers only toolkit-tier `canon/**`. |

---

## §11. Output artifacts

All artifacts written to `docs/audit/runs/<run-id>/`.

| Artifact | Schema / type | Description |
|----------|--------------|-------------|
| `findings.json` | `vc:infra:findings` | Part A — merged, deduped findings from all phases |
| `fix_plan.json` | `vc:infra:pr-audit-fix-plan` | Part B — ordered atomic fix tasks |
| `context_bundle.json` | (skill-internal) | P1 context-author output; shared by all downstream agents |
| `manifest.json` | (skill-internal) | Run metadata: run-id, base SHA, head SHA, T0 overrides, phase timestamps |
| `digests/` | per `digest_<type>.schema.json` | Per-file digest projections; organized by digest type |
| `iter_p1_<N>_review.json` | `vc:infra:findings` | L1 per-iteration review output (N = 1…cap); no fix artifact — rewritten `context_bundle.json` constitutes the fix |
| `iter_p4_<N>_review.json` | `vc:infra:findings` | L2 per-iteration review output (N = 1…cap) |
| `iter_p4_<N>_fix.json` | `vc:infra:pr-audit-fix-plan` | L2 per-iteration fix output |
| `.phase_N.done` | marker file | Written on phase N completion; drives resumption logic (§6) |
| `SUMMARY.md` | Markdown | Human-readable summary: finding counts by severity (P0/P1/P2), by slice, by catalog_tag; PARTIAL banner if L2 degraded |

### Severity and priority mapping

- `findings.json` uses the three-bucket severity vocabulary: `P0 | P1 | P2` (schema-locked in `vc:infra:findings`).
- `fix_plan.json` uses the four-bucket priority vocabulary: `P0 | P1 | P2 | P3` (schema-locked in `vc:infra:pr-audit-fix-plan`).
- Mapping rule: a P0 or P1 finding must be addressed by a P0 or P1 fix-plan task. A P2 finding may map to a P2 (medium) or P3 (low/cleanup) task. Using P3 to defer a P0 or P1 finding is a governance violation; the L2 verifier must reject it.

### `STATUS: PARTIAL` banner

When L2 degrades (cap=4 hit), `manifest.json` receives a top-level `status: "PARTIAL"` field and `meta_findings[]` lists each unresolved verifier delta with a short description. `findings.json` remains strictly conformant to `vc:infra:findings` — no `status` or `meta_findings` extension is added to it. `SUMMARY.md` opens with `STATUS: PARTIAL — see manifest.json meta_findings[] for unresolved items`.

`manifest.json` is skill-internal and has no schema lock — extending its fields is safe; `findings.json` is shared via `vc:infra:findings` and must stay strictly conformant.

### `manifest.json` structure

`manifest.json` is written by P0 and updated at each phase boundary. Minimum required fields:

```json
{
  "run_id": "20260520-143201-a3f9b2c",
  "head_sha": "a3f9b2c",
  "base_sha": "e57ca61",
  "branch": "my-feature-branch",
  "phases_completed": [0],
  "tier0_overrides": [],
  "slices_in_scope": ["schemas", "prompts"],
  "out_of_scope_files": [],
  "created_at": 1747743121,
  "updated_at": 1747743121
}
```

`phases_completed` is appended at each `.phase_N.done` write. `tier0_overrides` records any `--allow-tier0-failure` flags passed by the user. `out_of_scope_files` is populated by T0-08.

### `SUMMARY.md` format

```markdown
# PR Audit Summary — <run-id>

STATUS: OK  (or: STATUS: PARTIAL — see manifest.json meta_findings[])

Branch: <branch> (<head-sha> vs <base-sha>)
Slices in scope: <list>
Findings total: P0=N, P1=N, P2=N

## By slice
| Slice | P0 | P1 | P2 |
|-------|----|----|-----|
| ...   |    |    |     |

## By catalog tag
| Tag | Count |
|-----|-------|
| D5  | N     |
| ...       |

## Fix plan
Tasks total: N  (P0=N, P1=N, P2=N, P3=N)
See fix_plan.json for full task list.
```
