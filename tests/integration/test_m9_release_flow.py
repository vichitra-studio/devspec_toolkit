"""A release from the first evidence to the next release, through the commands, on ONE host (DOC section 13.6 rows 1 to 10; plan section 7 of M9).

The tests of this file are one story told in order: pytest runs them in the order of the file, each starts from what the row before left (the way
``test_m8_close_flow.py`` carries one host through a milestone, but as separate named tests so a failing row names itself; if a row fails, the rows
after it fail for want of its state).  The host is ``flow_host`` (``integration/_release_support.py``): the release-ready copy of the worked example
in which the latency NFR waits for staging proof, the pin of a third party is declared, and a closed milestone owes an at-deploy action for staging
and prod.  Every step is ``specdev ...`` through ``cli.main`` (``unit.lifecycle._milestone_support.cli_run``, the helper the other release
integration tests use) or plain ``git`` in the host, for what a person does by hand.  A tag push is simulated (the host has no remote; nothing is
contacted).  Each deploy job is the deploy preamble's commands run by hand, in its order.

Where the build differs from the plan's table (the tests keep the plan's names):

* Rows 5 and 7 have no command of their own.  Row 5 (the tag push) is the absence of a remote; row 7 (the evidence branch is merged into the default
  branch) opens row 8 and row 9's merge closes it.
* Row 3 stands BEFORE the cut: with no earlier release the production-verification line reads ``state: none``.  ``not verified (released, awaiting
  production proof)`` appears once the tag is behind HEAD, so row 8 asserts that line, and row 9 asserts ``verified in production``.
* Rows 8 and 10 (ruling N2: there is no E922; N3: the production gate reads the spec at the tag and the evidence from the checkout).  A removed
  staging evidence record is E347 with the owner ``release-gate`` at the production gate; the staging at-deploy record is not read there (it is
  owed at the next release: E920 names it).  The next-release failure is E920, cleared by the production records or by ``release rollback``.
* Row 10's cut is repeated on one commit: after the v1.1.0 that passes, the tag is deleted by hand (it was never pushed) and the production
  record is removed, so the same cut meets E920 and then passes after the rollback record.
* ``release prep`` writes its records at stage ``ci`` for the bindings of stage ``dev`` and ``ci`` (the host has the one binding at ``dev``).
* Row 2's equality of the code tree with the evidence's recorded tree has no command that prints a tree before the cut; the test reads it through
  ``unit.proof._support.context`` (a library call) and also asks the command (``release prep`` runs nothing on the merged tree: the evidence is
  valid for it).
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.core import changelog_parser
from specdev_tools.graph import gitview
from unit.graph._synth import git
from unit.lifecycle._milestone_support import cli_run
from unit.proof._support import context
from unit.release._support import LATENCY_BINDING, advance, set_scope
from unit.verify._support import commit_all
from integration._release_support import BINDING, DEPLOY_ACTION, DEPLOY_ITEM, IDENTITY, LOCKED_PIN, flow_host, snapshot

TAG = "v1.0.0"
NEXT_TAG = "v1.1.0"
PREP_EVIDENCE = f"spec/extras/verification/evd-{BINDING.removeprefix('ver-')}-ci.json"
STAGING_EVIDENCE = f"spec/extras/verification/evd-{LATENCY_BINDING.removeprefix('ver-')}-staging.json"
INSTALL_STAGING = "spec/extras/verification/evd-argon2-staging-install.json"
INSTALL_PROD = "spec/extras/verification/evd-argon2-prod-install.json"
ROLLBACK = "spec/extras/releases/rollback-v1.0.0.json"
NFR = "nfr-latency-reset-email"
ACTION = f"{DEPLOY_ITEM}/{DEPLOY_ACTION}"


@pytest.fixture(scope="module", autouse=True)
def environment() -> Iterator[None]:
    """Git has an identity (the tag and the merges need one) and the active toolkit reads as 1.2.0 (the host is stamped 1.2.0), for the whole module."""
    with pytest.MonkeyPatch.context() as patcher:
        for name, value in IDENTITY.items():
            patcher.setenv(name, value)
        patcher.setattr(changelog_parser, "get_toolkit_version", lambda *_args, **_kwargs: "1.2.0")
        yield


@pytest.fixture(scope="module")
def host(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The one host of the flow; the tests change it in the order of the rows."""
    return flow_host(tmp_path_factory.mktemp("m9-release-flow"))


