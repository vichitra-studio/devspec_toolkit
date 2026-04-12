"""Shared constants and utilities for the DevSpec Toolkit.

Centralises lookup tables that were previously duplicated across
``generation.prompt_generator`` and ``migration.planner``.

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
    "13": "template_extension_generator.md",
    "13a": "template_completeness_assessment.md",
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
    ("status", "status_ref", "status"),
    ("state", "state_ref", "status"),
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
    ("name", "tech_stack_ref", "tech_stack"),
    ("id", "dependency_ref", "dependency"),
    ("category", "risk_category_ref", "risk_category"),
    ("category", "completeness_dimension_ref", "completeness_dimension"),
    ("risk_category", "risk_category_ref", "risk_category"),
    ("tag", "tag_ref", "tag"),
)


# ---------------------------------------------------------------------------
# resolve_extras_path — shared logic for locating output files in the
# spec/extras/ directory (host-repo) with fallback to toolkit tools/.
# Used by context/extractor.py, context/scope_resolver.py, and
# validation/validators/step_14.py.
# ---------------------------------------------------------------------------
def resolve_extras_path(spec_dir: str, repo_root: str, filename: str) -> str:
    """Return the path for *filename* preferring ``<spec_dir>/extras/``.

    Resolution order (read-only — never creates directories):
    1. ``<spec_dir>/extras/`` directory exists → return path there
       (file may not exist yet — callers writing to this path will create it).
    2. Submodule deployment (spec_dir outside repo_root) and the specific
       file already exists at ``<spec_dir>/extras/<filename>`` → return it.
    3. Fallback: ``<repo_root>/tools/<filename>``.
    """
    spec_abs = Path(spec_dir).resolve()
    repo_abs = Path(repo_root).resolve()
    extras_dir = spec_abs / "extras"
    if extras_dir.is_dir():
        return str(extras_dir / filename)
    # If spec_dir is outside repo_root (submodule deployment), prefer
    # extras/ — but only return it if the target file already exists there
    # or a caller explicitly creates the directory.  Do NOT mkdir here:
    # this function is called by read-only code paths that should not
    # create directories as a side effect.
    if not spec_abs.is_relative_to(repo_abs):
        target = extras_dir / filename
        if target.exists():
            return str(target)
    # Fallback: toolkit's own tools/ directory.
    return str(repo_abs / "tools" / filename)
