"""Format-preserving writer for spec JSON files and the diff of two spec folders (WI-M10-02).

A migration script edits the parsed document of a spec file and hands it back here.  The file is written in the
style it was read in (indent, ``ensure_ascii``, trailing newline, line ending), so the lines a script did not edit
stay byte-identical and a file no script changed is never written.  A file that does not round-trip in any regular
style (hand-formatted, compact, duplicate keys, floats such as ``1e5``) is ``irregular``: it is left alone while
unchanged, and rewritten in its detected indent with ``ensure_ascii=False`` when a script changed it; the change of
style then shows in the diff like any other change.

This module is the migration's writer of a whole document.  ``trace.id_writes.execute_write`` stays the writer of an
id-keyed edit with its lock entries; the two do not call each other.  The atomic file replace is the one of
``trace.lockfile``.  Nothing here imports the rest of ``migration/``.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.json_utils import detect_indent
from specdev_tools.trace.lockfile import replace_file_atomically

DEFAULT_INDENT = "    "
_UNICODE_ESCAPE = re.compile(r"\\u[0-9a-fA-F]{4}")
_NO_NEWLINE_MARKER = "\\ No newline at end of file\n"


class WriterError(Exception):
    """A spec file cannot be read as JSON, or a relative path leaves the spec folder."""


@dataclass(frozen=True)
class FileStyle:
    """How one file is written: *indent* is the unit string (spaces or a tab), *irregular* says it does not round-trip."""

    indent: str
    ensure_ascii: bool
    final_newline: bool
    line_ending: str
    irregular: bool


def render(data: Any, style: FileStyle) -> str:
    """Return *data* as JSON text in *style* (key order as in *data*)."""
    text = json.dumps(data, indent=style.indent, ensure_ascii=style.ensure_ascii)
    if style.final_newline:
        text += "\n"
    return text.replace("\n", style.line_ending)


def detect_style(text: str, data: Any) -> FileStyle:
    """Detect the style of the file whose *text* parsed to *data*; ``irregular`` when no regular style reproduces it."""
    indent = detect_indent(text, DEFAULT_INDENT)
    final_newline = text.endswith("\n")
    line_ending = "\r\n" if "\r\n" in text else "\n"
    escaped = bool(_UNICODE_ESCAPE.search(text)) and text.isascii()
    for ensure_ascii in (escaped, not escaped):
        style = FileStyle(indent, ensure_ascii, final_newline, line_ending, irregular=False)
        if render(data, style) == text:
            return style
    return FileStyle(indent, False, final_newline, line_ending, irregular=True)


@dataclass
class StyledDocument:
    """A spec file as loaded: edit *data* in place; *style* and the original rendering stay fixed."""

    rel: str
    style: FileStyle
    data: Any
    original_rendered: str

    @property
    def changed(self) -> bool:
        """True when *data* renders differently from the data as loaded (a key order change counts)."""
        return render(self.data, self.style) != self.original_rendered

    def text(self) -> str:
        """The text to write: *data* in the file's style."""
        return render(self.data, self.style)


NEW_FILE_STYLE = FileStyle(DEFAULT_INDENT, ensure_ascii=False, final_newline=True, line_ending="\n", irregular=False)


class DocumentSet:
    """The spec JSON files of one folder, loaded once each, written back only when their data changed."""

    def __init__(self, spec_root: str) -> None:
        self._root = spec_root
        self._documents: dict[str, StyledDocument] = {}

    def load(self, rel: str) -> StyledDocument:
        """Return the document of *rel* (a path relative to the spec folder), reading it on first use.

        Raises:
            WriterError: *rel* leaves the spec folder, or the file is not valid JSON.
        """
        if rel not in self._documents:
            self._documents[rel] = self._read(rel)
        return self._documents[rel]

    def create(self, rel: str, data: Any) -> StyledDocument:
        """Create the spec file *rel*, which does not exist yet, holding *data*; return it loaded.

        The file is written at once in the default style (indent 4, non-ASCII kept, a final newline) through the same
        atomic replace ``write`` uses; later edits of the returned document are written by ``write``.

        Raises:
            WriterError: *rel* leaves the spec folder, or the file exists.
        """
        path = self._path(rel)
        if os.path.exists(path):
            raise WriterError(f"{rel}: the file exists")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        replace_file_atomically(path, render(data, NEW_FILE_STYLE))
        return self.load(rel)

    def changed(self) -> list[StyledDocument]:
        """The loaded documents whose data changed, in path order."""
        return [self._documents[rel] for rel in sorted(self._documents) if self._documents[rel].changed]

    def write(self) -> list[str]:
        """Write every changed document in its own style; return the relative paths written, in path order."""
        changed = self.changed()
        for document in changed:
            replace_file_atomically(self._path(document.rel), document.text())
        return [document.rel for document in changed]

    def _path(self, rel: str) -> str:
        normal = os.path.normpath(rel)
        if os.path.isabs(normal) or normal == ".." or normal.startswith(".." + os.sep):
            raise WriterError(f"{rel}: the path leaves the spec folder")
        return os.path.join(self._root, normal)

    def _read(self, rel: str) -> StyledDocument:
        path = self._path(rel)
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise WriterError(f"{rel}: not valid JSON ({exc})") from exc
        style = detect_style(text, data)
        rendered = text if not style.irregular else render(data, style)
        return StyledDocument(rel, style, copy.deepcopy(data), rendered)


def _folder_files(root: str) -> dict[str, str]:
    """Map each file under *root* (slash-separated relative path) to its text, read without newline translation."""
    files: dict[str, str] = {}
    for folder, _dirs, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, encoding="utf-8", errors="replace", newline="") as handle:
                files[rel] = handle.read()
    return files


def _lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n" + _NO_NEWLINE_MARKER
    return lines


def diff_trees(before_root: str, after_root: str) -> str:
    """Return the unified diff of the files under *after_root* against those under *before_root*; empty when equal.

    Only files that differ, or exist on one side only, appear; files come in path order, labelled ``a/<rel>`` and
    ``b/<rel>`` (``/dev/null`` for the absent side); the text has no timestamp and no folder name.
    """
    before, after = _folder_files(before_root), _folder_files(after_root)
    chunks: list[str] = []
    for rel in sorted(before.keys() | after.keys()):
        old, new = before.get(rel), after.get(rel)
        if old == new:
            continue
        chunks.extend(
            difflib.unified_diff(
                _lines(old or ""),
                _lines(new or ""),
                fromfile=f"a/{rel}" if old is not None else "/dev/null",
                tofile=f"b/{rel}" if new is not None else "/dev/null",
            )
        )
    return "".join(chunks)
