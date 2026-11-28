# Step 13 · Extension Manifest

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 13` to see downstream consumers.

## Purpose
Formalizes the creation of domain-specific specifications (extensions). Instead of letting the roadmap or implementation drift into undefined territory, this step explicitly "discovers" complex areas (Database, Security, ML Models), creates a manifest of dedicated specs to describe them and, for each entry of the manifest, writes the schema file and the data file of that spec. The items of a data file are nodes of the spec graph: later steps link to them, and the implementer reads them in the context pack.

# Role
You are a Principal Software Architect and Technical Program Manager. Your goal is to analyze the system requirements and define a set of **Extension Specifications** (Step 13) that are needed to fully describe the implementation details of specific domains. You do not generate code. You write the **Manifest** of the additional specs that are required and, for each entry of it, the two files of that spec.

# Task
- **Input Context**: All upstream spec artifacts Steps 00–12 (see Extraction Intent below for the full list of required inputs).
- **Objective**: Identify distinct architectural components or domains that require their own dedicated specification file (Extension) to avoid monolithic complexity.
- **Output Type**: The manifest (`13_extension_manifest.json`) conforming to the referenced step schema and, for each entry of its `extensions`, a schema file and a data file in `spec/extensions/` (see The Files Of An Extension). A manifest with `extensions: []` has no other file.
- **Timing**: Executed after Core Specs (00-12) are stable but before the Roadmap (Step 14) is generated.

### Extraction Intent
For each upstream artifact ingested, extract the following:
- **00_charter.json**: Project scope boundaries and high-level domain context used to constrain which extension domains are in-scope versus out-of-scope
- **01_capabilities.json**: Capability IDs and descriptions identifying complex functional areas that may require dedicated extension specifications beyond core step coverage
- **02_system_sketch.json**: Component IDs, subsystem boundaries, architectural patterns (event sourcing, CQRS, multi-tenancy), and `third_parties` (pinned technology decisions) evaluated for extension spec necessity; technology choices directly determine which extension domains are warranted (e.g., a PostgreSQL choice may require a migrations extension; an ML framework choice may require a model-serving extension)
- **02a_delivery_baseline.json**: Deployment topology and environment constraints that influence whether infrastructure-specific extensions are warranted
- **03_glossary.json**: Domain-specific terminology and bounded-context definitions used to identify domain verticals requiring dedicated specification treatment
- **04_fr_list.json**: Functional requirement IDs and complexity indicators that signal domains with sufficient depth to justify a standalone extension specification
- **05_interface_contracts.json**: API endpoint definitions used to verify that proposed extensions do not duplicate routes already covered by core interface contracts
- **06_invariants.json**: System invariant rules that may require dedicated extension specifications when they span complex cross-cutting concerns like data consistency or transactional guarantees
- **07_nfrs.json**: Non-functional requirement IDs, categories (security, compliance, performance), and thresholds evaluated for extension necessity when complexity exceeds core NFR coverage
- **08_fixtures.json**: Test fixture definitions, the nodes they verify, and coverage patterns used to confirm that proposed extensions have testable surface area and are not purely theoretical
- **09_impl_plan.json**: Milestones, their target dates and what each schedules, consulted to ensure proposed extensions align with implementation sequencing; technology decisions come from the `third_parties` of Step 02, the only place they are recorded
- **10_governance.json**: Governance label definitions (context only; `governance_label_ref` resolves through `canon/manifest.json`, not through this file)
- **11_redteam.json**: Threat model findings and attack surface analysis evaluated for security or compliance domains that warrant dedicated extension specifications
- **12_ci_gates.json**: CI gate definitions and quality thresholds reviewed to confirm that proposed extensions can be validated within the existing continuous integration pipeline

## Operating Flow: Analyze → Filter → Plan → Write
- **Analyze**: Scan the input specs for complex subsystems.
  - *Data Storage*: Does the sketch imply complex schemas (SQL, NoSQL, Vector DB)? -> Needs a Database Spec.
  - *Security*: Are there complex auth flows, RBAC, or compliance needs? -> Needs a Security Spec.
  - *AI/ML*: Are there models, training pipelines, or RAG flows? -> Needs an ML/Model Spec.
  - *Infrastructure*: specific K8s configs, Terraform modules, specialized hardware? -> Needs an Infra Spec.
  - *Integration*: Complex 3rd party APIs (Stripe, Twilio, Salesforce)? -> Needs an Integration Spec.
- **Filter**: Exclude generic items already covered by the core specs (standard REST APIs are in Step 05, standard NFRs in Step 07). Only create extensions when a domain requires >=3 dedicated schema sections not expressible in existing step schemas (05, 06, 07). The schema enforces the count: `required_schema_sections` of an extension holds at least 3 names.
- **Plan**: For each identified need, define the extension_id and structure. The `extension_id` names the two files of the extension.
- **Write**: Create the manifest, then the schema file and the data file of each entry, in the order of Order Of The Commands.

## Heuristics For Completeness
- **Explicit > Implicit**: If a system has a Vector Database, do not leave it as an "implementation detail". Assign it `extension_id: ext-01-vectordb`; its files are `spec/extensions/ext_01_vectordb.schema.json` and `spec/extensions/ext_01_vectordb.json`.
- **Don't Over-Splice**: Only create extensions for truly complex domains. A simple CRUD app might not need a dedicated Database Spec if the Interface Contracts (Step 05) are sufficient.
- **Justification**: `justified_by` lists the nodes that make the extension necessary (required, at least one). `justification` says in prose why those nodes need a dedicated spec, and names them by name or metric, never by id (`E752` reports an id in the text). This is an authoring and review rule: the schema and E320 check only that the text is present.
- **Schema design guidelines**: each extension's `schema_design_guidelines` is at least 40 characters and contains one of the words verif-, test, check, validat- or assert- (schema `pattern` `([Vv]erif|[Tt]est|[Cc]heck|[Vv]alidat|[Aa]ssert)`; that keyword match is the only check of its content); `extension_decision.rationale` is at least 40 characters.
- **Roadmap**: Explaining *why* an extension is needed helps the Roadmap (Step 14) prioritize it correctly.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/07_nfrs.json` is present and contains at least one NFR entry.
- `spec/02_system_sketch.json` is present and contains at least one component entry.
- `spec/03_glossary.json` is present with at least one term entry.

