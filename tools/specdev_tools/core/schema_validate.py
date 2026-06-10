"""schema_validate — resolution-agnostic schema validation core.

Factored from ``validation/validate.py`` so that both the spec-check
validator and the ``json patch``/``insert`` pre-write guardrail (Chunk E /
WS1) can share one implementation without importing each other.

SoC contract
------------
* ``repo_root`` MUST be an **already-resolved** toolkit root.  This helper
  performs NO package-relative fallback — that logic belongs in the caller
  layer (``json_utils`` for WS1; ``validate_file`` already supplies a correct
  ``repo_root`` via ``--repo-root``).
* The ``SchemaRegistry`` bootstrap is performed HERE (inside the helper) so
  that both callers get the same bootstrap error surface.  ``validate_file``
  additionally does its own bootstrap at the top of the function (before file
  I/O) for error-precedence reasons; that outer bootstrap result is discarded
  once the helper is called — the helper's bootstrap is the active one.

Typed-exception contract (§3.1 of DEVSPEC-37)
----------------------------------------------
Every schema-layer failure is surfaced as a distinct typed exception so
callers can reconstruct byte-identical error messages without guessing the
failure category.  All exceptions share the common base ``SchemaValidationError``
so Chunk E callers can use a single ``except SchemaValidationError`` clause:

  SchemaValidationError  — common base for all schema-layer failures
  ├── SchemaBootstrapError  — ``SchemaRegistry(repo_root)`` construction failed
  │                           (carries ``.original``, the triggering exception)
  ├── NoSchemaError         — ``$schema`` key missing, blank, or non-string
  │                           (carries ``.got_type: str | None``)
  ├── SchemaNotFoundError   — ``registry.load`` → OSError (incl. FileNotFoundError,
  │                           PermissionError, etc.)  (carries ``.uri``, ``.detail``)
  ├── SchemaDecodeError     — ``registry.load`` → JSONDecodeError
  │                           (carries ``.uri``, ``.detail``)
  ├── SchemaReferencingError — ``iter_errors`` → _WrappedReferencingError
  │                           (carries ``.original``, the original exception)
  └── SchemaRuntimeError    — ``iter_errors`` → any other Exception; also raised
                              for validator/registry-construction failures
                              (``to_referencing_registry()`` or
                              ``Draft202012Validator()`` raise unexpectedly)
                              (carries ``.original``, the original exception)

The happy path returns ``list[tuple[tuple, str]]`` — raw ``(path_tuple,
message)`` pairs, hint-agnostic.  The hint-enhancement loop stays in
``validate_file`` where it belongs.
"""
from __future__ import annotations

import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError  # type: ignore[attr-defined]

from .registry import SchemaRegistry


# ---------------------------------------------------------------------------
# Public typed exceptions
# ---------------------------------------------------------------------------

class SchemaValidationError(Exception):
    """Common base for all schema-layer typed exceptions.

    Catch this to handle any failure from ``validate_data_against_schema``
    in a single ``except`` clause.
    """


class SchemaBootstrapError(SchemaValidationError):
    """Raised when ``SchemaRegistry(repo_root)`` construction fails.

    Carries the **original** exception (``OSError``, ``json.JSONDecodeError``,
    ``ValueError``, or ``TypeError``) so callers can reconstruct the error
    message byte-identically.
    """

    def __init__(self, original: Exception) -> None:
        self.original = original
        super().__init__(f"schema_registry_bootstrap_failed: {type(original).__name__}: {original}")


class NoSchemaError(SchemaValidationError):
    """Raised when ``data["$schema"]`` is missing, blank, or not a string.

    ``got_type`` is the Python type name of the actual value, or ``None``
    when the key was absent / blank (i.e. "missing" rather than "wrong type").
    """

    def __init__(self, got_type: str | None = None) -> None:
        self.got_type = got_type
        super().__init__(f"$schema missing or blank (got_type={got_type!r})")


class SchemaNotFoundError(SchemaValidationError):
    """Raised when ``registry.load(uri)`` throws ``OSError`` (incl. ``FileNotFoundError``).

    Broadened from ``FileNotFoundError`` to ``OSError`` so permission-denied
    and other I/O failures are also surfaced as a typed member of the family.
    """

    def __init__(self, uri: str, detail: str) -> None:
        self.uri = uri
        self.detail = detail
        super().__init__(f"schema_not_found uri={uri} detail={detail}")


class SchemaDecodeError(SchemaValidationError):
    """Raised when ``registry.load(uri)`` throws ``json.JSONDecodeError``."""

    def __init__(self, uri: str, detail: str) -> None:
        self.uri = uri
        self.detail = detail
        super().__init__(f"schema_json_decode_failed uri={uri} detail={detail}")


class SchemaReferencingError(SchemaValidationError):
    """Raised when ``iter_errors`` throws ``_WrappedReferencingError``.

    Carries the **original** exception so callers can embed ``str(original)``
    byte-identically into the E520 message.
    """

    def __init__(self, original: Exception) -> None:
        self.original = original
        super().__init__(str(original))


