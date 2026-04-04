from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from typing import Any, cast

from jsonschema import Draft202012Validator
from .lint import lint_canon_dirs
from .registry import CanonicalRegistry
from ..core.errors import SpecError, make_error
from ..core.registry import SchemaRegistry
from ..core.constants import INFERENCE_RULES


def canonical_autofix(
    repo_root: str,
    spec_dir: str,
    write: bool = False,
    canon_dir: str = "canon",
    require_manifest_schema_registration: bool = True,
    project_canon_dir: str | None = None,
) -> dict[str, list[str | SpecError]]:
    spec_dir_abs = os.path.abspath(spec_dir)
    if not os.path.isdir(spec_dir_abs):
        return {spec_dir_abs: [make_error("E520", f"UNRESOLVED_INPUT missing_spec_dir {spec_dir_abs}")]}
    preflight_errors = lint_canon_dirs(
        repo_root,
        canon_dir=canon_dir,
        project_canon_dir=project_canon_dir,
        require_manifest_schema_registration=require_manifest_schema_registration,
    )
    if preflight_errors:
        canon_root = os.path.join(os.path.abspath(repo_root), canon_dir)
        return {canon_root: _uniq(preflight_errors)}
    registry = CanonicalRegistry.load(repo_root, canon_dir=canon_dir, project_canon_dir=project_canon_dir)
    schema_registry, schema_registry_error = _load_schema_registry(repo_root)
    changes: dict[str, list[str | SpecError]] = {}
    if registry.load_errors:
        canon_root = os.path.join(os.path.abspath(repo_root), canon_dir)
        sorted_errs = sorted(set(registry.load_errors), key=lambda e: e.render())
        changes[canon_root] = cast(list[str | SpecError], sorted_errs)
        return changes
    pending_writes: dict[str, Any] = {}
    for path in _iter_json(spec_dir_abs):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            changes[path] = [make_error("E520", f"UNRESOLVED_INPUT {path} invalid_json {str(exc)}")]
            continue
        schema_validator, schema_error = _build_schema_validator(schema_registry, data, schema_registry_error)
        if schema_error:
            changes[path] = [make_error("E520", f"UNRESOLVED_INPUT {path} {schema_error}")]
            continue
        file_changes: list[str | SpecError] = []
        _autofix_node(data, registry, file_changes, data, schema_validator)
        _sync_canonical_refs_used(data, registry, file_changes)
        if file_changes:
            changes[path] = file_changes
            if write:
                pending_writes[path] = data
    if write and pending_writes:
        if _has_errors(changes):
            for path in sorted(pending_writes):
                changes.setdefault(path, []).append(
                    make_error("E520", f"UNRESOLVED_INPUT {path} write_aborted_due_to_errors")
                )
            return changes
        _apply_writes_atomically(pending_writes, changes)
    return changes


def _autofix_node(
    node: Any,
    registry: CanonicalRegistry,
    file_changes: list[str | SpecError],
    root_data: Any,
    schema_validator: Draft202012Validator | None,
    path: str = "",
) -> None:
    if isinstance(node, dict):
        for source_field, target_ref_field, kind in INFERENCE_RULES:
            _try_infer_ref(
                node,
                source_field,
                target_ref_field,
                kind,
                registry,
                file_changes,
                root_data,
                schema_validator,
                path,
            )
        for key, value in node.items():
            next_path = f"{path}.{key}" if path else key
            _autofix_node(value, registry, file_changes, root_data, schema_validator, next_path)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            next_path = f"{path}[{idx}]"
            _autofix_node(value, registry, file_changes, root_data, schema_validator, next_path)


