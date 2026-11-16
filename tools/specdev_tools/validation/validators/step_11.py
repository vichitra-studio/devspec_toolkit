from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...core.scope_helpers import as_list, dict_items, str_items
from ...core.errors import make_error, SpecError
from ...core.loaders import load_sibling_artifact, load_sibling_json
from ...validation._legacy_shim import is_parked_any_shape
from ...validation.linter_utils import check_no_duplicates


def validate_step_11(
    instance: dict[str, Any],
    toolkit_root: str,
    artifact_path: str | None = None,
) -> list[SpecError]:
    """Validate Step 11 (Red Team / Threat Modeling) logic.

    Checks threat_id uniqueness, API-to-threat coverage (W583: an API no threat ``threatens``) and
    invariant coverage (W615: a security invariant no threat is ``mitigated_by``). An API or invariant
    whose every linked FR is parked is exempt from both. The existence of the ids a threat names is
    not checked here. A wrong-typed value is left to the schema and never raises.
    """
    errors: list[SpecError] = []

    threats = as_list(instance.get("threats"))
    check_no_duplicates(threats, "threat_id", "threat_id", errors)
    for i, threat in enumerate(threats):
        if not isinstance(threat, dict):
            errors.append(make_error("E520", f"threats[{i}] is not an object: {threat!r}"))

    api_ids = _load_api_ids(toolkit_root, artifact_path)
    invariant_ids = _load_invariant_ids(toolkit_root, artifact_path)
    parked_fr_ids = _load_parked_fr_ids(toolkit_root, artifact_path)

    if api_ids is not None:
        api_fr_links = _load_fr_links_by_id(toolkit_root, artifact_path, "05", "apis", "api_id", _fr_ids_from_derives_from)
        errors.extend(_api_coverage_errors(_linked_ids(threats, "threatens"), api_ids, api_fr_links, parked_fr_ids))

    if invariant_ids is not None:
        invariant_fr_links = _load_fr_links_by_id(toolkit_root, artifact_path, "06", "rules", "inv_id", _fr_ids_from_constrains)
        security_ids = _load_security_invariant_ids(toolkit_root, artifact_path)
        errors.extend(
            _invariant_coverage_errors(_linked_ids(threats, "mitigated_by"), security_ids, invariant_fr_links, parked_fr_ids)
        )

    return errors


def _linked_ids(threats: list[Any], link_field: str) -> set[str]:
    """Every non-empty string named by *link_field* on the object entries of *threats*."""
    named: set[str] = set()
    for threat in threats:
        links = threat.get(link_field) if isinstance(threat, dict) else None
        if isinstance(links, list):
            named.update(link for link in links if isinstance(link, str) and link)
    return named


def _api_coverage_errors(
    threatened_ids: set[str],
    api_ids: set[str],
    api_fr_links: dict[str, set[str]],
    parked_fr_ids: set[str],
) -> list[SpecError]:
    """W583 for each API no threat ``threatens``, except an API that only derives from parked FRs."""
    return [
        make_error("W583", f"API_UNCOVERED_BY_THREAT {api_id} has no corresponding threat in Step 11")
        for api_id in sorted(api_ids)
        if api_id not in threatened_ids
        and not _only_links_parked_frs(api_fr_links.get(api_id, set()), parked_fr_ids)
    ]


def _invariant_coverage_errors(
    mitigating_ids: set[str],
    security_invariant_ids: set[str],
    invariant_fr_links: dict[str, set[str]],
    parked_fr_ids: set[str],
) -> list[SpecError]:
    """W615 for each security invariant no threat is ``mitigated_by``, except one that only constrains parked FRs."""
    return [
        make_error(
            "W615",
            f"INVARIANT_UNEXERCISED_BY_THREAT {inv_id} has a risk_category_ref "
            "but no threat mitigated_by references it",
        )
        for inv_id in sorted(security_invariant_ids)
        if inv_id not in mitigating_ids
        and not _only_links_parked_frs(invariant_fr_links.get(inv_id, set()), parked_fr_ids)
    ]


