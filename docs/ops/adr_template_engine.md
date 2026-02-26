# ADR: Template Engine for Migration Prompts

**Status:** Accepted
**Date:** 2026-02-26
**Deciders:** DevSpec Toolkit Maintainers

## Context

The DevSpec Toolkit migration system generates AI prompts from templates stored in `prompts/migration/`. These templates use variable interpolation to produce context-aware prompts for semantic migrations that cannot be handled automatically.

The current implementation uses a Handlebars-style renderer that supports:
- Simple variable substitution: `{{VAR_NAME}}`
- List iteration: `{{#each ITEMS}}...{{/each}}`

The question was whether to replace this with a Python-native template engine (Jinja2, string.Template, f-strings) or keep the current approach.

## Decision

**Keep the current Handlebars-style renderer.**

## Rationale

1. **Sufficient for current needs.** The migration templates only require variable substitution and list iteration. No conditional logic (`{{#if}}`), filters, or inheritance is needed.

2. **Zero additional dependencies.** The current renderer is implemented in ~50 lines of Python within `prompt_generator.py`. Adopting Jinja2 would add a new dependency to `pyproject.toml` for marginal benefit.

3. **Template portability.** The `{{VAR}}` syntax is widely understood and can be consumed by non-Python tooling if needed. Jinja2's `{{ var | filter }}` syntax is Python-specific.

4. **Predictable output.** Migration prompts must be deterministic and auditable. A minimal renderer with no implicit coercion or filter chains reduces the surface area for unexpected behavior.

5. **Low maintenance burden.** The template set is small (14 templates) and changes infrequently. The cost of maintaining a custom renderer is negligible at this scale.

## Alternatives Considered

### Jinja2
- **Pros:** Full-featured, well-tested, supports conditionals/filters/inheritance
- **Cons:** New dependency, more complex than needed, Python-specific syntax
- **Verdict:** Over-engineered for 14 simple templates

### Python f-strings / str.format()
- **Pros:** Zero dependency, native Python
- **Cons:** No iteration support (`{{#each}}`), security concerns with `.format()` on untrusted input, poor multi-line ergonomics
- **Verdict:** Insufficient — cannot handle list rendering in templates

### string.Template
- **Pros:** Stdlib, safe substitution mode
- **Cons:** No iteration, limited syntax (`$var` only)
- **Verdict:** Insufficient — same limitations as f-strings

## Consequences

- Templates continue to use `{{VAR}}` and `{{#each LIST}}...{{/each}}` syntax
- If conditional logic is ever needed (e.g., `{{#if HAS_DEFAULT}}`), this decision should be revisited
- The renderer remains in `prompt_generator.py` (now at `specdev_tools/generation/prompt_generator.py`)
- New templates must be tested via `tests/test_migration_templates.py` to ensure all placeholders resolve

## References

- Migration system spec: `docs/developers/design/migration_system_spec.md`
- Template directory: `prompts/migration/`
- Renderer implementation: `tools/specdev_tools/generation/prompt_generator.py`
- RFC Finding: F-M9 (Handlebars not Python-native)
