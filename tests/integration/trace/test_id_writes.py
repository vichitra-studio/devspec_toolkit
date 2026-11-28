"""``specdev json patch|insert|delete --id`` and ``json insert --step`` end to end, on the worked example (WI-M5-09).

Each test copies the example (spec folder, seed documents and the committed trace lock) into a temporary host and runs the
command in this process through ``run_cli``.  The jq-path forms of the same subcommands, the ``--repo-root`` flag of
``json delete|keys|structure`` (DEVSPEC-155) and the differential schema check (DEVSPEC-317) are tested here too.
"""
from __future__ import annotations

import difflib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.json_utils import JsonUtilsError, check_edit
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.id_write_commands import is_id_write
from specdev_tools.trace.lockfile import lock_path, read_lock, with_write_lock
from specdev_tools.trace.suspects import find_suspects

from unit.graph._synth import ROOT, graph_check, run_cli
from unit.trace._lock_support import EXAMPLE_HOST

FR_FILE = "04_fr_list.json"
FR = "fr-password-reset"
FR_REQUEST = "fr-password-reset-request"
API = "api-password-reset-confirm"
CRITERION = "ac-password-reset-3"
FIXTURE = "fix-password-reset-expired-token"
EDGE_CASE = "ec-token-at-expiry-second"
PLAN_ITEM = "PWRESET_CONFIRM_EXPIRED_01"
PLAN_FILE = "impl_context/ms_account_recovery_plan.json"
STEPS_AFTER_FR = ["05", "06", "07", "08", "09", "11", "14", "15", "16a"]


@pytest.fixture
def host(tmp_path: Path) -> Path:
    """The worked example with its seed documents and current lock, as a host folder."""
    root = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    return root


def _flags(host: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]


def _run(host: Path, *args: str) -> tuple[int, str]:
    """``specdev json <args>`` against *host* with the three root flags, text output."""
    return run_cli("json", *args, *_flags(host))


def _json(host: Path, *args: str, code: int = 0) -> dict[str, Any]:
    status, out = run_cli("json", *args, *_flags(host), "--json")
    assert status == code, out
    document = json.loads(out)
    assert isinstance(document, dict)
    return document


def _doc(host: Path, rel: str) -> dict[str, Any]:
    return json.loads((host / "spec" / rel).read_text(encoding="utf-8"))


def _write_doc(host: Path, rel: str, document: dict[str, Any]) -> None:
    (host / "spec" / rel).write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")


def _snapshot(host: Path) -> dict[Path, bytes]:
    """Every file of the spec folder (the lock included) as bytes."""
    return {path: path.read_bytes() for path in (host / "spec").rglob("*") if path.is_file()}


def _item(host: Path, rel: str, collection: str, id_field: str, node_id: str) -> dict[str, Any]:
    return next(item for item in _doc(host, rel)[collection] if item[id_field] == node_id)


def _lock_keys(host: Path) -> set[tuple[str, str, str]]:
    return {entry.key for entry in read_lock(str(host / "spec")).entries}


# --- DEVSPEC-155: --repo-root on json delete, keys and structure ---------------------------------------------------------

def test_json_delete_accepts_repo_root(tmp_path: Path) -> None:
    """``--repo-root`` is accepted; a delete validates as patch does, so a file without ``$schema`` is refused by name."""
    scratch = tmp_path / "scratch.json"
    scratch.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    before = scratch.read_bytes()
    code, out = run_cli("json", "delete", str(scratch), ".a", "--repo-root", str(ROOT))
    assert code == 1 and "declares no $schema; json delete validates writes" in out
    assert scratch.read_bytes() == before


