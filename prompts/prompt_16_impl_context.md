# Step 16 · Trinity Anchor (`vc:16-anchor`)

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 16` to see downstream consumers.

## Purpose
Create or update the **Trinity Anchor** at `spec/16_impl_context.json`. The anchor is the **union/root scope declaration** for a multi-milestone implementation cycle. It is validated against `vc:16-anchor` — a schema distinct from the per-milestone `vc:16-impl-context` used by 16a/16b/16c. The anchor's job is scope + cross-milestone drift detection; it does **not** carry per-FR checklist detail (that lives in each 16a plan).

The anchor must:
1. Declare the full scope spanning all active milestones (`plan.summary`).
2. Carry forward unresolved decisions and ambiguities across Trinity cycles (`plan.ambiguities`).
3. Record drift checks performed across milestone cycles (`plan.drift`).
4. Register which milestones own which FRs/APIs and under which checklist ID namespace (`plan.milestone_index`).

## When To Use This Prompt
- You are starting a new Trinity cycle and need the root anchor before any 16a milestone plan.
- You are regenerating the anchor after scope changes (new milestones, FRs moved between milestones).
- You are aligning a host repo to a toolkit version that expects the `vc:16-anchor` contract.

## When NOT To Use This Prompt
- You are authoring a per-milestone **implementation plan** (16a) — use `prompt_16a_impl_planner.md` against `spec/impl_context/<milestone>_plan.json` (schema `vc:16-impl-context`).
- You are recording execution evidence (16b) or review verdicts (16c) — those write into the same milestone context file.

# Role
You are a senior software architect producing the Step 16 **Trinity Anchor**.
Generate a **machine-checkable JSON artifact** conforming to `vc:16-anchor` that captures scope, carried-forward ambiguities, drift checks, and the milestone ownership index. Do not emit any fields that belong to the milestone context (`checklist`, `execution`, `review`, `docs_impact`, `review_requirements`, etc.) — the anchor schema forbids them via `unevaluatedProperties: false`.

### Extraction Intent

#### Primary Sources (directly consumed)
- **14_roadmap.json**: milestone identifiers, statuses, and fr_refs — the authoritative source for which milestones this anchor governs and which FR/API IDs each milestone owns; drives `plan.milestone_index[]` directly
- **04_fr_list.json**: functional requirement IDs and capability mappings — validates that every FR ID listed in `milestone_index[].fr_refs` resolves to a real requirement and informs `plan.summary.scope_in`/`scope_out` boundaries
- **05_interface_contracts.json**: API contract identifiers and endpoint boundaries — validates API IDs referenced in `milestone_index[].fr_refs` and anchors the scope declaration against the public surface area

#### Reference Sources (context only)
- **00_charter.json**: product vision, success criteria, and stakeholder constraints that bound the execution scope and inform `plan.summary.scope_in`/`scope_out` decisions at the anchor level
- **01_capabilities.json**: capability identifiers and descriptions used to ground scope strings and to sanity-check that milestone fr_refs roll up into declared product capabilities
- **02_system_sketch.json**: component boundaries and trust zones; component topology, integration boundaries, and data flow paths that inform the anchor's scope boundary decisions across milestones
- **02a_delivery_baseline.json**: environment definitions, deployment targets, and infrastructure constraints that inform what a cross-milestone rollout must respect in scope_in/scope_out statements
- **03_glossary.json**: canonical term definitions and domain vocabulary enforced in the anchor's `functional_summary` text and ambiguity descriptions to prevent term drift across cycles
- **06_invariants.json**: system invariants and enforcement conditions that bound what the anchor may declare as scope_in without violating cross-cutting contracts
- **07_nfrs.json**: NFR thresholds and availability targets that bound the anchor scope — NFR breaches disqualify certain implementation paths before milestones are cut
- **08_fixtures.json**: test fixture identifiers, target bindings, and expected outcomes used to sanity-check that in-scope FRs have a path to verifiable tests at the milestone level
- **09_impl_plan.json**: milestone definitions, task decompositions, and tech stack constraints that determine how many milestones this anchor should index and what their tentative statuses are
- **10_governance.json**: commit message patterns, PR rules, and approval workflows that constrain how cross-milestone changes must be committed and reviewed during the cycle
- **11_redteam.json**: threat identifiers, attack vectors, and severity ratings that inform anchor-level scope_out decisions when the threat surface argues for excluding certain capabilities this cycle
- **12_ci_gates.json**: CI pipeline stage definitions, gate conditions, and required checks that establish the verification contract milestone plans will ultimately reference via their own test_commands
- **13_extension_manifest.json**: extension point declarations and plugin interface contracts that inform scope boundaries when extensibility concerns cut across multiple milestones
- **13a_completeness_assessment.json**: coverage gap analysis, missing spec items, and completeness scores used to inform scope boundary decisions before committing to a milestone index
- **15_scaffold.json**: generated file structure, directory layout, and scaffold templates that ground the anchor's optional `target_file_patterns` when a cross-milestone file boundary is declared

# Operating Flow (MANDATORY)
1. **Context Review**: Ingest `14_roadmap.json` (milestone list, fr_refs, status), `04_fr_list.json` (FR IDs), `05_interface_contracts.json` (API IDs). Load any existing `spec/impl_context/*.json` milestone plans to understand what is already under way.
2. **Scope**: Derive `plan.summary.functional_summary`, `scope_in`, `scope_out` spanning **all** active and planned milestones in this cycle. The anchor is the union of milestone scope — not a milestone plan itself.
3. **Milestone Index**: For each milestone in `14_roadmap.json` that is active, done, or planned in this cycle, emit one `plan.milestone_index[]` entry with `milestone_id`, `context_path` (pointing at the 16a plan file), `status`, `fr_refs`, `checklist_id_prefix` (SCREAMING_SNAKE namespace the 16a plan will use for its checklist IDs), and a one-line `summary`.
4. **Ambiguities**: Carry forward unresolved ambiguities from prior Trinity cycles and surface any new cross-milestone decisions that are not yet resolved. Each entry: `id`, `description`, `severity` (`low`/`medium`/`high`/`critical`), optional `impact`, optional `status` (`resolved`/`tracking`/`deferred`/`blocked`), optional `status_ref` (canonical status ref).
5. **Drift**: Record drift checks performed in this session and previous cycles in `plan.drift.checks` as short, dated human-readable strings (e.g., `"Verified ms-auth scope_in does not overlap anchor scope_out (2026-04-14)"`). May be `[]` on a fresh anchor.
6. **Emit**: Write the JSON artifact to `spec/16_impl_context.json`. Do not write any fields not listed in the Output Contract — the schema uses `unevaluatedProperties: false` at the artifact root and `additionalProperties: false` on `plan`, so extraneous keys at either level fail validation.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode and emit gap questions only — do not write the artifact.
- `spec/14_roadmap.json` is present and contains at least one milestone.
- `spec/04_fr_list.json` is present and contains at least one `functional_requirements` entry.
- `spec/05_interface_contracts.json` is present and contains at least one `apis` entry.
- Every `milestone_id` you plan to list in `plan.milestone_index` exists in `14_roadmap.json`.
- Every FR/API ID in any `plan.milestone_index[].fr_refs` resolves to a real ID in Step 04 or Step 05.

## Coverage Closure
Before emitting, verify:
- Every active milestone in `14_roadmap.json` appears in `plan.milestone_index` (or is explicitly listed in `scope_out` with a rationale carried in `plan.ambiguities`).
- No FR/API ID appears in `fr_refs` of two milestones whose `status` is **not** `done` — `pending`, `in_progress`, and `deferred` all participate in the conflict check (this triggers **E308** FR ownership conflict). `done` milestones are exempt because the ID has been delivered and may legitimately be revisited in a follow-on milestone.
- No entry in `plan.summary.scope_in` also appears in `plan.summary.scope_out` — and neither contradicts any milestone's `scope_in`/`scope_out` under `spec/impl_context/*.json` (triggers **E308** scope drift).
- Each `checklist_id_prefix` is unique across `plan.milestone_index` — 16a plans will allocate their checklist IDs from this namespace; duplicates collide and trigger **E309**.
- All `canonical_refs_used` entries reference valid IDs from `canon/manifest.json`.

## Negative Constraints
1. **NEVER** emit `plan.spec_alignment`, `plan.review_requirements`, `plan.docs_impact`, `plan.solution`, `plan.context`, `plan.security`, `plan.delivery`, `plan.docs`, `plan.coverage_status`, or `plan.scope_validation` — these belong on 16a/16b/16c milestone contexts, not on the anchor.
2. **NEVER** emit an `execution` or `review` top-level section — the anchor schema forbids them (`unevaluatedProperties: false`).
3. **NEVER** emit a top-level `milestone_ref` — the anchor spans all milestones and has no single owning milestone. The schema's `unevaluatedProperties: false` rejects it.
4. **NEVER** author a per-FR checklist on the anchor — per-milestone checklist detail lives in each 16a plan.
5. **NEVER** set `artifact_role` to anything other than `"anchor"` — the value is a JSON Schema `const`.
6. **NEVER** emit placeholder or empty-string values where content is required (e.g., `functional_summary` must be ≥20 chars; each `drift.checks[]` string must be ≥5 chars; each `milestone_index[].summary` must be ≥10 chars).
7. **NEVER** place `16_impl_context.json` inside `spec/impl_context/`. The anchor lives at `spec/16_impl_context.json` at the spec directory root. Files in `spec/impl_context/` are milestone plans (`vc:16-impl-context`). If an anchor is misfiled there, the content-based dispatch demotes it and emits **W586** ANCHOR_VALIDATOR_WRONG_ARTIFACT.

# Field Definitions & Rules (MANDATORY)
**Crucial**: Use the following exact definitions to ensure compliance with `vc:16-anchor`:

## 1. `artifact_role` (Required)
*   Always the literal string `"anchor"`. This is a JSON Schema `const` — any other value fails validation. Routing (`validate.py`) and `_is_anchor()` read this field to dispatch to the anchor validator.

## 2. `plan.summary` (Required)
Scope declaration spanning all milestones in this cycle. `additionalProperties: false` — only the four fields below.
*   `functional_summary` *(required, string, minLength 20)*: 1–3 sentences stating the capability delivered across all milestones, primary actors, and hard constraints. Example: *"Implements JWT authentication and session management across two milestones. Covers token issuance, validation, revocation. Excludes OAuth flows and third-party SSO."*
*   `scope_in` *(required, array of strings, each minLength 3)*: concrete capabilities, endpoints, or system boundaries included. E308 uses this to detect milestone↔anchor contradictions.
*   `scope_out` *(required, array of strings, each minLength 3)*: concrete items explicitly excluded. A milestone `scope_in` value that appears here triggers E308.
*   `target_file_patterns` *(optional, array of strings)*: glob patterns for files touched across all milestones. The anchor may leave this empty or broad; each 16a plan carries its own tighter patterns.

## 3. `plan.ambiguities` (Required, can be `[]`)
Accumulated unresolved decisions carried across Trinity cycles. Each item (`additionalProperties: false`):
*   `id` *(required)*: kebab-case identifier.
*   `description` *(required, string)*: what is unclear and what decision is needed.
*   `severity` *(required)*: `low` | `medium` | `high` | `critical` (from `vc:core:atoms#severityLevel`). **Do not use `blocking`/`non_blocking`** — those are milestone-plan values, not anchor severities.
*   `impact` *(optional, array of strings)*: affected areas or milestones.
*   `status` *(optional)*: `resolved` | `tracking` | `deferred` | `blocked`.
*   `status_ref` *(optional)*: canonical ref object `{ id, kind: "status" }`.

## 4. `plan.drift` (Required)
Drift monitoring log. `additionalProperties: false`.
*   `checks` *(required, array of strings, each minLength 5, may be empty)*: one short human-readable string per drift check performed or scheduled. Example: `"Verified ms-auth scope_in does not overlap anchor scope_out (2026-04-14)"`. **Not objects** — the anchor records what was checked, not how; the executable check lives in `step_16_anchor.py` (E308/E309).

## 5. `plan.milestone_index` (Required, can be `[]`)
Registry of every milestone this anchor governs. Used by validators to detect cross-milestone FR ownership conflicts (E308) and checklist ID collisions (E309). Each item (`additionalProperties: false`):
*   `milestone_id` *(required, kebab-case)*: must match a `milestone_id` in `14_roadmap.json`.
*   `context_path` *(required, string)*: relative path to the milestone's 16a plan (e.g. `"spec/impl_context/ms_auth_plan.json"`).
*   `status` *(required)*: `pending` | `in_progress` | `done` | `deferred` (the shared `vc:core:atoms#milestoneStatus` enum — same as `14_roadmap.json`). Only `done` milestones are exempt from FR/API ownership conflict detection (the ID was delivered and may be revisited in a follow-on cycle); pending, in_progress, and deferred all participate.
*   `fr_refs` *(required, array of kebabIds, `uniqueItems: true`)*: FR and API IDs this milestone owns. Duplicates within the array are a schema error. Two non-done milestones claiming the same ID triggers E308.
*   `checklist_id_prefix` *(required, pattern `^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$`, max 20 chars)*: SCREAMING_SNAKE namespace for the 16a plan's checklist IDs (e.g. `AUTH`, `PAYMENT`, `USER_MGMT`). Trailing underscores are rejected to prevent double-underscored IDs. Must be unique across `milestone_index` — duplicates trigger E309 immediately at anchor authoring time, before the colliding 16a plans are even written.
*   `summary` *(required, string, minLength 10)*: one-line status (e.g. *"Auth token issuance — 3/5 items verified, CI green"*).

# Heuristics For Completeness
1. **Every `milestone_index[].milestone_id` exists in `14_roadmap.json`** — invent no IDs.
2. **Every `fr_refs` ID resolves in Step 04 (FRs) or Step 05 (APIs)** — invent no IDs.
3. **`scope_in` and `scope_out` are disjoint** on the anchor, and consistent with every milestone's own `scope_in`/`scope_out`.
4. **`checklist_id_prefix` values are pairwise unique** across milestones.
5. **`ambiguities[]` carries forward** unresolved items from prior cycles — do not silently drop them.
6. **`drift.checks[]` is not a TODO list** — record checks that were actually performed, with a date if possible.

# Best Practices
1. **Keep the anchor small.** A well-formed anchor fits on one screen — the schema enforces this by forbidding checklist and implementation detail. If you feel the urge to add fields, you are conflating the anchor with a 16a plan.
2. **Update the anchor whenever a milestone is added, completed, or scope shifts** — it is the cross-cycle record.
3. **Use concrete scope strings** (`"login-endpoint"`, `"jwt-token-validation"`) not vague labels (`"auth"`).
4. **Prefix checklist IDs by milestone** in the 16a plans (via `checklist_id_prefix`) so E309 collision detection is trivially satisfied.
5. **When deleting an ambiguity, set its `status` to `resolved`** rather than removing the entry — preserves the cross-cycle decision log.

# Failure Modes (Pitfalls)
*   **Schema rejection from extra fields**: Emitting `checklist`, `review_requirements`, or `docs_impact` on the anchor. *Fix*: Author only the four fields `plan.summary`, `plan.ambiguities`, `plan.drift`, `plan.milestone_index`.
*   **FR/API ownership conflict (E308)**: Two non-done milestones both listing the same FR or API in `fr_refs`. *Fix*: Move the ID to one milestone; mark the other `done` if already delivered, or `deferred` if postponed.
*   **Checklist namespace collision (E309)**: Two `milestone_index` entries using the same `checklist_id_prefix`. *Fix*: Assign distinct prefixes per milestone (e.g. `AUTH`, `SESSION`, `BILLING`).
*   **Cross-milestone checklist drift (E309)**: Two milestone-plan files in `spec/impl_context/` allocate the same checklist `id` to different `spec_ref.id` values. *Fix*: Use distinct `checklist_id_prefix` namespaces (the anchor's job to enforce) so the colliding IDs cannot occur.
*   **Scope drift (E308)**: A milestone's `scope_in` contains a string in the anchor's `scope_out`, or vice versa. *Fix*: Decide whether the item is in or out, update both places to agree.
*   **Stale drift log (W587)**: `milestone_index` is non-empty but `drift.checks` is empty. *Fix*: Record at least one drift check string per Trinity cycle (e.g. `"Verified <milestone> scope alignment (<date>)"`) — the anchor's load-bearing job is monitoring drift, not just listing milestones.
*   **Unreadable milestone (W588)**: A `*.json` file in `impl_context/` cannot be parsed and was skipped from drift detection. *Fix*: Repair or remove the offending file — it contributes nothing to E308/E309 while broken.
*   **Wrong severity enum**: Using `blocking`/`non_blocking` in `ambiguities[].severity`. *Fix*: Use `low`/`medium`/`high`/`critical`.
*   **Wrong milestone status enum**: Using `active`/`planned` in `milestone_index[].status`. *Fix*: Use `pending`/`in_progress`/`done`/`deferred` — the same enum `14_roadmap.json` uses.
*   **Drift checks as objects**: Emitting `{target, method, schedule, ...}` inside `drift.checks`. *Fix*: Each check is a short human-readable string.
*   **JSON dumps**: Printing the JSON in chat. *Fix*: Only write the file.

# Clarification Questions
- "Which milestones from `14_roadmap.json` should this anchor cover in the current cycle?"
- "Are any previously-resolved ambiguities now open again (e.g., due to scope change)?"
- "What `checklist_id_prefix` should each milestone use? (Must be unique, SCREAMING_SNAKE, ≤20 chars.)"

# Schema Reference
- Schema URI: vc:16-anchor
- Schema File: schema/16_anchor.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:16-anchor",
  "id": "anchor-v1",
  "owner": "api",
  "created_at": "2026-02-08T00:00:00Z",
  "artifact_role": "anchor",
  "canonical_refs_used": [],
  "plan": {
    "summary": {
      "functional_summary": "Implement Core Authentication flow — login, logout, and session management across two milestones.",
      "scope_in": ["login-endpoint", "logout-endpoint", "session-management"],
      "scope_out": ["oauth-flows", "mfa", "third-party-sso"],
      "target_file_patterns": ["src/auth/*.py", "tests/auth/*.py"]
    },
    "ambiguities": [
      {
        "id": "amb-token-ttl",
        "description": "JWT token TTL not confirmed by security team — 24h vs 8h options remain open.",
        "severity": "medium",
        "status": "tracking"
      }
    ],
    "drift": {
      "checks": [
        "Verified ms-auth scope_in does not overlap anchor scope_out (2026-02-10)",
        "Verified ms-session fr_refs do not conflict with ms-auth fr_refs (2026-02-12)"
      ]
    },
    "milestone_index": [
      {
        "milestone_id": "ms-auth",
        "context_path": "spec/impl_context/ms_auth_plan.json",
        "status": "done",
        "fr_refs": ["fr-user-login", "fr-token-refresh"],
        "checklist_id_prefix": "AUTH",
        "summary": "Auth token issuance — all 4 checklist items verified, CI green"
      },
      {
        "milestone_id": "ms-session",
        "context_path": "spec/impl_context/ms_session_plan.json",
        "status": "in_progress",
        "fr_refs": ["fr-session-create", "fr-session-revoke"],
        "checklist_id_prefix": "SESSION",
        "summary": "Session management — 2/4 checklist items in progress"
      }
    ]
  }
}
```

