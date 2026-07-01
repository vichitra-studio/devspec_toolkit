## [unreleased]

### Added

- Added W555 `STEP00_SEED_OUT_OF_SCOPE_THIN` to `seed_lint.py`: fires when seeds routed
  to step "00" supply fewer than 3 substantive out-of-scope items combined. The Step 00
  charter schema requires `out_of_scope minItems:3`; without this warning, thin seeds
  cause authors to hit a gate failure or hallucinate content at authoring time. W555 is
  warn-only and non-promotable (E555 is the distinct `SEMANTIC_COVERAGE_REGRESSION` code).

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

### Removed

- Removed the `/specdev-trinity-plan` skill; its plan-phase functionality is now invoked via
  `/specdev-trinity --phase plan`. Host repos that vendor the toolkit as a git submodule must
  re-run project init (`init_project.py`) after bumping to this version to refresh the now-stale
  `specdev-trinity-plan` skill symlink. No spec-artifact migration is required.

### Added

- Added a new script `.claude/skills/devspec_pr_audit/scripts/p6_verify.py`, which reads
  a `fix_plan.json` and executes each task's `acceptance_command` in topological order,
  reporting PASS/FAIL per task as the post-fix verification gate. Also extended
  `SKILL.md` and `protocol.md` with the `--post-fix` scoped-audit contract
  (DEVSPEC-121). `validate_agent_outputs.py`'s scope is unchanged by this work; it
  continues to validate only the standard P0-P5 pipeline artifacts (`findings.json`,
  `fix_plan.json`, p2/p3 fragments, `manifest.json`).

### Changed

- Added an "Agentified flow note" to `prompts/prompt_16c_impl_reviewer.md` clarifying
  that when the Trinity loop is invoked via `/specdev-trinity --phase review`, the
  anchor/roadmap sync is performed by `.claude/skills/specdev-trinity/SKILL.md`'s
  post-convergence Step C3 (operator gate) -- not by this prompt directly -- whereas
  the standalone (non-agentified) invocation path continues to perform anchor/roadmap
  sync inline per the prompt's own Crucial Side Effect section.

### Internal

- Rewrote 11 `.claude/agents/*.md` agent-contract files across the DEVSPEC-100 fix arc:
  Phase 1 (WI-1..WI-8: `pr-audit-discovery-mechanical`, `pr-audit-discovery-semantic` via
  Wave B1, `specdev-reviewer`, `specdev-scope`, and initial passes on `specdev-impl`,
  `specdev-trinity-reviewer`), Phase 2 (IU-11 `pr-audit-context-author` bin-packing,
  IU-12 `pr-audit-fix-apply` post-fix automation, Wave B1 `pr-audit-context-verifier`),
  Phase 3 (IU-17 `specdev-trinity-impl` `errors_remaining`, IU-18 `pr-audit-cross-boundary`
  p2/-absent meta-finding, IU-20 `specdev-impl` author-extend mode), and follow-up F-1b
  (`specdev-trinity-reviewer` FR-coverage gate fix). Added corresponding test coverage:
  `tests/integration/pr_audit/test_p5_finalize.py`, `test_tier0_checks.py`,
  `test_validate_agent_outputs.py`, and `tests/unit/test_wi8_green_derivation.py`.
