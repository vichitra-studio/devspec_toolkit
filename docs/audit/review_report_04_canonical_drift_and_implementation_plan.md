# Audit Report: Cross-Artifact Drift Elimination via Canonical Definitions

Date: 2026-02-21
Reviewed Commit: `bb42fe8`
Repository Root: `/Users/vichitracollective/vc-code/vc_wesbite`
Toolkit Root: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit`

## Evidence Policy
- This report separates:
  - **Verified Current-State Facts**: directly evidenced by repository files/lines and reproducible commands.
  - **Proposed Target Design**: normative architecture and rollout to eliminate drift.
- No undocumented behavior is assumed. All current-state claims are tied to concrete file references.

## 1) Findings First (Prioritized)

### F-001 [P0] Prompt embedded schema `required` lists are stale in 18 prompts
**Impact**: Generation contract diverges from validation contract; model can produce artifacts that pass prompt constraints but fail schema validation.

**Evidence**:
- Example prompt missing `seed_refs` requirement:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md:272`
  - Schema requires it: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/00_charter.schema.json:148`
- Example prompt missing `seed_refs` and `trace`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_09_impl_plan.md:187`
  - Schema requires both: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/09_impl_plan.schema.json:178`
- Example prompt missing `seed_refs` and `commit_message_rules`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md:197`
  - Schema requires both: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/10_governance.schema.json:125`
- Full drift list generated from repository (all with `schema_only` missing from prompt embedded schema):
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md:180`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_01_capabilities.md:190`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_02_system_sketch.md:228`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_02a_delivery_baseline.md:160`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_03_glossary.md:153`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_04_functional_requirements.md:174`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_05_interface_contracts.md:206`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_06_invariants.md:182`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_07_nfrs.md:191`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md:173`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_09_impl_plan.md:174`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md:177`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md:216`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_12_ci_gates.md:174`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_13_extension_generator.md:100`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_13a_completeness_assessment.md:183`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_14_roadmap.md:173`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_15_scaffold.md:141`

**Repro Command**:
```bash
python3 - <<'PY'
import json,re
from pathlib import Path
root=Path('/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit')
for pr in sorted((root/'prompts').glob('prompt_*.md')):
    step=pr.stem.split('_')[1]
    candidates=sorted((root/'schema').glob(f'{step}*.schema.json'), key=lambda p:len(p.name))
    if not candidates: continue
    sc=candidates[0]
    txt=pr.read_text()
    blocks=re.findall(r'```json\n(.*?)\n```', txt, re.S)
    ps=None
    for b in blocks:
        try: j=json.loads(b)
        except: continue
        if isinstance(j,dict) and 'required' in j and 'properties' in j:
            ps=j; break
    if not ps: continue
    real=json.loads(sc.read_text())
    preq=set(ps.get('required',[])); rreq=set(real.get('required',[]))
    if preq!=rreq:
        print(pr)
PY
```

---

### F-002 [P0] `traceRef` type taxonomy is inconsistent across core schema, prompts, and validators
**Impact**: Trace linking can be valid in one subsystem and invalid in another; cross-step integrity checks are non-deterministic.

**Evidence**:
- Core trace types exclude `component` and `invariant`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json:53`
- Step 11 prompt requires `component` in `target_ids`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md:50`
- Step 01 deep validator explicitly checks `trace.type == "component"`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_01.py:17`
- Prompt 08 mixes invariant naming (`inv-*` and `invariant-*`):
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md:83`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md:106`
- Fixtures linter checks `type == "invariant"`, not `inv`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/fixtures_lint.py:53`

---

### F-003 [P0] Step 11 prompt contract and actual Step 11 schema disagree on shape and required fields
**Impact**: High-risk generation failures and red-team artifacts missing required safety metadata.

**Evidence**:
- Prompt embeds top-level `trace` as single object:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md:157`
- Schema requires top-level `trace` array (if present):
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/11_redteam.schema.json:20`
- Prompt threat `required` omits `category`, `target_ids`, `mitigations`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md:232`
- Schema threat `required` includes those fields:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/11_redteam.schema.json:98`
- Prompt output sample still emits object trace:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md:277`

---

### F-003A [P0] Step dependency model is not waterfall: prompts include forward edges and self edges
**Impact**: Future-step dependencies create ambiguous source-of-truth, force speculative inference, and increase hallucination risk.

**Evidence**:
- Prompt dependency scan over `spec/<step>_*.json` references found:
  - `97` total edges
  - `29` forward edges
  - `7` self edges
- Forward-edge examples:
  - `00 -> 07`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md:35`
  - `03 -> 16`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_03_glossary.md:32`
  - `09 -> 12`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_09_impl_plan.md:33`
  - `10 -> 12`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md:37`
- Self-edge examples:
  - `08 -> 08`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md:38`
  - `16 -> 16`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_16_impl_context.md:51`

**Required Policy Change**:
- No forward edges in step prompt input dependencies.
- No self edges in semantic dependencies.
- Any change at step `N` requires replay/regen for `N+1...end`.

---

### F-004 [P1] CI does not enforce all available drift checks; matrix step is non-blocking for integrity
**Impact**: Drift can merge undetected even when tooling exists to detect it.

**Evidence**:
- CI validate job runs only:
  - `validate-all`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/.github/workflows/ci.yml:36`
  - `fixtures-lint`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/.github/workflows/ci.yml:41`
  - `matrix`: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/.github/workflows/ci.yml:43`
- CLI has `seed-lint` and `docs-lint` commands, not wired in CI:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:43`
- `matrix` command only builds output; no failure path from integrity in `cli.py`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:119`
- `validate_trace_integrity()` exists but is not called in `build_trace_matrix()`:
  - definition only: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/matrix.py:81`

---

### F-005 [P1] Deep validation coverage is partial and does not cover all steps
**Impact**: Semantic consistency relies on informal discipline for many artifacts.

**Evidence**:
- Imported deep validators only for steps 01/02/03/04/10/15/16:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py:7`
- Step 03 validator accepts optional NFR/monitoring datasets, but caller passes none:
  - function signature: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_03.py:3`
  - call site: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py:112`

---

### F-006 [P1] Governance command enum drift across schema, prompt, and validator
**Impact**: Authoring guidance and runtime checks disagree; valid artifacts may be rejected and vice versa.

**Evidence**:
- Step 10 schema allows `seed-lint` and `docs-lint`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/10_governance.schema.json:34`
- Step 10 prompt embedded enum omits both:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md:142`
- Step 10 deep validator allowlist omits both:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_10.py:29`

---

### F-007 [P1] Owner taxonomy drift between core schema and docs/prompts
**Impact**: Cross-step ownership semantics are inconsistent; generated artifacts may be unnecessarily constrained.

**Evidence**:
- Core owner enum includes 8 values (`product`, `business`, `engineering` included):
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/atoms.schema.json:38`
- Developer reference still documents 5-value owner enum:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/developers/reference.md:17`
- Prompts enforce 5-value subset:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md:64`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_12_ci_gates.md:81`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_15_scaffold.md:59`

---

### F-008 [P1] Prompt references to non-existent monitoring artifact contract
**Impact**: Upstream context instructions can reference files that are not represented in schema registry.

**Evidence**:
- Prompt 03 references `spec/16_delivery_monitoring.json`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_03_glossary.md:32`
- Prompt 07 references same artifact:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_07_nfrs.md:32`
- Schema registry has only `16_impl_context`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/schema_registry.json:22`

---

### F-009 [P2] Shared concept schemas are duplicated with incompatible shapes
**Impact**: Same semantics (`tech_stack`, `dependencies`, environment/stage) can drift by step.

