"""Prompt generator for DevSpec Toolkit migration system.

Generates context-aware AI prompts for semantic migrations that cannot be
handled automatically. Works with the schema_differ to identify what needs
AI-assisted migration and generates verbose, predictable prompts.

Core Template Variables (always populated):
- SOURCE_VERSION, TARGET_VERSION, STEP_ID, TIMESTAMP
- SOURCE_FILE, TARGET_FILE, SOURCE_CONTENT, TARGET_SCHEMA, SCHEMA_REF
- REQUIRED_FIELDS (with path, type, description, constraints, default, extraction_hint)
- CONTEXT_SOURCES (from changelog migration.context_sources)

Field-Level Variables (auto-populated based on diff type):
- FIELD_PATH, FIELD_TYPE, FIELD_DESCRIPTION, FIELD_CONSTRAINTS
- OLD_FIELD_PATH, NEW_FIELD_PATH (for renames)
- OLD_TYPE, NEW_TYPE, CHANGE_REASON (for type coercion)
- REMOVAL_REASON, REPLACEMENT_FIELD (for removals)
- CONFLICT_TYPE, CONFLICT_DESCRIPTION (for broken refs)

Step-Level Variables (auto-populated based on status):
- OLD_STEP_ID, NEW_STEP_ID, RENAME_REASON (for step renames)
- ARCHIVE_PATH, FILENAME (for archive operations)
- CHANGE_REASON (from changelog description)

See: docs/developers/workflows/migration_system_spec.md
"""
from __future__ import annotations

import json
import re
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema_differ import (
    DiffType,
    FieldDiff,
    MigrationAction,
    MigrationDiff,
    ParadigmShift,
    StepDiff,
)
from ..core.changelog_parser import (
    ChangelogEntry,
    MigrationInfo,
    VersionChangelog,
    get_changes_between,
    load_version,
)


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass
class GeneratedPrompt:
    """Represents a generated migration prompt."""
    
    filename: str                    # e.g., "01_add_step_13_extension_generator.md"
    template_name: str               # Which template was used
    step_id: Optional[str] = None    # Which step it's for
    field_path: Optional[str] = None # For field-level prompts
    content: str = ""                # Fully rendered prompt
    priority: int = 0                # Lower = higher priority (for ordering)


@dataclass
class PromptContext:
    """Context data for template rendering."""
    
    source_version: Optional[str] = None
    target_version: str = ""
    step_id: str = ""
    source_file: Optional[str] = None
    target_file: Optional[str] = None
    source_content: str = ""
    target_schema: str = ""
    schema_ref: str = ""
    required_fields: List[Dict[str, Any]] = field(default_factory=list)
    context_sources: List[Dict[str, str]] = field(default_factory=list)
    field_path: str = ""
    field_type: str = ""
    field_description: str = ""
    field_constraints: str = ""
    old_field_path: str = ""
    new_field_path: str = ""
    old_type: str = ""
    new_type: str = ""
    timestamp: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Template Loading
# -----------------------------------------------------------------------------

def get_templates_dir(toolkit_root: Path) -> Path:
    """Get the path to migration prompt templates directory."""
    return toolkit_root / "prompts" / "migration"


def load_template(toolkit_root: Path, template_name: str) -> str:
    """Load a template file from the migration templates directory.
    
    Args:
        toolkit_root: Path to devspec_toolkit root
        template_name: Template filename (e.g., "template_add_step.md")
        
    Returns:
        Template content as string
        
    Raises:
        FileNotFoundError: If template doesn't exist
    """
    template_path = get_templates_dir(toolkit_root) / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def list_templates(toolkit_root: Path) -> List[str]:
    """List all available templates.
    
    Args:
        toolkit_root: Path to devspec_toolkit root
        
    Returns:
        List of template filenames
    """
    templates_dir = get_templates_dir(toolkit_root)
    if not templates_dir.exists():
        return []
    return [f.name for f in templates_dir.glob("template_*.md")]


# -----------------------------------------------------------------------------
# Template Rendering
# -----------------------------------------------------------------------------

