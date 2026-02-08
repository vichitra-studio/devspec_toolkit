#!/usr/bin/env python3
import sys


def main() -> int:
    if sys.prefix == sys.base_prefix:
        sys.stderr.write(
            "Error: Running without a virtual environment. Activate dev_env or run via ./tools/run_specdev.sh.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