**Evidence**:
- `tech_stack` required fields differ:
  - Step 09 requires languages/frameworks/infrastructure/tools:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/09_impl_plan.schema.json:113`
  - Step 14 requires only languages/frameworks:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/14_roadmap.schema.json:113`
- `dependencies` type differs:
  - Step 09: string array ref:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/09_impl_plan.schema.json:168`
  - Step 14: structured object array with conditional requirements:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/14_roadmap.schema.json:243`
- Environments/stages duplicated with independent enums:
  - Baseline env object keys `dev|ci|staging|prod`:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/02a_delivery_baseline.schema.json:26`
  - NFR stage enum `dev|staging|prod`:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/07_nfrs.schema.json:67`
  - Impl context deployment env enum `dev|staging|prod`:
    - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/16_impl_context.schema.json:1592`

---

### F-010 [P2] Fixtures lint behavior is over-specialized to HTTP contract fixtures
**Impact**: Non-HTTP fixture modes can fail with false positives (`expected.status` requirement).

**Evidence**:
- Linter enforces HTTP status when `expected` is object:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/fixtures_lint.py:61`
- Prompt supports multiple modes (`unit`, `contract`, `e2e`, `redteam`) where HTTP status may not apply:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md:84`

---

### F-011 [P2] Prompt command examples disagree with CLI argument contract
**Impact**: Generated governance/CI artifacts can encode invalid runnable commands.

**Evidence**:
- Prompt 12 lists invariants command without required `--sample`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_12_ci_gates.md:70`
- CLI requires `--sample`:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:40`

---

### F-012 [P2] Repository-level `spec` path provided in request is absent at root
**Impact**: Tools and plans must be explicit about which `spec` directory is authoritative for this repository state.

**Evidence**:
- `/Users/vichitracollective/vc-code/vc_wesbite/spec` is absent.
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/spec` exists.

---

## 2) Current-State Drift Map (End-to-End)

### 2.1 Prompt Dependency Graph (Declared Upstream References)
```text
00 -> 00,07
01 -> 00,02,03,04
02 -> 01,03,05,07
02a -> 02,07,10
03 -> 00,04,07,16
04 -> 00,01,03,05,07,08
05 -> 02,03,04,07,08
06 -> 04,05,07,10
07 -> 00,03,04,16
08 -> 04,05,06,07,08
09 -> 00,01,02,04,05,07,10,12
10 -> 00,09,12
11 -> 02,04,05,06,07
12 -> 02a,10
13 -> 02,07
13a -> -
14 -> 00,09,12,13,13a
15 -> 01,02,04,05,09
16 -> 09,14,16
16a -> 14
16b -> -
16c -> 09,14
```

### 2.2 Systemic Drift Entry Points
- **Prompt-local embedded schemas** drift from source schemas.
- **Core enum duplication** (`trace type`, `owner`, governance command IDs).
- **Step-local redefinition of shared semantics** (`tech_stack`, `dependencies`, environment/stage labels).
- **CI coverage mismatch** between available validators and enforced gates.

### 2.3 Artifact Lifecycle Where Drift Accumulates
1. Prompt authoring drift (embedded schema copies).
2. Schema updates not propagated to prompt copies.
3. Deep validators updated independently from schemas.
4. CI executes subset checks only.
5. Existing spec artifacts retain legacy terminology without canonical mapping.

### 2.4 Dependency Integrity Quantification
- Dependency scan basis: all prompt references matching `spec/<step>_...` tokens.
- Counts:
  - total edges: `97`
  - backward edges: `61`
  - forward edges: `29`
  - self edges: `7`
- Conclusion:
  - The current prompt graph is not waterfall.
  - Source-of-truth can flow backward from future steps, which is incompatible with no-assumption generation.

### 2.5 Strict Waterfall Target Dependency Graph (Proposed)
```text
00 -> -
01 -> 00
02 -> 00,01
02a -> 00,01,02
03 -> 00,01,02
04 -> 00,01,02,03
05 -> 02,03,04
06 -> 04,05
07 -> 00,02a,03,04,05,06
08 -> 04,05,06,07
09 -> 00,01,02,02a,03,04,05,06,07,08
10 -> 00,02a,09
11 -> 02,04,05,06,07,10
12 -> 02a,08,09,10,11
13 -> 02,03,07,12
13a -> 00..13
14 -> 00..13a
15 -> 01,02,03,04,05,06,07,08,09,10,12,14
16 -> 00..15
16a -> 16
16b -> 16,16a
16c -> 16,16a,16b
```

## 3) Target Architecture: Toolkit-Wide Canonical Definitions System

## 3.1 Design Goals (Normative)
- One canonical semantic definition per shared concept.
- Artifact fields reference canonical IDs, not ad-hoc strings.
- New concepts are isolated as explicit proposals.
- CI fails fast on ambiguity, mismatch, deprecated usage, and unresolved references.
- Backward compatibility during migration with deterministic autofix.
- Step execution is strictly forward-only (waterfall dependency model).
- No refinement mode: upstream changes require full downstream replay.

### 3.2 File/Module Layout
```text
devspec_toolkit/
  canon/
    manifest.json
    aliases.json
    kinds/
      term.json
      acronym.json
      capability.json
      action.json
      entity.json
      role.json
      metric.json
      unit.json
      environment.json
      lifecycle_state.json
      control.json
      policy.json
      id_pattern.json
      tag.json
      event.json
      interface_concept.json
      risk_category.json
      governance_label.json
      command.json
  schema/
    core/
      canon.schema.json
```

### 3.3 Canonical Registry Schema Contract (Required Fields)
Each entry requires:
- `id`: `cn:<namespace>:<kind>:<slug>`
- `kind`
- `preferred_label`
- `definition`
- `version` (`MAJOR.MINOR.PATCH`)
- `status` (`active|deprecated|sunset|retired`)
- `owners[]`
- `introduced_at`

Conditional required fields:
- if `status=deprecated|sunset|retired`, require `deprecated_since`, `replaced_by`.
- if `status=sunset`, require `sunset_after`.

Optional:
- `constraints`, `examples`, `tags`, `aliases`, `source_refs`.

### 3.4 ID and Namespace Convention
- Format: `cn:<namespace>:<kind>:<slug>`
- Namespace classes:
  - `core` (platform-wide)
  - `product.<domain>` (domain-wide)
  - `team.<group>` (team-local)
- Slug normalization: lowercase kebab-case.

### 3.5 Versioning and Deprecation Lifecycle
- **Patch**: typo/metadata changes only.
- **Minor**: additive aliases/metadata/constraints compatible with current semantics.
- **Major**: semantic meaning or compatibility-breaking constraint change.
- Deprecation lifecycle:
  - `active` -> `deprecated` -> `sunset` -> `retired`
- CI behavior:
  - `deprecated`: warning unless policy says strict.
  - `sunset|retired`: error unless explicit temporary waiver.

### 3.6 Step Order and Source-of-Truth Policy (Hard Requirement)
- Authoritative step order:
  - `00,01,02,02a,03,04,05,06,07,08,09,10,11,12,13,13a,14,15,16,16a,16b,16c`
- Dependency rule:
  - Step `N` may depend only on steps `< N` for semantic inputs.
  - Self references allowed only for output-path mentions, not semantic dependencies.
  - Future-step references are prohibited in `Context To Ingest`, validation rules, and examples that influence values.
- Replay rule:
  - Any semantic change in step `N` invalidates steps `N+1...end`.
  - CI must fail if downstream replay artifacts are not updated in the same change set.

## 4) Universal Reference Contract for All Artifacts

### 4.1 Standard Canonical Reference Object
```json
{
  "id": "cn:core:metric:error-rate",
  "kind": "metric",
  "version": "^1.0.0",
  "label": "Error Rate",
  "alias_used": "failure rate"
}
```

