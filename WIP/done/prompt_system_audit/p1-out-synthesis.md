# P1-B: Synthesis Guidance & Step Intent -- Findings

## Summary
- Total findings: 18
- Critical: 2 | High: 5 | Medium: 7 | Low: 3 | Info: 1

## Step Assessments

### Step 00: Charter
- **Intent**: Establish the authoritative project charter capturing business problem, users, constraints, and success criteria in falsifiable language.
- **Synthesis Challenge**: Extract structured, quantified business requirements from unstructured seed documents. The LLM must transform narrative product briefs into measurable metrics, distinct stakeholder needs, and explicit scope boundaries while avoiding solutioneering.
- **Guidance Quality**: STRONG
- **Missing Guidance**: None significant. The prompt includes Operating Flow with a private Context Ledger, Coverage Closure checklist, ambiguity scrub rules (replace vague terms with quantifiable targets), and field-by-field guidance. It explicitly warns against solutioneering and vague metrics.
- **Anti-Pattern Coverage**: Strong. Warns against "business speak" (optimize, improve), vague metrics, implicit assumptions, missing stakeholders, scope creep, and TBDs in critical sections.

### Step 01: Capabilities
- **Intent**: Translate charter goals into a catalog of verb-object capabilities with explicit scope boundaries and operating conditions.
- **Synthesis Challenge**: Decompose business goals into single, testable behaviors without creating overlaps or leaving gaps. The LLM must decide granularity (too coarse = untestable, too fine = noise) and distinguish in-scope from future/out capabilities.
- **Guidance Quality**: STRONG
- **Missing Guidance**: No guidance on how to determine the right GRANULARITY of capability decomposition. The prompt says "single verb-driven behavior" but does not explain when a behavior is too broad (e.g., "manage users") vs appropriately scoped (e.g., "create user account"). No guidance on handling charter goals that map to cross-cutting concerns (e.g., "security" or "performance") rather than discrete capabilities.
- **Anti-Pattern Coverage**: Good. Warns against marketing fluff, hidden dependencies, implementation leak, duplicate IDs, undefined I/O. Explicitly bans generic verbs ("manage", "handle").

### Step 02: System Sketch
- **Intent**: Build a lightweight architecture map showing components, ownership, technology choices, and integration contracts.
- **Synthesis Challenge**: Derive the right set of components and connections from capabilities without over-engineering. The LLM must make architectural decisions (how many services? what protocols? where are trust boundaries?) that are non-trivial engineering judgment calls.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to decide between monolith vs microservice, when to introduce a queue vs direct call, or when a capability warrants its own component vs being folded into an existing one. The prompt says "model only the necessary components" but provides no heuristic for determining necessity. No guidance on handling conflicting upstream inputs (e.g., charter says "simple" but capabilities imply complex integration patterns).
- **Anti-Pattern Coverage**: Good for connection-level concerns (trust boundaries, auth, rate limits). Weak on component-level architectural anti-patterns (over-splitting, missing shared services).

### Step 02a: Delivery Baseline
- **Intent**: Capture minimum delivery infrastructure (environments, CI, compliance) needed to move from spec to running code safely.
- **Synthesis Challenge**: Moderate. Derive environment configurations and CI gates from upstream constraints. The main challenge is completeness -- ensuring no external dependency or secret is missed.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on how to handle projects where delivery infrastructure is genuinely unknown or in flux. The parity rule (staging must match prod) is good but lacks guidance on when deviations are acceptable and how to document them. No reasoning guidance for choosing between different CI gate configurations.
- **Anti-Pattern Coverage**: Good. Warns against empty shells, manual gates, secret values, staging drift, optional compliance.

### Step 03: Glossary
- **Intent**: Create a single vocabulary that removes ambiguity across stakeholders by codifying domain terms, units, and context.
- **Synthesis Challenge**: Identify all domain-significant terms from upstream artifacts and write definitions that are precise enough for engineers but accessible enough for business stakeholders. The hard problem is deciding which terms NEED defining (not everything is ambiguous) and avoiding circular definitions.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to determine whether a term is "domain-significant" enough to include vs common English that needs no definition. No guidance on resolving cases where upstream artifacts use the same word with different meanings (a common source of specification bugs). The prompt says "normalize to one canonical term_id per concept" but gives no reasoning framework for when two terms are actually the same concept vs distinct concepts.
- **Anti-Pattern Coverage**: Good. Warns against circular definitions, missing units, duplicates, drift, broadness.

### Step 04: Functional Requirements
- **Intent**: Turn capabilities into falsifiable statements of system behavior with acceptance criteria and trace links.
- **Synthesis Challenge**: HIGH. This is one of the hardest synthesis steps. The LLM must decompose each capability into one-behavior FRs, write outcome-oriented (not implementation-oriented) statements, and create acceptance criteria that are specific enough to drive test fixtures. The key challenge is achieving the right level of specificity: too abstract and the FR is unfalsifiable; too concrete and it prescribes implementation.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to determine the right granularity of FRs. The prompt says "one behavior per FR" but does not explain how to decide what constitutes "one behavior" (e.g., is "user logs in" one behavior or three: validate credentials, create session, return token?). No guidance on deriving IMPLICIT requirements -- behaviors that the charter/capabilities assume but do not state (e.g., error handling, pagination, idempotency). No guidance on handling conflicting upstream signals (e.g., capability says "fast" but charter has no latency constraint).
- **Anti-Pattern Coverage**: Good. Warns against bundling, vague criteria, missing links, implementation leak. The "Given-When-Then" suggestion is useful but not expanded into a reasoning framework.

