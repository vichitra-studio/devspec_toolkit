# LLM Protocol — Agentic Spec Workflow

**Status:** stable • **Audience:** Claude Code (consumer) + subagent implementer • **Tracked in:** DevSpec Toolkit

This document is the single source of truth for how agentic callers — Claude Code sessions, subagents, and CI orchestrators — interact with the DevSpec Toolkit. Its purpose is to keep JSON-shaped planning, drafting, and lint-remediation work disciplined while the toolkit's deterministic guarantees stay intact.

If a contract here ever conflicts with code, code wins and this doc is updated. If a contract here ever conflicts with a Plane story description, this doc wins.

---

## 1. The boundary

```
Coding agent  →  specdev CLI  →  spec files / canon / schemas
                              ↑ all rich machinery lives here ↑
                              ↓ compact outcomes only ↓
Coding agent  ←  specdev CLI
```

Three rules govern this boundary; everything else is implementation detail:

1. **The agent emits pointers, never JSON content.** Content always comes from the CLI's deterministic readers (`json read`, `json read-multi`). This makes hallucination unrecoverable-by-construction → recoverable-by-validation.
2. **The orchestrating agent sees compact outcomes only.** Validated pointer sets, green check summaries, or honest structured failures. Intermediate envelopes, dry-run details, and multi-iteration sub-work never reach the outer context.
3. **The CLI remains the deterministic ground truth.** Schema validation, canonical-id resolution, traceability, governance — none of these get routed through an LLM. The LLM is at the I/O edges; the CLI is the middle.

---

## 2. Audience

This document is written for a single audience: any agent (Claude Code session or subagent spawned from one) that drives the spec pipeline. There is no bundle-mode vs bridge-mode split. The `/specdev-context` skill is the canonical entry point; the subagent bridge is the production orchestration mode (see §5).

The agent-facing surface is:

- `specdev json read`, `specdev json read-multi` — structured reads without direct file access
- `specdev json resolve-pointers` — pointer verification primitive
- `specdev json patch | insert | delete` — schema-aware edits
- `specdev spec-check [--json]` — unified gate check
- `specdev guide <code>` — canonical error-code playbook
- `specdev context structure` — upstream dependency map for a step

The CLI remains the deterministic ground truth for all of the above. Agents compose these primitives; they do not bypass them.

---

## 3. The three static indices

Three indices are the structural backbone of the pipeline. Agents derive all pipeline navigation from them — never hardcode step relationships or file mappings. `step_order.json` and `entry_key_registry.json` are static toolkit-side artifacts at `devspec_toolkit/tools/`; `trace_matrix.json` is ephemeral — regenerated per-spec-run and written to `<spec_dir>/extras/trace_matrix.json` (canonical location). See `docs/architecture/three_static_indices.md` for the full architecture reference.

### 3.1 `step_order.json`

The strict waterfall DAG. Answers:

- "Does step X consume step Y?" — consult `downstream_consumers` for each step.
- "What is the full dependency chain for step N?" — walk the DAG forward from N.

Agents almost never query this file directly. `specdev context structure <spec_dir> --step NN` is the canonical entry point; it reads `step_order.json` internally and emits the resolved upstream dependency map for step `NN`.

### 3.2 `trace_matrix.json`

Generated cross-reference edges: FR↔API, FR↔fixture, FR↔NFR, FR↔threat. Answers:

- "Which FRs are covered by test fixture X?"
- "Which APIs does NFR-Y trace back to?"
- "What cross-step edges exist for spec entry Z?"

Use `specdev json read spec/extras/trace_matrix.json` with a jq filter to query specific link kinds or reachability slices. Do not load the full file into context.

### 3.3 `entry_key_registry.json`

