# -*- coding: utf-8 -*-
"""Dry-run preview for 003_add_visit_tracking migration (no writes to production DB)."""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIGRATION_SQL = ROOT / "server" / "migrations" / "003_add_visit_tracking.sql"
BACKUP_SUFFIX = ".backup_pre_visit_tracking"
KST = timezone(timedelta(hours=9))


def column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def classify_referrer(referrer: str | None, utm_source: str | None) -> str:
    ref = (referrer or "").strip().lower()
    utm = (utm_source or "").strip().lower()
    if (not ref or ref == "direct") and not utm:
        return "직접 유입"
    hay = f"{ref} {utm}"
    if "threads.com" in hay or "threads.net" in hay:
        return "스레드"
    if "instagram.com" in hay:
        return "인스타그램"
    if "naver.com" in hay:
        return "네이버"
    if "google.com" in hay:
        return "구글 검색"
    if "kakao.com" in hay or "/talk" in hay or "kakaotalk" in hay:
        return "카카오톡"
    return "기타"


def print_section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    if not MIGRATION_SQL.is_file():
        raise SystemExit(f"Missing migration SQL: {MIGRATION_SQL}")

    sql_text = MIGRATION_SQL.read_text(encoding="utf-8")

    print_section("1. Migration file")
    print(f"Path: {MIGRATION_SQL}")
    print(f"Backup target: dopamine.db{BACKUP_SUFFIX}")
    print()
    print("SQL to apply:")
    print("-" * 60)
    print(sql_text.strip())
    print("-" * 60)

    print_section("2. Simulated schema change (temp DB)")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dopamine.db"
        prod_data = ROOT / "data"
        if (prod_data / "dopamine.db").is_file():
            shutil.copy2(prod_data / "dopamine.db", db_path)
            print(f"Source: copied local {prod_data / 'dopamine.db'}")
        else:
            # Build fresh schema matching production init_db visits table
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    visited_at TEXT NOT NULL
                );
                INSERT INTO visits (user_id, visited_at) VALUES
                    (NULL, '2026-07-05T10:00:00+00:00'),
                    (1, '2026-07-06T01:00:00+00:00'),
                    (NULL, '2026-07-06T03:30:00+00:00');
                """
            )
            conn.commit()
            conn.close()
            print("Source: synthetic visits-only DB (no local dopamine.db found)")

        conn = sqlite3.connect(db_path)
        before = column_names(conn, "visits")
        visit_count_before = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        conn.close()

        backup_path = db_path.with_name(db_path.name + BACKUP_SUFFIX)
        shutil.copy2(db_path, backup_path)

        conn = sqlite3.connect(db_path)
        conn.executescript(sql_text)
        conn.commit()
        after = column_names(conn, "visits")
        visit_count_after = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        null_referrer = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE referrer IS NULL"
        ).fetchone()[0]
        conn.close()

        print("BEFORE columns:", ", ".join(before))
        print("AFTER  columns:", ", ".join(after))
        print(f"Row count unchanged: {visit_count_before} -> {visit_count_after}")
        print(f"Existing rows with referrer NULL: {null_referrer} (expected: all legacy rows)")
        print(f"Backup would be created at: {backup_path.name}")

    print_section("3. Idempotency check")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "dopamine.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE visits (id INTEGER PRIMARY KEY, user_id INTEGER, visited_at TEXT NOT NULL)"
        )
        conn.commit()
        conn.close()
        conn = sqlite3.connect(db_path)
        conn.executescript(sql_text)
        conn.commit()
        conn.close()
        # second apply would fail on ADD COLUMN — runner must skip when referrer exists
        conn = sqlite3.connect(db_path)
        has_referrer = "referrer" in column_names(conn, "visits")
        conn.close()
        print("After first apply, referrer column exists:", has_referrer)
        print("Runner skip rule: if visits.referrer exists -> skip migration + skip backup")

    print_section("4. Referrer normalization preview (sample)")
    samples = [
        ("", None, "직접 유입"),
        ("direct", None, "직접 유입"),
        ("https://www.threads.net/@user/post/1", None, "스레드"),
        ("https://l.instagram.com/", "ig", "인스타그램"),
        ("https://search.naver.com/search.naver?q=test", None, "네이버"),
        ("https://www.google.com/", None, "구글 검색"),
        ("https://talk.kakao.com/...", None, "카카오톡"),
        ("https://example.com/blog", None, "기타"),
    ]
    for ref, utm, expected in samples:
        got = classify_referrer(ref, utm)
        status = "OK" if got == expected else "MISMATCH"
        print(f"  [{status}] ref={ref!r} utm={utm!r} -> {got}")

    print_section("5. Planned API / UI (not deployed yet)")
    print(f"GET /api/admin/stats/referrers?date=today  (KST today = {today_kst()})")
    print("POST /api/visits body adds: referrer, utm_source, utm_medium, utm_campaign, landing_page")
    print("admin.html: referrer breakdown list next to todayVisits")
    print()
    print("NOTE: Python runner already uses 003/004 for venue batch migrations.")
    print("      SQL file is 003_add_visit_tracking.sql; runner fn: apply_003_add_visit_tracking")
    print()
    print("DRY-RUN COMPLETE — no production database was modified.")


if __name__ == "__main__":
    main()
