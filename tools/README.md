# AI Spec Driven Development CLI (v3 Full)

Deterministic, schema-first utilities for the AI Spec Driven Development Toolkit.

## Install
The recommended way to install is via the **Project Initialization** script (see below), which handles virtualenv creation and dependency installation automatically.

If you are setting up manually or restoring an existing environment:

1. Follow the canonical setup in [`docs/developers/getting_started.md`](../docs/developers/getting_started.md#1-set-up-your-environment).
2. Or use the helper script locally:
   ```bash
   ./devspec_toolkit/scripts/setup_devspec_env.sh
   source dev_env/bin/activate
   ```

After initialization, the toolkit also generates `./tools/run_specdev.sh` in your host repo. This wrapper enforces virtualenv usage and is the canonical entrypoint for all CLI commands, even if you have not activated `dev_env` in your current shell.


## Project Initialization
To bootstrap a new project with the toolkit, use the initialization utility:

```bash
python3 devspec_toolkit/scripts/init_project.py --target /path/to/project --strict
```

### Arguments
- `--target`: Directory to initialize (defaults to current directory).
- `--strict`: Enable strict governance mode (installs `commit-msg` hooks and enforces message format).
- `--toolkit-url`: Custom URL for the submodule (defaults to `vichitracollective/devspec_toolkit`).

This utility standardizes directory creation (`spec/`, `spec/common/`, `docs/seed/`), submodule addition, and environment setup (`dev_env` with pre-commit hooks).

---

## What is **toolkit root**?

The toolkit root is the directory that contains this submodule (for example, `./devspec_toolkit`). For the canonical directory map, see [Toolkit Layout](../README.md#toolkit-layout).

The CLI resolves `$schema` URIs via [tools/schema_registry.json](schema_registry.json). When you run commands from your product repository, pass `--repo-root <toolkit-root>` so those paths resolve correctly.

Examples (assuming `./devspec_toolkit`):

- Host repo root:
  ```bash
  ./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
  ```
- Inside the toolkit directory:
  ```bash
  ../tools/run_specdev.sh validate ../spec/00_charter.json --repo-root .
  ```
- Arbitrary location:
  ```bash
  /abs/path/tools/run_specdev.sh validate /abs/path/spec/00_charter.json --repo-root /abs/path/devspec_toolkit
  ```

If you vend the toolkit elsewhere, substitute that path in the commands above and below.

---

## CLI Overview

The CLI exposes subcommands such as `validate`, `validate-all`, `matrix`, `fixtures-lint`, `seed-lint`, `docs-lint`, `invariants-check`, `governance-check`, `spec-quality-lint`, `hallucination-lint`, `canonical-lint`, `canonical-integrity`, `dependency-order-lint`, and `forward-replay-check`. The canonical usage examples and options are maintained in [`docs/developers/reference.md`](../docs/developers/reference.md#core-validation-commands); this README intentionally avoids duplicating that content.

From any location, run:
```bash
./tools/run_specdev.sh --help
```

Pass `--repo-root <toolkit-root>` whenever you execute commands from outside the toolkit directory so schema resolution goes through [tools/schema_registry.json](schema_registry.json).

### Completeness assessment (Step 13a)
After running `prompts/prompt_13a_completeness_assessment.md`, validate the resulting `spec/13a_completeness_assessment.json` the same way as any other artifact:

```bash
./tools/run_specdev.sh validate spec/13a_completeness_assessment.json --repo-root ./devspec_toolkit
```

---

## Schema Resolution

- Artifacts embed `$schema` URIs (for example `https://specdev.local/schema/04_fr_list.schema.json`).
- The CLI maps each URI using `tools/schema_registry.json` relative to the toolkit root.
- After moving or versioning schema files, update the registry to keep validation deterministic.

---

## CI Integration

Generate a starter workflow using the yaml template in prompts, or see [docs/developers/reference.md#validation-workflow](../docs/developers/reference.md#validation-workflow) for the authoritative list of validation commands enforced in CI.

In strict mode, quality and hallucination checks are blocking (`spec-quality-lint`, `hallucination-lint`) alongside canonical and replay integrity gates.

---

## FAQ

- **Do I always need `--repo-root`?** Inside the toolkit directory it defaults correctly; elsewhere pass the toolkit path explicitly.
- **Can I vendor the toolkit elsewhere?** Yes—use the same flag (and update any generated workflow paths) to point to the new location.
