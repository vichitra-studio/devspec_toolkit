# CLAUDE.md

Guidance for Claude Code (CLI, desktop app, web, and IDE extensions) when working with the **AI Spec Driven Development Toolkit** — a schema-first workflow that turns spec → implementation into a deterministic pipeline backed by machine-checkable artifacts.

This file auto-loads in any host that vendors the toolkit as a git submodule at `<host-repo>/devspec_toolkit/`. Most guidance below assumes that host context; toolkit-internal development notes are in the final section.

Current version: see `tools/pyproject.toml`.

---

## Setup

```bash
source devspec_env/bin/activate    # CLI refuses without it
specdev --help                  # list subcommands
specdev <command> --help       # usage for one command
```

First-time toolkit-internal setup (requires [`uv`](https://docs.astral.sh/uv/)) — provisions a managed CPython 3.13, builds `devspec_env`, installs the toolkit + dev tooling, and configures git hooks:
```bash
bash scripts/init_toolkit_dev.sh
```

If the venv isn't active, use the wrapper:
```bash
./tools/run_specdev.sh <command> ...
```

The wrapper is written (and refreshed) into the **host** repo's `tools/` directory by `specdev update`, which `init_project.py` runs after it creates the venv — it does NOT exist inside the toolkit submodule. An edited wrapper is reported (W930) and rewritten only by `specdev update --adopt`. From host root, `./tools/run_specdev.sh` works; from inside `devspec_toolkit/`, activate the venv and use `specdev` directly.

---

## Submodule deployment — flag rules

**Default to passing all three flags** so both canon tiers and host-repo git resolve correctly:

```
--repo-root <toolkit-path>     # schema + core canon (e.g. ./devspec_toolkit)
--spec-root <host-spec-path>   # project canon (e.g. ./spec)
--git-root <host-root>         # git operations against the host repo: gate baselines, governance (e.g. .)
```

If a command rejects a flag with "unrecognized arguments", drop that flag and retry. Six known specifics:
- `canon-accept` writes via `--git-root` and does **not** accept `--spec-root`.
- Most `specdev json …` subcommands (`read`, `read-multi`, `keys`, `structure`, `schema`, `patch`, `insert`, `delete`) take `--repo-root` only. The CLI now silently strips `--spec-root`/`--git-root` from these, so passing them is harmless — but the canonical invocation omits both. Exceptions: the id forms `json patch|insert|delete --id <id>` and `json insert --step <NN>` take all three flags; `specdev json resolve-pointers` legitimately accepts `--git-root` to anchor relative file-path resolution (and warns-then-ignores `--spec-root`); both flags are passed through unchanged.
- Most diagnostic / utility commands (e.g. `ai-help`, `env-check`, `dependency-order-lint`, `prompt-context`, `dag-lint`, `extraction-intent-check`) take only `--repo-root`.
- `update` takes `spec_dir` (positional) + `--repo-root` + `--git-root` (the host root it installs into; default: the git top folder of `spec_dir`) and the flags `--install-only`, `--no-install`, `--adopt`, `--force-claude`, `--dry-run`, `--json` — does **not** accept `--spec-root`.
- `align` takes `spec_dir` (positional) + `--repo-root` + `--git-root` — does **not** accept `--spec-root`. `align apply`, `propose`, `triage`, `bind-legacy` and `validate` need a git work tree (E880 otherwise).
- `seed-index` takes `spec_dir` (positional) + `--repo-root` + `--git-root` — does **not** accept `--spec-root`. `hardcoded-seed-check` takes `--repo-root` + `--git-root` only (no positional, no `--spec-root`).

For toolkit-internal development (cwd = toolkit root), the flags default sensibly and can usually be omitted.

---

## Core rules

1. **Use `spec-check`, not `validate`** — `spec-check` resolves project canon; bare `validate`/`validate-all` only see toolkit core canon and emit false E110s. `spec-check --step NN` is the gate of one step; `spec-check --merge` is the gate of a pull request.
2. **Spec context loads through the /specdev-context skill** (`devspec_toolkit/.claude/skills/specdev-context/SKILL.md`). The skill exposes two flows — Orientation (load context for a step) and Action (apply surgical edits driven by a source of findings). Never read `spec/*.json` files directly. For targeted reads, use `specdev json read|read-multi` or `specdev node show <id>`; for targeted edits, use `specdev json patch|insert|delete --id <id>` (by node id: it also keeps the trace lock in step). Direct file ops miss cross-step dependencies and bypass schema awareness.
3. **Read `docs/prompts/shared_expectations.md`** before executing any `prompt_NN_*.md`.
4. **Forward-only waterfall** — a spec is a graph of nodes with ids, linked by id (`derives_from`, `refines`, `verifies`, ...). An edit of a node makes every link that points at it suspect (E763): `specdev stale` lists them by step; replay each step it names, top down, and accept each link you have re-read with `specdev attest`. Don't fix downstream failures by silently rewriting upstream artifacts.
5. **A milestone's loop is `/specdev-trinity`** — it runs `specdev milestone start|close`, `plan record`, `review record` and `verify run`. A person decides `milestone sign-off`, `milestone defer`, `verify attest` and `release`; an agent never answers their prompt. Never write a plan, a record or a milestone status by hand.

---

## CLI — common patterns

Full command catalog: `docs/developers/reference.md`. Use `--help` on any subcommand for current flags.

```bash
# After bumping devspec_toolkit submodule — sync project to new toolkit version
# (installs the host files, then re-stamps spec/specdev_version if no schema changes; directs to align if changes required)
specdev update spec --repo-root ./devspec_toolkit --git-root .
# The host files only (hooks, merge driver, workflows, wrappers, .claude links): once per clone
specdev update spec --repo-root ./devspec_toolkit --git-root . --install-only

# Unified gate check — runs all applicable validation / lint checks
specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Step gate: finishing step 05 (exit 1 only when the step itself is blocked)
specdev spec-check spec --step 05 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Merge gate (what the merge-check workflow runs on a pull request)
specdev spec-check spec --merge --base-ref origin/main --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Before authoring step NN, and after an upstream edit: what blocks, which links are suspect, accept after reading
specdev step ready 05 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev stale --diff --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev attest <node-id> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# After Step 03 glossary — promote project terms to canon
specdev canon-accept --from spec/03_glossary.json \
  --repo-root ./devspec_toolkit --git-root . \
  --namespace cn:project: --owner product

# List every open ambiguity item (steps 00-15, the anchor, milestone plans) grouped by the step
# of the nodes it is about (does not accept --git-root)
specdev upstream-backlog spec --repo-root ./devspec_toolkit

# Pre-push commit-message check
specdev governance-check spec --repo-root ./devspec_toolkit \
  --spec-root ./spec --git-root . --message "<commit message>"

# Targeted JSON read of a spec artifact (avoids direct Read)
specdev json read spec/03_glossary.json '.terms[] | select(.domain == "analytics")'
specdev json read-multi spec/03_glossary.json '.terms | length' '.id' '.owner'

# Targeted edit of a spec artifact (avoids direct Edit/Write)
specdev json patch  spec/03_glossary.json '.terms[0].domain' '"infrastructure"'
specdev json insert spec/03_glossary.json '.terms' '<term-object-json>'
specdev json delete spec/03_glossary.json '.terms[3]'
# The same by node id (takes all three root flags; writes the trace lock entries of the links it changes)
specdev json patch --id fr-user-login .priority '"must-have"' --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# The life of a milestone (run by /specdev-trinity) and of a release (a person's decisions; none commits or pushes)
specdev milestone start ms-account-recovery --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev status --milestone ms-account-recovery --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev milestone close ms-account-recovery --check --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev release prep --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
specdev release --tag vX.Y.Z --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Diagnostic — print active SPECDEV_* config
specdev env-check --repo-root ./devspec_toolkit

# Regenerate toolkit-side entry-key registry + extraction_paths + step_order + cli_commands + schema-change checklist
# Run after any schema, annotation or CLI-parser change; the five generator-owned files it writes
# (entry_key_registry.json, extraction_paths.json, step_order.json, cli_commands.json under tools/,
# and docs/developers/schema-change-checklist.md) must stay byte-exact with
# this output (enforced by CI gate — do not hand-edit them). Note:
# command_prefixes.json and step_docs.json are NOT generator outputs — they are
# manually maintained despite also living under tools/.
specdev registry-generate --repo-root .
```

---

## Architecture

**Pipeline (forward-only waterfall):** steps `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 14 15 16` each produce `spec/NN_*.json`. Step 16 has a Trinity loop (16a plan → 16b code → 16c review) applied per-milestone in `spec/impl_context/ms_*_plan.json`.

**Phases:**
- *Phase 0* — seed docs (`spec/common/seed_manifest.json` + supporting seeds) before any formal specs
- *Phase I — Discovery (00–12)* — Charter → Capabilities → System Sketch → Glossary → FRs → APIs → Invariants → NFRs → Fixtures → Impl Plan → Governance → Red Team → CI Gates
- *Phase II — Impl (13–16c)* — Extension Generator → Roadmap → Scaffold → Trinity Loop

**Key directories:**
- `schema/` — JSON Schemas per step + `schema/core/` (`atoms`, `collections`, `errors`, `canon`, `step_base`)
- `canon/` — toolkit-tier canonical registry (`manifest.json`, `kinds/`, `aliases.json`); see `canon/README.md`
- `prompts/prompt_NN_*.md` — deterministic prompt contracts
- `tools/specdev_tools/` — Python CLI package (entry: `cli.py`)
- `tools/schema_registry.json` — maps `$schema` URIs to schema files
- `tools/step_order.json` — strict waterfall DAG
- `spec/extras/` — tool-owned files of a host spec (`trace.lock.json`: what each link's author accepted; verification records); never edited by hand
- `tools/specdev_tools/host_install.py` — the installer behind `init` and `specdev update` (pre-commit, merge driver, workflows, wrappers, `.claude` links, ask rules, gitignore); see `docs/developers/host_setup.md`
- `scripts/init_project.py` — bootstraps a new host repo (directories, submodule, venv), then runs `specdev update --install-only`

**Naming:**
- IDs: kebab-case (`fr-user-login`, `api-session-create`)
- Owner enum: `api | ui | system | ops | data | product | business | engineering` (source of truth: `schema/core/atoms.schema.json#owner`)
- Reuse primitives from `schema/core/` (atoms, collections, errors, etc.); never redefine
- Artifacts must include the canonical `$schema` URI from the matching prompt

**Agent operating protocol:** Two-Phase Clarify → Emit, Self-Audit Gate, ledger-only context. Full contract: `docs/agents/agents.md`.

---

## Troubleshooting

Full E/W code catalog: `docs/developers/error-codes.md`. Generic step/schema patterns: `docs/developers/reference.md`. Common submodule-deployment traps:

- **E110 UNKNOWN_CANONICAL_ID**: Run `specdev guide E110` for full playbook.
- **E530 INVENTED_ENUM_OR_ID**: Run `specdev guide E530-INVENTED_ENUM_OR_ID` for full playbook.
- **E763 suspect link**: the target of a link changed after the link was accepted. `specdev stale --diff` shows the old and new text; edit the holder, or accept with `specdev attest <node-id>`. E700 to E704 (broken links): `specdev guide E700` to `E704`.
- **Gate compares against the wrong baseline**: pass `--git-root .` so git operations target the host; name the base with `--base-ref` or `SPECDEV_REPLAY_BASE_REF`.
- **W930 to W935 from `specdev update`**: W930 = a host file the installer would write differs and is left alone (`--adopt` for hooks and wrappers, `--force-claude` for stale links); W931 = a piece was refused; W932 = a retired command in the host's own workflow or hooks; W935 = no `setup_command` declared. The ask rules and the merge driver are per clone: run `specdev update` once in each clone.
- **E880 to E882 in a migration**: `specdev guide E880` (the migration refuses to start), `E881` (a script broke a rule; nothing written), `E882` (a baseline link not yet accepted: `specdev attest <node-id> --yes`).
- **`Schema not found`**: confirm `--repo-root` points to the toolkit; check `tools/schema_registry.json`.

---

## Environment variables

| Variable | Effect |
|---|---|
| `SPECDEV_WARNINGS_AS_ERRORS=1` | Promote all W-codes with E-counterparts to errors |
| `SPECDEV_PROMOTE_CODES=W571,W593` | Selective promotion of listed W-codes. A listed code that is not promotable (absent from `PROMOTABLE_PAIRS`, e.g. `W590`/`W597`) or unrecognised is **ignored with a one-time stderr warning** naming the code (emitted by `validate-all` and `spec-check`), rather than silently dropped. |
| `SPECDEV_INVARIANTS_STRICT=1` | Promote `invariants-check` unevaluable rules (`W_INVARIANT_UNEVALUABLE`) to fatal errors (`E_INVARIANT_UNEVALUABLE`); equivalent to `invariants-check --strict` |
| `SPECDEV_REPLAY_BASE_REF=<ref>` | The base ref of the step gate and the merge gate when `--base-ref` is not given (default: `origin/HEAD`) |
| `SPECDEV_REVIEW_CONCURRENCY=N` | Max simultaneous reviewer agents per wave in the `/specdev-review` loop (default 6); controls wave width, not total fan-out |

Inspect active config: `specdev env-check --repo-root <toolkit>`.

---

## Versioning & migration

Semver. Toolkit version in `tools/pyproject.toml`. See `CHANGELOG.md` and `changelog/`.

When the toolkit version changes, `specdev update` says whether the host spec needs a migration; `align` runs it (positional `spec_dir`). A 1.1.1 host moving to 1.2.0 (the procedure: `docs/developers/workflows/workflow_migrate_1_2_0.md`):

```bash
specdev update spec --repo-root ./devspec_toolkit --git-root . --no-install --dry-run   # says a migration is needed and prints these steps (exit 1)
specdev align apply spec --auto --dry-run --repo-root ./devspec_toolkit --git-root .    # the diff; writes nothing
specdev align apply spec --auto --repo-root ./devspec_toolkit --git-root .              # writes under spec/ only; no commit, no backup
git add spec && git commit --no-verify -m "Migrate the spec to toolkit v1.2.0"
specdev align triage spec --repo-root ./devspec_toolkit --git-root .                    # the decisions left for a person: --step NN, --resolve ID --note "..."
specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .    # also: prose-ids, bindings
specdev align validate spec --repo-root ./devspec_toolkit --git-root . --base-ref origin/main   # the merge gate, then clears the migration status
```

Subcommands: `status, diff, plan, apply, propose, triage, bind-legacy, prompts, rollback, validate`. The older `status`, `diff`, `plan` and `prompts` read only the top level of each schema and say almost nothing about a 1.1.1 host; use `apply --auto`, `triage`, `propose` and `validate`.

---

## Toolkit-internal development

```bash
pytest tests/                  # full suite
pytest tests/unit/             # unit tests only
pytest tests/integration/ -v   # step-level integration tests
```

Run from toolkit root with `devspec_env` active.
