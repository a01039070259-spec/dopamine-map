-- Migration: 008_add_kakao_place_id
-- Purpose: Store Kakao Local place id when admin picks a place from search.
-- Applied automatically on server startup when the column is missing.

ALTER TABLE spots ADD COLUMN kakao_place_id TEXT;
