"""The ask-rule piece of the host installer (WI-M9-11d): the rules, their merge into ``.claude/settings.local.json``,
the git exclude line and the refusals.

Fixture hosts ``w`` and ``p`` hold invented settings files (``claude_settings.local.json``, copied into the scratch
host's ``.claude/`` by the test: a file named ``settings.local.json`` is ignored by many global git configs, so the
fixture would not be committed under that name).  Every host is a temporary git repository.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from specdev_tools import host_install as hi

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "hosts"
SETTINGS = ".claude/settings.local.json"


@pytest.fixture(autouse=True)
def no_global_git_ignores(tmp_path, monkeypatch):
    """A person's global ignore file may already cover ``settings.local.json``: the tests see only the host's own rules."""
    home = tmp_path / "home"
    home.mkdir()
    for name, value in (("HOME", home), ("XDG_CONFIG_HOME", home / "xdg"), ("GIT_CONFIG_GLOBAL", os.devnull), ("GIT_CONFIG_SYSTEM", os.devnull)):
        monkeypatch.setenv(name, str(value))


@pytest.fixture
def host(tmp_path: Path) -> Path:
    root = tmp_path / "host"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "spec").mkdir()
    return root


def make_ctx(host: Path, *, dry_run: bool = False) -> hi.InstallContext:
    return hi.InstallContext(
        spec_dir=host / "spec",
        spec_rel="spec",
        git_root=host,
        toolkit_root=host / "devspec_toolkit",
        templates_dir=REPO / "templates",
        toolkit_version="1.2.3",
        venv_prefix=host / "devspec_env",
        venv_name="devspec_env",
        dry_run=dry_run,
        adopt=False,
        force_claude=False,
    )


def use_fixture(host: Path, name: str) -> dict:
    target = host / SETTINGS
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / name / "claude_settings.local.json", target)
    return json.loads(target.read_text(encoding="utf-8"))


def settings(host: Path) -> dict:
    return json.loads((host / SETTINGS).read_text(encoding="utf-8"))


def asks(rule_text: str, command: str) -> bool:
    """Claude Code's Bash rule match for the two shapes the list uses: exact text, or a prefix before a trailing ``*``."""
    body = rule_text.removeprefix("Bash(").removesuffix(")")
    return command.startswith(body.removesuffix("*")) if body.endswith("*") else command == body


def tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(root).parts}


class TestTheList:
    def test_ask_rules_for_lists_both_forms_without_rollback(self):
        rules = hi.ask_rules_for("1.2.3")
        assert len(rules) == 10 == len(set(rules))
        for form in ("specdev", "./tools/run_specdev.sh"):
            for command in (
                f"{form} milestone sign-off ms-1",
                f"{form} milestone defer ms-1 --reason x",
                f"{form} release",
                f"{form} release --tag v1.0.0 --message m",
                f"{form} verify attest ev-1 --by someone",
            ):
                assert any(asks(rule, command) for rule in rules), command
            for command in (
                f"{form} release check --stage prod --tag v1.0.0",
                f"{form} release prep",
                f"{form} release rollback v1.0.0 --reason x",
                f"{form} milestone start ms-1",
                f"{form} verify run",
                f"{form} status",
            ):
                assert not any(asks(rule, command) for rule in rules), command
        # the forms that are not listed
        assert not any(asks(rule, "python -m specdev_tools.cli release") for rule in rules)
        assert not any(asks(rule, "devspec_env/bin/specdev release") for rule in rules)

    def test_the_list_is_the_same_on_every_call(self):
        assert hi.ask_rules_for("1.2.3") == hi.ask_rules_for("1.2.4")

    def test_every_command_pattern_names_a_command_of_the_real_cli(self):
        paths = {entry["path"] for entry in json.loads((REPO / "tools" / "cli_commands.json").read_text(encoding="utf-8"))["commands"]}
        for pattern in hi.ASK_COMMAND_PATTERNS:
            words = [w for w in pattern.split() if not w.startswith("*") and not w.startswith("-")]
            assert " ".join(words) in paths, pattern


