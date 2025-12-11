# AI Spec Driven Development Toolkit (v3 Full)

A schema-first, AI-assisted workflow that turns **spec → implementation** into a deterministic pipeline backed by machine-checkable artifacts.

---

## Why This Exists
- **Clarity for humans, structure for AIs.**
- **Falsifiability:** every statement is testable.
- **Traceability:** FRs ↔ APIs ↔ Fixtures ↔ NFRs remain linked end to end.
- **Early delivery:** CI enforces quality from Step 0.

---

## Start Here
- Onboard with [docs/developers/getting_started.md](docs/developers/getting_started.md).
- Keep [docs/developers/reference.md#core-validation-commands](docs/developers/reference.md#core-validation-commands) handy for the canonical command list, troubleshooting flow, and naming conventions.
- Use the workflow overviews in [docs/developers/workflows/](docs/developers/workflows/) as you progress through Steps 00–17.
- Automation agents begin at [docs/agents/agents.md](docs/agents/agents.md).

---

## Toolkit Layout
```
<toolkit-root>/
├─ README.md                 # this file (high-level orientation)
├─ docs/                     # audience-specific guidance
├─ prompts/                  # deterministic prompt contracts
├─ schema/                   # JSON Schemas per step + shared atoms/collections/errors
├─ template/                 # guide blueprints copied into host repos
├─ tests/                    # fixtures, samples, expectations, helper scripts
├─ tools/                    # CLI package + schema registry
└─ example/                  # fully specced reference implementation
```

Most teams vendor the toolkit as a git submodule at `<product-repo>/devspec_toolkit/` beside their live `spec/` directory.

---

## Working With The Toolkit
- Follow the environment setup in [docs/developers/getting_started.md#1-set-up-your-environment](docs/developers/getting_started.md#1-set-up-your-environment) (virtualenv + `PYTHONPATH`).
- Run validations with `python -m specdev_tools.cli … --repo-root <toolkit-root>`.
- Lean on the bundled scripts in [docs/developers/reference.md#bundled-scripts](docs/developers/reference.md#bundled-scripts) when you want the core validation cadence or to smoke-test the example artifacts.
- Regenerate guides from [template/](template/) before editing human-facing step docs.
- AI runners follow a two-phase flow (Clarify → Emit). See [docs/agents/manifest.json](docs/agents/manifest.json) and [docs/agents/agents.md](docs/agents/agents.md) for the operating protocol. Clarify responses are short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items.

---

## Commands & Troubleshooting
All authoritative CLI examples, guardrails, and troubleshooting checklists live in [docs/developers/reference.md](docs/developers/reference.md).

---

## Additional Resources
- [docs/README.md](docs/README.md) — documentation map.
- [tools/README.md](tools/README.md) — CLI packaging details.
- [example/devspec_kit/](example/devspec_kit/) — end-state example spec set.
- [tests/README.md](tests/README.md) — structure of fixtures, samples, and expectations.
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — sample workflow generated via `gen-ci`.

---

## License
Choose what suits your org (Apache-2.0, MIT, etc.) and place it in [LICENSE](LICENSE).
