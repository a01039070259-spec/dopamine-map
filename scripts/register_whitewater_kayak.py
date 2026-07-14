# -*- coding: utf-8 -*-
"""Register 급류 카약 spots via Kakao place_id (admin API)."""
from __future__ import annotations

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

SPOTS = [
    {
        "name": "송강카누학교",
        "kakao_queries": ["송강카누학교"],
        "prefer_place_id": "21087461",
        "thrillGrade": 4,
        "seasonStartMonth": 5,
        "seasonEndMonth": 9,
        "th": 4,
        "fp": 72,
        "sp2": 70,
        "ap": 78,
        "sp": 0,
        "br": "내린천 급류를 몸으로 끊는 국내 최초 패들스포츠 본진. 평시 2급, 장마 후면 3급으로 난이도가 급상승한다. 더키 가이드 투어 기본부터 다이나믹 코스까지 — 안전바가 없는 강이 진짜다.",
        "tags": ["#급류카약", "#내린천", "#더키투어", "#2급수", "#장마후3급"],
        "warns": [
            {"i": "⚠️", "tx": "평시에도 전복 가능성 있음 · 구명조끼 필착", "t": "y"},
            {"i": "💀", "tx": "장마·수위 상승 시 3급 급류 · 초보 단독 금지", "t": "y"},
            {"i": "📍", "tx": "상류 진동계곡 5~6m 폭포 구간은 전복률 높음", "t": "g"},
        ],
    },
    {
        "name": "동강레포츠 급류카약",
        "kakao_queries": ["동강레포츠스쿨", "동강레포츠 영월"],
        "prefer_place_id": "10110563",
        "thrillGrade": 4,
        "seasonStartMonth": 5,
        "seasonEndMonth": 9,
        "th": 4,
        "fp": 70,
        "sp2": 68,
        "ap": 76,
        "sp": 0,
        "br": "영월 동강에서 1~3인승 급류카약 강습과 카약서핑까지. 강줄기를 타는 속도감은 래프팅과 또 다른 도파민이다.",
        "tags": ["#급류카약", "#동강", "#카약서핑", "#영월", "#강습"],
        "warns": [
            {"i": "⚠️", "tx": "강습 코스 기준 구명조끼·헬멧 착용", "t": "y"},
            {"i": "🌊", "tx": "수위·기상 따라 코스 변동 · 당일 브리핑 필수", "t": "g"},
        ],
        "_note": "카카오 place명: 동강레포츠스쿨 (영월 김삿갓면)",
    },
    {
        "name": "내린천 리버버깅",
        "kakao_queries": ["리버버깅 인제", "미산계곡 리버버깅"],
        "prefer_place_id": "1908834498",
        "thrillGrade": 4,
        "seasonStartMonth": 6,
        "seasonEndMonth": 8,
        "th": 4,
        "fp": 74,
        "sp2": 72,
        "ap": 80,
        "sp": 0,
        "br": "래프팅+카약을 접목한 신종 급류 레포츠, 국내에서 여기서만. 인제 미산계곡 내린천을 튜브형 보트로 찢고 간다.",
        "tags": ["#리버버깅", "#내린천", "#미산계곡", "#국내최초", "#급류"],
        "warns": [
            {"i": "⚠️", "tx": "시즌 6~8월 · 수온·수위 브리핑 후 탑승", "t": "y"},
            {"i": "💀", "tx": "전복·낙수 대비 구명조끼 필착", "t": "y"},
        ],
        "_note": "카카오 place명: 리버버깅 (인제 상남면)",
    },
]


def kakao_by_id(client: httpx.Client, place_id: str) -> dict | None:
    # keyword API doesn't query by id; search and match
    return None


def resolve_place(client: httpx.Client, spot: dict) -> dict | None:
    prefer = spot.get("prefer_place_id")
    headers = {"Authorization": f"KakaoAK {KEY}"}
    for q in spot["kakao_queries"]:
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": q, "size": "5"},
            headers=headers,
            timeout=20,
        )
        docs = res.json().get("documents") or []
        if prefer:
            for d in docs:
                if str(d.get("id")) == str(prefer):
                    return d
        if docs:
            # if prefer set but not in this query, keep looking
            if prefer:
                continue
            return docs[0]
    # final pass: any query top hit if prefer not found
    if prefer:
        for q in spot["kakao_queries"]:
            res = client.get(
                "https://dapi.kakao.com/v2/local/search/keyword.json",
                params={"query": q, "size": "5"},
                headers=headers,
                timeout=20,
            )
            docs = res.json().get("documents") or []
            for d in docs:
                if str(d.get("id")) == str(prefer):
                    return d
            if docs and str(docs[0].get("id")) == str(prefer):
                return docs[0]
        # accept exact prefer via broader search of first query results scan
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": spot["kakao_queries"][0], "size": "15"},
            headers=headers,
            timeout=20,
        )
        for d in res.json().get("documents") or []:
            if str(d.get("id")) == str(prefer):
                return d
    return None


def main() -> None:
    if not ADMIN_PASS or not KEY:
        raise SystemExit("ADMIN_PASSWORD / KAKAO key 필요")

    needs = []
    with httpx.Client(timeout=60) as client:
        existing = client.get(f"{BASE}/api/spots").json()
        by_name = {s["name"]: s for s in existing}

        for spot in SPOTS:
            print(f"\n=== {spot['name']} ===")
            if spot["name"] in by_name:
                print(f"  already exists id={by_name[spot['name']]['id']} — skip create")
                # still try patch grade/season/verified
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
                    "type": "whitewaterKayak",
                    "tl": "급류 카약",
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
                reason = "카카오 place_id 확정 실패"
                needs.append({**spot, "reason": reason})
                print(f"  FAIL: {reason}")
                continue

            addr = place.get("road_address_name") or place.get("address_name") or ""
            lat = float(place["y"])
            lng = float(place["x"])
            pid = str(place.get("id") or "")
            print(f"  kakao: {place.get('place_name')} | {addr} | id={pid}")
            if spot.get("prefer_place_id") and pid != str(spot["prefer_place_id"]):
                needs.append({**spot, "reason": f"place_id 불일치 prefer={spot['prefer_place_id']} got={pid}"})
                print("  FAIL: place_id mismatch → needs_human")
                continue

            payload = {
                "name": spot["name"],
                "addr": addr,
                "lat": lat,
                "lng": lng,
                "type": "whitewaterKayak",
                "tl": "급류 카약",
                "em": "🛶",
                "bg": "#001828",
                "th": spot["th"],
                "fp": spot["fp"],
                "sp2": spot["sp2"],
                "ap": spot["ap"],
                "sp": spot["sp"],
                "rank": "WHITEWATER",
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
                print(r.text[:300])
                needs.append({**spot, "reason": f"API {r.status_code}"})
            else:
                created = r.json()
                print(f"  OK id={created.get('id')} verified={created.get('coordVerified')} grade={created.get('thrillGrade')}")

    if needs:
        import csv

        path = ROOT / "scripts" / "needs_human_kayak.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["name", "reason", "prefer_place_id", "seasonStartMonth", "seasonEndMonth"],
                extrasaction="ignore",
            )
            w.writeheader()
            for n in needs:
                w.writerow(n)
        print(f"\nneeds_human: {path} ({len(needs)})")
    else:
        print("\nall spots registered")


if __name__ == "__main__":
    main()
