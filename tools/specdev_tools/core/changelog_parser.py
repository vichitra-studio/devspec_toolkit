"""Changelog parser for DevSpec Toolkit migration system.

Parses and validates YAML changelog files for version tracking and migration.
See: docs/developers/workflows/migration_system_spec.md
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------

@dataclass
class MigrationInfo:
    """Migration action specification for a change."""
    action: str  # "auto", "ai_assisted", "merge", "archive"
    prompt: Optional[str] = None
    operations: List[str] = field(default_factory=list)
    source: Optional[str] = None
    target: Optional[str] = None
    context_sources: List[str] = field(default_factory=list)


@dataclass
class ChangelogEntry:
    """Represents a single change entry in a version changelog."""
    type: str  # add_step, rename_step, add_field, etc.
    description: Optional[str] = None
    step_id: Optional[str] = None
    path: Optional[str] = None  # For field changes: "milestones[].user_story"
    from_id: Optional[str] = None  # For renames
    to_id: Optional[str] = None
    required: bool = False
    migration: Optional[MigrationInfo] = None
    detection: Optional[Dict[str, str]] = None


@dataclass
class StepInfo:
    """Represents a step in a version's step list."""
    id: str
    schema: str


@dataclass
class VersionChangelog:
    """Represents a full version changelog."""
    version: str
    release_date: str
    breaking: bool
    description: Optional[str] = None
    changes: List[ChangelogEntry] = field(default_factory=list)
    steps: List[StepInfo] = field(default_factory=list)


@dataclass
class ChangelogFormat:
    """Represents the changelog format schema (format.yaml)."""
    format_version: str
    required_fields: List[str]
    optional_fields: List[str]
    change_types: List[str]
    migration_actions: List[str]


# -----------------------------------------------------------------------------
# Core Functions
# -----------------------------------------------------------------------------

def load_format(changelog_dir: Path) -> ChangelogFormat:
    """Load and parse the changelog format schema.
    
    Args:
        changelog_dir: Path to the changelog/ directory
        
    Returns:
        ChangelogFormat with schema definition
        
    Raises:
        FileNotFoundError: If format.yaml doesn't exist
        ValueError: If format.yaml is invalid
    """
    format_path = changelog_dir / "format.yaml"
    if not format_path.exists():
        raise FileNotFoundError(f"Changelog format not found: {format_path}")
    
    with open(format_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty format file: {format_path}")
    
    return ChangelogFormat(
        format_version=data.get("format_version", "1.0"),
        required_fields=data.get("required_fields", []),
        optional_fields=data.get("optional_fields", []),
        change_types=data.get("change_types", []),
        migration_actions=data.get("migration_actions", []),
    )


def load_version(changelog_dir: Path, version: str) -> VersionChangelog:
    """Load a specific version's changelog.
    
    Args:
        changelog_dir: Path to the changelog/ directory
        version: Version string (e.g., "0.1.0")
        
    Returns:
        VersionChangelog with all change details
        
    Raises:
        FileNotFoundError: If version YAML doesn't exist
        ValueError: If YAML is invalid or missing required fields
    """
    yaml_path = changelog_dir / f"v{version}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Changelog not found for version {version}: {yaml_path}")
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty changelog file: {yaml_path}")
    
    # Validate required fields
    for field in ["version", "release_date", "breaking"]:
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in {yaml_path}")
    
    # Parse changes
    changes: List[ChangelogEntry] = []
    for change_data in data.get("changes", []):
        migration = None
        if "migration" in change_data:
            m = change_data["migration"]
            migration = MigrationInfo(
                action=m.get("action", "auto"),
                prompt=m.get("prompt"),
                operations=m.get("operations", []),
                source=m.get("source"),
                target=m.get("target"),
                context_sources=m.get("context_sources", []),
            )
        
        changes.append(ChangelogEntry(
            type=change_data.get("type", "unknown"),
            description=change_data.get("description"),
            step_id=change_data.get("step_id"),
            path=change_data.get("path"),
            from_id=change_data.get("from"),
            to_id=change_data.get("to"),
            required=change_data.get("required", False),
            migration=migration,
            detection=change_data.get("detection"),
        ))
    
    # Parse steps
    steps: List[StepInfo] = []
    for step_data in data.get("steps", []):
        steps.append(StepInfo(
            id=step_data.get("id", ""),
            schema=step_data.get("schema", ""),
        ))
    
    return VersionChangelog(
        version=data["version"],
        release_date=data["release_date"],
        breaking=data["breaking"],
        description=data.get("description"),
        changes=changes,
        steps=steps,
    )


