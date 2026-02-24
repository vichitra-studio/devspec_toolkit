from __future__ import annotations

import json
import os
import re
from typing import Any


PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|placeholder|<[^>]+>)\b", re.IGNORECASE)
STEP_ARTIFACT_RE = re.compile(r"^\d{2}[a-z]?_[a-z0-9_]+\.json$")
STEP_SCHEMA_URI_RE = re.compile(r"^https://specdev\.local/schema/\d{2}[a-z]?_[a-z0-9_]+\.schema\.json$")
CRITICAL_ARRAY_KEYS = {"functional_requirements", "terms", "apis", "rules", "nfrs", "fixtures", "milestones", "jobs", "threats"}


def lint_spec_quality(spec_dir: str) -> list[str]:
    errors: list[str] = []
    known_ids: set[str] = set()
    refs: list[tuple[str, str, str]] = []

    for path in _iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, spec_dir)
            errors.append(f"E520 UNRESOLVED_INPUT {rel} invalid_json {exc}")
            continue
        if not _is_step_artifact(path, data):
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_check_required_top_level(rel, data))
        errors.extend(_check_placeholders(rel, data))
        errors.extend(_check_critical_arrays(rel, data))
        _collect_ids_and_refs(data, rel, known_ids, refs)

    for rel, p, ref_id in refs:
        if ref_id.startswith("external:") or ref_id.startswith("cn:"):
            continue
        if ref_id not in known_ids:
            errors.append(f"E520 UNRESOLVED_INPUT {rel}:{p} ref={ref_id}")

    return errors


def lint_spec_quality_file(path: str, spec_dir: str | None = None) -> list[str]:
    """Run per-artifact quality checks used by single-file validation.

    This enforces deterministic top-level and placeholder/array checks without
    requiring full-directory reference closure.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        rel = os.path.relpath(path, spec_dir or os.path.dirname(path) or ".")
        return [f"E520 UNRESOLVED_INPUT {rel} invalid_json {exc}"]

    if not _is_step_artifact(path, data):
        return []

    base = spec_dir or os.path.dirname(path) or "."
    rel = os.path.relpath(path, base)
    errs: list[str] = []
    errs.extend(_check_required_top_level(rel, data))
    errs.extend(_check_placeholders(rel, data))
    errs.extend(_check_critical_arrays(rel, data))
    return errs


def _check_required_top_level(rel: str, data: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for key in (
        "id",
        "owner",
        "created_at",
        "seed_refs",
        "generation_quality",
        "canonical_refs_used",
        "canonical_proposals",
        "canonical_conflicts",
    ):
        if key not in data:
            errs.append(f"E520 UNRESOLVED_INPUT {rel} missing top-level '{key}'")
    return errs


def _check_placeholders(rel: str, data: Any, path: str = "") -> list[str]:
    errs: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            errs.extend(_check_placeholders(rel, v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            p = f"{path}[{i}]"
            errs.extend(_check_placeholders(rel, v, p))
    elif isinstance(data, str):
        if PLACEHOLDER_RE.search(data):
            errs.append(f"E510 PLACEHOLDER_VALUE_FOUND {rel}:{path} value={data}")
    return errs


def _check_critical_arrays(rel: str, data: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for key in CRITICAL_ARRAY_KEYS:
        if key in data and isinstance(data[key], list) and len(data[key]) == 0:
            errs.append(f"E520 UNRESOLVED_INPUT {rel} empty critical array '{key}'")
    return errs


def _collect_ids_and_refs(obj: Any, rel: str, ids: set[str], refs: list[tuple[str, str, str]], path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k.endswith("_id") and isinstance(v, str):
                ids.add(v)
            if k in {"id", "target_id"} and isinstance(v, str) and _is_reference_context(path):
                refs.append((rel, p, v))
            if k.endswith("_ref") and isinstance(v, str):
                refs.append((rel, p, v))
            if k.endswith("_refs") and isinstance(v, list):
                for idx, ref_val in enumerate(v):
                    if isinstance(ref_val, str):
                        refs.append((rel, f"{p}[{idx}]", ref_val))
            _collect_ids_and_refs(v, rel, ids, refs, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _collect_ids_and_refs(v, rel, ids, refs, f"{path}[{i}]")


def _is_reference_context(path: str) -> bool:
    if not path:
        return False
    normalized = re.sub(r"\[\d+\]", "", path)
    segments = [seg for seg in normalized.split(".") if seg]
    return any(seg in {"trace", "targets", "dependencies", "links", "target_ids", "mitigations"} for seg in segments)


def _iter_json(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


def _is_step_artifact(path: str, data: dict[str, Any] | None = None) -> bool:
    if STEP_ARTIFACT_RE.match(os.path.basename(path)):
        return True
    if isinstance(data, dict):
        schema_uri = data.get("$schema")
        if isinstance(schema_uri, str) and STEP_SCHEMA_URI_RE.match(schema_uri):
            return True
    return False
