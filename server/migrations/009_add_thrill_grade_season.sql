-- Migration: 009_add_thrill_grade_season
-- Purpose: Spot thrill grade (1-5) + operating season months
-- Applied automatically on server startup when columns are missing.
-- Note: file is 009 (006 already used by venue_286_287).

ALTER TABLE spots ADD COLUMN thrill_grade INTEGER DEFAULT NULL;
ALTER TABLE spots ADD COLUMN season_start_month INTEGER DEFAULT NULL;
ALTER TABLE spots ADD COLUMN season_end_month INTEGER DEFAULT NULL;
