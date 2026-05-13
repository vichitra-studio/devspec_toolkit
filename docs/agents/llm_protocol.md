# LLM Protocol — Local-LLM Offload for Spec Workflow

**Status:** design • **Audience:** Claude Code (consumer) + local-agent implementer • **Tracked in:** Plane module *Local LLM Offload for Spec Workflow*

This document is the single source of truth for the agentic local-LLM layer that sits behind `specdev llm *`. Its purpose is to move JSON-shaped planning, drafting, and lint-remediation work off Claude's token budget while keeping the toolkit's deterministic guarantees intact.

If a contract here ever conflicts with code, code wins and this doc is updated. If a contract here ever conflicts with a Plane story description, this doc wins.

---

## 1. The boundary

```
Claude Code  →  specdev CLI  →  local LLM (OpenAI-compatible endpoint)
                              ↑ all rich machinery lives here ↑
                              ↓ outcomes only ↓
Claude Code  ←  specdev CLI
```

Three rules govern this boundary; everything else is implementation detail:

1. **The local LLM emits pointers, never JSON content.** Content always comes from the CLI's deterministic readers (`json read`, `context extract`). This makes hallucination unrecoverable-by-construction → recoverable-by-validation.
2. **Claude sees outcomes only.** Validated bundles, green checks, or honest compact failures. The intermediate envelopes, dry-runs, and multi-iteration prompting never reach Claude's context.
3. **The CLI remains the deterministic ground truth.** Schema validation, canonical-id resolution, traceability, governance — none of these get routed through an LLM. The LLM is at the I/O edges; the CLI is the middle.

---

## 2. Audience split

### 2.1 Claude-facing surface (small)

Three commands. That's it.

| Command | Purpose |
|---|---|
| `specdev llm bundle --step NN [--task <NL>] [--out <path>]` | Materialize the scoped context bundle Claude needs to work on step `NN`. Stdout when `--out` omitted. |
| `specdev llm edit "<NL change>" [--out <path>]` | Apply a schema-aware spec edit described in natural language (NL is positional, not a flag). |
| `specdev llm remediate [<spec-check.json>` \| `-] [--out <path>]` | Drive `spec-check` to green by applying structured remediation candidates. Reads from stdin when `-` or omitted. |

All three return a small outcome report (typically < 5 KB) — see §6 for exact schemas. Claude does not call lint commands directly, does not parse error envelopes, does not orchestrate loops.

### 2.2 Local-agent-facing surface (large)

The local agent uses everything below. Claude does not.

- `--json` on every lint emitting structured findings with `remediation{}` candidates
- `specdev guide <code>` — the canonical playbook for an error code
- `specdev json resolve-pointers` — the pointer verification primitive
- `--dry-run` and `--against-schema-field` on `json patch/insert/delete`
- `context snapshot` / `context diff` for outer-loop rollback safety
- The full orientation bundle assembled by `specdev llm bundle`

---

## 3. Orientation bundle

The set of artifacts fed to the local LLM as system context for any step-scoped task. Assembled deterministically by `specdev llm bundle --step NN`. Same inputs always produce the same bundle.

### 3.1 Always-included

| Artifact | Why included |
|---|---|
| `devspec_toolkit/.claude/skills/specdev-context/SKILL.md` | Skill protocol (what to load, prohibited reads) |
| `devspec_toolkit/docs/prompts/shared_expectations.md` | Agent operating rules (Two-Phase Clarify → Emit, ledger discipline) |
| `devspec_toolkit/prompts/prompt_NN_*.md` | The step's deterministic prompt contract |
| `devspec_toolkit/CLAUDE.md` | Toolkit CLAUDE.md — submodule flag rules + core CLI patterns (generic) |
| `<host>/CLAUDE.md` *(if present)* | Host-repo CLAUDE.md — project-specific conventions and protocol overrides |
| `devspec_toolkit/docs/agents/llm_protocol.md` *(this file)* | The contract the agent must honor |
| `devspec_toolkit/tools/step_order.json` | Forward-only DAG |
| `devspec_toolkit/tools/trace_matrix.json` *(top-level)* | Step-level dependency map |
| `devspec_toolkit/tools/step_docs.json` | Per-step metadata |
| `devspec_toolkit/canon/manifest.json` | Core-tier canon registry |
| `spec/canon/manifest.json` *(if present)* | Project-tier canon registry |
| `specdev context structure <spec_dir> --step NN` output | Upstream dependency map: which prior-step files + keys feed this step (existing command) |
| Project-step structure summary (entry-id list per spec file for the current step) | Derived at bundle time by reading each spec file with the **deterministic jq paths registered in story 04a's entry-key registry**. No semantic interpretation — the registry tells the assembler exactly which array to enumerate and which field on each entry is the id; the spec file content is read but never id-shape-inferred. The registry data file is **project-side** at `<spec_root>/entry_key_registry.json` — it is not shipped inside the toolkit submodule. The bundle assembler resolves it via `--spec-root` (the host repo's spec directory). |

Total size: typically < 30 KB. Cacheable across invocations within a session.

### 3.2 Never-included by default

- Raw `spec/*.json` files (200 KB+ each) — fetched on demand via pointers
- `spec/impl_context/ms_*.json` — milestone-specific, balloons context
- Individual canon kind files — fetched on demand
- Tool output dumps in `.specdev/`, `*.txt` blobs

### 3.3 Bundle output shape

`specdev llm bundle --step NN [--task "..."] [--out <path>]` emits one shape: the always-included orientation artifacts (§3.1) plus a structural summary — counts and ids per upstream source, never raw entry content. Total size: typically < 10 KB regardless of pipeline step.

