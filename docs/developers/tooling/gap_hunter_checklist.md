# Gap Hunter Checklist

Run this checklist after meaningful spec changes to catch missing or ambiguous elements before implementation drifts.

## Gap Categories
1. **Missing Fields** — Required schema fields not populated (detected by `validate` / `validate-all`).
2. **Dangling References** — FRs, APIs, or fixtures that point to non-existent IDs.
3. **Ambiguous Language** — Vague statements that cannot be falsified.
4. **Unlinked NFRs** — Targets without metrics, dashboards, or alerts.
5. **Stale Fixtures** — Expected payloads no longer match contracts or invariants.

## Procedure
```bash
# 1. Check schema compliance everywhere
python -m specdev_tools.cli validate-all spec

# 2. Inspect trace coverage (FR ↔ API ↔ Fixture ↔ NFR)
python -m specdev_tools.cli matrix spec --out tools/trace_matrix.json

# 3. Lint fixtures for missing or unknown targets
python -m specdev_tools.cli fixtures-lint spec
```

### Manual Review Pass
- Compare the generated `tools/trace_matrix.json` with expectations under `tests/expectations/`.
- Look for `traceRef` placeholders such as `*-tbd` and replace them with concrete IDs.
- Confirm every NFR in `07_nfrs.json` maps to monitoring assets in `16_delivery_monitoring.json`.
- Ensure threat IDs from `11_redteam.json` appear in `15_redteam_loop.json` updates.
- Spot language like “easy”, “fast”, or “user-friendly” and restate it with measurable criteria.

### Close The Loop
1. Update the affected spec JSON artifacts.
2. Regenerate the matrix and commit the new output.
3. Capture rationale in commit messages following `spec/10_governance.json`.

## Output
A spec set with resolved gaps, refreshed trace matrix, and fixtures aligned with the latest contracts.
