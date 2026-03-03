# Step 11 · Red‑Team / Failure Modes

Run `specdev prompt-context 11` to see downstream consumers.

## Schema Authority

The schema at `schema/11_redteam.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values —
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.

## Coverage Gap Reporting

Any output field whose value cannot be traced to a specific upstream artifact or seed document
MUST be recorded in `coverage_gaps[]` with:
- `upstream_item_id`: the ID of the upstream item that should have provided the data
- `source_step`: the step number where the data was expected
- `reason`: why the value could not be traced

This is DISTINCT from the Clarify->Emit protocol: ambiguous requirements trigger clarification
questions; untraceable content triggers `coverage_gaps[]` population.

## Path Variables
| Variable | Description |
|---|---|
| `$PRODUCT_ROOT` | Root of the consumer/product repository |
| `$TOOLKIT_ROOT` | Root of the devspec_toolkit directory |
| `$SPEC_DIR` | `$PRODUCT_ROOT/spec` — where spec artifacts live |
| `$SCHEMA_DIR` | `$TOOLKIT_ROOT/schema` — where JSON Schemas live |

## Purpose
Proactively identify security threats, failure modes, and edge cases. Ensure every threat is directly **traceable** to a specific public API or system component, and define actionable **mitigations** linked to requirements or invariants.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit
```

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
- **02_system_sketch.json**: Component IDs, trust boundary crossings, inter-component communication paths, and external integration points to map every threat to a concrete target_ids entry
- **02a_delivery_baseline.json**: Deployment environment definitions and infrastructure topology to identify environment-specific attack surfaces and operational failure modes per stage
- **03_glossary.json**: Domain term definitions and entity relationships to write threat descriptions and vectors using precise, unambiguous domain language rather than generic security jargon
- **04_fr_list.json**: Functional requirement IDs, business logic workflows, preconditions, and postconditions to identify business logic abuse scenarios and link mitigations via traceRef
- **05_interface_contracts.json**: API IDs, HTTP methods, authentication modes, request/response schemas, and error states to enumerate per-endpoint threat vectors and ensure every public API has coverage
- **06_invariants.json**: Invariant IDs and enforcement conditions to link threat mitigations to existing invariant controls via traceRef and verify every security invariant has a corresponding threat test
- **07_nfrs.json**: NFR IDs, performance thresholds, and availability targets to define resource exhaustion thresholds, link mitigations via traceRef, and scope edge case trigger conditions
- **08_fixtures.json**: Test fixture scenarios and boundary value definitions to identify edge case failure modes and ensure fixture coverage aligns with threat mitigation validation
- **09_impl_plan.json**: Technology stack selections, framework versions, and infrastructure choices to identify technology-specific vulnerability classes and attack vectors unique to the chosen stack
- **10_governance.json**: Access control policies, commit traceability rules, and review enforcement boundaries to determine which governance controls serve as mitigation anchors for authorization threats

## Operating Flow: Attack → Trace → Mitigate
1.  **Surface Analysis**: For each Public API and Critical Component, ask "How can this fail?" and "How can this be abused?".
2.  **Categorize**: Classify threats into `authn`, `authz`, `business_logic`, `transport`, or `data_privacy`.
3.  **Trace**: Link the threat explicitly to the `api` or `component` ID it targets. `target_ids` is MANDATORY.
4.  **Mitigate**: Define mitigations. MUST link to existing `inv-*` or `nfr-*` IDs from `spec/06_invariants.json` or `spec/07_nfrs.json` using the `traceRef` structure when a matching control exists. If no existing control applies, MUST create a new entry with `type: capability` and a concrete action description in `note`.
5.  **Edge Cases**: Identify non-malicious failure modes (timeouts, race conditions) as structured objects.

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
- [ ] Does every threat in `threats` have a non-empty `target_ids` array?
- [ ] Are all `target_ids` valid IDs from Step 05 (APIs) or Step 02 (Components)?
- [ ] Are `mitigations` structured objects with types, not just strings?
- [ ] Are `edge_cases` structured with IDs?
- If the system operates in a regulated, high-risk, or domain-specific context not evident from upstream specs, ask about domain-specific threat categories before finalizing.
- If the access control model is not fully specified in upstream interface contracts, ask Gap Questions rather than assuming a threat surface.
- If score < 0.9, output clarifying questions only — do not emit JSON.


### Coverage Closure
Before emitting, verify:
- Every `api_id` in `spec/05_interface_contracts.json` appears in ≥1 threat's `target_ids`, OR is explicitly listed in `out_of_scope` with rationale (low-risk internal-only endpoints).
- Every `component_id` in `spec/02_system_sketch.json` that crosses a trust boundary has ≥1 threat scenario.
- Every security-relevant `inv_id` in `spec/06_invariants.json` has a corresponding threat entry that tests its enforcement.
- All `target_ids[*].id` values resolve to existing `api_id`, `component_id`, or `fr_id` values in their referenced spec files.
- If any external-facing surface has unclear threat model: add a gap question (Clarify mode) rather than leaving it unanalyzed.
- [ ] Every upstream ID from ingested context has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] `seed_refs` is `[]` (this step derives from upstream specs, not seeds)

