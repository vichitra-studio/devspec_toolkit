# R2-A: Content Classification of All 22 Prompts

**Date**: 2026-03-20
**Analyst**: Claude Opus 4.6 (1M context)
**Scope**: Line-by-line content classification of all 22 step prompts
**Total LOC**: 5727

---

## Classification Legend

| Category | Definition | Action |
|---|---|---|
| SCHEMA-DUP | Duplicates schema field names, types, required lists, enum values, field descriptions | DELETE -- schema is authoritative |
| DAG-DUP | Duplicates cross-step relationships derivable from step_order.json | DELETE -- DAG is authoritative |
| CANON-DUP | Duplicates canonical registry values | DELETE -- canon is authoritative |
| BOILERPLATE | Identical/near-identical across prompts (Hardening Protocol, Canonical Binding, Path Variables, etc.) | EXTRACT to shared_expectations.md |
| STEP-REASONING | Step-specific operating flow, failure modes, examples, domain judgment, distillation guidance | KEEP -- this is what prompts are for |
| MISSING-REASONING | Reasoning that SHOULD exist but doesn't | ADD |
| AMBIGUOUS | Content that could go either way -- needs design decision | FLAG for review |

---

## Per-Prompt Classification

### Prompt 00 -- prompt_00_project_charter.md (245 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 32 | 13% | Quick Reference (L141-148: required fields, validation gates); Field-by-Field (L115-124: owner enum, field types); Output Contract structure (L186-244) |
| DAG-DUP | 3 | 1% | L3 "feeds 8 downstream steps" (derivable from downstream_consumers) |
| CANON-DUP | 2 | 1% | L96 owner enum list; L116 owner enum repeated |
| BOILERPLATE | 72 | 29% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Seed Order (L39-42); Output Rules (L89-98); Hardening Protocol (L163-168); Canonical Registry (L169-176); Canonical Binding Rules (L177-181); Metadata Contract (L182-184) |
| STEP-REASONING | 130 | 53% | Purpose (L20-21); Context To Ingest (L44-50); Extraction Intent (L52-56); Operating Flow (L57-63); Heuristics (L64-68); Self-Audit Gate (L69-88); Completeness Checklist (L99-107); Negative Constraints (L108-113); Best Practices (L126-132); Common Pitfalls (L134-139); Clarification Questions (L149-157); Output Contract example (L186-244) |
| MISSING-REASONING | ~10 | est | No weak-vs-strong examples; no conflict resolution protocol; no implicit requirement discovery guidance |
| AMBIGUOUS | 6 | 2% | Tool Execution (L23-27: could be shared or step-specific); Schema Reference (L158-161: could be generated) |

### Prompt 01 -- prompt_01_capabilities.md (208 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 25 | 12% | Quick Reference (L135-138: ID format, scope, owner enums); Field-by-Field (L110-119: owner enum, scope enum, field types); Output Contract (L177-207) |
| DAG-DUP | 3 | 1% | L3 "feeds 7 downstream steps"; L46 upstream from charter |
| CANON-DUP | 3 | 1% | L92/115/138 owner enum repeated 3 times |
| BOILERPLATE | 72 | 35% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Seed Order (L39-42); Output Rules (L86-94); Hardening Protocol (L154-158); Canonical Registry (L160-166); Canonical Binding Rules (L167-171); Metadata Contract (L173-175) |
| STEP-REASONING | 100 | 48% | Purpose (L20-21); Context To Ingest (L44-50); Extraction Intent (L52-56); Operating Flow (L57-61); Heuristics (L63-67); Self-Audit Gate (L68-84); Completeness Checklist (L96-103); Negative Constraints (L104-109); Best Practices (L121-127); Common Pitfalls (L128-133); Clarification Questions (L140-147) |
| MISSING-REASONING | ~12 | est | No weak-vs-strong examples; generic operating flow; no failure modes with causes/fixes; no conflict resolution |
| AMBIGUOUS | 5 | 2% | Tool Execution (L23-27); Schema Reference (L149-152) |

### Prompt 02 -- prompt_02_system_sketch.md (228 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 41 | 18% | Field-by-Field (L111-124: component types, protocols, auth methods, trust boundaries, rate limit shape, tag vocabulary -- all schema enums); Quick Reference (L140-146: enum lists); External Definition (L148-149: type:external semantics); Schema Ref and Rate Limit Formats (L151-152) |
| DAG-DUP | 5 | 2% | L3 "feeds 6 downstream steps"; L58-60 dependency order text |
| CANON-DUP | 2 | 1% | L99 owner enum |
| BOILERPLATE | 66 | 29% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-38); Seed Order (L39-42); Output Rules (L93-101); Hardening Protocol (L177-181); Canonical Registry (L183-189); Canonical Binding Rules (L190-194); Metadata Contract (L196-198) |
| STEP-REASONING | 107 | 47% | Purpose (L20-22); Context To Ingest (L44-48); Extraction Intent (L50-55); Operating Flow (L56-65); Heuristics (L67-72); Self-Audit Gate (L74-91); Completeness Checklist (L103-109); Negative Constraints (L161-170); Best Practices (L126-131); Common Pitfalls (L133-138); Clarification Questions (L154-159); Output Contract (L200-228) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong examples; no failure mode analysis; generic operating flow |
| AMBIGUOUS | 7 | 3% | Tool Execution (L23-27); Schema Reference (L172-175) |

### Prompt 02a -- prompt_02a_delivery_baseline.md (200 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 18 | 9% | Field-by-Field (L114-118: environments, ci_gates, secrets, compliance types); Quick Reference (L135-138); Output Contract (L174-199) |
| DAG-DUP | 3 | 2% | L3 "feeds 1 downstream step"; L46 upstream from system sketch |
| CANON-DUP | 2 | 1% | L93 owner enum |
| BOILERPLATE | 68 | 34% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-38); Seed Order (L39-42); Output Rules (L88-101); Hardening Protocol (L151-155); Canonical Registry (L157-163); Canonical Binding Rules (L164-168); Metadata Contract (L170-172) |
| STEP-REASONING | 103 | 52% | Purpose (L20-21); Context To Ingest (L44-48); Extraction Intent (L50-56); Operating Flow (L57-62); Heuristics (L64-67); Self-Audit Gate (L69-86); Completeness Checklist (L102-107); Negative Constraints (L108-113); Best Practices (L121-126); Common Pitfalls (L128-133); Clarification Questions (L140-144) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong examples; no failure modes; generic operating flow |
| AMBIGUOUS | 6 | 3% | Tool Execution (L23-27); Schema Reference (L146-149) |

