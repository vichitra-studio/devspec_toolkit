"""The core of the host installer: registry, context, dry run, result shape, markers and the venv name (WI-M9-11a).

No real piece exists yet, so the tests register small fake pieces that follow the rules the real ones must follow.
Every host here is invented content in a temporary folder; no venv is created and nothing touches the network.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from specdev_tools import host_install as hi
from specdev_tools.update import run_update

TOOLKIT_VERSION = "1.2.3"


def _toolkit(folder: Path) -> Path:
    (folder / "tools").mkdir(parents=True)
    (folder / "tools" / "pyproject.toml").write_text(f'[project]\nname = "specdev-tools"\nversion = "{TOOLKIT_VERSION}"\n', encoding="utf-8")
    (folder / "templates").mkdir()
    return folder


def _git_init(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(folder)], check=True)


@pytest.fixture
def host(tmp_path: Path) -> Path:
    root = tmp_path / "host"
    _git_init(root)
    (root / "spec").mkdir()
    return root


@pytest.fixture
def toolkit(tmp_path: Path) -> Path:
    return _toolkit(tmp_path / "toolkit")


def _tree(root: Path) -> dict[str, bytes | None]:
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
        if ".git" not in p.relative_to(root).parts
    }


def _writing_piece(name: str = "fake") -> hi.HostPiece:
    """A piece that follows the rules: it writes one file it owns, nothing in a dry run, nothing twice."""

    def install(ctx: hi.InstallContext) -> hi.PieceResult:
        return hi.PieceResult(hi.write_if_changed(ctx.git_root / "fake.txt", f"toolkit={ctx.toolkit_version}\n", dry_run=ctx.dry_run))

    return hi.HostPiece(name, install)


class TestRegistry:
    def test_the_registered_pieces_are_the_ones_of_parts_a_to_c(self):
        assert [p.name for p in hi.PIECES] == ["pre-commit", "merge-driver", "workflows", "wrappers"]

    def test_pieces_run_in_registry_order_and_each_reports_under_its_name(self, host, toolkit):
        report = hi.run_host_install(host / "spec", toolkit, pieces=(_writing_piece("b"), _writing_piece("a")))
        assert [name for name, _ in report.pieces] == ["b", "a"]
        assert report.skipped == ""

    def test_a_piece_that_raises_is_a_w931_result_and_the_others_still_run(self, host, toolkit):
        def broken(ctx: hi.InstallContext) -> hi.PieceResult:
            raise RuntimeError("boom")

        report = hi.run_host_install(host / "spec", toolkit, pieces=(hi.HostPiece("broken", broken), _writing_piece()))
        results = dict(report.pieces)
        assert results["broken"].status == hi.REFUSED
        assert report.warnings() == ["W931 HOST_INSTALL_REFUSED: broken failed: RuntimeError: boom"]
        assert results["fake"].status == hi.CREATED

    def test_the_four_codes_are_the_registered_ones(self):
        from specdev_tools.core.errors import ERROR_CODES

        names = {hi.W_TEMPLATE_DRIFT: "HOST_TEMPLATE_DRIFT", hi.W_INSTALL_REFUSED: "HOST_INSTALL_REFUSED",
                 hi.W_RETIRED_COMMAND: "HOST_RETIRED_COMMAND", hi.W_SETUP_UNDECLARED: "HOST_SETUP_UNDECLARED"}
        assert {code: ERROR_CODES[code] for code in names} == names


class TestContext:
    def test_context_carries_the_flags_the_paths_and_the_venv_name(self, host, toolkit):
        seen: list[hi.InstallContext] = []

        def spy(ctx: hi.InstallContext) -> hi.PieceResult:
            seen.append(ctx)
            return hi.PieceResult(hi.CURRENT)

        hi.run_host_install(host / "spec", toolkit, adopt=True, force_claude=True, dry_run=True, pieces=(hi.HostPiece("spy", spy),))
        (ctx,) = seen
        assert (ctx.adopt, ctx.force_claude, ctx.dry_run) == (True, True, True)
        assert ctx.git_root == host.resolve()
        assert ctx.spec_rel == "spec"
        assert ctx.toolkit_version == TOOLKIT_VERSION
        assert ctx.templates_dir == toolkit / "templates"
        assert ctx.toolkit_rel == Path(__import__("os").path.relpath(toolkit, host.resolve())).as_posix()
        assert ctx.venv_bin == Path(sys.prefix) / "bin"

    def test_spec_dir_in_a_subfolder_and_explicit_git_root_override(self, tmp_path, toolkit):
        outer = tmp_path / "outer"
        _git_init(outer)
        _git_init(outer / "inner")
        (outer / "inner" / "specs").mkdir()
        seen: list[hi.InstallContext] = []

        def spy(ctx: hi.InstallContext) -> hi.PieceResult:
            seen.append(ctx)
            return hi.PieceResult(hi.CURRENT)

        piece = (hi.HostPiece("spy", spy),)
        hi.run_host_install(outer / "inner" / "specs", toolkit, pieces=piece)
        hi.run_host_install(outer / "inner" / "specs", toolkit, git_root=outer, pieces=piece)
        assert [(c.git_root, c.spec_rel) for c in seen] == [
            ((outer / "inner").resolve(), "specs"),
            (outer.resolve(), "inner/specs"),
        ]

    @pytest.mark.parametrize(
        ("prefix", "expected"),
        [
            ("{host}/my_env", "my_env"),
            ("{host}/devspec_env", "devspec_env"),
            ("{host}/deeper/venv", "devspec_env"),
            ("{host}", "devspec_env"),
            ("/usr/local", "devspec_env"),
        ],
    )
    def test_venv_name_comes_from_sys_prefix_only_directly_under_the_host(self, host, prefix, expected):
        assert hi.venv_name_for(host, prefix.format(host=host)) == expected

    def test_venv_name_defaults_to_the_running_interpreter(self, host):
        with mock.patch.object(sys, "prefix", str(host / "custom_env")):
            assert hi.venv_name_for(host) == "custom_env"

    def test_the_context_uses_the_venv_the_command_runs_in(self, host, toolkit):
        # init runs `update` with the venv it just created: sys.prefix is that venv, directly under the host
        seen: list[hi.InstallContext] = []

        def spy(ctx: hi.InstallContext) -> hi.PieceResult:
            seen.append(ctx)
            return hi.PieceResult(hi.CURRENT)

        with mock.patch.object(sys, "prefix", str(host / "special_env")):
            hi.run_host_install(host / "spec", toolkit, pieces=(hi.HostPiece("spy", spy),))
        assert seen[0].venv_name == "special_env"
        assert seen[0].venv_bin == host / "special_env" / "bin"


class TestRefusals:
    def test_install_skipped_when_toolkit_is_the_host(self, tmp_path):
        both = _toolkit(tmp_path / "both")
        _git_init(both)
        (both / "spec").mkdir()
        called: list[str] = []
        piece = hi.HostPiece("fake", lambda ctx: called.append("ran") or hi.PieceResult(hi.CREATED))
        before = _tree(both)

        report = hi.run_host_install(both / "spec", both, pieces=(piece,))

        assert called == []
        assert dict(report.pieces)["fake"].status == hi.REFUSED
        assert report.warnings() == ["W931 HOST_INSTALL_REFUSED: the toolkit checkout is not a host"]
        assert _tree(both) == before

    def test_a_spec_dir_outside_git_refuses_every_piece(self, tmp_path, toolkit):
        spec = tmp_path / "loose" / "spec"
        spec.mkdir(parents=True)
        report = hi.run_host_install(spec, toolkit, pieces=(_writing_piece("a"), _writing_piece("b")))
        assert [(n, r.status) for n, r in report.pieces] == [("a", hi.REFUSED), ("b", hi.REFUSED)]
        assert all("not inside a git repository" in w for w in report.warnings())

    def test_a_spec_dir_outside_the_named_git_root_is_refused(self, tmp_path, host, toolkit):
        other = tmp_path / "other"
        _git_init(other)
        report = hi.run_host_install(host / "spec", toolkit, git_root=other, pieces=(_writing_piece(),))
        assert dict(report.pieces)["fake"].status == hi.REFUSED
        assert "is not inside the git root" in report.warnings()[0]

    def test_missing_templates_folder_or_version_skips_without_pieces(self, host, tmp_path, toolkit):
        (toolkit / "templates").rmdir()
        report = hi.run_host_install(host / "spec", toolkit, pieces=(_writing_piece(),))
        assert report.skipped == hi.NO_TOOLKIT_INPUTS and report.pieces == ()
        assert not (host / "fake.txt").exists()


class TestDryRun:
    def test_dry_run_writes_nothing(self, host, toolkit):
        before = _tree(host)
        report = hi.run_host_install(host / "spec", toolkit, dry_run=True, pieces=(_writing_piece(),))
        assert dict(report.pieces)["fake"].status == hi.WOULD_INSTALL
        assert _tree(host) == before

    def test_dry_run_of_update_writes_nothing_in_the_host(self, host, toolkit):
        before = _tree(host)
        result = run_update(host / "spec", toolkit, dry_run=True)
        assert result.status == "would_update"
        assert _tree(host) == before

    def test_dry_run_runs_no_git_config_or_pre_commit(self, host, toolkit):
        commands: list[list[str]] = []
        real_run = subprocess.run

        def recording_run(cmd, *args, **kwargs):
            commands.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=recording_run):
            hi.run_host_install(host / "spec", toolkit, dry_run=True, pieces=(_writing_piece(),))
            run_update(host / "spec", toolkit, dry_run=True, install_only=True)
        assert commands
        assert all(c[0] == "git" and c[3] == "rev-parse" for c in commands), commands


class TestResultShape:
    def test_json_value_has_skipped_and_one_entry_per_piece(self, host, toolkit):
        refusal = hi.refused("no", file="a.txt")
        drift = hi.PieceResult(hi.DRIFT, "differs", (hi.Finding(hi.W_TEMPLATE_DRIFT, file="x.yaml", line=3, command="spec-check", text="replace it"),))
        report = hi.InstallReport(pieces=(("one", refusal), ("two", drift)))
        assert report.to_dict() == {
            "skipped": None,
            "pieces": {
                "one": {"status": "refused", "detail": "no",
                        "findings": [{"code": "W931", "file": "a.txt", "line": None, "command": "", "text": "no"}]},
                "two": {"status": "drift", "detail": "differs",
                        "findings": [{"code": "W930", "file": "x.yaml", "line": 3, "command": "spec-check", "text": "replace it"}]},
            },
        }
        assert report.warnings() == ["W931 HOST_INSTALL_REFUSED: a.txt: no", "W930 HOST_TEMPLATE_DRIFT: x.yaml:3: replace it"]

    def test_empty_and_skipped_reports(self):
        assert hi.InstallReport().to_dict() == {"skipped": None, "pieces": {}}
        assert hi.InstallReport(skipped="--no-install").to_dict() == {"skipped": "--no-install", "pieces": {}}
        assert hi.InstallReport().summary() == "Host install: no pieces to install."

    def test_second_run_changes_nothing_and_says_so(self, host, toolkit):
        piece = (_writing_piece(),)
        first = hi.run_host_install(host / "spec", toolkit, pieces=piece)
        after_first = _tree(host)
        second = hi.run_host_install(host / "spec", toolkit, pieces=piece)
        assert dict(first.pieces)["fake"].status == hi.CREATED
        assert dict(second.pieces)["fake"].status == hi.CURRENT
        assert _tree(host) == after_first


class TestWriteIfChanged:
    def test_created_refreshed_current_and_would_install(self, tmp_path):
        target = tmp_path / "sub" / "f.txt"
        assert hi.write_if_changed(target, "a\n", dry_run=True) == hi.WOULD_INSTALL and not target.exists()
        assert hi.write_if_changed(target, "a\n", dry_run=False) == hi.CREATED
        assert hi.write_if_changed(target, "a\n", dry_run=False) == hi.CURRENT
        assert hi.write_if_changed(target, "b\n", dry_run=True) == hi.WOULD_INSTALL and target.read_text() == "a\n"
        assert hi.write_if_changed(target, "b\n", dry_run=False) == hi.REFRESHED and target.read_text() == "b\n"


class TestMarkers:
    TEXT = "# mine\nrepos:\n  # >>> specdev-managed\n  - old\n  # <<< specdev-managed\n# also mine\n"

    def test_replace_keeps_every_byte_outside_the_markers(self):
        out = hi.replace_marked_block(self.TEXT, "  - new\n  - newer")
        assert out == "# mine\nrepos:\n  # >>> specdev-managed\n  - new\n  - newer\n  # <<< specdev-managed\n# also mine\n"

    def test_replace_is_idempotent(self):
        once = hi.replace_marked_block(self.TEXT, "  - new\n")
        assert hi.replace_marked_block(once, "  - new\n") == once

    def test_split_parts_join_back_to_the_text(self):
        before, inside, after = hi.split_marked_block(self.TEXT)
        assert inside == "  - old\n"
        assert before + inside + after == self.TEXT

    def test_text_without_markers_has_no_block(self):
        assert hi.split_marked_block("repos: []\n") is None
        assert hi.replace_marked_block("repos: []\n", "x") is None

    @pytest.mark.parametrize(
        "text",
        [
            "# >>> specdev-managed\nx\n",
            "# <<< specdev-managed\n# >>> specdev-managed\n",
            "# >>> specdev-managed\n# <<< specdev-managed\n# >>> specdev-managed\n# <<< specdev-managed\n",
        ],
    )
    def test_damaged_markers_are_refused_not_guessed(self, text):
        with pytest.raises(hi.HostInstallError):
            hi.split_marked_block(text)

    def test_header_round_trip(self):
        header = hi.managed_header("workflow", "1.2.0")
        assert header == "# specdev-managed: workflow toolkit=1.2.0"
        assert hi.read_managed_header(header + "\nname: x\n") == ("workflow", "1.2.0")
        assert hi.read_managed_header("name: x\n") is None


class TestRefusedHelper:
    def test_refused_carries_a_w931_finding_with_the_reason(self):
        result = hi.refused("because", file="f")
        assert result.status == hi.REFUSED
        assert [f.render() for f in result.findings] == ["W931 HOST_INSTALL_REFUSED: f: because"]
