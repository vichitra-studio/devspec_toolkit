"""Unit tests for schema_validate.validate_data_against_schema.

Covers findings F4 and F5 from DEVSPEC-37:
  F4 — fail-closed construction-wrap (validator-construction failure routes to
        SchemaRuntimeError rather than silently returning []).
  F5 — direct typed-exception coverage for each row in §3.1.

Coverage map (all 6 typed-exception rows + construction-wrap + end-to-end):
  Row "SchemaBootstrapError"        → TestSchemaBootstrapError
  Row "NoSchemaError (missing)"     → TestNoSchemaError.test_no_schema_missing, test_no_schema_blank
  Row "NoSchemaError (non-str)"     → TestNoSchemaError.test_no_schema_wrong_type_int, test_no_schema_wrong_type_list
  Row "SchemaNotFoundError"         → TestSchemaNotFoundError.test_schema_not_found_unregistered_uri
  Row "SchemaDecodeError" (JSON)    → TestSchemaDecodeError.test_schema_decode_error_corrupt_file
  Row "SchemaDecodeError" (Unicode) → TestSchemaDecodeError.test_schema_decode_error_unicode
  Row "SchemaReferencingError"      → TestSchemaReferencingError.test_schema_referencing_error_dangling_ref
  Row "SchemaRuntimeError (F4a)"    → TestConstructionWrap.test_construction_wrap_raises_schema_runtime_error
  F4b end-to-end                    → TestConstructionWrap.test_construction_wrap_e2e_json_patch_refuses
  Happy path (valid doc)            → TestHappyPath.test_happy_path_valid_doc_returns_empty_list
  Happy path (invalid enum)         → TestHappyPath.test_happy_path_invalid_enum_returns_errors
  Input immutability                → TestHappyPath.test_input_dict_not_mutated
"""
from __future__ import annotations

import copy
import json
import pathlib
import shutil

import pytest

