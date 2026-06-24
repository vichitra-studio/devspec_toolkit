## [unreleased]

### Changed

- Relaxed the `vc:core:canon` JSON Schema `entries.minItems` constraint from 1 to 0.
  `init_project.py` bootstraps `spec/canon/manifest.json` with `entries: []` before any
  `specdev canon-accept` has run (Step 03), so the prior `minItems: 1` caused `spec-check`
  and `canonical-integrity` to emit E520 `schema_invalid` on every new project until the
  canon was populated. New projects legitimately start with an empty project-canon registry.

- Extended the changelog format schema (`changelog/format.yaml`) `optional_fields` with
  `source_of_truth` and `render_target`, declaring the authoritative YAML source file and
  its rendered Markdown target. These keys are declared in `changelog/format.yaml`'s
  `optional_fields`, so the `ChangelogFormat` parser accepts them as optional top-level
  keys in versioned changelog files without consuming their values. YAML-to-Markdown
  parity between the two paths is a manual
  convention, not tool-enforced.

### Fixed

- Fixed the generated pre-commit hook configuration for macOS and submodule deployments.
  All hook entry points are now invoked via `devspec_env/bin/python` instead of the ambient
  `python`, ensuring the managed venv is always used. The `validate-all` hook has been renamed
  to `spec-check` (matching the current CLI command) and updated to pass `--spec-root ./spec`
  and `--git-root .` so project-canon resolution works correctly. The `seed-lint`,
  `canonical-integrity`, and `prompt-sync` hooks likewise receive `--spec-root`/`--git-root`
  where applicable.

- The generated `devspec-governance` commit-msg hook now sets `pass_filenames: true` (was
  `false`) so pre-commit passes the commit-message file path to `governance-check --message`,
  which previously received no message file.

- The generated host CI workflow (`init_project.py` `_render_ci_workflow`) now runs
  `spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` instead of
  `validate-all`, so project-canon resolves and new host repos no longer emit false E110s in
  CI (matching the pre-commit hook fix).

- Corrected submodule-deployment documentation and prompt-contract examples to pass the
  project-canon flags (`--spec-root ./spec --git-root .`) on spec-validating commands, and
  switched the CI-gates and scaffold prompt examples to `spec-check`. Bare invocations
  previously emitted false E110s when followed in a host repo.
