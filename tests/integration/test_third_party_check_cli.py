"""``specdev third-party check`` through the CLI, on a git copy of the worked example with a lock file and a client."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.proof.proof import PROVEN
from specdev_tools.verify.records import evidence_id
from unit.proof._support import edit_doc, prove
from unit.trace._lock_support import git_copy_of_example, run_on_example
from unit.verify._support import commit_all, write, write_json

DECLARATIONS = {
    "$schema": "vc:host-declarations",
    "pin_sources": {
        "tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}],
        "tp-mailrelay": [{"type": "regex", "file": "src/mail/client.ts", "pattern": "MAILRELAY_API_VERSION = \"(api-v[0-9]+)\""}],
    },
}
OTHER_CRITERION = "ac-password-reset-1"
RECORDS = Path("spec") / "extras" / "verification"


def _lock(version: str) -> dict:
    return {"packages": {"node_modules/argon2": {"version": version}}}


@pytest.fixture
def host(tmp_path: Path) -> Path:
    root = git_copy_of_example(tmp_path / "host")
    write_json(root / "spec" / "common" / "host_declarations.json", DECLARATIONS)
    write_json(root / "package-lock.json", _lock("0.41.1"))
    write(root / "src" / "mail" / "client.ts", 'export const MAILRELAY_API_VERSION = "api-v3";\n')
    commit_all(root, "declarations and sources")
    return root


def test_check_without_arguments_passes_when_the_sources_agree(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check")
    assert code == 0 and "every pin matches its declared sources" in out


def test_check_without_arguments_exits_non_zero_on_any_error(host: Path) -> None:
    write_json(host / "package-lock.json", _lock("0.40.0"))
    code, out = run_on_example(host, "third-party", "check")
    assert code == 1 and "E337 the pin '0.41.1' of 'tp-argon2' differs from package-lock.json" in out and "'0.40.0'" in out
    (host / "src" / "mail" / "client.ts").unlink()
    code, out = run_on_example(host, "third-party", "check", "--json")
    assert code == 1 and sorted(entry["code"] for entry in json.loads(out)["errors"]) == ["E337", "E338"]


def test_check_installed_mismatch_exits_1(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.42.0", "tp-mailrelay=api-v3", "--env", "prod")
    assert code == 1 and "E339 'tp-argon2' is installed at '0.42.0' but the spec pin is '0.41.1'" in out
    assert not list((host / RECORDS).glob("evd-*-install.json"))


def test_check_installed_match_writes_the_evidence_file(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.41.1", "tp-mailrelay=api-v3", "--env", "prod", "--tag", "v1.2.0")
    assert code == 0, out
    assert "tp-argon2: installed 0.41.1 is the pin; recorded extras/verification/evd-argon2-prod-install.json" in out
    record = json.loads((host / RECORDS / "evd-argon2-prod-install.json").read_text(encoding="utf-8"))["records"][0]
    assert (record["type"], record["env"], record["tag"], record["installed_versions"]) == ("install-check", "prod", "v1.2.0", {"tp-argon2": "0.41.1"})


def test_installed_without_env_is_a_usage_error_before_anything_is_read(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.41.1")
    assert code == 2 and "--installed needs --env" in out
    code, out = run_on_example(host, "third-party", "check", "--env", "prod")
    assert code == 2 and "--env and --tag go with --installed" in out
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2", "--env", "prod")
    assert code == 2 and "--installed takes TP=VERSION" in out


def test_a_third_party_named_twice_in_installed_is_a_usage_error_and_writes_nothing(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.0.1", "tp-argon2=0.41.1", "--env", "prod")
    assert code == 2 and "--installed names 'tp-argon2' twice" in out
    assert not list((host / RECORDS).glob("evd-*-install.json"))


def _bind_and_run(host: Path) -> None:
    code, out = run_on_example(host, "verify", "bind", "fix-install-argon2", "--id", "ver-install-argon2", "--command", "true", "--guard", ".*")
    assert code == 0, out
    code, out = run_on_example(host, "verify", "run", "ver-install-argon2", "--stage", "dev")
    assert code == 0, out


def _install_check(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.41.1", "--env", "dev")
    assert code == 0, out


@pytest.mark.parametrize("install_check_first", [False, True])
def test_a_run_and_an_install_check_of_one_name_leave_two_files_each_its_own_type(tmp_path: Path, install_check_first: bool) -> None:
    """The binding ``ver-install-argon2`` run at ``dev`` and the install check of ``tp-argon2`` for ``dev``, in either order: two files, and the proof of the binding's node is the same."""
    host = git_copy_of_example(tmp_path / "host")
    write_json(host / "spec" / "common" / "host_declarations.json", {**DECLARATIONS, "pin_sources": {"tp-argon2": DECLARATIONS["pin_sources"]["tp-argon2"]}})
    write_json(host / "package-lock.json", _lock("0.41.1"))
    edit_doc(host, "08_fixtures.json", lambda doc: doc["fixtures"].append({"fixture_id": "fix-install-argon2", "mode": "contract", "verifies": [OTHER_CRITERION]}))
    commit_all(host, "declarations, sources and a fixture")
    if install_check_first:
        _install_check(host)
        commit_all(host, "install check")
        _bind_and_run(host)
    else:
        _bind_and_run(host)
        commit_all(host, "run")
        _install_check(host)
    types = {path.name: json.loads(path.read_text(encoding="utf-8"))["records"][0]["type"] for path in sorted((host / RECORDS).glob("evd-*.json"))}
    assert types == {"evd-argon2-dev-install.json": "install-check", f"{evidence_id('ver-install-argon2', 'dev')}.json": "run"}
    assert (prove(host, OTHER_CRITERION).status, [s.reason for s in prove(host, OTHER_CRITERION).shortfalls]) == (PROVEN, [])
