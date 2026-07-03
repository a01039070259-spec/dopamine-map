"""Apply SQL migrations on server startup."""

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATION_001_SQL = MIGRATIONS_DIR / "001_add_venues.sql"
BACKUP_SUFFIX = ".backup_pre_venues"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def apply_001_add_venues(db_path: Path) -> None:
    """Add venues table and spots.venue_id. Idempotent via venues table check."""
    migration_name = "001_add_venues"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_001_SQL.is_file():
        raise RuntimeError(f"migration {migration_name}: SQL file missing at {MIGRATION_001_SQL}")

    conn = sqlite3.connect(db_path)
    try:
        if _table_exists(conn, "venues"):
            logger.info("migration %s: skip (venues table already exists)", migration_name)
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_001_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(db_path)
    try:
        venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        spots_total = conn.execute("SELECT COUNT(*) FROM spots").fetchone()[0]
        spots_with_venue = conn.execute(
            "SELECT COUNT(*) FROM spots WHERE venue_id IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    logger.info(
        "migration %s: applied successfully "
        "(venues=%s spots=%s venue_id_set=%s)",
        migration_name,
        venue_count,
        spots_total,
        spots_with_venue,
    )


def apply_pending_migrations(db_path: Path) -> None:
    apply_001_add_venues(db_path)
