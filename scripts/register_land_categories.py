# -*- coding: utf-8 -*-
"""Register land-series spots via Kakao place_id (admin API). Ambiguous → needs_human_land.csv."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "").strip()
BASE = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")
KEY = (os.getenv("KAKAO_REST_KEY") or os.getenv("KAKAO_REST_API_KEY") or "").strip()

sys.stdout.reconfigure(encoding="utf-8")

# Confirmed Kakao place_id only. Unresolved listed in NEEDS_HUMAN below.
SPOTS = [
    {
        "name": "BAC센터 인수봉 암벽등반",
        "type": "rockClimbing",
        "tl": "자연 암벽등반",
        "em": "🧗",
        "bg": "#181208",
        "kakao_queries": ["블랙야크BAC센터", "BAC센터 우이동"],
        "prefer_place_id": "621524945",
        "thrillGrade": 4,
        "seasonStartMonth": 3,
        "seasonEndMonth": 11,
        "th": 4,
        "fp": 72,
        "sp2": 55,
        "ap": 76,
        "sp": 0,
        "br": "국내 암벽등반의 성지, 북한산 인수봉. 블랙야크 BAC센터 입문 교육과정으로 암장에 오른다. 콘크리트 벽이 아닌 진짜 바위에서 손목이 떨리는 맛.",
        "tags": ["#자연암벽", "#인수봉", "#BAC센터", "#블랙야크", "#성지"],
        "warns": [
            {"i": "⚠️", "tx": "시즌 3~11월 · 기상·암장 브리핑 후 진행", "t": "y"},
            {"i": "💀", "tx": "고소·낙석 대비 강사 지시 절대 준수", "t": "y"},
            {"i": "📅", "tx": "교육과정 사전 예약", "t": "g"},
        ],
    },
    {
        "name": "무주태권어드벤처",
        "type": "highRopes",
        "tl": "하이로프",
        "em": "🪢",
        "bg": "#0a1810",
        "kakao_queries": ["무주태권어드벤처"],
        "prefer_place_id": "800793776",
        "thrillGrade": 3,
        "seasonStartMonth": None,
        "seasonEndMonth": None,
        "th": 3,
        "fp": 62,
        "sp2": 60,
        "ap": 70,
        "sp": 0,
        "br": "짚라인+공중 로프코스 복합. 나무 사이로 매달린 하이로프에서 다리가 후들거리는 전북 무주. 체중 20~120kg 제한 — 체중 레인지 확인하고 올라가라.",
        "tags": ["#하이로프", "#무주", "#짚라인", "#태권어드벤처", "#체중제한"],
        "warns": [
            {"i": "⚠️", "tx": "체중 20~120kg 제한", "t": "y"},
            {"i": "📍", "tx": "고소공포·어지럼증 있으면 브리핑 때 고지", "t": "g"},
        ],
    },
    {
        "name": "관악산 모험숲",
        "type": "highRopes",
        "tl": "하이로프",
        "em": "🪢",
        "bg": "#0a1810",
        "kakao_queries": ["관악산모험숲", "관악산 모험숲"],
        "prefer_place_id": "1332885950",
        "thrillGrade": 2,
        "seasonStartMonth": 4,
        "seasonEndMonth": 11,
        "th": 2,
        "fp": 48,
        "sp2": 45,
        "ap": 58,
        "sp": 0,
        "br": "서울 관악산 자락 도심 하이로프. 어드벤처 21코스 — 입문용으로 딱 좋다. 매년 4~11월, 서울시 공공서비스 예약으로 굴러간다.",
        "tags": ["#하이로프", "#관악산", "#도심", "#모험숲", "#공공예약"],
        "warns": [
            {"i": "📅", "tx": "예약 권장 · 서울시 공공서비스 예약 / 현장 카드", "t": "y"},
            {"i": "⚠️", "tx": "시즌 4~11월 · 월·공휴일 휴장 여부 확인", "t": "g"},
        ],
        "_note": "관악구청 공식 안내 기준 4~11월 운영 확인",
    },
    {
        "name": "서대산드림리조트 서바이벌게임장",
        "type": "survivalGame",
        "tl": "서바이벌 게임",
        "em": "🪖",
        "bg": "#141808",
        "kakao_queries": ["서대산드림리조트"],
        "prefer_place_id": "7946418",
        "thrillGrade": 2,
        "seasonStartMonth": None,
        "seasonEndMonth": None,
        "th": 2,
        "fp": 55,
        "sp2": 50,
        "ap": 72,
        "sp": 0,
        "br": "충남 금산 서대산 자연 숲속 800평 대형 필드. 전면전·깃발전 — 팀이 뚫리면 심장이 먼저 뛴다. 교관 진행, 예약제로만 열린다.",
        "tags": ["#서바이벌", "#금산", "#서대산", "#예약필수", "#팀전도파민"],
        "warns": [
            {"i": "📅", "tx": "예약 필수 · 현장 즉석 이용 불가", "t": "y"},
            {"i": "⚠️", "tx": "단체(대략 50명대 패키지) 위주 · 사전 문의", "t": "y"},
            {"i": "🪖", "tx": "교관 브리핑·장비 지급 후 게임 진행", "t": "g"},
        ],
        "_note": "서바이벌 전용 POI 없음 → 활동지 리조트 place_id",
    },
]

NEEDS_HUMAN = [
    {
        "name": "도봉산 선인봉 원데이 암벽체험",
        "category": "자연 암벽등반",
        "region_hint": "서울 도봉산 선인봉",
        "grade": 4,
        "season": "3~11",
        "reason": "플랫폼 판매 원데이 강습 상품. 운영 업체 place_id 특정 불가. '선인봉'은 암장 자연지명만 존재.",
    },
    {
        "name": "철원 DMZ 서바이벌게임장",
        "category": "서바이벌 게임",
        "region_hint": "강원 철원",
        "grade": 2,
        "season": "연중",
        "reason": "DMZ 콘셉트 단일 업체로 특정 안 됨. 카카오에 'DMZ 서바이벌' 직접 POI 없음. 유사 레저업체 다수로 모호.",
    },
    {
        "name": "을왕리 서바이벌게임장",
        "category": "서바이벌 게임",
        "region_hint": "인천 을왕리",
        "grade": 2,
        "season": "연중",
        "reason": "카카오에 을왕리/영종도 서바이벌 게임장 전용 POI 없음. 리셀러·중개 페이지만 확인되어 place_id 확정 불가.",
    },
]


def resolve_place(client: httpx.Client, spot: dict) -> dict | None:
    prefer = spot.get("prefer_place_id")
    headers = {"Authorization": f"KakaoAK {KEY}"}
    for q in spot["kakao_queries"]:
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": q, "size": "15"},
            headers=headers,
            timeout=20,
        )
        docs = res.json().get("documents") or []
        if prefer:
            for d in docs:
                if str(d.get("id")) == str(prefer):
                    return d
            continue
        if docs:
            return docs[0]
    return None


def write_needs_human(extra: list[dict] | None = None) -> Path:
    path = ROOT / "scripts" / "needs_human_land.csv"
    rows = list(NEEDS_HUMAN)
    if extra:
        rows.extend(extra)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["name", "category", "region_hint", "grade", "season", "reason"],
            extrasaction="ignore",
        )
        w.writeheader()
        for n in rows:
            w.writerow(n)
    return path


def main() -> None:
    if not ADMIN_PASS or not KEY:
        raise SystemExit("ADMIN_PASSWORD / KAKAO key 필요")

    failed: list[dict] = []
    with httpx.Client(timeout=60) as client:
        existing = client.get(f"{BASE}/api/spots").json()
        by_name = {s["name"]: s for s in existing}

        for spot in SPOTS:
            print(f"\n=== {spot['name']} ===")
            if spot["name"] in by_name:
                print(f"  already exists id={by_name[spot['name']]['id']} — patch fields")
                ex = client.get(
                    f"{BASE}/api/spots/{by_name[spot['name']]['id']}",
                    headers={"X-Admin-Password": ADMIN_PASS},
                ).json()
                payload = {
                    **ex,
                    "thrillGrade": spot["thrillGrade"],
                    "seasonStartMonth": spot["seasonStartMonth"],
                    "seasonEndMonth": spot["seasonEndMonth"],
                    "coordVerified": True,
                    "type": spot["type"],
                    "tl": spot["tl"],
                    "br": spot["br"],
                    "tags": spot["tags"],
                    "warns": spot["warns"],
                }
                r = client.put(
                    f"{BASE}/api/spots/{ex['id']}",
                    headers={"X-Admin-Password": ADMIN_PASS, "Content-Type": "application/json"},
                    json=payload,
                )
                print(f"  update status={r.status_code}")
                continue

            place = resolve_place(client, spot)
            if not place:
                failed.append(
                    {
                        "name": spot["name"],
                        "category": spot["tl"],
                        "region_hint": "",
                        "grade": spot["thrillGrade"],
                        "season": f"{spot['seasonStartMonth']}-{spot['seasonEndMonth']}",
                        "reason": "카카오 place_id 확정 실패",
                    }
                )
                print("  FAIL: place resolve")
                continue

            addr = place.get("road_address_name") or place.get("address_name") or ""
            lat = float(place["y"])
            lng = float(place["x"])
            pid = str(place.get("id") or "")
            print(f"  kakao: {place.get('place_name')} | {addr} | id={pid}")
            if spot.get("prefer_place_id") and pid != str(spot["prefer_place_id"]):
                failed.append(
                    {
                        "name": spot["name"],
                        "category": spot["tl"],
                        "region_hint": addr,
                        "grade": spot["thrillGrade"],
                        "season": "",
                        "reason": f"place_id 불일치 prefer={spot['prefer_place_id']} got={pid}",
                    }
                )
                print("  FAIL: place_id mismatch")
                continue

            payload = {
                "name": spot["name"],
                "addr": addr,
                "lat": lat,
                "lng": lng,
                "type": spot["type"],
                "tl": spot["tl"],
                "em": spot["em"],
                "bg": spot["bg"],
                "th": spot["th"],
                "fp": spot["fp"],
                "sp2": spot["sp2"],
                "ap": spot["ap"],
                "sp": spot["sp"],
                "rank": "LAND",
                "br": spot["br"],
                "tags": spot["tags"],
                "warns": spot["warns"],
                "reviews": [],
                "img": "",
                "custom": True,
                "approved": True,
                "coordVerified": True,
                "kakaoPlaceId": pid,
                "thrillGrade": spot["thrillGrade"],
                "seasonStartMonth": spot["seasonStartMonth"],
                "seasonEndMonth": spot["seasonEndMonth"],
            }
            r = client.post(
                f"{BASE}/api/spots",
                headers={"X-Admin-Password": ADMIN_PASS, "Content-Type": "application/json"},
                json=payload,
            )
            print(f"  create status={r.status_code}")
            if r.status_code >= 400:
                print(r.text[:400])
                failed.append(
                    {
                        "name": spot["name"],
                        "category": spot["tl"],
                        "region_hint": addr,
                        "grade": spot["thrillGrade"],
                        "season": "",
                        "reason": f"API {r.status_code}",
                    }
                )
            else:
                created = r.json()
                print(
                    f"  OK id={created.get('id')} verified={created.get('coordVerified')} "
                    f"grade={created.get('thrillGrade')} season={created.get('seasonStartMonth')}-{created.get('seasonEndMonth')}"
                )

    path = write_needs_human(failed)
    print(f"\nneeds_human: {path}")
    print(f"  static unresolved: {len(NEEDS_HUMAN)}")
    print(f"  runtime failed: {len(failed)}")
    print(f"  registered attempts: {len(SPOTS)}")


if __name__ == "__main__":
    main()
