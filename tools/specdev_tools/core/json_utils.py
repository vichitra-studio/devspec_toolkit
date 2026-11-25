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
import contextlib
import glob as glob_mod
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

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
    SchemaViolation,
    jq_path_of,
    schema_violations,
    violation_text,
)
from specdev_tools.trace.lockfile import replace_file_atomically

# Detects bare array iterators (e.g. .arr[], to_entries[]) that produce value streams.
# Used to guard read-multi, whose {key: value} construct produces one output object per
# stream element — breaking the single-keyed-object output contract.
_STREAMING_FILTER_RE = re.compile(r'\[\s*\]')

# --- Configuration ---
JQ_INDENT = 4  # Indent of a new file; an existing file keeps its own (see detect_indent)


def _jq_command(args: List[str]) -> List[str]:
    """The jq command line for *args*, with jq resolved in this process (jq itself gets no PATH)."""
    return [shutil.which('jq') or 'jq', *args]


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
        # jq starts with no environment (env={}): a filter such as ``$ENV.TOKEN`` or ``env.TOKEN`` reads null.
        result = subprocess.run(
            _jq_command(['-n', f'try ({jq_filter}) catch null']),
            capture_output=True, text=True, timeout=5, env={},
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
    cmd = _jq_command(args)
    if file_path:
        cmd.append(file_path)

    try:
        if input_data is not None:
            result = subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=True, timeout=timeout, env={})
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout, env={})
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
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and '$id' in data:
                    index[data['$id']] = path
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue

    # Also scan sibling canon/ directory for canon schemas
    canon_dir = os.path.normpath(os.path.join(schema_dir, '..', 'canon'))
    if os.path.isdir(canon_dir):
        for path in glob_mod.glob(os.path.join(canon_dir, '**/*.schema.json'), recursive=True):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and '$id' in data:
                        index[data['$id']] = path
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
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
            with open(file_path, 'r', encoding='utf-8') as f:
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


def find_schema_dir(repo_root: Optional[str] = None) -> Optional[str]:
    """Locate the schema/ directory.

    Public API: this is part of json_utils' supported surface and may be imported
    by other toolkit modules (e.g. validation linters).

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
        schema_dir = find_schema_dir(repo_root)
        if schema_dir:
            id_index = build_id_index(schema_dir)

    if id_index:
        resolved = id_index.get(schema_url)
        if resolved and os.path.exists(resolved):
            return resolved

    return None


# --- Core Operations ---

def json_read(file_path: str, jq_filter: str, as_json: bool = False) -> Optional[str]:
    """Read data using a jq filter. Returns the result string, or None if empty.

    With *as_json* the value is printed as JSON (a string keeps its quotes) instead of raw text.
    """
    if jq_filter == ".":
        raise JsonUtilsError(
            "Full JSON reads are not allowed. Specify a targeted path (e.g. .title, .items[0])."
        )

    _check_file(file_path)
    _require_valid_filter(jq_filter)

    flags = [] if as_json else ['-r']
    result = run_jq([*flags, jq_filter], file_path=file_path, timeout=10)
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


def detect_indent(text: str, default: str = " " * JQ_INDENT) -> str:
    """The indentation unit of the JSON *text*: the leading whitespace of its first indented non-blank line
    (``"\t"`` for a tab), else *default*."""
    for line in text.split("\n"):
        stripped = line.lstrip(" \t")
        lead = line[: len(line) - len(stripped)]
        if stripped.strip("\r") and lead:
            return "\t" if lead.startswith("\t") else lead
    return default


def _jq_indent_args(indent: str) -> List[str]:
    """The jq flags that print *indent*: ``--tab``, ``--indent n`` for 1 to 7 spaces, else the default indent."""
    if indent == "\t":
        return ["--tab"]
    if indent.strip(" ") == "" and 1 <= len(indent) <= 7:
        return ["--indent", str(len(indent))]
    return ["--indent", str(JQ_INDENT)]


def json_write_atomic(file_path: str, data_str: str) -> None:
    """Write *data_str* to *file_path* atomically in the file's own indentation (new file: ``JQ_INDENT`` spaces).

    Raises JsonUtilsError on empty content or a jq failure; a failed write leaves no temp file (the write is
    ``trace.lockfile.replace_file_atomically``: the file keeps its mode).
    """
    if not data_str or not data_str.strip():
        raise JsonUtilsError(
            f"Refusing to write empty content to {file_path}. "
            "This usually indicates an upstream jq error — check the filter and input."
        )

    try:
        with open(file_path, encoding='utf-8') as fh:
            original_text = fh.read()
    except OSError:
        original_text = ''
    indent_args = _jq_indent_args(detect_indent(original_text))
    formatted = run_jq([*indent_args, '.'], input_data=data_str, timeout=10)

    if not formatted or not formatted.strip():
        raise JsonUtilsError(
            f"jq formatting produced empty output for {file_path}. Input may be invalid JSON."
        )

    replace_file_atomically(file_path, formatted + '\n')


# --- WS1: Differential schema validation helpers ---

def resolve_effective_toolkit_root(repo_root: Optional[str]) -> str:
    """Resolve the effective toolkit root for schema validation.

    If ``repo_root`` is falsy (None/empty) **or** ``repo_root/tools/schema_registry.json``
    does not exist (e.g. the default ``--repo-root .`` pointing at a host wrapper dir
    in a submodule deployment), fall back to the package-relative toolkit root derived
    from ``json_utils.__file__``.  This is the same anchor that ``find_schema_dir``
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


