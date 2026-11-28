"""canon-accept: Promote canonical_proposals from a spec file to canon/manifest.json and canon/kinds/<kind>.json.

Reads the ``canonical_proposals`` array from a spec JSON file and appends any
new proposals (as fully-formed canon entries) to both ``canon/manifest.json``
and the matching ``canon/kinds/<kind>.json`` modular file.
Proposals whose generated ID already exists in the manifest are skipped when their text is the stored text,
reported as ``changed`` when it differs, and rewritten (``definition``, ``preferred_label``, ``aliases``) with ``update=True``.

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
            "accepted_from": "<spec_file relative to git_root, else repo_root>"
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
from typing import Any, NamedTuple

from ..core.json_utils import detect_indent
from ..graph.contract import normalise_text
from .registry import label_matches_entry
from ..trace.lockfile import replace_file_atomically

CANON_ID_RE = re.compile(r'^cn:[a-z0-9.]+:[a-z_][a-z0-9_]*:[a-z0-9-]+$')

logger = logging.getLogger(__name__)

_DEFAULT_INDENT = "  "


class _Update(NamedTuple):
    """An existing canon entry whose proposal text changed: the new text to write."""

    canon_id: str
    kind: str
    label: str
    definition: str


def _empty_result(error: str) -> dict[str, Any]:
    """The result of a run that stopped before any proposal was read."""
    return {"added": [], "skipped": [], "changed": [], "updated": [], "would_update": [], "malformed": 0, "error": error}


def _same_text(stored: Any, proposed: str) -> bool:
    """Whether the stored value is the proposed text once both are normalised."""
    return isinstance(stored, str) and normalise_text(stored) == normalise_text(proposed)


def _changed_fields(entry: dict[str, Any], label: str, definition: str) -> list[str]:
    """The fields of *entry* whose stored text differs from the proposal.

    Texts are compared as E606 and E607 compare them: a definition by ``graph.contract.normalise_text`` (layout,
    Unicode form, curly quote and dash are not a change); a label by ``registry.label_matches_entry`` (case and
    an alias of the entry are not a change either).
    """
    fields = []
    if not _same_text(entry.get("definition"), definition):
        fields.append("definition")
    if not label_matches_entry(label, entry):
        fields.append("preferred_label")
    return fields


def _apply_update(entry: dict[str, Any], label: str, definition: str) -> None:
    """Set the definition and preferred label of *entry*; a replaced label becomes an alias once."""
    old_label = entry.get("preferred_label")
    entry["definition"] = definition
    entry["preferred_label"] = label
    aliases = entry.setdefault("aliases", [])
    if isinstance(old_label, str) and old_label != label and old_label not in aliases:
        aliases.append(old_label)


def _write_json_atomic(path: Path, data: Any, indent: str) -> None:
    """Write *data* as JSON in *indent* with a final newline, through ``replace_file_atomically``."""
    replace_file_atomically(str(path), json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def _load_kind_file(kind_file: Path, kind: str) -> tuple[dict[str, Any], str | None] | None:
    """The kind file's data and its text (None for a new file), or None when it exists but cannot be read."""
    if not kind_file.exists():
        return {"$schema": "vc:canon:kind", "registry_version": "1.0.0", "kind": kind, "entries": []}, None
    try:
        text = kind_file.read_text(encoding="utf-8")
        return json.loads(text), text
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("canon-accept: could not read kind file %s — skipping modular update: %s", kind_file, exc)
        return None


def _write_kind_files(
    kinds_dir: Path,
    new_entries: list[dict[str, Any]],
    updates: list[_Update],
    manifest_entries: dict[str, dict[str, Any]],
    manifest_indent: str,
) -> None:
    """Mirror the new and updated entries into ``kinds/<kind>.json``, each file in the indentation it has.

    An updated id missing from its kind file is appended as the manifest holds it; an update of a kind that has
    no kind file (a manifest-only canon) does not create one. A kind file that cannot be read or written is
    logged and skipped.
    """
    new_kinds = {e["kind"] for e in new_entries}
    for kind in sorted(new_kinds | {u.kind for u in updates}):
        kind_file = kinds_dir / f"{kind}.json"
        if kind not in new_kinds and not kind_file.exists():
            continue
        loaded = _load_kind_file(kind_file, kind)
        if loaded is None:
            continue
        kind_data, kind_text = loaded
        indent = detect_indent(kind_text, default=manifest_indent) if kind_text is not None else manifest_indent
        entries = kind_data.setdefault("entries", [])
        by_id = {e.get("id"): e for e in entries if isinstance(e, dict)}
        for entry in new_entries:
            if entry["kind"] == kind and entry["id"] not in by_id:
                entries.append(entry)
                by_id[entry["id"]] = entry
        for update in (u for u in updates if u.kind == kind):
            if update.canon_id in by_id:
                _apply_update(by_id[update.canon_id], update.label, update.definition)
            else:
                entries.append(manifest_entries[update.canon_id])
        try:
            kinds_dir.mkdir(parents=True, exist_ok=True)
            _write_json_atomic(kind_file, kind_data, indent)
        except OSError as exc:
            logger.warning("canon-accept: failed to write kind file %s: %s", kind_file, exc)


