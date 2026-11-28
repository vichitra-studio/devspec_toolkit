from __future__ import annotations

import json
import os
from typing import Any

from ..canonical.registry import label_matches_entry, load_tier_entries
from ..core.errors import SpecError, make_error
from ..core.loaders import iter_spec_artifacts
from ..graph.contract import normalise_text as _normalise

_PROJECT_PREFIX = "cn:project:"
_GLOSSARY_FILE = "03_glossary.json"
_SNIPPET_LENGTH = 30


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _fold(text: str) -> str:
    """Normalise and ignore case: the comparison of labels."""
    return _normalise(text).casefold()


def _first_difference(left: str, right: str) -> int:
    """Index of the first character at which two texts differ (the shorter length if one is a prefix)."""
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right))


def _difference_detail(left_name: str, left: str, right_name: str, right: str) -> str:
    """Message suffix naming where two normalised texts first differ and what each says there."""
    at = _first_difference(left, right)
    return (
        f" first_difference_at={at}"
        f" {left_name}='{left[at:at + _SNIPPET_LENGTH]}'"
        f" {right_name}='{right[at:at + _SNIPPET_LENGTH]}'"
    )


def _load_project_entries(
    spec_dir: str, repo_root: str | None, project_canon_dir: str | None,
) -> dict[str, dict[str, Any]]:
    """Project-tier canon entries by id, read through the registry loader (manifest and kinds/)."""
    project_dir = os.path.abspath(project_canon_dir or os.path.join(spec_dir, "canon"))
    if not os.path.isdir(project_dir):
        return {}
    if repo_root is None:
        entries = load_tier_entries(os.path.dirname(project_dir), os.path.basename(project_dir))
    else:
        entries = load_tier_entries(repo_root, "canon", project_canon_dir=project_dir)
    return {e["id"]: e for e in entries if e["id"].startswith(_PROJECT_PREFIX)}


def _label_texts(entry: dict[str, Any]) -> list[str]:
    """The labels a canon entry answers to: its preferred label first, then its aliases."""
    labels = [entry["preferred_label"]] if isinstance(entry.get("preferred_label"), str) else []
    labels.extend(a for a in (entry.get("aliases") or []) if isinstance(a, str))
    return labels


def _label_difference(label: str, entry: dict[str, Any]) -> str | None:
    """Detail suffix when *label* is neither the entry's preferred label nor an alias, else None."""
    if label_matches_entry(label, entry):
        return None
    return _difference_detail("spec", _fold(label), "canon", _fold(_label_texts(entry)[0]))


def _check_term_proposal_drift(
    terms: list[dict[str, Any]], proposals: list[dict[str, Any]],
) -> list[SpecError]:
    """Pass 1 (E606): a term definition must equal the proposal it was made from (kind == "term" only).

    Acronym proposals are excluded: they have no entry in terms[]. The term id is
    assumed to be "term-" + temp_id, the convention of the glossary prompt.
    """
    term_defs = {t["term_id"]: t.get("definition", "") for t in terms if t.get("term_id")}
    errors: list[SpecError] = []
    for proposal in proposals:
        if proposal.get("kind") != "term":
            continue
        temp_id = proposal.get("temp_id", "")
        tid = f"term-{temp_id}"
        if tid not in term_defs:
            continue
        spec_text = _normalise(term_defs[tid])
        proposal_text = _normalise(proposal.get("definition", ""))
        if spec_text != proposal_text:
            errors.append(make_error(
                "E606",
                f"GLOSSARY_PROPOSAL_DRIFT term={tid} proposal={temp_id}"
                + _difference_detail("spec", spec_text, "proposal", proposal_text),
                path=f"terms[{tid}]",
            ))
    return errors


def _compare_with_entry(
    base: str, path: str, side: str, definition: Any, label: Any, entry: dict[str, Any], *, name_field: bool,
) -> list[SpecError]:
    """E607 for the definition and the label of one spec text (*side*: ``spec`` or ``proposal``) against its canon entry.

    *name_field* puts ``field=definition`` in the definition message (the proposal form; the term form has none).
    """
    errors: list[SpecError] = []
    if isinstance(definition, str):
        spec_text = _normalise(definition)
        canon_text = _normalise(entry.get("definition", ""))
        if spec_text != canon_text:
            field = " field=definition" if name_field else ""
            errors.append(make_error(
                "E607", f"{base}{field}" + _difference_detail(side, spec_text, "canon", canon_text), path=path,
            ))
    label_detail = _label_difference(label, entry) if isinstance(label, str) else None
    if label_detail:
        errors.append(make_error("E607", f"{base} field=preferred_label{label_detail}", path=path))
    return errors


