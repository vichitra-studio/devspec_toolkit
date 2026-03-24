# ADR: Template Engine for Migration Prompts

**Status:** Accepted
**Date:** 2026-02-26
**Deciders:** DevSpec Toolkit Maintainers

## Context

The DevSpec Toolkit migration system generates AI prompts from templates stored in `prompts/migration/`. The design intent is for these templates to use variable interpolation to produce context-aware prompts for semantic migrations that cannot be handled automatically.

The current implementation includes a Handlebars-style renderer (`render_template()` in `prompt_generator.py`) that supports:
- Simple variable substitution: `{{VAR_NAME}}`
- List iteration: `{{#each ITEMS}}...{{/each}}`

The question was whether to replace this with a Python-native template engine (Jinja2, string.Template, f-strings) or keep the current approach.

## Current Implementation Status (as of v0.5.0)

**The renderer is implemented but templates are currently static.** The `render_template()` function fully supports `{{VAR}}` substitution and `{{#each}}` iteration, and the `PromptContext` dataclass populates variables such as `SOURCE_VERSION`, `TARGET_VERSION`, `STEP_ID`, `REQUIRED_FIELDS`, `CONTEXT_SOURCES`, and field-level variables (`FIELD_PATH`, `OLD_TYPE`, `NEW_TYPE`, etc.).

However, the 22 templates in `prompts/migration/` do not currently contain any `{{VAR}}` placeholders — they are static Markdown documents authored for each pipeline step. The renderer runs on every template render call but performs no substitutions because no placeholders are present.

**When interpolation would be used:** If a future template needs to embed context-specific content (e.g., the actual source file contents, a list of required fields extracted from the target schema, or the version numbers being migrated), authors can insert `{{SOURCE_CONTENT}}`, `{{#each REQUIRED_FIELDS}}...{{/each}}`, or any other supported placeholder directly in the template. The renderer will substitute them automatically without any code changes.

## Decision

**Keep the current Handlebars-style renderer.**

## Rationale

1. **Sufficient for current needs.** The migration templates only require variable substitution and list iteration. No conditional logic (`{{#if}}`), filters, or inheritance is needed.

2. **Zero additional dependencies.** The current renderer is implemented in ~50 lines of Python within `prompt_generator.py`. Adopting Jinja2 would add a new dependency to `pyproject.toml` for marginal benefit.

3. **Template portability.** The `{{VAR}}` syntax is widely understood and can be consumed by non-Python tooling if needed. Jinja2's `{{ var | filter }}` syntax is Python-specific.

4. **Predictable output.** Migration prompts must be deterministic and auditable. A minimal renderer with no implicit coercion or filter chains reduces the surface area for unexpected behavior.

5. **Low maintenance burden.** The template set is small (22 templates) and changes infrequently. The cost of maintaining a custom renderer is negligible at this scale.

## Alternatives Considered

### Jinja2
- **Pros:** Full-featured, well-tested, supports conditionals/filters/inheritance
- **Cons:** New dependency, more complex than needed, Python-specific syntax
- **Verdict:** Over-engineered for 22 simple templates

### Python f-strings / str.format()
- **Pros:** Zero dependency, native Python
- **Cons:** No iteration support (`{{#each}}`), security concerns with `.format()` on untrusted input, poor multi-line ergonomics
- **Verdict:** Insufficient — cannot handle list rendering in templates

### string.Template
- **Pros:** Stdlib, safe substitution mode
- **Cons:** No iteration, limited syntax (`$var` only)
- **Verdict:** Insufficient — same limitations as f-strings

## Dual-Renderer Landscape

Two renderers coexist in the toolkit — they serve different subsystems and are not interchangeable:

### `render_template()` — Generation subsystem
- **Location**: `specdev_tools/generation/prompt_generator.py`
- **Role**: Produces AI prompts for the `specdev align prompts` pipeline.
- **Mechanism**: Accepts a `PromptContext` dataclass and performs full `{{VAR}}` substitution and `{{#each LIST}}...{{/each}}` iteration against a loaded template string.
- **Status**: Fully implemented; this ADR's decision applies to this renderer.

### `_render_prompt()` — Migration subsystem
- **Location**: `specdev_tools/migration/runner.py`
- **Role**: Produces prompt files for `AI_ASSISTED` migration steps at plan-execution time (invoked by `execute_single_step()`).
- **Mechanism**: Loads the template file, applies `{{VAR}}` interpolation via the internal `_interpolate_template()` helper, appends a `## Context` block containing the step's context JSON, and returns the concatenated string.
- **Interpolation context**: At minimum contains `project_name` (from `spec/00_charter.json` `title` field), `spec_version` (from `spec/specdev_version`), and `step_id` (the step being migrated). Unknown placeholders are left as-is for backward compatibility with static templates.
- **Status**: Basic `{{VAR}}` interpolation is implemented (AUDIT-049 resolved). The `{{#each}}` iteration blocks supported by the generation-subsystem `render_template()` are intentionally not replicated here — if list rendering is needed in migration templates, authors should call `render_template()` directly.

## Consequences

- Templates continue to use `{{VAR}}` and `{{#each LIST}}...{{/each}}` syntax (via `render_template()`)
- If conditional logic is ever needed (e.g., `{{#if HAS_DEFAULT}}`), this decision should be revisited
- The generation-subsystem renderer remains in `specdev_tools/generation/prompt_generator.py`
- New templates must be tested via `tests/unit/generation/test_prompt_generator.py` to ensure all placeholders resolve

## References

- Migration system spec: `docs/developers/design/migration_system_spec.md`
- Template directory: `prompts/migration/`
- Renderer implementation: `tools/specdev_tools/generation/prompt_generator.py`
- RFC Finding: F-M9 (Handlebars not Python-native)
