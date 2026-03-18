"""Shared constants for the DevSpec Toolkit.

Centralises lookup tables that were previously duplicated across
``generation.prompt_generator`` and ``migration.planner``.

Created by FIX-027 (Batch 2).
"""
from __future__ import annotations

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
}
