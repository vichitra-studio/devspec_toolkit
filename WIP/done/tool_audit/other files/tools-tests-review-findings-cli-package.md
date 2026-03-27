# Findings: CLI & Packaging Layer

SOURCE: T-tools-tests-review-001
AGENT: cli-package
DATE: 2026-03-11

---

## A1 — Command dispatch

FINDING | A1 | MAJOR | cli.py monolithic dispatch | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:44-754 | cli.py is 757 LOC with a single main() function containing 25 subcommands defined via sub.add_parser() (lines 49-174) and dispatched through a 24-branch if/elif chain (lines 190-754). All subcommand definitions, argument parsing, and handler logic reside in one function in one file. Industry standard for 25+ subcommands is command groups with lazy loading or click.add_command() — one module per group (e.g., validation commands, canonical commands, generation commands). The current structure means every new subcommand adds to the same monolithic function.

FINDING | A1 | MINOR | Inline STEP_NAMES constant | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:666-675 | The prompt-context handler embeds a hardcoded STEP_NAMES dictionary (22 entries) inside the elif branch rather than sourcing it from step_order.json or a shared constant. This duplicates knowledge that exists elsewhere and will drift.

FINDING | A1 | INFO | No command grouping structure | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:46-47 | argparse.ArgumentParser with flat add_subparsers is used. There is no command group hierarchy (e.g., `specdev validate ...`, `specdev canonical ...`, `specdev align ...`). The only grouping is the `align` command which uses a positional `action` argument with choices (line 146) rather than nested subparsers.

---

## A2 — Separation of concerns

FINDING | A2 | MAJOR | Command handlers mix parsing, orchestration, and output formatting | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:190-754 | Multiple command handlers perform more than argument parsing. Examples: (1) `validate` handler (lines 190-212) builds JSON output structures and calls json.dumps inline; (2) `matrix` handler (lines 219-239) performs file I/O (os.makedirs, open/write), reads env vars, and formats error output; (3) `canonical-autofix` handler (lines 303-348) implements error classification logic (startswith("E")), groups changes by file, and formats multi-line output; (4) `changelog` handler (lines 438-491) formats version details with string interpolation; (5) `align` handler (lines 491-645) is 154 lines containing rollback interactive prompting, pre/post migration validation, and emoji-laden output formatting. A thin CLI layer should delegate to a service/orchestration layer and only handle arg parsing and exit codes.

FINDING | A2 | MINOR | env-check handler contains 50 lines of formatting logic | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:689-739 | The env-check handler reads env vars, opens step_order.json, parses JSON, and formats a multi-section diagnostic report all inline. This logic should live in a diagnostic module that the CLI handler simply invokes.

FINDING | A2 | MINOR | prompt-context handler contains display logic | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py:647-681 | The prompt-context handler reads step_order.json, normalizes step IDs, resolves downstream consumers, and formats a markdown table — all inline in the elif branch. No corresponding service function exists.

---

## A3 — Package layout

FINDING | A3 | MODERATE | validation/ is flat with 18 modules at the same level | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validation/ | The validation subpackage contains 18 Python modules (3752 LOC) plus a `validators/` sub-subpackage (22 step-specific validators, 2666 LOC) — totaling ~6418 LOC. All 18 linter/checker modules sit at the same directory level with no grouping by concern (e.g., structural lints vs. cross-artifact checks vs. replay/ordering checks). The validators/ sub-subpackage is well-organized by step. The flat linter layer could benefit from grouping (e.g., structural: fixtures_lint, seed_lint, docs_lint, spec_quality_lint; cross-artifact: matrix, traceability_closure, hallucination_lint; ordering: dependency_order_lint, forward_replay_check, dag_lint).

PASS | A3 | generation/ subpackage (3 modules, 2646 LOC) is appropriately sized and organized with clear module boundaries: prompt_generator.py, prompt_schema_sync.py, schema_differ.py.

PASS | A3 | canonical/ subpackage (4 modules, 1828 LOC) is appropriately sized and organized: autofix.py, integrity.py, lint.py, registry.py.

PASS | A3 | core/ subpackage has clear atomic modules: errors.py, registry.py, trace_types.py, changelog_parser.py.

