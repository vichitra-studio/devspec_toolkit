# Shared Expectations

Use this document as the authoritative baseline for all prompt-level directives. Individual prompts inherit all rules here and may add step-specific requirements or override named sections. Where a prompt defines a section that overlaps with this document (e.g., Role, Task, Output Rules), the prompt's version takes precedence.

## 1. Path Variables

| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## 2. Schema Authority & Metadata Contract

The schema at `$SCHEMA_DIR/NN_name.schema.json` is the authoritative source for all field definitions, types, required vs optional markers, enum values, patterns, and minItems rules. MUST read the schema before generating output. Do NOT guess field names, types, or valid values — all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

This step's output artifact MUST include every field listed in the schema's `required[]` array. Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them in the prompt.

## 3. Canonical Registry Protocol

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. NEVER use a deprecated canonical without checking `replaced_by` first.

- **Bind**: Map `*_ref` fields to canonical IDs (`cn:<namespace>:<kind>:<slug>`). Resolve aliases via `canon/aliases.json`.
- **Required**: `canonical_refs_used` MUST list every canonical ID referenced by any `*_ref` field. For each `*_ref` in the schema: if the semantic content exists, the ref MUST be populated — not optional.
- **Optional**: `canonical_proposals` for any new term with no registry match; `canonical_conflicts` for ambiguous or contradictory matches.
- **Resolution order**: exact canonical ID → active alias → canonical proposal. If multiple active canonicals match, emit `canonical_conflicts`. Never emit schema fields that invent a new semantic label without a canonical reference or proposal.

## 4. Hardening Protocol

- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, link and canonical closure (every link and every canonical ref names a node or entry that exists), and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## 5. Default Role & Task Framing

> **Applies to**: Steps 00–10, 12–15. Steps 11, 13, 16, 16a, 16b, 16c define their own Role/Task and override this default.

**Role**: You are a senior specification author and validator. Your job is to emit a single JSON artifact for **{{STEP_NAME}}** that is machine-checkable and immediately consumable by CI and generators. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

**Task**:
- **Input context:** previously authored spec artifacts (Charter, Capabilities, Glossary, FRs, etc.) available to you in the workspace; organizational constraints; known IDs for cross-references.
- **Objective:** produce a complete, falsifiable artifact for **{{STEP_NAME}}**.
- **Output type:** one JSON document conforming to the referenced step schema.
- **Determinism:** when unspecified, choose the minimal valid value that preserves falsifiability and traceability.
- **Traceability:** if this step's schema declares link fields (fields marked `x-link`, such as `derives_from`), connect to at least one upstream or downstream artifact.

## 6. Output Rules (Discovery Phase)

> **Applies to**: Steps 00–15. Steps 16–16c have different output rules defined in their own prompts. Note: Steps 11, 13 define their own Role/Task (see Section 5) but still follow these output rules.

1. Write the final JSON artifact to disk, never as a fenced code block in the response. A step that does not exist yet is written as a whole draft file outside `spec/` and created with `specdev step create NN --from <draft>`; a step that exists is edited with `specdev json patch|insert|delete --id <node-id>` (section 10). A file written by hand into `spec/` gets E761 for each of its links until `specdev attest <node-id> --yes`.
2. The JSON must validate against the referenced step schema listed in `Schema Reference`.
3. All IDs must be unique kebab-case strings.
4. Use concrete verbs and measurable outcomes; avoid adjectives that are not testable.
5. Include explicit preconditions, postconditions, and error states where applicable to the schema.
6. Set `owner` to one of the values defined in `schema/core/atoms.schema.json` owner enum.
7. If the schema declares link fields (fields marked `x-link`, such as `derives_from`), include at least one reference to connect artifacts across steps.
8. Do not include any fields outside the schema. `additionalProperties` is false everywhere.
9. A relation between nodes is a link in a link field, never a node id in prose. A mention of another node's id (or of a retired name of it, or of a seed) in a text field is not a link: the graph never sees it, and `spec-check` reports it as E752. Turn a mention that states a relation into the link and take the id out of the text; reword any other mention.
10. A glossary term is used by its label: a term of Step 03 that no node of steps 04 to 15 mentions by its label is reported as E741 (use the label in the text of a node, or delete the term with `specdev json delete --id <term-id>`).

## 7. Seed Order Protocol

> **Applies to**: Any step whose `step_requirements["NN"]` is non-empty in the host `spec/common/seed_manifest.json`.

