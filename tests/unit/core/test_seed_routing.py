"""Tests for specdev_tools.core.seed_routing.

Covers resolve_seeds_for_step and resolve_seed_paths per the DEVSPEC-43
contract (plan §3.14).
"""
from __future__ import annotations

import os

from specdev_tools.core.seed_routing import resolve_seed_paths, resolve_seeds_for_step


# ---------------------------------------------------------------------------
# Fixtures / shared manifest builders
# ---------------------------------------------------------------------------

def _make_manifest(
    global_seed_order=None,
    seeds=None,
    step_requirements=None,
) -> dict:
    """Build a minimal manifest dict."""
    m = {}
    if global_seed_order is not None:
        m["global_seed_order"] = global_seed_order
    if seeds is not None:
        m["seeds"] = seeds
    if step_requirements is not None:
        m["step_requirements"] = step_requirements
    return m


# ---------------------------------------------------------------------------
# resolve_seeds_for_step — plain step (no umbrella)
# ---------------------------------------------------------------------------

class TestPlainStep:
    """Step "09": only step_requirements["09"] is returned; no umbrella."""

    def test_basic(self):
        manifest = _make_manifest(
            global_seed_order=["s-a", "s-b", "s-c"],
            step_requirements={
                "09": ["s-b", "s-a"],
                "16": ["s-x"],  # must NOT leak into "09"
            },
        )
        global_ids, step_ids = resolve_seeds_for_step("09", manifest)
        assert global_ids == ["s-a", "s-b", "s-c"]
        assert set(step_ids) == {"s-a", "s-b"}
        assert "s-x" not in step_ids

    def test_02a_no_umbrella(self):
        """Umbrella semantics must NOT apply to "02a"."""
        manifest = _make_manifest(
            global_seed_order=["s-a"],
            step_requirements={
                "02a": ["s-a"],
                "16": ["s-umbrella"],  # must NOT appear in "02a" results
            },
        )
        _, step_ids = resolve_seeds_for_step("02a", manifest)
        assert step_ids == ["s-a"]
        assert "s-umbrella" not in step_ids

    def test_13a_no_umbrella(self):
        """Umbrella semantics must NOT apply to "13a"."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "13a": ["s-impl"],
                "16": ["s-umbrella"],
            },
        )
        _, step_ids = resolve_seeds_for_step("13a", manifest)
        assert step_ids == ["s-impl"]
        assert "s-umbrella" not in step_ids

    def test_step_absent_from_requirements(self):
        """Step not in step_requirements → empty step_seed_ids."""
        manifest = _make_manifest(
            global_seed_order=["s-a"],
            step_requirements={"05": ["s-a"]},
        )
        global_ids, step_ids = resolve_seeds_for_step("07", manifest)
        assert global_ids == ["s-a"]
        assert step_ids == []


# ---------------------------------------------------------------------------
# resolve_seeds_for_step — "16" aggregate (all four sub-keys)
# ---------------------------------------------------------------------------

class TestStep16Aggregate:
    """step_id == "16" unions all of 16, 16a, 16b, 16c."""

    def _manifest(self):
        return _make_manifest(
            global_seed_order=["s-global"],
            step_requirements={
                "16":  ["s-bare-16"],   # bare key — MUST be included
                "16a": ["s-16a"],
                "16b": ["s-16b"],
                "16c": ["s-16c"],
            },
        )

    def test_all_sub_keys_included(self):
        _, step_ids = resolve_seeds_for_step("16", self._manifest())
        assert "s-bare-16" in step_ids
        assert "s-16a" in step_ids
        assert "s-16b" in step_ids
        assert "s-16c" in step_ids

    def test_bare_16_key_explicitly_included(self):
        """Bare "16" key must appear — this is the deliberate behavior
        change vs seed_lint._collect_required_seeds which skipped it."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "16":  ["s-only-in-bare"],
                "16a": [],
                "16b": [],
                "16c": [],
            },
        )
        _, step_ids = resolve_seeds_for_step("16", manifest)
        assert "s-only-in-bare" in step_ids

    def test_deduplication(self):
        """Seeds appearing in multiple sub-keys count once."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "16":  ["s-shared"],
                "16a": ["s-shared", "s-a-only"],
                "16b": ["s-shared"],
                "16c": [],
            },
        )
        _, step_ids = resolve_seeds_for_step("16", manifest)
        assert step_ids.count("s-shared") == 1
        assert "s-a-only" in step_ids

    def test_missing_sub_keys_ok(self):
        """Missing 16a/16b/16c keys don't raise — treat as empty."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={"16": ["s-bare"]},
        )
        _, step_ids = resolve_seeds_for_step("16", manifest)
        assert step_ids == ["s-bare"]


# ---------------------------------------------------------------------------
# resolve_seeds_for_step — trinity sub-phase (16a / 16b / 16c)
# ---------------------------------------------------------------------------

