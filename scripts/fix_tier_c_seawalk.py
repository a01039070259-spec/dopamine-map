# -*- coding: utf-8
"""Tier C seawalk #11/#12 dedup - update #12 and delete #11. Dry-run or apply."""

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

UPDATE_12 = {
    "id": 12,
    "name": "제주 함덕 언더워터플레이",
    "addr": "제주특별자치도 제주시 조천읍 조함해안로 321-21",
    "geocode_query": "제주특별자치도 제주시 조천읍 조함해안로 321-21",
    "lat": 33.5514138,
    "lng": 126.6527429,
    "br": "함덕해수욕장 근처 국제리더스클럽 바다 씨워킹. 에메랄드 바다 속 보행.",
    "note": "venue_id=null 유지, 공식 바다 씨워킹 지점",
}

DELETE_11 = {
    "id": 11,
    "name": "제주 김녕 언더워터플레이",
    "reason": "김녕 바다 씨워킹 실존 근거 없음, #12와 동일 업체·상품 중복",
}


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
    fix = UPDATE_12
    current = spots.get(fix["id"]) or {}
    before = {
        "addr": current.get("addr"),
        "lat": current.get("lat"),
        "lng": current.get("lng"),
        "br": current.get("br"),
        "venueId": current.get("venueId"),
    }
    hit = kakao_geocode(client, fix["geocode_query"])
    time.sleep(0.15)
    after_lat = fix["lat"]
    after_lng = fix["lng"]
    geo_label = "manual (approved coords)"
    geo_source = "preset"
    if hit:
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
            "br": fix["br"],
        },
        "geocode_label": geo_label,
        "geocode_source": geo_source,
        "reverse_verify": rev,
    }

    del_item = DELETE_11
    cur11 = spots.get(del_item["id"]) or {}
    delete_row = {
        "id": del_item["id"],
        "name": del_item["name"],
        "reason": del_item["reason"],
        "before": {
            "addr": cur11.get("addr"),
            "lat": cur11.get("lat"),
            "lng": cur11.get("lng"),
            "br": cur11.get("br"),
            "venueId": cur11.get("venueId"),
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

    out = ROOT / "scripts" / "tier_c_seawalk_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER C SEAWALK #11/#12 - DRY RUN")
    print("=" * 72)

    row = plan["update"]
    b, a = row["before"], row["after"]
    print(f"\n#{row['id']} {row['name']} [UPDATE]")
    if row.get("note"):
        print(f"  Note: {row['note']}")
    print(f"  BEFORE addr: {b.get('addr')}")
    print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
    print(f"  BEFORE br:   {b.get('br')}")
    print(f"  BEFORE venueId: {b.get('venueId')}")
    print(f"  AFTER  addr: {a.get('addr')}")
    print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
    print(f"  AFTER  br:   {a.get('br')}")
    print(f"  Geocode:     {row.get('geocode_label')} ({row.get('geocode_source')})")
    print(f"  Reverse pin: {row.get('reverse_verify')}")

    row = plan["delete"]
    b = row["before"]
    print(f"\n#{row['id']} {row['name']} [DELETE]")
    print(f"  Reason: {row.get('reason')}")
    print(f"  Current addr: {b.get('addr')}")
    print(f"  Current pin:  {b.get('lat')}, {b.get('lng')}")
    print(f"  Current br:   {b.get('br')}")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            existing = spots.get(plan["update"]["id"])
            if not existing:
                raise SystemExit("Spot #12 not found")
            apply_update(client, existing, plan["update"]["after"])
            print(f"  OK UPDATE #{plan['update']['id']} {plan['update']['name']}")
            apply_delete(client, plan["delete"]["id"])
            print(f"  OK DELETE #{plan['delete']['id']} {plan['delete']['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_c_seawalk.py --apply")


if __name__ == "__main__":
    main()
