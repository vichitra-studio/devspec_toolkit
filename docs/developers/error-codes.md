# Error Codes Reference

## Validation Error Codes

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

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