### Step 05: Interface Contracts
- **Intent**: Document external-facing contracts (routes, schemas, security, versioning) that expose capabilities.
- **Synthesis Challenge**: HIGH. Translate FRs into concrete API shapes with correct HTTP semantics, error enumerations, security models, and versioning. The LLM must make REST design decisions (resource naming, nesting, pagination patterns, error schemas) that require domain expertise.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on API DESIGN PRINCIPLES -- how to decide resource naming, when to use path params vs query params, how to structure error responses consistently, when to use pagination, how to handle bulk operations. The prompt tells the LLM WHAT to output but not HOW to reason about good API design. No guidance on handling FRs that do not map cleanly to CRUD operations (e.g., complex workflows, async operations, file uploads).
- **Anti-Pattern Coverage**: Moderate. Warns against sync drift, mixed concerns, empty errors, bad versioning. Missing warnings about over-engineering (too many endpoints) or under-engineering (god endpoints).

### Step 06: Invariants & Rules
- **Intent**: Capture non-negotiable truths, guardrails, and data relationships the system must uphold regardless of implementation.
- **Synthesis Challenge**: HIGH. The LLM must identify invariants that are NOT explicitly stated in upstream specs but are implied by them (e.g., "if we have a login system, then sessions must expire"). It must also translate business rules into executable expressions (jsonlogic/CEL), which requires understanding both the business domain and expression language syntax.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: The prompt lists categories of invariants to consider (data integrity, state transitions, access boundaries, ordering guarantees) -- this is good. However, it provides no reasoning framework for DISCOVERING implicit invariants. The instruction to "go beyond FR-derived negative cases" is correct but lacks a systematic method. No guidance on how to scope invariants to avoid false positives in testing. No examples of jsonlogic or CEL expressions for common patterns.
- **Anti-Pattern Coverage**: Good. Warns against empty logic, severity misalignment, false positives, bad IDs.

### Step 07: NFRs
- **Intent**: Define measurable performance, reliability, security, and operational targets.
- **Synthesis Challenge**: MEDIUM-HIGH. The LLM must derive numeric targets from qualitative charter goals, align units with the glossary, and specify concrete measurement methods. The hard problem is knowing WHAT a realistic target is (e.g., "200ms p95" vs "500ms p95") without benchmarking data.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on how to set REALISTIC targets when baseline data is absent. The prompt says to include measurement_method that "specifies a concrete query, tool, or dashboard endpoint" but the LLM may not know what monitoring tools the organization uses. No guidance on handling trade-offs between NFRs (e.g., latency vs cost, availability vs consistency). No guidance on which NFR categories are MANDATORY for a given system type vs optional.
- **Anti-Pattern Coverage**: Good. Warns against qualitative targets, immeasurable metrics, prod-only targets, orphans, duplicates.

### Step 08: Fixtures
- **Intent**: Supply deterministic inputs and expected outputs that exercise functional and non-functional behaviors.
- **Synthesis Challenge**: MEDIUM. The LLM must derive concrete test data from abstract FRs and interface contracts. The main challenge is creating MINIMAL but REPRESENTATIVE fixtures that cover happy paths, edges, and failures without being exhaustive.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to derive concrete test data values (e.g., what makes a good test email address, a good boundary value, a realistic payload size). No guidance on fixture ORDERING or dependency (some fixtures may require setup data from other fixtures). No guidance on handling non-deterministic behaviors in fixtures (timestamps, random IDs).
- **Anti-Pattern Coverage**: Good. Warns against orphans, stale docs, complexity, drift. The "Self-Correction" instruction to verify target IDs exist is valuable.

### Step 09: Implementation Plan
- **Intent**: Translate the validated spec into an executable delivery roadmap with technology choices, sequencing, risks, and migration strategy.
- **Synthesis Challenge**: MEDIUM-HIGH. The LLM must synthesize all upstream specs into a coherent delivery plan, making sequencing decisions (what builds on what), technology selections with rationale, and risk assessments. The challenge is balancing completeness with actionability.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to determine milestone sequencing (what criteria make one milestone precede another? dependency? risk? value?). No guidance on estimating effort or timeline feasibility. No guidance on handling cases where the tech stack from upstream is under-specified or contradictory. The "Cross-Check" instruction to verify tech_stack against capabilities is good but does not explain what to do when a capability implies a technology not listed in seeds.
- **Anti-Pattern Coverage**: Good. Warns against grab-bag tech stacks, vague milestones, surprise migrations, blockers.

### Step 10: Governance
- **Intent**: Set policies for change control, versioning, reviewer expectations, and how code changes reference spec artifacts.
- **Synthesis Challenge**: MEDIUM. The LLM must derive governance rules from organizational constraints and upstream specs. The challenge is making rules enforceable (regex patterns, boolean flags) rather than advisory.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on handling organizational context that is not captured in upstream specs (e.g., team size, review culture, release cadence). The prompt asks Gap Questions for these but does not explain how to synthesize governance rules from organizational signals. No guidance on balancing strictness (blocks velocity) vs leniency (allows drift).
- **Anti-Pattern Coverage**: Good. Warns against implicit rules, friction, silos, breaking automation.

### Step 11: Red-Team / Failure Modes
- **Intent**: Proactively identify security threats, failure modes, and edge cases with strict traceability.
- **Synthesis Challenge**: HIGH. This is one of the hardest reasoning steps. The LLM must THINK LIKE AN ATTACKER and identify system-specific (not generic) threats. It must understand the architecture well enough to identify realistic attack vectors, then link each threat to specific APIs/components and propose concrete mitigations.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The prompt is one of the strongest. It has a distinct operating flow (Attack -> Trace -> Mitigate), a threat taxonomy, concrete weak-vs-strong examples, and explicit coverage rules. The "Shift Left" philosophy section effectively communicates the reasoning approach. Minor gap: no guidance on prioritizing threats when the system has many attack surfaces.
- **Anti-Pattern Coverage**: Excellent. The weak/strong examples table is highly effective. Warns against generic lists, empty targets, vague mitigations, ignoring edge cases.

