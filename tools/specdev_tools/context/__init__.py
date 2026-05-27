"""Context package for the DevSpec Toolkit.

Public API for Phase A: structured context preparation and review for spec authoring.
Reduces AI token usage from ~25,000+ to ~4,500 per pipeline step.

Note: ``extract_context`` is a deprecation stub that exits 1 with a migration
message. Use ``specdev json read <file> '<jq>'`` for surgical reads instead.
"""
from .structure import get_step_structure
from .scope_resolver import resolve_scope
from .extractor import extract_context
from .canon_extractor import extract_canon
from .freshness import check_freshness
from .seed_indexer import build_seed_index
from .reviewer import review_artifact

__all__ = [
    "get_step_structure",
    "resolve_scope",
    "extract_context",
    "extract_canon",
    "check_freshness",
    "build_seed_index",
    "review_artifact",
]