Schema-derived kind→file mapping, programmatically generated and stored in `devspec_toolkit/tools/entry_key_registry.json` inside the **toolkit submodule** (not in the host project's spec directory). Answers:

- "Where does kind X live?" (which spec file, which array, which id field)
- "Is this id array excluded from pointer-resolution corpus?"

The registry is consumed by `specdev json resolve-pointers` (pass `--repo-root <toolkit-path>` — required, no cwd fallback) and validated by `specdev registry-check`. Hosts must not hand-edit this file; regenerate it with `specdev registry-generate --repo-root <toolkit-path>` after any schema change.

**Composition discipline:** derive step relationships from `step_order.json`, cross-step links from `trace_matrix.json`, and file/kind mappings from `entry_key_registry.json`. Never hardcode these.

**See also:** `docs/architecture/three_static_indices.md` — full architecture reference including update cadence, composition rules, and a worked impact-walking example.

---

## 4. Pointer contract

Pointers are how an agent refers to entries without emitting their content.

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

**The agent must never emit JSON content from the underlying file.** Content is always fetched by the CLI after pointer validation. Violations are a protocol break; the orchestrator must discard the response and re-prompt.

### 4.2 Validation

Every emitted pointer is validated by `specdev json resolve-pointers` before it is fetched, used, or returned to the caller. Misses surface as:

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
| `invalid_shape: path_escapes_git_root` | normpath of resolved path falls outside `--git-root` (traversal guard) |
| `invalid_shape: path resolves to a directory` | `file` names a directory, not a file |
| `invalid_shape: path is under forbidden temp prefix '<prefix>'` | absolute path under `/tmp/`, `/var/tmp/`, `/private/tmp/`, `/var/folders/`, or `$TMPDIR` |
| `invalid_shape: path is under forbidden prefix '<prefix>'` | relative path under `.specdev/` |
| `invalid_shape: path has forbidden extension '<ext>'` | `*.txt` or other forbidden extension |

Note: `missing_path` is reused for two distinct miss cases — id-lookup failure (has `nearest[]`) and jq-path null/error (no `nearest[]`). Consumers can distinguish them by checking whether `nearest` is present in the miss record.

The `nearest` array is computed by the CLI from normalized Levenshtein distance over kebab-tokens of ids in the file, not by an LLM. It exists so the next re-prompt can give the agent concrete alternatives.

#### 4.2.1 Corpus exclusions

The id lookup corpus is built from registered entry arrays in the entry-key registry. The following array keys are always excluded from the corpus regardless of which spec file contains them:

- `canonical_refs_used` — cross-reference list; these are references to canon entries, not primary ids.
- `canonical_proposals` — staging proposals awaiting promotion; not yet authoritative ids.

Additional per-array exclusions may be declared via `corpus_excluded: true` in `entry_key_registry.json`. Excluded arrays never appear in `nearest[]` suggestions.

**Location:** `entry_key_registry.json` lives at `<repo_root>/tools/entry_key_registry.json` inside the **toolkit submodule** — not in the host project's spec directory. Pass `--repo-root <toolkit-path>` to `specdev json resolve-pointers` (required) so the registry is loaded from the correct location.

**Registry health:** `specdev registry-check --spec-root <host-spec-path> --repo-root <toolkit-path>` validates the registry itself (three checks: R001 coverage against `step_order.json`, R002 phantom-basename guard against `extraction_paths.json`, R003 drift detection of registered `array_path`/`id_field` triples against live spec files). This command is folded into `spec-check` — when `entry_key_registry.json` is present, `spec-check` automatically includes the registry-check result in its per-check breakdown.

### 4.3 Forbidden pointer shapes

- Bare strings (e.g. `"fr-x"`) — file context is mandatory
- File paths without an id or jq_path
- Anything resolving to a directory rather than a file
- Pointers to files under `.specdev/`, `*.txt` dumps, or temp paths

---

## 5. The subagent bridge

Coding agents (Claude Code and equivalents) provide the orchestration harness. This is the production mode.

### 5.1 How it works

The orchestrating agent spawns subagents for context-bound work: reading spec files, resolving pointers, applying edits, running checks. Subagent outputs are compact — pointer sets, check summaries, structured findings — and never include raw spec JSON in the outer context.

The `/specdev-context` skill is the canonical entry point. It loads the schema-aware context for a pipeline step (`context structure` + canon) and emits the minimal working set for the task. Agents start there; they do not call `specdev json read` on spec files speculatively.

### 5.2 Role mapping

| Role | Subagent type | Suggested model | Why |
|---|---|---|---|
| Step context load | spawned via `/specdev-context` skill | `haiku-4-5` | Read-only, cheapest. Loads structure + entry index. |
| Pointer planning + validation | general-purpose subagent with Bash + Read/Grep | `haiku-4-5` | Calls `specdev json read` and `specdev json resolve-pointers` via Bash. |
| Edit application | general-purpose subagent with Bash | `haiku-4-5` | Runs `specdev json patch/insert/delete` — CLI is the canonical write path and forces schema-aware validation. |
| Orchestrator | main conversation or outer subagent | `haiku-4-5` | Sequences plan→validate→apply; sees only compact outcomes from each step. |

### 5.3 Token economics

- Main thread sees only compact subagent results (typically < 5 KB), never raw spec JSON.
- Subagent input (specs, prompts, structure index) is billed at the subagent's model rate — Haiku is ~1/15 Opus.
- Subagent work happens in a single pass; main thread sees only the compact result.

### 5.4 Permissions

In permission-restricted Claude Code modes, the user must pre-allow the following Bash invocations for subagents to operate unattended:

- `specdev json read`, `specdev json read-multi`, `specdev json resolve-pointers`
- `specdev json patch`, `specdev json insert`, `specdev json delete`
- `specdev spec-check --json`
- `specdev guide`
- `specdev context structure`

In permissive modes this is automatic; for `--strict` or CI runs, add an allow-list rule.

### 5.5 Drill-down recipe

The canonical pattern for reading spec content without loading raw files:

1. Call `specdev context structure <spec_dir> --step NN` to get the upstream dependency map and entry-id list for step `NN`.
2. Use `specdev json read <file> '<jq filter>'` with counts and id slices (`.[0:50]`) to narrow scope.
3. Call `specdev json resolve-pointers` with the pointer list from step 2 to validate and get full entry previews.
4. Only fetch full entry content for the specific entries the task requires.

Do not load full spec files into context. Do not paginate via bundler flags — compose from these primitives directly.

---

## 6. Lint envelopes

### 6.1 Error envelope (emitted by lints with `--json`)

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

### 6.2 `specdev guide <code>`

Returns the canonical remediation playbook for an error code. Backed by `tools/specdev_tools/guides/*.yaml` (or equivalent). Single source of truth; `docs/developers/error-codes.md` is generated from this, and `CLAUDE.md` troubleshooting prose is reduced to a pointer.

### 6.3 `specdev json resolve-pointers`

```bash
# Pointer list is read from stdin; no --in flag. --out optional (defaults to stdout).
# --repo-root is required (toolkit root, e.g. ./devspec_toolkit for submodule deployments).
specdev json resolve-pointers --repo-root ./devspec_toolkit [--git-root .] [--out report.json] < pointers.json
cat pointers.json | specdev json resolve-pointers --repo-root ./devspec_toolkit --git-root .
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

### 6.4 Dry-run and schema-check on edits

```bash
specdev json patch <file> <jq-path> <value> [--dry-run] [--against-schema-field <step.field>]
```

The current `json patch/insert/delete` signature is `<file> <jq-path> <value> [--raw]`. `--dry-run` and `--against-schema-field` are **not yet implemented** — they are reserved flags documented here as the intended interface. Until implemented, passing them will produce a "not yet implemented" error.

When implemented: `--dry-run` returns the post-edit JSON without writing to disk. `--against-schema-field <step.field>` pre-checks the value's shape against a named field's schema before submission. Both are agent tools; they do not replace the CLI as the write path.

---

## 7. Forbidden patterns

These are protocol breaks. The orchestrator must detect and recover, not silently accept.

| Pattern | Why forbidden | Recovery |
|---|---|---|
| Agent emits JSON content from a spec file | Hallucination surface; bypasses validation | Discard response; re-prompt with pointer-only instruction |
| Lint envelope reaches outer agent context | Token bloat; envelopes leak | Outcomes compress to `(pointer, reason)`; use `--json` + jq to filter before surfacing |
| Silent partial result (drops misses without reporting) | Hides failure | `unresolved[]` must be non-empty if misses occurred |
| Spec edit applied without a rollback path | No recovery on failure | Stage affected files via git before multi-file edits; restore with `git checkout -- <files>` on non-success exit |
| Direct `Read` on `spec/*.json` files | Bypasses cross-step dependencies and schema awareness | Use `/specdev-context <NN>` or `specdev json read` instead |
