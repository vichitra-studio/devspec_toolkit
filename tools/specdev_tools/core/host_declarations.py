"""The host declarations: what only the host repository knows (the one reader of ``spec/common/host_declarations.json``).

The file is written by hand and every key is optional, so a host without it gets empty declarations.  The gates that
need an item (the release-tag pattern, the setup command) report their own error when it is absent; this module only
reads.  The shape is ``schema/host_declarations.schema.json``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .json_utils import resolve_effective_toolkit_root
from .schema_validate import jq_path_of, schema_violations, violation_text

HOST_DECLARATIONS_FILE = "common/host_declarations.json"
"""The declarations file, relative to the spec folder."""

HOST_DECLARATIONS_SCHEMA_URI = "vc:host-declarations"
JSON_POINTER_TYPE = "json-pointer"
REGEX_TYPE = "regex"


class HostDeclarationsError(ValueError):
    """The declarations file cannot be read; ``path`` names it, ``reason`` what is wrong."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


@dataclass(frozen=True)
class PinSource:
    """One place the repository declares the version of a third party.

    ``type`` is ``json-pointer`` (then ``pointer`` is set) or ``regex`` (then ``pattern`` is set); ``file`` is relative
    to the git root.
    """

    type: str
    file: str
    pointer: str | None = None
    pattern: str | None = None


@dataclass(frozen=True)
class HostDeclarations:
    """The four declarations; an item the file does not state is ``None`` or empty.

    ``pin_sources`` maps a third-party node id to its sources, in the file's order.
    """

    release_tag_pattern: str | None = None
    setup_command: str | None = None
    code_tree_exclusions: tuple[str, ...] = ()
    pin_sources: dict[str, tuple[PinSource, ...]] = field(default_factory=dict)


def load_host_declarations(spec_root: str | os.PathLike[str]) -> HostDeclarations:
    """The declarations of the host whose spec folder is *spec_root*.

    A missing file gives empty declarations.  Raises ``HostDeclarationsError`` when the file is not JSON, is not an
    object or breaks the schema (the message names the first violation).
    """
    path = os.path.join(os.fspath(spec_root), HOST_DECLARATIONS_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError:
        return HostDeclarations()
    except (OSError, json.JSONDecodeError) as exc:
        raise HostDeclarationsError(path, f"cannot be read as JSON ({exc})") from exc
    if not isinstance(document, dict):
        raise HostDeclarationsError(path, "must hold a JSON object")
    _require_schema_valid(path, document)
    return HostDeclarations(
        release_tag_pattern=document.get("release_tag_pattern"),
        setup_command=document.get("setup_command"),
        code_tree_exclusions=tuple(document.get("code_tree_exclusions", ())),
        pin_sources={
            third_party: tuple(PinSource(**source) for source in sources)
            for third_party, sources in document.get("pin_sources", {}).items()
        },
    )


def _require_schema_valid(path: str, document: dict[str, Any]) -> None:
    """Raise ``HostDeclarationsError`` for the first violation of the schema by *document*."""
    violations = schema_violations(
        resolve_effective_toolkit_root(None), {**document, "$schema": HOST_DECLARATIONS_SCHEMA_URI}
    )
    if violations:
        first = min(violations, key=lambda item: (len(item.path), tuple(map(str, item.path))))
        raise HostDeclarationsError(path, f"{jq_path_of(first.path)}: {violation_text(first)}")
