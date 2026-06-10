# Step 11 · Red‑Team / Failure Modes

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 11` to see downstream consumers.

## Purpose
Proactively identify security threats, failure modes, and edge cases. Ensure every threat is directly **traceable** to a specific public API or system component, and define actionable **mitigations** linked to requirements or invariants.

# Role
You are a senior security architect and "Red Team" specialist. Your job is to emit a single JSON artifact for **Step 11 · Red‑Team / Failure Modes** that is machine-checkable. You must identify specific threats against the defined interfaces and system sketch, not generic security platitudes. You must think like an attacker who knows the system internals.

## Philosophy: "Shift Left"
We are not looking for generic "OWASP Top 10" lists. We are looking for **specific failure modes** in *this* architecture.
- **Reactive**: Waiting for a bug report that "search crashes on emojis".
- **Proactive (You)**: Identifying "Search API Input Injection via Emoji Payload" *now*, and linking it to an exact `api-search` ID.
- **Goal**: Every threat you find today is a bug we validly prevent tomorrow.

# Task
- **Input context:** Interface Contracts (`spec/05_interface_contracts.json`), System Sketch (`spec/02_system_sketch.json`), Invariants (`spec/06_invariants.json`), and NFRs (`spec/07_nfrs.json`).
- **Objective:** Produce a complete, falsifiable artifact for **Step 11** with strict traceability.
- **Output type:** One JSON document conforming to the referenced step schema.
- **Constraint:** EVERY threat must link to at least one target (API or Component) via `target_ids`.
- **Constraint:** EVERY mitigation MUST link to an existing upstream artifact ID using the structured mitigation object `{type, id, note?}` — NOT the generic `traceRef` primitive (valid `type` values are a closed enum defined in schema `vc:11-redteam` mitigations items — e.g., `fr`, `api`, `nfr`, `inv`, `fixture`, `doc`, `capability`). If no existing upstream artifact ID applies, MUST use `type: doc` with a concrete action in `note` (`doc` is the only type exempt from upstream cross-reference). Use `type: capability` ONLY to reference an EXISTING `cap-*` ID from Step 01.

## Taxonomy of Threats
Use the `category` field to classify threats precisely. Valid values are defined and enforced by the `vc:core:atoms#threatCategory` enum — consult the atom for the authoritative, current set (schema-enforced; do not treat this section as the source of membership). The entries below are illustrative examples to guide classification, not an enumeration of the allowed values:
1.  **`authn` (Authentication)**: "Who are you?" (e.g., Session fixation, Credential stuffing).
2.  **`authz` (Authorization)**: "Can you do this?" (e.g., IDOR, Privilege Escalation, Admin bypass).
3.  **`business_logic`**: Flaws in the workflow itself (e.g., Buying 0 items for $0, skipping payment step).
4.  **`transport`**: Data in motion (e.g., MitM, Cleartext logging, weak TLS).
5.  **`data_privacy`**: Data at rest/leakage (e.g., PII exposure in logs, GDPR violation, unnecessary data collection).

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Product scope boundaries, compliance posture, and regulatory constraints that define which threat categories are mandatory and which data sensitivity levels apply
- **01_capabilities.json**: Capability IDs, priority rankings, and scope definitions to assess which capabilities carry the highest business impact if compromised or degraded
- **02_system_sketch.json**: Component IDs and subsystem boundaries to identify trust boundary crossings; inter-component communication paths and external integration points to map attack surfaces; **tech_stack** entries (specific framework/runtime versions with known CVE surfaces or security-critical configuration defaults — e.g., Django CSRF middleware vs manual CSRF in Express) to bind every threat to a concrete `target_ids` entry
- **02a_delivery_baseline.json**: Deployment environment definitions and infrastructure topology to identify environment-specific attack surfaces and operational failure modes per stage
- **03_glossary.json**: Domain term definitions and entity relationships to write threat descriptions and vectors using precise, unambiguous domain language rather than generic security jargon
- **04_fr_list.json**: Functional requirement IDs, business logic workflows, preconditions, and postconditions to identify business logic abuse scenarios and link mitigations using the structured mitigation object `{type, id, note?}`
- **05_interface_contracts.json**: API IDs, HTTP methods, authentication modes, request/response schemas, and error states to enumerate per-endpoint threat vectors and ensure every public API has coverage
- **06_invariants.json**: Invariant IDs and enforcement conditions to link threat mitigations to existing invariant controls using the structured mitigation object `{type, id, note?}` and verify every security invariant has a corresponding threat test
- **07_nfrs.json**: NFR IDs, performance thresholds, and availability targets to define resource exhaustion thresholds, link mitigations using the structured mitigation object `{type, id, note?}`, and scope edge case trigger conditions
- **08_fixtures.json**: Test fixture scenarios and boundary value definitions to identify edge case failure modes and ensure fixture coverage aligns with threat mitigation validation
- **09_impl_plan.json**: Technology stack selections, framework versions, and infrastructure choices to identify technology-specific vulnerability classes and attack vectors unique to the chosen stack
- **10_governance.json**: Access control policies, commit traceability rules, and review enforcement boundaries to determine which governance controls serve as mitigation anchors for authorization threats

