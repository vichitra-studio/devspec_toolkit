
from __future__ import annotations
import os, json

def lint_fixtures(spec_dir: str) -> list[str]:
    errors = []
    apis = set()
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

    for fx in fixtures:
        fid = fx.get("fixture_id","<unknown>")
        targets = fx.get("targets", [])
        if not targets:
            errors.append(f"{fid}: missing targets")
            continue
        for t in targets:
            if t.get("type") == "api" and t.get("id") not in apis:
                errors.append(f"{fid}: targets unknown API '{t.get('id')}'")
        expected = fx.get("expected")
        if "input" not in fx or expected is None:
            errors.append(f"{fid}: missing input/expected")
            continue
        status = expected.get("status")
        if not isinstance(status, int) or status < 100 or status > 599:
            errors.append(f"{fid}: expected.status must be an HTTP status (100-599)")
        body = expected.get("body")
        if body is not None and not isinstance(body, (dict, list, str, int, bool, float)):
            errors.append(f"{fid}: expected.body must be JSON serializable")
        headers = expected.get("headers")
        if headers is not None and not isinstance(headers, dict):
            errors.append(f"{fid}: expected.headers must be an object")
    return errors
