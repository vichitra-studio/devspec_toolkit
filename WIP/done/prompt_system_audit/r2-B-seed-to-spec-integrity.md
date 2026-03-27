# R2-B: Seed-to-Spec Integrity Chain Analysis

**Date**: 2026-03-20
**Scope**: Steps 00 through 07 -- every link in the chain from seed documents to non-functional requirements
**Method**: Line-by-line analysis of all 9 prompts, all 8 schemas, seed_manifest.json, step_order.json, and seed templates

---

## 1. Per-Step Analysis

### 1.1 Seed Documents (Root of Chain)

**What the templates guide:**
- `seed_overview.md` (seed_templates/seed_overview.md): Structured template with 7 sections covering problem/users, scope/MVP, expected capabilities, domain model, timeline, team/process. Contains meta-prompt instructions for an AI coach to enforce specificity.
- `seed_tech_stack.md` (seed_templates/seed_tech_stack.md): Structured template with 6 sections covering system type, core technology, components, constraints/boundaries, dependencies, stack summary. Contains meta-prompt for an AI architect.

**What the templates assume:**
- The human product owner provides honest, specific answers. `[UNKNOWN: reason]` is the escape valve.
- The seed_overview template explicitly separates product intent from technical decisions (line 15: "DO NOT STRAY into technical decisions").

**Requirement categories that seeds may not explicitly cover:**

Note: Seeds are PRD/system design input, not specs. They are intentionally unstructured. The toolkit's job is to surface and fill gaps through pipeline steps, not to require seeds to be exhaustive. The following categories may or may not appear in seed docs — the critical question is whether **step prompts guide LLMs to extract or derive them from whatever the seeds contain**:

- **Compliance/regulatory** — may appear in seed_tech_stack "Constraints & Boundaries" (section 4.1) but a product owner may not mention GDPR/SOC2/HIPAA unless prompted. Step prompts must guide extraction.
- **Data lifecycle/retention** — rarely in seed docs. Steps 04, 06, 07 must guide LLMs to derive these as implicit requirements.
- **Integration inventory** — seed_tech_stack asks about components but doesn't systematically inventory external systems. Step 02 must guide discovery.
- **Operational requirements** — on-call, incident response, monitoring. Step 07 (NFRs) must have category checklists for these.
- **Error handling philosophy** — rarely stated at the product level. Step 04 must guide implicit FR discovery for error handling patterns.

---

### 1.2 Seed -> Step 00 (Charter)

**What the prompt guides (prompt_00_project_charter.md):**
- Lines 40-41: Explicit seed ordering via seed_manifest.json, with step_requirements["00"] = ["seed-overview", "seed-tech-stack"].
- Lines 45-46: Primary source is seed_overview (required) for scope/objectives; secondary is seed_tech_stack (required) for constraints.
- Lines 53-56: Extraction Intent specifies exactly what to extract from each seed.
- Lines 79-84: **Coverage Closure** section explicitly requires "Every requirement stated in seed_overview and seed_tech_stack is reflected in goals, constraints, success_metrics, or user_segments, OR explicitly listed in out_of_scope with rationale."
- Line 82: "No seed requirement is silently dropped -- this is the root artifact; nothing upstream can be deferred."
- Lines 64-67: Ambiguity scrub requires replacing vague terms with quantifiable targets.
- Line 84: If seed statement is ambiguous or contradictory, add gap question rather than assume.

**What the prompt assumes:**
- That seed documents are comprehensive. The Coverage Closure check (line 81) verifies seed content is captured, but cannot detect what the seed documents themselves omitted.
- That the LLM can identify "requirements" in free-form prose. There is no taxonomy of requirement types to look for (functional, non-functional, compliance, operational, data, integration).

**What the prompt misses:**
- **No requirement classification guidance**. The prompt says to extract requirements but does not guide the LLM on what categories to look for. A seed_overview that focuses on features may cause the LLM to miss compliance constraints buried in section 3.3 of the template.
- **No guidance on seed_tech_stack constraint extraction**. Line 56 says to extract "Hardware/legacy constraints for out_of_scope or assumptions" but seed_tech_stack contains much more: security boundaries (4.1), distribution constraints (4.2), resilience requirements (4.3), dependency constraints (5.x). The extraction intent is narrower than the seed template structure.
- **Schema gap**: The schema requires `problem_statement`, `success_metrics`, `stakeholders`, `user_segments` but `in_scope`, `out_of_scope`, `assumptions`, `risks` are NOT required by the schema (lines 182-187 of schema). The prompt's completeness checklist (lines 99-106) treats these as essential, but the schema allows them to be omitted entirely.

**Schema enforcement vs prompt guidance:**
- Schema requires: `problem_statement`, `success_metrics` (min 2), `stakeholders`, `user_segments`
- Schema does NOT require: `in_scope`, `out_of_scope`, `assumptions`, `risks`, `links`, `title`
- Prompt guidance says in_scope needs >=3 items (line 101), but schema only enforces minItems:3 IF the field is present -- it is not required.

---

### 1.3 Step 00 -> Step 01 (Capabilities)

**What the prompt guides (prompt_01_capabilities.md):**
- Lines 45-46: Primary source is seed_overview for scope and user persona definitions. Charter is secondary source.
- Lines 53-55: Extraction Intent: from charter, extract goals, success metrics, in/out-of-scope, stakeholder needs.
- Lines 59: Cross-Check requires verifying each capability exists in charter's in_scope or goals, does not contradict out_of_scope.
- Lines 71-72: Self-Audit Gate: "All in-scope charter goals map to at least one capability."
- Lines 78-81: Coverage Closure: "Every goal and success metric in 00_charter.json is addressed by >=1 capability_id, OR explicitly listed in out_of_scope."

**What the prompt assumes:**
- That charter goals are sufficiently decomposed to identify individual capabilities. If the charter has a broad goal like "Improve user onboarding," the prompt says to derive capabilities but provides no decomposition methodology.
- That the LLM knows the difference between a capability and a feature. Line 106 says "DO NOT use generic verbs" but the granularity guidance is limited.

