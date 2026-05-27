#!/usr/bin/env bash
# EXTRACTOR_VERSION=1
# Extract a digest_cli JSON from tools/specdev_tools/cli.py.
# Usage: extract_digest_cli.sh <source_file> <output_path>
# Uses Python AST to find add_parser() calls and their add_argument() children.

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

python3 - "$SOURCE_FILE" "$OUTPUT_PATH" "$REL_PATH" "$SOURCE_SHA" "$EXTRACTOR_VERSION" "$EXTRACTED_AT" <<'PYEOF'
import ast
import json
import re
import sys

source_file = sys.argv[1]
output_path = sys.argv[2]
rel_path    = sys.argv[3]
source_sha  = sys.argv[4]
extractor_version = sys.argv[5]
extracted_at = int(sys.argv[6])

with open(source_file, encoding="utf-8") as f:
    source = f.read()

try:
    tree = ast.parse(source, filename=source_file)
except SyntaxError as exc:
    print(f"Error: AST parse failed for {source_file}: {exc}", file=sys.stderr)
    sys.exit(1)

# ── Strategy: find all add_parser() calls to discover subcommand names,
#    then for each parser variable assignment, find the associated
#    add_argument() calls to collect flags.
# This is a best-effort heuristic for monolithic CLI files.

# Pattern: SPECDEV_* env var references
ENV_PATTERN = re.compile(r'\bSPECDEV_[A-Z_]+\b')

commands = {}  # name -> {required_flags, accepted_flags, strips_flags, positional_args}
env_vars = set()

# Collect string constants for env var detection
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        for m in ENV_PATTERN.finditer(node.value):
            env_vars.add(m.group())

# Track variable name -> subcommand name from: varname = sub.add_parser("cmd")
parser_vars: dict[str, str] = {}

# Walk assignment statements at any nesting level
for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue
    # Look for: varname = <something>.add_parser("literal")
    if not isinstance(node.value, ast.Call):
        continue
    call = node.value
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "add_parser":
        continue
    # Extract the command name from the first positional arg
    if not call.args or not isinstance(call.args[0], ast.Constant):
        continue
    cmd_name = call.args[0].value
    if not isinstance(cmd_name, str):
        continue
    # Extract the variable name(s) from the LHS
    for target in node.targets:
        if isinstance(target, ast.Name):
            parser_vars[target.id] = cmd_name
            commands[cmd_name] = {
                "required_flags": [],
                "accepted_flags": [],
                "strips_flags": [],
                "positional_args": [],
            }

# Now find add_argument() calls on each parser variable
# Walk all Call nodes: varname.add_argument(...)
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "add_argument":
        continue
    if not isinstance(func.value, ast.Name):
        continue
    var_name = func.value.id
    if var_name not in parser_vars:
        continue
    cmd_name = parser_vars[var_name]

    if not node.args:
        continue
    first_arg = node.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        continue
    arg_str = first_arg.value

    # Check keywords for required=True
    is_required = False
    for kw in node.keywords:
        if kw.arg == "required" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            is_required = True

    if arg_str.startswith("--"):
        # Named flag
        flag = arg_str
        commands[cmd_name]["accepted_flags"].append(flag)
        if is_required:
            commands[cmd_name]["required_flags"].append(flag)
    elif not arg_str.startswith("-"):
        # Positional argument
        commands[cmd_name]["positional_args"].append(arg_str)

# Detect strips_flags for the "json" subcommand — documented in source
# We know from code analysis that "json" strips --spec-root and --git-root
if "json" in commands:
    commands["json"]["strips_flags"] = ["--spec-root", "--git-root"]

# Deduplicate and sort
command_list = []
for name, info in sorted(commands.items()):
    command_list.append({
        "name": name,
        "required_flags": sorted(set(info["required_flags"])),
        "accepted_flags": sorted(set(info["accepted_flags"])),
        "strips_flags": sorted(set(info["strips_flags"])),
        "positional_args": list(dict.fromkeys(info["positional_args"])),  # preserve order, dedup
    })

digest = {
    "digest_type": "digest_cli",
    "source_file": rel_path,
    "source_sha": source_sha,
    "extractor_version": extractor_version,
    "extracted_at": extracted_at,
    "payload": {
        "commands": command_list,
        "env_vars": sorted(env_vars),
    }
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
