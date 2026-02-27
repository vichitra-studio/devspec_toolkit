"""Strip generation_quality to assumptions-only.

Usage:
    python -m specdev_tools.migration.scripts.strip_generation_quality <directory>

Walks all .json files in <directory> (recursively). For each file containing
a "generation_quality" dict, replaces it with {"assumptions": <existing>} where
<existing> is the current assumptions array (or [] if absent).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def migrate_file(path: Path) -> bool:
    """Migrate a single JSON file. Returns True if modified."""
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return False

    if not isinstance(data, dict):
        return False

    gq = data.get("generation_quality")
    if not isinstance(gq, dict):
        return False

    # Already migrated?
    if set(gq.keys()) == {"assumptions"}:
        return False

    assumptions = gq.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = []

    data["generation_quality"] = {"assumptions": assumptions}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_directory(directory: str) -> int:
    """Migrate all JSON files in directory. Returns count of modified files."""
    root = Path(directory)
    count = 0
    for path in sorted(root.rglob("*.json")):
        if migrate_file(path):
            print(f"  migrated: {path}")
            count += 1
    return count


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory>", file=sys.stderr)
        sys.exit(1)
    directory = sys.argv[1]
    count = migrate_directory(directory)
    print(f"Migrated {count} file(s).")


if __name__ == "__main__":
    main()
