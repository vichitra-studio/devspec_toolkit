"""WI-M1-06: generated CLI command list (tools/cli_commands.json)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools import cli
from specdev_tools.cli import build_parser
from specdev_tools.core.json_utils import build_json_parser
from specdev_tools.core.registry import SchemaRegistry, clear_shared_caches
from specdev_tools.graph.commands import build_node_parser
from specdev_tools.registry.cli_commands import (
    PASSTHROUGH_BUILDERS,
    collect_command_paths,
    generate_cli_commands,
)
from specdev_tools.registry.generate import run as registry_run

_ROOT = Path(__file__).resolve().parents[3]


def _paths() -> list[str]:
    return collect_command_paths(build_parser())


def _top_level() -> list[str]:
    return [p for p in _paths() if " " not in p]


def test_counts_match_the_parsers():
    paths = _paths()
    assert len(_top_level()) == 42
    assert len([p for p in paths if p.startswith("context ")]) == 6
    assert len([p for p in paths if p.startswith("json ")]) == 9
    assert len([p for p in paths if p.startswith("node ")]) == 4
    assert len([p for p in paths if p.startswith("align ")]) == 7
    assert len([p for p in paths if p.startswith("lock ")]) == 2
    assert len([p for p in paths if p.startswith("step ")]) == 2
    assert paths == sorted(paths)


def test_spot_paths():
    paths = set(_paths())
    assert {"spec-check", "context structure", "json patch", "align apply", "json resolve-pointers"} <= paths


def test_cli_commands_lists_graph_commands():
    committed = {entry["path"] for entry in json.loads((_ROOT / "tools" / "cli_commands.json").read_text())["commands"]}
    expected = {"node", "node show", "node candidates", "node status", "node rename", "trace", "diff"}
    assert expected <= set(_paths())
    assert expected <= committed


def test_matrix_not_in_generated_command_list():
    """`specdev matrix` is refused before argparse (REMOVED_COMMANDS), so the step-10 `cli_command` list never names it."""
    committed = {entry["path"] for entry in json.loads((_ROOT / "tools" / "cli_commands.json").read_text())["commands"]}
    assert "matrix" not in committed
    assert "matrix" not in set(_paths())


def test_top_level_commands_equal_specdev_help():
    out = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "--help"], capture_output=True, text=True, cwd=_ROOT / "tools"
    ).stdout
    helped = set(out.split("{", 1)[1].split("}", 1)[0].split(","))
    assert helped == set(_top_level())


def test_build_parser_help_matches_main_help():
    parser = build_parser()
    subs = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices
    for name in ("validate", "context", "align", "json", "registry-generate"):
        out = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", name, "--help"],
            capture_output=True, text=True, cwd=_ROOT / "tools",
        ).stdout
        assert subs[name].format_help() == out
    ctx = parser.ctx_parser
    assert ctx is subs["context"]
    out = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "context"], capture_output=True, text=True, cwd=_ROOT / "tools"
    ).stdout
    assert ctx.format_help() == out


# `context extract` is a removed-command stub (add_help=False); it prints a removal notice instead.
@pytest.mark.parametrize("path", [p for p in _paths() if p != "context extract"])
def test_every_command_path_answers_help(path):
    r = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", *path.split(), "--help"],
        capture_output=True, text=True, cwd=_ROOT / "tools",
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip()


def test_json_group_sub_commands_come_only_from_build_json_parser():
    assert PASSTHROUGH_BUILDERS == {"json": build_json_parser, "node": build_node_parser}
    assert collect_command_paths(build_parser(), passthrough={}) != _paths()
    assert not [p for p in collect_command_paths(build_parser(), passthrough={}) if p.startswith(("json ", "node "))]


def test_passthrough_constant_is_iterated():
    def scratch() -> argparse.ArgumentParser:
        sp = argparse.ArgumentParser()
        sp.add_subparsers(dest="c").add_parser("zzz-scratch")
        return sp

    paths = collect_command_paths(build_parser(), passthrough={**PASSTHROUGH_BUILDERS, "context": scratch})
    assert "context zzz-scratch" in paths
    assert "context zzz-scratch" not in _paths()


def test_adding_a_parser_changes_the_output():
    parser = build_parser()
    next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).add_parser("zzz-new")
    assert "zzz-new" in collect_command_paths(parser)
    assert "zzz-new" not in _paths()


def _generate(tmp_path: Path, name: str) -> bytes:
    out = tmp_path / name
    clear_shared_caches()
    registry_run(str(_ROOT), str(tmp_path / f"{name}.r"), str(tmp_path / f"{name}.e"), cli_commands_out=str(out))
    return out.read_bytes()


def test_generated_file_equals_committed_and_is_deterministic(tmp_path):
    first = _generate(tmp_path, "a.json")
    assert first == _generate(tmp_path, "b.json")
    assert first == (_ROOT / "tools" / "cli_commands.json").read_bytes()


def test_generated_file_validates_against_schema():
    doc = generate_cli_commands()
    reg = SchemaRegistry(str(_ROOT))
    schema = json.loads((_ROOT / "schema" / "cli_commands.schema.json").read_text())
    Draft202012Validator(schema, registry=reg.to_referencing_registry()).validate(doc)
    assert json.loads((_ROOT / "tools" / "schema_registry.json").read_text())["vc:cli-commands"] == (
        "schema/cli_commands.schema.json"
    )


def test_without_cli_commands_out_nothing_extra_is_written(tmp_path):
    clear_shared_caches()
    registry_run(str(_ROOT), str(tmp_path / "r.json"), str(tmp_path / "e.json"))
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["e.json", "r.json"]


def _cli_kwargs(monkeypatch, argv: list[str]) -> dict:
    seen: dict = {}
    monkeypatch.setattr("specdev_tools.registry.generate.run", lambda **kw: seen.update(kw))
    monkeypatch.setattr(sys, "argv", ["specdev", *argv])
    cli.main()
    return seen


def test_default_destination_only_when_out_is_absent(monkeypatch, tmp_path):
    root = str(tmp_path)
    assert _cli_kwargs(monkeypatch, ["registry-generate", "--repo-root", root])["cli_commands_out"] == str(
        tmp_path / "tools" / "cli_commands.json"
    )
    explicit = _cli_kwargs(
        monkeypatch,
        ["registry-generate", "--repo-root", root, "--out", str(tmp_path / "o.json"),
         "--extraction-paths-out", str(tmp_path / "x.json")],
    )
    assert explicit["cli_commands_out"] is None
    given = _cli_kwargs(
        monkeypatch,
        ["registry-generate", "--repo-root", root, "--out", str(tmp_path / "o.json"),
         "--cli-commands-out", str(tmp_path / "c.json")],
    )
    assert given["cli_commands_out"] == str(tmp_path / "c.json")


def test_registry_generate_without_repo_root_still_fails():
    r = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "registry-generate"],
        capture_output=True, text=True, cwd=_ROOT / "tools",
    )
    assert r.returncode != 0

