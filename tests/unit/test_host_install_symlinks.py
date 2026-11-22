"""The Claude links piece of the host installer (WI-M9-11d): the skill and agent symlinks moved out of ``init_project``.

The toolkit here is a small invented folder with a ``.claude`` tree; the hosts are temporary git repositories.
``--force-claude`` is tested as acting, through the command line ``init`` builds for its delegate.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from specdev_tools import cli
from specdev_tools import host_install as hi
from unit._host_install_support import host, make_ctx as shared_make_ctx  # noqa: F401  (the fixture ``host``)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import init_project  # noqa: E402


def build_toolkit(folder: Path, skills=("specdev-context", "specdev-step"), agents=("specdev-impl.md", "pr-audit-fix-apply.md")) -> Path:
    for name in skills:
        (folder / ".claude" / "skills" / name).mkdir(parents=True, exist_ok=True)
        (folder / ".claude" / "skills" / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    for name in agents:
        (folder / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        (folder / ".claude" / "agents" / name).write_text(f"# {name}\n", encoding="utf-8")
    return folder


def make_ctx(host: Path, toolkit: Path, *, force: bool = False, dry_run: bool = False) -> hi.InstallContext:
    return shared_make_ctx(host, toolkit_root=toolkit, templates_dir=toolkit / "templates", force_claude=force, dry_run=dry_run)


def links(host: Path) -> dict[str, str]:
    return {
        str(p.relative_to(host)): os.readlink(p)
        for kind in ("skills", "agents")
        for p in sorted((host / ".claude" / kind).glob("*"))
        if p.is_symlink()
    }


def tree(root: Path) -> dict[str, str | bytes]:
    return {
        str(p.relative_to(root)): (f"-> {os.readlink(p)}" if p.is_symlink() else p.read_bytes() if p.is_file() else "dir")
        for p in sorted(root.rglob("*"))
        if ".git" not in p.relative_to(root).parts
    }


@pytest.fixture
def toolkit(host: Path) -> Path:
    return build_toolkit(host / "devspec_toolkit")


class TestLinks:
    def test_links_are_relative_and_reach_the_toolkit(self, host, toolkit):
        result = hi.install_claude_links(make_ctx(host, toolkit))
        assert result.status == hi.CREATED and result.findings == ()
        assert links(host) == {
            ".claude/skills/specdev-context": "../../devspec_toolkit/.claude/skills/specdev-context",
            ".claude/skills/specdev-step": "../../devspec_toolkit/.claude/skills/specdev-step",
            ".claude/agents/pr-audit-fix-apply.md": "../../devspec_toolkit/.claude/agents/pr-audit-fix-apply.md",
            ".claude/agents/specdev-impl.md": "../../devspec_toolkit/.claude/agents/specdev-impl.md",
        }
        assert (host / ".claude" / "skills" / "specdev-step" / "SKILL.md").read_text(encoding="utf-8") == "# specdev-step\n"
        assert (host / ".claude" / "agents" / "specdev-impl.md").is_file()

    def test_a_toolkit_outside_the_host_folder_is_linked_through_toolkit_rel(self, tmp_path, host):
        outside = build_toolkit(tmp_path / "shared" / "tk")
        ctx = make_ctx(host, outside)
        assert ctx.toolkit_rel == "../shared/tk"
        hi.install_claude_links(ctx)
        assert os.readlink(host / ".claude" / "skills" / "specdev-step") == "../../../shared/tk/.claude/skills/specdev-step"
        assert (host / ".claude" / "skills" / "specdev-step" / "SKILL.md").is_file()

    def test_second_run_is_current_and_changes_nothing(self, host, toolkit):
        hi.install_claude_links(make_ctx(host, toolkit))
        before = tree(host)
        again = hi.install_claude_links(make_ctx(host, toolkit))
        assert again.status == hi.CURRENT and again.detail == "up to date"
        assert tree(host) == before

    def test_symlinks_refreshed_for_new_skill(self, host, toolkit):
        hi.install_claude_links(make_ctx(host, toolkit))
        first = links(host)
        build_toolkit(toolkit, skills=("specdev-review",), agents=("specdev-scope.md",))  # a toolkit bump adds a skill and an agent
        result = hi.install_claude_links(make_ctx(host, toolkit))
        assert result.status == hi.CREATED
        after = links(host)
        assert set(after) - set(first) == {".claude/skills/specdev-review", ".claude/agents/specdev-scope.md"}
        assert {k: after[k] for k in first} == first

    def test_what_the_allowlists_leave_out_is_named_and_not_linked(self, host, toolkit):
        build_toolkit(toolkit, skills=("my-private-skill",), agents=("other-agent.md",))
        (toolkit / ".claude" / "skills" / ".hidden").mkdir()
        (toolkit / ".claude" / "agents" / "notes.txt").write_text("x", encoding="utf-8")
        result = hi.install_claude_links(make_ctx(host, toolkit))
        assert "my-private-skill" in result.detail and "other-agent.md" in result.detail
        assert not any("private" in name or "other-agent" in name or "hidden" in name or "notes" in name for name in links(host))
        assert hi.install_claude_links(make_ctx(host, toolkit)).status == hi.CURRENT

    def test_a_toolkit_without_a_claude_folder_has_nothing_to_link(self, host, tmp_path):
        empty = tmp_path / "empty_toolkit"
        empty.mkdir()
        result = hi.install_claude_links(make_ctx(host, empty))
        assert (result.status, result.detail) == (hi.CURRENT, "nothing to link")
        assert not (host / ".claude").exists()

    def test_dry_run_writes_nothing(self, host, toolkit):
        before = tree(host)
        result = hi.install_claude_links(make_ctx(host, toolkit, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert tree(host) == before and not (host / ".claude").exists()


class TestStaleLinks:
    def stale(self, host: Path, toolkit: Path) -> Path:
        hi.install_claude_links(make_ctx(host, toolkit))
        link = host / ".claude" / "skills" / "specdev-step"
        link.unlink()
        link.symlink_to("../../old_toolkit/.claude/skills/specdev-step")  # points elsewhere, and is broken
        return link

    def test_a_stale_link_is_reported_and_kept_without_the_flag(self, host, toolkit):
        link = self.stale(host, toolkit)
        result = hi.install_claude_links(make_ctx(host, toolkit))
        assert result.status == hi.DRIFT
        assert os.readlink(link) == "../../old_toolkit/.claude/skills/specdev-step"
        (finding,) = result.findings
        assert finding.code == "W930" and finding.file == ".claude/skills/specdev-step"
        assert "old_toolkit" in finding.text and "--force-claude" in finding.text

    def test_force_claude_replaces_a_stale_link_and_the_next_run_is_current(self, host, toolkit):
        link = self.stale(host, toolkit)
        result = hi.install_claude_links(make_ctx(host, toolkit, force=True))
        assert result.status == hi.REFRESHED and result.findings == ()
        assert os.readlink(link) == "../../devspec_toolkit/.claude/skills/specdev-step"
        assert hi.install_claude_links(make_ctx(host, toolkit)).status == hi.CURRENT

    def test_force_in_a_dry_run_replaces_nothing(self, host, toolkit):
        link = self.stale(host, toolkit)
        result = hi.install_claude_links(make_ctx(host, toolkit, force=True, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert os.readlink(link) == "../../old_toolkit/.claude/skills/specdev-step"


class TestRealFiles:
    @pytest.mark.parametrize("force", [False, True])
    def test_a_real_directory_at_a_skill_path_is_never_replaced(self, host, toolkit, force):
        own = host / ".claude" / "skills" / "specdev-step"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("the host's own skill\n", encoding="utf-8")
        result = hi.install_claude_links(make_ctx(host, toolkit, force=force))
        assert not own.is_symlink() and (own / "SKILL.md").read_bytes() == b"the host's own skill\n"
        assert result.status == hi.DRIFT
        (finding,) = result.findings
        assert finding.code == "W930" and finding.file == ".claude/skills/specdev-step" and "real file or folder" in finding.text
        # the other links were made
        assert (host / ".claude" / "skills" / "specdev-context").is_symlink()

    @pytest.mark.parametrize("force", [False, True])
    def test_a_real_file_at_an_agent_path_is_never_replaced(self, host, toolkit, force):
        own = host / ".claude" / "agents" / "specdev-impl.md"
        own.parent.mkdir(parents=True)
        own.write_bytes(b"my own agent\n")
        result = hi.install_claude_links(make_ctx(host, toolkit, force=force))
        assert not own.is_symlink() and own.read_bytes() == b"my own agent\n"
        assert result.status == hi.DRIFT and [f.file for f in result.findings] == [".claude/agents/specdev-impl.md"]

    def test_a_link_that_cannot_be_made_is_a_refusal_and_not_an_exception(self, host, toolkit):
        with mock.patch.object(Path, "symlink_to", side_effect=PermissionError(1, "Operation not permitted")):
            result = hi.install_claude_links(make_ctx(host, toolkit))
        assert result.status == hi.REFUSED
        assert {f.code for f in result.findings} == {"W931"}


class TestForceClaudeThroughTheDelegate:
    def test_init_force_claude_acts_through_the_delegate_command_line(self, host, tmp_path, monkeypatch, capsys):
        # a toolkit the host can run `update` against: the live templates and version, its own .claude tree
        toolkit = host / "devspec_toolkit"
        toolkit.mkdir()
        for name in ("tools", "templates", "scripts"):
            (toolkit / name).symlink_to(REPO / name, target_is_directory=True)
        build_toolkit(toolkit)
        stale = host / ".claude" / "skills" / "specdev-step"
        stale.parent.mkdir(parents=True)
        stale.symlink_to("../../somewhere_else/specdev-step")

        def delegate_argv(force: bool) -> list[str]:
            command = init_project.build_install_delegate(str(host / "devspec_env"), "devspec_toolkit", force_claude=force)
            assert command[0] == str(host / "devspec_env" / "bin" / "specdev")
            return command[1:]

        def run_main(force: bool) -> None:
            monkeypatch.setattr(sys, "argv", ["specdev", *delegate_argv(force)])
            with pytest.raises(SystemExit) as raised:
                cli.main()
            assert raised.value.code == 0

        monkeypatch.chdir(host)
        with mock.patch.object(hi, "_run_pre_commit_install", return_value=(0, "")):
            run_main(False)
            assert os.readlink(stale) == "../../somewhere_else/specdev-step"  # init without the flag leaves it
            run_main(True)
        assert os.readlink(stale) == "../../devspec_toolkit/.claude/skills/specdev-step"
        assert "claude-links" in capsys.readouterr().out