class TestMerge:
    @pytest.mark.parametrize("fixture", ["w", "p"])
    def test_ask_rules_merged_preserving_existing_allow_and_unknown_keys(self, host, fixture):
        before = use_fixture(host, fixture)
        result = hi.install_ask_rules(make_ctx(host))
        assert result.status == hi.REFRESHED and result.findings == ()
        after = settings(host)
        assert after["permissions"]["allow"] == before["permissions"]["allow"]
        assert after["permissions"].get("deny") == before["permissions"].get("deny")
        assert {k: v for k, v in after.items() if k != "permissions"} == {k: v for k, v in before.items() if k != "permissions"}
        assert list(after) == list(before)
        assert after["permissions"]["ask"] == before["permissions"].get("ask", []) + hi.ask_rules_for("1.2.3")

    def test_a_second_run_adds_nothing_and_changes_no_byte(self, host):
        use_fixture(host, "w")
        hi.install_ask_rules(make_ctx(host))
        first = tree(host)
        again = hi.install_ask_rules(make_ctx(host))
        assert again.status == hi.CURRENT
        assert tree(host) == first
        assert all(settings(host)["permissions"]["ask"].count(rule) == 1 for rule in hi.ask_rules_for("1.2.3"))

    def test_an_absent_file_is_created_with_two_space_indentation_and_a_final_newline(self, host):
        result = hi.install_ask_rules(make_ctx(host))
        assert result.status == hi.CREATED
        text = (host / SETTINGS).read_text(encoding="utf-8")
        assert text == json.dumps({"permissions": {"ask": hi.ask_rules_for("1.2.3")}}, indent=2) + "\n"

    def test_the_installer_never_adds_an_allow_removes_a_deny_or_touches_settings_json(self, host):
        use_fixture(host, "w")
        shared = host / ".claude" / "settings.json"
        shared.write_text('{"permissions": {"deny": ["Bash(rm:*)"]}}', encoding="utf-8")
        shared_before = shared.read_bytes()
        hi.install_ask_rules(make_ctx(host))
        assert shared.read_bytes() == shared_before
        permissions = settings(host)["permissions"]
        assert permissions["allow"] == ["Bash(git status:*)", "Bash(pytest tests/unit:*)", "Read(//tmp/**)"]
        assert permissions["deny"] == ["Read(./secrets/**)"]
        assert not any(rule in permissions["allow"] for rule in hi.ask_rules_for("1.2.3"))

    def test_a_rule_an_earlier_toolkit_installed_and_this_one_no_longer_lists_is_left_alone(self, host):
        (host / ".claude").mkdir()
        old = "Bash(specdev release rollback *)"
        (host / SETTINGS).write_text(json.dumps({"permissions": {"ask": [old, hi.ask_rules_for("1.2.3")[0]]}}), encoding="utf-8")
        hi.install_ask_rules(make_ctx(host))
        ask = settings(host)["permissions"]["ask"]
        assert ask[0] == old
        assert ask.count(hi.ask_rules_for("1.2.3")[0]) == 1
        assert set(hi.ask_rules_for("1.2.3")) <= set(ask)

    def test_a_file_with_every_rule_is_not_rewritten_even_when_formatted_differently(self, host):
        (host / ".claude").mkdir()
        text = json.dumps({"permissions": {"ask": hi.ask_rules_for("1.2.3")}}, indent=4)  # 4 spaces, no final newline
        (host / SETTINGS).write_text(text, encoding="utf-8")
        hi.install_ask_rules(make_ctx(host))
        assert (host / SETTINGS).read_text(encoding="utf-8") == text

    def test_dry_run_writes_nothing_and_says_what_it_would_do(self, host):
        use_fixture(host, "p")
        before = tree(host)
        exclude = (host / ".git" / "info" / "exclude").read_bytes()
        result = hi.install_ask_rules(make_ctx(host, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert tree(host) == before
        assert (host / ".git" / "info" / "exclude").read_bytes() == exclude


class TestRefusals:
    @pytest.mark.parametrize(
        "text",
        [
            '{"permissions": {"allow": ["Bash(ls:*)"],',  # not JSON
            "",  # empty
            '["not", "an", "object"]',
            '{"permissions": ["not an object"]}',
            '{"permissions": {"ask": "not a list"}}',
        ],
    )
    def test_ask_rules_invalid_json_not_overwritten(self, host, text):
        (host / ".claude").mkdir()
        (host / SETTINGS).write_text(text, encoding="utf-8")
        exclude_before = (host / ".git" / "info" / "exclude").read_bytes()
        result = hi.install_ask_rules(make_ctx(host))
        assert result.status == hi.REFUSED
        assert [f.code for f in result.findings] == ["W931"]
        assert (host / SETTINGS).read_text(encoding="utf-8") == text
        assert (host / ".git" / "info" / "exclude").read_bytes() == exclude_before
        # the refusal carries the fragment to merge by hand
        fragment = json.dumps({"permissions": {"ask": hi.ask_rules_for("1.2.3")}})
        assert fragment in result.findings[0].text
        assert SETTINGS in result.detail

    def test_ask_rules_permission_error_prints_bang_command(self, host):
        real_write = Path.write_text

        def refusing(self, *args, **kwargs):
            if self.name == "settings.local.json":
                raise PermissionError(13, "Operation not permitted")
            return real_write(self, *args, **kwargs)

        with mock.patch.object(Path, "write_text", refusing):
            result = hi.install_ask_rules(make_ctx(host))
        assert result.status == hi.REFUSED
        text = result.findings[0].text
        assert "! ./tools/run_specdev.sh update spec --repo-root devspec_toolkit --install-only" in text
        assert json.dumps({"permissions": {"ask": hi.ask_rules_for("1.2.3")}}) in text
        assert not (host / SETTINGS).exists()


class TestGitExclude:
    def exclude(self, host: Path) -> list[str]:
        return (host / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()

    def test_git_exclude_entry_added_only_when_not_ignored(self, host):
        # nothing ignores the file: the clone's exclude file gets the line, once, and the file is not untracked
        hi.install_ask_rules(make_ctx(host))
        assert self.exclude(host).count(SETTINGS) == 1
        status = subprocess.run(["git", "-C", str(host), "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
        assert "settings.local.json" not in status
        hi.install_ask_rules(make_ctx(host))
        assert self.exclude(host).count(SETTINGS) == 1

    def test_no_exclude_line_when_a_gitignore_already_covers_the_file(self, host, tmp_path):
        (host / ".gitignore").write_text(".claude/\n", encoding="utf-8")
        before = (host / ".git" / "info" / "exclude").read_bytes()
        result = hi.install_ask_rules(make_ctx(host))
        assert result.status == hi.CREATED
        assert (host / ".git" / "info" / "exclude").read_bytes() == before

    def test_the_exclude_line_is_written_before_the_settings_file(self, host):
        order: list[str] = []
        real_append, real_write = hi._append_line, Path.write_text

        def append(path, line):
            order.append("exclude")
            return real_append(path, line)

        def write(self, *args, **kwargs):
            if self.name == "settings.local.json":
                order.append("settings")
            return real_write(self, *args, **kwargs)

        with mock.patch.object(hi, "_append_line", append), mock.patch.object(Path, "write_text", write):
            hi.install_ask_rules(make_ctx(host))
        assert order == ["exclude", "settings"]

    def test_the_exclude_file_keeps_its_lines_and_gets_a_newline_before_the_entry(self, host):
        path = host / ".git" / "info" / "exclude"
        path.write_text("# my own\n*.swp", encoding="utf-8")
        hi.install_ask_rules(make_ctx(host))
        assert path.read_text(encoding="utf-8") == f"# my own\n*.swp\n{SETTINGS}\n"
