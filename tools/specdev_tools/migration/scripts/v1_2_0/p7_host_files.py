"""``p7_host_files``: what the migration REPORTS about the host's own hooks, workflows and declarations (it rewrites none).

Two things a person has to do by hand around the pass, found here and put on the worklist, one item each:

* **Retired commands.**  The host's ``.pre-commit-config.yaml`` (outside the toolkit's marked block) and
  ``.github/workflows/*.yml`` that call a command 1.2.0 retired.  The one detector is ``host_install.retired_command_findings``
  (W932); this script calls it and turns each finding into an item with the file, the line and the replacement the
  detector gives.  Nothing is rewritten: the runner writes under ``spec/`` only, and ``update`` leaves a host's own lines alone.
* **Declarations.**  ``spec/common/host_declarations.json`` is the host's own (the release-tag pattern, the setup command,
  the code-tree exclusions, where each third party's version is declared).  For each item the file does not declare, an item
  carries the fragment a person adds, proposed from what the repository shows (its tags, the install steps of its
  workflows, the toolkit's own folder, its lock files).  The file is never created or edited here.

The host files are read from the host's real work tree (``ctx.git_root``): the runner's scratch copy holds the spec folder
only.  A host file is only read, never written.  The script touches ``extras/`` only (the worklist).  A line a person has
already fixed is not found again; an item stays listed (and resolved ones stay resolved) because its id is built from the
file, the line and the command.  A command that stands on the line after a backslash continuation is not found by the
detector (it looks at one line at a time); the report says so.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from specdev_tools.core.host_declarations import HOST_DECLARATIONS_FILE, HostDeclarations, HostDeclarationsError, load_host_declarations
from specdev_tools.core.step_paths import STEP_JSON_RE
from specdev_tools.host_install import PRE_COMMIT_FILE, WORKFLOWS_DIR, read_managed_header, retired_command_findings
from specdev_tools.migration.context import GitReadError, MigrationContext
from specdev_tools.migration.registry import PHASE_HOST_FILES, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.worklist import AUDIENCE_OPERATOR, WORKLIST_FILE, WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p7_host_files", phase=PHASE_HOST_FILES, touches=("extras",))

KIND_RETIRED_COMMAND = "host-retired-command"
KIND_DECLARATION = "host-declaration"
KIND_PIN_SOURCE = "host-pin-source"
KIND_DECLARATIONS_INVALID = "host-declarations-invalid"
STEP_CI_GATES = "12"
STEP_SYSTEM_SKETCH = "02"

CONTINUATION_NOTE = (
    "a retired command on the line after a backslash continuation is not found (the detector reads one line at a time): "
    "read your hooks and workflows for it"
)
TAG_PATTERN_EXAMPLE = "^v[0-9]+[.][0-9]+[.][0-9]+$"
SETUP_EXAMPLE = "npm ci"
LOCK_FILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Pipfile.lock", "requirements.txt", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock")
JSON_LOCK_FILE = "package-lock.json"

_VALIDATE_ALL = "validate-all"
_INSTALL = re.compile(r"\b(?:npm ci|npm install|yarn install|pnpm install|uv sync|uv pip install|pip install|poetry install|bundle install|composer install|go mod download)\b")
_RUN_PREFIX = re.compile(r"^(?:-\s+)?(?:run:\s*)?")
_CANDIDATE_LIMIT = 5


# --- reading the host ---------------------------------------------------------------------------------------------------


def _read_lines(host: Path, rel: str) -> list[str]:
    """The lines of the host file *rel*; empty when it cannot be read."""
    try:
        return (host / rel).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def _spec_rel(ctx: MigrationContext) -> str:
    """The spec folder relative to the host root, as the declarations message names it (``spec``)."""
    return Path(os.path.relpath(ctx.spec_root, ctx.host_root)).as_posix()


def _declarations_path(ctx: MigrationContext) -> str:
    return f"{_spec_rel(ctx)}/{HOST_DECLARATIONS_FILE}"


def _tags(ctx: MigrationContext) -> list[str]:
    """The tags of the host repository (read-only ``git log``); empty when git cannot say."""
    try:
        decorations = ctx.git("log", "--no-walk=unsorted", "--tags", "--decorate=short", "--format=%D")
    except GitReadError:
        return []
    found = {part[len("tag: "):] for line in decorations.splitlines() for part in line.split(", ") if part.startswith("tag: ")}
    return sorted(found)


def _lock_files(ctx: MigrationContext) -> list[str]:
    """The lock and requirement files the repository tracks, relative to its root, in path order."""
    try:
        listed = ctx.git("ls-files", "--", *(f"*{name}" for name in LOCK_FILES)).splitlines()
    except GitReadError:
        return []
    return sorted(path for path in listed if os.path.basename(path) in LOCK_FILES)


def _workflow_files(host: Path) -> list[str]:
    """The host's own workflow files (not the toolkit's, which start with its header), relative to the host root."""
    folder = host / WORKFLOWS_DIR
    if not folder.is_dir():
        return []
    rels = sorted(p.relative_to(host).as_posix() for pattern in ("*.yml", "*.yaml") for p in folder.glob(pattern))
    return [rel for rel in rels if read_managed_header("\n".join(_read_lines(host, rel))) is None]


def _install_lines(host: Path) -> list[tuple[str, int, str]]:
    """``(file, line, command)`` of the host's workflow lines that install dependencies; the toolkit's own install is left out."""
    found: list[tuple[str, int, str]] = []
    for rel in _workflow_files(host):
        for number, line in enumerate(_read_lines(host, rel), start=1):
            command = _RUN_PREFIX.sub("", line.strip()).strip().strip("\"'")
            if _INSTALL.search(command) and "specdev" not in command and "devspec" not in command and not command.startswith("#"):
                found.append((rel, number, command))
    return found


def _third_parties(ctx: MigrationContext) -> list[dict[str, Any]]:
    """The ``third_parties[]`` entries of step 02 as the spec folder holds them now (the earlier scripts have run)."""
    names = sorted(name for name in os.listdir(ctx.spec_root) if (match := STEP_JSON_RE.match(name)) and match.group(1) == STEP_SYSTEM_SKETCH)
    if not names:
        return []
    entries = ctx.documents.load(names[0]).data.get("third_parties")
    return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("third_party_id"), str)] if isinstance(entries, list) else []


# --- items --------------------------------------------------------------------------------------------------------------


def _fragment_text(fragment: dict[str, Any]) -> str:
    return json.dumps(fragment, ensure_ascii=False)


def _declaration_item(ctx: MigrationContext, about: str, evidence: str, fragment: dict[str, Any], *, step: str = STEP_CI_GATES, kind: str = KIND_DECLARATION, key: str = "") -> WorklistItem:
    proposal = f"add this to the top-level object of {_declarations_path(ctx)} (the migration does not write that file): {_fragment_text(fragment)}"
    return make_item(step, kind, about, audience=AUDIENCE_OPERATOR, blocking=False, evidence=evidence, proposal=proposal, key=key)


def _retired_items(ctx: MigrationContext, host: Path) -> list[WorklistItem]:
    """One operator item per finding of the one detector: the file, the line and the replacement it gives."""
    items: list[WorklistItem] = []
    for finding in retired_command_findings(host):
        text = _read_lines(host, finding.file)
        shown = text[finding.line - 1].strip() if finding.line and 0 < finding.line <= len(text) else ""
        replacement = finding.text.replace("was removed in 1.2.0; superseded by", "is superseded in 1.2.0 by") if finding.command == _VALIDATE_ALL else finding.text
        is_hook = finding.file == PRE_COMMIT_FILE
        tail = " A hook that calls a retired command refuses every commit of the pass until its line is edited." if is_hook else ""
        items.append(
            make_item(
                STEP_CI_GATES,
                KIND_RETIRED_COMMAND,
                finding.file,
                audience=AUDIENCE_OPERATOR,
                blocking=is_hook,
                evidence=f"{finding.file}:{finding.line}: {shown}  [{finding.command}]",
                proposal=f"edit this line of the host file by hand (the migration does not rewrite it): {replacement}.{tail}",
                key=f"{finding.line}-{finding.command}",
            )
        )
    return items


def _tag_pattern_item(ctx: MigrationContext) -> WorklistItem:
    tags = _tags(ctx)
    pattern = re.compile(TAG_PATTERN_EXAMPLE)
    release = [tag for tag in tags if pattern.search(tag)]
    if release:
        shown = ", ".join(release[:_CANDIDATE_LIMIT])
        evidence = f"{len(tags)} tag(s); {len(release)} match {TAG_PATTERN_EXAMPLE}: {shown}; {len(tags) - len(release)} do not"
    else:
        evidence = f"{len(tags)} tag(s), none of the form vN.N.N; the pattern is the documented example, write the pattern of your release tags"
    return _declaration_item(ctx, "release_tag_pattern", evidence, {"release_tag_pattern": TAG_PATTERN_EXAMPLE})


def _setup_item(ctx: MigrationContext, host: Path) -> WorklistItem:
    found = _install_lines(host)
    if found:
        shown = "; ".join(f"{file}:{number}: {command}" for file, number, command in found[:_CANDIDATE_LIMIT])
        evidence, command = f"install step(s) of the host's workflows: {shown}", found[0][2]
    else:
        evidence, command = f"no install step in the host's workflows; the value is the documented example ({SETUP_EXAMPLE}), write the command that prepares a clean checkout", SETUP_EXAMPLE
    return _declaration_item(ctx, "setup_command", evidence, {"setup_command": command})


def _exclusions_item(ctx: MigrationContext) -> WorklistItem | None:
    """The toolkit's own folder when it sits inside the repository (a version bump must not make recorded evidence stale)."""
    relative = os.path.relpath(os.path.realpath(ctx.toolkit_root), os.path.realpath(ctx.git_root))
    if relative == "." or relative.startswith(os.pardir) or os.path.isabs(relative):
        return None
    folder = Path(relative).as_posix()
    return _declaration_item(ctx, "code_tree_exclusions", f"the toolkit is the folder {folder} of the repository", {"code_tree_exclusions": [folder]})


