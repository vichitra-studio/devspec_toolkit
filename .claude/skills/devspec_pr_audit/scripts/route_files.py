#!/usr/bin/env python3
"""Route diff files to slices defined in slices.yaml.

Input (stdin or --diff-file): newline-separated file paths.
Output (stdout): JSON {routing: {slice: [paths]}, unrouted: [paths],
                       excluded: [paths], slices_in_scope: [...]}

`**` in globs matches zero or more path components (including empty),
unlike pathlib.PurePath.match which is unreliable for nested patterns.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML not installed (pip install pyyaml)\n")
    sys.exit(2)


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Convert a slices.yaml glob to a regex.

    Semantics:
      `**`  → any sequence of characters including '/'
      `*`   → any sequence of characters NOT including '/'
      `?`   → single non-'/' character
      other → literal
    """
    out: list[str] = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if c == "*" and i + 1 < len(glob) and glob[i + 1] == "*":
            # `**/` or `**` — consume optional trailing slash
            out.append(".*")
            i += 2
            if i < len(glob) and glob[i] == "/":
                i += 1
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in ".+(){}|^$\\":
            out.append(re.escape(c))
            i += 1
        else:
            out.append(c)
            i += 1
    return re.compile("^" + "".join(out) + "$")


def load_slices(path: Path) -> tuple[list[str], list[dict]]:
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict):
        raise SystemExit(f"slices.yaml must be a top-level mapping; got {type(doc).__name__}")
    exclusions = doc.get("exclusions", []) or []
    slices = doc.get("slices", []) or []
    if not isinstance(exclusions, list) or not isinstance(slices, list):
        raise SystemExit("slices.yaml: exclusions and slices must be lists")
    return exclusions, slices


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slices", default=".claude/skills/devspec_pr_audit/slices.yaml")
    p.add_argument("--diff-file", help="File containing one path per line (default stdin)")
    p.add_argument("--extra-exclude", action="append", default=[],
                   help="Additional exclusion glob; may repeat")
    args = p.parse_args()

    exclusions, slices = load_slices(Path(args.slices))
    excl_pats = [glob_to_regex(g) for g in exclusions + args.extra_exclude]

    slice_pats: list[tuple[str, list[re.Pattern[str]]]] = []
    for s in slices:
        if not isinstance(s, dict) or "name" not in s:
            continue
        pats = [glob_to_regex(g) for g in s.get("globs", [])]
        slice_pats.append((s["name"], pats))

    if args.diff_file:
        lines = Path(args.diff_file).read_text().splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    files = [l.strip() for l in lines if l.strip()]

    routing: dict[str, list[str]] = {name: [] for name, _ in slice_pats}
    unrouted: list[str] = []
    excluded: list[str] = []

    for f in files:
        if any(p.match(f) for p in excl_pats):
            excluded.append(f)
            continue
        hit_any = False
        for name, pats in slice_pats:
            if any(p.match(f) for p in pats):
                routing[name].append(f)
                hit_any = True
        if not hit_any:
            unrouted.append(f)

    result = {
        "routing": routing,
        "unrouted": sorted(unrouted),
        "excluded": sorted(excluded),
        "slices_in_scope": sorted([n for n, fs in routing.items() if fs]),
        "counts": {
            "total": len(files),
            "excluded": len(excluded),
            "unrouted": len(unrouted),
            "routed_pairs": sum(len(v) for v in routing.values()),
        },
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