**What the prompt misses:**
- **No guidance on cross-cutting capabilities**. The prompt does not address how to handle capabilities that span multiple components (security, logging, observability, error handling). Line 97 says "each is a single verb-driven behavior" but cross-cutting concerns like "audit all state changes" do not fit neatly.
- **No guidance on capability granularity**. When should "manage users" be split into "create user," "update user," "delete user," "authenticate user"? The prompt says "each is a single verb-driven behavior" (line 97) but does not explain when to merge or split.
- **No guidance on deriving capabilities from user_segments JTBD**. The Coverage Closure checks against goals and success_metrics but not against user_segments[].jobs_to_be_done, which may contain implicit capabilities not reflected in goals.
- **Seed manifest gap**: step_requirements["01"] = ["seed-overview"] only. seed_tech_stack is NOT required for Step 01, yet tech stack constraints can affect capability scope (e.g., "must support offline mode" from tech stack should surface as a capability modifier).

---

### 1.4 Step 01 -> Step 02 (System Sketch)

**What the prompt guides (prompt_02_system_sketch.md):**
- Lines 46-47: Capabilities and owners from 01_capabilities.json inform components.
- Lines 52-55: Extraction Intent from three upstream sources: seed_tech_stack (architecture patterns), charter (scope/integration points), capabilities (IDs/owners mapped to components).
- Lines 71: "responsibilities MUST cover all in-scope capabilities from 01_capabilities.json."
- Lines 77-78: Self-Audit Gate: "Each in-scope capability maps to at least one component."
- Lines 84-88: Coverage Closure: Every capability_id reflected in >=1 component's trace. All tech choices align with seed_tech_stack constraints.

**What the prompt assumes:**
- That capabilities naturally decompose into component boundaries. When two capabilities share data or cross service boundaries, the prompt does not guide the LLM on how to resolve the tension.
- That the LLM can derive appropriate architecture patterns from seed_tech_stack alone.

**What the prompt misses:**
- **No guidance on architecture decision tradeoffs**. The prompt says to build components from capabilities (line 71) but provides no methodology for deciding service boundaries, monolith vs microservice, or shared-nothing vs shared-data patterns.
- **No explicit data model guidance**. Components have "responsibilities" but there is no guidance on where data models are captured. The system sketch schema has no "data_model" or "entities" field. Data modeling falls into a gap between the glossary (terms) and the system sketch (components).
- **No contradiction detection between tech stack and architecture**. Line 87 says "All tech choices align with constraints in seed_tech_stack" but there is no protocol for what to do when the LLM discovers a contradiction (e.g., seed says "single binary" but capabilities require message queue).
- **Schema enforcement gap**: `connections` is only required when 2+ components exist (schema lines 239-258). A single-component system sketch can have zero connections, which is architecturally unusual but schema-valid.

---

### 1.5 Step 02 -> Step 02a (Delivery Baseline)

**What the prompt guides (prompt_02a_delivery_baseline.md):**
- Lines 45-46: System Sketch for components and external dependencies. Charter for deployment targets, compliance.
- Lines 53-56: Extraction Intent from charter (deployment targets, compliance), capabilities (owners, operational modes), system sketch (component IDs, external deps), seed_tech_stack (runtime versions, cloud providers).
- Lines 65-66: MUST include secrets for every external system; MUST include compliance labels when charter or seed references regulatory frameworks.
- Lines 79-83: Coverage Closure: Every component requiring deployment has environment config; all external dependencies in secrets/dependencies.

**What the prompt assumes:**
- That all deployment-relevant information is captured in upstream steps. If the seed_tech_stack mentions "deployed to AWS ECS" but the charter does not mention deployment constraints, the prompt's extraction from charter (line 52) may yield nothing useful.
- That the LLM knows which CI gates are appropriate based on the toolkit's actual command set.

**What the prompt misses:**
- **Extremely limited downstream consumption**. Per step_order.json downstream_consumers, Step 02a feeds ONLY Step 12 (CI Gates). This means Steps 04-07 do NOT consume delivery baseline information, even though:
  - Step 04 (FRs) could benefit from knowing deployment constraints
  - Step 07 (NFRs) should know available monitoring infrastructure
  - Step 06 (Invariants) should know which environments invariants apply to
  The prompt's Extraction Intent (line 55) says capabilities feed into "environment tier requirements" but no downstream prompt references 02a_delivery_baseline.json for this purpose.
- **No staging/prod parity validation**. Line 66 says staging MUST match prod's region/runtime/cluster but the schema has no structure to express this parity requirement -- environments are free-form objects.
- **No tech stack coherence check for later steps**. Delivery baseline captures runtime versions and CI gates, but later steps (04-07) are not directed to validate their assumptions against this baseline.

---

### 1.6 Steps 00-02a -> Step 03 (Glossary)

**What the prompt guides (prompt_03_glossary.md):**
- Lines 45-46: Charter for business terms and metrics.
- Lines 52-56: Extraction Intent from four upstream sources: charter (business terms, metric names, persona names), capabilities (nouns/verbs), system sketch (component names, protocols), delivery baseline (environment names, CI terminology).
- Lines 59: MUST normalize to one canonical term_id per concept.
- Lines 65-66: Coverage rule: every metric name in charter success_metrics MUST have a corresponding term_id with units.
- Lines 79-83: Coverage Closure: Every domain noun from charter and capabilities defined as a term_id.

**What the prompt assumes:**
- That domain vocabulary can be fully derived from upstream spec artifacts. If the seed documents use domain-specific jargon not captured in the charter, those terms will be missed.
- That the LLM can identify all "key nouns" in upstream artifacts without a systematic method.

**What the prompt misses:**
- **No systematic term extraction methodology**. The prompt says "derive recurring nouns/actions from upstream charter and capability artifacts" (line 47) but does not provide a method (e.g., "scan all string fields in charter, extract unique nouns, deduplicate").
- **Glossary is poorly consumed downstream**. Per downstream_consumers, Step 03 feeds Steps 04, 05, and 07. However:
  - Step 04 prompt mentions glossary (line 46: "Glossary to anchor terms") but has no enforcement that FR statements use glossary term_ids.
  - Step 05 prompt says "All resource and action names align with term_id values from spec/03_glossary.json" (line 74) but this is a Coverage Closure check in the prompt, not enforced by any validator.
  - Step 06 prompt mentions glossary for entity definitions (line 51) but Step 06 is NOT listed as a downstream consumer of Step 03 in downstream_consumers.
  - No prompt has a machine-enforceable "must use glossary term" requirement. Glossary alignment is entirely LLM-self-audited.
