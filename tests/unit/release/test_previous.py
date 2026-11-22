"""The previous release and the next-release check (WI-M9-04): one tag lookup, then P is judged AT its own commit with the checkout's evidence."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.host_declarations import HostDeclarations
from specdev_tools.graph import gitview
from specdev_tools.graph.gitview import toolkit_stamp_at
from specdev_tools.lifecycle.plan_records import Address, record_at_deploy
from specdev_tools.release import records
from specdev_tools.release.previous import check_next_release, predates_1_2_0, previous_release
from specdev_tools.release.tag_state import release_tag_pattern, tag_matches, tag_state
from specdev_tools.proof.validity import ProofContext
from specdev_tools.verify.code_tree import code_tree_for_host
from unit.graph._synth import ROOT, git
from unit.lifecycle._record_support import ITEM, PLAN, action, closed_row, plan_host
from unit.release._support import PATTERN, advance, commit, declare, latency_host, release_host, stamp, tag
from unit.verify._support import edit_doc, write

REPO = str(ROOT)


def _check(host: Path):
    return check_next_release(str(host), str(host / "spec"), REPO)


def _codes(result) -> list[str]:
    return [finding.code for finding in (*result.errors, *result.warnings)]


def _released(tmp_path: Path, version: str | None = "1.2.0") -> Path:
    """A release-ready host stamped *version* (not stamped when ``None``), tagged v1.0.0 and one commit further on."""
    host = release_host(tmp_path)
    if version is None:
        (host / "spec" / "specdev_version").unlink()
    else:
        stamp(host, version)
    commit(host, "release one")
    tag(host, "v1.0.0")
    advance(host)
    return host


# --- which release is the previous one ----------------------------------------------------------------------------------


def test_previous_release_nearest_ancestor_matching_pattern(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    second = advance(host)
    tag(host, "v1.1.0")
    advance(host, "two")
    git(host, "checkout", "-q", "-b", "side", "v1.0.0")
    advance(host, "side")
    tag(host, "v9.9.9")
    git(host, "checkout", "-q", "main")
    found = previous_release(str(host), "HEAD", PATTERN)
    assert (found.tag, found.commit) == ("v1.1.0", second)  # v9.9.9 is on a branch HEAD does not descend from


def test_two_tags_the_same_distance_back_the_newest_is_the_previous_release(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    for name, date in (("v1.0.0", "2026-03-01T00:00:00"), ("v0.9.0", "2026-01-01T00:00:00")):  # the newest tag sorts first by name
        subprocess.run(["git", "-C", str(host), "tag", "-a", "-m", name, name, "HEAD"], check=True, env={**os.environ, "GIT_COMMITTER_DATE": date})
    advance(host)
    assert previous_release(str(host), "HEAD", PATTERN).tag == "v1.0.0"


def test_the_pattern_is_searched_in_the_tag_name_not_matched_against_all_of_it(tmp_path: Path) -> None:
    """``docs/developers/host_declarations.md``: the pattern is searched in the name, so it is anchored with ``^`` and ``$`` to be exact."""
    assert tag_matches("v[0-9]+", "release-v9-final") and tag_matches("v[0-9]+", "xv1") and not tag_matches("^v[0-9]+$", "xv1")
    host = release_host(tmp_path)
    tag(host, "xv1")
    advance(host)
    assert previous_release(str(host), "HEAD", "v[0-9]+").tag == "xv1"
    assert previous_release(str(host), "HEAD", "^v[0-9]+$") is None


def test_candidate_stage_tags_ignored(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    advance(host)
    tag(host, "v1.1.0-stage")
    advance(host, "two")
    assert previous_release(str(host), "HEAD", PATTERN).tag == "v1.0.0"


def test_tag_on_release_commit_itself_excluded(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    advance(host)
    tag(host, "v1.1.0")
    assert previous_release(str(host), "HEAD", PATTERN).tag == "v1.0.0"
    assert previous_release(str(host), "v1.0.0", PATTERN) is None


def test_lightweight_and_annotated_tags_both_resolve(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    first = git(host, "rev-parse", "HEAD")
    tag(host, "v1.0.0")
    second = advance(host)
    tag(host, "v1.1.0", annotated=True)
    advance(host, "two")
    assert previous_release(str(host), "HEAD", PATTERN).commit == second
    assert previous_release(str(host), "v1.1.0", PATTERN).commit == first
    git(host, "tag", "-d", "v1.1.0")
    tag(host, "v1.1.0", annotated=True, ref=first)
    assert previous_release(str(host), "HEAD", PATTERN).commit == first  # the annotated tag is read through its commit


def test_first_release_has_no_previous_and_passes(tmp_path: Path) -> None:
    result = _check(release_host(tmp_path))
    assert result.previous is None and not result.errors and _codes(result) == ["W937"]


# --- a release cut before the 1.2.0 spec -------------------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["1.1.1", None, "garbage: [", "1.2.0rc1"])
def test_previous_predating_1_2_0_passes_with_W938(tmp_path: Path, version: str | None) -> None:
    host = release_host(tmp_path)
    spec_version = host / "spec" / "specdev_version"
    if version is None:
        spec_version.unlink()
    elif version == "garbage: [":
        write(spec_version, version + "\n")
    else:
        stamp(host, version)
    commit(host, "release one")
    tag(host, "v1.0.0")
    advance(host)
    result = _check(host)
    if version == "1.2.0rc1":  # a pre-release suffix reads as 1.2.0: it has a 1.2.0 spec, and nothing waits for production
        assert _codes(result) == [] and result.previous.tag == "v1.0.0"
    else:
        assert not result.errors and _codes(result) == ["W938"] and "v1.0.0" in result.warnings[0].message


def test_a_spec_stamped_1_2_0_with_no_production_evidence_is_E920(tmp_path: Path) -> None:
    host = latency_host(tmp_path, run_it=False)
    tag(host, "v1.0.0")
    advance(host)
    result = _check(host)
    assert [error.code for error in result.errors] == ["E920"] and not result.warnings
    assert "v1.0.0" in result.errors[0].message and "ver-latency" in result.errors[0].message and "rollback" in result.errors[0].message


# --- verified, unverified and waived ---------------------------------------------------------------------------------------


def test_previous_unverified_blocks_E920(tmp_path: Path) -> None:
    host = latency_host(tmp_path, run_it=False)
    tag(host, "v1.0.0")
    advance(host)
    [error] = _check(host).errors
    assert error.code == "E920" and error.owner == "release-gate" and "NO_EVIDENCE" in error.message


def test_rollback_record_waives_previous(tmp_path: Path) -> None:
    host = latency_host(tmp_path, run_it=False)
    tag(host, "v1.0.0")
    advance(host)
    assert _check(host).errors
    records.write_rollback(str(host), str(host / "spec"), "v1.0.0", "the release was rolled back before production", PATTERN)
    result = _check(host)
    assert not result.errors and not result.warnings and result.previous.tag == "v1.0.0"


def test_previous_verified_with_prod_evidence_and_at_deploy_records_passes(tmp_path: Path) -> None:
    """Evidence run at P's tree is valid for P after the code moved on; the reading is AT P, so later bindings and a changed tree do not count against it."""
    host = latency_host(tmp_path, run_it=True)
    tag(host, "v1.0.0")
    advance(host)
    write(host / "src" / "hello.txt", "changed after the release\n")
    commit(host, "more")
    result = _check(host)
    assert not result.errors and not result.warnings and result.previous.tag == "v1.0.0"


