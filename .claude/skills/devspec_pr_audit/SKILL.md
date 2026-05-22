---
name: devspec_pr_audit
description: >
  Per-PR audit of the devspec_toolkit (branch diff vs main). Six-phase pipeline detects
  drift across schemas, prompts, validators, canon, CLI surface, and docs.
  Trigger on: "/devspec_pr_audit", "audit this PR", "run pr audit", "check toolkit drift",
  or any request to audit toolkit-internal changes on a feature branch.
---

# /devspec_pr_audit — PR Audit Pipeline

Six-phase orchestrator for toolkit-internal PR audits. Phases run in order; each writes
a phase marker on success. Artifacts land in `docs/audit/runs/<run-id>/`.

**Scope:** Toolkit submodule only (protocol §10). Never audits host-repo files.

**References:**
- `.claude/skills/devspec_pr_audit/protocol.md` (§-tagged throughout)
- `.claude/skills/devspec_pr_audit/catalogs.md`
- `.claude/skills/devspec_pr_audit/slices.yaml`
- `schema/infra/findings.schema.json` (`vc:infra:findings`)
- `schema/infra/pr_audit_fix_plan.schema.json` (`vc:infra:pr-audit-fix-plan`)

---

## 1. When to invoke

- User types `/devspec_pr_audit` (with or without flags).
- Current branch must have at least one commit ahead of `main` (protocol §4, T0-02).
- This skill audits **the toolkit submodule itself** — not host-repo specs, not `spec/` dirs.
- Run from the toolkit root (cwd = `devspec_toolkit/` or wherever the toolkit lives).

---

## 2. Inputs

The skill reads branch state. No files are required from the caller.

**Optional flags:**

```
/devspec_pr_audit [--from <phase>] [--base <ref>] [--allow-tier0-failure=<check-name>]...
```

- `--from p0|p1|p2|p3|p4|p5` — resume from a specific phase (skips phases with existing
  `.phase_N.done` markers; see §10 Resumption).
- `--base <ref>` — explicit base ref override for diff and commit-count checks
  (e.g. `--base origin/main`, `--base v1.2.0`). If not supplied, defaults to `main`.
  Used in T0-02, Step 0b `merge-base`, and Step 0d `git diff`. Fixes cases where the
  default `main` ref is 185+ commits behind the actual merge base (e.g., long-lived
  feature branches off a different upstream).
- `--allow-tier0-failure=<check-name>` — override a specific Tier-0 P0 failure by name
  (e.g. `--allow-tier0-failure=generated-artifacts-clean`). Repeat per check.
  No wildcards. Overrides logged in `manifest.json` (protocol §7).

---

## 3. Outputs

All artifacts under `docs/audit/runs/<run-id>/`:

| File | Schema / type | Description |
|------|---------------|-------------|
| `findings.json` | `vc:infra:findings` | Part A — merged, deduped findings from all phases |
| `fix_plan.json` | `vc:infra:pr-audit-fix-plan` | Part B — ordered atomic fix tasks (absent if no findings) |
| `manifest.json` | skill-internal | Run metadata, phase timestamps, T0 overrides, status |
| `SUMMARY.md` | Markdown | Human-readable counts by severity, slice, catalog_tag |
| `context_bundle.json` | skill-internal | P1 author output; shared by all downstream agents |
| `digests/<type>/<slug>.json` | per `digest_<type>.schema.json` | Per-file digest projections |
| `p0/tier0_findings.json` | `vc:infra:findings` | Tier-0 check failures (P0–P2) |
| `p2/tier1_<slice>_findings.json` | `vc:infra:findings` | Tier-1 mechanical findings per slice |
| `p2/tier2_<bin_id>_findings.json` | `vc:infra:findings` | Tier-2 semantic findings per bin |
| `p3/cross_boundary_findings.json` | `vc:infra:findings` | Cross-slice drift findings |
| `iter_p1_<N>_review.json` | `vc:infra:findings` | L1 per-iteration verifier output |
| `iter_p4_<N>_review.json` | `vc:infra:findings` | L2 per-iteration verifier output |
| `iter_p4_<N>_fix.json` | `vc:infra:pr-audit-fix-plan` | L2 per-iteration composer output |
| `.phase_N.done` | marker file | Written on phase N completion; drives resumption |

**manifest.json update pattern** (used at every phase boundary — orchestrator must not use
Edit; use jq + temp file):

```bash
jq --argjson phase 1 '.phases_completed = (.phases_completed + [$phase] | unique) | .updated_at = (now | floor)' \
  docs/audit/runs/$RUN_ID/manifest.json > /tmp/manifest_tmp.json \
  && mv /tmp/manifest_tmp.json docs/audit/runs/$RUN_ID/manifest.json
```

Adapt for other fields (`status`, `meta_findings`, `tier0_overrides`) using the same
`jq ... > tmp && mv tmp` pattern.

