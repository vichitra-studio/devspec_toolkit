"""The schemas a host writes for its own extensions (step 13): where they are, which are accepted, and why one is not.

An extension that ``13_extension_manifest.json`` declares as ``ext-01-database`` has two files in the spec folder::

    <spec root>/extensions/ext_01_database.schema.json    its schema, with "$id": "vc:ext-01-database"
    <spec root>/extensions/ext_01_database.json           its data,   with "$schema": "vc:ext-01-database"

The stem is the extension id with ``-`` turned to ``_``.  No registry file lists these schemas: one listing of the
folder finds them.  The two files belong to each other and to nothing else: the data file is judged by this schema
only, and the schema judges this data file only (``schema_uri_problem``).  A schema that is not accepted (not JSON, not a JSON Schema, a wrong ``$id``) is not loaded, and the
step-13 validator reports why.  A spec folder with no ``extensions`` folder costs one ``isdir`` and gives ``NO_HOST_SCHEMAS``.

The spec root is always an argument: the step gate reads a head tree and a baseline tree in one process, so nothing
here remembers "the" spec root.  This module imports nothing of the toolkit but ``step_paths``, so
both schema resolvers (the URI map of ``registry`` and the ``$id`` index of ``json_utils``) can use it.
"""
from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .step_paths import EXTENSION_FILE_SUFFIX, EXTENSIONS_DIR_NAME, is_extension_file, same_folder

SCHEMA_SUFFIX = ".schema.json"
DATA_SUFFIX = EXTENSION_FILE_SUFFIX
HOST_URI_PREFIX = "vc:"
HOST_URI_RE = re.compile(r"^vc:ext-[0-9]{2}-[a-z0-9-]+$")
"""The ``$id`` of an extension schema: ``vc:`` and the extension id.  No toolkit schema has this form."""
_STEM_RE = re.compile(r"^ext_[0-9]{2}_[a-z0-9_]+$")
_SCAN_LIMIT = 32
"""Folders remembered at once; a process reads two (head and baseline), a test session many."""
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
"""The one dialect an extension schema is read as: the ``$schema`` it may name (or leave out)."""
PROJECT_CANON_DIR_NAME = "canon"


def stem_of(extension_id: str) -> str:
    """The file stem of the extension *extension_id*: ``ext-01-database`` gives ``ext_01_database``."""
    return extension_id.replace("-", "_")


def uri_of(extension_id: str) -> str:
    """The schema URI of the extension *extension_id*: ``ext-01-database`` gives ``vc:ext-01-database``."""
    return HOST_URI_PREFIX + extension_id


def schema_file_of(extension_id: str) -> str:
    """The schema file of the extension, relative to the spec root: ``extensions/ext_01_database.schema.json``."""
    return f"{EXTENSIONS_DIR_NAME}/{stem_of(extension_id)}{SCHEMA_SUFFIX}"


def data_file_of(extension_id: str) -> str:
    """The data file of the extension, relative to the spec root: ``extensions/ext_01_database.json``."""
    return f"{EXTENSIONS_DIR_NAME}/{stem_of(extension_id)}{DATA_SUFFIX}"


def extension_id_of(file_name: str) -> str | None:
    """The extension id a file of the folder is named for (``ext_01_database.schema.json`` or ``ext_01_database.json``
    gives ``ext-01-database``); ``None`` for a name that is not an extension's."""
    for suffix in (SCHEMA_SUFFIX, DATA_SUFFIX):
        if file_name.endswith(suffix):
            stem = file_name[: -len(suffix)]
            return stem.replace("_", "-") if _STEM_RE.fullmatch(stem) else None
    return None


def spec_root_of(path: str) -> str | None:
    """The spec folder of a file of an ``extensions`` folder, read from its path alone (the folder above it); ``None`` for any other file.

    For a caller that holds only the path of a file (``specdev json schema <file>``, a file validated alone): the schema
    of an extension file lies beside it.  The limits of that reading: ``step_paths.is_extension_file``.
    """
    path = os.path.abspath(path)
    return os.path.dirname(os.path.dirname(path)) if is_extension_file(path) else None


