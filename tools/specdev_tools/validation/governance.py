
from __future__ import annotations
import os, json, re

from ..core.errors import SpecError, make_error

def load_governance(spec_dir: str) -> dict | None:
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                
                # Check by filename pattern (standard)
                if fn.startswith("10_"):
                    return data
                
                # Fallback: check by ID pattern
                if isinstance(data, dict) and data.get("id", "").startswith("governance-"):
                    return data
    return None

def check_commit_message(spec_dir: str, message: str) -> list[SpecError]:
    gov = load_governance(spec_dir) or {}
    rules = gov.get("commit_message_rules") or {}
    errs: list[SpecError] = []
    require_ids = rules.get("require_spec_ids")
    pattern = rules.get("pattern")
    custom_msg = rules.get("error_message")
    if require_ids and pattern:
        if not re.match(pattern, message or ""):
            if custom_msg:
                errs.append(make_error("E303", f"Commit message mismatch. {custom_msg}"))
            else:
                errs.append(make_error("E303", f"Commit message mismatch. Must match regex: '{pattern}' (defined in spec/10_governance.json)"))
    return errs
