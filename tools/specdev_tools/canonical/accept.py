"""canon-accept: Promote canonical_proposals from a spec file to canon/manifest.json.

Reads the ``canonical_proposals`` array from a spec JSON file and appends any
new proposals (as fully-formed canon entries) to ``canon/manifest.json``.
Proposals whose generated ID already exists in the manifest are skipped.

Entry format mirrors the existing manifest entries:

    {
        "id": "<namespace><temp_id>",
        "kind": "<kind>",
        "preferred_label": "<proposed_label>",
        "definition": "<definition>",
        "version": "1.0.0",
        "status": "active",
        "owners": [],
        "aliases": [],
        "lifecycle": {
            "introduced_at": "<iso8601 timestamp>",
            "source_field": "<source_field>",
            "accepted_from": "<spec_file relative to repo_root>"
        }
    }
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANON_ID_RE = re.compile(r'^cn:[a-z0-9.]+:[a-z_][a-z0-9_]*:[a-z0-9-]+$')

logger = logging.getLogger(__name__)


def run_canon_accept(
    spec_file: str,
    namespace: str,
    repo_root: str,
    dry_run: bool = False,
    owner: str | None = None,
) -> dict[str, Any]:
    """Read canonical_proposals from spec_file and promote them to canon/manifest.json.

    Args:
        spec_file: Path to spec file (e.g., spec/03_glossary.json).
        namespace: Target namespace prefix (e.g., 'cn:project:').
        repo_root: Path to toolkit root (for locating canon/manifest.json).
        dry_run: If True, report what would be added without modifying manifest.
        owner: Optional owner to assign to new entries (e.g., 'spec-platform').
               Defaults to no owner (empty list).

    Returns:
        dict with keys:
          - added: list of new IDs that were (or would be) added
          - skipped: list of IDs that already existed in the manifest
          - malformed: count of proposals skipped due to missing required fields
          - error: str describing any fatal error, or None on success
    """
    spec_path = Path(os.path.abspath(spec_file))
    if not spec_path.exists():
        return {"added": [], "skipped": [], "malformed": 0, "error": f"spec file not found: {spec_path}"}

    # Load spec file
    try:
        with spec_path.open("r", encoding="utf-8") as fh:
            spec_data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"added": [], "skipped": [], "malformed": 0, "error": f"failed to read spec file {spec_path}: {exc}"}

    if not isinstance(spec_data, dict):
        return {"added": [], "skipped": [], "malformed": 0, "error": f"spec file root must be an object: {spec_path}"}

    # Extract proposals — top-level key per step_base schema
    proposals = spec_data.get("canonical_proposals")
    if proposals is None:
        proposals = []
    if not isinstance(proposals, list):
        return {"added": [], "skipped": [], "malformed": 0, "error": f"canonical_proposals must be an array in {spec_path}"}

    # Normalise namespace — ensure it ends with ':'
    ns = namespace if namespace.endswith(":") else namespace + ":"

    # Validate namespace: all segments must be non-empty and match expected format
    ns_parts = ns.rstrip(":").split(":")
    if not ns.startswith("cn:") or len(ns_parts) < 2 or not all(p for p in ns_parts):
        return {"added": [], "skipped": [], "malformed": 0, "error": f"invalid namespace '{namespace}': must start with 'cn:' and have at least two non-empty segments (e.g., 'cn:project:')"}

    # Load manifest
    root = Path(os.path.abspath(repo_root))
    manifest_path = root / "canon" / "manifest.json"
    if not manifest_path.exists():
        return {"added": [], "skipped": [], "malformed": 0, "error": f"manifest not found: {manifest_path}"}

    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"added": [], "skipped": [], "malformed": 0, "error": f"failed to read manifest {manifest_path}: {exc}"}

    if not isinstance(manifest, dict):
        return {"added": [], "skipped": [], "malformed": 0, "error": f"manifest root must be an object: {manifest_path}"}

    existing_entries = manifest.get("entries")
    if not isinstance(existing_entries, list):
        return {"added": [], "skipped": [], "malformed": 0, "error": f"manifest.entries must be an array: {manifest_path}"}

    # Compute spec path relative to repo root for storage in lifecycle.accepted_from
    try:
        accepted_from = str(spec_path.relative_to(root))
    except ValueError:
        # spec file is outside repo_root — fall back to the absolute path
        accepted_from = str(spec_path)

    # Build set of existing IDs for fast duplicate detection
    existing_ids: set[str] = set()
    for entry in existing_entries:
        if isinstance(entry, dict):
            eid = entry.get("id")
            if isinstance(eid, str) and eid:
                existing_ids.add(eid)

    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    added: list[str] = []
    skipped: list[str] = []
    malformed: int = 0
    new_entries: list[dict[str, Any]] = []

    # Resolve owners list from the optional owner argument
    owners_list: list[str] = [owner] if isinstance(owner, str) and owner else []

    for i, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            malformed += 1
            logger.warning("canon-accept: proposal at index %d is not an object — skipped", i)
            continue
        temp_id = proposal.get("temp_id")
        kind = proposal.get("kind")
        proposed_label = proposal.get("proposed_label")
        definition = proposal.get("definition")
        source_field = proposal.get("source_field")

        # Validate required fields and warn on malformed proposals
        missing: list[str] = []
        if not isinstance(temp_id, str) or not temp_id:
            missing.append("temp_id")
        if not isinstance(kind, str) or not kind:
            missing.append("kind")
        if not isinstance(proposed_label, str) or not proposed_label:
            missing.append("proposed_label")
        if not isinstance(definition, str) or not definition:
            missing.append("definition")
        if not isinstance(source_field, str) or not source_field:
            missing.append("source_field")
        if missing:
            malformed += 1
            logger.warning(
                "canon-accept: proposal at index %d missing required field(s) %s — skipped",
                i,
                missing,
            )
            continue

        # All required fields validated as non-empty str by the missing-fields check above.
        assert isinstance(temp_id, str) and isinstance(kind, str)

        # Validate temp_id format before generating canon_id
        if not re.match(r'^[a-z0-9][a-z0-9-]*$', temp_id):
            malformed += 1
            logger.warning(
                "canon-accept: proposal at index %d: temp_id '%s' is not valid kebab-case "
                "(must be lowercase letters, digits, and hyphens only, e.g. 'my-term'). Skipping.",
                i, temp_id,
            )
            continue

        # Validate kind format
        if not re.match(r'^[a-z_][a-z0-9_]*$', kind):
            malformed += 1
            logger.warning(
                "canon-accept: proposal at index %d: kind '%s' is not valid "
                "(must be lowercase letters, digits, and underscores, e.g. 'entity', 'risk_category'). Skipping.",
                i, kind,
            )
            continue

        # Generate canonical ID
        canon_id = f"{ns}{kind}:{temp_id}"

        if not CANON_ID_RE.match(canon_id):
            malformed += 1
            logger.warning(
                f"Proposal {i}: generated ID '{canon_id}' does not match canonicalRef pattern "
                f"(kind must use underscores, slug must be kebab-case). Skipping."
            )
            continue

        if canon_id in existing_ids:
            skipped.append(canon_id)
            continue

        lifecycle: dict[str, Any] = {"introduced_at": now_ts}
        lifecycle["source_field"] = source_field
        lifecycle["accepted_from"] = accepted_from

        new_entry: dict[str, Any] = {
            "id": canon_id,
            "kind": kind,
            "preferred_label": proposed_label,
            "definition": definition,
            "version": "1.0.0",
            "status": "active",
            "owners": list(owners_list),
            "aliases": [],
            "lifecycle": lifecycle,
        }

        new_entries.append(new_entry)
        existing_ids.add(canon_id)
        added.append(canon_id)

    if not dry_run and new_entries:
        manifest["entries"] = existing_entries + new_entries
        try:
            with manifest_path.open("w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
        except OSError as exc:
            # `added` holds the IDs that were queued but NOT persisted due to the write failure.
            # `write_failed: True` signals that these entries were attempted but not saved to disk.
            return {"added": added, "skipped": skipped, "malformed": malformed, "error": f"failed to write manifest {manifest_path}: {exc}", "write_failed": True}

    return {"added": added, "skipped": skipped, "malformed": malformed, "error": None}
