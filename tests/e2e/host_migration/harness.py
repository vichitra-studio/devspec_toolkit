"""The host-migration acceptance harness (M10 WI-15): the mechanical stage and the end state of a migration, run on a COPY.

``run_mechanical_stage(copy, toolkit, kind)`` runs what ``specdev align apply --auto`` and the read-only commands after it do
to a 1.1.1 host and checks what the orchestrator saw hold on both real hosts (exit criteria 1 to 4 of plan section 8).
``check_end_state(copy, toolkit)`` checks the state after the judgement pass (criteria 6, 11 and 12).  It does NOT simulate
the judgement pass: that is the person's (steps 4 to 7 of the host guide).

Both return a ``Report``: a checklist (one line per check, ``ok`` / ``FAIL`` / ``note``) and the counts of the run (files,
lines, edits per script, worklist items, errors by code before and after: the table of ruling P15).  ``main(argv)`` prints
them and returns 0, 1 (a check failed) or 2 (a refusal or a usage mistake)::

    python -m tests.e2e.host_migration.harness --host-copy PATH --toolkit ROOT --kind w|p|mini [--expect FILE] [--stage mechanical|end]

The commands are run as a person runs them: ``python -m specdev_tools.cli ...`` in a child process with
``PYTHONPATH=<toolkit>/tools`` and the copy as working directory, so the code under test is the toolkit named by
``--toolkit``, never the one installed in the active venv.  Nothing is committed and nothing is written outside the copy;
the stage writes into the copy exactly what ``align apply --auto`` writes (``spec/**``).  A copy is refused when it is not a
git work tree, when it is the toolkit root, or when its ``spec/`` has uncommitted changes.

``--expect FILE`` is a JSON object ``{metric name: value}``; a value is an integer (equal), ``{"min": n, "max": m}`` or a
string.  A run that does not reproduce a named count fails a check ``expect.<name>``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LIVE_ROOT = Path(__file__).resolve().parents[3]
SPEC_DIR = "spec"
TARGET_VERSION = "1.2.0"
KINDS = ("w", "p", "mini")
STAGES = ("mechanical", "end")

# What the mechanical stage must clear on its own, by itself, with no judgement: code -> (script that clears it, how that is derived).
# Derived from the scripts' docstrings and ``verify`` functions and from plan section 8: E768 is the stored computed fields
# that ``p3_remove`` strips (and the plan-item ones ``p2_*`` leave behind); E704 the duplicated definition ids that
# ``p2_id_collisions`` and ``p4_ambiguities`` rename; E761 the lock entry every link needs, written by ``p6_baseline``; E622 the
# registered arrays whose items lack the id field, which ``p2_id_mint`` mints; W608 the plan with no ``milestone`` key,
# which ``p2_plan_milestone_key`` adds.  The first three codes are named in those scripts' own text (a unit test pins it).
MUST_CLEAR: Mapping[str, str] = {
    "E768": "p3_remove",
    "E704": "p2_id_collisions",
    "E761": "p6_baseline",
    "E622": "p2_id_mint",
    "W608": "p2_plan_milestone_key",
}
OPEN_ITEM_KIND = "ambiguity-item"
"""The kind of a legacy open item; one that was resolved in 1.1.1 is deleted by ``p4_ambiguities`` (its ``deleted_ids``), so its id may vanish."""
FAMILIES = ("errors_before.", "errors_after.", "errors_merge.", "edits.", "worklist_kind.")
"""Metric families where a name that was never counted reads 0 (an error code that did not occur)."""

# Run in a child process under the toolkit's own code: the id and close facts the harness cannot ask a command for.
_CHILD = r"""
import json, sys
mode = sys.argv[1]
if mode == "ids":
    from specdev_tools.graph.build import build_graph
    from specdev_tools.migration import runner
    toolkit, spec = sys.argv[2], sys.argv[3]
    snapshot = runner.take_snapshot(spec)
    graph = build_graph(spec, toolkit, files=set(snapshot.documents), overrides=snapshot.documents)
    found = {}
    for node in graph.nodes:
        found.setdefault(node.id, []).append([node.file, node.kind])
    print(json.dumps(found))
