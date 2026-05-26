"""Unit tests for _check_toolkit_version in spec_check.py."""

from __future__ import annotations

from pathlib import Path

from specdev_tools.validation.spec_check import _check_toolkit_version
from specdev_tools.core.errors import SpecError


def _make_toolkit_root(tmp_path: Path, version: str) -> Path:
    """Create a minimal toolkit root with tools/pyproject.toml."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True)
    pyproject = tools_dir / "pyproject.toml"
    pyproject.write_text(
        f'[project]\nname = "specdev-tools"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    return tmp_path


def _make_spec_dir(tmp_path: Path, version: str | None) -> Path:
    """Create a spec dir, optionally with a specdev_version file."""
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    if version is not None:
        sv_file = spec_dir / "specdev_version"
        sv_file.write_text(
            f'toolkit_version: "{version}"\ncreated_at: "2026-01-01T00:00:00Z"\n',
            encoding="utf-8",
        )
    return spec_dir


class TestCheckToolkitVersionMatch:
    def test_matching_versions_returns_empty_list(self, tmp_path):
        toolkit_root = _make_toolkit_root(tmp_path / "toolkit", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "spec", "1.0.0")
        result = _check_toolkit_version(str(toolkit_root), str(spec_dir))
        assert result == [], f"Expected [], got {result}"

    def test_mismatch_returns_single_e608(self, tmp_path):
        toolkit_root = _make_toolkit_root(tmp_path / "toolkit", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "spec", "0.9.0")
        result = _check_toolkit_version(str(toolkit_root), str(spec_dir))
        assert result is not None
        assert len(result) == 1
        err = result[0]
        assert isinstance(err, SpecError)
        assert err.code == "E608"
        assert "0.9.0" in err.message
        assert "1.0.0" in err.message
        assert "specdev align" in err.message

    def test_no_specdev_version_file_returns_e608(self, tmp_path):
        toolkit_root = _make_toolkit_root(tmp_path / "toolkit", "1.0.0")
        spec_dir = _make_spec_dir(tmp_path / "spec", None)  # no specdev_version file
        result = _check_toolkit_version(str(toolkit_root), str(spec_dir))
        assert len(result) == 1, f"Expected one E608 error, got {result}"
        err = result[0]
        assert isinstance(err, SpecError)
        assert err.code == "E608"
        assert "specdev_version" in err.message
        assert "specdev align" in err.message

    def test_malformed_specdev_version_file_returns_e608(self, tmp_path):
        """specdev_version exists but lacks the toolkit_version key — must get a distinct E608."""
        toolkit_root = _make_toolkit_root(tmp_path / "toolkit", "1.0.0")
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        # Write a file that exists but has no toolkit_version key
        sv_file = spec_dir / "specdev_version"
        sv_file.write_text(
            'created_at: "2026-01-01T00:00:00Z"\n',
            encoding="utf-8",
        )
        result = _check_toolkit_version(str(toolkit_root), str(spec_dir))
        assert len(result) == 1, f"Expected one E608 error for malformed file, got {result}"
        err = result[0]
        assert isinstance(err, SpecError)
        assert err.code == "E608"
        # Must indicate the file is malformed/missing the key, NOT the absent-file message
        assert "malformed" in err.message or "missing the `toolkit_version` key" in err.message
        assert "No toolkit version recorded" not in err.message

    def test_missing_pyproject_returns_e608(self, tmp_path):
        # toolkit root exists but has no tools/pyproject.toml
        toolkit_root = tmp_path / "toolkit"
        toolkit_root.mkdir()
        (toolkit_root / "tools").mkdir()
        spec_dir = _make_spec_dir(tmp_path / "spec", "1.0.0")
        result = _check_toolkit_version(str(toolkit_root), str(spec_dir))
        assert len(result) == 1, f"Expected one E608 error when pyproject.toml absent, got {result}"
        err = result[0]
        assert isinstance(err, SpecError)
        assert err.code == "E608"
        assert "pyproject.toml" in err.message
