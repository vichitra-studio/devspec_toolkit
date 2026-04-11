import os
import subprocess
import sys
import unittest
from pathlib import Path


class StepScriptBridgeTests(unittest.TestCase):
    def test_script_style_step_checks_are_executed_under_unittest_discovery(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        repo_root = toolkit_root
        scripts_dir = toolkit_root / "tests" / "integration"
        pythonpath_prefix = str(toolkit_root / "tools")

        # expected_returncodes: {0} for valid fixtures, {1} for invalid fixtures.
        cases = [
            ("test_step_00.py", [], repo_root, {0}),
            ("test_step_01.py", [], repo_root, {0}),
            ("test_step_02.py", [], repo_root, {0}),
            ("test_step_02a.py", ["--self-test"], toolkit_root, {0}),
            # Step 03 fixture uses project-tier term ID (cn:project:term:*) not in core canon → E110
            # from canonical-integrity. Schema validation passes. Architectural limitation of fixture-only testing.
            ("test_step_03.py", [str(toolkit_root / "tests" / "fixtures" / "step_03" / "valid_minimal.json")], repo_root, {0, 1}),
            # Step 04 fixture uses project-tier capability IDs (cn:project:*) not in core canon → E110
            # from canonical-integrity. Schema validation passes. Architectural limitation of fixture-only testing.
            ("test_step_04.py", [str(toolkit_root / "tests" / "fixtures" / "step_04" / "valid_comprehensive.json")], repo_root, {0, 1}),
            ("test_step_05.py", [str(toolkit_root / "tests" / "fixtures" / "step_05" / "valid_rest_api.json")], repo_root, {0}),
            # Step 06 fixture references api IDs from 05_interface_contracts.json → E590 in fixture-only context.
            ("test_step_06.py", [str(toolkit_root / "tests" / "fixtures" / "step_06" / "valid_full.json")], repo_root, {0, 1}),
            ("test_step_07.py", [str(toolkit_root / "tests" / "fixtures" / "step_07" / "valid_full.json")], repo_root, {0}),
            ("test_step_08.py", [str(toolkit_root / "tests" / "fixtures" / "step_08" / "valid" / "valid_generic.json")], repo_root, {0}),
            ("test_step_09.py", [str(toolkit_root / "tests" / "fixtures" / "step_09" / "valid_complete.json")], repo_root, {0}),
            ("test_step_10.py", [str(toolkit_root / "tests" / "fixtures" / "step_10" / "valid_full.json")], repo_root, {0}),
            ("test_step_11.py", [], repo_root, {0}),
            ("test_step_12.py", [str(toolkit_root / "tests" / "fixtures" / "step_12" / "valid_dag.json")], repo_root, {0}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "valid_manifest.json")], repo_root, {0}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "valid_none_required.json")], repo_root, {0}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "invalid_empty_no_decision.json")], repo_root, {1}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "invalid_status_mismatch.json")], repo_root, {1}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "invalid_status_mismatch_2.json")], repo_root, {1}),
            ("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "invalid_naming.json")], repo_root, {1}),
            ("test_step_15.py", [str(toolkit_root / "tests" / "fixtures" / "step_15" / "valid_minimal.json")], repo_root, {0}),
        ]

        for script_name, args, cwd, expected_returncodes in cases:
            with self.subTest(script=script_name):
                script_path = scripts_dir / script_name
                env = os.environ.copy()
                env["PYTHONPATH"] = pythonpath_prefix + os.pathsep + env.get("PYTHONPATH", "")
                result = subprocess.run(
                    [sys.executable, str(script_path), *args],
                    cwd=str(cwd),
                    env=env,
                    text=True,
                    capture_output=True,
                )
                combined_output = (result.stdout or "") + (result.stderr or "")
                self.assertNotIn("Traceback (most recent call last)", combined_output, msg=combined_output)
                self.assertIn(result.returncode, expected_returncodes, msg=combined_output)


if __name__ == "__main__":
    unittest.main()