### Step 12: CI Gates
- **Intent**: Translate governance rules and fixture expectations into enforceable CI automation.
- **Synthesis Challenge**: MEDIUM. The LLM must map governance PR rules and quality expectations to concrete CI jobs with dependencies. The DAG construction is non-trivial but the input is well-constrained.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on how to reason about job parallelism vs sequencing (when is parallelism safe?). No guidance on handling CI environments with different capabilities (e.g., GPU runners for ML tests). The tooling context section listing available CLI tools is valuable.
- **Anti-Pattern Coverage**: Good. Warns against vague steps, race conditions, perma-red, drift. The hallucination vectors section is unique and useful.

### Step 13: Extension Generator
- **Intent**: Identify complex domains requiring dedicated extension specifications beyond core step coverage.
- **Synthesis Challenge**: HIGH. The LLM must make a judgment call about WHEN a domain is complex enough to warrant its own spec vs being adequately covered by existing steps. The ">=3 dedicated schema sections" heuristic is good but still requires architectural judgment.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The "Analyze -> Filter -> Plan" flow is well-structured. The domain-specific questions (Data Storage, Security, AI/ML, Infrastructure, Integration) provide concrete reasoning triggers. Minor gap: no guidance on handling borderline cases where a domain might or might not need an extension.
- **Anti-Pattern Coverage**: Good. Warns against over-splicing, library bloat, redefinition, ignoring flow.

### Step 13a: Completeness Assessment
- **Intent**: Assess completeness of Phase 1 specifications and identify gaps preventing implementation readiness.
- **Synthesis Challenge**: HIGH. The LLM must perform a cross-artifact audit, checking traceability, coverage, and quality across all 13+ specs. The scoring/rating system requires calibrated judgment.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on HOW to calibrate the completeness score -- what does a "7" vs an "8" look like concretely? The scoring deduction rubric ("Missing API=-1.0, Missing NFR=-0.5") is a good start but incomplete. No guidance on distinguishing between "genuinely missing" and "intentionally deferred" when assessing gaps.
- **Anti-Pattern Coverage**: Good. Warns against vagueness, omissions, inflation, isolation.

### Step 14: Roadmap
- **Intent**: Synthesize all specs into a cohesive execution roadmap with user-story-driven milestones and atomic tasks.
- **Synthesis Challenge**: HIGH. The LLM must perform the most complex synthesis in the pipeline: aggregating all 14+ upstream specs into sequenced milestones with tasks, dependencies, and acceptance criteria. The "one milestone = one user story" constraint requires judgment about story granularity.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The 5-step operating flow (Ingest -> Synthesize -> Sequence -> Decompose -> Emit) is well-structured. Field-by-field guidance is extensive. The JIT granularity guidance ("plan immediate next 1-2 milestones in high detail") is practical. Minor gap: no guidance on resolving dependency conflicts between milestones or handling circular dependencies between features.
- **Anti-Pattern Coverage**: Good. The extensive negative constraints section is valuable. Warns against ignoring extensions, redoing Step 09, skipping completeness.

### Step 15: Scaffold Generation
- **Intent**: Generate compile-clean service skeletons and route bindings from the spec.
- **Synthesis Challenge**: MEDIUM. The LLM must map interface contracts to framework-specific route bindings and derive a project skeleton from the tech stack. The challenge is primarily mechanical mapping.
- **Guidance Quality**: ADEQUATE
- **Missing Guidance**: No guidance on handling framework-specific conventions (how to structure a FastAPI app vs an Express app vs a Flask app). The prompt says to map APIs to routes but does not explain how to handle non-REST patterns (WebSocket handlers, event consumers, cron jobs) in the scaffold. No guidance on test scaffold generation (test directory structure, test utilities).
- **Anti-Pattern Coverage**: Moderate. Warns against implicit modules, drift, false green, route drift.

### Step 16: Implementation Context (Trinity Anchor)
- **Intent**: Create the canonical anchor for the Trinity Loop (Plan/Code/Review cycle) with traceable checklist items.
- **Synthesis Challenge**: HIGH. The LLM must synthesize all 16 upstream specs into atomic checklist items with concrete spec references, test expectations, and file patterns. The drift check against active milestone contexts adds coordination complexity.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The field definitions are exhaustive (13 numbered sections). The mandatory operating flow with drift check is well-defined. The forbidden actions list is comprehensive. Gap: no guidance on determining the RIGHT NUMBER of checklist items (too few = incomplete, too many = checklist fatigue).
- **Anti-Pattern Coverage**: Excellent. The "Failure Modes" section with causes and fixes is effective.

### Step 16a: Implementation Planner
- **Intent**: Produce a machine-checkable implementation blueprint using checklist-driven architecture.
- **Synthesis Challenge**: HIGH. The LLM must decompose roadmap tasks into atomic checklist items with spec refs, test expectations, implementation slots, and ambiguity documentation. The roadmap-to-checklist coverage mandate is rigorous.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The checklist-driven architecture is well-explained with explicit rules for atomicity, traceability, and evidence binding. The forbidden actions section is the most comprehensive in the system (structural, content, roadmap coverage, inference, atomicity violations). Minor gap: no guidance on handling tasks that span multiple architectural layers (e.g., "add authentication" touches API, service, and DB layers).
- **Anti-Pattern Coverage**: Excellent. The categorized forbidden actions and failure modes sections are the gold standard in this prompt system.