**phase_trace append pattern** (used at every phase boundary alongside the
`phases_completed` update — appends one entry per phase to `manifest.json` `.phase_trace[]`):

```bash
ENTRY=$(jq -n \
  --argjson phase <N> \
  --arg phase_name "<P0 deterministic|P1 context|P2 discovery|P3 cross-boundary|P4 consolidation|P5 finalize>" \
  --argjson started_at <unix-epoch-from-corresponding-section> \
  --argjson ended_at "$(date +%s)" \
  --argjson loop_iterations <int-or-null> \
  --arg outcome "<OK|DEGRADED|HALTED>" \
  '{phase:$phase, phase_name:$phase_name, started_at:$started_at, ended_at:$ended_at, loop_iterations:$loop_iterations, outcome:$outcome}')

jq --argjson e "$ENTRY" '.phase_trace = ((.phase_trace // []) + [$e]) | .phases_completed = (.phases_completed + [<N>] | unique) | .updated_at = (now | floor)' \
  docs/audit/runs/$RUN_ID/manifest.json > /tmp/manifest_tmp.json \
  && mv /tmp/manifest_tmp.json docs/audit/runs/$RUN_ID/manifest.json
```

Conventions for entry fields:
- `loop_iterations`: `null` for P0/P2/P3/P5 (no loop); the converged iteration count for P1 and P4.
- `outcome`: `"OK"` on convergence, `"DEGRADED"` on L2 cap (P4), `"HALTED"` on L1 cap (P1).

The §§4-9 phase-completion blocks reference this canonical pattern rather than re-printing it
in full each time.

---

## 4. P0 — Bash Pre-flight

### Orchestrator steps

**Step 0a — Operational halts (run before creating any directories):**

Parse the `--base` flag here so T0-02 and later steps share a single variable:

<!-- Template note: $1, $1#--base=*}, and other "$1" expressions in this block are Bash positional-arg references evaluated at runtime, NOT skill-render-time substitutions. They must remain literal "$1" in the rendered skill output. -->

```bash
# Parse --base flag (default: main)
BASE_REF=main
while [ $# -gt 0 ]; do
  case "$1" in
    --base=*) BASE_REF="${1#--base=}"; shift ;;
    --base)   shift; BASE_REF="$1"; shift ;;
    *)        shift ;;
  esac
done
```

```bash
# T0-01: must be on a named branch
git symbolic-ref HEAD > /dev/null 2>&1 \
  || { echo "ERROR: HEAD is detached. Check out a named branch before auditing."; exit 1; }

# T0-02: must have commits ahead of base ref
AHEAD=$(git rev-list --count "${BASE_REF}..HEAD")
[ "$AHEAD" -gt 0 ] \
  || { echo "No commits ahead of ${BASE_REF}. Nothing to audit."; exit 0; }
```

These exit before any artifact is written (protocol §4, §6).

**Step 0b — Compute run-id and create run directory:**

`$BASE_REF` is set in Step 0a (default: `main`; overridable via `--base <ref>`). Use it
consistently here and in all downstream git commands so the operator can pass
`--base origin/main` or a tag when the default ref is wrong.

```bash
HEAD_SHA=$(git rev-parse --short HEAD)
RUN_ID=$(date -u '+%Y%m%d-%H%M%S')-${HEAD_SHA}
BASE_SHA=$(git merge-base "${BASE_REF}" HEAD 2>/dev/null || git rev-list --max-parents=0 HEAD)
BRANCH=$(git symbolic-ref --short HEAD)

mkdir -p docs/audit/runs/$RUN_ID/digests \
         docs/audit/runs/$RUN_ID/p0 \
         docs/audit/runs/$RUN_ID/p2 \
         docs/audit/runs/$RUN_ID/p3
```

If `git merge-base` fails (T0-03 fall-back), log the chosen base in manifest.json.

**Step 0c — Initialize manifest.json:**

```bash
cat > docs/audit/runs/$RUN_ID/manifest.json <<EOF
{
  "run_id": "$RUN_ID",
  "head_sha": "$HEAD_SHA",
  "base_sha": "$BASE_SHA",
  "branch": "$BRANCH",
  "phases_completed": [],
  "phase_trace": [],
  "tier0_overrides": [],
  "slices_in_scope": [],
  "out_of_scope_files": [],
  "created_at": $(date +%s),
  "updated_at": $(date +%s)
}
EOF
```

**Step 0d — Enumerate diff and route to slices:**

```bash
git diff --name-only "${BASE_REF}...HEAD" > docs/audit/runs/$RUN_ID/p0/diff_files.txt

python3 .claude/skills/devspec_pr_audit/scripts/route_files.py \
  --diff-file docs/audit/runs/$RUN_ID/p0/diff_files.txt \
  > docs/audit/runs/$RUN_ID/p0/routing.json
```

