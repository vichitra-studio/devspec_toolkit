---
name: specdev-trinity-plan
description: >
  DEPRECATED — transitional alias for /specdev-trinity --phase plan. Scheduled for removal in K3.
  Prints deprecation notice then executes the canonical /specdev-trinity --phase plan protocol.
  Trigger on: "/specdev-trinity-plan", "trinity plan" (legacy phrasing).
---

# /specdev-trinity-plan — DEPRECATED Transitional Delegation Skill

Print: `DEPRECATED: /specdev-trinity-plan is renamed to /specdev-trinity. Use: /specdev-trinity <batch_id> --phase plan. Proceeding with the forwarded invocation.`

Then execute the full `/specdev-trinity --phase plan` protocol with the supplied `batch_id`.

The complete plan-phase protocol is inlined below so the model executes correct behavior
after the notice (K §11.3 — Claude Code skills have no built-in forward primitive; delegation
is achieved by containing the complete protocol). Scheduled for K3 removal.

---

## Forwarded Protocol — /specdev-trinity --phase plan

Runs the review-fix loop against a milestone batch plan artifact, then gates on human
approval before the main thread proceeds. Plan-phase (16a) only.

**Source spec:** K_agentification.md §5.2, §5.5, §9.

### Step 1 — Locate the plan artifact

Verify that `spec/impl_context/ms_<batch_id>_plan.json` exists:
```bash
specdev json structure spec/impl_context/ms_<batch_id>_plan.json
```

If the file does not exist, return an error and stop.

### Step 2 — Review-fix loop

Run the review-fix loop on the plan artifact:

1. Dispatch `specdev-scope` with:
   ```json
   {
     "scope": "ms-<batch_id>-plan",
     "change_set": "recent_commits"
   }
   ```

2. For each round up to max_rounds=5:

   **2a. Dispatch all planned `specdev-reviewer` instances in parallel** (single message,
   multiple Agent tool calls). Pass the plan artifact path and scope:
   ```json
   {
     "steps": ["ms-<batch_id>-plan"],
     "scope_kind": "plan_artifact",
     "reviewer_id": "r1",
     "round": <current_round>,
     "scope": "ms-<batch_id>-plan",
     "flags": { "with_replay": false, "with_backlog": false },
     "artifact_path": "spec/impl_context/ms_<batch_id>_plan.json"
   }
   ```

   Each reviewer writes to:
   `.specdev/findings/findings_ms-<batch_id>-plan_<round>_r<reviewer_id>.json`

   (Ensure directory exists once: `mkdir -p .specdev/findings`.)

   **2b. Merge with the jq one-liner** (K_agentification.md §5.4, paths per §11.7):
   ```bash
   jq -s '{round: .[0].round, scope: .[0].scope, generated_at: (now | floor), findings: (map(.findings) | add | unique_by({kind, location, signature}))}' \
     .specdev/findings/findings_ms-<batch_id>-plan_<round>_r*.json > .specdev/findings/findings_ms-<batch_id>-plan_<round>.json
   ```

   **2c. Check convergence:**
   If `findings[]` is empty: CONVERGED. Proceed to Step 3.

   **2d. Dispatch fix:**
   Dispatch `specdev-impl` with `mode: "fix"` and the merged findings path.
   Wait for the structured summary.

   Increment round and continue.

3. If round 5 completes with findings remaining: HALT.

   Write the HALT artifact:
   `.specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json`

   This is a timestamped copy of the round-5 merged findings file. It is the audit trail.
   Do not promote it to a canonical name. The timestamped file IS the record.

   Print:
   ```
   HALT: max_rounds=5 reached with unresolved findings.
   Findings path: .specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json
   Finding count: <N> (<P0_count> P0, <P1_count> P1, <P2_count> P2)
   Human action required: proceed-with-gaps | replay | hand-edit then re-invoke /specdev-trinity <batch_id> --phase plan
   ```

   Do not silently accept partial convergence. HALT is a first-class verdict.

   Set verdict = "HALT (N unresolved findings)". Proceed to Step 3 regardless (HALT is a valid
   verdict to gate on).

### Step 3 — Human gate (K_agentification.md §5.5)

After the loop returns a verdict (CONVERGED or HALT), present an `AskUserQuestion` with
three options:

```
Plan phase review complete.
Verdict: <CONVERGED at round N | HALT at round 5 with N findings remaining>
[On HALT: Findings path: .specdev/findings/findings_ms-<batch_id>-plan_5_<unix_timestamp>.json]

How would you like to proceed?
A) Proceed — accept the plan and continue to downstream phases.
B) Replay — re-run the review-fix loop from round 1 (fresh state, no prior findings).
C) Abort — stop here; plan requires substantial rework before proceeding.
```

**On Proceed:** Return the verdict. Downstream 16b/16c are handled by
`/specdev-trinity --phase impl` and `/specdev-trinity --phase review`.

**On Replay:** Re-run the loop from Step 2 (round 1, fresh state). Prior findings files
are NOT consulted — the reviewer sees the artifact's current state (K_agentification.md §5.6).

**On Abort:** Return. The user will rework the plan artifact manually before re-invoking.

---

## Flag discipline

Three-flag protocol for all validation/governance commands:
```
--repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`specdev json` read/shape/edit subcommands: pass `--repo-root` only.
Exception: `specdev json resolve-pointers` accepts `--git-root`.
`canon-accept`: pass `--git-root`, NOT `--spec-root`.

Never read `spec/*.json` directly. Use `specdev json read` with a filter.
