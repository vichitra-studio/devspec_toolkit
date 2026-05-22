#!/usr/bin/env bash
# EXTRACTOR_VERSION=1
# Extract a digest_prompt JSON from a prompts/prompt_NN_*.md source file.
# Usage: extract_digest_prompt.sh <source_file> <output_path>
# Extracts ONLY structured facts via Bash/grep/awk. No LLM calls.

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

# ── step_id: derive from filename (e.g. prompt_01_capabilities.md → 01) ──────
BASENAME=$(basename "$SOURCE_FILE" .md)
STEP_ID=$(echo "$BASENAME" | sed -n 's/^prompt_\([0-9][0-9][a-c]*\)_.*/\1/p')
if [[ -z "$STEP_ID" ]]; then
  # Handle shared_expectations.md and migration prompts — not a numbered step
  STEP_ID="00"
fi

# ── schema_uri: grep for vc: URI patterns or $schema strings ─────────────────
# Prompts reference the schema URI in lines like:
#   "$schema": "vc:01-capabilities"  or  schema_uri: vc:01-capabilities
SCHEMA_URI=$(python3 -c "import re,sys; m=re.search(r'[\"\x27]\\\$schema[\"\x27]\s*:\s*[\"\x27]([^\"\x27]+)', open(sys.argv[1]).read()); print(m.group(1) if m else '')" "$SOURCE_FILE" 2>/dev/null || true)
if [[ -z "$SCHEMA_URI" ]]; then
  # Try bare vc: URI anywhere in file
  SCHEMA_URI=$(python3 -c "import re,sys; m=re.search(r'\bvc:[a-z0-9:-]+', open(sys.argv[1]).read()); print(m.group(0) if m else '')" "$SOURCE_FILE" 2>/dev/null || true)
fi
SCHEMA_URI="${SCHEMA_URI:-}"

# ── shared_expectations_required: detect the REQUIRED: directive ─────────────
if grep -q "REQUIRED.*shared_expectations" "$SOURCE_FILE" 2>/dev/null; then
  SHARED_EXPECTATIONS_REQUIRED="true"
else
  SHARED_EXPECTATIONS_REQUIRED="false"
fi

# ── section_headers: all ## level headers ────────────────────────────────────
SECTION_HEADERS_JSON=$(grep -E '^## ' "$SOURCE_FILE" | sed 's/^## //' | \
  python3 -c "import json,sys; lines=[l.rstrip() for l in sys.stdin]; print(json.dumps(lines))")

# ── inputs: .json files mentioned in Extraction Intent section ───────────────
# Extract lines between ## Extraction Intent and the next ## section
INPUTS_JSON=$(python3 - "$SOURCE_FILE" <<'PYEOF'
import re, json, sys

path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    content = f.read()

# Find Extraction Intent section (between ## Extraction Intent and next ##)
m = re.search(r'##\s+Extraction Intent.*?\n(.*?)(?=\n##\s|\Z)', content, re.DOTALL | re.IGNORECASE)
section = m.group(1) if m else content

# Extract all .json file references
refs = re.findall(r'\b\w+[\w/]*\.json\b', section)
# Deduplicate preserving order
seen = set()
unique = []
for r in refs:
    if r not in seen:
        seen.add(r)
        unique.append(r)
print(json.dumps(unique))
PYEOF
)

# ── gates: lines in Self-Audit Gate section ───────────────────────────────────
GATES_JSON=$(python3 - "$SOURCE_FILE" <<'PYEOF'
import re, json, sys

path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    content = f.read()

m = re.search(r'##\s+Self.Audit Gate.*?\n(.*?)(?=\n##\s|\Z)', content, re.DOTALL | re.IGNORECASE)
if not m:
    print('[]')
    sys.exit(0)

section = m.group(1)
# Extract bullet/checklist items
lines = [l.strip() for l in section.splitlines() if re.match(r'^\s*[-*\[]', l)]
# Strip leading - * [ ] markers
cleaned = [re.sub(r'^[-*\[x \]]+', '', l).strip() for l in lines]
cleaned = [c for c in cleaned if c]
print(json.dumps(cleaned))
PYEOF
)

# ── emergent_ambiguities_exit: check for escape-valve mentions ───────────────
if grep -qE "emergent_ambiguities|coverage_gaps" "$SOURCE_FILE" 2>/dev/null; then
  EMERGENT_AMBIGUITIES_EXIT="true"