### Prompt 03 -- prompt_03_glossary.md (192 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 14 | 7% | Quick Reference (L129-131: required/optional fields); Field-by-Field (L108-113: field types, min lengths, patterns); Output Contract (L167-192) |
| DAG-DUP | 3 | 2% | L3 "feeds 3 downstream steps" |
| CANON-DUP | 2 | 1% | L93 owner enum |
| BOILERPLATE | 64 | 33% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-38); Seed Order (L39-42); Output Rules (L88-94); Hardening Protocol (L144-148); Canonical Registry (L150-156); Canonical Binding Rules (L157-161); Metadata Contract (L163-165) |
| STEP-REASONING | 104 | 54% | Purpose (L20-21); Context To Ingest (L44-48); Extraction Intent (L50-56); Operating Flow (L57-62); Heuristics (L64-68); Self-Audit Gate (L70-86); Completeness Checklist (L96-101); Negative Constraints (L103-106); Best Practices (L115-120); Common Pitfalls (L122-127); Clarification Questions (L133-137) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong examples; no failure modes; generic operating flow |
| AMBIGUOUS | 5 | 3% | Tool Execution (L23-27); Schema Reference (L139-142) |

### Prompt 04 -- prompt_04_functional_requirements.md (222 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 22 | 10% | Quick Reference (L138-142: ID format, required fields, criteria structure, trace hooks); Field-by-Field (L109-117: field types, trace object structure); Output Contract (L179-222) |
| DAG-DUP | 4 | 2% | L3 "feeds 13 downstream steps"; L46 upstream references |
| CANON-DUP | 2 | 1% | L97 owner enum |
| BOILERPLATE | 66 | 30% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Seed Order (L39-42); Output Rules (L91-99); Hardening Protocol (L156-160); Canonical Registry (L162-168); Canonical Binding Rules (L169-173); Metadata Contract (L175-177) |
| STEP-REASONING | 121 | 55% | Purpose (L20-21); Context To Ingest (L44-48); Extraction Intent (L50-57); Operating Flow (L58-63); Heuristics (L65-68); Self-Audit Gate (L70-90); Completeness Checklist (L101-107); Negative Constraints (L131-136); Best Practices (L119-123); Common Pitfalls (L125-129); Clarification Questions (L144-149) |
| MISSING-REASONING | ~15 | est | No implicit requirement discovery checklist; no weak-vs-strong examples; no conflict resolution; no decomposition heuristics for splitting multi-behavior FRs |
| AMBIGUOUS | 7 | 3% | Tool Execution (L23-27); Schema Reference (L151-154) |

### Prompt 05 -- prompt_05_interface_contracts.md (183 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 22 | 12% | Quick Reference (L132-137: ID format, required fields, allowed protocols, security flag); Field-by-Field (L98-108: field types, enums); Output Contract (L174-183) |
| DAG-DUP | 3 | 2% | L3 "feeds 9 downstream steps" |
| CANON-DUP | 2 | 1% | L86 owner enum |
| BOILERPLATE | 58 | 32% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Output Rules (L80-88); Hardening Protocol (L151-155); Canonical Registry (L157-163); Canonical Binding Rules (L164-168); Metadata Contract (L170-172) |
| STEP-REASONING | 93 | 51% | Purpose (L20-21); Extraction Intent (L39-47); Operating Flow (L48-53); Heuristics (L55-58); Self-Audit Gate (L60-78); Completeness Checklist (L90-96); Negative Constraints (L124-131); Best Practices (L110-117); Common Pitfalls (L119-123); Clarification Questions (L139-144) |
| MISSING-REASONING | ~10 | est | No Seed Order section (missing); no weak-vs-strong examples; generic operating flow |
| AMBIGUOUS | 5 | 3% | Tool Execution (L23-27); Schema Reference (L146-149) |

### Prompt 06 -- prompt_06_invariants.md (205 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 18 | 9% | Quick Reference (L128-132: ID format, required fields, scope usage, trace hooks); Field-by-Field (L102-109: field types, language enum, severity enum); Output Contract (L169-205) |
| DAG-DUP | 3 | 1% | L3 "feeds 3 downstream steps" |
| CANON-DUP | 2 | 1% | L91 owner enum |
| BOILERPLATE | 62 | 30% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-35); Task (L37-42); Output Rules (L85-93); Hardening Protocol (L146-150); Canonical Registry (L152-158); Canonical Binding Rules (L159-163); Metadata Contract (L165-167) |
| STEP-REASONING | 115 | 56% | Purpose (L20-21); Extraction Intent (L44-52); Operating Flow (L54-60); Heuristics (L62-65); Self-Audit Gate (L67-83); Completeness Checklist (L95-100); Negative Constraints (L117-120); Best Practices (L111-115); Common Pitfalls (L122-126); Clarification Questions (L134-139); Tool Execution extended (L28-32: invariants-check command) |
| MISSING-REASONING | ~12 | est | No weak-vs-strong examples; no jsonlogic/CEL expression examples; no state-transition discovery method; no conflict resolution |
| AMBIGUOUS | 5 | 2% | Tool Execution (L23-32); Schema Reference (L141-144) |