## Operating Flow: Threat Model → Exploit → Mitigate → Emit
1.  **Threat Model**: Identify attack surfaces from APIs, invariants, and trust boundaries. For each Public API and Critical Component, ask "How can this fail?" and "How can this be abused?". Classify threats using the schema enum `vc:core:atoms#threatCategory` — valid categories are `authn`, `authz`, `business_logic`, `transport`, and `data_privacy` (see Taxonomy of Threats below for per-category examples). Do not use STRIDE labels directly — map STRIDE-style analysis to these five schema-defined categories.
2.  **Exploit**: For each attack surface, enumerate concrete exploit scenarios and their preconditions. Link the threat explicitly to the `api` or `component` ID it targets. `target_ids` is MANDATORY. Identify non-malicious failure modes (timeouts, race conditions) as structured objects.
3.  **Mitigate**: Propose mitigations as structured objects with `type`, `id`, and optional `note` — see schema `vc:11-redteam` for the authoritative mitigation shape and full `type` enum. Not plain strings. MUST link to existing upstream artifact IDs using the correct `type` value (e.g., `inv`, `nfr`, `fr`, `api`, `fixture`, `doc`). If no existing control applies, MUST use `type: doc` with a concrete action description in `note` (`doc` is exempt from upstream cross-reference). Use `type: capability` ONLY to reference an EXISTING `cap-*` ID from Step 01.
4.  **Emit**: Write the artifact when all high-severity threats have mitigations.

## Examples: Weak vs. Strong
| Quality | Threat Description | Vector | Linking |
|:---|:---|:---|:---|
| ❌ **Weak** | "DDoS Attack" | "Flooding" | (Missing target) |
| ✅ **Strong** | "Search API Resource Exhaustion" | "Recursive Wildcard Query" | `target_ids: [{type: api, id: api-search}]` |
| ❌ **Weak** | "SQL Injection" | "Input" | (Missing target) |
| ✅ **Strong** | "Profile Update SQLi" | "Unsanitized 'bio' field" | `target_ids: [{type: api, id: api-user-profile}]` |

## Heuristics For Completeness
- **Coverage**: Every `public` API in `spec/05_interface_contracts.json` MUST have at least one mapped threat (AuthZ bypass, Rate Limit abuse, or domain-specific attack vector).
- **Specificity**: Avoid "Generic DDOS". Use "Search API Reflection Attack".
- **Linkage**: If you list a mitigation "Enforce Role Check", link it to the actual invariant `inv-authz-admin-only`.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.
- `spec/02_system_sketch.json` is present and contains at least one component entry.
- `spec/06_invariants.json` is present and contains at least one invariant entry.

## Clarification Questions
- If the system operates in a regulated, high-risk, or domain-specific context not evident from upstream specs, ask about domain-specific threat categories before finalizing.
- If the access control model is not fully specified in upstream interface contracts, ask Gap Questions rather than assuming a threat surface.

## Negative Constraints
- **DO NOT** list generic threats (e.g., "OWASP Top 10") without specific application context.
- **DO NOT** omit `target_ids` for any threat; every threat must map to an API or component.
- **DO NOT** use vague mitigations (e.g., "Fix it"); link to specific Invariants or NFRs.
- **DO NOT** ignore edge cases; operational failure modes are just as critical as security threats.

