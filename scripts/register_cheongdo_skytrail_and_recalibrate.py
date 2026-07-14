#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1) 청도신화랑풍류마을 스카이트레일 등록 (place_id + 생존가이드 + 이미지)
2) 전 스팟 스릴 점수(th/fp/sp2/ap/thrillGrade) 재채점 — 관광형 과도 점수 완화
3) 이미지 없는 스팟 카테고리/스톡 이미지 채움
4) 생존가이드 비어 있으면 타입 템플릿으로 채움
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
load_dotenv(ROOT / ".env")

BASE = os.environ.get("DOPAMINE_API_BASE", "https://dopamine-map.onrender.com").rstrip("/")
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "0259").strip()
KAKAO_KEY = (os.environ.get("KAKAO_REST_API_KEY") or os.environ.get("KAKAO_REST_KEY") or "").strip()

CHEONGDO_PLACE_ID = "157800606"
CHEONGDO_NAME = "청도신화랑풍류마을 스카이트레일"

# 타입별 상한 — 관광·저자극은 크게 못 넘김. 하드코어는 상한 넉넉.
TYPE_TH_CAP: dict[str, int] = {
    "cave": 1,
    "monorail": 1,
    "horse": 2,
    "balloon": 2,
    "amphibious": 2,
    "skywalk": 2,
    "highRopes": 3,
    "survivalGame": 2,
    "kart": 2,
    "netadv": 3,
    "slide": 3,
    "seawalk": 3,
    "skybike": 3,
    "shooting": 3,
    "atv": 3,
    "zipline": 5,
    "luge": 4,
    "aircraft": 4,
    "paragliding": 4,
    "jetboat": 4,
    "speedboat": 4,
    "whitewaterKayak": 4,
    "rockClimbing": 4,
    "bungee": 5,
    "coaster": 5,
    "sky": 4,
    "hangglider": 5,
    "swing": 5,
}

# 타입별 하한 — 너무 낮게 깔리는 것 방지
TYPE_TH_FLOOR: dict[str, int] = {
    "bungee": 4,
    "swing": 5,
    "hangglider": 5,
    "whitewaterKayak": 4,
    "rockClimbing": 4,
    "coaster": 4,
    "jetboat": 4,
    "speedboat": 3,
    "paragliding": 3,
}

# 스팟별 강제 (동굴 등)
SPOT_TH_OVERRIDE: dict[int, int] = {
    251: 1,
    252: 1,
    253: 1,
    254: 1,
    255: 1,
    283: 1,
}

# 이름 키워드로만 올리는 경우 (과도한 상향 방지)
NAME_TH_FORCE: list[tuple[str, int]] = [
    ("슬링샷", 5),
    ("빅스윙", 5),
]

TYPE_PEXELS: dict[str, int] = {
    "zipline": 4494062,
    "bungee": 2107100,
    "swing": 6818336,
    "paragliding": 14501523,
    "balloon": 2325446,
    "aircraft": 46148,
    "seawalk": 847393,
    "skybike": 248547,
    "coaster": 1366919,
    "luge": 5622976,
    "amphibious": 1118448,
    "monorail": 209037,
    "slide": 1366919,
    "skywalk": 2662116,
    "sky": 599072,
    "netadv": 4498155,
    "highRopes": 4498155,
    "jetboat": 18337802,
    "whitewaterKayak": 18337802,
    "kart": 3807277,
    "atv": 4488327,
    "horse": 1996333,
    "shooting": 6091287,
    "speedboat": 11333804,
    "hangglider": 14501523,
    "cave": 19481872,
    "rockClimbing": 1578750,
    "survivalGame": 1586298,
}