PASS | A3 | Top-level __init__.py provides lazy-import deprecation shim for backward compatibility with proper DeprecationWarning messages (/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/__init__.py:36-44).

---

## A5 — Entry point & wrapper

PASS | A5 | pyproject.toml defines console_scripts entry point `specdev = "specdev_tools.cli:main"` (/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/pyproject.toml:20-21).

FINDING | A5 | MINOR | run_specdev.sh template hardcodes venv name "dev_env" | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/scripts/templates/run_specdev.sh:5 | The wrapper template sets `VENV_DIR="${ROOT}/dev_env"` but init_project.py allows `--venv-name` to customize the venv name (default: dev_env). The template is not parameterized — it is copied as-is by init_project.py (line 249: shutil.copy2). If a user specifies `--venv-name myenv`, the wrapper will still look for `dev_env/`.

PASS | A5 | run_specdev.sh self-locates via `ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` and handles cross-platform Python binary resolution (bin/python3, bin/python, Scripts/python.exe, Scripts/python) (/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/scripts/templates/run_specdev.sh:4-16).

PASS | A5 | init_project.py correctly wires the wrapper: copies run_specdev.sh and ensure_venv.py to host repo's tools/ directory, sets executable permission (0o755), installs toolkit in editable mode, and sets up pre-commit hooks (/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/scripts/init_project.py:239-262).

FINDING | A5 | INFO | No run_specdev.sh in toolkit's own tools/ directory | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/ | The toolkit's own tools/ directory does not contain a run_specdev.sh. The wrapper only exists as a template at scripts/templates/run_specdev.sh and is deployed to host repos. CLAUDE.md references `./tools/run_specdev.sh` for running commands, which works only in deployed host repos, not when developing the toolkit itself (where `specdev` console_scripts entry or `python -m specdev_tools.cli` must be used instead).

---

## A7 — Dependency management

FINDING | A7 | MODERATE | requirements.txt uses floor pins only — no upper bounds or hash pinning | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/requirements.txt:2-5 | All four dependencies use `>=` floor pins (jsonschema>=4.21.1, pyyaml>=6.0.1, jsonschema-specifications>=2023.12.1, pyjwt>=2.8.0) with no upper bounds and no lock file. This means `pip install -r requirements.txt` on different dates or machines may install different versions, breaking reproducibility. Industry standard is either (a) a lock file (pip-compile, pip freeze) for reproducible installs, or (b) compatible-release pins (`~=`) to bound the major version.

FINDING | A7 | MINOR | Dual setup.py + pyproject.toml with vestigial setup.py | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/setup.py:1-2 | setup.py contains only `from setuptools import setup; setup()` — a shim for older pip versions that cannot read pyproject.toml directly. Since requires-python >= 3.9 (pyproject.toml line 12), all supported Python versions ship with pip versions that support PEP 517 pyproject.toml builds natively. The setup.py shim is vestigial and can be removed.

PASS | A7 | pyproject.toml dependencies exactly mirror requirements.txt — no version skew between the two dependency declarations (/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/pyproject.toml:13-18 vs /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/requirements.txt:2-5).

FINDING | A7 | INFO | Duplicate dependency declarations in pyproject.toml and requirements.txt | /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/pyproject.toml:13-18 | The same four dependencies are listed in both pyproject.toml [project.dependencies] and requirements.txt. While currently in sync, maintaining two sources of truth risks future divergence. Consider generating requirements.txt from pyproject.toml or having requirements.txt reference `-e .` to use pyproject.toml as the single source.

---

## Summary

| Criterion | Status | Findings |
|-----------|--------|----------|
| A1 | FINDING | 2 findings (1 MAJOR, 1 MINOR), 1 INFO |
| A2 | FINDING | 3 findings (1 MAJOR, 2 MINOR) |
| A3 | FINDING | 1 finding (MODERATE), 4 PASS |
| A5 | FINDING | 1 finding (MINOR), 1 INFO, 2 PASS |
| A7 | FINDING | 2 findings (1 MODERATE, 1 MINOR), 1 INFO, 1 PASS |