def run(host: Path, *argv: str, want: int = 0) -> str:
    """``specdev <argv>`` on *host* (the three root flags added); asserts the exit code and returns stdout and stderr."""
    code, out, err = cli_run(host, *argv)
    assert code == want, f"specdev {' '.join(argv)} exited {code}, wanted {want}:\n{out}{err}"
    return out + err


def evidence(host: Path, rel: str) -> dict:
    """The one record of an evidence file of the host."""
    return json.loads((host / rel).read_text(encoding="utf-8"))["records"][0]


def at_deploy_record(host: Path, env: str) -> Path:
    """The deploy record file (``dep-NNNN.json``) of the at-deploy action for *env*."""
    found = [path for path in sorted((host / "spec" / "extras" / "verification").glob("dep-*.json")) if f'"{env}"' in path.read_text(encoding="utf-8")]
    assert len(found) == 1, f"deploy records for {env}: {found}"
    return found[0]


def untracked(host: Path) -> list[str]:
    return [line[3:] for line in git(host, "status", "--porcelain").splitlines()]


def tags(host: Path) -> list[str]:
    return git(host, "tag").split()


def evidence_branch(host: Path, name: str) -> None:
    """What the evidence pull request does: the deploy job's records on a branch of their own, committed (the job runs on the default branch head)."""
    git(host, "checkout", "-q", "-b", name)
    commit_all(host, f"evidence of {name}")


def merge(host: Path, branch: str) -> None:
    """Merge *branch* into the default branch with a merge commit (a pull request)."""
    git(host, "checkout", "-q", "main")
    git(host, "merge", "-q", "--no-ff", "-m", f"merge {branch}", branch)


def production_section(host: Path) -> str:
    """The lines of the "Production verification" section of ``specdev status``."""
    out = run(host, "status")
    assert "Production verification" in out
    return out[out.index("Production verification"):]


# --- row 1 -------------------------------------------------------------------------------------------------------------------


def test_row_1_release_prep_writes_dev_and_ci_evidence_on_a_release_prep_branch(host: Path) -> None:
    git(host, "checkout", "-q", "-b", "release-prep/x")
    assert not (host / PREP_EVIDENCE).exists() and untracked(host) == []
    out = run(host, "release", "prep")
    assert "1 binding(s) run, 1 passed, 0 failed; 0 already proven" in out and f"PASS {BINDING}" in out and "nothing blocks the release" in out
    assert untracked(host) == [PREP_EVIDENCE], "prep writes the evidence of the binding and nothing else, and does not stage it"
    record = evidence(host, PREP_EVIDENCE)
    assert (record["stage"], record["exit_code"], record["guard_matched"], record["about"]) == ("ci", 0, True, [BINDING])
    commit_all(host, "release prep: dev and ci evidence")
    assert git(host, "status", "--porcelain") == "" and git(host, "rev-parse", "--abbrev-ref", "HEAD") == "release-prep/x"


# --- row 2 -------------------------------------------------------------------------------------------------------------------


def test_row_2_merge_keeps_the_code_tree_equal_to_the_evidence_tree(host: Path) -> None:
    recorded = evidence(host, PREP_EVIDENCE)["tested_tree"]
    git(host, "checkout", "-q", "main")
    assert not (host / PREP_EVIDENCE).exists(), "main has not got the evidence yet"
    git(host, "merge", "-q", "--no-ff", "-m", "merge release-prep/x", "release-prep/x")
    assert len(git(host, "rev-list", "--parents", "-n1", "HEAD").split()) == 3, "a merge commit"
    assert context(host).code_tree == recorded, "the code tree of the merged head is the tree the evidence recorded (library call: no command prints it before the cut)"
    out = run(host, "release", "prep", "--json")
    document = json.loads(out)
    assert document["run"] == [] and document["already_proven"] == [BINDING] and document["evidence"] == [], "the command agrees: the evidence is valid for the merged tree"
    assert git(host, "status", "--porcelain") == ""


# --- row 3 -------------------------------------------------------------------------------------------------------------------


def test_row_3_status_shows_production_verification_not_verified(host: Path) -> None:
    """Asserts only the production-verification lines of ``status`` (what the rest of ``status`` prints is other bundles').  The cut has not happened,
    so there is no previous release: ``state: none``.  The ``not verified`` state is asserted in row 8, where a release stands behind HEAD."""
    before = snapshot(host)
    section = production_section(host)
    assert "previous release: none" in section and "state: none" in section
    assert snapshot(host) == before, "status writes nothing"


# --- row 4 -------------------------------------------------------------------------------------------------------------------


