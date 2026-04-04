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
- **Constraint:** EVERY mitigation MUST link to an existing requirement ID (`nfr-*`, `inv-*`, `fr-*`) from upstream specs using the `traceRef` structure. If no existing ID applies, MUST define a new capability entry with `type: capability` and a concrete action in `note`.

## Taxonomy of Threats
Use the `category` field to classify threats precisely:
1.  **`authn` (Authentication)**: "Who are you?" (e.g., Session fixation, Credential stuffing).
2.  **`authz` (Authorization)**: "Can you do this?" (e.g., IDOR, Privilege Escalation, Admin bypass).
3.  **`business_logic`**: Flaws in the workflow itself (e.g., Buying 0 items for $0, skipping payment step).
4.  **`transport`**: Data in motion (e.g., MitM, Cleartext logging, weak TLS).
5.  **`data_privacy`**: Data at rest/leakage (e.g., PII exposure in logs, GDPR violation, unnecessary data collection).

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Product scope boundaries, compliance posture, and regulatory constraints that define which threat categories are mandatory and which data sensitivity levels apply
- **01_capabilities.json**: Capability IDs, priority rankings, and scope definitions to assess which capabilities carry the highest business impact if compromised or degraded
- **02_system_sketch.json**: Component IDs, trust boundary crossings, inter-component communication paths, external integration points, and **tech_stack** (specific framework/runtime versions that have known CVE surfaces or security-relevant configuration defaults — e.g., Django CSRF middleware vs manual CSRF in Express) to map every threat to a concrete target_ids entry
- **02a_delivery_baseline.json**: Deployment environment definitions and infrastructure topology to identify environment-specific attack surfaces and operational failure modes per stage
- **03_glossary.json**: Domain term definitions and entity relationships to write threat descriptions and vectors using precise, unambiguous domain language rather than generic security jargon
- **04_fr_list.json**: Functional requirement IDs, business logic workflows, preconditions, and postconditions to identify business logic abuse scenarios and link mitigations via traceRef
- **05_interface_contracts.json**: API IDs, HTTP methods, authentication modes, request/response schemas, and error states to enumerate per-endpoint threat vectors and ensure every public API has coverage
- **06_invariants.json**: Invariant IDs and enforcement conditions to link threat mitigations to existing invariant controls via traceRef and verify every security invariant has a corresponding threat test
- **07_nfrs.json**: NFR IDs, performance thresholds, and availability targets to define resource exhaustion thresholds, link mitigations via traceRef, and scope edge case trigger conditions
- **08_fixtures.json**: Test fixture scenarios and boundary value definitions to identify edge case failure modes and ensure fixture coverage aligns with threat mitigation validation
- **09_impl_plan.json**: Technology stack selections, framework versions, and infrastructure choices to identify technology-specific vulnerability classes and attack vectors unique to the chosen stack
- **10_governance.json**: Access control policies, commit traceability rules, and review enforcement boundaries to determine which governance controls serve as mitigation anchors for authorization threats

## Operating Flow: Threat Model → Exploit → Mitigate → Emit
1.  **Threat Model**: Identify attack surfaces from APIs, invariants, and trust boundaries. Use threat categories: STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege). For each Public API and Critical Component, ask "How can this fail?" and "How can this be abused?". Classify threats into `authn`, `authz`, `business_logic`, `transport`, or `data_privacy`.
2.  **Exploit**: For each attack surface, enumerate concrete exploit scenarios and their preconditions. Link the threat explicitly to the `api` or `component` ID it targets. `target_ids` is MANDATORY. Identify non-malicious failure modes (timeouts, race conditions) as structured objects.
3.  **Mitigate**: Propose mitigations as structured objects (`{ "control": "...", "type": "preventive|detective|corrective" }`). Not plain strings. MUST link to existing `inv-*` or `nfr-*` IDs from `spec/06_invariants.json` or `spec/07_nfrs.json` using the `traceRef` structure when a matching control exists. If no existing control applies, MUST create a new entry with `type: capability` and a concrete action description in `note`.
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
- Every `api_id` in `spec/05_interface_contracts.json` appears in ≥1 threat's `target_ids`, OR is explicitly listed in `out_of_scope` with rationale (low-risk internal-only endpoints).
- Every `component_id` in `spec/02_system_sketch.json` that crosses a trust boundary has ≥1 threat scenario.
- Every security-relevant `inv_id` in `spec/06_invariants.json` has a corresponding threat entry that tests its enforcement.
- All `target_ids[*].id` values resolve to existing `api_id`, `component_id`, or `fr_id` values in their referenced spec files.
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
- [ ] All `mitigations` are structured objects with `type` and `control` fields, not plain strings
- [ ] All `edge_cases` entries have a structured `id` field

## Step-Specific Output Constraints
1.  `trace`: Include a root trace to `step-11` or relevant governance ticket.
2.  `target_ids`: MUST be populated for every threat.
3.  `mitigations`: MUST use `traceRef` structure (type + id).
4.  `category`: MUST be one of the allowed enum values.

## Step-Specific Completeness Checklist
- [ ] **Surface Coverage**: Every `public` API and critical component has at least one mapped threat.
- [ ] **Category Diversity**: Threats are not just `authz`; `transport`, `business_logic`, and `data_privacy` are represented.
- [ ] **Edge Case Rigor**: At least 3 distinct non-malicious failure modes (e.g., timeouts, race conditions) are identified.
- [ ] **Traceability Integrity**: Every threat has a valid `target_id` pointing to an existing Step 05 or Step 02 ID.
- [ ] **Mitigation Actionability**: Mitigations link to specific Invariants/NFRs or define concrete new capabilities (no vague "Fix it" notes).

## Cross-Step Synthesis Notes
- **id**: `redteam-catalog` (Fixed).
- **threats**:
    - `threat_id`: `threat-<category>-<slug>` (e.g., `threat-authz-elevation`).
    - `description`: A detailed narrative of the attack scenario. Don't be vague; explain *how* the attack works in the context of the system (e.g. "Attacker injects SQL into the 'user_id' parameter to bypass auth").
    - `vector`: The specific technical method (e.g., "JWT Substitution", "SQL Injection", "Race Condition").
    - `target_ids`: Array of objects `{ "type": "api"|"component", "id": "..." }`. **CRITICAL**: These must match actual upstream IDs.
    - `category`: strictly validation against enum (`authn`, `authz`, `business_logic`, `transport`, `data_privacy`).
    - `mitigations`: Array of references.
        - If mitigating via an Invariant: `{ "type": "inv", "id": "inv-...", "note": "Enforced by middleware" }`.
        - If mitigating via NFR: `{ "type": "nfr", "id": "nfr-..." }`.
        - If new: `{ "type": "capability", "id": "cap-new-measure", "note": "Implement specific check" }`.
    - `mitigation.note`: Optional context explaining *how* the linked item mitigates the threat (e.g., "Rate limit of 5rps prevents resource exhaustion").
    - `severity`: `low`, `medium`, `high`, `critical`.
- **edge_cases**:
    - `id`: `ec-<slug>` (e.g., `ec-timeout-upstream`).
    - `description`: The specific operational scenario (e.g. "Upstream API returns 429 after 100 requests").
    - `trigger`: The condition or threshold causing this (e.g., "Latency > 5000ms", "Concurrent Users > 1000").

## Best Practices
- **Think Like a Harrower**: Don't just list bugs; list *exploits*. How would you break the specific business logic defined in `04_fr_list.json`?
- **Link Everything**: A threat without a `target_id` is a hallucination. A mitigation without a `traceRef` is a wish.
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

