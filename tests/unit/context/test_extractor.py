"""Tests for the deprecated `specdev context extract` command.

Verifies that the hard-fail stub is in place: any invocation exits 1 and
emits the migration message to stderr.
"""
import subprocess
import sys


MIGRATION_MESSAGE = (
    "context extract is removed. Use 'specdev json read <file> '<jq>'' "
    "for surgical reads, scoped via 'specdev context structure' + 'specdev json schema'. "
    "See /specdev-context skill."
)


def _run_extract(*extra_args):
    """Run `python -m specdev_tools.cli context extract <extra_args>`.

    Returns a CompletedProcess with captured stdout/stderr.
    """
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "context", "extract"] + list(extra_args),
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).parents[3] / "tools"),
    )


class TestExtractDeprecationStub:
    """All invocations of `context extract` must hard-fail with the migration message."""

    def test_bare_invocation_exits_one(self):
        result = _run_extract()
        assert result.returncode == 1

    def test_bare_invocation_migration_message_in_stderr(self):
        result = _run_extract()
        assert MIGRATION_MESSAGE in result.stderr

    def test_with_spec_dir_and_step_exits_one(self):
        result = _run_extract("spec", "--step", "14")
        assert result.returncode == 1

    def test_with_spec_dir_and_step_migration_message_in_stderr(self):
        result = _run_extract("spec", "--step", "14")
        assert MIGRATION_MESSAGE in result.stderr

    def test_with_full_flag_exits_one(self):
        result = _run_extract("spec", "--step", "04", "--full")
        assert result.returncode == 1

    def test_with_full_flag_migration_message_in_stderr(self):
        result = _run_extract("spec", "--step", "04", "--full")
        assert MIGRATION_MESSAGE in result.stderr

    def test_stub_import_directly(self):
        """extract_context() is importable and raises SystemExit(1)."""
        import sys as _sys
        import pathlib

        tools_dir = pathlib.Path(__file__).parents[3] / "tools"
        if str(tools_dir) not in _sys.path:
            _sys.path.insert(0, str(tools_dir))

        from specdev_tools.context.extractor import extract_context, MIGRATION_MESSAGE as MSG
        import io

        stderr_capture = io.StringIO()
        orig_stderr = _sys.stderr
        _sys.stderr = stderr_capture
        try:
            try:
                extract_context()
            except SystemExit as e:
                assert e.code == 1
            else:
                raise AssertionError("extract_context() should have raised SystemExit(1)")
        finally:
            _sys.stderr = orig_stderr

        assert MSG in stderr_capture.getvalue()
