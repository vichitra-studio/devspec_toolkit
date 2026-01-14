def validate_trace_integrity(repo_root: str, spec_dir: str) -> list[str]:
    """Check for broken trace references."""
    artifacts = {}
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = load_json(p)
                    # Use file path as fallback ID if id not present, but for known_ids we need specific schemas
                    artifacts[p] = data
                except (OSError, json.JSONDecodeError):
                    pass

    # Index Definitions and References
    known_ids = set()
    references = [] # list of (source_file, target_id)

    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        
        # FRs
        if schema.endswith("/04_fr_list.schema.json"):
            for fr in data.get("functional_requirements", []):
                if "fr_id" in fr: known_ids.add(fr["fr_id"])
                for t in fr.get("trace", []):
                    references.append((path, t.get("id")))

        # APIs
        if schema.endswith("/05_interface_contracts.schema.json"):
            for a in data.get("apis", []):
                if "api_id" in a: known_ids.add(a["api_id"])
        
        # Fixtures
        if schema.endswith("/08_fixtures.schema.json"):
            for f in data.get("fixtures", []):
                if "fixture_id" in f: known_ids.add(f["fixture_id"])
                for t in f.get("targets", []):
                    references.append((path, t.get("id")))

        # NFRs
        if schema.endswith("/07_nfrs.schema.json"):
            for n in data.get("nfrs", []):
                if "nfr_id" in n: known_ids.add(n["nfr_id"])
                for t in n.get("trace", []):
                     references.append((path, t.get("id")))

    # Validation
    errors = []
    for src, tgt in references:
        if tgt and tgt not in known_ids:
             errors.append(f"Broken Trace in {os.path.basename(src)}: Reference to '{tgt}' not found.")
    
    return errors