# Output Rules
1.  Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).
2.  Do not dump JSON in the chat thread; respond with a short confirmation that the artifact path was written and validation status.
3.  Follow the referenced step schema exactly.
4.  `trace`: Include a root trace to `step-11` or relevant governance ticket.
5.  `target_ids`: MUST be populated for every threat.
6.  `mitigations`: MUST use `traceRef` structure (type + id).
7.  `category`: MUST be one of the allowed enum values.

## Negative Constraints
- **DO NOT** list generic threats (e.g., "OWASP Top 10") without specific application context.
- **DO NOT** omit `target_ids` for any threat; every threat must map to an API or component.
- **DO NOT** use vague mitigations (e.g., "Fix it"); link to specific Invariants or NFRs.
- **DO NOT** ignore edge cases; operational failure modes are just as critical as security threats.

## Step-Specific Completeness Checklist
- [ ] **Surface Coverage**: Every `public` API and critical component has at least one mapped threat.
- [ ] **Category Diversity**: Threats are not just `authz`; `transport`, `business_logic`, and `data_privacy` are represented.
- [ ] **Edge Case Rigor**: At least 3 distinct non-malicious failure modes (e.g., timeouts, race conditions) are identified.
- [ ] **Traceability Integrity**: Every threat has a valid `target_id` pointing to an existing Step 05 or Step 02 ID.
- [ ] **Mitigation Actionability**: Mitigations link to specific Invariants/NFRs or define concrete new capabilities (no vague "Fix it" notes).

## Field-by-Field Guidance
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

## Quick Reference
- **ID Format**: `redteam-catalog` (file), `threat-<cat>-<slug>`, `ec-<slug>`.
- **Categories**: `authn`, `authz`, `business_logic`, `transport`, `data_privacy`.
- **Targets**: Link to `api-*` (Step 05) or `component-*` (Step 02).
- **Mitigation Types**: `inv` (Step 06), `nfr` (Step 07), `fr` (Step 04), `doc` (Step 10).

# Clarification Questions
- Are there any specific compliance requirements (GDPR, HIPAA) that dictate data privacy threats?
- Which third-party integrations (from System Sketch) are considered untrusted trust boundaries?
- Are there specific legacy components known to be fragile?
- What is the expected throughput (NFRs) to define "Resource Exhaustion" thresholds?

# Schema Reference
- Schema URI: https://specdev.local/schema/11_redteam.schema.json
- Schema File: schema/11_redteam.schema.json
- Schema Registry: tools/schema_registry.json

## Hardening Protocol
- fail-closed preflight: verify required fields, allowed enums, referenced IDs, and command/tool existence before emitting JSON.
- No-Invention Rules: do not invent IDs, enums, commands, files, metrics, stages, or canonical mappings that are not grounded in provided inputs.
- Completeness Closure: run a final closure pass to confirm required sections, trace/canonical closure, and seed coverage are complete.
- blocker report: if required inputs are missing, conflicting, or ambiguous after clarification, stop and return a blocker report instead of speculative output.

## Canonical Registry (Required Input)

Before generating output, you MUST load and search `canon/manifest.json` for existing canonical entries. Use this registry to:
1. Bind `*_ref` fields to existing canonical IDs (`cn:<namespace>:<kind>:<slug>`)
2. Resolve aliases via `canon/aliases.json`
3. Propose new entries in `canonical_proposals` when no match exists
4. Flag conflicts in `canonical_conflicts` when ambiguous matches are found
## Canonical Binding Rules
1. `canonical_refs_used` is REQUIRED and must list every canonical ID referenced by any `*_ref` field in this artifact.
2. `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term, metric, entity, role, etc. that does not exist in the registry.
3. `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries or contradicts an existing definition.
4. `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.
5. For each `*_ref` field in the schema: if the semantic content exists, the ref MUST be populated. This is not optional.

## Metadata Contract

This step's output artifact MUST include every field listed in the schema's `required[]` array (see Schema Authority). Do NOT add fields not defined in the schema. Refer to the schema for the complete list of required fields, types, and structural constraints — do NOT restate them here.

# Output Contract
```json
{
  "id": "redteam-catalog",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "seed_refs": [],
  "spec_refs_ingested": [],
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
  "generation_quality": {
    "assumptions": []
  },
  "canonical_refs_used": [
    {
      "id": "cn:core:risk_category:authz",
      "kind": "risk_category"
    }
  ],
  "canonical_proposals": [],
  "canonical_conflicts": [],
  "coverage_gaps": []
}
```

