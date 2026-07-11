"""Registry generator for entry_key_registry.json and extraction_paths.json.

Implements W3-T1: programmatically derives the entry-key registry and
extraction-paths from toolkit schemas (schema/*.schema.json), replacing the
previously hand-curated spec/entry_key_registry.json.

Output is byte-deterministic across runs (sort_keys=True, indent=2, trailing
newline).  ``registry`` keys follow step_order.json::steps[] ordering;
``arrays[]`` entries follow schema-declaration order (Python 3.7+ dict ordering
preserved by json.load).

Design constraints:
  - $ref resolution: items that use "$ref": "vc:core:collections#traceRef" etc.
    are resolved via core/collections.schema.json $defs.
  - Sentinel arrays (canonical_refs_used, canonical_proposals) are listed only
    at the top-level _sentinels key, NOT per-file.
  - kind derivation:
      * id_field ends in _id → strip suffix, snake→kebab
        (e.g. fr_id → fr, threat_id → threat)
      * id_field == id → singularise array name snake→kebab
        (e.g. deliverables → deliverable, edge_cases → edge-case)
  - Basename overrides: schema name ≠ spec basename in two cases:
      * step 13: schema is 13_extension_manifest.schema.json
                 spec basename is 13_extension_manifest.json
      * step 16: two schemas exist (16_impl_context + 16_anchor);
                 only 16_impl_context.schema.json is used;
                 16_anchor.schema.json is an internal anchor schema, skipped.
  - Deferred-registration steps (16a, 16b, 16c): no schemas exist; entries live
    in per-milestone impl_context files. Routed to steps_with_deferred_registration
    regardless of missing-schema fallback rule (deferred-list wins).
  - Cross-reference arrays (e.g. 05_interface_contracts.out_of_scope, which has
    fr_id but is a cross-reference list, not primary entries) are excluded via
    the CROSS_REF_EXCLUSIONS hardcoded map.
  - job.steps in 12_ci_gates are workflow-internal and excluded via the same map.
  - capabilities.goal_id is a secondary ID alongside capability_id; the first
    *_id field found takes precedence (schema declaration order).
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any

from specdev_tools.core.schema_nav import effective_schema as _schema_nav_effective_schema


# ---------------------------------------------------------------------------
# Constants / overrides
# ---------------------------------------------------------------------------

#: Arrays that match the id-field heuristic but are cross-reference lists,
#: not primary entry registries.  Key: (schema_basename, array_name).
CROSS_REF_EXCLUSIONS: frozenset[tuple[str, str]] = frozenset([
    ("05_interface_contracts.schema.json", "out_of_scope"),  # fr_id refs, not primary
    ("12_ci_gates.schema.json", "steps"),                   # job.steps are workflow-internal
])

#: $ref URIs whose items are cross-step foreign-key references, NOT primary
#: entry keys.  Arrays whose items.$ref appears in this set are skipped during
#: scanning — they would otherwise pollute the corpus-ID collection with foreign
#: IDs and produce false nearest_id matches and spurious E110 collisions.
#:
#: traceRef (vc:core:collections#traceRef) is the canonical example: every
#: "trace" array in specs holds {type, id} pairs where id is a FOREIGN KEY
#: into another step's artifact, not a primary entry key for this step.
#:
#: Note: dependencyItem also has a {type, id} shape but is a primary entry
#: (dependencies are owned by the roadmap).  That ref resolves via
#: dependencyObjectList → dependencyItem, NOT directly via a traceRef $ref, so
#: it is unaffected by this set.
TRACE_REF_REFS: frozenset[str] = frozenset([
    "vc:core:collections#traceRef",
])

#: Sentinels: array names that appear across multiple spec files and are always
#: corpus-excluded.  Only emitted at top-level _sentinels, not per-file.
#: Also includes cross-reference arrays excluded via CROSS_REF_EXCLUSIONS that
#: need suppression in the W614 registry-check scanner (e.g. out_of_scope is
#: a cross-ref list of fr_ids in step 05 — primary entries live in step 04).
SENTINEL_ARRAYS: tuple[str, ...] = ("canonical_proposals", "canonical_refs_used", "out_of_scope")

#: Map step_id → spec_file_basename when schema filename ≠ spec basename.
STEP_BASENAME_OVERRIDES: dict[str, str] = {
    "13": "13_extension_manifest.json",
}

#: Schema files to skip entirely (not the canonical spec file for any step).
SCHEMA_SKIP: frozenset[str] = frozenset([
    "16_anchor.schema.json",          # internal anchor schema, not a spec file
    "seed_manifest.schema.json",      # seed manifest, not a step spec
    "seed_requirements.schema.json",  # seed requirements, not a step spec
    "step_order.schema.json",         # step_order, not a step spec
])

#: Steps whose entries live in per-milestone files, not spec/NN_*.json.
DEFERRED_STEPS: frozenset[str] = frozenset(["16a", "16b", "16c"])

#: Rationale string used for deferred steps.
DEFERRED_RATIONALE = "per-milestone files; deferred per Out-of-scope"

#: Format version for the generated registry.
FORMAT_VERSION = "1.0.0"

#: Note embedded in _note field of generated registry.
REGISTRY_NOTE = (
    "Generated by specdev registry-generate from devspec_toolkit/schema/*.schema.json. "
    "Do not hand-edit."
)


# ---------------------------------------------------------------------------
# Schema loading and $ref resolution
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    """Load JSON from path, raising FileNotFoundError or json.JSONDecodeError."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _build_ref_resolver(repo_root: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build ref-resolver maps from core/collections.schema.json $defs.

    Returns:
        (items_resolver, array_resolver) — both are dicts keyed by $ref string:
        - items_resolver: $ref → properties dict (for items.$ref resolution)
        - array_resolver: $ref → full $defs entry (for property-level $ref that
          resolves to an array, e.g. dependencyObjectList)

    Only resolves fragments from core/collections.schema.json $defs, which is
    the only file that defines items-level $refs in the toolkit schemas.  The
    resolver is intentionally narrow: it handles the specific $ref patterns seen
    in practice rather than a general JSON Schema resolver.
    """
    collections_path = os.path.join(repo_root, "schema", "core", "collections.schema.json")
    if not os.path.isfile(collections_path):
        return {}, {}
    collections = _load_json(collections_path)
    defs = collections.get("$defs", {})

    items_resolver: dict[str, dict[str, Any]] = {}
    array_resolver: dict[str, dict[str, Any]] = {}

    for name, defn in defs.items():
        if not isinstance(defn, dict):
            continue
        ref_key = f"vc:core:collections#{name}"
        # items resolver: maps ref → item properties dict
        props = defn.get("properties", {})
        if props:
            items_resolver[ref_key] = props
        # array resolver: maps ref → full defn (for top-level property $refs)
        if defn.get("type") == "array":
            array_resolver[ref_key] = defn

    return items_resolver, array_resolver


def _get_all_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """Return merged top-level properties from a schema, collapsing allOf blocks.

    Preserves insertion order (Python 3.7+), which is the schema-declaration
    order.  Later allOf entries override earlier ones if keys collide (rare).

    Thin adapter over ``schema_nav.effective_schema`` (conditionals OFF, no-op
    resolver).  Generate intentionally does NOT resolve the ``vc:core:step-base``
    ``$ref`` — only inline step-specific top-level properties are wanted.  The
    no-op resolver returns None (non-dict) for any ``$ref`` node, causing
    effective_schema to treat that branch as empty — same as before.

    Projects ``["properties"]`` only; ``["required"]`` is discarded (generate
    never reads required; the helper always sets ``required=[]``).
    """
    # No-op resolver: returns None (non-dict) for any $ref node so that
    # effective_schema skips bare-$ref branches without resolving them.
    # MUST return non-dict (None) — not the node itself — per the helper contract.
    def _noop_resolver(_node: dict) -> None:
        return None

    e = _schema_nav_effective_schema(schema, _noop_resolver, include_conditionals=False)
    return e["properties"]


# ---------------------------------------------------------------------------
# kind derivation
# ---------------------------------------------------------------------------

def _snake_to_kebab(s: str) -> str:
    """Convert snake_case to kebab-case."""
    return s.replace("_", "-")


def _singularize(name: str) -> str:
    """Naively singularize an English plural.

    Rules (applied in order):
      1. ends in 'ies' (not 'ss') → replace with 'y'
         e.g. dependencies → dependency
      2. ends in 'ss' → leave unchanged (e.g. 'class' stays 'class')
      3. ends in 's' → strip trailing 's'
         e.g. deliverables → deliverable, threats → threat

    Examples:
      deliverables → deliverable
      threats → threat
      edge_cases → edge_case
      dependencies → dependency
      milestones → milestone
    """
    if name.endswith("ies"):
        return name[: -len("ies")] + "y"
    if name.endswith("ss"):
        return name
    if name.endswith("s"):
        return name[:-1]
    return name


def _derive_kind(id_field: str, array_name: str) -> str:
    """Derive the 'kind' string for a registry entry.

    Rule A:
      - id_field ends in _id → strip suffix, snake→kebab
        e.g. fr_id → fr, threat_id → threat, milestone_id → milestone
      - id_field == 'id' → singularize array_name, snake→kebab
        e.g. deliverables → deliverable, edge_cases → edge-case, trace → trace
    """
    if id_field.endswith("_id"):
        base = id_field[: -len("_id")]
        return _snake_to_kebab(base)
    # id_field == 'id'
    singular = _singularize(array_name)
    return _snake_to_kebab(singular)


# ---------------------------------------------------------------------------
# Array scanning
# ---------------------------------------------------------------------------

def _find_id_field(item_props: dict[str, Any]) -> str | None:
    """Find the primary id field in an items.properties dict.

    Priority:
      1. First property name ending in _id (schema declaration order).
      2. Bare 'id' if present.
      3. None → array is not entry-bearing.
    """
    for key in item_props:
        if key.endswith("_id"):
            return key
    if "id" in item_props:
        return "id"
    return None


def _scan_nested_arrays(
    item_props: dict[str, Any],
    items_resolver: dict[str, dict[str, Any]],
    parent_schema_basename: str,
) -> list[dict[str, Any]]:
    """Scan item_props for nested arrays of objects with id fields.

    Recurses to arbitrary depth: each discovered nested entry is itself scanned
    for deeper entry-bearing arrays, whose entries are attached under a further
    ``nested`` key.  This mirrors the recursive ``arrayEntry.nested`` shape in
    ``schema/entry_key_registry.schema.json``.  Example: step 14's
    ``milestones[].tasks[].acceptance_criteria`` is 3-deep — the ``criterion``
    entry is nested under the ``task`` entry, which is nested under ``milestone``.

    Returns a list of arrayEntry dicts (without 'corpus_excluded').
    """
    nested: list[dict[str, Any]] = []
    for prop_name, prop_def in item_props.items():
        if not isinstance(prop_def, dict):
            continue
        if prop_def.get("type") != "array":
            continue
        # Exclusion check for nested arrays
        if (parent_schema_basename, prop_name) in CROSS_REF_EXCLUSIONS:
            continue
        nested_items = prop_def.get("items", {})
        if not isinstance(nested_items, dict):
            continue
        # Skip traceRef arrays: these are cross-step foreign-key references,
        # not primary entries for this spec file.
        if nested_items.get("$ref") in TRACE_REF_REFS:
            continue
        # Resolve $ref
        nested_item_props = _resolve_item_props(nested_items, items_resolver)
        if not nested_item_props:
            continue
        id_field = _find_id_field(nested_item_props)
        if id_field is None:
            continue
        kind = _derive_kind(id_field, prop_name)
        entry: dict[str, Any] = {
            "array_path": f".{prop_name}",
            "id_field": id_field,
            "kind": kind,
        }
        # Recurse: attach any deeper entry-bearing arrays under this entry.
        deeper = _scan_nested_arrays(
            nested_item_props, items_resolver, parent_schema_basename
        )
        if deeper:
            entry["nested"] = deeper
        nested.append(entry)
    return nested


def _resolve_item_props(
    items: dict[str, Any],
    items_resolver: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve items dict to its effective properties dict.

    Handles inline (items.type=object) and $ref (items.$ref=vc:core:...) cases.
    """
    if "$ref" in items:
        ref_key = items["$ref"]
        return items_resolver.get(ref_key, {})
    if items.get("type") == "object":
        return items.get("properties", {})
    return {}