### Step 16b: Implementation Coder
- **Intent**: Execute the plan by implementing checklist items with evidence capture.
- **Synthesis Challenge**: MEDIUM-HIGH. The LLM must translate plan specifications into actual code while maintaining strict scope boundaries and capturing verbatim evidence. The "Ambiguity Gatekeeper" role requires judgment about when plan ambiguity is blocking vs acceptable.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The requirement-first execution model is well-defined. The evidence binding rules are explicit. Minor gap: no guidance on handling situations where implementing one checklist item reveals that the plan's approach for another item is flawed.
- **Anti-Pattern Coverage**: Excellent. The forbidden actions for code generation, evidence, dependencies, and execution are comprehensive.

### Step 16c: Implementation Reviewer
- **Intent**: Audit implementation for completeness, quality, and adherence to spec.
- **Synthesis Challenge**: HIGH. The LLM must perform an evidence-based audit comparing plan, execution, and actual code. The semantic review (fr_coverage) requires cross-referencing multiple artifacts. The verdict gates are strict.
- **Guidance Quality**: STRONG
- **Missing Guidance**: The audit checklist and red flags sections are well-defined. The rating rubric (0-5 scale with clear criteria) is one of the most calibrated in the system. Minor gap: no guidance on how to handle disagreements between plan intent and implementation approach when both are technically valid.
- **Anti-Pattern Coverage**: Excellent. The "Rubber Stamping" pitfall and mandatory evidence verification are effective safeguards.

---

## Cross-Step Patterns

### What STRONG prompts do differently from THIN ones

**STRONG prompts (11, 13, 14, 16, 16a, 16b, 16c, 00) share these patterns:**

1. **Distinct operating flow with named phases**: Step 11 has "Attack -> Trace -> Mitigate". Step 13 has "Analyze -> Filter -> Plan". Step 14 has "Ingest -> Synthesize -> Sequence -> Decompose -> Emit". Step 16b has "Requirement-First Execution". These named flows communicate HOW to reason, not just WHAT to output.

2. **Concrete weak-vs-strong examples**: Step 11's threat quality table is the best example. It shows the LLM what bad output looks like and what good output looks like side by side, making the quality bar tangible.

3. **Categorized forbidden actions**: Steps 16a, 16b, 16c organize forbidden actions by violation type (structural, content, inference, atomicity). This makes it easy for the LLM to self-check against specific failure modes.

4. **Domain-specific reasoning triggers**: Step 13 lists specific domain questions (Data Storage? Security? AI/ML?). Step 11 has a threat taxonomy with categories. These give the LLM concrete "probes" to use when analyzing the system.

5. **Calibrated rating criteria**: Step 16c's 0-5 scale with specific criteria for each level. Step 13a's scoring deduction rubric. These reduce the subjectivity of quality judgments.

**ADEQUATE prompts (02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 12, 15) share these patterns:**

1. **Generic operating flow**: All use "Synthesize -> Clarify -> Emit" without step-specific reasoning guidance. The private "Context Ledger" / "Coverage Ledger" instruction tells the LLM to build an internal model but does not explain HOW to reason about it.

2. **Rules without reasoning frameworks**: They say "MUST include X when Y" but do not explain how to DISCOVER Y in the first place. For example, Step 06 says "MUST include data integrity constraints implied by entities in glossary" but does not explain how to identify which entities have integrity constraints.

3. **Anti-patterns as lists, not examples**: They list pitfall names (e.g., "Bundling", "Vague Criteria") without showing concrete before/after examples of what the anti-pattern looks like in practice.

4. **No granularity guidance**: None of the ADEQUATE prompts explain how to determine the right level of detail. This is particularly problematic for Steps 04 (FR granularity), 05 (API granularity), and 07 (NFR completeness).

### Key Structural Observations

1. **Boilerplate ratio**: All 22 prompts share approximately 40-50% identical boilerplate (Schema Authority, Path Variables, Role, Task, Seed Order, Output Rules, Hardening Protocol, Canonical Registry, Canonical Binding Rules, Metadata Contract). This mechanical repetition crowds out space for step-specific synthesis guidance.

2. **Role definition is identical for steps 00-10, 15**: "You are a senior specification author and validator." Only Steps 11, 13, 13a, 14, 16, 16a, 16b, 16c have distinct roles (security architect, program manager, auditor, coder, reviewer). The generic role provides no synthesis context.

3. **Operating Flow homogeneity**: 14 of 22 prompts use the identical "Synthesize -> Clarify -> Emit" pattern. The 8 prompts with unique flows (11, 13, 14, 16, 16a, 16b, 16c, and partially 00) are consistently rated STRONG.

---

## Findings

### FINDING-001: Boilerplate Dominates Step-Specific Synthesis Guidance
- **Severity**: HIGH
- **Category**: SYNTHESIS
- **Location**: All 22 prompts
- **Description**: Approximately 40-50% of each prompt is shared boilerplate (Schema Authority, Path Variables, Role, Task, Seed Order, Output Rules, Hardening Protocol, Canonical Registry, Canonical Binding Rules, Metadata Contract). This mechanical repetition dilutes the step-specific synthesis guidance that should be the core value of each prompt. The boilerplate also consumes LLM context window budget that could be used for actual upstream spec content.
- **Evidence**: Steps 00-10 each contain ~6 identical sections totaling approximately 50-70 lines of repeated text. The Canonical Registry + Binding Rules section alone is 15 lines repeated verbatim across all 22 prompts.
- **Recommendation**: Extract shared boilerplate into a `shared_expectations.md` reference document (which already exists but is not used as a substitute). Each prompt should reference the shared document and focus its content budget on step-specific synthesis reasoning.

