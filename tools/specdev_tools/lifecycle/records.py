"""Helpers the lifecycle commands share when they write a record: who ran it, when, and the next id.

``git_author`` and ``now_utc`` are how an author and a time reach a record: written by the tool, never by an agent.
The ids are the global zero-padded ids of the record kinds (``rec-0001``, ``dep-0001``, ``so-<milestone>-0001``) and the
per-item action ids of a plan (``a01``).
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.errors import refusal
from ..graph.gitview import git_reason, run_git

_IDENT = re.compile(r"^(?P<name>.*?) <(?P<email>[^>]*)> \d+ [+-]\d{4}$")
_ACTION_ID = re.compile(r"^a(\d{2,})$")
_ID_WIDTH = 4
_CI_AUTHOR = "ci"


@dataclass(frozen=True)
class GitAuthor:
    """The name and email git would put on a commit made now."""

    name: str
    email: str

    def as_record(self) -> dict[str, str]:
        """The ``git_author`` object of a record: ``{"name": ..., "email": ...}``."""
        return {"name": self.name, "email": self.email}


def git_author(git_root: str, *, ci_fallback: bool = False) -> GitAuthor:
    """The author git names for *git_root* (``git var GIT_AUTHOR_IDENT``).

    With *ci_fallback* an author git cannot name is ``{"name": "ci", "email": ""}`` (``plan record --at-deploy`` runs
    in a deploy job where no identity is often configured).

    Raises:
        FindingError: E767 when git cannot name an author with a name and an email and *ci_fallback* is not set; E708
            when git is missing.
    """
    process = run_git(git_root, ["var", "GIT_AUTHOR_IDENT"])
    match = _IDENT.match(process.stdout.decode("utf-8", errors="replace").strip()) if process.returncode == 0 else None
    if match and match["name"] and match["email"]:
        return GitAuthor(match["name"], match["email"])
    if ci_fallback:
        return GitAuthor(_CI_AUTHOR, "")
    reason = git_reason(process) if process.returncode != 0 else "its name or email is empty"
    raise refusal("E767", f"git cannot name an author for the record ({reason}); set `git config user.name` and `git config user.email`, then run the command again")


def now_utc() -> str:
    """The wall-clock time now in UTC, ``YYYY-MM-DDTHH:MM:SSZ``: informational, tool-written, never compared."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_number(numbers: Iterable[int]) -> int:
    return max(numbers, default=0) + 1


def mint_id(prefix: str, existing_ids: Iterable[str]) -> str:
    """The next global id ``<prefix>-<NNNN>``: one past the highest number among *existing_ids* of that prefix, four digits.

    The number counts from the ids that exist now: when the highest id is deleted, its number is minted again.  *prefix* has
    no trailing hyphen: ``rec``, ``dep``, ``evd``, ``so-<milestone id>``.
    """
    taken = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    numbers = (int(m.group(1)) for m in map(taken.match, existing_ids) if m)
    return f"{prefix}-{_next_number(numbers):0{_ID_WIDTH}d}"


def mint_action_id(existing_action_ids_in_item: Iterable[str]) -> str:
    """The next action id ``a<NN>`` of one plan item: one past the highest existing number, two digits (three after ``a99``).

    When the highest id is deleted, its number is minted again; an id that does not match ``^a[0-9]{2,}$`` is ignored.
    """
    numbers = (int(m.group(1)) for m in map(_ACTION_ID.match, existing_action_ids_in_item) if m)
    return f"a{_next_number(numbers):02d}"
