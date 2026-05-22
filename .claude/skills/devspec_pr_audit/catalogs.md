# Audit Catalogs

Stable reference for the `devspec_pr_audit` skill. Two orthogonal catalogs drive every discovery prompt:

- **Drift catalog (D1–D14)** — pairs/tuples of artifacts that must agree. Each catches a class of disagreement.
- **Invariant catalog (I1–I13)** — defect classes that are not pairwise drift (write-only metadata, lifecycle gaps, coverage, hygiene).

The catalogs are file-type agnostic. They survive toolkit evolution. Slice manifests declare which catalog items apply per slice; discovery agents apply only the declared subset.

---

## Drift catalog

Every audit asks, for each drift type: *"Are there two artifacts in scope that should agree on this axis, and don't?"*

Each D-type carries a `cross_boundary_candidate` annotation indicating whether it commonly manifests *across* slice boundaries (Phase 3 agent's responsibility) in addition to *within* a slice (Tier-2 agent's responsibility). Intra-slice-only D-types are handled exclusively by Tier-2; cross-boundary candidates run in both Tier-2 (within-slice instances) and Phase 3 (across-slice instances).

### D1 — Definition ↔ duplicate definition
**Generic pattern.** The same rule, value, or definition is asserted in two or more files; one is authoritative and the others restate it.
**Detection lens.** Find values present in artifact A and artifact B (same enum / same number / same constraint / same identifier list). If both exist independently, who owns it? Is the non-owner restating, or referencing?
**Example shape.** A required-fields list in a schema and a "fields you must include" line in a prompt; a numeric threshold in code and in docs.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D2 — Producer ↔ consumer shape
**Generic pattern.** Producer emits an artifact with shape X; consumer expects shape Y; X and Y diverge in field names, types, or required-ness.
**Detection lens.** For every produced artifact in scope, identify each consumer (validator, downstream step, generator, docs). Compare expected shape against produced shape.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D3 — Code ↔ docs
**Generic pattern.** Documented behavior, surface, or flag does not match the implementation that ships.
**Detection lens.** Every documented command/flag/symbol must resolve to real code; every public code surface must have a documented entry. Compare `--help` output to documented usage; compare exported symbols to documented APIs.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D4 — Code ↔ tests
**Generic pattern.** Test assertions encode an expectation the code no longer satisfies (or vice versa); tests pass but the contract has drifted.
**Detection lens.** For changed code surfaces, find tests that reference them. Inspect whether the test still validates the *current* contract or a stale one.

### D5 — Schema ↔ instance
**Generic pattern.** An artifact instance violates the schema it declares conformance to.
**Detection lens.** For every changed instance, validate against declared schema. For every changed schema, check existing instances still conform.

### D6 — Reference ↔ target
**Generic pattern.** Named ID, path, or symbol referenced in artifact A does not resolve in artifact B that A points to.
**Detection lens.** Every reference (ID string, `$ref`, file path, anchor link, glob) must resolve. Cross-artifact ID tables: every referenced ID exists as a defined ID somewhere.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D7 — Upstream ↔ downstream
**Generic pattern.** A change to an upstream artifact is not propagated to dependent downstream artifacts.
**Detection lens.** For each changed file, walk declared downstream dependents. Either each dependent reflects the change (renamed field, new constraint, removed value), or no propagation was needed (justified). Includes content-staleness, not just ID resolution.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D8 — Metadata N-tuple agreement
**Generic pattern.** Three or more files encode the same conceptual relationship (dependency graph, ownership list, registration set). All N must agree.
**Detection lens.** Identify metadata triples/N-tuples in scope. Cross-check: is every member present in every place it should be? Are the relations symmetric where they should be?
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D9 — Generator ↔ generated
**Generic pattern.** A file is declared generator-owned but its committed contents diverge from what the generator would emit now.
**Detection lens.** For every generator-owned path, re-run the generator (or its check mode) and diff against the committed file. Any drift = D9.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D10 — Spec ↔ implementation
**Generic pattern.** A specification, contract, or prompt describes behavior the implementation does not actually provide.
**Detection lens.** Compare declared semantics (in specs, contracts, schemas, prompt instructions) against runtime behavior or code paths. Find declared promises with no enforcer.

