---

# R9 Derivation Feasibility Assessment

Generated: 2026-03-03
Status: COMPLETE
Related: T29c from r9_findings.md

## Purpose

Assess whether the three core DAG configuration surfaces in `step_order.json` can be
dynamically derived from prompt content rather than manually maintained.

## Assessment

### 1. Can `allowed_upstream_dependencies` be derived from prompt Field-by-Field sections?

**Partially — ~60-70% derivable.**

Each prompt's **Field-by-Field Output Specification** section lists the upstream artifacts
a step consumes. For example, `prompt_05_interface_contracts.md` references
`04_functional_requirements.json` in its FR-trace fields. A static analysis tool could:

- Parse `### Field-by-Field Output Specification` sections
- Extract `**NN_artifact.json**` references
- Map to step numbers

**Irreducible manual surface:**
- Some upstream consumption is implicit (e.g., step 09 uses step 01 capabilities
  conceptually but may not reference the file literally in every field spec)
- Seed document dependencies (`seed_overview.md`, `seed_tech_stack.md`) are not
  step-numbered and require a separate mapping

### 2. Can extraction intent be validated against prompt sourcing text?

**Yes — ~80% derivable.**

Extraction Intent sections are structured as bullet lists mapping
`**NN_artifact.json**: description of what is extracted`. These can be:

- Parsed with `_INTENT_SPEC_ENTRY_RE` regex (already implemented in `dag_lint.py`)
- Cross-referenced against `allowed_upstream_dependencies`
- Validated for completeness (E597) and vagueness (W597)

This is **already implemented** by `extraction_intent_check.py` and `dag_lint.py`.

### 3. Can `downstream_consumers` be derived inversely from `allowed_upstream_dependencies`?

**Yes — 100% derivable.**

`downstream_consumers` is the inverse relation of `allowed_upstream_dependencies`:

```
downstream_consumers[X] = [Y for Y in steps if X in allowed_upstream_dependencies[Y]]
```

This inversion is deterministic and lossless. A `specdev derive-consumers` command could
regenerate `downstream_consumers` from `allowed_upstream_dependencies` at any time.

**Current status:** `downstream_consumers` is manually maintained alongside
`allowed_upstream_dependencies`. This creates a consistency risk (A-R9-02) that
`dag_lint` now enforces via E599 (DAG_CONSUMER_INCONSISTENCY).

**Recommendation:** Consider adding a `specdev derive-consumers` command that
auto-generates `downstream_consumers` from the inverse of `allowed_upstream_dependencies`.
This would reduce the maintenance surface from 2 configuration blocks to 1 and eliminate
E599 violations by construction.

### 4. What is the irreducible manual maintenance surface?

| Surface | Derivable | Manual |
|---------|-----------|--------|
| `allowed_upstream_dependencies` | ~60-70% from prompt field specs | ~30-40% requires domain expertise |
| `downstream_consumers` | 100% (inverse of above) | 0% if auto-derived |
| Extraction Intent sections | N/A (authored in prompts) | 100% authored, validated by tooling |
| `coverage_thresholds` | 0% (policy decision) | 100% requires human judgment |

**Total irreducible surface:** `allowed_upstream_dependencies` for implicit consumption
patterns + `coverage_thresholds` policy values. Everything else is derivable or
enforceable by existing R9 validators.

## Conclusion

The R9 DAG corrections in T04 establish the correct dependency graph. The tooling in
T16 (`dag_lint`) and T14 (`extraction_intent_check`) enforce ongoing consistency.
The primary remaining optimization is auto-deriving `downstream_consumers`, which would
eliminate one of the two manually-maintained DAG surfaces.
