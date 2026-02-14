import hashlib
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading
import unittest
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from specdev_tools.trinity_eval_export import export_eval_rows
from specdev_tools.trinity_replay import replay_session
from specdev_tools.trinity_dashboard import write_dashboard
from specdev_tools.trinity_remediation import build_remediation_plan
from specdev_tools.trinity_runtime_validate import validate_runtime_file
from specdev_tools.trinity_eval_publish import publish_eval_bundle


class TestTrinityEvalReplay(unittest.TestCase):
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

    def _sha256_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _sha256_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _event_sha256(self, event: dict) -> str:
        payload = dict(event)
        payload["event_sha256"] = None
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _git_head_commit(self) -> str:
        import subprocess

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

    def _base_metadata(self) -> dict:
        return {
            "toolkit_version": "0.2.3",
            "schema_version": "v1",
            "git_head": "deadbeef",
            "prompt_template_id": "prompt-16b",
            "prompt_template_sha256": "a" * 64,
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
        }

    def _build_events(self, tmp: str, mutate_after_log: bool = False) -> tuple[str, list[dict]]:
        sessions_dir = os.path.join(tmp, ".trinity", "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        captures_dir = os.path.join(tmp, ".trinity", "captures")
        os.makedirs(captures_dir, exist_ok=True)
        spawns_dir = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1")
        os.makedirs(spawns_dir, exist_ok=True)

        artifact_path = os.path.join(tmp, "artifact.json")
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump({"ok": True}, f)
        artifact_sha = self._sha256_file(artifact_path)

        commit_hash = self._git_head_commit()
        api_id, api_line = self._first_id_line("spec/05_interface_contracts.json")
        context_pack_path = os.path.join(tmp, ".trinity", "runtime", "context_pack.json")
        with open(context_pack_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "protocol_version": "trinity-runtime-v1",
                    "phase": "16a",
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
                    },
                    "allowed_read_paths": ["spec/", "src/", "tests/"],
                    "allowed_write_paths": ["src/", "tests/", "spec/impl_context/", "README.md"],
                    "target_file_patterns": ["src/*.py"],
                    "docs_policy": {"doc_paths": ["docs/**", "README.md"]},
                },
                f,
                indent=2,
            )

        spawn_task_input_path = os.path.join(spawns_dir, "task_input.json")
        with open(spawn_task_input_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "protocol_version": "trinity-runtime-v1",
                    "child_id": "child-1",
                    "parent_id": "agent-root",
                    "role": "Planner",
                    "phase": "16a",
                    "step_id": "m1-core-foundation",
                    "task_description": "Plan implementation for core foundation",
                    "expected_output_schema": "https://specdev.local/schema/trinity/task_result.schema.json",
                    "context_pack_ref": context_pack_path,
                    "target_files": ["src/core.py"],
                    "spec_refs": [{"type": "api", "id": api_id}],
                    "role_metadata": {
                        "prompt_source": "prompt_16a_impl_planner.md",
                        "persona_goal": "produce actionable plan",
                        "stop_conditions": ["plan complete"],
                    },
                },
                f,
                indent=2,
            )

        prompt_path = os.path.join(captures_dir, "prompt_evt-2.txt")
        response_path = os.path.join(captures_dir, "response_evt-2.txt")
        prompt_text = "Prompt content for replay/export"
        response_text = "Response content for replay/export"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        with open(response_path, "w", encoding="utf-8") as f:
            f.write(response_text)
        prompt_sha = self._sha256_text(prompt_text)
        response_sha = self._sha256_text(response_text)
        task_result_path = os.path.join(spawns_dir, "task_result.json")
        with open(task_result_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "protocol_version": "trinity-runtime-v1",
                    "child_id": "child-1",
                    "role": "Planner",
                    "phase": "16a",
                    "step_id": "m1-core-foundation",
                    "status": "blocked",
                    "summary": "Blocked waiting for clarification",
                    "artifacts": [],
                    "findings": [
                        {
                            "id": "amb-missing-requirement",
                            "type": "gap",
                            "severity": "blocking",
                            "description": "Missing deterministic requirement detail",
                            "source": "replay-test",
                            "impact": "planning",
                        }
                    ],
                },
                f,
                indent=2,
            )

        event_1 = {
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
            "artifact_ref": artifact_path,
            "artifact_sha256": artifact_sha,
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "spawn planner",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_input_artifact_ref": spawn_task_input_path,
            },
            "metadata": self._base_metadata(),
        }
        event_1["event_sha256"] = self._event_sha256(event_1)

        event_2 = {
            "schema_version": "trinity-session-log-v1",
            "timestamp": "2026-02-13T00:00:01Z",
            "event_type": "MESSAGE",
            "event_id": "evt-2",
            "event_sequence": 2,
            "prev_event_sha256": event_1["event_sha256"],
            "event_sha256": "0" * 64,
            "run_id": "run-1",
            "phase_id": "phase-16b",
            "loop_id": "loop-1",
            "agent_id": "agent-root",
            "parent_id": None,
            "role": "Orchestrator",
            "step_id": "m1-core-foundation",
            "tool_call_id": None,
            "result_id": None,
            "artifact_ref": artifact_path,
            "artifact_sha256": artifact_sha,
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "captured full prompt/response sample",
                "capture_level": "full",
                "capture_decision_reason": "policy:sampled:MESSAGE",
                "prompt_artifact_ref": prompt_path,
                "prompt_sha256": prompt_sha,
                "response_artifact_ref": response_path,
                "response_sha256": response_sha,
            },
            "metadata": self._base_metadata(),
        }
        event_2["event_sha256"] = self._event_sha256(event_2)

        event_3 = {
            "schema_version": "trinity-session-log-v1",
            "timestamp": "2026-02-13T00:00:02Z",
            "event_type": "VALIDATION",
            "event_id": "evt-3",
            "event_sequence": 3,
            "prev_event_sha256": event_2["event_sha256"],
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
            "artifact_ref": task_result_path,
            "artifact_sha256": self._sha256_file(task_result_path),
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "validated child task_input",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_input_artifact_ref": spawn_task_input_path,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            },
            "metadata": self._base_metadata(),
        }
        event_3["event_sha256"] = self._event_sha256(event_3)

        event_4 = {
            "schema_version": "trinity-session-log-v1",
            "timestamp": "2026-02-13T00:00:03Z",
            "event_type": "VALIDATION",
            "event_id": "evt-4",
            "event_sequence": 4,
            "prev_event_sha256": event_3["event_sha256"],
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
            "artifact_ref": task_result_path,
            "artifact_sha256": self._sha256_file(task_result_path),
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "validated child task_result",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_result_artifact_ref": task_result_path,
                "validation": {
                    "schema": "pass",
                    "deep_validator": "pass",
                    "governance": "n/a",
                    "seed_lint": "n/a",
                    "docs_lint": "n/a",
                },
            },
            "metadata": self._base_metadata(),
        }
        event_4["event_sha256"] = self._event_sha256(event_4)

        event_5 = {
            "schema_version": "trinity-session-log-v1",
            "timestamp": "2026-02-13T00:00:04Z",
            "event_type": "TERMINATE",
            "event_id": "evt-5",
            "event_sequence": 5,
            "prev_event_sha256": event_4["event_sha256"],
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
            "artifact_ref": task_result_path,
            "artifact_sha256": self._sha256_file(task_result_path),
            "diff_ref": None,
            "model": "gpt-5",
            "content": {
                "summary": "planner child completed",
                "capture_level": "none",
                "capture_decision_reason": "policy:default:none",
                "prompt_artifact_ref": None,
                "prompt_sha256": None,
                "response_artifact_ref": None,
                "response_sha256": None,
                "task_result_artifact_ref": task_result_path,
            },
            "metadata": self._base_metadata(),
        }
        event_5["event_sha256"] = self._event_sha256(event_5)

        session_log = os.path.join(sessions_dir, "session.jsonl")
        with open(session_log, "w", encoding="utf-8") as f:
            f.write(json.dumps(event_1) + "\n")
            f.write(json.dumps(event_2) + "\n")
            f.write(json.dumps(event_3) + "\n")
            f.write(json.dumps(event_4) + "\n")
            f.write(json.dumps(event_5) + "\n")

        if mutate_after_log:
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write("tampered")

        return session_log, [event_1, event_2, event_3, event_4, event_5]

    def test_export_eval_rows_from_session_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            runtime_errors = validate_runtime_file(self.repo_root, session_log, "session_event")
            self.assertEqual(runtime_errors, [], f"Session log should validate. Errors: {runtime_errors}")

            out_path = os.path.join(tmp, "eval_rows.jsonl")
            rows, errors = export_eval_rows(self.repo_root, session_log, out_path=out_path)
            self.assertEqual(errors, [], f"Eval export should succeed. Errors: {errors}")
            self.assertEqual(len(rows), 5, "Expected one eval row per event")

            with open(out_path, "r", encoding="utf-8") as f:
                exported_lines = [line for line in f.read().splitlines() if line.strip()]
            self.assertEqual(len(exported_lines), 5, "Output JSONL should contain five rows")
            self.assertEqual(rows[0]["event_id"], "evt-1")
            self.assertEqual(rows[1]["capture_level"], "full")
            self.assertEqual(rows[-1]["phase_outcome"], "blocked")
            self.assertEqual(rows[-1]["max_finding_severity"], "blocking")
            self.assertTrue(rows[-1]["remediation_required"])

    def test_replay_session_strict_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            report = replay_session(self.repo_root, session_log, strict=True)
            self.assertEqual(report["status"], "ok", f"Strict replay should pass. Report: {report}")
            self.assertEqual(report["artifact_verification"]["mismatch"], 0)
            self.assertEqual(report["artifact_verification"]["missing"], 0)

    def test_replay_session_detects_artifact_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp, mutate_after_log=True)
            report_warn = replay_session(self.repo_root, session_log, strict=False)
            self.assertEqual(report_warn["status"], "warnings", f"Replay should warn on tamper. Report: {report_warn}")
            self.assertGreater(report_warn["artifact_verification"]["mismatch"], 0)

            report_strict = replay_session(self.repo_root, session_log, strict=True)
            self.assertEqual(report_strict["status"], "failed", f"Strict replay should fail on tamper. Report: {report_strict}")

    def test_dashboard_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            rows_out = os.path.join(tmp, "eval_rows.jsonl")
            rows, errors = export_eval_rows(self.repo_root, session_log, out_path=rows_out)
            self.assertEqual(errors, [], f"Export should succeed. Errors: {errors}")
            self.assertEqual(len(rows), 5)

            replay_out = os.path.join(tmp, "replay.json")
            report = replay_session(self.repo_root, session_log, strict=False)
            with open(replay_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

            out_json = os.path.join(tmp, "dashboard.json")
            out_md = os.path.join(tmp, "dashboard.md")
            summary, markdown = write_dashboard(
                eval_rows_glob=os.path.join(tmp, "eval_rows*.jsonl"),
                replay_reports_glob=os.path.join(tmp, "replay*.json"),
                out_json=out_json,
                out_md=out_md,
            )
            self.assertEqual(summary["totals"]["eval_rows"], 5)
            self.assertIn("Trinity Eval Dashboard", markdown)
            self.assertTrue(os.path.exists(out_json))
            self.assertTrue(os.path.exists(out_md))

    def test_remediation_plan_generation_with_resume_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            replay_report = replay_session(self.repo_root, session_log, strict=False)
            replay_report_path = os.path.join(tmp, "replay_report.json")
            with open(replay_report_path, "w", encoding="utf-8") as f:
                json.dump(replay_report, f, indent=2)

            out_state = os.path.join(tmp, "session_state_resume.json")
            out_task_input = os.path.join(tmp, "task_input_resume.json")
            plan, errors = build_remediation_plan(
                repo_root=self.repo_root,
                replay_report_path=replay_report_path,
                session_log_path=session_log,
                emit_session_state_path=out_state,
                emit_task_input_path=out_task_input,
            )
            self.assertEqual(errors, [], f"Remediation should produce valid resume artifacts. Errors: {errors}")
            self.assertIn("actions", plan)
            self.assertTrue(os.path.exists(out_state))
            self.assertTrue(os.path.exists(out_task_input))
            self.assertEqual(plan["status"], "ready")

    def test_publish_eval_bundle_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            rows_out = os.path.join(tmp, "eval_rows.jsonl")
            replay_out = os.path.join(tmp, "replay.json")
            dashboard_out = os.path.join(tmp, "dashboard.json")

            rows, errors = export_eval_rows(self.repo_root, session_log, out_path=rows_out)
            self.assertEqual(errors, [], f"Eval export should succeed. Errors: {errors}")
            self.assertEqual(len(rows), 5)

            report = replay_session(self.repo_root, session_log, strict=False)
            with open(replay_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            summary, _ = write_dashboard(
                eval_rows_glob=rows_out,
                replay_reports_glob=replay_out,
                out_json=dashboard_out,
                out_md=None,
            )
            self.assertIn("totals", summary)

            bundle_out = os.path.join(tmp, "export_bundle.json")
            bundle, publish_result, publish_errors = publish_eval_bundle(
                rows_glob=rows_out,
                replay_glob=replay_out,
                dashboard_json=dashboard_out,
                out_path=bundle_out,
                source="tests",
            )
            self.assertEqual(publish_errors, [], f"Local bundle generation should succeed. Errors: {publish_errors}")
            self.assertEqual(publish_result["status"], "skipped")
            self.assertEqual(bundle["row_count_exported"], 5)
            self.assertTrue(os.path.exists(bundle_out))

    def test_publish_eval_bundle_http_endpoint(self):
        class _Handler(http.server.BaseHTTPRequestHandler):
            received = {"count": 0, "body": None, "auth": None}

            def do_POST(self):  # type: ignore[override]
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                _Handler.received["count"] += 1
                _Handler.received["body"] = body.decode("utf-8")
                _Handler.received["auth"] = self.headers.get("Authorization")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, format, *args):  # noqa: A003
                return

        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            rows_out = os.path.join(tmp, "eval_rows.jsonl")
            replay_out = os.path.join(tmp, "replay.json")
            export_eval_rows(self.repo_root, session_log, out_path=rows_out)
            report = replay_session(self.repo_root, session_log, strict=False)
            with open(replay_out, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

            class ReuseTCPServer(socketserver.TCPServer):
                allow_reuse_address = True

            with ReuseTCPServer(("127.0.0.1", 0), _Handler) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    bundle, publish_result, publish_errors = publish_eval_bundle(
                        rows_glob=rows_out,
                        replay_glob=replay_out,
                        source="tests",
                        endpoint=f"http://127.0.0.1:{port}/ingest",
                        auth_token="secret-token",
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=5)

            self.assertEqual(publish_errors, [], f"HTTP publish should succeed. Errors: {publish_errors}")
            self.assertEqual(publish_result["status"], "published")
            self.assertEqual(_Handler.received["count"], 1)
            self.assertIn('"schema_version": "trinity-eval-export-v1"', _Handler.received["body"])
            self.assertEqual(_Handler.received["auth"], "Bearer secret-token")

    def test_remediation_missing_resume_source_soft_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            spawn_task_input = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "task_input.json")
            os.remove(spawn_task_input)

            replay_report = replay_session(self.repo_root, session_log, strict=False)
            replay_report_path = os.path.join(tmp, "replay_report.json")
            with open(replay_report_path, "w", encoding="utf-8") as f:
                json.dump(replay_report, f, indent=2)

            out_state = os.path.join(tmp, "session_state_resume.json")
            out_task_input = os.path.join(tmp, "task_input_resume.json")
            plan, errors = build_remediation_plan(
                repo_root=self.repo_root,
                replay_report_path=replay_report_path,
                session_log_path=session_log,
                emit_session_state_path=out_state,
                emit_task_input_path=out_task_input,
                missing_resume_source_policy="soft",
            )
            self.assertEqual(errors, [], f"Soft policy should not fail remediation. Errors: {errors}")
            self.assertEqual(plan["status"], "ready_with_warnings")
            self.assertTrue(plan.get("warnings"), "Soft policy should record warnings for missing source artifacts")
            self.assertTrue(os.path.exists(out_state), "Session state should still be emitted in soft mode")
            self.assertFalse(os.path.exists(out_task_input), "Task input should not be emitted when source is missing")

    def test_remediation_missing_resume_source_hard_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_log, _ = self._build_events(tmp)
            spawn_task_input = os.path.join(tmp, ".trinity", "runtime", "spawns", "child-1", "task_input.json")
            os.remove(spawn_task_input)

            replay_report = replay_session(self.repo_root, session_log, strict=False)
            replay_report_path = os.path.join(tmp, "replay_report.json")
            with open(replay_report_path, "w", encoding="utf-8") as f:
                json.dump(replay_report, f, indent=2)

            out_state = os.path.join(tmp, "session_state_resume.json")
            out_task_input = os.path.join(tmp, "task_input_resume.json")
            plan, errors = build_remediation_plan(
                repo_root=self.repo_root,
                replay_report_path=replay_report_path,
                session_log_path=session_log,
                emit_session_state_path=out_state,
                emit_task_input_path=out_task_input,
                missing_resume_source_policy="hard",
            )
            self.assertTrue(errors, "Hard policy should fail remediation on missing source artifacts")
            self.assertEqual(plan["status"], "needs_attention")

    def test_remediation_session_state_requires_lineage_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            replay_report_path = os.path.join(tmp, "replay_report.json")
            with open(replay_report_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "status": "warnings",
                        "summary": {"run_id": "run-1", "step_ids": []},
                        "timeline": [
                            {
                                "event_id": "evt-1",
                                "event_type": "MESSAGE",
                                "phase_id": "phase-unknown",
                                "agent_id": None,
                            }
                        ],
                        "warnings": ["synthetic warning"],
                        "errors": [],
                    },
                    f,
                    indent=2,
                )

            out_state = os.path.join(tmp, "session_state_resume.json")
            plan, errors = build_remediation_plan(
                repo_root=self.repo_root,
                replay_report_path=replay_report_path,
                emit_session_state_path=out_state,
            )
            self.assertTrue(errors, "Lineage gaps should fail remediation state generation.")
            self.assertEqual(plan["status"], "needs_attention")
            self.assertFalse(os.path.exists(out_state), "Session state must not be emitted with missing lineage.")


if __name__ == "__main__":
    unittest.main()
