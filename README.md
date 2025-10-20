
# AI Spec Driven Development Toolkit (v3 Full)

A schema‑first, AI‑assisted workflow that turns **spec → implementation** into a deterministic pipeline. Every step produces a **machine‑checkable artifact** that CI enforces.

---

## Why this exists

- **Clarity for humans, structure for AIs.**
- **Falsifiability:** each statement is testable.
- **Traceability:** FRs ↔ APIs ↔ Fixtures ↔ NFRs.
- **Early delivery:** CI from Step 0, not as an afterthought.

If you want vibes, go start a mood board. If you want software that ships, keep reading.

---

## How it fits in your repo

Most teams vendor this toolkit as a git submodule in their primary product repository. This toolkit expects to live at the repo root as `./devspec_toolkit/`, and every command shown below assumes you run it from that root. If you keep the toolkit somewhere else, substitute your path consistently.

```
<product-repo>/
├─ spec/                         # your live artifacts (json + guides)
├─ ./devspec_toolkit/        # this toolkit (read-only unless upgrading)
│  ├─ README.md
│  ├─ docs/
│  ├─ prompts/
│  ├─ schema/
│  ├─ template/
│  └─ tools/
└─ …
```

When you generate or edit a step, copy the matching guide template from `template/` into your repo’s `spec/NN_name.guide.md` and store the AI-generated JSON beside it (for example, `spec/04_fr_list.json`).

The `example/devspec_kit/` directory shows a fully specced reference implementation for the toolkit itself; treat it as an end-state example, not scaffolding to copy.

## Toolkit layout (canonical)

```
<toolkit-root>/
├─ README.md
├─ docs/                         # meta-workflows (discovery, pipeline, coverage, gaps)
├─ schema/                       # JSON Schemas per step (00–17, 02a) + core atoms/collections/errors
├─ prompts/                      # prompt_XX_stepname.md (deterministic, schema-anchored)
├─ template/                     # per-step guide blueprints for spec authors
├─ tests/
│  ├─ fixtures/                  # data used by Step 14 impl
│  ├─ samples/                   # invariant evaluation contexts
│  └─ expectations/              # expected matrices, etc.
├─ tools/
│  ├─ requirements.txt
│  ├─ schema_registry.json       # maps $schema URIs → local files
│  └─ specdev_tools/             # CLI package
└─ .github/workflows/ci.yml      # generated or hand-curated pipeline
```

**Toolkit root** is the directory where you checked out the toolkit (for example, `./devspec_toolkit/`). The CLI resolves `$schema` via `tools/schema_registry.json` relative to this folder, even when your spec artifacts live in the host repo.

---

## Quick start

