from typing import List, Dict, Any, Optional

def validate_step_03(
    instance: Dict[str, Any],
    toolkit_root: str,
    nfrs_data: Optional[Dict[str, Any]] = None,
    monitoring_data: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Validate Step 03 (Glossary) artifacts against deep logical constraints.
    
    Args:
        instance: The loaded JSON instance of the glossary.
        toolkit_root: Absolute path to the toolkit root.
        nfrs_data: Optional loaded NFRs data for coverage checking.
        monitoring_data: Optional loaded monitoring data for unit consistency.
        
    Returns:
        List of error strings. Empty list if valid.
    """
    errors = []
    
    # Get terms array
    terms = instance.get('terms', [])
    
    # Check for empty terms array (already covered by schema, but let's be explicit)
    if len(terms) == 0:
        errors.append("Terms array is empty")
    
    # Track unique term_id and term values (case-insensitive)
    seen_term_ids = set()
    seen_terms = set()
    
    for i, term in enumerate(terms):
        # Validate term_id uniqueness (case-insensitive)
        term_id = term.get('term_id')
        if term_id:
            term_id_lower = term_id.lower()
            if term_id_lower in seen_term_ids:
                errors.append(f"Duplicate term_id '{term_id}' at index {i}")
            seen_term_ids.add(term_id_lower)
        
        # Validate term uniqueness (case-insensitive)  
        term_text = term.get('term')
        if term_text:
            term_text_lower = term_text.lower()
            if term_text_lower in seen_terms:
                errors.append(f"Duplicate term '{term_text}' at index {i}")
            seen_terms.add(term_text_lower)
        
        # Validate optional fields are not empty strings
        domain = term.get('domain')
        if isinstance(domain, str) and domain == "":
            errors.append(f"Empty domain string at term index {i}")
            
        units = term.get('units')
        if isinstance(units, str) and units == "":
            errors.append(f"Empty units string at term index {i}")

    # Create lookup for coverage checks
    term_lookup = {term['term'].lower(): term for term in terms if 'term' in term}

    # Check coverage against NFRs if provided
    if nfrs_data and 'nfrs' in nfrs_data:
        for nfr in nfrs_data['nfrs']:
            metric_name = nfr.get('metric')
            if metric_name:
                # Check if the metric is defined in glossary
                if metric_name.lower() not in term_lookup:
                    errors.append(f"NFR metric '{metric_name}' not found in glossary")
                else:
                    # Check that it has units if required
                    term = term_lookup[metric_name.lower()]
                    units = term.get('units')
                    if not units:
                        errors.append(f"NFR metric '{metric_name}' missing units in glossary")
    
    # Check unit consistency with monitoring data if provided
    if monitoring_data and 'metrics' in monitoring_data:
        for metric in monitoring_data['metrics']:
            metric_name = metric.get('name')
            expected_units = metric.get('units')
            
            if metric_name and expected_units:
                if metric_name.lower() in term_lookup:
                    term = term_lookup[metric_name.lower()]
                    actual_units = term.get('units')
                    if actual_units and actual_units != expected_units:
                        errors.append(f"Unit mismatch for '{metric_name}': expected '{expected_units}', got '{actual_units}'")

    # Optional dataset coverage: stage-specific NFR lists.
    if nfrs_data and "stage_nfrs" in nfrs_data:
        for stage_data in nfrs_data.get("stage_nfrs", []):
            for nfr in stage_data.get("nfrs", []):
                metric_name = nfr.get("metric")
                if metric_name and metric_name.lower() not in term_lookup:
                    errors.append(
                        f"Stage metric '{metric_name}' not found in glossary (stage={stage_data.get('stage', 'unknown')})"
                    )

    # Optional monitoring dataset coverage: dashboard widgets / alerts.
    if monitoring_data and "dashboards" in monitoring_data:
        for dashboard in monitoring_data.get("dashboards", []):
            for widget in dashboard.get("widgets", []):
                metric_name = widget.get("metric")
                if metric_name and metric_name.lower() not in term_lookup:
                    errors.append(
                        f"Dashboard metric '{metric_name}' not found in glossary (dashboard={dashboard.get('name', 'unknown')})"
                    )

    return errors
