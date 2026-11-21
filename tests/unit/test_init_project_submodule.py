"""Tests for init_project.py pre-commit config generation and seed bootstrap."""
import json
import os
import sys
from unittest import mock

import pytest
import yaml

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import init_project
from init_project import _build_pre_commit_config, _render_ci_workflow, copy_seeds_from_manifest

SPEC_CHECK_ENTRY_TAIL = "spec-check spec --repo-root ./{root} --spec-root ./spec --git-root . --paths"


def _spec_check_hook(content: str) -> dict:
    """Return the `spec-check` hook mapping of a rendered pre-commit config."""
    hooks = yaml.safe_load(content)["repos"][0]["hooks"]
    return next(h for h in hooks if h["id"] == "spec-check")


class TestBuildPreCommitConfig:
    def test_repo_root_flag_present(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "--repo-root ./devspec_toolkit" in content

    def test_custom_toolkit_path(self):
        content = _build_pre_commit_config("custom/path")
        assert "--repo-root ./custom/path" in content

    def test_contains_spec_check_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "spec-check" in content

    def test_contains_canonical_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canonical-lint" in content

    def test_contains_seed_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "seed-lint" in content

    def test_contains_dependency_order_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "dependency-order-lint" in content

    def test_path_substitution_applied(self):
        content = _build_pre_commit_config("my_toolkit")
        assert "./devspec_toolkit" not in content
        assert "devspec_toolkit/" not in content
        assert "devspec_toolkit/tools" not in content
        assert "./my_toolkit" in content
        assert "my_toolkit/" in content

    def test_build_pre_commit_config_missing_template(self):
        with mock.patch("init_project.os.path.exists", return_value=False):
            content = _build_pre_commit_config("devspec_toolkit")
        assert "spec-check" in content
        assert "devspec_env/bin/python" in content
        assert "--repo-root ./devspec_toolkit" in content
        assert "--spec-root ./spec" in content
        assert "--git-root ." in content

    def test_contains_dag_lint_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "dag-lint" in content

    def test_contains_extraction_intent_check_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "extraction-intent-check" in content

    def test_contains_canon_schema_alignment_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canon-schema-alignment" in content

    def test_contains_canonical_integrity_hook(self):
        content = _build_pre_commit_config("devspec_toolkit")
        assert "canonical-integrity" in content

    def test_custom_venv_name_propagates(self):
        content = _build_pre_commit_config("devspec_toolkit", "customenv")
        assert "customenv/bin/python" in content
        # no leakage of the default venv name when a custom one is requested
        assert "devspec_env/bin/python" not in content

    def test_spec_check_hook_ends_with_paths_takes_filenames_and_has_no_files_filter(self):
        hook = _spec_check_hook(_build_pre_commit_config("devspec_toolkit"))
        assert hook["entry"].endswith(" --paths")
        assert hook["pass_filenames"] is True
        assert hook["require_serial"] is True
        assert "files" not in hook

    @pytest.mark.parametrize("root", ["devspec_toolkit", "custom/path", "my_toolkit"])
    def test_custom_toolkit_root_is_substituted_in_the_spec_check_entry(self, root):
        hook = _spec_check_hook(_build_pre_commit_config(root))
        assert hook["entry"] == (
            "devspec_env/bin/python -m specdev_tools.cli "
            + SPEC_CHECK_ENTRY_TAIL.format(root=root)
        )

    def test_fallback_hook_also_ends_with_paths(self):
        with mock.patch("init_project.os.path.exists", return_value=False):
            hook = _spec_check_hook(_build_pre_commit_config("my_toolkit", "venv2"))
        assert hook["entry"] == "venv2/bin/python -m specdev_tools.cli " + SPEC_CHECK_ENTRY_TAIL.format(root="my_toolkit")
        assert hook["pass_filenames"] is True
        assert "files" not in hook

    def test_seed_lint_hook_keeps_its_files_filter(self):
        hooks = yaml.safe_load(_build_pre_commit_config("devspec_toolkit"))["repos"][0]["hooks"]
        seed_lint = next(h for h in hooks if h["id"] == "seed-lint")
        assert seed_lint["files"] == r"spec/.*\.json$"
        assert seed_lint["pass_filenames"] is False


class TestInitIntoHost:
    """Run `init_project.main` into a temporary host with every subprocess stubbed."""

    TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def _init(self, host, monkeypatch) -> None:
        monkeypatch.setattr(sys, "argv", ["init_project.py", "--target", str(host), "--toolkit-root", self.TOOLKIT_ROOT])
        with (
            mock.patch("init_project.run_cmd"),
            mock.patch("init_project.run_install_delegate", return_value=0),
            mock.patch("init_project.shutil.which", return_value="/usr/bin/uv"),
        ):
            init_project.main()

    def test_new_host_gets_the_step_gate_hook(self, tmp_path, monkeypatch):
        self._init(tmp_path, monkeypatch)
        hook = _spec_check_hook((tmp_path / ".pre-commit-config.yaml").read_text())
        assert hook["entry"].endswith(" --git-root . --paths")
        assert hook["pass_filenames"] is True
        assert "files" not in hook

    def test_existing_pre_commit_config_is_left_untouched(self, tmp_path, monkeypatch):
        old = "repos:\n  - repo: local\n    hooks:\n      - id: spec-check\n        files: spec/.*\\.json$\n"
        (tmp_path / ".pre-commit-config.yaml").write_text(old)
        self._init(tmp_path, monkeypatch)
        assert (tmp_path / ".pre-commit-config.yaml").read_text() == old


    def test_init_delegates_to_venv_cli_after_venv_created(self, tmp_path, monkeypatch):
        calls: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(
            sys, "argv",
            ["init_project.py", "--target", str(tmp_path), "--toolkit-root", self.TOOLKIT_ROOT, "--force-claude"],
        )
        with (
            mock.patch("init_project.run_cmd", side_effect=lambda cmd, **kw: calls.append(("run_cmd", list(cmd)))),
            mock.patch("init_project.run_install_delegate", side_effect=lambda cmd, cwd: calls.append(("delegate", [*cmd, cwd])) or 0),
            mock.patch("init_project.shutil.which", return_value="/usr/bin/uv"),
        ):
            init_project.main()
        names = [name for name, _ in calls]
        setup = next(i for i, (n, c) in enumerate(calls) if n == "run_cmd" and c[0] == "bash")
        precommit = next(i for i, (n, c) in enumerate(calls) if n == "run_cmd" and c[:3] == ["uv", "pip", "install"])
        delegate = names.index("delegate")
        assert setup < precommit < delegate
        command = calls[delegate][1]
        rel_toolkit = os.path.relpath(self.TOOLKIT_ROOT, tmp_path).replace("\\", "/")
        assert command == [
            str(tmp_path / "devspec_env" / "bin" / "specdev"), "update", "spec", "--repo-root", rel_toolkit,
            "--install-only", "--force-claude", str(tmp_path),
        ]

    def test_init_exits_nonzero_with_the_rerun_command_when_the_delegate_fails(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["init_project.py", "--target", str(tmp_path), "--toolkit-root", self.TOOLKIT_ROOT])
        with (
            mock.patch("init_project.run_cmd"),
            mock.patch("init_project.run_install_delegate", return_value=1),
            mock.patch("init_project.shutil.which", return_value="/usr/bin/uv"),
            pytest.raises(SystemExit) as raised,
        ):
            init_project.main()
        assert raised.value.code == 1
        assert "./tools/run_specdev.sh update spec --repo-root" in capsys.readouterr().err

    def test_init_project_never_imports_the_package(self):
        import ast

        tree = ast.parse(open(init_project.__file__, encoding="utf-8").read())
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert "specdev_tools" not in imported


class TestManifestDerivedSeedBootstrap:
    """Verify that seed templates land at the paths declared in seeds[].path,
    not at a hardcoded docs/seed/ location."""

    def _make_seed_manifest(self, target_dir, seed_paths):
        """Write a minimal seed_manifest.json with the given seed path entries."""
        seeds = []
        for rel_path in seed_paths:
            stem = os.path.splitext(os.path.basename(rel_path))[0]
            seed_id = stem.replace("_", "-")
            seeds.append({"seed_id": seed_id, "path": rel_path})
        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "test-manifest",
            "version": "0.1.0",
            "seeds": seeds,
        }
        common_dir = os.path.join(target_dir, "spec", "common")
        os.makedirs(common_dir, exist_ok=True)
        manifest_path = os.path.join(common_dir, "seed_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return manifest_path

    def _make_seed_templates(self, templates_dir, filenames):
        """Create stub .md template files."""
        os.makedirs(templates_dir, exist_ok=True)
        for name in filenames:
            with open(os.path.join(templates_dir, name), "w") as f:
                f.write(f"# {name}\n")

    def test_seeds_land_at_manifest_declared_paths(self, tmp_path):
        """Files must be copied to the exact relative paths in seeds[].path."""
        declared_paths = [
            "docs/seed/seed_overview.md",
            "docs/seed/seed_tech_stack.md",
        ]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        self._make_seed_templates(templates_dir, ["seed_overview.md", "seed_tech_stack.md"])

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        # Read back the manifest and assert each declared path exists on disk
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        for entry in manifest_data["seeds"]:
            expected = tmp_path / entry["path"]
            assert expected.exists(), (
                f"Expected seed file at {entry['path']} (declared in manifest) "
                f"but it was not created."
            )

    def test_seeds_land_at_non_default_path_when_manifest_declares_it(self, tmp_path):
        """When the manifest declares a non-docs/seed path the file must land
        there — proving the logic is manifest-driven, not hardcoded."""
        declared_paths = ["content/seeds/seed_overview.md"]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        self._make_seed_templates(templates_dir, ["seed_overview.md"])

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        expected = tmp_path / "content" / "seeds" / "seed_overview.md"
        assert expected.exists(), (
            "Expected seed file at content/seeds/seed_overview.md "
            "(non-default path declared in manifest) but it was not created."
        )
        # The hardcoded default must NOT have been used
        assert not (tmp_path / "docs" / "seed" / "seed_overview.md").exists(), (
            "File was placed at the hardcoded docs/seed/ path instead of "
            "the manifest-declared path."
        )

    def test_fallback_is_deterministic_across_multiple_parent_dirs(self, tmp_path):
        """When a template .md has no manifest entry and multiple seed parent
        dirs exist, the fallback must always be the lexicographically first dir."""
        declared_paths = [
            "alpha/seeds/seed_a.md",
            "zeta/seeds/seed_z.md",
        ]
        manifest_path = self._make_seed_manifest(str(tmp_path), declared_paths)

        templates_dir = str(tmp_path / "seed_templates")
        # seed_extra.md has no manifest entry — will use the fallback dir
        self._make_seed_templates(
            templates_dir, ["seed_a.md", "seed_z.md", "seed_extra.md"]
        )

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        # Fallback should be sorted(parent_dirs)[0] → alpha/seeds (< zeta/seeds)
        expected_fallback = tmp_path / "alpha" / "seeds" / "seed_extra.md"
        assert expected_fallback.exists(), (
            "Unmatched template should fall back to the lexicographically first "
            "seed parent dir (alpha/seeds), not a non-deterministic choice."
        )


class TestCiWorkflowRender:
    def test_default_venv_name_in_ci(self):
        content = _render_ci_workflow(".", "devspec_env")
        # uv-driven setup: managed Python + venv on the default name
        assert "astral-sh/setup-uv" in content
        assert "uv venv devspec_env --python 3.13" in content
        assert "uv pip install --python devspec_env/bin/python" in content
        # the old pip/venv path must be gone
        assert "python -m venv" not in content
        assert "/bin/pip install" not in content

    def test_custom_venv_name_propagates(self):
        content = _render_ci_workflow(".", "customenv")
        assert "uv venv customenv --python 3.13" in content
        assert "uv pip install --python customenv/bin/python" in content
        assert "customenv/bin" in content
        # no leakage of the default venv name when a custom one is requested
        assert "devspec_env" not in content

    def test_ci_uses_spec_check_not_validate_all(self):
        content = _render_ci_workflow(".", "devspec_env")
        assert "spec-check" in content
        assert "validate-all" not in content
        assert "--spec-root ./spec" in content
        assert "--git-root ." in content

    def test_init_template_has_no_matrix_step(self):
        content = _render_ci_workflow(".", "devspec_env")
        assert "matrix" not in content
        assert "trace_matrix" not in content
        assert "upload-artifact" not in content

    def test_toolkit_path_substitution(self):
        content = _render_ci_workflow("vendor/devspec_toolkit", "devspec_env")
        assert "vendor/devspec_toolkit/tools" in content
        # Every "devspec_toolkit/tools" occurrence must carry the vendor/ prefix —
        # i.e. the path substitution left no unsubstituted bare token behind.
        # (Discriminating: if replace-1 were dropped, bare tokens would remain and
        # the counts would diverge.)
        assert content.count("devspec_toolkit/tools") == content.count("vendor/devspec_toolkit/tools")
