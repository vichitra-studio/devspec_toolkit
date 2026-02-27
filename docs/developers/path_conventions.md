# Path Conventions

## Submodule Path Resolution

When the toolkit is vendored as a git submodule at `<host-repo>/devspec_toolkit/`, three distinct directory roots come into play:

| Root | Points to | Used for |
|------|-----------|----------|
| `--repo-root` | `devspec_toolkit/` | Schema registry, step_order.json, canon/ |
| `--spec-root` | `<host-repo>/spec/` | Spec artifact discovery, step existence checks |
| `--git-root` | `<host-repo>/` | Git diff operations, forward replay checks |

### Why This Matters

In a submodule deployment, `git diff` must run from the host repo's git root, not from the submodule directory (which is typically in detached HEAD state). Similarly, spec files live in the host repo's `spec/` directory, not inside the toolkit.

### Resolution Order

Without explicit flags, the toolkit auto-detects:
1. `git_root`: Runs `git rev-parse --show-toplevel` from `repo_root`
2. `spec_root`: Falls back to `repo_root/spec`

### Base Ref Resolution (for forward-replay)

The base ref for diff comparison is resolved in this order:
1. `SPECDEV_REPLAY_BASE_REF` environment variable
2. Current branch's upstream tracking branch (`@{upstream}`)
3. `origin/main` → `origin/master` → `main` → `master`
4. Current branch name (self-diff)
5. Fallback: `origin/main`

---

# Path Conventions (Variables & Contexts)

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