def spec_root_for(path: str, known: str | None = None) -> str | None:
    """The spec folder whose extension schemas judge the file *path*: *known* (``--spec-root``, or the spec folder a
    command works on) when the caller has one, else what the path alone gives (``spec_root_of``)."""
    return known if known is not None else spec_root_of(path)


def is_file_of_the_folder(path: str, known: str | None = None) -> bool:
    """Whether *path* is a file directly in the ``extensions`` folder of its spec folder (``step_paths.is_extension_file``).

    With the spec folder *known* the place decides: a JSON file directly in ``<known>/extensions`` (the same folder
    on disk, however it is typed), whatever its name, and no file of another folder that is also called
    ``extensions``.  With none the path alone is read, and the name as typed decides: the folder above a folder
    called ``extensions`` is taken for the spec folder, and a file named like a step file is not one.  A relative
    *path* is read from the current folder in both cases; a caller whose path is relative to the spec folder joins
    the two first.

    The spec folder of a command is the one it is told: ``--spec-root`` when given, else the folder it was handed.
    Nothing is read from disk and nothing from the name of a folder to decide it.
    """
    return is_extension_file(path, known)


def project_canon_of_file(path: str, known: str | None, project_canon_dir: str | None) -> str | None:
    """*project_canon_dir*; when the caller found none and *path* is a file of the extensions folder, the ``canon`` folder of its spec folder.

    ``specdev validate <file>`` looks for the project canon beside the file, where a step file has it; the canon of a
    file of the extensions folder is one folder up (*known*, or the folder above read from the path alone).
    """
    root = spec_root_for(path, known) if project_canon_dir is None and is_extension_file(path, known) else None
    if root is None:
        return project_canon_dir
    canon = os.path.join(root, PROJECT_CANON_DIR_NAME)
    return canon if os.path.isdir(canon) else None


def schema_uri_problem(path: str, document: Any, known: str | None = None) -> str | None:
    """Why the file *path* may not have the ``$schema`` it has, as far as extension schemas go; ``None`` when it may.

    An extension schema and its data file belong to each other and to nothing else.  *known* is the spec folder the
    caller knows (``is_file_of_the_folder``).  A command run on ``<spec>/extensions`` with no ``--spec-root`` takes
    that folder for its spec folder, and the data file then lies at the top of a spec folder: the text for that one
    file says so and names the way out (``_WAY_OUT``).

    - ``extensions/ext_01_database.json`` is judged by ``extensions/ext_01_database.schema.json`` and by no other
      schema, so its ``$schema`` is ``vc:ext-01-database``: a typo, the URI of another extension, a toolkit URI and no
      ``$schema`` at all are the same mistake.
    - Any other file that names a URI of the extension form (``vc:ext-01-database``) is not the file that schema
      judges: a file elsewhere in the spec folder (``ext_01_database.json`` at its top, where 1.1.1 had it), a file of
      the ``extensions`` folder that is not named for an extension.

    ``None`` for every other file and ``$schema``, and for a document that is not an object.
    """
    if not isinstance(document, dict):
        return None
    name = os.path.basename(path)
    found = document.get("$schema")
    own_id = None if name.endswith(SCHEMA_SUFFIX) or not is_file_of_the_folder(path, known) else extension_id_of(name)
    if own_id is not None:
        expected = uri_of(own_id)
        if isinstance(found, str) and found.strip() == expected:
            return None
        has = 'has no "$schema"' if found is None else f'has the "$schema" {json.dumps(found)}'
        return (
            f'schema_uri_mismatch the data file {EXTENSIONS_DIR_NAME}/{name} {has}; its file name gives "$schema": "{expected}" '
            f"(it is judged by {schema_file_of(own_id)} and by no other schema)"
        )
    named = found.strip() if isinstance(found, str) else ""
    if not HOST_URI_RE.fullmatch(named):
        return None
    place = data_file_of(named[len(HOST_URI_PREFIX):])
    text = (
        f'schema_uri_mismatch the file {name} has the "$schema" "{named}", the schema of the extension data file '
        f"{place} of the spec folder, which judges that file and no other: "
        f'move this file there if it is that data file, and give it a "$schema" of its own if it is not'
    )
    return text + _WAY_OUT if known is not None and _is_at_the_top_of_a_folder_called_extensions(path, known, place) else text


