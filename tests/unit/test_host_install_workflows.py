"""The workflow piece, the retired-command scan and the wrapper piece of the host installer (WI-M9-11c).

Fixture hosts under ``tests/fixtures/hosts/`` hold invented workflows: ``w`` calls retired commands (and has a GitHub
``matrix`` job strategy that must not count), ``p`` has its own CI with none.  A wrapper test runs the rendered
``run_specdev.sh`` against a fake venv, so no real venv and no network are needed.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import yaml

from specdev_tools import cli
from specdev_tools import host_install as hi
from unit._host_install_support import host, make_ctx as shared_make_ctx  # noqa: F401  (the fixture ``host``)

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "templates"
FIXTURES = REPO / "tests" / "fixtures" / "hosts"
WORKFLOW = ".github/workflows/specdev-merge-check.yml"
VERSION = "1.2.3"


def make_ctx(host: Path, *, venv: str = "devspec_env", dry_run: bool = False, adopt: bool = False, spec_rel: str = "spec", toolkit: Path | None = None) -> hi.InstallContext:
    (host / spec_rel).mkdir(parents=True, exist_ok=True)
    return shared_make_ctx(
        host, spec_dir=host / spec_rel, spec_rel=spec_rel, toolkit_root=toolkit or host / "devspec_toolkit", toolkit_version=VERSION,
        venv_prefix=host / venv, venv_name=venv, dry_run=dry_run, adopt=adopt,
    )


def make_ctx_live(host: Path, **kwargs) -> hi.InstallContext:
    """A context whose toolkit is the live repository (the wrapper templates live in its ``scripts/templates``)."""
    link = host / "devspec_toolkit"
    if not link.exists():
        link.symlink_to(REPO, target_is_directory=True)
    return make_ctx(host, **kwargs)


def declare(host: Path, **fields) -> None:
    (host / "spec" / "common").mkdir(parents=True, exist_ok=True)
    (host / "spec" / "common" / "host_declarations.json").write_text(json.dumps({"$schema": "vc:host-declarations", **fields}), encoding="utf-8")


def use_fixture(host: Path, name: str) -> None:
    shutil.copytree(FIXTURES / name / ".github", host / ".github")


def tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(root).parts}


class TestWorkflow:
    def test_workflow_installed_without_declarations(self, host):
        result = hi.install_workflows(make_ctx(host))
        assert result.status == hi.CREATED
        text = (host / WORKFLOW).read_text(encoding="utf-8")
        assert "specdev:setup-begin" not in text and "Host setup" not in text and "__SPECDEV_" not in text
        codes = [f.code for f in result.findings]
        assert codes == [hi.W_SETUP_UNDECLARED]
        finding = result.findings[0]
        assert finding.file == "spec/common/host_declarations.json" and "setup_command" in finding.text

    def test_setup_command_placeholder_substituted(self, host):
        declare(host, setup_command="npm ci")
        result = hi.install_workflows(make_ctx(host))
        assert result.status == hi.CREATED and result.findings == ()
        workflow = yaml.safe_load((host / WORKFLOW).read_text(encoding="utf-8"))
        for job in ("merge-check", "release-prep"):
            setup = [s for s in workflow["jobs"][job]["steps"] if s.get("name") == "Host setup"]
            assert [s["run"].strip() for s in setup] == ["npm ci"]

    def test_multi_line_setup_command_keeps_its_lines_in_the_block(self, host):
        declare(host, setup_command="npm ci\nnpm run build")
        hi.install_workflows(make_ctx(host))
        workflow = yaml.safe_load((host / WORKFLOW).read_text(encoding="utf-8"))
        setup = next(s for s in workflow["jobs"]["merge-check"]["steps"] if s.get("name") == "Host setup")
        assert setup["run"].splitlines() == ["npm ci", "npm run build"]

    def test_the_setup_command_is_not_rewritten_by_the_name_replacements(self, host):
        declare(host, setup_command="echo devspec_env devspec_toolkit")
        hi.install_workflows(make_ctx(host, venv=".venv"))
        assert "echo devspec_env devspec_toolkit" in (host / WORKFLOW).read_text(encoding="utf-8")

    def test_unreadable_declarations_are_refused_and_nothing_is_written(self, host):
        (host / "spec" / "common").mkdir(parents=True)
        (host / "spec" / "common" / "host_declarations.json").write_text("{not json", encoding="utf-8")
        result = hi.install_workflows(make_ctx(host))
        assert result.status == hi.REFUSED and result.findings[0].code == hi.W_INSTALL_REFUSED
        assert not (host / ".github").exists()

    def test_header_names_the_toolkit_version_and_reads_back(self, host):
        hi.install_workflows(make_ctx(host))
        text = (host / WORKFLOW).read_text(encoding="utf-8")
        assert hi.read_managed_header(text) == ("merge-check", VERSION)
        assert text.splitlines()[0] == hi.managed_header("merge-check", VERSION)

    def test_rendered_names_follow_the_host(self, host):
        result = hi.install_workflows(make_ctx(host, venv=".venv", spec_rel="docs/spec", toolkit=host / "vendor" / "devspec_toolkit"))
        assert result.status == hi.CREATED
        text = (host / WORKFLOW).read_text(encoding="utf-8")
        assert "uv venv .venv --python 3.13" in text and "uv pip install --python .venv/bin/python -e vendor/devspec_toolkit/tools/" in text
        assert "spec-check docs/spec --repo-root ./vendor/devspec_toolkit --spec-root ./docs/spec --git-root ." in text
        assert "git add -- docs/spec/extras/verification" in text
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        assert "devspec_env" not in code and "./devspec_toolkit" not in code
        assert " spec " not in code.replace("spec-check docs/spec", "") and "./spec " not in code

    def test_default_names_leave_the_template_text_as_it_is(self, host):
        declare(host, setup_command="make deps")
        hi.install_workflows(make_ctx(host, toolkit=host / "devspec_toolkit"))
        text = (host / WORKFLOW).read_text(encoding="utf-8")
        template = (TEMPLATES / "workflows" / "specdev-merge-check.yml").read_text(encoding="utf-8")
        code = lambda body: [line for line in body.splitlines() if not line.lstrip().startswith("#")]
        expected = [line.replace("__SPECDEV_SETUP_COMMAND__", "make deps").replace("__SPECDEV_TOOLKIT_VERSION__", VERSION) for line in code(template)]
        assert code(text) == expected and "__SPECDEV_" not in text
        assert "specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root . --merge" in text

    def test_rendered_workflow_passes_the_template_checks(self, host):
        """The rendered file, with and without a setup command: no placeholder, YAML parses, every specdev line parses."""
        for fields in ({}, {"setup_command": "make deps"}):
            for stale in (host / ".github").glob("**/*") if (host / ".github").exists() else ():
                stale.unlink() if stale.is_file() else None
            if fields:
                declare(host, **fields)
            hi.install_workflows(make_ctx(host))
            text = (host / WORKFLOW).read_text(encoding="utf-8")
            assert not re.search(r"__SPECDEV_[A-Z_]+__", text)
            document = yaml.safe_load(text)
            lines = [
                line.strip()
                for job in document["jobs"].values()
                for step in job["steps"]
                if isinstance(step.get("run"), str)
                for line in step["run"].splitlines()
                if line.strip().startswith("specdev ")
            ]
            assert len(lines) >= 5
            samples = {"BASE": "main", "BEFORE": "0" * 40, "PR_TITLE": "feat: a", "HEAD_REF": "release-prep/x"}
            for line in lines:
                argv = shlex.split(re.sub(r"\$\{?([A-Z_]+)\}?", lambda m: samples[m.group(1)], line))[1:]
                cli.build_parser().parse_args(argv)

    def test_rendered_workflow_runs_spec_check_and_no_retired_command(self, host):
        """What the deleted ``TestCiWorkflowRender`` asserted of the init workflow, asserted of the rendered one."""
        hi.install_workflows(make_ctx(host))
        text = (host / WORKFLOW).read_text(encoding="utf-8")
        assert "spec-check" in text and "--spec-root ./spec" in text and "--git-root ." in text
        assert not hi.retired_command_findings(host)
        assert "validate-all" not in text and "trace_matrix" not in text and "upload-artifact" not in text

    def test_workflow_marked_file_refreshed_unmarked_untouched(self, host):
        first = hi.install_workflows(make_ctx(host))
        assert first.status == hi.CREATED
        # a marked file of an older toolkit version is rewritten, and so is a hand-edited managed file
        path = host / WORKFLOW
        path.write_text(path.read_text(encoding="utf-8").replace(f"toolkit={VERSION}", "toolkit=0.9.0") + "# edited\n", encoding="utf-8")
        assert hi.install_workflows(make_ctx(host)).status == hi.REFRESHED
        assert hi.read_managed_header(path.read_text(encoding="utf-8")) == ("merge-check", VERSION)
        assert "# edited" not in path.read_text(encoding="utf-8")
        # a host file of the same name without the header is drift and is not touched, also under --adopt
        own = "name: mine\non: push\njobs: {}\n"
        path.write_text(own, encoding="utf-8")
        for adopt in (False, True):
            result = hi.install_workflows(make_ctx(host, adopt=adopt))
            assert result.status == hi.DRIFT and path.read_text(encoding="utf-8") == own
            assert [(f.code, f.file) for f in result.findings if f.code == hi.W_TEMPLATE_DRIFT] == [(hi.W_TEMPLATE_DRIFT, WORKFLOW)]

    def test_a_file_with_another_pieces_header_is_the_hosts(self, host):
        path = host / WORKFLOW
        path.parent.mkdir(parents=True)
        path.write_text("# specdev-managed: other toolkit=1.0.0\nname: x\n", encoding="utf-8")
        assert hi.install_workflows(make_ctx(host)).status == hi.DRIFT

    def test_second_run_is_current_and_changes_no_byte(self, host):
        declare(host, setup_command="npm ci")
        use_fixture(host, "w")
        hi.install_workflows(make_ctx(host))
        before = tree(host)
        again = hi.install_workflows(make_ctx(host))
        assert again.status == hi.CURRENT and tree(host) == before

    def test_dry_run_writes_nothing(self, host):
        use_fixture(host, "w")
        before = tree(host)
        result = hi.install_workflows(make_ctx(host, dry_run=True))
        assert result.status == hi.WOULD_INSTALL and tree(host) == before and not (host / WORKFLOW).exists()

    def test_missing_template_is_refused(self, host):
        ctx = make_ctx(host)
        ctx = hi.InstallContext(**{**ctx.__dict__, "templates_dir": host / "no-templates"})
        result = hi.install_workflows(ctx)
        assert result.status == hi.REFUSED and not (host / ".github").exists()

    def test_the_three_snippets_are_not_installed(self, host):
        hi.install_workflows(make_ctx(host))
        assert sorted(p.name for p in (host / ".github" / "workflows").iterdir()) == ["specdev-merge-check.yml"]


class TestRetiredCommands:
    def test_retired_command_reported_W932(self, host):
        use_fixture(host, "w")
        found = hi.retired_command_findings(host)
        assert {f.code for f in found} == {hi.W_RETIRED_COMMAND}
        by_command = {(f.file, f.line, f.command) for f in found}
        spec_validation = ".github/workflows/spec_validation.yml"
        text = (host / spec_validation).read_text(encoding="utf-8").splitlines()
        line_of = lambda needle: next(i for i, line in enumerate(text, 1) if needle in line and not line.strip().startswith("#"))
        assert (spec_validation, line_of("validate-all"), "validate-all") in by_command
        assert (spec_validation, line_of("cli matrix"), "matrix") in by_command
        assert (spec_validation, line_of("--output trace_matrix.json"), "trace_matrix.json") in by_command
        assert (spec_validation, line_of("path: spec/trace_matrix.json"), "trace_matrix.json") in by_command
        assert len(found) == 4
        pointers = {f.command: f.text for f in found}
        assert "superseded by `specdev spec-check`" in pointers["validate-all"]
        assert cli.REMOVED_COMMANDS["matrix"] in pointers["matrix"]

    def test_a_job_matrix_strategy_is_not_the_matrix_command(self, host):
        use_fixture(host, "w")
        text = (host / ".github/workflows/spec_validation.yml").read_text(encoding="utf-8").splitlines()
        strategy_line = next(i for i, line in enumerate(text, 1) if line.strip() == "matrix:")
        assert strategy_line not in {f.line for f in hi.retired_command_findings(host)}

    def test_validate_all_of_a_host_whose_ci_calls_it(self, host):
        workflows = host / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yaml").write_text("jobs:\n  a:\n    steps:\n      - run: specdev validate-all spec --repo-root ./t\n", encoding="utf-8")
        found = hi.retired_command_findings(host)
        assert [(f.file, f.line, f.command) for f in found] == [(".github/workflows/ci.yaml", 4, "validate-all")]

    def test_every_retired_key_of_the_cli_is_found_and_dag_lint_is_not(self, host):
        workflows = host / ".github" / "workflows"
        workflows.mkdir(parents=True)
        calls = [*cli.REMOVED_COMMANDS, "dag-lint", "spec-check"]
        body = "".join(f"      - run: ./tools/run_specdev.sh {name} spec\n" for name in calls)
        (workflows / "ci.yml").write_text("jobs:\n  a:\n    steps:\n" + body, encoding="utf-8")
        found = {f.command for f in hi.retired_command_findings(host)}
        assert found == set(cli.REMOVED_COMMANDS)

    def test_a_comment_line_is_not_a_call_and_a_clean_host_has_no_finding(self, host):
        use_fixture(host, "p")
        assert hi.retired_command_findings(host) == []

    def test_a_file_the_installer_renders_is_not_scanned(self, host):
        workflows = host / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "specdev-merge-check.yml").write_text(f"{hi.managed_header('merge-check', VERSION)}\n- run: specdev matrix\n", encoding="utf-8")
        assert hi.retired_command_findings(host) == []

    def test_pre_commit_config_is_scanned_outside_the_marked_block_only(self, host):
        (host / ".pre-commit-config.yaml").write_text(
            "repos:\n  - repo: local\n    hooks:\n      - id: old\n        entry: specdev validate-all spec\n"
            "      # >>> specdev-managed\n      - id: new\n        entry: specdev matrix spec\n      # <<< specdev-managed\n",
            encoding="utf-8",
        )
        found = hi.retired_command_findings(host)
        assert [(f.file, f.line, f.command) for f in found] == [(".pre-commit-config.yaml", 5, "validate-all")]

    def test_the_table_can_be_passed_in(self, host):
        workflows = host / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("run: specdev old-thing\n", encoding="utf-8")
        found = hi.retired_command_findings(host, removed_commands={"old-thing": "use `new-thing`"})
        assert [(f.command, f.text) for f in found] == [("old-thing", "'old-thing' was removed in 1.2.0; use `new-thing`")]

    def test_the_warning_string_carries_file_line_and_replacement(self, host):
        use_fixture(host, "w")
        rendered = [f.render() for f in hi.retired_command_findings(host)]
        assert any(r.startswith("W932 HOST_RETIRED_COMMAND: .github/workflows/spec_validation.yml:") and "validate-all" in r for r in rendered)

    def test_adopt_does_not_touch_workflows(self, host):
        use_fixture(host, "w")
        declare(host, setup_command="npm ci")
        before = tree(host / ".github")
        for adopt in (False, True):
            result = hi.install_workflows(make_ctx(host, adopt=adopt))
            assert {f.code for f in result.findings} == {hi.W_RETIRED_COMMAND}
        after = tree(host / ".github")
        assert {k: v for k, v in after.items() if not k.endswith("specdev-merge-check.yml")} == before

    def test_the_scan_rides_on_the_piece_and_leaves_its_status(self, host):
        use_fixture(host, "w")
        hi.install_workflows(make_ctx(host))
        again = hi.install_workflows(make_ctx(host))
        assert again.status == hi.CURRENT and {f.code for f in again.findings} == {hi.W_RETIRED_COMMAND, hi.W_SETUP_UNDECLARED}


class TestWrappers:
    def test_wrappers_written_with_the_venv_name_and_mode(self, host):
        result = hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        assert result.status == hi.CREATED and result.findings == ()
        script = host / "tools" / "run_specdev.sh"
        assert 'VENV_DIR="${ROOT}/.venv"' in script.read_text(encoding="utf-8") and "devspec_env" not in script.read_text(encoding="utf-8")
        assert os.access(script, os.X_OK)
        assert "Activate .venv" in (host / "tools" / "ensure_venv.py").read_text(encoding="utf-8")

    def test_the_rendered_wrapper_activates_the_hosts_venv(self, host):
        """Run the rendered wrapper with a fake venv named ``.venv``: the interpreter and the CLI it runs are that venv's."""
        hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        bin_dir = host / ".venv" / "bin"
        bin_dir.mkdir(parents=True)
        shim = bin_dir / "python3"
        shim.write_text("#!/bin/sh\necho \"shim:$0 $*\"\n", encoding="utf-8")
        shim.chmod(0o755)
        done = subprocess.run([str(host / "tools" / "run_specdev.sh"), "status"], capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr
        lines = done.stdout.splitlines()
        assert lines[-1] == f"shim:{host}/.venv/bin/python3 -m specdev_tools.cli status"
        assert lines[0].startswith(f"shim:{host}/.venv/bin/python3 {host}/tools/ensure_venv.py")

    def test_a_missing_venv_names_the_hosts_venv(self, host):
        hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        done = subprocess.run([str(host / "tools" / "run_specdev.sh")], capture_output=True, text=True, check=False)
        assert done.returncode == 1 and "Error: .venv virtual environment not found" in done.stderr

    def test_the_default_venv_gives_the_template_byte_for_byte(self, host):
        hi.install_wrappers(make_ctx_live(host, venv="devspec_env"))
        for name in ("run_specdev.sh", "ensure_venv.py"):
            assert (host / "tools" / name).read_bytes() == (REPO / "scripts" / "templates" / name).read_bytes()

    def test_a_copy_made_by_init_is_refreshed_not_drift(self, host):
        """``init`` copies the unrendered template before the venv name is known; the installer renders it without asking."""
        (host / "tools").mkdir()
        shutil.copy2(REPO / "scripts" / "templates" / "run_specdev.sh", host / "tools" / "run_specdev.sh")
        shutil.copy2(REPO / "scripts" / "templates" / "ensure_venv.py", host / "tools" / "ensure_venv.py")
        result = hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        assert result.status == hi.REFRESHED and result.findings == ()
        assert hi.install_wrappers(make_ctx_live(host, venv=".venv")).status == hi.CURRENT

    def test_wrapper_drift_reported_W930_and_adopt_rewrites(self, host):
        hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        script = host / "tools" / "run_specdev.sh"
        edited = script.read_text(encoding="utf-8").replace("exec ", "echo mine\nexec ")
        script.write_text(edited, encoding="utf-8")
        plain = hi.install_wrappers(make_ctx_live(host, venv=".venv"))
        assert plain.status == hi.DRIFT and script.read_text(encoding="utf-8") == edited
        assert [(f.code, f.file) for f in plain.findings] == [(hi.W_TEMPLATE_DRIFT, "tools/run_specdev.sh")]
        assert "+exec" not in plain.findings[0].text and "-echo mine" in plain.findings[0].text
        dry = hi.install_wrappers(make_ctx_live(host, venv=".venv", adopt=True, dry_run=True))
        assert dry.status == hi.WOULD_INSTALL and script.read_text(encoding="utf-8") == edited
        adopted = hi.install_wrappers(make_ctx_live(host, venv=".venv", adopt=True))
        assert adopted.status == hi.REFRESHED and "echo mine" not in script.read_text(encoding="utf-8") and os.access(script, os.X_OK)
        assert hi.install_wrappers(make_ctx_live(host, venv=".venv")).status == hi.CURRENT

    def test_dry_run_writes_nothing(self, host):
        result = hi.install_wrappers(make_ctx_live(host, dry_run=True))
        assert result.status == hi.WOULD_INSTALL and not (host / "tools").exists()

    def test_a_missing_wrapper_template_is_refused(self, host):
        result = hi.install_wrappers(make_ctx(host))  # the toolkit folder of this context has no scripts/templates
        assert result.status == hi.REFUSED and not (host / "tools").exists()


class TestRegistry:
    def test_the_pieces_of_parts_a_to_c(self):
        assert [p.name for p in hi.PIECES][:4] == ["pre-commit", "merge-driver", "workflows", "wrappers"]

    def test_the_four_pieces_run_through_the_registry_twice(self, host, monkeypatch):
        monkeypatch.setattr(hi, "_run_pre_commit_install", lambda binary, root: (0, ""))
        toolkit = host / "devspec_toolkit"
        shutil.copytree(REPO / "scripts" / "templates", toolkit / "scripts" / "templates")
        shutil.copytree(TEMPLATES, toolkit / "templates")
        (toolkit / "tools").mkdir()
        shutil.copy2(REPO / "tools" / "pyproject.toml", toolkit / "tools" / "pyproject.toml")
        for name in ("CHANGELOG.md",):
            if (REPO / name).is_file():
                shutil.copy2(REPO / name, toolkit / name)
        use_fixture(host, "w")
        first = hi.run_host_install(host / "spec", toolkit, git_root=host)
        statuses = {name: result.status for name, result in first.pieces}
        assert statuses["workflows"] == hi.CREATED and statuses["wrappers"] == hi.CREATED
        before = tree(host)
        second = hi.run_host_install(host / "spec", toolkit, git_root=host)
        assert {name: result.status for name, result in second.pieces}["workflows"] == hi.CURRENT
        assert {name: result.status for name, result in second.pieces}["wrappers"] == hi.CURRENT
        assert tree(host) == before
