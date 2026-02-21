from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path


FENCED_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
EMBEDDED_SCHEMA_RE = re.compile(r"#+\s*Embedded Schema\s*```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def run_prompt_schema_sync(repo_root: str) -> list[str]:
    root = Path(os.path.abspath(repo_root))
    schema_dir = root / "schema"
    prompt_dir = root / "prompts"
    errors: list[str] = []

    schema_files = sorted(glob.glob(str(schema_dir / "*.schema.json")))
    for schema_file in schema_files:
        step = Path(schema_file).name.split("_", 1)[0]
        if step == "seed":
            continue
        prompt_candidates = _prompt_candidates(prompt_dir, step)
        if not prompt_candidates:
            continue
        try:
            schema_required = _load_required(schema_file)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(f"E520 UNRESOLVED_INPUT invalid_schema {schema_file} {exc}")
            continue
        for prompt_path in prompt_candidates:
            prompt_required, line_no = _extract_prompt_required(prompt_path)
            if prompt_required is None:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing JSON contract block")
                continue
            missing = sorted(set(schema_required) - set(prompt_required))
            extra = sorted(set(prompt_required) - set(schema_required))
            if missing:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} missing required {missing}")
            if extra:
                errors.append(f"E310 PROMPT_SCHEMA_DRIFT {prompt_path}:{line_no} extra required {extra}")

    return errors


def _load_required(schema_path: str) -> list[str]:
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    return schema.get("required", []) or []


def _prompt_candidates(prompt_dir: Path, step: str) -> list[str]:
    return sorted(glob.glob(str(prompt_dir / f"prompt_{step}_*.md")))


def _extract_prompt_required(prompt_path: str) -> tuple[list[str] | None, int]:
    with open(prompt_path, "r", encoding="utf-8") as f:
        text = f.read()
    embedded = EMBEDDED_SCHEMA_RE.search(text)
    blocks: list[tuple[str, int]] = []
    if embedded:
        line_no = text[:embedded.start(1)].count("\n") + 1
        blocks.append((embedded.group(1), line_no))
    for m in FENCED_JSON_RE.finditer(text):
        line_no = text[:m.start(1)].count("\n") + 1
        blocks.append((m.group(1), line_no))
    for block, line_no in blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        # Prefer schema-like blocks; ignore output examples.
        if isinstance(parsed.get("properties"), dict):
            req = parsed.get("required")
            if isinstance(req, list):
                return req, line_no
    return None, 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    args = p.parse_args()
    errs = run_prompt_schema_sync(args.repo_root)
    if errs:
        for err in errs:
            print(err)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
