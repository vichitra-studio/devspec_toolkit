# Deep Architectural Review: Schema Design Questions Q3-Q6

Reviewed: 2026-03-19
Method: Workflow-first analysis grounded in actual prompts, spec files, schemas, and fixtures.

---

## Q3: generation_quality

### Workflow Context

Every prompt instructs the LLM to use a "Self-Audit Gate" before emitting JSON. The prompt says:
> "Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation."

The intent is clear: when an LLM generates a spec artifact, it should explicitly declare which assumptions it made -- things like "assumed OAuth2 is the auth mechanism because seed_overview mentions SSO" or "assumed a single-region deployment because no multi-region constraint was stated." This is a form of LLM introspection that creates an audit trail for human reviewers.

### What the Data Actually Looks Like

**Every single fixture and spec file in the entire codebase has `"assumptions": []`.**

- `spec/05_interface_contracts.json`: `"assumptions": []`
- All test fixtures across step_01, step_02a, step_12, step_13: `"assumptions": []`
- Every prompt's Output Contract example shows `"assumptions": []`
- Zero instances of non-empty assumptions exist anywhere in the repository.

The prompts instruct the LLM to populate this field, but the Output Contract examples (which LLMs weight heavily when generating) show it empty. This creates a conflicting signal: the prose says "populate it" but the exemplar says "leave it empty."

### Analysis

The *idea* is sound. When an LLM generates a spec for a real product, it genuinely does make assumptions -- about scope boundaries, about which seed statements take priority when they conflict, about how to interpret ambiguous requirements. Making those assumptions explicit is valuable for:

1. **Human review**: A reviewer can scan assumptions to catch bad inferences early
2. **Replay stability**: When seeds change, assumptions tell you which parts of the spec might be invalidated
3. **Clarify-vs-Emit decisions**: An assumption that scores low confidence should have triggered a clarification question instead

However, the current structure (`{"assumptions": [...]}`) is over-wrapped. There is exactly one field in the object. The wrapper object adds no information -- it exists only because the field was designed anticipating future siblings (confidence_score, audit_notes, etc.) that never materialized.

### Verdict: SIMPLIFY

**Action**: Flatten `generation_quality` from `{"assumptions": [...]}` to just `assumptions: [...]` as a direct top-level field on each spec artifact. Remove the wrapper object.

**Rationale**:
- The wrapper object `generation_quality` has had a single child (`assumptions`) since inception with no evolution. YAGNI.
- A flat `"assumptions": []` is simpler for LLMs to populate -- fewer nesting levels = fewer structural errors.
- The field's purpose (LLM introspection audit trail) is genuinely valuable in the workflow, so removing it entirely would lose a useful self-correction mechanism.
- Fix the Output Contract examples in prompts to show 1-2 populated assumptions, breaking the "always empty" pattern.

### Impact

- Schema change: Remove `generationQuality` from `collections.schema.json`; add `assumptions` as a direct `stringArray` property in each step schema's `required` list.
- Prompt change: Update Output Contract examples to show non-empty assumptions (e.g., `"assumptions": ["Assumed single-region deployment based on seed_tech_stack omitting multi-region"]`).
- Migration: Mechanical -- lift `generation_quality.assumptions` to top-level `assumptions` in all existing specs.
- Test fixtures: Update all fixtures (mechanical find-and-replace).

---

## Q4: seed_refs in Every Spec File

### Workflow Context

The workflow has two mechanisms that tell the LLM which seeds to read:

1. **seed_manifest.json `step_requirements`**: Declares which seeds each step MUST ingest. Step 00 needs `["seed-overview", "seed-tech-stack"]`. Step 04 needs `["seed-overview"]`. Steps 05+ have no seed requirements at all.

2. **Prompt "Seed Ingestion Protocol"**: Every prompt instructs the LLM to read `seed_manifest.json`, ingest required seeds, and "Populate `seed_refs[]` with actually-used seed IDs and content hashes."

3. **The `seed_refs` field in the spec output**: The LLM writes which seeds it actually consumed into the generated artifact.

The question is whether #3 is redundant given #1 and #2.

### What the Data Actually Looks Like

- `spec/05_interface_contracts.json`: `"seed_refs": []` -- Step 05 has no seed requirements
- Prompt 05 Coverage Closure checklist explicitly says: `seed_refs is [] (this step derives from upstream specs, not seeds)`
- Test fixtures for step_01, step_02a show `"seed_refs": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}]`
- The `seedRef` schema supports optional `section`, `note`, `hash`, and `version` fields