### 4.2 Proposal Object for Missing Canonicals
```json
{
  "temp_id": "proposal-metric-failure-rate",
  "kind": "metric",
  "proposed_label": "Failure Rate",
  "definition": "Ratio of failed requests to total requests.",
  "source_field": "nfrs[2].metric",
  "suggested_namespace": "core"
}
```

### 4.3 Top-Level Fields to Add to Every Step Schema (`00..16`)
- `canonical_refs_used`: array of canonical refs actually used in artifact.
- `canonical_proposals`: array of missing canonical proposals.
- `canonical_conflicts`: array of ambiguous references (must be empty to pass CI strict mode).

### 4.4 Required vs Optional Canonical References by Step
- `00_charter`: roles, metrics, units, environments, governance labels.
- `01_capabilities`: capabilities, actions, entities, roles.
- `02_system_sketch`: entities/resources, interface concepts, events, lifecycle states.
- `02a_delivery_baseline`: environments, controls/policies.
- `03_glossary`: terms/acronyms/units become canonical seed definitions.
- `04_fr_list`: capabilities/actions/entities/states.
- `05_interface_contracts`: interface concepts/events/entities/controls.
- `06_invariants`: lifecycle states, controls/policies, risk labels.
- `07_nfrs`: metrics/units/environments required.
- `08_fixtures`: invariant/nfr/fr/api refs via normalized trace + canonical semantic refs.
- `09_impl_plan`: tech stack item refs, dependencies, environment/stage refs.
- `10_governance`: controls/policies/command IDs/id-pattern refs.
- `11_redteam`: risk category refs + mitigation/control refs.
- `12_ci_gates`: command refs, owner role refs, environment refs.
- `13_extension_generator`: tag/id-pattern/policy refs.
- `13a_completeness_assessment`: governance/risk/completeness taxonomy refs.
- `14_roadmap`: capability/dependency/environment/metric refs.
- `15_scaffold`: interface/entity/command refs.
- `16_impl_context`: checklist targets/status labels/controls/risk refs.

### 4.5 Alias and Synonym Policy (No Ambiguity)
- Alias resolution key = `{kind, normalized_text}`.
- Exactly one active target allowed.
- Multiple active targets => hard error (`E140 AMBIGUOUS_ALIAS`).
- Artifacts may carry human-friendly label, but enforcement uses canonical ID.

## 5) Validation Blueprint and CI Enforcement

### 5.1 New/Updated Validation Commands
- `prompt-sync`:
  - verifies embedded prompt schema blocks match source schemas where embedded blocks are retained.
  - or enforces “no embedded schema” policy if that mode is adopted.
- `canonical-lint`:
  - validates canon files against `schema/core/canon.schema.json`.
  - verifies alias uniqueness and lifecycle metadata.
- `canonical-integrity`:
  - validates all artifact `*_ref`/`*_refs` and top-level canonical fields.
  - enforces version range compatibility.
- `trace-normalize-check`:
  - enforces canonical trace type vocabulary.
- `dependency-order-lint`:
  - parses prompt-declared step references and fails on forward/self semantic dependencies.
  - enforces the authoritative step order from `tools/step_order.json`.
- `forward-replay-check`:
  - verifies that any changed step `N` includes replay updates for all downstream steps `N+1...end`.
  - enforces full-cycle forward propagation in PRs.

### 5.2 Failure Classes
- `E1xx`: canonical resolution failures (unknown ID/version mismatch/deprecated blocked).
- `E2xx`: semantic drift (same semantic concept mapped to conflicting canonical IDs).
- `E3xx`: prompt-schema/validator-schema contract drift.
- `E4xx`: registry governance errors (alias collision/deprecation metadata invalid).
- `E5xx`: dependency-order and replay violations (forward edge/self edge/downstream replay missing).
- `W1xx`: migration warnings (legacy fields still present but mapped).

### 5.3 CI Gate Design (Required Jobs)
In `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/.github/workflows/ci.yml` add blocking steps:
1. `prompt-sync`
2. `canonical-lint`
3. `canonical-integrity`
4. `spec-quality-lint`
5. `hallucination-lint`
6. `seed-lint`
7. `docs-lint`
8. `dependency-order-lint`
9. `forward-replay-check`
10. `validate-all`
11. `fixtures-lint`
12. `matrix` (report artifact only)

## 6) Prompt-System Redesign (Exact Changes)

### 6.1 Global Prompt Contract Changes (`prompt_00` .. `prompt_16c`)
- Remove “Embedded Schema below” as source-of-truth requirement.
- Replace with required rule:
  - “Output MUST validate against schema file in `devspec_toolkit/schema` mapped by `tools/schema_registry.json`.”
- Add mandatory section in each prompt:
  - `Canonical Reuse Rules`.
  - deterministic behavior for missing/ambiguous canonicals.

### 6.2 Generation-Time Behavior (Deterministic)
- If canonical match count is **1**: bind automatically.
- If canonical match count is **0**: emit proposal in `canonical_proposals`.
- If canonical match count is **>1**: stop output and emit conflict in `canonical_conflicts`.

### 6.3 Immediate Prompt Fixes Required (Current Bugs)
- Step 11:
  - align `trace` to array, include `seed_refs`, and align threat `required` fields.
- Step 12:
  - fix `invariants-check` command sample to include `--sample`.
- Step 03 and Step 07:
  - replace stale monitoring reference `16_delivery_monitoring` with `16_impl_context` (or define a new schema + registry entry if monitoring artifact is intentional).
- Step 10/12/15:
  - align owner guidance with core owner enum in `atoms.schema.json`.

### 6.3A Prompt Dependency Hardening (Waterfall Rule)
- For every prompt, `Context To Ingest` must reference only prior steps.
- Remove all forward references (e.g., `00->07`, `03->16`, `09->12`, `10->12`).
- Remove self semantic dependencies (e.g., `08->08`) unless reference is output path/validation command only.
- Add explicit clause:
  - “Do not use future-step artifacts as input. If additional detail is needed, emit blocker report instead of inferring values.”

### 6.4 Prompt Hardening Profile (Comprehensive, Correct, Zero-Assumption Mode)
- Add a mandatory **fail-closed preflight** section to every prompt:
  - verify all required seed artifacts are present and fresh before generation.
  - if any required input is missing, stale, or contradictory, stop and emit a structured blocker report instead of generating speculative spec fields.
- Add mandatory **Evidence Ledger** behavior:
  - every non-trivial claim must map to a source in `seed_refs` and/or canonical registry.
  - no value may be introduced without one of:
    - existing upstream ID reference, or
    - canonical registry reference, or
    - explicit `canonical_proposals` entry.
- Add mandatory **No-Invention Rules**:
  - do not invent IDs, enum values, metrics, units, stages, controls, or command names.
  - disallow placeholders (`TBD`, `TODO`, `FIXME`, `???`, `lorem`) in final artifacts.
- Add mandatory **Completeness Closure Pass**:
  - before emitting JSON, prompt must self-check required sections and cross-links (for the current step schema plus required upstream dependencies).
  - if closure fails, return blocker report; do not emit partial artifact.
- Add mandatory **One-Go Emission Constraints**:
  - exactly one artifact output, schema-valid, with no unresolved assumptions.
  - unresolved items must be zero in strict mode.

### 6.5 Schema Changes Required for Prompt Hardening
- Add a reusable `generation_quality` anchor in `schema/core/collections.schema.json`:
  - `preflight_passed` (boolean),
  - `evidence_records[]` (field path -> source),
  - `unresolved_inputs[]`,
  - `assumptions[]`,
  - `placeholder_scan` (object),
  - `self_check_results[]` (named checks + pass/fail).