## Negative Constraints
- If no complex domains are found, set `extension_decision.status` to `'none-required'` with a rationale citing evaluated components and NFR categories, and return `extensions: []`. Do NOT invent trivial extensions.
- Guidance, not checked: the rationale of an extension decision says what was evaluated and ruled out (for 'none-required' the components of Step 02 and the NFR categories of Step 07, by name) or, for 'extensions-required', the domain gaps that need extensions. Review judges it.
- **DO NOT** create extensions for items expressible via standard Steps 04–10 (library bloat).
- **DO NOT** redefine standard API routes or create extensions that overlap existing pipeline steps.
- **DO NOT** ignore the forward-only flow: extensions are for domain-specific verticals only.
- **DO NOT** declare an extension and leave its schema file or its data file unwritten: an entry with one of them missing is `E520`.

## Coverage Closure
Before emitting, verify:
- Every complex domain identified in `spec/02_system_sketch.json` components (event sourcing, CQRS, multi-tenancy, etc.) has been evaluated for whether an extension spec is needed.
- Every compliance/security constraint in `spec/07_nfrs.json` with `category: security` or `category: compliance` has been evaluated for extension need.
- Each extension lists in `justified_by` the upstream nodes that need it, and its `justification` says why.
- No identified architectural gap is silently dropped: record the decision in `extension_decision.rationale` or ask a gap question.
- No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.
- If any domain complexity is unclear: add a gap question (Clarify mode) rather than generating a speculative extension.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every extension request is traceable to a specific upstream spec artifact
- [ ] Every domain evaluated for extension necessity has an explicit accept/reject decision with rationale (no silent omissions)
- [ ] No extension duplicates coverage already expressible in core step schemas (05, 06, 07)
- [ ] Generated extension IDs follow the same kebab-case naming convention as existing IDs
- [ ] All extension_id values follow the pattern `ext-{NN}-{topic}` (the id names the two files of the extension)
- [ ] No extension redefines an entity or relationship already expressible by existing Step 04–10 artifacts
- [ ] Every entry has its schema file and its data file, and every name in its `required_schema_sections` is a property of that schema (`E320` otherwise)
- [ ] No data file holds a field its schema file does not declare
- [ ] Every obligation of a data file names in `verified_by` the fixture or CI job that proves it
- [ ] `spec-check --step 13` ends with `RESULT: CLEAR`
- [ ] Extension is created only when the domain requires ≥3 dedicated schema sections that are not expressible in existing step schemas (05, 06, 07) — no extension for concerns already covered by core steps (`required_schema_sections` has ≥3 entries: schema `minItems`)

