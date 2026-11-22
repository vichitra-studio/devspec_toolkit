"""The migration scripts: what a script is, how the ones of a toolkit are found, and the order they run in.

A script is a module under ``migration/scripts/v<major>_<minor>_<patch>/`` named ``p<phase>_<name>.py`` that exports
``SCRIPT`` (a ``ScriptSpec``) and the functions ``detect(ctx)``, ``apply(ctx)`` and ``verify(before, after)``.  The
folder names the toolkit version whose migration the script belongs to; a host at version H migrated to version T runs
the scripts of the folders with H < version <= T.

Order: scripts of an earlier version first; inside a version by phase; inside a phase by ``requires`` (a script runs
after every script it requires), ties broken by id, so the order is the same on every run.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

# The phases a script may name.  P0 (preflight) and P8 (the version stamp) belong to the runner and have no script.
PHASE_CAPTURE = 1
PHASE_IDS = 2
PHASE_SHAPES = 3
PHASE_CONTENT = 4
PHASE_CLOSE = 5
PHASE_BASELINE = 6
PHASE_HOST_FILES = 7
PHASE_NAMES = {
    PHASE_CAPTURE: "capture",
    PHASE_IDS: "ids",
    PHASE_SHAPES: "shapes and removed fields",
    PHASE_CONTENT: "content",
    PHASE_CLOSE: "legacy close",
    PHASE_BASELINE: "lock baseline",
    PHASE_HOST_FILES: "host-file report",
}

_VERSION_FOLDER = re.compile(r"^v(\d+)_(\d+)_(\d+)$")
_SCRIPT_MODULE = re.compile(r"^p\d+_[a-z0-9_]+$")
_SCRIPTS_PACKAGE = "specdev_tools.migration.scripts"


class RegistryError(Exception):
    """The set of scripts is not usable (a duplicate id, an unknown requirement, a cycle, a malformed module)."""


@dataclass(frozen=True)
class ScriptSpec:
    """What the runner knows of a script before it runs it.

    ``id`` is unique and equals the module name (``p2_id_mint``); ``phase`` is one of the ``PHASE_*`` numbers;
    ``requires`` lists ids of scripts that run first (same version, same or an earlier phase); ``touches`` lists the
    files the script may change, as keys: a step id (``"04"``, ``"13a"``; the plans of ``impl_context/`` are step
    ``"16"``) or the first folder of the path (``"extras"``, ``"canon"``, ``"common"``) or ``"specdev_version"``;
    ``"*"`` means any file.  A file changed outside ``touches`` fails the run (E881).
    """

    id: str
    phase: int
    requires: tuple[str, ...] = ()
    touches: tuple[str, ...] = ()


@dataclass(frozen=True)
class Problem:
    """One broken invariant a ``verify`` found: what is wrong, and the spec file it is about when one is."""

    message: str
    file: str | None = None


@dataclass(frozen=True)
class ScriptResult:
    """What ``apply`` did.

    ``edits`` is the number of edits made (what ``detect`` counted); ``worklist_items`` the number of items written
    to the worklist for a person; ``residue`` free-text lines the report prints.  ``renames`` (pairs ``(old id, new
    id)``) and ``deleted_ids`` record the definition ids the script changed on purpose; every other definition id
    must survive the script (E881).  An id that is new after the script (a minted id) needs no record.
    """

    edits: int = 0
    worklist_items: int = 0
    residue: tuple[str, ...] = ()
    renames: tuple[tuple[str, str], ...] = ()
    deleted_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Script:
    """A registered script: its spec, the toolkit version it migrates to, and its three functions."""

    spec: ScriptSpec
    version: str
    detect: Callable[[Any], int]
    apply: Callable[[Any], ScriptResult]
    verify: Callable[[Any, Any], list[Problem]]

    @property
    def id(self) -> str:
        return self.spec.id


def version_key(version: str) -> tuple[int, int, int]:
    """``"1.2.0"`` as ``(1, 2, 0)``; a version with a pre-release suffix compares as its release."""
    core = version.split("-", 1)[0]
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch


def script_from_module(module: Any, version: str) -> Script:
    """The ``Script`` a module exports; ``RegistryError`` when ``SCRIPT`` or a function is missing or wrongly typed."""
    name = getattr(module, "__name__", repr(module))
    spec = getattr(module, "SCRIPT", None)
    if not isinstance(spec, ScriptSpec):
        raise RegistryError(f"{name}: no SCRIPT = ScriptSpec(...)")
    functions = {}
    for function in ("detect", "apply", "verify"):
        value = getattr(module, function, None)
        if not callable(value):
            raise RegistryError(f"{name}: no function {function}")
        functions[function] = value
    if name.rsplit(".", 1)[-1] != spec.id:
        raise RegistryError(f"{name}: SCRIPT.id is {spec.id!r}, the module name must be the same")
    return Script(spec, version, functions["detect"], functions["apply"], functions["verify"])


def discover_scripts() -> list[Script]:
    """Every script module under ``migration/scripts/v*_*_*/`` (modules named ``p<phase>_<name>``), unordered."""
    package = importlib.import_module(_SCRIPTS_PACKAGE)
    found: list[Script] = []
    for folder in pkgutil.iter_modules(package.__path__):
        match = _VERSION_FOLDER.match(folder.name)
        if not (folder.ispkg and match):
            continue
        version = ".".join(match.groups())
        subpackage = importlib.import_module(f"{_SCRIPTS_PACKAGE}.{folder.name}")
        for module in pkgutil.iter_modules(subpackage.__path__):
            if _SCRIPT_MODULE.match(module.name):
                found.append(script_from_module(importlib.import_module(f"{subpackage.__name__}.{module.name}"), version))
    return found


def _run_key(script: Script) -> tuple[tuple[int, int, int], int, str]:
    return version_key(script.version), script.spec.phase, script.id


def order_scripts(scripts: Iterable[Script]) -> list[Script]:
    """The scripts in the order they run.

    Raises:
        RegistryError: an id is used twice; a phase is not one of ``PHASE_NAMES``; a script requires an id that is not
            in *scripts*; the requirements form a cycle; a script requires one that would run after it (a later
            version or phase).
    """
    items = list(scripts)
    by_id: dict[str, Script] = {}
    for script in items:
        if script.id in by_id:
            raise RegistryError(f"script id {script.id} is registered twice")
        if script.spec.phase not in PHASE_NAMES:
            raise RegistryError(f"script {script.id}: phase {script.spec.phase} is not one of {sorted(PHASE_NAMES)}")
        by_id[script.id] = script
    for script in items:
        for required in script.spec.requires:
            if required not in by_id:
                raise RegistryError(f"script {script.id} requires {required}, which is not registered")
    ordered: list[Script] = []
    pending = {script.id: set(script.spec.requires) for script in items}
    while pending:
        ready = sorted((by_id[i] for i, needs in pending.items() if not needs), key=_run_key)
        if not ready:
            raise RegistryError("the requires of these scripts form a cycle: " + ", ".join(sorted(pending)))
        chosen = ready[0]
        ordered.append(chosen)
        del pending[chosen.id]
        for needs in pending.values():
            needs.discard(chosen.id)
    for script in ordered:
        for required in script.spec.requires:
            if _run_key(by_id[required])[:2] > _run_key(script)[:2]:
                raise RegistryError(
                    f"script {script.id} requires {required}, which belongs to a later phase or version and would run after it"
                )
    return ordered


def chain_for(scripts: Iterable[Script], from_version: str, to_version: str) -> list[Script]:
    """The ordered scripts of the versions above *from_version* up to and including *to_version*.

    A script of the chain may require only a script of the chain (``RegistryError`` otherwise, as for any set).
    """
    low, high = version_key(from_version), version_key(to_version)
    return order_scripts(script for script in scripts if low < version_key(script.version) <= high)
