"""``specdev align propose <spec_dir> --kind refines|prose-ids`` (WI-M10-09): the command, not only the proposers.

Each test runs ``cli.main`` with the argv of a real call on a copy of the invented gold set (``refines_gold``).
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools import cli
from specdev_tools.migration.proposers import KINDS
from specdev_tools.migration.worklist import WORKLIST_FILE
from specdev_tools.registry.cli_commands import collect_command_paths, generate_cli_commands

from ._proposer_support import copy_gold
from ._support import REAL_ROOT, tree_digest


def propose(host: Path, *argv: str, spec: Path | None = None) -> tuple[int, str, str]:
    """Run ``specdev align propose <spec> *argv`` in process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    command = ["specdev", "align", "propose", str(spec or host / "spec"), "--repo-root", str(REAL_ROOT), "--git-root", str(host), *argv]
    with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", command), redirect_stdout(out), redirect_stderr(err):
        try:
            cli.main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def host(tmp_path) -> Path:
    return copy_gold(tmp_path)


def test_kind_selects_the_proposer(host):
    code, out, err = propose(host, "--kind", "refines")
    assert code == 0, err
    assert out.startswith("align propose --kind refines: 104 task criteria, ")
    assert "auto-eligible   tc-" in out and "worklist: 104 item(s) added, 0 already listed" in out
    items = json.loads((host / "spec" / WORKLIST_FILE).read_text(encoding="utf-8"))["items"]
    assert {item["kind"] for item in items} == {"refines"}
    code, out, err = propose(host, "--kind", "prose-ids")
    assert code == 0, err
    assert out.startswith("align propose --kind prose-ids: 0 nodes, 0 resolved")
    assert {item["kind"] for item in json.loads((host / "spec" / WORKLIST_FILE).read_text(encoding="utf-8"))["items"]} == {"refines"}


def test_json_prints_the_envelope_of_the_other_align_actions_and_the_proposals(host):
    code, out, err = propose(host, "--kind", "refines", "--json")
    assert code == 0, err
    document = json.loads(out)
    assert {key: document[key] for key in ("status", "command", "action", "kind", "error_count", "dry_run")} == {
        "status": "PASS", "command": "align", "action": "propose", "kind": "refines", "error_count": 0, "dry_run": False,
    }
    assert document["added"] == len(document["proposals"]) == document["counts"]["task criteria"] == 104
    assert {"worklist_id", "class", "about", "target", "score", "alternatives"} <= set(document["proposals"][0])
    assert propose(host, "--kind", "refines", "--json")[1] and json.loads(propose(host, "--kind", "refines", "--json")[1])["added"] == 0


def test_a_dry_run_prints_the_proposals_and_adds_no_item(host):
    before = tree_digest(host)
    code, out, err = propose(host, "--kind", "refines", "--dry-run")
    assert code == 0, err
    assert "dry run: nothing was added to the worklist" in out and tree_digest(host) == before


def test_unknown_kind_is_a_usage_error(host):
    for argv in (("--kind", "binding"), ("--kind", "refine"), ()):
        code, out, err = propose(host, *argv)
        assert code == 2 and out == ""
        assert "align propose needs --kind {refines,prose-ids,bindings}" in err


def test_a_spec_folder_that_is_not_in_migration_is_refused_in_one_line(host):
    (host / "spec" / "extras" / "migration" / "capture.json").unlink()
    code, out, err = propose(host, "--kind", "refines")
    assert code == 1 and out == ""
    assert err.count("\n") == 1 and "is not in migration: it has no extras/migration/capture.json; run `specdev align apply --auto` first" in err
    code, out, err = propose(host, "--kind", "refines", "--json")
    assert code == 1 and f"{host / 'spec'} is not in migration" in json.loads(out)["errors"][0]["message"]


def test_the_help_names_the_kinds_the_command_runs():
    out = io.StringIO()
    with redirect_stdout(out), pytest.raises(SystemExit):
        cli.build_parser().parse_args(["align", "--help"])
    text = " ".join(out.getvalue().split())
    assert all(kind in text for kind in KINDS)
    assert "propose: print the proposals, add no item to the worklist" in text


def test_the_parser_registers_propose_in_cli_commands_json():
    assert "align propose" in collect_command_paths(cli.build_parser())
    assert {"path": "align propose"} in generate_cli_commands()["commands"]
