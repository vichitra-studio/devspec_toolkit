"""The pin sources the third-party and pin-source tests read: a lock file at argon2 0.41.1 and a client that names api-v3."""
from __future__ import annotations

from specdev_tools.core.host_declarations import PinSource

LOCK, CLIENT = "package-lock.json", "src/mail/client.ts"
ARGON_POINTER = "/packages/node_modules~1argon2/version"
RELAY_PATTERN = 'MAILRELAY_API_VERSION = "(api-v[0-9]+)"'
CLIENT_TEXT = 'export const MAILRELAY_API_VERSION = "api-v3";\n'


def pointer_source(pointer: str = ARGON_POINTER, file: str = LOCK) -> PinSource:
    """A ``json-pointer`` pin source."""
    return PinSource(type="json-pointer", file=file, pointer=pointer)


def regex_source(pattern: str = RELAY_PATTERN, file: str = CLIENT) -> PinSource:
    """A ``regex`` pin source."""
    return PinSource(type="regex", file=file, pattern=pattern)
