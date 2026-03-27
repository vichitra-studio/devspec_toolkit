# P1-D: Genericity & Domain Bias -- Findings

**Date**: 2026-03-19
**Agent**: P1-D
**Branch**: `codex/canonical-drift-review-plan`

---

## Summary

- Total findings: 14
- Critical: 0 | High: 5 | Medium: 5 | Low: 3 | Info: 1

---

## Findings

### FINDING-001: Step 05 `method` enum hardcodes HTTP verbs only

- **Severity**: HIGH
- **Category**: GENERICITY
- **Location**: `schema/05_interface_contracts.schema.json`:51-59
- **Description**: The `apis[].method` enum is restricted to `["GET", "POST", "PUT", "PATCH", "DELETE"]` -- pure HTTP verbs. This makes Step 05 unusable for CLI tools (which have commands/subcommands), event-driven systems (which have event types like publish/subscribe), gRPC (which has unary/server-streaming/client-streaming/bidi-streaming), MQTT (publish/subscribe), or library SDKs (which have function signatures). Ironically, the schema's own `protocol` enum supports `"grpc"`, `"ws"`, and `"mqtt"`, but the `method` field only accepts HTTP verbs.
- **Evidence**:
  ```json
  "method": {
    "type": "string",
    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]
  }
  ```
  Yet `protocol` allows: `["http", "grpc", "ws", "mqtt"]`. A gRPC interface would need to set `protocol: "grpc"` but has no valid `method` value since gRPC uses "unary", "server_stream", etc.
- **Recommendation**: Make `method` conditionally validated based on `protocol`. For HTTP: current verb set. For gRPC: `["unary", "server_stream", "client_stream", "bidi_stream"]`. For event/ws/mqtt: `["publish", "subscribe", "request_reply"]`. Alternatively, make `method` a free-form string with a pattern constraint (lowercase/uppercase kebab) and move the valid values to the canonical registry, allowing project-specific extension. Consider also renaming from `method` to `operation_type` to reduce HTTP bias in naming.

---

### FINDING-002: Step 05 `parameters[].in` enum is HTTP-location-specific