### FINDING-002: Generic Role Definition for 14 of 22 Steps
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_00_project_charter.md:30`, `prompts/prompt_01_capabilities.md:30`, and 12 other prompts
- **Description**: 14 of 22 prompts use the identical role: "You are a senior specification author and validator." This generic role provides no synthesis context about the specific reasoning challenges of each step. Only 8 prompts have distinct roles (11: security architect, 13: architect + TPM, 13a: auditor, 14: program manager, 16: architect, 16a: architect + planner, 16b: implementation engineer, 16c: technical reviewer).
- **Evidence**: Compare Step 11 role ("You are a senior security architect and 'Red Team' specialist. Your job is to... identify specific threats against the defined interfaces... You must think like an attacker who knows the system internals.") with Step 04 role ("You are a senior specification author and validator. Your job is to emit a single JSON artifact..."). Step 11's role primes adversarial reasoning; Step 04's role primes form-filling.
- **Recommendation**: Each step should have a role definition that primes the specific reasoning mode required. Step 04 should be "You are a senior requirements engineer who decomposes capabilities into falsifiable behavioral specifications." Step 06 should be "You are a systems reliability engineer who identifies the invariants that must hold to prevent data corruption and security breaches."

### FINDING-003: No Guidance on Handling Conflicting Upstream Inputs
- **Severity**: HIGH
- **Category**: SYNTHESIS
- **Location**: All prompts, but most critical at Steps 04 (`prompts/prompt_04_functional_requirements.md`), 05, 06, 07, 09
- **Description**: No prompt in the system explains HOW to handle conflicting upstream inputs. For example: charter says "fast" but no latency target exists; capability says "in scope" but system sketch has no component to deliver it; FR precondition contradicts an API contract's security model. The prompts say "ask Gap Questions" when ambiguous, but do not distinguish between "missing information" (ask) and "contradictory information" (which requires resolution, not just more data).
- **Evidence**: Step 04 says "If any upstream ID cannot be traced: add a gap question (Clarify mode) rather than omitting it" but does not address the case where two upstream specs provide contradictory guidance about the same behavior. Step 09 Cross-Check says "Do not introduce technologies not listed in capabilities" but does not address what to do when the capability implies a technology that contradicts a seed_tech_stack constraint.
- **Recommendation**: Add a "Conflict Resolution" section to at minimum Steps 04, 05, 06, 07, 09 explaining: (1) how to detect conflicts between upstream artifacts, (2) which upstream artifact takes precedence in case of conflict, (3) when to flag the conflict as a Gap Question vs resolving it locally.

### FINDING-004: No Guidance on Identifying Implicit Requirements
- **Severity**: HIGH
- **Category**: SYNTHESIS
- **Location**: Most critically Steps 04 (`prompts/prompt_04_functional_requirements.md:58-63`), 05, 06
- **Description**: No prompt explains HOW to identify implicit requirements not stated in upstream specs. Step 04 says "Build a private Context Ledger of candidate FRs mapped from capabilities" but does not explain how to discover FRs that are IMPLIED but not stated (e.g., error handling, pagination, rate limiting, session management, audit logging). Step 06 is the closest -- it says "MUST include data integrity constraints implied by entities" -- but still lacks a systematic method.
- **Evidence**: Step 04 has no instruction to consider: (a) standard error handling for every happy-path FR, (b) pagination for list endpoints, (c) idempotency for mutating operations, (d) audit logging for sensitive operations, (e) input validation bounds. These are implicit in any production system but absent from typical charter/capability descriptions.
- **Recommendation**: Add an "Implicit Requirements Discovery" section to Steps 04, 05, and 06 with a checklist of common implicit requirements by system type (e.g., "For every mutating FR: consider idempotency, conflict handling, and audit trail. For every list FR: consider pagination, filtering, and sorting. For every authenticated FR: consider session expiry and token refresh.").

### FINDING-005: Operating Flow Homogeneity -- "Synthesize -> Clarify -> Emit" is Underspecified
- **Severity**: HIGH
- **Category**: SYNTHESIS
- **Location**: 14 prompts using "Synthesize -> Clarify -> Emit": Steps 00-10, 12, 15
- **Description**: 14 of 22 prompts use the same "Synthesize -> Clarify -> Emit" operating flow with minor variations. This flow names three phases but does not explain the REASONING within each phase. Compare with Step 11's "Attack -> Trace -> Mitigate" or Step 14's "Ingest -> Synthesize -> Sequence -> Decompose -> Emit" -- these tell the LLM HOW to think at each stage. The generic flow is equivalent to saying "think, then write" which provides no reasoning scaffolding.
- **Evidence**: Step 04's flow: "Build a private Context Ledger... Do not output it. Propose fixture_ref names... Self-audit... Rewrite statements... Emit JSON." This tells the LLM what artifacts to create but not how to reason. Compare with Step 16a: "Context Review -> Scope -> Files -> Checklist -> Implementation Slots -> Drift Check -> Emit" -- each phase has a concrete reasoning action.
- **Recommendation**: Replace the generic flow with step-specific reasoning phases. For Step 04: "Enumerate -> Decompose -> Falsify -> Trace -> Emit" (Enumerate capabilities that need FRs; Decompose each into single behaviors; Rewrite each as falsifiable Given-When-Then; Trace to upstream; Emit). For Step 07: "Extract -> Quantify -> Verify -> Trace -> Emit" (Extract qualitative targets from upstream; Quantify each with numeric value + unit; Verify measurement method exists; Trace to FRs/APIs; Emit).

### FINDING-006: No Granularity Guidance for Key Decomposition Steps
- **Severity**: HIGH
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_05_interface_contracts.md`, `prompts/prompt_07_nfrs.md`
- **Description**: Steps 04, 05, and 07 require the LLM to make decomposition decisions (how many FRs per capability? how many endpoints per FR? how many NFRs per system?) but provide no guidance on the right granularity. This leads to wildly inconsistent outputs: some LLM runs produce 5 FRs for a complex system, others produce 50.
- **Evidence**: Step 04 says "each FR describes exactly one behavior" and "DO NOT bundle multiple behaviors into one FR" but does not define what constitutes "one behavior." Is "User logs in with email and password" one behavior or two (validate credentials + create session)? Is error handling a separate FR or part of the happy-path FR?
- **Recommendation**: Add granularity heuristics: "One FR should be implementable by one developer in one sprint. If an FR requires touching more than 3 components, it may be too broad. If an FR cannot be meaningfully tested in isolation, it may be too narrow. Aim for 3-8 FRs per in-scope capability as a starting point."

