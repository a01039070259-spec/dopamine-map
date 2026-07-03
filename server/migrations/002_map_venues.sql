-- Migration: 002_map_venues
-- Purpose: Create 7 real venue rows and link 19 grouped spots via venue_id.
-- Applied automatically on server startup when venue names are not yet present.
-- Backup: dopamine.db.backup_pre_venue_data (created by runner.py before first apply)
--
-- Idempotent: each INSERT runs only if the venue name is missing; UPDATE only sets NULL venue_id.

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- Helper pattern: region = first token of representative spot address
-- Venue 1: 인제엑스게임리조트 (261, 265, 68) — rep 261
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '인제엑스게임리조트',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 261
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '인제엑스게임리조트');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '인제엑스게임리조트')
WHERE id IN (261, 265, 68) AND venue_id IS NULL;

-- Venue 2: 하동알프스레포츠(금오산) (262, 53) — rep 262
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '하동알프스레포츠(금오산)',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 262
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '하동알프스레포츠(금오산)');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '하동알프스레포츠(금오산)')
WHERE id IN (262, 53) AND venue_id IS NULL;

-- Venue 3: 제천청풍랜드 (72, 263) — rep 72
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '제천청풍랜드',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 72
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '제천청풍랜드');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '제천청풍랜드')
WHERE id IN (72, 263) AND venue_id IS NULL;

-- Venue 4: 대천짚트랙타워 (271, 273, 272) — rep 271
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '대천짚트랙타워',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 271
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '대천짚트랙타워');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '대천짚트랙타워')
WHERE id IN (271, 273, 272) AND venue_id IS NULL;

-- Venue 5: 단양만천하스카이워크 (17, 20, 23, 25, 57) — rep 17
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '단양만천하스카이워크',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 17
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '단양만천하스카이워크');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '단양만천하스카이워크')
WHERE id IN (17, 20, 23, 25, 57) AND venue_id IS NULL;

-- Venue 6: 해남땅끝마을스카이워크 (21, 26) — rep 21
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '해남땅끝마을스카이워크',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 21
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '해남땅끝마을스카이워크');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '해남땅끝마을스카이워크')
WHERE id IN (21, 26) AND venue_id IS NULL;

-- Venue 7: 거제바람의(도장포) (241, 259) — rep 241
INSERT INTO venues (name, address, description, main_image, region)
SELECT
    '거제바람의(도장포)',
    addr,
    NULL,
    NULL,
    CASE WHEN instr(trim(addr), ' ') > 0
         THEN substr(trim(addr), 1, instr(trim(addr), ' ') - 1)
         ELSE trim(addr) END
FROM spots
WHERE id = 241
  AND NOT EXISTS (SELECT 1 FROM venues WHERE name = '거제바람의(도장포)');

UPDATE spots SET venue_id = (SELECT id FROM venues WHERE name = '거제바람의(도장포)')
WHERE id IN (241, 259) AND venue_id IS NULL;

COMMIT;

PRAGMA foreign_keys = ON;
