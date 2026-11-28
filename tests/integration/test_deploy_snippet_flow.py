"""The deploy preamble of ``templates/workflows/deploy-preamble.snippet.yml`` run as a flow, and the merge gate's pin check on the worked example (DOC 13.7 steps 4 and 6).

The preamble is a list of workflow steps a host copies into its deploy job.  Its ``specdev`` lines are read from the template, in the template's order
(none is retyped, so a change of the template changes what these tests run); the values a job supplies are filled in the way
``tests/unit/test_workflow_templates.py`` does it: ``$SPECDEV_ENV`` and ``$TAG`` from the job's ``env:`` (here a dict), the two names the template tells a host
to edit (``tp-example=1.0.0`` and ``ITEM/ACTION``) with the host's own, and a step whose ``if:`` does not hold for the job is skipped.  The three root flags
the template passes (``--repo-root ./devspec_toolkit --spec-root ./spec --git-root .``) are dropped from each line and added again, with the paths of the
scratch host, by ``cli_run``: the host here is not laid out as a submodule host.  A step that exits non-zero stops the job, as a workflow does.

The host is ``flow_host`` (``integration/_release_support.py``).  Nothing touches the network or a remote.
"""
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from unit.graph._synth import ROOT, git
from unit.lifecycle._milestone_support import cli_run
from unit.trace._lock_support import git_copy_of_example, run_on_example
from unit.verify._support import commit_all, write_json
from integration._release_support import DEPLOY_ACTION, DEPLOY_ITEM, LOCKED_PIN, flow_host, identity  # noqa: F401  (the fixtures)

PREAMBLE = ROOT / "templates" / "workflows" / "deploy-preamble.snippet.yml"
TAG = "v1.0.0"
ROOT_FLAGS = ("--repo-root", "--spec-root", "--git-root")
RECORDS = Path("spec") / "extras" / "verification"
pytestmark = pytest.mark.usefixtures("identity")


@dataclass(frozen=True)
class Ran:
    """One line of the preamble as it ran: the arguments (after ``specdev``), the exit code and everything it printed."""

    argv: tuple[str, ...]
    code: int
    out: str


def preamble_lines(env: str) -> list[str]:
    """The ``specdev`` lines of the template, in order, of the steps that run in the deploy job for the environment *env*."""
    lines = []
    for step in yaml.safe_load(PREAMBLE.read_text(encoding="utf-8")):
        condition = step.get("if")
        if condition is not None:
            matched = re.fullmatch(r"env\.SPECDEV_ENV == '(\w+)'", condition.strip())
            assert matched, f"the template has a condition this test does not read: {condition!r}"
            if matched.group(1) != env:
                continue
        lines += [line.strip() for line in step["run"].splitlines() if line.strip().startswith("specdev ")]
    assert lines, "the template holds no specdev line"
    return lines


def argv_of(line: str, env: str, installed: str) -> list[str]:
    """The arguments of a template line for a deploy of *env*: the job's values, the edited names, no root flags."""
    values = {"SPECDEV_ENV": env, "TAG": TAG}
    text = re.sub(r"\$\{?([A-Z_]+)\}?", lambda found: values[found.group(1)], line)
    tokens = shlex.split(text)
    assert tokens[0] == "specdev"
    argv, skip = [], False
    for token in tokens[1:]:
        if skip:
            skip = False
        elif token in ROOT_FLAGS:
            skip = True
        else:
            argv.append({"tp-example=1.0.0": f"{LOCKED_PIN[0]}={installed}", "ITEM/ACTION": f"{DEPLOY_ITEM}/{DEPLOY_ACTION}"}.get(token, token))
    return argv


def run_preamble(host: Path, env: str, installed: str = LOCKED_PIN[1]) -> list[Ran]:
    """Run the preamble's lines on *host* in order, stopping after the first that exits non-zero."""
    ran: list[Ran] = []
    for line in preamble_lines(env):
        argv = argv_of(line, env, installed)
        code, out, err = cli_run(host, *argv)
        ran.append(Ran(tuple(argv), code, out + err))
        if code != 0:
            break
    return ran


