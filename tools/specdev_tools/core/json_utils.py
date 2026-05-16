#!/usr/bin/env python3
"""
json_utils.py - Advanced JSON manipulation and discovery tool for AI Agents.

Capabilities:
- CRUD: read, read-multi, patch, insert, delete (using jq)
- Discovery: keys, structure (skeleton)
- Schema: Schema-aware property discovery with $ref resolution and allOf merging
- Pointer verification: resolve-pointers (pointer contract per llm_protocol.md §4/§7.3)

All public functions raise JsonUtilsError on failure (not sys.exit), and return
data instead of printing, making them safe to import as a library (e.g. from a
future extractor.py). The CLI entry point (main) handles printing to stdout.
"""

import argparse
import glob as glob_mod
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

# Entry-key registry — deterministic id-field lookup per spec file.
from specdev_tools.core import entry_key_registry as _ekreg

# Detects bare array iterators (e.g. .arr[], to_entries[]) that produce value streams.
# Used to guard read-multi, whose {key: value} construct produces one output object per
# stream element — breaking the single-keyed-object output contract.
_STREAMING_FILTER_RE = re.compile(r'\[\s*\]')

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
    """Syntax-check a jq filter without executing it against real data.

    Wraps the filter in ``try (...) catch null`` so runtime-only errors
    (null iteration, missing keys) do not block valid filters — only jq
    parse errors cause a failure return.

    Returns None on success, or an LLM-actionable error string on failure.
    """
    if not jq_filter or not jq_filter.strip():
        return "Filter is empty. Provide a valid jq expression (e.g. .title, .items[0].name)."

    try:
        # Wrap in try/catch so runtime-only errors (null iteration, missing keys)
        # don't block valid filters — we only want to catch syntax errors here.
        result = subprocess.run(
            ['jq', '-n', f'try ({jq_filter}) catch null'],
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
    for _, def_schema in schema.get('$defs', {}).items():
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
    candidates.append(os.path.normpath(os.path.join(this_dir, '..', '..', '..', 'schema')))

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
        if _STREAMING_FILTER_RE.search(f):
            raise JsonUtilsError(
                f"Filter '{f}' produces a stream of values — not allowed in read-multi. "
                "read-multi requires each filter to return a single value. "
                "Use 'json read' for streaming filters (e.g. '.terms[] | select(...)')."
            )

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


# --- Pointer Resolution (llm_protocol.md §4 / §7.3) ---

# Forbidden path prefixes/patterns per §4.3.
_FORBIDDEN_PREFIXES = (".specdev/",)
_FORBIDDEN_EXTENSIONS = (".txt",)

# Absolute path prefixes that indicate temp/scratch paths (§4.3).
# Includes standard POSIX paths plus /private/tmp (macOS symlink resolution of /tmp).
_FORBIDDEN_ABS_PREFIXES = (
    "/tmp/",
    "/var/tmp/",
    "/private/tmp/",
    "/var/folders/",  # macOS temp dir used by TMPDIR
)


def _is_forbidden_path(file_path: str) -> Optional[str]:
    """Return a reason string if file_path is forbidden per §4.3, else None.

    Forbidden shapes (§4.3):
    - Paths under .specdev/
    - *.txt dumps or temp paths
    - Absolute paths under /tmp/, /var/tmp/, /private/tmp/, /var/folders/,
      or TMPDIR (C1)
    - Anything that resolves to a directory rather than a file
      (checked at call time, not here — here we only check the path string)
    """
    # C1: Reject absolute paths under known temp directories before other checks.
    if os.path.isabs(file_path):
        norm = os.path.normpath(file_path)
        for prefix in _FORBIDDEN_ABS_PREFIXES:
            prefix_norm = os.path.normpath(prefix)
            if norm == prefix_norm or norm.startswith(prefix_norm + os.sep):
                return f"path is under forbidden temp prefix '{prefix}'"
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            tmpdir_norm = os.path.normpath(tmpdir)
            if norm == tmpdir_norm or norm.startswith(tmpdir_norm + os.sep):
                return f"path is under forbidden temp prefix (TMPDIR='{tmpdir}')"

    # Normalise away leading ./ for prefix matching
    normalised = file_path.lstrip("./").replace("\\", "/")
    for prefix in _FORBIDDEN_PREFIXES:
        if normalised.startswith(prefix.lstrip("./")):
            return f"path is under forbidden prefix '{prefix}'"
    _, ext = os.path.splitext(file_path)
    if ext.lower() in _FORBIDDEN_EXTENSIONS:
        return f"path has forbidden extension '{ext}'"
    return None


def _is_valid_pointer_shape(pointer: Any) -> Tuple[bool, str]:
    """Validate pointer shape per §4.1/§4.3.

    Returns (valid, reason).  On success reason is "".

    Valid shapes:
      { "file": str, "id": str }
      { "file": str, "jq_path": str }

    Forbidden (§4.3):
      - Bare strings
      - file without id or jq_path
      - Both id and jq_path absent
    """
    if not isinstance(pointer, dict):
        return False, "invalid_shape: pointer must be a JSON object"

    file_val = pointer.get("file")
    if not file_val or not isinstance(file_val, str):
        return False, "invalid_shape: 'file' field is missing or not a string"

    has_id = isinstance(pointer.get("id"), str) and pointer.get("id")
    has_jq = isinstance(pointer.get("jq_path"), str) and pointer.get("jq_path")

    if not has_id and not has_jq:
        return False, "invalid_shape: pointer must contain 'id' or 'jq_path'"

    # Check forbidden path shapes
    reason = _is_forbidden_path(file_val)
    if reason:
        return False, f"invalid_shape: {reason}"

    return True, ""


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(b)]


