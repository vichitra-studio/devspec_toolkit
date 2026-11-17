"""The trace lock file ``<spec_dir>/extras/trace.lock.json``: its format, reading, writing and the write lock.

The file holds one entry per link, in the format of ``schema/extras/trace_lock.schema.json``: one entry per line, keys
in a fixed order, entries sorted by (source, field, target).  The serialiser here is the only writer of that layout
(``json_write_atomic`` re-indents with jq), so a read followed by a write gives back the same bytes.

A write of the lock and of a spec file are two replaces, spec file first, so a crash between them leaves a state the
checks can see: entries missing after an addition, orphan entries after a removal.  ``with_write_lock`` keeps two
specdev writers from interleaving.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any

from specdev_tools.core.constants import TRACE_LOCK_FILENAME, resolve_extras_path
from specdev_tools.core.errors import FindingError, make_error

LOCK_SCHEMA_URI = "vc:extras:trace-lock"
LOCK_VERSION = 1
CONFLICT_MARKER = "<<<<<<<"
MERGE_CHECK_OWNER = "merge-check"
_DEFAULT_FILE_MODE = 0o644
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONFLICT_RE = re.compile(rf"^{CONFLICT_MARKER}", re.MULTILINE)
_REQUIRED_KEYS = ("source", "field", "target", "content_hash", "chain_stamp")
_ENTRY_KEYS = (*_REQUIRED_KEYS, "baseline")
_TOP_KEYS = frozenset({"$schema", "version", "entries"})
_HASH_KEYS = ("content_hash", "chain_stamp")


class LockError(FindingError):
    """The lock file cannot be read or written; ``error`` is the finding (E760 or E769)."""


def _malformed(path: str, message: str) -> LockError:
    return LockError(make_error("E760", f"trace lock {path}: {message}", file=path, owner=MERGE_CHECK_OWNER))


@dataclass(frozen=True)
class LockEntry:
    """The accepted state of one link: the hashes of its target when the holder last accepted it."""

    source: str
    field: str
    target: str
    content_hash: str
    chain_stamp: str
    baseline: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        """The (source, field, target) triple that identifies the entry."""
        return (self.source, self.field, self.target)


@dataclass(frozen=True)
class Lock:
    """The entries of a lock file, sorted by key.

    The constructor sorts ``entries`` and raises ``LockError`` (E760) when two entries have the same key.
    """

    entries: tuple[LockEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.entries, key=lambda entry: entry.key))
        for first, second in zip(ordered, ordered[1:]):
            if first.key == second.key:
                source, field, target = first.key
                raise LockError(make_error(
                    "E760",
                    f"trace lock has two entries for ({source}, {field}, {target}); the key must occur once",
                    owner=MERGE_CHECK_OWNER,
                ))
        object.__setattr__(self, "entries", ordered)


def lock_path(spec_dir: str) -> str:
    """Absolute path of the lock file of *spec_dir* (the file need not exist)."""
    return resolve_extras_path(spec_dir, TRACE_LOCK_FILENAME)


def _conflict_message(path: str) -> str:
    return (
        f"{path} holds git merge conflict markers ({CONFLICT_MARKER}). Repair: install the merge driver with "
        f'`git config merge.specdev-trace-lock.driver "specdev lock merge %O %A %B %P"`, then run '
        f"`git checkout -m -- {path}` (it re-runs the driver and writes the merged file, but git still lists the path "
        f"as unmerged), then `git add {path}`"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"key {key!r} occurs twice in one object")
        result[key] = value
    return result


def _entry_from_object(raw: object, path: str, index: int) -> LockEntry:
    where = f"entry {index}"
    if not isinstance(raw, dict):
        raise _malformed(path, f"{where} is not an object")
    unknown = sorted(set(raw) - set(_ENTRY_KEYS))
    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if unknown or missing:
        raise _malformed(path, f"{where} has unknown keys {unknown} or lacks keys {missing}")
    for key in ("source", "field", "target"):
        if not isinstance(raw[key], str) or not raw[key]:
            raise _malformed(path, f"{where}: {key} must be a non-empty string")
    for key in _HASH_KEYS:
        if not isinstance(raw[key], str) or not _HASH_RE.match(raw[key]):
            raise _malformed(path, f"{where}: {key} must be sha256: followed by 64 lower-case hex digits")
    if "baseline" in raw and raw["baseline"] is not True:
        raise _malformed(path, f"{where}: baseline is present only when true")
    return LockEntry(
        raw["source"], raw["field"], raw["target"], raw["content_hash"], raw["chain_stamp"], "baseline" in raw
    )


def _lock_from_document(document: object, path: str) -> Lock:
    if not isinstance(document, dict) or set(document) - _TOP_KEYS:
        raise _malformed(path, "the top level must be an object with only $schema, version and entries")
    if document.get("$schema") != LOCK_SCHEMA_URI:
        raise _malformed(path, f"$schema must be {LOCK_SCHEMA_URI}")
    version = document.get("version")
    if type(version) is not int or version != LOCK_VERSION:
        raise _malformed(path, f"version must be {LOCK_VERSION}; this toolkit reads no other")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise _malformed(path, "entries must be an array")
    parsed = tuple(_entry_from_object(raw, path, index) for index, raw in enumerate(entries))
    try:
        return Lock(parsed)
    except LockError as error:
        raise LockError(replace(error.error, file=path)) from None


def parse_lock(text: str, path: str) -> Lock:
    """The lock held in *text* (the content of the file at *path*, used only to name it in findings).

    Raises ``LockError`` (E760) for conflict markers, text that is not JSON, JSON that is not the lock format, a
    version other than 1, a bad hash and a key that occurs twice.
    """
    if _CONFLICT_RE.search(text):
        raise _malformed(path, _conflict_message(path))
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as error:
        raise _malformed(path, f"not valid JSON ({error})") from None
    return _lock_from_document(document, path)


def read_lock(spec_dir: str) -> Lock:
    """The lock of *spec_dir*; an empty lock when the file does not exist.

    Raises ``LockError`` (E760) as ``parse_lock`` does, and when the file is not UTF-8.
    """
    path = lock_path(spec_dir)
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return Lock()
    except UnicodeDecodeError as error:
        raise _malformed(path, f"not valid UTF-8 ({error})") from None
    return parse_lock(text, path)


def _entry_line(entry: LockEntry) -> str:
    fields = {key: getattr(entry, key) for key in _REQUIRED_KEYS}
    if entry.baseline:
        fields["baseline"] = True
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))


def serialise_lock(lock: Lock) -> str:
    """The text of the lock file: one entry per line, fixed key order, sorted entries, trailing newline."""
    head = f'{{"$schema": "{LOCK_SCHEMA_URI}", "version": {LOCK_VERSION}, "entries": ['
    if not lock.entries:
        return head + "]}\n"
    body = ",\n".join(f" {_entry_line(entry)}" for entry in lock.entries)
    return f"{head}\n{body}\n]}}\n"


def replace_file_atomically(path: str, text: str) -> None:
    """Write *text* to *path* through a temporary file in the same folder and ``os.replace``.

    The file keeps the mode of the file it replaces, or 0o644 for a new file.
    """
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        mode = _DEFAULT_FILE_MODE
    descriptor, temp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".trace-lock-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def write_lock(spec_dir: str, lock: Lock) -> None:
    """Write *lock* as the lock file of *spec_dir*, creating ``<spec_dir>/extras`` when it is missing."""
    path = lock_path(spec_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    replace_file_atomically(path, serialise_lock(lock))


@contextmanager
def with_write_lock(spec_dir: str) -> Iterator[None]:
    """Hold the exclusive write lock of *spec_dir* for the ``with`` block.

    The lock is ``flock`` on a descriptor opened on ``<spec_dir>/extras`` itself, so no file exists to be ignored or
    committed; it is released when the block ends or the process dies.  Creates the folder when it is missing.
    Raises ``LockError`` (E769) at once, without waiting, when another process holds it.
    """
    extras_dir = os.path.dirname(lock_path(spec_dir))
    os.makedirs(extras_dir, exist_ok=True)
    descriptor = os.open(extras_dir, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockError(make_error(
                "E769",
                f"another specdev write is running (the lock on {extras_dir} is held); "
                "wait for it to finish, then run the command again",
            )) from None
        yield
    finally:
        os.close(descriptor)
