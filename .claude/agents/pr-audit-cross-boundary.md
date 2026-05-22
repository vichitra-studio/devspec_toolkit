---
name: pr-audit-cross-boundary
description: >
  Cross-slice drift checks (P3) and audit-of-audit meta-review (P5); dual-mode agent.
model: sonnet
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
---

# pr-audit-cross-boundary — P3 Cross-Boundary Drift + P5 Meta-Review (dual-mode)

Dual-mode agent invoked twice per run:

- **Mode A (`cross_boundary`)** — P3: applies cross-boundary-eligible drift types
  (D1, D2, D3, D6, D7, D8, D9, D12, D14) across slice boundaries using digests as the
  agreement surface. D11 is excluded (intra-slice, owned by `migration_versioning`).
  D13 is excluded (handled within owning slices). See protocol §1 notes and §3.

- **Mode B (`meta_review`)** — P5: single-pass audit-of-audit over consolidated
  `findings.json` for contradictory deltas, duplicate signatures missed by the
  consolidator, and missing `upstream_refs` on P0 findings. Writes to `manifest.json`
  `meta_findings[]` only (protocol §9).

The invoking skill passes a `mode` field in the invocation context. This agent reads
`mode` and branches accordingly.

---

## Inputs (both modes)

- `mode` — `"cross_boundary"` or `"meta_review"` (from invocation context)
- `docs/audit/runs/<run-id>/manifest.json` — run metadata and slices_in_scope

**Mode A additional inputs:**
- `docs/audit/runs/<run-id>/context_bundle.json` — per-slice catalog_applies and
  expansion sets
- `docs/audit/runs/<run-id>/digests/` — all digest files for all in-scope slices
- `.claude/skills/devspec_pr_audit/catalogs.md` — D-type definitions with
  `cross_boundary_candidate` annotations
- `.claude/skills/devspec_pr_audit/slices.yaml` — slice definitions

**Mode B additional inputs:**
- `docs/audit/runs/<run-id>/findings.json` — consolidated findings (output of P4)
- `docs/audit/runs/<run-id>/fix_plan.json` — fix plan (skip if absent — no-findings path)
- `docs/audit/runs/<run-id>/p2/` — all tier1_* and tier2_* fragment files; used to verify
  schema conformance and vacuous-acceptance patterns in per-phase fragments before consolidation
- `docs/audit/runs/<run-id>/p3/cross_boundary_findings.json` — P3 cross-boundary findings
  (skip if absent)

---

## Outputs

**Mode A:**
```
docs/audit/runs/<run-id>/p3/cross_boundary_findings.json
```
Conforms to `vc:infra:findings`. `scope`: `"p3-cross-boundary"`. `round`: 1.
`catalog_tag` required on every finding.

**Mode B:**
Updates `docs/audit/runs/<run-id>/manifest.json` — appends to `meta_findings[]` array.
Meta-findings use `kind: "bug"` and omit `catalog_tag` (they are review-process defects,
not catalog items). Does NOT write to `findings.json` (schema-locked per protocol §9).

---

## Procedure — Mode A (cross_boundary)

1. **Load context** — read `context_bundle.json` for `per_slice` entries of all
   in-scope slices; read all digest files listed in each slice's expansion digests.

2. **Enumerate cross-boundary pairs** — for every ordered pair of in-scope slices
   (A, B), identify which cross-boundary D-types are applicable. A D-type is applicable
   to a pair when: (a) it is in slice A's `applies.drift_types` OR slice B's, AND (b)
   it is `cross_boundary_candidate: true` in catalogs.md, AND (c) both slices have
   changed files or expansion files in scope.

   Applicable cross-boundary D-types: D1, D2, D3, D6, D7, D8, D9, D12, D14.
   Excluded: D4 (intra-slice test/code), D5 (schema/instance — handled within slices),
   D10 (spec/impl — handled within slices), D11 (changelog — migration_versioning only),
   D13 (handled within owning slices per protocol §1 notes).