def _call_validate_or_raise(
    eff_root: str, doc: dict, file_path: str, command: str,
) -> List[SchemaViolation]:
    """Run schema_violations, mapping every schema-validation failure
    to a fail-CLOSED JsonUtilsError (never crash, never silently return [])."""
    try:
        return schema_violations(eff_root, doc)
    except NoSchemaError:
        raise JsonUtilsError(
            f"{file_path} declares no $schema; {command} validates writes against "
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
    *,
    command: str,
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
        Already-resolved toolkit root (from ``resolve_effective_toolkit_root``).
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
            f"{file_path} declares no $schema; {command} validates writes against "
            "the file's schema and cannot proceed without one. "
            "If this is a spec artifact, restore its $schema."
        )

    # Step 3: Validate post-edit doc — wrapped per catch strategy (fail closed).
    errors_after = _call_validate_or_raise(eff_root, new, file_path, command)

    # Fast path: no errors after edit → write is safe.
    if not errors_after:
        return

    # Step 4: Compute errors_before to distinguish pre-existing from newly introduced.
    errors_before = _call_validate_or_raise(eff_root, original, file_path, command)
    errors_before = _reindexed_after_removal(errors_before, _removed_array_item(original, new))

    added = _added_violations(errors_before, errors_after)
    if added:
        lines = [
            f"  path {jq_path_of(violation.path)}: {violation_text(violation)}"
            for violation in added
        ]
        raise JsonUtilsError(
            "Write refused: this edit introduces schema violation(s):\n" + "\n".join(lines)
        )


def _removed_array_item(original: Any, new: Any, path: tuple = ()) -> Optional[Tuple[tuple, int]]:
    """``(path of the array, index)`` when *new* is *original* with one array item removed, else ``None``."""
    if isinstance(original, list) and isinstance(new, list):
        if len(original) == len(new) + 1:
            index = next((i for i, item in enumerate(new) if original[i] != item), len(new))
            return (path, index) if original[:index] + original[index + 1:] == new else None
        if len(original) == len(new):
            for i, (old_item, new_item) in enumerate(zip(original, new)):
                found = _removed_array_item(old_item, new_item, path + (i,))
                if found:
                    return found
    elif isinstance(original, dict) and isinstance(new, dict):
        for key in original.keys() & new.keys():
            found = _removed_array_item(original[key], new[key], path + (key,))
            if found:
                return found
    return None


def _reindexed_after_removal(
    before: List[SchemaViolation], removed: Optional[Tuple[tuple, int]]
) -> List[SchemaViolation]:
    """*before* as its paths read once array item ``removed`` is gone: the removed item's violations drop out and the
    later items' violations move down one index, so a violation of a later sibling is not counted as added."""
    if removed is None:
        return before
    array_path, index = removed
    depth = len(array_path)
    result: List[SchemaViolation] = []
    for violation in before:
        path = violation.path
        if path[:depth] == array_path and len(path) > depth and isinstance(path[depth], int):
            if path[depth] == index:
                continue
            if path[depth] > index:
                violation = violation._replace(path=path[:depth] + (path[depth] - 1,) + path[depth + 1:])
        result.append(violation)
    return result


def _added_violations(
    before: List[SchemaViolation], after: List[SchemaViolation]
) -> List[SchemaViolation]:
    """The violations of *after* that an edit added, sorted by path then message (``unevaluatedProperties`` last).

    A violation is identified by ``(path, keyword)``, not by its message: the message of ``minItems`` or ``anyOf``
    quotes the instance and so changes with any edit inside it.  For each identity the violations beyond the count
    that *before* already had are the added ones, so one more violation of a kind that was already there at a path is
    still refused (DEVSPEC-317).
    """
    already = Counter((violation.path, violation.keyword) for violation in before)
    added: List[SchemaViolation] = []
    for violation in sorted(after, key=lambda v: (v.path, v.keyword, v.message)):
        key = (violation.path, violation.keyword)
        if already[key] > 0:
            already[key] -= 1
        else:
            added.append(violation)
    # An ``unevaluatedProperties`` violation only repeats that a deeper one exists: the specific ones come first.
    return sorted(added, key=lambda v: (v.keyword == "unevaluatedProperties", v.path, v.message))


def check_edit(file_path: str, content: str, new_content: str, repo_root: Optional[str]) -> None:
    """Refuse (``JsonUtilsError``) *new_content* when it adds a schema violation to *content*, the text of *file_path*.

    The same differential check ``json patch`` and ``json insert`` run before they write (the refusal names
    ``json patch``), for a caller that holds the edited text in memory.  Violations that *content* already had are ignored.
    """
    _ws1_differential_check(
        file_path, content, new_content, resolve_effective_toolkit_root(repo_root), command="json patch",
    )


def _run_value_filter(filter_expr: str, content: str, value: str, is_json: bool) -> str:
    """Run *filter_expr* over the JSON text *content* with ``$v`` bound to *value* (JSON when *is_json*, else a string)."""
    args = ['--indent', str(JQ_INDENT), '--argjson' if is_json else '--arg', 'v', value, filter_expr]
    return run_jq(args, input_data=content, timeout=10)


def patch_text(content: str, path_selector: str, value: str, is_json: bool = True) -> str:
    """The JSON text *content* with the value at *path_selector* replaced by *value*; nothing is read or written.

    Raises ``JsonUtilsError`` for a jq filter that does not parse or fails on the document.
    """
    _require_valid_filter(path_selector)
    return _run_value_filter(f'({path_selector}) = $v', content, value, is_json)