def _kebab_tokens(s: str) -> List[str]:
    """Split a kebab-case string into lowercase tokens."""
    return [t for t in s.replace("_", "-").split("-") if t]


def _nearest_ids(target: str, candidates: List[str], top_n: int = 3) -> List[Dict[str, Any]]:
    """Return top_n nearest ids by normalised token-level Levenshtein (§15).

    Scoring: 1 - (edit_distance / max_len) so higher = more similar.
    max_len is the max of the two token-joined strings' lengths (floor 1).
    """
    target_joined = " ".join(_kebab_tokens(target))
    scored = []
    for cand in candidates:
        cand_joined = " ".join(_kebab_tokens(cand))
        dist = _levenshtein(target_joined, cand_joined)
        max_len = max(len(target_joined), len(cand_joined), 1)
        score = round(1.0 - dist / max_len, 2)
        scored.append((score, cand))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [{"id": cand, "score": sc} for sc, cand in scored[:top_n]]


# ---------------------------------------------------------------------------
# All entry-id lookups now go through entry_key_registry exclusively.
# Callers must pass spec_root (required) so the registry can be loaded.
# Files not registered in the registry return empty results — no broad scan.
# ---------------------------------------------------------------------------


def _collect_ids_from_file(
    data: Any,
    spec_file: str,
    spec_root: str,
) -> Tuple[List[str], Dict[str, Tuple[str, str, Any]]]:
    """Walk a parsed JSON object and collect all entry ids.

    For each spec file, the entry-key registry (``<spec_root>/entry_key_registry.json``)
    is the sole source of truth for which arrays to scan and which id field to use.
    Files not registered in the registry return empty results — no broad scan.
    Nested arrays (e.g. ``milestones[].tasks``) are walked using the ``nested``
    declarations in the registry.

    Args:
        data: parsed JSON object to index.
        spec_file: basename or relative path of the spec file (required).
        spec_root: filesystem path to the project's spec directory (required).
            The registry is loaded from ``<spec_root>/entry_key_registry.json``.
            ``FileNotFoundError`` is raised (and propagates) if the registry is absent.

    Returns:
      - ``all_ids``: flat list of every discovered id (for nearest-search).
      - ``id_map``: {id_value -> (kind, jq_path, entry_object)}
        where kind is the singular kind label (e.g. "functional_requirement"),
        jq_path is the resolved path (e.g. ".functional_requirements[2]"),
        and entry_object is the raw dict.
    """
    all_ids: List[str] = []
    id_map: Dict[str, Tuple[str, str, Any]] = {}

    if not isinstance(data, dict):
        return all_ids, id_map

    # Registry is the only lookup path. FileNotFoundError propagates (misconfiguration).
    reg_entries = _ekreg.list_entries(spec_file, spec_root)

    # reg_entries is None  → unknown file — skip (no broad scan)
    # reg_entries is []    → known file with no entry arrays (no-op)
    # reg_entries is [...] → known file with registered arrays (may include nested)
    if reg_entries is None:
        return all_ids, id_map

    # --- Registry path (known spec file) ---
    # Split registry entries into top-level and nested.
    # Nested entries have paths like ".milestones[].tasks".
    top_level_lookup: Dict[str, Tuple[str, str]] = {}
    # nested_lookup: parent_key → list of (sub_array_key, id_field, kind)
    nested_lookup: Dict[str, List[Tuple[str, str, str]]] = {}

    for entry in reg_entries:
        path = entry.array_path  # e.g. ".milestones" or ".milestones[].tasks"
        if "[]." in path:
            # Nested: ".parent[].child" → parent="parent", child="child"
            parent_part, _, child_part = path.partition("[].")
            parent_key = parent_part.lstrip(".")
            nested_lookup.setdefault(parent_key, []).append(
                (child_part, entry.id_field, entry.kind)
            )
        else:
            arr_key = path.lstrip(".")
            top_level_lookup[arr_key] = (entry.id_field, entry.kind)

    for top_key, top_val in data.items():
        if not isinstance(top_val, list):
            continue
        # Skip corpus-excluded keys.
        if _ekreg.is_corpus_excluded(top_key, spec_root):
            continue
        if top_key not in top_level_lookup and top_key not in nested_lookup:
            # Array not registered for this file — skip deliberately.
            continue

        if top_key in top_level_lookup:
            id_field, kind = top_level_lookup[top_key]
            for idx, item in enumerate(top_val):
                if not isinstance(item, dict):
                    continue
                # Use the registered id field exclusively (deterministic).
                found_id = item.get(id_field)
                if not isinstance(found_id, str) or not found_id:
                    continue
                jq_path = f".{top_key}[{idx}]"
                all_ids.append(found_id)
                # On id collision, keep first occurrence (deterministic).
                if found_id not in id_map:
                    id_map[found_id] = (kind, jq_path, item)

        # Walk nested sub-arrays for entries registered under this parent.
        if top_key in nested_lookup:
            for parent_idx, parent_item in enumerate(top_val):
                if not isinstance(parent_item, dict):
                    continue
                for sub_key, id_field, kind in nested_lookup[top_key]:
                    sub_val = parent_item.get(sub_key)
                    if not isinstance(sub_val, list):
                        continue
                    for sub_idx, sub_item in enumerate(sub_val):
                        if not isinstance(sub_item, dict):
                            continue
                        found_id = sub_item.get(id_field)
                        if not isinstance(found_id, str) or not found_id:
                            continue
                        jq_path = f".{top_key}[{parent_idx}].{sub_key}[{sub_idx}]"
                        all_ids.append(found_id)
                        if found_id not in id_map:
                            id_map[found_id] = (kind, jq_path, sub_item)

    return all_ids, id_map


