"""Tests for W555 STEP00_SEED_OUT_OF_SCOPE_THIN.

DEVSPEC-107: lint_seeds() must warn when seeds routed to step "00" supply
fewer than 3 substantive out-of-scope items combined.

Coverage:
  1. Fires when combined substantive items < 3 (seed with 1 real item).
  2. Fires when seed has NO out-of-scope section at all (0 items — core case).
  3. Fires when out-of-scope items are bracket-placeholders only → 0 substantive.
  4. Fires when out-of-scope items are scaffold label bullets only
     (- **Expectation**: / - **Content**:) → 0 substantive from labels.
  5. Does NOT fire when combined substantive items >= 3 (aggregate across seeds).
  6. Does NOT fire when a single seed has 3 substantive items.
  7. Does NOT fire when step "00" routes no seeds (key absent).
  8. Does NOT fire when step "00" maps to an empty list (explicit empty gating).
  9. Does NOT fire for seeds routed only to non-00 steps.
 10. Real §3.2 scaffold structure: Expectation+Content labels + 1 real non-goal
     → fires (total substantive = 1, not 3).
 11. Scaffold-label skip requires trailing colon: a genuine non-goal starting with
     bold "**Content**" or "**Expectation**" WITHOUT a colon counts as substantive.
 12. W555 is warning-only (code starts with 'W').
 13. W555 is non-promotable (absent from PROMOTABLE_PAIRS).
 14. W555 fires exactly once (aggregate, not per-seed) for multiple thin seeds.
 15. Fenced backtick code blocks containing a fake out-of-scope heading are ignored.
 16. Fenced tilde (~~~) code blocks containing a fake out-of-scope heading are ignored.
 17. Empty bullets ("- " with no text) in out-of-scope section are NOT substantive
     → W555 fires (count is 0, not 3).
 18. Cross-delimiter fence discrimination: a ~~~ line inside a ```-opened fence is
     fenced content, not a closing delimiter — fake bullets after the ~~~ are skipped;
     only the genuine bullet outside the fence counts → W555 fires.

The real lint_seeds(), manifest parsing, and markdown parsing are NOT mocked.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from specdev_tools.validation.seed_lint import lint_seeds, _count_substantive_out_of_scope
from specdev_tools.core.errors import render_errors, PROMOTABLE_PAIRS

# Absolute path to toolkit root (needed for step_order.json / schema_registry.json).
_TOOLKIT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir)
)


# ---------------------------------------------------------------------------
# Project builder helpers (mirrors pattern from test_w553_seed_step_unknown.py)
# ---------------------------------------------------------------------------

def _build_project(
    tmpdir: str,
    *,
    seeds: list[dict],            # each: {seed_id, relpath, text}
    global_seed_order: list[str],
    step_requirements: dict,
) -> str:
    """Build a minimal project structure and return spec_dir."""
    spec_dir = os.path.join(tmpdir, "spec")
    os.makedirs(os.path.join(spec_dir, "common"), exist_ok=True)
    seed_dir = os.path.join(tmpdir, "docs", "seed")
    os.makedirs(seed_dir, exist_ok=True)

    manifest_seeds = []
    for s in seeds:
        abs_path = os.path.join(seed_dir, s["relpath"])
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(s["text"])
        manifest_seeds.append({
            "seed_id": s["seed_id"],
            "path": os.path.relpath(abs_path, tmpdir),
        })

    manifest = {
        "seed_directory": "docs/seed",
        "seeds": manifest_seeds,
        "global_seed_order": global_seed_order,
        "step_requirements": step_requirements,
    }
    manifest_path = os.path.join(spec_dir, "common", "seed_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    return spec_dir


def _seed(seed_id: str, relpath: str, text: str) -> dict:
    return {"seed_id": seed_id, "relpath": relpath, "text": text}


def _w555_errors(errors) -> list[str]:
    return [e for e in render_errors(errors) if "W555" in e]


# ---------------------------------------------------------------------------
# Seed content fixtures
# ---------------------------------------------------------------------------

# Seed with exactly 1 real out-of-scope item.
_SEED_ONE_REAL_ITEM = """\
# Product Brief

## 3. Scope

### 3.2 Out-of-Scope (Non-Goals)
- Multi-tenant support is out of scope for this release.
"""

# Seed with NO out-of-scope section at all.
_SEED_NO_SECTION = """\
# Product Brief

## 1. About This Document
Some introduction content.