def render_template(template: str, context: PromptContext) -> str:
    """Render a template with context variables.
    
    Supports:
    - {{VAR}} - Simple variable substitution
    - {{#each ARRAY}}...{{/each}} - Array iteration
    
    Args:
        template: Template string with placeholders
        context: PromptContext with values
        
    Returns:
        Rendered template string
    """
    result = template
    
    # Build context dict from dataclass
    ctx = {
        "SOURCE_VERSION": context.source_version or "N/A",
        "TARGET_VERSION": context.target_version,
        "STEP_ID": context.step_id,
        "SOURCE_FILE": context.source_file or "",
        "TARGET_FILE": context.target_file or "",
        "SOURCE_CONTENT": context.source_content,
        "TARGET_SCHEMA": context.target_schema,
        "SCHEMA_REF": context.schema_ref,
        "REQUIRED_FIELDS": context.required_fields,
        "CONTEXT_SOURCES": context.context_sources,
        "FIELD_PATH": context.field_path,
        "FIELD_TYPE": context.field_type,
        "FIELD_DESCRIPTION": context.field_description,
        "FIELD_CONSTRAINTS": context.field_constraints,
        "OLD_FIELD_PATH": context.old_field_path,
        "NEW_FIELD_PATH": context.new_field_path,
        "OLD_TYPE": context.old_type,
        "NEW_TYPE": context.new_type,
        "TIMESTAMP": context.timestamp or datetime.now().isoformat(),
    }
    # Add any extra context
    ctx.update(context.extra)
    
    # Handle {{#each ARRAY}}...{{/each}} blocks
    each_pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
    
    def replace_each(match):
        array_name = match.group(1)
        block_template = match.group(2)
        if array_name not in ctx:
            warnings.warn(
                f"Template each-block variable '{array_name}' not found in context",
                stacklevel=2,
            )
        array = ctx.get(array_name, [])

        if not array:
            return ""
        
        rendered_blocks = []
        for item in array:
            block = block_template
            if isinstance(item, dict):
                for key, value in item.items():
                    block = block.replace(f"{{{{this.{key}}}}}", str(value))
            else:
                block = block.replace("{{this}}", str(item))
            rendered_blocks.append(block)
        
        return "".join(rendered_blocks)
    
    result = re.sub(each_pattern, replace_each, result, flags=re.DOTALL)
    
    # Handle simple {{VAR}} substitutions
    for key, value in ctx.items():
        if isinstance(value, (list, dict)):
            continue  # Skip complex types for simple substitution
        result = result.replace(f"{{{{{key}}}}}", str(value) if value else "")

    # Warn about any {{VAR}} references that were not resolved
    unresolved_pattern = r'\{\{(\w+)\}\}'
    for var_name in re.findall(unresolved_pattern, result):
        if var_name not in ctx:
            warnings.warn(
                f"Template variable '{var_name}' not found in context",
                stacklevel=2,
            )

    return result


# -----------------------------------------------------------------------------
# Context Gathering
# -----------------------------------------------------------------------------