else
  EMERGENT_AMBIGUITIES_EXIT="false"
fi

# ── anchors: HTML comment anchors ────────────────────────────────────────────
# Extract anchor names from <!-- anchor: name --> comments.
# Use python3 for the full extraction to avoid pipefail interaction with grep no-match.
ANCHORS_JSON=$(python3 -c "
import re, json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    content = f.read()
names = re.findall(r'<!--\s*anchor:\s*([a-zA-Z0-9_-]+)\s*-->', content)
print(json.dumps(sorted(set(names))))
" "$SOURCE_FILE")

# ── negative_constraints_count: lines in Negative Constraints section ─────────
NEGATIVE_CONSTRAINTS_COUNT=$(python3 - "$SOURCE_FILE" <<'PYEOF'
import re, sys

path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    content = f.read()

m = re.search(r'##\s+Negative Constraints.*?\n(.*?)(?=\n##\s|\Z)', content, re.DOTALL | re.IGNORECASE)
if not m:
    print(0)
    sys.exit(0)

section = m.group(1)
lines = [l for l in section.splitlines() if re.match(r'^\s*[-*]', l)]
print(len(lines))
PYEOF
)

# ── downstream_consumer_count: parse "feeds N downstream steps" ───────────────
DOWNSTREAM_COUNT=$(python3 -c "import re,sys; m=re.search(r'feeds\s+(\d+)\s+downstream', open(sys.argv[1]).read()); print(m.group(1) if m else '-1')" "$SOURCE_FILE" 2>/dev/null || echo "-1")
if [[ -z "$DOWNSTREAM_COUNT" ]]; then
  DOWNSTREAM_COUNT="-1"
fi

# ── Assemble output JSON ──────────────────────────────────────────────────────
# Pass computed values as environment variables to avoid JSON/Python token collision.

export DIGEST_REL_PATH="$REL_PATH"
export DIGEST_SOURCE_SHA="$SOURCE_SHA"
export DIGEST_EXTRACTOR_VERSION="$EXTRACTOR_VERSION"
export DIGEST_EXTRACTED_AT="$EXTRACTED_AT"
export DIGEST_STEP_ID="$STEP_ID"
export DIGEST_SCHEMA_URI="$SCHEMA_URI"
export DIGEST_SHARED_EXP="$SHARED_EXPECTATIONS_REQUIRED"
export DIGEST_INPUTS="$INPUTS_JSON"
export DIGEST_GATES="$GATES_JSON"
export DIGEST_EMERGENT="$EMERGENT_AMBIGUITIES_EXIT"
export DIGEST_ANCHORS="$ANCHORS_JSON"
export DIGEST_HEADERS="$SECTION_HEADERS_JSON"
export DIGEST_NEG_COUNT="$NEGATIVE_CONSTRAINTS_COUNT"
export DIGEST_DOWNSTREAM="$DOWNSTREAM_COUNT"

python3 - "$OUTPUT_PATH" <<'PYEOF'
import json, os, sys

output_path = sys.argv[1]
g = os.environ.get

digest = {
    "digest_type": "digest_prompt",
    "source_file":        g("DIGEST_REL_PATH"),
    "source_sha":         g("DIGEST_SOURCE_SHA"),
    "extractor_version":  g("DIGEST_EXTRACTOR_VERSION"),
    "extracted_at":       int(g("DIGEST_EXTRACTED_AT")),
    "payload": {
        "step_id":                       g("DIGEST_STEP_ID"),
        "shared_expectations_required":  json.loads(g("DIGEST_SHARED_EXP")),
        "inputs":                        json.loads(g("DIGEST_INPUTS")),
        "outputs":                       [],
        "gates":                         json.loads(g("DIGEST_GATES")),
        "emergent_ambiguities_exit":     json.loads(g("DIGEST_EMERGENT")),
        "anchors":                       json.loads(g("DIGEST_ANCHORS")),
        "section_headers":               json.loads(g("DIGEST_HEADERS")),
        "negative_constraints_count":    int(g("DIGEST_NEG_COUNT")),
        "downstream_consumer_count":     int(g("DIGEST_DOWNSTREAM")),
    }
}

schema_uri = g("DIGEST_SCHEMA_URI", "")
if schema_uri:
    digest["payload"]["schema_uri"] = schema_uri

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
