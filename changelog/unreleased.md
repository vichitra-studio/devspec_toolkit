## [unreleased]

### Fixed

- Relaxed the `vc:core:canon` JSON Schema `entries.minItems` constraint from 1 to 0.
  `init_project.py` bootstraps `spec/canon/manifest.json` with `entries: []` before any
  `specdev canon-accept` has run (Step 03), so the prior `minItems: 1` caused `spec-check`
  and `canonical-integrity` to emit E520 `schema_invalid` on every new project until the
  canon was populated. New projects legitimately start with an empty project-canon registry.

- Fixed the generated pre-commit hook configuration for macOS and submodule deployments.
  All hook entry points are now invoked via `devspec_env/bin/python` instead of the ambient
  `python`, ensuring the managed venv is always used. The `validate-all` hook has been renamed
  to `spec-check` (matching the current CLI command) and updated to pass `--spec-root ./spec`
  and `--git-root .` so project-canon resolution works correctly. The `seed-lint`,
  `canonical-integrity`, and `prompt-sync` hooks likewise receive `--spec-root`/`--git-root`
  where applicable.
