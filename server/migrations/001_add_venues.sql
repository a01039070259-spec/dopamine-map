-- Migration: 001_add_venues
-- Purpose: Introduce venues (physical site / compound) and link spots via venue_id.
-- Scope: Schema only. Existing spots keep venue_id = NULL until a later data migration.
-- Applied automatically on server startup (init_db) when venues table does not exist.
--
-- Manual apply (local):
--   sqlite3 data/dopamine.db ".read server/migrations/001_add_venues.sql"
--
-- Rollback (manual, if needed before any venue_id values are set):
--   DROP INDEX IF EXISTS idx_spots_venue_id;
--   -- SQLite cannot DROP COLUMN before 3.35; recreate spots without venue_id if required.
--   DROP TABLE IF EXISTS venues;

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- ---------------------------------------------------------------------------
-- 1. venues
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    description TEXT,
    main_image TEXT,
    region TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 2. spots.venue_id (nullable FK; existing rows default to NULL)
-- ---------------------------------------------------------------------------
-- Note: IF NOT EXISTS for ADD COLUMN requires SQLite 3.35+.
-- Safe to run once on production; re-run will error on duplicate column name.
ALTER TABLE spots ADD COLUMN venue_id INTEGER REFERENCES venues(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_spots_venue_id ON spots(venue_id);

COMMIT;

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Post-migration checks (optional)
-- ---------------------------------------------------------------------------
-- SELECT COUNT(*) AS venue_count FROM venues;                    -- expect 0
-- SELECT COUNT(*) AS spots_total FROM spots;                     -- expect 132
-- SELECT COUNT(*) AS spots_with_venue FROM spots WHERE venue_id IS NOT NULL;  -- expect 0
-- PRAGMA table_info(spots);                                      -- venue_id column present
-- PRAGMA foreign_key_list(spots);                                -- venue_id -> venues(id)
