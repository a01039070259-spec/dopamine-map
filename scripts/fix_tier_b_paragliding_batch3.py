# -*- coding: utf-8 -*-
"""Tier B paragliding batch 3 - remaining 4 deferred spots. Dry-run or apply."""

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
        "id": 84,
        "name": "무주 덕유산 패러글라이딩",
        "addr": "전북특별자치도 무주군 무주읍 내도로 373-30",
        "geocode_query": "전북특별자치도 무주군 무주읍 내도로 373-30",
        "note": "무주 F1 패러글라이딩",
    },
    {
        "id": 82,
        "name": "부산 영도 패러글라이딩",
        "addr": "부산광역시 금정구 금정로 224",
        "geocode_query": "부산광역시 금정구 금정로 224",
        "note": "부산패러글라이딩학교 사무실 기준",
        "br_append": "실제 비행 장소는 당일 기상에 따라 영도/송도/금정산 등으로 변경됨.",
    },
    {
        "id": 80,
        "name": "담양 패러글라이딩",
        "addr": "전라남도 담양군 창평면 유천길 163",
        "geocode_query": "전라남도 담양군 창평면 유천길 163",
        "note": "010-4840-3330",
    },
    {
        "id": 78,
        "name": "고창 패러글라이딩",
        "addr": "전북특별자치도 고창군 고창읍 월곡리 35",
        "geocode_query": "전북특별자치도 고창군 고창읍 월곡리 35",
        "note": "고창읍성패러글라이딩, 010-4344-2625",
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


def merge_br(existing: str, append: str | None) -> str | None:
    if not append:
        return None
    base = (existing or "").strip()
    if append in base:
        return base
    if base:
        return f"{base} {append}"
    return append


def build_plan(client: httpx.Client, spots: dict[int, dict]) -> list[dict]:
    plan: list[dict] = []
    for fix in FIXES:
        current = spots.get(fix["id"]) or {}
        before = {
            "addr": current.get("addr"),
            "lat": current.get("lat"),
            "lng": current.get("lng"),
            "br": current.get("br"),
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

        new_lat, new_lng = hit["lat"], hit["lng"]
        rev = kakao_reverse(client, new_lat, new_lng)
        time.sleep(0.15)

        new_br = merge_br(before.get("br") or "", fix.get("br_append"))
        after = {
            "addr": fix["addr"],
            "lat": new_lat,
            "lng": new_lng,
        }
        if new_br is not None:
            after["br"] = new_br

        plan.append(
            {
                "id": fix["id"],
                "name": fix["name"],
                "note": fix.get("note"),
                "before": before,
                "after": after,
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

    out = ROOT / "scripts" / "tier_b_paragliding_batch3_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER B PARAGLIDING BATCH 3 - DRY RUN")
    print("=" * 72)

    for row in plan:
        if row.get("error"):
            print(f"\n#{row['id']} {row['name']} - ERROR: {row['error']}")
            continue
        b, a = row["before"], row["after"]
        print(f"\n#{row['id']} {row['name']}")
        if row.get("note"):
            print(f"  Note: {row['note']}")
        print(f"  BEFORE addr: {b.get('addr')}")
        print(f"  BEFORE pin:  {b.get('lat')}, {b.get('lng')}")
        if b.get("br"):
            print(f"  BEFORE br:   {b.get('br')}")
        print(f"  AFTER  addr: {a.get('addr')}")
        print(f"  AFTER  pin:  {a.get('lat')}, {a.get('lng')}")
        if a.get("br") and a.get("br") != b.get("br"):
            print(f"  AFTER  br:   {a.get('br')}")
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
        print("Apply with: python scripts/fix_tier_b_paragliding_batch3.py --apply")


if __name__ == "__main__":
    main()
