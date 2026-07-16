# -*- coding: utf-8 -*-
"""Canonical category taxonomy (migration 010) + type/tl → category resolver."""
from __future__ import annotations

from typing import Optional

# (slug, name, group_slug, group_name, icon, sort_order)
CATEGORY_SEED: list[tuple[str, str, str, str, str, int]] = [
    # sky — 일반인이 바로 알아듣는 짧은 한글명
    ("paragliding", "패러글라이딩", "sky", "하늘", "🪂", 10),
    ("bungee", "번지점프", "sky", "하늘", "🔻", 20),
    ("zipline", "짚라인", "sky", "하늘", "➰", 30),
    ("indoor-skydiving", "실내스카이다이빙", "sky", "하늘", "💨", 40),
    ("balloon", "열기구", "sky", "하늘", "🎈", 50),
    ("big-swing", "빅스윙", "sky", "하늘", "🌀", 60),
    ("light-aircraft", "경비행기", "sky", "하늘", "✈️", 70),
    ("hang-glider", "행글라이더", "sky", "하늘", "🪁", 80),
    # water
    ("rafting", "래프팅", "water", "물", "🛶", 10),
    ("whitewater-kayak", "급류카약", "water", "물", "🛶", 20),
    ("jetboat", "제트보트", "water", "물", "🚤", 30),
    ("parasailing", "패러세일링", "water", "물", "🪂", 40),
    ("seawalk", "바닷속걷기", "water", "물", "🤿", 50),
    ("cave-boat", "동굴보트", "water", "물", "🚤", 60),
    # land
    ("luge", "루지", "land", "땅", "🛷", 10),
    ("alpine-coaster", "롤러코스터", "land", "땅", "🎢", 20),
    ("skybike", "공중자전거", "land", "땅", "🚲", 30),
    ("monorail", "모노레일", "land", "땅", "🚋", 40),
    ("railbike", "레일바이크", "land", "땅", "🚞", 45),
    ("rock-climbing", "암벽등반", "land", "땅", "🧗", 60),
    ("high-ropes", "숲속모험", "land", "땅", "🪜", 70),
    ("survival-game", "서바이벌", "land", "땅", "🪖", 80),
    ("shooting", "실탄사격", "land", "땅", "🎯", 90),
    ("animal-riding", "승마", "land", "땅", "🐴", 100),
    ("skywalk", "스카이워크", "land", "땅", "🌉", 110),
    ("slide", "슬라이드", "land", "땅", "🛝", 120),
    ("cave-explore", "동굴탐험", "land", "땅", "🦇", 130),
    # speed
    ("kart", "카트", "speed", "스피드", "🏎️", 10),
    ("atv", "ATV", "speed", "스피드", "🏍️", 20),
    ("offroad", "오프로드", "speed", "스피드", "🚙", 30),
    ("suv-offroad", "SUV체험", "speed", "스피드", "🚙", 40),
    ("amphibious", "수륙양용차", "speed", "스피드", "🚢", 60),
]

GROUP_META = {
    "sky": {"name": "하늘", "icon": "🪂", "sort_order": 1},
    "water": {"name": "물", "icon": "🌊", "sort_order": 2},
    "land": {"name": "땅", "icon": "🏔️", "sort_order": 3},
    "speed": {"name": "스피드", "icon": "🏎️", "sort_order": 4},
}

TYPE_TO_SLUG = {
    "paragliding": "paragliding",
    "bungee": "bungee",
    "zipline": "zipline",
    "sky": "indoor-skydiving",
    "balloon": "balloon",
    "swing": "big-swing",
    "aircraft": "light-aircraft",
    "hangglider": "hang-glider",
    "whitewaterKayak": "whitewater-kayak",
    "jetboat": "jetboat",
    "speedboat": "jetboat",
    "parasailing": "parasailing",
    "seawalk": "seawalk",
    "luge": "luge",
    "coaster": "alpine-coaster",
    "skybike": "skybike",
    "monorail": "monorail",
    "railbike": "railbike",
    "rockClimbing": "rock-climbing",
    "highRopes": "high-ropes",
    "netadv": "high-ropes",
    "survivalGame": "survival-game",
    "shooting": "shooting",
    "horse": "animal-riding",
    "skywalk": "skywalk",
    "slide": "slide",
    "cave": "cave-explore",
    "kart": "kart",
    "atv": "atv",
    "amphibious": "amphibious",
}

# 홈/맵에서 제거한 카테고리 — 시작 시 DB 정리
RETIRED_CATEGORY_SLUGS: frozenset[str] = frozenset({"canyoning", "mtb-downhill"})
RETIRED_SPOT_TYPES: frozenset[str] = frozenset({"canyoning", "mtbDownhill"})


def resolve_category_slug(type_key: str, tl: str) -> Optional[str]:
    """Map legacy type + tl → canonical category slug. None = unmapped."""
    t = (type_key or "").strip()
    label = (tl or "").strip()

    if label == "오프로드":
        return "offroad"
    if label == "SUV오프로드":
        return "suv-offroad"
    if label == "레이저서바이벌":
        return "survival-game"
    if label == "슬링샷":
        return "bungee"
    if label == "페달보트":
        return "jetboat"

    return TYPE_TO_SLUG.get(t)
