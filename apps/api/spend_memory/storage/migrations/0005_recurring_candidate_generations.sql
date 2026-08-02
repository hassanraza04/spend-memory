CREATE TABLE recurring_candidate_generations (
    generation_id UUID PRIMARY KEY,
    candidate_count BIGINT NOT NULL,
    member_count BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    CHECK (candidate_count >= 0),
    CHECK (member_count >= 0)
);

CREATE TEMP TABLE recurring_candidate_initial_generation AS
SELECT uuid() AS generation_id;

INSERT INTO recurring_candidate_generations (
    generation_id, candidate_count, member_count
)
SELECT
    generation_id,
    (SELECT count(*) FROM recurring_candidates),
    (SELECT count(*) FROM recurring_candidate_members)
FROM recurring_candidate_initial_generation;

CREATE TEMP TABLE recurring_candidates_before_generations AS
SELECT * FROM recurring_candidates;

CREATE TEMP TABLE recurring_candidate_members_before_generations AS
SELECT * FROM recurring_candidate_members;

DROP TABLE recurring_candidate_members;
DROP TABLE recurring_candidates;

CREATE TABLE recurring_candidates (
    recurring_candidate_id UUID PRIMARY KEY,
    generation_id UUID NOT NULL REFERENCES recurring_candidate_generations(generation_id),
    candidate_key VARCHAR NOT NULL,
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
    UNIQUE (generation_id, candidate_key),
    CHECK (direction IN ('debit', 'credit')),
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly', 'annual')),
    CHECK (status = 'candidate')
);

INSERT INTO recurring_candidates
SELECT
    old.recurring_candidate_id,
    initial.generation_id,
    old.candidate_key,
    old.account_identity,
    old.merchant_id,
    old.normalized_descriptor,
    old.currency,
    old.direction,
    old.cadence,
    old.first_transaction_date,
    old.last_transaction_date,
    old.amount_min_minor,
    old.amount_max_minor,
    old.expected_next_start,
    old.expected_next_end,
    old.confidence,
    old.evidence_json,
    old.status,
    old.enrichment_version
FROM recurring_candidates_before_generations old
CROSS JOIN recurring_candidate_initial_generation initial;

CREATE TABLE recurring_candidate_members (
    recurring_candidate_id UUID NOT NULL REFERENCES recurring_candidates(recurring_candidate_id),
    raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    PRIMARY KEY (recurring_candidate_id, raw_transaction_id)
);

INSERT INTO recurring_candidate_members
SELECT * FROM recurring_candidate_members_before_generations;

CREATE TABLE recurring_candidate_state (
    state_key VARCHAR PRIMARY KEY,
    active_generation_id UUID NOT NULL REFERENCES recurring_candidate_generations(generation_id),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    CHECK (state_key = 'active')
);

INSERT INTO recurring_candidate_state (state_key, active_generation_id)
SELECT 'active', generation_id
FROM recurring_candidate_initial_generation;

DROP TABLE recurring_candidate_initial_generation;
DROP TABLE recurring_candidate_members_before_generations;
DROP TABLE recurring_candidates_before_generations;
