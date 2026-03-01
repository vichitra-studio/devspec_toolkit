#!/usr/bin/env python3
"""
json_utils.py - Advanced JSON manipulation and discovery tool for AI Agents.

Capabilities:
- CRUD: read, patch, insert, delete (using jq)
- Discovery: keys, structure (skeleton)
- Schema: Schema-aware property discovery via registry linkage
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Union

# --- Configuration ---
JQ_INDENT = 4  # Enforce 4-space indent to match repo style


def find_file_in_repo(filename: str) -> Optional[str]:
    """Find a file by name starting from the repository root."""
    try:
        # Get the current working directory (where agent runs)
        cwd = os.getcwd()
        
        # Use find from the current working directory to locate the file
        find_cmd = ['find', cwd, '-name', filename, '-type', 'f', '-print', '-quit']
        result = subprocess.run(find_cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        # If find fails, return None to indicate file not found
        return None
    return None


def run_jq(args: List[str], input_data: Optional[str] = None, file_path: Optional[str] = None, timeout: int = 30) -> str:
    """Run jq command and return output."""
    cmd = ['jq'] + args
    if file_path:
        cmd.append(file_path)
        
    try:
        if input_data:
            result = subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=True, timeout=timeout)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        error_msg = f"jq command timed out after {timeout} seconds: {' '.join(cmd)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # More graceful error handling for syntax errors
        error_msg = f"jq failed with command: {' '.join(cmd)}"
        if e.stderr:
            error_msg += f" - stderr: {e.stderr.strip()}"
        if e.stdout:
            error_msg += f" - stdout: {e.stdout.strip()}"
        
        # Check if this is a syntax error that we can safely ignore in some contexts
        if "syntax error" in e.stderr.lower() or "unexpected" in e.stderr.lower():
            # For operations that might have invalid jq paths, still report the error but don't crash
            print(f"Warning: {error_msg} (continuing execution)", file=sys.stderr)
            return ""
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)


def resolve_schema_path(file_path: str, registry_path: Optional[str] = None) -> Optional[str]:
    """Resolve the local schema file path from the target JSON's $schema field."""
    # 1. Read $schema url
    try:
        schema_url = run_jq(['-r', '.["$schema"]'], file_path=file_path)
        if not schema_url or schema_url == 'null':
            return None
    except Exception as e:
        print(f"Error reading $schema from {file_path}: {e}", file=sys.stderr)
        return None

    # 2. Load registry with dynamic search capability using find for better cross-platform support
    if not registry_path:
        # Try to find schema_registry.json using the reusable find function from repo root
        registry_path = find_file_in_repo('schema_registry.json')
    
    if not registry_path or not os.path.exists(registry_path):
        print(f"Warning: Could not find schema_registry.json. Schema-aware features will be limited.", file=sys.stderr)
        return None

    try:
        with open(registry_path, 'r') as f:
            registry = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load registry {registry_path}: {e}. Schema-aware features will be limited.", file=sys.stderr)
        return None

    # 3. Lookup
    # Registry format is typically { "uri": "path/to/schema" }
    # Paths in registry are relative to the repo root
    
    # Try direct match
    rel_path = registry.get(schema_url)
    
    # Try mapping if registry has a 'mappings' key (common pattern)
    if not rel_path and 'mappings' in registry:
         rel_path = registry['mappings'].get(schema_url)

    if not rel_path:
        print(f"Warning: Schema URL '{schema_url}' not found in registry {registry_path}. Schema-aware features will be limited.", file=sys.stderr)
        return None

    # Resolve schema path using find_file_in_repo for simplicity and reliability
    try:
        # Try to find the schema file directly using our reusable function
        full_schema_path = find_file_in_repo(os.path.basename(rel_path))
        if full_schema_path and os.path.exists(full_schema_path):
            return full_schema_path
            
    except Exception as e:
        print(f"Warning: Failed to resolve schema path '{rel_path}' for URL '{schema_url}': {e}. Schema-aware features will be limited.", file=sys.stderr)
        pass
    
    print(f"Warning: Could not locate schema file '{rel_path}' for URL '{schema_url}'. Schema-aware features will be limited.", file=sys.stderr)
    return None


