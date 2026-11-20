"""``specdev third-party check`` through the CLI, on a git copy of the worked example with a lock file and a client."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit.trace._lock_support import git_copy_of_example, run_on_example
from unit.verify._support import commit_all, write, write_json

DECLARATIONS = {
    "$schema": "vc:host-declarations",
    "pin_sources": {
        "tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}],
        "tp-mailrelay": [{"type": "regex", "file": "src/mail/client.ts", "pattern": "MAILRELAY_API_VERSION = \"(api-v[0-9]+)\""}],
    },
}
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
    assert not list((host / RECORDS).glob("evd-install-*"))


def test_check_installed_match_writes_the_evidence_file(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.41.1", "tp-mailrelay=api-v3", "--env", "prod", "--tag", "v1.2.0")
    assert code == 0, out
    assert "tp-argon2: installed 0.41.1 is the pin; recorded extras/verification/evd-install-argon2-prod.json" in out
    record = json.loads((host / RECORDS / "evd-install-argon2-prod.json").read_text(encoding="utf-8"))["records"][0]
    assert (record["type"], record["env"], record["tag"], record["installed_versions"]) == ("install-check", "prod", "v1.2.0", {"tp-argon2": "0.41.1"})


def test_installed_without_env_is_a_usage_error_before_anything_is_read(host: Path) -> None:
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2=0.41.1")
    assert code == 2 and "--installed needs --env" in out
    code, out = run_on_example(host, "third-party", "check", "--env", "prod")
    assert code == 2 and "--env and --tag go with --installed" in out
    code, out = run_on_example(host, "third-party", "check", "--installed", "tp-argon2", "--env", "prod")
    assert code == 2 and "--installed takes TP=VERSION" in out
