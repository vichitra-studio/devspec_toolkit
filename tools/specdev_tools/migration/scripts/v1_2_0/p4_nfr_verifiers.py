"""``p4_nfr_verifiers``: an NFR that nothing verifies gets a worklist item (CD-22, ruling P21).

After the fixture conversion a node in play is verified when a fixture or a job names it in ``verifies``.  The NFR exemption
is gone, so each in-play NFR that no verifier names would be an E743.  This script writes nothing: it lists one item per such
NFR (step 12, ``blocking``): add a step-12 job whose ``verifies`` names the NFR, or a fixture that verifies it.  When a
job of the migrated tree names the NFR id in its own text (name, step names, commands) the item proposes that job as the
verifier: a candidate, never a written ``verifies``.  The artifact-level ``trace`` of step 12 is dropped and not read (P21).
"""

from __future__ import annotations

import json
import re

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.names import JOB, NFR, VERIFIES, link_targets
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items
from specdev_tools.trace.coverage import exemption

SCRIPT = ScriptSpec(id="p4_nfr_verifiers", phase=PHASE_CONTENT, requires=("p3_convert", "p3_remove"), touches=("extras",))

KIND = "nfr-verifier"
CI_STEP = "12"


def _names(text: str, node_id: str) -> bool:
    return re.search(rf"(?<![a-z0-9-]){re.escape(node_id)}(?![a-z0-9-])", text) is not None


def _items(ctx) -> list[WorklistItem]:
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    verified = {target for node in graph.nodes for target in link_targets(graph, node, VERIFIES)}
    jobs = [node for node in graph.nodes if node.kind == JOB]
    documents = graph.documents
    items = []
    for nfr in graph.nodes:
        if nfr.kind != NFR or exemption(nfr) is not None or nfr.id in verified:
            continue
        holders = [job.id for job in jobs if _names(json.dumps(_job_object(documents, job), ensure_ascii=False), nfr.id)]
        proposal = (f"job {', '.join(holders)} names {nfr.id} in its text: let it `verifies` the NFR, or add a fixture that verifies it" if holders
                    else "add a step-12 job whose `verifies` names this NFR, or add a fixture that verifies it")
        items.append(make_item(CI_STEP, KIND, nfr.id, audience="agent", blocking=True, evidence=f"{nfr.id} is in play and no fixture or job names it in verifies (E743 would report it)", proposal=proposal))
    return items


def _job_object(documents, job):
    """The JSON object of the job *job* in its document (its steps and names)."""
    entries = documents[job.file].get("jobs", [])
    return next((entry for entry in entries if isinstance(entry, dict) and entry.get("job_id") == job.id), {})


def detect(ctx) -> int:
    """NFRs without a verifier whose item is not listed yet."""
    return len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """List one item per unverified NFR; nothing is written to a step file."""
    listed = add_items(ctx, _items(ctx))
    return ScriptResult(edits=listed, worklist_items=listed, residue=(f"NFRs with no verifier listed: {listed}",))


def verify(before, after) -> list[Problem]:
    """No spec file but the worklist changed."""
    return [Problem(f"{rel} changed; the script only lists", rel) for rel in sorted(after.documents) if after.documents[rel] != before.documents.get(rel) and not rel.startswith("extras/")]
