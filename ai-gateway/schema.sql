-- Run once only in a dedicated Cloudflare D1 AI budget database.
-- DO NOT run in ReplyPilot / Little King Chess databases.
-- The single row per UTC date is reserved atomically before inference.
-- A failed provider request intentionally consumes a reservation.
CREATE TABLE IF NOT EXISTS ai_daily_calls (
  day TEXT PRIMARY KEY NOT NULL CHECK (length(day) = 10),
  used INTEGER NOT NULL CHECK (used >= 1 AND used <= 10)
);