_WAY_OUT = (
    ". If the folder called extensions that this command took for the spec folder is the extensions folder of a spec, "
    "the file is where it belongs: run the command on the spec folder, or name the spec folder with --spec-root"
)


def _is_at_the_top_of_a_folder_called_extensions(path: str, known: str, place: str) -> bool:
    """Whether *path* is the file ``<known>/<name>`` in a spec folder *known* that is called ``extensions``, where
    ``extensions/<name>`` is *place* (the data file its ``$schema`` names): the one file ``_WAY_OUT`` is true of."""
    folder, name = os.path.split(os.path.abspath(path))
    return (
        os.path.basename(os.path.abspath(known)) == EXTENSIONS_DIR_NAME
        and place == f"{EXTENSIONS_DIR_NAME}/{name}"
        and same_folder(folder, known)
    )


def schema_place_of(uri: str) -> str | None:
    """Where the schema of *uri* is read from when *uri* has the form of an extension schema
    (``vc:ext-01-database`` gives ``extensions/ext_01_database.schema.json``, relative to the spec folder); ``None`` for any other URI."""
    return schema_file_of(uri[len(HOST_URI_PREFIX):]) if HOST_URI_RE.fullmatch(uri) else None


def missing_schema_text(uri: str) -> str | None:
    """What to say when no schema is loaded for *uri* and it has the form of an extension schema; ``None`` for any other URI."""
    place = schema_place_of(uri)
    if place is None:
        return None
    return (
        f"Schema not found for {uri}: it names an extension schema, which is read from {place} in the spec folder "
        f"(a JSON Schema whose \"$id\" is \"{uri}\"). Write that file, or correct it if `specdev spec-check` reports it."
    )


@dataclass(frozen=True)
class HostSchema:
    """One accepted extension schema: its URI (its ``$id``), its file (absolute) and the parsed document."""

    uri: str
    path: str
    schema: dict[str, Any] = field(compare=False)


@dataclass(frozen=True)
class HostSchemas:
    """What the ``extensions`` folder of one spec root holds.

    ``accepted`` maps a URI to its schema, in file-name order.  ``refused`` maps the name of a schema file that is
    named for an extension but is not loaded to the reason (a clause that follows the file's path in a sentence).
    ``schema_files`` and ``data_files`` are the names of every ``*.schema.json`` and of every other ``*.json`` in the
    folder, sorted; a schema file whose name is not an extension's is in ``schema_files`` only.
    """

    accepted: Mapping[str, HostSchema] = field(default_factory=dict)
    refused: Mapping[str, str] = field(default_factory=dict)
    schema_files: tuple[str, ...] = ()
    data_files: tuple[str, ...] = ()

    @property
    def paths(self) -> dict[str, str]:
        """``{URI: absolute path}`` of the accepted schemas."""
        return {uri: found.path for uri, found in self.accepted.items()}


NO_HOST_SCHEMAS = HostSchemas()
"""The answer for a spec root with no ``extensions`` folder (and for no spec root): always this one object."""

_LOCK = threading.Lock()
# realpath(extensions folder) -> (stat signature of its schema files, {schema file name: (document, reason it cannot be a schema)})
_SCANS: dict[str, tuple[tuple, dict[str, tuple[Any, str | None]]]] = {}


def find_host_schemas(spec_root: str | None, toolkit_uris: Collection[str] = ()) -> HostSchemas:
    """The extension schemas of the spec folder *spec_root*; ``NO_HOST_SCHEMAS`` when it has no ``extensions`` folder.

    *toolkit_uris* are the URIs the toolkit already has: a host schema may not take one.  The files are read once and
    read again only when a schema file is added, removed or rewritten (name, mtime and size).  Never raises: a file
    that cannot be used is in ``refused``.
    """
    if not spec_root:
        return NO_HOST_SCHEMAS
    folder = os.path.join(spec_root, EXTENSIONS_DIR_NAME)
    if not os.path.isdir(folder):
        return NO_HOST_SCHEMAS
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return NO_HOST_SCHEMAS
    schema_files = tuple(name for name in names if name.endswith(SCHEMA_SUFFIX))
    data_files = tuple(name for name in names if name.endswith(DATA_SUFFIX) and not name.endswith(SCHEMA_SUFFIX))
    documents = _scan(folder, schema_files)
    accepted: dict[str, HostSchema] = {}
    refused: dict[str, str] = {}
    for name in schema_files:
        extension_id = extension_id_of(name)
        if extension_id is None:
            continue
        document, reason = documents[name]
        if isinstance(document, dict):  # a missing $id is said first: with no $id the file names no schema at all
            expected = uri_of(extension_id)
            reason = _no_id(document, expected) or reason or _wrong_id(document, expected, toolkit_uris)
        if reason:
            refused[name] = reason
        else:
            uri = uri_of(extension_id)
            accepted[uri] = HostSchema(uri, os.path.join(os.path.abspath(folder), name), document)
    return HostSchemas(accepted, refused, schema_files, data_files)


