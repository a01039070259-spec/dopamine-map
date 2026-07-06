# -*- coding: utf-8
"""Tier C remaining batch (9 spots) - coordinate fixes. Dry-run or apply."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY", "").strip()
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "1111")
BASE = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")

FIXES = [
    {
        "id": 15,
        "name": "동해 도째비골 스카이밸리",
        "geocode_query": "강원특별자치도 동해시 묵호진동 2-109",
        "addr": "강원특별자치도 동해시 묵호진동 2-109",
    },
    {
        "id": 19,
        "name": "무등산 모노레일",
        "geocode_query": "광주광역시 동구 지산유원지",
        "addr": "광주광역시 동구 지산동 지산유원지",
    },
    {
        "id": 24,
        "name": "포항 환호공원 스페이스워크",
        "geocode_query": "경상북도 포항시 북구 환호공원길 30",
        "addr": "경상북도 포항시 북구 환호공원길 30",
    },
    {
        "id": 27,
        "name": "홍성 남당항 네트어드벤처",
        "geocode_query": "충청남도 홍성군 서부면 남당항로 171",
        "addr": "충청남도 홍성군 서부면 남당항로 171",
    },
    {
        "id": 14,
        "name": "함안 입곡군립공원 하늘자전거",
        "geocode_query": "함안 입곡군립공원",
        "addr": "경상남도 함안군 산인면 입곡리 1181-1",
        "note": "칠원읍 아님 — 실제는 산인면 입곡저수지 일대",
    },
    {
        "id": 6,
        "name": "공주 비행마을",
        "geocode_query": "충청남도 공주시 의당면 수촌리 945",
        "addr": "충청남도 공주시 의당면 수촌리 945",
    },
    {
        "id": 10,
        "name": "담양 에어로마스터",
        "geocode_query": "에어로마스터 담양비행장",
        "addr": "전라남도 담양군 금성면 담순로 156-46",
        "note": "금성면 석현리 640 = 동일 시설",
    },
    {
        "id": 9,
        "name": "원주 성주항공",
        "geocode_query": "강원특별자치도 원주시 문막읍 견훤로 941-21",
        "addr": "강원특별자치도 원주시 문막읍 견훤로 941-21",
        "note": "핀은 기존과 동일, 주소 placeholder 보정",
    },
    {
        "id": 246,
        "name": "엑스포마린 제트보트",
        "geocode_query": "전라남도 여수시 오동도로 61-13",
        "addr": "전라남도 여수시 오동도로 61-13",
        "note": "여수 베네치아 호텔 앞 선착장",
    },
]


def kakao_geocode(client: httpx.Client, query: str) -> dict | None:
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    for path, params in (
        ("search/address.json", {"query": query}),
        ("search/keyword.json", {"query": query, "size": "5"}),
    ):
        try:
            res = client.get(
                f"https://dapi.kakao.com/v2/local/{path}",
                params=params,
                headers=headers,
                timeout=20.0,
            )
            if res.status_code >= 400:
                continue
            docs = res.json().get("documents") or []
            if not docs:
                continue
            doc = docs[0]
            return {
                "lat": round(float(doc["y"]), 7),
                "lng": round(float(doc["x"]), 7),
                "label": doc.get("place_name") or doc.get("address_name") or query,
                "source": path,
                "raw_address": doc.get("address_name") or doc.get("road_address_name"),
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            continue
    return None


def kakao_reverse(client: httpx.Client, lat: float, lng: float) -> str:
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    try:
        res = client.get(
            "https://dapi.kakao.com/v2/local/geo/coord2address.json",
            params={"x": lng, "y": lat},
            headers=headers,
            timeout=20.0,
        )
        if res.status_code >= 400:
            return "(reverse geocode failed)"
        docs = res.json().get("documents") or []
        if not docs:
            return "(no result)"
        doc = docs[0]
        road = doc.get("road_address") or {}
        jibun = doc.get("address") or {}
        parts = [
            road.get("address_name"),
            road.get("building_name"),
            jibun.get("address_name"),
        ]
        return " | ".join(p for p in parts if p)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return "(reverse geocode error)"


def fetch_spots(client: httpx.Client) -> dict[int, dict]:
    res = client.get(f"{BASE}/api/spots", timeout=60.0)
    res.raise_for_status()
    return {s["id"]: s for s in res.json()}


def build_plan(client: httpx.Client, spots: dict[int, dict]) -> list[dict]:
    rows = []
    for fix in FIXES:
        current = spots.get(fix["id"]) or {}
        hit = kakao_geocode(client, fix["geocode_query"])
        time.sleep(0.15)
        if not hit:
            rows.append({
                "id": fix["id"],
                "name": fix["name"],
                "error": f"geocode failed: {fix['geocode_query']}",
                "before": {
                    "addr": current.get("addr"),
                    "lat": current.get("lat"),
                    "lng": current.get("lng"),
                    "venueId": current.get("venueId"),
                },
            })
            continue
        rev = kakao_reverse(client, hit["lat"], hit["lng"])
        time.sleep(0.15)
        rows.append({
            "id": fix["id"],
            "name": fix["name"],
            "note": fix.get("note"),
            "geocode_query": fix["geocode_query"],
            "before": {
                "addr": current.get("addr"),
                "lat": current.get("lat"),
                "lng": current.get("lng"),
                "venueId": current.get("venueId"),
            },
            "after": {
                "addr": fix["addr"],
                "lat": hit["lat"],
                "lng": hit["lng"],
            },
            "geocode_label": hit["label"],
            "geocode_source": hit["source"],
            "geocode_raw": hit.get("raw_address"),
            "reverse_verify": rev,
        })
    return rows


def apply_update(client: httpx.Client, existing: dict, changes: dict) -> dict:
    payload = {**existing, **changes}
    payload.setdefault("warns", [])
    payload.setdefault("reviews", [])
    payload.setdefault("img", "")
    res = client.put(
        f"{BASE}/api/spots/{existing['id']}",
        headers={"X-Admin-Password": ADMIN_PASS, "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    res.raise_for_status()
    return res.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY missing")

    with httpx.Client() as client:
        spots = fetch_spots(client)
        plan = build_plan(client, spots)

    out = ROOT / "scripts" / "tier_c_batch7_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER C REMAINING BATCH (9 spots) - DRY RUN")
    print("=" * 72)

    for row in plan:
        print(f"\n#{row['id']} {row['name']}")
        if row.get("error"):
            print(f"  ERROR: {row['error']}")
            continue
        if row.get("note"):
            print(f"  Note: {row['note']}")
        b, a = row["before"], row["after"]
        print(f"  Query:       {row.get('geocode_query')}")
        print(f"  BEFORE addr: {b.get('addr')}")
        print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
        print(f"  BEFORE venueId: {b.get('venueId')}")
        print(f"  AFTER  addr: {a.get('addr')}")
        print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
        print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
        print(f"  Reverse pin: {row.get('reverse_verify')}")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            for row in plan:
                if row.get("error"):
                    print(f"  SKIP #{row['id']} (geocode failed)")
                    continue
                existing = spots.get(row["id"])
                if not existing:
                    print(f"  SKIP #{row['id']} (not found)")
                    continue
                apply_update(client, existing, row["after"])
                print(f"  OK UPDATE #{row['id']} {row['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_c_batch7.py --apply")


if __name__ == "__main__":
    main()