def gather_step_context(
    diff: MigrationDiff,
    step_diff: StepDiff,
    toolkit_root: Path,
    spec_dir: Path,
    changelog_entry: Optional[ChangelogEntry] = None,
) -> PromptContext:
    """Gather context for a step-level migration.
    
    Args:
        diff: The complete migration diff
        step_diff: The specific step to gather context for
        toolkit_root: Path to devspec_toolkit root
        spec_dir: Path to user's spec/ directory
        changelog_entry: Optional changelog entry with migration hints
        
    Returns:
        PromptContext with all gathered data
    """
    context = PromptContext(
        source_version=diff.source_version,
        target_version=diff.target_version,
        step_id=step_diff.step_id,
        timestamp=datetime.now().isoformat(),
    )
    
    # Load source content if file exists
    if step_diff.source_file and step_diff.source_file.exists():
        try:
            context.source_content = step_diff.source_file.read_text(encoding="utf-8")
            context.source_file = str(step_diff.source_file.name)
        except Exception:
            context.source_content = ""
    
    # For paradigm shifts, check for prose source
    if step_diff.paradigm_shift_from:
        prose_path = spec_dir.parent / step_diff.paradigm_shift_from
        if prose_path.exists():
            try:
                context.source_content = prose_path.read_text(encoding="utf-8")
                context.source_file = step_diff.paradigm_shift_from
            except Exception:
                pass
    
    # Load target schema
    if step_diff.target_file:
        schema_name = f"{step_diff.step_id}.schema.json"
        schema_path = toolkit_root / "schema" / schema_name
        if schema_path.exists():
            try:
                context.target_schema = schema_path.read_text(encoding="utf-8")
                context.schema_ref = f"../devspec_toolkit/schema/{schema_name}"
                
                # Extract required fields
                schema_data = json.loads(context.target_schema)
                context.required_fields = _extract_required_fields(schema_data)
            except Exception:
                pass
        context.target_file = str(step_diff.target_file.name) if step_diff.target_file else f"{step_diff.step_id}.json"
    
    # Load context sources from changelog hints
    if changelog_entry and changelog_entry.migration:
        for source_path in changelog_entry.migration.context_sources:
            full_path = spec_dir / Path(source_path).name if not Path(source_path).is_absolute() else Path(source_path)
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    context.context_sources.append({
                        "filename": full_path.name,
                        "content": content,
                    })
                except Exception:
                    pass
    
    # Populate template-specific variables based on status/type
    status = step_diff.status.upper() if step_diff.status else ""
    
    # For step renames - populate OLD_STEP_ID, NEW_STEP_ID
    if status == "RENAME":
        context.extra["OLD_STEP_ID"] = step_diff.step_id
        if step_diff.target_file:
            context.extra["NEW_STEP_ID"] = step_diff.target_file.stem
        if changelog_entry and changelog_entry.description:
            context.extra["RENAME_REASON"] = changelog_entry.description
    
    # For unknown steps (project extensions) - populate ARCHIVE_PATH
    if status == "UNKNOWN":
        archive_dir = spec_dir / "archive"
        context.extra["ARCHIVE_PATH"] = str(archive_dir / f"{step_diff.step_id}.json")
        context.extra["FILENAME"] = f"{step_diff.step_id}.json"
    
    # For changelog-driven migrations, extract additional context
    if changelog_entry:
        if changelog_entry.description:
            context.extra["CHANGE_REASON"] = changelog_entry.description
        if changelog_entry.from_id:
            context.extra["OLD_STEP_ID"] = changelog_entry.from_id
        if changelog_entry.to_id:
            context.extra["NEW_STEP_ID"] = changelog_entry.to_id
    
    return context


def gather_field_context(
    diff: MigrationDiff,
    step_diff: StepDiff,
    field_diff: FieldDiff,
    toolkit_root: Path,
    spec_dir: Path,
) -> PromptContext:
    """Gather context for a field-level migration.
    
    Args:
        diff: The complete migration diff
        step_diff: The step containing the field
        field_diff: The specific field difference
        toolkit_root: Path to devspec_toolkit root
        spec_dir: Path to user's spec/ directory
        
    Returns:
        PromptContext with field-specific data
    """
    # Start with step context
    context = gather_step_context(diff, step_diff, toolkit_root, spec_dir)
    
    # Add field-specific info
    context.field_path = field_diff.path
    context.field_type = field_diff.expected or ""
    context.field_description = field_diff.suggestion or ""
    
    if field_diff.diff_type == DiffType.RENAME_CANDIDATE:
        context.old_field_path = field_diff.path
        context.new_field_path = field_diff.suggestion or field_diff.path
        context.extra["RENAME_REASON"] = "Field renamed in schema update"
    
    if field_diff.diff_type == DiffType.TYPE_MISMATCH:
        context.old_type = field_diff.actual or ""
        context.new_type = field_diff.expected or ""
        context.extra["CHANGE_REASON"] = f"Type changed from {field_diff.actual} to {field_diff.expected}"
    
    if field_diff.diff_type == DiffType.EXTRA_FIELD:
        context.extra["REMOVAL_REASON"] = "Field deprecated in new schema version"
        context.extra["REPLACEMENT_FIELD"] = field_diff.suggestion or "none"
    
    if field_diff.diff_type == DiffType.SCHEMA_REF_OUTDATED:
        context.extra["CONFLICT_TYPE"] = "Broken trace reference"
        context.extra["CONFLICT_DESCRIPTION"] = f"Reference at {field_diff.path} points to invalid target"
    
    return context


