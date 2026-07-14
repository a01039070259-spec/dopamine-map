"""Venue list/detail API helpers (virtual + DB-backed venues)."""

from __future__ import annotations

import sqlite3
from typing import Optional

from server.database import get_conn, row_to_spot_summary, venue_has_image


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


def _row_to_venue(
    row: sqlite3.Row,
    spot_count: int,
    *,
    for_list: bool = False,
    primary_spot_id: Optional[int] = None,
) -> dict:
    main_image = row["main_image"] or ""
    venue = {
        "id": row["id"],
        "virtual": False,
        "name": row["name"],
        "address": row["address"],
        "description": row["description"] or "",
        "mainImage": "" if for_list else main_image,
        "hasImage": venue_has_image(main_image),
        "region": row["region"],
        "spotCount": spot_count,
        "createdAt": row["created_at"],
    }
    if primary_spot_id:
        venue["primarySpotId"] = primary_spot_id
    return venue


def virtual_venue_id(spot_id: int) -> int:
    """Negative id so ungrouped spots never collide with real venues.id (often 1..N)."""
    return -int(spot_id)


def _spot_to_virtual_venue(spot: dict, *, for_list: bool = False) -> dict:
    """Ungrouped spot exposed as a venue; id is negative of spot id."""
    venue = {
        "id": virtual_venue_id(spot["id"]),
        "virtual": True,
        "name": spot["name"],
        "address": spot["addr"],
        "description": spot.get("br") or "",
        "mainImage": "" if for_list else (spot.get("img") or ""),
        "hasImage": bool(spot.get("hasImage")),
        "region": extract_region(spot.get("addr") or ""),
        "spotCount": 1,
        "lat": spot.get("lat"),
        "lng": spot.get("lng"),
        "primarySpotId": spot["id"],
        "createdAt": spot.get("createdAt"),
        "th": spot.get("th"),
        "fe": spot.get("fe"),
        "sp": spot.get("sp"),
        "em": spot.get("em"),
        "bg": spot.get("bg"),
        "tl": spot.get("tl"),
        "rank": spot.get("rank"),
        "ts": spot.get("ts"),
        "tags": spot.get("tags") or [],
        "categoryId": spot.get("categoryId"),
        "categorySlug": spot.get("categorySlug"),
        "categoryName": spot.get("categoryName"),
        "groupSlug": spot.get("groupSlug"),
        "groupName": spot.get("groupName"),
        "categoryIcon": spot.get("categoryIcon"),
    }
    return venue


def list_venues() -> list[dict]:
    venues: list[dict] = []

    with get_conn() as conn:
        if _venues_table_exists(conn):
            rows = conn.execute(
                """
                SELECT v.*,
                       COUNT(s.id) AS spot_count,
                       MIN(s.id) AS primary_spot_id
                FROM venues v
                LEFT JOIN spots s ON s.venue_id = v.id
                GROUP BY v.id
                ORDER BY v.name COLLATE NOCASE, v.id ASC
                """
            ).fetchall()
            for row in rows:
                primary = row["primary_spot_id"]
                venues.append(
                    _row_to_venue(
                        row,
                        int(row["spot_count"] or 0),
                        for_list=True,
                        primary_spot_id=int(primary) if primary else None,
                    )
                )

        spot_rows = []
        if _spots_have_venue_id(conn):
            try:
                spot_rows = conn.execute(
                    """
                    SELECT s.*,
                           c.slug AS category_slug,
                           c.name AS category_name,
                           c.group_slug AS group_slug,
                           c.group_name AS group_name,
                           c.icon AS category_icon
                    FROM spots s
                    LEFT JOIN categories c ON c.id = s.category_id
                    WHERE s.venue_id IS NULL
                    ORDER BY s.id ASC
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                spot_rows = conn.execute(
                    """
                    SELECT * FROM spots
                    WHERE venue_id IS NULL
                    ORDER BY id ASC
                    """
                ).fetchall()
        else:
            try:
                spot_rows = conn.execute(
                    """
                    SELECT s.*,
                           c.slug AS category_slug,
                           c.name AS category_name,
                           c.group_slug AS group_slug,
                           c.group_name AS group_name,
                           c.icon AS category_icon
                    FROM spots s
                    LEFT JOIN categories c ON c.id = s.category_id
                    ORDER BY s.id ASC
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                spot_rows = conn.execute(
                    "SELECT * FROM spots ORDER BY id ASC"
                ).fetchall()

    for row in spot_rows:
        spot = row_to_spot_summary(row)
        venues.append(_spot_to_virtual_venue(spot, for_list=True))

    return venues


def _get_virtual_venue_by_spot_id(spot_id: int) -> Optional[dict]:
    with get_conn() as conn:
        has_venue_id = _spots_have_venue_id(conn)
        spot_row = conn.execute(
            "SELECT * FROM spots WHERE id = ?",
            (spot_id,),
        ).fetchone()
        if not spot_row:
            return None
        if has_venue_id and spot_row["venue_id"] is not None:
            return None
        spot = row_to_spot_summary(spot_row)

    venue = _spot_to_virtual_venue(spot, for_list=False)
    venue["spots"] = [spot]
    return venue


def get_venue(venue_id: int) -> Optional[dict]:
    if venue_id < 0:
        return _get_virtual_venue_by_spot_id(-venue_id)

    with get_conn() as conn:
        if _venues_table_exists(conn):
            row = conn.execute(
                "SELECT * FROM venues WHERE id = ?",
                (venue_id,),
            ).fetchone()
            if row:
                spot_rows = []
                try:
                    spot_rows = conn.execute(
                        """
                        SELECT s.*,
                               c.slug AS category_slug,
                               c.name AS category_name,
                               c.group_slug AS group_slug,
                               c.group_name AS group_name,
                               c.icon AS category_icon
                        FROM spots s
                        LEFT JOIN categories c ON c.id = s.category_id
                        WHERE s.venue_id = ?
                        ORDER BY s.id ASC
                        """,
                        (venue_id,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    spot_rows = conn.execute(
                        "SELECT * FROM spots WHERE venue_id = ? ORDER BY id ASC",
                        (venue_id,),
                    ).fetchall()
                spot_count = len(spot_rows)
                primary_id = spot_rows[0]["id"] if spot_rows else None
                venue = _row_to_venue(
                    row,
                    spot_count,
                    for_list=True,
                    primary_spot_id=primary_id,
                )
                venue["spots"] = [row_to_spot_summary(r) for r in spot_rows]
                if spot_rows:
                    venue["lat"] = spot_rows[0]["lat"]
                    venue["lng"] = spot_rows[0]["lng"]
                    venue["primarySpotId"] = primary_id
                else:
                    venue["lat"] = None
                    venue["lng"] = None
                    venue["primarySpotId"] = None
                return venue

    return _get_virtual_venue_by_spot_id(venue_id)
