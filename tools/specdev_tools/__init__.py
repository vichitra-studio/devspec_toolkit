"""DevSpec Toolkit — schema-first, AI-assisted spec-driven development."""

import importlib as _importlib
import warnings as _warnings

__all__: list[str] = []

_MOVED = {
    "validate": "specdev_tools.validation.validate",
    "errors": "specdev_tools.core.errors",
    "registry": "specdev_tools.core.registry",
    "trace_types": "specdev_tools.core.trace_types",
    "changelog_parser": "specdev_tools.core.changelog_parser",
    "hallucination_lint": "specdev_tools.validation.hallucination_lint",
    "fixtures_lint": "specdev_tools.validation.fixtures_lint",
    "seed_lint": "specdev_tools.validation.seed_lint",
    "docs_lint": "specdev_tools.validation.docs_lint",
    "matrix": "specdev_tools.validation.matrix",
    "invariants": "specdev_tools.validation.invariants",
    "governance": "specdev_tools.validation.governance",
    "canonical_autofix": "specdev_tools.canonical.autofix",
    "canonical_lint": "specdev_tools.canonical.lint",
    "canonical_integrity": "specdev_tools.canonical.integrity",
    "canonical_registry": "specdev_tools.canonical.registry",
    "spec_quality_lint": "specdev_tools.validation.spec_quality_lint",
    "dependency_order_lint": "specdev_tools.validation.dependency_order_lint",
    "forward_replay_check": "specdev_tools.validation.forward_replay_check",
    "traceability_closure": "specdev_tools.validation.traceability_closure",
    "prompt_generator": "specdev_tools.generation.prompt_generator",
    "prompt_schema_sync": "specdev_tools.generation.prompt_schema_sync",
    "schema_differ": "specdev_tools.generation.schema_differ",
    "validators": "specdev_tools.validation.validators",
}


def __getattr__(name: str):
    if name in _MOVED:
        _warnings.warn(
            f"Importing '{name}' from specdev_tools is deprecated. "
            f"Use '{_MOVED[name]}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _importlib.import_module(_MOVED[name])
    raise AttributeError(f"module 'specdev_tools' has no attribute {name!r}")
