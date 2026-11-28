"""Regenerate tests/fixtures/step_gate/spec_check_summary.golden (run it after any change of a check, of the worked example or of a message the plain run prints).

Runs the body of test_plain_spec_check_summary_matches_golden and writes what it prints to stderr.
Usage (repo root, venv active): python scripts/regen_spec_check_summary_golden.py
"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests"), str(ROOT / "tests" / "unit" / "validation")]

import test_spec_check_step as t  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    host = t.git_copy_of_example(Path(tmp) / "host")
    spec = str(host / "spec")
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        t.reset_config()
        t.run_plain_spec_check(str(ROOT), spec, git_root=str(host), spec_root=spec, project_canon_dir=f"{spec}/canon")
        t.reset_config()
    t.GOLDEN.write_text(err.getvalue(), encoding="utf-8")
    print(err.getvalue())
