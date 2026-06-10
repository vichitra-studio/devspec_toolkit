#!/usr/bin/env python3
"""
json_utils.py - Advanced JSON manipulation and discovery tool for AI Agents.

Capabilities:
- CRUD: read, read-multi, patch, insert, delete (using jq)
- Discovery: keys, structure (skeleton)
- Schema: Schema-aware property discovery with $ref resolution and allOf merging
- Pointer verification: resolve-pointers (validates pointer shapes and resolves file+id or file+jq_path pairs)

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
from specdev_tools.core.schema_nav import effective_schema as _schema_nav_effective_schema
from specdev_tools.core.schema_validate import (
    NoSchemaError,
    SchemaBootstrapError,
    SchemaDecodeError,
    SchemaNotFoundError,
    SchemaReferencingError,
    SchemaRuntimeError,
    SchemaValidationError,
    validate_data_against_schema,
)

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


# --- WS1: Differential schema validation helpers ---

def _resolve_effective_toolkit_root(repo_root: Optional[str]) -> str:
    """Resolve the effective toolkit root for schema validation.

    If ``repo_root`` is falsy (None/empty) **or** ``repo_root/tools/schema_registry.json``
    does not exist (e.g. the default ``--repo-root .`` pointing at a host wrapper dir
    in a submodule deployment), fall back to the package-relative toolkit root derived
    from ``json_utils.__file__``.  This is the same anchor that ``_find_schema_dir``
    candidate #2 uses, guaranteeing bare agent invocations (no ``--repo-root``) always
    resolve the schema registry correctly.

    Guard: the falsy check is performed BEFORE ``os.path.join`` so that
    ``repo_root=None`` never reaches ``os.path.join(None, ...)``.
    """
    if repo_root and os.path.isfile(os.path.join(repo_root, "tools", "schema_registry.json")):
        return repo_root
    # Package-relative fallback: tools/specdev_tools/core/ -> ../../.. -> toolkit root
    this_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(this_dir, "..", "..", ".."))


def _path_tuple_to_jq(path_tuple: tuple) -> str:
    """Convert a jsonschema path tuple to a jq-style path string.

    Example: ('plan', 'spec_alignment', 'checklist', 1, 'status') → '.plan.spec_alignment.checklist[1].status'
    """
    parts = []
    for segment in path_tuple:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        else:
            parts.append(f".{segment}")
    return "".join(parts) if parts else "."


def _call_validate_or_raise(eff_root: str, doc: dict, file_path: str) -> list:
    """Run validate_data_against_schema, mapping every schema-validation failure
    to a fail-CLOSED JsonUtilsError (never crash, never silently return [])."""
    try:
        return validate_data_against_schema(eff_root, doc)
    except NoSchemaError:
        raise JsonUtilsError(
            f"{file_path} declares no $schema; json patch validates writes against "
            "the file's schema and cannot proceed without one. "
            "If this is a spec artifact, restore its $schema."
        )
    except (SchemaNotFoundError, SchemaDecodeError, SchemaBootstrapError) as exc:
        uri = getattr(exc, "uri", None) or getattr(exc, "original", exc)
        raise JsonUtilsError(
            f"Could not locate schema for {file_path} ($schema URI: {uri}); "
            "refusing to write. Check --repo-root points to the toolkit root and "
            "that the $schema URI is registered in tools/schema_registry.json."
        )
    except (SchemaReferencingError, SchemaRuntimeError) as exc:
        raise JsonUtilsError(
            f"Could not validate this write (schema resolution/runtime error: {exc.original}); "
            "refusing to proceed."
        )
    except SchemaValidationError as exc:
        raise JsonUtilsError(f"Schema validation failed: {exc}") from exc
    except Exception as exc:  # defensive depth — fail closed
        raise JsonUtilsError(
            f"Unexpected error during schema validation: {type(exc).__name__}: {exc}; "
            "refusing to proceed."
        ) from exc


def _ws1_differential_check(
    file_path: str,
    content: str,
    new_content: str,
    eff_root: str,
) -> None:
    """Run the WS1 differential validation algorithm.

    Raises ``JsonUtilsError`` (fail-closed) if the edit introduces a new schema
    violation, if the document lacks a ``$schema``, if ``$schema`` would change,
    or if the schema cannot be located/loaded.  Also raises on any unexpected
    exception (defensive depth).

    Does NOT raise if the edit introduces no *new* violations — pre-existing errors
    in ``original`` that survive unchanged are ignored (enables incremental repair).

    Parameters
    ----------
    file_path:
        The target file path (used only in didactic messages).
    content:
        The original file content (JSON string).
    new_content:
        The post-edit document (JSON string).
    eff_root:
        Already-resolved toolkit root (from ``_resolve_effective_toolkit_root``).
    """
    try:
        original = json.loads(content)
        new = json.loads(new_content)
    except json.JSONDecodeError as exc:
        raise JsonUtilsError(f"Internal: could not parse document for validation: {exc}") from exc

    # Step 1: Detect $schema change (content-based, robust to any jq form).
    if new.get("$schema") != original.get("$schema"):
        raise JsonUtilsError(
            "Refusing to patch $schema: it determines how the document is validated."
        )

    # Step 2: Refuse if resulting doc has no $schema.
    if not new.get("$schema"):
        raise JsonUtilsError(
            f"{file_path} declares no $schema; json patch validates writes against "
            "the file's schema and cannot proceed without one. "
            "If this is a spec artifact, restore its $schema."
        )

    # Step 3: Validate post-edit doc — wrapped per catch strategy (fail closed).
    errors_after = _call_validate_or_raise(eff_root, new, file_path)

    # Fast path: no errors after edit → write is safe.
    if not errors_after:
        return

    # Step 4: Compute errors_before to distinguish pre-existing from newly introduced.
    errors_before = _call_validate_or_raise(eff_root, original, file_path)

    new_errors = set(errors_after) - set(errors_before)
    if new_errors:
        # Sort for deterministic output.
        sorted_errors = sorted(new_errors, key=lambda x: (x[0], x[1]))
        lines = [
            f"  path {_path_tuple_to_jq(path)}: {msg}"
            for path, msg in sorted_errors
        ]
        raise JsonUtilsError(
            "Write refused: this edit introduces schema violation(s):\n" + "\n".join(lines)
        )


def json_patch(
    file_path: str,
    path_selector: str,
    value: str,
    is_json: bool = True,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    validate: bool = True,
) -> str:
    """Update a value at the path.

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written).

    When ``validate`` is True (the default), the edit is validated against the
    document's own ``$schema`` before writing.  Uses a differential (before/after)
    approach so that pre-existing schema violations are not treated as blockers
    — only violations *introduced* by this edit are refused.
    """
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

    if validate:
        eff_root = _resolve_effective_toolkit_root(repo_root)
        _ws1_differential_check(file_path, content, new_content, eff_root)

    if dry_run:
        return f"[dry-run] Would update {path_selector} in {file_path}:\n{new_content}"
    json_write_atomic(file_path, new_content)
    return f"Updated {path_selector} in {file_path}"


def json_insert(
    file_path: str,
    path_selector: str,
    value: str,
    is_json: bool = True,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    validate: bool = True,
    create_schema: Optional[str] = None,
) -> str:
    """Append to array or merge object.

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written).

    When ``validate`` is True (the default), the edit is validated against the
    document's own ``$schema`` before writing.  Uses a differential (before/after)
    approach so pre-existing violations are not treated as blockers.

    ``create_schema``: if the target file does not exist **and** ``create_schema``
    is set to a registered ``$schema`` URI, the file is seeded as
    ``{"$schema": "<uri>"}`` before the insert is applied.  This bootstraps
    array-valued fields in a single shot (e.g. the ``command_prefixes.json``
    first-use path).  If the file already exists, ``create_schema`` is a no-op
    (the normal path applies; WS1 validation then enforces the existing schema).
    """
    # --- ORDERING IS LOAD-BEARING ---
    # ``_check_file`` is normally the first statement and raises ``File not found``
    # before any other logic.  The ``--create-schema`` seed branch MUST be the
    # function's first action so it short-circuits ``_check_file`` for missing files.
    # Normal (error-on-null) filter: used for existing files.
    _normal_filter = (
        f'({path_selector}) |= (if type=="array" then . + [$v] '
        f'elif type=="object" then . + $v '
        f'else error("Cannot insert into " + type) end)'
    )
    # Create-variant filter: null-coalesces the target so a missing array field is
    # bootstrapped to [$v] instead of erroring "Cannot insert into null".
    # (The normal filter hits ``else error(...)`` on a null/missing field.)
    _create_filter = (
        f'({path_selector}) |= (if type=="array" then . + [$v] '
        f'elif type=="object" then . + $v '
        f'elif type=="null" then [$v] '
        f'else error("Cannot insert into " + type) end)'
    )

    using_seed = False
    if create_schema and not os.path.isfile(file_path):
        # Seed path: create the file content in memory; do NOT call _check_file.
        content = json.dumps({"$schema": create_schema})
        using_seed = True
        active_filter = _create_filter
    else:
        _check_file(file_path)
        with open(file_path, 'r') as f:
            content = f.read()
        active_filter = _normal_filter

    _require_valid_filter(path_selector)

    args = ['--indent', str(JQ_INDENT)]
    if is_json:
        args.extend(['--argjson', 'v', value])
    else:
        args.extend(['--arg', 'v', value])

    args.append(active_filter)

    new_content = run_jq(args, input_data=content, timeout=10)

    if validate:
        eff_root = _resolve_effective_toolkit_root(repo_root)
        _ws1_differential_check(file_path, content, new_content, eff_root)

    if dry_run:
        if using_seed:
            return f"[dry-run] Would create and insert into {path_selector} in {file_path}:\n{new_content}"
        return f"[dry-run] Would insert into {path_selector} in {file_path}:\n{new_content}"

    # On seed path, ensure the parent directory exists before writing.
    if using_seed:
        parent_dir = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(parent_dir, exist_ok=True)
    json_write_atomic(file_path, new_content)
    if using_seed:
        return f"Created and inserted into {path_selector} in {file_path}"
    return f"Inserted into {path_selector} in {file_path}"


def json_delete(
    file_path: str,
    path_selector: str,
    dry_run: bool = False,
) -> str:
    """Delete item at path.

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written).
    """
    _check_file(file_path)
    _require_valid_filter(path_selector)

    args = ['--indent', str(JQ_INDENT)]
    filter_expr = f'del({path_selector})'
    args.append(filter_expr)

    with open(file_path, 'r') as f:
        content = f.read()

    new_content = run_jq(args, input_data=content, timeout=10)
    if dry_run:
        return f"[dry-run] Would delete {path_selector} in {file_path}:\n{new_content}"
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
    """Resolve $ref and merge allOf (+ oneOf/anyOf/if-then-else) to produce a navigable schema node.

    Thin adapter over ``schema_nav.effective_schema`` with
    ``include_conditionals=True`` so that ``json schema`` discovery can navigate
    into conditional-branch properties (e.g. ``plan.docs`` oneOf branches).

    Handles the composition patterns in this codebase:
    - $ref: resolved via resolve_fn (local #/$defs/... or URN vc:...)
    - allOf: branches resolved and merged (properties unioned, required concatenated)
    - oneOf/anyOf/if-then-else: branch properties unioned into navigable set
      (required is NOT extended for conditional branches — they are mutually exclusive)

    Note: the old claim that oneOf/anyOf/if/then/else "never add navigable
    properties" was false.  Dozens of schema locations define properties inside
    conditional branches (e.g. plan.docs in 16_impl_context.schema.json);
    enabling conditionals here allows full discovery of those fields.
    """
    return _schema_nav_effective_schema(node, resolve_fn, include_conditionals=True)


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

    def _resolve_node(node: dict) -> Optional[dict]:
        """Resolve a single $ref node."""
        if not isinstance(node, dict) or '$ref' not in node:
            return node
        ref = node['$ref']
        # Local ref: look up in current schema's $defs
        if ref.startswith('#/$defs/'):
            def_name = ref.split('/')[-1]
            resolved = schema.get('$defs', {}).get(def_name)
            return resolved if resolved else None
        # URN ref: resolve via $id index
        resolved = resolve_ref(ref, id_index, ref_cache)
        return resolved if resolved else None

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


# --- Pointer Resolution ---

# Forbidden path prefixes/patterns for pointer validation.
_FORBIDDEN_PREFIXES = (".specdev/",)
_FORBIDDEN_EXTENSIONS = (".txt",)

# Absolute path prefixes that indicate temp/scratch paths (forbidden for pointers).
# Includes standard POSIX paths plus /private/tmp (macOS symlink resolution of /tmp).
_FORBIDDEN_ABS_PREFIXES = (
    "/tmp/",
    "/var/tmp/",
    "/private/tmp/",
    "/var/folders/",  # macOS temp dir used by TMPDIR
)


def _is_forbidden_path(file_path: str) -> Optional[str]:
    """Return a reason string if file_path is a forbidden pointer target, else None.

    Forbidden paths:
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
    """Validate pointer shape: must be a JSON object with 'file' and either 'id' or 'jq_path'.

    Returns (valid, reason).  On success reason is "".

    Valid shapes:
      { "file": str, "id": str }
      { "file": str, "jq_path": str }

    Forbidden:
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
    """Return top_n nearest ids by normalised token-level Levenshtein distance.

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
    repo_root: str,
) -> Tuple[List[str], Dict[str, Tuple[str, str, Any]]]:
    """Walk a parsed JSON object and collect all entry ids.

    For each spec file, the entry-key registry (``<repo_root>/tools/entry_key_registry.json``)
    is the sole source of truth for which arrays to scan and which id field to use.
    Files not registered in the registry return empty results — no broad scan.
    Nested arrays (e.g. ``milestones[].tasks``) are walked using the ``nested``
    declarations in the registry.

    Args:
        data: parsed JSON object to index.
        spec_file: basename or relative path of the spec file (required).
        repo_root: filesystem path to the toolkit root directory (required).
            The registry is loaded from ``<repo_root>/tools/entry_key_registry.json``.
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
    reg_entries = _ekreg.list_entries(spec_file, repo_root)

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
        if _ekreg.is_corpus_excluded(top_key, repo_root):
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
    repo_root: str,
    git_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve one pointer to a result record per § specdev json resolve-pointers report shape.

    repo_root (keyword-only, required) is the toolkit root directory containing
    ``tools/entry_key_registry.json``.
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
        if seg_matches and repo_root:
            raw_key = seg_matches[-1]
            try:
                reg_entries = _ekreg.list_entries(file_val, repo_root)
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
    all_ids, id_map = _collect_ids_from_file(data, spec_file=file_val, repo_root=repo_root)

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
    repo_root: str,
    git_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a list of pointers. Each pointer must be {file, id} or {file, jq_path}.

    Args:
        pointer_list: List of pointer objects (each {file, id} or {file, jq_path}).
        repo_root: Keyword-only, REQUIRED. Filesystem path to the toolkit root
            directory. The entry-key registry is loaded from
            ``<repo_root>/tools/entry_key_registry.json``. Omitting this raises
            ``TypeError`` at call time rather than a later FileNotFoundError.
        git_root: Keyword-only. Root directory for resolving relative file paths.
            Defaults to cwd.

    Returns:
        Report dict: {"results": [...], "summary": {"hits": N, "misses": M}}

    Always returns a valid dict once repo_root is supplied; never raises beyond
    the argument-binding TypeError described above.
    """
    results = []
    hits = 0
    misses = 0

    for ptr in pointer_list:
        record = _resolve_single_pointer(ptr, repo_root=repo_root, git_root=git_root)
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
    repo_root: str,
    out_path: Optional[str] = None,
    git_root: Optional[str] = None,
) -> None:
    """CLI entry point for ``json resolve-pointers``.

    All parameters are keyword-only. ``repo_root`` is REQUIRED and is the
    toolkit root directory containing ``tools/entry_key_registry.json``.
    Reads JSON pointer list from stdin. Writes report JSON to ``out_path``
    (file) or stdout. Always exits 0 — the report is the artifact (§ specdev json resolve-pointers).
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

    # C4: resolve-pointers accepts a bare JSON array only; {"pointers": [...]} envelope is rejected
    # (the error envelope uses "errors[]", not "pointers").
    if not isinstance(data, list):
        report = {
            "results": [],
            "summary": {"hits": 0, "misses": 0},
            "parse_error": "invalid input: expected a JSON array of pointer objects, got " + type(data).__name__,
        }
        _write_report(report, out_path)
        return
    pointer_list = data

    report = resolve_pointers(pointer_list, repo_root=repo_root, git_root=git_root)
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
    p_patch.add_argument("--dry-run", action="store_true", help="Preview result without writing")
    p_patch.add_argument(
        "--repo-root",
        default=".",
        help=(
            "Toolkit root for schema validation (e.g. ./devspec_toolkit for submodule "
            "deployments). Defaults to '.'; falls back to package-relative toolkit root "
            "when tools/schema_registry.json is not found at the given path."
        ),
    )

    # Insert
    p_insert = subparsers.add_parser("insert", help="Insert/Append value")
    p_insert.add_argument("file", help="JSON file path")
    p_insert.add_argument("path", help="jq path to target array/object")
    p_insert.add_argument("value", help="Value to insert")
    p_insert.add_argument("--raw", action="store_true", help="Treat value as string, not JSON")
    p_insert.add_argument("--dry-run", action="store_true", help="Preview result without writing")
    p_insert.add_argument(
        "--create-schema",
        metavar="URI",
        default=None,
        help=(
            "When the target file does not exist, seed it as {\"$schema\": \"<URI>\"} "
            "before applying the insert. Bootstraps array-valued fields (e.g. "
            "allowed_prefixes in command_prefixes.json) in a single shot. "
            "No-op when the file already exists."
        ),
    )
    p_insert.add_argument(
        "--repo-root",
        default=".",
        help=(
            "Toolkit root for schema validation (e.g. ./devspec_toolkit for submodule "
            "deployments). Defaults to '.'; falls back to package-relative toolkit root "
            "when tools/schema_registry.json is not found at the given path."
        ),
    )

    # Delete
    p_del = subparsers.add_parser("delete", help="Delete value")
    p_del.add_argument("file", help="JSON file path")
    p_del.add_argument("path", help="jq path to target")
    p_del.add_argument("--dry-run", action="store_true", help="Preview result without writing")

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

    # Resolve-pointers: validate and resolve a JSON array of pointer objects.
    # Input: pointer list from stdin (no --in flag; flag minimalism).
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
        "--repo-root",
        required=True,
        metavar="DIR",
        help=(
            "Toolkit root directory containing tools/entry_key_registry.json "
            "(e.g. ./devspec_toolkit for submodule deployments). "
            "Required for deterministic id-field lookup via the entry-key registry."
        ),
    )
    p_rp.add_argument(
        "--spec-root",
        required=False,
        default=None,
        metavar="DIR",
        help=(
            "Deprecated; accepted but ignored. "
            "The registry is now toolkit-side (--repo-root). "
            "This flag will be removed in a future release."
        ),
    )
    p_rp.add_argument(
        "--git-root",
        default=None,
        metavar="DIR",
        help="Root directory for resolving relative file paths (defaults to cwd)",
    )

    args = parser.parse_args()

    try:
        result = None
        if args.command == "read":
            result = json_read(args.file, args.filter)
        elif args.command == "read-multi":
            result = json_read_multi(args.file, args.filters)
        elif args.command == "patch":
            result = json_patch(
                args.file, args.path, args.value, not args.raw,
                dry_run=getattr(args, "dry_run", False),
                repo_root=os.path.abspath(args.repo_root),
                validate=True,
            )
        elif args.command == "insert":
            result = json_insert(
                args.file, args.path, args.value, not args.raw,
                dry_run=getattr(args, "dry_run", False),
                repo_root=os.path.abspath(args.repo_root),
                validate=True,
                create_schema=getattr(args, "create_schema", None),
            )
        elif args.command == "delete":
            result = json_delete(args.file, args.path, dry_run=getattr(args, "dry_run", False))
        elif args.command == "keys":
            result = json_keys(args.file, args.path)
        elif args.command == "structure":
            result = json_structure(args.file, args.path)
        elif args.command == "schema":
            result = json_schema_discovery(args.file, args.path, repo_root=args.repo_root)
        elif args.command == "resolve-pointers":
            # Always exits 0; report is the artifact.
            if getattr(args, "spec_root", None):
                print(
                    "--spec-root is no longer used by resolve-pointers (registry is toolkit-side). "
                    "Flag will be removed in a future release.",
                    file=sys.stderr,
                )
            repo_root_arg = os.path.abspath(args.repo_root)
            resolve_pointers_from_stdin(repo_root=repo_root_arg, out_path=args.out, git_root=args.git_root)
            return

        if result is not None:
            print(result)
    except JsonUtilsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
