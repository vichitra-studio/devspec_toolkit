#!/usr/bin/env bash
# EXTRACTOR_VERSION=1.0.5
# Extract a digest_changelog JSON from CHANGELOG.md or changelog/*.md.
# Usage: extract_digest_changelog.sh <source_file> <output_path>
# Extracts ONLY structured facts (version labels, section headers, change-lines).
# No free-form prose summarisation.

set -euo pipefail

EXTRACTOR_VERSION="1.0.5"

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

# ── All extraction via Python (structured markdown parsing) ──────────────────
python3 - "$SOURCE_FILE" "$OUTPUT_PATH" "$REL_PATH" "$SOURCE_SHA" "$EXTRACTOR_VERSION" "$EXTRACTED_AT" <<'PYEOF'
import re
import json
import sys
from pathlib import Path

source_file  = sys.argv[1]
output_path  = sys.argv[2]
rel_path     = sys.argv[3]
source_sha   = sys.argv[4]
extractor_version = sys.argv[5]
extracted_at = int(sys.argv[6])

with open(source_file, encoding="utf-8") as f:
    content = f.read()

# ── Detect if this is an unreleased file ─────────────────────────────────────
basename = Path(source_file).name.lower()
is_unreleased_file = "unreleased" in basename

# ── Find the primary version section ─────────────────────────────────────────
# Handles multiple heading styles:
#   # [Unreleased]         (H1 — used in unreleased.md)
#   ## [0.3.0] — 2026-02-26  (H2 with date — used in vX.Y.Z.md)
#   ## [Unreleased]           (H2 — used in some changelogs)
# Check H1 first (most specific for standalone changelog files), then H2.

version_label = ""
release_date = ""

# H1 version heading: # [Label] or # Label — YYYY-MM-DD
h1_m = re.search(
    r'^#\s+(?:\[([^\]]+)\]|(\S[^\n]*?))\s*(?:—|-|–)?\s*(\d{4}-\d{2}-\d{2})?$',
    content,
    re.MULTILINE,
)
if h1_m:
    version_label = (h1_m.group(1) or h1_m.group(2) or "").strip()
    release_date = h1_m.group(3) or ""

# H2 version heading: ## [Label] or ## Label — YYYY-MM-DD
if not version_label:
    h2_m = re.search(
        r'^##\s+(?:\[([^\]]+)\]|([^\n]+?))\s*(?:—|-|–)?\s*(\d{4}-\d{2}-\d{2})?$',
        content,
        re.MULTILINE,
    )
    if h2_m:
        version_label = (h2_m.group(1) or h2_m.group(2) or "").strip()
        release_date = h2_m.group(3) or ""

if not version_label:
    version_label = "Unknown"

is_unreleased = is_unreleased_file or version_label.lower() in ("unreleased", "[unreleased]")

# ── Extract section headers (### level) ──────────────────────────────────────
section_headers = re.findall(r'^###\s+(.+)$', content, re.MULTILINE)
section_headers = [h.strip() for h in section_headers]

# ── Extract change lines per section category ─────────────────────────────────
# Strategy: scan through ## and ### headers and collect bullet lines until the
# next heading of equal-or-higher level.  This handles changelogs that use ##
# for top-level category sections (e.g. "## Breaking Changes", "## Added") as
# well as those that use ### for nested sub-sections.
#
# Root cause of bin5-f09: the previous implementation only split on ### (H3),
# so ## Breaking Changes (H2) in unreleased.md was never matched.

CATEGORY_MAP = {
    "breaking": ["breaking changes", "breaking"],
    "added": ["added"],
    "changed": ["changed"],
    "removed": ["removed"],
    "deprecated": ["deprecated"],
    "fixed": ["fixed", "security"],
}

# Strip fenced code blocks before splitting so that ## / ### inside code
# blocks are not treated as section headings (P1-1).
# Handles both backtick (```) and tilde (~~~) fences (P2-6).
stripped_for_split = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
stripped_for_split = re.sub(r'~~~.*?~~~', '', stripped_for_split, flags=re.DOTALL)
# P2-7: Handle dangling unclosed fences — count markers; if odd, strip from
# the last opening fence marker to EOF.
for fence_marker in ('```', '~~~'):
    fence_occurrences = re.findall(r'^' + re.escape(fence_marker), stripped_for_split, flags=re.MULTILINE)
    if len(fence_occurrences) % 2 == 1:
        last_idx = stripped_for_split.rfind(fence_marker)
        stripped_for_split = stripped_for_split[:last_idx]

# Split on both ## and ### headings (captures the hashes + text as one token)
blocks = re.split(r'^(#{2,3}\s+.+)$', stripped_for_split, flags=re.MULTILINE)

categorized: dict[str, list[str]] = {k: [] for k in CATEGORY_MAP}

# blocks alternates: [pre-text, heading, body, heading, body, ...]
i = 1
while i < len(blocks) - 1:
    raw_heading = blocks[i].strip()
    # Count leading '#' to determine heading level (2 or 3)
    heading_level = len(raw_heading) - len(raw_heading.lstrip("#"))
    heading = raw_heading.lstrip("#").strip().lower()
    body = blocks[i + 1] if (i + 1) < len(blocks) else ""

    # Determine category — only if the heading text itself matches a keyword.
    # Version headings like "## [0.3.0] — 2026-02-26" or "## Summary" won't
    # match any CATEGORY_MAP keyword, so they are safely skipped.
    matched_category = None
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in heading for kw in keywords):
            matched_category = cat
            break

    if matched_category:
        # Collect bullet lines from body; stop at any heading of same or higher
        # level so we don't bleed into sibling/parent sections.
        for line in body.splitlines():
            stripped = line.strip()
            # Stop if we hit a heading marker at the same or higher level.
            # Use raw `line` (not `stripped`) so indented "  ## Note" in
            # bullet prose does NOT trigger a false heading-stop (P2 fix).
            _hm = re.match(r'^(#+)\s', line)
            if _hm:
                h_level = len(_hm.group(1))
                if h_level <= heading_level:
                    break
                continue
            # P1-2 / P2-4 / P2-5: Only count top-level bullets (no leading
            # whitespace).  Match against `line` (not `stripped`) so indented
            # sub-items are excluded.  Pattern covers -, *, + bullets and both
            # `1.` and `1)` ordered-list syntax.
            m = re.match(r'^([-*+]|\d+[.)])\s+', line)
            if m:
                # Take first line of multi-line bullet (enough for structural check)
                # Strip bullet/number prefix, then preserve inner markdown as-is (P2-2, P2-3).
                entry = re.sub(r'^(?:[-*+]+|\d+[.)])\s+', '', line).strip()
                if entry:
                    categorized[matched_category].append(entry)

    i += 2

total_entries = sum(len(v) for v in categorized.values())

digest = {
    "digest_type": "digest_changelog",
    "source_file": rel_path,
    "source_sha": source_sha,
    "extractor_version": extractor_version,
    "extracted_at": extracted_at,
    "payload": {
        "version_label": version_label,
        "release_date": release_date,
        "is_unreleased": is_unreleased,
        "breaking": categorized["breaking"],
        "added": categorized["added"],
        "changed": categorized["changed"],
        "removed": categorized["removed"],
        "deprecated": categorized["deprecated"],
        "fixed": categorized["fixed"],
        "section_headers": section_headers,
        "total_entries": total_entries,
        "has_breaking_changes": len(categorized["breaking"]) > 0,
    }
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(digest, f, indent=2)

print(f"Wrote digest to {output_path}")
PYEOF