def test_json_keys_accepts_repo_root(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.json"
    scratch.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    plain = run_cli("json", "keys", str(scratch), ".")
    assert run_cli("json", "keys", str(scratch), ".", "--repo-root", str(ROOT)) == plain and plain[0] == 0
    assert json.loads(plain[1]) == ["a", "b"]


def test_json_structure_accepts_repo_root(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.json"
    scratch.write_text(json.dumps({"a": 1, "b": [1]}), encoding="utf-8")
    plain = run_cli("json", "structure", str(scratch), ".")
    assert run_cli("json", "structure", str(scratch), ".", "--repo-root", str(ROOT)) == plain and plain[0] == 0
    assert "a: int" in plain[1]


def test_id_form_refusal_names_its_own_command(host: Path) -> None:
    """Without ``$schema`` the write is refused as E767, and the refusal names the verb that was typed."""
    document = _doc(host, FR_FILE)
    del document["$schema"]
    _write_doc(host, FR_FILE, document)
    before = _snapshot(host)
    forms = {
        "patch": ("patch", "--id", FR, ".priority", '"should-have"'),
        "insert": ("insert", "--id", FR, ".acceptance_criteria", '{"text": "x", "scope": "in"}'),
        "insert --step": ("insert", "--step", "04", ".functional_requirements", json.dumps({"fr_id": "fr-x"})),
    }
    for verb, args in forms.items():
        status, out = _run(host, *args)
        command = verb.split()[0]
        assert status == 1 and out.startswith("E767"), (verb, out)
        assert f"json {command} validates writes" in out, (verb, out)
        if command == "patch":
            assert "json insert validates writes" not in out
        else:
            assert "json patch validates writes" not in out
    assert _snapshot(host) == before


# --- the id forms: lookup, validation, lock ---------------------------------------------------------------------------

def test_patch_by_id_resolves_validates_and_writes_lock_entry(host: Path) -> None:
    link = (API, "derives_from", FR_REQUEST)
    assert link not in _lock_keys(host)
    result = _json(host, "patch", "--id", API, ".derives_from", json.dumps([FR, FR_REQUEST]))
    assert result["written"] is True and (result["id"], result["file"]) == (API, "05_interface_contracts.json")
    assert _item(host, "05_interface_contracts.json", "apis", "api_id", API)["derives_from"] == [FR, FR_REQUEST]
    assert link in _lock_keys(host)
    graph = build_graph(str(host / "spec"), str(ROOT))
    hashes = compute_all(graph, read_seed_texts(graph, str(host)))
    entry = read_lock(str(host / "spec")).get(*link)
    assert entry is not None and (entry.content_hash, entry.chain_stamp) == hashes[FR_REQUEST]
    assert [(e["holder"], e["field"], e["target"]) for e in result["lock"]["written"]] == [link]
    assert graph_check(host / "spec")["status"] == "PASS"
    before = _snapshot(host)
    status, out = _run(host, "patch", "--id", API, ".derives_from", '"not-a-list"')
    assert status == 1 and out.startswith("E767") and "schema violation" in out
    assert _snapshot(host) == before


def test_differential_check_ignores_a_preexisting_violation_and_refuses_a_new_one(host: Path) -> None:
    document = _doc(host, FR_FILE)
    document["functional_requirements"] = [document["functional_requirements"][0]]
    _write_doc(host, FR_FILE, document)
    before = _snapshot(host)
    assert run_cli("validate", str(host / "spec" / FR_FILE), "--repo-root", str(ROOT))[0] != 0
    status, out = run_cli("node", "status", FR, "deprecated", *_flags(host))
    assert status == 0, out
    assert _json(host, "patch", "--id", FR, ".statement", '"The system shall let a member set a new password."')["written"]
    assert _item(host, FR_FILE, "functional_requirements", "fr_id", FR)["lifecycle"] == "deprecated"
    status, out = run_cli("json", "patch", str(host / "spec" / FR_FILE), ".functional_requirements[0].statement", '"The system shall let a registered member set a new password, edited by path."', "--repo-root", str(ROOT))
    assert status == 0, out
    after = _snapshot(host)
    assert after != before
    new_path = _run(host, "patch", "--id", FR, ".acceptance_criteria", '[{"criterion_id": "ac-only", "text": "x", "scope": "in"}]')
    new_keyword = _run(host, "patch", "--id", FR, ".priority", '"urgent"')
    assert new_path[0] == new_keyword[0] == 1 and new_path[1].startswith("E767") and new_keyword[1].startswith("E767")
    assert _snapshot(host) == after


def test_differential_check_counts_violations_per_path_and_keyword(host: Path) -> None:
    """The check compares how many violations of each keyword each path has, not their messages (DEVSPEC-317)."""
    document = _doc(host, FR_FILE)
    document["functional_requirements"] = document["functional_requirements"][:1]
    original = json.dumps(document)
    edited = json.loads(original)
    edited["functional_requirements"][0]["statement"] = "The system shall let a member set a new password, in other words."
    check_edit(FR_FILE, original, json.dumps(edited), str(ROOT))
    del edited["functional_requirements"][0]["capability_ref"]
    with pytest.raises(JsonUtilsError, match=r"\.functional_requirements\[0\].*'capability_ref' is a required property"):
        check_edit(FR_FILE, original, json.dumps(edited), str(ROOT))


def test_duplicate_id_write_is_refused_with_e767(host: Path) -> None:
    document = _doc(host, FR_FILE)
    document["functional_requirements"].append({**document["functional_requirements"][1]})
    _write_doc(host, FR_FILE, document)
    before = _snapshot(host)
    status, out = _run(host, "patch", "--id", FR_REQUEST, ".statement", '"Changed."')
    assert status == 1 and out.startswith("E767") and "defined more than once (E704); fix the duplicate first" in out
    assert _snapshot(host) == before


@pytest.mark.parametrize("action", [("patch", ".statement", '"x"'), ("delete",)], ids=["patch", "delete"])
def test_non_matching_id_exits_nonzero_and_changes_nothing(host: Path, action: tuple[str, ...]) -> None:
    before = _snapshot(host)
    status, out = _run(host, action[0], "--id", "fr-password-rest", *action[1:])
    assert status == 1 and out.startswith("E706") and "nearest: fr-password-reset" in out
    document = json.loads(run_cli("json", action[0], "--id", "fr-password-rest", *action[1:], *_flags(host), "--json")[1])
    assert document["errors"][0]["code"] == "E706"
    assert _snapshot(host) == before


def test_non_matching_id_exits_nonzero_and_changes_nothing_for_field_path_missing(host: Path) -> None:
    before = _snapshot(host)
    status, out = _run(host, "patch", "--id", "fr-no-such-node", ".no_such_field", '"x"')
    assert status == 1 and out.startswith("E706") and "fr-no-such-node" in out
    assert _snapshot(host) == before


def test_delete_lower_index_then_patch_by_id_hits_right_node(host: Path) -> None:
    terms = [item["term_id"] for item in _doc(host, "03_glossary.json")["terms"]]
    assert terms == ["term-reset-token", "term-reset-email-delivery-time-p95"]
    assert _json(host, "delete", "--id", terms[0])["written"]
    assert _json(host, "patch", "--id", terms[1], ".definition", '"Seconds from request to the reset email reaching the mail relay."')["written"]
    remaining = _doc(host, "03_glossary.json")["terms"]
    assert [item["term_id"] for item in remaining] == [terms[1]]
    assert remaining[0]["definition"].startswith("Seconds from request")


def _revocation_fr(**changes: Any) -> dict[str, Any]:
    fr: dict[str, Any] = {
        "statement": "The system shall let an admin revoke an outstanding reset token before it expires.",
        "scope": "in",
        "priority": "must-have",
        "capability_ref": {"id": "cn:project:capability:account-recovery", "kind": "capability", "version": "1.0.0"},
        "derives_from": ["cap-account-recovery"],
        "acceptance_criteria": [
            {"text": "Given an outstanding token, when an admin revokes it, then redeeming it is rejected.", "scope": "in"},
            {"text": "Given a revoked token, when it is redeemed, then no password changes.", "scope": "in"},
        ],
    }
    return {**fr, **changes}


def test_insert_mints_ids_and_shows_targets_with_text(host: Path) -> None:
    result = _json(host, "insert", "--step", "04", ".functional_requirements", json.dumps(_revocation_fr()))
    new_id = result["id"]
    assert new_id.startswith("fr-") and result["minted"][0] == new_id and len(result["minted"]) == 3
    assert all(minted.startswith("ac-") for minted in result["minted"][1:])
    (target,) = result["targets"]
    assert (target["holder"], target["field"], target["target"], target["kind"], target["step"]) == (new_id, "derives_from", "cap-account-recovery", "capability", "01")
    assert "regain access to their account" in target["text"]
    stored = _doc(host, FR_FILE)["functional_requirements"][-1]
    assert stored["fr_id"] == new_id and [c["criterion_id"] for c in stored["acceptance_criteria"]] == result["minted"][1:]
    assert (new_id, "derives_from", "cap-account-recovery") in _lock_keys(host)
    status, out = _run(host, "insert", "--id", new_id, ".acceptance_criteria", '{"text": "Revoking a token an admin does not own is refused.", "scope": "in"}')
    assert status == 0 and "ids minted: ac-revoking-a-token-an-admin-does-not-own-is" in out and "targets:" not in out


def test_write_reports_newly_suspect_links_by_step(host: Path) -> None:
    result = _json(host, "patch", "--id", FR, ".statement", '"The system shall let a member set a new password by redeeming a reset token."')
    assert [item["step"] for item in result["newly_suspect"]] == STEPS_AFTER_FR and all(item["count"] >= 1 for item in result["newly_suspect"])
    graph = build_graph(str(host / "spec"), str(ROOT))
    suspects = find_suspects(graph, read_lock(str(host / "spec")), read_seed_texts(graph, str(host)))
    counted: dict[str, int] = {}
    for suspect in suspects:
        counted[suspect.holder_step or ""] = counted.get(suspect.holder_step or "", 0) + 1
    assert {item["step"]: item["count"] for item in result["newly_suspect"]} == counted
    quiet = _json(host, "patch", "--id", EDGE_CASE, ".description", '"A token redeemed in the second it expires, in any time zone."')
    assert quiet["newly_suspect"] == []


def test_delete_runs_schema_validation_and_removes_held_entries_only(host: Path) -> None:
    before = _snapshot(host)
    status, out = _run(host, "delete", "--id", "inv-reset-token-single-use")
    assert status == 1 and out.startswith("E767") and "schema violation" in out
    assert _snapshot(host) == before
    keys_before = _lock_keys(host)
    held = {key for key in keys_before if key[0] == FIXTURE}
    inbound = {key for key in keys_before if key[2] == FIXTURE}
    assert held and inbound
    result = _json(host, "delete", "--id", FIXTURE)
    assert {(e["holder"], e["field"], e["target"]) for e in result["lock"]["removed"]} == held
    assert _lock_keys(host) == keys_before - held and inbound <= _lock_keys(host)
    assert {(b["holder"], b["field"]) for b in result["broken"]} == {(key[0], key[1]) for key in inbound} | {("ver-password-reset-expired-token", "verifies")}
    assert FIXTURE not in {item["fixture_id"] for item in _doc(host, "08_fixtures.json")["fixtures"]}


def test_deleted_then_readded_id_with_new_text_makes_holders_suspect(host: Path) -> None:
    original = _item(host, "08_fixtures.json", "fixtures", "fixture_id", FIXTURE)
    inbound = {key for key in _lock_keys(host) if key[2] == FIXTURE}
    _json(host, "delete", "--id", FIXTURE)
    assert inbound <= _lock_keys(host)
    changed = {**original, "description": "The confirm endpoint rejects a token issued 45 minutes earlier and leaves the password unchanged."}
    result = _json(host, "insert", "--step", "08", ".fixtures", json.dumps(changed))
    assert result["id"] == FIXTURE and result["newly_suspect"]
    status, out = run_cli("stale", "--json", *_flags(host))
    suspect_keys = {(node["node"], link["field"], link["target"]) for step in json.loads(out)["steps"] for node in step["suspect_nodes"] for link in node["links"]}
    assert inbound <= suspect_keys


def test_refuses_payload_with_hash_or_pin_fields(host: Path) -> None:
    before = _snapshot(host)
    cases = [
        ("patch", "--id", FR, ".content_hash", '"sha256:aa"'),
        ("insert", "--id", FR, ".acceptance_criteria", json.dumps({"text": "x", "scope": "in", "chain_stamp": "sha256:bb"})),
        ("insert", "--id", FR, ".acceptance_criteria", json.dumps({"text": "x", "scope": "in", "spec_ref": {"line_range": "1-2"}})),
        ("insert", "--id", FR, ".acceptance_criteria", json.dumps({"text": "x", "scope": "in", "spec_refs": [{"commit_hash": "abc"}]})),
        ("patch", "--id", PLAN_ITEM, ".milestone_ref", '"ms-account-recovery"'),
    ]
    for case in cases:
        status, out = _run(host, *case)
        assert status == 1 and out.startswith("E768"), (case, out)
    assert _snapshot(host) == before
    status, out = _run(host, "patch", "--id", FR, ".content_hash", '"sha256:aa"')
    assert f"the write to {FR} stores 'content_hash'" in out and "kept in the trace lock, not in a spec file" in out and "attest" not in out, out
    assert "compute it with" not in out, out


def test_wrong_kind_target_refused_with_candidates_hint(host: Path) -> None:
    before = _snapshot(host)
    status, out = _run(host, "insert", "--id", API, ".derives_from", '"cap-account-recovery"')
    assert status == 1 and out.startswith("E767") and "E701" in out and "is a capability" in out
    assert f"specdev node candidates --for {API} --field derives_from" in out
    status, out = _run(host, "insert", "--id", API, ".derives_from", '"fr-nowhere"')
    assert status == 1 and "E700" in out
    status, out = _run(host, "insert", "--step", "04", ".functional_requirements", json.dumps(_revocation_fr(derives_from=["fr-password-reset"])))
    assert status == 1 and "specdev node candidates --kind fr --field derives_from" in out
    assert _snapshot(host) == before


def test_plan_item_link_write_by_id(host: Path) -> None:
    result = _json(host, "insert", "--id", PLAN_ITEM, ".realises", '"tc-confirm-reused-token"')
    assert result["file"] == PLAN_FILE and result["jq_path"] == ".plan.spec_alignment.checklist[0]"
    realises = _doc(host, PLAN_FILE)["plan"]["spec_alignment"]["checklist"][0]["realises"]
    assert realises == ["tc-confirm-expired-token", "tc-confirm-reused-token"]
    assert (PLAN_ITEM, "realises", "tc-confirm-reused-token") in _lock_keys(host)
    assert result["targets"][0]["target"] == "tc-confirm-reused-token" and "HTTP 410" in result["targets"][0]["text"]


def test_insert_creates_the_first_item_of_an_array_field_the_schema_declares(host: Path) -> None:
    assert "assumes" not in _item(host, FR_FILE, "functional_requirements", "fr_id", FR_REQUEST)
    result = _json(host, "insert", "--id", FR_REQUEST, ".assumes", '"asm-member-controls-email"')
    assert result["written"] is True
    assert _item(host, FR_FILE, "functional_requirements", "fr_id", FR_REQUEST)["assumes"] == ["asm-member-controls-email"]
    assert (FR_REQUEST, "assumes", "asm-member-controls-email") in _lock_keys(host)
    assert graph_check(host / "spec")["status"] == "PASS"


def test_insert_into_a_field_the_schema_does_not_have_is_refused_naming_the_field(host: Path) -> None:
    before = _snapshot(host)
    status, out = _run(host, "insert", "--id", FR_REQUEST, ".nope", '"x"')
    assert status == 1 and out.startswith("E767") and "jq" not in out
    assert f"{FR_REQUEST!r} has no nope and its schema does not declare .nope as an array" in out
    assert _snapshot(host) == before


def test_insert_into_a_free_form_object_field_that_is_absent_is_refused_before_jq_makes_an_array(host: Path) -> None:
    """H1-5(a): the schema of ``.security.token_permissions`` is a free-form object; only the declared-array check keeps jq from creating an array there."""
    before = _snapshot(host)
    status, out = _run(host, "insert", "--id", "job-contract-tests", ".security.token_permissions", '"x"')
    assert status == 1 and out.startswith("E767")
    assert "'job-contract-tests' has no security.token_permissions and its schema does not declare .security.token_permissions as an array" in out
    assert _snapshot(host) == before


@pytest.mark.parametrize(
    ("node", "field", "what"),
    [(FR_REQUEST, ".statement", "a string"), ("job-contract-tests", ".environment_ref", "an object")],
    ids=["string", "object"],
)
def test_insert_into_a_present_field_that_is_not_an_array_names_what_it_is(host: Path, node: str, field: str, what: str) -> None:
    """H1-3: decided from the file and the schema before jq runs, so no jq error text is shown or matched."""
    before = _snapshot(host)
    status, out = _run(host, "insert", "--id", node, field, '"x"')
    assert status == 1 and out.startswith("E767"), out
    assert f"{field} of {node!r} is {what}, not an array" in out
    assert f"specdev json patch --id {node} {field}" in out
    assert "jq" not in out and "Cannot insert" not in out
    assert _snapshot(host) == before


def test_classic_jq_path_forms_unchanged(host: Path, tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.json"
    scratch.write_text((host / "spec" / FR_FILE).read_text(encoding="utf-8"), encoding="utf-8")
    added = {**_item(host, FR_FILE, "functional_requirements", "fr_id", FR_REQUEST), "fr_id": "fr-added-by-path"}
    for argv in (
        ("patch", str(scratch), ".functional_requirements[0].statement", '"The system shall be edited by path."', "--spec-root", "ignored", "--git-root", "ignored"),
        ("insert", str(scratch), ".functional_requirements", json.dumps(added)),
        ("delete", str(scratch), ".functional_requirements[1]"),
    ):
        status, out = run_cli("json", *argv)
        assert status == 0, out
    written = json.loads(scratch.read_text(encoding="utf-8"))["functional_requirements"]
    assert [item["fr_id"] for item in written] == [FR, "fr-added-by-path"] and written[0]["statement"] == "The system shall be edited by path."
    classic = run_cli("json", "read", str(host / "spec" / FR_FILE), ".functional_requirements[0].fr_id", *_flags(host))
    assert classic[0] == 0 and classic[1].strip() == FR
    before_lock = Path(lock_path(str(host / "spec"))).read_bytes()
    status, out = run_cli("json", "patch", str(host / "spec" / FR_FILE), ".functional_requirements[1].statement", '"The system shall email a single-use reset link, edited by path."', *_flags(host))
    assert status == 0, out
    assert _item(host, FR_FILE, "functional_requirements", "fr_id", FR_REQUEST)["statement"].endswith("edited by path.")
    assert Path(lock_path(str(host / "spec"))).read_bytes() == before_lock


def test_node_status_active_writes_and_classic_delete_validates_as_patch_does(host: Path) -> None:
    assert run_cli("node", "status", FR, "deprecated", *_flags(host))[0] == 0
    assert run_cli("node", "status", FR, "active", *_flags(host))[0] == 0
    assert "lifecycle" not in _item(host, FR_FILE, "functional_requirements", "fr_id", FR)
    path = str(host / "spec" / FR_FILE)
    before = (host / "spec" / FR_FILE).read_bytes()
    status, out = run_cli("json", "delete", path, ".functional_requirements[1]", *_flags(host))
    assert status == 1 and "Write refused" in out, out
    assert (host / "spec" / FR_FILE).read_bytes() == before
    extra = {"criterion_id": "ac-password-reset-request-3", "scope": "in", "text": "Given a registered member, when a reset is requested twice, then only the latest link works."}
    status, out = run_cli("json", "insert", path, ".functional_requirements[1].acceptance_criteria", json.dumps(extra), *_flags(host))
    assert status == 0, out
    status, out = run_cli("json", "delete", path, ".functional_requirements[1].acceptance_criteria[2]", *_flags(host))
    assert status == 0, out
    assert len(_item(host, FR_FILE, "functional_requirements", "fr_id", FR_REQUEST)["acceptance_criteria"]) == 2


def test_edit_refused_only_for_the_violation_it_adds_not_for_an_unrelated_existing_resolver_error(host: Path) -> None:
    document = _doc(host, "05_interface_contracts.json")
    document["apis"][0]["derives_from"].append("fr-ghost")
    _write_doc(host, "05_interface_contracts.json", document)
    assert _json(host, "patch", "--id", FR_REQUEST, ".statement", '"The system shall email a single-use reset link on request."')["written"]
    before = _snapshot(host)
    status, out = _run(host, "insert", "--id", FR_REQUEST, ".derives_from", '"cap-ghost"')
    assert status == 1 and "cap-ghost" in out and "fr-ghost" not in out
    assert _snapshot(host) == before


def test_write_cost_at_w_scale(host: Path) -> None:
    """PD-8: a write builds the graph three times (base, under the lock, candidate); the cost is printed and gated at 120 s."""
    document = _doc(host, FR_FILE)
    template = document["functional_requirements"][1]
    for number in range(300):
        document["functional_requirements"].append({**template, "fr_id": f"fr-scale-{number}", "acceptance_criteria": []})
    _write_doc(host, FR_FILE, document)
    started = time.perf_counter()
    result = _json(host, "patch", "--id", "fr-scale-150", ".statement", '"The system shall scale."')
    elapsed = time.perf_counter() - started
    print(f"id write on a graph of {len(build_graph(str(host / 'spec'), str(ROOT)).nodes)} nodes: {elapsed:.2f}s")
    assert result["written"] and elapsed < 120


def test_a_write_waits_for_nobody_and_is_refused_while_another_write_holds_the_lock(host: Path) -> None:
    before = _snapshot(host)
    with with_write_lock(str(host / "spec")):
        status, out = _run(host, "delete", "--id", FIXTURE)
        assert status == 1 and out.startswith("E769") and "another specdev write is running" in out
        assert _run(host, "delete", "--id", FIXTURE, "--dry-run")[0] == 0
    assert _snapshot(host) == before


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["patch", "--id", "x", ".a", "1"], True),
        (["insert", "--step", "04", ".a", "{}"], True),
        (["delete", "--id=x"], True),
        (["patch", "file.json", ".a", "1"], False),
        (["read", "file.json", "--id"], False),
        ([], False),
    ],
)
def test_only_patch_insert_and_delete_with_id_or_step_are_id_writes(tokens: list[str], expected: bool) -> None:
    assert is_id_write(tokens) is expected


