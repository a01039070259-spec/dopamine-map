-- Migration: 011_add_legacy_spots
-- Grandfather id<=302 as legacy so publish = coord_verified OR legacy

ALTER TABLE spots ADD COLUMN legacy INTEGER NOT NULL DEFAULT 0;
UPDATE spots SET legacy = 1 WHERE id <= 302;
