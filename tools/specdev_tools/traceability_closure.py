from __future__ import annotations
import json
import os
from typing import Any

SPEC_FILES = {
    "capabilities": "01_capabilities.json",
    "frs": "04_functional_requirements.json",
    "roadmap": "14_roadmap.json",
    "impl_planner": "16a_impl_planner.json",
}


def check_traceability_closure(spec_dir: str, repo_root: str | None = None) -> list[str]:
    errors: list[str] = []

    # Resolve spec_dir relative to repo_root if it's a relative path
    if repo_root and not os.path.isabs(spec_dir):
        spec_dir = os.path.join(repo_root, spec_dir)

    data: dict[str, Any] = {}
    for key, filename in SPEC_FILES.items():
        path = os.path.join(spec_dir, filename)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data[key] = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    capability_ids = {c.get("capability_id") for c in data["capabilities"].get("capabilities", []) if c.get("capability_id")}

    fr_traced_caps: set[str] = set()
    fr_ids: set[str] = set()
    for fr in data["frs"].get("functional_requirements", []):
        if "fr_id" in fr:
            fr_ids.add(fr["fr_id"])
        for cap_ref in fr.get("trace", []):
            if isinstance(cap_ref, dict) and cap_ref.get("type") == "capability" and "id" in cap_ref:
                fr_traced_caps.add(cap_ref["id"])

    milestone_fr_refs: set[str] = set()
    milestone_ids: set[str] = set()
    milestone_task_ids: dict[str, list[str]] = {}
    for ms in data["roadmap"].get("milestones", []):
        ms_id = ms.get("milestone_id")
        if ms_id:
            milestone_ids.add(ms_id)
            milestone_task_ids[ms_id] = [t.get("task_id") for t in ms.get("tasks", []) if t.get("task_id")]
        for fr_ref in ms.get("fr_refs", []):
            milestone_fr_refs.add(fr_ref)

    checklist_milestone_refs: set[str] = set()
    impl_data = data["impl_planner"]
    checklist = impl_data.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
    
    checklist_task_refs = set()
    for item in checklist:
        spec_ref = item.get("spec_ref", {})
        if isinstance(spec_ref, dict) and "id" in spec_ref:
            checklist_task_refs.add(spec_ref["id"])

    for ms_id, tasks in milestone_task_ids.items():
        if any(t_id in checklist_task_refs for t_id in tasks):
            checklist_milestone_refs.add(ms_id)

    for cap_id in sorted(capability_ids - fr_traced_caps):
        errors.append(f"E560 TRACEABILITY_GAP capability_without_fr {cap_id}")

    for fr_id in sorted(fr_ids - milestone_fr_refs):
        errors.append(f"E560 TRACEABILITY_GAP fr_without_milestone {fr_id}")

    for ms_id in sorted(milestone_ids - checklist_milestone_refs):
        errors.append(f"E560 TRACEABILITY_GAP milestone_without_checklist {ms_id}")

    return errors
