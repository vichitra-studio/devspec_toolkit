# Path Conventions

This document defines the canonical path variables used across the DevSpec Toolkit. These conventions apply to prompts, CLI commands, schema references, and CI pipelines.

## Variable Definitions

| Variable | Description | Typical Value |
|---|---|---|
| `$PRODUCT_ROOT` | Root of the consumer (host) repository | `/path/to/my-product/` |
| `$TOOLKIT_ROOT` | Root of the vendored devspec_toolkit | `$PRODUCT_ROOT/devspec_toolkit/` |
| `$SPEC_DIR` | Directory containing live spec artifacts | `$PRODUCT_ROOT/spec/` (consumer) or `$TOOLKIT_ROOT/spec` (toolkit itself) |
| `$SEED_DIR` | Directory containing seed documents | `$PRODUCT_ROOT/docs/seed/` |
| `$CANON_DIR` | Canonical registry directory | `$TOOLKIT_ROOT/canon/` |
| `$SCHEMA_DIR` | JSON Schema definitions | `$TOOLKIT_ROOT/schema/` |
| `$PROMPTS_DIR` | Deterministic prompt contracts | `$TOOLKIT_ROOT/prompts/` |

## Context-Specific Usage

### Prompt Context

Prompts reference spec inputs using paths relative to `$SPEC_DIR`:

- `spec/04_fr_list.json` — refers to `$SPEC_DIR/04_fr_list.json`
- `spec/common/seed_manifest.json` — refers to `$SPEC_DIR/common/seed_manifest.json`

### CLI Context

CLI commands accept `--repo-root` to resolve `$TOOLKIT_ROOT` and `--spec-dir` or positional `spec` to resolve `$SPEC_DIR`:

```bash
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
```

When running from the host repo, always pass `--repo-root ./devspec_toolkit` so the schema registry resolves correctly.

### Schema Context

Schema `$id` URIs use the `specdev.local` namespace and resolve via the schema registry:

- `https://specdev.local/schema/core/atoms/1` — resolves to `$SCHEMA_DIR/core/atoms.schema.json`
- `https://specdev.local/schema/04_fr_list/1` — resolves to `$SCHEMA_DIR/04_fr_list.schema.json`

The registry file at `$TOOLKIT_ROOT/tools/schema_registry.json` maps URIs to relative file paths.

## Dual-Root Convention

The toolkit supports two deployment modes:

1. **Consumer repo** (submodule): `$SPEC_DIR = $PRODUCT_ROOT/spec/`, `$TOOLKIT_ROOT = $PRODUCT_ROOT/devspec_toolkit/`
2. **Toolkit repo itself**: `$SPEC_DIR = $TOOLKIT_ROOT/spec`, `$TOOLKIT_ROOT = .`

The `spec_dir` scope lock (documented in [reference.md](reference.md#scope-lock-spec_dir)) ensures all commands use the same `$SPEC_DIR` to avoid path-assumption drift.
