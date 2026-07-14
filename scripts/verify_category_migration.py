# -*- coding: utf-8 -*-
"""Verify migration 010: every spot has category_id; print before/after + merge log.

Usage:
  python scripts/verify_category_migration.py              # local DATA_DIR DB
  python scripts/verify_category_migration.py --prod-sim   # map production API spots in-memory
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from server.category_defs import CATEGORY_SEED, resolve_category_slug  # noqa: E402


def verify_db(db_path: Path) -> int:
    import sqlite3

    if not db_path.is_file():
        print(f"FAIL: DB not found at {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM spots").fetchone()["c"]
        assigned = conn.execute(
            "SELECT COUNT(*) AS c FROM spots WHERE category_id IS NOT NULL"
        ).fetchone()["c"]
        nulls = conn.execute(
            """
            SELECT id, name, type, tl FROM spots WHERE category_id IS NULL
            ORDER BY id
            """
        ).fetchall()

        print(f"=== DB verify: {db_path}")
        print(f"total spots: {total}")
        print(f"with category_id: {assigned}")
        print(f"NULL category_id: {len(nulls)}")

        by_cat = conn.execute(
            """
            SELECT c.slug, c.name, c.group_slug, COUNT(s.id) AS n
            FROM categories c
            LEFT JOIN spots s ON s.category_id = c.id
            GROUP BY c.id
            ORDER BY c.group_slug, n DESC, c.name
            """
        ).fetchall()
        print("\ncategory spot counts:")
        for r in by_cat:
            print(f"  [{r['group_slug']}] {r['name']} ({r['slug']}): {r['n']}")

        # cave-boat vs cave-explore both exist?
        slugs = {r["slug"] for r in by_cat}
        assert "cave-boat" in slugs, "cave-boat category missing"
        assert "cave-explore" in slugs, "cave-explore category missing"
        print("\nOK: cave-boat (water) and cave-explore (land) both present")

        if nulls:
            print("\nNULL category_id spots (DEPLOY BLOCKED):")
            for r in nulls:
                print(f"  #{r['id']} {r['name']} type={r['type']!r} tl={r['tl']!r}")
            return 1

        print("\nPASS: category_id coverage 100%")
        return 0
    finally:
        conn.close()


def sim_prod() -> int:
    import httpx

    base = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")
    spots = httpx.get(f"{base}/api/spots", timeout=90).json()
    print(f"=== prod-sim via {base} ({len(spots)} spots)")

    before = Counter((s.get("type"), s.get("tl")) for s in spots)
    print("\nbefore (type/tl counts):")
    for (t, tl), n in before.most_common():
        print(f"  {n:3d}  {t!r} / {tl!r}")

    merge = Counter()
    unmapped = []
    after_slug = Counter()
    pedal = []
    for s in spots:
        t, tl = s.get("type") or "", s.get("tl") or ""
        slug = resolve_category_slug(t, tl)
        if not slug:
            unmapped.append(s)
            continue
        merge[f"{t!r}/{tl!r} → {slug}"] += 1
        after_slug[slug] += 1
        if tl.strip() == "페달보트":
            pedal.append(s)

    print("\nmerge log:")
    for k, n in merge.most_common():
        print(f"  {n:3d}  {k}")

    print("\nafter (canonical slug counts):")
    slug_name = {s: n for s, n, *_ in CATEGORY_SEED}
    for slug, n in after_slug.most_common():
        print(f"  {n:3d}  {slug} ({slug_name.get(slug, '?')})")

    # empty seed categories
    empty = [n for s, n, *_ in CATEGORY_SEED if after_slug[s] == 0]
    print(f"\nempty categories (seeded, 0 spots): {empty}")

    out_csv = ROOT / "scripts" / "pedal_boat_review.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "type", "tl", "addr", "note"])
        w.writeheader()
        for s in pedal:
            w.writerow(
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "type": s.get("type"),
                    "tl": s.get("tl"),
                    "addr": s.get("addr"),
                    "note": "jetboat로 배정됨 — 스릴 기준 발행 유지 재검토",
                }
            )
    print(f"\npedal_boat_review.csv: {len(pedal)}건 → {out_csv}")

    if unmapped:
        print(f"\nUNMAPPED ({len(unmapped)}):")
        for s in unmapped:
            print(f"  #{s['id']} {s['name']} type={s.get('type')!r} tl={s.get('tl')!r}")
        print("FAIL: would block deploy")
        return 1

    print(f"\nPASS sim: {len(spots)}/{len(spots)} mapped, unmapped=0")
    return 0


def main() -> None:
    if "--prod-sim" in sys.argv:
        raise SystemExit(sim_prod())
    from server.database import DB_PATH, init_db

    init_db()
    raise SystemExit(verify_db(DB_PATH))


if __name__ == "__main__":
    main()