```json
{
  "step": "04",
  "task": "<NL task, or null>",
  "bundle_version": "1",
  "context": {
    "skill_md": "...",
    "shared_expectations": "...",
    "prompt_NN": "...",
    "claude_md_toolkit": "...",
    "claude_md_host": "...",
    "llm_protocol": "...",
    "step_order": { ... },
    "trace_matrix": { ... },
    "step_docs": { ... },
    "canon_manifest_core": { ... },
    "canon_manifest_project": { ... }
  },
  "upstream_structure": {
    "spec/03_glossary.json": { "entry_count": 47, "top_level_keys": ["terms"] }
  },
  "step_structure_summary": {
    "spec/04_fr_list.json": { "entry_count": 23, "ids": ["fr-user-login", "fr-newsletter-subscribe", "..."] }
  },
  "scoped_entries": [
    { "file": "spec/04_fr_list.json", "id": "fr-user-login", "jq_path": ".functional_requirements[3]" }
  ],
  "unresolved": []
}
```

- `scoped_entries` (pointers only — **no content**) is populated when `--task` is provided. Without `--task`, the bundle is orientation-only.
- For entry content, the agent uses the **drill-down recipe**: `specdev json read` for counts and id lists (with jq slicing for pagination), then `specdev json resolve-pointers` for selected full entries. The skill (§16, story 17) is the canonical source of this recipe.
- The bundler does not page, chunk, or auto-write to disk. If a step's structural summary is genuinely too large to return inline, fix it upstream (the step has too many entries; split it) — do not paper over with bundler complexity.

`--out <path>` writes the bundle to disk explicitly (user controls the path). When `--out` is omitted, the bundle JSON is written to **stdout** and any diagnostic logs go to **stderr**, so callers can pipe directly. `--out` is the only output flag. Per §17 flag minimalism, there is no `--mode`, no `--inline`, no `--from`, no `--page`. Drill-down composes from existing primitives.

### 3.4 Valid JSON under all conditions

The bundle is **valid JSON under all conditions**, including failure. There is no half-written truncation. If the bundle cannot be assembled (missing step, endpoint unreachable, schema not found), the output is a top-level error object:

```json
{ "ok": false, "error": "...", "bundle_version": "1" }
```

Never a partial write, never a bare traceback.

### 3.5 Path resolution

All file paths in bundle output and pointer schemas are **relative to `--git-root`** (the host repo root). When the toolkit runs inside its own repo (no host), `--git-root` defaults to the toolkit root.

Paths in §3.1's always-included artifacts table are written from a toolkit-relative perspective for readability, but at runtime the bundle assembler resolves them via `--repo-root` (for toolkit-internal paths like `devspec_toolkit/...`) and `--git-root` (for host-spec paths like `spec/...`).

---

## 4. Pointer contract

Pointers are how the LLM refers to entries without emitting their content.

### 4.1 Shape

```json
// Entry-level lookup (most common)
{ "file": "spec/04_fr_list.json", "id": "fr-newsletter-subscribe" }
```

Or, for jq-path access where `id` is ambiguous:

```json
// Sub-field lookup (when targeting a specific path within an entry)
{ "file": "spec/04_fr_list.json", "jq_path": ".functional_requirements[2].acceptance" }
```

**The LLM must never emit JSON content from the underlying file.** Content is always fetched by the CLI after pointer validation. Violations are a protocol break; the orchestrator must discard the response and re-prompt.

### 4.2 Validation

Every emitted pointer is validated by `specdev json resolve-pointers` before it is fetched, used, or returned to Claude. Misses surface as:

```json
{
  "pointer": { "file": "spec/04_fr_list.json", "id": "fr-nonexistent" },
  "exists": false,
  "reason": "missing_path",
  "nearest": [
    { "id": "fr-newsletter-subscribe", "score": 0.62 },
    { "id": "fr-newsletter-confirm", "score": 0.58 }
  ]
}
```

Every miss record carries a `reason` field. The exhaustive set of values the implementation emits:

| `reason` value | Meaning |
|---|---|
| `missing_file` | `file` path does not exist on disk |
| `missing_path` | id not found in the file's entry corpus (accompanied by `nearest[]`), or `jq_path` returned null / a jq error |
| `file_parse_error: <exc>` | file exists but is not valid JSON |
| `file_read_error: <exc>` | OS-level error reading the file |
| `invalid_shape: pointer must be a JSON object` | pointer is not a dict (e.g. bare string) |
| `invalid_shape: 'file' field is missing or not a string` | missing or non-string `file` field |
| `invalid_shape: pointer must contain 'id' or 'jq_path'` | neither lookup field present |
| `invalid_shape: path_escapes_git_root` | normpath of resolved path falls outside `--git-root` (B1 traversal guard) |
| `invalid_shape: path resolves to a directory` | `file` names a directory, not a file |
| `invalid_shape: path is under forbidden temp prefix '<prefix>'` | absolute path under `/tmp/`, `/var/tmp/`, `/private/tmp/`, `/var/folders/`, or `$TMPDIR` |
| `invalid_shape: path is under forbidden prefix '<prefix>'` | relative path under `.specdev/` |
| `invalid_shape: path has forbidden extension '<ext>'` | `*.txt` or other forbidden extension |

Note: `missing_path` is reused for two distinct miss cases — id-lookup failure (has `nearest[]`) and jq-path null/error (no `nearest[]`). Consumers can distinguish them by checking whether `nearest` is present in the miss record.

The `nearest` array is computed by the CLI from normalized Levenshtein distance over kebab-tokens of ids in the file (§15), not by an LLM. It exists so the next re-prompt can give the LLM concrete alternatives.

#### 4.2.1 Corpus exclusions

The id lookup corpus is built from registered entry arrays in the entry-key registry. The following array keys are always excluded from the corpus regardless of which spec file contains them:

- `canonical_refs_used` — cross-reference list; these are references to canon entries, not primary ids.
- `canonical_proposals` — staging proposals awaiting promotion; not yet authoritative ids.

Additional per-array exclusions may be declared via `corpus_excluded: true` in `entry_key_registry.json`. Excluded arrays never appear in `nearest[]` suggestions.

**Location:** `entry_key_registry.json` lives at `<spec_root>/entry_key_registry.json` in the **host project's spec directory** — not inside the toolkit submodule. Each project provides its own registry. Pass `--spec-root <host-spec-path>` to `specdev json resolve-pointers` (required) so the registry is loaded from the correct location.