- **Seed manifest gap**: step_requirements["03"] = ["seed-overview"]. seed_tech_stack is NOT required, yet tech stack documents contain technical terms (protocols, frameworks, patterns) that should appear in the glossary.
- **Schema does not enforce domain/units**. The schema makes `domain` and `units` optional (only `term_id`, `term`, `definition`, `term_ref` are required). The prompt says to include units for metrics (line 65) but the schema does not enforce this.

---

### 1.7 Capabilities -> Step 04 (Functional Requirements)

**What the prompt guides (prompt_04_functional_requirements.md):**
- Lines 45-47: Charter and Capabilities as source of behaviors. Glossary to anchor terms.
- Lines 52-56: Extraction Intent from five upstream sources: charter (scope, success criteria), capabilities (IDs, scope), system sketch (component IDs, trust boundaries), delivery baseline (environments, deployment stages), glossary (domain terms).
- Lines 59-62: Operating Flow requires building Context Ledger of candidate FRs mapped from capabilities.
- Lines 68: Ambiguity scrub bans "should/could/fast/easy" and requires Given-When-Then phrasing.
- Lines 72-73: Self-Audit Gate: "Every in-scope capability maps to >=1 FR."
- Lines 88-89: Extraction Mandate: "Every capability ID from 01_capabilities.json must map to >=1 FR."

**What the prompt assumes:**
- That capabilities are the sole source of FRs. The prompt does not guide discovery of FRs that arise from system-level concerns not captured as capabilities (error handling, session management, audit logging, data migration, configuration management).
- That the LLM knows how to decompose capabilities into testable FRs at the right granularity.

**What the prompt misses:**
- **No implicit FR discovery framework** (corroborates AUDIT-003). The prompt says "Build a private Context Ledger of candidate FRs" (line 59) but provides no checklist of FR categories to consider per capability:
  - Error handling FRs (what happens on failure?)
  - Authorization FRs (who can do this?)
  - Pagination/filtering FRs (for list operations)
  - Idempotency FRs (for mutations)
  - Audit logging FRs (for compliance)
  - Rate limiting FRs (for public APIs)
  - Data validation FRs (for inputs)
- **No conflict resolution protocol** (corroborates AUDIT-002). When charter constraints contradict capability scope (e.g., charter says "SOC2 compliant" but no capability addresses audit logging), the prompt has no guidance.
- **Schema enforces minItems:2 for acceptance_criteria** but the prompt says "each FR has >=1 acceptance criterion" (line 74) -- the schema is stricter than the prompt guidance. This inconsistency could confuse LLMs.
- **Glossary consumption is aspirational**. The prompt says to use glossary to "anchor terms" (line 46) but has no enforcement mechanism for terminological consistency. An FR could use "user" while the glossary defines "end-user" and no validator catches this.
- **No guidance on FR-to-component mapping**. Extraction Intent says to extract component IDs from system sketch (line 54), but the FR schema has no `component_ref` field. The component assignment happens only implicitly through trace to APIs.

---

### 1.8 FRs -> Step 05 (Interface Contracts)

**What the prompt guides (prompt_05_interface_contracts.md):**
- Lines 39-47: Extraction Intent from six upstream sources including charter, capabilities, system sketch, delivery baseline, glossary, and FRs.
- Lines 50-53: Operating Flow maps APIs to FRs; ensures each FR with external behavior has an interface or rationale.
- Lines 56-58: Heuristics require input/output schema refs when FR specifies payloads; at least one error state for non-GET mutations.
- Lines 71-75: Coverage Closure: Every FR with observable external behavior covered by >=1 api_id. Every component exposing an interface has at least one API contract.

**What the prompt assumes:**
- That the LLM can distinguish "external behavior" FRs from "internal" FRs without explicit guidance. The prompt says "each FR with external behavior has an interface" (line 50) but does not define "external behavior."
- That the LLM can derive complete error states from FR acceptance criteria alone.

**What the prompt misses:**
- **No guidance on FRs without API surface**. The prompt says to cover FRs with "observable external behavior" but does not explain what happens to FRs that are purely system-internal (background jobs, scheduled tasks, data migrations). These FRs legitimately have no API but the Coverage Closure (line 71) may flag them as gaps.
- **No pagination/filtering patterns**. The prompt mentions API design but provides no guidance on common patterns (pagination, filtering, sorting, partial responses) that most list APIs require. These generate implicit FRs and invariants.
- **No webhook/event API guidance**. The protocol enum includes `ws` and `mqtt` but the prompt provides almost no guidance on async/event-driven APIs beyond line 117: "For MQTT, map routes to topic paths."
- **Schema requires `interface_ref` (canonical)** but does not require `trace`, `security`, `path`, `method`, or `errors`. A minimal valid API contract is just `api_id`, `name`, `version`, `protocol`, `owner`, and `interface_ref` -- which is structurally valid but useless for downstream steps.
- **No tech stack alignment check**. The extraction intent mentions delivery baseline (line 44) for protocol and transport security, but there is no explicit check that chosen protocols align with Step 02 system sketch connection protocols.

---

### 1.9 FRs -> Step 06 (Invariants)

**What the prompt guides (prompt_06_invariants.md):**
- Lines 44-53: Extraction Intent from seven upstream sources -- the widest upstream surface of any step in scope.
- Lines 55-56: Beyond FR-derived negative cases, MUST include data integrity constraints from glossary entities, state transition rules for lifecycle entities, access boundary rules from trust boundaries, ordering guarantees from FR pre/postconditions.
- Lines 63: MUST use jsonlogic for data predicates, cel for field-level logic; severity=error for security and FR error conditions.
- Lines 76-83: Coverage Closure: Every FR acceptance criterion negative case encoded as inv_id; every API error response has a corresponding invariant.

**What the prompt assumes:**
- That the LLM can write syntactically valid jsonlogic or CEL expressions. No examples of valid expressions are provided in the prompt.
- That FR acceptance criteria and API error responses contain enough information to derive meaningful invariants.

