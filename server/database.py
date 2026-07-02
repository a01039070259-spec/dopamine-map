import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "dopamine.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kakao_id TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL,
                diagnosis_result TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                nick TEXT NOT NULL,
                content TEXT NOT NULL,
                stars TEXT NOT NULL DEFAULT '🔥🔥🔥',
                rating_fear INTEGER NOT NULL DEFAULT 50,
                rating_speed INTEGER NOT NULL DEFAULT 50,
                rating_adr INTEGER NOT NULL DEFAULT 50,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (spot_id) REFERENCES spots(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                visited_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
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


def row_to_spot_summary(row: sqlite3.Row) -> dict:
    spot = row_to_spot(row)
    spot.pop("reviews", None)
    spot.pop("warns", None)
    return spot


def review_row_to_dict(row: sqlite3.Row) -> dict:
    created = row["created_at"] or ""
    date_label = created[:7].replace("-", ".") if len(created) >= 7 else created
    return {
        "id": row["id"],
        "spotId": row["spot_id"],
        "userId": row["user_id"],
        "nick": row["nick"],
        "date": date_label,
        "stars": row["stars"],
        "text": row["content"],
        "tags": json.loads(row["tags"] or "[]"),
        "ratingFear": row["rating_fear"],
        "ratingSpeed": row["rating_speed"],
        "ratingAdr": row["rating_adr"],
        "createdAt": row["created_at"],
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
    return [row_to_spot_summary(r) for r in rows]


def get_spot(spot_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM spots WHERE id = ?", (spot_id,)).fetchone()
    return row_to_spot(row) if row else None


def get_spot_detail(spot_id: int) -> Optional[dict]:
    spot = get_spot(spot_id)
    if not spot:
        return None
    db_reviews = list_reviews_for_spot(spot_id)
    legacy_reviews = spot.pop("reviews", []) or []
    spot["reviews"] = db_reviews + legacy_reviews
    return spot


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


def get_user_by_kakao_id(kakao_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE kakao_id = ?", (kakao_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "kakaoId": row["kakao_id"],
        "nickname": row["nickname"],
        "diagnosisResult": row["diagnosis_result"],
        "createdAt": row["created_at"],
    }


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "kakaoId": row["kakao_id"],
        "nickname": row["nickname"],
        "diagnosisResult": row["diagnosis_result"],
        "createdAt": row["created_at"],
    }


def upsert_kakao_user(kakao_id: str, nickname: str) -> dict:
    existing = get_user_by_kakao_id(kakao_id)
    if existing:
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET nickname = ? WHERE kakao_id = ?",
                (nickname or existing["nickname"], kakao_id),
            )
            conn.commit()
        user = get_user_by_kakao_id(kakao_id)
        assert user is not None
        return user

    created = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (kakao_id, nickname, diagnosis_result, created_at) VALUES (?, ?, NULL, ?)",
            (kakao_id, nickname or "카카오유저", created),
        )
        conn.commit()
        user_id = cur.lastrowid
    user = get_user_by_id(user_id)
    assert user is not None
    return user


def update_user_diagnosis(user_id: int, result: str) -> Optional[dict]:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET diagnosis_result = ? WHERE id = ?",
            (result, user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def list_reviews_for_spot(spot_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE spot_id = ? ORDER BY created_at DESC, id DESC",
            (spot_id,),
        ).fetchall()
    return [review_row_to_dict(r) for r in rows]


def create_review(payload: dict, user_id: int, nickname: str) -> dict:
    tags = payload.get("tags") or []
    fear = int(payload.get("rating_fear") or payload.get("ratingFear") or 50)
    speed = int(payload.get("rating_speed") or payload.get("ratingSpeed") or 50)
    adr = int(payload.get("rating_adr") or payload.get("ratingAdr") or 50)
    avg = max(1, min(5, round((fear + speed + adr) / 60)))
    stars = "🔥" * avg
    nick = (payload.get("nick") or nickname or "익명").strip()[:16]
    content = (payload.get("content") or payload.get("text") or "").strip()
    created = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO reviews (
                spot_id, user_id, nick, content, stars,
                rating_fear, rating_speed, rating_adr, tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(payload["spot_id"]),
                user_id,
                nick,
                content,
                stars,
                fear,
                speed,
                adr,
                json.dumps(tags, ensure_ascii=False),
                created,
            ),
        )
        conn.commit()
        review_id = cur.lastrowid
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    assert row is not None
    return review_row_to_dict(row)


def record_visit(user_id: Optional[int] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO visits (user_id, visited_at) VALUES (?, ?)",
            (user_id, now_iso()),
        )
        conn.commit()


def get_admin_stats() -> dict:
    today = today_utc()
    with get_conn() as conn:
        total_visits = conn.execute("SELECT COUNT(*) AS c FROM visits").fetchone()["c"]
        today_visits = conn.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE substr(visited_at, 1, 10) = ?",
            (today,),
        ).fetchone()["c"]
        logged_in_visits = conn.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE user_id IS NOT NULL"
        ).fetchone()["c"]
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
    return {
        "totalVisits": total_visits,
        "todayVisits": today_visits,
        "loggedInVisits": logged_in_visits,
        "totalUsers": total_users,
        "totalReviews": total_reviews,
    }


def clear_all_login_data() -> dict:
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_visits = conn.execute("SELECT COUNT(*) AS c FROM visits").fetchone()["c"]
        total_reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
        conn.execute("DELETE FROM reviews")
        conn.execute("DELETE FROM visits")
        conn.execute("DELETE FROM users")
        conn.commit()
    return {
        "deletedUsers": total_users,
        "deletedVisits": total_visits,
        "deletedReviews": total_reviews,
    }
