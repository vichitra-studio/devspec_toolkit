# CLI Reference

## Submodule-Aware Flags

The following flags are available on most spec-operating commands, including
`validate`, `validate-all`, `spec-check`, `seed-lint`, `fixtures-lint`,
`invariants-check`, `governance-check`, `canonical-lint`, `canonical-integrity`,
`spec-quality-lint`, `hallucination-lint`,
`milestone-state`, and `canon-schema-alignment`; the trace commands `stale`,
`attest`, `coverage`, `step create`, `step ready`, `node rename`,
`lock install-driver`, `verify bind`, `verify run`, `third-party pin` and
`third-party check` take all three (and `--json`). Per-command exceptions (per
CLAUDE.md): `canon-accept` takes `--git-root` (and `--repo-root`) but **not**
`--spec-root`; the path forms of `specdev json` (`read`, `patch`, `insert`, ...)
take `--repo-root` only, while `json patch|insert|delete --id` and
`json insert --step` take all three; `lock merge` takes only its four positional
arguments (git runs it); and
diagnostic/utility commands (`ai-help`, `env-check`, `dependency-order-lint`,
`dag-lint`, `extraction-intent-check`, `prompt-context`) take `--repo-root`
only; `update` takes `spec_dir` (positional) + `--repo-root` only and does
**not** accept `--spec-root` or `--git-root`; `seed-index` takes `spec_dir`
(positional) + `--repo-root` + `--git-root` but **not** `--spec-root`, and
`hardcoded-seed-check` takes `--repo-root` + `--git-root` only (no
positional, no `--spec-root`).
Run `<command> --help` to confirm the supported flags for any subcommand:

| Flag | Description | Default |
|------|-------------|---------|
| `--repo-root` | Path to devspec_toolkit directory (for schema resolution) | `.` |
| `--spec-root` | Path to the spec directory (for submodule deployments where spec/ is outside toolkit) | Depends on the command: see the list below the table |
| `--git-root` | Path to the host repo git root (for submodule deployments where git root differs from toolkit root) | Depends on the command: see the list below the table |

The default of the two flags, for the commands that were run from the folder above a copy of a host with `--spec-root host/spec` and no `--git-root`:

- `node`, `trace`, `diff`, `stale`, `attest`, `step`, `lock install-driver`, `verify`, `third-party`, `json patch|insert|delete --id` and `json insert --step`: `--spec-root` is `./spec` (with no `--spec-root` they read `./spec` of the current folder; when that folder has no `spec`, `node`, `trace`, `stale`, `attest`, `step` and the `json` forms print `E520 UNRESOLVED_INPUT missing_spec_dir <current folder>/spec`, and `diff` and `lock install-driver` report what git says); `--git-root` is the folder that holds the spec folder (`host`), where the seed documents and the git history are read. `coverage` was run with the same defaults for `--git-root`.
- `spec-check` and `validate-all` (the spec folder is the positional argument): the seed documents are read from the folder that holds the spec folder when `--git-root` is absent.
- Every other command: `<command> --help`; this table does not say.

A spec folder that is not directly below the repository root (spec at `h/sub/spec`, seed documents at `h/docs/seed`) needs `--git-root .` from `h`: without it the folder that holds the spec folder is `h/sub`, the seed documents are not found there, `validate-all` and `spec-check` report their links as suspect (E763), and the commands that write hashes into the trace lock are refused with E520 (see `specdev attest` below).

### Examples

```bash
# Standard (non-submodule) usage — intentionally flagless: when spec/ lives under the
# toolkit root, --spec-root/--git-root default correctly and are omitted on purpose.
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

# Submodule deployment
./tools/run_specdev.sh validate-all spec \
  --repo-root ./devspec_toolkit \
  --spec-root ./spec \
  --git-root .

# What is still to be replayed after an upstream change, with explicit roots
./tools/run_specdev.sh stale \
  --repo-root ./devspec_toolkit \
  --git-root . \
  --spec-root ./spec
```

---

# Developer Reference

This reference collects recurring facts that developers need while authoring or reviewing specs. It replaces ad-hoc snippets scattered across multiple documents; other guides intentionally link here for the canonical commands and troubleshooting flow.

## Terminology
| Term       | Definition                                              |
|------------|----------------------------------------------------------|
| Step       | Numbered phase of the spec lifecycle (00–16c, 02a)        |
| Artifact   | Machine-checked JSON file for a step (`spec/NN_name.json`) |
| Guide      | Human playbook describing a step (`spec/NN_name.guide.md`) |
| Prompt     | AI instruction file (`prompts/prompt_NN_name.md`)         |
| DoR        | Definition of Ready requirements for completing a step    |
| Link field | An id array on a node whose schema carries an `x-link` annotation (for example `derives_from`, `constrains`, `verifies`, `schedules`, `threatens`, `mitigated_by`, `realises`, `refines`, `removes`); see [schema-annotations.md](schema-annotations.md) |

## Naming & Schema Conventions
- **IDs**: kebab-case only (`fr-user-login`, `api-session-create`).
- **Owner enum**: one of `{api, ui, system, ops, data, product, business, engineering}` (source of truth: `schema/core/atoms.schema.json#owner`).
- **Artifacts**: include the canonical `$schema` URI exactly as emitted in the prompt.
- **File naming**: `spec/NN_name.json`, `spec/NN_name.guide.md`, [./devspec_toolkit/prompts/prompt_NN_name.md](../../prompts/) (adjust the toolkit path as needed).
- **No redefining primitives**: reuse atoms/collections/errors from [schema/core/](../../schema/core/).

## Path Conventions
See [path_conventions.md](path_conventions.md) for canonical path variables (`$PRODUCT_ROOT`, `$TOOLKIT_ROOT`, `$SPEC_DIR`, etc.) and the dual-root convention.

## Scope Lock (`spec_dir`)
- Enforce scope lock for every repo: set and persist `spec_dir` explicitly instead of inferring from cwd.
- **Consumer repos** (projects that vendor the toolkit as a submodule): the locked `spec_dir` is `<product-repo>/spec/` — this is where your live spec artifacts live.
- **Toolkit repo itself**: the toolkit does not maintain spec waterfall artifacts and does not run spec validation against itself. Seed templates for host bootstrap live in `seed_templates/`.
- Automation and CI must pass the same `spec_dir` to every command to avoid path-assumption drift.

