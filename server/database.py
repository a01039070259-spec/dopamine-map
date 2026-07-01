import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "dopamine.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                addr TEXT NOT NULL,
                type TEXT NOT NULL,
                tl TEXT NOT NULL,
                em TEXT NOT NULL DEFAULT '🔥',
                bg TEXT NOT NULL DEFAULT '#1a0a2e',
                img TEXT NOT NULL DEFAULT '',
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                th INTEGER NOT NULL DEFAULT 4,
                fe INTEGER NOT NULL DEFAULT 3,
                sp INTEGER NOT NULL DEFAULT 0,
                fp INTEGER NOT NULL DEFAULT 70,
                sp2 INTEGER NOT NULL DEFAULT 70,
                ap INTEGER NOT NULL DEFAULT 80,
                rank TEXT NOT NULL DEFAULT 'NEW SPOT',
                marker_type TEXT NOT NULL DEFAULT 'fire',
                tags TEXT NOT NULL DEFAULT '[]',
                br TEXT NOT NULL DEFAULT '',
                ts TEXT NOT NULL DEFAULT '🔥🔥🔥🔥',
                warns TEXT NOT NULL DEFAULT '[]',
                reviews TEXT NOT NULL DEFAULT '[]',
                custom INTEGER NOT NULL DEFAULT 1,
                approved INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def row_to_spot(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "addr": row["addr"],
        "type": row["type"],
        "tl": row["tl"],
        "em": row["em"],
        "bg": row["bg"],
        "img": row["img"] or "",
        "lat": row["lat"],
        "lng": row["lng"],
        "th": row["th"],
        "fe": row["fe"],
        "sp": row["sp"],
        "fp": row["fp"],
        "sp2": row["sp2"],
        "ap": row["ap"],
        "rank": row["rank"],
        "markerType": row["marker_type"],
        "tags": json.loads(row["tags"] or "[]"),
        "br": row["br"],
        "ts": row["ts"],
        "warns": json.loads(row["warns"] or "[]"),
        "reviews": json.loads(row["reviews"] or "[]"),
        "custom": bool(row["custom"]),
        "approved": bool(row["approved"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def spot_payload_to_columns(payload: dict) -> dict:
    tags = payload.get("tags") or []
    warns = payload.get("warns") or []
    reviews = payload.get("reviews") or []
    return {
        "name": payload["name"],
        "addr": payload["addr"],
        "type": payload.get("type") or "custom",
        "tl": payload.get("tl") or payload.get("type") or "액티비티",
        "em": payload.get("em") or "🔥",
        "bg": payload.get("bg") or "#1a0a2e",
        "img": payload.get("img") or "",
        "lat": float(payload["lat"]),
        "lng": float(payload["lng"]),
        "th": int(payload.get("th") or 3),
        "fe": int(payload.get("fe") or 3),
        "sp": int(payload.get("sp") or 0),
        "fp": int(payload.get("fp") or 50),
        "sp2": int(payload.get("sp2") or 50),
        "ap": int(payload.get("ap") or 50),
        "rank": payload.get("rank") or "NEW SPOT",
        "marker_type": payload.get("markerType") or "fire",
        "tags": json.dumps(tags, ensure_ascii=False),
        "br": payload.get("br") or "",
        "ts": payload.get("ts") or "🔥🔥🔥🔥",
        "warns": json.dumps(warns, ensure_ascii=False),
        "reviews": json.dumps(reviews, ensure_ascii=False),
        "custom": 1 if payload.get("custom", True) else 0,
        "approved": 1 if payload.get("approved", True) else 0,
    }


def list_spots() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM spots ORDER BY id ASC").fetchall()
    return [row_to_spot(r) for r in rows]


def get_spot(spot_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM spots WHERE id = ?", (spot_id,)).fetchone()
    return row_to_spot(row) if row else None


def create_spot(payload: dict) -> dict:
    cols = spot_payload_to_columns(payload)
    created = payload.get("createdAt") or now_iso()
    updated = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO spots (
                name, addr, type, tl, em, bg, img, lat, lng,
                th, fe, sp, fp, sp2, ap, rank, marker_type,
                tags, br, ts, warns, reviews, custom, approved,
                created_at, updated_at
            ) VALUES (
                :name, :addr, :type, :tl, :em, :bg, :img, :lat, :lng,
                :th, :fe, :sp, :fp, :sp2, :ap, :rank, :marker_type,
                :tags, :br, :ts, :warns, :reviews, :custom, :approved,
                :created_at, :updated_at
            )
            """,
            {**cols, "created_at": created, "updated_at": updated},
        )
        conn.commit()
        new_id = cur.lastrowid
    spot = get_spot(new_id)
    assert spot is not None
    return spot


def update_spot(spot_id: int, payload: dict) -> Optional[dict]:
    existing = get_spot(spot_id)
    if not existing:
        return None
    cols = spot_payload_to_columns(payload)
    created = payload.get("createdAt") or existing["createdAt"]
    updated = now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE spots SET
                name=:name, addr=:addr, type=:type, tl=:tl, em=:em, bg=:bg, img=:img,
                lat=:lat, lng=:lng, th=:th, fe=:fe, sp=:sp, fp=:fp, sp2=:sp2, ap=:ap,
                rank=:rank, marker_type=:marker_type, tags=:tags, br=:br, ts=:ts,
                warns=:warns, reviews=:reviews, custom=:custom, approved=:approved,
                created_at=:created_at, updated_at=:updated_at
            WHERE id=:id
            """,
            {**cols, "created_at": created, "updated_at": updated, "id": spot_id},
        )
        conn.commit()
    return get_spot(spot_id)


def delete_spot(spot_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM spots WHERE id = ?", (spot_id,))
        conn.commit()
        return cur.rowcount > 0