For early steps (00-04), `seed_refs` duplicates what `step_requirements` already declares. For later steps (05+), it is always `[]`.

### Analysis

There are two possible workflow values for `seed_refs`:

**Value 1: Hash-based staleness detection.** The `seedRef` schema includes a `hash` field (SHA-256). If the LLM records the hash of the seed at generation time, downstream tooling can detect when seeds have changed and flag that specs need regeneration. This is genuinely valuable -- but no spec or fixture in the codebase actually populates the `hash` field. The infrastructure exists but is unused.

**Value 2: Section-level citation.** The `seedRef` schema includes a `section` and `note` field. An LLM could write `{"seed_id": "seed-overview", "section": "Business Objectives", "note": "Derived success metrics from stated KPIs"}`. This would be genuinely useful for traceability -- knowing not just THAT a seed was used, but WHICH PART informed WHICH output. But again, no existing spec or fixture uses these fields.

**The redundancy argument**: For steps with seed requirements, the *list* of seed IDs is fully determined by `step_requirements`. The LLM cannot choose to ignore a required seed. So `seed_refs` as a mere list of IDs is purely redundant with `seed_manifest.json`.

**The non-redundancy argument**: `seed_refs` could carry richer data (hash, section, note) that `step_requirements` cannot. But currently it never does.

### Verdict: SIMPLIFY

**Action**: Make `seed_refs` optional (remove from `required[]`). When present, require at least `hash` to justify its existence. For steps with no seed requirements (05+), validators should accept its absence entirely.

**Rationale**:
- As currently used (bare `seed_id` only), it is 100% redundant with `step_requirements`.
- The field has unrealized potential (hash-based staleness, section citations) that justifies keeping it in the schema -- but only when that potential is exercised.
- Making it optional eliminates the "always empty `[]`" busywork for steps 05-16c (17 of 22 steps) while preserving the mechanism for steps that benefit from it.
- If hash-based staleness detection is implemented later, the field can be promoted back to required for seed-consuming steps only.

### Impact

- Schema change: Remove `seed_refs` from `required[]` in step schemas for steps 05+. For steps 00-04, keep it required but add `minItems: 1` (since these steps MUST consume seeds).
- Prompt change: Remove the "Populate seed_refs" instruction from prompts for steps that have no seed requirements. For seed-consuming steps, update the instruction to require `hash` population.
- Validator change: `seed_lint` should not flag missing `seed_refs` when `step_requirements` for that step is empty or undefined.
- Migration: Remove empty `"seed_refs": []` from steps 05+ (or leave as-is; making optional means both presence and absence are valid).

---

## Q5: canonical_proposals and canonical_conflicts (Required vs Optional)

### Workflow Context

The canonical registry (`canon/manifest.json`) contains a vocabulary of shared terms: units, stages, environments, roles, NFR categories, trace types, etc. When an LLM generates a spec for a real product, it encounters product-specific domain terms that do not exist in the generic canonical registry. The workflow provides two mechanisms:

- **`canonical_proposals`**: The LLM proposes new canonical entries (e.g., "this product uses 'loyalty-points' as a unit, which isn't in the registry").
- **`canonical_conflicts`**: The LLM flags when a value could match multiple canonical entries (e.g., "the term 'session' could be `cn:core:entity:session` or `cn:auth:concept:session`").

Every prompt's "Canonical Binding Rules" section says:
> `canonical_proposals` is REQUIRED (may be empty `[]`). Populate it for any new term...
> `canonical_conflicts` is REQUIRED (may be empty `[]`). Populate it when a field value matches multiple canonical entries...

### What the Data Actually Looks Like

**Every single spec file and fixture has `"canonical_proposals": []` and `"canonical_conflicts": []`.**

Zero non-empty instances across the entire codebase. The fields are universally empty.

