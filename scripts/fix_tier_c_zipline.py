# -*- coding: utf-8 -*-
"""Tier C zipline spots - address/coordinate fixes. Dry-run or apply."""

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

UPDATES = [
    {
        "id": 59,
        "name": "창원 짚라인",
        "addr": "경상남도 창원시 진해구 명동로 62",
        "geocode_query": "경상남도 창원시 진해구 명동로 62",
        "note": "진해해양공원 내",
    },
    {
        "id": 60,
        "name": "문경 짚라인",
        "addr": "경상북도 문경시 불정길 174",
        "geocode_query": "경상북도 문경시 불정길 174",
    },
    {
        "id": 61,
        "name": "충주 짚라인",
        "addr": "충청북도 충주시 노은면 우성1길 191",
        "geocode_query": "충청북도 충주시 노은면 우성1길 191",
        "note": "문성자연휴양림",
    },
    {
        "id": 65,
        "name": "영천 짚라인",
        "addr": "경상북도 영천시 화북면 배나무정길 196",
        "geocode_query": "경상북도 영천시 화북면 배나무정길 196",
        "note": "보현산댐 짚와이어",
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
    for fix in UPDATES:
        current = spots.get(fix["id"]) or {}
        before = {
            "addr": current.get("addr"),
            "lat": current.get("lat"),
            "lng": current.get("lng"),
        }
        hit = kakao_geocode(client, fix["geocode_query"])
        time.sleep(0.15)
        if not hit:
            plan.append(
                {
                    "id": fix["id"],
                    "name": fix["name"],
                    "error": f"geocode failed: {fix['geocode_query']}",
                    "before": before,
                }
            )
            continue
        rev = kakao_reverse(client, hit["lat"], hit["lng"])
        time.sleep(0.15)
        plan.append(
            {
                "id": fix["id"],
                "name": fix["name"],
                "note": fix.get("note"),
                "before": before,
                "after": {
                    "addr": fix["addr"],
                    "lat": hit["lat"],
                    "lng": hit["lng"],
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
    parser.add_argument("--spot-id", type=int, default=None)
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY missing")

    with httpx.Client() as client:
        spots = fetch_spots(client)
        plan = build_plan(client, spots)

    if args.spot_id is not None:
        plan = [r for r in plan if r["id"] == args.spot_id]
        if not plan:
            raise SystemExit(f"spot-id {args.spot_id} not in Tier C zipline plan")

    out = ROOT / "scripts" / "tier_c_zipline_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER C ZIPLINE - DRY RUN")
    print("=" * 72)

    for row in plan:
        if row.get("error"):
            print(f"\n#{row['id']} {row['name']} - ERROR: {row['error']}")
            continue
        b, a = row["before"], row["after"]
        print(f"\n#{row['id']} {row['name']} [UPDATE]")
        if row.get("note"):
            print(f"  Note: {row['note']}")
        print(f"  BEFORE addr: {b.get('addr')}")
        print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
        print(f"  AFTER  addr: {a.get('addr')}")
        print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
        print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
        print(f"  Reverse pin: {row.get('reverse_verify')}")

    errors = [r for r in plan if r.get("error")]
    if errors and args.apply:
        raise SystemExit(f"{len(errors)} geocode failure(s)")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            for row in plan:
                if row.get("error"):
                    continue
                existing = spots.get(row["id"])
                if not existing:
                    raise SystemExit(f"Spot #{row['id']} not found")
                apply_fix(client, existing, row["after"])
                print(f"  OK #{row['id']} {row['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_c_zipline.py --apply")


if __name__ == "__main__":
    main()
