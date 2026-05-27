"""DEPRECATED — `specdev context extract` was removed.

Use `specdev json read <file> '<jq>'` for surgical reads, scoped via
`specdev context structure` + `specdev json schema`. See /specdev-context skill.
"""
import sys

MIGRATION_MESSAGE = (
    "context extract is removed. Use 'specdev json read <file> '<jq>'' "
    "for surgical reads, scoped via 'specdev context structure' + 'specdev json schema'. "
    "See /specdev-context skill."
)


def extract_context(*_args, **_kwargs):
    """Deprecation stub — always exits 1 with the migration message.

    Accepts any signature so prior call sites fail cleanly with the migration
    message rather than a TypeError.
    """
    del _args, _kwargs
    print(MIGRATION_MESSAGE, file=sys.stderr)
    sys.exit(1)
