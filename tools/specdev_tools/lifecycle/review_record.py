"""``specdev review record``: replace the ``review`` block of a milestone's plan with the verdict of the 16c review.

The block holds the single latest verdict (no history), the findings of the reviewer's converged findings file mapped to the
plan's own finding shape, and what the person who ran the command gave: next actions, a security status, ratings.  The tool
refuses input that is wrong (E823: an unknown verdict, a findings file that is not a valid ``vc:infra:findings`` document, a
finding that names a plan item the plan does not have, a block that breaks the plan schema) and a closed plan (E820).  It
does not judge: ``verified`` is accepted with a blocking finding or a red security status; the close gate and the reviewer own
those rules.  Nothing about coverage or proof is stored: they are computed.

A findings file is read as a ``vc:infra:findings`` document and must carry ``"$schema": "vc:infra:findings"``.  Each finding
becomes one entry of ``review.findings``:

* ``id`` ``finding-<NN>``, numbered in file order; ``type`` from the finding's ``kind`` (``TYPE_OF_KIND``); ``severity`` P0 to
  ``blocking``, P1 to ``major``, P2 to ``minor``; ``description`` the finding's message (at most 600 characters);
* ``spec_ref`` the milestone (type ``code``) with the finding's ``location`` as its note;
* ``related_checklist_ids`` the plan items the finding names: the file's ``scope`` when it is a plan-item id, and each entry
  of ``upstream_refs`` written as a plan-item id; each must be an item of this plan;
* ``remediation_task`` for a finding that is blocking or major, or has a ``suggested_fix``: its summary is the suggested fix
  (else the message), the file part of ``location`` is the file to touch;
* ``metadata`` the findings round and scope as source, the evidence (else the kind) as impact.

A finding whose ``status`` is ``verified`` is fixed and confirmed and is left out.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.errors import FindingError, refusal
from ..core.json_utils import JsonUtilsError, check_edit, json_write_atomic, patch_text
from ..core.schema_validate import SchemaValidationError, validate_data_against_schema
from ..graph.names import PLAN_ITEM
from ..trace.writing import locked_graph
from . import plans
from .plan_records import refuse_if_frozen
from .records import now_utc

VERDICTS = ("verified", "needs_work", "blocked", "deferred")
FINDINGS_URI = "vc:infra:findings"
MAX_FINDINGS = 50
MAX_DESCRIPTION = 600
REVIEW_PATH = ".review"
SEVERITY = {"P0": "blocking", "P1": "major", "P2": "minor"}
TYPE_OF_KIND = {
    "gap": "gap",
    "miss": "gap",
    "seed-grounding": "gap",
    "bug": "bug",
    "regression": "bug",
    "drift": "bug",
    "determinism": "bug",
    "assumption": "design",
    "ambiguity": "design",
    "hallucination": "scope_creep",
    "coverage": "tests",
}
"""The review finding ``type`` for each ``kind`` of the findings schema."""
VERIFIED_STATUS = "verified"
PLAN_ITEM_ID = re.compile(r"^[A-Z0-9_]*[A-Z][A-Z0-9_]*$")
BLOCKS_CLOSE = frozenset({"blocking", "major"})


@dataclass(frozen=True)
class ReviewRequest:
    """The arguments of ``review record``: the milestone, the verdict and the optional inputs."""

    milestone: str
    verdict: str
    findings_file: str | None = None
    next_actions: str | None = None
    security_status: str | None = None
    ratings_json: str | None = None


@dataclass(frozen=True)
class ReviewResult:
    """What ``review record`` wrote: the block, the plan file and its size before and after."""

    block: dict[str, Any]
    plan: str
    bytes_before: int
    bytes_after: int


def _invalid(message: str) -> FindingError:
    return refusal("E823", message)


def read_findings(path: str, repo_root: str) -> dict[str, Any]:
    """The findings document in the file *path*, checked against ``vc:infra:findings``.

    Raises:
        FindingError: E823 when the file cannot be read or is not a JSON object, has no ``"$schema"`` (or another one than
            ``vc:infra:findings``), or breaks the findings schema; the message names the missing or wrong thing.
    """
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise _invalid(f"the findings file {path} cannot be read as JSON ({error}); give the path of a converged findings file") from None
    if not isinstance(document, dict):
        raise _invalid(f"the findings file {path} is not a JSON object; give the path of a converged findings file")
    uri = document.get("$schema")
    if uri != FINDINGS_URI:
        what = "has no \"$schema\"" if uri is None else f"has \"$schema\" {uri!r}"
        raise _invalid(f"the findings file {path} {what}; add \"$schema\": \"{FINDINGS_URI}\"")
    try:
        problems = sorted(validate_data_against_schema(repo_root, document), key=lambda pair: (len(pair[0]), pair[0]))
    except SchemaValidationError as error:
        raise _invalid(f"the findings file {path} cannot be checked: {error}") from None
    if problems:
        where, message = problems[0]
        raise _invalid(f"the findings file {path} is not a valid findings document: {'/'.join(str(part) for part in where) or 'file'}: {message}")
    return document


def _plan_item_refs(document: Mapping[str, Any], finding: Mapping[str, Any]) -> list[str]:
    """The plan-item ids the finding names: the file's scope when it is one, then the ``upstream_refs`` written as one, each once."""
    named = [document["scope"], *finding.get("upstream_refs", ())]
    return list(dict.fromkeys(name for name in named if PLAN_ITEM_ID.match(name)))


