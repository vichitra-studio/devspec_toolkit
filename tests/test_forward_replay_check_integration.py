import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from specdev_tools.forward_replay_check import check_forward_replay


class ForwardReplayCheckIntegrationTests(unittest.TestCase):
    def test_real_git_history_detects_missing_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_step_order(root, ["00", "01", "02"])
            self._write_spec(root, "00_charter.json", "{}")
            self._write_spec(root, "01_capabilities.json", "{}")
            self._write_spec(root, "02_system_sketch.json", "{}")
            self._commit_all(root, "base")

            self._run(root, ["git", "checkout", "-b", "feature/replay"])
            self._write_spec(root, "00_charter.json", "{\"changed\":true}")
            self._commit_all(root, "change step 00")

            errs = check_forward_replay(str(root), base_ref="main")
            self.assertTrue(any("missing_downstream=01" in e for e in errs))

    def test_real_git_history_no_error_when_all_downstream_changed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_step_order(root, ["00", "01", "02"])
            self._write_spec(root, "00_charter.json", "{}")
            self._write_spec(root, "01_capabilities.json", "{}")
            self._write_spec(root, "02_system_sketch.json", "{}")
            self._commit_all(root, "base")

            self._run(root, ["git", "checkout", "-b", "feature/replay"])
            self._write_spec(root, "00_charter.json", "{\"changed\":true}")
            self._write_spec(root, "01_capabilities.json", "{\"changed\":true}")
            self._write_spec(root, "02_system_sketch.json", "{\"changed\":true}")
            self._commit_all(root, "change all")

            errs = check_forward_replay(str(root), base_ref="main")
            self.assertFalse(any("E550" in e for e in errs))

    def _init_repo(self, root: Path) -> None:
        self._run(root, ["git", "init"])
        self._run(root, ["git", "checkout", "-b", "main"])
        self._run(root, ["git", "config", "user.email", "dev@example.com"])
        self._run(root, ["git", "config", "user.name", "Dev"])
        (root / "tools").mkdir(parents=True, exist_ok=True)
        (root / "spec").mkdir(parents=True, exist_ok=True)

    def _write_step_order(self, root: Path, steps: list[str]) -> None:
        (root / "tools" / "step_order.json").write_text(
            json.dumps({"steps": steps, "allowed_upstream_dependencies": {s: steps[:i] for i, s in enumerate(steps)}}),
            encoding="utf-8",
        )

    def _write_spec(self, root: Path, name: str, content: str) -> None:
        (root / "spec" / name).write_text(content, encoding="utf-8")

    def _commit_all(self, root: Path, message: str) -> None:
        self._run(root, ["git", "add", "."])
        self._run(root, ["git", "commit", "-m", message])

    def _run(self, root: Path, cmd: list[str]) -> None:
        subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