def gather_paradigm_context(
    diff: MigrationDiff,
    paradigm: ParadigmShift,
    toolkit_root: Path,
    spec_dir: Path,
) -> PromptContext:
    """Gather context for a paradigm shift migration.
    
    Args:
        diff: The complete migration diff
        paradigm: The paradigm shift to handle
        toolkit_root: Path to devspec_toolkit root
        spec_dir: Path to user's spec/ directory
        
    Returns:
        PromptContext with paradigm shift data
    """
    context = PromptContext(
        source_version=diff.source_version,
        target_version=diff.target_version,
        source_file=str(paradigm.source_file),
        target_file=str(paradigm.target_file),
        timestamp=datetime.now().isoformat(),
    )
    
    # Derive step_id from target file
    if paradigm.target_file:
        context.step_id = paradigm.target_file.stem
    
    # Load source content
    source_path = spec_dir.parent / paradigm.source_file if not paradigm.source_file.is_absolute() else paradigm.source_file
    if source_path.exists():
        try:
            context.source_content = source_path.read_text(encoding="utf-8")
        except Exception:
            pass
    
    # Load target schema
    if context.step_id:
        schema_name = f"{context.step_id}.schema.json"
        schema_path = toolkit_root / "schema" / schema_name
        if schema_path.exists():
            try:
                context.target_schema = schema_path.read_text(encoding="utf-8")
                try:
                    rel_path = os.path.relpath(schema_path, spec_dir)
                    context.schema_ref = str(rel_path)
                except ValueError:
                    context.schema_ref = f"../devspec_toolkit/schema/{schema_name}"
                
                schema_data = json.loads(context.target_schema)
                context.required_fields = _extract_required_fields(schema_data)
            except Exception:
                pass
    
    return context


