"""Record helpers: the git author, the UTC time and the minted ids."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.lifecycle import records
from unit.graph._synth import git


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


@pytest.fixture
def no_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Git has no configured identity and may not guess one from the user database."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)


def test_git_author_reads_the_configured_identity(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.invalid")
    author = records.git_author(str(repo))
    assert (author.name, author.email) == ("Ada Lovelace", "ada@example.invalid")
    assert author.as_record() == {"name": "Ada Lovelace", "email": "ada@example.invalid"}


def test_git_author_missing_identity(repo: Path, no_identity: None) -> None:
    with pytest.raises(FindingError) as caught:
        records.git_author(str(repo))
    assert caught.value.error.code == "E767"
    assert "user.name" in caught.value.error.message and "user.email" in caught.value.error.message


def test_git_author_ci_fallback_when_no_identity(repo: Path, no_identity: None) -> None:
    assert records.git_author(str(repo), ci_fallback=True).as_record() == {"name": "ci", "email": ""}


def test_now_utc_is_utc_with_z() -> None:
    before = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = records.now_utc()
    after = datetime.now(timezone.utc)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp)
    assert before <= datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= after


def test_mint_id_pads_and_skips_taken_ids() -> None:
    assert records.mint_id("rec", []) == "rec-0001"
    assert records.mint_id("rec", ["rec-0001", "rec-0003", "dep-0009"]) == "rec-0004"
    assert records.mint_id("so-ms-a", ["so-ms-a-0002", "so-ms-ab-0007"]) == "so-ms-a-0003"
    assert records.mint_id("dep", ["dep-9999"]) == "dep-10000"


def test_mint_action_id() -> None:
    assert records.mint_action_id([]) == "a01"
    assert records.mint_action_id(["a01", "a03"]) == "a04"
    assert records.mint_action_id(["a99"]) == "a100"
    assert records.mint_action_id(["a100", "b02", "a1"]) == "a101"
