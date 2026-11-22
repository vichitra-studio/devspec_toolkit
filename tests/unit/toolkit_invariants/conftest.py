"""Fixtures of the graph-declaration tests: the annotations of the schemas, read once per module."""
import pytest

from specdev_tools.core.registry import get_shared_registry
from specdev_tools.registry.annotations import SchemaReader, SchemaRefs, collect_annotations

from ._declarations_support import _ROOT


@pytest.fixture(scope="module")
def decls():
    return collect_annotations(str(_ROOT))


@pytest.fixture(scope="module")
def reader() -> SchemaReader:
    return SchemaReader(SchemaRefs(get_shared_registry(str(_ROOT))))