def test_the_help_of_the_id_forms_is_the_help_of_the_id_parser() -> None:
    code, out = run_cli("json", "patch", "--id", "x", "--help")
    assert code == 0 and "FIELD_PATH" in out and "--id NODE_ID" in out and "--dry-run" in out
    classic_code, classic = run_cli("json", "patch", "--help")
    assert classic_code == 0 and "FIELD_PATH" not in classic


# --- review round 1 (A2-1, B6): a violation a later sibling already had moves down one index on a delete -----------------

def test_delete_is_not_refused_for_a_violation_a_later_sibling_already_had(host: Path) -> None:
    document = _doc(host, "08_fixtures.json")
    document["fixtures"][1]["zzz"] = 1
    _write_doc(host, "08_fixtures.json", document)
    result = _json(host, "delete", "--id", FIXTURE)
    assert result["written"] is True
    left = _doc(host, "08_fixtures.json")["fixtures"]
    assert [item["fixture_id"] for item in left] == ["fix-password-reset-reused-token"] and left[0]["zzz"] == 1


def test_delete_of_a_criterion_is_not_refused_for_a_bad_scope_on_a_later_criterion(host: Path) -> None:
    document = _doc(host, FR_FILE)
    document["functional_requirements"][0]["acceptance_criteria"][1]["scope"] = "bogus"
    _write_doc(host, FR_FILE, document)
    result = _json(host, "delete", "--id", "ac-password-reset-1")
    assert result["written"] is True
    left = _doc(host, FR_FILE)["functional_requirements"][0]["acceptance_criteria"]
    assert [item["criterion_id"] for item in left] == ["ac-password-reset-2", "ac-password-reset-3"]
    assert left[0]["scope"] == "bogus"


