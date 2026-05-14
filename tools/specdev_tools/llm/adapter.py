"""adapter.py — LLMAdapter Protocol for the inner/outer loop.

Defines the injectable adapter interface so loop_inner.py (and future loop
implementations) stay decoupled from any concrete HTTP transport.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMAdapter(Protocol):
    def chat(self, system: str, user: str) -> str:
        """Call the LLM with system + user messages.

        Returns raw response string (JSON-mode expected by the inner loop).
        The caller is responsible for JSON parsing and schema validation.
        """
        ...
