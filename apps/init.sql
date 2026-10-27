CREATE TABLE IF NOT EXISTS notes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    text       TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS notes_created_at_idx ON notes (created_at);