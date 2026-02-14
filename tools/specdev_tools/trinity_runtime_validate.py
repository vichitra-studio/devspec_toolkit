from __future__ import annotations

import json
import os
import re
import subprocess
import hashlib
from typing import Optional, Dict
import fnmatch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .registry import SchemaRegistry


RUNTIME_SCHEMA_BY_TYPE: Dict[str, str] = {
    "task_input": "https://specdev.local/schema/trinity/task_input.schema.json",
    "context_pack": "https://specdev.local/schema/trinity/context_pack.schema.json",
    "task_result": "https://specdev.local/schema/trinity/task_result.schema.json",
    "tool_call_request": "https://specdev.local/schema/trinity/tool_call_request.schema.json",
    "tool_call_result": "https://specdev.local/schema/trinity/tool_call_result.schema.json",
    "utility_call": "https://specdev.local/schema/trinity/utility_call.schema.json",
    "utility_result": "https://specdev.local/schema/trinity/utility_result.schema.json",
    "session_event": "https://specdev.local/schema/trinity/session_event.schema.json",
    "log_capture_policy": "https://specdev.local/schema/trinity/log_capture_policy.schema.json",
    "eval_export_row": "https://specdev.local/schema/trinity/eval_export_row.schema.json",
    "scratchpad_state": "https://specdev.local/schema/trinity/scratchpad_state.schema.json",
    "session_state": "https://specdev.local/schema/trinity/session_state.schema.json",
    "spawn_log": "https://specdev.local/schema/trinity/spawn_log.schema.json",
}

_SPEC_REF_TYPE_BY_BASENAME: Dict[str, str] = {
    "04_fr_list.json": "fr",
    "05_interface_contracts.json": "api",
    "06_invariants.json": "inv",
    "07_nfrs.json": "nfr",
    "08_fixtures.json": "fixture",
}

_SENSITIVE_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "aws_secret_access_key": re.compile(r"\baws[_-]?secret[_-]?access[_-]?key\b[^\n]{0,40}[A-Za-z0-9/+=]{40}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "github_pat": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "gitlab_pat": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    "npm_token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}\b"),
    "jwt_token": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "generic_secret_assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{16,}"
    ),
}


def _registry_for(registry: SchemaRegistry) -> Registry:
    store = {uri: Resource.from_contents(schema) for uri, schema in registry.store.items()}
    return Registry().with_resources(store.items())


def detect_runtime_artifact_type(path: str) -> Optional[str]:
    norm = path.replace("\\", "/")
    name = os.path.basename(norm)

    if name == "task_input.json":
        return "task_input"
    if name == "context_pack.json":
        return "context_pack"
    if name == "task_result.json":
        return "task_result"
    if name == "tool_call_request.json":
        return "tool_call_request"
    if name == "tool_call_result.json":
        return "tool_call_result"
    if name == "utility_call.json":
        return "utility_call"
    if name == "utility_result.json":
        return "utility_result"
    if name.startswith("scratchpad_") and name.endswith(".json"):
        return "scratchpad_state"
    if name.startswith("session_state_") and name.endswith(".json"):
        return "session_state"
    if name == "spawn_log.json":
        return "spawn_log"
    if name == "log_capture_policy.json":
        return "log_capture_policy"
    if name == "eval_export_row.json":
        return "eval_export_row"
    if name.endswith(".jsonl") and "/.trinity/sessions/" in norm:
        return "session_event"
    return None


def maybe_validate_runtime_artifact(repo_root: str, path: str) -> Optional[list[str]]:
    artifact_type = detect_runtime_artifact_type(path)
    if not artifact_type:
        return None
    return validate_runtime_file(repo_root, path, artifact_type)


