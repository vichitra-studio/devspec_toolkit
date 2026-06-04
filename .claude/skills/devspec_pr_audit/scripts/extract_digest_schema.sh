#!/usr/bin/env bash
# EXTRACTOR_VERSION=1
# Extract a digest_schema JSON from a *.schema.json source file.
# Usage: extract_digest_schema.sh <source_file> <output_path>
# <source_file> is relative to the toolkit root (or an absolute path).
# <output_path> is the full path where the digest JSON will be written.

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

# Validate that it parses as JSON before proceeding
if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SOURCE_FILE" 2>/dev/null; then
  echo "Error: source file is not valid JSON: $SOURCE_FILE" >&2
  exit 1
fi

SOURCE_SHA=$(git hash-object "$SOURCE_FILE")
EXTRACTED_AT=$(date +%s)

# Compute relative path from toolkit root (strip leading ./ if present)
REL_PATH="${SOURCE_FILE#./}"

# ── Extract payload fields ────────────────────────────────────────────────────

# schema_id: value of $id field
SCHEMA_ID=$(jq -r '.["$id"] // ""' "$SOURCE_FILE")

# schema_uri: value of $schema field
SCHEMA_URI=$(jq -r '.["$schema"] // ""' "$SOURCE_FILE")

# title
TITLE=$(jq -r '.title // ""' "$SOURCE_FILE")

# required[] at root level
REQUIRED_JSON=$(jq -c '[.required[]? | strings] | unique' "$SOURCE_FILE" 2>/dev/null || echo '[]')

# All property keys at root (from .properties object)
ALL_PROP_KEYS=$(jq -c '[.properties // {} | keys[]] | sort' "$SOURCE_FILE" 2>/dev/null || echo '[]')

# optional = all_keys - required
OPTIONAL_JSON=$(python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
required = set(data.get('required', []))
all_props = list((data.get('properties') or {}).keys())
optional = [k for k in all_props if k not in required]
print(json.dumps(sorted(optional)))
" "$SOURCE_FILE")

# additional_properties_at_root: false means the root is CLOSED, i.e.
# additionalProperties == false OR unevaluatedProperties == false.
# Only report true (open) when neither closure mechanism is present.
ADDL_PROPS_AT_ROOT=$(python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
ap = data.get('additionalProperties', '__unset__')
up = data.get('unevaluatedProperties', '__unset__')
closed = (ap is False) or (up is False)
print('false' if closed else 'true')
" "$SOURCE_FILE")

# refs[]: all \$ref values found recursively anywhere in the schema
REFS_JSON=$(jq -c '[ .. | objects | .["$ref"]? // empty ] | unique | sort' "$SOURCE_FILE" 2>/dev/null || echo '[]')

# enums: walk schema looking for enum arrays, recording dot-path → values
# Strategy: use python for recursive traversal
ENUMS_JSON=$(python3 -c "
import json, sys

def walk(node, path, out):
    if isinstance(node, dict):
        if 'enum' in node and isinstance(node['enum'], list):
            out[path or 'root'] = [str(v) for v in node['enum']]
        for k, v in node.items():
            sep = '.' if path else ''
            walk(v, path + sep + k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + '[' + str(i) + ']', out)

data = json.load(open(sys.argv[1]))
result = {}
walk(data, '', result)
# Remove 'root' key if trivially empty
print(json.dumps(result))
" "$SOURCE_FILE")

# patterns: walk schema looking for 'pattern' strings
PATTERNS_JSON=$(python3 -c "
import json, sys

def walk(node, path, out):
    if isinstance(node, dict):
        if 'pattern' in node and isinstance(node['pattern'], str):
            out[path or 'root'] = node['pattern']
        for k, v in node.items():
            sep = '.' if path else ''
            walk(v, path + sep + k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + '[' + str(i) + ']', out)

data = json.load(open(sys.argv[1]))
result = {}
walk(data, '', result)
print(json.dumps(result))
" "$SOURCE_FILE")

# has_definitions: does the schema have a non-empty $defs or definitions block?
HAS_DEFS=$(jq -r '
  if ((.["$defs"] // {} | length) > 0) or ((.definitions // {} | length) > 0)
  then "true" else "false" end
' "$SOURCE_FILE")

# def_names: keys of $defs (or definitions)
DEF_NAMES=$(jq -c '
  (.["$defs"] // .definitions // {}) | keys
' "$SOURCE_FILE" 2>/dev/null || echo '[]')

# ── Assemble output JSON ──────────────────────────────────────────────────────
# Pass all computed values as environment variables so Python can read them
# without JSON/Python token confusion in heredoc expansion.

export DIGEST_REL_PATH="$REL_PATH"
export DIGEST_SOURCE_SHA="$SOURCE_SHA"
export DIGEST_EXTRACTOR_VERSION="$EXTRACTOR_VERSION"
export DIGEST_EXTRACTED_AT="$EXTRACTED_AT"
export DIGEST_SCHEMA_ID="$SCHEMA_ID"
export DIGEST_SCHEMA_URI="$SCHEMA_URI"
export DIGEST_TITLE="$TITLE"
export DIGEST_REQUIRED="$REQUIRED_JSON"
export DIGEST_OPTIONAL="$OPTIONAL_JSON"
export DIGEST_ADDL_PROPS="$ADDL_PROPS_AT_ROOT"
export DIGEST_REFS="$REFS_JSON"
export DIGEST_ENUMS="$ENUMS_JSON"
export DIGEST_PATTERNS="$PATTERNS_JSON"
export DIGEST_HAS_DEFS="$HAS_DEFS"
export DIGEST_DEF_NAMES="$DEF_NAMES"

python3 - "$OUTPUT_PATH" <<'PYEOF'
import json, os, sys

output_path = sys.argv[1]
g = os.environ.get

digest = {
    "digest_type": "digest_schema",
    "source_file":        g("DIGEST_REL_PATH"),
    "source_sha":         g("DIGEST_SOURCE_SHA"),
    "extractor_version":  g("DIGEST_EXTRACTOR_VERSION"),
    "extracted_at":       int(g("DIGEST_EXTRACTED_AT")),
    "payload": {
        "schema_id":                  g("DIGEST_SCHEMA_ID"),
        "required":                   json.loads(g("DIGEST_REQUIRED")),
        "optional":                   json.loads(g("DIGEST_OPTIONAL")),
        "additional_properties_at_root": json.loads(g("DIGEST_ADDL_PROPS")),
        "refs":                       json.loads(g("DIGEST_REFS")),
        "enums":                      json.loads(g("DIGEST_ENUMS")),
        "patterns":                   json.loads(g("DIGEST_PATTERNS")),
        "has_definitions":            json.loads(g("DIGEST_HAS_DEFS")),
        "def_names":                  json.loads(g("DIGEST_DEF_NAMES")),
    }
}

schema_uri = g("DIGEST_SCHEMA_URI", "")
title = g("DIGEST_TITLE", "")
if schema_uri:
    digest["payload"]["schema_uri"] = schema_uri
if title:
    digest["payload"]["title"] = title

# Remove optional fields that are empty (cleaner digest)
for key in ("enums", "patterns", "def_names"):
    val = digest["payload"].get(key)
    if val is not None and len(val) == 0:
        del digest["payload"][key]

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