def run_canon_accept(
    spec_file: str,
    namespace: str,
    repo_root: str,
    dry_run: bool = False,
    owner: str | None = None,
    canon_dir: str | None = None,
    project_canon: bool = False,
    git_root: str | None = None,
    update: bool = False,
) -> dict[str, Any]:
    """Read canonical_proposals from spec_file and promote them to canon/manifest.json.

    Args:
        spec_file: Path to spec file (e.g., spec/03_glossary.json).
        namespace: Target namespace prefix (e.g., 'cn:project:').
        repo_root: Path to toolkit root (for locating canon/manifest.json).
        dry_run: If True, report what would be added without modifying manifest.
        owner: Optional owner to assign to new entries (e.g., 'spec-platform').
               Defaults to no owner (empty list).
        git_root: Host root. ``lifecycle.accepted_from`` is the spec file's path relative to it or, without it,
               to ``repo_root``; an absolute path is never stored.
        update: Rewrite the definition, preferred label and aliases of an existing entry whose proposal text
               changed, in ``manifest.json`` and ``kinds/<kind>.json`` (default: list it as ``changed``, write nothing).

    Returns:
        dict with keys:
          - added: list of new IDs that were (or would be) added
          - skipped: list of IDs that already existed in the manifest with the proposal's text
          - changed: list of ``{"id", "fields"}`` for existing entries whose proposal text differs (not written)
          - updated / would_update: IDs of existing entries rewritten (``update``) / that a dry run would rewrite
          - malformed: count of proposals skipped due to missing required fields
          - error: str describing any fatal error, or None on success
    """
    spec_path = Path(os.path.abspath(spec_file))
    if not spec_path.exists():
        return _empty_result(f"spec file not found: {spec_path}")

    # Load spec file
    try:
        with spec_path.open("r", encoding="utf-8") as fh:
            spec_data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_result(f"failed to read spec file {spec_path}: {exc}")

    if not isinstance(spec_data, dict):
        return _empty_result(f"spec file root must be an object: {spec_path}")

    # Extract proposals — top-level key per step_base schema
    proposals = spec_data.get("canonical_proposals")
    if proposals is None:
        proposals = []
    if not isinstance(proposals, list):
        return _empty_result(f"canonical_proposals must be an array in {spec_path}")

    # Normalise namespace — ensure it ends with ':'
    ns = namespace if namespace.endswith(":") else namespace + ":"

    # Validate namespace: all segments must be non-empty and match expected format
    ns_parts = ns.rstrip(":").split(":")
    if not ns.startswith("cn:") or len(ns_parts) < 2 or not all(p for p in ns_parts):
        return _empty_result(f"invalid namespace '{namespace}': must start with 'cn:' and have at least two non-empty segments (e.g., 'cn:project:')")

    # Namespace guard: reject cn:core:* entries in project canon
    if project_canon and ns.startswith("cn:core:"):
        return _empty_result(
            f"E422 CORE_ENTRY_IN_PROJECT_CANON: namespace '{namespace}' targets cn:core:* which cannot be written to project canon"
        )

    # Load manifest
    root = Path(os.path.abspath(repo_root))
    canon_path = Path(os.path.abspath(canon_dir)) if canon_dir else root / "canon"
    manifest_path = canon_path / "manifest.json"
    if not manifest_path.exists():
        return _empty_result(f"manifest not found: {manifest_path}")

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
    except (OSError, json.JSONDecodeError) as exc:
        return _empty_result(f"failed to read manifest {manifest_path}: {exc}")

    if not isinstance(manifest, dict):
        return _empty_result(f"manifest root must be an object: {manifest_path}")

    existing_entries = manifest.get("entries")
    if not isinstance(existing_entries, list):
        return _empty_result(f"manifest.entries must be an array: {manifest_path}")

    manifest_indent = detect_indent(manifest_text, default=_DEFAULT_INDENT)

    # lifecycle.accepted_from: the spec file's path relative to the host root (else the toolkit root), never absolute
    base = Path(os.path.abspath(git_root)) if git_root else root
    accepted_from = Path(os.path.relpath(os.path.realpath(spec_path), os.path.realpath(base))).as_posix()

    # Index the existing entries by id for duplicate and change detection
    existing_by_id: dict[str, dict[str, Any]] = {}
    for entry in existing_entries:
        if isinstance(entry, dict):
            eid = entry.get("id")
            if isinstance(eid, str) and eid:
                existing_by_id[eid] = entry

    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    added: list[str] = []
    skipped: list[str] = []
    changed: list[dict[str, Any]] = []
    updated: list[str] = []
    would_update: list[str] = []
    updates: list[_Update] = []
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
        assert isinstance(proposed_label, str) and isinstance(definition, str)

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

        stored = existing_by_id.get(canon_id)
        if stored is not None:
            fields = _changed_fields(stored, proposed_label, definition)
            if not fields:
                skipped.append(canon_id)
            elif not update:
                changed.append({"id": canon_id, "fields": fields})
            elif dry_run:
                would_update.append(canon_id)
            else:
                _apply_update(stored, proposed_label, definition)
                updates.append(_Update(canon_id, kind, proposed_label, definition))
                updated.append(canon_id)
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
        existing_by_id[canon_id] = new_entry
        added.append(canon_id)

    result: dict[str, Any] = {
        "added": added, "skipped": skipped, "changed": changed, "updated": updated,
        "would_update": would_update, "malformed": malformed, "error": None,
    }
    if not dry_run and (new_entries or updates):
        manifest["entries"] = existing_entries + new_entries
        try:
            _write_json_atomic(manifest_path, manifest, manifest_indent)
        except OSError as exc:
            return {**result, "error": f"failed to write manifest {manifest_path}: {exc}", "write_failed": True}
        _write_kind_files(canon_path / "kinds", new_entries, updates, existing_by_id, manifest_indent)

    return result
