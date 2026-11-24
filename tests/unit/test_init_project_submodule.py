"""Tests for init_project.py: the host install delegate, the strict-mode hook, seed bootstrap and the CI workflow render."""
import json
import os
import sys
from unittest import mock

import pytest

# Add scripts to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import init_project
from init_project import copy_seeds_from_manifest


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

    def test_init_itself_writes_no_pre_commit_config_and_runs_no_plain_pre_commit_install(self, tmp_path, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(sys, "argv", ["init_project.py", "--target", str(tmp_path), "--toolkit-root", self.TOOLKIT_ROOT])
        with (
            mock.patch("init_project.run_cmd", side_effect=lambda cmd, **kw: calls.append(list(cmd))),
            mock.patch("init_project.run_install_delegate", return_value=0),
            mock.patch("init_project.shutil.which", return_value="/usr/bin/uv"),
        ):
            init_project.main()
        assert not (tmp_path / ".pre-commit-config.yaml").exists()
        assert not any(c[-1:] == ["install"] and "pre-commit" in c[0] for c in calls)
        assert not hasattr(init_project, "_build_pre_commit_config")

    def test_strict_adds_the_commit_msg_hook_and_appends_the_governance_hook_after_the_delegate(self, tmp_path, monkeypatch):
        (tmp_path / "devspec_env" / "bin").mkdir(parents=True)
        (tmp_path / "devspec_env" / "bin" / "pre-commit").write_text("#!/bin/sh\n")
        config = tmp_path / ".pre-commit-config.yaml"
        calls: list[tuple[str, list[str]]] = []

        def delegate(cmd, cwd):  # the installer writes the file; init only appends the strict hook afterwards
            calls.append(("delegate", list(cmd)))
            config.write_text("repos:\n  - repo: local\n    hooks:\n      # >>> specdev-managed\n      - id: spec-check\n      # <<< specdev-managed\n")
            return 0

        monkeypatch.setattr(sys, "argv", ["init_project.py", "--target", str(tmp_path), "--toolkit-root", self.TOOLKIT_ROOT, "--strict"])
        with (
            mock.patch("init_project.run_cmd", side_effect=lambda cmd, **kw: calls.append(("run_cmd", list(cmd)))),
            mock.patch("init_project.run_install_delegate", side_effect=delegate),
            mock.patch("init_project.shutil.which", return_value="/usr/bin/uv"),
        ):
            init_project.main()
        order = [name for name, _ in calls]
        commit_msg = next(i for i, (n, c) in enumerate(calls) if n == "run_cmd" and c[-2:] == ["--hook-type", "commit-msg"])
        assert order.index("delegate") < commit_msg
        text = config.read_text()
        assert text.rstrip().endswith("stages: [commit-msg]")
        assert text.index("devspec-governance") > text.index("# <<< specdev-managed")

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


class TestCommitMsgHookInstall:
    """`--strict` installs the commit-msg hook; a refusal by pre-commit is a warning, not a crash."""

    @staticmethod
    def _fake_pre_commit(tmp_path, exit_code):
        script = tmp_path / "pre-commit"
        script.write_text(f"#!/bin/sh\nexit {exit_code}\n")
        script.chmod(0o755)
        return str(script)

    def test_a_failing_commit_msg_install_is_a_warning(self, tmp_path, capsys):
        installed = init_project.install_commit_msg_hook(self._fake_pre_commit(tmp_path, 1), str(tmp_path))
        assert installed is False
        assert "core.hooksPath" in capsys.readouterr().err

    def test_a_working_commit_msg_install_returns_true(self, tmp_path, capsys):
        installed = init_project.install_commit_msg_hook(self._fake_pre_commit(tmp_path, 0), str(tmp_path))
        assert installed is True
        assert capsys.readouterr().err == ""


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


class TestExtensionSeedTemplate:
    """seed_templates/seed_extension.md is a blank for the seed of one feature; init copies it with the others."""

    TOOLKIT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def test_extension_seed_template_is_scaffolded(self, tmp_path):
        templates_dir = os.path.join(self.TOOLKIT_ROOT, "seed_templates")
        manifest_path = os.path.join(templates_dir, "seed_manifest.json")

        copy_seeds_from_manifest(str(tmp_path), templates_dir, manifest_path)

        assert (tmp_path / "docs" / "seed" / "seed_extension.md").is_file()
        assert (tmp_path / "docs" / "seed" / "seed_overview.md").is_file()