`route_files.py` reads `slices.yaml` (top-level mapping `{exclusions, slices}`), drops
files matching any `exclusions[]` glob, then routes the remainder. A file may belong
to multiple slices (matches are not exclusive). `**` in globs matches zero or more
path components.

Extra runtime exclusions (e.g. for the audit skill auditing itself, or specific
sub-directories) may be passed via `--extra-exclude '<glob>'` (repeatable).

After routing, update `manifest.json`:
- `slices_in_scope` ← `routing.json` `.slices_in_scope`
- `out_of_scope_files` ← `routing.json` `.unrouted`

Emit one T0-08 finding per **unrouted** file (P2, catalog_tag: "I2", kind `gap`,
location = file path) — aggregate all into `p0/tier0_findings.json`. **Excluded**
files (matched by exclusions) are NOT findings — they are intentional drops.

**Step 0e — Run Tier-0 checks (T0-04 through T0-11):**

```bash
# Ensure fresh write — Tier-0 checks may have changed since prior run.
rm -f docs/audit/runs/$RUN_ID/p0/tier0_findings.json

python3 .claude/skills/devspec_pr_audit/scripts/tier0_checks.py \
  --run-dir docs/audit/runs/$RUN_ID \
  --routing docs/audit/runs/$RUN_ID/p0/routing.json \
  --head-sha $HEAD_SHA \
  --base-sha $BASE_SHA \
  [--allow-tier0-failure=<check-name>]...
```

The script executes all 8 checks, writes `p0/tier0_findings.json` (conformant to
`vc:infra:findings`, round=1, scope="tier0"), updates `manifest.json`
`tier0_overrides[]` for any `--allow-tier0-failure` flags, and exits non-zero if
any unoverridden P0 findings exist (orchestrator halt condition).

Check table (reference — `tier0_checks.py` is the authoritative executor):

| Check | Implementation | Severity | catalog_tag |
|-------|---------------|----------|-------------|
| T0-04 `schema-metaschema-valid` | `tier0_checks.py:T0-04` | P0 | D5 |
| T0-05 `json-parse-clean` | `tier0_checks.py:T0-05` | P0 | I3 |
| T0-06 `schema-registry-targets-exist` | `tier0_checks.py:T0-06` | P0 | I4 |
| T0-07 `no-addl-props-true-regression` | `tier0_checks.py:T0-07` | P1 | D14 |
| T0-08 `unrouted-files` | `tier0_checks.py:T0-08` | P2 | I2 |
| T0-09 `changelog-entry-present` | `tier0_checks.py:T0-09` | P1 | D11 |
| T0-10 `generated-artifacts-clean` | `tier0_checks.py:T0-10` | P0 | D9 |
| T0-11 `new-module-has-test` | `tier0_checks.py:T0-11` | P1 | I8 |

Use evidence templates from protocol §4 for each finding's `location` and `evidence[]` fields.

**Step 0e.5 — Removal audit:**

```bash
python3 .claude/skills/devspec_pr_audit/scripts/removal_audit.py \
  --run-dir docs/audit/runs/$RUN_ID \
  --head-sha $HEAD_SHA \
  --base-sha $BASE_SHA \
  [--allow-tier0-failure=<check-name>]...
```

Detects deleted files and appends catalog-tagged findings to `p0/tier0_findings.json`.
Run AFTER Step 0e (tier0_checks.py must have written the file first).
Severity: P0 for `canon/**` and generator-owned JSON deletions; P1 for schema/prompt/validator
deletions; P2 for other deletions.

**Step 0f — Extract digests:**

```bash
python3 .claude/skills/devspec_pr_audit/scripts/extract_all_digests.py \
  --routing docs/audit/runs/$RUN_ID/p0/routing.json \
  --run-id $RUN_ID \
  --run-dir docs/audit/runs/$RUN_ID
```

Dispatches per-file digest extraction by type. Digests land at
`docs/audit/runs/$RUN_ID/digests/<type>/<slug>.json` (protocol §5).

**Step 0g — Validate digests:**

```bash
python3 .claude/skills/devspec_pr_audit/scripts/validate_digests.py \
  docs/audit/runs/$RUN_ID/digests/
```

Exit non-zero = P0 halt; no P2 agents dispatched (protocol §5).

**Step 0h — Write phase marker:**

```bash
touch docs/audit/runs/$RUN_ID/.phase_0.done
```

Update `manifest.json` `phases_completed`, `phase_trace[]`, and `updated_at` using the
**phase_trace append pattern** in §3 with: `<N>=0`, `phase_name="P0 deterministic"`,
`started_at=<P0 start timestamp captured before Step 0a>`, `loop_iterations=null`,
`outcome="OK"`.

---

## 5. P1 — Context (L1 loop, cap=4, halt)

**Participants:** `pr-audit-context-author` (compose), `pr-audit-context-verifier` (review).

