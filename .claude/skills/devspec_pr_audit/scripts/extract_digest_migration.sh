#!/usr/bin/env bash
# EXTRACTOR_VERSION=1.0.0
# Extract a digest_migration JSON from a migration/versioning artifact.
# Usage: extract_digest_migration.sh <source_file> <output_path>
# macOS-portable: pure Python parsing.

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
from __future__ import annotations
import json
import os
import re
import sys
from typing import Any

source_file       = sys.argv[1]
output_path       = sys.argv[2]
rel_path          = sys.argv[3]
source_sha        = sys.argv[4]
extractor_version = sys.argv[5]
extracted_at      = int(sys.argv[6])

with open(source_file, encoding="utf-8") as f:
    raw = f.read()

basename = os.path.basename(source_file).lower()
low_content = raw.lower()

# ── kind ─────────────────────────────────────────────────────────────────────
KIND_KEYWORDS = ("added", "changed", "deprecated", "removed", "fixed")
kind = "unknown"
# Filename hint first
for kw in KIND_KEYWORDS:
    if kw in basename:
        kind = kw
        break
# Fall back to heading content
if kind == "unknown":
    for m in re.finditer(r"^#{1,6}\s+([^\n]+)$", raw, re.MULTILINE):
        heading = m.group(1).strip().lower()
        for kw in KIND_KEYWORDS:
            if kw in heading:
                kind = kw
                break
        if kind != "unknown":
            break

# ── affected_entities (canonical IDs) ─────────────────────────────────────────
# Patterns: cn:..., fr-..., api-..., nfr-..., inv-..., cap-..., tc-...
ID_RE = re.compile(
    r"\b("
    r"cn:[A-Za-z0-9:_-]+"
    r"|(?:fr|api|nfr|inv|cap|tc|gate|cn)-[A-Za-z0-9][A-Za-z0-9_-]*"
    r")\b"
)
entity_set: set[str] = set()
for m in ID_RE.finditer(raw):
    entity_set.add(m.group(1))
affected_entities = sorted(entity_set)

# ── target_version ────────────────────────────────────────────────────────────
target_version: str | None = None
# Filename like v0.4.0.md or migration_v0.4.0.md or 0.4.0.md
m_fname = re.search(r"v?(\d+\.\d+\.\d+)", basename)
if m_fname:
    target_version = m_fname.group(1)
else:
    m_body = re.search(r"target\s*version\s*[:\-]\s*v?(\d+\.\d+\.\d+)", low_content)
    if m_body:
        target_version = m_body.group(1)

# ── is_breaking ───────────────────────────────────────────────────────────────
is_breaking = False
if "breaking" in basename:
    is_breaking = True
else:
    # Heading mention of "breaking"
    for m in re.finditer(r"^#{1,6}\s+([^\n]+)$", raw, re.MULTILINE):
        if "breaking" in m.group(1).lower():
            is_breaking = True
            break

payload: dict[str, Any] = {
    "migration_path": rel_path,
    "kind": kind,
    "affected_entities": affected_entities,
    "is_breaking": is_breaking,
}
if target_version is not None:
    payload["target_version"] = target_version

digest = {
    "digest_type": "digest_migration",
    "source_file": rel_path,
    "source_sha": source_sha,
    "extractor_version": extractor_version,
    "extracted_at": extracted_at,
    "payload": payload,
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
