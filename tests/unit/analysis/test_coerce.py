"""Coerce-records unit tests — E520 emission for schema-bypass records."""
from __future__ import annotations

from specdev_tools.analysis.upstream_backlog import _coerce_records


def test_missing_id_emits_e520_and_skips():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"severity": "low", "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert len(errors) == 1
    assert errors[0].startswith("E520 ")
    assert "missing_id" in errors[0]


def test_invalid_severity_emits_e520_and_skips():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"id": "amb-1", "severity": "LOW", "impact": []},
            {"id": "amb-2", "severity": "unknown", "impact": []},
            {"id": "amb-3", "impact": []},  # severity missing
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert len(errors) == 3
    assert all(e.startswith("E520 ") for e in errors)
    assert all("invalid_severity" in e for e in errors)


def test_non_dict_ambiguity_emits_e520_and_skips():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": ["not-a-dict", 42]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert len(errors) == 2
    assert all("non_dict_ambiguity" in e for e in errors)


def test_null_execution_yields_empty_no_error():
    plan = {"id": "ms-x", "execution": None}
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert errors == []


def test_null_ambiguities_yields_empty_no_error():
    plan = {"id": "ms-x", "execution": {"emergent_ambiguities": None}}
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert errors == []


def test_non_list_ambiguities_yields_empty_no_error():
    plan = {"id": "ms-x", "execution": {"emergent_ambiguities": {"a": 1}}}
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert errors == []


def test_happy_path_coerces_null_status_to_tracking():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"id": "amb-1", "severity": "low", "status": None, "impact": []},
            {"id": "amb-2", "severity": "low", "impact": []},  # missing status
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert errors == []
    assert len(records) == 2
    for r in records:
        assert r["status"] == "tracking"
        assert r["status_unset"] is True


def test_explicit_tracking_status_preserves_unset_false():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"id": "amb-1", "severity": "low", "status": "tracking",
             "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert errors == []
    assert records[0]["status"] == "tracking"
    assert records[0]["status_unset"] is False


def test_non_string_description_coerced_to_empty():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"id": "amb-1", "severity": "low", "description": None,
             "impact": []},
        ]},
    }
    records, _ = _coerce_records(plan, "p.json")
    assert records[0]["description"] == ""


# ---------------------------------------------------------------------------
# DEVSPEC-123: plan.ambiguities[] (16a) must be scanned alongside
# execution.emergent_ambiguities[] (16b/16c) — previously it was never read.
# ---------------------------------------------------------------------------

def test_plan_ambiguities_are_extracted_and_tagged_with_origin():
    plan = {
        "id": "ms-x",
        "plan": {"ambiguities": [
            {"id": "amb-1", "severity": "blocking", "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert errors == []
    assert len(records) == 1
    assert records[0]["origin"] == "plan"
    assert records[0]["severity"] == "blocking"


def test_execution_records_are_tagged_with_origin():
    plan = {
        "id": "ms-x",
        "execution": {"emergent_ambiguities": [
            {"id": "amb-1", "severity": "low", "impact": []},
        ]},
    }
    records, _ = _coerce_records(plan, "p.json")
    assert records[0]["origin"] == "execution"


def test_both_arrays_combine_in_one_pass():
    plan = {
        "id": "ms-x",
        "plan": {"ambiguities": [
            {"id": "amb-plan", "severity": "non_blocking", "impact": []},
        ]},
        "execution": {"emergent_ambiguities": [
            {"id": "amb-exec", "severity": "low", "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert errors == []
    ids = {r["ambiguity_id"]: r["origin"] for r in records}
    assert ids == {"amb-plan": "plan", "amb-exec": "execution"}


def test_plan_ambiguity_invalid_severity_for_its_scale_emits_e520():
    # "low" is valid for execution but not for the plan's blocking/non_blocking scale.
    plan = {
        "id": "ms-x",
        "plan": {"ambiguities": [
            {"id": "amb-1", "severity": "low", "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert len(errors) == 1
    assert "invalid_severity" in errors[0]
    assert "origin=plan" in errors[0]


def test_duplicate_id_across_origins_yields_two_independent_records():
    # The same ambiguity id can legitimately appear in both plan.ambiguities[]
    # (16a) and execution.emergent_ambiguities[] (16b/16c) -- e.g. a 16a
    # ambiguity re-surfaced during execution under the same id. Origin, not
    # id, differentiates the two records; neither should be dropped/merged.
    plan = {
        "id": "ms-x",
        "plan": {"ambiguities": [
            {"id": "amb-shared", "severity": "blocking", "impact": []},
        ]},
        "execution": {"emergent_ambiguities": [
            {"id": "amb-shared", "severity": "high", "impact": []},
        ]},
    }
    records, errors = _coerce_records(plan, "p.json")
    assert errors == []
    assert len(records) == 2
    origins = {r["origin"] for r in records}
    assert origins == {"plan", "execution"}
    assert all(r["ambiguity_id"] == "amb-shared" for r in records)


def test_null_plan_section_yields_empty_no_error():
    plan = {"id": "ms-x", "plan": None}
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert errors == []


def test_null_plan_ambiguities_yields_empty_no_error():
    plan = {"id": "ms-x", "plan": {"ambiguities": None}}
    records, errors = _coerce_records(plan, "p.json")
    assert records == []
    assert errors == []