def deployed_files(host: Path) -> set[str]:
    """The evidence and deploy records the deploy jobs write (everything under ``extras/verification`` that is not the host's own)."""
    return {path.name for path in (host / RECORDS).glob("*") if path.name.startswith(("dep-", "evd-")) and not path.name.startswith("evd-password-reset")}


def commands(ran: list[Ran]) -> list[str]:
    return [" ".join(item.argv[:2]) for item in ran]


# --- the preamble -------------------------------------------------------------------------------------------------------------


def test_the_template_holds_the_four_commands_in_the_order_the_docs_name() -> None:
    """The flow below follows the template; this fixes what it is made of today, so a command that moves or goes shows up here first."""
    assert [" ".join(argv_of(line, "prod", LOCKED_PIN[1])[:2]) for line in preamble_lines("prod")] == ["third-party check", "release check", "verify run", "plan record"]
    assert [" ".join(argv_of(line, "staging", LOCKED_PIN[1])[:2]) for line in preamble_lines("staging")] == ["third-party check", "verify run", "plan record"], "the production gate runs for prod only"


def test_a_matching_installed_version_lets_the_staging_and_then_the_prod_job_through(tmp_path: Path) -> None:
    """Staging: every line passes and the job leaves its records; prod (after the evidence is committed, with the tag on the commit it was cut on): the gate line runs and passes too."""
    host = flow_host(tmp_path)
    git(host, "tag", "-a", "-m", f"release {TAG}", TAG)  # the cut (its own commands are the flow test's); by hand here
    staged = run_preamble(host, "staging")
    assert commands(staged) == ["third-party check", "verify run", "plan record"] and [item.code for item in staged] == [0, 0, 0], [item.out for item in staged]
    assert "installed 0.41.1 is the pin" in staged[0].out and "1 run, 1 passed, 0 failed" in staged[1].out and "done at staging" in staged[2].out
    assert deployed_files(host) == {"evd-argon2-staging-install.json", "evd-latency-staging.json", "dep-0001.json"}
    commit_all(host, "the evidence pull request, merged")
    prod = run_preamble(host, "prod")
    assert commands(prod) == ["third-party check", "release check", "verify run", "plan record"] and [item.code for item in prod] == [0, 0, 0, 0], [item.out for item in prod]
    assert "passes" in prod[1].out and f"release check --stage prod {TAG}" in prod[1].out
    assert deployed_files(host) >= {"evd-argon2-prod-install.json", "dep-0002.json"}


def test_third_party_check_installed_mismatch_stops_the_deploy_E339(tmp_path: Path) -> None:
    """A third party installed at another version than the pin: E339, exit 1, and not one later line of the preamble runs (no evidence, no deploy record)."""
    host = flow_host(tmp_path)
    git(host, "tag", "-a", "-m", f"release {TAG}", TAG)
    before = deployed_files(host)
    for env in ("staging", "prod"):
        ran = run_preamble(host, env, installed="0.42.0")
        assert len(ran) == 1 and ran[0].code == 1 and commands(ran) == ["third-party check"], [item.out for item in ran]
        assert "E339" in ran[0].out and f"'{LOCKED_PIN[0]}' is installed at '0.42.0' but the spec pin is '{LOCKED_PIN[1]}'" in ran[0].out
        assert deployed_files(host) == before, "the stopped job wrote nothing: no install evidence, no staging evidence, no at-deploy record"
    assert git(host, "status", "--porcelain") == ""


# --- spec-check --merge on the worked example ----------------------------------------------------------------------------------