_ARRAY_ITEM_OBJECT_COUNT = (
    '[path({sel}) as $p | select(($p|length)>0 and ($p|last|type)=="number") | getpath($p) | select(type=="object")] | length'
)


def _refuse_array_item_target(content: str, path_selector: str) -> None:
    """Raise ``JsonUtilsError`` when *path_selector* names an object held as an item of an array in *content*."""
    try:
        count = int(run_jq([_ARRAY_ITEM_OBJECT_COUNT.format(sel=path_selector)], input_data=content, timeout=10))
    except (JsonUtilsError, ValueError):
        return  # not a path expression: the insert filter reports it
    if count > 0:
        raise JsonUtilsError(
            f"'{path_selector}' names an item of an array (an object): an insert there would merge into that item, "
            "not add one. Insert into the array itself (the path without the index) to append, "
            "or use json patch for a field of the item."
        )


def insert_text(content: str, path_selector: str, value: str, is_json: bool = True, *, create: bool = False) -> str:
    """The JSON text *content* with *value* appended to the array (or merged into the object) at *path_selector*.

    With *create*, a missing (null) target becomes ``[value]``.  A path that names an object held as an array item
    (``.rules[1]``) is refused: the value would merge into that item.  Raises ``JsonUtilsError`` for a jq filter that
    does not parse, for such a path, or when the target is neither an array nor an object (nor null with *create*).
    """
    _require_valid_filter(path_selector)
    _refuse_array_item_target(content, path_selector)
    return _run_value_filter(_insert_filter(path_selector, create=create), content, value, is_json)


def delete_text(content: str, path_selector: str) -> str:
    """The JSON text *content* without the value at *path_selector*.

    Raises ``JsonUtilsError`` for a jq filter that does not parse or fails on the document.
    """
    _require_valid_filter(path_selector)
    return run_jq(['--indent', str(JQ_INDENT), f'del({path_selector})'], input_data=content, timeout=10)


def _insert_filter(path_selector: str, *, create: bool) -> str:
    """The jq filter that appends ``$v`` to the array or merges it into the object at *path_selector*.

    With *create*, a null target (a missing field) becomes ``[$v]`` instead of an error.
    """
    on_null = 'elif type=="null" then [$v] ' if create else ''
    return (
        f'({path_selector}) |= (if type=="array" then . + [$v] '
        f'elif type=="object" then . + $v '
        f'{on_null}else error("Cannot insert into " + type) end)'
    )


# A path through an array index at or past the end of that array does not exist: a patch there would pad the array.
_COUNT_PATHS = (
    '. as $d | [path({sel}) | select(. as $p | all(range(0; length); . as $i | (($p[$i] | type) != "number") or '
    '(try ($d | getpath($p[:$i]) | if type == "array" then ($p[$i] < length and $p[$i] >= -length) else true end) '
    'catch true)))] | length'
)
_COUNT_EXISTING_PATHS = (
    '. as $d | [path({sel}) | select(length==0 or (. as $p | try ($d | getpath($p[:-1]) | '
    'if type=="array" then ($p[-1]|type)=="number" and $p[-1] < length and $p[-1] >= -length '
    'elif type=="object" then has($p[-1]) else false end) catch false))] | length'
)


def _count_targets(content: str, path_selector: str, *, existing_only: bool) -> Optional[int]:
    """How many paths *path_selector* yields in *content* (with *existing_only*: paths that exist and can be deleted).

    Returns None when jq cannot count it (the selector is not a path expression); the edit then reports its own error.
    """
    template = _COUNT_EXISTING_PATHS if existing_only else _COUNT_PATHS
    try:
        return int(run_jq([template.format(sel=path_selector)], input_data=content, timeout=10))
    except (JsonUtilsError, ValueError):
        return None


def _warn_if_many(path_selector: str, count: Optional[int]) -> None:
    """Print the multi-match warning to stderr when *count* is above one."""
    if count is not None and count > 1:
        print(f"warning: '{path_selector}' matches {count} values; all {count} are changed.", file=sys.stderr)


def _edit_counted(
    content: str, path_selector: str, location: str, edit: Callable[[], str], *, existing_only: bool,
) -> tuple[str, Optional[int]]:
    """Run ``edit()`` (a patch or delete of *path_selector* in the text *content*) and return the new text and count.

    Raises ``JsonUtilsError`` before the edit when the selector matches nothing (with *existing_only*, nothing that
    exists and can be deleted); warns on stderr when it matches several values.  The one place both ``json patch`` /
    ``json delete`` and a batch item get this refusal.  Returns ``(new text, match count)``; the caller warns
    (``_warn_if_many``) once the edit has passed its schema check, so the warning is true.
    """
    count = _count_targets(content, path_selector, existing_only=existing_only)
    if count == 0 and existing_only:
        raise JsonUtilsError(
            f"Nothing to delete at '{path_selector}' in {location}: the selector matches nothing, "
            "or the index is out of range. Nothing was changed."
        )
    if count == 0:
        raise JsonUtilsError(
            f"The selector '{path_selector}' matches nothing in {location}: nothing was changed. "
            "Check the filter (a select() that names no item, or an index past the end of an array?)."
        )
    return edit(), count


_SUMMARY_MAX_MATCHES = 5
_SUMMARY_MAX_CHARS = 120


