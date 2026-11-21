"""The rollback record: a person's statement that a release is not to be verified in production.

``spec/extras/releases/rollback-<tag>.json`` (a ``/`` in the tag becomes ``_``) holds one object: ``$schema``, ``id``
(``rollback-<tag>``), ``tag``, ``commit`` (the commit the tag names), ``reason`` (not blank) and ``recorded_at`` (UTC).  Who made
it is the git author of the commit that adds it.  The spec loader skips ``extras/`` below the first level and no graph node
reads the file, so ``spec-check`` ignores it and the code tree leaves it out with the spec folder.  No schema file describes it
(ruling: no schema, no registry line): ``record_problems`` is the whole validation, run on every read and before every write.

The writer writes the file in the working tree and does not commit it; the person commits it through the normal branch.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from specdev_tools.core.errors import refusal
from specdev_tools.core.json_utils import JQ_INDENT
from specdev_tools.graph.gitview import GitViewError, resolve_ref
from specdev_tools.lifecycle.records import now_utc
from specdev_tools.release.tag_state import tag_matches
from specdev_tools.trace.lockfile import replace_file_atomically

ROLLBACK_DIR = os.path.join("extras", "releases")
"""The folder of the rollback records, relative to the spec folder."""
ROLLBACK_SCHEMA = "vc:extras:rollback-record"
"""The ``$schema`` value of a record: a label only, no schema file or registry line stands behind it."""
_PREFIX = "rollback-"
_KEYS = ("$schema", "id", "tag", "commit", "reason", "recorded_at")


def rollback_id(tag: str) -> str:
    """The record id of *tag*: ``rollback-`` and the tag with every ``/`` replaced by ``_``."""
    return _PREFIX + tag.replace("/", "_")


def rollback_path(spec_root: str, tag: str) -> str:
    """The file of the rollback record of *tag* under the spec folder *spec_root*."""
    return os.path.join(spec_root, ROLLBACK_DIR, rollback_id(tag) + ".json")


def record_problems(record: object, tag: str) -> list[str]:
    """What is wrong with *record* as the rollback record of *tag*: a missing key, a value that is not text, a blank reason, an id or tag that is not the tag's."""
    if not isinstance(record, Mapping):
        return ["the file does not hold one JSON object"]
    problems = [f"key '{key}' is missing" for key in _KEYS if key not in record]
    problems += [f"'{key}' is not text" for key in _KEYS if key in record and not isinstance(record[key], str)]
    if isinstance(record.get("reason"), str) and not record["reason"].strip():
        problems.append("'reason' is blank")
    if record.get("tag") != tag:
        problems.append(f"'tag' is {record.get('tag')!r}, not {tag!r}")
    if record.get("id") != rollback_id(tag):
        problems.append(f"'id' is {record.get('id')!r}, not {rollback_id(tag)!r}")
    return problems


def read_rollback(spec_root: str, tag: str) -> dict[str, Any] | None:
    """The valid rollback record of *tag*, or ``None`` when no file exists.

    Raises:
        FindingError: E774 when the file exists and is not a valid record (the message names the first problem).
    """
    path = rollback_path(spec_root, tag)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise refusal("E774", f"{os.path.basename(path)} cannot be read as JSON ({exc}); correct or remove the file") from exc
    problems = record_problems(record, tag)
    if problems:
        raise refusal("E774", f"{os.path.basename(path)} is not a valid rollback record: {problems[0]}; correct the file or remove it and record the rollback again")
    return record


def write_rollback(git_root: str, spec_root: str, tag: str, reason: str, pattern: str) -> str:
    """Write the rollback record of *tag* (not committed) and return its path.

    *pattern* is the host's ``release_tag_pattern``.

    Raises:
        FindingError: E925 when *tag* names no commit or does not match *pattern*; E926 when *reason* is blank; E927 when a record of *tag* exists.
    """
    if not tag_matches(pattern, tag):
        raise refusal("E925", f"'{tag}' does not match the release tag pattern {pattern}; name a release tag")
    try:
        commit = resolve_ref(tag, git_root)
    except GitViewError as error:
        raise refusal("E925", f"'{tag}' names no commit in this repository; name an existing release tag") from error
    if not reason.strip():
        raise refusal("E926", "the rollback reason is blank; say why the release is not verified in production")
    path = rollback_path(spec_root, tag)
    if os.path.exists(path):
        raise refusal("E927", f"a rollback record for '{tag}' exists at {path}; remove it first if it was a mistake")
    record = {"$schema": ROLLBACK_SCHEMA, "id": rollback_id(tag), "tag": tag, "commit": commit, "reason": reason.strip(), "recorded_at": now_utc()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    replace_file_atomically(path, json.dumps(record, indent=JQ_INDENT, ensure_ascii=False) + "\n")
    return path
