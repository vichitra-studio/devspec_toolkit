"""Unit tests for the DEVSPEC-89 invariant_threat_coverage key in build_trace_matrix().

These tests exercise the branch added in DEVSPEC-89:

    inv_to_threats: dict[str, set[str]] = collections.defaultdict(set)
    for th in threats:
        for mitigation in th.get("mitigations", []):
            if _normalize_type(mitigation.get("type", "")) == "invariant":
                inv_id = mitigation.get("id", "")
                if inv_id:
                    inv_to_threats[inv_id].add(th["threat_id"])
    if inv_to_threats:
        result["invariant_threat_coverage"] = {
            inv_id: sorted(threat_ids)
            for inv_id, threat_ids in sorted(inv_to_threats.items())
        }

All tests use a *temp* repo_root (same as spec_dir) so the toolkit-side
entry_key_registry.json is absent, triggering `_registry_available=False` and
the legacy `_id`-suffix discovery path.  The DEVSPEC-89 block is independent
of discovery path, so this loses no fidelity on the targeted branch.

T1 regression guard (defaultdict(set)+add vs defaultdict(list)+append):
The dedup test asserts the threat id count is EXACTLY 1 when two mitigations
both resolve to the same inv_id.  Under the old list+append accumulator the
list would contain the threat id TWICE and that assertion would FAIL — which is
the correct regression signal.
"""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.validation.matrix import build_trace_matrix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_threats(spec_dir: Path, threats: list[dict]) -> None:
    """Write a minimal redteam spec JSON containing the given threat objects."""
    artifact = {
        "id": "test-redteam",
        "threats": threats,
    }
    (spec_dir / "11_redteam.json").write_text(json.dumps(artifact), encoding="utf-8")


def _build(tmp_path: Path) -> dict:
    """Invoke build_trace_matrix with tmp_path as both repo_root and spec_dir."""
    return build_trace_matrix(str(tmp_path), str(tmp_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInvariantThreatCoveragePresent:
    """Key is present and correctly populated when a threat carries a type=inv mitigation."""

    def test_invariant_threat_coverage_present(self, tmp_path: Path):
        """A single threat with type=inv mitigation → key maps inv_id to [threat_id]."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-001",
                "mitigations": [
                    {"type": "inv", "id": "inv-X"},
                ],
            }
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result, (
            "invariant_threat_coverage key missing from result; "
            "DEVSPEC-89 branch not reached or threat not discovered."
        )
        coverage = result["invariant_threat_coverage"]
        assert "inv-X" in coverage, (
            f"inv-X not found in invariant_threat_coverage; got keys: {list(coverage.keys())}"
        )
        assert coverage["inv-X"] == ["THR-001"], (
            f"Expected ['THR-001'] but got {coverage['inv-X']}"
        )

    def test_invariant_type_alias_resolves(self, tmp_path: Path):
        """type=invariant (full form, not alias) is also accepted."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-002",
                "mitigations": [
                    {"type": "invariant", "id": "inv-Y"},
                ],
            }
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result
        coverage = result["invariant_threat_coverage"]
        assert coverage.get("inv-Y") == ["THR-002"], (
            f"Expected ['THR-002'] for inv-Y but got {coverage.get('inv-Y')}"
        )


class TestInvariantThreatCoverageDedup:
    """Regression guard for T1: duplicate threat ids must be deduplicated.

    A threat with TWO mitigations that both resolve to the same invariant id
    (one via the 'inv' alias, one via the canonical 'invariant' label) must
    appear EXACTLY ONCE in that invariant's threat list.

    Under the old defaultdict(list)+append accumulator the list would contain
    the threat id TWICE, making the equality assertion fail — which is the
    correct regression signal for T1.
    """

    def test_invariant_threat_coverage_dedup_alias_and_canonical(self, tmp_path: Path):
        """type:inv alias + type:invariant canonical on same threat + same inv_id → count == 1."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-DUP",
                "mitigations": [
                    {"type": "inv", "id": "inv-DUP"},        # alias form
                    {"type": "invariant", "id": "inv-DUP"},  # canonical form, same inv_id
                ],
            }
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result, (
            "invariant_threat_coverage key missing — THR-DUP not discovered or no inv mitigations processed."
        )
        coverage = result["invariant_threat_coverage"]
        assert "inv-DUP" in coverage, f"inv-DUP not in coverage; got {list(coverage.keys())}"

        threat_list = coverage["inv-DUP"]
        # EXACT equality — must contain THR-DUP exactly once, not twice.
        assert threat_list == ["THR-DUP"], (
            f"Expected ['THR-DUP'] (deduplicated) but got {threat_list!r}. "
            "Under the old defaultdict(list)+append accumulator this would be ['THR-DUP','THR-DUP'] — "
            "this assertion is the regression guard for T1."
        )
        # Belt-and-suspenders: explicit count check
        assert threat_list.count("THR-DUP") == 1, (
            f"THR-DUP appears {threat_list.count('THR-DUP')} times; expected exactly 1."
        )

    def test_invariant_threat_coverage_dedup_two_inv_aliases_same_id(self, tmp_path: Path):
        """Two type:inv mitigations both referencing the same inv_id → threat id appears once."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-DEDUP2",
                "mitigations": [
                    {"type": "inv", "id": "inv-SAME"},
                    {"type": "inv", "id": "inv-SAME"},  # same id again
                ],
            }
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result
        coverage = result["invariant_threat_coverage"]
        threat_list = coverage.get("inv-SAME", [])
        assert threat_list == ["THR-DEDUP2"], (
            f"Expected ['THR-DEDUP2'] but got {threat_list!r}; duplicate mitigation entries "
            "must not produce duplicate threat ids."
        )
        assert threat_list.count("THR-DEDUP2") == 1