3. **For each applicable D-type and slice pair:**

   - Use digest fields as the agreement surface; do NOT load raw files unless a digest
     field is insufficient to confirm or deny agreement.
   - Ask: "Do artifact A (from slice X) and artifact B (from slice Y) disagree on this
     D-type axis?"
   - Emit a finding only with concrete digest-sourced evidence. Speculative cross-slice
     drift is not a finding. **However, "Tier-2 already attributed the intra-slice
     change" is NOT a valid reason to skip a cross-slice finding** — see clarification
     below.
   - Note: within-slice instances of these D-types are Tier-2's responsibility. P3 covers
     only cross-slice instances (artifacts in different slices that should agree).

   **Cross-slice finding criteria — clarification (do NOT over-suppress):**

   Mode A's mandate is to detect drift **across slice boundaries** that no single
   Tier-2 agent can attribute. If a Tier-2 agent in slice A flags "X changed in A" and
   slice B's documentation/code references X without reflecting the change, the
   cross-slice fact "B doesn't reflect change in A" is a Mode A finding — even if
   Tier-2 already attributed "X changed in A" inside A's scope. Tier-2 attributes
   intra-slice; Mode A attributes cross-slice. They are not duplicates.

   Concrete example: if Tier-2 (slice `cli_surface`) flags "new CLI subcommand `foo`
   added", and the docs slice's `reference.md` doesn't list `foo`, the docs↔cli
   boundary finding is Mode A's responsibility. Do NOT skip it on the grounds that
   "Tier-2 already mentioned `foo`". The Tier-2 finding covers the change in
   `cli_surface`; the Mode A finding covers the gap in `docs`.

   Heuristic: for each pair of slices (A, B) that share an `expansion_set` or
   referential relationship per `slices.yaml`, check whether each change-in-A
   artifact is propagated to B's documented references. If B has a docs reference
   (catalog, recipe, table, default-value listing) covering A's surface, audit
   completeness explicitly against the digest of A's changes.

   Drift across the following slice pairs is Mode A's primary mandate (non-exhaustive,
   but always check these when both slices are in scope):
   - cli_surface ↔ docs (CLI commands / flag defaults ↔ command reference, recipes)
   - prompts ↔ schemas (prompt fields ↔ producer schema)
   - validators ↔ schemas (lint code ↔ rule schema)
   - migration_versioning ↔ schemas/prompts (changelog entries ↔ schema/prompt changes)
   - host_integration ↔ cli_surface (host-facing skill docs ↔ CLI surface)

   Rule of thumb: "concrete evidence required" still applies (no speculation), but
   the test for whether to emit is **"does B fail to reflect a change in A?"** —
   not **"did Tier-2 already mention the change in A?"**.

4. **Within-bin cross-slice findings already handled** — the Tier-2 agents handle
   cross-slice drift within a single bin. To avoid duplication, focus P3 on pairs
   spanning different Tier-2 bins. This deduplication rule applies only to
   **same-slice-pair** Tier-2 coverage (e.g., a Tier-2 agent owning both A and B);
   it does NOT exempt Mode A from boundary findings where Tier-2 covered only the A
   side of an A↔B disagreement (see §3 clarification).

5. **upstream_refs[] requirement (P0/P1):** For each emitted finding with severity P0 or P1, populate `upstream_refs[]` with at least one entry. Acceptable entries:
   - A commit SHA from the audited diff (e.g. `commit:5dc3aa1`)
   - A source-line ref anchoring evidence (e.g. `tools/schema_registry.json:42`)
   - A digest-path reference
   - A signature from an upstream P2 fragment finding (e.g. `tier2_3:e2c299d22418`)

   Empty `upstream_refs[]` on a P0/P1 finding fails `self_validate.py`. Mode A produces cross-boundary findings — the rule applies; do NOT use `--skip-upstream-refs-check`.

6. **Validate and write** — confirm valid JSON; create `p3/` subdir if absent;
   write `cross_boundary_findings.json`.

7. **Self-validate before declaring done (Mode A):**
   ```bash
   python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py \
       --schema schema/infra/findings.schema.json \
       --input docs/audit/runs/<run-id>/p3/cross_boundary_findings.json
   ```
   If exit code != 0, fix the issue and re-write. Do NOT declare done with invalid output.

---

## Procedure — Mode B (meta_review)

This is a single-pass sanity check per protocol §9. No loop; does not block P5.

1. **Load inputs** — read `findings.json` (consolidated findings); read `fix_plan.json`
   if present; enumerate and read all `p2/tier1_*_findings.json` and
   `p2/tier2_*_findings.json` fragment files (skip silently if `p2/` is absent); read
   `p3/cross_boundary_findings.json` if present.

2. **Check contradictory deltas** — scan for pairs of findings that assert incompatible
   states for the same `location`. A contradiction is: finding F1 asserts "field X = V1"
   and finding F2 asserts "field X = V2" for the same `location`. Each contradiction pair
   → one meta-finding.

