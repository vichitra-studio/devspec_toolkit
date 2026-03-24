# Future Extension Candidates

**Created**: 2026-03-25
**Status**: DEFERRED — not in current pipeline

These candidates have been identified as valuable additions to the spec pipeline but are not part of the current 00–16c step sequence. Each would require a new schema, prompt, and validator before it can be introduced. They are documented here to preserve the rationale and avoid re-discovery.

---

## AUDIT-089: Consumed Third-Party API Contracts Artifact

**Proposed step**: Between Step 05 (Interface Contracts) and Step 06 (Invariants), or as a companion to Step 05.

### What it is

A dedicated spec step for capturing the external API contracts that the system *consumes* — payment gateways, notification services, identity providers, map APIs, etc. The artifact would record the provider, the endpoint or SDK surface used, the data exchanged, and the contractual guarantees (SLA, versioning, deprecation policy).

### What exists today

Third-party dependencies are currently mentioned implicitly in:
- **Step 01 (Capabilities)**: external integrations appear as capability references.
- **Step 07 (NFRs)**: availability and latency targets for third-party calls.
- There is no structured record of which external contracts the system depends on or what happens when they change.

### Why it is a future extension, not current

Adding it now would require a new schema, a migration template, prompt changes across Steps 05–07, and matrix updates. The benefit is real but the cost of insertion mid-pipeline is high. The current pipeline handles the majority of projects adequately; the gap only surfaces when third-party failure modes (versioning, deprecation, outages) need to be traced through the spec.

### What it would augment

Augments Step 05 (Interface Contracts) by separating *owned* interfaces from *consumed* interfaces. Feeds into Step 07 (NFRs, specifically availability budgets) and Step 11 (Red Team, specifically third-party failure scenarios).

---

## AUDIT-090: Security Model Consolidation Artifact

**Proposed step**: Between Step 06 (Invariants) and Step 07 (NFRs), or as a dedicated Phase I step after Step 11.

### What it is

A dedicated step for consolidating security model decisions: authentication schemes, authorization model (RBAC, ABAC, scopes), session management policy, data classification tiers, and secrets management. The artifact would be the single authoritative source for security architecture decisions, replacing scattered prose in other steps.

### What exists today

Security concerns are currently spread across:
- **Step 06 (Invariants)**: security invariants (e.g., "all data at rest must be encrypted").
- **Step 07 (NFRs)**: security NFRs (e.g., `nfr-auth-mfa`).
- **Step 11 (Red Team)**: attack scenarios and mitigations.
- No step consolidates auth scheme, RBAC design, and data classification into a single artifact that downstream steps can trace to.

### Why it is a future extension, not current

Security decisions are already partially captured; adding a consolidation step without refactoring Steps 06, 07, and 11 would create duplication. The consolidation requires domain agreement on what belongs in the new step versus what stays in invariants and NFRs. This is a non-trivial schema and migration effort.

### What it would augment

Replaces security-related content currently split across Steps 06, 07, and 11. Provides a single trace target for security requirements in Step 05 (Interface Contracts), Step 12 (CI Gates), and Steps 16a–16c (implementation planning).

---

## AUDIT-099: Dedicated Data Model Artifact

**Proposed step**: Between Step 04 (Functional Requirements) and Step 05 (Interface Contracts).

### What it is

A formal data model / entity-relationship specification step. It would define the primary entities the system manages, their attributes, cardinalities, and relationships. This is distinct from Step 08 (Fixtures), which provides sample data instances, not entity definitions.

### What exists today

Entity definitions are currently implicit in:
- **Step 08 (Fixtures)**: fixture objects encode entity shapes, but are sample instances not schemas.
- **Step 04 (FRs)**: acceptance criteria mention entity operations (create, update, delete) without defining the entity shape.
- There is no step that says "the system has an `Order` entity with these fields and these relationships to `Customer` and `Product`."

### Why it is a future extension, not current

A data model step would need to sit between Step 04 and Step 05, which requires renumbering downstream steps or inserting a `04a` step (similar to how `02a` and `13a` were added). It also requires defining the right level of formalism — full ERD JSON, a simplified entity list, or a JSON-Schema-per-entity approach. This design work is not yet done.

### What it would augment

Augments Step 08 (Fixtures) by providing the schema definition that fixtures instantiate. Feeds into Step 05 (Interface Contracts, specifically request/response body shapes) and Step 07 (NFRs, specifically storage and data retention). Makes Step 13a (Completeness Assessment) more precise for data-centric systems.

---

## Adoption Criteria

Before any of these candidates can be promoted to the pipeline, they must satisfy:

1. A new JSON Schema in `schema/` with full validation coverage.
2. A migration template in `prompts/migration/` for projects upgrading to the new step.
3. A prompt file in `prompts/` covering the Clarify → Emit contract.
4. Entries in `tools/schema_registry.json` and `tools/step_order.json` (including `downstream_consumers`).
5. At least one valid and one invalid fixture in `tests/fixtures/`.
6. A passing `pytest tests/` run with no regressions.
