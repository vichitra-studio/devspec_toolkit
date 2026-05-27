#!/usr/bin/env bash
# EXTRACTOR_VERSION=1.0.0
# Extract a digest_test JSON from a Python test module (tests/**/*.py) or a
# JSON fixture file (tests/**/*.json).
# Usage: extract_digest_test.sh <source_file> <output_path>
# macOS-portable: pure Python parsing, no GNU-only grep flags.

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
import re
import sys
from pathlib import Path

source_file       = sys.argv[1]
output_path       = sys.argv[2]
rel_path          = sys.argv[3]
source_sha        = sys.argv[4]
extractor_version = sys.argv[5]
extracted_at      = int(sys.argv[6])

with open(source_file, encoding="utf-8") as f:
    raw = f.read()

is_fixture = source_file.endswith(".json")

test_names: list[str] = []
markers: list[str] = []
imports: list[str] = []
fixtures_referenced: list[str] = []
hardcoded_paths: list[str] = []
test_count: int | None = None

# Regex for path-like literals: absolute (/foo/bar.ext) or relative with at
# least one slash AND a trailing extension. Tuned to surface candidates only.
PATH_RE = re.compile(
    r"""['"]((?:/|\.{1,2}/)[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})['"]"""
)

if not is_fixture:
    # ── Python source ────────────────────────────────────────────────────────
    # test_* function definitions
    for m in re.finditer(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", raw, re.MULTILINE):
        test_names.append(m.group(1))
    test_count = len(test_names)

    # pytest markers (capture marker name only, without arguments)
    for m in re.finditer(r"@(pytest\.mark\.[A-Za-z_][A-Za-z0-9_]*)", raw):
        markers.append(m.group(1))
    # Preserve order while deduping markers
    seen: set[str] = set()
    uniq_markers: list[str] = []
    for mk in markers:
        if mk not in seen:
            seen.add(mk)
            uniq_markers.append(mk)
    markers = uniq_markers

    # Top-level imports
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            mod = stripped[len("import "):].split(" as ")[0].split(",")[0].strip()
            if mod:
                imports.append(mod)
        elif stripped.startswith("from "):
            m = re.match(r"from\s+([A-Za-z0-9_.]+)\s+import", stripped)
            if m:
                imports.append(m.group(1))

    # Hardcoded path candidates
    for m in PATH_RE.finditer(raw):
        hardcoded_paths.append(m.group(1))

else:
    # ── JSON fixture ─────────────────────────────────────────────────────────
    # Surface fixture_path values via string-matching (schema-agnostic).
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "fixture_path" and isinstance(v, str) and v:
                    fixtures_referenced.append(v)
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if data is not None:
        walk(data)

    # Path-like literal scan over the raw text (catches both keys and values)
    for m in PATH_RE.finditer(raw):
        hardcoded_paths.append(m.group(1))

# Dedupe imports / fixtures / hardcoded_paths preserving order
def dedupe(seq: list[str]) -> list[str]:
    out: list[str] = []
    seen_local: set[str] = set()
    for item in seq:
        if item not in seen_local:
            seen_local.add(item)
            out.append(item)
    return out

imports             = dedupe(imports)
fixtures_referenced = dedupe(fixtures_referenced)
hardcoded_paths     = dedupe(hardcoded_paths)

digest = {
    "digest_type": "digest_test",
    "source_file": rel_path,
    "source_sha": source_sha,
    "extractor_version": extractor_version,
    "extracted_at": extracted_at,
    "payload": {
        "test_file_path": rel_path,
        "test_count": test_count,
        "test_names": test_names,
        "markers": markers,
        "imports": imports,
        "fixtures_referenced": fixtures_referenced,
        "hardcoded_paths": hardcoded_paths,
        "is_fixture": is_fixture,
    },
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
