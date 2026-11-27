from __future__ import annotations

import os
import re
from typing import Any, Optional

from ...core.host_schemas import (
    DATA_SUFFIX,
    SCHEMA_SUFFIX,
    HostSchemas,
    data_file_of,
    extension_id_of,
    find_host_schemas,
    schema_file_of,
    stem_of,
    uri_of,
)
from ...core.registry import SchemaRegistry, get_shared_registry
from ...core.schema_nav import effective_schema
from ...core.scope_helpers import as_list, dict_items
from ...core.errors import make_error, SpecError
from ...core.step_paths import EXTENSION_STEP, EXTENSIONS_DIR_NAME, same_folder
from ...graph.ownership import stamp_file_owner


# Valid section name patterns: numeric step prefix (00_*, 16a_*) OR any
# domain-style identifier (tables, indexes, my-section, etc.).  The original
# strict pattern r"^[0-9]{2}[a-z]?_" incorrectly rejected non-numeric section
# names used by domain-specific schemas.
_STEP_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
_MANIFEST_NAME = "13_extension_manifest.json"
_FILE_NAMING = f"an extension's files are named ext_NN_<topic>{SCHEMA_SUFFIX} and ext_NN_<topic>{DATA_SUFFIX}"


def validate_step_13(instance: dict[str, Any], toolkit_root: str, spec_root: Optional[str] = None) -> list[SpecError]:
    """The deep checks of the extension manifest *instance*.

    *spec_root* is the spec folder the manifest is known to belong to.  With it, each declared extension is compared
    with the folder's ``extensions/`` files: its schema and its data file exist, the schema is a JSON Schema with the
    ``$id`` its file name gives, it declares each name of ``required_schema_sections``, and no file of the folder is
    left undeclared.  Without it (a manifest validated alone) no file is looked for.

    A finding about an entry carries the entry's place (``jq_path`` ``.extensions[i]``) and its extension id
    (``node_id``: an entry is a node); a finding about a file of the folder carries the file (``path``, relative to the
    spec folder).  The step gate tells two findings of one code apart by these and not by their text.
    """
    errors: list[SpecError] = []
    extensions = as_list(instance.get("extensions"))
    for ext in dict_items(extensions):
        ext_id = ext.get("extension_id")

        # required_schema_sections must be present and non-empty
        sections = ext.get("required_schema_sections")
        if not sections:
            errors.append(make_error("E520", f"Extension '{ext_id}' missing required_schema_sections"))
        elif isinstance(sections, list):
            for j, section in enumerate(sections):
                if isinstance(section, str) and not _STEP_PATTERN.match(section):
                    errors.append(
                        make_error("E320", f"Extension '{ext_id}' required_schema_sections[{j}] "
                        f"'{section}' is not a valid identifier (must start with alphanumeric, only alphanumeric/underscore/hyphen allowed)")
                    )

        # Justification must be non-empty
        justification = ext.get("justification")
        if not justification or (isinstance(justification, str) and not justification.strip()):
            errors.append(
                make_error("E320", f"Extension '{ext_id}' missing or empty justification")
            )

    if spec_root:
        errors.extend(_extension_file_errors(extensions, toolkit_root, spec_root))
    return errors


def _extension_file_errors(extensions: list[Any], toolkit_root: str, spec_root: str) -> list[SpecError]:
    """The manifest's entries against the files of ``<spec_root>/extensions``.

    E520 for a file that is missing, refused or undeclared; E320 for a section the schema does not declare.
    """
    try:
        toolkit = get_shared_registry(toolkit_root)
        registry = get_shared_registry(toolkit_root, spec_root)
    except (OSError, ValueError, TypeError):  # the toolkit's own registry cannot be read: every file reports that
        return []
    found = find_host_schemas(spec_root, toolkit.map)
    errors: list[SpecError] = []
    declared: set[str] = set()
    for index, ext in enumerate(extensions):
        ext_id = ext.get("extension_id") if isinstance(ext, dict) else None
        if not isinstance(ext_id, str) or extension_id_of(stem_of(ext_id) + DATA_SUFFIX) != ext_id:
            continue  # not an extension id: the schema of the manifest reports it, and no file can be named for it
        declared.add(ext_id)
        place = {"jq_path": f".extensions[{index}]", "node_id": ext_id}
        schema_name = stem_of(ext_id) + SCHEMA_SUFFIX
        if schema_name not in found.schema_files:
            errors.append(make_error(
                "E520",
                f"Extension '{ext_id}' has no schema: expected {schema_file_of(ext_id)} "
                f"(a JSON Schema whose \"$id\" is \"{uri_of(ext_id)}\")",
                **place,
            ))
        elif uri_of(ext_id) in found.accepted:
            errors.extend(_section_errors(ext, found, registry, place))
        if stem_of(ext_id) + DATA_SUFFIX not in found.data_files:
            errors.append(make_error(
                "E520",
                f"Extension '{ext_id}' has no file: expected {data_file_of(ext_id)} "
                f"(its \"$schema\" is \"{uri_of(ext_id)}\")",
                **place,
            ))
    for name, reason in found.refused.items():
        errors.append(_refused_schema_error(name, reason))
    for name in (*found.schema_files, *found.data_files):
        if extension_id_of(name) not in declared:
            errors.append(_undeclared_file_error(name))
    return errors