### FINDING-007: Step 00 Adequately Extracts from Seed Templates
- **Severity**: INFO
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_00_project_charter.md:43-56`, `seed_templates/seed_overview.md`, `seed_templates/seed_tech_stack.md`
- **Description**: Step 00's extraction guidance aligns well with the seed template structure. The seed_overview.md template has sections for Problem & Users (2.1-2.4), Scope (3.1-3.3), Expected Capabilities (4), Domain Model (5), Timeline (6), and Team (7). Step 00's Context To Ingest and Extraction Intent correctly target these sections. The Heuristics for Completeness section includes "MUST include baselines and measurement_method for success_metrics when seed documents reference historical data" and "Ambiguity scrub: MUST replace any instance of 'improve', 'optimize'..." which directly address the seed templates' coaching prompts.
- **Evidence**: seed_overview.md section 2.4 says "Format: [Metric Name] | Target: [Value] [Unit] | Baseline: [Value]" and Step 00 says "Success metrics include unit+target+measurement_method (baseline where available)." seed_tech_stack.md's constraint sections map to Step 00's "Constraints Source" directive.
- **Recommendation**: One gap remains: seed_overview.md section 5 (Domain Model -- Data Sources, Key Entities, Update Strategy) contains structured information that should feed Step 03 (Glossary) and Step 02 (System Sketch) but is not referenced in Step 00's extraction intent. Step 00 should either extract domain model concepts for its own use or explicitly defer them to downstream steps.

### FINDING-008: No Weak-vs-Strong Examples in 19 of 22 Prompts
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: All prompts except 11, 13, seed_overview.md
- **Description**: Only Step 11 (Red-Team) provides a concrete weak-vs-strong examples table. Step 13 has implicit quality contrasts in its "Don't Over-Splice" heuristic. The seed templates have "BAD/GOOD" examples in their meta-prompts. None of the other 19 prompts show the LLM what bad output looks like alongside good output, despite this being one of the most effective prompt engineering techniques for calibrating quality.
- **Evidence**: Step 11 line 76-81: the weak/strong table showing "DDoS Attack" (weak) vs "Search API Resource Exhaustion via Recursive Wildcard Query" (strong). This single table communicates the quality bar more effectively than paragraphs of prose rules.
- **Recommendation**: Add a 3-5 row weak-vs-strong examples table to at minimum Steps 04 (FR statements), 05 (API contracts), 06 (invariant expressions), 07 (NFR targets), and 08 (fixture payloads). Example for Step 04: Weak: "The system should handle user input" vs Strong: "Given a login request with valid email and password, the system shall return a 200 response with a signed JWT token within 500ms."

### FINDING-009: Coverage Closure Checklist is Mechanical, Not Reasoning-Oriented
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: All 22 prompts' "Coverage Closure" sections
- **Description**: Every prompt has a Coverage Closure checklist, but it focuses on mechanical verification (every ID consumed, no placeholders, no hallucinations) rather than reasoning verification (is the output logically complete? are there gaps in reasoning? are there unstated assumptions?). The three universal checklist items ("Every upstream ID consumed", "No placeholder tokens", "All required fields from actual upstream data") are necessary but insufficient for synthesis quality.
- **Evidence**: Step 04's Coverage Closure: "Every upstream requirement... is represented... No upstream capability... is silently dropped. All trace/links IDs resolve..." These are traceability checks, not reasoning checks. Missing: "Does every capability have both happy-path AND error-path FRs? Are there capabilities that imply cross-cutting concerns (auth, logging, error handling) that need dedicated FRs?"
- **Recommendation**: Add 2-3 step-specific reasoning verification items to each Coverage Closure section. These should ask the LLM to verify the LOGIC of its output, not just the structure.

### FINDING-010: Extraction Intent Sections are Exhaustive but Lack Priority
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: All 22 prompts' "Extraction Intent" sections
- **Description**: Extraction Intent sections list every upstream artifact and what to extract. Later steps (12, 14, 15, 16, 16a, 16b, 16c) list 12-20+ upstream artifacts each. This flat list provides no priority -- the LLM treats all extractions equally, which leads to shallow processing of critical inputs (e.g., Step 14 treating charter constraints and glossary terms with equal depth).
- **Evidence**: Step 14's Extraction Intent lists 16 upstream artifacts. Step 16a lists 17. Step 16b lists 20. Each gets the same one-line description. The LLM cannot distinguish between "must deeply analyze" (e.g., 04_fr_list.json for Step 14) and "reference for consistency" (e.g., 03_glossary.json for Step 14).
- **Recommendation**: Group extraction intents into "Primary Sources" (deeply analyze, drive output structure) and "Reference Sources" (check for consistency, use for vocabulary alignment). This already exists partially in some prompts' "Context To Ingest" sections but is not carried into the Extraction Intent format.

### FINDING-011: Step 05 (Interfaces) Lacks API Design Reasoning Framework
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_05_interface_contracts.md:48-53`
- **Description**: Step 05 is one of the most consequential steps (feeds 9 downstream steps) but its operating flow is the generic "Synthesize -> Clarify -> Emit" with no API design reasoning. The LLM must make REST design decisions (resource naming, URL structure, pagination, error schema, status codes) that require domain expertise the prompt does not provide.
- **Evidence**: The operating flow says "Map APIs to FRs; ensure each FR with external behavior has an interface or rationale for being internal-only" but does not explain HOW to decide: resource naming conventions, when to nest resources (POST /users/:id/orders vs POST /orders?user_id=:id), how to handle bulk operations, what standard error response shape to use, when to use 201 vs 200 vs 204.
- **Recommendation**: Add a "REST Design Heuristics" section covering: (1) resource naming from glossary terms, (2) standard CRUD mapping (POST=create, GET=read, PUT=replace, PATCH=update, DELETE=remove), (3) standard error response shape, (4) pagination pattern, (5) when to use nested vs flat routes.

