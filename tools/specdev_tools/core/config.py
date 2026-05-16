"""Centralised environment variable configuration.

Reads all ``SPECDEV_*`` env vars once and exposes them as typed properties
via the :class:`SpecdevConfig` singleton.

Created by FIX-003 (Batch 0).
"""
from __future__ import annotations

import os
import threading


def _parse_bool(key: str) -> bool:
    """Parse a boolean env var (``1``, ``true``, ``yes`` → True)."""
    return os.environ.get(key, "").strip().lower() in ("1", "true", "yes")


def _parse_set(key: str) -> set[str]:
    """Parse a comma-separated env var into a set of stripped strings."""
    raw = os.environ.get(key, "").strip()
    if not raw:
        return set()
    return {c.strip() for c in raw.split(",") if c.strip()}


class SpecdevConfig:
    """Typed, read-only view of all ``SPECDEV_*`` environment variables.

    Attributes
    ----------
    warnings_as_errors : bool
        ``SPECDEV_WARNINGS_AS_ERRORS`` — promote all W-codes to E-codes.
    promote_codes : set[str]
        ``SPECDEV_PROMOTE_CODES`` — selective W→E promotion set.
    matrix_strict : bool
        ``SPECDEV_MATRIX_STRICT`` — make matrix coverage errors fatal.
    replay_base_ref : str | None
        ``SPECDEV_REPLAY_BASE_REF`` — explicit git base ref override.
    replay_diff_error_mode : str
        ``SPECDEV_REPLAY_DIFF_ERROR_MODE`` — ``"error"`` or ``"ignore"``.
    staleness_threshold : int
        ``SPECDEV_STALENESS_THRESHOLD`` — minimum new upstream tokens for W595 (default 3).
    """

    __slots__ = (
        "warnings_as_errors",
        "promote_codes",
        "matrix_strict",
        "replay_base_ref",
        "replay_diff_error_mode",
        "staleness_threshold",
    )

    def __init__(self) -> None:
        self.warnings_as_errors: bool = _parse_bool("SPECDEV_WARNINGS_AS_ERRORS")
        self.promote_codes: set[str] = _parse_set("SPECDEV_PROMOTE_CODES")
        self.matrix_strict: bool = _parse_bool("SPECDEV_MATRIX_STRICT")

        raw_base_ref = os.environ.get("SPECDEV_REPLAY_BASE_REF", "").strip()
        self.replay_base_ref: str | None = raw_base_ref if raw_base_ref else None

        self.replay_diff_error_mode: str = os.environ.get(
            "SPECDEV_REPLAY_DIFF_ERROR_MODE", ""
        ).strip().lower()

        try:
            self.staleness_threshold: int = int(
                os.environ.get("SPECDEV_STALENESS_THRESHOLD", "3")
            )
        except (ValueError, TypeError):
            self.staleness_threshold = 3

    def __repr__(self) -> str:
        attrs = ", ".join(f"{attr}={getattr(self, attr)!r}" for attr in self.__slots__)
        return f"SpecdevConfig({attrs})"


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_instance: SpecdevConfig | None = None


def get_config() -> SpecdevConfig:
    """Return the cached :class:`SpecdevConfig` singleton.

    Thread-safe.  Reads env vars on first call only.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SpecdevConfig()
    return _instance


def reset_config() -> None:
    """Discard the cached config (useful for tests that modify env vars)."""
    global _instance
    with _lock:
        _instance = None
