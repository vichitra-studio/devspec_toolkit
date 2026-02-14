# Trinity Observability Tooling

This page documents the runtime observability helpers for Trinity session logs.

## Commands

### Run runtime orchestration
Execute the full Trinity `16a -> 16b -> 16c` lifecycle for a single roadmap milestone:

```bash
./tools/run_specdev.sh trinity --step-id <milestone_id> --repo-root ./devspec_toolkit
```

Use JSON output for machine-readable automation:

```bash
./tools/run_specdev.sh trinity --step-id <milestone_id> --repo-root ./devspec_toolkit --json
```

Resume from the latest persisted runtime session state:

```bash
./tools/run_specdev.sh trinity --resume --repo-root ./devspec_toolkit --json
```

Disambiguate resume target when multiple session states exist:

```bash
./tools/run_specdev.sh trinity --resume --resume-run-id <run_id> --repo-root ./devspec_toolkit --json
```

### Export eval rows
Convert session-event JSONL into normalized eval rows:

```bash
./tools/run_specdev.sh trinity-export-eval .trinity/sessions/<session>.jsonl --repo-root ./devspec_toolkit --out .trinity/eval/<session>_rows.jsonl
```

### Replay verification
Reconstruct timeline and verify artifact/hash lineage:

```bash
./tools/run_specdev.sh trinity-replay .trinity/sessions/<session>.jsonl --repo-root ./devspec_toolkit --out .trinity/eval/<session>_replay.json
```

Use strict mode to fail on warnings:

```bash
./tools/run_specdev.sh trinity-replay .trinity/sessions/<session>.jsonl --repo-root ./devspec_toolkit --strict
```

### Dashboard summary
Aggregate exported rows and replay reports:

```bash
./tools/run_specdev.sh trinity-dashboard --rows-glob ".trinity/eval/*_rows.jsonl" --replay-glob ".trinity/eval/*_replay.json" --out-json .trinity/eval/dashboard.json --out-md .trinity/eval/dashboard.md
```

### Remediation plan
Generate remediation actions from replay findings:

```bash
./tools/run_specdev.sh trinity-remediate .trinity/eval/<session>_replay.json --repo-root ./devspec_toolkit --out .trinity/eval/<session>_remediation.json
```

`trinity-remediate` defaults to `--missing-resume-source-policy hard`, so missing source artifacts fail fast by default. Use `--missing-resume-source-policy soft` only for local triage workflows.

Optional resume artifact generation:

```bash
./tools/run_specdev.sh trinity-remediate .trinity/eval/<session>_replay.json \
  --repo-root ./devspec_toolkit \
  --session-log .trinity/sessions/<session>.jsonl \
  --emit-session-state .trinity/runtime/session_state_resume.json \
  --emit-task-input .trinity/runtime/task_input_resume.json \
  --missing-resume-source-policy hard \
  --out .trinity/eval/<session>_remediation.json
```

### Eval dashboard export
Bundle eval rows/replay summaries/dashboard and optionally publish to an external HTTP endpoint:

```bash
./tools/run_specdev.sh trinity-publish-eval \
  --rows-glob ".trinity/eval/*_rows.jsonl" \
  --replay-glob ".trinity/eval/*_replay.json" \
  --dashboard-json ".trinity/eval/dashboard.json" \
  --out ".trinity/eval/export_bundle.json" \
  --endpoint-env TRINITY_EVAL_EXPORT_ENDPOINT \
  --auth-token-env TRINITY_EVAL_EXPORT_TOKEN
```

## CI Hook

`.github/workflows/ci.yml` includes a `trinity-observability` job that:
1. Discovers `.trinity/sessions/*.jsonl`.
2. Runs export + replay + remediation per session log.
3. Builds dashboard summary files under `.trinity/eval/`.
4. Bundles eval dashboard export payloads (`.trinity/eval/export_bundle.json`) and optionally pushes them to `TRINITY_EVAL_EXPORT_ENDPOINT`.
5. Uploads `trinity-observability` artifacts and writes dashboard markdown to the GitHub Actions job summary.

### Real CI verification run
Use manual dispatch to run a strict verification pass against real logs:
1. Open Actions → `SpecDev CI` → `Run workflow`.
2. Set `require_trinity_logs=true` (job fails if no `.trinity/sessions/*.jsonl` exist).
3. Optional: set `trinity_logs_glob` when logs are in non-standard paths.
4. Optional: set `require_eval_publish=true` to fail if external export is not configured or publish fails.

To enable external dashboard publishing, configure repository secrets:
- `TRINITY_EVAL_EXPORT_ENDPOINT`
- `TRINITY_EVAL_EXPORT_TOKEN`

## Capture Policy Tuning (60k–80k Window)
`schema/trinity/log_capture_policy.schema.json` supports token-budget controls:
- `context_window_token_target`: intended context window (for example `80000`).
- `max_full_capture_context_fraction`: max fraction of the window for full-capture events (for example `0.2`).
- `full_capture_token_budget_per_run`: explicit hard budget for total full-capture tokens per run.
- `max_full_prompt_tokens_per_event`: per-event prompt token cap before fallback.
- `max_full_completion_tokens_per_event`: per-event completion token cap before fallback.
- `operating_profile`: profile/tier/budget-tier contract (`eval_default|eval_extended|cost_guarded`).
- `budgets`: normalized budget block used by runtime completeness/fallback checks.
- `retention`: retention windows for `session_log_days`, `capture_artifact_days`, and `eval_export_days`.

Runtime validation applies these controls and expects fallback capture levels (`oversize_fallback`) when budgets are exceeded.
Session events also capture policy-fallback telemetry in metadata:
- `capture_policy_profile`
- `capture_policy_fallback_applied`
- `capture_policy_fallback_reasons`

## Child Timeout Tuning (Local LLMs)
Trinity child processes now support YAML-configured timeouts:
- `runtime.child_timeout_seconds`: default timeout applied to all phases.
- `runtime.child_timeout_by_phase`: optional overrides for `16a`, `16b`, `16c`, `utility`.

Example:

```yaml
runtime:
  child_timeout_seconds: 21600
  child_timeout_by_phase:
    16a: 7200
    16b: 21600
    16c: 10800
    utility: 3600
```

Use larger values for local/self-hosted LLM endpoints to prevent false timeout blocks during long completions.
Set a timeout to `0` to disable timeout enforcement for that scope.

## Utility Schema Validation
Utility orchestration now validates structured utility payloads with:
- `schema/trinity/utility_call.schema.json`
- `schema/trinity/utility_result.schema.json`

Runtime emits explicit `VALIDATION` events for utility payload schema pass/fail before utility output is ingested by parent phases.

## Anchor Union Telemetry
Anchor regeneration emits `VALIDATION` events with `metadata.anchor_union_metrics` so replay/eval pipelines can track:
- active context count
- merged checklist size
- checklist conflict count and conflict IDs
- scope/docs/test-command union counts

## Bootstrap Ref Explainability
Planner bootstrap context packs may include `bootstrap_ref_trace` entries that document:
- which roadmap field produced each bootstrap candidate (`selected_from`)
- whether it came from `structured`, `tokenized`, or `authority_fallback` selection
- the grounded spec path and line range used for the final reference
