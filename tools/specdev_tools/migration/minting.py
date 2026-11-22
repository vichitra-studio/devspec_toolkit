"""The one place the migration makes an id from a host's text.

``graph.ids.mint_slug`` raises when the text holds no ASCII letter or digit (a risk written in Japanese, a lone ``???``).
A migration must not stop on that: the id then falls back to a number after the kind's prefix (``risk-1``, the first
free one among the taken ids), and the text stays in the node as it was.  A rerun mints nothing, as before: it only
mints for a node that has no id yet.
"""

from __future__ import annotations

from collections.abc import Collection

from specdev_tools.graph.ids import mint_slug

_NO_PREFIX = "id-"


def mint_id(text: str, taken: Collection[str], *, prefix: str | None) -> str:
    """``mint_slug(text, taken, prefix=prefix)``, or ``<prefix>1``, ``<prefix>2``, ... (the first not in *taken*) when the text makes no slug."""
    try:
        return mint_slug(text, taken, prefix=prefix)
    except ValueError:
        number = 1
        while f"{prefix or _NO_PREFIX}{number}" in taken:
            number += 1
        return f"{prefix or _NO_PREFIX}{number}"
