"""Guide loader for ``specdev guide <code>`` subcommand.

Loads all ``*.yaml`` files from ``tools/specdev_tools/guides/`` and provides
a lookup function that resolves:

  1. Exact ``{code}-{subcode}`` match (e.g. ``E530-INVENTED_ENUM_OR_ID``).
  2. Base-code fallback (e.g. ``E530``).

Usage::

    from .core.guide import load_guides, lookup_guide
    guides = load_guides()
    entry = lookup_guide("E530-INVENTED_ENUM_OR_ID", guides)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Path to the guides directory (sibling directory of this package)
_GUIDES_DIR = Path(__file__).resolve().parent.parent / "guides"


def load_guides(guides_dir: Path | None = None) -> dict[str, Any]:
    """Load all ``*.yaml`` guide files and return a lookup dict.

    Each entry is indexed under one or two keys:
    - Base-code entries (no ``subcode`` field) → ``"{CODE}"``.
    - Subcoded entries → ``"{CODE}-{SUBCODE}"`` **and** ``"{CODE}"`` (as a
      fallback, so bare lookups like ``specdev guide E110`` still resolve when
      only a subcoded YAML exists for that code).  A base-code YAML always wins
      over a subcoded-fallback for the bare key.

    Parameters
    ----------
    guides_dir:
        Override the directory to scan.  Defaults to the bundled
        ``guides/`` directory next to the package.

    Returns
    -------
    dict[str, Any]
        Mapping of lookup key → parsed YAML dict.
    """
    directory = guides_dir or _GUIDES_DIR
    # Two-pass: collect all entries first, then build the index so base-code
    # entries overwrite subcoded fallbacks for the bare key.
    entries: list[tuple[str, str | None, dict[str, Any]]] = []
    if not directory.is_dir():
        return {}
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "code" not in data:
            continue
        code = str(data["code"])
        subcode = data.get("subcode") or None
        entries.append((code, subcode, data))

    index: dict[str, Any] = {}
    # First pass: register subcoded entries under their bare code as a fallback
    # so `specdev guide E110` works even when only E110-UNKNOWN_CANONICAL_ID.yaml exists.
    for code, subcode, data in entries:
        if subcode:
            bare_key = code
            if bare_key not in index:
                index[bare_key] = data

    # Second pass: register primary keys (base-code YAML overwrites subcoded fallback).
    for code, subcode, data in entries:
        if subcode:
            primary_key = f"{code}-{subcode}"
        else:
            primary_key = code
        index[primary_key] = data

    return index


def lookup_guide(code_arg: str, guides: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Look up a guide entry for *code_arg*.

    *code_arg* may be:
    - A bare code: ``"E110"``
    - A hyphen-joined subcoded form: ``"E530-INVENTED_ENUM_OR_ID"``

    Lookup order:
    1. Exact match on *code_arg* (handles both bare and subcoded forms).
    2. Base-code fallback: the portion before the first ``-``.

    Returns the guide dict, or ``None`` if not found.
    """
    if guides is None:
        guides = load_guides()

    # 1. Exact match
    if code_arg in guides:
        return guides[code_arg]

    # 2. Base-code fallback (split on first hyphen)
    base = code_arg.split("-", 1)[0]
    return guides.get(base)


def format_guide_text(entry: dict[str, Any], code_arg: str | None = None) -> str:
    """Render a guide entry as human-readable text.

    Parameters
    ----------
    entry:
        Guide dict returned by :func:`lookup_guide`.
    code_arg:
        The code string the caller looked up (e.g. ``"E110"`` or
        ``"E530-INVENTED_ENUM_OR_ID"``).  When provided, used as-is in the
        header so the output matches the user's invocation.  When omitted, the
        header is derived from the entry's ``code`` and ``subcode`` fields.

    Returns a multi-line string suitable for direct stdout output.
    """
    lines: list[str] = []
    code = entry.get("code", "")
    subcode = entry.get("subcode")
    header = code_arg if code_arg is not None else (f"{code}-{subcode}" if subcode else code)
    title = entry.get("title", "")
    lines.append(f"=== {header}: {title} ===")
    lines.append("")

    trigger = entry.get("trigger", "").strip()
    if trigger:
        lines.append("Trigger:")
        for line in trigger.splitlines():
            lines.append(f"  {line}")
        lines.append("")

    resolution = entry.get("resolution", "").strip()
    if resolution:
        lines.append("Resolution:")
        for line in resolution.splitlines():
            lines.append(f"  {line}")
        lines.append("")

    see_also = entry.get("see_also")
    if see_also:
        lines.append("See also:")
        for ref in see_also:
            lines.append(f"  specdev guide {ref}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
