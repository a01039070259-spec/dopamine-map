# -*- coding: utf-8 -*-
"""Tier A spot coordinate fixes — dry-run or apply via production admin API."""

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
        "id": 77,
        "name": "제주 패러글라이딩",
        "addr": "제주특별자치도 제주시 한림읍 한창로 1295",
        "geocode_query": "제주특별자치도 제주시 한림읍 한창로 1295",
        "lat": None,
        "lng": None,
    },
    {
        "id": 69,
        "name": "성남 분당 율동공원 번지점프",
        "addr": "경기도 성남시 분당구 문정로 72",
        "geocode_query": "경기도 성남시 분당구 문정로 72",
        "lat": None,
        "lng": None,
    },
    {
        "id": 233,
        "name": "영도실탄사격장",
        "addr": "부산광역시 영도구 절영로 319",
        "geocode_query": None,
        "lat": 35.0735,
        "lng": 129.0541,
    },
    {
        "id": 2,
        "name": "부여 열기구",
        "addr": "충청남도 부여군 부여읍 성왕로173번길 12",
        "geocode_query": "충청남도 부여군 부여읍 성왕로173번길 12",
        "lat": None,
        "lng": None,
    },
    {
        "id": 8,
        "name": "남원 K1 항공교육원",
        "addr": "전라북도 남원시 요천로 2272",
        "geocode_query": "전라북도 남원시 요천로 2272",
        "lat": None,
        "lng": None,
    },
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
            return "(역지오코딩 실패)"
        docs = res.json().get("documents") or []
        if not docs:
            return "(결과 없음)"
        doc = docs[0]
        road = doc.get("road_address") or {}
        jibun = doc.get("address") or {}
        parts = [
            road.get("address_name"),
            road.get("building_name"),
            jibun.get("address_name"),
        ]
        return " ".join(p for p in parts if p)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return "(역지오코딩 오류)"


def fetch_spot(client: httpx.Client, spot_id: int) -> dict | None:
    try:
        res = client.get(f"{BASE}/api/spots/{spot_id}", timeout=30.0)
        if res.status_code == 200:
            return res.json()
    except httpx.HTTPError:
        pass
    # list fallback
    res = client.get(f"{BASE}/api/spots", timeout=60.0)
    res.raise_for_status()
    for s in res.json():
        if s.get("id") == spot_id:
            return s
    return None


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


def build_plan(client: httpx.Client) -> list[dict]:
    plan: list[dict] = []
    for fix in FIXES:
        current = fetch_spot(client, fix["id"]) or {}
        if fix["lat"] is not None and fix["lng"] is not None:
            new_lat, new_lng = fix["lat"], fix["lng"]
            geo_label = "manual"
            geo_source = "audit_suggestion"
        else:
            hit = kakao_geocode(client, fix["geocode_query"] or fix["addr"])
            time.sleep(0.15)
            if not hit:
                plan.append(
                    {
                        "id": fix["id"],
                        "name": fix["name"],
                        "error": f"지오코딩 실패: {fix['geocode_query']}",
                        "before": {
                            "addr": current.get("addr"),
                            "lat": current.get("lat"),
                            "lng": current.get("lng"),
                        },
                    }
                )
                continue
            new_lat, new_lng = hit["lat"], hit["lng"]
            geo_label = hit["label"]
            geo_source = hit["source"]

        rev = kakao_reverse(client, new_lat, new_lng)
        time.sleep(0.15)

        plan.append(
            {
                "id": fix["id"],
                "name": fix["name"],
                "before": {
                    "addr": current.get("addr"),
                    "lat": current.get("lat"),
                    "lng": current.get("lng"),
                },
                "after": {
                    "addr": fix["addr"],
                    "lat": new_lat,
                    "lng": new_lng,
                },
                "geocode_label": geo_label,
                "geocode_source": geo_source,
                "reverse_verify": rev,
            }
        )
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes to production API")
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY missing")

    with httpx.Client() as client:
        plan = build_plan(client)

    out = ROOT / "scripts" / "tier_a_coordinate_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER A COORDINATE FIX - DRY RUN")
    print("=" * 72)
    for row in plan:
        if row.get("error"):
            print(f"\n#{row['id']} {row['name']} - ERROR: {row['error']}")
            continue
        b, a = row["before"], row["after"]
        print(f"\n#{row['id']} {row['name']}")
        print(f"  BEFORE addr: {b.get('addr')}")
        print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
        print(f"  AFTER  addr: {a.get('addr')}")
        print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
        print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
        print(f"  Reverse pin: {row.get('reverse_verify')}")

    errors = [r for r in plan if r.get("error")]
    if errors:
        print(f"\n{len(errors)} item(s) failed geocoding — not applying those.")
        if args.apply:
            raise SystemExit(1)

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            for row in plan:
                if row.get("error"):
                    continue
                existing = fetch_spot(client, row["id"])
                if not existing:
                    raise SystemExit(f"Spot #{row['id']} not found")
                a = row["after"]
                changes = {"addr": a["addr"], "lat": a["lat"], "lng": a["lng"]}
                apply_fix(client, existing, changes)
                print(f"  OK #{row['id']} {row['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_a_coordinates.py --apply")


if __name__ == "__main__":
    main()