def _json_pointer_for(host: Path, lock: str, entry: dict[str, Any]) -> tuple[str, str] | None:
    """``(pointer, version)`` of the third party in the JSON lock file *lock*, when a package of its id or name is listed."""
    try:
        packages = json.loads((host / lock).read_text(encoding="utf-8")).get("packages", {})
    except (OSError, UnicodeDecodeError, ValueError, AttributeError):
        return None
    name = str(entry.get("name", "")).strip().lower().replace(" ", "-")
    for candidate in (str(entry["third_party_id"]).removeprefix("tp-"), name):
        package = packages.get(f"node_modules/{candidate}") if candidate and isinstance(packages, dict) else None
        if isinstance(package, dict) and isinstance(package.get("version"), str):
            escaped = f"node_modules/{candidate}".replace("~", "~0").replace("/", "~1")
            return f"/packages/{escaped}/version", package["version"]
    return None


def _pin_item(ctx: MigrationContext, host: Path, entry: dict[str, Any], locks: list[str]) -> WorklistItem:
    third_party = entry["third_party_id"]
    pin = entry.get("pin")
    seen = f"lock or requirement files tracked by the repository: {', '.join(locks)}" if locks else "no lock or requirement file is tracked by the repository"
    found = next((hit for lock in locks if lock == JSON_LOCK_FILE for hit in [_json_pointer_for(host, lock, entry)] if hit), None)
    if found is None:
        evidence = f"the pin is {pin!r}; {seen}; no source could be derived, so write one by hand (see docs/developers/host_declarations.md)"
        return make_item(STEP_SYSTEM_SKETCH, KIND_PIN_SOURCE, third_party, audience=AUDIENCE_OPERATOR, blocking=False, evidence=evidence,
                         proposal=f"declare where the repository states the version of {third_party} under pin_sources of {_declarations_path(ctx)}; the migration does not write that file")
    pointer, version = found
    evidence = f"the pin is {pin!r}; {JSON_LOCK_FILE} lists the package at {version!r}"
    source = {"type": "json-pointer", "file": JSON_LOCK_FILE, "pointer": pointer}
    return _declaration_item(ctx, third_party, evidence, {"pin_sources": {third_party: [source]}}, step=STEP_SYSTEM_SKETCH, kind=KIND_PIN_SOURCE)


