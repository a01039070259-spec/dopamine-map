"""Apply SQL migrations on server startup."""

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATION_001_SQL = MIGRATIONS_DIR / "001_add_venues.sql"
MIGRATION_002_SQL = MIGRATIONS_DIR / "002_map_venues.sql"
BACKUP_SUFFIX_001 = ".backup_pre_venues"
BACKUP_SUFFIX_002 = ".backup_pre_venue_data"
MIGRATION_002_VENUE_NAMES = (
    "인제엑스게임리조트",
    "하동알프스레포츠(금오산)",
    "제천청풍랜드",
    "대천짚트랙타워",
    "단양만천하스카이워크",
    "해남땅끝마을스카이워크",
    "거제바람의(도장포)",
)


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

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_001)
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


def _migration_002_applied(conn: sqlite3.Connection) -> bool:
    placeholders = ",".join("?" * len(MIGRATION_002_VENUE_NAMES))
    count = conn.execute(
        f"SELECT COUNT(*) FROM venues WHERE name IN ({placeholders})",
        MIGRATION_002_VENUE_NAMES,
    ).fetchone()[0]
    return count == len(MIGRATION_002_VENUE_NAMES)


def apply_002_map_venues(db_path: Path) -> None:
    """Create 7 venue rows and link 19 spots. Idempotent via venue name check."""
    migration_name = "002_map_venues"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_002_SQL.is_file():
        raise RuntimeError(f"migration {migration_name}: SQL file missing at {MIGRATION_002_SQL}")

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "venues"):
            logger.info(
                "migration %s: skip (venues table missing; run 001 first)",
                migration_name,
            )
            return
        if _migration_002_applied(conn):
            venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
            spots_with_venue = conn.execute(
                "SELECT COUNT(*) FROM spots WHERE venue_id IS NOT NULL"
            ).fetchone()[0]
            spots_without_venue = conn.execute(
                "SELECT COUNT(*) FROM spots WHERE venue_id IS NULL"
            ).fetchone()[0]
            logger.info(
                "migration %s: skip (already applied; venues=%s venue_id_set=%s venue_id_null=%s)",
                migration_name,
                venue_count,
                spots_with_venue,
                spots_without_venue,
            )
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_002)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_002_SQL.read_text(encoding="utf-8")
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
        spots_without_venue = conn.execute(
            "SELECT COUNT(*) FROM spots WHERE venue_id IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    logger.info(
        "migration %s: applied successfully "
        "(venues=%s spots=%s venue_id_set=%s venue_id_null=%s)",
        migration_name,
        venue_count,
        spots_total,
        spots_with_venue,
        spots_without_venue,
    )

    if venue_count != 7 or spots_with_venue != 19 or spots_without_venue != 113:
        logger.warning(
            "migration %s: post-check mismatch "
            "(expected venues=7 venue_id_set=19 venue_id_null=113; got venues=%s set=%s null=%s)",
            migration_name,
            venue_count,
            spots_with_venue,
            spots_without_venue,
        )


def apply_pending_migrations(db_path: Path) -> None:
    apply_001_add_venues(db_path)
    apply_002_map_venues(db_path)