def _at_deploy_host(tmp_path: Path) -> Path:
    """A closed milestone whose plan marks an action ``at_deploy`` for staging and prod, released as v1.0.0 with no deploy record yet."""
    host = plan_host(tmp_path, action("a03", at_deploy=["staging", "prod"]))
    closed_row(host)
    declare(host)
    stamp(host, "1.2.0")
    commit(host, "closed")
    tag(host, "v1.0.0")
    advance(host)
    return host


def _record(host: Path, env: str) -> None:
    record_at_deploy(str(host / "spec"), REPO, str(host), Address(ITEM, "a03"), env, "done")


def test_missing_at_deploy_record_for_one_env_blocks(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    [error] = _check(host).errors
    assert error.code == "E920" and f"{ITEM}/a03 has no done record for staging" in error.message and "for prod" in error.message
    _record(host, "staging")
    [error] = _check(host).errors
    assert "for staging" not in error.message and f"{ITEM}/a03 has no done record for prod" in error.message
    _record(host, "prod")
    assert not _check(host).errors


def test_the_at_deploy_plan_of_the_previous_release_is_read_at_that_release_not_in_the_checkout(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    _record(host, "staging")
    [error] = _check(host).errors
    assert f"{ITEM}/a03 has no done record for prod" in error.message

    def narrow(document: dict) -> None:
        for action in document["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"]:
            if action.get("id") == "a03":
                action["at_deploy"] = ["staging"]

    edit_doc(host, PLAN, narrow)  # after the release: the checkout's plan no longer owes prod, the plan at v1.0.0 does
    commit(host, "plan edited after the release")
    [error] = _check(host).errors
    assert error.code == "E920" and f"{ITEM}/a03 has no done record for prod" in error.message


def test_a_milestone_the_release_before_it_closed_owes_nothing_to_the_next(tmp_path: Path) -> None:
    """P's milestones are those done at P and not done at the release before P: an at-deploy action of an older milestone is that older release's."""
    host = _at_deploy_host(tmp_path)
    git(host, "tag", "-d", "v1.0.0")
    tag(host, "v1.0.0", ref="HEAD~1")
    tag(host, "v1.1.0")
    advance(host, "two")
    assert not _check(host).errors  # done at v1.0.0 already: owed by v1.0.0's check, not by v1.1.0's


# --- the pieces --------------------------------------------------------------------------------------------------------------


def test_predates_reads_the_stamp_at_the_commit_not_the_checkout(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    stamp(host, "1.2.0")
    commit(host, "stamped")
    stamped = git(host, "rev-parse", "HEAD")
    stamp(host, "1.1.1")
    commit(host, "stamped back")
    assert not predates_1_2_0(str(host), str(host / "spec"), stamped) and predates_1_2_0(str(host), str(host / "spec"), "HEAD")


def test_a_spec_with_no_stamp_file_at_the_commit_predates_1_2_0(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    (host / "spec" / "specdev_version").unlink()
    commit(host, "no stamp")
    assert predates_1_2_0(str(host), str(host / "spec"), "HEAD") and toolkit_stamp_at("HEAD", str(host), str(host / "spec")) is None
    assert toolkit_stamp_at("HEAD~1", str(host), str(host / "spec")) is not None


def test_a_stamp_file_that_cannot_be_parsed_reads_as_no_stamp(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    write(host / "spec" / "specdev_version", "toolkit_version: [\n")
    commit(host, "damaged stamp")
    assert toolkit_stamp_at("HEAD", str(host), str(host / "spec")) is None
    assert predates_1_2_0(str(host), str(host / "spec"), "HEAD")


def test_a_git_failure_reading_the_stamp_is_E708_not_a_release_that_predates(tmp_path: Path) -> None:
    host = _released(tmp_path)
    real = gitview.run_git

    def failing_archive(root, args, **kw):
        if args[0] == "archive":
            return subprocess.CompletedProcess(["git", *args], 128, b"", b"fatal: unable to read tree object")
        return real(root, args, **kw)

    with patch.object(gitview, "run_git", side_effect=failing_archive):
        with pytest.raises(FindingError) as caught:
            predates_1_2_0(str(host), str(host / "spec"), "v1.0.0")
        assert caught.value.error.code == "E708"
        with pytest.raises(FindingError) as at_the_caller:
            _check(host)  # not "the previous release predates 1.2.0" (W938)
        assert at_the_caller.value.error.code == "E708"
    assert not predates_1_2_0(str(host), str(host / "spec"), "v1.0.0")


def test_the_pattern_is_read_from_the_declarations_and_refused_when_absent_or_broken() -> None:
    assert release_tag_pattern(HostDeclarations(release_tag_pattern=PATTERN)) == PATTERN
    for declared in (None, "", "("):
        with pytest.raises(FindingError) as caught:
            release_tag_pattern(HostDeclarations(release_tag_pattern=declared))
        assert caught.value.error.code == "E911"


def test_code_tree_at_a_commit_from_an_archived_spec_equals_the_live_one(tmp_path: Path) -> None:
    host = latency_host(tmp_path, run_it=True)
    tag(host, "v1.0.0")
    at = git(host, "rev-parse", "HEAD")
    live = code_tree_for_host(str(host), str(host / "spec"), at)
    write(host / "src" / "hello.txt", "later\n")
    commit(host, "later")
    with tag_state(str(host), str(host / "spec"), REPO, "v1.0.0") as state:
        assert str(host / "spec") != state.spec_dir
        assert state.proof.code_tree == live == code_tree_for_host(str(host), state.spec_dir, at, spec_in_host=str(host / "spec"))
        # without the live spec folder named, the archived folder (outside the host) would stay IN the tree: a different id
        assert code_tree_for_host(str(host), state.spec_dir, at) != live
        assert ProofContext(str(host), str(host / "spec"), state.proof.evidence_dir, commit=at).code_tree == live
