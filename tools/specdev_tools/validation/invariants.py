
# CEL evaluator: uses cel-python (imported as `celpy`, distributed on PyPI as
# `cel-python`). This library is the maintained pure-Python CEL implementation
# and supports the features exercised by real-world Step 06 invariants:
# ternaries, collection macros (.all/.exists/.filter), .contains/.startsWith/
# .matches, size(...), has(...), and comparison/logical operators.
#
# Known gaps (as of cel-python 0.1.5):
#   - `.split()` is a cel-go extension, not in the CEL spec proper; authors
#     needing tokenisation should pre-split values in the sample fixture.
# If cel-python becomes unmaintained or drops features, swap this module for a
# bind to google-cel or a hand-rolled evaluator — the _cel_eval surface is
# intentionally narrow to make substitution cheap.
from __future__ import annotations
import json
import os

# Pre-declare with a common base so both the happy path (real celpy classes)
# and the fallback path (Exception sentinel) are type-compatible.
_CelParseError: type[Exception]
_CelEvalError: type[Exception]

try:  # pragma: no cover - import guard
    import celpy  # type: ignore[import]
    from celpy.adapter import json_to_cel as _cel_json_to_cel  # type: ignore[import]
    _CEL_AVAILABLE = True
    _CEL_ENV = celpy.Environment()
    # Bind exception classes to module-level names so _cel_eval never needs to
    # access attributes on the module reference (which Pyright types as optional).
    _CelParseError = celpy.CELParseError
    _CelEvalError = celpy.CELEvalError
except Exception:  # pragma: no cover - library absent or broken at import time
    _CEL_AVAILABLE = False
    _CEL_ENV = None
    _cel_json_to_cel = None  # type: ignore[assignment]
    # Sentinels: the _CEL_AVAILABLE guard in _cel_eval returns before these are
    # ever reached, but they must be assigned so the name is always bound.
    _CelParseError = Exception
    _CelEvalError = Exception


def _cel_eval(expr_str, ctx):
    """Compile and evaluate a CEL expression string against *ctx*.

    Returns a tuple ``(raw_value, evaluable_flag, reason)`` where ``reason`` is
    ``None`` on success or a short machine-readable token on failure
    (``"cel_unavailable"``, ``"cel_parse_error"``, ``"cel_eval_error"``).
    """
    if not _CEL_AVAILABLE:
        return None, False, "cel_unavailable"

    # Bind module-level objects to locals so static analysers can narrow them.
    # _CEL_AVAILABLE=True guarantees these were set in the try block above.
    env = _CEL_ENV
    j2c = _cel_json_to_cel
    assert env is not None and j2c is not None

    try:
        ast = env.compile(expr_str)
        prog = env.program(ast)
    except _CelParseError:
        return None, False, "cel_parse_error"
    try:
        # celpy rejects identifiers that are not valid CEL names (e.g. keys
        # containing '-'). Skip those at the activation level so JSONLogic-style
        # samples (which allow arbitrary keys) do not break CEL evaluation.
        activation = {
            k: j2c(v)
            for k, v in (ctx or {}).items()
            if isinstance(k, str) and k.replace("_", "").isalnum() and not k[:1].isdigit()
        }
        raw = prog.evaluate(activation)
    except (_CelEvalError, ValueError, AttributeError, TypeError):
        # CELEvalError covers the canonical failure path.  AttributeError
        # and TypeError guard against internal celpy implementation gaps
        # (e.g. attribute access on missing activation keys) that surface
        # across different celpy releases.
        return None, False, "cel_eval_error"
    return raw, True, None


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
            if op in (">=", "<=", ">", "<", "==", "!="):
                if any(v is None for v in vals[:2]):
                    return None  # unresolved var → not evaluable
                if op == ">=": return vals[0] >= vals[1]
                if op == "<=": return vals[0] <= vals[1]
                if op == ">":  return vals[0] > vals[1]
                if op == "<":  return vals[0] < vals[1]
                if op == "==": return vals[0] == vals[1]
                if op == "!=": return vals[0] != vals[1]
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
            if op == "empty":
                v = vals[0]
                return v is None or v == "" or v == [] or v == {}
    return None


def run_invariants(spec_dir: str, sample: dict) -> list[dict]:
    out = []
    # find 06_invariants.json files
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                schema_uri = data.get("$schema", "")
                if schema_uri == "vc:06-invariants":
                    for rule in data.get("rules", []):
                        lang = rule.get("language", "jsonlogic")
                        expr = rule.get("expression")
                        evaluable = True
                        ok = None
                        reason = None
                        unsupported_language = None
                        if lang == "jsonlogic":
                            try:
                                parsed = (json.loads(expr)
                                          if isinstance(expr, str) and expr.strip()[:1] in ("{", "[")
                                          else expr)
                                ok = _tiny_eval(parsed, sample)
                            except (TypeError, ValueError, IndexError, KeyError, AttributeError):
                                ok = None
                                evaluable = False
                                reason = "jsonlogic_eval_error"
                            if evaluable and not isinstance(ok, bool):
                                evaluable = False
                                reason = "non_boolean_result" if ok is not None else "unresolved_expression"
                        elif lang == "cel":
                            if not isinstance(expr, str):
                                evaluable = False
                                reason = "cel_expression_not_string"
                            else:
                                raw, evaluable, reason = _cel_eval(expr, sample)
                                if evaluable:
                                    # Only booleans count as evaluated invariant results.
                                    try:
                                        is_bool = isinstance(raw, bool) or type(raw).__name__ == "BoolType"
                                    except Exception:
                                        is_bool = False
                                    if not is_bool:
                                        evaluable = False
                                        reason = "non_boolean_result"
                                    else:
                                        ok = bool(raw)
                        else:
                            evaluable = False
                            unsupported_language = lang
                            reason = "unsupported_language"
                        record = {
                            "inv_id": rule.get("inv_id"),
                            "description": rule.get("description"),
                            "result": bool(ok) if evaluable else False,
                            "evaluable": evaluable,
                            "language": lang,
                        }
                        if reason is not None:
                            record["unevaluable_reason"] = reason
                        if unsupported_language is not None:
                            record["unsupported_language"] = unsupported_language
                        out.append(record)
    return out
