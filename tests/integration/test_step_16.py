import unittest
import os
import json
from specdev_tools.validate import validate_file

class TestStep16(unittest.TestCase):
    def setUp(self):
        # Calculate paths relative to this test file
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        self.fixtures_dir = os.path.join(self.repo_root, "devspec_toolkit/tests/fixtures/step_16")

    def test_valid_minimal(self):
        path = os.path.join(self.fixtures_dir, "valid_minimal.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid minimal fixture should pass. Errors: {errors}")

    def test_valid_full(self):
        path = os.path.join(self.fixtures_dir, "valid_full.json")
        errors = validate_file(self.repo_root, path)
        self.assertEqual(errors, [], f"Valid full fixture should pass. Errors: {errors}")

    def test_invalid_missing_evidence(self):
        # Expect failure because 'verified' implementation requires evidence in actions
        path = os.path.join(self.fixtures_dir, "invalid_missing_evidence.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (missing evidence) should fail validation")
        # Optional: check message content
        # print(f"Invalid Evidence Errors: {errors}")

    def test_invalid_bad_enum(self):
        # Expect failure due to bad enum
        path = os.path.join(self.fixtures_dir, "invalid_bad_enum.json")
        errors = validate_file(self.repo_root, path)
        self.assertTrue(len(errors) > 0, "Invalid fixture (bad enum) should fail validation")
        
if __name__ == '__main__':
    unittest.main()
