#!/usr/bin/env python3
"""
json_utils.py - Advanced JSON manipulation and discovery tool for AI Agents.

Capabilities:
- CRUD: read, read-multi, patch, insert, delete (using jq)
- Discovery: keys, structure (skeleton)
- Schema: Schema-aware property discovery with $ref resolution and allOf merging

All public functions raise JsonUtilsError on failure (not sys.exit), and return
data instead of printing, making them safe to import as a library (e.g. from a
future extractor.py). The CLI entry point (main) handles printing to stdout.
"""

import argparse
import glob as glob_mod
import json
import os
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

# --- Configuration ---
JQ_INDENT = 4  # Enforce 4-space indent to match repo style


# --- Exceptions ---

class JsonUtilsError(Exception):
    """LLM-friendly error for all json_utils operations.

    Raised instead of sys.exit(1) so callers importing json_utils as a
    library get catchable exceptions. The CLI main() converts these to
    stderr output + exit code 1.
    """
    pass


# --- Helpers ---

def _check_file(file_path: str) -> None:
    """Verify file exists before operating on it."""
    if not os.path.isfile(file_path):
        raise JsonUtilsError(
            f"File not found: {file_path}. "
            "Check the path — spec files live in spec/, test fixtures in tests/fixtures/."
        )


def validate_jq_filter(jq_filter: str) -> Optional[str]:
    """Dry-run a jq filter against null input to catch syntax errors early.

    Returns None on success, or an LLM-actionable error string on failure.
    """
    if not jq_filter or not jq_filter.strip():
        return "Filter is empty. Provide a valid jq expression (e.g. .title, .items[0].name)."

    try:
        result = subprocess.run(
            ['jq', '-n', '--argjson', '_x', 'null', jq_filter],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 and result.stderr:
            stderr = result.stderr.strip()
            hint = ""
            if "unexpected BINDING" in stderr or "try .\\[" in stderr:
                hint = " Hint: use .[\"$field\"] for fields starting with $."
            elif "unexpected $end" in stderr:
                hint = " Hint: filter has unbalanced brackets or quotes."
            elif "is not defined" in stderr:
                hint = " Hint: check for typos in function names."
            return f"jq syntax error in filter '{jq_filter}': {stderr}{hint}"
    except subprocess.TimeoutExpired:
        return f"jq filter '{jq_filter}' timed out during syntax check."
    except FileNotFoundError:
        return "jq is not installed or not on PATH."

    return None


def _require_valid_filter(jq_filter: str) -> None:
    """Validate a jq filter, raising JsonUtilsError on failure."""
    err = validate_jq_filter(jq_filter)
    if err:
        raise JsonUtilsError(err)


def run_jq(args: List[str], input_data: Optional[str] = None, file_path: Optional[str] = None, timeout: int = 30) -> str:
    """Run jq command and return output. Raises JsonUtilsError on failure."""
    cmd = ['jq'] + args
    if file_path:
        cmd.append(file_path)

    try:
        if input_data is not None:
            result = subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=True, timeout=timeout)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        return result.stdout.strip()
    except FileNotFoundError:
        raise JsonUtilsError("jq is not installed or not on PATH. Install with: brew install jq")
    except subprocess.TimeoutExpired:
        raise JsonUtilsError(
            f"jq timed out after {timeout}s. Simplify the filter or target a narrower path."
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        hint = ""
        if "unexpected BINDING" in stderr or "try .\\[" in stderr:
            hint = " Hint: use .[\"$field\"] for fields starting with $."
        elif "unexpected $end" in stderr:
            hint = " Hint: unbalanced brackets or quotes in filter."
        elif "Cannot index" in stderr:
            hint = " Hint: the path targets a scalar, not an object/array. Check parent path."
        elif "null" in stderr and "iterate" in stderr:
            hint = " Hint: an intermediate path is null. Verify the path exists with 'keys' first."
        elif "Could not open file" in stderr:
            hint = " Hint: check that the file path is correct and the file exists."

        raise JsonUtilsError(f"jq failed — {stderr}{hint}")


# --- Schema Resolution ---

def build_id_index(schema_dir: str) -> Dict[str, str]:
    """Scan schema dir once, build {$id: file_path} mapping from all *.schema.json files.

    Also scans a sibling canon/ directory if it exists, so that canon schema
    $id values (vc:canon:kind, vc:canon:aliases) are indexed for $ref resolution.
    """
    index = {}
    # Primary: schema/**/*.schema.json
    for path in glob_mod.glob(os.path.join(schema_dir, '**/*.schema.json'), recursive=True):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if '$id' in data:
                    index[data['$id']] = path
        except (json.JSONDecodeError, OSError):
            continue

    # Also scan sibling canon/ directory for canon schemas
    canon_dir = os.path.normpath(os.path.join(schema_dir, '..', 'canon'))
    if os.path.isdir(canon_dir):
        for path in glob_mod.glob(os.path.join(canon_dir, '**/*.schema.json'), recursive=True):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    if '$id' in data:
                        index[data['$id']] = path
            except (json.JSONDecodeError, OSError):
                continue

    return index


def resolve_ref(ref: str, id_index: Dict[str, str], cache: Dict[str, dict]) -> Optional[dict]:
    """Resolve a vc: URN $ref to its schema definition.

    Returns the resolved schema fragment, or None if unresolvable.
    Local refs (#/$defs/...) return None — caller handles those.
    """
    if ref.startswith('#/'):
        return None  # local ref — handled by caller

    base, _, fragment = ref.partition('#')
    file_path = id_index.get(base)
    if not file_path:
        return None

    if file_path not in cache:
        try:
            with open(file_path, 'r') as f:
                cache[file_path] = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    schema = cache[file_path]
    if not fragment:
        return schema  # whole-schema ref

    # Resolve by $anchor match in $defs
    for _def_name, def_schema in schema.get('$defs', {}).items():
        if isinstance(def_schema, dict) and def_schema.get('$anchor') == fragment:
            return def_schema
    return None


def _find_schema_dir(repo_root: Optional[str] = None) -> Optional[str]:
    """Locate the schema/ directory.

    Search order:
    1. repo_root/schema (explicit --repo-root from CLI)
    2. Relative to this file (tools/core/ -> ../../schema)
    3. cwd/schema (toolkit IS the repo)
    4. cwd/devspec_toolkit/schema (toolkit is a submodule)
    """
    candidates = []
    if repo_root:
        candidates.append(os.path.join(repo_root, 'schema'))

    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(this_dir, '..', '..', 'schema')))

    cwd = os.getcwd()
    candidates.append(os.path.join(cwd, 'schema'))
    candidates.append(os.path.join(cwd, 'devspec_toolkit', 'schema'))

    for candidate in candidates:
        normed = os.path.normpath(candidate)
        if os.path.isdir(normed):
            return normed
    return None