def _scan_schema_for_arrays(
    schema: dict[str, Any],
    schema_basename: str,
    items_resolver: dict[str, dict[str, Any]],
    array_resolver: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scan a schema for entry-bearing top-level arrays.

    Handles two forms of array declaration:
    1. Inline: property has type=array with items
    2. Top-level $ref: property is "$ref": "vc:core:collections#X" where X
       resolves to an array type in core/collections.schema.json $defs
       (e.g. dependencyObjectList for 14_roadmap.dependencies)

    Returns:
        (arrays, sentinels_found)
        arrays: list of arrayEntry dicts suitable for inclusion in the registry
        sentinels_found: array names that match SENTINEL_ARRAYS (not included in
                         arrays — only collected for the top-level _sentinels list)
    """
    props = _get_all_properties(schema)
    arrays: list[dict[str, Any]] = []
    sentinels_found: list[str] = []

    for prop_name, prop_def in props.items():
        if not isinstance(prop_def, dict):
            continue

        # Sentinel check (sentinels are always inline arrays added at write-time)
        if prop_name in SENTINEL_ARRAYS:
            sentinels_found.append(prop_name)
            continue

        # Exclusion check
        if (schema_basename, prop_name) in CROSS_REF_EXCLUSIONS:
            continue

        # Resolve array definition — two cases:
        # Case 1: property itself is a $ref to a collection that is an array
        #         e.g. "dependencies": {"$ref": "vc:core:collections#dependencyObjectList"}
        # Case 2: property has type=array with inline items
        if "$ref" in prop_def and "type" not in prop_def:
            # Top-level property $ref
            ref_key = prop_def["$ref"]
            array_defn = array_resolver.get(ref_key)
            if array_defn is None:
                continue
            items = array_defn.get("items", {})
            if not isinstance(items, dict):
                continue
        elif prop_def.get("type") == "array":
            items = prop_def.get("items", {})
            if not isinstance(items, dict):
                continue
        else:
            continue

        # Skip traceRef arrays: these are cross-step foreign-key references,
        # not primary entries for this spec file.  Check BEFORE resolving props
        # because _resolve_item_props strips the $ref away.
        if items.get("$ref") in TRACE_REF_REFS:
            continue

        item_props = _resolve_item_props(items, items_resolver)
        if not item_props:
            continue

        id_field = _find_id_field(item_props)
        if id_field is None:
            continue

        kind = _derive_kind(id_field, prop_name)
        entry: dict[str, Any] = {
            "array_path": f".{prop_name}",
            "id_field": id_field,
            "kind": kind,
        }

        # Nested arrays
        nested = _scan_nested_arrays(item_props, items_resolver, schema_basename)
        if nested:
            entry["nested"] = nested

        arrays.append(entry)

    return arrays, sentinels_found


# ---------------------------------------------------------------------------
# Step → schema mapping
# ---------------------------------------------------------------------------

def _schema_file_for_step(step: str, schema_dir: str) -> str | None:
    """Return the path to the schema file for a step, or None if none exists.

    Fail-loud hardening: after the SCHEMA_SKIP filter, if >1 file remains for
    the same step, raises ``ValueError`` naming the step, the remaining files,
    and the fix instruction (add the non-spec schema to SCHEMA_SKIP).

    Today exactly 1 file remains for every step after the filter, so this raise
    is purely future-proofing — it NEVER triggers on the current schema corpus.
    Step 16 has two schema files (16_impl_context, 16_anchor) but 16_anchor is
    in SCHEMA_SKIP, so only 16_impl_context remains and the raise does not fire.

    This makes the selector ORDER-INDEPENDENT and FAIL-LOUD rather than silently
    picking the lexicographic-first when an unhandled multi-schema step is added.
    """
    pattern = os.path.join(schema_dir, f"{step}_*.schema.json")
    matches = [
        p for p in sorted(glob.glob(pattern))
        if os.path.basename(p) not in SCHEMA_SKIP
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # >1 match after SCHEMA_SKIP filter: unhandled ambiguity — fail loud.
    # To fix: add the non-spec schema file(s) to SCHEMA_SKIP in generate.py.
    remaining = [os.path.basename(p) for p in matches]
    raise ValueError(
        f"_schema_file_for_step: step '{step}' has {len(matches)} schema files "
        f"remaining after SCHEMA_SKIP filter: {remaining!r}. "
        f"Add the non-spec schema(s) to SCHEMA_SKIP in "
        f"tools/specdev_tools/registry/generate.py."
    )


def _spec_basename_for_step(step: str, schema_path: str) -> str:
    """Derive the spec file basename from a schema path.

    Applies STEP_BASENAME_OVERRIDES where schema filename ≠ spec basename.
    For all other steps: strips .schema.json suffix, adds .json.
    """
    if step in STEP_BASENAME_OVERRIDES:
        return STEP_BASENAME_OVERRIDES[step]
    base = os.path.basename(schema_path)
    # e.g. 04_fr_list.schema.json → 04_fr_list.json
    if base.endswith(".schema.json"):
        return base[: -len(".schema.json")] + ".json"
    return base


# ---------------------------------------------------------------------------
# extraction_paths.json generation
# ---------------------------------------------------------------------------

def _build_extraction_paths(
    registry: dict[str, dict[str, Any]],
    step_order: list[str],
) -> dict[str, Any]:
    """Build the extraction_paths.json structure from the registry.

    Format matches the existing extraction_paths.json: step-keyed dict
    (excluding _meta) with inner basename → list[array_path].

    The _meta key is preserved in spirit but we emit only the structure that
    downstream consumers (registry_check._load_extraction_basenames) expect:
    a dict where values are dicts whose keys are spec file basenames.

    Note: generated_at is intentionally omitted to preserve byte-determinism
    across runs.  schema_hashes is also omitted (generated from schemas, not
    hashed here) — downstream consumers only read the step-keyed structure.

    Structure:
        {
          "_meta": { "note": "Generated by specdev registry-generate." },
          "<step>": { "<basename>": [<array_paths>] },
          ...
        }
    """
    result: dict[str, Any] = {
        "_meta": {
            "note": (
                "Generated by specdev registry-generate. "
                "Do not hand-edit. Step-keyed; inner keys are spec file basenames."
            )
        }
    }

    # Build step → {basename: [array_paths]} from registry
    # Follow step_order for deterministic ordering
    basename_to_step: dict[str, str] = {}
    for basename, entry in registry.items():
        basename_to_step[basename] = entry["step"]

    # Group basenames by step in step_order sequence
    step_basenames: dict[str, list[str]] = {}
    for basename, entry in registry.items():
        step = entry["step"]
        step_basenames.setdefault(step, []).append(basename)

    for step in step_order:
        basenames = step_basenames.get(step, [])
        if not basenames:
            continue
        step_block: dict[str, list[str]] = {}
        for basename in sorted(basenames):
            arrays = registry[basename]["arrays"]
            paths = [a["array_path"] for a in arrays]
            step_block[basename] = paths
        result[step] = step_block

    return result


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_registry(repo_root: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate the entry_key_registry and extraction_paths dicts from schemas.

    Args:
        repo_root: Absolute path to the toolkit root (contains schema/, tools/).

    Returns:
        (registry_doc, extraction_paths_doc) — two dicts ready to serialize.

    Raises:
        FileNotFoundError: if step_order.json or core/collections.schema.json
                           are missing.
        json.JSONDecodeError: if any schema file is malformed.
    """
    schema_dir = os.path.join(repo_root, "schema")
    tools_dir = os.path.join(repo_root, "tools")

    # Load step order
    step_order_path = os.path.join(tools_dir, "step_order.json")
    step_order_data = _load_json(step_order_path)
    steps: list[str] = step_order_data["steps"]

    # Build $ref resolvers
    items_resolver, array_resolver = _build_ref_resolver(repo_root)

    # Accumulators
    registry: dict[str, dict[str, Any]] = {}  # basename → entry
    sentinels_set: set[str] = set()
    steps_without: list[dict[str, str]] = []
    steps_deferred: list[dict[str, str]] = []

    for step in steps:
        # Deferred-list wins over missing-schema fallback
        if step in DEFERRED_STEPS:
            steps_deferred.append({"step": step, "rationale": DEFERRED_RATIONALE})
            continue

        schema_path = _schema_file_for_step(step, schema_dir)
        if schema_path is None:
            steps_without.append({
                "step": step,
                "rationale": "no schema file",
            })
            continue

        schema = _load_json(schema_path)
        schema_basename = os.path.basename(schema_path)
        spec_basename = _spec_basename_for_step(step, schema_path)

        arrays, sentinels_found = _scan_schema_for_arrays(
            schema, schema_basename, items_resolver, array_resolver
        )
        sentinels_set.update(sentinels_found)

        if not arrays:
            steps_without.append({
                "step": step,
                "rationale": "no top-level array properties with id fields",
            })
            # Still emit a registry entry with empty arrays so basename coverage
            # matches extraction_paths; omit if you don't want empty entries.
            # Decision: skip empty entries — keep registry clean and match plan.
            continue

        registry[spec_basename] = {
            "step": step,
            "arrays": arrays,
        }

    # Sentinels are a hardcoded constant list: these array names appear across
    # multiple spec files at write-time (appended by canonical-lint tooling) and
    # are never declared in any schema's properties.  We do NOT discover them
    # via schema walk — they are always emitted from the SENTINEL_ARRAYS constant.
    # sentinels_set tracks any that *were* found in schemas (should be empty in
    # practice) and is merged in for completeness.
    all_sentinels = sorted(set(SENTINEL_ARRAYS) | sentinels_set)

    # Build output document
    registry_doc: dict[str, Any] = {
        "$schema": "vc:entry-key-registry",
        "_format_version": FORMAT_VERSION,
        "_note": REGISTRY_NOTE,
        "registry": registry,
        "_sentinels": all_sentinels,
        "steps_without_entry_arrays": steps_without,
        "steps_with_deferred_registration": steps_deferred,
    }

    # Build extraction_paths
    extraction_paths_doc = _build_extraction_paths(registry, steps)

    return registry_doc, extraction_paths_doc


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize(doc: Any) -> str:
    """Serialize to deterministic JSON string with trailing newline."""
    return json.dumps(doc, sort_keys=True, indent=2) + "\n"


def run(
    repo_root: str,
    out_path: str,
    extraction_paths_out: str,
) -> None:
    """Generate registry and extraction_paths files and write them to disk.

    Args:
        repo_root: Absolute or relative path to the toolkit root.
        out_path: Destination path for entry_key_registry.json.
        extraction_paths_out: Destination path for extraction_paths.json.
    """
    repo_root = os.path.abspath(repo_root)
    registry_doc, extraction_paths_doc = generate_registry(repo_root)

    # Write registry
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(_serialize(registry_doc))

    # Write extraction_paths
    os.makedirs(os.path.dirname(os.path.abspath(extraction_paths_out)), exist_ok=True)
    with open(extraction_paths_out, "w", encoding="utf-8") as fh:
        fh.write(_serialize(extraction_paths_doc))

    print(f"registry-generate: wrote {out_path}")
    print(f"registry-generate: wrote {extraction_paths_out}")
