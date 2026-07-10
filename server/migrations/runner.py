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
MIGRATION_VISIT_TRACKING_SQL = MIGRATIONS_DIR / "003_add_visit_tracking.sql"
MIGRATION_COORD_VERIFIED_SQL = MIGRATIONS_DIR / "005_add_coord_verified.sql"
MIGRATION_006_VENUE_286_287_SQL = MIGRATIONS_DIR / "006_venue_286_287.sql"
MIGRATION_007_RENAME_VENUE_13_SQL = MIGRATIONS_DIR / "007_rename_venue_13.sql"
MIGRATION_008_KAKAO_PLACE_ID_SQL = MIGRATIONS_DIR / "008_add_kakao_place_id.sql"
VENUE_GROUPS_003_JSON = MIGRATIONS_DIR / "venue_groups_003.json"
VENUE_GROUPS_004_JSON = MIGRATIONS_DIR / "venue_groups_004.json"
BACKUP_SUFFIX_001 = ".backup_pre_venues"
BACKUP_SUFFIX_002 = ".backup_pre_venue_data"
BACKUP_SUFFIX_003 = ".backup_pre_venue_data_003"
BACKUP_SUFFIX_004 = ".backup_pre_venue_data_004"
BACKUP_SUFFIX_VISIT_TRACKING = ".backup_pre_visit_tracking"
BACKUP_SUFFIX_COORD_VERIFIED = ".backup_pre_coord_verified"
BACKUP_SUFFIX_006 = ".backup_pre_venue_286_287"
BACKUP_SUFFIX_007 = ".backup_pre_rename_venue_13"
BACKUP_SUFFIX_008 = ".backup_pre_kakao_place_id"
VENUE_006_NAME = "부산 스카이라인루지(기장해안로)"
VENUE_006_NAME_NEW = "부산 스카이라인 루지 & 하이플라이"
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
    """Skip only if an existing venue row matches (not spot names)."""
    skip_names = group.get("skip_if_names_exist") or []
    for token in skip_names:
        venue_hit = conn.execute(
            "SELECT 1 FROM venues WHERE name LIKE ? LIMIT 1",
            (f"%{token}%",),
        ).fetchone()
        if venue_hit:
            return True
    return False


def _migration_batch_applied(conn: sqlite3.Connection, groups: list[dict]) -> bool:
    """Done when every group has its venue row or is explicitly skipped."""
    for group in groups:
        venue_name = group["name"]
        if conn.execute("SELECT 1 FROM venues WHERE name = ?", (venue_name,)).fetchone():
            continue
        if _should_skip_group(conn, group):
            continue
        return False
    return True


def _apply_batch_venue_groups(
    db_path: Path,
    *,
    migration_name: str,
    groups_json: Path,
    backup_suffix: str,
) -> None:
    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not groups_json.is_file():
        raise RuntimeError(f"migration {migration_name}: config missing at {groups_json}")

    groups = json.loads(groups_json.read_text(encoding="utf-8"))

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "venues"):
            logger.info(
                "migration %s: skip (venues table missing; run 001 first)",
                migration_name,
            )
            return
        if _migration_batch_applied(conn, groups):
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

    backup_path = db_path.with_name(db_path.name + backup_suffix)
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
                logger.info(
                    "migration %s: venue exists, skip insert: %s",
                    migration_name,
                    venue_name,
                )
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


def apply_003_map_venues(db_path: Path) -> None:
    """Create batch-003 venue rows and link spots by name. Idempotent."""
    _apply_batch_venue_groups(
        db_path,
        migration_name="003_map_venues",
        groups_json=VENUE_GROUPS_003_JSON,
        backup_suffix=BACKUP_SUFFIX_003,
    )


def apply_004_map_venues(db_path: Path) -> None:
    """Create batch-004 venue rows and link spots by name. Idempotent."""
    _apply_batch_venue_groups(
        db_path,
        migration_name="004_map_venues",
        groups_json=VENUE_GROUPS_004_JSON,
        backup_suffix=BACKUP_SUFFIX_004,
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return column in cols


def apply_003_add_visit_tracking(db_path: Path) -> None:
    """Add referrer/UTM columns to visits. Idempotent via referrer column check."""
    migration_name = "003_add_visit_tracking"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_VISIT_TRACKING_SQL.is_file():
        raise RuntimeError(
            f"migration {migration_name}: SQL file missing at {MIGRATION_VISIT_TRACKING_SQL}"
        )

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "visits"):
            logger.info("migration %s: skip (visits table missing)", migration_name)
            return
        if _column_exists(conn, "visits", "referrer"):
            logger.info("migration %s: skip (referrer column already exists)", migration_name)
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_VISIT_TRACKING)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_VISIT_TRACKING_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    conn = sqlite3.connect(db_path)
    try:
        visit_count = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        null_referrer = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE referrer IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    logger.info(
        "migration %s: applied successfully (visits=%s legacy_null_referrer=%s)",
        migration_name,
        visit_count,
        null_referrer,
    )


