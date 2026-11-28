# refines_gold

INVENTED content ("Hollow Creek Seed Library"; nothing here comes from a host): the gold set of the `refines`
proposer (`specdev align propose --kind refines`, WI-M10-09; ruling P5: the 0.95 precision gate is a fixture gate).

It is a spec folder in the shape the proposer reads after the mechanical scripts, plus the capture's `task_status`:

| File | Holds |
|---|---|
| `spec/04_fr_list.json` | 23 FRs with 3 acceptance criteria each (`ac-<fr slug>-<n>`) |
| `spec/05_interface_contracts.json`, `06_invariants.json`, `07_nfrs.json` | 2 APIs with an error each, 4 invariants, 2 NFRs: the other kinds a task criterion may refine (an API and an NFR are linked to their FR, so they are one link away from it) |
| `spec/14_roadmap.json` | two milestones, 25 tasks, 104 task criteria (`tc-<fr slug>-<n>`), none with `refines` |
| `spec/extras/migration/capture.json` | `task_status`: per task its legacy `fr_refs` and `invariant_refs` (two tasks name none: one with `legacy_fr_refs: []`, one without the key) |
| `gold.json` | per task criterion: its `half`, the id a person would link (`refines`; `null` when they would link nothing) and its `shape` |

Shapes: `high` (restates an acceptance criterion at task level, most words kept), `low` (the same rule in other
words), `other-kind` (narrows an invariant, an API error or an NFR, not an acceptance criterion), `near-miss`
(shares words with the FR but states something no acceptance criterion states: a person would link nothing),
`no-refs` (a task that names no FR and no invariant).

## The split

* `tune`: milestone `ms-first-season`, 10 FRs, 46 criteria. The half the proposer's behaviour was looked at on.
  Nothing in the proposer was changed because of it: its constants (`MIN_SCORE` 0.6, the stop list, the TF-IDF form) are the
  pack's.
* `scored`: milestone `ms-second-season`, 13 FRs, 58 criteria. The test computes the precision here. Its labels were
  written before the first scored run. The first run gave 19 auto-eligible proposals (all right) against a planned floor of
  20, so three more FRs (`seed-quarantine`, `member-directory`, `workshop-feedback`) were written blind and added; no label
  of the first ten was changed.

The gate (`tests/unit/migration/test_refines_proposer.py`): of the scored criteria the proposer classes `auto-eligible`,
the share whose proposed target is the gold one is at least 0.95, and there are at least 20 of them.