def _compact(value: Any) -> str:
    """*value* as compact JSON, cut at ``_SUMMARY_MAX_CHARS`` characters."""
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return text if len(text) <= _SUMMARY_MAX_CHARS else text[:_SUMMARY_MAX_CHARS] + '...'


def _value_of(value: str, is_json: bool) -> Any:
    """The Python value that the command line *value* stands for (JSON when *is_json*, else the raw string)."""
    return json.loads(value) if is_json else value


def _dry_run_text(
    verb: str, path_selector: str, location: str, content: str, new_content: str,
    *, new: Optional[tuple[Any]], show_old: bool, show_file: bool,
) -> str:
    """What a dry run returns: the whole resulting file (*show_file*), else a short report of the matches.

    *new* is a one-item tuple holding the value written at each match (None for a delete); *show_old* lists the
    values now at the matches, at most ``_SUMMARY_MAX_MATCHES`` of them.
    """
    if show_file:
        return f"[dry-run] Would {verb} {path_selector} in {location}:\n{new_content}"
    matches = json.loads(run_jq(['-c', f'[({path_selector})]'], input_data=content, timeout=10))
    lines = [f"[dry-run] Would {verb} {path_selector} in {location}: {len(matches)} value(s)"]
    for old in matches[:_SUMMARY_MAX_MATCHES]:
        if show_old:
            lines.append(f"  old: {_compact(old)}")
        if new is not None:
            lines.append(f"  new: {_compact(new[0])}")
    if len(matches) > _SUMMARY_MAX_MATCHES:
        lines.append(f"  ... and {len(matches) - _SUMMARY_MAX_MATCHES} more")
    return "\n".join(lines)


def json_patch(
    file_path: str,
    path_selector: str,
    value: str,
    is_json: bool = True,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    validate: bool = True,
    show_file: bool = False,
) -> str:
    """Update a value at the path.

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written): a short report of the matches, or with *show_file* the whole resulting file.

    When ``validate`` is True (the default), the edit is validated against the
    document's own ``$schema`` before writing.  Uses a differential (before/after)
    approach so that pre-existing schema violations are not treated as blockers
    — only violations *introduced* by this edit are refused.
    """
    _check_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content, count = _edit_counted(
        content, path_selector, file_path, lambda: patch_text(content, path_selector, value, is_json), existing_only=False,
    )

    if validate:
        eff_root = resolve_effective_toolkit_root(repo_root)
        _ws1_differential_check(file_path, content, new_content, eff_root, command="json patch")
    _warn_if_many(path_selector, count)

    if dry_run:
        return _dry_run_text(
            "update", path_selector, file_path, content, new_content,
            new=(_value_of(value, is_json),), show_old=True, show_file=show_file,
        )
    json_write_atomic(file_path, new_content)
    return f"Updated {path_selector} in {file_path}"


_BATCH_VERBS = {"patch": "update", "insert": "insert into", "delete": "delete"}


def _apply_batch_item(index: int, item: Any, content: str, location: str) -> tuple[str, str, str, Optional[int]]:
    """Apply one item of a batch file to the JSON text *content*.

    Returns ``(verb, path, new_content, match count)`` (the count is None for an insert).  Raises ``JsonUtilsError("batch item <i> (<op> <path>): <reason>")`` for a
    malformed item, a selector that matches nothing or a failing jq filter.
    """
    op = item.get("op") if isinstance(item, dict) else None
    path = item.get("path") if isinstance(item, dict) else None
    label = f"batch item {index} ({op} {path})"
    if op not in _BATCH_VERBS:
        raise JsonUtilsError(f"{label}: 'op' must be one of {', '.join(_BATCH_VERBS)}")
    if not isinstance(path, str) or not path:
        raise JsonUtilsError(f"{label}: 'path' must be a jq path")
    if op != "delete" and "value" not in item:
        raise JsonUtilsError(f"{label}: 'value' is missing")
    try:
        if op == "delete":
            new_content, count = _edit_counted(
                content, path, location, lambda: delete_text(content, path), existing_only=True,
            )
            return _BATCH_VERBS[op], path, new_content, count
        value = json.dumps(item["value"], ensure_ascii=False)
        if op == "patch":
            new_content, count = _edit_counted(
                content, path, location, lambda: patch_text(content, path, value, True), existing_only=False,
            )
        else:
            new_content, count = insert_text(content, path, value, True), None
        return _BATCH_VERBS[op], path, new_content, count
    except JsonUtilsError as error:
        raise JsonUtilsError(f"{label}: {error}") from error


