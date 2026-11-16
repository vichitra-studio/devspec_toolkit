from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

from ..core.errors import SpecError, make_error
from .linter_utils import (
    build_file_graph_or_none,
    build_lint_graph,
    collect_ids_and_refs,
    graph_covered_files,
    graph_known_ids,
    is_reference_context,
    iter_json,
)

if TYPE_CHECKING:
    from ..graph.model import Graph


PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX|placeholder|<[^>]+>)\b", re.IGNORECASE)
STEP_ARTIFACT_RE = re.compile(r"^\d{2}[a-z]?_[a-z0-9_]+\.json$")
ASSUMPTION_ID_RE = re.compile(r"\b((?:fr|api|cap|nfr|inv|fix|comp|job|step|role|env|unit|stage|owner|trace|gov)-[a-z0-9]+(?:-[a-z0-9]+)*)\b")
# Spec baseline: few|some|many|several|various — extended with safe additions: fast|reliable|easy|hard|quick
# R9: additional vague terms: appropriate|adequate|sufficient|reasonable|significant|typical|generally|usually
VAGUE_QUANTIFIER_RE = re.compile(
    r"\b(few|some|many|several|various|fast|reliable|easy|hard|quick"
    r"|appropriate|adequate|sufficient|reasonable|significant|typical|generally|usually)\b",
    re.IGNORECASE,
)
# Free-text fields to scan for vague language (beyond assumptions)
_VAGUE_SCAN_FIELDS = {
    "description", "statement", "rationale", "justification", "notes",
    "narrative", "postconditions", "preconditions", "risks", "spikes",
    "migration_plan", "definition",
}
# Metadata fields that should NOT be scanned
_METADATA_FIELDS = {"$schema", "id", "owner", "created_at", "specdev_version"}
STEP_SCHEMA_URI_RE = re.compile(r"^vc:\d{2}[a-z]?-[a-z0-9-]+$")
CRITICAL_ARRAY_KEYS = {"functional_requirements", "terms", "apis", "rules", "nfrs", "fixtures", "milestones", "jobs", "threats"}

# Maximum number of assumptions before W572 fires.  Chosen empirically:
# most well-scoped spec artifacts have <10 assumptions.
_ASSUMPTION_THRESHOLD = 10


def lint_spec_quality(spec_dir: str, *, graph: Graph | None = None) -> list[SpecError]:
    """Quality checks over every artifact of *spec_dir*, plus reference closure over the ids the spec defines.

    Definitions come from *graph* (built here when ``None``) for the files it covers and from a scan of the file
    for the others.  Returns the findings; never raises.
    """
    errors: list[SpecError] = []
    graph = build_lint_graph(spec_dir) if graph is None else graph
    covered = graph_covered_files(graph)
    known_ids = graph_known_ids(graph)
    refs: list[tuple[str, str, str]] = []

    for path in iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, spec_dir)
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}"))
            continue
        if not _is_step_artifact(path, data):
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_check_required_top_level(rel, data))
        placeholder_errs, _ = _check_placeholders(rel, data)
        errors.extend(placeholder_errs)
        errors.extend(_check_critical_arrays(rel, data))
        errors.extend(_check_free_text_vague(rel, data))
        collect_ids_and_refs(data, rel, known_ids, refs, skip_ids_for_files=covered)

    # Second pass: assumption checks with full cross-artifact known_ids
    for path in iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not _is_step_artifact(path, data):
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_check_assumptions(rel, data, known_ids))

    for rel, p, ref_id in refs:
        if ref_id.startswith("external:") or ref_id.startswith("cn:"):
            continue
        if ref_id not in known_ids:
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel}:{p} ref={ref_id}"))

    return errors


def lint_spec_quality_file(path: str, spec_dir: str | None = None, *, graph: Graph | None = None) -> list[SpecError]:
    """Run per-artifact quality checks used by single-file validation.

    This enforces deterministic top-level and placeholder/array checks without
    requiring full-directory reference closure.  The ids an assumption may name come from *graph* (the one-file
    graph slice when ``None``), or from a scan of the file when the graph holds no node of it.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        rel = os.path.relpath(path, spec_dir or os.path.dirname(path) or ".")
        return [make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}")]

    if not _is_step_artifact(path, data):
        return []

    base = spec_dir or os.path.dirname(path) or "."
    rel = os.path.relpath(path, base)
    errs: list[SpecError] = []
    errs.extend(_check_required_top_level(rel, data))
    placeholder_errs, _ = _check_placeholders(rel, data)
    errs.extend(placeholder_errs)
    errs.extend(_check_critical_arrays(rel, data))
    errs.extend(_check_free_text_vague(rel, data))
    errs.extend(_check_assumptions(rel, data, _single_file_known_ids(path, rel, data, graph)))
    return errs


def _single_file_known_ids(path: str, rel: str, data: Any, graph: Graph | None) -> set[str]:
    """Ids an assumption of the single file *path* may name: graph nodes, else the ids the file's fields define."""
    if graph is None:
        graph = build_file_graph_or_none(path, data)
        covered = frozenset({rel.replace(os.sep, "/")}) if graph is not None and graph.nodes else frozenset()
    else:
        covered = graph_covered_files(graph)
    known_ids = graph_known_ids(graph)
    collect_ids_and_refs(data, rel, known_ids, [], skip_ids_for_files=covered)
    return known_ids