def test_delete_that_adds_a_violation_is_still_refused_beside_an_old_one(host: Path) -> None:
    document = _doc(host, FR_FILE)
    document["functional_requirements"][1]["acceptance_criteria"][0]["scope"] = "bogus"
    _write_doc(host, FR_FILE, document)
    before = _snapshot(host)
    status, out = _run(host, "delete", "--id", FR)  # leaves one FR: the list's minItems is a violation the delete adds
    assert status == 1 and out.startswith("E767") and ("fewer items than the schema requires" in out or "non-empty" in out or "too short" in out), out
    assert "acceptance_criteria" not in out and "bogus" not in out  # the old violation's path is not reported
    assert len(out) < 400, out  # the whole array is not quoted
    assert _snapshot(host) == before


def test_insert_into_the_seed_step_is_e706_like_step_ready(host: Path) -> None:
    before = _snapshot(host)
    status, out = _run(host, "insert", "--step", "seed", ".seeds", '{"seed_id": "seed-x"}')
    assert status == 1 and out.startswith("E706") and "no step 'seed'" in out and "seed," not in out, out
    status, out = _run(host, "insert", "--step", "99", ".x", "{}")
    assert status == 1 and out.startswith("E706") and "known steps" in out
    assert _snapshot(host) == before


def test_dry_run_says_to_write_and_to_remove_and_a_write_says_written_and_removed(host: Path) -> None:
    status, dry = _run(host, "delete", "--id", FIXTURE, "--dry-run")
    assert status == 0 and "lock entry to remove: " in dry and "lock entry removed" not in dry, dry
    status, done = _run(host, "delete", "--id", FIXTURE)
    assert status == 0 and "lock entry removed: " in done and "lock entry to remove" not in done, done


