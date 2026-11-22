# Migrating a 1.1.1 host to 1.2.0

This guide is for a person who owns a host repository whose `spec/` was written for toolkit 1.1.1 and who has not seen this release. It lists the work in the order you do it, each step with the command and what the command prints. Every command below was run on a copy of a small invented host; the counts it prints for your host will differ, and a block that shows only some of the printed lines says so (`...` or "excerpt").

The release changes the shape of every step file, so a 1.1.1 spec does not validate against the 1.2.0 schemas. The migration has two stages:

1. **The mechanical stage** is one command, `specdev align apply --auto`. It rewrites `spec/` (ids, link fields, removed fields, the lock, the legacy close) and writes a list of the decisions it could not take. It runs in a few seconds and writes nothing outside `spec/`.
2. **The judgement pass** is yours. For each decision on the list, and for each link the migration wrote but nobody has accepted, a person (or an agent that a person reviews) reads the spec, edits it with the id-keyed commands and accepts the result. This is where the work is: see [Sizing](#sizing) for how much.

Nothing is committed for you. The migration is reviewed with `git diff` and undone with `git checkout -- spec && git clean -fd spec` (the second command removes the files the run created; a rerun after only `checkout` stops with `E881` on the leftover files).

Related documents: [`host_setup.md`](../host_setup.md) (what `update` installs into a host), [`host_declarations.md`](../host_declarations.md) (the optional host file the migration asks you to write), [`reference.md`](../reference.md) (every command), [`error-codes.md`](../error-codes.md) (every code named below), [`tools/align.md`](../tools/align.md) (the `align` actions).

## Before you start

- Work in a clone, on a branch off your default branch. The default branch must hold the 1.1.1 spec: the merge check at the end measures the branch against it (`--base-ref <ref>` names another base).
- `git status --porcelain spec` prints nothing. A run on a spec with uncommitted changes is refused with `E880` unless you pass `--allow-dirty`.
- The toolkit submodule is at 1.2.0 and the venv is active (`source devspec_env/bin/activate`).
- `spec/specdev_version` exists and records `toolkit_version: "1.1.1"` (or the version your spec was built with). On a host with no stamp, or a stamp without `toolkit_version`, write that line into the file and commit it before anything else, and **do not run `specdev update` first**: on a spec with no stamp `update` stamps the toolkit's version, and the migration then reads the spec as already migrated and never runs (`align apply` refuses such a spec with `E880` and says the same).
- Every command below is given with the flags a submodule deployment passes (`--repo-root` for the toolkit, `--spec-root` for the host's spec, `--git-root` for the host). A command that rejects a flag is run without it: `align` takes no `--spec-root`.

```bash
export TK=./devspec_toolkit      # the toolkit root, as in the rest of the docs
specdev update spec --repo-root $TK --git-root . --dry-run
```

This run writes nothing (`git status` stays clean). On a 1.1.1 host it does not re-stamp `spec/specdev_version`: it prints the warnings of the host-file scan first (W930, W932, W935), then why the spec needs a migration and the order of the commands to run (exit 1), then the lines of what `update` would install:

```
The spec needs a migration, not a re-stamp (v1.1.1 -> v1.2.0): 24 migration script(s) are registered for v1.1.1 -> v1.2.0: p1_capture, p2_id_collisions, ...
spec/specdev_version is left as it is. Run, in this order:
  1. specdev update spec --repo-root ... --no-install --dry-run
  2. specdev align apply spec --auto --dry-run --repo-root ...
  3. specdev align apply spec --auto --repo-root ...
  4. git add spec && git commit --no-verify -m "Migrate the spec to toolkit v1.2.0"
  5. specdev update spec --repo-root ... --adopt
  6. specdev align triage spec --repo-root ...
  7. specdev align validate spec --repo-root ...
```

The seven lines are this guide in short (the command of line 1 is the same run with `--no-install`, which skips the host-file scan and so prints no warning; use the command above). The scan prints one `W932 HOST_RETIRED_COMMAND` warning for each line of your hooks and workflows that calls a command 1.2.0 removed (`matrix`, `forward-replay-check`, `completeness-check`, `traceability-check`) or replaced (`validate-all` is superseded by `spec-check`):

```
W932 HOST_RETIRED_COMMAND: .github/workflows/spec_validation.yml:11: 'validate-all' was removed in 1.2.0; superseded by `specdev spec-check` (run it with --merge on a pull request)
W932 HOST_RETIRED_COMMAND: .github/workflows/spec_validation.yml:12: 'matrix' was removed in 1.2.0; use `specdev coverage --by fr` for the FR view and `specdev trace --up|--down <id>` for lineage
```

**Edit those lines by hand now**, hooks first: a hook that calls `matrix` refuses every commit once the toolkit is updated, and `validate-all` still runs but reports false `E110`s on a 1.2.0 spec. The detector does not see a command on the line after a trailing backslash: read your multi-line shell steps yourself. The migration writes only under `spec/`.

## Step 1: the dry run

```bash
specdev align apply spec --auto --dry-run --repo-root $TK --git-root .
```

The run happens on a scratch copy of `spec/` and the seed files; nothing is written to your tree (and a dry run is allowed on a dirty `spec/`). It prints one line per script and the totals, then the diff of every file it would change (the diff is the long part; the lines below are the top of the output):

```
migration 1.1.1 -> 1.2.0 (dry run, nothing written)
  p1 p1_capture: 2 edit(s), 0 worklist item(s)
  p2 p2_id_collisions: 8 edit(s), 4 worklist item(s)
  ...
  p6 p6_baseline: 73 edit(s), 0 worklist item(s)
  p7 p7_host_files: 5 edit(s), 5 worklist item(s)
total: 614 edit(s), 91 worklist item(s), 28 file(s) changed
```

`--json` prints the same as a document (`status`, `edits_by_script`, `worklist_items`, `residue`, `errors`). Each script the run lists has a one-sentence description in the changelog of 1.2.0, the file `changelog/v1.2.0.md` of the toolkit (the entries "Migration script `<id>`").

## Step 2: the real run

```bash
git switch -c migrate-to-1.2.0
specdev align apply spec --auto --repo-root $TK --git-root .
```

It prints the same lines without "(dry run)", ends with the changes the scripts do not make for you (a list of `paradigm_shift` and `change_schema` descriptions from the changelog, for reading), and then four closing lines: `review: git diff --stat spec`, `undo:   git checkout -- spec && git clean -fd spec`, the commit command of step 3 with the reason it needs `--no-verify`, and `next:   specdev align triage spec`. What it did:

- It rewrote the step files in place, keeping each file's own indentation. Ids were minted where 1.1.1 had none (from the item's text; a text with no ASCII letter or digit gets a numbered id such as `risk-1`, which `specdev node rename` can change later); link fields replaced `trace`, `fr_refs`, `targets`, `scope.components` and the like; removed fields are gone; step 13a and `spec/extras/trace_matrix.json` are deleted; a host canon kind `inv` is renamed `invariant`. Every plan under `spec/impl_context/` gained its `milestone` key.
- A milestone that 1.1.1 called done (the roadmap says done, the anchor row says done, or the plan's review verdict is verified) was closed with a `legacy-migration` close record and its plan was frozen.
- It wrote `spec/extras/trace.lock.json`: one entry per link that resolves, each marked `baseline` (the hashes are the ones the migrated spec has; nobody has accepted them).
- It wrote `spec/extras/migration/capture.json` (a copy of what it removed, and where to read the rest in git) and `spec/extras/migration/worklist.json` (the decisions left). Both are tool-owned: do not edit them by hand; `align validate` deletes them at the end.
- It stamped `spec/specdev_version` with `toolkit_version: 1.2.0` and `migration_status: in_progress`.

Run the command a second time and it reports `nothing to do` for every script and changes no byte. It is allowed on the dirty tree for that reason: the stamp says the migration is in progress. If a run stops with `E881` (a script broke an invariant), nothing was written: the message names the script, and `git status` is clean.

Check the result before you go on:

```bash
specdev spec-check spec --repo-root $TK --spec-root ./spec --git-root .
```

On the invented host the errors fall from 559 to 278 (the merge check, which reads more, prints 285). [Sizing](#sizing) has the numbers of two real hosts. The codes that mark a shape the scripts must have fixed (`E768`, `E704`, `E761`, `E622`) are gone. What is left is the judgement pass.

## Step 3: the one commit

```bash
git add spec
git commit --no-verify -m "Migrate the spec to toolkit v1.2.0"
```

`--no-verify` is needed because your pre-commit hooks are still the 1.1.1 ones: they name retired commands, and the spec does not pass the 1.2.0 checks yet. This is the only commit made with it. It gives you a clean tree, a base for `git diff` through the pass, and one commit to revert.

## Step 4: install the host files

```bash
env PATH="$(dirname "$(which python)"):/usr/bin:/bin" specdev update spec --repo-root $TK --git-root . --adopt
```

(The `env PATH` prefix only matters in a scratch copy, where `update` would otherwise run `uv pip install` into the active venv; in your own host run `specdev update spec --repo-root $TK --git-root . --adopt`.) With the stamp in progress it re-stamps nothing, installs the host pieces and prints:

```
A migration is in progress: spec/specdev_version records v1.2.0 with migration_status: in_progress, ...
Host install:
  pre-commit: refreshed (1 hand-written hook(s) replaced by one marked block)
  merge-driver: created (merge driver 'specdev-trace-lock' set in the clone's git config)
  workflows: created (written from the template)
  wrappers: created (tools/run_specdev.sh: created; tools/ensure_venv.py: created)
  claude-links: created (17 linked)
  ask-rules: created (10 ask rule(s) added to .claude/settings.local.json)
  gitignore: created ('.specdev/' added to .gitignore)
```

`--adopt` replaces the hand-written toolkit hooks of `.pre-commit-config.yaml` by one block the toolkit owns. The merge driver and the ask rules live in your clone, not in the repository: **run `update` in every clone** that will touch the spec. The ask rules go into `.claude/settings.local.json`, which the installer keeps out of git when nothing ignores it. A host that tracks that file will see it as modified: commit it or restore it as you decide. `claude-links` is `created` the first time and `current` when the host already has every link; the links are the symlinks in `.claude/`. Commit the rest (`.pre-commit-config.yaml`, `.github/workflows/`, `tools/`, `.gitignore`, `.claude/`) as a second commit. [`host_setup.md`](../host_setup.md) lists every piece.

## Step 5: read the list

```bash
specdev align triage spec --repo-root $TK --git-root .
```

```
Worklist: 91 open item(s), 33 blocking; 0 resolved

operator (25 open):
  BLOCKING  wl-00-decisions-seed-seed-decision-clarifications
      step 00, decisions-seed, about seed-decision-clarifications
      evidence: the seed manifest lists seed-decision-clarifications (docs/seed/seed_decision_clarifications.md), which holds decisions; ...
      proposal: fold what it decides into the seeds that own each subject, then remove its entry ...
  ...
agent (66 open):
  ...
```

(An excerpt: each `...` stands for lines the command prints.)

Each item has an id, a step, a kind, the node or file it is about, the evidence the script saw and, when it has one, a proposal. **operator** items need a decision of a person. **agent** items are ones an agent can work out from the spec and propose, which a person confirms. `BLOCKING` is a display hint: it sorts the list, and nothing refuses on it. `--step NN`, `--audience operator|agent` and `--json` narrow or reformat the list. The list is ordered by audience, blocking first, then step and kind.

Decide the `status-conflict` items first (`--step 14` lists them), before any other work of the pass. Each names the sources that disagree about a milestone and says which one closed it. If the milestone is done, resolve the item. If it is not, the migration closed it by mistake, and the way to reopen it is in the 1.1.1 spec, before the migration; see "A milestone closed by mistake" below.

The kinds you will meet most, by what you do:

| Kind | What it asks for |
|---|---|
| `trace-link`, `fixture-target`, `legacy-ref`, `schedules`, `connection-external` | a link field the old data could not fix: say what the node derives from, verifies or schedules |
| `scope-reason`, `rule-reason` | the reason a `later` or `out` item or a rule needs; no reason is invented |
| `legacy-exit-condition` | the old exit condition is now a task criterion; name what it `refines` |
| `legacy-open-item`, `anchor-open-item`, `ambiguity-about`, `duplicate-promoted-item` | an open item without an `about`, or kept in two places: write the answer into the spec and delete the item (`specdev json delete --id <item-id>`). An `about` repairs the item's shape (E520) and nothing more: `spec-check --merge`, which `align validate` runs, reports E631 for every open item outside a frozen plan until the item is deleted. A question that is still open is deleted here and raised again after the migration |
| `third-party-proposal`, `external-dependency`, `host-pin-source` | an external component or a dependency written as a sentence in step 09: decide whether it is a third party and give its pin |
| `seed-route-cleanup`, `decisions-seed` | a seed no node distils, or a decisions seed that folds into others |
| `spec-ref-realises`, `pending-task`, `plan-item-disposition` | a plan item of an open plan, or a task of a closed milestone, that needs a decision |
| `unresolved-link` | a link the resolver refused (E700 to E702): fix it or remove it; `attest` writes its lock entry once it resolves |
| `host-retired-command`, `host-declaration` | a line of your own hooks or workflows (edit it by hand), or a value for `spec/common/host_declarations.json`: the item prints the command that adds it and creates the file when it does not exist, `specdev json insert spec/common/host_declarations.json . '{"setup_command": "npm ci"}' --create-schema vc:host-declarations` |

When a decision is taken, close its item:

```bash
specdev align triage spec --resolve wl-00-scope-reason-scope-online-payment-of-late-fees --note "Reason and seeds written."
```

It prints `<id>: resolved (extras/migration/worklist.json)` and changes only the worklist. A second run on a closed item says it is already resolved. To see a step's file as it was before the migration: `specdev align triage spec --legacy 13` prints `git show <commit>:spec/13_extension_manifest.json` for every file of step 13, from the commit the capture names. It writes nothing.

## Step 6: the pass, step by step

Work in the order of the waterfall: 00, 01, 02, 02a, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 16a, 16b, 16c. Step 03 (the glossary) needs no pass. An edit makes the links that point at the edited node suspect, so finish a step before the next, and inside a step edit a node that other nodes link to before those nodes (it saves a second `attest`). For one step NN:

1. **List what is asked.** `specdev align triage spec --step NN`.
2. **Open the template of the step by hand.** `specdev align prompts` is not made for this migration: on a 1.1.1 host its only output is a prompt for the removed step 13a file, made from the charter template (`Template: template_charter.md`), so you open the file yourself: `prompts/migration/template_<name>.md`. Each template says what the step's nodes look like in 1.2.0, the table of item kinds with the command that answers each, and how to close an item.

   | Step | Template | Step | Template |
   |---|---|---|---|
   | 00 | `template_charter.md` | 09 | `template_impl_plan.md` |
   | 01 | `template_capabilities.md` | 10 | `template_governance.md` |
   | 02 | `template_system_sketch.md` | 11 | `template_redteam.md` |
   | 02a | `template_delivery_baseline.md` | 12 | `template_ci_gates.md` |
   | 03 | `template_glossary.md` | 13 | `template_extension_manifest.md` |
   | 04 | `template_frs.md` | 14 | `template_roadmap.md` |
   | 05 | `template_interfaces.md` | 15 | `template_scaffold.md` |
   | 06 | `template_invariants.md` | 16 | `template_impl_context.md` |
   | 07 | `template_nfrs.md` | 16a / 16b / 16c | `template_impl_planner.md` / `template_impl_coder.md` / `template_impl_reviewer.md` |
   | 08 | `template_fixtures.md` | | |

3. **Ask for proposals once, before the first step.** `specdev align propose spec --kind refines|prose-ids|bindings` adds worklist items that carry a candidate each (add `--dry-run` to print them and add nothing); run each kind once for the whole spec, and a rerun adds nothing. `refines` is for the task criteria of step 14, `prose-ids` for text that names an id, `bindings` for legacy fixtures (see [the legacy binding pass](#the-legacy-binding-pass)). A rerun adds no item twice. Proposals are suggestions with a score; nothing is applied.
4. **Read a node, then edit it by id.** `specdev node show <id>` prints the node, where it lives and its links in and out. `specdev node candidates --for <id> --field <field>` lists the nodes a field accepts (use it when a link is refused with E767 "the field accepts: ..."). Then:
   - `specdev json patch --id <id> .<field> '<json>'`: set a field. Setting a link field writes its lock entry.
   - `specdev json insert --id <id> .<array field> '<json>'`: add an item inside a node (a criterion, a task).
   - `specdev json insert --step NN .<collection> '<json>'`: add a new node to a step. To insert a node use this form or `--id`, **never the file form** (`json insert <file> ...`): the file form writes no lock entry, and the link then reports E761.
   - `specdev json delete --id <id>`: remove a node, for example an open item once its answer is in the spec text.
   - `specdev json delete <file> '<jq path>'`: remove a field that is not a node (`--id` removes a whole node and takes no field path), for example `specdev json delete spec/impl_context/ms_x_plan.json '.plan.spec_alignment.checklist[2].spec_ref'`. A file that has no node to address, such as `spec/common/host_declarations.json`, is written the same way, with the file form.
   No hand edit of a `spec/*.json` file is needed anywhere in the pass: every change is a `specdev json` command.
5. **Close the items.** `specdev align triage spec --resolve <id> --note "<what was decided>"`.
6. **Accept the links.** Every edit of a node makes the links that point at it suspect, and every link the migration wrote is still marked `baseline`. `spec-check` reports one `E882` per baseline link, owned by the step of the node that holds it:

   ```
   E882 trace lock entry (fr-catalog-search, field derives_from, target 'cap-browse-catalog') still carries the migration baseline marker; check the link, then clear it: `specdev attest fr-catalog-search` shows what would be written, `specdev attest fr-catalog-search --yes` writes it
   ```

   Check the link, then `specdev attest <node-id> --yes` for each node; without `--yes` the command prints what it would write. `specdev attest --step NN --yes` accepts every link of the step that is *suspect* because its target changed, and that includes a baseline link whose target was edited in the pass. The baseline links that are not suspect are not touched by it: it prints `attest: nothing to attest` when only those are left, and they are cleared node by node. The links of a closed milestone keep their marker for good (`E765` when you try to attest them) and are not an error.
7. **Gate the step.** `specdev spec-check spec --step NN ...` ends with `RESULT: CLEAR` or `RESULT: BLOCKED`. While the stamp differs from the merge base's, the gate is in migration mode: an error of an earlier step that still has baseline markers is printed as upstream debt, and an error of any other earlier step is new. Clear each step before the next.

Order of attention that worked on the invented host: the charter's links to seeds and needs; capabilities; components and environments; requirements; API errors (each `derives_from` the criterion it follows from); fixtures (`verifies` the criteria; a new fixture where a criterion, API, invariant or NFR was left with none); milestone `schedules`; rule texts and their `derives_from`; edge cases and threats; jobs (`realises`); the task criteria of step 14; the scaffold row paths (a tracked file each); the plan of the open milestone.

Points the pass runs into:

- A node with `scope: out` or `later` needs its `scope_reason` first; a fixture with `mode: manual` needs its `manual_reason` first. A node with `scope: out` does not count as distilling a seed for E748: an in-scope node must list the seed.
- A seed that the manifest routes to a step and no node of that step lists in `derives_from` is `E748`; a seed with no route is `E747`. Route it in `spec/common/seed_manifest.json` (a file edit, not a node) or distil it.
- After a job's steps changed, `specdev canonical-autofix spec --write` rewrites the canonical references of the job (`E210`).
- **An error that has no worklist item.** After the mechanical stage many of the remaining errors are `E520 ... '<field>' is a required property` for a link a node must now have: `derives_from` on the charter's assumptions, risks and scope items, on the delivery baseline's environments, gates and secrets, on API errors and on requirements; `threatens` and `mitigated_by` on edge cases. No item is written for them (the migration cannot know what the node derives from) and the message names the place only as a file and a path with an index, for example `00_charter.json:risks/0: 'derives_from' is a required property`. Read the node at the path, list what the field accepts, and write the link (run on the invented host):

  ```bash
  specdev json read spec/00_charter.json '.risks[0]' --repo-root $TK
  specdev node candidates --for risk-volunteer-availability-at-the-cafe-lantern --field derives_from --repo-root $TK --git-root .
  specdev json patch --id risk-volunteer-availability-at-the-cafe-lantern .derives_from '["seed-volunteer-roster"]' --repo-root $TK --git-root .
  ```

  The first prints the node (`{"risk_id": "risk-volunteer-availability-at-the-cafe-lantern", "text": "...", "scope": "in"}`; the id is the field that ends in `_id`). The second prints `6 candidates for risk.derives_from (showing 6)` and one line per node the field accepts (id, kind, step, file, text). The third prints `patched risk-volunteer-availability-at-the-cafe-lantern (00_charter.json .risks[0])` and `lock entry written: risk-volunteer-availability-at-the-cafe-lantern.derives_from -> seed-volunteer-roster`; a target the field does not accept is refused with `E767` and nothing is written. The same three commands answer `threatens` and `mitigated_by` (the value is a list of ids).
- Text that names an id (`E752`): reword it without the id, or write the relation as a link and take the id out. The nodes of a frozen plan are not read.

### Step 14: `refines` on task criteria

Every task criterion must `refine` the node whose behaviour it checks (a requirement, an acceptance criterion, an API, an API error, an invariant, an NFR, a threat). The old `exit_conditions` became task criteria with `tc-` ids, one worklist item each (`legacy-exit-condition`). `specdev align propose spec --kind refines --dry-run` prints a candidate per criterion with a class and a score:

```
align propose --kind refines: 12 task criteria, 1 auto-eligible, 10 needs-judgement, 1 none
  auto-eligible   ac-fee-calculator-1 -> ac-late-fee-calc-1 (criterion, 0.74)
  needs-judgement ac-fee-endpoint-1 -> api-fee-get (api, 0.44)
  none            tc-the-migration-runs-on-a-fresh-database-without (no candidate)
```

The score is a text similarity, not a judgement: even an `auto-eligible` line is read before it is written. Apply it with `specdev json patch --id <criterion id> .refines '["<id>"]'`, and list the verifier in `.verified_by` where there is one. Criteria of milestones the migration closed need `refines` and `verified_by` too.

### An invariant that constrains a component

The old invariant field `scope.components` became `constrains` of the invariant: the field lists the components (and other nodes) the invariant constrains; the component holds nothing. Step 14 then raises `E744` for every task of an **open** milestone that falls under that component and has no criterion refining the invariant:

```
E744 task task-x falls under inv-y through cmp-z but no criterion of the task refines it; add a task criterion that refines inv-y and lists in verified_by a verifier that verifies it
```

You have two answers. Narrow the invariant to the requirement or API it is really about (change its `constrains` to name that node instead of the component), or add a task criterion to each task that `refines` the invariant and is `verified_by` a fixture or job that verifies it. The tasks of closed milestones are not asked. On the two real hosts nearly every invariant named a component, but only a dozen tasks (or none) were in reach, so this is a short list; no worklist item is written for it.

### A milestone closed by mistake

A milestone is closed by the migration when any one of three 1.1.1 sources says it is done: its `status` in `14_roadmap.json`, the `status` of its row in `16_impl_context.json`, or the `verdict` (`verified`) in the `review` block of its plan file. The migration keeps what they said, so a second run closes it again, and its plan is then a closed plan, not an open one. Reopening it in the migrated spec (setting the anchor row to `in_progress` and deleting its `close`) leaves a plan with 1.1.1 fields that the open-plan scripts never reshaped. To reopen it, undo the migration, correct the 1.1.1 spec, and run it again:

1. Undo the migration. Before the migration commit: `git checkout -- spec && git clean -fd spec`. After it: `git revert --no-edit <the migration commit>`.
2. Correct each source that says done. The item's evidence names them, for example `14 says done; anchor says done; 09 milestone-catalog-basics says done; 16c verdict says verified (closed by 14.status, 16c.verdict)`. Three of the readings can close a milestone: `14` (the roadmap `status`), `anchor` (the row of `16_impl_context.json`) and `16c verdict` (the plan's review); the parenthesis `closed by` lists the ones that did. The `09` reading (the milestone of `09_impl_plan.json`) never closes a milestone, but it is compared with the others: if it still says done once the others are corrected, the run raises a new `status-conflict` item for the milestone, so correct it as well. `specdev json patch` works on the 1.1.1 files with the toolkit's `--repo-root`:

   ```bash
   specdev json patch spec/14_roadmap.json '.milestones[<N>].status' '"in_progress"' --repo-root $TK
   specdev json patch spec/16_impl_context.json '.plan.milestone_index[<N>].status' '"in_progress"' --repo-root $TK
   specdev json patch spec/impl_context/ms_<batch>_plan.json '.review.verdict' '"needs_work"' --repo-root $TK
   specdev json patch spec/09_impl_plan.json '.milestones[<N>].status' '"in_progress"' --repo-root $TK
   ```

   (`<N>` is the place of the milestone or row in its list; `specdev json read <file> '<path>'` shows it. Patch only the sources the item names.)
3. Commit, then run `specdev align apply spec --auto --repo-root $TK --git-root .` again. Followed on a copy of the example host for its `ms-late-fees` (whose only source saying done was the roadmap `status`): after the undo by either form and the one patch, the run printed no `legacy close` line for it, the worklist held no `status-conflict` item, and its anchor row read `pending`. Followed for `ms-catalog-basics`, which the roadmap, the anchor row, the plan's verdict and the step 09 entry all called done: after the four patches above the run closed no milestone but the ones still done and the worklist held no `status-conflict` item for it; with the step 09 patch left out the item `14 says in_progress; anchor says in_progress; 09 milestone-catalog-basics says done; 16c verdict says needs_work (no closing source, so it stays open)` was there. `spec-check` reports on the plan of a reopened milestone only what it reports on any open plan (E520 for the `spec_ref` and missing `realises` of each item, E304 `ROADMAP_TASK_UNCOVERED`), which the open-plan paragraph below tells you to repair.

### An open plan

A plan whose milestone is still open is not frozen (this is also the plan of a milestone you had the migration reopen, see "A milestone closed by mistake"). If the plan was deferred as a whole, the worklist holds one `plan-item-disposition` item about its milestone that quotes the old reason: `specdev milestone defer <milestone-id> --reason "..."` keeps the deferral. The migration removed its old progress fields (`execution.execution_results`, `implementation.status`, an action's `evidence`, `review.fixture_status` and the like); their values are not copied into the capture. Read them in git: `specdev align triage spec --legacy 16a` prints the plan files as they were (`--legacy 16` prints only the anchor file `16_impl_context.json`). **Record each action that was carried out again** with `specdev plan record <item>/<action>` (see `specdev plan record --help`); the close gate asks for the records by name. A plan item keeps its `spec_ref` (with its pins) until you write `realises` on the item and delete the old field with the file form, `specdev json delete <plan file> '.plan.spec_alignment.checklist[<N>].spec_ref'` (`<N>` is the item's place in the `checklist`): the `spec-ref-realises` items say which items. Items marked deferred or dropped in the old plan are `plan-item-disposition` items for you, not open items in the plan. A frozen plan (a milestone whose anchor row says `done`) is changed by the migration in three things and by nothing else, and you never edit it: it gains the `milestone` key; the names the toolkit now computes are removed from it (`milestone_ref`, `nfr_refs` and `fixture_ref` of its plan items, and a stored `content_hash` or `chain_stamp`); and its open items (`execution.emergent_ambiguities` and the like) are removed from it and listed as `legacy-open-item` worklist items (a closed plan keeps no open item; the old item is in the capture and in git).

## Step 7: finish

```bash
specdev spec-check spec --repo-root $TK --spec-root ./spec --git-root . --merge --base-ref <default-branch>
specdev align validate spec --repo-root $TK --git-root . --base-ref <default-branch>
```

`spec-check --merge` is the gate: it runs every check over the whole spec and judges new errors against the base, and it must print no error (warnings do not fail it). `align validate` runs it, and then, only when it passes, deletes `capture.json` and `worklist.json` (when no item is open), clears `migration_status` and refreshes `last_migration`:

```
align validate: spec-check --merge: no error (3 warning(s)).
worklist: every item is resolved.
deleted: spec/extras/migration/capture.json, spec/extras/migration/worklist.json
stamp: migration_status cleared, last_migration refreshed (spec/specdev_version).
Migration finished. Commit the result.
```

- Worklist items that are still open are information, not a failure: `validate` keeps the folder and prints how many are unresolved and how many were marked blocking. `--keep-worklist` keeps it even when nothing is open.
- With a spec stamped below the toolkit's version, `validate` is refused: the migration has not been run.
- With errors it prints them and `spec-check --merge reports N error(s); the migration is not finished and nothing was changed`, exit 1.
- Without `--base-ref` it needs a default branch (`origin/main`, `origin/master`, `main` or `master`) that holds the 1.1.1 spec; otherwise `E900`.

Commit the result. The migration pull request can merge when `spec-check --merge` is clean on it.

## The legacy binding pass

A 1.1.1 fixture proved nothing in the 1.2.0 sense: a fixture needs a binding (the command that runs it, with a guard that matches its output) or an attestation. A fixture with none is no merge-time error, but it is `E811` when a milestone closes (the close gate) and `E348` at a release, so the count must read 0 before your **first release** (not before the migration pull request).

```bash
specdev align propose spec --kind bindings --repo-root $TK --git-root .
specdev align bind-legacy spec --repo-root $TK --git-root .
specdev align bind-legacy spec --summary --repo-root $TK --git-root .
```

`propose --kind bindings` reads the commands the 1.1.1 plans and your CI workflows recorded and adds one item per legacy fixture or group of fixtures. A group is `certain` when one command of a trusted runner (jest, vitest, pytest, playwright) names one test file git tracks, `needs-judgement` otherwise, and `manual` when no plan names a command. `bind-legacy` prints the `specdev verify bind` line of each `certain` group and writes those it is allowed to, through the writer of `verify bind` (it asks, or `--yes` answers for you). It closes the items it settled, and refuses what `verify bind` refuses (`E330` to `E334`, `E767`) unchanged. `--summary` prints:

```
bindings written: 0
fixtures covered by a binding: 0
fixtures made manual: 0 (0 attested)
fixtures still without a binding or attestation: 6 (must be 0 before the first release)
  no binding: fix-checkout-conflict
  ...
```

The command prints one `no binding: <fixture id>` line for each of the six fixtures after the four counts (the excerpt shows the first).

A binding written from a legacy record proves nothing until `specdev verify run --stage <its stage>` has run it on the migrated tree and the guard matched real output; a binding above `dev` is not exercised by the pass. For a `needs-judgement` group, take the lines from the item's proposal (`align triage`), decide, and run `verify bind` yourself; for a manual conversion, apply the `json patch` lines of the proposal and then `specdev verify attest`.

## What is lost, and where it is

Everything the migration removed is in git: `git show <commit>:<spec path>/<file>`, with the commit named in `capture.json` (`align triage --legacy NN` prints it for a step). `capture.json` also keeps, until `align validate` deletes it, the values a later script or the pass reads: milestone and task statuses, exit conditions and assumptions of tasks, the legacy governance fields of step 10, the technology and external-component entries, plan security items and plan items, milestone order and links, the old open items (those of a frozen plan too), the old environment host keys and the renames of ids. Kept only in git: the old per-action progress of an open plan, the stored computed fields, the artifact-level `trace` notes (copies of statements), step 13a and `extras/trace_matrix.json`. The `note` that a 1.1.1 `trace[]` entry of a node gave for a link is not carried either (1.2.0 has no place for the note of a link): read it in the old file with `specdev align triage spec --legacy NN` when you check the link before `attest`. A task criterion or milestone whose id collided with another was renamed once, and the capture's `renames` section lists the old and new id of each; a citation of the old id in prose is a `collided-id-citation` item.

## What stays as it was

- A frozen plan is never edited by you. The migration changes it only as the open-plan paragraph of step 6 says: the `milestone` key, the stored computed names and its open items (listed as `legacy-open-item`).
- `E752` does not read the nodes of a frozen plan.
- The legacy open-item readers (`upstream-backlog`'s legacy shape, `W617`) stay, because a host that is not migrated yet reads through them.
- The old `align` actions `status`, `diff`, `plan`, `prompts` and `rollback` are still there, but on a 1.1.1 host they read only the top level of each schema and say almost nothing about this release; do not use them to plan this migration.

## Sizing

Two real hosts were migrated on copies. A larger host (about 14,000 errors before the mechanical stage) and a smaller one (about 3,800):

| | Larger host | Smaller host |
|---|---|---|
| Errors of `spec-check`, before then after the mechanical stage | 13,795 then 5,715 | 3,752 then 1,193 |
| Files changed / deleted / new by the stage | 25 / 1 / 2 | 25 / 2 / 2 |
| Worklist items | 1,099 (agent 864, operator 235) | 327 (agent 293, operator 34) |
| Of which marked blocking | 146 | 48 |
| Trace-lock entries (all baseline) | 2,143 | 478 |
| Live `E882` / nodes to attest | 1,948 / 769 | 386 / 153 |

The mechanical stage removes about 60 to 70 percent of the errors. What is left, and who clears it:

| Left after the stage | Larger host | Smaller host | Who clears it |
|---|---|---|---|
| `E882` baseline links | 1,948 | 386 | a person, one `attest <node> --yes` per node |
| `E752` an id in live text (closed step-14 nodes not counted) | 1,337 | 112 | reword, or write the link |
| `E520` a field only a person can give (`derives_from`, `refines` on task criteria, `scope_reason`, `pin`) | 884 | 323 | a person; most have no worklist item, see "An error that has no worklist item" in step 6 |
| `E740` a node nothing links to | 854 | 197 | link it, or give it a scope reason |
| `E743` / `E742` no verifier / an unused verifier | 304 / 109 | 79 / 23 | a fixture or job that `verifies`, a `verified_by` |
| `E566`, `E748`, `E701`, `E304`, `E741` | 56, 48, 21, 12, 10 | 21, 7, 2, 0, 6 | a person |

The codes the stage must clear (`E768`, `E704`, `E622`, `E761`) were gone on both hosts. The most common worklist kinds were `fixture-target`, `collided-id-citation` (on the host with renamed ids), `trace-link`, `legacy-exit-condition` and `legacy-open-item` or `scope-reason`. Plan the pass by the audience split: the larger host's 864 agent items are the part an agent can propose and a person checks.

## Run the migration on a copy first

`tests/e2e/host_migration/` runs the whole mechanical stage on a copy and checks it. It writes only in the copy:

```bash
python -m tests.e2e.host_migration.harness --host-copy <copy> --toolkit <1.2.0 toolkit root> --kind mini --stage mechanical
python -m tests.e2e.host_migration.harness --host-copy <copy> --toolkit <1.2.0 toolkit root> --kind mini --stage end --base-ref <default-branch>
```

The copy must be a `git clone` (a copy that lacks untracked files adds `E530` findings before and after), committed, with `spec/` clean, and the toolkit root must say 1.2.0 in `tools/pyproject.toml` (the harness refuses the live checkout). `--kind` is a label for the report. The run prints the checklist of the mechanical stage (a dry run that changes nothing, a real run, a second run with no edit, nothing outside `spec/`, no id lost, fewer errors) and the table of counts the sizing below is made from (`--stage end` checks the finished state: a clean merge check, no live `E882`, and `align validate` exit 0). Two further tests of the folder, one per real host, are skipped unless an environment variable names a copy (see `tests/e2e/host_migration/conftest.py`).

The same pass as a scripted example is `tests/integration/_mini_host_pass.py` (`run_scripted_pass`), driven by `tests/fixtures/migration/mini_host_pass/pass.json`. It takes the invented host from 285 errors after the mechanical stage to zero in 182 commands: 91 items resolved, about 100 links written, 17 `attest --step` runs, 12 sentences reworded, 13 nodes added and 8 removed; then `spec-check --merge` printed no error and `align validate` exited 0. Read `pass.json` as the model of what each step's answers look like.