### Prompt 07 -- prompt_07_nfrs.md (216 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 19 | 9% | Quick Reference (L127-129: categories enum, stage enum); Field-by-Field (L96-105: field types, enums); Output Contract (L165-216) |
| DAG-DUP | 3 | 1% | L3 "feeds 5 downstream steps" |
| CANON-DUP | 4 | 2% | L86 owner enum; L128 category enum list |
| BOILERPLATE | 66 | 31% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Output Rules (L80-88); Hardening Protocol (L142-146); Canonical Registry (L148-154); Canonical Binding Rules (L155-159); Metadata Contract (L161-163) |
| STEP-REASONING | 117 | 54% | Purpose (L20-21); Extraction Intent (L39-48); Operating Flow (L50-56); Heuristics (L58-61); Self-Audit Gate (L63-78); Completeness Checklist (L90-94); Negative Constraints (L122-125); Best Practices (L107-113); Common Pitfalls (L115-120); Clarification Questions (L131-135) |
| MISSING-REASONING | ~12 | est | No weak-vs-strong examples; no conflict resolution; no measurement method feasibility guidance; generic operating flow |
| AMBIGUOUS | 7 | 3% | Tool Execution (L23-27); Schema Reference (L137-140) |

### Prompt 08 -- prompt_08_fixtures.md (206 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 18 | 9% | Quick Reference (L130-134: ID format, required fields, mode choices, trace hooks); Field-by-Field (L108-116: mode enum, target shape, contract usage); Output Contract (L170-206) |
| DAG-DUP | 3 | 1% | L3 "feeds 2 downstream steps" (derivable) |
| CANON-DUP | 2 | 1% | L92 owner enum |
| BOILERPLATE | 62 | 30% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-35); Task (L37-42); Output Rules (L86-93); Hardening Protocol (L147-151); Canonical Registry (L153-159); Canonical Binding Rules (L160-164); Metadata Contract (L166-168) |
| STEP-REASONING | 115 | 56% | Purpose (L20-21); Extraction Intent (L44-54); Operating Flow (L56-61); Heuristics (L63-66); Self-Audit Gate (L68-84); Completeness Checklist (L95-100); Negative Constraints (L102-106); Best Practices (L118-122); Common Pitfalls (L124-128); Clarification Questions (L136-140); Tool Execution extended (L28-31: fixtures-lint command) |
| MISSING-REASONING | ~10 | est | No weak-vs-strong fixture examples; no mode selection guidance; generic operating flow |
| AMBIGUOUS | 6 | 3% | Tool Execution (L23-31); Schema Reference (L142-145) |

### Prompt 09 -- prompt_09_impl_plan.md (240 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 30 | 13% | Field-by-Field (L106-117: tech_stack structure, milestone fields, status enum); Quick Reference (L132-134); Negative Constraints (L93-98: tech_stack structure rules); Output Contract (L170-240) |
| DAG-DUP | 3 | 1% | L3 "feeds 3 downstream steps" |
| CANON-DUP | 2 | 1% | L89 owner enum |
| BOILERPLATE | 64 | 27% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Output Rules (L83-91); Hardening Protocol (L147-151); Canonical Registry (L153-159); Canonical Binding Rules (L160-164); Metadata Contract (L166-168) |
| STEP-REASONING | 133 | 55% | Purpose (L20-21); Extraction Intent (L39-50); Operating Flow (L52-58); Heuristics (L60-62); Self-Audit Gate (L64-81); Completeness Checklist (L100-104); Negative Constraints (L93-98 -- some are step-reasoning, not just schema-dup); Best Practices (L119-124); Common Pitfalls (L126-130); Clarification Questions (L136-140) |
| MISSING-REASONING | ~10 | est | No weak-vs-strong examples; no tech stack evaluation heuristics; no milestone sizing guidance |
| AMBIGUOUS | 8 | 3% | Tool Execution (L23-27); Schema Reference (L142-145) |

### Prompt 10 -- prompt_10_governance.md (188 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 16 | 9% | Field-by-Field (L112-119: pr_rules enum values, commit_message_rules structure); Quick Reference (L135-139); Output Contract (L175-188) |
| DAG-DUP | 3 | 2% | L3 "downstream consumers" |
| CANON-DUP | 2 | 1% | L94 owner enum |
| BOILERPLATE | 64 | 34% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-36); Task (L38-43); Output Rules (L88-96); Hardening Protocol (L152-156); Canonical Registry (L158-164); Canonical Binding Rules (L165-169); Metadata Contract (L171-173) |
| STEP-REASONING | 97 | 52% | Purpose (L20-21); Extraction Intent (L45-57); Operating Flow (L59-64); Heuristics (L66-68); Self-Audit Gate (L70-86); Completeness Checklist (L105-110); Negative Constraints (L98-103); Best Practices (L121-127); Common Pitfalls (L129-133); Clarification Questions (L141-145); Tool Execution extended (L28-32: governance-check command) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong commit message examples; no regex pattern examples; generic operating flow |
| AMBIGUOUS | 6 | 3% | Tool Execution (L23-32); Schema Reference (L147-150) |

### Prompt 11 -- prompt_11_redteam.md (254 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 19 | 7% | Quick Reference (L161-165: ID format, categories enum, targets, mitigation types); Field-by-Field (L130-148: field types, enums); Output Contract (L201-254) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 2 | 1% | None specific beyond output contract example |
| BOILERPLATE | 52 | 20% | Schema Authority (L5-10); Path Variables (L12-18); Output Rules (L108-116); Hardening Protocol (L178-182); Canonical Registry (L184-190); Canonical Binding Rules (L191-195); Metadata Contract (L197-199) |
| STEP-REASONING | 172 | 68% | Purpose (L20-21); Philosophy "Shift Left" (L32-37); Task (L39-44); Taxonomy (L46-52); Extraction Intent (L53-66); Operating Flow "Attack -> Trace -> Mitigate" (L68-74); Examples weak-vs-strong (L76-81); Heuristics (L83-86); Self-Audit Gate (L88-106); Completeness Checklist (L123-128); Negative Constraints (L117-121); Best Practices (L149-153); Common Pitfalls (L155-159); Clarification Questions (L167-171) |
| MISSING-REASONING | ~5 | est | Could use more domain-specific threat patterns per category |
| AMBIGUOUS | 6 | 2% | Tool Execution (L23-27); Schema Reference (L173-176) |

