"""Unit tests for LLM prompt templates.

Asserts:
- Each template has exactly the 4 required sections in order.
- meta YAML is valid and contains required keys.
- response_schema points to a real schema file.
- response_format is json_object.
- response_shape JSON example validates against the referenced schema.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROMPTS_DIR = (
    Path(__file__).parents[3]
    / "tools" / "specdev_tools" / "llm" / "prompts"
)
SCHEMAS_DIR = (
    Path(__file__).parents[3]
    / "tools" / "specdev_tools" / "llm" / "schemas"
)

TEMPLATE_FILES = [
    "inner_plan.md",
    "inner_repair.md",
    "outer_edit.md",
    "outer_remediate.md",
    "widen_semantic.md",
]

REQUIRED_SECTION_ORDER = ["meta", "system", "user", "response_shape"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sections(text: str) -> dict[str, str]:
    """Split a template into named sections keyed by heading name.

    Sections are delimited by lines matching exactly `# <name>`.
    Returns a dict mapping section name -> section body (text after heading).
    """
    section_pattern = re.compile(r"^# (\w+)\s*$", re.MULTILINE)
    matches = list(section_pattern.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def _extract_yaml_block(meta_body: str) -> str:
    """Extract content inside the first ```yaml ... ``` fence."""
    m = re.search(r"```yaml\s*\n(.*?)```", meta_body, re.DOTALL)
    assert m, "meta section must contain a ```yaml``` fenced block"
    return m.group(1)


def _extract_json_example(response_shape_body: str) -> str:
    """Extract content inside the first ```json ... ``` fence."""
    m = re.search(r"```json\s*\n(.*?)```", response_shape_body, re.DOTALL)
    assert m, "response_shape section must contain a ```json``` fenced block"
    return m.group(1)


def _load_schema(schema_filename: str) -> dict:
    schema_path = SCHEMAS_DIR / schema_filename
    assert schema_path.exists(), f"Schema file not found: {schema_path}"
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parametrised tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", TEMPLATE_FILES)
class TestPromptTemplateStructure:
    """Structure and metadata assertions for each template."""

    def _read(self, filename: str) -> str:
        path = PROMPTS_DIR / filename
        assert path.exists(), f"Template not found: {path}"
        return path.read_text(encoding="utf-8")

    def test_has_exactly_four_sections_in_order(self, filename: str) -> None:
        text = self._read(filename)
        sections = _parse_sections(text)
        assert list(sections.keys()) == REQUIRED_SECTION_ORDER, (
            f"{filename}: expected sections {REQUIRED_SECTION_ORDER}, got {list(sections.keys())}"
        )

    def test_meta_yaml_is_valid(self, filename: str) -> None:
        text = self._read(filename)
        sections = _parse_sections(text)
        yaml_text = _extract_yaml_block(sections["meta"])
        meta = yaml.safe_load(yaml_text)
        assert isinstance(meta, dict), f"{filename}: meta YAML must be a mapping"
        for key in ("name", "model", "loop", "response_schema", "response_format"):
            assert key in meta, f"{filename}: meta is missing required key '{key}'"

    def test_response_schema_file_exists(self, filename: str) -> None:
        text = self._read(filename)
        sections = _parse_sections(text)
        yaml_text = _extract_yaml_block(sections["meta"])
        meta = yaml.safe_load(yaml_text)
        schema_filename = meta["response_schema"]
        schema_path = SCHEMAS_DIR / schema_filename
        assert schema_path.exists(), (
            f"{filename}: response_schema '{schema_filename}' not found under {SCHEMAS_DIR}"
        )

    def test_response_format_is_json_object(self, filename: str) -> None:
        text = self._read(filename)
        sections = _parse_sections(text)
        yaml_text = _extract_yaml_block(sections["meta"])
        meta = yaml.safe_load(yaml_text)
        assert meta["response_format"] == "json_object", (
            f"{filename}: response_format must be 'json_object', got {meta['response_format']!r}"
        )

    def test_response_shape_json_validates_against_schema(self, filename: str) -> None:
        text = self._read(filename)
        sections = _parse_sections(text)

        # Extract meta
        yaml_text = _extract_yaml_block(sections["meta"])
        meta = yaml.safe_load(yaml_text)
        schema_filename = meta["response_schema"]

        # Extract and parse the example JSON
        json_text = _extract_json_example(sections["response_shape"])
        try:
            example = json.loads(json_text)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{filename}: response_shape JSON is not valid JSON: {exc}")

        # Load schema and validate
        schema = _load_schema(schema_filename)
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(example))
        assert not errors, (
            f"{filename}: response_shape example does not validate against {schema_filename}:\n"
            + "\n".join(str(e) for e in errors)
        )


# ---------------------------------------------------------------------------
# Model values per §16.1
# ---------------------------------------------------------------------------

_EXPECTED_MODELS = {
    "widen_semantic.md": "sonnet-4-6",
    "inner_plan.md": "haiku-4-5",
    "inner_repair.md": "haiku-4-5",
    "outer_edit.md": "haiku-4-5",
    "outer_remediate.md": "haiku-4-5",
}


def _read_meta(filename: str) -> dict:
    path = PROMPTS_DIR / filename
    assert path.exists(), f"Template not found: {path}"
    text = path.read_text(encoding="utf-8")
    sections = _parse_sections(text)
    yaml_text = _extract_yaml_block(sections["meta"])
    return yaml.safe_load(yaml_text)


@pytest.mark.parametrize("filename,expected_model", list(_EXPECTED_MODELS.items()))
def test_meta_model_matches_protocol_16_1(filename: str, expected_model: str) -> None:
    meta = _read_meta(filename)
    assert meta.get("model") == expected_model, (
        f"{filename}: expected meta.model == {expected_model!r}, got {meta.get('model')!r}"
    )


# ---------------------------------------------------------------------------
# Loop enum membership per §16.1
# ---------------------------------------------------------------------------

_VALID_LOOP_VALUES = {"inner", "outer-edit", "outer-remediate", "widen"}

_EXPECTED_LOOPS = {
    "inner_plan.md": "inner",
    "inner_repair.md": "inner",
    "outer_edit.md": "outer-edit",
    "outer_remediate.md": "outer-remediate",
    "widen_semantic.md": "widen",
}


@pytest.mark.parametrize("filename", TEMPLATE_FILES)
def test_meta_loop_is_valid_enum_value(filename: str) -> None:
    meta = _read_meta(filename)
    loop = meta.get("loop")
    assert loop in _VALID_LOOP_VALUES, (
        f"{filename}: meta.loop {loop!r} is not a valid enum value; "
        f"expected one of {sorted(_VALID_LOOP_VALUES)}"
    )


@pytest.mark.parametrize("filename,expected_loop", list(_EXPECTED_LOOPS.items()))
def test_meta_loop_matches_template_role(filename: str, expected_loop: str) -> None:
    meta = _read_meta(filename)
    assert meta.get("loop") == expected_loop, (
        f"{filename}: expected meta.loop == {expected_loop!r}, got {meta.get('loop')!r}"
    )
