"""The end of a run: ``final.json`` and ``handoffs.json`` (findings documents), ``summary.json`` and ``report.md``."""

from __future__ import annotations

import os
import time
from typing import Any

from specdev_tools.loop import store
from specdev_tools.loop.machine import RESOLVED, REVIEW, SETTLED, RunState

CLOSED = (RESOLVED, SETTLED)
MESSAGE_MAX = 600


GUIDANCE = "The operator: "


def as_finding(key: str, info: dict[str, Any]) -> dict[str, Any]:
    """One entry of a findings document from the run's record of a key: the first description, at most 600 characters."""
    messages = info.get("messages") or [key]
    out: dict[str, Any] = {
        "kind": info.get("kind", "bug"), "location": info.get("location", info.get("target", key)), "signature": key,
        "message": str(messages[0])[:MESSAGE_MAX], "severity": info.get("severity", "P1"),
    }
    if info.get("evidence_quotes"):
        out["evidence_quotes"] = info["evidence_quotes"]
    for optional in ("evidence", "origin", "upstream_refs"):  # what the reviewers gave besides the quotes
        if info.get(optional):
            out[optional] = info[optional]
    if str(info.get("instruction") or "").startswith(GUIDANCE):
        out["suggested_fix"] = info["instruction"]  # the operator's guidance travels with the finding
    return out


def findings_document(scope: str, round_no: int, findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {"$schema": "vc:infra:findings", "round": max(1, round_no), "scope": scope,
            "generated_at": int(time.time()), "findings": findings}


def open_review_keys(state: RunState) -> list[str]:
    """The reviewer findings that are not closed: what ``final.json`` holds."""
    return sorted(f.key for f in state.findings.values() if f.source == REVIEW and f.status not in CLOSED)


def write(run_dir: str, state: RunState, meta: dict[str, Any], verdict: str) -> dict[str, str]:
    """Write the files of a finished run and return their paths."""
    detail, handoffs = meta.get("detail", {}), meta.get("handoffs", {})
    names = ("final.json", "handoffs.json", "summary.json", "report.md")
    paths = {name: os.path.join(run_dir, name) for name in names}
    left = open_review_keys(state)
    scope, rounds = meta["scope_label"], state.rounds_used
    store.write_json(paths["final.json"], findings_document(scope, rounds, [as_finding(k, dict(detail.get(k, {}), instruction=state.findings[k].instruction)) for k in left]))
    store.write_json(paths["handoffs.json"],
                     findings_document(scope, rounds, [as_finding(k, handoffs[k]) for k in sorted(handoffs)]))
    findings = [
        {"key": f.key, "source": f.source, "status": f.status, "attempts": f.attempts, "target": f.target,
         "left_as_is": f.left_as_is, "messages": detail.get(f.key, {}).get("messages", []),
         "fixer": detail.get(f.key, {}).get("fixer", "")}
        for f in sorted(state.findings.values(), key=lambda f: f.key)
    ]
    store.write_json(paths["summary.json"], {
        "run_id": meta["run_id"], "kind": meta["kind"], "steps": meta["steps"], "mode": meta["mode"],
        "verdict": verdict, "rounds": meta.get("rounds", []), "findings": findings, "notes": meta.get("notes", {}),
        "gate": meta.get("gate", {}), "links": meta.get("links", {}), "rejected": meta.get("rejected", 0),
        "unasked_changes": meta.get("unasked_changes", []), "noticed": meta.get("noticed", []),
    })
    counts: dict[str, int] = {}
    for f in state.findings.values():
        counts[f.status] = counts.get(f.status, 0) + 1
    lines = [
        f"# Run `{meta['run_id']}`: {verdict}", "",
        f"Scope {scope}; rounds used {state.rounds_used} of {state.cap}.", "",
        "| Round | P0 | P1 | P2 | Refused | Reviewers | Nodes read |", "|---|---|---|---|---|---|---|",
        *[f"| {r['round']} | {r['P0']} | {r['P1']} | {r['P2']} | {r['rejected']} | {r['reviewers']} | {r['read']} |"
          for r in meta.get("rounds", [])], "",
        "| Status | Findings |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(counts.items())], "",
        f"Handoffs to other steps: {len(handoffs)}. Findings refused at intake: {meta.get('rejected', 0)}.",
    ]
    sections = (
        ("Not closed", [f"{f['key']} ({f['status']}): {' / '.join(f['messages'])}" for f in findings if f["status"] not in CLOSED]),
        ("Left as is by the operator", [f["key"] for f in findings if f["left_as_is"]]),
        ("Settled", [f"{f['key']}: {f['fixer']}" for f in findings if f["status"] == SETTLED and not f["left_as_is"]]),
        ("Handoffs", [f"{k}: {(handoffs[k].get('messages') or [''])[0]}" for k in sorted(handoffs)]),
        ("Notes (P2)", [f"{k}: {v}" for k, v in sorted(meta.get("notes", {}).items())]),
        ("Changed without a finding", meta.get("unasked_changes", [])),
        ("Noticed by the fixer", meta.get("noticed", [])),
        ("Step gate", [f"step {s}: {r}" for s, r in sorted(meta.get("gate", {}).get("result", {}).items())]),
        ("Blocked by other steps", meta.get("gate", {}).get("blocked_by", [])),
        ("Waiting on open items", meta.get("gate", {}).get("waiting", [])),
        ("Suspect links that wait on a node above", meta.get("links", {}).get("waiting", [])),
        ("Coverage gaps", meta.get("links", {}).get("gaps", [])),
    )
    for title, values in sections:
        if values:
            lines += ["", f"## {title}", *[f"- {v}" for v in values]]
    store.write_text(paths["report.md"], "\n".join(lines) + "\n")
    return {"final": paths["final.json"], "handoffs": paths["handoffs.json"], "summary": paths["summary.json"],
            "report": paths["report.md"]}
