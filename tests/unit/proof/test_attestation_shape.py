"""The shape of an attestation record: it validates against the evidence schema, and the proof reads it as valid on the tree and the hash."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.schema_validate import schema_violations
from specdev_tools.proof.validity import STALE_HASH, attestation_valid
from specdev_tools.verify.records import ATTESTATION_TYPE, attestations_about
from unit.graph._synth import ROOT

from ._support import FIXTURE, attest, context, edit_doc, graph_of, host_with

EVIDENCE_URI = "vc:extras:evidence-record"


def test_attestation_record_validates_and_is_valid_on_the_current_tree_and_stale_hash_after_the_node_changes(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    attest(host, FIXTURE)
    stored = host / "spec" / "extras" / "verification" / "evd-attest-one.json"
    document = json.loads(stored.read_text(encoding="utf-8"))
    assert document["$schema"] == EVIDENCE_URI and document["records"][0]["type"] == ATTESTATION_TYPE
    assert list(schema_violations(str(ROOT), document)) == []
    graph = graph_of(host)
    [attestation] = attestations_about(graph, FIXTURE)
    assert attestation_valid(attestation, FIXTURE, graph, context(host)) == (True, None)
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint answers 404 for a stale token."))
    assert attestation_valid(attestation, FIXTURE, graph_of(host), context(host)) == (False, STALE_HASH)


def test_an_attestation_without_a_git_author_breaks_the_schema(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    attest(host, FIXTURE)
    document = json.loads((host / "spec" / "extras" / "verification" / "evd-attest-one.json").read_text(encoding="utf-8"))
    del document["records"][0]["git_author"]
    assert list(schema_violations(str(ROOT), document))


def test_attestations_about_resolves_an_old_id(tmp_path: Path) -> None:
    host = host_with(tmp_path)
    attest(host, FIXTURE)
    assert [a.evidence_id for a in attestations_about(graph_of(host), FIXTURE)] == ["evd-attest-one"]
    assert attestations_about(graph_of(host), "fix-no-such") == []
    pytest.importorskip("specdev_tools")
