# -*- coding: utf-8 -*-
"""Tier B paragliding coordinate fixes - dry-run or apply via production admin API."""

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
        "id": 74,
        "name": "단양 패러글라이딩",
        "addr": "충청북도 단양군 가곡면 사평리 246-33",
        "geocode_query": "충청북도 단양군 가곡면 사평리 246-33",
        "skip_geocode": False,
    },
    {
        "id": 75,
        "name": "양평 패러글라이딩",
        "addr": "경기도 양평군 옥천면 신촌길 80",
        "geocode_query": "경기도 양평군 옥천면 신촌길 80",
        "skip_geocode": False,
    },
    {
        "id": 76,
        "name": "포항 패러글라이딩",
        "addr": "경상북도 포항시 북구 흥해읍 해안로 1366-42",
        "geocode_query": "경상북도 포항시 북구 흥해읍 해안로 1366-42",
        "skip_geocode": False,
    },
    {
        "id": 1,
        "name": "여수 국가대표 패러글라이딩",
        "addr": "전라남도 여수시 망양로 225",
        "geocode_query": "전라남도 여수시 망양로 225",
        "skip_geocode": False,
    },
    {
        "id": 79,
        "name": "남해 패러글라이딩",
        "addr": "경상남도 남해군 서면 남서대로2197번길 64-20",
        "geocode_query": "경상남도 남해군 서면 남서대로2197번길 64-20",
        "skip_geocode": False,
    },
    {
        "id": 81,
        "name": "영월 패러글라이딩",
        "addr": "강원특별자치도 영월군 영월읍",
        "geocode_query": "강원특별자치도 영월군 영월읍",
        "skip_geocode": False,
        "note": "별마로천문대 인근 - 상세 지번 보류, 읍 단위만 반영",
    },
    {
        "id": 87,
        "name": "순천 벌교 패러글라이딩",
        "addr": None,
        "geocode_query": None,
        "skip_geocode": True,
        "note": "기존 주소/좌표 유지 (양호 판정)",
    },
]

DEFERRED = [
    {"id": 78, "name": "고창 패러글라이딩"},
    {"id": 80, "name": "담양 패러글라이딩"},
    {"id": 84, "name": "무주 덕유산 패러글라이딩"},
    {"id": 82, "name": "부산 영도 패러글라이딩"},
]


def kakao_geocode(client: httpx.Client, query: str) -> dict | None:
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    for path, params in (
        ("search/address.json", {"query": query}),
        ("search/keyword.json", {"query": query, "size": "3"}),
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
    plan: list[dict] = []
    for fix in FIXES:
        current = spots.get(fix["id"]) or {}
        before = {
            "addr": current.get("addr"),
            "lat": current.get("lat"),
            "lng": current.get("lng"),
        }

        if fix["skip_geocode"]:
            rev = kakao_reverse(client, float(before["lat"]), float(before["lng"]))
            time.sleep(0.15)
            plan.append(
                {
                    "id": fix["id"],
                    "name": fix["name"],
                    "action": "keep",
                    "note": fix.get("note"),
                    "before": before,
                    "after": before,
                    "reverse_verify": rev,
                }
            )
            continue

        hit = kakao_geocode(client, fix["geocode_query"] or fix["addr"])
        time.sleep(0.15)
        if not hit:
            plan.append(
                {
                    "id": fix["id"],
                    "name": fix["name"],
                    "action": "update",
                    "error": f"geocode failed: {fix['geocode_query']}",
                    "before": before,
                }
            )
            continue

        new_lat, new_lng = hit["lat"], hit["lng"]
        rev = kakao_reverse(client, new_lat, new_lng)
        time.sleep(0.15)

        plan.append(
            {
                "id": fix["id"],
                "name": fix["name"],
                "action": "update",
                "note": fix.get("note"),
                "before": before,
                "after": {
                    "addr": fix["addr"],
                    "lat": new_lat,
                    "lng": new_lng,
                },
                "geocode_label": hit["label"],
                "geocode_source": hit["source"],
                "reverse_verify": rev,
            }
        )
    return plan


def apply_fix(client: httpx.Client, existing: dict, changes: dict) -> dict:
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

    out = ROOT / "scripts" / "tier_b_paragliding_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER B PARAGLIDING FIX - DRY RUN")
    print("=" * 72)

    for row in plan:
        if row.get("error"):
            print(f"\n#{row['id']} {row['name']} - ERROR: {row['error']}")
            continue
        b, a = row["before"], row["after"]
        action = row.get("action", "update")
        print(f"\n#{row['id']} {row['name']} [{action.upper()}]")
        if row.get("note"):
            print(f"  Note: {row['note']}")
        print(f"  BEFORE addr: {b.get('addr')}")
        print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
        print(f"  AFTER  addr: {a.get('addr')}")
        print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
        if action == "update":
            print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
        print(f"  Reverse pin: {row.get('reverse_verify')}")

    print("\n" + "-" * 72)
    print("DEFERRED (no changes this round):")
    for d in DEFERRED:
        s = spots.get(d["id"], {})
        print(f"  #{d['id']} {d['name']} - {s.get('addr', '(not found)')}")

    errors = [r for r in plan if r.get("error")]
    if errors and args.apply:
        raise SystemExit(f"{len(errors)} geocode failure(s)")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            for row in plan:
                if row.get("error") or row.get("action") == "keep":
                    continue
                existing = spots.get(row["id"])
                if not existing:
                    raise SystemExit(f"Spot #{row['id']} not found")
                apply_fix(client, existing, row["after"])
                print(f"  OK #{row['id']} {row['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_b_paragliding.py --apply")


if __name__ == "__main__":
    main()