def test_a_refusal_names_the_specific_violation_before_the_unevaluated_properties_cascade(host: Path) -> None:
    status, out = _run(host, "insert", "--step", "04", ".functional_requirements", '{"fr_id": "fr-new-one"}')
    lines = out.splitlines()
    assert status == 1 and lines[0].startswith("E767"), out
    assert "required property" in lines[1] and "Unevaluated properties" in lines[-1], out


def test_insert_into_a_map_keyed_collection_is_refused_with_a_message_that_says_so(host: Path) -> None:
    """F3-4: ``.environments`` (the path without ``{}``) reaches the map-keyed refusal instead of "no node collection"."""
    before = (host / "spec" / "02a_delivery_baseline.json").read_text(encoding="utf-8")
    status, out = _run(host, "insert", "--step", "02a", ".environments", '{"scope": "in"}')
    assert status == 1, out
    assert "E767" in out and ".environments is a map keyed by id" in out and "does not add to a map" in out, out
    assert "no node collection" not in out and "specdev json patch --id" not in out
    assert (host / "spec" / "02a_delivery_baseline.json").read_text(encoding="utf-8") == before


def test_the_collections_listed_for_a_step_are_spelt_as_the_command_takes_them(host: Path) -> None:
    status, out = _run(host, "insert", "--step", "02a", ".nope", "{}")
    assert status == 1 and out.startswith("E767"), out
    listed = out.split("its collections:")[1]
    assert ".environments (environment, map: not added by this command)" in listed and ".environments{}" not in listed


def test_step_create_16a_without_impl_context_folder(host: Path, tmp_path: Path) -> None:
    draft = tmp_path / "plan_draft.json"
    shutil.copyfile(host / "spec" / PLAN_FILE, draft)
    shutil.rmtree(host / "spec" / "impl_context")
    code, out = run_cli("attest", "--prune", *_flags(host))
    assert code == 0, out
    code, out = run_cli("step", "create", "16a", "account_recovery", "--from", str(draft), *_flags(host))
    assert code == 0, out
    assert _doc(host, PLAN_FILE) == json.loads(draft.read_text(encoding="utf-8"))


def test_a_write_by_id_keeps_the_indent_of_the_file(host: Path) -> None:
    path = host / "spec" / "10_governance.json"
    before = path.read_text(encoding="utf-8").splitlines()
    status, out = _run(host, "patch", "--id", "rule-spec-check-on-every-pr", ".text", '"Every pull request passes the merge check."')
    assert status == 0, out
    after = path.read_text(encoding="utf-8").splitlines()
    changed = [line for line in difflib.ndiff(before, after) if line[:2] in ("- ", "+ ")]
    assert len(changed) <= 2, changed
