"""Copies of the worked example with documents edited by name, for the tests that need a spec folder."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from unit.graph._synth import copy_example, load_doc, write_json

Edit = Callable[[dict[str, Any]], None]
"""An edit of a spec file: a function over the parsed document."""


def edit_documents(spec: Path, **edits: Edit) -> Path:
    """Apply each edit (file name under *spec* to function over the parsed document) to *spec*; *spec*."""
    for rel, edit in edits.items():
        document = load_doc(spec, rel)
        edit(document)
        write_json(spec, rel, document)
    return spec


def edited_example(dest: Path, **edits: Edit) -> Path:
    """A copy of the worked example spec folder at *dest* with each edit applied (see ``edit_documents``); *dest*."""
    return edit_documents(copy_example(dest), **edits)