def api(method: str, path: str, body: dict | None = None):
    headers = {
        "X-Admin-Password": ADMIN_PASSWORD,
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "DopamineMapRecalibrate/1.0",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def public_get(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "DopamineMapRecalibrate/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def kakao_place(place_id: str) -> dict:
    url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urllib.parse.urlencode(
        {"query": CHEONGDO_NAME, "size": 10}
    )
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        docs = json.loads(resp.read()).get("documents") or []
    for d in docs:
        if str(d.get("id")) == str(place_id):
            return d
    raise RuntimeError(f"kakao place_id {place_id} not found")


def download_pexels(photo_id: int) -> bytes:
    url = (
        f"https://images.pexels.com/photos/{photo_id}/"
        f"pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=1200"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "DopamineMapRecalibrate/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if len(data) < 8000:
        raise ValueError(f"pexels too small {photo_id}")
    return data


def compress_jpeg(raw: bytes, max_w: int = 800, max_h: int = 600, quality: int = 82) -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return raw
    img = Image.open(BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    ratio = min(max_w / w, max_h / h, 1.0)
    if ratio < 1.0:
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def to_data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def scores_for_th(th: int) -> tuple[int, int, int, int]:
    """th(1~5) → th, fp, sp2, ap. 종합 스릴% = 평균."""
    centers = {1: 26, 2: 40, 3: 55, 4: 72, 5: 88}
    c = centers.get(int(th), 50)
    return int(th), c - 2, c + 1, c + 3


def resolve_th(spot: dict) -> int:
    sid = int(spot["id"])
    if sid in SPOT_TH_OVERRIDE:
        return SPOT_TH_OVERRIDE[sid]
    name = spot.get("name") or ""
    for kw, grade in NAME_TH_FORCE:
        if kw in name:
            return grade
    t = spot.get("type") or ""
    try:
        cur = int(spot.get("th") or 0)
    except (TypeError, ValueError):
        cur = 0
    if cur < 1:
        # thrillGrade fallback
        try:
            cur = int(spot.get("thrillGrade") or 3)
        except (TypeError, ValueError):
            cur = 3
    cap = TYPE_TH_CAP.get(t, 5)
    floor = TYPE_TH_FLOOR.get(t, 1)
    return max(floor, min(cur, cap))


def load_survival_templates() -> dict:
    path = SCRIPTS / "survival_type_templates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_const() -> dict:
    path = SCRIPTS / "constants.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "warnTypes": {"☄": "y", "🎒": "y", "📏": "y", "💡": "g", "⏰": "g", "🍻": "r", "📸": "y", "✅": "g"},
        "defaultWarnType": "y",
        "defaultWarnIcon": "💡",
        "fallbackWarn": "탑승 전 현장 안전 수칙을 확인하세요.",
    }


def lines_to_warns(lines: list[str], const: dict) -> list[dict]:
    warn_types = const.get("warnTypes") or {}
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\S+)\s+(.*)$", line, re.DOTALL)
        if not m:
            continue
        icon, tx = m.group(1), m.group(2).strip()
        out.append({"t": warn_types.get(icon, const.get("defaultWarnType", "y")), "i": icon, "tx": tx})
    if not out:
        out.append(
            {
                "t": "y",
                "i": const.get("defaultWarnIcon", "💡"),
                "tx": const.get("fallbackWarn", "탑승 전 현장 안전 수칙을 확인하세요."),
            }
        )
    return out


def skytrail_warns() -> list[dict]:
    return [
        {"i": "⚠️", "tx": "우천·강풍·빙판이면 스카이트레일 휴장 — 당일 운영 전화 확인", "t": "y"},
        {"i": "💀", "tx": "고소·협곡 구간 — 난간 밖 몸 내밀기·뛰어다니기 금지", "t": "y"},
        {"i": "👟", "tx": "미끄럼 주의 · 운동화 필수 (슬리퍼·하이힐 비추)", "t": "y"},
        {"i": "📅", "tx": "성수기·주말 대기·주차 여유 두고 · 홈페이지/현장 시간표 확인", "t": "g"},
        {"i": "💡", "tx": "고소공포·어지럼증 있으면 진입 전 안내소에 고지", "t": "g"},
        {"i": "📸", "tx": "인증샷은 난간 안쪽에서 — 폰 떨어뜨리면 협곡행", "t": "y"},
        {"i": "🍻", "tx": "음주 후 입장 불가 · 숙취면 다리가 먼저 후들", "t": "r"},
    ]


def ensure_cheongdo(image_data_url: str) -> dict:
    spots = public_get("/api/spots")
    existing = next((s for s in spots if CHEONGDO_NAME in (s.get("name") or "")), None)
    place = kakao_place(CHEONGDO_PLACE_ID)
    addr = place.get("road_address_name") or place.get("address_name") or "경상북도 청도군 운문면 신화랑길 1"
    lat = float(place["y"])
    lng = float(place["x"])
    th, fp, sp2, ap = scores_for_th(2)
    payload = {
        "name": CHEONGDO_NAME,
        "addr": addr,
        "lat": lat,
        "lng": lng,
        "type": "skywalk",
        "tl": "스카이워크",
        "em": "🌉",
        "bg": "#101018",
        "th": th,
        "fp": fp,
        "sp2": sp2,
        "ap": ap,
        "sp": 0,
        "rank": "SKY",
        "br": "청도 신화랑풍류마을 숲속 공중 산책로. 번지·패러처럼 낙하하진 않지만, 협곡 위 스카이트레일에서 난간만 바라봐도 무릎이 먼저 반응한다.",
        "tags": ["#스카이트레일", "#청도", "#신화랑", "#숲속산책", "#고소주의"],
        "warns": skytrail_warns(),
        "reviews": [],
        "img": image_data_url,
        "custom": True,
        "approved": True,
        "coordVerified": True,
        "kakaoPlaceId": CHEONGDO_PLACE_ID,
        "thrillGrade": th,
        "seasonStartMonth": None,
        "seasonEndMonth": None,
    }
    if existing:
        full = api("GET", f"/api/spots/{existing['id']}")
        full.update(payload)
        # keep reviews if any
        full["reviews"] = full.get("reviews") or []
        print(f"UPDATE cheongdo #{existing['id']}")
        return api("PUT", f"/api/spots/{existing['id']}", full)
    print("CREATE cheongdo skytrail")
    return api("POST", "/api/spots", payload)


def recalibrate_all(dry_run: bool) -> None:
    spots = public_get("/api/spots")
    changed = 0
    for s in sorted(spots, key=lambda x: int(x["id"])):
        th = resolve_th(s)
        new_th, fp, sp2, ap = scores_for_th(th)
        old_th = s.get("th")
        old_fp, old_sp2, old_ap = s.get("fp"), s.get("sp2"), s.get("ap")
        old_tg = s.get("thrillGrade")
        try:
            old_pct = round((int(old_fp) + int(old_sp2) + int(old_ap)) / 3)
        except (TypeError, ValueError):
            old_pct = 50
        expected = {1: 26, 2: 40, 3: 55, 4: 72, 5: 88}.get(th, 50)
        need = (
            int(old_th or 0) != new_th
            or int(old_tg or 0) != new_th
            or abs(old_pct - expected) > 12
        )
        if not need:
            continue
        print(
            f"  #{s['id']} [{s.get('type')}] {(s.get('name') or '')[:28]} "
            f"th {old_th}->{new_th} pct {old_pct}->{expected}"
        )
        changed += 1
        if dry_run:
            continue
        full = api("GET", f"/api/spots/{s['id']}")
        full["th"] = new_th
        full["fp"] = fp
        full["sp2"] = sp2
        full["ap"] = ap
        full["thrillGrade"] = new_th
        api("PUT", f"/api/spots/{full['id']}", full)
        time.sleep(0.18)
    print(f"recalibrate changed={changed} dry_run={dry_run}")


def fill_images(dry_run: bool) -> None:
    spots = public_get("/api/spots")
    missing = [s for s in spots if not s.get("hasImage")]
    donors: dict[str, list[int]] = defaultdict(list)
    for s in spots:
        if s.get("hasImage"):
            donors[s.get("type") or "unknown"].append(int(s["id"]))
    print(f"images missing={len(missing)}")
    stock_cache: dict[str, str] = {}
    donor_cache: dict[int, str] = {}
    used: dict[str, int] = {}

    def donor_url(did: int) -> str:
        if did in donor_cache:
            return donor_cache[did]
        req = urllib.request.Request(
            f"{BASE}/api/spots/{did}/image",
            headers={"User-Agent": "DopamineMapRecalibrate/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            jpeg = compress_jpeg(resp.read())
        donor_cache[did] = to_data_url(jpeg)
        return donor_cache[did]

    def stock_url(stype: str) -> str:
        if stype in stock_cache:
            return stock_cache[stype]
        pid = TYPE_PEXELS.get(stype) or TYPE_PEXELS["skywalk"]
        stock_cache[stype] = to_data_url(compress_jpeg(download_pexels(pid)))
        return stock_cache[stype]

    for s in sorted(missing, key=lambda x: int(x["id"])):
        stype = s.get("type") or "unknown"
        dlist = donors.get(stype) or []
        if dlist:
            idx = used.get(stype, 0) % len(dlist)
            used[stype] = idx + 1
            donor_id = dlist[idx]
            src = f"donor #{donor_id}"
        else:
            donor_id = None
            src = f"pexels {stype}"
        print(f"  img #{s['id']} {s['name'][:28]} <- {src}")
        if dry_run:
            continue
        if donor_id is not None:
            img = donor_url(donor_id)
        else:
            img = stock_url(stype)
        full = api("GET", f"/api/spots/{s['id']}")
        full["img"] = img
        api("PUT", f"/api/spots/{s['id']}", full)
        time.sleep(0.3)


def fill_survival(dry_run: bool) -> None:
    templates = load_survival_templates()
    # aliases for types without dedicated templates
    aliases = {
        "highRopes": "netadv",
        "rockClimbing": "default",
        "survivalGame": "default",
        "whitewaterKayak": "jetboat",
        "luge": "coaster",
        "atv": "kart",
        "horse": "default",
        "coaster": "coaster",
    }
    const = load_const()
    spots = public_get("/api/spots")
    filled = 0
    for s in spots:
        full = api("GET", f"/api/spots/{s['id']}")
        if full.get("warns"):
            continue
        t = full.get("type") or "default"
        key = t if t in templates else aliases.get(t, "default")
        tpl = templates.get(key) or templates.get("default") or []
        region = (full.get("name") or "현장").split()[0]
        lines = [str(x).replace("{region}", region) for x in tpl]
        warns = lines_to_warns(lines, const)
        print(f"  warns #{full['id']} [{t}] {full.get('name')[:28]} -> {len(warns)}")
        filled += 1
        if dry_run:
            continue
        full["warns"] = warns
        api("PUT", f"/api/spots/{full['id']}", full)
        time.sleep(0.2)
    print(f"survival filled={filled} dry_run={dry_run}")


def donor_spot_image(spot_id: int) -> str:
    req = urllib.request.Request(
        f"{BASE}/api/spots/{spot_id}/image",
        headers={"User-Agent": "DopamineMapRecalibrate/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return to_data_url(compress_jpeg(resp.read()))


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not KAKAO_KEY:
        print("ERR: KAKAO_REST_API_KEY missing")
        return 2

    print("=== 1) skytrail image (donor skywalk #25) ===")
    sky_img = donor_spot_image(25)
    print("=== 2) register/update cheongdo ===")
    if not dry:
        created = ensure_cheongdo(sky_img)
        print("cheongdo id=", created.get("id"), "th=", created.get("th"), "img=", bool(created.get("img")))
    else:
        print("dry-run skip create")

    print("=== 3) recalibrate thrill ===")
    recalibrate_all(dry)

    print("=== 4) fill images ===")
    fill_images(dry)

    print("=== 5) fill survival ===")
    fill_survival(dry)

    spots = public_get("/api/spots")
    no_img = [s for s in spots if not s.get("hasImage")]
    caves = [s for s in spots if s.get("type") == "cave"]
    print("VERIFY total", len(spots), "no_img", len(no_img))
    for c in caves:
        print(" cave", c["id"], c["name"], "th", c.get("th"), "thrillGrade", c.get("thrillGrade"))
    cd = next((s for s in spots if CHEONGDO_NAME in (s.get("name") or "")), None)
    print("cheongdo listed:", bool(cd), cd and cd.get("id"), cd and cd.get("hasImage"))
    return 0 if not no_img else 1


if __name__ == "__main__":
    raise SystemExit(main())
