"""The workflow templates and snippets a host copies (``templates/workflows/``).

The merge-check workflow is rendered by the installer; the three snippets are copied by hand.
Every ``specdev`` line in them is parsed by the real CLI parser, so a flag that does not exist
fails here, and a value that comes from a pull request reaches a shell only through ``env:``.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.host_install import read_managed_header

WORKFLOWS = Path(__file__).resolve().parents[2] / "templates" / "workflows"
MERGE_CHECK = WORKFLOWS / "specdev-merge-check.yml"
STEP_SNIPPET = WORKFLOWS / "specdev-step.snippet.yml"
PREAMBLE = WORKFLOWS / "deploy-preamble.snippet.yml"
EVIDENCE_PR = WORKFLOWS / "evidence-pr.snippet.yml"
ALL_FILES = [MERGE_CHECK, STEP_SNIPPET, PREAMBLE, EVIDENCE_PR]
SNIPPETS = [STEP_SNIPPET, PREAMBLE, EVIDENCE_PR]

#: The placeholders the installer replaces: ``__SPECDEV_<NAME>__``, the one syntax of the four files.
PLACEHOLDERS = {"__SPECDEV_TOOLKIT_VERSION__", "__SPECDEV_SETUP_COMMAND__"}
#: The only ``${{ }}`` expressions allowed inside a ``run:`` block (none of them is chosen by an outside author).
SAFE_RUN_EXPRESSIONS = {"github.workspace"}
SETUP_BEGIN = "# specdev:setup-begin"
SETUP_END = "# specdev:setup-end"
DECK_MARKER = "# --- the host's own deploy steps go here ---"
#: Sample values for the shell variables the templates read from ``env:``.
SAMPLES = {"BASE": "main", "BEFORE": "0123456789abcdef0123456789abcdef01234567", "PR_TITLE": "feat: add a thing",
           "SPECDEV_ENV": "staging", "TAG": "v1.0.0", "HEAD_REF": "release-prep/x", "BRANCH": "specdev-evidence/1"}


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _workflow() -> dict:
    return _load(MERGE_CHECK)


def _steps(job: str) -> list[dict]:
    return _workflow()["jobs"][job]["steps"]


def _run_blocks(node) -> list[str]:
    """Every ``run:`` value found anywhere in *node*."""
    if isinstance(node, dict):
        found = [v for k, v in node.items() if k == "run" and isinstance(v, str)]
        return found + [r for v in node.values() for r in _run_blocks(v)]
    if isinstance(node, list):
        return [r for v in node for r in _run_blocks(v)]
    return []


def _specdev_lines(path: Path) -> list[str]:
    lines = []
    for block in _run_blocks(_load(path)):
        lines.extend(line.strip() for line in block.splitlines() if line.strip().startswith("specdev "))
    return lines


def _argv(line: str) -> list[str]:
    """The argument list of a ``specdev`` line with the shell variables replaced by sample values."""
    text = re.sub(r"\$\{?([A-Z_]+)\}?", lambda m: SAMPLES[m.group(1)], line)
    tokens = shlex.split(text)
    assert tokens[0] == "specdev"
    return tokens[1:]


def _parse(line: str):
    try:
        return cli.build_parser().parse_args(_argv(line))
    except SystemExit as exc:  # argparse prints its usage and exits 2
        pytest.fail(f"the parser rejects {line!r} (exit {exc.code})")


def _step(steps: list[dict], needle: str) -> dict:
    found = [s for s in steps if needle in s.get("run", "")]
    assert len(found) == 1, (needle, found)
    return found[0]


# --- every file -------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_files_are_plain_text_with_lf_and_final_newline(path):
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert b"\r" not in raw and b"\t" not in raw


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_only_listed_placeholders_appear(path):
    found = set(re.findall(r"__[A-Z][A-Z0-9_]*__", path.read_text(encoding="utf-8")))
    assert found <= PLACEHOLDERS, found - PLACEHOLDERS


def test_merge_check_names_its_placeholders_in_a_top_comment():
    head = MERGE_CHECK.read_text(encoding="utf-8").split("\nname:")[0]
    for placeholder in PLACEHOLDERS:
        assert placeholder in head


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_every_specdev_command_line_parses(path):
    lines = _specdev_lines(path)
    assert lines or path == EVIDENCE_PR  # the evidence snippet runs git and gh only
    for line in lines:
        if line.startswith("specdev release prep"):
            continue  # its own test below
        _parse(line)


def test_release_prep_line_parses():
    (line,) = [x for x in _specdev_lines(MERGE_CHECK) if x.startswith("specdev release prep")]
    assert _parse(line).release_cmd == "prep"


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_no_run_block_interpolates_an_expression_that_is_not_listed(path):
    for block in _run_blocks(_load(path)):
        for expression in re.findall(r"\$\{\{\s*(.*?)\s*\}\}", block):
            assert expression in SAFE_RUN_EXPRESSIONS, expression


def test_untrusted_text_reaches_run_only_through_env():
    for path in ALL_FILES:
        for block in _run_blocks(_load(path)):
            assert "${{" not in block
            assert "github.event.pull_request.title" not in block and "github.head_ref" not in block
    env_values = {}
    for step in _steps("merge-check") + _steps("release-prep"):
        env_values.update(step.get("env", {}))
    assert env_values["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    assert env_values["HEAD_REF"] == "${{ github.head_ref }}"
    assert env_values["BASE"] == "${{ github.base_ref }}"


def test_no_retired_commands():
    retired = ["forward-replay-check", "completeness-check", "traceability-check", "matrix", "validate-all"]
    for path in ALL_FILES:
        for line in _specdev_lines(path):
            assert _argv(line)[0] not in retired
        text = path.read_text(encoding="utf-8")
        for word in retired:
            assert not re.search(rf"specdev\s+{re.escape(word)}\b", text)


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_no_secret_is_echoed(path):
    for block in _run_blocks(_load(path)):
        assert "secrets." not in block
        assert not re.search(r"\becho\b[^\n]*(TOKEN|SECRET|PASSWORD)", block)


# --- WI-M9-09 ---------------------------------------------------------------------------------


def test_template_parses_as_yaml_and_has_marker():
    workflow = _workflow()
    assert set(workflow["jobs"]) == {"merge-check", "release-prep"}
    header = read_managed_header(MERGE_CHECK.read_text(encoding="utf-8"))
    assert header == ("merge-check", "__SPECDEV_TOOLKIT_VERSION__")
    triggers = workflow[True]  # PyYAML 1.1 reads the key `on` as the boolean True
    assert {"pull_request", "push", "workflow_dispatch"} <= set(triggers)
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "github.ref" in workflow["concurrency"]["group"]


def test_merge_step_only_on_pr_and_default_push():
    steps = _steps("merge-check")
    pr = _step(steps, '--base-ref "origin/$BASE"')
    push = _step(steps, '--base-ref "$BEFORE"')
    assert "--merge" in pr["run"] and "--merge" in push["run"]
    assert pr["if"] == "github.event_name == 'pull_request'"
    assert "github.event_name == 'push'" in push["if"]
    assert "github.event.repository.default_branch" in push["if"] and "!=" not in push["if"]
    assert pr["env"] == {"BASE": "${{ github.base_ref }}"}
    assert push["env"] == {"BEFORE": "${{ github.event.before }}"}
    others = [s for s in steps if "spec-check" in s.get("run", "") and "--merge" not in s["run"]]
    assert len(others) == 1
    assert "!= github.event.repository.default_branch" in others[0]["if"]
    gov = _step(steps, "governance-check")
    assert gov["if"] == "github.event_name == 'pull_request'" and '--message "$PR_TITLE"' in gov["run"]


def test_checkout_has_full_history_submodules_and_token_fallback():
    for job in ("merge-check", "release-prep"):
        checkout = _steps(job)[0]
        assert checkout["uses"] == "actions/checkout@v6"
        assert checkout["with"]["fetch-depth"] == 0
        assert checkout["with"]["submodules"] == "recursive"
        assert checkout["with"]["token"] == "${{ secrets.SPECDEV_CHECKOUT_TOKEN || github.token }}"
    assert _steps("merge-check")[1]["uses"] == "astral-sh/setup-uv@v8.2.0"


def test_template_has_setup_markers_and_placeholder():
    text = MERGE_CHECK.read_text(encoding="utf-8")
    lines = text.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == SETUP_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == SETUP_END]
    assert len(begins) == len(ends) == 2  # one pair per job
    for begin, end in zip(begins, ends):
        between = [line.strip() for line in lines[begin + 1 : end]]
        assert "__SPECDEV_SETUP_COMMAND__" in between
        assert between.count("__SPECDEV_SETUP_COMMAND__") == 1


def test_merge_job_read_only_and_prep_job_write():
    jobs = _workflow()["jobs"]
    assert jobs["merge-check"]["permissions"] == {"contents": "read"}
    assert jobs["release-prep"]["permissions"] == {"contents": "write"}
    assert "needs" not in jobs["merge-check"] and "needs" not in jobs["release-prep"]


def test_snippet_contains_single_specdev_step():
    steps = _load(STEP_SNIPPET)
    assert isinstance(steps, list) and len(steps) == 1
    (line,) = _specdev_lines(STEP_SNIPPET)
    args = _parse(line)
    assert args.cmd == "spec-check" and args.merge and args.base_ref == "origin/main"
    assert steps[0]["env"] == {"BASE": "${{ github.base_ref }}"}


def test_prep_job_condition_head_ref_prefix_and_not_fork():
    condition = _workflow()["jobs"]["release-prep"]["if"]
    assert "github.event_name == 'pull_request'" in condition
    assert "github.event.pull_request.head.repo.full_name == github.repository" in condition
    assert "startsWith(github.head_ref, vars.SPECDEV_RELEASE_PREP_PREFIX || 'release-prep/')" in condition


def test_prep_job_checks_out_head_ref_with_full_history_and_write_credentials():
    checkout = _steps("release-prep")[0]
    assert checkout["with"]["ref"] == "${{ github.head_ref }}"
    assert checkout["with"]["fetch-depth"] == 0 and checkout["with"]["persist-credentials"] is True
    commit = _step(_steps("release-prep"), "git push")
    assert "git add -- spec/extras/verification" in commit["run"]
    assert "git diff --cached --quiet" in commit["run"]
    assert 'git push origin HEAD:"$HEAD_REF"' in commit["run"]
    assert commit["env"] == {"HEAD_REF": "${{ github.head_ref }}"}
    assert "git config user.name" in commit["run"] and "git config user.email" in commit["run"]
    order = [s.get("run", "") for s in _steps("release-prep")]
    assert next(i for i, r in enumerate(order) if "release prep" in r) < next(i for i, r in enumerate(order) if "git push" in r)


# --- WI-M9-10 ---------------------------------------------------------------------------------


def test_preamble_third_party_check_command_exists_in_cli_registry():
    (line,) = [x for x in _specdev_lines(PREAMBLE) if x.startswith("specdev third-party check")]
    args = _parse(line)
    assert args.installed == ["tp-example=1.0.0"] and args.env == "staging" and args.tag == "v1.0.0"
    (post,) = [x for x in _specdev_lines(PREAMBLE) if x.startswith("specdev plan record")]
    assert _parse(post).at_deploy is True
    (verify,) = [x for x in _specdev_lines(PREAMBLE) if x.startswith("specdev verify run")]
    assert _parse(verify).only_stage is True
    # exit 1 of a step stops the job: no step swallows it
    for block in _run_blocks(_load(PREAMBLE)):
        assert "|| true" not in block and "continue-on-error" not in PREAMBLE.read_text(encoding="utf-8")


def test_snippets_parse_as_yaml_fragments():
    for path in SNIPPETS:
        steps = _load(path)
        assert isinstance(steps, list) and steps
        for step in steps:
            assert isinstance(step, dict) and ("run" in step or "uses" in step) and step.get("name")


def test_prod_snippet_runs_release_check_before_deploy_steps():
    text = PREAMBLE.read_text(encoding="utf-8")
    assert text.count(DECK_MARKER) == 1
    before, after = text.split(DECK_MARKER)
    assert "specdev release check --stage prod" in before and "specdev release check" not in after
    assert "specdev third-party check" in before.split("specdev release check")[0]
    assert "specdev plan record" in after and "specdev verify run" in after


def test_staging_snippet_has_no_release_check():
    steps = _load(PREAMBLE)
    gated = [s for s in steps if "release check" in s.get("run", "")]
    assert len(gated) == 1 and gated[0]["if"] == "env.SPECDEV_ENV == 'prod'"
    assert not [s for s in steps if "release check" in s.get("run", "") and s is not gated[0]]
    third_party = _step(steps, "third-party check")
    assert "if" not in third_party  # staging and prod both run it


def test_snippets_have_write_permission_comments():
    for path in (PREAMBLE, EVIDENCE_PR):
        text = path.read_text(encoding="utf-8")
        comments = "\n".join(line for line in text.splitlines() if line.startswith("#"))
        assert "contents: write" in comments and "pull-requests: write" in comments
    assert "GITHUB_TOKEN" in EVIDENCE_PR.read_text(encoding="utf-8")
    (step,) = _load(EVIDENCE_PR)
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "git add -- spec/extras/verification" in step["run"] and "gh pr create" in step["run"]