## 2. Problem
The problem description.
"""

# Seed with bracket-placeholder bullets only (template placeholders, not real content).
_SEED_BRACKET_PLACEHOLDERS_ONLY = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- [Non-goal 1]
- [Non-goal 2]
"""

# Seed with scaffold label bullets only (Expectation/Content labels, no real items).
_SEED_SCAFFOLD_LABELS_ONLY = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- **Expectation**: Explicit list of "Phase 2" items to prevent scope creep.
- **Content**:
"""

# Seed with real §3.2 scaffold structure: scaffold labels + 1 real non-goal.
# Under the correct algorithm: labels are skipped, count = 1 → W555 fires.
_SEED_SCAFFOLD_WITH_ONE_REAL = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- **Expectation**: Explicit list of "Phase 2" items to prevent scope creep.
- **Content**:
  - Mobile app support is not in scope for MVP.
"""

# Seed with 2 substantive out-of-scope items.
_SEED_TWO_REAL_ITEMS = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- Third-party integrations are deferred to Phase 2.
- Offline mode is not in scope.
"""

# Seed with 3 substantive out-of-scope items (sufficient alone).
_SEED_THREE_REAL_ITEMS = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- Third-party integrations are deferred to Phase 2.
- Offline mode is not in scope.
- Multi-language support is deferred.
"""

# Seed with 1 additional substantive item (used to compose 3 across two seeds).
_SEED_ONE_REAL_ITEM_B = """\
# Product Brief

### Non-Goals
- Admin dashboard is excluded from MVP.
"""

# Seed where a fenced code block contains a fake out-of-scope heading and 2 fake
# bullets BEFORE the real out-of-scope section (which has 3 genuine items).
# Without the fenced-block fix the parser enters the section on the fake heading
# and counts 2 items, then breaks on the real heading → fires (discriminating).
# With the fix the fenced block is skipped entirely and the real 3 items are found.
_SEED_FENCED_FAKE_SECTION = """\
# Product Brief

## 2. Examples

```
### 3.2 Out-of-Scope (Non-Goals)
- Fake non-goal alpha inside fence.
- Fake non-goal beta inside fence.
```

### 3.2 Out-of-Scope (Non-Goals)
- Third-party integrations are deferred to Phase 2.
- Offline mode is not in scope.
- Multi-language support is deferred.
"""

# Seed where a TILDE fenced code block contains a fake out-of-scope heading and 2
# fake bullets BEFORE the real out-of-scope section (which has 3 genuine items).
# Mirrors _SEED_FENCED_FAKE_SECTION exactly, swapping backtick fences for tilde
# fences.  Without the tilde-fence fix the parser enters the section on the fake
# heading inside the fence, counts 2 items, then breaks on the real heading →
# W555 fires (discriminating).  With the fix the tilde fence is skipped entirely
# and the real 3 items are counted → no W555.
_SEED_TILDE_FENCED_FAKE_SECTION = """\
# Product Brief

## 2. Examples

~~~
### 3.2 Out-of-Scope (Non-Goals)
- Fake non-goal alpha inside tilde fence.
- Fake non-goal beta inside tilde fence.
~~~

### 3.2 Out-of-Scope (Non-Goals)
- Third-party integrations are deferred to Phase 2.
- Offline mode is not in scope.
- Multi-language support is deferred.
"""

# Seed where genuine non-goals start with bold words but WITHOUT a trailing colon.
# These must NOT be treated as scaffold labels — they are real content.
# With 3 such items the aggregate is 3 → W555 must NOT fire.
_SEED_BOLD_LEAD_WITHOUT_COLON = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- **Content** moderation workflows are deferred to Phase 2.
- **Expectation** management features are out of scope.
- **Multi-region** deployment is not planned for MVP.
"""

# Seed that proves cross-delimiter fence isolation (T1 fix).
# The out-of-scope section contains:
#   1. one genuine bullet OUTSIDE the fence,
#   2. a ```-opened fenced block that contains a ~~~ line followed by two fake
#      bullets that look like out-of-scope items.
#
# Old boolean-toggle impl: the ~~~ line inside the ``` block toggles in_fenced
# OFF, so the two subsequent fake bullets are visible to the bullet counter while
# in_section is still True → count = 3 → W555 does NOT fire (false-negative).
#
# Current fence_char impl: the ~~~ line is a non-matching delimiter inside a
# backtick fence → treated as fence content, fence stays open; the two fake
# bullets are skipped; only the one genuine bullet counts → count = 1 < 3
# → W555 fires (true-positive).
_SEED_CROSS_DELIMITER_FENCE = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- Genuine non-goal kept outside the fence.
```
pseudo code line
~~~
- fake bullet alpha
- fake bullet beta
```
"""