**What the prompt misses:**
- **No jsonlogic/CEL examples**. The prompt says to use jsonlogic and CEL (line 63) but provides no examples of valid expressions. The Output Contract example (line 180) uses `language: "text"` with `expression: "request.authenticated == true"` -- which is a text expression, not jsonlogic or CEL. This contradicts the prompt's own guidance to avoid `text` language (line 118).
- **No systematic invariant discovery method** (partially corroborates AUDIT-003). The prompt lists categories (line 56: data integrity, state transitions, access boundaries, ordering) but provides no method for systematically scanning upstream artifacts for each category.
- **Glossary consumption gap**. The prompt says to derive state transition invariants from "entities with lifecycle stages defined in the glossary" (line 56), but the glossary schema has no `lifecycle_states` field. Glossary terms have only `term_id`, `term`, `definition`, `domain`, `units`. The prompt assumes glossary structure that does not exist.
- **Schema requires `policy_ref`** on every invariant rule (schema line 94). This means every invariant must reference a canonical policy, which may not exist for all types of data integrity constraints.

---

### 1.10 Capabilities/FRs -> Step 07 (NFRs)

**What the prompt guides (prompt_07_nfrs.md):**
- Lines 39-48: Extraction Intent from eight upstream sources -- the widest of any step, consuming everything from charter through invariants.
- Lines 51-54: Align names/units with glossary; measurement_method must reference specific tool/query/dashboard.
- Lines 59: MUST include stage and owner for prod/staging NFRs; measurement_method must be concrete.
- Lines 70-75: Coverage Closure: Every charter success_metric encoded as >=1 nfr_id; every performance-critical FR has corresponding NFR.

**What the prompt assumes:**
- That the LLM can determine which FRs are "performance-critical" without explicit guidance.
- That measurement methods can be determined without knowing the monitoring stack (which lives in delivery baseline, a step NFRs are not documented as consuming from downstream_consumers).

**What the prompt misses:**
- **No NFR category coverage checklist**. The prompt says NFRs should cover "latency, throughput, availability, durability, cost, security/privacy, maintainability, usability, portability, and energy as applicable" (line 91) but provides no guidance on how to determine which categories apply. There is no "for each category, check if any upstream artifact implies a target."
- **Delivery baseline is not a listed consumer source**. Per downstream_consumers, 02a feeds ONLY 12. But prompt_07 says to extract from 02a_delivery_baseline.json (line 44). The Extraction Intent references 02a for "Environment definitions, monitoring tooling, and infrastructure capabilities," but this contradicts the step_order.json downstream_consumers configuration. This is either a prompt-DAG inconsistency or an intentional allowed_upstream that is not reflected in downstream_consumers (allowed_upstream does include "02a" for step "07").
- **No guidance on deriving security NFRs from system sketch trust boundaries**. The prompt says to extract from system sketch (line 43) but does not explain how trust_boundary=public implies specific security NFRs (e.g., WAF, TLS version, certificate management).
- **Schema requires all NFR fields to be non-optional**: `nfr_id`, `category`, `metric`, `target`, `unit`, `metric_ref`, `unit_ref`, `environment_ref`, `measurement_method`, `stage`, `owner`, `trace` are ALL required. This is the strictest schema of any step. The prompt does not warn about this strictness.
- **No tech stack coherence for measurement methods**. If delivery baseline says "CI runner: ubuntu-latest" but an NFR measurement_method says "Grafana dashboard query," there is no validation that Grafana exists in the tech stack.

---

## 2. Per-Transition Analysis

### 2.1 Seed -> Step 00: Extraction Completeness

**Risk**: MEDIUM-HIGH

The prompt has the strongest seed coverage check of any step (lines 79-84), explicitly requiring every seed requirement to be captured or listed in out_of_scope. However:
- The extraction intent (lines 53-56) narrows seed_tech_stack extraction to "Hardware/legacy constraints" and "technology constraints informing risks," which is narrower than what seed_tech_stack actually contains (security boundaries, resilience requirements, distribution constraints, dependency inventory).
- The schema does not require `in_scope`, `out_of_scope`, `assumptions`, or `risks`, meaning a schema-valid charter can omit these entirely.

**What can fall through**: Compliance requirements in seed_tech_stack section 4.1. Resilience requirements in section 4.3. Dependency constraints in section 5.x. Distribution/delivery requirements in section 4.2.

### 2.2 Step 00 -> Step 01: Goal-to-Capability Decomposition

**Risk**: MEDIUM

The prompt has explicit coverage checks (line 78: every goal maps to >=1 capability). The main risk is:
- user_segments[].jobs_to_be_done are not checked. A JTBD may imply a capability that no charter goal explicitly mentions.
- Cross-cutting capabilities (security, observability, audit) have no decomposition guidance.
- success_metrics are checked for coverage but may imply capabilities that are not goal-aligned (e.g., a "session error rate < 0.1%" metric implies a session management capability).

**What can fall through**: Cross-cutting concerns. Implicit capabilities from user JTBD. Capabilities implied by metrics rather than goals.

### 2.3 Step 01 -> Step 02: Capability-to-Component Mapping

**Risk**: MEDIUM

The prompt has strong coverage checks (line 84: every capability_id in >=1 component trace). The main risk is:
- Architecture decisions are made with no formal tradeoff analysis methodology.
- Data model is not captured anywhere in this transition.
- The prompt says "Do not depend on downstream specs" (line 47) but architecture decisions have direct NFR implications that are not captured until Step 07.

**What can fall through**: Data model decisions. Architecture tradeoff documentation. NFR implications of architecture choices (choosing eventual consistency implies availability NFRs).

### 2.4 Step 02 -> Step 02a: Architecture-to-Delivery Mapping

**Risk**: LOW-MEDIUM

The prompt has reasonable coverage checks (lines 79-83). The main risk is the extremely narrow downstream consumption -- only Step 12 consumes 02a, meaning delivery baseline information is effectively invisible to Steps 04-07.

**What can fall through**: Environment-specific constraints on FR feasibility. Monitoring infrastructure availability for NFR measurement methods.

### 2.5 Steps 00-02a -> Step 03: Vocabulary Extraction

**Risk**: MEDIUM-HIGH

The prompt has coverage checks for charter and capability terms (lines 79-83) but:
- No method for systematic term extraction.
- No enforcement that downstream steps use glossary terms.
- The glossary schema lacks structure for lifecycle states, entity relationships, or other rich domain modeling -- it is just term/definition pairs.
- seed_tech_stack is not required (step_requirements["03"] = ["seed-overview"]), so technical vocabulary may be missed.

**What can fall through**: Technical terms from seed_tech_stack. Entity lifecycle states. Entity relationships. Terms introduced in downstream steps without glossary entries (the prompt warns against this at line 126 but no validator enforces it).