## Command Cheatsheet
Set up your environment per [`getting_started.md`](getting_started.md#1-set-up-your-environment) before running these commands. Every other document links back here so this serves as the canonical command reference.
All validation and linting commands below use `./tools/run_specdev.sh` (generated by the init script) to enforce virtualenv usage. Alignment commands use `specdev align`, which is installed alongside the toolkit CLI.

### Project Initialization
```bash
# Initialize a new project (creates dirs, submodule, venv, hooks, CI)
python3 devspec_toolkit/scripts/init_project.py --target . --strict
```

### Core validation commands
```bash
# Unified gate — runs all applicable validation / lint checks (preferred over bare validate-all;
# resolves project canon, so it avoids the false E110s that validate-all alone can emit)
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Step gate (see "Step gate" below): finish step 05, or gate the steps of the files you touched.
# Exit 1 only when something blocks.
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --step 05
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --step 05 --base-ref main --detail all
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --paths spec/04_fr_list.json spec/05_interface_contracts.json

# Validation
./tools/run_specdev.sh validate spec/00_charter.json --repo-root ./devspec_toolkit
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Coverage and fixtures. `matrix`, `completeness-check` and `traceability-check` were removed in 1.2.0:
# `specdev coverage` shows the link counts and the ids that are not linked, `specdev coverage --by fr`
# the per-FR view, `specdev trace` the lineage of one node, and the role-rule findings (E740 to E745)
# are checks of `spec-check`.
./tools/run_specdev.sh coverage --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh coverage --by fr --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Seed enforcement
./tools/run_specdev.sh seed-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Invariants & Governance
# SPECDEV_INVARIANTS_STRICT=1 is equivalent to passing --strict: promotes unevaluable
# rules (W_INVARIANT_UNEVALUABLE) to fatal errors (E_INVARIANT_UNEVALUABLE)
./tools/run_specdev.sh invariants-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --sample ./path/to/sample.json
./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --message "feat(spec): add login [fr-initial-login]"

# Quality, hallucination, and canonical integrity
./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Canon/schema alignment
./tools/run_specdev.sh canon-schema-alignment --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Step-order integrity (strict waterfall)
./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit

# Replay after an upstream change: see "Trace lock, replay and attest" below.
# forward-replay-check was removed in 1.2.0: stale lists the suspect links, spec-check the broken links.
./tools/run_specdev.sh stale --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# DAG completeness lint (validates downstream_consumers consistency)
./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit

# Extraction intent validation (prompts vs step_order.json)
./tools/run_specdev.sh extraction-intent-check --repo-root ./devspec_toolkit

# Environment diagnostic (read-only — prints active config)
./tools/run_specdev.sh env-check --repo-root ./devspec_toolkit

# Prompt workflow reminders
./tools/run_specdev.sh ai-help --step 04

# Changelog utilities (migration system)
./tools/run_specdev.sh changelog --list --repo-root ./devspec_toolkit
./tools/run_specdev.sh changelog --version <version> --repo-root ./devspec_toolkit
./tools/run_specdev.sh changelog --validate <version> --repo-root ./devspec_toolkit

# Trinity milestone-state — deterministic phase-position computation (DEVSPEC-38)
./tools/run_specdev.sh milestone-state --batch-id <batch-id> \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .

# Targeted JSON read/query of a spec artifact (avoids direct Read)
./tools/run_specdev.sh json read spec/03_glossary.json '.terms[0].id' --repo-root ./devspec_toolkit
./tools/run_specdev.sh json read-multi spec/03_glossary.json '.terms | length' '.id' --repo-root ./devspec_toolkit

# Targeted JSON edit of a spec artifact (avoids direct Edit/Write)
./tools/run_specdev.sh json patch  spec/03_glossary.json '.terms[0].domain' '"infrastructure"' --repo-root ./devspec_toolkit
./tools/run_specdev.sh json insert spec/03_glossary.json '.terms' '<term-object-json>' --repo-root ./devspec_toolkit
# delete/keys/structure accept --repo-root too (delete does not use it)
./tools/run_specdev.sh json delete spec/03_glossary.json '.terms[3]' --repo-root ./devspec_toolkit

# By node id (see the json section below): writes the trace lock entries of the links it adds or removes
./tools/run_specdev.sh json patch --id fr-password-reset .priority '"should-have"' \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

### Step gate: `spec-check --step` and `--paths`

Plain `spec-check` lists every finding of every check. With `--step` or `--paths` it gates one step instead: it says whether you may call that step done. The gate blocks on the errors that step owns and on the errors of earlier steps that are new since the baseline (the tree it compares your working tree with, see `--base-ref`). It does not block on an earlier step's errors that the baseline already had (upstream debt), on errors owned by a later step (pending: owned by a later step), or on errors owned by a gate such as `merge-check`.

| Flag | Meaning |
|------|---------|
| `--step N` | Gate step `N`, written as in the file name: `05`, `02a`, `16`. `5`, `13A` and `13a` (step 13a was removed in 1.2.0) are unknown steps (`E706 no step '5'; known steps: 00, 01, ... 16c`, exit 1). Repeat it for several steps: one block per step, in the order given; a step given twice is gated once. An unknown step gives E706 and exit 1. A step that has no artifact in the spec folder (step `15` once `15_scaffold.json` is removed from the worked example) is still gated, and stderr says `step 15 has no artifact in <spec dir>`. |
| `--paths FILE...` | Gate the steps that the listed files belong to. It takes every word after it up to the next option, zero or more files, so write `spec_dir` before it (`spec-check --paths FILE spec` reads `spec` as a file and exits 2: `spec_dir` is required). It cannot be combined with `--step`. A file `<spec>/NN_*.json` maps to step `NN` (`<spec>/16_impl_context.json` to `16`), a milestone plan `<spec>/impl_context/ms_*_plan.json` to `16a`, `16b` and `16c`, a seed document listed in the seed manifest to the steps whose nodes derive from it and the steps the manifest routes it to (step `00` when there are none), and the manifest `<spec>/common/seed_manifest.json` itself to step `00` and every step of its `step_requirements` (`00` and `02` in the worked example). Any other file, such as one under `<spec>/extras/` or `<spec>/canon/`, or one outside the repository, maps to no step. A step with no artifact in the spec folder (its file is not there, for example because a commit deleted it) is dropped, not gated, unlike under `--step`, which gates it. When no file maps to a step the command exits 0 without running a check; when files were listed it says so on stderr (`no step gated: no listed path maps to a step that has an artifact`), so a mistyped path is seen (with `--json` it prints a `step_gate` with no steps and `"result": "clear"`). |
| `--base-ref REF` | The base ref. The baseline is the merge-base of `HEAD` with it (the commit where your branch left it), and what changed since then is new. The default is `SPECDEV_REPLAY_BASE_REF`, then `origin/HEAD`, then `origin/main`, `origin/master`, `main` and `master`, the first that exists. The baseline is `HEAD` itself (mode `head`: only edits you have not committed count as new) when `HEAD` has no commit that the base ref lacks. A commit that is on `HEAD` and not on the base ref counts as new: with `origin/HEAD` set and an unpushed commit on `main`, the baseline is `origin/main` (mode `merge-base`) and an error of that commit blocks; with no remote the base ref is `main` itself, so an error committed on `main` is not new. When the baseline is `HEAD` on a branch other than the base ref's, stderr says `note: the baseline is HEAD itself: only uncommitted changes count as new`. When no baseline can be used, the report says `base: unavailable`, every upstream error counts as new, and stderr gives one `note:` line with the reason: `no base ref found (origin/main, origin/master, main, master); pass --base-ref`, `<ref> does not name a commit`, `no common history with <ref> (a shallow clone?)`, `not a git repository`, `no commit yet`, `the spec folder is not in the base commit <12-char sha>: every error of an earlier step counts as new` (a branch that adds the spec folder, such as a host's first adoption branch: the base commit has no spec folder to compare with; a base commit that holds a file named like the spec folder is the same case), or `the checks could not run on the baseline tree: <ErrorType>: <its text>` (the checks raised an error on the baseline tree; a baseline whose `07_nfrs.json` holds `[]` instead of an object gives `AttributeError: 'list' object has no attribute 'get'`). An empty `--base-ref ""` is a usage error (exit 2). |
| `--detail {summary,all}` | `summary` (the default) prints a count for upstream debt, pending (owned by a later step) and gate-owned findings; `all` lists them. |

`--base-ref` and `--detail` need `--step` or `--paths`. Each misuse is a usage error with exit 2. The report goes to stdout, with or without `--json`; notes go to stderr (the reason a baseline is unavailable, a step with no artifact, a seed document listed on `--paths`, a path that lies outside the host root, seed documents not found, a file that could not be read). A seed document listed on `--paths` gives `seed document edited: run specdev stale to see what became suspect`, whether or not the file changed: the note follows the list, not an edit. The exit code is 1 when the result is `BLOCKED` and 0 when it is `CLEAR`, with `--json` too. A refusal prints one finding and exits 1, to stderr in text mode and as JSON on stdout with `--json`. `--step` and `--paths` have these refusals: a spec folder that does not exist (`E520 UNRESOLVED_INPUT missing_spec_dir <dir>`; plain `spec-check` on it runs every check and prints that E520 among other findings, exit 1), a toolkit whose `tools/error_ownership.json` is missing or unreadable (`E520 UNRESOLVED_INPUT ownership_table <path>: unreadable or not a JSON object`; plain `spec-check` refuses the same way), a toolkit whose `tools/step_order.json` is unreadable (`E520 <path> step order is unreadable: <reason>`, for a missing file `No such file or directory`), and, with `--step` only, a step that does not exist (`E706 no step '99'; known steps: 00, 01, ... 16c`). With `--paths` only, a spec folder that is not inside `--git-root` is a refusal too: it gives `E708 the spec folder <dir> is not inside the git root <root>, so it cannot be found in the repository`. `--step` is not refused in that layout: the report says `base: unavailable` and stderr gives the note `the spec folder <dir> is not inside the git root <root>, so it cannot be found in the repository`. A spec file that cannot be read (no permission, or a folder named like a step file) does not stop the run: stderr says `specdev spec-check: could not read <file>; the answer may be incomplete`, the `open-items` check reports one E520 `cannot read <path>: <reason>`, owned by the step of the file, and the other checks go on; they may report errors of their own for the same file.

Run on the worked example with a broken link in step 04, `spec-check spec ... --step 05` prints (`<sha>` is the commit id of the baseline; the numbers in `PENDING (N)` and `GATE-OWNED (N)` are written `N` here because they move when a check or warning is added). The `PENDING` line is there because the worked example is a partial spec: the role checks (E740, E743) report nodes that steps 07, 08, 12 and 14 own:

```
step gate: step 05   base: main <sha> (head)
BLOCKING (1)       own 0, new upstream 1
  E700  [04 new upstream]   fr-broken-link  fr-broken-link (04_fr_list.json), field derives_from, target 'cap-ghost': no node has that id
PENDING (N)        07: N, 08: N, 12: N, 14: N   (clears when those steps run)
GATE-OWNED (N)     merge-check: N   (--detail all to list)
RESULT: BLOCKED
```

Other lines the report can carry: `WARNINGS` (warnings of the step, and new warnings of earlier steps; they do not block), `WAITING` (errors of the step that sit below a node an open item is about; they are listed with the ids of the items and do not block), `UPSTREAM DEBT`, `PENDING` and `GATE-OWNED`. A finding line is the code, the step and bucket in brackets (`04 new upstream`: owned by step 04, which is earlier than the gated step, and new), the node id (else the file name, else `-`), and the message. In the summary the `GATE-OWNED` line ends `(incl. suspects: specdev stale)` when some of those findings are suspect links (E762, E763: for example after the `statement` of `fr-password-reset` was edited, the line read `GATE-OWNED (N)    merge-check: N   (incl. suspects: specdev stale) (--detail all to list)`); with `--detail all` the findings are listed and the line has no suffix. With `--json` the same buckets are under `step_gate` (`steps`, the gated steps in the order given; `blocking`, `waiting`, `own_warnings`, `new_upstream_warnings`, `upstream_debt`, `pending`, `gate_owned`) beside `baseline` (`ref`, the base ref; `commit`; `mode`: `merge-base`, `head` or `unavailable`) and `result`. With several steps each bucket is the union over the steps and an entry does not say which step it belongs to: an error that is the own error of step 04 and upstream debt for step 05 is listed in `blocking` and in `upstream_debt`.

What is new is decided by count. The key of a finding is its code, owner, node id, link target, file, location, subcode and path; the message is not in it. The location is the `jq` path of the place with every array index removed, for a finding that has one: `.functional_requirements[3].scope` is `.functional_requirements[].scope`. An index inside a quoted key is part of the key and stays: `.environments["x[3]"]` and `.environments["x[4]"]` are two keys (with a bad `x[3]` entry in `environments` of step `02a` in the baseline, a second bad entry `x[4]` gave `UPSTREAM DEBT (3)` and two new upstream E520). A schema error (E520) has no node id; it carries `file` (`04_fr_list.json`) and `jq_path` (`--json` prints both; `jq_path` is a filter that `specdev json read` accepts, except `.` (the whole file, which it refuses), and a key that is not a name in jq is written in brackets: with `step_requirements.00` set to `5` in `common/seed_manifest.json`, `validate --json` gives `"jq_path": ".step_requirements[\"00\"]"` and `specdev json read` of it prints `5`; `validate` and `validate-all` with `--json` give `jq_path` on a schema E520 too, without `file`, and the `path` lines of a `json patch` schema refusal print it the same way: `path .step_requirements["00"]: 5 is not of type 'array'`), so the key of the bad `scope` of one requirement is E520, owner `step:04`, file `04_fr_list.json`, location `.functional_requirements[].scope`. For each key the gate counts the findings on the working tree and in the baseline. A finding whose message the baseline also had is old (the baseline's findings are reported with the paths of your tree, so an error that did not change has the same message in both). Of the others with that key, as many as the baseline had are old (their text changed) and the rest are new. Two findings with one key and one message are one finding; with two messages they are two. A new finding owned by a step earlier than the gated one is a "new upstream" finding in the report. So, with one bad `scope` in step 04 in the baseline (two E520: the bad value and the unevaluated-properties error that follows it), a second bad `scope` on your branch gives `UPSTREAM DEBT (2)` and `BLOCKING (1)`, one new upstream. Not new: a message that was reworded (`bogus` changed to `bogus2`), and an old error that moved because you inserted an item before it. A node renamed with `specdev node rename` keeps its old id as an alias, so an old error about it stays old: with a link of `fr-password-reset` to a node of the wrong kind in the baseline, renaming that node (`fr-password-reset-request` to `fr-password-reset-request-x`) gave `UPSTREAM DEBT (1)` and `RESULT: CLEAR` (`specdev node rename` refuses a node that has a link error of its own, E770). A node renamed by hand, and a file renamed, give their old errors a new key: renaming `fr-password-reset` to `fr-password-reset-y` by hand gave `E701 [04 new upstream] fr-password-reset-y` (and an `E700 [05 own]`: an API of step 05 still names the old id), and renaming `04_fr_list.json` to `04_requirements.json` gave its two E520 as new upstream (and two `E700 [05 own]`: `no file of step 04 exists in the spec`). An error in another file or at another place is a different key, so a fix elsewhere does not offset it: with a bad `priority` of the first requirement in the baseline, a branch that fixes it and breaks the `scope` of the second gives `BLOCKING (1)`, `RESULT: BLOCKED`. One limit: if one error is fixed and another with the same key is added on the same branch (the same code, file and place once the indexes are removed: the `scope` of the second requirement fixed and the `scope` of the first broken), the count does not grow and the step gate reads no change: `UPSTREAM DEBT (2)`, `RESULT: CLEAR`. Plain `spec-check` lists the new error, and the merge check, which no command runs yet, reports every error.

A relative path after `--paths` is taken from the repository top, never from the current folder: `--git-root` when it is given, else the top of the git working tree that holds the spec folder, else the folder that holds the spec folder. That is where pre-commit runs a hook. With a nested spec folder (`h/sub/spec`, seed documents at `h/docs/seed`), pass `--git-root .` from `h`; without it a seed document lies outside the folder the command can see, and the run prints a note such as `1 path lies outside the host root and maps to no step; pass --git-root <repository root> when the spec folder is nested` (when no other listed file maps to a step, the exit code is 0 and no check runs). With `--git-root` given the note stops after `maps to no step`: `spec-check spec --git-root . --paths ../README.md` prints `1 path lies outside the host root and maps to no step`.

The `spec-check` hook of `templates/pre-commit-config.host.yaml` runs `spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --paths` with `pass_filenames: true` and `require_serial: true`, so pre-commit appends the files of the commit. `init_project.py` writes the template as `.pre-commit-config.yaml` in a new host. A host that already has a `.pre-commit-config.yaml` keeps it: `init_project.py` only prints that the file exists and asks you to check the hooks by hand. A host whose `spec-check` hook still runs the whole spec on every commit has to copy the hook from the template to use the gate.

### `specdev json` — artifact read/query/edit family

Surgical, schema-aware access to `spec/*.json` artifacts; preferred over direct
file reads/writes (the `/specdev-context` skill drives these under the hood). All
positional path arguments are **jq paths/filters** (e.g. `.terms[0].id`), not RFC-6901
JSON pointers. The path forms (a file and a jq path) do not accept
`--spec-root`/`--git-root`; `resolve-pointers` is the exception — it accepts `--git-root` (used, to
anchor relative file-path resolution) and a deprecated `--spec-root` (accepted but
warned-then-ignored; slated for removal). The id forms, `json patch|insert|delete --id <node-id>` and
`json insert --step NN`, are the other exception: they take `--repo-root`, `--spec-root` (default `./spec`),
`--git-root` (default: the folder that holds `--spec-root`) and `--json`, so the three-flag default of CLAUDE.md is accepted by them.
`--repo-root` support is per-subcommand (see the column below):
it is **required** by `resolve-pointers` (registry lookup), used by `schema` for schema
discovery (optional — falls back to `find_schema_dir`) and by `patch`/`insert` for
differential validation, and accepted by `read`/`read-multi`/`keys`/`structure`/`delete`
without being used.

| Subcommand | `--repo-root` | Purpose |
|------------|:---:|---------|
| `specdev json read <file> <jq-filter>` | accepted (unused) | Evaluate a single jq filter against the artifact |
| `specdev json read-multi <file> <jq...>` | accepted (unused) | Evaluate several jq filters in one call |
| `specdev json keys <file> [jq-path]` | accepted (unused) | List object keys at a jq path |
| `specdev json structure <file> [jq-path]` | accepted (unused) | Print the artifact's shape (keys/types) |
| `specdev json schema <file> <jq-path>` | used (optional) | Navigate the resolved schema at a path (own-first property merge; unions `oneOf`/`anyOf`/`if-then-else`) |
| `specdev json patch <file> <jq-path> <value>` | used | Set one value; differential schema-validated before write |
| `specdev json insert <file> <jq-path> <value>` | used | Append into an array; differential schema-validated before write |
| `specdev json delete <file> <jq-path>` | accepted (unused) | Remove one node (jq `del()`; **no** schema validation) |
| `specdev json patch --id <id> <field-path> <value> [--raw] [--dry-run] [--full]` | used | Set a field of the node with that id (an id or an alias); `<field-path>` is a jq path inside the node, for example `.statement`. The edit is checked as above and, in addition, refused (E767) when it would leave a link that does not resolve or names the node's id; a payload that stores a computed field is E768. The lock entries of the links the edit adds or removes are written in the same run, and the command lists the links it leaves suspect (`newly suspect: 21 links (step 05: 2, ...); see `specdev stale``; with `--dry-run` the line reads `would become suspect: 21 links (step 05: 2, ...)`) |
| `specdev json insert --id <id> <field-path> <value> [--raw] [--dry-run] [--full]` | used | Append to an array field of the node with that id. A field the node does not have is created with the one item when the node's schema declares it as an array (`json insert --id fr-password-reset-request .assumes '"asm-member-controls-email"'` creates `assumes`); for a field the schema does not declare as an array the command is E767, names the field and points to `json patch --id` |
| `specdev json delete --id <id> [--dry-run] [--full]` | used | Delete the node with that id and drop the lock entries of its links; links that now point at it are listed as `now broken` |
| `specdev json insert --step NN <collection-path> <value> [--raw] [--dry-run] [--full]` | used | Add a new node to a node collection of the step's file, for example `.functional_requirements` for step 04; ids the item leaves out are minted (`ids minted: ...`) and the lock entries of its links are written. A path that is not a node collection of the step is E767 and the message lists the collections; so is the path of a collection that is a map keyed by id (`.environments` of step 02a), which `insert --step` does not add to (the list marks it `map: not added by this command`) |

With `--dry-run` an id write prints the report of the write, with `lock entry to write` and `lock entry to remove` in place of `lock entry written` and `lock entry removed`, and writes nothing. `json patch|insert|delete --id` and `json insert --step`, dry run included, are refused with E520 when a spec file cannot be read, because the links that file holds are not in the graph: `E520 json patch --id refused: 04_fr_list.json cannot be read, so the links it holds are not in the graph and the lock cannot be checked against them; repair the file, then run the command again`. `node rename`, `node rename --label` and `step create`, dry run included, `attest --yes` and `attest --prune` (each with or without `--dry-run`) and `step ready` refuse the same way. An `attest` preview (no `--yes`), bare or with `--dry-run`, `stale`, `coverage` and `node` print a warning on stderr and an answer that may be incomplete.

The id forms of `json` (`patch`, `insert`, `delete`), `json insert --step` and `step create`, dry run included, `attest <node-id> --yes` and `attest --step NN --yes` (dry run included) are also refused with E520 when a seed document the spec names is not found under the host root, because a hash written for it would be the hash of a missing file: `E520 seed document docs/seed/seed_accounts.md (seed-accounts) was not found under <root>/sub; if the repository root is another folder pass --git-root` (several seeds: `seed documents A (id), B (id) were not found under ...`). The check comes after the schema and id checks of the edit, so an edit that the schema refuses is E767 first. It was run for those forms on a copy whose spec folder is `h/sub/spec` with the seed documents at `h/docs/seed` and no `--git-root`, nothing was written, and the same commands with `--git-root .` ran. `node rename`, `node rename --label`, `node status` and `attest --prune` were run in that layout and are not refused: they write no hash of a seed. The reads (`stale`, `coverage`, `step ready`, the `attest` preview, `attest --prune`) print one line on stderr and then their answer: `note: seed documents not found under <root>/sub: docs/seed/seed_accounts.md (seed-accounts); their links count as suspect; if the repository root is another folder pass --git-root`.
| `specdev json resolve-pointers` (pointer list on **stdin**) | required | Resolve a canonical-ref pointer list; report to `--out <path>` or stdout (also accepts `--git-root`, default cwd). An id defined more than once in the file is reported with `"ambiguous": true` and each definition under `locations` |

`patch` and `insert` perform always-on differential whole-document validation using
the file's own `$schema` URI: a write is refused only if it *introduces* a new
violation (before/after diff), so one-patch-at-a-time repair is never deadlocked.
There is no `--no-validate` bypass. The path form of `delete` does **not** validate — it applies a
jq `del()` and writes atomically; `delete --id` does check the edit. `specdev json insert --create-schema <uri>`
seeds a missing target file with `{"$schema": "<uri>"}` and bootstraps the
array-valued field before validating — enabling first-use creation of an artifact
(e.g. `spec/canon/command_prefixes.json`) without a separate file-creation step.

### `specdev context` — context preparation family

Drives the `/specdev-context` skill's Orientation flow (scoped structure/canon reads
that feed targeted `specdev json` calls, rather than reading `spec/*.json` directly).

| Subcommand | Required flags | Purpose |
|------------|-----------------|---------|
| `specdev context structure <spec_dir> --step STEP` | `--step` | Print the artifact shape (keys/types) scoped to one step, for Orientation reads |
| `specdev context scope <spec_dir> --entry ENTRY` | `--entry` | **Deprecated alias of `specdev trace`.** Prints JSON (`entry`, `resolved_ids` grouped by node kind, `source_files`) for the nodes a trace of the entry reaches up and down, and one deprecation line on stderr. It writes no file (the 1.1.1 command wrote `spec/extras/trace_matrix.json`; `specdev matrix` was removed in 1.2.0) |
| `specdev context canon --step STEP [--spec-root SPEC_ROOT]` | `--step` | List canon entries relevant to a step; `--spec-root` optionally includes project-tier canon alongside toolkit canon |
| `specdev context freshness <spec_dir> [--git-root GIT_ROOT]` | none | Report staleness of loaded context relative to upstream step edits |
| `specdev context review <artifact_path> --step STEP [--entry ENTRY] [--spec-dir SPEC_DIR] [--git-root GIT_ROOT]` | `--step` | Prepare review context for one artifact ahead of a review pass |
| `specdev context extract` | — | **Removed.** Errors with a message directing to `specdev json read <file> '<jq>'`, scoped via `specdev context structure` + `specdev json schema` |

### `specdev node`, `trace`, `diff` — spec graph family

These commands read the spec as a graph: a node is an entry with an id (an FR, an acceptance criterion, an API, a job), and a link field such as `derives_from` or `verifies` points from a node to the nodes it rests on. Ids and links are followed across files. Each command takes `--repo-root`, `--spec-root` (default `./spec`), `--git-root` (default: the folder that holds `--spec-root`, so a run from another folder with `--spec-root host/spec` reads the git history and the seed documents of `host`) and `--json`, so the three-flag default of CLAUDE.md ("Submodule deployment") is accepted by each. A finding is printed on stderr (with `--json`, as the `status` / `errors` envelope on stdout) and the command exits 1.

| Command | Purpose |
|---------|---------|
| `specdev node <id> [<id> ...] [--full]` | For each id: kind, step, role, lifecycle, scope, file and jq path, the node's content (child nodes by id; `--full` includes them), its links out with each target's kind, step and label, and the number of links in by field and kind. `node show <id>` is the same command and also reads an id that is itself a subcommand name. An unknown id is E706 and names the nearest ids |
| `specdev node candidates (--kind KIND \| --for ID) --field FIELD [--query TEXT] [--limit N]` | List the nodes a link field may point at, for a node of kind `KIND` or for the existing node `ID` (which also leaves out the node itself, what it already links to in that field and, in a field that stays within one step, the nodes that would close a cycle (E703)). Exactly one of `--kind` and `--for` is required |
| `specdev node status <id> active\|deprecated\|not_applicable` | Write the node's `lifecycle` into its spec file (`active` removes the key from a node that has another value) and print `<id>: <old> -> <new> (<file>)`; a node that already has the value is not written, an explicit `"lifecycle": "active"` in its file included, and the line reads `<id>: already <value>, nothing written (<file>)`. `not_applicable` parks a node that takes no part: a glossary term no node uses (E741), or a closed milestone's historical step-14 node whose built target was deleted. E705 for an unknown or duplicated id, for a node with no lifecycle (for example a seed), and for a write the JSON tools refuse. A write takes the write lock of the spec folder (E769 when another write holds it) |
| `specdev node rename <old> <new> [--dry-run]` | Change a node's id in one change under the write lock of the spec folder: the node gets the new id and its old id is added to its `aliases`; the links that live nodes write to it are rewritten, and so are the trace lock entries of those links and of the node's own links (their stored hashes do not change, so a rename makes nothing suspect). Links held by closed milestones and by records keep the old id and resolve through the alias. Before it writes it checks the schema of the files it edits and the findings of the graph, and refuses under E770, with nothing written, a rename that adds a schema violation or a finding (for example a plan item renamed to an id that is not in capitals and underscores), a seed, a record, an environment, an id a node or alias already has, the same id twice. It does not run the step validators: a new id that breaks the id convention of a step (`node rename fr-password-reset 9`) is written, and `spec-check` reports it (E530). An unknown id is E706. A plan item can be renamed (`node rename PWRESET_CONFIRM_EXPIRED_01 PWRESET_CONFIRM_EXPIRED_02`) |
| `specdev node rename --label <term-id> "<new label>" [--dry-run]` | Change the label (`term`) of a glossary term and rewrite every use of the old label (whole words, the same spelling) in the text of nodes of steps 04 to 15, listing each use with its node, field path and old and new text; a use in a node of a closed milestone is not rewritten and is listed under `not rewritten (closed milestone)`. The nodes whose text changes, and the nodes that link to them, become suspect (`specdev stale`); the lock is not touched. E770 when the id is not a glossary term |
| `specdev trace <id> [--up] [--down] [--depth N] [--kinds K,K] [--verbs V,V] [--no-containment]` | List what the node rests on (`--up`) and what rests on it (`--down`); neither flag prints both. `--depth` counts edges, `--kinds` keeps the listed kinds in the output, `--verbs` limits the link fields followed, `--no-containment` stops following the parent / child edge of the JSON tree |
| `specdev trace <id> --recipe 16a\|16b\|16c [--expand] [--since REF]` | Print the context pack of a role from a start node: a task for `16a`, a plan item for `16b`, a roadmap milestone for `16c` (E707 for another kind). `--expand` adds each node's content; `--since` sets the git ref the `16b` dependency report compares against. Not combined with the walk flags above |
| `specdev diff <refA> <refB>` | Compare the graph at two git refs (tags, branches or commits; the working tree is not read): nodes added, removed, changed, whose lifecycle or kind changed, grouped by role and kind, then a suggested version bump (advisory). A node renamed with `node rename` prints one line `<new id>: renamed from <old id>` (suggested bump `patch`); the nodes that link to it are not listed. E708 for a ref that does not resolve and for a spec folder that cannot be read at it (not a git repository, absent at the ref, outside the git root, git failing); E709 for a tree with no graph node (seeds do not count); a tree from before 1.2.0 that has ids the registry reads is compared as it is, and the result is not meaningful |

```bash
./tools/run_specdev.sh node ac-password-reset-3 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh node candidates --kind api --field derives_from --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh node status ac-password-reset-3 deprecated --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh trace ac-password-reset-3 --down --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh trace PWRESET_CONFIRM_EXPIRED_01 --recipe 16b --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh diff v1.0.0 v1.1.0 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`spec-check` also runs a `graph` check over these links: E700 to E704 (a link to an id no node has, to a node of a kind the field does not accept, to a node of a later step; a cycle within one step; an id defined twice), and, with the trace lock below, E761 (a link with no lock entry), W720 (a new link to a deprecated node), E771 and E772 (aliases, `replaces`) and E778 (a live node that uses an old id). A single-file `validate` does not report a link cycle, an unknown job in `depends_on` or an id defined in two files; `spec-check` does. Codes: [Spec Graph (70x / 72x)](error-codes.md#spec-graph-70x--72x).

Eight checks of `spec-check` read the nodes by role, the step-14 check `milestone-numbers` reads the roadmap against the milestones of step 09, and the step-14 check `removal-rules` reads the removal criteria and fixtures (codes in [Graph Role Checks (74x)](error-codes.md#graph-role-checks-74x)). On the worked example, which is a partial spec, they report role findings and `spec-check` exits 1 (the counts are in the catalogue section):

| Check | Code | Reports |
|-------|------|---------|
| `no-dangling` | E740 | A node of a requirement, delivery or context kind that no other node uses: link it; schedule it, for a kind that a step 09 milestone's `schedules` is one of the ways to use (a criterion, an FR, an NFR, an API, an invariant, a risk); or, where the kind has a `scope` field, set `scope` to `later` or `out` and give a `scope_reason` |
| `term-use` | E741 | A glossary term whose label no node of steps 04 to 15 mentions |
| `verifier-rules` | E742, E743 | A fixture that no task criterion lists in `verified_by`, or a job that none lists and that realises and verifies nothing (E742; a closed milestone's criterion counts as listing it, and so does a verification record that lists the verifier in `verifies` or an evidence record about it); a criterion, API, invariant or NFR that no fixture verifies (E743, and for an NFR a job counts too; a node that a closed milestone's task criterion `removes` is not checked; a verifier whose every binding is retired, because the environment of its stage has `scope: out`, verifies nothing) |
| `cross-cutting` | E744 | A task that an invariant or NFR applies to, when no criterion of the task refines it |
| `refinement` | E745 | A task criterion whose `verified_by` verifiers do not verify what the criterion refines (a threat or an edge case is verified through its mitigations) |
| `scaffold-paths` | E746 | A step 15 scaffold row whose file git does not track, once an API the row realises is built (merge mode; skipped outside a git repository, and when every row to check is under a submodule that is not checked out; a row under such a submodule among others is noted on stderr and not checked) |
| `seed-routes` | E747, E748, E749 | A seed no route names (E747, and only that finding for such a seed); a route no node of its step uses (E748); a link from a node to a seed the manifest does not route to the node's step (E749, one finding for each link) |
| `prose-ids` | E752 | A node id written in the text of a node, where a link belongs (nodes parked with `scope: later` or `out` are read; fields whose schema fixes the value are not) |
| `milestone-numbers` | E566, E567 | Step 14 (it replaces the 1.1.1 warnings W566 and W567, which `fr_refs` fed): an FR in scope that no task criterion reaches (E566: the task criterion refines the FR, one of its acceptance criteria or a node derived from them), and a step 09 milestone that a step 14 milestone computes and that schedules a node no task criterion refines (E567). The step gate (`spec-check --step 14`) blocks on them; `validate` and `validate-all` do not run them |
| `removal-rules` | E341, E342 | Step 14: a removal criterion (a task criterion with `removes`) and its removal fixture must name the same ids (E341), and neither may name an id the spec still has (E342); criteria of a closed milestone are not checked (the loop is in [error-codes.md](error-codes.md#graph-role-checks-74x), "Removing a node through a milestone") |

E740, E742 and E743 are coverage gaps (see `stale`, `coverage` and `step ready` below); E743 is owned by step 08, and the step gate shows a finding under PENDING (owned by a later step) until its owner step is gated. Most fixes add, change or remove a link and end with `specdev attest <node> --yes` for each node an E761 or E763 names (after a removed link, `specdev attest --prune`): the Resolutions of the catalogue say how, and which advice each message gives for which kind. A spec that has only some of its steps written fails these checks until its nodes are linked, or marked `scope: later` or `out` with a `scope_reason` where the kind has that field. A child keeps its own `scope`: an FR set to `scope: later` does not park its criteria.

**A spec that has not been migrated.** The checks run on every spec; none is skipped because the files look like 1.1.1. Run on the 1.1.1-shaped files of `tests/fixtures/spec_corpus` (steps 04, 05, 07, 08, 11 and 14, with `trace`, `targets` and `fr_refs` fields), `spec-check` ran the nine checks (none printed `[SKIP]`) and reported, besides the schema errors (E520) that the old shape causes: E740 (`criterion AC-CORPUS-001 is not used by any node; ...`), E742 (`fixture FIX-CORPUS-001 is not used: no task criterion lists it in verified_by; ...`), E743 (`api API-CORPUS-001 has no verifier: add a fixture at step 08 that verifies it and that a task criterion lists in verified_by`) and E566 (`fr FR-CORPUS-001 is in scope but no task criterion reaches it: ...`). Such a spec fails `spec-check` until it is migrated; the migration of a later step of this release maps the old shape.

### Trace lock, replay and attest

A link is accepted by the node that holds it: `spec/extras/trace.lock.json` stores, for each link (holder, field, target), the content hash and the chain stamp the target had when the holder accepted it. A link whose target has changed since is **suspect** (E763): the cause is `content_changed` when the target itself was edited and `upstream_changed` when a node above it was (the chain stamp covers what a node rests on, so an edit reaches every node below it). Replay is the work of reading each suspect link, upward first, and either editing the holder or accepting the link with `attest`. Suspect links of nodes of a closed milestone are not listed. The file is written by the commands below, not by hand, and its format is `schema/extras/trace_lock.schema.json`.

Each command takes `--repo-root`, `--spec-root` (default `./spec`), `--git-root` (default: the folder that holds `--spec-root`) and `--json`, except `lock merge`.

| Command | Purpose |
|---------|---------|
| `specdev stale [--step NN] [--diff]` | What is still to be replayed (the pending replay): the suspect links grouped by owning step in waterfall order, nodes upward first, each with its cause (`content_changed`, `upstream_changed`) and the nodes the change started from (`roots`), and the coverage gaps of each step: the nodes E740, E742 and E743 name, each under the step that owns the finding, with their count (`step 08: 0 suspect nodes, 0 suspect links, N coverage gaps`, then `coverage gap E743: ac-password-reset-1` and one line for each of the others). A link with no lock entry is not listed (E761 of `spec-check`). `--step NN` limits it to the links the nodes of that step hold; `--diff` adds, per root, the unified diff of its contract text against the text the holders accepted, recovered from git: when the holders below one root accepted different versions, each version has its diff and the line `changed above: <root> (as accepted by <holders>)`; a link that changed upstream with no root left gets one closing line that says the change above was already accepted. The diff says `no earlier version found` when no commit matches and `history unavailable` in a folder that is not a git repository. Exit 0 when it lists links (it informs; the gate is `spec-check`); an unknown step is E706, exit 1; a spec file that cannot be read is a warning on stderr (exit 0), a lock that cannot be read is E760, exit 1 |
| `specdev attest <node-id> [--field F] [--target T] [--yes] [--dry-run]` | Accept the links of a node as they are now: the lock entry of each suspect link, each link with no entry (the entry is created) and each entry that still carries the migration baseline marker (E882) is written with the hashes its target has today. The command takes no hash from the user. **Without `--yes` it prints what it would write and exits 0, writing nothing**; `--dry-run` never writes, with or without `--yes`, and the first line then ends `(--dry-run: nothing is written)`. `--target` takes an id or an alias of the target. Refused with exit 1 and nothing written: E520 for `--yes` (with or without `--dry-run`) and for `--prune` (with or without `--dry-run`) while a spec file cannot be read (a preview, bare or with `--dry-run`, still prints, with a warning on stderr that the answer may be incomplete); E764 while a node the holder links to is itself suspect (attest that one first), E765 for a node of a closed milestone, E706 for an unknown id, E704 for an id defined twice |
| `specdev attest --step NN [--yes] [--dry-run]` | The same for every node of step NN that holds a suspect link, upward first in one run. A node that is blocked (E764) is named in the error, exit 1, and the nodes that are not blocked are written |
| `specdev attest --prune [--dry-run]` | Remove the lock entries whose link no longer exists (E762), and the verification and evidence records whose every `verifies` / `about` target is gone (repeated until none dangles, so the evidence of a removed binding goes with it; a record that still has a target is kept). It writes at once, without `--yes`; `--dry-run` lists and deletes nothing. The text adds `attest --prune: removed N orphan records` and one file per line (`would remove` with `--dry-run`); `--json` carries `pruned_records` (a list, empty when no record was removed). E520 while a spec file cannot be read, with `--dry-run` as well |
| `specdev lock merge BASE OURS THEIRS PATH` | The git merge driver of the lock: merges the three versions entry by entry and writes the result over OURS. Git runs it with `%O %A %B %P`; it takes no root flags. When both sides changed one entry in different ways, the entry the common ancestor had is kept, or, when it had none, the entry with the smaller chain stamp (string order); the link is suspect again when its target changed after the kept entry. E760 for an input that is not a valid lock, E520 for a file that cannot be read |
| `specdev lock install-driver --driver-command CMD` | Set up the merge driver in the clone at the git root (`--git-root`, or the folder that holds `--spec-root`): add the line `<path of the lock relative to the git top level> merge=specdev-trace-lock` (`spec/extras/trace.lock.json merge=specdev-trace-lock` when the spec folder is `spec/` at the top level, `sub/spec/extras/trace.lock.json merge=specdev-trace-lock` for a spec folder `sub/spec`) to the file `git rev-parse --git-path info/attributes` names (`<top>/.git/info/attributes`; in the nested layout `git check-attr merge -- sub/spec/extras/trace.lock.json` then says `specdev-trace-lock`), and set `merge.specdev-trace-lock.driver` to `CMD %O %A %B %P`. Running it again changes nothing. Quote what a shell needs quoted in `CMD`, for example `'<venv>/bin/specdev lock merge'` |
| `specdev step create NN --from DRAFT [--dry-run]` | Write the file of step NN from a JSON draft that holds the whole artifact (ids of sub-items may be left out; they are minted). The draft is checked against the step's schema, every link must resolve, and the lock entries of its links are written. E767 when the step already has its file (use `json ... --id`), for steps 16 to 16c (E767 `step 16 has no spec file that step create writes`), for a draft that cannot be read or whose `$schema` is not the step's; `step create` has no `--full`. The skills write the draft outside `spec/`, at `.specdev/drafts/step_<NN>.json`, then run `step create NN --from` on it and gate the step with `spec-check --step NN` |
| `specdev step ready NN` | Exit 0 and `step NN: ready` when every step NN links to has a spec file and no pending replay (a suspect link, or a coverage gap: E740, E742 or E743); otherwise E773 with the blockers, exit 1, and a last line by the blockers of the first step: `write step NN first` for a missing file, `replay step NN first` for suspect links, `fix the coverage gaps of step NN first` for coverage gaps only, `replay step NN first and fix its coverage gaps` for both; E520, exit 1, when a spec file cannot be read. `--json` adds `ready`, `upstream`, `replay_first` and `blockers`. The step's own file is not required. When NN has no spec file yet, the steps checked, for presence and for pending replay, are its declared inputs (the `required_spec_inputs` of NN in `tools/step_order.json`); run on copies of the worked example with the files from step K on removed, `step ready` printed `ready` for K = 02, 04 and 05, `not ready, 1 blocker` (step 07: `coverage gap E740: metric-reset-completion-rate`) for K = 08 and 09, and `not ready, 11 blockers` (steps 07, 08 and 12) for K = 14. |
| `specdev coverage [--by fr]` | Information, no gate: exit 0 when it shows the counts and unlinked ids; a spec file that cannot be read is a warning on stderr, a lock that cannot be read is E760, exit 1. How many FRs have an API, how many have a fixture and how many capabilities have an FR, with the ids that are not linked; the criteria that have a current refinement; and the exempt FRs, capabilities and criteria (lifecycle `not_applicable`, scope `later` or `out`), which no count includes. A `Role findings` section lists the coverage gaps (E740, E742, E743) by owner step, with a count of each code (`E740: N`, `E743: N`). `--by fr` prints, per FR and criterion, the nodes that link to it directly, each with `current`, `suspect` and `historical` in `--json` (the text prints `[not current, suspect]` for a suspect link). No rule requires an FR to have an API |

```bash
./tools/run_specdev.sh stale --step 05 --diff --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh attest --step 05 --yes --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh lock install-driver --driver-command './devspec_env/bin/specdev lock merge' --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh step ready 06 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`spec-check` reports the lock in two checks: `graph` (E761 for a link with no entry, W720) and `trace-lock` (E760 for a lock that cannot be read, E762 for an entry with no link, E763 for a suspect link, E882 for a baseline marker that was not re-attested). `validate-all` reports E760 to E763, E778, E882 and W720 (it does not run the `graph`, `computed-fields` or `records` checks of `spec-check`). `forward-replay-check` was removed in 1.2.0 (it exits 2 and points to `specdev stale` and `specdev spec-check`). Two more `spec-check` checks belong to this family: `computed-fields` (E768 for a stored computed field such as `content_hash`) and `records` (E774 for an invalid record file, or for a `proves` id of a verification record that names no node; E330 and E334 for a stored binding whose stage no longer fits the nodes it proves). The `open-items` check reports the open items of the spec (W630); see `specdev upstream-backlog` below.

**Verification and evidence records** are the files `spec/extras/verification/ver-<id>.json` and `evd-<id>.json`. Each is `{"$schema": "vc:extras:verification-record" | "vc:extras:evidence-record", "records": [one record]}`, and the file name is the record id. The worked example has `ver-password-reset-expired-token.json`. A record is a node of role `record`: its `verifies` (or `about`) link is resolved by the `graph` check (E700 for an id no node has) and needs no lock entry; `records` reports E774 for a file that is not valid. A **verification record** (a binding) is written by `specdev verify bind` and holds the verifier it covers (`verifies`), the nodes it proves (`proves`, plain data: an id there is not a link), its `stage`, its `commands` and the `output_guard` their output must match. An **evidence record** is written by `specdev verify run` (`type: run`) or `specdev third-party check --installed` (`type: install-check`): what ran (`about`), at which `stage`, on which code tree (`tested_tree`), with the exit code, whether the guard matched, the `installed_versions` and the `recorded_hashes` of the nodes at the time. The commands are in "Verification runs and third-party pins" below.

**Interim state** until a later 1.2.0 change: `lock install-driver` is not run by any setup script, so a host has to run it once.

### Verification runs and third-party pins

A verifier (a fixture of step 08, a job of step 12 or a rule of step 10) is **bound** to the commands that prove it and the output they must print: that binding is a verification record. A **run** of the binding writes an evidence record for it. The records are described under "Verification and evidence records" above; the optional host file `spec/common/host_declarations.json` (the paths the code-tree id leaves out, where the repository declares each third-party version) is described in [`host_declarations.md`](host_declarations.md).

Each command takes `--repo-root`, `--spec-root` (default `./spec`), `--git-root` (default: the folder that holds `--spec-root`) and `--json`.

| Command | Purpose |
|---------|---------|
| `specdev verify bind <verifier-id> --command CMD [--command CMD ...] --guard REGEX [--proves ID ...] [--stage dev\|ci\|staging\|prod] [--id ver-ID]` | Write the verification record of a fixture, a job or a rule: the commands (repeat `--command`; they run in order), the regular expression their output must match (`--guard`, required: the only protection against a command that exits 0 and ran nothing), the nodes it proves (`--proves`; default every node the verifier proves) and its stage, which is the highest stage those nodes need (an NFR its own `stage`, a job the stage of the environments it realises, anything else `dev`). It writes `spec/extras/verification/<id>.json` and nothing else: never a spec file or the lock. Binding the same verifier and nodes again replaces the record. Exit 0 written, 1 refused: E330 for a `--stage` that is not the one the nodes need, E331 for a `--proves` id the verifier does not prove, E332 for a missing or invalid guard, E333 for a node that another binding of the verifier proves, E334 for an environment that is not a stage, E767 for a verifier that cannot be bound (not a fixture, job or rule; a manual fixture; nodes that need different stages without `--proves`), E706 for an unknown id. Run: `fix-password-reset-expired-token: binding ver-password-reset-expired-token replaced (stage dev, extras/verification/ver-password-reset-expired-token.json)`, then `  proves: ac-password-reset-3, api-password-reset-confirm` and a line that names the stage each node needs |
| `specdev verify run [ver-ID ...] [--all \| --milestone ms-ID] [--stage dev\|ci\|staging\|prod] [--only-stage] [--no-record] [--installed TP=VERSION ...] [--timeout SEC]` | Run the commands of the named bindings (`--all`: every binding; `--milestone`: the bindings of the verifiers its task criteria list in `verified_by`; exactly one of these three ways, else a usage error, exit 2) in a shell at the host root, and write one evidence record for each: `spec/extras/verification/evd-<binding>-<stage>.json`, overwritten by the next run. A binding passes when its commands exit 0 and the output matches its guard. `--stage` (default `dev`) is the stage the run executes in: bindings of that stage or below run, and a named binding above it is E767; `--only-stage` keeps the bindings of exactly that stage. Bindings with the same commands and guard run once. `--timeout SEC` kills a command that runs longer (exit 124 in the record). `--no-record` writes nothing; the run is the proof. `--installed TP=VERSION` records the version a deploy installed instead of the one the working tree declares. The record holds the code-tree id of the host (`tested_tree`), so a later change to the code makes it stale. Exit 0 when every binding passed, 1 when one failed (or E520 for an unreadable `host_declarations.json`, E706 for an id that is not a binding). W350 (a submodule with uncommitted content) and W351 (the run changed the code tree) are warnings on stderr. Run: `PASS ver-password-reset-expired-token at dev` and `1 run, 1 passed, 0 failed`; with a failing guard `FAIL ver-password-reset-expired-token at dev (guard not matched)` and exit 1 |
| `specdev third-party pin <tp-id> <version>` | Write `<version>` as the `pin` of a third-party node, through the id-keyed write path: the node's hash changes, so the links into it become suspect (see `specdev stale`) and the command prints how many, by step. The version must be exact (a version, a commit or a contract id): `latest`, an empty value, `*`, an x-wildcard and a range are E336, nothing written. The code change itself is made in the branch, through a change milestone, which the last line says. Exit 0 written, 1 refused (E706 for an unknown id). Run: `patched tp-argon2 (02_system_sketch.json .third_parties[0])`, then `newly suspect: 14 links (step 05: 1, step 06: 1, step 08: 2, step 11: 5, step 14: 3, step 15: 1, step 16a: 1); see `specdev stale``, on the worked example |
| `specdev third-party check` | With no flags: compare the `pin` of every third party that declares `pin_sources` in `host_declarations.json` with the version each source reads from the working tree, and print `every pin matches its declared sources` (or `no pin sources are declared; nothing checked` when the file declares none), exit 0; E336 for a pin that is not exact, E337 for a pin that differs from a source, E338 for a source that gives no version (or a `pin_sources` key that is no third-party node), each a line, exit 1. Writes nothing |
| `specdev third-party check --installed TP=VERSION [TP=VERSION ...] --env ENV [--tag TAG]` | The deploy form: compare what a deploy installed with the pins (`--env` is required with `--installed`, else a usage error, exit 2). A version that is not the pin is E339, exit 1 (which stops the deploy), and nothing is written. When all match, it writes one `type: install-check` evidence record for each third party, `evd-install-<name>-<env>.json` (`<name>` is the node id without `tp-`), as an audit trail that no check reads yet. Run: `tp-argon2: installed 0.42.0 is the pin; recorded extras/verification/evd-install-argon2-prod.json` |

```bash
./tools/run_specdev.sh verify bind fix-password-reset-expired-token --command "npx vitest run" --guard "expired token .*passed" --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh verify run --all --stage ci --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh third-party pin tp-argon2 0.42.0 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
./tools/run_specdev.sh third-party check --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

`spec-check` reads the records in its `records` check (see above); a binding that no run has covered is not an error of `spec-check`. The findings that say a binding has no valid evidence (E347, E348) are returned by the library function `proof_errors` for the close and release gates, which no command runs in this release.

### Registry, Canon & Prompt Maintenance Commands

| Subcommand | Purpose |
|------------|---------|
| `specdev seed-index spec_dir [--git-root GIT_ROOT] [--json]` | Report seed-doc reference index/coverage across spec artifacts |
| `specdev prompt-sync [spec_dir] [--spec-root SPEC_ROOT] [--git-root GIT_ROOT] [--json]` | Check prompt files are in sync with their canonical templates |
| `specdev canonical-autofix spec_dir [--canon-dir CANON_DIR] [--write \| --dry-run] [--json]` | Auto-fix canonical-reference issues; defaults to reporting only — pass `--write` to persist |
| `specdev glossary-drift-check spec_dir [--spec-root SPEC_ROOT] [--git-root GIT_ROOT] [--json]` | Validate definition parity across glossary terms, canonical proposals, and the canon registry |
| `specdev registry-check --spec-root SPEC_ROOT [--repo-root REPO_ROOT] [--git-root GIT_ROOT] [--json]` | Validate `entry_key_registry.json`: coverage, phantom basenames, and drift against live spec files (R003) |
| `specdev registry-generate --repo-root REPO_ROOT [--out OUT] [--extraction-paths-out PATH] [--cli-commands-out PATH] [--step-order-out PATH] [--checklist-out PATH]` | Regenerate `entry_key_registry.json` + `extraction_paths.json` + `step_order.json` + `cli_commands.json` and `docs/developers/schema-change-checklist.md` from toolkit schemas, annotations and the CLI parser (byte-deterministic; run after any schema, annotation or parser change — see CLAUDE.md). `--step-order-out`, `--cli-commands-out` and `--checklist-out` each default to their file (`tools/step_order.json`, `tools/cli_commands.json`, `docs/developers/schema-change-checklist.md`) only when `--out` is absent. With no annotated step, when the annotation lint finds issues, or when `tools/schema_changes.json` is malformed, the command exits 1 and prints `registry-generate: failed:` with the reason. Annotation reference: [schema-annotations.md](schema-annotations.md) |
| `specdev guide <CODE> [--json]` | Show the remediation playbook for an error/warning code, e.g. `specdev guide E110` or `specdev guide E530-INVENTED_ENUM_OR_ID` |
| `specdev hardcoded-seed-check [--repo-root REPO_ROOT] [--git-root GIT_ROOT] [--json]` | Detect literal seed-doc filenames hardcoded in prompts (W554 regression guard); with `--git-root` also scans `<git-root>/prompts/` for submodule deployments |
| `specdev upstream-backlog spec_dir [--severity {low,medium,high,critical}] [--status {open,resolved,all}] [--json]` | List every open ambiguity item of the spec (read-only), from the step files 00 to 15, the anchor and the `plan.ambiguities[]` and `execution.emergent_ambiguities[]` of the milestone plans, grouped by the step of the nodes the item is `about`. A seed item is grouped under `seed`; an item about nodes of several steps is listed in each group and counted once; an item none of whose `about` ids names a node, and an item of the 1.1.1 shape whose `impact[]` names no step, is listed under `unplaced` and fires W613. Each record says whether the answer is known (the item has a `decision`) or needed from the operator. `--severity` and `--status` filter items of the 1.1.1 shape only; an item with `about` is always listed. `--json` has `schema_version` `"2"`. An artifact that cannot be read (bad JSON, no permission, a folder named like a step file: `E520 UNRESOLVED_INPUT <path>: <reason>`), or a spec folder that does not exist (`E520 UNRESOLVED_INPUT missing_spec_dir <dir>`), stops the run with E520 and exit 2. An item that cannot be reported (no id: `missing_id`; neither `about` nor a valid severity: `item has neither about nor a valid severity`; a severity outside the scale of its step: `invalid_severity='low'`) prints one E520 line on stderr with the file, the step and the item id; the run goes on, the other items are listed and the JSON is printed, and the exit code is 2. A `decision` of spaces only counts as no answer. It takes `--repo-root` and accepts `--spec-root` and ignores it; it does not accept `--git-root` |
| `specdev canon-accept --from SPEC_FILE [--namespace NAMESPACE] [--owner OWNER] [--repo-root REPO_ROOT] [--git-root GIT_ROOT] [--dry-run] [--json]` | Promote `canonical_proposals` from a spec file into `canon/manifest.json`; with `--git-root`, writes project canon to `<git-root>/spec/canon/` instead (accepts `--git-root`, not `--spec-root` — see CLAUDE.md exception list) |

### DAG & Extraction Intent Commands

#### `dag-lint`

Validates the completeness and consistency of the dependency DAG defined in `tools/step_order.json` (a generated file; see `registry-generate`). This is a standalone command — it is **not** included in `validate-all`.

**What it checks:**
- Every non-terminal step has at least one `downstream_consumers` entry (E596 DAG_DEAD_END_PRODUCER). Steps 03 and 16c are exempt: 16c is the terminal step, and the generated order lists no consumer for the glossary (03).
- Every `downstream_consumers` entry is consistent with the computed step ordering (E599 DAG_CONSUMER_INCONSISTENCY). If step X lists Y as a consumer, Y must appear after X in the `steps` list.
- No circular dependencies in the computed upstream graph (E585 DAG_CIRCULAR_DEPENDENCY).
- Prompt extraction intent entries reference only computed upstream steps (W596 UNDECLARED_UPSTREAM_REF).

**When to run:** After running `registry-generate` (which writes `tools/step_order.json`) or after changing any prompt's `### Extraction Intent` section. Also runs automatically via pre-commit hook and CI gate.

#### `extraction-intent-check`

Validates that each prompt's `### Extraction Intent` section is consistent with `tools/step_order.json`: an entry may name only a step that the `steps` list holds (E598 otherwise), and every step in the current step's `step_metadata.required_spec_inputs` needs an entry (E597 otherwise). It also reports an empty section (E591: the `### Extraction Intent` header is present and neither a step entry nor a manifest-anchored seed bullet, `- **Seeds**: per spec/common/seed_manifest.json step_requirements[...]`, parses) and vague intent text (W597). A prompt without that header is skipped with no message. An entry that names a step which does not precede the current one is reported by `dag-lint` (W596), not by this command.

**What it checks:**
- Every allowed upstream dependency has a corresponding extraction intent entry (E597 EXTRACTION_INTENT_UPSTREAM_GAP).
- Extraction intent entries reference valid steps (E598 EXTRACTION_INTENT_INVALID_REF).
- Intent text is specific (W597 EXTRACTION_INTENT_VAGUE — fewer than 10 words or contains weasel words).
- Extraction intent sections are non-empty when present (E591 EXTRACTION_INTENT_EMPTY).

**When to run:** After adding or modifying `### Extraction Intent` sections in prompts.

#### `env-check`

Read-only diagnostic that prints the active validation configuration. Modifies no state.

**What it displays:**
- All active `SPECDEV_*` environment variables and their values.
- W→E promotion status: ALL (every registered pair via `SPECDEV_WARNINGS_AS_ERRORS=1`), SELECTIVE (per-code via `SPECDEV_PROMOTE_CODES`), or OFF. The live pair count is printed from `PROMOTABLE_PAIRS`.
- The replay base ref: the value of `SPECDEV_REPLAY_BASE_REF`, or `(auto-resolved)` when it is not set (the step gate and `specdev diff` then resolve it as described under `--base-ref`).
- Spec directory and step_order.json paths.

**When to run:** When troubleshooting CI failures related to W→E promotion, replay base ref, or configuration issues.

#### `milestone-state`

Deterministic milestone-state computation for the Trinity loop. Reads
`spec/impl_context/ms_<batch-id>_plan.json`, probes `.specdev/findings/` under the host
git root, and emits a single JSON object to stdout.

This command replaces the LLM-evaluated `milestone_state` mode of the `specdev-scope` agent
(DEVSPEC-38, D7/D7a). The `specdev-scope` agent now delegates to this command and passes its
output through unchanged, so the output contract is identical for skills that parse it.

**Flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `--batch-id BATCH_ID` | Yes | Milestone batch identifier (e.g. `phase2_newsletter_send`) |
| `--repo-root REPO_ROOT` | No | Toolkit root directory (schema tier). Default: cwd |
| `--spec-root SPEC_ROOT` | No | Host spec directory used to locate `spec/impl_context/ms_<batch-id>_plan.json`. Default: `<repo-root>/spec` |
| `--git-root GIT_ROOT` | No | Host repo git root used to locate `.specdev/findings/` (host-relative, NOT under spec-root). Default: `<repo-root>` |

**Output contract** (JSON to stdout):

```json
{
  "milestone_id": "<string>",
  "groups": [
    {
      "group_id": "<string>",
      "state": "<pending|code_converged|blocked|verified|deferred|wont_do>",
      "implementation_converged_at": "<ISO8601 or null>",
      "reviewer_rounds": "<integer>",
      "findings_resolved_path": "<path or null>",
      "blocking_amb_ids": ["<string>"],
      "blocking_amb_health": [{"id": "<string>", "status": "<string>", "resolved": <boolean>, "well_formed": <boolean>}],
      "fixtures_exercised": ["<string>"]
    }
  ],
  "derived_phase_position": "<pending|impl_in_progress|impl_complete|review_pending|review_complete|operator_pending|closed>",
  "blockers": [
    { "kind": "ambiguity", "id": "<string>", "issue": "<string>" }
  ]
}
```

**Submodule deployment:**

```bash
specdev milestone-state \
  --batch-id phase2_newsletter_send \
  --repo-root ./devspec_toolkit \
  --spec-root ./spec \
  --git-root .
```

**When to run:** When debugging Trinity loop state, verifying phase-position transitions, or
smoke-testing the `specdev-trinity` skill's milestone dispatch.

> **Note:** The former `specdev-trinity-plan` skill no longer exists as a separate skill;
> its plan-phase functionality is now `/specdev-trinity <batch_id> --phase plan` (the default
> phase — see `.claude/skills/specdev-trinity/SKILL.md`).

### Version Update & Migration

```bash
# Sync to current toolkit version (re-stamp or direct to align)
specdev update spec --repo-root ./devspec_toolkit

# Preview what update would do without writing any files
specdev update spec --repo-root ./devspec_toolkit --dry-run
```

**`update` flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `spec_dir` | Yes | Path to the project `spec/` directory (positional) |
| `--repo-root REPO_ROOT` | No | Toolkit root directory. Default: cwd (`.`) |
| `--dry-run` | No | Report what would be done without writing any files. The re-stamp path reports `update_status: would_update` (no write); a migration-requiring diff reports `needs_migration` |
| `--json` | No | Emit a JSON envelope (`status`, `update_status`, `from_version`, `to_version`, `dry_run`, …) instead of plain text |

When `specdev update` reports schema changes, run the migration workflow first:
```bash
# Check status of spec vs toolkit version
specdev align status spec --repo-root ./devspec_toolkit

# Show diff of what needs to change
specdev align diff spec --repo-root ./devspec_toolkit

# Generate an execution plan
specdev align plan spec --repo-root ./devspec_toolkit

# Apply mechanical fixes (auto-mode)
specdev align apply spec --auto --repo-root ./devspec_toolkit

# Generate prompts for AI-assisted migration
specdev align prompts spec --output prompts/migration/ --mode upgrade --repo-root ./devspec_toolkit

# Finalize: full post-migration validation + version stamp (with migration history)
specdev align validate spec --repo-root ./devspec_toolkit

# Restore spec/ from a migration backup (non-interactive)
specdev align rollback spec --repo-root ./devspec_toolkit --backup-dir <backup-name> --yes
```

> Finalize a migration with `align validate`, not by re-running `specdev update`. `validate` stamps `spec/specdev_version` only after schema + trace-integrity checks pass and records a `migration_history` entry; `update` re-stamps after a weaker structural-diff check and omits the audit trail.

> `align rollback` restores `spec/` from a backup in `spec/migration_backups/`. Without `--backup-dir` it lists available backups and prompts interactively for a selection — `--yes` alone does **not** make this non-interactive-safe; it only skips the early guard and the final confirmation prompt, not the backup-selection `input()` call, which still raises on non-interactive stdin. Pass `--backup-dir <name>` as well to bypass interactive backup selection entirely and restore that backup directly. `--json` is not yet supported for this action.



### Step-Specific Verification
The toolkit's own step tests run with `pytest`. Most of the step test files are also scripts that check one file given as the argument (for example step 12: DAG and cycles; step 15: `validate`). Run them from the toolkit root, because the `validate` scripts read the argument relative to it; each line below changes directory only for its own command:
```bash
(cd devspec_toolkit && pytest tests/integration/test_step_02.py -v)
(cd devspec_toolkit && python tests/integration/test_step_12.py tests/fixtures/step_12/valid_dag.json)
(cd devspec_toolkit && python tests/integration/test_step_15.py tests/fixtures/step_15/valid_full.json)
```

Invoke commands from the root of your host repository so relative paths to `spec/` and [./devspec_toolkit/](../../) resolve cleanly.

## Strict Execution Policy
- Workflow is forward-only.
- There is no refinement mode.
- Any accepted upstream change is replayed through the steps below it before merge. The replay is the set of suspect links of the trace lock (`specdev stale`): each is read and either the holder is edited or the link is accepted with `specdev attest`, upward first. `spec-check` reports a suspect link as E763 and a link with no lock entry as E761, both as errors.
- File-level forward replay (a changed step N requires a changed file for every later step) was removed in 1.2.0, with `forward-replay-check`, `spec-check --include-forward-replay` and `SPECDEV_REPLAY_DIFF_ERROR_MODE`. The trace lock replaces it.
- In strict mode, host-repo CI should run quality, hallucination, dependency-order, and `spec-check` (which includes the trace-lock checks) as blocking gates.

## Two-Phase AI Runner Mode
- Prompts support a two-phase flow: Clarify (questions only) → Emit (disk-first JSON artifact write).
- Agents follow the prompt’s “Operating Flow”, apply the “Self‑Audit Gate”, and ask targeted questions if gating items are missing. Agents read the “Context To Ingest” section for steps that include it; steps that use “Coverage Closure” apply that section instead.
- Runners should honor the manifest interaction hints: see `docs/agents/manifest.json` (`interaction_mode: two_phase`).
- Operational guidance for agents and runner tips: `docs/agents/agents.md`.

## Validation Workflow
1. Edit the JSON artifact.
2. Run `validate`.
3. Run `seed-lint` to ensure required seed context is referenced and current.
4. If any link changed, run `spec-check` (the role rules E740 to E745 report what is not linked) and lint fixtures.
5. Update governance-compliant commit messages per `spec/10_governance.json`.

## Troubleshooting Checklist
- **Schema not found**: run from repo root or configure `--repo-root`; confirm [tools/schema_registry.json](../../tools/schema_registry.json).
- **Fixture without a link**: every fixture needs `verifies` (ids of acceptance criteria, APIs, invariants or NFRs) or `removes`; `targets` is no longer part of the schema.
- **Invariant evaluation null**: check referenced keys in fixtures or adjust the invariant expression.
- **Governance rejection**: match the commit pattern defined in Step 10 (`governance-check` reads only `commit_message_rules`).
- **Step 10 schema failure**: each `rules[]` entry needs `rule_id`, `text` and `derives_from`; `validate` reports a missing one.
- **Glossary failures**:
  - `minItems` error: Ensure `terms` array has at least one item.
  - `minLength` error: Definitions must be >20 chars.
  - `pattern` error: Check `domain` (kebab-case) and `units` (alphanumeric/slash) formats. no empty strings allowed.
- **Implementation Plan failures**:
  - `milestones` error: Ensure every milestone has a `schedules` array with at least one id.
- **Red Team (Step 11) failures**:
  - `threatens` error: Every threat needs at least one id of an API, component, connection or third party.
  - `mitigated_by` error: An edge case needs at least one id in `mitigated_by`; on a threat it is optional.
- **Scaffold (Step 15) failures**:
  - `duplicate row_id`: Each `interface_map[]` row needs its own `row_id`; an API may be realised by several rows.
- **Canon/schema alignment failures** (`canon-schema-alignment`); see [error-codes.md](error-codes.md#canonschema-alignment-55x) for the authoritative E551-E554 definitions:
  - `E554 CANON_ENUM_DRIFT`: Canon kind has entries missing from the paired schema enum.
  - `E551 SCHEMA_ENUM_EXTRA`: Schema enum has values not present in the paired canon kind.
  - `E552 MISSING_PAIRED_SCHEMA`: Schema file referenced in pairing config not found.
  - `E553 MISSING_ENUM_PATH`: JSON path referenced in pairing config not found in schema.
  - `W552 POTENTIAL_UNREGISTERED_PAIRING`: Unregistered schema enum has high overlap (>=80%) with a canon kind; consider adding an explicit pairing.

## Architecture Notes

### `step_order.json` schema changes
- `tools/step_order.json` is generated by `specdev registry-generate`; do not edit it by hand. The hand-carried keys are `version`, `steps`, `policy` and `declared_edges` (`[producer, consumer]` pairs for context reads no stored link carries).
- `downstream_consumers` maps each step ID to the list of step IDs that consume its output (e.g., `"04": ["05", "06", ...]`), derived from the `x-link` declarations of the step schemas plus `declared_edges`. `prompt-context` and `context` read it.

### `prompt-context` output format
The `prompt-context` command now outputs a 2-column table (`Step`, `Name`) instead of the previous 3-column format (`Step`, `Name`, `Extraction Intent`). Consumer lists are derived from the `downstream_consumers` field in `step_order.json`.

## Related Resources
- [index.md](index.md) — Navigational overview of every document set.
- [getting_started.md](getting_started.md) — Single-path onboarding for new team members.
- [workflows/discovery.md](workflows/discovery.md) & [workflows/spec_to_impl.md](workflows/spec_to_impl.md) — Conceptual phase breakdowns.
- [../agents/agents.md](../agents/agents.md) — Automation contract used by AI assistants.
- [schema-annotations.md](schema-annotations.md) — Graph annotation language (`x-node`, `x-link`, link verbs, lifecycle and scope fields) defined by `schema/core/graph.schema.json`.
