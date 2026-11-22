"""The pre-commit piece of the host installer: the template renderer, the marked block, drift and ``--adopt``.

Fixture hosts under ``tests/fixtures/hosts/`` hold invented configs: ``w`` has hand-written toolkit hooks among the
host's own, ``p`` has none (and a different indentation).  No test runs a real ``pre-commit install``: the runner is
replaced the way a test replaces any command.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from specdev_tools import host_install as hi
from unit._host_install_support import host, make_ctx as shared_make_ctx  # noqa: F401  (the fixture ``host``)

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "templates"
FIXTURES = REPO / "tests" / "fixtures" / "hosts"
CONFIG = ".pre-commit-config.yaml"
SPEC_CHECK_ENTRY_TAIL = "spec-check spec --repo-root ./{root} --spec-root ./spec --git-root . --paths"


@pytest.fixture
def pre_commit_runs(monkeypatch) -> list[tuple[Path, Path]]:
    """Replace the pre-commit runner; the list records (binary, host root) of every call, the exit code is ``exit_code[0]``."""
    runs: list[tuple[Path, Path]] = []
    monkeypatch.setattr(hi, "_run_pre_commit_install", lambda binary, root: (runs.append((binary, root)) or (0, "installed")))
    return runs


def make_ctx(host: Path, *, venv: str = ".venv", dry_run: bool = False, adopt: bool = False, with_binary: bool = True) -> hi.InstallContext:
    prefix = host / venv
    if with_binary:
        (prefix / "bin").mkdir(parents=True, exist_ok=True)
        (prefix / "bin" / "pre-commit").write_text("#!/bin/sh\n")
    return shared_make_ctx(host, venv_prefix=prefix, venv_name=venv, dry_run=dry_run, adopt=adopt)


def use_fixture(host: Path, name: str) -> str:
    text = (FIXTURES / name / CONFIG).read_text(encoding="utf-8")
    (host / CONFIG).write_text(text, encoding="utf-8")
    return text


def hook_ids(text: str) -> list[str]:
    return [h.id for h in hi.enumerate_pre_commit_hooks(text)]


def template_ids() -> list[str]:
    return hook_ids((TEMPLATES / "pre-commit-config.host.yaml").read_text(encoding="utf-8"))


def outside_block(text: str) -> tuple[str, str]:
    before, _, after = hi.split_marked_block(text)
    return before, after


class TestRenderer:
    """The cases of the old ``TestBuildPreCommitConfig`` (``init_project._build_pre_commit_config``), on the installer's renderer."""

    @staticmethod
    def render(root: str, venv: str = "devspec_env") -> str:
        return hi.render_pre_commit_template(root, venv, TEMPLATES)

    @staticmethod
    def spec_check(content: str) -> dict:
        return next(h for h in yaml.safe_load(content)["repos"][0]["hooks"] if h["id"] == "spec-check")

    def test_repo_root_flag_present(self):
        assert "--repo-root ./devspec_toolkit" in self.render("devspec_toolkit")

    def test_custom_toolkit_path(self):
        assert "--repo-root ./custom/path" in self.render("custom/path")

    @pytest.mark.parametrize(
        "hook",
        [
            "spec-check", "canonical-lint", "seed-lint", "dependency-order-lint", "dag-lint",
            "extraction-intent-check", "canon-schema-alignment", "canonical-integrity",
        ],
    )
    def test_contains_the_template_hook(self, hook):
        assert hook in self.render("devspec_toolkit")

    def test_path_substitution_applied(self):
        content = self.render("my_toolkit")
        assert "./devspec_toolkit" not in content
        assert "devspec_toolkit/" not in content
        assert "./my_toolkit" in content
        assert "my_toolkit/" in content

    def test_missing_template_gives_the_minimal_config(self):
        content = hi.render_pre_commit_template("devspec_toolkit", "devspec_env", None)
        assert "spec-check" in content
        assert "devspec_env/bin/python" in content
        assert "--repo-root ./devspec_toolkit" in content
        assert "--spec-root ./spec" in content
        assert "--git-root ." in content

    def test_missing_template_file_in_an_existing_folder_gives_the_minimal_config(self, tmp_path):
        assert hi.render_pre_commit_template("tk", "v", tmp_path) == hi.render_pre_commit_template("tk", "v", None)

    def test_custom_venv_name_propagates(self):
        content = self.render("devspec_toolkit", "customenv")
        assert "customenv/bin/python" in content
        assert "devspec_env/bin/python" not in content

    def test_spec_check_hook_ends_with_paths_takes_filenames_and_has_no_files_filter(self):
        hook = self.spec_check(self.render("devspec_toolkit"))
        assert hook["entry"].endswith(" --paths")
        assert hook["pass_filenames"] is True
        assert hook["require_serial"] is True
        assert "files" not in hook

    @pytest.mark.parametrize("root", ["devspec_toolkit", "custom/path", "my_toolkit"])
    def test_custom_toolkit_root_is_substituted_in_the_spec_check_entry(self, root):
        assert self.spec_check(self.render(root))["entry"] == (
            "devspec_env/bin/python -m specdev_tools.cli " + SPEC_CHECK_ENTRY_TAIL.format(root=root)
        )

    def test_fallback_hook_also_ends_with_paths(self):
        hook = self.spec_check(hi.render_pre_commit_template("my_toolkit", "venv2", None))
        assert hook["entry"] == "venv2/bin/python -m specdev_tools.cli " + SPEC_CHECK_ENTRY_TAIL.format(root="my_toolkit")
        assert hook["pass_filenames"] is True
        assert "files" not in hook

    def test_seed_lint_hook_keeps_its_files_filter(self):
        hooks = yaml.safe_load(self.render("devspec_toolkit"))["repos"][0]["hooks"]
        seed_lint = next(h for h in hooks if h["id"] == "seed-lint")
        assert seed_lint["files"] == r"spec/.*\.json$"
        assert seed_lint["pass_filenames"] is False


