#!/usr/bin/env python3
"""Manual runner for migration 002 (startup applies this automatically via init_db)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from server.database import DB_PATH
from server.migrations.runner import apply_002_map_venues

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    try:
        apply_002_map_venues(DB_PATH)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
