from __future__ import annotations

from ...core.errors import SpecError


def validate_step_01(instance: dict, repo_root: str) -> list[SpecError]:
    """Deep validation for Step 01 (Capabilities).

    Schema validation runs before this function. The capability-to-component
    link-existence check was removed in 1.2.0 (the graph resolver owns link
    checks), so no content check remains and the result is always empty.
    """
    return []
