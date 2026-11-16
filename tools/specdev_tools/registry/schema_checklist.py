"""Schema-change rows, the frozen baseline, their closure checks and the generated checklist.

``tools/schema_changes.json`` lists every change the schemas made since the 1.1.1 baseline
(``tests/fixtures/schema_baseline/paths_1.1.1.json``) as one row per path: ``add``, ``remove`` or
``change`` (the node's type, ``$ref`` or enum differs).  This module loads the rows without
trusting their shape, compares them with the flattened schemas (``schema_paths``) in both
directions, and renders the markdown checklist ``registry-generate`` writes.

Path notation is that of ``schema_paths``: ``a[].b`` for array items, ``m{}`` for map values,
``$defs.<name>`` for core definitions.  A row ``path`` may be a glob: ``**`` matches any
characters, ``*`` any characters except ``.``, ``[``, ``]``, ``{`` and ``}``.  A row's ``step``
selects every schema whose name equals it or starts with it plus ``_`` (core schemas are
``core/<name>``).
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specdev_tools.registry.schema_paths import PathInfo

ROWS_FILE = Path("tools") / "schema_changes.json"
CHECKLIST_FILE = Path("docs") / "developers" / "schema-change-checklist.md"

CHANGE_KINDS = ("add", "remove", "change")
OWNERS = ("M2", "M3")

Inventory = Mapping[str, Mapping[str, PathInfo]]

_ROW_ID = re.compile(r"^SC-(?P<step>.+)-(?P<seq>[0-9]{2,})$")
_BOUNDARY = r"(?:$|[.\[{])"
_STRING_LISTS = ("design", "tickets")


class ChecklistError(ValueError):
    """Raised when the rows file cannot be used to generate the checklist."""


@dataclass(frozen=True)
class ChangeRow:
    """One schema change: ``change`` of ``path`` in the schemas selected by ``step``."""

    id: str
    step: str
    path: str
    change: str
    replaced_by: str | None
    owner: str
    design: tuple[str, ...]
    tickets: tuple[str, ...]
    shim: bool


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _row_problems(raw: Any) -> list[str]:
    """Problems of one raw row (an empty list when it is well formed); never raises."""
    if not isinstance(raw, dict):
        return ["row is not an object"]
    problems = [f"{key}: must be a non-empty string" for key in ("id", "step", "path")
                if not isinstance(raw.get(key), str) or not raw[key]]
    if raw.get("change") not in CHANGE_KINDS:
        problems.append(f"change: must be one of {', '.join(CHANGE_KINDS)}")
    if raw.get("owner") not in OWNERS:
        problems.append(f"owner: must be one of {', '.join(OWNERS)}")
    if raw.get("replaced_by") is not None and not isinstance(raw.get("replaced_by"), str):
        problems.append("replaced_by: must be a string or null")
    problems += [f"{key}: must be a list of strings" for key in _STRING_LISTS if not _is_str_list(raw.get(key))]
    if not isinstance(raw.get("shim"), bool):
        problems.append("shim: must be a boolean")
    return problems or _id_problems(raw)


def _id_problems(raw: dict[str, Any]) -> list[str]:
    """Problems of the row id: it must read ``SC-<step>-<nn>`` with ``/`` of the step written ``-``."""
    match = _ROW_ID.match(raw["id"])
    if match is None or match["step"] != raw["step"].replace("/", "-"):
        return [f"id: {raw['id']!r} is not SC-<step>-<nn> for step {raw['step']!r}"]
    return []


def parse_rows(document: Any) -> tuple[list[ChangeRow], list[str]]:
    """Read the rows of a parsed rows file as ``(valid rows, problems)``; never raises.

    A row with any problem is left out of the rows and each problem is named with its position
    (and id).  A duplicate id is a problem of the later row.
    """
    raw_rows = document.get("rows") if isinstance(document, dict) else None
    if not isinstance(raw_rows, list):
        return [], ["the file must be an object with a 'rows' array"]
    rows: list[ChangeRow] = []
    problems: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rows):
        found = _row_problems(raw)
        label = f"rows[{index}]" + (f" {raw['id']}" if isinstance(raw, dict) and isinstance(raw.get("id"), str) else "")
        if not found and raw["id"] in seen:
            found = ["id: duplicate"]
        problems += [f"{label}: {p}" for p in found]
        if found:
            continue
        seen.add(raw["id"])
        rows.append(ChangeRow(
            raw["id"], raw["step"], raw["path"], raw["change"], raw["replaced_by"], raw["owner"],
            tuple(raw["design"]), tuple(raw["tickets"]), raw["shim"],
        ))
    return rows, problems


def load_rows(path: Path) -> tuple[list[ChangeRow], list[str]]:
    """Read the rows file at *path* as ``parse_rows`` does; raises ``OSError`` or ``JSONDecodeError``."""
    return parse_rows(json.loads(path.read_text(encoding="utf-8")))


def load_baseline(path: Path) -> dict[str, dict[str, PathInfo]]:
    """Read the frozen baseline fixture into ``{schema name: {path: PathInfo}}``.

    Raises ``ChecklistError`` when the file is not ``{"schemas": {name: {path: {type, ref, enum}}}}``.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    schemas = document.get("schemas") if isinstance(document, dict) else None
    if not isinstance(schemas, dict):
        raise ChecklistError(f"{path}: baseline must be an object with a 'schemas' object")
    try:
        return {
            name: {
                p: PathInfo(f["type"], f["ref"], tuple(f["enum"]) if f["enum"] is not None else None)
                for p, f in paths.items()
            }
            for name, paths in schemas.items()
        }
    except (KeyError, TypeError, AttributeError) as exc:
        raise ChecklistError(f"{path}: malformed baseline entry: {exc!r}") from exc