### D11 — Changelog ↔ change
**Generic pattern.** A code/schema/prompt/CLI change ships without a changelog entry, or a changelog entry references a change that isn't in the diff.
**Detection lens.** Inventory of files changed in the PR. For each, is there a matching changelog entry (in the active unreleased section or the appropriate version file)? For every changelog entry added in this PR, does a real diff back it? Also: did a release ship without promoting `unreleased` content?
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D12 — Version ↔ migration
**Generic pattern.** A version bump occurred without the migration artifacts the version policy requires, or migration artifacts exist without an accompanying version bump.
**Detection lens.** Compare version string changes against migration-prompt presence, migration-test presence, and breaking-change documentation. Conversely, look for breaking-change indicators (renamed/removed fields, changed enums) without a version bump.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

### D13 — Deprecation ↔ replacement
**Generic pattern.** Something is marked deprecated/sunset but its replacement is missing, unreferenced, or non-functional; or a deprecation marker lacks the lifecycle fields its registry requires.
**Detection lens.** For every deprecation marker, verify: replacement target exists, replacement is referenced from at least one active code path, sunset/owner/lifecycle fields are populated and within their policy window.

### D14 — Schema-authority delegation drift
**Generic pattern.** A consumer artifact restates constraints (types, enums, numeric bounds, required-ness, pattern strings) that are owned by a declared producer (schema, registry, manifest), rather than delegating to the producer as the single authority.
**Detection lens.** For each consumer artifact in scope, find restatements of constraints that the declared producer already encodes. The consumer should reference the producer (via a Schema Authority directive, `$ref`, or equivalent), not duplicate its constraints inline.
**Example shape.** A prompt's field-level guidance lists enum values that already exist as `enum` in its declared schema; a doc page restates numeric thresholds defined in code constants.
**Cross-boundary candidate.** True — typically manifests across slice boundaries.

---

## Invariant catalog

For each invariant, the audit asks: *"Does this scope violate this invariant anywhere?"*

### I1 — Single source of truth
**Lens.** For any rule, value, or definition that exists in scope, exactly one file owns it. All other mentions reference, not restate.
**Caught defects.** Duplications that exist but haven't yet drifted, restating where referencing would suffice, missing canonical ownership (no single file is the declared authority for a definition).

### I2 — Producer–consumer closure
**Lens.** Every produced artifact / field / surface has at least one consumer. Every consumed reference resolves to a producer.
**Caught defects.** Write-only metadata (no reader), orphan references (no resolver), dead-end producers (no downstream). Caught defects also include metadata fields populated by writers (often AI-generated) where no validator, generator, or downstream consumer ever reads them — "self-report theater" — fields that exist only to satisfy a checklist.

### I3 — Contract conformance
**Lens.** Every artifact satisfies the contract it declares (schema, prompt output spec, function signature).
**Caught defects.** Schema violations, prompt outputs that fail their declared schema, function calls with mismatched arity.

### I4 — Cross-artifact referential integrity
**Lens.** Every reference between artifacts (IDs, paths, anchors, imports) resolves to its target. No dangling pointers.
**Caught defects.** Broken links, missing imports, undefined IDs referenced from elsewhere.

### I5 — Forward-edge propagation
**Lens.** When upstream changes, downstream re-validation / re-generation / re-testing is triggered. Mechanisms exist and are enabled.
**Caught defects.** Disabled replay, ID-only replay missing content drift, non-fatal warnings where errors are required.

### I6 — Determinism / zero-inference
**Lens.** No instruction or schema field invites guessing, fabrication, or unsourced choice. Ambiguity routes to an explicit declared escape valve (escape valves in this toolkit: `coverage_gaps[]` arrays in spec artifact schemas for untraceable content; `## Clarify → Emit` protocol in prompt contracts for ambiguous requirements).
**Caught defects.** Vague modal language ("may", "consider", "if appropriate"), free-text fields with no sourcing rule, missing escape-valve for gaps.

### I7 — Lifecycle completeness
**Lens.** Anything with declared states (deprecation, version, warning→error promotion, sunset, status) has every required state field populated and policy-conformant.
**Caught defects.** Deprecations without sunset dates, codes that should be promotable but aren't, versions without changelog; codes that the policy declares promotable (e.g., via `SPECDEV_PROMOTE_CODES` / `SPECDEV_WARNINGS_AS_ERRORS`) but lack the registry fields required for promotion.