### Prompt 12 -- prompt_12_ci_gates.md (211 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 16 | 8% | Quick Reference (L142-144: jobs, coverage); Field-by-Field (L123-128: job fields, environment_ref, coverage_thresholds); Output Contract (L183-211) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 2 | 1% | L113 owner enum |
| BOILERPLATE | 58 | 27% | Schema Authority (L5-10); Path Variables (L12-18); Role (L29-30); Task (L32-37); Output Rules (L107-115); Hardening Protocol (L157-161); Canonical Registry (L163-171); Canonical Binding Rules (L173-177); Metadata Contract (L179-181) |
| STEP-REASONING | 125 | 59% | Purpose (L20-21); Extraction Intent (L39-53); Operating Flow (L55-60); Heuristics (L62-64); Self-Audit Gate (L66-82); Negative Constraints (L84-89); Hallucination Vectors (L91-95); Tooling Context (L97-106); Completeness Checklist (L117-121); Best Practices (L130-134); Common Pitfalls (L136-140); Clarification Questions (L146-150) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong DAG examples; no CI pipeline pattern examples |
| AMBIGUOUS | 7 | 3% | Tooling Context (L97-106: could be derivable from CLI help); Schema Reference (L152-155) |

### Prompt 13 -- prompt_13_extension_generator.md (170 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 14 | 8% | Field-by-Field (L93-101: extension_id pattern, file_name pattern, governance_label_ref); Output Contract (L136-170) |
| DAG-DUP | 3 | 2% | L3 "downstream consumers" |
| CANON-DUP | 3 | 2% | L101 governance_label_ref canonical values listed |
| BOILERPLATE | 48 | 28% | Schema Authority (L5-10); Path Variables (L12-18); Output Rules (L103-107); Hardening Protocol (L113-117); Canonical Registry (L119-125); Canonical Binding Rules (L126-130); Metadata Contract (L132-134) |
| STEP-REASONING | 98 | 58% | Purpose (L20-22); Role (L29-31); Task (L33-37); Extraction Intent (L38-53); Operating Flow "Analyze -> Filter -> Plan" (L55-63); Heuristics (L65-69); Self-Audit Gate (L71-88); Negative Constraints (L90-91); Output Contract (L136-170) |
| MISSING-REASONING | ~8 | est | No weak-vs-strong extension examples; no domain complexity threshold guidance |
| AMBIGUOUS | 4 | 2% | Tool Execution (L23-27); Schema Reference (L108-111) |

### Prompt 13a -- prompt_13a_completeness_assessment.md (203 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 16 | 8% | Field-by-Field (L108-121: element fields, completeness_rating structure, category enum, priority enum); Quick Reference (L152-153); Output Contract (L188-203) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | L129 owner |
| BOILERPLATE | 56 | 28% | Schema Authority (L5-10); Path Variables (L12-18); Role (L35-36); Output Rules (L123-131); Hardening Protocol (L165-169); Canonical Registry (L171-177); Canonical Binding Rules (L178-182); Metadata Contract (L184-186) |
| STEP-REASONING | 121 | 60% | Purpose (L20-21); Task (L38-42); Logic Update (L44-47); Extraction Intent (L49-65); Operating Flow (L67-72); Heuristics (L74-81); Self-Audit Gate (L83-100); Negative Constraints (L102-106); Completeness Checklist (L132-137); Best Practices (L139-144); Common Pitfalls (L146-150); Clarification Questions (L155-158) |
| MISSING-REASONING | ~5 | est | No scoring rubric examples; no assessment methodology guidance |
| AMBIGUOUS | 6 | 3% | Tool Execution (L23-32); Schema Reference (L160-163) |

### Prompt 14 -- prompt_14_roadmap.md (322 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 68 | 21% | Field-by-Field (L116-187: tech_stack objects, milestones structure, deliverables shape, target_date format, status/risk_status enums, tasks structure, depends_on, assumptions, exit_conditions, source_milestones, fr_refs, capability_refs, risks, spikes, migration_plan, dependencies, trace); Output Contract (L228-322) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | Implicit in output contract |
| BOILERPLATE | 58 | 18% | Schema Authority (L5-10); Path Variables (L12-18); Output Rules (L191-196); Note on $schema (L198-199); Hardening Protocol (L205-209); Canonical Registry (L211-217); Canonical Binding Rules (L218-222); Metadata Contract (L224-226) |
| STEP-REASONING | 182 | 57% | Purpose (L20-21); Role (L34-35); Task (L37-41); Extraction Intent (L43-60); Operating Flow "Ingest -> Synthesize -> Sequence -> Decompose -> Emit" (L62-67); Heuristics (L69-71); Self-Audit Gate (L73-90); Best Practices (L91-98); Common Pitfalls (L99-103); Negative Constraints (L104-114); Clarification Questions implicit |
| MISSING-REASONING | ~8 | est | No user story decomposition heuristics; no dependency ordering examples |
| AMBIGUOUS | 10 | 3% | Tool Execution (L23-32); Schema Reference (L200-203) |

### Prompt 15 -- prompt_15_scaffold.md (189 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 16 | 8% | Field-by-Field (L114-120: project_skeleton fields, interface_map fields, validators, build_status enum); Quick Reference (L134-136); Output Contract (L172-189) |
| DAG-DUP | 3 | 2% | L3 "downstream consumers" |
| CANON-DUP | 2 | 1% | L96 owner enum |
| BOILERPLATE | 58 | 31% | Schema Authority (L5-10); Path Variables (L12-18); Role (L31-32); Task (L34-39); Output Rules (L90-100); Hardening Protocol (L149-153); Canonical Registry (L155-161); Canonical Binding Rules (L162-166); Metadata Contract (L168-170) |
| STEP-REASONING | 104 | 55% | Purpose (L20-21); Extraction Intent (L42-59); Operating Flow (L61-66); Heuristics (L68-70); Self-Audit Gate (L72-88); Completeness Checklist (L108-112); Negative Constraints (L102-106); Best Practices (L122-126); Common Pitfalls (L128-132); Clarification Questions (L138-142) |
| MISSING-REASONING | ~8 | est | No framework-specific scaffold examples; no interface_map generation guidance |
| AMBIGUOUS | 6 | 3% | Tool Execution (L23-29); Schema Reference (L144-147) |

