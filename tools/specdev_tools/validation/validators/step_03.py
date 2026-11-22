from __future__ import annotations

from typing import Dict, Any, Optional

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import as_dict, dict_items

def validate_step_03(
    instance: Dict[str, Any],
    toolkit_root: str,
    nfrs_data: Optional[Dict[str, Any]] = None,
    monitoring_data: Optional[Dict[str, Any]] = None
) -> list[SpecError]:
    """
    Validate Step 03 (Glossary) artifacts against deep logical constraints.

    Args:
        instance: The loaded JSON instance of the glossary.
        toolkit_root: Absolute path to the toolkit root.
        nfrs_data: Optional loaded NFRs data for coverage checking.
        monitoring_data: Optional loaded monitoring data for unit consistency.

    Returns:
        List of SpecError objects. Empty list if valid.
    """
    errors: list[SpecError] = []

    # Get terms array
    terms = dict_items(instance.get('terms'))

    # Check for empty terms array (already covered by schema, but let's be explicit)
    if len(terms) == 0:
        errors.append(make_error("E520", "Terms array is empty"))

    # Track unique term values (case-insensitive); duplicate term_id values are the graph's E704
    seen_terms = set()

    for i, term in enumerate(terms):
        # Validate term uniqueness (case-insensitive)
        term_text = term.get('term')
        if isinstance(term_text, str) and term_text:
            term_text_lower = term_text.lower()
            if term_text_lower in seen_terms:
                errors.append(make_error("E520", f"Duplicate term '{term_text}' at index {i}"))
            seen_terms.add(term_text_lower)

        # Validate optional fields are not empty strings
        domain = term.get('domain')
        if isinstance(domain, str) and domain == "":
            errors.append(make_error("E520", f"Empty domain string at term index {i}"))

        units = term.get('units')
        if isinstance(units, str) and units == "":
            errors.append(make_error("E520", f"Empty units string at term index {i}"))

    # Create lookup for coverage checks
    term_lookup = {term['term'].lower(): term for term in terms if isinstance(term.get('term'), str)}

    # Check coverage against NFRs if provided
    nfrs_data = as_dict(nfrs_data)
    monitoring_data = as_dict(monitoring_data)
    if 'nfrs' in nfrs_data:
        for nfr in dict_items(nfrs_data['nfrs']):
            metric_name = nfr.get('metric')
            if isinstance(metric_name, str) and metric_name:
                # Check if the metric is defined in glossary
                if metric_name.lower() not in term_lookup:
                    errors.append(make_error("E590", f"NFR metric '{metric_name}' not found in glossary"))
                else:
                    # Check that it has units if required
                    term = term_lookup[metric_name.lower()]
                    units = term.get('units')
                    if not units:
                        errors.append(make_error("E520", f"NFR metric '{metric_name}' missing units in glossary"))

    # Check unit consistency with monitoring data if provided
    if 'metrics' in monitoring_data:
        for metric in dict_items(monitoring_data['metrics']):
            metric_name = metric.get('name')
            expected_units = metric.get('units')

            if isinstance(metric_name, str) and metric_name and expected_units:
                if metric_name.lower() in term_lookup:
                    term = term_lookup[metric_name.lower()]
                    actual_units = term.get('units')
                    if actual_units and actual_units != expected_units:
                        errors.append(make_error("E520", f"Unit mismatch for '{metric_name}': expected '{expected_units}', got '{actual_units}'"))

    # Optional dataset coverage: stage-specific NFR lists.
    if "stage_nfrs" in nfrs_data:
        for stage_data in dict_items(nfrs_data.get("stage_nfrs")):
            for nfr in dict_items(stage_data.get("nfrs")):
                metric_name = nfr.get("metric")
                if isinstance(metric_name, str) and metric_name and metric_name.lower() not in term_lookup:
                    errors.append(
                        make_error("E590", f"Stage metric '{metric_name}' not found in glossary (stage={stage_data.get('stage', 'unknown')})")
                    )

    # Optional monitoring dataset coverage: dashboard widgets / alerts.
    if "dashboards" in monitoring_data:
        for dashboard in dict_items(monitoring_data.get("dashboards")):
            for widget in dict_items(dashboard.get("widgets")):
                metric_name = widget.get("metric")
                if isinstance(metric_name, str) and metric_name and metric_name.lower() not in term_lookup:
                    errors.append(
                        make_error("E590", f"Dashboard metric '{metric_name}' not found in glossary (dashboard={dashboard.get('name', 'unknown')})")
                    )

    return errors
