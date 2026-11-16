"""Read ``tools/step_order.json``, the strict waterfall DAG, from a toolkit root.

Lives in ``core`` so that ``graph`` (which ranks nodes by step) does not import ``context``.  ``context._utils``
re-exports ``load_step_order`` for its older importers.
"""
from __future__ import annotations

import json
import os


def load_step_order(repo_root: str) -> dict:
    """Load ``tools/step_order.json`` from *repo_root*.

    The DAG lives only under ``tools/``; there is no repo-root copy. If the file
    is absent the ``open`` raises ``FileNotFoundError`` naming that canonical
    ``tools/`` path — previously a dead repo-root fallback masked it.
    """
    path = os.path.join(os.path.abspath(repo_root), "tools", "step_order.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