class TestTrinitySubPhase:
    """step_id in {16a,16b,16c}: own seeds PLUS umbrella "16" seeds."""

    def _manifest(self):
        return _make_manifest(
            global_seed_order=["s-global"],
            step_requirements={
                "16":  ["s-umbrella"],
                "16a": ["s-alpha"],
                "16b": ["s-beta"],
                "16c": ["s-gamma"],
            },
        )

    def test_16b_gets_own_and_umbrella(self):
        _, step_ids = resolve_seeds_for_step("16b", self._manifest())
        assert "s-beta" in step_ids       # own
        assert "s-umbrella" in step_ids   # umbrella
        assert "s-alpha" not in step_ids  # 16a — must NOT appear
        assert "s-gamma" not in step_ids  # 16c — must NOT appear

    def test_16a_gets_own_and_umbrella(self):
        _, step_ids = resolve_seeds_for_step("16a", self._manifest())
        assert "s-alpha" in step_ids
        assert "s-umbrella" in step_ids
        assert "s-beta" not in step_ids
        assert "s-gamma" not in step_ids

    def test_16c_gets_own_and_umbrella(self):
        _, step_ids = resolve_seeds_for_step("16c", self._manifest())
        assert "s-gamma" in step_ids
        assert "s-umbrella" in step_ids
        assert "s-alpha" not in step_ids
        assert "s-beta" not in step_ids

    def test_umbrella_key_absent(self):
        """If bare "16" key is absent, sub-phase still works."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={"16b": ["s-beta"]},
        )
        _, step_ids = resolve_seeds_for_step("16b", manifest)
        assert step_ids == ["s-beta"]

    def test_dedup_between_own_and_umbrella(self):
        """Seed in both sub-key and umbrella appears once."""
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "16":  ["s-shared"],
                "16a": ["s-shared", "s-a-only"],
            },
        )
        _, step_ids = resolve_seeds_for_step("16a", manifest)
        assert step_ids.count("s-shared") == 1
        assert "s-a-only" in step_ids


# ---------------------------------------------------------------------------
# resolve_seeds_for_step — ordering
# ---------------------------------------------------------------------------

class TestOrdering:
    """global_seed_order takes precedence; extras are appended."""

    def test_global_order_first(self):
        """Seeds in global_seed_order appear before extras, regardless of
        the order they are listed in step_requirements."""
        manifest = _make_manifest(
            global_seed_order=["s-c", "s-a", "s-b"],
            step_requirements={"04": ["s-b", "s-a", "s-c"]},
        )
        _, step_ids = resolve_seeds_for_step("04", manifest)
        assert step_ids == ["s-c", "s-a", "s-b"]

    def test_step_seed_absent_from_global_appended(self):
        """A step-required seed not in global_seed_order must be appended,
        not dropped."""
        manifest = _make_manifest(
            global_seed_order=["s-a", "s-b"],
            step_requirements={"04": ["s-b", "s-extra"]},
        )
        _, step_ids = resolve_seeds_for_step("04", manifest)
        assert step_ids[0] == "s-b"    # global order: s-a skipped (not required), s-b first
        assert step_ids[-1] == "s-extra"  # appended because not in global_order
        assert "s-extra" in step_ids

    def test_extra_preserved_in_encounter_order(self):
        """Multiple extras outside global_seed_order are appended in the
        order they were first encountered."""
        manifest = _make_manifest(
            global_seed_order=["s-a"],
            step_requirements={"05": ["s-z", "s-y", "s-a", "s-x"]},
        )
        _, step_ids = resolve_seeds_for_step("05", manifest)
        # global-order portion: just s-a
        assert step_ids[0] == "s-a"
        # remainder in encounter order: s-z, s-y, s-x
        remainder = step_ids[1:]
        assert remainder == ["s-z", "s-y", "s-x"]


# ---------------------------------------------------------------------------
# resolve_seeds_for_step — graceful handling
# ---------------------------------------------------------------------------

class TestGracefulHandling:
    """Unknown steps and absent/empty manifests never raise."""

    def test_unknown_step(self):
        manifest = _make_manifest(
            global_seed_order=["s-a"],
            step_requirements={"04": ["s-a"]},
        )
        global_ids, step_ids = resolve_seeds_for_step("unknown", manifest)
        assert global_ids == ["s-a"]
        assert step_ids == []

    def test_absent_step_requirements_key(self):
        manifest = _make_manifest(global_seed_order=["s-a"])
        global_ids, step_ids = resolve_seeds_for_step("04", manifest)
        assert global_ids == ["s-a"]
        assert step_ids == []

    def test_empty_manifest(self):
        global_ids, step_ids = resolve_seeds_for_step("04", {})
        assert global_ids == []
        assert step_ids == []

    def test_none_values_graceful(self):
        """Keys present but mapped to None are treated as empty."""
        manifest = {
            "global_seed_order": None,
            "seeds": None,
            "step_requirements": None,
        }
        global_ids, step_ids = resolve_seeds_for_step("04", manifest)
        assert global_ids == []
        assert step_ids == []

    def test_step_requirements_key_present_but_empty(self):
        manifest = _make_manifest(
            global_seed_order=["s-a"],
            step_requirements={"04": []},
        )
        _, step_ids = resolve_seeds_for_step("04", manifest)
        assert step_ids == []

    def test_none_step_id_does_not_raise(self):
        """step_id=None must return (global_seed_ids, []) without raising."""
        manifest = _make_manifest(
            global_seed_order=["s-a", "s-b"],
            step_requirements={"04": ["s-a"]},
        )
        global_ids, step_ids = resolve_seeds_for_step(None, manifest)
        assert global_ids == ["s-a", "s-b"]
        assert step_ids == []


# ---------------------------------------------------------------------------
# resolve_seed_paths
# ---------------------------------------------------------------------------

class TestResolveSeedPaths:
    """resolve_seed_paths resolves IDs to absolute paths."""

    def _manifest_with_seeds(self):
        return _make_manifest(
            global_seed_order=["s-a", "s-b"],
            seeds=[
                {"seed_id": "s-a", "path": "seeds/alpha.md"},
                {"seed_id": "s-b", "path": "seeds/beta.md"},
                {"seed_id": "s-c", "path": "seeds/gamma.md"},
            ],
        )

    def test_resolves_against_host_root(self):
        host_root = "/host/repo"
        paths = resolve_seed_paths(self._manifest_with_seeds(), ["s-a", "s-b"], host_root)
        assert paths["s-a"] == os.path.join("/host/repo", "seeds/alpha.md")
        assert paths["s-b"] == os.path.join("/host/repo", "seeds/beta.md")

    def test_omits_unknown_seed_id(self):
        """A seed_id not in manifest["seeds"] is silently omitted."""
        paths = resolve_seed_paths(self._manifest_with_seeds(), ["s-a", "s-nonexistent"], "/root")
        assert "s-a" in paths
        assert "s-nonexistent" not in paths

    def test_no_existence_filter(self):
        """Paths that don't exist on disk are still returned (pure helper)."""
        manifest = _make_manifest(
            seeds=[{"seed_id": "s-ghost", "path": "does/not/exist.md"}]
        )
        paths = resolve_seed_paths(manifest, ["s-ghost"], "/root")
        assert "s-ghost" in paths
        assert paths["s-ghost"] == os.path.join("/root", "does/not/exist.md")
        # The file must not exist for this test to be meaningful:
        assert not os.path.exists(paths["s-ghost"])

    def test_absolute_entry_path_handled(self):
        """If seeds[].path is already absolute, os.path.join returns it as-is."""
        abs_path = "/absolute/seed/file.md"
        manifest = _make_manifest(
            seeds=[{"seed_id": "s-abs", "path": abs_path}]
        )
        paths = resolve_seed_paths(manifest, ["s-abs"], "/some/host")
        assert paths["s-abs"] == abs_path

    def test_empty_seed_ids_list(self):
        paths = resolve_seed_paths(self._manifest_with_seeds(), [], "/root")
        assert paths == {}

    def test_empty_manifest_seeds(self):
        manifest = _make_manifest(seeds=[])
        paths = resolve_seed_paths(manifest, ["s-a"], "/root")
        assert paths == {}

    def test_missing_seeds_key(self):
        manifest = {}
        paths = resolve_seed_paths(manifest, ["s-a"], "/root")
        assert paths == {}


# ---------------------------------------------------------------------------
# Umbrella isolation — "16" key must NOT leak into non-16-family steps
# ---------------------------------------------------------------------------

class TestUmbrellaIsolation:
    """Bare "16" umbrella key must NOT affect any non-16-family step."""

    def test_16_bare_does_not_leak_into_02a(self):
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "02a": ["s-normal"],
                "16": ["s-umbrella"],
            },
        )
        _, step_ids = resolve_seeds_for_step("02a", manifest)
        assert "s-umbrella" not in step_ids
        assert step_ids == ["s-normal"]

    def test_16_bare_does_not_leak_into_00(self):
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "00": ["s-seed"],
                "16": ["s-umbrella"],
            },
        )
        _, step_ids = resolve_seeds_for_step("00", manifest)
        assert "s-umbrella" not in step_ids

    def test_16_bare_does_not_leak_into_13a(self):
        manifest = _make_manifest(
            global_seed_order=[],
            step_requirements={
                "13a": ["s-ext"],
                "16": ["s-umbrella"],
            },
        )
        _, step_ids = resolve_seeds_for_step("13a", manifest)
        assert "s-umbrella" not in step_ids
