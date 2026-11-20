"""The worked example of the design (section 12) end to end, through the CLI where a command exists: bind, run, prove, change, pin, close, realise."""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.proof.proof import PENDING_STAGE, PROVEN, UNPROVEN
from specdev_tools.proof.validity import STALE_HASH, STALE_TP_VERSION, STALE_TREE
from unit.graph._synth import git
from unit.proof._closed import CRITERION, FR, add_milestone, closed_example, criterion, delete_fr, reword_criterion, unresolved, with_removal
from unit.proof._support import API, FIXTURE, NFR, edit_code, edit_doc, prove
from unit.trace._lock_support import git_copy_of_example, run_on_example
from unit.verify._support import commit_all, write, write_json

LATENCY_FIXTURE = "fix-reset-email-delivery-time"
DECLARATIONS = {
    "$schema": "vc:host-declarations",
    "pin_sources": {"tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}]},
}
RECORDS = Path("spec") / "extras" / "verification"
EXPIRED_TOKEN_TEST = ["python3", "src/expired_token_test.py"]
PROBE = ["python3", "src/latency_probe.py"]


def _lock(version: str) -> dict:
    return {"packages": {"node_modules/argon2": {"version": version}}}


def _example_with_code(tmp_path: Path) -> Path:
    host = git_copy_of_example(tmp_path / "host")
    write_json(host / "spec" / "common" / "host_declarations.json", DECLARATIONS)
    write_json(host / "package-lock.json", _lock("0.41.1"))
    write(host / "src" / "expired_token_test.py", "print('expired token case passed')\n")
    write(host / "src" / "latency_probe.py", "print('reset email delivered in 12 s')\n")
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"].append({
        "fixture_id": LATENCY_FIXTURE, "mode": "contract", "verifies": [NFR], "input": {"method": "POST", "path": "/v1/password-resets"},
        "expected": {"status": 202}, "tag_ref": {"id": "cn:core:tag:critical-path", "kind": "tag", "version": "1.0.0"},
    }))
    commit_all(host, "code, declarations and a latency fixture")
    return host


def _bound_and_run(tmp_path: Path) -> Path:
    host = _example_with_code(tmp_path)
    code, out = run_on_example(host, "verify", "bind", FIXTURE, "--command", " ".join(EXPIRED_TOKEN_TEST), "--guard", "expired token .*passed")
    assert code == 0 and "(stage dev" in out, out
    code, out = run_on_example(host, "verify", "bind", LATENCY_FIXTURE, "--command", " ".join(PROBE), "--guard", "delivered in [0-9]+ s")
    assert code == 0 and "(stage staging" in out, out
    code, out = run_on_example(host, "verify", "run", "--all")
    assert code == 0, out
    return host


def _evidence(host: Path) -> dict:
    return json.loads((host / RECORDS / "evd-password-reset-expired-token-dev.json").read_text(encoding="utf-8"))["records"][0]


def test_step_1_bind_gives_the_computed_stage_and_both_targets_and_refuses_a_forced_dev_stage(tmp_path: Path) -> None:
    host = _example_with_code(tmp_path)
    code, out = run_on_example(host, "verify", "bind", FIXTURE, "--command", " ".join(EXPIRED_TOKEN_TEST), "--guard", "expired token .*passed")
    assert code == 0, out
    stored = json.loads((host / RECORDS / "ver-password-reset-expired-token.json").read_text(encoding="utf-8"))["records"][0]
    assert (stored["stage"], stored["proves"]) == ("dev", [CRITERION, API])
    code, out = run_on_example(host, "verify", "bind", LATENCY_FIXTURE, "--command", " ".join(PROBE), "--guard", "delivered", "--stage", "dev")
    assert code == 1 and "E330" in out
    code, out = run_on_example(host, "verify", "bind", LATENCY_FIXTURE, "--command", " ".join(PROBE), "--guard", "delivered")
    assert code == 0 and "stage staging" in out


def test_step_2_run_records_the_installed_version_and_proof_follows_the_cap(tmp_path: Path) -> None:
    host = _bound_and_run(tmp_path)
    assert _evidence(host)["installed_versions"] == {"tp-argon2": "0.41.1"}
    assert (prove(host, CRITERION).status, prove(host, API).status, prove(host, NFR, "dev").status) == (PROVEN, PROVEN, PENDING_STAGE)
    assert prove(host, NFR, "staging").status == UNPROVEN


def test_step_3_code_edit_is_stale_tree_spec_side_edits_leave_it_valid_and_a_fixture_edit_is_stale_hash(tmp_path: Path) -> None:
    host = _bound_and_run(tmp_path)
    edit_doc(host, "impl_context/ms_account_recovery_plan.json", lambda doc: doc.update(note="a plan edit"))
    lock = host / "spec" / "extras" / "trace.lock.json"
    lock.write_text(lock.read_text(encoding="utf-8").rstrip() + "\n\n", encoding="utf-8")
    assert prove(host, CRITERION).status == PROVEN
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint answers 404 for a stale token."))
    assert prove(host, CRITERION).shortfalls[0].reason == STALE_HASH
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"][0].update(description="The confirm endpoint rejects a token issued 31 minutes earlier and leaves the password unchanged."))
    assert prove(host, CRITERION).status == PROVEN
    edit_code(host)
    assert prove(host, CRITERION).shortfalls[0].reason == STALE_TREE


def test_pin_bump_makes_evidence_stale_tp_version(tmp_path: Path) -> None:
    host = _bound_and_run(tmp_path)
    code, out = run_on_example(host, "third-party", "pin", "tp-argon2", "0.42.0")
    assert code == 0, out
    result = prove(host, API)
    assert (result.status, result.shortfalls[0].reason) == (UNPROVEN, STALE_TP_VERSION)
    code, out = run_on_example(host, "third-party", "check")
    assert code == 1 and "E337" in out
    write_json(host / "package-lock.json", _lock("0.42.0"))
    code, out = run_on_example(host, "third-party", "check")
    assert code == 0, out
    code, out = run_on_example(host, "verify", "run", "--all")
    assert code == 0 and prove(host, API).status == PROVEN, out


def test_step_5_realisation_follows_the_edits_and_the_unresolved_list_empties_once_the_milestones_close(tmp_path: Path) -> None:
    host = closed_example(tmp_path)
    assert unresolved(host) == []
    reword_criterion(host, CRITERION, "A reset link older than 31 minutes is refused with HTTP 410 and the password stays as it was.")
    assert [entry.kind for entry in unresolved(host)] == ["outdated"]
    add_milestone(host, "ms-token-ttl", [criterion("tc-ttl-31", refines=[CRITERION])], done=True)
    assert unresolved(host) == []
    delete_fr(host, FR)
    assert {entry.kind for entry in unresolved(host)} == {"removed"}
    with_removal(host, removes=[FR])
    assert unresolved(host) == []


def test_step_6_a_dirty_submodule_gives_w350_on_a_run(tmp_path: Path) -> None:
    host = _bound_and_run(tmp_path)
    library = tmp_path / "library"
    library.mkdir()
    git(library, "init", "-q", "-b", "main")
    write(library / "lib.py", "one\n")
    commit_all(library, "library")
    git(host, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "theme")
    git(host, "commit", "-q", "-m", "add the submodule")
    write(host / "theme" / "lib.py", "uncommitted\n")
    code, out = run_on_example(host, "verify", "run", "--all")
    assert code == 0 and "W350 submodule 'theme' has uncommitted content" in out