- Add `generation_quality` to each step schema (`00..16`) with phase-specific constraints:
  - migration phase: optional (warn on violations),
  - strict phase: required and must satisfy:
    - `preflight_passed = true`
    - `assumptions` length = `0`
    - `unresolved_inputs` length = `0`
    - `placeholder_scan.has_placeholders = false`
- Add schema-level `pattern` guards in user-facing free text fields where feasible to block common placeholder tokens.

## 7) Migration Plan (Phased, Low Disruption)

### Phase 0: Contract Stabilization (No Schema Shape Changes Yet)
- Fix prompt/schema drifts.
- Normalize trace vocabulary.
- Remove forward/self step dependencies from prompts.
- Add CI checks for prompt/schema drift and missing checks (`seed-lint`, `docs-lint`, dependency-order checks).

### Phase 1: Canonical Registry Introduction (Non-blocking)
- Add canonical schema and registry files.
- Add canonical validators in warning mode.
- Seed registry from existing glossary/enums.

### Phase 2: Dual-Write (`legacy + canonical_ref`) in all step schemas
- Add canonical fields across `00..16`.
- Preserve current legacy fields.
- Add autofix tool to backfill refs from existing artifacts.
- Add full-cycle replay checker so upstream edits require downstream updates.

### Phase 3: Strict Enforcement
- Block unresolved proposals/conflicts in CI.
- Enforce deprecation policy.
- Disallow new legacy-only fields for shared semantic classes.
- Block forward/self prompt dependencies and missing downstream replay in CI.

### Phase 4: Legacy Field Retirement
- Remove deprecated legacy semantic fields after migration window.
- Keep strict forward-only dependency policy permanently (no refinement mode).

## 8) Atomic Implementation Plan (Execution-Ready)

Notes:
- All tasks are intentionally small and independently verifiable.
- `Depends On` means hard prerequisite.
- All commands assume cwd: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit`.
- Execution contract: in host repos, run commands via `./tools/run_specdev.sh ... --repo-root ./devspec_toolkit`; treat `python -m specdev_tools.cli` as logical command identity only.

### 8.1 Workstream A: Stabilize Existing Contracts

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| A-001 | `tools/specdev_tools/prompt_schema_sync.py` (new) | Add prompt-vs-schema required-field drift checker | `python -m specdev_tools.prompt_schema_sync --repo-root .` | exits 0 when no drift; non-zero with file:line otherwise | none |
| A-002 | `tools/specdev_tools/cli.py` | Add `prompt-sync` subcommand wiring | `python -m specdev_tools.cli prompt-sync spec --repo-root .` | command available and returns status codes correctly | A-001 |
| A-003 | `.github/workflows/ci.yml` | Add blocking step to run `prompt-sync` | run CI | CI fails on prompt/schema drift | A-002 |
| A-004 | `prompts/prompt_00_*.md` through `prompts/prompt_15_*.md` | Fix embedded `required` lists to include schema-required fields (`seed_refs`, etc.) | `python -m specdev_tools.cli prompt-sync spec --repo-root .` | zero drift findings | A-001 |
| A-005 | `prompts/prompt_11_redteam.md` | Fix `trace` shape (array), threat required list, include `seed_refs`, align output sample | `python -m specdev_tools.cli prompt-sync spec --repo-root .` | prompt contract matches schema; output-contract sample validates via prompt-sync tests | A-004 |
| A-006 | `prompts/prompt_03_glossary.md`, `prompts/prompt_07_nfrs.md` | Replace stale `16_delivery_monitoring` reference with `16_impl_context` (or add schema/registry if separate artifact intended) | `rg -n "16_delivery_monitoring" prompts` | no stale references remain | none |
| A-007 | `prompts/prompt_12_ci_gates.md` | Fix invariants command sample to include `--sample` | `rg -n "invariants-check" prompts/prompt_12_ci_gates.md` | example command matches CLI contract | none |
| A-008 | `docs/developers/reference.md` | Update owner enum doc to match core atoms enum | `rg -n "Owner enum" docs/developers/reference.md` | doc equals schema enum | none |
| A-009 | `prompts/prompt_10_governance.md`, `prompts/prompt_12_ci_gates.md`, `prompts/prompt_15_scaffold.md` | Update owner guidance to full schema enum set | `rg -n "Set owner to one of" prompts/prompt_10_governance.md prompts/prompt_12_ci_gates.md prompts/prompt_15_scaffold.md` | guidance matches core schema | A-008 |
| A-010 | `tools/specdev_tools/validators/step_10.py` | Include `seed-lint` and `docs-lint` in governance `pr_rules` allowlist | `python -m specdev_tools.cli validate spec/10_governance.json --repo-root .` | no false invalidation for schema-valid rules | none |
| A-011 | `.github/workflows/ci.yml` | Add blocking `seed-lint` and `docs-lint` steps | run CI | pipeline enforces both checks | none |
| A-012 | `tools/specdev_tools/fixtures_lint.py` | Make HTTP `expected.status` enforcement conditional to `mode == contract` | `python -m specdev_tools.cli fixtures-lint spec` | non-contract fixtures do not require HTTP status | none |

### 8.2 Workstream B: Canonical Registry Foundation

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| B-001 | `schema/core/canon.schema.json` (new) | Add canonical registry schema with required lifecycle fields | `python -m specdev_tools.cli validate canon/manifest.json --repo-root .` (after wiring) | schema validates canonical registry | none |
| B-002 | `tools/schema_registry.json` | Register `https://specdev.local/schema/core/canon/1` URI | `python -m specdev_tools.cli validate canon/manifest.json --repo-root .` | registry resolves canon schema URI | B-001 |
| B-003 | `canon/manifest.json` (new) | Create canonical registry manifest file | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | lint passes | B-001 |
| B-004 | `canon/aliases.json` (new) | Create alias registry with uniqueness constraints | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | no duplicate active alias keys | B-003 |
| B-005 | `canon/kinds/*.json` (new set) | Create modular kind files (term, metric, unit, environment, risk_category, command, etc.) | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | all kind files validate and merge | B-003 |
| B-006 | `tools/specdev_tools/canonical_registry.py` (new) | Add loader and resolver (ID lookup, alias lookup, version checks) | `python -m unittest discover -s tests -p "test_canonical_registry*.py"` | resolver unit tests pass | B-001 |
| B-007 | `tools/specdev_tools/canonical_lint.py` (new) | Add lint rules for lifecycle/deprecation/alias collisions | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | lint returns deterministic error classes | B-006 |
| B-008 | `tools/specdev_tools/cli.py` | Add `canonical-lint` subcommand | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | command exposed and functional | B-007 |
| B-009 | `tests/...` (new) | Add fixtures for alias conflict, deprecated metadata, version mismatch | `python -m unittest discover -s tests` | tests fail/pass deterministically by fixture | B-007 |
| B-010 | `canon/kinds/*.json` | Seed initial canonical entries from existing glossary/enums | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | initial registry passes lint | B-005 |

