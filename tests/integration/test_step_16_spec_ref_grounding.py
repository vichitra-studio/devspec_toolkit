import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from specdev_tools.validate import validate_file


class TestStep16SpecRefGrounding(unittest.TestCase):
    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)
        self.git_available = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0

    def _write_json(self, path: str, payload: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _init_project(self, tmp: str) -> tuple[str, str]:
        if not self.git_available:
            self.skipTest("git is required for spec_ref grounding tests")

        seed_manifest = {
            "$schema": "https://specdev.local/schema/seed_manifest.schema.json",
            "seed_manifest_id": "seed-manifest-core",
            "version": "0.1.0",
            "created_at": "2026-02-12T00:00:00Z",
            "last_updated": "2026-02-12T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "nested_order": [],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "overview",
                    "required": True,
                    "source_type": "doc"
                }
            ],
            "step_requirements": {
                "16a": ["seed-overview"],
                "16b": ["seed-overview"],
                "16c": ["seed-overview"]
            },
            "docs_policy": {
                "readme_required": True,
                "root_readme_required": True,
                "readme_depth_default": 0,
                "readme_depth_by_scope": {},
                "scope": ["."],
                "exclusions": [],
                "doc_paths": ["docs/**", "README.md"]
            }
        }
        fr_list = {
            "$schema": "https://specdev.local/schema/04_fr_list.schema.json",
            "functional_requirements": [
                {
                    "id": "fr-core-login",
                    "title": "login",
                    "description": "Implement login."
                }
            ]
        }
        impl_context_path = os.path.join(tmp, "spec", "impl_context", "16_step.json")

        self._write_json(os.path.join(tmp, "spec", "common", "seed_manifest.json"), seed_manifest)
        self._write_json(os.path.join(tmp, "spec", "04_fr_list.json"), fr_list)
        os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
            f.write("# temp\n")

        subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=tmp, check=True, capture_output=True)
        commit_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        return impl_context_path, commit_hash

    def _build_impl_context(self, commit_hash: str, spec_ref_id: str, line_range: str) -> dict:
        return {
            "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
            "id": "step-test-grounding",
            "owner": "api",
            "created_at": "2026-02-12T00:00:00Z",
            "seed_refs": [{"seed_id": "seed-overview"}],
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": "Grounding test",
                    "scope_in": ["core-auth"],
                    "scope_out": ["oauth"],
                    "target_file_patterns": ["src/auth.py", "README.md"]
                },
                "spec_alignment": {
                    "requirements_summary": [
                        {
                            "theme": "Auth",
                            "summary": "Implement login requirement"
                        }
                    ],
                    "checklist": [
                        {
                            "id": "REQ_AUTH_001",
                            "spec_ref": {
                                "type": "fr",
                                "id": spec_ref_id,
                                "line_range": line_range,
                                "commit_hash": commit_hash
                            },
                            "description": "Implement login behavior",
                            "type": "behavior",
                            "layer": "service",
                            "linked_test_expectation": "pytest -q",
                            "nfr_refs": ["nfr-availability-uptime"],
                            "fixture_ref": "fixture-login-success"
                        }
                    ]
                },
                "docs_impact": {
                    "status": "required",
                    "rationale": "Non-doc scope requires docs updates for traceability.",
                    "docs_touched": ["README.md"]
                },
                "review_requirements": {
                    "test_commands": ["pytest -q"]
                }
            }
        }

    def test_spec_ref_grounding_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_context_path, commit_hash = self._init_project(tmp)
            payload = self._build_impl_context(commit_hash, "fr-core-login", "L1-L5")
            self._write_json(impl_context_path, payload)
            errors = validate_file(self.repo_root, impl_context_path)
            self.assertEqual(errors, [], f"Valid grounded spec_ref should pass. Errors: {errors}")

    def test_spec_ref_grounding_invalid_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_context_path, commit_hash = self._init_project(tmp)
            payload = self._build_impl_context(commit_hash, "fr-does-not-exist", "L1-L5")
            self._write_json(impl_context_path, payload)
            errors = validate_file(self.repo_root, impl_context_path)
            self.assertTrue(
                any("id not found for type" in e for e in errors),
                f"Expected authority-id grounding error. Errors: {errors}",
            )

    def test_spec_ref_grounding_invalid_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_context_path, _ = self._init_project(tmp)
            bad_commit = "f" * 40
            payload = self._build_impl_context(bad_commit, "fr-core-login", "L1-L5")
            self._write_json(impl_context_path, payload)
            errors = validate_file(self.repo_root, impl_context_path)
            self.assertTrue(
                any("commit_hash" in e and "not found in git" in e for e in errors),
                f"Expected commit grounding error. Errors: {errors}",
            )

    def test_spec_ref_grounding_invalid_line_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_context_path, commit_hash = self._init_project(tmp)
            payload = self._build_impl_context(commit_hash, "fr-core-login", "L999-L1000")
            self._write_json(impl_context_path, payload)
            errors = validate_file(self.repo_root, impl_context_path)
            self.assertTrue(
                any("line_range" in e and "does not map" in e for e in errors),
                f"Expected line-range grounding error. Errors: {errors}",
            )

    def test_spec_ref_grounding_applies_to_real_milestone_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _ = self._init_project(tmp)
            impl_context_path = os.path.join(tmp, "spec", "impl_context", "m1-core-foundation.json")
            bad_commit = "f" * 40
            payload = self._build_impl_context(bad_commit, "fr-core-login", "L1-L5")
            self._write_json(impl_context_path, payload)
            errors = validate_file(self.repo_root, impl_context_path)
            self.assertTrue(
                any("commit_hash" in e and "not found in git" in e for e in errors),
                f"Expected commit grounding error for milestone filename. Errors: {errors}",
            )


if __name__ == "__main__":
    unittest.main()
