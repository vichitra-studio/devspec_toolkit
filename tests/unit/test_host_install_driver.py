"""The merge-driver piece of the host installer: ``trace.merge_driver.install_driver`` run in a temporary host clone.

Git config and the attributes file are per clone; every test works in a repository under ``tmp_path`` and one test
asserts that the toolkit's own repository is left as it was.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from specdev_tools import host_install as hi
from specdev_tools.trace.merge_driver import DRIVER_DESCRIPTION, DRIVER_NAME

REPO = Path(__file__).resolve().parents[2]
KEY = f"merge.{DRIVER_NAME}.driver"
ATTRIBUTE = "spec/extras/trace.lock.json merge=specdev-trace-lock"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else f"<exit {done.returncode}>"


@pytest.fixture
def host(tmp_path: Path) -> Path:
    root = tmp_path / "host"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "spec").mkdir()
    return root


def make_ctx(root: Path, *, venv_prefix: Path | None = None, venv: str | None = None, dry_run: bool = False) -> hi.InstallContext:
    prefix = venv_prefix or root / ".venv"
    return hi.InstallContext(
        spec_dir=root / "spec",
        spec_rel="spec",
        git_root=root,
        toolkit_root=root / "devspec_toolkit",
        templates_dir=REPO / "templates",
        toolkit_version="1.2.3",
        venv_prefix=prefix,
        venv_name=venv or prefix.name,
        dry_run=dry_run,
        adopt=False,
        force_claude=False,
    )


def info_attributes(root: Path) -> Path:
    return root / git(root, "rev-parse", "--git-path", "info/attributes")


class TestInstall:
    def test_merge_driver_config_and_info_attributes_written_in_worktree(self, host, tmp_path):
        subprocess.run(["git", "-C", str(host), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "base"], check=True)
        linked = tmp_path / "linked"
        subprocess.run(["git", "-C", str(host), "worktree", "add", "-q", str(linked), "-b", "side"], check=True)
        (linked / "spec").mkdir()
        result = hi.install_merge_driver(make_ctx(linked))
        assert result.status == hi.CREATED and result.findings == ()
        # one config and one attributes file, shared by both working trees of the clone
        assert git(host, "config", "--local", "--get", KEY) == git(linked, "config", "--local", "--get", KEY) != "<exit 1>"
        shared = (host / ".git" / "info" / "attributes").read_text(encoding="utf-8")
        assert shared.splitlines() == [ATTRIBUTE]
        assert git(linked, "rev-parse", "--git-path", "info/attributes").endswith(".git/info/attributes")
        assert not (linked / ".gitattributes").exists() and not (host / ".gitattributes").exists()
        assert git(host, "config", "--local", "--get", f"merge.{DRIVER_NAME}.name") == DRIVER_DESCRIPTION

    def test_merge_driver_command_carries_the_four_arguments_once(self, host):
        hi.install_merge_driver(make_ctx(host))
        value = git(host, "config", "--local", "--get", KEY)
        assert value.endswith(" lock merge %O %A %B %P")
        assert [value.count(token) for token in ("%O", "%A", "%B", "%P")] == [1, 1, 1, 1]
        assert shlex.split(value)[0] == str(host / ".venv" / "bin" / "specdev")

    @pytest.mark.parametrize("venv", [".venv", "devspec_env"])
    def test_the_command_names_the_venv_of_the_context(self, host, venv):
        hi.install_merge_driver(make_ctx(host, venv_prefix=host / venv))
        assert shlex.split(git(host, "config", "--local", "--get", KEY))[0] == str(host / venv / "bin" / "specdev")

    def test_a_venv_path_with_a_space_is_quoted_and_still_current_on_the_second_run(self, host):
        ctx = make_ctx(host, venv_prefix=host / "my env")
        hi.install_merge_driver(ctx)
        assert shlex.split(git(host, "config", "--local", "--get", KEY))[0] == str(host / "my env" / "bin" / "specdev")
        assert hi.install_merge_driver(ctx).status == hi.CURRENT
        assert hi.install_merge_driver(make_ctx(host, venv_prefix=host / "my env", dry_run=True)).status == hi.CURRENT

    def test_second_run_changes_nothing_and_says_current(self, host):
        ctx = make_ctx(host)
        hi.install_merge_driver(ctx)
        before = (info_attributes(host).read_bytes(), (host / ".git" / "config").read_bytes())
        again = hi.install_merge_driver(ctx)
        assert again.status == hi.CURRENT and again.findings == ()
        assert (info_attributes(host).read_bytes(), (host / ".git" / "config").read_bytes()) == before

    def test_a_changed_driver_command_is_refreshed(self, host):
        hi.install_merge_driver(make_ctx(host))
        result = hi.install_merge_driver(make_ctx(host, venv_prefix=host / "other"))
        assert result.status == hi.REFRESHED
        assert shlex.split(git(host, "config", "--local", "--get", KEY))[0] == str(host / "other" / "bin" / "specdev")
        assert info_attributes(host).read_text(encoding="utf-8").splitlines() == [ATTRIBUTE]

    def test_the_hosts_own_attribute_lines_survive(self, host):
        path = info_attributes(host)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("*.png binary\n# my note", encoding="utf-8")  # no final newline on purpose
        hi.install_merge_driver(make_ctx(host))
        assert path.read_text(encoding="utf-8").splitlines() == ["*.png binary", "# my note", ATTRIBUTE]

    def test_a_spec_folder_in_a_subfolder_routes_its_own_lock(self, host):
        ctx = make_ctx(host)
        ctx = hi.InstallContext(**{**ctx.__dict__, "spec_rel": "docs/spec"})
        hi.install_merge_driver(ctx)
        assert info_attributes(host).read_text(encoding="utf-8").splitlines() == ["docs/spec/extras/trace.lock.json merge=specdev-trace-lock"]

    def test_git_config_is_local_to_the_host_and_the_toolkit_repository_is_untouched(self, host, tmp_path):
        toolkit_config = Path(git(REPO, "rev-parse", "--path-format=absolute", "--git-path", "config"))
        toolkit_attributes = Path(git(REPO, "rev-parse", "--path-format=absolute", "--git-path", "info/attributes"))
        snapshot = lambda: (toolkit_config.read_bytes(), toolkit_attributes.read_bytes() if toolkit_attributes.exists() else None)  # noqa: E731
        before = snapshot()
        global_before = git(host, "config", "--global", "--get", KEY)
        hi.install_merge_driver(make_ctx(host))
        assert snapshot() == before
        assert git(host, "config", "--global", "--get", KEY) == global_before
        assert git(host, "config", "--local", "--get", KEY).endswith("lock merge %O %A %B %P")


class TestDryRunAndRefusal:
    def test_dry_run_writes_nothing_and_runs_no_git_config(self, host):
        before = ((host / ".git" / "config").read_bytes(), info_attributes(host).exists())
        commands: list[list[str]] = []
        real_run = subprocess.run

        def recording(cmd, *args, **kwargs):
            commands.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=recording):
            result = hi.install_merge_driver(make_ctx(host, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert commands and all(c[0] == "git" and c[3] == "rev-parse" for c in commands), commands
        assert ((host / ".git" / "config").read_bytes(), info_attributes(host).exists()) == before

    def test_dry_run_of_an_installed_driver_says_current(self, host):
        hi.install_merge_driver(make_ctx(host))
        assert hi.install_merge_driver(make_ctx(host, dry_run=True)).status == hi.CURRENT

    def test_dry_run_notices_a_missing_attributes_line(self, host):
        hi.install_merge_driver(make_ctx(host))
        info_attributes(host).write_text("", encoding="utf-8")
        assert hi.install_merge_driver(make_ctx(host, dry_run=True)).status == hi.WOULD_INSTALL

    def test_a_folder_that_is_not_a_clone_is_refused_with_w931(self, tmp_path):
        folder = tmp_path / "not-a-repo"
        (folder / "spec").mkdir(parents=True)
        result = hi.install_merge_driver(make_ctx(folder))
        assert result.status == hi.REFUSED and [f.code for f in result.findings] == ["W931"]

    def test_the_piece_is_registered_after_the_pre_commit_piece(self):
        assert [p.name for p in hi.PIECES][:2] == ["pre-commit", "merge-driver"]
        assert hi.PIECES[1].install is hi.install_merge_driver
