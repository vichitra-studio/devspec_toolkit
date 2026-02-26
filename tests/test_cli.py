import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Optional
from unittest.mock import patch
import sys

from specdev_tools import cli


class CliTests(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("specdev_tools.cli.check_venv", return_value=None), \
             patch.object(sys, "argv", ["specdev-tools", *argv]), \
             redirect_stdout(stdout), \
             redirect_stderr(stderr):
            try:
                cli.main()
                code = 0
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
        return code, stdout.getvalue(), stderr.getvalue()

    def _write_schema_registry_with_canon(self, repo_root: Path, extra_map: Optional[dict[str, str]] = None) -> None:
        tools_dir = repo_root / "tools"
        schema_core_dir = repo_root / "schema" / "core"
        tools_dir.mkdir(exist_ok=True)
        schema_core_dir.mkdir(parents=True, exist_ok=True)
        (schema_core_dir / "canon.schema.json").write_text(
            json.dumps(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": "https://specdev.local/schema/core/canon/1",
                    "type": "object",
                    "properties": {
                        "registry_version": {"type": "string"},
                        "entries": {"type": "array", "items": {"type": "object"}},
                        "aliases": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["registry_version", "entries", "aliases"],
                }
            ),
            encoding="utf-8",
        )

        registry_map = {
            "https://specdev.local/schema/core/canon/1": "schema/core/canon.schema.json",
        }
        if extra_map:
            registry_map.update(extra_map)
        (tools_dir / "schema_registry.json").write_text(json.dumps(registry_map), encoding="utf-8")

    def test_help_lists_b3_subcommands(self):
        code, out, _ = self._run_cli(["--help"])
        self.assertEqual(0, code)
        for name in (
            "prompt-sync",
            "canonical-lint",
            "canonical-integrity",
            "canonical-autofix",
            "spec-quality-lint",
            "hallucination-lint",
            "dependency-order-lint",
            "forward-replay-check",
        ):
            self.assertIn(name, out)

    def test_prompt_sync_fails_when_default_spec_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            with patch("specdev_tools.generation.prompt_schema_sync.run_prompt_schema_sync", return_value=[]):
                code, _, err = self._run_cli(["prompt-sync", "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertIn("missing_spec_dir", err)

    def test_prompt_sync_dispatches_when_spec_dir_exists(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            with patch("specdev_tools.generation.prompt_schema_sync.run_prompt_schema_sync", return_value=[]) as run_sync:
                code, out, err = self._run_cli(["prompt-sync", str(spec_dir), "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK", out)
            run_sync.assert_called_once_with(os.path.abspath(str(repo_root)))

    def test_prompt_sync_rejects_non_repo_spec_dir(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "spec").mkdir()
            other_dir = repo_root / "other"
            other_dir.mkdir()
            with patch("specdev_tools.generation.prompt_schema_sync.run_prompt_schema_sync", return_value=[]):
                code, _, err = self._run_cli(["prompt-sync", str(other_dir), "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertIn("prompt_sync_spec_dir_must_equal_repo_spec", err)

    def test_prompt_sync_uses_repo_root_spec_when_spec_dir_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "spec").mkdir()
            with patch("specdev_tools.generation.prompt_schema_sync.run_prompt_schema_sync", return_value=[]) as run_sync:
                code, out, err = self._run_cli(["prompt-sync", "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK", out)
            run_sync.assert_called_once_with(os.path.abspath(str(repo_root)))

    def test_prompt_sync_reports_malformed_registry_map_shape(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "spec").mkdir()
            (repo_root / "tools").mkdir()
            (repo_root / "schema").mkdir()
            (repo_root / "prompts").mkdir()
            (repo_root / "tools" / "schema_registry.json").write_text("[]", encoding="utf-8")
            (repo_root / "schema" / "00_charter.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                        "required": ["id"],
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / "prompts" / "prompt_00_project_charter.md").write_text(
                (
                    "## Embedded Schema\n"
                    "```json\n"
                    "{\"type\":\"object\",\"properties\":{\"id\":{\"type\":\"string\"}},\"required\":[\"id\"]}\n"
                    "```\n\n"
                    "# Output Contract\n"
                    "```json\n"
                    "{\"id\":\"charter\"}\n"
                    "```\n\n"
                    "## B4 Metadata Contract\n"
                ),
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["prompt-sync", "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("E520 UNRESOLVED_INPUT", err)
            self.assertIn("schema_registry_bootstrap_failed", err)

    def test_canonical_autofix_rejects_conflicting_flags(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            code, _, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write", "--dry-run"]
            )
            self.assertEqual(2, code)
            self.assertIn("not allowed with argument", err)

    def test_validate_does_not_fail_on_warning_only_output(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            sample = repo_root / "sample.json"
            sample.write_text("{}", encoding="utf-8")
            with patch("specdev_tools.validation.validate.validate_file", return_value=["W130 CANONICAL_REF_VERSION_OMITTED cn:core:unit:ms"]):
                code, out, err = self._run_cli(["validate", str(sample), "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (warnings)", out)
            self.assertIn("W130", err)

    def test_validate_fails_when_error_is_present_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            sample = repo_root / "sample.json"
            sample.write_text("{}", encoding="utf-8")
            with patch(
                "specdev_tools.validation.validate.validate_file",
                return_value=[
                    "W130 CANONICAL_REF_VERSION_OMITTED cn:core:unit:ms",
                    "E110 UNKNOWN_CANONICAL_ID cn:core:status:unknown",
                ],
            ):
                code, _, err = self._run_cli(["validate", str(sample), "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertIn("E110", err)

    def test_validate_all_does_not_fail_on_warning_only_output(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            with patch("specdev_tools.validation.validate.validate_dir", return_value=["W130 CANONICAL_REF_VERSION_OMITTED cn:core:unit:ms"]):
                code, out, err = self._run_cli(["validate-all", str(spec_dir), "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (warnings)", out)
            self.assertIn("W130", err)

    def test_canonical_integrity_does_not_fail_on_warning_only_output(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            with patch(
                "specdev_tools.canonical.integrity.validate_canonical_integrity",
                return_value=["W130 CANONICAL_REF_VERSION_OMITTED cn:core:unit:ms"],
            ):
                code, out, err = self._run_cli(["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)])
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (warnings)", out)
            self.assertIn("W130", err)

    def test_canonical_integrity_fails_when_spec_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            missing = repo_root / "missing-spec"
            code, out, err = self._run_cli(["canonical-integrity", str(missing), "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing_spec_dir", err)

    def test_canonical_autofix_fails_when_spec_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            missing = repo_root / "missing-spec"
            code, out, err = self._run_cli(["canonical-autofix", str(missing), "--repo-root", str(repo_root), "--dry-run"])
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing_spec_dir", err)

    def test_canonical_autofix_fails_when_spec_dir_is_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            not_dir = repo_root / "not-a-dir.json"
            not_dir.write_text("{}", encoding="utf-8")
            code, out, err = self._run_cli(["canonical-autofix", str(not_dir), "--repo-root", str(repo_root), "--dry-run"])
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing_spec_dir", err)

    def test_canonical_autofix_infers_refs_and_skips_unknown_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "canonical_refs_used": {"type": "array"},
                            "threats": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "category": {"type": "string"},
                                        "risk_category_ref": {"type": "object"},
                                    },
                                },
                            },
                            "interface": {"type": "string"},
                            "interface_ref": {"type": "object"},
                            "event": {"type": "string"},
                            "event_ref": {"type": "object"},
                            "commit_message_rules": {
                                "type": "object",
                                "additionalProperties": True,
                                "properties": {
                                    "pattern": {"type": "string"},
                                    "id_pattern_ref": {"type": "object"},
                                },
                            },
                            "extensions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "area_of_concern": {"type": "string"},
                                        "governance_label_ref": {"type": "object"},
                                    },
                                },
                            },
                            "tech_stack": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "name": {"type": "string"},
                                        "tech_stack_ref": {"type": "object"},
                                    },
                                },
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "type": {"type": "string"},
                                        "id": {"type": "string"},
                                        "dependency_ref": {"type": "object"},
                                    },
                                },
                            },
                            "terms": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "term": {"type": "string"},
                                        "term_ref": {"type": "object"},
                                    },
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:stage:prod",
                                "kind": "stage",
                                "preferred_label": "prod",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:status:active",
                                "kind": "status",
                                "preferred_label": "active",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:role:reviewer",
                                "kind": "role",
                                "preferred_label": "reviewer",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:policy:spec-first",
                                "kind": "policy",
                                "preferred_label": "spec_first",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:action:authenticate",
                                "kind": "action",
                                "preferred_label": "authenticate",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "JWT",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:risk_category:authz",
                                "kind": "risk_category",
                                "preferred_label": "authz",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:interface:http-json",
                                "kind": "interface",
                                "preferred_label": "http_json",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:event:login-succeeded",
                                "kind": "event",
                                "preferred_label": "login_succeeded",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:id_pattern:conventional-commit",
                                "kind": "id_pattern",
                                "preferred_label": "conventional-commit",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:governance_label:security",
                                "kind": "governance_label",
                                "preferred_label": "security",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:tech_stack:python",
                                "kind": "tech_stack",
                                "preferred_label": "python",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:dependency:auth-service",
                                "kind": "dependency",
                                "preferred_label": "auth-service",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )

            artifact = spec_dir / "artifact.json"
            artifact.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test.schema.json",
                        "stage": "prod",
                        "status": "active",
                        "role": "reviewer",
                        "policy": "spec-first",
                        "action": "authenticate",
                        "term": "JWT",
                        "interface": "http_json",
                        "event": "login_succeeded",
                        "commit_message_rules": {"pattern": "conventional-commit"},
                        "extensions": [
                            {"area_of_concern": "security"},
                            {"area_of_concern": "unknown-area"},
                        ],
                        "tech_stack": [
                            {"name": "python"},
                            {"name": "unknown-tech"},
                        ],
                        "dependencies": [
                            {"type": "external", "id": "auth-service"},
                            {"type": "external", "id": "unknown-dependency"},
                        ],
                        "terms": [
                            {"term": "JWT"},
                            {"term": "unknown-term"},
                        ],
                        "canonical_refs_used": [],
                        "items": [{"action": "unknown-action"}],
                        "threats": [{"category": "authz"}, {"category": "unknown-category"}],
                    }
                ),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (changes written)", out)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(
                {"id": "cn:core:stage:prod", "kind": "stage"},
                payload.get("stage_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:status:active", "kind": "status"},
                payload.get("status_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:role:reviewer", "kind": "role"},
                payload.get("role_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:policy:spec-first", "kind": "policy"},
                payload.get("policy_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:action:authenticate", "kind": "action"},
                payload.get("action_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:term:jwt", "kind": "term"},
                payload.get("term_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:term:jwt", "kind": "term"},
                payload["terms"][0].get("term_ref"),
            )
            self.assertNotIn("term_ref", payload["terms"][1])
            self.assertEqual(
                {"id": "cn:core:interface:http-json", "kind": "interface"},
                payload.get("interface_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:event:login-succeeded", "kind": "event"},
                payload.get("event_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:id_pattern:conventional-commit", "kind": "id_pattern"},
                payload["commit_message_rules"].get("id_pattern_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:governance_label:security", "kind": "governance_label"},
                payload["extensions"][0].get("governance_label_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:tech_stack:python", "kind": "tech_stack"},
                payload["tech_stack"][0].get("tech_stack_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:dependency:auth-service", "kind": "dependency"},
                payload["dependencies"][0].get("dependency_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:risk_category:authz", "kind": "risk_category"},
                payload["threats"][0].get("risk_category_ref"),
            )
            self.assertNotIn("action_ref", payload["items"][0])
            self.assertNotIn("governance_label_ref", payload["extensions"][1])
            self.assertNotIn("tech_stack_ref", payload["tech_stack"][1])
            self.assertNotIn("dependency_ref", payload["dependencies"][1])
            self.assertNotIn("risk_category_ref", payload["threats"][1])

    def test_canonical_autofix_infers_term_and_risk_category_with_negative_cases(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "canonical_refs_used": {"type": "array"},
                            "terms": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "term": {"type": "string"},
                                        "term_ref": {"type": "object"},
                                    },
                                },
                            },
                            "threats": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "category": {"type": "string"},
                                        "risk_category_ref": {"type": "object"},
                                    },
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "JWT",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:risk_category:authz",
                                "kind": "risk_category",
                                "preferred_label": "authz",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )

            artifact = spec_dir / "artifact.json"
            artifact.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test.schema.json",
                        "terms": [
                            {"term": "JWT"},
                            {"term": "unknown-term"},
                        ],
                        "threats": [
                            {"category": "authz"},
                            {"category": "unknown-category"},
                        ],
                        "canonical_refs_used": [],
                    }
                ),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (changes written)", out)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(
                {"id": "cn:core:term:jwt", "kind": "term"},
                payload["terms"][0].get("term_ref"),
            )
            self.assertNotIn("term_ref", payload["terms"][1])
            self.assertEqual(
                {"id": "cn:core:risk_category:authz", "kind": "risk_category"},
                payload["threats"][0].get("risk_category_ref"),
            )
            self.assertNotIn("risk_category_ref", payload["threats"][1])

    def test_canonical_autofix_prefers_environment_field_over_stage_for_environment_ref(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "stage": {"type": "string"},
                            "environment": {"type": "string"},
                            "stage_ref": {"type": "object"},
                            "environment_ref": {"type": "object"},
                            "canonical_refs_used": {"type": "array"},
                        },
                        "required": ["stage", "environment", "canonical_refs_used"],
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:stage:ci",
                                "kind": "stage",
                                "preferred_label": "ci",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:environment:ci",
                                "kind": "environment",
                                "preferred_label": "ci",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:environment:prod",
                                "kind": "environment",
                                "preferred_label": "prod",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            artifact = spec_dir / "artifact.json"
            artifact.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test.schema.json",
                        "stage": "ci",
                        "environment": "prod",
                        "canonical_refs_used": [],
                    }
                ),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (changes written)", out)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(
                {"id": "cn:core:stage:ci", "kind": "stage"},
                payload.get("stage_ref"),
            )
            self.assertEqual(
                {"id": "cn:core:environment:prod", "kind": "environment"},
                payload.get("environment_ref"),
            )

    def test_canonical_autofix_does_not_infer_dependency_ref_from_top_level_id(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "dependency_ref": {"type": "object"},
                            "canonical_refs_used": {"type": "array"},
                        },
                        "required": ["id", "canonical_refs_used"],
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:dependency:artifact-id",
                                "kind": "dependency",
                                "preferred_label": "artifact-id",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            artifact = spec_dir / "artifact.json"
            artifact.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test.schema.json",
                        "id": "artifact-id",
                        "canonical_refs_used": [],
                    }
                ),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK", out)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertNotIn("dependency_ref", payload)

    def test_canonical_autofix_infers_acronym_and_completeness_dimension_refs(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "canonical_refs_used": {"type": "array"},
                            "terms": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "acronym": {"type": "string"},
                                        "acronym_ref": {"type": "object"},
                                    },
                                },
                            },
                            "missing_elements": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "properties": {
                                        "category": {"type": "string"},
                                        "completeness_dimension_ref": {"type": "object"},
                                    },
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:acronym:jwt",
                                "kind": "acronym",
                                "preferred_label": "JWT",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                            {
                                "id": "cn:core:completeness_dimension:traceability",
                                "kind": "completeness_dimension",
                                "preferred_label": "traceability",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            },
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            artifact = spec_dir / "artifact.json"
            artifact.write_text(
                json.dumps(
                    {
                        "$schema": "https://specdev.local/schema/test.schema.json",
                        "terms": [{"acronym": "JWT"}, {"acronym": "XYZ"}],
                        "missing_elements": [
                            {"category": "traceability"},
                            {"category": "unknown-dimension"},
                        ],
                        "canonical_refs_used": [],
                    }
                ),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(0, code, msg=err)
            self.assertIn("OK (changes written)", out)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(
                {"id": "cn:core:acronym:jwt", "kind": "acronym"},
                payload["terms"][0].get("acronym_ref"),
            )
            self.assertNotIn("acronym_ref", payload["terms"][1])
            self.assertEqual(
                {"id": "cn:core:completeness_dimension:traceability", "kind": "completeness_dimension"},
                payload["missing_elements"][0].get("completeness_dimension_ref"),
            )
            self.assertNotIn("completeness_dimension_ref", payload["missing_elements"][1])

    def test_canonical_autofix_reports_invalid_json_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            self._write_schema_registry_with_canon(repo_root, {})
            (canon_dir / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (spec_dir / "bad.json").write_text("{bad", encoding="utf-8")

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("E520 UNRESOLVED_INPUT", err)
            self.assertIn("invalid_json", err)

    def test_canonical_autofix_write_is_atomic_when_any_error_exists(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            self._write_schema_registry_with_canon(
                repo_root,
                {"https://specdev.local/schema/test.schema.json": "schema/test.schema.json"},
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "$schema": {"type": "string"},
                            "stage": {"type": "string"},
                            "stage_ref": {"type": "object"},
                            "canonical_refs_used": {"type": "array"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:stage:prod",
                                "kind": "stage",
                                "preferred_label": "prod",
                                "version": "1.0.0",
                                "status": "active",
                                "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
                            }
                        ],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            bad_file = spec_dir / "a_bad.json"
            bad_file.write_text("{bad", encoding="utf-8")
            good_file = spec_dir / "b_good.json"
            original_good = {
                "$schema": "https://specdev.local/schema/test.schema.json",
                "stage": "prod",
                "canonical_refs_used": [],
            }
            good_file.write_text(json.dumps(original_good, indent=2), encoding="utf-8")

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--write"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("invalid_json", err)
            self.assertIn("write_aborted_due_to_errors", err)
            self.assertEqual(json.loads(good_file.read_text(encoding="utf-8")), original_good)

    def test_canonical_autofix_handles_malformed_registry_map_shape(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            (tools_dir / "schema_registry.json").write_text("[]", encoding="utf-8")
            (canon_dir / "manifest.json").write_text(
                json.dumps({"registry_version": "1.0.0", "entries": [], "aliases": []}),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({"$schema": "https://specdev.local/schema/test.schema.json", "canonical_refs_used": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("E520 UNRESOLVED_INPUT", err)
            self.assertIn("schema_registry_bootstrap_failed", err)

    def test_canonical_autofix_fails_when_canon_registry_load_has_errors(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            (tools_dir / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/test.schema.json": "schema/test.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "$schema": {"type": "string"},
                            "term": {"type": "string"},
                            "canonical_refs_used": {"type": "array"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            # Malformed modular registry artifact should fail autofix preflight.
            (canon_dir / "aliases.json").write_text("{bad", encoding="utf-8")
            (spec_dir / "artifact.json").write_text(
                json.dumps({"$schema": "https://specdev.local/schema/test.schema.json", "term": "jwt", "canonical_refs_used": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("invalid_aliases", err)

    def test_canonical_autofix_fails_when_kind_file_shape_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            tools_dir = repo_root / "tools"
            schema_dir = repo_root / "schema"
            spec_dir.mkdir()
            canon_dir.mkdir()
            tools_dir.mkdir()
            schema_dir.mkdir()
            (canon_dir / "kinds").mkdir()
            (tools_dir / "schema_registry.json").write_text(
                json.dumps(
                    {
                        "https://specdev.local/schema/test.schema.json": "schema/test.schema.json",
                    }
                ),
                encoding="utf-8",
            )
            (schema_dir / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://specdev.local/schema/test.schema.json",
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "$schema": {"type": "string"},
                            "term": {"type": "string"},
                            "canonical_refs_used": {"type": "array"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (canon_dir / "kinds" / "term.json").write_text(
                json.dumps(
                    {
                        "kind": "term",
                        "registry_version": "1.0.0",
                        "entries": {"id": "cn:core:term:jwt", "preferred_label": "jwt"},
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({"$schema": "https://specdev.local/schema/test.schema.json", "term": "jwt", "canonical_refs_used": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("invalid_kind_file", err)
            self.assertIn("entries must be an array", err)

    def test_canonical_integrity_fails_when_alias_missing_required_target_id(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            spec_dir.mkdir()
            canon_dir.mkdir()
            (canon_dir / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [{"kind": "term", "normalized": "jwt"}],
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({"canonical_refs_used": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)])
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("manifest.aliases[0] missing target_id", err)

    def test_canonical_autofix_fails_when_alias_missing_required_target_id(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            spec_dir.mkdir()
            canon_dir.mkdir()
            (canon_dir / "aliases.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "aliases": [{"kind": "term", "normalized": "jwt"}],
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({"canonical_refs_used": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("manifest.aliases[0] missing target_id", err)

    def test_canonical_autofix_fails_when_entry_lifecycle_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            spec_dir.mkdir()
            canon_dir.mkdir()
            (canon_dir / "kinds").mkdir()
            (canon_dir / "kinds" / "term.json").write_text(
                json.dumps(
                    {
                        "kind": "term",
                        "registry_version": "1.0.0",
                        "entries": [
                            {
                                "id": "cn:core:term:jwt",
                                "kind": "term",
                                "preferred_label": "jwt",
                                "definition": "token",
                                "version": "1.0.0",
                                "status": "active",
                                "owners": ["team"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({"canonical_refs_used": [], "canonical_proposals": [], "canonical_conflicts": []}),
                encoding="utf-8",
            )

            code, out, err = self._run_cli(
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing introduced_at", err)

    def test_new_b3_command_dispatch_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            canon_dir = repo_root / "canon"
            spec_dir.mkdir()
            canon_dir.mkdir()

            with patch("specdev_tools.canonical.lint.lint_canon_dir", return_value=[]) as p_canon_lint:
                code, out, err = self._run_cli(["canonical-lint", str(canon_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_canon_lint.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    canon_dir=os.path.abspath(str(canon_dir)),
                    require_manifest_schema_registration=True,
                )

            with patch("specdev_tools.canonical.integrity.validate_canonical_integrity", return_value=[]) as p_integrity:
                code, out, err = self._run_cli(["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_integrity.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    os.path.abspath(str(spec_dir)),
                    canon_dir="canon",
                    require_manifest_schema_registration=True,
                )

            with patch("specdev_tools.canonical.autofix.canonical_autofix", return_value={}) as p_autofix:
                code, out, err = self._run_cli(["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK (no changes)", out)
                p_autofix.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    os.path.abspath(str(spec_dir)),
                    write=False,
                    canon_dir="canon",
                    require_manifest_schema_registration=True,
                )

            with patch("specdev_tools.validation.spec_quality_lint.lint_spec_quality", return_value=[]) as p_quality:
                code, out, err = self._run_cli(["spec-quality-lint", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_quality.assert_called_once_with(os.path.abspath(str(spec_dir)))

            with patch("specdev_tools.validation.hallucination_lint.lint_hallucinations", return_value=[]) as p_hall:
                code, out, err = self._run_cli(["hallucination-lint", str(spec_dir), "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_hall.assert_called_once_with(
                    os.path.abspath(str(spec_dir)),
                    repo_root=os.path.abspath(str(repo_root)),
                    canon_dir="canon",
                    require_canon_dir=True,
                    require_manifest_schema_registration=True,
                )

            with patch("specdev_tools.validation.dependency_order_lint.lint_dependency_order", return_value=[]) as p_dep:
                code, out, err = self._run_cli(["dependency-order-lint", "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_dep.assert_called_once_with(os.path.abspath(str(repo_root)))

            with patch("specdev_tools.validation.validate._resolve_replay_base_ref", return_value="feature/x") as p_base, \
                 patch("specdev_tools.validation.forward_replay_check.check_forward_replay", return_value=[]) as p_replay:
                code, out, err = self._run_cli(["forward-replay-check", "--repo-root", str(repo_root)])
                self.assertEqual(0, code, msg=err)
                self.assertIn("OK", out)
                p_base.assert_called_once_with(os.path.abspath(str(repo_root)))
                p_replay.assert_called_once_with(
                    os.path.abspath(str(repo_root)),
                    base_ref="feature/x",
                    diff_error_mode="error",
                )

    def test_hallucination_lint_fails_when_canon_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            (spec_dir / "artifact.json").write_text(json.dumps({"id": "a1"}), encoding="utf-8")

            code, out, err = self._run_cli(
                [
                    "hallucination-lint",
                    str(spec_dir),
                    "--repo-root",
                    str(repo_root),
                    "--canon-dir",
                    "does_not_exist",
                ]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing_canon_dir", err)

    def test_hallucination_lint_fails_when_spec_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            missing_spec = repo_root / "does-not-exist"

            code, out, err = self._run_cli(
                [
                    "hallucination-lint",
                    str(missing_spec),
                    "--repo-root",
                    str(repo_root),
                ]
            )
            self.assertEqual(1, code)
            self.assertEqual("", out.strip())
            self.assertIn("missing_spec_dir", err)

    def test_matrix_non_strict_writes_output_with_integrity_errors(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            out_file = repo_root / "matrix.json"

            payload = {
                "matrix": [],
                "coverage": {"fr_total": 0},
                "integrity_errors": ["Broken Trace in probe.json: Reference to 'fr-missing' not found."],
            }
            with patch("specdev_tools.validation.matrix.build_trace_matrix", return_value=payload), patch.dict(
                os.environ,
                {"SPECDEV_MATRIX_STRICT": "0"},
                clear=False,
            ):
                code, out, err = self._run_cli(
                    ["matrix", str(spec_dir), "--out", str(out_file), "--repo-root", str(repo_root)]
                )

            self.assertEqual(0, code, msg=err)
            self.assertIn(str(out_file), out)
            self.assertEqual("", err.strip())
            self.assertTrue(out_file.exists())
            written = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("integrity_errors", written)
            self.assertEqual(payload["integrity_errors"], written["integrity_errors"])

    def test_matrix_strict_writes_output_and_fails_on_integrity_errors(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()
            out_file = repo_root / "matrix.json"

            payload = {
                "matrix": [],
                "coverage": {"fr_total": 0},
                "integrity_errors": ["Broken Trace in probe.json: Reference to 'fr-missing' not found."],
            }
            with patch("specdev_tools.validation.matrix.build_trace_matrix", return_value=payload), patch.dict(
                os.environ,
                {"SPECDEV_MATRIX_STRICT": "1"},
                clear=False,
            ):
                code, out, err = self._run_cli(
                    ["matrix", str(spec_dir), "--out", str(out_file), "--repo-root", str(repo_root)]
                )

            self.assertEqual(1, code)
            self.assertIn(str(out_file), out)
            self.assertIn("E210 TRACE_INTEGRITY matrix_failed count=1", err)
            self.assertIn(payload["integrity_errors"][0], err)
            self.assertTrue(out_file.exists())
            written = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("integrity_errors", written)
            self.assertEqual(payload["integrity_errors"], written["integrity_errors"])

    def test_strict_canonical_manifest_schema_registration_is_enforced_across_commands(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "tools").mkdir()
            (repo_root / "canon").mkdir()
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()

            (repo_root / "tools" / "schema_registry.json").write_text(
                json.dumps({}),
                encoding="utf-8",
            )
            (repo_root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({}),
                encoding="utf-8",
            )

            commands = [
                ["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)],
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"],
                ["hallucination-lint", str(spec_dir), "--repo-root", str(repo_root)],
                ["validate-all", str(spec_dir), "--repo-root", str(repo_root)],
            ]
            for command in commands:
                code, out, err = self._run_cli(command)
                self.assertEqual(1, code, msg=f"command={command} out={out} err={err}")
                self.assertEqual("", out.strip(), msg=f"command={command} unexpected stdout={out}")
                self.assertIn("schema_uri_not_registered", err, msg=f"command={command} err={err}")
                if command[0] == "validate-all":
                    self.assertEqual(
                        1,
                        len([line for line in err.splitlines() if line.strip()]),
                        msg=f"command={command} err={err}",
                    )

    def test_strict_canonical_manifest_schema_registration_fails_when_registry_file_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            (repo_root / "canon").mkdir()
            spec_dir = repo_root / "spec"
            spec_dir.mkdir()

            (repo_root / "canon" / "manifest.json").write_text(
                json.dumps(
                    {
                        "registry_version": "1.0.0",
                        "entries": [],
                        "aliases": [],
                    }
                ),
                encoding="utf-8",
            )
            (spec_dir / "artifact.json").write_text(
                json.dumps({}),
                encoding="utf-8",
            )

            commands = [
                ["canonical-lint", str(repo_root / "canon"), "--repo-root", str(repo_root)],
                ["canonical-integrity", str(spec_dir), "--repo-root", str(repo_root)],
                ["canonical-autofix", str(spec_dir), "--repo-root", str(repo_root), "--dry-run"],
                ["hallucination-lint", str(spec_dir), "--repo-root", str(repo_root)],
                ["validate-all", str(spec_dir), "--repo-root", str(repo_root)],
            ]
            for command in commands:
                code, out, err = self._run_cli(command)
                self.assertEqual(1, code, msg=f"command={command} out={out} err={err}")
                self.assertEqual("", out.strip(), msg=f"command={command} unexpected stdout={out}")
                self.assertIn("missing_schema_registry", err, msg=f"command={command} err={err}")
                if command[0] == "validate-all":
                    self.assertEqual(
                        1,
                        len([line for line in err.splitlines() if line.strip()]),
                        msg=f"command={command} err={err}",
                    )


if __name__ == "__main__":
    unittest.main()