def _resolve_single_pointer(
    pointer: Dict[str, Any],
    *,
    spec_root: str,
    git_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve one pointer to a result record per §7.3 report shape.

    spec_root (keyword-only, required) is the host-repo spec directory; the
    entry-key registry is loaded from ``<spec_root>/entry_key_registry.json``.
    git_root (keyword-only) anchors relative ``file`` paths; defaults to cwd.
    Always returns a dict; never raises.
    """
    base_dir = os.path.abspath(git_root) if git_root else os.getcwd()

    valid, shape_reason = _is_valid_pointer_shape(pointer)
    if not valid:
        return {
            "pointer": pointer,
            "exists": False,
            "reason": shape_reason,
        }

    file_val: str = pointer["file"]
    id_val: Optional[str] = pointer.get("id")
    jq_path_val: Optional[str] = pointer.get("jq_path")

    # Resolve file path against git_root
    if not os.path.isabs(file_val):
        abs_file = os.path.join(base_dir, file_val)
    else:
        abs_file = file_val

    # B1: Containment check — reject paths that escape git_root via traversal.
    # Applied after forbidden-shape checks (stronger rejection takes priority).
    abs_file = os.path.normpath(abs_file)
    base_dir_norm = os.path.normpath(base_dir)
    if abs_file != base_dir_norm and not abs_file.startswith(base_dir_norm + os.sep):
        return {
            "pointer": pointer,
            "exists": False,
            "reason": "invalid_shape: path_escapes_git_root",
        }

    # Check that the path is not a directory
    if os.path.isdir(abs_file):
        return {
            "pointer": pointer,
            "exists": False,
            "reason": "invalid_shape: path resolves to a directory",
        }

    if not os.path.isfile(abs_file):
        return {
            "pointer": pointer,
            "exists": False,
            "reason": "missing_file",
        }

    # Load the file
    try:
        with open(abs_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return {
            "pointer": pointer,
            "exists": False,
            "reason": f"file_parse_error: {exc}",
        }
    except OSError as exc:
        return {
            "pointer": pointer,
            "exists": False,
            "reason": f"file_read_error: {exc}",
        }

    # --- jq_path pointer ---
    if jq_path_val:
        # Execute the jq_path against the file; report miss if null/error
        try:
            raw = run_jq(["-c", jq_path_val], file_path=abs_file, timeout=10)
        except JsonUtilsError as exc:
            return {
                "pointer": pointer,
                "exists": False,
                "reason": f"missing_path: {exc}",
            }
        if raw == "null" or not raw:
            return {
                "pointer": pointer,
                "exists": False,
                "reason": "missing_path",
            }
        # Derive kind from the registry: look up the terminal array segment's
        # registered kind.  For nested paths like ".milestones[0].tasks[2]"
        # we extract ".tasks" to match a registered array_path.
        # Falls back to omitting the kind field if no registry match exists.
        kind: Optional[str] = None
        # Find all ".<word>[" segments; use the last one to get the array key.
        seg_matches = re.findall(r'\.([\w]+)\[', jq_path_val)
        if seg_matches and spec_root:
            raw_key = seg_matches[-1]
            try:
                reg_entries = _ekreg.list_entries(file_val, spec_root)
                if reg_entries:
                    # Match by the last array segment name
                    for reg_e in reg_entries:
                        reg_arr_key = reg_e.array_path.split("[].")[-1].lstrip(".")
                        if reg_arr_key == raw_key:
                            kind = reg_e.kind
                            break
            except FileNotFoundError:
                pass  # registry missing — kind remains None

        # Build value_preview (first 3 keys of object, or truncated scalar)
        try:
            val_obj = json.loads(raw)
            if isinstance(val_obj, dict):
                preview_keys = list(val_obj.keys())[:3]
                value_preview = {k: val_obj[k] for k in preview_keys}
            else:
                value_preview = val_obj
        except (json.JSONDecodeError, ValueError):
            value_preview = raw[:120]

        result: Dict[str, Any] = {
            "pointer": pointer,
            "exists": True,
            "jq_path": jq_path_val,
            "value_preview": value_preview,
        }
        if kind:
            result["kind"] = kind
        return result

    # --- id pointer ---
    # C3: shape validation guarantees id_val is set; raise instead of bare assert
    # so -O (optimised) builds don't silently skip the guard.
    if id_val is None:
        raise JsonUtilsError("internal: id_val is None; pointer shape check failed")
    all_ids, id_map = _collect_ids_from_file(data, spec_file=file_val, spec_root=spec_root)

    if id_val in id_map:
        kind_found, resolved_jq, entry = id_map[id_val]
        # Build value_preview (first 3 keys)
        preview_keys = list(entry.keys())[:3]
        value_preview = {k: entry[k] for k in preview_keys}
        return {
            "pointer": pointer,
            "exists": True,
            "kind": kind_found,
            "jq_path": resolved_jq,
            "value_preview": value_preview,
        }
    else:
        # Miss — compute nearest ids from the file's id corpus
        nearest = _nearest_ids(id_val, all_ids, top_n=3)
        result = {
            "pointer": pointer,
            "exists": False,
            "reason": "missing_path",
            "nearest": nearest,
        }
        return result


def resolve_pointers(
    pointer_list: List[Any],
    *,
    spec_root: str,
    git_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a list of pointers per llm_protocol.md §4/§7.3.

    Args:
        pointer_list: List of pointer objects (each {file, id} or {file, jq_path}).
        spec_root: Keyword-only, REQUIRED. Filesystem path to the project's spec
            directory. The entry-key registry is loaded from
            ``<spec_root>/entry_key_registry.json``. Omitting this raises
            ``TypeError`` at call time rather than a later FileNotFoundError —
            this contract supersedes the previous (broken) empty-string default.
        git_root: Keyword-only. Root directory for resolving relative file paths.
            Defaults to cwd.

    Returns:
        Report dict: {"results": [...], "summary": {"hits": N, "misses": M}}

    Always returns a valid dict once spec_root is supplied; never raises beyond
    the argument-binding TypeError described above.
    """
    results = []
    hits = 0
    misses = 0

    for ptr in pointer_list:
        record = _resolve_single_pointer(ptr, spec_root=spec_root, git_root=git_root)
        results.append(record)
        if record.get("exists"):
            hits += 1
        else:
            misses += 1

    return {
        "results": results,
        "summary": {"hits": hits, "misses": misses},
    }


def resolve_pointers_from_stdin(
    *,
    spec_root: str,
    out_path: Optional[str] = None,
    git_root: Optional[str] = None,
) -> None:
    """CLI entry point for ``json resolve-pointers``.

    All parameters are keyword-only. ``spec_root`` is REQUIRED and is the
    host-repo spec directory used to load ``entry_key_registry.json``.
    Reads JSON pointer list from stdin. Writes report JSON to ``out_path``
    (file) or stdout. Always exits 0 — the report is the artifact (§6.4/§7.3).
    """
    raw = sys.stdin.read()

    # Parse input — emit a minimal error report on bad JSON rather than crashing
    try:
        data = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError as exc:
        report = {
            "results": [],
            "summary": {"hits": 0, "misses": 0},
            "parse_error": str(exc),
        }
        _write_report(report, out_path)
        return

    # C4: §7.3 specifies bare list only; {"pointers": [...]} envelope is not part
    # of the protocol (§6.1 uses "scoped_entries", not "pointers"). Reject envelope.
    if not isinstance(data, list):
        report = {
            "results": [],
            "summary": {"hits": 0, "misses": 0},
            "parse_error": "invalid input: expected a JSON array of pointer objects, got " + type(data).__name__,
        }
        _write_report(report, out_path)
        return
    pointer_list = data

    report = resolve_pointers(pointer_list, spec_root=spec_root, git_root=git_root)
    _write_report(report, out_path)


def _write_report(report: Dict[str, Any], out_path: Optional[str]) -> None:
    """Write report JSON to out_path or stdout."""
    output = json.dumps(report, indent=2)
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
    else:
        print(output)


# --- CLI Setup ---

def main():
    parser = argparse.ArgumentParser(description="Smart JSON Tool for AI Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    p_read = subparsers.add_parser("read", help="Read data (use targeted paths, not '.' for full JSON)")
    p_read.add_argument("file", help="JSON file path")
    p_read.add_argument("filter", help="jq filter (e.g. .items[0].name, .version, '.items[] | select(.id==\"x\")')")
    p_read.add_argument("--repo-root", default=".", help="Accepted for CLI consistency; unused by read")

    # Read-multi
    p_readm = subparsers.add_parser("read-multi", help="Read multiple paths in one pass (keyed output)")
    p_readm.add_argument("file", help="JSON file path")
    p_readm.add_argument("filters", nargs="+", help="jq filters (e.g. .version .name)")
    p_readm.add_argument("--repo-root", default=".", help="Accepted for CLI consistency; unused by read-multi")

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

    # Resolve-pointers (llm_protocol.md §4/§7.3)
    # Input: pointer list from stdin (no --in flag per §17.1 flag minimalism).
    # Output: report to --out <path> or stdout.  Always exits 0.
    p_rp = subparsers.add_parser(
        "resolve-pointers",
        help="Validate a JSON pointer list and return a resolution report (always exits 0)",
    )
    p_rp.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="Write report JSON to PATH instead of stdout",
    )
    p_rp.add_argument(
        "--git-root",
        default=None,
        metavar="DIR",
        help="Root directory for resolving relative file paths (defaults to cwd)",
    )
    p_rp.add_argument(
        "--spec-root",
        required=True,
        metavar="DIR",
        help=(
            "Project spec directory containing entry_key_registry.json "
            "(e.g. ./spec for submodule deployments). "
            "Required for deterministic id-field lookup via the entry-key registry."
        ),
    )

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
        elif args.command == "resolve-pointers":
            # Always exits 0; report is the artifact. --spec-root is required by argparse.
            spec_root_arg = os.path.abspath(args.spec_root)
            resolve_pointers_from_stdin(spec_root=spec_root_arg, out_path=args.out, git_root=args.git_root)
            return

        if result is not None:
            print(result)
    except JsonUtilsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
