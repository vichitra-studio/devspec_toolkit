# AI Spec Driven Development Reference Spec

[`example/devspec_kit/`](devspec_kit/) contains the fully specced JSON artifacts for every step (00–17) of the AI Spec Driven Development Toolkit. Treat these files as a read-only reference when you need to inspect a completed spec set or compare your artifacts against the toolkit’s expectations.

## What’s Included
- `example/devspec_kit/00_charter.json` … `17_spec_drift.json` — validated machine artifacts for each step
- Example trace matrix and fixtures wired into [tests/](../tests/)
- Command coverage exercised by [`tests/unit`](../tests/unit)

## How To Use This Reference
- Follow the environment setup in [`docs/developers/getting_started.md`](../docs/developers/getting_started.md#1-set-up-your-environment).
- Run `python -m specdev_tools.cli validate-all example/devspec_kit --repo-root ./devspec_toolkit` to confirm the reference artifacts stay healthy.
- Generate a comparison matrix with `python -m specdev_tools.cli matrix example/devspec_kit --repo-root ./devspec_toolkit --out example/tools/trace_matrix.json`.

Use this directory to answer “what does complete look like?”—not as scaffolding for new projects. When creating your own specs, copy templates from [./devspec_toolkit/template/](../template/) (or your toolkit path) into your host repository’s `spec/` folder and generate fresh artifacts via the prompts.
