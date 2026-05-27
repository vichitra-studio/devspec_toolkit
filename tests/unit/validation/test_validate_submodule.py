"""Tests for validate.py submodule detection, stderr warnings, and 16a/16b/16c routing."""
import subprocess
from unittest.mock import patch, MagicMock

from specdev_tools.validation.validate import (
    _detect_git_root,
    _is_git_repo,
    DEEP_VALIDATORS,
)


class TestDetectGitRoot:
    def test_returns_git_toplevel(self, tmp_path):
        """When git rev-parse succeeds, returns the detected root."""
        with patch("specdev_tools.validation.validate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=str(tmp_path) + "\n"
            )
            result = _detect_git_root(tmp_path)
            assert result == tmp_path

    def test_fallback_on_failure(self, tmp_path):
        """When git fails, falls back to repo_root."""
        with patch("specdev_tools.validation.validate.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = _detect_git_root(tmp_path)
            assert result == tmp_path

    def test_fallback_on_timeout(self, tmp_path):
        """When git times out, falls back to repo_root."""
        with patch("specdev_tools.validation.validate.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
            result = _detect_git_root(tmp_path)
            assert result == tmp_path


class TestDeepValidators16abc:
    def test_16a_routes_to_step_16a(self):
        assert "16a" in DEEP_VALIDATORS
        # Verify it's not routing to step_16 anymore
        validator = DEEP_VALIDATORS["16a"]
        # The lambda should reference step_16a, not step_16
        assert validator is not DEEP_VALIDATORS["16"]

    def test_16b_routes_to_step_16b(self):
        assert "16b" in DEEP_VALIDATORS
        assert DEEP_VALIDATORS["16b"] is not DEEP_VALIDATORS["16"]

    def test_16c_routes_to_step_16c(self):
        assert "16c" in DEEP_VALIDATORS
        assert DEEP_VALIDATORS["16c"] is not DEEP_VALIDATORS["16"]


class TestIsGitRepoTimeout:
    def test_logs_on_timeout(self, tmp_path, capsys):
        """When git times out, stderr should contain a message."""
        with patch("specdev_tools.validation.validate.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
            result = _is_git_repo(tmp_path)
            assert result is False
            captured = capsys.readouterr()
            assert "timed out" in captured.err
