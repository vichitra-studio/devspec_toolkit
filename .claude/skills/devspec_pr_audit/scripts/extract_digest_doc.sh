#!/usr/bin/env bash
# EXTRACTOR_VERSION=1.0.0
# Extract a digest_doc JSON from a documentation markdown file.
# Usage: extract_digest_doc.sh <source_file> <output_path>
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

# ── Frontmatter (optional) ────────────────────────────────────────────────────
frontmatter: dict[str, Any] | None = None
body = raw
fm_match = re.match(r"^---\n(.*?)\n---\n", raw, re.DOTALL)
if fm_match:
    fm_text = fm_match.group(1)
    body = raw[fm_match.end():]
    # Minimal YAML parser: only top-level "key: value" lines (string values).
    # We avoid pulling in PyYAML to keep the toolkit dependency surface flat.
    parsed: dict[str, Any] = {}
    ok = True
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if not m:
            ok = False
            break
        key, val = m.group(1), m.group(2).strip()
        # Strip surrounding quotes if present
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        parsed[key] = val
    if ok and parsed:
        frontmatter = parsed

# ── Strip fenced code blocks before heading / link scanning ──────────────────
# Track code blocks (language + line_count) before stripping.
code_blocks: list[dict[str, Any]] = []
fence_re = re.compile(r"^(```|~~~)([^\n`~]*)\n(.*?)(?:^\1\s*$)", re.DOTALL | re.MULTILINE)
stripped = body
# Iterate by scanning rather than re.sub, so we can collect metadata cleanly.
positions: list[tuple[int, int]] = []
for m in fence_re.finditer(body):
    info = m.group(2).strip()
    inner = m.group(3)
    # line_count counts non-fence body lines
    if inner == "":
        line_count = 0
    else:
        # Trailing newline before closing fence is part of body; do not double count.
        line_count = inner.count("\n")
        if not inner.endswith("\n"):
            line_count += 1
    code_blocks.append({"language": info, "line_count": line_count})
    positions.append((m.start(), m.end()))

# Build stripped version (replace fenced blocks with blank lines so line refs stay
# meaningful, though we don't track lines downstream).
if positions:
    parts: list[str] = []
    last = 0
    for start, end in positions:
        parts.append(body[last:start])
        last = end
    parts.append(body[last:])
    stripped = "".join(parts)

# ── Headings (skip lines inside code blocks; stripped already excludes them) ─
headings: list[dict[str, Any]] = []
for line in stripped.splitlines():
    m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
    if m:
        depth = len(m.group(1))
        text = m.group(2).strip()
        if text:
            headings.append({"depth": depth, "text": text})

# ── Referenced specdev commands ──────────────────────────────────────────────
# Match `specdev <subcommand>` where subcommand is the next token.
cmd_set: set[str] = set()
for m in re.finditer(r"\bspecdev\s+([a-z][a-z0-9-]*)", raw):
    cmd = m.group(1)
    # Filter out obvious non-subcommand tokens (flags etc.)
    if cmd and not cmd.startswith("-"):
        cmd_set.add(cmd)
referenced_commands = sorted(cmd_set)

# ── Referenced file paths from markdown links ────────────────────────────────
# Pattern: [label](target).  target is treated as a file path when it has a
# slash or a recognised file extension, and is NOT an http(s)/mailto URL.
file_set: set[str] = set()
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}(?:#.*)?$")
for m in LINK_RE.finditer(raw):
    target = m.group(1)
    if not target:
        continue
    low = target.lower()
    if low.startswith(("http://", "https://", "mailto:", "ftp://")):
        continue
    # Strip URL fragment for path check
    path_only = target.split("#", 1)[0]
    if "/" in path_only or EXT_RE.search(path_only):
        file_set.add(target)
referenced_files = sorted(file_set)

payload: dict[str, Any] = {
    "doc_path": rel_path,
    "headings": headings,
    "code_blocks": code_blocks,
    "referenced_commands": referenced_commands,
    "referenced_files": referenced_files,
}
if frontmatter is not None:
    payload["frontmatter"] = frontmatter

digest = {
    "digest_type": "digest_doc",
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
