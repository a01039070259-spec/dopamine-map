-- Migration: 003_add_visit_tracking
-- Purpose: Store referrer / UTM / landing page on each visit for admin analytics.
-- Scope: visits table columns only. Existing rows keep NULL for new columns.
-- Applied automatically on server startup when referrer column is missing.
-- Backup: dopamine.db.backup_pre_visit_tracking (created by runner.py before first apply)
--
-- Idempotent: runner skips if visits.referrer already exists.
-- Requires SQLite 3.35+ for ADD COLUMN (same as 001_add_venues).

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

ALTER TABLE visits ADD COLUMN referrer TEXT;
ALTER TABLE visits ADD COLUMN utm_source TEXT;
ALTER TABLE visits ADD COLUMN utm_medium TEXT;
ALTER TABLE visits ADD COLUMN utm_campaign TEXT;
ALTER TABLE visits ADD COLUMN landing_page TEXT;

CREATE INDEX IF NOT EXISTS idx_visits_visited_at ON visits(visited_at);
CREATE INDEX IF NOT EXISTS idx_visits_referrer ON visits(referrer);

COMMIT;

PRAGMA foreign_keys = ON;

-- Post-migration checks (optional):
-- PRAGMA table_info(visits);
-- SELECT COUNT(*) FROM visits WHERE referrer IS NULL;