### 8.3 Workstream C: Core Contract Normalization

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| C-001 | `schema/core/collections.schema.json` | Add canonical trace enum set and transitional alias support (`inv` + `invariant`, `component`) | `python -m specdev_tools.cli validate-all spec --repo-root .` | all existing artifacts still validate | B-001 |
| C-002 | `tools/specdev_tools/trace_types.py` (new) | Centralize allowed trace types as single source for validators | `python -m unittest discover -s tests -p "test_trace_types*.py"` | validators import shared list | C-001 |
| C-003 | `tools/specdev_tools/validators/step_01.py` | Use shared trace type constants and normalized matching | `python -m specdev_tools.cli validate spec/01_capabilities.json --repo-root .` | component trace checks remain correct | C-002 |
| C-004 | `tools/specdev_tools/fixtures_lint.py` | Normalize `inv`/`invariant` for fixtures target checks | `python -m specdev_tools.cli fixtures-lint spec` | both forms handled consistently | C-002 |
| C-005 | `prompts/prompt_08_fixtures.md` | Make invariant trace token usage consistent with core trace taxonomy | `rg -n "inv-|invariant-" prompts/prompt_08_fixtures.md` | single canonical guidance retained | C-001 |
| C-006 | `prompts/prompt_11_redteam.md` | Make `target_ids.type` aligned with normalized trace taxonomy | `python -m specdev_tools.cli prompt-sync spec --repo-root .` | prompt/schema/validator alignment achieved | C-001 |

### 8.4 Workstream D: Add Canonical Reference Support to Schemas (`00..16`)

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| D-001 | `schema/core/collections.schema.json` | Add `$anchor` definitions: `canonicalRef`, `canonicalRefArray`, `canonicalProposal`, `canonicalConflict` | `python -m specdev_tools.cli validate-all spec --repo-root .` | core schema compiles and existing specs unaffected | B-001 |
| D-002 | `schema/00_charter.schema.json` | Add top-level canonical fields + refs for `stakeholders`, `success_metrics` units | `python -m specdev_tools.cli validate spec/00_charter.json --repo-root .` | step validates with canonical fields optional (phase 2) | D-001 |
| D-003 | `schema/01_capabilities.schema.json` | Add canonical refs for capabilities/actions/actors/entities | `python -m specdev_tools.cli validate spec/01_capabilities.json --repo-root .` | step validates with dual-write support | D-001 |
| D-004 | `schema/02_system_sketch.schema.json` | Add canonical refs for components/entities/events/interfaces | `python -m specdev_tools.cli validate spec/02_system_sketch.json --repo-root .` | step validates | D-001 |
| D-005 | `schema/02a_delivery_baseline.schema.json` | Add canonical refs for environments/controls | `python -m specdev_tools.cli validate spec/02a_delivery_baseline.json --repo-root .` | step validates | D-001 |
| D-006 | `schema/03_glossary.schema.json` | Add canonical binding fields for terms/acronyms/units | `python -m specdev_tools.cli validate spec/03_glossary.json --repo-root .` | step validates | D-001 |
| D-007 | `schema/04_fr_list.schema.json` | Add canonical refs for capabilities/actions/entities/states | `python -m specdev_tools.cli validate spec/04_fr_list.json --repo-root .` | step validates | D-001 |
| D-008 | `schema/05_interface_contracts.schema.json` | Add canonical refs for event/interface/entity/control vocabulary | `python -m specdev_tools.cli validate spec/05_interface_contracts.json --repo-root .` | step validates | D-001 |
| D-009 | `schema/06_invariants.schema.json` | Add canonical refs for control/policy/risk/lifecycle state | `python -m specdev_tools.cli validate spec/06_invariants.json --repo-root .` | step validates | D-001 |
| D-010 | `schema/07_nfrs.schema.json` | Add required canonical refs for metric/unit/environment | `python -m specdev_tools.cli validate spec/07_nfrs.json --repo-root .` | step validates with dual-write | D-001 |
| D-011 | `schema/08_fixtures.schema.json` | Add canonical refs where fixture semantics require shared labels | `python -m specdev_tools.cli validate spec/08_fixtures.json --repo-root .` | step validates | D-001 |
| D-012 | `schema/09_impl_plan.schema.json` | Add canonical refs for tech stack/dependencies/environments | `python -m specdev_tools.cli validate spec/09_impl_plan.json --repo-root .` | step validates | D-001 |
| D-013 | `schema/10_governance.schema.json` | Add canonical refs for commands/policies/id-patterns | `python -m specdev_tools.cli validate spec/10_governance.json --repo-root .` | step validates | D-001 |
| D-014 | `schema/11_redteam.schema.json` | Add canonical refs for risk categories and mitigation controls | `python -m specdev_tools.cli validate-all spec --repo-root .` | schema compiles and existing spec set validates | D-001 |
| D-015 | `schema/12_ci_gates.schema.json` | Add canonical refs for commands/owners/environments | `python -m specdev_tools.cli validate spec/12_ci_gates.json --repo-root .` | step validates | D-001 |
| D-016 | `schema/13_extension_generator.schema.json` | Add canonical refs for tags/id patterns/governance labels | `python -m specdev_tools.cli validate spec/13_extension_generator.json --repo-root .` | step validates | D-001 |
| D-017 | `schema/13a_completeness_assessment.schema.json` | Add canonical refs for completeness dimensions/risk labels | `python -m specdev_tools.cli validate spec/13a_completeness_assessment.json --repo-root .` | step validates | D-001 |
| D-018 | `schema/14_roadmap.schema.json` | Add canonical refs for dependencies/tech stack/env/metrics | `python -m specdev_tools.cli validate spec/14_roadmap.json --repo-root .` | step validates | D-001 |
| D-019 | `schema/15_scaffold.schema.json` | Add canonical refs for route semantics and validator command IDs | `python -m specdev_tools.cli validate spec/15_scaffold.json --repo-root .` | step validates | D-001 |
| D-020 | `schema/16_impl_context.schema.json` | Add canonical refs for checklist targets/status/control/risk concepts | `python -m specdev_tools.cli validate spec/16_impl_context.json --repo-root .` | step validates | D-001 |
| D-021 | `schema/core/collections.schema.json` | Add shared anchors for reused structures (`techStack`, `dependencyList`, `environmentName`, `stageName`) to remove cross-step shape drift | `python -m specdev_tools.cli validate-all spec --repo-root .` | shared schema atoms available for all step schemas | B-001 |
| D-022 | `schema/02a_delivery_baseline.schema.json`, `schema/07_nfrs.schema.json`, `schema/09_impl_plan.schema.json`, `schema/14_roadmap.schema.json`, `schema/16_impl_context.schema.json` | Refactor duplicated environment/stage/tech-stack/dependency structures to reuse shared anchors with compatibility guards | `python -m specdev_tools.cli validate-all spec --repo-root .` | shared concepts reuse core anchors; no behavior regression | D-021 |

### 8.5 Workstream E: Validator and Integrity Enforcement

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| E-001 | `tools/specdev_tools/canonical_integrity.py` (new) | Resolve and validate all canonical refs in all artifacts | `python -m specdev_tools.cli canonical-integrity spec --repo-root .` | unknown IDs/version mismatches produce E1xx | none |
| E-002 | `tools/specdev_tools/cli.py` | Add `canonical-integrity` command | `python -m specdev_tools.cli canonical-integrity spec --repo-root .` | command returns non-zero on E* | E-001 |
| E-003 | `tools/specdev_tools/validate.py` | Invoke canonical integrity in `validate-all` (toggle strict/warn modes) | `python -m specdev_tools.cli validate-all spec --repo-root .` | includes canonical checks | E-002 |
| E-004 | `tools/specdev_tools/matrix.py` | Integrate `validate_trace_integrity` invocation and report errors | `python -m specdev_tools.cli matrix spec --out tools/trace_matrix.json` | integrity errors reflected in output + non-zero in strict mode | C-006 |
| E-005 | `tools/specdev_tools/validators/step_03.py` | Extend step 03 deep checks to consume optional NFR/monitoring datasets when provided by validator pipeline | `python -m specdev_tools.cli validate-all spec --repo-root .` | step 03 deep checks ready for dataset wiring | none |
| E-006 | `tools/specdev_tools/errors.py` (new or existing) | Standardize E/W error code taxonomy and formatting | run unit tests | all checks emit machine-parseable codes | none |
| E-007 | `tests/fixtures/...` | Add positive/negative fixtures for each error class | `python -m unittest discover -s tests` | coverage for E1xx..E5xx + W1xx | E-006 |
| E-008 | `.github/workflows/ci.yml` | Add blocking `canonical-lint` + `canonical-integrity` + strict `validate-all` | run CI | drift blocks PR merges | E-003 |
| E-009 | `tools/specdev_tools/validators/step_05.py`, `tools/specdev_tools/validators/step_06.py`, `tools/specdev_tools/validators/step_07.py`, `tools/specdev_tools/validators/step_08.py`, `tools/specdev_tools/validators/step_09.py`, `tools/specdev_tools/validators/step_11.py`, `tools/specdev_tools/validators/step_12.py`, `tools/specdev_tools/validators/step_13.py`, `tools/specdev_tools/validators/step_13a.py`, `tools/specdev_tools/validators/step_14.py`, `tests/*` | Add missing deep validators for uncovered steps and unit tests | `python -m unittest discover -s tests -p \"test_step_*.py\"` | deep-validation coverage exists for all schema steps | none |
| E-010 | `tools/specdev_tools/validate.py` | Wire all step deep validators via centralized dispatch table and dataset loader hooks | `python -m specdev_tools.cli validate-all spec --repo-root .` | no step bypasses deep validation pipeline | E-009 |

