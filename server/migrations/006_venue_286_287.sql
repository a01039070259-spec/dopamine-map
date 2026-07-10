-- Migration: 006_venue_286_287
-- Purpose: #286 부산 스카이라인 루지 + #287 부산 기장 HyFly 짚라인 → 복합 venue
-- 근거: 동일 주소(기장해안로 205), DB 좌표 0m, 카카오 "스카이라인 루지 부산" 동일 도로명
-- Pattern: 002_map_venues.sql / venue_groups_004.json 과 동일
-- Idempotent: venue name EXISTS 체크 + venue_id IS NULL

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '부산 스카이라인루지(기장해안로)',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 286
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '부산 스카이라인루지(기장해안로)');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '부산 스카이라인루지(기장해안로)')
WHERE id IN (286, 287) AND venue_id IS NULL;

COMMIT;
PRAGMA foreign_keys = ON;
