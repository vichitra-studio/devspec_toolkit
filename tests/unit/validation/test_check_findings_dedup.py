"""``spec_check.check_findings``: a finding that two checks both report is one finding of the gate."""
from __future__ import annotations

from specdev_tools.core.errors import SpecError
from specdev_tools.validation.spec_check import check_findings


def test_the_completeness_check_findings_are_not_counted_with_the_traceability_closure_ones() -> None:
    shared = SpecError(code="E750", message="fr-a has no covering test")
    other = SpecError(code="E751", message="fr-b has no covering test")
    checks = {
        "traceability-closure": {"errors": [shared, other]},
        "completeness-check": {"errors": [shared]},
        "graph": {"errors": []},
    }
    assert check_findings(checks) == [shared, other]