### 8.6 Workstream F: Prompt Redesign for Canonical Reuse

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| F-001 | `docs/prompts/shared_expectations.md` | Add canonical resolution protocol and conflict behavior | `rg -n "Canonical Reuse Rules|canonical_proposals|canonical_conflicts" docs/prompts/shared_expectations.md` | shared prompt contract updated | B-010 |
| F-002 | `prompts/prompt_00_*.md` ... `prompt_16c_*.md` | Add canonical behavior block to each prompt | `rg -n "canonical_proposals|canonical_conflicts" prompts` | all prompts contain canonical policy | F-001 |
| F-003 | `prompts/prompt_00_*.md` ... `prompt_16_*.md` | Update output contracts to include top-level canonical fields | `python -m specdev_tools.cli prompt-sync spec --repo-root .` | prompt output contracts align with schema fields | D-020 |
| F-004 | `prompts/prompt_16a_impl_planner.md`, `prompt_16b_impl_coder.md`, `prompt_16c_impl_reviewer.md` | Enforce carry-forward of canonical bindings from step 16 | grep + test fixtures | trinity loop preserves canonical IDs | F-003 |

### 8.7 Workstream G: Migration and Backfill

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| G-001 | `tools/specdev_tools/canonical_autofix.py` (new) | Add autofix to infer refs from current fields + aliases | `python -m specdev_tools.cli canonical-autofix spec --repo-root . --write` | artifacts backfilled deterministically | none |
| G-002 | `tools/specdev_tools/cli.py` | Add `canonical-autofix` command | `python -m specdev_tools.cli canonical-autofix spec --repo-root . --dry-run` | dry-run and write modes work | G-001 |
| G-003 | `spec/**/*.json` | Backfill canonical refs across existing spec artifacts | `python -m specdev_tools.cli canonical-integrity spec --repo-root .` | no unknown canonical refs | G-001 |
| G-004 | `spec/**/*.json` | Add unresolved entries to `canonical_proposals` where mapping confidence < threshold | `python -m specdev_tools.cli canonical-integrity spec --repo-root .` | no silent unresolved terms | G-003 |
| G-005 | `canon/kinds/*.json` | Approve and merge proposals into registry | `python -m specdev_tools.cli canonical-lint canon --repo-root .` | proposals converted into canonical IDs | G-004 |
| G-006 | `.github/workflows/ci.yml` | Enable strict mode to fail on unresolved proposals/conflicts | run CI | unresolved canonical conflicts block merge | G-005 |

### 8.8 Workstream H: Prompt Hardening, Tooling, and Docs (One-Go Quality)

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| H-001 | `schema/core/collections.schema.json` | Add `generation_quality` anchor and evidence/self-check sub-anchors | `python -m specdev_tools.cli validate-all spec --repo-root .` | core schema supports quality metadata | D-001 |
| H-002 | `schema/00_*.schema.json` ... `schema/16_*.schema.json` | Add `generation_quality` field to all step schemas with migration-safe constraints | `python -m specdev_tools.cli validate-all spec --repo-root .` | all steps accept and validate quality block | H-001 |
| H-003 | `tools/specdev_tools/spec_quality_lint.py` (new) | Implement completeness checks (required coverage, cross-link closure, no placeholders, no empty critical arrays) | `python -m specdev_tools.cli spec-quality-lint spec --repo-root .` | deterministic quality errors with line/context paths | H-001 |
| H-004 | `tools/specdev_tools/hallucination_lint.py` (new) | Implement no-invention checks (unknown IDs/enums/commands/units/stages vs schema+canon) | `python -m specdev_tools.cli hallucination-lint spec --repo-root .` | unknown semantic values fail with E/H codes | H-001 |
| H-005 | `tools/specdev_tools/cli.py` | Add `spec-quality-lint` and `hallucination-lint` subcommands | `python -m specdev_tools.cli --help` | commands available and executable | H-003 |
| H-006 | `tools/specdev_tools/errors.py` | Add error classes/codes for hardening (`E510` placeholder, `E520` unresolved input, `E530` invented enum/id) | unit tests | hardening checks emit stable machine-parseable codes | none |
| H-007 | `.github/workflows/ci.yml` | Add blocking CI steps for `spec-quality-lint` and `hallucination-lint` | run CI | quality/hallucination failures block merges | H-005 |
| H-008 | `docs/prompts/shared_expectations.md` | Add strict “one-go quality protocol” (preflight, evidence ledger, closure pass, fail-closed blockers) | `rg -n \"one-go|fail-closed|Evidence Ledger|Completeness Closure\" docs/prompts/shared_expectations.md` | global prompt behavior updated | F-001 |
| H-009 | `prompts/prompt_00_*.md` ... `prompts/prompt_16c_*.md` | Add hardening blocks and blocker-report behavior to every prompt | `rg -n \"fail-closed preflight|blocker report|No-Invention Rules|Completeness Closure\" prompts` | all prompts hardened consistently | H-008 |
| H-010 | `docs/developers/reference.md`, `docs/README.md`, `tools/README.md` | Document new quality/hallucination commands and strict-mode workflow | `rg -n \"spec-quality-lint|hallucination-lint|strict mode\" docs/README.md docs/developers/reference.md tools/README.md` | docs and tooling references fully aligned | H-005 |

### 8.9 Workstream I: Step-Order Integrity and Full Forward Replay (No Refinement Mode)