elif mode == "closes":
    from specdev_tools.lifecycle import anchor_store, frozen
    spec = sys.argv[2]
    states = anchor_store.read_statuses(spec)
    done = sorted(m for m, s in states.items() if s.status == "done")
    legacy = sorted(m for m in done if anchor_store.is_legacy_close(states[m].close))
    report = frozen.check_frozen_plans(spec)
    print(json.dumps({"done": done, "legacy": legacy, "drift": [e.message for e in report.errors]}))
"""


class HarnessRefusal(Exception):
    """The copy or the toolkit is not something the harness may run on (nothing was run)."""


@dataclass(frozen=True)
class Check:
    """One line of the checklist: ``ok`` is True (ok), False (FAIL) or None (a note: informational, never fails)."""

    criterion: str
    name: str
    ok: bool | None
    detail: str = ""

    def render(self) -> str:
        mark = {True: " ok ", False: "FAIL", None: "note"}[self.ok]
        text = f"[{mark}] {self.criterion:<4} {self.name}"
        return f"{text}: {self.detail}" if self.detail else text


@dataclass
class Report:
    """The checklist and the counts of one stage."""

    stage: str
    kind: str
    copy: str
    checks: list[Check] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    tables: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok is not False for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.ok is False]

    def add(self, criterion: str, name: str, ok: bool | None, detail: str = "") -> bool | None:
        self.checks.append(Check(criterion, name, ok, detail))
        return ok

    def check(self, criterion: str, name: str, ok: bool, detail: str = "") -> bool:
        self.add(criterion, name, bool(ok), detail)
        return bool(ok)

    def render(self) -> str:
        lines = [f"host migration harness: stage {self.stage}, kind {self.kind}, copy {self.copy}", ""]
        lines += [check.render() for check in self.checks]
        if self.tables:
            lines += ["", *self.tables]
        failed = len(self.failures)
        lines += ["", f"{len(self.checks)} check(s), {failed} failed: " + ("FAILED" if failed else "PASSED")]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Running commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    code: int
    out: str
    err: str

    def json(self) -> dict[str, Any]:
        """The JSON object the command printed on stdout (``{}`` when there is none)."""
        start = self.out.find("{")
        if start < 0:
            return {}
        try:
            value, _end = json.JSONDecoder().raw_decode(self.out[start:])
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}


class Cli:
    """``python -m specdev_tools.cli`` of *toolkit*, run in *copy* with the three roots on every command."""

    def __init__(self, copy: Path, toolkit: Path) -> None:
        self.copy, self.toolkit = copy, toolkit
        self.spec = copy / SPEC_DIR
        self.env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        self.env["PYTHONPATH"] = str(toolkit / "tools")

    def roots(self) -> list[str]:
        return ["--repo-root", str(self.toolkit), "--git-root", str(self.copy)]

    def specdev(self, *argv: str) -> Run:
        return self._run([sys.executable, "-m", "specdev_tools.cli", *argv])

    def align(self, action: str, *flags: str) -> Run:
        return self.specdev("align", action, str(self.spec), *flags, *self.roots())

    def spec_check(self, *flags: str) -> Run:
        return self.specdev("spec-check", str(self.spec), "--spec-root", str(self.spec), *flags, *self.roots(), "--json")

    def child(self, *args: str) -> dict[str, Any]:
        done = self._run([sys.executable, "-c", _CHILD, *args])
        if done.code != 0:
            raise RuntimeError(done.err.strip() or done.out.strip() or f"exit {done.code}")
        return json.loads(done.out)

    def _run(self, argv: list[str]) -> Run:
        done = subprocess.run(argv, cwd=self.copy, env=self.env, capture_output=True, text=True, check=False)
        return Run(done.returncode, done.stdout, done.stderr)


def git(copy: Path, *args: str) -> str:
    """Read-only git in *copy* (the harness never writes into the git history of a copy)."""
    done = subprocess.run(["git", "-C", str(copy), *args], capture_output=True, text=True, check=False)
    return done.stdout


def git_state(copy: Path) -> dict[str, str]:
    """HEAD, refs, stash and status of *copy*."""
    return {
        "HEAD": git(copy, "rev-parse", "HEAD").strip(),
        "refs": git(copy, "for-each-ref"),
        "stash": git(copy, "stash", "list"),
        "status": git(copy, "status", "--porcelain=v1", "-uall"),
    }


def tree_digest(root: Path) -> dict[str, str]:
    """``{path relative to root: sha256}`` of every file under *root* except the git folder."""
    digests: dict[str, str] = {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            path = Path(folder) / name
            digests[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def changed_paths(before: Mapping[str, str], after: Mapping[str, str]) -> tuple[list[str], list[str], list[str]]:
    """``(changed, deleted, new)`` between two tree digests."""
    changed = sorted(p for p in before if p in after and before[p] != after[p])
    return changed, sorted(p for p in before if p not in after), sorted(p for p in after if p not in before)


# ---------------------------------------------------------------------------
# Refusals and the temporary toolkit / host
# ---------------------------------------------------------------------------


def toolkit_version(toolkit: Path) -> str | None:
    pyproject = toolkit / "tools" / "pyproject.toml"
    if not pyproject.is_file():
        return None
    found = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    return found.group(1) if found else None


def refuse(copy: Path, toolkit: Path) -> None:
    """Raise ``HarnessRefusal`` unless *copy* is a git work tree that is not a toolkit root and whose ``spec/`` is clean."""
    copy, toolkit = copy.resolve(), toolkit.resolve()
    if toolkit_version(toolkit) is None:
        raise HarnessRefusal(f"{toolkit} is not a toolkit root: it has no tools/pyproject.toml with a version")
    if copy in (toolkit, LIVE_ROOT) or (copy / "tools" / "specdev_tools" / "cli.py").is_file():
        raise HarnessRefusal(f"{copy} is a toolkit root, not a host copy; the harness runs the migration on a copy of a host")
    if not copy.is_dir() or git(copy, "rev-parse", "--is-inside-work-tree").strip() != "true" or Path(git(copy, "rev-parse", "--show-toplevel").strip()).resolve() != copy:
        raise HarnessRefusal(f"{copy} is not the top of a git work tree; make the copy with git (git clone or git init + commit)")
    if not (copy / SPEC_DIR).is_dir():
        raise HarnessRefusal(f"{copy} has no {SPEC_DIR}/ folder")
    if not git(copy, "rev-parse", "--verify", "-q", "HEAD").strip():
        raise HarnessRefusal(f"{copy} has no commit: commit the 1.1.1 host first, the migration is read against it")
    dirty = git(copy, "status", "--porcelain=v1", "-uall", "--", SPEC_DIR).strip()
    if dirty:
        raise HarnessRefusal(f"{SPEC_DIR}/ of {copy} has uncommitted changes ({len(dirty.splitlines())} path(s)); commit or discard them first")


def build_toolkit_1_2_0(destination: Path, source: Path = LIVE_ROOT) -> Path:
    """A copy of the toolkit's tools, schema, canon and changelog under *destination* that says 1.2.0.

    The live pyproject says 1.1.1 until the version commit (ruling P1); a migration needs a toolkit that says 1.2.0, so the
    copy gets the version and an empty ``changelog/v1.2.0.yaml`` when it has none.
    """
    for name in ("tools", "schema", "canon", "changelog"):
        shutil.copytree(source / name, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    pyproject = destination / "tools" / "pyproject.toml"
    pyproject.write_text(re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{TARGET_VERSION}"', pyproject.read_text(encoding="utf-8"), count=1, flags=re.MULTILINE), encoding="utf-8")
    released = destination / "changelog" / f"v{TARGET_VERSION}.yaml"
    if not released.exists():
        released.write_text(f"version: {TARGET_VERSION}\nbreaking: true\nchanges: []\n", encoding="utf-8")
    return destination


def make_git_copy(source: Path, destination: Path, *, drop: Iterable[str] = ("README.md",)) -> Path:
    """A git work tree at *destination* holding a copy of *source* (the files in *drop* left out), one commit on ``main``."""
    shutil.copytree(source, destination)
    for name in drop:
        target = destination / name
        if target.is_file():
            target.unlink()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "harness@example.invalid"), ("config", "user.name", "harness"), ("add", "-A"), ("commit", "-q", "--no-verify", "-m", "host at 1.1.1")):
        subprocess.run(["git", "-C", str(destination), *args], capture_output=True, text=True, check=True)
    return destination


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


def error_codes(findings: Iterable[Mapping[str, Any]]) -> Counter[str]:
    return Counter(str(f.get("code")) for f in findings)


def count_errors(findings: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for f in findings if f.get("severity", "error") == "error")


def spec_check_counts(cli: Cli, *flags: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``(the JSON envelope, its findings)`` of ``spec-check`` on the copy."""
    done = cli.spec_check(*flags)
    data = done.json()
    return data, list(data.get("errors") or [])