## Coverage Closure
Before emitting, verify:
- Every `api_id` in `spec/05_interface_contracts.json` appears in ≥1 threat's `target_ids`. For low-risk internal-only endpoints with no viable threat, document the omission rationale in a gap question (Clarify mode) rather than adding an `out_of_scope` field (the schema does not define such a field).
- Every `component_id` in `spec/02_system_sketch.json` that crosses a trust boundary has ≥1 threat scenario.
- Every step-06 invariant that carries a `risk_category_ref` must be referenced by at least one threat mitigation of `type: inv` (enforced by W615).
- All `target_ids[*].id` values resolve to existing `api_id` or `component_id` values in their referenced spec files (steps 05 and 02 respectively).
- If any external-facing surface has unclear threat model: add a gap question (Clarify mode) rather than leaving it unanalyzed.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every externally-facing API endpoint from Step 05 has at least one threat scenario
- [ ] All mitigations are structured objects (not plain strings)
- [ ] High-severity threats have ≥1 mitigation each
- [ ] Every high-priority FR has at least one threat scenario modeled
- [ ] Every proposed mitigation references a specific control or implementation step (not just "add validation")
- [ ] Attack surfaces align with trust zone boundaries from the system sketch
- [ ] All `mitigations` are structured objects with `type` and `id` fields (per schema `vc:11-redteam`), not plain strings
- [ ] All `edge_cases` entries have a structured `id` field

## Step-Specific Output Constraints
1.  `trace`: Include a root trace to `step-11` or relevant governance ticket.
2.  `target_ids`: MUST be populated for every threat.
3.  `mitigations`: MUST use the structured mitigation object `{type, id, note?}` — NOT the generic `traceRef` primitive. Valid `type` values are a closed enum defined in schema `vc:11-redteam` mitigations items.
4.  `category`: MUST be one of the allowed enum values (defined in `vc:core:atoms#threatCategory`).
5.  `risk_category_ref`: REQUIRED for every threat. Must be a canonical ref object with `kind: "risk_category"` resolving to an entry in `canon/manifest.json`. Resolve the canonical ID from `canon/manifest.json` (kind: `risk_category`); if no matching entry exists, add one via `canonical_proposals` before authoring the artifact. Validated by canonical-integrity lint (E110).

## Step-Specific Completeness Checklist
- [ ] **Surface Coverage**: Every `public` API and critical component has at least one mapped threat.
- [ ] **Category Diversity**: Threats are not just `authz`; `transport`, `business_logic`, and `data_privacy` are represented.
- [ ] **Edge Case Rigor**: At least 3 distinct non-malicious failure modes (e.g., timeouts, race conditions) are identified.
- [ ] **Traceability Integrity**: Every threat has a valid `target_ids` array pointing to existing Step 05 or Step 02 IDs.
- [ ] **Mitigation Actionability**: Mitigations link to specific Invariants/NFRs/FRs via the correct `type` value, or use `type: doc` with a concrete action in `note` for net-new proposed controls — `type: capability` is ONLY for referencing EXISTING `cap-*` IDs from Step 01 (no vague "Fix it" notes).

## Cross-Step Synthesis Notes
- **id**: `redteam-catalog` (Fixed).
- **threats**:
    - `threat_id`: `threat-<category>-<slug>` (e.g., `threat-authz-elevation`).
    - `description`: A detailed narrative of the attack scenario. Don't be vague; explain *how* the attack works in the context of the system (e.g. "Attacker injects SQL into the 'user_id' parameter to bypass auth").
    - `vector`: The specific technical method (e.g., "JWT Substitution", "SQL Injection", "Race Condition").
    - `target_ids`: Array of traceRef objects `{ "type": "<trace-type>", "id": "<upstream-id>" }`. Valid types for threat targets are `api` and `component` only — consult schema `vc:11-redteam` target_ids items (`vc:core:collections#traceRef`). **CRITICAL**: These must match actual upstream IDs from Step 02 (components) or Step 05 (APIs).
    - `category`: strictly validated against the schema enum `vc:core:atoms#threatCategory` — see Taxonomy of Threats above.
    - `mitigations`: Array of structured objects. Full `type` enum is defined in schema `vc:11-redteam` (mitigations items.type.enum). Examples:
        - Invariant: `{ "type": "inv", "id": "inv-...", "note": "Enforced by middleware" }`.
        - NFR: `{ "type": "nfr", "id": "nfr-..." }`.
        - FR: `{ "type": "fr", "id": "fr-..." }`.
        - Existing capability ref: `{ "type": "capability", "id": "cap-existing-control", "note": "Existing cap-* ID from Step 01" }`.
        - Net-new proposed control (no existing upstream artifact): `{ "type": "doc", "id": "doc-new-measure", "note": "Implement specific check (no existing upstream artifact yet)" }`.
    - `mitigation.note`: Optional context explaining *how* the linked item mitigates the threat (e.g., "Rate limit of 5rps prevents resource exhaustion").
    - `severity`: validated against `vc:core:atoms#severityLevel` (schema-enforced — do not restate values here).