def test_row_4_release_creates_an_annotated_tag_on_the_merge_commit(host: Path) -> None:
    head, before = git(host, "rev-parse", "HEAD"), snapshot(host)
    sent: list[list[str]] = []
    real = gitview.run_git
    with patch.object(gitview, "run_git", side_effect=lambda root, args, **kw: (sent.append(list(args)), real(root, args, **kw))[1]):
        out = run(host, "release", "--tag", TAG)
    assert "annotated tag created" in out and head in out and "release gate: 0 error(s)" in out
    assert git(host, "cat-file", "-t", TAG) == "tag" and git(host, "rev-parse", f"{TAG}^{{commit}}") == head
    assert git(host, "tag", "-n1", "-l", TAG).split(None, 1)[1] == f"release {TAG}"
    after = snapshot(host)
    assert after["files"] == before["files"] and after["head"] == head and git(host, "status", "--porcelain") == "", "the cut writes the tag and nothing else"
    added = set(str(after["refs"]).splitlines()) - set(str(before["refs"]).splitlines())
    assert len(added) == 1 and next(iter(added)).endswith(f"refs/tags/{TAG}"), "the only new ref is the tag"
    assert tags(host) == [TAG] and git(host, "remote") == "" and not [args for args in sent if args[0] in {"push", "commit", "fetch"}]
    # row 5: the tag push is simulated; the host has no remote, so nothing is contacted


# --- rows 6 and 7 ------------------------------------------------------------------------------------------------------------


def test_row_6_staging_job_records_install_check_evidence_and_at_deploy_record(host: Path) -> None:
    """The staging deploy job, from the default branch head: the deploy preamble's commands, no release check; its records go to an evidence branch."""
    tree = evidence(host, PREP_EVIDENCE)["tested_tree"]
    out = run(host, "third-party", "check", "--installed", f"{LOCKED_PIN[0]}={LOCKED_PIN[1]}", "--env", "staging", "--tag", TAG)
    assert f"{LOCKED_PIN[0]}: installed {LOCKED_PIN[1]} is the pin" in out
    install = evidence(host, INSTALL_STAGING)
    assert (install["type"], install["env"], install["tag"], install["installed_versions"]) == ("install-check", "staging", TAG, {LOCKED_PIN[0]: LOCKED_PIN[1]})
    out = run(host, "verify", "run", "--all", "--stage", "staging", "--only-stage")
    assert f"PASS {LATENCY_BINDING} at staging" in out and "1 run, 1 passed, 0 failed" in out
    staged = evidence(host, STAGING_EVIDENCE)
    assert (staged["stage"], staged["exit_code"], staged["tested_tree"]) == ("staging", 0, tree), "the staging evidence names the tree the release was cut on"
    out = run(host, "plan", "record", "--at-deploy", ACTION, "--env", "staging", "--tag", TAG)
    assert f"{ACTION} done at staging" in out
    assert sorted(untracked(host)) == sorted([INSTALL_STAGING, STAGING_EVIDENCE, at_deploy_record(host, "staging").relative_to(host).as_posix()])
    assert tags(host) == [TAG], "no release check ran and no tag moved"
    evidence_branch(host, "specdev-evidence/staging")


# --- rows 7 and 8 ------------------------------------------------------------------------------------------------------------


def test_row_8_prod_gate_passes_then_fails_without_the_staging_record(host: Path) -> None:
    merge(host, "specdev-evidence/staging")  # row 7
    assert git(host, "rev-parse", "HEAD") != git(host, "rev-parse", f"{TAG}^{{commit}}"), "the default branch head is past the tag"
    section = production_section(host)
    assert f"previous release: {TAG}" in section and "state: not verified (released, awaiting production proof)" in section
    tree = evidence(host, PREP_EVIDENCE)["tested_tree"]
    before = snapshot(host)
    out = run(host, "release", "check", "--stage", "prod", "--tag", TAG)
    assert "passes" in out and tree in out
    assert snapshot(host) == before, "release check writes nothing"

    # the spec moves on after the tag: the gate still reads the spec AT the tag (the code tree of the tag is computed with the spec folder of that commit)
    set_scope(host, "fr-password-reset", "in")
    commit_all(host, "a later spec edit on the default branch")
    out = run(host, "release", "check", "--stage", "prod", "--tag", TAG)
    assert "passes" in out and tree in out
    git(host, "revert", "--no-edit", "HEAD")

    # the staging evidence record is removed: refused, with E347 and the owner of the gate (there is no E922: ruling N2)
    git(host, "rm", "-q", STAGING_EVIDENCE)
    commit_all(host, "the staging evidence record is removed")
    before = snapshot(host)
    out = run(host, "release", "check", "--stage", "prod", "--tag", TAG, want=1)
    assert "blocked" in out and "E347" in out and "NO_EVIDENCE" in out and "E922" not in out
    refused = json.loads(run(host, "release", "check", "--stage", "prod", "--tag", TAG, "--json", want=1))
    assert refused["status"] == "FAIL" and [(error["code"], error["owner"], error["node_id"]) for error in refused["errors"]] == [("E347", "release-gate", NFR)]
    assert snapshot(host) == before
    git(host, "revert", "--no-edit", "HEAD")  # restore
    assert "passes" in run(host, "release", "check", "--stage", "prod", "--tag", TAG)

    # the staging at-deploy record is not read at the production gate (the next release owes it): removing it does not block the deploy
    git(host, "rm", "-q", at_deploy_record(host, "staging").relative_to(host).as_posix())
    commit_all(host, "the staging at-deploy record is removed")
    assert "passes" in run(host, "release", "check", "--stage", "prod", "--tag", TAG)
    assert "no done record for staging" in production_section(host)
    git(host, "revert", "--no-edit", "HEAD")
    assert "no done record for staging" not in production_section(host)


