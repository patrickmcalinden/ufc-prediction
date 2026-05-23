-- 003_add_card_order.sql
-- Preserves ESPN card position so the UI can render fights in their real
-- card order (main event first, then co-main, then the rest). Value is
-- computed by the scraper as (cardSeg_index * 100) + match_index.

ALTER TABLE fights ADD COLUMN IF NOT EXISTS card_order INT;