class TestInvariantThreatCoverageSorted:
    """Threat id lists are sorted in ascending order."""

    def test_invariant_threat_coverage_sorted(self, tmp_path: Path):
        """Multiple threats for the same invariant → threat id list is sorted, not insertion-ordered."""
        # Insert threats in REVERSE alphabetical order to prove sorting is applied.
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-003",
                "mitigations": [{"type": "inv", "id": "inv-SORT"}],
            },
            {
                "threat_id": "THR-001",
                "mitigations": [{"type": "inv", "id": "inv-SORT"}],
            },
            {
                "threat_id": "THR-002",
                "mitigations": [{"type": "inv", "id": "inv-SORT"}],
            },
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result
        coverage = result["invariant_threat_coverage"]
        threat_list = coverage.get("inv-SORT", [])
        assert threat_list == ["THR-001", "THR-002", "THR-003"], (
            f"Expected sorted list ['THR-001','THR-002','THR-003'] but got {threat_list!r}. "
            "Threats were inserted in reverse order to prove sorting is applied."
        )

    def test_invariant_keys_are_sorted(self, tmp_path: Path):
        """Multiple distinct invariants → the invariant_threat_coverage dict keys are sorted."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-A",
                "mitigations": [{"type": "inv", "id": "inv-ZZZ"}],
            },
            {
                "threat_id": "THR-B",
                "mitigations": [{"type": "inv", "id": "inv-AAA"}],
            },
        ])

        result = _build(tmp_path)

        assert "invariant_threat_coverage" in result
        keys = list(result["invariant_threat_coverage"].keys())
        assert keys == sorted(keys), (
            f"Invariant keys are not sorted; got {keys}"
        )
        assert keys == ["inv-AAA", "inv-ZZZ"], (
            f"Expected ['inv-AAA','inv-ZZZ'] but got {keys!r}"
        )


class TestInvariantThreatCoverageAbsent:
    """Key is absent when no inv mitigations are present (if inv_to_threats: guard)."""

    def test_absent_when_no_threats(self, tmp_path: Path):
        """Empty spec dir (no threat objects at all) → key absent."""
        # Write a minimal artifact with an empty threats list.
        artifact = {"id": "test-redteam", "threats": []}
        (tmp_path / "11_redteam.json").write_text(json.dumps(artifact), encoding="utf-8")

        result = _build(tmp_path)
        assert "invariant_threat_coverage" not in result, (
            "invariant_threat_coverage should be absent when there are no threats."
        )

    def test_absent_when_threats_have_no_inv_mitigations(self, tmp_path: Path):
        """Threats present but carrying ONLY non-inv mitigations → key absent.

        This is the non-vacuous form of the guard test: a discovered threat
        exists, but its mitigations are type=api, not type=inv.  The
        `if inv_to_threats:` guard must suppress the key.
        """
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-API-ONLY",
                "mitigations": [
                    {"type": "api", "id": "api-1"},   # non-inv mitigation
                    {"type": "fr", "id": "fr-1"},     # non-inv mitigation
                ],
            }
        ])

        result = _build(tmp_path)
        assert "invariant_threat_coverage" not in result, (
            "invariant_threat_coverage should be absent when threats have no inv mitigations; "
            "the `if inv_to_threats:` guard should prevent the key from being emitted."
        )

    def test_absent_when_inv_mitigation_has_empty_id(self, tmp_path: Path):
        """A type=inv mitigation with an empty id string is ignored → key absent if it is the only one."""
        _write_threats(tmp_path, [
            {
                "threat_id": "THR-EMPTY-ID",
                "mitigations": [
                    {"type": "inv", "id": ""},   # empty id — should be ignored
                ],
            }
        ])

        result = _build(tmp_path)
        assert "invariant_threat_coverage" not in result, (
            "A type=inv mitigation with empty id must not create an entry; key should be absent."
        )
