"""Read the version a repository declares for a third party (a pin source of the host declarations).

Two source types exist, both declared in ``core/host_declarations.py::PinSource``: ``json-pointer`` (an RFC 6901
pointer into a JSON file) and ``regex`` (the one capture group of the first match in a text file).  A source that
cannot give a version raises ``SourceError``; the callers decide what that means (an error line for the pin check, no
recorded version for ``verify run``).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..core.host_declarations import JSON_POINTER_TYPE, REGEX_TYPE, PinSource

_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")


class SourceError(ValueError):
    """A pin source gives no version; the message says which file and what is wrong."""


def read_source(source: PinSource, git_root: str | Path) -> str:
    """The version string *source* declares, read from its file under *git_root*.

    Raises ``SourceError`` when the file is missing or not readable, the pointer does not select a string, the regex
    does not compile, does not have exactly one capture group or does not match, or the source type is unknown.
    """
    text = _read_text(Path(git_root) / source.file, source.file)
    if source.type == JSON_POINTER_TYPE:
        return _pointer_value(text, source)
    if source.type == REGEX_TYPE:
        return _regex_value(text, source)
    raise SourceError(f"{source.file}: unknown source type '{source.type}'")


def _read_text(path: Path, name: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"{name}: cannot be read ({exc})") from exc


def _pointer_value(text: str, source: PinSource) -> str:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceError(f"{source.file}: is not JSON ({exc})") from exc
    value = _resolve_pointer(document, source.pointer or "", source.file)
    if not isinstance(value, str):
        raise SourceError(f"{source.file}: pointer '{source.pointer}' does not select a string")
    return value


def _resolve_pointer(document: Any, pointer: str, name: str) -> Any:
    """The value an RFC 6901 *pointer* selects in *document*; *name* (the file) is only for the message.

    ``~1`` stands for ``/`` and ``~0`` for ``~`` in a key (``~1`` is undone first).  Raises ``SourceError`` for a pointer
    that does not start with ``/`` or selects nothing.
    """
    if not pointer.startswith("/"):
        raise SourceError(f"{name}: pointer '{pointer}' must start with '/'")
    value = document
    for token in pointer[1:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        value = _step(value, key, pointer, name)
    return value


def _step(value: Any, key: str, pointer: str, name: str) -> Any:
    if isinstance(value, dict) and key in value:
        return value[key]
    if isinstance(value, list) and _ARRAY_INDEX.fullmatch(key) and int(key) < len(value):
        return value[int(key)]
    raise SourceError(f"{name}: pointer '{pointer}' does not resolve at '{key}'")


def _regex_value(text: str, source: PinSource) -> str:
    pattern = source.pattern or ""
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise SourceError(f"{source.file}: pattern '{pattern}' does not compile ({exc})") from exc
    if compiled.groups != 1:
        raise SourceError(f"{source.file}: pattern '{pattern}' must have exactly one capture group")
    match = compiled.search(text)
    if match is None or match.group(1) is None:
        raise SourceError(f"{source.file}: pattern '{pattern}' does not match")
    return match.group(1)
