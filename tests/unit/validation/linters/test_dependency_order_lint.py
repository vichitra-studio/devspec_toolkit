import json
import tempfile
import unittest
from pathlib import Path

from specdev_tools.validation.dependency_order_lint import lint_dependency_order
from specdev_tools.core.errors import render_errors


class DependencyOrderLintTests(unittest.TestCase):
    def test_detects_forward_and_self_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            fixture_path = (
                Path(__file__).resolve().parents[3]
                / "fixtures"
                / "dependency_order"
                / "prompt_01_with_forward_ref.md"
            )
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("self-edge" in e for e in render_errors(errs)))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))
            self.assertEqual(len(errs), len(set(errs)))

    def test_detects_absolute_path_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8"
            )
            (root / "prompts" / "prompt_01_abs.md").write_text(
                "/repo/spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))

    def test_ignores_plain_step_number_mentions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_text.md").write_text(
                "This is Step 01 and references 00 in prose only.",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_forward_dependency_enforced(self):
        """Forward references (to steps after the current step) are flagged as forward-edge violations.

        Under derive_allowed_upstream, all prior steps are valid upstreams.
        Only references to later steps (forward edges) are disallowed.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8",
            )
            # prompt_01 references spec/02_*.json which comes AFTER step 01 -> disallowed forward edge
            (root / "prompts" / "prompt_01_text.md").write_text(
                "Use spec/00_charter.json and spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("forward-edge" in e for e in render_errors(errs)))

    def test_ignores_example_spec_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_00_test.md").write_text(
                "Example only: example/devspec_kit/spec/00_charter.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_does_not_match_space_separated_path_fragment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({"steps": ["00", "01", "02"]}),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_text.md").write_text(
                "Broken token: /repo path/spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_policy_can_allow_forward_and_self_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps(
                    {
                        "steps": ["00", "01", "02"],
                        "policy": {"allow_self_dependency": True, "allow_forward_dependency": True},
                    }
                ),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                "spec/01_capabilities.json and spec/02_system_sketch.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_invalid_step_order_json_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text("{bad", encoding="utf-8")
            errs = lint_dependency_order(str(root))
            self.assertTrue(any("invalid_step_order" in e for e in render_errors(errs)))

    def test_works_with_downstream_consumers_format(self):
        """Verify lint works with new step_order.json format (downstream_consumers, no step_metadata)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "prompts").mkdir()
            (root / "tools" / "step_order.json").write_text(
                json.dumps({
                    "steps": ["00", "01", "02"],
                    "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                }),
                encoding="utf-8",
            )
            (root / "prompts" / "prompt_01_test.md").write_text(
                "Use spec/00_charter.json",
                encoding="utf-8",
            )
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)


class StepMetadataConsistencyTests(unittest.TestCase):
    """Consistency check: step_metadata.required_spec_inputs must be inverse of downstream_consumers."""

    def _write_order(self, root: Path, data: dict) -> None:
        (root / "tools").mkdir(exist_ok=True)
        (root / "prompts").mkdir(exist_ok=True)
        (root / "tools" / "step_order.json").write_text(
            json.dumps(data), encoding="utf-8",
        )

    def _write_seed_manifest(self, root: Path, step_requirements: dict) -> None:
        """Write a minimal seed_manifest.json under spec/common/ for the seed-consistency check."""
        (root / "spec" / "common").mkdir(parents=True, exist_ok=True)
        (root / "spec" / "common" / "seed_manifest.json").write_text(
            json.dumps({"step_requirements": step_requirements}),
            encoding="utf-8",
        )

    def test_absent_step_metadata_is_no_op(self):
        """When step_metadata is absent the consistency check emits no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_consistent_step_metadata_passes(self):
        """Correctly inverted step_metadata produces no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": []},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": []},
                    "02": {"required_spec_inputs": ["00", "01"], "required_seed_inputs": []},
                },
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_missing_required_spec_input_reported(self):
        """E543 fires when downstream_consumers implies an edge not declared in required_spec_inputs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": []},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": []},
                    # 02 is missing "01" — should trigger E543
                    "02": {"required_spec_inputs": ["00"], "required_seed_inputs": []},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any("STEP_METADATA_INCONSISTENT" in e and "missing" in e for e in rendered),
                f"Expected missing-edge error, got: {rendered}",
            )

    def test_extra_required_spec_input_reported(self):
        """E543 fires when required_spec_inputs lists a step not in downstream_consumers."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01"], "01": [], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": []},
                    # 01 claims to depend on 02 but downstream_consumers says otherwise
                    "01": {"required_spec_inputs": ["00", "02"], "required_seed_inputs": []},
                    "02": {"required_spec_inputs": [], "required_seed_inputs": []},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any("STEP_METADATA_INCONSISTENT" in e and "extra" in e for e in rendered),
                f"Expected extra-edge error, got: {rendered}",
            )

    def test_seed_consistency_no_manifest_is_no_op(self):
        """When seed_manifest.json is absent the seed-consistency check emits no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01"],
                "downstream_consumers": {"00": ["01"], "01": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": ["seed-overview"]},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": []},
                },
            })
            # No seed_manifest.json written — seed-consistency branch must skip silently.
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_seed_consistency_consistent_passes(self):
        """Matching required_seed_inputs and seed_manifest.step_requirements produces no errors."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01"],
                "downstream_consumers": {"00": ["01"], "01": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": [], "required_seed_inputs": ["seed-overview", "seed-tech-stack"]},
                    "01": {"required_spec_inputs": ["00"], "required_seed_inputs": ["seed-overview"]},
                },
            })
            self._write_seed_manifest(root, {
                "00": ["seed-overview", "seed-tech-stack"],
                "01": ["seed-overview"],
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs)

    def test_seed_consistency_missing_reported(self):
        """E543 fires when seed_manifest declares a seed dependency that step_metadata omits."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00"],
                "downstream_consumers": {"00": []},
                "step_metadata": {
                    # step_metadata declares no seeds for 00
                    "00": {"required_spec_inputs": [], "required_seed_inputs": []},
                },
            })
            # seed_manifest says 00 needs seed-overview — this is a missing edge
            self._write_seed_manifest(root, {"00": ["seed-overview"]})
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any(
                    "STEP_METADATA_INCONSISTENT" in e
                    and "required_seed_inputs" in e
                    and "missing" in e
                    for e in rendered
                ),
                f"Expected missing seed-edge error, got: {rendered}",
            )

    def test_seed_consistency_extra_reported(self):
        """E543 fires when step_metadata lists a seed that seed_manifest does not require."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00"],
                "downstream_consumers": {"00": []},
                "step_metadata": {
                    # step_metadata claims 00 needs seed-bogus, but seed_manifest disagrees
                    "00": {"required_spec_inputs": [], "required_seed_inputs": ["seed-overview", "seed-bogus"]},
                },
            })
            self._write_seed_manifest(root, {"00": ["seed-overview"]})
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any(
                    "STEP_METADATA_INCONSISTENT" in e
                    and "required_seed_inputs" in e
                    and "extra" in e
                    for e in rendered
                ),
                f"Expected extra seed-edge error, got: {rendered}",
            )

    # ── M3: incremental adoption — both inner fields independently optional ──

    def test_step_metadata_with_only_required_spec_inputs_passes(self):
        """M3: a step_metadata entry with only required_spec_inputs is valid.

        Both inner fields are optional independently. Omitting required_seed_inputs
        is treated as an empty list and no E543 should fire as long as the seed-side
        comparison source (seed_manifest.step_requirements) is also empty for the step.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01"],
                "downstream_consumers": {"00": ["01"], "01": []},
                "step_metadata": {
                    # required_seed_inputs intentionally omitted — incremental adoption
                    "00": {"required_spec_inputs": []},
                    "01": {"required_spec_inputs": ["00"]},
                },
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs, f"Expected no errors. Got: {errs}")

    def test_step_metadata_with_only_required_seed_inputs_passes(self):
        """M3: a step_metadata entry with only required_seed_inputs is valid.

        Symmetric to the spec-side test: omitting required_spec_inputs is valid
        as long as downstream_consumers also implies no spec-side edge.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00"],
                "downstream_consumers": {"00": []},
                "step_metadata": {
                    # required_spec_inputs intentionally omitted
                    "00": {"required_seed_inputs": ["seed-overview"]},
                },
            })
            self._write_seed_manifest(root, {"00": ["seed-overview"]})
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs, f"Expected no errors. Got: {errs}")

    def test_step_metadata_with_empty_inner_block_passes(self):
        """M3: an entirely empty inner block (`{}`) is valid for steps with no edges.

        Equivalent to {required_spec_inputs: [], required_seed_inputs: []} but lets
        a partial migration land step-by-step without forcing every entry to fully
        declare both arrays at once.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00"],
                "downstream_consumers": {"00": []},
                "step_metadata": {"00": {}},
            })
            errs = lint_dependency_order(str(root))
            self.assertEqual([], errs, f"Expected no errors. Got: {errs}")

    # ── M4: phantom step keys ────────────────────────────────────────────────

    def test_step_metadata_phantom_step_key_reported(self):
        """M4: E543 fires when step_metadata contains a key not declared in steps[].

        Without this check, step_metadata['99']={} silently passes both schema and
        the inverse check (the inverse for an unlisted step is always empty).
        Phantom keys mask typos and stale entries — surface them at lint time.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01"],
                "downstream_consumers": {"00": ["01"], "01": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": []},
                    "01": {"required_spec_inputs": ["00"]},
                    # Phantom — "99" is not in steps[]
                    "99": {"required_spec_inputs": []},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any(
                    "STEP_METADATA_INCONSISTENT" in e
                    and "'99'" in e
                    and "not declared in the top-level 'steps' array" in e
                    for e in rendered
                ),
                f"Expected phantom-key error naming step '99'. Got: {rendered}",
            )

    def test_step_metadata_phantom_step_key_typo_caught(self):
        """M4: a typo'd step ID (e.g. '02b' instead of '02a') is flagged as phantom.

        This is the realistic failure mode the check protects against: an author
        adds a step_metadata entry for a step that LOOKS like a real ID but does
        not exist in the canonical steps[] array.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "02a"],
                "downstream_consumers": {"00": ["02a"], "02a": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": []},
                    "02a": {"required_spec_inputs": ["00"]},
                    # Typo: meant 02a, wrote 02b
                    "02b": {"required_spec_inputs": ["00"]},
                },
            })
            errs = lint_dependency_order(str(root))
            rendered = render_errors(errs)
            self.assertTrue(
                any("'02b'" in e and "not declared" in e for e in rendered),
                f"Expected phantom-key error naming step '02b'. Got: {rendered}",
            )

    def test_step_metadata_no_phantom_keys_passes(self):
        """M4: when every step_metadata key is in steps[], no phantom error fires.

        Negative test ensuring the M4 check is scoped to truly unknown keys and
        doesn't false-positive on the canonical configuration (the toolkit's own
        step_order.json declares step_metadata for all 22 listed steps).
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_order(root, {
                "steps": ["00", "01", "02"],
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
                "step_metadata": {
                    "00": {"required_spec_inputs": []},
                    "01": {"required_spec_inputs": ["00"]},
                    "02": {"required_spec_inputs": ["00", "01"]},
                },
            })
            errs = lint_dependency_order(str(root))
            phantom = [e for e in errs if "not declared in the top-level 'steps' array" in e.message]
            self.assertEqual(phantom, [], f"Expected no phantom-key errors. Got: {phantom}")


if __name__ == "__main__":
    unittest.main()
