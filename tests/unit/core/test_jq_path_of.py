"""One rendering of the place of a schema violation: ``schema_validate.jq_path_of`` (valid jq for every key)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.core.schema_validate import jq_key, jq_path_of

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools"
GRAPH_EXAMPLE_SPEC = REPO_ROOT / "tests" / "fixtures" / "graph_example" / "spec"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (("frs", 1, "scope"), ".frs[1].scope"),
        ((), "."),
        (("step_requirements", "00"), '.step_requirements["00"]'),
        (("a", "x-y", 0), '.a["x-y"][0]'),
        (("00",), '.["00"]'),
        (("a", 'q"b\\c'), '.a["q\\"b\\\\c"]'),
        ((0,), ".[0]"),
        ((0, "a"), ".[0].a"),
        ((0, "00"), '.[0]["00"]'),
    ],
)
def test_jq_path_of(path: tuple, expected: str) -> None:
    assert jq_path_of(path) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("frs", ".frs"), ("_x1", "._x1"), ("00", '["00"]'), ("a-b", '["a-b"]'), ("é", '["\\u00e9"]'), ('q"b', '["q\\"b"]')],
)
def test_jq_key_is_the_one_quoter_of_a_key(name: str, expected: str) -> None:
    assert jq_key(name) == expected


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", *args], capture_output=True, text=True, cwd=str(TOOLS_DIR)
    )


def test_validate_jq_path_of_a_non_identifier_key_is_read_by_json_read(tmp_path: Path) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(str(GRAPH_EXAMPLE_SPEC), str(spec))
    seed = spec / "common" / "seed_manifest.json"
    doc = json.loads(seed.read_text())
    doc["step_requirements"]["00"] = 5
    seed.write_text(json.dumps(doc))

    proc = _run("validate", str(seed), "--json", "--repo-root", str(REPO_ROOT))
    paths = [e["jq_path"] for e in json.loads(proc.stdout)["errors"] if e["code"] == "E520"]
    place = '.step_requirements["00"]'
    assert place in paths, paths
    read = _run("json", "read", str(seed), place, "--repo-root", str(REPO_ROOT))
    assert read.returncode == 0, read.stderr
    assert json.loads(read.stdout) == 5
