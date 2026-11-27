"""Which pipeline step a spec file belongs to, from its path and (for ``impl_context/``) its content.

Lives in ``core`` because both ``validation`` (deep-validator dispatch) and ``graph`` (error ownership) need it and
``graph`` must not import ``validation``.  ``validation.validate`` imports ``get_step_from_path`` and
``refine_impl_context_substep`` from here.
"""
from __future__ import annotations

import os
import re
from typing import Any

STEP_FILE_RE = re.compile(r"^(\d{2}[a-z]?)_")
STEP_JSON_RE = re.compile(r"^(\d{2}[a-z]?)_[^/]*\.json$")
"""A root spec file name (``05_interface_contracts.json``): group 1 is its step."""
PLAN_DIR_NAME = "impl_context"
PLAN_FILE_GLOB = "ms_*_plan.json"
"""The one spelling of "a milestone plan file": the name pattern inside ``PLAN_DIR_NAME``."""


def plan_file_name(batch: str) -> str:
    """The file name of the plan of batch *batch* (``ms_<batch>_plan.json``): ``PLAN_FILE_GLOB`` with the batch for its ``*``."""
    return PLAN_FILE_GLOB.replace("*", batch)


PLAN_FILE_KEY = f"{PLAN_DIR_NAME}/{PLAN_FILE_GLOB}"
"""The same rule as an entry-key registry key (``impl_context/ms_*_plan.json``)."""
STEP_DIR_RE = re.compile(r"^step_(\d{2}[a-z]?)$")
IMPL_CONTEXT_DIR_RE = re.compile(r"^impl_context$")
EXTENSIONS_DIR_NAME = "extensions"
"""The folder of the spec root that holds the files of the host's extensions (``core/host_schemas.py``)."""
EXTENSION_STEP = "13"
"""The step that owns the files of the extensions folder: the step of the manifest that declares them."""
EXTENSION_FILE_SUFFIX = ".json"
"""What step 13 owns in that folder: its JSON files (schemas and data files).  A ``README.md`` there is no step's."""
_NOT_A_SPEC_ROOT = frozenset({PLAN_DIR_NAME})
"""Folders of a spec root that are never one themselves (``impl_context/extensions/x.json`` is not an extension file)."""
_UNKNOWN_STEP = "unknown"


def same_folder(one: str, other: str) -> bool:
    """Whether *one* and *other* are the same folder on disk, however each is typed (through a link, in another case
    where the file system ignores case).  A folder that is not on disk (that of a deleted file) is compared by its
    path, links resolved."""
    try:
        return os.path.samefile(one, other)
    except OSError:
        return os.path.realpath(one) == os.path.realpath(other)


def is_extension_file(path: str, spec_root: str | None = None) -> bool:
    """Whether *path* is a JSON file of the extensions folder of its spec folder.  Step 13 owns such a file.

    *path* names the same file however it is typed: a relative path is read from the current folder.

    With the spec folder known (*spec_root*: ``--spec-root``, else the folder a command was handed), the place
    decides: the file lies directly in ``<spec_root>/extensions``, whatever its name (``extensions/04_notes.json``
    too), and no file anywhere else is one (not ``common/extensions/x.json``, not ``extensions/sub/x.json``).  The
    folder of the file is compared with ``<spec_root>/extensions`` as a folder on disk (``same_folder``), not by its
    name as typed.  A spec folder that is itself called ``extensions`` is a spec folder like any other.

    By the path alone (no *spec_root*: a ``json`` command by path, ``validate <file>`` with no ``--spec-root``) the
    answer is a reading, because a path does not say where its spec folder is, and the name as typed decides: the
    folder above a folder typed ``extensions`` is taken for the spec folder (unless it is ``impl_context``), and a
    file named like a step file (``NN_*.json``) keeps its step.  So ``<spec>/sub/extensions/x.json`` reads as an
    extension file of ``<spec>/sub``, and in a spec folder itself called ``extensions`` a file of no step at its top
    reads as an extension file of the folder above.  Where that is wrong: ``validate <file> --spec-root <spec>`` and
    ``spec-check`` judge the file with the spec folder known.  A ``json`` command by path has no flag for the spec
    folder.
    """
    folder, name = os.path.split(os.path.abspath(path))
    if not name.endswith(EXTENSION_FILE_SUFFIX):
        return False
    if spec_root is not None:
        return same_folder(folder, os.path.join(spec_root, EXTENSIONS_DIR_NAME))
    above, folder_name = os.path.split(folder)
    return folder_name == EXTENSIONS_DIR_NAME and not STEP_FILE_RE.match(name) and os.path.basename(above) not in _NOT_A_SPEC_ROOT


