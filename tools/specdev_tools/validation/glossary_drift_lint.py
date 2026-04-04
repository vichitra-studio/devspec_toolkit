from __future__ import annotations

import json
import os
from typing import Any

from ..core.errors import SpecError, make_error


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def lint_glossary_drift(
    spec_dir: str,
    repo_root: str | None = None,  # accepted for API consistency with other lint functions; unused
    project_canon_dir: str | None = None,
) -> list[SpecError]:
    errors: list[SpecError] = []
    spec_dir = os.path.abspath(spec_dir)

    glossary_path = os.path.join(spec_dir, "03_glossary.json")
    if not os.path.isfile(glossary_path):
        return errors

    try:
        glossary = _load_json(glossary_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [make_error("E521", f"VALIDATOR_RUNTIME glossary_drift_lint: {exc}")]

    terms = glossary.get("terms", [])
    proposals = glossary.get("canonical_proposals", [])
    refs_used = {r["id"] for r in glossary.get("canonical_refs_used", []) if "id" in r}

    # Build index: term_id -> definition
    # Pass 1 assumes term_id == "term-" + temp_id for kind=="term" proposals.
    # This convention holds for all terms authored via the standard glossary prompt
    # (each term's term_id is the kebab-case term prefixed with "term-").
    term_defs: dict[str, str] = {t["term_id"]: t.get("definition", "") for t in terms}

    # --- Pass 1: term ↔ proposal (kind == "term" only) ---
    # Acronym proposals (kind == "acronym") are excluded: they have no corresponding
    # entry in terms[] — the glossary schema does not place acronyms in the terms array.
    for proposal in proposals:
        if proposal.get("kind") != "term":
            continue
        temp_id = proposal.get("temp_id", "")
        prop_def = proposal.get("definition", "")
        tid = f"term-{temp_id}"
        if tid in term_defs and term_defs[tid] != prop_def:
            errors.append(make_error(
                "E606",
                f"GLOSSARY_PROPOSAL_DRIFT term={tid} proposal={temp_id}",
                path=f"terms[{tid}]",
            ))

    # --- Pass 2: term ↔ canon kinds ---
    # project_canon_dir points to spec/canon (the canon/ dir, not kinds/).
    # Derive kinds_base by appending /kinds — consistent with _discover_project_canon_dir
    # convention used throughout the toolkit.
    kinds_base: str | None = None
    if project_canon_dir:
        candidate = os.path.join(os.path.abspath(project_canon_dir), "kinds")
        if os.path.isdir(candidate):
            kinds_base = candidate
    else:
        # Fallback: project canon lives inside spec_dir/canon/kinds
        candidate = os.path.join(spec_dir, "canon", "kinds")
        if os.path.isdir(candidate):
            kinds_base = candidate

    if kinds_base:
        canon_defs: dict[str, str] = {}
        for kinds_file in sorted(os.listdir(kinds_base)):
            if not kinds_file.endswith(".json"):
                continue
            kpath = os.path.join(kinds_base, kinds_file)
            try:
                kdata = _load_json(kpath)
                for entry in kdata.get("entries", []):
                    eid = entry.get("id", "")
                    if eid.startswith("cn:project:"):
                        canon_defs[eid] = entry.get("definition", "")
            except (OSError, json.JSONDecodeError):
                continue

        for term in terms:
            term_ref = term.get("term_ref", {})
            canon_id = term_ref.get("id", "")
            if not canon_id.startswith("cn:project:"):
                continue
            if canon_id in canon_defs and term.get("definition", "") != canon_defs[canon_id]:
                errors.append(make_error(
                    "E607",
                    f"GLOSSARY_CANON_DRIFT term={term['term_id']} canon={canon_id}",
                    path=f"terms[{term['term_id']}]",
                ))

    # --- Pass 3: orphan detection ---
    manifest_path: str | None = None
    if project_canon_dir:
        mp = os.path.join(os.path.abspath(project_canon_dir), "manifest.json")
        if os.path.isfile(mp):
            manifest_path = mp
    else:
        mp = os.path.join(spec_dir, "canon", "manifest.json")
        if os.path.isfile(mp):
            manifest_path = mp

    if manifest_path:
        proposals_ids = {
            f"cn:project:{p['kind']}:{p['temp_id']}"
            for p in proposals
            if "kind" in p and "temp_id" in p
        }
        try:
            manifest = _load_json(manifest_path)
            for entry in manifest.get("entries", []):
                eid = entry.get("id", "")
                if not eid.startswith("cn:project:"):
                    continue
                accepted_from = entry.get("lifecycle", {}).get("accepted_from", "")
                if os.path.basename(accepted_from) != "03_glossary.json":
                    continue
                if eid not in refs_used and eid not in proposals_ids:
                    errors.append(make_error(
                        "W606",
                        f"GLOSSARY_CANON_ORPHAN id={eid} registered from glossary but not referenced",
                        path=eid,
                    ))
        except (OSError, json.JSONDecodeError):
            pass

    return errors
