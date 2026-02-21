from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .registry import SchemaRegistry
from .trinity_runtime_validate import RUNTIME_SCHEMA_BY_TYPE, validate_runtime_file
from .validate import validate_file
from .seed_lint import lint_seeds
from .docs_lint import lint_docs
from .governance import check_commit_message


PROTO_VER = "trinity-runtime-v1"
SESSION_SCHEMA_VER = "trinity-session-log-v1"
TOOL_REQUEST_SCHEMA_URI = "https://specdev.local/schema/trinity/tool_call_request.schema.json"
TOOL_RESULT_SCHEMA_URI = "https://specdev.local/schema/trinity/tool_call_result.schema.json"
UTILITY_CALL_SCHEMA_URI = "https://specdev.local/schema/trinity/utility_call.schema.json"
UTILITY_RESULT_SCHEMA_URI = "https://specdev.local/schema/trinity/utility_result.schema.json"

CORE_AUTHORITY_FILES = [
    "spec/04_fr_list.json",
    "spec/05_interface_contracts.json",
    "spec/06_invariants.json",
    "spec/07_nfrs.json",
    "spec/08_fixtures.json",
    "spec/09_impl_plan.json",
    "spec/10_governance.json",
    "spec/11_redteam.json",
    "spec/12_ci_gates.json",
    "spec/13_extension_manifest.json",
    "spec/13a_completeness_assessment.json",
    "spec/14_roadmap.json",
    "spec/15_scaffold.json",
]

SPEC_FILE_BY_TYPE = {
    "fr": "spec/04_fr_list.json",
    "api": "spec/05_interface_contracts.json",
    "inv": "spec/06_invariants.json",
    "nfr": "spec/07_nfrs.json",
    "fixture": "spec/08_fixtures.json",
}

PROMPT_MAP = {
    "16a": "prompts/prompt_16a_impl_planner.md",
    "16b": "prompts/prompt_16b_impl_coder.md",
    "16c": "prompts/prompt_16c_impl_reviewer.md",
}

UTILITY_PROMPT_MAP = {
    "Researcher": "prompts/trinity/70_researcher.md",
    "ToolUser": "prompts/trinity/80_tool_usage.md",
    "Summarizer": "prompts/trinity/90_summarizer.md",
    "Auditor": "prompts/trinity/99_auditor.md",
}

READONLY_GIT_SUBCOMMANDS = {
    "branch",
    "describe",
    "diff",
    "grep",
    "log",
    "ls-files",
    "rev-parse",
    "show",
    "status",
    "tag",
}

WILDCARD_CHARS = set("*?[]")

DEFAULT_CAPTURE_POLICY = {
    "policy_id": "builtin-eval-default",
    "version": "1",
    "default_capture_level": "summary",
    "always_full_on_event_types": ["ERROR"],
    "sample_rate_by_event_type": {
        "SPAWN": 0.0,
        "MESSAGE": 0.2,
        "TOOL_CALL": 0.0,
        "TOOL_RESULT": 0.25,
        "VALIDATION": 0.5,
        "TERMINATE": 0.1,
        "ERROR": 1.0,
    },
    "max_full_events_per_run": 24,
    "context_window_token_target": 80000,
    "max_full_capture_context_fraction": 0.2,
    "full_capture_token_budget_per_run": 20000,
    "max_full_prompt_tokens_per_event": 12000,
    "max_full_completion_tokens_per_event": 6000,
    "oversize_fallback": "summary",
    "full_capture_allowlist_roles": [
        "Orchestrator",
        "Planner",
        "Builder",
        "Verifier",
        "Worker",
        "Researcher",
        "Auditor",
        "Summarizer",
        "ToolUser",
    ],
    "require_redaction_before_full": True,
    "sampling_salt": "builtin",
    "operating_profile": {
        "profile": "eval_default",
        "tier": "balanced",
        "budget_tier": "medium",
    },
    "budgets": {
        "context_window_token_target": 80000,
        "full_capture_token_budget_per_run": 20000,
        "max_full_prompt_tokens_per_event": 12000,
        "max_full_completion_tokens_per_event": 6000,
    },
    "retention": {
        "session_log_days": 30,
        "capture_artifact_days": 14,
        "eval_export_days": 90,
    },
}

