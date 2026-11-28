"""Step 16c (Review phase) validator.

Validates the review phase of the Trinity Loop on top of the 16a plan checks: the ``review`` block is an object.
The verdict enum and the shape of the block are the schema's; whether a milestone may close on that verdict is the
close gate's (``specdev milestone close``), not this validator's.
"""
from __future__ import annotations

from typing import Any, Optional

from ...core.errors import SpecError
from .step_16a import validate_step_16a


def validate_step_16c(data: dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None, spec_root: Optional[str] = None) -> list[SpecError]:
    """Deep validation for Step 16c (Review phase).

    A 16c artifact is a 16a plan augmented with a ``review`` section, so it must satisfy every 16a-phase constraint.
    Chains up through ``validate_step_16a`` → ``validate_step_16``.  The ``review`` block is only routed here when it is an
    object with a verdict (``refine_impl_context_substep``), and the schema reports any other shape.
    """
    return validate_step_16a(data, toolkit_root, spec_path, spec_root)