**Registry health:** `specdev registry-check --spec-root <host-spec-path> --repo-root <toolkit-path>` validates the registry itself (three checks: R001 coverage against `step_order.json`, R002 phantom-basename guard against `extraction_paths.json`, R003 drift detection of registered `array_path`/`id_field` triples against live spec files). This command is folded into `spec-check` — when `entry_key_registry.json` is present, `spec-check` automatically includes the registry-check result in its per-check breakdown.

### 4.3 Forbidden pointer shapes

- Bare strings (e.g. `"fr-x"`) — file context is mandatory
- File paths without an id or jq_path
- Anything resolving to a directory rather than a file
- Pointers to files under `.specdev/`, `*.txt` dumps, or temp paths

---

## 5. Loops

Two distinct loops with different cost profiles, different bounds, and different termination conditions. They compose: the inner loop runs *inside* the planning phase of the outer loop.

### 5.1 Inner loop — pointer verification (cheap)

```
plan:    LLM emits pointer bundle
verify:  specdev json resolve-pointers
repair:  if misses: re-prompt with miss set + nearest-name hints
         if no misses: proceed
```

**Bound:** `SPECDEV_LLM_INNER_MAX_ITERS` (default 3).

**Termination conditions** (in order checked):
1. Miss set is empty — return validated bundle.
2. Miss set has not shrunk for **2 consecutive iterations**, OR the same miss set appears twice in a row — return partial bundle with `unresolved[]`. (This avoids premature exit on productive-but-non-strict-monotonic trajectories.)
3. Iteration count reached `INNER_MAX_ITERS` — return partial bundle with `unresolved[]`.

**Cost:** O(iterations × LLM call). No spec edits, no filesystem mutation. Safe to run aggressively.

**Honest partial returns are required.** If pointers cannot be resolved, the response includes `unresolved[]` with reasons. Silent drops are forbidden.

### 5.2 Outer loop — remediation gate (expensive)

```
snapshot:        specdev context snapshot <spec_dir> --step <NN> \
                   --repo-root <toolkit> --spec-root <host-spec> --git-root <host>
plan:            LLM proposes edit (inner loop validates pointers)
dry-run:         specdev json patch|insert|delete --dry-run --against-schema-field <NN>.<field>
apply:           specdev json patch|insert|delete (write to disk)
check:           specdev spec-check --json
forward-replay:  if upstream step mutated, run forward-replay-check; failures flow into re-prompt
repair:          if findings: feed structured envelopes to LLM, re-plan
                 if green: exit success
```

Submodule deployments require all three root flags on `context snapshot` (and every other sub-command); see toolkit `CLAUDE.md` for the flag-rules contract.

**Bound:** `SPECDEV_LLM_MAX_ITERS` (default 3).

**Termination conditions** (in order checked):
1. `spec-check` exits green — return `{applied: true, ...}`.
2. No edit converges within `MAX_ITERS` — rollback to snapshot, return `{applied: false, ...}`.
3. Unrecoverable error (file missing, schema not found, endpoint down) — rollback to snapshot, return error.

**Cost:** O(iterations × (LLM call + spec-check)). Each iteration mutates files; rollback is the safety net.

**Never leave artifacts in a half-fixed state.** On any non-success exit, the snapshot is restored. Snapshots are stored in `.specdev/snapshots/` and are not committed to git.

**Snapshots are per-step.** The snapshot is taken with `context snapshot <spec_dir> --step NN` and covers only the files belonging to step `NN`. The outer loop operates on **one step per invocation** — multi-step mutations require multiple sequential `specdev llm edit` calls. A single `llm edit` invocation must not mutate files belonging to more than one step.

---

## 6. Claude-facing return schemas

### 6.1 `specdev llm bundle`

The bundle return is the shape defined in §3.3 — orientation context plus structural summaries plus, when `--task` is provided, a **pointer-only** `scoped_entries` array. **No entry content is ever materialized into the bundle.** Agents drill down to content via `specdev json resolve-pointers` and `specdev json read` per the recipe in story 17's skill extension.

Happy path (`--task` provided, all pointers resolved):

```json
{
  "step": "04",
  "task": "implement FR-newsletter-subscribe end-to-end",
  "bundle_version": "1",
  "context": { "skill_md": "...", "prompt_NN": "...", "...": "..." },
  "upstream_structure": {
    "spec/03_glossary.json": { "entry_count": 47, "top_level_keys": ["terms"] }
  },
  "step_structure_summary": {
    "spec/04_fr_list.json": { "entry_count": 23, "ids": ["fr-newsletter-subscribe", "..."] }
  },
  "scoped_entries": [
    { "file": "spec/04_fr_list.json", "id": "fr-newsletter-subscribe", "jq_path": ".functional_requirements[3]" }
  ],
  "unresolved": [],
  "iterations": { "inner": 2 },
  "partial": false,
  "ok": true
}
```

`ok: true` iff the orientation bundle assembled without error AND (if `--task` was provided) `unresolved` is empty. `partial` is `false` when `ok: true`.

On partial success (some pointers could not be resolved):

```json
{
  "step": "04",
  "task": "implement FR-newsletter-subscribe end-to-end",
  "bundle_version": "1",
  "context": { "...": "..." },
  "upstream_structure": { "...": "..." },
  "step_structure_summary": { "...": "..." },
  "scoped_entries": [
    { "file": "spec/04_fr_list.json", "id": "fr-newsletter-subscribe", "jq_path": ".functional_requirements[3]" }
  ],
  "unresolved": [
    { "pointer": { "file": "spec/04_fr_list.json", "id": "fr-bogus" }, "reason": "no match; nearest: fr-newsletter-subscribe" }
  ],
  "iterations": { "inner": 3 },
  "partial": true,
  "ok": false
}
```

`ok: false` with a non-empty `unresolved` is the honest-failure case; `partial: true` distinguishes "tried, partial success" from "tried nothing". Claude decides whether to proceed with the partial bundle (the validated pointers are still emitted, so the agent can still drill into them).

