CREATE TABLE source_documents (
    document_id UUID PRIMARY KEY,
    sha256_hex VARCHAR NOT NULL UNIQUE,
    original_filename VARCHAR NOT NULL,
    mime_type VARCHAR NOT NULL,
    byte_size BIGINT NOT NULL,
    storage_filename VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE import_runs (
    run_id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES source_documents(document_id),
    parser_id VARCHAR NOT NULL,
    parser_version VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    UNIQUE (document_id, parser_id, parser_version)
);

CREATE TABLE raw_transactions (
    raw_transaction_id UUID PRIMARY KEY,
    import_run_id UUID NOT NULL REFERENCES import_runs(run_id),
    source_ordinal BIGINT NOT NULL,
    date_text VARCHAR NOT NULL,
    description_text VARCHAR NOT NULL,
    amount_text VARCHAR NOT NULL,
    currency_text VARCHAR,
    source_page BIGINT,
    source_row BIGINT,
    source_text VARCHAR,
    extraction_method VARCHAR NOT NULL,
    raw_account_identity VARCHAR,
    raw_account_reference VARCHAR,
    raw_balance_text VARCHAR,
    extraction_confidence DOUBLE NOT NULL,
    UNIQUE (import_run_id, source_ordinal)
);

CREATE TABLE import_errors (
    error_id UUID PRIMARY KEY,
    document_sha256_hex VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    declared_mime_type VARCHAR NOT NULL,
    parser_id VARCHAR,
    parser_version VARCHAR,
    error_type VARCHAR NOT NULL,
    error_message VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);
