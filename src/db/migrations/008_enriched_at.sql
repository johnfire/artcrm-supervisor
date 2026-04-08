-- Add enriched_at to contacts to track when enrichment agent last processed a contact.
-- NULL means never enriched. Allows distinguishing "no email found" from "never tried".
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;
