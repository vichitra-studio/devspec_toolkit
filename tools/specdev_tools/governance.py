
from __future__ import annotations
import os, json, re

def load_governance(spec_dir: str) -> dict | None:
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = json.load(open(p, "r", encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if data.get("$schema","").endswith("/10_governance.schema.json"):
                    return data
    return None

def check_commit_message(spec_dir: str, message: str) -> list[str]:
    gov = load_governance(spec_dir) or {}
    rules = gov.get("commit_message_rules") or {}
    errs = []
    require_ids = rules.get("require_spec_ids")
    pattern = rules.get("pattern")
    if require_ids and pattern:
        if not re.match(pattern, message or ""):
            errs.append("commit message does not match governance pattern")
    return errs
