CREATE TABLE counterparties (
    counterparty_id UUID PRIMARY KEY,
    label VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE counterparty_aliases (
    counterparty_alias_id UUID PRIMARY KEY,
    normalized_descriptor VARCHAR NOT NULL UNIQUE,
    counterparty_id UUID NOT NULL REFERENCES counterparties(counterparty_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE transaction_counterparty_assignments (
    transaction_counterparty_assignment_id UUID PRIMARY KEY,
    raw_transaction_id UUID NOT NULL UNIQUE REFERENCES raw_transactions(raw_transaction_id),
    counterparty_id UUID NOT NULL REFERENCES counterparties(counterparty_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);
