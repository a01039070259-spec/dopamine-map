# -*- coding: utf-8 -*-
"""단양 스팟 좌표/주소 수정 + venue 전파 검증.

- #17, #57: #25와 동일 좌표(36.9776, 128.3371)로 통일
- #237 단양사격테마파크: 실제 주소(단양클레이사격장, dyclay.kr)로 교체 + 카카오 지오코딩 좌표
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KAKAO_KEY = (os.getenv("KAKAO_REST_KEY") or os.getenv("KAKAO_REST_API_KEY") or "").strip()
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "").strip()
BASE = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")

DANYANG_237_ADDR = "충청북도 단양군 단양읍 노동장현로 207-17"


def kakao_geocode(client: httpx.Client, queries: list[str]) -> dict | None:
    headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}
    for query in queries:
        for path, params in (
            ("search/keyword.json", {"query": query, "size": "3"}),
            ("search/address.json", {"query": query}),
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
                    "source": f"{path} ({query})",
                }
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                continue
            finally:
                time.sleep(0.2)
    return None


def fetch_spot(client: httpx.Client, spot_id: int) -> dict:
    res = client.get(
        f"{BASE}/api/spots/{spot_id}",
        headers={"X-Admin-Password": ADMIN_PASS},
        timeout=30.0,
    )
    res.raise_for_status()
    return res.json()


def put_spot(client: httpx.Client, existing: dict, changes: dict) -> dict:
    payload = {**existing, **changes}
    payload.setdefault("warns", [])
    payload.setdefault("reviews", [])
    payload.setdefault("img", payload.get("img") or "")
    res = client.put(
        f"{BASE}/api/spots/{existing['id']}",
        headers={"X-Admin-Password": ADMIN_PASS, "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
    res.raise_for_status()
    return res.json()


def get_venue(client: httpx.Client, venue_id: int) -> dict:
    res = client.get(f"{BASE}/api/venues/{venue_id}", timeout=30.0)
    res.raise_for_status()
    return res.json()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    if not ADMIN_PASS:
        raise SystemExit("ADMIN_PASSWORD 필요 (.env)")
    if not KAKAO_KEY:
        raise SystemExit("KAKAO_REST_API_KEY 필요 (.env)")

    with httpx.Client() as client:
        # #237 지오코딩 (업체명 우선, 새 주소 fallback)
        hit = kakao_geocode(client, ["단양클레이사격장", DANYANG_237_ADDR])
        if not hit:
            raise SystemExit("#237 지오코딩 실패 — 중단")
        print(f"#237 지오코딩: {hit['label']} → {hit['lat']}, {hit['lng']}  [{hit['source']}]")

        # 1) #17, #57 → #25와 동일 좌표
        for sid in (17, 57):
            existing = fetch_spot(client, sid)
            before = (existing.get("lat"), existing.get("lng"))
            put_spot(client, existing, {"lat": 36.9776, "lng": 128.3371})
            print(f"OK #{sid} {existing['name']}: {before} → (36.9776, 128.3371)")
            time.sleep(0.15)

        # 2) #237 주소 + 좌표
        existing = fetch_spot(client, 237)
        before = (existing.get("addr"), existing.get("lat"), existing.get("lng"))
        put_spot(
            client,
            existing,
            {"addr": DANYANG_237_ADDR, "lat": hit["lat"], "lng": hit["lng"]},
        )
        print(f"OK #237 {existing['name']}:")
        print(f"   BEFORE addr={before[0]} pin=({before[1]}, {before[2]})")
        print(f"   AFTER  addr={DANYANG_237_ADDR} pin=({hit['lat']}, {hit['lng']})")

        # 3) venue 전파 검증
        print()
        print("=== venue 전파 검증 ===")
        v5 = get_venue(client, 5)
        print(f"venue 5 ({v5.get('name')}): lat={v5.get('lat')} lng={v5.get('lng')}")
        for s in v5.get("spots") or []:
            print(f"   - #{s['id']} {s['name']}: {s.get('lat')}, {s.get('lng')}")
        v237 = get_venue(client, -237)
        print(f"venue -237 ({v237.get('name')}): lat={v237.get('lat')} lng={v237.get('lng')}")

        ok5 = abs(float(v5.get("lat") or 0) - 36.9776) < 1e-6 and abs(float(v5.get("lng") or 0) - 128.3371) < 1e-6
        ok237 = abs(float(v237.get("lat") or 0) - hit["lat"]) < 1e-6 and abs(float(v237.get("lng") or 0) - hit["lng"]) < 1e-6
        print()
        print(f"venue 5 마커 좌표 정위치: {'PASS' if ok5 else 'FAIL'}")
        print(f"venue -237 마커 좌표 정위치: {'PASS' if ok237 else 'FAIL'}")


if __name__ == "__main__":
    main()
