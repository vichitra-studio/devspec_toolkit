# Toolkit Update Checklist

Standard operating procedure for changes to the DevSpec Toolkit. Follow the applicable section(s) based on what changed.

## Schema Change Workflow

1. [ ] Update the JSON Schema file in `schema/`
2. [ ] Update the corresponding prompt in `prompts/`
3. [ ] Run `specdev prompt-sync` to verify prompt ↔ schema alignment
4. [ ] Update step validator if logic changed (`tools/specdev_tools/validation/validators/step_NN.py`)
5. [ ] Add/update test fixtures in `tests/fixtures/step_NN/`
6. [ ] Run `pytest tests/ -v` — all tests pass
7. [ ] Add changelog entry: create `changelog/vX.Y.Z.yaml` (machine) + `changelog/vX.Y.Z.md` (human) directly (no unreleased staging)

## Prompt Change Workflow

1. [ ] Edit the prompt file in `prompts/prompt_NN_*.md`
2. [ ] Run `specdev prompt-sync` to verify alignment with schema
3. [ ] Update `docs/agents/manifest.json` if agent protocol changed
4. [ ] Run `pytest tests/test_prompt_contracts.py -v`
5. [ ] Test the prompt with an AI assistant to verify output quality

## Canonical Registry Change Workflow

1. [ ] Update `canon/manifest.json` or the relevant `canon/kinds/*/` file
2. [ ] Run `specdev canonical-lint canon --repo-root .` — no errors
3. [ ] Run `specdev canonical-integrity spec --repo-root .` — all refs valid
4. [ ] If aliases changed: update `canon/aliases.json`
5. [ ] Run full test suite: `pytest tests/ -v`

## Migration Template Change Workflow

1. [ ] Edit or create template in `prompts/migration/`
2. [ ] Ensure all `{{VARIABLE}}` placeholders are documented
3. [ ] Add/update test in `tests/test_migration_templates.py`
4. [ ] Run `pytest tests/test_migration_templates.py -v`

## Release Checklist

1. [ ] All items from applicable workflow checklists above are complete
2. [ ] Create `changelog/vX.Y.Z.md` (human-readable release notes)
3. [ ] Create `changelog/vX.Y.Z.yaml` (machine-readable changelog entry)
4. [ ] Add new version to `CHANGELOG.md` version index table
5. [ ] Bump `version` in `tools/pyproject.toml` to `X.Y.Z`
6. [ ] Verify `CLAUDE.md` still points to `tools/pyproject.toml` for version (no hardcoded version to update)
7. [ ] Run `specdev changelog --validate X.Y.Z --repo-root .` — no errors
8. [ ] Run full test suite: `pytest tests/ -v`
9. [ ] Commit: `git commit -m "chore(release): vX.Y.Z"`
10. [ ] Tag and release: `git tag vX.Y.Z` then create a GitHub Release with release notes = the changelog entry for that version (`changelog/vX.Y.Z.md`)
