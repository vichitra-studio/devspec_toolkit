# AI Spec Driven Development CLI (v3 Full)

Deterministic, schema-first utilities for the AI Spec Driven Development Toolkit.

## Install

Follow the environment setup in [`docs/developers/getting_started.md`](../docs/developers/getting_started.md#1-set-up-your-environment). Those instructions are the canonical source for creating the virtualenv, installing requirements, and exporting `PYTHONPATH`.

---

## What is **toolkit root**?

The toolkit root is the directory that contains this submodule (for example, `./devspec_toolkit`). For the canonical directory map, see [Toolkit Layout](../README.md#toolkit-layout).

The CLI resolves `$schema` URIs via `tools/schema_registry.json`. When you run commands from your product repository, pass `--repo-root <toolkit-root>` so those paths resolve correctly.

Examples (assuming `./devspec_toolkit`):

- Host repo root:
  ```bash
  python -m specdev_tools.cli validate spec/00_charter.json --repo-root ./devspec_toolkit
  ```
- Inside the toolkit directory:
  ```bash
  python -m specdev_tools.cli validate ../spec/00_charter.json --repo-root .
  ```
- Arbitrary location:
  ```bash
  python -m specdev_tools.cli validate /abs/path/spec/00_charter.json --repo-root /abs/path/devspec_toolkit
  ```

If you vend the toolkit elsewhere, substitute that path in the commands above and below.

---

## CLI Overview

The CLI exposes subcommands such as `validate`, `validate-all`, `matrix`, `fixtures-lint`, `gen-ci`, and `scaffold`. The canonical usage examples and options are maintained in [`docs/developers/reference.md`](../docs/developers/reference.md#core-validation-commands); this README intentionally avoids duplicating that content.

From any location, run:
```bash
python -m specdev_tools.cli --help
```

Pass `--repo-root <toolkit-root>` whenever you execute commands from outside the toolkit directory so schema resolution goes through `tools/schema_registry.json`.

---

## Schema Resolution

- Artifacts embed `$schema` URIs (for example `https://specdev.local/schema/04_fr_list.schema.json`).
- The CLI maps each URI using `tools/schema_registry.json` relative to the toolkit root.
- After moving or versioning schema files, update the registry to keep validation deterministic.

---

## CI Integration

Generate a starter workflow with `python -m specdev_tools.cli gen-ci …` and extend it with your own jobs. For the authoritative list of validation commands enforced in CI, see `docs/developers/reference.md#validation-workflow`.

---

## FAQ

- **Do I always need `--repo-root`?** Inside the toolkit directory it defaults correctly; elsewhere pass the toolkit path explicitly.
- **Can I vendor the toolkit elsewhere?** Yes—use the same flag (and update any generated workflow paths) to point to the new location.
