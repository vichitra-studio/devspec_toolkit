# Governance Architecture

Developer reference for the enforcement and traceability subsystems that keep spec artifacts consistent.

---

## Removed in 1.2.0: trace types, the trace matrix and the cross-artifact checks

The canon kind `trace_type` (`canon/kinds/trace_type.json`), the module `core/trace_types.py`, the trace matrix builder `validation/matrix.py` (with its entity index), `validation/cross_artifact_checks.py` and `validation/traceability_closure.py` are removed. A link between two nodes is now a link field in the node (`derives_from`, `verifies`, `refines`, and so on) that the graph resolver reads: a link to an id no node has is E700, and `specdev trace`, `specdev coverage` and `specdev stale` read the same graph. See [reference.md](../developers/reference.md).

---

## Step Dependency DAG

Defined in `tools/step_order.json`.

**Structure:**

- `steps`: ordered list of 21 step IDs: `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 14 15 16 16a 16b 16c`
- `step_metadata[<step>].required_spec_inputs`: the steps whose artifacts this step reads.
- `downstream_consumers`: declared on the **provider** side. Each step lists which later steps directly consume its output.

**Policy flags:**

```json
{
  "mode": "strict_waterfall",
  "allow_self_dependency": false,
  "allow_forward_dependency": false
}
```

Replay is the set of suspect links in the trace lock (`spec/extras/trace.lock.json`, E763); `spec-check` and `validate-all` report them. The command `forward-replay-check` and the keys `policy.require_full_forward_replay_on_change` and `policy.status_write_exemptions` were removed in 1.2.0; the schema `schema/step_order.schema.json` allows no other key in `policy` (`additionalProperties: false`). File-level forward replay (the old requirement that every step after a changed step has a changed file) is removed; see [reference.md](../developers/reference.md#trace-lock-replay-and-attest).

**Generated, not hand-kept:** `specdev registry-generate` derives `step_metadata` and `downstream_consumers` from the `x-link` declarations of the step schemas and from the hand-kept `declared_edges` pairs; the two keys are each other's inverse (E543 otherwise). Only `version`, `steps`, `policy` and `declared_edges` are edited by hand.

**Reading the inputs of a step:** `step_metadata["05"].required_spec_inputs` is `["00", "02", "04"]`, and `downstream_consumers["00"]`, `["02"]` and `["04"]` each contain `"05"`. `specdev prompt-context <step>` prints the consumers of a step.

**Fan-out:** steps `00` (Charter), `04` (FRs) and `05` (APIs) have the most consumers; step `14` (Roadmap) feeds the Trinity Loop (`16`, `16a`, `16b`, `16c`). Steps `03` (Glossary: its terms are used by label, not by link) and `16c` have no consumer.

---

## Seed Propagation Boundary

Defined in `spec/common/seed_manifest.json`.

**Routing is manifest-driven:** `spec/common/seed_manifest.json` is the single authoritative source for which seeds apply to which steps and where they live. The `step_requirements` map in the manifest defines per-step seed requirements; the `seeds[]` array defines each seed's `path` and metadata. A seed is routed to every step that distils a part of it: a node of that step lists the seed in `derives_from`, and a route that no node of its step uses is refused (E748), as is a route to step 13 or a trinity step, where no node can list a seed. Steps not listed (or with an empty array) require no seeds; `global_seed_order` governs only the read order of step-required seeds. The `seed-lint` command validates that all referenced seed IDs are declared in the manifest and that each step's usage is consistent with its manifest entry.

---

## Prompt Architecture (Post-Sanitization)

Prompts no longer contain "Context To Ingest" sections. This was a deliberate sanitization to enforce a clean separation:

- **Prompts** define output contracts (JSON schema URI, required fields, validation rules) and operating flows (Clarify/Emit protocol, self-audit gates).
- **Orchestration layer** is responsible for assembling and delivering context (upstream artifacts, seed docs, canon entries) to the AI runner.

This means prompts are portable across orchestration implementations. An orchestration layer reads `step_order.json` to determine which upstream artifacts to inject, and `seed_manifest.json` to determine which seeds to include.

---

## Enforcement Tiers

Validation operates at three levels of dynamism:

### Tier 1: JSON Schema (Static)

- Enums are self-contained in `schema/` files (e.g., `owner` enum in `schema/core/atoms.schema.json`).
- Works fully offline with no canon dependency.
- Validates structure, required fields, types, patterns.

### Tier 2: Hallucination Lint (Dynamic)

- `hallucination_lint.py` loads the canon registry at runtime (`CanonicalRegistry.load`).
- Detects unknown entity references and invalid enum values that JSON Schema cannot catch because the allowed set is externally managed.
- Falls back to the built-in stage set (`KNOWN_STAGES`) when the canon has no stages.

### Tier 3: Canonical Integrity (Fully Dynamic)

- `canonical-integrity` and `canonical-lint` commands operate entirely against the live canon registry.
- Validates that spec artifacts reference only active (non-deprecated) canon entries.
- Checks alias consistency, lifecycle status, and cross-kind reference validity.
- No fallback -- requires a functioning `canon/` directory.

---

## Validation Ritual

The required sequence after any spec edit:

```
1. validate          -- JSON Schema validation of the changed artifact
2. seed-lint         -- verify seed usage matches seed_manifest step_requirements
3. spec-check        -- the graph, role-rule and trace-lock checks
4. fixtures-lint     -- check that each fixture has input and expected (see the note below)
```

`fixtures-lint` recognises a step 08 file by the registry id `vc:08-fixtures` (what the step 08 prompt writes) or by a `$schema` that ends in `/08_fixtures.schema.json` (the only form 1.1.1 read). A fixture of such a file with no `input` or `expected` is `E520`: a file with `{"$schema": "vc:08-fixtures", "fixtures": [{"fixture_id": "fx-a", "mode": "unit"}]}` printed `E520 fx-a: missing input/expected`.

**When to run each check:**

| Trigger | Required checks |
|---|---|
| Any spec file edit | `validate`, `seed-lint` |
| A link field changed (`derives_from`, `verifies`, `refines`, ...) | Add `spec-check`, then `attest` for each node it names (E761, E763) |
| Fixture `input` or `expected` changed | Add `fixtures-lint` (reads no `vc:08-fixtures` file, see the note above) |
| New canon entry added | `canonical-lint`, `canonical-integrity` |
| Commit | `governance-check` against commit message |
| Upstream step changed | `stale` to list the suspect links, `attest` once each is read, then `spec-check` |
| Schema enum modified | `hallucination-lint` to verify specs still conform |
