-- Migration: 007_rename_venue_13
-- Purpose: venue 13 display name shows both luge + HyFly
-- Idempotent: only renames the previous draft name

UPDATE venues
SET name = '부산 스카이라인 루지 & 하이플라이'
WHERE name = '부산 스카이라인루지(기장해안로)';