### FINDING-012: Step 06 (Invariants) Needs Systematic Discovery Method
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_06_invariants.md:55-59`
- **Description**: Step 06 correctly identifies that invariants go "beyond FR-derived negative cases" and lists categories (data integrity, state transitions, access boundaries, ordering guarantees). However, it provides no systematic method for DISCOVERING these invariants. The LLM is told WHAT to look for but not HOW to find it.
- **Evidence**: The instruction "MUST include data integrity constraints implied by entities in spec/03_glossary.json, state transition rules for entities with lifecycle stages defined in the glossary" tells the LLM to look at the glossary for entities with lifecycle stages -- but does not explain how to determine whether an entity HAS lifecycle stages if the glossary does not explicitly say so.
- **Recommendation**: Add an invariant discovery checklist: "For each entity in the glossary: (1) Does it have states? If yes, what transitions are valid? (2) Does it have quantities? If yes, what bounds apply? (3) Does it reference other entities? If yes, what referential integrity rules apply? (4) Can it be deleted? If yes, what cascade rules apply? For each API: (1) Does it mutate state? If yes, what idempotency rule applies? (2) Does it cross a trust boundary? If yes, what access rule applies?"

### FINDING-013: Steps 04-08 Need "Given-When-Then" Reasoning Framework
- **Severity**: MEDIUM
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_04_functional_requirements.md:68`
- **Description**: Step 04 mentions "Given-When-Then phrasing in acceptance criteria" as part of the ambiguity scrub, but does not expand this into a proper reasoning framework. Given-When-Then (or Arrange-Act-Assert) is one of the most effective tools for forcing specificity in behavioral specifications, but it appears as a one-line mention rather than a structured method that flows through Steps 04 (FRs), 05 (APIs), 06 (Invariants), 07 (NFRs), and 08 (Fixtures).
- **Evidence**: Step 04 line 68: "ban 'should/could/fast/easy'; use 'Given-When-Then' phrasing in acceptance criteria." This is one line in a 222-line prompt. No example is provided. Steps 05-08 do not reference this pattern at all despite being the downstream consumers of these criteria.
- **Recommendation**: Promote Given-When-Then from a one-line mention to a structured section in Step 04 with examples. Add cross-references in Steps 05, 06, and 08 showing how GWT criteria map to API contracts, invariant expressions, and fixture inputs/expected respectively.

### FINDING-014: Output Contract Examples Contradict Prompt Guidance
- **Severity**: LOW
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_07_nfrs.md:190`, `prompts/prompt_01_capabilities.md:186`
- **Description**: Some Output Contract examples contradict the prompt's own guidance. Step 07's example uses `"measurement_method": "automated monitoring"` despite the prompt explicitly saying measurement_method must "specify a concrete query, tool, or dashboard endpoint (not generic phrases like 'automated monitoring')." Step 01's example uses `"capability_id": "capability-authentication"` but the field guidance says "MUST use capability-<verb>-<object> format" -- "authentication" is a noun, not a verb-object pair.
- **Evidence**: Step 07 line 52: "MUST ensure measurement_method references a specific tool, query, or dashboard endpoint (not generic phrases like 'automated monitoring')" vs line 190: `"measurement_method": "automated monitoring"`. Direct contradiction within the same prompt.
- **Recommendation**: Fix Output Contract examples to comply with the prompt's own rules. Step 07 example should use `"measurement_method": "PromQL: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{handler='login'}[5m]))"`. Step 01 example should use `"capability_id": "capability-authenticate-user"`.

### FINDING-015: No Cross-Step Consistency Verification Guidance
- **Severity**: LOW
- **Category**: SYNTHESIS
- **Location**: All prompts
- **Description**: Each prompt focuses on producing its own artifact but provides no guidance on verifying consistency with SIBLING artifacts at the same level of abstraction. For example, Steps 04 (FRs) and 05 (APIs) are written independently, but an API that does not correspond to any FR (or vice versa) indicates a consistency problem that neither prompt checks for explicitly.
- **Evidence**: While Coverage Closure sections check for forward/backward traceability (does every FR trace to a capability?), they do not check for cross-artifact consistency (do the FRs and APIs tell a consistent story about system behavior?). The traceability matrix tool exists but is not integrated into the prompt's reasoning flow.
- **Recommendation**: Add a "Cross-Artifact Consistency" check to Steps 04-08 prompts that explicitly asks the LLM to verify its output is consistent with sibling artifacts, not just upstream ancestors.

### FINDING-016: Seed Template Deep-Dive Questions Not Referenced by Step 00
- **Severity**: LOW
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_00_project_charter.md:43-56`, `seed_templates/seed_overview.md:57-62`
- **Description**: The seed_overview.md template contains rich "DEEP DIVE QUESTIONS" in HTML comments that serve as coaching prompts for the product owner (e.g., "Problem: What is the specific pain point? Tell me a story about it. What is broken TODAY?"). Step 00 does not reference these coaching questions or use them as extraction heuristics. Similarly, seed_tech_stack.md has system-type-specific guidance (examples by system type for web app, library, CLI, mobile, embedded) that Step 00 and Step 02 do not leverage.
- **Evidence**: seed_overview.md line 58-62: "DEEP DIVE QUESTIONS: Problem: 'What is the specific pain point?'... User: 'Whose life is being improved? Give me a job title and a mood.'" These questions would be valuable extraction heuristics for Step 00 but are not referenced. seed_tech_stack.md has "EXAMPLES BY SYSTEM TYPE" (line 92-98) that would help Step 02 make architecture decisions but are not referenced.
- **Recommendation**: Step 00 should reference the seed template coaching questions as extraction heuristics. Step 02 should reference seed_tech_stack.md's system-type-specific examples when making architecture decisions.