# Seed with exactly three EMPTY bullets ("- " with no text after the dash+space).
# An author who deletes the [Non-goal N] placeholder text but leaves the dash
# gets 3 empty bullets.  Empty bullets are NOT substantive content → W555 must fire
# (count = 0, not 3).
# Note: each bullet line ends with a trailing space after the dash so that
# _BULLET_RE (which requires \s+ after the marker) actually matches and m.group(1)
# is the empty string — this is the exact condition the F1 fix guards against.
_SEED_EMPTY_BULLETS_ONLY = """\
# Product Brief

### 3.2 Out-of-Scope (Non-Goals)
- \x20
- \x20
- \x20
"""


class TestW555Step00OutOfScopeThin(unittest.TestCase):
    """W555 STEP00_SEED_OUT_OF_SCOPE_THIN — aggregate thin-content detection."""

    # ------------------------------------------------------------------
    # 1. Fires when combined substantive out-of-scope items < 3 (1 item)
    # ------------------------------------------------------------------

    def test_fires_when_one_substantive_item(self):
        """A step-00 seed with exactly 1 real out-of-scope item → W555 fires."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_ONE_REAL_ITEM)],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected exactly 1 W555 for 1 substantive item. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 2. Fires when seed has NO out-of-scope section (0 items — core case)
    # ------------------------------------------------------------------

    def test_fires_when_no_out_of_scope_section(self):
        """A step-00 seed with no out-of-scope heading contributes 0 items → W555 fires."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_NO_SECTION)],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected exactly 1 W555 when no out-of-scope section. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 3. Fires when items are bracket-placeholders only (counted as 0)
    # ------------------------------------------------------------------

    def test_fires_when_only_bracket_placeholders(self):
        """Bracket-only bullets like [Non-goal 1] are NOT substantive → W555 fires."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_BRACKET_PLACEHOLDERS_ONLY)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected W555 for bracket-placeholder bullets only. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 4. Fires when items are scaffold label bullets only (Expectation/Content)
    # ------------------------------------------------------------------

    def test_fires_when_only_scaffold_labels(self):
        """Scaffold label bullets (- **Expectation**: / - **Content**:) are NOT substantive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_SCAFFOLD_LABELS_ONLY)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected W555 for scaffold-label-only bullets. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 5. Does NOT fire when combined substantive items >= 3
    #    (aggregate across two step-00 seeds: 2 + 1 = 3)
    # ------------------------------------------------------------------

    def test_no_fire_when_aggregate_equals_three(self):
        """Two step-00 seeds: 2 real items + 1 real item = 3 combined → no W555."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_TWO_REAL_ITEMS),
                    _seed("seed-goals", "seed_goals.md", _SEED_ONE_REAL_ITEM_B),
                ],
                global_seed_order=["seed-overview", "seed-goals"],
                step_requirements={"00": ["seed-overview", "seed-goals"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555 when aggregate substantive items = 3. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 6. Does NOT fire when a single seed has 3 substantive items
    # ------------------------------------------------------------------

    def test_no_fire_when_single_seed_has_three_items(self):
        """A single step-00 seed with 3 real out-of-scope items → no W555."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_THREE_REAL_ITEMS)],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555 for 3 substantive items. Got: {w555}\n"
                f"All errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 7. Does NOT fire when step "00" key is absent from step_requirements
    # ------------------------------------------------------------------

    def test_no_fire_when_step00_absent(self):
        """When step_requirements has no '00' key, W555 must never fire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_NO_SECTION)],
                global_seed_order=["seed-overview"],
                step_requirements={"04": ["seed-overview"]},  # no "00" key
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555 when '00' key absent from step_requirements. Got: {w555}",
            )

    # ------------------------------------------------------------------
    # 8. Does NOT fire when step "00" maps to an explicit empty list
    # ------------------------------------------------------------------

    def test_no_fire_when_step00_empty_list(self):
        """When step_requirements['00'] = [], W555 must not fire (gating: empty list)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_NO_SECTION)],
                global_seed_order=["seed-overview"],
                step_requirements={"00": []},  # explicit empty
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555 when step_requirements['00'] = []. Got: {w555}",
            )

    # ------------------------------------------------------------------
    # 9. Does NOT fire for seeds routed only to non-00 steps
    # ------------------------------------------------------------------

    def test_no_fire_for_non_00_step_seeds(self):
        """Seeds routed only to step '04' (no out-of-scope content) must not fire W555."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-api", "seed_api.md", _SEED_NO_SECTION)],
                global_seed_order=["seed-api"],
                step_requirements={"04": ["seed-api"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555 for seeds routed only to non-00 steps. Got: {w555}",
            )

    # ------------------------------------------------------------------
    # 10. Real §3.2 scaffold: Expectation+Content labels + 1 real item → fires
    # ------------------------------------------------------------------

    def test_fires_for_real_template_with_one_real_item(self):
        """Real §3.2 scaffold (Expectation label + Content label + 1 real item).

        Under the correct algorithm scaffold labels are skipped, so substantive
        count = 1.  W555 must fire.  Under a broken algorithm that counts labels
        as substantive, count = 3 and W555 silently suppresses — this test
        discriminates between the two.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_SCAFFOLD_WITH_ONE_REAL)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected W555 for real template with 1 real item (labels must not count). "
                f"Got: {w555}\nAll errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 11. Scaffold-label skip requires trailing colon — genuine bold-lead
    #     non-goals without a colon count as substantive
    # ------------------------------------------------------------------

    def test_bold_lead_without_colon_counts_as_substantive(self):
        """Bullets "- **Content** foo" (no colon) and "- **Expectation** bar" (no colon)
        are NOT scaffold labels — they are genuine non-goals.

        _SCAFFOLD_LABEL_RE requires a trailing colon (pattern ends with colon + optional space).
        Without the colon, the bullet is treated as substantive.  Three such items → no W555.

        This test discriminates the precise regex from an over-greedy variant
        that would skip all bold-lead bullets and under-count real content.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_BOLD_LEAD_WITHOUT_COLON)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555: bold-lead bullets without trailing colon are substantive. "
                f"Got: {w555}\nAll errors: {render_errors(errors)}",
            )

    # ------------------------------------------------------------------
    # 12. W555 is warning-only (code starts with 'W')
    # ------------------------------------------------------------------

    def test_w555_is_warning_only(self):
        """W555 findings have warning severity (code starts with 'W')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[_seed("seed-overview", "seed_overview.md", _SEED_NO_SECTION)],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = [e for e in errors if e.code == "W555"]
            self.assertTrue(w555, "Expected at least one W555 finding")
            for e in w555:
                self.assertTrue(
                    e.code.startswith("W"),
                    f"Expected warning-level code, got: {e.code}",
                )

    # ------------------------------------------------------------------
    # 13. W555 is non-promotable
    # ------------------------------------------------------------------

    def test_w555_is_non_promotable(self):
        """W555 must be absent from PROMOTABLE_PAIRS (E555 is a different code)."""
        self.assertNotIn(
            "W555",
            PROMOTABLE_PAIRS,
            "W555 must be non-promotable (E555=SEMANTIC_COVERAGE_REGRESSION is different)",
        )

    # ------------------------------------------------------------------
    # 14. W555 fires exactly once (not per-seed) even with multiple thin seeds
    # ------------------------------------------------------------------

    def test_fires_exactly_once_for_multiple_thin_seeds(self):
        """Two step-00 seeds, both thin → W555 fires exactly once (aggregate, not per-seed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_NO_SECTION),
                    _seed("seed-goals", "seed_goals.md", _SEED_NO_SECTION),
                ],
                global_seed_order=["seed-overview", "seed-goals"],
                step_requirements={"00": ["seed-overview", "seed-goals"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                len(w555),
                1,
                f"Expected exactly 1 W555 (aggregate, not per-seed). Got: {w555}",
            )


    # ------------------------------------------------------------------
    # 15. Fenced code blocks are ignored by the out-of-scope parser (F6)
    # ------------------------------------------------------------------

    def test_no_fire_when_fenced_block_contains_fake_section(self):
        """Fenced code block with a fake out-of-scope heading and 2 fake bullets
        must NOT be counted; only the 3 genuine bullets in the real section count.

        Discriminating: without the fenced-block fix the parser enters the section
        on the fake heading inside the fence, counts 2 fake bullets (<3), then
        breaks on the real heading → W555 fires.  With the fix the fence is
        skipped entirely and the real 3 items are counted → no W555.

        Uses a real temp project; lint_seeds() and the parser are NOT mocked.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_FENCED_FAKE_SECTION)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555: fenced-block fake section must not be counted. "
                f"Got: {w555}\nAll errors: {render_errors(errors)}",
            )


    # ------------------------------------------------------------------
    # 16. Tilde fenced code blocks are ignored by the out-of-scope parser
    # ------------------------------------------------------------------

    def test_no_fire_when_tilde_fenced_block_contains_fake_section(self):
        """Tilde fenced block (~~~) with a fake out-of-scope heading and 2 fake
        bullets must NOT be counted; only the 3 genuine bullets in the real
        section count.

        Discriminating: without the tilde-fence fix the parser enters the section
        on the fake heading inside the ~~~ fence, counts 2 fake bullets (<3), then
        breaks on the real heading → W555 fires.  With the fix the tilde fence is
        skipped entirely and the real 3 items are counted → no W555.

        Uses a real temp project; lint_seeds() and the parser are NOT mocked.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_TILDE_FENCED_FAKE_SECTION)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertEqual(
                w555,
                [],
                f"Expected no W555: tilde-fenced fake section must not be counted. "
                f"Got: {w555}\nAll errors: {render_errors(errors)}",
            )


    # ------------------------------------------------------------------
    # 17. Empty bullets ("- " with no text) are NOT substantive content
    # ------------------------------------------------------------------

    def test_fires_when_only_empty_bullets(self):
        """Three empty bullets ("- " with no text) in out-of-scope section are NOT
        substantive — W555 must fire (count = 0, not 3).

        Discriminating: without the F1 fix, _count_substantive_out_of_scope returns 3
        (each empty bullet falls through to count += 1) → W555 stays silent (false-negative).
        With the fix, the empty-content guard short-circuits each bullet → count = 0
        → W555 fires.

        Uses a real temp project; lint_seeds() and the parser are NOT mocked.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_EMPTY_BULLETS_ONLY)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected exactly 1 W555: empty bullets are not substantive content. "
                f"Got: {w555}\nAll errors: {render_errors(errors)}",
            )


    # ------------------------------------------------------------------
    # 18. Cross-delimiter fence isolation: ~~~ inside ``` fence is content,
    #     not a toggle — bullets inside the ``` block are NOT counted
    # ------------------------------------------------------------------

    def test_fires_when_cross_delimiter_fence_contains_fake_bullets(self):
        """A ```-opened fence containing a ~~~ line plus two fake out-of-scope
        bullets under the out-of-scope heading must NOT have those fake bullets
        counted.  Only the one genuine bullet OUTSIDE the fence is substantive
        → aggregate = 1 < 3 → W555 fires.

        Discriminating (T1 fix): the fixture places the out-of-scope heading
        FIRST, then one genuine bullet, then a ```-opened fence that contains a
        ~~~ line and two fake bullets.

        OLD boolean-toggle impl: the ~~~ line inside the ``` block flips
        in_fenced OFF, so the two subsequent fake bullets are counted while
        in_section is still True → count = 3 → W555 does NOT fire (false-neg).

        CURRENT fence_char impl: the ~~~ line is a non-matching delimiter inside a
        backtick fence → treated as fence content, fence stays open; the two fake
        bullets are skipped; only the genuine bullet counts → count = 1 → W555
        fires (true-positive).

        Two assertions are made:
        (a) Direct unit check: _count_substantive_out_of_scope returns 1.
        (b) Full lint run: exactly one W555 is emitted.

        lint_seeds() and the parser are NOT mocked.
        """
        # (a) Direct unit-level assertion — count must be 1 with the real impl.
        self.assertEqual(
            _count_substantive_out_of_scope(_SEED_CROSS_DELIMITER_FENCE),
            1,
            "Expected _count_substantive_out_of_scope to return 1: only the genuine "
            "bullet outside the fence should be counted; the two fake bullets inside "
            "the backtick fence (after ~~~) must be skipped.",
        )
        # (b) Full lint run — exactly one W555 must fire.
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = _build_project(
                tmpdir,
                seeds=[
                    _seed("seed-overview", "seed_overview.md", _SEED_CROSS_DELIMITER_FENCE)
                ],
                global_seed_order=["seed-overview"],
                step_requirements={"00": ["seed-overview"]},
            )
            errors = lint_seeds(
                repo_root=_TOOLKIT_ROOT, spec_dir=spec_dir, project_root=tmpdir
            )
            w555 = _w555_errors(errors)
            self.assertTrue(
                len(w555) == 1,
                f"Expected exactly 1 W555: cross-delimiter ~~~ inside ``` must not "
                f"count fake bullets. Got: {w555}\nAll errors: {render_errors(errors)}",
            )


if __name__ == "__main__":
    unittest.main()