### Prompt 16 -- prompt_16_impl_context.md (498 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 30 | 6% | Quick Reference table (L207-223: field types, required markers); some Field Definitions overlap schema (plan.status values, drift target enums, schedule values) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | Minimal |
| BOILERPLATE | 52 | 10% | Schema Authority (L5-10); Path Variables (L12-18); Hardening Protocol (L242-246); Canonical Registry (L248-254); Canonical Binding Rules (L255-259); Metadata Contract (L261-263) |
| STEP-REASONING | 385 | 77% | Purpose (L20-27); When To Use (L29-31); Extraction Intent (L44-63); Operating Flow mandatory (L65-75); Forbidden Actions (L77-82); Field Definitions 1-13 (L83-170); Heuristics (L172-177); Self-Audit Gate (L179-198); Best Practices (L200-206); Failure Modes (L225-231); Clarification Questions (L233-236); Output Contract (L265-498) |
| MISSING-REASONING | ~5 | est | Anchor-to-milestone drift detection heuristics |
| AMBIGUOUS | 27 | 5% | Tool Execution (L33-36); Schema Reference (L237-240); Output Contract is 233 lines (L265-498) -- its size as an example is borderline |

### Prompt 16a -- prompt_16a_impl_planner.md (392 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 20 | 5% | Field Definitions that restate schema (checklist status values, action types, severity values); some overlap with prompt 16 |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | Minimal |
| BOILERPLATE | 50 | 13% | Schema Authority (L5-10); Path Variables (L12-18); Hardening Protocol (L289-293); Canonical Registry (L295-301); Canonical Binding Rules (L302-306); Metadata Contract (L308-310) |
| STEP-REASONING | 310 | 79% | Purpose (L20-25); Critical Changes (L27-31); Role (L39-42); Extraction Intent (L44-64); Operating Flow (L66-76); Roadmap-to-Checklist Coverage (L75-76); Self-Audit Gate (L78-79); Forbidden Actions categorized (L81-112); Field Definitions 1-12 (L113-243); Error Path Rules (L244-247); Failure Modes (L249-255); Output Rules (L257-262); Clarification Questions (L264-267); Coverage Closure (L271-283); Output Contract (L312-392) |
| MISSING-REASONING | ~5 | est | Minimal -- this prompt has strong reasoning |
| AMBIGUOUS | 8 | 2% | Tool Execution (L33-36); Schema Reference (L284-287) |

### Prompt 16b -- prompt_16b_impl_coder.md (430 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 15 | 3% | Some field definition overlap (execution_results fields, evidence structure) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | Minimal |
| BOILERPLATE | 48 | 11% | Schema Authority (L5-10); Path Variables (L12-18); Hardening Protocol (L231-235); Canonical Registry (L237-243); Canonical Binding Rules (L244-248); Metadata Contract (L250-252) |
| STEP-REASONING | 355 | 83% | Purpose (L20-21); Role + Ambiguity Gatekeeper (L29-34); Task (L40-44); Field Definitions 1-6 (L46-127); Extraction Intent (L128-149); Operating Flow v2.0 (L151-172); Failure Modes (L174-178); Self-Audit Gate (L180-181); Forbidden Actions categorized (L183-206); Output Rules (L208-212); Coverage Closure (L214-224); Output Contract Input/Output (L254-430) |
| MISSING-REASONING | ~3 | est | Minimal -- this prompt has strong reasoning |
| AMBIGUOUS | 8 | 2% | Tool Execution (L23-27); Schema Reference (L226-229) |

### Prompt 16c -- prompt_16c_impl_reviewer.md (525 LOC)

| Category | LOC | % | Key sections |
|----------|-----|---|---|
| SCHEMA-DUP | 15 | 3% | Some field definition overlap (review fields, verdict gates, ratings scale) |
| DAG-DUP | 3 | 1% | L3 "downstream consumers" |
| CANON-DUP | 1 | 0% | Minimal |
| BOILERPLATE | 48 | 9% | Schema Authority (L5-10); Path Variables (L12-18); Hardening Protocol (L286-290); Canonical Registry (L292-298); Canonical Binding Rules (L299-303); Metadata Contract (L305-307) |
| STEP-REASONING | 450 | 86% | Purpose (L20-21); Role (L29-31); Task (L34-38); Roadmap Sync (L42-46); Field Definitions 1-7 (L48-187); Extraction Intent (L188-210); Operating Flow audit checklist (L212-222); Red Flags (L223-228); Failure Modes (L229-232); Self-Audit Gate (L234-235); Forbidden Actions categorized (L237-263); Output Rules (L264-266); Coverage Closure (L270-279); Output Contract Input/Output (L309-525) |
| MISSING-REASONING | ~3 | est | Minimal -- this prompt has strong reasoning |
| AMBIGUOUS | 8 | 2% | Tool Execution (L23-27); Schema Reference (L281-284) |

---

## Summary Table

