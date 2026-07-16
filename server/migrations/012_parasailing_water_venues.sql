-- Migration: 012_parasailing_water_venues
-- Purpose: Pair each parasailing spot with its jetboat/jetski/yacht sibling into composite venues.
-- Idempotent: venue name EXISTS + venue_id IS NULL only.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1) 가평 캠프통포레스트
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '가평 캠프통포레스트 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '가평 캠프통포레스트 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '가평 캠프통포레스트 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '가평 캠프통포레스트 수상레저')
WHERE venue_id IS NULL
  AND name IN ('가평 캠프통포레스트 파라세일링', '가평 캠프통포레스트 제트보트');

-- 2) 양양 서피비치
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '양양 서피비치 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '양양 서피비치 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '양양 서피비치 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '양양 서피비치 수상레저')
WHERE venue_id IS NULL
  AND name IN ('양양 서피비치 파라세일링', '양양 서피비치 제트보트');

-- 3) 통영 도남
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '통영 도남 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '통영 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '통영 도남 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '통영 도남 수상레저')
WHERE venue_id IS NULL
  AND name IN ('통영 파라세일링', '통영 도남 요트투어');

-- 4) 거제 옥포
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '거제 옥포 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '거제 옥포 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '거제 옥포 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '거제 옥포 수상레저')
WHERE venue_id IS NULL
  AND name IN ('거제 옥포 파라세일링', '거제 옥포 제트보트');

-- 5) 서귀포
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '서귀포 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '서귀포 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '서귀포 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '서귀포 수상레저')
WHERE venue_id IS NULL
  AND name IN ('서귀포 파라세일링', '서귀포 제트보트');

-- 6) 함덕
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '제주 함덕 수상레저',
    addr, NULL, NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE name = '제주 함덕 파라세일링'
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '제주 함덕 수상레저');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '제주 함덕 수상레저')
WHERE venue_id IS NULL
  AND name IN ('제주 함덕 파라세일링', '제주 함덕 제트스키');

COMMIT;
PRAGMA foreign_keys = ON;