SECRET_REDACTION_RULES: Tuple[Tuple[str, re.Pattern[str], str, float], ...] = (
    (
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "[REDACTED_OPENAI_KEY]",
        0.98,
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_ACCESS_KEY]",
        0.96,
    ),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
        0.94,
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_JWT]",
        0.92,
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY_BLOCK]",
        0.99,
    ),
    (
        "api_secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([\"']?)[^\s\"';]{8,}\2"
        ),
        r"\1=[REDACTED_SECRET]",
        0.9,
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _canonical_sha(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(canonical)


def _compute_event_sha(event: dict) -> str:
    hash_payload = dict(event)
    hash_payload["event_sha256"] = None
    canonical = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(canonical)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_atomic(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp-{uuid.uuid4().hex}"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(temp_path, path)


def _append_jsonl(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def _rel(repo_root: str, path: str) -> str:
    return os.path.relpath(path, repo_root).replace("\\", "/")


def _path_within_root(root: str, candidate: str) -> bool:
    root_real = os.path.realpath(root)
    cand_real = os.path.realpath(candidate)
    return cand_real == root_real or cand_real.startswith(root_real + os.sep)


def _normalize_rel_path(path_value: str) -> str:
    raw = path_value.replace("\\", "/").strip()
    if raw.startswith("./"):
        raw = raw[2:]
    normalized = os.path.normpath(raw or ".").replace("\\", "/")
    if normalized in {"", "."}:
        return "."
    return normalized


def _is_escape_rel_path(path_value: str) -> bool:
    normalized = _normalize_rel_path(path_value)
    return normalized == ".." or normalized.startswith("../")


def _prompt_path_for(phase: str, role: Optional[str] = None) -> str:
    if phase == "utility" and isinstance(role, str):
        role_prompt = UTILITY_PROMPT_MAP.get(role)
        if isinstance(role_prompt, str):
            return role_prompt
    return PROMPT_MAP.get(phase, "prompts/prompt_16_impl_context.md")


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: trinity config must be a YAML object")
    return data


def _run_git(repo_root: str, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {msg}")
    return result


def _git_head(repo_root: str) -> Optional[str]:
    result = _run_git(repo_root, ["rev-parse", "HEAD"], check=False)
    if result.returncode != 0:
        return None
    out = (result.stdout or "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", out):
        return out
    return None


def _is_dirty_worktree(repo_root: str) -> bool:
    result = _run_git(repo_root, ["status", "--porcelain"], check=False)
    if result.returncode != 0:
        return True
    return bool((result.stdout or "").strip())


def _normalize_test_command(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        cmd = entry.strip()
        return cmd or None
    if isinstance(entry, dict):
        cmd = entry.get("command")
        if isinstance(cmd, str):
            cmd = cmd.strip()
            return cmd or None
    return None


def _looks_like_pattern(path_value: str) -> bool:
    return any(ch in WILDCARD_CHARS for ch in path_value)


def _redact_sensitive_text(text: str) -> Tuple[str, dict]:
    if not isinstance(text, str):
        return "", {
            "total_replacements": 0,
            "by_class": {},
            "classes_detected": [],
            "detectors_used": ["secret_scanner_v2"],
            "min_confidence": 0.0,
            "max_confidence": 0.0,
        }

    redacted = text
    by_class: Dict[str, int] = {}
    confidence_hits: List[float] = []
    for cls, pattern, replacement, confidence in SECRET_REDACTION_RULES:
        redacted, count = pattern.subn(replacement, redacted)
        if count > 0:
            by_class[cls] = by_class.get(cls, 0) + int(count)
            confidence_hits.extend([confidence] * int(count))

    total = sum(by_class.values())
    stats = {
        "total_replacements": total,
        "by_class": by_class,
        "classes_detected": sorted(by_class.keys()),
        "detectors_used": ["secret_scanner_v2"],
        "min_confidence": min(confidence_hits) if confidence_hits else 0.0,
        "max_confidence": max(confidence_hits) if confidence_hits else 0.0,
    }
    return redacted, stats


def _is_secret_dump_command(command: str) -> bool:
    lowered = command.lower()
    try:
        tokens = shlex.split(command, posix=True)
    except Exception:
        # Preserve conservative behavior when parsing fails.
        fallback_patterns = (
            "printenv",
            "env |",
            "cat ~/.ssh",
            "cat $home/.ssh",
            "cat ~/.aws",
            "aws configure get",
            "cat .env",
            "grep -r secret",
            "grep -r token",
        )
        return any(p in lowered for p in fallback_patterns)

    if not tokens:
        return False

    binary = tokens[0].lower()
    if binary == "printenv":
        return True
    if binary == "env":
        # Allow `env KEY=value <command>` but block output-dumping forms like
        # `env`, `env -0`, or shell-piped forms that primarily print environment.
        idx = 1
        while idx < len(tokens):
            tok = tokens[idx]
            if tok.startswith("-"):
                idx += 1
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok):
                idx += 1
                continue
            break
        if idx >= len(tokens):
            return True
        if tokens[idx] in {"|", ">", ">>"}:
            return True
        return False
    if binary == "aws" and len(tokens) >= 3 and tokens[1].lower() == "configure" and tokens[2].lower() == "get":
        return True
    if binary == "cat":
        sensitive_reads = {".env", "~/.ssh", "$home/.ssh", "~/.aws"}
        for tok in tokens[1:]:
            norm = tok.strip().lower()
            if norm in sensitive_reads or norm.startswith("~/.ssh/") or norm.startswith("$home/.ssh/"):
                return True
    if binary == "grep" and any(tok.lower() == "-r" for tok in tokens[1:]):
        targets = {tok.lower() for tok in tokens[1:] if isinstance(tok, str)}
        if "secret" in targets or "token" in targets:
            return True
    return False


def _loop_evidence_present(payload: Any) -> bool:
    if isinstance(payload, str):
        return len(payload.strip()) >= 8
    if isinstance(payload, list):
        return any(_loop_evidence_present(item) for item in payload)
    if isinstance(payload, dict):
        preferred_keys = ("evidence", "summary", "notes", "rationale", "decision", "artifact_ref")
        for key in preferred_keys:
            if _loop_evidence_present(payload.get(key)):
                return True
        for value in payload.values():
            if _loop_evidence_present(value):
                return True
    return False


def _extract_command_excerpt(stdout: str, stderr: str, exit_code: int) -> Tuple[str, bool]:
    text = (stdout or "") + ("\n" + stderr if stderr else "")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    marker_re = re.compile(r"(PASSED|passed|OK|SUCCESS|✓|0 (errors|failures?|failed)|\d+ passed)")
    for line in lines:
        if marker_re.search(line):
            return line[:400], True
    if lines:
        return lines[-1][:400], False
    return f"FAILED exit_code={exit_code}", False


def _stable_unit_interval(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)


def _extract_json_object(text: str) -> Optional[dict]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    end = -1
    for i, ch in enumerate(raw[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


@dataclass
class TrinityConfig:
    llm_api_base: str
    llm_model: str
    llm_timeout: int
    llm_api_key_env: str
    llm_temperature: float
    llm_top_p: float
    llm_max_tokens: int
    execution_mode: str
    max_child_turns: int
    max_loops: int
    retry_cap_planner: int
    retry_cap_builder: int
    retry_cap_verifier: int
    retry_cap_milestone: int
    allow_dirty: bool
    checkpoint_commits: bool
    conformance_mode: bool
    child_timeout_seconds: int
    child_timeout_by_phase: Dict[str, int]
    allow_bootstrap_authority_fallback: bool
    allow_anchor_conflicts: bool

    @staticmethod
    def load(repo_root: str) -> "TrinityConfig":
        config_path = os.path.join(repo_root, ".trinity", "trinity.yaml")
        if not os.path.exists(config_path):
            raise RuntimeError(f"Missing Trinity config: {config_path}")
        raw = _load_yaml(config_path)
        llm = raw.get("llm", {}) if isinstance(raw.get("llm"), dict) else {}
        limits = raw.get("limits", {}) if isinstance(raw.get("limits"), dict) else {}
        runtime = raw.get("runtime", {}) if isinstance(raw.get("runtime"), dict) else {}
        retry_caps = runtime.get("retry_caps", {}) if isinstance(runtime.get("retry_caps"), dict) else {}
        timeout_by_phase_raw = runtime.get("child_timeout_by_phase", {})
        timeout_by_phase: Dict[str, int] = {}
        if isinstance(timeout_by_phase_raw, dict):
            for phase_name in ("16a", "16b", "16c", "utility"):
                value = timeout_by_phase_raw.get(phase_name)
                if value is None:
                    continue
                ivalue = int(value)
                if ivalue < 0:
                    raise RuntimeError(f"runtime.child_timeout_by_phase.{phase_name} must be >= 0")
                timeout_by_phase[phase_name] = ivalue

        def _cap(name: str, fallback: int) -> int:
            value = int(retry_caps.get(name, fallback))
            if value < 1:
                raise RuntimeError(f"runtime.retry_caps.{name} must be >= 1")
            return value

        milestone_default = int(limits.get("max_loops", 10))
        if milestone_default < 1:
            raise RuntimeError("limits.max_loops must be >= 1")
        return TrinityConfig(
            llm_api_base=str(llm.get("api_base", "http://localhost:1234/v1")),
            llm_model=str(llm.get("model", "input-model")),
            llm_timeout=int(llm.get("timeout", 300)),
            llm_api_key_env=str(llm.get("api_key_env", "OPENAI_API_KEY")),
            llm_temperature=float(llm.get("temperature", 0.2)),
            llm_top_p=float(llm.get("top_p", 0.9)),
            llm_max_tokens=int(llm.get("max_tokens", 4096)),
            execution_mode=str(runtime.get("execution_mode", "llm")).strip().lower() or "llm",
            max_child_turns=int(runtime.get("max_child_turns", 12)),
            max_loops=milestone_default,
            retry_cap_planner=_cap("planner", 10),
            retry_cap_builder=_cap("builder", 10),
            retry_cap_verifier=_cap("verifier", 10),
            retry_cap_milestone=_cap("milestone", milestone_default),
            allow_dirty=bool(runtime.get("allow_dirty", False)),
            checkpoint_commits=bool(runtime.get("checkpoint_commits", True)),
            conformance_mode=bool(runtime.get("conformance_mode", True)),
            child_timeout_seconds=max(0, int(runtime.get("child_timeout_seconds", 21600))),
            child_timeout_by_phase=timeout_by_phase,
            allow_bootstrap_authority_fallback=bool(runtime.get("allow_bootstrap_authority_fallback", False)),
            allow_anchor_conflicts=bool(runtime.get("allow_anchor_conflicts", False)),
        )


class SessionLogger:
    def __init__(
        self,
        repo_root: str,
        run_id: str,
        root_task_id: str,
        step_id: str,
        model: str,
        *,
        decoding_temperature: float = 0.2,
        decoding_top_p: float = 0.9,
        decoding_max_tokens: int = 4096,
        log_path: Optional[str] = None,
    ) -> None:
        self.repo_root = repo_root
        self.run_id = run_id
        self.step_id = step_id
        self.model = model
        self.decoding_temperature = decoding_temperature
        self.decoding_top_p = decoding_top_p
        self.decoding_max_tokens = decoding_max_tokens
        if isinstance(log_path, str) and log_path.strip():
            self.path = log_path if os.path.isabs(log_path) else os.path.join(repo_root, log_path)
        else:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            self.path = os.path.join(repo_root, ".trinity", "sessions", f"{ts}_{root_task_id}.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8"):
                pass
        self.sequence = 0
        self.prev_hash: Optional[str] = None
        self.schema_registry = SchemaRegistry(repo_root)
        self.request_schema_sha = _canonical_sha(self.schema_registry.load(TOOL_REQUEST_SCHEMA_URI))
        self.result_schema_sha = _canonical_sha(self.schema_registry.load(TOOL_RESULT_SCHEMA_URI))
        self._session_event_validator = self._build_session_event_validator()
        self.catalog_ref = ".trinity/runtime/tools/catalog.json"
        self.catalog_sha = self._ensure_tool_catalog()
        self.toolkit_version = self._detect_toolkit_version()
        self.git_head = _git_head(repo_root) or "unknown"
        (
            self.capture_policy_ref,
            self.capture_policy_sha256,
            self.capture_policy,
            self.capture_policy_profile,
            self.capture_policy_fallback_warnings,
        ) = self._load_capture_policy()
        self._sampled_full_counts: Dict[str, int] = {}
        self._full_capture_tokens: Dict[str, int] = {}
        self._scan_offset = 0
        self.sync_from_disk()

    def _build_session_event_validator(self) -> Draft202012Validator:
        store = {uri: Resource.from_contents(schema) for uri, schema in self.schema_registry.store.items()}
        registry = Registry().with_resources(store.items())
        schema = self.schema_registry.load(RUNTIME_SCHEMA_BY_TYPE["session_event"])
        return Draft202012Validator(
            schema,
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )

    def sync_from_disk(self) -> None:
        if not os.path.exists(self.path):
            self.sequence = 0
            self.prev_hash = None
            self._scan_offset = 0
            return
        file_size = os.path.getsize(self.path)
        if self._scan_offset < 0 or self._scan_offset > file_size:
            self.sequence = 0
            self.prev_hash = None
            self._scan_offset = 0

        last_sequence = self.sequence
        last_hash: Optional[str] = self.prev_hash
        with open(self.path, "r", encoding="utf-8") as f:
            if self._scan_offset:
                f.seek(self._scan_offset)
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                seq = event.get("event_sequence")
                sha = event.get("event_sha256")
                if isinstance(seq, int) and seq > 0 and seq >= last_sequence:
                    last_sequence = seq
                    if isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{64}", sha):
                        last_hash = sha
            self._scan_offset = f.tell()
        self.sequence = last_sequence
        self.prev_hash = last_hash

    def _detect_toolkit_version(self) -> str:
        pyproject_path = os.path.join(self.repo_root, "tools", "pyproject.toml")
        if not os.path.exists(pyproject_path):
            return "unknown"
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
        return m.group(1) if m else "unknown"

    def _normalize_capture_policy(self, payload: dict) -> Tuple[dict, dict, List[str]]:
        effective = copy.deepcopy(DEFAULT_CAPTURE_POLICY)
        warnings: List[str] = []
        if not isinstance(payload, dict):
            warnings.append("capture policy payload was not an object; using builtin defaults")
            return effective, dict(effective.get("operating_profile", {})), warnings

        for key in (
            "policy_id",
            "version",
            "default_capture_level",
            "always_full_on_event_types",
            "sample_rate_by_event_type",
            "max_full_events_per_run",
            "context_window_token_target",
            "max_full_capture_context_fraction",
            "full_capture_token_budget_per_run",
            "max_full_prompt_tokens_per_event",
            "max_full_completion_tokens_per_event",
            "oversize_fallback",
            "full_capture_allowlist_roles",
            "require_redaction_before_full",
            "sampling_salt",
        ):
            if key in payload:
                effective[key] = payload[key]

        profile_in = payload.get("operating_profile")
        profile = copy.deepcopy(effective.get("operating_profile", {}))
        if isinstance(profile_in, dict):
            for pkey in ("profile", "tier", "budget_tier"):
                if isinstance(profile_in.get(pkey), str) and profile_in[pkey]:
                    profile[pkey] = profile_in[pkey]
                else:
                    warnings.append(f"capture policy operating_profile.{pkey} missing; default applied")
        else:
            warnings.append("capture policy operating_profile missing; default profile applied")

        retention_in = payload.get("retention")
        retention = copy.deepcopy(effective.get("retention", {}))
        if isinstance(retention_in, dict):
            for rkey in ("session_log_days", "capture_artifact_days", "eval_export_days"):
                rval = retention_in.get(rkey)
                if isinstance(rval, int) and rval >= 1:
                    retention[rkey] = rval
                else:
                    warnings.append(f"capture policy retention.{rkey} missing or invalid; default applied")
        else:
            warnings.append("capture policy retention missing; default retention applied")

        budgets_in = payload.get("budgets")
        budgets = copy.deepcopy(effective.get("budgets", {}))
        budget_map = {
            "context_window_token_target": 1024,
            "full_capture_token_budget_per_run": 0,
            "max_full_prompt_tokens_per_event": 0,
            "max_full_completion_tokens_per_event": 0,
        }
        for bkey, minimum in budget_map.items():
            chosen = None
            if isinstance(budgets_in, dict):
                chosen = budgets_in.get(bkey)
            if not (isinstance(chosen, int) and chosen >= minimum):
                chosen = payload.get(bkey)
            if isinstance(chosen, int) and chosen >= minimum:
                budgets[bkey] = chosen
            else:
                warnings.append(f"capture policy budget '{bkey}' missing or invalid; default applied")

        effective["operating_profile"] = profile
        effective["retention"] = retention
        effective["budgets"] = budgets
        effective["context_window_token_target"] = budgets["context_window_token_target"]
        effective["full_capture_token_budget_per_run"] = budgets["full_capture_token_budget_per_run"]
        effective["max_full_prompt_tokens_per_event"] = budgets["max_full_prompt_tokens_per_event"]
        effective["max_full_completion_tokens_per_event"] = budgets["max_full_completion_tokens_per_event"]
        return effective, profile, warnings

    def _load_capture_policy(self) -> Tuple[Optional[str], Optional[str], Optional[dict], dict, List[str]]:
        rel = ".trinity/logging/log_capture_policy.json"
        path = os.path.join(self.repo_root, rel)
        if not os.path.exists(path):
            default_policy = copy.deepcopy(DEFAULT_CAPTURE_POLICY)
            return (
                None,
                None,
                default_policy,
                copy.deepcopy(default_policy.get("operating_profile", {})),
                [],
            )
        errs = validate_runtime_file(self.repo_root, path, "log_capture_policy")
        if errs:
            raise RuntimeError("Invalid Trinity log capture policy: " + "; ".join(errs))
        payload = _read_json(path)
        effective, profile, warnings = self._normalize_capture_policy(payload)
        return rel, _canonical_sha(payload), effective, profile, warnings

    def _capture_decision(
        self,
        *,
        event_type: str,
        role: str,
        event_id: str,
        event_sequence: int,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Tuple[str, str]:
        if not isinstance(self.capture_policy, dict):
            return "summary", "policy:default"

        policy = self.capture_policy
        policy_id = str(policy.get("policy_id", "policy"))
        policy_run_key = f"{policy_id}|{self.run_id}"
        default_capture_level = str(policy.get("default_capture_level", "summary"))
        always_full_events = set(policy.get("always_full_on_event_types", []))
        allowlist_roles = policy.get("full_capture_allowlist_roles", [])
        role_allowed_for_full = (not allowlist_roles) or (role in allowlist_roles)
        sampling_salt = str(policy.get("sampling_salt", "default"))

        expected_capture_level = default_capture_level
        expected_reason_prefix = "policy:default"

        is_always_full = role_allowed_for_full and event_type in always_full_events
        if is_always_full:
            expected_capture_level = "full"
            expected_reason_prefix = "policy:always_full"
        else:
            sample_rates = policy.get("sample_rate_by_event_type", {})
            sample_rate = sample_rates.get(event_type, 0.0) if isinstance(sample_rates, dict) else 0.0
            sample_rate = sample_rate if isinstance(sample_rate, (int, float)) else 0.0
            sampled_for_full = False
            if role_allowed_for_full and sample_rate > 0:
                sample_key = f"{policy_id}|{sampling_salt}|{self.run_id}|{event_id}|{event_sequence}"
                sampled_for_full = _stable_unit_interval(sample_key) < float(sample_rate)
            if sampled_for_full:
                max_full_events = policy.get("max_full_events_per_run", 0)
                max_full_events = max_full_events if isinstance(max_full_events, int) else 0
                used = self._sampled_full_counts.get(policy_run_key, 0)
                if used < max_full_events:
                    expected_capture_level = "full"
                    expected_reason_prefix = "policy:sampled"
                    self._sampled_full_counts[policy_run_key] = used + 1
                else:
                    expected_capture_level = str(policy.get("oversize_fallback", "summary"))
                    expected_reason_prefix = "policy:capped"

        if expected_capture_level == "full":
            max_prompt_tokens = policy.get("max_full_prompt_tokens_per_event")
            max_prompt_tokens = max_prompt_tokens if isinstance(max_prompt_tokens, int) and max_prompt_tokens >= 0 else None
            max_completion_tokens = policy.get("max_full_completion_tokens_per_event")
            max_completion_tokens = (
                max_completion_tokens if isinstance(max_completion_tokens, int) and max_completion_tokens >= 0 else None
            )
            explicit_budget = policy.get("full_capture_token_budget_per_run")
            explicit_budget = explicit_budget if isinstance(explicit_budget, int) and explicit_budget >= 0 else None
            window_target = policy.get("context_window_token_target")
            window_target = window_target if isinstance(window_target, int) and window_target >= 0 else None
            window_fraction_raw = policy.get("max_full_capture_context_fraction")
            derived_budget: Optional[int] = None
            if (
                isinstance(window_fraction_raw, (int, float))
                and window_fraction_raw > 0
                and window_fraction_raw <= 1
                and isinstance(window_target, int)
            ):
                derived_budget = int(window_target * float(window_fraction_raw))

            effective_budget: Optional[int] = None
            for candidate in (explicit_budget, derived_budget):
                if candidate is None:
                    continue
                effective_budget = candidate if effective_budget is None else min(effective_budget, candidate)

            if isinstance(max_prompt_tokens, int) and prompt_tokens > max_prompt_tokens:
                expected_capture_level = str(policy.get("oversize_fallback", "summary"))
                expected_reason_prefix = "policy:token_guard_prompt"
            elif isinstance(max_completion_tokens, int) and completion_tokens > max_completion_tokens:
                expected_capture_level = str(policy.get("oversize_fallback", "summary"))
                expected_reason_prefix = "policy:token_guard_completion"
            else:
                used_tokens = self._full_capture_tokens.get(policy_run_key, 0)
                total_tokens = prompt_tokens + completion_tokens
                if isinstance(effective_budget, int) and (used_tokens + total_tokens > effective_budget):
                    expected_capture_level = str(policy.get("oversize_fallback", "summary"))
                    expected_reason_prefix = "policy:token_budget"
                else:
                    self._full_capture_tokens[policy_run_key] = used_tokens + total_tokens

        return expected_capture_level, expected_reason_prefix

    def _write_capture_artifact(self, *, event_id: str, kind: str, content: str) -> Tuple[str, str]:
        capture_dir = os.path.join(self.repo_root, ".trinity", "captures")
        os.makedirs(capture_dir, exist_ok=True)
        rel = f".trinity/captures/{kind}_{event_id}.txt"
        abs_path = os.path.join(self.repo_root, rel)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        return rel, _sha256_file(abs_path)

    def _ensure_tool_catalog(self) -> str:
        catalog_path = os.path.join(self.repo_root, self.catalog_ref)
        catalog = {
            "schema_version": "trinity-tool-catalog-v1",
            "tools": [
                {"tool_name": "read_file", "required_args": ["path"]},
                {"tool_name": "write_file", "required_args": ["path", "content"]},
                {"tool_name": "edit_file", "required_args": ["path", "edits"]},
                {"tool_name": "apply_patch", "required_args": ["patch"]},
                {"tool_name": "move_file", "required_args": ["src_path", "dst_path"]},
                {"tool_name": "remove_file", "required_args": ["path"]},
                {"tool_name": "list_dir", "required_args": ["path"]},
                {"tool_name": "glob_match", "required_args": ["path", "patterns"]},
                {"tool_name": "search_text", "required_args": ["pattern", "paths"]},
                {"tool_name": "git_head", "required_args": []},
                {"tool_name": "git_show", "required_args": ["rev"]},
                {"tool_name": "git_diff", "required_args": []},
                {"tool_name": "exec_cmd", "required_args": ["command", "mode"]},
                {"tool_name": "validate_json", "required_args": ["path"]},
                {"tool_name": "checkpoint_branch", "required_args": ["branch_name"]},
                {"tool_name": "checkpoint_commit", "required_args": ["message"]},
            ],
        }
        _write_json_atomic(catalog_path, catalog)
        return _canonical_sha(catalog)

    def _validate_event_before_persist(self, event: dict) -> None:
        errors = sorted(self._session_event_validator.iter_errors(event), key=lambda e: list(e.path))
        if errors:
            rendered = []
            for err in errors[:5]:
                path = "/".join(map(str, err.path))
                rendered.append(f"{path}: {err.message}" if path else str(err.message))
            raise RuntimeError("Session event schema validation failed before persistence: " + "; ".join(rendered))

    def append(
        self,
        event_type: str,
        *,
        role: str,
        phase_id: str,
        loop_id: str,
        agent_id: str,
        parent_id: Optional[str],
        summary: str,
        prompt_template_id: str,
        step_id: Optional[str],
        content_extra: Optional[dict] = None,
        metadata_extra: Optional[dict] = None,
        tool_call_id: Optional[str] = None,
        result_id: Optional[str] = None,
        artifact_ref: Optional[str] = None,
        artifact_sha256: Optional[str] = None,
        diff_ref: Optional[str] = None,
        prompt_material_override: Optional[str] = None,
        response_material_override: Optional[str] = None,
    ) -> dict:
        self.sync_from_disk()
        next_sequence = self.sequence + 1
        event_id = str(uuid.uuid4())
        prompt_template_path = None
        if isinstance(prompt_template_id, str) and prompt_template_id:
            candidate = prompt_template_id
            if not os.path.isabs(candidate):
                candidate = os.path.join(self.repo_root, candidate)
            if os.path.exists(candidate):
                prompt_template_path = candidate
        if prompt_template_path is None:
            prompt_template_path = os.path.join(self.repo_root, _prompt_path_for(phase_id, role))
        prompt_sha = ""
        prompt_text = prompt_template_id
        if os.path.exists(prompt_template_path):
            with open(prompt_template_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            prompt_sha = _sha256_text(prompt_text)
        else:
            prompt_sha = _sha256_text(prompt_template_id)
        prompt_capture_material = prompt_material_override if isinstance(prompt_material_override, str) else prompt_text

        content = {
            "summary": summary,
            "capture_level": "summary",
            "capture_decision_reason": "policy:default",
            "prompt_artifact_ref": None,
            "prompt_sha256": None,
            "response_artifact_ref": None,
            "response_sha256": None,
        }
        if content_extra:
            content.update(content_extra)

        completion_material = summary
        if content_extra:
            completion_material = completion_material + "\n" + json.dumps(content_extra, sort_keys=True, ensure_ascii=False)
        if isinstance(response_material_override, str):
            completion_material = response_material_override
        prompt_tokens = max(1, len(prompt_capture_material) // 4)
        completion_tokens = max(1, len(completion_material) // 4)
        capture_level, capture_reason = self._capture_decision(
            event_type=event_type,
            role=role,
            event_id=event_id,
            event_sequence=next_sequence,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        redaction_applied = False
        redaction_stats = {
            "total_replacements": 0,
            "by_class": {},
            "classes_detected": [],
            "detectors_used": ["secret_scanner_v2"],
            "min_confidence": 0.0,
            "max_confidence": 0.0,
        }
        prompt_capture_ref = None
        prompt_capture_sha = None
        response_capture_ref = None
        response_capture_sha = None
        if capture_level == "full":
            prompt_payload = prompt_capture_material
            response_payload = completion_material
            if isinstance(self.capture_policy, dict) and bool(self.capture_policy.get("require_redaction_before_full")):
                redaction_applied = True
                prompt_payload, prompt_stats = _redact_sensitive_text(prompt_payload)
                response_payload, response_stats = _redact_sensitive_text(response_payload)
                merged_by_class: Dict[str, int] = {}
                for stats_obj in (prompt_stats, response_stats):
                    by_class = stats_obj.get("by_class", {}) if isinstance(stats_obj.get("by_class"), dict) else {}
                    for cls, count in by_class.items():
                        if isinstance(cls, str) and isinstance(count, int) and count > 0:
                            merged_by_class[cls] = merged_by_class.get(cls, 0) + count
                total_replacements = sum(merged_by_class.values())
                confidence_values: List[float] = []
                for stats_obj in (prompt_stats, response_stats):
                    min_conf = stats_obj.get("min_confidence")
                    max_conf = stats_obj.get("max_confidence")
                    if isinstance(min_conf, (int, float)) and min_conf > 0:
                        confidence_values.append(float(min_conf))
                    if isinstance(max_conf, (int, float)) and max_conf > 0:
                        confidence_values.append(float(max_conf))
                redaction_stats = {
                    "total_replacements": total_replacements,
                    "by_class": merged_by_class,
                    "classes_detected": sorted(merged_by_class.keys()),
                    "detectors_used": ["secret_scanner_v2"],
                    "min_confidence": min(confidence_values) if confidence_values else 0.0,
                    "max_confidence": max(confidence_values) if confidence_values else 0.0,
                }
                _, residual_prompt_stats = _redact_sensitive_text(prompt_payload)
                _, residual_response_stats = _redact_sensitive_text(response_payload)
                residual_hits = int(residual_prompt_stats.get("total_replacements", 0)) + int(
                    residual_response_stats.get("total_replacements", 0)
                )
                if residual_hits > 0:
                    raise RuntimeError(
                        "capture policy requires redaction before full capture, but residual sensitive patterns remained"
                    )

            prompt_capture_ref, prompt_capture_sha = self._write_capture_artifact(
                event_id=event_id,
                kind="prompt",
                content=prompt_payload,
            )
            response_capture_ref, response_capture_sha = self._write_capture_artifact(
                event_id=event_id,
                kind="response",
                content=response_payload,
            )
            content["capture_level"] = "full"
            content["capture_decision_reason"] = capture_reason
            content["prompt_artifact_ref"] = prompt_capture_ref
            content["prompt_sha256"] = prompt_capture_sha
            content["response_artifact_ref"] = response_capture_ref
            content["response_sha256"] = response_capture_sha
        else:
            content["capture_level"] = capture_level
            content["capture_decision_reason"] = capture_reason

        metadata = {
            "toolkit_version": self.toolkit_version,
            "schema_version": "v1",
            "git_head": self.git_head,
            "prompt_template_id": prompt_template_id,
            "prompt_template_sha256": prompt_sha,
            "redaction_profile": "eval",
            "redaction_applied": redaction_applied,
            "capture_policy_ref": self.capture_policy_ref,
            "capture_policy_sha256": self.capture_policy_sha256,
            "capture_policy_profile": self.capture_policy_profile if isinstance(self.capture_policy_profile, dict) else None,
            "capture_policy_fallback_applied": bool(self.capture_policy_fallback_warnings),
            "capture_policy_fallback_reasons": list(self.capture_policy_fallback_warnings),
            "redaction_stats": redaction_stats,
            "decoding": {
                "temperature": self.decoding_temperature,
                "top_p": self.decoding_top_p,
                "max_tokens": self.decoding_max_tokens,
            },
            "token_usage": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
        }
        if metadata_extra:
            metadata.update(metadata_extra)

        event = {
            "schema_version": SESSION_SCHEMA_VER,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "event_id": event_id,
            "event_sequence": next_sequence,
            "prev_event_sha256": self.prev_hash,
            "event_sha256": None,
            "run_id": self.run_id,
            "phase_id": phase_id,
            "loop_id": loop_id,
            "agent_id": agent_id,
            "parent_id": parent_id,
            "role": role,
            "step_id": step_id,
            "tool_call_id": tool_call_id,
            "result_id": result_id,
            "artifact_ref": artifact_ref,
            "artifact_sha256": artifact_sha256,
            "diff_ref": diff_ref,
            "model": self.model,
            "content": content,
            "metadata": metadata,
        }
        event["event_sha256"] = _compute_event_sha(event)
        self._validate_event_before_persist(event)
        _append_jsonl(self.path, event)
        self.sequence = next_sequence
        self.prev_hash = event["event_sha256"]
        return event

    def tool_schema_context(self, tool_name: str) -> dict:
        return {
            "tool_schema_context": {
                "mode": "catalog_plus_on_demand",
                "catalog_ref": self.catalog_ref,
                "catalog_sha256": self.catalog_sha,
                "expanded_tool_names": [tool_name],
                "request_schema_uri": TOOL_REQUEST_SCHEMA_URI,
                "request_schema_sha256": self.request_schema_sha,
                "result_schema_uri": TOOL_RESULT_SCHEMA_URI,
                "result_schema_sha256": self.result_schema_sha,
            }
        }


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_base: str,
        model: str,
        timeout_seconds: int,
        api_key_env: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> None:
        base = (api_base or "").strip()
        if not base:
            raise RuntimeError("llm.api_base is required for llm execution mode")
        if base.endswith("/chat/completions"):
            self.url = base
        else:
            self.url = base.rstrip("/") + "/chat/completions"
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        key_name = (api_key_env or "").strip()
        self.api_key = os.environ.get(key_name) if key_name else None

    def chat(self, messages: List[dict]) -> Tuple[str, dict]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"LLM endpoint unreachable at {self.url}: {e}") from e
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"LLM request failed: {e}") from e

        try:
            parsed = json.loads(body)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"LLM response was not valid JSON: {e}") from e

        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM response missing choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {}) if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            text = "\n".join(parts)
        else:
            text = ""
        usage = parsed.get("usage", {}) if isinstance(parsed.get("usage"), dict) else {}
        return text, usage


class ToolExecutor:
    def __init__(
        self,
        repo_root: str,
        logger: SessionLogger,
        run_id: str,
        *,
        agent_id: str,
        phase: str,
        step_id: str,
        allowed_read_paths: List[str],
        allowed_write_paths: List[str],
        target_file_patterns: Optional[List[str]] = None,
        docs_policy: Optional[dict] = None,
        protected_write_paths: Optional[List[str]] = None,
        enable_checkpoints: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.logger = logger
        self.run_id = run_id
        self.agent_id = agent_id
        self.phase = phase
        self.step_id = step_id
        self.allowed_read_paths = allowed_read_paths
        self.allowed_write_paths = allowed_write_paths
        self.target_file_patterns = [p for p in (target_file_patterns or []) if isinstance(p, str) and p]
        self.docs_policy = docs_policy if isinstance(docs_policy, dict) else {}
        self.protected_write_paths = [p for p in (protected_write_paths or []) if isinstance(p, str) and p]
        self.enable_checkpoints = enable_checkpoints
        self.tools_dir = os.path.join(repo_root, ".trinity", "runtime", "tools")
        os.makedirs(self.tools_dir, exist_ok=True)

    def _is_allowed_path(self, rel_path: str, allowlist: List[str]) -> bool:
        normalized = _normalize_rel_path(rel_path)
        if _is_escape_rel_path(normalized):
            return False
        for allowed in allowlist:
            if not isinstance(allowed, str) or not allowed:
                continue
            allowed_norm = allowed.replace("\\", "/").strip()
            if allowed_norm.startswith("./"):
                allowed_norm = allowed_norm[2:]
            allowed_norm = allowed_norm.rstrip("/") or "."
            if _is_escape_rel_path(allowed_norm):
                continue
            if allowed_norm == ".":
                return True
            if normalized == allowed_norm or normalized.startswith(allowed_norm + "/"):
                return True
            if fnmatch.fnmatch(normalized, allowed_norm):
                return True
        return False

    def _resolve_path(self, path_value: str) -> Tuple[str, str]:
        if os.path.isabs(path_value):
            abs_path = path_value
        else:
            abs_path = os.path.abspath(os.path.join(self.repo_root, path_value))
        real = os.path.realpath(abs_path)
        root_real = os.path.realpath(self.repo_root)
        rel = os.path.relpath(real, root_real).replace("\\", "/")
        return real, rel

    def _matches_any_pattern(self, rel_path: str, patterns: List[str]) -> bool:
        normalized = _normalize_rel_path(rel_path)
        if _is_escape_rel_path(normalized):
            return False
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            pnorm = pattern.replace("\\", "/").strip()
            if pnorm.startswith("./"):
                pnorm = pnorm[2:]
            pnorm = pnorm or "."
            if _is_escape_rel_path(pnorm):
                continue
            if fnmatch.fnmatch(normalized, pnorm):
                return True
        return False

    def _is_protected_write_path(self, rel_path: str) -> bool:
        return self._is_allowed_path(rel_path, self.protected_write_paths)

    def _is_allowed_write_target(self, rel_path: str) -> bool:
        if not self._is_allowed_path(rel_path, self.allowed_write_paths):
            return False
        if not self.target_file_patterns:
            return True
        if self._matches_any_pattern(rel_path, self.target_file_patterns):
            return True
        doc_paths = self.docs_policy.get("doc_paths", []) if isinstance(self.docs_policy, dict) else []
        if isinstance(doc_paths, list) and self._matches_any_pattern(rel_path, [str(p) for p in doc_paths]):
            return True
        return False

    def _assert_write_allowed(self, rel_path: str, tool_name: str) -> None:
        if self.phase in {"16b", "16c"} and self._is_protected_write_path(rel_path):
            raise PermissionError(f"{tool_name} blocked by seed-authority guard: {rel_path}")
        if not self._is_allowed_write_target(rel_path):
            raise PermissionError(f"{tool_name} blocked by write scope: {rel_path}")

    def _worktree_snapshot(self) -> Set[str]:
        status = _run_git(self.repo_root, ["status", "--porcelain", "--untracked-files=all"], check=False)
        if status.returncode != 0:
            raise PermissionError("exec_cmd blocked: unable to inspect worktree state for readonly guard")
        ignored_prefixes = (".trinity/runtime/home", ".trinity/runtime/tmp")
        snapshot: Set[str] = set()
        for line in (status.stdout or "").splitlines():
            if not line.strip():
                continue
            path_fragment = line[3:] if len(line) > 3 else line
            if " -> " in path_fragment:
                path_fragment = path_fragment.split(" -> ", 1)[1]
            normalized = path_fragment.strip().replace("\\", "/")
            if any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in ignored_prefixes):
                continue
            snapshot.add(line.rstrip())
        return snapshot

    def _fallback_result(self, tool_name: str, args: dict) -> dict:
        head = _git_head(self.repo_root) or ("0" * 40)
        default_path = args.get("path") if isinstance(args.get("path"), str) and args.get("path").strip() else "."
        if tool_name == "read_file":
            start = args.get("start_line", 1)
            start_line = start if isinstance(start, int) and start > 0 else 1
            end = args.get("end_line")
            end_line = end if isinstance(end, int) and end > 0 else None
            return {"path": default_path, "line_start": start_line, "line_end": end_line, "bytes_read": 0, "content": "", "truncated": False}
        if tool_name == "write_file":
            return {"path": default_path, "bytes_written": 0, "content_sha256": "sha256:" + _sha256_text("")}
        if tool_name == "edit_file":
            return {"path": default_path, "edits_applied": 0, "content_sha256": "sha256:" + _sha256_text("")}
        if tool_name == "apply_patch":
            return {"files_changed": 0, "hunks_applied": 0}
        if tool_name == "move_file":
            src_path = args.get("src_path") if isinstance(args.get("src_path"), str) and args.get("src_path").strip() else default_path
            dst_path = args.get("dst_path") if isinstance(args.get("dst_path"), str) and args.get("dst_path").strip() else default_path
            return {"src_path": src_path, "dst_path": dst_path, "content_sha256": "sha256:" + _sha256_text("")}
        if tool_name == "remove_file":
            return {"path": default_path, "removed": False, "previously_missing": True}
        if tool_name == "list_dir":
            return {"path": default_path, "entries": []}
        if tool_name == "glob_match":
            patterns_raw = args.get("patterns", [])
            patterns = [p for p in patterns_raw if isinstance(p, str) and p] if isinstance(patterns_raw, list) else []
            if not patterns:
                patterns = ["*"]
            return {"path": default_path, "patterns": patterns, "matches": []}
        if tool_name == "search_text":
            pattern = args.get("pattern") if isinstance(args.get("pattern"), str) and args.get("pattern") else "<missing-pattern>"
            return {"pattern": pattern, "paths_scanned": 0, "matches": []}
        if tool_name == "git_head":
            return {"head": head}
        if tool_name == "git_show":
            rev = args.get("rev") if isinstance(args.get("rev"), str) and args.get("rev") else "HEAD"
            return {"rev": rev, "content_excerpt": "", "truncated": False}
        if tool_name == "git_diff":
            return {"base_rev": None, "head_rev": None, "diff_excerpt": "", "truncated": False}
        if tool_name == "exec_cmd":
            command = args.get("command") if isinstance(args.get("command"), str) and args.get("command") else "<blocked-command>"
            mode = args.get("mode") if args.get("mode") in {"standard", "summarized"} else "summarized"
            return {"command": command, "mode": mode}
        if tool_name == "validate_json":
            return {"path": default_path, "valid": False, "errors": []}
        if tool_name == "checkpoint_branch":
            branch = args.get("branch_name") if isinstance(args.get("branch_name"), str) and args.get("branch_name") else f"trinity/{self.step_id or 'default'}"
            return {"branch_name": branch, "head": head}
        if tool_name == "checkpoint_commit":
            message = args.get("message") if isinstance(args.get("message"), str) and args.get("message") else "checkpoint blocked"
            return {"commit_sha": head, "message": message}
        return {}

    def call(
        self,
        tool_name: str,
        args: dict,
        *,
        role: str = "Orchestrator",
        parent_id: Optional[str] = None,
        loop_id: str = "l1",
    ) -> dict:
        call_id = f"tool-{uuid.uuid4().hex[:12]}"
        created_at = _utc_now()
        request = {
            "protocol_version": PROTO_VER,
            "run_id": self.run_id,
            "call_id": call_id,
            "agent_id": self.agent_id,
            "parent_id": parent_id,
            "role": role,
            "phase": self.phase,
            "step_id": self.step_id,
            "tool_name": tool_name,
            "args": args,
            "working_dir": self.repo_root,
            "timeout_seconds": 120,
            "created_at": created_at,
        }
        request_path = os.path.join(self.tools_dir, "tool_call_request.json")
        _write_json_atomic(request_path, request)
        request_errors = validate_runtime_file(self.repo_root, request_path, "tool_call_request")
        if request_errors:
            raise RuntimeError("; ".join(request_errors))

        self.logger.append(
            "TOOL_CALL",
            role=role,
            phase_id=self.phase,
            loop_id=loop_id,
            agent_id=self.agent_id,
            parent_id=parent_id,
            summary=f"{tool_name} request",
            prompt_template_id="tool_protocol",
            step_id=self.step_id,
            tool_call_id=call_id,
            content_extra={"tool_call": {"name": tool_name, "args": args}},
            metadata_extra=self.logger.tool_schema_context(tool_name),
        )

        started = time.monotonic()
        status = "success"
        exit_code: Optional[int] = None
        stdout_excerpt: Optional[str] = None
        stderr_excerpt: Optional[str] = None
        truncated = False
        artifact_ref: Optional[str] = None
        artifact_sha: Optional[str] = None
        result: dict = {}
        error_payload: Optional[dict] = None

        try:
            if tool_name == "exec_cmd":
                result, exit_code, stdout_excerpt, stderr_excerpt, truncated = self._exec_cmd(args)
            elif tool_name == "read_file":
                result = self._read_file(args)
            elif tool_name == "write_file":
                result, artifact_ref, artifact_sha = self._write_file(args)
            elif tool_name == "edit_file":
                result, artifact_ref, artifact_sha = self._edit_file(args)
            elif tool_name == "move_file":
                result, artifact_ref, artifact_sha = self._move_file(args)
            elif tool_name == "remove_file":
                result, artifact_ref, artifact_sha = self._remove_file(args)
            elif tool_name == "list_dir":
                result = self._list_dir(args)
            elif tool_name == "glob_match":
                result = self._glob_match(args)
            elif tool_name == "search_text":
                result = self._search_text(args)
            elif tool_name == "git_head":
                result = self._tool_git_head()
            elif tool_name == "git_show":
                result = self._git_show(args)
            elif tool_name == "git_diff":
                result = self._git_diff(args)
            elif tool_name == "validate_json":
                result = self._validate_json(args)
            elif tool_name == "checkpoint_branch":
                result = self._checkpoint_branch(args)
            elif tool_name == "checkpoint_commit":
                result = self._checkpoint_commit(args)
            elif tool_name == "apply_patch":
                result, artifact_ref, artifact_sha = self._apply_patch(args)
            else:
                raise RuntimeError(f"unsupported tool '{tool_name}'")
        except TimeoutError as e:
            status = "timeout"
            error_payload = {"code": "timeout", "message": str(e)}
        except PermissionError as e:
            status = "blocked"
            error_payload = {"code": "blocked", "message": str(e)}
        except Exception as e:  # noqa: BLE001
            status = "error"
            error_payload = {"code": "error", "message": str(e)}

        if not result:
            result = self._fallback_result(tool_name, args)
        if tool_name == "exec_cmd" and not isinstance(exit_code, int):
            exit_code = 1

        duration_ms = int((time.monotonic() - started) * 1000)
        result_id = f"result-{uuid.uuid4().hex[:12]}"
        summary = f"{tool_name} {status}"
        result_payload = {
            "protocol_version": PROTO_VER,
            "run_id": self.run_id,
            "call_id": call_id,
            "result_id": result_id,
            "agent_id": self.agent_id,
            "role": role,
            "phase": self.phase,
            "step_id": self.step_id,
            "tool_name": tool_name,
            "status": status,
            "summary": summary,
            "result": result,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "working_dir": self.repo_root,
            "stdout_excerpt": stdout_excerpt,
            "stderr_excerpt": stderr_excerpt,
            "truncated": bool(truncated),
            "artifact_ref": artifact_ref,
            "artifact_sha256": artifact_sha,
            "finished_at": _utc_now(),
        }
        if error_payload:
            result_payload["error"] = error_payload

        result_path = os.path.join(self.tools_dir, "tool_call_result.json")
        _write_json_atomic(result_path, result_payload)
        result_errors = validate_runtime_file(self.repo_root, result_path, "tool_call_result")
        if result_errors:
            raise RuntimeError("; ".join(result_errors))

        self.logger.append(
            "TOOL_RESULT",
            role=role,
            phase_id=self.phase,
            loop_id=loop_id,
            agent_id=self.agent_id,
            parent_id=parent_id,
            summary=summary,
            prompt_template_id="tool_protocol",
            step_id=self.step_id,
            tool_call_id=call_id,
            result_id=result_id,
            artifact_ref=artifact_ref,
            artifact_sha256=artifact_sha,
            content_extra={
                "tool_result": {
                    "command": result_payload.get("result", {}).get("command", tool_name),
                    "exit_code": int(exit_code) if isinstance(exit_code, int) else 0,
                    "duration_ms": duration_ms,
                    "working_dir": self.repo_root,
                    "stdout_excerpt": stdout_excerpt or "",
                    "stderr_excerpt": stderr_excerpt or "",
                    "truncated": bool(truncated),
                }
            },
            metadata_extra=self.logger.tool_schema_context(tool_name),
        )
        return result_payload

    def _read_file(self, args: dict) -> dict:
        path = args.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("read_file: missing path")
        abs_path, rel = self._resolve_path(path)
        if not self._is_allowed_path(rel, self.allowed_read_paths):
            raise PermissionError(f"read_file blocked by allowlist: {rel}")
        if not os.path.exists(abs_path):
            raise RuntimeError(f"file not found: {rel}")
        start_line = int(args.get("start_line", 1))
        end_line = args.get("end_line")
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if isinstance(end_line, int):
            chunk = lines[start_line - 1 : end_line]
            line_end: Optional[int] = end_line
        else:
            chunk = lines[start_line - 1 :]
            line_end = None
        content = "".join(chunk)
        max_chars = args.get("max_chars")
        truncated = False
        if isinstance(max_chars, int) and max_chars > 0 and len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
        return {
            "path": rel,
            "line_start": start_line,
            "line_end": line_end,
            "bytes_read": len("".join(chunk).encode("utf-8")),
            "content": content,
            "truncated": truncated,
        }

    def _write_file(self, args: dict) -> Tuple[dict, str, str]:
        path = args.get("path")
        content = args.get("content")
        if not isinstance(path, str) or not path:
            raise RuntimeError("write_file: missing path")
        if not isinstance(content, str):
            raise RuntimeError("write_file: missing content")
        abs_path, rel = self._resolve_path(path)
        self._assert_write_allowed(rel, "write_file")
        create_parents = bool(args.get("create_parents", True))
        mode = args.get("mode", "overwrite")
        if create_parents:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        if mode == "append":
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(content)
        elif mode == "create_new":
            if os.path.exists(abs_path):
                raise RuntimeError(f"write_file create_new target exists: {rel}")
            with open(abs_path, "x", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
        sha = "sha256:" + _sha256_file(abs_path)
        return {"path": rel, "bytes_written": len(content.encode("utf-8")), "content_sha256": sha}, rel, sha

    def _edit_file(self, args: dict) -> Tuple[dict, str, str]:
        path = args.get("path")
        edits = args.get("edits")
        if not isinstance(path, str) or not path:
            raise RuntimeError("edit_file: missing path")
        if not isinstance(edits, list) or not edits:
            raise RuntimeError("edit_file: missing edits")
        abs_path, rel = self._resolve_path(path)
        self._assert_write_allowed(rel, "edit_file")
        if not os.path.exists(abs_path):
            raise RuntimeError(f"edit_file target missing: {rel}")
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        applied = 0
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            search = edit.get("search")
            replace = edit.get("replace")
            regex = bool(edit.get("regex", False))
            occurrence = edit.get("occurrence")
            if not isinstance(search, str) or not isinstance(replace, str):
                continue
            if regex:
                count = 0 if not isinstance(occurrence, int) else 1
                new_content, n = re.subn(search, replace, content, count=count)
                if n > 0:
                    content = new_content
                    applied += n
            else:
                if isinstance(occurrence, int) and occurrence > 0:
                    idx = -1
                    start = 0
                    for _ in range(occurrence):
                        idx = content.find(search, start)
                        if idx == -1:
                            break
                        start = idx + len(search)
                    if idx != -1:
                        content = content[:idx] + replace + content[idx + len(search) :]
                        applied += 1
                else:
                    n = content.count(search)
                    if n > 0:
                        content = content.replace(search, replace)
                        applied += n
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        sha = "sha256:" + _sha256_text(content)
        return {"path": rel, "edits_applied": applied, "content_sha256": sha}, rel, sha

    def _move_file(self, args: dict) -> Tuple[dict, str, str]:
        src_path = args.get("src_path")
        dst_path = args.get("dst_path")
        overwrite = bool(args.get("overwrite", False))
        create_parents = bool(args.get("create_parents", True))
        if not isinstance(src_path, str) or not src_path.strip():
            raise RuntimeError("move_file: missing src_path")
        if not isinstance(dst_path, str) or not dst_path.strip():
            raise RuntimeError("move_file: missing dst_path")

        src_abs, src_rel = self._resolve_path(src_path)
        dst_abs, dst_rel = self._resolve_path(dst_path)
        self._assert_write_allowed(src_rel, "move_file")
        self._assert_write_allowed(dst_rel, "move_file")

        if not os.path.exists(src_abs):
            raise RuntimeError(f"move_file source missing: {src_rel}")
        if os.path.isdir(src_abs):
            raise RuntimeError(f"move_file source must be a file: {src_rel}")
        if os.path.exists(dst_abs) and not overwrite:
            raise RuntimeError(f"move_file destination exists: {dst_rel}")
        if create_parents:
            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        os.replace(src_abs, dst_abs)
        sha = "sha256:" + _sha256_file(dst_abs)
        return {"src_path": src_rel, "dst_path": dst_rel, "content_sha256": sha}, dst_rel, sha

    def _remove_file(self, args: dict) -> Tuple[dict, str, str]:
        path = args.get("path")
        missing_ok = bool(args.get("missing_ok", False))
        if not isinstance(path, str) or not path.strip():
            raise RuntimeError("remove_file: missing path")
        abs_path, rel = self._resolve_path(path)
        self._assert_write_allowed(rel, "remove_file")

        if not os.path.exists(abs_path):
            if not missing_ok:
                raise RuntimeError(f"remove_file target missing: {rel}")
            artifact_sha = "sha256:" + _sha256_text(f"missing:{rel}")
            return {"path": rel, "removed": False, "previously_missing": True}, rel, artifact_sha
        if os.path.isdir(abs_path):
            raise RuntimeError(f"remove_file target must be file: {rel}")
        prior_sha = "sha256:" + _sha256_file(abs_path)
        os.remove(abs_path)
        return {"path": rel, "removed": True, "previously_missing": False}, rel, prior_sha

    def _apply_patch(self, args: dict) -> Tuple[dict, str, str]:
        patch = args.get("patch")
        if not isinstance(patch, str) or not patch.strip():
            raise RuntimeError("apply_patch: missing patch")

        touched_paths: List[str] = []
        for line in patch.splitlines():
            if not (line.startswith("+++ ") or line.startswith("--- ")):
                continue
            path = line[4:].strip()
            if path == "/dev/null":
                continue
            if path.startswith("b/") or path.startswith("a/"):
                path = path[2:]
            if path and path not in touched_paths:
                touched_paths.append(path)

        if not touched_paths:
            raise RuntimeError("apply_patch: no target paths detected")

        for rel in touched_paths:
            self._assert_write_allowed(rel, "apply_patch")

        patch_path = os.path.join(self.tools_dir, f"patch-{uuid.uuid4().hex[:12]}.diff")
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch)
            if not patch.endswith("\n"):
                f.write("\n")

        try:
            result = _run_git(self.repo_root, ["apply", "--whitespace=nowarn", patch_path], check=False)
            if result.returncode != 0:
                msg = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(msg or "git apply failed")
        finally:
            if os.path.exists(patch_path):
                os.remove(patch_path)

        artifact_ref = touched_paths[0]
        artifact_abs, artifact_rel = self._resolve_path(artifact_ref)
        if os.path.exists(artifact_abs):
            patch_sha = "sha256:" + _sha256_file(artifact_abs)
        else:
            patch_sha = "sha256:" + _sha256_text(patch)
        hunk_count = sum(1 for line in patch.splitlines() if line.startswith("@@"))
        return {"files_changed": len(touched_paths), "hunks_applied": hunk_count}, artifact_rel, patch_sha

    def _list_dir(self, args: dict) -> dict:
        path = args.get("path")
        recursive = bool(args.get("recursive", False))
        include_hidden = bool(args.get("include_hidden", False))
        if not isinstance(path, str) or not path:
            raise RuntimeError("list_dir: missing path")
        abs_path, rel = self._resolve_path(path)
        if not self._is_allowed_path(rel, self.allowed_read_paths):
            raise PermissionError(f"list_dir blocked by allowlist: {rel}")
        if not os.path.isdir(abs_path):
            raise RuntimeError(f"directory not found: {rel}")
        entries: List[str] = []
        if recursive:
            for root, dirs, files in os.walk(abs_path):
                for name in dirs + files:
                    if not include_hidden and name.startswith("."):
                        continue
                    entries.append(_rel(self.repo_root, os.path.join(root, name)))
        else:
            for name in sorted(os.listdir(abs_path)):
                if not include_hidden and name.startswith("."):
                    continue
                entries.append(_rel(self.repo_root, os.path.join(abs_path, name)))
        return {"path": rel, "entries": entries}

    def _glob_match(self, args: dict) -> dict:
        path = args.get("path")
        patterns = args.get("patterns")
        if not isinstance(path, str) or not path:
            raise RuntimeError("glob_match: missing path")
        if not isinstance(patterns, list) or not patterns:
            raise RuntimeError("glob_match: missing patterns")
        abs_path, rel = self._resolve_path(path)
        if not self._is_allowed_path(rel, self.allowed_read_paths):
            raise PermissionError(f"glob_match blocked by allowlist: {rel}")
        matches: List[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            for matched in Path(abs_path).glob(pattern):
                matches.append(_rel(self.repo_root, str(matched)))
        return {"path": rel, "patterns": patterns, "matches": sorted(set(matches))}

    def _search_text(self, args: dict) -> dict:
        pattern = args.get("pattern")
        paths = args.get("paths")
        if not isinstance(pattern, str) or not pattern:
            raise RuntimeError("search_text: missing pattern")
        if not isinstance(paths, list) or not paths:
            raise RuntimeError("search_text: missing paths")
        regex = bool(args.get("use_regex", args.get("regex", False)))
        case_sensitive = bool(args.get("case_sensitive", True))
        results: List[dict] = []
        paths_scanned = 0
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags=flags) if regex else None
        for path in paths:
            if not isinstance(path, str) or not path:
                continue
            abs_path, rel = self._resolve_path(path)
            if not self._is_allowed_path(rel, self.allowed_read_paths):
                continue
            if not os.path.isfile(abs_path):
                continue
            paths_scanned += 1
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, start=1):
                    hit = bool(compiled.search(line)) if compiled else (pattern in line)
                    if hit:
                        results.append({"path": rel, "line": i, "text_excerpt": line.rstrip("\n")[:400]})
        return {"pattern": pattern, "paths_scanned": paths_scanned, "matches": results}

    def _tool_git_head(self) -> dict:
        head = _git_head(self.repo_root)
        if not head:
            raise RuntimeError("git_head unavailable")
        return {"head": head}

    def _git_show(self, args: dict) -> dict:
        rev = args.get("rev")
        if not isinstance(rev, str) or not rev:
            raise RuntimeError("git_show: missing rev")
        result = _run_git(self.repo_root, ["show", rev], check=False)
        content = (result.stdout or "") + ("\n" + (result.stderr or "") if result.stderr else "")
        excerpt = content[:4000]
        return {"rev": rev, "content_excerpt": excerpt, "truncated": len(content) > len(excerpt)}

    def _git_diff(self, args: dict) -> dict:
        base_rev = args.get("base_rev", args.get("rev_a"))
        head_rev = args.get("head_rev", args.get("rev_b"))
        context_lines = args.get("context_lines")
        paths = args.get("paths")
        cmd = ["diff"]
        if isinstance(context_lines, int) and context_lines >= 0:
            cmd.extend(["-U", str(context_lines)])
        if isinstance(base_rev, str) and base_rev and isinstance(head_rev, str) and head_rev:
            cmd.append(f"{base_rev}..{head_rev}")
        elif isinstance(base_rev, str) and base_rev:
            cmd.append(base_rev)
        elif isinstance(head_rev, str) and head_rev:
            cmd.append(head_rev)
        if isinstance(paths, list):
            normalized_paths = [p for p in paths if isinstance(p, str) and p]
            if normalized_paths:
                cmd.append("--")
                cmd.extend(normalized_paths)
        result = _run_git(self.repo_root, cmd, check=False)
        content = (result.stdout or "") + ("\n" + (result.stderr or "") if result.stderr else "")
        excerpt = content[:4000]
        return {
            "base_rev": base_rev if isinstance(base_rev, str) else None,
            "head_rev": head_rev if isinstance(head_rev, str) else None,
            "diff_excerpt": excerpt,
            "truncated": len(content) > len(excerpt),
        }

    def _validate_json(self, args: dict) -> dict:
        path = args.get("path")
        if not isinstance(path, str) or not path:
            raise RuntimeError("validate_json: missing path")
        abs_path, rel = self._resolve_path(path)
        errs = validate_file(self.repo_root, abs_path)
        return {"path": rel, "valid": not errs, "errors": errs}

    def _checkpoint_branch(self, args: dict) -> dict:
        branch = args.get("branch_name", args.get("branch"))
        if not isinstance(branch, str) or not branch:
            raise RuntimeError("checkpoint_branch: missing branch")
        if not branch.startswith("trinity/"):
            raise RuntimeError("checkpoint_branch: branch must start with 'trinity/'")
        if not self.enable_checkpoints:
            head = _git_head(self.repo_root)
            if not head:
                raise RuntimeError("checkpoint_branch skipped but git head unavailable")
            return {"branch_name": branch, "head": head}
        _run_git(self.repo_root, ["switch", "main"])
        exists = _run_git(self.repo_root, ["rev-parse", "--verify", branch], check=False).returncode == 0
        if exists:
            _run_git(self.repo_root, ["switch", branch])
        else:
            _run_git(self.repo_root, ["switch", "-c", branch])
        head = _git_head(self.repo_root)
        if not head:
            raise RuntimeError("checkpoint_branch completed but git head unavailable")
        return {"branch_name": branch, "head": head}

    def _checkpoint_commit(self, args: dict) -> dict:
        message = args.get("message")
        if not isinstance(message, str) or not message.strip():
            raise RuntimeError("checkpoint_commit: missing message")
        if not self.enable_checkpoints:
            head = _git_head(self.repo_root)
            if not head:
                raise RuntimeError("checkpoint_commit skipped but git head unavailable")
            return {"commit_sha": head, "message": message}
        _run_git(self.repo_root, ["add", "-A"])
        commit = _run_git(self.repo_root, ["commit", "-m", message], check=False)
        if commit.returncode != 0 and "nothing to commit" in (commit.stderr or commit.stdout):
            head = _git_head(self.repo_root)
            if not head:
                raise RuntimeError("checkpoint_commit noop but git head unavailable")
            return {"commit_sha": head, "message": message}
        if commit.returncode != 0:
            raise RuntimeError((commit.stderr or commit.stdout or "").strip())
        head = _git_head(self.repo_root)
        if not head:
            raise RuntimeError("checkpoint_commit completed but git head unavailable")
        return {"commit_sha": head, "message": message}

    def _exec_cmd(self, args: dict) -> Tuple[dict, int, str, str, bool]:
        command = args.get("command")
        mode = args.get("mode")
        if not isinstance(command, str) or not command.strip():
            raise RuntimeError("exec_cmd: missing command")
        if mode not in {"standard", "summarized"}:
            raise RuntimeError("exec_cmd: mode must be 'standard' or 'summarized'")
        # Unattended safety gate: block common secret-dumping commands.
        if _is_secret_dump_command(command):
            raise PermissionError("exec_cmd blocked by unattended command safety policy")

        readonly_snapshot: Optional[Set[str]] = None
        if self.phase in {"16c", "utility"}:
            self._assert_exec_cmd_readonly(command)
            readonly_snapshot = self._worktree_snapshot()

        timeout_seconds = int(args.get("timeout_seconds", 300))
        started = time.monotonic()
        env = os.environ.copy()
        runtime_home = os.path.join(self.repo_root, ".trinity", "runtime", "home")
        runtime_tmp = os.path.join(self.repo_root, ".trinity", "runtime", "tmp")
        os.makedirs(runtime_home, exist_ok=True)
        os.makedirs(runtime_tmp, exist_ok=True)
        env["HOME"] = runtime_home
        env["TMPDIR"] = runtime_tmp
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        truncated = False
        if mode == "summarized":
            stdout_lines = stdout.splitlines()
            stderr_lines = stderr.splitlines()
            stdout_out = "\n".join(stdout_lines[:40])
            stderr_out = "\n".join(stderr_lines[:20])
            truncated = len(stdout_lines) > 40 or len(stderr_lines) > 20
        else:
            stdout_out = stdout
            stderr_out = stderr
        if readonly_snapshot is not None:
            after_snapshot = self._worktree_snapshot()
            if after_snapshot != readonly_snapshot:
                raise PermissionError("exec_cmd blocked: readonly command produced worktree side effects")
        return (
            {
                "command": command,
                "mode": mode,
            },
            proc.returncode,
            stdout_out,
            stderr_out,
            truncated,
        )

    def _assert_exec_cmd_readonly(self, command: str) -> None:
        lowered = command.lower()
        write_operator_patterns = [
            re.compile(r"(^|[^<])>(>|)?"),
            re.compile(r"<<<?"),
            re.compile(r"\|\s*tee\b"),
        ]
        if any(p.search(lowered) for p in write_operator_patterns):
            raise PermissionError("exec_cmd blocked: shell redirection/tee is not allowed in readonly mode")

        if re.search(r"\b(cat|head|tail|sed)\s+[^|;]*\s>\s*", lowered):
            raise PermissionError("exec_cmd blocked: output redirection is not allowed in readonly mode")

        try:
            tokens = shlex.split(command, posix=True)
        except Exception:
            raise PermissionError("exec_cmd blocked: command parsing failed for readonly policy")
        if not tokens:
            raise PermissionError("exec_cmd blocked: empty command")

        binary = tokens[0].lower()
        mutating_bins = {
            "mv",
            "cp",
            "rm",
            "touch",
            "mkdir",
            "rmdir",
            "chmod",
            "chown",
            "ln",
            "install",
            "truncate",
            "dd",
        }
        if binary in mutating_bins:
            raise PermissionError(f"exec_cmd blocked: '{binary}' is disallowed in readonly mode")

        if binary == "sed" and "-i" in tokens:
            raise PermissionError("exec_cmd blocked: 'sed -i' is disallowed in readonly mode")

        if binary == "git":
            sub = tokens[1].lower() if len(tokens) > 1 else ""
            if sub not in READONLY_GIT_SUBCOMMANDS:
                raise PermissionError(f"exec_cmd blocked: git subcommand '{sub or '<none>'}' is not readonly")

        if binary in {"python", "python3"} and "-c" in tokens:
            idx = tokens.index("-c")
            snippet = tokens[idx + 1] if idx + 1 < len(tokens) else ""
            if re.search(r"\b(open|Path)\s*\(", snippet) and re.search(r"\b(write|append|touch|mkdir|unlink|remove|rename)\b", snippet):
                raise PermissionError("exec_cmd blocked: python -c snippet includes mutating filesystem operations")

        if binary in {"bash", "sh", "zsh"} and any(flag in tokens for flag in ("-c", "-lc")):
            idx = max(i for i, t in enumerate(tokens) if t in {"-c", "-lc"})
            nested = tokens[idx + 1] if idx + 1 < len(tokens) else ""
            if re.search(r"(^|[^<])>(>|)?|<<<?|\|\s*tee\b", nested):
                raise PermissionError("exec_cmd blocked: nested shell command uses redirection/tee in readonly mode")


class ContextResolver:
    def __init__(
        self,
        repo_root: str,
        step_id: str,
        milestone_path: str,
        anchor_path: str,
        *,
        allow_authority_fallback: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.step_id = step_id
        self.milestone_path = milestone_path
        self.anchor_path = anchor_path
        self.allow_authority_fallback = allow_authority_fallback
        self.seed_manifest_rel = "spec/common/seed_manifest.json"
        self.seed_manifest_path = os.path.join(repo_root, self.seed_manifest_rel)
        if not os.path.exists(self.seed_manifest_path):
            raise RuntimeError(f"seed manifest missing: {self.seed_manifest_rel}")
        self.seed_manifest = _read_json(self.seed_manifest_path)
        self.git_head = _git_head(repo_root)
        if not self.git_head:
            raise RuntimeError("git head commit not available; required for spec_ref grounding")
        self._bootstrap_selection_trace: List[dict] = []

    def seed_files_ordered(self, phase: str) -> List[str]:
        seeds = self.seed_manifest.get("seeds", [])
        seed_path_by_id: Dict[str, str] = {}
        for seed in seeds:
            if isinstance(seed, dict):
                sid = seed.get("seed_id")
                spath = seed.get("path")
                if isinstance(sid, str) and isinstance(spath, str):
                    seed_path_by_id[sid] = spath

        ordered: List[str] = []
        global_seed_order = self.seed_manifest.get("global_seed_order", [])
        if isinstance(global_seed_order, list):
            for sid in global_seed_order:
                if isinstance(sid, str) and sid in seed_path_by_id and seed_path_by_id[sid] not in ordered:
                    ordered.append(seed_path_by_id[sid])

        req = self.seed_manifest.get("step_requirements", {})
        phase_seed_ids = req.get(phase, []) if isinstance(req, dict) else []
        if isinstance(phase_seed_ids, list):
            for sid in phase_seed_ids:
                if isinstance(sid, str) and sid in seed_path_by_id and seed_path_by_id[sid] not in ordered:
                    ordered.append(seed_path_by_id[sid])
        return ordered

    def docs_policy(self) -> dict:
        policy = self.seed_manifest.get("docs_policy", {})
        if not isinstance(policy, dict):
            return {"doc_paths": ["docs/**", "README.md", "CHANGELOG.md"], "readme_required": True, "root_readme_required": True}
        doc_paths = policy.get("doc_paths")
        if not isinstance(doc_paths, list) or not doc_paths:
            doc_paths = ["docs/**", "README.md", "CHANGELOG.md"]
        return {
            "doc_paths": [p for p in doc_paths if isinstance(p, str) and p],
            "readme_required": bool(policy.get("readme_required", True)),
            "root_readme_required": bool(policy.get("root_readme_required", True)),
        }

    def _collect_json_ids(self, payload: Any, out: List[str]) -> None:
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(v, str) and (k == "id" or k.endswith("_id")) and v:
                    out.append(v)
                self._collect_json_ids(v, out)
        elif isinstance(payload, list):
            for item in payload:
                self._collect_json_ids(item, out)

    def _resolve_line_range(self, rel_path: str, item_id: str) -> Optional[str]:
        abs_path = os.path.join(self.repo_root, rel_path)
        if not os.path.exists(abs_path):
            return None
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        patterns = [
            re.compile(rf'"id"\s*:\s*"{re.escape(item_id)}"'),
            re.compile(rf'"[a-z_]*id"\s*:\s*"{re.escape(item_id)}"'),
            re.compile(rf'"{re.escape(item_id)}"'),
        ]
        for i, line in enumerate(lines, start=1):
            for p in patterns:
                if p.search(line):
                    return f"L{i}-L{i}"
        return None

    def resolve_spec_ref(self, spec_type: str, item_id: str) -> dict:
        preferred = SPEC_FILE_BY_TYPE.get(spec_type)
        candidates: List[str] = []
        if preferred:
            candidates.append(preferred)
        candidates.extend([p for p in CORE_AUTHORITY_FILES if p not in candidates])
        for rel_path in candidates:
            abs_path = os.path.join(self.repo_root, rel_path)
            if not os.path.exists(abs_path):
                continue
            try:
                payload = _read_json(abs_path)
            except Exception:
                continue
            ids: List[str] = []
            self._collect_json_ids(payload, ids)
            if item_id not in ids:
                continue
            line_range = self._resolve_line_range(rel_path, item_id)
            if not line_range:
                continue
            return {
                "type": spec_type,
                "id": item_id,
                "path": rel_path,
                "line_range": line_range,
                "commit_hash": self.git_head,
            }
        raise RuntimeError(f"Unable to resolve grounded spec ref: {spec_type}:{item_id}")

    def _tokenize_candidate_ids(self, value: str, source: str) -> List[dict]:
        out: List[dict] = []
        if not isinstance(value, str):
            return out
        for token in re.findall(r"[A-Za-z0-9_-]+", value):
            normalized = token.strip().lower()
            if not normalized or "-" not in normalized:
                continue
            if normalized.startswith(("fr-", "api-", "nfr-", "inv-", "fixture-")):
                ref_type = normalized.split("-", 1)[0]
                out.append({"type_hint": ref_type, "item_id": normalized, "source": source, "candidate_mode": "tokenized"})
            else:
                out.append({"type_hint": None, "item_id": normalized, "source": source, "candidate_mode": "tokenized"})
        return out

    def _roadmap_bootstrap_candidates(self) -> List[dict]:
        roadmap_path = os.path.join(self.repo_root, "spec", "14_roadmap.json")
        if not os.path.exists(roadmap_path):
            return []
        try:
            roadmap = _read_json(roadmap_path)
        except Exception:
            return []
        milestones = roadmap.get("milestones", [])
        if not isinstance(milestones, list):
            return []
        current = None
        for milestone in milestones:
            if isinstance(milestone, dict) and milestone.get("milestone_id") == self.step_id:
                current = milestone
                break
        if not isinstance(current, dict):
            return []
        values: List[Tuple[str, str]] = []

        candidates: List[dict] = []
        seen: Set[Tuple[Optional[str], str]] = set()

        def _add_candidate(type_hint: Optional[str], item_id: str, source: str, candidate_mode: str) -> None:
            key = (type_hint, item_id)
            if key in seen:
                return
            seen.add(key)
            candidates.append(
                {
                    "type_hint": type_hint,
                    "item_id": item_id,
                    "source": source,
                    "candidate_mode": candidate_mode,
                }
            )

        deliverables = current.get("deliverables", [])
        if isinstance(deliverables, list):
            for idx, deliverable in enumerate(deliverables):
                if not isinstance(deliverable, dict):
                    continue
                dtype = deliverable.get("type")
                did = deliverable.get("id")
                if dtype in {"fr", "api", "nfr", "inv", "fixture"} and isinstance(did, str) and did:
                    _add_candidate(dtype, did, f"roadmap.milestones[{self.step_id}].deliverables[{idx}]", "structured")

        tasks = current.get("tasks")
        if isinstance(tasks, list):
            for task_idx, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                acceptance = task.get("acceptance_criteria")
                if isinstance(acceptance, list):
                    for crit_idx, criterion in enumerate(acceptance):
                        if not isinstance(criterion, dict):
                            continue
                        fixture_ref = criterion.get("fixture_ref")
                        if isinstance(fixture_ref, str) and fixture_ref:
                            _add_candidate(
                                "fixture",
                                fixture_ref,
                                f"roadmap.milestones[{self.step_id}].tasks[{task_idx}].acceptance_criteria[{crit_idx}].fixture_ref",
                                "structured",
                            )

        for key in ("name", "user_story", "milestone_id"):
            v = current.get(key)
            if isinstance(v, str) and v.strip():
                values.append((v, f"roadmap.milestones[{self.step_id}].{key}"))
        for key in ("deliverables", "source_milestones"):
            arr = current.get(key)
            if isinstance(arr, list):
                for idx, entry in enumerate(arr):
                    if isinstance(entry, str) and entry.strip():
                        values.append((entry, f"roadmap.milestones[{self.step_id}].{key}[{idx}]"))
        if isinstance(tasks, list):
            for task_idx, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                task_id = task.get("task_id")
                desc = task.get("description")
                if isinstance(task_id, str) and task_id.strip():
                    values.append((task_id, f"roadmap.milestones[{self.step_id}].tasks[{task_idx}].task_id"))
                if isinstance(desc, str) and desc.strip():
                    values.append((desc, f"roadmap.milestones[{self.step_id}].tasks[{task_idx}].description"))

        for value, source in values:
            for candidate in self._tokenize_candidate_ids(value, source):
                type_hint = candidate.get("type_hint")
                item_id = candidate.get("item_id")
                if isinstance(item_id, str) and item_id:
                    _add_candidate(
                        type_hint if isinstance(type_hint, str) else None,
                        item_id,
                        str(candidate.get("source", source)),
                        str(candidate.get("candidate_mode", "tokenized")),
                    )
        return candidates

    def _first_available_ref_for_type(self, spec_type: str) -> Optional[dict]:
        rel_path = SPEC_FILE_BY_TYPE.get(spec_type)
        if not isinstance(rel_path, str):
            return None
        abs_path = os.path.join(self.repo_root, rel_path)
        if not os.path.exists(abs_path):
            return None
        try:
            payload = _read_json(abs_path)
        except Exception:
            return None
        ids: List[str] = []
        self._collect_json_ids(payload, ids)
        for item_id in ids:
            try:
                return self.resolve_spec_ref(spec_type, item_id)
            except Exception:
                continue
        return None

    def _bootstrap_required_spec_refs(self) -> List[dict]:
        refs: List[dict] = []
        seen: Set[Tuple[str, str]] = set()
        trace: List[dict] = []
        self._bootstrap_selection_trace = []

        def _try_add(spec_type: str, item_id: str, source: str, selection_mode: str) -> None:
            key = (spec_type, item_id)
            if key in seen:
                return
            preferred_path = SPEC_FILE_BY_TYPE.get(spec_type)
            try:
                ref = self.resolve_spec_ref(spec_type, item_id)
            except Exception:
                return
            if isinstance(preferred_path, str) and ref.get("path") != preferred_path:
                return
            refs.append(ref)
            seen.add(key)
            trace.append(
                {
                    "spec_type": spec_type,
                    "id": item_id,
                    "selected_from": source,
                    "selection_mode": selection_mode,
                    "path": str(ref.get("path") or ""),
                    "line_range": str(ref.get("line_range") or ""),
                }
            )

        for candidate in self._roadmap_bootstrap_candidates():
            maybe_type = candidate.get("type_hint") if isinstance(candidate.get("type_hint"), str) else None
            item_id = candidate.get("item_id")
            source = candidate.get("source")
            candidate_mode = candidate.get("candidate_mode")
            if not isinstance(item_id, str) or not item_id:
                continue
            source_label = source if isinstance(source, str) and source else "roadmap"
            selection_mode = candidate_mode if isinstance(candidate_mode, str) and candidate_mode else "tokenized"
            if isinstance(maybe_type, str):
                _try_add(maybe_type, item_id, source_label, selection_mode)
            else:
                for spec_type in ("fr", "api", "nfr", "inv", "fixture"):
                    _try_add(spec_type, item_id, source_label, "tokenized")
            if len(refs) >= 8:
                break

        if not refs and self.allow_authority_fallback:
            for spec_type in ("fr", "api", "nfr", "inv", "fixture"):
                candidate = self._first_available_ref_for_type(spec_type)
                if isinstance(candidate, dict):
                    candidate_type = candidate.get("type")
                    candidate_id = candidate.get("id")
                    if isinstance(candidate_type, str) and isinstance(candidate_id, str):
                        key = (candidate_type, candidate_id)
                    else:
                        key = None
                    if key is not None and key not in seen:
                        refs.append(candidate)
                        seen.add(key)
                        trace.append(
                            {
                                "spec_type": candidate_type,
                                "id": candidate_id,
                                "selected_from": f"authority:{SPEC_FILE_BY_TYPE.get(spec_type, '')}",
                                "selection_mode": "authority_fallback",
                                "path": str(candidate.get("path") or ""),
                                "line_range": str(candidate.get("line_range") or ""),
                            }
                        )
                if refs:
                    break
        self._bootstrap_selection_trace = trace
        return refs

    def bootstrap_selection_trace(self) -> List[dict]:
        return [dict(item) for item in self._bootstrap_selection_trace if isinstance(item, dict)]

    def required_spec_refs(self, phase: str, milestone_payload: Optional[dict]) -> List[dict]:
        refs: List[dict] = []
        seen: set[Tuple[str, str]] = set()
        self._bootstrap_selection_trace = []
        checklist = []
        if isinstance(milestone_payload, dict):
            plan = milestone_payload.get("plan", {})
            if isinstance(plan, dict):
                spec_alignment = plan.get("spec_alignment", {})
                if isinstance(spec_alignment, dict):
                    checklist = spec_alignment.get("checklist", [])
        if isinstance(checklist, list):
            for item in checklist:
                if not isinstance(item, dict):
                    continue
                ref = item.get("spec_ref")
                if not isinstance(ref, dict):
                    continue
                rtype = ref.get("type")
                rid = ref.get("id")
                if isinstance(rtype, str) and isinstance(rid, str):
                    key = (rtype, rid)
                    if key in seen:
                        continue
                    try:
                        resolved = self.resolve_spec_ref(rtype, rid)
                    except Exception:
                        continue
                    refs.append(resolved)
                    seen.add(key)
        if not refs and phase == "16a":
            refs = self._bootstrap_required_spec_refs()
        return refs

    def _pattern_roots(self, patterns: List[str]) -> List[str]:
        roots: List[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            root = pattern.split("*", 1)[0].rstrip("/")
            if not root:
                continue
            if root not in roots:
                roots.append(root)
        return roots

    def context_pack(
        self,
        phase: str,
        milestone_payload: Optional[dict],
        target_file_patterns: List[str],
        test_commands: Optional[List[Any]] = None,
    ) -> dict:
        seed_files = self.seed_files_ordered(phase)
        refs = self.required_spec_refs(phase, milestone_payload)
        read_paths: List[str] = []
        # Phase-differentiated read paths (C-1 finding):
        # - .trinity/logging is never needed by children (capture policy is parent-owned)
        # - .trinity/runtime/tools is excluded from utility agents (they use inline protocol)
        phase_runtime_paths: List[str] = [".trinity/runtime/spawns"]
        if phase != "utility":
            phase_runtime_paths.append(".trinity/runtime/tools")
        for rel in seed_files + CORE_AUTHORITY_FILES + [
            self.seed_manifest_rel,
            _rel(self.repo_root, self.milestone_path),
            _rel(self.repo_root, self.anchor_path),
        ] + phase_runtime_paths:
            if rel not in read_paths:
                read_paths.append(rel)
        for root in self._pattern_roots(target_file_patterns):
            if root not in read_paths:
                read_paths.append(root)

        write_paths = [
            ".trinity/runtime/workspace",
            "spec/impl_context",
            "spec/16_impl_context.json",
        ]
        for root in self._pattern_roots(target_file_patterns):
            if root not in write_paths:
                write_paths.append(root)
        docs = self.docs_policy()
        for root in self._pattern_roots(docs.get("doc_paths", [])):
            if root not in write_paths:
                write_paths.append(root)

        payload: dict = {
            "protocol_version": PROTO_VER,
            "phase": phase,
            "step_id": self.step_id,
            "seed_manifest_path": self.seed_manifest_rel,
            "seed_files_ordered": seed_files,
            "required_spec_refs": refs,
            "artifact_refs": {
                "milestone_context_path": _rel(self.repo_root, self.milestone_path),
                "anchor_path": _rel(self.repo_root, self.anchor_path),
                "workspace_refs": [f".trinity/workspace/{self.step_id}/"],
            },
            "allowed_read_paths": read_paths,
            "allowed_write_paths": write_paths,
            "target_file_patterns": target_file_patterns,
            "docs_policy": docs,
        }
        bootstrap_trace = self.bootstrap_selection_trace()
        if phase == "16a" and bootstrap_trace:
            payload["bootstrap_ref_trace"] = bootstrap_trace
        if phase in {"16b", "16c"}:
            tcmds = test_commands or []
            payload["test_contract"] = {
                "test_commands": tcmds,
                "success_markers": ["PASSED", "passed", "OK", "SUCCESS", "✓", "0 failures", "0 failed", "0 errors"],
            }
        return payload


class TrinityRuntime:
    def __init__(
        self,
        repo_root: str,
        config: TrinityConfig,
        *,
        step_id: Optional[str],
        resume: bool = False,
        answers: Optional[List[str]] = None,
        resume_run_id: Optional[str] = None,
    ) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.config = config
        self.step_id = step_id
        self.resume = resume
        self.resume_answers = [a.strip() for a in (answers or []) if isinstance(a, str) and a.strip()]
        self.resume_run_id = resume_run_id.strip() if isinstance(resume_run_id, str) and resume_run_id.strip() else None
        self.run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.root_agent_id = f"orchestrator-{uuid.uuid4().hex[:12]}"
        self.retry_caps = {
            "planner": int(self.config.retry_cap_planner),
            "builder": int(self.config.retry_cap_builder),
            "verifier": int(self.config.retry_cap_verifier),
            "milestone": int(self.config.retry_cap_milestone),
        }
        mode = (self.config.execution_mode or "").strip().lower()
        if mode not in {"llm", "deterministic"}:
            raise RuntimeError("runtime.execution_mode must be one of: llm, deterministic")
        self.execution_mode = mode
        self._llm_client_instance: Optional[OpenAICompatibleClient] = None
        self._runtime_schema_registry = SchemaRegistry(self.repo_root)
        store = {uri: Resource.from_contents(schema) for uri, schema in self._runtime_schema_registry.store.items()}
        self._runtime_schema_refs = Registry().with_resources(store.items())
        self._runtime_validator_cache: Dict[str, Draft202012Validator] = {}

    def _llm_client(self) -> OpenAICompatibleClient:
        if self._llm_client_instance is None:
            self._llm_client_instance = OpenAICompatibleClient(
                api_base=self.config.llm_api_base,
                model=self.config.llm_model,
                timeout_seconds=max(1, int(self.config.llm_timeout)),
                api_key_env=self.config.llm_api_key_env,
                temperature=self.config.llm_temperature,
                top_p=self.config.llm_top_p,
                max_tokens=max(128, int(self.config.llm_max_tokens)),
            )
        return self._llm_client_instance

    def _runtime_schema_validator(self, schema_uri: str) -> Draft202012Validator:
        cached = self._runtime_validator_cache.get(schema_uri)
        if cached is not None:
            return cached
        schema = self._runtime_schema_registry.load(schema_uri)
        validator = Draft202012Validator(
            schema,
            registry=self._runtime_schema_refs,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        self._runtime_validator_cache[schema_uri] = validator
        return validator

    def _validate_payload_against_schema(self, schema_uri: str, payload: Any) -> List[str]:
        validator = self._runtime_schema_validator(schema_uri)
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        rendered: List[str] = []
        for err in errors:
            path = "/".join(str(p) for p in err.path)
            rendered.append(f"{path}: {err.message}" if path else str(err.message))
        return rendered

    def _log_utility_schema_validation(
        self,
        *,
        logger: SessionLogger,
        utility_role: str,
        utility_child_id: str,
        parent_child_id: str,
        loop_id: str,
        turn: int,
        schema_label: str,
        passed: bool,
        errors: Optional[List[str]] = None,
    ) -> None:
        details = ""
        if errors:
            details = ": " + "; ".join(errors[:3])
        logger.append(
            "VALIDATION",
            role=utility_role,
            phase_id="utility",
            loop_id=f"{loop_id}-utility-{turn}",
            agent_id=utility_child_id,
            parent_id=parent_child_id,
            summary=f"{utility_role} {schema_label} schema {'pass' if passed else 'fail'}{details}",
            prompt_template_id=_prompt_path_for("utility", utility_role),
            step_id=self.step_id,
            content_extra=self._phase_validation_content(
                passed=passed,
                schema_status="pass" if passed else "fail",
                deep_status="pass" if passed else "fail",
                governance_status="n/a",
            ),
        )

    def _load_prompt_text(self, phase: str, *, role: Optional[str] = None) -> str:
        rel = _prompt_path_for(phase, role)
        path = os.path.join(self.repo_root, rel)
        if not os.path.exists(path):
            raise RuntimeError(f"Prompt source missing for phase {phase}: {rel}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _normalize_llm_task_result(
        self,
        *,
        action_obj: dict,
        child_id: str,
        role: str,
        phase: str,
        milestone_path: str,
    ) -> dict:
        raw = action_obj.get("task_result", {})
        result = raw if isinstance(raw, dict) else {}
        status = result.get("status")
        if status not in {"success", "blocked", "failed", "questions"}:
            status = "failed"

        normalized = {
            "protocol_version": PROTO_VER,
            "child_id": child_id,
            "role": role,
            "phase": phase,
            "step_id": self.step_id,
            "status": status,
            "summary": str(result.get("summary") or action_obj.get("summary") or f"{role} {status}"),
            "artifacts": result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
        }
        milestone_rel = _rel(self.repo_root, milestone_path)
        if status == "success" and phase in {"16a", "16b", "16c"} and not normalized["artifacts"]:
            normalized["artifacts"] = [milestone_rel]

        findings = result.get("findings")
        if status in {"blocked", "failed"}:
            if isinstance(findings, list) and findings:
                normalized["findings"] = findings
            else:
                normalized["findings"] = [
                    self._finding(
                        f"llm-{phase}-missing-findings",
                        "gap",
                        "blocking",
                        "LLM returned blocked/failed status without findings payload.",
                    )
                ]

        if status == "questions":
            questions = result.get("questions")
            if isinstance(questions, list) and questions:
                normalized["questions"] = [str(q) for q in questions if isinstance(q, str) and q.strip()]
            if not normalized.get("questions"):
                normalized["questions"] = ["Clarification required by LLM phase output."]
            normalized["artifacts"] = []

        return normalized

    def _validate_loop_checkpoint(self, action_obj: dict, phase: str) -> Optional[str]:
        if phase not in {"16a", "16b", "16c"}:
            return None
        checkpoint = action_obj.get("loop_checkpoint")
        if not isinstance(checkpoint, dict):
            return (
                "final_result must include loop_checkpoint object with draft/review/refine evidence "
                "for phases 16a/16b/16c."
            )
        missing: List[str] = []
        for stage in ("draft", "review", "refine"):
            if not _loop_evidence_present(checkpoint.get(stage)):
                missing.append(stage)
        if missing:
            return (
                "loop_checkpoint is missing required evidence for: "
                + ", ".join(missing)
                + ". Provide concrete Draft/Review/Refine evidence."
            )
        return None

    def _validate_utility_loop_checkpoint(self, action_obj: dict, utility_role: str) -> Optional[str]:
        if utility_role not in {"Researcher", "Summarizer", "Auditor"}:
            return None
        checkpoint = action_obj.get("loop_checkpoint")
        if not isinstance(checkpoint, dict):
            return (
                "utility final_result must include loop_checkpoint object with draft/review/refine evidence "
                f"for utility role '{utility_role}'."
            )
        missing: List[str] = []
        for stage in ("draft", "review", "refine"):
            if not _loop_evidence_present(checkpoint.get(stage)):
                missing.append(stage)
        if missing:
            return (
                "utility loop_checkpoint is missing required evidence for: "
                + ", ".join(missing)
                + ". Provide concrete Draft/Review/Refine evidence."
            )
        return None

    def _run_utility_role(
        self,
        *,
        llm_client: OpenAICompatibleClient,
        logger: SessionLogger,
        parent_child_id: str,
        parent_phase: str,
        utility_role: str,
        utility_call: dict,
        context_pack: dict,
        milestone_path: str,
        loop_id: str,
    ) -> dict:
        if utility_role not in UTILITY_PROMPT_MAP:
            return {
                "status": "blocked",
                "summary": f"Unsupported utility role '{utility_role}'",
                "findings": [self._finding("utility-role-unsupported", "policy", "blocking", f"Unsupported utility role '{utility_role}'.")],
                "utility_payload": {},
            }

        utility_child_id = f"{utility_role.lower()}-{uuid.uuid4().hex[:8]}"
        utility_tools = ToolExecutor(
            self.repo_root,
            logger,
            self.run_id,
            agent_id=utility_child_id,
            phase="utility",
            step_id=self.step_id,
            allowed_read_paths=context_pack.get("allowed_read_paths", []),
            allowed_write_paths=context_pack.get("allowed_write_paths", []),
            target_file_patterns=context_pack.get("target_file_patterns", []),
            docs_policy=context_pack.get("docs_policy", {}),
            protected_write_paths=(
                ([context_pack.get("seed_manifest_path")] if isinstance(context_pack.get("seed_manifest_path"), str) else [])
                + (
                    context_pack.get("seed_files_ordered", [])
                    if isinstance(context_pack.get("seed_files_ordered"), list)
                    else []
                )
            ),
            enable_checkpoints=False,
        )

        objective = utility_call.get("objective")
        if not isinstance(objective, str) or not objective.strip():
            objective = utility_call.get("summary")
        if not isinstance(objective, str) or not objective.strip():
            objective = f"Utility support for {parent_phase}"
        utility_input = utility_call.get("input") if isinstance(utility_call.get("input"), dict) else {}
        utility_prompt = self._load_prompt_text("utility", role=utility_role)
        utility_protocol = (
            "Return JSON only. Supported actions:\n"
            "1) Tool call:\n"
            '{"action":"tool_call","summary":"...","tool_call":{"tool_name":"<tool>","args":{...}}}\n'
            "2) Final result:\n"
            '{"action":"final_result","summary":"...","loop_checkpoint":{"draft":"...","review":"...","refine":"..."},"utility_result":{"status":"ready|questions|blocked","summary":"...","open_questions":[...],"errors":[...],"findings":[...]}}\n'
            "Rules:\n"
            "- Never fabricate evidence.\n"
            "- Stay within context_pack constraints.\n"
            "- Keep output assumption-free."
        )
        utility_payload = {
            "protocol_version": PROTO_VER,
            "role": utility_role,
            "phase": "utility",
            "step_id": self.step_id,
            "objective": objective,
            "input": utility_input,
            "context_pack": context_pack,
            "milestone_artifact_ref": _rel(self.repo_root, milestone_path),
            "tool_catalog_ref": ".trinity/runtime/tools/catalog.json",
        }
        messages: List[dict] = [
            {"role": "system", "content": utility_prompt},
            {"role": "system", "content": utility_protocol},
            {"role": "user", "content": json.dumps(utility_payload, ensure_ascii=False)},
        ]
        max_turns = max(1, min(4, int(self.config.max_child_turns)))
        for turn in range(1, max_turns + 1):
            request_material = json.dumps({"messages": messages}, ensure_ascii=False)
            try:
                llm_text, llm_usage = llm_client.chat(messages)
            except Exception as e:  # noqa: BLE001
                return {
                    "status": "blocked",
                    "summary": f"{utility_role} blocked: LLM request failed",
                    "findings": [self._finding("utility-llm-request-failed", "policy", "blocking", str(e))],
                    "utility_payload": {},
                }

            metadata_extra = None
            if isinstance(llm_usage, dict):
                prompt_toks = llm_usage.get("prompt_tokens")
                completion_toks = llm_usage.get("completion_tokens")
                total_toks = llm_usage.get("total_tokens")
                if all(isinstance(v, int) for v in (prompt_toks, completion_toks, total_toks)):
                    metadata_extra = {
                        "token_usage": {
                            "prompt": int(prompt_toks),
                            "completion": int(completion_toks),
                            "total": int(total_toks),
                        }
                    }

            logger.append(
                "MESSAGE",
                role=utility_role,
                phase_id="utility",
                loop_id=f"{loop_id}-utility-{turn}",
                agent_id=utility_child_id,
                parent_id=parent_child_id,
                summary=f"{utility_role} utility turn {turn}",
                prompt_template_id=_prompt_path_for("utility", utility_role),
                step_id=self.step_id,
                metadata_extra=metadata_extra,
                prompt_material_override=request_material,
                response_material_override=llm_text,
            )

            action_obj = _extract_json_object(llm_text)
            if not isinstance(action_obj, dict):
                return {
                    "status": "blocked",
                    "summary": f"{utility_role} blocked: invalid utility JSON action",
                    "findings": [
                        self._finding(
                            "utility-invalid-json",
                            "policy",
                            "blocking",
                            "Utility role output could not be parsed as a JSON action object.",
                        )
                    ],
                    "utility_payload": {},
                }
            action = action_obj.get("action")
            if action == "tool_call":
                tool_call = action_obj.get("tool_call", {})
                tool_name = tool_call.get("tool_name") if isinstance(tool_call, dict) else None
                args = tool_call.get("args") if isinstance(tool_call, dict) else None
                if not isinstance(tool_name, str) or not isinstance(args, dict):
                    return {
                        "status": "blocked",
                        "summary": f"{utility_role} blocked: malformed utility tool_call",
                        "findings": [
                            self._finding(
                                "utility-malformed-tool-call",
                                "policy",
                                "blocking",
                                "Utility role returned tool_call without valid tool_name/args.",
                            )
                        ],
                        "utility_payload": {},
                    }
                tool_result = utility_tools.call(
                    tool_name,
                    args,
                    role=utility_role,
                    parent_id=parent_child_id,
                    loop_id=f"{loop_id}-utility-{turn}",
                )
                messages.append({"role": "assistant", "content": json.dumps(action_obj, ensure_ascii=False)})
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "tool_result": tool_result,
                                "instruction": "Continue with next action or final_result.",
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                continue

            if action == "final_result":
                checkpoint_error = self._validate_utility_loop_checkpoint(action_obj, utility_role)
                if checkpoint_error:
                    return {
                        "status": "blocked",
                        "summary": f"{utility_role} blocked: missing utility loop checkpoint evidence",
                        "findings": [
                            self._finding(
                                "utility-loop-checkpoint-missing",
                                "policy",
                                "blocking",
                                checkpoint_error,
                            )
                        ],
                        "utility_payload": {},
                    }
                utility_result = action_obj.get("utility_result", {})
                if not isinstance(utility_result, dict):
                    self._log_utility_schema_validation(
                        logger=logger,
                        utility_role=utility_role,
                        utility_child_id=utility_child_id,
                        parent_child_id=parent_child_id,
                        loop_id=loop_id,
                        turn=turn,
                        schema_label="utility_result",
                        passed=False,
                        errors=["utility_result must be an object"],
                    )
                    return {
                        "status": "blocked",
                        "summary": f"{utility_role} blocked: malformed utility_result payload",
                        "findings": [
                            self._finding(
                                "utility-malformed-result",
                                "policy",
                                "blocking",
                                "Utility role returned final_result without utility_result object.",
                            )
                        ],
                        "utility_payload": {},
                    }
                schema_errors = self._validate_payload_against_schema(UTILITY_RESULT_SCHEMA_URI, utility_result)
                self._log_utility_schema_validation(
                    logger=logger,
                    utility_role=utility_role,
                    utility_child_id=utility_child_id,
                    parent_child_id=parent_child_id,
                    loop_id=loop_id,
                    turn=turn,
                    schema_label="utility_result",
                    passed=not schema_errors,
                    errors=schema_errors,
                )
                if schema_errors:
                    return {
                        "status": "blocked",
                        "summary": f"{utility_role} blocked: utility_result schema validation failed",
                        "findings": [
                            self._finding(
                                "utility-result-schema-invalid",
                                "policy",
                                "blocking",
                                "; ".join(schema_errors[:3]),
                            )
                        ],
                        "utility_payload": utility_result,
                    }
                utility_status = utility_result.get("status")
                mapped_status = (
                    "success"
                    if utility_status == "ready"
                    else "questions"
                    if utility_status == "questions"
                    else "blocked"
                )
                findings = utility_result.get("findings")
                questions = utility_result.get("open_questions")
                return {
                    "status": mapped_status,
                    "summary": str(utility_result.get("summary") or action_obj.get("summary") or f"{utility_role} completed"),
                    "findings": findings if isinstance(findings, list) else [],
                    "questions": [str(q) for q in questions if isinstance(q, str)] if isinstance(questions, list) else [],
                    "utility_payload": utility_result,
                }

            return {
                "status": "blocked",
                "summary": f"{utility_role} blocked: unsupported utility action",
                "findings": [
                    self._finding(
                        "utility-unsupported-action",
                        "policy",
                        "blocking",
                        f"Unsupported utility action '{action}'.",
                    )
                ],
                "utility_payload": {},
            }

        return {
            "status": "blocked",
            "summary": f"{utility_role} blocked: max utility turns exceeded",
            "findings": [
                self._finding(
                    "utility-turn-cap",
                    "policy",
                    "blocking",
                    "Utility role exceeded max turns without final_result.",
                )
            ],
            "utility_payload": {},
        }

    def _llm_phase_handler(self, milestone_path: str, logger: SessionLogger, *, phase: str, role: str):
        def _handler(task_input: dict, context_pack: dict, child_id: str) -> dict:
            llm_client = self._llm_client()
            tools = ToolExecutor(
                self.repo_root,
                logger,
                self.run_id,
                agent_id=child_id,
                phase=phase,
                step_id=self.step_id,
                allowed_read_paths=context_pack.get("allowed_read_paths", []),
                allowed_write_paths=context_pack.get("allowed_write_paths", []),
                target_file_patterns=context_pack.get("target_file_patterns", []),
                docs_policy=context_pack.get("docs_policy", {}),
                protected_write_paths=(
                    ([context_pack.get("seed_manifest_path")] if isinstance(context_pack.get("seed_manifest_path"), str) else [])
                    + (
                        context_pack.get("seed_files_ordered", [])
                        if isinstance(context_pack.get("seed_files_ordered"), list)
                        else []
                    )
                ),
                enable_checkpoints=self.config.checkpoint_commits,
            )

            prompt_text = self._load_prompt_text(phase, role=role)
            protocol_instructions = (
                "Return JSON only. Supported actions:\n"
                "1) Tool call:\n"
                '{"action":"tool_call","summary":"...","tool_call":{"tool_name":"<tool>","args":{...}}}\n'
                "2) Final result:\n"
                '{"action":"final_result","summary":"...","loop_checkpoint":{"draft":"...","review":"...","refine":"..."},"task_result":{"status":"success|blocked|failed|questions","summary":"...","artifacts":[...],"findings":[...],"questions":[...]}}\n'
                "3) Utility role invocation (16a/16b/16c only):\n"
                '{"action":"utility_call","summary":"...","utility_call":{"role":"Researcher|ToolUser|Summarizer|Auditor","objective":"...","input":{...}}}\n'
                "Rules:\n"
                "- Never fabricate files or test outcomes.\n"
                "- Use only listed tools when needed.\n"
                "- For phases 16a/16b/16c, final_result MUST include loop_checkpoint with draft/review/refine evidence.\n"
                "- For success in phases 16a/16b/16c, include milestone artifact in artifacts.\n"
                "- Keep all outputs assumption-free and schema-compliant."
            )

            initial_payload = {
                "task_input": task_input,
                "context_pack": context_pack,
                "milestone_artifact_ref": _rel(self.repo_root, milestone_path),
                "tool_catalog_ref": ".trinity/runtime/tools/catalog.json",
                "result_schema_hint": "schema/trinity/task_result.schema.json",
            }
            messages: List[dict] = [
                {"role": "system", "content": prompt_text},
                {"role": "system", "content": protocol_instructions},
                {"role": "user", "content": json.dumps(initial_payload, ensure_ascii=False)},
            ]

            max_turns = max(1, int(self.config.max_child_turns))
            for turn in range(1, max_turns + 1):
                request_material = json.dumps({"messages": messages}, ensure_ascii=False)
                try:
                    llm_text, llm_usage = llm_client.chat(messages)
                except Exception as e:  # noqa: BLE001
                    return self._task_result(
                        child_id=child_id,
                        role=role,
                        phase=phase,
                        status="blocked",
                        summary=f"{role} blocked: LLM request failed",
                        artifacts=[],
                        findings=[self._finding(f"{phase}-llm-request-failed", "policy", "blocking", str(e))],
                    )

                metadata_extra = None
                if isinstance(llm_usage, dict):
                    prompt_toks = llm_usage.get("prompt_tokens")
                    completion_toks = llm_usage.get("completion_tokens")
                    total_toks = llm_usage.get("total_tokens")
                    if all(isinstance(v, int) for v in (prompt_toks, completion_toks, total_toks)):
                        metadata_extra = {
                            "token_usage": {
                                "prompt": int(prompt_toks),
                                "completion": int(completion_toks),
                                "total": int(total_toks),
                            }
                        }

                logger.append(
                    "MESSAGE",
                    role=role,
                    phase_id=phase,
                    loop_id=f"l2-{turn}",
                    agent_id=child_id,
                    parent_id=self.root_agent_id,
                    summary=f"{role} LLM turn {turn}",
                    prompt_template_id=_prompt_path_for(phase, role),
                    step_id=self.step_id,
                    metadata_extra=metadata_extra,
                    prompt_material_override=request_material,
                    response_material_override=llm_text,
                )

                action_obj = _extract_json_object(llm_text)
                if not isinstance(action_obj, dict):
                    return self._task_result(
                        child_id=child_id,
                        role=role,
                        phase=phase,
                        status="blocked",
                        summary=f"{role} blocked: invalid LLM JSON action",
                        artifacts=[],
                        findings=[
                            self._finding(
                                f"{phase}-llm-invalid-json",
                                "policy",
                                "blocking",
                                "LLM output could not be parsed as a JSON action object.",
                            )
                        ],
                    )

                action = action_obj.get("action")
                if action == "tool_call":
                    tool_call = action_obj.get("tool_call", {})
                    tool_name = tool_call.get("tool_name") if isinstance(tool_call, dict) else None
                    args = tool_call.get("args") if isinstance(tool_call, dict) else None
                    if not isinstance(tool_name, str) or not isinstance(args, dict):
                        return self._task_result(
                            child_id=child_id,
                            role=role,
                            phase=phase,
                            status="blocked",
                            summary=f"{role} blocked: malformed tool_call action",
                            artifacts=[],
                            findings=[
                                self._finding(
                                    f"{phase}-llm-malformed-tool-call",
                                    "policy",
                                    "blocking",
                                    "LLM returned tool_call action without valid tool_name/args.",
                                )
                            ],
                        )
                    tool_result = tools.call(
                        tool_name,
                        args,
                        role=role,
                        parent_id=self.root_agent_id,
                        loop_id=f"l2-{turn}",
                    )
                    messages.append({"role": "assistant", "content": json.dumps(action_obj, ensure_ascii=False)})
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "tool_result": tool_result,
                                    "instruction": "Continue with next action or final_result.",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )
                    continue

                if action == "utility_call":
                    if phase not in {"16a", "16b", "16c"}:
                        return self._task_result(
                            child_id=child_id,
                            role=role,
                            phase=phase,
                            status="blocked",
                            summary=f"{role} blocked: utility_call unsupported in phase {phase}",
                            artifacts=[],
                            findings=[
                                self._finding(
                                    f"{phase}-utility-call-unsupported",
                                    "policy",
                                    "blocking",
                                    "utility_call is only supported for 16a/16b/16c phase handlers.",
                                )
                            ],
                        )
                    utility_call = action_obj.get("utility_call", {})
                    utility_call_schema_errors = self._validate_payload_against_schema(
                        UTILITY_CALL_SCHEMA_URI,
                        utility_call,
                    )
                    logger.append(
                        "VALIDATION",
                        role=role,
                        phase_id=phase,
                        loop_id=f"l{turn}",
                        agent_id=child_id,
                        parent_id=self.root_agent_id,
                        summary=(
                            "utility_call schema pass"
                            if not utility_call_schema_errors
                            else "utility_call schema fail: " + "; ".join(utility_call_schema_errors[:3])
                        ),
                        prompt_template_id=_prompt_path_for(phase, role),
                        step_id=self.step_id,
                        content_extra=self._phase_validation_content(
                            passed=not utility_call_schema_errors,
                            schema_status="pass" if not utility_call_schema_errors else "fail",
                            deep_status="pass" if not utility_call_schema_errors else "fail",
                            governance_status="n/a",
                        ),
                    )
                    if utility_call_schema_errors:
                        return self._task_result(
                            child_id=child_id,
                            role=role,
                            phase=phase,
                            status="blocked",
                            summary=f"{role} blocked: utility_call schema validation failed",
                            artifacts=[],
                            findings=[
                                self._finding(
                                    f"{phase}-llm-invalid-utility-call-schema",
                                    "policy",
                                    "blocking",
                                    "; ".join(utility_call_schema_errors[:3]),
                                )
                            ],
                        )
                    utility_role = utility_call.get("role") if isinstance(utility_call, dict) else None
                    if not isinstance(utility_role, str) or utility_role not in UTILITY_PROMPT_MAP:
                        return self._task_result(
                            child_id=child_id,
                            role=role,
                            phase=phase,
                            status="blocked",
                            summary=f"{role} blocked: malformed utility_call action",
                            artifacts=[],
                            findings=[
                                self._finding(
                                    f"{phase}-llm-malformed-utility-call",
                                    "policy",
                                    "blocking",
                                    "LLM returned utility_call without valid role.",
                                )
                            ],
                        )
                    utility_result = self._run_utility_role(
                        llm_client=llm_client,
                        logger=logger,
                        parent_child_id=child_id,
                        parent_phase=phase,
                        utility_role=utility_role,
                        utility_call=utility_call,
                        context_pack=context_pack,
                        milestone_path=milestone_path,
                        loop_id=f"l2-{turn}",
                    )
                    messages.append({"role": "assistant", "content": json.dumps(action_obj, ensure_ascii=False)})
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "utility_result": utility_result,
                                    "instruction": "Incorporate utility result and continue with next action or final_result.",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )
                    continue

                if action == "final_result":
                    checkpoint_error = self._validate_loop_checkpoint(action_obj, phase)
                    if checkpoint_error:
                        return self._task_result(
                            child_id=child_id,
                            role=role,
                            phase=phase,
                            status="blocked",
                            summary=f"{role} blocked: missing loop checkpoint evidence",
                            artifacts=[],
                            findings=[
                                self._finding(
                                    f"{phase}-llm-loop-checkpoint-missing",
                                    "policy",
                                    "blocking",
                                    checkpoint_error,
                                )
                            ],
                        )
                    return self._normalize_llm_task_result(
                        action_obj=action_obj,
                        child_id=child_id,
                        role=role,
                        phase=phase,
                        milestone_path=milestone_path,
                    )

                return self._task_result(
                    child_id=child_id,
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: unsupported LLM action",
                    artifacts=[],
                    findings=[
                        self._finding(
                            f"{phase}-llm-unsupported-action",
                            "policy",
                            "blocking",
                            f"Unsupported LLM action '{action}'.",
                        )
                    ],
                )

            return self._task_result(
                child_id=child_id,
                role=role,
                phase=phase,
                status="blocked",
                summary=f"{role} blocked: max LLM turns exceeded",
                artifacts=[],
                findings=[
                    self._finding(
                        f"{phase}-llm-turn-cap",
                        "policy",
                        "blocking",
                        f"Phase exceeded max child turns ({max_turns}) without final_result.",
                    )
                ],
            )

        return _handler

    def _roadmap_path(self) -> str:
        return os.path.join(self.repo_root, "spec", "14_roadmap.json")

    def _load_roadmap(self) -> dict:
        path = self._roadmap_path()
        if not os.path.exists(path):
            raise RuntimeError(f"Roadmap missing: {_rel(self.repo_root, path)}")
        payload = _read_json(path)
        if payload.get("$schema") != "https://specdev.local/schema/14_roadmap.schema.json":
            raise RuntimeError(f"Roadmap schema mismatch in {_rel(self.repo_root, path)}")
        return payload

    def _session_state_candidates(self) -> List[str]:
        runtime_dir = os.path.join(self.repo_root, ".trinity", "runtime")
        if not os.path.isdir(runtime_dir):
            return []
        candidates: List[str] = []
        for name in os.listdir(runtime_dir):
            if not (name.startswith("session_state_") and name.endswith(".json")):
                continue
            candidates.append(os.path.join(runtime_dir, name))
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates

    def _select_resume_state_path(self) -> str:
        candidates = self._session_state_candidates()
        if not candidates:
            raise RuntimeError("Resume requested but no session_state_*.json found under .trinity/runtime")

        matched: List[Tuple[str, dict]] = []
        for path in candidates:
            try:
                payload = _read_json(path)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            run_id = payload.get("run_id")
            step_id = payload.get("step_id")
            if self.resume_run_id and run_id != self.resume_run_id:
                continue
            if self.step_id and step_id != self.step_id:
                continue
            matched.append((path, payload))

        if not matched:
            details: List[str] = []
            if self.resume_run_id:
                details.append(f"run_id='{self.resume_run_id}'")
            if self.step_id:
                details.append(f"step_id='{self.step_id}'")
            suffix = " for " + ", ".join(details) if details else ""
            raise RuntimeError(f"Resume requested but no matching session state found{suffix}")

        if self.resume_run_id:
            run_matches = [path for path, _ in matched]
            if len(run_matches) > 1:
                raise RuntimeError(
                    "Resume run_id matched multiple session states; clean stale states or provide --step-id for disambiguation"
                )
            return run_matches[0]

        if self.step_id:
            step_matches = [path for path, _ in matched]
            if len(step_matches) > 1:
                raise RuntimeError(
                    f"Resume for step_id '{self.step_id}' is ambiguous ({len(step_matches)} states). "
                    "Provide --resume-run-id to select a specific run."
                )
            return step_matches[0]

        if len(matched) > 1:
            raise RuntimeError(
                "Resume is ambiguous because multiple session states exist. Provide --step-id or --resume-run-id."
            )
        return matched[0][0]

    def _load_resume_state(self) -> Optional[dict]:
        if not self.resume:
            return None
        state_path = self._select_resume_state_path()
        errs = validate_runtime_file(self.repo_root, state_path, "session_state")
        if errs:
            raise RuntimeError("Resume state is invalid: " + "; ".join(errs))
        state = _read_json(state_path)
        state_step_id = state.get("step_id")
        if not isinstance(state_step_id, str) or not state_step_id:
            raise RuntimeError("Resume state missing step_id")
        if self.step_id and self.step_id != state_step_id:
            raise RuntimeError(
                f"Resume state step_id '{state_step_id}' does not match requested step_id '{self.step_id}'"
            )
        self.step_id = state_step_id
        return state

    def _pick_step_id(self, roadmap: dict) -> str:
        milestones = roadmap.get("milestones", [])
        if not isinstance(milestones, list) or not milestones:
            raise RuntimeError("Roadmap has no milestones")
        milestone_ids = [m.get("milestone_id") for m in milestones if isinstance(m, dict)]
        if self.step_id:
            if self.step_id not in milestone_ids:
                raise RuntimeError(f"step_id '{self.step_id}' not found in roadmap milestones")
            return self.step_id

        status_by_id = {
            m.get("milestone_id"): m.get("status", "pending")
            for m in milestones
            if isinstance(m, dict) and isinstance(m.get("milestone_id"), str)
        }
        dependencies = roadmap.get("dependencies", [])
        dep_ids = []
        if isinstance(dependencies, list):
            dep_ids = [
                d.get("id")
                for d in dependencies
                if isinstance(d, dict) and d.get("type") == "milestone" and isinstance(d.get("id"), str)
            ]
        for m in milestones:
            if not isinstance(m, dict):
                continue
            mid = m.get("milestone_id")
            status = m.get("status", "pending")
            if not isinstance(mid, str):
                continue
            if status == "done":
                continue
            deps_ok = all(status_by_id.get(dep) == "done" for dep in dep_ids if dep in status_by_id)
            if deps_ok:
                return mid
        raise RuntimeError("No eligible milestone found with satisfied dependencies")

    def _ensure_branch(self, tools: ToolExecutor) -> None:
        branch = f"trinity/{self.step_id}"
        tools.call("checkpoint_branch", {"branch_name": branch}, loop_id="l1")

    def _phase_validation_content(
        self,
        *,
        task_input_ref: Optional[str] = None,
        task_result_ref: Optional[str] = None,
        passed: Optional[bool] = None,
        schema_status: Optional[str] = None,
        deep_status: Optional[str] = None,
        governance_status: str = "n/a",
        seed_lint_status: str = "n/a",
        docs_lint_status: str = "n/a",
    ) -> dict:
        status = "pass" if bool(passed) else "fail"
        schema = schema_status if schema_status in {"pass", "fail", "n/a"} else status
        deep = deep_status if deep_status in {"pass", "fail", "n/a"} else status
        content = {
            "validation": {
                "schema": schema,
                "deep_validator": deep,
                "governance": governance_status if governance_status in {"pass", "fail", "n/a"} else "n/a",
                "seed_lint": seed_lint_status if seed_lint_status in {"pass", "fail", "n/a"} else "n/a",
                "docs_lint": docs_lint_status if docs_lint_status in {"pass", "fail", "n/a"} else "n/a",
            }
        }
        if task_input_ref:
            content["task_input_artifact_ref"] = task_input_ref
        if task_result_ref:
            content["task_result_artifact_ref"] = task_result_ref
        return content

    def _phase_attempt_cap(self, phase: str) -> int:
        if phase == "16a":
            return self.retry_caps["planner"]
        if phase == "16b":
            return self.retry_caps["builder"]
        if phase == "16c":
            return self.retry_caps["verifier"]
        return self.retry_caps["milestone"]

    def _normalize_checklist_scope(self, checklist_scope: Optional[List[str]]) -> List[str]:
        if not isinstance(checklist_scope, list):
            return []
        return sorted({x for x in checklist_scope if isinstance(x, str) and x.strip()})

    def _next_spawn_attempt(self, spawn_log_path: str, role: str, phase: str, checklist_scope: Optional[List[str]]) -> int:
        if not os.path.exists(spawn_log_path):
            return 1
        try:
            payload = _read_json(spawn_log_path)
        except Exception:
            return 1
        if payload.get("run_id") != self.run_id:
            return 1
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            return 1
        purpose = f"{role} {phase}"
        count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("step_id") != self.step_id:
                continue
            if entry.get("phase") != phase:
                continue
            if entry.get("purpose") != purpose:
                continue
            entry_scope = self._normalize_checklist_scope(entry.get("checklist_scope"))
            if entry_scope != self._normalize_checklist_scope(checklist_scope):
                continue
            count += 1
        return count + 1

    def _child_timeout_for_phase(self, phase: str) -> int:
        override = self.config.child_timeout_by_phase.get(phase)
        if isinstance(override, int) and override >= 0:
            return override
        return max(0, int(self.config.child_timeout_seconds))

    def _run_child_subprocess(
        self,
        *,
        phase: str,
        role: str,
        child_id: str,
        milestone_path: str,
        task_input_path: str,
        context_pack_path: str,
        task_result_path: str,
        session_log_path: str,
    ) -> Optional[str]:
        module_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cmd = [
            sys.executable,
            "-m",
            "specdev_tools.cli",
            "trinity-child",
            "--repo-root",
            self.repo_root,
            "--step-id",
            self.step_id,
            "--phase",
            phase,
            "--role",
            role,
            "--child-id",
            child_id,
            "--milestone-path",
            _rel(self.repo_root, milestone_path),
            "--task-input",
            _rel(self.repo_root, task_input_path),
            "--context-pack",
            _rel(self.repo_root, context_pack_path),
            "--task-result",
            _rel(self.repo_root, task_result_path),
            "--session-log",
            _rel(self.repo_root, session_log_path),
            "--run-id",
            self.run_id,
            "--parent-id",
            self.root_agent_id,
            "--mode",
            self.execution_mode,
        ]
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            module_root
            if not existing_pythonpath
            else module_root + os.pathsep + existing_pythonpath
        )
        env["SPECDEV_SKIP_VENV_CHECK"] = "1"
        timeout_seconds = self._child_timeout_for_phase(phase)
        timeout_arg = timeout_seconds if timeout_seconds > 0 else None
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout_arg,
            )
        except subprocess.TimeoutExpired:
            if timeout_seconds > 0:
                return f"child subprocess timeout after {timeout_seconds}s in phase {phase}"
            return f"child subprocess timeout in phase {phase}"
        if proc.returncode == 0:
            return None
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        msg = stderr or stdout or f"child subprocess failed with exit {proc.returncode}"
        return msg

    def _ingest_phase_result(
        self,
        *,
        logger: SessionLogger,
        role: str,
        phase: str,
        child_id: str,
        attempt: int,
        milestone_path: str,
        session_state_path: str,
        spawn_log_path: str,
        scratchpad_path: str,
        retry_counters: dict,
        canonical_task_input_ref: str,
        canonical_task_result_ref: str,
        checklist_scope: List[str],
        task_result: dict,
        task_result_errors: List[str],
    ) -> Tuple[dict, List[str]]:
        logger.append(
            "VALIDATION",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"{role} task_result validation {'pass' if not task_result_errors else 'fail'}",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra=self._phase_validation_content(task_result_ref=canonical_task_result_ref, passed=not task_result_errors),
        )
        logger.append(
            "TERMINATE",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"Terminate {role} with {task_result.get('status')}",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra={"task_result_artifact_ref": canonical_task_result_ref},
        )
        self._update_spawn_log(
            spawn_log_path=spawn_log_path,
            child_id=child_id,
            role=role,
            phase=phase,
            attempt=attempt,
            checklist_scope=checklist_scope,
            task_input_ref=canonical_task_input_ref,
            task_result_ref=canonical_task_result_ref,
            task_result=task_result,
        )

        status = task_result.get("status")
        if status == "questions":
            questions_raw = task_result.get("questions", [])
            questions = [q for q in questions_raw if isinstance(q, str) and q.strip()] if isinstance(questions_raw, list) else []
            self._write_session_state(
                session_state_path=session_state_path,
                active_phase=phase,
                status="awaiting_input",
                pending_child_id=child_id,
                pending_spawn_ref=canonical_task_input_ref,
                pending_questions=questions,
                spawn_log_ref=".trinity/runtime/spawn_log.json",
                scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                retry_counters=retry_counters,
            )
            self._write_scratchpad(
                scratchpad_path,
                phase=phase,
                next_action_ref=f"phase:{phase}:awaiting_input",
                state_summary=f"{phase} awaiting clarification",
                checklist_scope=self._checklist_ids(milestone_path),
                validation_gate={
                    "schema": "pass" if not task_result_errors else "fail",
                    "deep_validator": "pass" if not task_result_errors else "fail",
                    "governance": "n/a",
                },
            )
            return task_result, task_result_errors

        self._write_session_state(
            session_state_path=session_state_path,
            active_phase=phase,
            status="resuming",
            pending_child_id=None,
            pending_spawn_ref=None,
            pending_questions=None,
            spawn_log_ref=".trinity/runtime/spawn_log.json",
            scratchpad_ref=_rel(self.repo_root, scratchpad_path),
            retry_counters=retry_counters,
        )
        self._write_scratchpad(
            scratchpad_path,
            phase=phase,
            next_action_ref=f"phase:{phase}:ingest",
            state_summary=f"{phase} completed with status {task_result.get('status')}",
            checklist_scope=self._checklist_ids(milestone_path),
            validation_gate={
                "schema": "pass" if not task_result_errors else "fail",
                "deep_validator": "pass" if not task_result_errors else "fail",
                "governance": "n/a",
            },
        )
        return task_result, task_result_errors

    def _spawn_phase(
        self,
        *,
        logger: SessionLogger,
        resolver: ContextResolver,
        phase: str,
        role: str,
        phase_label: str,
        milestone_path: str,
        anchor_path: str,
        session_state_path: str,
        spawn_log_path: str,
        scratchpad_path: str,
        retry_counters: dict,
    ) -> Tuple[dict, List[str]]:
        checklist_scope = self._checklist_ids(milestone_path)
        attempt = self._next_spawn_attempt(spawn_log_path, role, phase, checklist_scope)
        if attempt > self._phase_attempt_cap(phase):
            finding = self._finding(
                f"{phase}-spawn-loop-cap",
                "policy",
                "blocking",
                f"Spawn loop cap exceeded for {role} {phase} (attempt {attempt}).",
            )
            return (
                self._task_result(
                    child_id=f"{role.lower()}-blocked",
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: spawn loop cap exceeded",
                    artifacts=[],
                    findings=[finding],
                ),
                [finding["description"]],
            )

        milestone_payload = _read_json(milestone_path) if os.path.exists(milestone_path) else None
        phase_target_patterns = self._target_patterns_for_phase(phase, milestone_payload, milestone_path, anchor_path)
        phase_test_commands = self._phase_test_commands(milestone_payload)
        context_pack = resolver.context_pack(phase, milestone_payload, phase_target_patterns, phase_test_commands)
        bootstrap_trace = context_pack.get("bootstrap_ref_trace") if isinstance(context_pack.get("bootstrap_ref_trace"), list) else None
        if phase == "16a" and not isinstance(milestone_payload, dict):
            try:
                milestone_payload = self._ensure_milestone_artifact(milestone_path, context_pack=context_pack)
            except Exception as e:  # noqa: BLE001
                finding = self._finding(
                    "planner-bootstrap-failed",
                    "policy",
                    "blocking",
                    str(e),
                )
                blocked_result = self._task_result(
                    child_id=f"{role.lower()}-blocked",
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: milestone bootstrap failed",
                    artifacts=[],
                    findings=[finding],
                )
                return blocked_result, [finding["description"]]
            phase_target_patterns = self._target_patterns_for_phase(phase, milestone_payload, milestone_path, anchor_path)
            phase_test_commands = self._phase_test_commands(milestone_payload)
            context_pack = resolver.context_pack(phase, milestone_payload, phase_target_patterns, phase_test_commands)
            if bootstrap_trace and not isinstance(context_pack.get("bootstrap_ref_trace"), list):
                context_pack["bootstrap_ref_trace"] = bootstrap_trace
            checklist_scope = self._checklist_ids(milestone_path)

        child_id = f"{role.lower()}-{uuid.uuid4().hex[:8]}"
        spawn_dir = os.path.join(self.repo_root, ".trinity", "runtime", "spawns", child_id)
        os.makedirs(spawn_dir, exist_ok=True)

        # S-1: Write-ahead marker for transaction atomicity.
        # If runtime crashes between here and marker removal, recovery
        # detects the orphaned .wal file and cleans up partial artifacts.
        wal_dir = os.path.join(self.repo_root, ".trinity", "runtime", "wal")
        os.makedirs(wal_dir, exist_ok=True)
        wal_path = os.path.join(wal_dir, f"{child_id}.wal")
        with open(wal_path, "w") as wf:
            wf.write(child_id)

        context_pack_path = os.path.join(spawn_dir, "context_pack.json")
        _write_json_atomic(context_pack_path, context_pack)
        context_errors = validate_runtime_file(self.repo_root, context_pack_path, "context_pack")

        task_input = {
            "protocol_version": PROTO_VER,
            "child_id": child_id,
            "parent_id": self.root_agent_id,
            "role": role,
            "phase": phase,
            "step_id": self.step_id,
            "task_description": f"{phase_label} execution for milestone {self.step_id}",
            "expected_output_schema": RUNTIME_SCHEMA_BY_TYPE["task_result"],
            "context_pack_ref": _rel(self.repo_root, context_pack_path),
            "target_files": self._target_files_for_task_input(
                milestone_payload=milestone_payload,
                milestone_path=milestone_path,
                anchor_path=anchor_path,
                phase_target_patterns=phase_target_patterns,
            ),
            "spec_refs": context_pack.get("required_spec_refs", []),
            "role_metadata": {
                "prompt_source": _prompt_path_for(phase, role),
                "persona_goal": f"Execute {phase} for milestone {self.step_id}",
                "stop_conditions": ["questions", "blocked", "success"],
            },
        }
        task_input_path = os.path.join(spawn_dir, "task_input.json")
        _write_json_atomic(task_input_path, task_input)
        task_input_errors = validate_runtime_file(self.repo_root, task_input_path, "task_input")

        task_result_path = os.path.join(spawn_dir, "task_result.json")
        canonical_task_input_ref = f".trinity/runtime/spawns/{child_id}/task_input.json"
        canonical_task_result_ref = f".trinity/runtime/spawns/{child_id}/task_result.json"
        validation_ok = not context_errors and not task_input_errors
        if not validation_ok:
            logger.append(
                "VALIDATION",
                role="Orchestrator",
                phase_id=phase,
                loop_id="l1",
                agent_id=self.root_agent_id,
                parent_id=None,
                summary=f"{role} task_input validation fail",
                prompt_template_id=f"prompt_{phase}",
                step_id=self.step_id,
                content_extra=self._phase_validation_content(task_input_ref=canonical_task_input_ref, passed=False),
            )
            blocked_result = self._task_result(
                child_id=child_id,
                role=role,
                phase=phase,
                status="blocked",
                summary=f"{role} blocked: invalid spawn artifacts",
                artifacts=[],
                findings=[
                    self._finding(
                        f"{phase}-spawn-validation-failed",
                        "policy",
                        "blocking",
                        "; ".join(context_errors + task_input_errors),
                    )
                ],
            )
            self._update_spawn_log(
                spawn_log_path=spawn_log_path,
                child_id=child_id,
                role=role,
                phase=phase,
                attempt=attempt,
                checklist_scope=checklist_scope,
                task_input_ref=canonical_task_input_ref,
                task_result_ref=None,
                task_result=blocked_result,
            )
            self._write_session_state(
                session_state_path=session_state_path,
                active_phase=phase,
                status="blocked",
                pending_child_id=None,
                pending_spawn_ref=None,
                pending_questions=None,
                spawn_log_ref=".trinity/runtime/spawn_log.json",
                scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                retry_counters=retry_counters,
            )
            return blocked_result, context_errors + task_input_errors

        self._write_session_state(
            session_state_path=session_state_path,
            active_phase=phase,
            status="waiting_child",
            pending_child_id=child_id,
            pending_spawn_ref=canonical_task_input_ref,
            pending_questions=None,
            spawn_log_ref=".trinity/runtime/spawn_log.json",
            scratchpad_ref=_rel(self.repo_root, scratchpad_path),
            retry_counters=retry_counters,
        )
        logger.append(
            "SPAWN",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"Spawn {role}",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra={"task_input_artifact_ref": canonical_task_input_ref},
        )
        logger.append(
            "VALIDATION",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"{role} task_input validation pass",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra=self._phase_validation_content(task_input_ref=canonical_task_input_ref, passed=True),
        )

        child_error = self._run_child_subprocess(
            phase=phase,
            role=role,
            child_id=child_id,
            milestone_path=milestone_path,
            task_input_path=task_input_path,
            context_pack_path=context_pack_path,
            task_result_path=task_result_path,
            session_log_path=logger.path,
        )
        if child_error and not os.path.exists(task_result_path):
            blocked_result = self._task_result(
                child_id=child_id,
                role=role,
                phase=phase,
                status="blocked",
                summary=f"{role} blocked: child execution failed",
                artifacts=[],
                findings=[self._finding(f"{phase}-child-process-failed", "policy", "blocking", child_error)],
            )
            _write_json_atomic(task_result_path, blocked_result)

        if not os.path.exists(task_result_path):
            missing_result = self._task_result(
                child_id=child_id,
                role=role,
                phase=phase,
                status="blocked",
                summary=f"{role} blocked: child did not produce task_result",
                artifacts=[],
                findings=[self._finding(f"{phase}-missing-task-result", "policy", "blocking", "Child produced no task_result.json")],
            )
            _write_json_atomic(task_result_path, missing_result)

        logger.sync_from_disk()
        task_result_errors = validate_runtime_file(self.repo_root, task_result_path, "task_result")
        task_result = _read_json(task_result_path)
        ingest_result = self._ingest_phase_result(
            logger=logger,
            role=role,
            phase=phase,
            child_id=child_id,
            attempt=attempt,
            milestone_path=milestone_path,
            session_state_path=session_state_path,
            spawn_log_path=spawn_log_path,
            scratchpad_path=scratchpad_path,
            retry_counters=retry_counters,
            canonical_task_input_ref=canonical_task_input_ref,
            canonical_task_result_ref=canonical_task_result_ref,
            checklist_scope=checklist_scope,
            task_result=task_result,
            task_result_errors=task_result_errors,
        )
        # S-1: Remove WAL marker after successful transaction closure.
        if os.path.exists(wal_path):
            os.remove(wal_path)
        return ingest_result

    def _resume_pending_spawn(
        self,
        *,
        logger: SessionLogger,
        session_state_path: str,
        spawn_log_path: str,
        scratchpad_path: str,
        milestone_path: str,
        retry_counters: dict,
        resume_state: dict,
    ) -> Optional[dict]:
        pending_child_id = resume_state.get("pending_child_id")
        pending_spawn_ref = resume_state.get("pending_spawn_ref")
        if not (isinstance(pending_child_id, str) and pending_child_id and isinstance(pending_spawn_ref, str) and pending_spawn_ref):
            return None
        task_input_path = os.path.join(self.repo_root, pending_spawn_ref)
        if not os.path.exists(task_input_path):
            return None
        task_input_errors = validate_runtime_file(self.repo_root, task_input_path, "task_input")
        if task_input_errors:
            return {
                "status": "blocked",
                "phase": "16a",
                "task_result": self._task_result(
                    child_id=pending_child_id,
                    role="Planner",
                    phase="16a",
                    status="blocked",
                    summary="Pending spawn invalid",
                    artifacts=[],
                    findings=[self._finding("resume-invalid-task-input", "policy", "blocking", "; ".join(task_input_errors))],
                ),
                "errors": task_input_errors,
            }
        task_input = _read_json(task_input_path)
        phase = task_input.get("phase")
        role = task_input.get("role")
        if phase not in {"16a", "16b", "16c", "utility"} or not isinstance(role, str):
            return None
        context_pack_ref = task_input.get("context_pack_ref")
        if not isinstance(context_pack_ref, str) or not context_pack_ref:
            return None
        context_pack_path = os.path.join(self.repo_root, context_pack_ref)
        if not os.path.exists(context_pack_path):
            return None
        spawn_dir = os.path.dirname(task_input_path)
        task_result_path = os.path.join(spawn_dir, "task_result.json")
        canonical_task_input_ref = pending_spawn_ref
        canonical_task_result_ref = _rel(self.repo_root, task_result_path)
        resume_status = resume_state.get("status")
        if resume_status == "awaiting_input":
            if not self.resume_answers:
                pending_questions = resume_state.get("pending_questions")
                questions = (
                    [q for q in pending_questions if isinstance(q, str) and q.strip()]
                    if isinstance(pending_questions, list)
                    else []
                )
                if not questions and os.path.exists(task_result_path):
                    existing = _read_json(task_result_path)
                    q = existing.get("questions")
                    if isinstance(q, list):
                        questions = [x for x in q if isinstance(x, str) and x.strip()]
                return {
                    "status": "questions",
                    "phase": phase,
                    "questions": questions,
                    "pending_spawn_ref": pending_spawn_ref,
                }
            clarifications = "\n".join(f"- {a}" for a in self.resume_answers)
            existing_desc = task_input.get("task_description", "")
            task_input["task_description"] = f"{existing_desc}\n\nUser clarifications:\n{clarifications}".strip()
            _write_json_atomic(task_input_path, task_input)
            refreshed_errors = validate_runtime_file(self.repo_root, task_input_path, "task_input")
            if refreshed_errors:
                return {
                    "status": "blocked",
                    "phase": phase,
                    "task_result": self._task_result(
                        child_id=pending_child_id,
                        role=role,
                        phase=phase,
                        status="blocked",
                        summary=f"{role} blocked: invalid resumed task_input",
                        artifacts=[],
                        findings=[self._finding("resume-invalid-updated-task-input", "policy", "blocking", "; ".join(refreshed_errors))],
                    ),
                    "errors": refreshed_errors,
                }
            if os.path.exists(task_result_path):
                os.remove(task_result_path)
            self._write_session_state(
                session_state_path=session_state_path,
                active_phase=phase,
                status="waiting_child",
                pending_child_id=pending_child_id,
                pending_spawn_ref=pending_spawn_ref,
                pending_questions=None,
                spawn_log_ref=".trinity/runtime/spawn_log.json",
                scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                retry_counters=retry_counters,
            )

        checklist_scope = self._checklist_ids(milestone_path)
        attempt = self._next_spawn_attempt(spawn_log_path, role, phase, checklist_scope)
        if attempt > self._phase_attempt_cap(phase):
            return {
                "status": "blocked",
                "phase": phase,
                "task_result": self._task_result(
                    child_id=pending_child_id,
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: spawn loop cap exceeded",
                    artifacts=[],
                    findings=[self._finding(f"{phase}-resume-loop-cap", "policy", "blocking", "Resume spawn loop cap exceeded.")],
                ),
                "errors": [f"{phase} resume spawn loop cap exceeded"],
            }

        logger.append(
            "SPAWN",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"Resume {role}",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra={"task_input_artifact_ref": canonical_task_input_ref},
        )
        logger.append(
            "VALIDATION",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=f"{role} task_input validation pass",
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            content_extra=self._phase_validation_content(task_input_ref=canonical_task_input_ref, passed=True),
        )
        if not os.path.exists(task_result_path):
            child_error = self._run_child_subprocess(
                phase=phase,
                role=role,
                child_id=pending_child_id,
                milestone_path=milestone_path,
                task_input_path=task_input_path,
                context_pack_path=context_pack_path,
                task_result_path=task_result_path,
                session_log_path=logger.path,
            )
            if child_error and not os.path.exists(task_result_path):
                blocked = self._task_result(
                    child_id=pending_child_id,
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: child execution failed on resume",
                    artifacts=[],
                    findings=[self._finding(f"{phase}-resume-child-failed", "policy", "blocking", child_error)],
                )
                _write_json_atomic(task_result_path, blocked)
        logger.sync_from_disk()
        if not os.path.exists(task_result_path):
            return {
                "status": "blocked",
                "phase": phase,
                "task_result": self._task_result(
                    child_id=pending_child_id,
                    role=role,
                    phase=phase,
                    status="blocked",
                    summary=f"{role} blocked: missing task_result after resume",
                    artifacts=[],
                    findings=[self._finding(f"{phase}-resume-missing-task-result", "policy", "blocking", "Resume produced no task_result")],
                ),
                "errors": [f"{phase} missing task_result after resume"],
            }
        task_result_errors = validate_runtime_file(self.repo_root, task_result_path, "task_result")
        task_result = _read_json(task_result_path)
        ingested_result, ingested_errors = self._ingest_phase_result(
            logger=logger,
            role=role,
            phase=phase,
            child_id=pending_child_id,
            attempt=attempt,
            milestone_path=milestone_path,
            session_state_path=session_state_path,
            spawn_log_path=spawn_log_path,
            scratchpad_path=scratchpad_path,
            retry_counters=retry_counters,
            canonical_task_input_ref=canonical_task_input_ref,
            canonical_task_result_ref=canonical_task_result_ref,
            checklist_scope=checklist_scope,
            task_result=task_result,
            task_result_errors=task_result_errors,
        )
        return {"status": "replayed", "phase": phase, "task_result": ingested_result, "errors": ingested_errors}

    def _checklist_ids(self, milestone_path: str) -> List[str]:
        if not os.path.exists(milestone_path):
            return []
        payload = _read_json(milestone_path)
        checklist = payload.get("plan", {}).get("spec_alignment", {}).get("checklist", [])
        if not isinstance(checklist, list):
            return []
        ids: List[str] = []
        for item in checklist:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.append(item["id"])
        return ids

    def _target_patterns_for_phase(
        self,
        phase: str,
        milestone_payload: Optional[dict],
        milestone_path: str,
        anchor_path: str,
    ) -> List[str]:
        milestone_rel = _rel(self.repo_root, milestone_path)
        anchor_rel = _rel(self.repo_root, anchor_path)
        patterns: List[str] = [milestone_rel, anchor_rel, "spec/impl_context/*.json", "spec/16_impl_context.json"]
        if isinstance(milestone_payload, dict):
            plan = milestone_payload.get("plan", {})
            summary = plan.get("summary", {}) if isinstance(plan, dict) else {}
            targets = summary.get("target_file_patterns", []) if isinstance(summary, dict) else []
            if isinstance(targets, list):
                for p in targets:
                    if isinstance(p, str) and p and p not in patterns:
                        patterns.append(p)
        if phase == "16a" and "docs/**" not in patterns:
            patterns.append("docs/**")
        return patterns

    def _phase_test_commands(self, milestone_payload: Optional[dict]) -> List[Any]:
        if not isinstance(milestone_payload, dict):
            return []
        plan = milestone_payload.get("plan", {})
        if not isinstance(plan, dict):
            return []
        req = plan.get("review_requirements", {})
        if not isinstance(req, dict):
            return []
        cmds = req.get("test_commands", [])
        if isinstance(cmds, list) and cmds:
            return cmds
        return []

    def _target_files_for_task_input(
        self,
        *,
        milestone_payload: Optional[dict],
        milestone_path: str,
        anchor_path: str,
        phase_target_patterns: List[str],
    ) -> List[str]:
        files: List[str] = [
            _rel(self.repo_root, milestone_path),
            _rel(self.repo_root, anchor_path),
        ]
        for candidate in phase_target_patterns:
            if isinstance(candidate, str) and candidate and not _looks_like_pattern(candidate):
                files.append(candidate)
        if isinstance(milestone_payload, dict):
            plan = milestone_payload.get("plan", {})
            if isinstance(plan, dict):
                docs_impact = plan.get("docs_impact", {})
                if isinstance(docs_impact, dict):
                    docs_touched = docs_impact.get("docs_touched", [])
                    if isinstance(docs_touched, list):
                        for doc_path in docs_touched:
                            if isinstance(doc_path, str) and doc_path and not _looks_like_pattern(doc_path):
                                files.append(doc_path)
                checklist = plan.get("spec_alignment", {}).get("checklist", []) if isinstance(plan.get("spec_alignment"), dict) else []
                if isinstance(checklist, list):
                    for item in checklist:
                        if not isinstance(item, dict):
                            continue
                        impl = item.get("implementation", {})
                        if isinstance(impl, dict):
                            touched = impl.get("files_touched", [])
                            if isinstance(touched, list):
                                for touched_path in touched:
                                    if isinstance(touched_path, str) and touched_path and not _looks_like_pattern(touched_path):
                                        files.append(touched_path)
                            actions = impl.get("actions", [])
                            if isinstance(actions, list):
                                for action in actions:
                                    if not isinstance(action, dict):
                                        continue
                                    target = action.get("target")
                                    if isinstance(target, str) and target and not _looks_like_pattern(target):
                                        files.append(target)
        return list(dict.fromkeys(files))

    def _bootstrap_seed_refs(self) -> List[dict]:
        manifest_path = os.path.join(self.repo_root, "spec", "common", "seed_manifest.json")
        if not os.path.exists(manifest_path):
            return []
        try:
            manifest = _read_json(manifest_path)
        except Exception:
            return []
        step_requirements = manifest.get("step_requirements", {})
        required_seed_ids: List[str] = []
        if isinstance(step_requirements, dict):
            for phase in ("16a", "16"):
                ids = step_requirements.get(phase, [])
                if isinstance(ids, list):
                    for seed_id in ids:
                        if isinstance(seed_id, str) and seed_id and seed_id not in required_seed_ids:
                            required_seed_ids.append(seed_id)
        return [{"seed_id": seed_id} for seed_id in required_seed_ids]

    def _bootstrap_milestone_artifact(self, milestone_path: str, required_spec_refs: List[dict]) -> dict:
        refs: List[dict] = []
        for ref in required_spec_refs:
            if not isinstance(ref, dict):
                continue
            rtype = ref.get("type")
            rid = ref.get("id")
            line_range = ref.get("line_range")
            commit_hash = ref.get("commit_hash")
            if all(isinstance(v, str) and v for v in (rtype, rid, line_range, commit_hash)):
                refs.append(
                    {
                        "type": rtype,
                        "id": rid,
                        "line_range": line_range,
                        "commit_hash": commit_hash,
                    }
                )
        if not refs:
            raise RuntimeError("Planner bootstrap failed: no grounded spec refs available for milestone initialization")

        bootstrap_cmd = 'python3 -c "print(\'SUCCESS TRINITY_BOOTSTRAP\')"'
        checklist: List[dict] = []
        for idx, ref in enumerate(refs[:5], start=1):
            checklist.append(
                {
                    "id": f"CHK_BOOTSTRAP_{idx:03d}",
                    "spec_ref": ref,
                    "description": (
                        f"Bootstrap planner contract for grounded reference {ref['type']}:{ref['id']} "
                        "using deterministic evidence collection."
                    ),
                    "type": "validation",
                    "layer": "integration",
                    "checklist_status": "active",
                    "linked_test_expectation": bootstrap_cmd,
                    "nfr_refs": ["nfr-bootstrap-safety"],
                    "fixture_ref": "fixture-bootstrap-smoke",
                    "implementation": {
                        "status": "pending",
                        "files_touched": [],
                        "actions": [
                            {
                                "type": "run_command",
                                "description": "Execute deterministic bootstrap smoke command to initialize evidence contract.",
                                "command": bootstrap_cmd,
                            },
                            {
                                "type": "manual_verification",
                                "description": "Confirm success marker from bootstrap smoke command output.",
                            },
                        ],
                    },
                }
            )
        owner = "api"
        roadmap_path = os.path.join(self.repo_root, "spec", "14_roadmap.json")
        if os.path.exists(roadmap_path):
            try:
                roadmap = _read_json(roadmap_path)
                if isinstance(roadmap.get("owner"), str) and roadmap["owner"]:
                    owner = roadmap["owner"]
            except Exception:
                owner = "api"

        payload = {
            "$schema": "https://specdev.local/schema/16_impl_context.schema.json",
            "id": self.step_id,
            "owner": owner,
            "created_at": _utc_now(),
            "seed_refs": self._bootstrap_seed_refs() or [{"seed_id": "seed-overview"}],
            "plan": {
                "status": "active",
                "summary": {
                    "functional_summary": (
                        f"Bootstrap implementation context for milestone '{self.step_id}' generated from governed seeds and roadmap."
                    ),
                    "scope_in": [f"bootstrap:{self.step_id}"],
                    "scope_out": [],
                    "target_file_patterns": [
                        _rel(self.repo_root, milestone_path),
                        "spec/16_impl_context.json",
                        "README.md",
                    ],
                },
                "docs_impact": {
                    "status": "required",
                    "rationale": "Bootstrap writes Step 16 planning artifacts and must keep documentation traceability updated.",
                    "docs_touched": ["README.md"],
                },
                "spec_alignment": {"checklist": checklist},
                "review_requirements": {
                    "guidelines": "Bootstrap milestone context until planner emits refined plan.",
                    "test_commands": [bootstrap_cmd],
                },
            },
        }
        _write_json_atomic(milestone_path, payload)
        errs = validate_file(self.repo_root, milestone_path)
        if errs:
            raise RuntimeError("Planner bootstrap produced invalid milestone artifact: " + "; ".join(errs))
        return payload

    def _ensure_milestone_artifact(self, milestone_path: str, *, context_pack: Optional[dict] = None) -> dict:
        if not os.path.exists(milestone_path):
            refs = context_pack.get("required_spec_refs", []) if isinstance(context_pack, dict) else []
            if not isinstance(refs, list):
                refs = []
            self._bootstrap_milestone_artifact(milestone_path, refs)
        payload = _read_json(milestone_path)
        if payload.get("$schema") != "https://specdev.local/schema/16_impl_context.schema.json":
            raise RuntimeError(f"{_rel(self.repo_root, milestone_path)} is not a Step 16 milestone artifact")
        return payload

    def _regenerate_anchor(
        self,
        milestone_path: str,
        anchor_path: str,
        *,
        logger: Optional[SessionLogger] = None,
        phase: str = "16a",
    ) -> dict:
        existing_extensions = {}
        if os.path.exists(anchor_path):
            try:
                anchor = _read_json(anchor_path)
                ext = anchor.get("extensions")
                if isinstance(ext, dict):
                    existing_extensions = ext
            except Exception:
                existing_extensions = {}

        roadmap_active_ids: Set[str] = set()
        roadmap_path = self._roadmap_path()
        if os.path.exists(roadmap_path):
            try:
                roadmap = _read_json(roadmap_path)
                milestones = roadmap.get("milestones", [])
                if isinstance(milestones, list):
                    for milestone in milestones:
                        if not isinstance(milestone, dict):
                            continue
                        milestone_id = milestone.get("milestone_id")
                        status = milestone.get("status", "pending")
                        if isinstance(milestone_id, str) and status != "done":
                            roadmap_active_ids.add(milestone_id)
            except Exception:
                roadmap_active_ids = set()

        impl_dir = os.path.join(self.repo_root, "spec", "impl_context")
        candidate_paths: List[str] = []
        if os.path.isdir(impl_dir):
            for entry in sorted(os.listdir(impl_dir)):
                if not entry.endswith(".json"):
                    continue
                candidate_paths.append(os.path.join(impl_dir, entry))
        if os.path.exists(milestone_path) and milestone_path not in candidate_paths:
            candidate_paths.append(milestone_path)

        milestone_payloads: List[dict] = []
        for candidate in candidate_paths:
            if not os.path.exists(candidate):
                continue
            try:
                payload = _read_json(candidate)
            except Exception:
                continue
            if payload.get("$schema") != "https://specdev.local/schema/16_impl_context.schema.json":
                continue
            milestone_id = payload.get("id")
            if roadmap_active_ids and isinstance(milestone_id, str) and milestone_id not in roadmap_active_ids:
                continue
            milestone_payloads.append(payload)
        if not milestone_payloads:
            return {
                "active_contexts": 0,
                "merged_seed_refs": 0,
                "union_scope_in_count": 0,
                "union_scope_out_count": 0,
                "union_target_patterns_count": 0,
                "union_docs_touched_count": 0,
                "union_test_commands_count": 0,
                "checklist_items_count": 0,
                "checklist_conflicts_count": 0,
                "checklist_conflict_ids": [],
            }

        primary = None
        for payload in milestone_payloads:
            if payload.get("id") == self.step_id:
                primary = payload
                break
        if primary is None:
            primary = milestone_payloads[0]

        merged = copy.deepcopy(primary)
        merged["id"] = "step-impl-anchor"
        merged["created_at"] = _utc_now()

        seed_ids: List[str] = []
        union_scope_in: Set[str] = set()
        union_scope_out: Set[str] = set()
        union_targets: Set[str] = set()
        union_docs_touched: Set[str] = set()
        union_test_commands: List[Any] = []
        checklist_by_id: Dict[str, dict] = {}
        checklist_conflict_ids: Set[str] = set()

        for payload in milestone_payloads:
            for seed_ref in payload.get("seed_refs", []):
                if isinstance(seed_ref, dict):
                    seed_id = seed_ref.get("seed_id")
                    if isinstance(seed_id, str) and seed_id and seed_id not in seed_ids:
                        seed_ids.append(seed_id)
            plan = payload.get("plan", {})
            if not isinstance(plan, dict):
                continue
            summary = plan.get("summary", {})
            if isinstance(summary, dict):
                scope_in = summary.get("scope_in", [])
                if isinstance(scope_in, list):
                    for item in scope_in:
                        if isinstance(item, str) and item:
                            union_scope_in.add(item)
                scope_out = summary.get("scope_out", [])
                if isinstance(scope_out, list):
                    for item in scope_out:
                        if isinstance(item, str) and item:
                            union_scope_out.add(item)
                targets = summary.get("target_file_patterns", [])
                if isinstance(targets, list):
                    for item in targets:
                        if isinstance(item, str) and item:
                            union_targets.add(item)
            docs_impact = plan.get("docs_impact", {})
            if isinstance(docs_impact, dict):
                docs_touched = docs_impact.get("docs_touched", [])
                if isinstance(docs_touched, list):
                    for item in docs_touched:
                        if isinstance(item, str) and item:
                            union_docs_touched.add(item)
            review_requirements = plan.get("review_requirements", {})
            if isinstance(review_requirements, dict):
                test_commands = review_requirements.get("test_commands", [])
                if isinstance(test_commands, list):
                    for command in test_commands:
                        if command not in union_test_commands:
                            union_test_commands.append(command)
            checklist = plan.get("spec_alignment", {}).get("checklist", []) if isinstance(plan.get("spec_alignment"), dict) else []
            if isinstance(checklist, list):
                for item in checklist:
                    if not isinstance(item, dict):
                        continue
                    item_id = item.get("id")
                    if isinstance(item_id, str) and item_id:
                        candidate = copy.deepcopy(item)
                        existing = checklist_by_id.get(item_id)
                        if isinstance(existing, dict):
                            existing_canon = json.dumps(existing, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                            candidate_canon = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                            if existing_canon != candidate_canon:
                                checklist_conflict_ids.add(item_id)
                        checklist_by_id[item_id] = candidate

        if seed_ids:
            merged["seed_refs"] = [{"seed_id": seed_id} for seed_id in seed_ids]
        plan = merged.get("plan", {}) if isinstance(merged.get("plan"), dict) else {}
        summary = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}
        summary["functional_summary"] = summary.get("functional_summary") or (
            f"Anchor union of active milestone implementation contexts for run step '{self.step_id}'."
        )
        summary["scope_in"] = sorted(union_scope_in) if union_scope_in else summary.get("scope_in", [])
        summary["scope_out"] = sorted(union_scope_out) if union_scope_out else summary.get("scope_out", [])
        summary["target_file_patterns"] = sorted(union_targets) if union_targets else summary.get("target_file_patterns", [])
        plan["summary"] = summary

        docs_impact = plan.get("docs_impact", {}) if isinstance(plan.get("docs_impact"), dict) else {}
        docs_impact["status"] = "required"
        docs_impact["rationale"] = docs_impact.get("rationale") or "Union anchor reflects active milestone context updates."
        docs_impact["docs_touched"] = sorted(union_docs_touched) if union_docs_touched else docs_impact.get("docs_touched", ["README.md"])
        if not docs_impact.get("docs_touched"):
            docs_impact["docs_touched"] = ["README.md"]
        plan["docs_impact"] = docs_impact

        spec_alignment = plan.get("spec_alignment", {}) if isinstance(plan.get("spec_alignment"), dict) else {}
        checklist_union = [checklist_by_id[key] for key in sorted(checklist_by_id.keys())]
        if checklist_union:
            spec_alignment["checklist"] = checklist_union
        plan["spec_alignment"] = spec_alignment

        review_requirements = plan.get("review_requirements", {}) if isinstance(plan.get("review_requirements"), dict) else {}
        if union_test_commands:
            review_requirements["test_commands"] = union_test_commands
        review_requirements["guidelines"] = review_requirements.get("guidelines") or "Union of active milestone review requirements."
        plan["review_requirements"] = review_requirements

        checklist_for_coverage = spec_alignment.get("checklist", [])
        if isinstance(checklist_for_coverage, list):
            total = len(checklist_for_coverage)
            verified = 0
            deferred = 0
            for item in checklist_for_coverage:
                if not isinstance(item, dict):
                    continue
                impl = item.get("implementation", {})
                if isinstance(impl, dict) and impl.get("status") == "verified":
                    verified += 1
                elif item.get("checklist_status") == "deferred" or (isinstance(impl, dict) and impl.get("status") == "deferred"):
                    deferred += 1
            pending = max(0, total - verified - deferred)
            plan["coverage_status"] = {
                "total": total,
                "verified": verified,
                "deferred": deferred,
                "pending": pending,
            }

        merged["plan"] = plan
        union_metrics = {
            "active_contexts": len(milestone_payloads),
            "merged_seed_refs": len(seed_ids),
            "union_scope_in_count": len(union_scope_in),
            "union_scope_out_count": len(union_scope_out),
            "union_target_patterns_count": len(union_targets),
            "union_docs_touched_count": len(union_docs_touched),
            "union_test_commands_count": len(union_test_commands),
            "checklist_items_count": len(checklist_by_id),
            "checklist_conflicts_count": len(checklist_conflict_ids),
            "checklist_conflict_ids": sorted(checklist_conflict_ids),
        }
        if checklist_conflict_ids and not self.config.allow_anchor_conflicts:
            conflict_list = ", ".join(sorted(checklist_conflict_ids))
            raise RuntimeError(
                "Anchor union detected conflicting checklist definitions: "
                + conflict_list
                + ". Set runtime.allow_anchor_conflicts=true to override."
            )
        merged_extensions = merged.get("extensions", {}) if isinstance(merged.get("extensions"), dict) else {}
        if existing_extensions:
            merged_extensions.update(existing_extensions)
        if merged_extensions:
            merged["extensions"] = merged_extensions
        _write_json_atomic(anchor_path, merged)
        errs = validate_file(self.repo_root, anchor_path)
        if errs:
            raise RuntimeError("; ".join(errs))
        if logger is not None:
            logger.append(
                "VALIDATION",
                role="Orchestrator",
                phase_id=phase,
                loop_id="l1",
                agent_id=self.root_agent_id,
                parent_id=None,
                summary=(
                    f"anchor union merged {union_metrics['active_contexts']} context(s), "
                    f"{union_metrics['checklist_items_count']} checklist item(s), "
                    f"{union_metrics['checklist_conflicts_count']} conflict(s)"
                ),
                prompt_template_id=f"prompt_{phase}",
                step_id=self.step_id,
                content_extra=self._phase_validation_content(
                    passed=True,
                    schema_status="pass",
                    deep_status="pass",
                    governance_status="n/a",
                ),
                metadata_extra={"anchor_union_metrics": union_metrics},
            )
        return union_metrics

    def _update_roadmap_status(self, roadmap_path: str, status: str) -> None:
        roadmap = _read_json(roadmap_path)
        milestones = roadmap.get("milestones", [])
        if not isinstance(milestones, list):
            return
        for milestone in milestones:
            if isinstance(milestone, dict) and milestone.get("milestone_id") == self.step_id:
                milestone["status"] = status
        _write_json_atomic(roadmap_path, roadmap)

    def _write_session_state(
        self,
        *,
        session_state_path: str,
        active_phase: str,
        status: str,
        pending_child_id: Optional[str],
        pending_spawn_ref: Optional[str],
        pending_questions: Optional[List[str]] = None,
        session_log_ref: Optional[str] = None,
        spawn_log_ref: Optional[str],
        scratchpad_ref: Optional[str],
        retry_counters: dict,
    ) -> None:
        if session_log_ref is None and os.path.exists(session_state_path):
            try:
                existing = _read_json(session_state_path)
                existing_ref = existing.get("session_log_ref")
                if isinstance(existing_ref, str) and existing_ref:
                    session_log_ref = existing_ref
            except Exception:
                session_log_ref = None
        payload = {
            "protocol_version": PROTO_VER,
            "run_id": self.run_id,
            "parent_id": self.root_agent_id,
            "active_phase": active_phase,
            "step_id": self.step_id,
            "status": status,
            "pending_child_id": pending_child_id,
            "pending_spawn_ref": pending_spawn_ref,
            "pending_questions": pending_questions,
            "session_log_ref": session_log_ref,
            "spawn_log_ref": spawn_log_ref,
            "scratchpad_ref": scratchpad_ref,
            "last_event_id": None,
            "retry_counters": retry_counters,
            "updated_at": _utc_now(),
        }
        _write_json_atomic(session_state_path, payload)
        errs = validate_runtime_file(self.repo_root, session_state_path, "session_state")
        if errs:
            raise RuntimeError("; ".join(errs))

    def _update_spawn_log(
        self,
        *,
        spawn_log_path: str,
        child_id: str,
        role: str,
        phase: str,
        attempt: int,
        checklist_scope: List[str],
        task_input_ref: Optional[str],
        task_result_ref: Optional[str],
        task_result: dict,
    ) -> None:
        if os.path.exists(spawn_log_path):
            payload = _read_json(spawn_log_path)
        else:
            payload = {"protocol_version": PROTO_VER, "run_id": self.run_id, "entries": []}
        if payload.get("run_id") != self.run_id:
            payload = {"protocol_version": PROTO_VER, "run_id": self.run_id, "entries": []}
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        now = _utc_now()
        entries.append(
            {
                "spawn_id": f"spawn-{uuid.uuid4().hex[:12]}",
                "parent_id": self.root_agent_id,
                "child_id": child_id,
                "purpose": f"{role} {phase}",
                "phase": phase,
                "step_id": self.step_id,
                "attempt": max(1, int(attempt)),
                "checklist_scope": self._normalize_checklist_scope(checklist_scope),
                "status": (
                    "completed"
                    if task_result.get("status") == "success"
                    else "blocked"
                    if task_result.get("status") in {"blocked", "questions"}
                    else "failed"
                ),
                "task_input_ref": task_input_ref,
                "task_result_ref": task_result_ref,
                "created_at": now,
                "updated_at": now,
            }
        )
        payload["entries"] = entries
        _write_json_atomic(spawn_log_path, payload)
        errs = validate_runtime_file(self.repo_root, spawn_log_path, "spawn_log")
        if errs:
            raise RuntimeError("; ".join(errs))

    def _write_scratchpad(
        self,
        scratchpad_path: str,
        *,
        phase: str,
        next_action_ref: str,
        state_summary: str,
        checklist_scope: List[str],
        validation_gate: Optional[dict] = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        gate = validation_gate if isinstance(validation_gate, dict) else {}
        payload = {
            "phase": phase,
            "checklist_scope": checklist_scope,
            "last_validation_gate": {
                "schema": gate.get("schema") if gate.get("schema") in {"pass", "fail", "n/a"} else "n/a",
                "deep_validator": (
                    gate.get("deep_validator") if gate.get("deep_validator") in {"pass", "fail", "n/a"} else "n/a"
                ),
                "governance": gate.get("governance") if gate.get("governance") in {"pass", "fail", "n/a"} else "n/a",
            },
            "next_action_ref": next_action_ref,
            "state_summary": state_summary,
            "variables": {"step_id": self.step_id},
            "milestone_step_id": self.step_id,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        _write_json_atomic(scratchpad_path, payload)
        errs = validate_runtime_file(self.repo_root, scratchpad_path, "scratchpad_state")
        if errs:
            raise RuntimeError("; ".join(errs))

    def _planner_handler(self, milestone_path: str):
        def _handler(task_input: dict, context_pack: dict, child_id: str) -> dict:
            try:
                milestone = self._ensure_milestone_artifact(milestone_path, context_pack=context_pack)
            except Exception as e:  # noqa: BLE001
                return self._task_result(
                    child_id=child_id,
                    role="Planner",
                    phase="16a",
                    status="blocked",
                    summary="Planner blocked: missing or invalid milestone artifact",
                    artifacts=[],
                    findings=[
                        self._finding(
                            "planner-missing-milestone-artifact",
                            "gap",
                            "blocking",
                            str(e),
                        )
                    ],
                )
            plan = milestone.get("plan", {})
            if not isinstance(plan, dict):
                return self._task_result(
                    child_id=child_id,
                    role="Planner",
                    phase="16a",
                    status="blocked",
                    summary="Planner blocked: missing plan section",
                    artifacts=[],
                    findings=[self._finding("planner-missing-plan", "gap", "blocking", "Plan section missing in milestone context.")],
                )
            checklist = plan.get("spec_alignment", {}).get("checklist", [])
            if not isinstance(checklist, list) or not checklist:
                return self._task_result(
                    child_id=child_id,
                    role="Planner",
                    phase="16a",
                    status="blocked",
                    summary="Planner blocked: checklist is missing",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[
                        self._finding(
                            "planner-missing-checklist",
                            "gap",
                            "blocking",
                            "plan.spec_alignment.checklist must be present and non-empty; planner will not invent checklist entries.",
                        )
                    ],
                )
            _write_json_atomic(milestone_path, milestone)
            errs = validate_file(self.repo_root, milestone_path)
            if errs:
                return self._task_result(
                    child_id=child_id,
                    role="Planner",
                    phase="16a",
                    status="failed",
                    summary="Planner failed: milestone validation errors",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[self._finding("planner-validation-failed", "policy", "blocking", "; ".join(errs))],
                )
            return self._task_result(
                child_id=child_id,
                role="Planner",
                phase="16a",
                status="success",
                summary="Planner produced valid milestone plan artifact",
                artifacts=[_rel(self.repo_root, milestone_path)],
            )

        return _handler

    def _builder_handler(self, milestone_path: str, logger: SessionLogger):
        def _linked_expectation_commands(item: dict) -> Set[str]:
            linked = item.get("linked_test_expectation")
            commands: Set[str] = set()
            if isinstance(linked, str) and linked.strip():
                commands.add(linked.strip())
            elif isinstance(linked, list):
                for entry in linked:
                    if isinstance(entry, str) and entry.strip():
                        commands.add(entry.strip())
            return commands

        def _slug(text: object) -> str:
            return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"

        def _handler(task_input: dict, context_pack: dict, child_id: str) -> dict:
            milestone = _read_json(milestone_path)
            plan = milestone.get("plan", {})
            if not isinstance(plan, dict):
                return self._task_result(
                    child_id=child_id,
                    role="Builder",
                    phase="16b",
                    status="blocked",
                    summary="Builder blocked: missing plan",
                    artifacts=[],
                    findings=[self._finding("builder-missing-plan", "gap", "blocking", "Plan section missing.")],
                )

            checklist = plan.get("spec_alignment", {}).get("checklist", [])
            if not isinstance(checklist, list):
                return self._task_result(
                    child_id=child_id,
                    role="Builder",
                    phase="16b",
                    status="blocked",
                    summary="Builder blocked: missing checklist",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[
                        self._finding(
                            "builder-missing-checklist",
                            "gap",
                            "blocking",
                            "plan.spec_alignment.checklist must be a list.",
                        )
                    ],
                )

            tools = ToolExecutor(
                self.repo_root,
                logger,
                self.run_id,
                agent_id=self.root_agent_id,
                phase="16b",
                step_id=self.step_id,
                allowed_read_paths=context_pack.get("allowed_read_paths", []),
                allowed_write_paths=context_pack.get("allowed_write_paths", []),
                target_file_patterns=context_pack.get("target_file_patterns", []),
                docs_policy=context_pack.get("docs_policy", {}),
                protected_write_paths=(
                    ([context_pack.get("seed_manifest_path")] if isinstance(context_pack.get("seed_manifest_path"), str) else [])
                    + (
                        context_pack.get("seed_files_ordered", [])
                        if isinstance(context_pack.get("seed_files_ordered"), list)
                        else []
                    )
                ),
                enable_checkpoints=self.config.checkpoint_commits,
            )

            execution_results: List[dict] = []
            command_order: List[str] = []
            command_cache: Dict[str, dict] = {}
            passed_commands: Set[str] = set()
            builder_findings: List[dict] = []
            files_touched: Set[str] = set()
            satisfied_checklist_ids: List[str] = []

            def _run_command(command: str) -> dict:
                if command in command_cache:
                    return command_cache[command]
                tool_result = tools.call(
                    "exec_cmd",
                    {"command": command, "mode": "standard", "timeout_seconds": 300},
                    role="Builder",
                    parent_id=self.root_agent_id,
                    loop_id="l3",
                )
                status = tool_result.get("status")
                exit_code = tool_result.get("exit_code")
                stdout_excerpt = tool_result.get("stdout_excerpt") or ""
                stderr_excerpt = tool_result.get("stderr_excerpt") or ""
                evidence, has_success_marker = _extract_command_excerpt(
                    stdout_excerpt,
                    stderr_excerpt,
                    exit_code if isinstance(exit_code, int) else 1,
                )
                combined_output = ((stdout_excerpt or "") + ("\n" + stderr_excerpt if stderr_excerpt else "")).strip()
                passed = (
                    status == "success"
                    and isinstance(exit_code, int)
                    and exit_code == 0
                    and has_success_marker
                )
                if passed and len(evidence) < 20:
                    if len(combined_output) >= 20:
                        evidence = combined_output[:400]
                    else:
                        passed = False
                        evidence = "Blocked: command exited 0 but lacked sufficient verbatim success evidence."
                if len(evidence) < 20:
                    if len(combined_output) >= 20:
                        evidence = combined_output[:400]
                    else:
                        evidence = (evidence + " :: evidence length below contract minimum").ljust(20, ".")[:400]
                binding_sha = _sha256_text(evidence)
                execution_results.append(
                    {
                        "status": (
                            "passed"
                            if passed
                            else "blocked"
                            if status == "blocked"
                            or (status == "success" and isinstance(exit_code, int) and exit_code == 0 and not has_success_marker)
                            else "partial"
                            if status == "timeout"
                            else "failed"
                        ),
                        "outcome_description": (
                            "Command passed"
                            if passed
                            else "Command exited without required success marker"
                            if (status == "success" and isinstance(exit_code, int) and exit_code == 0 and not has_success_marker)
                            else "Command did not pass"
                        ),
                        "reasoning": "Deterministic command execution in Trinity builder phase.",
                        "command": command,
                        "evidence": evidence,
                        "evidence_ref": f"sha256:{binding_sha}",
                        "evidence_binding": {
                            "timestamp": _utc_now(),
                            "sha256": binding_sha,
                            "exit_code": int(exit_code) if isinstance(exit_code, int) else 1,
                            "command": command,
                        },
                    }
                )
                if command not in command_order:
                    command_order.append(command)
                if passed:
                    passed_commands.add(command)
                payload = {"passed": passed, "evidence": evidence, "evidence_ref": f"sha256:{binding_sha}"}
                command_cache[command] = payload
                return payload

            review_req = plan.get("review_requirements", {}) if isinstance(plan.get("review_requirements"), dict) else {}
            test_commands_raw = review_req.get("test_commands", []) if isinstance(review_req.get("test_commands"), list) else []
            normalized_cmds = [cmd for cmd in (_normalize_test_command(x) for x in test_commands_raw) if cmd]
            if not normalized_cmds:
                return self._task_result(
                    child_id=child_id,
                    role="Builder",
                    phase="16b",
                    status="blocked",
                    summary="Builder blocked: review_requirements.test_commands missing",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[
                        self._finding(
                            "builder-missing-test-contract",
                            "policy",
                            "blocking",
                            "plan.review_requirements.test_commands must be provided; runtime will not inject synthetic default commands.",
                        )
                    ],
                )
            if isinstance(checklist, list):
                for idx, item in enumerate(checklist):
                    if not isinstance(item, dict):
                        continue
                    if item.get("checklist_status", "active") == "deferred":
                        continue
                    item_id = item.get("id", f"checklist-{idx + 1}")
                    impl = item.get("implementation")
                    if not isinstance(impl, dict):
                        impl = {"status": "deferred", "actions": []}
                        item["implementation"] = impl
                        builder_findings.append(
                            self._finding(
                                f"builder-missing-implementation-{_slug(item_id)}",
                                "gap",
                                "major",
                                f"Checklist item '{item_id}' is active but missing implementation actions.",
                            )
                        )
                        continue
                    actions = impl.get("actions")
                    if not isinstance(actions, list):
                        actions = []
                    if not actions:
                        impl["status"] = "deferred"
                        impl["actions"] = []
                        builder_findings.append(
                            self._finding(
                                f"builder-empty-actions-{_slug(item_id)}",
                                "gap",
                                "major",
                                f"Checklist item '{item_id}' has no implementation.actions to execute.",
                            )
                        )
                        continue

                    impl["status"] = "in_progress"
                    item_files_touched: Set[str] = set()
                    existing_touched = impl.get("files_touched", [])
                    if isinstance(existing_touched, list):
                        for touched in existing_touched:
                            if isinstance(touched, str) and touched:
                                item_files_touched.add(touched)
                    item_verified = True

                    for action_idx, action in enumerate(actions):
                        if not isinstance(action, dict):
                            item_verified = False
                            continue
                        action_type = action.get("type")
                        target = action.get("target")

                        if action_type == "run_command":
                            command = action.get("command")
                            if not isinstance(command, str) or not command.strip():
                                item_verified = False
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": "Blocked: run_command action missing command.",
                                }
                                builder_findings.append(
                                    self._finding(
                                        f"builder-missing-command-{_slug(item_id)}-{action_idx + 1}",
                                        "gap",
                                        "major",
                                        f"Checklist item '{item_id}' has run_command action without a command.",
                                    )
                                )
                                continue
                            result = _run_command(command.strip())
                            action["evidence"] = {
                                "type": "snippet",
                                "content": result["evidence"],
                                "evidence_ref": result["evidence_ref"],
                            }
                            if not result["passed"]:
                                item_verified = False
                            continue

                        if action_type == "manual_verification":
                            linked = _linked_expectation_commands(item)
                            selected: Optional[dict] = None
                            for command in linked:
                                if command in command_cache and command_cache[command]["passed"]:
                                    selected = command_cache[command]
                                    break
                            if selected is None:
                                for command in command_order:
                                    maybe = command_cache.get(command)
                                    if maybe and maybe["passed"]:
                                        selected = maybe
                                        break
                            if selected is None:
                                item_verified = False
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": "Blocked: manual_verification has no passing command evidence.",
                                }
                            else:
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": selected["evidence"],
                                    "evidence_ref": selected["evidence_ref"],
                                }
                            continue

                        if action_type == "file_create":
                            if not isinstance(target, str) or not target.strip():
                                item_verified = False
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": "Blocked: file_create action missing target.",
                                }
                                builder_findings.append(
                                    self._finding(
                                        f"builder-missing-target-{_slug(item_id)}-{action_idx + 1}",
                                        "gap",
                                        "major",
                                        f"Checklist item '{item_id}' has file_create action without target.",
                                    )
                                )
                                continue
                            rel_target = target.strip()
                            abs_target = os.path.join(self.repo_root, rel_target)
                            if os.path.exists(abs_target):
                                check = tools.call(
                                    "read_file",
                                    {"path": rel_target, "start_line": 1, "end_line": 1},
                                    role="Builder",
                                    parent_id=self.root_agent_id,
                                    loop_id="l3",
                                )
                                ok = check.get("status") == "success"
                                evidence = "file_create target already exists and is readable."
                                evidence_ref = f"sha256:{_sha256_text(evidence)}"
                            else:
                                write = tools.call(
                                    "write_file",
                                    {"path": rel_target, "content": "", "mode": "create_new", "create_parents": True},
                                    role="Builder",
                                    parent_id=self.root_agent_id,
                                    loop_id="l3",
                                )
                                ok = write.get("status") == "success"
                                evidence = "Created empty file for deterministic file_create action."
                                evidence_ref = f"sha256:{_sha256_text(evidence)}"
                                if ok:
                                    item_files_touched.add(rel_target)
                            action["evidence"] = {"type": "snippet", "content": evidence, "evidence_ref": evidence_ref}
                            if not ok:
                                item_verified = False
                            continue

                        if action_type == "file_edit":
                            if not isinstance(target, str) or not target.strip():
                                item_verified = False
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": "Blocked: file_edit action missing target.",
                                }
                                builder_findings.append(
                                    self._finding(
                                        f"builder-edit-missing-target-{_slug(item_id)}-{action_idx + 1}",
                                        "gap",
                                        "major",
                                        f"Checklist item '{item_id}' has file_edit action without target.",
                                    )
                                )
                                continue
                            command = action.get("command")
                            if not isinstance(command, str) or not command.strip():
                                item_verified = False
                                action["evidence"] = {
                                    "type": "snippet",
                                    "content": "Blocked: file_edit action missing deterministic command.",
                                }
                                builder_findings.append(
                                    self._finding(
                                        f"builder-edit-missing-command-{_slug(item_id)}-{action_idx + 1}",
                                        "gap",
                                        "major",
                                        (
                                            f"Checklist item '{item_id}' has file_edit action for '{target}' without a command; "
                                            "runtime does not invent edit instructions."
                                        ),
                                    )
                                )
                                continue
                            rel_target = target.strip()
                            abs_target = os.path.join(self.repo_root, rel_target)
                            before_hash = _sha256_file(abs_target) if os.path.exists(abs_target) else None
                            result = _run_command(command.strip())
                            action["evidence"] = {
                                "type": "snippet",
                                "content": result["evidence"],
                                "evidence_ref": result["evidence_ref"],
                            }
                            if result["passed"]:
                                after_hash = _sha256_file(abs_target) if os.path.exists(abs_target) else None
                                if before_hash == after_hash:
                                    item_verified = False
                                    builder_findings.append(
                                        self._finding(
                                            f"builder-edit-no-mutation-{_slug(item_id)}-{action_idx + 1}",
                                            "gap",
                                            "major",
                                            (
                                                f"Checklist item '{item_id}' file_edit action for '{rel_target}' "
                                                "reported a passing command but produced no target file mutation."
                                            ),
                                        )
                                    )
                                else:
                                    item_files_touched.add(rel_target)
                            else:
                                item_verified = False
                            continue

                        item_verified = False
                        action["evidence"] = {
                            "type": "snippet",
                            "content": f"Blocked: unsupported action type '{action_type}'.",
                        }
                        builder_findings.append(
                            self._finding(
                                f"builder-unsupported-action-{_slug(item_id)}-{action_idx + 1}",
                                "policy",
                                "major",
                                f"Checklist item '{item_id}' uses unsupported action type '{action_type}'.",
                            )
                        )

                    expected_commands = _linked_expectation_commands(item)
                    missing_expected = sorted(cmd for cmd in expected_commands if cmd not in passed_commands)
                    if missing_expected:
                        item_verified = False
                        builder_findings.append(
                            self._finding(
                                f"builder-missing-linked-command-{_slug(item_id)}",
                                "tests",
                                "major",
                                (
                                    f"Checklist item '{item_id}' linked_test_expectation commands were not observed as passing: "
                                    + ", ".join(missing_expected)
                                ),
                            )
                        )

                    impl["status"] = "verified" if item_verified else "deferred"
                    impl["actions"] = actions
                    impl["files_touched"] = sorted(item_files_touched)
                    files_touched.update(item_files_touched)
                    if item_verified and isinstance(item_id, str):
                        satisfied_checklist_ids.append(item_id)

            for command in normalized_cmds:
                _run_command(command)

            execution = milestone.get("execution", {})
            if not isinstance(execution, dict):
                execution = {}
            existing_files_touched = execution.get("files_touched", [])
            if isinstance(existing_files_touched, list):
                for touched in existing_files_touched:
                    if isinstance(touched, str) and touched:
                        files_touched.add(touched)
            execution["files_touched"] = sorted(files_touched)
            execution["execution_results"] = execution_results
            execution["critical_evidence"] = {
                "satisfied_checklist_ids": sorted(dict.fromkeys(satisfied_checklist_ids)),
                "passed_test_commands": [cmd for cmd in command_order if cmd in passed_commands],
            }
            milestone["execution"] = execution
            _write_json_atomic(milestone_path, milestone)
            errs = validate_file(self.repo_root, milestone_path)
            if errs:
                return self._task_result(
                    child_id=child_id,
                    role="Builder",
                    phase="16b",
                    status="failed",
                    summary="Builder failed: milestone execution artifact invalid",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[self._finding("builder-validation-failed", "policy", "blocking", "; ".join(errs))],
                )
            return self._task_result(
                child_id=child_id,
                role="Builder",
                phase="16b",
                status="success",
                summary="Builder executed checklist actions and updated execution evidence",
                artifacts=[_rel(self.repo_root, milestone_path)],
                findings=builder_findings if builder_findings else None,
            )

        return _handler

    def _verifier_handler(self, milestone_path: str):
        def _linked_expectation_commands(item: dict) -> Set[str]:
            linked = item.get("linked_test_expectation")
            commands: Set[str] = set()
            if isinstance(linked, str) and linked.strip():
                commands.add(linked.strip())
            elif isinstance(linked, list):
                for entry in linked:
                    if isinstance(entry, str) and entry.strip():
                        commands.add(entry.strip())
            return commands

        def _valid_spec_ref(ref: object) -> bool:
            return (
                isinstance(ref, dict)
                and isinstance(ref.get("type"), str)
                and isinstance(ref.get("id"), str)
                and isinstance(ref.get("line_range"), str)
                and isinstance(ref.get("commit_hash"), str)
            )

        def _remediation(idx: int, summary: str, checklist_id: Optional[str]) -> dict:
            return {
                "task_id": f"rev-{self.step_id}-{idx}",
                "summary": summary,
                "files_to_touch": [],
                "checklist_ids": [checklist_id] if isinstance(checklist_id, str) else [],
            }

        def _handler(task_input: dict, context_pack: dict, child_id: str) -> dict:
            milestone = _read_json(milestone_path)
            plan = milestone.get("plan", {}) if isinstance(milestone.get("plan"), dict) else {}
            checklist = plan.get("spec_alignment", {}).get("checklist", []) if isinstance(plan.get("spec_alignment"), dict) else []
            execution = milestone.get("execution", {}) if isinstance(milestone.get("execution"), dict) else {}
            results = execution.get("execution_results", []) if isinstance(execution.get("execution_results"), list) else []
            passed_cmds = execution.get("critical_evidence", {}).get("passed_test_commands", [])
            passed_commands = {cmd for cmd in passed_cmds if isinstance(cmd, str) and cmd}
            has_failures = any(isinstance(r, dict) and r.get("status") in {"failed", "blocked", "partial"} for r in results)
            findings: List[dict] = []
            active_items: List[dict] = []

            default_spec_ref = None
            if isinstance(checklist, list):
                for item in checklist:
                    if not isinstance(item, dict):
                        continue
                    if item.get("checklist_status", "active") != "deferred":
                        active_items.append(item)
                    candidate = item.get("spec_ref")
                    if _valid_spec_ref(candidate):
                        default_spec_ref = candidate
                        break

            if not active_items:
                findings.append(
                    {
                        "id": "finding-no-active-checklist-001",
                        "type": "gap",
                        "severity": "blocking",
                        "spec_ref": default_spec_ref
                        if _valid_spec_ref(default_spec_ref)
                        else {
                            "type": "api",
                            "id": "interface-contracts",
                            "line_range": "L1-L1",
                            "commit_hash": _git_head(self.repo_root) or "0" * 40,
                        },
                        "description": "Milestone contains no active checklist items; verified closure is not allowed.",
                        "metadata": {"source": "Verifier", "impact": "No implementable contract executed"},
                        "remediation_task": _remediation(0, "Planner must provide at least one active checklist item.", None),
                    }
                )

            if has_failures:
                findings.append(
                    {
                        "id": "finding-builder-failure-001",
                        "type": "tests",
                        "severity": "blocking",
                        "spec_ref": default_spec_ref if _valid_spec_ref(default_spec_ref) else {
                            "type": "api",
                            "id": "interface-contracts",
                            "line_range": "L1-L1",
                            "commit_hash": _git_head(self.repo_root) or "0" * 40,
                        },
                        "description": "Execution contains failed command results.",
                        "metadata": {"source": "Verifier", "impact": "Milestone cannot be verified"},
                        "remediation_task": _remediation(1, "Fix failing builder command and rerun planner-first loop.", None),
                    }
                )

            fixture_results: List[dict] = []
            if isinstance(checklist, list):
                for idx, item in enumerate(checklist):
                    if not isinstance(item, dict):
                        continue
                    if item.get("checklist_status", "active") == "deferred":
                        continue
                    checklist_id = item.get("id") if isinstance(item.get("id"), str) else f"item-{idx + 1}"
                    spec_ref = item.get("spec_ref") if _valid_spec_ref(item.get("spec_ref")) else default_spec_ref
                    if not _valid_spec_ref(spec_ref):
                        continue
                    impl = item.get("implementation")
                    verified = isinstance(impl, dict) and impl.get("status") == "verified"
                    if not verified:
                        findings.append(
                            {
                                "id": f"finding-checklist-not-verified-{idx + 1}",
                                "type": "gap",
                                "severity": "major",
                                "spec_ref": spec_ref,
                                "description": f"Checklist item '{checklist_id}' is not verified in implementation output.",
                                "metadata": {"source": "Verifier", "impact": "Spec contract remains incomplete"},
                                "remediation_task": _remediation(
                                    idx + 2,
                                    f"Complete checklist item '{checklist_id}' and provide evidence.",
                                    checklist_id,
                                ),
                            }
                        )
                    else:
                        actions = impl.get("actions", [])
                        missing_evidence = False
                        if not isinstance(actions, list) or not actions:
                            missing_evidence = True
                        else:
                            for action in actions:
                                if not (isinstance(action, dict) and isinstance(action.get("evidence"), dict)):
                                    missing_evidence = True
                                    break
                        if missing_evidence:
                            findings.append(
                                {
                                    "id": f"finding-missing-evidence-{idx + 1}",
                                    "type": "tests",
                                    "severity": "major",
                                    "spec_ref": spec_ref,
                                    "description": f"Checklist item '{checklist_id}' is verified but action evidence is incomplete.",
                                    "metadata": {"source": "Verifier", "impact": "Evidence-binding contract violated"},
                                    "remediation_task": _remediation(
                                        idx + 20,
                                        f"Attach action evidence for checklist item '{checklist_id}'.",
                                        checklist_id,
                                    ),
                                }
                            )
                        expected_commands = _linked_expectation_commands(item)
                        missing_commands = sorted(cmd for cmd in expected_commands if cmd not in passed_commands)
                        if missing_commands:
                            findings.append(
                                {
                                    "id": f"finding-missing-linked-tests-{idx + 1}",
                                    "type": "tests",
                                    "severity": "major",
                                    "spec_ref": spec_ref,
                                    "description": (
                                        f"Checklist item '{checklist_id}' missing passed linked_test_expectation commands: "
                                        + ", ".join(missing_commands)
                                    ),
                                    "metadata": {"source": "Verifier", "impact": "Cannot prove requirement closure"},
                                    "remediation_task": _remediation(
                                        idx + 40,
                                        f"Run and pass linked test expectations for '{checklist_id}'.",
                                        checklist_id,
                                    ),
                                }
                            )

                    fixture_ref = item.get("fixture_ref")
                    if isinstance(fixture_ref, str) and fixture_ref:
                        fixture_results.append(
                            {"fixture_ref": fixture_ref, "status": "pass" if verified else "fail"}
                        )

            has_blocking = any(isinstance(f, dict) and f.get("severity") == "blocking" for f in findings)
            has_major = any(isinstance(f, dict) and f.get("severity") == "major" for f in findings)
            if has_blocking:
                verdict = "rejected"
            elif has_major:
                verdict = "deferred"
            else:
                verdict = "verified"

            if not fixture_results:
                fixture_results = []

            findings_count = len(findings)
            ratings = {
                "spec_completeness": 5 if findings_count == 0 else 2 if has_blocking else 3,
                "code_quality": 4 if findings_count == 0 else 2,
                "tests_completeness": 5 if verdict == "verified" else 2,
                "docs_completeness": 4 if verdict == "verified" else 3,
                "metadata_usage": 5 if findings_count == 0 else 4,
            }

            review = milestone.get("review", {})
            if not isinstance(review, dict):
                review = {}
            review.update(
                {
                    "findings": findings,
                    "ratings": ratings,
                    "verdict": verdict,
                    "next_actions": (
                        "Planner-first remediation required."
                        if verdict != "verified"
                        else "Milestone verified."
                    ),
                    "fixture_status": {
                        "implemented_endpoints": [],
                        "test_results": fixture_results,
                        "ci_status": "green" if verdict == "verified" else "red",
                    },
                }
            )
            milestone["review"] = review
            _write_json_atomic(milestone_path, milestone)
            errs = validate_file(self.repo_root, milestone_path)
            if errs:
                return self._task_result(
                    child_id=child_id,
                    role="Verifier",
                    phase="16c",
                    status="failed",
                    summary="Verifier failed: review artifact invalid",
                    artifacts=[_rel(self.repo_root, milestone_path)],
                    findings=[self._finding("verifier-validation-failed", "policy", "blocking", "; ".join(errs))],
                )
            return self._task_result(
                child_id=child_id,
                role="Verifier",
                phase="16c",
                status="success",
                summary=f"Verifier completed with verdict={verdict}",
                artifacts=[_rel(self.repo_root, milestone_path)],
            )

        return _handler

    def _verified_closure_issues(self, milestone: dict) -> List[str]:
        issues: List[str] = []
        review = milestone.get("review", {}) if isinstance(milestone.get("review"), dict) else {}
        verdict = review.get("verdict")
        if verdict != "verified":
            return issues

        findings = review.get("findings", [])
        if not isinstance(findings, list):
            issues.append("review.findings must be a list when review.verdict is 'verified'")
            return issues
        blocking_or_major = [
            f for f in findings
            if isinstance(f, dict) and f.get("severity") in {"blocking", "major"}
        ]
        if blocking_or_major:
            issues.append("review.verdict is 'verified' but review.findings contains blocking/major findings")

        execution = milestone.get("execution", {}) if isinstance(milestone.get("execution"), dict) else {}
        execution_results = execution.get("execution_results", [])
        if not isinstance(execution_results, list) or not execution_results:
            issues.append("review.verdict is 'verified' but execution.execution_results is missing or empty")
        else:
            bad_results = [
                r for r in execution_results
                if isinstance(r, dict) and r.get("status") in {"failed", "blocked", "partial"}
            ]
            if bad_results:
                issues.append("review.verdict is 'verified' but execution results include failed/blocked/partial statuses")

        plan = milestone.get("plan", {}) if isinstance(milestone.get("plan"), dict) else {}
        spec_alignment = plan.get("spec_alignment", {}) if isinstance(plan.get("spec_alignment"), dict) else {}
        checklist = spec_alignment.get("checklist", [])
        if not isinstance(checklist, list) or not checklist:
            issues.append("review.verdict is 'verified' but plan.spec_alignment.checklist is missing or empty")
        else:
            for item in checklist:
                if not isinstance(item, dict):
                    continue
                if item.get("checklist_status", "active") == "deferred":
                    continue
                impl = item.get("implementation") if isinstance(item.get("implementation"), dict) else {}
                if impl.get("status") != "verified":
                    cid = item.get("id", "<unknown>")
                    issues.append(f"review.verdict is 'verified' but checklist item '{cid}' implementation.status is not 'verified'")
                    break
        return issues

    def _task_result(
        self,
        *,
        child_id: str,
        role: str,
        phase: str,
        status: str,
        summary: str,
        artifacts: List[str],
        findings: Optional[List[dict]] = None,
        questions: Optional[List[str]] = None,
    ) -> dict:
        payload = {
            "protocol_version": PROTO_VER,
            "child_id": child_id,
            "role": role,
            "phase": phase,
            "step_id": self.step_id,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
        }
        if findings is not None:
            payload["findings"] = findings
        if questions is not None:
            payload["questions"] = questions
        return payload

    def _finding(self, fid: str, ftype: str, severity: str, description: str) -> dict:
        return {
            "id": fid,
            "type": ftype,
            "severity": severity,
            "description": description,
            "source": "TrinityRuntime",
            "impact": "Blocking contract",
        }

    def _run_governance_gates(self, commit_message: str, milestone_path: str, anchor_path: str) -> dict:
        spec_dir = os.path.join(self.repo_root, "spec")
        schema_errors: List[str] = []
        seed_errors: List[str] = []
        docs_errors: List[str] = []
        commit_errors: List[str] = []

        if os.path.exists(milestone_path):
            schema_errors.extend(validate_file(self.repo_root, milestone_path))
        else:
            schema_errors.append(f"Missing milestone artifact for governance: {_rel(self.repo_root, milestone_path)}")
        if os.path.exists(anchor_path):
            schema_errors.extend(validate_file(self.repo_root, anchor_path))
        else:
            schema_errors.append(f"Missing anchor artifact for governance: {_rel(self.repo_root, anchor_path)}")

        seed_errors.extend(lint_seeds(self.repo_root, spec_dir))
        docs_errors.extend(lint_docs(spec_dir))
        commit_errors.extend(check_commit_message(spec_dir, commit_message))

        errors = schema_errors + seed_errors + docs_errors + commit_errors
        return {
            "errors": errors,
            "schema_status": "pass" if not schema_errors else "fail",
            "deep_status": "pass" if not schema_errors else "fail",
            "seed_lint_status": "pass" if not seed_errors else "fail",
            "docs_lint_status": "pass" if not docs_errors else "fail",
            "governance_status": "pass" if not errors else "fail",
            "schema_errors": schema_errors,
            "seed_errors": seed_errors,
            "docs_errors": docs_errors,
            "commit_errors": commit_errors,
        }

    def _record_governance_validation(
        self,
        *,
        logger: SessionLogger,
        phase: str,
        commit_message: str,
        milestone_path: str,
        anchor_path: str,
        gate_result: dict,
    ) -> None:
        summary = (
            f"{phase} governance validation {gate_result.get('governance_status', 'fail')} "
            f"({len(gate_result.get('errors', []))} issues)"
        )
        artifact_path = anchor_path if os.path.exists(anchor_path) else milestone_path
        artifact_ref = _rel(self.repo_root, artifact_path) if os.path.exists(artifact_path) else None
        artifact_sha = _sha256_file(artifact_path) if artifact_ref else None
        logger.append(
            "VALIDATION",
            role="Orchestrator",
            phase_id=phase,
            loop_id="l1",
            agent_id=self.root_agent_id,
            parent_id=None,
            summary=summary,
            prompt_template_id=f"prompt_{phase}",
            step_id=self.step_id,
            artifact_ref=artifact_ref,
            artifact_sha256=artifact_sha,
            content_extra=self._phase_validation_content(
                passed=gate_result.get("governance_status") == "pass",
                schema_status=gate_result.get("schema_status"),
                deep_status=gate_result.get("deep_status"),
                governance_status=gate_result.get("governance_status", "fail"),
                seed_lint_status=gate_result.get("seed_lint_status", "fail"),
                docs_lint_status=gate_result.get("docs_lint_status", "fail"),
            ),
        )

    def _finalize_terminal_result(self, logger: SessionLogger, payload: dict) -> dict:
        session_errors = validate_runtime_file(self.repo_root, logger.path, "session_event")
        if session_errors:
            return {
                "status": "blocked",
                "step_id": self.step_id,
                "run_id": self.run_id,
                "phase": "session_log",
                "errors": session_errors,
                "session_log": _rel(self.repo_root, logger.path),
            }
        finalized = dict(payload) if isinstance(payload, dict) else {}
        if "step_id" not in finalized and isinstance(self.step_id, str):
            finalized["step_id"] = self.step_id
        if "run_id" not in finalized:
            finalized["run_id"] = self.run_id
        if "session_log" not in finalized:
            finalized["session_log"] = _rel(self.repo_root, logger.path)
        return finalized

    def run(self) -> dict:
        roadmap = self._load_roadmap()
        resume_state = self._load_resume_state()
        if isinstance(resume_state, dict):
            resume_run_id = resume_state.get("run_id")
            resume_parent_id = resume_state.get("parent_id")
            if isinstance(resume_run_id, str) and resume_run_id:
                self.run_id = resume_run_id
            if isinstance(resume_parent_id, str) and resume_parent_id:
                self.root_agent_id = resume_parent_id
        self.step_id = self._pick_step_id(roadmap)
        if not self.step_id:
            raise RuntimeError("Unable to resolve step_id")

        if not self.config.allow_dirty and not self.resume and _is_dirty_worktree(self.repo_root):
            raise RuntimeError("Working tree must be clean before running Trinity. Set runtime.allow_dirty=true to override.")

        trinity_root = os.path.join(self.repo_root, ".trinity")
        runtime_dir = os.path.join(trinity_root, "runtime")
        os.makedirs(runtime_dir, exist_ok=True)
        milestone_path = os.path.join(self.repo_root, "spec", "impl_context", f"{self.step_id}.json")
        anchor_path = os.path.join(self.repo_root, "spec", "16_impl_context.json")
        session_state_path = os.path.join(runtime_dir, f"session_state_{self.root_agent_id}.json")
        spawn_log_path = os.path.join(runtime_dir, "spawn_log.json")
        scratchpad_path = os.path.join(runtime_dir, "scratchpads", f"scratchpad_{self.step_id}.json")
        resume_session_log_ref = resume_state.get("session_log_ref") if isinstance(resume_state, dict) else None
        if not isinstance(resume_session_log_ref, str):
            resume_session_log_ref = None

        resolver = ContextResolver(
            self.repo_root,
            self.step_id,
            milestone_path,
            anchor_path,
            allow_authority_fallback=self.config.allow_bootstrap_authority_fallback,
        )
        logger = SessionLogger(
            self.repo_root,
            self.run_id,
            self.root_agent_id,
            self.step_id,
            self.config.llm_model,
            decoding_temperature=self.config.llm_temperature,
            decoding_top_p=self.config.llm_top_p,
            decoding_max_tokens=self.config.llm_max_tokens,
            log_path=resume_session_log_ref,
        )
        def _terminal(payload: dict) -> dict:
            return self._finalize_terminal_result(logger, payload)

        tools = ToolExecutor(
            self.repo_root,
            logger,
            self.run_id,
            agent_id=self.root_agent_id,
            phase="16a",
            step_id=self.step_id,
            allowed_read_paths=["."],
            allowed_write_paths=["."],
            target_file_patterns=[],
            docs_policy={},
            protected_write_paths=[],
            enable_checkpoints=self.config.checkpoint_commits,
        )

        milestone_attempt = 0
        planner_retries = 0
        builder_retries = 0
        verifier_retries = 0
        if isinstance(resume_state, dict):
            retry_counters = resume_state.get("retry_counters", {})
            if isinstance(retry_counters, dict):
                planner_retries = int(retry_counters.get("planner", 0) or 0)
                builder_retries = int(retry_counters.get("builder", 0) or 0)
                verifier_retries = int(retry_counters.get("verifier", 0) or 0)
                milestone_attempt = int(retry_counters.get("milestone", 0) or 0)
        session_status = "resuming" if isinstance(resume_state, dict) else "idle"
        pending_child_id = resume_state.get("pending_child_id") if isinstance(resume_state, dict) else None
        pending_spawn_ref = resume_state.get("pending_spawn_ref") if isinstance(resume_state, dict) else None
        pending_questions = resume_state.get("pending_questions") if isinstance(resume_state, dict) else None
        if not isinstance(pending_child_id, str):
            pending_child_id = None
        if not isinstance(pending_spawn_ref, str):
            pending_spawn_ref = None
        if not isinstance(pending_questions, list):
            pending_questions = None
        self._write_session_state(
            session_state_path=session_state_path,
            active_phase="16a",
            status=session_status,
            pending_child_id=pending_child_id,
            pending_spawn_ref=pending_spawn_ref,
            pending_questions=pending_questions,
            session_log_ref=_rel(self.repo_root, logger.path),
            spawn_log_ref=".trinity/runtime/spawn_log.json",
            scratchpad_ref=_rel(self.repo_root, scratchpad_path),
            retry_counters={
                "planner": planner_retries,
                "builder": builder_retries,
                "verifier": verifier_retries,
                "milestone": milestone_attempt,
            },
        )
        if not self.resume or not os.path.exists(spawn_log_path):
            _write_json_atomic(
                spawn_log_path,
                {"protocol_version": PROTO_VER, "run_id": self.run_id, "entries": []},
            )
            spawn_log_errors = validate_runtime_file(self.repo_root, spawn_log_path, "spawn_log")
            if spawn_log_errors:
                raise RuntimeError("; ".join(spawn_log_errors))

        if self.config.conformance_mode and not self.config.checkpoint_commits:
            raise RuntimeError(
                "runtime.checkpoint_commits=false is only allowed when runtime.conformance_mode=false"
            )

        if self.config.checkpoint_commits:
            self._ensure_branch(tools)

        replayed_phase_results: Dict[str, Tuple[dict, List[str]]] = {}
        if isinstance(resume_state, dict):
            resumed = self._resume_pending_spawn(
                logger=logger,
                session_state_path=session_state_path,
                spawn_log_path=spawn_log_path,
                scratchpad_path=scratchpad_path,
                milestone_path=milestone_path,
                retry_counters={
                    "planner": planner_retries,
                    "builder": builder_retries,
                    "verifier": verifier_retries,
                    "milestone": milestone_attempt,
                },
                resume_state=resume_state,
            )
            if isinstance(resumed, dict):
                if resumed.get("status") == "questions":
                    return _terminal({
                        "status": "questions",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": resumed.get("phase"),
                        "questions": resumed.get("questions", []),
                        "pending_spawn_ref": resumed.get("pending_spawn_ref"),
                    })
                if resumed.get("status") == "blocked":
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": resumed.get("phase"),
                        "errors": resumed.get("errors", []),
                    })
                if resumed.get("status") == "replayed":
                    phase_key = resumed.get("phase")
                    if isinstance(phase_key, str):
                        replayed_phase_results[phase_key] = (
                            resumed.get("task_result", {}),
                            resumed.get("errors", []),
                        )

        while milestone_attempt < self.retry_caps["milestone"]:
            milestone_attempt += 1
            if "16a" in replayed_phase_results:
                planner_result, planner_errors = replayed_phase_results.pop("16a")
            else:
                planner_result, planner_errors = self._spawn_phase(
                    logger=logger,
                    resolver=resolver,
                    phase="16a",
                    role="Planner",
                    phase_label="Planner",
                    milestone_path=milestone_path,
                    anchor_path=anchor_path,
                    session_state_path=session_state_path,
                    spawn_log_path=spawn_log_path,
                    scratchpad_path=scratchpad_path,
                    retry_counters={
                        "planner": planner_retries,
                        "builder": builder_retries,
                        "verifier": verifier_retries,
                        "milestone": milestone_attempt,
                    },
                )
            if planner_result.get("status") == "questions":
                state_snapshot = _read_json(session_state_path) if os.path.exists(session_state_path) else {}
                return _terminal({
                    "status": "questions",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16a",
                    "questions": planner_result.get("questions", []),
                    "pending_spawn_ref": state_snapshot.get("pending_spawn_ref"),
                })
            if planner_errors or planner_result.get("status") != "success":
                planner_retries += 1
                if planner_retries >= self.retry_caps["planner"]:
                    self._write_session_state(
                        session_state_path=session_state_path,
                        active_phase="16a",
                        status="blocked",
                        pending_child_id=None,
                        pending_spawn_ref=None,
                        pending_questions=None,
                        spawn_log_ref=".trinity/runtime/spawn_log.json",
                        scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                        retry_counters={
                            "planner": planner_retries,
                            "builder": builder_retries,
                            "verifier": verifier_retries,
                            "milestone": milestone_attempt,
                        },
                    )
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": "16a",
                        "errors": planner_errors or planner_result.get("errors", []),
                    })
                continue

            try:
                self._regenerate_anchor(milestone_path, anchor_path, logger=logger, phase="16a")
            except Exception as e:  # noqa: BLE001
                return _terminal({
                    "status": "blocked",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16a-anchor",
                    "errors": [str(e)],
                })
            if self.config.checkpoint_commits:
                tools.phase = "16a"
                commit_message = f"trinity({self.step_id}): checkpoint after 16a"
                gate_result = self._run_governance_gates(commit_message, milestone_path, anchor_path)
                self._record_governance_validation(
                    logger=logger,
                    phase="16a",
                    commit_message=commit_message,
                    milestone_path=milestone_path,
                    anchor_path=anchor_path,
                    gate_result=gate_result,
                )
                self._write_scratchpad(
                    scratchpad_path,
                    phase="16a",
                    next_action_ref="phase:16a:checkpoint",
                    state_summary="16a governance gate evaluated",
                    checklist_scope=self._checklist_ids(milestone_path),
                    validation_gate={
                        "schema": gate_result.get("schema_status"),
                        "deep_validator": gate_result.get("deep_status"),
                        "governance": gate_result.get("governance_status"),
                    },
                )
                gate_errs = gate_result.get("errors", [])
                if gate_errs:
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": "16a-governance",
                        "errors": gate_errs,
                    })
                tools.call("checkpoint_commit", {"message": commit_message}, role="Orchestrator", loop_id="l1")

            if "16b" in replayed_phase_results:
                builder_result, builder_errors = replayed_phase_results.pop("16b")
            else:
                builder_result, builder_errors = self._spawn_phase(
                    logger=logger,
                    resolver=resolver,
                    phase="16b",
                    role="Builder",
                    phase_label="Builder",
                    milestone_path=milestone_path,
                    anchor_path=anchor_path,
                    session_state_path=session_state_path,
                    spawn_log_path=spawn_log_path,
                    scratchpad_path=scratchpad_path,
                    retry_counters={
                        "planner": planner_retries,
                        "builder": builder_retries,
                        "verifier": verifier_retries,
                        "milestone": milestone_attempt,
                    },
                )
            if builder_result.get("status") == "questions":
                state_snapshot = _read_json(session_state_path) if os.path.exists(session_state_path) else {}
                return _terminal({
                    "status": "questions",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16b",
                    "questions": builder_result.get("questions", []),
                    "pending_spawn_ref": state_snapshot.get("pending_spawn_ref"),
                })
            if builder_errors or builder_result.get("status") != "success":
                builder_retries += 1
                if builder_retries >= self.retry_caps["builder"]:
                    self._write_session_state(
                        session_state_path=session_state_path,
                        active_phase="16b",
                        status="blocked",
                        pending_child_id=None,
                        pending_spawn_ref=None,
                        pending_questions=None,
                        spawn_log_ref=".trinity/runtime/spawn_log.json",
                        scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                        retry_counters={
                            "planner": planner_retries,
                            "builder": builder_retries,
                            "verifier": verifier_retries,
                            "milestone": milestone_attempt,
                        },
                    )
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": "16b",
                        "errors": builder_errors or builder_result.get("errors", []),
                    })
                continue

            try:
                self._regenerate_anchor(milestone_path, anchor_path, logger=logger, phase="16b")
            except Exception as e:  # noqa: BLE001
                return _terminal({
                    "status": "blocked",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16b-anchor",
                    "errors": [str(e)],
                })
            if self.config.checkpoint_commits:
                tools.phase = "16b"
                commit_message = f"trinity({self.step_id}): checkpoint after 16b"
                gate_result = self._run_governance_gates(commit_message, milestone_path, anchor_path)
                self._record_governance_validation(
                    logger=logger,
                    phase="16b",
                    commit_message=commit_message,
                    milestone_path=milestone_path,
                    anchor_path=anchor_path,
                    gate_result=gate_result,
                )
                self._write_scratchpad(
                    scratchpad_path,
                    phase="16b",
                    next_action_ref="phase:16b:checkpoint",
                    state_summary="16b governance gate evaluated",
                    checklist_scope=self._checklist_ids(milestone_path),
                    validation_gate={
                        "schema": gate_result.get("schema_status"),
                        "deep_validator": gate_result.get("deep_status"),
                        "governance": gate_result.get("governance_status"),
                    },
                )
                gate_errs = gate_result.get("errors", [])
                if gate_errs:
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": "16b-governance",
                        "errors": gate_errs,
                    })
                tools.call("checkpoint_commit", {"message": commit_message}, role="Orchestrator", loop_id="l1")

            if "16c" in replayed_phase_results:
                verifier_result, verifier_errors = replayed_phase_results.pop("16c")
            else:
                verifier_result, verifier_errors = self._spawn_phase(
                    logger=logger,
                    resolver=resolver,
                    phase="16c",
                    role="Verifier",
                    phase_label="Verifier",
                    milestone_path=milestone_path,
                    anchor_path=anchor_path,
                    session_state_path=session_state_path,
                    spawn_log_path=spawn_log_path,
                    scratchpad_path=scratchpad_path,
                    retry_counters={
                        "planner": planner_retries,
                        "builder": builder_retries,
                        "verifier": verifier_retries,
                        "milestone": milestone_attempt,
                    },
                )
            if verifier_result.get("status") == "questions":
                state_snapshot = _read_json(session_state_path) if os.path.exists(session_state_path) else {}
                return _terminal({
                    "status": "questions",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16c",
                    "questions": verifier_result.get("questions", []),
                    "pending_spawn_ref": state_snapshot.get("pending_spawn_ref"),
                })
            if verifier_errors or verifier_result.get("status") != "success":
                verifier_retries += 1
                if verifier_retries >= self.retry_caps["verifier"]:
                    verifier_cap_errors = verifier_errors or verifier_result.get("errors", [])
                    if not verifier_cap_errors:
                        verifier_cap_errors = [
                            f"verifier retry cap exceeded after {verifier_retries} attempts without explicit error payload"
                        ]
                    self._write_session_state(
                        session_state_path=session_state_path,
                        active_phase="16c",
                        status="blocked",
                        pending_child_id=None,
                        pending_spawn_ref=None,
                        pending_questions=None,
                        spawn_log_ref=".trinity/runtime/spawn_log.json",
                        scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                        retry_counters={
                            "planner": planner_retries,
                            "builder": builder_retries,
                            "verifier": verifier_retries,
                            "milestone": milestone_attempt,
                        },
                    )
                    return _terminal({
                        "status": "blocked",
                        "step_id": self.step_id,
                        "run_id": self.run_id,
                        "phase": "16c",
                        "errors": verifier_cap_errors,
                    })
                continue
            milestone = _read_json(milestone_path)
            verdict = (
                milestone.get("review", {}).get("verdict")
                if isinstance(milestone.get("review"), dict)
                else None
            )
            try:
                self._regenerate_anchor(milestone_path, anchor_path, logger=logger, phase="16c")
            except Exception as e:  # noqa: BLE001
                return _terminal({
                    "status": "blocked",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "phase": "16c-anchor",
                    "errors": [str(e)],
                })
            if verdict == "verified":
                closure_issues = self._verified_closure_issues(milestone)
                if closure_issues:
                    verifier_retries += 1
                    if verifier_retries >= self.retry_caps["verifier"]:
                        self._write_session_state(
                            session_state_path=session_state_path,
                            active_phase="16c",
                            status="blocked",
                            pending_child_id=None,
                            pending_spawn_ref=None,
                            pending_questions=None,
                            spawn_log_ref=".trinity/runtime/spawn_log.json",
                            scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                            retry_counters={
                                "planner": planner_retries,
                                "builder": builder_retries,
                                "verifier": verifier_retries,
                                "milestone": milestone_attempt,
                            },
                        )
                        return _terminal({
                            "status": "blocked",
                            "step_id": self.step_id,
                            "run_id": self.run_id,
                            "phase": "16c-closure",
                            "errors": closure_issues,
                        })
                    continue
                self._update_roadmap_status(self._roadmap_path(), "done")
                if self.config.checkpoint_commits:
                    tools.phase = "16c"
                    commit_message = f"trinity({self.step_id}): final closure after 16c"
                    gate_result = self._run_governance_gates(commit_message, milestone_path, anchor_path)
                    self._record_governance_validation(
                        logger=logger,
                        phase="16c",
                        commit_message=commit_message,
                        milestone_path=milestone_path,
                        anchor_path=anchor_path,
                        gate_result=gate_result,
                    )
                    self._write_scratchpad(
                        scratchpad_path,
                        phase="16c",
                        next_action_ref="phase:16c:checkpoint",
                        state_summary="16c governance gate evaluated",
                        checklist_scope=self._checklist_ids(milestone_path),
                        validation_gate={
                            "schema": gate_result.get("schema_status"),
                            "deep_validator": gate_result.get("deep_status"),
                            "governance": gate_result.get("governance_status"),
                        },
                    )
                    gate_errs = gate_result.get("errors", [])
                    if gate_errs:
                        return _terminal({
                            "status": "blocked",
                            "step_id": self.step_id,
                            "run_id": self.run_id,
                            "phase": "16c-governance",
                            "errors": gate_errs,
                        })
                    tools.call("checkpoint_commit", {"message": commit_message}, role="Orchestrator", loop_id="l1")
                self._write_session_state(
                    session_state_path=session_state_path,
                    active_phase="16c",
                    status="done",
                    pending_child_id=None,
                    pending_spawn_ref=None,
                    pending_questions=None,
                    spawn_log_ref=".trinity/runtime/spawn_log.json",
                    scratchpad_ref=_rel(self.repo_root, scratchpad_path),
                    retry_counters={
                        "planner": planner_retries,
                        "builder": builder_retries,
                        "verifier": verifier_retries,
                        "milestone": milestone_attempt,
                    },
                )
                return _terminal({
                    "status": "completed",
                    "step_id": self.step_id,
                    "run_id": self.run_id,
                    "execution_mode": self.execution_mode,
                    "milestone_artifact": _rel(self.repo_root, milestone_path),
                    "anchor_artifact": _rel(self.repo_root, anchor_path),
                    "session_log": _rel(self.repo_root, logger.path),
                    "verdict": verdict,
                })
            # planner-first remediation
            continue

        self._write_session_state(
            session_state_path=session_state_path,
            active_phase="16a",
            status="blocked",
            pending_child_id=None,
            pending_spawn_ref=None,
            pending_questions=None,
            spawn_log_ref=".trinity/runtime/spawn_log.json",
            scratchpad_ref=_rel(self.repo_root, scratchpad_path),
            retry_counters={
                "planner": planner_retries,
                "builder": builder_retries,
                "verifier": verifier_retries,
                "milestone": milestone_attempt,
            },
        )
        return _terminal({
            "status": "blocked",
            "step_id": self.step_id,
            "run_id": self.run_id,
            "errors": ["global milestone retry cap exceeded"],
        })