def _check_term_canon_drift(
    terms: list[dict[str, Any]], canon_entries: dict[str, dict[str, Any]],
) -> list[SpecError]:
    """Pass 2 (E607): a term bound to a project canon entry agrees with it in definition and label."""
    errors: list[SpecError] = []
    for term in terms:
        term_id = term.get("term_id")
        canon_id = (term.get("term_ref") or {}).get("id", "")
        if not term_id or canon_id not in canon_entries:
            continue
        errors.extend(_compare_with_entry(
            f"GLOSSARY_CANON_DRIFT term={term_id} canon={canon_id}", f"terms[{term_id}]",
            "spec", term.get("definition", ""), term.get("term"), canon_entries[canon_id],
            name_field=False,
        ))
    return errors


def _check_proposal_against_canon(
    proposal: dict[str, Any], canon_id: str, file_name: str, entry: dict[str, Any],
) -> list[SpecError]:
    """E607 for one proposal of a non-glossary step whose canon entry differs from it."""
    return _compare_with_entry(
        f"CANON_PROPOSAL_DRIFT kind={proposal['kind']} canon={canon_id} file={file_name}",
        f"{file_name}:{canon_id}", "proposal", proposal.get("definition"), proposal.get("proposed_label"), entry,
        name_field=True,
    )


def _check_artifact_proposals(
    spec_dir: str, canon_entries: dict[str, dict[str, Any]],
) -> list[SpecError]:
    """Pass 2b (E607): proposals of every step except the glossary against the entries made from them."""
    errors: list[SpecError] = []
    for path in iter_spec_artifacts(spec_dir):
        file_name = os.path.basename(path)
        if file_name == _GLOSSARY_FILE:
            continue
        try:
            artifact = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue  # a malformed artifact is reported by the schema validators
        proposals = artifact.get("canonical_proposals") if isinstance(artifact, dict) else None
        if not isinstance(proposals, list):
            continue
        for proposal in proposals:
            if not isinstance(proposal, dict) or "kind" not in proposal or "temp_id" not in proposal:
                continue
            canon_id = f"{_PROJECT_PREFIX}{proposal['kind']}:{proposal['temp_id']}"
            if canon_id in canon_entries:
                errors.extend(_check_proposal_against_canon(proposal, canon_id, file_name, canon_entries[canon_id]))
    return errors


def _check_orphans(
    canon_entries: dict[str, dict[str, Any]],
    proposals: list[dict[str, Any]],
    refs_used: set[str],
) -> list[SpecError]:
    """Pass 3 (W606): an entry accepted from the glossary that nothing in the glossary names."""
    proposal_ids = {
        f"{_PROJECT_PREFIX}{p['kind']}:{p['temp_id']}"
        for p in proposals
        if "kind" in p and "temp_id" in p
    }
    errors: list[SpecError] = []
    for eid, entry in canon_entries.items():
        accepted_from = (entry.get("lifecycle") or {}).get("accepted_from", "")
        if os.path.basename(accepted_from) != _GLOSSARY_FILE:
            continue
        if eid not in refs_used and eid not in proposal_ids:
            errors.append(make_error(
                "W606",
                f"GLOSSARY_CANON_ORPHAN id={eid} registered from glossary but not referenced",
                path=eid,
            ))
    return errors


def lint_glossary_drift(
    spec_dir: str,
    repo_root: str | None = None,
    project_canon_dir: str | None = None,
) -> list[SpecError]:
    """Check the glossary, its proposals and the project canon against each other.

    Text is compared after collapsing whitespace, composing Unicode and folding
    curly quotes and dashes; a
    message names the first differing position. Returns E606 (term vs its
    proposal), E607 (term or ``canonical_proposals`` item of any step vs the
    project canon entry: definition and label) and W606 (orphan entry), or
    E521 when the glossary cannot be read. ``repo_root`` is the toolkit root
    whose canon tier is merged under the project tier (project wins);
    ``project_canon_dir`` defaults to ``<spec_dir>/canon``.
    """
    spec_dir = os.path.abspath(spec_dir)
    glossary_path = os.path.join(spec_dir, _GLOSSARY_FILE)
    if not os.path.isfile(glossary_path):
        return []

    try:
        glossary = _load_json(glossary_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [make_error("E521", f"VALIDATOR_RUNTIME glossary_drift_lint: {exc}")]

    terms = glossary.get("terms", [])
    proposals = glossary.get("canonical_proposals", [])
    refs_used = {r["id"] for r in glossary.get("canonical_refs_used", []) if "id" in r}
    canon_entries = _load_project_entries(spec_dir, repo_root, project_canon_dir)

    return [
        *_check_term_proposal_drift(terms, proposals),
        *_check_term_canon_drift(terms, canon_entries),
        *_check_artifact_proposals(spec_dir, canon_entries),
        *_check_orphans(canon_entries, proposals, refs_used),
    ]