- **Severity**: HIGH
- **Category**: GENERICITY
- **Location**: `schema/05_interface_contracts.schema.json`:83-88
- **Description**: The `parameters[].in` enum is `["query", "path", "header"]` -- these are HTTP-specific parameter locations (matching OpenAPI's `in` field). For a CLI tool, parameters come from `argv`, `stdin`, `env`, or config files. For gRPC, parameters are message fields. For event systems, parameters are payload fields. This enum locks the schema to HTTP semantics.
- **Evidence**:
  ```json
  "in": {
    "type": "string",
    "enum": ["query", "path", "header"]
  }
  ```
  Missing even for HTTP: `"body"` and `"cookie"` (both valid in OpenAPI). Missing entirely for non-HTTP: `"argv"`, `"stdin"`, `"env"`, `"config"`, `"payload"`, `"metadata"` (gRPC), `"topic"` (MQTT).
- **Recommendation**: Extend the enum to cover non-HTTP locations: `["query", "path", "header", "body", "cookie", "argv", "stdin", "env", "config", "payload", "metadata", "field"]`. Alternatively, move to canonical registry for project-specific extensibility. Consider making `in` conditional on `protocol` via `allOf/if/then`.

---

### FINDING-003: Step 05 `route` field name implies HTTP URL paths

- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Location**: `schema/05_interface_contracts.schema.json`:48-50
- **Description**: The field `apis[].route` (type: string, no constraints) is named using HTTP/web terminology. For a CLI tool, this would be a "command path" (e.g., `specdev validate`). For a library, this would be a "function signature" or "module path". For gRPC, this would be a "service/method path" (e.g., `UserService/GetUser`). The name creates cognitive friction for non-web projects.
- **Evidence**:
  ```json
  "route": { "type": "string" }
  ```
  The field is optional (not in `required`), which mitigates impact, but the naming still signals HTTP bias.
- **Recommendation**: Rename to `path` or `identifier` -- both are domain-neutral. If backward compatibility is a concern, accept both `route` and `path` via a deprecation alias in the canonical registry.

---

### FINDING-004: Step 05 `request_schema_ref` / `response_schema_ref` assume request-response pattern

- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Location**: `schema/05_interface_contracts.schema.json`:61-66
- **Description**: The fields `request_schema_ref` and `response_schema_ref` assume a synchronous request-response communication pattern. This does not fit: fire-and-forget events (no response), streaming protocols (continuous data, not single request/response), pub/sub systems (one publisher, many subscribers, no direct response), or CLI tools (stdin/stdout/stderr, not request/response).
- **Evidence**:
  ```json
  "request_schema_ref": { "type": "string" },
  "response_schema_ref": { "type": "string" }
  ```
  Both are optional, which mitigates the issue. However, the naming prevents non-request/response interfaces from describing their data shapes naturally.
- **Recommendation**: Generalize to `input_schema_ref` and `output_schema_ref`. These terms work for all paradigms: HTTP request/response, CLI stdin/stdout, event payload, gRPC message, function arguments/return values.

---

### FINDING-005: Step 15 `route_map` is inherently web-service-specific

- **Severity**: HIGH
- **Category**: GENERICITY
- **Location**: `schema/15_scaffold.schema.json`:43-76
- **Description**: The entire `route_map` array is web-service-specific. Each entry has `api_ref`, `path`, and `method` (with HTTP verb enum `["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"]`). This required field would be meaningless for: CLI tools (which have command trees, not routes), libraries/SDKs (which have modules and function exports), data pipelines (which have stages/transforms), desktop/mobile apps (which have screens/views, not routes), embedded systems (which have interrupt handlers, not routes). Making `route_map` required (line 139) means Step 15 cannot validate for any non-web project.
- **Evidence**:
  ```json
  "route_map": {
    "type": "array",
    "items": {
      "properties": {
        "api_ref": { "$ref": "...#kebabId" },
        "path": { "type": "string" },
        "method": { "enum": ["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"] }
      },
      "required": ["api_ref", "path", "method"]
    }
  }
  ```
  And in the top-level `required` array (line 139): `"route_map"` is mandatory.
- **Recommendation**: Rename `route_map` to `interface_map` or `entry_points` and generalize the item schema. Replace `method` with an extensible `operation_type` (or make it conditional on the project type from `service_skeleton`). Make `route_map`/`interface_map` optional, with a conditional requirement: if `service_skeleton.framework` indicates a web framework, then require it; otherwise, allow alternatives like `command_map` (for CLIs), `export_map` (for libraries), or `stage_map` (for pipelines). At minimum, remove `route_map` from the unconditional `required` array.

---

### FINDING-006: Step 15 `service_skeleton` names and description assume web services

- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Location**: `schema/15_scaffold.schema.json`:23-42
- **Description**: The field is named `service_skeleton` (implying a running service) with a `framework` property described as "Web framework (e.g., fastapi, nextjs, gin)". For a CLI tool, library, or data pipeline, there is no "service" and the framework description is misleading. The field is required (line 138).
- **Evidence**:
  ```json
  "service_skeleton": {
    "properties": {
      "language": {
        "description": "Programming language (e.g., python, typescript, go). Use lowercase/kebab-case."
      },
      "framework": {
        "description": "Web framework (e.g., fastapi, nextjs, gin). Use lowercase/kebab-case."
      },
      "modules": { ... }
    },
    "required": ["language"]
  }
  ```
  The `language` property and `modules` are generic. Only `framework`'s description is biased.
- **Recommendation**: Rename `service_skeleton` to `project_skeleton`. Update `framework` description to: "Framework or toolkit (e.g., fastapi, click, react-native, pytorch). Use lowercase/kebab-case." This is a naming-only change with no structural impact.

---

### FINDING-007: Step 12 `token_permissions` is GitHub Actions-specific

- **Severity**: HIGH
- **Category**: GENERICITY
- **Location**: `schema/12_ci_gates.schema.json`:88-99
- **Description**: The `jobs[].security.token_permissions` field uses a GitHub Actions-specific pattern: an object with string keys like `contents`, `packages` mapped to values `["read", "write", "none"]`. This is a direct mapping of GitHub Actions' `permissions` block. GitLab CI, Jenkins, CircleCI, Buildkite, and other CI systems do not use this permission model. The description confirms this: "Token permission scopes (e.g. {'contents': 'read', 'packages': 'write'})." -- these are GitHub-specific scope names.
- **Evidence**:
  ```json
  "token_permissions": {
    "type": "object",
    "additionalProperties": {
      "type": "string",
      "enum": ["read", "write", "none"]
    },
    "description": "Token permission scopes (e.g. {'contents': 'read', 'packages': 'write'})."
  }
  ```
  The `runner_labels` property (line 81-86) with examples `'self-hosted', 'ubuntu-latest'` is also GitHub Actions-specific terminology, though the structure (string array) is generic enough.
- **Recommendation**: Generalize `token_permissions` to a `permissions` object with a `provider` field and a flexible `scopes` sub-object. Or make it a generic key-value map with a description that does not assume GitHub. Update the description to be CI-provider-agnostic: "CI token/credential permission scopes as key-value pairs." Consider also adding a `ci_provider` field to `jobs[]` so that provider-specific validations can be applied conditionally.

---

### FINDING-008: Step 12 `environment_protection` assumes GitHub Environments

- **Severity**: LOW
- **Category**: GENERICITY
- **Location**: `schema/12_ci_gates.schema.json`:100-114
- **Description**: The `environment_protection` sub-object with `required_reviewers` and `wait_timer_minutes` maps directly to GitHub Actions Environment Protection Rules. While the concept of deployment gates exists across CI systems, the specific field names and structure are GitHub-flavored. Other systems use different abstractions (GitLab uses "approval rules", Jenkins uses "input step").
- **Evidence**:
  ```json
  "environment_protection": {
    "properties": {
      "required_reviewers": { "type": "integer", "minimum": 0 },
      "wait_timer_minutes": { "type": "integer", "minimum": 0 }
    }
  }
  ```
- **Recommendation**: LOW priority. The fields are generic enough conceptually (reviewers + wait time). Update the descriptions to be provider-agnostic. Optionally add `approval_type` enum to support different gate mechanisms.

---

### FINDING-009: Core `environmentName` enum hardcodes 4 deployment environments

- **Severity**: HIGH
- **Category**: GENERICITY
- **Location**: `schema/core/collections.schema.json`:198-206
- **Description**: The `environmentName` enum is hardcoded to `["dev", "ci", "staging", "prod"]`. This is consumed by Step 02a (`environments` required keys, line 37-41) which mandates ALL FOUR environments exist, and by Step 16 (`review.delivery_status.deployments[].env`, line 1708-1719). For many project types, this 4-environment model is wrong: libraries/SDKs have no deployment environments (they are published to registries), embedded systems may have `["dev", "test", "factory", "field"]`, data pipelines may have `["dev", "test", "prod"]` (no staging), simple CLI tools may only have `["dev", "release"]`, and mobile apps have `["debug", "release", "beta"]`. Step 02a compounds the problem by requiring all 4 as mandatory keys (line 37-41: `"required": ["dev", "ci", "staging", "prod"]`).
- **Evidence**:
  Core definition:
  ```json
  "environmentName": {
    "$anchor": "environmentName",
    "type": "string",
    "enum": ["dev", "ci", "staging", "prod"]
  }
  ```
  Step 02a usage (line 37-41):
  ```json
  "environments": {
    "propertyNames": { "$ref": "...#environmentName" },
    "required": ["dev", "ci", "staging", "prod"],
    "minProperties": 4
  }
  ```
  Step 16 narrows it further to `["dev", "staging", "prod"]` in the review deployment status (line 1714-1718).
- **Recommendation**: Move the environment name enum to the canonical registry so projects can define their own environments. Change `environmentName` from a closed enum to a pattern-validated string (e.g., `^[a-z][a-z0-9-]*$`). Remove the hardcoded `required: ["dev", "ci", "staging", "prod"]` from Step 02a and instead require `minProperties: 1` with validation that at least one environment exists. The `stageName` definition (line 209-216) has the same issue and should be unified with `environmentName` (they are identical enums).

---

### FINDING-010: Step 16 `implemented_endpoints` naming assumes web service endpoints

- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Location**: `schema/16_impl_context.schema.json`:1641-1646
- **Description**: The `review.fixture_status.implemented_endpoints` field name assumes the project has "endpoints" (a web service concept). For a CLI tool, these would be "implemented commands". For a library, "implemented exports/functions". For a data pipeline, "implemented stages". The field itself is just an array of traceIds, so its structure is generic -- only the name is biased.
- **Evidence**:
  ```json
  "implemented_endpoints": {
    "type": "array",
    "items": {
      "$ref": "...#traceId"
    }
  }
  ```
  It is required (line 1686): `"required": ["implemented_endpoints", "test_results", "ci_status"]`.
- **Recommendation**: Rename to `implemented_interfaces` or `implemented_items`. The structure (array of traceIds) is already generic. This is a naming-only change.

---

### FINDING-011: Step 16 `drift.checks[].target` enum is partially web-biased

- **Severity**: LOW
- **Category**: GENERICITY
- **Location**: `schema/16_impl_context.schema.json`:1055-1064
- **Description**: The `target` enum `["api", "schema", "nfr", "invariant", "fixture", "config"]` is mostly generic but includes "api" which implies a network API. For a CLI tool or library, the equivalent drift target would be "interface" or "contract". Most values are fine for any project type.
- **Evidence**:
  ```json
  "target": {
    "type": "string",
    "enum": ["api", "schema", "nfr", "invariant", "fixture", "config"]
  }
  ```
- **Recommendation**: LOW priority. Consider adding `"interface"` as an alias for `"api"` or renaming `"api"` to `"interface"` since the toolkit already uses "interface_contracts" as the Step 05 name.

---

### FINDING-012: Step 16 `checklist[].layer` enum is web-architecture-biased

- **Severity**: MEDIUM
- **Category**: GENERICITY
- **Location**: `schema/16_impl_context.schema.json`:315-327
- **Description**: The `layer` enum `["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"]` assumes a layered web service architecture (database, model/ORM, service logic, API controllers, integration). For a CLI tool, relevant layers might be `["parser", "core", "output", "tests"]`. For a library: `["types", "core", "public_api", "tests"]`. For embedded: `["hal", "driver", "application", "tests"]`. For data pipelines: `["ingestion", "transform", "output", "tests"]`. Only `"tests"`, `"docs"`, `"config"`, and `"security"` are truly generic.
- **Evidence**:
  ```json
  "layer": {
    "type": "string",
    "enum": ["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"]
  }
  ```
- **Recommendation**: Move layer values to the canonical registry for project-specific extensibility. Alternatively, split into generic layers (always available: `tests`, `docs`, `config`, `security`) and domain-specific layers (project defines its own: `db`, `model`, `service`, `api` for web; `parser`, `core`, `output` for CLI; etc.). At minimum, change from a closed enum to a pattern-validated string.

---

### FINDING-013: Step 10 `review_policy.evidence_source_by_phase` hardcodes deployment phases

- **Severity**: LOW
- **Category**: GENERICITY
- **Location**: `schema/10_governance.schema.json`:88-107
- **Description**: The `evidence_source_by_phase` object has hardcoded required properties `["dev", "staging", "prod"]`. This mirrors the environment bias in FINDING-009 but in the governance context. A library that is published (not deployed) has no "staging" or "prod" evidence source.
- **Evidence**:
  ```json
  "evidence_source_by_phase": {
    "properties": {
      "dev": { "type": "string" },
      "staging": { "type": "string" },
      "prod": { "type": "string" }
    },
    "required": ["dev", "staging", "prod"]
  }
  ```
- **Recommendation**: Make the required phases dynamic by referencing the project's defined environments from Step 02a rather than hardcoding. Or change to `additionalProperties: { "type": "string" }` with `minProperties: 1`.

---

### FINDING-014: Schemas already generic enough for most project types

- **Severity**: INFO
- **Category**: GENERICITY
- **Location**: Multiple schemas
- **Description**: The following schemas are already domain-neutral and work for any project type without modification:
  - **Step 00 (charter)**: Problem statement, success metrics, stakeholders, user segments -- entirely generic.
  - **Step 01 (capabilities)**: Scope enum `["in", "out", "future"]` is universal.
  - **Step 03 (glossary)**: Terms with definitions -- universal.
  - **Step 04 (fr_list)**: Functional requirements with acceptance criteria -- universal.
  - **Step 06 (invariants)**: Business rules with jsonlogic/cel/text -- universal.
  - **Step 07 (nfrs)**: NFR categories include domain-neutral items (maintainability, usability, portability, energy). The `stage` field references `stageName` which has the environment enum issue (FINDING-009), but the NFR structure itself is generic.
  - **Step 08 (fixtures)**: Test modes `["unit", "contract", "e2e", "redteam"]` work across project types.
  - **Step 09 (impl_plan)**: Tech stack and milestones -- generic.
  - **Step 11 (redteam)**: Threat categories `["authn", "authz", "business_logic", "transport", "data_privacy"]` are somewhat web-biased but broadly applicable. Missing categories for other domains: `"memory_safety"`, `"physical_access"`, `"supply_chain"`.
  - **Step 13 (extension_generator)**: Generic.
  - **Step 13a (completeness_assessment)**: Generic.
  - **Step 14 (roadmap)**: Generic.
  - **Step 02 (system_sketch)**: The `components[].type` enum `["service", "db", "queue", "cache", "job", "ui", "lib", "external"]` is reasonably broad. Missing for non-web: `"cli"`, `"driver"`, `"firmware"`, `"model"` (ML). The `connections[].protocol` enum `["http", "grpc", "event", "rpc", "db", "file"]` is more generic than Step 05's but still missing: `"ipc"`, `"serial"`, `"spi"`, `"i2c"`, `"usb"`, `"pipe"`.
- **Evidence**: See individual schema files listed above.
- **Recommendation**: No changes needed for the generic schemas. For Step 02 and Step 11, consider expanding their enums via canonical registry to support more project types, but this is lower priority than the HIGH findings.

---

## Cross-Project Compatibility Matrix

Assessment of whether each affected schema would work as-is for non-web project types:

| Schema | CLI Tool | Mobile App | Data Pipeline | Library/SDK | Embedded System | Desktop App |
|---|---|---|---|---|---|---|
| 02 system_sketch | Partial (missing `cli` type) | OK | OK | OK | Partial (missing protocols) | OK |
| 02a delivery_baseline | BROKEN (requires 4 envs) | BROKEN | BROKEN | BROKEN | BROKEN | BROKEN |
| 05 interface_contracts | BROKEN (HTTP methods) | BROKEN | BROKEN | BROKEN | BROKEN | BROKEN |
| 10 governance | Partial (phase names) | Partial | Partial | BROKEN (no staging/prod) | Partial | Partial |
| 12 ci_gates | OK (security is optional) | OK | OK | OK | OK | OK |
| 15 scaffold | BROKEN (route_map required) | BROKEN | BROKEN | BROKEN | BROKEN | BROKEN |
| 16 impl_context | Partial (naming only) | Partial | Partial | Partial | Partial | Partial |

**BROKEN** = Schema validation would reject valid data for this project type.
**Partial** = Schema accepts data but naming/enums cause confusion or force awkward workarounds.
**OK** = Schema works without issues.

---

## Summary of Recommended Priority

1. **FINDING-009** (environmentName hardcoding) -- Foundation fix. Affects Steps 02a, 07, 10, 16. Fix this first as other fixes depend on a flexible environment model.
2. **FINDING-005** (route_map required) -- Blocks Step 15 for all non-web projects.
3. **FINDING-001** (method enum HTTP-only) -- Blocks Step 05 for non-HTTP interfaces.
4. **FINDING-002** (parameters[].in HTTP locations) -- Blocks Step 05 parameter modeling for non-HTTP.
5. **FINDING-007** (token_permissions GitHub-specific) -- Blocks Step 12 security modeling for non-GitHub CI.
6. **FINDING-012** (layer enum web-biased) -- Moderate impact on Step 16 usability.
7. **FINDING-006** (service_skeleton naming) -- Naming fix, low effort.
8. **FINDING-004** (request/response naming) -- Naming fix, low effort.
9. **FINDING-003** (route naming) -- Naming fix, low effort.
10. **FINDING-010** (implemented_endpoints naming) -- Naming fix, low effort.
11. **FINDING-013** (evidence_source_by_phase) -- Related to FINDING-009.
12. **FINDING-011** (drift target) -- Very minor.
13. **FINDING-008** (environment_protection) -- Very minor.

The overarching recommendation across all HIGH findings is to move hardcoded enums to the canonical registry, allowing projects to define domain-appropriate values while keeping sensible defaults for web services.