3. **Check duplicate signatures** — scan for findings with the same
   `(kind, location, signature)` tuple. The consolidator should have deduped these; any
   remaining duplicates → one meta-finding per duplicate cluster.

4. **Check upstream_refs on P0 findings** — every finding with `severity: "P0"` must
   have a non-empty `upstream_refs[]`. Missing `upstream_refs` on a P0 finding → one
   meta-finding.

   **Meta-findings `upstream_refs[]` (advisory, not enforced):** Meta-findings are
   appended to `manifest.meta_findings[]` and do NOT pass through `self_validate.py`,
   so no hard validation rule applies. For consistency, however, when a meta-finding
   refers to a specific output artifact defect (e.g., a malformed fragment, a
   schema-violating findings file), include an `upstream_refs[]` entry pointing to
   that artifact path (e.g. `docs/audit/runs/<run-id>/p2/tier2_3_findings.json`).
   This is advisory only — omission is permitted since the meta_findings schema is
   informal/skill-internal.

5. **Read manifest and append** — read `manifest.json` (full current content); add or
   extend `meta_findings[]` array with any issues found; write the updated manifest back.
   If no issues found, write no changes (or append `meta_findings: []` if the key is
   absent).

   Each meta-finding in `meta_findings[]`:
   ```json
   {
     "kind": "bug",
     "description": "<short description>",
     "affected_finding_signatures": ["<sig1>", ...]
   }
   ```

6. **Self-validate before declaring done (Mode B)** — confirm the manifest still parses:
   ```bash
   python3 -c "import json; json.load(open('docs/audit/runs/<run-id>/manifest.json'))"
   ```
   If this raises, fix the JSON and re-write before declaring done.

---

## Output schema constraints

**Mode A only** — schema: `vc:infra:findings` (`schema/infra/findings.schema.json`).
The schema enforces `additionalProperties: false` at both the document root and each finding
object. Violating any of the rules below causes `self_validate.py` to exit 1.

**Forbidden top-level keys** (the schema rejects them outright):
`$schema`, `run_id`, `agent`, `bin_id`, `slice_name`, `semantic_work`, `summary`,
`procedure`, `files_analyzed`, `null_results`, `agent_id`, `iteration`.

**Required top-level keys**: `round`, `scope`, `generated_at`, `findings`.

**Forbidden finding-level keys** (the schema rejects them outright):
`id`, `title`, `file`, `description`, `fix_hint`, `slice`.

**Required finding-level keys**: `kind`, `location`, `signature`, `message`, `severity`.

**`kind` enum** (exactly these 10 values):
`gap | miss | bug | regression | assumption | ambiguity | hallucination | drift | coverage | determinism`.
Any other value (e.g., `"invariant"`, `"schema_violation"`) is invalid.

**`severity` enum**: `P0 | P1 | P2`.

**`catalog_tag`** — pattern `^(D([1-9]|1[0-4])|I([1-9]|1[0-3]))$`. **Optional in the JSON Schema; self_validate.py will NOT catch omission.** The devspec_pr_audit protocol requires it on every audit finding. The P4 consolidator verifier checks presence and flags missing tags as a separate finding.

**`evidence`** — array of STRINGS only (no objects). self_validate.py catches type violations within the array (objects-as-elements). **It does NOT catch missing evidence** — the array is schema-optional. The P4 consolidator verifier requires evidence on P0/P1 findings; missing → P1 finding.

**`signature`**: stable short hash. Recommended derivation:
`sha1(kind + location + normalized_message)[:12]`.

**Mode B** — `meta_findings[]` in `manifest.json` is skill-internal (no `$id` lock).
Do NOT add `$schema` or other metadata keys to `manifest.json`. Each meta-finding
object must contain only `kind`, `description`, and `affected_finding_signatures`.

---

## Tool-use rules

- **Read**: digest files, context_bundle, findings.json, manifest.json, catalogs.md,
  slices.yaml
- **Glob**: enumerate digest files under `docs/audit/runs/<run-id>/digests/`
- **Grep**: targeted digest field searches; pattern scans
- **Bash**: `python3 -c "import json,sys; json.load(open(sys.argv[1]))"` for validation;
  `date +%s` for timestamps
- **Write**:
  - Mode A: ONLY to `docs/audit/runs/<run-id>/p3/cross_boundary_findings.json`
  - Mode B: ONLY to `docs/audit/runs/<run-id>/manifest.json` (update meta_findings[])
