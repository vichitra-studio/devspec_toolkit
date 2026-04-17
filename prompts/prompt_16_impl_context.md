# Step 16 · Trinity Anchor (`vc:16-anchor`)

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 16` to see downstream consumers.

## Purpose
Create or update the **Trinity Anchor** at `spec/16_impl_context.json`. The anchor is the **union/root scope declaration** for a multi-milestone implementation cycle. It is validated against `vc:16-anchor` — a schema distinct from the per-milestone `vc:16-impl-context` used by 16a/16b/16c. The anchor's job is scope + cross-milestone drift detection; it does **not** carry per-FR checklist detail (that lives in each 16a plan).

The anchor must:
1. Declare the full scope spanning every milestone in this cycle (`plan.summary`).
2. Carry forward unresolved decisions and ambiguities across Trinity cycles (`plan.ambiguities`).
3. Record drift checks performed across milestone cycles (`plan.drift`).
4. Register which milestones own which FRs/APIs and under which checklist ID namespace (`plan.milestone_index`).

## When To Use This Prompt
- You are starting a new Trinity cycle and need the root anchor before any 16a milestone plan.
- You are regenerating the anchor after scope changes (new milestones, FRs moved between milestones).

## When NOT To Use This Prompt
- You are authoring a per-milestone **implementation plan** (16a) — use `prompt_16a_impl_planner.md` against `spec/impl_context/<milestone>_plan.json` (schema `vc:16-impl-context`).
- You are recording execution evidence (16b) or review verdicts (16c) — those write into the same milestone context file.

# Role
You are a senior software architect producing the Step 16 **Trinity Anchor**.
Generate a **machine-checkable JSON artifact** conforming to `vc:16-anchor` that captures scope, carried-forward ambiguities, drift checks, and the milestone ownership index. Do not emit any fields that belong to the milestone context (`checklist`, `execution`, `review`, `docs_impact`, `review_requirements`, etc.) — the anchor schema forbids them.

### Extraction Intent

#### Primary Sources (directly consumed)
- **14_roadmap.json**: milestone identifiers, statuses, and fr_refs — the authoritative source for which milestones this anchor governs and which FR/API IDs each milestone owns; drives `plan.milestone_index[]` directly
- **04_fr_list.json**: functional requirement IDs and capability mappings — validates that every FR ID listed in `milestone_index[].fr_refs` resolves to a real requirement and informs scope boundaries
- **05_interface_contracts.json**: API contract identifiers and endpoint boundaries — validates API IDs referenced in `milestone_index[].fr_refs`

#### Reference Sources (context only)
- **08_fixtures.json**: test fixture identifiers used to sanity-check that in-scope FRs have a path to verifiable tests
- **09_impl_plan.json**: milestone definitions and tech stack constraints that determine how many milestones this anchor should index
- **11_redteam.json**: threat identifiers that inform scope_out decisions when the threat surface argues for excluding capabilities this cycle
- **12_ci_gates.json**: CI pipeline definitions that establish the verification contract milestone plans will reference
- **15_scaffold.json**: generated file structure that grounds per-milestone `target_file_patterns` in 16a plans

# Operating Flow (MANDATORY)
1. **Context Review**: Ingest `14_roadmap.json` (milestone list, fr_refs, status), `04_fr_list.json` (FR IDs), `05_interface_contracts.json` (API IDs). Load any existing `spec/impl_context/*.json` milestone plans to understand what is already under way.
2. **Scope**: Derive `plan.summary.functional_summary`, `scope_in`, `scope_out` spanning **every milestone in this cycle**. The anchor is the union of milestone scope — not a milestone plan itself.
3. **Milestone Index**: For every milestone in `14_roadmap.json` that participates in this cycle, emit one `plan.milestone_index[]` entry with `milestone_id`, `context_path`, `status`, `fr_refs`, `checklist_id_prefix`, and a one-line `summary`. Drop a milestone from the index only when it has been removed from the roadmap entirely.
4. **Ambiguities**: Carry forward unresolved ambiguities from prior Trinity cycles and surface any new cross-milestone decisions that are not yet resolved.
5. **Drift**: Record drift checks performed in this session and previous cycles in `plan.drift.checks` as short, dated human-readable strings (e.g., `"Verified ms-auth scope_in does not overlap anchor scope_out (2026-04-14)"`). May be `[]` on a fresh anchor.
6. **Emit**: Write the JSON artifact to `spec/16_impl_context.json`. The schema forbids extra fields at both the root and `plan` level — only emit the fields in the Output Contract.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode and emit gap questions only — do not write the artifact.
- `spec/14_roadmap.json` is present and contains at least one milestone.
- `spec/04_fr_list.json` is present and contains at least one `functional_requirements` entry.
- `spec/05_interface_contracts.json` is present and contains at least one `apis` entry.
- Every `milestone_id` you plan to list in `plan.milestone_index` exists in `14_roadmap.json`.
- Every FR/API ID in any `plan.milestone_index[].fr_refs` resolves to a real ID in Step 04 or Step 05.

## Coverage Closure
Before emitting, verify:
- Every milestone in `14_roadmap.json` appears in `plan.milestone_index`, OR is explicitly listed in `scope_out` with a rationale in `plan.ambiguities`. The anchor is the cumulative ledger — `done` milestones must remain indexed so traceability stays enforceable.
- No FR/API ID appears in `fr_refs` of two milestones whose status is not `done` — a delivered ID may be revisited, but two active milestones cannot own the same FR simultaneously.
- No entry in `plan.summary.scope_in` also appears in `plan.summary.scope_out` — and neither contradicts any milestone's scope.
- Each `checklist_id_prefix` is unique across `plan.milestone_index` — 16a plans allocate checklist IDs from this namespace.
- All `canonical_refs_used` entries reference valid IDs from `canon/manifest.json`.

## Negative Constraints
1. **NEVER** emit `plan.spec_alignment`, `plan.review_requirements`, `plan.docs_impact`, `plan.solution`, `plan.context`, `plan.security`, `plan.delivery`, `plan.docs`, `plan.coverage_status`, or `plan.scope_validation` — these belong on 16a/16b/16c milestone contexts, not on the anchor.
2. **NEVER** emit an `execution` or `review` top-level section.
3. **NEVER** emit a top-level `milestone_ref` — the anchor spans all milestones.
4. **NEVER** author a per-FR checklist on the anchor — that detail lives in each 16a plan.
5. **NEVER** set `artifact_role` to anything other than `"anchor"`.
6. **NEVER** emit placeholder or empty-string values where content is required — consult the schema for minimum lengths.
7. **NEVER** place `16_impl_context.json` inside `spec/impl_context/`. The anchor lives at `spec/16_impl_context.json` at the spec directory root. Files in `spec/impl_context/` are milestone plans.

# Heuristics For Completeness
1. **Every `milestone_index[].milestone_id` exists in `14_roadmap.json`** — invent no IDs.
2. **Every `fr_refs` ID resolves in Step 04 (FRs) or Step 05 (APIs)** — invent no IDs.
3. **`scope_in` and `scope_out` are disjoint** on the anchor, and consistent with every milestone's own scope.
4. **`checklist_id_prefix` values are pairwise unique** across milestones.
5. **`ambiguities[]` carries forward** unresolved items from prior cycles — do not silently drop them.
6. **`drift.checks[]` is not a TODO list** — record checks that were actually performed, with a date if possible.

# Best Practices
1. **Keep the anchor small.** A well-formed anchor fits on one screen — the schema enforces this by forbidding checklist and implementation detail.
2. **Update the anchor whenever a milestone is added, completed, or scope shifts** — it is the cross-cycle record.
3. **Use concrete scope strings** (`"login-endpoint"`, `"jwt-token-validation"`) not vague labels (`"auth"`).
4. **Prefix checklist IDs by milestone** in the 16a plans (via `checklist_id_prefix`) so cross-milestone ID collisions are trivially avoided.
5. **When resolving an ambiguity, set its `status` to `resolved`** rather than removing the entry — preserves the decision log.

# Common Pitfalls
- **Schema rejection from extra fields**: Emitting `checklist`, `review_requirements`, or `docs_impact` on the anchor. *Fix*: Author only `plan.summary`, `plan.ambiguities`, `plan.drift`, `plan.milestone_index`.
- **Scope contradiction**: A milestone claims something the anchor excludes, or two active milestones claim the same FR. *Fix*: Reconcile scope and ownership before emitting.
- **Namespace collision**: Two milestones sharing the same `checklist_id_prefix`. *Fix*: Assign distinct prefixes (e.g., `AUTH`, `SESSION`, `BILLING`).
- **Stale drift log**: Milestones are indexed but no drift checks recorded. *Fix*: Record at least one check string per Trinity cycle.

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
      "scope_out": ["oauth-flows", "mfa", "third-party-sso"]
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