**Convergence predicate:** `jq '.findings | length' iter_p1_<N>_review.json` returns 0.

### Iteration 1

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-context-author.md -->
Invoke `pr-audit-context-author` with:

```
You are pr-audit-context-author, invoked for run 20260520-143201-a3f9b2c, iteration 1.

Inputs:
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json
- docs/audit/runs/20260520-143201-a3f9b2c/digests/  (all digest subdirs)
- .claude/skills/devspec_pr_audit/slices.yaml
- .claude/skills/devspec_pr_audit/catalogs.md
- .claude/skills/devspec_pr_audit/protocol.md

Outputs:
- docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json  (skill-internal schema; no $id lock)

Procedure: follow the §Procedure section in this agent file.
Verdict format: N/A — compose agent, no verdict.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Write only to docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json
- After writing, confirm JSON parses: python3 -c "import json; json.load(open('docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json'))"
```

(Substitute `$RUN_ID` for the literal run-id in all invocations.)

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-context-verifier.md -->
Then invoke `pr-audit-context-verifier` with:

```
You are pr-audit-context-verifier, invoked for run 20260520-143201-a3f9b2c, reviewing iteration 1.

Inputs:
- docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json  (the bundle produced by iteration 1)
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json
- docs/audit/runs/20260520-143201-a3f9b2c/digests/  (all digest subdirs — used to verify digest path existence)
- .claude/skills/devspec_pr_audit/slices.yaml
- .claude/skills/devspec_pr_audit/protocol.md

Outputs:
- docs/audit/runs/20260520-143201-a3f9b2c/iter_p1_1_review.json  (conforms to vc:infra:findings)

Procedure: follow the §Procedure section in this agent file.
Verdict format: findings[] array is the verdict — empty = VERIFIED, non-empty = NEEDS_REVISION.
  See §Verdict format in this agent file.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Write only to docs/audit/runs/20260520-143201-a3f9b2c/iter_p1_1_review.json
- Do NOT modify context_bundle.json
- After writing output, run: python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/iter_p1_1_review.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

### L1 loop logic

After each verifier run:

```bash
FINDINGS_COUNT=$(jq '.findings | length' docs/audit/runs/$RUN_ID/iter_p1_${ITER_N}_review.json)
```

- `FINDINGS_COUNT == 0` → VERIFIED. Proceed to P2.
- `FINDINGS_COUNT > 0` and `ITER_N < 4` → increment `ITER_N`; re-invoke author with:
  - `iter_n = ITER_N`
  - `prev_iter_n = ITER_N - 1`
  - Author inputs now include `iter_p1_{prev_iter_n}_review.json`.
  - Then re-invoke verifier with `iter_n = ITER_N`.
- `FINDINGS_COUNT > 0` and `ITER_N == 4` → **HALT**:

```
P1 context loop reached cap (4 rounds) without converging.

Run: $RUN_ID
Last review file: docs/audit/runs/$RUN_ID/iter_p1_4_review.json

To resume after manual intervention:
  1. Review iter_p1_4_review.json for outstanding deltas.
  2. Edit context_bundle.json to resolve them.
  3. Re-run with: /devspec_pr_audit --from p1
```

Do not write `.phase_1.done` on halt. (protocol §2, §7)

### On convergence

Write `.phase_1.done`:

```bash
touch docs/audit/runs/$RUN_ID/.phase_1.done
```

Update `manifest.json` `phases_completed`, `phase_trace[]`, and `updated_at` using the
**phase_trace append pattern** in §3 with: `<N>=1`, `phase_name="P1 context"`,
`started_at=<P1 start timestamp captured before Iteration 1>`,
`loop_iterations=<converged ITER_N>`, `outcome="OK"`.

---

## 6. P2 — Discovery

### Tier-1 (mechanical, haiku)

Dispatch one `pr-audit-discovery-mechanical` agent per `semantic_work: false` slice
that has changed files. The two eligible slices are `generated_artifacts` and
`host_integration`. Skip Tier-1 entirely if neither has changed files.

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-discovery-mechanical.md -->
For each eligible slice, invoke:

```
You are pr-audit-discovery-mechanical, invoked for run 20260520-143201-a3f9b2c, slice batch "generated_artifacts".

IMPORTANT — SLICE GATE: Your FIRST action is to check whether "generated_artifacts" is one of
the two values in the allowlist: generated_artifacts, host_integration.
If it is NOT, immediately write the following document (substituting real values for
scope and generated_at) to docs/audit/runs/20260520-143201-a3f9b2c/p2/tier1_generated_artifacts_findings.json:

  {"round": 1, "scope": "tier1-generated_artifacts", "generated_at": <unix-epoch-int>, "findings": []}

Then run .claude/skills/devspec_pr_audit/scripts/self_validate.py on it and stop. Do not read the bundle. Do not load digests.
Do not analyze any files. This agent's mechanical checks only apply to generated_artifacts
and host_integration; all other slices are routed to Tier-2.

