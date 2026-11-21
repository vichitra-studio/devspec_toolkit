"""Which pipeline step a spec file belongs to, from its path and (for ``impl_context/``) its content.

Lives in ``core`` because both ``validation`` (deep-validator dispatch) and ``graph`` (error ownership) need it and
``graph`` must not import ``validation``.  ``validation.validate`` keeps the old underscore names as aliases.
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
PLAN_FILE_KEY = f"{PLAN_DIR_NAME}/{PLAN_FILE_GLOB}"
"""The same rule as an entry-key registry key (``impl_context/ms_*_plan.json``)."""
STEP_DIR_RE = re.compile(r"^step_(\d{2}[a-z]?)$")
IMPL_CONTEXT_DIR_RE = re.compile(r"^impl_context$")


def get_step_from_path(path: str) -> str:
    """Extract step number from file path.

    Handles standard ``NN_name.json`` filenames, ``step_NN/`` directories,
    and ``impl_context/`` directories.

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
            # "16b"/"16c" once the artifact is loaded.
            return "16a"

    return "unknown"


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
    ``review.verdict`` — including values outside the ``VALID_VERDICTS`` enum
    (e.g. ``"TOTALLY_INVALID"``).  This is intentional: the enum check lives
    inside ``validate_step_16c``, so routing must reach it *first* for the
    E520 signal to fire.  Demoting unknown verdicts back to 16a would silence
    that diagnostic.
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