### 2.6 Step 03/01 -> Step 04: Capability-to-FR Decomposition

**Risk**: HIGH

This is the highest-risk transition. Step 04 feeds 13 downstream steps -- more than any other. Gaps here propagate furthest.
- No implicit requirement discovery framework.
- No conflict resolution protocol when upstream artifacts contradict.
- Glossary consumption is advisory, not enforced.
- No FR category checklist (error handling, auth, pagination, audit, idempotency).

**What can fall through**: Error handling requirements. Authorization requirements. Pagination/filtering requirements. Audit logging requirements. Idempotency requirements. Data validation requirements.

### 2.7 Step 04 -> Step 05: FR-to-API Mapping

**Risk**: MEDIUM

The prompt has good coverage checks (line 71) but:
- No distinction between "external" and "internal" FRs.
- No common API pattern guidance (pagination, filtering, error response format).
- Schema allows minimally useful API contracts (no path, method, errors, or trace required).

**What can fall through**: FRs requiring internal-only implementation with no API surface (no guidance on documenting these). Common API patterns that should be standardized across endpoints.

### 2.8 Step 04 -> Step 06: FR-to-Invariant Derivation

**Risk**: MEDIUM-HIGH

The prompt has the widest upstream surface (7 sources) and strong coverage checks, but:
- No jsonlogic/CEL examples make expression authoring unreliable.
- Glossary lifecycle states referenced in prompt do not exist in glossary schema.
- Required `policy_ref` may be impossible to populate for data integrity invariants.

**What can fall through**: State transition invariants (glossary lacks lifecycle state structure). Data integrity invariants that the LLM cannot express in jsonlogic/CEL. Cross-entity invariants.

### 2.9 Steps 01-06 -> Step 07: NFR Derivation

**Risk**: MEDIUM-HIGH

The prompt has the widest extraction intent (8 sources) but:
- No NFR category coverage checklist methodology.
- No tech stack coherence for measurement methods.
- Delivery baseline consumption is prompt-documented but not reflected in downstream_consumers.

**What can fall through**: Security NFRs from trust boundaries. Availability/durability NFRs implied by architecture choices. Cost NFRs. Measurement feasibility validation.

---

## 3. Coverage Gap Matrix

| Requirement Category | Seed Template | Step 00 | Step 01 | Step 02 | Step 02a | Step 03 | Step 04 | Step 05 | Step 06 | Step 07 |
|---|---|---|---|---|---|---|---|---|---|---|
| Business goals | overview 2.4 | goals, success_metrics | -- | -- | -- | -- | -- | -- | -- | -- |
| User personas/JTBD | overview 2.2-2.3 | user_segments | -- | -- | -- | -- | -- | -- | -- | -- |
| Scope boundaries | overview 3.1-3.2 | in/out_of_scope | scope field | -- | -- | -- | -- | -- | -- | -- |
| Success metrics | overview 2.4 | success_metrics | -- | -- | -- | -- | -- | -- | -- | nfrs |
| Compliance/regulatory | tech 4.1 (partial) | assumptions (partial) | -- | -- | compliance | -- | -- | -- | invariants (partial) | security NFRs |
| Data model/entities | overview 5.1-5.2 | -- | -- | -- | -- | terms (partial) | -- | -- | -- | -- |
| Data lifecycle/retention | **NONE** | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Error handling philosophy | **NONE** | -- | -- | -- | -- | -- | implicit only | errors | invariants | -- |
| Security boundaries | tech 4.1 | assumptions (partial) | -- | trust_boundary | -- | -- | preconditions | security | access invariants | security NFRs |
| Deployment topology | tech 4.2 | -- | -- | components | environments | -- | -- | -- | -- | -- |
| Resilience/recovery | tech 4.3 | risks (partial) | -- | reliability | -- | -- | -- | -- | -- | availability NFRs |
| Integration inventory | tech 3.x | -- | -- | external components | -- | -- | -- | APIs | -- | -- |
| Operational requirements | **NONE** | -- | -- | -- | -- | -- | -- | -- | -- | NFRs (partial) |
| Monitoring/observability | **NONE** | -- | -- | -- | -- | -- | -- | -- | -- | measurement_method |
| Configuration management | **NONE** | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Migration/upgrade strategy | **NONE** | -- | -- | -- | -- | -- | -- | -- | -- | -- |
| Cross-cutting auth/authz | tech 4.1 (partial) | -- | -- | auth on connections | -- | -- | preconditions (partial) | security | access invariants | security NFRs |
| Performance targets | overview 2.4 | success_metrics | -- | -- | -- | -- | -- | -- | -- | latency/throughput NFRs |
| Cost constraints | overview 3.3 | constraints | -- | -- | -- | -- | -- | -- | -- | cost NFRs |

**Categories with no dedicated home in Steps 00-07:**
1. Data lifecycle/retention requirements
2. Configuration management strategy
3. Migration/upgrade strategy
4. Operational runbook requirements (on-call, incident response)
5. Monitoring/observability requirements (partially in NFR measurement_method)
6. Error taxonomy/error code strategy

---

## 4. Lossy Transitions (Ranked by Risk)

| Rank | Transition | Risk | Root Cause | Impact |
|---|---|---|---|---|
| 1 | Step 03/01 -> Step 04 (Capability to FR) | HIGH | No implicit FR discovery framework; no conflict resolution; no category checklist | Missing FRs propagate to 13 downstream steps; fixtures, invariants, NFRs all inherit gaps |
| 2 | Seed -> Step 00 (Seed to Charter) | MEDIUM-HIGH | Extraction intent narrower than seed template structure; schema does not require scope/risks | Root artifact gaps are unfixable downstream; every later step inherits |
| 3 | Steps 00-02a -> Step 03 (Vocabulary) | MEDIUM-HIGH | No systematic extraction; no downstream enforcement; schema lacks lifecycle states | Terminological inconsistency across all downstream steps; invariant discovery hampered |
| 4 | Steps 01-06 -> Step 07 (NFR Derivation) | MEDIUM-HIGH | No category coverage checklist; measurement feasibility unvalidated | Missing NFRs leave system properties unmonitored |
| 5 | Step 04 -> Step 06 (FR to Invariant) | MEDIUM-HIGH | No expression examples; glossary lifecycle gap; required policy_ref barrier | Missing invariants leave data integrity unguarded |
| 6 | Step 01 -> Step 02 (Capability to Architecture) | MEDIUM | No tradeoff methodology; no data model home; NFR implications not captured | Architecture decisions made without formal rationale |
| 7 | Step 04 -> Step 05 (FR to API) | MEDIUM | No external/internal FR distinction; no common patterns | API contracts may miss standard patterns |
| 8 | Step 00 -> Step 01 (Charter to Capabilities) | MEDIUM | JTBD not checked in coverage; no cross-cutting guidance | Cross-cutting capabilities missed |
| 9 | Step 02 -> Step 02a (Architecture to Delivery) | LOW-MEDIUM | Narrow downstream consumption limits value | Delivery info invisible to Steps 04-07 |

