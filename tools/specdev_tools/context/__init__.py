"""Context package for the DevSpec Toolkit.

Public API for Phase A: structured context preparation and review for spec authoring.
Reduces AI token usage from ~25,000+ to ~4,500 per pipeline step.
"""
from .structure import get_step_structure
from .scope_resolver import resolve_scope
from .extractor import extract_context
from .canon_extractor import extract_canon
from .freshness import check_freshness
from .reviewer import review_artifact

__all__ = [
    "get_step_structure",
    "resolve_scope",
    "extract_context",
    "extract_canon",
    "check_freshness",
    "review_artifact",
]
