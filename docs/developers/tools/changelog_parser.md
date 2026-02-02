# Changelog Parser Reference

The `changelog_parser` module parses and validates YAML changelog files for the DevSpec Toolkit migration system.

## Installation

The parser is included in `specdev_tools`. Ensure the toolkit is installed:

```bash
pip install -e ./devspec_toolkit/tools
```

## CLI Usage

```bash
# List toolkit version and available changelogs
specdev changelog --list --repo-root ./devspec_toolkit

# Show details for a specific version
specdev changelog --version 0.1.0 --repo-root ./devspec_toolkit

# Validate a changelog file
specdev changelog --validate 0.1.0 --repo-root ./devspec_toolkit
```

## Python API

```python
from pathlib import Path
from specdev_tools.changelog_parser import (
    load_format,
    load_version,
    list_versions,
    compare_versions,
    get_changes_between,
    validate_changelog,
    get_toolkit_version,
)

changelog_dir = Path("devspec_toolkit/changelog")

# Load format schema
fmt = load_format(changelog_dir)
print(fmt.change_types)  # ['add_step', 'rename_step', ...]

# List versions
versions = list_versions(changelog_dir)  # ['0.1.0']

# Load a version
changelog = load_version(changelog_dir, "0.1.0")
print(f"Steps: {len(changelog.steps)}, Breaking: {changelog.breaking}")

# Compare versions
compare_versions("0.1.0", "0.2.0")  # Returns -1 (v1 < v2)

# Get changes between versions
changes = get_changes_between(changelog_dir, "0.1.0", "0.2.0")
```

## Data Structures

### VersionChangelog
```python
@dataclass
class VersionChangelog:
    version: str           # "0.1.0"
    release_date: str      # "2026-01-14"
    breaking: bool         # True if breaking changes
    description: str       # Release notes
    changes: List[ChangelogEntry]
    steps: List[StepInfo]
```

### ChangelogEntry
```python
@dataclass
class ChangelogEntry:
    type: str              # "add_step", "rename_field", etc.
    step_id: str           # "14_roadmap"
    path: str              # "milestones[].user_story" (for field changes)
    from_id: str           # For renames
    to_id: str             # For renames
    required: bool         # Is this a required field?
    migration: MigrationInfo
```

### Change Types

| Type | Description |
|------|-------------|
| `add_step` | New step added |
| `remove_step` | Step removed |
| `rename_step` | Step renumbered |
| `merge_steps` | Steps consolidated |
| `split_step` | Step decomposed |
| `add_field` | Field added to schema |
| `remove_field` | Field removed |
| `rename_field` | Field renamed |
| `change_type` | Field type changed |
| `add_constraint` | New validation |
| `paradigm_shift` | Format change (prose→JSON) |

## See Also

- [Migration System Spec](../design/migration_system_spec_v0.1.0.md)
- [CHANGELOG.md](../../../CHANGELOG.md)
- [changelog/format.yaml](../../../changelog/format.yaml)
