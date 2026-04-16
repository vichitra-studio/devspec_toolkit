from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from referencing import Registry

from ..core.errors import SpecError, make_error
from ..core.registry import SchemaRegistry

FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
EMBEDDED_SCHEMA_RE = re.compile(r"#+\s*Embedded Schema\s*```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
OUTPUT_CONTRACT_HEADING_RE = re.compile(r"(?im)^#\s*Output Contract\b.*$")
SUBHEADING_RE = re.compile(r"(?im)^##\s+")
SCHEMA_URI_RE = re.compile(r"(?im)^\s*-\s*Schema URI:\s*(\S+)\s*$")
SCHEMA_FILE_RE = re.compile(r"(?im)^\s*-\s*Schema File:\s*(\S+)\s*$")
DRIFT_SENSITIVE_FIELDS = (
    "dependencies",
    "trace",
    "canonical_refs_used",
)

# Schema-filename → step-key override.  ``schema_contracts`` is keyed by the
# numeric prefix of the schema filename (``Path(schema_file).name.split("_", 1)[0]``).
# Two schemas with the same prefix will silently overwrite each other unless one
# is given an explicit, distinct key here.  Currently:
#
#   - ``16_anchor.schema.json`` and ``16_impl_context.schema.json`` both yield
#     ``"16"``.  Without the override below, alphabetical sort processes the
#     anchor first, then impl-context overwrites ``schema_contracts["16"]``,
#     making the anchor schema invisible to ``_validate_output_contracts`` and
#     causing false E310 fires when ``prompt_16_impl_context.md`` is checked
#     against the anchor schema.
#
# Add new entries when a future schema collides on numeric prefix.  Keep the
# overridden key prefixed by the numeric step (e.g. ``"16anchor"``) so it
# remains adjacent to the family it belongs to in ``DEEP_VALIDATORS`` and any
# downstream consumer that scans ``schema_contracts`` keys alphabetically.
_SCHEMA_FILE_TO_STEP_KEY: dict[str, str] = {
    "16_anchor.schema.json": "16anchor",
}


def run_prompt_schema_sync(repo_root: str) -> list[SpecError]:
    root = Path(os.path.abspath(repo_root))
    schema_dir = root / "schema"
    prompt_dir = root / "prompts"
    errors: list[SpecError] = []
    schema_contracts: dict[str, tuple[str, dict[str, Any], list[str], dict[str, Any]]] = {}
    registry_map, registry_map_error = _schema_registry_map(root)

    schema_files = sorted(glob.glob(str(schema_dir / "*.schema.json")))
    for schema_file in schema_files:
        schema_filename = Path(schema_file).name
        if schema_filename in _SCHEMA_FILE_TO_STEP_KEY:
            step = _SCHEMA_FILE_TO_STEP_KEY[schema_filename]
        else:
            step = schema_filename.split("_", 1)[0]
        if step == "seed":
            continue
        try:
            schema_required, schema_props, schema = _load_contract(schema_file)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(make_error("E520", f"UNRESOLVED_INPUT invalid_schema {schema_file} {exc}"))
            continue
        schema_contracts[step] = (schema_file, schema, schema_required, schema_props)
        prompt_candidates = _prompt_candidates(prompt_dir, step)
        if not prompt_candidates:
            continue
        for prompt_path in prompt_candidates:
            # Prompts with a _PROMPT_STEP_OVERRIDE entry are validated by
            # _validate_output_contracts against their overridden schema — skip
            # them here to avoid double-validation against the wrong schema.
            if Path(prompt_path).name in _PROMPT_STEP_OVERRIDE:
                continue
            schema_ref, schema_ref_line = _extract_schema_reference(prompt_path)
            errors.extend(
                _schema_reference_errors(
                    prompt_path=prompt_path,
                    line_no=schema_ref_line,
                    schema_file=schema_file,
                    schema=schema,
                    schema_ref=schema_ref,
                    registry_map=registry_map,
                    registry_map_error=registry_map_error,
                    repo_root=root,
                )
            )
            prompt_required, prompt_props, prompt_schema, line_no = _extract_prompt_contract(prompt_path)
            if prompt_required is None:
                if schema_ref is None:
                    errors.append(make_error(
                        "E310",
                        f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
                        "missing JSON contract block and schema reference",
                    ))
                continue
            missing = sorted(set(schema_required) - set(prompt_required))
            extra = sorted(set(prompt_required) - set(schema_required))
            if missing:
                errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing required {missing}"))
            if extra:
                errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} extra required {extra}"))
            errors.extend(
                _drift_sensitive_property_errors(
                    prompt_path,
                    line_no,
                    schema_props,
                    prompt_props,
                )
            )
            errors.extend(
                _required_canonical_ref_errors(
                    prompt_path,
                    line_no,
                    schema,
                    prompt_schema,
                )
            )

    errors.extend(_validate_output_contracts(prompt_dir, schema_contracts, root))
    return errors


