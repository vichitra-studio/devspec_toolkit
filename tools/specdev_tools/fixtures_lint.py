
from __future__ import annotations
import os, json

def lint_fixtures(spec_dir: str) -> list[str]:
    errors = []
    apis = set()
    frs = set()
    invariants = set()
    nfrs = set()
    fixtures = []
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = json.load(open(p, "r", encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                s = data.get("$schema","")
                if s.endswith("/05_interface_contracts.schema.json"):
                    for a in data.get("apis", []):
                        if a.get("api_id"):
                            apis.add(a["api_id"])
                if s.endswith("/08_fixtures.schema.json"):
                    fixtures.extend(data.get("fixtures", []))
                if s.endswith("/04_fr_list.schema.json"):
                    for item in data.get("functional_requirements", []):
                        if item.get("fr_id"): frs.add(item["fr_id"])
                if s.endswith("/06_invariants.schema.json"):
                    for item in data.get("rules", []):
                        if item.get("inv_id"): invariants.add(item["inv_id"])
                if s.endswith("/07_nfrs.schema.json"):
                    for item in data.get("nfrs", []):
                        if item.get("nfr_id"): nfrs.add(item["nfr_id"])

    for fx in fixtures:
        fid = fx.get("fixture_id","<unknown>")
        targets = fx.get("targets", [])
        if not targets:
            errors.append(f"{fid}: missing targets")
            continue
        for t in targets:
            # Check if target is a proper traceRef object before accessing its properties
            if isinstance(t, dict):
                tid = t.get("id", "")
                ttype = t.get("type", "")
                
                if ttype == "api" and tid not in apis:
                    errors.append(f"{fid}: targets unknown API '{tid}'")
                elif ttype == "fr" and tid not in frs:
                    errors.append(f"{fid}: targets unknown FR '{tid}'")
                elif ttype == "invariant" and tid not in invariants:
                    errors.append(f"{fid}: targets unknown Invariant '{tid}'")
                elif ttype == "nfr" and tid not in nfrs:
                    errors.append(f"{fid}: targets unknown NFR '{tid}'")
        expected = fx.get("expected")
        if "input" not in fx or expected is None:
            errors.append(f"{fid}: missing input/expected")
            continue
        if isinstance(expected, dict):
            status = expected.get("status")
            if not isinstance(status, int) or status < 100 or status > 599:
                errors.append(f"{fid}: expected.status must be an HTTP status (100-599)")
            body = expected.get("body")
            if body is not None and not isinstance(body, (dict, list, str, int, bool, float)):
                errors.append(f"{fid}: expected.body must be JSON serializable")
            headers = expected.get("headers")
            if headers is not None and not isinstance(headers, dict):
                errors.append(f"{fid}: expected.headers must be an object")
        else:
            # Add warning if mode is contract or api but expected is not a dictionary
            mode = fx.get("mode")
            if mode in ["contract", "api"]:
                errors.append(f"{fid}: expected should be a dictionary for mode '{mode}' but got {type(expected).__name__}")
    return errors
