"""Tests for specdev_tools.core.config — centralised environment config.

Created by FIX-045 (Batch 5).
"""
from __future__ import annotations

import pytest

from specdev_tools.core.config import SpecdevConfig, get_config, reset_config


@pytest.fixture(autouse=True)
def _clean_config():
    """Reset singleton before and after each test."""
    reset_config()
    yield
    reset_config()


class TestSpecdevConfig:
    """Tests for SpecdevConfig direct instantiation."""

    def test_defaults_no_env(self, monkeypatch):
        for var in (
            "SPECDEV_WARNINGS_AS_ERRORS",
            "SPECDEV_PROMOTE_CODES",
            "SPECDEV_MATRIX_STRICT",
            "SPECDEV_REPLAY_BASE_REF",
            "SPECDEV_REPLAY_DIFF_ERROR_MODE",
            "SPECDEV_STALENESS_THRESHOLD",
        ):
            monkeypatch.delenv(var, raising=False)
        cfg = SpecdevConfig()
        assert cfg.warnings_as_errors is False
        assert cfg.promote_codes == set()
        assert cfg.matrix_strict is False
        assert cfg.replay_base_ref is None
        assert cfg.replay_diff_error_mode == ""
        assert cfg.staleness_threshold == 3

    def test_all_env_vars_set(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571,W593")
        monkeypatch.setenv("SPECDEV_MATRIX_STRICT", "true")
        monkeypatch.setenv("SPECDEV_REPLAY_BASE_REF", "origin/develop")
        monkeypatch.setenv("SPECDEV_REPLAY_DIFF_ERROR_MODE", "error")
        monkeypatch.setenv("SPECDEV_STALENESS_THRESHOLD", "5")
        cfg = SpecdevConfig()
        assert cfg.warnings_as_errors is True
        assert cfg.promote_codes == {"W571", "W593"}
        assert cfg.matrix_strict is True
        assert cfg.replay_base_ref == "origin/develop"
        assert cfg.replay_diff_error_mode == "error"
        assert cfg.staleness_threshold == 5

    def test_boolean_true_variants(self, monkeypatch):
        for val in ("1", "true", "yes", "TRUE", "Yes", " 1 "):
            monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", val)
            cfg = SpecdevConfig()
            assert cfg.warnings_as_errors is True, f"Expected True for {val!r}"

    def test_boolean_false_variants(self, monkeypatch):
        for val in ("0", "false", "no", "", "anything"):
            monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", val)
            cfg = SpecdevConfig()
            assert cfg.warnings_as_errors is False, f"Expected False for {val!r}"

    def test_promote_codes_single(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "W571")
        cfg = SpecdevConfig()
        assert cfg.promote_codes == {"W571"}

    def test_promote_codes_with_spaces(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", " W571 , W593 , W595 ")
        cfg = SpecdevConfig()
        assert cfg.promote_codes == {"W571", "W593", "W595"}

    def test_promote_codes_empty_string(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_PROMOTE_CODES", "")
        cfg = SpecdevConfig()
        assert cfg.promote_codes == set()

    def test_staleness_threshold_invalid(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_STALENESS_THRESHOLD", "not-a-number")
        cfg = SpecdevConfig()
        assert cfg.staleness_threshold == 3  # default fallback

    def test_replay_base_ref_empty(self, monkeypatch):
        monkeypatch.setenv("SPECDEV_REPLAY_BASE_REF", "   ")
        cfg = SpecdevConfig()
        assert cfg.replay_base_ref is None

    def test_repr(self, monkeypatch):
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        monkeypatch.delenv("SPECDEV_PROMOTE_CODES", raising=False)
        monkeypatch.delenv("SPECDEV_MATRIX_STRICT", raising=False)
        monkeypatch.delenv("SPECDEV_REPLAY_BASE_REF", raising=False)
        monkeypatch.delenv("SPECDEV_REPLAY_DIFF_ERROR_MODE", raising=False)
        monkeypatch.delenv("SPECDEV_STALENESS_THRESHOLD", raising=False)
        cfg = SpecdevConfig()
        r = repr(cfg)
        assert r.startswith("SpecdevConfig(")
        assert "warnings_as_errors=False" in r


class TestGetConfig:
    """Tests for get_config() singleton factory."""

    def test_returns_instance(self, monkeypatch):
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        cfg = get_config()
        assert isinstance(cfg, SpecdevConfig)

    def test_returns_same_instance(self, monkeypatch):
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        a = get_config()
        b = get_config()
        assert a is b

    def test_reset_clears_singleton(self, monkeypatch):
        monkeypatch.delenv("SPECDEV_WARNINGS_AS_ERRORS", raising=False)
        a = get_config()
        reset_config()
        b = get_config()
        assert a is not b
