"""W->E promotion in spec-check's per-check results.

Regression coverage for the two findings fixed in spec_check.py:

  - c6782c829f15: ``run_spec_check`` / ``run_spec_check_json`` returned the
    aggregate error list without applying ``_apply_we_promotion``, so under an
    active promotion contract (``SPECDEV_WARNINGS_AS_ERRORS`` /
    ``SPECDEV_PROMOTE_CODES``) promoted W-codes were still emitted W-prefixed in
    the JSON ``findings`` and the returned codes.
  - 470d4be9aac6: ``_classify`` was run *before* promotion, so a check whose
    only errors were promotable W-codes was reported WARN instead of FAIL under
    that contract.

Both surfaces are now built through the single ``_check_result`` fix-point,
which promotes first. These tests exercise that helper directly (it is the only
place per-check results are constructed) under each env configuration.
"""

from __future__ import annotations

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import SpecError
from specdev_tools.validation.spec_check import _check_result

# W615 is in PROMOTABLE_PAIRS (-> E615). Used as a representative promotable
# W-code emitted by one of checks #2-#14 (step-11 invariant/threat drift).
PROMOTABLE_W = "W615"
PROMOTED_E = "E615"


@pytest.fixture(autouse=True)
def _isolate_config():
    """Each test sees a freshly-parsed config; restore the default afterwards."""
    reset_config()
    yield
    reset_config()


def _warn_only() -> list[SpecError]:
    return [SpecError(code=PROMOTABLE_W, message="invariant unexercised by threat")]


def test_no_promotion_env_keeps_warn(monkeypatch):
    """Default (no promotion env): status WARN, code stays W-prefixed."""
    monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
    monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
    reset_config()

    result = _check_result(_warn_only())

    assert result["status"] == "WARN"
    assert result["warning_count"] == 1
    assert result["error_count"] == 0
    assert [e.code for e in result["errors"]] == [PROMOTABLE_W]


def test_warnings_as_errors_promotes_and_flips_status(monkeypatch):
    """SPECDEV_WARNINGS_AS_ERRORS=1: status FAIL, stored code is E-prefixed.

    Covers both findings at once: _classify post-promotion (470d4be9aac6) and
    the stored/returned errors carrying the promoted code (c6782c829f15).
    """
    monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
    monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
    reset_config()

    result = _check_result(_warn_only())

    assert result["status"] == "FAIL"
    assert result["error_count"] == 1
    assert result["warning_count"] == 0
    assert [e.code for e in result["errors"]] == [PROMOTED_E]


def test_selective_promote_codes_promotes_listed_code(monkeypatch):
    """SPECDEV_PROMOTE_CODES listing the W-code promotes just that code."""
    monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", PROMOTABLE_W)
    reset_config()

    result = _check_result(_warn_only())

    assert result["status"] == "FAIL"
    assert [e.code for e in result["errors"]] == [PROMOTED_E]


def test_selective_promote_codes_leaves_unlisted_warn(monkeypatch):
    """A promote list that does not include the emitted code leaves it WARN."""
    monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
    monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571")
    reset_config()

    result = _check_result(_warn_only())

    assert result["status"] == "WARN"
    assert [e.code for e in result["errors"]] == [PROMOTABLE_W]
