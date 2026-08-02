CREATE TABLE recurring_candidate_members (
    recurring_candidate_id UUID NOT NULL REFERENCES recurring_candidates(recurring_candidate_id),
    raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    PRIMARY KEY (recurring_candidate_id, raw_transaction_id)
);