def resolve_schema_path(
    file_path: str,
    repo_root: Optional[str] = None,
    id_index: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Resolve the local schema file path from the target JSON's $schema field.

    Uses $id-index resolution. If id_index is pre-built, reuses it (avoids
    double scan when called from json_schema_discovery).
    """
    # 1. Read $schema URI from the target file
    try:
        schema_url = run_jq(['-r', '.["$schema"]'], file_path=file_path)
        if not schema_url or schema_url == 'null':
            return None
    except JsonUtilsError:
        return None

    # 2. Build or reuse $id index
    if id_index is None:
        schema_dir = _find_schema_dir(repo_root)
        if schema_dir:
            id_index = build_id_index(schema_dir)

    if id_index:
        resolved = id_index.get(schema_url)
        if resolved and os.path.exists(resolved):
            return resolved

    return None


# --- Core Operations ---

def json_read(file_path: str, jq_filter: str) -> Optional[str]:
    """Read data using a jq filter. Returns the result string, or None if empty."""
    if jq_filter == ".":
        raise JsonUtilsError(
            "Full JSON reads are not allowed. Specify a targeted path (e.g. .title, .items[0])."
        )

    _check_file(file_path)
    _require_valid_filter(jq_filter)

    result = run_jq(['-r', jq_filter], file_path=file_path, timeout=10)
    if result == 'null':
        return "null"
    return result


def json_read_multi(file_path: str, filters: List[str]) -> Optional[str]:
    """Read multiple jq filters in a single pass, returning keyed-by-filter JSON.

    Returns the JSON string result. Errors cascade immediately — if any filter
    fails, the entire call errors rather than falling back to per-filter execution.
    """
    if not filters:
        raise JsonUtilsError("No filters provided.")

    _check_file(file_path)

    for f in filters:
        if f.strip() == ".":
            raise JsonUtilsError("Full JSON reads are not allowed. Specify targeted paths.")
        _require_valid_filter(f)

    # Keys use json.dumps to safely encode filter strings (handles $, quotes, etc.)
    kv_entries = []
    for f in filters:
        safe_key = json.dumps(f)  # produces "...", already quoted
        kv_entries.append(f'({safe_key}): ({f})')
    kv_pairs = ",\n  ".join(kv_entries)
    filter_expr = "{\n  " + kv_pairs + "\n}"

    result = run_jq(["--indent", str(JQ_INDENT), filter_expr], file_path=file_path, timeout=15)
    return result


def json_keys(file_path: str, path_selector: str) -> Optional[str]:
    """List keys at the given path. Returns JSON array string."""
    _check_file(file_path)
    _require_valid_filter(path_selector)

    filter_expr = f'({path_selector}) | keys'
    result = run_jq([filter_expr], file_path=file_path, timeout=10)
    if result and result != 'null':
        return result
    return None


def json_write_atomic(file_path: str, data_str: str) -> None:
    """Write string data to file atomically, enforcing format."""
    if not data_str or not data_str.strip():
        raise JsonUtilsError(
            f"Refusing to write empty content to {file_path}. "
            "This usually indicates an upstream jq error — check the filter and input."
        )

    formatted = run_jq(['--indent', str(JQ_INDENT), '.'], input_data=data_str, timeout=10)

    if not formatted or not formatted.strip():
        raise JsonUtilsError(
            f"jq formatting produced empty output for {file_path}. Input may be invalid JSON."
        )

    dirname = os.path.dirname(file_path) or '.'
    # Preserve original file permissions (temp files default to 0o600)
    try:
        original_mode = os.stat(file_path).st_mode
    except OSError:
        original_mode = None

    with tempfile.NamedTemporaryFile('w', dir=dirname, delete=False) as tf:
        tf.write(formatted + '\n')
        temp_name = tf.name

    os.replace(temp_name, file_path)
    if original_mode is not None:
        os.chmod(file_path, original_mode)


def json_patch(file_path: str, path_selector: str, value: str, is_json: bool = True) -> str:
    """Update a value at the path. Returns confirmation message."""
    _check_file(file_path)
    _require_valid_filter(path_selector)

    args = ['--indent', str(JQ_INDENT)]
    if is_json:
        args.extend(['--argjson', 'v', value])
    else:
        args.extend(['--arg', 'v', value])

    filter_expr = f'({path_selector}) = $v'
    args.append(filter_expr)

    with open(file_path, 'r') as f:
        content = f.read()

    new_content = run_jq(args, input_data=content, timeout=10)
    json_write_atomic(file_path, new_content)
    return f"Updated {path_selector} in {file_path}"


def json_insert(file_path: str, path_selector: str, value: str, is_json: bool = True) -> str:
    """Append to array or merge object. Returns confirmation message."""
    _check_file(file_path)
    _require_valid_filter(path_selector)

    args = ['--indent', str(JQ_INDENT)]
    if is_json:
        args.extend(['--argjson', 'v', value])
    else:
        args.extend(['--arg', 'v', value])

    filter_expr = f'({path_selector}) |= (if type=="array" then . + [$v] elif type=="object" then . + $v else error("Cannot insert into " + type) end)'
    args.append(filter_expr)

    with open(file_path, 'r') as f:
        content = f.read()

    new_content = run_jq(args, input_data=content, timeout=10)
    json_write_atomic(file_path, new_content)
    return f"Inserted into {path_selector} in {file_path}"


def json_delete(file_path: str, path_selector: str) -> str:
    """Delete item at path. Returns confirmation message."""
    _check_file(file_path)
    _require_valid_filter(path_selector)

    args = ['--indent', str(JQ_INDENT)]
    filter_expr = f'del({path_selector})'
    args.append(filter_expr)

    with open(file_path, 'r') as f:
        content = f.read()

    new_content = run_jq(args, input_data=content, timeout=10)
    json_write_atomic(file_path, new_content)
    return f"Deleted {path_selector} in {file_path}"


def json_structure(file_path: str, path_selector: str = ".") -> Optional[str]:
    """Return a visual hierarchical structure of the JSON as a string."""
    _check_file(file_path)

    if path_selector != ".":
        _require_valid_filter(path_selector)

    result = run_jq(['-c', f'({path_selector})'], file_path=file_path, timeout=30)

    if result == 'null':
        return "null"

    parsed_data = json.loads(result)
    lines: List[str] = []

    def _collect(data, prefix=""):
        if isinstance(data, dict):
            items = list(data.items())
            for i, (key, value) in enumerate(items):
                last = (i == len(items) - 1)
                connector = "└── " if last else "├── "
                lines.append(f"{prefix}{connector}{key}: {type(value).__name__}")

                if isinstance(value, (dict, list)):
                    extension = "    " if last else "│   "
                    _collect(value, prefix + extension)

        elif isinstance(data, list):
            lines.append(f"{prefix}└── array[{len(data)} items]")
            if len(data) > 0:
                first_elem = data[0]
                lines.append(f"{prefix}    ├── [0]: {type(first_elem).__name__}")
                if isinstance(first_elem, (dict, list)):
                    _collect(first_elem, prefix + "    ")

    # Build the visual tree representation
    if isinstance(parsed_data, dict):
        items = list(parsed_data.items())
        for i, (key, value) in enumerate(items):
            last = (i == len(items) - 1)
            connector = "└── " if last else "├── "
            lines.append(f"{connector}{key}: {type(value).__name__}")

            if isinstance(value, (dict, list)):
                extension = "    " if last else "│   "
                _collect(value, extension)
    elif isinstance(parsed_data, list):
        lines.append(f"array[{len(parsed_data)} items]")
        if len(parsed_data) > 0:
            first_elem = parsed_data[0]
            lines.append(f"├── [0]: {type(first_elem).__name__}")
            if isinstance(first_elem, (dict, list)):
                _collect(first_elem, "    ")
    else:
        lines.append(f"{type(parsed_data).__name__}")

    return "\n".join(lines) if lines else None


# --- Schema Discovery ---

def _effective_schema(node: dict, resolve_fn) -> dict:
    """Resolve $ref and merge allOf to produce a navigable schema node.

    Handles the two composition patterns in this codebase:
    - $ref: resolved via resolve_fn (local #/$defs/... or URN vc:...)
    - allOf: branches resolved and merged (properties unioned, required concatenated)

    Does NOT handle oneOf, anyOf, or if/then/else. In this codebase those are
    used only for type unions (number|string) and conditional required fields —
    neither adds navigable properties, so discovery results remain correct.
    """
    if not isinstance(node, dict):
        return node

    # Resolve $ref first
    if '$ref' in node:
        node = resolve_fn(node)
        if not isinstance(node, dict):
            return node

    # Merge allOf branches
    if 'allOf' in node:
        merged_props = {}
        merged_required = []
        merged_defs = {}
        base = {k: v for k, v in node.items() if k != 'allOf'}

        for branch in node['allOf']:
            branch = _effective_schema(branch, resolve_fn)
            if 'properties' in branch:
                merged_props.update(branch['properties'])
            if 'required' in branch:
                merged_required.extend(branch['required'])
            if '$defs' in branch:
                merged_defs.update(branch['$defs'])
            # Copy other schema keywords (first-wins for non-mergeable keys)
            for key in ('type', 'description', 'items', 'additionalProperties'):
                if key in branch and key not in base:
                    base[key] = branch[key]

        if merged_props:
            base['properties'] = merged_props
        if merged_required:
            base['required'] = merged_required
        if merged_defs:
            base.setdefault('$defs', {}).update(merged_defs)
        return base

    return node


def json_schema_discovery(file_path: str, path_selector: str, repo_root: Optional[str] = None) -> Optional[str]:
    """Discover allowable fields from the schema, resolving $ref URNs and allOf inline.

    Returns JSON string of discovered schema info.
    """
    _check_file(file_path)

    # Build index once — shared between resolve_schema_path and ref resolution
    schema_dir = _find_schema_dir(repo_root)
    id_index = build_id_index(schema_dir) if schema_dir else {}
    ref_cache: Dict[str, dict] = {}

    schema_path = resolve_schema_path(file_path, repo_root=repo_root, id_index=id_index)
    if not schema_path:
        raise JsonUtilsError(
            f"Could not resolve schema for {file_path}. "
            "Make sure it has a $schema field and the schema directory is accessible."
        )

    with open(schema_path, 'r') as f:
        schema = json.load(f)

    def _resolve_node(node: dict) -> dict:
        """Resolve a single $ref node."""
        if not isinstance(node, dict) or '$ref' not in node:
            return node
        ref = node['$ref']
        # Local ref: look up in current schema's $defs
        if ref.startswith('#/$defs/'):
            def_name = ref.split('/')[-1]
            resolved = schema.get('$defs', {}).get(def_name)
            return resolved if resolved else node
        # URN ref: resolve via $id index
        resolved = resolve_ref(ref, id_index, ref_cache)
        return resolved if resolved else node

    # Get the effective root schema (resolves allOf at root level)
    effective_root = _effective_schema(schema, _resolve_node)

    # Handle root-level query
    clean_path = path_selector.lstrip('.').replace('[]', '')
    if not clean_path:
        props = effective_root.get('properties', {})
        resolved_props = {k: _effective_schema(v, _resolve_node) for k, v in props.items()}
        return json.dumps({k: _summarise_prop(v) for k, v in resolved_props.items()}, indent=2)

    # Walk the schema path
    current = effective_root
    parts = clean_path.replace('[', '.').replace(']', '').split('.')
    parts = [p for p in parts if p]

    path_found = True
    for part in parts:
        current = _effective_schema(current, _resolve_node)

        if 'properties' in current and part in current['properties']:
            current = current['properties'][part]
        elif 'items' in current and isinstance(current['items'], dict):
            items = _effective_schema(current['items'], _resolve_node)
            if 'properties' in items and part in items['properties']:
                current = items['properties'][part]
            else:
                current = items
        else:
            path_found = False
            break

    current = _effective_schema(current, _resolve_node)

    if not path_found:
        return json.dumps({
            "error": f"Could not navigate to path '{path_selector}' in schema",
            "schema_info": {
                "type": current.get("type", "unknown"),
                "description": current.get("description", "No description available")
            }
        }, indent=2)

    info = {
        "type": current.get("type"),
        "description": current.get("description"),
        "allowed_properties": list(current.get("properties", {}).keys()) if current.get("type") == "object" or current.get("properties") else None,
        "items": current.get("items", {}).get("type") if current.get("type") == "array" else None,
        "required": current.get("required"),
        "enum": current.get("enum")
    }
    return json.dumps(info, indent=2)


def _summarise_prop(prop: dict) -> dict:
    """Create a compact summary of a schema property for root-level discovery."""
    if not isinstance(prop, dict):
        return prop
    summary = {}
    if 'type' in prop:
        summary['type'] = prop['type']
    if 'description' in prop:
        # Truncate long descriptions for overview
        desc = prop['description']
        summary['description'] = desc[:120] + '...' if len(desc) > 120 else desc
    if 'enum' in prop:
        summary['enum'] = prop['enum']
    return summary


# --- CLI Setup ---

def main():
    parser = argparse.ArgumentParser(description="Smart JSON Tool for AI Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    p_read = subparsers.add_parser("read", help="Read data (use targeted paths, not '.' for full JSON)")
    p_read.add_argument("file", help="JSON file path")
    p_read.add_argument("filter", help="jq filter (e.g. .items[0].name, .version)")

    # Read-multi
    p_readm = subparsers.add_parser("read-multi", help="Read multiple paths in one pass (keyed output)")
    p_readm.add_argument("file", help="JSON file path")
    p_readm.add_argument("filters", nargs="+", help="jq filters (e.g. .version .name)")

    # Patch
    p_patch = subparsers.add_parser("patch", help="Update value")
    p_patch.add_argument("file", help="JSON file path")
    p_patch.add_argument("path", help="jq path to target (e.g. .version)")
    p_patch.add_argument("value", help="New value (JSON string or raw string)")
    p_patch.add_argument("--raw", action="store_true", help="Treat value as string, not JSON")

    # Insert
    p_insert = subparsers.add_parser("insert", help="Insert/Append value")
    p_insert.add_argument("file", help="JSON file path")
    p_insert.add_argument("path", help="jq path to target array/object")
    p_insert.add_argument("value", help="Value to insert")
    p_insert.add_argument("--raw", action="store_true", help="Treat value as string, not JSON")

    # Delete
    p_del = subparsers.add_parser("delete", help="Delete value")
    p_del.add_argument("file", help="JSON file path")
    p_del.add_argument("path", help="jq path to target")

    # Keys
    p_keys = subparsers.add_parser("keys", help="List keys")
    p_keys.add_argument("file", help="JSON file path")
    p_keys.add_argument("path", help="jq path (optional)", default=".", nargs="?")

    # Structure
    p_struct = subparsers.add_parser("structure", help="Show visual hierarchical structure")
    p_struct.add_argument("file", help="JSON file path")
    p_struct.add_argument("path", help="jq path (optional)", default=".", nargs="?")

    # Schema
    p_schema = subparsers.add_parser("schema", help="Query schema capabilities")
    p_schema.add_argument("file", help="Source data file (to find $schema)")
    p_schema.add_argument("path", help="Path looking for (e.g. .capabilities)")
    p_schema.add_argument("--repo-root", help="Toolkit root dir (for submodule deployments)")

    args = parser.parse_args()

    try:
        result = None
        if args.command == "read":
            result = json_read(args.file, args.filter)
        elif args.command == "read-multi":
            result = json_read_multi(args.file, args.filters)
        elif args.command == "patch":
            result = json_patch(args.file, args.path, args.value, not args.raw)
        elif args.command == "insert":
            result = json_insert(args.file, args.path, args.value, not args.raw)
        elif args.command == "delete":
            result = json_delete(args.file, args.path)
        elif args.command == "keys":
            result = json_keys(args.file, args.path)
        elif args.command == "structure":
            result = json_structure(args.file, args.path)
        elif args.command == "schema":
            result = json_schema_discovery(args.file, args.path, repo_root=args.repo_root)

        if result is not None:
            print(result)
    except JsonUtilsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