Inputs (only if slice gate passes):
- docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json  (tier1_slices list, changed files per slice)
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json
- docs/audit/runs/20260520-143201-a3f9b2c/digests/digest_schema/  (expansion-set schema digests)
- Raw changed files for the "generated_artifacts" slice (read via Read tool as needed)
- .claude/skills/devspec_pr_audit/slices.yaml

Outputs:
- docs/audit/runs/20260520-143201-a3f9b2c/p2/tier1_generated_artifacts_findings.json  (conforms to vc:infra:findings)

Procedure: follow the §Procedure section in this agent file.
Verdict format: N/A — discovery agent, no verdict; emits findings only.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Write only to docs/audit/runs/20260520-143201-a3f9b2c/p2/tier1_generated_artifacts_findings.json
- Apply only deterministic checks; no semantic judgment
- After writing output, run: python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/p2/tier1_generated_artifacts_findings.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

If both Tier-1 slices have changed files, the two agents can be dispatched in parallel.

### Tier-2 (semantic, sonnet)

Read `context_bundle.json` `.tier2_bins[]`. Each bin is an array of
`{file, slice, impact, digests_needed[]}` objects, already bin-packed by the
context-author using the impact formula from protocol §3 (~200 units per bin).

Dispatch bins in waves of up to 6 agents in parallel. Wait for all agents in a wave
to complete before dispatching the next wave.

**Example:** 14 bins → wave 1 dispatches bins 1-6, wave 2 dispatches bins 7-12, wave 3
dispatches bins 13-14.

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-discovery-semantic.md -->
For each bin, invoke (substituting `$RUN_ID`, `$BIN_ID`, and inlining `$BIN_FILES_JSON`):

```
You are pr-audit-discovery-semantic, invoked for run 20260520-143201-a3f9b2c, bin 3.

Inputs:
- bin_id: 3
- bin_files: [{"file":"schema/core/canon.schema.json","slice":"schemas","impact":480,"digests_needed":["digests/digest_schema/canon.schema.json"]}]  (sourced from context_bundle.json tier2_bins[2])
- docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json
- docs/audit/runs/20260520-143201-a3f9b2c/digests/<type>/<slug>.json  (paths listed in each file's digests_needed[])
- Raw source files for each file in bin_files (escape hatch — prefer digests)
- .claude/skills/devspec_pr_audit/catalogs.md
- .claude/skills/devspec_pr_audit/slices.yaml

Outputs:
- docs/audit/runs/20260520-143201-a3f9b2c/p2/tier2_3_findings.json  (conforms to vc:infra:findings)

Procedure: follow the §Procedure section in this agent file.
Verdict format: N/A — discovery agent, no verdict; emits findings only.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Write only to docs/audit/runs/20260520-143201-a3f9b2c/p2/tier2_3_findings.json
- catalog_tag is required on every finding — omission is a protocol violation
- After writing output, run: python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/p2/tier2_3_findings.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

### P2 completion

```bash
touch docs/audit/runs/$RUN_ID/.phase_2.done
```

Update `manifest.json` `phases_completed`, `phase_trace[]`, and `updated_at` using the
**phase_trace append pattern** in §3 with: `<N>=2`, `phase_name="P2 discovery"`,
`started_at=<P2 start timestamp captured before Tier-1 dispatch>`,
`loop_iterations=null`, `outcome="OK"`.

---

## 7. P3 — Cross-boundary (single pass)

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-cross-boundary.md -->
Invoke `pr-audit-cross-boundary` in `cross_boundary` mode:

```
You are pr-audit-cross-boundary, invoked for run 20260520-143201-a3f9b2c, mode "cross_boundary".

Inputs (both modes):
- mode: cross_boundary
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json

Mode A (cross_boundary) additional inputs:
- docs/audit/runs/20260520-143201-a3f9b2c/context_bundle.json
- docs/audit/runs/20260520-143201-a3f9b2c/digests/  (all digest files for all in-scope slices)
- .claude/skills/devspec_pr_audit/catalogs.md
- .claude/skills/devspec_pr_audit/slices.yaml

Outputs:
- Mode A: docs/audit/runs/20260520-143201-a3f9b2c/p3/cross_boundary_findings.json  (conforms to vc:infra:findings)

Procedure: follow the §Procedure — Mode A section in this agent file.
Verdict format: N/A for both modes — no loop participation; single-pass only.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Mode A: write only to docs/audit/runs/20260520-143201-a3f9b2c/p3/cross_boundary_findings.json
- After writing output, run: python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/p3/cross_boundary_findings.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

Cross-boundary applies drift types D1, D2, D3, D6, D7, D8, D9, D12, D14 only
(protocol §1 — D11 is intra-slice-only; D13 stays within its owning slices).

