
from __future__ import annotations
import os, json, collections

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_trace_matrix(repo_root: str, spec_dir: str) -> dict:
    # Collect step artifacts
    artifacts = {}
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = load_json(p)
                    artifacts[data.get("id", p)] = data
                except (OSError, json.JSONDecodeError):
                    pass

    # Index
    frs = []
    apis = {}
    fixtures = []
    nfrs = []
    for data in artifacts.values():
        schema = data.get("$schema", "")
        if schema.endswith("/04_fr_list.schema.json"):
            frs.extend(data.get("functional_requirements", []))
        if schema.endswith("/05_interface_contracts.schema.json"):
            for a in data.get("apis", []):
                apis[a.get("api_id")] = a
        if schema.endswith("/08_fixtures.schema.json"):
            fixtures.extend(data.get("fixtures", []))
        if schema.endswith("/07_nfrs.schema.json"):
            nfrs.extend(data.get("nfrs", []))

    # Build links
    fr_to_api = collections.defaultdict(set)
    api_to_fixture = collections.defaultdict(set)
    api_to_nfr = collections.defaultdict(set)
    for fr in frs:
        for t in fr.get("trace", []):
            if t.get("type") == "api":
                fr_to_api[fr["fr_id"]].add(t["id"])

    for fx in fixtures:
        for t in fx.get("targets", []):
            if t.get("type") == "api":
                api_to_fixture[t["id"]].add(fx["fixture_id"])

    for n in nfrs:
        for t in n.get("trace", []):
            if t.get("type") == "api":
                api_to_nfr[t["id"]].add(n["nfr_id"])

    # Emit matrix
    matrix = []
    for fr in frs:
        fr_id = fr["fr_id"]
        apirefs = sorted(fr_to_api.get(fr_id, []))
        row = {
            "fr_id": fr_id,
            "apis": apirefs,
            "fixtures": sorted({fx for api in apirefs for fx in api_to_fixture.get(api, set())}),
            "nfrs": sorted({n for api in apirefs for n in api_to_nfr.get(api, set())})
        }
        matrix.append(row)

    # Coverage summaries
    coverage = {
        "fr_total": len(frs),
        "fr_with_api": sum(1 for r in matrix if r["apis"]),
        "fr_with_fixture": sum(1 for r in matrix if r["fixtures"]),
        "fr_with_nfr": sum(1 for r in matrix if r["nfrs"]),
    }
    return {"matrix": matrix, "coverage": coverage}
