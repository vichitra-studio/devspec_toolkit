from typing import List, Dict, Any, Optional, Set, Tuple
import fnmatch
import hashlib
import json
import os
import re
import subprocess


_CORE_AUTHORITY_FILES = [
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

_SPEC_REF_TYPE_BY_BASENAME = {
    "04_fr_list.json": "fr",
    "05_interface_contracts.json": "api",
    "06_invariants.json": "inv",
    "07_nfrs.json": "nfr",
    "08_fixtures.json": "fixture",
}

_KNOWN_TYPED_SPEC_REFS = {"fr", "api", "nfr", "inv", "fixture"}

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


def _find_seed_manifest(spec_path: Optional[str], toolkit_root: str) -> Optional[str]:
    if spec_path:
        cur = os.path.abspath(os.path.dirname(spec_path))
        while True:
            cand = os.path.join(cur, "spec", "common", "seed_manifest.json")
            if os.path.exists(cand):
                return cand
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    fallback = os.path.join(toolkit_root, "spec", "common", "seed_manifest.json")
    if os.path.exists(fallback):
        return fallback
    return None


def _is_fixture_validation(spec_path: Optional[str]) -> bool:
    if not spec_path:
        return False
    normalized = spec_path.replace("\\", "/")
    return "/tests/fixtures/" in normalized


def _project_root_from_manifest(manifest_path: str) -> str:
    # seed_manifest.json is expected at <project_root>/spec/common/seed_manifest.json
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(manifest_path))))


