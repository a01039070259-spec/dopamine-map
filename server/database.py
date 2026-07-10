import base64
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from server.migrations.runner import apply_pending_migrations


def _resolve_data_dir() -> Path:
    raw = os.getenv("DOPAMINE_DATA_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = _resolve_data_dir()
DB_PATH = DATA_DIR / "dopamine.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


KST = timezone(timedelta(hours=9))


def today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def kst_day_utc_bounds(date_str: str) -> tuple[str, str]:
    start_kst = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
    end_kst = start_kst + timedelta(days=1) - timedelta(seconds=1)
    start_utc = start_kst.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    end_utc = end_kst.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return start_utc, end_utc


def classify_visit_source(
    referrer: str | None, utm_source: str | None
) -> tuple[str, str | None]:
    ref = (referrer or "").strip().lower()
    utm = (utm_source or "").strip().lower()
    if (not ref or ref == "direct") and not utm:
        return "직접 유입", None
    hay = f"{ref} {utm}"
    if "threads.com" in hay or "threads.net" in hay:
        return "스레드", None
    if "instagram.com" in hay or "instagr.am" in hay:
        return "인스타그램", None
    if "naver.com" in hay:
        return "네이버", None
    if "google.com" in hay or "google.co.kr" in hay:
        return "구글 검색", None
    if "kakao.com" in hay or "kakaotalk" in hay or "/talk" in hay:
        return "카카오톡", None
    raw = (referrer or utm_source or "").strip()
    if not raw or raw.lower() == "direct":
        raw = utm_source or referrer or "unknown"
    return "기타", raw[:200] if raw else None


def _visits_has_tracking_columns(conn: sqlite3.Connection) -> bool:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(visits)")}
    return "referrer" in cols


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
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

    apply_pending_migrations(DB_PATH)


def row_to_spot(row: sqlite3.Row) -> dict:
    spot = {
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
    if "venue_id" in row.keys():
        spot["venueId"] = row["venue_id"]
    if "coord_verified" in row.keys():
        spot["coordVerified"] = bool(row["coord_verified"])
    return spot


def spot_has_image(img: str) -> bool:
    return bool(img and str(img).startswith("data:image"))


def venue_has_image(img: str) -> bool:
    return spot_has_image(img)


def _decode_image_data_url(img: str) -> Optional[tuple[bytes, str]]:
    if not spot_has_image(img):
        return None
    match = re.match(r"data:(image/[^;]+);base64,(.+)", img, re.DOTALL)
    if not match:
        return None
    try:
        return base64.b64decode(match.group(2)), match.group(1)
    except (ValueError, TypeError):
        return None


def row_to_spot_summary(row: sqlite3.Row) -> dict:
    spot = row_to_spot(row)
    spot.pop("reviews", None)
    spot.pop("warns", None)
    img = spot.pop("img", "") or ""
    spot["hasImage"] = spot_has_image(img)
    return spot


def get_spot_image_data(spot_id: int) -> Optional[tuple[bytes, str]]:
    with get_conn() as conn:
        row = conn.execute("SELECT img FROM spots WHERE id = ?", (spot_id,)).fetchone()
    if not row:
        return None
    return _decode_image_data_url(row["img"] or "")


def get_venue_image_data(venue_id: int) -> Optional[tuple[bytes, str]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT main_image FROM venues WHERE id = ?", (venue_id,)
        ).fetchone()
    if not row:
        return None
    return _decode_image_data_url(row["main_image"] or "")


def update_venue(venue_id: int, payload: dict) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        if not row:
            return None
        main_image = (
            payload["mainImage"] if "mainImage" in payload else row["main_image"]
        ) or ""
        description = (
            payload["description"] if "description" in payload else row["description"]
        ) or ""
        conn.execute(
            """
            UPDATE venues SET main_image = ?, description = ?
            WHERE id = ?
            """,
            (main_image, description, venue_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM venues WHERE id = ?", (venue_id,)
        ).fetchone()
    if not updated:
        return None
    spot_count = 0
    with get_conn() as conn:
        spot_count = conn.execute(
            "SELECT COUNT(*) FROM spots WHERE venue_id = ?", (venue_id,)
        ).fetchone()[0]
    return {
        "id": updated["id"],
        "name": updated["name"],
        "address": updated["address"],
        "description": updated["description"] or "",
        "mainImage": updated["main_image"] or "",
        "hasImage": venue_has_image(updated["main_image"] or ""),
        "region": updated["region"],
        "spotCount": int(spot_count or 0),
        "createdAt": updated["created_at"],
    }


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
        "coord_verified": 1 if payload.get("coordVerified") else 0,
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
                coord_verified, created_at, updated_at
            ) VALUES (
                :name, :addr, :type, :tl, :em, :bg, :img, :lat, :lng,
                :th, :fe, :sp, :fp, :sp2, :ap, :rank, :marker_type,
                :tags, :br, :ts, :warns, :reviews, :custom, :approved,
                :coord_verified, :created_at, :updated_at
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
    if "coordVerified" not in payload:
        # 부분 업데이트에서 기존 검증 플래그가 초기화되지 않도록 유지
        cols["coord_verified"] = 1 if existing.get("coordVerified") else 0
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
                coord_verified=:coord_verified, created_at=:created_at, updated_at=:updated_at
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


def update_user_diagnosis(
    user_id: int, result: str, score: int | None = None
) -> Optional[dict]:
    stored = result
    if score is not None and result:
        stored = json.dumps({"grade": result, "score": int(score)}, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET diagnosis_result = ? WHERE id = ?",
            (stored, user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def parse_diagnosis_result(raw: str | None) -> dict:
    if not raw:
        return {"result": None, "score": None}
    text = str(raw).strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            grade = data.get("grade") or data.get("result")
            score = data.get("score")
            if score is not None:
                score = int(score)
            return {"result": grade, "score": score}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return {"result": text, "score": None}


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


def record_visit(
    user_id: Optional[int] = None,
    *,
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    landing_page: str | None = None,
) -> None:
    visited_at = now_iso()
    with get_conn() as conn:
        if _visits_has_tracking_columns(conn):
            conn.execute(
                """
                INSERT INTO visits (
                    user_id, visited_at, referrer, utm_source,
                    utm_medium, utm_campaign, landing_page
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    visited_at,
                    (referrer or None),
                    (utm_source or None),
                    (utm_medium or None),
                    (utm_campaign or None),
                    (landing_page or None),
                ),
            )
        else:
            conn.execute(
                "INSERT INTO visits (user_id, visited_at) VALUES (?, ?)",
                (user_id, visited_at),
            )
        conn.commit()


def get_admin_stats() -> dict:
    today = today_kst()
    start, end = kst_day_utc_bounds(today)
    with get_conn() as conn:
        total_visits = conn.execute("SELECT COUNT(*) AS c FROM visits").fetchone()["c"]
        today_visits = conn.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE visited_at >= ? AND visited_at <= ?",
            (start, end),
        ).fetchone()["c"]
        logged_in_visits = conn.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE user_id IS NOT NULL"
        ).fetchone()["c"]
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        total_reviews = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
    return {
        "totalVisits": total_visits,
        "todayVisits": today_visits,
        "todayDate": today,
        "todayTimezone": "Asia/Seoul",
        "loggedInVisits": logged_in_visits,
        "totalUsers": total_users,
        "totalReviews": total_reviews,
    }


def get_admin_referrer_stats(date: str | None = None) -> dict:
    target = today_kst() if not date or date == "today" else date.strip()
    start, end = kst_day_utc_bounds(target)
    buckets: dict[str, int] = {}
    other_details: dict[str, int] = {}

    with get_conn() as conn:
        if not _visits_has_tracking_columns(conn):
            return {"date": target, "timezone": "Asia/Seoul", "breakdown": []}
        rows = conn.execute(
            """
            SELECT referrer, utm_source
            FROM visits
            WHERE visited_at >= ? AND visited_at <= ?
            """,
            (start, end),
        ).fetchall()

    for row in rows:
        category, detail = classify_visit_source(row["referrer"], row["utm_source"])
        buckets[category] = buckets.get(category, 0) + 1
        if category == "기타" and detail:
            other_details[detail] = other_details.get(detail, 0) + 1

    order = [
        "스레드",
        "인스타그램",
        "네이버",
        "구글 검색",
        "카카오톡",
        "직접 유입",
        "기타",
    ]

    def sort_key(item: tuple[str, int]) -> tuple[int, int]:
        name, count = item
        try:
            idx = order.index(name)
        except ValueError:
            idx = len(order)
        return (-count, idx)

    breakdown = []
    for name, count in sorted(buckets.items(), key=sort_key):
        entry: dict = {"source": name, "count": count}
        if name == "기타" and other_details:
            entry["detail"] = [
                f"{label} ({cnt})"
                for label, cnt in sorted(
                    other_details.items(), key=lambda x: (-x[1], x[0])
                )[:10]
            ]
        breakdown.append(entry)

    return {"date": target, "timezone": "Asia/Seoul", "breakdown": breakdown}


def get_persistence_info() -> dict:
    writable = False
    probe = DATA_DIR / ".write_probe"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        writable = probe.is_file()
        probe.unlink(missing_ok=True)
    except OSError:
        writable = False

    with get_conn() as conn:
        spot_count = conn.execute("SELECT COUNT(*) AS c FROM spots").fetchone()["c"]

    return {
        "dataDir": str(DATA_DIR),
        "dataDirWritable": writable,
        "dbExists": DB_PATH.is_file(),
        "dbPath": str(DB_PATH),
        "spotCount": spot_count,
        "persistentDiskExpected": str(DATA_DIR) == "/app/data",
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
