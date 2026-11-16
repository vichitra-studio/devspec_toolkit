#!/usr/bin/env python3
"""Write the frozen schema path inventory of a release commit.

The inventory is the baseline of the schema-change rows: ``specdev``'s schema changes are
checked against it. It is produced once (``--ref 55de053``, the 1.1.1 release merge) and
committed; the schemas of the commit are exported with ``git archive`` into a temporary
directory, so the working tree is never touched.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from specdev_tools.registry.schema_paths import flatten_schema_dir  # noqa: E402

DEFAULT_OUT = ROOT / "tests" / "fixtures" / "schema_baseline" / "paths_1.1.1.json"


def export_schemas(ref: str, dest: Path) -> None:
    """Extract the ``schema/`` tree of commit *ref* into *dest* (read-only git)."""
    archive = subprocess.run(
        ["git", "-C", str(ROOT), "archive", ref, "schema"], check=True, capture_output=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)


def build_baseline(ref: str) -> dict:
    """Return ``{"ref": ref, "schemas": {name: {path: {"type", "ref", "enum"}}}}`` for commit *ref*."""
    with tempfile.TemporaryDirectory() as tmp:
        export_schemas(ref, Path(tmp))
        flat = flatten_schema_dir(Path(tmp) / "schema")
    schemas = {
        name: {path: {"type": info.type, "ref": info.ref, "enum": list(info.enum) if info.enum is not None else None} for path, info in sorted(paths.items())}
        for name, paths in sorted(flat.items())
    }
    return {"ref": ref, "schemas": schemas}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: write the baseline of ``--ref`` to ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="commit to read the schemas of")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSON file")
    args = parser.parse_args(argv)
    baseline = build_baseline(args.ref)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(baseline, indent=1, sort_keys=False) + "\n")
    print(f"wrote {args.out} ({sum(len(p) for p in baseline['schemas'].values())} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
