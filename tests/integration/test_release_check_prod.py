"""``specdev release check --stage prod --tag <t>``: the spec is read AT the tag, the evidence from the checkout, and nothing about the tag itself is checked.

The host is ``staged_host`` (``integration/_release_support.py``): a release-ready example in which a threat stays in scope and is
mitigated by a fixture bound at ``staging``.  The staging evidence reaches the repository on a commit after the tag, as the evidence pull
request brings it; it names the code tree, and the spec folder is not part of the tree.  The proof findings are E347 / E348 with the owner
``release-gate`` (ruling N2: there is no E922).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.graph import gitview
from specdev_tools.release.prod_gate import run_prod_gate
from unit.graph._synth import ROOT, git
from unit.lifecycle._milestone_support import cli_run
from unit.proof._support import run
from unit.release._support import advance, commit, release_host, set_scope, tag
from unit.verify._support import commit_all
from integration._release_support import BINDING, SECOND_BINDING, THREAT, run_staging, snapshot, staged_host

DELIVERY = "secret-mailrelay-api-key"
TAG = "v1.0.0"


def _gate(host: Path, name: str = TAG):
    return run_prod_gate(str(host), str(host / "spec"), str(ROOT), name)


def _codes(result) -> list[str]:
    return [error.code for error in result.errors]


def _check(host: Path, *argv: str) -> tuple[int, str, str]:
    return cli_run(host, "release", "check", "--stage", "prod", "--tag", TAG, *argv)


def test_prod_gate_passes_with_staging_evidence_on_descendant_commit(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, TAG)
    run_staging(host)  # the evidence commit comes after the tag
    result = _gate(host)
    assert result.passed and not result.warnings and result.commit == git(host, "rev-parse", f"{TAG}^{{commit}}")
    before = snapshot(host)
    code, out, err = _check(host)
    assert code == 0 and "passes" in out and result.code_tree in out, out + err
    assert snapshot(host) == before, "release check writes nothing"


def test_prod_gate_fails_without_staging_evidence_E922(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, TAG)
    result = _gate(host)
    assert {"E347"} <= set(_codes(result)) and "E922" not in _codes(result)
    proof = next(error for error in result.errors if error.code == "E347")
    assert proof.owner == "release-gate" and proof.node_id == THREAT and "NO_EVIDENCE" in proof.message
    assert {error.message.split("binding ")[1].split(" ")[0] for error in result.errors if error.code == "E347"} == {BINDING, SECOND_BINDING}
    before = snapshot(host)
    code, out, err = _check(host)
    assert code == 1 and "blocked" in out + err and "E347" in out + err and snapshot(host) == before
    run_staging(host)
    assert _gate(host).passed


def test_candidate_tag_staging_evidence_counts_when_tree_matches(tmp_path: Path) -> None:
    """Staging evidence made while the candidate tag stood still counts for the release tag put on a later commit with the same code tree."""
    host = staged_host(tmp_path)
    tag(host, "v1.0.0-stage")
    run_staging(host)
    commit(host, "spec only")
    tag(host, TAG)
    assert _gate(host).passed


def test_candidate_tag_evidence_other_tree_rejected(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, "v1.0.0-stage")
    run_staging(host)
    advance(host, "the code moved on after the candidate\n")
    tag(host, TAG)
    result = _gate(host)
    proof = [error for error in result.errors if error.code == "E347"]
    assert len(proof) == 2 and all("STALE_TREE" in error.message for error in proof)


def test_staging_delivery_obligation_unbuilt_E923(tmp_path: Path) -> None:
    host = staged_host(tmp_path, DELIVERY)
    run_staging(host)
    tag(host, TAG)
    result = _gate(host)
    [error] = [error for error in result.errors if error.code == "E923"]
    assert error.node_id == DELIVERY and error.owner == "release-gate" and "not built at staging" in error.message
    assert "E924" not in _codes(result), "a delivery obligation E923 names is not named again"
    assert {"E347", "E348"}.isdisjoint(_codes(result)), "a delivery obligation is E923's, not the proof findings'"


def test_relieved_node_failing_at_prod_E924(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, TAG)
    result = _gate(host)
    [error] = [error for error in result.errors if error.code == "E924"]
    assert error.node_id == THREAT and "relieved at the release gate" in error.message and error.owner == "release-gate"
    run_staging(host)
    assert _gate(host).passed


def test_staging_scope_out_skips_W934(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    set_scope(host, "staging", "out")
    commit_all(host, "retire staging")
    tag(host, TAG)
    result = _gate(host)
    assert result.passed and [warning.code for warning in result.warnings] == ["W934"]
    assert result.warnings[0].node_id == "staging" and "retired" in result.warnings[0].message
    code, out, err = _check(host)
    assert code == 0 and "W934" in out, out + err


def test_node_set_read_from_tag_not_from_head(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    run_staging(host)
    tag(host, TAG)
    at_tag = _gate(host)
    assert at_tag.passed
    set_scope(host, "fr-password-reset", "in")  # at HEAD an obligation with no evidence is in play; at the tag it is parked
    commit_all(host, "a new obligation after the tag")
    after = _gate(host)
    assert after.passed and (after.errors, after.warnings, after.code_tree) == (at_tag.errors, at_tag.warnings, at_tag.code_tree)


def test_node_set_of_the_tag_is_judged_even_when_head_parked_it(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, TAG)
    set_scope(host, THREAT, "later")
    commit_all(host, "park the threat after the tag")
    assert "E347" in _codes(_gate(host)), "the tag still holds the threat in scope"


def test_prod_gate_never_checks_tag_signature_or_history(tmp_path: Path) -> None:
    """A lightweight, unsigned tag on a commit HEAD does not descend from is judged on its spec and the evidence alone."""
    host = staged_host(tmp_path)
    git(host, "checkout", "-q", "-b", "release-line")
    advance(host, "the line of the release\n")
    tag(host, TAG)
    git(host, "checkout", "-q", "main")
    _evidence_for_the_tree_of(host, TAG)
    sent: list[list[str]] = []
    real = gitview.run_git
    with patch.object(gitview, "run_git", side_effect=lambda root, args, **kw: (sent.append(list(args)), real(root, args, **kw))[1]):
        result = _gate(host)
    assert result.passed, [error.render() for error in result.errors]
    assert not [args for args in sent if args[0] in {"verify-tag", "merge-base", "log", "rev-list", "show", "cat-file", "for-each-ref", "tag"}]


def _evidence_for_the_tree_of(host: Path, name: str) -> None:
    """Make staging evidence valid for the code tree of *name*: check it out, run the binding, commit the evidence on a branch off main, return to main with the record."""
    git(host, "checkout", "-q", name)
    run(host, [BINDING, SECOND_BINDING], stage="staging")
    record = next((host / "spec" / "extras" / "verification").glob("evd-*.json"))
    text = record.read_text(encoding="utf-8")
    git(host, "checkout", "-q", "-f", "main")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(text, encoding="utf-8")
    commit_all(host, "evidence of the release tree")


def test_unknown_tag_is_E921(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    before = snapshot(host)
    code, out, err = cli_run(host, "release", "check", "--stage", "prod", "--tag", "v9.9.9")
    assert code == 1 and "E921" in out + err and "v9.9.9" in out + err and snapshot(host) == before


def test_release_check_json(tmp_path: Path) -> None:
    host = staged_host(tmp_path)
    tag(host, TAG)
    code, out, _ = _check(host, "--json")
    document = json.loads(out)
    assert code == 1 and document["command"] == "release check" and document["stage"] == "prod" and document["tag"] == TAG
    assert document["status"] == "FAIL" and {error["code"] for error in document["errors"]} >= {"E347", "E924"}
    run_staging(host)
    code, out, _ = _check(host, "--json")
    assert code == 0 and json.loads(out)["status"] == "PASS"
