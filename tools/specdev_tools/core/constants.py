"""Shared constants and utilities for the DevSpec Toolkit.

Centralises lookup tables that were previously duplicated across
``generation.prompt_generator`` and the old migration planner (deleted in 1.2.0).

Created by FIX-027 (Batch 2).
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# STEP_TO_TEMPLATE — maps pipeline step number prefixes to migration
# prompt template filenames in prompts/migration/.
# ---------------------------------------------------------------------------

STEP_TO_TEMPLATE: dict[str, str] = {
    "00": "template_charter.md",
    "01": "template_capabilities.md",
    "02": "template_system_sketch.md",
    "02a": "template_delivery_baseline.md",
    "03": "template_glossary.md",
    "04": "template_frs.md",
    "05": "template_interfaces.md",
    "06": "template_invariants.md",
    "07": "template_nfrs.md",
    "08": "template_fixtures.md",
    "09": "template_impl_plan.md",
    "10": "template_governance.md",
    "11": "template_redteam.md",
    "12": "template_ci_gates.md",
    "13": "template_extension_manifest.md",
    "14": "template_roadmap.md",
    "15": "template_scaffold.md",
    "16": "template_impl_context.md",
    "16a": "template_impl_planner.md",
    "16b": "template_impl_coder.md",
    "16c": "template_impl_reviewer.md",
}

# ---------------------------------------------------------------------------
# INFERENCE_RULES — canonical _ref field → canon kind mapping.
# Used by canonical/autofix.py and context/canon_extractor.py.
# Promoted from autofix.py to allow reuse without circular imports.
# ---------------------------------------------------------------------------
INFERENCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("metric", "metric_ref", "metric"),
    ("term", "term_ref", "term"),
    ("term", "acronym_ref", "acronym"),
    ("acronym", "acronym_ref", "acronym"),
    ("unit", "unit_ref", "unit"),
    ("interface", "interface_ref", "interface"),
    ("event", "event_ref", "event"),
    ("stage", "stage_ref", "stage"),
    ("stage", "environment_ref", "environment"),
    ("environment", "environment_ref", "environment"),
    ("role", "role_ref", "role"),
    ("actor", "actor_ref", "role"),
    ("entity", "entity_ref", "entity"),
    ("resource", "resource_ref", "entity"),
    ("capability", "capability_ref", "capability"),
    ("action", "action_ref", "action"),
    ("command", "command_ref", "command"),
    ("policy", "policy_ref", "policy"),
    ("pattern", "id_pattern_ref", "id_pattern"),
    ("area_of_concern", "governance_label_ref", "governance_label"),
    ("category", "risk_category_ref", "risk_category"),
    ("risk_category", "risk_category_ref", "risk_category"),
    ("tag", "tag_ref", "tag"),
)


# File name of the trace lock, kept in ``<spec_dir>/extras/`` (see ``resolve_extras_path``).
TRACE_LOCK_FILENAME = "trace.lock.json"


# ---------------------------------------------------------------------------
# resolve_extras_path — shared logic for locating output files in the
# spec/extras/ directory (host-repo).
# ---------------------------------------------------------------------------
def resolve_extras_path(spec_dir: str, filename: str) -> str:
    """Return the canonical path ``<spec_dir>/extras/<filename>``.

    Single-path policy (no fallback):
    - Always returns ``<spec_dir>/extras/<filename>``.
    - The ``extras/`` directory is NOT created here.  Callers that write to
      this path must run ``os.makedirs(os.path.dirname(path), exist_ok=True)``
      before opening the file.  Read-only callers handle a missing file as a
      ``FileNotFoundError`` (or equivalent) in their own error-handling logic.
    """
    return str(Path(spec_dir).resolve() / "extras" / filename)


STAMP_FILE = "specdev_version"
"""The name of the file that stamps a spec folder with the toolkit version it was built with."""
STATUS_IN_PROGRESS = "in_progress"
"""The ``migration_status`` the stamp holds between the runner's install and the close of the triage."""

# The default-branch candidates of the step gate's base ref (core/git_base.py) and of the graph's default base ref (graph/gitview.py).
# Refs tried, in order, when a command needs the repository's default branch and none is given.
DEFAULT_BRANCH_CANDIDATES: tuple[str, ...] = ("origin/main", "origin/master", "main", "master")


# ---------------------------------------------------------------------------
# REMOVED_COMMANDS: the commands 1.2.0 removed and what replaces each. The
# argument parser refuses them before argparse (``cli``); the host installer
# scans a host's own workflows and hooks for them (``host_install``).
# ---------------------------------------------------------------------------

REMOVED_COMMANDS: dict[str, str] = {
    "forward-replay-check": "use `specdev stale` for the pending replay and `specdev spec-check` for broken links",
    "completeness-check": "use `specdev coverage` for the link counts and the ids that are not linked",
    "traceability-check": "use `specdev spec-check` for the role-rule findings (E740 to E745) and broken links",
    "matrix": "use `specdev coverage --by fr` for the FR view and `specdev trace --up|--down <id>` for lineage",
}

SEED_MANIFEST_FILE = "common/seed_manifest.json"
"""The seed manifest, relative to the spec folder (always ``/``-separated)."""