When `--task` is omitted, `scoped_entries` and `unresolved` are empty arrays. `iterations.inner` is `0`. `ok` is `true` iff the orientation bundle assembled without error. The agent picks pointers from `step_structure_summary` and fetches content itself via `specdev json read`.

### 6.2 `specdev llm edit`

```json
{
  "task": "change owner of fr-newsletter-subscribe to product",
  "bundle_version": "1",
  "applied": true,
  "snapshot_id": "snap-04-20260512T170032Z-a3f1",
  "files_changed": ["spec/04_fr_list.json"],
  "commands_run": [
    { "cmd": "specdev json patch ...", "exit": 0 }
  ],
  "spec_check": { "status": "green", "findings": [] },
  "iterations": { "outer": 1, "inner": 1 },
  "ok": true
}
```

`ok: true` iff `applied: true` AND `spec_check.status == "green"`. Any other combination is `ok: false`.

On failure:

```json
{
  "task": "...",
  "bundle_version": "1",
  "applied": false,
  "snapshot_id": "snap-...",
  "rolled_back": true,
  "spec_check": { "status": "failed", "findings_summary": [ ... ] },
  "iterations": { "outer": 3, "inner": 2 },
  "ok": false,
  "handoff": [
    { "pointer": { "file": "...", "id": "..." }, "reason": "..." }
  ]
}
```

`handoff[]` is the compact `(pointer, reason)` list Claude consumes if it needs to take over.

### 6.3 `specdev llm remediate`

```json
{
  "bundle_version": "1",
  "from": ".specdev/spec-check.json",
  "resolved": [
    { "code": "E110", "file": "spec/04_fr_list.json", "id": "fr-x", "command_run": "specdev canon-accept ..." }
  ],
  "unresolved": [
    { "code": "E530", "subcode": "LINKED_TEST_FILE_NOT_FOUND", "file": "...", "reason": "no candidate fix succeeded" }
  ],
  "commands_run": [ ... ],
  "iterations": { "outer": 2 },
  "partial": true,
  "ok": false
}
```

`ok: true` iff `unresolved` is empty (all findings resolved). `partial: true` iff some findings were resolved AND some remain unresolved — distinguishes "tried, partial success" from "tried nothing" (both `resolved` and `unresolved` empty) and from "fully green" (`ok: true`). `partial` is `false` when `ok: true`.

### 6.4 Exit codes

All three `specdev llm *` commands follow this policy:

| Outcome | Applies to | Exit code |
|---|---|---|
| `ok: true` | `bundle` \| `remediate` \| `edit` | 0 |
| `ok: false`, `partial: true` (some resolved) | `bundle` \| `remediate` | 0 (caller branches on JSON) |
| `ok: false`, nothing resolved | `bundle` \| `remediate` | 1 |
| `ok: false` (any failure) | `edit`[^edit-no-partial] | 1 |
| Unrecoverable error (endpoint down, missing config, invalid step) | `bundle` \| `remediate` \| `edit` | 2 |
| Usage error (bad flags) | `bundle` \| `remediate` \| `edit` | 64 (EX_USAGE) |

[^edit-no-partial]: `llm edit` has no `partial` field; any failure exits 1 (row 4).

`specdev json resolve-pointers` always exits 0 (the report is the artifact).

---

## 7. Local-agent-facing details

### 7.1 Error envelope (emitted by lints with `--json`)

The `--json` boolean flag already exists on: `spec-check`, `canonical-integrity`, `hallucination-lint`, `canonical-lint`, `canonical-autofix`, `glossary-drift-check`, `traceability-check`, `completeness-check`, `registry-check`. The current top-level envelope is `{status, error_count, warning_count, errors[]}` and each error object has `{code, message, severity}` always present; `path` is present when set. The extensions below add new fields to each error object without removing existing ones — existing consumers continue to work unmodified.

Extended per-error fields: `subcode` (optional string), `file` (string; equals `path` when not split out separately), `jq_path` (string; location within the file), `value` (the offending value), `remediation{}` (structured fix candidates — see example). These are additive; no existing field is renamed or removed.

```json
{
  "code": "E530",
  "subcode": "INVENTED_ENUM_OR_ID",
  "severity": "error",
  "file": "spec/09_impl_plan.json",
  "jq_path": ".plan[3].command",
  "value": "kubectl apply -f manifests/",
  "message": "Verb 'kubectl' not in allowlist",
  "remediation": {
    "fix_kind": "register-command-prefix | register-command-canon | rewrite-value",
    "candidates": [
      {
        "kind": "register-command-prefix",
        "command": "specdev json insert spec/canon/command_prefixes.json '.allowed_prefixes' '\"kubectl\"'",
        "rationale": "Allowlist extension; merged with toolkit default"
      },
      {
        "kind": "register-command-canon",
        "command": "specdev json insert spec/canon/kinds/command.json '.commands' '{\"id\": \"cn:project:command:kubectl\", ...}'",
        "rationale": "Canonical id; sibling command_ref bypasses prefix check"
      }
    ],
    "references": [
      "docs/developers/error-codes.md#E530",
      "specdev guide E530"
    ]
  }
}
```

### 7.2 `specdev guide <code>`

Returns the canonical remediation playbook for an error code. Backed by `tools/specdev_tools/guides/*.yaml` (or equivalent). Single source of truth; `docs/developers/error-codes.md` is generated from this, and `CLAUDE.md` troubleshooting prose is reduced to a pointer.

### 7.3 `specdev json resolve-pointers`

```bash
# Pointer list is read from stdin; no --in flag. --out optional (defaults to stdout).
specdev json resolve-pointers [--out report.json] < pointers.json
cat pointers.json | specdev json resolve-pointers
```

Always exits 0. The report is the artifact:

