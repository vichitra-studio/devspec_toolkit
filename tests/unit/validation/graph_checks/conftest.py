"""The ``bindings`` fixture of the graph-check tests: binds a seam or a built provider and removes what is still bound when the test ends."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from ._bindings_support import Bindings


@pytest.fixture
def bindings() -> Iterator[Bindings]:
    held = Bindings()
    yield held
    held.release()