```bash
touch docs/audit/runs/$RUN_ID/.phase_3.done
```

Update `manifest.json` `phases_completed`, `phase_trace[]`, and `updated_at` using the
**phase_trace append pattern** in §3 with: `<N>=3`, `phase_name="P3 cross-boundary"`,
`started_at=<P3 start timestamp captured before cross-boundary invocation>`,
`loop_iterations=null`, `outcome="OK"`.

---

## 8. P4 — Consolidation (L2 loop, cap=4, degrade)

**Participants:** `pr-audit-consolidator` in compose-mode, then verify-mode.

**Convergence predicate:** `jq '.findings | length' iter_p4_<N>_review.json` returns 0.

### Iteration 1 — compose

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-consolidator.md -->
Invoke `pr-audit-consolidator` with mode=compose, iter_n=1:

```
You are pr-audit-consolidator, invoked for run 20260520-143201-a3f9b2c, mode "compose", iteration 1.

Inputs (compose mode):
- docs/audit/runs/20260520-143201-a3f9b2c/p0/tier0_findings.json  (Tier-0 fragments; skip if absent)
- docs/audit/runs/20260520-143201-a3f9b2c/p2/tier1_*_findings.json  (Tier-1 fragments; skip if absent)
- docs/audit/runs/20260520-143201-a3f9b2c/p2/tier2_*_findings.json  (Tier-2 fragments; skip if absent)
- docs/audit/runs/20260520-143201-a3f9b2c/p3/cross_boundary_findings.json  (skip if absent)
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json

Outputs (compose mode):
- docs/audit/runs/20260520-143201-a3f9b2c/findings.json  (conforms to vc:infra:findings; always written)
- docs/audit/runs/20260520-143201-a3f9b2c/fix_plan.json  (conforms to vc:infra:pr-audit-fix-plan; only when findings non-empty)
- docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_fix.json  (conforms to vc:infra:pr-audit-fix-plan; only when findings non-empty)

Procedure: follow the §Procedure — Mode A (compose) section in this agent file.
Verdict format: N/A — compose mode; emits findings.json + fix_plan.json + iter_p4_1_fix.json only.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Do NOT write to finding fragment files (p0/, p2/ or p3/)
- After writing, self-validate all three outputs:
    python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/findings.json
    python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/pr_audit_fix_plan.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/fix_plan.json
    python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/pr_audit_fix_plan.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_fix.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

Note: `p0/tier0_findings.json` is included in compose inputs so the consolidator merges T0 findings into Part A.

### Iteration 1 — verify

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-consolidator.md -->
Invoke `pr-audit-consolidator` with mode=verify, iter_n=1:

```
You are pr-audit-consolidator, invoked for run 20260520-143201-a3f9b2c, mode "verify", iteration 1.

Inputs (verify mode):
- docs/audit/runs/20260520-143201-a3f9b2c/findings.json
- docs/audit/runs/20260520-143201-a3f9b2c/fix_plan.json  (absent on no-defects path — treat as consistent with empty findings)
- docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_fix.json
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json
- schema/infra/findings.schema.json  (vc:infra:findings)
- schema/infra/pr_audit_fix_plan.schema.json  (vc:infra:pr-audit-fix-plan)

Outputs (verify mode):
- docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_review.json  (conforms to vc:infra:findings)

Procedure: follow the §Procedure — Mode B (verify) section in this agent file.
Verdict format (verify mode only): findings[] array is the verdict — empty = VERIFIED,
  non-empty = NEEDS_REVISION. See §Verdict format (Mode B) in this agent file.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Do NOT modify findings.json or fix_plan.json
