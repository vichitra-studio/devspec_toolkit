"""``p4_third_party``: third parties from ``tech_stack`` and the external components (DOC "Third-party", DEVSPEC-263 migration part).

1.1.1 named what the system depends on in three places: the ``tech_stack`` of steps 02, 09 and 14, the components of step 02
with ``type: external`` (tagged ``external-dependency``), and typed ``external`` entries of the dependencies of 09 and 14.
1.2.0 has one node, a ``third_parties`` entry of step 02 with an exact ``pin``.  What this script does:

- MECHANICAL: an external component becomes a ``third_parties`` entry that keeps the component's id (so a worklist item or a
  mention of the id still finds it), ``name`` the id and ``rationale`` the old responsibilities; the component is removed
  (``capture.json`` keeps it whole).  No ``pin`` and no ``derives_from`` is written: the exact pin and the upstream reason are
  judgement.
- PROPOSALS (worklist items, nothing applied): one item per distinct ``tech_stack`` entry of the capture (candidate id from the
  name, candidate pin from the version, the steps that held it); one per external component (name, pin candidate, who
  pointed at it); one per typed ``external`` dependency entry of 09 and 14 ("relate it to the third-party node by an API
  ``relies_on`` or a connection ``connects_to``, or drop it": the entry is copied to no milestone field); one per API whose
  name or version names a ``tech_stack`` entry (a candidate ``relies_on``).  The same items say when two names make one id,
  when the copies of an entry carry different versions, and when a version is not semver and so cannot be an exact pin.

``tech_stack`` itself (steps 02, 09, 14) was removed in phase 3 after the capture kept it.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import mint_slug, suggest_prefix
from specdev_tools.graph.names import THIRD_PARTY
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, LEGACY
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import insert_key, step_data
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_third_party", phase=PHASE_CONTENT, requires=("p3_convert", "p3_remove"), touches=("02", "extras"))

SYSTEM_STEP = "02"
KIND_PROPOSAL = "third-party-proposal"
KIND_EXTERNAL_COMPONENT = "external-component"
KIND_EXTERNAL_DEPENDENCY = "external-dependency"
KIND_API_VERSION = "api-relies-on"
EXTERNAL_TYPE = "external"
EXTERNAL_TAG = "external-dependency"
_SEMVER = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_MIN_NAME = 4


def _slug(name: str) -> str | None:
    try:
        return mint_slug(name, set(), prefix=suggest_prefix(THIRD_PARTY))
    except ValueError:
        return None


def _captured(ctx) -> dict[str, Any]:
    return ctx.documents.load(CAPTURE_REL).data.get("third_party") or {}


def _stack_rows(ctx) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """``(step, group, entry)`` of every ``tech_stack`` entry of the capture."""
    for row in _captured(ctx).get("tech_stacks") or []:
        for group, entries in (row.get(LEGACY + "tech_stack") or {}).items():
            for entry in entries if isinstance(entries, list) else []:
                if isinstance(entry, dict):
                    yield row["step"], group, entry


def _stack_entries(ctx) -> dict[str, dict[str, Any]]:
    """The distinct ``tech_stack`` entries of the capture by candidate id: names, versions per step, groups, the first rationale."""
    found: dict[str, dict[str, Any]] = {}
    for step, group, entry in _stack_rows(ctx):
        slug = _slug(str(entry.get("name", "")))
        if slug is None:
            continue
        held = found.setdefault(slug, {"names": [], "versions": defaultdict(list), "groups": [], "rationale": ""})
        held["names"] += [entry["name"]] if entry["name"] not in held["names"] else []
        held["groups"] += [group] if group not in held["groups"] else []
        held["versions"][step].append(str(entry.get("version", "")))
        held["rationale"] = held["rationale"] or str(entry.get("rationale", ""))
    return found


def _flags(slug: str, held: dict[str, Any], taken: set[str], components: list[str]) -> list[str]:
    """What makes the entry a decision rather than a copy: two names for one id, a clash with another node, differing or non-semver versions, an ambiguous grain."""
    flags = []
    if len(held["names"]) > 1:
        flags.append(f"the names {held['names']} make one id")
    if slug in taken:
        flags.append(f"{slug} is already the id of another node")
    by_step = {step: sorted(set(versions)) for step, versions in sorted(held["versions"].items())}
    distinct = sorted({v for versions in by_step.values() for v in versions})
    if len(distinct) > 1:
        flags.append("the steps disagree on the version: " + ", ".join(f"{step} {versions}" for step, versions in by_step.items()))
    flags += [f"version {v!r} is not semver and cannot be an exact pin as written" for v in distinct if not _SEMVER.match(v)]
    first = held["names"][0].split()[0].lower()
    near = [c for c in components if len(first) >= _MIN_NAME and first in c]
    if len(near) > 1:
        flags.append(f"{len(near)} external components ({', '.join(near)}) share its first word: the grain (one third party or several) is a decision")
    return flags


def _external_components(ctx) -> list[dict[str, Any]]:
    components = step_data(ctx, SYSTEM_STEP).get("components")
    return [c for c in components if isinstance(c, dict) and c.get("type") == EXTERNAL_TYPE] if isinstance(components, list) else []


def _items(ctx) -> list[WorklistItem]:
    graph = build_graph(ctx.spec_root, ctx.toolkit_root)
    taken = set(graph.by_id)
    external = [c["component_id"] for c in _external_components(ctx)]
    captured_external = [row["component"] for row in _captured(ctx).get("external_components") or []]
    stack = _stack_entries(ctx)
    items = []
    for slug, held in sorted(stack.items()):
        pins = sorted({v for versions in held["versions"].values() for v in versions if v})
        flags = _flags(slug, held, taken - set(external) - set(captured_external), captured_external)
        items.append(make_item(
            SYSTEM_STEP, KIND_PROPOSAL, slug, audience="agent", blocking=False,
            evidence=f"tech_stack entry {held['names'][0]!r} ({', '.join(held['groups'])}) in step(s) {', '.join(sorted(held['versions']))}, versions {pins or 'none'}" + ("; " + "; ".join(flags) if flags else ""),
            proposal=f"third_parties entry {slug}: name {held['names'][0]!r}, pin {pins[0] if pins else '(a version the host can show)'} if that is exact, rationale {held['rationale']!r}; judge the grain, the exact pin, derives_from (a seed or a constraint) and which nodes relies_on it",
        ))
    covered = {ref for c in step_data(ctx, SYSTEM_STEP).get("components", []) if isinstance(c, dict) and c.get("type") != EXTERNAL_TYPE for ref in c.get("derives_from") or []}
    live = {c["component_id"]: c for c in _external_components(ctx) if isinstance(c.get("component_id"), str)}
    for row in _captured(ctx).get("external_components") or []:
        component = row["component"]
        pins = sorted({v for held in stack.values() if held["names"] and held["names"][0].lower().startswith(component.split("-")[0]) for vs in held["versions"].values() for v in vs})
        holders = sorted({f"{link.source}.{link.field}" for link in graph.incoming.get(component, ())})
        lost = [ref for ref in live.get(component, {}).get("derives_from") or [] if ref not in covered]
        items.append(make_item(
            SYSTEM_STEP, KIND_EXTERNAL_COMPONENT, component, audience="agent", blocking=True,
            evidence=(f"the external component {component} is now the third_parties entry {component} (name the id, no pin, no derives_from); referenced by {holders or 'nothing'}; "
                      f"tech_stack versions of similar names: {pins or 'none'}"
                      + (f"; a third party derives from no capability, so {', '.join(lost)} has no component deriving from it now (E590)" if lost else "")),
            proposal="give it its name, an exact pin and a derives_from (a seed or constraint); point what used it (a connection `connects_to`, an API `relies_on`) at it" + ("; add or name the component that covers the capability" if lost else ""),
        ))
    for row in (ctx.documents.load(CAPTURE_REL).data.get("milestone_ordering") or {}).get("typed_dependencies") or []:
        entry = row.get(LEGACY + "dependency") or {}
        if entry.get("type") == EXTERNAL_TYPE:
            items.append(make_item(
                SYSTEM_STEP, KIND_EXTERNAL_DEPENDENCY, str(entry.get("id")), audience="agent", blocking=False, key=str(row.get("step")),
                evidence=f"the step {row.get('step')} dependencies named the external {entry.get('id')}: owner {entry.get('owner')!r}, note {entry.get('note')!r}",
                proposal="relate to the third-party node by an API `relies_on` or a connection `connects_to`, or drop it; the entry is copied to no milestone field",
            ))
    items += _api_items(ctx, stack)
    return items


def _api_items(ctx, stack: dict[str, dict[str, Any]]) -> list[WorklistItem]:
    items = []
    for api in step_data(ctx, "05").get("apis", []):
        if not isinstance(api, dict) or not isinstance(api.get("api_id"), str):
            continue
        text = f"{api.get('name', '')} {api.get('version', '')}".lower()
        for slug, held in sorted(stack.items()):
            name = next((n for n in held["names"] if len(n) >= _MIN_NAME and n.lower() in text), None)
            if name:
                items.append(make_item(
                    "05", KIND_API_VERSION, api["api_id"], audience="agent", blocking=False, key=slug,
                    evidence=f"api {api['api_id']} names {name!r} in its name or version ({api.get('name')!r}, {api.get('version')!r})",
                    proposal=f"relies_on {slug} once that third-party node exists (a candidate: the version is the pin the API was specified against)",
                ))
    return items


def _convert(component: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"third_party_id": component["component_id"], "name": component["component_id"]}
    responsibilities = [r for r in component.get("responsibilities") or [] if isinstance(r, str)]
    if responsibilities:
        entry["rationale"] = "; ".join(responsibilities)
    return entry


def detect(ctx) -> int:
    """External components still to convert, plus worklist items not yet listed."""
    return len(_external_components(ctx)) + len(missing_items(ctx, _items(ctx)))


def apply(ctx) -> ScriptResult:
    """List the items first (they read the components), then convert each external component."""
    listed = add_items(ctx, _items(ctx))
    components = _external_components(ctx)
    data = step_data(ctx, SYSTEM_STEP)
    if components:
        if not isinstance(data.get("third_parties"), list):
            insert_key(data, "third_parties", [], after="connections" if "connections" in data else "components")
        data["third_parties"].extend(_convert(c) for c in components)
        data["components"] = [c for c in data["components"] if c not in components]
    residue = (f"external components converted to third_parties entries: {len(components)}", f"worklist items: {listed}")
    return ScriptResult(edits=len(components) + listed, worklist_items=listed, residue=residue)


def verify(before, after) -> list[Problem]:
    """No component of step 02 has ``type: external`` any more."""
    return [
        Problem(f"{rel}: a component with type external is left", rel)
        for rel, document in sorted(after.documents.items())
        if rel[:2] == SYSTEM_STEP and isinstance(document, dict) and any(isinstance(c, dict) and c.get("type") == EXTERNAL_TYPE for c in document.get("components") or [])
    ]
