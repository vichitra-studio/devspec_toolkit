"""``specdev step create NN --from <draft>`` end to end, on the worked example taken apart into drafts (WI-M5-10).

Each test copies the example into a temporary host, moves the step files from the step under test onward (and the lock)
into a ``drafts`` folder, and creates them again through the command in this process (``run_cli``).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.trace.lockfile import lock_path, read_lock

from unit.graph._synth import ROOT, run_cli
from unit.trace._lock_support import EXAMPLE_HOST

STEP_FILES = {
    "00": "00_charter.json", "01": "01_capabilities.json", "02": "02_system_sketch.json", "02a": "02a_delivery_baseline.json",
    "03": "03_glossary.json", "04": "04_fr_list.json", "05": "05_interface_contracts.json", "06": "06_invariants.json",
    "07": "07_nfrs.json", "08": "08_fixtures.json", "09": "09_impl_plan.json", "10": "10_governance.json",
    "11": "11_redteam.json", "12": "12_ci_gates.json", "13": "13_extension_manifest.json", "14": "14_roadmap.json",
    "15": "15_scaffold.json",
}
FR_STEP = "04"
PLAN_ITEM_ENTRY = ("PWRESET_CONFIRM_EXPIRED_01", "realises", "tc-confirm-expired-token")


class Host:
    """A temporary host holding the worked example up to a step; the files from that step on wait in ``drafts``."""

    def __init__(self, root: Path, first_missing: str) -> None:
        self.root = root
        self.spec = root / "spec"
        self.drafts = root.parent / "drafts"
        self.drafts.mkdir()
        shutil.copytree(EXAMPLE_HOST, root)
        steps = list(STEP_FILES)
        for step in steps[steps.index(first_missing):]:
            shutil.move(self.spec / STEP_FILES[step], self.drafts / STEP_FILES[step])
        shutil.rmtree(self.spec / "impl_context")
        (self.spec / "16_impl_context.json").unlink()
        Path(lock_path(str(self.spec))).unlink()

    def flags(self) -> list[str]:
        return ["--repo-root", str(ROOT), "--spec-root", str(self.spec), "--git-root", str(self.root)]

    def draft(self, step: str) -> Path:
        return self.drafts / STEP_FILES[step]

    def create(self, step: str, *args: str, draft: Path | None = None, code: int = 0) -> str:
        status, out = run_cli("step", "create", step, "--from", str(draft or self.draft(step)), *args, *self.flags())
        assert status == code, out
        return out

    def create_json(self, step: str, *args: str, draft: Path | None = None, code: int = 0) -> dict[str, Any]:
        out = self.create(step, *args, "--json", draft=draft, code=code)
        document = json.loads(out)
        assert isinstance(document, dict)
        return document

    def snapshot(self) -> dict[Path, bytes]:
        """Every file of the spec folder as bytes (the lock included)."""
        return {path: path.read_bytes() for path in self.spec.rglob("*") if path.is_file()}

    def lock_keys(self) -> set[tuple[str, str, str]]:
        return {entry.key for entry in read_lock(str(self.spec)).entries}


@pytest.fixture
def host(tmp_path: Path) -> Host:
    """The example without the step files from step 04 on."""
    return Host(tmp_path / "host", FR_STEP)


def _without_ids(draft: Path, dest: Path) -> Path:
    """A copy of the step 04 draft with every ``fr_id`` and ``criterion_id`` removed."""
    document = json.loads(draft.read_text(encoding="utf-8"))
    for fr in document["functional_requirements"]:
        fr.pop("fr_id")
        for criterion in fr["acceptance_criteria"]:
            criterion.pop("criterion_id")
    dest.write_text(json.dumps(document), encoding="utf-8")
    return dest


def _with_draft(host: Host, name: str, change: Any) -> Path:
    """A copy of the step 04 draft changed by *change(document)*."""
    document = json.loads(host.draft(FR_STEP).read_text(encoding="utf-8"))
    change(document)
    path = host.drafts / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_step_create_writes_artifact_mints_ids_and_lock_entries(host: Host) -> None:
    draft = _without_ids(host.draft(FR_STEP), host.drafts / "no_ids.json")
    document = host.create_json(FR_STEP, draft=draft)
    written = json.loads((host.spec / STEP_FILES[FR_STEP]).read_text(encoding="utf-8"))
    ids = [fr["fr_id"] for fr in written["functional_requirements"]]
    criteria = [criterion["criterion_id"] for fr in written["functional_requirements"] for criterion in fr["acceptance_criteria"]]
    assert document["written"] is True and document["action"] == "create" and document["file"] == STEP_FILES[FR_STEP]
    assert ids and all(fr_id.startswith("fr-") for fr_id in ids) and criteria and all(c.startswith("ac-") for c in criteria)
    assert set(document["minted"]) == {*ids, *criteria}
    assert {key[0] for key in host.lock_keys()} >= set(ids)
    assert {(item["holder"], item["field"]) for item in document["lock"]["written"]} == {(fr_id, "derives_from") for fr_id in ids}


def test_step_create_refuses_existing_artifact(host: Host) -> None:
    host.create(FR_STEP)
    before = host.snapshot()
    document = host.create_json(FR_STEP, code=1)
    assert document["errors"][0]["code"] == "E767" and "already has a spec file" in document["errors"][0]["message"]
    assert host.snapshot() == before


@pytest.mark.parametrize(
    ("name", "change", "needle"),
    [
        ("bad_enum.json", lambda doc: doc["functional_requirements"][0].update(priority="bogus"), "not valid against its schema"),
        ("no_list.json", lambda doc: doc.pop("functional_requirements"), "not valid against its schema"),
        ("bad_link.json", lambda doc: doc["functional_requirements"][0].update(derives_from=["cap-no-such-capability"]), "cap-no-such-capability"),
    ],
)
def test_step_create_invalid_draft_writes_nothing(host: Host, name: str, change: Any, needle: str) -> None:
    before = host.snapshot()
    document = host.create_json(FR_STEP, draft=_with_draft(host, name, change), code=1)
    assert document["errors"][0]["code"] == "E767" and needle in document["errors"][0]["message"]
    assert host.snapshot() == before and not (host.spec / STEP_FILES[FR_STEP]).exists()


def test_step_create_shows_every_link_target(host: Host) -> None:
    draft = json.loads(host.draft(FR_STEP).read_text(encoding="utf-8"))
    expected = {(fr["fr_id"], "derives_from", target) for fr in draft["functional_requirements"] for target in fr["derives_from"]}
    document = host.create_json(FR_STEP)
    assert {(item["holder"], item["field"], item["target"]) for item in document["targets"]} == expected
    assert all(item["text"] and item["kind"] and item["step"] for item in document["targets"])


def test_step_create_text_lists_each_target_with_its_contract_text(host: Host) -> None:
    out = host.create(FR_STEP)
    lines = out.splitlines()
    assert lines[0] == f"created fr-list-password-reset ({STEP_FILES[FR_STEP]} .)"
    targets = [line for line in lines if line.startswith("  fr-") and " -> " in line]
    assert len(targets) == 2 and all("(capability, step 01)" in line and "A registered member can regain access" in line for line in targets)
    assert sum(line.startswith("lock entry written: ") for line in lines) == 2


def test_step_create_dry_run_prints_the_same_and_writes_nothing(host: Host) -> None:
    before = host.snapshot()
    dry = host.create_json(FR_STEP, "--dry-run")
    assert host.snapshot() == before
    dry_text = host.create(FR_STEP, "--dry-run")
    assert dry_text.splitlines()[0] == f"[dry-run] would create fr-list-password-reset ({STEP_FILES[FR_STEP]} .)"
    real = host.create_json(FR_STEP)
    assert dry["written"] is False and real["written"] is True
    assert {**dry, "written": True} == real


def test_step_create_of_section12_steps_in_order_reproduces_lock_example(tmp_path: Path) -> None:
    """Creating steps 00 to 15 from their drafts, in order, leaves the lock of the worked example without its step 16 entry."""
    host = Host(tmp_path / "host", "00")
    for step in STEP_FILES:
        host.create(step)
    expected = {entry for entry in read_lock(str(EXAMPLE_HOST / "spec")).entries if entry.key != PLAN_ITEM_ENTRY}
    created = read_lock(str(host.spec))
    assert PLAN_ITEM_ENTRY not in {entry.key for entry in created.entries}
    assert set(created.entries) == expected
    for step, name in STEP_FILES.items():
        assert json.loads((host.spec / name).read_text(encoding="utf-8")) == json.loads((EXAMPLE_HOST / "spec" / name).read_text(encoding="utf-8")), step


@pytest.mark.parametrize(("step", "needle"), [("13a", "creates steps 00, 01"), ("16", "creates steps 00, 01")])
def test_step_create_refuses_13a_and_an_unknown_step(host: Host, step: str, needle: str) -> None:
    document = host.create_json(step, draft=host.draft(FR_STEP), code=1)
    (error,) = document["errors"]
    assert error["code"] == "E767" and f"step {step} has no spec file that step create writes" in error["message"] and needle in error["message"]
    status, out = run_cli("step", "create", "99", "--from", str(host.draft(FR_STEP)), *host.flags())
    assert status == 1 and out.startswith("E706") and "no step '99'" in out and "known steps: 00, 01" in out
    status, out = run_cli("step", "create", "99", "--from", str(host.draft(FR_STEP)), *host.flags(), "--json")
    assert status == 1 and json.loads(out)["errors"][0]["code"] == "E706"
    assert not (host.spec / STEP_FILES[FR_STEP]).exists()


def test_step_create_refuses_a_draft_that_cannot_be_used(host: Host) -> None:
    missing = host.drafts / "missing.json"
    broken = host.drafts / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    listed = host.drafts / "list.json"
    listed.write_text("[]", encoding="utf-8")
    for path, needle in ((missing, "cannot read the draft"), (broken, "is not valid JSON"), (listed, "must be a JSON object")):
        error = host.create_json(FR_STEP, draft=path, code=1)["errors"][0]
        assert error["code"] == "E767" and needle in error["message"]


def test_step_create_refuses_a_draft_of_another_step(host: Host) -> None:
    other = _with_draft(host, "other.json", lambda doc: doc.update({"$schema": "vc:05-interface-contracts"}))
    message = host.create_json(FR_STEP, draft=other, code=1)["errors"][0]["message"]
    assert "the schema of step 04 is 'vc:04-fr-list'" in message and not (host.spec / STEP_FILES[FR_STEP]).exists()


def test_step_create_needs_from(host: Host) -> None:
    status, out = run_cli("step", "create", FR_STEP, *host.flags())
    assert status == 2 and "--from" in out
