"""Unit tests for specdev_tools.llm.bundle — run_bundle assembler.

All tests use tmp_path fixtures for synthetic spec dirs.
No dependency on the real host repo spec directory.
Synthetic ids follow the fr-example-NNN pattern.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Helpers to build synthetic spec environments in tmp_path
# ---------------------------------------------------------------------------

_STEP_ORDER = {
    "version": "1",
    "steps": ["00", "01", "02", "03", "04", "05"],
    "downstream_consumers": {
        "03": ["04"],
        "04": ["05"],
    },
}

_ENTRY_KEY_REGISTRY = {
    "registry": {
        "04_fr_list.json": {
            "step": "04",
            "arrays": [
                {
                    "array_path": ".functional_requirements",
                    "id_field": "fr_id",
                    "kind": "functional_requirement",
                }
            ],
        }
    }
}

_FR_LIST_SPEC = {
    "$schema": "vc:04-fr-list",
    "id": "fr-list",
    "owner": "product",
    "functional_requirements": [
        {"fr_id": "fr-example-001", "name": "First example requirement"},
        {"fr_id": "fr-example-002", "name": "Second example requirement"},
        {"fr_id": "fr-example-subscribe", "name": "Subscribe to newsletter"},
    ],
}

_PROMPT_04_CONTENT = "# Prompt 04: Functional Requirements\nWrite functional requirements."


def _make_repo(tmp_path: object) -> tuple:
    """Build a minimal synthetic repo under tmp_path.

    Returns (repo_root, spec_root) as string paths.
    """
    import pathlib
    base = pathlib.Path(str(tmp_path))

    # toolkit repo structure
    repo = base / "toolkit"
    repo.mkdir()

    # tools/step_order.json
    (repo / "tools").mkdir()
    (repo / "tools" / "step_order.json").write_text(
        json.dumps(_STEP_ORDER), encoding="utf-8"
    )

    # prompts/prompt_04_functional_requirements.md
    (repo / "prompts").mkdir()
    (repo / "prompts" / "prompt_04_functional_requirements.md").write_text(
        _PROMPT_04_CONTENT, encoding="utf-8"
    )

    # CLAUDE.md (toolkit)
    (repo / "CLAUDE.md").write_text("# Toolkit CLAUDE.md", encoding="utf-8")

    # spec dir (host-side, under git_root)
    git_root = base / "host"
    git_root.mkdir()
    spec = git_root / "spec"
    spec.mkdir()

    # entry_key_registry.json
    (spec / "entry_key_registry.json").write_text(
        json.dumps(_ENTRY_KEY_REGISTRY), encoding="utf-8"
    )

    # 04_fr_list.json
    (spec / "04_fr_list.json").write_text(
        json.dumps(_FR_LIST_SPEC), encoding="utf-8"
    )

    # host CLAUDE.md
    (git_root / "CLAUDE.md").write_text("# Host CLAUDE.md", encoding="utf-8")

    return str(repo), str(spec), str(git_root)


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from specdev_tools.llm.bundle import run_bundle


# ---------------------------------------------------------------------------
# Test 1: Happy path (no --task)
# ---------------------------------------------------------------------------

def test_happy_path_no_task(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )
    assert result["ok"] is True
    assert result["bundle_version"] == "1"
    assert result["step"] == "04"
    assert result["task"] is None
    assert result["scoped_entries"] == []
    assert result["unresolved"] == []
    assert result["iterations"] == {"inner": 0}
    assert result["partial"] is False

    # All 11 context slots present (even if null for missing optional files)
    ctx = result["context"]
    required_slots = [
        "skill_md", "shared_expectations", "prompt_NN", "claude_md_toolkit",
        "claude_md_host", "llm_protocol", "step_order", "trace_matrix",
        "step_docs", "canon_manifest_core", "canon_manifest_project",
    ]
    for slot in required_slots:
        assert slot in ctx, f"context missing slot: {slot!r}"

    # step_order must be the parsed dict (not null)
    assert isinstance(ctx["step_order"], dict)
    assert "steps" in ctx["step_order"]

    # prompt_NN must be non-null (file exists)
    assert ctx["prompt_NN"] is not None

    # claude_md_toolkit must be non-null (file exists)
    assert ctx["claude_md_toolkit"] is not None

    # step_structure_summary: entry_count and ids
    sss = result["step_structure_summary"]
    assert len(sss) >= 1
    first_key = next(iter(sss))
    entry = sss[first_key]
    assert "entry_count" in entry
    assert "ids" in entry
    assert isinstance(entry["entry_count"], int)
    assert entry["entry_count"] >= 0


# ---------------------------------------------------------------------------
# Test 2: Unknown step → error envelope
# ---------------------------------------------------------------------------

def test_unknown_step(tmp_path):
    import jsonschema

    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="99",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )
    assert result["ok"] is False
    assert "unknown step" in result["error"].lower()
    assert result["bundle_version"] == "1"

    # Validate the failure envelope shape against the schema
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "tools", "specdev_tools", "llm", "schemas", "bundle_response.schema.json",
    )
    schema_path = os.path.normpath(schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(result))
    assert errors == [], f"Failure envelope schema errors:\n" + "\n".join(str(e) for e in errors)


# ---------------------------------------------------------------------------
# Test 3: Valid step but no spec file yet → step_structure_summary == {}
# ---------------------------------------------------------------------------

def test_missing_spec_file_for_step(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    # Remove the spec file so step 04 has no spec yet
    os.remove(os.path.join(spec_root, "04_fr_list.json"))

    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )
    assert result["ok"] is True  # not an error — step not yet generated
    assert result["step_structure_summary"] == {}


# ---------------------------------------------------------------------------
# Test 4: Missing entry_key_registry.json → step_structure_summary == {}
# ---------------------------------------------------------------------------

def test_missing_registry(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    os.remove(os.path.join(spec_root, "entry_key_registry.json"))

    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )
    assert result["ok"] is True
    assert result["step_structure_summary"] == {}


# ---------------------------------------------------------------------------
# Test 5: --task that matches a known id
# ---------------------------------------------------------------------------

def test_task_matches(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
        task="fr-example-001",  # exact match
    )
    assert result["ok"] is True
    matched_ids = [e["id"] for e in result["scoped_entries"]]
    assert "fr-example-001" in matched_ids, f"Expected fr-example-001 in matches, got: {matched_ids}"
    # Verify no content field leaked onto any scoped entry
    for entry in result["scoped_entries"]:
        assert "content" not in entry, f"scoped_entry must not have content: {entry}"


# ---------------------------------------------------------------------------
# Test 6: --task with no match → unresolved with reason
# ---------------------------------------------------------------------------

def test_task_no_match(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
        task="zzzzzzz",
    )
    assert result["ok"] is False
    assert len(result["unresolved"]) >= 1
    ur = result["unresolved"][0]
    assert "reason" in ur
    assert "no match" in ur["reason"].lower()


# ---------------------------------------------------------------------------
# Test 7: Argparse rejects unknown flags
# ---------------------------------------------------------------------------

def test_argparse_rejects_unknown_flags():
    from specdev_tools.cli import main as cli_main

    # Patch sys.argv and capture SystemExit
    old_argv = sys.argv[:]
    sys.argv = [
        "specdev", "llm", "bundle",
        "--step", "04",
        "--spec-root", ".",
        "--mode", "index",  # unknown flag — argparse exits 2 on unrecognized args
    ]
    try:
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        # argparse exits with code 2 for usage errors; dispatch exits 0 or 1.
        # Code 2 confirms it's argparse rejection, not a normal dispatch exit.
        assert exc_info.value.code == 2
    finally:
        sys.argv = old_argv


# ---------------------------------------------------------------------------
# Test 8: Output validates against bundle_response schema
# ---------------------------------------------------------------------------

def test_output_validates_against_schema(tmp_path):
    import jsonschema

    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )

    # Load the schema
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "tools", "specdev_tools", "llm", "schemas", "bundle_response.schema.json",
    )
    schema_path = os.path.normpath(schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(result))
    assert errors == [], f"Schema validation errors:\n" + "\n".join(str(e) for e in errors)


# ---------------------------------------------------------------------------
# Test 9: Context keys present (all 11 slots)
# ---------------------------------------------------------------------------

def test_context_keys_present(tmp_path):
    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )
    assert result["ok"] is True
    ctx = result["context"]
    expected_slots = {
        "skill_md", "shared_expectations", "prompt_NN", "claude_md_toolkit",
        "claude_md_host", "llm_protocol", "step_order", "trace_matrix",
        "step_docs", "canon_manifest_core", "canon_manifest_project",
    }
    assert expected_slots.issubset(set(ctx.keys())), (
        f"Missing context slots: {expected_slots - set(ctx.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 10: Schema rejects scoped_entries items with content field
# ---------------------------------------------------------------------------

def test_schema_rejects_scoped_entries_with_content(tmp_path):
    import jsonschema

    repo_root, spec_root, git_root = _make_repo(tmp_path)
    result = run_bundle(
        step="04",
        spec_root=spec_root,
        repo_root=repo_root,
        git_root=git_root,
    )

    # Inject a content field into scoped_entries to verify schema rejects it
    tampered = dict(result)
    tampered["scoped_entries"] = [
        {
            "file": "spec/04_fr_list.json",
            "id": "fr-example-001",
            "jq_path": ".functional_requirements[0]",
            "content": {"fr_id": "fr-example-001", "name": "First example requirement"},
        }
    ]

    schema_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "tools", "specdev_tools", "llm", "schemas", "bundle_response.schema.json",
    )
    schema_path = os.path.normpath(schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(tampered))
    assert len(errors) > 0, (
        "Schema should reject scoped_entries items with a 'content' field, but no errors found"
    )
