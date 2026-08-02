CREATE TABLE merchants (
    merchant_id UUID PRIMARY KEY,
    merchant_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_aliases (
    merchant_alias_id UUID PRIMARY KEY,
    normalized_descriptor VARCHAR NOT NULL UNIQUE,
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_currency_observations (
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id),
    currency VARCHAR NOT NULL,
    first_confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (merchant_id, currency)
);

CREATE TABLE categories (
    category_id UUID PRIMARY KEY,
    category_label VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_category_assignments (
    merchant_id UUID PRIMARY KEY REFERENCES merchants(merchant_id),
    category_id UUID NOT NULL REFERENCES categories(category_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE transaction_category_overrides (
    raw_transaction_id UUID PRIMARY KEY REFERENCES raw_transactions(raw_transaction_id),
    category_id UUID NOT NULL REFERENCES categories(category_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE transaction_merchant_annotations (
    raw_transaction_id UUID PRIMARY KEY REFERENCES raw_transactions(raw_transaction_id),
    merchant_id UUID REFERENCES merchants(merchant_id),
    resolution_status VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    method VARCHAR NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    CHECK (resolution_status IN ('confirmed', 'suggested', 'unresolved')),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE recurring_candidates (
    recurring_candidate_id UUID PRIMARY KEY,
    candidate_key VARCHAR NOT NULL UNIQUE,
    account_identity VARCHAR,
    merchant_id UUID REFERENCES merchants(merchant_id),
    normalized_descriptor VARCHAR NOT NULL,
    currency VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    cadence VARCHAR NOT NULL,
    first_transaction_date DATE NOT NULL,
    last_transaction_date DATE NOT NULL,
    amount_min_minor BIGINT NOT NULL,
    amount_max_minor BIGINT NOT NULL,
    expected_next_start DATE NOT NULL,
    expected_next_end DATE NOT NULL,
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'candidate',
    enrichment_version VARCHAR NOT NULL,
    CHECK (direction IN ('debit', 'credit')),
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly', 'annual')),
    CHECK (status = 'candidate')
);

CREATE TABLE duplicate_review_candidates (
    duplicate_candidate_id UUID PRIMARY KEY,
    first_raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    second_raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    UNIQUE (first_raw_transaction_id, second_raw_transaction_id),
    CHECK (first_raw_transaction_id < second_raw_transaction_id),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE unusual_spend_candidates (
    unusual_candidate_id UUID PRIMARY KEY,
    raw_transaction_id UUID NOT NULL UNIQUE REFERENCES raw_transactions(raw_transaction_id),
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    CHECK (confidence >= 0 AND confidence <= 1)
);
