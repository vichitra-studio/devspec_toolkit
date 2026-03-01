# specdev prompt-context - Step Dependency Query Tool

## Synopsis
`specdev prompt-context <step> [--repo-root PATH]`

## Overview
The `prompt-context` command queries the specification pipeline to identify all downstream consumers of a given step. This helps authors understand the impact scope of their work and avoid under-specifying key fields that downstream steps depend on.

## Usage

```bash
specdev prompt-context 04 --repo-root ./devspec_toolkit
```

**Output**: A markdown table with one row per downstream consumer, showing:
- Step ID and name

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
| Step | Name |
|------|------|
| 05 | Interface Contracts |
| 06 | Invariants |
| 07 | NFRs |
| 08 | Fixtures |
| 09 | Implementation Plan |
| 11 | Red Team |
| 13 | Extension Generator |
| 13a | Completeness Assessment |
| 14 | Roadmap |
| 15 | Scaffold |
| 16 | Impl Context |
| 16a | Impl Planner |
| 16c | Impl Reviewer |
```

## Error Handling

- **Unknown Step**: If the step ID does not exist in `tools/step_order.json`, the command exits with an error and lists valid step IDs.
- **Missing downstream_consumers**: If the step has no entries in the `downstream_consumers` field of `tools/step_order.json`, the command returns an empty table.

## See Also

- [`specdev align`](./align.md) — Toolkit alignment CLI for managing version migrations
- [`specdev schema-differ`](./schema_differ.md) — Library for detecting schema changes
- [Workflow Guides](../workflows/) — Using prompt-context results in spec authoring
