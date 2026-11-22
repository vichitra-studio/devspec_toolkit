"""The migration runner behind ``specdev align apply --auto``: scripts in phases on a scratch copy, then an install.

``run_migration`` checks the host (P0, E880), runs the scripts of the versions between the host's and the toolkit's in
their fixed order (P1 to P7) on a scratch copy of the spec folder and of the seed documents, checks the invariants
after every script (E881), writes the version stamp (P8) and, unless it is a dry run, installs the changed files into
the spec folder.  Nothing in the host changes before every script and invariant has passed, so a failed run leaves the
host as it was; a dry run never changes it.  The runner makes only read-only git calls and writes under the spec
folder only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from specdev_tools.core.changelog_parser import (
    compare_versions,
    get_changes_between,
    get_toolkit_version,
    list_versions,
)
from specdev_tools.core.constants import STAMP_FILE
from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.core.plan_files import plan_files
from specdev_tools.core.step_paths import PLAN_DIR_NAME
from specdev_tools.generation.schema_differ import read_stamp, stamp_specdev_version
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import GitViewError, status_lines
from specdev_tools.graph.kinds import KindRegistryError, load_kind_registry
from specdev_tools.lifecycle import plans
from specdev_tools.lifecycle.frozen import check_frozen_plans
from specdev_tools.migration.context import CAPTURE_FILE, STATUS_IN_PROGRESS, GitReadError, MigrationContext, Snapshot, file_key, read_git
from specdev_tools.migration.registry import (
    PHASE_CLOSE,
    PHASE_NAMES,
    Problem,
    RegistryError,
    Script,
    ScriptResult,
    chain_for,
    discover_scripts,
)
from specdev_tools.migration.report import (
    STATUS_FAILED,
    STATUS_NOOP,
    STATUS_OK,
    STATUS_REFUSED,
    MigrationReport,
    ScriptReport,
    mask_stamp_timestamps,
)
from specdev_tools.migration.writer import DocumentSet, diff_trees

MIN_SOURCE_VERSION = "1.0.0"
SEED_MANIFEST = os.path.join("common", "seed_manifest.json")
ANY_FILE = "*"


# ---------------------------------------------------------------------------
# Snapshots of the spec folder
# ---------------------------------------------------------------------------


def _walk_files(root: str) -> dict[str, str]:
    """``{slash-separated path relative to root: sha256 of the bytes}`` of every file under *root*."""
    digests: dict[str, str] = {}
    for folder, _dirs, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            with open(path, "rb") as handle:
                digests[os.path.relpath(path, root).replace(os.sep, "/")] = hashlib.sha256(handle.read()).hexdigest()
    return digests


def take_snapshot(root: str, previous: Snapshot | None = None) -> Snapshot:
    """The ``Snapshot`` of *root*; a file whose digest equals the one in *previous* reuses its parsed content."""
    files = _walk_files(root)
    documents: dict[str, Any] = {}
    for rel, digest in files.items():
        if not rel.endswith(".json"):
            continue
        if previous is not None and previous.files.get(rel) == digest and rel in previous.documents:
            documents[rel] = previous.documents[rel]
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as handle:
                documents[rel] = json.load(handle)
        except (OSError, ValueError):
            continue
    hashes: dict[str, str] = {}
    for path in plan_files(root):
        try:
            hashes[f"{PLAN_DIR_NAME}/{path.name}"] = plans.plan_hash(path)
        except FindingError:
            continue
    return Snapshot(root, files, documents, hashes)


def definition_ids(snapshot: Snapshot, toolkit_root: str) -> Counter[str]:
    """How many times each definition id occurs in the graph of *snapshot* (built from the snapshot's documents alone)."""
    graph = build_graph(snapshot.root, toolkit_root, files=set(snapshot.documents), overrides=snapshot.documents)
    return Counter(node.id for node in graph.nodes)


# ---------------------------------------------------------------------------
# Invariants (E881)
# ---------------------------------------------------------------------------


def check_invariants(
    script: Script, result: ScriptResult, before: Snapshot, after: Snapshot, toolkit_root: str
) -> list[Problem]:
    """The invariants every script keeps, as problems.

    Files changed, added or removed are only those whose ``file_key`` the script lists in ``touches`` (or all, for
    ``"*"``); no definition id the script did not record as renamed or deleted disappears or is defined once more;
    after the legacy close (a script of a phase above 5) no plan file changes its hash.
    """
    problems: list[Problem] = []
    touches = set(script.spec.touches)
    if ANY_FILE not in touches:
        for rel in sorted(set(before.files) | set(after.files)):
            if before.files.get(rel) != after.files.get(rel) and file_key(rel) not in touches:
                problems.append(Problem(f"changed {rel}, which is outside its touches {sorted(touches)}", rel))
    before_ids = definition_ids(before, toolkit_root)
    expected = Counter(before_ids)
    for old, new in result.renames:
        expected[old] -= 1
        expected[new] += 1
    for gone in result.deleted_ids:
        expected[gone] -= 1
    now = definition_ids(after, toolkit_root)
    for node_id in sorted(set(before_ids) | {new for _old, new in result.renames}):
        wanted = max(expected[node_id], 0)
        if now[node_id] < wanted:
            problems.append(Problem(f"definition id {node_id} was lost without a recorded rename or deletion"))
        elif now[node_id] > wanted:
            problems.append(Problem(f"definition id {node_id} is defined {now[node_id]} times, expected {wanted}"))
    if script.spec.phase > PHASE_CLOSE:
        for rel in sorted(set(before.plan_hashes) | set(after.plan_hashes)):
            if before.plan_hashes.get(rel) != after.plan_hashes.get(rel):
                problems.append(Problem(f"changed the plan {rel} after the legacy close; a plan changes then only through a recorded close migration", rel))
    return problems


# ---------------------------------------------------------------------------
# Preflight (P0, E880)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Start:
    host_version: str
    target: str
    resume: bool
    from_version: str


def _refusal(message: str) -> MigrationReport:
    return MigrationReport(STATUS_REFUSED, False, errors=[make_error("E880", message)])


def _history_from(stamp: Mapping[str, Any]) -> str:
    history = stamp.get("migration_history")
    if isinstance(history, list) and history and isinstance(history[-1], dict):
        value = history[-1].get("from")
        if isinstance(value, str) and value.count(".") == 2 and all(p.isdigit() for p in value.split("-", 1)[0].split(".")):
            return value
    return "0.0.0"


def _dirty_refusal(spec_dir: str, git_root: str) -> MigrationReport | None:
    """E880 when ``git status`` lists a changed, staged or untracked path under *spec_dir* (all untracked files, whatever the host's ``status.showUntrackedFiles`` says); ``None`` when it lists none."""
    try:
        dirty = status_lines(git_root, spec_dir)
    except GitViewError as error:
        return _refusal(error.error.message)
    if dirty:
        return _refusal(
            f"{spec_dir} has uncommitted changes; commit them first (the migration is reviewed with `git diff` and undone with "
            "`git checkout -- spec && git clean -fd spec`), or pass --allow-dirty"
        )
    return None


def _preflight(spec_dir: str, git_root: str, toolkit_root: str, dry_run: bool, allow_dirty: bool) -> _Start | MigrationReport:
    try:
        inside = read_git(git_root, "rev-parse", "--is-inside-work-tree").strip()
    except GitReadError as error:
        return _refusal(f"{git_root} is not a git work tree ({error}); the migration needs git to review and undo what it writes: run `git init` and commit the spec first")
    if inside != "true":
        return _refusal(f"{git_root} is not inside a git work tree; run `git init` and commit the spec first")
    stamp = read_stamp(spec_dir)
    host_version = stamp.get("toolkit_version") if stamp else None
    if not isinstance(host_version, str):
        return _refusal(
            f"{spec_dir}/{STAMP_FILE} records no toolkit_version (or the file does not exist); write the version the spec was built with "
            'into it (`toolkit_version: "1.1.1"` for a 1.1.1 spec), commit it, and run again; do not run `specdev update` first, '
            "it would stamp the spec with the new version and the migration would never run"
        )
    target = get_toolkit_version(Path(toolkit_root))
    if target is None:
        return _refusal(f"the toolkit version cannot be read from {toolkit_root}/tools/pyproject.toml")
    try:
        load_kind_registry(toolkit_root)
    except KindRegistryError as error:
        return _refusal(f"the toolkit at {toolkit_root} has no readable kind registry: {error.error.message}")
    listed = list_versions(Path(toolkit_root) / "changelog")
    try:
        too_old = compare_versions(host_version, MIN_SOURCE_VERSION) < 0
        too_new = compare_versions(host_version, target) > 0
    except ValueError:
        return _refusal(f"toolkit_version {host_version!r} in {spec_dir}/{STAMP_FILE} is not a version number")
    if too_old:
        return _refusal(f"spec was built with toolkit {host_version}, older than {MIN_SOURCE_VERSION}, the oldest the migration starts from")
    if too_new:
        return _refusal(f"spec was built with toolkit {host_version}, newer than this toolkit ({target}); update the toolkit first")
    if host_version not in listed:
        return _refusal(f"toolkit {host_version} is not a version listed in {toolkit_root}/changelog ({', '.join(listed)}); the migration cannot tell which scripts apply")
    resume = bool(stamp and stamp.get("migration_status") == STATUS_IN_PROGRESS) or os.path.isfile(os.path.join(spec_dir, CAPTURE_FILE))
    from_version = _history_from(stamp or {}) if host_version == target else host_version
    return _Start(host_version, target, resume, from_version)


# ---------------------------------------------------------------------------
# Scratch copy and install
# ---------------------------------------------------------------------------


def _seed_paths(spec_dir: str) -> list[str]:
    """The seed document paths (relative to the host root) of the seed manifest, when it lists any."""
    try:
        with open(os.path.join(spec_dir, SEED_MANIFEST), encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        return []
    seeds = manifest.get("seeds") if isinstance(manifest, dict) else None
    paths = [seed.get("path") for seed in seeds if isinstance(seed, dict)] if isinstance(seeds, list) else []
    return [p for p in paths if isinstance(p, str) and not os.path.isabs(p) and ".." not in Path(p).parts]


def _make_scratch(spec_dir: str, host_root: str, spec_rel: str, seed_paths: Iterable[str]) -> tuple[str, str]:
    """Copy the spec folder and the seed documents to a temp folder with the host's layout; return (host root, spec folder)."""
    scratch = tempfile.mkdtemp(prefix="specdev-migrate-")
    scratch_spec = os.path.join(scratch, spec_rel)
    shutil.copytree(spec_dir, scratch_spec, symlinks=True)
    for rel in seed_paths:
        source = os.path.join(host_root, rel)
        if os.path.isfile(source):
            os.makedirs(os.path.dirname(os.path.join(scratch, rel)), exist_ok=True)
            shutil.copy2(source, os.path.join(scratch, rel))
    return scratch, scratch_spec


def _outside_spec(scratch: str, spec_rel: str) -> dict[str, str]:
    """Digests of every file of the scratch host that is not inside its spec folder."""
    return {rel: digest for rel, digest in _walk_files(scratch).items() if not (rel == spec_rel or rel.startswith(spec_rel.replace(os.sep, "/") + "/"))}


def _install(source: str, destination: str) -> None:
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    descriptor, temp = tempfile.mkstemp(dir=os.path.dirname(destination), prefix=".specdev-migrate-", suffix=".tmp")
    os.close(descriptor)
    try:
        shutil.copyfile(source, temp)
        shutil.copymode(source, temp)
        os.replace(temp, destination)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def _install_changes(real_spec: str, scratch_spec: str, changed: Iterable[str], removed: Iterable[str]) -> None:
    for rel in changed:
        _install(os.path.join(scratch_spec, rel), os.path.join(real_spec, rel))
    for rel in removed:
        os.remove(os.path.join(real_spec, rel))
        folder = os.path.dirname(os.path.join(real_spec, rel))
        while folder != real_spec and not os.listdir(folder):
            os.rmdir(folder)
            folder = os.path.dirname(folder)


# ---------------------------------------------------------------------------
# Stamp (P8)
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stamp_migrated(spec_dir: str, to_version: str, script_ids: Iterable[str], now: Callable[[], str]) -> bool:
    """Record the migration in ``<spec_dir>/specdev_version``; ``False`` (file untouched) when it already names *to_version*.

    Calls ``schema_differ.stamp_specdev_version``, the one writer of the stamp: it sets ``toolkit_version``,
    ``last_migration`` and ``migration_status: in_progress``, appends one ``migration_history`` entry
    ``{from, to, date, notes}`` and keeps every other key.  A rerun after the stamp finds the version already
    current and writes nothing, so a resumed run never adds a second entry.  ``specdev align validate`` clears the status.

    Raises:
        OSError: the stamp cannot be written.
    """
    data = read_stamp(spec_dir) or {}
    if data.get("toolkit_version") == to_version:
        return False
    error = stamp_specdev_version(
        Path(spec_dir),
        to_version,
        is_migration=True,
        migration_status=STATUS_IN_PROGRESS,
        history_notes=f"mechanical migration (runner); scripts: {', '.join(script_ids)}",
        now=now,
    )
    if error:
        raise OSError(error)
    return True


def _not_run(toolkit_root: str, from_version: str, to_version: str) -> list[str]:
    """The changelog entries between the versions that are ``ai_assisted``: the runner does not do them."""
    try:
        changes = get_changes_between(Path(toolkit_root) / "changelog", from_version, to_version)
    except (FileNotFoundError, ValueError):
        return []
    entries = []
    for change in changes:
        if change.migration is not None and change.migration.action == "ai_assisted":
            text = (change.description or change.type).strip().splitlines()[0]
            entries.append(f"{change.type}: {text}")
    return entries


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _failed(
    script: Script | None, message: str, report: MigrationReport, file: str | None = None, *, written: bool = False
) -> MigrationReport:
    label = f"script {script.id} (phase {script.spec.phase}, {PHASE_NAMES[script.spec.phase]}): " if script else ""
    report.status = STATUS_FAILED
    report.errors.append(make_error("E881", f"{label}{message}" + ("" if written else "; nothing was written"), file=file))
    report.changed_files = []
    report.diff = ""
    return report


def _describe(error: BaseException) -> str:
    if isinstance(error, FindingError):
        return error.error.render()
    return f"raised {type(error).__name__}: {error}"


def run_migration(
    spec_dir: str | os.PathLike[str],
    *,
    toolkit_root: str | os.PathLike[str],
    git_root: str | os.PathLike[str] | None = None,
    dry_run: bool = False,
    allow_dirty: bool = False,
    scripts: Iterable[Script] | None = None,
    now: Callable[[], str] = _utc_now,
) -> MigrationReport:
    """Migrate the spec folder *spec_dir* from the version it records to the version of the toolkit at *toolkit_root*.

    Args:
        spec_dir: the host's spec folder.
        toolkit_root: the toolkit (``tools/pyproject.toml``, ``changelog/``, ``tools/entry_key_registry.json``); the target
            version is its version.
        git_root: the host's git work tree (default: the folder that holds *spec_dir*); seed documents are read from it.
        dry_run: run on the scratch copy only and report the diff; the host is not changed.
        allow_dirty: do not refuse a spec folder with uncommitted changes.
        scripts: the scripts to choose from (default: every script module of the toolkit, ``discover_scripts``).
        now: the clock of the stamp.

    Returns:
        A ``MigrationReport``: status ``ok`` or ``noop``, ``refused`` (E880: the runner did not start) or ``failed``
        (E881: a script or an invariant failed; the host is unchanged).
    """
    spec = os.path.abspath(spec_dir)
    toolkit = os.path.abspath(toolkit_root)
    git = os.path.abspath(git_root) if git_root is not None else os.path.dirname(spec)
    spec_rel = os.path.relpath(spec, git)
    if spec_rel == "." or spec_rel.startswith(".."):
        git, spec_rel = os.path.dirname(spec), os.path.basename(spec)
    host_root = git

    start = _preflight(spec, git, toolkit, dry_run, allow_dirty)
    if isinstance(start, MigrationReport):
        start.dry_run = dry_run
        return start
    report = MigrationReport(STATUS_OK, dry_run, start.host_version, start.target, spec_dir=spec_rel)
    if compare_versions(start.host_version, start.target) == 0 and not start.resume:
        report.status = STATUS_NOOP
        report.notes.append(f"the spec is already at toolkit version {start.target}; nothing to do")
        return report
    if not (start.resume or allow_dirty or dry_run):
        refusal = _dirty_refusal(spec, git)
        if refusal is not None:
            return refusal
    try:
        chain = chain_for(discover_scripts() if scripts is None else scripts, start.from_version, start.target)
    except RegistryError as error:
        return _failed(None, str(error), report)
    report.not_run = _not_run(toolkit, start.from_version, start.target)
    if not chain:
        report.status = STATUS_NOOP
        report.notes.append(f"no migration script is registered for {start.from_version} -> {start.target}; nothing changed")
        return report

    scratch, scratch_spec = _make_scratch(spec, host_root, spec_rel, _seed_paths(spec))
    try:
        return _run_chain(report, chain, start, spec, scratch, scratch_spec, spec_rel, git, toolkit, now)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run_chain(
    report: MigrationReport,
    chain: list[Script],
    start: _Start,
    spec: str,
    scratch: str,
    scratch_spec: str,
    spec_rel: str,
    git: str,
    toolkit: str,
    now: Callable[[], str],
) -> MigrationReport:
    outside = _outside_spec(scratch, spec_rel)
    snapshot = take_snapshot(scratch_spec)
    applied_any = False
    for script in chain:
        context = MigrationContext(scratch_spec, scratch, git, toolkit, report.dry_run, DocumentSet(scratch_spec), start.from_version, start.target)
        try:
            detected = int(script.detect(context))
        except Exception as error:  # a script bug must fail the run, never leave it half done
            return _failed(script, f"detect {_describe(error)}", report)
        if detected == 0:
            report.scripts.append(ScriptReport(script.id, script.spec.phase, 0, 0))
            continue
        try:
            result = script.apply(context)
            context.documents.write()
            after = take_snapshot(scratch_spec, snapshot)
            problems = check_invariants(script, result, snapshot, after, toolkit)
            problems += list(script.verify(snapshot, after))
            rerun = int(script.detect(MigrationContext(scratch_spec, scratch, git, toolkit, report.dry_run, DocumentSet(scratch_spec), start.from_version, start.target)))
        except Exception as error:
            return _failed(script, _describe(error), report)
        if rerun:
            problems.append(Problem(f"a second detect still finds {rerun} edit(s); the script is not idempotent"))
        for rel, digest in _outside_spec(scratch, spec_rel).items():
            if outside.get(rel) != digest:
                problems.append(Problem(f"wrote {rel}, which is outside the spec folder", rel))
        if problems:
            _failed(script, "; ".join(problem.message for problem in problems), report, problems[0].file)
            return report
        report.scripts.append(ScriptReport(script.id, script.spec.phase, detected, result.edits, result.worklist_items, tuple(result.residue)))
        applied_any = True
        snapshot = after
    if applied_any:
        drift = [e for e in check_frozen_plans(scratch_spec).errors if e.code == "E827"]
        if drift:
            return _failed(None, "a closed plan no longer has the hash of its close record: " + "; ".join(e.message for e in drift), report)
    stamp_migrated(scratch_spec, start.target, [s.id for s in chain], now)
    real, copy = _walk_files(spec), _walk_files(scratch_spec)
    changed = sorted(rel for rel in copy if real.get(rel) != copy[rel])
    removed = sorted(rel for rel in real if rel not in copy)
    report.changed_files = sorted(changed + removed)
    if report.dry_run:
        report.diff = mask_stamp_timestamps(diff_trees(spec, scratch_spec))
        return report
    try:
        _install_changes(spec, scratch_spec, changed, removed)
    except OSError as error:
        return _failed(None, f"the changes could not be installed into {spec} ({error}); the spec folder may be partly changed, review `git status`", report, written=True)
    return report
