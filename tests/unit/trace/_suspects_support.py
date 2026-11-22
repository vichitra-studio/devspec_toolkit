"""Support for the tests of the lock, the suspects, the replay and the coverage: a writable copy of the worked example with helpers to edit and read it."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.model import Graph
from specdev_tools.trace.lockfile import Lock, LockEntry, read_lock, write_lock
from specdev_tools.trace.suspects import SuspectLink, find_suspects

from ..graph._synth import ROOT
from ._lock_support import lock_for

SEED_FILE = Path("docs") / "seed" / "seed_accounts.md"
ANCHOR = "anchor-ms-account-recovery"
CRITERION = "ac-password-reset-3"

# The 21 links DOC 13.1 names (PD-3 with chain(T)): (holder, field, target).
CLOSURE_OF_CRITERION_EDIT = {
    ("PWRESET_CONFIRM_EXPIRED_01", "realises", "tc-confirm-expired-token"),
    ("api-password-reset-confirm", "derives_from", "fr-password-reset"),
    ("ec-token-at-expiry-second", "mitigated_by", CRITERION),
    ("ec-token-at-expiry-second", "mitigated_by", "fix-password-reset-expired-token"),
    ("ec-token-at-expiry-second", "threatens", "api-password-reset-confirm"),
    ("err-password-reset-confirm-token-expired", "derives_from", CRITERION),
    ("fix-password-reset-expired-token", "verifies", CRITERION),
    ("fix-password-reset-expired-token", "verifies", "api-password-reset-confirm"),
    ("fix-password-reset-reused-token", "verifies", "inv-reset-token-single-use"),
    ("inv-reset-token-single-use", "constrains", "api-password-reset-confirm"),
    ("inv-reset-token-single-use", "constrains", "fr-password-reset"),
    ("milestone-account-recovery", "schedules", "fr-password-reset"),
    ("nfr-latency-reset-email", "constrains", "fr-password-reset"),
    ("scaffold-password-reset-confirm", "realises", "api-password-reset-confirm"),
    ("tc-confirm-expired-token", "refines", CRITERION),
    ("tc-confirm-expired-token", "verified_by", "fix-password-reset-expired-token"),
    ("tc-confirm-reused-token", "refines", "inv-reset-token-single-use"),
    ("tc-confirm-reused-token", "verified_by", "fix-password-reset-reused-token"),
    ("threat-reset-token-replay", "mitigated_by", "fix-password-reset-expired-token"),
    ("threat-reset-token-replay", "mitigated_by", "inv-reset-token-single-use"),
    ("threat-reset-token-replay", "threatens", "api-password-reset-confirm"),
}
CLOSED_HOLDERS = {"PWRESET_CONFIRM_EXPIRED_01", "tc-confirm-expired-token", "tc-confirm-reused-token"}


class Example:
    """A writable copy of the worked example (spec folder, seed docs and committed lock) with helpers to edit and read it."""

    def __init__(self, host: Path) -> None:
        self.host = host
        self.spec = host / "spec"

    def graph(self) -> Graph:
        return build_graph(str(self.spec), str(ROOT))

    def lock(self) -> Lock:
        return read_lock(str(self.spec))

    def seed_texts(self, graph: Graph) -> dict[str, str]:
        return read_seed_texts(graph, str(self.host))

    def suspects(self) -> list[SuspectLink]:
        graph = self.graph()
        return find_suspects(graph, self.lock(), self.seed_texts(graph))

    def suspect_keys(self) -> set[tuple[str, str, str]]:
        return {suspect.key for suspect in self.suspects()}

    def edit_item(self, node_id: str, change: Callable[[dict[str, Any]], None]) -> None:
        """Apply *change* to the item of the node *node_id* in its spec file."""
        node = self.graph().by_id[node_id]
        path = self.spec / node.file
        document = json.loads(path.read_text(encoding="utf-8"))
        item = item_at(document, node.jq_path)
        assert item is not None
        change(item)  # type: ignore[arg-type]
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def edit_criterion(self) -> None:
        self.edit_item(CRITERION, lambda item: item.update(text=item["text"] + " Also reject a token issued for another account."))

    def edit_seed(self) -> None:
        path = self.host / SEED_FILE
        path.write_text(path.read_text(encoding="utf-8") + "\nThe link is also sent to the member's phone.\n", encoding="utf-8")

    def close_milestone(self) -> None:
        self.edit_item(ANCHOR, lambda item: item.update(status="done"))

    def write_lock(self, lock: Lock) -> None:
        write_lock(str(self.spec), lock)

    def attest(self, *holders: str) -> None:
        """Refresh every entry held by *holders* to the hashes of now, as ``attest`` will."""
        graph = self.graph()
        current = lock_for(graph, self.host, only_holders=holders)
        kept = [entry for entry in self.lock().entries if entry.source not in holders]
        self.write_lock(Lock((*kept, *current.entries)))

    def drop_entries(self, predicate: Callable[[LockEntry], bool]) -> None:
        self.write_lock(Lock(tuple(entry for entry in self.lock().entries if not predicate(entry))))