- Verify mode: write only to docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_review.json
- After writing output, run: python3 .claude/skills/devspec_pr_audit/scripts/self_validate.py --schema schema/infra/findings.schema.json --input docs/audit/runs/20260520-143201-a3f9b2c/iter_p4_1_review.json
- If exit code != 0, fix and re-write. Do NOT declare success until self-validate exits 0.
```

### L2 loop logic

After each verify invocation:

```bash
FINDINGS_COUNT=$(jq '.findings | length' docs/audit/runs/$RUN_ID/iter_p4_${ITER_N}_review.json)
```

- `FINDINGS_COUNT == 0` → VERIFIED. Proceed to P5.
- `FINDINGS_COUNT > 0` and `ITER_N < 4` → increment `ITER_N`; re-invoke compose with:
  - `mode=compose`, `iter_n=ITER_N`, `prev_iter_n=ITER_N-1`
  - Compose inputs now include `iter_p4_{prev_iter_n}_review.json`.
  - Then re-invoke verify with `mode=verify`, `iter_n=ITER_N`.
  - Verify reads `iter_p4_{iter_n}_fix.json` (same-iteration fix, not prev).
- `FINDINGS_COUNT > 0` and `ITER_N == 4` → **DEGRADE**:

```bash
# Consolidator (Mode B) already wrote status="PARTIAL" and meta_findings[] to
# manifest.json on cap; orchestrator reads to confirm, then writes .phase_4.done.
STATUS=$(jq -r '.status // "OK"' docs/audit/runs/$RUN_ID/manifest.json)
# STATUS should be "PARTIAL" at this point (written by consolidator Mode B step 4).
echo '{"degraded":true}' > docs/audit/runs/$RUN_ID/.phase_4.done
```

Continue to P5 (degrade does not halt — protocol §2).

### P4 completion

On **normal** convergence (VERIFIED before cap):

```bash
echo '{"degraded":false}' > docs/audit/runs/$RUN_ID/.phase_4.done
```

On **degrade** path (L2 cap hit), `.phase_4.done` is already written by the degrade
block above (`echo '{"degraded":true}' > ...`). No second write needed here.

Update `manifest.json` `phases_completed`, `phase_trace[]`, and `updated_at` using the
**phase_trace append pattern** in §3 with: `<N>=4`, `phase_name="P4 consolidation"`,
`started_at=<P4 start timestamp captured before Iteration 1 compose>`,
`loop_iterations=<converged or capped ITER_N>`,
`outcome="OK"` on normal convergence, `"DEGRADED"` on L2 cap.

---

## 9. P5 — Audit-of-Audit and Finalization

### Audit-of-audit (meta-review)

Invoke `pr-audit-cross-boundary` in `meta_review` mode. This is a single pass;
no loop (protocol §9). The agent writes directly to `manifest.json` `meta_findings[]` —
the orchestrator does not need to read and forward anything.

<!-- Constraints: keep in sync with §Invocation template in .claude/agents/pr-audit-cross-boundary.md -->
```
You are pr-audit-cross-boundary, invoked for run 20260520-143201-a3f9b2c, mode "meta_review".

Inputs (both modes):
- mode: meta_review
- docs/audit/runs/20260520-143201-a3f9b2c/manifest.json

Mode B (meta_review) additional inputs:
- docs/audit/runs/20260520-143201-a3f9b2c/findings.json
- docs/audit/runs/20260520-143201-a3f9b2c/fix_plan.json  (skip if absent — no-findings path)
- docs/audit/runs/20260520-143201-a3f9b2c/p2/  (all tier1_* and tier2_* fragment files; used to verify schema conformance and vacuous-acceptance patterns in per-phase fragments before consolidation; skip if absent)
- docs/audit/runs/20260520-143201-a3f9b2c/p3/cross_boundary_findings.json  (skip if absent)

Outputs:
- Mode B: docs/audit/runs/20260520-143201-a3f9b2c/manifest.json  (appends to meta_findings[] only)

Procedure: follow the §Procedure — Mode B section in this agent file.
Verdict format: N/A for both modes — no loop participation; single-pass only.

Constraints:
- Use only tools listed in this agent's frontmatter (Read, Glob, Grep, Bash, Write)
- Do NOT call Edit
- Do NOT invoke other agents
- Mode B: write only to docs/audit/runs/20260520-143201-a3f9b2c/manifest.json (meta_findings[] extension);
  do NOT write to findings.json (schema-locked per protocol §9)
