# -*- coding: utf-8 -*-
"""Tier C kart spots - address/coordinate fixes and selective delete. Dry-run or apply."""

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
        "id": 30,
        "name": "한반도 카트체험장",
        "addr": "강원특별자치도 영월군 한반도면 안새내길 63-33",
        "geocode_query": "강원특별자치도 영월군 한반도면 안새내길 63-33",
    },
    {
        "id": 31,
        "name": "오션뷰 카트체험장",
        "addr": "경상남도 거제시 일운면 거제대로 1514-18",
        "geocode_query": "경상남도 거제시 일운면 거제대로 1514-18",
    },
    {
        "id": 32,
        "name": "서광 카트체험장",
        "addr": "제주특별자치도 서귀포시 안덕면 서광리 771",
        "geocode_query": "제주특별자치도 서귀포시 안덕면 서광리 771",
    },
    {
        "id": 34,
        "name": "화암 카트체험장",
        "addr": "강원특별자치도 정선군 화암면 소금강로 973",
        "geocode_query": "강원특별자치도 정선군 화암면 소금강로 973",
    },
    {
        "id": 35,
        "name": "송악 카트체험장",
        "addr": "제주특별자치도 서귀포시 대정읍 송악산",
        "geocode_query": "제주특별자치도 서귀포시 대정읍 송악산",
        "note": "송악산 인근 - 상모리 산 2",
    },
    {
        "id": 36,
        "name": "왜관 카트체험장",
        "addr": "경상북도 칠곡군 왜관읍 강변대로 807",
        "geocode_query": "경상북도 칠곡군 왜관읍 강변대로 807",
    },
    {
        "id": 37,
        "name": "양남 카트체험장",
        "addr": "경상북도 경주시 양남면 동남로 856",
        "geocode_query": "경상북도 경주시 양남면 동남로 856",
    },
    {
        "id": 38,
        "name": "낙동강자전거이야기촌 카트체험장",
        "addr": "경상북도 상주시 사벌국면 국제승마장로 27",
        "geocode_query": "경상북도 상주시 사벌국면 국제승마장로 27",
        "note": "audit 역지오코딩: 삼덕리 산 23-38 카트대여소",
    },
    {
        "id": 40,
        "name": "증도 카트체험장",
        "addr": "전라남도 신안군 증도면 우전리",
        "geocode_query": "전라남도 신안군 증도면 엘도라도리조트",
        "note": "우전리 엘도라도리조트 인근 - 정확 지번 보류",
    },
    {
        "id": 41,
        "name": "제주레포츠랜드 카트체험장",
        "addr": "제주특별자치도 제주시 조천읍 와흘상서2길 47",
        "geocode_query": "제주특별자치도 제주시 조천읍 와흘상서2길 47",
    },
]

DELETE = [
    {
        "id": 39,
        "name": "드리프트전동 카트체험장",
        "reason": "특정 장소가 아닌 카트 종류명",
    },
    {
        "id": 33,
        "name": "스피드캠프 카트체험장",
        "reason": "실존 업체 확인 안 됨",
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


def build_plan(client: httpx.Client, spots: dict[int, dict]) -> dict:
    updates: list[dict] = []
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
            updates.append(
                {
                    "id": fix["id"],
                    "name": fix["name"],
                    "action": "update",
                    "error": f"geocode failed: {fix['geocode_query']}",
                    "before": before,
                }
            )
            continue
        rev = kakao_reverse(client, hit["lat"], hit["lng"])
        time.sleep(0.15)
        updates.append(
            {
                "id": fix["id"],
                "name": fix["name"],
                "action": "update",
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

    deletes: list[dict] = []
    for item in DELETE:
        current = spots.get(item["id"]) or {}
        deletes.append(
            {
                "id": item["id"],
                "name": item["name"],
                "action": "delete",
                "reason": item["reason"],
                "before": {
                    "addr": current.get("addr"),
                    "lat": current.get("lat"),
                    "lng": current.get("lng"),
                },
            }
        )

    return {"updates": updates, "deletes": deletes}


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
    parser.add_argument("--spot-id", type=int, default=None, help="Apply only this spot id")
    args = parser.parse_args()

    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY missing")

    with httpx.Client() as client:
        spots = fetch_spots(client)
        plan = build_plan(client, spots)

    if args.spot_id is not None:
        plan["updates"] = [r for r in plan["updates"] if r["id"] == args.spot_id]
        plan["deletes"] = [r for r in plan["deletes"] if r["id"] == args.spot_id]
        if not plan["updates"] and not plan["deletes"]:
            raise SystemExit(f"spot-id {args.spot_id} not in Tier C kart plan")

    out = ROOT / "scripts" / "tier_c_kart_fix_dryrun.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("TIER C KART - DRY RUN")
    print("=" * 72)

    for row in plan["updates"]:
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

    print("\n" + "-" * 72)
    print("DELETE:")
    for row in plan["deletes"]:
        b = row["before"]
        print(f"\n#{row['id']} {row['name']} [DELETE]")
        print(f"  Reason: {row.get('reason')}")
        print(f"  Current addr: {b.get('addr')}")
        print(f"  Current pin:  {b.get('lat')}, {b.get('lng')}")

    errors = [r for r in plan["updates"] if r.get("error")]
    if errors and args.apply:
        raise SystemExit(f"{len(errors)} geocode failure(s)")

    if args.apply:
        print("\nApplying to", BASE, "...")
        with httpx.Client() as client:
            spots = fetch_spots(client)
            for row in plan["updates"]:
                if row.get("error"):
                    continue
                existing = spots.get(row["id"])
                if not existing:
                    raise SystemExit(f"Spot #{row['id']} not found")
                apply_update(client, existing, row["after"])
                print(f"  OK UPDATE #{row['id']} {row['name']}")
            for row in plan["deletes"]:
                apply_delete(client, row["id"])
                print(f"  OK DELETE #{row['id']} {row['name']}")
        print("Done.")
    else:
        print(f"\nDry-run saved: {out}")
        print("Apply with: python scripts/fix_tier_c_kart.py --apply [--spot-id ID]")


if __name__ == "__main__":
    main()