def selects(step: str, schema: str) -> bool:
    """True when a row ``step`` selects the schema named *schema* (equal, or *step* plus ``_`` as prefix)."""
    return schema == step or schema.startswith(f"{step}_")


def _glob_pattern(glob: str) -> str:
    """Regular-expression source of a path glob (without anchors)."""
    out: list[str] = []
    i = 0
    while i < len(glob):
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append(r"[^.\[\]{}]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return "".join(out)


def matches(glob: str, path: str) -> bool:
    """True when the whole of *path* matches the row path *glob*."""
    return re.fullmatch(_glob_pattern(glob), path) is not None


def covers(glob: str, path: str) -> bool:
    """True when *path* matches *glob* or lies below a node the glob matches (boundary prefix)."""
    return re.match(_glob_pattern(glob) + _BOUNDARY, path) is not None


def _facts(info: PathInfo) -> tuple[str | None, str | None, tuple[Any, ...] | None]:
    return info.type, info.ref, info.enum


def row_holds(row: ChangeRow, baseline: Inventory, current: Inventory) -> bool:
    """True when the change a row states is true of the selected schemas.

    ``add``: some matching path is in the current schemas and not in the baseline.  ``remove``:
    the reverse.  ``change``: some matching path is in both and its type, ``$ref`` or enum differs.
    """
    for name in sorted(set(baseline) | set(current)):
        if not selects(row.step, name):
            continue
        before = {p: i for p, i in baseline.get(name, {}).items() if matches(row.path, p)}
        after = {p: i for p, i in current.get(name, {}).items() if matches(row.path, p)}
        if row.change == "add" and set(after) - set(before):
            return True
        if row.change == "remove" and set(before) - set(after):
            return True
        if row.change == "change" and any(_facts(before[p]) != _facts(after[p]) for p in set(before) & set(after)):
            return True
    return False


def differing_paths(baseline: Inventory, current: Inventory, schema: str) -> list[str]:
    """Paths of *schema* that are added, removed or changed between the two inventories, sorted."""
    before, after = baseline.get(schema, {}), current.get(schema, {})
    return sorted(
        p for p in set(before) | set(after)
        if p not in before or p not in after or _facts(before[p]) != _facts(after[p])
    )


def uncovered_paths(
    rows: Iterable[ChangeRow], baseline: Inventory, current: Inventory, schemas: Iterable[str]
) -> list[str]:
    """Differing paths of the named *schemas* that no row covers, as sorted ``schema:path`` strings."""
    rows = list(rows)
    out: list[str] = []
    for name in sorted(set(schemas)):
        globs = [r.path for r in rows if selects(r.step, name)]
        out += [f"{name}:{p}" for p in differing_paths(baseline, current, name)
                if not any(covers(g, p) for g in globs)]
    return out


def _cell(value: str) -> str:
    return value.replace("|", "\\|")


def _row_line(row: ChangeRow) -> str:
    cells = [
        row.id, f"`{_cell(row.path)}`", row.change, _cell(row.replaced_by or ""), row.owner,
        ", ".join(row.design), ", ".join(row.tickets), "yes" if row.shim else "",
    ]
    return "| " + " | ".join(cells) + " |"


def render_checklist(rows: Iterable[ChangeRow]) -> str:
    """Render the rows as the markdown checklist, grouped by step in order of first appearance."""
    rows = list(rows)
    groups: dict[str, list[ChangeRow]] = {}
    for row in rows:
        groups.setdefault(row.step, []).append(row)
    lines = [
        "# Schema change checklist",
        "",
        f"Generated by `specdev registry-generate` from `{ROWS_FILE.as_posix()}`. Do not hand-edit.",
        "",
        f"{len(rows)} changes since the 1.1.1 baseline across {len(groups)} schema groups. "
        "Each row says what happened to one path (or a glob of paths) of a schema; "
        "`replaced_by` names where the content went, `shim` marks a removed field a legacy reader still reads.",
    ]
    for step, group in groups.items():
        lines += [
            "",
            f"## {step}",
            "",
            "| ID | Path | Change | Replaced by | Owner | Design | Tickets | Shim |",
            "|---|---|---|---|---|---|---|---|",
            *(_row_line(r) for r in group),
        ]
    return "\n".join(lines) + "\n"


def generate_checklist(repo_root: Path) -> str:
    """Render the checklist of ``<repo_root>/tools/schema_changes.json``.

    Raises ``ChecklistError`` naming every problem when the rows file is not well formed.
    """
    rows, problems = load_rows(repo_root / ROWS_FILE)
    if problems:
        raise ChecklistError(f"{ROWS_FILE.as_posix()}: " + "; ".join(problems))
    return render_checklist(rows)
