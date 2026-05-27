#!/usr/bin/env bash
# EXTRACTOR_VERSION=1
# Extract a digest_validator JSON from a Python validator/generation module.
# Usage: extract_digest_validator.sh <source_file> <output_path>
# Uses Python AST (via python3 -c) for reliable extraction — no regex on Python.

set -euo pipefail

EXTRACTOR_VERSION="1.0.0"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <source_file> <output_path>" >&2
  exit 1
fi

SOURCE_FILE="$1"
OUTPUT_PATH="$2"

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "Error: source file not found: $SOURCE_FILE" >&2
  exit 1
fi

SOURCE_SHA=$(git hash-object "$SOURCE_FILE")
EXTRACTED_AT=$(date +%s)
REL_PATH="${SOURCE_FILE#./}"

# ── All extraction via Python AST ────────────────────────────────────────────
python3 - "$SOURCE_FILE" "$OUTPUT_PATH" "$REL_PATH" "$SOURCE_SHA" "$EXTRACTOR_VERSION" "$EXTRACTED_AT" <<'PYEOF'
import ast
import json
import re
import sys
from pathlib import Path

source_file = sys.argv[1]
output_path = sys.argv[2]
rel_path    = sys.argv[3]
source_sha  = sys.argv[4]
extractor_version = sys.argv[5]
extracted_at = int(sys.argv[6])

# Derive Python module path from file path
# e.g. tools/specdev_tools/validation/hallucination_lint.py
#   -> tools.specdev_tools.validation.hallucination_lint
module_path = rel_path.replace("/", ".").removesuffix(".py")

with open(source_file, encoding="utf-8") as f:
    source = f.read()

try:
    tree = ast.parse(source, filename=source_file)
except SyntaxError as exc:
    print(f"Error: AST parse failed for {source_file}: {exc}", file=sys.stderr)
    sys.exit(1)

error_codes = set()
warning_codes = set()
guide_refs = set()
schema_path_refs = set()
checks_exported = []
imports = set()

# E/W code pattern
EW_PATTERN = re.compile(r'^[EW]\d{3}$')
# Guide code pattern (e.g. E110-UNKNOWN_CANONICAL_ID)
GUIDE_PATTERN = re.compile(r'^[EW]\d{3}-[A-Z_]+$')
# Schema path pattern
SCHEMA_PATH_PATTERN = re.compile(r'\.schema\.json$')

for node in ast.walk(tree):
    # Collect make_error() call sites — look for Call nodes
    if isinstance(node, ast.Call):
        func = node.func
        func_name = None
        if isinstance(func, ast.Attribute):
            func_name = func.attr
        elif isinstance(func, ast.Name):
            func_name = func.id

        if func_name == "make_error" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                code = first_arg.value
                if EW_PATTERN.match(code):
                    if code.startswith("E"):
                        error_codes.add(code)
                    else:
                        warning_codes.add(code)

    # Collect string literals for guide refs and schema path refs
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        val = node.value
        if GUIDE_PATTERN.match(val):
            guide_refs.add(val)
        if SCHEMA_PATH_PATTERN.search(val):
            schema_path_refs.add(val)

    # Collect top-level imports
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

# Collect public function/class names at module top-level
for node in ast.iter_child_nodes(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if not node.name.startswith("_"):
            checks_exported.append(node.name)
    elif isinstance(node, ast.ClassDef):
        if not node.name.startswith("_"):
            checks_exported.append(node.name)

digest = {
    "digest_type": "digest_validator",
    "source_file": rel_path,
    "source_sha": source_sha,
    "extractor_version": extractor_version,
    "extracted_at": extracted_at,
    "payload": {
        "module_path": module_path,
        "error_codes": sorted(error_codes),
        "warning_codes": sorted(warning_codes),
        "checks_exported": checks_exported,
        "guide_refs": sorted(guide_refs),
        "schema_paths_referenced": sorted(schema_path_refs),
        "imports": sorted(imports),
    }
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
