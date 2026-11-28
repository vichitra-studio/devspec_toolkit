"""Support for the tests of the term-use check: the question the check asks of one label and one text."""
from __future__ import annotations

from specdev_tools.validation.graph_checks.term_use import label_pattern, normalise


def label_matches(label: str, text: str) -> bool:
    """Whether *text* uses *label*: both normalised, the label on token boundaries (``Tag`` is not in ``Tagline``)."""
    pattern = label_pattern(label)
    return pattern is not None and pattern.search(normalise(text)) is not None