def _refused_schema_error(name: str, reason: str) -> SpecError:
    """E520 for a schema file that is not accepted.  A folder finding names its file as the finding of a spec with no manifest does (``file``)."""
    return make_error("E520", f"Extension schema {_place_of(name)} {reason}", _place_of(name), file=_place_of(name))


def _undeclared_file_error(name: str) -> SpecError:
    """E520 for a file of the folder that no entry declares; a file not named for an extension can be declared by none, and is told the naming."""
    hint = "" if extension_id_of(name) else f" ({_FILE_NAMING})"
    return make_error("E520", f"{_place_of(name)}: no entry of {_MANIFEST_NAME} declares it{hint}", _place_of(name), file=_place_of(name))


def schema_file_errors(toolkit_root: str, spec_root: str, name: str) -> list[SpecError]:
    """What the folder check says of the one schema file *name* of ``<spec_root>/extensions`` whatever the manifest declares, owned by step 13.

    The E520 of a refused schema (the same reason), the E520 of a file that is not named for an extension (it is never
    loaded as a schema), nothing for an accepted schema.  For ``specdev validate <schema file>``: a schema file is no
    spec artifact, so no per-file check applies to it.  The caller has loaded the toolkit's registry.
    """
    found = find_host_schemas(spec_root, get_shared_registry(toolkit_root).map)
    if name in found.refused:
        errors = [_refused_schema_error(name, found.refused[name])]
    elif name in found.schema_files and extension_id_of(name) is None:
        errors = [_undeclared_file_error(name)]
    else:
        errors = []
    return stamp_file_owner(errors, EXTENSION_STEP)


def _place_of(name: str) -> str:
    """The file *name* of the extensions folder, relative to the spec folder: the same text in a head tree and in a baseline tree."""
    return f"{EXTENSIONS_DIR_NAME}/{name}"


def folder_without_manifest_errors(spec_root: str) -> list[SpecError]:
    """E520, owned by step 13, for each schema file and each data file of ``<spec_root>/extensions`` when the spec has no manifest.

    The manifest's validator judges the folder; with no ``13_extension_manifest.json`` nothing would, and the files
    would pass unseen.  Nothing for a spec with a manifest, or with no ``extensions`` folder.  Each finding is the
    finding of its own file (``file``, relative to the spec folder).
    """
    found = find_host_schemas(spec_root)
    if not (found.schema_files or found.data_files) or os.path.isfile(os.path.join(spec_root, _MANIFEST_NAME)):
        return []
    undeclared = [
        make_error("E520", f"{_place_of(name)}: the spec has no {_MANIFEST_NAME} to declare it", file=_place_of(name))
        for name in (*found.schema_files, *found.data_files)
    ]
    return stamp_file_owner(undeclared, EXTENSION_STEP)


def folder_errors_of_a_walk(toolkit_root: str, walked: str, spec_root: str) -> list[SpecError]:
    """What a command that reads the files under *walked* says of the extensions folder of *spec_root* beyond those files.

    With no manifest: the E520 of each file (``folder_without_manifest_errors``).  With one, and only when the walk
    is the extensions folder alone (``validate-all <spec>/extensions --spec-root <spec>``): the own finding of each
    schema file (``schema_file_errors``), because the manifest, whose check judges them, is not in the walk.  The
    declaration checks stay with the manifest: they belong to a walk of the spec folder.
    """
    no_manifest = folder_without_manifest_errors(spec_root)
    if no_manifest or not same_folder(walked, os.path.join(spec_root, EXTENSIONS_DIR_NAME)):
        return no_manifest
    return [error for name in find_host_schemas(spec_root).schema_files for error in schema_file_errors(toolkit_root, spec_root, name)]


def _section_errors(ext: dict[str, Any], found: HostSchemas, registry: SchemaRegistry, place: dict[str, str]) -> list[SpecError]:
    """E320 for each name of ``required_schema_sections`` that the extension's schema does not declare as a property."""
    ext_id = ext["extension_id"]
    properties = _declared_properties(uri_of(ext_id), found.accepted[uri_of(ext_id)].schema, registry)
    return [
        make_error(
            "E320",
            f"Extension '{ext_id}' required_schema_sections[{j}] '{section}' is not a property of its schema "
            f"{schema_file_of(ext_id)}",
            **place,
        )
        for j, section in enumerate(as_list(ext.get("required_schema_sections")))
        if isinstance(section, str) and _STEP_PATTERN.match(section) and section not in properties
    ]


def _declared_properties(uri: str, schema: dict[str, Any], registry: SchemaRegistry) -> set[str]:
    """The property names the schema *uri* declares for its document: its own, and those of its ``allOf``, ``$ref`` and conditional branches."""
    try:
        resolver = registry.to_referencing_registry().resolver(base_uri=uri)
    except Exception:  # the store cannot be crawled: every file of the spec reports that (E521)
        resolver = None

    def resolve(node: dict[str, Any]) -> Any:
        if resolver is None:
            return None
        try:
            return resolver.lookup(node["$ref"]).contents
        except Exception:  # an unresolvable $ref is an empty branch here; validating the data file reports it
            return None

    return set(effective_schema(schema, resolve, include_conditionals=True)["properties"])
