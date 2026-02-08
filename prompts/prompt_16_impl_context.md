# Step 16 · Implementation Context (Trinity Anchor)

## Purpose
Create or update the **canonical Step 16 anchor** at `spec/16_impl_context.json`.
This file is the **root reference** for the Trinity Loop and exists alongside per‑milestone execution files in `spec/impl_context/`. It must:
1. Summarize the current execution scope.
2. Declare traceable checklist items for the active implementation cycle.
3. Record documentation impact decisions and seed provenance.
4. act as the union/root of all active milestone implementation contexts (16a/16b/16c).

## When To Use This Prompt
- You need a **single, canonical Step 16** artifact in `spec/`.
- You want a root view of the current Trinity cycle that references active milestone contexts.
- You are aligning a repo to the toolkit version that expects `spec/16_impl_context.json`.

## Tool Execution
Validate the generated JSON:
```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

# Role
You are a senior software architect producing the Step 16 **Trinity Anchor**.
Generate a **machine‑checkable JSON artifact** that captures the plan,
implementation checklist, and review expectations for the *current* execution cycle.

# Seed Order & Mandatory Sources
- Read `spec/common/seed_manifest.json` first.
- Use `step_requirements["16"]` if present. If missing, use the union of `16a/16b/16c`.
- Ingest required seeds in order before any other context.
- Populate `seed_refs` with the seeds actually used.
- If a required seed is missing or stale, stop and request it before proceeding.

# Context To Ingest
- **Roadmap**: Step sequencing and current milestone selection from `spec/14_roadmap.json`.
- **Implementation Plan**: Tech stack and constraints from `spec/09_impl_plan.json`.
- **Core Specs**: Relevant FRs (04), APIs (05), Invariants (06), NFRs (07), Fixtures (08).
- **Active Impl Contexts**: Enumerate any active files in `spec/impl_context/` (16a/b/c).
- **Documentation Map**: `README.md` and `docs/README.md` for current doc surface.

# Operating Flow (MANDATORY)
1. **Context Review**: Resolve seeds and ingest required sources.
2. **Scope**: Identify the exact execution scope for the current cycle.
3. **Active Contexts**: List `spec/impl_context/*.json` files in `plan.context.existing_structures`.
4. **Drift Check**: Verify that the Anchor (Step 16) does not conflict with Milestone contexts (16a/b/c).
5. **Checklist**: Convert relevant spec requirements into atomic checklist items.
6. **Docs Impact**: Decide whether docs updates are required and list impacted docs.
7. **Roadmap Sync**: If you identify that milestones are fully completed based on the ingested context, you MUST update:
    - `spec/14_roadmap.json`: Statuses to `done`.
    - `spec/09_impl_plan.json`: Statuses to `done`.
8. **Emit**: Write `spec/16_impl_context.json`.

# FORBIDDEN ACTIONS (Immediate Rejection)
1. **NEVER** hallucinate `step_id` or use loose references.
2. **NEVER** omit `commit_hash` in `spec_ref`.
3. **NEVER** emit incomplete JSON or use placeholder values.
4. **NEVER** use `plan.tasks` or `metadata`.

# Field Definitions & Rules (MANDATORY)
**Crucial**: Use the following exact definitions to ensure compliance:

## 1. `plan.summary` (The Step Summary)
*   `functional_summary`: A 1-paragraph summary of what this step accomplishes in the global architecture.
*   `scope_in`: List explicit concerns that are IN scope.
*   `scope_out`: List explicit concerns that are OUT of scope.
*   `target_file_patterns`: List **ALL** likely files that will be modified.
    *   *Rule*: Use glob patterns (e.g. `src/auth/*.py`).
    *   *Expectation*: If a file is not matched here, the coder is forbidden from touching it.

## 2. `plan.spec_alignment.checklist` (The Contract)
*   `checklist`: A list of **Atomic Requirements**.
    *   `id`: Uppercase snake-case ID (stable, e.g. `CHK_AUTH_01`).
    *   `spec_ref`: **Structured Object**. `{ type, id, line_range, commit_hash }`.
        *   *Rule*: `commit_hash` is MANDATORY. Do not use placeholders.
    *   `description`: **Verbose, Atomic, and Self-Explanatory**.
        *   *Rule*: Use "Subject-Action-Constraint" format.
    *   `linked_test_expectation`: **CRITICAL**. A concrete test identifier or command (e.g. `pytest tests/module/test_feature.py::test_name`).
        *   *Expectation*: This serves as the "contract" for verification.
    *   `implementation`: **Execution Slots**.
        *   `status`: `pending`, `in_progress`, `verified`, `deferred`.
        *   `files_touched`: Files explicitly modified.
        *   `actions`: Atomic implementation steps.
            *   `type`: `file_create`, `file_edit`, `run_command`, `manual_verification`.
            *   `description`: Verbose action description.
            *   `target` / `command`: Mandatory based on type.

## 3. `plan.ambiguities` (Risk Management)
*   List ANY ambiguity that would affect implementation.
    *   `id`: unique kebab-case identifier.
    *   `description`: What is unclear?
    *   `source`: `spec`, `code`, `plan`, `mixed`, `review`.
    *   `severity`: `blocking` or `non_blocking`.
    *   `mitigation`: Required for non_blocking.
    *   `impact`: List of affected components/flows.
    *   `status`: `resolved`, `tracking`, `deferred`, `blocked`.

## 4. `plan.drift` (Sustainment)
*   `checks`: Define periodic drift checks.
    *   `target`: `api`, `schema`, `nfr`, `invariant`, `fixture`, `config`.
    *   `method`: `runtime-sample`, `log-diff`, `schema-diff`, `trace-replay`.
    *   `schedule`: hourly/daily/weekly/monthly or cron expression.
    *   `remediation_policy`: Explicit steps to fix.

## 5. `plan.review_requirements` (Verification Plan)
*   `test_commands`: Precision commands to run tests.
    *   *Rule*: must match `linked_test_expectation` commands.

## 6. `plan.docs_impact` (Documentation Update)
*   `status`: `required` or `not_required`.
    *   *Rule*: If code changes are planned, you MUST set `status: required` and list doc paths in `docs_touched`.

## 7. `plan.solution` (Architecture Sketch)
*   `architecture_sketch`: High-level description of the technical approach.
*   `sequence_of_concerns`: Ordered list of implementation phases (e.g., ["Models", "Views", "Tests"]).
*   `risks`: Array of identified technical risks.

## 8. `plan.context` (Existing Codebase Context)
*   `existing_structures`: Array of known code or non-code structures.
    *   *Rule*: Use strings for non-code artifacts, objects for code signatures.
    *   For code objects: `{ signature, source_file, line_range }` are required.
*   `coding_examples`: Optional array of illustrative code snippets.

## 9. `plan.security` (Security Considerations)
*   `status`: `not_applicable` or `planned`.
    *   If `not_applicable`: Provide `reason`.
    *   If `planned`: List `new_fixtures` (IDs) and `spec_mutations` (changes to specs).

## 10. `plan.delivery` (Observability & Monitoring)
*   `status`: `not_applicable` or `planned`.
    *   If `planned`: Define `dashboards` (with dashboard_id, nfr_refs) and `alerts` (with alert_id, nfr_ref, rule, severity).

## 11. `plan.docs` (Documentation Plan)
*   `status`: `not_applicable` or `planned`.
    *   If `not_applicable`: Provide `reason`.
    *   If `planned`: List `required_updates` with `path` and `update_summary`.

## 12. `plan.coverage_status` (Checklist Coverage Metrics)
*   `total`: Total checklist items.
*   `verified`: Count of verified items.
*   `deferred`: Count of deferred items.
*   `pending`: Count of pending items.

## 13. `plan.scope_validation` (Scope Acknowledgment)
*   `in_scope`: List of concerns IN scope.
*   `out_of_scope`: List of concerns OUT of scope.
*   `acknowledged`: Boolean, must be true if `out_of_scope` is non-empty.

# Heuristics For Completeness
1. **Every checklist item has a concrete `linked_test_expectation`** (not generic like "run tests").
2. **Every `spec_ref` has a valid 40-char SHA commit_hash** (no placeholders or zeros).
3. **`target_file_patterns` use explicit globs** (avoid `**/*` or empty arrays unless deferred).
4. **`docs_impact.status` is `required` if any non-doc file is in `target_file_patterns`**.
5. **Anchor (Step 16) does not conflict with Milestone contexts (16a/b/c)** (check for drift).

# Self-Audit Gate
Before emitting `spec/16_impl_context.json`, verify:
- [ ] All `spec_ref.commit_hash` values are valid 40-char SHAs (not `0000...`).
- [ ] Every checklist item with `checklist_status: active` has an `implementation` block.
- [ ] `target_file_patterns` are explicit (no `**/*` unless deferred).
- [ ] If `docs_impact.status` is `required`, `docs_touched` has at least one entry.
- [ ] If `plan.status` is `deferred`, `deferred_reason` is provided.
- [ ] No active Milestone Contexts (16a/b/c) conflict with this Anchor.

# Best Practices
1. **Always validate drift** between Step 16 Anchor and active 16a/b/c contexts before emit.
2. **Use specific test commands**, not vague placeholders (e.g., `pytest tests/auth/test_login.py::test_success`).
3. **Document EVERY environmental dependency** in `docs_impact` (env vars, secrets, config files).
4. **Prefer atomic checklist items** (one testable behavior per item, not compound requirements).
5. **Link evidence explicitly** when marking items as `verified` (use `evidence_ref` field).

# Quick Reference

| Field | Type | Required | Purpose |
|-------|------|----------|----------|
| `plan.summary` | object | yes | Scope definition (functional_summary, scope_in/out, target_file_patterns) |
| `plan.spec_alignment.checklist` | array | yes | Atomic requirements with spec_ref, linked_test_expectation, implementation |
| `plan.ambiguities` | array | no | Risk management (blocking/non_blocking issues) |
| `plan.solution` | object | no | Architecture sketch and sequence of concerns |
| `plan.context` | object | no | Existing codebase structures and coding examples |
| `plan.review_requirements` | object | no | Verification plan (test_commands, guidelines) |
| `plan.docs_impact` | object | yes | Documentation impact assessment |
| `plan.security` | object | no | Security fixtures and spec mutations |
| `plan.delivery` | object | no | Observability (dashboards, alerts) |
| `plan.drift` | object | no | Sustainment (periodic drift checks) |
| `plan.docs` | object | no | Documentation plan |
| `plan.coverage_status` | object | no | Metrics (total, verified, deferred, pending) |
| `plan.scope_validation` | object | no | Scope acknowledgment |

# Failure Modes (Pitfalls)
*   **Anchor Drift**: Producing a Step 16 context that conflicts with the specific Milestone contexts (16a/b/c). *Fix*: Anchor must be the union/root, not a distinct implementation plan.
*   **Lazy Scope**: Leaving `target_file_patterns` empty or using broad `**/*` patterns. *Fix*: Must be explicit glob patterns based on `spec/impl_context/*.json`.
*   **Hidden Dependencies**: Introducing code changes that require new env vars or secrets without documenting them in `docs_impact`. *Fix*: Check `env` usage.
*   **JSON dumps**: Dumping the JSON in the chat output. *Fix*: Only write the file.
*   **Schema Hallucination**: Using fields like `plan.tasks` (deprecated) or `metadata` (untyped). *Fix*: Strict adherence to Embedded Schema.

# Clarification Questions
- "Are there any active Milestone Contexts (16a/16b/16c) I should merge?"
- "Does this Step 16 Anchor require specific documentation updates beyond the standard set?"
- "Are there specific file patterns that should be strictly OUT of scope?"

# Embedded Schema
```json
{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://specdev.local/schema/16_impl_context.schema.json",
    "title": "16_impl_context",
    "description": "Unified artifact for the implementation loop (Plan -> Code -> Review). Enforces Checklist-Driven Implementation with evidence binding.",
    "type": "object",
    "additionalProperties": false,
    "$defs": {
        "specRef": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "fr",
                        "api",
                        "nfr",
                        "inv",
                        "fixture",
                        "doc",
                        "code"
                    ]
                },
                "id": {
                    "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                },
                "note": {
                    "type": "string"
                },
                "line_range": {
                    "type": "string",
                    "pattern": "^L\\d+-L\\d+$"
                },
                "commit_hash": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{40}$",
                    "not": {
                        "pattern": "^0{40}$"
                    }
                }
            },
            "required": [
                "type",
                "id",
                "line_range",
                "commit_hash"
            ]
        },
        "severityLevel": {
            "type": "string",
            "enum": [
                "low",
                "medium",
                "high",
                "critical"
            ]
        },
        "executionStatus": {
            "type": "string",
            "enum": [
                "passed",
                "failed",
                "blocked",
                "partial"
            ]
        },
        "evidenceObject": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "log",
                        "snippet",
                        "screenshot"
                    ]
                },
                "content": {
                    "type": "string",
                    "minLength": 20,
                    "pattern": "\\S"
                },
                "evidence_ref": {
                    "type": "string"
                }
            },
            "required": [
                "type",
                "content"
            ]
        }
    },
    "properties": {
        "id": {
            "$ref": "https://specdev.local/schema/core/atoms/1#kebabId",
            "description": "The Step ID from the Roadmap (e.g., step-api-core)."
        },
        "owner": {
            "$ref": "https://specdev.local/schema/core/atoms/1#owner"
        },
        "created_at": {
            "$ref": "https://specdev.local/schema/core/atoms/1#timestamp"
        },
        "seed_refs": {
            "$ref": "https://specdev.local/schema/core/collections/1#seedRefArray"
        },
        "extensions": {
            "type": "object",
            "description": "Structured extensions for domain-specific data.",
            "additionalProperties": false,
            "properties": {
                "review_state": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "outcome": {
                            "type": "string"
                        },
                        "verified_by": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "outcome"
                    ]
                },
                "execution_context": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "command_overrides": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        },
        "plan": {
            "type": "object",
            "additionalProperties": false,
            "description": "Trinity loop plan (scope, checklist, review requirements, and documentation impact).",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "active",
                        "deferred"
                    ]
                },
                "deferred_reason": {
                    "type": "string"
                },
                "summary": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "functional_summary": {
                            "type": "string"
                        },
                        "scope_in": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "scope_out": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "target_file_patterns": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Explicit list of files/directories to modify or create."
                        }
                    },
                    "required": [
                        "functional_summary",
                        "scope_in",
                        "scope_out",
                        "target_file_patterns"
                    ]
                },
                "docs_impact": {
                    "type": "object",
                    "additionalProperties": false,
                    "description": "Documentation impact assessment. Required when any non-doc file is modified.",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": [
                                "required",
                                "not_required"
                            ]
                        },
                        "rationale": {
                            "type": "string",
                            "minLength": 10
                        },
                        "docs_touched": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "status",
                        "rationale"
                    ],
                    "allOf": [
                        {
                            "if": {
                                "properties": {
                                    "status": {
                                        "const": "required"
                                    }
                                }
                            },
                            "then": {
                                "required": [
                                    "docs_touched"
                                ],
                                "properties": {
                                    "docs_touched": {
                                        "minItems": 1
                                    }
                                }
                            }
                        }
                    ]
                },
                "spec_alignment": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "requirements_summary": {
                            "type": "array",
                            "description": "Thematic grouping of requirements.",
                            "items": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "theme": {
                                        "type": "string"
                                    },
                                    "summary": {
                                        "type": "string"
                                    },
                                    "spec_refs": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/$defs/specRef"
                                        }
                                    }
                                },
                                "required": [
                                    "theme",
                                    "summary"
                                ]
                            }
                        },
                        "checklist": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "id": {
                                        "$ref": "https://specdev.local/schema/core/atoms/1#screamingSnakeId"
                                    },
                                    "spec_ref": {
                                        "$ref": "#/$defs/specRef"
                                    },
                                    "description": {
                                        "type": "string"
                                    },
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "behavior",
                                            "constraint",
                                            "validation",
                                            "metadata",
                                            "perf",
                                            "logging",
                                            "docs"
                                        ]
                                    },
                                    "layer": {
                                        "type": "string",
                                        "enum": [
                                            "db",
                                            "model",
                                            "service",
                                            "api",
                                            "integration",
                                            "tests",
                                            "docs",
                                            "config"
                                        ]
                                    },
                                    "checklist_status": {
                                        "type": "string",
                                        "enum": [
                                            "active",
                                            "deferred"
                                        ],
                                        "default": "active"
                                    },
                                    "linked_test_expectation": {
                                        "oneOf": [
                                            {
                                                "type": "string",
                                                "minLength": 1
                                            },
                                            {
                                                "type": "array",
                                                "minItems": 1,
                                                "items": {
                                                    "type": "string",
                                                    "minLength": 1
                                                }
                                            }
                                        ]
                                    },
                                    "implementation": {
                                        "type": "object",
                                        "description": "Atomic work definition for this specific requirement.",
                                        "additionalProperties": false,
                                        "properties": {
                                            "status": {
                                                "type": "string",
                                                "enum": [
                                                    "pending",
                                                    "in_progress",
                                                    "verified",
                                                    "deferred"
                                                ]
                                            },
                                            "files_touched": {
                                                "type": "array",
                                                "items": {
                                                    "type": "string"
                                                }
                                            },
                                            "actions": {
                                                "type": "array",
                                                "minItems": 1,
                                                "items": {
                                                    "type": "object",
                                                    "additionalProperties": false,
                                                    "properties": {
                                                        "type": {
                                                            "type": "string",
                                                            "enum": [
                                                                "file_create",
                                                                "file_edit",
                                                                "run_command",
                                                                "manual_verification"
                                                            ]
                                                        },
                                                        "description": {
                                                            "type": "string"
                                                        },
                                                        "target": {
                                                            "type": "string"
                                                        },
                                                        "command": {
                                                            "type": "string"
                                                        },
                                                        "evidence": {
                                                            "$ref": "#/$defs/evidenceObject"
                                                        }
                                                    },
                                                    "required": [
                                                        "type",
                                                        "description"
                                                    ],
                                                    "allOf": [
                                                        {
                                                            "if": {
                                                                "properties": {
                                                                    "type": {
                                                                        "enum": [
                                                                            "file_create",
                                                                            "file_edit"
                                                                        ]
                                                                    }
                                                                }
                                                            },
                                                            "then": {
                                                                "required": [
                                                                    "target"
                                                                ],
                                                                "properties": {
                                                                    "target": {
                                                                        "minLength": 1
                                                                    }
                                                                }
                                                            }
                                                        },
                                                        {
                                                            "if": {
                                                                "properties": {
                                                                    "type": {
                                                                        "const": "run_command"
                                                                    }
                                                                }
                                                            },
                                                            "then": {
                                                                "required": [
                                                                    "command"
                                                                ],
                                                                "properties": {
                                                                    "command": {
                                                                        "minLength": 1
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        },
                                        "required": [
                                            "status",
                                            "actions"
                                        ],
                                        "allOf": [
                                            {
                                                "if": {
                                                    "properties": {
                                                        "status": {
                                                            "const": "verified"
                                                        }
                                                    }
                                                },
                                                "then": {
                                                    "properties": {
                                                        "actions": {
                                                            "items": {
                                                                "required": [
                                                                    "evidence"
                                                                ]
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                },
                                "required": [
                                    "id",
                                    "spec_ref",
                                    "description",
                                    "linked_test_expectation"
                                ],
                                "allOf": [
                                    {
                                        "if": {
                                            "not": {
                                                "properties": {
                                                    "checklist_status": {
                                                        "const": "deferred"
                                                    }
                                                }
                                            }
                                        },
                                        "then": {
                                            "required": [
                                                "implementation"
                                            ]
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "required": [
                        "checklist"
                    ]
                },
                "ambiguities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "properties": {
                            "id": {
                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                            },
                            "description": {
                                "type": "string"
                            },
                            "source": {
                                "type": "string",
                                "enum": [
                                    "spec",
                                    "code",
                                    "plan",
                                    "mixed",
                                    "review"
                                ]
                            },
                            "severity": {
                                "type": "string",
                                "enum": [
                                    "blocking",
                                    "non_blocking"
                                ]
                            },
                            "impact": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "proposed_assumption": {
                                "type": "string"
                            },
                            "mitigation": {
                                "type": "string",
                                "minLength": 10
                            },
                            "status": {
                                "type": "string",
                                "enum": [
                                    "resolved",
                                    "tracking",
                                    "deferred",
                                    "blocked"
                                ]
                            }
                        },
                        "required": [
                            "id",
                            "description",
                            "severity"
                        ],
                        "allOf": [
                            {
                                "if": {
                                    "properties": {
                                        "severity": {
                                            "const": "non_blocking"
                                        }
                                    }
                                },
                                "then": {
                                    "required": [
                                        "mitigation"
                                    ]
                                }
                            }
                        ]
                    }
                },
                "solution": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "architecture_sketch": {
                            "type": "string"
                        },
                        "sequence_of_concerns": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "risks": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    },
                    "required": [
                        "architecture_sketch"
                    ]
                },
                "context": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "existing_structures": {
                            "type": "array",
                            "description": "Known code or non-code structures. Strings may reference non-code artifacts; objects must cite real code signatures.",
                            "items": {
                                "oneOf": [
                                    {
                                        "type": "string"
                                    },
                                    {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "signature": {
                                                "type": "string"
                                            },
                                            "source_file": {
                                                "type": "string",
                                                "pattern": "^[^/].*\\.(py|ts|js|go|rs)$"
                                            },
                                            "line_range": {
                                                "type": "string",
                                                "pattern": "^L\\d+-L\\d+$"
                                            }
                                        },
                                        "required": [
                                            "signature",
                                            "source_file"
                                        ]
                                    }
                                ]
                            }
                        },
                        "coding_examples": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "title": {
                                        "type": "string"
                                    },
                                    "description": {
                                        "type": "string"
                                    },
                                    "code": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "title",
                                    "code"
                                ]
                            }
                        }
                    }
                },
                "review_requirements": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "guidelines": {
                            "type": "string"
                        },
                        "test_commands": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {
                                        "type": "string",
                                        "minLength": 1
                                    },
                                    {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "command": {
                                                "type": "string",
                                                "minLength": 1
                                            },
                                            "expected_exit_code": {
                                                "type": "integer",
                                                "default": 0
                                            },
                                            "timeout_seconds": {
                                                "type": "integer",
                                                "minimum": 1,
                                                "maximum": 3600
                                            },
                                            "description": {
                                                "type": "string"
                                            }
                                        },
                                        "required": [
                                            "command"
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                    "required": [
                        "test_commands"
                    ]
                },
                "docs": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "not_applicable"
                                },
                                "reason": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "status",
                                "reason"
                            ]
                        },
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "planned"
                                },
                                "required_updates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "path": {
                                                "type": "string"
                                            },
                                            "update_summary": {
                                                "type": "string"
                                            }
                                        },
                                        "required": [
                                            "path",
                                            "update_summary"
                                        ]
                                    }
                                }
                            },
                            "required": [
                                "status",
                                "required_updates"
                            ]
                        }
                    ]
                },
                "security": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "not_applicable"
                                },
                                "reason": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "status",
                                "reason"
                            ]
                        },
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "planned"
                                },
                                "new_fixtures": {
                                    "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
                                },
                                "spec_mutations": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "ref": {
                                                "$ref": "https://specdev.local/schema/core/collections/1#traceRef"
                                            },
                                            "change": {
                                                "type": "string"
                                            },
                                            "reason": {
                                                "type": "string"
                                            }
                                        },
                                        "required": [
                                            "ref",
                                            "change",
                                            "reason"
                                        ]
                                    }
                                }
                            },
                            "required": [
                                "status"
                            ]
                        }
                    ]
                },
                "delivery": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "not_applicable"
                                },
                                "reason": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "status",
                                "reason"
                            ]
                        },
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "planned"
                                },
                                "dashboards": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "dashboard_id": {
                                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                            },
                                            "nfr_refs": {
                                                "$ref": "https://specdev.local/schema/core/collections/1#kebabIdArray"
                                            },
                                            "url": {
                                                "type": "string"
                                            }
                                        },
                                        "required": [
                                            "dashboard_id"
                                        ]
                                    }
                                },
                                "alerts": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "alert_id": {
                                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                            },
                                            "nfr_ref": {
                                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                            },
                                            "rule": {
                                                "type": "string"
                                            },
                                            "severity": {
                                                "$ref": "#/$defs/severityLevel"
                                            }
                                        },
                                        "required": [
                                            "alert_id",
                                            "rule"
                                        ]
                                    }
                                }
                            },
                            "required": [
                                "status"
                            ]
                        }
                    ]
                },
                "drift": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "not_applicable"
                                },
                                "reason": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "status",
                                "reason"
                            ]
                        },
                        {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                                "status": {
                                    "const": "planned"
                                },
                                "checks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": false,
                                        "properties": {
                                            "check_id": {
                                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                            },
                                            "target": {
                                                "type": "string",
                                                "enum": [
                                                    "api",
                                                    "schema",
                                                    "nfr",
                                                    "invariant",
                                                    "fixture",
                                                    "config"
                                                ]
                                            },
                                            "method": {
                                                "type": "string",
                                                "enum": [
                                                    "runtime-sample",
                                                    "log-diff",
                                                    "schema-diff",
                                                    "trace-replay"
                                                ]
                                            },
                                            "schedule": {
                                                "type": "string",
                                                "pattern": "^(hourly|daily|weekly|monthly|@(annually|monthly|weekly|daily|hourly)|([0-9*/,-]+ ){4}[0-9*/,-]+)$",
                                                "description": "Named interval (hourly/daily/weekly/monthly) or cron expression"
                                            },
                                            "severity": {
                                                "$ref": "#/$defs/severityLevel"
                                            },
                                            "remediation_policy": {
                                                "type": "string"
                                            }
                                        },
                                        "required": [
                                            "check_id",
                                            "target",
                                            "method"
                                        ]
                                    }
                                }
                            },
                            "required": [
                                "status"
                            ]
                        }
                    ]
                },
                "coverage_status": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "total": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "verified": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "deferred": {
                            "type": "integer",
                            "minimum": 0
                        },
                        "pending": {
                            "type": "integer",
                            "minimum": 0
                        }
                    },
                    "required": [
                        "total",
                        "verified",
                        "deferred",
                        "pending"
                    ]
                },
                "scope_validation": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "in_scope": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "out_of_scope": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "acknowledged": {
                            "type": "boolean"
                        }
                    },
                    "allOf": [
                        {
                            "if": {
                                "properties": {
                                    "out_of_scope": {
                                        "minItems": 1
                                    }
                                }
                            },
                            "then": {
                                "required": [
                                    "acknowledged"
                                ],
                                "properties": {
                                    "acknowledged": {
                                        "const": true
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "status": {
                                "const": "deferred"
                            }
                        }
                    },
                    "then": {
                        "required": [
                            "deferred_reason"
                        ],
                        "properties": {
                            "summary": {
                                "properties": {
                                    "target_file_patterns": {
                                        "maxItems": 0
                                    }
                                }
                            },
                            "review_requirements": {
                                "properties": {
                                    "test_commands": {
                                        "maxItems": 0
                                    }
                                }
                            }
                        }
                    },
                    "else": {
                        "properties": {
                            "summary": {
                                "properties": {
                                    "target_file_patterns": {
                                        "minItems": 1
                                    }
                                }
                            },
                            "review_requirements": {
                                "properties": {
                                    "test_commands": {
                                        "minItems": 1
                                    }
                                }
                            }
                        }
                    }
                }
            ]
        },
        "execution": {
            "type": "object",
            "description": "Global execution summary.",
            "additionalProperties": false,
            "properties": {
                "files_touched": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "execution_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "properties": {
                            "status": {
                                "$ref": "#/$defs/executionStatus"
                            },
                            "outcome_description": {
                                "type": "string"
                            },
                            "reasoning": {
                                "type": "string"
                            },
                            "command": {
                                "type": "string"
                            },
                            "evidence": {
                                "type": "string",
                                "minLength": 20
                            },
                            "evidence_ref": {
                                "type": "string"
                            },
                            "evidence_binding": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time"
                                    },
                                    "sha256": {
                                        "type": "string",
                                        "pattern": "^[a-f0-9]{64}$"
                                    },
                                    "exit_code": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 255
                                    },
                                    "command": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "timestamp",
                                    "sha256",
                                    "exit_code"
                                ]
                            }
                        },
                        "required": [
                            "status",
                            "outcome_description",
                            "reasoning",
                            "command",
                            "evidence"
                        ],
                        "allOf": [
                            {
                                "if": {
                                    "properties": {
                                        "status": {
                                            "const": "passed"
                                        }
                                    }
                                },
                                "then": {
                                    "required": [
                                        "evidence_ref",
                                        "evidence_binding"
                                    ],
                                    "properties": {
                                        "evidence": {
                                            "pattern": "(PASSED|passed|OK|SUCCESS|✓|0 (errors|failures?|failed)|\\d+ passed)"
                                        }
                                    }
                                }
                            }
                        ]
                    }
                },
                "critical_evidence": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "satisfied_checklist_ids": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "passed_test_commands": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    }
                },
                "config_validation": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "dashboard_links_valid": {
                            "type": "boolean"
                        },
                        "alert_rules_valid": {
                            "type": "boolean"
                        },
                        "drift_schedules_valid": {
                            "type": "boolean"
                        },
                        "notes": {
                            "type": "string"
                        }
                    }
                },
                "emergent_ambiguities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "properties": {
                            "id": {
                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                            },
                            "description": {
                                "type": "string"
                            },
                            "severity": {
                                "type": "string"
                            },
                            "impact": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "status": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "id",
                            "description",
                            "severity"
                        ]
                    }
                },
                "final_status": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "test_results": {
                            "type": "array",
                            "items": {
                                "type": "object"
                            }
                        },
                        "ci_status": {
                            "type": "string",
                            "enum": [
                                "green",
                                "red"
                            ]
                        }
                    }
                }
            }
        },
        "review": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "properties": {
                            "id": {
                                "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                            },
                            "type": {
                                "type": "string",
                                "enum": [
                                    "bug",
                                    "gap",
                                    "scope_creep",
                                    "style",
                                    "design",
                                    "tests",
                                    "docs"
                                ]
                            },
                            "severity": {
                                "type": "string",
                                "enum": [
                                    "blocking",
                                    "major",
                                    "minor",
                                    "nit"
                                ]
                            },
                            "spec_ref": {
                                "$ref": "#/$defs/specRef"
                            },
                            "description": {
                                "type": "string"
                            },
                            "related_checklist_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "remediation_task": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "task_id": {
                                        "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                    },
                                    "summary": {
                                        "type": "string"
                                    },
                                    "files_to_touch": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        }
                                    },
                                    "checklist_ids": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "required": [
                                    "task_id",
                                    "summary",
                                    "files_to_touch",
                                    "checklist_ids"
                                ]
                            },
                            "metadata": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "source": {
                                        "type": "string"
                                    },
                                    "impact": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "source",
                                    "impact"
                                ]
                            }
                        },
                        "required": [
                            "id",
                            "type",
                            "severity",
                            "spec_ref",
                            "description",
                            "metadata"
                        ],
                        "allOf": [
                            {
                                "if": {
                                    "properties": {
                                        "severity": {
                                            "enum": [
                                                "blocking",
                                                "major"
                                            ]
                                        }
                                    }
                                },
                                "then": {
                                    "required": [
                                        "remediation_task"
                                    ]
                                }
                            }
                        ]
                    }
                },
                "ratings": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "spec_completeness": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5
                        },
                        "code_quality": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5
                        },
                        "tests_completeness": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5
                        },
                        "docs_completeness": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5
                        },
                        "metadata_usage": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 5
                        }
                    },
                    "required": [
                        "spec_completeness",
                        "code_quality",
                        "tests_completeness",
                        "docs_completeness",
                        "metadata_usage"
                    ]
                },
                "verdict": {
                    "type": "string",
                    "enum": [
                        "verified",
                        "deferred",
                        "rejected"
                    ]
                },
                "next_actions": {
                    "type": "string"
                },
                "fixture_status": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "implemented_endpoints": {
                            "type": "array",
                            "items": {
                                "$ref": "https://specdev.local/schema/core/collections/1#traceId"
                            }
                        },
                        "test_results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "fixture_ref": {
                                        "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                    },
                                    "status": {
                                        "type": "string",
                                        "enum": [
                                            "pass",
                                            "fail",
                                            "skip"
                                        ]
                                    },
                                    "notes": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "fixture_ref",
                                    "status"
                                ]
                            }
                        },
                        "ci_status": {
                            "type": "string",
                            "enum": [
                                "green",
                                "red"
                            ]
                        }
                    },
                    "required": [
                        "implemented_endpoints",
                        "test_results",
                        "ci_status"
                    ]
                },
                "security_status": {
                    "type": "string",
                    "enum": [
                        "green",
                        "red"
                    ]
                },
                "delivery_status": {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                        "deployments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": false,
                                "properties": {
                                    "env": {
                                        "type": "string",
                                        "enum": [
                                            "dev",
                                            "staging",
                                            "prod"
                                        ]
                                    },
                                    "build_id": {
                                        "$ref": "https://specdev.local/schema/core/atoms/1#kebabId"
                                    },
                                    "status": {
                                        "type": "string",
                                        "enum": [
                                            "pending",
                                            "success",
                                            "failed"
                                        ]
                                    }
                                },
                                "required": [
                                    "env",
                                    "build_id"
                                ]
                            }
                        }
                    }
                }
            },
            "allOf": [
                {
                    "if": {
                        "required": [
                            "verdict"
                        ],
                        "properties": {
                            "verdict": {
                                "const": "verified"
                            }
                        }
                    },
                    "then": {
                        "required": [
                            "fixture_status"
                        ],
                        "properties": {
                            "fixture_status": {
                                "properties": {
                                    "ci_status": {
                                        "const": "green"
                                    }
                                },
                                "required": [
                                    "ci_status"
                                ]
                            }
                        }
                    }
                }
            ]
        }
    },
    "required": [
        "id",
        "owner",
        "created_at",
        "seed_refs",
        "plan"
    ]
}
```

# Output Contract
```json
{
  "id": "step-16-example",
  "owner": "system",
  "created_at": "2026-02-08T00:00:00Z",
  "seed_refs": [
    { "seed_id": "seed-overview", "path": "docs/seed/seed_overview.md" }
  ],
  "plan": {
    "status": "active",
    "summary": {
      "functional_summary": "Implement Core Authentication flow.",
      "scope_in": ["Login", "Logout", "Session Management"],
      "scope_out": ["OAuth", "MFA"],
      "target_file_patterns": ["src/auth/*.py", "tests/auth/*.py"]
    },
    "docs_impact": {
      "status": "required",
      "rationale": "New auth module requires API documentation updates.",
      "docs_touched": ["docs/api/auth.md"]
    },
    "spec_alignment": {
      "requirements_summary": [
        { "theme": "Security", "summary": "Implement JWT handling" }
      ],
      "checklist": [
        {
          "id": "CHK_AUTH_01",
          "spec_ref": {
            "type": "fr",
            "id": "fr-auth-login",
            "line_range": "L10-L20",
            "commit_hash": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4"
          },
          "description": "User can login with valid credentials.",
          "linked_test_expectation": "pytest tests/auth/test_login.py::test_login_success",
          "checklist_status": "active",
          "implementation": {
            "status": "pending",
            "files_touched": ["src/auth/login.py"],
            "actions": [
              {
                "type": "file_create",
                "description": "Create login handler",
                "target": "src/auth/login.py"
              }
            ]
          }
        }
      ]
    },
    "ambiguities": [
      {
        "id": "amb-token-storage",
        "description": "Token storage mechanism not specified (in-memory vs Redis)",
        "source": "spec",
        "severity": "non_blocking",
        "mitigation": "Default to in-memory for MVP, Redis for production",
        "impact": ["session-management"],
        "status": "resolved"
      }
    ],
    "solution": {
      "architecture_sketch": "Flask Blueprint with JWT extended.",
      "sequence_of_concerns": ["Models", "Views", "Tests"],
      "risks": ["Token leakage in logs"]
    },
    "context": {
      "existing_structures": [
         { "signature": "class User(db.Model)", "source_file": "src/models.py", "line_range": "L1-L50" }
      ]
    },
    "review_requirements": {
      "test_commands": ["pytest tests/auth"]
    },
    "security": {
      "status": "planned",
      "new_fixtures": ["fix-auth-token-leak"],
      "spec_mutations": [
        {
          "ref": { "type": "nfr", "id": "nfr-sec-01" },
          "change": "Add token rotation requirement",
          "reason": "Mitigate token replay attacks"
        }
      ]
    },
    "delivery": {
      "status": "not_applicable",
      "reason": "No observability changes required for initial implementation"
    },
    "drift": {
      "status": "planned",
      "checks": [
        {
          "check_id": "drift-auth-api",
          "target": "api",
          "method": "runtime-sample",
          "schedule": "daily",
          "remediation_policy": "Regenerate API fixtures from live endpoints"
        }
      ]
    }
  },
  "execution": {
    "files_touched": ["src/auth/login.py", "tests/auth/test_login.py"],
    "execution_results": [
      {
        "status": "passed",
        "outcome_description": "Login test passed with valid credentials",
        "reasoning": "Implemented JWT token generation and validation",
        "command": "pytest tests/auth/test_login.py::test_login_success",
        "evidence": "tests/auth/test_login.py::test_login_success PASSED",
        "evidence_ref": "artifacts/test_run_2026_02_08.log",
        "evidence_binding": {
          "timestamp": "2026-02-08T03:00:00Z",
          "sha256": "abc123def456...",
          "exit_code": 0,
          "command": "pytest tests/auth/test_login.py::test_login_success"
        }
      }
    ],
    "critical_evidence": {
      "satisfied_checklist_ids": ["CHK_AUTH_01"],
      "passed_test_commands": ["pytest tests/auth"]
    }
  },
  "review": {
    "findings": [
      {
        "id": "rev-auth-01",
        "type": "docs",
        "severity": "minor",
        "spec_ref": {
          "type": "doc",
          "id": "doc-api-auth",
          "line_range": "L1-L10",
          "commit_hash": "b1c2d3e4f5a67890b1c2d3e4f5a67890b1c2d3e4"
        },
        "description": "API documentation missing error response codes",
        "related_checklist_ids": ["CHK_AUTH_01"],
        "metadata": {
          "source": "reviewer",
          "impact": "Documentation completeness"
        }
      }
    ],
    "ratings": {
      "spec_completeness": 5,
      "code_quality": 5,
      "tests_completeness": 5,
      "docs_completeness": 4,
      "metadata_usage": 5
    },
    "verdict": "verified",
    "next_actions": "Update API documentation with error codes",
    "fixture_status": {
      "implemented_endpoints": ["POST /auth/login"],
      "test_results": [
        {
          "fixture_ref": "fix-auth-login-success",
          "status": "pass",
          "notes": "All assertions passed"
        }
      ],
      "ci_status": "green"
    }
  }
}
```
