
from __future__ import annotations
import os, json, collections, re

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_definitions_and_references(artifacts: dict) -> tuple[set[str], list[tuple[str, str]]]:
    """
    Generic traversal to find all ID definitions and references.
    
    Definition Heuristic:
    - Any field ending in '_id' (e.g., fr_id, api_id) is a definition.
    - Field 'id' is a definition UNLESS it appears in a reference list context.
    - Value must be a non-empty string.
    
    Reference Heuristic:
    - Lists named 'trace', 'targets', 'dependencies', 'deliverables', 'links', 'spec_refs' containing objects with 'id'
    - Fields ending in '_ref' or '_refs'
    """
    known_ids = set()
    references = [] # list of (source_file, target_id)

    # Contexts where 'id' is a REFERENCE, not a definition
    REFERENCE_CONTEXTS = {
        "trace", "targets", "deliverables", "links", "spec_refs", "seed_refs", "ref", "refs"
    }

    def scan_obj(obj, source_file, path="", parent_key=None):
        if isinstance(obj, dict):
            # Check for definitions
            for k, v in obj.items():
                # 1. Standard definition pattern (*_id)
                if k.endswith("_id") and isinstance(v, str) and v:
                    known_ids.add(v)
                
                # 2. 'id' field is a definition unless parent is a reference list
                elif k == "id" and isinstance(v, str) and v:
                    # Check if parent key implies this is a reference container
                    if parent_key not in REFERENCE_CONTEXTS:
                        known_ids.add(v)
                
                # Check for explicit references (lists of objects with id)
                if k in REFERENCE_CONTEXTS and isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "id" in item:
                             references.append((source_file, item["id"]))
                
                # Check for direct references (field_ref: "target-id" or field_refs: ["id1", "id2"])
                # Exclude evidence_ref - it's for evidence binding metadata, not spec traceability
                if k.endswith("_ref") and k != "evidence_ref" and isinstance(v, str):
                    references.append((source_file, v))
                elif k.endswith("_refs") and isinstance(v, list):
                    for ref_id in v:
                        if isinstance(ref_id, str):
                            references.append((source_file, ref_id))

                # Special case for Step 14 source_milestones (list of strings)
                if k == "source_milestones" and isinstance(v, list):
                    for ref_id in v:
                        if isinstance(ref_id, str):
                            references.append((source_file, ref_id))

            # Recurse
            for k, v in obj.items():
                # Pass 'k' as parent_key for the children
                scan_obj(v, source_file, path=f"{path}.{k}", parent_key=k)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                # Keep the same parent_key for items in a list (e.g. parent is "trace", items are trace objects)
                scan_obj(item, source_file, path=f"{path}[{i}]", parent_key=parent_key)

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
        # Validate target existence
        # Allow external refs, file paths, and git refs hacks
        if tgt and tgt not in known_ids and not (
            tgt.startswith("external:") or 
            tgt.startswith("file:") or 
            tgt.startswith("refs/")
        ):
             errors.append(f"Broken Trace in {os.path.basename(src)}: Reference to '{tgt}' not found.")

    # Step 02 system sketch checks
    capability_ids = set()
    for data in artifacts.values():
        schema = data.get("$schema", "")
        if "01_capabilities" in schema:
            for cap in data.get("capabilities", []):
                if cap.get("capability_id"):
                    capability_ids.add(cap["capability_id"])

    schema_ref_re = re.compile(r"^(?:-tbd|(file://|https://|glossary:|api:).+)$")
    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        if "02_system_sketch" not in schema:
            continue

        components = data.get("components", [])
        connections = data.get("connections", [])

        component_ids = []
        component_types = {}
        for comp in components:
            comp_id = comp.get("component_id")
            if comp_id:
                component_ids.append(comp_id)
                component_types[comp_id] = comp.get("type")

        seen = set()
        for comp_id in component_ids:
            if comp_id in seen:
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: Duplicate component_id '{comp_id}'."
                )
            seen.add(comp_id)

        component_id_set = set(component_ids)
        for idx, conn in enumerate(connections):
            source = conn.get("from")
            target = conn.get("to")
            if source and source not in component_id_set:
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: connection[{idx}] from '{source}' not found."
                )
            if target and target not in component_id_set:
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: connection[{idx}] to '{target}' not found."
                )

            schema_ref = conn.get("schema_ref")
            if schema_ref and not schema_ref_re.match(schema_ref):
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: connection[{idx}] schema_ref '{schema_ref}' is invalid."
                )

            if (
                (source and component_types.get(source) == "external")
                or (target and component_types.get(target) == "external")
            ):
                trust_boundary = conn.get("trust_boundary")
                if trust_boundary == "internal":
                    errors.append(
                        f"Step 02 Integrity in {os.path.basename(path)}: connection[{idx}] uses internal trust_boundary with external component."
                    )

        if capability_ids:
            traced = set()
            for comp in components:
                # Check both trace (standard) and trace_refs (legacy/alt)
                traces = (comp.get("trace") or []) + (comp.get("trace_refs") or [])
                for trace in traces:
                    trace_id = trace.get("id")
                    trace_type = trace.get("type")
                    if not trace_id:
                        continue
                    if trace_type in ("doc", "capability"):
                        traced.add(trace_id)
                    elif trace_id in capability_ids:
                        errors.append(
                            f"Step 02 Integrity in {os.path.basename(path)}: Capability trace_refs must use type 'doc' or 'capability' for '{trace_id}'."
                        )
            missing = sorted(capability_ids - traced)
            if missing:
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: Missing capability coverage {', '.join(missing)}."
                )

        for comp in components:
            if comp.get("type") != "external":
                continue
            tags = comp.get("tags", []) or []
            if "external-dependency" not in tags:
                errors.append(
                    f"Step 02 Integrity in {os.path.basename(path)}: external component '{comp.get('component_id')}' lacks external-dependency tag."
                )

    # Step 03 glossary checks
    glossary_term_ids = set()
    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        if "03_glossary" not in schema:
            continue
        for term in data.get("terms", []):
            if term.get("term_id"):
                glossary_term_ids.add(term.get("term_id").lower())

    for path, data in artifacts.items():
        schema = data.get("$schema", "")
        
        # FR Coverage Check against Glossary
        if "04_fr_list" in schema:
            for fr in data.get("functional_requirements", []):
                for trace in fr.get("trace", []) or []:
                    trace_type = trace.get("type")
                    trace_id = trace.get("id")
                    
                    if not trace_id:
                        continue
                        
                    # explicit glossary trace or implicit ID pattern
                    if trace_type == "glossary" or trace_id.startswith("term-"):
                        if trace_id.lower() not in glossary_term_ids:
                             errors.append(
                                f"Step 04 Integrity in {os.path.basename(path)}: FR '{fr.get('fr_id')}' references unknown glossary term '{trace_id}'."
                             )
                    
                    # Capability Trace Coverage
                    if trace_type == "capability":
                        if trace_id not in capability_ids:
                             errors.append(
                                f"Step 04 Integrity in {os.path.basename(path)}: FR '{fr.get('fr_id')}' references unknown capability '{trace_id}'."
                             )

        if "03_glossary" not in schema:
            continue

        # Validate glossary integrity
        terms = data.get("terms", [])
        
        # Check for empty terms array
        if len(terms) == 0:
            errors.append(f"Step 03 Integrity in {os.path.basename(path)}: Empty terms array")
        
        # Check for duplicate term_ids and terms (case-insensitive)
        seen_term_ids = set()
        seen_terms = set()
        
        for i, term in enumerate(terms):
            term_id = term.get("term_id")
            if term_id:
                term_id_lower = term_id.lower()
                if term_id_lower in seen_term_ids:
                    errors.append(
                        f"Step 03 Integrity in {os.path.basename(path)}: Duplicate term_id '{term_id}' at index {i}"
                    )
                seen_term_ids.add(term_id_lower)
            
            term_text = term.get("term")
            if term_text:
                term_text_lower = term_text.lower()
                if term_text_lower in seen_terms:
                    errors.append(
                        f"Step 03 Integrity in {os.path.basename(path)}: Duplicate term '{term_text}' at index {i}"
                    )
                seen_terms.add(term_text_lower)
            
            # Check that optional fields are not empty strings
            domain = term.get("domain")
            if isinstance(domain, str) and domain == "":
                errors.append(
                    f"Step 03 Integrity in {os.path.basename(path)}: Empty domain string at term index {i}"
                )
                
            units = term.get("units")
            if isinstance(units, str) and units == "":
                errors.append(
                    f"Step 03 Integrity in {os.path.basename(path)}: Empty units string at term index {i}"
                )
    
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

    # Index core specs
    frs = []
    apis = {}
    fixtures = []
    nfrs = []
    threats = []
    
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
        if "11_redteam" in schema:
            threats.extend(data.get("threats", []))

    # Index extension files
    extensions = []
    for data in artifacts.values():
        schema = data.get("$schema", "")
        # Check if this is an extension file (ext_[0-9]{2}_)
        if "extension_generator" in schema or any(fn.startswith("ext_") for fn in artifacts.keys() if fn.endswith(".json")):
            # Add extensions to the index
            if "extensions" in data:
                extensions.extend(data.get("extensions", []))

    # Build links
    fr_to_api = collections.defaultdict(set)
    api_to_fixture = collections.defaultdict(set)
    api_to_nfr = collections.defaultdict(set)
    fr_to_nfr = collections.defaultdict(set)
    api_to_threat = collections.defaultdict(set)

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
            elif t.get("type") == "fr":
                fr_to_nfr[t["id"]].add(n["nfr_id"])

    # Link Threats to APIs
    for th in threats:
        for t in th.get("target_ids", []):
            if t.get("type") == "api":
                api_to_threat[t["id"]].add(th["threat_id"])

    # Emit matrix
    matrix = []
    for fr in frs:
        fr_id = fr["fr_id"]
        apirefs = sorted(fr_to_api.get(fr_id, []))
        
        # Collect NFRs from both direct FR traces and indirect API traces
        direct_nfrs = fr_to_nfr.get(fr_id, set())
        indirect_nfrs = {n for api in apirefs for n in api_to_nfr.get(api, set())}
        
        # Collect Threats via API links
        associated_threats = {th for api in apirefs for th in api_to_threat.get(api, set())}

        row = {
            "fr_id": fr_id,
            "apis": apirefs,
            "fixtures": sorted({fx for api in apirefs for fx in api_to_fixture.get(api, set())}),
            "nfrs": sorted(direct_nfrs | indirect_nfrs),
            "threats": sorted(associated_threats)
        }
        matrix.append(row)

    # Coverage summaries
    coverage = {
        "fr_total": len(frs),
        "fr_with_api": sum(1 for r in matrix if r["apis"]),
        "fr_with_fixture": sum(1 for r in matrix if r["fixtures"]),
        "fr_with_nfr": sum(1 for r in matrix if r["nfrs"]),
        "fr_with_threat": sum(1 for r in matrix if r["threats"]),
        "scaffolds_found": len([a for a in artifacts.values() if "15_scaffold" in a.get("$schema", "")]),
    }
    
    # Add extensions to the result for traceability
    result = {"matrix": matrix, "coverage": coverage}
    
    # Add extension information if available
    if extensions:
        result["extensions"] = extensions

    integrity_errors = validate_trace_integrity(repo_root, spec_dir)
    if integrity_errors:
        result["integrity_errors"] = integrity_errors
    
    return result