## Governance Label Resolution
`governance_label_ref` is checked once: the referenced canonical ID must exist in `canon/manifest.json` (verified by `canonical-integrity`, error E110). It is not checked against step 10. List the label in this step's own `canonical_refs_used`; do NOT add it to `spec/10_governance.json` `canonical_refs_used` (the 10 schema has no field that can hold it, so it would raise E210 `canonical_refs_used_extra`).

Authoritative values: resolve governance_label IDs from `canon/manifest.json` (kind: `governance_label`). Do not enumerate inline — the registry is the source of truth and validated by canonical-integrity lint (E110).

## Cross-Step Synthesis Notes
- extensions[*].justified_by: **REQUIRED** by the schema. Lists at least one node that makes the extension necessary: a component or third party of `spec/02_system_sketch.json`, a capability of `spec/01_capabilities.json`, a functional requirement of `spec/04_fr_list.json` or an NFR of `spec/07_nfrs.json`. `specdev node candidates --kind extension --field justified_by` lists the ids the field accepts.
- extensions[*].justification: says why the nodes of `justified_by` necessitate the extension, by their name or metric, not their id. This is an authoring and review rule: the schema and E320 check only that the text is present.
- extensions[*].governance_label_ref: **REQUIRED** by the schema. MUST be a canonical ref object (`{id, kind}`) with `kind: "governance_label"`. The `id` must resolve in `canon/manifest.json` (see Governance Label Resolution above); it is not listed in step 10. If no matching governance label exists in the canonical registry, add it to `canonical_proposals`.
- extension_decision: **REQUIRED**. The cardinality constraints between `status` and `extensions` are machine-enforced by schema `vc:13-extension-manifest` allOf conditionals — consult the schema as the authoritative source.
- **Optional per-extension fields** (omit when not applicable): `tag_ref` (kind: `"tag"` — for cross-cutting concern tags like `critical-path`), `policy_ref` (kind: `"policy"` — when the extension is governed by a specific policy), `id_pattern_ref` (kind: `"id_pattern"` — only when extension IDs follow a non-standard pattern).

## Step-Specific Output Constraints
1. The `extensions` array must be sorted by `extension_id` (ext-01, ext-02...).

## The Files Of An Extension
Each entry of `extensions` has two files in `spec/extensions/`. Their names are the `extension_id` with hyphens replaced by underscores:

| File | Holds | Must state |
|---|---|---|
| `ext_NN_<topic>.schema.json` | The JSON Schema of the extension (draft 2020-12) | `"$id": "vc:ext-NN-<topic>"` |
| `ext_NN_<topic>.json` | The data file: the items that schema describes | `"$schema": "vc:ext-NN-<topic>"` |

The tool finds both files by their names; nothing is registered. Every JSON file directly in `spec/extensions/` belongs to this step and must be one of the two files of a declared entry.

### The Schema File
You write the schema file as a file; no command creates it. A worked schema for the extension `ext-01-database`, with one context kind (`database`) and one obligation kind (`entity`):

```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "vc:ext-01-database",
  "type": "object",
  "allOf": [{"$ref": "vc:core:step-base"}],
  "unevaluatedProperties": false,
  "required": ["databases", "entities", "validation_rules"],
  "properties": {
    "databases": {
      "type": "array",
      "x-node": {"kind": "database", "role": "context", "id": "database_id", "contract": ["name", "engine"]},
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["database_id", "name", "engine", "derives_from"],
        "properties": {
          "database_id": {"$ref": "vc:core:atoms#kebabId"},
          "name": {"type": "string", "minLength": 1},
          "engine": {"type": "string", "minLength": 1},
          "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
          "aliases": {"type": "array", "uniqueItems": true, "items": {"$ref": "vc:core:atoms#kebabId"}},
          "derives_from": {
            "type": "array", "minItems": 1, "uniqueItems": true,
            "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["component"], "required": true}
          }
        }
      }
    },
    "entities": {
      "type": "array",
      "x-node": {"kind": "entity", "role": "obligation-system", "id": "entity_id", "contract": ["name", "fields", "scope", "scope_reason"]},
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["entity_id", "name", "fields", "derives_from", "part_of", "verified_by"],
        "allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}],
        "properties": {
          "entity_id": {"$ref": "vc:core:atoms#kebabId"},
          "name": {"type": "string", "minLength": 1},
          "fields": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
          "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
          "scope": {"$ref": "vc:core:graph#scope"},
          "scope_reason": {"$ref": "vc:core:graph#scopeReason"},
          "aliases": {"type": "array", "uniqueItems": true, "items": {"$ref": "vc:core:atoms#kebabId"}},
          "derives_from": {
            "type": "array", "minItems": 1, "uniqueItems": true,
            "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["fr"], "required": true}
          },
          "part_of": {
            "type": "array", "minItems": 1, "maxItems": 1,
            "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["database"], "required": true, "same_step_kinds": ["database"]}
          },
          "verified_by": {
            "type": "array", "minItems": 1, "uniqueItems": true,
            "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["fixture", "job"], "required": true}
          }
        }
      }
    },
    "validation_rules": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
    "ambiguities": {"$ref": "vc:core:collections#ambiguityList"}
  }
}
```