def _try_infer_ref(
    obj: dict[str, Any],
    source_field: str,
    target_ref_field: str,
    kind: str,
    registry: CanonicalRegistry,
    file_changes: list[str | SpecError],
    root_data: Any,
    schema_validator: Draft202012Validator | None,
    path: str,
) -> None:
    value = obj.get(source_field)
    if not isinstance(value, str):
        return
    # If an explicit environment field exists, infer environment_ref from it
    # instead of stage to avoid cross-field misbinding.
    if source_field == "stage" and target_ref_field == "environment_ref":
        explicit_env = obj.get("environment")
        if isinstance(explicit_env, str):
            return
    # Restrict dependency inference from generic "id" to dependency-item shapes.
    if source_field == "id" and target_ref_field == "dependency_ref":
        dep_type = obj.get("type")
        if dep_type not in {"milestone", "external"}:
            return
    if target_ref_field in obj and isinstance(obj[target_ref_field], dict):
        return
    resolved = registry.resolve_alias(kind, value)
    if not resolved:
        return
    if registry.alias_is_deprecated(kind, value):
        normalized = " ".join(p for p in re.split(r"[\s_-]+", value.lower().strip()) if p)
        lc = registry.alias_lifecycle.get((kind, normalized), {})
        replaced_by = lc.get("replaced_by", "")
        file_changes.append(
            make_error("W570", f"GRACEFUL_SKIP {path or '$'} skipped autofix for deprecated alias {source_field}='{value}' replaced_by={replaced_by}")
        )
        return
    candidate_ref = {"id": resolved, "kind": kind}
    if not _apply_if_schema_valid(obj, target_ref_field, candidate_ref, root_data, schema_validator):
        return
    file_changes.append(f"{path or '$'} add {target_ref_field} from {source_field}")


