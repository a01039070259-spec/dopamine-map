# -*- coding: utf-8 -*-
"""a_group_review.csv 반자동 처리.

자동 fix: 시/군 일치 + 상호 동일
자동 keep: 명백한 오탐 → DB 유지 + coordVerified=true
needs_human: 애매 / #48 강제
#17, #57 스킵

사용법:
    python scripts/process_a_group_review.py          # 분류 + 목록, y/n 후 적용
    python scripts/process_a_group_review.py --plan   # 분류만
    python scripts/process_a_group_review.py --yes    # 확인 생략
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "").strip()
BASE = os.getenv("APPLY_BASE_URL", "https://dopamine-map.onrender.com")
REVIEW_CSV = ROOT / "scripts" / "a_group_review.csv"
NEEDS_HUMAN_CSV = ROOT / "scripts" / "needs_human.csv"

SKIP_IDS = {17, 57}
FORCE_HUMAN_IDS = {48}

METRO_SHORT = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주"}
METRO_SUFFIX = re.compile(r"(특별자치도|특별자치시|통합특별시|광역시|특별시)$")

# 업종 불일치 신호 (카카오 결과에만 있고 스팟 활동과 무관)
FOOD_OR_UNRELATED = (
    "닭갈비",
    "꼬막",
    "식당",
    "카페",
    "호텔",
    "리조트",
    "모텔",
    "펜션",
    "마트",
    "편의점",
    "주유소",
    "충전소",
    "캠핑장",
    "호수",
)

ACTIVITY_HINTS = (
    "짚라인",
    "짚와이어",
    "번지",
    "패러",
    "열기구",
    "루지",
    "코스터",
    "ATV",
    "승마",
    "사격",
    "카트",
    "스카이워크",
    "휴양밸리",
    "스포랜드",
)

SUFFIX_RE = re.compile(
    r"(체험장|체험|클럽|파크|레저|레포츠|테마파크|휴양밸리|스카이워크|"
    r"짚라인|짚와이어|번지점프|패러글라이딩|알파인코스터|열기구)$"
)


def region_keys(addr: str) -> set[str]:
    keys: set[str] = set()
    for token in (addr or "").split()[:3]:
        stripped = METRO_SUFFIX.sub("", token)
        if stripped != token:
            if stripped:
                keys.add(stripped)
            continue
        if token in METRO_SHORT:
            keys.add(token)
        elif len(token) >= 2 and token.endswith(("시", "군")):
            keys.add(token[:-1])
    return keys


def normalize_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[\s\-_/·&()（）\[\]【】]", "", s)
    s = s.replace("보불", "보문")  # known typo
    return s


def core_tokens(name: str) -> set[str]:
    s = normalize_name(name)
    # strip common activity suffixes repeatedly
    for _ in range(3):
        ns = SUFFIX_RE.sub("", s)
        if ns == s:
            break
        s = ns
    tokens = set()
    if len(s) >= 2:
        tokens.add(s)
    # also keep significant chunks >= 2 chars from original spaced words
    for w in re.split(r"[\s\-_/·&]+", name or ""):
        w = normalize_name(w)
        w = SUFFIX_RE.sub("", w)
        if len(w) >= 2:
            tokens.add(w)
    return {t for t in tokens if t}


def same_business(spot_name: str, kakao_place: str) -> bool | None:
    """True=동일, False=명백히 다름, None=애매."""
    kp = kakao_place or ""
    sn = spot_name or ""
    if not kp:
        return None

    # 업종 충돌: 카카오가 음식/숙박 등이고 스팟은 액티비티
    kp_food = any(x in kp for x in FOOD_OR_UNRELATED)
    sn_act = any(x in sn for x in ACTIVITY_HINTS) or True  # most spots are activities
    if kp_food and not any(x in kp for x in ACTIVITY_HINTS):
        # hotel/resort exception only if spot also contains that word
        if any(x in kp for x in ("호텔", "리조트", "닭갈비", "꼬막", "식당", "카페", "캠핑장", "호수")):
            if not any(x in sn for x in ("호텔", "리조트", "캠핑")):
                return False

    st = core_tokens(sn)
    kt = core_tokens(kp)
    if not st or not kt:
        return None

    # direct containment
    sn_n, kp_n = normalize_name(sn), normalize_name(kp)
    if sn_n and kp_n and (sn_n in kp_n or kp_n in sn_n):
        return True

    # shared significant token (len>=3 preferred)
    shared = st & kt
    if any(len(t) >= 3 for t in shared):
        return True
    if shared and any(len(t) >= 2 for t in shared):
        # weak: e.g. 왕솔
        return True

    # partial: longest common substring >= 4
    for a in st:
        for b in kt:
            if len(a) >= 4 and a in b:
                return True
            if len(b) >= 4 and b in a:
                return True

    return None


def classify_row(r: dict) -> tuple[str, str]:
    """Return (action, reason) where action in fix|keep|needs_human|skip."""
    sid = int(r["spot_id"])
    if sid in SKIP_IDS:
        return "skip", "이미 단양 좌표 수정 완료"
    if sid in FORCE_HUMAN_IDS:
        return "needs_human", "DB 안산 vs 카카오 곤지암 — 강제 수동 확인"

    db_addr = r.get("db_addr") or ""
    kakao_addr = r.get("kakao_addr") or ""
    kakao_place = r.get("kakao_place") or ""
    name = r.get("name") or ""

    db_keys = region_keys(db_addr)
    kk_keys = region_keys(kakao_addr)
    region_ok = bool(db_keys & kk_keys) if (db_keys and kk_keys) else False

    biz = same_business(name, kakao_place)

    # Explicit known false positives
    if sid in (87, 52):
        return "keep", f"명백한 오탐 (카카오={kakao_place})"

    if region_ok and biz is True:
        return "fix", f"시/군 일치({sorted(db_keys & kk_keys)}) + 상호 동일({kakao_place})"

    if biz is False:
        return "keep", f"업종/상호 오탐 (카카오={kakao_place})"

    if not region_ok and biz is not True:
        return "keep", (
            f"시/군 불일치 오탐 "
            f"(DB={'/'.join(sorted(db_keys)) or '?'} vs 카카오={'/'.join(sorted(kk_keys)) or '?'})"
        )

    # region ok but biz ambiguous, or region fail but biz true (weird)
    if region_ok and biz is None:
        return "needs_human", f"시/군은 맞지만 상호 동일 여부 애매 (카카오={kakao_place})"

    if not region_ok and biz is True:
        return "needs_human", (
            f"상호는 유사하나 시/군 불일치 "
            f"(DB={'/'.join(sorted(db_keys)) or '?'} vs 카카오={'/'.join(sorted(kk_keys)) or '?'})"
        )

    return "needs_human", f"자동 판정 불가 (카카오={kakao_place})"


def fetch_spot(client: httpx.Client, spot_id: int) -> dict | None:
    res = client.get(
        f"{BASE}/api/spots/{spot_id}",
        headers={"X-Admin-Password": ADMIN_PASS},
        timeout=30.0,
    )
    if res.status_code == 200:
        return res.json()
    return None


def put_spot(client: httpx.Client, existing: dict, updates: dict) -> dict:
    payload = {**existing, **updates}
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


def refresh_kakao(client: httpx.Client, place_hint: str, name: str) -> dict | None:
    """Re-query Kakao so ADDR rows with stale CSV coords get real lat/lng."""
    key = (os.getenv("KAKAO_REST_KEY") or os.getenv("KAKAO_REST_API_KEY") or "").strip()
    if not key:
        return None
    headers = {"Authorization": f"KakaoAK {key}"}
    for q in (place_hint, name):
        q = (q or "").strip()
        if not q:
            continue
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": q, "size": "1"},
            headers=headers,
            timeout=20.0,
        )
        if res.status_code >= 400:
            continue
        docs = res.json().get("documents") or []
        if not docs:
            continue
        d = docs[0]
        return {
            "place": d.get("place_name") or "",
            "addr": d.get("road_address_name") or d.get("address_name") or "",
            "lat": float(d["y"]),
            "lng": float(d["x"]),
        }
    return None


def write_needs_human(rows: list[dict]) -> None:
    fields = [
        "spot_id",
        "name",
        "db_addr",
        "db_lat",
        "db_lng",
        "kakao_place",
        "kakao_addr",
        "kakao_lat",
        "kakao_lng",
        "distance_km",
        "reason",
    ]
    with open(NEEDS_HUMAN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="분류만 출력")
    parser.add_argument("--yes", action="store_true", help="y/n 생략하고 적용")
    args = parser.parse_args()

    with open(REVIEW_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    buckets: dict[str, list[tuple[dict, str]]] = {
        "fix": [],
        "keep": [],
        "needs_human": [],
        "skip": [],
    }
    for r in rows:
        action, reason = classify_row(r)
        buckets[action].append((r, reason))

    print("=" * 90)
    print(
        f"a_group_review {len(rows)}건 → "
        f"fix={len(buckets['fix'])} keep={len(buckets['keep'])} "
        f"needs_human={len(buckets['needs_human'])} skip={len(buckets['skip'])}"
    )
    print("=" * 90)

    for label in ("fix", "keep", "needs_human", "skip"):
        print(f"\n--- {label.upper()} ({len(buckets[label])}) ---")
        for r, reason in buckets[label]:
            print(
                f"#{r['spot_id']} {r['name']}\n"
                f"  DB: {r.get('db_addr')} ({r.get('db_lat')}, {r.get('db_lng')})\n"
                f"  KK: {r.get('kakao_place')} / {r.get('kakao_addr')} "
                f"({r.get('kakao_lat')}, {r.get('kakao_lng')}) dist={r.get('distance_km')}\n"
                f"  → {reason}"
            )

    human_rows = []
    for r, reason in buckets["needs_human"]:
        human_rows.append({**r, "reason": reason})
    write_needs_human(human_rows)
    print(f"\nneeds_human.csv 저장: {NEEDS_HUMAN_CSV} ({len(human_rows)}건)")

    if args.plan:
        print("\n[plan] 적용하지 않고 종료")
        return

    if not ADMIN_PASS:
        raise SystemExit("ADMIN_PASSWORD 필요")

    to_apply = buckets["fix"] + buckets["keep"]
    if not to_apply:
        print("적용할 fix/keep 없음")
        return

    print("\n" + "=" * 90)
    print(f"자동 적용 예정: fix {len(buckets['fix'])} + keep {len(buckets['keep'])} = {len(to_apply)}건")
    print("=" * 90)
    if not args.yes:
        ans = input("위 목록대로 적용할까요? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("취소됨")
            return

    ok_fix = ok_keep = 0
    with httpx.Client(timeout=60) as client:
        for r, reason in buckets["fix"]:
            sid = int(r["spot_id"])
            existing = fetch_spot(client, sid)
            if not existing:
                print(f"FAIL fix #{sid}: spot 조회 실패")
                continue
            hit = refresh_kakao(client, r.get("kakao_place") or "", r.get("name") or "")
            if hit:
                lat, lng, addr = hit["lat"], hit["lng"], hit["addr"] or r.get("kakao_addr")
                print(f"  kakao refresh: {hit['place']} / {addr} ({lat}, {lng})")
            else:
                lat = float(r["kakao_lat"])
                lng = float(r["kakao_lng"])
                addr = r.get("kakao_addr") or existing["addr"]
            updates = {
                "lat": lat,
                "lng": lng,
                "addr": addr or existing["addr"],
                "coordVerified": True,
            }
            put_spot(client, existing, updates)
            print(f"OK fix #{sid} {r['name']} → {updates['lat']}, {updates['lng']}")
            ok_fix += 1

        for r, reason in buckets["keep"]:
            sid = int(r["spot_id"])
            existing = fetch_spot(client, sid)
            if not existing:
                print(f"FAIL keep #{sid}: spot 조회 실패")
                continue
            put_spot(client, existing, {"coordVerified": True})
            print(f"OK keep #{sid} {r['name']} (DB 유지, verified)")
            ok_keep += 1

    print(f"\n적용 완료: fix={ok_fix} keep={ok_keep} needs_human={len(human_rows)}")


if __name__ == "__main__":
    main()