```json
{
  "results": [
    {
      "pointer": { "file": "spec/04_fr_list.json", "id": "fr-x" },
      "exists": true,
      "kind": "functional_requirement",
      "jq_path": ".functional_requirements[2]",
      "value_preview": { "fr_id": "fr-x", "name": "...", "owner": "..." }
    },
    {
      "pointer": { "file": "spec/04_fr_list.json", "id": "fr-bogus" },
      "exists": false,
      "nearest": [ { "id": "fr-x", "score": 0.71 } ]
    }
  ],
  "summary": { "hits": 1, "misses": 1 }
}
```

### 7.4 Dry-run and schema-check on edits

```bash
specdev json patch <file> <jq-path> <value> [--dry-run] [--against-schema-field <step.field>]
```

The current `json patch/insert/delete` signature is `<file> <jq-path> <value> [--raw]`. `--dry-run` and `--against-schema-field` are **not yet implemented** — they are reserved flags documented here as the intended interface. Until implemented, passing them will produce a "not yet implemented" error. See §15 for the `--against-schema-field` dotted-path syntax.

When implemented: `--dry-run` returns the post-edit JSON without writing to disk. `--against-schema-field <step.field>` pre-checks the value's shape against a named field's schema before submission. Both are local-agent tools; Claude does not use them directly.

---

## 8. Configuration

### 8.1 Master switch

`SPECDEV_LLM_ENABLED=1` to enable. Default `0`. Disabled state errors fast on any `specdev llm *` invocation — no silent fallback to a non-LLM path.

### 8.2 Endpoint contract

OpenAI-compatible `POST /v1/chat/completions`. Supports `response_format: {"type": "json_object"}` for pointer emission. Native ollama, LM Studio, llama.cpp server, vLLM all speak this directly. Anthropic's OpenAI-compat shim works without protocol change.

No Anthropic-native Messages API support. If a future need surfaces, revisit with a concrete requirement.

### 8.3 Configuration precedence

CLI flag > environment variable > `specdev.toml` (or `.specdev/config.toml`) `[llm]` table. **Note:** `specdev.toml` does not exist today — this is a new file format to be introduced. Until it exists, only CLI flags and environment variables are active.

### 8.4 Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SPECDEV_LLM_ENABLED` | `0` | Master switch |
| `SPECDEV_LLM_BASE_URL` | — | e.g. `http://localhost:11434/v1` |
| `SPECDEV_LLM_MODEL` | — | e.g. `qwen2.5-coder:32b-instruct` |
| `SPECDEV_LLM_API_KEY` | `""` | Optional; required for hosted endpoints |
| `SPECDEV_LLM_TIMEOUT` | `120` | Per-request seconds |
| `SPECDEV_LLM_MAX_ITERS` | `3` | Outer loop bound |
| `SPECDEV_LLM_INNER_MAX_ITERS` | `3` | Inner loop bound |
| `SPECDEV_LLM_TEMPERATURE` | `0.1` | Low; deterministic-ish pointer emission |
| `SPECDEV_LLM_DRY_RUN` | `0` | Print prompts without calling endpoint |
| `SPECDEV_LLM_SMOKE` | `0` | Gate live-endpoint smoke tests (see §14). Off by default in CI. |

### 8.5 Diagnostic

`specdev env-check` prints active LLM config and probes the endpoint for reachability. No real planning call; just transport-level verification.

### 8.6 Recommended local models (M4 Pro 48GB)

| Model | Size (Q4_K_M) | Notes |
|---|---|---|
| Qwen2.5-Coder-32B-Instruct | ~20 GB | Strongest pointer planning; ~10–15 tok/s |
| DeepSeek-Coder-V2-Lite 16B | ~9 GB | Faster (~30 tok/s); slightly weaker reasoning |
| Llama-3.3-70B (Q3_K_M) | ~30 GB | Highest quality if you have the patience; ~5 tok/s |

Pick one based on the latency/quality tradeoff for your workflow. The protocol is model-agnostic — anything that respects the OpenAI-compatible JSON mode contract will work.

---

## 9. Forbidden patterns

These are protocol breaks. Orchestrator must detect and recover, not silently accept.

| Pattern | Why forbidden | Recovery |
|---|---|---|
| LLM emits JSON content from a spec file | Hallucination surface; bypasses validation | Discard response; re-prompt with pointer-only instruction |
| Claude calls a lint command directly | Token bloat; envelopes leak | Route through `specdev llm remediate` |
| Lint envelope reaches Claude's context | Same | Outcome reports compress to `(pointer, reason)` |
| Silent partial bundle (drops misses without reporting) | Hides failure | `unresolved[]` must be non-empty if misses occurred |
| Spec edit applied without snapshot | No rollback path | Outer loop refuses to proceed if snapshot missing |
| `specdev llm *` invoked with `ENABLED=0` falling back to non-LLM path | Hides token regression | Error fast with actionable message |

---

## 10. Failure handoffs

When the local agent cannot complete a task within its loop bounds, it returns control to Claude with a compact handoff payload. The handoff is not a full envelope dump — it is the minimum information needed for Claude to decide what to do next.

### 10.1 Handoff payload

```json
{
  "ok": false,
  "failed_phases": ["inner", "outer"],
  "iterations": { "inner": 3, "outer": 2 },
  "rolled_back": true,
  "last_iteration_log": [
    "<raw LLM response N-2>",
    "<raw LLM response N-1>",
    "<raw LLM response N>"
  ],
  "handoff": [
    {
      "pointer": { "file": "spec/04_fr_list.json", "id": "fr-bogus" },
      "reason": "pointer did not resolve after 3 inner iterations; nearest: fr-newsletter-subscribe"
    },
    {
      "pointer": { "file": "spec/06_invariants.json", "jq_path": ".invariants[2]" },
      "reason": "E530 INVENTED_ENUM_OR_ID; no remediation candidate succeeded"
    }
  ]
}
```

`failed_phases` is an array; it can include `"inner"`, `"outer"`, or both, depending on where termination was triggered. `last_iteration_log` contains the last 3 raw LLM responses (capped to avoid token bloat) — useful for forensic diagnosis when handing off to a human or Claude.

### 10.2 Claude's options on handoff