class TestToolkitPath:
    def test_the_toolkit_folder_is_relative_to_the_host_through_a_symlinked_parent(self, tmp_path):
        real = tmp_path / "real"
        (real / "host" / "devspec_toolkit").mkdir(parents=True)
        (tmp_path / "link").symlink_to(real)
        ctx = make_ctx(real / "host")
        ctx = hi.InstallContext(**{**ctx.__dict__, "toolkit_root": tmp_path / "link" / "host" / "devspec_toolkit"})
        assert ctx.toolkit_rel == "devspec_toolkit"

    def test_a_relative_toolkit_path_given_from_the_host_root(self, host, monkeypatch):
        (host / "vendor" / "tk").mkdir(parents=True)
        monkeypatch.chdir(host)
        ctx = make_ctx(host)
        assert hi.InstallContext(**{**ctx.__dict__, "toolkit_root": Path("vendor/tk")}).toolkit_rel == "vendor/tk"


class TestEnumeration:
    def test_precommit_enumeration_parses_current_template_and_w_p_fixtures(self):
        template = hi.enumerate_pre_commit_hooks((TEMPLATES / "pre-commit-config.host.yaml").read_text(encoding="utf-8"))
        w = hi.enumerate_pre_commit_hooks((FIXTURES / "w" / CONFIG).read_text(encoding="utf-8"))
        p = hi.enumerate_pre_commit_hooks((FIXTURES / "p" / CONFIG).read_text(encoding="utf-8"))
        assert [h.id for h in template][:3] == ["dag-lint", "extraction-intent-check", "spec-check"]
        assert [h.id for h in w] == ["web-format", "spec-check", "seed-lint", "web-unit"]
        assert [h.id for h in p] == ["secret-scan", "service-lint"]  # the remote repo's hook is not a local hook

    def test_spans_are_one_based_and_exclude_the_comment_lines_between_hooks(self):
        text = (FIXTURES / "w" / CONFIG).read_text(encoding="utf-8")
        lines = text.splitlines()
        spec_check = next(h for h in hi.enumerate_pre_commit_hooks(text) if h.id == "spec-check")
        assert lines[spec_check.start - 1].strip() == "- id: spec-check"
        assert lines[spec_check.end - 1].strip() == "types: [file]"
        assert lines[spec_check.start - 2].strip().startswith("# hand-written copy")

    def test_absent_fields_hold_pre_commit_defaults(self):
        hook = hi.enumerate_pre_commit_hooks("repos:\n  - repo: local\n    hooks:\n      - id: a\n        entry: x\n")[0]
        assert (hook.pass_filenames, hook.require_serial, hook.types, hook.files) == (True, False, ("file",), None)

    def test_the_hook_runs_the_subcommand_it_names(self):
        text = (TEMPLATES / "pre-commit-config.host.yaml").read_text(encoding="utf-8")
        assert {h.id: h.subcommand for h in hi.enumerate_pre_commit_hooks(text)}["seed-lint"] == "seed-lint"
        assert hi.enumerate_pre_commit_hooks((FIXTURES / "p" / CONFIG).read_text())[0].subcommand is None

    def test_precommit_template_hooks_enumerated_from_real_m6a_template(self, host, pre_commit_runs):
        result = hi.install_pre_commit(make_ctx(host))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.CREATED
        assert hook_ids(text) == template_ids()
        before, inside, after = hi.split_marked_block(text)
        assert hi.replace_marked_block(text, inside) == text
        assert hook_ids(before + inside + after) == template_ids()