### I8 — Coverage
**Lens.** Every declared rule, error code, branch, edge case has at least one test or fixture that exercises it. Tests assert specific failures, not just generic ones.
**Caught defects.** Untested error codes, schemas with no negative fixtures, validators with no test, edge cases declared but not exercised.

### I9 — Discoverability / canonical location
**Lens.** Every public surface (command, error code, schema, env var, hook) is documented in exactly one canonical place, and that place is findable from the standard entry points. When a surface is documented in multiple places intentionally (agent docs vs developer docs vs user docs), each audience document must justify its existence with audience-specific content; pure duplication across audiences is a violation.
**Caught defects.** Undocumented features, features documented in N places without cross-link, canonical reference doc missing entries.

### I10 — Environment portability
**Lens.** No artifact assumes a specific machine, user, CWD, or OS. All locations resolved through declared roots (`--repo-root`, `--spec-root`, `--git-root`) or runtime discovery.
**Caught defects.** Hardcoded absolute paths, machine-specific assumptions, scripts that only work from one directory.

### I11 — Governance / changelog discipline
**Lens.** Every change ships with the governance artifacts policy demands: changelog entry, migration path for breaking changes, version bump when contracts change, CI gates that fail when policy is violated.
**Caught defects.** Silent breaking changes, missing CI enforcement for declared policies, governance fields that exist but aren't enforced; policies named in env-var contracts (e.g., `SPECDEV_*` flags) that have no enforcement path in CI.

### I12 — Hygiene
**Lens.** No dead code, redundant files, broken links, deprecated syntax, hedge language in normative docs, machine-specific artifacts, or stale comments.
**Caught defects.** Orphan files, broken markdown links, deprecated GitHub Alert syntax, comments referencing removed paths, hedge language ("appears to", "likely", "probably") in findings or normative prose.

### I13 — Upstream derivation traceability
**Lens.** Every spec artifact field whose value must be derived from an upstream artifact or seed declares its source. Untraceable content routes to a declared escape valve (e.g., `coverage_gaps[]`) with the upstream identifier, source step, and reason populated.
**Caught defects.** Derived fields without a declared source, missing `coverage_gaps` entries when content cannot be sourced to an upstream artifact, escape-valve entries with empty or unpopulated rationale.

---

## How catalogs are applied

A discovery agent is given, per slice:
- The slice's files (full source for owned files; digests for cross-slice neighbors)
- The applicable subset of D1–D14 and I1–I13 (declared in `slices.yaml`)
- The drift-pair partners in scope (which other slices it should cross-reference via digests)

For each applicable catalog item, the agent emits findings keyed by catalog ID. Severity follows the findings schema: `P0 | P1 | P2` (P0 = blocker, P1 = high, P2 = medium-or-low (the findings schema collapses these into a single severity bucket; fix-plan `priority` separates them: P2 = medium, P3 = low/docs/cleanup)). The Part B `priority` field carries finer-grained ordering (P0/P1/P2/P3) when ranking fix tasks. Findings tagged with catalog IDs let the consolidator dedupe deterministically and the verifier check coverage.

The cross-boundary agent (Phase 3) re-applies the **drift-only** subset (D1–D14) across slice boundaries, using digests as the agreement surface. Intra-slice drift is the Tier-2 agents' responsibility; cross-slice drift is Phase 3's exclusive responsibility.

Review-protocol meta-defects (hedge language in findings, unconfirmed `file:line` citations, orphan findings, multi-file tasks, missing test/doc pairs) are governed by the L2 verifier checklist, not by D/I items in this catalog.

---

## Adding to the catalogs

Adding a new D-type or I-type is a deliberate change to the audit contract:

1. Confirm the defect class is **generic** (file-type agnostic, would apply to any schema-driven pipeline).
2. Confirm it is **not subsumed** by an existing item.
3. Append to this file with the same shape: name, generic pattern, detection lens.
4. Update `slices.yaml` to declare which slices it applies to.
5. Update prompt templates if the new item requires special handling.

Reject any proposed addition that names a specific file, error code, validator, or past bug. Such additions belong in slice-specific checklists, not the generic catalog.
