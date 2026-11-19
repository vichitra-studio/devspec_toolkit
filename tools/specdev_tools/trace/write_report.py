"""The report of an id-keyed write or a ``step create``: the JSON dict and the text, shared by both commands.

``id_write_commands`` (``specdev json ... --id|--step``) and ``trace.commands`` (``specdev step create``) print a
``WriteResult`` through these; neither command imports the other's CLI module.  A dry run says "to write" / "to remove"
where a write says "written" / "removed".
"""
from __future__ import annotations

from typing import Any

from specdev_tools.graph.queries import plural
from specdev_tools.trace.id_writes import WriteResult
from specdev_tools.trace.lockfile import LockEntry


def _entry_dict(entry: LockEntry) -> dict[str, str]:
    return {"holder": entry.source, "field": entry.field, "target": entry.target}


def result_to_dict(result: WriteResult) -> dict[str, Any]:
    """The result as a JSON-able dict (``json --json``): the write, ``targets``, ``lock``, ``newly_suspect`` and ``broken``."""
    return {
        "action": result.action,
        "id": result.node_id,
        "file": result.file,
        "jq_path": result.jq_path,
        "written": result.written,
        "minted": list(result.minted),
        "targets": [
            {"holder": item.holder, "field": item.field, "target": item.target, "kind": item.kind, "step": item.step, "text": item.text}
            for item in result.targets
        ],
        "lock": {"written": [_entry_dict(e) for e in result.lock_written], "removed": [_entry_dict(e) for e in result.lock_removed]},
        "newly_suspect": [{"step": step, "count": count} for step, count in result.newly_suspect],
        "broken": [{"holder": link.holder, "field": link.field, "target": link.target} for link in result.broken],
    }


_VERBS = {"patch": ("patched", "patch"), "insert": ("inserted into", "insert into"), "delete": ("deleted", "delete"), "create": ("created", "create")}


def _target_lines(result: WriteResult) -> list[str]:
    if not result.targets:
        return []
    lines = ["targets:"]
    for item in result.targets:
        step = f", step {item.step}" if item.step else ""
        lines.append(f"  {item.holder}.{item.field} -> {item.target} ({item.kind}{step}): {item.text}")
    return lines


def _lock_lines(result: WriteResult) -> list[str]:
    lines: list[str] = []
    written, removed = (
        ("lock entry written", "lock entry removed") if result.written else ("lock entry to write", "lock entry to remove")
    )
    for label, entries in ((written, result.lock_written), (removed, result.lock_removed)):
        lines.extend(f"{label}: {e.source}.{e.field} -> {e.target}" for e in entries)
    return lines


def render_text(result: WriteResult) -> str:
    """The text report: the change, the targets, the lock entries, the newly suspect links and, for a delete, the broken links."""
    past, plain = _VERBS[result.action]
    where = f"{result.node_id} ({result.file} {result.jq_path or '.'})"
    lines = [f"{past} {where}" if result.written else f"[dry-run] would {plain} {where}"]
    if result.minted:
        lines.append(f"ids minted: {', '.join(result.minted)}")
    lines.extend(_target_lines(result))
    lines.extend(_lock_lines(result))
    if result.newly_suspect:
        total = sum(count for _step, count in result.newly_suspect)
        per_step = ", ".join(f"step {step}: {count}" for step, count in result.newly_suspect)
        if result.written:
            lines.append(f"newly suspect: {plural(total, 'link')} ({per_step}); see `specdev stale`")
        else:
            lines.append(f"would become suspect: {plural(total, 'link')} ({per_step})")
    if result.broken:
        lines.append(f"now broken ({plural(len(result.broken), 'link')} point at the deleted node):")
        lines.extend(f"  {link.holder}.{link.field} -> {link.target}" for link in result.broken)
    return "\n".join(lines)
