# AI Spec Driven Development Reference Spec

`example/devspec_kit/` contains the fully specced JSON artifacts for every step (00–17) of the AI Spec Driven Development Toolkit. Treat these files as a read-only reference when you need to inspect a completed spec set or compare your artifacts against the toolkit’s expectations.

## What’s Included
- `example/devspec_kit/00_charter.json` … `17_spec_drift.json` — validated machine artifacts for each step
- Example trace matrix and fixtures wired into `tests/`
- Command coverage exercised by `tests/unit`

## How To Use This Reference
```bash
# From your host repo root (adjust ./devspec_toolkit if needed)
python -m venv .venv && . .venv/bin/activate
pip install -r ./devspec_toolkit/tools/requirements.txt
export PYTHONPATH="${PWD}/devspec_toolkit/tools"

# Validate the reference artifacts
python -m specdev_tools.cli validate-all example/devspec_kit --repo-root ./devspec_toolkit

# Compare your trace matrix to the reference
python -m specdev_tools.cli matrix example/devspec_kit --repo-root ./devspec_toolkit --out /tmp/reference_matrix.json
```

Use this directory to answer “what does complete look like?”—not as scaffolding for new projects. When creating your own specs, copy templates from `./devspec_toolkit/template/` (or your toolkit path) into your host repository’s `spec/` folder and generate fresh artifacts via the prompts.