def json_patch_batch(
    file_path: str,
    ops_path: str,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    show_file: bool = False,
) -> str:
    """Apply the operations of the JSON array in *ops_path* to *file_path* in order: one validation, one atomic write.

    Each item is ``{"op": "patch"|"insert"|"delete", "path": "<jq path>", "value": <any JSON>}`` (no ``value`` for
    ``delete``).  Returns ``Applied <n> operations to <file>``; with *dry_run* a report that lists the first
    ``_SUMMARY_MAX_MATCHES`` operations (the whole resulting file with *show_file*) and writes nothing.
    Raises ``JsonUtilsError`` before anything is written when the ops file is not an array, an item is malformed or
    fails (the message names the item), or the edit adds a schema violation.
    """
    _check_file(file_path)
    try:
        with open(ops_path, 'r', encoding='utf-8') as f:
            ops = json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        raise JsonUtilsError(f"cannot read the batch file {ops_path}: {error}") from error
    if not isinstance(ops, list) or not ops:
        raise JsonUtilsError(f"The batch file {ops_path} must hold a non-empty JSON array of {{op, path, value}} items.")

    with open(file_path, 'r', encoding='utf-8') as f:
        original = f.read()
    running = original
    reports: list[str] = []
    counts: list[tuple[str, Optional[int]]] = []
    for index, item in enumerate(ops):
        before = running
        verb, path, running, count = _apply_batch_item(index, item, before, file_path)
        counts.append((path, count))
        if dry_run and not show_file and index < _SUMMARY_MAX_MATCHES:
            new = None if verb == "delete" else (item["value"],)
            reports.append(_dry_run_text(
                verb, path, file_path, before, running, new=new, show_old=verb != "insert into", show_file=False,
            ))

    _ws1_differential_check(
        file_path, original, running, resolve_effective_toolkit_root(repo_root), command="json patch --batch",
    )
    for path, count in counts:
        _warn_if_many(path, count)
    if not dry_run:
        json_write_atomic(file_path, running)
        return f"Applied {len(ops)} operations to {file_path}"
    heading = f"[dry-run] Would apply {len(ops)} operations to {file_path}"
    if show_file:
        return f"{heading}:\n{running}"
    more = [f"  ... and {len(ops) - _SUMMARY_MAX_MATCHES} more operations"] if len(ops) > _SUMMARY_MAX_MATCHES else []
    return "\n".join([heading, *reports, *more])