### FINDING-017: Steps 04 and 07 Have the Largest Challenge-vs-Guidance Gap
- **Severity**: CRITICAL
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_04_functional_requirements.md`, `prompts/prompt_07_nfrs.md`
- **Description**: Steps 04 (FRs) and 07 (NFRs) have the largest gap between the difficulty of their synthesis challenge and the guidance provided. Step 04 feeds 13 downstream steps (the most of any step) and requires the hardest decomposition reasoning in the pipeline, yet uses the generic "Synthesize -> Clarify -> Emit" flow with no decomposition methodology. Step 07 requires deriving numeric targets from qualitative goals -- a judgment-heavy task -- but provides no framework for setting realistic targets.
- **Evidence**: Step 04 feeds 13 downstream steps (more than any other). Its synthesis challenge (decomposing capabilities into falsifiable behavioral specifications) is one of the hardest in the pipeline. Yet its operating flow is the same 4-bullet generic pattern used by Step 03 (Glossary), which has a much simpler synthesis challenge. Step 07 says "MUST include stage and owner for every NFR" but does not explain how to determine what the right latency target is for a login endpoint when no benchmark data exists.
- **Recommendation**: Step 04 needs a dedicated decomposition methodology (e.g., "For each capability: (1) identify the primary happy-path behavior, (2) identify error/edge behaviors, (3) identify cross-cutting behaviors (auth, logging, validation), (4) write each as a separate FR"). Step 07 needs a "Target Setting Heuristic" section (e.g., "For latency: web APIs should target p95 < 500ms for reads, < 1000ms for writes as a starting point. For availability: SaaS products should target 99.9% for non-critical, 99.95% for critical paths.").

### FINDING-018: Trinity Loop (16/16a/16b/16c) is the Gold Standard -- Patterns Should Propagate
- **Severity**: CRITICAL
- **Category**: SYNTHESIS
- **Location**: `prompts/prompt_16a_impl_planner.md`, `prompts/prompt_16b_impl_coder.md`, `prompts/prompt_16c_impl_reviewer.md`
- **Description**: The Trinity Loop prompts (16a, 16b, 16c) represent the gold standard of synthesis guidance in this system. They have: (1) unique roles with specific reasoning modes, (2) step-specific operating flows with named phases, (3) categorized forbidden actions, (4) explicit field definitions with rules and expectations, (5) failure modes with causes and fixes, (6) evidence-binding requirements. The gap between these prompts and the Discovery Phase prompts (01-10) is significant and represents the largest improvement opportunity in the system.
- **Evidence**: Step 16a has 5 categories of forbidden actions (structural, content, roadmap coverage, inference, atomicity) with 15 specific violations listed. Step 04 has 5 negative constraints as a flat list. Step 16b's "Requirement-First Execution" flow has 5 named phases with stop conditions. Step 04's "Synthesize -> Clarify -> Emit" has 4 generic bullets.
- **Recommendation**: Propagate the following patterns from Trinity Loop to Discovery Phase prompts: (1) categorized forbidden actions (at minimum for Steps 04, 05, 06, 07), (2) step-specific operating flows with named reasoning phases, (3) failure modes with causes and fixes, (4) evidence/quality calibration criteria (weak-vs-strong examples).

---

## Answers to Required Questions

### Q1: For each step, what is the synthesis challenge and does the prompt adequately address it?
See individual step assessments above. In summary: 8 prompts have STRONG guidance (00, 11, 13, 14, 16, 16a, 16b, 16c), 14 have ADEQUATE guidance (01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 12, 13a, 15), and 0 are THIN. The ADEQUATE ratings cluster in the Discovery Phase (Steps 01-10) which, paradoxically, contains the hardest synthesis challenges (decomposition, quantification, invariant discovery).

### Q2: Which steps have the largest gap between difficulty and guidance?
1. **Step 04 (FRs)**: Highest downstream impact (13 consumers), hardest decomposition challenge, generic operating flow.
2. **Step 07 (NFRs)**: Requires numeric target judgment, no target-setting heuristics.
3. **Step 05 (Interfaces)**: Requires API design expertise, no design reasoning framework.
4. **Step 06 (Invariants)**: Requires invariant discovery from implicit constraints, no systematic method.

### Q3: What patterns from highest-rated prompts could be applied to lowest-rated?
See FINDING-018. Key patterns: (1) Named operating flow phases, (2) Categorized forbidden actions, (3) Weak-vs-strong examples, (4) Failure modes with causes/fixes, (5) Calibrated quality criteria.

### Q4: Does any prompt explain HOW to handle conflicting upstream inputs?
No. See FINDING-003. No prompt addresses contradiction resolution. Steps 04, 05, 06, 07, and 09 should.

### Q5: Does any prompt explain HOW to identify implicit requirements?
Partially. Step 06 comes closest ("MUST include data integrity constraints implied by entities... state transition rules... access boundary rules... ordering guarantees") but lacks a systematic method. See FINDING-004. Steps 04, 05, and 06 should have explicit implicit-requirement discovery checklists.

### Q6: For Step 00 specifically, does it extract enough from seed templates?
Largely yes. See FINDING-007 and FINDING-016. Step 00's extraction intent aligns well with seed_overview.md sections 2-7 and seed_tech_stack.md constraints. Gap: seed_overview.md section 5 (Domain Model) and seed_tech_stack.md's system-type-specific guidance are not referenced.