| Prompt | LOC | SCHEMA-DUP | DAG-DUP | CANON-DUP | BOILERPLATE | STEP-REASONING | MISSING | AMBIG |
|--------|-----|------------|---------|-----------|-------------|----------------|---------|-------|
| 00 Charter | 245 | 32 (13%) | 3 (1%) | 2 (1%) | 72 (29%) | 130 (53%) | ~10 | 6 (2%) |
| 01 Capabilities | 208 | 25 (12%) | 3 (1%) | 3 (1%) | 72 (35%) | 100 (48%) | ~12 | 5 (2%) |
| 02 System Sketch | 228 | 41 (18%) | 5 (2%) | 2 (1%) | 66 (29%) | 107 (47%) | ~8 | 7 (3%) |
| 02a Delivery Baseline | 200 | 18 (9%) | 3 (2%) | 2 (1%) | 68 (34%) | 103 (52%) | ~8 | 6 (3%) |
| 03 Glossary | 192 | 14 (7%) | 3 (2%) | 2 (1%) | 64 (33%) | 104 (54%) | ~8 | 5 (3%) |
| 04 FRs | 222 | 22 (10%) | 4 (2%) | 2 (1%) | 66 (30%) | 121 (55%) | ~15 | 7 (3%) |
| 05 Interfaces | 183 | 22 (12%) | 3 (2%) | 2 (1%) | 58 (32%) | 93 (51%) | ~10 | 5 (3%) |
| 06 Invariants | 205 | 18 (9%) | 3 (1%) | 2 (1%) | 62 (30%) | 115 (56%) | ~12 | 5 (2%) |
| 07 NFRs | 216 | 19 (9%) | 3 (1%) | 4 (2%) | 66 (31%) | 117 (54%) | ~12 | 7 (3%) |
| 08 Fixtures | 206 | 18 (9%) | 3 (1%) | 2 (1%) | 62 (30%) | 115 (56%) | ~10 | 6 (3%) |
| 09 Impl Plan | 240 | 30 (13%) | 3 (1%) | 2 (1%) | 64 (27%) | 133 (55%) | ~10 | 8 (3%) |
| 10 Governance | 188 | 16 (9%) | 3 (2%) | 2 (1%) | 64 (34%) | 97 (52%) | ~8 | 6 (3%) |
| 11 Red Team | 254 | 19 (7%) | 3 (1%) | 2 (1%) | 52 (20%) | 172 (68%) | ~5 | 6 (2%) |
| 12 CI Gates | 211 | 16 (8%) | 3 (1%) | 2 (1%) | 58 (27%) | 125 (59%) | ~8 | 7 (3%) |
| 13 Extensions | 170 | 14 (8%) | 3 (2%) | 3 (2%) | 48 (28%) | 98 (58%) | ~8 | 4 (2%) |
| 13a Completeness | 203 | 16 (8%) | 3 (1%) | 1 (0%) | 56 (28%) | 121 (60%) | ~5 | 6 (3%) |
| 14 Roadmap | 322 | 68 (21%) | 3 (1%) | 1 (0%) | 58 (18%) | 182 (57%) | ~8 | 10 (3%) |
| 15 Scaffold | 189 | 16 (8%) | 3 (2%) | 2 (1%) | 58 (31%) | 104 (55%) | ~8 | 6 (3%) |
| 16 Impl Context | 498 | 30 (6%) | 3 (1%) | 1 (0%) | 52 (10%) | 385 (77%) | ~5 | 27 (5%) |
| 16a Planner | 392 | 20 (5%) | 3 (1%) | 1 (0%) | 50 (13%) | 310 (79%) | ~5 | 8 (2%) |
| 16b Coder | 430 | 15 (3%) | 3 (1%) | 1 (0%) | 48 (11%) | 355 (83%) | ~3 | 8 (2%) |
| 16c Reviewer | 525 | 15 (3%) | 3 (1%) | 1 (0%) | 48 (9%) | 450 (86%) | ~3 | 8 (2%) |
| **TOTAL** | **5727** | **500 (9%)** | **69 (1%)** | **43 (1%)** | **1312 (23%)** | **3582 (63%)** | **~186** | **155 (3%)** |

---

## Aggregate Analysis

### Total Deletable/Extractable LOC

| Category | Total LOC | % of 5727 | Action |
|----------|-----------|-----------|--------|
| SCHEMA-DUP | 500 | 9% | DELETE (schema is authoritative) |
| DAG-DUP | 69 | 1% | DELETE (step_order.json is authoritative) |
| CANON-DUP | 43 | 1% | DELETE (canon/ is authoritative) |
| BOILERPLATE | 1312 | 23% | EXTRACT to shared_expectations.md |
| **Subtotal removable** | **1924** | **34%** | |
| STEP-REASONING | 3582 | 63% | KEEP |
| AMBIGUOUS | 155 | 3% | FLAG for design decision |

**34% of prompt content is removable** without losing any step-specific reasoning.

### Boilerplate Breakdown (1312 LOC)

These sections appear identically or near-identically in all 22 prompts:

| Boilerplate Section | LOC per prompt | Total LOC (x22) | Variation |
|---|---|---|---|
| Schema Authority | 6 | 132 | Varies only by schema filename |
| Path Variables | 7 | 154 | Identical across all 22 |
| Role paragraph | 2 | 44 | Varies only by step name |
| Task section | 5 | 110 | Nearly identical; only step name and trace/links differ |
| Seed Order & Mandatory Sources | 3 | 54 | Varies only by step number (12 prompts have it) |
| Output Rules | 8 | 176 | Identical across 18 prompts; 4 have minor variations |
| Hardening Protocol | 4 | 88 | Identical across all 22 |
| Canonical Registry (Required Input) | 5 | 110 | Identical across all 22 |
| Canonical Binding Rules | 4 | 88 | Identical across all 22 |
| Metadata Contract | 3 | 66 | Identical across all 22 |
| Schema Reference | 3 | 66 | Varies only by schema URI and filename |
| Tool Execution | 3-4 | ~70 | Varies only by step-specific additional commands |

### Schema Duplication Hotspots

The worst offenders for schema duplication (enum values, field types, required lists):

| Prompt | Schema-DUP LOC | Worst sections |
|--------|----------------|----------------|
| **14 Roadmap** | **68 (21%)** | Field-by-Field is 72 lines restating schema field types, patterns, structures |
| **02 System Sketch** | **41 (18%)** | Tag vocabulary (21 values), protocol/auth/trust boundary enums |
| **00 Charter** | **32 (13%)** | Quick Reference repeats required fields; Field-by-Field restates types |
| **09 Impl Plan** | **30 (13%)** | tech_stack structure rules, milestone field definitions |

### Discovery Phase vs Trinity Loop Reasoning Quality

| Metric | Discovery (00-12) | Trinity (16-16c) |
|--------|-------------------|------------------|
| Avg STEP-REASONING % | 54% | 81% |
| Avg BOILERPLATE % | 30% | 11% |
| Has categorized forbidden actions | 0/15 | 4/4 |
| Has weak-vs-strong examples | 1/15 (Step 11) | 0/4 (but has output contracts showing input->output) |
| Has named failure modes | 0/15 | 4/4 |
| Has named operating flow phases | 0/15 (all generic) | 4/4 |
| MISSING-REASONING avg | ~10 LOC | ~4 LOC |

