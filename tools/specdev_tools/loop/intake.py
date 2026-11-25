"""Intake: the checks on every file an agent hands to a run, and the merge of a round.

A reviewer's file is checked as a whole first (shape, coverage, judgements): a file that
fails counts as not arrived, so the entry is handed out again. Each finding is then checked
on its own (target, evidence): one that fails goes to ``rejected.json`` with the reason.
Nothing is dropped silently.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.schema_validate import SchemaValidationError, schema_violations
from specdev_tools.loop.spec_io import SpecIO

FINDINGS_SCHEMA = "vc:infra:findings"
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
LINE = re.compile(r"#L?\d+(?:-L?\d+)?$|:\d+(?:-\d+)?$")
INDEX = re.compile(r"/\d+(?:/|$)|\[\d+\]")
"""A line number, or an array index in the pointer after ``#``: a position, which is never identity."""


def is_position(location: str) -> bool:
    _, _, pointer = location.partition("#")
    return bool(LINE.search(location) or INDEX.search(pointer))


def _pair(value: Any) -> dict[str, Any]:
    """A ``{source, text}`` an agent wrote, or an empty one when it wrote something else."""
    return value if isinstance(value, dict) else {}


@dataclass
class ReviewFile:
    ok: bool
    reason: str = ""
    document: dict[str, Any] = field(default_factory=dict)


def key_of(finding: dict[str, Any]) -> str:
    return f"{finding.get('kind', '')}|{finding.get('location', '')}"


def target_of(location: str) -> str:
    return location.split("#", 1)[0]


def load_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def check_review_file(
    path: str, repo_root: str, *, round_no: int, scope: str, assigned: list[str], contract: list[str], judge: list[str]
) -> ReviewFile:
    """Shape, coverage and judgements of one reviewer's file."""
    document = load_json(path)
    if not isinstance(document, dict):
        return ReviewFile(False, "the file is not a JSON object")
    for finding in document.get("findings") or []:
        if isinstance(finding, dict):
            finding["signature"] = key_of(finding)  # the key is computed here, never by an agent
    document["$schema"] = FINDINGS_SCHEMA
    try:
        violations = schema_violations(repo_root, document)
    except SchemaValidationError as exc:
        return ReviewFile(False, f"schema: {exc}")
    if violations:
        first = violations[0]
        return ReviewFile(False, f"schema: {'/'.join(str(p) for p in first.path)}: {first.message}")
    if document.get("round") != round_no or document.get("scope") != scope:
        return ReviewFile(False, f"round and scope must be {round_no} and {scope!r}")
    coverage = document.get("coverage") or {}
    read = set(coverage.get("read") or [])
    missing = [x for x in [*assigned, *contract] if x not in read]
    if missing:
        return ReviewFile(False, f"coverage.read lacks {len(missing)} assigned entries, the first: {missing[0]}")
    if coverage.get("not_run"):
        return ReviewFile(False, "coverage.not_run is not empty")
    judged = {j.get("key") for j in document.get("judgements") or [] if isinstance(j, dict)}
    unjudged = [k for k in judge if k not in judged]
    if unjudged:
        return ReviewFile(False, f"no judgement for {unjudged[0]}")
    return ReviewFile(True, document=document)


def check_finding(finding: dict[str, Any], io: SpecIO) -> str | None:
    """The reason a finding is refused, or None: its target must exist and its quotes occur."""
    location = finding.get("location", "")
    if is_position(location):
        return "the location holds a line number or an array index"
    if not io.exists(target_of(location)):
        return f"the target {target_of(location)!r} is neither a node nor a file"
    quotes = finding.get("evidence_quotes") or []
    if not quotes:
        return "no evidence quote"
    for quote in quotes:
        if not io.quote_occurs(quote.get("source", ""), quote.get("text", "")):
            return f"a quote does not occur in {quote.get('source', '')!r}"
    return None


@dataclass
class Merged:
    raised: list[dict[str, Any]] = field(default_factory=list)  # for apply_review
    detail: dict[str, dict[str, Any]] = field(default_factory=dict)  # key -> merged finding
    rejected: list[dict[str, Any]] = field(default_factory=list)
    judgements: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)  # key -> the judging reviewer's quote