def numstat(copy: Path) -> tuple[int, int]:
    """``(lines added, lines removed)`` of the tracked files under ``spec/`` against HEAD, plus the lines of new files."""
    added = removed = 0
    for line in git(copy, "diff", "--numstat", "HEAD", "--", SPEC_DIR).splitlines():
        a, r, _path = (line.split("\t", 2) + ["", "", ""])[:3]
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    for line in git(copy, "status", "--porcelain=v1", "-uall", "--", SPEC_DIR).splitlines():
        if line.startswith("??"):
            path = copy / line[3:]
            if path.is_file():
                added += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return added, removed


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def worklist_items(spec: Path) -> list[dict[str, Any]]:
    path = spec / "extras" / "migration" / "worklist.json"
    return list(read_json(path).get("items") or []) if path.is_file() else []


def plan_paths(spec: Path) -> list[Path]:
    return sorted((spec / "impl_context").glob("ms_*_plan.json")) if (spec / "impl_context").is_dir() else []


def table(title: str, rows: Iterable[tuple[str, Any]], limit: int | None = None) -> str:
    rows = list(rows)
    shown = rows if limit is None else rows[:limit]
    lines = [title] + [f"  {name:<44} {value}" for name, value in shown]
    if limit is not None and len(rows) > limit:
        lines.append(f"  ... {len(rows) - limit} more")
    return "\n".join(lines)


