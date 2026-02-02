# AI Spec Driven Development Toolkit

A schema-first, AI-assisted workflow that turns **spec → implementation** into a deterministic pipeline backed by machine-checkable artifacts.

---

## Why This Exists
- **Clarity for humans, structure for AIs.**
- **Falsifiability:** every statement is testable.
- **Traceability:** FRs ↔ APIs ↔ Fixtures ↔ NFRs remain linked end to end.
- **Early delivery:** CI enforces quality from Step 0.

---

## Start Here
- **Start a new project** using the [init utility](scripts/init_project.py): `python devspec_toolkit/scripts/init_project.py --target <path> --strict`.
- Onboard as a developer with [docs/developers/getting_started.md](docs/developers/getting_started.md).
- Keep [docs/developers/reference.md#core-validation-commands](docs/developers/reference.md#core-validation-commands) handy for the canonical command list, troubleshooting flow, and naming conventions.
- Use the workflow overviews in [docs/developers/workflows/](docs/developers/workflows/) as you progress through Steps 00–16c.
- Automation agents begin at [docs/agents/agents.md](docs/agents/agents.md).

---

## Toolkit Layout
```
<toolkit-root>/
├─ README.md                 # this file (high-level orientation)
├─ docs/                     # audience-specific guidance
├─ prompts/                  # deterministic prompt contracts
├─ schema/                   # JSON Schemas per step + shared atoms/collections/errors
└─ tools/                    # CLI package + schema registry

```

Most teams vendor the toolkit as a git submodule at `<product-repo>/devspec_toolkit/` beside their live `spec/` directory.

---

## Versioning & Migration

This toolkit uses [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes that require spec migration
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes and documentation

Current version is defined in [tools/pyproject.toml](tools/pyproject.toml). See [CHANGELOG.md](CHANGELOG.md) for release history and [changelog/](changelog/) for machine-readable version details.

Projects track their toolkit version in `spec/specdev_version` to enable migration tooling. When versions mismatch, use the `specdev align` CLI to upgrade.

👉 **[Migration Guide](docs/developers/workflows/workflow_align.md)**

---

## Working With The Toolkit
- Follow the environment setup in [docs/developers/getting_started.md#1-set-up-your-environment](docs/developers/getting_started.md#1-set-up-your-environment) (virtualenv + `PYTHONPATH`).
- Run validations with `python -m specdev_tools.cli … --repo-root <toolkit-root>`.


- AI runners follow a two-phase flow (Clarify → Emit). See [docs/agents/manifest.json](docs/agents/manifest.json) and [docs/agents/agents.md](docs/agents/agents.md) for the operating protocol. Clarify responses are short, bulleted questions grouped by topic (no JSON, no code fences), prioritizing gating items.

---

## Commands & Troubleshooting
All authoritative CLI examples, guardrails, and troubleshooting checklists live in [docs/developers/reference.md](docs/developers/reference.md).

---

## Additional Resources
- [docs/README.md](docs/README.md) — documentation map.
- [tools/README.md](tools/README.md) — CLI packaging details.

- [.github/workflows/ci.yml](.github/workflows/ci.yml) — sample workflow generated via `gen-ci`.

---

## License
Choose what suits your org (Apache-2.0, MIT, etc.) and place it in [LICENSE](LICENSE).