```bash
# ensure you run this from repo root so ./devspec_toolkit/... resolves

python -m venv .venv && . .venv/bin/activate
pip install -r ./devspec_toolkit/tools/requirements.txt

# Make the toolkit modules importable
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

The CLI covers validation, traceability, fixtures, invariants, governance, CI generation, scaffolding, and ai-help reminders. `docs/developers/reference.md` is the canonical cheat sheet showing each command with the required `--repo-root ./devspec_toolkit` flag.

➡️ For a narrated walkthrough of the workflow, see `docs/developers/getting_started.md` in this toolkit.

---

## Workflow (Mandala model)

**Phase I · Spec Discovery (0–12)** → define, constrain, verify the specification.  
**Phase II · Spec → Implementation (13–17)** → generate scaffold, implement via fixtures, red‑team, ship, and audit drift.

Each step has:
- `spec/NN_name.json` → **authoritative machine artifact** (validates against `schema/NN_name.schema.json`).
- `spec/NN_name.guide.md` → **human playbook** (purpose, DoR/guardrails, checks, failure modes).
- `prompts/prompt_NN_name.md` → **deterministic instruction** to produce the JSON (single fenced code block).

No examples inside prompts. Reference artifacts live under `example/` and `tests/fixtures/`.

---

## Conventions

- **IDs:** kebab‑case, stable, unique.
- **Owners:** one of `{api, ui, system, ops, data}`.
- **JSON only:** output is a single fenced `json` block validating against the embedded schema URI.
- **No redefining primitives:** use core atoms/collections/errors from `schema/core/`.

---

## CLI reference

Keep `docs/developers/reference.md` as the single source of truth for CLI commands, naming conventions, and troubleshooting flows. This README only highlights the quick-start sequence above. Exit code 0 means OK. Anything else means fix your specs.

---

## How `$schema` resolution works

Artifacts carry `$schema` URIs like:
```
"https://specdev.local/schema/04_fr_list.schema.json"
```
The CLI looks up that URI in `tools/schema_registry.json` and loads the corresponding file from `schema/`. If you move files, update the registry. If you run outside repo root, pass `--repo-root`.

> ⚠️ Editors do not know about `specdev.local`. To avoid “schema cannot be resolved” warnings in VS Code/JetBrains, either map your spec files to the local schema paths via editor settings (e.g. `.vscode/settings.json`) or serve the schemas yourself (add `specdev.local` to `/etc/hosts` and run `python -m http.server` inside `./devspec_toolkit/schema`). The CLI already resolves everything offline; this caveat only affects IDE hints.

---

## CI pipeline sketch

Minimal gates (can be generated via `gen-ci`):
1) **validate** — schema and link checks.  
2) **scaffold** — ensure route map and contracts compile.  
Extend with tests, red‑team, deploy, and drift audit as you mature.

---

## Tests

See `tests/README.md` for commands and guardrails. The folder includes fixtures for login, invariant samples, and an expected trace matrix that should match your spec state.

---

## Troubleshooting

- **Schema not found:** run from repo root or pass `--repo-root`. Confirm `tools/schema_registry.json` paths.
- **Unknown API in fixtures:** define it in `05_interface_contracts.json` or fix the target IDs.
- **Invariant eval returns null:** your expression references missing keys; update the sample or the rule.
- **Commit message rejected:** align with `10_governance.json` `commit_message_rules.pattern`.

---

## Versioning

- Prompts and schemas use independent semver lines.
- Breaking changes bump major and update CI, registry, and guides accordingly.

---

## Requirements

- Python 3.10+
- Node.js (optional, for running the generated scaffold)

---

## License

Choose what suits your org (Apache‑2.0, MIT, etc.). Put it in `LICENSE` and relax your legal team.

---

## Components of the toolkit

### 1) `schema/` (machine guardrails)
- **Purpose:** defines the JSON Schemas for each step (00–17, 02a) and the **core** primitives.
- **Core:** `core/atoms/1` (kebabId, owner, timestamp, tag), `core/collections/1` (kebabIdArray, stringArray, link, traceRef, errorState, anyJson), `core/errors/1` (errorState).
- **Rule:** do not redefine atoms/collections/errors in artifacts; reference them via `$ref` in step schemas.
- **Change control:** bump semver and update `tools/schema_registry.json` when paths/IDs change.

### 2) `prompts/` (deterministic authoring)
- **Purpose:** contracts that instruct an AI to emit **one** fenced `json` block conforming to the embedded schema.
- **Shape:** Role, Task, Output Rules, Clarification Questions (≤3), Embedded Schema (verbatim), Output Contract.
- **Rule:** no examples inside prompts; reference material lives under `example/` and `tests/fixtures/`.

### 3) `spec/` (authoritative specs)
- Stored in your host repository’s `spec/` directory; copy guide templates from `./devspec_toolkit/template/` before editing.
- **Two files per step:**
  - `NN_name.json` — canonical, machine-checkable artifact with `$schema`.
  - `NN_name.guide.md` — human playbook: purpose, DoR/guardrails, checks, failure modes, best practices.
- **Traceability:** use `traceRef` to link FRs ↔ APIs ↔ Fixtures ↔ NFRs.
- **IDs:** kebab-case, stable. `owner ∈ {api, ui, system, ops, data}`.

### 4) `tools/` (CLI utilities)
- **Entry:** `python -m specdev_tools.cli --help`.
- **Registry:** `tools/schema_registry.json` maps `$schema` URIs → `schema/*.schema.json` paths.
- **Key commands:** `validate`, `validate-all`, `matrix`, `fixtures-lint`, `invariants-check`, `governance-check`, `gen-ci`, `scaffold`, `ai-help`.
- **Toolkit root:** the submodule directory (e.g., `./devspec_toolkit`) containing `tools/`, `schema/`, `prompts/`, `docs/`, and `template/`. Pass `--repo-root` pointing here when running from your host repo.

### 5) `tests/` (data-first checks)
- **fixtures/** data referenced by contracts; **samples/** contexts for invariants; **expectations/** matrices for drift checks.
- **Helper:** `tests/run.sh` runs a minimal suite end-to-end.

### 6) `docs/` (audience-specific guidance)
- `docs/developers/` — onboarding, workflow overviews, diagnostics, changelog.
- `docs/agents/` — machine-readable manifest plus automation contract.
- Start at `docs/developers/index.md` (humans) or `docs/agents/agents.md` (agents).

### 7) `example/` (teaching, not binding)
- Contains the fully specced reference artifacts for this toolkit (see `example/devspec_kit/`).

### 8) `.github/workflows/ci.yml` (pipeline)
- Generated by `gen-ci` then hand-edited as you mature. Enforces schema validation and scaffold checks at minimum.


---

## How to use the toolkit

### 0) Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r ./devspec_toolkit/tools/requirements.txt
export PYTHONPATH="${PWD}/devspec_toolkit/tools"
```

Always pass `--repo-root <toolkit-path>` (for example, `./devspec_toolkit`) when you invoke the CLI from your host repository so the schema registry resolves correctly.

### 1) Author step artifacts

Repeat for each step (`00` → `17`, including `02a` where applicable):

1. **Read** `spec/NN_name.guide.md` to align on purpose and guardrails.
2. **Run** the corresponding prompt in `./devspec_toolkit/prompts/prompt_NN_name.md` and produce a single fenced `json` output.
3. **Paste** the output into `spec/NN_name.json` (which already contains `$schema`).
4. **Validate:**
   ```bash
   python -m specdev_tools.cli validate spec/NN_name.json --repo-root ./devspec_toolkit
   ```
5. **Commit** with a governance-compliant message (Step 10).

### 2) Validate the whole spec set

```bash
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit
```

### 3) Generate scaffold (Steps 05 ↔ 13)

```bash
python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out
node scaffold_out/src/index.js  # optional, to boot the minimal server
```

The scaffold registers routes listed in `13_scaffold.json` and references the request/response schema refs from `05_interface_contracts.json` as TODOs.

### 4) Implement via fixtures (Step 14)

- Implement handlers until:
  - All fixtures in `08_fixtures.json` pass.
  - `14_fixture_impl.json` reports `ci_status = "green"`.
- Use your runtime test runner to feed `tests/fixtures/*` into your handlers and assert the `expected` shapes.

### 5) Red-team loop (Step 15)

- Add adversarial cases to `11_redteam.json` and generate new fixtures.
- Update `15_redteam_loop.json` with `new_fixtures` and any `spec_updates`.
- Re-run `fixtures-lint`, `validate-all`, and your test suite.

### 6) Delivery & monitoring (Step 16)

- Map NFRs → dashboards/alerts in `16_delivery_monitoring.json`.
- Exercise staging; ensure dashboards show SLO signals referenced by `07_nfrs.json`.

### 7) Spec-drift audit (Step 17)

- Schedule drift checks in `17_spec_drift.json`.
- When drift is detected, open remediation PRs as per governance rules.

---

## Monorepo and pathing

- If the toolkit is nested (e.g., `mono/tools/devspec_kit`), the **toolkit root** is that folder.
- Commands from elsewhere must pass `--repo-root <path-to-toolkit>` so `$schema` resolves through `tools/schema_registry.json`.

---

## Upgrading schemas safely

1. Bump schema version (semver) and update `$id`.
2. Update `tools/schema_registry.json` mapping.
3. Run `validate-all`; fix artifacts that violate new constraints.
4. Adjust prompts only if the schema meaning changed.

---

## Common pitfalls

- Missing `$schema` in a spec artifact → validator fails fast.
- Unknown API targeted by a fixture → `fixtures-lint` flags it.
- Non-kebab IDs or wrong `owner` enum → schema validation fails.
- Examples placed inside prompts → reject and move to `example/`.
- Governance pattern mismatch → `governance-check` fails; fix the message.

---

## Example sessions

Create charter and capabilities, then validate:

```bash
python -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit
python -m specdev_tools.cli validate spec/01_capabilities.json --repo-root ./devspec_toolkit
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
```

Scaffold and boot the server for manual smoke:

```bash
python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out
node scaffold_out/src/index.js
```

Generate CI and commit:

```bash
python -m specdev_tools.cli gen-ci spec --repo-root ./devspec_toolkit --toolkit-path ./devspec_toolkit --out .github/workflows/ci.yml
git add . && git commit -m "feat(spec): baseline CI [fr-initial-login]"
```

---

## Step-by-step details (00–17, 02a)

Each step has two files in `spec/`: `NN_name.json` (machine artifact) and `NN_name.guide.md` (human playbook). The JSON must validate against the corresponding schema in `schema/NN_name.schema.json` and use core atoms/collections/errors.

> Abbreviations: DoR = Definition of Ready. Checks = additional automated validations beyond schema shape. Consumers = later steps referencing this artifact.

### 00 · Project Charter
- **Artifact:** `spec/00_charter.json`  • **Schema:** `schema/00_charter.schema.json`
- **Purpose:** define problem, scope, users, success metrics in falsifiable terms.
- **DoR:** concrete problem statement; measurable success metrics; in/out of scope; risks/assumptions; stakeholders; segments.
- **Checks:** no vague language; metrics have units and baselines; IDs are kebab-case.
- **Consumers:** 01, 04, 09, CI readme badges or dashboards.

### 01 · Capabilities
- **Artifact:** `spec/01_capabilities.json`  • **Schema:** `schema/01_capabilities.schema.json`
- **Purpose:** enumerate system verbs, with pre/postconditions and error states.
- **DoR:** each capability has verb, scope, inputs/outputs, owner, traces to FRs (or `fr-*-tbd` anchors).
- **Checks:** `owner ∈ {api, ui, system, ops, data}`; error states shaped via `errorState`.
- **Consumers:** 04 FRs, 05 Contracts, 13 Scaffold.

### 02 · System Sketch
- **Artifact:** `spec/02_system_sketch.json`  • **Schema:** `schema/02_system_sketch.schema.json`
- **Purpose:** components and connections that realize capabilities.
- **DoR:** component responsibilities, types, owners; connections with protocol and refs.
- **Checks:** component IDs referenced by connections exist.
- **Consumers:** 13 Scaffold topology, 09 Plan.

### 02a · Delivery Baseline
- **Artifact:** `spec/02a_delivery_baseline.json`  • **Schema:** `schema/02a_delivery_baseline.schema.json`
- **Purpose:** define environments, CI gates, secrets, compliance constraints.
- **DoR:** objects for `dev`, `ci`, `staging`, `prod`; at least one gate in `ci_gates`.
- **Checks:** gates cross-reference 12 CI jobs by ID.
- **Consumers:** .github workflows, 12 CI Gates.

### 03 · Glossary
- **Artifact:** `spec/03_glossary.json`  • **Schema:** `schema/03_glossary.schema.json`
- **Purpose:** shared terms to kill ambiguity (units, domains).
- **DoR:** term, definition, optional domain/units.
- **Checks:** unique terms; no circular definitions.
- **Consumers:** all narrative fields; 07 NFRs units.

### 04 · Functional Requirements (FRs)
- **Artifact:** `spec/04_fr_list.json`  • **Schema:** `schema/04_fr_list.schema.json`
- **Purpose:** testable behavior with acceptance criteria.
- **DoR:** statement, rationale, pre/postconditions, acceptance criteria; traces to APIs.
- **Checks:** each FR has ≥1 acceptance criterion; trace to 05 or temporary anchors.
- **Consumers:** 05 Contracts, 08 Fixtures, matrix coverage.

### 05 · Interface Contracts
- **Artifact:** `spec/05_interface_contracts.json`  • **Schema:** `schema/05_interface_contracts.schema.json`
- **Purpose:** routes, methods, schema refs, security, examples.
- **DoR:** request/response schema refs, error codes, version, route/method, owner.
- **Checks:** `api_id` unique; example refs exist; error codes are `kebabId`.
- **Consumers:** 13 Scaffold, 08 Fixtures, 14 Impl.

### 06 · Invariants & Rules
- **Artifact:** `spec/06_invariants.json`  • **Schema:** `schema/06_invariants.schema.json`
- **Purpose:** truths that must always hold (jsonlogic or equivalent expression format).
- **DoR:** inv_id, description, expression, scope, severity, traces.
- **Checks:** expressions parse; scope references known components.
- **Consumers:** validators/middleware, 14 Impl, 17 Drift checks.

### 07 · NFRs
- **Artifact:** `spec/07_nfrs.json`  • **Schema:** `schema/07_nfrs.schema.json`
- **Purpose:** performance, reliability, cost targets.
- **DoR:** metric id, target, unit, measurement method, stage.
- **Checks:** units from glossary where applicable; trace links to APIs or components.
- **Consumers:** 16 Delivery & Monitoring, 17 Drift.

### 08 · Test Plan & Fixtures
- **Artifact:** `spec/08_fixtures.json`  • **Schema:** `schema/08_fixtures.schema.json`
- **Purpose:** data-first checks for happy-path and edge-cases.
- **DoR:** fixture id, targets, input, expected, tags.
- **Checks:** targeted APIs exist in 05; expected shapes are concrete.
- **Consumers:** 14 Implementation, CI fixture jobs.

### 09 · Implementation Plan
- **Artifact:** `spec/09_impl_plan.json`  • **Schema:** `schema/09_impl_plan.schema.json`
- **Purpose:** tech stack, milestones, migration.
- **DoR:** stack fields filled; milestones with names and optional target dates/risks.
- **Checks:** milestone ids unique; dependencies tracked.
- **Consumers:** planning boards, CI milestone gates (optional).

### 10 · Governance / Change Control
- **Artifact:** `spec/10_governance.json`  • **Schema:** `schema/10_governance.schema.json`
- **Purpose:** spec-first rules, PR/review policy, commit message pattern.
- **DoR:** versioning policy, PR rules, reviewers, commit pattern.
- **Checks:** `governance-check` validates commit messages.
- **Consumers:** CI pre-merge checks, human process.

### 11 · Red-Team / Failure Modes
- **Artifact:** `spec/11_redteam.json`  • **Schema:** `schema/11_redteam.schema.json`
- **Purpose:** enumerate threats, edge cases, mitigations.
- **DoR:** threat id, description, vector, mitigations, severity.
- **Checks:** severity enum; vectors are concrete; tie to fixtures later.
- **Consumers:** 15 Red-team loop, new fixtures.

### 12 · CI Gates
- **Artifact:** `spec/12_ci_gates.json`  • **Schema:** `schema/12_ci_gates.schema.json`
- **Purpose:** jobs, dependencies, coverage thresholds.
- **DoR:** unique job ids, names, steps, requires chains.
- **Checks:** DAG is acyclic; coverage in [0,100].
- **Consumers:** .github workflows, 02a baseline reference.

### 13 · Scaffold Generation
- **Artifact:** `spec/13_scaffold.json`  • **Schema:** `schema/13_scaffold.schema.json`
- **Purpose:** language/framework skeleton plus route map with TODOs for wiring validation.
- **DoR:** service_skeleton.language set; route_map aligns with 05.
- **Checks:** each route_map.api_ref exists in 05; follow-up work wires validators manually.
- **Consumers:** scaffolder output, build status.

### 14 · Fixture-Driven Implementation
- **Artifact:** `spec/14_fixture_impl.json`  • **Schema:** `schema/14_fixture_impl.schema.json`
- **Purpose:** record which endpoints implemented and fixture pass/fail.
- **DoR:** implemented_endpoints; test_results with status.
- **Checks:** all critical fixtures pass before marking `ci_status = "green"`.
- **Consumers:** release readiness, CI badges.

### 15 · Continuous Red-Team / QA Loop
- **Artifact:** `spec/15_redteam_loop.json`  • **Schema:** `schema/15_redteam_loop.schema.json`
- **Purpose:** add new fixtures and spec updates sourced from red-team findings.
- **DoR:** new_fixtures ids; spec_updates with trace refs and reasons.
- **Checks:** all added fixtures linked to threats/FRs; loop status flips green only when mitigations land.
- **Consumers:** ongoing test growth, spec hardening.

### 16 · Delivery & Monitoring
- **Artifact:** `spec/16_delivery_monitoring.json`  • **Schema:** `schema/16_delivery_monitoring.schema.json`
- **Purpose:** deployments, dashboards, alerts mapped to NFRs.
- **DoR:** deployments have env+build_id; dashboards link NFRs; alerts have rule+severity.
- **Checks:** NFR refs exist; URLs reachable in your environment (out of band).
- **Consumers:** ops runbooks, dashboards, alerts.

### 17 · Spec-Drift Audit
- **Artifact:** `spec/17_spec_drift.json`  • **Schema:** `schema/17_spec_drift.schema.json`
- **Purpose:** scheduled checks for schema/runtime drift with remediation guidance.
- **DoR:** checks with target+method+schedule; severities and remediation text.
- **Checks:** supported methods only; cron expressions valid (enforced by your CI).
- **Consumers:** scheduled job, governance PRs.

---

## Tutorial: AI‑driven speccing and implementation

This is the fastest way to get from blank repo to a running, validated scaffold, using prompts plus CI.

### A. Setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r ./devspec_toolkit/tools/requirements.txt
export PYTHONPATH="${PWD}/devspec_toolkit/tools"
```
Run every CLI command from your host repo root and include `--repo-root ./devspec_toolkit` (or the toolkit path you use) so the schema registry resolves.

### B. Author early steps (00 → 05)
1. Open `./devspec_toolkit/prompts/prompt_00_project_charter.md`. Feed it to your AI as-is. Answer the Clarification Questions block if needed.
2. Paste the single fenced `json` output into `spec/00_charter.json`.  
   Validate:
   ```bash
   python -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit
   ```
3. Repeat for:
   - `./devspec_toolkit/prompts/prompt_01_capabilities.md` → `spec/01_capabilities.json`
   - `./devspec_toolkit/prompts/prompt_02_system_sketch.md` → `spec/02_system_sketch.json`
   - `./devspec_toolkit/prompts/prompt_05_interface_contracts.md` → `spec/05_interface_contracts.json`

Run whole‑tree checks:
```bash
python -m specdev_tools.cli validate-all spec --repo-root ./devspec_toolkit
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
```

### C. Lock traceability via FRs and Fixtures (04, 08)
1. Fill `spec/04_fr_list.json` linking each FR to `05` APIs using `traceRef`.
2. Create initial fixtures in `spec/08_fixtures.json` and put raw request/expectation pairs under `tests/fixtures/`.
3. Lint and cover:
```bash
python -m specdev_tools.cli fixtures-lint spec --repo-root ./devspec_toolkit
python -m specdev_tools.cli matrix spec --repo-root ./devspec_toolkit --out tools/trace_matrix.json
```

### D. Generate scaffold (13) and smoke
```bash
python -m specdev_tools.cli scaffold spec --repo-root ./devspec_toolkit --out scaffold_out
node scaffold_out/src/index.js  # optional: boots minimal server for manual pings
```

### E. Implement to green (14)
- Implement each route to satisfy `tests/fixtures/*` and the expectations embedded in `spec/08_fixtures.json`.
- Update `spec/14_fixture_impl.json` and keep running:
```bash
python -m specdev_tools.cli validate spec/14_fixture_impl.json --repo-root ./devspec_toolkit
```

### F. Add invariants and NFRs (06, 07)
- Encode rules in `spec/06_invariants.json`; verify:
```bash
python -m specdev_tools.cli invariants-check spec --repo-root ./devspec_toolkit --sample ./devspec_toolkit/tests/samples/invariants/password_ok.json
```
- Define NFRs in `spec/07_nfrs.json` and wire dashboards/alerts in `spec/16_delivery_monitoring.json`.

### G. Red-team and harden (11, 15)
- Capture threats in `spec/11_redteam.json`.
- Add new fixtures from findings and record them in `spec/15_redteam_loop.json`.
- Re‑run `fixtures-lint`, `validate-all`, and your runtime tests.

### H. CI & governance (10, 12, 02a, .github)
- Generate or update CI:
```bash
python -m specdev_tools.cli gen-ci spec --repo-root ./devspec_toolkit --toolkit-path ./devspec_toolkit --out .github/workflows/ci.yml
```
- Enforce commit messages against governance:
```bash
python -m specdev_tools.cli governance-check spec --repo-root ./devspec_toolkit --message "feat(spec): add login [fr-initial-login]"
```

### I. Drift audit (17)
- Ensure `spec/17_spec_drift.json` includes scheduled checks.
- Keep `schedule` in CI to run daily:
```yaml
schedule:
  - cron: "0 2 * * *"
```

Result: a running scaffold, green fixtures, dashboards tied to NFRs, and automated drift checks — with spec as the single source of truth.
