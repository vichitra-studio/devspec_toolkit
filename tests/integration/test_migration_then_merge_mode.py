"""A migrated 1.1.1 host CAN reach a clean merge check: the mechanical stage, then a SCRIPTED judgement pass (WI-M10-15b).

The host is a git copy of the invented mini host (``tests/fixtures/migration/mini_host_1_1_1/``, never written).  The test
runs what a person or an agent runs, in the generated step order, through the same entry point as the shell
(``specdev_tools.cli.main``, in process):

1. ``align apply --auto`` (the mechanical stage) and one commit, as the migration guide says;
2. for each step NN of ``tests/fixtures/migration/mini_host_pass/pass.json``: the answers written with
   ``json patch|insert|delete --id`` (or ``--step``), ``attest --step NN --yes`` for the baseline links and the links the
   answers made suspect, ``canonical-autofix``, the worklist items of the step closed with
   ``align triage --resolve ID --note`` (the notes are in ``resolutions.json``), and ``spec-check --step NN``;
3. ``spec-check --merge``: zero errors; then ``align validate``: exit 0, the worklist and the capture gone, the stamp finished.

Every answer is INVENTED content about the invented host.  Nothing is deleted to get to zero: the only nodes that leave
are the open items the answers closed (their answer is applied to the text first) and one plan item that was dropped, and
that set is pinned below.  The toolkit root is the live checkout (it says 1.2.0).

The pass runs ONCE per session (a module-scoped fixture); every test reads what it recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
import yaml

from integration._mini_host_pass import PASS_DIR, SPEC, Host, digest, error_codes, run_scripted_pass
from unit.migration._support import MINI_HOST, REAL_ROOT, git, make_host

WORKLIST = f"{SPEC}/extras/migration/worklist.json"
CAPTURE = f"{SPEC}/extras/migration/capture.json"
STAMP = f"{SPEC}/specdev_version"

# The nodes the answers close or drop (the rest of the spec only grows): open items whose answer the pass applied to the
# text of the spec first, and one plan item (a waitlist the host decided not to build).
REMOVED_BY_ANSWER = frozenset(
    {"amb-fee-rounding", "amb-card-renewal", "amb-fee-rounding-2", "amb-sms-retry", "amb-sms-quota", "amb-sms-retry-2", "amb-pickup-hours", "RESERVE_WAITLIST_01"}
)


# ---------------------------------------------------------------------------
# What the run records
# ---------------------------------------------------------------------------


@dataclass
class Recorded:
    """What the one run saw."""

    host: Host
    fixture_before: dict[str, str]
    fixture_after: dict[str, str]
    migrated_digest_spec: dict[str, str]
    errors_before: dict[str, int]
    ids_before: frozenset[str]
    ids_after: frozenset[str]
    worklist_ids: list[str]
    failed_commands: list[tuple[str, list]] = field(default_factory=list)
    step_gates: dict[str, int] = field(default_factory=dict)
    later_gates: dict[str, dict[str, int]] = field(default_factory=dict)
    resolved: list[str] = field(default_factory=list)
    merge: dict = field(default_factory=dict)
    merge_code: int = -1
    validate: tuple[int, str, str] = (-1, "", "")
    changed_paths: list[str] = field(default_factory=list)
    stamp_after: dict = field(default_factory=dict)
    commands_run: int = 0


@pytest.fixture(scope="module")
def recorded(tmp_path_factory) -> Recorded:
    tmp = tmp_path_factory.mktemp("scripted_pass")
    fixture_before = digest(MINI_HOST)
    toolkit = REAL_ROOT
    host = Host(make_host(tmp, version="1.1.1"), toolkit)

    # 1. the mechanical stage, committed
    code, _out, err = host.specdev("align", "apply", str(host.spec), "--auto")
    assert code == 0, err
    host.commit("Migrate the spec to toolkit v1.2.0")
    migrated = git(host.root, "rev-parse", "HEAD").strip()
    _code, before = host.spec_check("--merge")
    rec = Recorded(
        host=host,
        fixture_before=fixture_before,
        fixture_after={},
        migrated_digest_spec=digest(host.spec),
        errors_before=error_codes(before),
        ids_before=host.node_ids(),
        ids_after=frozenset(),
        worklist_ids=[],
    )
    # 2. the judgement pass
    log = run_scripted_pass(host)
    rec.worklist_ids, rec.failed_commands, rec.step_gates = log.worklist_ids, log.failed_commands, log.step_gates
    rec.later_gates, rec.resolved, rec.commands_run = log.later_gates, log.resolved, log.commands_run

    # 3. merge mode, then the end of the migration
    rec.merge_code, rec.merge = host.spec_check("--merge")
    rec.validate = host.specdev("align", "validate", str(host.spec))
    rec.ids_after = host.node_ids()
    rec.stamp_after = yaml.safe_load((host.root / STAMP).read_text(encoding="utf-8"))
    rec.changed_paths = sorted(set(git(host.root, "diff", "--name-only", migrated).split()) | {line[3:] for line in git(host.root, "status", "--porcelain").splitlines()})
    rec.fixture_after = digest(MINI_HOST)
    return rec


# ---------------------------------------------------------------------------
# What the run shows
# ---------------------------------------------------------------------------


def test_the_mechanical_stage_leaves_the_errors_only_a_person_can_clear(recorded: Recorded) -> None:
    """The point of the pass: after the scripts, merge mode reports hundreds of errors, in the classes of the judgement pass."""
    assert sum(recorded.errors_before.values()) > 100
    # links a person gives (E520: derives_from, refines, schedules, connects_to...), baseline links to attest, nodes nothing links to
    assert {"E520", "E882", "E740", "E743", "E566", "E631", "E752"} <= set(recorded.errors_before)


def test_every_worklist_item_has_exactly_one_scripted_note(recorded: Recorded) -> None:
    notes = json.loads((PASS_DIR / "resolutions.json").read_text(encoding="utf-8"))
    assert sorted(notes) == sorted(recorded.worklist_ids)
    assert all(len(text) > 20 for text in notes.values())
    assert sorted(recorded.resolved) == sorted(recorded.worklist_ids)


def test_every_command_of_the_pass_succeeds(recorded: Recorded) -> None:
    assert recorded.failed_commands == []
    assert recorded.commands_run > 150


def test_a_finished_step_is_clear_while_the_later_steps_are_not(recorded: Recorded) -> None:
    """The migration-mode gate (M10-10): ``spec-check --step NN`` passes once step NN is done; 14 and 16a still block until their turn."""
    assert recorded.step_gates and all(code == 0 for code in recorded.step_gates.values()), recorded.step_gates
    assert {"00", "02a", "08", "12", "14", "16a"} <= set(recorded.step_gates)
    for done, later in recorded.later_gates.items():
        assert all(code != 0 for code in later.values()), (done, later)
    assert recorded.later_gates["00"] == {"14": 1, "16a": 1}
    assert recorded.later_gates["14"] == {"16a": 1} and recorded.later_gates["16a"] == {}


def test_merge_mode_reports_no_error_after_the_pass(recorded: Recorded) -> None:
    assert recorded.merge_code == 0
    assert recorded.merge["error_count"] == 0, [e["code"] for e in recorded.merge["errors"] if e.get("severity", "error") == "error"]


def test_align_validate_finishes_the_migration(recorded: Recorded) -> None:
    """The passing end M10-12 left for this bundle: exit 0, merge mode clean, worklist and capture gone, the stamp finished."""
    code, out, err = recorded.validate
    host = recorded.host
    assert code == 0, err
    assert "spec-check --merge: no error" in out and "worklist: every item is resolved" in out
    assert not (host.root / WORKLIST).exists() and not (host.root / CAPTURE).exists()
    assert not (host.root / SPEC / "extras" / "migration").exists()
    assert "migration_status" not in recorded.stamp_after
    assert recorded.stamp_after["toolkit_version"] == "1.2.0"
    assert [(entry["from"], entry["to"]) for entry in recorded.stamp_after["migration_history"]] == [("1.1.1", "1.2.0")]


def test_the_pass_deletes_only_the_open_items_it_answered(recorded: Recorded) -> None:
    """Zero errors is not reached by deleting nodes: what leaves is the answered open items and one dropped plan item; the rest only grows."""
    removed = recorded.ids_before - recorded.ids_after
    assert removed == REMOVED_BY_ANSWER
    added = recorded.ids_after - recorded.ids_before
    assert len(added) >= 10 and any(node.startswith("fix-") for node in added) and any(node.startswith("tc-") for node in added)


def test_the_mini_host_input_is_never_written(recorded: Recorded) -> None:
    assert recorded.fixture_before == recorded.fixture_after


def test_the_pass_writes_only_the_spec_and_the_host_files_it_names(recorded: Recorded) -> None:
    outside = {path for path in recorded.changed_paths if not path.startswith(f"{SPEC}/")}
    assert outside == {
        ".github/workflows/spec_validation.yml",
        "src/routes/tools.ts",
        "src/routes/reservations.ts",
        "src/routes/checkouts.ts",
    }
    workflow = (recorded.host.root / ".github/workflows/spec_validation.yml").read_text(encoding="utf-8")
    assert "validate-all" not in workflow and "specdev matrix" not in workflow


def test_the_frozen_plans_are_not_edited_by_the_pass(recorded: Recorded) -> None:
    """Closed plans are history: the pass leaves ``ms_catalog_plan.json`` and ``ms_late_fees_plan.json`` exactly as the migration wrote them."""
    after = digest(recorded.host.spec)
    for name in ("impl_context/ms_catalog_plan.json", "impl_context/ms_late_fees_plan.json"):
        assert after[name] == recorded.migrated_digest_spec[name], name


def test_git_history_of_the_host_holds_only_the_commits_the_script_makes(recorded: Recorded) -> None:
    subjects = git(recorded.host.root, "log", "--format=%s").splitlines()
    assert subjects == ["Judgement pass", "Add the route files the scaffold rows name", "Migrate the spec to toolkit v1.2.0", "host"]