def _check_assumptions(rel: str, data: Any, known_ids: set[str], path: str = "") -> list[SpecError]:
    """RFC 3.6: Warn if assumption text references unbound spec IDs."""
    errs: list[SpecError] = []
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            if k == "assumptions":
                if isinstance(v, list) and len(v) > _ASSUMPTION_THRESHOLD:
                    errs.append(make_error("W572", f"ASSUMPTION_COUNT_HIGH {rel}:{p} count={len(v)}"))
                errs.extend(_scan_assumption_value(rel, v, known_ids, p))
            else:
                errs.extend(_check_assumptions(rel, v, known_ids, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            errs.extend(_check_assumptions(rel, v, known_ids, f"{path}[{i}]"))
    return errs


def _scan_assumption_value(rel: str, value: Any, known_ids: set[str], path: str) -> list[SpecError]:
    """Scan one ``assumptions`` value: a string, a list of them, or an assumption node whose ``text`` is scanned."""
    errs: list[SpecError] = []
    if isinstance(value, dict):
        if "text" in value:
            errs.extend(_scan_assumption_value(rel, value["text"], known_ids, f"{path}.text"))
    elif isinstance(value, str):
        if PLACEHOLDER_RE.search(value):
            errs.append(make_error("E512", f"ASSUMPTION_HAS_PLACEHOLDER {rel}:{path} value={value}"))
        for token in _scan_for_vague_language(value):
            errs.append(make_error("W571", f"ASSUMPTION_VAGUE_QUANTIFIER {rel}:{path} ref={token}"))
        for m in ASSUMPTION_ID_RE.finditer(value):
            token = m.group(1)
            if token not in known_ids:
                errs.append(make_error("W573", f"ASSUMPTION_UNBOUND_ID {rel}:{path} ref={token}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            errs.extend(_scan_assumption_value(rel, item, known_ids, f"{path}[{i}]"))
    return errs


def _scan_for_vague_language(text: str) -> list[str]:
    """Extract vague terms from a text string. Returns list of matched tokens."""
    return [m.group(1) for m in VAGUE_QUANTIFIER_RE.finditer(text)]


def _check_free_text_vague(rel: str, data: Any, path: str = "") -> list[SpecError]:
    """R9/T18: Scan all free-text fields (not assumptions) for vague language."""
    errs: list[SpecError] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in _METADATA_FIELDS:
                continue
            p = f"{path}.{k}" if path else k
            if k in _VAGUE_SCAN_FIELDS and isinstance(v, str):
                for token in _scan_for_vague_language(v):
                    errs.append(make_error("W593", f"VAGUE_LANGUAGE_FREE_TEXT {rel}:{p} ref={token}"))
            elif k != "assumptions":
                errs.extend(_check_free_text_vague(rel, v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            errs.extend(_check_free_text_vague(rel, v, f"{path}[{i}]"))
    return errs


def _check_required_top_level(rel: str, data: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    for key in (
        "id",
        "owner",
        "created_at",
        "canonical_refs_used",
    ):
        if key not in data:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT {rel} missing top-level '{key}'"))
    return errs


def _check_placeholders(rel: str, data: Any, path: str = "") -> tuple[list[SpecError], set[str]]:
    errs: list[SpecError] = []
    found: set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            child_errs, child_found = _check_placeholders(rel, v, p)
            errs.extend(child_errs)
            found.update(child_found)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            p = f"{path}[{i}]"
            child_errs, child_found = _check_placeholders(rel, v, p)
            errs.extend(child_errs)
            found.update(child_found)
    elif isinstance(data, str):
        matches = PLACEHOLDER_RE.findall(data)
        if matches:
            found.update(m.upper() for m in matches)
            errs.append(make_error("E510", f"PLACEHOLDER_VALUE_FOUND {rel}:{path} value={data}"))
    return errs, found


def _check_critical_arrays(rel: str, data: dict[str, Any]) -> list[SpecError]:
    errs: list[SpecError] = []
    for key in CRITICAL_ARRAY_KEYS:
        if key in data and isinstance(data[key], list) and len(data[key]) == 0:
            errs.append(make_error("E520", f"UNRESOLVED_INPUT {rel} empty critical array '{key}'"))
    return errs


def _is_step_artifact(path: str, data: dict[str, Any] | None = None) -> bool:
    if STEP_ARTIFACT_RE.match(os.path.basename(path)):
        return True
    if isinstance(data, dict):
        schema_uri = data.get("$schema")
        if isinstance(schema_uri, str) and STEP_SCHEMA_URI_RE.match(schema_uri):
            return True
    return False
