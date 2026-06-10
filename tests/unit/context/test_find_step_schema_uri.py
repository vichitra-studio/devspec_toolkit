"""Tests for find_step_schema_uri fail-loud hardening.

Covers the three invariants introduced by the order-independent / fail-loud
refactor of ``find_step_schema_uri`` in context/_utils.py:

1. Step 16 returns ``vc:16-impl-context`` against a real SchemaRegistry.
2. Step 16 still returns ``vc:16-impl-context`` when registry map lists
   ``vc:16-anchor`` BEFORE ``vc:16-impl-context`` (order-independence proof).
3. A synthetic stub registry with two URIs for the same unmapped step raises
   ``ValueError`` naming the step and the ambiguous URIs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from specdev_tools.core.registry import SchemaRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
"""Absolute path to devspec_toolkit/."""


class _StubRegistry:
    """Minimal duck-typed substitute for SchemaRegistry.

    find_step_schema_uri only reads ``.map.keys()``, so only that attribute
    is required.
    """

    def __init__(self, map_: dict[str, Any]) -> None:
        self.map = map_


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindStepSchemaUri:
    """find_step_schema_uri — fail-loud hardening."""

    # ------------------------------------------------------------------
    # 1. Correctness: real SchemaRegistry, step 16 → vc:16-impl-context
    # ------------------------------------------------------------------

    def test_step_16_returns_impl_context_real_registry(self) -> None:
        """Against a real SchemaRegistry built on repo_root='.', step 16 returns
        vc:16-impl-context (the canonical spec artifact, not the anchor).
        """
        from specdev_tools.core.registry import SchemaRegistry
        from specdev_tools.context._utils import find_step_schema_uri

        registry = SchemaRegistry(str(_TOOLKIT_ROOT))
        result = find_step_schema_uri("16", registry)
        assert result == "vc:16-impl-context", (
            f"Expected 'vc:16-impl-context', got {result!r}. "
            "The disambiguation table may be missing or stale."
        )

    # ------------------------------------------------------------------
    # 2. Order-independence: reversed stub, step 16 → vc:16-impl-context
    # ------------------------------------------------------------------

    def test_step_16_order_independent_anchor_listed_first(self) -> None:
        """Step 16 returns vc:16-impl-context even when vc:16-anchor is listed
        BEFORE vc:16-impl-context in the registry map.

        This is the key order-independence proof: the old code would have
        returned vc:16-anchor here; the new code ignores dict order.
        """
        from specdev_tools.context._utils import find_step_schema_uri

        # Deliberately place anchor first to prove order-independence.
        stub = _StubRegistry({
            "vc:16-anchor": "schema/16_anchor.schema.json",
            "vc:16-impl-context": "schema/16_impl_context.schema.json",
        })
        result = find_step_schema_uri("16", cast(SchemaRegistry, stub))
        assert result == "vc:16-impl-context", (
            f"Expected 'vc:16-impl-context' regardless of dict order, got {result!r}. "
            "find_step_schema_uri is still order-dependent."
        )

    # ------------------------------------------------------------------
    # 3. Fail-loud: unmapped multi-match → ValueError
    # ------------------------------------------------------------------

    def test_unmapped_multi_match_raises_value_error(self) -> None:
        """Two URIs matching an unmapped step raise ValueError naming step +
        ambiguous URIs + fix instruction.
        """
        from specdev_tools.context._utils import find_step_schema_uri

        # Step 99 is not in _MULTI_SCHEMA_STEP_PRIMARY.
        stub = _StubRegistry({
            "vc:99-alpha": "schema/99_alpha.schema.json",
            "vc:99-beta": "schema/99_beta.schema.json",
        })
        with pytest.raises(ValueError) as exc_info:
            find_step_schema_uri("99", cast(SchemaRegistry, stub))

        msg = str(exc_info.value)
        assert "99" in msg, f"ValueError should name the step; got: {msg!r}"
        assert "vc:99-alpha" in msg, f"ValueError should list ambiguous URI; got: {msg!r}"
        assert "vc:99-beta" in msg, f"ValueError should list ambiguous URI; got: {msg!r}"
        assert "_MULTI_SCHEMA_STEP_PRIMARY" in msg, (
            f"ValueError should mention _MULTI_SCHEMA_STEP_PRIMARY; got: {msg!r}"
        )

    # ------------------------------------------------------------------
    # 4. Zero match → None (unchanged behaviour)
    # ------------------------------------------------------------------

    def test_no_match_returns_none(self) -> None:
        """Steps with no matching URI still return None."""
        from specdev_tools.context._utils import find_step_schema_uri

        stub = _StubRegistry({
            "vc:04-fr-list": "schema/04_fr_list.schema.json",
        })
        result = find_step_schema_uri("99", cast(SchemaRegistry, stub))
        assert result is None

    # ------------------------------------------------------------------
    # 5. Exactly one match → return it (unchanged behaviour, no table needed)
    # ------------------------------------------------------------------

    def test_single_match_returned_directly(self) -> None:
        """Steps with exactly one URI match return that URI without consulting
        the disambiguation table.
        """
        from specdev_tools.context._utils import find_step_schema_uri

        stub = _StubRegistry({
            "vc:04-fr-list": "schema/04_fr_list.schema.json",
        })
        result = find_step_schema_uri("04", cast(SchemaRegistry, stub))
        assert result == "vc:04-fr-list"
