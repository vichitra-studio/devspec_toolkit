# graph_example

The worked example of the spec-graph design (a member resets a forgotten password, section 12) as a 1.2.0 spec: one
file per step 00 to 16, the plan file of the one milestone in `spec/impl_context/`, the trace lock in
`spec/extras/trace.lock.json`, one verification record, and the seed `docs/seed/seed_accounts.md`. Everything in it is
invented.

## It is partial on purpose

`specdev spec-check` on this folder does **not** pass. Run on a git copy, it reports 24 errors and 1 warning (2 when the copy lives under a symlinked path such as `/tmp` on macOS: W570). A person
who copies the folder as a starting point should expect that: the design's table "In a real spec, each 'no use shown'
node gets its user before merge" says the example stops short of a finished spec, and the folder stops short in the
same places.

The errors, by code (run `specdev spec-check spec --repo-root <toolkit> --spec-root <folder>/spec --git-root <copy>`;
`spec-check --json` gives the owner of each):

| Code | Count | Check | What it says |
|---|---|---|---|
| E608 | 1 | `toolkit-version` | The folder has no `spec/specdev_version`. Write `toolkit_version: <the toolkit version>` into it first (the tests that stamp a copy do so before they run anything); every other count below holds with the stamp. |
| E740 | 16 | `no-dangling` | A node that nothing uses: three environments (`dev`, `staging`, `prod`), two secrets, `metric-reset-completion-rate`, the criteria `ac-password-reset-1`, `-2`, `ac-password-reset-request-1`, `-2`, `fr-password-reset-request`, `nfr-latency-reset-email`, the rules `rule-security-review-of-token-handling` and `rule-spec-check-on-every-pr`, `ec-token-at-expiry-second` and `threat-reset-token-replay`. |
| E743 | 5 | `verifier-rules` | A criterion or an NFR with no verifier: `ac-password-reset-1`, `-2`, `ac-password-reset-request-1`, `-2` and `nfr-latency-reset-email`. |
| E744 | 1 | `cross-cutting` | `task-implement-password-reset-confirm` falls under `nfr-latency-reset-email` but no criterion of the task refines it. |
| E566 | 1 | `milestone-numbers` | `fr-password-reset-request` is in scope and no task criterion reaches it. |

The API error `err-password-reset-confirm-token-expired` is used: the invariant `inv-reset-token-single-use` names it in
`constrains`. It carries its `http_status` (410), and both fixtures name it in `expects` (a fixture whose `expected.status`
is 400 or more must, E754).

The warning is W555 (the seed has no out-of-scope bullets).

The set is pinned by `tests/integration/test_graph_roles_example.py` (each E740 with its owner step and the part the
example leaves out), `tests/integration/test_graph_example_steps_06_16.py` (`_PINNED_FINDINGS`, the warnings),
`tests/integration/test_merge_mode.py` and `tests/unit/release/_support.py` (the merge and release runs that start from
the example), and `tests/fixtures/step_gate/spec_check_summary.golden`. A change to the folder that adds or removes a
finding changes those on purpose.

## What it holds beyond the design's blocks

Section 12 shows 10 nodes with no use. The folder holds six more, and a second requirement that has no task criterion:

- `fr-password-reset-request`, with its two criteria `ac-password-reset-request-1` and `-2`;
- the criteria `ac-password-reset-1` and `-2` of `fr-password-reset`, beside `ac-password-reset-3`, which the task criterion refines;
- `metric-reset-completion-rate` and the glossary term `term-reset-email-delivery-time-p95`;
- a third responsibility of `identity-service`;
- `auth` and `rate_limit` on the connection `conn-identity-to-mailrelay`, which have no counterpart in the design's blocks.

## Its canon ids are not the design's

The design's blocks show canon ids such as `cn:core:unit:min`, `cn:core:unit:s`, `cn:project:metric:email-delivery-time`,
`cn:project:policy:auth-required` and `cn:project:risk_category:authn`, and an NFR target of `<= 60 s`. The core canon
has none of them. The folder uses ids the canon has: `cn:project:unit:min`, `cn:core:unit:ms` with `"target": 60000`,
`cn:core:metric:p95-response-time`, `cn:core:policy:spec-first` and `cn:core:risk_category:security`, and adds a
`stage_ref` where the design shows none. Carry ids from the design's text into a spec and `spec-check` reports E110.
