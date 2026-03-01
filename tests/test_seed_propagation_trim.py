"""Tests for seed propagation trim: seeds feed Steps 00-04 only."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import (
    _collect_required_seeds,
    _extract_step_from_prompt_filename,
    _lint_prompt_manifest_refs,
    lint_seeds,
)


def _make_project(
    tmpdir,
    step_requirements=None,
    global_seed_order=None,
    spec_files=None,
    prompt_files=None,
):
    """Create a minimal project structure for seed propagation testing."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)
    seed_dir = os.path.join(tmpdir, "docs", "seed")
    os.makedirs(seed_dir, exist_ok=True)

    # Create seed files on disk
    for name in ("seed_overview.md", "seed_tech_stack.md"):
        with open(os.path.join(seed_dir, name), "w", encoding="utf-8") as f:
            f.write(f"# {name}\nSample content for testing purposes with enough words.")

    manifest = {
        "seed_directory": "docs/seed",
        "seeds": [
            {
                "seed_id": "seed-overview",
                "path": "docs/seed/seed_overview.md",
                "description": "Project scope.",
                "required": True,
                "source_type": "doc",
            },
            {
                "seed_id": "seed-tech-stack",
                "path": "docs/seed/seed_tech_stack.md",
                "description": "Architecture decisions.",
                "required": True,
                "source_type": "doc",
            },
        ],
        "global_seed_order": global_seed_order or ["seed-overview", "seed-tech-stack"],
        "nested_order": [],
        "step_requirements": step_requirements or {},
        "docs_policy": {"doc_paths": ["README.md"]},
    }
    with open(
        os.path.join(spec_dir, "common", "seed_manifest.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(manifest, f)

    # Create spec artifact files
    if spec_files:
        for filename, data in spec_files.items():
            path = os.path.join(spec_dir, filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)

    # Create prompt files
    if prompt_files:
        prompts_dir = os.path.join(tmpdir, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        for filename, content in prompt_files.items():
            with open(os.path.join(prompts_dir, filename), "w", encoding="utf-8") as f:
                f.write(content)

    return spec_dir, manifest


class TestSeedPropagationTrim(unittest.TestCase):
    """Verify that seed requirements only apply to Steps 00-04."""

    def test_steps_00_04_require_seeds(self):
        """Steps 00-04 with missing seed_refs should produce errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {
                "00": ["seed-overview", "seed-tech-stack"],
                "01": ["seed-overview"],
                "04": ["seed-overview"],
            }
            spec_files = {
                # Step 00 artifact missing required seed_refs
                "00_charter.json": {
                    "seed_refs": [],
                    "goals": [{"goal_id": "goal-alpha"}],
                },
            }
            spec_dir, _ = _make_project(
                tmpdir, step_requirements=step_reqs, spec_files=spec_files
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            missing = [e for e in errors if "missing required seed_refs" in e and "step 00" in e]
            self.assertTrue(
                len(missing) > 0,
                f"Expected missing seed_refs error for step 00. Got: {errors}",
            )

    def test_steps_05_plus_no_seed_requirement(self):
        """Steps 05+ with empty seed_refs should produce NO errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {
                "00": ["seed-overview", "seed-tech-stack"],
                "01": ["seed-overview"],
            }
            spec_files = {
                "05_interface_contracts.json": {
                    "seed_refs": [],
                    "interfaces": [],
                },
                "07_nfrs.json": {
                    "seed_refs": [],
                    "nfrs": [],
                },
                "09_impl_plan.json": {
                    "seed_refs": [],
                    "milestones": [],
                },
            }
            spec_dir, _ = _make_project(
                tmpdir, step_requirements=step_reqs, spec_files=spec_files
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            seed_errors = [
                e
                for e in errors
                if "missing required seed_refs" in e
                and any(s in e for s in ("step 05", "step 07", "step 09"))
            ]
            self.assertEqual(
                seed_errors,
                [],
                f"Steps 05+ should not require seeds. Got: {seed_errors}",
            )

    def test_global_seed_order_only_applies_to_required_steps(self):
        """global_seed_order should only be enforced for steps in step_requirements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {"00": ["seed-overview"]}
            spec_files = {
                # Step 05 with empty seed_refs — should be fine
                "05_interface_contracts.json": {
                    "seed_refs": [],
                    "interfaces": [],
                },
                # Step 00 without seed-overview — should error
                "00_charter.json": {
                    "seed_refs": [],
                    "goals": [{"goal_id": "goal-alpha"}],
                },
            }
            spec_dir, _ = _make_project(
                tmpdir,
                step_requirements=step_reqs,
                global_seed_order=["seed-overview"],
                spec_files=spec_files,
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            step_05_errors = [
                e for e in errors if "missing required seed_refs" in e and "step 05" in e
            ]
            step_00_errors = [
                e for e in errors if "missing required seed_refs" in e and "step 00" in e
            ]
            self.assertEqual(
                step_05_errors,
                [],
                f"Step 05 should not require seeds. Got: {step_05_errors}",
            )
            self.assertTrue(
                len(step_00_errors) > 0,
                f"Step 00 should require seeds. Got: {errors}",
            )

    def test_lint_prompt_refs_step_aware(self):
        """Prompt lint should only enforce seed sections for seed-required steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {"00": ["seed-overview"]}
            prompt_with_seed = (
                "# Prompt 00\n"
                "## Seed Order & Mandatory Sources\n"
                "Read `spec/common/seed_manifest.json` first.\n"
            )
            prompt_without_seed = "# Prompt 05\n## Context To Ingest\nRead upstream specs.\n"
            prompt_files = {
                "prompt_00_project_charter.md": prompt_with_seed,
                "prompt_05_interface_contracts.md": prompt_without_seed,
            }
            spec_dir, manifest = _make_project(
                tmpdir, step_requirements=step_reqs, prompt_files=prompt_files
            )
            errors: list[str] = []
            _lint_prompt_manifest_refs(tmpdir, errors, manifest)
            step_05_errors = [e for e in errors if "prompt_05" in e]
            self.assertEqual(
                step_05_errors,
                [],
                f"Step 05 prompt should not require seed section. Got: {step_05_errors}",
            )

    def test_extract_step_from_prompt_filename(self):
        """Step extraction from prompt filenames handles all patterns."""
        cases = {
            "prompt_00_project_charter.md": "00",
            "prompt_02a_delivery_baseline.md": "02a",
            "prompt_05_interface_contracts.md": "05",
            "prompt_13a_completeness_assessment.md": "13a",
            "prompt_16a_impl_planner.md": "16a",
        }
        for filename, expected in cases.items():
            result = _extract_step_from_prompt_filename(filename)
            self.assertEqual(
                result,
                expected,
                f"Expected step '{expected}' from '{filename}', got '{result}'",
            )

    def test_collect_required_seeds_empty_for_unlisted_step(self):
        """_collect_required_seeds returns empty set for steps not in step_requirements."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "07")
        self.assertEqual(result, set(), f"Step 07 should have no required seeds. Got: {result}")

    def test_collect_required_seeds_includes_global_for_listed_step(self):
        """_collect_required_seeds includes global_seed_order for steps in step_requirements."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "00")
        self.assertIn("seed-overview", result)
        self.assertIn("seed-tech-stack", result)

    def test_empty_seed_refs_valid_in_spec_artifact(self):
        """Spec artifacts with empty seed_refs should not trigger seed_refs errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {"00": ["seed-overview"]}
            spec_files = {
                "05_interface_contracts.json": {
                    "seed_refs": [],
                    "description": "testing empty seed refs",
                },
            }
            spec_dir, _ = _make_project(
                tmpdir, step_requirements=step_reqs, spec_files=spec_files
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            seed_ref_errors = [
                e
                for e in errors
                if "seed_refs" in e and "05_interface" in e
            ]
            self.assertEqual(
                seed_ref_errors,
                [],
                f"Empty seed_refs for step 05 should be valid. Got: {seed_ref_errors}",
            )


    def test_step_16_no_sub_steps_in_requirements(self):
        """Step 16 with no 16a/16b/16c in step_requirements should require no seeds."""
        manifest = {
            "global_seed_order": ["seed-overview", "seed-tech-stack"],
            "step_requirements": {"00": ["seed-overview"]},
        }
        result = _collect_required_seeds(manifest, "16")
        self.assertEqual(result, set(), f"Step 16 should have no required seeds. Got: {result}")

        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {"00": ["seed-overview"]}
            spec_files = {
                "16_impl_context.json": {
                    "seed_refs": [],
                    "context": [],
                },
            }
            spec_dir, _ = _make_project(
                tmpdir, step_requirements=step_reqs, spec_files=spec_files
            )
            errors = lint_seeds(repo_root=tmpdir, spec_dir=spec_dir, project_root=tmpdir)
            step_16_errors = [
                e for e in errors if "missing required seed_refs" in e and "step 16" in e
            ]
            self.assertEqual(
                step_16_errors,
                [],
                f"Step 16 should not require seeds when 16a/16b/16c absent. Got: {step_16_errors}",
            )

    def test_lint_prompt_refs_manifest_none(self):
        """_lint_prompt_manifest_refs with manifest=None emits warning, not seed errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = os.path.join(tmpdir, "prompts")
            os.makedirs(prompts_dir, exist_ok=True)
            with open(
                os.path.join(prompts_dir, "prompt_05_interface_contracts.md"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write("# Prompt 05\n## Context To Ingest\nRead upstream specs.\n")

            errors: list[str] = []
            _lint_prompt_manifest_refs(tmpdir, errors, manifest=None)
            warning = [e for e in errors if "skipping prompt seed-section checks" in e]
            self.assertEqual(
                len(warning),
                1,
                f"Expected exactly 1 manifest-None warning. Got: {errors}",
            )
            seed_section_errors = [
                e for e in errors if "missing 'Seed Order & Mandatory Sources'" in e
            ]
            self.assertEqual(
                seed_section_errors,
                [],
                f"Should not require seed sections when manifest is None. Got: {seed_section_errors}",
            )


    def test_lint_prompt_refs_step_aware_step00_missing_section(self):
        """Step 00 prompt missing 'Seed Order & Mandatory Sources' should produce an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_reqs = {"00": ["seed-overview"]}
            # Prompt for step 00 that is MISSING the seed section
            prompt_missing_seed_section = (
                "# Prompt 00 Charter\n"
                "## Context To Ingest\n"
                "Read upstream specs.\n"
            )
            prompt_files = {
                "prompt_00_charter.md": prompt_missing_seed_section,
            }
            spec_dir, manifest = _make_project(
                tmpdir, step_requirements=step_reqs, prompt_files=prompt_files
            )
            errors: list[str] = []
            _lint_prompt_manifest_refs(tmpdir, errors, manifest)
            step_00_errors = [
                e
                for e in errors
                if "prompt_00" in e or "step 00" in e.lower() or "Seed Order" in e
            ]
            self.assertTrue(
                len(step_00_errors) > 0,
                f"Expected error about missing seed section for step 00 prompt. Got: {errors}",
            )

    def test_empty_seed_refs_passes_json_schema(self):
        """An empty seed_refs array should pass JSON Schema validation against seedRefArray."""
        from pathlib import Path

        from jsonschema import Draft202012Validator

        from specdev_tools.core.registry import SchemaRegistry
        from specdev_tools.validation.validate import _registry_for

        repo_root = Path(__file__).resolve().parents[1]
        registry = SchemaRegistry(str(repo_root))
        jsonschema_registry = _registry_for(registry)

        collections_path = repo_root / "schema" / "core" / "collections.schema.json"
        with collections_path.open("r", encoding="utf-8") as f:
            collections_schema = json.load(f)

        seed_ref_array_schema = collections_schema["$defs"]["seedRefArray"]
        # Resolve relative to the parent schema $id
        seed_ref_array_schema.setdefault("$id", collections_schema["$id"] + "#seedRefArray")

        validator = Draft202012Validator(
            seed_ref_array_schema,
            registry=jsonschema_registry,
        )
        # Empty array should validate without error
        errors = list(validator.iter_errors([]))
        self.assertEqual(
            errors,
            [],
            f"Empty seed_refs should pass seedRefArray validation. Got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