| Task ID | Files | Exact Change | Verify Command | Done When | Depends On |
|---|---|---|---|---|---|
| I-001 | `tools/step_order.json` (new) | Add authoritative step order and allowed upstream dependencies map | `cat tools/step_order.json` | file exists and defines full order `00..16c` | none |
| I-002 | `tools/specdev_tools/dependency_order_lint.py` (new) | Implement lint that parses prompt references and fails on forward/self semantic dependencies | `python -m specdev_tools.cli dependency-order-lint --repo-root .` | linter reports violations with file:line and edge class | I-001 |
| I-003 | `tools/specdev_tools/forward_replay_check.py` (new) | Implement check that detects changed step `N` and requires downstream updates `N+1...end` | `python -m specdev_tools.cli forward-replay-check --repo-root . --base-ref origin/main` | check fails when downstream replay is missing | I-001 |
| I-004 | `tools/specdev_tools/cli.py` | Add `dependency-order-lint` and `forward-replay-check` commands | `python -m specdev_tools.cli --help` | commands available and callable | I-002 |
| I-005 | `tests/fixtures/...`, `tests/*` | Add forward-edge/self-edge and replay-missing fixtures for dependency checks | `python -m unittest discover -s tests` | dependency validators have deterministic tests | I-003 |
| I-006 | `prompts/prompt_00_*.md` ... `prompts/prompt_16c_*.md` | Rewrite prompt dependency inputs to strict upstream-only map; remove forward/self semantic references | `python -m specdev_tools.cli dependency-order-lint --repo-root .` | zero forward/self violations | I-002 |
| I-007 | `docs/prompts/shared_expectations.md`, `docs/developers/reference.md` | Document strict waterfall/no-refinement/full-replay policy | `rg -n \"forward-only|no refinement|full replay\" docs/prompts/shared_expectations.md docs/developers/reference.md` | policy documented in agent + developer docs | none |
| I-008 | `.github/workflows/ci.yml` | Add blocking `dependency-order-lint` and `forward-replay-check` gates | run CI | PRs fail on forward-edge or replay violations | I-004 |
| I-009 | `docs/audit/batch_B0_baseline.md`, `docs/developers/reference.md` | Persist and document spec scope lock protocol (`spec_dir` must be explicit per repo) to prevent path assumptions in automation | `rg -n \"spec_dir|scope lock|devspec_toolkit/spec\" docs/audit/batch_B0_baseline.md docs/developers/reference.md` | repo-specific spec path assumptions are eliminated | none |

## 9) Governance and Operating Model

### 9.1 Ownership
- `canon/core` entries: Platform governance owner.
- Domain namespaces: Domain owners.
- Security/risk kinds: Security owner.
- Command/policy kinds: DevEx/Governance owner.

### 9.2 Change Control
- Every canonical change PR must include:
  - impacted artifacts list,
  - version bump rationale,
  - deprecation impact.

### 9.3 Deprecation Windows
- Minimum two release windows from `deprecated` to `sunset`.
- `retired` entries blocked in strict mode except explicit temporary waiver list.

## 10) Example Artifacts (Ready to Implement)

### 10.1 Draft Canonical Schema Snippet
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://specdev.local/schema/core/canon/1",
  "type": "object",
  "properties": {
    "registry_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "entries": { "type": "array", "items": { "$ref": "#/$defs/entry" } },
    "aliases": { "type": "array", "items": { "$ref": "#/$defs/alias" } }
  },
  "required": ["registry_version", "entries", "aliases"],
  "$defs": {
    "entry": {
      "type": "object",
      "required": ["id", "kind", "preferred_label", "definition", "version", "status", "owners", "introduced_at"],
      "properties": {
        "id": { "type": "string", "pattern": "^cn:[a-z0-9.]+:[a-z_]+:[a-z0-9-]+$" },
        "kind": { "type": "string" },
        "preferred_label": { "type": "string" },
        "definition": { "type": "string" },
        "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
        "status": { "type": "string", "enum": ["active", "deprecated", "sunset", "retired"] },
        "owners": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
        "introduced_at": { "type": "string", "format": "date-time" },
        "deprecated_since": { "type": "string", "format": "date-time" },
        "sunset_after": { "type": "string", "format": "date-time" },
        "replaced_by": { "type": "string" }
      }
    },
    "alias": {
      "type": "object",
      "required": ["kind", "normalized", "target_id", "status"],
      "properties": {
        "kind": { "type": "string" },
        "normalized": { "type": "string" },
        "target_id": { "type": "string" },
        "status": { "type": "string", "enum": ["active", "deprecated"] }
      }
    }
  }
}
```

### 10.2 Sample Canonical Entries
```json
{
  "registry_version": "1.0.0",
  "entries": [
    {
      "id": "cn:core:metric:error-rate",
      "kind": "metric",
      "preferred_label": "Error Rate",
      "definition": "Ratio of failed requests to total requests over an interval.",
      "version": "1.0.0",
      "status": "active",
      "owners": ["sre"],
      "introduced_at": "2026-02-21T00:00:00Z"
    },
    {
      "id": "cn:core:unit:percent",
      "kind": "unit",
      "preferred_label": "Percent",
      "definition": "A ratio expressed from 0 to 100.",
      "version": "1.0.0",
      "status": "active",
      "owners": ["sre"],
      "introduced_at": "2026-02-21T00:00:00Z"
    },
    {
      "id": "cn:core:environment:staging",
      "kind": "environment",
      "preferred_label": "Staging",
      "definition": "Pre-production integration environment.",
      "version": "1.0.0",
      "status": "active",
      "owners": ["platform"],
      "introduced_at": "2026-02-21T00:00:00Z"
    }
  ],
  "aliases": [
    {
      "kind": "metric",
      "normalized": "failure rate",
      "target_id": "cn:core:metric:error-rate",
      "status": "active"
    }
  ]
}
```

### 10.3 Sample Step Artifact Using Canonical Refs
```json
{
  "nfr_id": "nfr-api-error-rate",
  "metric": "error-rate",
  "metric_ref": {
    "id": "cn:core:metric:error-rate",
    "kind": "metric",
    "version": "^1.0.0"
  },
  "unit": "%",
  "unit_ref": {
    "id": "cn:core:unit:percent",
    "kind": "unit"
  },
  "stage": "staging",
  "stage_ref": {
    "id": "cn:core:environment:staging",
    "kind": "environment"
  },
  "target": "<=1.0"
}
```

### 10.4 Sample Validator Error Output
```text
E110 UNKNOWN_CANONICAL_ID spec/07_nfrs.json:nfrs[2].metric_ref.id=cn:core:metric:err-rate
E120 CANONICAL_KIND_MISMATCH spec/07_nfrs.json:nfrs[2].unit_ref.kind=metric expected=unit
E140 AMBIGUOUS_ALIAS spec/03_glossary.json:term='latency' candidates=[cn:core:metric:p95-latency, cn:core:metric:p99-latency]
E210 CROSS_ARTIFACT_DRIFT spec/14_roadmap.json:dependency 'auth service' conflicts with spec/09_impl_plan.json mapping
E310 PROMPT_SCHEMA_DRIFT prompts/prompt_10_governance.md:missing required ['seed_refs','commit_message_rules']
```

## 11) Reproducibility Commands (Used for This Review)
```bash
# list prompts/schemas
rg --files /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts | sort
rg --files /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema | sort

# prompt required-field drift detection
python3 <script from F-001>

# trace taxonomy evidence
rg -n "traceRef|component|invariant|inv" /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_01.py /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/fixtures_lint.py

