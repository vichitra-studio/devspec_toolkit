
from __future__ import annotations
import os, json

def _tiny_eval(expr, ctx):
    # Minimal JSONLogic subset for offline environments.
    if isinstance(expr, (str, int, float, bool)) or expr is None:
        return expr
    if isinstance(expr, list):
        return [_tiny_eval(e, ctx) for e in expr]
    if isinstance(expr, dict):
        if "var" in expr:
            path = expr["var"]
            if isinstance(path, str) and path:
                cur = ctx
                for part in path.split("."):
                    cur = cur.get(part) if isinstance(cur, dict) else None
                return cur
            return None
        for op, args in expr.items():
            vals = [_tiny_eval(a, ctx) for a in (args if isinstance(args, list) else [args])]
            if op == ">=": return vals[0] >= vals[1]
            if op == "<=": return vals[0] <= vals[1]
            if op == ">":  return vals[0] > vals[1]
            if op == "<":  return vals[0] < vals[1]
            if op == "==": return vals[0] == vals[1]
            if op == "and": return all(vals)
            if op == "or":  return any(vals)
            if op == "not": return not bool(vals[0])
            if op == "in":
                item, container = vals
                if isinstance(container, (list, tuple, set, str)):
                    return item in container
                return False
            if op == "contains":
                haystack, needle = vals
                if isinstance(haystack, (list, tuple, set, str)):
                    return needle in haystack
                return False
    return None

def run_invariants(spec_dir: str, sample: dict) -> list[dict]:
    out = []
    # find 06_invariants.json files
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = json.load(open(p, "r", encoding="utf-8"))
                except Exception:
                    continue
                if data.get("$schema","").endswith("/06_invariants.schema.json"):
                    for rule in data.get("rules", []):
                        expr = rule.get("expression")
                        try:
                            ok = _tiny_eval(json.loads(expr) if isinstance(expr, str) and expr.strip().startswith("{") else expr, sample)
                        except Exception:
                            ok = None
                        out.append({
                            "inv_id": rule.get("inv_id"),
                            "description": rule.get("description"),
                            "result": bool(ok),
                        })
    return out
