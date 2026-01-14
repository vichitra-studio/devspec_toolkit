
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


def collect_definitions_and_references(artifacts: dict) -> tuple[set[str], list[tuple[str, str]]]:
    """
    Generic traversal to find all ID definitions and references.
    
    Definition Heuristic:
    - Any field ending in '_id' (e.g., fr_id, api_id) is a definition.
    - Value must be a non-empty string.
    
    Reference Heuristic:
    - Lists named 'trace', 'targets', 'dependencies' containing objects with 'container'/'id'
    - Fields ending in '_ref' or '_refs'
    """
    known_ids = set()
    references = [] # list of (source_file, target_id)

    def scan_obj(obj, source_file, path=""):
        if isinstance(obj, dict):
            # Check for definitions
            for k, v in obj.items():
                if k.endswith("_id") and isinstance(v, str) and v:
                    known_ids.add(v)
                
                # Check for explicit references (trace/targets lists of objects with id)
                if k in ("trace", "targets", "dependencies") and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "id" in item:
                             references.append((source_file, item["id"]))
                
                # Check for direct references (field_ref: "target-id" or field_refs: ["id1", "id2"])
                if k.endswith("_ref") and isinstance(v, str):
                    references.append((source_file, v))
                elif k.endswith("_refs") and isinstance(v, list):
                    for ref_id in v:
                        if isinstance(ref_id, str):
                            references.append((source_file, ref_id))

            # Recurse
            for k, v in obj.items():
                scan_obj(v, source_file, path=f"{path}.{k}")

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                scan_obj(item, source_file, path=f"{path}[{i}]")

    for path, data in artifacts.items():
        scan_obj(data, path)
        
    return known_ids, references


def validate_trace_integrity(repo_root: str, spec_dir: str) -> list[str]:
    """Check for broken trace references (Generic Implementation)."""
    artifacts = {}
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = load_json(p)
                    artifacts[p] = data
                except (OSError, json.JSONDecodeError):
                    pass

    known_ids, references = collect_definitions_and_references(artifacts)

    # Validation
    errors = []
    for src, tgt in references:
        if tgt and tgt not in known_ids and not tgt.startswith("external:"): # Allow external refs hack
             errors.append(f"Broken Trace in {os.path.basename(src)}: Reference to '{tgt}' not found.")
    
    return errors

def build_trace_matrix(repo_root: str, spec_dir: str) -> dict:
    # Reusing the existing matrix logic for 00-09 core steps for visualization purposes
    # Generalized Matrix visualization is much harder without a schema, so we keep 
    # the core matrix logic "Classic" for now but ensure it doesn't crash on extensions.
    # The crucial fix was validate_trace_integrity, which is now generic.
    
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
        # Fuzzy matching schemas to be more robust
        if "04_fr_list" in schema:
            frs.extend(data.get("functional_requirements", []))
        if "05_interface_contracts" in schema:
            for a in data.get("apis", []):
                apis[a.get("api_id")] = a
        if "08_fixtures" in schema:
            fixtures.extend(data.get("fixtures", []))
        if "07_nfrs" in schema:
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

