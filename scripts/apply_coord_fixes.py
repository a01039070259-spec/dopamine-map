# -*- coding: utf-8 -*-
"""coord_audit.csv A그룹(1km 초과) 좌표 자동 수정.

적용 조건: DB 주소와 카카오 결과 주소의 시/군이 일치할 것.
제외 건은 scripts/skipped_fixes.csv에 사유와 함께 기록.

venue 좌표 관련: venues 테이블에는 lat/lng 컬럼이 없고 venue 좌표는 항상
소속 spot(첫 번째 멤버)에서 파생되므로, spot 좌표를 수정하면 venue 마커
좌표는 자동 반영된다. 수정 후 venue API를 재조회해 전파를 검증한다.

사용법:
    python scripts/apply_coord_fixes.py          # 목록 출력 후 y/n 확인
    python scripts/apply_coord_fixes.py --yes    # 확인 생략 (비대화형)
    python scripts/apply_coord_fixes.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "").strip()
BASE = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")

AUDIT_CSV = ROOT / "scripts" / "coord_audit.csv"
SKIPPED_CSV = ROOT / "scripts" / "skipped_fixes.csv"

# 광역/특별시 등 시/군 토큰이 아닌 1depth 축약명 (카카오는 "부산 남구" 식으로 반환)
METRO_SHORT = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주"}
METRO_SUFFIX = re.compile(r"(특별자치도|특별자치시|통합특별시|광역시|특별시)$")


def region_keys(addr: str) -> set[str]:
    """주소에서 시/군 단위 키 추출. 예: '충청남도 부여군 부여읍' -> {'부여'}"""
    keys: set[str] = set()
    for token in (addr or "").split()[:3]:
        stripped = METRO_SUFFIX.sub("", token)
        if stripped != token:
            # 부산광역시 -> 부산, 세종특별자치시 -> 세종
            if stripped:
                keys.add(stripped)
            continue
        if token in METRO_SHORT:
            keys.add(token)
        elif len(token) >= 2 and token.endswith(("시", "군")):
            keys.add(token[:-1])  # 부여군 -> 부여, 포천시 -> 포천
    return keys


def gu_keys(addr: str) -> set[str]:
    return {t for t in (addr or "").split()[:4] if len(t) >= 2 and t.endswith("구")}


def load_group_a() -> list[dict]:
    if not AUDIT_CSV.is_file():
        raise SystemExit(f"감사 CSV가 없습니다: {AUDIT_CSV} (먼저 verify_coords.py 실행)")
    with open(AUDIT_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if (r.get("group") or "").strip().upper() == "A"]


def build_plan(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    apply_list: list[dict] = []
    skipped: list[dict] = []
    for r in rows:
        sid = r.get("spot_id")
        name = r.get("name") or ""
        db_addr = r.get("db_addr") or ""
        kakao_addr = r.get("kakao_addr") or ""
        kakao_lat = r.get("kakao_lat") or ""
        kakao_lng = r.get("kakao_lng") or ""

        if not kakao_lat or not kakao_lng:
            skipped.append({**r, "skip_reason": "카카오 좌표 없음"})
            continue
        if not kakao_addr:
            skipped.append({**r, "skip_reason": "카카오 주소 없음 — 시/군 비교 불가"})
            continue

        db_keys = region_keys(db_addr)
        kk_keys = region_keys(kakao_addr)
        matched = db_keys & kk_keys
        if not matched:
            skipped.append(
                {
                    **r,
                    "skip_reason": f"시/군 불일치 (DB={'/'.join(sorted(db_keys)) or '?'} vs 카카오={'/'.join(sorted(kk_keys)) or '?'})",
                }
            )
            continue

        warn = ""
        db_gu, kk_gu = gu_keys(db_addr), gu_keys(kakao_addr)
        if db_gu and kk_gu and not (db_gu & kk_gu):
            warn = f"구 단위 불일치 주의 ({'/'.join(sorted(db_gu))} vs {'/'.join(sorted(kk_gu))})"

        apply_list.append(
            {
                "spot_id": int(sid),
                "name": name,
                "db_lat": r.get("db_lat"),
                "db_lng": r.get("db_lng"),
                "new_lat": float(kakao_lat),
                "new_lng": float(kakao_lng),
                "distance_km": r.get("distance_km"),
                "kakao_place": r.get("kakao_place") or "",
                "kakao_addr": kakao_addr,
                "matched_region": "/".join(sorted(matched)),
                "warn": warn,
            }
        )
    return apply_list, skipped


def fetch_spot(client: httpx.Client, spot_id: int) -> dict | None:
    res = client.get(
        f"{BASE}/api/spots/{spot_id}",
        headers={"X-Admin-Password": ADMIN_PASS},
        timeout=30.0,
    )
    if res.status_code == 200:
        return res.json()
    return None


def update_spot_coords(client: httpx.Client, existing: dict, lat: float, lng: float) -> None:
    payload = {**existing, "lat": lat, "lng": lng}
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


def verify_venue_propagation(client: httpx.Client, spot: dict) -> str:
    """venue 좌표는 spot에서 파생 — 수정 후 venue API로 전파 확인."""
    venue_id = spot.get("venueId")
    if venue_id is None:
        venue_id = -int(spot["id"])  # virtual 1:1 venue
    try:
        res = client.get(f"{BASE}/api/venues/{venue_id}", timeout=30.0)
        if res.status_code != 200:
            return f"venue {venue_id} 조회 실패({res.status_code})"
        v = res.json()
        return f"venue {venue_id} ({v.get('name')}) lat={v.get('lat')} lng={v.get('lng')}"
    except httpx.HTTPError as e:
        return f"venue {venue_id} 조회 오류: {e}"


def write_skipped(skipped: list[dict]) -> None:
    if not skipped:
        if SKIPPED_CSV.exists():
            SKIPPED_CSV.unlink()
        return
    fields = list(skipped[0].keys())
    if "skip_reason" not in fields:
        fields.append("skip_reason")
    with open(SKIPPED_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(skipped)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="y/n 확인 생략")
    parser.add_argument("--dry-run", action="store_true", help="적용 없이 목록만 출력")
    args = parser.parse_args()

    if not ADMIN_PASS and not args.dry_run:
        raise SystemExit("ADMIN_PASSWORD 환경변수가 필요합니다 (.env)")

    rows = load_group_a()
    apply_list, skipped = build_plan(rows)

    print("=" * 90)
    print(f"A그룹 {len(rows)}건 중 적용 대상 {len(apply_list)}건 / 제외 {len(skipped)}건")
    print("=" * 90)
    for it in apply_list:
        print(f"\n#{it['spot_id']} {it['name']}  [시/군 일치: {it['matched_region']}]")
        print(f"  BEFORE: {it['db_lat']}, {it['db_lng']}")
        print(f"  AFTER : {it['new_lat']}, {it['new_lng']}  ({it['distance_km']}km 이동)")
        print(f"  카카오: {it['kakao_place']} / {it['kakao_addr']}")
        if it["warn"]:
            print(f"  ⚠ {it['warn']}")

    if skipped:
        print("\n--- 제외 목록 (skipped_fixes.csv) ---")
        for s in skipped:
            print(f"#{s.get('spot_id')} {s.get('name')} — {s['skip_reason']}")

    write_skipped(skipped)
    print(f"\n제외 CSV 저장: {SKIPPED_CSV if skipped else '(제외 건 없음)'}")

    if args.dry_run:
        print("\n[dry-run] 적용하지 않고 종료합니다.")
        return

    if not apply_list:
        print("\n적용할 건이 없습니다.")
        return

    if not args.yes:
        answer = input(f"\n위 {len(apply_list)}건을 {BASE} 에 적용할까요? (y/n): ").strip().lower()
        if answer != "y":
            print("취소했습니다.")
            return

    print(f"\n{BASE} 에 적용 중...")
    ok, fail = 0, 0
    with httpx.Client() as client:
        for it in apply_list:
            existing = fetch_spot(client, it["spot_id"])
            if not existing:
                print(f"  FAIL #{it['spot_id']} {it['name']} — 스팟 조회 실패")
                fail += 1
                continue
            try:
                update_spot_coords(client, existing, it["new_lat"], it["new_lng"])
            except httpx.HTTPError as e:
                print(f"  FAIL #{it['spot_id']} {it['name']} — {e}")
                fail += 1
                continue
            venue_info = verify_venue_propagation(client, existing)
            print(f"  OK #{it['spot_id']} {it['name']} → {it['new_lat']}, {it['new_lng']}")
            print(f"     └ {venue_info}")
            ok += 1
            time.sleep(0.15)

    print(f"\n완료: 성공 {ok} / 실패 {fail} / 제외 {len(skipped)}")


if __name__ == "__main__":
    main()
