# -*- coding: utf-8 -*-
"""D그룹 ∩ placeholder_addr → d_group_risky.csv (조회만)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "coord_audit.csv"
INTEGRITY = ROOT / "scripts" / "integrity_report.csv"
OUT_RISKY = ROOT / "scripts" / "d_group_risky.csv"
OUT_OK = ROOT / "scripts" / "d_group_kakao_missing.csv"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    d_rows: dict[int, dict] = {}
    with open(AUDIT, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("group") or "").upper() == "D":
                d_rows[int(r["spot_id"])] = r

    placeholders: dict[int, dict] = {}
    with open(INTEGRITY, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("issue_type") == "placeholder_addr":
                placeholders[int(r["spot_id"])] = r

    risky_ids = sorted(set(d_rows) & set(placeholders))
    ok_ids = sorted(set(d_rows) - set(placeholders))

    risky_fields = ["spot_id", "name", "addr", "lat", "lng", "placeholder_reason"]
    with open(OUT_RISKY, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=risky_fields)
        w.writeheader()
        for sid in risky_ids:
            p = placeholders[sid]
            a = d_rows[sid]
            w.writerow(
                {
                    "spot_id": sid,
                    "name": p.get("name") or a.get("name"),
                    "addr": p.get("addr") or a.get("db_addr"),
                    "lat": p.get("lat") or a.get("db_lat"),
                    "lng": p.get("lng") or a.get("db_lng"),
                    "placeholder_reason": p.get("detail") or "",
                }
            )

    ok_fields = ["spot_id", "name", "db_addr", "db_lat", "db_lng", "note"]
    with open(OUT_OK, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=ok_fields)
        w.writeheader()
        for sid in ok_ids:
            a = d_rows[sid]
            w.writerow(
                {
                    "spot_id": sid,
                    "name": a.get("name"),
                    "db_addr": a.get("db_addr"),
                    "db_lat": a.get("db_lat"),
                    "db_lng": a.get("db_lng"),
                    "note": "카카오 미등록으로 간주 — 조치 없음",
                }
            )

    print(f"D그룹 {len(d_rows)}건")
    print(f"d_group_risky.csv: {len(risky_ids)}건 → {OUT_RISKY}")
    for sid in risky_ids:
        p = placeholders[sid]
        print(f"  #{sid} {p.get('name')} — {p.get('detail')}")
    print(f"d_group_kakao_missing.csv: {len(ok_ids)}건 (조치 없음) → {OUT_OK}")


if __name__ == "__main__":
    main()
