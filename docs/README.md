# Documentation Overview

The AI Spec Driven Development Toolkit separates documentation by audience to keep guidance predictable and easy to maintain.

## Sections
- [developers/](developers/) — human-focused onboarding, reference material, workflow overviews, and diagnostics.
- [agents/](agents/) — operational contract and manifest for AI or automated contributors.
- [prompts/](prompts/) — deterministic prompts (the source of truth for guidelines).

## Start Here
1. Developers: open [developers/index.md](developers/index.md) and follow the links to [getting_started.md](developers/getting_started.md), [reference.md](developers/reference.md), or the workflow guides.
2. Agents: consume [agents/manifest.json](agents/manifest.json) (machine hints) and [agents/agents.md](agents/agents.md) (two‑phase protocol: Clarify → Emit).

## Related Assets
- Toolkit overview: [../README.md](../README.md)
- CLI details: [../tools/README.md](../tools/README.md)
- Examples: [../example/](../example/)
- Tests and fixtures: [../tests/](../tests/)

## Contributing Improvements
1. Align updates with the structure above (developers vs. agents).
2. Open a PR summarizing the gap addressed and include validation steps.
