from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError
from referencing import Registry, Resource

from .registry import SchemaRegistry

FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
EMBEDDED_SCHEMA_RE = re.compile(r"#+\s*Embedded Schema\s*```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
OUTPUT_CONTRACT_HEADING_RE = re.compile(r"(?im)^#\s*Output Contract\b.*$")
SUBHEADING_RE = re.compile(r"(?im)^##\s+")
DRIFT_SENSITIVE_FIELDS = (
    "dependencies",
    "trace",
    "generation_quality",
    "canonical_refs_used",
    "canonical_proposals",
    "canonical_conflicts",
)


def run_prompt_schema_sync(repo_root: str) -> list[str]:
    root = Path(os.path.abspath(repo_root))
    schema_dir = root / "schema"
    prompt_dir = root / "prompts"
    errors: list[str] = []
    schema_contracts: dict[str, tuple[str, dict[str, Any], list[str], dict[str, Any]]] = {}

    schema_files = sorted(glob.glob(str(schema_dir / "*.schema.json")))
    for schema_file in schema_files:
        step = Path(schema_file).name.split("_", 1)[0]
        if step == "seed":
            continue
        try:
            schema_required, schema_props, schema = _load_contract(schema_file)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(f"E520 UNRESOLVED_INPUT invalid_schema {schema_file} {exc}")
            continue
        schema_contracts[step] = (schema_file, schema, schema_required, schema_props)
        prompt_candidates = _prompt_candidates(prompt_dir, step)
        if not prompt_candidates:
            continue
        for prompt_path in prompt_candidates:
            prompt_required, prompt_props, prompt_schema, line_no = _extract_prompt_contract(prompt_path)
            if prompt_required is None:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing JSON contract block")
                continue
            missing = sorted(set(schema_required) - set(prompt_required))
            extra = sorted(set(prompt_required) - set(schema_required))
            if missing:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing required {missing}")
            if extra:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} extra required {extra}")
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


def _drift_sensitive_property_errors(
    prompt_path: str,
    line_no: int,
    schema_props: dict[str, object],
    prompt_props: dict[str, object],
) -> list[str]:
    fields = DRIFT_SENSITIVE_FIELDS
    errors: list[str] = []
    for field in fields:
        schema_prop = schema_props.get(field)
        prompt_prop = prompt_props.get(field)
        if schema_prop is None:
            continue
        if prompt_prop is None:
            errors.append(
                f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing property field='{field}'"
            )
            continue
        if not (isinstance(schema_prop, dict) and isinstance(prompt_prop, dict)):
            continue
        if _canonical_json(schema_prop) != _canonical_json(prompt_prop):
            errors.append(
                f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} property_drift field='{field}'"
            )
    return errors


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _required_canonical_ref_errors(
    prompt_path: str,
    line_no: int,
    schema: dict[str, Any],
    prompt_schema: dict[str, Any],
) -> list[str]:
    expected = _collect_required_canonical_ref_paths(schema)
    if not expected:
        return []
    actual = _collect_required_canonical_ref_paths(prompt_schema)
    missing = sorted(expected - actual)
    if not missing:
        return []
    return [
        f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
        f"missing_required_canonical_refs {missing}"
    ]


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
) -> list[str]:
    errors: list[str] = []
    registry, registry_error = _schema_registry(repo_root)
    if registry_error:
        errors.append(
            f"E520 UNRESOLVED_INPUT {repo_root / 'tools' / 'schema_registry.json'} "
            f"schema_registry_bootstrap_failed {registry_error}"
        )
    for prompt_path in sorted(glob.glob(str(prompt_dir / "prompt_*.md"))):
        step = _step_from_prompt_name(Path(prompt_path).name)
        if not step:
            continue
        contract = schema_contracts.get(step)
        if not contract:
            continue
        _, schema, _, _ = contract
        output_payload, line_no, parse_error = _extract_output_contract(prompt_path)
        if parse_error:
            errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} {parse_error}")
            continue
        if not isinstance(output_payload, dict):
            errors.append(
                f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} output_contract_must_be_json_object"
            )
            continue
        schema_uri_error = _validate_output_schema_uri(output_payload, schema)
        if schema_uri_error:
            errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} {schema_uri_error}")
            continue
        payload = dict(output_payload)
        payload.pop("$schema", None)
        errors.extend(_validate_output_payload(prompt_path, line_no, payload, schema, registry))
    return errors


def _step_from_prompt_name(name: str) -> str | None:
    match = re.match(r"prompt_(\d{2}[a-z]?)_", name)
    if not match:
        return None
    step = match.group(1)
    if step in {"16a", "16b", "16c"}:
        return "16"
    return step


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
    store = {uri: Resource.from_contents(schema) for uri, schema in schema_registry.store.items()}
    return Registry().with_resources(store.items()), None


def _validate_output_payload(
    prompt_path: str,
    line_no: int,
    payload: dict[str, Any],
    schema: dict[str, Any],
    registry: Registry | None,
) -> list[str]:
    try:
        if registry is None:
            validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        else:
            validator = Draft202012Validator(
                schema,
                registry=registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
        validation_errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    except _WrappedReferencingError as exc:
        return [
            f"E520 UNRESOLVED_INPUT {prompt_path}:{line_no} "
            f"output_contract_schema_resolution_failed {exc}"
        ]
    except Exception as exc:
        return [
            f"E521 VALIDATOR_RUNTIME {prompt_path}:{line_no} "
            f"output_contract_schema_validation_runtime_error {type(exc).__name__}: {exc}"
        ]
    errors: list[str] = []
    for err in validation_errors[:5]:
        path = f"/{'/'.join(map(str, err.path))}" if err.path else "$"
        errors.append(
            f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} "
            f"output_contract_schema_error path='{path}' {err.message}"
        )
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    args = p.parse_args()
    errs = run_prompt_schema_sync(args.repo_root)
    if errs:
        for err in errs:
            print(err)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