from specdev_tools.core.schema_validate import (
    NoSchemaError,
    SchemaBootstrapError,
    SchemaDecodeError,
    SchemaNotFoundError,
    SchemaReferencingError,
    SchemaRuntimeError,
    SchemaValidationError,
    validate_data_against_schema,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# Toolkit root — guaranteed to have tools/schema_registry.json.
_TOOLKIT_ROOT = str(pathlib.Path(__file__).resolve().parents[3])

# Step-16 impl-context fixtures directory.
_STEP16_DIR = pathlib.Path(_TOOLKIT_ROOT) / "tests" / "fixtures" / "step_16" / "impl_context"


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _load_valid_full() -> dict:
    """Load valid_full.json (a known-good step-16 impl-context document)."""
    return json.loads((_STEP16_DIR / "valid_full.json").read_text(encoding="utf-8"))


def _make_corrupt_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Build a minimal fake toolkit root where the schema file is corrupt JSON.

    Layout:
        <tmp>/tools/schema_registry.json  → {"vc:corrupt": "corrupt.json"}
        <tmp>/corrupt.json                → not valid JSON

    The _preload_store in SchemaRegistry silently skips the corrupt file
    (swallows JSONDecodeError), but registry.load() re-reads and raises.
    """
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    registry_map = {"vc:corrupt": "corrupt.json"}
    (tools_dir / "schema_registry.json").write_text(
        json.dumps(registry_map), encoding="utf-8"
    )
    (tmp_path / "corrupt.json").write_text("this is NOT valid json {{{", encoding="utf-8")
    return tmp_path


def _make_dangling_ref_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Build a minimal fake toolkit root where the schema has a dangling $ref.

    Layout:
        <tmp>/tools/schema_registry.json  → {"vc:dangling": "dangling.json"}
        <tmp>/dangling.json               → schema with a property whose $ref
                                            points to a URN not in the registry

    The schema MUST carry a $schema dialect key so that SchemaRegistry
    successfully calls from_contents() during construction (otherwise
    to_referencing_registry() raises CannotDetermineSpecification, routing into
    SchemaRuntimeError instead of SchemaReferencingError).

    When iter_errors tries to resolve the dangling URN, it raises
    _WrappedReferencingError → schema_validate catches it as SchemaReferencingError.
    """
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    dangling_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "name": {"$ref": "urn:totally-nonexistent-resource"},
        },
    }
    (tmp_path / "dangling.json").write_text(json.dumps(dangling_schema), encoding="utf-8")
    registry_map = {"vc:dangling": "dangling.json"}
    (tools_dir / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# F4a — construction-wrap raises SchemaRuntimeError (NOT returns [])
# ---------------------------------------------------------------------------


class TestConstructionWrap:
    """F4: validator-construction failure is routed to SchemaRuntimeError (fail-closed)."""

    def test_construction_wrap_raises_schema_runtime_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """F4a: monkeypatching Draft202012Validator.__init__ to raise AttributeError
        causes validate_data_against_schema to raise SchemaRuntimeError rather than
        returning [] silently.

        This is the exact round-2 regression: the construction-wrap at lines 238-248
        of schema_validate.py must catch the AttributeError and re-raise as
        SchemaRuntimeError.
        """
        from jsonschema import Draft202012Validator as _RealValidator

        class _FakeBrokenValidator:
            """Fake validator whose constructor always raises AttributeError."""

            # Expose the real FORMAT_CHECKER so the attribute-access on line 243
            # (`format_checker=Draft202012Validator.FORMAT_CHECKER`) does NOT itself
            # raise — only __init__ should raise, testing that specific path.
            FORMAT_CHECKER = _RealValidator.FORMAT_CHECKER

            def __init__(self, *args, **kwargs):
                raise AttributeError("injected: non-dict schema has no $schema key")

        import specdev_tools.core.schema_validate as _sv_mod

        monkeypatch.setattr(_sv_mod, "Draft202012Validator", _FakeBrokenValidator)

        doc = _load_valid_full()

        with pytest.raises(SchemaRuntimeError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)

        # The original exception must be carried on .original.
        assert isinstance(exc_info.value.original, AttributeError), (
            f"expected .original to be AttributeError; got {type(exc_info.value.original)}"
        )

    def test_construction_wrap_e2e_json_patch_refuses(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
    ) -> None:
        """F4b end-to-end: with the validator constructor broken, json_patch
        REFUSES (raises) and the file content is UNCHANGED.

        This proves WS1 caller (_call_validate_or_raise) maps SchemaRuntimeError
        to a fail-closed JsonUtilsError refusal rather than silently writing.
        """
        from jsonschema import Draft202012Validator as _RealValidator
        from specdev_tools.core.json_utils import JsonUtilsError, json_patch

        # Copy fixture to tmp so the original is not modified.
        src = _STEP16_DIR / "valid_full.json"
        dst = tmp_path / "valid_full.json"
        shutil.copy2(str(src), str(dst))

        original_bytes = dst.read_bytes()

        class _FakeBrokenValidator:
            FORMAT_CHECKER = _RealValidator.FORMAT_CHECKER

            def __init__(self, *args, **kwargs):
                raise AttributeError("injected: broken validator")

        import specdev_tools.core.schema_validate as _sv_mod

        monkeypatch.setattr(_sv_mod, "Draft202012Validator", _FakeBrokenValidator)

        # A syntactically valid patch; the refusal must come from validation, not jq.
        with pytest.raises(JsonUtilsError) as exc_info:
            json_patch(
                str(dst),
                ".plan.spec_alignment.checklist[1].implementation.status",
                '"in_progress"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

        # The error must originate from the construction-wrap / WS1 fail-closed path.
        assert "refusing to proceed" in str(exc_info.value), (
            f"Expected 'refusing to proceed' in JsonUtilsError message; got: {exc_info.value!r}"
        )

        # File must be UNCHANGED — the broken constructor must not allow a silent write.
        assert dst.read_bytes() == original_bytes, (
            "File was written despite constructor failure — fail-closed guarantee violated"
        )


# ---------------------------------------------------------------------------
# F5 — typed-exception coverage per §3.1
# ---------------------------------------------------------------------------


class TestNoSchemaError:
    """Row: $schema missing, blank, or non-string → NoSchemaError."""

    def test_no_schema_missing(self) -> None:
        """No $schema key → NoSchemaError with got_type=None."""
        doc = {"id": "step-03", "owner": "api"}
        with pytest.raises(NoSchemaError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert exc_info.value.got_type is None

    def test_no_schema_blank(self) -> None:
        """Blank $schema string → NoSchemaError with got_type=None (stripped to empty)."""
        doc = {"$schema": "   ", "id": "step-03"}
        with pytest.raises(NoSchemaError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert exc_info.value.got_type is None

    def test_no_schema_wrong_type_int(self) -> None:
        """$schema=123 (integer) → NoSchemaError with got_type='int'."""
        doc = {"$schema": 123, "id": "step-03"}
        with pytest.raises(NoSchemaError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert exc_info.value.got_type == "int"

    def test_no_schema_wrong_type_list(self) -> None:
        """$schema=[] (list) → NoSchemaError with got_type='list'."""
        doc = {"$schema": [], "id": "step-03"}
        with pytest.raises(NoSchemaError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert exc_info.value.got_type == "list"

    def test_no_schema_is_schema_validation_error(self) -> None:
        """NoSchemaError is a subclass of SchemaValidationError (common base)."""
        doc = {"id": "step-03"}
        with pytest.raises(SchemaValidationError):
            validate_data_against_schema(_TOOLKIT_ROOT, doc)


class TestSchemaBootstrapError:
    """Row: SchemaRegistry(repo_root) fails → SchemaBootstrapError."""

    def test_bootstrap_error_bad_repo_root(self, tmp_path: pathlib.Path) -> None:
        """An empty tmp_path has no tools/schema_registry.json → OSError → SchemaBootstrapError.

        The $schema key must be a non-blank string so Step 1 (NoSchemaError check)
        passes and we reach Step 2 (bootstrap).
        """
        doc = {"$schema": "vc:anything", "id": "step-test"}
        with pytest.raises(SchemaBootstrapError) as exc_info:
            validate_data_against_schema(str(tmp_path), doc)

        # .original must be an OSError (FileNotFoundError ⊂ OSError).
        assert isinstance(exc_info.value.original, OSError), (
            f"expected .original to be OSError; got {type(exc_info.value.original)}"
        )

    def test_bootstrap_error_is_schema_validation_error(self, tmp_path: pathlib.Path) -> None:
        """SchemaBootstrapError is a subclass of SchemaValidationError."""
        doc = {"$schema": "vc:anything"}
        with pytest.raises(SchemaValidationError):
            validate_data_against_schema(str(tmp_path), doc)


class TestSchemaNotFoundError:
    """Row: registry.load → OSError (unregistered or missing schema) → SchemaNotFoundError."""

    def test_schema_not_found_unregistered_uri(self) -> None:
        """An unregistered $schema URI causes registry.load to raise FileNotFoundError
        (a subclass of OSError), which is wrapped as SchemaNotFoundError.

        The URI 'vc:this-uri-is-not-in-the-registry' is deliberately unknown.
        registry.resolve() returns None → registry.load raises FileNotFoundError →
        the OSError clause in validate_data_against_schema catches it.
        """
        doc = {"$schema": "vc:this-uri-is-not-in-the-registry", "id": "step-test"}
        with pytest.raises(SchemaNotFoundError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)

        exc = exc_info.value
        assert exc.uri == "vc:this-uri-is-not-in-the-registry"
        assert exc.detail, "detail must be a non-empty string"

    def test_schema_not_found_is_schema_validation_error(self) -> None:
        """SchemaNotFoundError is a subclass of SchemaValidationError."""
        doc = {"$schema": "vc:completely-missing-uri"}
        with pytest.raises(SchemaValidationError):
            validate_data_against_schema(_TOOLKIT_ROOT, doc)


class TestSchemaDecodeError:
    """Row: registry.load → JSONDecodeError → SchemaDecodeError."""

    def test_schema_decode_error_corrupt_file(self, tmp_path: pathlib.Path) -> None:
        """A corrupt (non-JSON) schema file causes JSONDecodeError wrapped as SchemaDecodeError.

        Approach: build a minimal fake toolkit root where:
          - tools/schema_registry.json maps 'vc:corrupt' → 'corrupt.json'
          - corrupt.json contains non-JSON bytes

        SchemaRegistry._preload_store silently swallows the JSONDecodeError during
        bootstrap, but registry.load() re-reads the file and raises JSONDecodeError
        there — which schema_validate catches and maps to SchemaDecodeError.
        """
        fake_root = _make_corrupt_repo(tmp_path)
        doc = {"$schema": "vc:corrupt", "id": "step-test"}

        with pytest.raises(SchemaDecodeError) as exc_info:
            validate_data_against_schema(str(fake_root), doc)

        exc = exc_info.value
        assert exc.uri == "vc:corrupt"
        assert exc.detail, "detail must be a non-empty string"

    def test_schema_decode_error_is_schema_validation_error(self, tmp_path: pathlib.Path) -> None:
        """SchemaDecodeError is a subclass of SchemaValidationError."""
        fake_root = _make_corrupt_repo(tmp_path)
        doc = {"$schema": "vc:corrupt"}
        with pytest.raises(SchemaValidationError):
            validate_data_against_schema(str(fake_root), doc)

    def test_schema_decode_error_unicode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """registry.load → UnicodeDecodeError maps to SchemaDecodeError (line 217-223).

        This clause is unreachable in normal flow — the bootstrap pre-read catches
        malformed bytes first — so it is exercised by forcing registry.load to raise
        UnicodeDecodeError directly. UnicodeDecodeError is a ValueError subclass (NOT
        an OSError), so the preceding OSError clause must NOT shadow it; this test
        guards that ordering and the typed family's completeness if a future
        SchemaRegistry change makes the path reachable.
        """
        import specdev_tools.core.schema_validate as _sv_mod

        def _raise_unicode(self, uri):  # noqa: ANN001
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        # Bootstrap (SchemaRegistry.__init__) still runs on the real toolkit root;
        # only .load is replaced, so we reach Step 3 and hit the decode clause.
        monkeypatch.setattr(_sv_mod.SchemaRegistry, "load", _raise_unicode)
        doc = {"$schema": "vc:anything", "id": "step-test"}

        with pytest.raises(SchemaDecodeError) as exc_info:
            validate_data_against_schema(_TOOLKIT_ROOT, doc)

        exc = exc_info.value
        assert exc.uri == "vc:anything"
        assert "invalid start byte" in exc.detail


# ---------------------------------------------------------------------------
# F5 — SchemaReferencingError: iter_errors → _WrappedReferencingError
# ---------------------------------------------------------------------------


class TestSchemaReferencingError:
    """Row: iter_errors → _WrappedReferencingError → SchemaReferencingError."""

    def test_schema_referencing_error_dangling_ref(self, tmp_path: pathlib.Path) -> None:
        """A schema with a property whose $ref resolves to an unregistered URN
        causes iter_errors to raise _WrappedReferencingError, which is wrapped
        as SchemaReferencingError.

        Construction succeeds because the schema carries a proper $schema dialect
        key.  The error fires only at iter_errors time, testing line 253.
        """
        fake_root = _make_dangling_ref_repo(tmp_path)
        # The 'name' field triggers resolution of the dangling $ref during iter_errors.
        doc = {"$schema": "vc:dangling", "name": "test-value"}

        with pytest.raises(SchemaReferencingError) as exc_info:
            validate_data_against_schema(str(fake_root), doc)

        # .original must carry the underlying referencing exception.
        assert exc_info.value.original is not None, ".original must be set"
        # The error message should mention the unresolvable URN.
        err_str = str(exc_info.value)
        assert "nonexistent" in err_str or "Unresolvable" in err_str, (
            f"Expected URN mention in SchemaReferencingError message; got: {err_str!r}"
        )

    def test_schema_referencing_error_is_schema_validation_error(
        self, tmp_path: pathlib.Path
    ) -> None:
        """SchemaReferencingError is a subclass of SchemaValidationError."""
        fake_root = _make_dangling_ref_repo(tmp_path)
        doc = {"$schema": "vc:dangling", "name": "test"}
        with pytest.raises(SchemaValidationError):
            validate_data_against_schema(str(fake_root), doc)


# ---------------------------------------------------------------------------
# F5 — happy path: return shape and input immutability
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Happy path: valid doc → [], invalid doc → [(path_tuple, message), ...] list."""

    def test_happy_path_valid_doc_returns_empty_list(self) -> None:
        """A known-valid step-16 impl-context document returns an empty list."""
        doc = _load_valid_full()
        result = validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert result == [], f"Expected no errors for valid_full.json; got {result}"

    def test_happy_path_returns_list_type(self) -> None:
        """Return value is always a list (never None, never raises)."""
        doc = _load_valid_full()
        result = validate_data_against_schema(_TOOLKIT_ROOT, doc)
        assert isinstance(result, list)

    def test_happy_path_invalid_enum_returns_errors(self) -> None:
        """A doc with an invalid enum value returns a non-empty list.

        Each element must be a (tuple, str) pair where the tuple is the path
        and the str is the error message from jsonschema.
        """
        doc = _load_valid_full()
        # Introduce an invalid enum value in checklist[1].implementation.status.
        doc["plan"]["spec_alignment"]["checklist"][1]["implementation"]["status"] = "verifyed"

        result = validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert len(result) > 0, "Expected at least one error for invalid enum"

        # Check return shape: list of (tuple, str).
        for item in result:
            assert isinstance(item, tuple) and len(item) == 2, (
                f"Each element must be a 2-tuple; got {item!r}"
            )
            path_tuple, message = item
            assert isinstance(path_tuple, tuple), (
                f"First element must be a tuple (path); got {type(path_tuple)}"
            )
            assert isinstance(message, str), (
                f"Second element must be a str (message); got {type(message)}"
            )

        # At least one error must mention the enum violation.
        all_messages = " ".join(msg for _, msg in result)
        assert "is not one of" in all_messages or "verifyed" in all_messages, (
            f"Expected enum-mismatch message in errors; got: {result!r}"
        )

    def test_input_dict_not_mutated(self) -> None:
        """validate_data_against_schema must NOT mutate the input dict.

        The helper strips $schema from an internal *copy* (payload = dict(data)),
        so the original dict must be unchanged after the call.
        """
        doc = _load_valid_full()
        original_copy = copy.deepcopy(doc)

        validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert doc == original_copy, (
            "Input dict was mutated by validate_data_against_schema — "
            "$schema was likely popped from the original instead of a copy"
        )

    def test_input_schema_key_preserved(self) -> None:
        """The '$schema' key in the input dict must survive the call unchanged."""
        doc = _load_valid_full()
        original_uri = doc["$schema"]

        validate_data_against_schema(_TOOLKIT_ROOT, doc)

        assert "$schema" in doc, "$schema key was removed from the input dict"
        assert doc["$schema"] == original_uri, "$schema value was modified"