1. **Accept the partial result** if the unresolved set is non-blocking.
2. **Probe for depth** by calling `specdev json read` on a specific pointer — single-purpose query, no protocol re-entry.
3. **Re-issue the task** with a narrower `--scope` or `--task` phrasing.
4. **Take over directly** if the failure indicates a design decision needed (e.g. the LLM couldn't pick between two equally valid canonical-id registrations).

Claude does not re-enter the loop. Re-entry happens only via a new `specdev llm *` invocation.

---

## 11. Sequencing — implementation order

Tracked in Plane module *Local LLM Offload for Spec Workflow*. Five waves; dependencies resolve forward.

| Wave | Stories | What unblocks |
|---|---|---|
| Wave A — foundation (provider-agnostic) | 01 *(this doc)*, 04a *(entry-key registry)*, 09a *(prompt templates + schemas)*, 15a *(test fixtures)*, 17 *(extend `/specdev-context` skill with LLM-offload sections + composition recipes)* | Protocol contract, deterministic primitives' inputs, and the unified spec-surface skill |
| Wave B — deterministic primitives | 04 *(resolve-pointers)*, 05 *(bundle without --task)* | The pointer-verification floor and orientation-bundle assembly |
| Wave C — lint envelopes & guides | 06, 07, 08 *(`--json` envelope extensions)*, 09 *(remediation{})*, 10 *(specdev guide + CLAUDE.md migration)* | Structured findings for remediation; canonical playbook |
| Wave E — local LLM provider (deferred) | 02 *(LLM config)*, 03 *(HTTP adapter)*, 11 *(inner loop Python)*, 13 *(outer loop Python + dry-run flags)*, 14 *(llm edit)*, 15 *(llm remediate)*, 12 *(bundle --task with semantic widening)* | Full automation, no Claude Code session required |
| Wave F — local LLM quality | 16b *(integration tests + smoke for local-LLM mode)* | CI lock-in for the local-LLM path |

**No Wave D.** The Claude Code subagent bridge has no dedicated integration-test wave — see §16.4. Bridge correctness is asserted by (a) the design doc + the unified `/specdev-context` skill extensions shipped in story 17 and (b) the unit/integration tests already owned by each CLI command's story (04, 05, 06–10).

Note: story 17 and 16b are new — they will be filed in Plane by the ticket-side agent. Story numbers may differ; cross-reference by name not number when adjusting prose.

Each story description in Plane is the implementation contract for that wave's deliverable. This doc is the integration contract across all of them.

---

## 12. Versioning

`bundle_version` is the **only** version field surfaced in API responses (every `specdev llm *` return includes it). The toolkit's own semver in `tools/pyproject.toml` is independent and does not drive protocol compatibility.

`bundle_version` is a string (currently `"1"`). Breaking changes to any contract here — pointer shape, return schemas, envelope shape, field semantics — bump `bundle_version` AND require a `specdev align` migration for hosts that vendor the toolkit. See §15 for bumping rules and `SPECDEV_LLM_DRY_RUN` semantics.

Non-breaking additions (new env vars with sensible defaults, new optional fields in return schemas, new remediation candidates) do not bump `bundle_version`.

Current version: **"1"** (draft — not yet implemented).

---

## 13. Prompt templates and response schemas

Prompt templates live at `devspec_toolkit/tools/specdev_tools/llm/prompts/*.md`. One template per loop:

| Template | Loop it drives | Used by |
|---|---|---|
| `inner_plan.md` | Inner loop — initial pointer planning prompt | `specdev llm bundle --task`, `specdev llm edit`, `specdev llm remediate` |
| `inner_repair.md` | Inner loop — re-prompt after miss set returned | same as above |
| `outer_edit.md` | Outer loop — edit proposal given validated pointers | `specdev llm edit` |
| `outer_remediate.md` | Outer loop — remediation plan given structured findings | `specdev llm remediate` |
| `widen_semantic.md` | Widen (pass 2 of `bundle --task`) — semantic expansion when pointer scope is too narrow | `specdev llm bundle --task` |

Each template specifies: system message, user message format, and expected JSON-mode response shape. Templates are committed to the repository; they are not generated at runtime.

**Template file structure** — every template under `prompts/*.md` has four front-matter-delimited sections in this order; story 09a's acceptance criteria assert this layout:

1. **`# meta`** — YAML block: `name`, `model` (default `haiku-4-5`; override per §16.1), `loop` (`inner` \| `outer-edit` \| `outer-remediate` \| `widen`), `response_schema` (path under `schemas/`), `response_format` (`json_object`).
2. **`# system`** — system message (deterministic-ish guardrails: pointer-only emission, no content, response must validate against `response_schema`).
3. **`# user`** — Jinja-style placeholders for bundle slots (`{{ context.prompt_NN }}`, `{{ task }}`, `{{ step_structure_summary }}`, `{{ unresolved }}`, etc.). Loop modules render the user message at call time.
4. **`# response_shape`** — fenced JSON example of the expected response, mirrored by the schema file. Smoke tests assert example-validates-against-schema before any loop runs.

Response JSON schemas live at `devspec_toolkit/tools/specdev_tools/llm/schemas/*.schema.json`. One schema per response type:

| Schema file | Validates |
|---|---|
| `pointer_response.schema.json` | LLM pointer bundle emission (inner loop output) |
| `edit_response.schema.json` | LLM edit proposal (outer loop output) |
| `remediation_response.schema.json` | LLM remediation plan (remediate loop output) |
| `bundle_response.schema.json` | Bundle CLI return envelope (success, partial, and failure variants) |

Loop modules import templates and schemas at runtime. Smoke tests assert that each response from a real or mocked LLM validates against its schema before the loop acts on it.

**Model assignments per template** — see §16.1. All five templates default to `haiku-4-5` except `widen_semantic.md` which uses `sonnet-4-6` (the one phase where reasoning quality matters). Subagent invocations override via the Agent tool's `model` parameter; local-LLM mode reads `SPECDEV_LLM_MODEL` from §8.

**Status:** Templates and schemas are live. Prompt templates are at `devspec_toolkit/tools/specdev_tools/llm/prompts/` and response schemas at `devspec_toolkit/tools/specdev_tools/llm/schemas/`. Unit tests for both are at `devspec_toolkit/tests/unit/llm/`.

---

## 14. Test fixtures and CI gating

Fixtures live at `devspec_toolkit/tools/specdev_tools/llm/test_fixtures/`. Two kinds of fixtures; do not mix them.

**Spec-fixture directories** (mini-spec dirs readable by `spec-check`, stored in `test_fixtures/specs/`):

| Directory | Failure mode exercised |
|---|---|
| `e110_missing_canon/` | E110 UNKNOWN_CANONICAL_ID — entry references an unregistered canonical id |
| `e530_invented_verb/` | E530 INVENTED_ENUM_OR_ID — command verb not in allowlist |
| `e530_missing_test_file/` | E530 LINKED_TEST_FILE_NOT_FOUND — linked test path does not exist |

**LLM-response fixture JSON files** (static JSON examples of LLM outputs, stored in `test_fixtures/llm_responses/`; not mini-spec dirs):

| File | Failure mode exercised |
|---|---|
| `pointer_miss_typo.json` | LLM emits `fr-newslettr-subscribe` (typo) vs real `fr-newsletter-subscribe` |
| `pointer_miss_wrong_file.json` | pointer with correct id but wrong file |

Unit tests use mocked HTTP transport (no real LLM calls). Integration tests require `SPECDEV_LLM_SMOKE=1` in the environment — this is **off by default** in CI to avoid network dependencies. Set `SPECDEV_LLM_SMOKE=1` explicitly for smoke runs against a live endpoint.

---

## 15. Open implementation choices

These decisions are deliberately deferred. Each has a constraint that must be respected when the choice is made.

- **Nearest-name algorithm** for pointer miss hints: must be deterministic, LLM-free, and fast (< 10ms per 100-id corpus). Suggested approach: normalized Levenshtein over kebab-tokens of ids in the file (file-local ids only — not global canon), top-3 results. The algorithm lives in the CLI, not in a prompt.

- **Snapshot id format**: must be sortable, unique per invocation, and embedded in `edit`/`remediate` return payloads. Suggested format: `snap-<step>-<UTC-ISO-timestamp>-<short-hash>` (e.g. `snap-04-20260512T170032Z-a3f1`).

- **Concurrency model**: single-writer per host repo. Two concurrent `specdev llm edit` invocations must serialize via a lock file at `.specdev/locks/edit.lock`. The second invocation fails fast with a clear message identifying the lock holder and PID. No silent queuing.

- **Versioning**: `bundle_version` (string, currently `"1"`) is the protocol-contract version. Breaking changes bump it AND require `specdev align` migration. Non-breaking additions do not bump. See §12.

- **`SPECDEV_LLM_DRY_RUN=1` semantics**: prints all prompts to stdout, makes no HTTP calls, makes no filesystem mutations (no snapshot written, no edit applied, no report file created). Intended for prompt-template debugging and CI sanity checks. Implication: `--out` is ignored under dry-run.

- **`specdev guide` argument shape**: takes the full error code (`E110`) or the hyphen-joined subcoded form (`E530-INVENTED_ENUM_OR_ID`). Both resolve to the same playbook entry; the subcoded form returns a more specific sub-section. Slash-separated or underscore-separated forms are not supported.

- **`remediate` scope**: covers any error code present in the guide registry. Codes without a guide entry are reported as `unresolved` with reason `"no remediation guide"` — never silently dropped. This means `remediate` is safe to run on any `spec-check` output without pre-filtering.

- **Forward-replay integration**: an `llm edit` that mutates an upstream-step file must run `forward-replay-check` after the edit and report failures in `spec_check.forward_replay` (a sub-field of the return payload). If `forward_replay` has failures, the outer loop treats the edit as non-green and includes replay failures in the re-prompt.

- **`specdev llm replay --from-step NN` — out of scope for this module.** Regenerating downstream artifacts (as distinct from detecting drift) is a generation-driven workflow that requires per-step prompt-template execution, different outer-loop semantics, and a transactional regeneration model across the forward DAG. Tracked as a deferred feature request at Plane **DEVSPEC-24** (`http://127.0.0.1/vc-studio/browse/DEVSPEC-24/`), filed outside any module against the `devspec_toolkit` project; will belong to a future "Trinity-loop automation" module. Interim workaround: the unified `/specdev-context` skill (extended in story 17) hosts a manual replay playbook a subagent can execute under user oversight.

- **`--against-schema-field` syntax**: dotted path `<step>.<field>` (e.g. `04.functional_requirements`), resolved against `devspec_toolkit/schema/<step>_*.schema.json`. **Multi-schema step disambiguation:** when a step has more than one schema file (today: step `16` has both `16_anchor.schema.json` and `16_impl_context.schema.json`), use the extended form `<step>.<schema_suffix>.<field>` (e.g. `16.anchor.steps`, `16.impl_context.tasks`). The `<schema_suffix>` is the portion of the schema filename between `<step>_` and `.schema.json`. For single-schema steps the suffix is omitted. The flag is a local-agent tool; it validates the proposed value's shape before the edit is submitted to the file. Not yet implemented — flag is reserved but rejected with a clear "not yet implemented" message until story 13 delivers it.

---

## 16. Claude Code subagent provider mode (bridge workflow)

The protocol is provider-agnostic. Until the local LLM path ships (Wave E), Claude Code can execute the same contract by spawning subagents. This is the **default and recommended mode today**.

### 16.1 Mapping protocol roles to subagents

| Protocol role | Subagent type | Suggested model | Why |
|---|---|---|---|
| Inner-loop pointer planning | general-purpose subagent invoked via Agent tool with read-only Bash + Read/Grep/Glob | `haiku-4-5` | Read-only, cheapest. Uses Bash to call `specdev json read`. |
| Pointer validation | general-purpose subagent invoked via Agent tool with read-only Bash + Read/Grep/Glob | `haiku-4-5` | Same agent runs `specdev json resolve-pointers` via Bash. |
| Outer-loop edit application | general-purpose subagent invoked via Agent tool with read-only Bash + Read/Grep/Glob | `haiku-4-5` | Runs `specdev json patch/insert/delete` via Bash (no Edit tool needed — CLI is the canonical write path and forces schema-aware validation). |
| Outer-loop orchestrator | orchestrator (main conversation, or general-purpose subagent that spawns children via Agent tool) | `haiku-4-5` | Needs Agent tool to spawn subagent children for plan→validate→apply. |
| Semantic widening (bundle --task) | general-purpose subagent invoked via Agent tool with read-only Bash + Read/Grep/Glob | `sonnet-4-6` | The one phase where reasoning quality matters; budget a model step up. |

### 16.2 Token economics

The bridge mode achieves the same isolation goals as the local-LLM mode:

- Main thread sees only compact subagent results (typically <5 KB), never raw spec JSON.
- Subagent input (specs, prompts, structure index) is billed at the subagent's model rate — Haiku is ~1/15 Opus.
- Inner-loop iteration happens entirely inside the orchestrator subagent; main thread waits once.

### 16.3 Permissions

In permission-restricted Claude Code modes, the user must pre-allow the following Bash invocations for the subagents to operate unattended:

- `specdev json read`, `specdev json read-multi`, `specdev json resolve-pointers`
- `specdev json patch`, `specdev json insert`, `specdev json delete`
- `specdev spec-check --json`
- `specdev guide`
- `specdev context structure`, `specdev context snapshot`, `specdev context diff`

In permissive modes this is automatic; for `--strict` or CI runs, add an allow-list rule.

### 16.4 Provider-mode parity

Both providers consume the same:

- **Orientation bundle** (`specdev llm bundle --step NN` — same command, same output)
- **Prompt templates** (`devspec_toolkit/tools/specdev_tools/llm/prompts/*.md` — same files)
- **Response JSON schemas** (`devspec_toolkit/tools/specdev_tools/llm/schemas/*.schema.json` — same shapes)

**Test coverage policy:** Subagent-mode (Claude Code bridge) is documentation- and skill-driven; no automated test suite covers the bridge behavior itself. CLI commands invoked by the bridge are tested as part of their owning stories. Local-LLM-mode tests (story 16b) provide the only integration coverage that includes loop dynamics.

### 16.5 Migration to local-LLM mode

Switching from subagent mode to local-LLM mode is a config change, not a code change:

1. Implement the toolkit-side `specdev llm *` commands (Wave E).
2. Set `SPECDEV_LLM_ENABLED=1` and `SPECDEV_LLM_BASE_URL=...`.
3. Claude Code stops spawning subagents for these roles and instead calls `specdev llm bundle --task / edit / remediate` directly.

Until step 2 is set, Claude Code's main thread continues using the subagent pattern.

---

## 17. CLI surface principles

These principles govern every `specdev *` command added by this module. They exist because LLM-driven workflows fail when the surface grows faster than the agent's ability to reason about it.

### 17.1 Flag minimalism

A new flag is justified only when it meets one of these criteria:

| Criterion | Example |
|---|---|
| **Mandatory input** with no sensible default | `--step NN`, `--task "..."`, `--from <lint.json>` |
| **Output destination** the user explicitly controls | `--out <path>` |
| **Safety toggle** requiring explicit user intent | `--dry-run`, `--force` |
| **Architectural** — required by toolkit deployment | `--repo-root`, `--spec-root`, `--git-root` |
| **Standard output shape switch** | `--json` |

A flag does **not** earn its place if:

- It has a sensible default that's right ~95% of the time → use an env var (`SPECDEV_LLM_*`) or a fixed value.
- The workflow it enables composes from existing primitives → document the composition as a recipe in the skill (§16 / story 17), not a flag.
- It's a convenience alias for two existing operations → skill recipe.
- It exposes loop tuning or operational thresholds → `SPECDEV_LLM_*` env var.

### 17.2 Recipes over configuration

When a workflow variant is genuinely useful but composes from existing primitives, codify it as a **named recipe in the skill**, not as a new flag, mode, or command. Examples this module adopts:

- **Drill-down extraction**: bundle (structure only) → `json read` with jq counts/slices → `json resolve-pointers` for selected entries. No `--mode index`, no `--enumerate`, no `--page`.
- **Code-filtered remediation**: `spec-check --json | jq 'select(.code=="E110")' | specdev llm remediate -`. No `--code` flag on `remediate`.
- **Rollback after edit**: `specdev context diff <step>` to inspect, then git or `context snapshot` to restore. No `--rollback` flag on `llm edit`.
- **Replay** (interim, until the deferred `llm replay` ships): manual playbook in the skill, subagent-executed step-by-step. No new CLI surface.

The principle: **the CLI exposes primitives; the skill teaches composition.**

### 17.3 Reasoning the skill must articulate

The skill (and any future contributor docs) must explain *why* recipe-over-flag wins, so future PRs don't yes-and a flag back in:

1. **Live reads are staleness-free.** Each composed call reads fresh state. No cached state to invalidate.
2. **Output budgets are unpredictable across harnesses.** Composing small calls keeps every individual response under any tool-call clipping limit. A single fat call that "should" fit often doesn't.
3. **The agent's "what to look at" decision improves with each call.** Drilling down means each pick is informed by the previous answer.
4. **Failure is isolated.** A single composed call failing doesn't blow up the whole assembly. The agent retries that call, not the world.
5. **Pagination via jq is free and general** (`.arr[0:50]`). No CLI flag, no off-by-one bugs, no schema knowledge in the CLI.

### 17.4 Field minimalism in response envelopes

The same principle applies to response shapes, not just CLI flags. The `remediation{}` envelope added by stories 06–09 stays at `{guide_code, parameters, owner_story}` — agents follow `guide_code` to `specdev guide <code>` for the full playbook. Do not add `severity_override`, `suggested_fix_text`, `auto_apply: bool`, or similar fields. The guide is the canonical playbook; the envelope is the cross-reference.
