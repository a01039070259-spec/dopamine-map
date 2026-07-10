# -*- coding: utf-8 -*-
"""스팟 좌표 전수 검증 — 카카오 로컬 API 대조 리포트 (읽기 전용, DB 수정 없음).

검색 fallback 순서 (이름 계열만 사용, 주소 검색은 검증에 쓰지 않음):
    1) 스팟 이름 키워드 검색
    2) 소속 venue 이름 키워드 검색
    3) 스팟 이름 축약형(괄호/부속시설 접미어 제거) 키워드 검색
    전부 실패 → D그룹(검증불가)

주소 검색을 fallback으로 쓰지 않는 이유: 주소 필드 자체가 오염됐을 수 있어
(예: 단양 케이스 — 군청 주소로 등록) 오염된 주소로 검증하면 오류를 정상으로
판정하게 된다.

사용법:
    python scripts/verify_coords.py               # 로컬 SQLite DB 기준
    python scripts/verify_coords.py --source api  # 프로덕션 API 기준

환경변수:
    KAKAO_REST_KEY   카카오 REST API 키 (없으면 KAKAO_REST_API_KEY로 fallback)
    SPOTS_API_URL    --source api일 때 스팟 목록 URL (기본: 프로덕션)
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KAKAO_KEY = (os.getenv("KAKAO_REST_KEY") or os.getenv("KAKAO_REST_API_KEY") or "").strip()
SPOTS_API_URL = os.getenv("SPOTS_API_URL", "https://dopamine-map.onrender.com/api/spots")
VENUES_API_URL = os.getenv("VENUES_API_URL", "https://dopamine-map.onrender.com/api/venues")
REQUEST_DELAY_SEC = 0.2

THRESHOLD_SUSPECT_KM = 1.0   # A그룹: 초과 시 좌표 오류 확실 후보
THRESHOLD_REVIEW_KM = 0.3    # B그룹: 300m~1km 수동 확인

CSV_PATH = ROOT / "scripts" / "coord_audit.csv"

# 스팟 이름 끝에 붙는 부속 시설/체험 접미어 — 축약형 재검색 시 제거
FACILITY_SUFFIXES = (
    "짚와이어",
    "짚라인",
    "짚트랙",
    "집와이어",
    "집라인",
    "번지점프",
    "번지",
    "슬링샷",
    "알파인코스터",
    "마운틴코스터",
    "모노레일",
    "스카이워크",
    "스카이바이크",
    "루지",
    "카트",
    "ATV",
    "서바이벌",
    "패러글라이딩",
    "행글라이더",
    "열기구",
    "제트보트",
    "씨워킹",
    "요트",
    "체험장",
    "체험존",
    "체험",
    "탑승장",
)


def resolve_db_path() -> Path:
    raw = os.getenv("DOPAMINE_DATA_DIR", "").strip()
    data_dir = Path(raw) if raw else ROOT / "data"
    return data_dir / "dopamine.db"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def shorten_name(name: str) -> str:
    """괄호 내용과 부속 시설 접미어를 제거한 축약형.

    예: '단양 만천하스카이워크 짚와이어' -> '단양 만천하스카이워크'
        '하동 코리아 짚와이어 금오산'   -> (접미어가 중간이라 그대로)
        '강촌 ATV·카트·서바이벌 체험장(본점)' -> '강촌'
    """
    s = re.sub(r"[\(（][^\)）]*[\)）]", " ", name or "").strip()
    tokens = s.split()
    while tokens:
        last = tokens[-1]
        stripped = None
        for suffix in FACILITY_SUFFIXES:
            if last == suffix:
                stripped = ""
                break
            if last.endswith(suffix) and len(last) > len(suffix):
                head = last[: -len(suffix)]
                # '만천하스카이워크'처럼 고유명+접미어 결합이면 고유명은 남긴다
                stripped = head if len(head) >= 2 else ""
                break
        if stripped is None:
            break
        if stripped:
            tokens[-1] = stripped
            break
        tokens.pop()
    # ·/・ 로 연결된 시설 나열 제거 후 남은 잔여물 정리
    result = " ".join(t for t in tokens if t not in ("·", "・", "-"))
    return result.strip()


def load_spots_from_db() -> tuple[list[dict], dict[int, str]]:
    db_path = resolve_db_path()
    if not db_path.is_file():
        raise SystemExit(f"DB 파일이 없습니다: {db_path} (프로덕션 검증은 --source api)")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(spots)").fetchall()}
        venue_col = ", venue_id" if "venue_id" in cols else ""
        rows = conn.execute(
            f"SELECT id, name, addr, lat, lng{venue_col} FROM spots ORDER BY id"
        ).fetchall()
        venue_names: dict[int, str] = {}
        has_venues = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venues'"
        ).fetchone()
        if has_venues:
            for r in conn.execute("SELECT id, name FROM venues").fetchall():
                venue_names[r["id"]] = r["name"]
    finally:
        conn.close()
    spots = []
    for r in rows:
        d = dict(r)
        d["venueId"] = d.pop("venue_id", None)
        spots.append(d)
    return spots, venue_names


def load_spots_from_api() -> tuple[list[dict], dict[int, str]]:
    res = httpx.get(SPOTS_API_URL, timeout=90.0)
    res.raise_for_status()
    spots = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "addr": s.get("addr"),
            "lat": s.get("lat"),
            "lng": s.get("lng"),
            "venueId": s.get("venueId"),
        }
        for s in res.json()
    ]
    venue_names: dict[int, str] = {}
    res = httpx.get(VENUES_API_URL, timeout=90.0)
    if res.status_code == 200:
        for v in res.json():
            if not v.get("virtual"):
                venue_names[v["id"]] = v.get("name") or ""
    return spots, venue_names


def kakao_search_keyword(client: httpx.Client, query: str) -> dict | None:
    """키워드(장소명) 검색. 최상위 결과 반환."""
    if not (query or "").strip():
        return None
    try:
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": query.strip(), "size": "1"},
        )
        if res.status_code >= 400:
            return None
        docs = res.json().get("documents") or []
        if not docs:
            return None
        doc = docs[0]
        return {
            "lat": float(doc["y"]),
            "lng": float(doc["x"]),
            "place": doc.get("place_name") or "",
            "addr": doc.get("road_address_name") or doc.get("address_name") or "",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def search_with_fallbacks(
    client: httpx.Client, spot: dict, venue_names: dict[int, str]
) -> tuple[dict | None, str]:
    """(결과, 검색어 출처) 반환. 이름 계열 검색만 사용."""
    name = (spot.get("name") or "").strip()

    hit = kakao_search_keyword(client, name)
    time.sleep(REQUEST_DELAY_SEC)
    if hit:
        return hit, "spot_name"

    venue_id = spot.get("venueId")
    venue_name = (venue_names.get(venue_id) or "").strip() if venue_id else ""
    if venue_name and venue_name != name:
        hit = kakao_search_keyword(client, venue_name)
        time.sleep(REQUEST_DELAY_SEC)
        if hit:
            return hit, f"venue_name({venue_name})"

    short = shorten_name(name)
    if short and short != name and short != venue_name:
        hit = kakao_search_keyword(client, short)
        time.sleep(REQUEST_DELAY_SEC)
        if hit:
            return hit, f"short_name({short})"

    return None, ""


def audit(
    spots: list[dict], venue_names: dict[int, str]
) -> tuple[list[dict], list[dict], list[dict]]:
    group_a: list[dict] = []  # >1km
    group_b: list[dict] = []  # 300m ~ 1km
    group_d: list[dict] = []  # 이름 계열 검색 전부 실패 — 검증불가

    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    with httpx.Client(timeout=20.0, headers=headers) as client:
        for i, spot in enumerate(spots, 1):
            hit, query_source = search_with_fallbacks(client, spot, venue_names)

            row = {
                "spot_id": spot.get("id"),
                "name": spot.get("name") or "",
                "db_lat": spot.get("lat"),
                "db_lng": spot.get("lng"),
                "kakao_lat": hit["lat"] if hit else "",
                "kakao_lng": hit["lng"] if hit else "",
                "distance_km": "",
                "kakao_place": hit["place"] if hit else "",
                "kakao_addr": hit["addr"] if hit else "",
                "kakao_source": query_source,
                "db_addr": spot.get("addr") or "",
            }

            if not hit:
                row["group"] = "D"
                group_d.append(row)
            else:
                try:
                    d = haversine_km(
                        float(spot["lat"]), float(spot["lng"]), hit["lat"], hit["lng"]
                    )
                except (TypeError, ValueError):
                    d = None
                if d is None:
                    row["group"] = "A"
                    group_a.append(row)
                else:
                    row["distance_km"] = round(d, 3)
                    if d > THRESHOLD_SUSPECT_KM:
                        row["group"] = "A"
                        group_a.append(row)
                    elif d >= THRESHOLD_REVIEW_KM:
                        row["group"] = "B"
                        group_b.append(row)

            if i % 20 == 0:
                print(
                    f"  ... {i}/{len(spots)} 검사 (A={len(group_a)} B={len(group_b)} D={len(group_d)})"
                )

    group_a.sort(key=lambda r: -(r["distance_km"] if isinstance(r["distance_km"], float) else 9999))
    return group_a, group_b, group_d


def print_group(title: str, rows: list[dict]) -> None:
    print()
    print("=" * 100)
    print(f"{title} — {len(rows)}건")
    print("=" * 100)
    if not rows:
        print("(없음)")
        return
    for r in rows:
        dist = f"{r['distance_km']}km" if r["distance_km"] != "" else "거리계산불가"
        kakao_pt = f"{r['kakao_lat']}, {r['kakao_lng']}" if r["kakao_lat"] != "" else "-"
        print(
            f"#{r['spot_id']:>4} {r['name'][:28]:<30} "
            f"DB=({r['db_lat']}, {r['db_lng']}) 카카오=({kakao_pt}) {dist}"
        )
        found = f"{r['kakao_place']} / {r['kakao_addr']}".strip(" /")
        if found:
            print(f"      └ 카카오 검색결과: {found} [{r['kakao_source']}]")


def write_csv(rows: list[dict]) -> None:
    fields = [
        "group",
        "spot_id",
        "name",
        "db_lat",
        "db_lng",
        "kakao_lat",
        "kakao_lng",
        "distance_km",
        "kakao_place",
        "kakao_addr",
        "kakao_source",
        "db_addr",
    ]
    # utf-8-sig: 엑셀에서 한글 깨짐 방지
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="스팟 좌표 검증 리포트 (읽기 전용)")
    parser.add_argument(
        "--source",
        choices=["db", "api"],
        default="db",
        help="db=로컬 SQLite(기본), api=프로덕션 API",
    )
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_KEY 환경변수가 필요합니다 (.env의 KAKAO_REST_API_KEY도 인식)")

    if args.source == "db":
        spots, venue_names = load_spots_from_db()
    else:
        spots, venue_names = load_spots_from_api()
    print(f"스팟 {len(spots)}개 로드 (source={args.source}, venue {len(venue_names)}개)")

    group_a, group_b, group_d = audit(spots, venue_names)

    print_group("[A] 거리 1km 초과 — 좌표 오류 확실 후보 (거리 내림차순)", group_a)
    print_group("[B] 거리 300m~1km — 애매, 수동 확인 필요", group_b)
    print_group("[D] 이름 계열 검색 전부 실패 — 검증불가 (이름/주소 재확인 필요)", group_d)

    write_csv(group_a + group_b + group_d)
    print()
    print(f"CSV 저장: {CSV_PATH}")
    print(f"요약: 전체 {len(spots)} / A={len(group_a)} / B={len(group_b)} / D={len(group_d)}")
    print("※ 이 스크립트는 리포트만 생성하며 DB를 수정하지 않습니다.")


if __name__ == "__main__":
    main()