# --- Core Operations ---

def json_read(file_path: str, jq_filter: str) -> None:
    """Read data using a jq filter."""
    # Block full JSON reads (filter is ".")
    if jq_filter == ".":
        print("Error: Full JSON reads are not allowed because they are inefficient. Please specify a targeted path to read.", file=sys.stderr)
        sys.exit(1)
    
    try:
        result = run_jq(['-r', jq_filter], file_path=file_path, timeout=10)
        if result and result != 'null':
            print(result)
        elif result == 'null':
            # Explicitly handle null results
            pass
    except Exception as e:
        print(f"Error reading {file_path} with filter '{jq_filter}': {e}", file=sys.stderr)
        sys.exit(1)


def json_keys(file_path: str, path_selector: str) -> None:
    """List keys at the given path."""
    filter_expr = f'({path_selector}) | keys'
    try:
        result = run_jq(['-r', filter_expr], file_path=file_path, timeout=10)
        if result and result != 'null':
            print(result)
    except Exception as e:
         # Fallback if path doesn't return an object
         print(f"Error listing keys at {path_selector} in {file_path}: {e}", file=sys.stderr)
         sys.exit(1)


def json_write_atomic(file_path: str, data_str: str) -> None:
    """Write string data to file atomically, enforcing format."""
    # Ensure it's valid JSON first by piping through jq
    formatted = run_jq(['--indent', str(JQ_INDENT), '.'], input_data=data_str, timeout=10)
    
    dirname = os.path.dirname(file_path) or '.'
    with tempfile.NamedTemporaryFile('w', dir=dirname, delete=False) as tf:
        tf.write(formatted)
        temp_name = tf.name
    
    os.replace(temp_name, file_path)


def json_patch(file_path: str, path_selector: str, value: str, is_json: bool = True) -> None:
    """Update a value at the path."""
    # Logic: usage of --argjson for typed JSON, --arg for strings if needed
    # usage: jq --indent 4 --argjson v <value> 'path = $v' file
    
    args = ['--indent', str(JQ_INDENT)]
    if is_json:
        args.extend(['--argjson', 'v', value])
    else:
        args.extend(['--arg', 'v', value])
        
    filter_expr = f'({path_selector}) = $v'
    args.append(filter_expr)
    
    # atomic read-modify-write
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        new_content = run_jq(args, input_data=content, timeout=10)
        json_write_atomic(file_path, new_content)
        print(f"Updated {path_selector} in {file_path}")
    except Exception as e:
        print(f"Error patching {file_path} at path '{path_selector}': {e}", file=sys.stderr)
        sys.exit(1)


def json_insert(file_path: str, path_selector: str, value: str, is_json: bool = True) -> None:
    """Append to array or merge object."""
    args = ['--indent', str(JQ_INDENT)]
    if is_json:
        args.extend(['--argjson', 'v', value])
    else:
        args.extend(['--arg', 'v', value])

    # Try append first (+= [$v]), if fail, try += $v (object merge) or error
    # We use a robust filter: 
    # if type array then += [$v] elif type object then += $v else error("Cannot insert into " + type) end
    filter_expr = f'({path_selector}) |= (if type=="array" then . + [$v] elif type=="object" then . + $v else error("Cannot insert into " + type) end)'
    
    args.append(filter_expr)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        new_content = run_jq(args, input_data=content, timeout=10)
        json_write_atomic(file_path, new_content)
        print(f"Inserted into {path_selector} in {file_path}")
    except Exception as e:
        print(f"Error inserting into {file_path} at path '{path_selector}': {e}", file=sys.stderr)
        sys.exit(1)


def json_delete(file_path: str, path_selector: str) -> None:
    """Delete item at path."""
    args = ['--indent', str(JQ_INDENT)]
    filter_expr = f'del({path_selector})'
    args.append(filter_expr)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        new_content = run_jq(args, input_data=content, timeout=10)
        json_write_atomic(file_path, new_content)
        print(f"Deleted {path_selector} in {file_path}")
    except Exception as e:
        print(f"Error deleting from {file_path} at path '{path_selector}': {e}", file=sys.stderr)
        sys.exit(1)




