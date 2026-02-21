from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpecError:
    code: str
    message: str
    path: Optional[str] = None

    def render(self) -> str:
        if self.path:
            return f"{self.code} {self.path} {self.message}"
        return f"{self.code} {self.message}"


ERROR_CODES = {
    "E110": "UNKNOWN_CANONICAL_ID",
    "E120": "CANONICAL_KIND_MISMATCH",
    "E130": "CANONICAL_VERSION_MISMATCH",
    "E140": "AMBIGUOUS_ALIAS",
    "E210": "CROSS_ARTIFACT_DRIFT",
    "E310": "PROMPT_SCHEMA_DRIFT",
    "E410": "CANONICAL_ALIAS_COLLISION",
    "E420": "INVALID_DEPRECATION_LIFECYCLE",
    "E510": "PLACEHOLDER_VALUE_FOUND",
    "E520": "UNRESOLVED_INPUT",
    "E521": "VALIDATOR_RUNTIME",
    "E530": "INVENTED_ENUM_OR_ID",
    "E540": "SELF_OR_FORWARD_DEPENDENCY",
    "E550": "FORWARD_REPLAY_MISSING",
    "W110": "DEPRECATED_CANONICAL_USED",
    "W120": "ALIAS_DEPRECATED",
    "W130": "CANONICAL_REF_VERSION_OMITTED"
}


def make_error(code: str, message: str, path: Optional[str] = None) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(code=code, message=message, path=path)