def _load_api_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load API IDs from step 05, or ``None`` when step 05 is absent (the caller skips the check)."""
    return load_sibling_artifact(artifact_path or "", "05", "apis", "api_id", fallback_root=toolkit_root)


def _load_invariant_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str] | None:
    """Load invariant IDs from step 06, or ``None`` when step 06 is absent (the caller skips the check)."""
    return load_sibling_artifact(artifact_path or "", "06", "rules", "inv_id", fallback_root=toolkit_root)


def _load_entities(
    toolkit_root: str, artifact_path: str | None, step_prefix: str, array_key: str
) -> list[dict[str, Any]]:
    """The object entries of the sibling step artifact's *array_key* array; empty when the step is absent.

    Resolves the sibling with ``load_sibling_json`` (beside the artifact first, then ``<toolkit_root>/spec``;
    the first candidate that parses wins).
    """
    data = load_sibling_json(artifact_path, step_prefix, fallback_root=toolkit_root)
    items = data.get(array_key) if data is not None else None
    return dict_items(items)


def _load_security_invariant_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str]:
    """Load the set of step-06 inv_ids that carry a non-empty risk_category_ref (the invariants W615 checks).

    Returns an empty set when step 06 is absent or contains no such invariants.
    """
    return {
        str(rule["inv_id"])
        for rule in _load_entities(toolkit_root, artifact_path, "06", "rules")
        if rule.get("inv_id") and rule.get("risk_category_ref")
    }


def _load_parked_fr_ids(toolkit_root: str, artifact_path: str | None = None) -> set[str]:
    """Load the set of step-04 fr_ids that are parked (``is_parked_any_shape``: a 1.1.1 FR parks with
    ``priority: wont-have``). Returns an empty set when step 04 is absent or contains no such FRs."""
    return {
        str(fr["fr_id"])
        for fr in _load_entities(toolkit_root, artifact_path, "04", "functional_requirements")
        if fr.get("fr_id") and is_parked_any_shape(fr)
    }


def _fr_ids_from_constrains(entity: dict[str, Any]) -> set[str]:
    """Every non-empty string in an entity's ``constrains``, not filtered to FR ids.

    An invariant's ``constrains`` lists FRs, APIs, components and connections; an id that is not a
    parked FR keeps the invariant out of the "only parked FRs" subset test of ``_only_links_parked_frs``."""
    return _non_empty_strings(entity.get("constrains"))


def _fr_ids_from_derives_from(entity: dict[str, Any]) -> set[str]:
    """Every non-empty string in an entity's ``derives_from``, not filtered to FR ids.

    An API's ``derives_from`` lists FRs only; an id that is not a parked FR keeps the entity out of the
    "only parked FRs" subset test of ``_only_links_parked_frs``."""
    return _non_empty_strings(entity.get("derives_from"))


def _non_empty_strings(value: Any) -> set[str]:
    """The non-empty strings of *value* when it is a list; an empty set for any other type."""
    return {item for item in str_items(value) if item}


def _load_fr_links_by_id(
    toolkit_root: str,
    artifact_path: str | None,
    step_prefix: str,
    array_key: str,
    id_field: str,
    fr_ids_of: Callable[[dict[str, Any]], set[str]],
) -> dict[str, set[str]]:
    """Load {entity_id: {linked fr_ids}} from a step artifact's *array_key* entities.

    Used to walk each API's/invariant's link back to its FR(s), so callers can determine whether an
    entity's *only* FR(s) are parked. *fr_ids_of* extracts the linked ids from one entity
    (``_fr_ids_from_derives_from`` for an API, ``_fr_ids_from_constrains`` for an invariant).
    Returns an empty dict when the upstream step is absent.
    """
    return {
        str(entity[id_field]): fr_ids_of(entity)
        for entity in _load_entities(toolkit_root, artifact_path, step_prefix, array_key)
        if entity.get(id_field)
    }


def _only_links_parked_frs(linked_ids: set[str], parked_fr_ids: set[str]) -> bool:
    """True when an entity has at least one link and every linked id is a parked FR.

    An entity with no link at all is not excluded here: there is nothing parked to exempt it on.
    """
    return bool(linked_ids) and linked_ids.issubset(parked_fr_ids)
