"""Tests for migration template files in prompts/migration/ directory."""
import re
from pathlib import Path

import pytest


EXPECTED_TEMPLATES = [
    "template_capabilities.md",
    "template_charter.md",
    "template_ci_gates.md",
    "template_completeness_assessment.md",
    "template_delivery_baseline.md",
    "template_extension_manifest.md",
    "template_fixtures.md",
    "template_frs.md",
    "template_glossary.md",
    "template_governance.md",
    "template_impl_coder.md",
    "template_impl_context.md",
    "template_impl_plan.md",
    "template_impl_planner.md",
    "template_impl_reviewer.md",
    "template_interfaces.md",
    "template_invariants.md",
    "template_nfrs.md",
    "template_redteam.md",
    "template_roadmap.md",
    "template_scaffold.md",
    "template_system_sketch.md",
]


@pytest.fixture
def templates_dir(repo_root):
    """Return the migration templates directory."""
    return repo_root / "prompts" / "migration"


class TestAllTemplatesExist:
    """All expected template files exist on disk."""

    def test_all_templates_exist(self, templates_dir):
        missing = [
            name for name in EXPECTED_TEMPLATES
            if not (templates_dir / name).exists()
        ]
        assert missing == [], f"Missing template files: {missing}"

    def test_expected_count(self):
        assert len(EXPECTED_TEMPLATES) == 22


class TestTemplatesReadable:
    """Each template can be read without error."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_template_readable(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        content = path.read_text(encoding="utf-8")
        assert isinstance(content, str)


class TestNoEmptyTemplates:
    """No template file is empty."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_template_not_empty(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, f"{template_name} is empty"


class TestTemplateContentValidation:
    """Templates reference canonical schema URIs and metadata fields."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_templates_reference_canonical_schema_uri(self, templates_dir, template_name):
        """Each template mentions a canonical schema URI (vc: format)."""
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        content = path.read_text(encoding="utf-8")
        has_uri = "vc:" in content
        assert has_uri, (
            f"{template_name} does not reference canonical schema URI"
        )

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_templates_include_metadata_fields(self, templates_dir, template_name):
        """Each template mentions canonical_refs_used."""
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        content = path.read_text(encoding="utf-8")
        assert "canonical_refs_used" in content, (
            f"{template_name} does not mention canonical_refs_used"
        )
