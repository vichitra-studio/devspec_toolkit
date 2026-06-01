## [Unreleased]

### Added

**CLI**
- `specdev update <spec_dir> --repo-root <toolkit>` — primary post-submodule-bump
  entry point. Re-stamps `spec/specdev_version` instantly when no structural schema
  changes are present; directs through the `specdev align` flow
  (`apply --auto` → optionally `prompts` → `validate`) when schema migration is
  required, exiting 1 so CI catches un-migrated specs. Supports `--dry-run` and
  `--json` output modes. (DEVSPEC-87)

### Changed

- `spec_check` E608 messages now direct users to `specdev update` instead of
  `specdev align` directly. (DEVSPEC-87)
- `stamp_specdev_version` extracted from `validate_post_migration` into
  `schema_differ.py` as a shared helper. Plain re-stamps (`is_migration=False`)
  preserve `last_migration` and never add a `migration_history` entry; migration
  stamps (`is_migration=True`, called only by `align validate`) append a history
  entry and update `last_migration`. (DEVSPEC-87)
