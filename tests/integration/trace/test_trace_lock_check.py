"""The ``trace-lock`` check of ``spec-check``, end to end on the worked example (WI-M5-03)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.constants import TRACE_LOCK_FILENAME
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.lifecycle import set_lifecycle
from specdev_tools.graph.model import NOT_APPLICABLE
from specdev_tools.trace.lockfile import lock_path
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, load_doc, write_json, write_spec
from unit.trace._lock_support import EXAMPLE_HOST

ANCHOR_FILE = "16_impl_context.json"
CLOSED_HOLDER = "tc-confirm-expired-token"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """A writable copy of the worked example (spec folder and seed docs, with the committed lock)."""
    destination = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, destination)
    return destination


def _checks(host: Path) -> dict[str, Any]:
    _errors, context = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    return context["checks"]


def _close_milestone(spec: Path) -> None:
    document = load_doc(spec, ANCHOR_FILE)
    document["plan"]["milestone_index"][0]["status"] = "done"
    write_json(spec, ANCHOR_FILE, document)


def test_default_spec_check_runs_trace_lock_check(host: Path) -> None:
    checks = _checks(host)
    assert checks["trace-lock"]["status"] in ("PASS", "FAIL")
    assert checks["trace-lock"]["status"] == "PASS"
    assert checks["graph"]["findings"] == []


def test_trace_lock_check_skips_a_spec_with_no_links_and_no_lock(tmp_path: Path) -> None:
    spec = write_spec(tmp_path / "spec", {"03_glossary.json": {"terms": [{"term_id": "term-a", "term": "A", "definition": "a"}]}})
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    assert context["checks"]["trace-lock"]["status"] == "SKIP"
    assert not Path(lock_path(str(spec))).exists()


def test_a_link_with_no_lock_file_is_e761_in_the_graph_check_only(host: Path) -> None:
    Path(lock_path(str(host / "spec"))).unlink()
    checks = _checks(host)
    assert {finding["code"] for finding in checks["graph"]["findings"]} == {"E761"}
    assert len(checks["graph"]["findings"]) == 64
    assert checks["trace-lock"]["status"] == "PASS"


def test_a_malformed_lock_is_e760_and_no_e761_flood(host: Path) -> None:
    Path(lock_path(str(host / "spec"))).write_text("{not json", encoding="utf-8")
    checks = _checks(host)
    assert [finding["code"] for finding in checks["trace-lock"]["findings"]] == ["E760"]
    assert checks["trace-lock"]["findings"][0]["owner"] == "merge-check"
    assert checks["graph"]["findings"] == []


def test_a_conflicted_lock_is_e760(host: Path) -> None:
    path = Path(lock_path(str(host / "spec")))
    path.write_text("<<<<<<< ours\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    assert [finding["code"] for finding in _checks(host)["trace-lock"]["findings"]] == ["E760"]
    assert path.name == TRACE_LOCK_FILENAME


def test_deleted_target_on_historical_holder_is_not_an_error_orphan_or_suspect(host: Path) -> None:
    """Since M7 (WI-M7-09) the resolver does not resolve a closed criterion's `refines` link, so a deleted target is no E700 either: the link is `removed` in the realisation status."""
    spec = host / "spec"
    toolkit = str(ROOT)
    _close_milestone(spec)
    document = load_doc(spec, "04_fr_list.json")
    document["functional_requirements"] = [fr for fr in document["functional_requirements"] if fr["fr_id"] != "fr-password-reset"]
    write_json(spec, "04_fr_list.json", document)
    lock_before = Path(lock_path(str(spec))).read_bytes()

    checks = _checks(host)
    held = [finding for name in ("graph", "trace-lock") for finding in checks[name]["findings"] if finding.get("node_id") == CLOSED_HOLDER]
    assert held == []
    assert not [
        finding for finding in checks["trace-lock"]["findings"]
        if finding["code"] == "E763" and finding.get("node_id") == CLOSED_HOLDER
    ]
    assert not [finding for finding in checks["trace-lock"]["findings"] if CLOSED_HOLDER in finding["message"] and finding["code"] == "E762"]

    set_lifecycle(build_graph(str(spec), toolkit), str(spec), toolkit, CLOSED_HOLDER, NOT_APPLICABLE)
    cleared = _checks(host)
    assert [
        finding for name in ("graph", "trace-lock") for finding in cleared[name]["findings"]
        if finding.get("node_id") == CLOSED_HOLDER
    ] == []
    assert json.loads(Path(lock_path(str(spec))).read_text(encoding="utf-8")) == json.loads(lock_before)
