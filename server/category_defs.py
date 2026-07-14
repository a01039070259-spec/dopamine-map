# -*- coding: utf-8 -*-
"""Canonical category taxonomy (migration 010) + type/tl → category resolver."""
from __future__ import annotations

from typing import Optional

# (slug, name, group_slug, group_name, icon, sort_order)
CATEGORY_SEED: list[tuple[str, str, str, str, str, int]] = [
    # sky
    ("paragliding", "패러글라이딩", "sky", "하늘", "🪂", 10),
    ("bungee", "번지점프", "sky", "하늘", "🪢", 20),
    ("zipline", "짚라인", "sky", "하늘", "🪢", 30),
    ("indoor-skydiving", "실내스카이다이빙", "sky", "하늘", "💨", 40),
    ("balloon", "열기구", "sky", "하늘", "🎈", 50),
    ("big-swing", "빅스윙", "sky", "하늘", "🌀", 60),
    ("light-aircraft", "경비행기", "sky", "하늘", "✈️", 70),
    ("hang-glider", "행글라이더", "sky", "하늘", "🪂", 80),
    # water
    ("rafting", "래프팅", "water", "물", "🛶", 10),
    ("whitewater-kayak", "급류 카약", "water", "물", "🛶", 20),
    ("jetboat", "제트보트", "water", "물", "🚤", 30),
    ("parasailing", "패러세일링", "water", "물", "🪂", 40),
    ("seawalk", "씨워킹", "water", "물", "🤿", 50),
    ("cave-boat", "케이브보트", "water", "물", "🚤", 60),
    # land
    ("luge", "루지", "land", "땅", "🛷", 10),
    ("alpine-coaster", "알파인코스터", "land", "땅", "🎢", 20),
    ("skybike", "스카이바이크", "land", "땅", "🚲", 30),
    ("monorail", "모노레일", "land", "땅", "🚋", 40),
    ("canyoning", "캐녀닝", "land", "땅", "🏔️", 50),
    ("rock-climbing", "자연 암벽등반", "land", "땅", "🧗", 60),
    ("high-ropes", "하이로프", "land", "땅", "🪢", 70),
    ("survival-game", "서바이벌 게임", "land", "땅", "🪖", 80),
    ("shooting", "실탄사격", "land", "땅", "🎯", 90),
    ("animal-riding", "동물라이딩", "land", "땅", "🐴", 100),
    ("skywalk", "스카이워크", "land", "땅", "🌉", 110),
    ("slide", "슬라이드", "land", "땅", "🛝", 120),
    ("cave-explore", "동굴탐험", "land", "땅", "🦇", 130),
    # speed
    ("kart", "카트", "speed", "스피드", "🏎️", 10),
    ("atv", "ATV", "speed", "스피드", "🛵", 20),
    ("offroad", "오프로드", "speed", "스피드", "🚙", 30),
    ("suv-offroad", "SUV오프로드", "speed", "스피드", "🚙", 40),
    ("mtb-downhill", "MTB 다운힐", "speed", "스피드", "🚵", 50),
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
    "seawalk": "seawalk",
    "luge": "luge",
    "coaster": "alpine-coaster",
    "skybike": "skybike",
    "monorail": "monorail",
    "canyoning": "canyoning",
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
    "mtbDownhill": "mtb-downhill",
    "amphibious": "amphibious",
}


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