def list_versions(changelog_dir: Path) -> List[str]:
    """List all available version changelogs.
    
    Args:
        changelog_dir: Path to the changelog/ directory
        
    Returns:
        List of version strings, sorted by semantic version (oldest first)
    """
    versions = []
    
    if not changelog_dir.exists():
        return versions
    
    for f in changelog_dir.iterdir():
        if f.is_file() and f.suffix == ".yaml" and f.name.startswith("v"):
            # Extract version from filename (v0.1.0.yaml -> 0.1.0)
            version = f.stem[1:]  # Remove leading 'v'
            if _is_valid_semver(version):
                versions.append(version)
    
    return sorted(versions, key=_parse_semver)


def get_latest_version(changelog_dir: Path) -> Optional[str]:
    """Get the latest version from the changelog directory.
    
    Args:
        changelog_dir: Path to the changelog/ directory
        
    Returns:
        Latest version string, or None if no versions found
    """
    versions = list_versions(changelog_dir)
    return versions[-1] if versions else None


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic version strings.
    
    Args:
        v1: First version string
        v2: Second version string
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    p1 = _parse_semver(v1)
    p2 = _parse_semver(v2)
    
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def get_changes_between(
    changelog_dir: Path,
    from_version: str,
    to_version: str,
) -> List[ChangelogEntry]:
    """Get all changes between two versions (exclusive of from, inclusive of to).
    
    Args:
        changelog_dir: Path to the changelog/ directory
        from_version: Starting version (not included)
        to_version: Ending version (included)
        
    Returns:
        List of all change entries between the versions
    """
    versions = list_versions(changelog_dir)
    all_changes: List[ChangelogEntry] = []
    
    in_range = False
    for version in versions:
        if version == from_version:
            in_range = True
            continue
        
        if in_range:
            changelog = load_version(changelog_dir, version)
            all_changes.extend(changelog.changes)
            
            if version == to_version:
                break
    
    return all_changes


def validate_changelog(changelog_dir: Path, version: str) -> List[str]:
    """Validate a version changelog against the format schema.
    
    Args:
        changelog_dir: Path to the changelog/ directory
        version: Version string to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors: List[str] = []
    
    try:
        fmt = load_format(changelog_dir)
    except (FileNotFoundError, ValueError) as e:
        errors.append(f"Cannot load format: {e}")
        return errors
    
    try:
        changelog = load_version(changelog_dir, version)
    except (FileNotFoundError, ValueError) as e:
        errors.append(f"Cannot load changelog: {e}")
        return errors
    
    # Validate change types
    for i, change in enumerate(changelog.changes):
        if change.type not in fmt.change_types:
            errors.append(
                f"Change {i}: Invalid type '{change.type}'. "
                f"Valid types: {fmt.change_types}"
            )
        
        # Validate migration action if present
        if change.migration and change.migration.action not in fmt.migration_actions:
            errors.append(
                f"Change {i}: Invalid migration action '{change.migration.action}'. "
                f"Valid actions: {fmt.migration_actions}"
            )
    
    return errors


def get_toolkit_version(repo_root: Path) -> Optional[str]:
    """Get the toolkit version from pyproject.toml.
    
    Args:
        repo_root: Root path of the devspec_toolkit
        
    Returns:
        Version string, or None if not found
    """
    pyproject = repo_root / "tools" / "pyproject.toml"
    if not pyproject.exists():
        return None
    
    # Try using tomllib (Python 3.11+) for robust parsing
    try:
        import tomllib
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version")
    except ImportError:
        # Fallback for older Python: Simple line-based parser
        # Only looks for version = "..." inside [project] block
        with open(pyproject, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        in_project_section = False
        for line in lines:
            line = line.strip()
            if line == "[project]":
                in_project_section = True
                continue
            if line.startswith("[") and line != "[project]":
                in_project_section = False
                continue
                
            if in_project_section and line.startswith("version"):
                # Match version = "X.Y.Z"
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    return match.group(1)
    except Exception:
        pass
        
    return None


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _is_valid_semver(version: str) -> bool:
    """Check if string is a valid semantic version."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def _parse_semver(version: str) -> Tuple[int, int, int, str]:
    """Parse semantic version into comparable tuple.
    
    Returns tuple of (major, minor, patch, prerelease).
    Prerelease is empty string for release versions.
    """
    # Handle prerelease suffix
    prerelease = ""
    if "-" in version:
        version, prerelease = version.split("-", 1)
    
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    
    # Prerelease versions sort before release versions
    # Using '~' prefix for prereleases makes them sort before empty string
    if prerelease:
        prerelease = "~" + prerelease
    
    return (major, minor, patch, prerelease)