---

## Boilerplate Blocks for Extraction to shared_expectations.md

The following 10 blocks should be extracted to `shared_expectations.md` and replaced with a single `{{include shared_expectations}}` reference (or similar mechanism):

### Block 1: Schema Authority (132 LOC total, 6 per prompt)
```
The schema at `schema/NN_name.schema.json` is the authoritative source for all
field definitions, types, required vs optional markers, enum values, patterns, and minItems rules.
MUST read the schema before generating output. Do NOT guess field names, types, or valid values --
all structural constraints are defined in the schema. Do NOT output fields not defined in the schema.
```
**Parameterize**: schema filename only.

### Block 2: Path Variables (154 LOC total, 7 per prompt)
Identical table across all 22 prompts. Zero variation.

### Block 3: Generic Role + Task (154 LOC total, 7 per prompt)
Same structure in every prompt except step name substitution.

### Block 4: Seed Order (54 LOC total, 3 per prompt, 18 prompts)
Same text except step number.

### Block 5: Output Rules (176 LOC total, 8 per prompt)
8 rules repeated identically in 18 prompts. 4 prompts have minor variations (02, 02a, 15, 16).

### Block 6: Hardening Protocol (88 LOC total, 4 per prompt)
Identical in all 22 prompts. Zero variation.

### Block 7: Canonical Registry + Binding Rules (198 LOC total, 9 per prompt)
Identical in 20 of 22 prompts. Step 12 has a slightly expanded version but semantically equivalent.

### Block 8: Metadata Contract (66 LOC total, 3 per prompt)
Identical in all 22 prompts. Zero variation.

### Block 9: Coverage Closure checklist tail (66 LOC total, 3 per prompt)
The final 3 lines of Coverage Closure are identical in all 22 prompts:
```
- [ ] Every upstream ID referenced in extraction intent has been consumed
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
```

### Block 10: Owner enum
`api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering` -- appears 2-3 times per prompt. Should be one reference to schema/canon.

---

## Findings

### New Findings (issues the P1 agents missed)

#### R2-A-001: Prompt 14 has the worst DRY violation -- 21% schema duplication
- **Severity**: HIGH
- **Evidence**: 68 of 322 lines in `prompt_14_roadmap.md` restate schema field definitions. The Field-by-Field section (L116-187) is 72 lines describing `tech_stack` object structure, `milestones[].deliverables` shape, `target_date` format, `status`/`risk_status` enums, `tasks` structure with `acceptance_criteria`, `depends_on`, `assumptions`, `exit_conditions`, `source_milestones`, `fr_refs`, `capability_refs`, `risks`, `spikes`, `migration_plan`, and `dependencies` -- all of which are fully specified in `schema/14_roadmap.schema.json` with complete descriptions.
- **Impact**: When schema evolves, this prompt WILL drift. The schema already has 253 lines of authoritative definitions including descriptions on every field.
- **Fix**: Delete the entire Field-by-Field section and replace with "See schema for field definitions. Step-specific notes:" followed by only the domain judgment not in the schema.

#### R2-A-002: Owner enum appears 43 times across 22 prompts -- classic canon duplication
- **Severity**: MEDIUM
- **Evidence**: The string `api`, `ui`, `system`, `ops`, `data`, `product`, `business`, `engineering` appears in Output Rules, Field-by-Field, and Quick Reference sections of nearly every prompt. This is a canonical value set defined in `schema/core/atoms.schema.json` as `ownerEnum`.
- **Impact**: If the owner enum changes, 43 locations across 22 files must be updated.
- **Fix**: Delete all owner enum listings. The schema already constrains the value set. Prompts should say "Set `owner` per schema enum" without listing values.

#### R2-A-003: 1312 LOC of boilerplate is 23% of total prompt content -- higher than P1 estimated
- **Severity**: HIGH
- **Evidence**: P1-A estimated ~2000 extractable LOC (AUDIT-065). The actual per-category breakdown shows 1312 LOC of identical/near-identical boilerplate (23%), plus 500 LOC of schema duplication (9%) and 69 LOC of DAG duplication (1%). Total removable = 1924 LOC (34%).
- **Impact**: Every prompt carries ~60 lines of identical text. This crowds out step-specific reasoning and makes prompts harder to maintain.
- **Fix**: Extract the 10 identified boilerplate blocks to `shared_expectations.md` and replace with references. This reduces average prompt size from 260 LOC to ~200 LOC.

#### R2-A-004: Discovery Phase prompts (00-10) have 30% boilerplate vs Trinity Loop's 11%
- **Severity**: MEDIUM
- **Evidence**: The Trinity Loop prompts (16, 16a, 16b, 16c) average 11% boilerplate because they dedicate space to categorized forbidden actions, named failure modes, and detailed field definitions. Discovery Phase prompts (00-10) average 30% boilerplate because they lack this depth and fill space with repeated generic blocks.
- **Impact**: This is the structural root cause of AUDIT-001 (critical finding). The prompts that need the MOST reasoning (Steps 04, 05, 06, 07) have the MOST boilerplate relative to reasoning.
- **Fix**: Extract boilerplate from Discovery Phase first. Use the freed space to add step-specific reasoning per AUDIT-001.

#### R2-A-005: Quick Reference sections are pure schema duplication in 16 of 22 prompts
- **Severity**: MEDIUM
- **Evidence**: Every Quick Reference section lists required fields, ID formats, enum values, and structural constraints that are already authoritative in the schema. Examples: Prompt 02 Quick Reference lists component types, protocols, auth methods, trust boundaries, and the full 21-value tag vocabulary -- all defined in `schema/02_system_sketch.schema.json`. Prompt 07 lists NFR categories and stages -- all defined in `schema/07_nfrs.schema.json`.
- **Impact**: Quick Reference creates a third copy of truth (schema + Field-by-Field + Quick Reference) that WILL drift.
- **Fix**: Delete Quick Reference entirely. The schema is the quick reference. If an LLM needs a summary, it should read the schema.