# --- row 9 -------------------------------------------------------------------------------------------------------------------


def test_row_9_prod_evidence_and_at_deploy_records_merge(host: Path) -> None:
    """The production deploy job: the preamble's gate first, then the records; they reach the default branch by their evidence branch."""
    assert "passes" in run(host, "release", "check", "--stage", "prod", "--tag", TAG)
    out = run(host, "third-party", "check", "--installed", f"{LOCKED_PIN[0]}={LOCKED_PIN[1]}", "--env", "prod", "--tag", TAG)
    assert f"recorded extras/verification/{INSTALL_PROD.rsplit('/', 1)[1]}" in out
    assert "0 run, 0 passed, 0 failed" in run(host, "verify", "run", "--all", "--stage", "prod", "--only-stage"), "no binding of the host is bound at prod"
    assert f"{ACTION} done at prod" in run(host, "plan", "record", "--at-deploy", ACTION, "--env", "prod", "--tag", TAG)
    assert sorted(untracked(host)) == sorted([INSTALL_PROD, at_deploy_record(host, "prod").relative_to(host).as_posix()])
    evidence_branch(host, "specdev-evidence/prod")
    merge(host, "specdev-evidence/prod")
    assert git(host, "status", "--porcelain") == ""
    section = production_section(host)
    assert f"previous release: {TAG}" in section and "state: verified in production" in section


# --- row 10 ------------------------------------------------------------------------------------------------------------------


def test_row_10_next_release_passes_fails_without_prod_evidence_and_passes_after_rollback(host: Path) -> None:
    advance(host)  # the next release carries code that the first did not
    out = run(host, "release", "--tag", NEXT_TAG)
    assert "annotated tag created" in out and git(host, "rev-parse", f"{NEXT_TAG}^{{commit}}") == git(host, "rev-parse", "HEAD")
    assert tags(host) == [TAG, NEXT_TAG]

    # the person did not push the tag; the production record of v1.0.0 is deleted and the cut is tried again on the same commit
    git(host, "tag", "-d", NEXT_TAG)
    git(host, "rm", "-q", at_deploy_record(host, "prod").relative_to(host).as_posix())
    commit_all(host, "the production at-deploy record is deleted")
    before = snapshot(host)
    out = run(host, "release", "--tag", NEXT_TAG, want=1)
    assert "E920" in out and f"the previous release {TAG} is not verified in production" in out and f"{ACTION} has no done record for prod" in out
    assert f"specdev release rollback {TAG}" in out and "not tagged" in out
    assert tags(host) == [TAG] and snapshot(host) == before, "a refused cut writes nothing"
    assert "not verified" in production_section(host)

    # the waiver: a rollback record of v1.0.0, committed
    assert "the file is written, not committed" in run(host, "release", "rollback", TAG, "--reason", "v1.0.0 never reached production")
    assert json.loads((host / ROLLBACK).read_text(encoding="utf-8"))["reason"] == "v1.0.0 never reached production"
    assert "E910" in run(host, "release", "--tag", NEXT_TAG, want=1), "the record is not committed yet: the tree is not clean"
    commit_all(host, "rollback record of v1.0.0")
    out = run(host, "release", "--tag", NEXT_TAG)
    assert "annotated tag created" in out and tags(host) == [TAG, NEXT_TAG]
    assert "state: rollback recorded" in production_section(host)
