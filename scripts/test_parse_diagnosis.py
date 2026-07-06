"""Dry-run: legacy plain-string diagnosis_result compatibility."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.database import parse_diagnosis_result  # noqa: E402

LEGACY = [
    "하드코어 상급자",
    "잠재적 도파민 중독자",
    "도파민 입문자",
    "극한의 무서움",
    "도파민 각성 직전",
    "스릴 입문자",
    "핵불닭 · 통제불능",
    "매운맛 · 상급자",
    "중간맛 · 각성 직전",
    "순한맛 · 입문자",
    "무맛 · 회전목마 단계",
]

NEW_GRADES = [
    "병아리 감별 필요",
    "무서운데 계속 보는 사람",
    "국가대표급 허세",
    "이미 정상 범주 이탈",
    "지구인 아닌 것으로 추정",
]


def main() -> None:
    print("=== parse_diagnosis_result dry-run ===")

    for s in LEGACY + NEW_GRADES:
        parsed = parse_diagnosis_result(s)
        assert parsed["score"] is None, s
        assert parsed["result"] == s, (s, parsed)
        print(f"OK plain: {s!r}")

    assert parse_diagnosis_result(None) == {"result": None, "score": None}
    print("OK null")

    assert parse_diagnosis_result("") == {"result": None, "score": None}
    print("OK empty")

    assert parse_diagnosis_result("  병아리 감별 필요  ")["result"] == "병아리 감별 필요"
    print("OK trim")

    j = json.dumps({"grade": "국가대표급 허세", "score": 13}, ensure_ascii=False)
    assert parse_diagnosis_result(j) == {"result": "국가대표급 허세", "score": 13}
    print("OK json new format")

    alt = json.dumps({"result": "매운맛 · 상급자", "score": 16}, ensure_ascii=False)
    assert parse_diagnosis_result(alt) == {"result": "매운맛 · 상급자", "score": 16}
    print("OK json alt key (legacy grade name in JSON)")

    # Frontend maps legacy names via LEGACY_DIAGNOSIS_MAP after API read.
    legacy_map = {
        "하드코어 상급자": "지구인 아닌 것으로 추정",
        "매운맛 · 상급자": "이미 정상 범주 이탈",
        "무맛 · 회전목마 단계": "병아리 감별 필요",
    }
    for old, new in legacy_map.items():
        api = parse_diagnosis_result(old)
        normalized = legacy_map.get(api["result"], api["result"])
        assert normalized == new, (old, api, normalized)
        print(f"OK frontend path: {old!r} -> API {api['result']!r} -> {new!r}")

    print("ALL PASSED")


if __name__ == "__main__":
    main()