def _extract_required_fields(schema: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
    """Extract required field information from a JSON schema.
    
    Args:
        schema: JSON schema dict
        prefix: Path prefix for nested fields
        
    Returns:
        List of dicts with path, type, description, constraints
    """
    fields = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required
        if not is_required:
            continue
        
        path = f"{prefix}{prop_name}" if prefix else prop_name
        field_info = {
            "path": path,
            "type": prop_schema.get("type", "any"),
            "description": prop_schema.get("description", ""),
            "constraints": "",
            "extraction_hint": "",
            "default": "",
        }
        
        # Build constraints string
        constraints = []
        if "minLength" in prop_schema:
            constraints.append(f"minLength: {prop_schema['minLength']}")
        if "maxLength" in prop_schema:
            constraints.append(f"maxLength: {prop_schema['maxLength']}")
        if "pattern" in prop_schema:
            constraints.append(f"pattern: {prop_schema['pattern']}")
        if "enum" in prop_schema:
            constraints.append(f"enum: {prop_schema['enum']}")
        if "minimum" in prop_schema:
            constraints.append(f"minimum: {prop_schema['minimum']}")
        if "maximum" in prop_schema:
            constraints.append(f"maximum: {prop_schema['maximum']}")
        
        field_info["constraints"] = ", ".join(constraints) if constraints else "None"
        
        # Extract default value if present
        if "default" in prop_schema:
            field_info["default"] = str(prop_schema["default"])
        
        # Generate extraction hints based on field semantics
        field_lower = prop_name.lower()
        if "id" in field_lower:
            field_info["extraction_hint"] = "Use kebab-case identifier derived from name or title"
        elif "trace" in field_lower or "ref" in field_lower:
            field_info["extraction_hint"] = "Reference existing IDs from related specs"
        elif "date" in field_lower or "time" in field_lower or "created" in field_lower:
            field_info["extraction_hint"] = "Use ISO 8601 format (YYYY-MM-DD or full timestamp)"
        elif "description" in field_lower or "notes" in field_lower:
            field_info["extraction_hint"] = "Extract from document prose or summarize purpose"
        elif prop_schema.get("type") == "array":
            field_info["extraction_hint"] = "Collect items from bullet lists or enumerated sections"
        
        fields.append(field_info)
        
        # Recurse into nested objects
        if prop_schema.get("type") == "object":
            nested = _extract_required_fields(prop_schema, prefix=f"{path}.")
            fields.extend(nested)
    
    return fields


# -----------------------------------------------------------------------------
# Template Selection
# -----------------------------------------------------------------------------

_STEP_TO_TEMPLATE: dict[str, str] = {
    "00": "template_charter.md",
    "01": "template_capabilities.md",
    "02": "template_system_sketch.md",
    "02a": "template_delivery_baseline.md",
    "03": "template_glossary.md",
    "04": "template_frs.md",
    "05": "template_interfaces.md",
    "06": "template_invariants.md",
    "07": "template_nfrs.md",
    "08": "template_fixtures.md",
    "09": "template_impl_plan.md",
    "10": "template_governance.md",
    "14": "template_roadmap.md",
    "16": "template_impl_context.md",
}


def _step_prefix(step_id: str) -> str:
    """Extract the pipeline step number prefix (e.g. '04' from '04_frs')."""
    m = re.match(r"^(\d{2}[a-z]?)", step_id)
    return m.group(1) if m else step_id


def select_template(
    step_diff: Optional[StepDiff] = None,
    field_diff: Optional[FieldDiff] = None,
    paradigm: Optional[ParadigmShift] = None,
    changelog_entry: Optional[ChangelogEntry] = None,
) -> str:
    """Select appropriate step-based template.

    Priority:
    1. ChangelogEntry.migration.prompt (if specified)
    2. Step-based template lookup from step_diff or paradigm target
    3. Fallback to template_charter.md (step 00) as generic base

    Args:
        step_diff: Optional step-level diff
        field_diff: Optional field-level diff
        paradigm: Optional paradigm shift
        changelog_entry: Optional changelog hint

    Returns:
        Template filename from prompts/migration/
    """
    # Priority 1: Changelog explicit template
    if changelog_entry and changelog_entry.migration and changelog_entry.migration.prompt:
        return changelog_entry.migration.prompt

    # Priority 2: Resolve step_id from available context
    step_id: Optional[str] = None
    if step_diff:
        step_id = step_diff.step_id
    elif paradigm and paradigm.target_file:
        step_id = paradigm.target_file.stem

    if step_id:
        prefix = _step_prefix(step_id)
        template = _STEP_TO_TEMPLATE.get(prefix)
        if template:
            return template

    # Fallback: use charter template as generic base
    return "template_charter.md"


# -----------------------------------------------------------------------------
# Prompt Generation
# -----------------------------------------------------------------------------

def generate_prompts(
    diff: MigrationDiff,
    toolkit_root: Path,
    spec_dir: Path,
    mode: str = "upgrade",
    changelog_dir: Optional[Path] = None,
) -> List[GeneratedPrompt]:
    """Generate all prompts based on migration diff.
    
    Args:
        diff: MigrationDiff with identified changes
        toolkit_root: Path to devspec_toolkit root
        spec_dir: Path to user's spec/ directory
        mode: "upgrade" for version migration, "bootstrap" for new project
        changelog_dir: Optional path to changelog/ (defaults to toolkit_root/changelog)
        
    Returns:
        List of GeneratedPrompt objects, ordered by priority
    """
    prompts: List[GeneratedPrompt] = []
    prompt_index = 0
    
    if changelog_dir is None:
        changelog_dir = toolkit_root / "changelog"
    
    # Load changelog for template hints
    changelog: Optional[VersionChangelog] = None
    if diff.target_version and changelog_dir.exists():
        try:
            changelog = load_version(changelog_dir, diff.target_version)
        except Exception:
            pass
    
    # Collect changelog entries by type for lookup
    changelog_by_step: Dict[str, ChangelogEntry] = {}
    if changelog:
        for change in changelog.changes:
            if change.step_id:
                changelog_by_step[change.step_id] = change
    
    # Dynamic step ordering based on ID (alphanumeric sort)
    def step_priority(step_diff: StepDiff) -> str:
        return step_diff.step_id
    
    # Generate prompts for paradigm shifts first
    for paradigm in diff.paradigm_shifts:
        if not paradigm.detected:
            continue
        
        prompt_index += 1
        template_name = select_template(paradigm=paradigm)
        
        try:
            template = load_template(toolkit_root, template_name)
            context = gather_paradigm_context(diff, paradigm, toolkit_root, spec_dir)
            content = render_template(template, context)
            
            prompts.append(GeneratedPrompt(
                filename=f"{prompt_index:02d}_paradigm_{Path(paradigm.target_file).stem}.md",
                template_name=template_name,
                step_id=context.step_id,
                content=content,
                priority=prompt_index,
            ))
        except Exception as e:
            # Create error prompt
            prompts.append(GeneratedPrompt(
                filename=f"{prompt_index:02d}_paradigm_{Path(paradigm.target_file).stem}_ERROR.md",
                template_name=template_name,
                content=f"# Error generating prompt\n\nTemplate: {template_name}\nError: {e}",
                priority=prompt_index,
            ))
    
    # Generate prompts for step-level changes
    sorted_steps = sorted(diff.steps, key=step_priority)
    
    for step_diff in sorted_steps:
        # Normalize status to uppercase for comparison
        status = step_diff.status.upper() if step_diff.status else ""
        
        # Skip auto-fixable steps in upgrade mode
        if mode == "upgrade" and step_diff.action == MigrationAction.AUTO:
            continue
        
        # Skip OK steps
        if status == "OK":
            continue
        
        # For bootstrap mode, generate for all missing steps
        if mode == "bootstrap" and status != "MISSING":
            continue
        
        prompt_index += 1
        changelog_entry = changelog_by_step.get(step_diff.step_id)
        template_name = select_template(step_diff=step_diff, changelog_entry=changelog_entry)
        
        try:
            template = load_template(toolkit_root, template_name)
            context = gather_step_context(diff, step_diff, toolkit_root, spec_dir, changelog_entry)
            content = render_template(template, context)
            
            prompts.append(GeneratedPrompt(
                filename=f"{prompt_index:02d}_{step_diff.status.lower()}_{step_diff.step_id}.md",
                template_name=template_name,
                step_id=step_diff.step_id,
                content=content,
                priority=prompt_index,
            ))
        except Exception as e:
            prompts.append(GeneratedPrompt(
                filename=f"{prompt_index:02d}_{step_diff.step_id}_ERROR.md",
                template_name=template_name,
                step_id=step_diff.step_id,
                content=f"# Error generating prompt\n\nStep: {step_diff.step_id}\nTemplate: {template_name}\nError: {e}",
                priority=prompt_index,
            ))
        
        # Generate field-level prompts if not auto-fixable
        for field_diff in step_diff.field_diffs:
            if field_diff.auto_fixable:
                continue
            if field_diff.action == MigrationAction.AUTO:
                continue
            
            prompt_index += 1
            field_template = select_template(field_diff=field_diff)
            
            try:
                template = load_template(toolkit_root, field_template)
                context = gather_field_context(diff, step_diff, field_diff, toolkit_root, spec_dir)
                content = render_template(template, context)
                
                # Sanitize field path for filename
                safe_field = field_diff.path.replace(".", "_").replace("[", "_").replace("]", "")
                
                prompts.append(GeneratedPrompt(
                    filename=f"{prompt_index:02d}_field_{step_diff.step_id}_{safe_field}.md",
                    template_name=field_template,
                    step_id=step_diff.step_id,
                    field_path=field_diff.path,
                    content=content,
                    priority=prompt_index,
                ))
            except Exception as e:
                prompts.append(GeneratedPrompt(
                    filename=f"{prompt_index:02d}_field_{step_diff.step_id}_ERROR.md",
                    template_name=field_template,
                    step_id=step_diff.step_id,
                    field_path=field_diff.path,
                    content=f"# Error generating prompt\n\nField: {field_diff.path}\nError: {e}",
                    priority=prompt_index,
                ))
    
    return prompts


# -----------------------------------------------------------------------------
# Output Functions
# -----------------------------------------------------------------------------

def write_prompts(prompts: List[GeneratedPrompt], output_dir: Path) -> None:
    """Write generated prompts to files.
    
    Args:
        prompts: List of GeneratedPrompt objects
        output_dir: Directory to write prompts to
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for prompt in prompts:
        output_path = output_dir / prompt.filename
        output_path.write_text(prompt.content, encoding="utf-8")


def format_prompts_report(prompts: List[GeneratedPrompt]) -> str:
    """Format prompts summary for CLI output.
    
    Args:
        prompts: List of generated prompts
        
    Returns:
        Formatted report string
    """
    if not prompts:
        return "✅ No AI-assisted prompts needed. All changes are mechanical."
    
    lines = [
        "",
        "📝 Generated AI Prompts",
        "━" * 40,
        "",
    ]
    
    for prompt in prompts:
        icon = "📄"
        if "paradigm" in prompt.filename:
            icon = "🔄"
        elif "field" in prompt.filename:
            icon = "📋"
        elif "ERROR" in prompt.filename:
            icon = "❌"
        
        step_info = f" ({prompt.step_id})" if prompt.step_id else ""
        field_info = f" → {prompt.field_path}" if prompt.field_path else ""
        
        lines.append(f"  {icon} {prompt.filename}{step_info}{field_info}")
        lines.append(f"      Template: {prompt.template_name}")
    
    lines.extend([
        "",
        f"Total: {len(prompts)} prompt(s) generated",
        "",
        "Instructions:",
        "  1. Review each prompt file",
        "  2. Copy content to your AI assistant",
        "  3. Paste AI output into the appropriate spec file",
        "  4. Run `specdev align validate` to confirm success",
    ])
    
    return "\n".join(lines)
