"""Tests for specdev_tools.generation.prompt_generator — prompt generation.

Created by FIX-048 (Batch 5).
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from specdev_tools.generation.prompt_generator import (
    GeneratedPrompt,
    PromptContext,
    _extract_required_fields,
    format_prompts_report,
    get_templates_dir,
    list_templates,
    load_template,
    render_template,
    select_template,
)
from specdev_tools.generation.schema_differ import (
    DiffType,
    FieldDiff,
    MigrationAction,
    MigrationDiff,
    StepDiff,
)


# ---------------------------------------------------------------------------
# get_templates_dir / load_template / list_templates
# ---------------------------------------------------------------------------

class TestTemplateLoading:
    def test_get_templates_dir(self, tmp_path):
        result = get_templates_dir(tmp_path)
        assert result == tmp_path / "prompts" / "migration"

    def test_load_template_success(self, tmp_path):
        d = tmp_path / "prompts" / "migration"
        d.mkdir(parents=True)
        (d / "template_test.md").write_text("Hello {{STEP_ID}}")
        result = load_template(tmp_path, "template_test.md")
        assert result == "Hello {{STEP_ID}}"

    def test_load_template_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_template(tmp_path, "nonexistent.md")

    def test_list_templates(self, tmp_path):
        d = tmp_path / "prompts" / "migration"
        d.mkdir(parents=True)
        (d / "template_charter.md").write_text("a")
        (d / "template_frs.md").write_text("b")
        (d / "not_a_template.md").write_text("c")
        result = list_templates(tmp_path)
        assert "template_charter.md" in result
        assert "template_frs.md" in result
        assert "not_a_template.md" not in result

    def test_list_templates_empty_dir(self, tmp_path):
        assert list_templates(tmp_path) == []


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    def test_simple_substitution(self):
        ctx = PromptContext(step_id="04_frs", target_version="0.3.0")
        result = render_template("Step: {{STEP_ID}}, Version: {{TARGET_VERSION}}", ctx)
        assert "04_frs" in result
        assert "0.3.0" in result

    def test_missing_var_warns(self):
        ctx = PromptContext(step_id="test")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            render_template("{{UNKNOWN_VAR}}", ctx)
            assert any("UNKNOWN_VAR" in str(warning.message) for warning in w)

    def test_each_block(self):
        ctx = PromptContext(
            step_id="test",
            required_fields=[
                {"path": "name", "type": "string"},
                {"path": "id", "type": "string"},
            ],
        )
        template = "{{#each REQUIRED_FIELDS}}- {{this.path}}: {{this.type}}\n{{/each}}"
        result = render_template(template, ctx)
        assert "- name: string" in result
        assert "- id: string" in result

    def test_each_block_empty_array(self):
        ctx = PromptContext(step_id="test", required_fields=[])
        template = "Before{{#each REQUIRED_FIELDS}}item{{/each}}After"
        result = render_template(template, ctx)
        assert result == "BeforeAfter"

    def test_extra_context(self):
        ctx = PromptContext(step_id="test", extra={"CUSTOM_VAR": "custom_value"})
        result = render_template("{{CUSTOM_VAR}}", ctx)
        assert "custom_value" in result

    def test_source_version_none_renders_na(self):
        ctx = PromptContext(source_version=None, step_id="test")
        result = render_template("{{SOURCE_VERSION}}", ctx)
        assert "N/A" in result


# ---------------------------------------------------------------------------
# select_template
# ---------------------------------------------------------------------------

class TestSelectTemplate:
    def test_fallback_to_charter(self):
        result = select_template()
        assert result == "template_charter.md"

    def test_step_diff_lookup(self):
        sd = StepDiff(step_id="04_frs", status="missing")
        result = select_template(step_diff=sd)
        # Should resolve based on step prefix "04"
        assert result.endswith(".md")

    def test_changelog_explicit_template(self):
        from specdev_tools.core.changelog_parser import ChangelogEntry, MigrationInfo
        mi = MigrationInfo(action="auto", prompt="template_custom.md")
        ce = ChangelogEntry(type="add_step", step_id="04", description="test", migration=mi)
        result = select_template(changelog_entry=ce)
        assert result == "template_custom.md"


# ---------------------------------------------------------------------------
# _extract_required_fields
# ---------------------------------------------------------------------------

class TestExtractRequiredFields:
    def test_extracts_required(self):
        schema = {
            "required": ["name", "id"],
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "id": {"type": "string", "pattern": "^[a-z]+$"},
                "optional": {"type": "number"},
            },
        }
        fields = _extract_required_fields(schema)
        assert len(fields) == 2
        paths = {f["path"] for f in fields}
        assert paths == {"name", "id"}

    def test_constraints_extracted(self):
        schema = {
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        }
        fields = _extract_required_fields(schema)
        assert "minLength" in fields[0]["constraints"]

    def test_nested_objects(self):
        schema = {
            "required": ["meta"],
            "properties": {
                "meta": {
                    "type": "object",
                    "required": ["version"],
                    "properties": {
                        "version": {"type": "string"},
                    },
                },
            },
        }
        fields = _extract_required_fields(schema)
        paths = {f["path"] for f in fields}
        assert "meta" in paths
        assert "meta.version" in paths

    def test_empty_schema(self):
        assert _extract_required_fields({}) == []


# ---------------------------------------------------------------------------
# format_prompts_report
# ---------------------------------------------------------------------------

class TestFormatPromptsReport:
    def test_no_prompts(self):
        result = format_prompts_report([])
        assert "No AI-assisted prompts needed" in result

    def test_with_prompts(self):
        prompts = [
            GeneratedPrompt(
                filename="01_missing_04_frs.md",
                template_name="template_frs.md",
                step_id="04_frs",
                content="test content",
                priority=1,
            ),
        ]
        result = format_prompts_report(prompts)
        assert "1 prompt(s) generated" in result
        assert "04_frs" in result
