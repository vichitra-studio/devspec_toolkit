"""Synthetic toolkit and spec folders for the graph tests.

``make_toolkit`` copies the mini spec-graph toolkit (``tests/fixtures/graph/mini_toolkit``: a nested array, a map-keyed
collection, a plan file, a record file and the seed manifest) and generates its registry.  ``copy_build_spec`` copies the
spec folder ``tests/fixtures/graph/synthetic/builder`` that matches it.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

from specdev_tools import cli
from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.core.errors import SpecError
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import check_unique_ids
from specdev_tools.graph.model import Graph
from specdev_tools.registry.generate import generate_registry
from specdev_tools.validation.spec_check import run_spec_check_json

ROOT = Path(__file__).parents[3]
EXAMPLE_SPEC = ROOT / "tests" / "fixtures" / "graph_example" / "spec"
MINI_TOOLKIT = ROOT / "tests" / "fixtures" / "graph" / "mini_toolkit"
BUILD_SPEC = ROOT / "tests" / "fixtures" / "graph" / "synthetic" / "builder"
_CORE_SCHEMAS = ("graph", "atoms", "collections")
GIT_IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false")


def make_toolkit(dest: Path) -> Path:
    """Copy the mini toolkit to *dest*, add the real core schemas and step order, write its generated registry."""
    shutil.copytree(MINI_TOOLKIT, dest)
    for name in _CORE_SCHEMAS:
        shutil.copy(ROOT / "schema" / "core" / f"{name}.schema.json", dest / "schema" / "core")
    shutil.copy(ROOT / "tools" / "step_order.json", dest / "tools")
    shutil.copy(ROOT / "schema" / "step_order.schema.json", dest / "schema")
    clear_shared_caches()
    registry, _extraction = generate_registry(str(dest))
    write_json(dest, "tools/entry_key_registry.json", registry)
    return dest


def copy_build_spec(dest: Path) -> Path:
    """Copy the synthetic build spec folder to *dest* and return it."""
    shutil.copytree(BUILD_SPEC, dest)
    return dest


def docs_graph(docs: Mapping[str, Any]) -> Graph:
    """The graph of the real toolkit's registry over *docs* (``{file relative to the spec folder: parsed document}``).

    No file is read: the spec folder named does not exist, so *docs* are the whole spec.
    """
    return build_graph(str(ROOT / "no-such-spec-folder"), str(ROOT), overrides=docs)


def unique_id_errors(docs: Mapping[str, Any]) -> list[SpecError]:
    """E704 findings over *docs* (``{file relative to the spec folder: parsed document}``), no file read."""
    return check_unique_ids(docs_graph(docs))


def write_spec(dest: Path, docs: Mapping[str, Any]) -> Path:
    """Write each document of *docs* under *dest* and return *dest*."""
    for rel, document in docs.items():
        write_json(dest, rel, document)
    return dest


def run_specdev(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``specdev_tools.cli`` with *args* in a subprocess; the exit code is not asserted."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "tools") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run([sys.executable, "-m", "specdev_tools.cli", *args], capture_output=True, text=True, env=env)


def copy_example(dest: Path) -> Path:
    """Copy the worked example spec folder to *dest* and return it."""
    shutil.copytree(EXAMPLE_SPEC, dest)
    return dest


def load_doc(spec_dir: Path, rel: str) -> dict[str, Any]:
    """The parsed JSON document ``spec_dir/rel``."""
    return json.loads((spec_dir / rel).read_text(encoding="utf-8"))


def graph_check(spec_dir: Path) -> dict[str, Any]:
    """The ``graph`` entry of ``spec-check --json`` (status, counts, ``findings``) for *spec_dir*, on the real toolkit."""
    _errors, context = run_spec_check_json(str(ROOT), str(spec_dir))
    return context["checks"]["graph"]


def spec_check_graph_findings(docs: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The findings of the ``graph`` check of ``spec-check`` over *docs*, written to a temporary spec folder."""
    with tempfile.TemporaryDirectory() as tmp:
        return graph_check(write_spec(Path(tmp), docs))["findings"]


def write_json(root: Path, rel: str, document: Any) -> None:
    """Write *document* as JSON to ``root/rel``, creating folders."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run_cli(*argv: str) -> tuple[int, str]:
    """Run ``cli.main()`` in this process with *argv*; the exit code and what it printed (stdout and stderr together)."""
    buf = io.StringIO()
    with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", ["specdev", *argv]), \
            redirect_stdout(buf), redirect_stderr(buf):
        try:
            cli.main()
            code = 0
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else 1
    return code, buf.getvalue()


def git(repo: Path, *args: str) -> str:
    """Run ``git -C repo`` with a fixed identity and no user or system config; the stripped stdout (raises on failure)."""
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    done = subprocess.run(["git", "-C", str(repo), *GIT_IDENTITY, *args], capture_output=True, text=True, env=env, check=True)
    return done.stdout.strip()
