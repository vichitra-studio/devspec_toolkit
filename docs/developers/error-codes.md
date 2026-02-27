# Error Codes Reference

## Validation Error Codes

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

### E561 / W561 UNCOVERED_FR

**Trigger**: A functional requirement defined in step 04 is not assigned to any milestone in step 14 (`fr_refs`).

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`, or document why the FR is intentionally unscheduled.

### E562 / W562 ORPHAN_MILESTONE

**Trigger**: A milestone in step 14 is not referenced by any checklist item in step 16a.

**Resolution**: Either add FR references to the milestone or add checklist items that reference the milestone's tasks.

### E563 / W563 CHECKLIST_ROADMAP_MISMATCH

**Trigger**: A roadmap task exists in step 14 but has no corresponding checklist item in step 16a.

**Resolution**: Create a checklist item with `spec_ref.id` matching the roadmap `task_id`, or mark the task as deferred.

### E582 MILESTONE_REF_MISMATCH

**Trigger**: A checklist item's `milestone_ref` does not match the milestone that owns its `spec_ref.id` task in step 14.

**Resolution**: Update the checklist item's `milestone_ref` to match the milestone containing the referenced roadmap task.

### W140 SEED_CONTENT_OVERLAP_LOW

**Trigger**: A spec artifact declares a `seed_ref` but shares fewer than 3 content tokens with the referenced seed document.

**Resolution**: Either use content from the referenced seed in the artifact or remove the unused `seed_ref`.

### W581 MILESTONE_REF_MISSING

**Trigger**: A non-deferred checklist item in step 16 lacks a `milestone_ref` field binding it to a step 14 milestone.

**Resolution**: Add a `milestone_ref` field to the checklist item with the `milestone_id` from step 14 that owns the referenced task.

## Exception Classes

### SubmoduleDetectionError

**Module**: `specdev_tools.core.errors`

**Raised when**: The toolkit cannot detect the git root in a submodule deployment.

**Common triggers**:
- Running from a detached HEAD state in the submodule
- `--repo-root` pointing to the wrong directory

**Resolution**: Pass `--git-root` pointing to the host repo's git root, and `--spec-root` pointing to the spec directory.

### SchemaRegistryError

**Module**: `specdev_tools.core.errors`

**Raised when**: A schema URI cannot be resolved from `tools/schema_registry.json`.

**Common triggers**:
- Missing entry in `tools/schema_registry.json`
- `--repo-root` not pointing to the toolkit directory
- Schema file referenced in the registry doesn't exist on disk

**Resolution**: Check `tools/schema_registry.json` for the expected URI mapping and verify `--repo-root` points to the devspec_toolkit directory.
