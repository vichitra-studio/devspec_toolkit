"""``third-party pin``: what an exact pin is, and the write of one into a third-party node."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.thirdparty.pin import pin_is_exact, pin_third_party
from specdev_tools.trace.hashing import content_hash
from specdev_tools.trace.writing import seed_texts_for_write
from unit.graph._synth import ROOT
from unit.verify._support import example_host, graph_of

ARGON = "tp-argon2"
SHA = "3f2a9c1d8e4b7a6f0c5d2e1b9a8f7c6d5e4b3a21"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return example_host(tmp_path)


def _refusal(host: Path, version: str, node: str = ARGON) -> FindingError:
    with pytest.raises(FindingError) as caught:
        pin_third_party(graph_of(host), str(host / "spec"), str(ROOT), str(host), node, version, dry_run=True)
    return caught.value


def _hash_of(host: Path, node: str) -> str:
    graph = graph_of(host)
    return content_hash(node, graph, seed_texts_for_write(graph, str(host)))


def test_latest_is_e336(host: Path) -> None:
    assert _refusal(host, "latest").error.code == "E336"
    assert not pin_is_exact("Latest")


def test_empty_pin_is_e336(host: Path) -> None:
    assert _refusal(host, "").error.code == "E336"
    assert _refusal(host, "   ").error.code == "E336"


def test_star_is_e336(host: Path) -> None:
    assert _refusal(host, "*").error.code == "E336"


def test_caret_range_is_e336(host: Path) -> None:
    assert _refusal(host, "^6.24").error.code == "E336"


@pytest.mark.parametrize("value", ["any", "1.x", "1.2.X", "1.*", "~1.2", ">1.0", "<2", ">=1.0", "<=2.0", "=1.2.3", "1.0 || 2.0", "1.0 - 2.0", "1.0,2.0"])
def test_other_floating_or_range_values_are_not_exact(value: str) -> None:
    assert not pin_is_exact(value)


def test_exact_semver_commit_sha_and_api_version_are_accepted() -> None:
    assert all(pin_is_exact(value) for value in ("0.41.1", SHA, "api-v3"))


@pytest.mark.parametrize("value", ["2024-06-01", "v3", "r12", "2.0.0-rc.1", "x86-build", "1.0.0+build.5"])
def test_non_semver_values_of_the_hosts_are_accepted(value: str) -> None:
    """No grammar: a date, a bare tag, a pre-release and a name that merely contains an x all pass."""
    assert pin_is_exact(value)


def test_pin_edit_changes_the_node_content_hash(host: Path) -> None:
    before = _hash_of(host, ARGON)
    result = pin_third_party(graph_of(host), str(host / "spec"), str(ROOT), str(host), ARGON, "0.42.0")
    assert result is not None and result.written and result.lock_written == ()
    assert _hash_of(host, ARGON) != before
    document = json.loads((host / "spec" / "02_system_sketch.json").read_text(encoding="utf-8"))
    assert [item["pin"] for item in document["third_parties"] if item["third_party_id"] == ARGON] == ["0.42.0"]


def test_the_pin_the_node_already_has_is_not_written(host: Path) -> None:
    before = (host / "spec" / "02_system_sketch.json").read_text(encoding="utf-8")
    assert pin_third_party(graph_of(host), str(host / "spec"), str(ROOT), str(host), ARGON, " 0.41.1 ") is None
    assert (host / "spec" / "02_system_sketch.json").read_text(encoding="utf-8") == before


def test_a_refused_pin_writes_nothing(host: Path) -> None:
    before = (host / "spec" / "02_system_sketch.json").read_text(encoding="utf-8")
    with pytest.raises(FindingError):
        pin_third_party(graph_of(host), str(host / "spec"), str(ROOT), str(host), ARGON, "latest")
    assert (host / "spec" / "02_system_sketch.json").read_text(encoding="utf-8") == before


def test_a_node_that_is_not_a_third_party_and_an_unknown_id_are_e706(host: Path) -> None:
    assert _refusal(host, "1.0", "api-password-reset-confirm").error.code == "E706"
    assert _refusal(host, "1.0", "tp-nope").error.code == "E706"
