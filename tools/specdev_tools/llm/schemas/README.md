# LLM Response Schemas

JSON Schema (draft 2020-12) files for validating LLM responses within the `specdev llm *` loop machinery.

| Schema file | Template | Loop | Protocol section |
|---|---|---|---|
| `pointer_response.schema.json` | `inner_plan.md`, `inner_repair.md`, `widen_semantic.md` | `inner`, `widen` | §6.1 (pointer-only emission; no content) |
| `edit_response.schema.json` | `outer_edit.md` | `outer-edit` | §6.2 (edit proposal: jq_path + value + rationale) |
| `remediation_response.schema.json` | `outer_remediate.md` | `outer-remediate` | §6.3 (remediation plan: specdev commands + rationale) |
| `bundle_response.schema.json` | *(CLI return — not a template)* | *(bundle assembler)* | §6.1 (bundle return envelope) |

All schemas live under `devspec_toolkit/tools/specdev_tools/llm/schemas/`.
Protocol contract: `devspec_toolkit/docs/agents/llm_protocol.md`.
