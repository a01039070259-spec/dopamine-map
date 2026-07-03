"""Venue list/detail API helpers (virtual + DB-backed venues)."""

from __future__ import annotations

import sqlite3
from typing import Optional

from server.database import get_conn, row_to_spot_summary


def extract_region(address: str) -> str:
    addr = (address or "").strip()
    if not addr:
        return ""
    return addr.split()[0]


def _spots_have_venue_id(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA table_info(spots)").fetchall()
    return any(row[1] == "venue_id" for row in rows)


def _venues_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venues'"
    ).fetchone()
    return row is not None


def _row_to_venue(row: sqlite3.Row, spot_count: int) -> dict:
    return {
        "id": row["id"],
        "virtual": False,
        "name": row["name"],
        "address": row["address"],
        "description": row["description"] or "",
        "mainImage": row["main_image"] or "",
        "region": row["region"],
        "spotCount": spot_count,
        "createdAt": row["created_at"],
    }


def _spot_to_virtual_venue(spot: dict) -> dict:
    """Ungrouped spot exposed as a venue using the same numeric id as the spot."""
    return {
        "id": spot["id"],
        "virtual": True,
        "name": spot["name"],
        "address": spot["addr"],
        "description": spot.get("br") or "",
        "mainImage": spot.get("img") or "",
        "region": extract_region(spot.get("addr") or ""),
        "spotCount": 1,
        "lat": spot.get("lat"),
        "lng": spot.get("lng"),
        "primarySpotId": spot["id"],
        "createdAt": spot.get("createdAt"),
    }


def list_venues() -> list[dict]:
    venues: list[dict] = []

    with get_conn() as conn:
        if _venues_table_exists(conn):
            rows = conn.execute(
                """
                SELECT v.*, COUNT(s.id) AS spot_count
                FROM venues v
                LEFT JOIN spots s ON s.venue_id = v.id
                GROUP BY v.id
                ORDER BY v.name COLLATE NOCASE, v.id ASC
                """
            ).fetchall()
            for row in rows:
                venues.append(_row_to_venue(row, int(row["spot_count"] or 0)))

        if _spots_have_venue_id(conn):
            spot_rows = conn.execute(
                """
                SELECT * FROM spots
                WHERE venue_id IS NULL
                ORDER BY id ASC
                """
            ).fetchall()
        else:
            spot_rows = conn.execute(
                "SELECT * FROM spots ORDER BY id ASC"
            ).fetchall()

    for row in spot_rows:
        spot = row_to_spot_summary(row)
        venues.append(_spot_to_virtual_venue(spot))

    return venues


def get_venue(venue_id: int) -> Optional[dict]:
    with get_conn() as conn:
        if _venues_table_exists(conn):
            row = conn.execute(
                "SELECT * FROM venues WHERE id = ?",
                (venue_id,),
            ).fetchone()
            if row:
                spot_rows = conn.execute(
                    "SELECT * FROM spots WHERE venue_id = ? ORDER BY id ASC",
                    (venue_id,),
                ).fetchall()
                spot_count = len(spot_rows)
                venue = _row_to_venue(row, spot_count)
                venue["spots"] = [row_to_spot_summary(r) for r in spot_rows]
                if spot_rows:
                    venue["lat"] = spot_rows[0]["lat"]
                    venue["lng"] = spot_rows[0]["lng"]
                    venue["primarySpotId"] = (
                        spot_rows[0]["id"] if spot_count == 1 else None
                    )
                else:
                    venue["lat"] = None
                    venue["lng"] = None
                    venue["primarySpotId"] = None
                return venue

        has_venue_id = _spots_have_venue_id(conn)
        spot_row = conn.execute(
            "SELECT * FROM spots WHERE id = ?",
            (venue_id,),
        ).fetchone()
        if not spot_row:
            return None
        if has_venue_id and spot_row["venue_id"] is not None:
            return None
        spot = row_to_spot_summary(spot_row)

    venue = _spot_to_virtual_venue(spot)
    venue["spots"] = [spot]
    return venue
