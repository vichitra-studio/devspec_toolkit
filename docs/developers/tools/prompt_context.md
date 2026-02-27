# specdev prompt-context - Step Dependency Query Tool

## Synopsis
`specdev prompt-context <step> [--repo-root PATH]`

## Overview
The `prompt-context` command queries the specification pipeline to identify all downstream consumers of a given step and what each extracts from it. This helps authors understand the impact scope of their work and avoid under-specifying key fields that downstream steps depend on.

## Usage

```bash
specdev prompt-context 04 --repo-root ./devspec_toolkit
```

**Output**: A markdown table with one row per downstream consumer, showing:
- Step ID and name
- Extraction intent (what data is pulled from the upstream step)

## Arguments

### `<step>` (required)
The step ID to query. Use either the numeric form (`04`) or full name form (`04_fr_list`). Examples:
- `00` — Project Charter
- `04` — Functional Requirements
- `16c` — Implementation Review

### `--repo-root PATH` (optional)
Path to the DevSpec Toolkit root directory. Defaults to current directory. Used to locate `tools/step_order.json` and validate step metadata.

## Example

Query downstream consumers of step 04 (Functional Requirements):

```bash
$ specdev prompt-context 04 --repo-root ./devspec_toolkit
```

**Output:**

```
| Step | Name | Extraction Intent |
|------|------|-------------------|
| 05 | Interface Contracts | Maps each FR to its API surface (one api_ref per FR) |
| 06 | Invariants | Identifies system constraints and data boundaries referenced by FRs |
| 07 | Non-Functional Requirements | Binds NFR targets to FR capabilities via capability_ref |
| 08 | Fixtures | Creates test cases for each FR acceptance_criteria item |
| 09 | Implementation Plan | Decomposes FR acceptance_criteria into implementation tasks |
| 11 | Red Team | Audits FR completeness and acceptance_criteria robustness |
| 13 | Extension Generator | Uses FR statements to generate new capabilities |
| 13a | Completeness Assessment | Verifies all capability_refs are met by FRs |
| 14 | Roadmap | Maps FRs to milestone_ref for delivery sequencing |
| 15 | Scaffold | Translates FR acceptance_criteria into test cases |
| 16 | Implementation Context | Uses FR trace for cross-referencing implementation work |
| 16a | Implementation Planner | Binds FRs to implementation checklist items |
| 16c | Implementation Reviewer | Verifies each FR acceptance_criteria item is covered |
```

## Error Handling

- **Unknown Step**: If the step ID does not exist in `tools/step_order.json`, the command exits with an error and lists valid step IDs.
- **Missing step_metadata**: If the step lacks upstream extraction metadata, the command warns that information is incomplete.

## See Also

- [`specdev align`](./align.md) — Toolkit alignment CLI for managing version migrations
- [`specdev schema-differ`](./schema_differ.md) — Library for detecting schema changes
- [Workflow Guides](../workflows/) — Using prompt-context results in spec authoring
