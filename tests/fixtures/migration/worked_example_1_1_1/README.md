# worked_example_1_1_1

The "Today" blocks of the design's section 12 (a member resets a forgotten password, 12.2 to 12.19), put together as the
1.1.1 host they describe: one file per step, one node per block, the shapes exactly as 1.1.1 wrote them. Everything is
invented. It carries only what section 12 shows (plus the second fixture `fix-password-reset-reused-token` that 12.11 names,
the empty lists a step file needs, and the seed excerpt of 12.1), so it has no collision, no status conflict and no legacy close:
`mini_host_1_1_1` carries those.

`tests/e2e/test_worked_example_migration.py` copies this folder (without this file), makes it a git repository, runs the
migration and compares the result with the "New" blocks of the same section by structure and ids.

| File | Today block |
|---|---|
| `spec/00_charter.json` | 12.2 |
| `spec/01_capabilities.json` | 12.3 |
| `spec/02_system_sketch.json` | 12.4 |
| `spec/02a_delivery_baseline.json` | 12.5 |
| `spec/03_glossary.json` | 12.6 |
| `spec/04_fr_list.json` | 12.7 |
| `spec/05_interface_contracts.json` | 12.8 |
| `spec/06_invariants.json` | 12.9 |
| `spec/07_nfrs.json` | 12.10 |
| `spec/08_fixtures.json` | 12.11 |
| `spec/09_impl_plan.json` | 12.12 |
| `spec/10_governance.json` | 12.13 |
| `spec/11_redteam.json` | 12.14 |
| `spec/12_ci_gates.json` | 12.15 |
| `spec/13_extension_manifest.json` | 12.16 (none-required) |
| `spec/14_roadmap.json` | 12.17 |
| `spec/15_scaffold.json` | 12.18 |
| `spec/16_impl_context.json`, `spec/impl_context/ms_account_recovery_plan.json` | 12.19 |
| `docs/seed/seed_accounts.md`, `spec/common/seed_manifest.json` | 12.1 |