def run_trinity_child(
    *,
    repo_root: str,
    step_id: str,
    phase: str,
    role: str,
    child_id: str,
    milestone_path: str,
    task_input_path: str,
    context_pack_path: str,
    task_result_path: str,
    session_log_path: str,
    run_id: str,
    parent_id: str,
    mode_override: Optional[str] = None,
) -> dict:
    config = TrinityConfig.load(repo_root)
    if isinstance(mode_override, str) and mode_override.strip():
        config.execution_mode = mode_override.strip().lower()
    runtime = TrinityRuntime(repo_root, config, step_id=step_id, resume=False, answers=None, resume_run_id=None)
    runtime.run_id = run_id
    runtime.root_agent_id = parent_id
    logger = SessionLogger(
        repo_root,
        run_id,
        child_id,
        step_id,
        config.llm_model,
        decoding_temperature=config.llm_temperature,
        decoding_top_p=config.llm_top_p,
        decoding_max_tokens=config.llm_max_tokens,
        log_path=session_log_path,
    )
    milestone_abs = milestone_path if os.path.isabs(milestone_path) else os.path.join(repo_root, milestone_path)
    task_input_abs = task_input_path if os.path.isabs(task_input_path) else os.path.join(repo_root, task_input_path)
    context_pack_abs = context_pack_path if os.path.isabs(context_pack_path) else os.path.join(repo_root, context_pack_path)
    task_result_abs = task_result_path if os.path.isabs(task_result_path) else os.path.join(repo_root, task_result_path)
    task_input = _read_json(task_input_abs)
    context_pack = _read_json(context_pack_abs)
    if phase == "16a":
        handler = (
            runtime._llm_phase_handler(milestone_abs, logger, phase="16a", role=role)
            if runtime.execution_mode == "llm"
            else runtime._planner_handler(milestone_abs)
        )
    elif phase == "16b":
        handler = (
            runtime._llm_phase_handler(milestone_abs, logger, phase="16b", role=role)
            if runtime.execution_mode == "llm"
            else runtime._builder_handler(milestone_abs, logger)
        )
    elif phase == "16c":
        handler = (
            runtime._llm_phase_handler(milestone_abs, logger, phase="16c", role=role)
            if runtime.execution_mode == "llm"
            else runtime._verifier_handler(milestone_abs)
        )
    elif phase == "utility":
        if runtime.execution_mode != "llm":
            result = runtime._task_result(
                child_id=child_id,
                role=role,
                phase=phase,
                status="blocked",
                summary=f"{role} blocked: utility phase requires llm execution mode",
                artifacts=[],
                findings=[
                    runtime._finding(
                        "utility-deterministic-unsupported",
                        "policy",
                        "blocking",
                        "Utility phase is only supported in llm execution mode.",
                    )
                ],
            )
            _write_json_atomic(task_result_abs, result)
            return result
        handler = runtime._llm_phase_handler(milestone_abs, logger, phase="utility", role=role)
    else:
        result = runtime._task_result(
            child_id=child_id,
            role=role,
            phase=phase,
            status="blocked",
            summary=f"{role} blocked: unsupported phase for child runner",
            artifacts=[],
            findings=[runtime._finding(f"child-unsupported-phase-{phase}", "policy", "blocking", f"Unsupported child phase '{phase}'")],
        )
        _write_json_atomic(task_result_abs, result)
        return result
    result = handler(task_input, context_pack, child_id)
    _write_json_atomic(task_result_abs, result)
    errors = validate_runtime_file(repo_root, task_result_abs, "task_result")
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def run_trinity(
    repo_root: str,
    step_id: Optional[str],
    resume: bool = False,
    mode_override: Optional[str] = None,
    answers: Optional[List[str]] = None,
    resume_run_id: Optional[str] = None,
) -> dict:
    config = TrinityConfig.load(repo_root)
    if isinstance(mode_override, str) and mode_override.strip():
        config.execution_mode = mode_override.strip().lower()
    runtime = TrinityRuntime(
        repo_root,
        config,
        step_id=step_id,
        resume=resume,
        answers=answers,
        resume_run_id=resume_run_id,
    )
    return runtime.run()
