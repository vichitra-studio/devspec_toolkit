# Gap Hunter Checklist

Run this checklist after meaningful spec changes to catch missing or ambiguous elements before implementation drifts.

## Gap Categories
1. **Missing Fields** — Required schema fields not populated (detected by `validate` / `validate-all`).
2. **Dangling References** — FRs, APIs, or fixtures that point to non-existent IDs (E700, E701 in `spec-check`).
3. **Ambiguous Language** — Vague statements that cannot be falsified.
4. **Unlinked NFRs** — Targets without metrics, dashboards, or alerts.
5. **Stale Fixtures** — Expected payloads no longer match contracts or invariants.

## Procedure
1. Run the [core validation commands](../reference.md#core-validation-commands) to verify schema compliance, links, and fixture health.
2. Lint fixtures specifically when targeting new APIs or updating payloads.

### Manual Review Pass
- Run `specdev coverage` (and `specdev coverage --by fr` for one row per FR) and read the ids it lists as not linked. The role findings E740 to E745 of `specdev spec-check` are the gate; `coverage` only shows the counts.
- Confirm every NFR in `07_nfrs.json` maps to monitoring assets in `16_impl_context.json` (Plan.Delivery).
- Ensure threat IDs from `11_redteam.json` appear in `16_impl_context.json` (Plan.Security).
- Spot language like “easy”, “fast”, or “user-friendly” and restate it with measurable criteria.

### Close The Loop
1. Update the affected spec JSON artifacts.
2. Run `specdev stale`, read each suspect link, and edit the holder or `specdev attest` it.
3. Capture rationale in commit messages following `spec/10_governance.json`.

## Output
A spec set with resolved gaps, no suspect links, and fixtures aligned with the latest contracts.