---

## 5. Glossary and Tech-Stack Coherence Assessment

### Glossary Coherence

**Is the glossary actually consumed?**

Per downstream_consumers: Step 03 feeds Steps 04, 05, and 07. Steps 06 is NOT listed as a consumer despite prompt_06 referencing glossary extensively.

| Step | Prompt References Glossary? | Schema Enforces Glossary Use? | Validator Enforces? |
|---|---|---|---|
| 04 (FRs) | Yes (line 46: "anchor terms") | No | No |
| 05 (APIs) | Yes (line 74: "align with term_id values") | No | No |
| 06 (Invariants) | Yes (line 51: "entity definitions, lifecycle states") | No | No |
| 07 (NFRs) | Yes (line 52: "Align names/units with glossary") | No | No |

**Assessment**: The glossary is **aspirational, not enforced**. Every downstream prompt tells the LLM to use glossary terms, but no schema field requires glossary term_ids, and no validator checks terminological alignment. The glossary is structurally decorative -- it has no machine-enforceable teeth.

### Tech-Stack Coherence

| Step | References Tech Stack? | Validates Against seed_tech_stack? | Validates Against System Sketch? |
|---|---|---|---|
| 00 (Charter) | Yes (required seed) | Extraction intent only | N/A |
| 01 (Capabilities) | No (not required) | No | No |
| 02 (System Sketch) | Yes (required seed) | Coverage Closure line 87 | N/A (is the system sketch) |
| 02a (Delivery Baseline) | Yes (required seed) | Extraction intent only | Coverage Closure line 79 |
| 03 (Glossary) | Extraction Intent only | No | No |
| 04 (FRs) | Extraction Intent only | No | No |
| 05 (APIs) | Extraction Intent only | No | No |
| 06 (Invariants) | Extraction Intent only | No | No |
| 07 (NFRs) | Extraction Intent only | No | No |

**Assessment**: Tech stack coherence is checked at Step 02 (Coverage Closure) and partially at Step 02a. After that, no step validates that its outputs are consistent with the declared tech stack. An NFR could specify a "Grafana dashboard query" measurement method while the tech stack specifies no Grafana deployment. An API could specify gRPC protocol while seed_tech_stack specifies HTTP-only infrastructure. These contradictions are undetectable.

---

## 6. Findings

### R2-B-001: Step Prompts Don't Guide Extraction of Compliance, Data Lifecycle, and Operational Requirements from Seed Docs
- **Severity**: HIGH
- **Target**: `prompts/prompt_00_project_charter.md`, `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_07_nfrs.md`
- **Evidence**: seed_overview has no compliance section. seed_tech_stack buries compliance under "Security Boundary" (section 4.1). Neither template has a data retention/deletion section. Neither has an operational requirements section (monitoring, on-call, incident response).
- **Impact**: Requirements in these categories are never systematically elicited.
- **Reframing**: Seed templates are PRD/system design input, not specs. The toolkit's job is to surface and fill gaps through pipeline steps, not to require seeds to be exhaustive. The real issue is that **step prompts don't guide LLMs to extract these requirement categories from unstructured seed input**. Step 00 should guide extraction of compliance/regulatory mentions. Step 04 should have implicit FR discovery for data lifecycle. Step 07 should have an NFR category checklist that includes operational requirements. This is a prompt synthesis quality issue (AUDIT-001 territory), not a seed template issue.
- **Proposed Fix**: Enrich step prompts with extraction guidance and category checklists for compliance, data lifecycle, and operational requirements. Do NOT add rigid sections to seed templates — seeds should remain flexible PRD/system design documents.

### R2-B-002: Step 00 Extraction Intent Is Narrower Than seed_tech_stack Template Structure
- **Severity**: MEDIUM
- **Target**: `prompts/prompt_00_project_charter.md` lines 55-56
- **Evidence**: Extraction intent for seed_tech_stack says "Hardware/legacy constraints for out_of_scope or assumptions; technology constraints informing risks." But seed_tech_stack contains security boundaries (4.1), distribution constraints (4.2), resilience requirements (4.3), and dependency inventory (5.x) -- none of which are mentioned in the extraction intent.
- **Impact**: The LLM may extract only hardware/legacy constraints from seed_tech_stack, missing security posture, deployment model, and resilience requirements that should inform the charter.
- **Proposed Fix**: Expand extraction intent to: "Security boundary requirements for constraints and risks; distribution/delivery model for assumptions; resilience requirements for risks; dependency inventory for assumptions and integration scope."

### R2-B-003: Schema Does Not Require in_scope, out_of_scope, assumptions, or risks in Step 00
- **Severity**: HIGH
- **Target**: `schema/00_charter.schema.json` lines 182-187
- **Evidence**: Schema requires only `problem_statement`, `success_metrics`, `stakeholders`, `user_segments`. The prompt's completeness checklist (lines 99-106) treats `in_scope` (min 3 items), `out_of_scope`, `assumptions`, and `risks` as essential, but the schema allows a valid charter without any of these fields.
- **Impact**: A charter can pass schema validation with no scope boundaries, no risk register, and no assumptions documented -- undermining the root anchor for every downstream step.
- **Proposed Fix**: Add `in_scope`, `out_of_scope`, `assumptions`, and `risks` to the schema's `required` array. These are foundational fields for downstream traceability.

