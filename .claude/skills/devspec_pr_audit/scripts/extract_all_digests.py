#!/usr/bin/env python3
"""Dispatch per-file digest extraction by type.

Reads routing.json, maps each routed file to a digest type via the rules below,
computes `docs/audit/runs/<run-id>/digests/<type>/<slug>.json`, and invokes the
matching extractor script.

Type rules (first match wins; deleted source files are skipped with a log line):
  schema     — *.schema.json under canon/ or schema/
  prompt     — *.md under prompts/ or migration_prompts/
  validator  — *.py under tools/specdev_tools/{validation,validators,canonical,
                                              analysis,registry,generation}/
  cli        — tools/specdev_tools/cli.py or *.py under tools/specdev_tools/
               {guides,context}/ or *.yaml under tools/specdev_tools/guides/
  canon      — canon/**/*.{json,md} excluding *.schema.json (handled by schema)
  changelog  — CHANGELOG.md or changelog/unreleased.md or changelog/v*.md/yaml
               (release-changelog artifacts; per-migration files route to
               `migration` below).
  migration  — changelog/migrations/** or other migration_versioning slice
               files that are not a release-changelog artifact.
  test       — *.py or *.json under tests/
  doc        — *.md under docs/, or CLAUDE.md, or **/SHARED_*.md / SKILL.md
               (host_integration slice).

Files that match no rule are reported on stderr and skipped.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent


# Slices (per routing.json) used to disambiguate doc / migration when the file
# extension alone is insufficient (e.g. a .md inside migration_versioning that
# is not a release-changelog must route to migration, not doc).
_DOC_SLICES = {"docs", "host_integration"}
_MIGRATION_SLICES = {"migration_versioning"}


def _is_release_changelog(p: str) -> bool:
    """Return True for top-level release / unreleased changelog artifacts."""
    if p == "CHANGELOG.md":
        return True
    if p.startswith("changelog/migrations/"):
        return False
    if p.startswith("changelog/") and (p.endswith(".md") or p.endswith(".yaml")):
        return True
    return False


def digest_type(path: str, slices: set[str] | None = None) -> str | None:
    """Classify a single routed file into a digest type.

    `slices` is the set of routing.json slice names this file belongs to.
    When supplied, slice membership disambiguates ambiguous paths (e.g. a
    markdown file routed under migration_versioning vs docs).
    """
    p = path
    s: set[str] = slices or set()

    if p.endswith(".schema.json") and (p.startswith("schema/") or p.startswith("canon/")):
        return "schema"
    if (p.startswith("prompts/") or p.startswith("migration_prompts/")) and p.endswith(".md"):
        return "prompt"
    if p.endswith(".py"):
        # Test sources take precedence over validator/cli classification.
        if p.startswith("tests/"):
            return "test"
        validator_dirs = ("validation/", "validators/", "canonical/", "analysis/",
                          "registry/", "generation/")
        if any(f"tools/specdev_tools/{d}" in p for d in validator_dirs):
            return "validator"
        if p == "tools/specdev_tools/cli.py":
            return "cli"
        if p.startswith("tools/specdev_tools/context/"):
            return "cli"
    if p.startswith("tests/") and (p.endswith(".py") or p.endswith(".json")):
        return "test"
    if p.startswith("canon/") and p.endswith(".json"):
        return "canon"

    # Migration vs changelog: migrations live under changelog/migrations/, and
    # any non-changelog file routed via migration_versioning is also migration.
    if p.startswith("changelog/migrations/"):
        return "migration"
    if _is_release_changelog(p):
        return "changelog"
    if _MIGRATION_SLICES & s and not _is_release_changelog(p):
        return "migration"

    # Documentation markdown: explicit paths first, then slice membership.
    if p.endswith(".md"):
        basename = p.rsplit("/", 1)[-1]
        if (
            p == "CLAUDE.md"
            or p.endswith("/CLAUDE.md")
            or p.startswith("docs/")
            or basename.startswith("SHARED_")
            or basename == "SKILL.md"
            or (_DOC_SLICES & s)
        ):
            return "doc"
    return None


def slug(path: str) -> str:
    """Filesystem-safe per-file identifier (path with / → __ + 8-char sha)."""
    flat = re.sub(r"[^A-Za-z0-9._-]", "_", path)
    if len(flat) > 80:
        h = hashlib.sha1(path.encode()).hexdigest()[:8]
        flat = flat[:60] + "_" + h
    return flat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routing", required=True, help="Path to routing.json")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--run-dir", required=True, help="docs/audit/runs/<run-id>")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    routing = json.loads(Path(args.routing).read_text())
    # Build a reverse map: file path -> set of slice names it appears in.
    file_slices: dict[str, set[str]] = {}
    for slice_name, files in routing["routing"].items():
        for f in files:
            file_slices.setdefault(f, set()).add(slice_name)
    seen: set[str] = set(file_slices.keys())

    run_dir = Path(args.run_dir)
    counts: dict[str, int] = {"schema": 0, "prompt": 0, "validator": 0, "cli": 0,
                              "canon": 0, "changelog": 0, "test": 0, "doc": 0,
                              "migration": 0, "untyped": 0, "missing_source": 0,
                              "extractor_failed": 0}

    failures: list[str] = []
    for path in sorted(seen):
        t = digest_type(path, file_slices.get(path))
        if t is None:
            counts["untyped"] += 1
            continue
        if not Path(path).exists():
            # Deleted file — source no longer present in working tree
            counts["missing_source"] += 1
            continue
        out = run_dir / "digests" / t / f"{slug(path)}.json"
        if args.dry_run:
            counts[t] += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        extractor = SCRIPTS_DIR / f"extract_digest_{t}.sh"
        r = subprocess.run(["bash", str(extractor), path, str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            counts["extractor_failed"] += 1
            failures.append(f"{path} → {t}: {r.stderr.strip()[:160]}")
            continue
        counts[t] += 1

    print(json.dumps({"counts": counts, "failures": failures[:20],
                      "failure_count": len(failures)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