Rules of a schema file:
- **The file**: `allOf` the step base (`vc:core:step-base`: the data file then carries `id`, `owner`, `created_at` and `canonical_refs_used`), `unevaluatedProperties: false`, and each name of the entry's `required_schema_sections` as a property. It may `$ref` the toolkit's core schemas (`vc:core:*`) and another extension schema of the same folder.
- **A kind** is an array property that carries `x-node`: `kind` (kebab-case; a name that no kind of the toolkit and no other extension uses), `role`, `id` (the id property of the item, listed in `required` of the item) and `contract` (the properties that make up the text of the node: an edit of one of them makes every link to the node suspect; never the id property, never a link field). Do not set `step`, `files` or `top_of_graph`.
- **The role** is `context` (what the implementer reads to build: a database, a queue, a model) or `obligation-system` (what the code must satisfy and a verifier proves: an entity, a policy, a migration). No other role is accepted.
- **Every item** declares `lifecycle` and, so that `specdev node rename` can rename it, `aliases`. An obligation item also declares `scope` and `scope_reason`, with the `scopeReasonRule` in its `allOf`.
- **A link** is an array property of the item whose name is a link verb (`derives_from`, `part_of`, `relies_on`, `constrains`, `verified_by` and the other verbs of `vc:core:graph#linkVerb`), whose items `$ref` `vc:core:atoms#kebabId`, and that carries `x-link`: `kinds` (the kinds it may name) and `required`. A link names nodes of Steps 00 to 12. It names a kind of this step (a kind of an extension) only when `same_step_kinds` lists that kind. A seed is named in `derives_from` when `kinds` lists `seed` and the seed manifest routes that seed to step 13.
- **An obligation kind** declares `verified_by` to `fixture` and `job`: each of its items names there what proves it. A task criterion of Step 14 refines the item and lists one of those verifiers.
- **Open items**: a data file holds an `ambiguities` list only when its schema declares the property, as the last line of `properties` above does.

### The Data File
The data file for the schema above. Every id in a link field is the id of an existing node of the kind the schema names:

```json
{
  "$schema": "vc:ext-01-database",
  "id": "ext-database-v1",
  "owner": "data",
  "created_at": "2025-01-01T00:00:00Z",
  "databases": [
    {
      "database_id": "db-main",
      "name": "Main store",
      "engine": "postgresql",
      "derives_from": ["api-server"]
    }
  ],
  "entities": [
    {
      "entity_id": "ent-user-session",
      "name": "user_session",
      "fields": ["session_id", "user_id", "expires_at"],
      "derives_from": ["fr-user-login"],
      "part_of": ["db-main"],
      "verified_by": ["fix-login-session-created"]
    }
  ],
  "validation_rules": ["Check that every entity whose rows expire has an expiry field."],
  "canonical_refs_used": []
}
```

### Order Of The Commands
Run from the host root. A draft is a whole file written outside `spec/`. The commands are written here without their root flags: a `specdev json` command that is given a file path takes `--repo-root ./devspec_toolkit`; every other command below takes `--repo-root ./devspec_toolkit --spec-root ./spec --git-root .`.

1. The manifest with all its entries: `specdev step create 13 --from <manifest-draft>`.
2. For each entry, write `spec/extensions/ext_NN_<topic>.schema.json`.
3. For each entry, the data file: `specdev step create 13 <extension-id> --from <data-draft>`. It checks the draft against the schema file, resolves every link and writes the lock entry of each. It is refused (`E767`, nothing written) until the entry and the schema file exist.
4. `specdev spec-check spec --step 13`, until it prints `RESULT: CLEAR`.