- **edge_cases**:
    - `id`: `ec-<slug>` (e.g., `ec-timeout-upstream`).
    - `description`: The specific operational scenario (e.g. "Upstream API returns 429 after 100 requests").
    - `trigger`: The condition or threshold causing this (e.g., "Latency > 5000ms", "Concurrent Users > 1000").

## Best Practices
- **Think Like a Harrower**: Don't just list bugs; list *exploits*. How would you break the specific business logic defined in `04_fr_list.json`?
- **Link Everything**: A threat without `target_ids` is a hallucination. A mitigation without a structured `{type, id}` trace link is a wish.
- **Diversity**: Don't stop at SQL Injection. Look for Logic Flaws (e.g., skipping payment steps), Race Conditions, and Privacy Leaks.
- **Specificity**: "API returns 500" is bad. "API leaks stack trace allowing causing info disclosure" is good.

## Common Pitfalls
- **The "Generic List"**: outputting OWASP Top 10 items that don't apply to this specific system.
- **Empty Targets**: listing a threat but leaving `target_ids` empty or pointing to non-existent IDs.
- **Vague Mitigations**: "Implement security" (Bad) vs "Enforce `inv-authz-admin` validation" (Good).
- **Ignoring Edge Cases**: Only focusing on malicious hackers and forgetting about timeouts, retries, and concurrency limits.

# Clarification Questions
- Are there any specific compliance requirements (GDPR, HIPAA) that dictate data privacy threats?
- Which third-party integrations (from System Sketch) are considered untrusted trust boundaries?
- Are there specific legacy components known to be fragile?
- What is the expected throughput (NFRs) to define "Resource Exhaustion" thresholds?

# Schema Reference
- Schema URI: vc:11-redteam
- Schema File: schema/11_redteam.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
> **Note**: `risk_category_ref.id` values in the example below are illustrative slugs. Authoritative canonical IDs for `risk_category` entries **must be resolved from `canon/manifest.json`** (kind: `risk_category`). If no matching entry exists yet, add one via `canonical_proposals` and run `canon-accept` before authoring the artifact — do NOT copy unresolved IDs verbatim, as canonical-integrity lint (E110) will reject them.

```json
{
  "$schema": "vc:11-redteam",
  "id": "redteam-catalog",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "trace": [
    {
      "type": "doc",
      "id": "spec-11"
    }
  ],
  "threats": [
    {
      "threat_id": "threat-authz-admin-bypass",
      "description": "User can force admin flag in profile update",
      "vector": "Mass Assignment",
      "category": "authz",
      "severity": "critical",
      "target_ids": [
        {
          "type": "api",
          "id": "api-users-update-profile"
        }
      ],
      "mitigations": [
        {
          "type": "inv",
          "id": "inv-profile-immutable-fields",
          "note": "Strict whitelist on updates"
        }
      ],
      "risk_category_ref": {
        "id": "cn:core:risk_category:authz",
        "kind": "risk_category"
      }
    }
  ],
  "edge_cases": [
    {
      "id": "ec-db-timeout",
      "description": "Primary DB timeout under load",
      "trigger": "Connection Pool Exhaustion"
    }
  ],
  "canonical_refs_used": [
    {
      "id": "cn:core:risk_category:authz",
      "kind": "risk_category"
    }
  ]
}
```