def json_structure(file_path: str, path_selector: str = ".") -> None:
    """Return a visual hierarchical structure of the JSON."""
    try:
        # Get the actual data at path
        result = run_jq(['-c', f'({path_selector})'], file_path=file_path, timeout=30)
        
        if result == 'null':
            print("null")
            return
            
        parsed_data = json.loads(result)
        
        # Create a visual tree representation
        def _print_structure(data, prefix="", is_last=True):
            if isinstance(data, dict):
                items = list(data.items())
                for i, (key, value) in enumerate(items):
                    is_last_item = (i == len(items) - 1)
                    connector = "└── " if is_last_item else "├── "
                    print(f"{prefix}{connector}{key}: {type(value).__name__}")
                    
                    if isinstance(value, (dict, list)):
                        extension = "    " if is_last_item else "│   "
                        _print_structure(value, prefix + extension, is_last_item)
                        
            elif isinstance(data, list):
                print(f"{prefix}└── array[{len(data)} items]")
                if len(data) > 0:
                    # Only show first element type to avoid excessive output
                    first_elem = data[0]
                    print(f"{prefix}    ├── [0]: {type(first_elem).__name__}")
                    if isinstance(first_elem, (dict, list)):
                        extension = "    "
                        _print_structure(first_elem, prefix + extension, True)
                        
        # Start the visual tree representation
        if isinstance(parsed_data, dict):
            items = list(parsed_data.items())
            for i, (key, value) in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                print(f"{connector}{key}: {type(value).__name__}")
                
                if isinstance(value, (dict, list)):
                    extension = "    " if is_last else "│   "
                    _print_structure(value, extension, is_last)
        elif isinstance(parsed_data, list):
            print(f"array[{len(parsed_data)} items]")
            if len(parsed_data) > 0:
                first_elem = parsed_data[0]
                print(f"├── [0]: {type(first_elem).__name__}")
                if isinstance(first_elem, (dict, list)):
                    _print_structure(first_elem, "    ", True)
        else:
            print(f"{type(parsed_data).__name__}")
            
    except Exception as e:
        # Provide better error messages for debugging
        if "unexpected" in str(e).lower() or "syntax error" in str(e).lower():
            print(f"Error: Invalid path '{path_selector}' for structure - {e}")
        else:
            print(f"Error showing structure for {file_path} at path '{path_selector}': {e}", file=sys.stderr)
        sys.exit(1)