def _validate_payload(
    repo_root: str,
    path: str,
    payload: dict,
    schema_uri: str,
    line_no: Optional[int] = None,
) -> list[str]:
    registry = SchemaRegistry(repo_root)
    schema = registry.load(schema_uri)
    reg = _registry_for(registry)
    validator = Draft202012Validator(
        schema,
        registry=reg,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    prefix = f"{path}:{line_no}" if line_no is not None else path
    return [f"{prefix}:{'/'.join(map(str, e.path))}: {e.message}" for e in errors]


def _normalize_path(path: str) -> str:
    raw = path.replace("\\", "/").strip()
    if raw.startswith("./"):
        raw = raw[2:]
    normalized = os.path.normpath(raw or ".").replace("\\", "/")
    if normalized in {"", "."}:
        return "."
    return normalized


def _is_escape_path(path: str) -> bool:
    normalized = _normalize_path(path)
    return normalized == ".." or normalized.startswith("../")


def _find_git_root(repo_root: str) -> Optional[str]:
    cur = os.path.abspath(repo_root)
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _parse_line_range(value: str) -> Optional[tuple[int, int]]:
    match = re.match(r"^L(\d+)-L(\d+)$", value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _git_commit_exists(git_root: str, commit_hash: str, cache: dict[str, bool]) -> bool:
    if commit_hash in cache:
        return cache[commit_hash]
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
        cwd=git_root,
        capture_output=True,
        text=True,
        check=False,
    )
    cache[commit_hash] = result.returncode == 0
    return cache[commit_hash]


def _git_file_lines(
    git_root: str,
    commit_hash: str,
    rel_path: str,
    cache: dict[tuple[str, str], Optional[list[str]]],
) -> Optional[list[str]]:
    key = (commit_hash, rel_path)
    if key in cache:
        return cache[key]
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{rel_path}"],
        cwd=git_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        cache[key] = None
        return None
    cache[key] = result.stdout.splitlines()
    return cache[key]


def _line_range_contains_reference_id(lines: list[str], start: int, end: int, ref_id: str) -> bool:
    excerpt = "\n".join(lines[start - 1 : end])
    id_field_pattern = re.compile(rf'"id"\s*:\s*"{re.escape(ref_id)}"')
    quoted_id_pattern = re.compile(rf'"{re.escape(ref_id)}"')
    return bool(id_field_pattern.search(excerpt) or quoted_id_pattern.search(excerpt))


def _resolve_ref(base_file: str, ref: str, repo_root: str) -> str:
    if os.path.isabs(ref):
        return ref
    candidate_local = os.path.abspath(os.path.join(os.path.dirname(base_file), ref))
    if os.path.exists(candidate_local):
        return candidate_local
    return os.path.abspath(os.path.join(repo_root, ref))


def _detect_sensitive_classes(text: Optional[str]) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    hits: list[str] = []
    for cls, pattern in _SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            hits.append(cls)
    return hits


def _artifact_sensitive_classes(base_file: str, ref: Optional[str], repo_root: str) -> list[str]:
    if not isinstance(ref, str) or not ref:
        return []
    resolved = _resolve_ref(base_file, ref, repo_root)
    if not os.path.exists(resolved):
        return []
    try:
        with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(256 * 1024)
    except Exception:
        return []
    return _detect_sensitive_classes(sample)


def _is_pattern_covered_by_allowed(pattern: str, allowed_paths: list[str]) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if _is_escape_path(normalized_pattern):
        return False
    root = normalized_pattern.split("*", 1)[0]
    root = root.rstrip("/")
    if not root:
        return False

    for allowed in allowed_paths:
        allowed_norm = _normalize_path(allowed).rstrip("/")
        if not allowed_norm:
            continue
        if _is_escape_path(allowed_norm):
            continue
        if allowed_norm == ".":
            return True
        if root == allowed_norm or root.startswith(allowed_norm + "/"):
            return True
        if fnmatch.fnmatch(root, allowed_norm):
            return True
    return False


def _is_file_covered_by_pattern(path: str, patterns: list[str]) -> bool:
    normalized_path = _normalize_path(path)
    if _is_escape_path(normalized_path):
        return False
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        normalized_pattern = _normalize_path(pattern)
        if _is_escape_path(normalized_pattern):
            continue
        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True
    return False


def _is_file_covered_by_allowed(path: str, allowed_paths: list[str]) -> bool:
    normalized_path = _normalize_path(path)
    if _is_escape_path(normalized_path):
        return False
    for allowed in allowed_paths:
        allowed_norm = _normalize_path(allowed).rstrip("/")
        if not allowed_norm:
            continue
        if _is_escape_path(allowed_norm):
            continue
        if allowed_norm == ".":
            return True
        if normalized_path == allowed_norm or normalized_path.startswith(allowed_norm + "/"):
            return True
        if fnmatch.fnmatch(normalized_path, allowed_norm):
            return True
    return False


def _validate_required_spec_refs_grounding(repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []
    refs = payload.get("required_spec_refs", [])
    if not isinstance(refs, list) or not refs:
        return errors

    git_root = _find_git_root(repo_root)
    if not git_root:
        return [f"{path}: git root not found for required_spec_refs grounding"]

    commit_cache: dict[str, bool] = {}
    lines_cache: dict[tuple[str, str], Optional[list[str]]] = {}
    for idx, ref in enumerate(refs, start=1):
        if not isinstance(ref, dict):
            continue

        ref_type = ref.get("type")
        ref_id = ref.get("id")
        ref_path = ref.get("path")
        line_range = ref.get("line_range")
        commit_hash = ref.get("commit_hash")

        if not all(isinstance(v, str) and v for v in (ref_type, ref_id, ref_path, line_range, commit_hash)):
            continue

        if not _git_commit_exists(git_root, commit_hash, commit_cache):
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) commit_hash '{commit_hash}' not found in git"
            )
            continue

        rel_path = _normalize_path(ref_path)
        if os.path.isabs(ref_path):
            rel_path = _normalize_path(os.path.relpath(ref_path, git_root))
        if _is_escape_path(rel_path):
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) path '{ref_path}' is outside git root"
            )
            continue

        expected_type = _SPEC_REF_TYPE_BY_BASENAME.get(os.path.basename(rel_path))
        if expected_type and ref_type != expected_type:
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) path '{rel_path}' implies type '{expected_type}'"
            )

        parsed = _parse_line_range(line_range)
        if not parsed:
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) invalid line_range '{line_range}'"
            )
            continue
        start, end = parsed
        if start < 1 or end < start:
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) invalid line_range bounds '{line_range}'"
            )
            continue

        lines = _git_file_lines(git_root, commit_hash, rel_path, lines_cache)
        if lines is None:
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) path '{rel_path}' not present at commit '{commit_hash}'"
            )
            continue
        if end > len(lines):
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) line_range '{line_range}' exceeds file length at commit"
            )
            continue

        if not _line_range_contains_reference_id(lines, start, end, ref_id):
            errors.append(
                f"{path}: required_spec_refs[{idx}] ({ref_type}:{ref_id}) line_range '{line_range}' does not contain referenced id at commit"
            )

    return errors