def merge_round(documents: list[dict[str, Any]], io: SpecIO) -> Merged:
    """Merge the files of a round by key: one entry per key, all descriptions and quotes, the higher severity."""
    out = Merged()
    for document in documents:
        for finding in document.get("findings") or []:
            reason = check_finding(finding, io)
            if reason is not None:
                out.rejected.append({"finding": finding, "reason": reason})
                continue
            key = key_of(finding)
            target = target_of(finding["location"])
            entry = out.detail.get(key)
            if entry is None:
                out.detail[key] = entry = {
                    "kind": finding["kind"], "location": finding["location"], "severity": finding["severity"],
                    "messages": [], "evidence_quotes": [], "suggested_fix": finding.get("suggested_fix", ""),
                    "upstream_refs": list(finding.get("upstream_refs") or []), "target": target,
                    "in_scope": io.in_scope(target), "evidence": [], "origin": finding.get("origin"),
                }
            elif SEVERITY_ORDER[finding["severity"]] < SEVERITY_ORDER[entry["severity"]]:
                entry["severity"] = finding["severity"]
            if finding["message"] not in entry["messages"]:
                entry["messages"].append(finding["message"])
            for quote in finding.get("evidence_quotes") or []:
                if quote not in entry["evidence_quotes"]:
                    entry["evidence_quotes"].append(quote)
            for line in finding.get("evidence") or []:  # what a reviewer cites besides its quotes
                if line not in entry["evidence"]:
                    entry["evidence"].append(line)
            entry["origin"] = entry["origin"] or finding.get("origin")
        for judgement in document.get("judgements") or []:
            out.judgements[judgement["key"]] = judgement["verdict"]
            out.reasons[judgement["key"]] = judgement.get("quote", "")
    for key, entry in sorted(out.detail.items()):
        out.raised.append(
            {"key": key, "severity": entry["severity"], "target": entry["target"], "in_scope": entry["in_scope"]}
        )
    return out


def fix_checks(
    document: Any, io: SpecIO, *, before: dict[str, str], now: dict[str, str], listed: set[str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Turn a fixer's outcome file into what ``apply_fix`` takes, with every claim checked."""
    outcomes: dict[str, dict[str, Any]] = {}
    noticed: list[str] = []
    if not isinstance(document, dict):
        return outcomes, noticed
    items = io.open_item_ids()
    listed_outcomes = document.get("outcomes")
    for entry in listed_outcomes if isinstance(listed_outcomes, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("key"), str):
            continue
        kind = entry.get("outcome")
        checked: dict[str, Any] = {"outcome": kind, "raw": entry}
        named_changed = entry.get("changed")
        changed = [c for c in (named_changed if isinstance(named_changed, list) else [])
                   if isinstance(c, str) and before.get(c) != now.get(c)]
        checked["changed"] = bool(changed)
        basis = entry.get("basis")
        checked["basis_ok"] = True if not basis else io.quote_occurs(
            str(_pair(basis).get("source", "")), str(_pair(basis).get("text", "")))
        checked["item_exists"] = isinstance(entry.get("item_id"), str) and entry["item_id"] in items
        checked["listed"] = entry["key"] in listed
        if kind == "declined":
            quote = _pair(entry.get("quote"))
            if not io.quote_occurs(str(quote.get("source", "")), str(quote.get("text", ""))):
                checked["outcome"] = None  # a decline with no quote that occurs is no outcome
        if kind == "upstream":
            named = _pair(entry.get("named"))
            if isinstance(named.get("kind"), str) and isinstance(named.get("location"), str) and named["kind"] and named["location"]:
                target = target_of(named["location"])
                checked["named"] = key_of(named)
                checked["target"] = target
                checked["in_scope"] = io.in_scope(target)
        outcomes[entry["key"]] = checked
    noticed = [str(n) for n in document.get("noticed") or []] if isinstance(document.get("noticed"), list) else []
    return outcomes, noticed


def file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