- Read `spec/common/seed_manifest.json` first. The manifest is authoritative for both routing (which seeds apply to which step, via `step_requirements["NN"]`) and location (the resolved file path, via `seeds[].path`). Do not assume `docs/seed/` or any specific filename.
- Ingest all seeds listed under `step_requirements["NN"]` for this step (resolved via `seeds[].path`, in `global_seed_order` order) before any other context. `global_seed_order` governs read order only; a step with empty or absent `step_requirements[NN]` ingests no seeds — there is no fallback to `global_seed_order`.
- A seed can be routed only to a step whose nodes can link a seed with `derives_from`: step 00, 02 or 02a. A route to any other step, including 16a, 16b, 16c and the key `16`, is reported by `spec-check` as E748. Every later step reads the nodes that those steps distilled from the seed, not the seed itself.
- If a required seed is missing or stale, stop and request it before proceeding.

## 8. Self-Audit Gate Protocol

### 8.1 Self-Audit Gate (input sufficiency)

Each gate item is a pass/fail check on whether upstream inputs are sufficient to proceed. If ALL items pass → enter Emit mode. If ANY item cannot be satisfied → enter Clarify mode: output only short bulleted gap questions, no JSON, no code fences. Stop and wait for user input.

Output quality verification is in the Coverage Closure section — run Coverage Closure AFTER emitting the artifact.

### 8.2 Universal Coverage Closure Checklist

Each prompt's Coverage Closure section contains step-specific rules. In addition, before emitting, always verify:
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.

## 9. Step-Order Policy

- Use a forward-only execution model.
- Use no refinement mode.
- Any accepted change at step N is replayed through the steps below it before merge. The replay is the list of suspect links in the trace lock (`spec/extras/trace.lock.json`): a link is suspect when its target changed after the node that holds the link accepted it. `specdev stale` lists them by step, upward first. Each is read, and then either the holder is edited or the link is accepted with `specdev attest <node-id> --yes`. File-level replay (a changed file for every later step) is retired.

### 9.1 Forward pass across 00-16

When several steps change in one pass, run the steps in order and handle only the slice that reaches the step you are on:

1. Run the steps in waterfall order. Before step NN, `specdev step ready NN` says whether the steps above NN (its declared inputs while NN has no file yet; the steps its nodes link to once it has one) are present and have no pending replay (exit 1 with E773 and the blockers when not).
2. For step NN, only the suspect links its own nodes hold count: `specdev stale --step NN`. Read each, edit the holder if the change affects it, then `specdev attest --step NN --yes` (it works upward first and writes nothing without `--yes`).
3. Suspect links held by later steps show in plain `specdev stale`. Leave them: they are fixed when the pass reaches those steps.
4. The end-of-pass gate is `specdev spec-check`: it reports no suspect link (E763) and no link without an entry (E761).

## 10. Tool Execution

All spec reads and edits MUST go through the `/specdev-context` skill (`.claude/skills/specdev-context/SKILL.md`). Do not `Read` spec files directly. Before composing any new `specdev json read` filter, learn the shape via `specdev json structure` / `json keys` / `json schema` — guessing field names is the dominant failure pattern. If a `json read` call fails, do not retry with another guessed path; drop back to a shape probe.

Flag scope: `--spec-root` and `--git-root` apply to validation/governance commands (`spec-check`, `validate`, `governance-check`). `canon-accept` accepts `--git-root` only (not `--spec-root`). Most `specdev json …` subcommands accept `--repo-root` only; the CLI silently strips `--spec-root`/`--git-root` if passed. Exceptions: `specdev json resolve-pointers` legitimately accepts `--git-root` to anchor relative file paths, and the id forms `specdev json patch|insert|delete --id <node-id>` and `specdev json insert --step NN` accept all three flags (and `--json`).

After generating or modifying a spec artifact, run the unified check command. It runs schema validation, the toolkit version, quality, canonical and hallucination lints, canonical integrity, seed, fixtures and dependency-order lints, the `graph` check (links), computed fields, records, the registry and hardcoded-seed checks, glossary drift, the trace lock, the eight graph role checks (`no-dangling`, `term-use`, `verifier-rules`, `cross-cutting`, `refinement`, `scaffold-paths`, `seed-routes`, `prose-ids`), the step 14 `milestone-numbers` check and the open-items check:
```bash
specdev spec-check <spec_dir> --repo-root ./devspec_toolkit
```

With `--step NN` (written as in the file name: `05`, `02a`) it is the gate of step NN instead: it blocks on the step's own errors and on new errors of earlier steps, lists a finding that a later step owns as PENDING (not blocking), and leaves a finding of the merge or release gate as GATE-OWNED. `UPSTREAM DEBT (N)` counts the errors of earlier steps that the baseline (the tree the gate compares with, `--base-ref`) already had: they do not block step NN and are fixed at their own step (run: `spec-check spec --step 14` on the worked example printed `UPSTREAM DEBT (11) 07: 1, 08: 5, 12: 5`; `--detail all` lists them). `specdev coverage` shows how the obligations are linked (`--by fr` for the view per FR) and `specdev trace <id> --up|--down` the lineage of one node; neither is a gate.