def json_schema_discovery(file_path: str, path_selector: str) -> None:
    """Discover allowable fields from the schema."""
    # Try to find registry in repo root using our reusable function
    registry_path = find_file_in_repo('schema_registry.json')
    
    schema_path = resolve_schema_path(file_path, registry_path)
    if not schema_path:
        print(f"Error: Could not resolve schema for {file_path}. Make sure it has a $schema field and registry is properly configured.", file=sys.stderr)
        sys.exit(1)
        
    # We need to map the data path (e.g. .capabilities[0].verb) to schema path (properties.capabilities.items.properties.verb)
    # This is complex in pure jq.
    # Simplified approach: 
    # 1. Load schema
    # 2. Traverse schema structure corresponding to the path
    
    # For now, let's just dump the relevant part of the schema if possible.
    # We will use a python walker for the path since JSONPath to SchemaPath mapping is non-trivial.
    
    # Naive Schema Walker:
    # 1. Split path_selector into parts.
    # 2. Walk schema properties/items.
    
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"Error loading schema from {schema_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Remove leading '.'
    clean_path = path_selector.lstrip('.').replace('[]', '')
    if not clean_path:
        print(json.dumps(schema.get('properties', {}), indent=2))
        return

    # Basic approximation of path traversal
    # Note: proper implementation requires a full JSONPointer parser. 
    # Here we assume simple dot notation for properties.
    current = schema
    
    # This is a heuristic walker for the tool's v1
    parts = clean_path.replace('[', '.').replace(']', '').split('.')
    parts = [p for p in parts if p]
    
    # Try to navigate the schema path
    path_found = True
    for part in parts:
        # Move through properties
        if 'properties' in current and part in current['properties']:
            current = current['properties'][part]
        elif 'items' in current and isinstance(current['items'], dict):
            # Array traversal - check if it's an object array
            if 'properties' in current['items'] and part in current['items']['properties']:
                current = current['items']['properties'][part]
            else:
                # If we can't find the specific property, show array structure
                current = current['items']
        elif '$ref' in current:
             # Just warn about ref, we don't resolve deep refs yet in this tool version
             print(f"Stopped at $ref: {current['$ref']}. (Deep ref resolution not yet supported)", file=sys.stderr)
             path_found = False
             break
        else:
            # Try to find in any level of nested structure
            path_found = False
            break

    if not path_found:
        # If we couldn't navigate the exact path, try to get information about the schema structure
        print(json.dumps({
            "error": f"Could not navigate to path '{path_selector}' in schema",
            "schema_info": {
                "type": current.get("type", "unknown"),
                "description": current.get("description", "No description available")
            }
        }, indent=2))
        return
              
    # Output useful info about the target
    info = {
        "type": current.get("type"),
        "description": current.get("description"),
        "allowed_properties": list(current.get("properties", {}).keys()) if current.get("type") == "object" else None,
        "items": current.get("items", {}).get("type") if current.get("type") == "array" else None,
        "required": current.get("required"),
        "enum": current.get("enum")
    }
    print(json.dumps(info, indent=2))

#Find all occurances of value
## TODO: Refine and expose as a tool
def trace_relationship(root_dir: str, value: str) -> None:
    """
    Tracing custom ID relationships using ripgrep's JSON output.
    """
    # -t json: Search only JSON files
    # --json: Output machine-readable matches
    cmd = ['rg', '--json', '-t', 'json', '--fixed-strings', value, root_dir]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        findings = []
        
        for line in result.stdout.strip().split('\n'):
            msg = json.loads(line)
            if msg["type"] == "match":
                findings.append({
                    "file": msg["data"]["path"]["text"],
                    "line": msg["data"]["line_number"],
                    "content": msg["data"]["lines"]["text"].strip()
                })
        
        print(json.dumps(findings, indent=4))
    except Exception as e:
        print(f"Discovery error: {e}", file=sys.stderr)



# --- CLI Setup ---

def main():
    parser = argparse.ArgumentParser(description="Smart JSON Tool for AI Agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    p_read = subparsers.add_parser("read", help="Read data (use targeted paths, not '.' for full JSON)")
    p_read.add_argument("file", help="JSON file path")
    p_read.add_argument("filter", help="jq filter (e.g. .items[0])", default=".", nargs="?")

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
    p_struct = subparsers.add_parser("structure", help="Show visual hierarchical structure (use targeted paths, not '.' for full JSON)")
    p_struct.add_argument("file", help="JSON file path")
    p_struct.add_argument("path", help="jq path (optional)", default=".", nargs="?")
    
    # Schema
    p_schema = subparsers.add_parser("schema", help="Query schema capabilities")
    p_schema.add_argument("file", help="Source data file (to find $schema)")
    p_schema.add_argument("path", help="Path looking for (e.g. .capabilities)")

    args = parser.parse_args()

    if args.command == "read":
        json_read(args.file, args.filter)
    elif args.command == "patch":
        json_patch(args.file, args.path, args.value, not args.raw)
    elif args.command == "insert":
        json_insert(args.file, args.path, args.value, not args.raw)
    elif args.command == "delete":
        json_delete(args.file, args.path)
    elif args.command == "keys":
        json_keys(args.file, args.path)
    elif args.command == "structure":
        json_structure(args.file, args.path)
    elif args.command == "schema":
        json_schema_discovery(args.file, args.path)

if __name__ == "__main__":
    main()
