"""The end of a run: ``final.json`` and ``handoffs.json`` (findings documents), ``summary.json`` and ``report.md``."""

from __future__ import annotations

import os
import time
from typing import Any

from specdev_tools.loop import machine, store
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


def stop_rule(state: RunState) -> dict[str, Any]:
    """The rule this run stops by, for its summary and report: the values are the run's own."""
    blocking, attempts = list(machine.BLOCKING), machine.MAX_ATTEMPTS
    at_cap = "the operator is asked" if state.kind in machine.CODE_KINDS else "it ends HALT(cap)"
    parked = "ends the run HALT(stuck)" if state.defer else "is put to the operator"
    text = (f"the run converges when every node of the scope was read in its current content and no "
            f"{' or '.join(blocking)} finding is open (a P2 is a note); at {state.cap} rounds {at_cap}; "
            f"a finding whose fix failed {attempts} times {parked}; when a fix changed the scope after the round that read all "
            f"of it, one fresh reviewer reads the whole scope once more before the run converges, if a round is left "
            f"under the cap.")
    if state.mode == "review-only":
        text = (f"review-only: one round and nothing is fixed; CLEAN when no {' or '.join(blocking)} finding is "
                f"raised, else FINDINGS (a P2 is a note).")
    return {"blocking": blocking, "cap": state.cap, "max_attempts": attempts, "defer": state.defer,
            "readers": state.readers, "final_read": state.final_read, "text": text}


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
        "stop_rule": stop_rule(state), "recorded_items": meta.get("recorded_items", []),
        "strength_changes": meta.get("strength_changes", []), "fix_sizes": meta.get("fix_sizes", []),
    })
    counts: dict[str, int] = {}
    for f in state.findings.values():
        counts[f.status] = counts.get(f.status, 0) + 1
    lines = [
        f"# Run `{meta['run_id']}`: {verdict}", "",
        f"Scope {scope}; rounds used {state.rounds_used} of {state.cap}.", "",
        f"Stop rule: {stop_rule(state)['text']}", "",
        "| Round | P0 | P1 | P2 | Refused | Reviewers | Nodes read |", "|---|---|---|---|---|---|---|",
        *[f"| {r['round']}{' (full re-read)' if r.get('final_read') else ''} | {r['P0']} | {r['P1']} | {r['P2']} | {r['rejected']} | {r['reviewers']} | {r['read']} |"
          for r in meta.get("rounds", [])], "",
        "| Status | Findings |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(counts.items())], "",
        f"Handoffs to other steps: {len(handoffs)}. Findings refused at intake: {meta.get('rejected', 0)}.",
    ]
    if verdict == "CONVERGED" and state.rounds_used > 1 and not state.final_read and state.full_read != machine._reviewed(state):
        lines += ["", "No full re-read before this verdict: the run was at its cap. The last rounds read only what a fix changed."]
    sections = (
        ("Not closed", [f"{f['key']} ({f['status']}): {' / '.join(f['messages'])}" for f in findings if f["status"] not in CLOSED]),
        ("Left as is by the operator", [f["key"] for f in findings if f["left_as_is"]]),
        ("Settled", [f"{f['key']}: {f['fixer']}" for f in findings if f["status"] == SETTLED and not f["left_as_is"]]),
        ("Handoffs", [f"{k}: {(handoffs[k].get('messages') or [''])[0]}" for k in sorted(handoffs)]),
        ("Notes (P2)", [f"{k}: {v}" for k, v in sorted(meta.get("notes", {}).items())]),
        ("Open items recorded by a fixer", meta.get("recorded_items", [])),
        ("Changed without a finding", meta.get("unasked_changes", [])),
        ("Requirement keywords a fix changed", meta.get("strength_changes", [])),
        ("Size of each fix", [f"fix {x['dispatch']}: {x['findings']} findings, {x['added']} bytes added, {x['removed']} removed"
                              for x in meta.get("fix_sizes", [])]),
        ("Noticed by the fixer", meta.get("noticed", [])),
        ("Step gate", [f"step {s}: {r}" for s, r in sorted(meta.get("gate", {}).get("result", {}).items())]),
        ("Warnings new since the base (they do not block)", meta.get("gate", {}).get("new_warnings", [])),
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