def _find_git_root(spec_path: Optional[str], toolkit_root: str) -> Optional[str]:
    def walk_up(start: str) -> Optional[str]:
        cur = os.path.abspath(start)
        while True:
            if os.path.isdir(os.path.join(cur, ".git")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return None

    if spec_path:
        root = walk_up(os.path.dirname(spec_path))
        if root:
            return root
    return walk_up(toolkit_root)


def _collect_spec_refs(node: Any, refs: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if {"type", "id", "line_range", "commit_hash"}.issubset(node.keys()):
            if isinstance(node.get("id"), str):
                refs.append(node)
        for value in node.values():
            _collect_spec_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_spec_refs(item, refs)


def _collect_ids(node: Any, source_rel: str, ids: Set[str], id_to_paths: Dict[str, Set[str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "id" and isinstance(value, str) and value:
                ids.add(value)
                id_to_paths.setdefault(value, set()).add(source_rel)
            _collect_ids(value, source_rel, ids, id_to_paths)
    elif isinstance(node, list):
        for item in node:
            _collect_ids(item, source_rel, ids, id_to_paths)


def _build_authority_index(
    manifest_path: str,
) -> Tuple[
    Set[str],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[Tuple[str, str], Set[str]],
]:
    all_ids: Set[str] = set()
    all_id_to_paths: Dict[str, Set[str]] = {}
    typed_ids: Dict[str, Set[str]] = {}
    typed_id_to_paths: Dict[Tuple[str, str], Set[str]] = {}

    project_root = _project_root_from_manifest(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest: Dict[str, Any] = json.load(f)

    authority_paths: Set[str] = set()

    seeds_by_id: Dict[str, str] = {}
    for seed in manifest.get("seeds", []):
        if isinstance(seed, dict):
            sid = seed.get("seed_id")
            path = seed.get("path")
            if isinstance(sid, str) and isinstance(path, str):
                seeds_by_id[sid] = path

    step_requirements = manifest.get("step_requirements", {})
    required_seed_ids: Set[str] = set()
    for step_key in ("16", "16a", "16b", "16c"):
        seed_ids = step_requirements.get(step_key, [])
        if isinstance(seed_ids, list):
            for seed_id in seed_ids:
                if isinstance(seed_id, str):
                    required_seed_ids.add(seed_id)

    for seed_id in required_seed_ids:
        rel_path = seeds_by_id.get(seed_id)
        if isinstance(rel_path, str) and rel_path.endswith(".json"):
            authority_paths.add(os.path.join(project_root, rel_path))

    for rel in _CORE_AUTHORITY_FILES:
        authority_paths.add(os.path.join(project_root, rel))

    for abs_path in sorted(authority_paths):
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue

        rel_path = os.path.relpath(abs_path, project_root).replace("\\", "/")
        local_ids: Set[str] = set()
        local_id_to_paths: Dict[str, Set[str]] = {}
        _collect_ids(payload, rel_path, local_ids, local_id_to_paths)

        for item_id in local_ids:
            all_ids.add(item_id)
            all_id_to_paths.setdefault(item_id, set()).add(rel_path)

        spec_ref_type = _SPEC_REF_TYPE_BY_BASENAME.get(os.path.basename(rel_path))
        if spec_ref_type:
            typed_ids.setdefault(spec_ref_type, set()).update(local_ids)
            for item_id in local_ids:
                typed_id_to_paths.setdefault((spec_ref_type, item_id), set()).add(rel_path)

    return all_ids, all_id_to_paths, typed_ids, typed_id_to_paths


def _git_commit_exists(git_root: str, commit_hash: str, cache: Dict[str, bool]) -> bool:
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
    cache: Dict[Tuple[str, str], Optional[List[str]]],
) -> Optional[List[str]]:
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


def _parse_line_range(value: str) -> Optional[Tuple[int, int]]:
    match = re.match(r"^L(\d+)-L(\d+)$", value or "")
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    return start, end


def _line_range_contains_reference_id(lines: List[str], start: int, end: int, ref_id: str) -> bool:
    excerpt = "\n".join(lines[start - 1 : end])
    id_field_pattern = re.compile(rf'"id"\s*:\s*"{re.escape(ref_id)}"')
    quoted_id_pattern = re.compile(rf'"{re.escape(ref_id)}"')
    return bool(id_field_pattern.search(excerpt) or quoted_id_pattern.search(excerpt))


def _normalize_test_command(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        normalized = entry.strip()
        return normalized or None
    if isinstance(entry, dict):
        command = entry.get("command")
        if isinstance(command, str):
            normalized = command.strip()
            return normalized or None
    return None


def _detect_sensitive_classes(text: Any) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    hits: List[str] = []
    for cls, pattern in _SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            hits.append(cls)
    return hits


def _validate_spec_ref_grounding(
    data: Dict[str, Any],
    toolkit_root: str,
    spec_path: Optional[str],
    manifest_path: Optional[str],
) -> List[str]:
    errors: List[str] = []
    spec_refs: List[Dict[str, Any]] = []
    _collect_spec_refs(data, spec_refs)

    if not spec_refs:
        return errors

    if not manifest_path or not os.path.exists(manifest_path):
        errors.append("spec_ref grounding check failed: seed_manifest.json not found.")
        return errors

    try:
        all_ids, all_id_to_paths, typed_ids, typed_id_to_paths = _build_authority_index(manifest_path)
    except Exception as e:
        return [f"spec_ref grounding check failed: unable to build authority index ({e})."]

    if not all_ids:
        errors.append("spec_ref grounding check failed: no authority IDs were indexed from governed artifacts.")
        return errors

    git_root = _find_git_root(spec_path, toolkit_root)
    if not git_root:
        errors.append("spec_ref grounding check failed: git root not found.")
        return errors

    commit_cache: Dict[str, bool] = {}
    lines_cache: Dict[Tuple[str, str], Optional[List[str]]] = {}

    for idx, ref in enumerate(spec_refs, start=1):
        ref_type = ref.get("type", "unknown")
        ref_id = ref.get("id", "")
        line_range = ref.get("line_range", "")
        commit_hash = ref.get("commit_hash", "")

        candidate_paths: List[str] = []

        if ref_type in _KNOWN_TYPED_SPEC_REFS:
            type_ids = typed_ids.get(ref_type, set())
            if not isinstance(ref_id, str) or ref_id not in type_ids:
                errors.append(
                    f"spec_ref[{idx}] ({ref_type}:{ref_id}) is not grounded: id not found for type '{ref_type}' in authority artifacts."
                )
            candidate_paths = sorted(typed_id_to_paths.get((ref_type, ref_id), set()))
        else:
            if not isinstance(ref_id, str) or ref_id not in all_ids:
                errors.append(
                    f"spec_ref[{idx}] ({ref_type}:{ref_id}) is not grounded: id not found in authority artifacts."
                )
            candidate_paths = sorted(all_id_to_paths.get(ref_id, set()))

        if not isinstance(commit_hash, str) or not _git_commit_exists(git_root, commit_hash, commit_cache):
            errors.append(
                f"spec_ref[{idx}] ({ref_type}:{ref_id}) is not grounded: commit_hash '{commit_hash}' not found in git."
            )
            continue

        parsed = _parse_line_range(line_range if isinstance(line_range, str) else "")
        if not parsed:
            errors.append(
                f"spec_ref[{idx}] ({ref_type}:{ref_id}) has invalid line_range '{line_range}'. Expected format Lx-Ly."
            )
            continue

        start, end = parsed
        if start < 1 or end < start:
            errors.append(
                f"spec_ref[{idx}] ({ref_type}:{ref_id}) has invalid line_range bounds '{line_range}'."
            )
            continue

        if not candidate_paths:
            continue

        plausible = False
        for rel_path in candidate_paths:
            lines = _git_file_lines(git_root, commit_hash, rel_path, lines_cache)
            if not lines:
                continue
            if end > len(lines):
                continue
            if _line_range_contains_reference_id(lines, start, end, ref_id):
                plausible = True
                break

        if not plausible:
            errors.append(
                f"spec_ref[{idx}] ({ref_type}:{ref_id}) line_range '{line_range}' does not map to referenced authority object content at commit {commit_hash}."
            )

    return errors


def validate_step_16(data: Dict[str, Any], toolkit_root: str, spec_path: Optional[str] = None) -> List[str]:
    """
    Deep validation for Step 16 (Implementation Context).

    Args:
        data: The parsed JSON content of the step file.
        toolkit_root: The root directory of the toolkit (for resolving references).

    Returns:
        List of error messages. Empty list if valid.
    """
    errors = []

    plan = data.get("plan", {})
    checklist = plan.get("spec_alignment", {}).get("checklist", [])
    docs_impact = plan.get("docs_impact")
    review_requirements = plan.get("review_requirements", {}) if isinstance(plan.get("review_requirements"), dict) else {}
    review_test_commands_raw = review_requirements.get("test_commands", []) if isinstance(review_requirements.get("test_commands"), list) else []
    review_test_commands = [cmd for cmd in (_normalize_test_command(x) for x in review_test_commands_raw) if cmd]
    review_test_command_set = set(review_test_commands)
    active_checklist_expected_commands: Dict[str, Set[str]] = {}

    for item in checklist:
        impl = item.get("implementation", {})
        status = impl.get("status")
        item_id = item.get("id", "unknown")
        checklist_status = item.get("checklist_status", "active")
        linked_expectation = item.get("linked_test_expectation")
        expected_commands: Set[str] = set()
        if isinstance(linked_expectation, str):
            normalized = linked_expectation.strip()
            if normalized:
                expected_commands.add(normalized)
        elif isinstance(linked_expectation, list):
            for entry in linked_expectation:
                if isinstance(entry, str) and entry.strip():
                    expected_commands.add(entry.strip())

        if checklist_status != "deferred":
            active_checklist_expected_commands[item_id] = expected_commands
            if not expected_commands:
                errors.append(f"Checklist item '{item_id}' is active but has no concrete linked_test_expectation command.")
            else:
                missing_from_review_plan = sorted(expected_commands - review_test_command_set)
                if missing_from_review_plan:
                    errors.append(
                        f"Checklist item '{item_id}' has linked_test_expectation commands not present in plan.review_requirements.test_commands: "
                        + ", ".join(missing_from_review_plan)
                    )

        item_type = item.get("type", "")
        item_layer = item.get("layer", "")

        if item_type not in ["behavior", "constraint", "validation", "metadata", "perf", "logging", "docs", "security"]:
            errors.append(
                f"Checklist item '{item_id}' has invalid type '{item_type}'. Must be one of: behavior, constraint, validation, metadata, perf, logging, docs, security"
            )

        if item_layer not in ["db", "model", "service", "api", "integration", "tests", "docs", "config", "security"]:
            errors.append(
                f"Checklist item '{item_id}' has invalid layer '{item_layer}'. Must be one of: db, model, service, api, integration, tests, docs, config, security"
            )

        if checklist_status != "deferred":
            nfr_refs = item.get("nfr_refs", [])
            if not nfr_refs:
                errors.append(f"Checklist item '{item_id}' is not deferred but has no nfr_refs")

            fixture_ref = item.get("fixture_ref")
            if not fixture_ref:
                errors.append(f"Checklist item '{item_id}' is not deferred but has no fixture_ref")

        if status in ["verified", "in_progress"]:
            actions = impl.get("actions", [])
            if not actions and status == "verified":
                errors.append(f"Checklist item '{item_id}' is 'verified' but has no actions.")

            if status == "verified" and actions:
                has_evidence = any("evidence" in action for action in actions)
                if not has_evidence:
                    errors.append(f"Checklist item '{item_id}' is 'verified' but contains no evidence in any action.")

    summary_patterns = list(plan.get("summary", {}).get("target_file_patterns", []))

    def is_path_covered_by_scope(path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in summary_patterns)

    implementation_touched: Set[str] = set()
    for item in checklist:
        impl = item.get("implementation", {})
        if impl.get("status") in ["in_progress", "verified"]:
            for touched in impl.get("files_touched", []):
                implementation_touched.add(touched)

    for touched in implementation_touched:
        if not is_path_covered_by_scope(touched):
            errors.append(f"File '{touched}' is touched by implementation but not covered by target_file_patterns.")

    execution = data.get("execution", {}) if isinstance(data.get("execution"), dict) else {}
    execution_files_touched: Set[str] = set(execution.get("files_touched", [])) if isinstance(execution.get("files_touched"), list) else set()
    for touched in execution_files_touched:
        if not is_path_covered_by_scope(touched):
            errors.append(f"File '{touched}' is touched by execution but not covered by target_file_patterns.")

    execution_results = execution.get("execution_results", []) if isinstance(execution.get("execution_results"), list) else []
    executed_command_set: Set[str] = set()
    passed_command_set: Set[str] = set()

    for idx, result in enumerate(execution_results, start=1):
        command = result.get("command", "")
        normalized_command = command.strip() if isinstance(command, str) else ""
        if normalized_command:
            executed_command_set.add(normalized_command)

        status = result.get("status")
        evidence = result.get("evidence")
        evidence_ref = result.get("evidence_ref")
        evidence_binding = result.get("evidence_binding", {}) if isinstance(result.get("evidence_binding"), dict) else {}
        if isinstance(evidence, str) and evidence:
            sensitive_hits = _detect_sensitive_classes(evidence)
            if sensitive_hits:
                errors.append(
                    f"execution.execution_results[{idx}] evidence contains sensitive content classes: {', '.join(sorted(set(sensitive_hits)))}."
                )

        if status == "passed":
            if normalized_command:
                passed_command_set.add(normalized_command)

            if isinstance(evidence, str) and evidence:
                expected_sha = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
                actual_sha = evidence_binding.get("sha256")
                if actual_sha != expected_sha:
                    errors.append(
                        f"execution.execution_results[{idx}] has invalid evidence_binding.sha256; expected hash of evidence content."
                    )
                expected_ref = f"sha256:{expected_sha}"
                if evidence_ref != expected_ref:
                    errors.append(
                        f"execution.execution_results[{idx}] has invalid evidence_ref; expected '{expected_ref}'."
                    )
            else:
                errors.append(
                    f"execution.execution_results[{idx}] is passed but evidence is missing or not a string."
                )

            binding_command = evidence_binding.get("command")
            if isinstance(binding_command, str) and normalized_command and binding_command.strip() and binding_command.strip() != normalized_command:
                errors.append(
                    f"execution.execution_results[{idx}] evidence_binding.command does not match command."
                )

    for item in checklist:
        item_id = item.get("id", "unknown")
        actions = (
            item.get("implementation", {}).get("actions", [])
            if isinstance(item.get("implementation"), dict)
            else []
        )
        if not isinstance(actions, list):
            continue
        for action_idx, action in enumerate(actions, start=1):
            evidence_obj = action.get("evidence", {}) if isinstance(action, dict) else {}
            if not isinstance(evidence_obj, dict):
                continue
            content = evidence_obj.get("content")
            sensitive_hits = _detect_sensitive_classes(content)
            if sensitive_hits:
                errors.append(
                    f"Checklist item '{item_id}' action[{action_idx}] evidence.content contains sensitive content classes: "
                    + ", ".join(sorted(set(sensitive_hits)))
                )

    has_execution_context = bool(execution)
    if has_execution_context and review_test_commands and not execution_results:
        errors.append("execution.execution_results must be populated when execution context exists for active review test commands.")
    if execution_results:
        missing_executed = sorted(review_test_command_set - executed_command_set)
        if missing_executed:
            errors.append(
                "execution.execution_results is missing required plan.review_requirements.test_commands: "
                + ", ".join(missing_executed)
            )

    critical_evidence = execution.get("critical_evidence", {}) if isinstance(execution.get("critical_evidence"), dict) else {}
    satisfied_checklist_ids = critical_evidence.get("satisfied_checklist_ids", []) if isinstance(critical_evidence.get("satisfied_checklist_ids"), list) else []
    checklist_ids = {item.get("id") for item in checklist if isinstance(item, dict) and isinstance(item.get("id"), str)}
    unknown_satisfied_ids = sorted({cid for cid in satisfied_checklist_ids if isinstance(cid, str)} - checklist_ids)
    if unknown_satisfied_ids:
        errors.append(
            "execution.critical_evidence.satisfied_checklist_ids contains unknown checklist IDs: "
            + ", ".join(unknown_satisfied_ids)
        )
    passed_test_commands = critical_evidence.get("passed_test_commands", []) if isinstance(critical_evidence.get("passed_test_commands"), list) else []
    normalized_passed_test_commands = {
        cmd.strip() for cmd in passed_test_commands if isinstance(cmd, str) and cmd.strip()
    }
    if normalized_passed_test_commands:
        missing_from_review_plan = sorted(normalized_passed_test_commands - review_test_command_set)
        if missing_from_review_plan:
            errors.append(
                "execution.critical_evidence.passed_test_commands includes commands not present in plan.review_requirements.test_commands: "
                + ", ".join(missing_from_review_plan)
            )

    for checklist_id, expected_commands in active_checklist_expected_commands.items():
        if execution_results and expected_commands:
            if not (expected_commands & normalized_passed_test_commands):
                errors.append(
                    f"Checklist item '{checklist_id}' has no matching passed command in execution.critical_evidence.passed_test_commands."
                )

    manifest_path = _find_seed_manifest(spec_path, toolkit_root)
    doc_patterns: List[str] = []
    doc_patterns_valid = False
    if manifest_path:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            doc_patterns = manifest.get("docs_policy", {}).get("doc_paths", []) or []
            doc_patterns_valid = isinstance(doc_patterns, list) and len(doc_patterns) > 0
            if not doc_patterns_valid:
                errors.append("seed_manifest.json missing docs_policy.doc_paths; cannot validate docs_impact doc paths.")
        except Exception:
            errors.append("Failed to read seed_manifest.json; cannot validate docs_impact doc paths.")
    else:
        errors.append("seed_manifest.json not found; cannot validate docs_impact doc paths.")

    def is_doc_path(path: str) -> bool:
        if not path or not doc_patterns_valid:
            return False
        norm = path.replace("\\", "/").lstrip("./")
        return any(fnmatch.fnmatch(norm, pattern) for pattern in doc_patterns)

    planned_non_doc_targets = [
        path for path in summary_patterns if path and not is_doc_path(path)
    ]

    code_change_targets = []
    for item in checklist:
        impl = item.get("implementation", {})
        for action in impl.get("actions", []):
            if action.get("type") in ["file_create", "file_edit"]:
                target = action.get("target", "")
                if target and not is_doc_path(target):
                    code_change_targets.append(target)

    should_require_docs = bool(planned_non_doc_targets or code_change_targets)

    if should_require_docs:
        if not isinstance(docs_impact, dict):
            errors.append("plan.docs_impact is required when non-doc implementation scope is present.")
        else:
            status = docs_impact.get("status")
            if status != "required":
                errors.append("plan.docs_impact.status must be 'required' when non-doc implementation scope is present.")
            docs_touched = docs_impact.get("docs_touched", [])
            if not docs_touched:
                errors.append("plan.docs_impact.docs_touched must be provided when non-doc implementation scope is present.")
            else:
                out_of_scope_docs = [doc_path for doc_path in docs_touched if not is_path_covered_by_scope(doc_path)]
                if out_of_scope_docs:
                    errors.append(
                        "plan.docs_impact.docs_touched includes paths outside plan.summary.target_file_patterns: "
                        + ", ".join(out_of_scope_docs)
                    )

            if docs_touched and doc_patterns_valid:
                for doc_path in docs_touched:
                    if not is_doc_path(doc_path):
                        errors.append(f"plan.docs_impact.docs_touched contains non-doc path: {doc_path}")
                if execution_files_touched:
                    missing_docs_in_execution = [
                        doc_path for doc_path in docs_touched if doc_path not in execution_files_touched
                    ]
                    if missing_docs_in_execution:
                        errors.append(
                            "Execution touched code/spec scope but did not include documented updates in execution.files_touched: "
                            + ", ".join(missing_docs_in_execution)
                        )

    delivery = plan.get("delivery")
    if isinstance(delivery, dict) and delivery.get("status") == "planned":
        review = data.get("review", {})
        delivery_status = review.get("delivery_status", {}) if isinstance(review, dict) else {}
        deployments = delivery_status.get("deployments", []) if isinstance(delivery_status, dict) else []
        dashboards_verified = delivery_status.get("dashboards_verified", []) if isinstance(delivery_status, dict) else []
        alerts_verified = delivery_status.get("alerts_verified", []) if isinstance(delivery_status, dict) else []

        if not (deployments or dashboards_verified or alerts_verified):
            errors.append(
                "plan.delivery.status is 'planned' but review.delivery_status has no verification entries "
                "(expected deployments or dashboards_verified or alerts_verified)."
            )

        planned_dashboards = delivery.get("dashboards", []) if isinstance(delivery.get("dashboards"), list) else []
        if planned_dashboards:
            planned_ids = {
                item.get("dashboard_id")
                for item in planned_dashboards
                if isinstance(item, dict) and item.get("dashboard_id")
            }
            verified_ids = {
                item.get("dashboard_id")
                for item in dashboards_verified
                if isinstance(item, dict) and item.get("dashboard_id")
            }
            missing = sorted(planned_ids - verified_ids)
            if missing:
                errors.append(
                    "plan.delivery.dashboards includes planned dashboards without matching review.delivery_status."
                    f"dashboards_verified entries: {', '.join(missing)}"
                )

        planned_alerts = delivery.get("alerts", []) if isinstance(delivery.get("alerts"), list) else []
        if planned_alerts:
            planned_ids = {
                item.get("alert_id")
                for item in planned_alerts
                if isinstance(item, dict) and item.get("alert_id")
            }
            verified_ids = {
                item.get("alert_id")
                for item in alerts_verified
                if isinstance(item, dict) and item.get("alert_id")
            }
            missing = sorted(planned_ids - verified_ids)
            if missing:
                errors.append(
                    "plan.delivery.alerts includes planned alerts without matching review.delivery_status."
                    f"alerts_verified entries: {', '.join(missing)}"
                )

    if not _is_fixture_validation(spec_path):
        errors.extend(_validate_spec_ref_grounding(data, toolkit_root, spec_path, manifest_path))

    return errors
