import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from specdev_tools.trinity_runtime import SessionLogger, ToolExecutor, TrinityConfig, TrinityRuntime, run_trinity
from specdev_tools.trinity_runtime_validate import validate_runtime_file
from specdev_tools.validate import validate_file


class TestTrinityRuntimeOrchestration(unittest.TestCase):
    def setUp(self):
        self.toolkit_root = str(Path(__file__).resolve().parents[2])

    def _write_json(self, path: str, payload: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")

    def _write_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _loop_checkpoint(self, label: str) -> dict:
        return {
            "draft": f"{label} draft evidence captured from grounded inputs.",
            "review": f"{label} review evidence confirms contract alignment.",
            "refine": f"{label} refine evidence captures final adjustments.",
        }

    def _init_git_repo(self, repo_root: str) -> None:
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Trinity Test"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "trinity-test@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo_root, check=True, capture_output=True, text=True)

    def _start_fake_openai_server(self):
        calls = []
        outer_self = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A003
                return

            def do_POST(self):  # noqa: N802
                raw_len = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(raw_len).decode("utf-8")
                payload = json.loads(raw)
                messages = payload.get("messages", []) if isinstance(payload.get("messages"), list) else []
                phase = "unknown"
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    if isinstance(candidate, dict) and isinstance(candidate.get("task_input"), dict):
                        maybe_phase = candidate["task_input"].get("phase")
                        if isinstance(maybe_phase, str) and maybe_phase:
                            phase = maybe_phase
                            break
                calls.append({"path": self.path, "phase": phase})

                response_payload = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1700000000,
                    "model": "input-model",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "action": "final_result",
                                        "summary": f"{phase} completed by fake llm",
                                        "loop_checkpoint": outer_self._loop_checkpoint(phase),
                                        "task_result": {
                                            "status": "success",
                                            "summary": f"{phase} success",
                                            "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                                        },
                                    }
                                ),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 48, "total_tokens": 168},
                }
                data = json.dumps(response_payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, calls

    def _start_scripted_openai_server(self, responder):
        calls = []
        state = {"turn": 0}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A003
                return

            def do_POST(self):  # noqa: N802
                raw_len = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(raw_len).decode("utf-8")
                payload = json.loads(raw)
                messages = payload.get("messages", []) if isinstance(payload.get("messages"), list) else []
                state["turn"] = int(state.get("turn", 0)) + 1
                reply = responder(messages, state)
                calls.append({"turn": state["turn"], "reply": reply})
                response_payload = {
                    "id": "chatcmpl-scripted",
                    "object": "chat.completion",
                    "created": 1700000000 + state["turn"],
                    "model": "input-model",
                    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(reply)}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 48, "total_tokens": 168},
                }
                data = json.dumps(response_payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, calls

    def _create_fixture_repo(
        self,
        repo_root: str,
        allow_dirty: bool = False,
        checkpoint_commits: bool = False,
        conformance_mode: Optional[bool] = None,
        execution_mode: str = "deterministic",
        preverified_artifact: bool = False,
        retry_cap_planner: int = 10,
        retry_cap_builder: int = 10,
        retry_cap_verifier: int = 10,
        retry_cap_milestone: int = 10,
    ) -> None:
        shutil.copytree(os.path.join(self.toolkit_root, "schema"), os.path.join(repo_root, "schema"))
        shutil.copytree(os.path.join(self.toolkit_root, "prompts"), os.path.join(repo_root, "prompts"))
        os.makedirs(os.path.join(repo_root, "tools"), exist_ok=True)
        shutil.copy2(
            os.path.join(self.toolkit_root, "tools", "schema_registry.json"),
            os.path.join(repo_root, "tools", "schema_registry.json"),
        )

        self._write_text(os.path.join(repo_root, "docs", "seed", "seed_overview.md"), "# overview\n")
        self._write_text(os.path.join(repo_root, "docs", "seed", "seed_tech_stack.md"), "# tech stack\n")
        self._write_text(os.path.join(repo_root, "README.md"), "Fixture repository for Trinity runtime.\n")

        self._write_json(
            os.path.join(repo_root, "spec", "common", "seed_manifest.json"),
            {
                "$schema": "https://specdev.local/schema/seed_manifest.schema.json",
                "seed_manifest_id": "seed-manifest-core",
                "version": "0.1.0",
                "created_at": "2026-02-07T00:00:00Z",
                "last_updated": "2026-02-07T00:00:00Z",
                "global_seed_order": ["seed-overview", "seed-tech-stack"],
                "seeds": [
                    {"seed_id": "seed-overview", "path": "docs/seed/seed_overview.md", "required": True, "source_type": "doc"},
                    {"seed_id": "seed-tech-stack", "path": "docs/seed/seed_tech_stack.md", "required": True, "source_type": "doc"},
                ],
                "step_requirements": {
                    "16a": ["seed-overview", "seed-tech-stack"],
                    "16b": ["seed-overview", "seed-tech-stack"],
                    "16c": ["seed-overview", "seed-tech-stack"],
                },
                "docs_policy": {
                    "readme_required": True,
                    "root_readme_required": True,
                    "scope": ["."],
                    "exclusions": [".git/"],
                    "doc_paths": ["docs/**", "README.md", "CHANGELOG.md"],
                },
            },
        )

        interface_contracts_path = os.path.join(repo_root, "spec", "05_interface_contracts.json")
        self._write_json(
            interface_contracts_path,
            {
                "$schema": "https://specdev.local/schema/05_interface_contracts.schema.json",
                "id": "interface-contracts",
                "owner": "api",
                "created_at": "2025-01-01T00:00:00Z",
                "seed_refs": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}],
                "apis": [
                    {
                        "api_id": "api-trinity-bootstrap",
                        "name": "Trinity Bootstrap",
                        "version": "v1",
                        "protocol": "http",
                        "route": "/trinity",
                        "method": "GET",
                        "owner": "api",
                    }
                ],
            },
        )
        with open(interface_contracts_path, "r", encoding="utf-8") as f:
            contract_lines = f.readlines()
        interface_id_line = 1
        for idx, line in enumerate(contract_lines, start=1):
            if '"id": "interface-contracts"' in line:
                interface_id_line = idx
                break
        interface_id_range = f"L{interface_id_line}-L{interface_id_line}"

        self._write_json(
            os.path.join(repo_root, "spec", "14_roadmap.json"),
            {
                "$schema": "https://specdev.local/schema/14_roadmap.schema.json",
                "id": "roadmap-core",
                "owner": "api",
                "created_at": "2026-02-10T00:00:00Z",
                "seed_refs": [{"seed_id": "seed-overview"}],
                "tech_stack": {"languages": [{"name": "python", "version": "3.11"}], "frameworks": [{"name": "stdlib", "version": "1"}]},
                "milestones": [
                    {
                        "milestone_id": "m1-core-foundation",
                        "name": "Core Foundation",
                        "target_date": "2026-03-01",
                        "status": "pending",
                        "user_story": "As an engineer, I can run Trinity on one milestone.",
                        "source_milestones": ["m0-source"],
                        "tasks": [{"task_id": "task-bootstrap", "description": "bootstrap milestone context"}],
                        "deliverables": [{"type": "api", "id": "interface-contracts"}],
                    }
                ],
                "dependencies": [],
            },
        )

        if conformance_mode is None:
            conformance_mode = bool(checkpoint_commits)
        self._write_text(
            os.path.join(repo_root, ".trinity", "trinity.yaml"),
            (
                "llm:\n"
                "  api_base: \"http://localhost:1234/v1\"\n"
                "  model: \"input-model\"\n"
                "  timeout: 300\n\n"
                "limits:\n"
                "  soft_token_limit: 60000\n"
                "  hard_token_limit: 80000\n"
                f"  max_loops: {retry_cap_milestone}\n\n"
                "runtime:\n"
                f"  allow_dirty: {'true' if allow_dirty else 'false'}\n"
                f"  checkpoint_commits: {'true' if checkpoint_commits else 'false'}\n"
                f"  conformance_mode: {'true' if conformance_mode else 'false'}\n"
                f"  execution_mode: \"{execution_mode}\"\n"
                "  max_child_turns: 6\n"
                "  retry_caps:\n"
                f"    planner: {retry_cap_planner}\n"
                f"    builder: {retry_cap_builder}\n"
                f"    verifier: {retry_cap_verifier}\n"
                f"    milestone: {retry_cap_milestone}\n"
            ),
        )

        self._init_git_repo(repo_root)
        base_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        smoke_cmd = "python3 -c \"print('SUCCESS TRINITY_OK evidence marker')\""
        evidence = "SUCCESS TRINITY_OK evidence marker"
        evidence_sha = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        implementation_status = "verified" if preverified_artifact else "pending"
        run_action_evidence = (
            {"type": "snippet", "content": evidence, "evidence_ref": f"sha256:{evidence_sha}"}
            if preverified_artifact
            else None
        )
        verify_action_evidence = (
            {"type": "snippet", "content": evidence, "evidence_ref": f"sha256:{evidence_sha}"}
            if preverified_artifact
            else None
        )
        execution_block = (
            {
                "files_touched": ["README.md"],
                "execution_results": [
                    {
                        "status": "passed",
                        "outcome_description": "Command passed",
                        "reasoning": "Pre-seeded execution evidence for llm mode fixture.",
                        "command": smoke_cmd,
                        "evidence": evidence,
                        "evidence_ref": f"sha256:{evidence_sha}",
                        "evidence_binding": {
                            "timestamp": "2026-02-13T00:00:00Z",
                            "sha256": evidence_sha,
                            "exit_code": 0,
                            "command": smoke_cmd,
                        },
                    }
                ],
                "critical_evidence": {
                    "satisfied_checklist_ids": ["CHK_TRINITY_RUNTIME_001"],
                    "passed_test_commands": [smoke_cmd],
                },
            }
            if preverified_artifact
            else None
        )
        review_block = (
            {
                "findings": [],
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
                    "test_results": [{"fixture_ref": "fixture-trinity-runtime-smoke", "status": "pass"}],
                    "ci_status": "green",
                },
            }
            if preverified_artifact
            else None
        )
        self._write_json(
            os.path.join(repo_root, "spec", "impl_context", "m1-core-foundation.json"),
            {
                "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
                "id": "m1-core-foundation",
                "owner": "api",
                "created_at": "2026-02-10T00:00:00Z",
                "seed_refs": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}],
                "plan": {
                    "status": "active",
                    "summary": {
                        "functional_summary": "Execute deterministic Trinity vertical-slice implementation checks.",
                        "scope_in": ["milestone execution lifecycle"],
                        "scope_out": ["cross-milestone feature work"],
                        "target_file_patterns": ["docs/**", "README.md", "spec/impl_context/*.json", "spec/16_impl_context.json"],
                    },
                    "docs_impact": {
                        "status": "required",
                        "rationale": "Step 16 contract requires docs impact tracking for non-doc target scope.",
                        "docs_touched": ["README.md"],
                    },
                    "spec_alignment": {
                        "checklist": [
                            {
                                "id": "CHK_TRINITY_RUNTIME_001",
                                "spec_ref": {
                                    "type": "api",
                                    "id": "interface-contracts",
                                    "line_range": interface_id_range,
                                    "commit_hash": base_commit,
                                },
                                "description": "Builder executes deterministic smoke command and binds evidence for verification.",
                                "type": "validation",
                                "layer": "integration",
                                "checklist_status": "active",
                                "linked_test_expectation": smoke_cmd,
                                "nfr_refs": ["nfr-runtime-determinism"],
                                "fixture_ref": "fixture-trinity-runtime-smoke",
                                "implementation": {
                                    "status": implementation_status,
                                    "actions": [
                                        {
                                            "type": "run_command",
                                            "description": "Execute deterministic smoke command with explicit success marker.",
                                            "command": smoke_cmd,
                                            **({"evidence": run_action_evidence} if run_action_evidence else {}),
                                        },
                                        {
                                            "type": "manual_verification",
                                            "description": "Bind manual verification to command evidence for checklist closure.",
                                            **({"evidence": verify_action_evidence} if verify_action_evidence else {}),
                                        },
                                    ],
                                },
                            }
                        ]
                    },
                    "review_requirements": {
                        "guidelines": "Require explicit success marker evidence for all passed command outputs.",
                        "test_commands": [smoke_cmd],
                    },
                    "solution": {
                        "architecture_sketch": "Single-checklist deterministic runtime validation plan.",
                        "sequence_of_concerns": ["16a", "16b", "16c"],
                        "risks": ["false positives if evidence markers are not enforced"],
                    },
                },
                **({"execution": execution_block} if execution_block else {}),
                **({"review": review_block} if review_block else {}),
            },
        )
        subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "milestone fixture"], cwd=repo_root, check=True, capture_output=True, text=True)

    def test_run_trinity_full_runtime_vertical_slice(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False)
            result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")

            self.assertEqual(result.get("status"), "completed", result)
            self.assertEqual(result.get("step_id"), "m1-core-foundation")
            self.assertEqual(result.get("verdict"), "verified")

            milestone_path = os.path.join(tmp, result["milestone_artifact"])
            anchor_path = os.path.join(tmp, result["anchor_artifact"])
            session_path = os.path.join(tmp, result["session_log"])

            self.assertTrue(os.path.exists(milestone_path), "Milestone artifact should be created")
            self.assertTrue(os.path.exists(anchor_path), "Anchor artifact should be created")
            self.assertTrue(os.path.exists(session_path), "Session log should be created")

            milestone_errors = validate_file(tmp, milestone_path)
            self.assertEqual(milestone_errors, [], f"Milestone artifact must pass Step 16 validation: {milestone_errors}")

            session_errors = validate_runtime_file(tmp, session_path, "session_event")
            self.assertEqual(session_errors, [], f"Session log must pass runtime validation: {session_errors}")

            with open(os.path.join(tmp, "spec", "14_roadmap.json"), "r", encoding="utf-8") as f:
                roadmap = json.load(f)
            milestone = roadmap["milestones"][0]
            self.assertEqual(milestone.get("status"), "done", "Roadmap milestone should be synced to done on verified closure")

    def test_run_trinity_blocks_on_dirty_tree_when_not_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False)
            self._write_text(os.path.join(tmp, "notes.txt"), "dirty\n")
            with self.assertRaises(RuntimeError):
                run_trinity(repo_root=tmp, step_id="m1-core-foundation")

    def test_cli_trinity_command_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False)
            cmd = [
                sys.executable,
                "-m",
                "specdev_tools.cli",
                "trinity",
                "--step-id",
                "m1-core-foundation",
                "--repo-root",
                tmp,
                "--json",
            ]
            env = os.environ.copy()
            current = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                os.path.join(self.toolkit_root, "tools")
                if not current
                else os.path.join(self.toolkit_root, "tools") + os.pathsep + current
            )
            env["SPECDEV_SKIP_VENV_CHECK"] = "1"
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("status"), "completed", payload)
            self.assertEqual(payload.get("step_id"), "m1-core-foundation")

    def test_run_trinity_fallback_step_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False)
            result = run_trinity(repo_root=tmp, step_id=None)
            self.assertEqual(result.get("status"), "completed", result)
            self.assertEqual(result.get("step_id"), "m1-core-foundation")

    def test_run_trinity_with_checkpoints_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            config = TrinityConfig.load(tmp)
            runtime = TrinityRuntime(tmp, config, step_id="m1-core-foundation")
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16a",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["."],
                enable_checkpoints=False,
            )
            runtime._ensure_branch(tools)
            request_path = os.path.join(tmp, ".trinity", "runtime", "tools", "tool_call_request.json")
            with open(request_path, "r", encoding="utf-8") as f:
                request = json.load(f)
            self.assertEqual(request.get("tool_name"), "checkpoint_branch")
            self.assertEqual(request.get("args", {}).get("branch_name"), "trinity/m1-core-foundation")

    def test_exec_cmd_blocks_secret_dump_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16c",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["."],
                enable_checkpoints=False,
            )
            blocked = tools.call(
                "exec_cmd",
                {"command": "printenv", "mode": "summarized", "timeout_seconds": 30},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(blocked.get("status"), "blocked", blocked)
            self.assertEqual((blocked.get("error") or {}).get("code"), "blocked", blocked)

            blocked_env = tools.call(
                "exec_cmd",
                {"command": "env", "mode": "summarized", "timeout_seconds": 30},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(blocked_env.get("status"), "blocked", blocked_env)
            self.assertEqual((blocked_env.get("error") or {}).get("code"), "blocked", blocked_env)

    def test_exec_cmd_blocks_redirection_in_readonly_phases(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16c",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["."],
                enable_checkpoints=False,
            )
            blocked = tools.call(
                "exec_cmd",
                {"command": "echo blocked > /tmp/trinity_scope_probe.txt", "mode": "summarized", "timeout_seconds": 30},
                role="Verifier",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(blocked.get("status"), "blocked", blocked)
            self.assertEqual((blocked.get("error") or {}).get("code"), "blocked", blocked)

    def test_path_allowlist_rejects_parent_traversal_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16b",
                step_id="m1-core-foundation",
                allowed_read_paths=[".trinity", "spec"],
                allowed_write_paths=["spec/impl_context"],
                enable_checkpoints=False,
            )
            self.assertFalse(tools._is_allowed_path("../.trinity/secrets.txt", [".trinity"]))
            self.assertFalse(tools._is_allowed_path("../../spec/14_roadmap.json", ["spec"]))

    def test_write_file_append_reports_resulting_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16b",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["spec/impl_context"],
                enable_checkpoints=False,
            )
            seed_path = os.path.join(tmp, "spec", "impl_context", "append_hash.txt")
            self._write_text(seed_path, "A")
            result = tools.call(
                "write_file",
                {"path": "spec/impl_context/append_hash.txt", "content": "B", "mode": "append"},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(result.get("status"), "success", result)
            with open(seed_path, "rb") as f:
                expected_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(result.get("artifact_sha256"), f"sha256:{expected_sha}", result)

    def test_apply_patch_reports_artifact_hash_for_patched_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16b",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["spec/impl_context"],
                enable_checkpoints=False,
            )
            target = os.path.join(tmp, "spec", "impl_context", "patch_hash.txt")
            self._write_text(target, "old line\n")
            patch = (
                "--- a/spec/impl_context/patch_hash.txt\n"
                "+++ b/spec/impl_context/patch_hash.txt\n"
                "@@ -1 +1 @@\n"
                "-old line\n"
                "+new line\n"
            )
            result = tools.call(
                "apply_patch",
                {"patch": patch},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(result.get("status"), "success", result)
            with open(target, "rb") as f:
                expected_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(result.get("artifact_ref"), "spec/impl_context/patch_hash.txt", result)
            self.assertEqual(result.get("artifact_sha256"), f"sha256:{expected_sha}", result)

    def test_move_file_and_remove_file_report_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            tools = ToolExecutor(
                tmp,
                logger,
                "run-test",
                agent_id="orchestrator-test",
                phase="16b",
                step_id="m1-core-foundation",
                allowed_read_paths=["."],
                allowed_write_paths=["spec/impl_context"],
                enable_checkpoints=False,
            )
            src = os.path.join(tmp, "spec", "impl_context", "move_src.txt")
            dst = os.path.join(tmp, "spec", "impl_context", "move_dst.txt")
            self._write_text(src, "moved-by-trinity\n")
            moved = tools.call(
                "move_file",
                {"src_path": "spec/impl_context/move_src.txt", "dst_path": "spec/impl_context/move_dst.txt"},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(moved.get("status"), "success", moved)
            self.assertFalse(os.path.exists(src), "move_file should remove source path")
            self.assertTrue(os.path.exists(dst), "move_file should create destination path")
            with open(dst, "rb") as f:
                moved_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(moved.get("artifact_ref"), "spec/impl_context/move_dst.txt", moved)
            self.assertEqual(moved.get("artifact_sha256"), f"sha256:{moved_sha}", moved)

            removed = tools.call(
                "remove_file",
                {"path": "spec/impl_context/move_dst.txt"},
                role="Builder",
                parent_id="orchestrator-test",
                loop_id="l3",
            )
            self.assertEqual(removed.get("status"), "success", removed)
            self.assertFalse(os.path.exists(dst), "remove_file should delete destination path")
            self.assertEqual(removed.get("artifact_ref"), "spec/impl_context/move_dst.txt", removed)
            self.assertEqual(removed.get("artifact_sha256"), f"sha256:{moved_sha}", removed)

    def test_capture_artifact_hash_matches_written_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            rel, sha = logger._write_capture_artifact(event_id="evt-hash", kind="prompt", content="capture-content")
            abs_path = os.path.join(tmp, rel)
            with open(abs_path, "rb") as f:
                expected_sha = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(sha, expected_sha)

    def test_session_logger_rejects_invalid_event_before_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False, checkpoint_commits=False)
            logger = SessionLogger(tmp, "run-test", "orchestrator-test", "m1-core-foundation", "input-model")
            with self.assertRaises(RuntimeError):
                logger.append(
                    "MESSAGE",
                    role="InvalidRole",
                    phase_id="16a",
                    loop_id="l1",
                    agent_id="orchestrator-test",
                    parent_id=None,
                    summary="invalid role test",
                    prompt_template_id="prompt_16a",
                    step_id="m1-core-foundation",
                )
            self.assertTrue(os.path.exists(logger.path), "Session log file should exist")
            self.assertEqual(os.path.getsize(logger.path), 0, "Invalid event must not be persisted")

    def test_run_trinity_sets_capture_policy_fallback_metadata_for_incomplete_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=True, checkpoint_commits=False, execution_mode="deterministic")
            self._write_json(
                os.path.join(tmp, ".trinity", "logging", "log_capture_policy.json"),
                {
                    "policy_id": "legacy-policy",
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
                        "ERROR": 0.0,
                    },
                    "max_full_events_per_run": 4,
                    "oversize_fallback": "summary",
                    "full_capture_allowlist_roles": [],
                    "require_redaction_before_full": True,
                },
            )
            result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(result.get("status"), "completed", result)

            session_path = os.path.join(tmp, result["session_log"])
            with open(session_path, "r", encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
            fallback_events = [
                e for e in events
                if isinstance(e.get("metadata"), dict) and e["metadata"].get("capture_policy_fallback_applied") is True
            ]
            self.assertTrue(fallback_events, "Expected capture_policy_fallback_applied=true when policy profile is incomplete")

    def test_run_trinity_resume_from_latest_session_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(tmp, allow_dirty=False)
            first = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(first.get("status"), "completed", first)
            resumed = run_trinity(repo_root=tmp, step_id=None, resume=True)
            self.assertEqual(resumed.get("status"), "completed", resumed)
            self.assertEqual(resumed.get("step_id"), "m1-core-foundation")

    def test_run_trinity_llm_mode_openai_compatible_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )
            server, thread, calls = self._start_fake_openai_server()
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)

                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "completed", result)
                self.assertEqual(result.get("execution_mode"), "llm", result)
                phases = {entry["phase"] for entry in calls}
                self.assertTrue({"16a", "16b", "16c"}.issubset(phases), calls)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_session_log_aggregates_child_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )
            server, thread, _calls = self._start_fake_openai_server()
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)

                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "completed", result)
                session_log_path = os.path.join(tmp, result["session_log"])
                with open(session_log_path, "r", encoding="utf-8") as f:
                    events = [json.loads(line) for line in f if line.strip()]

                self.assertTrue(events, "Session log should contain events")
                self.assertTrue(
                    any(e.get("event_type") == "MESSAGE" and e.get("role") in {"Planner", "Builder", "Verifier"} for e in events),
                    "Canonical session log should include child MESSAGE events",
                )
                self.assertTrue(
                    all(e.get("run_id") == result.get("run_id") for e in events if isinstance(e, dict)),
                    "All events in canonical session log should share one run_id",
                )

                sessions_dir = os.path.join(tmp, ".trinity", "sessions")
                session_files = [name for name in os.listdir(sessions_dir) if name.endswith(".jsonl")]
                self.assertEqual(len(session_files), 1, session_files)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_llm_mode_supports_utility_role_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )
            state = {"utility_called": False}

            def _phase_and_role(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    task_input = candidate.get("task_input")
                    if isinstance(task_input, dict):
                        maybe_phase = task_input.get("phase")
                        maybe_role = task_input.get("role")
                        if isinstance(maybe_phase, str) and maybe_phase:
                            return maybe_phase, maybe_role if isinstance(maybe_role, str) else None
                    maybe_phase = candidate.get("phase")
                    maybe_role = candidate.get("role")
                    if isinstance(maybe_phase, str) and maybe_phase:
                        return maybe_phase, maybe_role if isinstance(maybe_role, str) else None
                return "16a", None

            def responder(messages, _state):
                phase, role = _phase_and_role(messages)
                if phase == "utility" and role == "Researcher":
                    return {
                        "action": "final_result",
                        "summary": "research ready",
                        "loop_checkpoint": self._loop_checkpoint("utility-researcher"),
                        "utility_result": {
                            "status": "ready",
                            "summary": "Grounded context collected",
                            "open_questions": [],
                            "findings": [],
                        },
                    }
                if phase == "16a":
                    if not state["utility_called"]:
                        state["utility_called"] = True
                        return {
                            "action": "utility_call",
                            "summary": "run researcher utility",
                            "utility_call": {
                                "role": "Researcher",
                                "objective": "Collect grounded references for planner stage",
                                "input": {"required_outputs": ["findings", "recommended_spec_refs"]},
                            },
                        }
                    return {
                        "action": "final_result",
                        "summary": "16a success",
                        "loop_checkpoint": self._loop_checkpoint("16a"),
                        "task_result": {
                            "status": "success",
                            "summary": "16a success",
                            "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                        },
                    }
                return {
                    "action": "final_result",
                    "summary": f"{phase} success",
                    "loop_checkpoint": self._loop_checkpoint(phase),
                    "task_result": {
                        "status": "success",
                        "summary": f"{phase} success",
                        "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                    },
                }

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)

                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "completed", result)
                self.assertTrue(state["utility_called"], "Planner should invoke utility role before final_result")

                session_path = os.path.join(tmp, result["session_log"])
                with open(session_path, "r", encoding="utf-8") as f:
                    events = [json.loads(line) for line in f if line.strip()]
                researcher_events = [e for e in events if e.get("role") == "Researcher" and e.get("phase_id") == "utility"]
                self.assertTrue(researcher_events, "Utility role events should be present in session log")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_llm_mode_blocks_malformed_utility_result_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )

            state = {"utility_called": False}

            def _phase_and_role(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    task_input = candidate.get("task_input")
                    if isinstance(task_input, dict):
                        phase = task_input.get("phase")
                        role = task_input.get("role")
                        if isinstance(phase, str):
                            return phase, role if isinstance(role, str) else None
                    phase = candidate.get("phase")
                    role = candidate.get("role")
                    if isinstance(phase, str):
                        return phase, role if isinstance(role, str) else None
                return "16a", None

            def _has_utility_feedback(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    if isinstance(candidate, dict) and isinstance(candidate.get("utility_result"), dict):
                        return True
                return False

            def responder(messages, _state):
                phase, role = _phase_and_role(messages)
                if phase == "utility" and role == "Researcher":
                    return {
                        "action": "final_result",
                        "summary": "malformed utility result",
                        "loop_checkpoint": self._loop_checkpoint("utility-researcher"),
                        "utility_result": {
                            "summary": "missing status should fail schema"
                        },
                    }
                if phase == "16a":
                    if not state["utility_called"]:
                        state["utility_called"] = True
                        return {
                            "action": "utility_call",
                            "summary": "run researcher utility",
                            "utility_call": {
                                "role": "Researcher",
                                "objective": "Collect references",
                                "input": {"required_outputs": ["findings"]},
                            },
                        }
                    if _has_utility_feedback(messages):
                        return {
                            "action": "final_result",
                            "summary": "planner blocked by malformed utility result",
                            "loop_checkpoint": self._loop_checkpoint("16a"),
                            "task_result": {
                                "status": "blocked",
                                "summary": "utility payload invalid",
                                "artifacts": [],
                                "findings": [
                                    {
                                        "id": "planner-utility-result-invalid",
                                        "type": "policy",
                                        "severity": "blocking",
                                        "description": "Utility result schema validation failed.",
                                        "source": "Planner",
                                        "impact": "Planner cannot continue",
                                    }
                                ],
                            },
                        }
                return {
                    "action": "final_result",
                    "summary": f"{phase} success",
                    "loop_checkpoint": self._loop_checkpoint(phase),
                    "task_result": {
                        "status": "success",
                        "summary": f"{phase} success",
                        "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                    },
                }

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)

                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertIn(result.get("status"), {"blocked", "completed"}, result)

                session_path = os.path.join(tmp, result["session_log"])
                with open(session_path, "r", encoding="utf-8") as f:
                    events = [json.loads(line) for line in f if line.strip()]
                fail_events = [
                    e for e in events
                    if e.get("event_type") == "VALIDATION"
                    and e.get("role") == "Researcher"
                    and "utility_result schema fail" in (e.get("content", {}).get("summary", ""))
                ]
                self.assertTrue(fail_events, "Expected utility_result schema fail validation event for malformed payload")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_fresh_run_resets_spawn_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
            )

            first = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(first.get("status"), "completed", first)

            second = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(second.get("status"), "completed", second)

            spawn_log_path = os.path.join(tmp, ".trinity", "runtime", "spawn_log.json")
            with open(spawn_log_path, "r", encoding="utf-8") as f:
                spawn_log = json.load(f)

            self.assertEqual(spawn_log.get("run_id"), second.get("run_id"))
            entries = spawn_log.get("entries", [])
            self.assertTrue(entries, "spawn_log should contain entries for the latest run")
            attempts = [int(e.get("attempt", 0)) for e in entries if isinstance(e, dict)]
            self.assertTrue(all(attempt == 1 for attempt in attempts), attempts)

    def test_run_trinity_bootstraps_missing_milestone_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
            )
            milestone_path = os.path.join(tmp, "spec", "impl_context", "m1-core-foundation.json")
            os.remove(milestone_path)

            result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(result.get("status"), "completed", result)
            self.assertTrue(os.path.exists(milestone_path), "Planner bootstrap should recreate missing milestone artifact")

            with open(milestone_path, "r", encoding="utf-8") as f:
                milestone = json.load(f)
            checklist = milestone.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
            self.assertTrue(isinstance(checklist, list) and checklist, "Bootstrapped milestone should include checklist contract")
            spawn_root = os.path.join(tmp, ".trinity", "runtime", "spawns")
            context_paths = []
            if os.path.isdir(spawn_root):
                for child in os.listdir(spawn_root):
                    candidate = os.path.join(spawn_root, child, "context_pack.json")
                    if os.path.exists(candidate):
                        context_paths.append(candidate)
            self.assertTrue(context_paths, "Expected planner spawn context pack artifacts")
            planner_context = None
            for candidate in sorted(context_paths):
                with open(candidate, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("phase") == "16a":
                    planner_context = loaded
                    break
            self.assertIsInstance(planner_context, dict, "Expected a 16a planner context pack artifact")
            trace = planner_context.get("bootstrap_ref_trace")
            self.assertTrue(isinstance(trace, list) and trace, "Planner bootstrap should emit bootstrap_ref_trace explainability")

    def test_run_trinity_emits_anchor_union_metrics_validation_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
            )
            result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(result.get("status"), "completed", result)

            session_path = os.path.join(tmp, result["session_log"])
            with open(session_path, "r", encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]

            union_events = [
                e for e in events
                if e.get("event_type") == "VALIDATION"
                and isinstance(e.get("metadata"), dict)
                and isinstance(e["metadata"].get("anchor_union_metrics"), dict)
            ]
            self.assertTrue(union_events, "Expected VALIDATION event with anchor_union_metrics metadata")
            metrics = union_events[-1]["metadata"]["anchor_union_metrics"]
            self.assertGreaterEqual(metrics.get("active_contexts", -1), 1, metrics)
            self.assertIn("checklist_conflicts_count", metrics)

    def test_run_trinity_retry_caps_are_driven_by_yaml_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
                retry_cap_planner=2,
                retry_cap_builder=10,
                retry_cap_verifier=10,
                retry_cap_milestone=10,
            )
            os.remove(os.path.join(tmp, "spec", "05_interface_contracts.json"))

            result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(result.get("status"), "blocked", result)
            self.assertEqual(result.get("phase"), "16a", result)

            config = TrinityConfig.load(tmp)
            self.assertEqual(config.retry_cap_planner, 2)

            spawn_log_path = os.path.join(tmp, ".trinity", "runtime", "spawn_log.json")
            with open(spawn_log_path, "r", encoding="utf-8") as f:
                spawn_log = json.load(f)
            attempts = [
                int(e.get("attempt", 0))
                for e in spawn_log.get("entries", [])
                if isinstance(e, dict) and e.get("phase") == "16a"
            ]
            self.assertEqual(sorted(set(attempts)), [1, 2], attempts)

    def test_run_trinity_child_timeouts_are_driven_by_yaml_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
            )
            config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
            with open(config_path, "a", encoding="utf-8") as f:
                f.write("  child_timeout_seconds: 7200\n")
                f.write("  child_timeout_by_phase:\n")
                f.write("    16a: 1200\n")
                f.write("    16b: 14400\n")
                f.write("    16c: 3600\n")
                f.write("  allow_bootstrap_authority_fallback: true\n")
                f.write("  allow_anchor_conflicts: true\n")

            config = TrinityConfig.load(tmp)
            runtime = TrinityRuntime(tmp, config, step_id="m1-core-foundation")
            self.assertEqual(config.child_timeout_seconds, 7200)
            self.assertEqual(config.child_timeout_by_phase.get("16b"), 14400)
            self.assertTrue(config.allow_bootstrap_authority_fallback)
            self.assertTrue(config.allow_anchor_conflicts)
            self.assertEqual(runtime._child_timeout_for_phase("16a"), 1200)
            self.assertEqual(runtime._child_timeout_for_phase("16b"), 14400)
            self.assertEqual(runtime._child_timeout_for_phase("utility"), 7200)

    def test_run_trinity_terminal_questions_path_runs_session_log_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )

            def responder(_messages, _state):
                return {
                    "action": "final_result",
                    "summary": "Need clarification",
                    "loop_checkpoint": self._loop_checkpoint("16a"),
                    "task_result": {
                        "status": "questions",
                        "summary": "Clarification required",
                        "artifacts": [],
                        "questions": ["Confirm scope."],
                    },
                }

            def _validate_with_session_error(_repo_root, _path, schema_type):
                if schema_type == "session_event":
                    return ["forced terminal session log validation failure"]
                return []

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)
                with patch("specdev_tools.trinity_runtime.validate_runtime_file", side_effect=_validate_with_session_error):
                    result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "blocked", result)
                self.assertEqual(result.get("phase"), "session_log", result)
                self.assertTrue(any("forced terminal session log validation failure" in e for e in result.get("errors", [])), result)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_terminal_blocked_path_runs_session_log_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="deterministic",
                preverified_artifact=False,
                retry_cap_planner=1,
                retry_cap_builder=1,
                retry_cap_verifier=1,
                retry_cap_milestone=1,
            )
            os.remove(os.path.join(tmp, "spec", "05_interface_contracts.json"))

            def _validate_with_session_error(_repo_root, _path, schema_type):
                if schema_type == "session_event":
                    return ["forced terminal session log validation failure"]
                return []

            with patch("specdev_tools.trinity_runtime.validate_runtime_file", side_effect=_validate_with_session_error):
                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
            self.assertEqual(result.get("status"), "blocked", result)
            self.assertEqual(result.get("phase"), "session_log", result)
            self.assertTrue(any("forced terminal session log validation failure" in e for e in result.get("errors", [])), result)

    def test_run_trinity_llm_mode_tool_call_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )

            def _phase_from_messages(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    if isinstance(candidate, dict) and isinstance(candidate.get("task_input"), dict):
                        maybe_phase = candidate["task_input"].get("phase")
                        if isinstance(maybe_phase, str):
                            return maybe_phase
                return "16a"

            def _has_tool_result(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    if isinstance(candidate, dict) and isinstance(candidate.get("tool_result"), dict):
                        return True
                return False

            def responder(messages, _state):
                phase = _phase_from_messages(messages)
                if _has_tool_result(messages):
                    return {
                        "action": "final_result",
                        "summary": f"{phase} success after tool loop",
                        "loop_checkpoint": self._loop_checkpoint(phase),
                        "task_result": {
                            "status": "success",
                            "summary": f"{phase} success",
                            "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                        },
                    }
                return {
                    "action": "tool_call",
                    "summary": f"{phase} inspect milestone artifact",
                    "tool_call": {
                        "tool_name": "read_file",
                        "args": {"path": "spec/impl_context/m1-core-foundation.json", "start_line": 1, "end_line": 5},
                    },
                }

            server, thread, calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)
                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "completed", result)
                self.assertEqual(result.get("execution_mode"), "llm", result)
                self.assertGreaterEqual(len(calls), 6, calls)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_llm_mode_questions_resume_with_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )

            def _phase_and_desc(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    task_input = candidate.get("task_input")
                    if isinstance(task_input, dict):
                        phase = task_input.get("phase")
                        desc = task_input.get("task_description", "")
                        if isinstance(phase, str):
                            return phase, str(desc)
                return "16a", ""

            def responder(messages, _state):
                phase, desc = _phase_and_desc(messages)
                if phase == "16a" and "User clarifications:" not in desc:
                    return {
                        "action": "final_result",
                        "summary": "Need clarification",
                        "loop_checkpoint": self._loop_checkpoint("16a"),
                        "task_result": {
                            "status": "questions",
                            "summary": "Clarification required",
                            "artifacts": [],
                            "questions": ["Confirm scope for m1-core-foundation implementation loop."],
                        },
                    }
                return {
                    "action": "final_result",
                    "summary": f"{phase} success",
                    "loop_checkpoint": self._loop_checkpoint(phase),
                    "task_result": {
                        "status": "success",
                        "summary": f"{phase} success",
                        "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                    },
                }

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)

                first = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(first.get("status"), "questions", first)
                self.assertEqual(first.get("phase"), "16a", first)
                self.assertTrue(first.get("questions"), first)

                resumed = run_trinity(
                    repo_root=tmp,
                    step_id=None,
                    resume=True,
                    answers=["Stay within the existing milestone plan and target files."],
                )
                self.assertEqual(resumed.get("status"), "completed", resumed)
                sessions_dir = os.path.join(tmp, ".trinity", "sessions")
                session_files = [name for name in os.listdir(sessions_dir) if name.endswith(".jsonl")]
                self.assertEqual(len(session_files), 1, session_files)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_llm_mode_blocks_out_of_scope_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )
            seen = {"blocked_tool_result": False}

            def _phase(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    task_input = candidate.get("task_input")
                    if isinstance(task_input, dict):
                        maybe_phase = task_input.get("phase")
                        if isinstance(maybe_phase, str):
                            return maybe_phase
                return "16a"

            def _tool_result_status(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    tool_result = candidate.get("tool_result")
                    if isinstance(tool_result, dict):
                        return tool_result.get("status")
                return None

            def responder(messages, _state):
                phase = _phase(messages)
                if phase == "16a":
                    return {
                        "action": "final_result",
                        "summary": "16a success",
                        "loop_checkpoint": self._loop_checkpoint("16a"),
                        "task_result": {
                            "status": "success",
                            "summary": "16a success",
                            "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                        },
                    }
                if phase == "16b":
                    status = _tool_result_status(messages)
                    if status:
                        seen["blocked_tool_result"] = (status == "blocked")
                        return {
                            "action": "final_result",
                            "summary": "16b blocked on out-of-scope write",
                            "loop_checkpoint": self._loop_checkpoint("16b"),
                            "task_result": {
                                "status": "blocked",
                                "summary": "Attempted out-of-scope write",
                                "artifacts": [],
                                "findings": [
                                    {
                                        "id": "llm-out-of-scope-write",
                                        "type": "scope_creep",
                                        "severity": "blocking",
                                        "description": "Write target outside scope",
                                        "source": "LLM",
                                        "impact": "Scope violation",
                                    }
                                ],
                            },
                        }
                    return {
                        "action": "tool_call",
                        "summary": "Attempt out-of-scope write",
                        "tool_call": {
                            "tool_name": "write_file",
                            "args": {"path": "src/out_of_scope.py", "content": "print('x')"},
                        },
                    }
                return {
                    "action": "final_result",
                    "summary": f"{phase} success",
                    "loop_checkpoint": self._loop_checkpoint(phase),
                    "task_result": {
                        "status": "success",
                        "summary": f"{phase} success",
                        "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                    },
                }

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)
                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "blocked", result)
                self.assertEqual(result.get("phase"), "16b", result)
                self.assertTrue(seen["blocked_tool_result"], "LLM tool_result should be blocked for out-of-scope write")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_run_trinity_llm_mode_evidence_binding_failure_retries_planner_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture_repo(
                tmp,
                allow_dirty=True,
                checkpoint_commits=False,
                execution_mode="llm",
                preverified_artifact=True,
            )
            phase_counts = {"16a": 0, "16b": 0, "16c": 0}

            def _phase(messages):
                for msg in messages:
                    if not (isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str)):
                        continue
                    try:
                        candidate = json.loads(msg["content"])
                    except Exception:
                        continue
                    task_input = candidate.get("task_input")
                    if isinstance(task_input, dict):
                        maybe_phase = task_input.get("phase")
                        if isinstance(maybe_phase, str):
                            return maybe_phase
                return "16a"

            def responder(messages, _state):
                phase = _phase(messages)
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
                if phase == "16c":
                    return {
                        "action": "final_result",
                        "summary": "Evidence binding missing",
                        "loop_checkpoint": self._loop_checkpoint("16c"),
                        "task_result": {
                            "status": "blocked",
                            "summary": "Verifier blocked: missing evidence binding",
                            "artifacts": [],
                            "findings": [
                                {
                                    "id": "llm-missing-evidence-binding",
                                    "type": "policy",
                                    "severity": "blocking",
                                    "description": "Evidence binding missing for required checklist command.",
                                    "source": "LLM",
                                    "impact": "Cannot verify milestone closure.",
                                }
                            ],
                        },
                    }
                return {
                    "action": "final_result",
                    "summary": f"{phase} success",
                    "loop_checkpoint": self._loop_checkpoint(phase),
                    "task_result": {
                        "status": "success",
                        "summary": f"{phase} success",
                        "artifacts": ["spec/impl_context/m1-core-foundation.json"],
                    },
                }

            server, thread, _calls = self._start_scripted_openai_server(responder)
            try:
                port = server.server_address[1]
                config_path = os.path.join(tmp, ".trinity", "trinity.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config_text = f.read()
                config_text = config_text.replace("http://localhost:1234/v1", f"http://127.0.0.1:{port}/v1")
                self._write_text(config_path, config_text)
                result = run_trinity(repo_root=tmp, step_id="m1-core-foundation")
                self.assertEqual(result.get("status"), "blocked", result)
                self.assertEqual(result.get("phase"), "16c", result)
                self.assertTrue(any("verifier retry cap exceeded" in e for e in result.get("errors", [])), result)
                self.assertGreaterEqual(phase_counts["16c"], 1, phase_counts)
                self.assertGreaterEqual(phase_counts["16a"], 2, phase_counts)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