- After writing, confirm JSON parses: python3 -c "import json; json.load(open('docs/audit/runs/20260520-143201-a3f9b2c/manifest.json'))"
```

### SUMMARY.md format

`SUMMARY.md` is generated **last**, after the phase marker and manifest update (see
"P5 completion" sequence below). The format below documents what `p5_finalize.py`
produces (per protocol §11):

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

Omit the "## Fix plan" section if `fix_plan.json` does not exist (no findings path).

If `STATUS == "PARTIAL"`, open with `STATUS: PARTIAL — see manifest.json meta_findings[]
for unresolved items` (protocol §11).

### P5 completion

The P5 completion sequence is **strictly ordered** — the SUMMARY.md render must read a
manifest that already reflects phase 5 completion, otherwise the first render shows
`Status: UNKNOWN` and `phases_completed: [0..4]` and requires manual regeneration.

1. **Run the audit-of-audit (meta-review)** — already executed above (single pass; appends
   `meta_findings[]` to `manifest.json`).
2. **Write the `.phase_5.done` marker:**

   ```bash
   touch docs/audit/runs/$RUN_ID/.phase_5.done
   ```

3. **Update `manifest.json`** — append the P5 entry to `phase_trace[]`, update
   `phases_completed`, and set `status` (defaulting to `"OK"` if unset; preserved if the
   consolidator wrote `"PARTIAL"` in P4). Use the **phase_trace append pattern** in §3
   with: `<N>=5`, `phase_name="P5 finalize"`,
   `started_at=<P5 start timestamp captured before the meta-review invocation>`,
   `loop_iterations=null`, `outcome="OK"`. Compose the jq filter so it also sets
   `.status = (.status // "OK")` in the same update.

4. **Generate `SUMMARY.md`** — invoke the dedicated finalize script, which reads
   manifest.json (now with `phase_trace[]` and the final `status`) and findings.json to
   compute counts, then renders per the SUMMARY.md format documented above:

   ```bash
   python3 .claude/skills/devspec_pr_audit/scripts/p5_finalize.py \
     --run-dir docs/audit/runs/$RUN_ID
   ```

5. **Print the completion footer to stdout:**

   ```
   PR audit complete.
   Run: $RUN_ID
   Summary: docs/audit/runs/$RUN_ID/SUMMARY.md
   Findings: docs/audit/runs/$RUN_ID/findings.json
   Fix plan: docs/audit/runs/$RUN_ID/fix_plan.json  (or "Fix plan: none (no findings)")
   ```

---

## 10. Resumption (`--from <phase>`)

**Locate run-id:** If `--from` is given without an explicit run-id, find the most recently
modified run directory:

```bash
RUN_ID=$(ls -t docs/audit/runs/ | head -1)
```

**Delete forward markers:** `--from pN` deletes `.phase_N.done` through `.phase_5.done`
for the located run-id before resuming, so that those phases re-execute cleanly:

```bash
for I in $(seq $PHASE_NUM 5); do
  rm -f docs/audit/runs/$RUN_ID/.phase_${I}.done
done
```

**Skip completed phases:** Any phase N where `.phase_N.done` exists (after the deletion
above) is skipped. Resume execution from the first phase without a marker.

**Phase immutability:** Artifacts written by completed phases are not overwritten by
subsequent phases (protocol §6). Only the forced replay from `--from` re-executes them.

---

## 11. Failure modes

| Failure | Behavior |
|---------|----------|
| T0-01 `branch-not-detached` | Abort before creating run dir; print error; exit non-zero |
| T0-02 zero commits ahead | Abort before creating run dir; print "no changes to audit"; exit 0 |
| T0-04/05/06/10 (P0) failure | Abort after writing finding to `p0/tier0_findings.json`; exit non-zero (unless overridden) |
| T0-07/09/11 (P1) failure | Record in `p0/tier0_findings.json`; continue |
| Digest validation failure | Abort; print digest path + validation error; exit non-zero |
| Agent crash or timeout (P1-P4) | Retry once with identical input; second failure → PARTIAL + reason in `manifest.json` `meta_findings[]` |
| L1 cap hit (P1) | HALT; print intervention guide; no `.phase_1.done` written |
| L2 cap hit (P4) | DEGRADE; write `status: "PARTIAL"` and unresolved deltas to `manifest.json`; write `.phase_4.done` with `degraded=true` content |
| P0 or P5 Bash subprocess error | Print error; do not write partial artifacts; exit non-zero |

---

## 12. Tool-use rules for the orchestrator

The orchestrator (this skill) may use: **Bash, Read, Write, Agent**.

- **Agent:** used to dispatch subagents; the orchestrator IS the dispatcher and may call Agent.
  Subagents themselves must NOT call Agent (protocol §3).
- **Edit:** forbidden for the orchestrator. Use Bash + jq for all manifest.json updates.
- **Write:** not used by the orchestrator. SUMMARY.md is generated by `p5_finalize.py` (P5). All other structured file creation is delegated to agents;
  manifest.json is created and updated via Bash (heredoc + jq pattern).

---

## 13. References

| Resource | Location |
|----------|----------|
| Protocol (authoritative) | `.claude/skills/devspec_pr_audit/protocol.md` |
| Catalog (D1–D14, I1–I13) | `.claude/skills/devspec_pr_audit/catalogs.md` |
| Slice routing | `.claude/skills/devspec_pr_audit/slices.yaml` |
| Digest schemas | `.claude/skills/devspec_pr_audit/schemas/digest_<type>.schema.json` |
| Extractor scripts | `.claude/skills/devspec_pr_audit/scripts/extract_digest_<type>.sh` |
| Digest validator | `.claude/skills/devspec_pr_audit/scripts/validate_digests.py` |
| Findings schema | `schema/infra/findings.schema.json` (`vc:infra:findings`) |
| Fix-plan schema | `schema/infra/pr_audit_fix_plan.schema.json` (`vc:infra:pr-audit-fix-plan`) |
| context-author agent | `.claude/agents/pr-audit-context-author.md` |
| context-verifier agent | `.claude/agents/pr-audit-context-verifier.md` |
| discovery-mechanical agent | `.claude/agents/pr-audit-discovery-mechanical.md` |
| discovery-semantic agent | `.claude/agents/pr-audit-discovery-semantic.md` |
| cross-boundary agent | `.claude/agents/pr-audit-cross-boundary.md` |
| consolidator agent | `.claude/agents/pr-audit-consolidator.md` |