### R2-B-004: Step 01 Coverage Closure Does Not Check user_segments JTBD
- **Severity**: MEDIUM
- **Target**: `prompts/prompt_01_capabilities.md` lines 78-81
- **Evidence**: Coverage Closure checks "Every goal and success metric in 00_charter.json" but does not check `user_segments[].jobs_to_be_done`. A JTBD like "quickly find relevant products" may imply a search capability that no charter goal explicitly mentions.
- **Impact**: Capabilities implied by user needs but not by business goals can be silently omitted.
- **Proposed Fix**: Add to Coverage Closure: "Every `jobs_to_be_done` entry in `spec/00_charter.json` `user_segments` is addressed by >=1 `capability_id`, OR explicitly documented as out-of-scope."

### R2-B-005: Step 01 Lacks Cross-Cutting Capability Discovery Guidance
- **Severity**: MEDIUM
- **Target**: `prompts/prompt_01_capabilities.md`
- **Evidence**: No guidance on identifying cross-cutting capabilities (security, observability, audit logging, error handling) that apply to multiple business capabilities. The prompt says "each is a single verb-driven behavior" (line 97) but cross-cutting concerns do not decompose into single-behavior capabilities cleanly.
- **Impact**: Cross-cutting capabilities are left to LLM inference, leading to inconsistent coverage across runs.
- **Proposed Fix**: Add a "Cross-Cutting Capability Checklist" section: "For each of the following, determine if a dedicated capability is needed: (1) Authentication/authorization, (2) Audit logging, (3) Error handling/reporting, (4) Monitoring/health checks, (5) Rate limiting/throttling, (6) Data backup/recovery."

### R2-B-006: Step 02a Has Near-Zero Downstream Consumption (Feeds Only Step 12)
- **Severity**: MEDIUM
- **Target**: `tools/step_order.json` downstream_consumers["02a"]
- **Evidence**: downstream_consumers shows 02a feeds ONLY Step 12 (CI Gates). Steps 04-07 prompts reference 02a in their Extraction Intent but 02a is not listed as feeding them in downstream_consumers. Meanwhile, allowed_upstream_dependencies does include 02a for Steps 04-07, so the dependency is structurally allowed but not documented as consumed.
- **Impact**: Delivery baseline information (environments, monitoring tools, compliance labels) is captured but then invisible to the steps that most need it (FRs for feasibility, NFRs for measurement methods, Invariants for environment scoping).
- **Proposed Fix**: Update downstream_consumers to reflect actual consumption: add "04", "05", "06", "07" to downstream_consumers["02a"] if the extraction intents in those prompts are meant to be consumed. Alternatively, remove 02a from those prompts' Extraction Intent if the consumption is not intended.

### R2-B-007: Glossary Is Structurally Decorative -- No Machine Enforcement of Term Usage
- **Severity**: HIGH
- **Target**: All prompts for Steps 04-07; no validator
- **Evidence**: Every downstream prompt tells the LLM to align with glossary terms, but: (1) No schema field in Steps 04-07 requires glossary term_id references in text fields. (2) No validator checks that FR statements, API names, or NFR metrics use glossary-defined terms. (3) The canonical_lint and canonical_integrity checks validate canonical registry refs but not glossary term usage in free-text fields.
- **Impact**: Terminological drift across the spec chain. An FR can say "user" while the glossary defines "end-user" and the API uses "customer" -- all valid, all inconsistent, all undetectable.
- **Proposed Fix**: Either (a) add a `term_refs` field to FR, API, and NFR schemas that references glossary term_ids, with a validator that checks coverage, or (b) add a lint rule that scans free-text fields in Steps 04-07 for terms that should match glossary entries.

### R2-B-008: Step 04 Lacks Implicit Requirement Discovery Framework
- **Severity**: HIGH (corroborates AUDIT-003)
- **Target**: `prompts/prompt_04_functional_requirements.md`
- **Evidence**: The prompt says to "Build a private Context Ledger of candidate FRs" (line 59) but provides no checklist of FR categories to discover beyond what capabilities state explicitly. For every capability, standard production requirements exist (error handling, authorization, input validation, audit logging, pagination, idempotency) that the prompt does not guide the LLM to discover.
- **Impact**: Step 04 feeds 13 downstream steps. Missing FRs at this stage create phantom coverage -- invariants, APIs, fixtures, and NFRs all assume FRs are complete.
- **Proposed Fix**: Add "Implicit FR Discovery Checklist" to Step 04: "For each capability, evaluate: (1) Error handling: what happens on invalid input, timeout, downstream failure? (2) Authorization: who can exercise this capability? (3) Input validation: what constraints apply to inputs? (4) Audit: does this capability require an audit trail? (5) Idempotency: can this operation be safely retried? (6) Pagination: if this returns a list, how is it paginated? (7) Concurrency: what happens with simultaneous requests?"

### R2-B-009: Step 06 References Glossary Lifecycle States That Do Not Exist in Schema
- **Severity**: MEDIUM
- **Target**: `prompts/prompt_06_invariants.md` line 51, line 56, line 72
- **Evidence**: Prompt says to derive "state transition invariants for entities with lifecycle stages defined in the glossary" (line 56) and the Self-Audit Gate says "if glossary defines entities with lifecycle states, state transition invariants MUST exist" (line 72). However, the glossary schema (03_glossary.schema.json) has no `lifecycle_states` field. Terms have only `term_id`, `term`, `definition`, `domain`, `units`.
- **Impact**: The prompt directs the LLM to extract structure that does not exist, leading to either confusion (LLM ignores the instruction) or hallucination (LLM invents lifecycle states from free-text definitions).
- **Proposed Fix**: Either (a) add a `lifecycle_states` field to the glossary term schema for entity-type terms, or (b) rewrite prompt_06 to say "derive state transition invariants from entity state fields described in FR preconditions/postconditions" instead of referencing non-existent glossary structure.

### R2-B-010: Step 06 Output Contract Contradicts Its Own Guidance
- **Severity**: LOW
- **Target**: `prompts/prompt_06_invariants.md` lines 118, 177-180
- **Evidence**: Line 118 says "DO NOT use `text` language unless absolutely necessary." The Output Contract example (lines 177-180) uses `language: "text"` with `expression: "request.authenticated == true"`. This same expression could be written in CEL.
- **Impact**: LLMs learn from examples. An example using `text` language contradicts the guidance to use jsonlogic/CEL, making LLMs more likely to produce text-language invariants.
- **Proposed Fix**: Change the Output Contract example to use `language: "cel"` with `expression: "request.authenticated == true"` or provide a jsonlogic equivalent.

