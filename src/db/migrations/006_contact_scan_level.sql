-- Add scan_level to contacts to track which research level found each contact.
-- Backfill existing contacts by mapping type to level.

ALTER TABLE contacts ADD COLUMN IF NOT EXISTS scan_level int;

UPDATE contacts SET scan_level = CASE
    WHEN type IN ('gallery', 'cafe', 'interior_designer', 'coworking') THEN 1
    WHEN type IN ('gift_shop', 'wellness', 'concept_store')            THEN 2
    WHEN type IN ('restaurant')                                         THEN 3
    WHEN type IN ('corporate_office')                                   THEN 4
    WHEN type IN ('hotel')                                              THEN 5
    ELSE NULL
END
WHERE scan_level IS NULL;
