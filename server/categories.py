# -*- coding: utf-8 -*-
"""Category list / map cluster helpers."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from server.category_defs import GROUP_META, resolve_category_slug
from server.database import get_conn
from server.venues import extract_region

_PROVINCE_ALIASES = {
    "서울특별시": "서울",
    "서울시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "세종시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
}


def normalize_province(region_or_addr: str) -> str:
    raw = (region_or_addr or "").strip()
    if not raw:
        return "기타"
    first = raw.split()[0]
    return _PROVINCE_ALIASES.get(first, first)


def row_to_category(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "groupSlug": row["group_slug"],
        "groupName": row["group_name"],
        "icon": row["icon"] or "",
        "sortOrder": row["sort_order"] or 0,
        "spotCount": int(row["spot_count"]) if "spot_count" in row.keys() else 0,
    }


def list_categories(*, with_counts: bool = True, only_with_spots: bool = False) -> list[dict]:
    with get_conn() as conn:
        if with_counts:
            rows = conn.execute(
                """
                SELECT c.*,
                       COALESCE((
                         SELECT COUNT(*) FROM spots s
                         WHERE s.category_id = c.id
                           AND (COALESCE(s.coord_verified, 0) = 1 OR COALESCE(s.legacy, 0) = 1)
                       ), 0) AS spot_count
                FROM categories c
                ORDER BY c.group_slug ASC, spot_count DESC, c.sort_order ASC, c.name ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT *, 0 AS spot_count FROM categories ORDER BY group_slug, sort_order, name"
            ).fetchall()
    out = [row_to_category(r) for r in rows]
    if only_with_spots:
        out = [c for c in out if c["spotCount"] > 0]
    return out


def list_category_groups(*, only_with_spots: bool = True) -> list[dict]:
    cats = list_categories(with_counts=True, only_with_spots=False)
    by_group: dict[str, dict] = {}
    for c in cats:
        g = c["groupSlug"]
        if g not in by_group:
            meta = GROUP_META.get(g, {})
            by_group[g] = {
                "groupSlug": g,
                "groupName": c["groupName"] or meta.get("name", g),
                "icon": meta.get("icon", ""),
                "sortOrder": meta.get("sort_order", 99),
                "spotCount": 0,
                "categories": [],
            }
        if c["spotCount"] > 0 or not only_with_spots:
            by_group[g]["categories"].append(c)
        by_group[g]["spotCount"] += c["spotCount"]
    groups = sorted(by_group.values(), key=lambda x: x["sortOrder"])
    if only_with_spots:
        for g in groups:
            g["categories"] = [c for c in g["categories"] if c["spotCount"] > 0]
    return groups


def get_category_by_id(category_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT c.*,
                   COALESCE((
                     SELECT COUNT(*) FROM spots s WHERE s.category_id = c.id
                   ), 0) AS spot_count
            FROM categories c WHERE c.id = ?
            """,
            (category_id,),
        ).fetchone()
    return row_to_category(row) if row else None


def resolve_category_id_for_spot(type_key: str, tl: str) -> Optional[int]:
    slug = resolve_category_slug(type_key, tl)
    if not slug:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM categories WHERE slug = ?", (slug,)
        ).fetchone()
    return int(row["id"]) if row else None


def map_region_clusters(
    *,
    group_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    season_month: Optional[int] = None,
) -> list[dict]:
    """L1 province bubbles: count verified spots (or venues approximating spot locations)."""
    sql = """
        SELECT s.id, s.addr, s.lat, s.lng, s.season_start_month, s.season_end_month,
               s.category_id, c.group_slug
        FROM spots s
        LEFT JOIN categories c ON c.id = s.category_id
        WHERE (COALESCE(s.coord_verified, 0) = 1 OR COALESCE(s.legacy, 0) = 1)
    """
    params: list = []
    if group_slug:
        sql += " AND c.group_slug = ?"
        params.append(group_slug)
    if category_id:
        sql += " AND s.category_id = ?"
        params.append(category_id)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    buckets: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "lat_sum": 0.0, "lng_sum": 0.0}
    )
    for row in rows:
        if season_month is not None:
            start = row["season_start_month"]
            end = row["season_end_month"]
            if start is not None and end is not None:
                m = season_month
                open_now = (start <= end and start <= m <= end) or (
                    start > end and (m >= start or m <= end)
                )
                if not open_now:
                    continue
        province = normalize_province(extract_region(row["addr"] or ""))
        if row["lat"] is None or row["lng"] is None:
            continue
        b = buckets[province]
        b["count"] += 1
        b["lat_sum"] += float(row["lat"])
        b["lng_sum"] += float(row["lng"])

    out = []
    for province, b in buckets.items():
        if b["count"] <= 0:
            continue
        out.append(
            {
                "region": province,
                "count": b["count"],
                "lat": b["lat_sum"] / b["count"],
                "lng": b["lng_sum"] / b["count"],
            }
        )
    out.sort(key=lambda x: -x["count"])
    return out


def is_pedal_boat(tl: str) -> bool:
    return (tl or "").strip() == "페달보트"