def _remediation(finding: Mapping[str, Any], finding_id: str, checklist: list[str]) -> dict[str, Any]:
    file_part = finding["location"].split("#", 1)[0]
    return {
        "task_id": f"fix-{finding_id}",
        "summary": finding.get("suggested_fix") or finding["message"],
        "files_to_touch": [file_part] if file_part else [],
        "checklist_ids": checklist,
    }


def _review_finding(document: Mapping[str, Any], finding: Mapping[str, Any], number: int, milestone: str, items: frozenset[str]) -> dict[str, Any]:
    finding_id = f"finding-{number:02d}"
    if len(finding["message"]) > MAX_DESCRIPTION:
        raise _invalid(f"finding {number} of the findings file has a message of {len(finding['message'])} characters, above {MAX_DESCRIPTION}; shorten it")
    checklist = _plan_item_refs(document, finding)
    unknown = [name for name in checklist if name not in items]
    if unknown:
        raise _invalid(f"finding {number} names plan item {unknown[0]}, which no plan item of milestone {milestone} has; name an item of the plan, or drop it from the finding")
    severity = SEVERITY[finding["severity"]]
    mapped: dict[str, Any] = {
        "id": finding_id,
        "type": TYPE_OF_KIND[finding["kind"]],
        "severity": severity,
        "spec_ref": {"type": "code", "id": milestone, "note": finding["location"]},
        "description": finding["message"],
        "metadata": {
            "source": f"findings round {document['round']}, scope {document['scope']}",
            "impact": "; ".join(finding.get("evidence", ())) or finding["kind"],
        },
    }
    if checklist:
        mapped["related_checklist_ids"] = checklist
    if severity in BLOCKS_CLOSE or "suggested_fix" in finding:
        mapped["remediation_task"] = _remediation(finding, finding_id, checklist)
    return mapped


def map_findings(document: Mapping[str, Any], milestone: str, items: frozenset[str]) -> list[dict[str, Any]]:
    """The ``review.findings`` entries for the findings *document* of *milestone* whose plan has the items *items*; a finding already ``verified`` is left out.

    Raises:
        FindingError: E823 for a finding that names a plan item *items* does not hold, has a message above 600 characters,
            or when more than 50 findings remain.
    """
    open_ones = [finding for finding in document["findings"] if finding.get("status") != VERIFIED_STATUS]
    if len(open_ones) > MAX_FINDINGS:
        raise _invalid(f"the findings file holds {len(open_ones)} open findings, above the {MAX_FINDINGS} the review block takes; fix the most serious first and run the review again")
    return [_review_finding(document, finding, number, milestone, items) for number, finding in enumerate(open_ones, start=1)]


def _ratings(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except ValueError as error:
        raise _invalid(f"--ratings-json is not JSON ({error}); give an object such as '{{\"code_quality\": 4, ...}}'") from None
    if not isinstance(value, dict):
        raise _invalid("--ratings-json is not a JSON object; give an object such as '{\"code_quality\": 4, ...}'")
    return value


def _violations(error: JsonUtilsError) -> str:
    """The violations a refused edit lists (its ``path ...`` lines) on one line; the whole message when it lists none."""
    lines = [line.strip().removeprefix("path ") for line in str(error).splitlines() if line.strip().startswith("path ")]
    return "; ".join(lines) or str(error)


def _block(request: ReviewRequest, findings: list[dict[str, Any]] | None) -> dict[str, Any]:
    block: dict[str, Any] = {} if findings is None else {"findings": findings}
    block["verdict"] = request.verdict
    block["recorded_at"] = now_utc()
    if request.next_actions is not None:
        block["next_actions"] = request.next_actions
    if request.security_status is not None:
        block["security_status"] = request.security_status
    if request.ratings_json is not None:
        block["ratings"] = _ratings(request.ratings_json)
    return block


def record_review(spec_root: str, repo_root: str, request: ReviewRequest) -> ReviewResult:
    """Replace the ``review`` block of the plan of ``request.milestone`` by the one the request describes.

    Takes the write lock of *spec_root*.  The whole block is replaced; nothing of an earlier verdict stays.

    Raises:
        FindingError: E803 when no plan names the milestone; E820 for a closed milestone; E823 for input that is wrong (see
            the module docstring); E769 when another write holds the lock.
    """
    if request.verdict not in VERDICTS:
        raise _invalid(f"verdict {request.verdict!r} is not one of {', '.join(VERDICTS)}")
    plan = plans.require_plan(spec_root, request.milestone)
    rel = os.path.relpath(plan, spec_root)
    document = read_findings(request.findings_file, repo_root) if request.findings_file else None
    with locked_graph(spec_root, repo_root, "review record") as graph:
        refuse_if_frozen(spec_root, request.milestone, rel)
        items = frozenset(node.id for node in graph.by_kind.get(PLAN_ITEM, ()) if node.file == rel)
        block = _block(request, map_findings(document, request.milestone, items) if document is not None else None)
        content, before = Path(plan).read_text(encoding="utf-8"), os.path.getsize(plan)
        new_content = patch_text(content, REVIEW_PATH, json.dumps(block))
        try:
            check_edit(str(plan), content, new_content, repo_root)
        except JsonUtilsError as error:
            raise _invalid(f"the review block would not satisfy the plan schema: {_violations(error)}") from None
        json_write_atomic(str(plan), new_content)
        return ReviewResult(block, rel, before, os.path.getsize(plan))