class TestAbsentConfig:
    def test_precommit_absent_written_with_markers(self, host, pre_commit_runs):
        result = hi.install_pre_commit(make_ctx(host))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.CREATED and result.findings == ()
        assert text.count(hi.MARKER_BEGIN) == 1 and text.count(hi.MARKER_END) == 1
        assert text.index(hi.MARKER_BEGIN) < text.index("- id: dag-lint") < text.index("- id: spec-check") < text.index(hi.MARKER_END)
        assert "--repo-root ./devspec_toolkit" in text
        assert text.startswith("# Pre-commit hooks for host repos")
        assert yaml.safe_load(text)["repos"][0]["repo"] == "local"

    def test_the_git_hook_is_installed_once_by_the_venv_pre_commit(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        hi.install_pre_commit(ctx)
        assert pre_commit_runs == [(ctx.venv_bin / "pre-commit", host)]

    def test_second_run_is_current_and_writes_nothing(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        hi.install_pre_commit(ctx)
        first = (host / CONFIG).read_bytes()
        again = hi.install_pre_commit(ctx)
        assert again.status == hi.CURRENT and again.findings == ()
        assert (host / CONFIG).read_bytes() == first

    def test_dry_run_writes_nothing_and_runs_no_command(self, host, pre_commit_runs):
        result = hi.install_pre_commit(make_ctx(host, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert not (host / CONFIG).exists()
        assert pre_commit_runs == []

    def test_dry_run_of_a_current_file_says_current(self, host, pre_commit_runs):
        hi.install_pre_commit(make_ctx(host))
        assert hi.install_pre_commit(make_ctx(host, dry_run=True)).status == hi.CURRENT

    @pytest.mark.parametrize("venv", [".venv", "devspec_env"])
    def test_every_path_that_names_the_venv_uses_the_context_venv_name(self, host, pre_commit_runs, venv):
        hi.install_pre_commit(make_ctx(host, venv=venv))
        entries = [h.entry for h in hi.enumerate_pre_commit_hooks((host / CONFIG).read_text(encoding="utf-8"))]
        assert entries and all(e.startswith(f"{venv}/bin/python -m specdev_tools.cli ") for e in entries)
        other = "devspec_env" if venv == ".venv" else ".venv"
        assert f"{other}/bin" not in (host / CONFIG).read_text(encoding="utf-8")

    def test_an_empty_file_is_treated_as_absent(self, host, pre_commit_runs):
        (host / CONFIG).write_text("\n", encoding="utf-8")
        assert hi.install_pre_commit(make_ctx(host)).status == hi.REFRESHED
        assert hook_ids((host / CONFIG).read_text(encoding="utf-8")) == template_ids()

    def test_the_minimal_config_is_written_when_the_template_is_missing(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        ctx = hi.InstallContext(**{**ctx.__dict__, "templates_dir": host / "no-templates"})
        assert hi.install_pre_commit(ctx).status == hi.CREATED
        assert hook_ids((host / CONFIG).read_text(encoding="utf-8")) == ["spec-check"]


class TestMarkedBlock:
    def test_precommit_marked_block_replaced_other_lines_untouched(self, host, pre_commit_runs):
        host_lines_before = "# my hooks\nrepos:\n  - repo: https://example.invalid/x\n    rev: v1\n    hooks:\n      - id: x\n\n"
        stale = (
            "  - repo: local\n    hooks:\n      # a comment of the host\n      - id: web-format\n        entry: npm run format\n"
            f"      {hi.MARKER_BEGIN}\n      - id: spec-check\n        entry: old\n      {hi.MARKER_END}\n"
            "      - id: web-unit\n        entry: npm test\n# trailing host comment\n"
        )
        (host / CONFIG).write_text(host_lines_before + stale, encoding="utf-8")
        result = hi.install_pre_commit(make_ctx(host))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.REFRESHED
        before_old, after_old = outside_block(host_lines_before + stale)
        before_new, after_new = outside_block(text)
        assert (before_new, after_new) == (before_old, after_old)
        assert hook_ids(text) == ["web-format", *template_ids(), "web-unit"]

    def test_a_block_at_another_indentation_is_refreshed_at_that_indentation(self, host, pre_commit_runs):
        (host / CONFIG).write_text(
            f"repos:\n- repo: local\n  hooks:\n  {hi.MARKER_BEGIN}\n  - id: old\n    entry: x\n  {hi.MARKER_END}\n", encoding="utf-8"
        )
        hi.install_pre_commit(make_ctx(host))
        hooks = hi.enumerate_pre_commit_hooks((host / CONFIG).read_text(encoding="utf-8"))
        assert [h.id for h in hooks] == template_ids() and {h.col for h in hooks} == {2}

    def test_a_current_block_is_current_with_no_write(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        hi.install_pre_commit(ctx)
        text = (host / CONFIG).read_text(encoding="utf-8")
        (host / CONFIG).write_text(text, encoding="utf-8")
        assert hi.install_pre_commit(ctx).status == hi.CURRENT

    def test_an_edit_between_the_markers_is_overwritten_not_reported(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        hi.install_pre_commit(ctx)
        text = (host / CONFIG).read_text(encoding="utf-8").replace("language: system", "language: python", 1)
        (host / CONFIG).write_text(text, encoding="utf-8")
        result = hi.install_pre_commit(ctx)
        assert result.status == hi.REFRESHED and result.findings == ()
        assert "language: python" not in (host / CONFIG).read_text(encoding="utf-8")

    def test_damaged_markers_are_refused_and_the_file_is_untouched(self, host, pre_commit_runs):
        damaged = f"repos:\n  - repo: local\n    hooks:\n      {hi.MARKER_BEGIN}\n      - id: a\n"
        (host / CONFIG).write_text(damaged, encoding="utf-8")
        result = hi.install_pre_commit(make_ctx(host))
        assert result.status == hi.REFUSED and result.findings[0].code == "W931" and result.findings[0].file == CONFIG
        assert (host / CONFIG).read_text(encoding="utf-8") == damaged
        assert pre_commit_runs == []

    def test_update_after_init_strict_preserves_commit_msg_hook(self, host, pre_commit_runs):
        ctx = make_ctx(host)
        hi.install_pre_commit(ctx)
        governance = (
            "      - id: devspec-governance\n        name: DevSpec Governance Check\n"
            "        entry: .venv/bin/python -m specdev_tools.cli governance-check spec --repo-root ./devspec_toolkit --message\n"
            "        language: system\n        pass_filenames: true\n        stages: [commit-msg]\n"
        )
        with (host / CONFIG).open("a", encoding="utf-8") as handle:  # what `init --strict` appends after the delegate
            handle.write(governance)
        again = hi.install_pre_commit(ctx)
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert again.status == hi.CURRENT and text.endswith(governance)
        # a stale block is refreshed and the appended hook still survives
        (host / CONFIG).write_text(text.replace("seed-lint spec", "seed-lint old"), encoding="utf-8")
        assert hi.install_pre_commit(ctx).status == hi.REFRESHED
        assert (host / CONFIG).read_text(encoding="utf-8").endswith(governance)
        assert "devspec-governance" in hook_ids((host / CONFIG).read_text(encoding="utf-8"))


class TestHandWrittenHooks:
    def test_precommit_unmarked_reports_drift_and_does_not_rewrite(self, host, pre_commit_runs):
        original = use_fixture(host, "w")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env"))
        assert result.status == hi.DRIFT
        assert (host / CONFIG).read_text(encoding="utf-8") == original
        assert {f.code for f in result.findings} == {"W930"}
        lines = original.splitlines()
        for finding in result.findings:
            assert finding.file == CONFIG and finding.line is not None and finding.line <= len(lines)
            assert "specdev update --adopt" in finding.text
        by_line = {f.line: f for f in result.findings if "differs" in f.text}
        spec_check_line = lines.index("      - id: spec-check") + 1
        seed_lint_line = lines.index("      - id: seed-lint") + 1
        assert spec_check_line in by_line and seed_lint_line not in by_line  # seed-lint matches the template

    def test_precommit_old_full_run_spec_check_hook_reported_as_drift(self, host, pre_commit_runs):
        original = use_fixture(host, "w")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env"))
        spec_check = next(f for f in result.findings if f.command == "spec-check")
        assert spec_check.line == original.splitlines().index("      - id: spec-check") + 1
        assert "differs from the template in entry, files, pass_filenames, require_serial" in spec_check.text
        assert "- id: spec-check" in spec_check.text and spec_check.text.rstrip().endswith("types: [file]")
        assert spec_check.render().startswith(f"W930 HOST_TEMPLATE_DRIFT: {CONFIG}:{spec_check.line}: ")

    def test_template_hooks_the_host_lacks_are_one_finding_at_the_first_matched_hook(self, host, pre_commit_runs):
        original = use_fixture(host, "w")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env"))
        missing = [f for f in result.findings if "not in the config" in f.text]
        assert len(missing) == 1
        assert missing[0].line == original.splitlines().index("      - id: spec-check") + 1
        listed = re.search(r"config: (.*?); ", missing[0].text)[1].split(", ")
        assert listed == [i for i in template_ids() if i not in {"spec-check", "seed-lint"}]

    def test_a_hand_written_hook_equal_to_the_template_is_current(self, host, pre_commit_runs):
        ctx = make_ctx(host, venv="devspec_env")
        rendered = hi.render_pre_commit_template("devspec_toolkit", "devspec_env", TEMPLATES)
        (host / CONFIG).write_text(rendered, encoding="utf-8")
        result = hi.install_pre_commit(ctx)
        assert result.status == hi.CURRENT and result.findings == ()
        assert (host / CONFIG).read_text(encoding="utf-8") == rendered

    def test_precommit_adopt_rewrites_only_matching_hooks_and_keeps_comments(self, host, pre_commit_runs):
        original = use_fixture(host, "w")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env", adopt=True))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.REFRESHED and result.findings == ()
        assert text.count(hi.MARKER_BEGIN) == 1
        assert hook_ids(text) == ["web-format", *template_ids(), "web-unit"]
        # the block sits where the first matched hook was, and the host's own text outside the replaced spans is untouched
        for comment in ("# Invented fixture", "# hand-written copy of the step gate", "# unit tests of the web code run last", "# the formatter of the web code"):
            assert any(comment in line for line in text.splitlines())
        before, after = outside_block(text)
        assert "- id: web-format" in before and "- id: web-unit" in after and "- id: trailing-whitespace" in before
        # every original line that is not part of a replaced hook is still there, in order
        removed_ranges = []
        for hook in hi.enumerate_pre_commit_hooks(original):
            if hook.id in {"spec-check", "seed-lint"}:
                removed_ranges.append(range(hook.start, hook.end + 1))
        survivors = [line for n, line in enumerate(original.splitlines(), 1) if not any(n in r for r in removed_ranges)]
        it = iter(text.splitlines())
        assert all(line in it for line in survivors)

    def test_adopt_then_a_plain_update_is_current_and_takes_later_toolkit_changes(self, host, pre_commit_runs):
        use_fixture(host, "w")
        hi.install_pre_commit(make_ctx(host, venv="devspec_env", adopt=True))
        assert hi.install_pre_commit(make_ctx(host, venv="devspec_env")).status == hi.CURRENT
        assert hi.install_pre_commit(make_ctx(host, venv="devspec_env", adopt=True)).status == hi.CURRENT

    def test_adopt_dry_run_writes_nothing(self, host, pre_commit_runs):
        original = use_fixture(host, "w")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env", adopt=True, dry_run=True))
        assert result.status == hi.WOULD_INSTALL
        assert (host / CONFIG).read_text(encoding="utf-8") == original
        assert pre_commit_runs == []

    def test_host_hooks_of_a_remote_repo_with_a_template_id_are_not_matched(self, host, pre_commit_runs):
        original = "repos:\n  - repo: https://example.invalid/x\n    rev: v1\n    hooks:\n      - id: spec-check\n"
        (host / CONFIG).write_text(original, encoding="utf-8")
        result = hi.install_pre_commit(make_ctx(host, venv="devspec_env"))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.CREATED or result.status == hi.REFRESHED
        assert text.startswith(original) and hook_ids(text) == template_ids()


class TestConfigWithoutToolkitHooks:
    def test_the_block_is_appended_after_the_last_local_hook_keeping_every_host_line(self, host, pre_commit_runs):
        original = use_fixture(host, "p")
        result = hi.install_pre_commit(make_ctx(host))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert result.status == hi.REFRESHED and result.findings == ()
        assert hook_ids(text) == ["secret-scan", "service-lint", *template_ids()]
        lines = text.splitlines()
        it = iter(lines)
        assert all(line in it for line in original.splitlines())  # every original line, in order
        assert {h.col for h in hi.enumerate_pre_commit_hooks(text)} == {4}  # the block follows the host's indentation
        begin = lines.index(next(line for line in lines if hi.MARKER_BEGIN in line))
        assert lines[begin - 1] == "      types: [python]" and "- repo: https://example.invalid/hooks/yaml-tools" in text[text.index(hi.MARKER_END):]

    def test_adopt_changes_nothing_for_a_config_without_toolkit_hooks(self, host, pre_commit_runs):
        use_fixture(host, "p")
        plain = hi.install_pre_commit(make_ctx(host))
        first = (host / CONFIG).read_text(encoding="utf-8")
        (host / CONFIG).write_text(first, encoding="utf-8")
        again = hi.install_pre_commit(make_ctx(host, adopt=True))
        assert again.status == hi.CURRENT and (host / CONFIG).read_text(encoding="utf-8") == first and plain.status == hi.REFRESHED

    def test_second_run_is_current(self, host, pre_commit_runs):
        use_fixture(host, "p")
        hi.install_pre_commit(make_ctx(host))
        assert hi.install_pre_commit(make_ctx(host)).status == hi.CURRENT

    def test_a_config_with_no_local_repo_gets_a_new_local_repo_at_the_end_of_repos(self, host, pre_commit_runs):
        original = "repos:\n  - repo: https://example.invalid/x\n    rev: v1\n    hooks:\n      - id: y\n"
        (host / CONFIG).write_text(original, encoding="utf-8")
        hi.install_pre_commit(make_ctx(host))
        text = (host / CONFIG).read_text(encoding="utf-8")
        assert text.startswith(original) and hook_ids(text) == template_ids()
        assert yaml.safe_load(text)["repos"][1]["repo"] == "local"
        assert hi.install_pre_commit(make_ctx(host)).status == hi.CURRENT

    def test_a_config_whose_repos_is_not_a_list_is_refused(self, host, pre_commit_runs):
        (host / CONFIG).write_text("repos: []\n", encoding="utf-8")
        result = hi.install_pre_commit(make_ctx(host))
        assert result.status == hi.REFUSED and "block-style 'repos' list" in result.findings[0].text
        assert (host / CONFIG).read_text(encoding="utf-8") == "repos: []\n"

    @pytest.mark.parametrize("text", ["repos: [unclosed\n", "just a string\n", "other: 1\n"])
    def test_a_file_that_is_not_a_pre_commit_config_is_refused_untouched(self, host, pre_commit_runs, text):
        (host / CONFIG).write_text(text, encoding="utf-8")
        assert hi.install_pre_commit(make_ctx(host)).status == hi.REFUSED
        assert (host / CONFIG).read_text(encoding="utf-8") == text

    def test_a_crlf_file_is_refused_untouched(self, host, pre_commit_runs):
        data = b"repos:\r\n  - repo: local\r\n    hooks:\r\n      - id: x\r\n"
        (host / CONFIG).write_bytes(data)
        result = hi.install_pre_commit(make_ctx(host))
        assert result.status == hi.REFUSED and "CRLF" in result.findings[0].text
        assert (host / CONFIG).read_bytes() == data


class TestGitHook:
    def test_a_failing_pre_commit_install_is_a_w931_finding_not_an_exception(self, host, monkeypatch):
        monkeypatch.setattr(hi, "_run_pre_commit_install", lambda binary, root: (1, "Cowardly refusing to install hooks with `core.hooksPath` set"))
        result = hi.install_pre_commit(make_ctx(host))
        assert result.status == hi.CREATED
        assert [f.code for f in result.findings] == ["W931"]
        assert "core.hooksPath" in result.findings[0].text and "install' by hand" in result.findings[0].text

    def test_an_os_error_from_the_runner_is_the_same_finding(self, host, monkeypatch):
        def boom(binary, root):
            raise OSError("exec format error")

        monkeypatch.setattr(hi, "_run_pre_commit_install", boom)
        assert [f.code for f in hi.install_pre_commit(make_ctx(host)).findings] == ["W931"]

    def test_no_pre_commit_in_the_venv_means_no_run_and_no_finding(self, host, pre_commit_runs):
        result = hi.install_pre_commit(make_ctx(host, with_binary=False))
        assert pre_commit_runs == [] and result.findings == () and result.status == hi.CREATED

    def test_drift_does_not_stop_the_git_hook_install(self, host, pre_commit_runs):
        use_fixture(host, "w")
        assert hi.install_pre_commit(make_ctx(host)).status == hi.DRIFT
        assert len(pre_commit_runs) == 1

    def test_the_real_runner_runs_the_binary_install_in_the_host(self, host, tmp_path):
        script = tmp_path / "fake-pre-commit"
        script.write_text('#!/bin/sh\npwd > "$0.cwd"\necho "$@" > "$0.args"\n')
        script.chmod(0o755)
        assert hi._run_pre_commit_install(script, host) == (0, "")
        assert Path(f"{script}.args").read_text().strip() == "install"
        assert Path(f"{script}.cwd").read_text().strip() == str(host.resolve())


class TestRegistry:
    def test_the_piece_is_registered_first_under_the_name_pre_commit(self):
        assert [p.name for p in hi.PIECES][:1] == ["pre-commit"]
        assert hi.PIECES[0].install is hi.install_pre_commit

    def test_the_fixture_hosts_hold_invented_content_only(self):
        for name in ("w", "p"):
            text = (FIXTURES / name / CONFIG).read_text(encoding="utf-8")
            assert "example.invalid" in text and not re.search(r"vc_|payments|wesbite|/Users/", text)