To write a new step artifact from a draft file: `specdev step create NN --from <draft>` (ids of sub-items may be left out; `--dry-run` prints the report and writes nothing). It writes the lock entry of every link it writes.

`spec-check` includes the `graph` check: a link that names no node or a node of the wrong kind, a link cycle within one step, and an id defined in two places are reported as E700 to E704. A single-file `validate` does not report a job or task cycle, an unknown job in `depends_on`, or an id defined in two files; run `spec-check` for those.

For submodule deployments, add `--spec-root ./spec --git-root .` to resolve seed paths correctly.

The attest step is needed after a link was written by path or by hand (E761) and after an edit to a node that other nodes link to (E763); the id forms (`json patch|insert|delete --id`, `json insert --step`) and `step create` write the lock entry of each link themselves, and `attest` then says `nothing to attest`. The step is `specdev attest <node-id> --yes` for each node that E761 or E763 names, `specdev attest --prune` after a link was removed, then `spec-check` again (`docs/developers/error-codes.md`, "The attest step" under "Graph Role Checks").

For single-file quick validation during iterative editing:
```bash
specdev validate <path_to_artifact> --repo-root ./devspec_toolkit
```

Step-specific additional commands (e.g., `invariants-check`, `fixtures-lint`, `governance-check`) are listed in each prompt's Tool Execution section.

## 11. Conflict Resolution Protocol

When two upstream artifacts contradict each other:
1. Identify the conflict explicitly in the Context Ledger.
2. Apply precedence: seed > charter > capabilities > architecture > delivery > glossary.
3. If same-level artifacts conflict, add a Gap Question — do not guess.
4. Never silently resolve a conflict.

## 12. Context Ledger

Before emitting output, build a private synthesis ledger (Context Ledger) containing all inputs ingested, decisions made, and evidence chains. Do not output it. It serves as internal audit trail for completeness closure and self-audit scoring. Each prompt's Operating Flow section specifies what the Context Ledger should contain for that step.

## 13. Namespace Resolution

- `cn:core:*` — reserved for universal, toolkit-wide vocabulary: environment (dev, ci, staging, prod), severity levels. These are defined in the toolkit's own `canon/manifest.json` or must be created in the project's `spec/canon/kinds/` if not present.
- `cn:project:*` — project-specific canonical entries: custom capabilities, roles, domain terms, dependencies. Created via `specdev canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit` from Step 03 glossary (see the "Canon management" section in CLAUDE.md).
- Before emitting a `*_ref` field with a `cn:core:*` ID, verify the entry exists in either the toolkit's `canon/manifest.json` or the project's `spec/canon/manifest.json`. If missing, create it in the project's `spec/canon/kinds/{kind}.json` and manifest.
- For submodule deployments: add `--namespace cn:project: --owner product` to `canon-accept` to scope entries to project canon. Use `--git-root .` when running from the host repo.

## 14. Fixture Traceability

- Fixture binding is authored in Step 08 via `fixtures[].verifies`, which names acceptance criteria, APIs, invariants or NFRs (not FRs). A fixture carries `verifies` or `removes`. Step 04 acceptance criteria carry no fixture reference; the inverse direction is the single source of truth.
- Step 14 (`task.acceptance_criteria[].verified_by`) binds a roadmap acceptance criterion to the fixtures, jobs or rules that verify it. Step 16 plan items carry no fixture reference. When this step's schema includes `verified_by`, a fixture value MUST equal a `fixture_id` from `spec/08_fixtures.json` exactly.
- Before omitting `verified_by` in Step 14, check `spec/08_fixtures.json` for a matching fixture by what it verifies. Missing fixtures are coverage gaps, not permission to omit.

## 15. Cross-Step Relationships

Cross-step relationships (dependencies, downstream consumers) are derivable from `step_order.json` DAG. Do not restate them in prompts. Use `specdev prompt-context NN` to inspect them at runtime.

## 16. Documentation Resources

Use these resources to orient yourself within the toolkit before emitting output:

- **`docs/README.md`** — index of all documentation; start here to find the right guide.
- **`docs/`** — organized into subdirectories: `developers/` (getting started, `reference.md`, `error-codes.md` and `workflows/`, the how-to guides), `ops/` (operational runbooks), `architecture/` (design records), `agents/` (agent manifests and protocols) and `prompts/` (this file).
- **`tools/step_docs.json`** — machine-readable mapping from step name to its documentation files; use this to locate step-specific guides programmatically.
- **Step guides** — human-readable guidance for each step is inline in the step's prompt file and in the guides that step_docs.json lists for it (the authoritative list).