def apply_006_venue_286_287(db_path: Path) -> None:
    """Link #286/#287 into one composite venue. Idempotent via venue name."""
    migration_name = "006_venue_286_287"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_006_VENUE_286_287_SQL.is_file():
        raise RuntimeError(
            f"migration {migration_name}: SQL file missing at {MIGRATION_006_VENUE_286_287_SQL}"
        )

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "venues"):
            logger.info(
                "migration %s: skip (venues table missing; run 001 first)",
                migration_name,
            )
            return
        existing = conn.execute(
            "SELECT id FROM venues WHERE name IN (?, ?)",
            (VENUE_006_NAME, VENUE_006_NAME_NEW),
        ).fetchone()
        if existing:
            venue_id = int(existing[0])
            linked = conn.execute(
                "SELECT COUNT(*) FROM spots WHERE venue_id = ? AND id IN (286, 287)",
                (venue_id,),
            ).fetchone()[0]
            if linked >= 2:
                logger.info(
                    "migration %s: skip (already applied; venue_id=%s)",
                    migration_name,
                    venue_id,
                )
                return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_006)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_006_VENUE_286_287_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
        venue = conn.execute(
            "SELECT id FROM venues WHERE name IN (?, ?)",
            (VENUE_006_NAME, VENUE_006_NAME_NEW),
        ).fetchone()
        linked = 0
        if venue:
            linked = conn.execute(
                "SELECT COUNT(*) FROM spots WHERE venue_id = ? AND id IN (286, 287)",
                (int(venue[0]),),
            ).fetchone()[0]
    finally:
        conn.close()

    logger.info(
        "migration %s: applied (venue=%s linked_spots=%s)",
        migration_name,
        VENUE_006_NAME,
        linked,
    )


def apply_005_add_coord_verified(db_path: Path) -> None:
    """Add spots.coord_verified flag. Idempotent via column check."""
    migration_name = "005_add_coord_verified"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_COORD_VERIFIED_SQL.is_file():
        raise RuntimeError(
            f"migration {migration_name}: SQL file missing at {MIGRATION_COORD_VERIFIED_SQL}"
        )

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "spots"):
            logger.info("migration %s: skip (spots table missing)", migration_name)
            return
        if _column_exists(conn, "spots", "coord_verified"):
            logger.info(
                "migration %s: skip (coord_verified column already exists)", migration_name
            )
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_COORD_VERIFIED)
    if backup_path.exists():
        logger.info(
            "migration %s: backup already exists at %s",
            migration_name,
            backup_path,
        )
    else:
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_COORD_VERIFIED_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    logger.info("migration %s: applied successfully", migration_name)


def apply_007_rename_venue_13(db_path: Path) -> None:
    """Rename venue 13 display name. Idempotent via old/new name check."""
    migration_name = "007_rename_venue_13"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_007_RENAME_VENUE_13_SQL.is_file():
        raise RuntimeError(
            f"migration {migration_name}: SQL file missing at {MIGRATION_007_RENAME_VENUE_13_SQL}"
        )

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "venues"):
            logger.info("migration %s: skip (venues table missing)", migration_name)
            return
        if conn.execute(
            "SELECT 1 FROM venues WHERE name = ?", (VENUE_006_NAME_NEW,)
        ).fetchone():
            logger.info("migration %s: skip (already renamed)", migration_name)
            return
        if not conn.execute(
            "SELECT 1 FROM venues WHERE name = ?", (VENUE_006_NAME,)
        ).fetchone():
            logger.info(
                "migration %s: skip (old venue name not found)", migration_name
            )
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_007)
    if not backup_path.exists():
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_007_RENAME_VENUE_13_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "migration %s: applied (%s -> %s)",
        migration_name,
        VENUE_006_NAME,
        VENUE_006_NAME_NEW,
    )


def apply_008_add_kakao_place_id(db_path: Path) -> None:
    """Add spots.kakao_place_id. Idempotent via column check."""
    migration_name = "008_add_kakao_place_id"

    if not db_path.is_file():
        logger.info("migration %s: skip (database file not found: %s)", migration_name, db_path)
        return

    if not MIGRATION_008_KAKAO_PLACE_ID_SQL.is_file():
        raise RuntimeError(
            f"migration {migration_name}: SQL file missing at {MIGRATION_008_KAKAO_PLACE_ID_SQL}"
        )

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "spots"):
            logger.info("migration %s: skip (spots table missing)", migration_name)
            return
        if _column_exists(conn, "spots", "kakao_place_id"):
            logger.info(
                "migration %s: skip (kakao_place_id column already exists)",
                migration_name,
            )
            return
    finally:
        conn.close()

    backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX_008)
    if not backup_path.exists():
        shutil.copy2(db_path, backup_path)
        logger.info("migration %s: backup created at %s", migration_name, backup_path)

    sql = MIGRATION_008_KAKAO_PLACE_ID_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    logger.info("migration %s: applied successfully", migration_name)


def apply_pending_migrations(db_path: Path) -> None:
    apply_001_add_venues(db_path)
    apply_002_map_venues(db_path)
    apply_003_map_venues(db_path)
    apply_004_map_venues(db_path)
    apply_003_add_visit_tracking(db_path)
    apply_005_add_coord_verified(db_path)
    apply_006_venue_286_287(db_path)
    apply_007_rename_venue_13(db_path)
    apply_008_add_kakao_place_id(db_path)