def get_step_from_path(path: str, spec_root: str | None = None) -> str:
    """Extract step number from file path.

    Handles standard ``NN_name.json`` filenames, ``step_NN/`` directories,
    ``impl_context/`` directories and the files of the extensions folder
    (step ``"13"``: see ``is_extension_file``).  With *spec_root* (the spec
    folder, from a caller that knows it) the place of a file of the extensions
    folder decides before its name; without it the name decides first and
    the extensions folder is read from the path alone.

    Routing rules for Step 16 artifacts:
    - ``16_impl_context.json`` NOT inside ``impl_context/`` → step ``"16"``
      (Trinity Anchor; dispatches to validate_step_16_anchor).
    - Any ``.json`` inside an ``impl_context/`` directory → step ``"16a"``
      by default.  ``refine_impl_context_substep`` promotes to ``"16c"`` based on
      artifact content (presence of ``review.verdict``).  The 16c validator chains
      up through the 16a one, so dispatching to the highest-phase validator runs
      every earlier phase's checks as well.  Nothing routes to ``"16b"``: an
      execution record is a record in the plan, not a phase of the file.
    """
    filename = os.path.basename(path)
    if spec_root is not None and is_extension_file(path, spec_root):
        return EXTENSION_STEP

    # Anchor: 16_impl_context.json NOT inside impl_context/ → step "16"
    # Check this before the generic STEP_FILE_RE so the specific filename
    # takes priority over the numeric-prefix pattern.
    dirname_full = os.path.dirname(path)
    if filename == "16_impl_context.json" and os.path.basename(dirname_full) != PLAN_DIR_NAME:
        return "16"

    match = STEP_FILE_RE.match(filename)
    if match:
        return match.group(1)

    dirname = os.path.basename(dirname_full) if dirname_full else ""
    if dirname:
        match = STEP_DIR_RE.match(dirname)
        if match:
            return match.group(1)
        if IMPL_CONTEXT_DIR_RE.match(dirname):
            # Default to "16a" for impl_context/ artifacts.  Content-based
            # refinement (see refine_impl_context_substep) promotes to
            # "16c" once the artifact is loaded.
            return "16a"
    if spec_root is None and is_extension_file(path):
        return EXTENSION_STEP

    return _UNKNOWN_STEP


def step_of_spec_file(path: str, data: Any, spec_root: str | None = None) -> str | None:
    """The step that owns the spec file *path* (``impl_context`` plans by their content *data*), or ``None`` for a file of no step.

    ``graph.ownership.step_for_file`` for a caller that knows the spec folder (*spec_root*, see ``get_step_from_path``).
    """
    step = refine_impl_context_substep(get_step_from_path(path, spec_root), data)
    return None if step == _UNKNOWN_STEP else step


def refine_impl_context_substep(step: str, data: Any) -> str:
    """Promote/demote ``impl_context/`` dispatch by artifact content.

    A plan file and its review share ``spec/impl_context/`` and the
    ``vc:16-impl-context`` schema, so path alone cannot distinguish them.
    Content signals the highest phase present:

    - ``artifact_role == "anchor"``                      → ``"16"`` (misfiled anchor)
    - ``review.verdict`` present (non-empty string)      → ``"16c"`` (reviewer output)
    - otherwise                                          → ``"16a"`` (planner output)

    Execution records (``execution.records``) do not change the route.
    ``validate_step_16c`` chains through ``validate_step_16a``,
    so routing to the highest phase runs every earlier phase's checks as well.
    Non-``"16a"`` inputs are returned unchanged — this function is a no-op for
    charter artifacts, scaffold artifacts, etc.

    Anchor demotion rationale: when an author drops the anchor file inside
    ``spec/impl_context/`` by mistake, ``get_step_from_path`` classifies it as
    ``"16a"`` by directory.  Without this demotion the file would be deep-validated
    by ``validate_step_16a`` and emit confusing 16a-specific errors (missing
    ``plan.status``, missing ``spec_alignment.checklist``) instead of being
    routed to the anchor validator.  The anchor validator's ``_is_anchor`` + W586
    signal then surfaces the real problem — wrong location for this artifact_role.

    Note on invalid verdicts: promotion triggers on *any* non-empty string in
    ``review.verdict`` — including values outside the verdict enum
    (e.g. ``"TOTALLY_INVALID"``).  The schema owns the verdict enum and reports
    such a value as a schema finding; ``validate_step_16c`` passes the file
    through to ``validate_step_16a``, so the route changes no check.
    """
    if step != "16a" or not isinstance(data, dict):
        return step
    # ``.strip()`` for consistency with the verdict check below — schema enforces
    # the const ``"anchor"`` exactly, but defensive normalisation keeps routing
    # symmetric (a stray trailing space in either field shouldn't break dispatch
    # silently while the schema validator separately complains).
    artifact_role = data.get("artifact_role")
    if isinstance(artifact_role, str) and artifact_role.strip() == "anchor":
        return "16"
    review = data.get("review")
    if isinstance(review, dict) and isinstance(review.get("verdict"), str) and review["verdict"].strip():
        return "16c"
    return "16a"