def json_insert(
    file_path: str,
    path_selector: str,
    value: str,
    is_json: bool = True,
    dry_run: bool = False,
    repo_root: Optional[str] = None,
    validate: bool = True,
    create_schema: Optional[str] = None,
    show_file: bool = False,
) -> str:
    """Append to array or merge object.  A path that names an object held as an array item is refused (see ``insert_text``).

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written): a short report of the matches, or with *show_file* the whole resulting file.

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
    # ``_insert_filter(create=True)`` (seed path) null-coalesces the target so a missing array field is
    # bootstrapped to [$v]; the normal filter errors "Cannot insert into null" for an existing file.
    using_seed = False
    if create_schema and not os.path.isfile(file_path):
        # Seed path: create the file content in memory; do NOT call _check_file.
        content = json.dumps({"$schema": create_schema})
        using_seed = True
    else:
        _check_file(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

    new_content = insert_text(content, path_selector, value, is_json, create=using_seed)

    if validate:
        eff_root = resolve_effective_toolkit_root(repo_root)
        _ws1_differential_check(file_path, content, new_content, eff_root, command="json insert")

    if dry_run:
        return _dry_run_text(
            "create and insert into" if using_seed else "insert into", path_selector, file_path, content, new_content,
            new=(_value_of(value, is_json),), show_old=False, show_file=show_file,
        )

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
    repo_root: Optional[str] = None,
    validate: bool = False,
    show_file: bool = False,
) -> str:
    """Delete item at path.

    Returns a confirmation message, or a preview string when *dry_run* is True
    (no file is written): a short report of the matches, or with *show_file* the whole resulting file.

    ``validate`` defaults to False: the classic ``json delete`` and ``node status <id> active`` validate nothing.  When
    True, the edit is checked against the document's own ``$schema`` as ``json patch`` is: only a violation the
    deletion adds refuses it.  When the deletion removes an array item, the violations of the later items are compared
    at their new index, so a violation a later sibling already had is not counted as added.
    """
    _check_file(file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content, count = _edit_counted(
        content, path_selector, file_path, lambda: delete_text(content, path_selector), existing_only=True,
    )
    if validate:
        _ws1_differential_check(file_path, content, new_content, resolve_effective_toolkit_root(repo_root), command="json delete")
    _warn_if_many(path_selector, count)
    if dry_run:
        return _dry_run_text(
            "delete", path_selector, file_path, content, new_content, new=None, show_old=True, show_file=show_file,
        )
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


_CONSTRAINT_KEYWORDS = (
    "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "additionalProperties", "const",
)


def json_schema_discovery(file_path: str, path_selector: str, repo_root: Optional[str] = None) -> Optional[str]:
    """Discover allowable fields from the schema, resolving $ref URNs and allOf inline.

    Returns JSON string of discovered schema info.
    """
    _check_file(file_path)

    # Build index once — shared between resolve_schema_path and ref resolution
    schema_dir = find_schema_dir(repo_root)
    id_index = build_id_index(schema_dir) if schema_dir else {}
    ref_cache: Dict[str, dict] = {}

    schema_path = resolve_schema_path(file_path, repo_root=repo_root, id_index=id_index)
    if not schema_path:
        raise JsonUtilsError(
            f"Could not resolve schema for {file_path}. "
            "Make sure it has a $schema field and the schema directory is accessible."
        )

    with open(schema_path, 'r', encoding='utf-8') as f:
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

    info: Dict[str, Any] = {
        "type": current.get("type"),
        "description": current.get("description"),
        "allowed_properties": list(current.get("properties", {}).keys()) if current.get("type") == "object" or current.get("properties") else None,
        "items": current.get("items", {}).get("type") if current.get("type") == "array" else None,
        "required": current.get("required"),
        "enum": current.get("enum")
    }
    info.update(_constraints_of(current))
    if current.get("type") == "array" and isinstance(current.get("items"), dict):
        items_constraints = _constraints_of(_effective_schema(current["items"], _resolve_node))
        if items_constraints:
            info["items_constraints"] = items_constraints
    return json.dumps(info, indent=2)


def _constraints_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """The keywords of ``_CONSTRAINT_KEYWORDS`` that the schema *node* carries, under their own names."""
    return {keyword: node[keyword] for keyword in _CONSTRAINT_KEYWORDS if keyword in node}


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


def _under_any(paths: set[str], prefix: str) -> bool:
    """True when any of *paths* is *prefix* or below it, comparing the prefix as written and with symlinks resolved."""
    prefixes = {os.path.normpath(prefix), os.path.realpath(prefix)}
    return any(p == q or p.startswith(q + os.sep) for p in paths for q in prefixes)


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
        forms = {os.path.normpath(file_path), os.path.realpath(file_path)}
        for prefix in _FORBIDDEN_ABS_PREFIXES:
            if _under_any(forms, prefix):
                return f"path is under forbidden temp prefix '{prefix}'"
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir and _under_any(forms, tmpdir):
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


def nearest_ids(target: str, candidates: List[str], top_n: int = 3) -> List[Dict[str, Any]]:
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


class _IdDefinition(NamedTuple):
    """One definition of an id in a spec file: the singular kind label, its jq path, and the raw entry."""

    kind: str
    jq_path: str
    entry: Any


def _collect_id_definitions(
    data: Any,
    spec_file: str,
    repo_root: str,
) -> Tuple[List[str], Dict[str, List[_IdDefinition]]]:
    """Walk a parsed JSON object and collect every definition of every entry id.

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
      - ``id_map``: {id_value -> [definitions in document order]}; each
        definition is an ``_IdDefinition`` (kind, jq_path, entry).  More than
        one definition means the id is ambiguous.
    """
    all_ids: List[str] = []
    id_map: Dict[str, List[_IdDefinition]] = {}

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
    # Group registered entries by their top-level array key (the first path
    # segment).  ``list_entries`` emits a parent entry before its descendants,
    # so registry order within each group is parent-first.  Each entry's
    # ``array_path`` (e.g. ".milestones[].tasks[].acceptance_criteria") is
    # walked to arbitrary depth by ``iter_array_path`` — no single-level cap.
    by_top: Dict[str, List[Any]] = {}
    for entry in reg_entries:
        top_key = _ekreg.array_top_key(entry.array_path)
        by_top.setdefault(top_key, []).append(entry)

    # Outer iteration follows the spec document's key order (as before) so id
    # collection order is data-driven and deterministic; inner iteration follows
    # registry order (top-level array, then each deeper nested array).
    for top_key, top_val in data.items():
        # A top-level node container is a list, or an object holding the nodes
        # (dotted paths such as ``.plan.items``, map-keyed ``.environments{}``).
        if not isinstance(top_val, (list, dict)):
            continue
        # Skip corpus-excluded keys.
        if _ekreg.is_corpus_excluded(top_key, repo_root):
            continue
        if top_key not in by_top:
            # Array not registered for this file — skip deliberately.
            continue

        for entry in by_top[top_key]:
            for item, jq_path, map_key in _ekreg.iter_nodes(data, entry.array_path):
                # A map-keyed node's id is its map key; otherwise read the id field.
                found_id = map_key if map_key is not None else item.get(entry.id_field)
                if not isinstance(found_id, str) or not found_id:
                    continue
                all_ids.append(found_id)
                id_map.setdefault(found_id, []).append(_IdDefinition(entry.kind, jq_path, item))

    return all_ids, id_map


def _collect_ids_from_file(
    data: Any,
    spec_file: str,
    repo_root: str,
) -> Tuple[List[str], Dict[str, Tuple[str, str, Any]]]:
    """Like ``_collect_id_definitions`` but ``id_map`` keeps the first definition of each id as a tuple.

    Only tests call it (``test_entry_key_registry.py``, ``test_annotation_scan.py``); the toolkit reads definitions.

    Returns ``(all_ids, {id_value -> (kind, jq_path, entry_object)})``; on a collision the first
    occurrence wins (deterministic).
    """
    all_ids, definitions = _collect_id_definitions(data, spec_file, repo_root)
    return all_ids, {found_id: (found[0].kind, found[0].jq_path, found[0].entry) for found_id, found in definitions.items()}


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
    A pointer that does not resolve returns a dict with ``exists: False``.
    Raises ``FileNotFoundError`` when the registry is missing under *repo_root*
    and ``UnicodeDecodeError`` when the target file is not UTF-8.
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
                        reg_arr_key = _ekreg.array_leaf_key(reg_e.array_path)
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
    all_ids, id_map = _collect_id_definitions(data, spec_file=file_val, repo_root=repo_root)

    if id_val in id_map:
        definitions = id_map[id_val]
        first = definitions[0]
        # Build value_preview (first 3 keys)
        preview_keys = list(first.entry.keys())[:3]
        value_preview = {k: first.entry[k] for k in preview_keys}
        hit: Dict[str, Any] = {
            "pointer": pointer,
            "exists": True,
            "kind": first.kind,
            "jq_path": first.jq_path,
            "value_preview": value_preview,
        }
        if len(definitions) > 1:
            hit["ambiguous"] = True
            hit["locations"] = [{"kind": d.kind, "jq_path": d.jq_path} for d in definitions]
        return hit
    else:
        # Miss — compute nearest ids from the file's id corpus
        nearest = nearest_ids(id_val, all_ids, top_n=3)
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

    A pointer that does not resolve is a miss in the report. Beyond the
    argument-binding TypeError described above, raises ``FileNotFoundError``
    when the registry is missing under *repo_root* and ``UnicodeDecodeError``
    when a target file is not UTF-8.
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
    (file) or stdout. Exits 0 when a report is written, whatever its misses — the
    report is the artifact (§ specdev json resolve-pointers). A registry missing
    under ``repo_root`` (``FileNotFoundError``) or a target file that is not UTF-8
    (``UnicodeDecodeError``) propagates and the command exits non-zero.
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

def _add_repo_root(parser: argparse.ArgumentParser, command: str) -> None:
    """Give *parser* the ``--repo-root`` flag the rest of the ``json`` family takes (unused by *command*)."""
    parser.add_argument("--repo-root", default=".", help=f"Accepted for CLI consistency; unused by {command}")


def _add_ref(parser: argparse.ArgumentParser) -> None:
    """Add the ``--ref REF`` option of the read subcommands."""
    parser.add_argument(
        "--ref", metavar="REF", default=None,
        help="Read the file as of this git ref (tag, branch or commit) instead of the working tree",
    )


def _materialise_at_ref(file_path: str, ref: str) -> str:
    """Write *file_path* as of the git *ref* to a new temporary folder and return the copy's path.

    Raises ``JsonUtilsError`` (``cannot read <path> at <ref>: <git reason>``) when git is missing, the folder is not in
    a repository, the ref is unknown or the path is absent at the ref.  The caller removes the folder.
    """
    # Imported here: ``graph`` is heavy, and only ``--ref`` needs it.
    from specdev_tools.graph.gitview import GitViewError, git_reason, run_git

    # Resolve the folder as git does (``--show-toplevel`` is a real path), so a path through a symlink gets a ``rel``.
    absolute = os.path.abspath(file_path)
    abs_path = os.path.join(os.path.realpath(os.path.dirname(absolute)), os.path.basename(absolute))
    folder = os.path.dirname(abs_path)
    while not os.path.isdir(folder):
        folder = os.path.dirname(folder)
    try:
        top = run_git(folder, ["rev-parse", "--show-toplevel"])
        if top.returncode != 0:
            raise JsonUtilsError(f"cannot read {file_path} at {ref}: {git_reason(top)}")
        root = top.stdout.decode("utf-8").strip()
        rel = os.path.relpath(abs_path, root).replace(os.sep, "/")
        shown = run_git(root, ["show", f"{ref}:{rel}"])
    except GitViewError as error:
        raise JsonUtilsError(f"cannot read {file_path} at {ref}: {error}") from error
    if shown.returncode != 0:
        raise JsonUtilsError(f"cannot read {rel} at {ref}: {git_reason(shown)}")
    copy_dir = tempfile.mkdtemp()
    copy_path = os.path.join(copy_dir, os.path.basename(abs_path))
    try:
        pathlib.Path(copy_path).write_bytes(shown.stdout)
    except BaseException:
        shutil.rmtree(copy_dir, ignore_errors=True)
        raise
    return copy_path


@contextlib.contextmanager
def _read_source(file_path: str, ref: Optional[str]) -> Iterator[str]:
    """The path to read: *file_path* itself, or a temporary copy of it as of the git *ref* (removed on exit)."""
    if ref is None:
        yield file_path
        return
    copy_path = _materialise_at_ref(file_path, ref)
    try:
        yield copy_path
    except JsonUtilsError as error:
        raise JsonUtilsError(str(error).replace(copy_path, f"{file_path} at {ref}")) from error
    finally:
        shutil.rmtree(os.path.dirname(copy_path), ignore_errors=True)


def build_json_parser() -> argparse.ArgumentParser:
    """Build the ``specdev json`` argparse parser (no parsing, no side effects)."""
    parser = argparse.ArgumentParser(description="Smart JSON Tool for AI Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    p_read = subparsers.add_parser("read", help="Read data (use targeted paths, not '.' for full JSON)")
    p_read.add_argument("file", help="JSON file path")
    p_read.add_argument("filter", help="jq filter (e.g. .items[0].name, .version, '.items[] | select(.id==\"x\")')")
    p_read.add_argument("--repo-root", default=".", help="Accepted for CLI consistency; unused by read")
    p_read.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Print the value as JSON (strings quoted) instead of raw text",
    )
    _add_ref(p_read)

    # Read-multi
    p_readm = subparsers.add_parser("read-multi", help="Read multiple paths in one pass (keyed output)")
    p_readm.add_argument("file", help="JSON file path")
    p_readm.add_argument("filters", nargs="+", help="jq filters (e.g. .version .name)")
    p_readm.add_argument("--repo-root", default=".", help="Accepted for CLI consistency; unused by read-multi")
    _add_ref(p_readm)

    # Patch
    p_patch = subparsers.add_parser(
        "patch", help="Update value",
        epilog="This is the file form (a file and a jq path). A node of a spec is written by its id: specdev json patch --id <node-id> <field-path> <value> (`specdev json patch --id <node-id> --help`).",
    )
    p_patch.add_argument("file", help="JSON file path")
    p_patch.add_argument("path", nargs="?", help="jq path to target (e.g. .version)")
    p_patch.add_argument("value", nargs="?", help="New value (JSON string or raw string)")
    p_patch.add_argument(
        "--batch", metavar="OPS_FILE", default=None,
        help='JSON array of {"op": "patch"|"insert"|"delete", "path": ..., "value": ...} applied in one validation and one write',
    )
    p_patch.add_argument("--raw", action="store_true", help="Treat value as string, not JSON")
    p_patch.add_argument("--dry-run", action="store_true", help="Print a short summary of the change without writing")
    p_patch.add_argument("--show-file", action="store_true", help="With --dry-run, print the whole resulting file")
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
    p_insert = subparsers.add_parser(
        "insert", help="Insert/Append value",
        epilog="This is the file form (a file and a jq path). A node of a spec is written by its id: specdev json insert --id <node-id> <field-path> <value>, or --step <NN> <collection-path> <node-object> for a new node (`specdev json insert --id <node-id> --help`).",
    )
    p_insert.add_argument("file", help="JSON file path")
    p_insert.add_argument("path", help="jq path to target array/object")
    p_insert.add_argument("value", help="Value to insert")
    p_insert.add_argument("--raw", action="store_true", help="Treat value as string, not JSON")
    p_insert.add_argument("--dry-run", action="store_true", help="Print a short summary of the change without writing")
    p_insert.add_argument("--show-file", action="store_true", help="With --dry-run, print the whole resulting file")
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
    p_del = subparsers.add_parser(
        "delete", help="Delete value",
        epilog="This is the file form (a file and a jq path). A node of a spec is written by its id: specdev json delete --id <node-id> (`specdev json delete --id <node-id> --help`).",
    )
    p_del.add_argument("file", help="JSON file path")
    p_del.add_argument("path", help="jq path to target")
    p_del.add_argument("--dry-run", action="store_true", help="Print a short summary of the change without writing")
    p_del.add_argument("--show-file", action="store_true", help="With --dry-run, print the whole resulting file")
    p_del.add_argument(
        "--repo-root", default=".",
        help="Toolkit root for the schema check (as for patch); falls back to the package-relative toolkit root",
    )

    # Keys
    p_keys = subparsers.add_parser("keys", help="List keys")
    p_keys.add_argument("file", help="JSON file path")
    p_keys.add_argument("path", help="jq path (optional)", default=".", nargs="?")
    _add_repo_root(p_keys, "keys")
    _add_ref(p_keys)

    # Structure
    p_struct = subparsers.add_parser("structure", help="Show visual hierarchical structure")
    p_struct.add_argument("file", help="JSON file path")
    p_struct.add_argument("path", help="jq path (optional)", default=".", nargs="?")
    _add_repo_root(p_struct, "structure")
    _add_ref(p_struct)

    # Schema
    p_schema = subparsers.add_parser("schema", help="Query schema capabilities")
    p_schema.add_argument("file", help="Source data file (to find $schema)")
    p_schema.add_argument("path", help="Path looking for (e.g. .capabilities)")
    p_schema.add_argument("--repo-root", help="Toolkit root dir (for submodule deployments)")

    # Resolve-pointers: validate and resolve a JSON array of pointer objects.
    # Input: pointer list from stdin (no --in flag; flag minimalism).
    # Output: report to --out <path> or stdout.  Exits 0 when a report is written;
    # a missing registry or a target file that is not UTF-8 exits non-zero.
    p_rp = subparsers.add_parser(
        "resolve-pointers",
        help="Validate a JSON pointer list and return a resolution report (exits 0 with a report; non-zero when the registry is missing or a target file is not UTF-8)",
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
    return parser


def main():
    parser = build_json_parser()

    args = parser.parse_args()
    if getattr(args, "show_file", False) and not getattr(args, "dry_run", False):
        parser.error("--show-file needs --dry-run (it prints the file a dry run would write)")

    try:
        result = None
        if args.command == "read":
            with _read_source(args.file, args.ref) as path:
                result = json_read(path, args.filter, as_json=args.as_json)
        elif args.command == "read-multi":
            with _read_source(args.file, args.ref) as path:
                result = json_read_multi(path, args.filters)
        elif args.command == "patch" and args.batch:
            if args.path is not None or args.value is not None:
                raise JsonUtilsError("--batch takes the operations from its file: give no path or value with it.")
            result = json_patch_batch(
                args.file, args.batch, dry_run=args.dry_run, repo_root=os.path.abspath(args.repo_root),
                show_file=args.show_file,
            )
        elif args.command == "patch":
            if args.path is None or args.value is None:
                parser.error("the following arguments are required: path, value (or give --batch OPS_FILE)")
            result = json_patch(
                args.file, args.path, args.value, not args.raw,
                dry_run=getattr(args, "dry_run", False),
                repo_root=os.path.abspath(args.repo_root),
                validate=True,
                show_file=args.show_file,
            )
        elif args.command == "insert":
            result = json_insert(
                args.file, args.path, args.value, not args.raw,
                dry_run=getattr(args, "dry_run", False),
                repo_root=os.path.abspath(args.repo_root),
                validate=True,
                create_schema=getattr(args, "create_schema", None),
                show_file=args.show_file,
            )
        elif args.command == "delete":
            result = json_delete(
                args.file, args.path, dry_run=getattr(args, "dry_run", False),
                repo_root=os.path.abspath(args.repo_root), validate=True, show_file=args.show_file,
            )
        elif args.command == "keys":
            with _read_source(args.file, args.ref) as path:
                result = json_keys(path, args.path)
        elif args.command == "structure":
            with _read_source(args.file, args.ref) as path:
                result = json_structure(path, args.path)
        elif args.command == "schema":
            result = json_schema_discovery(args.file, args.path, repo_root=args.repo_root)
        elif args.command == "resolve-pointers":
            # Exits 0 when a report is written; the report is the artifact.
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