def by_code_table(title: str, before: Mapping[str, int], after: Mapping[str, int]) -> str:
    codes = sorted(set(before) | set(after), key=lambda c: (-after.get(c, 0), -before.get(c, 0), c))
    return table(title + " (code: before -> after)", [(code, f"{before.get(code, 0)} -> {after.get(code, 0)}") for code in codes])


# ---------------------------------------------------------------------------
# The mechanical stage
# ---------------------------------------------------------------------------


def run_mechanical_stage(copy: Path | str, toolkit: Path | str, kind: str = "mini") -> Report:
    """Run the mechanical stage on *copy* (a git copy of a 1.1.1 host) against *toolkit* (a root that says 1.2.0).

    Writes into the copy what ``align apply --auto`` writes and nothing else; commits nothing.  Raises ``HarnessRefusal``
    before anything is run when the copy is refused.
    """
    copy, toolkit = Path(copy).resolve(), Path(toolkit).resolve()
    refuse(copy, toolkit)
    report = Report("mechanical", kind, str(copy))
    cli, metrics = Cli(copy, toolkit), report.metrics
    spec = copy / SPEC_DIR
    scratch = Path(tempfile.mkdtemp(prefix="host-migration-"))
    try:
        _mechanical(report, cli, spec, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    metrics["kind"] = kind
    return report


def _mechanical(report: Report, cli: Cli, spec: Path, scratch: Path) -> None:
    copy, metrics = cli.copy, report.metrics
    before_tree, before_git = tree_digest(copy), git_state(copy)
    before_data, before_findings = spec_check_counts(cli)
    before_codes = error_codes(before_findings)
    metrics["errors_before"] = count_errors(before_findings)
    for code, number in before_codes.items():
        metrics[f"errors_before.{code}"] = number
    shutil.copytree(spec, scratch / "spec_before")

    # 1: the dry run reports ok and leaves git and the tree as they were
    dry = cli.align("apply", "--auto", "--dry-run", "--json")
    dry_json = dry.json()
    report.check("1", "the dry run reports ok", dry.code == 0 and dry_json.get("status") == "ok", f"exit {dry.code}, status {dry_json.get('status')!r}, {sum((dry_json.get('edits_by_script') or {}).values())} edit(s), {dry_json.get('worklist_items')} worklist item(s)" + ("" if dry.code == 0 else "; " + (dry.err or dry.out).strip()[:300]))
    same_git, same_tree = git_state(copy) == before_git, tree_digest(copy) == before_tree
    report.check("1", "the dry run leaves HEAD, refs, stash, status and every file as they were", same_git and same_tree, "" if same_git and same_tree else f"git state equal: {same_git}; files equal: {same_tree}")

    # 1: the real run
    real = cli.align("apply", "--auto", "--json")
    real_json = real.json()
    edits = real_json.get("edits_by_script") or {}
    report.check("1", "the real run reports ok", real.code == 0 and real_json.get("status") == "ok" and not real_json.get("errors"), f"exit {real.code}, status {real_json.get('status')!r}, {sum(edits.values())} edit(s)" + ("" if real.code == 0 else "; " + (real.err or real.out).strip()[:300]))
    report.check("1", "the dry run and the real run count the same edits", (dry_json.get("edits_by_script") or {}) == edits and dry_json.get("worklist_items") == real_json.get("worklist_items"), f"{sum((dry_json.get('edits_by_script') or {}).values())} vs {sum(edits.values())} edit(s)")
    metrics["edits"] = sum(edits.values())
    for script, number in edits.items():
        metrics[f"edits.{script}"] = number
    after_tree = tree_digest(copy)
    changed, deleted, new = changed_paths(before_tree, after_tree)
    metrics.update(files_changed=len(changed), files_deleted=len(deleted), files_new=len(new))
    outside = [p for p in changed + deleted + new if not p.startswith(SPEC_DIR + "/")]
    report.check("1", f"no path outside {SPEC_DIR}/ changed", not outside, ", ".join(outside[:5]) if outside else f"{len(changed)} changed, {len(deleted)} deleted, {len(new)} new, all under {SPEC_DIR}/")
    after_git = git_state(copy)
    report.check("1", "the real run made no git write (HEAD, refs, stash)", all(after_git[k] == before_git[k] for k in ("HEAD", "refs", "stash")), "")
    added, removed = numstat(copy)
    metrics.update(diff_added=added, diff_removed=removed)

    # 1: idempotent
    second = cli.align("apply", "--auto", "--json")
    second_json = second.json()
    second_edits = sum((second_json.get("edits_by_script") or {}).values())
    stable = tree_digest(copy) == after_tree
    report.check("1", "a second run changes 0 files", second.code == 0 and second_edits == 0 and stable, f"exit {second.code}, {second_edits} edit(s); files equal: {stable}")

    # 1: every plan carries the milestone key; no frozen plan drifts
    plans = plan_paths(spec)
    without = [p.name for p in plans if not isinstance(read_json(p).get("milestone"), str)]
    metrics.update(plans=len(plans), plans_without_milestone=len(without))
    report.check("1", "every plan carries the milestone key", not without, f"{len(plans)} plan(s)" + (f"; without: {', '.join(without)}" if without else ""))
    try:
        closes = cli.child("closes", str(spec))
        metrics["legacy_closes"] = len(closes["legacy"])
        report.check("1", "no frozen plan drifts from the hash its close record stores", not closes["drift"], f"{len(closes['legacy'])} legacy close(s) of {len(closes['done'])} done milestone(s)" + (f"; {closes['drift'][0]}" if closes["drift"] else ""))
    except RuntimeError as error:
        report.check("1", "no frozen plan drifts from the hash its close record stores", False, f"could not ask: {error}")

    # 2: no id is lost and every string-list item has an id
    try:
        ids_before, ids_after = cli.child("ids", str(cli.toolkit), str(scratch / "spec_before")), cli.child("ids", str(cli.toolkit), str(spec))
        renames = list((read_json(spec / "extras" / "migration" / "capture.json").get("renames") or [])) if (spec / "extras" / "migration" / "capture.json").is_file() else []
        renamed = {r["old"] for r in renames}
        metrics["renames"] = len(renames)
        lost = [i for i in ids_before if i not in ids_after and i not in renamed and any((spec / file).exists() for file, _kind in ids_before[i])]
        resolved = [i for i in lost if all(kind == OPEN_ITEM_KIND for _file, kind in ids_before[i])]
        gone = sorted(set(lost) - set(resolved))
        doubled = sorted(i for i, places in ids_after.items() if len(places) > 1)
        report.check("2", "every definition id of before exists after, except the recorded renames, the deleted files and the resolved open items", not gone, f"{len(ids_before)} id(s) before, {len(ids_after)} after, {len(renames)} rename(s), {len(resolved)} resolved open item(s) deleted by design" + (f"; lost: {', '.join(gone[:5])}" if gone else ""))
        report.check("2", "no id is defined twice after", not doubled, f"{len(doubled)} defined twice" + (f": {', '.join(doubled[:5])}" if doubled else ""))
    except RuntimeError as error:
        report.check("2", "every definition id of before exists after", False, f"could not ask: {error}")

    # 3: the lock
    lock_path = spec / "extras" / "trace.lock.json"
    entries = list(read_json(lock_path).get("entries") or []) if lock_path.is_file() else []
    non_baseline = [e for e in entries if e.get("baseline") is not True]
    metrics["lock_entries"] = len(entries)
    report.check("3", "the lock exists and every entry is a baseline entry", lock_path.is_file() and bool(entries) and not non_baseline, f"{len(entries)} entr(ies), {len(non_baseline)} not baseline")

    # 4: the worklist
    items = worklist_items(spec)
    report.check("4", "the worklist exists", (spec / "extras" / "migration" / "worklist.json").is_file(), f"{len(items)} item(s)")
    kinds = Counter(i.get("kind") for i in items)
    metrics.update(worklist_items=len(items), worklist_agent=sum(1 for i in items if i.get("audience") == "agent"), worklist_operator=sum(1 for i in items if i.get("audience") == "operator"), worklist_blocking=sum(1 for i in items if i.get("blocking")))
    for name, number in kinds.items():
        metrics[f"worklist_kind.{name}"] = number
    skipped = kinds.get("legacy-close-skipped", 0)
    report.check("4", "no done milestone was left without a legacy close (legacy-close-skipped)", skipped == 0, f"{skipped} item(s)")

    # 1, 2, 3: spec-check after
    after_data, after_findings = spec_check_counts(cli)
    after_codes = error_codes(after_findings)
    metrics["errors_after"] = count_errors(after_findings)
    for code, number in after_codes.items():
        metrics[f"errors_after.{code}"] = number
    e882 = [f for f in after_findings if f.get("code") == "E882"]
    metrics.update(e882_live=len(e882), e882_nodes=len({f.get("node_id") for f in e882}))
    report.check("1", "spec-check after reports fewer errors than before", metrics["errors_after"] < metrics["errors_before"], f"{metrics['errors_before']} before, {metrics['errors_after']} after")
    left = {code: after_codes[code] for code in MUST_CLEAR if after_codes.get(code)}
    report.check("2", "none of the codes the mechanical stage clears on its own is left (" + ", ".join(MUST_CLEAR) + ")", not left, ", ".join(f"{c} {n}" for c, n in left.items()) if left else f"before: " + ", ".join(f"{c} {before_codes.get(c, 0)}" for c in MUST_CLEAR))
    missing_id = [f for f in after_findings if f.get("code") == "E520" and "'id' is a required property" in str(f.get("message"))]
    report.check("2", "no item lacks an id (E520 'id' is a required property)", not missing_id, f"{len(missing_id)} finding(s)")
    report.add("3", "baseline links left to attest", None, f"{len(e882)} live E882 on {metrics['e882_nodes']} node(s): the judgement pass attests them")

    # read-only commands
    quiet_tree, quiet_git = tree_digest(copy), git_state(copy)
    for label, run in (
        ("align triage", cli.align("triage")),
        ("align propose --kind refines --dry-run", cli.align("propose", "--kind", "refines", "--dry-run")),
        ("align propose --kind prose-ids --dry-run", cli.align("propose", "--kind", "prose-ids", "--dry-run")),
        ("align propose --kind bindings --dry-run", cli.align("propose", "--kind", "bindings", "--dry-run")),
        ("align bind-legacy --summary", cli.align("bind-legacy", "--summary")),
    ):
        report.check("4", f"{label} exits 0", run.code == 0, "" if run.code == 0 else (run.err or run.out).strip()[:300])
    unchanged = tree_digest(copy) == quiet_tree and git_state(copy) == quiet_git
    report.check("4", "triage, the three propose kinds and bind-legacy --summary change nothing", unchanged, "")

    report.tables += [
        table("files and lines", [("files changed / deleted / new", f"{len(changed)} / {len(deleted)} / {len(new)}"), ("diff lines + / -", f"{added} / {removed}"), ("edits", metrics["edits"]), ("renames", metrics.get("renames", 0)), ("legacy closes", metrics.get("legacy_closes", 0)), ("lock entries", len(entries))]),
        table("edits per script", sorted(edits.items(), key=lambda kv: (-kv[1], kv[0])), 10),
        table("worklist", [("items (agent / operator)", f"{metrics['worklist_agent']} / {metrics['worklist_operator']}"), ("marked blocking", metrics["worklist_blocking"])] + [(f"kind {k}", n) for k, n in kinds.most_common(10)]),
        by_code_table("spec-check errors by code", before_codes, after_codes),
    ]


# ---------------------------------------------------------------------------
# The end stage
# ---------------------------------------------------------------------------

PROOF_CODES = ("E347", "E348", "E914")
"""The release gate's proof codes: an obligation not built or without valid evidence (E914), a verifier without a binding or a run (E347, E348)."""


def fixture_ids(spec: Path) -> list[str]:
    ids: list[str] = []
    for path in sorted(spec.glob("08_*.json")):
        ids += [f["fixture_id"] for f in read_json(path).get("fixtures") or [] if isinstance(f, dict) and isinstance(f.get("fixture_id"), str)]
    return ids


def check_end_state(copy: Path | str, toolkit: Path | str, kind: str = "mini", *, base_ref: str | None = None, release_ready: bool = False) -> Report:
    """Check the state after the judgement pass: criteria 6, 11 and 12 (``align validate`` is run, and writes what it writes).

    *base_ref* is the merge base for ``spec-check --merge`` and ``align validate`` (default: what the commands find: the default
    branch).  Criterion 11 is a release-time condition, not a condition of the migration PR: it is a note unless *release_ready*.
    """
    copy, toolkit = Path(copy).resolve(), Path(toolkit).resolve()
    refuse(copy, toolkit)
    report = Report("end", kind, str(copy))
    cli, metrics = Cli(copy, toolkit), report.metrics
    spec = copy / SPEC_DIR
    base = ["--base-ref", base_ref] if base_ref else []

    merge_data, merge_findings = spec_check_counts(cli, "--merge", *base)
    codes = error_codes(merge_findings)
    errors = count_errors(merge_findings)
    metrics["errors_merge"] = errors
    for code, number in codes.items():
        metrics[f"errors_merge.{code}"] = number
    report.check("6", "spec-check --merge is clean", errors == 0, "0 error(s)" if errors == 0 else f"{errors} error(s): " + ", ".join(f"{c} {n}" for c, n in codes.most_common(8)))
    report.check("3", "no live baseline marker is left (E882)", codes.get("E882", 0) == 0, f"{codes.get('E882', 0)} live")
    report.check("5", "no id in live prose is left (E752)", codes.get("E752", 0) == 0, f"{codes.get('E752', 0)} finding(s)")

    # 12: no depends_on or dependencies on a 09 or 14 milestone
    leftover: list[str] = []
    for step_file in sorted(spec.glob("09_*.json")) + sorted(spec.glob("14_*.json")):
        for milestone in read_json(step_file).get("milestones") or []:
            leftover += [f"{step_file.name}:{milestone.get('id')}.{key}" for key in ("depends_on", "dependencies") if isinstance(milestone, dict) and key in milestone]
    report.check("12", "no depends_on or dependencies field is left on a 09 or 14 milestone", not leftover, ", ".join(leftover[:5]) if leftover else "none")

    # 11: the release gate on the checkout, for the legacy fixtures
    status = cli.specdev("status", "--spec-root", str(spec), *cli.roots(), "--json").json()
    section = (status.get("sections") or {}).get("merge_release_gates") or {}
    gate_errors = [text for found in ((section.get("data") or {}).get("errors") or {}).values() for text in found]
    fixtures = fixture_ids(spec)
    unproven = [text for text in gate_errors if text.startswith(PROOF_CODES) and any(re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) for name in fixtures)]
    metrics["fixtures_without_proof"] = len(unproven)
    report.add("11", "the release gate reports no proof error for a legacy fixture", (not unproven) if release_ready else None, f"{len(unproven)} proof error(s) name a legacy fixture" + ("" if release_ready or not unproven else " (a release-time condition: the binding pass, `align bind-legacy`, must make it 0 before the first release)"))

    # validate: the one gate of the migration; it writes
    validate = cli.align("validate", *base, "--json")
    report.check("6", "align validate exits 0", validate.code == 0, f"exit {validate.code}" + ("" if validate.code == 0 else "; " + (validate.err or validate.out).strip().replace("\n", " ")[:300]))
    capture, worklist = spec / "extras" / "migration" / "capture.json", spec / "extras" / "migration" / "worklist.json"
    report.check("6", "align validate removed the worklist and the capture", not capture.exists() and not worklist.exists(), f"capture {'present' if capture.exists() else 'gone'}, worklist {'present' if worklist.exists() else 'gone'}")
    stamp_text = (spec / "specdev_version").read_text(encoding="utf-8") if (spec / "specdev_version").is_file() else ""
    report.check("6", "the stamp says the migration is finished", "migration_status" not in stamp_text and f"toolkit_version: {toolkit_version(toolkit)}" in stamp_text, "")
    return report


