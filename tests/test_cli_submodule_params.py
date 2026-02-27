"""Tests for CLI --spec-root and --git-root parameter parsing."""
import subprocess
import sys
import pytest


class TestValidateSpecRootParam:
    def test_help_shows_spec_root(self):
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "validate", "--help"],
            capture_output=True, text=True,
        )
        assert "--spec-root" in result.stdout

    def test_help_shows_git_root(self):
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "validate", "--help"],
            capture_output=True, text=True,
        )
        assert "--git-root" in result.stdout


class TestValidateAllSpecRootParam:
    def test_help_shows_spec_root(self):
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "validate-all", "--help"],
            capture_output=True, text=True,
        )
        assert "--spec-root" in result.stdout


class TestForwardReplayCheckParams:
    def test_help_shows_spec_root(self):
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "forward-replay-check", "--help"],
            capture_output=True, text=True,
        )
        assert "--spec-root" in result.stdout

    def test_help_shows_git_root(self):
        result = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "forward-replay-check", "--help"],
            capture_output=True, text=True,
        )
        assert "--git-root" in result.stdout