#### R2-A-006: Output Contract examples average 25 LOC but Prompt 16 uses 233 LOC
- **Severity**: LOW
- **Evidence**: Discovery Phase output contracts are 10-40 lines each. Prompt 16's output contract (L265-498) is 233 lines -- nearly half the prompt. Prompts 16b and 16c also include input/output pairs totaling 175+ lines each.
- **Impact**: Large output contracts consume tokens without adding reasoning. They are examples, not contracts -- the schema IS the contract.
- **Fix**: Reduce Output Contract to minimal valid examples (15-25 LOC max). The schema defines the contract. Large examples should be in test fixtures, not prompts.

#### R2-A-007: Field-by-Field sections restate schema descriptions verbatim in 18 prompts
- **Severity**: HIGH
- **Evidence**: Field-by-Field guidance in prompts like 02 (L111-124), 04 (L109-117), 07 (L96-105), 09 (L106-117), 14 (L116-187) restates field names, types, enum values, and descriptions that are already in the schema's `description` properties. Example: Prompt 09 says `milestones[*].status: pending, in_progress, done, deferred` -- the schema already defines this as `$ref: "vc:core:atoms#milestoneStatus"` with a description.
- **Impact**: When schema descriptions are updated (as was done in the ALIGN-1 batch), prompts do NOT get updated in sync, causing semantic drift.
- **Fix**: Field-by-Field should contain ONLY domain judgment not expressible in schema: "when to use X over Y", "what constitutes a good value", "common mistakes". Delete any line that restates field name, type, enum values, or required status.

#### R2-A-008: Prompt 11 (Red Team) is the ONLY Discovery Phase prompt with weak-vs-strong examples
- **Severity**: MEDIUM
- **Evidence**: Prompt 11 has a "Examples: Weak vs. Strong" table (L76-81) showing bad vs good threat descriptions. No other Discovery Phase prompt (00-10, 12-13a) has equivalent examples. The P3 master findings (AUDIT-001) identified this as critical.
- **Impact**: Steps 04, 05, 06, 07, 08 would benefit most from weak-vs-strong examples because they require the most domain judgment (FR statement quality, API design, invariant expression quality, NFR measurability, fixture completeness).
- **Fix**: Add weak-vs-strong example tables to prompts 04, 05, 06, 07, 08 as the highest-priority reasoning additions.

#### R2-A-009: DAG-DUP is minimal (69 LOC, 1%) but indicates a design smell
- **Severity**: LOW
- **Evidence**: Every prompt has L3 stating "This prompt's output feeds N downstream steps" which is derivable from `step_order.json` `downstream_consumers`. Some prompts also have "Dependency Order" sections (e.g., Prompt 02 L58-60) or upstream references in Context To Ingest that duplicate `allowed_upstream_dependencies`.
- **Impact**: Low -- this text is small and rarely drifts. But it signals that prompts don't trust the DAG source of truth.
- **Fix**: Replace L3 in all prompts with `{{downstream_count}}` or a prompt-context CLI reference.

#### R2-A-010: Extraction Intent sections are inconsistent in granularity across prompts
- **Severity**: MEDIUM
- **Evidence**: Prompt 16c has 23 upstream artifacts in its Extraction Intent (L188-210), each with 1-2 lines of detailed extraction guidance. Prompt 05 has 6 upstream artifacts (L39-47) with comparable detail. But Prompt 03 Glossary has only 4 (L50-56) despite consuming 4 upstream artifacts. The level of specificity varies: some say "extract X, Y, Z" (actionable) while others say "for scope boundaries" (vague).
- **Impact**: Inconsistent extraction intent quality affects downstream extraction quality. This is STEP-REASONING (not boilerplate), but its quality is uneven.
- **Fix**: Standardize Extraction Intent to always include: (1) artifact filename, (2) specific fields/sections to extract, (3) what to do with the extracted data. Use the Prompt 04/05 format as the template.

#### R2-A-011: Schema Reference section (66 LOC) should be auto-generated
- **Severity**: LOW
- **Evidence**: Every prompt ends with a Schema Reference section listing schema URI, schema file, and schema registry. This is derivable from `tools/schema_registry.json` and adds no reasoning.
- **Impact**: Must be manually updated when schema URIs change.
- **Fix**: Auto-generate from schema_registry.json during prompt generation/sync.

#### R2-A-012: Tool Execution sections mix boilerplate with step-specific commands
- **Severity**: MEDIUM
- **Evidence**: Every prompt has `./tools/run_specdev.sh validate <path_to_artifact> --repo-root ./devspec_toolkit` (boilerplate). Some prompts add step-specific commands: Prompt 06 adds `invariants-check`, Prompt 08 adds `fixtures-lint`, Prompt 10 adds `governance-check`. The boilerplate validate command should be shared; only additional commands are step-specific.
- **Impact**: The base validate command appears 22 times unnecessarily.
- **Fix**: Extract base validate command to shared_expectations.md. Keep only step-specific additional commands in prompts.

---

## Relationship to P3 Master Findings

| P3 Finding | R2-A Classification Confirms | New Insight |
|---|---|---|
| AUDIT-001 (Discovery prompts lack synthesis reasoning) | YES -- Discovery Phase averages 54% step-reasoning vs Trinity's 81% | Root cause is that boilerplate consumes 30% of Discovery prompts, leaving less room for reasoning |
| AUDIT-006 (Hardening Protocol extractable) | YES -- 88 LOC identical across 22 prompts | Part of a larger 1312 LOC boilerplate problem (10 distinct blocks) |
| AUDIT-008 (Quick Ref subset of Field-by-Field) | YES -- Quick Reference is pure schema duplication (R2-A-005) | BOTH Quick Reference AND Field-by-Field are largely schema duplication (R2-A-007) |
| AUDIT-065 (projected extractable LOC) | Refined -- actual boilerplate is 1312 LOC (23%), total removable is 1924 LOC (34%) | More precise than the P1 estimate |