This is partly explained by the toolkit being used to spec *itself* (the devspec_toolkit's own spec/), where the canonical registry already covers all terms. In a real product repo, these fields would more likely be populated. But the evidence shows that the LLM consistently produces empty arrays even when the prompt says to populate them.

### Analysis

**The `required` + `default: []` question**: In JSON Schema 2020-12, `default` is an annotation keyword with no validation effect. A field listed in `required[]` MUST be present in the JSON document regardless of `default`. So yes, the LLM MUST explicitly produce `"canonical_proposals": []` in its output. The `default` annotation does not excuse absence.

**LLM cognitive load**: The prompts dedicate an entire "Canonical Registry" section (8 lines of dense instructions) to these fields. For a typical spec generation task, the LLM must:
1. Load `canon/manifest.json`
2. Load `canon/aliases.json`
3. Search for matching entries
4. Decide whether to propose or flag conflicts
5. Produce the structured output

This is significant cognitive overhead for a field that is almost always empty. The LLM spends attention budget on canonical matching when the real work is spec generation.

**When it matters**: `canonical_proposals` would be valuable when onboarding a new product to the toolkit. The first few specs would generate many proposals (new domain terms, product-specific units, custom roles). But after that initial phase, the canonical registry stabilizes and proposals become rare.

**The `required` problem**: Making these required forces the LLM to *always* reason about canonical matching, even when there is nothing to propose or conflict. Making them optional would let the LLM skip this entire reasoning path when it has no findings to report -- and only engage the canonical machinery when it encounters genuinely novel terms.

### Verdict: MAKE OPTIONAL

**Action**: Remove `canonical_proposals` and `canonical_conflicts` from `required[]` in all step schemas. Keep them defined in `properties` with their current structure. Keep `default: []` as documentation. Update prompts to say "populate ONLY IF you encounter novel terms or ambiguous matches."

**Rationale**:
- Required empty arrays impose cognitive overhead on LLMs for zero information gain in the common case.
- The canonical matching workflow is genuinely valuable during product onboarding but is wasted effort in steady-state.
- Making optional preserves the mechanism for when it's needed while eliminating busywork when it's not.
- JSON Schema `default: []` means validators/consumers can treat absence as equivalent to `[]`.
- The canonical registry's value comes from `canonical_refs_used` (which references EXISTING entries) -- that field SHOULD remain required. Proposals and conflicts are edge-case signals.

### Impact

- Schema change: Remove `canonical_proposals` and `canonical_conflicts` from `required[]` in all step schemas (approximately 20 schemas). Keep in `properties`.
- Prompt change: Reduce "Canonical Binding Rules" from 5 mandatory items to 3 (keep rules for `canonical_refs_used`, `generation_quality`, and `*_ref` binding; make proposals/conflicts conditional).
- Validator change: Validators that check for presence of these fields should treat absence as `[]`.
- Token savings: Estimated 100-200 tokens per spec generation from reduced prompt instructions and output boilerplate.

---

## Q6: seed_manifest.json Simplification

### Workflow Context

`seed_manifest.json` serves as the configuration file that tells the pipeline:
1. Which seed documents exist and where they live (`seeds[]`)
2. What order to read them (`global_seed_order`)
3. Which steps need which seeds (`step_requirements`)
4. Grouping of seeds (`nested_order`)
5. Documentation policy (`docs_policy`)

`step_order.json` serves as the pipeline configuration:
1. Step execution order (`steps[]`)
2. Allowed upstream dependencies per step (`allowed_upstream_dependencies`)
3. Coverage thresholds (`coverage_thresholds`)
4. Downstream consumer mapping (`downstream_consumers`)

### What the Data Actually Looks Like

**seed_manifest.json**:
- `global_seed_order`: `["seed-overview", "seed-tech-stack"]` -- 2 items
- `nested_order`: 1 level ("foundation") containing both seeds -- adds zero information beyond `global_seed_order`
- `step_requirements`: Maps steps 00-04 to their required seeds. Steps 05+ have no entries.
- `seeds[]`: 2 entries with path, description, required flag, source_type
- `docs_policy`: README enforcement config (scope, exclusions, depth) -- conceptually unrelated to seeds

**step_order.json**:
- `steps[]`: The 22-step waterfall sequence
- `allowed_upstream_dependencies`: Every step lists ALL prior steps (strict waterfall = cumulative). Step 04 depends on `["00","01","02","02a","03"]`. Step 16c depends on all 21 prior steps.
- `coverage_thresholds`: `{"fr_coverage": 80, "mode": "warn"}` -- one threshold
- `downstream_consumers`: Selective mapping of which downstream steps actually consume each step's output (sparser than allowed_upstream_dependencies)

### Analysis

**nested_order**: With exactly 2 seeds both in a single "foundation" level, `nested_order` provides zero workflow value. It would matter if there were 10+ seeds organized into phases (e.g., "foundation" seeds read before "domain" seeds read before "integration" seeds). For the current 2-seed reality, it is pure structure-for-structure's-sake.

However, the toolkit is designed to be vendored into product repos. A product with a complex domain might have 5-8 seeds (overview, tech stack, domain model, integration landscape, compliance requirements, analytics taxonomy). In that scenario, `nested_order` could provide meaningful grouping. But even then, `global_seed_order` already provides the reading order, and `step_requirements` already maps seeds to steps. What `nested_order` adds is *human-readable grouping* -- a documentation concern, not a workflow concern.

**allowed_upstream_dependencies**: In a strict waterfall, this is fully derivable from position in `steps[]`. Step N can depend on all steps before it. The explicit enumeration is redundant:

```
Step "04" -> ["00","01","02","02a","03"]  -- this IS just "all steps before 04 in the steps array"
```

The only scenario where explicit enumeration adds value is if the waterfall is NOT strict -- if some steps could skip certain predecessors. But the `policy.mode` is `"strict_waterfall"` and `policy.allow_forward_dependency` is `false`. Under strict waterfall, the dependency list is mechanically derivable and adds maintenance burden (must be updated if steps are added/reordered).

**downstream_consumers**: Unlike `allowed_upstream_dependencies`, this is NOT derivable. It records the *actual* consumption relationships (which steps read which outputs), not the *allowed* relationships. Step 02a only feeds into step 12, despite being upstream of 18 other steps. This is genuine workflow knowledge that cannot be derived from position. It is used by `specdev prompt-context` to generate the "downstream consumers" note at the top of each prompt.

**coverage_thresholds**: A single configurable threshold (`fr_coverage: 80%`). This is legitimately workflow-configurable -- different products might want 60% or 95% coverage. However, it lives in `step_order.json`, which is primarily a structural/ordering config. It belongs in a separate config or at least has no strong reason to be here.

**docs_policy in seed_manifest.json**: README enforcement configuration (scope, exclusions, depth rules) has nothing to do with seed documents. It was likely placed here because seed_manifest was the only "project config" file available. This is a clear separation-of-concerns violation.

### Verdict: SIMPLIFY

**Actions (4 specific changes)**:

1. **Remove `nested_order`** from `seed_manifest.json`. It provides zero workflow value for 2 seeds and `global_seed_order` + `step_requirements` cover all actual use cases. If a future product needs seed grouping, add it then.

2. **Remove `allowed_upstream_dependencies`** from `step_order.json`. Under strict waterfall policy, it is fully derivable from position in `steps[]`. The derivation should happen in code: `allowed_upstream_deps(step) = steps[0:index_of(step)]`. This eliminates ~120 lines of redundant, maintenance-heavy configuration.

3. **Extract `docs_policy`** from `seed_manifest.json` into its own config file (e.g., `spec/common/docs_policy.json` or merge into a general project config). Seeds and documentation enforcement are unrelated concerns.

4. **Keep `downstream_consumers`** in `step_order.json`. It encodes non-derivable workflow knowledge (which steps actually READ which outputs vs which steps are merely sequentially later). This is the valuable, non-redundant part of the config.

5. **Keep `coverage_thresholds`** in `step_order.json`. While conceptually separate from ordering, it is a small, stable config block and splitting it out would create config file proliferation for minimal benefit.

6. **Keep `step_requirements`** in `seed_manifest.json`. It answers the question "which seeds does each step need?" which is the manifest's core responsibility. This is NOT redundant with step_order because step_order says nothing about seeds.

### Impact

- **seed_manifest.json**: Remove `nested_order` (saves ~10 lines). Extract `docs_policy` into separate config (saves ~20 lines, fixes separation of concerns). Remaining file is lean: `seeds[]`, `global_seed_order`, `step_requirements`.
- **step_order.json**: Remove `allowed_upstream_dependencies` (saves ~120 lines). Remaining file: `policy`, `steps`, `downstream_consumers`, `coverage_thresholds`. Code that needs dependency info derives it from `steps[]` position.
- **Tool changes**: `forward_replay_check.py` and `dag_lint.py` would need to derive dependencies from step position instead of reading the explicit map. This is a ~5-line code change per file.
- **Risk**: If the toolkit ever needs non-strict waterfall (where some steps skip predecessors), the explicit dependency map would need to be reintroduced. But the current `policy.mode: "strict_waterfall"` makes this unlikely without a major design change.
