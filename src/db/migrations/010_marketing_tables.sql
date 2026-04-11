-- Marketing strategies: one row per strategy, tracking layer alongside the markdown doc
CREATE TABLE IF NOT EXISTS marketing_strategies (
    id               serial PRIMARY KEY,
    name             text NOT NULL,
    slug             text UNIQUE NOT NULL,
    doc_path         text NOT NULL,
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on_hold', 'paused')),
    priority         int NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    last_reviewed_at timestamptz,
    next_action_due  date,
    notes            text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Marketing research findings: one row per finding from the research agent
CREATE TABLE IF NOT EXISTS marketing_research (
    id          serial PRIMARY KEY,
    strategy_id int REFERENCES marketing_strategies(id) ON DELETE SET NULL,
    run_date    date NOT NULL,
    topic       text NOT NULL,
    summary     text NOT NULL,
    source_url  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Weekly digests: one row per Monday
CREATE TABLE IF NOT EXISTS marketing_digests (
    id         serial PRIMARY KEY,
    week_date  date UNIQUE NOT NULL,
    content    text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the three initial strategies
INSERT INTO marketing_strategies (name, slug, doc_path, status, priority)
VALUES
    ('Plein Air Visibility',   'plein-air',       'plein-air-strategy.md', 'active', 2),
    ('Art Markets',            'markets',          'markets-strategy.md',   'active', 2),
    ('Email Outreach Pipeline','email-outreach',   'AGENTS.md',             'active', 1)
ON CONFLICT (slug) DO NOTHING;