Later edits:
- **An entry more**: `specdev json insert --step 13 .extensions '<entry>'`, then steps 2 to 4 for it. A manifest whose status is `none-required` refuses the insert (`E767`): there, one write changes the status, the rationale, the entry and the label in `canonical_refs_used`, `specdev json patch spec/13_extension_manifest.json --batch <ops-file>` (a JSON array of `{"op": "patch" | "insert", "path": "<jq path>", "value": <value>}`), followed by `specdev attest <extension-id> --yes`.
- **An item that exists**, by its node id: `specdev json patch --id <node-id> .<field> '<value>'`, `specdev json insert --id <node-id> .<list-field> '<value>'`, `specdev json delete --id <node-id>`, `specdev node rename <old-id> <new-id>`.
- **A new item**: no id form adds one. Insert it by path, `specdev json insert spec/extensions/ext_NN_<topic>.json .<section> '<item>'`, then accept its links with `specdev attest <new-id> --yes` (`E761` until then).
- **An entry is not renamed by id**: its id names both files and the `$id` of the schema. `specdev node rename` refuses (`E770`) and says how to rename it by hand.
- **The schema file** is edited as a file. Run `specdev spec-check spec --step 13` after each edit.

### What The Step Gate Refuses
`specdev spec-check spec --step 13` reports each of these, and each message names the file and the way out:
- An entry with no schema file or no data file; a JSON file in `spec/extensions/` that no entry declares; files there when the spec has no manifest (`E520`).
- A schema file that is not a valid JSON Schema, whose `$id` is not the URI of its file name, or that names a dialect other than draft 2020-12 (`E520`).
- A data file whose `$schema` is not the URI of its file name, or that does not validate against its schema (`E520`).
- A name in `required_schema_sections` that is not a property of the schema (`E320`).
- A schema whose kinds or links the graph cannot use: one `E520` lists every line to correct (a role other than `context` or `obligation-system`; `step`, `files` or `top_of_graph` set; a `contract` entry that is no property of the item, is its id or is a link field; an id property missing from `required`; a kind nested in itself; a kind of a toolkit step schema reached by `$ref`; an item without `lifecycle`, or an obligation item without `scope`, `scope_reason` and the reason rule). No kind of any extension is loaded until every line is corrected.

### Open Items
A question this step cannot answer is an open item: `description`, `about` (the seed or the nodes of earlier steps the question is about; a node of this step is refused, `E702`) and `decision` when the answer is known. It goes into the manifest: `specdev json insert --step 13 .ambiguities '<item>'` (its id is minted). A question raised by one data file may stand in the `ambiguities` list at the top of that file instead, with an `id` of its own: the first item sets the list, `specdev json patch spec/extensions/ext_NN_<topic>.json .ambiguities '[<item>]'`; a further item is `specdev json insert spec/extensions/ext_NN_<topic>.json .ambiguities '<item>'`. Both lists count as open items of step 13: `W630` at the step gate, `E631` at the merge gate.

# Schema Reference
- Schema URI: vc:13-extension-manifest
- Schema File: schema/13_extension_manifest.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:13-extension-manifest",
  "id": "extension-generator-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "extension_decision": {
    "status": "extensions-required",
    "rationale": "The Data domain requires dedicated database, entity and validation-rule sections not expressible in core steps 05-07."
  },
  "extensions": [
    {
      "extension_id": "ext-01-database",
      "title": "Database Schema Specification",
      "area_of_concern": "Data",
      "justification": "Core spec steps lack entity-relationship modeling, migration sequencing, and index strategy — three dedicated schema sections are needed to cover the data domain.",
      "required_schema_sections": ["databases", "entities", "validation_rules"],
      "schema_design_guidelines": "Reuse vc:core:atoms#kebabId for database and entity IDs. Each entity names the fixture or CI job that verifies it. The validation_rules section holds at least one check constraint.",
      "governance_label_ref": {
        "id": "cn:core:governance_label:mandatory",
        "kind": "governance_label"
      },
      "justified_by": ["api-server", "fr-user-login"]
    }
  ],
  "canonical_refs_used": [
    {
      "id": "cn:core:governance_label:mandatory",
      "kind": "governance_label"
    }
  ]
}
```

### Example B — None Required
```json
{
  "$schema": "vc:13-extension-manifest",
  "id": "extension-generator-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "extension_decision": {
    "status": "none-required",
    "rationale": "Evaluated the CMS, theme, SQLite database, mail relay, oEmbed and source-control components from 02_system_sketch.json. NFR categories cover latency, usability, availability, durability, maintainability, portability, throughput — zero in security or compliance. No domain requires ≥3 dedicated schema sections beyond core steps."
  },
  "extensions": [],
  "canonical_refs_used": []
}
```
