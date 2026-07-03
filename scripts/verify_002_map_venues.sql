-- Post-migration verification for 002_map_venues
-- Run on production DB: sqlite3 /app/data/dopamine.db < scripts/verify_002_map_venues.sql

.headers on
.mode column

SELECT 'venues_total' AS check_name, COUNT(*) AS value FROM venues;
-- expect 7

SELECT 'spots_with_venue_id' AS check_name, COUNT(*) AS value
FROM spots WHERE venue_id IS NOT NULL;
-- expect 19

SELECT 'spots_without_venue_id' AS check_name, COUNT(*) AS value
FROM spots WHERE venue_id IS NULL;
-- expect 113

SELECT 'spots_total' AS check_name, COUNT(*) AS value FROM spots;
-- expect 132

SELECT v.id, v.name, COUNT(s.id) AS spot_count
FROM venues v
LEFT JOIN spots s ON s.venue_id = v.id
GROUP BY v.id
ORDER BY v.id;
-- expect 7 rows, spot_count in (2, 3, 5)

SELECT s.id, s.name, s.venue_id, v.name AS venue_name
FROM spots s
LEFT JOIN venues v ON v.id = s.venue_id
WHERE s.venue_id IS NOT NULL
ORDER BY s.venue_id, s.id;
-- expect 19 rows

SELECT s.id, s.name
FROM spots s
WHERE s.id IN (261,265,68,262,53,72,263,271,273,272,17,20,23,25,57,21,26,241,259)
  AND s.venue_id IS NULL;
-- expect 0 rows
