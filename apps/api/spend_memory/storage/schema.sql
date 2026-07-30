CREATE TABLE IF NOT EXISTS storage_migrations (
    version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);