# ---------------------------------------------------------------------------
# --expect
# ---------------------------------------------------------------------------


def compare_expect(report: Report, expected: Mapping[str, Any]) -> None:
    """Add a check ``expect.<name>`` per entry of *expected*: a count the run must reproduce, compared by name."""
    for name, wanted in expected.items():
        have = report.metrics.get(name, 0 if name.startswith(FAMILIES) else None)
        if have is None:
            report.check("exp", f"expect.{name}", False, "the run has no metric of that name")
        elif isinstance(wanted, Mapping):
            low, high = wanted.get("min"), wanted.get("max")
            ok = isinstance(have, int) and (low is None or have >= low) and (high is None or have <= high)
            report.check("exp", f"expect.{name}", ok, f"{have} (wanted {low if low is not None else '-inf'} to {high if high is not None else 'inf'})")
        else:
            report.check("exp", f"expect.{name}", have == wanted, f"{have!r}" if have == wanted else f"{have!r}, wanted {wanted!r}")


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="host_migration.harness", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host-copy", required=True, help="a git copy of the 1.1.1 host (committed, spec/ clean)")
    parser.add_argument("--toolkit", required=True, help="a toolkit root that says 1.2.0 (tools/pyproject.toml, schema, canon, changelog)")
    parser.add_argument("--kind", required=True, choices=KINDS, help="w, p or mini (a label for the report)")
    parser.add_argument("--expect", help="a JSON file of counts the run must reproduce, by metric name")
    parser.add_argument("--stage", choices=STAGES, default="mechanical")
    parser.add_argument("--base-ref", help="end stage: the merge base for spec-check --merge and align validate")
    parser.add_argument("--release-ready", action="store_true", help="end stage: fail when a legacy fixture has no valid evidence (criterion 11)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the harness; 0 every check passed, 1 a check failed, 2 a refusal or a usage mistake."""
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exit_:
        return 2 if exit_.code else 0
    try:
        expected = json.loads(Path(args.expect).read_text(encoding="utf-8")) if args.expect else {}
        if not isinstance(expected, dict):
            raise ValueError("the --expect file must hold a JSON object")
    except (OSError, ValueError) as error:
        print(f"host migration harness: cannot read --expect: {error}", file=sys.stderr)
        return 2
    try:
        if args.stage == "mechanical":
            report = run_mechanical_stage(args.host_copy, args.toolkit, args.kind)
        else:
            report = check_end_state(args.host_copy, args.toolkit, args.kind, base_ref=args.base_ref, release_ready=args.release_ready)
    except HarnessRefusal as refusal:
        print(f"host migration harness: refused: {refusal}", file=sys.stderr)
        return 2
    compare_expect(report, expected)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