def _iter_json(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


def _load_schema_registry(repo_root: str) -> tuple[SchemaRegistry | None, str | None]:
    try:
        return SchemaRegistry(repo_root), None
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, str(exc)


def _build_schema_validator(
    schema_registry: SchemaRegistry | None,
    data: Any,
    schema_registry_error: str | None,
) -> tuple[Draft202012Validator | None, str | None]:
    if not isinstance(data, dict):
        return None, f"invalid_document_root_type expected=object got={type(data).__name__}"
    schema_uri = data.get("$schema")
    if schema_uri is None:
        return None, "missing_schema_uri"
    if not isinstance(schema_uri, str):
        return None, f"invalid_schema_uri_type expected=str got={type(schema_uri).__name__}"
    schema_uri = schema_uri.strip()
    if not schema_uri:
        return None, "missing_schema_uri"
    if schema_registry is None:
        detail = schema_registry_error or "unknown"
        return None, f"schema_registry_bootstrap_failed detail={detail}"
    try:
        schema = schema_registry.load(schema_uri)
    except FileNotFoundError as exc:
        return None, f"schema_not_found uri={schema_uri} detail={str(exc)}"
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, f"schema_load_failed uri={schema_uri} detail={str(exc)}"
    try:
        reg = schema_registry.to_referencing_registry()
        validator = Draft202012Validator(
            schema,
            registry=reg,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        return validator, None
    except Exception as exc:
        return None, f"schema_validator_build_failed detail={type(exc).__name__}: {str(exc)}"


def _apply_if_schema_valid(
    obj: dict[str, Any],
    key: str,
    value: Any,
    root_data: Any,
    schema_validator: Draft202012Validator | None,
) -> bool:
    if schema_validator is None:
        obj[key] = value
        return True
    before = _validation_error_fingerprints(schema_validator, root_data)
    if before is None:
        return False
    obj[key] = value
    after = _validation_error_fingerprints(schema_validator, root_data)
    if after is None:
        obj.pop(key, None)
        return False
    if after - before:
        obj.pop(key, None)
        return False
    return True


def _has_errors(changes: dict[str, list[str | SpecError]]) -> bool:
    return any(
        (isinstance(item, SpecError) and item.code.startswith("E"))
        or (isinstance(item, str) and item.startswith("E"))
        for entries in changes.values()
        for item in entries
    )


def _uniq(messages: Sequence[str | SpecError]) -> list[str | SpecError]:
    return list(dict.fromkeys(messages))


def _apply_writes_atomically(pending_writes: dict[str, Any], changes: dict[str, list[str | SpecError]]) -> None:
    temp_outputs: dict[str, str] = {}
    backup_outputs: dict[str, str] = {}
    applied: list[str] = []
    try:
        # Phase 1: materialize all new payloads to temp files.
        for path, payload in pending_writes.items():
            directory = os.path.dirname(path) or "."
            fd, tmp_path = tempfile.mkstemp(prefix=".specdev-autofix-new-", suffix=".json", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                    f.write("\n")
            except (OSError, ValueError, TypeError) as exc:
                changes.setdefault(path, []).append(
                    make_error("E520", f"UNRESOLVED_INPUT {path} temp_write_failed {str(exc)}")
                )
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            temp_outputs[path] = tmp_path

        # Phase 2: snapshot originals to allow rollback if replace fails.
        for path in pending_writes:
            directory = os.path.dirname(path) or "."
            fd, backup_path = tempfile.mkstemp(prefix=".specdev-autofix-backup-", suffix=".json", dir=directory)
            os.close(fd)
            try:
                shutil.copy2(path, backup_path)
            except OSError as exc:
                changes.setdefault(path, []).append(
                    make_error("E520", f"UNRESOLVED_INPUT {path} backup_failed {str(exc)}")
                )
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass
                return
            backup_outputs[path] = backup_path

        # Phase 3: replace originals.
        for path, tmp_path in temp_outputs.items():
            try:
                os.replace(tmp_path, path)
                applied.append(path)
            except OSError as exc:
                changes.setdefault(path, []).append(
                    make_error("E520", f"UNRESOLVED_INPUT {path} write_failed {str(exc)}")
                )
                # Best-effort rollback for already-applied files.
                for applied_path in reversed(applied):
                    backup_path = backup_outputs.get(applied_path)
                    if not backup_path:
                        continue
                    try:
                        os.replace(backup_path, applied_path)
                    except OSError as rollback_exc:
                        changes.setdefault(applied_path, []).append(
                            make_error("E520", f"UNRESOLVED_INPUT {applied_path} rollback_failed {str(rollback_exc)}")
                        )
                return
    finally:
        for path, tmp_path in temp_outputs.items():
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        for backup_path in backup_outputs.values():
            if os.path.exists(backup_path):
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass


def _validation_error_fingerprints(validator: Draft202012Validator, root_data: Any) -> set[tuple[tuple[Any, ...], str, str]] | None:
    payload = root_data
    if isinstance(root_data, dict):
        payload = dict(root_data)
        payload.pop("$schema", None)
    try:
        errors = validator.iter_errors(payload)
        fingerprints: set[tuple[tuple[Any, ...], str, str]] = set()
        for err in errors:
            fingerprints.add((tuple(err.path), str(err.validator), err.message))
        return fingerprints
    except Exception:
        return None


def _sync_canonical_refs_used(data: Any, registry: CanonicalRegistry, file_changes: list[str | SpecError]) -> None:
    if not isinstance(data, dict):
        return
    declared = data.get("canonical_refs_used")
    if not isinstance(declared, list):
        return
    used_refs = _collect_used_refs(data)
    if not used_refs:
        return
    declared_ids = {
        item.get("id")
        for item in declared
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].startswith("cn:")
    }
    for cid in sorted(used_refs.keys()):
        if cid in declared_ids:
            continue
        ref_obj = used_refs[cid]
        entry = registry.get(cid)
        new_declared_ref = {"id": cid, "kind": ref_obj["kind"]}
        if entry is not None:
            new_declared_ref["version"] = entry.version
        declared.append(new_declared_ref)
        declared_ids.add(cid)
        file_changes.append(f"$ add canonical_refs_used id={cid}")


def _collect_used_refs(node: Any) -> dict[str, dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if key.endswith("_ref") and isinstance(value, dict):
                cid = value.get("id")
                kind = value.get("kind")
                if isinstance(cid, str) and cid.startswith("cn:") and isinstance(kind, str) and kind:
                    refs.setdefault(cid, {"kind": kind})
            nested = _collect_used_refs(value)
            refs.update({k: v for k, v in nested.items() if k not in refs})
    elif isinstance(node, list):
        for value in node:
            nested = _collect_used_refs(value)
            refs.update({k: v for k, v in nested.items() if k not in refs})
    return refs


# INFERENCE_RULES imported from core.constants to allow reuse in context/canon_extractor.py
# without circular imports.  The canonical definition lives in core/constants.py.
