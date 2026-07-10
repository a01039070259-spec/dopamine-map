-- Migration: 005_add_coord_verified
-- Purpose: Track spots whose lat/lng were human/audit verified.
--          Venue representative coordinates prefer verified member spots.
-- Applied automatically on server startup when the column is missing.

ALTER TABLE spots ADD COLUMN coord_verified INTEGER NOT NULL DEFAULT 0;