### R2-B-011: Step 07 NFR Output Contract Uses Generic measurement_method
- **Severity**: LOW
- **Target**: `prompts/prompt_07_nfrs.md` line 191
- **Evidence**: The Output Contract example uses `measurement_method: "automated monitoring"` (line 191). The prompt itself says measurement_method "MUST reference a specific tool, query, or dashboard endpoint (not generic phrases like 'automated monitoring')" (line 52). The example violates the prompt's own guidance.
- **Impact**: LLMs learn from examples. This example teaches the exact anti-pattern the prompt prohibits.
- **Proposed Fix**: Change to `measurement_method: "PromQL: histogram_quantile(0.95, rate(login_duration_seconds_bucket[5m]))"` or similar concrete example.

### R2-B-012: No Prompt Has Conflict Resolution Protocol for Contradicting Upstream Inputs
- **Severity**: HIGH (corroborates AUDIT-002)
- **Target**: All prompts for Steps 00-07
- **Evidence**: Every prompt has "Gap Questions" for missing information but none has guidance for contradictory information. Examples: charter says "SOC2 compliant" but no capability addresses audit logging; seed_tech_stack says "single binary" but capability requires message queue; FR says "respond in < 200ms" but system sketch has 3 network hops.
- **Impact**: LLMs silently resolve contradictions by picking one input, propagating potentially incorrect assumptions through all downstream steps.
- **Proposed Fix**: Add a "Conflict Resolution" protocol to shared_expectations.md: "When two upstream artifacts contradict: (1) Identify the conflict explicitly. (2) Apply upstream precedence: seed > charter > capabilities > architecture > delivery > glossary. (3) If the conflict is between same-level artifacts, add a Gap Question. (4) Never silently resolve -- surface every conflict."

### R2-B-013: Traceability Is Required by Prompt but Optional in Some Schemas
- **Severity**: MEDIUM
- **Target**: `schema/05_interface_contracts.schema.json`, prompt guidance
- **Evidence**: Step 05 prompt says "trace links to FRs/capabilities that justify the API" (line 95) and Coverage Closure requires trace entries (line 72). But the schema does NOT require `trace` on individual API objects -- only `api_id`, `name`, `version`, `protocol`, `owner`, and `interface_ref` are required (schema lines 170-177). A valid API contract can have zero trace entries.
- **Impact**: A schema-valid but trace-free API contract passes validation but breaks the integrity chain. Downstream steps (fixtures, NFRs) cannot determine which FRs an API implements.
- **Proposed Fix**: Add `trace` to the required array in the API item schema: `"required": ["api_id", "name", "version", "protocol", "owner", "interface_ref", "trace"]`.

### R2-B-014: Step 04 Schema Requires minItems:2 for acceptance_criteria but Prompt Says >=1
- **Severity**: LOW
- **Target**: `prompts/prompt_04_functional_requirements.md` line 74, `schema/04_fr_list.schema.json` line 46
- **Evidence**: Self-Audit Gate says "Each FR has >=1 acceptance criterion" (line 74). Schema requires `minItems: 2` for acceptance_criteria (schema line 46). The schema is stricter.
- **Impact**: Minor confusion for LLMs that read the prompt guidance but produce FRs with only 1 criterion, which then fail schema validation.
- **Proposed Fix**: Update prompt Self-Audit Gate to say "Each FR has >=2 acceptance criteria" to match schema.

### R2-B-015: No Step Validates Tech Stack Coherence After Step 02
- **Severity**: MEDIUM
- **Target**: Prompts for Steps 04-07
- **Evidence**: Step 02 Coverage Closure validates tech choices against seed_tech_stack (prompt line 87). After that, no step checks that its outputs align with the declared tech stack. NFR measurement methods can reference tools not in the stack. API protocols can contradict system sketch connection protocols. Invariant scope can reference components that changed.
- **Impact**: Tech stack drift accumulates silently across Steps 04-07. The chain captures initial tech decisions but does not validate ongoing coherence.
- **Proposed Fix**: Add to shared_expectations or to individual step Coverage Closures: "All technology references (protocols, tools, frameworks, infrastructure) in this artifact are consistent with `spec/02_system_sketch.json` components and `spec/02a_delivery_baseline.json` environments."

### R2-B-016: seed_manifest step_requirements Stops at Step 04 -- Steps 05-07 Have No Seed Requirements
- **Severity**: LOW
- **Target**: `spec/common/seed_manifest.json` lines 38-57
- **Evidence**: step_requirements defines seed requirements for Steps 00-04 only. Steps 05, 06, and 07 have no seed requirements. While these steps primarily consume upstream spec artifacts, seed documents remain relevant (e.g., seed_tech_stack security boundaries inform invariants and NFRs).
- **Impact**: Steps 05-07 are not instructed to verify seed documents are current before generating. This is low severity because these steps primarily derive from spec artifacts which themselves derive from seeds, but the indirect dependency means seed changes may not propagate.
- **Proposed Fix**: Consider adding seed_tech_stack as optional (not required) context for Steps 05-07 in seed_manifest.json step_requirements.

---

## Summary

The seed-to-spec integrity chain has strong structural bones -- every prompt has extraction intents, coverage closure checks, and self-audit gates. The most significant systemic issues are:

1. **The chain is only as strong as its root**: Step prompts don't guide extraction of compliance, data lifecycle, and operational requirements from seed docs (R2-B-001). These gaps propagate irreversibly.

2. **Step 04 is the critical bottleneck**: It feeds 13 downstream steps but lacks an implicit requirement discovery framework (R2-B-008, corroborating AUDIT-003). Missing FRs at this stage are nearly impossible to recover downstream.

3. **Glossary is decorative, not enforced**: No schema or validator checks that downstream steps use glossary terms (R2-B-007). The entire terminological consistency mechanism is LLM-self-audited.

4. **Conflict resolution is absent everywhere**: No prompt addresses contradicting upstream inputs (R2-B-012, corroborating AUDIT-002). LLMs silently pick one interpretation.

5. **Schema-prompt gaps create false confidence**: Several schemas are more lenient than prompts suggest (R2-B-003, R2-B-013, R2-B-014), meaning artifacts can pass validation while missing prompt-required content.

6. **Tech stack coherence degrades after Step 02**: No downstream step validates that its outputs align with declared technology choices (R2-B-015).
