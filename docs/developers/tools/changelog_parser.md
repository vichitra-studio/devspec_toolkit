# Changelog Parser Reference

The `changelog_parser` module parses and validates YAML changelog files for the DevSpec Toolkit migration system.

## Installation

The parser is included in `specdev_tools`. Ensure the toolkit is installed:

```bash
uv pip install -e ./devspec_toolkit/tools
```

## CLI Usage

```bash
# List toolkit version and available changelogs
specdev changelog --list --repo-root ./devspec_toolkit

# Show details for a specific version
specdev changelog --version 0.1.0 --repo-root ./devspec_toolkit

# Validate a changelog file ("unreleased" is a version too); prints OK or the errors, exit 1 on an error
specdev changelog --validate 0.1.0 --repo-root ./devspec_toolkit
specdev changelog --validate unreleased --repo-root ./devspec_toolkit
```

## Python API

```python
from pathlib import Path
from specdev_tools.core.changelog_parser import (
    load_format,
    load_version,
    list_versions,
    compare_versions,
    get_changes_between,
    validate_changelog,
    get_toolkit_version,
)
from specdev_tools.migration.registry import discover_scripts

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

# Validate; pass the ids of the registered migration scripts to check that a named script exists
errors = validate_changelog(changelog_dir, "1.2.0", known_scripts={s.id for s in discover_scripts()})
```

## Data Structures

### VersionChangelog
```python
@dataclass
class VersionChangelog:
    version: str           # "0.1.0"
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

### MigrationInfo
```python
@dataclass
class MigrationInfo:
    action: str                    # "auto", "ai_assisted", "merge", "archive"
    script: Optional[str] = None   # id of the migration script that performs an `auto` entry
    kind: Optional[str] = None     # "mechanical", "judgement" or "none"
    prompt: Optional[str] = None
    operations: List[str] = field(default_factory=list)
    source: Optional[str] = None
    target: Optional[str] = None
    context_sources: List[str] = field(default_factory=list)
```

`script` is the module name of a migration script under `migration/scripts/` (for example `p3_convert`); the runner finds the scripts of a release by the folder they live in (`v1_2_0/`), and the changelog entry tells a reader which sentence belongs to which script. `kind` says what the entry does to host data: `mechanical` (a script edits it), `judgement` (a person or an agent must decide; the script only lists items) or `none` (a toolkit-internal note). The allowed values are `migration_kinds` in `changelog/format.yaml`; any other value is `E520`.

### Validation: E884

`validate_changelog(changelog_dir, version, known_scripts=None)` returns the format errors and, for each entry of a version above 1.1.1 (and of `unreleased`) whose migration is `action: auto` with `kind: mechanical`, **E884** when the entry names no `script`, or, when `known_scripts` is given (the CLI passes the registered ids), names one that no module defines. An entry with another kind or action is never asked for a script. Versions up to 1.1.1 are exempt, because a released changelog is not edited. The module imports nothing from `migration/`: the caller supplies the ids. See [E884](../error-codes.md#e884-migration_changelog_script_missing) and `specdev guide E884`.

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
| `add_module`, `add_config`, `change_config`, `change_schema`, `add_definition`, `add_script`, `remove_validator`, `fix`, `internal_restructure` | Descriptions of what a release changed in the tools and schemas; `add_script` is a migration script |

## See Also

- [Migration System Spec](../design/migration_system_spec.md)
- [CHANGELOG.md](../../../CHANGELOG.md)
- [changelog/format.yaml](../../../changelog/format.yaml)
