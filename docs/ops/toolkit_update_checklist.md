# Toolkit Update Checklist

Standard operating procedure for changes to the DevSpec Toolkit. Follow the applicable section(s) based on what changed.

## Schema Change Workflow

1. [ ] Update the JSON Schema file in `schema/`
2. [ ] Update the corresponding prompt in `prompts/`
3. [ ] Run `specdev prompt-sync` to verify prompt ↔ schema alignment
4. [ ] Update step validator if logic changed (`tools/specdev_tools/validation/validators/step_NN.py`)
5. [ ] Add/update test fixtures in `tests/fixtures/step_NN/`
6. [ ] Run `pytest tests/ -v` — all tests pass
7. [ ] Add changelog entry: `changelog/unreleased.yaml` (machine) + `changelog/unreleased.md` (human)

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
2. [ ] Rename `changelog/unreleased.md` → `changelog/vX.Y.Z.md`
3. [ ] Rename `changelog/unreleased.yaml` → `changelog/vX.Y.Z.yaml`
4. [ ] Update version in `tools/pyproject.toml`
5. [ ] Update version in `CLAUDE.md`
6. [ ] Update version in `docs/developers/getting_started.md`
7. [ ] Add new version to `CHANGELOG.md` version index table
8. [ ] Run full test suite: `pytest tests/ -v`
9. [ ] Commit and tag: `git tag vX.Y.Z`
