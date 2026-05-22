-- Chains/brands to permanently ignore when scouting contacts.
-- Any new contact whose name is >= 90% similar to an entry here
-- is silently skipped by save_contact.
CREATE TABLE IF NOT EXISTS ignored_chains (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    reason     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO ignored_chains (name, reason) VALUES
    ('NANU-NANA',      'Mass-market gift chain, not suitable for art placement'),
    ('Søstrene Grene', 'Scandinavian mass-market design chain, not suitable for art placement')
ON CONFLICT (name) DO NOTHING;
