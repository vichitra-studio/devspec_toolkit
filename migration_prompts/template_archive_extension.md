# Migration: Archive Project Extension

## Purpose

Move a project-specific extension spec file to the archive directory. This occurs when the toolkit doesn't recognize a custom extension (files matching `13[a-z]_*.json`), and they should be preserved but moved out of the active spec directory.

The goal is **safe preservation**: the extension file is moved to the archive with full content intact, ready for manual review and potential reintegration.

## Context

- Source Version: {{SOURCE_VERSION}}
- Target Version: {{TARGET_VERSION}}
- Extension File: `{{SOURCE_FILE}}`
- Archive Location: `{{ARCHIVE_PATH}}`
- Operation: Archive Extension

## Source Data

The following is the project extension file to be archived:

```json
{{SOURCE_CONTENT}}
```

## Why Archive?

This file is being archived because:
- It uses a project-specific schema (`13[a-z]_*.json` pattern)
- The toolkit doesn't have a corresponding schema for validation
- It may contain valuable project-specific data that shouldn't be deleted

## Archive Process

### What Happens

1. The original file is copied to `spec/archive/{{FILENAME}}`
2. A metadata wrapper is added documenting the archival
3. The file is removed from the main `spec/` directory
4. The file can be restored later if needed

### Archived File Format

The archived file should include:
1. Original content unchanged
2. Archive metadata in `_archive_info`

## Transformation Rules

### Rule 1: Preserve Complete Content
- The entire original JSON must be preserved exactly
- Do not modify any fields or values
- Do not attempt to validate against any schema

### Rule 2: Add Archive Metadata
Add an `_archive_info` object with:
- `archived_at`: ISO timestamp
- `from_version`: Source toolkit version
- `to_version`: Target toolkit version
- `reason`: Why it was archived
- `restore_instructions`: How to restore if needed

### Rule 3: Maintain Readability
- Keep the JSON well-formatted
- Place `_archive_info` at the end of the root object

## Handling Edge Cases

### If the file has existing `_archive_info`:
This file was previously archived. Merge the new archive info, keeping history.

### If the file has validation errors:
Archive it anyway. The point is preservation, not validation.

### If the file references other specs:
Note these dependencies in `_archive_info.dependencies` for future restoration.

## Self-Audit Gate

Before returning your output, you MUST verify each item:

- [ ] **Complete**: All original content is preserved
- [ ] **Unmodified**: No changes to original data (except adding metadata)
- [ ] **Documented**: `_archive_info` explains the archival
- [ ] **Valid JSON**: Output parses as valid JSON

## Output Contract

Write the final JSON artifact directly to disk at the step path under `spec/` (or runner-provided path).

The JSON must:
1. Be valid, parseable JSON
2. Contain ALL original content unchanged
3. Include `_archive_info` metadata

```json
{
  // All original content exactly as-is...
  
  "_archive_info": {
    "archived_at": "{{TIMESTAMP}}",
    "from_version": "{{SOURCE_VERSION}}",
    "to_version": "{{TARGET_VERSION}}",
    "reason": "Project extension not recognized by toolkit v{{TARGET_VERSION}}",
    "original_path": "spec/{{SOURCE_FILE}}",
    "restore_instructions": "Copy this file back to spec/ and remove _archive_info if reintegrating"
  }
}
```
