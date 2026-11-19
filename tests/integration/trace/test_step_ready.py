"""``specdev step ready NN`` end to end, on the worked example (WI-M5-11)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.trace.gaps import CoverageGap

from unit.graph._synth import ROOT, run_cli
from unit.trace._lock_support import EXAMPLE_HOST, gap_providers  # noqa: F401  (a fixture)
from unit.trace.test_suspects import Example

API = "api-password-reset-confirm"
API_FILE = "05_interface_contracts.json"


@pytest.fixture
def host(tmp_path: Path) -> Example:
    """The worked example (spec, seed docs and a current lock) in a temporary host."""
    root = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    return Example(root)


def _flags(example: Example, repo_root: Path = ROOT) -> list[str]:
    return ["--repo-root", str(repo_root), "--spec-root", str(example.spec), "--git-root", str(example.host)]


def _ready(example: Example, step: str, *, repo_root: Path = ROOT) -> tuple[int, str]:
    return run_cli("step", "ready", step, *_flags(example, repo_root))


def _ready_json(example: Example, step: str, *, code: int, repo_root: Path = ROOT) -> dict[str, Any]:
    status, out = run_cli("step", "ready", step, *_flags(example, repo_root), "--json")
    assert status == code, out
    document = json.loads(out)
    assert isinstance(document, dict)
    return document


def _blocker_steps(document: dict[str, Any], reason: str | None = None) -> list[str]:
    """The steps that hold blockers (of *reason* when given), in the order listed."""
    return list(dict.fromkeys(blocker["step"] for blocker in document["blockers"] if reason in (None, blocker["reason"])))


def test_ready_when_upstream_present_and_clean(host: Example) -> None:
    assert _ready(host, "06") == (0, "step 06: ready\n")
    document = _ready_json(host, "06", code=0)
    assert document["ready"] is True and document["blockers"] == [] and document["replay_first"] is None
    assert document["upstream"] == ["00", "02", "04", "05"] and document["status"] == "PASS" and document["errors"] == []


def test_not_ready_when_upstream_step_has_suspect(host: Example) -> None:
    host.edit_criterion()
    code, out = _ready(host, "06")
    assert code == 1
    assert "step 06: not ready" in out and f"  step 05: {API}.derives_from -> fr-password-reset (content_changed, roots: ac-password-reset-3)" in out
    assert "replay step 05 first" in out and "E773" in out
    document = _ready_json(host, "06", code=1)
    assert document["ready"] is False and document["replay_first"] == "05" and _blocker_steps(document) == ["05"]
    assert document["errors"][0]["code"] == "E773" and "step 05" in document["errors"][0]["message"]
    assert _ready(host, "05") == (0, "step 05: ready\n")


def test_not_ready_when_upstream_artifact_absent(host: Example) -> None:
    """Step 07 does not link into step 05 but lists it as an input: a missing file blocks."""
    (host.spec / API_FILE).unlink()
    document = _ready_json(host, "07", code=1)
    assert [(b["step"], b["reason"]) for b in document["blockers"]] == [("05", "missing")]
    assert document["replay_first"] == "05"
    code, out = _ready(host, "07")
    assert "  step 05: no spec file yet" in out
    assert "\nwrite step 05 first\n" in out and "; write step 05 first" in out and "replay step" not in out


def test_ready_refuses_while_an_upstream_spec_file_cannot_be_read(host: Example) -> None:
    """The unreadable file gives no nodes, so nothing points at a suspect node and the file name exists: the gate must not say ready."""
    path = host.spec / "04_fr_list.json"
    path.write_text("<<<<<<< ours\n" + path.read_text(encoding="utf-8") + "=======\n>>>>>>> theirs\n", encoding="utf-8")
    code, out = _ready(host, "05")
    assert code == 1 and "E520" in out and "04_fr_list.json cannot be read" in out and "step ready refused" in out, out
    assert "step 05: ready" not in out
    status, text = run_cli("step", "ready", "05", *_flags(host), "--json")
    assert status == 1 and '"ready": true' not in text and '"E520"' in text
    # the reading commands keep printing, with their warning
    assert run_cli("stale", *_flags(host))[0] == 0


def test_link_target_step_not_in_required_spec_inputs_still_blocks(host: Example, tmp_path: Path) -> None:
    """The toolkit's step order names only step 00 as an input of 06; the links of 06 into step 05 still block it."""
    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    for folder in ("schema", "canon"):
        shutil.copytree(ROOT / folder, toolkit / folder)
    (toolkit / "tools").mkdir()
    for path in (ROOT / "tools").glob("*.json"):
        shutil.copy(path, toolkit / "tools")
    order_path = toolkit / "tools" / "step_order.json"
    order = json.loads(order_path.read_text(encoding="utf-8"))
    order["step_metadata"]["06"]["required_spec_inputs"] = ["00"]
    order_path.write_text(json.dumps(order), encoding="utf-8")
    host.edit_criterion()
    document = _ready_json(host, "06", code=1, repo_root=toolkit)
    assert document["upstream"] == ["00", "02", "04", "05"] and _blocker_steps(document) == ["05"]


def test_ready_blocked_by_coverage_gap_in_upstream_step(host: Example, gap_providers: Any) -> None:
    assert _ready(host, "06")[0] == 0
    gap_providers(lambda graph, lock: [CoverageGap("E740", "cap-account-recovery", "05")])
    document = _ready_json(host, "06", code=1)
    assert [(b["step"], b["reason"], b["code"], b["node"]) for b in document["blockers"]] == [("05", "gap", "E740", "cap-account-recovery")]
    assert "  step 05: coverage gap E740: cap-account-recovery" in _ready(host, "06")[1]
    assert _ready(host, "05") == (0, "step 05: ready\n")


def test_ready_ignores_historical(host: Example) -> None:
    """The suspect links of a closed milestone's nodes (the step 14 test cases) do not block the step after them.

    The example has no step 13a file, which 16a lists as an input, so 16a stays blocked by that; only suspects are compared.
    """
    host.edit_criterion()
    assert _blocker_steps(_ready_json(host, "16a", code=1), "suspect") == ["14"]
    host.close_milestone()
    document = _ready_json(host, "16a", code=1)
    assert _blocker_steps(document, "suspect") == [] and [(b["step"], b["reason"]) for b in document["blockers"]] == [("13a", "missing")]


@pytest.mark.parametrize("step", ["99", "6", "seed"])
def test_unknown_step_is_refused(host: Example, step: str) -> None:
    code, text = _ready(host, step)
    assert code == 1 and text.startswith("E706") and f"no step {step!r}" in text and "known steps: 00, 01, 02, 02a" in text
    document = _ready_json(host, step, code=1)
    assert document["errors"][0]["code"] == "E706" and f"no step {step!r}" in document["errors"][0]["message"]