def clear_host_schema_cache() -> None:
    """Forget every folder read so far (``registry.clear_shared_caches`` calls this)."""
    with _LOCK:
        _SCANS.clear()


def _scan(folder: str, schema_files: tuple[str, ...]) -> dict[str, tuple[Any, str | None]]:
    """``{schema file name: (parsed document, reason it cannot be a schema or None)}`` for *folder*, read once per state of its files.

    The stat signature is taken before the read and the result is remembered only if it is unchanged after it, so a
    file rewritten during the read is never remembered under its new signature with the old content.
    """
    key = os.path.realpath(folder)
    before = _signature(folder, schema_files)
    with _LOCK:
        entry = _SCANS.get(key)
    if entry is not None and entry[0] == before:
        return entry[1]
    documents = {name: _read_schema(os.path.join(folder, name)) for name in schema_files}
    if _signature(folder, schema_files) == before:
        with _LOCK:
            if len(_SCANS) >= _SCAN_LIMIT and key not in _SCANS:
                _SCANS.clear()
            _SCANS[key] = (before, documents)
    return documents


def _signature(folder: str, schema_files: tuple[str, ...]) -> tuple:
    parts: list[tuple[str, int, int] | tuple[str, None]] = []
    for name in schema_files:
        try:
            status = os.stat(os.path.join(folder, name))
        except OSError:
            parts.append((name, None))
        else:
            parts.append((name, status.st_mtime_ns, status.st_size))
    return tuple(parts)


def _read_schema(path: str) -> tuple[Any, str | None]:
    """The document of the schema file *path* and, when it cannot serve as a schema, the reason (``None`` when it can)."""
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        return None, f"cannot be read: {error.strerror or error}"
    except ValueError as error:  # json.JSONDecodeError and UnicodeDecodeError
        return None, f"is not JSON: {error}"
    if not isinstance(document, dict):
        return document, 'is not a JSON object: an extension schema must be a JSON object with an "$id"'
    dialect = document.get("$schema", DRAFT_2020_12)
    if dialect != DRAFT_2020_12:
        return document, (
            f'names the dialect "$schema": {json.dumps(dialect)}; an extension schema is read as JSON Schema draft 2020-12: '
            f'leave "$schema" out or set it to "{DRAFT_2020_12}"'
        )
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError as error:
        where = "/".join(str(part) for part in error.absolute_path)
        return document, f"is not a valid JSON Schema: {error.message}" + (f" (at /{where})" if where else "")
    return document, None


def _no_id(document: dict[str, Any], expected: str) -> str | None:
    """The reason when *document* has no ``$id`` (none, an empty one, or a value that is not a string); ``None`` when it has one."""
    found = document.get("$id")
    if not isinstance(found, str) or not found:
        return f'has no "$id"; its file name gives "$id": "{expected}"'
    return None


def _wrong_id(document: dict[str, Any], expected: str, toolkit_uris: Collection[str]) -> str | None:
    """Why the ``$id`` of *document* is not the one its file name gives (*expected*); ``None`` when it is."""
    found = document["$id"]
    wanted = f'its file name gives "$id": "{expected}"'
    if found in toolkit_uris:
        return f'has the "$id" of a toolkit schema ("{found}"); {wanted}'
    if found != expected:
        return f'has the "$id" "{found}"; {wanted}'
    return None
