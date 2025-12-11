# Implementation Workflow: The JIT Engine

This document describes the iterative **"Plan → Implement → Review"** workflow (often called the JIT Engine) that executes the Roadmap.

## Concept
Use a Just-In-Time (JIT) approach to managing complexity. Instead of specifying technical implementation details for the entire system at the start, we lock the **Interfaces** and **Behaviors** (Steps 00-12) early, but defer the **Internal Implementation Plans** until just before code is written.

## The Sequence
1.  **Phase 1: Core Specs (00-12)**: Define *what* to build.
2.  **Phase 2: Extensions**: Define domain-specific *what* (Step 13).
3.  **Step 14: Roadmap**: Plan *when* to build it.
    *   *Stop here. Do not detail Step 15+ for the whole project yet.*
4.  **Phase 3: Implementation Loop (Per Milestone)**:
    *   **Select**: Pick the next milestone from the Roadmap.
    *   **Expand (Step 15/16/17)**: Create detailed technical plans (e.g., scaffolds, fixtures, red-team attacks) *only for this milestone*.
    *   **Implement**: Write the code.
    *   **Contract**: Validate that the code meets the Core Specs.
    *   **Repeat**: Move to the next milestone.

## The Loop Steps
### A. Select & Expand
For a chosen milestone (e.g., "User Auth"):
- Generate `15_scaffold.json`: Structural code generation.
- Generate `16_fixture_impl.json`: Concrete test data for this feature.
- Generate `17_redteam_loop.json`: Specific attack vectors relevant to this feature.

### B. Implement & Verify
- Write code satisfying the `05_interface_contracts`.
- Run tests using the `16_fixture_impl` data.
- Run red-team checks from `17_redteam_loop`.

### C. Contract & Monitor
- Once passed, the milestone is "Done".
- `18_delivery_monitoring` tracks the velocity.
- `19_spec_drift` watches for code changing without spec updates.

## Why JIT?
- **Reduces Waste**: distinct plans for late-stage features often expire before implementation starts.
- **agility**: You can change the *how* of Milestone 3 based on lessons from Milestone 1 without rewriting the entire roadmap.
- **Trust**: The Core Specs (Contract) remain stable, only the implementation plan evolves.
