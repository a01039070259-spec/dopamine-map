-- Migration: 010_categories
-- Purpose: categories table + spots.category_id (keeps type/tl for rollback)

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  group_slug TEXT NOT NULL,
  group_name TEXT NOT NULL,
  icon TEXT,
  sort_order INTEGER DEFAULT 0
);

-- Applied from Python when missing (SQLite lacks IF NOT EXISTS for ADD COLUMN):
-- ALTER TABLE spots ADD COLUMN category_id INTEGER REFERENCES categories(id);
