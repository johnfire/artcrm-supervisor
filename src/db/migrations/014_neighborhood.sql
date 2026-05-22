-- Migration 014: add neighborhood field to contacts
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS neighborhood TEXT;

CREATE INDEX IF NOT EXISTS idx_contacts_neighborhood ON contacts (neighborhood) WHERE deleted_at IS NULL;