class SchemaRuntimeError(SchemaValidationError):
    """Raised when ``iter_errors`` throws any non-referencing ``Exception``.

    Carries the **original** exception so callers can embed
    ``type(original).__name__`` and ``str(original)`` into the E521 message.
    """

    def __init__(self, original: Exception) -> None:
        self.original = original
        super().__init__(f"{type(original).__name__}: {original}")


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def validate_data_against_schema(
    repo_root: str,
    data: dict,
) -> list[tuple[tuple, str]]:
    """Validate *data* against the schema declared by its ``"$schema"`` key.

    Parameters
    ----------
    repo_root:
        Absolute path to the toolkit root (``tools/schema_registry.json``
        must exist there).  The caller is responsible for resolution; this
        helper performs no package-relative fallback.
    data:
        The document to validate.  Must be a ``dict``; the ``"$schema"``
        field is read from it and then stripped from the validation payload
        (mirrors ``validate.py:215-216``).

    Returns
    -------
    list[tuple[tuple, str]]
        ``[(path_tuple, message), ...]`` — raw, hint-agnostic error pairs
        from ``jsonschema``.  The list is **unsorted**; callers that need a
        deterministic order (e.g. ``validate_file``) must sort externally.

    Raises
    ------
    SchemaBootstrapError
        ``SchemaRegistry(repo_root)`` raised ``OSError``, ``json.JSONDecodeError``,
        ``ValueError``, or ``TypeError``.  Note: ``validate_file`` does its own
        bootstrap probe FIRST and returns early on failure, so
        ``SchemaBootstrapError`` is unreachable via that path (the probe's
        ``schema_registry_bootstrap_failed`` message is emitted instead).
        Callers without a probe (e.g. Chunk E json_utils) will see this exception.
    NoSchemaError
        ``data["$schema"]`` is absent, blank, or not a ``str``.
    SchemaNotFoundError
        ``SchemaRegistry.load(uri)`` raised ``OSError`` (including
        ``FileNotFoundError``, ``PermissionError``, and other I/O errors).
    SchemaDecodeError
        ``SchemaRegistry.load(uri)`` raised ``json.JSONDecodeError``.
    SchemaReferencingError
        ``Draft202012Validator.iter_errors`` raised ``_WrappedReferencingError``.
    SchemaRuntimeError
        ``Draft202012Validator.iter_errors`` raised any other ``Exception``;
        also raised when ``registry.to_referencing_registry()`` or
        ``Draft202012Validator()`` construction raises an unexpected exception
        (e.g. ``referencing.exceptions.CannotDetermineSpecification`` or
        ``AttributeError`` for a non-dict schema).

    All of the above are subclasses of ``SchemaValidationError`` so a single
    ``except SchemaValidationError`` clause handles the whole family.
    """
    # --- Step 1: validate and extract $schema ---
    schema_uri = data.get("$schema")
    if schema_uri is None:
        raise NoSchemaError(got_type=None)
    if not isinstance(schema_uri, str):
        raise NoSchemaError(got_type=type(schema_uri).__name__)
    schema_uri = schema_uri.strip()
    if not schema_uri:
        raise NoSchemaError(got_type=None)

    # --- Step 2: bootstrap registry (wrapped as typed exception) ---
    try:
        registry = SchemaRegistry(repo_root)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise SchemaBootstrapError(original=exc) from exc

    # --- Step 3: load schema file ---
    try:
        schema = registry.load(schema_uri)
    except OSError as exc:
        raise SchemaNotFoundError(uri=schema_uri, detail=str(exc)) from exc
    except UnicodeDecodeError as exc:
        # Bad UTF-8 in the schema file is a decode failure, not an I/O failure.
        # UnicodeDecodeError is a ValueError subclass (NOT an OSError), so the
        # OSError clause above does not shadow it.  Unreachable in normal flow
        # (the bootstrap pre-read catches malformed bytes first); caught here so
        # the typed family is formally complete.
        raise SchemaDecodeError(uri=schema_uri, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise SchemaDecodeError(uri=schema_uri, detail=str(exc)) from exc

    # --- Step 4: build validation payload (strip $schema, mirror validate.py:215-216) ---
    payload = dict(data)
    payload.pop("$schema", None)

    # --- Step 5: build referencing registry and validator ---
    # Wrapped fail-closed: ``to_referencing_registry()`` can raise
    # ``referencing.exceptions.CannotDetermineSpecification`` (not an
    # OSError/JSONDecodeError/ValueError/TypeError) when a schema in the
    # store lacks a ``$schema`` key; ``Draft202012Validator(non-dict)`` can
    # raise ``AttributeError``.  Both escape the existing family — route them
    # into SchemaRuntimeError so callers see the typed E521 path.
    try:
        reg = registry.to_referencing_registry()
        v = Draft202012Validator(
            schema,
            registry=reg,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
    except SchemaValidationError:
        raise
    except Exception as exc:
        raise SchemaRuntimeError(original=exc) from exc

    # --- Step 6: iterate errors ---
    try:
        raw_errors = list(v.iter_errors(payload))
    except _WrappedReferencingError as exc:
        raise SchemaReferencingError(original=exc) from exc
    except Exception as exc:
        raise SchemaRuntimeError(original=exc) from exc

    return [(tuple(e.path), e.message) for e in raw_errors]
