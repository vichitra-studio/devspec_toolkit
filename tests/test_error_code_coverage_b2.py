import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.errors import ERROR_CODES


class ErrorCodeCoverageB2Tests(unittest.TestCase):
    def test_expected_codes_present(self):
        expected = {
            "E110",
            "E120",
            "E130",
            "E140",
            "E210",
            "E310",
            "E410",
            "E420",
            "E510",
            "E520",
            "E521",
            "E530",
            "E540",
            "E550",
            "W110",
            "W120",
            "W130",
        }
        self.assertTrue(expected.issubset(set(ERROR_CODES.keys())))


if __name__ == "__main__":
    unittest.main()
