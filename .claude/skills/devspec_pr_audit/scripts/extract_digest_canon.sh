#!/usr/bin/env bash
# EXTRACTOR_VERSION=1
# Extract a digest_canon JSON from a canon/**/*.json source file.
# Usage: extract_digest_canon.sh <source_file> <output_path>

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

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SOURCE_FILE" 2>/dev/null; then
  echo "Error: source file is not valid JSON: $SOURCE_FILE" >&2
  exit 1
fi

SOURCE_SHA=$(git hash-object "$SOURCE_FILE")
EXTRACTED_AT=$(date +%s)
REL_PATH="${SOURCE_FILE#./}"

# ── registry_version ─────────────────────────────────────────────────────────
REGISTRY_VERSION=$(jq -r '.registry_version // ""' "$SOURCE_FILE")

# ── ids: entries[*].id ────────────────────────────────────────────────────────
IDS_JSON=$(jq -c '[.entries[]?.id | select(. != null) | strings] | sort | unique' "$SOURCE_FILE")

# ── owners: flatten entries[*].owners[] ───────────────────────────────────────
OWNERS_JSON=$(jq -c '[.entries[]?.owners[]? | strings] | sort | unique' "$SOURCE_FILE")

# ── aliases: build alias → canonical_id map from entries[*].aliases[] ─────────
# Each entry has id and aliases array. aliases is alias → id (lookup direction).
ALIASES_JSON=$(jq -c '
  [.entries[]? | . as $entry | (.aliases // [])[] | {key: ., value: $entry.id}]
  | from_entries
' "$SOURCE_FILE")

# ── kinds ─────────────────────────────────────────────────────────────────────
KINDS_JSON=$(jq -c '[.entries[]?.kind | select(. != null) | strings] | sort | unique' "$SOURCE_FILE")

# ── statuses ──────────────────────────────────────────────────────────────────
STATUSES_JSON=$(jq -c '[.entries[]?.status | select(. != null) | strings] | sort | unique' "$SOURCE_FILE")

# ── deprecated_ids ────────────────────────────────────────────────────────────
DEPRECATED_IDS_JSON=$(jq -c '[.entries[]? | select(.status == "deprecated") | .id] | sort' "$SOURCE_FILE")

# ── entry_count ───────────────────────────────────────────────────────────────
ENTRY_COUNT=$(jq -r '(.entries // []) | length' "$SOURCE_FILE")

# ── namespace: longest common prefix of all IDs ───────────────────────────────
NAMESPACE=$(python3 - "$SOURCE_FILE" <<'PYEOF'
import json, sys, os

data = json.load(open(sys.argv[1]))
ids = [e.get("id","") for e in data.get("entries", []) if e.get("id")]
if not ids:
    print("")
    sys.exit(0)

# Find common prefix by splitting on ":"
parts_list = [i.split(":") for i in ids]
common = []
for parts in zip(*parts_list):
    if len(set(parts)) == 1:
        common.append(parts[0])
    else:
        break

if len(common) >= 2:
    # e.g. ["cn", "core"] -> "cn:core:"
    print(":".join(common) + ":")
else:
    print("")
PYEOF
)

# ── Assemble output JSON ──────────────────────────────────────────────────────
export DIGEST_REL_PATH="$REL_PATH"
export DIGEST_SOURCE_SHA="$SOURCE_SHA"
export DIGEST_EXTRACTOR_VERSION="$EXTRACTOR_VERSION"
export DIGEST_EXTRACTED_AT="$EXTRACTED_AT"
export DIGEST_NAMESPACE="$NAMESPACE"
export DIGEST_IDS="$IDS_JSON"
export DIGEST_OWNERS="$OWNERS_JSON"
export DIGEST_ALIASES="$ALIASES_JSON"
export DIGEST_KINDS="$KINDS_JSON"
export DIGEST_STATUSES="$STATUSES_JSON"
export DIGEST_DEPRECATED="$DEPRECATED_IDS_JSON"
export DIGEST_ENTRY_COUNT="$ENTRY_COUNT"
export DIGEST_REGISTRY_VERSION="$REGISTRY_VERSION"

python3 - "$OUTPUT_PATH" <<'PYEOF'
import json, os, sys

output_path = sys.argv[1]
g = os.environ.get

digest = {
    "digest_type": "digest_canon",
    "source_file":        g("DIGEST_REL_PATH"),
    "source_sha":         g("DIGEST_SOURCE_SHA"),
    "extractor_version":  g("DIGEST_EXTRACTOR_VERSION"),
    "extracted_at":       int(g("DIGEST_EXTRACTED_AT")),
    "payload": {
        "namespace":      g("DIGEST_NAMESPACE", ""),
        "ids":            json.loads(g("DIGEST_IDS")),
        "owners":         json.loads(g("DIGEST_OWNERS")),
        "aliases":        json.loads(g("DIGEST_ALIASES")),
        "kinds":          json.loads(g("DIGEST_KINDS")),
        "statuses":       json.loads(g("DIGEST_STATUSES")),
        "deprecated_ids": json.loads(g("DIGEST_DEPRECATED")),
        "entry_count":    int(g("DIGEST_ENTRY_COUNT")),
    }
}

registry_version = g("DIGEST_REGISTRY_VERSION", "")
if registry_version:
    digest["payload"]["registry_version"] = registry_version

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
