"""``third-party check``: the pins against their declared sources, and the installed versions against the pins."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.host_declarations import HostDeclarations, PinSource
from specdev_tools.thirdparty.check import check_installed, check_pins, write_install_checks
from unit.graph._synth import ROOT
from unit.verify._support import edit_doc, example_host, graph_of, write, write_json

ARGON, RELAY = "tp-argon2", "tp-mailrelay"
LOCK, CLIENT = "package-lock.json", "src/mail/client.ts"
ARGON_POINTER = "/packages/node_modules~1argon2/version"
RELAY_PATTERN = 'MAILRELAY_API_VERSION = "(api-v[0-9]+)"'
CLIENT_TEXT = 'export const MAILRELAY_API_VERSION = "api-v3";\n'


def _pointer(pointer: str = ARGON_POINTER, file: str = LOCK) -> PinSource:
    return PinSource(type="json-pointer", file=file, pointer=pointer)


def _regex(pattern: str = RELAY_PATTERN, file: str = CLIENT) -> PinSource:
    return PinSource(type="regex", file=file, pattern=pattern)


def _declare(**sources: tuple[PinSource, ...]) -> HostDeclarations:
    """Declarations keyed by the ids the tests use (``tp_argon2`` means ``tp-argon2``)."""
    return HostDeclarations(pin_sources={name.replace("_", "-"): value for name, value in sources.items()})


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return example_host(tmp_path)


@pytest.fixture
def code(tmp_path: Path) -> Path:
    """The files the sources read: a lock file at argon2 0.41.1 and a client that names api-v3."""
    root = tmp_path / "code"
    write_json(root / LOCK, {"packages": {"node_modules/argon2": {"version": "0.41.1"}}})
    write(root / CLIENT, CLIENT_TEXT)
    return root


def _codes(findings: list) -> list[str]:
    return [finding.code for finding in findings]


def test_pointer_and_regex_sources_pass(host: Path, code: Path) -> None:
    declarations = _declare(tp_argon2=(_pointer(),), tp_mailrelay=(_regex(),))
    assert check_pins(graph_of(host), declarations, code) == []


def test_doc_example_tp_argon2_against_a_package_lock(host: Path, code: Path) -> None:
    graph = graph_of(host)
    assert check_pins(graph, _declare(tp_argon2=(_pointer(),)), code) == []
    write_json(code / LOCK, {"packages": {"node_modules/argon2": {"version": "0.42.0"}}})
    assert _codes(check_pins(graph, _declare(tp_argon2=(_pointer(),)), code)) == ["E337"]


def test_mismatch_is_e337_naming_file_and_found_value(host: Path, code: Path) -> None:
    write_json(code / LOCK, {"packages": {"node_modules/argon2": {"version": "0.40.0"}}})
    (finding,) = check_pins(graph_of(host), _declare(tp_argon2=(_pointer(),)), code)
    assert finding.code == "E337" and finding.node_id == ARGON
    for text in (ARGON, "0.41.1", LOCK, ARGON_POINTER, "0.40.0"):
        assert text in finding.message


def test_a_pin_sources_key_that_names_no_third_party_is_e338(host: Path, code: Path) -> None:
    (finding,) = check_pins(graph_of(host), _declare(tp_argon=(_pointer(),)), code)
    assert finding.code == "E338" and "tp-argon'" in finding.message and finding.node_id is None


def test_a_missing_source_file_is_named_without_its_absolute_path(host: Path, code: Path) -> None:
    (code / LOCK).unlink()
    (finding,) = check_pins(graph_of(host), _declare(tp_argon2=(_pointer(),)), code)
    assert LOCK in finding.message and str(code) not in finding.message


def test_unresolved_pointer_is_e338(host: Path, code: Path) -> None:
    (finding,) = check_pins(graph_of(host), _declare(tp_argon2=(_pointer("/packages/nothing/version"),)), code)
    assert finding.code == "E338" and finding.node_id == ARGON and LOCK in finding.message


def test_missing_file_is_e338(host: Path, code: Path) -> None:
    (code / LOCK).unlink()
    assert _codes(check_pins(graph_of(host), _declare(tp_argon2=(_pointer(),)), code)) == ["E338"]


def test_non_compiling_regex_is_e338(host: Path, code: Path) -> None:
    (finding,) = check_pins(graph_of(host), _declare(tp_mailrelay=(_regex("(unclosed"),)), code)
    assert finding.code == "E338" and "does not compile" in finding.message


def test_regex_without_exactly_one_capture_group_is_e338(host: Path, code: Path) -> None:
    for pattern in ("MAILRELAY_API_VERSION", r"(MAILRELAY)_API_(VERSION)"):
        assert _codes(check_pins(graph_of(host), _declare(tp_mailrelay=(_regex(pattern),)), code)) == ["E338"]


def test_two_sources_one_differing_fails(host: Path, code: Path) -> None:
    write(code / "src" / "mail" / "headers.ts", 'headers["X-Api-Version"] = "api-v2"\n')
    other = _regex(r'X-Api-Version"\] = "(api-v[0-9]+)"', "src/mail/headers.ts")
    (finding,) = check_pins(graph_of(host), _declare(tp_mailrelay=(_regex(), other)), code)
    assert finding.code == "E337" and "headers.ts" in finding.message and "api-v2" in finding.message


def test_third_party_without_a_source_is_not_checked(host: Path, code: Path) -> None:
    write_json(code / LOCK, {"packages": {"node_modules/argon2": {"version": "9.9.9"}}})
    assert check_pins(graph_of(host), _declare(tp_mailrelay=(_regex(),)), code) == []
    assert check_pins(graph_of(host), HostDeclarations(), code) == []


def test_range_valued_pin_is_e336_before_the_comparison(host: Path, code: Path) -> None:
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="^0.41"))
    findings = check_pins(graph_of(host), _declare(tp_argon2=(_pointer(),)), code)
    assert _codes(findings) == ["E336"] and findings[0].node_id == ARGON


def test_check_pins_raises_e336_on_a_hand_edited_latest_pin(host: Path, code: Path) -> None:
    edit_doc(host, "02_system_sketch.json", lambda doc: doc["third_parties"][0].update(pin="latest"))
    assert _codes(check_pins(graph_of(host), _declare(tp_argon2=(_pointer(),)), code)) == ["E336"]


def test_deploy_mode_mismatch_is_e339(host: Path) -> None:
    resolved, findings = check_installed(graph_of(host), {ARGON: "0.42.0", RELAY: "api-v3"})
    assert resolved == {ARGON: "0.42.0", RELAY: "api-v3"}
    (finding,) = findings
    assert finding.code == "E339" and finding.node_id == ARGON and "0.42.0" in finding.message and "0.41.1" in finding.message


@pytest.mark.parametrize("name", ["tp-nope", "api-password-reset-confirm"])
def test_deploy_mode_refuses_a_name_that_is_not_a_third_party(host: Path, name: str) -> None:
    with pytest.raises(FindingError) as caught:
        check_installed(graph_of(host), {name: "1.0"})
    assert caught.value.error.code == "E706"


def _record(host: Path, name: str) -> dict:
    return json.loads((host / "spec" / "extras" / "verification" / name).read_text(encoding="utf-8"))["records"][0]


def test_deploy_mode_match_writes_an_install_check_record(host: Path) -> None:
    files = write_install_checks(str(host / "spec"), str(ROOT), str(host), {ARGON: "0.41.1"}, "prod", None)
    assert files == ["evd-install-argon2-prod.json"]
    record = _record(host, files[0])
    assert (record["type"], record["about"], record["env"]) == ("install-check", [ARGON], "prod")


def test_install_check_record_has_exactly_its_field_set(host: Path) -> None:
    write_install_checks(str(host / "spec"), str(ROOT), str(host), {ARGON: "0.41.1"}, "prod", None)
    assert set(_record(host, "evd-install-argon2-prod.json")) == {"evidence_id", "about", "type", "tested_tree", "installed_versions", "env"}
    write_install_checks(str(host / "spec"), str(ROOT), str(host), {RELAY: "api-v3"}, "Staging 2", "v1.2.0")
    record = _record(host, "evd-install-mailrelay-staging-2.json")
    assert set(record) == {"evidence_id", "about", "type", "tested_tree", "installed_versions", "env", "tag"}
    assert record["installed_versions"] == {RELAY: "api-v3"} and record["tag"] == "v1.2.0"


def test_an_environment_with_no_letter_is_refused_and_writes_nothing(host: Path) -> None:
    with pytest.raises(FindingError) as caught:
        write_install_checks(str(host / "spec"), str(ROOT), str(host), {ARGON: "0.41.1"}, "!!", None)
    assert caught.value.error.code == "E767"
    assert not list((host / "spec" / "extras" / "verification").glob("evd-install-*"))
