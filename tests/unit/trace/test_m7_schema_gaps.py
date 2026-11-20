"""WI-M7-03: the fields M7 needs on the record and lock schemas of M5 (``proves``, ``recorded_hashes``, ``git_author``,
the ``install-check`` type, ``target_containers``), the readers and the writers of the lock that carry the last one."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.graph.build import build_graph
from specdev_tools.trace.attest import apply_attest, plan_node_attest
from specdev_tools.trace.id_writes import _lock_after
from specdev_tools.trace.history import containers_of
from specdev_tools.trace.lockfile import Lock, LockEntry, parse_lock, serialise_lock
from specdev_tools.trace.merge_driver import merge_files, merge_locks
from specdev_tools.trace.records import check_records
from specdev_tools.validation.spec_check import run_spec_check_json

from ..graph._synth import ROOT, copy_example, write_json
from ._lock_support import EXAMPLE_HOST, lock_for

HASH = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
FIXTURE = "fix-password-reset-expired-token"
CRITERION = "ac-password-reset-3"
VERIFICATION = {
    "verification_id": "ver-password-reset-expired-token",
    "verifies": [FIXTURE],
    "stage": "dev",
    "commands": ["pytest -k expired"],
    "output_guard": "expired token .*passed",
}
RUN = {
    "evidence_id": "evd-password-reset-expired-token-dev",
    "about": ["ver-password-reset-expired-token"],
    "exit_code": 0,
    "guard_matched": True,
    "output_hash": HASH,
    "tested_tree": "9a41c7e2",
    "stage": "dev",
}
ATTESTATION = {
    "evidence_id": "evd-attest-reset-link-copy",
    "type": "attestation",
    "about": [FIXTURE],
    "tested_tree": "9a41c7e2",
    "stage": "staging",
    "git_author": {"name": "A Person", "email": "person@example.org"},
}
INSTALL_CHECK = {
    "evidence_id": "evd-install-argon2-prod",
    "type": "install-check",
    "about": ["tp-argon2"],
    "stage": "prod",
    "tested_tree": "9a41c7e2",
    "installed_versions": {"tp-argon2": "0.41.1"},
    "env": "prod",
    "tag": "v1.4.0",
}


def _file(uri: str, record: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": uri, "records": [record]}


def _verification(record: dict[str, Any]) -> list[Any]:
    return validate_data_against_schema(str(ROOT), _file("vc:extras:verification-record", record))


def _evidence(record: dict[str, Any]) -> list[Any]:
    return validate_data_against_schema(str(ROOT), _file("vc:extras:evidence-record", record))


def _without(record: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {name: value for name, value in record.items() if name not in keys}


def test_verification_record_accepts_proves_and_an_empty_proves() -> None:
    assert _verification({**VERIFICATION, "proves": [CRITERION, "ac-password-reset-1"]}) == []
    assert _verification({**VERIFICATION, "proves": []}) == []
    assert _verification({**VERIFICATION, "proves": [CRITERION, CRITERION]}) != []


def test_verification_record_without_proves_still_validates() -> None:
    assert _verification(VERIFICATION) == []
    assert "proves" not in json.loads(
        (EXAMPLE_HOST / "spec" / "extras" / "verification" / "ver-password-reset-expired-token.json").read_text(encoding="utf-8")
    )["records"][0]


def test_evidence_record_accepts_recorded_hashes() -> None:
    hashes = {"ver-password-reset-expired-token": HASH, CRITERION: HASH_B}
    assert _evidence({**RUN, "recorded_hashes": hashes}) == []
    assert _evidence({**ATTESTATION, "recorded_hashes": {FIXTURE: HASH}}) == []
    assert _evidence({**RUN, "recorded_hashes": {CRITERION: "sha256:short"}}) != []
    assert _evidence({**RUN, "recorded_hashes": {}}) != []
    assert _evidence({**INSTALL_CHECK, "recorded_hashes": {"tp-argon2": HASH}}) != []


def test_install_check_record_validates_with_exactly_its_field_set() -> None:
    assert _evidence(INSTALL_CHECK) == []
    assert _evidence(_without(INSTALL_CHECK, "tag")) == []
    for missing in ("installed_versions", "env", "tested_tree", "about"):
        assert _evidence(_without(INSTALL_CHECK, missing)) != [], missing
    for extra in ({"guard_matched": True}, {"output_hash": HASH}, {"git_author": ATTESTATION["git_author"]}):
        assert _evidence({**INSTALL_CHECK, **extra}) != [], extra


def test_run_record_without_exit_code_still_fails() -> None:
    violations = _evidence(_without(RUN, "exit_code"))
    assert violations and any("exit_code" in message for _path, message in violations)
    assert _evidence(RUN) == []
    assert _evidence({**RUN, "git_author": ATTESTATION["git_author"]}) != []
    assert _evidence({**RUN, "env": "prod"}) != []


def test_install_check_with_exit_code_fails() -> None:
    violations = _evidence({**INSTALL_CHECK, "exit_code": 0})
    assert violations and any("False schema" in message for _path, message in violations)


def test_attestation_requires_git_author() -> None:
    assert _evidence(ATTESTATION) == []
    violations = _evidence(_without(ATTESTATION, "git_author"))
    assert violations and any("git_author" in message for _path, message in violations)
    assert _evidence({**ATTESTATION, "git_author": {"name": "A Person"}}) != []
    assert _evidence({**ATTESTATION, "exit_code": 0}) != []


def _codes(spec: Path) -> list[tuple[str, str, str | None]]:
    checks = run_spec_check_json(str(ROOT), str(spec))[1]["checks"]
    return [
        (name, item["code"], item.get("node_id"))
        for name, check in checks.items()
        if name in {"graph", "records"}
        for item in check.get("findings", [])
    ]


def test_check_records_accepts_an_install_check_about_a_third_party(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    write_json(spec, "extras/verification/evd-install-argon2-prod.json", _file("vc:extras:evidence-record", INSTALL_CHECK))
    graph = build_graph(str(spec), str(ROOT))
    assert check_records(str(spec), str(ROOT), graph) == []
    assert _codes(spec) == []
    dangling = {**INSTALL_CHECK, "about": ["tp-no-such-party"]}
    write_json(spec, "extras/verification/evd-install-argon2-prod.json", _file("vc:extras:evidence-record", dangling))
    assert _codes(spec) == [("graph", "E700", "evd-install-argon2-prod")]


def test_lock_entry_target_containers_round_trips_and_is_optional() -> None:
    plain = LockEntry("fr-a", "api_refs", "api-x", HASH, HASH_B)
    nested = LockEntry("fr-a", "refines", "ac-1", HASH, HASH_B, target_containers=("fr-a", "scope-a"))
    text = serialise_lock(Lock((plain, nested)))
    assert '"target_containers"' not in text.splitlines()[1]
    assert '"target_containers":["fr-a","scope-a"]' in text
    again = parse_lock(text, "trace.lock.json")
    assert again.entries == (plain, nested)
    assert serialise_lock(again) == text
    assert plain.target_containers == ()
    for bad in ("[]", '["x","x"]', '"fr-a"', '[""]', "[1]"):
        broken = text.replace('["fr-a","scope-a"]', bad)
        try:
            parse_lock(broken, "trace.lock.json")
        except Exception as error:  # noqa: BLE001 - the type is checked below
            assert type(error).__name__ == "LockError" and "target_containers" in str(error.error.message)
        else:
            raise AssertionError(f"{bad} was accepted")


def test_lock_writer_records_target_containers_for_ac_password_reset_3(tmp_path: Path) -> None:
    graph = build_graph(str(copy_example(tmp_path / "spec")), str(ROOT))
    node = graph.by_id[CRITERION]
    assert containers_of(graph, node) == ("fr-password-reset",)
    lock = lock_for(graph, EXAMPLE_HOST)
    entries = [entry for entry in lock.entries if entry.target == CRITERION]
    assert entries and all(entry.target_containers == ("fr-password-reset",) for entry in entries)
    top = [entry for entry in lock.entries if graph.by_id[entry.target].parent is None]
    assert top and all(entry.target_containers == () for entry in top)


def _without_the_link(tmp_path: Path) -> Path:
    """The worked example with the link of ``fix-password-reset-expired-token`` to ``ac-password-reset-3`` removed."""
    spec = copy_example(tmp_path / "spec")
    document = json.loads((spec / "08_fixtures.json").read_text(encoding="utf-8"))
    fixture = next(item for item in _walk(document) if item.get("fixture_id") == FIXTURE)
    fixture["verifies"].remove(CRITERION)
    write_json(spec, "08_fixtures.json", document)
    return spec


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_the_writers_of_an_edit_and_of_attest_stamp_the_same_field(tmp_path: Path) -> None:
    graph = build_graph(str(copy_example(tmp_path / "now")), str(ROOT))
    before = build_graph(str(_without_the_link(tmp_path / "before")), str(ROOT))
    written = _lock_after(before, graph, Lock(), {})[1]
    assert [(entry.source, entry.target, entry.target_containers) for entry in written] == [
        (FIXTURE, CRITERION, ("fr-password-reset",))
    ]
    plan = plan_node_attest(graph, Lock(), {}, FIXTURE, target=CRITERION)
    assert [(link.new.target, link.new.target_containers) for link in plan.links] == [(CRITERION, ("fr-password-reset",))]
    assert apply_attest(Lock(), plan).entries == tuple(link.new for link in plan.links)


def test_merge_driver_keeps_target_containers(tmp_path: Path) -> None:
    base = LockEntry("fr-a", "refines", "ac-1", HASH, HASH_B)
    stamped = LockEntry("fr-a", "refines", "ac-1", HASH, HASH_B, target_containers=("fr-a",))
    other = LockEntry("fr-b", "refines", "ac-2", HASH, HASH_B)
    # the field on one side only: the entry merges entry by entry as before and the field survives
    merged = merge_locks(Lock((base, other)), Lock((stamped, other)), Lock((base, other)))
    assert merged.entries == (stamped, other)
    merged = merge_locks(Lock((base,)), Lock((base,)), Lock((stamped,)))
    assert merged.entries == (stamped,)
    # the field on both sides, differing: both changed the same entry, so the base entry is kept (as for any field)
    ours = LockEntry("fr-a", "refines", "ac-1", HASH, HASH_B, target_containers=("fr-a", "scope-a"))
    assert merge_locks(Lock((base,)), Lock((stamped,)), Lock((ours,))).entries == (base,)
    # no base: the same pick on either side of the merge
    left = merge_locks(Lock(), Lock((stamped,)), Lock((ours,))).entries
    right = merge_locks(Lock(), Lock((ours,)), Lock((stamped,))).entries
    assert left == right
    # through the files, as git calls the driver
    paths = {}
    for name, lock in (("base", Lock((base,))), ("ours", Lock((stamped,))), ("theirs", Lock((base, other)))):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(serialise_lock(lock), encoding="utf-8")
    merge_files(str(paths["base"]), str(paths["ours"]), str(paths["theirs"]), "spec/extras/trace.lock.json")
    result = parse_lock(paths["ours"].read_text(encoding="utf-8"), "ours")
    assert result.entries == (stamped, other)


def test_example_lock_fixture_equals_regenerated_output() -> None:
    graph = build_graph(str(EXAMPLE_HOST / "spec"), str(ROOT))
    committed = (EXAMPLE_HOST / "spec" / "extras" / "trace.lock.json").read_text(encoding="utf-8")
    assert committed == serialise_lock(lock_for(graph, EXAMPLE_HOST))
    assert '"target_containers":["fr-password-reset"]' in committed
