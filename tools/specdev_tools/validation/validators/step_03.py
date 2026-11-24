from __future__ import annotations

from typing import Dict, Any, Optional

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import as_dict, dict_items

def validate_step_03(
    instance: Dict[str, Any],
    toolkit_root: str,
    nfrs_data: Optional[Dict[str, Any]] = None,
) -> list[SpecError]:
    """
    Validate Step 03 (Glossary) artifacts against deep logical constraints.

    Args:
        instance: The loaded JSON instance of the glossary.
        toolkit_root: Absolute path to the toolkit root.
        nfrs_data: Optional loaded NFRs data for coverage checking.

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

    return errors
