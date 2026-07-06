"""Apply SQL migrations on server startup."""

import json
import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATION_001_SQL = MIGRATIONS_DIR / "001_add_venues.sql"
MIGRATION_002_SQL = MIGRATIONS_DIR / "002_map_venues.sql"
VENUE_GROUPS_003_JSON = MIGRATIONS_DIR / "venue_groups_003.json"
BACKUP_SUFFIX_001 = ".backup_pre_venues"
BACKUP_SUFFIX_002 = ".backup_pre_venue_data"
BACKUP_SUFFIX_003 = ".backup_pre_venue_data_003"
MIGRATION_002_VENUE_NAMES = (
    "인제엑스게임리조트",
    "하동알프스레포츠(금오산)",
    "제천청풍랜드",
    "대천짚트랙타워",
    "단양만천하스카이워크",
    "해남땅끝마을스카이워크",
    "거제바람의(도장포)",
)
MIGRATION_003_VENUE_NAMES = (
    "강화레포츠파크(티앤림자연휴양림)",
    "장생포고래문화마을",
    "더스카이184(청라하늘대교)",
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


def _extract_region(address: str) -> str:
    addr = (address or "").strip()
    if not addr:
        return ""
    return addr.split()[0]


def _spot_ids_by_names(conn: sqlite3.Connection, names: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in names:
        row = conn.execute("SELECT id FROM spots WHERE name = ?", (name,)).fetchone()
        if row:
            result[name] = int(row[0])
    return result


def _should_skip_group(conn: sqlite3.Connection, group: dict) -> bool:
    skip_names = group.get("skip_if_names_exist") or []
    for token in skip_names:
        venue_hit = conn.execute(
            "SELECT 1 FROM venues WHERE name LIKE ? LIMIT 1",
            (f"%{token}%",),
        ).fetchone()
        if venue_hit:
            return True
        spot_hit = conn.execute(
            "SELECT 1 FROM spots WHERE name LIKE ? LIMIT 1",
            (f"%{token}%",),
        ).fetchone()
        if spot_hit:
            return True
    return False


def _migration_003_applied(conn: sqlite3.Connection) -> bool:
    """Applied when all non-skipped target venues exist (at least 장생포 + 더스카이)."""
    applied = 0
    for name in MIGRATION_003_VENUE_NAMES:
        row = conn.execute("SELECT 1 FROM venues WHERE name = ?", (name,)).fetchone()
        if row:
            applied += 1
    # 강화 may be skipped; success if 장생포+더스카이 exist (2) or all 3
    return applied >= 2 and conn.execute(
        "SELECT 1 FROM venues WHERE name = ?", ("장생포고래문화마을",)
    ).fetchone() and conn.execute(
        "SELECT 1 FROM venues WHERE name = ?", ("더스카이184(청라하늘대교)",)
    ).fetchone()


def apply_003_map_venues(db_path: Path) -> None:
    """Create batch-003 venue rows and link spots by name. Idempotent."""
    migration_name = "003_map_venues"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not VENUE_GROUPS_003_JSON.is_file():
        raise RuntimeError(
            f"migration {migration_name}: config missing at {VENUE_GROUPS_003_JSON}"
        )

    groups = json.loads(VENUE_GROUPS_003_JSON.read_text(encoding="utf-8"))

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "venues"):
            logger.info(
                "migration %s: skip (venues table missing; run 001 first)",
                migration_name,
            )
            return
        if _migration_003_applied(conn):
            venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
            spots_with_venue = conn.execute(
                "SELECT COUNT(*) FROM spots WHERE venue_id IS NOT NULL"
            ).fetchone()[0]
            logger.info(
                "migration %s: skip (already applied; venues=%s venue_id_set=%s)",
                migration_name,
                venue_count,
                spots_with_venue,
            )
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_003)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    linked = 0
    created = 0
    skipped_groups = 0

    conn = sqlite3.connect(db_path)
    try:
        for group in groups:
            venue_name = group["name"]
            existing = conn.execute(
                "SELECT id FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()
            if existing:
                logger.info("migration %s: venue exists, skip insert: %s", migration_name, venue_name)
                venue_id = int(existing[0])
            elif _should_skip_group(conn, group):
                logger.info(
                    "migration %s: skip group (existing name match): %s",
                    migration_name,
                    venue_name,
                )
                skipped_groups += 1
                continue
            else:
                rep_name = group["representative_name"]
                rep = conn.execute(
                    "SELECT addr FROM spots WHERE name = ?", (rep_name,)
                ).fetchone()
                if not rep:
                    logger.warning(
                        "migration %s: representative spot missing: %s",
                        migration_name,
                        rep_name,
                    )
                    continue
                addr = rep[0]
                region = _extract_region(addr)
                cur = conn.execute(
                    """
                    INSERT INTO venues (name, address, description, main_image, region)
                    VALUES (?, ?, NULL, NULL, ?)
                    """,
                    (venue_name, addr, region),
                )
                venue_id = int(cur.lastrowid)
                created += 1

            spot_names = group.get("spot_names") or []
            id_map = _spot_ids_by_names(conn, spot_names)
            missing = [n for n in spot_names if n not in id_map]
            if missing:
                logger.warning(
                    "migration %s: missing spots for %s: %s",
                    migration_name,
                    venue_name,
                    ", ".join(missing),
                )
            for spot_name in spot_names:
                spot_id = id_map.get(spot_name)
                if not spot_id:
                    continue
                conn.execute(
                    "UPDATE spots SET venue_id = ? WHERE id = ? AND venue_id IS NULL",
                    (venue_id, spot_id),
                )
                linked += 1

        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(db_path)
    try:
        venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        spots_with_venue = conn.execute(
            "SELECT COUNT(*) FROM spots WHERE venue_id IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    logger.info(
        "migration %s: applied (venues_created=%s groups_skipped=%s spots_linked=%s total_venues=%s venue_id_set=%s)",
        migration_name,
        created,
        skipped_groups,
        linked,
        venue_count,
        spots_with_venue,
    )


def apply_pending_migrations(db_path: Path) -> None:
    apply_001_add_venues(db_path)
    apply_002_map_venues(db_path)
    apply_003_map_venues(db_path)