def declare_pin(host: Path, lock_version: str) -> None:
    """The pin of ``tp-argon2`` (0.41.1) is declared to be the version in the host's ``package-lock.json``; the file says *lock_version*; committed."""
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": lock_version}}})
    write_json(host / "spec" / "common" / "host_declarations.json", {
        "$schema": "vc:host-declarations",
        "pin_sources": {"tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}]},
    })
    commit_all(host, f"the lock file says {lock_version}")


def merge_check(host: Path) -> str:
    """``spec-check --merge --base-ref main`` on *host* (the example has findings of its own, so the exit code is not what is read: the per-check lines are)."""
    _, out = run_on_example(host, "spec-check", str(host / "spec"), "--merge", "--base-ref", "main")
    return out


def check_line(out: str, name: str) -> str:
    [line] = [line for line in out.splitlines() if re.match(rf"\s*\[(PASS|FAIL|WARN|SKIP)\]\s+{re.escape(name)}\s", line)]
    return line.split()[0]


def test_merge_mode_runs_the_pin_check_on_the_graph_example(tmp_path: Path) -> None:
    """DOC 13.7 step 4: ``spec-check --merge`` reads the pin sources; a pin that differs from its declared source fails ``third-party-pins`` with E337, and passes when they agree."""
    host = git_copy_of_example(tmp_path / "host")
    git(host, "checkout", "-q", "-b", "feature")
    declare_pin(host, "0.41.1")
    out = merge_check(host)
    assert check_line(out, "third-party-pins") == "[PASS]", "the pin equals what its source reads"
    declare_pin(host, "0.40.0")
    out = merge_check(host)
    assert check_line(out, "third-party-pins") == "[FAIL]" and "E337" in out and "'0.41.1' of 'tp-argon2' differs from package-lock.json" in out and "'0.40.0'" in out
    declare_pin(host, "0.41.1")
    assert check_line(merge_check(host), "third-party-pins") == "[PASS]", "making them agree again clears it"


def test_the_step_02_gate_and_the_plain_run_report_a_pin_that_differs_from_its_source(tmp_path: Path) -> None:
    """The owner of E337 is step 02, so its own gate says it: ``--step 02`` blocks on it (it was ``CLEAR``), the plain run lists the ``third-party-pins`` check as failed, and the lock file edit alone (the pin unchanged) is a new finding against the commit before it."""
    host = git_copy_of_example(tmp_path / "host")
    git(host, "checkout", "-q", "-b", "feature")
    declare_pin(host, "0.41.1")
    _, plain = run_on_example(host, "spec-check", str(host / "spec"))
    assert check_line(plain, "third-party-pins") == "[PASS]"
    declare_pin(host, "0.40.0")
    _, gate = run_on_example(host, "spec-check", str(host / "spec"), "--step", "02", "--detail", "all", "--base-ref", "HEAD~1")
    assert "RESULT: CLEAR" not in gate and re.search(r"E337\s+\[02 own\]\s+tp-argon2", gate), gate
    _, plain = run_on_example(host, "spec-check", str(host / "spec"))
    assert check_line(plain, "third-party-pins") == "[FAIL]" and "E337" in plain


def test_the_step_02_gate_refuses_a_range_pin_of_a_third_party_with_no_declared_source(tmp_path: Path) -> None:
    """DOC L991: an exact pin always.  A third party that declares no ``pin_sources`` was not tested; its range pin is E336 at step 02 now."""
    host = git_copy_of_example(tmp_path / "host")
    git(host, "checkout", "-q", "-b", "feature")
    sketch = host / "spec" / "02_system_sketch.json"
    doc = json.loads(sketch.read_text(encoding="utf-8"))
    doc["third_parties"][0]["pin"] = "^0.41"
    write_json(sketch, doc)
    commit_all(host, "a range pin")
    _, gate = run_on_example(host, "spec-check", str(host / "spec"), "--step", "02", "--detail", "all", "--base-ref", "HEAD~1")
    assert re.search(r"E336\s+\[02 own\]\s+tp-argon2", gate) and "RESULT: CLEAR" not in gate, gate
    _, merge = run_on_example(host, "spec-check", str(host / "spec"), "--merge", "--base-ref", "main")
    assert check_line(merge, "third-party-pins") == "[FAIL]" and "E336" in merge