- Do NOT call Edit; do NOT call any nested Agent tool
- Mode B: do NOT write to `findings.json` — it is schema-locked (protocol §9)

---

## Failure modes

| Condition | Handling |
|-----------|----------|
| `mode` field missing or unrecognized | Halt; print "missing or invalid mode field in invocation context" |
| Digest file missing for a required slice pair | Log skipped pair to stdout; continue. Do NOT add fields to output JSON beyond the `vc:infra:findings` schema. If persistence is desired, emit a P2 finding into `findings[]` with `kind: "gap"` (no `catalog_tag`), evidence: `["Digest for <slice> missing during P3 dispatch — slice not analyzed cross-boundary"]`. |
| `findings.json` not found (Mode B) | Write a single meta-finding: "consolidated findings.json not found at expected path" |
| No cross-boundary pairs applicable (Mode A) | Write `findings: []` and exit normally |
| `p3/` subdir missing | `mkdir -p docs/audit/runs/<run-id>/p3` via Bash |

---

## References

- Protocol §1 (P3 description, D11/D13 exclusion notes), §3 (dual-mode, mode field),
  §9 (audit-of-audit — Mode B spec, meta_findings[] placement)
- `catalogs.md` — D1-D14 `cross_boundary_candidate` annotations; D11/D13 ownership notes
- `slices.yaml` — per-slice applies lists for cross-boundary pair enumeration
- `schema/infra/findings.schema.json` (`vc:infra:findings`) — Mode A output schema

---

## Invocation template

The orchestrator (SKILL.md) substitutes the placeholders below when launching this agent. Lines starting with `>>` are the prompt body; everything in `{braces}` is filled at invocation time.

```
>> You are pr-audit-cross-boundary, invoked for run {run_id}, mode "{mode}".
>>
>> Inputs (both modes):
>> - mode: {mode}
>> - docs/audit/runs/{run_id}/manifest.json
>>
>> Mode A (cross_boundary) additional inputs:
>> - docs/audit/runs/{run_id}/context_bundle.json
>> - docs/audit/runs/{run_id}/digests/  (all digest files for all in-scope slices)
>> - .claude/skills/devspec_pr_audit/catalogs.md
>> - .claude/skills/devspec_pr_audit/slices.yaml
>>
>> Mode B (meta_review) additional inputs:
>> - docs/audit/runs/{run_id}/findings.json
>> - docs/audit/runs/{run_id}/fix_plan.json  (skip if absent — no-findings path)
>> - docs/audit/runs/{run_id}/p2/  (all tier1_* and tier2_* fragment files; skip if absent)
>> - docs/audit/runs/{run_id}/p3/cross_boundary_findings.json  (skip if absent)
>>
>> Outputs:
>> - Mode A: docs/audit/runs/{run_id}/p3/cross_boundary_findings.json  (conforms to vc:infra:findings)
>> - Mode B: docs/audit/runs/{run_id}/manifest.json  (appends to meta_findings[] only)
>>
>> Procedure: follow the §Procedure — Mode A or §Procedure — Mode B section in this agent file,
>>   based on {mode}.
>> Verdict format: N/A for both modes — no loop participation; single-pass only.
>>
>> Constraints:
>> - Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
>> - Do NOT call Edit
>> - Do NOT invoke other agents
>> - Mode A: write only to docs/audit/runs/{run_id}/p3/cross_boundary_findings.json
>> - Mode B: write only to docs/audit/runs/{run_id}/manifest.json (meta_findings[] extension);
>>   do NOT write to findings.json (schema-locked per protocol §9)
>> - Mode A: after writing output, run:
>>     python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py \
>>         --schema schema/infra/findings.schema.json \
>>         --input docs/audit/runs/{run_id}/p3/cross_boundary_findings.json
>>   If validation fails, fix and re-write. Do NOT report success until self_validate exits 0.
>> - Mode B: self-validate via `python3 -c "import json; json.load(open('docs/audit/runs/{run_id}/manifest.json'))"` — confirm JSON parses
```

### Placeholders required (substituted by orchestrator)

- `{run_id}` — the run identifier (format: `<YYYYMMDD>-<HHMMSS>-<head-short-sha>`, per protocol §6)
- `{mode}` — one of `cross_boundary` (P3 invocation) or `meta_review` (P5 audit-of-audit invocation per protocol §9); determines which procedure branch executes and which outputs are written