def _declaration_items(ctx: MigrationContext, host: Path) -> list[WorklistItem]:
    """One operator item per declaration the host's file lacks (all of it when there is no file)."""
    try:
        declared = load_host_declarations(ctx.spec_root)
    except HostDeclarationsError as error:
        where = _declarations_path(ctx)
        return [make_item(STEP_CI_GATES, KIND_DECLARATIONS_INVALID, where, audience=AUDIENCE_OPERATOR, blocking=False, evidence=str(error), proposal=f"correct {where} by hand; the migration does not write it")]
    items: list[WorklistItem] = []
    if not declared.release_tag_pattern:
        items.append(_tag_pattern_item(ctx))
    if not (declared.setup_command and declared.setup_command.strip()):
        items.append(_setup_item(ctx, host))
    exclusions = None if declared.code_tree_exclusions else _exclusions_item(ctx)
    items.extend([exclusions] if exclusions else [])
    items.extend(_pin_items(ctx, host, declared))
    return items


def _pin_items(ctx: MigrationContext, host: Path, declared: HostDeclarations) -> list[WorklistItem]:
    locks = _lock_files(ctx)
    return [_pin_item(ctx, host, entry, locks) for entry in _third_parties(ctx) if entry["third_party_id"] not in declared.pin_sources]


def _items(ctx: MigrationContext) -> list[WorklistItem]:
    host = Path(ctx.git_root)
    return _retired_items(ctx, host) + _declaration_items(ctx, host)


# --- the script contract ------------------------------------------------------------------------------------------------


def detect(ctx) -> int:
    """The number of worklist items not listed yet: 0 once every finding and every missing declaration has its item."""
    return len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """Add the missing items; the report prints one line per added item and the note on continuation lines."""
    new = missing_items(ctx, _items(ctx))
    added = add_items(ctx, new)
    lines = [f"{item.about} ({item.kind}): {item.evidence}" for item in new]
    return ScriptResult(edits=added, worklist_items=added, residue=tuple(lines + [CONTINUATION_NOTE]))


def verify(before, after) -> list[Problem]:
    """Only the worklist file changed: a host's declarations and every other spec file are as they were."""
    listed = WORKLIST_FILE.replace(os.sep, "/")
    changed = sorted(rel for rel in set(before.files) | set(after.files) if before.files.get(rel) != after.files.get(rel) and rel != listed)
    return [Problem(f"changed {rel}; this script adds worklist items only", rel) for rel in changed]
