"""The migration maps ship as package data and load through ``importlib.resources`` (WI-M10-05 item 7a)."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

import pytest

from specdev_tools.migration.maps import legacy_ref_fields, shape_map, shape_rows

PACKAGE_DIR = Path(__file__).resolve().parents[3] / "tools" / "specdev_tools"
PYPROJECT = PACKAGE_DIR.parent / "pyproject.toml"


def test_map_loads_through_importlib_resources():
    folder = resources.files("specdev_tools.migration.maps")
    names = {entry.name for entry in folder.iterdir()}
    assert {"v1_2_0.yaml", "legacy_ref_fields.yaml"} <= names
    assert len(shape_map()["rows"]) == 325
    assert shape_map()["retired_files"] and shape_map()["host_canon"]["renamed_kinds"] == {"inv": "invariant"}
    assert legacy_ref_fields()["fields"]


def test_every_package_data_glob_matches_a_file():
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["specdev_tools"]
    assert "migration/maps/*.yaml" in declared
    for pattern in declared:
        assert list(PACKAGE_DIR.glob(pattern)), f"package-data glob {pattern} matches no file"


@pytest.mark.parametrize("script", ["p3_remove", "p3_copies", "p3_convert"])
def test_shape_rows_filters_by_script(script):
    rows = shape_rows(script)
    assert rows and all(row["script"] == script for row in rows)