def _load_contract(schema_path: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    required = schema.get("required", []) or []
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        props = {}
    return required, props, schema


def _prompt_candidates(prompt_dir: Path, step: str) -> list[str]:
    return sorted(glob.glob(str(prompt_dir / f"prompt_{step}_*.md")))


def _extract_prompt_contract(prompt_path: str) -> tuple[list[str] | None, dict[str, object], dict[str, Any], int]:
    with open(prompt_path, "r", encoding="utf-8") as f:
        text = f.read()
    embedded = EMBEDDED_SCHEMA_RE.search(text)
    blocks: list[tuple[str, int]] = []
    if embedded:
        line_no = text[:embedded.start(1)].count("\n") + 1
        blocks.append((embedded.group(1), line_no))
    for m in FENCED_JSON_RE.finditer(text):
        line_no = text[:m.start(1)].count("\n") + 1
        blocks.append((m.group(1), line_no))
    for block, line_no in blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        # Prefer schema-like blocks; ignore output examples.
        if isinstance(parsed.get("properties"), dict):
            req = parsed.get("required")
            if isinstance(req, list):
                props = parsed.get("properties", {})
                if not isinstance(props, dict):
                    props = {}
                return req, props, parsed, line_no
    return None, {}, {}, 1


def _extract_schema_reference(prompt_path: str) -> tuple[dict[str, str] | None, int]:
    with open(prompt_path, "r", encoding="utf-8") as f:
        text = f.read()
    uri_match = SCHEMA_URI_RE.search(text)
    file_match = SCHEMA_FILE_RE.search(text)
    if not uri_match and not file_match:
        return None, 1
    line_numbers = []
    if uri_match:
        line_numbers.append(text[:uri_match.start(1)].count("\n") + 1)
    if file_match:
        line_numbers.append(text[:file_match.start(1)].count("\n") + 1)
    line_no = min(line_numbers) if line_numbers else 1
    return {
        "uri": uri_match.group(1).strip() if uri_match else "",
        "file": file_match.group(1).strip() if file_match else "",
    }, line_no


def _schema_registry_map(repo_root: Path) -> tuple[dict[str, str] | None, str | None]:
    try:
        schema_registry = SchemaRegistry(str(repo_root))
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return None, str(exc)
    return schema_registry.map, None


def _schema_reference_errors(
    prompt_path: str,
    line_no: int,
    schema_file: str,
    schema: dict[str, Any],
    schema_ref: dict[str, str] | None,
    registry_map: dict[str, str] | None,
    registry_map_error: str | None,
    repo_root: Path,
) -> list[SpecError]:
    errors: list[SpecError] = []
    if schema_ref is None:
        errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing schema reference section"))
        return errors

    uri = schema_ref.get("uri", "").strip()
    rel_file = schema_ref.get("file", "").strip()
    expected_uri = schema.get("$id")
    expected_rel_file = Path(
        os.path.relpath(os.path.abspath(schema_file), os.path.abspath(str(repo_root)))
    ).as_posix()

    if not uri:
        errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing schema URI reference"))
    elif isinstance(expected_uri, str) and expected_uri.strip() and uri != expected_uri:
        errors.append(make_error(
            "E310",
            f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
            f"schema_uri_mismatch expected='{expected_uri}' got='{uri}'",
        ))

    if not rel_file:
        errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing schema file reference"))
    elif Path(rel_file).as_posix() != expected_rel_file:
        errors.append(make_error(
            "E310",
            f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
            f"schema_file_mismatch expected='{expected_rel_file}' got='{Path(rel_file).as_posix()}'",
        ))

    if registry_map is None:
        detail = registry_map_error or "unknown"
        errors.append(make_error(
            "E520",
            f"UNRESOLVED_INPUT {prompt_path}:{line_no} "
            f"schema_registry_bootstrap_failed detail={detail}",
        ))
        return errors

    if uri:
        mapped = registry_map.get(uri)
        if not mapped:
            errors.append(make_error(
                "E310",
                f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
                f"schema_uri_not_registered uri='{uri}'",
            ))
        elif rel_file and Path(mapped).as_posix() != Path(rel_file).as_posix():
            errors.append(make_error(
                "E310",
                f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
                f"schema_registry_path_mismatch uri='{uri}' registry='{Path(mapped).as_posix()}' "
                f"prompt='{Path(rel_file).as_posix()}'",
            ))

    return errors


def _drift_sensitive_property_errors(
    prompt_path: str,
    line_no: int,
    schema_props: dict[str, object],
    prompt_props: dict[str, object],
) -> list[SpecError]:
    fields = DRIFT_SENSITIVE_FIELDS
    errors: list[SpecError] = []
    for field in fields:
        schema_prop = schema_props.get(field)
        prompt_prop = prompt_props.get(field)
        if schema_prop is None:
            continue
        if prompt_prop is None:
            errors.append(make_error(
                "E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing property field='{field}'"
            ))
            continue
        if not (isinstance(schema_prop, dict) and isinstance(prompt_prop, dict)):
            continue
        if _canonical_json(schema_prop) != _canonical_json(prompt_prop):
            errors.append(make_error(
                "E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} property_drift field='{field}'"
            ))
    return errors


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _required_canonical_ref_errors(
    prompt_path: str,
    line_no: int,
    schema: dict[str, Any],
    prompt_schema: dict[str, Any],
) -> list[SpecError]:
    expected = _collect_required_canonical_ref_paths(schema)
    if not expected:
        return []
    actual = _collect_required_canonical_ref_paths(prompt_schema)
    missing = sorted(expected - actual)
    if not missing:
        return []
    return [make_error(
        "E310",
        f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
        f"missing_required_canonical_refs {missing}",
    )]


def _collect_required_canonical_ref_paths(node: Any, path: str = "$") -> set[str]:
    paths: set[str] = set()
    if not isinstance(node, dict):
        return paths

    properties = node.get("properties")
    required = node.get("required")
    if isinstance(properties, dict):
        required_set = set(required) if isinstance(required, list) else set()
        for key, value in properties.items():
            child_path = f"{path}.{key}" if path else key
            if (
                key in required_set
                and key.endswith("_ref")
                and isinstance(value, dict)
                and "canonicalRef" in value.get("$ref", "")
            ):
                paths.add(child_path)
            paths.update(_collect_required_canonical_ref_paths(value, child_path))

    items = node.get("items")
    if isinstance(items, dict):
        paths.update(_collect_required_canonical_ref_paths(items, f"{path}[]"))

    for key in ("allOf", "anyOf", "oneOf"):
        branches = node.get(key)
        if isinstance(branches, list):
            for idx, branch in enumerate(branches):
                paths.update(_collect_required_canonical_ref_paths(branch, f"{path}.{key}[{idx}]"))

    return paths


def _validate_output_contracts(
    prompt_dir: Path,
    schema_contracts: dict[str, tuple[str, dict[str, Any], list[str], dict[str, Any]]],
    repo_root: Path,
) -> list[SpecError]:
    errors: list[SpecError] = []
    registry, registry_error = _schema_registry(repo_root)
    if registry_error:
        errors.append(make_error(
            "E520",
            f"UNRESOLVED_INPUT {repo_root / 'tools' / 'schema_registry.json'} "
            f"schema_registry_bootstrap_failed {registry_error}",
        ))
    for prompt_path in sorted(glob.glob(str(prompt_dir / "prompt_*.md"))):
        step = _PROMPT_STEP_OVERRIDE.get(Path(prompt_path).name) or _step_from_prompt_name(Path(prompt_path).name)
        if not step:
            continue
        base_step = _SUBSTEP_TO_BASE_SCHEMA.get(step, step)
        contract = schema_contracts.get(base_step)
        if not contract:
            continue
        _, schema, _, _ = contract
        output_payload, line_no, parse_error = _extract_output_contract(prompt_path)
        if parse_error:
            errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} {parse_error}"))
            continue
        if not isinstance(output_payload, dict):
            errors.append(make_error(
                "E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} output_contract_must_be_json_object"
            ))
            continue
        schema_uri_error = _validate_output_schema_uri(output_payload, schema)
        if schema_uri_error:
            errors.append(make_error("E310", f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} {schema_uri_error}"))
            continue
        payload = dict(output_payload)
        payload.pop("$schema", None)
        errors.extend(_validate_output_payload(prompt_path, line_no, payload, schema, registry))
        # W580 — sub-step domain drift detection (forward-only)
        # Trinity Loop steps accumulate upstream sections:
        # 16a writes plan; 16b reads plan + writes execution;
        # 16c reads plan+execution + writes review.
        # Only warn about keys from LATER steps (forward drift).
        if step in _SUBSTEP_EXPECTED_KEYS and isinstance(output_payload, dict):
            payload_keys = set(output_payload.keys()) - {"$schema"}
            step_idx = _SUBSTEP_ORDER.index(step)
            for other_step, other_keys in _SUBSTEP_EXPECTED_KEYS.items():
                other_idx = _SUBSTEP_ORDER.index(other_step)
                if other_idx <= step_idx:
                    continue  # upstream or self — allowed
                foreign_keys = payload_keys & other_keys
                if foreign_keys:
                    errors.append(make_error(
                        "W580",
                        f"SUBSTEP_DRIFT {prompt_path}:{line_no} "
                        f"sub-step '{step}' output contract contains keys "
                        f"from '{other_step}' domain: {sorted(foreign_keys)}",
                    ))
            # Anchor-exclusive keys are never legitimate in 16a/16b/16c payloads.
            anchor_leak = payload_keys & _ANCHOR_EXCLUSIVE_KEYS
            if anchor_leak:
                errors.append(make_error(
                    "W580",
                    f"SUBSTEP_DRIFT {prompt_path}:{line_no} "
                    f"sub-step '{step}' output contract contains keys "
                    f"from '16anchor' domain: {sorted(anchor_leak)}",
                ))
    return errors


_SUBSTEP_TO_BASE_SCHEMA = {
    "16a": "16",
    "16b": "16",
    "16c": "16",
}

# Prompt filename → explicit step key override.  Used when the auto-extracted step
# key from _step_from_prompt_name() would map to the wrong schema entry.
# prompt_16_impl_context.md authors the Trinity Anchor (vc:16-anchor), not a
# milestone plan (vc:16-impl-context).  Its step key must be "16anchor" so
# _validate_output_contracts validates it against the anchor schema.
_PROMPT_STEP_OVERRIDE: dict[str, str] = {
    "prompt_16_impl_context.md": "16anchor",
}

# Forward-drift domains for W580 within the Trinity Loop (16a → 16b → 16c).
# Each set is the keys UNIQUELY written by that step. Shared keys (top-level
# `plan`, `plan.summary`, `plan.ambiguities`) are intentionally absent because
# they legitimately appear in multiple artifacts with different semantics.
_SUBSTEP_EXPECTED_KEYS = {
    "16a": {"spec_alignment", "checklist"},
    "16b": {"execution", "implementation", "evidence"},
    "16c": {"review", "verdict", "semantic_review"},
}

_SUBSTEP_ORDER = ["16a", "16b", "16c"]

# Anchor-exclusive keys — no Trinity sub-step (16a/16b/16c) should emit these.
# Unlike the Trinity forward-drift relationship, the anchor is an independent
# artifact (vc:16-anchor) read by 16a/b/c but never written by them, so the
# check here is direction-free: any presence in a Trinity sub-step payload is a
# contract violation routed via W580 SUBSTEP_DRIFT.
_ANCHOR_EXCLUSIVE_KEYS: frozenset[str] = frozenset({"artifact_role", "milestone_index"})


def _step_from_prompt_name(name: str) -> str | None:
    match = re.match(r"prompt_(\d{2}[a-z]?)_", name)
    if not match:
        return None
    return match.group(1)


def _extract_output_contract(prompt_path: str) -> tuple[dict[str, Any] | None, int, str | None]:
    with open(prompt_path, "r", encoding="utf-8") as f:
        text = f.read()
    heading_match = OUTPUT_CONTRACT_HEADING_RE.search(text)
    if not heading_match:
        return None, 1, "missing output contract section"
    section_start = heading_match.end()
    subheading_match = SUBHEADING_RE.search(text, section_start)
    section_end = subheading_match.start() if subheading_match else len(text)
    section = text[section_start:section_end]
    blocks = list(FENCED_JSON_RE.finditer(section))
    if not blocks:
        line_no = text[:section_start].count("\n") + 1
        return None, line_no, "missing output contract JSON block"
    # Enforce that the latest block in the Output Contract section is authoritative.
    last_block = blocks[-1]
    line_no = text[: section_start + last_block.start(1)].count("\n") + 1
    try:
        payload = json.loads(last_block.group(1))
    except json.JSONDecodeError:
        return None, line_no, "invalid output contract JSON block"
    return payload, line_no, None


def _validate_output_schema_uri(payload: dict[str, Any], schema: dict[str, Any]) -> str | None:
    expected_schema_uri = schema.get("$id")
    if not isinstance(expected_schema_uri, str) or not expected_schema_uri.strip():
        return None
    got_schema_uri = payload.get("$schema")
    if got_schema_uri is None:
        return None
    if not isinstance(got_schema_uri, str) or not got_schema_uri.strip():
        return f"output_contract_invalid_schema_uri expected='{expected_schema_uri}' got='{got_schema_uri}'"
    got_schema_uri = got_schema_uri.strip()
    if got_schema_uri != expected_schema_uri:
        return (
            f"output_contract_schema_uri_mismatch expected='{expected_schema_uri}' "
            f"got='{got_schema_uri}'"
        )
    return None


def _schema_registry(repo_root: Path) -> tuple[Registry | None, str | None]:
    try:
        schema_registry = SchemaRegistry(str(repo_root))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return schema_registry.to_referencing_registry(), None


_DEAD_FIELD_DEFAULTS: dict[str, Any] = {
    "canonical_proposals": [],
    "canonical_conflicts": [],
}
"""Fields removed from prompts but still required by step schemas.
Injected as defaults so prompt-schema sync validation does not raise
false-positive drift errors."""


def _validate_output_payload(
    prompt_path: str,
    line_no: int,
    payload: dict[str, Any],
    schema: dict[str, Any],
    registry: Registry | None,
) -> list[SpecError]:
    # Inject dead-field defaults so Output Contract examples validate against
    # schemas that still list these as required (pending FIX-061..065).
    patched = dict(payload)
    for field, default in _DEAD_FIELD_DEFAULTS.items():
        patched.setdefault(field, default)
    try:
        if registry is None:
            validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        else:
            validator = Draft202012Validator(
                schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
        validation_errors = sorted(validator.iter_errors(patched), key=lambda e: list(e.path))
    except _WrappedReferencingError as exc:
        return [make_error(
            "E520",
            f"UNRESOLVED_INPUT {prompt_path}:{line_no} "
            f"output_contract_schema_resolution_failed {exc}",
        )]
    except Exception as exc:
        return [make_error(
            "E521",
            f"VALIDATOR_RUNTIME {prompt_path}:{line_no} "
            f"output_contract_schema_validation_runtime_error {type(exc).__name__}: {exc}",
        )]
    errors: list[SpecError] = []
    for err in validation_errors[:5]:
        path = f"/{'/'.join(map(str, err.path))}" if err.path else "$"
        errors.append(make_error(
            "E310",
            f"PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
            f"output_contract_schema_error path='{path}' {err.message}",
        ))
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    args = p.parse_args()
    errs = run_prompt_schema_sync(args.repo_root)
    if errs:
        for err in errs:
            print(err.render())
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