def _validate_context_pack_deep(repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []

    phase = payload.get("phase")
    required_spec_refs = payload.get("required_spec_refs", [])
    allowed_write_paths = payload.get("allowed_write_paths", [])
    target_file_patterns = payload.get("target_file_patterns", [])
    if phase in {"16a", "16b", "16c"}:
        if not isinstance(required_spec_refs, list) or len(required_spec_refs) == 0:
            errors.append(
                f"{path}: required_spec_refs must include at least one grounded spec reference for phase '{phase}'"
            )
    if phase in {"16a", "16b", "16c"}:
        for pattern in target_file_patterns:
            if isinstance(pattern, str) and pattern and not _is_pattern_covered_by_allowed(pattern, allowed_write_paths):
                errors.append(
                    f"{path}: target_file_patterns entry '{pattern}' is outside allowed_write_paths"
                )

    manifest_ref = payload.get("seed_manifest_path")
    if isinstance(manifest_ref, str) and manifest_ref:
        manifest_path = _resolve_ref(path, manifest_ref, repo_root)
        if not os.path.exists(manifest_path):
            errors.append(f"{path}: seed_manifest_path not found: {manifest_ref}")
            return errors
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            errors.append(f"{path}: unable to read seed manifest for deep validation ({e})")
            return errors

        manifest_seed_paths = set()
        seed_path_by_id: dict[str, str] = {}
        for seed in manifest.get("seeds", []):
            if isinstance(seed, dict):
                sid = seed.get("seed_id")
                spath = seed.get("path")
                if isinstance(spath, str):
                    manifest_seed_paths.add(spath)
                if isinstance(sid, str) and isinstance(spath, str):
                    seed_path_by_id[sid] = spath

        provided_seed_files = payload.get("seed_files_ordered", [])
        for seed_file in provided_seed_files:
            if isinstance(seed_file, str) and seed_file not in manifest_seed_paths:
                errors.append(
                    f"{path}: seed_files_ordered entry '{seed_file}' is not present in seed_manifest.seeds"
                )

        global_order = manifest.get("global_seed_order", [])
        expected_global_paths = [seed_path_by_id[sid] for sid in global_order if sid in seed_path_by_id]
        missing_global_paths = [p for p in expected_global_paths if p not in provided_seed_files]
        if missing_global_paths:
            errors.append(
                f"{path}: seed_files_ordered missing global seed paths: {', '.join(missing_global_paths)}"
            )
        else:
            idxs = [provided_seed_files.index(p) for p in expected_global_paths]
            if idxs != sorted(idxs):
                errors.append(
                    f"{path}: seed_files_ordered violates global_seed_order sequence from seed_manifest"
                )

        # Fail-fast phase contract: context pack must include all seeds required
        # by step_requirements for the active phase.
        if phase in {"16a", "16b", "16c"}:
            step_requirements = manifest.get("step_requirements", {})
            required_seed_ids = step_requirements.get(phase)
            if not isinstance(required_seed_ids, list):
                errors.append(
                    f"{path}: seed_manifest.step_requirements['{phase}'] is missing or invalid"
                )
            else:
                unknown_required_ids = [
                    sid for sid in required_seed_ids if isinstance(sid, str) and sid not in seed_path_by_id
                ]
                if unknown_required_ids:
                    errors.append(
                        f"{path}: seed_manifest.step_requirements['{phase}'] references unknown seed ids: "
                        + ", ".join(unknown_required_ids)
                    )
                expected_phase_paths = [
                    seed_path_by_id[sid]
                    for sid in required_seed_ids
                    if isinstance(sid, str) and sid in seed_path_by_id
                ]
                missing_phase_paths = [p for p in expected_phase_paths if p not in provided_seed_files]
                if missing_phase_paths:
                    errors.append(
                        f"{path}: seed_files_ordered missing step_requirements['{phase}'] seed paths: "
                        + ", ".join(missing_phase_paths)
                    )

    seen_refs: set[tuple[str, str]] = set()
    for ref in required_spec_refs if isinstance(required_spec_refs, list) else []:
        if not isinstance(ref, dict):
            continue
        key = (str(ref.get("type", "")), str(ref.get("id", "")))
        if key in seen_refs:
            errors.append(f"{path}: duplicate required_spec_refs entry for type/id {key[0]}:{key[1]}")
        seen_refs.add(key)

    bootstrap_trace = payload.get("bootstrap_ref_trace")
    if phase == "16a" and isinstance(bootstrap_trace, list) and bootstrap_trace:
        grounded_keys = {
            (str(ref.get("type", "")), str(ref.get("id", "")))
            for ref in required_spec_refs
            if isinstance(ref, dict)
        }
        for idx, entry in enumerate(bootstrap_trace):
            if not isinstance(entry, dict):
                continue
            key = (str(entry.get("spec_type", "")), str(entry.get("id", "")))
            if key not in grounded_keys:
                errors.append(
                    f"{path}: bootstrap_ref_trace[{idx}] ({key[0]}:{key[1]}) must map to required_spec_refs"
                )
            source = entry.get("selected_from")
            mode = entry.get("selection_mode")
            if isinstance(source, str) and source.startswith("roadmap.") and mode == "authority_fallback":
                errors.append(
                    f"{path}: bootstrap_ref_trace[{idx}] cannot use authority_fallback mode with roadmap source '{source}'"
                )

    errors.extend(_validate_required_spec_refs_grounding(repo_root, path, payload))

    return errors


def _validate_task_input_deep(repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []

    context_pack_ref = payload.get("context_pack_ref")
    if not isinstance(context_pack_ref, str) or not context_pack_ref:
        return errors

    context_pack_path = _resolve_ref(path, context_pack_ref, repo_root)
    if not os.path.exists(context_pack_path):
        return [f"{path}: context_pack_ref not found: {context_pack_ref}"]

    try:
        with open(context_pack_path, "r", encoding="utf-8") as f:
            context_pack = json.load(f)
    except Exception as e:
        return [f"{path}: failed reading context_pack_ref '{context_pack_ref}' ({e})"]

    context_pack_schema_errors = _validate_payload(
        repo_root,
        context_pack_path,
        context_pack,
        RUNTIME_SCHEMA_BY_TYPE["context_pack"],
    )
    if context_pack_schema_errors:
        errors.extend(
            [f"{path}: referenced context_pack_ref failed schema validation: {msg}" for msg in context_pack_schema_errors]
        )
        return errors

    task_phase = payload.get("phase")
    context_phase = context_pack.get("phase")
    if isinstance(task_phase, str) and isinstance(context_phase, str) and task_phase != context_phase:
        errors.append(
            f"{path}: task_input phase '{task_phase}' does not match context_pack phase '{context_phase}'"
        )

    task_step_id = payload.get("step_id")
    context_step_id = context_pack.get("step_id")
    if isinstance(task_step_id, str) and isinstance(context_step_id, str) and task_step_id != context_step_id:
        errors.append(
            f"{path}: task_input step_id '{task_step_id}' does not match context_pack step_id '{context_step_id}'"
        )

    target_files = payload.get("target_files", [])
    target_file_patterns = context_pack.get("target_file_patterns", [])
    allowed_write_paths = context_pack.get("allowed_write_paths", [])

    if isinstance(target_files, list):
        for target in target_files:
            if not isinstance(target, str) or not target:
                continue
            if isinstance(target_file_patterns, list) and target_file_patterns:
                if not _is_file_covered_by_pattern(target, target_file_patterns):
                    errors.append(
                        f"{path}: target_files entry '{target}' is not covered by context_pack.target_file_patterns"
                    )
            if isinstance(allowed_write_paths, list) and allowed_write_paths:
                if not _is_file_covered_by_allowed(target, allowed_write_paths):
                    errors.append(
                        f"{path}: target_files entry '{target}' is outside context_pack.allowed_write_paths"
                    )

    task_spec_refs = payload.get("spec_refs", [])
    context_required_refs = context_pack.get("required_spec_refs", [])
    context_ref_keys = set()
    if isinstance(context_required_refs, list):
        for ref in context_required_refs:
            if isinstance(ref, dict):
                ref_type = ref.get("type")
                ref_id = ref.get("id")
                if isinstance(ref_type, str) and isinstance(ref_id, str):
                    context_ref_keys.add((ref_type, ref_id))

    if task_phase in {"16a", "16b", "16c"} and not context_ref_keys:
        errors.append(
            f"{path}: context_pack.required_spec_refs must be non-empty for phase '{task_phase}'"
        )
    if isinstance(task_spec_refs, list):
        for idx, ref in enumerate(task_spec_refs, start=1):
            if not isinstance(ref, dict):
                continue
            ref_type = ref.get("type")
            ref_id = ref.get("id")
            if isinstance(ref_type, str) and isinstance(ref_id, str):
                if (ref_type, ref_id) not in context_ref_keys:
                    errors.append(
                        f"{path}: spec_refs[{idx}] ({ref_type}:{ref_id}) is missing from context_pack.required_spec_refs"
                    )

    return errors


def _validate_task_result_deep(repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []
    phase = payload.get("phase")
    status = payload.get("status")
    artifacts = payload.get("artifacts", [])

    if status != "success" or phase not in {"16a", "16b", "16c"}:
        return errors
    if not isinstance(artifacts, list) or not artifacts:
        return errors

    step16_artifacts: list[tuple[str, dict, str]] = []
    for ref in artifacts:
        if not isinstance(ref, str) or not ref or not ref.endswith(".json"):
            continue
        resolved = _resolve_ref(path, ref, repo_root)
        if not os.path.exists(resolved):
            continue
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                payload_json = json.load(f)
        except Exception:
            continue
        if payload_json.get("$schema") == "https://specdev.local/schema/16_impl_context.schema.json":
            step16_artifacts.append((ref, payload_json, resolved))

    if not step16_artifacts:
        errors.append(
            f"{path}: success task_result for phase '{phase}' must include at least one 16_impl_context artifact reference"
        )
        return errors

    for artifact_ref, artifact, resolved_path in step16_artifacts:
        # A success task_result must never point at a malformed Step 16 artifact.
        # Validate referenced artifacts fully (schema + deep checks) before phase gates.
        from .validate import validate_file

        step16_validation_errors = validate_file(repo_root, resolved_path)
        if step16_validation_errors:
            errors.append(
                f"{path}: phase {phase} success artifact '{artifact_ref}' failed step16 validation: "
                + "; ".join(step16_validation_errors)
            )
            continue

        if phase == "16a":
            plan = artifact.get("plan")
            checklist = (
                plan.get("spec_alignment", {}).get("checklist", [])
                if isinstance(plan, dict)
                else []
            )
            if not isinstance(plan, dict) or not isinstance(checklist, list) or not checklist:
                errors.append(
                    f"{path}: phase 16a success artifact '{artifact_ref}' must include a non-empty plan.spec_alignment.checklist"
                )

        if phase == "16b":
            execution = artifact.get("execution")
            execution_results = execution.get("execution_results", []) if isinstance(execution, dict) else []
            if not isinstance(execution, dict):
                errors.append(
                    f"{path}: phase 16b success artifact '{artifact_ref}' must include execution section"
                )
            elif not isinstance(execution_results, list) or not execution_results:
                errors.append(
                    f"{path}: phase 16b success artifact '{artifact_ref}' must include non-empty execution.execution_results"
                )

        if phase == "16c":
            review = artifact.get("review")
            verdict = review.get("verdict") if isinstance(review, dict) else None
            if not isinstance(review, dict):
                errors.append(
                    f"{path}: phase 16c success artifact '{artifact_ref}' must include review section"
                )
            elif verdict not in {"verified", "deferred", "rejected"}:
                errors.append(
                    f"{path}: phase 16c success artifact '{artifact_ref}' must include review.verdict"
                )
            elif verdict == "verified":
                findings = review.get("findings", [])
                if not isinstance(findings, list):
                    errors.append(
                        f"{path}: phase 16c success artifact '{artifact_ref}' has verdict=verified but review.findings is not a list"
                    )
                else:
                    major_or_blocking = [
                        f
                        for f in findings
                        if isinstance(f, dict) and f.get("severity") in {"blocking", "major"}
                    ]
                    if major_or_blocking:
                        errors.append(
                            f"{path}: phase 16c success artifact '{artifact_ref}' has verdict=verified but includes blocking/major findings"
                        )
                execution = artifact.get("execution")
                execution_results = execution.get("execution_results", []) if isinstance(execution, dict) else []
                if not isinstance(execution_results, list) or not execution_results:
                    errors.append(
                        f"{path}: phase 16c success artifact '{artifact_ref}' has verdict=verified but execution.execution_results is missing or empty"
                    )
                else:
                    non_passed = [
                        r
                        for r in execution_results
                        if isinstance(r, dict) and r.get("status") in {"failed", "blocked", "partial"}
                    ]
                    if non_passed:
                        errors.append(
                            f"{path}: phase 16c success artifact '{artifact_ref}' has verdict=verified but execution results include failed/blocked/partial status"
                        )

    return errors


def _extract_child_id_from_spawn_ref(spawn_ref: object) -> Optional[str]:
    if not isinstance(spawn_ref, str) or not spawn_ref:
        return None
    m = re.search(r"/spawns/([^/]+)/task_input\.json$", spawn_ref.replace("\\", "/"))
    if not m:
        return None
    return m.group(1)


def _extract_child_id_from_result_ref(result_ref: object) -> Optional[str]:
    if not isinstance(result_ref, str) or not result_ref:
        return None
    m = re.search(r"/spawns/([^/]+)/task_result\.json$", result_ref.replace("\\", "/"))
    if not m:
        return None
    return m.group(1)


def _validate_session_state_deep(repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []

    status = payload.get("status")
    pending_child_id = payload.get("pending_child_id")
    pending_spawn_ref = payload.get("pending_spawn_ref")
    pending_questions = payload.get("pending_questions")
    retry_counters = payload.get("retry_counters")

    if status == "waiting_child":
        if not isinstance(pending_child_id, str) or not pending_child_id:
            errors.append(f"{path}: status waiting_child requires non-null pending_child_id")
        if not isinstance(pending_spawn_ref, str) or not pending_spawn_ref:
            errors.append(f"{path}: status waiting_child requires non-null pending_spawn_ref")
        if pending_questions is not None and pending_questions != []:
            errors.append(f"{path}: status waiting_child requires pending_questions to be null/empty")
    elif status == "awaiting_input":
        if not isinstance(pending_child_id, str) or not pending_child_id:
            errors.append(f"{path}: status awaiting_input requires non-null pending_child_id")
        if not isinstance(pending_spawn_ref, str) or not pending_spawn_ref:
            errors.append(f"{path}: status awaiting_input requires non-null pending_spawn_ref")
        if not (
            isinstance(pending_questions, list)
            and any(isinstance(q, str) and q.strip() for q in pending_questions)
        ):
            errors.append(f"{path}: status awaiting_input requires non-empty pending_questions")
    elif status in {"idle", "done", "blocked"}:
        if pending_child_id is not None:
            errors.append(f"{path}: status {status} requires pending_child_id=null")
        if pending_spawn_ref is not None:
            errors.append(f"{path}: status {status} requires pending_spawn_ref=null")
        if pending_questions is not None and pending_questions != []:
            errors.append(f"{path}: status {status} requires pending_questions to be null/empty")

    if isinstance(pending_spawn_ref, str) and pending_spawn_ref:
        if _is_escape_path(pending_spawn_ref):
            errors.append(f"{path}: pending_spawn_ref must stay within repo root")
        child_from_ref = _extract_child_id_from_spawn_ref(pending_spawn_ref)
        if child_from_ref is None:
            errors.append(
                f"{path}: pending_spawn_ref must use canonical '/spawns/<child_id>/task_input.json' path"
            )
        elif isinstance(pending_child_id, str) and pending_child_id and child_from_ref != pending_child_id:
            errors.append(
                f"{path}: pending_spawn_ref child_id '{child_from_ref}' does not match pending_child_id '{pending_child_id}'"
            )

    for ref_name in ("session_log_ref", "spawn_log_ref", "scratchpad_ref"):
        ref = payload.get(ref_name)
        if isinstance(ref, str) and ref and _is_escape_path(ref):
            errors.append(f"{path}: {ref_name} '{ref}' escapes repo root")

    if not isinstance(retry_counters, dict):
        errors.append(f"{path}: retry_counters must be an object")
    else:
        for key in ("planner", "builder", "verifier", "milestone"):
            value = retry_counters.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{path}: retry_counters.{key} must be integer >= 0")

    return errors


def _validate_spawn_log_deep(_repo_root: str, path: str, payload: dict) -> list[str]:
    errors: list[str] = []
    entries = payload.get("entries", [])

    if not isinstance(entries, list):
        return errors

    attempt_key_last: dict[tuple[str, str, str, tuple[str, ...]], int] = {}
    seen_spawn_ids: set[str] = set()
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        spawn_id = entry.get("spawn_id")
        child_id = entry.get("child_id")
        phase = entry.get("phase")
        purpose = entry.get("purpose")
        attempt = entry.get("attempt")
        checklist_scope = entry.get("checklist_scope")
        status = entry.get("status")
        task_input_ref = entry.get("task_input_ref")
        task_result_ref = entry.get("task_result_ref")

        if isinstance(spawn_id, str):
            if spawn_id in seen_spawn_ids:
                errors.append(f"{path}: entries[{idx}] duplicate spawn_id '{spawn_id}'")
            seen_spawn_ids.add(spawn_id)

        if isinstance(task_input_ref, str):
            child_from_input = _extract_child_id_from_spawn_ref(task_input_ref)
            if child_from_input is None:
                errors.append(
                    f"{path}: entries[{idx}] task_input_ref must use canonical '/spawns/<child_id>/task_input.json' path"
                )
            elif isinstance(child_id, str) and child_id and child_from_input != child_id:
                errors.append(
                    f"{path}: entries[{idx}] task_input_ref child '{child_from_input}' does not match child_id '{child_id}'"
                )
        if isinstance(task_result_ref, str):
            child_from_result = _extract_child_id_from_result_ref(task_result_ref)
            if child_from_result is None:
                errors.append(
                    f"{path}: entries[{idx}] task_result_ref must use canonical '/spawns/<child_id>/task_result.json' path"
                )
            elif isinstance(child_id, str) and child_id and child_from_result != child_id:
                errors.append(
                    f"{path}: entries[{idx}] task_result_ref child '{child_from_result}' does not match child_id '{child_id}'"
                )

        if status == "completed" and not (isinstance(task_result_ref, str) and task_result_ref):
            errors.append(f"{path}: entries[{idx}] completed spawn must include task_result_ref")
        if status == "spawned" and task_result_ref not in {None, ""}:
            errors.append(f"{path}: entries[{idx}] spawned status must not include task_result_ref")

        scope_tuple: tuple[str, ...] = ()
        if isinstance(checklist_scope, list):
            scope_tuple = tuple(sorted([x for x in checklist_scope if isinstance(x, str) and x]))
        if all(isinstance(v, str) and v for v in (child_id, phase, purpose)) and isinstance(attempt, int):
            key = (child_id, phase, purpose, scope_tuple)
            last_attempt = attempt_key_last.get(key, 0)
            if attempt > 0 and attempt < last_attempt:
                errors.append(
                    f"{path}: entries[{idx}] attempt regressed for child '{child_id}' phase '{phase}' "
                    f"(found {attempt} after {last_attempt})"
                )
            attempt_key_last[key] = max(last_attempt, attempt)

    return errors


def _compute_event_sha256(event: dict) -> str:
    hash_payload = dict(event)
    hash_payload["event_sha256"] = None
    canonical = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_unit_interval(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)


def _canonical_json_sha256(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _runtime_schema_sha256(
    schema_registry: SchemaRegistry,
    schema_uri: str,
    cache: dict[str, Optional[str]],
) -> Optional[str]:
    if schema_uri in cache:
        return cache[schema_uri]
    try:
        payload = schema_registry.load(schema_uri)
    except Exception:
        cache[schema_uri] = None
        return None
    sha = _canonical_json_sha256(payload)
    cache[schema_uri] = sha
    return sha


def _as_non_negative_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _capture_policy_completeness_warnings(policy: object) -> list[str]:
    warnings: list[str] = []
    if not isinstance(policy, dict):
        return ["capture policy payload was not an object; using builtin defaults"]

    profile = policy.get("operating_profile")
    if not isinstance(profile, dict):
        warnings.append("capture policy operating_profile missing; default profile applied")
    else:
        for key in ("profile", "tier", "budget_tier"):
            value = profile.get(key)
            if not isinstance(value, str) or not value:
                warnings.append(f"capture policy operating_profile.{key} missing; default applied")

    retention = policy.get("retention")
    if not isinstance(retention, dict):
        warnings.append("capture policy retention missing; default retention applied")
    else:
        for key in ("session_log_days", "capture_artifact_days", "eval_export_days"):
            value = retention.get(key)
            if not isinstance(value, int) or value < 1:
                warnings.append(f"capture policy retention.{key} missing or invalid; default applied")

    budgets = policy.get("budgets")
    budget_requirements = {
        "context_window_token_target": 1024,
        "full_capture_token_budget_per_run": 0,
        "max_full_prompt_tokens_per_event": 0,
        "max_full_completion_tokens_per_event": 0,
    }
    for key, minimum in budget_requirements.items():
        chosen = budgets.get(key) if isinstance(budgets, dict) else None
        if not (isinstance(chosen, int) and chosen >= minimum):
            chosen = policy.get(key)
        if not (isinstance(chosen, int) and chosen >= minimum):
            warnings.append(f"capture policy budget '{key}' missing or invalid; default applied")
    return warnings


def _load_capture_policy(
    repo_root: str,
    session_log_path: str,
    policy_ref: str,
    cache: dict[str, tuple[Optional[dict], list[str]]],
) -> tuple[Optional[dict], list[str]]:
    if policy_ref in cache:
        return cache[policy_ref]

    policy_path = _resolve_ref(session_log_path, policy_ref, repo_root)
    if not os.path.exists(policy_path):
        result = (None, [f"capture_policy_ref not found: {policy_ref}"])
        cache[policy_ref] = result
        return result

    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        result = (None, [f"unable to read capture policy '{policy_ref}' ({e})"])
        cache[policy_ref] = result
        return result

    schema_errors = _validate_payload(
        repo_root,
        policy_path,
        payload,
        RUNTIME_SCHEMA_BY_TYPE["log_capture_policy"],
    )
    if schema_errors:
        result = (None, [f"invalid capture policy '{policy_ref}'"] + schema_errors)
        cache[policy_ref] = result
        return result

    result = (payload, [])
    cache[policy_ref] = result
    return result


def _validate_session_event_log_deep(repo_root: str, path: str, events: list[tuple[int, dict]]) -> list[str]:
    errors: list[str] = []
    expected_next_sequence = 1
    previous_hash: Optional[str] = None
    capture_policy_cache: dict[str, tuple[Optional[dict], list[str]]] = {}
    sampled_full_counts: dict[str, int] = {}
    full_capture_tokens: dict[str, int] = {}
    seen_tool_calls: dict[str, int] = {}
    seen_result_ids: dict[str, int] = {}
    spawn_counts: dict[str, int] = {}
    terminate_counts: dict[str, int] = {}
    spawn_sequences: dict[str, list[int]] = {}
    terminate_sequences: dict[str, list[int]] = {}
    validation_input_pass_sequences: dict[str, list[int]] = {}
    validation_result_pass_sequences: dict[str, list[int]] = {}
    schema_sha_cache: dict[str, Optional[str]] = {}
    schema_registry = SchemaRegistry(repo_root)

    for line_no, event in events:
        sequence = event.get("event_sequence")
        event_type = event.get("event_type")
        prev_hash = event.get("prev_event_sha256")
        event_hash = event.get("event_sha256")

        if sequence != expected_next_sequence:
            errors.append(
                f"{path}:{line_no}: event_sequence must be contiguous; expected {expected_next_sequence}, found {sequence}"
            )

        if expected_next_sequence == 1:
            if prev_hash is not None:
                errors.append(f"{path}:{line_no}: first event must set prev_event_sha256 to null")
        else:
            if prev_hash != previous_hash:
                errors.append(
                    f"{path}:{line_no}: prev_event_sha256 does not match previous event hash"
                )

        expected_hash = _compute_event_sha256(event)
        if event_hash != expected_hash:
            errors.append(
                f"{path}:{line_no}: event_sha256 does not match canonical event payload hash"
            )

        content = event.get("content", {}) if isinstance(event.get("content"), dict) else {}
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        step_id = event.get("step_id")
        role = event.get("role")
        parent_id = event.get("parent_id")
        tool_call_id = event.get("tool_call_id")
        result_id = event.get("result_id")
        capture_level = content.get("capture_level")
        capture_reason = content.get("capture_decision_reason")
        prompt_ref = content.get("prompt_artifact_ref")
        prompt_sha = content.get("prompt_sha256")
        response_ref = content.get("response_artifact_ref")
        response_sha = content.get("response_sha256")
        tool_call = content.get("tool_call", {}) if isinstance(content.get("tool_call"), dict) else {}
        token_usage = metadata.get("token_usage", {}) if isinstance(metadata.get("token_usage"), dict) else {}
        prompt_tokens = _as_non_negative_int(token_usage.get("prompt")) or 0
        completion_tokens = _as_non_negative_int(token_usage.get("completion")) or 0
        total_tokens = _as_non_negative_int(token_usage.get("total")) or 0

        if role in {"Orchestrator", "Planner", "Builder", "Verifier", "Worker"} and not (
            isinstance(step_id, str) and step_id
        ):
            errors.append(
                f"{path}:{line_no}: role '{role}' requires non-null step_id for deterministic milestone lineage"
            )

        if expected_next_sequence > 1 and role != "Orchestrator" and parent_id is None:
            errors.append(
                f"{path}:{line_no}: non-root role '{role}' must include parent_id"
            )

        if event_type == "TOOL_CALL" and isinstance(tool_call_id, str):
            if tool_call_id in seen_tool_calls:
                errors.append(
                    f"{path}:{line_no}: duplicate TOOL_CALL tool_call_id '{tool_call_id}'"
                )
            else:
                seen_tool_calls[tool_call_id] = line_no

        if event_type == "TOOL_RESULT":
            if isinstance(tool_call_id, str):
                if tool_call_id not in seen_tool_calls:
                    errors.append(
                        f"{path}:{line_no}: TOOL_RESULT references unknown tool_call_id '{tool_call_id}'"
                    )
            if isinstance(result_id, str):
                if result_id in seen_result_ids:
                    errors.append(
                        f"{path}:{line_no}: duplicate TOOL_RESULT result_id '{result_id}'"
                    )
                else:
                    seen_result_ids[result_id] = line_no

        if event_type in {"TOOL_CALL", "TOOL_RESULT"}:
            tool_schema_context = (
                metadata.get("tool_schema_context")
                if isinstance(metadata.get("tool_schema_context"), dict)
                else None
            )
            if tool_schema_context is None:
                errors.append(
                    f"{path}:{line_no}: {event_type} must include metadata.tool_schema_context"
                )
            else:
                mode = tool_schema_context.get("mode")
                expanded_tools = tool_schema_context.get("expanded_tool_names")
                if mode == "catalog_plus_on_demand":
                    if event_type == "TOOL_CALL":
                        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else None
                        if isinstance(tool_name, str):
                            if not isinstance(expanded_tools, list) or tool_name not in expanded_tools:
                                errors.append(
                                    f"{path}:{line_no}: TOOL_CALL tool '{tool_name}' must appear in tool_schema_context.expanded_tool_names for mode 'catalog_plus_on_demand'"
                                )
                    elif not isinstance(expanded_tools, list) or len(expanded_tools) == 0:
                        errors.append(
                            f"{path}:{line_no}: TOOL_RESULT with mode 'catalog_plus_on_demand' must include non-empty expanded_tool_names"
                        )

                request_schema_uri = tool_schema_context.get("request_schema_uri")
                request_schema_sha = tool_schema_context.get("request_schema_sha256")
                result_schema_uri = tool_schema_context.get("result_schema_uri")
                result_schema_sha = tool_schema_context.get("result_schema_sha256")
                if isinstance(request_schema_uri, str) and isinstance(request_schema_sha, str):
                    expected_request_sha = _runtime_schema_sha256(
                        schema_registry,
                        request_schema_uri,
                        schema_sha_cache,
                    )
                    if expected_request_sha and request_schema_sha != expected_request_sha:
                        errors.append(
                            f"{path}:{line_no}: tool_schema_context.request_schema_sha256 does not match canonical schema hash"
                        )
                if isinstance(result_schema_uri, str) and isinstance(result_schema_sha, str):
                    expected_result_sha = _runtime_schema_sha256(
                        schema_registry,
                        result_schema_uri,
                        schema_sha_cache,
                    )
                    if expected_result_sha and result_schema_sha != expected_result_sha:
                        errors.append(
                            f"{path}:{line_no}: tool_schema_context.result_schema_sha256 does not match canonical schema hash"
                        )

        spawn_ref = content.get("task_input_artifact_ref")
        if event_type == "SPAWN" and isinstance(spawn_ref, str):
            m = re.search(r"/spawns/([^/]+)/task_input\.json$", spawn_ref.replace("\\", "/"))
            if m:
                child_id = m.group(1)
                spawn_counts[child_id] = spawn_counts.get(child_id, 0) + 1
                spawn_sequences.setdefault(child_id, []).append(sequence)
            else:
                errors.append(
                    f"{path}:{line_no}: SPAWN task_input_artifact_ref must use canonical '/spawns/<child_id>/task_input.json' path"
                )

        terminate_ref = content.get("task_result_artifact_ref")
        if event_type == "TERMINATE" and isinstance(terminate_ref, str):
            m = re.search(r"/spawns/([^/]+)/task_result\.json$", terminate_ref.replace("\\", "/"))
            if m:
                child_id = m.group(1)
                terminate_counts[child_id] = terminate_counts.get(child_id, 0) + 1
                terminate_sequences.setdefault(child_id, []).append(sequence)
                if terminate_counts[child_id] > spawn_counts.get(child_id, 0):
                    errors.append(
                        f"{path}:{line_no}: TERMINATE for child '{child_id}' appears without matching prior SPAWN"
                    )
            else:
                errors.append(
                    f"{path}:{line_no}: TERMINATE task_result_artifact_ref must use canonical '/spawns/<child_id>/task_result.json' path"
                )

        if event_type == "VALIDATION":
            validation = content.get("validation", {}) if isinstance(content.get("validation"), dict) else {}
            schema_status = validation.get("schema")
            deep_status = validation.get("deep_validator")
            if schema_status == "pass" and deep_status == "pass":
                validation_task_input_ref = content.get("task_input_artifact_ref")
                if isinstance(validation_task_input_ref, str):
                    m = re.search(
                        r"/spawns/([^/]+)/task_input\.json$",
                        validation_task_input_ref.replace("\\", "/"),
                    )
                    if m:
                        child_id = m.group(1)
                        validation_input_pass_sequences.setdefault(child_id, []).append(sequence)
                    else:
                        errors.append(
                            f"{path}:{line_no}: VALIDATION task_input_artifact_ref must use canonical '/spawns/<child_id>/task_input.json' path"
                        )

                validation_task_result_ref = content.get("task_result_artifact_ref")
                if isinstance(validation_task_result_ref, str):
                    m = re.search(
                        r"/spawns/([^/]+)/task_result\.json$",
                        validation_task_result_ref.replace("\\", "/"),
                    )
                    if m:
                        child_id = m.group(1)
                        validation_result_pass_sequences.setdefault(child_id, []).append(sequence)
                    else:
                        errors.append(
                            f"{path}:{line_no}: VALIDATION task_result_artifact_ref must use canonical '/spawns/<child_id>/task_result.json' path"
                        )

        if capture_level == "full":
            if not all(isinstance(v, str) and v for v in (prompt_ref, prompt_sha, response_ref, response_sha)):
                errors.append(
                    f"{path}:{line_no}: capture_level 'full' requires non-null prompt/response artifact refs and hashes"
                )
        elif capture_level == "none":
            if any(v is not None for v in (prompt_ref, prompt_sha, response_ref, response_sha)):
                errors.append(
                    f"{path}:{line_no}: capture_level 'none' requires null prompt/response artifact refs and hashes"
                )

        if total_tokens != prompt_tokens + completion_tokens:
            errors.append(
                f"{path}:{line_no}: token_usage.total must equal token_usage.prompt + token_usage.completion"
            )

        secret_hits: list[str] = []
        secret_hits.extend(_detect_sensitive_classes(content.get("summary")))
        tool_result = content.get("tool_result", {}) if isinstance(content.get("tool_result"), dict) else {}
        secret_hits.extend(_detect_sensitive_classes(tool_result.get("stdout_excerpt")))
        secret_hits.extend(_detect_sensitive_classes(tool_result.get("stderr_excerpt")))
        tool_call = content.get("tool_call", {}) if isinstance(content.get("tool_call"), dict) else {}
        if tool_call:
            try:
                args_json = json.dumps(tool_call.get("args", {}), ensure_ascii=False)
            except Exception:
                args_json = ""
            secret_hits.extend(_detect_sensitive_classes(args_json))
        if capture_level == "full":
            secret_hits.extend(_artifact_sensitive_classes(path, prompt_ref, repo_root))
            secret_hits.extend(_artifact_sensitive_classes(path, response_ref, repo_root))
        if secret_hits:
            classes = ", ".join(sorted(set(secret_hits)))
            errors.append(
                f"{path}:{line_no}: sensitive content detected in persisted session artifacts ({classes})"
            )

        redaction_applied = metadata.get("redaction_applied")
        redaction_stats = metadata.get("redaction_stats", {}) if isinstance(metadata.get("redaction_stats"), dict) else {}
        total_replacements = redaction_stats.get("total_replacements")
        by_class = redaction_stats.get("by_class", {}) if isinstance(redaction_stats.get("by_class"), dict) else {}
        classes_detected = redaction_stats.get("classes_detected", [])
        by_class_sum = sum(v for v in by_class.values() if isinstance(v, int))

        if isinstance(total_replacements, int):
            if by_class_sum > total_replacements:
                errors.append(
                    f"{path}:{line_no}: redaction_stats.by_class total exceeds redaction_stats.total_replacements"
                )
            if redaction_applied is False and total_replacements > 0:
                errors.append(
                    f"{path}:{line_no}: redaction_applied is false but redaction_stats.total_replacements is greater than 0"
                )
        if isinstance(classes_detected, list):
            missing_class_keys = [c for c in classes_detected if isinstance(c, str) and c not in by_class]
            if missing_class_keys:
                errors.append(
                    f"{path}:{line_no}: redaction_stats.classes_detected includes classes not present in by_class: {', '.join(missing_class_keys)}"
                )

        policy_ref = metadata.get("capture_policy_ref")
        policy_sha = metadata.get("capture_policy_sha256")
        if isinstance(policy_ref, str) and policy_ref:
            policy, policy_errors = _load_capture_policy(repo_root, path, policy_ref, capture_policy_cache)
            if policy_errors:
                errors.extend([f"{path}:{line_no}: {msg}" for msg in policy_errors])
            elif policy is not None:
                if isinstance(policy_sha, str):
                    expected_policy_sha = _canonical_json_sha256(policy)
                    if policy_sha != expected_policy_sha:
                        errors.append(
                            f"{path}:{line_no}: capture_policy_sha256 does not match canonical policy payload hash"
                        )

                policy_id = policy.get("policy_id", "policy")
                run_id = event.get("run_id", "run")
                policy_run_key = f"{policy_id}|{run_id}"
                event_type = event.get("event_type")
                role = event.get("role")
                default_capture_level = policy.get("default_capture_level", "summary")
                always_full_events = set(policy.get("always_full_on_event_types", []))
                allowlist_roles = policy.get("full_capture_allowlist_roles", [])
                role_allowed_for_full = (not allowlist_roles) or (role in allowlist_roles)
                sampling_salt = policy.get("sampling_salt", "default")

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
                        sample_key = (
                            f"{policy_id}|{sampling_salt}|{event.get('run_id')}|"
                            f"{event.get('event_id')}|{event.get('event_sequence')}"
                        )
                        sampled_for_full = _stable_unit_interval(sample_key) < float(sample_rate)
                    if sampled_for_full:
                        max_full_events = policy.get("max_full_events_per_run", 0)
                        max_full_events = max_full_events if isinstance(max_full_events, int) else 0
                        used = sampled_full_counts.get(policy_run_key, 0)
                        if used < max_full_events:
                            expected_capture_level = "full"
                            expected_reason_prefix = "policy:sampled"
                            sampled_full_counts[policy_run_key] = used + 1
                        else:
                            expected_capture_level = policy.get("oversize_fallback", "summary")
                            expected_reason_prefix = "policy:capped"

                # Apply token guards after the initial decision to support 60k-80k context budgets.
                if expected_capture_level == "full":
                    max_prompt_tokens = _as_non_negative_int(policy.get("max_full_prompt_tokens_per_event"))
                    max_completion_tokens = _as_non_negative_int(policy.get("max_full_completion_tokens_per_event"))
                    explicit_budget = _as_non_negative_int(policy.get("full_capture_token_budget_per_run"))
                    window_target = _as_non_negative_int(policy.get("context_window_token_target"))
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
                        expected_capture_level = policy.get("oversize_fallback", "summary")
                        expected_reason_prefix = "policy:token_guard_prompt"
                    elif isinstance(max_completion_tokens, int) and completion_tokens > max_completion_tokens:
                        expected_capture_level = policy.get("oversize_fallback", "summary")
                        expected_reason_prefix = "policy:token_guard_completion"
                    else:
                        used_tokens = full_capture_tokens.get(policy_run_key, 0)
                        if isinstance(effective_budget, int) and (used_tokens + total_tokens > effective_budget):
                            expected_capture_level = policy.get("oversize_fallback", "summary")
                            expected_reason_prefix = "policy:token_budget"
                        else:
                            full_capture_tokens[policy_run_key] = used_tokens + total_tokens

                if capture_level != expected_capture_level:
                    errors.append(
                        f"{path}:{line_no}: capture_level '{capture_level}' does not match policy-expected level '{expected_capture_level}'"
                    )
                if not isinstance(capture_reason, str) or not capture_reason.startswith(expected_reason_prefix):
                    errors.append(
                        f"{path}:{line_no}: capture_decision_reason must start with '{expected_reason_prefix}'"
                    )
                if (
                    policy.get("require_redaction_before_full") is True
                    and expected_capture_level == "full"
                    and redaction_applied is not True
                ):
                    errors.append(
                        f"{path}:{line_no}: policy requires redaction_applied=true before full capture"
                    )

                fallback_applied = metadata.get("capture_policy_fallback_applied")
                fallback_reasons = metadata.get("capture_policy_fallback_reasons")
                profile_meta = metadata.get("capture_policy_profile")
                expected_fallback_warnings = _capture_policy_completeness_warnings(policy)
                if isinstance(fallback_applied, bool):
                    if fallback_applied and not (
                        isinstance(fallback_reasons, list)
                        and any(isinstance(reason, str) and reason for reason in fallback_reasons)
                    ):
                        errors.append(
                            f"{path}:{line_no}: capture_policy_fallback_applied=true requires non-empty capture_policy_fallback_reasons"
                        )
                    if (not fallback_applied) and isinstance(fallback_reasons, list) and any(
                        isinstance(reason, str) and reason for reason in fallback_reasons
                    ):
                        errors.append(
                            f"{path}:{line_no}: capture_policy_fallback_applied=false must not include capture_policy_fallback_reasons entries"
                        )
                    expected_fallback_applied = bool(expected_fallback_warnings)
                    if fallback_applied != expected_fallback_applied:
                        errors.append(
                            f"{path}:{line_no}: capture_policy_fallback_applied does not match policy completeness expectations"
                        )
                if isinstance(fallback_reasons, list) and expected_fallback_warnings:
                    missing_expected = sorted(
                        set(expected_fallback_warnings) - {r for r in fallback_reasons if isinstance(r, str)}
                    )
                    if missing_expected:
                        errors.append(
                            f"{path}:{line_no}: capture_policy_fallback_reasons missing expected entries: {', '.join(missing_expected[:3])}"
                        )
                if isinstance(profile_meta, dict):
                    for pkey in ("profile", "tier", "budget_tier"):
                        if not isinstance(profile_meta.get(pkey), str) or not profile_meta.get(pkey):
                            errors.append(
                                f"{path}:{line_no}: capture_policy_profile.{pkey} must be a non-empty string when capture_policy_profile is present"
                            )

        expected_next_sequence += 1
        previous_hash = event_hash if isinstance(event_hash, str) else None

    # Every child spawn that is tracked by runtime artifact refs must close.
    for child_id, spawn_total in spawn_counts.items():
        terminate_total = terminate_counts.get(child_id, 0)
        if terminate_total < spawn_total:
            errors.append(
                f"{path}: child '{child_id}' has {spawn_total} SPAWN event(s) but only {terminate_total} TERMINATE event(s)"
            )

    # Enforce transaction boundaries around parent-child handoff:
    # spawn must be followed by validated task_input, and terminate must close
    # only after validated task_result for the same child span.
    for child_id, spans in spawn_sequences.items():
        terminations = terminate_sequences.get(child_id, [])
        input_passes = validation_input_pass_sequences.get(child_id, [])
        result_passes = validation_result_pass_sequences.get(child_id, [])
        for idx, spawn_seq in enumerate(spans):
            terminate_seq = terminations[idx] if idx < len(terminations) else None
            upper_bound = terminate_seq if isinstance(terminate_seq, int) else 10**18
            has_input_validation = any(
                isinstance(vs, int) and vs > spawn_seq and vs <= upper_bound for vs in input_passes
            )
            if not has_input_validation:
                errors.append(
                    f"{path}: child '{child_id}' spawn sequence {spawn_seq} is missing pass VALIDATION for task_input_artifact_ref before termination"
                )

            if isinstance(terminate_seq, int):
                has_result_validation = any(
                    isinstance(vs, int) and vs >= spawn_seq and vs <= terminate_seq for vs in result_passes
                )
                if not has_result_validation:
                    errors.append(
                        f"{path}: child '{child_id}' terminate sequence {terminate_seq} is missing pass VALIDATION for task_result_artifact_ref in same transaction span"
                    )

    return errors


def validate_runtime_file(repo_root: str, path: str, artifact_type: Optional[str] = None) -> list[str]:
    resolved_type = artifact_type or detect_runtime_artifact_type(path)
    if not resolved_type:
        return [f"{path}: unable to infer trinity runtime artifact type"]
    if resolved_type not in RUNTIME_SCHEMA_BY_TYPE:
        return [f"{path}: unsupported trinity runtime artifact type '{resolved_type}'"]

    schema_uri = RUNTIME_SCHEMA_BY_TYPE[resolved_type]

    try:
        if resolved_type == "session_event":
            errors: list[str] = []
            valid_events: list[tuple[int, dict]] = []
            with open(path, "r", encoding="utf-8") as f:
                for idx, raw_line in enumerate(f, start=1):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError as e:
                        errors.append(f"{path}:{idx}: invalid json line ({e})")
                        continue
                    line_errors = _validate_payload(repo_root, path, payload, schema_uri, line_no=idx)
                    if line_errors:
                        errors.extend(line_errors)
                        continue
                    valid_events.append((idx, payload))
            if errors:
                return errors
            errors.extend(_validate_session_event_log_deep(repo_root, path, valid_events))
            return errors

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        errors = _validate_payload(repo_root, path, payload, schema_uri)
        if errors:
            return errors
        if resolved_type == "task_input":
            errors.extend(_validate_task_input_deep(repo_root, path, payload))
        if resolved_type == "task_result":
            errors.extend(_validate_task_result_deep(repo_root, path, payload))
        if resolved_type == "context_pack":
            errors.extend(_validate_context_pack_deep(repo_root, path, payload))
        if resolved_type == "session_state":
            errors.extend(_validate_session_state_deep(repo_root, path, payload))
        if resolved_type == "spawn_log":
            errors.extend(_validate_spawn_log_deep(repo_root, path, payload))
        return errors
    except (OSError, json.JSONDecodeError) as e:
        return [f"{path}: error during runtime validation - {e}"]
