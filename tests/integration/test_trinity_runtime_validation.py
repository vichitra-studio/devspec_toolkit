import json
import os
import re
import subprocess
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from specdev_tools.trinity_runtime_validate import validate_runtime_file
from specdev_tools.validate import validate_file


class TestTrinityRuntimeValidation(unittest.TestCase):
    def setUp(self):
        toolkit_root = Path(__file__).resolve().parents[2]
        self.repo_root = str(toolkit_root)
        self.tool_call_request_schema_sha = self._schema_sha_from_rel("schema/trinity/tool_call_request.schema.json")
        self.tool_call_result_schema_sha = self._schema_sha_from_rel("schema/trinity/tool_call_result.schema.json")

    def _schema_sha_from_rel(self, rel_path: str) -> str:
        abs_path = os.path.join(self.repo_root, rel_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _git_head_commit(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.skipTest("git is required for trinity runtime grounding tests")
        return result.stdout.strip()

    def _first_id_line(self, rel_path: str) -> tuple[str, int]:
        abs_path = os.path.join(self.repo_root, rel_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                match = re.search(r'"id"\s*:\s*"([^"]+)"', line)
                if match:
                    return match.group(1), idx
        self.fail(f"No id field found in {rel_path}")

    def _write_json(self, path: str, payload: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _event_sha256(self, event: dict) -> str:
        payload = dict(event)
        payload["event_sha256"] = None
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _valid_task_input_payload(self) -> dict:
        api_id, _ = self._first_id_line("spec/05_interface_contracts.json")
        return {
            "protocol_version": "trinity-runtime-v1",
            "child_id": "child-1",
            "parent_id": "parent-1",
            "role": "Planner",
            "phase": "16a",
            "step_id": "m1-core-foundation",
            "task_description": "Plan milestone m1-core-foundation.",
            "expected_output_schema": "https://specdev.local/schema/16_impl_context.schema.json",
            "context_pack_ref": ".trinity/runtime/spawns/child-1/context_pack.json",
            "target_files": ["spec/impl_context/m1-core-foundation.json"],
            "spec_refs": [{"type": "api", "id": api_id}],
            "role_metadata": {
                "prompt_source": "devspec_toolkit/prompts/prompt_16a_impl_planner.md",
                "persona_goal": "Create checklist-driven implementation plan",
                "stop_conditions": ["missing required seed", "schema validation fail"],
            },
        }

    def _valid_context_pack_16b(self) -> dict:
        commit_hash = self._git_head_commit()
        api_id, api_line = self._first_id_line("spec/05_interface_contracts.json")
        return {
            "protocol_version": "trinity-runtime-v1",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "seed_manifest_path": "spec/common/seed_manifest.json",
            "seed_files_ordered": ["docs/seed/seed_overview.md", "docs/seed/seed_tech_stack.md"],
            "required_spec_refs": [
                {
                    "type": "api",
                    "id": api_id,
                    "path": "spec/05_interface_contracts.json",
                    "line_range": f"L{api_line}-L{api_line}",
                    "commit_hash": commit_hash,
                }
            ],
            "artifact_refs": {
                "milestone_context_path": "spec/impl_context/m1-core-foundation.json",
                "anchor_path": "spec/16_impl_context.json",
            },
            "allowed_read_paths": ["spec/", "src/", "tests/"],
            "allowed_write_paths": ["src/", "tests/", "spec/impl_context/", "README.md"],
            "target_file_patterns": ["src/auth.py", "tests/auth/test_login.py", "README.md"],
            "docs_policy": {
                "doc_paths": ["docs/**", "README.md"],
                "readme_required": True,
                "root_readme_required": True,
            },
            "test_contract": {
                "test_commands": ["pytest tests/auth/test_login.py::test_jwt -q"],
                "success_markers": ["PASSED", "0 failed"],
            },
        }

    def _valid_context_pack_16a_for_task_input(self) -> dict:
        payload = self._valid_context_pack_16b()
        payload["phase"] = "16a"
        payload["target_file_patterns"] = ["spec/impl_context/m1-core-foundation.json"]
        payload["allowed_write_paths"] = ["spec/impl_context/", "README.md"]
        payload.pop("test_contract", None)
        return payload

    def _valid_session_event(self) -> dict:
        event = {
            "schema_version": "trinity-session-log-v1",
            "timestamp": "2026-02-13T00:00:00Z",
            "event_type": "SPAWN",
            "event_id": "evt-1",
            "event_sequence": 1,
            "prev_event_sha256": None,
            "event_sha256": "0" * 64,
            "run_id": "run-1",
            "phase_id": "phase-16a",
            "loop_id": "loop-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Orchestrator",
            "step_id": "m1-core-foundation",
            "tool_call_id": None,
            "result_id": None,
            "artifact_ref": ".trinity/runtime/spawns/child-1/task_input.json",
            "artifact_sha256": "a" * 64,
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "spawn planner",
                "task_input_artifact_ref": ".trinity/runtime/spawns/child-1/task_input.json",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
            },
            "metadata": {
                "toolkit_version": "0.2.3",
                "schema_version": "v1",
                "git_head": "deadbeef",
                "prompt_template_id": "prompt-16a",
                "prompt_template_sha256": "b" * 64,
                "redaction_profile": "eval",
                "redaction_applied": False,
                "capture_policy_ref": None,
                "capture_policy_sha256": None,
                "redaction_stats": {
                    "total_replacements": 0,
                    "by_class": {},
                    "classes_detected": [],
                    "detectors_used": ["secret_scanner_v1"],
                    "min_confidence": 0.0,
                    "max_confidence": 0.0,
                },
                "decoding": {"temperature": 0.2, "top_p": 0.9, "max_tokens": 4096},
                "token_usage": {"prompt": 100, "completion": 50, "total": 150},
                "tool_schema_context": {
                    "mode": "full_inline",
                    "catalog_ref": None,
                    "catalog_sha256": None,
                    "expanded_tool_names": [],
                    "request_schema_uri": "https://specdev.local/schema/trinity/tool_call_request.schema.json",
                    "request_schema_sha256": self.tool_call_request_schema_sha,
                    "result_schema_uri": "https://specdev.local/schema/trinity/tool_call_result.schema.json",
                    "result_schema_sha256": self.tool_call_result_schema_sha,
                },
            },
        }
        event["event_sha256"] = self._event_sha256(event)
        return event

    def test_validate_file_fallback_for_task_input(self):
        payload = self._valid_task_input_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_input.json")
            context_pack_path = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "context_pack.json")
            self._write_json(path, payload)
            self._write_json(context_pack_path, self._valid_context_pack_16a_for_task_input())
            errors = validate_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Runtime task_input should validate via fallback. Errors: {errors}")

    def test_validate_file_fallback_invalid_task_input(self):
        payload = self._valid_task_input_payload()
        payload.pop("role_metadata")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_input.json")
            context_pack_path = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "context_pack.json")
            self._write_json(path, payload)
            self._write_json(context_pack_path, self._valid_context_pack_16a_for_task_input())
            errors = validate_file(self.repo_root, path)
            self.assertTrue(errors, "Invalid runtime task_input should fail validation")

    def test_validate_runtime_context_pack_valid_16b(self):
        payload = self._valid_context_pack_16b()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Context pack should validate. Errors: {errors}")

    def test_validate_runtime_context_pack_missing_phase_required_seed_fails(self):
        payload = self._valid_context_pack_16b()
        payload["seed_files_ordered"] = ["docs/seed/seed_overview.md"]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("step_requirements['16b']" in e for e in errors),
                f"Context pack should fail when phase-required seeds are missing. Errors: {errors}",
            )

    def test_validate_runtime_context_pack_missing_required_spec_refs_fails(self):
        payload = self._valid_context_pack_16b()
        payload["required_spec_refs"] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("required_spec_refs" in e for e in errors),
                f"Context pack should fail when required_spec_refs is empty for phase 16x. Errors: {errors}",
            )

    def test_validate_runtime_context_pack_bootstrap_ref_trace_maps_to_required_refs(self):
        payload = self._valid_context_pack_16a_for_task_input()
        ref = payload["required_spec_refs"][0]
        payload["bootstrap_ref_trace"] = [
            {
                "spec_type": ref["type"],
                "id": ref["id"],
                "selected_from": "roadmap.milestones[m1-core-foundation].deliverables[0]",
                "selection_mode": "structured",
                "path": ref["path"],
                "line_range": ref["line_range"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Context pack bootstrap_ref_trace should validate. Errors: {errors}")

    def test_validate_runtime_context_pack_bootstrap_ref_trace_rejects_unmapped_refs(self):
        payload = self._valid_context_pack_16a_for_task_input()
        ref = payload["required_spec_refs"][0]
        payload["bootstrap_ref_trace"] = [
            {
                "spec_type": ref["type"],
                "id": "api-missing-from-required-refs",
                "selected_from": "roadmap.milestones[m1-core-foundation].name",
                "selection_mode": "tokenized",
                "path": ref["path"],
                "line_range": ref["line_range"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("bootstrap_ref_trace" in e and "required_spec_refs" in e for e in errors),
                f"Context pack should reject bootstrap_ref_trace entries not mapped to required_spec_refs. Errors: {errors}",
            )

    def test_validate_runtime_context_pack_invalid_missing_test_contract_for_16b(self):
        payload = self._valid_context_pack_16b()
        payload.pop("test_contract")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(errors, "16b context pack without test_contract should fail validation")

    def test_validate_runtime_task_result_questions(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "child_id": "child-1",
            "role": "Planner",
            "phase": "16a",
            "step_id": "m1-core-foundation",
            "status": "questions",
            "summary": "Need clarification before plan emission",
            "artifacts": [],
            "questions": ["Which roadmap milestone should be active?"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Questions task_result should validate. Errors: {errors}")

    def test_validate_runtime_task_result_questions_missing_questions(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "child_id": "child-1",
            "role": "Planner",
            "phase": "16a",
            "step_id": "m1-core-foundation",
            "status": "questions",
            "summary": "Need clarification before plan emission",
            "artifacts": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(errors, "Questions task_result without questions array should fail validation")

    def test_validate_runtime_task_result_blocked_requires_finding_provenance(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "child_id": "child-1",
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "status": "blocked",
            "summary": "Blocked by missing context",
            "artifacts": [],
            "findings": [
                {
                    "id": "missing-seed",
                    "type": "policy",
                    "severity": "blocking",
                    "description": "Required seed missing",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "task_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("source" in e or "impact" in e for e in errors),
                f"Blocked task_result findings should require source and impact. Errors: {errors}",
            )

    def test_validate_runtime_task_result_success_16b_requires_execution_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = os.path.join(tmp, "m1-core-foundation.json")
            self._write_json(
                artifact_path,
                {
                    "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
                    "id": "m1-core-foundation",
                    "owner": "api",
                    "created_at": "2026-02-13T00:00:00Z",
                    "seed_refs": [{"seed_id": "seed-overview"}],
                    "plan": {
                        "status": "active",
                        "summary": {
                            "functional_summary": "x",
                            "scope_in": ["x"],
                            "scope_out": [],
                            "target_file_patterns": ["src/x.py", "README.md"],
                        },
                        "docs_impact": {
                            "status": "required",
                            "rationale": "x rationale for docs impact.",
                            "docs_touched": ["README.md"],
                        },
                        "spec_alignment": {
                            "checklist": [
                                {
                                    "id": "CHK_X_01",
                                    "spec_ref": {
                                        "type": "fr",
                                        "id": "fr-core-login",
                                        "line_range": "L1-L1",
                                        "commit_hash": "a1b2c3d4e5f61234567890123456789012345678",
                                    },
                                    "description": "x",
                                    "linked_test_expectation": "pytest -q",
                                    "type": "behavior",
                                    "layer": "service",
                                    "nfr_refs": ["nfr-availability-uptime"],
                                    "fixture_ref": "fixture-login-success",
                                    "implementation": {
                                        "status": "pending",
                                        "actions": [
                                            {
                                                "type": "manual_verification",
                                                "description": "x",
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "review_requirements": {"test_commands": ["pytest -q"]},
                    },
                },
            )
            task_result_path = os.path.join(tmp, "task_result.json")
            self._write_json(
                task_result_path,
                {
                    "protocol_version": "trinity-runtime-v1",
                    "child_id": "child-1",
                    "role": "Builder",
                    "phase": "16b",
                    "step_id": "m1-core-foundation",
                    "status": "success",
                    "summary": "builder completed",
                    "artifacts": [artifact_path],
                },
            )
            errors = validate_runtime_file(self.repo_root, task_result_path)
            self.assertTrue(
                any("phase 16b success artifact" in e for e in errors),
                f"16b success task_result should require execution section. Errors: {errors}",
            )

    def test_validate_runtime_task_result_success_16b_referenced_step16_must_be_schema_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = os.path.join(tmp, "m1-core-foundation.json")
            # Contains the Step 16 schema URI but is intentionally schema-invalid:
            # missing required top-level plan/owner/created_at/seed_refs.
            self._write_json(
                artifact_path,
                {
                    "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
                    "id": "m1-core-foundation",
                    "execution": {
                        "execution_results": [
                            {
                                "status": "passed",
                                "outcome_description": "ran tests",
                                "reasoning": "ok",
                                "command": "pytest -q",
                                "evidence": "tests PASSED",
                                "evidence_ref": "sha256:" + ("a" * 64),
                                "evidence_binding": {
                                    "sha256": "a" * 64,
                                    "command": "pytest -q",
                                    "exit_code": 0,
                                },
                            }
                        ]
                    },
                },
            )
            task_result_path = os.path.join(tmp, "task_result.json")
            self._write_json(
                task_result_path,
                {
                    "protocol_version": "trinity-runtime-v1",
                    "child_id": "child-1",
                    "role": "Builder",
                    "phase": "16b",
                    "step_id": "m1-core-foundation",
                    "status": "success",
                    "summary": "builder completed",
                    "artifacts": [artifact_path],
                },
            )
            errors = validate_runtime_file(self.repo_root, task_result_path)
            self.assertTrue(
                any("failed step16 validation" in e for e in errors),
                f"16b success task_result should fail when referenced Step 16 artifact is schema-invalid. Errors: {errors}",
            )

    def test_validate_runtime_task_result_success_16c_verified_rejects_blocking_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = os.path.join(tmp, "m1-core-foundation.json")
            evidence = "PASSED marker content"
            evidence_sha = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
            api_id, api_line = self._first_id_line("spec/05_interface_contracts.json")
            commit_hash = self._git_head_commit()
            line_range = f"L{api_line}-L{api_line}"
            self._write_json(
                artifact_path,
                {
                    "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
                    "id": "m1-core-foundation",
                    "owner": "api",
                    "created_at": "2026-02-13T00:00:00Z",
                    "seed_refs": [{"seed_id": "seed-overview"}],
                    "plan": {
                        "status": "active",
                        "summary": {
                            "functional_summary": "x",
                            "scope_in": ["x"],
                            "scope_out": [],
                            "target_file_patterns": ["src/x.py", "README.md"],
                        },
                        "docs_impact": {
                            "status": "required",
                            "rationale": "x rationale for docs impact.",
                            "docs_touched": ["README.md"],
                        },
                        "spec_alignment": {
                            "checklist": [
                                {
                                    "id": "CHK_X_01",
                                    "spec_ref": {
                                        "type": "api",
                                        "id": api_id,
                                        "line_range": line_range,
                                        "commit_hash": commit_hash,
                                    },
                                    "description": "x",
                                    "linked_test_expectation": "pytest -q",
                                    "type": "behavior",
                                    "layer": "service",
                                    "nfr_refs": ["nfr-availability-uptime"],
                                    "fixture_ref": "fixture-login-success",
                                    "implementation": {
                                        "status": "verified",
                                        "actions": [
                                            {
                                                "type": "manual_verification",
                                                "description": "x",
                                                "evidence": {
                                                    "type": "snippet",
                                                    "content": evidence,
                                                    "evidence_ref": f"sha256:{evidence_sha}",
                                                },
                                            }
                                        ],
                                    },
                                }
                            ]
                        },
                        "review_requirements": {"test_commands": ["pytest -q"]},
                    },
                    "execution": {
                        "files_touched": ["README.md"],
                        "execution_results": [
                            {
                                "status": "passed",
                                "outcome_description": "ok",
                                "reasoning": "ok",
                                "command": "pytest -q",
                                "evidence": evidence,
                                "evidence_ref": f"sha256:{evidence_sha}",
                                "evidence_binding": {
                                    "sha256": evidence_sha,
                                    "command": "pytest -q",
                                    "exit_code": 0,
                                    "timestamp": "2026-02-13T00:00:00Z",
                                },
                            }
                        ],
                        "critical_evidence": {
                            "satisfied_checklist_ids": ["CHK_X_01"],
                            "passed_test_commands": ["pytest -q"],
                        },
                    },
                    "review": {
                        "findings": [
                            {
                                "id": "f-1",
                                "type": "tests",
                                "severity": "blocking",
                                "description": "blocking issue present",
                                "spec_ref": {
                                    "type": "api",
                                    "id": api_id,
                                    "line_range": line_range,
                                    "commit_hash": commit_hash,
                                },
                                "metadata": {"source": "Verifier", "impact": "functional-failure"},
                                "remediation_task": {
                                    "task_id": "rem-1",
                                    "summary": "fix it",
                                    "checklist_ids": ["CHK_X_01"],
                                    "files_to_touch": ["README.md"],
                                },
                            }
                        ],
                        "ratings": {
                            "spec_completeness": 5,
                            "code_quality": 5,
                            "tests_completeness": 5,
                            "docs_completeness": 5,
                            "metadata_usage": 5,
                        },
                        "verdict": "verified",
                        "next_actions": "Milestone verified.",
                        "fixture_status": {
                            "implemented_endpoints": [],
                            "test_results": [],
                            "ci_status": "green",
                        },
                    },
                },
            )
            task_result_path = os.path.join(tmp, "task_result.json")
            self._write_json(
                task_result_path,
                {
                    "protocol_version": "trinity-runtime-v1",
                    "child_id": "child-1",
                    "role": "Verifier",
                    "phase": "16c",
                    "step_id": "m1-core-foundation",
                    "status": "success",
                    "summary": "verifier completed",
                    "artifacts": [artifact_path],
                },
            )
            errors = validate_runtime_file(self.repo_root, task_result_path)
            self.assertTrue(
                any("verdict=verified but includes blocking/major findings" in e for e in errors),
                f"16c success task_result should fail when verified verdict conflicts with findings severity. Errors: {errors}",
            )

    def test_validate_runtime_context_pack_invalid_protocol_version(self):
        payload = self._valid_context_pack_16b()
        payload["protocol_version"] = "v1"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(errors, "Context pack with non-constant protocol_version should fail validation")

    def test_validate_runtime_scratchpad_state(self):
        payload = {
            "phase": "16b",
            "checklist_scope": ["CHK_AUTH_01"],
            "last_validation_gate": {
                "schema": "pass",
                "deep_validator": "pass",
                "governance": "n/a",
            },
            "next_action_ref": "checklist:CHK_AUTH_01:run_tests",
            "state_summary": "Continue implementation and run linked tests",
            "milestone_step_id": "m1-core-foundation",
            "created_at": "2026-02-13T00:00:00+00:00",
            "updated_at": "2026-02-13T00:00:00+00:00",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scratchpad_abc123.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Scratchpad state should validate. Errors: {errors}")

    def test_validate_runtime_session_event_log(self):
        event = self._valid_session_event()
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            validation_input = self._valid_session_event()
            validation_input["event_type"] = "VALIDATION"
            validation_input["event_id"] = "evt-2"
            validation_input["event_sequence"] = 2
            validation_input["prev_event_sha256"] = event["event_sha256"]
            validation_input["content"] = {
                "summary": "validated spawn task input",
                "task_input_artifact_ref": ".trinity/runtime/spawns/child-1/task_input.json",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            }
            validation_input["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_input.json"
            validation_input["artifact_sha256"] = "b" * 64
            validation_input["event_sha256"] = self._event_sha256(validation_input)

            validation_result = self._valid_session_event()
            validation_result["event_type"] = "VALIDATION"
            validation_result["event_id"] = "evt-3"
            validation_result["event_sequence"] = 3
            validation_result["prev_event_sha256"] = validation_input["event_sha256"]
            validation_result["content"] = {
                "summary": "validated child result",
                "task_result_artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            }
            validation_result["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
            validation_result["artifact_sha256"] = "d" * 64
            validation_result["event_sha256"] = self._event_sha256(validation_result)

            terminate = self._valid_session_event()
            terminate["event_type"] = "TERMINATE"
            terminate["event_id"] = "evt-4"
            terminate["event_sequence"] = 4
            terminate["prev_event_sha256"] = validation_result["event_sha256"]
            terminate["content"] = {
                "summary": "child completed",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_result_artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
            }
            terminate["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
            terminate["artifact_sha256"] = "c" * 64
            terminate["event_sha256"] = self._event_sha256(terminate)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
                f.write(json.dumps(validation_input) + "\n")
                f.write(json.dumps(validation_result) + "\n")
                f.write(json.dumps(terminate) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Session event log should validate. Errors: {errors}")

    def test_validate_runtime_session_event_log_fails_when_spawn_not_terminated(self):
        event = self._valid_session_event()
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("SPAWN event(s) but only" in e for e in errors),
                f"Session log should fail when SPAWN does not have matching TERMINATE. Errors: {errors}",
            )

    def test_validate_runtime_session_event_spawn_ref_must_be_canonical(self):
        event = self._valid_session_event()
        event["content"]["task_input_artifact_ref"] = "task_input.json"
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("task_input_artifact_ref" in e for e in errors),
                f"Session log should fail when SPAWN task_input_artifact_ref is non-canonical. Errors: {errors}",
            )

    def test_validate_runtime_session_event_terminate_ref_must_be_canonical(self):
        spawn = self._valid_session_event()
        terminate = self._valid_session_event()
        terminate["event_type"] = "TERMINATE"
        terminate["event_id"] = "evt-2"
        terminate["event_sequence"] = 2
        terminate["prev_event_sha256"] = spawn["event_sha256"]
        terminate["content"] = {
            "summary": "child completed",
            "capture_level": "none",
            "capture_decision_reason": "policy:default:none",
            "prompt_artifact_ref": None,
            "prompt_sha256": None,
            "response_artifact_ref": None,
            "response_sha256": None,
            "task_result_artifact_ref": "task_result.json",
        }
        terminate["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
        terminate["artifact_sha256"] = "c" * 64
        terminate["event_sha256"] = self._event_sha256(terminate)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(spawn) + "\n")
                f.write(json.dumps(terminate) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("task_result_artifact_ref" in e for e in errors),
                f"Session log should fail when TERMINATE task_result_artifact_ref is non-canonical. Errors: {errors}",
            )

    def test_validate_runtime_session_event_artifact_ref_requires_artifact_sha256(self):
        event = self._valid_session_event()
        event["event_type"] = "MESSAGE"
        event["content"].pop("task_input_artifact_ref", None)
        event["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_input.json"
        event["artifact_sha256"] = None
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("artifact_sha256" in e for e in errors),
                f"Session event should fail when artifact_ref is set without artifact_sha256. Errors: {errors}",
            )

    def test_validate_runtime_session_event_tool_result_requires_result_id(self):
        event = self._valid_session_event()
        event["event_type"] = "TOOL_RESULT"
        event["tool_call_id"] = "tool-1"
        event["result_id"] = None
        event["content"].pop("task_input_artifact_ref", None)
        event["content"]["tool_result"] = {
            "command": "pytest -q",
            "exit_code": 0,
            "duration_ms": 1200,
            "working_dir": "/tmp/workspace",
        }
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(errors, "TOOL_RESULT event without result_id should fail validation")

    def test_validate_runtime_session_event_tool_call_missing_tool_schema_context_fails(self):
        event = self._valid_session_event()
        event["event_type"] = "TOOL_CALL"
        event["tool_call_id"] = "tool-1"
        event["content"]["tool_call"] = {"name": "exec_cmd", "args": {"command": "pytest -q", "mode": "summarized"}}
        event["metadata"].pop("tool_schema_context", None)
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("tool_schema_context" in e for e in errors),
                f"TOOL_CALL should fail when tool_schema_context is missing. Errors: {errors}",
            )

    def test_validate_runtime_session_event_tool_call_on_demand_context_requires_expanded_tool(self):
        event = self._valid_session_event()
        event["event_type"] = "TOOL_CALL"
        event["tool_call_id"] = "tool-1"
        event["content"]["tool_call"] = {"name": "exec_cmd", "args": {"command": "pytest -q", "mode": "summarized"}}
        event["metadata"]["tool_schema_context"] = {
            "mode": "catalog_plus_on_demand",
            "catalog_ref": ".trinity/runtime/tools/catalog.json",
            "catalog_sha256": "9" * 64,
            "expanded_tool_names": ["read_file"],
            "request_schema_uri": "https://specdev.local/schema/trinity/tool_call_request.schema.json",
            "request_schema_sha256": self.tool_call_request_schema_sha,
            "result_schema_uri": "https://specdev.local/schema/trinity/tool_call_result.schema.json",
            "result_schema_sha256": self.tool_call_result_schema_sha,
        }
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("expanded_tool_names" in e for e in errors),
                f"TOOL_CALL on-demand context should fail when expanded tool list omits active tool. Errors: {errors}",
            )

    def test_validate_runtime_session_event_tool_result_requires_prior_tool_call(self):
        tool_result = self._valid_session_event()
        tool_result["event_type"] = "TOOL_RESULT"
        tool_result["tool_call_id"] = "tool-missing"
        tool_result["result_id"] = "result-1"
        tool_result["content"].pop("task_input_artifact_ref", None)
        tool_result["content"]["tool_result"] = {
            "command": "pytest -q",
            "exit_code": 0,
            "duration_ms": 1200,
            "working_dir": "/tmp/workspace",
        }
        tool_result["event_sha256"] = self._event_sha256(tool_result)

        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(tool_result) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("unknown tool_call_id" in e for e in errors),
                f"Session log should fail when TOOL_RESULT has no prior TOOL_CALL. Errors: {errors}",
            )

    def test_validate_runtime_session_event_detects_sensitive_content(self):
        event = self._valid_session_event()
        event["event_type"] = "TOOL_RESULT"
        event["tool_call_id"] = "tool-1"
        event["result_id"] = "result-1"
        event["content"].pop("task_input_artifact_ref", None)
        event["content"]["tool_result"] = {
            "command": "pytest -q",
            "exit_code": 0,
            "duration_ms": 1200,
            "working_dir": "/tmp/workspace",
            "stdout_excerpt": "token=ghp_123456789012345678901234567890123456",
            "stderr_excerpt": "",
            "truncated": False,
        }
        event["event_sha256"] = self._event_sha256(event)

        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                # include matching TOOL_CALL first so failure is from secret detection
                tool_call = self._valid_session_event()
                tool_call["event_type"] = "TOOL_CALL"
                tool_call["tool_call_id"] = "tool-1"
                tool_call["result_id"] = None
                tool_call["content"]["tool_call"] = {"name": "exec_cmd", "args": {"command": "pytest -q"}}
                tool_call["event_sha256"] = self._event_sha256(tool_call)
                f.write(json.dumps(tool_call) + "\n")

                event["event_sequence"] = 2
                event["prev_event_sha256"] = tool_call["event_sha256"]
                event["event_sha256"] = self._event_sha256(event)
                f.write(json.dumps(event) + "\n")

            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("sensitive content detected" in e for e in errors),
                f"Session log should fail when sensitive content is persisted. Errors: {errors}",
            )

    def test_validate_runtime_session_event_log_invalid_hash_chain(self):
        event_1 = self._valid_session_event()
        event_2 = self._valid_session_event()
        event_2["event_id"] = "evt-2"
        event_2["event_sequence"] = 2
        event_2["prev_event_sha256"] = "f" * 64
        event_2["event_sha256"] = self._event_sha256(event_2)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event_1) + "\n")
                f.write(json.dumps(event_2) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("prev_event_sha256 does not match previous event hash" in e for e in errors),
                f"Session log should fail when hash chain is invalid. Errors: {errors}",
            )

    def test_validate_runtime_session_event_log_invalid_redaction_stats(self):
        event = self._valid_session_event()
        event["metadata"]["redaction_applied"] = True
        event["metadata"]["redaction_stats"]["total_replacements"] = 0
        event["metadata"]["redaction_stats"]["by_class"] = {"openai_key": 1}
        event["metadata"]["redaction_stats"]["classes_detected"] = ["openai_key"]
        event["event_sha256"] = self._event_sha256(event)
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("by_class total exceeds" in e for e in errors),
                f"Session log should fail for inconsistent redaction stats. Errors: {errors}",
            )

    def test_validate_runtime_session_event_log_policy_enforced_capture_level(self):
        event = self._valid_session_event()
        policy = {
            "policy_id": "policy-default",
            "version": "1",
            "default_capture_level": "none",
            "always_full_on_event_types": ["SPAWN"],
            "sample_rate_by_event_type": {
                "SPAWN": 0.0,
                "MESSAGE": 0.0,
                "TOOL_CALL": 0.0,
                "TOOL_RESULT": 0.0,
                "VALIDATION": 0.0,
                "TERMINATE": 0.0,
                "ERROR": 0.0
            },
            "max_full_events_per_run": 10,
            "oversize_fallback": "summary",
            "full_capture_allowlist_roles": ["Orchestrator"],
            "require_redaction_before_full": False,
            "sampling_salt": "salt-1"
        }
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            policy_path = os.path.join(tmp, "log_capture_policy.json")
            self._write_json(policy_path, policy)

            policy_sha = hashlib.sha256(
                json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            event["metadata"]["capture_policy_ref"] = policy_path
            event["metadata"]["capture_policy_sha256"] = policy_sha
            event["content"]["capture_level"] = "none"
            event["content"]["capture_decision_reason"] = "policy:default:none"
            event["event_sha256"] = self._event_sha256(event)

            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("policy-expected level 'full'" in e for e in errors),
                f"Session log should fail when capture policy mandates full capture. Errors: {errors}",
            )

    def test_validate_runtime_session_event_log_policy_sampled_full(self):
        event = self._valid_session_event()
        policy = {
            "policy_id": "policy-sampled",
            "version": "1",
            "default_capture_level": "none",
            "always_full_on_event_types": [],
            "sample_rate_by_event_type": {
                "SPAWN": 1.0,
                "MESSAGE": 0.0,
                "TOOL_CALL": 0.0,
                "TOOL_RESULT": 0.0,
                "VALIDATION": 0.0,
                "TERMINATE": 0.0,
                "ERROR": 0.0
            },
            "max_full_events_per_run": 1,
            "oversize_fallback": "summary",
            "full_capture_allowlist_roles": ["Orchestrator"],
            "require_redaction_before_full": False,
            "sampling_salt": "salt-2"
        }
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            policy_path = os.path.join(tmp, "log_capture_policy.json")
            self._write_json(policy_path, policy)

            policy_sha = hashlib.sha256(
                json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            event["metadata"]["capture_policy_ref"] = policy_path
            event["metadata"]["capture_policy_sha256"] = policy_sha
            event["content"]["capture_level"] = "full"
            event["content"]["capture_decision_reason"] = "policy:sampled:SPAWN"
            event["content"]["prompt_artifact_ref"] = ".trinity/captures/prompt_evt-1.txt"
            event["content"]["prompt_sha256"] = "1" * 64
            event["content"]["response_artifact_ref"] = ".trinity/captures/response_evt-1.txt"
            event["content"]["response_sha256"] = "2" * 64
            event["event_sha256"] = self._event_sha256(event)

            validation_input = self._valid_session_event()
            validation_input["event_type"] = "VALIDATION"
            validation_input["event_id"] = "evt-2"
            validation_input["event_sequence"] = 2
            validation_input["prev_event_sha256"] = event["event_sha256"]
            validation_input["content"] = {
                "summary": "validated task input",
                "task_input_artifact_ref": ".trinity/runtime/spawns/child-1/task_input.json",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            }
            validation_input["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_input.json"
            validation_input["artifact_sha256"] = "3" * 64
            validation_input["metadata"]["capture_policy_ref"] = policy_path
            validation_input["metadata"]["capture_policy_sha256"] = policy_sha
            validation_input["event_sha256"] = self._event_sha256(validation_input)

            validation_result = self._valid_session_event()
            validation_result["event_type"] = "VALIDATION"
            validation_result["event_id"] = "evt-3"
            validation_result["event_sequence"] = 3
            validation_result["prev_event_sha256"] = validation_input["event_sha256"]
            validation_result["content"] = {
                "summary": "validated task result",
                "task_result_artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            }
            validation_result["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
            validation_result["artifact_sha256"] = "4" * 64
            validation_result["metadata"]["capture_policy_ref"] = policy_path
            validation_result["metadata"]["capture_policy_sha256"] = policy_sha
            validation_result["event_sha256"] = self._event_sha256(validation_result)

            terminate = self._valid_session_event()
            terminate["event_type"] = "TERMINATE"
            terminate["event_id"] = "evt-4"
            terminate["event_sequence"] = 4
            terminate["prev_event_sha256"] = validation_result["event_sha256"]
            terminate["content"] = {
                "summary": "child completed",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_result_artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
            }
            terminate["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
            terminate["artifact_sha256"] = "d" * 64
            terminate["metadata"]["capture_policy_ref"] = policy_path
            terminate["metadata"]["capture_policy_sha256"] = policy_sha
            terminate["event_sha256"] = self._event_sha256(terminate)

            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
                f.write(json.dumps(validation_input) + "\n")
                f.write(json.dumps(validation_result) + "\n")
                f.write(json.dumps(terminate) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Session log should pass when sampled policy is honored. Errors: {errors}")

    def test_validate_runtime_session_event_log_policy_token_budget_fallback(self):
        event = self._valid_session_event()
        policy = {
            "policy_id": "policy-budget",
            "version": "1",
            "default_capture_level": "none",
            "always_full_on_event_types": ["SPAWN"],
            "sample_rate_by_event_type": {
                "SPAWN": 0.0,
                "MESSAGE": 0.0,
                "TOOL_CALL": 0.0,
                "TOOL_RESULT": 0.0,
                "VALIDATION": 0.0,
                "TERMINATE": 0.0,
                "ERROR": 0.0
            },
            "max_full_events_per_run": 10,
            "context_window_token_target": 80000,
            "max_full_capture_context_fraction": 0.001,
            "full_capture_token_budget_per_run": 50,
            "max_full_prompt_tokens_per_event": 1000,
            "max_full_completion_tokens_per_event": 1000,
            "oversize_fallback": "summary",
            "full_capture_allowlist_roles": ["Orchestrator"],
            "require_redaction_before_full": False,
            "sampling_salt": "salt-budget"
        }
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            policy_path = os.path.join(tmp, "log_capture_policy.json")
            self._write_json(policy_path, policy)

            policy_sha = hashlib.sha256(
                json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            event["metadata"]["capture_policy_ref"] = policy_path
            event["metadata"]["capture_policy_sha256"] = policy_sha
            event["metadata"]["token_usage"] = {"prompt": 90, "completion": 80, "total": 170}
            event["content"]["capture_level"] = "full"
            event["content"]["capture_decision_reason"] = "policy:always_full:SPAWN"
            event["content"]["prompt_artifact_ref"] = ".trinity/captures/prompt_evt-1.txt"
            event["content"]["prompt_sha256"] = "1" * 64
            event["content"]["response_artifact_ref"] = ".trinity/captures/response_evt-1.txt"
            event["content"]["response_sha256"] = "2" * 64
            event["event_sha256"] = self._event_sha256(event)

            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("policy-expected level 'summary'" in e for e in errors),
                f"Session log should fail when full-capture token budget is exceeded. Errors: {errors}",
            )

    def test_validate_runtime_session_event_log_policy_per_event_token_guard(self):
        event = self._valid_session_event()
        policy = {
            "policy_id": "policy-per-event",
            "version": "1",
            "default_capture_level": "none",
            "always_full_on_event_types": ["SPAWN"],
            "sample_rate_by_event_type": {
                "SPAWN": 0.0,
                "MESSAGE": 0.0,
                "TOOL_CALL": 0.0,
                "TOOL_RESULT": 0.0,
                "VALIDATION": 0.0,
                "TERMINATE": 0.0,
                "ERROR": 0.0
            },
            "max_full_events_per_run": 10,
            "context_window_token_target": 80000,
            "max_full_capture_context_fraction": 0.5,
            "full_capture_token_budget_per_run": 10000,
            "max_full_prompt_tokens_per_event": 20,
            "max_full_completion_tokens_per_event": 1000,
            "oversize_fallback": "summary",
            "full_capture_allowlist_roles": ["Orchestrator"],
            "require_redaction_before_full": False,
            "sampling_salt": "salt-per-event"
        }
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            policy_path = os.path.join(tmp, "log_capture_policy.json")
            self._write_json(policy_path, policy)

            policy_sha = hashlib.sha256(
                json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            event["metadata"]["capture_policy_ref"] = policy_path
            event["metadata"]["capture_policy_sha256"] = policy_sha
            event["metadata"]["token_usage"] = {"prompt": 100, "completion": 10, "total": 110}
            event["content"]["capture_level"] = "full"
            event["content"]["capture_decision_reason"] = "policy:always_full:SPAWN"
            event["content"]["prompt_artifact_ref"] = ".trinity/captures/prompt_evt-1.txt"
            event["content"]["prompt_sha256"] = "1" * 64
            event["content"]["response_artifact_ref"] = ".trinity/captures/response_evt-1.txt"
            event["content"]["response_sha256"] = "2" * 64
            event["event_sha256"] = self._event_sha256(event)

            path = os.path.join(sessions_dir, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("policy-expected level 'summary'" in e for e in errors),
                f"Session log should fail when per-event prompt token guard is exceeded. Errors: {errors}",
            )

    def test_validate_runtime_context_pack_invalid_outside_allowed_write_paths(self):
        payload = self._valid_context_pack_16b()
        payload["target_file_patterns"] = ["infra/scripts/deploy.sh"]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(errors, "Context pack should fail when target_file_patterns are outside allowed_write_paths")

    def test_validate_runtime_context_pack_invalid_ungrounded_spec_ref_commit(self):
        payload = self._valid_context_pack_16b()
        payload["required_spec_refs"][0]["commit_hash"] = "f" * 40
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context_pack.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("commit_hash" in e and "not found in git" in e for e in errors),
                f"Context pack should fail grounding when commit hash is invalid. Errors: {errors}",
            )

    def test_validate_runtime_log_capture_policy_schema(self):
        payload = {
            "policy_id": "policy-basic",
            "version": "1",
            "default_capture_level": "summary",
            "always_full_on_event_types": ["ERROR"],
            "sample_rate_by_event_type": {
                "SPAWN": 0.0,
                "MESSAGE": 0.0,
                "TOOL_CALL": 0.0,
                "TOOL_RESULT": 0.0,
                "VALIDATION": 0.0,
                "TERMINATE": 0.0,
                "ERROR": 0.0
            },
            "max_full_events_per_run": 10,
            "context_window_token_target": 80000,
            "max_full_capture_context_fraction": 0.25,
            "full_capture_token_budget_per_run": 20000,
            "max_full_prompt_tokens_per_event": 2048,
            "max_full_completion_tokens_per_event": 2048,
            "oversize_fallback": "summary",
            "full_capture_allowlist_roles": [],
            "require_redaction_before_full": True,
            "sampling_salt": "seed",
            "operating_profile": {
                "profile": "eval_default",
                "tier": "balanced",
                "budget_tier": "medium",
            },
            "budgets": {
                "context_window_token_target": 80000,
                "full_capture_token_budget_per_run": 20000,
                "max_full_prompt_tokens_per_event": 2048,
                "max_full_completion_tokens_per_event": 2048,
            },
            "retention": {
                "session_log_days": 30,
                "capture_artifact_days": 14,
                "eval_export_days": 90,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log_capture_policy.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Log capture policy should validate. Errors: {errors}")

    def test_validate_runtime_utility_call_schema(self):
        payload = {
            "role": "Researcher",
            "objective": "Collect grounded references",
            "input": {"required_outputs": ["findings"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "utility_call.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"utility_call payload should validate. Errors: {errors}")

    def test_validate_runtime_utility_result_schema(self):
        payload = {
            "status": "questions",
            "summary": "Need one clarification",
            "open_questions": ["Which fixture should be prioritized?"],
            "findings": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "utility_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"utility_result payload should validate. Errors: {errors}")

    def test_validate_runtime_eval_export_row_schema(self):
        payload = {
            "run_id": "run-1",
            "event_id": "evt-1",
            "event_sequence": 1,
            "timestamp": "2026-02-13T00:00:00Z",
            "event_type": "SPAWN",
            "role": "Orchestrator",
            "phase_id": "phase-16a",
            "step_id": "m1-core-foundation",
            "capture_level": "summary",
            "prompt_artifact_ref": None,
            "prompt_sha256": None,
            "response_artifact_ref": None,
            "response_sha256": None,
            "artifact_ref": ".trinity/runtime/spawns/child-1/task_input.json",
            "artifact_sha256": "a" * 64,
            "diff_ref": None,
            "redaction_applied": False,
            "redaction_total_replacements": 0,
            "redaction_classes": [],
            "token_prompt": 100,
            "token_completion": 50,
            "token_total": 150,
            "event_sha256": "b" * 64,
            "prev_event_sha256": None
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "eval_export_row.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Eval export row should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_request_schema(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "exec_cmd",
            "args": {"command": "pytest -q", "mode": "summarized"},
            "working_dir": "/tmp/workspace",
            "timeout_seconds": 30,
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Tool call request should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_result_schema(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-1",
            "result_id": "result-1",
            "agent_id": "agent-root",
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "exec_cmd",
            "status": "success",
            "summary": "Command executed",
            "result": {"command": "pytest -q", "mode": "summarized"},
            "duration_ms": 1200,
            "exit_code": 0,
            "working_dir": "/tmp/workspace",
            "stdout_excerpt": "tests PASSED",
            "stderr_excerpt": "",
            "truncated": False,
            "artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
            "artifact_sha256": "a" * 64,
            "finished_at": "2026-02-13T00:00:02Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Tool call result should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_result_read_file_schema(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-2",
            "result_id": "result-2",
            "agent_id": "agent-root",
            "role": "Planner",
            "phase": "16a",
            "step_id": "m1-core-foundation",
            "tool_name": "read_file",
            "status": "success",
            "summary": "File read",
            "result": {
                "path": "spec/impl_context/m1-core-foundation.json",
                "line_start": 1,
                "line_end": 5,
                "bytes_read": 128,
                "content": "{\\n  \\\"id\\\": \\\"m1-core-foundation\\\"\\n}\\n",
                "truncated": False,
            },
            "duration_ms": 25,
            "truncated": False,
            "finished_at": "2026-02-13T00:00:02Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"read_file tool call result should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_result_apply_patch_schema(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-3",
            "result_id": "result-3",
            "agent_id": "agent-root",
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "apply_patch",
            "status": "success",
            "summary": "Patch applied",
            "result": {"files_changed": 1, "hunks_applied": 2},
            "duration_ms": 40,
            "artifact_ref": "src/example.py",
            "artifact_sha256": "a" * 64,
            "truncated": False,
            "finished_at": "2026-02-13T00:00:02Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"apply_patch tool call result should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_result_artifact_hash_pairing(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-1",
            "result_id": "result-1",
            "agent_id": "agent-root",
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "exec_cmd",
            "status": "success",
            "summary": "Command executed",
            "result": {"command": "pytest -q", "mode": "summarized"},
            "duration_ms": 1200,
            "exit_code": 0,
            "working_dir": "/tmp/workspace",
            "stdout_excerpt": "tests PASSED",
            "stderr_excerpt": "",
            "truncated": False,
            "artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
            "finished_at": "2026-02-13T00:00:02Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("artifact_sha256" in e for e in errors),
                f"Tool call result should fail when artifact_ref lacks artifact_sha256. Errors: {errors}",
            )

    def test_validate_runtime_tool_call_request_invalid_exec_cmd_args(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "exec_cmd",
            "args": {"command": "pytest -q"},
            "working_dir": "/tmp/workspace",
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("mode" in e for e in errors),
                f"Tool call request should fail when exec_cmd mode is missing. Errors: {errors}",
            )

    def test_validate_runtime_tool_call_request_checkpoint_branch_branch_name(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-branch-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Orchestrator",
            "phase": "16a",
            "step_id": "m1-core-foundation",
            "tool_name": "checkpoint_branch",
            "args": {"branch_name": "trinity/m1-core-foundation"},
            "working_dir": "/tmp/workspace",
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"checkpoint_branch request should validate with branch_name. Errors: {errors}")

    def test_validate_runtime_tool_call_request_search_text_use_regex(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-search-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "search_text",
            "args": {"pattern": "foo", "paths": ["README.md"], "use_regex": True},
            "working_dir": "/tmp/workspace",
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"search_text request should validate with use_regex. Errors: {errors}")

    def test_validate_runtime_tool_call_request_git_diff_base_head(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-diff-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "git_diff",
            "args": {"base_rev": "HEAD~1", "head_rev": "HEAD"},
            "working_dir": "/tmp/workspace",
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"git_diff request should validate with base/head rev keys. Errors: {errors}")

    def test_validate_runtime_tool_call_request_move_file(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-move-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "move_file",
            "args": {"src_path": "src/a.py", "dst_path": "src/b.py", "overwrite": True},
            "working_dir": "/tmp/workspace",
            "created_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_request.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"move_file request should validate. Errors: {errors}")

    def test_validate_runtime_tool_call_result_remove_file(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "call_id": "call-remove-1",
            "result_id": "result-remove-1",
            "agent_id": "agent-root",
            "role": "Builder",
            "phase": "16b",
            "step_id": "m1-core-foundation",
            "tool_name": "remove_file",
            "status": "success",
            "summary": "File removed",
            "result": {
                "path": "src/obsolete.py",
                "removed": True,
                "previously_missing": False,
            },
            "duration_ms": 12,
            "artifact_ref": "src/obsolete.py",
            "artifact_sha256": "a" * 64,
            "truncated": False,
            "finished_at": "2026-02-13T00:00:02Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tool_call_result.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"remove_file result should validate. Errors: {errors}")

    def test_validate_runtime_session_event_log_missing_validation_closure_fails(self):
        event = self._valid_session_event()
        with tempfile.TemporaryDirectory() as tmp:
            sessions_dir = os.path.join(tmp, ".trinity", "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            path = os.path.join(sessions_dir, "session.jsonl")
            terminate = self._valid_session_event()
            terminate["event_type"] = "TERMINATE"
            terminate["event_id"] = "evt-2"
            terminate["event_sequence"] = 2
            terminate["prev_event_sha256"] = event["event_sha256"]
            terminate["content"] = {
                "summary": "child completed",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_result_artifact_ref": ".trinity/runtime/spawns/child-1/task_result.json",
            }
            terminate["artifact_ref"] = ".trinity/runtime/spawns/child-1/task_result.json"
            terminate["artifact_sha256"] = "d" * 64
            terminate["event_sha256"] = self._event_sha256(terminate)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
                f.write(json.dumps(terminate) + "\n")
            errors = validate_runtime_file(self.repo_root, path)
            self.assertTrue(
                any("missing pass VALIDATION" in e for e in errors),
                f"Session log should fail when spawn/terminate transaction lacks validation closure. Errors: {errors}",
            )

    def test_validate_runtime_task_input_invalid_target_files_not_in_context_pack_patterns(self):
        task_input = self._valid_task_input_payload()
        context_pack = self._valid_context_pack_16a_for_task_input()
        context_pack["target_file_patterns"] = ["src/**"]
        context_pack["allowed_write_paths"] = ["src/"]
        with tempfile.TemporaryDirectory() as tmp:
            task_input_path = os.path.join(tmp, "task_input.json")
            context_pack_path = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "context_pack.json")
            self._write_json(task_input_path, task_input)
            self._write_json(context_pack_path, context_pack)
            errors = validate_runtime_file(self.repo_root, task_input_path)
            self.assertTrue(
                any("target_files entry" in e for e in errors),
                f"Task input should fail when target_files are not covered by context pack scope. Errors: {errors}",
            )

    def test_validate_runtime_task_input_step_id_mismatch_context_pack(self):
        task_input = self._valid_task_input_payload()
        context_pack = self._valid_context_pack_16a_for_task_input()
        context_pack["step_id"] = "m2-another-step"
        with tempfile.TemporaryDirectory() as tmp:
            task_input_path = os.path.join(tmp, "task_input.json")
            context_pack_path = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "context_pack.json")
            self._write_json(task_input_path, task_input)
            self._write_json(context_pack_path, context_pack)
            errors = validate_runtime_file(self.repo_root, task_input_path)
            self.assertTrue(
                any("does not match context_pack step_id" in e for e in errors),
                f"Task input should fail when step_id mismatches context pack. Errors: {errors}",
            )

    def test_validate_runtime_session_state(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "parent_id": "agent-root",
            "active_phase": "16b",
            "step_id": "m1-core-foundation",
            "status": "waiting_child",
            "pending_child_id": "child-9",
            "pending_spawn_ref": ".trinity/runtime/spawns/child-9/task_input.json",
            "spawn_log_ref": ".trinity/runtime/spawn_log.json",
            "scratchpad_ref": ".trinity/runtime/scratchpads/scratchpad_child-9.json",
            "last_event_id": "evt-10",
            "retry_counters": {"planner": 0, "builder": 1, "verifier": 0, "milestone": 1},
            "updated_at": "2026-02-13T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "session_state_parent-1.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Session state should validate. Errors: {errors}")

    def test_validate_runtime_spawn_log(self):
        payload = {
            "protocol_version": "trinity-runtime-v1",
            "run_id": "run-1",
            "entries": [
                {
                    "spawn_id": "spawn-1",
                    "parent_id": "agent-root",
                    "child_id": "child-1",
                    "purpose": "planner phase",
                    "phase": "16a",
                    "step_id": "m1-core-foundation",
                    "attempt": 1,
                    "status": "completed",
                    "task_input_ref": ".trinity/runtime/spawns/child-1/task_input.json",
                    "task_result_ref": ".trinity/runtime/spawns/child-1/task_result.json",
                    "created_at": "2026-02-13T00:00:00Z",
                    "updated_at": "2026-02-13T00:00:01Z",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spawn_log.json")
            self._write_json(path, payload)
            errors = validate_runtime_file(self.repo_root, path)
            self.assertEqual(errors, [], f"Spawn log should validate. Errors: {errors}")


if __name__ == "__main__":
    unittest.main()
