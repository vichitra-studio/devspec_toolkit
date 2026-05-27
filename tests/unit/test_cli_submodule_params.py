"""Tests for CLI --spec-root and --git-root parameter parsing.

These tests verify that submodule-aware flags are registered on the
expected subcommands by invoking ``--help`` through the CLI's argparse
parser directly (bypassing subprocess and venv checks).
"""
import sys
import pytest


def _get_help_text(monkeypatch: pytest.MonkeyPatch, subcommand: str) -> str:
    """Return the --help output for a subcommand by capturing SystemExit(0)."""
    import specdev_tools.cli as cli_module

    monkeypatch.setattr(cli_module, "check_venv", lambda: None)
    monkeypatch.setattr(sys, "argv", ["specdev", subcommand, "--help"])

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main()
    assert exc_info.value.code == 0, f"Expected exit 0 for {subcommand} --help"
    return ""  # capsys captures the actual output; we just need no crash


class TestValidateSpecRootParam:
    def test_help_shows_spec_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "validate", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--spec-root" in capsys.readouterr().out

    def test_help_shows_git_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "validate", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--git-root" in capsys.readouterr().out


class TestValidateAllSpecRootParam:
    def test_help_shows_spec_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "validate-all", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--spec-root" in capsys.readouterr().out


class TestForwardReplayCheckParams:
    def test_help_shows_spec_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "forward-replay-check", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--spec-root" in capsys.readouterr().out

    def test_help_shows_git_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "forward-replay-check", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--git-root" in capsys.readouterr().out


class TestCanonAcceptGitRootParam:
    def test_help_shows_git_root(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "canon-accept", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--git-root" in capsys.readouterr().out


class TestCanonSchemaAlignmentCanonDirParam:
    def test_help_shows_canon_dir(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        import specdev_tools.cli as cli_module
        monkeypatch.setattr(cli_module, "check_venv", lambda: None)
        monkeypatch.setattr(sys, "argv", ["specdev", "canon-schema-alignment", "--help"])
        with pytest.raises(SystemExit):
            cli_module.main()
        assert "--canon-dir" in capsys.readouterr().out
