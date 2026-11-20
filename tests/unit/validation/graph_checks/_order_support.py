"""The order tests: a scenario run in a fresh process under each hash seed must give what the same scenario gives here."""
from __future__ import annotations

import json
from typing import Any

from unit.graph._synth import run_python_seeded


def jsonable(value: Any) -> Any:
    """*value* as ``json`` gives it back (tuples are lists)."""
    return json.loads(json.dumps(value))


def seeded(seed: int, module: str, function: str, *args: Any) -> Any:
    """``module.function(*args)`` run in a subprocess with ``PYTHONHASHSEED=seed``; its JSON result (arguments must be JSON-able)."""
    code = f"import json\nfrom {module} import {function}\nprint(json.dumps({function}(*json.loads({json.dumps(json.dumps(list(args)))}))))\n"
    return json.loads(run_python_seeded(seed, code))