# CI coverage evidence
rg -n "prompt-sync|canonical-lint|canonical-integrity|spec-quality-lint|hallucination-lint|dependency-order-lint|forward-replay-check|validate-all|fixtures-lint|matrix|seed-lint|docs-lint" /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/.github/workflows/ci.yml /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py
```

---

## 12) No-Rework Execution Sequence (Dependency-Resolved, Minimal Agent Calls)

This sequence is optimized to:
- avoid touching the same file class multiple times,
- satisfy hard dependencies before downstream tasks,
- keep CI churn low until all required commands exist,
- minimize total agent calls by bundling related edits.

### 12.1 Batch Order (Execute Exactly in This Order)

| Batch | Purpose | Include Tasks | Primary Files Touched Once | Exit Criteria |
|---|---|---|---|---|
| B0 | Baseline lock + scope confirmation | (pre-task) confirm canonical `spec_dir`, capture baseline failures | none | baseline command log captured; active `spec_dir` fixed |
| B1 | Core contract foundations (single pass) | `B-001`, `B-002`, `C-001`, `D-001`, `D-021`, `H-001`, `E-006`, `H-006`, `I-001` | `schema/core/collections.schema.json`, `schema/core/canon.schema.json`, `tools/schema_registry.json`, `tools/specdev_tools/errors.py`, `tools/step_order.json` | core schemas validate; registry resolves; error taxonomy + step order present |
| B2 | Lint/validator module implementation (no CLI wiring yet) | `A-001`, `A-010`, `A-012`, `C-002`, `C-003`, `C-004`, `E-001`, `E-005`, `E-007`, `E-009`, `H-003`, `H-004`, `G-001`, `B-006`, `B-007`, `B-009`, `I-002`, `I-003`, `I-005` | `tools/specdev_tools/*.py`, `tests/**` | module unit tests pass without CLI integration |
| B3 | Single CLI wiring pass | `A-002`, `B-008`, `E-002`, `G-002`, `H-005`, `I-004` | `tools/specdev_tools/cli.py` | all new commands visible in `--help` and callable |
| B4 | Step schema mega-pass (`00..16`) | `D-002..D-020`, `D-022`, `H-002` | `schema/00_*.json` .. `schema/16_*.json` | all schemas validate; no schema regression |
| B5 | Shared docs contract updates | `F-001`, `H-008`, `H-010`, `A-008`, `I-007`, `I-009` | `docs/prompts/shared_expectations.md`, `docs/developers/reference.md`, `docs/README.md`, `tools/README.md`, `docs/audit/batch_B0_baseline.md` | docs reflect new commands/rules exactly |
| B6 | Prompt mega-pass (single touch for all prompts) | `A-004`, `A-005`, `A-006`, `A-007`, `A-009`, `C-005`, `C-006`, `F-002`, `F-003`, `F-004`, `H-009`, `I-006` | `prompts/prompt_00*.md` .. `prompts/prompt_16c*.md` | `prompt-sync` clean; no forward/self semantic dependencies |
| B7 | Canon seed + backfill | `B-003`, `B-004`, `B-005`, `B-010`, `G-003`, `G-004`, `G-005` | `canon/**`, `spec/**/*.json` | canonical lint/integrity pass in migration mode |
| B8 | Enforcement + CI finalization (single CI edit) | `E-003`, `E-004`, `E-008`, `E-010`, `A-003`, `A-011`, `G-006`, `H-007`, `I-008` | `tools/specdev_tools/validate.py`, `tools/specdev_tools/matrix.py`, `.github/workflows/ci.yml` | strict mode on; CI fully blocking on drift/hallucination/dependency-order/replay |

### 12.2 Why This Order Minimizes Rework
- `cli.py` is edited once (B3), not in 5 separate passes.
- `.github/workflows/ci.yml` is edited once (B8), after all commands exist.
- `schema/core/collections.schema.json` is edited once (B1) for trace + canonical + quality anchors.
- `tools/step_order.json` is created once (B1) and used everywhere else.
- Step schemas are edited once (B4) for canonical refs and quality metadata together.
- Prompts are edited once (B6) after shared expectations and schema contracts are final.
- Backfill (B7) happens only after schemas + validators + prompts are stable.

### 12.3 Call-Minimized Agent Execution Pattern
- Use one agent call per batch (`B0`..`B8`) with explicit task list and acceptance criteria.
- Require each batch to output:
  - changed files list,
  - verification command outputs,
  - unresolved blockers (if any).
- Do not start the next batch until the previous batch exit criteria are met.

### 12.4 Batch Gate Commands
Run at end of each batch as applicable:
```bash
# core/schema health
python -m specdev_tools.cli validate-all spec --repo-root .

# prompt contract health
python -m specdev_tools.cli prompt-sync spec --repo-root .

# canonical health
python -m specdev_tools.cli canonical-lint canon --repo-root .
python -m specdev_tools.cli canonical-integrity spec --repo-root .

# hardening checks
python -m specdev_tools.cli spec-quality-lint spec --repo-root .
python -m specdev_tools.cli hallucination-lint spec --repo-root .

# dependency integrity checks
python -m specdev_tools.cli dependency-order-lint --repo-root .
python -m specdev_tools.cli forward-replay-check --repo-root . --base-ref origin/main
```
In CI, set `--base-ref` from PR target branch (for GitHub Actions: `origin/${{ github.base_ref }}`).

---

## 13) Findings-to-Plan Coverage Matrix

| Finding | Covered By Tasks | Coverage Status | Notes |
|---|---|---|---|
| `F-001` Prompt/schema required drift | `A-001`, `A-002`, `A-004`, `A-003` | Full | Detection + fix + CI enforcement |
| `F-002` Trace taxonomy inconsistency | `C-001`, `C-002`, `C-003`, `C-004`, `C-005`, `C-006` | Full | Core enum + validators + prompts aligned |
| `F-003` Step 11 prompt/schema mismatch | `A-005`, `C-006`, `D-014` | Full | Immediate repair + structural canonicalization |
| `F-003A` Forward/self step dependencies | `I-001`, `I-002`, `I-004`, `I-006`, `I-008` | Full | Policy + lint + prompt rewrite + CI block |
| `F-004` CI missing enforcement | `A-003`, `A-011`, `E-008`, `H-007`, `I-008` | Full | Final CI includes all required blocking gates |
| `F-005` Partial deep validation coverage | `E-005`, `E-009`, `E-010` | Full | Missing step validators added and wired |
| `F-006` Governance command enum drift | `A-010`, `A-004`, `A-003` | Full | Validator and prompt contracts aligned |
| `F-007` Owner enum drift | `A-008`, `A-009`, `B5 docs pass` | Full | Core schema, prompts, docs aligned |
| `F-008` Monitoring artifact ref mismatch | `A-006` | Full | Prompt references normalized to valid artifact contract |
| `F-009` Shared structure divergence (`tech_stack`, deps, env/stage) | `D-021`, `D-022`, `D-012`, `D-018` | Full | Reuse via core shared anchors, then step refactor |
| `F-010` Fixtures lint HTTP overfitting | `A-012`, `C-004` | Full | Mode-aware lint behavior + trace normalization |
| `F-011` CLI command example mismatch | `A-007`, `H-010`, `I-007` | Full | Prompt + docs command contracts aligned |
| `F-012` Spec path ambiguity across repos | `B0 scope lock`, `I-009` | Full | Explicit repo-level spec scope protocol documented |

## 14) Machine-Readable Task Catalog
```json
{
  "report_id": "review_report_04_canonical_drift_and_implementation_plan",
  "generated_at_utc": "2026-02-21T15:51:01Z",
  "repo": "/Users/vichitracollective/vc-code/vc_wesbite",
  "toolkit": "/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit",
  "phases": [
    {"id": "A", "name": "Stabilize Existing Contracts", "task_count": 12},
    {"id": "B", "name": "Canonical Registry Foundation", "task_count": 10},
    {"id": "C", "name": "Core Contract Normalization", "task_count": 6},
    {"id": "D", "name": "Schema Canonical Ref Adoption", "task_count": 22},
    {"id": "E", "name": "Validator + CI Enforcement", "task_count": 10},
    {"id": "F", "name": "Prompt Redesign", "task_count": 4},
    {"id": "G", "name": "Migration + Backfill", "task_count": 6},
    {"id": "H", "name": "Prompt Hardening + Tooling + Docs", "task_count": 10},
    {"id": "I", "name": "Step-Order Integrity + Forward Replay", "task_count": 9}
  ],
  "total_tasks": 89,
  "blocking_findings": ["F-001", "F-002", "F-003", "F-003A"],
  "strict_mode_ready_after": ["G-005", "G-006", "H-007", "H-009", "I-008"],
  "execution_sequence": ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
}
```
