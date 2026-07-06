# -*- coding: utf-8
"""Tier C bungee #67/#68 dedup - update #68 and delete #67. Dry-run or apply."""

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

UPDATE_68 = {
    "id": 68,
    "name": "인제엑스게임리조트 번지점프",
    "addr": "강원특별자치도 인제군 인제읍 설악로 2254",
    "geocode_query": "강원특별자치도 인제군 인제읍 설악로 2254",
    "lat": 38.0776068,
    "lng": 128.1861031,
    "note": "venue_id=1 유지, #265와 동일 좌표",
}

DELETE_67 = {
    "id": 67,
    "name": "인제 내린천 번지점프",
    "reason": "#68과 동일 63m 번지 중복 (venue 미연결)",
}

VENUE1_SPOTS = [68, 261, 265]


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


def build_plan(client: httpx.Client, spots: dict[int, dict]) -> dict:
    fix = UPDATE_68
    current = spots.get(fix["id"]) or {}
    before = {
        "addr": current.get("addr"),
        "lat": current.get("lat"),
        "lng": current.get("lng"),
        "venueId": current.get("venueId"),
    }
    hit = kakao_geocode(client, fix["geocode_query"])
    time.sleep(0.15)
    after_lat = fix["lat"]
    after_lng = fix["lng"]
    geo_label = "manual (#265 match)"
    geo_source = "preset"
    if hit:
        after_lat, after_lng = hit["lat"], hit["lng"]
        geo_label = hit["label"]
        geo_source = hit["source"]
    rev = kakao_reverse(client, after_lat, after_lng)
    time.sleep(0.15)

    update_row = {
        "id": fix["id"],
        "name": fix["name"],
        "note": fix.get("note"),
        "before": before,
        "after": {
            "addr": fix["addr"],
            "lat": after_lat,
            "lng": after_lng,
        },
        "geocode_label": geo_label,
        "geocode_source": geo_source,
        "reverse_verify": rev,
    }

    del_item = DELETE_67
    cur67 = spots.get(del_item["id"]) or {}
    delete_row = {
        "id": del_item["id"],
        "name": del_item["name"],
        "reason": del_item["reason"],
        "before": {
            "addr": cur67.get("addr"),
            "lat": cur67.get("lat"),
            "lng": cur67.get("lng"),
            "venueId": cur67.get("venueId"),
        },
    }

    return {"update": update_row, "delete": delete_row}


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


def apply_delete(client: httpx.Client, spot_id: int) -> None:
    res = client.delete(
        f"{BASE}/api/spots/{spot_id}",
        headers={"X-Admin-Password": ADMIN_PASS},
        timeout=30.0,
    )
    res.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY missing")

    with httpx.Client() as client:
        spots = fetch_spots(client)
        plan = build_plan(client, spots)

    out = ROOT / "scripts" / "tier_c_bungee_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER C BUNGEE #67/#68 - DRY RUN")
    print("=" * 72)

    row = plan["update"]
    b, a = row["before"], row["after"]
    print(f"\n#{row['id']} {row['name']} [UPDATE]")
    if row.get("note"):
        print(f"  Note: {row['note']}")
    print(f"  BEFORE addr: {b.get('addr')}")
    print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
    print(f"  BEFORE venueId: {b.get('venueId')}")
    print(f"  AFTER  addr: {a.get('addr')}")
    print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
    print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
    print(f"  Reverse pin: {row.get('reverse_verify')}")

    row = plan["delete"]
    b = row["before"]
    print(f"\n#{row['id']} {row['name']} [DELETE]")
    print(f"  Reason: {row.get('reason')}")
    print(f"  Current addr: {b.get('addr')}")
    print(f"  Current pin:  {b.get('lat')}, {b.get('lng')}")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            existing = spots.get(plan["update"]["id"])
            if not existing:
                raise SystemExit("Spot #68 not found")
            apply_update(client, existing, plan["update"]["after"])
            print(f"  OK UPDATE #{plan['update']['id']} {plan['update']['name']}")
            apply_delete(client, plan["delete"]["id"])
            print(f"  OK DELETE #{plan['delete']['id']} {plan['delete']['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_c_bungee.py --apply")


if __name__ == "__main__":
    main()
